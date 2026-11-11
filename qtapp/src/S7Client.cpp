#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "S7Client.hpp"
#include "ProtocolNet.hpp"

#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QtEndian>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <thread>

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

namespace sieans_qt {
namespace {

constexpr int kDbSize = 4096;
constexpr int kAreaSize = 1024;
constexpr int kMaxPayload = 200;

QMutex gStoreMutex;
QHash<int, QByteArray> gDbs;
QByteArray gMk;
QByteArray gPe;
QByteArray gPa;
bool gStoreInit = false;

QMutex gServerMutex;
S7SoftServer* gServer = nullptr;
int gListenFd = -1;
quint16 gListenPort = 0;
bool gServerRun = false;

/** 按 Python 模拟器初始化 DB1（DBW0=123，DBD4=12.5）以及 M/I/Q 映像。 */
void ensureStore() {
  if (gStoreInit) return;
  QByteArray db(kDbSize, 0);
  qToBigEndian(quint16(123), db.data());
  const float f = 12.5f;
  quint32 u = 0;
  std::memcpy(&u, &f, 4);
  qToBigEndian(u, db.data() + 4);
  gDbs.insert(1, db);
  gMk = QByteArray(kAreaSize, 0);
  gPe = QByteArray(kAreaSize, 0);
  gPa = QByteArray(kAreaSize, 0);
  gStoreInit = true;
}

QByteArray* areaMemory(const QString& area, int db, QString* error) {
  ensureStore();
  if (area == QLatin1String("db")) {
    if (db < 1 || db > 65535) {
      *error = QStringLiteral("数据块编号无效");
      return nullptr;
    }
    if (!gDbs.contains(db)) gDbs.insert(db, QByteArray(kDbSize, 0));
    return &gDbs[db];
  }
  if (area == QLatin1String("mk")) return &gMk;
  if (area == QLatin1String("pe")) return &gPe;
  if (area == QLatin1String("pa")) return &gPa;
  *error = QStringLiteral("S7 数据区仅支持 DB、M、I、Q");
  return nullptr;
}

quint8 areaCode(const QString& area) {
  if (area == QLatin1String("pe")) return 0x81;
  if (area == QLatin1String("pa")) return 0x82;
  if (area == QLatin1String("mk")) return 0x83;
  return 0x84;
}

QString areaFromCode(quint8 code) {
  if (code == 0x81) return QStringLiteral("pe");
  if (code == 0x82) return QStringLiteral("pa");
  if (code == 0x83) return QStringLiteral("mk");
  if (code == 0x84) return QStringLiteral("db");
  return QString();
}

int typeWidth(const QString& dtype) {
  if (dtype == QLatin1String("bool") || dtype == QLatin1String("uint8") ||
      dtype == QLatin1String("int8"))
    return 1;
  if (dtype == QLatin1String("uint16") || dtype == QLatin1String("int16")) return 2;
  if (dtype == QLatin1String("uint32") || dtype == QLatin1String("int32") ||
      dtype == QLatin1String("float32"))
    return 4;
  if (dtype == QLatin1String("float64")) return 8;
  return 0;
}

bool encodeValues(const QVariantList& values, const QString& dtype, QByteArray* raw,
                  QString* error) {
  raw->clear();
  for (const QVariant& v : values) {
    if (dtype == QLatin1String("bool")) {
      if (v.typeId() != QMetaType::Bool && v.toString() != QLatin1String("true") &&
          v.toString() != QLatin1String("false") && v.toString() != QLatin1String("1") &&
          v.toString() != QLatin1String("0")) {
        *error = QStringLiteral("BOOL 写入必须使用开关类型");
        return false;
      }
      raw->append(char(v.toBool() || v.toInt() != 0 ? 1 : 0));
      continue;
    }
    if (v.typeId() == QMetaType::Bool) {
      *error = QStringLiteral("S7 写入必须为有限数值");
      return false;
    }
    QByteArray part;
    if (dtype == QLatin1String("uint8")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < 0 || n > 255) {
        *error = QStringLiteral("写入值超出 uint8 范围");
        return false;
      }
      part.append(char(n));
    } else if (dtype == QLatin1String("int8")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < -128 || n > 127) {
        *error = QStringLiteral("写入值超出 int8 范围");
        return false;
      }
      part.append(char(qint8(n)));
    } else if (dtype == QLatin1String("uint16")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < 0 || n > 65535) {
        *error = QStringLiteral("写入值超出 uint16 范围");
        return false;
      }
      part.resize(2);
      qToBigEndian(quint16(n), part.data());
    } else if (dtype == QLatin1String("int16")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < -32768 || n > 32767) {
        *error = QStringLiteral("写入值超出 int16 范围");
        return false;
      }
      part.resize(2);
      qToBigEndian(qint16(n), part.data());
    } else if (dtype == QLatin1String("uint32")) {
      bool ok = false;
      const qlonglong n = v.toLongLong(&ok);
      if (!ok || n < 0 || quint64(n) > 0xffffffffull) {
        *error = QStringLiteral("写入值超出 uint32 范围");
        return false;
      }
      part.resize(4);
      qToBigEndian(quint32(n), part.data());
    } else if (dtype == QLatin1String("int32")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < -2147483648ll || n > 2147483647ll) {
        *error = QStringLiteral("写入值超出 int32 范围");
        return false;
      }
      part.resize(4);
      qToBigEndian(qint32(n), part.data());
    } else if (dtype == QLatin1String("float32")) {
      bool ok = false;
      const float f = v.toFloat(&ok);
      if (!ok || !std::isfinite(f)) {
        *error = QStringLiteral("S7 写入必须为有限数值");
        return false;
      }
      quint32 u = 0;
      std::memcpy(&u, &f, 4);
      part.resize(4);
      qToBigEndian(u, part.data());
    } else if (dtype == QLatin1String("float64")) {
      bool ok = false;
      const double d = v.toDouble(&ok);
      if (!ok || !std::isfinite(d)) {
        *error = QStringLiteral("S7 写入必须为有限数值");
        return false;
      }
      quint64 u = 0;
      std::memcpy(&u, &d, 8);
      part.resize(8);
      qToBigEndian(u, part.data());
    } else {
      *error = QStringLiteral("S7 数据类型无效");
      return false;
    }
    raw->append(part);
  }
  return true;
}

bool decodeRaw(const QByteArray& raw, const QString& dtype, int count, QVariantList* values,
               QString* error) {
  const int w = typeWidth(dtype);
  if (w <= 0 || raw.size() != count * w) {
    *error = QStringLiteral("S7 返回字节数量不匹配");
    return false;
  }
  values->clear();
  if (dtype == QLatin1String("bool")) {
    if (raw.size() != 1 || (quint8(raw[0]) != 0 && quint8(raw[0]) != 1)) {
      *error = QStringLiteral("S7 返回的位值无效");
      return false;
    }
    values->push_back(bool(quint8(raw[0])));
    return true;
  }
  const char* p = raw.constData();
  for (int i = 0; i < count; ++i) {
    const char* b = p + i * w;
    if (dtype == QLatin1String("uint8"))
      values->push_back(int(quint8(*b)));
    else if (dtype == QLatin1String("int8"))
      values->push_back(int(qint8(*b)));
    else if (dtype == QLatin1String("uint16"))
      values->push_back(int(qFromBigEndian<quint16>(b)));
    else if (dtype == QLatin1String("int16"))
      values->push_back(int(qFromBigEndian<qint16>(b)));
    else if (dtype == QLatin1String("uint32"))
      values->push_back(qulonglong(qFromBigEndian<quint32>(b)));
    else if (dtype == QLatin1String("int32"))
      values->push_back(qlonglong(qFromBigEndian<qint32>(b)));
    else if (dtype == QLatin1String("float32")) {
      const quint32 u = qFromBigEndian<quint32>(b);
      float f = 0;
      std::memcpy(&f, &u, 4);
      if (!std::isfinite(f)) {
        *error = QStringLiteral("设备返回非有限数值，请检查地址和类型");
        return false;
      }
      values->push_back(double(f));
    } else if (dtype == QLatin1String("float64")) {
      const quint64 u = qFromBigEndian<quint64>(b);
      double d = 0;
      std::memcpy(&d, &u, 8);
      if (!std::isfinite(d)) {
        *error = QStringLiteral("设备返回非有限数值，请检查地址和类型");
        return false;
      }
      values->push_back(d);
    }
  }
  return true;
}

struct Prepared {
  QString connection;
  QString host;
  QString area;
  QString dtype;
  int port = 102;
  int rack = 0;
  int slot = 1;
  int db = 1;
  int offset = 0;
  int bit = 0;
  int timeoutMs = 3000;
  int count = 1;
  int size = 1;
  bool writing = false;
  QVariantList values;
  QByteArray raw;
};

bool prepareCommon(const QVariantMap& p, bool writing, Prepared* c, QString* error) {
  c->writing = writing;
  c->connection = p.value(QStringLiteral("connection"), QStringLiteral("simulator")).toString();
  if (c->connection != QLatin1String("simulator") && c->connection != QLatin1String("plc")) {
    *error = QStringLiteral("S7 连接方式无效");
    return false;
  }
  c->host = p.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString().trimmed();
  if (c->host.isEmpty() || c->host.size() > 253) {
    *error = QStringLiteral("设备地址必须为 IP 或主机名，不包含协议或路径");
    return false;
  }
  c->port = p.value(QStringLiteral("port"), 102).toInt();
  if (c->port < 1 || c->port > 65535) {
    *error = QStringLiteral("TCP 端口无效");
    return false;
  }
  c->rack = p.value(QStringLiteral("rack"), 0).toInt();
  c->slot = p.value(QStringLiteral("slot"), 1).toInt();
  if (c->rack < 0 || c->rack > 7 || c->slot < 0 || c->slot > 31) {
    *error = QStringLiteral("机架号或槽号无效");
    return false;
  }
  c->timeoutMs = p.value(QStringLiteral("timeoutMs"), 3000).toInt();
  if (c->timeoutMs < 100 || c->timeoutMs > 10000) {
    *error = QStringLiteral("timeoutMs 必须是 100 到 10000 的整数");
    return false;
  }
  c->area = p.value(QStringLiteral("area"), QStringLiteral("db")).toString();
  const QStringList areas{QStringLiteral("db"), QStringLiteral("mk"), QStringLiteral("pe"),
                          QStringLiteral("pa")};
  if (!areas.contains(c->area)) {
    *error = QStringLiteral("S7 数据区仅支持 DB、M、I、Q");
    return false;
  }
  if (writing && c->area == QLatin1String("pe")) {
    *error = QStringLiteral("输入区 I 仅支持读取");
    return false;
  }
  c->dtype = p.value(QStringLiteral("dataType"), QStringLiteral("uint16")).toString();
  if (typeWidth(c->dtype) <= 0) {
    *error = QStringLiteral("S7 数据类型无效");
    return false;
  }
  c->db = c->area == QLatin1String("db") ? p.value(QStringLiteral("dbNumber"), 1).toInt() : 0;
  if (c->area == QLatin1String("db") && (c->db < 1 || c->db > 65535)) {
    *error = QStringLiteral("数据块编号无效");
    return false;
  }
  c->offset = p.value(QStringLiteral("byteOffset"), writing ? 10 : 0).toInt();
  if (c->offset < 0 || c->offset > 2097151) {
    *error = QStringLiteral("S7 字节地址范围越界");
    return false;
  }
  c->bit = c->dtype == QLatin1String("bool") ? p.value(QStringLiteral("bitOffset"), 0).toInt() : 0;
  if (c->bit < 0 || c->bit > 7) {
    *error = QStringLiteral("位偏移必须是 0 到 7 的整数");
    return false;
  }
  if (writing) {
    QVariant rawv = p.contains(QStringLiteral("values")) ? p.value(QStringLiteral("values"))
                                                          : p.value(QStringLiteral("value"), 0);
    if (rawv.userType() == QMetaType::QVariantList)
      c->values = rawv.toList();
    else
      c->values = QVariantList{rawv};
    if (c->values.isEmpty() || c->values.size() > 200) {
      *error = QStringLiteral("写入值不能为空，单次最多 200 字节");
      return false;
    }
    if (!encodeValues(c->values, c->dtype, &c->raw, error)) return false;
    c->count = c->values.size();
  } else {
    c->count = p.value(QStringLiteral("count"), 1).toInt();
    if (c->count < 1 || c->count > 200) {
      *error = QStringLiteral("count 必须是 1 到 200 的整数");
      return false;
    }
  }
  if (c->dtype == QLatin1String("bool") && c->count != 1) {
    *error = QStringLiteral("BOOL 每次访问一个位；批量位请使用字节类型或多个节点");
    return false;
  }
  c->size = c->count * typeWidth(c->dtype);
  if (c->size > kMaxPayload) {
    *error = QStringLiteral("S7 单次数据最多 200 字节，请减少数量");
    return false;
  }
  if (c->offset + c->size > 2097152) {
    *error = QStringLiteral("S7 字节地址范围越界");
    return false;
  }
  if (c->connection == QLatin1String("plc") &&
      (c->port == 102 || c->port == 1102 || c->port == 0) &&
      (c->host == QLatin1String("127.0.0.1") || c->host == QLatin1String("localhost")) &&
      s7SoftServer().running()) {
    const quint16 sp = s7SoftServer().port();
    if (sp != 0) c->port = int(sp);
  }
  return true;
}

/** 在共享映像上直接读字节或单个位。 */
bool storeRead(const Prepared& c, QByteArray* raw, QString* error) {
  QMutexLocker lock(&gStoreMutex);
  QByteArray* mem = areaMemory(c.area, c.db, error);
  if (!mem) return false;
  if (c.dtype == QLatin1String("bool")) {
    if (c.offset < 0 || c.offset >= mem->size()) {
      *error = QStringLiteral("S7 字节地址范围越界");
      return false;
    }
    raw->resize(1);
    (*raw)[0] = char((quint8(mem->at(c.offset)) >> c.bit) & 1);
    return true;
  }
  if (c.offset < 0 || c.offset + c.size > mem->size()) {
    *error = QStringLiteral("S7 字节地址范围越界");
    return false;
  }
  *raw = mem->mid(c.offset, c.size);
  return true;
}

/** 写入字节，或按位写入且不覆盖相邻位。 */
bool storeWrite(const Prepared& c, QString* error) {
  QMutexLocker lock(&gStoreMutex);
  if (c.area == QLatin1String("pe")) {
    *error = QStringLiteral("输入区 I 仅支持读取");
    return false;
  }
  QByteArray* mem = areaMemory(c.area, c.db, error);
  if (!mem) return false;
  if (c.dtype == QLatin1String("bool")) {
    if (c.offset < 0 || c.offset >= mem->size() || c.raw.isEmpty()) {
      *error = QStringLiteral("S7 字节地址范围越界");
      return false;
    }
    const quint8 mask = quint8(1u << c.bit);
    quint8 cur = quint8(mem->at(c.offset));
    if (quint8(c.raw[0]))
      cur = quint8(cur | mask);
    else
      cur = quint8(cur & ~mask);
    (*mem)[c.offset] = char(cur);
    return true;
  }
  if (c.offset < 0 || c.offset + c.raw.size() > mem->size()) {
    *error = QStringLiteral("S7 字节地址范围越界");
    return false;
  }
  mem->replace(c.offset, c.raw.size(), c.raw);
  return true;
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
    const ssize_t n = ::send(fd, buf.constData() + off, size_t(buf.size() - off), MSG_NOSIGNAL);
    if (n < 0) {
      if (errno == EINTR) continue;
      *error = (errno == EAGAIN || errno == EWOULDBLOCK)
                   ? QStringLiteral("S7 操作超时")
                   : QStringLiteral("S7 发送失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    off += int(n);
  }
  return true;
}

bool recvExact(int fd, int want, QByteArray* out, QString* error) {
  out->clear();
  while (out->size() < want) {
    char tmp[512];
    const ssize_t n = ::recv(fd, tmp, size_t(std::min(int(want - out->size()), 512)), 0);
    if (n < 0) {
      if (errno == EINTR) continue;
      *error = (errno == EAGAIN || errno == EWOULDBLOCK)
                   ? QStringLiteral("S7 操作超时")
                   : QStringLiteral("S7 接收失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    if (n == 0) {
      *error = QStringLiteral("S7 连接已关闭");
      return false;
    }
    out->append(tmp, int(n));
  }
  return true;
}

/** 读一个完整 TPKT 帧（含 4 字节头）。 */
bool recvTpkt(int fd, QByteArray* frame, QString* error) {
  QByteArray hdr;
  if (!recvExact(fd, 4, &hdr, error)) return false;
  if (quint8(hdr[0]) != 0x03) {
    *error = QStringLiteral("S7 TPKT 版本无效");
    return false;
  }
  const int len = (quint8(hdr[2]) << 8) | quint8(hdr[3]);
  if (len < 4 || len > 4096) {
    *error = QStringLiteral("S7 TPKT 长度无效");
    return false;
  }
  QByteArray rest;
  if (len > 4 && !recvExact(fd, len - 4, &rest, error)) return false;
  *frame = hdr + rest;
  return true;
}

QByteArray wrapTpkt(const QByteArray& payload) {
  QByteArray out(4, 0);
  const int len = 4 + payload.size();
  out[0] = 0x03;
  out[2] = char((len >> 8) & 0xff);
  out[3] = char(len & 0xff);
  out.append(payload);
  return out;
}

QByteArray wrapCotpDt(const QByteArray& s7) {
  QByteArray cotp;
  cotp.append(char(0x02));
  cotp.append(char(0xF0));
  cotp.append(char(0x80));
  cotp.append(s7);
  return wrapTpkt(cotp);
}

/** 从 TPKT 帧取出 S7 载荷；COTP CR/CC 时 pdu 为空并返回 typ。 */
quint8 cotpType(const QByteArray& frame, QByteArray* s7) {
  if (frame.size() < 7) return 0;
  const int li = quint8(frame[4]);
  const quint8 typ = quint8(frame[5]);
  // DT (0xF0): LI=2, 随后是 0x80 与 S7 数据。
  if (typ == 0xF0) {
    const int off = 5 + li;
    if (off <= frame.size()) *s7 = frame.mid(off);
  }
  return typ;
}

QByteArray buildCotpCr(int rack, int slot) {
  QByteArray cotp;
  cotp.append(char(0x11));
  cotp.append(char(0xE0));
  cotp.append(char(0x00));
  cotp.append(char(0x00));
  cotp.append(char(0x00));
  cotp.append(char(0x01));
  cotp.append(char(0x00));
  cotp.append(char(0xC0));
  cotp.append(char(0x01));
  cotp.append(char(0x0A));
  cotp.append(char(0xC1));
  cotp.append(char(0x02));
  cotp.append(char(0x01));
  cotp.append(char(0x00));
  cotp.append(char(0xC2));
  cotp.append(char(0x02));
  cotp.append(char(0x03));
  cotp.append(char((rack << 5) | (slot & 0x1f)));
  cotp[0] = char(cotp.size() - 1);
  return wrapTpkt(cotp);
}

QByteArray buildCotpCc(const QByteArray& cr) {
  QByteArray frame = cr;
  if (frame.size() >= 6) frame[5] = char(0xD0);  // CC
  // 对端引用填入本端源引用，源引用用 0x0001。
  if (frame.size() >= 10) {
    // dest-ref = client's src-ref (bytes 8-9 of TPKT+COTP = frame[8],frame[9])
    frame[6] = frame[8];
    frame[7] = frame[9];
    frame[8] = 0x00;
    frame[9] = 0x01;
  }
  return frame;
}

QByteArray buildJob(quint16 seq, const QByteArray& params, const QByteArray& data) {
  QByteArray h(10, 0);
  h[0] = 0x32;
  h[1] = 0x01;
  h[4] = char((seq >> 8) & 0xff);
  h[5] = char(seq & 0xff);
  h[6] = char((params.size() >> 8) & 0xff);
  h[7] = char(params.size() & 0xff);
  h[8] = char((data.size() >> 8) & 0xff);
  h[9] = char(data.size() & 0xff);
  return wrapCotpDt(h + params + data);
}

QByteArray buildAck(quint16 seq, const QByteArray& params, const QByteArray& data) {
  QByteArray h(12, 0);
  h[0] = 0x32;
  h[1] = 0x03;
  h[4] = char((seq >> 8) & 0xff);
  h[5] = char(seq & 0xff);
  h[6] = char((params.size() >> 8) & 0xff);
  h[7] = char(params.size() & 0xff);
  h[8] = char((data.size() >> 8) & 0xff);
  h[9] = char(data.size() & 0xff);
  return wrapCotpDt(h + params + data);
}

struct S7Pdu {
  quint8 rosctr = 0;
  quint16 seq = 0;
  QByteArray params;
  QByteArray data;
  quint8 errClass = 0;
  quint8 errCode = 0;
};

bool parseS7(const QByteArray& s7, S7Pdu* out, QString* error) {
  if (s7.size() < 10 || quint8(s7[0]) != 0x32) {
    *error = QStringLiteral("S7 报文头无效");
    return false;
  }
  out->rosctr = quint8(s7[1]);
  out->seq = (quint16(quint8(s7[4])) << 8) | quint8(s7[5]);
  const int paramLen = (quint8(s7[6]) << 8) | quint8(s7[7]);
  const int dataLen = (quint8(s7[8]) << 8) | quint8(s7[9]);
  int off = 10;
  if (out->rosctr == 0x02 || out->rosctr == 0x03) {
    if (s7.size() < 12) {
      *error = QStringLiteral("S7 应答过短");
      return false;
    }
    out->errClass = quint8(s7[10]);
    out->errCode = quint8(s7[11]);
    off = 12;
  }
  if (s7.size() < off + paramLen + dataLen) {
    *error = QStringLiteral("S7 报文长度不完整");
    return false;
  }
  out->params = s7.mid(off, paramLen);
  out->data = s7.mid(off + paramLen, dataLen);
  return true;
}

QByteArray itemSpec(const Prepared& c) {
  QByteArray it;
  it.append(char(0x12));
  it.append(char(0x0A));
  it.append(char(0x10));
  const bool bit = c.dtype == QLatin1String("bool");
  it.append(char(bit ? 0x01 : 0x02));
  const quint16 count = quint16(bit ? 1 : c.size);
  it.append(char((count >> 8) & 0xff));
  it.append(char(count & 0xff));
  const quint16 db = quint16(c.area == QLatin1String("db") ? c.db : 0);
  it.append(char((db >> 8) & 0xff));
  it.append(char(db & 0xff));
  it.append(char(areaCode(c.area)));
  const int bitAddr = c.offset * 8 + (bit ? c.bit : 0);
  it.append(char((bitAddr >> 16) & 0xff));
  it.append(char((bitAddr >> 8) & 0xff));
  it.append(char(bitAddr & 0xff));
  return it;
}

QByteArray buildSetup(quint16 seq) {
  QByteArray p;
  p.append(char(0xF0));
  p.append(char(0x00));
  p.append(char(0x00));
  p.append(char(0x01));
  p.append(char(0x00));
  p.append(char(0x01));
  p.append(char(0x03));
  p.append(char(0xC0));
  return buildJob(seq, p, QByteArray());
}

int tcpConnect(const Prepared& c, QString* error) {
  return connectTcpTimeout(c.host, quint16(c.port), c.timeoutMs, error, QStringLiteral("S7"));
}

bool handshake(int fd, const Prepared& c, QString* error) {
  if (!sendAll(fd, buildCotpCr(c.rack, c.slot), error)) return false;
  QByteArray cc;
  if (!recvTpkt(fd, &cc, error)) return false;
  QByteArray dummy;
  if (cotpType(cc, &dummy) != 0xD0) {
    *error = QStringLiteral("S7 COTP 连接未被确认");
    return false;
  }
  if (!sendAll(fd, buildSetup(1), error)) return false;
  QByteArray setup;
  if (!recvTpkt(fd, &setup, error)) return false;
  QByteArray s7;
  cotpType(setup, &s7);
  S7Pdu pdu;
  if (!parseS7(s7, &pdu, error)) return false;
  if (pdu.params.isEmpty() || quint8(pdu.params[0]) != 0xF0) {
    *error = QStringLiteral("S7 通信协商失败");
    return false;
  }
  if (pdu.errClass != 0 || pdu.errCode != 0) {
    *error = QStringLiteral("S7 通信协商被拒绝");
    return false;
  }
  return true;
}

bool transactPlc(const Prepared& c, QByteArray* raw, QString* error) {
  const int fd = tcpConnect(c, error);
  if (fd < 0) return false;
  auto closer = [&]() { ::close(fd); };
  if (!handshake(fd, c, error)) {
    closer();
    return false;
  }
  QByteArray params;
  QByteArray data;
  if (c.writing) {
    params.append(char(0x05));
    params.append(char(0x01));
    params.append(itemSpec(c));
    const bool bit = c.dtype == QLatin1String("bool");
    data.append(char(0x00));
    data.append(char(bit ? 0x03 : 0x04));
    const int bits = bit ? 1 : c.raw.size() * 8;
    data.append(char((bits >> 8) & 0xff));
    data.append(char(bits & 0xff));
    data.append(c.raw);
    if (data.size() % 2 != 0) data.append(char(0x00));
  } else {
    params.append(char(0x04));
    params.append(char(0x01));
    params.append(itemSpec(c));
  }
  if (!sendAll(fd, buildJob(2, params, data), error)) {
    closer();
    return false;
  }
  QByteArray frame;
  if (!recvTpkt(fd, &frame, error)) {
    closer();
    return false;
  }
  closer();
  QByteArray s7;
  cotpType(frame, &s7);
  S7Pdu pdu;
  if (!parseS7(s7, &pdu, error)) return false;
  if (pdu.errClass != 0 || pdu.errCode != 0) {
    *error = QStringLiteral("S7 设备应答异常（class %1 code %2）")
                 .arg(pdu.errClass)
                 .arg(pdu.errCode);
    return false;
  }
  if (pdu.params.isEmpty() || quint8(pdu.params[0]) != (c.writing ? 0x05 : 0x04)) {
    *error = QStringLiteral("S7 功能码应答不匹配");
    return false;
  }
  if (c.writing) {
    if (pdu.data.isEmpty() || quint8(pdu.data[0]) != 0xFF) {
      *error = QStringLiteral("S7 写入应答异常");
      return false;
    }
    *raw = c.raw;
    return true;
  }
  // 读应答：FF + transport + length + payload
  if (pdu.data.size() < 4 || quint8(pdu.data[0]) != 0xFF) {
    *error = QStringLiteral("S7 读取应答异常");
    return false;
  }
  const int transport = quint8(pdu.data[1]);
  int dlen = (quint8(pdu.data[2]) << 8) | quint8(pdu.data[3]);
  if (transport != 0x03) dlen = (dlen + 7) / 8;  // 长度以位计
  if (pdu.data.size() < 4 + dlen) {
    *error = QStringLiteral("S7 返回字节数量不匹配");
    return false;
  }
  *raw = pdu.data.mid(4, c.dtype == QLatin1String("bool") ? 1 : c.size);
  return true;
}

S7Result finishOk(S7Result r, const Prepared& c, const QVariantList& values,
                  const QByteArray& raw, const std::chrono::steady_clock::time_point& started) {
  r.ok = true;
  r.protocol = QStringLiteral("s7");
  r.area = c.area;
  r.dbNumber = c.db;
  r.byteOffset = c.offset;
  r.bitOffset = c.bit;
  r.dataType = c.dtype;
  r.values = values;
  r.count = values.size();
  r.value = values.size() == 1 ? values.first() : QVariant(values);
  if (c.dtype != QLatin1String("bool")) {
    r.rawBytes.clear();
    for (unsigned char b : raw) r.rawBytes.push_back(int(b));
  }
  r.quality = QStringLiteral("good");
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  if (r.note.isEmpty()) {
    r.note = QStringLiteral("s7 %1 %2 DB%3.%4 n=%5")
                 .arg(r.action, r.area)
                 .arg(r.dbNumber)
                 .arg(r.byteOffset)
                 .arg(r.count);
  }
  return r;
}

S7Result finishFail(S7Result r, const QString& e,
                    const std::chrono::steady_clock::time_point& started, bool sent) {
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

S7Result runOp(const QVariantMap& params, bool writing) {
  const auto started = std::chrono::steady_clock::now();
  S7Result r;
  r.action = writing ? QStringLiteral("write") : QStringLiteral("read");
  Prepared c;
  QString err;
  if (!prepareCommon(params, writing, &c, &err)) return finishFail(r, err, started, false);
  r.area = c.area;
  r.dbNumber = c.db;
  r.byteOffset = c.offset;
  r.bitOffset = c.bit;
  r.dataType = c.dtype;
  QByteArray raw;
  if (c.connection == QLatin1String("simulator")) {
    if (writing) {
      if (!storeWrite(c, &err)) return finishFail(r, err, started, true);
      raw = c.raw;
    } else if (!storeRead(c, &raw, &err)) {
      return finishFail(r, err, started, false);
    }
  } else {
    if (!transactPlc(c, &raw, &err)) return finishFail(r, err, started, writing);
  }
  QVariantList values;
  if (!decodeRaw(raw, c.dtype, c.count, &values, &err))
    return finishFail(r, err, started, writing);
  if (writing) {
    r.acknowledged = true;
    r.note = QStringLiteral("设备已应答，不代表物理动作完成；外部写入不随流程回滚。");
  }
  return finishOk(r, c, values, raw, started);
}

/** 按请求项读写共享映像，构造 S7 读/写应答。 */
QByteArray handleS7Job(const S7Pdu& req) {
  if (req.params.isEmpty()) return QByteArray();
  const quint8 fn = quint8(req.params[0]);
  if (fn == 0xF0) {
    QByteArray p;
    p.append(char(0xF0));
    p.append(char(0x00));
    p.append(char(0x00));
    p.append(char(0x01));
    p.append(char(0x00));
    p.append(char(0x01));
    p.append(char(0x03));
    p.append(char(0xC0));
    return buildAck(req.seq, p, QByteArray());
  }
  if ((fn != 0x04 && fn != 0x05) || req.params.size() < 2)
    return buildAck(req.seq, QByteArray(2, 0), QByteArray());
  const int items = quint8(req.params[1]);
  int poff = 2;
  int doff = 0;
  QByteArray outParams;
  outParams.append(char(fn));
  outParams.append(char(items));
  QByteArray outData;
  for (int i = 0; i < items; ++i) {
    if (poff + 12 > req.params.size() || quint8(req.params[poff]) != 0x12) {
      outData.append(char(0x05));  // invalid
      break;
    }
    const int rest = quint8(req.params[poff + 1]);
    if (poff + 2 + rest > req.params.size()) break;
    const QByteArray spec = req.params.mid(poff, 2 + rest);
    poff += 2 + rest;
    // Any-Pointer：12 10 <wordLen> <count:2> <db:2> <area> <bitAddr:3>
    if (spec.size() < 12) {
      outData.append(char(0x05));
      break;
    }
    const quint8 wordLen = quint8(spec[3]);
    const int count = (quint8(spec[4]) << 8) | quint8(spec[5]);
    const int db = (quint8(spec[6]) << 8) | quint8(spec[7]);
    const QString area = areaFromCode(quint8(spec[8]));
    const int bitAddr = (int(quint8(spec[9])) << 16) | (int(quint8(spec[10])) << 8) |
                        quint8(spec[11]);
    const int byteOff = bitAddr / 8;
    const int bit = bitAddr % 8;
    const bool isBit = wordLen == 0x01;
    const int nbytes = isBit ? 1 : count;
    QString err;
    if (fn == 0x05) {
      // 写数据：00, transport, length, payload, 可选填充
      if (doff + 4 > req.data.size()) {
        outData.append(char(0x05));
        continue;
      }
      const int transport = quint8(req.data[doff + 1]);
      int dlen = (quint8(req.data[doff + 2]) << 8) | quint8(req.data[doff + 3]);
      if (transport != 0x03) dlen = (dlen + 7) / 8;
      if (doff + 4 + dlen > req.data.size()) {
        outData.append(char(0x05));
        continue;
      }
      const QByteArray payload = req.data.mid(doff + 4, isBit ? 1 : nbytes);
      int consumed = 4 + dlen;
      if (consumed % 2) consumed += 1;
      doff += consumed;
      Prepared c;
      c.area = area;
      c.db = db;
      c.offset = byteOff;
      c.bit = bit;
      c.dtype = isBit ? QStringLiteral("bool") : QStringLiteral("uint8");
      c.size = payload.size();
      c.raw = payload;
      c.count = isBit ? 1 : payload.size();
      if (!storeWrite(c, &err)) {
        outData.append(char(0x05));
        continue;
      }
      outData.append(char(0xFF));
    } else {
      Prepared c;
      c.area = area;
      c.db = db;
      c.offset = byteOff;
      c.bit = bit;
      c.dtype = isBit ? QStringLiteral("bool") : QStringLiteral("uint8");
      c.size = nbytes;
      c.count = isBit ? 1 : nbytes;
      QByteArray raw;
      if (!storeRead(c, &raw, &err)) {
        outData.append(char(0x05));
        continue;
      }
      outData.append(char(0xFF));
      outData.append(char(isBit ? 0x03 : 0x04));
      const int bits = isBit ? 1 : raw.size() * 8;
      outData.append(char((bits >> 8) & 0xff));
      outData.append(char(bits & 0xff));
      outData.append(raw);
      if (outData.size() % 2) outData.append(char(0x00));
    }
  }
  return buildAck(req.seq, outParams, outData);
}

void serveClient(int cfd) {
  auto last = std::chrono::steady_clock::now();
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
    QByteArray frame;
    QString err;
    // 阻塞短超时读一帧；poll 已表明可读。
    timeval tv{};
    tv.tv_sec = 2;
    tv.tv_usec = 0;
    setsockopt(cfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(cfd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    if (!recvTpkt(cfd, &frame, &err)) break;
    last = std::chrono::steady_clock::now();
    QByteArray s7;
    const quint8 typ = cotpType(frame, &s7);
    QByteArray reply;
    if (typ == 0xE0) {
      reply = buildCotpCc(frame);
    } else if (typ == 0xF0) {
      S7Pdu pdu;
      QString pe;
      if (!parseS7(s7, &pdu, &pe)) break;
      reply = handleS7Job(pdu);
    } else {
      break;
    }
    if (reply.isEmpty() || !sendAll(cfd, reply, &err)) break;
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

S7SoftServer& s7SoftServer() {
  QMutexLocker lock(&gServerMutex);
  if (!gServer) gServer = new S7SoftServer();
  return *gServer;
}

bool S7SoftServer::start(quint16 port, QString* error) {
  if (gServerRun && gListenFd >= 0 && (port == 0 || port == gListenPort)) return true;
  if (gServerRun) stop();
  ensureStore();
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    if (error) *error = QStringLiteral("无法创建 S7 监听套接字");
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
      *error = QStringLiteral("无法绑定 S7 端口 %1: %2")
                   .arg(port)
                   .arg(QString::fromLocal8Bit(strerror(errno)));
    ::close(fd);
    return false;
  }
  if (::listen(fd, 8) != 0) {
    if (error) *error = QStringLiteral("S7 监听失败");
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

void S7SoftServer::stop() {
  gServerRun = false;
  if (gListenFd >= 0) {
    ::close(gListenFd);
    gListenFd = -1;
  }
  gListenPort = 0;
}

bool S7SoftServer::running() const { return gServerRun && gListenFd >= 0; }

quint16 S7SoftServer::port() const { return gListenPort; }

QString S7SoftServer::endpoint() const {
  return QStringLiteral("127.0.0.1:%1").arg(gListenPort);
}

S7Result runS7Read(const QVariantMap& params) { return runOp(params, false); }

S7Result runS7Write(const QVariantMap& params) { return runOp(params, true); }

QStringList s7SelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail) {
    if (!ok) fails << QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail);
  };

  {
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("area"), QStringLiteral("db"));
    r.insert(QStringLiteral("dbNumber"), 1);
    r.insert(QStringLiteral("byteOffset"), 0);
    r.insert(QStringLiteral("dataType"), QStringLiteral("uint16"));
    const S7Result rr = runS7Read(r);
    check("sim-default-dbw0", rr.ok && rr.value.toInt() == 123,
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap r;
    r.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("area"), QStringLiteral("db"));
    r.insert(QStringLiteral("dbNumber"), 1);
    r.insert(QStringLiteral("byteOffset"), 4);
    r.insert(QStringLiteral("dataType"), QStringLiteral("float32"));
    const S7Result rr = runS7Read(r);
    check("sim-default-real4", rr.ok && qFuzzyCompare(rr.value.toDouble() + 1.0, 13.5),
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("area"), QStringLiteral("db"));
    w.insert(QStringLiteral("dbNumber"), 1);
    w.insert(QStringLiteral("byteOffset"), 10);
    w.insert(QStringLiteral("dataType"), QStringLiteral("uint16"));
    w.insert(QStringLiteral("value"), 4242);
    const S7Result wr = runS7Write(w);
    check("sim-write", wr.ok && wr.acknowledged && wr.value.toInt() == 4242,
          wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r = w;
    r.remove(QStringLiteral("value"));
    r.insert(QStringLiteral("count"), 1);
    const S7Result rr = runS7Read(r);
    check("sim-readback", rr.ok && rr.value.toInt() == 4242,
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("area"), QStringLiteral("db"));
    w.insert(QStringLiteral("dbNumber"), 1);
    w.insert(QStringLiteral("byteOffset"), 0);
    w.insert(QStringLiteral("bitOffset"), 3);
    w.insert(QStringLiteral("dataType"), QStringLiteral("bool"));
    w.insert(QStringLiteral("value"), true);
    const S7Result wr = runS7Write(w);
    check("sim-bool-write", wr.ok && wr.value.toBool(), wr.error);
    // 相邻位写入不得破坏 DBW0 的其余位；再读回 bit3。
    const S7Result rr = runS7Read(w);
    check("sim-bool-read", rr.ok && rr.value.toBool(), rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("area"), QStringLiteral("pe"));
    w.insert(QStringLiteral("byteOffset"), 0);
    w.insert(QStringLiteral("value"), 1);
    const S7Result wr = runS7Write(w);
    check("sim-pe-rejected", !wr.ok && wr.error.contains(QStringLiteral("输入区")), wr.error);
  }

  QString serr;
  bool started = false;
  for (int p = 1102; p <= 1106 && !started; ++p) {
    QString e;
    if (s7SoftServer().start(quint16(p), &e)) started = true;
    else serr = e;
  }
  check("tcp-server", started, serr);
  if (started) {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("plc"));
    w.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    w.insert(QStringLiteral("port"), int(s7SoftServer().port()));
    w.insert(QStringLiteral("rack"), 0);
    w.insert(QStringLiteral("slot"), 1);
    w.insert(QStringLiteral("area"), QStringLiteral("db"));
    w.insert(QStringLiteral("dbNumber"), 1);
    w.insert(QStringLiteral("byteOffset"), 20);
    w.insert(QStringLiteral("dataType"), QStringLiteral("uint16"));
    w.insert(QStringLiteral("value"), 9001);
    w.insert(QStringLiteral("timeoutMs"), 3000);
    const S7Result wr = runS7Write(w);
    check("tcp-write", wr.ok && wr.acknowledged, wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r = w;
    r.remove(QStringLiteral("value"));
    r.insert(QStringLiteral("count"), 1);
    const S7Result rr = runS7Read(r);
    check("tcp-readback", rr.ok && rr.value.toInt() == 9001,
          rr.ok ? rr.value.toString() : rr.error);
  }
  return fails;
}

}  // namespace sieans_qt
