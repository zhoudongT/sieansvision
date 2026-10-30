#include "CommPanel.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QFormLayout>
#include <QHeaderView>
#include <QScrollBar>

namespace sieans_qt {

CommPanel::CommPanel(CommHub* hub, QWidget* parent)
    : QWidget(parent), hub_(hub) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  auto* title = new QLabel(QStringLiteral("通信 · 多设备 TCP / LocalBus"));
  title->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title);

  status_ = new QLabel(QStringLiteral("TCP: idle"));
  status_->setObjectName(QStringLiteral("muted"));
  lay->addWidget(status_);

  deviceTable_ = new QTableWidget(0, 5);
  deviceTable_->setHorizontalHeaderLabels(
      {QStringLiteral("名称"), QStringLiteral("协议"), QStringLiteral("主机"),
       QStringLiteral("端口"), QStringLiteral("启用")});
  deviceTable_->horizontalHeader()->setStretchLastSection(true);
  deviceTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  deviceTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
  deviceTable_->setSelectionMode(QAbstractItemView::SingleSelection);
  deviceTable_->setMaximumHeight(120);
  lay->addWidget(deviceTable_);
  connect(deviceTable_, &QTableWidget::itemSelectionChanged, this,
          &CommPanel::onDeviceRowChanged);

  detail_ = new QLabel(QStringLiteral("选择设备查看备注"));
  detail_->setObjectName(QStringLiteral("muted"));
  detail_->setWordWrap(true);
  lay->addWidget(detail_);

  auto* form = new QFormLayout;
  deviceCombo_ = new QComboBox;
  form->addRow(QStringLiteral("试发设备"), deviceCombo_);
  hostEdit_ = new QLineEdit;
  hostEdit_->setPlaceholderText(QStringLiteral("tcpReal host"));
  portEdit_ = new QLineEdit;
  portEdit_->setPlaceholderText(QStringLiteral("port"));
  auto* hp = new QHBoxLayout;
  hp->addWidget(hostEdit_);
  hp->addWidget(portEdit_);
  form->addRow(QStringLiteral("TCP 端点"), hp);
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
  const QVariantMap tcp = commManager.value(QStringLiteral("tcpReal")).toMap();
  hostEdit_->setText(tcp.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString());
  portEdit_->setText(QString::number(tcp.value(QStringLiteral("port"), 19956).toInt()));
  refreshDevices();
  refreshTranscript();
}

void CommPanel::refreshDevices() {
  deviceCombo_->clear();
  deviceTable_->setRowCount(0);
  if (!hub_) return;
  const QVariantList list = hub_->deviceList();
  for (const QVariant& v : list) {
    const QVariantMap d = v.toMap();
    const QString name = d.value(QStringLiteral("name")).toString();
    if (name.isEmpty()) continue;
    deviceCombo_->addItem(name);
    const int row = deviceTable_->rowCount();
    deviceTable_->insertRow(row);
    deviceTable_->setItem(row, 0, new QTableWidgetItem(name));
    deviceTable_->setItem(
        row, 1, new QTableWidgetItem(d.value(QStringLiteral("protocol")).toString()));
    deviceTable_->setItem(
        row, 2, new QTableWidgetItem(d.value(QStringLiteral("host")).toString()));
    deviceTable_->setItem(
        row, 3,
        new QTableWidgetItem(QString::number(d.value(QStringLiteral("port")).toInt())));
    deviceTable_->setItem(
        row, 4,
        new QTableWidgetItem(d.value(QStringLiteral("enabled"), true).toBool()
                                 ? QStringLiteral("是")
                                 : QStringLiteral("否")));
    deviceTable_->item(row, 0)->setData(Qt::UserRole, d.value(QStringLiteral("remark")));
  }
  if (deviceCombo_->count() == 0) {
    deviceCombo_->addItem(QStringLiteral("LocalLoop"));
    deviceTable_->insertRow(0);
    deviceTable_->setItem(0, 0, new QTableWidgetItem(QStringLiteral("LocalLoop")));
    deviceTable_->setItem(0, 1, new QTableWidgetItem(QStringLiteral("Local Bus")));
  }
  if (deviceTable_->rowCount() > 0) deviceTable_->selectRow(0);
}

void CommPanel::onDeviceRowChanged() {
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  const int idx = deviceCombo_->findText(name);
  if (idx >= 0) deviceCombo_->setCurrentIndex(idx);
  const QString remark = nameItem->data(Qt::UserRole).toString();
  const QString proto =
      deviceTable_->item(row, 1) ? deviceTable_->item(row, 1)->text() : QString();
  const QString host =
      deviceTable_->item(row, 2) ? deviceTable_->item(row, 2)->text() : QString();
  const QString port =
      deviceTable_->item(row, 3) ? deviceTable_->item(row, 3)->text() : QString();
  detail_->setText(QStringLiteral("[%1] %2 · %3:%4 · %5")
                       .arg(proto, name, host, port,
                            remark.isEmpty() ? QStringLiteral("(无备注)") : remark));
  if (!host.isEmpty()) hostEdit_->setText(host);
  if (!port.isEmpty() && port != QLatin1String("0")) portEdit_->setText(port);
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
  const QString payload = CommHub::expandTemplate(payloadEdit_->text(), vars_);
  QString err;
  hub_->sendPayload(deviceCombo_->currentText(), payload, &err);
}

void CommPanel::onStartTcp() {
  if (!hub_) return;
  // push endpoint edits into tcpReal before start
  QVariantMap cm = hub_->commManager();
  QVariantMap tcp = cm.value(QStringLiteral("tcpReal")).toMap();
  if (!hostEdit_->text().isEmpty()) tcp.insert(QStringLiteral("host"), hostEdit_->text());
  if (!portEdit_->text().isEmpty())
    tcp.insert(QStringLiteral("port"), portEdit_->text().toInt());
  cm.insert(QStringLiteral("tcpReal"), tcp);
  hub_->loadFromCommManager(cm);
  QString err;
  if (!hub_->startTcp(&err) && !err.isEmpty())
    status_->setText(QStringLiteral("TCP: %1").arg(err));
}

void CommPanel::onStopTcp() {
  if (hub_) hub_->stopTcp();
}

}  // namespace sieans_qt
