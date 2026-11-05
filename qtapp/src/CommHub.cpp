#include "CommHub.hpp"
#include <QtEndian>

#include <QDateTime>
#include <QHostAddress>
#include <QRegularExpression>
#include <QTimer>
#include <QCoreApplication>
#include <QEventLoop>

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
  applyRe(QRegularExpression(QStringLiteral(R"(\$\{(?:flow\.)?([A-Za-z_][A-Za-z0-9_.]*)\})")),
          false);
  // {{name}} mustache — before single braces so {{x}} is not eaten as {x}
  applyRe(QRegularExpression(QStringLiteral(R"(\{\{([A-Za-z_][A-Za-z0-9_.]*)\}\})")), true);
  // Named braces {barcodeText} — skip pure numeric {0}/{1} (format_data indices).
  applyRe(QRegularExpression(QStringLiteral(R"(\{([A-Za-z_][A-Za-z0-9_.]*)\})")), true);
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
  lastTxDevice_ = deviceName;
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
    noteDeviceTx(deviceName, payload, QStringLiteral("TX+echo"));
    if (!ack_.isEmpty()) noteDeviceAck(deviceName, ack_);
  }

  // If TCP device or tcpReal active, also push on wire
  const bool wantTcp =
      proto.contains(QStringLiteral("TCP"), Qt::CaseInsensitive) ||
      deviceName.contains(QStringLiteral("Tcp"), Qt::CaseInsensitive);
  if (wantTcp && tcpActive()) {
    sendTcpRaw(payload);
    if (!local) {
      const int n = livePeerCount();
      const QString st =
          n > 0 ? QStringLiteral("TX·peers%1").arg(n) : QStringLiteral("TX");
      noteDeviceTx(deviceName, payload, st);
      DeviceTxStatus& ds = deviceTx_[deviceName];
      if (!lastPeerEndpoint_.isEmpty()) ds.lastPeer = lastPeerEndpoint_;
    }
  } else if (wantTcp && !tcpActive()) {
    // Soft TCP mirror when server not up: still echo so RX step is not empty.
    if (lastRx_.isEmpty()) {
      lastRx_ = payload;
      appendTranscript(QStringLiteral("RX"),
                       QStringLiteral("%1 (soft-echo): %2").arg(deviceName, payload.left(240)));
      emit payloadReceived(deviceName, payload);
    }
    if (!local) noteDeviceTx(deviceName, payload, QStringLiteral("TX soft"));
  } else if (!local) {
    noteDeviceTx(deviceName, payload, QStringLiteral("TX"));
  }
  return true;
}

CommHub::DeviceTxStatus CommHub::deviceTxStatus(const QString& name) const {
  return deviceTx_.value(name);
}

void CommHub::noteDeviceTx(const QString& device, const QString& payload,
                           const QString& status) {
  if (device.isEmpty()) return;
  DeviceTxStatus& st = deviceTx_[device];
  st.lastTx = payload;
  st.status = status;
  st.txCount += 1;
  st.lastMs = QDateTime::currentMSecsSinceEpoch();
  emit deviceTxChanged(device);
}

void CommHub::noteDeviceAck(const QString& device, const QString& ack,
                            const QString& peer) {
  if (device.isEmpty() || ack.isEmpty()) return;
  DeviceTxStatus& st = deviceTx_[device];
  if (!peer.isEmpty()) {
    st.lastPeer = peer;
    lastPeerEndpoint_ = peer;
    st.lastAck = QStringLiteral("%1@%2").arg(ack.left(64), peer);
    st.peerAckCount += 1;
    st.ackCount += 1;
    st.lastMs = QDateTime::currentMSecsSinceEpoch();
    if (st.status.startsWith(QLatin1String("TX")))
      st.status = QStringLiteral("TX+ACK");
    else
      st.status = QStringLiteral("peerACK");
  } else {
    st.lastAck = ack;
    st.ackCount += 1;
    st.lastMs = QDateTime::currentMSecsSinceEpoch();
    if (st.status.startsWith(QLatin1String("TX")))
      st.status = QStringLiteral("TX+ACK");
    else
      st.status = QStringLiteral("ACK");
  }
  emit deviceTxChanged(device);
}

QString CommHub::primaryTcpDevice() const {
  const QVariantList devs = cm_.value(QStringLiteral("devices")).toList();
  QString fallback;
  for (const QVariant& v : devs) {
    const QVariantMap d = v.toMap();
    const QString name = d.value(QStringLiteral("name")).toString();
    if (name.isEmpty()) continue;
    const QString proto = d.value(QStringLiteral("protocol")).toString();
    const bool tcpish =
        proto.contains(QStringLiteral("TCP"), Qt::CaseInsensitive) ||
        name.contains(QStringLiteral("Tcp"), Qt::CaseInsensitive);
    if (!tcpish) continue;
    if (!d.value(QStringLiteral("enabled"), true).toBool()) {
      if (fallback.isEmpty()) fallback = name;
      continue;
    }
    return name;
  }
  return fallback.isEmpty() ? QStringLiteral("TCP") : fallback;
}

int CommHub::livePeerCount() const {
  int n = 0;
  for (QTcpSocket* s : peers_) {
    if (s && s->state() == QAbstractSocket::ConnectedState) ++n;
  }
  if (client_ && client_->state() == QAbstractSocket::ConnectedState) ++n;
  return n;
}

QString CommHub::peerEndpointOf(QTcpSocket* s) const {
  if (!s) return {};
  if (peerKeys_.contains(s)) return peerKeys_.value(s);
  return QStringLiteral("%1:%2")
      .arg(s->peerAddress().toString())
      .arg(s->peerPort());
}

QByteArray CommHub::framePayload(const QString& payload) const {
  QByteArray body = payload.toUtf8();
  if (framing_ == QLatin1String("len4")) {
    QByteArray bytes;
    const quint32 n = quint32(body.size());
    bytes.resize(4);
    qToBigEndian(n, reinterpret_cast<uchar*>(bytes.data()));
    bytes.append(body);
    return bytes;
  }
  QByteArray bytes = body;
  if (framing_ == QLatin1String("crlf"))
    bytes.append("\r\n");
  else if (framing_ == QLatin1String("lf") || framing_.isEmpty())
    bytes.append('\n');
  return bytes;
}

void CommHub::sendTcpRaw(const QString& payload) {
  const QByteArray bytes = framePayload(payload);
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
    tcpStatus_ = QStringLiteral("listen-fail · %1")
                     .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
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
  peerKeys_.clear();
  lastPeerEndpoint_.clear();
  len4Buf_.clear();
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
  if (!server_) return;
  while (server_->hasPendingConnections()) {
    QTcpSocket* s = server_->nextPendingConnection();
    if (!s) continue;
    peers_.append(s);
    const QString peer = QStringLiteral("%1:%2")
                             .arg(s->peerAddress().toString())
                             .arg(s->peerPort());
    peerKeys_.insert(s, peer);
    lastPeerEndpoint_ = peer;
    connect(s, &QTcpSocket::readyRead, this, &CommHub::onClientReadyRead);
    connect(s, &QTcpSocket::disconnected, this, [this, s]() {
      peers_.removeAll(s);
      peerKeys_.remove(s);
      len4Buf_.remove(s);
      s->deleteLater();
      refreshListenStatus();
      appendTranscript(QStringLiteral("SYS"), QStringLiteral("peer disconnected"));
      const QString tcpDev = primaryTcpDevice();
      if (!tcpDev.isEmpty()) emit deviceTxChanged(tcpDev);
    });
    refreshListenStatus();
    appendTranscript(QStringLiteral("SYS"),
                     QStringLiteral("peer connected %1").arg(peer));
    const QString tcpDev = primaryTcpDevice();
    if (!tcpDev.isEmpty()) {
      DeviceTxStatus& st = deviceTx_[tcpDev];
      st.lastPeer = peer;
      st.lastMs = QDateTime::currentMSecsSinceEpoch();
      emit deviceTxChanged(tcpDev);
    }
  }
}

void CommHub::onClientReadyRead() {
  QTcpSocket* s = qobject_cast<QTcpSocket*>(sender());
  if (!s) return;

  auto emitLine = [this, s](const QString& text) {
    if (text.isEmpty()) return;
    handleFramedPayload(s, text);
  };

  if (framing_ == QLatin1String("len4")) {
    QByteArray& buf = len4Buf_[s];
    buf.append(s->readAll());
    while (buf.size() >= 4) {
      const quint32 n = qFromBigEndian<quint32>(
          reinterpret_cast<const uchar*>(buf.constData()));
      if (n > 16u * 1024u * 1024u) {
        appendTranscript(QStringLiteral("ERR"),
                         QStringLiteral("len4 frame too large (%1)").arg(n));
        buf.clear();
        break;
      }
      if (buf.size() < int(4 + n)) break;
      const QByteArray payload = buf.mid(4, int(n));
      buf.remove(0, int(4 + n));
      emitLine(QString::fromUtf8(payload));
    }
    return;
  }

  if (framing_ == QLatin1String("raw")) {
    const QByteArray raw = s->readAll();
    if (!raw.isEmpty()) emitLine(QString::fromUtf8(raw));
    return;
  }

  // lf / crlf (default lf)
  while (s->canReadLine()) {
    QByteArray line = s->readLine();
    while (line.endsWith('\n') || line.endsWith('\r')) line.chop(1);
    emitLine(QString::fromUtf8(line));
  }
}

void CommHub::handleFramedPayload(QTcpSocket* s, const QString& text) {
  if (text.isEmpty()) return;
  const QString peer = peerEndpointOf(s);
  if (!peer.isEmpty()) lastPeerEndpoint_ = peer;
  const QString tcpDev = primaryTcpDevice();
  lastRx_ = text;
  appendTranscript(QStringLiteral("RX"),
                   peer.isEmpty() ? text
                                  : QStringLiteral("%1 ← %2").arg(text, peer));
  emit payloadReceived(tcpDev.isEmpty() ? QStringLiteral("TCP") : tcpDev, text);

  DeviceTxStatus& st = deviceTx_[tcpDev.isEmpty() ? QStringLiteral("TCP") : tcpDev];
  st.lastPeer = peer;
  st.lastPeerRx = text.left(120);
  st.lastMs = QDateTime::currentMSecsSinceEpoch();

  // Server/listen role: reply with configured ack_ and attribute peer ACK to tcp device.
  if (server_ && server_->isListening() && peers_.contains(s) && !ack_.isEmpty()) {
    s->write(framePayload(ack_));
    s->flush();
    appendTranscript(QStringLiteral("TX"),
                     QStringLiteral("%1 → %2").arg(ack_, peer));
    noteDeviceAck(tcpDev.isEmpty() ? QStringLiteral("TCP") : tcpDev, ack_, peer);
    return;
  }

  // Client role (or any socket): inbound payload that looks like our ACK → attribute.
  const bool looksAck =
      (!ack_.isEmpty() && (text == ack_ || text.startsWith(ack_))) ||
      text.startsWith(QLatin1String("ACK"), Qt::CaseInsensitive);
  if (looksAck) {
    const QString dest =
        !lastTxDevice_.isEmpty()
            ? lastTxDevice_
            : (tcpDev.isEmpty() ? QStringLiteral("TCP") : tcpDev);
    noteDeviceAck(dest, text, peer);
  } else {
    emit deviceTxChanged(tcpDev.isEmpty() ? QStringLiteral("TCP") : tcpDev);
  }
}

bool CommHub::probeLocalPeerAck(QString* detail) {
  if (!server_ || !server_->isListening() || listenPort_ == 0) {
    if (detail) *detail = QStringLiteral("no-listen");
    return false;
  }
  const QString tcpDev = primaryTcpDevice();
  const int before = deviceTx_.value(tcpDev).peerAckCount;
  QTcpSocket sock;
  const QString host =
      listenHost_.isEmpty() ? QStringLiteral("127.0.0.1") : listenHost_;
  sock.connectToHost(QHostAddress(host), listenPort_);
  if (!sock.waitForConnected(800)) {
    if (detail)
      *detail = QStringLiteral("connect-fail:%1").arg(sock.errorString());
    return false;
  }
  const QString ping = QStringLiteral("PEERPROBE");
  sock.write(framePayload(ping));
  sock.flush();
  QByteArray got;
  for (int i = 0; i < 40; ++i) {
    QCoreApplication::processEvents(QEventLoop::AllEvents, 25);
    if (sock.waitForReadyRead(50)) {
      got.append(sock.readAll());
      if (!got.isEmpty()) break;
    }
  }
  sock.disconnectFromHost();
  if (sock.state() != QAbstractSocket::UnconnectedState)
    sock.waitForDisconnected(300);

  const QString gotText = QString::fromUtf8(got).trimmed();
  const int after = deviceTx_.value(tcpDev).peerAckCount;
  const bool acked =
      (after > before) ||
      (!ack_.isEmpty() && gotText.contains(ack_)) ||
      gotText.startsWith(QLatin1String("ACK"), Qt::CaseInsensitive);
  if (detail) {
    *detail = QStringLiteral("%1 peer=%2 before=%3 after=%4 rx=%5")
                  .arg(acked ? QStringLiteral("ok") : QStringLiteral("fail"),
                       lastPeerEndpoint_.isEmpty() ? QStringLiteral("-")
                                                   : lastPeerEndpoint_)
                  .arg(before)
                  .arg(after)
                  .arg(gotText.left(48));
  }
  return acked;
}

void CommHub::onSocketError() {
  QTcpSocket* s = qobject_cast<QTcpSocket*>(sender());
  const QString err = s ? s->errorString() : QStringLiteral("socket error");
  appendTranscript(QStringLiteral("ERR"), err);
  tcpStatus_ = QStringLiteral("error · %1")
                   .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
  emit statusChanged(tcpStatus_);
  if (reconnectEnabled_ && client_ && s == client_ && reconnectTimer_ &&
      !reconnectTimer_->isActive())
    reconnectTimer_->start();
}

void CommHub::onClientDisconnected() {
  if (client_) len4Buf_.remove(client_);
  appendTranscript(QStringLiteral("SYS"),
                   QStringLiteral("client disconnected · %1")
                       .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_));
  tcpStatus_ = QStringLiteral("disconnected · %1")
                   .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
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
    tcpStatus_ = QStringLiteral("reconnect paused #%1 %2:%3 · %4")
                     .arg(reconnectAttempts_ - 1)
                     .arg(reconnectHost_)
                     .arg(reconnectPort_)
                     .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
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
  tcpStatus_ = QStringLiteral("reconnecting #%1 %2:%3 · backoff %4ms · %5")
                   .arg(reconnectAttempts_)
                   .arg(reconnectHost_)
                   .arg(reconnectPort_)
                   .arg(reconnectTimer_ ? reconnectTimer_->interval() : 0)
                   .arg(framing_.isEmpty() ? QStringLiteral("lf") : framing_);
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
