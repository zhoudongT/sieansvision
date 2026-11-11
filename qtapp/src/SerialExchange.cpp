#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "SerialExchange.hpp"

#include <QDir>
#include <QFileInfo>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonValue>
#include <QJsonParseError>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <thread>
#include <vector>

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <termios.h>
#include <unistd.h>

#ifndef CMSPAR
#define CMSPAR 010000000000
#endif
#ifndef TIOCEXCL
#define TIOCEXCL 0x540C
#endif
#ifndef TIOCOUTQ
#define TIOCOUTQ 0x5411
#endif
#ifndef TIOCMGET
#define TIOCMGET 0x5415
#endif
#ifndef TIOCMSET
#define TIOCMSET 0x5418
#endif
#ifndef TIOCM_DTR
#define TIOCM_DTR 0x002
#define TIOCM_RTS 0x004
#endif

namespace sieans_qt {
namespace {

constexpr int kMaxPayload = 65536;
constexpr int kSimMaxWire = 4096;

QMutex gPtyMutex;
SerialPtyLoopback* gPty = nullptr;

/** 返回距截止时刻的剩余秒数；已超时则返回 0。 */
double remainingSec(const std::chrono::steady_clock::time_point& deadline) {
  const auto now = std::chrono::steady_clock::now();
  if (now >= deadline) return 0.0;
  return std::chrono::duration<double>(deadline - now).count();
}

/** 按 catalog 分帧规则把报文体加上结束符或长度头。长度头不计自身。 */
QByteArray framePayload(const QByteArray& payload, const QString& framing) {
  if (framing == QLatin1String("raw") || framing.isEmpty()) return payload;
  if (framing == QLatin1String("lf")) return payload + QByteArray("\n");
  if (framing == QLatin1String("crlf")) return payload + QByteArray("\r\n");
  if (framing == QLatin1String("nul")) {
    QByteArray out = payload;
    out.append('\0');
    return out;
  }
  const bool be = framing.endsWith(QLatin1String("be"));
  int size = 0;
  if (framing.startsWith(QLatin1String("length16"))) size = 2;
  else if (framing.startsWith(QLatin1String("length32"))) size = 4;
  if (size <= 0) return payload;
  QByteArray out;
  const int n = payload.size();
  if (size == 2) {
    const quint16 v = static_cast<quint16>(n);
    if (be) {
      out.append(char((v >> 8) & 0xff));
      out.append(char(v & 0xff));
    } else {
      out.append(char(v & 0xff));
      out.append(char((v >> 8) & 0xff));
    }
  } else {
    const quint32 v = static_cast<quint32>(n);
    if (be) {
      out.append(char((v >> 24) & 0xff));
      out.append(char((v >> 16) & 0xff));
      out.append(char((v >> 8) & 0xff));
      out.append(char(v & 0xff));
    } else {
      out.append(char(v & 0xff));
      out.append(char((v >> 8) & 0xff));
      out.append(char((v >> 16) & 0xff));
      out.append(char((v >> 24) & 0xff));
    }
  }
  out.append(payload);
  return out;
}

struct FrameCut {
  bool ready = false;
  QByteArray payload;
  int trailing = 0;
  QString error;
};

/** 缓冲区已凑齐一帧时返回载荷与尾随字节数；未凑齐且未超限则 ready=false。 */
FrameCut completeFrame(const QByteArray& buffer, const QString& framing, int maximum,
                       int expected) {
  FrameCut cut;
  auto overflow = [&]() {
    cut.error = QStringLiteral("接收数据超过字节上限");
    return cut;
  };
  if (framing == QLatin1String("lf") || framing == QLatin1String("crlf") ||
      framing == QLatin1String("nul")) {
    const QByteArray delim = framing == QLatin1String("crlf")
                                 ? QByteArray("\r\n")
                                 : (framing == QLatin1String("lf") ? QByteArray("\n")
                                                                   : QByteArray(1, '\0'));
    const int end = buffer.indexOf(delim);
    if (end >= 0) {
      if (end > maximum) return overflow();
      cut.ready = true;
      cut.payload = buffer.left(end);
      cut.trailing = buffer.size() - end - delim.size();
      return cut;
    }
    if (buffer.size() > maximum + delim.size() - 1) return overflow();
    return cut;
  }
  int size = 0;
  bool be = true;
  if (framing.startsWith(QLatin1String("length16"))) {
    size = 2;
    be = framing.endsWith(QLatin1String("be"));
  } else if (framing.startsWith(QLatin1String("length32"))) {
    size = 4;
    be = framing.endsWith(QLatin1String("be"));
  }
  if (size > 0) {
    if (buffer.size() < size) return cut;
    quint32 length = 0;
    const auto* u = reinterpret_cast<const unsigned char*>(buffer.constData());
    if (size == 2) {
      length = be ? (quint32(u[0]) << 8) | u[1] : (quint32(u[1]) << 8) | u[0];
    } else {
      length = be ? (quint32(u[0]) << 24) | (quint32(u[1]) << 16) | (quint32(u[2]) << 8) | u[3]
                  : (quint32(u[3]) << 24) | (quint32(u[2]) << 16) | (quint32(u[1]) << 8) | u[0];
    }
    if (static_cast<int>(length) > maximum) {
      cut.error = QStringLiteral("长度前缀超过接收字节上限");
      return cut;
    }
    if (buffer.size() >= size + static_cast<int>(length)) {
      cut.ready = true;
      cut.payload = buffer.mid(size, int(length));
      cut.trailing = buffer.size() - size - int(length);
    }
    return cut;
  }
  if (framing == QLatin1String("fixed")) {
    if (expected < 1 || expected > maximum) {
      cut.error = QStringLiteral("应答字节数无效");
      return cut;
    }
    if (buffer.size() >= expected) {
      cut.ready = true;
      cut.payload = buffer.left(expected);
      cut.trailing = buffer.size() - expected;
    }
    return cut;
  }
  cut.error = QStringLiteral("串口接收分帧方式无效");
  return cut;
}

/** 把 value 按 text / structured / bytes 编码为报文体。 */
bool encodeValue(const QVariant& value, const QString& encoding, QByteArray* out,
                 QString* error) {
  if (encoding == QLatin1String("bytes")) {
    QByteArray raw;
    if (value.typeId() == QMetaType::QByteArray) {
      raw = value.toByteArray();
    } else if (value.canConvert<QVariantList>() && value.userType() != QMetaType::QString) {
      const QVariantList lst = value.toList();
      raw.reserve(lst.size());
      for (const QVariant& n : lst) {
        bool ok = false;
        const int v = n.toInt(&ok);
        if (!ok || v < 0 || v > 255) {
          *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
          return false;
        }
        raw.append(char(v));
      }
    } else {
      const QString s = value.toString().trimmed();
      if (s.startsWith(QLatin1Char('['))) {
        QJsonParseError pe;
        const QJsonDocument doc = QJsonDocument::fromJson(s.toUtf8(), &pe);
        if (pe.error != QJsonParseError::NoError || !doc.isArray()) {
          *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
          return false;
        }
        for (const QJsonValue& jv : doc.array()) {
          const int v = jv.toInt(-1);
          if (v < 0 || v > 255) {
            *error = QStringLiteral("字节消息须为 0–255 的数值数组，最多 64 KiB");
            return false;
          }
          raw.append(char(v));
        }
      } else {
        // 允许 "01 0A FF" 或 "010AFF" 十六进制，便于属性面板录入。
        QString hex = s;
        hex.remove(QLatin1Char(' '));
        hex.remove(QLatin1Char(','));
        if (hex.size() % 2 != 0 || hex.isEmpty()) {
          *error = QStringLiteral("字节消息须为 0–255 的数值数组或十六进制文本");
          return false;
        }
        raw = QByteArray::fromHex(hex.toLatin1());
        if (raw.size() * 2 != hex.size()) {
          *error = QStringLiteral("字节消息须为 0–255 的数值数组或十六进制文本");
          return false;
        }
      }
    }
    if (raw.size() > kMaxPayload) {
      *error = QStringLiteral("消息体超过 64 KiB");
      return false;
    }
    *out = raw;
    return true;
  }
  if (encoding == QLatin1String("structured")) {
    QByteArray raw;
    if (value.typeId() == QMetaType::QVariantMap || value.typeId() == QMetaType::QVariantList ||
        value.userType() == QMetaType::QJsonObject || value.userType() == QMetaType::QJsonArray) {
      raw = QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);
    } else {
      const QString s = value.toString();
      QJsonParseError pe;
      const QJsonDocument doc = QJsonDocument::fromJson(s.toUtf8(), &pe);
      if (pe.error != QJsonParseError::NoError) {
        *error = QStringLiteral("消息不是有效的结构化数据，请检查发送格式或选择文本");
        return false;
      }
      raw = doc.toJson(QJsonDocument::Compact);
    }
    if (raw.size() > kMaxPayload) {
      *error = QStringLiteral("消息体超过 64 KiB");
      return false;
    }
    *out = raw;
    return true;
  }
  // text
  const QByteArray raw = value.toString().toUtf8();
  if (raw.size() > kMaxPayload) {
    *error = QStringLiteral("消息体超过 64 KiB");
    return false;
  }
  *out = raw;
  return true;
}

/** 按接收编码把载荷解码为文本 / JSON / 字节数组。 */
bool decodePayload(const QByteArray& payload, const QString& encoding, QVariant* decoded,
                   QString* text, QString* error) {
  if (payload.size() > kMaxPayload) {
    *error = QStringLiteral("收到的消息体超过 64 KiB");
    return false;
  }
  if (encoding == QLatin1String("bytes")) {
    QVariantList lst;
    lst.reserve(payload.size());
    for (unsigned char c : payload) lst.push_back(int(c));
    *decoded = lst;
    *text = QString::fromLatin1(payload.toHex(' '));
    return true;
  }
  const QString s = QString::fromUtf8(payload);
  // fromUtf8 替换非法序列；严格检查是否为有效 UTF-8。
  if (s.toUtf8() != payload) {
    *error = QStringLiteral("消息不是有效 UTF-8 文本，请选择字节数组");
    return false;
  }
  if (encoding == QLatin1String("structured")) {
    QJsonParseError pe;
    const QJsonDocument doc = QJsonDocument::fromJson(payload, &pe);
    if (pe.error != QJsonParseError::NoError) {
      *error = QStringLiteral("消息不是有效的结构化数据，请检查发送格式或选择文本");
      return false;
    }
    *decoded = doc.toVariant();
    *text = QString::fromUtf8(doc.toJson(QJsonDocument::Compact));
    return true;
  }
  *decoded = s;
  *text = s;
  return true;
}

/** 在截止时刻前轮询 fd 的可读/可写事件。 */
bool pollWait(int fd, short events, const std::chrono::steady_clock::time_point& deadline,
              QString* error) {
  const double left = remainingSec(deadline);
  if (left <= 0) {
    *error = QStringLiteral("串口操作超时，未完成完整报文收发");
    return false;
  }
  pollfd pfd{};
  pfd.fd = fd;
  pfd.events = events;
  const int ms = std::max(1, int(left * 1000));
  const int rc = ::poll(&pfd, 1, ms);
  if (rc == 0) {
    *error = QStringLiteral("串口操作超时，未完成完整报文收发");
    return false;
  }
  if (rc < 0) {
    if (errno == EINTR) return pollWait(fd, events, deadline, error);
    *error = QStringLiteral("串口等待失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
    return false;
  }
  return true;
}

/** 在截止前尽量写完 buffer。 */
bool writeAll(int fd, const QByteArray& buf, const std::chrono::steady_clock::time_point& deadline,
              int* wrote, QString* error) {
  int off = 0;
  while (off < buf.size()) {
    if (!pollWait(fd, POLLOUT, deadline, error)) return false;
    const ssize_t n = ::write(fd, buf.constData() + off, size_t(buf.size() - off));
    if (n < 0) {
      if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) continue;
      *error = QStringLiteral("串口写入失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
      return false;
    }
    if (n == 0) {
      *error = QStringLiteral("串口写入未取得进展");
      return false;
    }
    off += int(n);
    *wrote = off;
  }
  // 等待驱动发送队列排空，但不在截止后无限阻塞。
  while (remainingSec(deadline) > 0) {
    int queued = 0;
    if (ioctl(fd, TIOCOUTQ, &queued) != 0 || queued <= 0) break;
    pollfd pfd{};
    pfd.fd = fd;
    pfd.events = POLLOUT;
    ::poll(&pfd, 1, std::min(5, int(remainingSec(deadline) * 1000)));
  }
  return true;
}

/** 将整数波特率映射到 termios 常量；非常用速率在 Linux 上再尝试 CBAUD 扩展。 */
bool applyBaud(termios* tio, int baud, QString* error) {
  speed_t spd = B0;
  switch (baud) {
    case 300: spd = B300; break;
    case 600: spd = B600; break;
    case 1200: spd = B1200; break;
    case 2400: spd = B2400; break;
    case 4800: spd = B4800; break;
    case 9600: spd = B9600; break;
    case 19200: spd = B19200; break;
    case 38400: spd = B38400; break;
#ifdef B57600
    case 57600: spd = B57600; break;
#endif
#ifdef B115200
    case 115200: spd = B115200; break;
#endif
#ifdef B230400
    case 230400: spd = B230400; break;
#endif
#ifdef B460800
    case 460800: spd = B460800; break;
#endif
#ifdef B500000
    case 500000: spd = B500000; break;
#endif
#ifdef B921600
    case 921600: spd = B921600; break;
#endif
#ifdef B1000000
    case 1000000: spd = B1000000; break;
#endif
#ifdef B1152000
    case 1152000: spd = B1152000; break;
#endif
#ifdef B1500000
    case 1500000: spd = B1500000; break;
#endif
#ifdef B2000000
    case 2000000: spd = B2000000; break;
#endif
#ifdef B3000000
    case 3000000: spd = B3000000; break;
#endif
#ifdef B4000000
    case 4000000: spd = B4000000; break;
#endif
    default:
      *error = QStringLiteral("当前系统不支持波特率 %1").arg(baud);
      return false;
  }
  if (cfsetispeed(tio, spd) != 0 || cfsetospeed(tio, spd) != 0) {
    *error = QStringLiteral("设置波特率失败");
    return false;
  }
  return true;
}

/** 配置数据位、校验、停止位、流控，并打开原始模式。 */
bool configurePort(int fd, int baud, int dataBits, const QString& parity, double stopbits,
                   const QString& flow, bool rts, bool dtr, QString* error) {
  termios tio{};
  if (tcgetattr(fd, &tio) != 0) {
    *error = QStringLiteral("读取串口属性失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
    return false;
  }
  cfmakeraw(&tio);
  tio.c_cflag |= (CLOCAL | CREAD);
  tio.c_cflag &= ~CSIZE;
  switch (dataBits) {
    case 5: tio.c_cflag |= CS5; break;
    case 6: tio.c_cflag |= CS6; break;
    case 7: tio.c_cflag |= CS7; break;
    default: tio.c_cflag |= CS8; break;
  }
  tio.c_cflag &= ~(PARENB | PARODD | CMSPAR);
  if (parity == QLatin1String("E")) {
    tio.c_cflag |= PARENB;
  } else if (parity == QLatin1String("O")) {
    tio.c_cflag |= (PARENB | PARODD);
  } else if (parity == QLatin1String("M")) {
    tio.c_cflag |= (PARENB | PARODD | CMSPAR);
  } else if (parity == QLatin1String("S")) {
    tio.c_cflag |= (PARENB | CMSPAR);
  }
  if (stopbits > 1.0)
    tio.c_cflag |= CSTOPB;
  else
    tio.c_cflag &= ~CSTOPB;
  tio.c_iflag &= ~(IXON | IXOFF | IXANY);
  tio.c_cflag &= ~CRTSCTS;
  if (flow == QLatin1String("rtscts") || flow == QLatin1String("dsrdtr"))
    tio.c_cflag |= CRTSCTS;
  else if (flow == QLatin1String("xonxoff"))
    tio.c_iflag |= (IXON | IXOFF);
  tio.c_cc[VMIN] = 0;
  tio.c_cc[VTIME] = 0;
  if (!applyBaud(&tio, baud, error)) return false;
  if (tcsetattr(fd, TCSANOW, &tio) != 0) {
    *error = QStringLiteral("配置串口失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
    return false;
  }
  int mflags = 0;
  if (ioctl(fd, TIOCMGET, &mflags) == 0) {
    if (dtr)
      mflags |= TIOCM_DTR;
    else
      mflags &= ~TIOCM_DTR;
    if (rts)
      mflags |= TIOCM_RTS;
    else
      mflags &= ~TIOCM_RTS;
    ioctl(fd, TIOCMSET, &mflags);
  }
  ioctl(fd, TIOCEXCL);
  return true;
}

int openDevice(const QString& path, QString* error) {
  const QByteArray p = QFile::encodeName(path);
  const int fd = ::open(p.constData(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd < 0) {
    *error = QStringLiteral("无法打开串口 %1: %2")
                 .arg(path, QString::fromLocal8Bit(strerror(errno)));
    return -1;
  }
  return fd;
}

}  // namespace

QStringList listSerialPorts() {
  QStringList out;
  const QStringList globs = {
      QStringLiteral("/dev/ttyUSB*"), QStringLiteral("/dev/ttyACM*"),
      QStringLiteral("/dev/ttyAMA*"), QStringLiteral("/dev/ttyS*"),
      QStringLiteral("/dev/ttyXRUSB*"), QStringLiteral("/dev/ttymxc*")};
  for (const QString& g : globs) {
    const QFileInfoList infos =
        QDir(QFileInfo(g).absolutePath())
            .entryInfoList(QStringList{QFileInfo(g).fileName()}, QDir::System | QDir::Files);
    for (const QFileInfo& fi : infos) {
      const QString p = fi.absoluteFilePath();
      if (!out.contains(p)) out << p;
    }
  }
  const QString pty = serialPtyLoopback().slavePath();
  if (!pty.isEmpty() && !out.contains(pty)) out.prepend(pty);
  out.sort();
  return out;
}

SerialPtyLoopback& serialPtyLoopback() {
  QMutexLocker lock(&gPtyMutex);
  if (!gPty) gPty = new SerialPtyLoopback();
  return *gPty;
}

bool SerialPtyLoopback::start(QString* error) {
  if (running_ && masterFd_ >= 0) return true;
  const int master = posix_openpt(O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (master < 0) {
    if (error)
      *error = QStringLiteral("无法创建 PTY: %1").arg(QString::fromLocal8Bit(strerror(errno)));
    return false;
  }
  if (grantpt(master) != 0 || unlockpt(master) != 0) {
    if (error)
      *error = QStringLiteral("PTY 授权失败: %1").arg(QString::fromLocal8Bit(strerror(errno)));
    ::close(master);
    return false;
  }
  const char* name = ptsname(master);
  if (!name) {
    if (error) *error = QStringLiteral("无法读取 PTY 从设备路径");
    ::close(master);
    return false;
  }
  // 不长期占用从设备描述符，以便算子每次执行都能独占打开。
  // 算子打开后会自行配置原始模式；主端线程只负责把字节写回。
  masterFd_ = master;
  slaveFd_ = -1;
  slavePath_ = QString::fromLocal8Bit(name);
  running_ = true;
  std::thread([this]() { peerLoop(); }).detach();
  return true;
}

void SerialPtyLoopback::stop() {
  running_ = false;
  if (masterFd_ >= 0) {
    ::close(masterFd_);
    masterFd_ = -1;
  }
  if (slaveFd_ >= 0) {
    ::close(slaveFd_);
    slaveFd_ = -1;
  }
  slavePath_.clear();
}

bool SerialPtyLoopback::running() const { return running_ && masterFd_ >= 0; }

QString SerialPtyLoopback::slavePath() const { return slavePath_; }

void SerialPtyLoopback::peerLoop() {
  // 读到的字节立即写回主端，模拟环回插头；对端关闭或 stop() 后退出。
  char buf[1024];
  while (running_ && masterFd_ >= 0) {
    pollfd pfd{};
    pfd.fd = masterFd_;
    pfd.events = POLLIN;
    const int rc = ::poll(&pfd, 1, 50);
    if (!running_) break;
    if (rc <= 0) continue;
    const ssize_t n = ::read(masterFd_, buf, sizeof(buf));
    if (n < 0) {
      if (errno == EAGAIN || errno == EINTR) continue;
      break;
    }
    if (n == 0) break;
    ssize_t off = 0;
    while (off < n && running_) {
      const ssize_t w = ::write(masterFd_, buf + off, size_t(n - off));
      if (w < 0) {
        if (errno == EAGAIN || errno == EINTR) {
          pollfd wo{};
          wo.fd = masterFd_;
          wo.events = POLLOUT;
          ::poll(&wo, 1, 20);
          continue;
        }
        return;
      }
      off += w;
    }
  }
}

SerialResult runSerialExchange(const QVariantMap& params) {
  SerialResult r;
  const auto started = std::chrono::steady_clock::now();
  auto finish = [&]() {
    r.elapsedMs = int(std::chrono::duration<double, std::milli>(
                          std::chrono::steady_clock::now() - started)
                          .count());
    if (r.ok && r.note.isEmpty()) {
      r.note = QStringLiteral("%1 %2 %3B")
                   .arg(r.simulated ? QStringLiteral("回环") : r.serialPort, r.mode)
                   .arg(r.mode == QLatin1String("send") ? r.sentBytes : r.byteLength);
    }
    return r;
  };
  auto fail = [&](const QString& e) {
    r.ok = false;
    r.error = e;
    r.note = e;
    return finish();
  };

  r.mode = params.value(QStringLiteral("mode"), QStringLiteral("exchange")).toString();
  if (r.mode != QLatin1String("exchange") && r.mode != QLatin1String("send") &&
      r.mode != QLatin1String("receive"))
    return fail(QStringLiteral("串口通信方式无效"));
  const bool sending = r.mode != QLatin1String("receive");
  const bool receiving = r.mode != QLatin1String("send");

  const QString connection =
      params.value(QStringLiteral("connection"), QStringLiteral("simulator")).toString();
  r.simulated = connection == QLatin1String("simulator");
  if (connection != QLatin1String("simulator") && connection != QLatin1String("device"))
    return fail(QStringLiteral("串口连接方式无效"));
  if (r.simulated && r.mode == QLatin1String("receive"))
    return fail(QStringLiteral("回环模拟需要先发送，请选择请求应答或仅发送"));

  int timeoutMs = params.value(QStringLiteral("timeoutMs"), 3000).toInt();
  if (timeoutMs < 100 || timeoutMs > 10000)
    return fail(QStringLiteral("串口超时必须为 100–10000 ms"));
  int maximum = params.value(QStringLiteral("maxBytes"), 65536).toInt();
  if (maximum < 1 || maximum > kMaxPayload) return fail(QStringLiteral("接收字节上限无效"));

  const QString txFraming =
      params.value(QStringLiteral("txFraming"), QStringLiteral("crlf")).toString();
  const QString rxFraming =
      params.value(QStringLiteral("rxFraming"), QStringLiteral("crlf")).toString();
  if (receiving && rxFraming == QLatin1String("eof"))
    return fail(QStringLiteral("串口没有 EOF 报文边界，请设置结束符、长度头或固定字节数"));
  if (receiving) {
    const FrameCut probe = completeFrame(QByteArray(), rxFraming, maximum,
                                         params.value(QStringLiteral("responseBytes"), 8).toInt());
    if (!probe.error.isEmpty() && rxFraming != QLatin1String("fixed") &&
        !rxFraming.startsWith(QLatin1String("length")) &&
        rxFraming != QLatin1String("lf") && rxFraming != QLatin1String("crlf") &&
        rxFraming != QLatin1String("nul"))
      return fail(probe.error);
    if (rxFraming != QLatin1String("lf") && rxFraming != QLatin1String("crlf") &&
        rxFraming != QLatin1String("nul") && !rxFraming.startsWith(QLatin1String("length")) &&
        rxFraming != QLatin1String("fixed"))
      return fail(QStringLiteral("串口接收分帧方式无效"));
  }

  r.encoding = receiving ? params.value(QStringLiteral("responseEncoding"),
                                        params.value(QStringLiteral("encoding"),
                                                     QStringLiteral("text")))
                               .toString()
                         : params.value(QStringLiteral("encoding"), QStringLiteral("text"))
                               .toString();
  r.sentEncoding =
      sending ? params.value(QStringLiteral("encoding"), QStringLiteral("text")).toString()
              : QString();
  const QStringList encOk{QStringLiteral("text"), QStringLiteral("structured"),
                          QStringLiteral("bytes")};
  if (!encOk.contains(r.encoding) || (sending && !encOk.contains(r.sentEncoding)))
    return fail(QStringLiteral("接收内容格式无效"));

  r.baudrate = r.simulated ? 115200 : params.value(QStringLiteral("baudrate"), 115200).toInt();
  r.dataBits = r.simulated ? 8 : params.value(QStringLiteral("dataBits"), 8).toInt();
  r.parity = r.simulated ? QStringLiteral("N")
                         : params.value(QStringLiteral("parity"), QStringLiteral("N")).toString();
  r.stopbits = r.simulated ? 1.0 : params.value(QStringLiteral("stopbits"), 1).toDouble();
  r.flowControl = r.simulated
                      ? QStringLiteral("none")
                      : params.value(QStringLiteral("flowControl"), QStringLiteral("none"))
                            .toString();
  const bool rts = r.simulated ? true : params.value(QStringLiteral("rts"), true).toBool();
  const bool dtr = r.simulated ? true : params.value(QStringLiteral("dtr"), true).toBool();
  if (!r.simulated) {
    if (r.baudrate < 300 || r.baudrate > 4000000)
      return fail(QStringLiteral("波特率须为 300–4000000 的整数"));
    if (r.dataBits < 5 || r.dataBits > 8) return fail(QStringLiteral("数据位须为 5、6、7 或 8"));
    const QStringList parOk{QStringLiteral("N"), QStringLiteral("E"), QStringLiteral("O"),
                            QStringLiteral("M"), QStringLiteral("S")};
    if (!parOk.contains(r.parity)) return fail(QStringLiteral("校验位无效"));
    if (!(std::fabs(r.stopbits - 1.0) < 1e-6 || std::fabs(r.stopbits - 1.5) < 1e-6 ||
          std::fabs(r.stopbits - 2.0) < 1e-6))
      return fail(QStringLiteral("停止位须为 1、1.5 或 2"));
    const QStringList flOk{QStringLiteral("none"), QStringLiteral("rtscts"),
                           QStringLiteral("xonxoff"), QStringLiteral("dsrdtr")};
    if (!flOk.contains(r.flowControl)) return fail(QStringLiteral("串口流控无效"));
  }

  QByteArray body;
  if (sending) {
    QString encErr;
    const QVariant value = params.contains(QStringLiteral("value"))
                               ? params.value(QStringLiteral("value"))
                               : QVariant(QStringLiteral("SIEANS-SERIAL-00042"));
    if (!encodeValue(value, r.sentEncoding, &body, &encErr)) return fail(encErr);
    r.value = value.toString();
    r.sentValue = r.value;
  }

  const QByteArray wire = sending ? framePayload(body, txFraming) : QByteArray();
  if (sending && (wire.size() > (r.simulated ? kSimMaxWire : (kMaxPayload + 4))))
    return fail(r.simulated ? QStringLiteral("回环模拟报文含头部最多 4096 字节，真实端口支持 64 KiB 内容")
                            : QStringLiteral("发送报文超过上限"));
  r.sentWire = wire;

  QString portName;
  if (r.simulated) {
    portName = QStringLiteral("回环模拟");
  } else {
    portName = params.value(QStringLiteral("serialPort")).toString().trimmed();
    if (portName.isEmpty() || portName == QLatin1String("SerialLoopback") ||
        portName == QLatin1String("pty-loopback") || portName == QLatin1String("loopback")) {
      QString ptyErr;
      if (!serialPtyLoopback().running() && !serialPtyLoopback().start(&ptyErr))
        return fail(ptyErr.isEmpty() ? QStringLiteral("串口路径无效") : ptyErr);
      portName = serialPtyLoopback().slavePath();
    }
    if (portName.isEmpty() || portName.size() > 1024 || portName.contains(QLatin1String("://")))
      return fail(QStringLiteral("串口路径无效"));
    if (!portName.startsWith(QLatin1String("/dev/")))
      return fail(QStringLiteral("串口路径须位于 /dev/，例如 /dev/ttyUSB0"));
  }
  r.serialPort = portName;

  const bool clearInput =
      sending ? params.value(QStringLiteral("clearInput"), false).toBool() : false;
  const int responseBytes = params.value(QStringLiteral("responseBytes"), 8).toInt();
  const auto deadline = started + std::chrono::milliseconds(timeoutMs);
  bool sentAny = false;

  if (r.simulated) {
    r.sentBytes = wire.size();
    sentAny = sending && !wire.isEmpty();
    if (receiving) {
      const FrameCut cut = completeFrame(wire, rxFraming, maximum, responseBytes);
      if (!cut.error.isEmpty()) return fail(cut.error);
      if (!cut.ready) return fail(QStringLiteral("串口操作超时，未完成完整报文收发"));
      QString decErr;
      if (!decodePayload(cut.payload, r.encoding, &r.decoded, &r.value, &decErr))
        return fail(decErr);
      r.payload = cut.payload;
      r.trailingBytes = cut.trailing;
      r.byteLength = cut.payload.size();
      r.delivery = QStringLiteral("received");
    } else {
      r.delivery = QStringLiteral("sent");
      r.byteLength = body.size();
    }
    r.ok = true;
    return finish();
  }

  QString openErr;
  const int fd = openDevice(portName, &openErr);
  if (fd < 0) return fail(openErr);
  auto closer = [&]() { ::close(fd); };
  if (!configurePort(fd, r.baudrate, r.dataBits, r.parity, r.stopbits, r.flowControl, rts, dtr,
                     &openErr)) {
    closer();
    return fail(openErr);
  }
  if (remainingSec(deadline) <= 0) {
    closer();
    return fail(QStringLiteral("串口操作超时，未完成完整报文收发"));
  }
  if (sending && clearInput) {
    // 发送前丢弃已在驱动缓冲中的旧数据，避免上一帧残渣被当成应答。
    int avail = 0;
#ifdef FIONREAD
    ioctl(fd, FIONREAD, &avail);
#endif
    r.discardedInputBytes = std::max(0, avail);
    tcflush(fd, TCIFLUSH);
  }
  if (sending) {
    int wrote = 0;
    if (!writeAll(fd, wire, deadline, &wrote, &openErr)) {
      r.sentBytes = wrote;
      closer();
      return fail(openErr + QStringLiteral("；数据可能已经发出，不能回滚，未自动重试"));
    }
    r.sentBytes = wrote;
    sentAny = wrote > 0;
  }
  if (receiving) {
    QByteArray buffer;
    buffer.reserve(std::min(maximum + 16, 8192));
    while (true) {
      if (remainingSec(deadline) <= 0) {
        closer();
        return fail(QStringLiteral("串口操作超时，未完成完整报文收发") +
                    (sentAny ? QStringLiteral("；数据可能已经发出，不能回滚，未自动重试")
                             : QString()));
      }
      if (!pollWait(fd, POLLIN, deadline, &openErr)) {
        closer();
        return fail(openErr + (sentAny ? QStringLiteral("；数据可能已经发出，不能回滚，未自动重试")
                                       : QString()));
      }
      char tmp[4096];
      const ssize_t n = ::read(fd, tmp, sizeof(tmp));
      if (n < 0) {
        if (errno == EAGAIN || errno == EINTR) continue;
        closer();
        return fail(QStringLiteral("串口读取失败: %1")
                        .arg(QString::fromLocal8Bit(strerror(errno))));
      }
      if (n > 0) buffer.append(tmp, int(n));
      const FrameCut cut = completeFrame(buffer, rxFraming, maximum, responseBytes);
      if (!cut.error.isEmpty()) {
        closer();
        return fail(cut.error);
      }
      if (cut.ready) {
        QString decErr;
        if (!decodePayload(cut.payload, r.encoding, &r.decoded, &r.value, &decErr)) {
          closer();
          return fail(decErr);
        }
        r.payload = cut.payload;
        r.trailingBytes = cut.trailing;
        r.byteLength = cut.payload.size();
        r.delivery = QStringLiteral("received");
        break;
      }
    }
  } else {
    r.delivery = QStringLiteral("sent");
    r.byteLength = body.size();
  }
  closer();
  r.ok = true;
  return finish();
}

QStringList serialSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail) {
    if (!ok) fails << QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail);
  };

  {
    QVariantMap p;
    p.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    p.insert(QStringLiteral("mode"), QStringLiteral("exchange"));
    p.insert(QStringLiteral("value"), QStringLiteral("SIEANS-SERIAL-00042"));
    p.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    p.insert(QStringLiteral("txFraming"), QStringLiteral("crlf"));
    p.insert(QStringLiteral("rxFraming"), QStringLiteral("crlf"));
    const SerialResult r = runSerialExchange(p);
    check("sim-exchange", r.ok && r.value == QLatin1String("SIEANS-SERIAL-00042") &&
                              r.simulated && r.sentBytes > 0,
          r.ok ? QStringLiteral("value=%1 sent=%2").arg(r.value).arg(r.sentBytes) : r.error);
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    p.insert(QStringLiteral("mode"), QStringLiteral("send"));
    p.insert(QStringLiteral("value"), QStringLiteral("PING"));
    p.insert(QStringLiteral("txFraming"), QStringLiteral("lf"));
    const SerialResult r = runSerialExchange(p);
    check("sim-send", r.ok && r.delivery == QLatin1String("sent") && r.sentBytes == 5,
          r.ok ? QStringLiteral("sent=%1").arg(r.sentBytes) : r.error);
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    p.insert(QStringLiteral("mode"), QStringLiteral("receive"));
    const SerialResult r = runSerialExchange(p);
    check("sim-receive-rejected", !r.ok && r.error.contains(QStringLiteral("回环模拟")),
          r.error);
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    p.insert(QStringLiteral("mode"), QStringLiteral("exchange"));
    p.insert(QStringLiteral("value"), QStringLiteral("{\"k\":1}"));
    p.insert(QStringLiteral("encoding"), QStringLiteral("structured"));
    p.insert(QStringLiteral("responseEncoding"), QStringLiteral("structured"));
    p.insert(QStringLiteral("txFraming"), QStringLiteral("length16be"));
    p.insert(QStringLiteral("rxFraming"), QStringLiteral("length16be"));
    const SerialResult r = runSerialExchange(p);
    check("sim-structured-len16", r.ok && r.value.contains(QLatin1String("\"k\"")),
          r.ok ? r.value : r.error);
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("connection"), QStringLiteral("simulator"));
    p.insert(QStringLiteral("mode"), QStringLiteral("exchange"));
    p.insert(QStringLiteral("value"), QStringLiteral("01 02 03 04"));
    p.insert(QStringLiteral("encoding"), QStringLiteral("bytes"));
    p.insert(QStringLiteral("responseEncoding"), QStringLiteral("bytes"));
    p.insert(QStringLiteral("txFraming"), QStringLiteral("raw"));
    p.insert(QStringLiteral("rxFraming"), QStringLiteral("fixed"));
    p.insert(QStringLiteral("responseBytes"), 4);
    const SerialResult r = runSerialExchange(p);
    check("sim-bytes-fixed", r.ok && r.payload.size() == 4 &&
                                 uchar(r.payload.at(3)) == 0x04,
          r.ok ? QStringLiteral("n=%1").arg(r.payload.size()) : r.error);
  }

  QString ptyErr;
  const bool ptyOk = serialPtyLoopback().start(&ptyErr);
  check("pty-start", ptyOk, ptyErr);
  if (ptyOk) {
    QVariantMap p;
    p.insert(QStringLiteral("connection"), QStringLiteral("device"));
    p.insert(QStringLiteral("mode"), QStringLiteral("exchange"));
    p.insert(QStringLiteral("serialPort"), serialPtyLoopback().slavePath());
    p.insert(QStringLiteral("value"), QStringLiteral("PTY-LOOP-OK"));
    p.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    p.insert(QStringLiteral("txFraming"), QStringLiteral("crlf"));
    p.insert(QStringLiteral("rxFraming"), QStringLiteral("crlf"));
    p.insert(QStringLiteral("baudrate"), 115200);
    p.insert(QStringLiteral("timeoutMs"), 2000);
    const SerialResult r = runSerialExchange(p);
    check("pty-exchange", r.ok && r.value == QLatin1String("PTY-LOOP-OK") && !r.simulated,
          r.ok ? QStringLiteral("port=%1 value=%2").arg(r.serialPort, r.value) : r.error);
  }
  return fails;
}

}  // namespace sieans_qt
