#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QTcpServer>
#include <QTcpSocket>
#include <QHash>
#include <QByteArray>
#include <QVariantMap>
#include <QTimer>

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

  /** Soft LocalBus TX — records transcript + TX→RX echo; mirrors to TCP if up. */
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
  QString lastTxDevice() const { return lastTxDevice_; }

  /** Per-device last TX / ACK chrome (wave222+224 peer ACK). */
  struct DeviceTxStatus {
    QString lastTx;
    QString lastAck;
    QString lastPeer;   // live TCP peer endpoint ip:port
    QString lastPeerRx; // last RX attributed to this device from a peer
    QString status;  // TX | TX+echo | TX soft | TX+ACK | peerACK | ACK
    int txCount = 0;
    int ackCount = 0;
    int peerAckCount = 0;
    qint64 lastMs = 0;
  };
  DeviceTxStatus deviceTxStatus(const QString& name) const;
  QHash<QString, DeviceTxStatus> deviceTxMap() const { return deviceTx_; }
  QString primaryTcpDevice() const;
  int livePeerCount() const;
  QString lastPeerEndpoint() const { return lastPeerEndpoint_; }
  /** Smoke/helper: connect loopback peer, send probe, expect tcpReal.ack reply. */
  bool probeLocalPeerAck(QString* detail = nullptr);
  /** Smoke/helper: hold loopback peer, TX payload via primaryTcpDevice (OK path). */
  bool smokePeerHostTx(const QString& payload, QString* detail = nullptr);

  /** Expand ${flow.x} / ${x} / {name} / {{name}} placeholders from vars map. */
  static QString expandTemplate(const QString& tmpl, const QVariantMap& vars);
  /** 解析流程 I/O 绑定：裸 flow.x / host.x，或 ${flow.x}/{name}/{{name}} 模板。 */
  static QVariant resolveBinding(const QString& binding, const QVariantMap& vars,
                                 const QVariantMap& sourceConfig = QVariantMap(),
                                 const QString& sourceImageHint = QString());
  /** 绑定结果为空时使用 emptyDefault（再展开一次模板）。 */
  static QVariant resolveBindingOrDefault(const QString& binding,
                                          const QString& emptyDefault,
                                          const QVariantMap& vars,
                                          const QVariantMap& sourceConfig = QVariantMap(),
                                          const QString& sourceImageHint = QString());
  /** I/O 与通信模板解析一致性。空列表表示通过。 */
  static QStringList ioResolveSelfTest();

 signals:
  void transcriptChanged();
  void statusChanged(const QString& status);
  void payloadReceived(const QString& device, const QString& payload);
  void deviceTxChanged(const QString& device);

 private slots:
  void onNewConnection();
  void onClientReadyRead();
  void onSocketError();
  void onClientDisconnected();
  void tryReconnect();

 private:
  void appendTranscript(const QString& tag, const QString& line);
  void sendTcpRaw(const QString& payload);
  void noteDeviceTx(const QString& device, const QString& payload,
                    const QString& status);
  void noteDeviceAck(const QString& device, const QString& ack,
                     const QString& peer = QString());
  void handleFramedPayload(QTcpSocket* s, const QString& text);
  QString peerEndpointOf(QTcpSocket* s) const;
  QByteArray framePayload(const QString& payload) const;

  QVariantMap cm_;
  QStringList transcript_;
  QString lastTx_;
  QString lastRx_;
  QString lastTxDevice_;
  QString lastPeerEndpoint_;
  QHash<QString, DeviceTxStatus> deviceTx_;
  QHash<QTcpSocket*, QString> peerKeys_;
  QString tcpStatus_ = QStringLiteral("idle");
  QString framing_ = QStringLiteral("lf");
  QString ack_;

  QTcpServer* server_ = nullptr;
  QTcpSocket* client_ = nullptr;   // outbound client role
  QList<QTcpSocket*> peers_;       // accepted server clients
  bool reconnectEnabled_ = false;
  QString reconnectHost_;
  quint16 reconnectPort_ = 0;
  QTimer* reconnectTimer_ = nullptr;
  int reconnectAttempts_ = 0;
  QHash<QTcpSocket*, QByteArray> len4Buf_;  // incomplete len4 frames
  QString listenHost_;
  quint16 listenPort_ = 0;
  void refreshListenStatus();
};

}  // namespace sieans_qt
