#pragma once

#include "CommHub.hpp"

#include <QWidget>
#include <QPlainTextEdit>
#include <QComboBox>
#include <QLineEdit>
#include <QLabel>
#include <QTableWidget>
#include <QVariantMap>

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

 private:
  void onDeviceRowChanged();

  CommHub* hub_ = nullptr;
  QTableWidget* deviceTable_ = nullptr;
  QComboBox* deviceCombo_ = nullptr;
  QLineEdit* payloadEdit_ = nullptr;
  QLineEdit* hostEdit_ = nullptr;
  QLineEdit* portEdit_ = nullptr;
  QPlainTextEdit* transcript_ = nullptr;
  QLabel* status_ = nullptr;
  QLabel* detail_ = nullptr;
  QVariantMap vars_;
};

}  // namespace sieans_qt
