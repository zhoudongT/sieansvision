#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QTcpServer>
#include <QTcpSocket>
#include <QHash>
#include <QVariantMap>

namespace sieans_qt {

/** LocalBus (in-process) + optional real TCP server/client for passgate TX/RX. */
class CommHub : public QObject {
  Q_OBJECT
 public:
  explicit CommHub(QObject* parent = nullptr);
  ~CommHub() override;

  void loadFromCommManager(const QVariantMap& cm);
  QVariantMap commManager() const { return cm_; }

  QStringList devices() const;
  QString deviceProtocol(const QString& name) const;
  QVariantMap deviceInfo(const QString& name) const;
  QVariantList deviceList() const;

  /** Soft LocalBus TX — always records transcript; also mirrors to TCP if up. */
  bool sendPayload(const QString& deviceName, const QString& payload,
                   QString* error = nullptr);

  /** Start TCP from tcpReal (server listen or client connect). */
  bool startTcp(QString* error = nullptr);
  void stopTcp();
  bool tcpActive() const;
  QString tcpStatus() const { return tcpStatus_; }

  QStringList transcript() const { return transcript_; }
  void clearTranscript();
  QString lastTx() const { return lastTx_; }
  QString lastRx() const { return lastRx_; }

  /** Expand ${flow.x} / ${x} placeholders from vars map. */
  static QString expandTemplate(const QString& tmpl, const QVariantMap& vars);

 signals:
  void transcriptChanged();
  void statusChanged(const QString& status);
  void payloadReceived(const QString& device, const QString& payload);

 private slots:
  void onNewConnection();
  void onClientReadyRead();
  void onSocketError();

 private:
  void appendTranscript(const QString& tag, const QString& line);
  void sendTcpRaw(const QString& payload);

  QVariantMap cm_;
  QStringList transcript_;
  QString lastTx_;
  QString lastRx_;
  QString tcpStatus_ = QStringLiteral("idle");
  QString framing_ = QStringLiteral("lf");
  QString ack_;

  QTcpServer* server_ = nullptr;
  QTcpSocket* client_ = nullptr;   // outbound client role
  QList<QTcpSocket*> peers_;       // accepted server clients
};

}  // namespace sieans_qt
