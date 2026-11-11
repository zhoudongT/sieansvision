#include "ProtocolNet.hpp"
#include "ModbusClient.hpp"
#include "S7Client.hpp"
#include "MqttClient.hpp"

#include <QVariantMap>

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

namespace sieans_qt {
namespace {

QString formatConnectErrno(const QString& label, const QString& host, quint16 port,
                           int timeoutMs, int err) {
  if (err == ECONNREFUSED)
    return QStringLiteral("%1 连接被拒绝 (%2:%3)").arg(label, host).arg(port);
  if (err == ETIMEDOUT || err == EAGAIN || err == EWOULDBLOCK)
    return QStringLiteral("%1 连接超时 (%2:%3, %4ms)").arg(label, host).arg(port).arg(timeoutMs);
  if (err == ECONNRESET || err == EPIPE || err == EHOSTUNREACH || err == ENETUNREACH)
    return QStringLiteral("%1 连接已断开 (%2:%3): %4")
        .arg(label, host)
        .arg(port)
        .arg(QString::fromLocal8Bit(std::strerror(err)));
  return QStringLiteral("%1 连接失败 (%2:%3): %4")
      .arg(label, host)
      .arg(port)
      .arg(QString::fromLocal8Bit(std::strerror(err)));
}

}  // namespace

int connectTcpTimeout(const QString& host, quint16 port, int timeoutMs, QString* error,
                      const QString& label) {
  const QString tag = label.isEmpty() ? QStringLiteral("TCP") : label;
  if (timeoutMs < 50) timeoutMs = 50;
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    if (error) *error = QStringLiteral("无法创建 %1 套接字").arg(tag);
    return -1;
  }
  const int flags = ::fcntl(fd, F_GETFL, 0);
  if (flags >= 0) ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);

  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  if (::inet_pton(AF_INET, host.toUtf8().constData(), &addr.sin_addr) != 1) {
    if (error) *error = QStringLiteral("无法解析 %1 主机地址").arg(tag);
    ::close(fd);
    return -1;
  }

  const int rc = ::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
  if (rc != 0 && errno != EINPROGRESS) {
    const int err = errno;
    if (error) *error = formatConnectErrno(tag, host, port, timeoutMs, err);
    ::close(fd);
    return -1;
  }
  if (rc != 0) {
    pollfd pfd{};
    pfd.fd = fd;
    pfd.events = POLLOUT;
    const int pr = ::poll(&pfd, 1, timeoutMs);
    if (pr == 0) {
      if (error)
        *error = QStringLiteral("%1 连接超时 (%2:%3, %4ms)").arg(tag, host).arg(port).arg(timeoutMs);
      ::close(fd);
      return -1;
    }
    if (pr < 0) {
      const int err = errno;
      if (error) *error = formatConnectErrno(tag, host, port, timeoutMs, err);
      ::close(fd);
      return -1;
    }
    int soerr = 0;
    socklen_t sl = sizeof(soerr);
    if (::getsockopt(fd, SOL_SOCKET, SO_ERROR, &soerr, &sl) != 0 || soerr != 0) {
      if (error) *error = formatConnectErrno(tag, host, port, timeoutMs, soerr ? soerr : errno);
      ::close(fd);
      return -1;
    }
  }

  if (flags >= 0) ::fcntl(fd, F_SETFL, flags & ~O_NONBLOCK);
  timeval tv{};
  tv.tv_sec = timeoutMs / 1000;
  tv.tv_usec = (timeoutMs % 1000) * 1000;
  ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  ::setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
  return fd;
}

QString g_lastRobustClass;

QString lastProtocolRobustClass() { return g_lastRobustClass; }

QString classifyProtocolFailure(const QString& error) {
  if (error.contains(QStringLiteral("被拒绝"))) return QStringLiteral("refused");
  if (error.contains(QStringLiteral("超时"))) return QStringLiteral("timeout");
  if (error.contains(QStringLiteral("已关闭")) || error.contains(QStringLiteral("已断开")) ||
      error.contains(QStringLiteral("重置")) ||
      error.contains(QStringLiteral("Connection reset"), Qt::CaseInsensitive))
    return QStringLiteral("closed");
  if (error.contains(QStringLiteral("Connection refused"), Qt::CaseInsensitive) ||
      error.contains(QStringLiteral("拒绝连接")))
    return QStringLiteral("refused");
  if (error.contains(QStringLiteral("timed out"), Qt::CaseInsensitive) ||
      error.contains(QStringLiteral("Timeout"), Qt::CaseInsensitive))
    return QStringLiteral("timeout");
  return QStringLiteral("other");
}

QStringList protocolRobustnessSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail) {
    if (!ok) fails << QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail);
  };

  auto probeMb = [](quint16 port, int value) {
    QVariantMap w;
    w.insert(QStringLiteral("transport"), QStringLiteral("tcp"));
    w.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    w.insert(QStringLiteral("port"), int(port));
    w.insert(QStringLiteral("area"), QStringLiteral("holding"));
    w.insert(QStringLiteral("address"), 80);
    w.insert(QStringLiteral("value"), value);
    w.insert(QStringLiteral("timeoutMs"), 400);
    return runModbusWrite(w);
  };

  const bool mbWas = modbusSoftServer().running();
  quint16 mbPort = mbWas ? modbusSoftServer().port() : 0;
  if (!mbWas) {
    QString e;
    for (int p = 1502; p <= 1506 && mbPort == 0; ++p) {
      if (modbusSoftServer().start(quint16(p), &e)) mbPort = quint16(p);
    }
    check("mb-start", mbPort != 0, e);
  }
  if (mbPort != 0) {
    const ModbusResult happy = probeMb(mbPort, 9001);
    check("mb-happy", happy.ok, happy.error);
    modbusSoftServer().stop();
    const ModbusResult down = probeMb(mbPort, 1);
    check("mb-down-fails", !down.ok, down.ok ? QStringLiteral("unexpected ok") : down.error);
    const QString cls = classifyProtocolFailure(down.error);
    g_lastRobustClass = cls;
    check("mb-fail-class",
          cls == QLatin1String("refused") || cls == QLatin1String("timeout") ||
              cls == QLatin1String("closed"),
          down.error.isEmpty() ? QStringLiteral("empty error")
                               : (cls + QLatin1Char(' ') + down.error));
    QString upErr;
    const bool up = modbusSoftServer().start(mbPort, &upErr);
    check("mb-restart", up, upErr);
    if (up) {
      const ModbusResult again = probeMb(mbPort, 4242);
      check("mb-reconnect", again.ok && again.value.toInt() == 4242,
            again.ok ? again.value.toString() : again.error);
    }
    if (!mbWas) modbusSoftServer().stop();
  }

  auto probeMqtt = [](quint16 port, int value) {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("broker"));
    w.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    w.insert(QStringLiteral("port"), int(port));
    w.insert(QStringLiteral("topic"), QStringLiteral("sieans/robust"));
    w.insert(QStringLiteral("encoding"), QStringLiteral("text"));
    w.insert(QStringLiteral("value"), QString::number(value));
    w.insert(QStringLiteral("qos"), 0);
    w.insert(QStringLiteral("timeoutMs"), 400);
    return runMqttPublish(w);
  };

  const bool mqttWas = mqttSoftBroker().running();
  quint16 mqttPort = mqttWas ? mqttSoftBroker().port() : 0;
  if (!mqttWas) {
    QString e;
    for (int p = 1883; p <= 1887 && mqttPort == 0; ++p) {
      if (mqttSoftBroker().start(quint16(p), &e)) mqttPort = quint16(p);
    }
    check("mqtt-start", mqttPort != 0, e);
  }
  if (mqttPort != 0) {
    mqttSoftBroker().stop();
    const auto down = probeMqtt(mqttPort, 1);
    check("mqtt-down-fails", !down.ok, down.ok ? QStringLiteral("unexpected ok") : down.error);
    const QString cls = classifyProtocolFailure(down.error);
    check("mqtt-fail-class",
          cls == QLatin1String("refused") || cls == QLatin1String("timeout") ||
              cls == QLatin1String("closed"),
          down.error.isEmpty() ? QStringLiteral("empty error")
                               : (cls + QLatin1Char(' ') + down.error));
    QString upErr;
    const bool up = mqttSoftBroker().start(mqttPort, &upErr);
    check("mqtt-restart", up, upErr);
    if (up) {
      const auto again = probeMqtt(mqttPort, 9001);
      check("mqtt-reconnect", again.ok, again.error);
    }
    if (!mqttWas) mqttSoftBroker().stop();
  }

  auto probeS7 = [](quint16 port, int value) {
    QVariantMap w;
    w.insert(QStringLiteral("connection"), QStringLiteral("plc"));
    w.insert(QStringLiteral("host"), QStringLiteral("127.0.0.1"));
    w.insert(QStringLiteral("port"), int(port));
    w.insert(QStringLiteral("rack"), 0);
    w.insert(QStringLiteral("slot"), 1);
    w.insert(QStringLiteral("area"), QStringLiteral("db"));
    w.insert(QStringLiteral("dbNumber"), 1);
    w.insert(QStringLiteral("byteOffset"), 20);
    w.insert(QStringLiteral("dataType"), QStringLiteral("uint16"));
    w.insert(QStringLiteral("value"), value);
    w.insert(QStringLiteral("timeoutMs"), 400);
    return runS7Write(w);
  };

  const bool s7Was = s7SoftServer().running();
  quint16 s7Port = s7Was ? s7SoftServer().port() : 0;
  if (!s7Was) {
    QString e;
    for (int p = 1102; p <= 1106 && s7Port == 0; ++p) {
      if (s7SoftServer().start(quint16(p), &e)) s7Port = quint16(p);
    }
    check("s7-start", s7Port != 0, e);
  }
  if (s7Port != 0) {
    s7SoftServer().stop();
    const auto down = probeS7(s7Port, 1);
    check("s7-down-fails", !down.ok, down.ok ? QStringLiteral("unexpected ok") : down.error);
    const QString cls = classifyProtocolFailure(down.error);
    check("s7-fail-class",
          cls == QLatin1String("refused") || cls == QLatin1String("timeout") ||
              cls == QLatin1String("closed"),
          down.error.isEmpty() ? QStringLiteral("empty error")
                               : (cls + QLatin1Char(' ') + down.error));
    QString upErr;
    const bool up = s7SoftServer().start(s7Port, &upErr);
    check("s7-restart", up, upErr);
    if (up) {
      const auto again = probeS7(s7Port, 4242);
      check("s7-reconnect", again.ok, again.error);
    }
    if (!s7Was) s7SoftServer().stop();
  }

  return fails;
}

}  // namespace sieans_qt
