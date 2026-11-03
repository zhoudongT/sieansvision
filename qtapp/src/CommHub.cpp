#include "CommHub.hpp"
#include <QtEndian>

#include <QDateTime>
#include <QHostAddress>
#include <QRegularExpression>
#include <QTimer>

namespace sieans_qt {

CommHub::CommHub(QObject* parent) : QObject(parent) {}

CommHub::~CommHub() { stopTcp(); }

void CommHub::loadFromCommManager(const QVariantMap& cm) {
  cm_ = cm;
  const QVariantMap tcp = cm.value(QStringLiteral("tcpReal")).toMap();
  framing_ = tcp.value(QStringLiteral("framing"), QStringLiteral("lf")).toString();
  ack_ = tcp.value(QStringLiteral("ack")).toString();
}

QStringList CommHub::devices() const {
  QStringList out;
  const QVariantList devs = cm_.value(QStringLiteral("devices")).toList();
  for (const QVariant& v : devs) {
    const QVariantMap d = v.toMap();
    const QString name = d.value(QStringLiteral("name")).toString();
    if (!name.isEmpty()) out << name;
  }
  if (out.isEmpty()) out << QStringLiteral("LocalLoop");
  return out;
}


QVariantMap CommHub::deviceInfo(const QString& name) const {
  const QVariantList devs = cm_.value(QStringLiteral("devices")).toList();
  for (const QVariant& v : devs) {
    const QVariantMap d = v.toMap();
    if (d.value(QStringLiteral("name")).toString() == name) return d;
  }
  return {};
}

QVariantList CommHub::deviceList() const {
  return cm_.value(QStringLiteral("devices")).toList();
}

QString CommHub::deviceProtocol(const QString& name) const {
  const QVariantList devs = cm_.value(QStringLiteral("devices")).toList();
  for (const QVariant& v : devs) {
    const QVariantMap d = v.toMap();
    if (d.value(QStringLiteral("name")).toString() == name)
      return d.value(QStringLiteral("protocol")).toString();
  }
  return QStringLiteral("Local Bus");
}

QString CommHub::expandTemplate(const QString& tmpl, const QVariantMap& vars) {
  QString out = tmpl;
  auto applyRe = [&](const QRegularExpression& re, bool requireKey) {
    QRegularExpressionMatchIterator it = re.globalMatch(out);
    struct Rep { int start; int len; QString val; };
    QVector<Rep> reps;
    while (it.hasNext()) {
      const auto m = it.next();
      const QString key = m.captured(1);
      if (requireKey && !vars.contains(key)) continue;
      reps.push_back({static_cast<int>(m.capturedStart()), static_cast<int>(m.capturedLength()),
                      vars.value(key).toString()});
    }
    for (int i = reps.size() - 1; i >= 0; --i)
      out.replace(reps[i].start, reps[i].len, reps[i].val);
  };
  // ${flow.x} / ${x}
  applyRe(QRegularExpression(QStringLiteral(R"(\$\{(?:flow\.)?([A-Za-z_][A-Za-z0-9_]*)\})")),
          false);
  // {{name}} mustache — before single braces so {{x}} is not eaten as {x}
  applyRe(QRegularExpression(QStringLiteral(R"(\{\{([A-Za-z_][A-Za-z0-9_]*)\}\})")), true);
  // Named braces {barcodeText} — skip pure numeric {0}/{1} (format_data indices).
  applyRe(QRegularExpression(QStringLiteral(R"(\{([A-Za-z_][A-Za-z0-9_]*)\})")), true);
  return out;
}

void CommHub::appendTranscript(const QString& tag, const QString& line) {
  const QString stamp =
      QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss.zzz"));
  transcript_.append(QStringLiteral("[%1] %2 %3").arg(stamp, tag, line));
  while (transcript_.size() > 200) transcript_.removeFirst();
  emit transcriptChanged();
}

void CommHub::clearTranscript() {
  transcript_.clear();
  emit transcriptChanged();
}

bool CommHub::sendPayload(const QString& deviceName, const QString& payload,
                          QString* error) {
  Q_UNUSED(error);
  lastTx_ = payload;
  const QString proto = deviceProtocol(deviceName);
  appendTranscript(QStringLiteral("TX"),
                   QStringLiteral("%1 (%2): %3")
                       .arg(deviceName, proto, payload.left(240)));

  // Local Bus / LocalLoop: in-process TX→RX echo so receive_data works open-and-run.
  const bool local =
      proto.contains(QStringLiteral("Local"), Qt::CaseInsensitive) ||
      deviceName.contains(QStringLiteral("Local"), Qt::CaseInsensitive) ||
      deviceName.compare(QStringLiteral("LocalLoop"), Qt::CaseInsensitive) == 0;
  if (local) {
    lastRx_ = payload;
    appendTranscript(QStringLiteral("RX"),
                     QStringLiteral("%1 (echo): %2").arg(deviceName, payload.left(240)));
    emit payloadReceived(deviceName, payload);
  }

  // If TCP device or tcpReal active, also push on wire
  const bool wantTcp =
      proto.contains(QStringLiteral("TCP"), Qt::CaseInsensitive) ||
      deviceName.contains(QStringLiteral("Tcp"), Qt::CaseInsensitive);
  if (wantTcp && tcpActive()) {
    sendTcpRaw(payload);
  } else if (wantTcp && !tcpActive()) {
    // Soft TCP mirror when server not up: still echo so RX step is not empty.
    if (lastRx_.isEmpty()) {
      lastRx_ = payload;
      appendTranscript(QStringLiteral("RX"),
                       QStringLiteral("%1 (soft-echo): %2").arg(deviceName, payload.left(240)));
      emit payloadReceived(deviceName, payload);
    }
  }
  return true;
}

void CommHub::sendTcpRaw(const QString& payload) {
  QByteArray body = payload.toUtf8();
  QByteArray bytes;
  if (framing_ == QLatin1String("len4")) {
    const quint32 n = quint32(body.size());
    bytes.resize(4);
    qToBigEndian(n, reinterpret_cast<uchar*>(bytes.data()));
    bytes.append(body);
  } else {
    bytes = body;
    if (framing_ == QLatin1String("crlf"))
      bytes.append("\r\n");
    else if (framing_ == QLatin1String("lf") || framing_.isEmpty())
      bytes.append('\n');
    // raw: as-is
  }

  auto writeSock = [&](QTcpSocket* s) {
    if (!s || s->state() != QAbstractSocket::ConnectedState) return;
    s->write(bytes);
    s->flush();
  };
  writeSock(client_);
  for (QTcpSocket* s : peers_) writeSock(s);
}

bool CommHub::tcpActive() const {
  if (client_ && client_->state() == QAbstractSocket::ConnectedState) return true;
  if (server_ && server_->isListening()) return true;
  for (QTcpSocket* s : peers_) {
    if (s && s->state() == QAbstractSocket::ConnectedState) return true;
  }
  return false;
}

bool CommHub::startTcp(QString* error) {
  stopTcp();
  const QVariantMap tcp = cm_.value(QStringLiteral("tcpReal")).toMap();
  const QString host =
      tcp.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString();
  const quint16 port =
      static_cast<quint16>(tcp.value(QStringLiteral("port"), 19956).toInt());
  const QString role =
      tcp.value(QStringLiteral("role"), QStringLiteral("server")).toString();
  framing_ = tcp.value(QStringLiteral("framing"), QStringLiteral("lf")).toString();
  ack_ = tcp.value(QStringLiteral("ack")).toString();

  if (role.compare(QStringLiteral("client"), Qt::CaseInsensitive) == 0) {
    reconnectEnabled_ = tcp.value(QStringLiteral("reconnect"), true).toBool();
    reconnectHost_ = host;
    reconnectPort_ = port;
    if (!reconnectTimer_) {
      reconnectTimer_ = new QTimer(this);
      reconnectTimer_->setInterval(1500);
      connect(reconnectTimer_, &QTimer::timeout, this, &CommHub::tryReconnect);
    }
    client_ = new QTcpSocket(this);
    connect(client_, &QTcpSocket::readyRead, this, &CommHub::onClientReadyRead);
    connect(client_, &QTcpSocket::errorOccurred, this, &CommHub::onSocketError);
    connect(client_, &QTcpSocket::disconnected, this, &CommHub::onClientDisconnected);
    reconnectAttempts_ = 0;
    connect(client_, &QTcpSocket::connected, this, [this, host, port]() {
      if (reconnectTimer_) reconnectTimer_->stop();
      reconnectAttempts_ = 0;
      if (reconnectTimer_) reconnectTimer_->setInterval(1500);
      tcpStatus_ = QStringLiteral("connected %1:%2 · %3")
                       .arg(host)
                       .arg(port)
                       .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
      emit statusChanged(tcpStatus_);
      appendTranscript(QStringLiteral("SYS"),
                       QStringLiteral("%1 · attempts reset").arg(tcpStatus_));
    });
    client_->connectToHost(host, port);
    tcpStatus_ = QStringLiteral("connecting %1:%2 · reconnect=%3 · %4")
                     .arg(host)
                     .arg(port)
                     .arg(reconnectEnabled_ ? QStringLiteral("on") : QStringLiteral("off"))
                     .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
    emit statusChanged(tcpStatus_);
    return true;
  }

  server_ = new QTcpServer(this);
  connect(server_, &QTcpServer::newConnection, this, &CommHub::onNewConnection);
  if (!server_->listen(QHostAddress(host), port)) {
    const QString err = server_->errorString();
    if (error) *error = err;
    appendTranscript(QStringLiteral("ERR"),
                     QStringLiteral("listen %1:%2 failed: %3").arg(host).arg(port).arg(err));
    tcpStatus_ = QStringLiteral("listen-fail");
    emit statusChanged(tcpStatus_);
    server_->deleteLater();
    server_ = nullptr;
    return false;
  }
  listenHost_ = host;
  listenPort_ = port;
  refreshListenStatus();
  appendTranscript(QStringLiteral("SYS"), tcpStatus_);
  return true;
}

void CommHub::stopTcp() {
  reconnectEnabled_ = false;
  reconnectAttempts_ = 0;
  if (reconnectTimer_) {
    reconnectTimer_->stop();
    reconnectTimer_->setInterval(1500);
  }
  for (QTcpSocket* s : peers_) {
    if (s) {
      s->disconnectFromHost();
      s->deleteLater();
    }
  }
  peers_.clear();
  if (client_) {
    client_->disconnectFromHost();
    client_->deleteLater();
    client_ = nullptr;
  }
  if (server_) {
    server_->close();
    server_->deleteLater();
    server_ = nullptr;
  }
  listenHost_.clear();
  listenPort_ = 0;
  if (tcpStatus_ != QLatin1String("idle")) {
    tcpStatus_ = QStringLiteral("idle");
    emit statusChanged(tcpStatus_);
    appendTranscript(QStringLiteral("SYS"), QStringLiteral("TCP stopped"));
  }
}

void CommHub::refreshListenStatus() {
  if (!server_ || !server_->isListening()) return;
  const int n = peers_.size();
  if (n <= 0)
    tcpStatus_ = QStringLiteral("listening %1:%2 · %3")
                     .arg(listenHost_)
                     .arg(listenPort_)
                     .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
  else
    tcpStatus_ = QStringLiteral("listening %1:%2 · peers %3 · %4")
                     .arg(listenHost_)
                     .arg(listenPort_)
                     .arg(n)
                     .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
  emit statusChanged(tcpStatus_);
}

void CommHub::onNewConnection() {
  while (server_ && server_->hasPendingConnections()) {
    QTcpSocket* s = server_->nextPendingConnection();
    peers_.append(s);
    connect(s, &QTcpSocket::readyRead, this, &CommHub::onClientReadyRead);
    connect(s, &QTcpSocket::disconnected, this, [this, s]() {
      peers_.removeAll(s);
      s->deleteLater();
      appendTranscript(QStringLiteral("SYS"), QStringLiteral("peer disconnected"));
      refreshListenStatus();
    });
    appendTranscript(QStringLiteral("SYS"),
                     QStringLiteral("peer connected %1 · %2")
                         .arg(s->peerAddress().toString(),
                              framing_.isEmpty() ? QStringLiteral("lf") : framing_));
    refreshListenStatus();
  }
}

void CommHub::onClientReadyRead() {
  QObject* src = sender();
  QTcpSocket* s = qobject_cast<QTcpSocket*>(src);
  if (!s) return;
  const QByteArray raw = s->readAll();
  QString text;
  if (framing_ == QLatin1String("len4") && raw.size() >= 4) {
    const quint32 n = qFromBigEndian<quint32>(
        reinterpret_cast<const uchar*>(raw.constData()));
    const int take = qMin(int(n), raw.size() - 4);
    text = QString::fromUtf8(raw.constData() + 4, take).trimmed();
  } else {
    text = QString::fromUtf8(raw).trimmed();
  }
  if (text.isEmpty()) return;
  lastRx_ = text;
  appendTranscript(QStringLiteral("RX"), text.left(240));
  emit payloadReceived(QStringLiteral("TCP"), text);
  if (!ack_.isEmpty() && s->state() == QAbstractSocket::ConnectedState) {
    QByteArray a = ack_.toUtf8();
    if (framing_ == QLatin1String("len4")) {
      QByteArray framed;
      const quint32 n = quint32(a.size());
      framed.resize(4);
      qToBigEndian(n, reinterpret_cast<uchar*>(framed.data()));
      framed.append(a);
      a = framed;
    } else if (framing_ == QLatin1String("crlf")) a.append("\r\n");
    else if (framing_ != QLatin1String("raw")) a.append('\n');
    s->write(a);
    s->flush();
  }
}

void CommHub::onSocketError() {
  QTcpSocket* s = qobject_cast<QTcpSocket*>(sender());
  const QString err = s ? s->errorString() : QStringLiteral("socket error");
  appendTranscript(QStringLiteral("ERR"), err);
  tcpStatus_ = QStringLiteral("error");
  emit statusChanged(tcpStatus_);
  if (reconnectEnabled_ && client_ && s == client_ && reconnectTimer_ &&
      !reconnectTimer_->isActive())
    reconnectTimer_->start();
}

void CommHub::onClientDisconnected() {
  appendTranscript(QStringLiteral("SYS"), QStringLiteral("client disconnected"));
  tcpStatus_ = QStringLiteral("disconnected");
  emit statusChanged(tcpStatus_);
  if (reconnectEnabled_ && reconnectTimer_ && !reconnectTimer_->isActive())
    reconnectTimer_->start();
}

void CommHub::tryReconnect() {
  if (!reconnectEnabled_ || reconnectHost_.isEmpty() || reconnectPort_ == 0) {
    if (reconnectTimer_) reconnectTimer_->stop();
    return;
  }
  if (client_ && client_->state() == QAbstractSocket::ConnectedState) {
    if (reconnectTimer_) reconnectTimer_->stop();
    return;
  }
  if (client_ && (client_->state() == QAbstractSocket::ConnectingState ||
                  client_->state() == QAbstractSocket::HostLookupState))
    return;
  ++reconnectAttempts_;
  // Cap attempts so runaway client reconnect does not spin forever.
  if (reconnectAttempts_ > 40) {
    if (reconnectTimer_) reconnectTimer_->stop();
    tcpStatus_ = QStringLiteral("reconnect paused #%1 %2:%3")
                     .arg(reconnectAttempts_ - 1)
                     .arg(reconnectHost_)
                     .arg(reconnectPort_);
    emit statusChanged(tcpStatus_);
    appendTranscript(QStringLiteral("SYS"),
                     QStringLiteral("%1 · give up until restartTcp").arg(tcpStatus_));
    return;
  }
  // Backoff 1.5s → ~10s cap
  if (reconnectTimer_) {
    const int ms = qMin(10000, 1500 * (1 << qMin(reconnectAttempts_ - 1, 3)));
    reconnectTimer_->setInterval(ms);
  }
  appendTranscript(QStringLiteral("SYS"),
                   QStringLiteral("reconnect #%1 %2:%3 (backoff %4ms)")
                       .arg(reconnectAttempts_)
                       .arg(reconnectHost_)
                       .arg(reconnectPort_)
                       .arg(reconnectTimer_ ? reconnectTimer_->interval() : 0));
  tcpStatus_ = QStringLiteral("reconnecting #%1 %2:%3 · backoff %4ms")
                   .arg(reconnectAttempts_)
                   .arg(reconnectHost_)
                   .arg(reconnectPort_)
                   .arg(reconnectTimer_ ? reconnectTimer_->interval() : 0);
  emit statusChanged(tcpStatus_);
  if (!client_) {
    client_ = new QTcpSocket(this);
    connect(client_, &QTcpSocket::readyRead, this, &CommHub::onClientReadyRead);
    connect(client_, &QTcpSocket::errorOccurred, this, &CommHub::onSocketError);
    connect(client_, &QTcpSocket::disconnected, this, &CommHub::onClientDisconnected);
    connect(client_, &QTcpSocket::connected, this, [this]() {
      if (reconnectTimer_) reconnectTimer_->stop();
      reconnectAttempts_ = 0;
      if (reconnectTimer_) reconnectTimer_->setInterval(1500);
      tcpStatus_ = QStringLiteral("connected %1:%2 · %3")
                       .arg(reconnectHost_)
                       .arg(reconnectPort_)
                       .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
      emit statusChanged(tcpStatus_);
      appendTranscript(QStringLiteral("SYS"),
                       QStringLiteral("%1 · attempts reset").arg(tcpStatus_));
    });
  }
  client_->abort();
  client_->connectToHost(reconnectHost_, reconnectPort_);
}

}  // namespace sieans_qt
