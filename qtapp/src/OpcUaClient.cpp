#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "OpcUaClient.hpp"

#include <QDateTime>
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QUrl>
#include <QUuid>
#include <QtEndian>

#include <algorithm>
#include <chrono>
#include <cmath>
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

constexpr int kMaxItems = 1000;
constexpr qint64 kUnixToUa = 116444736000000000LL;
const char* kPolicyNone = "http://opcfoundation.org/UA/SecurityPolicy#None";
const char* kTransport =
    "http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary";
const char* kNsUri = "urn:sieans:simulator";
const char* kNs0 = "http://opcfoundation.org/UA/";
const char* kNs1 = "urn:sieans:vision:server";

// Encoding ids (Default Binary)
constexpr quint32 kOpenChReq = 446, kOpenChRes = 449;
constexpr quint32 kCreateSessReq = 461, kCreateSessRes = 464;
constexpr quint32 kActivateReq = 467, kActivateRes = 470;
constexpr quint32 kCloseSessReq = 473, kCloseSessRes = 476;
constexpr quint32 kCloseChReq = 452;
constexpr quint32 kReadReq = 631, kReadRes = 634;
constexpr quint32 kWriteReq = 673, kWriteRes = 676;
constexpr quint32 kBrowseReq = 527, kBrowseRes = 530;
constexpr quint32 kCreateSubReq = 787, kCreateSubRes = 790;
constexpr quint32 kCreateMonReq = 751, kCreateMonRes = 754;
constexpr quint32 kPublishReq = 826, kPublishRes = 829;
constexpr quint32 kDeleteSubReq = 847, kDeleteSubRes = 850;
constexpr quint32 kAnonymousTok = 321;
constexpr quint32 kDataChangeNotif = 811;
constexpr quint32 kServiceFault = 397;

constexpr quint32 kBadNodeIdUnknown = 0x80340000u;
constexpr quint32 kBadUserAccessDenied = 0x801F0000u;
constexpr quint32 kBadTypeMismatch = 0x80740000u;
constexpr quint32 kBadAttributeIdInvalid = 0x80350000u;
constexpr quint32 kBadNotWritable = 0x803B0000u;
constexpr quint32 kBadSubId = 0x80280000u;
constexpr quint32 kBadTimeout = 0x800A0000u;
constexpr quint32 kBadDecoding = 0x80070000u;
constexpr quint32 kBadSessionId = 0x80250000u;
constexpr quint32 kBadSecureChannel = 0x80220000u;

enum class NodeKind { Numeric, String, Guid, Bytes };

struct UaNodeId {
  NodeKind kind = NodeKind::Numeric;
  quint16 ns = 0;
  quint32 numeric = 0;
  QString str;
  QUuid guid;
  QByteArray bytes;

  QString toString() const {
    QString head = (ns == 0 && kind == NodeKind::Numeric)
                       ? QString()
                       : QStringLiteral("ns=%1;").arg(ns);
    if (kind == NodeKind::Numeric)
      return (ns == 0) ? QStringLiteral("i=%1").arg(numeric)
                       : head + QStringLiteral("i=%1").arg(numeric);
    if (kind == NodeKind::String) return head + QStringLiteral("s=%1").arg(str);
    if (kind == NodeKind::Guid)
      return head + QStringLiteral("g=%1").arg(guid.toString(QUuid::WithoutBraces));
    return head + QStringLiteral("b=%1").arg(QString::fromLatin1(bytes.toBase64()));
  }
  bool operator==(const UaNodeId& o) const {
    if (kind != o.kind || ns != o.ns) return false;
    if (kind == NodeKind::Numeric) return numeric == o.numeric;
    if (kind == NodeKind::String) return str == o.str;
    if (kind == NodeKind::Guid) return guid == o.guid;
    return bytes == o.bytes;
  }
};

struct StoreNode {
  UaNodeId id;
  QString browseName;
  QString displayName;
  quint32 nodeClass = 2;
  UaNodeId parent;
  UaNodeId typeDef;
  QString dataType;
  QVariant value;
  bool writable = false;
  quint32 status = 0;
  qint64 sourceTs = 0;
  qint64 serverTs = 0;
};

QMutex gStoreMutex;
QHash<QString, StoreNode> gNodes;
QHash<QString, QStringList> gChildren;
bool gStoreInit = false;

QMutex gServerMutex;
OpcUaSoftServer* gServer = nullptr;
int gListenFd = -1;
quint16 gListenPort = 0;
bool gServerRun = false;
quint32 gNextSession = 10;
quint32 gNextChannel = 1;

qint64 uaNow() {
  return QDateTime::currentMSecsSinceEpoch() * 10000LL + kUnixToUa;
}

QString tsIso(qint64 t) {
  if (t <= 0) return QString();
  return QDateTime::fromMSecsSinceEpoch((t - kUnixToUa) / 10000, Qt::UTC)
      .toString(Qt::ISODateWithMs);
}

int typeIdOf(const QString& name) {
  static const QHash<QString, int> m{
      {QStringLiteral("Boolean"), 1},  {QStringLiteral("SByte"), 2},
      {QStringLiteral("Byte"), 3},     {QStringLiteral("Int16"), 4},
      {QStringLiteral("UInt16"), 5},   {QStringLiteral("Int32"), 6},
      {QStringLiteral("UInt32"), 7},   {QStringLiteral("Int64"), 8},
      {QStringLiteral("UInt64"), 9},   {QStringLiteral("Float"), 10},
      {QStringLiteral("Double"), 11},  {QStringLiteral("String"), 12},
      {QStringLiteral("DateTime"), 13},{QStringLiteral("Guid"), 14},
      {QStringLiteral("ByteString"), 15}};
  return m.value(name, 0);
}

QString typeNameOf(int id) {
  static const QHash<int, QString> m{
      {1, QStringLiteral("Boolean")},  {2, QStringLiteral("SByte")},
      {3, QStringLiteral("Byte")},     {4, QStringLiteral("Int16")},
      {5, QStringLiteral("UInt16")},   {6, QStringLiteral("Int32")},
      {7, QStringLiteral("UInt32")},   {8, QStringLiteral("Int64")},
      {9, QStringLiteral("UInt64")},   {10, QStringLiteral("Float")},
      {11, QStringLiteral("Double")},  {12, QStringLiteral("String")},
      {13, QStringLiteral("DateTime")},{14, QStringLiteral("Guid")},
      {15, QStringLiteral("ByteString")}};
  return m.value(id, QStringLiteral("Null"));
}

UaNodeId nidNumeric(quint16 ns, quint32 id) {
  UaNodeId n;
  n.kind = NodeKind::Numeric;
  n.ns = ns;
  n.numeric = id;
  return n;
}
UaNodeId nidString(quint16 ns, const QString& s) {
  UaNodeId n;
  n.kind = NodeKind::String;
  n.ns = ns;
  n.str = s;
  return n;
}

bool parseNodeId(const QString& text, UaNodeId* out, QString* error) {
  const QString t = text.trimmed();
  if (t.isEmpty() || t.size() > 500) {
    *error = QStringLiteral("节点地址无效");
    return false;
  }
  quint16 ns = 0;
  QString rest = t;
  if (t.startsWith(QLatin1String("ns="))) {
    const int sc = t.indexOf(QLatin1Char(';'));
    if (sc < 0) {
      *error = QStringLiteral("节点地址格式无效，例如 ns=2;s=SIEANS.Count");
      return false;
    }
    bool ok = false;
    const int n = t.mid(3, sc - 3).toInt(&ok);
    if (!ok || n < 0 || n > 65535) {
      *error = QStringLiteral("节点地址格式无效，例如 ns=2;s=SIEANS.Count");
      return false;
    }
    ns = quint16(n);
    rest = t.mid(sc + 1);
  }
  if (rest.size() < 3 || rest[1] != QLatin1Char('=')) {
    *error = QStringLiteral("节点地址格式无效，例如 ns=2;s=SIEANS.Count");
    return false;
  }
  const QChar k = rest[0];
  const QString v = rest.mid(2);
  out->ns = ns;
  if (k == QLatin1Char('i')) {
    bool ok = false;
    const qlonglong n = v.toLongLong(&ok);
    if (!ok || n < 0 || n > 0xffffffffll) {
      *error = QStringLiteral("节点地址格式无效，例如 ns=2;s=SIEANS.Count");
      return false;
    }
    out->kind = NodeKind::Numeric;
    out->numeric = quint32(n);
    return true;
  }
  if (k == QLatin1Char('s')) {
    out->kind = NodeKind::String;
    out->str = v;
    return true;
  }
  if (k == QLatin1Char('g')) {
    const QUuid g = QUuid::fromString(v);
    if (g.isNull()) {
      *error = QStringLiteral("节点地址格式无效，例如 ns=2;s=SIEANS.Count");
      return false;
    }
    out->kind = NodeKind::Guid;
    out->guid = g;
    return true;
  }
  if (k == QLatin1Char('b')) {
    out->kind = NodeKind::Bytes;
    out->bytes = QByteArray::fromBase64(v.toLatin1());
    return true;
  }
  *error = QStringLiteral("节点地址格式无效，例如 ns=2;s=SIEANS.Count");
  return false;
}

void addStore(StoreNode n) {
  n.sourceTs = n.serverTs = uaNow();
  const QString key = n.id.toString();
  const QString pk = n.parent.toString();
  gNodes.insert(key, n);
  if (!pk.isEmpty()) {
    QStringList ch = gChildren.value(pk);
    if (!ch.contains(key)) ch.push_back(key);
    gChildren.insert(pk, ch);
  }
}

void ensureStore() {
  if (gStoreInit) return;
  gNodes.clear();
  gChildren.clear();
  StoreNode root;
  root.id = nidNumeric(0, 84);
  root.browseName = QStringLiteral("Root");
  root.displayName = root.browseName;
  root.nodeClass = 1;
  root.typeDef = nidNumeric(0, 61);
  addStore(root);
  StoreNode objects;
  objects.id = nidNumeric(0, 85);
  objects.browseName = QStringLiteral("Objects");
  objects.displayName = objects.browseName;
  objects.nodeClass = 1;
  objects.parent = nidNumeric(0, 84);
  objects.typeDef = nidNumeric(0, 61);
  addStore(objects);
  StoreNode folder;
  folder.id = nidString(2, QStringLiteral("SIEANS"));
  folder.browseName = QStringLiteral("SIEANS");
  folder.displayName = folder.browseName;
  folder.nodeClass = 1;
  folder.parent = nidNumeric(0, 85);
  folder.typeDef = nidNumeric(0, 58);
  addStore(folder);
  auto var = [&](const QString& name, const QString& dtype, const QVariant& val,
                 bool writable) {
    StoreNode n;
    n.id = nidString(2, QStringLiteral("SIEANS.") + name);
    n.browseName = name;
    n.displayName = name;
    n.nodeClass = 2;
    n.parent = folder.id;
    n.typeDef = nidNumeric(0, 63);
    n.dataType = dtype;
    n.value = val;
    n.writable = writable;
    addStore(n);
  };
  var(QStringLiteral("Count"), QStringLiteral("UInt32"), QVariant(uint(0)), true);
  var(QStringLiteral("Passed"), QStringLiteral("Boolean"), QVariant(false), true);
  var(QStringLiteral("Height"), QStringLiteral("Double"), QVariant(12.5), true);
  var(QStringLiteral("Label"), QStringLiteral("String"),
      QVariant(QStringLiteral("SIEANS")), true);
  var(QStringLiteral("Samples"), QStringLiteral("Double"),
      QVariant(QVariantList{1.0, 2.0, 3.0}), true);
  var(QStringLiteral("Serial"), QStringLiteral("String"),
      QVariant(QStringLiteral("SIM-OPCUA-001")), false);
  gStoreInit = true;
}

QString resolveNs(const QString& uri, const UaNodeId& id) {
  UaNodeId n = id;
  if (!uri.isEmpty()) {
    if (uri == QLatin1String(kNsUri))
      n.ns = 2;
    else if (uri == QLatin1String(kNs0))
      n.ns = 0;
    else if (uri == QLatin1String(kNs1))
      n.ns = 1;
  }
  return n.toString();
}

QStringList nsArray() {
  return {QString::fromUtf8(kNs0), QString::fromUtf8(kNs1), QString::fromUtf8(kNsUri)};
}

/* ---------------- binary IO ---------------- */

struct Writer {
  QByteArray b;
  void u8(quint8 v) { b.append(char(v)); }
  void u16(quint16 v) {
    char d[2];
    qToLittleEndian(v, d);
    b.append(d, 2);
  }
  void u32(quint32 v) {
    char d[4];
    qToLittleEndian(v, d);
    b.append(d, 4);
  }
  void i32(qint32 v) { u32(quint32(v)); }
  void u64(quint64 v) {
    char d[8];
    qToLittleEndian(v, d);
    b.append(d, 8);
  }
  void i64(qint64 v) { u64(quint64(v)); }
  void f32(float v) {
    quint32 u = 0;
    std::memcpy(&u, &v, 4);
    u32(u);
  }
  void f64(double v) {
    quint64 u = 0;
    std::memcpy(&u, &v, 8);
    u64(u);
  }
  void str(const QString& s, bool nll = false) {
    if (nll && s.isNull()) {
      i32(-1);
      return;
    }
    const QByteArray u = s.toUtf8();
    i32(u.size());
    b.append(u);
  }
  void bytes(const QByteArray& s, bool nll = false) {
    if (nll && s.isNull()) {
      i32(-1);
      return;
    }
    i32(s.size());
    b.append(s);
  }
  void nodeId(const UaNodeId& n) {
    if (n.kind == NodeKind::Numeric) {
      if (n.ns == 0 && n.numeric <= 255) {
        u8(0x00);
        u8(quint8(n.numeric));
        return;
      }
      if (n.ns <= 255 && n.numeric <= 65535) {
        u8(0x01);
        u8(quint8(n.ns));
        u16(quint16(n.numeric));
        return;
      }
      u8(0x02);
      u16(n.ns);
      u32(n.numeric);
      return;
    }
    if (n.kind == NodeKind::String) {
      u8(0x03);
      u16(n.ns);
      str(n.str);
      return;
    }
    if (n.kind == NodeKind::Guid) {
      u8(0x04);
      u16(n.ns);
      const QByteArray rb = n.guid.toRfc4122();
      // OPC UA Guid is mixed endian: Data1 LE, Data2 LE, Data3 LE, Data4 as-is
      QByteArray g = rb;
      if (g.size() == 16) {
        Writer w;
        const auto be32 = qFromBigEndian<quint32>(g.constData());
        const auto be16a = qFromBigEndian<quint16>(g.constData() + 4);
        const auto be16b = qFromBigEndian<quint16>(g.constData() + 6);
        w.u32(be32);
        w.u16(be16a);
        w.u16(be16b);
        w.b.append(g.mid(8, 8));
        b.append(w.b);
      }
      return;
    }
    u8(0x05);
    u16(n.ns);
    bytes(n.bytes);
  }
  void expNodeId(const UaNodeId& n) { nodeId(n); }  // local, no flags
  void locText(const QString& t) {
    u8(0x02);  // has text
    str(t);
  }
  void qname(quint16 ns, const QString& name) {
    u16(ns);
    str(name);
  }
  void diagEmpty() { u8(0); }
  void extEmpty() {
    nodeId(nidNumeric(0, 0));
    u8(0);
  }
  void extObj(quint32 typeId, const QByteArray& body) {
    nodeId(nidNumeric(0, typeId));
    u8(1);
    bytes(body);
  }
};

struct Reader {
  QByteArray d;
  int off = 0;
  bool ok = true;
  Reader() = default;
  explicit Reader(const QByteArray& b) : d(b) {}
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
    const quint16 v = qFromLittleEndian<quint16>(d.constData() + off);
    off += 2;
    return v;
  }
  quint32 u32() {
    if (!need(4)) return 0;
    const quint32 v = qFromLittleEndian<quint32>(d.constData() + off);
    off += 4;
    return v;
  }
  qint32 i32() { return qint32(u32()); }
  quint64 u64() {
    if (!need(8)) return 0;
    const quint64 v = qFromLittleEndian<quint64>(d.constData() + off);
    off += 8;
    return v;
  }
  qint64 i64() { return qint64(u64()); }
  float f32() {
    quint32 u = u32();
    float f = 0;
    std::memcpy(&f, &u, 4);
    return f;
  }
  double f64() {
    quint64 u = u64();
    double f = 0;
    std::memcpy(&f, &u, 8);
    return f;
  }
  QByteArray raw(int n) {
    if (n < 0 || !need(n)) return {};
    QByteArray s = d.mid(off, n);
    off += n;
    return s;
  }
  QByteArray bytes() {
    const qint32 n = i32();
    if (n < 0) return QByteArray();  // null
    if (n > remain()) {
      ok = false;
      return {};
    }
    return raw(n);
  }
  QString str() {
    const QByteArray u = bytes();
    if (!ok) return {};
    if (u.isNull()) return QString();
    return QString::fromUtf8(u);
  }
  UaNodeId nodeId() {
    UaNodeId n;
    const quint8 enc = u8();
    const quint8 base = enc & 0x3f;
    if (base == 0x00) {
      n.kind = NodeKind::Numeric;
      n.numeric = u8();
    } else if (base == 0x01) {
      n.kind = NodeKind::Numeric;
      n.ns = u8();
      n.numeric = u16();
    } else if (base == 0x02) {
      n.kind = NodeKind::Numeric;
      n.ns = u16();
      n.numeric = u32();
    } else if (base == 0x03) {
      n.kind = NodeKind::String;
      n.ns = u16();
      n.str = str();
    } else if (base == 0x04) {
      n.kind = NodeKind::Guid;
      n.ns = u16();
      if (!need(16)) return n;
      const quint32 d1 = u32();
      const quint16 d2 = u16();
      const quint16 d3 = u16();
      const QByteArray d4 = raw(8);
      // toRfc4122 is big-endian Data1-3
      QByteArray rfc(16, 0);
      qToBigEndian(d1, rfc.data());
      qToBigEndian(d2, rfc.data() + 4);
      qToBigEndian(d3, rfc.data() + 6);
      memcpy(rfc.data() + 8, d4.constData(), 8);
      n.guid = QUuid::fromRfc4122(rfc);
    } else if (base == 0x05) {
      n.kind = NodeKind::Bytes;
      n.ns = u16();
      n.bytes = bytes();
    } else {
      ok = false;
    }
    if (enc & 0x80) (void)str();   // namespace uri
    if (enc & 0x40) (void)u32();  // server index
    return n;
  }
  void skipDiag() {
    const quint8 m = u8();
    if (m & 0x01) (void)i32();
    if (m & 0x02) (void)str();
    if (m & 0x04) (void)i32();
    if (m & 0x08) (void)i32();
    if (m & 0x10) (void)i32();
    if (m & 0x20) skipDiag();
    if (m & 0x40) (void)str();
  }
  void skipExt() {
    (void)nodeId();
    const quint8 e = u8();
    if (e == 1 || e == 2) (void)bytes();
  }
};

QByteArray wrapMsg(const char* typ, const QByteArray& body) {
  Writer w;
  w.b.append(typ, 3);
  w.u8(quint8('F'));
  w.u32(0);
  w.b.append(body);
  const quint32 len = quint32(w.b.size());
  qToLittleEndian(len, w.b.data() + 4);
  return w.b;
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
                   ? QStringLiteral("OPC UA 操作超时")
                   : QStringLiteral("OPC UA 发送失败: %1")
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
                   ? QStringLiteral("OPC UA 操作超时")
                   : QStringLiteral("OPC UA 接收失败: %1")
                         .arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    if (n == 0) {
      *error = QStringLiteral("OPC UA 连接已关闭");
      return false;
    }
    out->append(tmp, int(n));
  }
  return true;
}

bool recvMsg(int fd, char typ[4], QByteArray* body, QString* error) {
  QByteArray hdr;
  if (!recvExact(fd, 8, &hdr, error)) return false;
  typ[0] = hdr[0];
  typ[1] = hdr[1];
  typ[2] = hdr[2];
  typ[3] = hdr[3];
  typ[3] = typ[3];
  const quint32 len = qFromLittleEndian<quint32>(hdr.constData() + 4);
  if (len < 8 || len > 1u << 20) {
    *error = QStringLiteral("OPC UA 报文长度无效");
    return false;
  }
  QByteArray rest;
  if (len > 8 && !recvExact(fd, int(len - 8), &rest, error)) return false;
  *body = rest;
  if (hdr[0] == 'E' && hdr[1] == 'R' && hdr[2] == 'R') {
    Reader r(*body);
    const quint32 code = r.u32();
    const QString reason = r.str();
    *error = QStringLiteral("OPC UA 连接或协议错误：ERR %1 %2")
                 .arg(code, 0, 16)
                 .arg(reason);
    return false;
  }
  return true;
}

/* ---------------- variant / datavalue ---------------- */

QVariant encodeDisplay(const QVariant& v, const QString& dtype) {
  if (v.metaType().id() == QMetaType::QVariantList) {
    QVariantList out;
    for (const QVariant& x : v.toList()) out.push_back(encodeDisplay(x, dtype));
    return out;
  }
  if (dtype == QLatin1String("Int64") || dtype == QLatin1String("UInt64"))
    return v.toString();
  if (dtype == QLatin1String("DateTime") && v.canConvert<QDateTime>())
    return v.toDateTime().toUTC().toString(Qt::ISODateWithMs);
  if (dtype == QLatin1String("Guid") && v.canConvert<QUuid>())
    return v.toUuid().toString(QUuid::WithoutBraces);
  if (dtype == QLatin1String("ByteString"))
    return QString::fromLatin1(v.toByteArray().toBase64());
  return v;
}

bool parseWriteValue(const QVariant& raw, const QString& dtype, QVariant* out,
                     QString* error) {
  if (raw.metaType().id() == QMetaType::QVariantList) {
    const QVariantList lst = raw.toList();
    if (lst.size() > kMaxItems) {
      *error = QStringLiteral("写入仅支持一维数组，最多 1000 项");
      return false;
    }
    QVariantList acc;
    for (const QVariant& x : lst) {
      if (x.metaType().id() == QMetaType::QVariantList) {
        *error = QStringLiteral("写入仅支持一维数组，最多 1000 项");
        return false;
      }
      QVariant one;
      if (!parseWriteValue(x, dtype, &one, error)) return false;
      acc.push_back(one);
    }
    *out = acc;
    return true;
  }
  if (dtype == QLatin1String("Boolean")) {
    if (raw.typeId() != QMetaType::Bool && raw.toString() != QLatin1String("true") &&
        raw.toString() != QLatin1String("false")) {
      *error = QStringLiteral("Boolean 必须使用开关值");
      return false;
    }
    *out = raw.toBool();
    return true;
  }
  auto inRange = [&](qint64 n, qint64 lo, qint64 hi, const char* name) {
    if (n < lo || n > hi) {
      *error = QStringLiteral("整数超出 ") + QString::fromUtf8(name) +
               QStringLiteral(" 范围");
      return false;
    }
    return true;
  };
  if (dtype == QLatin1String("SByte") || dtype == QLatin1String("Byte") ||
      dtype == QLatin1String("Int16") || dtype == QLatin1String("UInt16") ||
      dtype == QLatin1String("Int32") || dtype == QLatin1String("UInt32") ||
      dtype == QLatin1String("Int64") || dtype == QLatin1String("UInt64")) {
    bool ok = false;
    qint64 n = 0;
    if ((dtype == QLatin1String("Int64") || dtype == QLatin1String("UInt64")) &&
        raw.typeId() == QMetaType::QString) {
      n = raw.toString().toLongLong(&ok);
    } else {
      n = raw.toLongLong(&ok);
    }
    if (!ok) {
      *error = QStringLiteral("整数值无效；64 位大整数请使用十进制文本");
      return false;
    }
    if (dtype == QLatin1String("SByte") && !inRange(n, -128, 127, "SByte")) return false;
    if (dtype == QLatin1String("Byte") && !inRange(n, 0, 255, "Byte")) return false;
    if (dtype == QLatin1String("Int16") && !inRange(n, -32768, 32767, "Int16"))
      return false;
    if (dtype == QLatin1String("UInt16") && !inRange(n, 0, 65535, "UInt16")) return false;
    if (dtype == QLatin1String("Int32") && !inRange(n, -2147483648ll, 2147483647ll, "Int32"))
      return false;
    if (dtype == QLatin1String("UInt32") && !inRange(n, 0, 4294967295ll, "UInt32"))
      return false;
    *out = QVariant(n);
    if (dtype == QLatin1String("UInt32")) *out = QVariant(quint32(n));
    if (dtype == QLatin1String("UInt16") || dtype == QLatin1String("Byte"))
      *out = QVariant(uint(n));
    return true;
  }
  if (dtype == QLatin1String("Float") || dtype == QLatin1String("Double")) {
    bool ok = false;
    const double d = raw.toDouble(&ok);
    if (!ok || !std::isfinite(d)) {
      *error = QStringLiteral("浮点值必须为有限数值");
      return false;
    }
    if (dtype == QLatin1String("Float")) {
      const float f = float(d);
      if (!std::isfinite(f)) {
        *error = QStringLiteral("数值超出 Float 范围");
        return false;
      }
      *out = double(f);
    } else {
      *out = d;
    }
    return true;
  }
  if (dtype == QLatin1String("String")) {
    if (raw.typeId() != QMetaType::QString && raw.typeId() != QMetaType::QByteArray) {
      *error = QStringLiteral("String 需要文本，最多 16384 字符");
      return false;
    }
    const QString s = raw.toString();
    if (s.size() > 16384) {
      *error = QStringLiteral("String 需要文本，最多 16384 字符");
      return false;
    }
    *out = s;
    return true;
  }
  if (dtype == QLatin1String("DateTime")) {
    const QDateTime dt = QDateTime::fromString(raw.toString(), Qt::ISODateWithMs);
    if (!dt.isValid() || !dt.offsetFromUtc() && !raw.toString().contains(QLatin1Char('Z')) &&
                             !raw.toString().contains(QLatin1Char('+'))) {
      // still accept trailing Z via ISODate
    }
    QDateTime x = QDateTime::fromString(raw.toString(), Qt::ISODate);
    if (!x.isValid()) x = QDateTime::fromString(raw.toString(), Qt::ISODateWithMs);
    if (!x.isValid()) {
      *error = QStringLiteral("DateTime 需要带时区的日期时间文本");
      return false;
    }
    *out = x.toUTC();
    return true;
  }
  if (dtype == QLatin1String("Guid")) {
    const QUuid g = QUuid::fromString(raw.toString());
    if (g.isNull()) {
      *error = QStringLiteral("Guid 无效");
      return false;
    }
    *out = g;
    return true;
  }
  if (dtype == QLatin1String("ByteString")) {
    QByteArray bin = QByteArray::fromBase64(raw.toString().toLatin1());
    if (bin.size() > 16384) {
      *error = QStringLiteral("ByteString 超过 16 KB");
      return false;
    }
    *out = bin;
    return true;
  }
  *error = QStringLiteral("不支持的 OPC UA 写入类型");
  return false;
}

void writeScalar(Writer& w, const QString& dtype, const QVariant& v) {
  const int t = typeIdOf(dtype);
  switch (t) {
    case 1:
      w.u8(v.toBool() ? 1 : 0);
      break;
    case 2:
      w.u8(quint8(qint8(v.toInt())));
      break;
    case 3:
      w.u8(quint8(v.toUInt()));
      break;
    case 4:
      w.u16(quint16(qint16(v.toInt())));
      break;
    case 5:
      w.u16(quint16(v.toUInt()));
      break;
    case 6:
      w.i32(v.toInt());
      break;
    case 7:
      w.u32(v.toUInt());
      break;
    case 8:
      w.i64(v.toLongLong());
      break;
    case 9:
      w.u64(v.toULongLong());
      break;
    case 10:
      w.f32(float(v.toDouble()));
      break;
    case 11:
      w.f64(v.toDouble());
      break;
    case 12:
      w.str(v.toString());
      break;
    case 13: {
      qint64 tck = 0;
      if (v.canConvert<QDateTime>()) tck = v.toDateTime().toUTC().toMSecsSinceEpoch() * 10000 + kUnixToUa;
      else tck = v.toLongLong();
      w.i64(tck);
      break;
    }
    case 14: {
      QUuid g = v.toUuid();
      if (g.isNull()) g = QUuid::fromString(v.toString());
      const QByteArray rfc = g.toRfc4122();
      Writer gw;
      gw.u32(qFromBigEndian<quint32>(rfc.constData()));
      gw.u16(qFromBigEndian<quint16>(rfc.constData() + 4));
      gw.u16(qFromBigEndian<quint16>(rfc.constData() + 6));
      gw.b.append(rfc.mid(8, 8));
      w.b.append(gw.b);
      break;
    }
    case 15:
      w.bytes(v.toByteArray());
      break;
    default:
      break;
  }
}

QVariant readScalar(Reader& r, int typeId) {
  switch (typeId) {
    case 1:
      return QVariant(bool(r.u8()));
    case 2:
      return QVariant(int(qint8(r.u8())));
    case 3:
      return QVariant(uint(r.u8()));
    case 4:
      return QVariant(int(qint16(r.u16())));
    case 5:
      return QVariant(uint(r.u16()));
    case 6:
      return QVariant(int(r.i32()));
    case 7:
      return QVariant(uint(r.u32()));
    case 8:
      return QVariant(r.i64());
    case 9:
      return QVariant(r.u64());
    case 10:
      return QVariant(double(r.f32()));
    case 11:
      return QVariant(r.f64());
    case 12:
      return QVariant(r.str());
    case 13:
      return QVariant(r.i64());
    case 14: {
      const quint32 d1 = r.u32();
      const quint16 d2 = r.u16();
      const quint16 d3 = r.u16();
      const QByteArray d4 = r.raw(8);
      QByteArray rfc(16, 0);
      qToBigEndian(d1, rfc.data());
      qToBigEndian(d2, rfc.data() + 4);
      qToBigEndian(d3, rfc.data() + 6);
      if (d4.size() == 8) memcpy(rfc.data() + 8, d4.constData(), 8);
      return QVariant(QUuid::fromRfc4122(rfc));
    }
    case 15:
      return QVariant(r.bytes());
    default:
      r.ok = false;
      return {};
  }
}

void writeVariant(Writer& w, const QString& dtype, const QVariant& v) {
  const int tid = typeIdOf(dtype);
  const bool arr = v.metaType().id() == QMetaType::QVariantList;
  w.u8(quint8(tid | (arr ? 0x80 : 0)));
  if (arr) {
    const QVariantList lst = v.toList();
    w.i32(lst.size());
    for (const QVariant& x : lst) writeScalar(w, dtype, x);
  } else {
    writeScalar(w, dtype, v);
  }
}

bool readVariant(Reader& r, QString* dtype, QVariant* v, bool* isArray) {
  const quint8 mask = r.u8();
  const int tid = mask & 0x3f;
  *dtype = typeNameOf(tid);
  *isArray = (mask & 0x80) != 0;
  if (tid == 0) {
    *v = QVariant();
    return r.ok;
  }
  if (*isArray) {
    const qint32 n = r.i32();
    if (n < 0) {
      *v = QVariant();
      return r.ok;
    }
    if (n > kMaxItems) {
      r.ok = false;
      return false;
    }
    QVariantList lst;
    lst.reserve(n);
    for (int i = 0; i < n; ++i) lst.push_back(readScalar(r, tid));
    *v = lst;
  } else {
    *v = readScalar(r, tid);
  }
  if (mask & 0x40) {
    const qint32 dims = r.i32();
    for (int i = 0; i < dims; ++i) (void)r.i32();
  }
  return r.ok;
}

struct DataVal {
  bool hasValue = false;
  QString dtype;
  QVariant value;
  bool isArray = false;
  quint32 status = 0;
  qint64 sourceTs = 0;
  qint64 serverTs = 0;
};

void writeDataValue(Writer& w, const DataVal& dv) {
  quint8 mask = 0;
  if (dv.hasValue) mask |= 0x01;
  mask |= 0x02;
  if (dv.sourceTs) mask |= 0x04;
  if (dv.serverTs) mask |= 0x08;
  w.u8(mask);
  if (dv.hasValue) writeVariant(w, dv.dtype, dv.value);
  w.u32(dv.status);
  if (dv.sourceTs) w.i64(dv.sourceTs);
  if (dv.serverTs) w.i64(dv.serverTs);
}

DataVal readDataValue(Reader& r) {
  DataVal dv;
  const quint8 mask = r.u8();
  if (mask & 0x01) {
    dv.hasValue = true;
    readVariant(r, &dv.dtype, &dv.value, &dv.isArray);
  }
  if (mask & 0x02) dv.status = r.u32();
  if (mask & 0x04) dv.sourceTs = r.i64();
  if (mask & 0x08) dv.serverTs = r.i64();
  if (mask & 0x10) (void)r.u16();
  if (mask & 0x20) (void)r.u16();
  return dv;
}

void writeRequestHeader(Writer& w, const UaNodeId& token, quint32 handle,
                        quint32 timeoutMs) {
  w.nodeId(token);
  w.i64(uaNow());
  w.u32(handle);
  w.u32(0);
  w.i32(-1);  // AuditEntryId null
  w.u32(timeoutMs);
  w.extEmpty();
}

struct RespHead {
  quint32 handle = 0;
  quint32 service = 0;
};

bool readResponseHeader(Reader& r, RespHead* h) {
  (void)r.i64();
  h->handle = r.u32();
  h->service = r.u32();
  r.skipDiag();
  const qint32 n = r.i32();
  for (int i = 0; i < n; ++i) (void)r.str();
  r.skipExt();
  return r.ok;
}

QByteArray msgBody(char /*kind*/, quint32 channel, quint32 token, quint32 seq,
                   quint32 reqId, quint32 typeId, const QByteArray& payload) {
  Writer w;
  w.u32(channel);
  w.u32(token);
  w.u32(seq);
  w.u32(reqId);
  w.nodeId(nidNumeric(0, typeId));
  w.b.append(payload);
  return w.b;
}

QByteArray opnBody(quint32 seq, quint32 reqId, const QByteArray& payload) {
  Writer w;
  w.str(QString::fromUtf8(kPolicyNone));
  w.i32(-1);  // sender cert null
  w.i32(-1);  // thumbprint null
  w.u32(seq);
  w.u32(reqId);
  w.nodeId(nidNumeric(0, kOpenChReq));
  w.b.append(payload);
  return w.b;
}


/* ---------------- store operations ---------------- */

bool storeRead(const UaNodeId& id, DataVal* dv, QString* error) {
  QMutexLocker lock(&gStoreMutex);
  ensureStore();
  const auto it = gNodes.find(id.toString());
  if (it == gNodes.end()) {
    *error = QStringLiteral("节点不存在：") + id.toString();
    dv->status = kBadNodeIdUnknown;
    return false;
  }
  const StoreNode& n = it.value();
  if (n.nodeClass != 2) {
    *error = QStringLiteral("该节点不是变量，无法读取值");
    dv->status = kBadAttributeIdInvalid;
    return false;
  }
  dv->hasValue = true;
  dv->dtype = n.dataType;
  dv->value = n.value;
  dv->isArray = n.value.metaType().id() == QMetaType::QVariantList;
  dv->status = n.status;
  dv->sourceTs = n.sourceTs;
  dv->serverTs = uaNow();
  return true;
}

quint32 storeWriteRaw(const UaNodeId& id, const QString& dtype, const QVariant& val) {
  QMutexLocker lock(&gStoreMutex);
  ensureStore();
  auto it = gNodes.find(id.toString());
  if (it == gNodes.end()) return kBadNodeIdUnknown;
  StoreNode& n = it.value();
  if (n.nodeClass != 2) return kBadAttributeIdInvalid;
  if (!n.writable) return kBadUserAccessDenied;
  if (n.dataType != dtype) return kBadTypeMismatch;
  n.value = val;
  n.sourceTs = n.serverTs = uaNow();
  n.status = 0;
  return 0;
}

bool storeBrowse(const UaNodeId& id, int limit, QVariantList* items, bool* truncated,
                 QString* error) {
  QMutexLocker lock(&gStoreMutex);
  ensureStore();
  const QString key = id.toString();
  if (!gNodes.contains(key) && key != QLatin1String("i=84") &&
      key != QLatin1String("i=85")) {
    *error = QStringLiteral("节点不存在：") + key;
    return false;
  }
  const QStringList ch = gChildren.value(key);
  *truncated = ch.size() > limit;
  const int n = std::min(int(ch.size()), limit);
  const QStringList nss = nsArray();
  for (int i = 0; i < n; ++i) {
    const StoreNode& c = gNodes[ch[i]];
    QVariantMap row;
    row.insert(QStringLiteral("nodeId"), c.id.toString());
    row.insert(QStringLiteral("displayName"), c.displayName);
    row.insert(QStringLiteral("browseName"), c.browseName);
    row.insert(QStringLiteral("nodeClass"),
               c.nodeClass == 1 ? QStringLiteral("Object") : QStringLiteral("Variable"));
    row.insert(QStringLiteral("namespaceUri"),
               c.id.ns < nss.size() ? nss[c.id.ns] : QString());
    items->push_back(row);
  }
  return true;
}

bool qualityOk(quint32 status) { return (status & 0xC0000000u) == 0; }

QString qualityName(quint32 status) {
  if (qualityOk(status)) return QStringLiteral("good");
  if (status & 0x80000000u) return QStringLiteral("bad");
  return QStringLiteral("uncertain");
}

QString statusName(quint32 status) {
  if (status == 0) return QStringLiteral("Good");
  if (status == kBadNodeIdUnknown) return QStringLiteral("BadNodeIdUnknown");
  if (status == kBadUserAccessDenied) return QStringLiteral("BadUserAccessDenied");
  if (status == kBadTypeMismatch) return QStringLiteral("BadTypeMismatch");
  if (status == kBadNotWritable) return QStringLiteral("BadNotWritable");
  if (status == kBadAttributeIdInvalid) return QStringLiteral("BadAttributeIdInvalid");
  return QStringLiteral("0x") + QString::number(status, 16);
}

bool evalCondition(const QVariant& value, const QString& dtype, const QVariantMap& p,
                   bool* matched, QString* error) {
  const QString cmp = p.value(QStringLiteral("comparison"), QStringLiteral("eq")).toString();
  if (value.metaType().id() == QMetaType::QVariantList) {
    *error = QStringLiteral("OPC UA 等待仅支持数值或开关标量");
    return false;
  }
  if (cmp == QLatin1String("is_true") || cmp == QLatin1String("is_false")) {
    if (dtype != QLatin1String("Boolean") && value.typeId() != QMetaType::Bool) {
      *error = QStringLiteral("开关条件需要 Boolean 节点");
      return false;
    }
    const bool b = value.toBool();
    *matched = (cmp == QLatin1String("is_true")) ? b : !b;
    return true;
  }
  if (dtype == QLatin1String("String") || dtype == QLatin1String("ByteString") ||
      dtype == QLatin1String("Guid") || dtype == QLatin1String("DateTime")) {
    *error = QStringLiteral("数值条件需要安全数值范围内的标量；不转换文本或大整数");
    return false;
  }
  bool ok = false;
  const double v = value.toDouble(&ok);
  if (!ok || !std::isfinite(v) || std::fabs(v) > 9007199254740991.0) {
    *error = QStringLiteral("数值条件需要安全数值范围内的标量；不转换文本或大整数");
    return false;
  }
  const double exp = p.value(QStringLiteral("expectedValue"), 0).toDouble();
  if (cmp == QLatin1String("eq"))
    *matched = v == exp;
  else if (cmp == QLatin1String("ne"))
    *matched = v != exp;
  else if (cmp == QLatin1String("gt"))
    *matched = v > exp;
  else if (cmp == QLatin1String("gte"))
    *matched = v >= exp;
  else if (cmp == QLatin1String("lt"))
    *matched = v < exp;
  else if (cmp == QLatin1String("lte"))
    *matched = v <= exp;
  else {
    *error = QStringLiteral("OPC UA 信号条件无效");
    return false;
  }
  return true;
}

/* ---------------- params ---------------- */

struct Prepared {
  QString connection;
  QString endpoint;
  QString host;
  int port = 4840;
  QString path = QStringLiteral("/sieans/");
  QString security;
  QString nodeText;
  UaNodeId node;
  QString nsUri;
  int timeoutMs = 3000;
  int browseLimit = 100;
  int waitTimeoutMs = 10000;
  int publishingMs = 100;
  bool requireGood = true;
  bool writing = false;
  QString dtype = QStringLiteral("UInt32");
  QVariant writeValue;
  QVariantMap raw;
};

bool parseEndpoint(const QString& ep, Prepared* c, QString* error) {
  if (ep.isEmpty() || ep.size() > 500 || std::any_of(ep.begin(), ep.end(), [](QChar c){ return c.isSpace(); })) {
    *error = QStringLiteral("OPC UA 端点地址无效");
    return false;
  }
  const QUrl url(ep);
  if (url.scheme() != QLatin1String("opc.tcp") || url.host().isEmpty() || url.port() <= 0 ||
      !url.userName().isEmpty() || !url.password().isEmpty() || url.hasQuery() ||
      url.hasFragment()) {
    *error = QStringLiteral("端点须为 opc.tcp://主机:端口/路径，认证请使用独立字段");
    return false;
  }
  c->endpoint = ep;
  c->host = url.host();
  c->port = url.port();
  c->path = url.path().isEmpty() ? QStringLiteral("/") : url.path();
  return true;
}

bool prepareCommon(const QVariantMap& p, const QString& op, Prepared* c, QString* error) {
  c->raw = p;
  c->connection = p.value(QStringLiteral("connection"), QStringLiteral("simulator")).toString();
  if (c->connection != QLatin1String("simulator") &&
      c->connection != QLatin1String("server")) {
    *error = QStringLiteral("OPC UA 连接方式无效");
    return false;
  }
  const QString ep = p.value(QStringLiteral("endpoint"),
                             QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/"))
                         .toString();
  if (!parseEndpoint(ep, c, error)) return false;
  c->security = p.value(QStringLiteral("security"), QStringLiteral("None")).toString();
  if (c->security != QLatin1String("None") &&
      c->security != QLatin1String("Basic256Sha256")) {
    *error = QStringLiteral("不支持的安全策略");
    return false;
  }
  if (p.contains(QStringLiteral("password"))) {
    *error = QStringLiteral("密码不能保存在工程参数，请配置密码环境变量名");
    return false;
  }
  if (c->security == QLatin1String("None") &&
      (!p.value(QStringLiteral("username")).toString().isEmpty() ||
       !p.value(QStringLiteral("passwordEnv")).toString().isEmpty())) {
    *error = QStringLiteral("用户名认证需要 Basic256Sha256 加密连接");
    return false;
  }
  if (c->security != QLatin1String("None")) {
    *error = QStringLiteral("当前内置软从站仅支持 Security=None 的匿名会话");
    return false;
  }
  c->timeoutMs = p.value(QStringLiteral("timeoutMs"), 3000).toInt();
  if (c->timeoutMs < 100 || c->timeoutMs > 10000) {
    *error = QStringLiteral("通信超时必须为 100–10000 ms");
    return false;
  }
  const QString defNode = (op == QLatin1String("browse"))
                              ? QStringLiteral("i=85")
                              : QStringLiteral("ns=2;s=SIEANS.Count");
  c->nodeText = p.value(QStringLiteral("nodeId"), defNode).toString();
  if (!parseNodeId(c->nodeText, &c->node, error)) return false;
  c->nsUri = p.value(QStringLiteral("namespaceUri")).toString();
  if (c->nsUri.size() > 500) {
    *error = QStringLiteral("命名空间 URI 无效");
    return false;
  }
  if (!c->nsUri.isEmpty()) {
    if (c->nsUri == QLatin1String(kNsUri))
      c->node.ns = 2;
    else if (c->nsUri == QLatin1String(kNs0))
      c->node.ns = 0;
    else if (c->nsUri == QLatin1String(kNs1))
      c->node.ns = 1;
    else if (c->connection == QLatin1String("simulator")) {
      *error = QStringLiteral("未知的命名空间 URI");
      return false;
    }
  }
  c->requireGood = p.value(QStringLiteral("requireGood"), true).toBool();
  c->browseLimit = p.value(QStringLiteral("browseLimit"), 100).toInt();
  if (c->browseLimit < 1 || c->browseLimit > 500) {
    *error = QStringLiteral("浏览上限必须为 1–500");
    return false;
  }
  c->waitTimeoutMs = p.value(QStringLiteral("waitTimeoutMs"), 10000).toInt();
  c->publishingMs = p.value(QStringLiteral("publishingIntervalMs"), 100).toInt();
  if (op == QLatin1String("wait")) {
    if (c->waitTimeoutMs < 100 || c->waitTimeoutMs > 600000) {
      *error = QStringLiteral("waitTimeoutMs 参数范围无效");
      return false;
    }
    if (c->publishingMs < 20 || c->publishingMs > 10000) {
      *error = QStringLiteral("publishingIntervalMs 参数范围无效");
      return false;
    }
    const QString mode =
        p.value(QStringLiteral("triggerMode"), QStringLiteral("level")).toString();
    const QString on =
        p.value(QStringLiteral("onTimeout"), QStringLiteral("error")).toString();
    const QString cmp =
        p.value(QStringLiteral("comparison"), QStringLiteral("eq")).toString();
    if (mode != QLatin1String("level") && mode != QLatin1String("rising") &&
        mode != QLatin1String("falling")) {
      *error = QStringLiteral("OPC UA 触发方式无效");
      return false;
    }
    if (on != QLatin1String("error") && on != QLatin1String("continue")) {
      *error = QStringLiteral("OPC UA 超时处理无效");
      return false;
    }
    const QStringList cmps{QStringLiteral("eq"),      QStringLiteral("ne"),
                           QStringLiteral("gt"),      QStringLiteral("gte"),
                           QStringLiteral("lt"),      QStringLiteral("lte"),
                           QStringLiteral("is_true"), QStringLiteral("is_false")};
    if (!cmps.contains(cmp)) {
      *error = QStringLiteral("OPC UA 信号条件无效");
      return false;
    }
  }
  if (op == QLatin1String("write")) {
    c->writing = true;
    c->dtype = p.value(QStringLiteral("dataType"), QStringLiteral("UInt32")).toString();
    if (typeIdOf(c->dtype) <= 0) {
      *error = QStringLiteral("不支持的 OPC UA 写入类型");
      return false;
    }
    if (!parseWriteValue(p.value(QStringLiteral("value"), 0), c->dtype, &c->writeValue,
                         error))
      return false;
  }
  if (c->connection == QLatin1String("server") && opcUaSoftServer().running() &&
      (c->host == QLatin1String("127.0.0.1") || c->host == QLatin1String("localhost")) &&
      (c->port == 4840 || c->port == 0)) {
    const quint16 sp = opcUaSoftServer().port();
    if (sp != 0) {
      c->port = int(sp);
      c->endpoint = QStringLiteral("opc.tcp://127.0.0.1:%1%2").arg(c->port).arg(c->path);
    }
  }
  return true;
}

/* ---------------- TCP client session ---------------- */

struct UaSession {
  int fd = -1;
  quint32 channel = 0;
  quint32 token = 0;
  quint32 seq = 0;
  quint32 req = 0;
  UaNodeId auth;
  int timeoutMs = 3000;
};

void closeFd(UaSession* s) {
  if (s->fd >= 0) {
    ::close(s->fd);
    s->fd = -1;
  }
}

bool sendRecv(UaSession* s, const char* typ, const QByteArray& body, quint32 expectType,
              Reader* out, QString* error) {
  if (!sendAll(s->fd, wrapMsg(typ, body), error)) return false;
  char got[4] = {};
  QByteArray raw;
  if (!recvMsg(s->fd, got, &raw, error)) return false;
  Reader r(raw);
  if (got[0] == 'O' && got[1] == 'P' && got[2] == 'N') {
    (void)r.str();
    (void)r.bytes();
    (void)r.bytes();
  } else {
    const quint32 ch = r.u32();
    const quint32 tok = r.u32();
    (void)ch;
    (void)tok;
  }
  (void)r.u32();  // seq
  (void)r.u32();  // req
  const UaNodeId tid = r.nodeId();
  if (!r.ok) {
    *error = QStringLiteral("OPC UA 连接或协议错误：应答不完整");
    return false;
  }
  if (tid.kind != NodeKind::Numeric || (tid.numeric != expectType && tid.numeric != kServiceFault)) {
    *error = QStringLiteral("OPC UA 连接或协议错误：功能码应答不匹配");
    return false;
  }
  RespHead h;
  if (!readResponseHeader(r, &h)) {
    *error = QStringLiteral("OPC UA 连接或协议错误：应答头无效");
    return false;
  }
  if (h.service != 0) {
    *error = QStringLiteral("OPC UA 设备应答异常：") + statusName(h.service);
    return false;
  }
  if (tid.numeric == kServiceFault) {
    *error = QStringLiteral("OPC UA 服务被拒绝");
    return false;
  }
  *out = r;
  return true;
}

bool uaHello(UaSession* s, const Prepared& c, QString* error) {
  Writer w;
  w.u32(0);
  w.u32(65536);
  w.u32(65536);
  w.u32(0);
  w.u32(0);
  w.str(c.endpoint);
  if (!sendAll(s->fd, wrapMsg("HEL", w.b), error)) return false;
  char typ[4] = {};
  QByteArray body;
  if (!recvMsg(s->fd, typ, &body, error)) return false;
  if (!(typ[0] == 'A' && typ[1] == 'C' && typ[2] == 'K')) {
    *error = QStringLiteral("OPC UA 握手未被确认");
    return false;
  }
  return true;
}

bool uaOpenChannel(UaSession* s, QString* error) {
  Writer p;
  writeRequestHeader(p, nidNumeric(0, 0), ++s->req, s->timeoutMs);
  p.u32(0);  // protocol version
  p.u32(0);  // Issue
  p.u32(1);  // SecurityMode None
  QByteArray nonce(32, char(0x11));
  p.bytes(nonce);
  p.u32(600000);
  Reader r((QByteArray()));
  if (!sendRecv(s, "OPN", opnBody(++s->seq, s->req, p.b), kOpenChRes, &r, error))
    return false;
  (void)r.u32();  // server protocol
  s->channel = r.u32();
  s->token = r.u32();
  (void)r.i64();
  (void)r.u32();
  (void)r.bytes();
  if (!r.ok || s->channel == 0) {
    *error = QStringLiteral("OPC UA 安全通道建立失败");
    return false;
  }
  return true;
}

bool uaCreateSession(UaSession* s, const Prepared& c, QString* error) {
  Writer p;
  writeRequestHeader(p, nidNumeric(0, 0), ++s->req, s->timeoutMs);
  // ApplicationDescription
  p.str(QStringLiteral("urn:sieans:vision:client"));
  p.str(QStringLiteral("urn:sieans:vision"));
  p.locText(QStringLiteral("SIEANS Vision"));
  p.u32(1);  // Client
  p.i32(-1);
  p.i32(-1);
  p.i32(0);  // discovery urls empty
  p.i32(-1);  // serverUri
  p.str(c.endpoint);
  p.str(QStringLiteral("SIEANS Qt"));
  QByteArray nonce(32, char(0x22));
  p.bytes(nonce);
  p.i32(-1);  // client cert
  p.f64(60000);
  p.u32(0);
  Reader r((QByteArray()));
  const QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kCreateSessReq, p.b);
  if (!sendRecv(s, "MSG", body, kCreateSessRes, &r, error)) return false;
  (void)r.nodeId();  // session id
  s->auth = r.nodeId();
  (void)r.f64();
  (void)r.bytes();
  (void)r.bytes();
  // skip endpoints array
  const qint32 nEp = r.i32();
  for (int i = 0; i < nEp && r.ok; ++i) {
    (void)r.str();
    // ApplicationDescription
    (void)r.str();
    (void)r.str();
    const quint8 lm = r.u8();
    if (lm & 0x01) (void)r.str();
    if (lm & 0x02) (void)r.str();
    (void)r.u32();
    (void)r.str();
    (void)r.str();
    const qint32 nd = r.i32();
    for (int j = 0; j < nd; ++j) (void)r.str();
    (void)r.bytes();
    (void)r.u32();
    (void)r.str();
    const qint32 nu = r.i32();
    for (int j = 0; j < nu; ++j) {
      (void)r.str();
      (void)r.u32();
      (void)r.str();
      (void)r.str();
      (void)r.str();
    }
    (void)r.str();
    (void)r.u8();
  }
  const qint32 nCert = r.i32();
  for (int i = 0; i < nCert; ++i) {
    (void)r.bytes();
    (void)r.bytes();
  }
  (void)r.str();
  (void)r.bytes();
  (void)r.u32();
  if (!r.ok) {
    *error = QStringLiteral("OPC UA 会话应答不完整");
    return false;
  }
  return true;
}

bool uaActivate(UaSession* s, QString* error) {
  Writer tok;
  tok.str(QStringLiteral("Anonymous"));
  Writer p;
  writeRequestHeader(p, s->auth, ++s->req, s->timeoutMs);
  p.i32(-1);  // algorithm null
  p.i32(-1);  // signature null
  p.i32(0);   // software certs
  p.i32(0);   // locales
  p.extObj(kAnonymousTok, tok.b);
  p.i32(-1);
  p.i32(-1);
  Reader r((QByteArray()));
  const QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kActivateReq, p.b);
  if (!sendRecv(s, "MSG", body, kActivateRes, &r, error)) return false;
  return true;
}

bool uaClose(UaSession* s) {
  if (s->fd < 0) return true;
  QString err;
  Writer p;
  writeRequestHeader(p, s->auth, ++s->req, s->timeoutMs);
  p.u8(1);  // deleteSubscriptions
  Reader r((QByteArray()));
  const QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kCloseSessReq, p.b);
  (void)sendRecv(s, "MSG", body, kCloseSessRes, &r, &err);
  Writer q;
  writeRequestHeader(q, nidNumeric(0, 0), ++s->req, s->timeoutMs);
  const QByteArray clo =
      msgBody('C', s->channel, s->token, ++s->seq, s->req, kCloseChReq, q.b);
  (void)sendAll(s->fd, wrapMsg("CLO", clo), &err);
  closeFd(s);
  return true;
}

bool uaConnect(UaSession* s, const Prepared& c, QString* error) {
  s->timeoutMs = c.timeoutMs;
  s->fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (s->fd < 0) {
    *error = QStringLiteral("无法创建 OPC UA 套接字");
    return false;
  }
  setTimeo(s->fd, c.timeoutMs);
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(quint16(c.port));
  if (::inet_pton(AF_INET, c.host.toUtf8().constData(), &addr.sin_addr) != 1) {
    *error = QStringLiteral("无法解析 OPC UA 主机地址");
    closeFd(s);
    return false;
  }
  if (::connect(s->fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
    *error = QStringLiteral("无法连接 OPC UA 设备，请检查端点");
    closeFd(s);
    return false;
  }
  if (!uaHello(s, c, error) || !uaOpenChannel(s, error) || !uaCreateSession(s, c, error) ||
      !uaActivate(s, error)) {
    closeFd(s);
    return false;
  }
  return true;
}

bool uaRead(UaSession* s, const UaNodeId& node, DataVal* dv, QString* error) {
  Writer p;
  writeRequestHeader(p, s->auth, ++s->req, s->timeoutMs);
  p.f64(0);
  p.u32(2);  // Both timestamps
  p.i32(1);
  p.nodeId(node);
  p.u32(13);  // Value
  p.i32(-1);  // index range null
  p.u16(0);
  p.i32(-1);  // data encoding name null
  Reader r((QByteArray()));
  const QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kReadReq, p.b);
  if (!sendRecv(s, "MSG", body, kReadRes, &r, error)) return false;
  const qint32 n = r.i32();
  if (n < 1) {
    *error = QStringLiteral("OPC UA 读取应答为空");
    return false;
  }
  *dv = readDataValue(r);
  if (!r.ok) {
    *error = QStringLiteral("OPC UA 读取应答异常");
    return false;
  }
  return true;
}

bool uaWrite(UaSession* s, const UaNodeId& node, const QString& dtype, const QVariant& val,
             quint32* status, QString* error) {
  DataVal dv;
  dv.hasValue = true;
  dv.dtype = dtype;
  dv.value = val;
  dv.isArray = val.metaType().id() == QMetaType::QVariantList;
  dv.status = 0;
  Writer p;
  writeRequestHeader(p, s->auth, ++s->req, s->timeoutMs);
  p.i32(1);
  p.nodeId(node);
  p.u32(13);
  p.i32(-1);
  writeDataValue(p, dv);
  Reader r((QByteArray()));
  const QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kWriteReq, p.b);
  if (!sendRecv(s, "MSG", body, kWriteRes, &r, error)) return false;
  const qint32 n = r.i32();
  if (n < 1) {
    *error = QStringLiteral("OPC UA 写入应答为空");
    return false;
  }
  *status = r.u32();
  return r.ok;
}

bool uaBrowse(UaSession* s, const UaNodeId& node, int limit, QVariantList* items,
              bool* truncated, QString* error) {
  Writer p;
  writeRequestHeader(p, s->auth, ++s->req, s->timeoutMs);
  p.nodeId(nidNumeric(0, 0));  // view
  p.i64(0);
  p.u32(0);
  p.u32(quint32(limit));
  p.i32(1);
  p.nodeId(node);
  p.u32(0);  // forward
  p.nodeId(nidNumeric(0, 33));
  p.u8(1);
  p.u32(0);
  p.u32(63);
  Reader r((QByteArray()));
  const QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kBrowseReq, p.b);
  if (!sendRecv(s, "MSG", body, kBrowseRes, &r, error)) return false;
  const qint32 n = r.i32();
  if (n < 1) {
    *error = QStringLiteral("OPC UA 浏览应答为空");
    return false;
  }
  const quint32 st = r.u32();
  if (st != 0) {
    *error = QStringLiteral("OPC UA 浏览失败：") + statusName(st);
    return false;
  }
  const QByteArray cont = r.bytes();
  *truncated = !cont.isEmpty() && !cont.isNull();
  const qint32 nref = r.i32();
  const QStringList nss = nsArray();
  for (int i = 0; i < nref && r.ok; ++i) {
    (void)r.nodeId();
    (void)r.u8();
    const UaNodeId nid = r.nodeId();
    const quint16 bns = r.u16();
    const QString bname = r.str();
    const quint8 lm = r.u8();
    QString locale, text;
    if (lm & 0x01) locale = r.str();
    if (lm & 0x02) text = r.str();
    const quint32 cls = r.u32();
    (void)r.nodeId();
    QVariantMap row;
    row.insert(QStringLiteral("nodeId"), nid.toString());
    row.insert(QStringLiteral("displayName"), text.isEmpty() ? bname : text);
    row.insert(QStringLiteral("browseName"), bname);
    row.insert(QStringLiteral("nodeClass"),
               cls == 1 ? QStringLiteral("Object") : QStringLiteral("Variable"));
    row.insert(QStringLiteral("namespaceUri"),
               nid.ns < nss.size() ? nss[nid.ns] : QString());
    (void)bns;
    items->push_back(row);
  }
  if (int(items->size()) > limit) {
    while (items->size() > limit) items->removeLast();
    *truncated = true;
  }
  return r.ok;
}

bool uaWait(UaSession* s, const Prepared& c, OpcUaResult* out, QString* error) {
  const QString mode =
      c.raw.value(QStringLiteral("triggerMode"), QStringLiteral("level")).toString();
  // CreateSubscription
  Writer p;
  writeRequestHeader(p, s->auth, ++s->req, s->timeoutMs);
  p.f64(double(c.publishingMs));
  p.u32(10000);
  p.u32(10);
  p.u32(100);
  p.u8(1);
  p.u8(0);
  Reader r((QByteArray()));
  QByteArray body =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kCreateSubReq, p.b);
  if (!sendRecv(s, "MSG", body, kCreateSubRes, &r, error)) return false;
  const quint32 subId = r.u32();
  (void)r.f64();
  (void)r.u32();
  (void)r.u32();
  // CreateMonitoredItems
  Writer m;
  writeRequestHeader(m, s->auth, ++s->req, s->timeoutMs);
  m.u32(subId);
  m.u32(2);
  m.i32(1);
  m.nodeId(c.node);
  m.u32(13);
  m.i32(-1);
  m.u16(0);
  m.i32(-1);
  m.u32(2);  // reporting
  m.u32(1);  // client handle
  m.f64(double(c.publishingMs));
  m.extEmpty();
  m.u32(100);
  m.u8(1);
  body = msgBody('M', s->channel, s->token, ++s->seq, s->req, kCreateMonReq, m.b);
  Reader r2((QByteArray()));
  if (!sendRecv(s, "MSG", body, kCreateMonRes, &r2, error)) return false;
  const qint32 nres = r2.i32();
  if (nres < 1) {
    *error = QStringLiteral("OPC UA 订阅未建立");
    return false;
  }
  const quint32 mst = r2.u32();
  if (mst != 0) {
    *error = QStringLiteral("等待时限内未能建立 OPC UA 订阅");
    return false;
  }
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::milliseconds(c.waitTimeoutMs);
  bool havePrev = false;
  bool prev = false;
  quint32 lastSeq = 0;
  int count = 0;
  QVariant first;
  bool gotAny = false;
  while (std::chrono::steady_clock::now() < deadline) {
    Writer pb;
    writeRequestHeader(pb, s->auth, ++s->req, s->timeoutMs);
    if (lastSeq == 0)
      pb.i32(0);
    else {
      pb.i32(1);
      pb.u32(subId);
      pb.u32(lastSeq);
    }
    Reader pr((QByteArray()));
    body = msgBody('M', s->channel, s->token, ++s->seq, s->req, kPublishReq, pb.b);
    QString pe;
    if (!sendRecv(s, "MSG", body, kPublishRes, &pr, &pe)) {
      if (pe.contains(QStringLiteral("超时")) && gotAny) break;
      *error = pe.isEmpty() ? QStringLiteral("OPC UA 订阅未收到有效初始数据，不能作为条件超时继续")
                            : pe;
      if (!gotAny) *error = QStringLiteral("OPC UA 订阅未收到有效初始数据，不能作为条件超时继续");
      return false;
    }
    const quint32 sid = pr.u32();
    (void)sid;
    const qint32 nav = pr.i32();
    for (int i = 0; i < nav; ++i) (void)pr.u32();
    (void)pr.u8();
    lastSeq = pr.u32();
    (void)pr.i64();
    const qint32 nnot = pr.i32();
    for (int i = 0; i < nnot && pr.ok; ++i) {
      const UaNodeId typ = pr.nodeId();
      const quint8 enc = pr.u8();
      QByteArray nb;
      if (enc == 1) nb = pr.bytes();
      if (typ.numeric != kDataChangeNotif) continue;
      Reader nr(nb);
      const qint32 nitem = nr.i32();
      for (int j = 0; j < nitem && nr.ok; ++j) {
        (void)nr.u32();
        const DataVal dv = readDataValue(nr);
        if (!qualityOk(dv.status)) {
          *error = QStringLiteral("订阅节点数据质量不合格：") + statusName(dv.status);
          return false;
        }
        bool matched = false;
        if (!evalCondition(dv.value, dv.dtype, c.raw, &matched, error)) return false;
        count++;
        if (count == 1) first = dv.value;
        gotAny = true;
        out->value = encodeDisplay(dv.value, dv.dtype);
        out->dataType = dv.dtype;
        out->status = statusName(dv.status);
        out->quality = QStringLiteral("good");
        out->notificationCount = count;
        bool fire = false;
        if (mode == QLatin1String("level"))
          fire = matched;
        else if (mode == QLatin1String("rising"))
          fire = havePrev && !prev && matched;
        else
          fire = havePrev && prev && !matched;
        havePrev = true;
        prev = matched;
        if (fire) {
          out->triggered = true;
          out->passed = true;
          // delete subscription
          Writer d;
          writeRequestHeader(d, s->auth, ++s->req, s->timeoutMs);
          d.i32(1);
          d.u32(subId);
          Reader dr((QByteArray()));
          const QByteArray db =
              msgBody('M', s->channel, s->token, ++s->seq, s->req, kDeleteSubReq, d.b);
          QString de;
          (void)sendRecv(s, "MSG", db, kDeleteSubRes, &dr, &de);
          return true;
        }
      }
    }
  }
  if (!gotAny) {
    *error = QStringLiteral("OPC UA 订阅未收到有效初始数据，不能作为条件超时继续");
    return false;
  }
  if (c.raw.value(QStringLiteral("onTimeout"), QStringLiteral("error")).toString() ==
      QLatin1String("error")) {
    *error = QStringLiteral("等待 OPC UA 信号超时");
    return false;
  }
  out->timedOut = true;
  out->passed = true;
  Writer d;
  writeRequestHeader(d, s->auth, ++s->req, s->timeoutMs);
  d.i32(1);
  d.u32(subId);
  Reader dr((QByteArray()));
  const QByteArray db =
      msgBody('M', s->channel, s->token, ++s->seq, s->req, kDeleteSubReq, d.b);
  QString de;
  (void)sendRecv(s, "MSG", db, kDeleteSubRes, &dr, &de);
  return true;
}


/* ---------------- runOp ---------------- */

OpcUaResult finishFail(OpcUaResult r, const QString& e,
                       const std::chrono::steady_clock::time_point& started,
                       bool sent) {
  r.ok = false;
  r.error = e;
  if (sent)
    r.error += QStringLiteral("；写请求可能已到达设备，未自动重试，请读取设备状态确认");
  r.note = r.error;
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  return r;
}

OpcUaResult finishOk(OpcUaResult r, const Prepared& c,
                     const std::chrono::steady_clock::time_point& started) {
  r.ok = true;
  r.endpoint = c.endpoint;
  r.nodeId = c.node.toString();
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  if (r.note.isEmpty())
    r.note = QStringLiteral("opcua %1 %2").arg(r.action, r.nodeId);
  if (r.quality.isEmpty() && r.statusCode == 0) r.quality = QStringLiteral("good");
  if (r.status.isEmpty()) r.status = QStringLiteral("Good");
  return r;
}

void fillFromData(OpcUaResult* r, const DataVal& dv) {
  r->dataType = dv.dtype;
  r->isArray = dv.isArray;
  r->value = encodeDisplay(dv.value, dv.dtype);
  if (dv.isArray)
    r->values = r->value.toList();
  else if (r->value.isValid())
    r->values = QVariantList{r->value};
  r->statusCode = dv.status;
  r->status = statusName(dv.status);
  r->quality = qualityName(dv.status);
  r->sourceTimestamp = tsIso(dv.sourceTs);
  r->serverTimestamp = tsIso(dv.serverTs);
}

OpcUaResult runOp(const QVariantMap& params, const QString& op) {
  const auto started = std::chrono::steady_clock::now();
  OpcUaResult r;
  r.action = op;
  r.protocol = QStringLiteral("opc-ua");
  Prepared c;
  QString err;
  if (!prepareCommon(params, op, &c, &err)) return finishFail(r, err, started, false);
  r.endpoint = c.endpoint;
  r.nodeId = c.node.toString();

  if (c.connection == QLatin1String("simulator")) {
    if (op == QLatin1String("write")) {
      const quint32 st = storeWriteRaw(c.node, c.dtype, c.writeValue);
      if (st != 0)
        return finishFail(r, QStringLiteral("OPC UA 写入失败：") + statusName(st), started,
                          true);
      r.acknowledged = true;
      r.dataType = c.dtype;
      r.value = encodeDisplay(c.writeValue, c.dtype);
      r.note = QStringLiteral("服务端已确认写入；不代表物理动作完成，流程停止或失败不会撤销设备写入。");
      return finishOk(r, c, started);
    }
    if (op == QLatin1String("browse")) {
      if (!storeBrowse(c.node, c.browseLimit, &r.items, &r.truncated, &err))
        return finishFail(r, err, started, false);
      r.browseCount = r.items.size();
      r.value = r.browseCount;
      return finishOk(r, c, started);
    }
    if (op == QLatin1String("read")) {
      DataVal dv;
      if (!storeRead(c.node, &dv, &err)) return finishFail(r, err, started, false);
      fillFromData(&r, dv);
      if (c.requireGood && !qualityOk(dv.status))
        return finishFail(r, QStringLiteral("节点数据质量不合格：") + statusName(dv.status),
                          started, false);
      return finishOk(r, c, started);
    }
    // wait: poll the shared image
    const QString mode =
        c.raw.value(QStringLiteral("triggerMode"), QStringLiteral("level")).toString();
    const auto deadline =
        std::chrono::steady_clock::now() + std::chrono::milliseconds(c.waitTimeoutMs);
    bool havePrev = false;
    bool prev = false;
    int count = 0;
    QVariant first;
    while (true) {
      DataVal dv;
      if (!storeRead(c.node, &dv, &err)) return finishFail(r, err, started, false);
      if (!qualityOk(dv.status))
        return finishFail(r, QStringLiteral("订阅节点数据质量不合格：") + statusName(dv.status),
                          started, false);
      bool matched = false;
      if (!evalCondition(dv.value, dv.dtype, c.raw, &matched, &err))
        return finishFail(r, err, started, false);
      count++;
      if (count == 1) first = dv.value;
      r.value = encodeDisplay(dv.value, dv.dtype);
      r.dataType = dv.dtype;
      r.status = statusName(dv.status);
      r.quality = QStringLiteral("good");
      r.notificationCount = count;
      bool fire = false;
      if (mode == QLatin1String("level"))
        fire = matched;
      else if (mode == QLatin1String("rising"))
        fire = havePrev && !prev && matched;
      else
        fire = havePrev && prev && !matched;
      havePrev = true;
      prev = matched;
      if (fire) {
        r.triggered = true;
        r.passed = true;
        return finishOk(r, c, started);
      }
      if (std::chrono::steady_clock::now() >= deadline) break;
      std::this_thread::sleep_for(std::chrono::milliseconds(c.publishingMs));
      if (std::chrono::steady_clock::now() >= deadline) break;
    }
    if (count == 0)
      return finishFail(r, QStringLiteral("OPC UA 订阅未收到有效初始数据，不能作为条件超时继续"),
                        started, false);
    if (c.raw.value(QStringLiteral("onTimeout"), QStringLiteral("error")).toString() ==
        QLatin1String("error"))
      return finishFail(r, QStringLiteral("等待 OPC UA 信号超时"), started, false);
    r.timedOut = true;
    r.passed = true;
    return finishOk(r, c, started);
  }

  UaSession sess;
  if (!uaConnect(&sess, c, &err)) return finishFail(r, err, started, false);
  bool sent = false;
  if (op == QLatin1String("write")) {
    quint32 st = 0;
    sent = true;
    if (!uaWrite(&sess, c.node, c.dtype, c.writeValue, &st, &err)) {
      uaClose(&sess);
      return finishFail(r, err, started, true);
    }
    uaClose(&sess);
    if (st != 0)
      return finishFail(r, QStringLiteral("OPC UA 写入失败：") + statusName(st), started, true);
    r.acknowledged = true;
    r.dataType = c.dtype;
    r.value = encodeDisplay(c.writeValue, c.dtype);
    r.note = QStringLiteral("服务端已确认写入；不代表物理动作完成，流程停止或失败不会撤销设备写入。");
    return finishOk(r, c, started);
  }
  if (op == QLatin1String("read")) {
    DataVal dv;
    if (!uaRead(&sess, c.node, &dv, &err)) {
      uaClose(&sess);
      return finishFail(r, err, started, false);
    }
    uaClose(&sess);
    fillFromData(&r, dv);
    if (c.requireGood && !qualityOk(dv.status))
      return finishFail(r, QStringLiteral("节点数据质量不合格：") + statusName(dv.status),
                        started, false);
    return finishOk(r, c, started);
  }
  if (op == QLatin1String("browse")) {
    if (!uaBrowse(&sess, c.node, c.browseLimit, &r.items, &r.truncated, &err)) {
      uaClose(&sess);
      return finishFail(r, err, started, false);
    }
    uaClose(&sess);
    r.browseCount = r.items.size();
    r.value = r.browseCount;
    return finishOk(r, c, started);
  }
  if (!uaWait(&sess, c, &r, &err)) {
    uaClose(&sess);
    return finishFail(r, err, started, false);
  }
  uaClose(&sess);
  return finishOk(r, c, started);
}

/* ---------------- soft server ---------------- */

QByteArray makeRespHeader(quint32 handle, quint32 service = 0) {
  Writer w;
  w.i64(uaNow());
  w.u32(handle);
  w.u32(service);
  w.diagEmpty();
  w.i32(0);
  w.extEmpty();
  return w.b;
}

QByteArray makeMsg(quint32 channel, quint32 token, quint32 seq, quint32 reqId,
                   quint32 typeId, const QByteArray& payload) {
  return wrapMsg("MSG", msgBody('M', channel, token, seq, reqId, typeId, payload));
}

struct MonItem {
  quint32 id = 0;
  quint32 clientHandle = 0;
  UaNodeId node;
};

struct SubState {
  quint32 id = 0;
  quint32 seq = 0;
  std::vector<MonItem> items;
};

struct SvcState {
  quint32 channel = 0;
  quint32 token = 0;
  quint32 seq = 0;
  UaNodeId auth;
  bool activated = false;
  QHash<quint32, SubState> subs;
  quint32 nextSub = 1;
  quint32 nextMon = 1;
};

void writeAppDesc(Writer& w) {
  w.str(QStringLiteral("urn:sieans:vision:server"));
  w.str(QStringLiteral("urn:sieans:vision"));
  w.locText(QStringLiteral("SIEANS OPC UA 本机模拟设备"));
  w.u32(0);  // Server
  w.i32(-1);
  w.i32(-1);
  w.i32(0);
}

void writeEndpoint(Writer& w, const QString& ep) {
  w.str(ep);
  writeAppDesc(w);
  w.i32(-1);  // cert
  w.u32(1);   // None
  w.str(QString::fromUtf8(kPolicyNone));
  w.i32(1);
  w.str(QStringLiteral("Anonymous"));
  w.u32(0);
  w.i32(-1);
  w.i32(-1);
  w.i32(-1);
  w.str(QString::fromUtf8(kTransport));
  w.u8(0);
}

QByteArray handleService(SvcState* st, quint32 typeId, Reader& r, quint32 reqId) {
  RespHead dummy;
  // Request header already starts at r
  UaNodeId token = r.nodeId();
  (void)r.i64();
  const quint32 handle = r.u32();
  (void)r.u32();
  (void)r.str();
  (void)r.u32();
  r.skipExt();
  if (!r.ok) return QByteArray();

  auto fail = [&](quint32 code, quint32 typ) {
    Writer w;
    w.b.append(makeRespHeader(handle, code));
    return makeMsg(st->channel, st->token, ++st->seq, reqId, typ ? typ : kServiceFault, w.b);
  };

  if (typeId == kCreateSessReq) {
    st->auth = nidNumeric(1, ++gNextSession);
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.nodeId(nidNumeric(1, st->auth.numeric));
    w.nodeId(st->auth);
    w.f64(60000);
    QByteArray nonce(32, char(0x33));
    w.bytes(nonce);
    w.i32(-1);
    w.i32(1);
    const QString ep = opcUaSoftServer().endpoint();
    writeEndpoint(w, ep);
    w.i32(0);
    w.i32(-1);
    w.i32(-1);
    w.u32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kCreateSessRes, w.b);
  }
  if (typeId == kActivateReq) {
    st->activated = true;
    (void)token;
    Writer w;
    w.b.append(makeRespHeader(handle));
    QByteArray nonce(32, char(0x44));
    w.bytes(nonce);
    w.i32(0);
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kActivateRes, w.b);
  }
  if (typeId == kCloseSessReq) {
    st->activated = false;
    st->subs.clear();
    Writer w;
    w.b.append(makeRespHeader(handle));
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kCloseSessRes, w.b);
  }
  if (typeId == kReadReq) {
    (void)r.f64();
    (void)r.u32();
    const qint32 n = r.i32();
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.i32(n);
    for (int i = 0; i < n && r.ok; ++i) {
      const UaNodeId id = r.nodeId();
      const quint32 attr = r.u32();
      (void)r.str();
      (void)r.u16();
      (void)r.str();
      DataVal dv;
      if (attr != 13) {
        dv.status = kBadAttributeIdInvalid;
        writeDataValue(w, dv);
        continue;
      }
      QString err;
      if (!storeRead(id, &dv, &err)) {
        dv.hasValue = false;
        writeDataValue(w, dv);
        continue;
      }
      writeDataValue(w, dv);
    }
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kReadRes, w.b);
  }
  if (typeId == kWriteReq) {
    const qint32 n = r.i32();
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.i32(n);
    for (int i = 0; i < n && r.ok; ++i) {
      const UaNodeId id = r.nodeId();
      const quint32 attr = r.u32();
      (void)r.str();
      const DataVal dv = readDataValue(r);
      quint32 stc = 0;
      if (attr != 13)
        stc = kBadAttributeIdInvalid;
      else if (!dv.hasValue)
        stc = kBadTypeMismatch;
      else
        stc = storeWriteRaw(id, dv.dtype, dv.value);
      w.u32(stc);
    }
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kWriteRes, w.b);
  }
  if (typeId == kBrowseReq) {
    (void)r.nodeId();
    (void)r.i64();
    (void)r.u32();
    const quint32 maxr = r.u32();
    const qint32 n = r.i32();
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.i32(n);
    for (int i = 0; i < n && r.ok; ++i) {
      const UaNodeId id = r.nodeId();
      (void)r.u32();
      (void)r.nodeId();
      (void)r.u8();
      (void)r.u32();
      (void)r.u32();
      QVariantList items;
      bool trunc = false;
      QString err;
      const int limit = maxr == 0 ? 100 : int(std::min<quint32>(maxr, 500));
      if (!storeBrowse(id, limit, &items, &trunc, &err)) {
        w.u32(kBadNodeIdUnknown);
        w.i32(-1);
        w.i32(0);
        continue;
      }
      w.u32(0);
      w.i32(-1);
      w.i32(items.size());
      for (const QVariant& rowv : items) {
        const QVariantMap row = rowv.toMap();
        w.nodeId(nidNumeric(0, 47));  // HasComponent
        w.u8(1);
        UaNodeId cid;
        QString e2;
        parseNodeId(row.value(QStringLiteral("nodeId")).toString(), &cid, &e2);
        w.expNodeId(cid);
        const quint16 nsi = cid.ns;
        w.qname(nsi, row.value(QStringLiteral("browseName")).toString());
        w.locText(row.value(QStringLiteral("displayName")).toString());
        const bool isObj = row.value(QStringLiteral("nodeClass")).toString() ==
                           QLatin1String("Object");
        w.u32(isObj ? 1 : 2);
        w.expNodeId(nidNumeric(0, isObj ? 58 : 63));
      }
    }
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kBrowseRes, w.b);
  }
  if (typeId == kCreateSubReq) {
    (void)r.f64();
    (void)r.u32();
    (void)r.u32();
    (void)r.u32();
    (void)r.u8();
    (void)r.u8();
    SubState sub;
    sub.id = st->nextSub++;
    sub.seq = 0;
    st->subs.insert(sub.id, sub);
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.u32(sub.id);
    w.f64(100);
    w.u32(10000);
    w.u32(10);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kCreateSubRes, w.b);
  }
  if (typeId == kCreateMonReq) {
    const quint32 subId = r.u32();
    (void)r.u32();
    const qint32 n = r.i32();
    auto it = st->subs.find(subId);
    Writer w;
    if (it == st->subs.end()) {
      w.b.append(makeRespHeader(handle));
      w.i32(n);
      for (int i = 0; i < n; ++i) {
        w.u32(kBadSubId);
        w.u32(0);
        w.f64(0);
        w.u8(0);
        w.u32(0);
        w.u32(0);
        w.u8(0);
      }
      w.i32(0);
      return makeMsg(st->channel, st->token, ++st->seq, reqId, kCreateMonRes, w.b);
    }
    w.b.append(makeRespHeader(handle));
    w.i32(n);
    for (int i = 0; i < n && r.ok; ++i) {
      const UaNodeId id = r.nodeId();
      (void)r.u32();
      (void)r.str();
      (void)r.u16();
      (void)r.str();
      (void)r.u32();
      const quint32 ch = r.u32();
      (void)r.f64();
      r.skipExt();
      (void)r.u32();
      (void)r.u8();
      MonItem mi;
      mi.id = st->nextMon++;
      mi.clientHandle = ch;
      mi.node = id;
      it->items.push_back(mi);
      QString err;
      DataVal dv;
      const bool ok = storeRead(id, &dv, &err);
      w.u32(ok ? 0 : kBadNodeIdUnknown);
      w.u32(mi.id);
      w.f64(100);
      w.u8(0);
      w.u32(0);
      w.u32(100);
      w.u8(0);
    }
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kCreateMonRes, w.b);
  }
  if (typeId == kPublishReq) {
    const qint32 nack = r.i32();
    for (int i = 0; i < nack; ++i) {
      (void)r.u32();
      (void)r.u32();
    }
    quint32 subId = 0;
    if (!st->subs.isEmpty()) subId = st->subs.begin().key();
    SubState* sub = subId ? &st->subs[subId] : nullptr;
    Writer notif;
    qint32 nitems = 0;
    if (sub) {
      Writer items;
      for (const MonItem& mi : sub->items) {
        DataVal dv;
        QString err;
        if (!storeRead(mi.node, &dv, &err)) continue;
        items.u32(mi.clientHandle);
        writeDataValue(items, dv);
        nitems++;
      }
      items.i32(0);  // diags - wait, this should be after the array. I'll prefix count.
      Writer body;
      body.i32(nitems);
      // rebuild: the items writer already wrote handle+dv pairs without count
      // Fix: write properly
      (void)items;
    }
    Writer inner;
    if (sub) {
      inner.i32(int(sub->items.size()));
      for (const MonItem& mi : sub->items) {
        DataVal dv;
        QString err;
        if (!storeRead(mi.node, &dv, &err)) {
          dv.hasValue = false;
          dv.status = kBadNodeIdUnknown;
        }
        inner.u32(mi.clientHandle);
        writeDataValue(inner, dv);
      }
      inner.i32(0);
    } else {
      inner.i32(0);
      inner.i32(0);
    }
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.u32(subId);
    w.i32(0);  // available seq
    w.u8(0);   // more
    const quint32 seqn = sub ? ++sub->seq : 1;
    w.u32(seqn);
    w.i64(uaNow());
    if (sub && !sub->items.empty()) {
      w.i32(1);
      w.extObj(kDataChangeNotif, inner.b);
    } else {
      w.i32(0);
    }
    w.i32(0);  // results
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kPublishRes, w.b);
  }
  if (typeId == kDeleteSubReq) {
    const qint32 n = r.i32();
    Writer w;
    w.b.append(makeRespHeader(handle));
    w.i32(n);
    for (int i = 0; i < n; ++i) {
      const quint32 id = r.u32();
      const bool ok = st->subs.remove(id) > 0;
      w.u32(ok ? 0 : kBadSubId);
    }
    w.i32(0);
    return makeMsg(st->channel, st->token, ++st->seq, reqId, kDeleteSubRes, w.b);
  }
  return fail(kBadDecoding, kServiceFault);
}

QByteArray handleOpen(SvcState* st, Reader& r, quint32 reqId) {
  // request already after type id; parse header + fields loosely
  (void)r.nodeId();
  (void)r.i64();
  const quint32 handle = r.u32();
  (void)r.u32();
  (void)r.str();
  (void)r.u32();
  r.skipExt();
  (void)r.u32();
  (void)r.u32();
  (void)r.u32();
  (void)r.bytes();
  (void)r.u32();
  if (st->channel == 0) {
    st->channel = ++gNextChannel;
    st->token = 1;
  }
  Writer w;
  w.b.append(makeRespHeader(handle));
  w.u32(0);  // server protocol
  w.u32(st->channel);
  w.u32(st->token);
  w.i64(uaNow());
  w.u32(600000);
  QByteArray nonce(32, char(0x55));
  w.bytes(nonce);
  Writer out;
  out.str(QString::fromUtf8(kPolicyNone));
  out.i32(-1);
  out.i32(-1);
  out.u32(++st->seq);
  out.u32(reqId);
  out.nodeId(nidNumeric(0, kOpenChRes));
  out.b.append(w.b);
  return wrapMsg("OPN", out.b);
}

void serveClient(int cfd) {
  auto last = std::chrono::steady_clock::now();
  SvcState st;
  QString err;
  while (gServerRun) {
    pollfd pfd{};
    pfd.fd = cfd;
    pfd.events = POLLIN;
    const int rc = ::poll(&pfd, 1, 200);
    if (rc == 0) {
      if (std::chrono::steady_clock::now() - last > std::chrono::seconds(30)) break;
      continue;
    }
    if (rc < 0) {
      if (errno == EINTR) continue;
      break;
    }
    timeval tv{};
    tv.tv_sec = 2;
    setsockopt(cfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(cfd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    char typ[4] = {};
    QByteArray body;
    if (!recvMsg(cfd, typ, &body, &err)) break;
    last = std::chrono::steady_clock::now();
    QByteArray reply;
    if (typ[0] == 'H' && typ[1] == 'E' && typ[2] == 'L') {
      Writer w;
      w.u32(0);
      w.u32(65536);
      w.u32(65536);
      w.u32(0);
      w.u32(0);
      reply = wrapMsg("ACK", w.b);
    } else if (typ[0] == 'O' && typ[1] == 'P' && typ[2] == 'N') {
      Reader r(body);
      (void)r.str();
      (void)r.bytes();
      (void)r.bytes();
      (void)r.u32();
      const quint32 reqId = r.u32();
      const UaNodeId tid = r.nodeId();
      (void)tid;
      reply = handleOpen(&st, r, reqId);
    } else if (typ[0] == 'C' && typ[1] == 'L' && typ[2] == 'O') {
      break;
    } else if (typ[0] == 'M' && typ[1] == 'S' && typ[2] == 'G') {
      Reader r(body);
      const quint32 ch = r.u32();
      const quint32 tok = r.u32();
      (void)ch;
      (void)tok;
      (void)r.u32();
      const quint32 reqId = r.u32();
      const UaNodeId tid = r.nodeId();
      if (!r.ok || tid.kind != NodeKind::Numeric) break;
      reply = handleService(&st, tid.numeric, r, reqId);
    } else {
      break;
    }
    if (!reply.isEmpty() && !sendAll(cfd, reply, &err)) break;
  }
  ::close(cfd);
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

OpcUaResult runOpcUaRead(const QVariantMap& params) { return runOp(params, QStringLiteral("read")); }
OpcUaResult runOpcUaWrite(const QVariantMap& params) { return runOp(params, QStringLiteral("write")); }
OpcUaResult runOpcUaBrowse(const QVariantMap& params) {
  return runOp(params, QStringLiteral("browse"));
}
OpcUaResult runOpcUaWait(const QVariantMap& params) { return runOp(params, QStringLiteral("wait")); }

OpcUaSoftServer& opcUaSoftServer() {
  QMutexLocker lock(&gServerMutex);
  if (!gServer) gServer = new OpcUaSoftServer();
  return *gServer;
}

bool OpcUaSoftServer::start(quint16 port, QString* error) {
  if (gServerRun && gListenFd >= 0 && (port == 0 || port == gListenPort)) return true;
  if (gServerRun) stop();
  ensureStore();
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    if (error) *error = QStringLiteral("无法创建 OPC UA 监听套接字");
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
      *error = QStringLiteral("无法绑定 OPC UA 端口 %1: %2")
                   .arg(port)
                   .arg(QString::fromLocal8Bit(strerror(errno)));
    ::close(fd);
    return false;
  }
  if (::listen(fd, 8) != 0) {
    if (error) *error = QStringLiteral("OPC UA 监听失败");
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

void OpcUaSoftServer::stop() {
  gServerRun = false;
  if (gListenFd >= 0) {
    ::close(gListenFd);
    gListenFd = -1;
  }
  gListenPort = 0;
}

bool OpcUaSoftServer::running() const { return gServerRun && gListenFd >= 0; }

quint16 OpcUaSoftServer::port() const { return gListenPort; }

QString OpcUaSoftServer::endpoint() const {
  return QStringLiteral("opc.tcp://127.0.0.1:%1/sieans/").arg(gListenPort);
}

QStringList opcUaSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail) {
    if (!ok) fails << QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail);
  };

  {
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Height"));
    const OpcUaResult rr = runOpcUaRead(r);
    check("sim-height", rr.ok && qFuzzyCompare(rr.value.toDouble() + 1.0, 13.5),
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Label"));
    const OpcUaResult rr = runOpcUaRead(r);
    check("sim-label", rr.ok && rr.value.toString() == QLatin1String("SIEANS"),
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count"));
    w.insert(QStringLiteral("dataType"), QStringLiteral("UInt32"));
    w.insert(QStringLiteral("value"), 4242);
    const OpcUaResult wr = runOpcUaWrite(w);
    check("sim-write", wr.ok && wr.acknowledged, wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r = w;
    r.remove(QStringLiteral("value"));
    const OpcUaResult rr = runOpcUaRead(r);
    check("sim-readback", rr.ok && rr.value.toInt() == 4242,
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Serial"));
    w.insert(QStringLiteral("dataType"), QStringLiteral("String"));
    w.insert(QStringLiteral("value"), QStringLiteral("nope"));
    const OpcUaResult wr = runOpcUaWrite(w);
    check("sim-serial-ro", !wr.ok, wr.error);
  }
  {
    QVariantMap b;
    b.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    b.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS"));
    const OpcUaResult br = runOpcUaBrowse(b);
    check("sim-browse", br.ok && br.browseCount >= 6,
          br.ok ? QString::number(br.browseCount) : br.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count"));
    w.insert(QStringLiteral("comparison"), QStringLiteral("eq"));
    w.insert(QStringLiteral("expectedValue"), 4242);
    w.insert(QStringLiteral("triggerMode"), QStringLiteral("level"));
    w.insert(QStringLiteral("waitTimeoutMs"), 2000);
    w.insert(QStringLiteral("publishingIntervalMs"), 50);
    const OpcUaResult wr = runOpcUaWait(w);
    check("sim-wait", wr.ok && wr.triggered && wr.value.toInt() == 4242,
          wr.ok ? wr.value.toString() : wr.error);
  }

  QString serr;
  bool started = false;
  for (int p = 4840; p <= 4844 && !started; ++p) {
    QString e;
    if (opcUaSoftServer().start(quint16(p), &e)) started = true;
    else serr = e;
  }
  check("tcp-server", started, serr);
  if (started) {
    const QString ep = opcUaSoftServer().endpoint();
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("server"));
    w.insert(QStringLiteral("endpoint"), ep);
    w.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count"));
    w.insert(QStringLiteral("dataType"), QStringLiteral("UInt32"));
    w.insert(QStringLiteral("value"), 9001);
    w.insert(QStringLiteral("timeoutMs"), 3000);
    const OpcUaResult wr = runOpcUaWrite(w);
    check("tcp-write", wr.ok && wr.acknowledged, wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r = w;
    r.remove(QStringLiteral("value"));
    const OpcUaResult rr = runOpcUaRead(r);
    check("tcp-readback", rr.ok && rr.value.toInt() == 9001,
          rr.ok ? rr.value.toString() : rr.error);
    QVariantMap b;
    b.insert(QStringLiteral("connection"), QStringLiteral("server"));
    b.insert(QStringLiteral("endpoint"), ep);
    b.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS"));
    b.insert(QStringLiteral("timeoutMs"), 3000);
    const OpcUaResult br = runOpcUaBrowse(b);
    check("tcp-browse", br.ok && br.browseCount >= 6,
          br.ok ? QString::number(br.browseCount) : br.error);
    QVariantMap wt;
    wt.insert(QStringLiteral("connection"), QStringLiteral("server"));
    wt.insert(QStringLiteral("endpoint"), ep);
    wt.insert(QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count"));
    wt.insert(QStringLiteral("comparison"), QStringLiteral("eq"));
    wt.insert(QStringLiteral("expectedValue"), 9001);
    wt.insert(QStringLiteral("triggerMode"), QStringLiteral("level"));
    wt.insert(QStringLiteral("waitTimeoutMs"), 3000);
    wt.insert(QStringLiteral("publishingIntervalMs"), 50);
    wt.insert(QStringLiteral("timeoutMs"), 3000);
    const OpcUaResult wtr = runOpcUaWait(wt);
    check("tcp-wait", wtr.ok && wtr.triggered && wtr.value.toInt() == 9001,
          wtr.ok ? wtr.value.toString() : wtr.error);
  }
  return fails;
}

}  // namespace sieans_qt
