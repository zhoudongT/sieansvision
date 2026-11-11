#include "SocketExchange.hpp"
#include "ProtocolNet.hpp"

#include "CommHub.hpp"

#include <QByteArray>
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QHash>
#include <QHostAddress>
#include <QSet>
#ifdef Q_OS_UNIX
#include <sys/socket.h>
#endif
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QObject>
#include <QTcpServer>
#include <QTcpSocket>
#include <QThread>
#include <QUdpSocket>
#include <QtGlobal>

#include <cstring>

namespace sieans_qt {
namespace {

constexpr int kMaxPayload = 65536;
constexpr int kMaxUdpPayload = 65507;

QByteArray delimiterOf(const QString& framing) {
  if (framing == QLatin1String("lf")) return QByteArray("\n", 1);
  if (framing == QLatin1String("crlf")) return QByteArray("\r\n", 2);
  if (framing == QLatin1String("nul")) return QByteArray("\0", 1);
  return {};
}

int prefixSizeOf(const QString& framing) {
  if (framing.startsWith(QLatin1String("length16"))) return 2;
  if (framing.startsWith(QLatin1String("length32"))) return 4;
  return 0;
}

bool prefixLittle(const QString& framing) { return framing.endsWith(QLatin1String("le")); }

quint32 readPrefix(const char* p, int size, bool le) {
  const uchar* u = reinterpret_cast<const uchar*>(p);
  if (size == 2) {
    return le ? (quint32(u[0]) | (quint32(u[1]) << 8))
              : ((quint32(u[0]) << 8) | quint32(u[1]));
  }
  return le ? (quint32(u[0]) | (quint32(u[1]) << 8) | (quint32(u[2]) << 16) | (quint32(u[3]) << 24))
            : ((quint32(u[0]) << 24) | (quint32(u[1]) << 16) | (quint32(u[2]) << 8) | quint32(u[3]));
}

void writePrefix(char* p, int size, bool le, quint32 len) {
  if (size == 2) {
    if (le) {
      p[0] = char(len & 0xff);
      p[1] = char((len >> 8) & 0xff);
    } else {
      p[0] = char((len >> 8) & 0xff);
      p[1] = char(len & 0xff);
    }
    return;
  }
  if (le) {
    p[0] = char(len & 0xff);
    p[1] = char((len >> 8) & 0xff);
    p[2] = char((len >> 16) & 0xff);
    p[3] = char((len >> 24) & 0xff);
  } else {
    p[0] = char((len >> 24) & 0xff);
    p[1] = char((len >> 16) & 0xff);
    p[2] = char((len >> 8) & 0xff);
    p[3] = char(len & 0xff);
  }
}

bool encodePayload(const QVariant& value, const QString& encoding, QByteArray* raw,
                   QString* error) {
  if (encoding == QLatin1String("bytes")) {
    if (value.typeId() == QMetaType::QByteArray) {
      *raw = value.toByteArray();
    } else {
      const QVariantList lst = value.toList();
      raw->clear();
      raw->reserve(lst.size());
      for (const QVariant& v : lst) {
        bool ok = false;
        const int n = v.toInt(&ok);
        if (!ok || n < 0 || n > 255) {
          if (error) *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
          return false;
        }
        raw->append(char(n));
      }
    }
  } else if (encoding == QLatin1String("text")) {
    *raw = value.toString().toUtf8();
  } else if (encoding == QLatin1String("structured")) {
    const QJsonDocument doc = QJsonDocument::fromVariant(value);
    if (doc.isNull() && !value.isNull() && value.isValid() &&
        value.typeId() != QMetaType::Bool && !value.canConvert<double>() &&
        value.typeId() != QMetaType::QString && value.typeId() != QMetaType::QVariantList &&
        value.typeId() != QMetaType::QVariantMap) {
      if (error) *error = QStringLiteral("消息仅支持数值、文本、开关、数组和结构体");
      return false;
    }
    if (value.typeId() == QMetaType::QVariantMap || value.typeId() == QMetaType::QVariantList)
      *raw = doc.toJson(QJsonDocument::Compact);
    else if (value.isNull())
      *raw = QByteArray("null");
    else if (value.typeId() == QMetaType::Bool)
      *raw = value.toBool() ? QByteArray("true") : QByteArray("false");
    else if (value.typeId() == QMetaType::QString)
      *raw = QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);
    else
      *raw = QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);
  } else {
    if (error) *error = QStringLiteral("消息格式无效");
    return false;
  }
  if (raw->size() > kMaxPayload) {
    if (error) *error = QStringLiteral("消息体超过 64 KiB");
    return false;
  }
  return true;
}

bool decodePayload(const QByteArray& raw, const QString& encoding, QVariant* value,
                   QString* error) {
  if (raw.size() > kMaxPayload) {
    if (error) *error = QStringLiteral("收到的消息体超过 64 KiB");
    return false;
  }
  if (encoding == QLatin1String("bytes")) {
    QVariantList lst;
    lst.reserve(raw.size());
    for (unsigned char b : raw) lst.append(int(b));
    *value = lst;
    return true;
  }
  QString text = QString::fromUtf8(raw);
  // fromUtf8 replaces invalid sequences with U+FFFD — reject if replacement appears
  // and the raw was not already valid.
  if (text.contains(QChar::ReplacementCharacter)) {
    const QByteArray round = text.toUtf8();
    if (round != raw) {
      if (error) *error = QStringLiteral("消息不是有效 UTF-8 文本，请选择字节数组");
      return false;
    }
  }
  if (encoding == QLatin1String("text")) {
    *value = text;
    return true;
  }
  if (encoding == QLatin1String("structured")) {
    QJsonParseError pe;
    const QJsonDocument doc = QJsonDocument::fromJson(raw, &pe);
    if (pe.error == QJsonParseError::NoError) {
      *value = doc.toVariant();
      return true;
    }
    // QJsonDocument 只接受对象/数组；裸值 (null/bool/number/string) 包一层再解。
    QJsonParseError pe2;
    const QJsonDocument wrapped =
        QJsonDocument::fromJson(QByteArray("[") + raw + ']', &pe2);
    if (pe2.error == QJsonParseError::NoError && wrapped.isArray() &&
        wrapped.array().size() == 1) {
      *value = wrapped.array().at(0).toVariant();
      return true;
    }
    if (error) *error = QStringLiteral("消息不是有效的结构化数据，请检查发送格式或选择文本");
    return false;
  }
  if (error) *error = QStringLiteral("消息格式无效");
  return false;
}

QByteArray framePayload(const QByteArray& payload, const QString& framing, QString* error) {
  const QByteArray del = delimiterOf(framing);
  if (!del.isEmpty()) {
    if (payload.indexOf(del) >= 0) {
      if (error) *error = QStringLiteral("发送内容包含所选结束符，请改用长度前缀或字节协议");
      return {};
    }
    return payload + del;
  }
  const int psz = prefixSizeOf(framing);
  if (psz > 0) {
    if (psz == 2 && payload.size() > 65535) {
      if (error) *error = QStringLiteral("两字节长度前缀最大支持 65535 字节");
      return {};
    }
    QByteArray header(psz, 0);
    writePrefix(header.data(), psz, prefixLittle(framing), quint32(payload.size()));
    return header + payload;
  }
  return payload;  // raw
}

struct FrameParse {
  bool complete = false;
  bool error = false;
  QString err;
  QByteArray payload;
  int trailingBytes = 0;
};

FrameParse tryParse(const QByteArray& buffer, const QString& rxFraming, int maxBytes,
                    int responseBytes, bool ended) {
  FrameParse out;
  int offset = 0;
  int length = -1;
  int wireLength = -1;
  const QByteArray del = delimiterOf(rxFraming);
  const int psz = prefixSizeOf(rxFraming);
  if (!del.isEmpty()) {
    const int at = buffer.indexOf(del);
    if (at >= 0) {
      length = at;
      wireLength = at + del.size();
    } else if (buffer.size() > maxBytes + del.size() - 1) {
      out.error = true;
      out.err = QStringLiteral("接收数据超过字节上限");
      return out;
    }
  } else if (psz > 0) {
    if (buffer.size() >= psz) {
      offset = psz;
      length = int(readPrefix(buffer.constData(), psz, prefixLittle(rxFraming)));
      if (length > maxBytes) {
        out.error = true;
        out.err = QStringLiteral("长度前缀超过接收字节上限");
        return out;
      }
      wireLength = psz + length;
    }
  } else if (rxFraming == QLatin1String("fixed")) {
    length = responseBytes;
    wireLength = length;
  } else {  // eof
    if (buffer.size() > maxBytes) {
      out.error = true;
      out.err = QStringLiteral("接收数据超过字节上限");
      return out;
    }
    if (ended) {
      length = buffer.size();
      wireLength = length;
    }
  }
  if (length >= 0 && length > maxBytes) {
    out.error = true;
    out.err = QStringLiteral("接收数据超过字节上限");
    return out;
  }
  if (wireLength >= 0 && buffer.size() >= wireLength) {
    out.complete = true;
    out.payload = buffer.mid(offset, length);
    out.trailingBytes = buffer.size() - wireLength;
    return out;
  }
  if (ended) {
    out.error = true;
    out.err = QStringLiteral("对端关闭连接，但未收到完整报文");
  }
  return out;
}

bool cancelled(std::atomic<bool>* cancel) { return cancel && cancel->load(); }

bool waitSlice(int ms, std::atomic<bool>* cancel) {
  if (cancelled(cancel)) return false;
  if (ms <= 0) return true;
  const int slice = qMin(ms, 20);
  QElapsedTimer t;
  t.start();
  while (t.elapsed() < slice) {
    if (cancelled(cancel)) return false;
    if (QCoreApplication::instance())
      QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
    QThread::msleep(1);
  }
  return !cancelled(cancel);
}

/** 进程内 TCP/UDP 原样回显，绑定 127.0.0.1 动态端口，避开 CommHub :19956。 */
class SoftSocketEcho : public QObject {
 public:
  bool ensureStarted(QString* error) {
    if (running_) return true;
    tcp_ = new QTcpServer(this);
    connect(tcp_, &QTcpServer::newConnection, this, [this]() {
      while (tcp_->hasPendingConnections()) {
        QTcpSocket* s = tcp_->nextPendingConnection();
        if (!s) break;
        clients_.insert(s);
        connect(s, &QTcpSocket::readyRead, this, [this, s]() {
          const QByteArray data = s->readAll();
          receivedBytes_ += data.size();
          if (!data.isEmpty()) {
            s->write(data);
            s->flush();
          }
        });
        // 对端半关闭写端（rxFraming=eof）时回完数据后关闭，以便客户端读到结束。
        connect(s, &QTcpSocket::readChannelFinished, this, [s]() {
          s->flush();
          s->disconnectFromHost();
        });
        connect(s, &QTcpSocket::disconnected, this, [this, s]() {
          clients_.remove(s);
          s->deleteLater();
        });
        connect(s, &QTcpSocket::errorOccurred, this, [s](QAbstractSocket::SocketError) {
          Q_UNUSED(s);
        });
      }
    });
    if (!tcp_->listen(QHostAddress::LocalHost, 0)) {
      if (error)
        *error = QStringLiteral("TCP 回显模拟器启动失败：%1").arg(tcp_->errorString());
      delete tcp_;
      tcp_ = nullptr;
      return false;
    }
    udp_ = new QUdpSocket(this);
    if (!udp_->bind(QHostAddress::LocalHost, 0, QUdpSocket::ShareAddress | QUdpSocket::ReuseAddressHint) &&
        !udp_->bind(QHostAddress::LocalHost, 0)) {
      if (error)
        *error = QStringLiteral("UDP 回显模拟器启动失败：%1").arg(udp_->errorString());
      tcp_->close();
      delete tcp_;
      tcp_ = nullptr;
      delete udp_;
      udp_ = nullptr;
      return false;
    }
    connect(udp_, &QUdpSocket::readyRead, this, [this]() {
      while (udp_->hasPendingDatagrams()) {
        QByteArray data;
        data.resize(int(udp_->pendingDatagramSize()));
        QHostAddress from;
        quint16 port = 0;
        udp_->readDatagram(data.data(), data.size(), &from, &port);
        receivedBytes_ += data.size();
        udp_->writeDatagram(data, from, port);
      }
    });
    running_ = true;
    return true;
  }

  QString host() const { return QStringLiteral("127.0.0.1"); }
  quint16 tcpPort() const { return tcp_ ? tcp_->serverPort() : 0; }
  quint16 udpPort() const { return udp_ ? udp_->localPort() : 0; }

 private:
  QTcpServer* tcp_ = nullptr;
  QUdpSocket* udp_ = nullptr;
  QSet<QTcpSocket*> clients_;
  qint64 receivedBytes_ = 0;
  bool running_ = false;
};

SoftSocketEcho& softEcho() {
  static SoftSocketEcho inst;
  return inst;
}

int intParam(const QVariantMap& p, const QString& key, int def, int lo, int hi, QString* err,
             const QString& label) {
  const QVariant v = p.contains(key) ? p.value(key) : QVariant(def);
  bool ok = false;
  const int n = v.toInt(&ok);
  if (!ok || n < lo || n > hi) {
    if (err) *err = label + QStringLiteral("必须为 %1–%2 的整数").arg(lo).arg(hi);
    return def;
  }
  return n;
}

SocketXferResult fail(const QString& protocol, const QString& error, bool sent) {
  SocketXferResult r;
  r.protocol = protocol;
  r.error = error;
  if (sent) r.error += QStringLiteral("；数据可能已经发出，不能回滚，未自动重试");
  r.note = r.error;
  return r;
}

SocketXferResult runExchange(bool udp, const QVariantMap& params, std::atomic<bool>* cancel) {
  const QString protocol = udp ? QStringLiteral("UDP") : QStringLiteral("TCP");
  const QElapsedTimer clock;
  const_cast<QElapsedTimer&>(clock).start();
  QElapsedTimer started;
  started.start();

  auto finishElapsed = [&](SocketXferResult r) {
    r.elapsedMs = int(started.elapsed());
    return r;
  };

  if (cancelled(cancel)) return finishElapsed(fail(protocol, QStringLiteral("网络通信已取消"), false));

  const QString mode =
      params.value(QStringLiteral("mode"), QStringLiteral("exchange")).toString().trimmed();
  if (mode != QLatin1String("exchange") && mode != QLatin1String("send") &&
      mode != QLatin1String("receive"))
    return finishElapsed(fail(protocol, QStringLiteral("通信方式无效"), false));
  const QString connection =
      params.value(QStringLiteral("connection"), QStringLiteral("simulator"))
          .toString()
          .trimmed();
  const bool simulated = (connection == QLatin1String("simulator"));
  if (connection != QLatin1String("simulator") && connection != QLatin1String("device"))
    return finishElapsed(fail(protocol, QStringLiteral("连接方式无效"), false));
  const QString encoding =
      params.value(QStringLiteral("encoding"), QStringLiteral("text")).toString().trimmed();
  if (encoding != QLatin1String("text") && encoding != QLatin1String("structured") &&
      encoding != QLatin1String("bytes"))
    return finishElapsed(fail(protocol, QStringLiteral("消息格式无效"), false));

  QString err;
  const int timeoutMs =
      intParam(params, QStringLiteral("timeoutMs"), 3000, 100, 60000, &err, QStringLiteral("总超时"));
  if (!err.isEmpty()) return finishElapsed(fail(protocol, err, false));
  const int maxBytes =
      intParam(params, QStringLiteral("maxBytes"), kMaxPayload, 1, kMaxPayload, &err,
               QStringLiteral("接收字节上限"));
  if (!err.isEmpty()) return finishElapsed(fail(protocol, err, false));

  const bool doSend = (mode != QLatin1String("receive"));
  const bool doRecv = (mode != QLatin1String("send"));
  if (simulated && mode == QLatin1String("receive"))
    return finishElapsed(
        fail(protocol, QStringLiteral("回显模拟器需要先发送，请选择请求应答或仅发送"), false));

  QString host = params.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString().trimmed();
  int port = intParam(params, QStringLiteral("port"), 9000, 1, 65535, &err, QStringLiteral("远端端口"));
  if (!simulated && !err.isEmpty()) return finishElapsed(fail(protocol, err, false));
  err.clear();
  int localPort = 0;
  QString localAddress;
  if (udp && !simulated) {
    const int lo = (mode == QLatin1String("receive")) ? 1 : 0;
    localPort = intParam(params, QStringLiteral("localPort"), 0, lo, 65535, &err,
                         QStringLiteral("本地 UDP 端口"));
    if (!err.isEmpty()) return finishElapsed(fail(protocol, err, false));
    localAddress = params.value(QStringLiteral("localAddress")).toString().trimmed();
  }

  if (simulated) {
    if (!softEcho().ensureStarted(&err)) return finishElapsed(fail(protocol, err, false));
    host = softEcho().host();
    port = udp ? int(softEcho().udpPort()) : int(softEcho().tcpPort());
  }
  if (host.isEmpty() || host.size() > 253)
    return finishElapsed(fail(protocol, QStringLiteral("远端主机名或 IP 无效"), false));

  QByteArray payload, wire;
  if (doSend) {
    QVariant value = params.contains(QStringLiteral("value")) ? params.value(QStringLiteral("value"))
                                                              : QVariant(QString());
    if (value.typeId() == QMetaType::QString)
      value = CommHub::expandTemplate(value.toString(), QVariantMap{});  // expanded by caller usually
    if (!encodePayload(value, encoding, &payload, &err))
      return finishElapsed(fail(protocol, err, false));
    if (udp && payload.size() > kMaxUdpPayload)
      return finishElapsed(fail(protocol, QStringLiteral("UDP 报文超过 65507 字节"), false));
    if (!udp) {
      const QString tx = params.value(QStringLiteral("txFraming"), QStringLiteral("crlf"))
                             .toString()
                             .trimmed();
      wire = framePayload(payload, tx, &err);
      if (!err.isEmpty()) return finishElapsed(fail(protocol, err, false));
    } else {
      wire = payload;
    }
  }

  QString rxFraming = QStringLiteral("crlf");
  int responseBytes = 1;
  if (doRecv && !udp) {
    rxFraming = params.value(QStringLiteral("rxFraming"), QStringLiteral("crlf")).toString().trimmed();
    const QStringList okRx = {QStringLiteral("lf"),         QStringLiteral("crlf"),
                              QStringLiteral("nul"),        QStringLiteral("length16be"),
                              QStringLiteral("length16le"), QStringLiteral("length32be"),
                              QStringLiteral("length32le"), QStringLiteral("fixed"),
                              QStringLiteral("eof")};
    if (!okRx.contains(rxFraming))
      return finishElapsed(fail(protocol, QStringLiteral("接收分帧方式无效"), false));
    if (rxFraming == QLatin1String("fixed")) {
      responseBytes = intParam(params, QStringLiteral("responseBytes"), 1, 1, maxBytes, &err,
                               QStringLiteral("定长报文字节数"));
      if (!err.isEmpty()) return finishElapsed(fail(protocol, err, false));
    }
  }

  bool sent = false;

  if (udp) {
    QUdpSocket sock;
    QHostAddress bindAddr = localAddress.isEmpty() ? QHostAddress::AnyIPv4
                                                   : QHostAddress(localAddress);
    if (!localAddress.isEmpty() && bindAddr.isNull())
      return finishElapsed(fail(protocol, QStringLiteral("本地地址必须是 IP 或留空"), false));
    if (!sock.bind(bindAddr, quint16(localPort)))
      return finishElapsed(
          fail(protocol, QStringLiteral("UDP 通信失败：%1").arg(sock.errorString()), false));
    const QHostAddress peer(host);
    const QHostAddress peerNorm = peer.isNull() ? QHostAddress(host) : peer;
    if (doSend) {
      const qint64 n = sock.writeDatagram(wire, QHostAddress(host), quint16(port));
      sent = n >= 0;
      if (!sent)
        return finishElapsed(
            fail(protocol, QStringLiteral("UDP 通信失败：%1").arg(sock.errorString()), false));
      if (!doRecv) {
        SocketXferResult r;
        r.ok = true;
        r.protocol = protocol;
        r.mode = mode;
        r.encoding = encoding;
        r.host = host;
        r.port = port;
        r.localPort = int(sock.localPort());
        r.simulated = simulated;
        r.delivery = QStringLiteral("sent");
        r.acknowledged = false;
        r.value = params.value(QStringLiteral("value"));
        r.byteLength = payload.size();
        r.sentBytes = wire.size();
        r.note = QStringLiteral("UDP sent %1 B → %2:%3").arg(r.sentBytes).arg(host).arg(port);
        return finishElapsed(r);
      }
    }
    const int remain0 = timeoutMs - int(started.elapsed());
    QByteArray recvd;
    QHostAddress from;
    quint16 fromPort = 0;
    bool got = false;
    while (int(started.elapsed()) < timeoutMs) {
      if (cancelled(cancel))
        return finishElapsed(fail(protocol, QStringLiteral("网络通信已取消"), sent));
      const int left = timeoutMs - int(started.elapsed());
      if (sock.waitForReadyRead(qMin(20, qMax(1, left)))) {
        while (sock.hasPendingDatagrams()) {
          QByteArray data;
          data.resize(int(sock.pendingDatagramSize()));
          sock.readDatagram(data.data(), data.size(), &from, &fromPort);
          const QHostAddress fromV4 = from.toIPv4Address() ? QHostAddress(from.toIPv4Address()) : from;
          const QHostAddress wantV4 =
              QHostAddress(host).toIPv4Address() ? QHostAddress(QHostAddress(host).toIPv4Address())
                                                  : QHostAddress(host);
          if (fromV4 != wantV4 && from.toString() != host &&
              fromV4.toString() != wantV4.toString())
            continue;  // wrong source
          if (fromPort != quint16(port)) continue;
          if (data.size() > maxBytes)
            return finishElapsed(fail(protocol, QStringLiteral("UDP 报文超过接收字节上限"), sent));
          recvd = data;
          got = true;
          break;
        }
        if (got) break;
      }
      if (QCoreApplication::instance())
        QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
    }
    if (!got) {
      if (cancelled(cancel))
        return finishElapsed(fail(protocol, QStringLiteral("网络通信已取消"), sent));
      return finishElapsed(fail(protocol, QStringLiteral("网络通信总超时"), sent));
    }
    QVariant decoded;
    if (!decodePayload(recvd, encoding, &decoded, &err))
      return finishElapsed(fail(protocol, err, sent));
    SocketXferResult r;
    r.ok = true;
    r.protocol = protocol;
    r.mode = mode;
    r.encoding = encoding;
    r.host = host;
    r.port = port;
    r.localPort = int(sock.localPort());
    r.simulated = simulated;
    r.delivery = QStringLiteral("received");
    r.acknowledged = false;
    r.value = decoded;
    r.byteLength = recvd.size();
    r.sentBytes = doSend ? wire.size() : 0;
    r.note = QStringLiteral("UDP received %1 B from %2:%3").arg(r.byteLength).arg(host).arg(port);
    Q_UNUSED(remain0);
    return finishElapsed(r);
  }

  // TCP
  QTcpSocket sock;
  sock.setSocketOption(QAbstractSocket::LowDelayOption, 1);
  sock.connectToHost(host, quint16(port));
  bool connected = false;
  while (int(started.elapsed()) < timeoutMs) {
    if (cancelled(cancel))
      return finishElapsed(fail(protocol, QStringLiteral("网络通信已取消"), false));
    const int left = timeoutMs - int(started.elapsed());
    if (sock.waitForConnected(qMin(20, qMax(1, left)))) {
      connected = true;
      break;
    }
    if (sock.state() == QAbstractSocket::UnconnectedState &&
        sock.error() != QAbstractSocket::SocketTimeoutError &&
        sock.error() != QAbstractSocket::UnknownSocketError) {
      const QString raw = sock.errorString();
      const QString msg =
          (sock.error() == QAbstractSocket::ConnectionRefusedError)
              ? QStringLiteral("TCP 连接被拒绝 (%1:%2)").arg(host).arg(port)
              : (sock.error() == QAbstractSocket::NetworkError ||
                 sock.error() == QAbstractSocket::RemoteHostClosedError)
                    ? QStringLiteral("TCP 连接已断开 (%1:%2): %3").arg(host).arg(port).arg(raw)
                    : QStringLiteral("TCP 通信失败：%1").arg(raw);
      return finishElapsed(fail(protocol, msg, false));
    }
    if (QCoreApplication::instance())
      QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
  }
  if (!connected)
    return finishElapsed(fail(protocol, QStringLiteral("TCP 连接超时 (%1:%2, %3ms)").arg(host).arg(port).arg(timeoutMs), false));

  if (doSend) {
    const qint64 n = sock.write(wire);
    if (n < 0)
      return finishElapsed(
          fail(protocol, QStringLiteral("TCP 通信失败：%1").arg(sock.errorString()), false));
    // 先把请求刷出。eof 分帧时再半关闭写端（POSIX SHUT_WR），等对端关连接结束报文。
    // 不可在刷写前 disconnectFromHost，否则尚未回显就会把本端当成已结束。
    sock.waitForBytesWritten(qMin(500, qMax(1, timeoutMs - int(started.elapsed()))));
    sent = true;
    if (rxFraming == QLatin1String("eof") && doRecv) {
#ifdef Q_OS_UNIX
      const qintptr fd = sock.socketDescriptor();
      if (fd >= 0)
        ::shutdown(int(fd), SHUT_WR);
      else
        sock.disconnectFromHost();
#else
      sock.disconnectFromHost();
#endif
    }
    if (!doRecv) {
      sock.disconnectFromHost();
      SocketXferResult r;
      r.ok = true;
      r.protocol = protocol;
      r.mode = mode;
      r.encoding = encoding;
      r.host = host;
      r.port = port;
      r.localPort = int(sock.localPort());
      r.simulated = simulated;
      r.delivery = QStringLiteral("sent");
      r.acknowledged = false;
      r.value = params.value(QStringLiteral("value"));
      r.byteLength = payload.size();
      r.sentBytes = wire.size();
      r.note = QStringLiteral("TCP sent %1 B → %2:%3").arg(r.sentBytes).arg(host).arg(port);
      return finishElapsed(r);
    }
  }

  QByteArray buffer;
  FrameParse frame;
  bool ended = false;
  while (int(started.elapsed()) < timeoutMs) {
    if (cancelled(cancel))
      return finishElapsed(fail(protocol, QStringLiteral("网络通信已取消"), sent));
    if (sock.bytesAvailable() > 0) {
      buffer += sock.readAll();
      frame = tryParse(buffer, rxFraming, maxBytes, responseBytes, false);
      if (frame.error) return finishElapsed(fail(protocol, frame.err, sent));
      if (frame.complete) break;
    }
    if (sock.state() != QAbstractSocket::ConnectedState &&
        sock.state() != QAbstractSocket::ClosingState) {
      ended = true;
      if (sock.bytesAvailable() > 0) buffer += sock.readAll();
      frame = tryParse(buffer, rxFraming, maxBytes, responseBytes, true);
      if (frame.error) return finishElapsed(fail(protocol, frame.err, sent));
      if (frame.complete) break;
      return finishElapsed(fail(protocol, QStringLiteral("TCP 连接在报文完成前关闭"), sent));
    }
    const int left = timeoutMs - int(started.elapsed());
    sock.waitForReadyRead(qMin(20, qMax(1, left)));
    if (QCoreApplication::instance())
      QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
  }
  if (!frame.complete) {
    if (cancelled(cancel))
      return finishElapsed(fail(protocol, QStringLiteral("网络通信已取消"), sent));
    // try eof if peer already closed
    if (ended || sock.state() != QAbstractSocket::ConnectedState) {
      if (sock.bytesAvailable() > 0) buffer += sock.readAll();
      frame = tryParse(buffer, rxFraming, maxBytes, responseBytes, true);
    }
    if (!frame.complete)
      return finishElapsed(fail(protocol, frame.error ? frame.err : QStringLiteral("网络通信总超时"),
                                sent));
  }
  sock.disconnectFromHost();
  QVariant decoded;
  if (!decodePayload(frame.payload, encoding, &decoded, &err))
    return finishElapsed(fail(protocol, err, sent));
  SocketXferResult r;
  r.ok = true;
  r.protocol = protocol;
  r.mode = mode;
  r.encoding = encoding;
  r.host = host;
  r.port = port;
  r.localPort = int(sock.localPort());
  r.simulated = simulated;
  r.delivery = QStringLiteral("received");
  r.acknowledged = false;
  r.value = decoded;
  r.byteLength = frame.payload.size();
  r.sentBytes = doSend ? wire.size() : 0;
  r.trailingBytes = frame.trailingBytes;
  r.note = QStringLiteral("TCP received %1 B trailing=%2")
               .arg(r.byteLength)
               .arg(r.trailingBytes);
  Q_UNUSED(waitSlice);
  return finishElapsed(r);
}

}  // namespace

SocketXferResult runTcpExchange(const QVariantMap& params, std::atomic<bool>* cancel) {
  return runExchange(false, params, cancel);
}

SocketXferResult runUdpExchange(const QVariantMap& params, std::atomic<bool>* cancel) {
  return runExchange(true, params, cancel);
}

QStringList socketExchangeSelfTest() {
  QStringList fails;
  auto check = [&](bool cond, const QString& msg) {
    if (!cond) fails << msg;
  };

  const QStringList framings = {QStringLiteral("lf"),         QStringLiteral("crlf"),
                                QStringLiteral("nul"),        QStringLiteral("length16be"),
                                QStringLiteral("length16le"), QStringLiteral("length32be"),
                                QStringLiteral("length32le")};
  for (const QString& fr : framings) {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("mode"), QStringLiteral("exchange")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("工件 OK")},
         {QStringLiteral("txFraming"), fr},
         {QStringLiteral("rxFraming"), fr},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("tcp %1 not ok: %2").arg(fr, r.error));
    check(r.simulated, QStringLiteral("tcp %1 not simulated").arg(fr));
    check(r.delivery == QLatin1String("received"), QStringLiteral("tcp %1 delivery").arg(fr));
    check(!r.acknowledged, QStringLiteral("tcp %1 ack").arg(fr));
    check(r.value.toString() == QStringLiteral("工件 OK"),
          QStringLiteral("tcp %1 value %2").arg(fr, r.value.toString()));
  }

  {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("structured")},
         {QStringLiteral("value"), QVariantMap{{QStringLiteral("count"), 3},
                                               {QStringLiteral("passed"), true}}},
         {QStringLiteral("txFraming"), QStringLiteral("length16be")},
         {QStringLiteral("rxFraming"), QStringLiteral("length16be")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("tcp structured: %1").arg(r.error));
    const QVariantMap m = r.value.toMap();
    check(m.value(QStringLiteral("count")).toInt() == 3, QStringLiteral("tcp structured count"));
    check(m.value(QStringLiteral("passed")).toBool(), QStringLiteral("tcp structured passed"));
  }

  {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("bytes")},
         {QStringLiteral("value"), QVariantList{128, 255, 1}},
         {QStringLiteral("txFraming"), QStringLiteral("length32le")},
         {QStringLiteral("rxFraming"), QStringLiteral("length32le")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("tcp bytes: %1").arg(r.error));
    const QVariantList lst = r.value.toList();
    check(lst.size() == 3 && lst[1].toInt() == 255, QStringLiteral("tcp bytes value"));
  }

  {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("end")},
         {QStringLiteral("txFraming"), QStringLiteral("raw")},
         {QStringLiteral("rxFraming"), QStringLiteral("eof")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("tcp eof: %1").arg(r.error));
    check(r.value.toString() == QStringLiteral("end"),
          QStringLiteral("tcp eof value [%1] ok=%2 %3")
              .arg(r.value.toString())
              .arg(r.ok)
              .arg(r.error));
  }

  {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("ABCD")},
         {QStringLiteral("txFraming"), QStringLiteral("raw")},
         {QStringLiteral("rxFraming"), QStringLiteral("fixed")},
         {QStringLiteral("responseBytes"), 4},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("tcp fixed: %1").arg(r.error));
    check(r.value.toString() == QLatin1String("ABCD"), QStringLiteral("tcp fixed value"));
  }

  {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("mode"), QStringLiteral("send")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("ABC")},
         {QStringLiteral("txFraming"), QStringLiteral("crlf")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("tcp send: %1").arg(r.error));
    check(r.delivery == QLatin1String("sent"), QStringLiteral("tcp send delivery"));
    check(!r.acknowledged, QStringLiteral("tcp send ack"));
  }

  {
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("a\r\nb")},
         {QStringLiteral("txFraming"), QStringLiteral("crlf")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(!r.ok, QStringLiteral("tcp delimiter should fail"));
  }

  {
    const SocketXferResult r = runUdpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("中文\n")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("udp text: %1").arg(r.error));
    check(r.delivery == QLatin1String("received"), QStringLiteral("udp delivery"));
    check(r.value.toString() == QStringLiteral("中文\n"),
          QStringLiteral("udp value %1").arg(r.value.toString()));
    check(r.simulated, QStringLiteral("udp not simulated"));
  }

  {
    const SocketXferResult r = runUdpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("structured")},
         {QStringLiteral("value"), QVariant() /* null */},
         {QStringLiteral("timeoutMs"), 2000}});
    // QVariant() is null → JSON null
    check(r.ok, QStringLiteral("udp structured null: %1").arg(r.error));
  }

  {
    const SocketXferResult r = runUdpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("bytes")},
         {QStringLiteral("value"), QVariantList{0, 255, 128}},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("udp bytes: %1").arg(r.error));
    const QVariantList lst = r.value.toList();
    check(lst.size() == 3 && lst[1].toInt() == 255, QStringLiteral("udp bytes value"));
  }

  {
    const SocketXferResult r = runUdpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("mode"), QStringLiteral("send")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("ABC")},
         {QStringLiteral("timeoutMs"), 2000}});
    check(r.ok, QStringLiteral("udp send: %1").arg(r.error));
    check(r.delivery == QLatin1String("sent"), QStringLiteral("udp send delivery"));
  }

  {
    std::atomic<bool> cancel{true};
    const SocketXferResult r = runTcpExchange(
        {{QStringLiteral("connection"), QStringLiteral("simulator")},
         {QStringLiteral("encoding"), QStringLiteral("text")},
         {QStringLiteral("value"), QStringLiteral("X")},
         {QStringLiteral("timeoutMs"), 2000}},
        &cancel);
    check(!r.ok && r.error.contains(QStringLiteral("取消")),
          QStringLiteral("tcp cancel: %1").arg(r.error));
  }

  return fails;
}

}  // namespace sieans_qt
