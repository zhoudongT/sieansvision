#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "ModbusClient.hpp"
#include "ProtocolNet.hpp"

#include <QFile>
#include <QMutex>
#include <QMutexLocker>
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
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <termios.h>
#include <unistd.h>

namespace sieans_qt {
namespace {

constexpr int kMapSize = 1024;
constexpr int kMaxPdu = 253;

QMutex gStoreMutex;
QVector<quint16> gHolding;
QVector<quint16> gInput;
QVector<quint8> gCoils;
QVector<quint8> gDiscrete;
bool gStoreInit = false;

QMutex gServerMutex;
ModbusSoftServer* gServer = nullptr;
int gListenFd = -1;
quint16 gListenPort = 0;
bool gServerRun = false;

QMutex gRtuMutex;
ModbusRtuPeer* gRtu = nullptr;
int gRtuMaster = -1;
QString gRtuPath;
bool gRtuRun = false;

/** 初始化与 Python pymodbus 模拟器一致的默认寄存器内容，供回环冒烟对照。 */
void ensureStore() {
  if (gStoreInit) return;
  gHolding.resize(kMapSize);
  gInput.resize(kMapSize);
  gCoils.resize(kMapSize);
  gDiscrete.resize(kMapSize);
  gHolding.fill(0);
  gInput.fill(0);
  gCoils.fill(0);
  gDiscrete.fill(1);
  if (kMapSize > 0) gHolding[0] = 123;
  if (kMapSize > 1) gHolding[1] = 456;
  if (kMapSize > 2) gHolding[2] = 250;
  if (kMapSize > 0) gInput[0] = 100;
  if (kMapSize > 1) gInput[1] = 200;
  if (kMapSize > 2) gInput[2] = 300;
  gStoreInit = true;
}

int widthOf(const QString& dtype) {
  if (dtype == QLatin1String("uint16") || dtype == QLatin1String("int16")) return 1;
  if (dtype == QLatin1String("uint32") || dtype == QLatin1String("int32") ||
      dtype == QLatin1String("float32"))
    return 2;
  if (dtype == QLatin1String("float64")) return 4;
  return 1;
}

bool isBitArea(const QString& area) {
  return area == QLatin1String("coils") || area == QLatin1String("discrete");
}

/** 按字节序 / 字序把主机大端载荷重排为线路寄存器字（高字节在前的 16 位值）。 */
QVector<quint16> wordswapFromBe(const QByteArray& beRaw, const QString& byteOrder,
                                const QString& wordOrder) {
  QVector<QByteArray> words;
  for (int i = 0; i + 1 < beRaw.size(); i += 2)
    words.push_back(beRaw.mid(i, 2));
  if (byteOrder == QLatin1String("little")) {
    for (QByteArray& w : words) {
      if (w.size() == 2) std::swap(w[0], w[1]);
    }
  }
  if (wordOrder == QLatin1String("little"))
    std::reverse(words.begin(), words.end());
  QVector<quint16> out;
  out.reserve(words.size());
  for (const QByteArray& w : words) {
    const auto* u = reinterpret_cast<const unsigned char*>(w.constData());
    out.push_back(quint16((quint16(u[0]) << 8) | u[1]));
  }
  return out;
}

QByteArray wordswapToBe(const QVector<quint16>& regs, const QString& byteOrder,
                        const QString& wordOrder) {
  QVector<QByteArray> words;
  for (quint16 r : regs) {
    QByteArray w(2, 0);
    w[0] = char((r >> 8) & 0xff);
    w[1] = char(r & 0xff);
    words.push_back(w);
  }
  if (wordOrder == QLatin1String("little"))
    std::reverse(words.begin(), words.end());
  if (byteOrder == QLatin1String("little")) {
    for (QByteArray& w : words) {
      if (w.size() == 2) std::swap(w[0], w[1]);
    }
  }
  QByteArray raw;
  for (const QByteArray& w : words) raw.append(w);
  return raw;
}

bool encodeValues(const QVariantList& values, const QString& dtype, const QString& byteOrder,
                  const QString& wordOrder, QVector<quint16>* regs, QString* error) {
  regs->clear();
  for (const QVariant& v : values) {
    if (v.typeId() == QMetaType::Bool) {
      *error = QStringLiteral("寄存器写入值必须为有限数值");
      return false;
    }
    QByteArray raw;
    if (dtype == QLatin1String("uint16")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < 0 || n > 65535) {
        *error = QStringLiteral("写入值超出 uint16 范围");
        return false;
      }
      raw.resize(2);
      qToBigEndian(quint16(n), raw.data());
    } else if (dtype == QLatin1String("int16")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < -32768 || n > 32767) {
        *error = QStringLiteral("写入值超出 int16 范围");
        return false;
      }
      raw.resize(2);
      qToBigEndian(qint16(n), raw.data());
    } else if (dtype == QLatin1String("uint32")) {
      bool ok = false;
      const qlonglong n = v.toLongLong(&ok);
      if (!ok || n < 0 || quint64(n) > 0xffffffffull) {
        *error = QStringLiteral("写入值超出 uint32 范围");
        return false;
      }
      raw.resize(4);
      qToBigEndian(quint32(n), raw.data());
    } else if (dtype == QLatin1String("int32")) {
      bool ok = false;
      const qint64 n = v.toLongLong(&ok);
      if (!ok || n < -2147483648ll || n > 2147483647ll) {
        *error = QStringLiteral("写入值超出 int32 范围");
        return false;
      }
      raw.resize(4);
      qToBigEndian(qint32(n), raw.data());
    } else if (dtype == QLatin1String("float32")) {
      bool ok = false;
      const float f = v.toFloat(&ok);
      if (!ok || !std::isfinite(f)) {
        *error = QStringLiteral("寄存器写入值必须为有限数值");
        return false;
      }
      quint32 u = 0;
      static_assert(sizeof(float) == 4, "float");
      std::memcpy(&u, &f, 4);
      raw.resize(4);
      qToBigEndian(u, raw.data());
    } else if (dtype == QLatin1String("float64")) {
      bool ok = false;
      const double d = v.toDouble(&ok);
      if (!ok || !std::isfinite(d)) {
        *error = QStringLiteral("寄存器写入值必须为有限数值");
        return false;
      }
      quint64 u = 0;
      static_assert(sizeof(double) == 8, "double");
      std::memcpy(&u, &d, 8);
      raw.resize(8);
      qToBigEndian(u, raw.data());
    } else {
      *error = QStringLiteral("寄存器数据类型或字节/字序无效");
      return false;
    }
    regs->append(wordswapFromBe(raw, byteOrder, wordOrder));
  }
  return true;
}

bool decodeRegisters(const QVector<quint16>& regs, const QString& dtype,
                     const QString& byteOrder, const QString& wordOrder, QVariantList* values,
                     QString* error) {
  const int w = widthOf(dtype);
  if (w <= 0 || regs.size() % w != 0) {
    *error = QStringLiteral("返回寄存器数量与数据类型不匹配");
    return false;
  }
  values->clear();
  for (int i = 0; i < regs.size(); i += w) {
    QVector<quint16> slice = regs.mid(i, w);
    const QByteArray raw = wordswapToBe(slice, byteOrder, wordOrder);
    if (dtype == QLatin1String("uint16")) {
      values->push_back(int(qFromBigEndian<quint16>(raw.constData())));
    } else if (dtype == QLatin1String("int16")) {
      values->push_back(int(qFromBigEndian<qint16>(raw.constData())));
    } else if (dtype == QLatin1String("uint32")) {
      values->push_back(qulonglong(qFromBigEndian<quint32>(raw.constData())));
    } else if (dtype == QLatin1String("int32")) {
      values->push_back(qlonglong(qFromBigEndian<qint32>(raw.constData())));
    } else if (dtype == QLatin1String("float32")) {
      const quint32 u = qFromBigEndian<quint32>(raw.constData());
      float f = 0;
      std::memcpy(&f, &u, 4);
      if (!std::isfinite(f)) {
        *error = QStringLiteral("设备返回 NaN/Infinity，请检查数据类型和字节序");
        return false;
      }
      values->push_back(double(f));
    } else if (dtype == QLatin1String("float64")) {
      const quint64 u = qFromBigEndian<quint64>(raw.constData());
      double d = 0;
      std::memcpy(&d, &u, 8);
      if (!std::isfinite(d)) {
        *error = QStringLiteral("设备返回 NaN/Infinity，请检查数据类型和字节序");
        return false;
      }
      values->push_back(d);
    } else {
      *error = QStringLiteral("寄存器数据类型或字节/字序无效");
      return false;
    }
  }
  return true;
}

quint16 crc16Modbus(const char* data, int len) {
  quint16 crc = 0xFFFF;
  for (int i = 0; i < len; ++i) {
    crc ^= quint8(data[i]);
    for (int b = 0; b < 8; ++b) {
      if (crc & 1)
        crc = quint16((crc >> 1) ^ 0xA001);
      else
        crc >>= 1;
    }
  }
  return crc;
}

QByteArray exceptionPdu(quint8 fn, quint8 code) {
  QByteArray p(2, 0);
  p[0] = char(fn | 0x80);
  p[1] = char(code);
  return p;
}

/** 在共享寄存器表上执行一个 Modbus PDU，返回应答 PDU（含异常帧）。 */
QByteArray handlePdu(const QByteArray& pdu) {
  ensureStore();
  if (pdu.size() < 2) return exceptionPdu(0, 0x01);
  const quint8 fn = quint8(pdu[0]);
  QMutexLocker lock(&gStoreMutex);
  auto readBits = [&](QVector<quint8>& map) -> QByteArray {
    if (pdu.size() < 5) return exceptionPdu(fn, 0x03);
    const int addr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
    const int qty = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    if (qty < 1 || qty > 2000) return exceptionPdu(fn, 0x03);
    if (addr < 0 || addr + qty > kMapSize) return exceptionPdu(fn, 0x02);
    const int nbytes = (qty + 7) / 8;
    QByteArray out;
    out.append(char(fn));
    out.append(char(nbytes));
    out.append(QByteArray(nbytes, 0));
    for (int i = 0; i < qty; ++i) {
      if (map[addr + i])
        out[2 + i / 8] = char(quint8(out[2 + i / 8]) | (1 << (i % 8)));
    }
    return out;
  };
  auto readRegs = [&](QVector<quint16>& map) -> QByteArray {
    if (pdu.size() < 5) return exceptionPdu(fn, 0x03);
    const int addr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
    const int qty = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    if (qty < 1 || qty > 125) return exceptionPdu(fn, 0x03);
    if (addr < 0 || addr + qty > kMapSize) return exceptionPdu(fn, 0x02);
    QByteArray out;
    out.append(char(fn));
    out.append(char(qty * 2));
    for (int i = 0; i < qty; ++i) {
      const quint16 v = map[addr + i];
      out.append(char((v >> 8) & 0xff));
      out.append(char(v & 0xff));
    }
    return out;
  };
  if (fn == 0x01) return readBits(gCoils);
  if (fn == 0x02) return readBits(gDiscrete);
  if (fn == 0x03) return readRegs(gHolding);
  if (fn == 0x04) return readRegs(gInput);
  if (fn == 0x05) {
    if (pdu.size() < 5) return exceptionPdu(fn, 0x03);
    const int addr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
    const quint16 val = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    if (addr < 0 || addr >= kMapSize) return exceptionPdu(fn, 0x02);
    if (val != 0x0000 && val != 0xFF00) return exceptionPdu(fn, 0x03);
    gCoils[addr] = val == 0xFF00 ? 1 : 0;
    return pdu.left(5);
  }
  if (fn == 0x06) {
    if (pdu.size() < 5) return exceptionPdu(fn, 0x03);
    const int addr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
    const quint16 val = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    if (addr < 0 || addr >= kMapSize) return exceptionPdu(fn, 0x02);
    gHolding[addr] = val;
    return pdu.left(5);
  }
  if (fn == 0x0F) {
    if (pdu.size() < 6) return exceptionPdu(fn, 0x03);
    const int addr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
    const int qty = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    const int nbytes = quint8(pdu[5]);
    if (qty < 1 || qty > 1968 || nbytes != (qty + 7) / 8 || pdu.size() < 6 + nbytes)
      return exceptionPdu(fn, 0x03);
    if (addr < 0 || addr + qty > kMapSize) return exceptionPdu(fn, 0x02);
    for (int i = 0; i < qty; ++i)
      gCoils[addr + i] = (quint8(pdu[6 + i / 8]) >> (i % 8)) & 1;
    QByteArray out;
    out.append(char(fn));
    out.append(pdu.mid(1, 4));
    return out;
  }
  if (fn == 0x10) {
    if (pdu.size() < 6) return exceptionPdu(fn, 0x03);
    const int addr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
    const int qty = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    const int nbytes = quint8(pdu[5]);
    if (qty < 1 || qty > 123 || nbytes != qty * 2 || pdu.size() < 6 + nbytes)
      return exceptionPdu(fn, 0x03);
    if (addr < 0 || addr + qty > kMapSize) return exceptionPdu(fn, 0x02);
    for (int i = 0; i < qty; ++i) {
      gHolding[addr + i] =
          (quint16(quint8(pdu[6 + i * 2])) << 8) | quint8(pdu[7 + i * 2]);
    }
    QByteArray out;
    out.append(char(fn));
    out.append(pdu.mid(1, 4));
    return out;
  }
  return exceptionPdu(fn, 0x01);
}

bool applyDirectRead(const QString& area, int addr, int wireCount, bool bits,
                     QVector<quint16>* regs, QVector<quint8>* bitVals, QString* error) {
  ensureStore();
  QMutexLocker lock(&gStoreMutex);
  if (addr < 0 || wireCount < 1 || addr + wireCount > kMapSize) {
    *error = QStringLiteral("起始地址或数量超出模拟设备范围");
    return false;
  }
  if (bits) {
    const QVector<quint8>& map = area == QLatin1String("discrete") ? gDiscrete : gCoils;
    bitVals->resize(wireCount);
    for (int i = 0; i < wireCount; ++i) (*bitVals)[i] = map[addr + i];
  } else {
    const QVector<quint16>& map = area == QLatin1String("input") ? gInput : gHolding;
    *regs = map.mid(addr, wireCount);
  }
  return true;
}

bool applyDirectWrite(const QString& area, int addr, bool bits, const QVector<quint16>& regs,
                      const QVector<quint8>& bitVals, QString* error) {
  ensureStore();
  QMutexLocker lock(&gStoreMutex);
  if (area == QLatin1String("input") || area == QLatin1String("discrete")) {
    *error = QStringLiteral("输入寄存器和离散输入不能写入");
    return false;
  }
  if (bits) {
    if (addr < 0 || addr + bitVals.size() > kMapSize) {
      *error = QStringLiteral("起始地址或数量超出模拟设备范围");
      return false;
    }
    for (int i = 0; i < bitVals.size(); ++i) gCoils[addr + i] = bitVals[i] ? 1 : 0;
  } else {
    if (addr < 0 || addr + regs.size() > kMapSize) {
      *error = QStringLiteral("起始地址或数量超出模拟设备范围");
      return false;
    }
    for (int i = 0; i < regs.size(); ++i) gHolding[addr + i] = regs[i];
  }
  return true;
}

int setNonblock(int fd) {
  const int flags = fcntl(fd, F_GETFL, 0);
  if (flags >= 0) fcntl(fd, F_SETFL, flags | O_NONBLOCK);
  return fd;
}

bool waitFd(int fd, short events, const std::chrono::steady_clock::time_point& deadline,
            QString* error) {
  const auto now = std::chrono::steady_clock::now();
  if (now >= deadline) {
    *error = QStringLiteral("Modbus 操作超时");
    return false;
  }
  const int ms = std::max(1, int(std::chrono::duration<double, std::milli>(deadline - now).count()));
  pollfd pfd{};
  pfd.fd = fd;
  pfd.events = events;
  const int rc = ::poll(&pfd, 1, ms);
  if (rc == 0) {
    *error = QStringLiteral("Modbus 操作超时");
    return false;
  }
  if (rc < 0) {
    if (errno == EINTR) return waitFd(fd, events, deadline, error);
    *error = QStringLiteral("Modbus 等待失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
    return false;
  }
  return true;
}

bool writeAllFd(int fd, const QByteArray& buf, const std::chrono::steady_clock::time_point& deadline,
                QString* error) {
  int off = 0;
  while (off < buf.size()) {
    if (!waitFd(fd, POLLOUT, deadline, error)) return false;
    const ssize_t n = ::write(fd, buf.constData() + off, size_t(buf.size() - off));
    if (n < 0) {
      if (errno == EINTR || errno == EAGAIN) continue;
      *error = QStringLiteral("Modbus 发送失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    off += int(n);
  }
  return true;
}

bool readExactFd(int fd, int want, QByteArray* out, const std::chrono::steady_clock::time_point& deadline,
                 QString* error) {
  out->clear();
  out->reserve(want);
  while (out->size() < want) {
    if (!waitFd(fd, POLLIN, deadline, error)) return false;
    char tmp[512];
    const ssize_t n = ::read(fd, tmp, size_t(std::min(int(want - out->size()), 512)));
    if (n < 0) {
      if (errno == EINTR || errno == EAGAIN) continue;
      *error = QStringLiteral("Modbus 接收失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    if (n == 0) {
      *error = QStringLiteral("Modbus 连接已关闭");
      return false;
    }
    out->append(tmp, int(n));
  }
  return true;
}

QByteArray buildReadPdu(const QString& area, int addr, int wireCount) {
  quint8 fn = 0x03;
  if (area == QLatin1String("coils")) fn = 0x01;
  else if (area == QLatin1String("discrete")) fn = 0x02;
  else if (area == QLatin1String("input")) fn = 0x04;
  QByteArray p(5, 0);
  p[0] = char(fn);
  p[1] = char((addr >> 8) & 0xff);
  p[2] = char(addr & 0xff);
  p[3] = char((wireCount >> 8) & 0xff);
  p[4] = char(wireCount & 0xff);
  return p;
}

QByteArray buildWritePdu(bool bits, int addr, const QVector<quint16>& regs,
                         const QVector<quint8>& bitVals) {
  if (bits) {
    if (bitVals.size() == 1) {
      QByteArray p(5, 0);
      p[0] = 0x05;
      p[1] = char((addr >> 8) & 0xff);
      p[2] = char(addr & 0xff);
      const quint16 v = bitVals[0] ? 0xFF00 : 0x0000;
      p[3] = char((v >> 8) & 0xff);
      p[4] = char(v & 0xff);
      return p;
    }
    const int qty = bitVals.size();
    const int nbytes = (qty + 7) / 8;
    QByteArray p;
    p.append(char(0x0F));
    p.append(char((addr >> 8) & 0xff));
    p.append(char(addr & 0xff));
    p.append(char((qty >> 8) & 0xff));
    p.append(char(qty & 0xff));
    p.append(char(nbytes));
    QByteArray data(nbytes, 0);
    for (int i = 0; i < qty; ++i) {
      if (bitVals[i]) data[i / 8] = char(quint8(data[i / 8]) | (1 << (i % 8)));
    }
    p.append(data);
    return p;
  }
  if (regs.size() == 1) {
    QByteArray p(5, 0);
    p[0] = 0x06;
    p[1] = char((addr >> 8) & 0xff);
    p[2] = char(addr & 0xff);
    p[3] = char((regs[0] >> 8) & 0xff);
    p[4] = char(regs[0] & 0xff);
    return p;
  }
  const int qty = regs.size();
  QByteArray p;
  p.append(char(0x10));
  p.append(char((addr >> 8) & 0xff));
  p.append(char(addr & 0xff));
  p.append(char((qty >> 8) & 0xff));
  p.append(char(qty & 0xff));
  p.append(char(qty * 2));
  for (quint16 r : regs) {
    p.append(char((r >> 8) & 0xff));
    p.append(char(r & 0xff));
  }
  return p;
}

bool parseReadResponse(const QByteArray& pdu, bool bits, int wireCount, QVector<quint16>* regs,
                       QVector<quint8>* bitVals, QString* error) {
  if (pdu.isEmpty()) {
    *error = QStringLiteral("Modbus 设备应答为空");
    return false;
  }
  const quint8 fn = quint8(pdu[0]);
  if (fn & 0x80) {
    const int code = pdu.size() > 1 ? quint8(pdu[1]) : 0;
    *error = QStringLiteral("Modbus 设备异常响应，功能码 %1，异常码 %2")
                 .arg(fn & 0x7f)
                 .arg(code);
    return false;
  }
  if (pdu.size() < 2) {
    *error = QStringLiteral("Modbus 设备应答过短");
    return false;
  }
  const int nbytes = quint8(pdu[1]);
  if (pdu.size() < 2 + nbytes) {
    *error = QStringLiteral("Modbus 设备应答长度不完整");
    return false;
  }
  if (bits) {
    bitVals->clear();
    for (int i = 0; i < wireCount; ++i) {
      if (i / 8 >= nbytes) {
        *error = QStringLiteral("设备返回的线圈数量不足");
        return false;
      }
      bitVals->push_back((quint8(pdu[2 + i / 8]) >> (i % 8)) & 1);
    }
  } else {
    if (nbytes != wireCount * 2) {
      *error = QStringLiteral("设备返回的寄存器数量不匹配");
      return false;
    }
    regs->clear();
    for (int i = 0; i < wireCount; ++i) {
      regs->push_back((quint16(quint8(pdu[2 + i * 2])) << 8) | quint8(pdu[3 + i * 2]));
    }
  }
  return true;
}

bool parseWriteResponse(const QByteArray& pdu, bool bits, int addr, int wireCount,
                        const QVector<quint16>& regs, const QVector<quint8>& bitVals,
                        QString* error) {
  if (pdu.isEmpty()) {
    *error = QStringLiteral("Modbus 设备应答为空");
    return false;
  }
  const quint8 fn = quint8(pdu[0]);
  if (fn & 0x80) {
    const int code = pdu.size() > 1 ? quint8(pdu[1]) : 0;
    *error = QStringLiteral("Modbus 设备异常响应，功能码 %1，异常码 %2")
                 .arg(fn & 0x7f)
                 .arg(code);
    return false;
  }
  if (pdu.size() < 5) {
    *error = QStringLiteral("设备写入确认过短");
    return false;
  }
  const int raddr = (quint8(pdu[1]) << 8) | quint8(pdu[2]);
  if (raddr != addr) {
    *error = QStringLiteral("设备写入确认的地址/数量不匹配");
    return false;
  }
  if (fn == 0x05) {
    const quint16 v = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    const quint16 expect = bitVals.isEmpty() ? 0 : (bitVals[0] ? 0xFF00 : 0x0000);
    if (v != expect) {
      *error = QStringLiteral("设备写入确认的数值不匹配");
      return false;
    }
  } else if (fn == 0x06) {
    const quint16 v = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    if (regs.isEmpty() || v != regs[0]) {
      *error = QStringLiteral("设备写入确认的数值不匹配");
      return false;
    }
  } else {
    const int qty = (quint8(pdu[3]) << 8) | quint8(pdu[4]);
    if (qty != wireCount) {
      *error = QStringLiteral("设备写入确认的地址/数量不匹配");
      return false;
    }
  }
  return true;
}

struct Prepared {
  QString transport;
  QString area;
  QString dtype;
  QString byteOrder;
  QString wordOrder;
  QString host;
  QString serialPort;
  int port = 502;
  int baudrate = 19200;
  QString parity = QStringLiteral("N");
  int stopbits = 1;
  int deviceId = 1;
  int address = 0;
  int count = 1;
  int wireCount = 1;
  int timeoutMs = 1500;
  bool bits = false;
  bool writing = false;
  QVariantList values;
  QVector<quint16> wireRegs;
  QVector<quint8> wireBits;
};

bool prepareCommon(const QVariantMap& p, bool writing, Prepared* c, QString* error) {
  c->writing = writing;
  c->transport = p.value(QStringLiteral("transport"), QStringLiteral("simulator")).toString();
  if (c->transport != QLatin1String("simulator") && c->transport != QLatin1String("tcp") &&
      c->transport != QLatin1String("rtu")) {
    *error = QStringLiteral("transport 仅支持 simulator、tcp 或 rtu");
    return false;
  }
  c->timeoutMs = p.value(QStringLiteral("timeoutMs"), 1500).toInt();
  if (c->timeoutMs < 100 || c->timeoutMs > 10000) {
    *error = QStringLiteral("timeoutMs 必须是 100 到 10000 的整数");
    return false;
  }
  c->deviceId = p.value(QStringLiteral("deviceId"), 1).toInt();
  const int idMin = c->transport == QLatin1String("rtu") ? 1 : 0;
  const int idMax = c->transport == QLatin1String("rtu") ? 247 : 255;
  if (c->deviceId < idMin || c->deviceId > idMax) {
    *error = QStringLiteral("deviceId 必须是 %1 到 %2 的整数").arg(idMin).arg(idMax);
    return false;
  }
  c->area = p.value(QStringLiteral("area"), QStringLiteral("holding")).toString();
  const QStringList areas{QStringLiteral("holding"), QStringLiteral("input"),
                          QStringLiteral("coils"), QStringLiteral("discrete")};
  if (!areas.contains(c->area)) {
    *error = QStringLiteral("数据区域无效");
    return false;
  }
  if (writing && (c->area == QLatin1String("input") || c->area == QLatin1String("discrete"))) {
    *error = QStringLiteral("输入寄存器和离散输入不能写入");
    return false;
  }
  c->bits = isBitArea(c->area);
  c->address = p.value(QStringLiteral("address"), writing ? 10 : 0).toInt();
  if (c->address < 0 || c->address > 65535) {
    *error = QStringLiteral("address 必须是 0 到 65535 的整数");
    return false;
  }
  c->dtype = p.value(QStringLiteral("dataType"), QStringLiteral("uint16")).toString();
  c->byteOrder = p.value(QStringLiteral("byteOrder"), QStringLiteral("big")).toString();
  c->wordOrder = p.value(QStringLiteral("wordOrder"), QStringLiteral("big")).toString();
  const QStringList dtypes{QStringLiteral("uint16"), QStringLiteral("int16"),
                           QStringLiteral("uint32"), QStringLiteral("int32"),
                           QStringLiteral("float32"), QStringLiteral("float64")};
  if (!dtypes.contains(c->dtype) ||
      (c->byteOrder != QLatin1String("big") && c->byteOrder != QLatin1String("little")) ||
      (c->wordOrder != QLatin1String("big") && c->wordOrder != QLatin1String("little"))) {
    *error = QStringLiteral("寄存器数据类型或字节/字序无效");
    return false;
  }
  if (writing) {
    const QVariant raw = p.value(QStringLiteral("value"), 0);
    if (c->bits) {
      if (raw.userType() == QMetaType::QVariantList) {
        for (const QVariant& v : raw.toList())
          c->wireBits.push_back(v.toBool() || v.toInt() != 0 ? 1 : 0);
      } else {
        c->wireBits.push_back(raw.toBool() || raw.toInt() != 0 ? 1 : 0);
      }
      if (c->wireBits.isEmpty()) {
        *error = QStringLiteral("线圈使用 true / false");
        return false;
      }
      for (quint8 b : c->wireBits) c->values.push_back(bool(b));
      c->count = c->wireBits.size();
      c->wireCount = c->count;
    } else {
      QVariantList vals;
      if (raw.userType() == QMetaType::QVariantList)
        vals = raw.toList();
      else
        vals << raw;
      if (p.contains(QStringLiteral("values")) && p.value(QStringLiteral("values")).canConvert<QVariantList>() &&
          p.value(QStringLiteral("values")).userType() != QMetaType::QString &&
          !p.value(QStringLiteral("values")).toList().isEmpty())
        vals = p.value(QStringLiteral("values")).toList();
      if (!encodeValues(vals, c->dtype, c->byteOrder, c->wordOrder, &c->wireRegs, error))
        return false;
      if (!decodeRegisters(c->wireRegs, c->dtype, c->byteOrder, c->wordOrder, &c->values, error))
        return false;
      c->count = c->values.size();
      c->wireCount = c->wireRegs.size();
    }
  } else {
    c->count = p.value(QStringLiteral("count"), 1).toInt();
    if (c->count < 1 || c->count > 2000) {
      *error = QStringLiteral("count 必须是 1 到 2000 的整数");
      return false;
    }
    c->wireCount = c->bits ? c->count : c->count * widthOf(c->dtype);
    if (!c->bits && c->wireCount > 125) {
      *error = QStringLiteral("读取寄存器数量超过单帧上限");
      return false;
    }
  }
  if (c->transport == QLatin1String("tcp")) {
    c->host = p.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString().trimmed();
    if (c->host.isEmpty()) {
      *error = QStringLiteral("host 必须是 IP 或主机名，不包含协议和路径");
      return false;
    }
    c->port = p.value(QStringLiteral("port"), 502).toInt();
    if (c->port <= 0 || c->port > 65535) {
      *error = QStringLiteral("TCP 端口无效");
      return false;
    }
    // 本机软从站：1502/0 或显式空端口时改用已启动的回环端口。
    if ((c->port == 1502 || c->port == 0) &&
        (c->host == QLatin1String("127.0.0.1") || c->host == QLatin1String("localhost")) &&
        modbusSoftServer().running()) {
      const quint16 sp = modbusSoftServer().port();
      if (sp != 0) c->port = int(sp);
    }
  } else if (c->transport == QLatin1String("rtu")) {
    c->serialPort = p.value(QStringLiteral("serialPort")).toString().trimmed();
    if (c->serialPort.isEmpty() || c->serialPort == QLatin1String("ModbusRtuLoopback") ||
        c->serialPort == QLatin1String("rtu-loopback")) {
      QString e;
      if (!modbusRtuPeer().running() && !modbusRtuPeer().start(&e)) {
        *error = e.isEmpty() ? QStringLiteral("serialPort 必须是 COM 端口或 /dev/ 下的串口路径") : e;
        return false;
      }
      c->serialPort = modbusRtuPeer().slavePath();
    }
    if (c->serialPort.isEmpty() || !c->serialPort.startsWith(QLatin1String("/dev/"))) {
      *error = QStringLiteral("serialPort 必须是 COM 端口或 /dev/ 下的串口路径");
      return false;
    }
    c->baudrate = p.value(QStringLiteral("baudrate"), 19200).toInt();
    c->parity = p.value(QStringLiteral("parity"), QStringLiteral("N")).toString();
    c->stopbits = p.value(QStringLiteral("stopbits"), 1).toInt();
  }
  return true;
}

quint16 nextTxId() {
  static quint16 id = 1;
  return id++;
}

bool transactTcp(const Prepared& c, const QByteArray& reqPdu, QByteArray* rspPdu, QString* error) {
  const int fd = connectTcpTimeout(c.host, quint16(c.port), c.timeoutMs, error,
                                   QStringLiteral("Modbus"));
  if (fd < 0) return false;
  const quint16 tx = nextTxId();
  QByteArray mbap(7, 0);
  const int len = 1 + reqPdu.size();
  mbap[0] = char((tx >> 8) & 0xff);
  mbap[1] = char(tx & 0xff);
  mbap[4] = char((len >> 8) & 0xff);
  mbap[5] = char(len & 0xff);
  mbap[6] = char(c.deviceId);
  const QByteArray wire = mbap + reqPdu;
  int off = 0;
  while (off < wire.size()) {
    const ssize_t n = ::send(fd, wire.constData() + off, size_t(wire.size() - off), MSG_NOSIGNAL);
    if (n < 0) {
      if (errno == EINTR) continue;
      *error = (errno == EAGAIN || errno == EWOULDBLOCK)
                   ? QStringLiteral("Modbus 操作超时")
                   : QStringLiteral("Modbus 发送失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
      ::close(fd);
      return false;
    }
    off += int(n);
  }
  auto readExact = [&](int want, QByteArray* out) -> bool {
    out->clear();
    while (out->size() < want) {
      char tmp[512];
      const ssize_t n = ::recv(fd, tmp, size_t(want - out->size()), 0);
      if (n < 0) {
        if (errno == EINTR) continue;
        *error = (errno == EAGAIN || errno == EWOULDBLOCK)
                     ? QStringLiteral("Modbus 操作超时")
                     : QStringLiteral("Modbus 接收失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
        return false;
      }
      if (n == 0) {
        *error = QStringLiteral("Modbus 连接已关闭");
        return false;
      }
      out->append(tmp, int(n));
    }
    return true;
  };
  // MBAP 前 6 字节后的 Length 包含站号 + PDU，因此先读 6 再读 Length。
  QByteArray hdr;
  if (!readExact(6, &hdr)) {
    ::close(fd);
    return false;
  }
  const quint16 rtx = (quint16(quint8(hdr[0])) << 8) | quint8(hdr[1]);
  const quint16 proto = (quint16(quint8(hdr[2])) << 8) | quint8(hdr[3]);
  const quint16 rlen = (quint16(quint8(hdr[4])) << 8) | quint8(hdr[5]);
  if (rtx != tx || proto != 0 || rlen < 1 || rlen > 260) {
    *error = QStringLiteral("Modbus TCP 报文头无效");
    ::close(fd);
    return false;
  }
  QByteArray rest;
  if (!readExact(int(rlen), &rest)) {
    ::close(fd);
    return false;
  }
  ::close(fd);
  if (rest.isEmpty() || quint8(rest[0]) != quint8(c.deviceId)) {
    *error = QStringLiteral("Modbus TCP 站号不匹配");
    return false;
  }
  *rspPdu = rest.mid(1);
  return true;
}

// 简单的 termios 打开，仅服务 RTU 事务（与串口算子互相独立的路径）。
int openRtuPort(const Prepared& c, QString* error) {
  const QByteArray path = QFile::encodeName(c.serialPort);
  const int fd = ::open(path.constData(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd < 0) {
    *error = QStringLiteral("无法打开 RTU 串口 %1: %2")
                 .arg(c.serialPort, QString::fromLocal8Bit(strerror(errno)));
    return -1;
  }
  termios tio{};
  if (tcgetattr(fd, &tio) != 0) {
    *error = QStringLiteral("读取 RTU 串口属性失败");
    ::close(fd);
    return -1;
  }
  cfmakeraw(&tio);
  tio.c_cflag |= (CLOCAL | CREAD | CS8);
  tio.c_cflag &= ~(PARENB | PARODD);
  if (c.parity == QLatin1String("E"))
    tio.c_cflag |= PARENB;
  else if (c.parity == QLatin1String("O"))
    tio.c_cflag |= (PARENB | PARODD);
  if (c.stopbits >= 2)
    tio.c_cflag |= CSTOPB;
  else
    tio.c_cflag &= ~CSTOPB;
  speed_t spd = B19200;
#ifdef B115200
  if (c.baudrate == 115200) spd = B115200;
#endif
#ifdef B9600
  if (c.baudrate == 9600) spd = B9600;
#endif
  if (c.baudrate == 19200) spd = B19200;
#ifdef B38400
  if (c.baudrate == 38400) spd = B38400;
#endif
  cfsetispeed(&tio, spd);
  cfsetospeed(&tio, spd);
  tio.c_cc[VMIN] = 0;
  tio.c_cc[VTIME] = 0;
  if (tcsetattr(fd, TCSANOW, &tio) != 0) {
    *error = QStringLiteral("配置 RTU 串口失败");
    ::close(fd);
    return -1;
  }
  tcflush(fd, TCIOFLUSH);
  return fd;
}

bool transactRtu(const Prepared& c, const QByteArray& reqPdu, QByteArray* rspPdu, QString* error) {
  const int fd = openRtuPort(c, error);
  if (fd < 0) return false;
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::milliseconds(c.timeoutMs);
  QByteArray frame;
  frame.append(char(c.deviceId));
  frame.append(reqPdu);
  const quint16 crc = crc16Modbus(frame.constData(), frame.size());
  frame.append(char(crc & 0xff));
  frame.append(char((crc >> 8) & 0xff));
  if (!writeAllFd(fd, frame, deadline, error)) {
    ::close(fd);
    return false;
  }
  // RTU 以静默间隔结束一帧：先读最少 5 字节，再在短间隙内排空。
  QByteArray buf;
  if (!readExactFd(fd, 5, &buf, deadline, error)) {
    ::close(fd);
    return false;
  }
  while (true) {
    const auto now = std::chrono::steady_clock::now();
    if (now >= deadline) break;
    pollfd pfd{};
    pfd.fd = fd;
    pfd.events = POLLIN;
    const int gapMs = 20;
    const int rc = ::poll(&pfd, 1, gapMs);
    if (rc <= 0) break;
    char tmp[256];
    const ssize_t n = ::read(fd, tmp, sizeof(tmp));
    if (n > 0) buf.append(tmp, int(n));
    else break;
    if (buf.size() > 260) break;
  }
  ::close(fd);
  if (buf.size() < 5) {
    *error = QStringLiteral("Modbus RTU 应答过短");
    return false;
  }
  const quint16 got = quint16(quint8(buf[buf.size() - 2])) |
                      (quint16(quint8(buf[buf.size() - 1])) << 8);
  const quint16 expect = crc16Modbus(buf.constData(), buf.size() - 2);
  if (got != expect) {
    *error = QStringLiteral("Modbus RTU 校验失败");
    return false;
  }
  if (quint8(buf[0]) != quint8(c.deviceId)) {
    *error = QStringLiteral("Modbus RTU 站号不匹配");
    return false;
  }
  *rspPdu = buf.mid(1, buf.size() - 3);
  return true;
}

bool transact(const Prepared& c, const QByteArray& reqPdu, QByteArray* rspPdu, QString* error) {
  if (c.transport == QLatin1String("simulator")) {
    *rspPdu = handlePdu(reqPdu);
    return true;
  }
  if (c.transport == QLatin1String("tcp")) return transactTcp(c, reqPdu, rspPdu, error);
  return transactRtu(c, reqPdu, rspPdu, error);
}

void fillValues(ModbusResult* r, const Prepared& c, const QVariantList& values,
                const QVector<quint16>& regs) {
  r->values = values;
  r->count = values.size();
  r->value = values.size() == 1 ? values.first() : QVariant(values);
  if (!c.bits) {
    r->registers.clear();
    for (quint16 v : regs) r->registers.push_back(int(v));
  }
}

ModbusResult finishOk(ModbusResult r, const std::chrono::steady_clock::time_point& started) {
  r.ok = true;
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  if (r.note.isEmpty()) {
    r.note = QStringLiteral("%1 %2 %3[%4] n=%5")
                 .arg(r.protocol, r.action, r.area)
                 .arg(r.address)
                 .arg(r.count);
  }
  return r;
}

ModbusResult finishFail(ModbusResult r, const QString& e,
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

bool matchesPred(const QVariant& value, const QString& cmp, const QVariant& expected) {
  if (cmp == QLatin1String("is_true")) return value.toBool();
  if (cmp == QLatin1String("is_false")) return !value.toBool();
  const double a = value.toDouble();
  const double b = expected.toDouble();
  if (cmp == QLatin1String("eq")) return value == expected || qFuzzyCompare(a + 1.0, b + 1.0);
  if (cmp == QLatin1String("ne")) return value != expected && !qFuzzyCompare(a + 1.0, b + 1.0);
  if (cmp == QLatin1String("gt")) return a > b;
  if (cmp == QLatin1String("gte")) return a >= b;
  if (cmp == QLatin1String("lt")) return a < b;
  if (cmp == QLatin1String("lte")) return a <= b;
  return false;
}

void serveTcpClient(int cfd) {
  // 单次连接可处理多帧；对端关闭或超长空闲后退出。
  auto last = std::chrono::steady_clock::now();
  QByteArray buf;
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
    char tmp[512];
    const ssize_t n = ::recv(cfd, tmp, sizeof(tmp), 0);
    if (n <= 0) break;
    buf.append(tmp, int(n));
    last = std::chrono::steady_clock::now();
    while (buf.size() >= 7) {
      const int len = (quint8(buf[4]) << 8) | quint8(buf[5]);
      if (len < 1 || len > 260) {
        buf.clear();
        break;
      }
      if (buf.size() < 6 + len) break;
      const QByteArray frame = buf.left(6 + len);
      buf.remove(0, 6 + len);
      const QByteArray pdu = frame.mid(7);
      const QByteArray rsp = handlePdu(pdu);
      QByteArray out(7, 0);
      out[0] = frame[0];
      out[1] = frame[1];
      const int rlen = 1 + rsp.size();
      out[4] = char((rlen >> 8) & 0xff);
      out[5] = char(rlen & 0xff);
      out[6] = frame[6];
      out.append(rsp);
      const char* p = out.constData();
      int left = out.size();
      while (left > 0) {
        const ssize_t w = ::send(cfd, p, size_t(left), MSG_NOSIGNAL);
        if (w < 0) {
          if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) {
            pollfd wo{};
            wo.fd = cfd;
            wo.events = POLLOUT;
            ::poll(&wo, 1, 50);
            continue;
          }
          left = -1;
          break;
        }
        if (w == 0) {
          pollfd wo{};
          wo.fd = cfd;
          wo.events = POLLOUT;
          ::poll(&wo, 1, 50);
          continue;
        }
        p += w;
        left -= int(w);
      }
      if (left < 0) {
        ::close(cfd);
        return;
      }
    }
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
    // 从站对已接受连接使用阻塞 I/O，避免非阻塞 send 在无 poll 时空转。
    int flags = fcntl(cfd, F_GETFL, 0);
    if (flags >= 0) fcntl(cfd, F_SETFL, flags & ~O_NONBLOCK);
    std::thread([cfd]() { serveTcpClient(cfd); }).detach();
  }
}

void rtuPeerLoop() {
  QByteArray buf;
  auto lastRx = std::chrono::steady_clock::now();
  while (gRtuRun && gRtuMaster >= 0) {
    pollfd pfd{};
    pfd.fd = gRtuMaster;
    pfd.events = POLLIN;
    const int rc = ::poll(&pfd, 1, 15);
    if (rc > 0) {
      char tmp[256];
      const ssize_t n = ::read(gRtuMaster, tmp, sizeof(tmp));
      if (n > 0) {
        buf.append(tmp, int(n));
        lastRx = std::chrono::steady_clock::now();
      }
    }
    if (buf.size() < 5) continue;
    const auto gap = std::chrono::steady_clock::now() - lastRx;
    if (gap < std::chrono::milliseconds(15) && rc > 0) continue;
    if (buf.size() < 5) {
      buf.clear();
      continue;
    }
    const quint16 got = quint16(quint8(buf[buf.size() - 2])) |
                        (quint16(quint8(buf[buf.size() - 1])) << 8);
    const quint16 expect = crc16Modbus(buf.constData(), buf.size() - 2);
    if (got != expect) {
      buf.clear();
      continue;
    }
    const quint8 unit = quint8(buf[0]);
    const QByteArray pdu = buf.mid(1, buf.size() - 3);
    buf.clear();
    const QByteArray rsp = handlePdu(pdu);
    QByteArray frame;
    frame.append(char(unit));
    frame.append(rsp);
    const quint16 crc = crc16Modbus(frame.constData(), frame.size());
    frame.append(char(crc & 0xff));
    frame.append(char((crc >> 8) & 0xff));
    int off = 0;
    while (off < frame.size() && gRtuRun) {
      const ssize_t w = ::write(gRtuMaster, frame.constData() + off, size_t(frame.size() - off));
      if (w < 0) {
        if (errno == EAGAIN || errno == EINTR) {
          pollfd wo{};
          wo.fd = gRtuMaster;
          wo.events = POLLOUT;
          ::poll(&wo, 1, 20);
          continue;
        }
        return;
      }
      off += int(w);
    }
  }
}

}  // namespace

ModbusSoftServer& modbusSoftServer() {
  QMutexLocker lock(&gServerMutex);
  if (!gServer) gServer = new ModbusSoftServer();
  return *gServer;
}

bool ModbusSoftServer::start(quint16 port, QString* error) {
  if (gServerRun && gListenFd >= 0 && (port == 0 || port == gListenPort)) return true;
  if (gServerRun) stop();
  ensureStore();
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    if (error) *error = QStringLiteral("无法创建 Modbus 监听套接字");
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
      *error = QStringLiteral("无法绑定 Modbus 端口 %1: %2")
                   .arg(port)
                   .arg(QString::fromLocal8Bit(strerror(errno)));
    ::close(fd);
    return false;
  }
  if (::listen(fd, 8) != 0) {
    if (error) *error = QStringLiteral("Modbus 监听失败");
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

void ModbusSoftServer::stop() {
  gServerRun = false;
  if (gListenFd >= 0) {
    ::close(gListenFd);
    gListenFd = -1;
  }
  gListenPort = 0;
}

bool ModbusSoftServer::running() const { return gServerRun && gListenFd >= 0; }

quint16 ModbusSoftServer::port() const { return gListenPort; }

QString ModbusSoftServer::endpoint() const {
  return QStringLiteral("127.0.0.1:%1").arg(gListenPort);
}

ModbusRtuPeer& modbusRtuPeer() {
  QMutexLocker lock(&gRtuMutex);
  if (!gRtu) gRtu = new ModbusRtuPeer();
  return *gRtu;
}

bool ModbusRtuPeer::start(QString* error) {
  if (gRtuRun && gRtuMaster >= 0) return true;
  ensureStore();
  const int master = posix_openpt(O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (master < 0) {
    if (error)
      *error = QStringLiteral("无法创建 Modbus RTU PTY: %1")
                   .arg(QString::fromLocal8Bit(strerror(errno)));
    return false;
  }
  if (grantpt(master) != 0 || unlockpt(master) != 0) {
    if (error) *error = QStringLiteral("Modbus RTU PTY 授权失败");
    ::close(master);
    return false;
  }
  const char* name = ptsname(master);
  if (!name) {
    if (error) *error = QStringLiteral("无法读取 Modbus RTU PTY 路径");
    ::close(master);
    return false;
  }
  gRtuMaster = master;
  gRtuPath = QString::fromLocal8Bit(name);
  gRtuRun = true;
  std::thread(rtuPeerLoop).detach();
  return true;
}

void ModbusRtuPeer::stop() {
  gRtuRun = false;
  if (gRtuMaster >= 0) {
    ::close(gRtuMaster);
    gRtuMaster = -1;
  }
  gRtuPath.clear();
}

bool ModbusRtuPeer::running() const { return gRtuRun && gRtuMaster >= 0; }

QString ModbusRtuPeer::slavePath() const { return gRtuPath; }

ModbusResult runModbusRead(const QVariantMap& params) {
  const auto started = std::chrono::steady_clock::now();
  ModbusResult r;
  r.action = QStringLiteral("read");
  Prepared c;
  QString err;
  if (!prepareCommon(params, false, &c, &err)) return finishFail(r, err, started, false);
  r.protocol = QStringLiteral("modbus-%1").arg(c.transport);
  r.area = c.area;
  r.deviceId = c.deviceId;
  r.address = c.address;
  r.dataType = c.dtype;
  r.quality = QStringLiteral("good");
  QByteArray rsp;
  const QByteArray req = buildReadPdu(c.area, c.address, c.wireCount);
  if (!transact(c, req, &rsp, &err)) return finishFail(r, err, started, false);
  QVector<quint16> regs;
  QVector<quint8> bits;
  if (!parseReadResponse(rsp, c.bits, c.wireCount, &regs, &bits, &err))
    return finishFail(r, err, started, false);
  QVariantList values;
  if (c.bits) {
    for (quint8 b : bits) values.push_back(bool(b));
  } else if (!decodeRegisters(regs, c.dtype, c.byteOrder, c.wordOrder, &values, &err)) {
    return finishFail(r, err, started, false);
  }
  fillValues(&r, c, values, regs);
  return finishOk(r, started);
}

ModbusResult runModbusWrite(const QVariantMap& params) {
  const auto started = std::chrono::steady_clock::now();
  ModbusResult r;
  r.action = QStringLiteral("write");
  Prepared c;
  QString err;
  if (!prepareCommon(params, true, &c, &err)) return finishFail(r, err, started, false);
  r.protocol = QStringLiteral("modbus-%1").arg(c.transport);
  r.area = c.area;
  r.deviceId = c.deviceId;
  r.address = c.address;
  r.dataType = c.dtype;
  r.quality = QStringLiteral("good");
  const QByteArray req = buildWritePdu(c.bits, c.address, c.wireRegs, c.wireBits);
  QByteArray rsp;
  if (!transact(c, req, &rsp, &err)) return finishFail(r, err, started, true);
  if (!parseWriteResponse(rsp, c.bits, c.address, c.wireCount, c.wireRegs, c.wireBits, &err))
    return finishFail(r, err, started, true);
  r.acknowledged = true;
  fillValues(&r, c, c.values, c.wireRegs);
  r.note = QStringLiteral("设备已应答写请求；不等于物理动作完成。外部写入不会随流程变量回滚。");
  return finishOk(r, started);
}

ModbusResult runModbusWait(const QVariantMap& params) {
  const auto started = std::chrono::steady_clock::now();
  ModbusResult r;
  r.action = QStringLiteral("wait");
  Prepared c;
  QString err;
  QVariantMap readParams = params;
  readParams.insert(QStringLiteral("count"), 1);
  if (!prepareCommon(readParams, false, &c, &err)) return finishFail(r, err, started, false);
  r.protocol = QStringLiteral("modbus-%1").arg(c.transport);
  r.area = c.area;
  r.deviceId = c.deviceId;
  r.address = c.address;
  r.dataType = c.dtype;
  const QString cmp = params.value(QStringLiteral("comparison"), QStringLiteral("eq")).toString();
  const QVariant expected = params.value(QStringLiteral("expectedValue"), 123);
  if (c.bits) {
    if (cmp != QLatin1String("is_true") && cmp != QLatin1String("is_false"))
      return finishFail(r, QStringLiteral("线圈和离散输入请选择“开关为是”或“开关为否”"), started,
                        false);
  } else {
    const QStringList ok{QStringLiteral("eq"), QStringLiteral("ne"), QStringLiteral("gt"),
                         QStringLiteral("gte"), QStringLiteral("lt"), QStringLiteral("lte")};
    if (!ok.contains(cmp))
      return finishFail(r, QStringLiteral("寄存器请选择数值比较方式"), started, false);
  }
  const QString mode =
      params.value(QStringLiteral("triggerMode"), QStringLiteral("level")).toString();
  const QString policy =
      params.value(QStringLiteral("onTimeout"), QStringLiteral("error")).toString();
  if ((mode != QLatin1String("level") && mode != QLatin1String("rising") &&
       mode != QLatin1String("falling")) ||
      (policy != QLatin1String("error") && policy != QLatin1String("continue")))
    return finishFail(r, QStringLiteral("触发方式或超时处理无效"), started, false);
  const int waitMs = params.value(QStringLiteral("waitTimeoutMs"), 10000).toInt();
  const int interval = params.value(QStringLiteral("pollIntervalMs"), 100).toInt();
  const int stable = params.value(QStringLiteral("stableMs"), 0).toInt();
  if (waitMs < 100 || waitMs > 600000)
    return finishFail(r, QStringLiteral("waitTimeoutMs 无效"), started, false);
  if (interval < 20 || interval > 10000)
    return finishFail(r, QStringLiteral("pollIntervalMs 无效"), started, false);
  if (stable < 0 || stable >= waitMs)
    return finishFail(r, QStringLiteral("稳定时间必须小于等待超时"), started, false);

  r.expectedValue = expected;
  const auto deadline = started + std::chrono::milliseconds(waitMs);
  bool armed = mode == QLatin1String("level");
  std::chrono::steady_clock::time_point since{};
  bool hasSince = false;
  QVariant first, last;
  bool lastPred = false;
  int samples = 0;
  bool triggered = false;
  while (std::chrono::steady_clock::now() < deadline) {
    QByteArray rsp;
    const QByteArray req = buildReadPdu(c.area, c.address, c.wireCount);
    if (!transact(c, req, &rsp, &err)) return finishFail(r, err, started, false);
    QVector<quint16> regs;
    QVector<quint8> bits;
    if (!parseReadResponse(rsp, c.bits, c.wireCount, &regs, &bits, &err))
      return finishFail(r, err, started, false);
    QVariant cur;
    if (c.bits) {
      if (bits.isEmpty())
        return finishFail(r, QStringLiteral("设备返回的开关数量不足"), started, false);
      cur = bool(bits[0]);
    } else {
      QVariantList values;
      if (!decodeRegisters(regs, c.dtype, c.byteOrder, c.wordOrder, &values, &err))
        return finishFail(r, err, started, false);
      cur = values.isEmpty() ? QVariant() : values.first();
    }
    samples += 1;
    if (samples == 1) first = cur;
    last = cur;
    const bool pred = matchesPred(cur, cmp, expected);
    lastPred = pred;
    const auto now = std::chrono::steady_clock::now();
    if (now >= deadline) break;
    const bool desired = mode != QLatin1String("falling");
    if (pred != desired) {
      armed = true;
      hasSince = false;
    } else if (armed) {
      if (!hasSince) {
        since = now;
        hasSince = true;
      }
      if (now - since >= std::chrono::milliseconds(stable)) {
        triggered = true;
        break;
      }
    }
    const auto left = deadline - std::chrono::steady_clock::now();
    const int sleepMs =
        int(std::min<std::chrono::milliseconds>(std::chrono::milliseconds(interval),
                                                std::chrono::duration_cast<std::chrono::milliseconds>(
                                                    left > std::chrono::milliseconds(0)
                                                        ? left
                                                        : std::chrono::milliseconds(0)))
                .count());
    if (sleepMs > 0) std::this_thread::sleep_for(std::chrono::milliseconds(sleepMs));
  }
  r.samples = samples;
  r.firstValue = first;
  r.value = last;
  r.values = QVariantList{last};
  r.count = 1;
  r.triggered = triggered;
  r.passed = triggered;
  r.reason = triggered ? QStringLiteral("triggered") : QStringLiteral("timeout");
  r.quality = samples ? QStringLiteral("good") : QStringLiteral("no_sample");
  if (!triggered && policy == QLatin1String("error"))
    return finishFail(r,
                      QStringLiteral("等待 Modbus 信号超时（%1 ms，已采样 %2 次），未触发后续检测")
                          .arg(waitMs)
                          .arg(samples),
                      started, false);
  r.ok = true;
  r.note = triggered ? QStringLiteral("triggered value=%1 samples=%2").arg(last.toString()).arg(samples)
                     : QStringLiteral("timeout continue samples=%1").arg(samples);
  r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - started)
                        .count());
  Q_UNUSED(lastPred);
  return r;
}

QStringList modbusSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail) {
    if (!ok) fails << QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail);
  };

  {
    QVariantMap w;
    w.insert(QStringLiteral("transport"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("area"), QStringLiteral("holding"));
    w.insert(QStringLiteral("address"), 10);
    w.insert(QStringLiteral("value"), 4242);
    const ModbusResult wr = runModbusWrite(w);
    check("sim-write", wr.ok && wr.acknowledged && wr.value.toInt() == 4242,
          wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("transport"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("area"), QStringLiteral("holding"));
    r.insert(QStringLiteral("address"), 10);
    r.insert(QStringLiteral("count"), 1);
    const ModbusResult rr = runModbusRead(r);
    check("sim-readback", rr.ok && rr.value.toInt() == 4242,
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap w;
    w.insert(QStringLiteral("transport"), QStringLiteral("simulator"));
    w.insert(QStringLiteral("area"), QStringLiteral("coils"));
    w.insert(QStringLiteral("address"), 5);
    w.insert(QStringLiteral("value"), true);
    const ModbusResult wr = runModbusWrite(w);
    check("sim-coil-write", wr.ok, wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("transport"), QStringLiteral("simulator"));
    r.insert(QStringLiteral("area"), QStringLiteral("coils"));
    r.insert(QStringLiteral("address"), 5);
    const ModbusResult rr = runModbusRead(r);
    check("sim-coil-read", rr.ok && rr.value.toBool(),
          rr.ok ? rr.value.toString() : rr.error);
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("transport"), QStringLiteral("simulator"));
    p.insert(QStringLiteral("area"), QStringLiteral("holding"));
    p.insert(QStringLiteral("address"), 10);
    p.insert(QStringLiteral("comparison"), QStringLiteral("eq"));
    p.insert(QStringLiteral("expectedValue"), 4242);
    p.insert(QStringLiteral("waitTimeoutMs"), 1000);
    p.insert(QStringLiteral("pollIntervalMs"), 20);
    const ModbusResult wr = runModbusWait(p);
    check("sim-wait", wr.ok && wr.triggered && wr.value.toInt() == 4242,
          wr.ok ? wr.note : wr.error);
  }

  QString serr;
  bool started = false;
  for (int p = 1502; p <= 1506 && !started; ++p) {
    QString e;
    if (modbusSoftServer().start(quint16(p), &e)) started = true;
    else serr = e;
  }
  check("tcp-server", started, serr);
  if (started) {
    QVariantMap w;
    w.insert(QStringLiteral("transport"), QStringLiteral("tcp"));
    w.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    w.insert(QStringLiteral("port"), int(modbusSoftServer().port()));
    w.insert(QStringLiteral("area"), QStringLiteral("holding"));
    w.insert(QStringLiteral("address"), 20);
    w.insert(QStringLiteral("value"), 9001);
    w.insert(QStringLiteral("timeoutMs"), 1500);
    const ModbusResult wr = runModbusWrite(w);
    check("tcp-write", wr.ok && wr.acknowledged, wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("transport"), QStringLiteral("tcp"));
    r.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    r.insert(QStringLiteral("port"), int(modbusSoftServer().port()));
    r.insert(QStringLiteral("area"), QStringLiteral("holding"));
    r.insert(QStringLiteral("address"), 20);
    r.insert(QStringLiteral("timeoutMs"), 1500);
    const ModbusResult rr = runModbusRead(r);
    check("tcp-readback", rr.ok && rr.value.toInt() == 9001,
          rr.ok ? rr.value.toString() : rr.error);
  }

  QString rerr;
  const bool rtuOk = modbusRtuPeer().start(&rerr);
  check("rtu-pty", rtuOk, rerr);
  if (rtuOk) {
    QVariantMap w;
    w.insert(QStringLiteral("transport"), QStringLiteral("rtu"));
    w.insert(QStringLiteral("serialPort"), modbusRtuPeer().slavePath());
    w.insert(QStringLiteral("baudrate"), 115200);
    w.insert(QStringLiteral("area"), QStringLiteral("holding"));
    w.insert(QStringLiteral("address"), 30);
    w.insert(QStringLiteral("value"), 777);
    w.insert(QStringLiteral("timeoutMs"), 2000);
    const ModbusResult wr = runModbusWrite(w);
    check("rtu-write", wr.ok && wr.acknowledged, wr.ok ? wr.value.toString() : wr.error);
    QVariantMap r;
    r.insert(QStringLiteral("transport"), QStringLiteral("rtu"));
    r.insert(QStringLiteral("serialPort"), modbusRtuPeer().slavePath());
    r.insert(QStringLiteral("baudrate"), 115200);
    r.insert(QStringLiteral("area"), QStringLiteral("holding"));
    r.insert(QStringLiteral("address"), 30);
    r.insert(QStringLiteral("timeoutMs"), 2000);
    const ModbusResult rr = runModbusRead(r);
    check("rtu-readback", rr.ok && rr.value.toInt() == 777,
          rr.ok ? rr.value.toString() : rr.error);
  }
  return fails;
}

}  // namespace sieans_qt
