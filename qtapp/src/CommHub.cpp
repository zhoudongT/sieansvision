#include "CommHub.hpp"

#include <QDateTime>
#include <QHostAddress>
#include <QRegularExpression>

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
  QRegularExpression re(QStringLiteral(R"(\$\{(?:flow\.)?([A-Za-z_][A-Za-z0-9_]*)\})"));
  QRegularExpressionMatchIterator it = re.globalMatch(tmpl);
  // Replace from end to keep indices stable — collect pairs first
  struct Rep { int start; int len; QString val; };
  QVector<Rep> reps;
  while (it.hasNext()) {
    const auto m = it.next();
    const QString key = m.captured(1);
    reps.push_back({static_cast<int>(m.capturedStart()), static_cast<int>(m.capturedLength()),
                    vars.value(key).toString()});
  }
  for (int i = reps.size() - 1; i >= 0; --i) {
    out.replace(reps[i].start, reps[i].len, reps[i].val);
  }
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

  // Soft LocalBus always accepts
  // If TCP device or tcpReal active, also push on wire
  const bool wantTcp =
      proto.contains(QStringLiteral("TCP"), Qt::CaseInsensitive) || tcpActive();
  if (wantTcp && tcpActive()) {
    sendTcpRaw(payload);
  }
  return true;
}

void CommHub::sendTcpRaw(const QString& payload) {
  QByteArray bytes = payload.toUtf8();
  if (framing_ == QLatin1String("crlf"))
    bytes.append("\r\n");
  else if (framing_ == QLatin1String("lf") || framing_.isEmpty())
    bytes.append('\n');
  // raw / len4: send as-is (len4 simplified to raw for this wave)

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
    client_ = new QTcpSocket(this);
    connect(client_, &QTcpSocket::readyRead, this, &CommHub::onClientReadyRead);
    connect(client_, &QTcpSocket::errorOccurred, this, &CommHub::onSocketError);
    connect(client_, &QTcpSocket::connected, this, [this, host, port]() {
      tcpStatus_ = QStringLiteral("connected %1:%2").arg(host).arg(port);
      emit statusChanged(tcpStatus_);
      appendTranscript(QStringLiteral("SYS"), tcpStatus_);
    });
    client_->connectToHost(host, port);
    tcpStatus_ = QStringLiteral("connecting %1:%2").arg(host).arg(port);
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
  tcpStatus_ = QStringLiteral("listening %1:%2").arg(host).arg(port);
  emit statusChanged(tcpStatus_);
  appendTranscript(QStringLiteral("SYS"), tcpStatus_);
  return true;
}

void CommHub::stopTcp() {
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
  if (tcpStatus_ != QLatin1String("idle")) {
    tcpStatus_ = QStringLiteral("idle");
    emit statusChanged(tcpStatus_);
    appendTranscript(QStringLiteral("SYS"), QStringLiteral("TCP stopped"));
  }
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
    });
    appendTranscript(QStringLiteral("SYS"),
                     QStringLiteral("peer connected %1")
                         .arg(s->peerAddress().toString()));
    tcpStatus_ = QStringLiteral("peer-connected");
    emit statusChanged(tcpStatus_);
  }
}

void CommHub::onClientReadyRead() {
  QObject* src = sender();
  QTcpSocket* s = qobject_cast<QTcpSocket*>(src);
  if (!s) return;
  const QByteArray raw = s->readAll();
  QString text = QString::fromUtf8(raw).trimmed();
  if (text.isEmpty()) return;
  lastRx_ = text;
  appendTranscript(QStringLiteral("RX"), text.left(240));
  emit payloadReceived(QStringLiteral("TCP"), text);
  if (!ack_.isEmpty() && s->state() == QAbstractSocket::ConnectedState) {
    QByteArray a = ack_.toUtf8();
    if (framing_ == QLatin1String("crlf")) a.append("\r\n");
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
}

}  // namespace sieans_qt
