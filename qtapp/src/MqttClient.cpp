#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "MqttClient.hpp"

#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QJsonValue>
#include <QMutex>
#include <QMutexLocker>
#include <QUuid>
#include <QWaitCondition>
#include <QtEndian>

#include <algorithm>
#include <cmath>
#include <chrono>
#include <cstring>
#include <thread>
#include <vector>

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

namespace sieans_qt {
namespace {

constexpr int kMaxPayload = 65536;
constexpr int kMaxTopicBytes = 1024;
constexpr int kMaxLevels = 64;
constexpr int kMaxRetained = 100;

struct Retained {
  QByteArray payload;
  int qos = 0;
};

QMutex gStoreMutex;
QHash<QString, Retained> gRetained;
int gRetainedBytes = 0;
// In-process waiters for simulator receive (topic filter -> sequence of new messages).
struct LiveMsg {
  QString topic;
  QByteArray payload;
  int qos = 0;
  bool retain = false;
  bool dup = false;
};
QList<LiveMsg> gLive;
QWaitCondition gLiveCv;
quint64 gLiveSeq = 0;

QMutex gServerMutex;
MqttSoftBroker* gServer = nullptr;
int gListenFd = -1;
quint16 gListenPort = 0;
bool gServerRun = false;

struct SubClient {
  int fd = -1;
  QMutex writeMu;
  QVector<QPair<QString, int>> filters;
  bool alive = true;
};
QMutex gSubsMutex;
QList<SubClient*> gSubs;

void ensureStore() {
  // retained map starts empty; no default message.
}

/* ---------------- packet IO ---------------- */

QByteArray encLen(int n) {
  QByteArray b;
  do {
    quint8 d = quint8(n % 128);
    n /= 128;
    if (n) d |= 0x80;
    b.append(char(d));
  } while (n);
  return b;
}

QByteArray mqttPacket(quint8 typeFlags, const QByteArray& body) {
  QByteArray out;
  out.append(char(typeFlags));
  out.append(encLen(body.size()));
  out.append(body);
  return out;
}

void appendMqttStr(QByteArray& b, const QString& s) {
  const QByteArray u = s.toUtf8();
  const quint16 n = quint16(u.size());
  char be[2];
  qToBigEndian(n, be);
  b.append(be, 2);
  b.append(u);
}

void appendU16(QByteArray& b, quint16 v) {
  char be[2];
  qToBigEndian(v, be);
  b.append(be, 2);
}

int setTimeo(int fd, int timeoutMs) {
  timeval tv{};
  tv.tv_sec = timeoutMs / 1000;
  tv.tv_usec = (timeoutMs % 1000) * 1000;
  setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
  return fd;
}

bool sendAll(int fd, const QByteArray& buf, QString* error) {
  int off = 0;
  while (off < buf.size()) {
    const ssize_t n =
        ::send(fd, buf.constData() + off, size_t(buf.size() - off), MSG_NOSIGNAL);
    if (n < 0) {
      if (errno == EINTR) continue;
      *error = (errno == EAGAIN || errno == EWOULDBLOCK)
                   ? QStringLiteral("MQTT 操作超时")
                   : QStringLiteral("MQTT 发送失败: %1")
                         .arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    off += int(n);
  }
  return true;
}

bool recvExact(int fd, int want, QByteArray* out, QString* error) {
  out->clear();
  while (out->size() < want) {
    char tmp[1024];
    const ssize_t n =
        ::recv(fd, tmp, size_t(std::min(int(want - out->size()), 1024)), 0);
    if (n < 0) {
      if (errno == EINTR) continue;
      *error = (errno == EAGAIN || errno == EWOULDBLOCK)
                   ? QStringLiteral("MQTT 操作超时")
                   : QStringLiteral("MQTT 接收失败: %1")
                         .arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    if (n == 0) {
      *error = QStringLiteral("MQTT 连接在操作完成前关闭");
      return false;
    }
    out->append(tmp, int(n));
  }
  return true;
}

struct MqttPkt {
  quint8 type = 0;
  quint8 flags = 0;
  QByteArray body;
};

bool recvPkt(int fd, MqttPkt* pkt, QString* error) {
  QByteArray b1;
  if (!recvExact(fd, 1, &b1, error)) return false;
  pkt->type = quint8(b1[0]) >> 4;
  pkt->flags = quint8(b1[0]) & 0x0f;
  int len = 0;
  int mul = 1;
  for (int i = 0; i < 4; ++i) {
    QByteArray lb;
    if (!recvExact(fd, 1, &lb, error)) return false;
    const quint8 d = quint8(lb[0]);
    len += int(d & 0x7f) * mul;
    if (!(d & 0x80)) break;
    mul *= 128;
    if (i == 3) {
      *error = QStringLiteral("MQTT 报文长度无效");
      return false;
    }
  }
  if (len < 0 || len > kMaxPayload + 1024) {
    *error = QStringLiteral("MQTT 报文长度无效");
    return false;
  }
  if (len > 0 && !recvExact(fd, len, &pkt->body, error)) return false;
  if (len == 0) pkt->body.clear();
  return true;
}

struct Cursor {
  QByteArray d;
  int off = 0;
  bool ok = true;
  explicit Cursor(const QByteArray& b) : d(b) {}
  int remain() const { return d.size() - off; }
  bool need(int n) {
    if (!ok || remain() < n) {
      ok = false;
      return false;
    }
    return true;
  }
  quint8 u8() {
    if (!need(1)) return 0;
    return quint8(d.at(off++));
  }
  quint16 u16() {
    if (!need(2)) return 0;
    const quint16 v = qFromBigEndian<quint16>(d.constData() + off);
    off += 2;
    return v;
  }
  QByteArray raw(int n) {
    if (n < 0 || !need(n)) return {};
    QByteArray s = d.mid(off, n);
    off += n;
    return s;
  }
  QString str() {
    const quint16 n = u16();
    return QString::fromUtf8(raw(n));
  }
};

/* ---------------- topic / payload ---------------- */

bool validTopic(const QString& topic, bool receive, QString* error) {
  if (topic.isEmpty() || topic.size() > kMaxTopicBytes) {
    *error = QStringLiteral("MQTT 主题无效");
    return false;
  }
  const QByteArray raw = topic.toUtf8();
  if (raw.size() > kMaxTopicBytes) {
    *error = QStringLiteral("MQTT 主题无效");
    return false;
  }
  for (unsigned char c : raw) {
    if (c < 0x20 || c == 0x7f) {
      *error = QStringLiteral("MQTT 主题无效");
      return false;
    }
  }
  if (topic.startsWith(QLatin1String("$share/"))) {
    *error = QStringLiteral("当前不支持共享订阅");
    return false;
  }
  const QStringList levels = topic.split(QLatin1Char('/'));
  if (levels.size() > kMaxLevels) {
    *error = QStringLiteral("主题层级最多 64 层");
    return false;
  }
  if (!receive) {
    if (topic.contains(QLatin1Char('+')) || topic.contains(QLatin1Char('#'))) {
      *error = QStringLiteral("发布主题不能包含通配符");
      return false;
    }
    if (topic.startsWith(QLatin1String("$SYS/"))) {
      *error = QStringLiteral("模拟器消息超出范围");
      return false;
    }
    return true;
  }
  for (int i = 0; i < levels.size(); ++i) {
    const QString& p = levels[i];
    if (p.contains(QLatin1Char('+')) && p != QLatin1String("+")) {
      *error = QStringLiteral("订阅通配符 + 必须独占层级，# 必须位于最后一层");
      return false;
    }
    if (p.contains(QLatin1Char('#')) &&
        !(p == QLatin1String("#") && i == levels.size() - 1)) {
      *error = QStringLiteral("订阅通配符 + 必须独占层级，# 必须位于最后一层");
      return false;
    }
  }
  return true;
}

bool topicMatch(const QString& filter, const QString& topic) {
  const QStringList f = filter.split(QLatin1Char('/'));
  const QStringList t = topic.split(QLatin1Char('/'));
  for (int i = 0; i < f.size(); ++i) {
    if (f[i] == QLatin1String("#")) return i == f.size() - 1;
    if (i >= t.size()) return false;
    if (f[i] != QLatin1String("+") && f[i] != t[i]) return false;
  }
  return f.size() == t.size();
}

QJsonValue toJson(const QVariant& v, QString* error, int depth = 0) {
  if (depth > 20) {
    *error = QStringLiteral("消息数据嵌套最多 20 层");
    return {};
  }
  if (!v.isValid() || v.isNull()) return QJsonValue();
  switch (v.typeId()) {
    case QMetaType::Bool:
      return QJsonValue(v.toBool());
    case QMetaType::Int:
    case QMetaType::UInt:
    case QMetaType::Long:
    case QMetaType::ULong:
    case QMetaType::LongLong:
    case QMetaType::ULongLong:
    case QMetaType::Double:
    case QMetaType::Float: {
      const double d = v.toDouble();
      if (!std::isfinite(d)) {
        *error = QStringLiteral("消息数值必须有限，大整数请用文本表示");
        return {};
      }
      return QJsonValue(d);
    }
    case QMetaType::QString:
      if (v.toString().toUtf8().size() > kMaxPayload) {
        *error = QStringLiteral("消息文本无效或超过 64 KiB");
        return {};
      }
      return QJsonValue(v.toString());
    case QMetaType::QVariantList: {
      QJsonArray a;
      const QVariantList lst = v.toList();
      if (lst.size() > 10000) {
        *error = QStringLiteral("消息字段或元素超过 10000 项");
        return {};
      }
      for (const QVariant& x : lst) {
        const QJsonValue j = toJson(x, error, depth + 1);
        if (!error->isEmpty()) return {};
        a.append(j);
      }
      return a;
    }
    case QMetaType::QVariantMap: {
      QJsonObject o;
      const QVariantMap m = v.toMap();
      if (m.size() > 10000) {
        *error = QStringLiteral("消息字段或元素超过 10000 项");
        return {};
      }
      for (auto it = m.begin(); it != m.end(); ++it) {
        if (it.key() == QLatin1String("__proto__") ||
            it.key() == QLatin1String("prototype") ||
            it.key() == QLatin1String("constructor")) {
          *error = QStringLiteral("消息字段包含保留名称");
          return {};
        }
        const QJsonValue j = toJson(it.value(), error, depth + 1);
        if (!error->isEmpty()) return {};
        o.insert(it.key(), j);
      }
      return o;
    }
    default:
      *error = QStringLiteral("消息仅支持数值、文本、开关、数组和结构体");
      return {};
  }
}

QByteArray jsonBytes(const QJsonValue& j) {
  if (j.isObject())
    return QJsonDocument(j.toObject()).toJson(QJsonDocument::Compact);
  if (j.isArray())
    return QJsonDocument(j.toArray()).toJson(QJsonDocument::Compact);
  if (j.isNull()) return QByteArray("null");
  if (j.isBool()) return j.toBool() ? QByteArray("true") : QByteArray("false");
  if (j.isDouble()) {
    const double d = j.toDouble();
    if (d == qRound(d) && std::fabs(d) < 1e15)
      return QByteArray::number(qint64(d));
    return QByteArray::number(d, 'g', 16);
  }
  if (j.isString()) {
    QJsonArray wrap;
    wrap.append(j);
    QByteArray a = QJsonDocument(wrap).toJson(QJsonDocument::Compact);
    // ["..."] -> "..."
    if (a.startsWith('[') && a.endsWith(']'))
      return a.mid(1, a.size() - 2);
  }
  return {};
}

QVariant fromJsonValue(const QJsonValue& j) {
  if (j.isBool()) return j.toBool();
  if (j.isDouble()) {
    const double d = j.toDouble();
    if (d == qRound(d) && std::fabs(d) < 2e9) return int(d);
    return d;
  }
  if (j.isString()) return j.toString();
  if (j.isArray()) return j.toArray().toVariantList();
  if (j.isObject()) return j.toObject().toVariantMap();
  return QVariant();
}

bool encodePayload(const QVariant& value, const QString& encoding, QByteArray* raw,
                   QString* error) {
  if (encoding == QLatin1String("bytes")) {
    if (value.metaType().id() != QMetaType::QVariantList) {
      *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
      return false;
    }
    const QVariantList lst = value.toList();
    if (lst.size() > kMaxPayload) {
      *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
      return false;
    }
    raw->resize(lst.size());
    for (int i = 0; i < lst.size(); ++i) {
      bool ok = false;
      const int n = lst[i].toInt(&ok);
      if (!ok || n < 0 || n > 255) {
        *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
        return false;
      }
      (*raw)[i] = char(n);
    }
    return true;
  }
  if (encoding == QLatin1String("text")) {
    const QString s = value.toString();
    *raw = s.toUtf8();
    if (raw->size() > kMaxPayload) {
      *error = QStringLiteral("消息体超过 64 KiB");
      return false;
    }
    return true;
  }
  if (encoding != QLatin1String("structured")) {
    *error = QStringLiteral("MQTT 消息格式无效");
    return false;
  }
  const QJsonValue j = toJson(value, error);
  if (!error->isEmpty()) return false;
  *raw = jsonBytes(j);
  if (raw->size() > kMaxPayload) {
    *error = QStringLiteral("消息体超过 64 KiB");
    return false;
  }
  return true;
}

bool decodePayload(const QByteArray& raw, const QString& encoding, QVariant* value,
                   QString* error) {
  if (raw.size() > kMaxPayload) {
    *error = QStringLiteral("收到的消息体超过 64 KiB");
    return false;
  }
  if (encoding == QLatin1String("bytes")) {
    QVariantList lst;
    lst.reserve(raw.size());
    for (unsigned char b : raw) lst.push_back(int(b));
    *value = lst;
    return true;
  }
  // UTF-8
  if (raw.contains('\0')) {
    *error = QStringLiteral("消息不是有效 UTF-8 文本，请选择字节数组");
    return false;
  }
  QString text = QString::fromUtf8(raw);
  if (text.toUtf8() != raw) {
    *error = QStringLiteral("消息不是有效 UTF-8 文本，请选择字节数组");
    return false;
  }
  if (encoding == QLatin1String("text")) {
    *value = text;
    return true;
  }
  QJsonParseError err;
  QJsonDocument doc = QJsonDocument::fromJson(raw, &err);
  QJsonValue jv;
  if (err.error == QJsonParseError::NoError && !doc.isNull()) {
    jv = doc.isObject() ? QJsonValue(doc.object())
                        : doc.isArray() ? QJsonValue(doc.array()) : QJsonValue();
  } else {
    const QByteArray wrapped = QByteArray("[") + raw + "]";
    QJsonParseError err2;
    QJsonDocument w = QJsonDocument::fromJson(wrapped, &err2);
    if (err2.error != QJsonParseError::NoError || !w.isArray() || w.array().size() != 1) {
      *error = QStringLiteral("消息不是有效的结构化数据，请检查发送格式或选择文本");
      return false;
    }
    jv = w.array().at(0);
  }
  *value = fromJsonValue(jv);
  return true;
}

/* ---------------- store ---------------- */

QString storePublish(const QString& topic, const QByteArray& payload, int qos,
                     bool retain) {
  QMutexLocker lock(&gStoreMutex);
  if (retain) {
    const int prev = gRetained.contains(topic) ? gRetained[topic].payload.size() : 0;
    if (payload.isEmpty()) {
      if (gRetained.contains(topic)) {
        gRetainedBytes -= prev;
        gRetained.remove(topic);
      }
    } else {
      const int next = gRetainedBytes - prev + payload.size();
      if (next > 4 * 1024 * 1024 ||
          (!gRetained.contains(topic) && gRetained.size() >= kMaxRetained))
        return QStringLiteral("模拟器保留消息容量已满");
      if (payload.size() > kMaxPayload) return QStringLiteral("模拟器消息超出范围");
      gRetainedBytes = next;
      gRetained.insert(topic, Retained{payload, qos});
    }
  }
  gLive.push_back(LiveMsg{topic, payload, qos, retain, false});
  if (gLive.size() > 256) gLive.removeFirst();
  ++gLiveSeq;
  gLiveCv.wakeAll();
  return QString();
}

bool storeFindRetained(const QString& filter, LiveMsg* out) {
  QMutexLocker lock(&gStoreMutex);
  for (auto it = gRetained.begin(); it != gRetained.end(); ++it) {
    if (topicMatch(filter, it.key())) {
      out->topic = it.key();
      out->payload = it.value().payload;
      out->qos = it.value().qos;
      out->retain = true;
      out->dup = false;
      return true;
    }
  }
  return false;
}

/* ---------------- params ---------------- */

struct Prepared {
  QString connection;
  QString host = QStringLiteral("127.0.0.1");
  int port = 1883;
  QString security;
  QString topic;
  QString encoding;
  int qos = 1;
  int timeoutMs = 5000;
  QString clientId;
  bool retain = false;
  bool acceptRetained = true;
  bool receive = false;
  QByteArray payload;
  QVariant value;
};

bool prepareCommon(const QVariantMap& p, bool receive, Prepared* c, QString* error) {
  c->receive = receive;
  c->connection = p.value(QStringLiteral("connection"), QStringLiteral("simulator")).toString();
  if (c->connection != QLatin1String("simulator") &&
      c->connection != QLatin1String("broker")) {
    *error = QStringLiteral("MQTT 连接方式无效");
    return false;
  }
  c->encoding = p.value(QStringLiteral("encoding"),
                        receive ? QStringLiteral("text") : QStringLiteral("structured"))
                    .toString();
  if (c->encoding != QLatin1String("text") && c->encoding != QLatin1String("structured") &&
      c->encoding != QLatin1String("bytes")) {
    *error = QStringLiteral("MQTT 消息格式无效");
    return false;
  }
  c->security = p.value(QStringLiteral("security"), QStringLiteral("plain")).toString();
  if (c->security != QLatin1String("plain") && c->security != QLatin1String("tls")) {
    *error = QStringLiteral("MQTT 安全模式无效");
    return false;
  }
  if (p.contains(QStringLiteral("password"))) {
    *error = QStringLiteral("密码不能保存在工程参数，请配置密码环境变量名");
    return false;
  }
  if (c->security == QLatin1String("tls")) {
    *error = QStringLiteral("当前内置软代理仅支持 security=plain 的明文会话");
    return false;
  }
  c->topic = p.value(QStringLiteral("topic"), QStringLiteral("sieans/inspection")).toString();
  if (!validTopic(c->topic, receive, error)) return false;
  c->qos = p.value(QStringLiteral("qos"), 1).toInt();
  if (c->qos < 0 || c->qos > 2) {
    *error = QStringLiteral("QoS 必须为 0–2 的整数");
    return false;
  }
  c->timeoutMs = p.value(QStringLiteral("timeoutMs"), 5000).toInt();
  if (c->timeoutMs < 100 || c->timeoutMs > 60000) {
    *error = QStringLiteral("MQTT 超时必须为 100–60000 的整数");
    return false;
  }
  c->clientId = p.value(QStringLiteral("clientId")).toString();
  if (c->clientId.size() > 128) {
    *error = QStringLiteral("客户端标识无效");
    return false;
  }
  if (c->clientId.isEmpty())
    c->clientId = QStringLiteral("sv-") + QUuid::createUuid().toString(QUuid::Id128).left(20);
  c->retain = p.value(QStringLiteral("retain"), false).toBool();
  c->acceptRetained = p.value(QStringLiteral("acceptRetained"), true).toBool();
  c->host = p.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString().trimmed();
  if (c->host.isEmpty() || c->host.size() > 253) {
    *error = QStringLiteral("服务器主机名无效");
    return false;
  }
  for (const QChar ch : c->host) {
    if (ch.isSpace() || ch == QLatin1Char('/') || ch == QLatin1Char('?') ||
        ch == QLatin1Char('#') || ch == QLatin1Char('@')) {
      *error = QStringLiteral("服务器主机名不能包含 URL 或空白");
      return false;
    }
  }
  if (c->host.isEmpty()) {
    *error = QStringLiteral("服务器主机名无效");
    return false;
  }
  c->port = p.value(QStringLiteral("port"), 1883).toInt();
  if (c->port < 1 || c->port > 65535) {
    *error = QStringLiteral("MQTT 端口必须为 1–65535 的整数");
    return false;
  }
  if (!receive) {
    QVariant val = p.contains(QStringLiteral("value")) ? p.value(QStringLiteral("value"))
                                                       : QVariant(QString());
    if (!encodePayload(val, c->encoding, &c->payload, error)) return false;
    c->value = val;
  }
  if (c->connection == QLatin1String("broker") && mqttSoftBroker().running() &&
      (c->host == QLatin1String("127.0.0.1") || c->host == QLatin1String("localhost")) &&
      (c->port == 1883 || c->port == 0)) {
    const quint16 sp = mqttSoftBroker().port();
    if (sp != 0) c->port = int(sp);
  }
  return true;
}


/* ---------------- MQTT 3.1.1 client ---------------- */

QByteArray buildConnect(const Prepared& c) {
  QByteArray var;
  appendMqttStr(var, QStringLiteral("MQTT"));
  var.append(char(4));   // protocol level 3.1.1
  var.append(char(0x02));  // clean session
  appendU16(var, 15);    // keepalive
  appendMqttStr(var, c.clientId);
  QByteArray pkt;
  pkt.append(char(0x10));
  pkt.append(encLen(var.size()));
  pkt.append(var);
  return pkt;
}

QByteArray buildPublish(const QString& topic, const QByteArray& payload, int qos,
                        bool retain, quint16 id, bool dup = false) {
  QByteArray var;
  appendMqttStr(var, topic);
  if (qos > 0) appendU16(var, id);
  var.append(payload);
  quint8 flags = 0x30 | (quint8(qos) << 1) | (retain ? 0x01 : 0) | (dup ? 0x08 : 0);
  return mqttPacket(flags, var);
}

QByteArray buildSubscribe(const QString& topic, int qos, quint16 id) {
  QByteArray var;
  appendU16(var, id);
  appendMqttStr(var, topic);
  var.append(char(qos));
  return mqttPacket(0x82, var);
}

QByteArray buildPubAck(quint16 id) {
  QByteArray var;
  appendU16(var, id);
  return mqttPacket(0x40, var);
}
QByteArray buildPubRec(quint16 id) {
  QByteArray var;
  appendU16(var, id);
  return mqttPacket(0x50, var);
}
QByteArray buildPubRel(quint16 id) {
  QByteArray var;
  appendU16(var, id);
  return mqttPacket(0x62, var);
}
QByteArray buildPubComp(quint16 id) {
  QByteArray var;
  appendU16(var, id);
  return mqttPacket(0x70, var);
}

int tcpConnect(const Prepared& c, QString* error) {
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    *error = QStringLiteral("无法创建 MQTT 套接字");
    return -1;
  }
  setTimeo(fd, c.timeoutMs);
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(quint16(c.port));
  if (::inet_pton(AF_INET, c.host.toUtf8().constData(), &addr.sin_addr) != 1) {
    *error = QStringLiteral("无法解析 MQTT 主机地址");
    ::close(fd);
    return -1;
  }
  if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
    *error = QStringLiteral("无法连接 MQTT 服务器，请检查主机和端口");
    ::close(fd);
    return -1;
  }
  return fd;
}

bool handshake(int fd, const Prepared& c, QString* error) {
  if (!sendAll(fd, buildConnect(c), error)) return false;
  MqttPkt pkt;
  if (!recvPkt(fd, &pkt, error)) return false;
  if (pkt.type != 2 || pkt.body.size() < 2) {
    *error = QStringLiteral("MQTT 连接未被确认");
    return false;
  }
  const quint8 rc = quint8(pkt.body[1]);
  if (rc != 0) {
    *error = QStringLiteral("MQTT 服务器拒绝连接（代码 %1）").arg(rc);
    return false;
  }
  return true;
}

bool waitType(int fd, quint8 typ, quint16 expectId, QString* error,
              MqttPkt* out = nullptr) {
  MqttPkt pkt;
  if (!recvPkt(fd, &pkt, error)) return false;
  if (pkt.type == 13) {  // PINGRESP, ignore and wait again
    return waitType(fd, typ, expectId, error, out);
  }
  if (pkt.type != typ) {
    *error = QStringLiteral("MQTT 功能码应答不匹配");
    return false;
  }
  if (expectId && pkt.body.size() >= 2) {
    const quint16 id = qFromBigEndian<quint16>(pkt.body.constData());
    if (id != expectId) {
      *error = QStringLiteral("MQTT 报文标识不匹配");
      return false;
    }
  }
  if (out) *out = pkt;
  return true;
}

bool publishBroker(int fd, const Prepared& c, quint16* nextId, QString* error) {
  const quint16 id = (c.qos > 0) ? (*nextId)++ : 0;
  if (!sendAll(fd, buildPublish(c.topic, c.payload, c.qos, c.retain, id), error))
    return false;
  if (c.qos == 0) return true;
  if (c.qos == 1) return waitType(fd, 4, id, error);
  // QoS 2
  if (!waitType(fd, 5, id, error)) return false;
  if (!sendAll(fd, buildPubRel(id), error)) return false;
  return waitType(fd, 7, id, error);
}

bool parsePublish(const MqttPkt& pkt, LiveMsg* msg, QString* error) {
  if (pkt.type != 3) {
    *error = QStringLiteral("MQTT 功能码应答不匹配");
    return false;
  }
  Cursor cur(pkt.body);
  msg->topic = cur.str();
  msg->qos = (pkt.flags >> 1) & 0x03;
  msg->retain = (pkt.flags & 0x01) != 0;
  msg->dup = (pkt.flags & 0x08) != 0;
  quint16 id = 0;
  if (msg->qos > 0) id = cur.u16();
  if (!cur.ok) {
    *error = QStringLiteral("MQTT 发布报文不完整");
    return false;
  }
  msg->payload = cur.raw(cur.remain());
  (void)id;
  return true;
}

bool ackPublish(int fd, const MqttPkt& pkt, const LiveMsg& msg, QString* error) {
  if (msg.qos == 0) return true;
  Cursor cur(pkt.body);
  (void)cur.str();
  const quint16 id = cur.u16();
  if (msg.qos == 1) return sendAll(fd, buildPubAck(id), error);
  if (!sendAll(fd, buildPubRec(id), error)) return false;
  if (!waitType(fd, 6, id, error)) return false;
  return sendAll(fd, buildPubComp(id), error);
}

bool receiveBroker(int fd, const Prepared& c, quint16* nextId, LiveMsg* msg,
                   QString* error) {
  const quint16 id = (*nextId)++;
  if (!sendAll(fd, buildSubscribe(c.topic, c.qos, id), error)) return false;
  MqttPkt suback;
  if (!waitType(fd, 9, id, error, &suback)) return false;
  if (suback.body.size() < 3 || quint8(suback.body[2]) == 0x80) {
    *error = QStringLiteral("MQTT 服务器拒绝订阅");
    return false;
  }
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::milliseconds(c.timeoutMs);
  while (std::chrono::steady_clock::now() < deadline) {
    // shrink remaining timeout
    const auto left = std::chrono::duration_cast<std::chrono::milliseconds>(
                          deadline - std::chrono::steady_clock::now())
                          .count();
    if (left <= 0) break;
    setTimeo(fd, int(std::max<qint64>(left, 50)));
    MqttPkt pkt;
    QString pe;
    if (!recvPkt(fd, &pkt, &pe)) {
      if (pe.contains(QStringLiteral("超时"))) break;
      *error = pe;
      return false;
    }
    if (pkt.type == 13) continue;
    if (pkt.type == 3) {
      if (!parsePublish(pkt, msg, error)) return false;
      if (!c.acceptRetained && msg->retain) continue;
      if (!ackPublish(fd, pkt, *msg, error)) return false;
      return true;
    }
  }
  *error = QStringLiteral("MQTT 操作超时");
  return false;
}

void disconnectMqtt(int fd) {
  QString e;
  const QByteArray d = mqttPacket(0xE0, QByteArray());
  (void)sendAll(fd, d, &e);
  ::close(fd);
}

/* ---------------- run ---------------- */

MqttResult finishFail(MqttResult r, const QString& e,
                      const std::chrono::steady_clock::time_point& started, bool sent) {
  r.ok = false;
  r.error = e;
  if (sent)
    r.error += QStringLiteral("；消息可能已被服务器接收，不能回滚，未自动重试");
  r.note = r.error;
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  return r;
}

MqttResult finishOk(MqttResult r, const Prepared& c,
                    const std::chrono::steady_clock::time_point& started) {
  r.ok = true;
  r.protocol = QStringLiteral("MQTT 3.1.1");
  r.topic = c.topic;
  r.encoding = c.encoding;
  r.qos = c.qos;
  r.clientId = c.clientId;
  r.simulated = c.connection == QLatin1String("simulator");
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  if (r.note.isEmpty())
    r.note = QStringLiteral("mqtt %1 %2").arg(r.action, r.topic);
  return r;
}

void forwardToSubs(const QString& topic, const QByteArray& payload, int qos, bool retain);

MqttResult runOp(const QVariantMap& params, bool receive) {
  const auto started = std::chrono::steady_clock::now();
  MqttResult r;
  r.action = receive ? QStringLiteral("receive") : QStringLiteral("publish");
  Prepared c;
  QString err;
  if (!prepareCommon(params, receive, &c, &err)) return finishFail(r, err, started, false);
  r.topic = c.topic;
  r.encoding = c.encoding;
  r.qos = c.qos;
  r.clientId = c.clientId;
  r.simulated = c.connection == QLatin1String("simulator");

  if (c.connection == QLatin1String("simulator")) {
    if (!receive) {
      const QString se = storePublish(c.topic, c.payload, c.qos, c.retain);
      if (!se.isEmpty()) return finishFail(r, se, started, true);
      forwardToSubs(c.topic, c.payload, c.qos, c.retain);
      r.acknowledged = c.qos > 0;
      r.retained = c.retain;
      r.byteLength = c.payload.size();
      r.delivery = c.qos > 0 ? QStringLiteral("broker_acknowledged")
                             : QStringLiteral("sent");
      if (!decodePayload(c.payload, c.encoding, &r.value, &err))
        r.value = c.value;
      r.note = QStringLiteral("设备已应答，不代表下游已执行；已发布消息不能随流程回滚。");
      return finishOk(r, c, started);
    }
    // receive: retained first, else wait for a live message
    LiveMsg msg;
    if (c.acceptRetained && storeFindRetained(c.topic, &msg)) {
      if (!decodePayload(msg.payload, c.encoding, &r.value, &err))
        return finishFail(r, err, started, false);
      r.topic = msg.topic;
      r.retained = true;
      r.byteLength = msg.payload.size();
      r.qos = msg.qos;
      r.delivery = QStringLiteral("received");
      return finishOk(r, c, started);
    }
    const auto deadline =
        std::chrono::steady_clock::now() + std::chrono::milliseconds(c.timeoutMs);
    quint64 seen = 0;
    {
      QMutexLocker lock(&gStoreMutex);
      seen = gLiveSeq;
    }
    while (std::chrono::steady_clock::now() < deadline) {
      QMutexLocker lock(&gStoreMutex);
      for (int i = 0; i < gLive.size(); ++i) {
        const LiveMsg& m = gLive[i];
        if (!topicMatch(c.topic, m.topic)) continue;
        if (!c.acceptRetained && m.retain) continue;
        // only messages published after we started waiting, unless we missed
        // them in the buffer — take the latest matching after seen by scanning
        // the whole buffer; first match from the end is fine if we check seq.
        (void)seen;
      }
      // Take newest matching live message whose arrival is "now"; wait for CV
      // if none yet. We record start seq and accept messages after it.
      for (int i = gLive.size() - 1; i >= 0; --i) {
        // no per-msg seq; use wait + re-scan for any new
      }
      const auto left = std::chrono::duration_cast<std::chrono::milliseconds>(
                            deadline - std::chrono::steady_clock::now())
                            .count();
      if (left <= 0) break;
      const quint64 before = gLiveSeq;
      if (gLiveSeq > seen) {
        for (const LiveMsg& m : gLive) {
          if (!topicMatch(c.topic, m.topic)) continue;
          if (!c.acceptRetained && m.retain) continue;
          msg = m;
          if (!decodePayload(msg.payload, c.encoding, &r.value, &err))
            return finishFail(r, err, started, false);
          r.topic = msg.topic;
          r.retained = msg.retain;
          r.duplicate = msg.dup;
          r.byteLength = msg.payload.size();
          r.qos = msg.qos;
          r.delivery = QStringLiteral("received");
          return finishOk(r, c, started);
        }
        seen = gLiveSeq;
      }
      gLiveCv.wait(&gStoreMutex, int(std::min<qint64>(left, 200)));
      (void)before;
    }
    return finishFail(r, QStringLiteral("MQTT 操作超时"), started, false);
  }

  const int fd = tcpConnect(c, &err);
  if (fd < 0) return finishFail(r, err, started, false);
  if (!handshake(fd, c, &err)) {
    ::close(fd);
    return finishFail(r, err, started, false);
  }
  quint16 nextId = 1;
  if (!receive) {
    if (!publishBroker(fd, c, &nextId, &err)) {
      disconnectMqtt(fd);
      return finishFail(r, err, started, true);
    }
    disconnectMqtt(fd);
    r.acknowledged = c.qos > 0;
    r.retained = c.retain;
    r.byteLength = c.payload.size();
    r.delivery = c.qos > 0 ? QStringLiteral("broker_acknowledged") : QStringLiteral("sent");
    if (!decodePayload(c.payload, c.encoding, &r.value, &err)) r.value = c.value;
    r.note = QStringLiteral("设备已应答，不代表下游已执行；已发布消息不能随流程回滚。");
    return finishOk(r, c, started);
  }
  LiveMsg msg;
  if (!receiveBroker(fd, c, &nextId, &msg, &err)) {
    disconnectMqtt(fd);
    return finishFail(r, err, started, false);
  }
  disconnectMqtt(fd);
  if (!decodePayload(msg.payload, c.encoding, &r.value, &err))
    return finishFail(r, err, started, false);
  r.topic = msg.topic;
  r.retained = msg.retain;
  r.duplicate = msg.dup;
  r.byteLength = msg.payload.size();
  r.qos = msg.qos;
  r.delivery = QStringLiteral("received");
  return finishOk(r, c, started);
}

/* ---------------- soft broker ---------------- */

bool writePkt(SubClient* sub, const QByteArray& buf) {
  QMutexLocker lock(&sub->writeMu);
  QString e;
  return sendAll(sub->fd, buf, &e);
}

void forwardToSubs(const QString& topic, const QByteArray& payload, int qos, bool retain) {
  QMutexLocker lock(&gSubsMutex);
  for (SubClient* sub : gSubs) {
    if (!sub->alive) continue;
    int useQos = -1;
    for (const auto& f : sub->filters) {
      if (topicMatch(f.first, topic))
        useQos = std::max(useQos, std::min({qos, f.second, 1}));
    }
    if (useQos < 0) continue;
    // packet id 1 is fine for fire-and-forget QoS1 from broker in tests
    const quint16 id = useQos > 0 ? 1 : 0;
    (void)writePkt(sub, buildPublish(topic, payload, useQos, retain, id));
  }
}

QByteArray connack(quint8 rc) {
  QByteArray b;
  b.append(char(0x20));
  b.append(char(2));
  b.append(char(0));
  b.append(char(rc));
  return b;
}

void serveClient(int cfd) {
  setTimeo(cfd, 15000);
  QString err;
  MqttPkt first;
  if (!recvPkt(cfd, &first, &err) || first.type != 1) {
    ::close(cfd);
    return;
  }
  Cursor cur(first.body);
  const QString proto = cur.str();
  const quint8 level = cur.u8();
  (void)cur.u8();
  (void)cur.u16();
  const QString clientId = cur.str();
  (void)clientId;
  if (!cur.ok || proto != QLatin1String("MQTT") || level != 4) {
    QString e;
    (void)sendAll(cfd, connack(1), &e);
    ::close(cfd);
    return;
  }
  {
    QString e;
    if (!sendAll(cfd, connack(0), &e)) {
      ::close(cfd);
      return;
    }
  }
  auto* sub = new SubClient();
  sub->fd = cfd;
  {
    QMutexLocker lock(&gSubsMutex);
    gSubs.push_back(sub);
  }
  auto last = std::chrono::steady_clock::now();
  while (gServerRun && sub->alive) {
    pollfd pfd{};
    pfd.fd = cfd;
    pfd.events = POLLIN;
    const int rc = ::poll(&pfd, 1, 200);
    if (rc == 0) {
      if (std::chrono::steady_clock::now() - last > std::chrono::seconds(60)) break;
      continue;
    }
    if (rc < 0) {
      if (errno == EINTR) continue;
      break;
    }
    MqttPkt pkt;
    if (!recvPkt(cfd, &pkt, &err)) break;
    last = std::chrono::steady_clock::now();
    QByteArray reply;
    if (pkt.type == 14) {  // DISCONNECT
      break;
    } else if (pkt.type == 12) {  // PINGREQ
      reply = mqttPacket(0xD0, QByteArray());
    } else if (pkt.type == 8) {  // SUBSCRIBE
      Cursor s(pkt.body);
      const quint16 id = s.u16();
      QByteArray codes;
      QVector<QPair<QString, int>> added;
      while (s.remain() >= 3 && s.ok) {
        const QString filter = s.str();
        const int q = s.u8() & 0x03;
        QString ve;
        if (!validTopic(filter, true, &ve))
          codes.append(char(0x80));
        else {
          const int gq = std::min(q, 2);
          codes.append(char(gq));
          added.push_back({filter, gq});
        }
      }
      {
        QMutexLocker lock(&sub->writeMu);
        sub->filters.append(added);
      }
      QByteArray body;
      appendU16(body, id);
      body.append(codes);
      reply = mqttPacket(0x90, body);
      // send SUBACK first, then retained
      {
        QString e;
        if (!writePkt(sub, reply)) break;
        reply.clear();
      }
      for (const auto& f : added) {
        QMutexLocker slock(&gStoreMutex);
        for (auto it = gRetained.begin(); it != gRetained.end(); ++it) {
          if (!topicMatch(f.first, it.key())) continue;
          const int useQos = std::min({f.second, it.value().qos, 1});
          const quint16 pid = useQos > 0 ? 1 : 0;
          slock.unlock();
          if (!writePkt(sub, buildPublish(it.key(), it.value().payload, useQos, true, pid)))
            goto done;
          slock.relock();
        }
      }
    } else if (pkt.type == 3) {  // PUBLISH
      LiveMsg msg;
      if (!parsePublish(pkt, &msg, &err)) break;
      Cursor pc(pkt.body);
      (void)pc.str();
      quint16 id = 0;
      if (msg.qos > 0) id = pc.u16();
      const QString se = storePublish(msg.topic, msg.payload, msg.qos, msg.retain);
      if (se.isEmpty())
        forwardToSubs(msg.topic, msg.payload, msg.qos, msg.retain);
      if (msg.qos == 1) {
        QString e;
        if (!writePkt(sub, buildPubAck(id))) break;
      } else if (msg.qos == 2) {
        if (!writePkt(sub, buildPubRec(id))) break;
      }
    } else if (pkt.type == 6) {  // PUBREL
      Cursor s(pkt.body);
      const quint16 id = s.u16();
      if (!writePkt(sub, buildPubComp(id))) break;
    } else if (pkt.type == 4 || pkt.type == 5 || pkt.type == 7 || pkt.type == 11) {
      // acks from client; ignore
    } else if (pkt.type == 10) {  // UNSUBSCRIBE
      Cursor s(pkt.body);
      const quint16 id = s.u16();
      QByteArray body;
      appendU16(body, id);
      if (!writePkt(sub, mqttPacket(0xB0, body))) break;
    }
    if (!reply.isEmpty() && !writePkt(sub, reply)) break;
  }
done:
  sub->alive = false;
  {
    QMutexLocker lock(&gSubsMutex);
    gSubs.removeAll(sub);
  }
  ::close(cfd);
  delete sub;
}

void serverAcceptLoop() {
  while (gServerRun && gListenFd >= 0) {
    pollfd pfd{};
    pfd.fd = gListenFd;
    pfd.events = POLLIN;
    const int rc = ::poll(&pfd, 1, 200);
    if (rc <= 0) continue;
    const int cfd = ::accept(gListenFd, nullptr, nullptr);
    if (cfd < 0) continue;
    int flags = fcntl(cfd, F_GETFL, 0);
    if (flags >= 0) fcntl(cfd, F_SETFL, flags & ~O_NONBLOCK);
    std::thread([cfd]() { serveClient(cfd); }).detach();
  }
}

}  // namespace

MqttResult runMqttPublish(const QVariantMap& params) { return runOp(params, false); }
MqttResult runMqttReceive(const QVariantMap& params) { return runOp(params, true); }

MqttSoftBroker& mqttSoftBroker() {
  QMutexLocker lock(&gServerMutex);
  if (!gServer) gServer = new MqttSoftBroker();
  return *gServer;
}

bool MqttSoftBroker::start(quint16 port, QString* error) {
  if (gServerRun && gListenFd >= 0 && (port == 0 || port == gListenPort)) return true;
  if (gServerRun) stop();
  ensureStore();
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    if (error) *error = QStringLiteral("无法创建 MQTT 监听套接字");
    return false;
  }
  int yes = 1;
  setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
  if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
    if (error)
      *error = QStringLiteral("无法绑定 MQTT 端口 %1: %2")
                   .arg(port)
                   .arg(QString::fromLocal8Bit(strerror(errno)));
    ::close(fd);
    return false;
  }
  if (::listen(fd, 8) != 0) {
    if (error) *error = QStringLiteral("MQTT 监听失败");
    ::close(fd);
    return false;
  }
  sockaddr_in got{};
  socklen_t gl = sizeof(got);
  getsockname(fd, reinterpret_cast<sockaddr*>(&got), &gl);
  gListenPort = ntohs(got.sin_port);
  gListenFd = fd;
  gServerRun = true;
  std::thread(serverAcceptLoop).detach();
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  return true;
}

void MqttSoftBroker::stop() {
  gServerRun = false;
  if (gListenFd >= 0) {
    ::close(gListenFd);
    gListenFd = -1;
  }
  gListenPort = 0;
}

bool MqttSoftBroker::running() const { return gServerRun && gListenFd >= 0; }
quint16 MqttSoftBroker::port() const { return gListenPort; }
QString MqttSoftBroker::endpoint() const {
  return QStringLiteral("127.0.0.1:%1").arg(gListenPort);
}

QStringList mqttSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail) {
    if (!ok) fails << QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail);
  };
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("topic"), QStringLiteral("sieans/inspection"));
    w.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    w.insert(QStringLiteral("value"), QStringLiteral("4242"));
    w.insert(QStringLiteral("qos"), 1);
    w.insert(QStringLiteral("retain"), true);
    const MqttResult wr = runMqttPublish(w);
    check("sim-publish", wr.ok && wr.acknowledged && wr.value.toString() == QLatin1String("4242"),
          wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("topic"), QStringLiteral("sieans/inspection"));
    r.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    r.insert(QStringLiteral("qos"), 1);
    r.insert(QStringLiteral("acceptRetained"), true);
    r.insert(QStringLiteral("timeoutMs"), 2000);
    const MqttResult rr = runMqttReceive(r);
    check("sim-receive", rr.ok && rr.value.toString() == QLatin1String("4242") && rr.retained,
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("topic"), QStringLiteral("sieans/bad/#"));
    w.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    w.insert(QStringLiteral("value"), QStringLiteral("x"));
    const MqttResult wr = runMqttPublish(w);
    check("sim-wildcard-rejected", !wr.ok && wr.error.contains(QStringLiteral("通配符")),
          wr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("topic"), QStringLiteral("sieans/struct"));
    w.insert(QStringLiteral("encoding"), QStringLiteral("structured"));
    w.insert(QStringLiteral("value"), 4242);
    w.insert(QStringLiteral("retain"), true);
    const MqttResult wr = runMqttPublish(w);
    check("sim-structured-pub", wr.ok, wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("topic"), QStringLiteral("sieans/struct"));
    r.insert(QStringLiteral("encoding"), QStringLiteral("structured"));
    r.insert(QStringLiteral("acceptRetained"), true);
    const MqttResult rr = runMqttReceive(r);
    check("sim-structured-recv", rr.ok && rr.value.toInt() == 4242,
          rr.ok ? rr.value.toString() : rr.error);
  }

  QString serr;
  bool started = false;
  for (int p = 1883; p <= 1887 && !started; ++p) {
    QString e;
    if (mqttSoftBroker().start(quint16(p), &e)) started = true;
    else serr = e;
  }
  check("tcp-broker", started, serr);
  if (started) {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("broker"));
    w.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    w.insert(QStringLiteral("port"), int(mqttSoftBroker().port()));
    w.insert(QStringLiteral("topic"), QStringLiteral("sieans/inspection"));
    w.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    w.insert(QStringLiteral("value"), QStringLiteral("9001"));
    w.insert(QStringLiteral("qos"), 1);
    w.insert(QStringLiteral("retain"), true);
    w.insert(QStringLiteral("timeoutMs"), 3000);
    const MqttResult wr = runMqttPublish(w);
    check("tcp-publish", wr.ok && wr.acknowledged, wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("broker"));
    r.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    r.insert(QStringLiteral("port"), int(mqttSoftBroker().port()));
    r.insert(QStringLiteral("topic"), QStringLiteral("sieans/inspection"));
    r.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    r.insert(QStringLiteral("qos"), 1);
    r.insert(QStringLiteral("acceptRetained"), true);
    r.insert(QStringLiteral("timeoutMs"), 3000);
    const MqttResult rr = runMqttReceive(r);
    check("tcp-receive", rr.ok && rr.value.toString() == QLatin1String("9001"),
          rr.ok ? rr.value.toString() : rr.error);
    // QoS 2
    w.insert(QStringLiteral("topic"), QStringLiteral("sieans/qos2"));
    w.insert(QStringLiteral("value"), QStringLiteral("777"));
    w.insert(QStringLiteral("qos"), 2);
    const MqttResult w2 = runMqttPublish(w);
    check("tcp-qos2-pub", w2.ok && w2.acknowledged, w2.ok ? w2.value.toString() : w2.error);
    r.insert(QStringLiteral("topic"), QStringLiteral("sieans/qos2"));
    r.insert(QStringLiteral("qos"), 2);
    const MqttResult r2 = runMqttReceive(r);
    check("tcp-qos2-recv", r2.ok && r2.value.toString() == QLatin1String("777"),
          r2.ok ? r2.value.toString() : r2.error);
  }
  return fails;
}

}  // namespace sieans_qt
