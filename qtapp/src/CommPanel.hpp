#pragma once

#include "CommHub.hpp"

#include <QWidget>
#include <QPlainTextEdit>
#include <QComboBox>
#include <QLineEdit>
#include <QLabel>
#include <QCheckBox>
#include <QTableWidget>
#include <QVariantMap>
#include <QHBoxLayout>

class QEvent;

namespace sieans_qt {

class CommPanel : public QWidget {
  Q_OBJECT
 public:
  explicit CommPanel(CommHub* hub, QWidget* parent = nullptr);

  void bindDocument(const QVariantMap& commManager);
  void setFlowVars(const QVariantMap& vars);

 public slots:
  void refreshTranscript();
  void refreshDevices();
  void onTrialSend();
  void onStartTcp();
  void onStopTcp();

 signals:
  void requestSaveComm(const QVariantMap& cm);

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

 private:
  void onDeviceRowChanged();
  void onRemarkEdit();
  void pushTcpEndpoint(bool emitSave);
  void syncFramingFromDoc(const QVariantMap& tcp);
  void rebuildVarChips();
  void refreshDeviceTxChrome();
  void refreshHostResultStrip();
  void insertFlowToken(const QString& key);
  void copyTranscriptFiltered();
  void toggleTcp();
  void applyFraming(const QString& framing);
  void applyPayloadPreset(const QString& kind);
  void pasteEndpointFromClipboard();
  void pushPayloadHistory();
  void recallPayloadHistory(int delta);
  void removeCurrentPayloadHistory();
  void clearPayloadHistory();
  void reversePayloadHistory();
  void dedupePayloadHistory();
  void sortPayloadHistory();
  void exportPayloadHistoryJson();
  void importPayloadHistoryJson();
  void copyPayloadHistoryText();
  void copyFramingPayload();
  void pasteFramingPayload();
  void cycleFraming(int delta);
  void loadLastRxToPayload();
  void loadLastTxToPayload();
  void copyLastTxRx();
  void copyEndpoint();
  void writeBackSelectedDeviceEndpoint();
  void copySelectedDeviceEndpoint();
  void toggleSelectedDeviceEnabled();
  void setAllDevicesEnabled(bool on);
  void addDeviceRow();
  void duplicateSelectedDevice();
  void removeSelectedDevice();
  void moveSelectedDevice(int delta);
  void moveSelectedDeviceToEdge(int edge);
  void sortDevicesByName();
  void reverseDeviceOrder();
  void dedupeDevicesByName();
  void exportDevicesJson();
  void importDevicesJson();
  void cutSelectedDevice();
  void mergePasteDevicesFromClipboard();

  CommHub* hub_ = nullptr;
  QTableWidget* deviceTable_ = nullptr;
  QComboBox* deviceCombo_ = nullptr;
  QLineEdit* payloadEdit_ = nullptr;
  QLineEdit* hostEdit_ = nullptr;
  QLineEdit* portEdit_ = nullptr;
  QComboBox* framingCombo_ = nullptr;
  QLineEdit* ackEdit_ = nullptr;
  QCheckBox* reconnectCheck_ = nullptr;
  QLabel* bindSummary_ = nullptr;
  QWidget* varChipHost_ = nullptr;
  QHBoxLayout* varChipLay_ = nullptr;
  QPlainTextEdit* transcript_ = nullptr;
  QLineEdit* txFilter_ = nullptr;
  QStringList transcriptAll_;
  QLabel* status_ = nullptr;
  QLabel* hostResultStrip_ = nullptr;
  QLabel* detail_ = nullptr;
  QVariantMap vars_;
  QStringList payloadHistory_;
  int payloadHistoryIdx_ = -1;
};

}  // namespace sieans_qt
