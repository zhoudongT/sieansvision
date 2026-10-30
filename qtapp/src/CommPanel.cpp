#include "CommPanel.hpp"

#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QFormLayout>
#include <QScrollBar>

namespace sieans_qt {

CommPanel::CommPanel(CommHub* hub, QWidget* parent)
    : QWidget(parent), hub_(hub) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  auto* title = new QLabel(QStringLiteral("通信 · TCP / LocalBus"));
  title->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title);

  status_ = new QLabel(QStringLiteral("TCP: idle"));
  status_->setObjectName(QStringLiteral("muted"));
  lay->addWidget(status_);

  auto* form = new QFormLayout;
  deviceCombo_ = new QComboBox;
  form->addRow(QStringLiteral("设备"), deviceCombo_);
  payloadEdit_ = new QLineEdit(
      QStringLiteral("BARCODE ok=${flow.passGate} text=${flow.barcodeText}"));
  form->addRow(QStringLiteral("报文"), payloadEdit_);
  lay->addLayout(form);

  auto* row = new QHBoxLayout;
  auto* btnTcp = new QPushButton(QStringLiteral("启动 TCP"));
  btnTcp->setObjectName(QStringLiteral("accentBtn"));
  auto* btnStop = new QPushButton(QStringLiteral("停止 TCP"));
  auto* btnSend = new QPushButton(QStringLiteral("试发"));
  auto* btnClear = new QPushButton(QStringLiteral("清空日志"));
  row->addWidget(btnTcp);
  row->addWidget(btnStop);
  row->addWidget(btnSend);
  row->addWidget(btnClear);
  lay->addLayout(row);

  transcript_ = new QPlainTextEdit;
  transcript_->setReadOnly(true);
  transcript_->setPlaceholderText(
      QStringLiteral("TX/RX 抄本 · LocalBus 软总线 + 真 TCP"));
  lay->addWidget(transcript_, 1);

  connect(btnTcp, &QPushButton::clicked, this, &CommPanel::onStartTcp);
  connect(btnStop, &QPushButton::clicked, this, &CommPanel::onStopTcp);
  connect(btnSend, &QPushButton::clicked, this, &CommPanel::onTrialSend);
  connect(btnClear, &QPushButton::clicked, this, [this]() {
    if (hub_) hub_->clearTranscript();
  });
  if (hub_) {
    connect(hub_, &CommHub::transcriptChanged, this, &CommPanel::refreshTranscript);
    connect(hub_, &CommHub::statusChanged, this, [this](const QString& s) {
      status_->setText(QStringLiteral("TCP: %1").arg(s));
    });
  }
}

void CommPanel::bindDocument(const QVariantMap& commManager) {
  if (hub_) hub_->loadFromCommManager(commManager);
  deviceCombo_->clear();
  if (hub_) {
    for (const QString& d : hub_->devices()) deviceCombo_->addItem(d);
  }
  if (deviceCombo_->count() == 0)
    deviceCombo_->addItem(QStringLiteral("LocalLoop"));
  refreshTranscript();
}

void CommPanel::setFlowVars(const QVariantMap& vars) { vars_ = vars; }

void CommPanel::refreshTranscript() {
  if (!hub_) return;
  transcript_->setPlainText(hub_->transcript().join(QLatin1Char('\n')));
  auto* bar = transcript_->verticalScrollBar();
  if (bar) bar->setValue(bar->maximum());
}

void CommPanel::onTrialSend() {
  if (!hub_) return;
  const QString payload =
      CommHub::expandTemplate(payloadEdit_->text(), vars_);
  QString err;
  hub_->sendPayload(deviceCombo_->currentText(), payload, &err);
}

void CommPanel::onStartTcp() {
  if (!hub_) return;
  QString err;
  if (!hub_->startTcp(&err) && !err.isEmpty()) {
    status_->setText(QStringLiteral("TCP: %1").arg(err));
  }
}

void CommPanel::onStopTcp() {
  if (hub_) hub_->stopTcp();
}

}  // namespace sieans_qt
