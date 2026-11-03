#include "CommPanel.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QFormLayout>
#include <QHeaderView>
#include <QScrollBar>
#include <QShortcut>
#include <QKeySequence>
#include <QInputDialog>
#include <QMessageBox>
#include <QAbstractItemView>

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
  setStatusTip(QStringLiteral("通信面板 · LocalBus/TCP · peers/framing(lf/crlf/raw/len4) · 模板 ${flow.x}/{name}/{{name}} · AUTO_TCP bump"));
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
  deviceTable_->setToolTip(QStringLiteral("通信设备表 · 选中后试发 / 查看备注 · framing 见启动 tip · 帧分隔见 framing 下拉 · 双击编辑备注"));
  deviceTable_->setStatusTip(QStringLiteral("通信 · 设备表 · LocalBus/TCP"));
  lay->addWidget(deviceTable_);
  connect(deviceTable_, &QTableWidget::itemSelectionChanged, this,
          &CommPanel::onDeviceRowChanged);
  connect(deviceTable_, &QTableWidget::itemDoubleClicked, this,
          [this](QTableWidgetItem*) { onRemarkEdit(); });

  detail_ = new QLabel(QStringLiteral("选择设备查看备注"));
  detail_->setObjectName(QStringLiteral("muted"));
  detail_->setWordWrap(true);
  lay->addWidget(detail_);

  auto* form = new QFormLayout;
  deviceCombo_ = new QComboBox;
  form->addRow(QStringLiteral("试发设备"), deviceCombo_);
  hostEdit_ = new QLineEdit;
  hostEdit_->setPlaceholderText(QStringLiteral("tcpReal host"));
  hostEdit_->setToolTip(QStringLiteral("TCP host · client 连接目标 / server 绑定 · 空=本机"));
  portEdit_ = new QLineEdit;
  portEdit_->setPlaceholderText(QStringLiteral("port"));
  portEdit_->setToolTip(QStringLiteral("TCP port · listen/connect · AUTO_TCP 可 bump +1..+4 · 1-65535"));
  auto* hp = new QHBoxLayout;
  hp->addWidget(hostEdit_);
  hp->addWidget(portEdit_);
  form->addRow(QStringLiteral("TCP 端点"), hp);
  framingCombo_ = new QComboBox;
  framingCombo_->setObjectName(QStringLiteral("framingCombo"));
  framingCombo_->addItem(QStringLiteral("LF (\\n)"), QStringLiteral("lf"));
  framingCombo_->addItem(QStringLiteral("CRLF (\\r\\n)"), QStringLiteral("crlf"));
  framingCombo_->addItem(QStringLiteral("Raw 原样"), QStringLiteral("raw"));
  framingCombo_->addItem(QStringLiteral("Len4 BE 前缀"), QStringLiteral("len4"));
  framingCombo_->setToolTip(
      QStringLiteral("TCP 帧分隔 · lf/crlf/raw/len4 · 写入 tcpReal.framing · 启动前可改 · 运行中改写下次生效"));
  framingCombo_->setStatusTip(QStringLiteral("通信 · framing lf/crlf/raw/len4"));
  form->addRow(QStringLiteral("帧分隔"), framingCombo_);
  connect(framingCombo_, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
          [this](int) { pushTcpEndpoint(true); });
  payloadEdit_ = new QLineEdit(
      QStringLiteral("BARCODE ok=${flow.passGate} text=${flow.barcodeText}"));
  payloadEdit_->setToolTip(
      QStringLiteral("报文模板 · ${flow.x} / {name} / {{name}} · Enter/Ctrl+Enter 试发 · LocalBus echo"));
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
      QStringLiteral("TX/RX 抄本 · LocalBus 软总线 + 真 TCP · peers 见状态行"));
  lay->addWidget(transcript_, 1);

  btnTcp->setToolTip(QStringLiteral("启动 tcpReal（server 监听 / client 连接+重连）· framing lf/crlf/raw/len4 · framing 见启动 tip · 状态见徽章"));
  btnStop->setToolTip(QStringLiteral("停止 TCP · 清空重连计数 · framing 保留到下次启动 · peers 断开"));
  btnSend->setToolTip(QStringLiteral("按报文模板试发到所选设备（支持 ${flow.x}/{name}/{{name}}）· Enter/Ctrl+Enter"));
  btnClear->setToolTip(QStringLiteral("清空 TX/RX 抄本 · Ctrl+L"));
  connect(btnTcp, &QPushButton::clicked, this, &CommPanel::onStartTcp);
  connect(btnStop, &QPushButton::clicked, this, &CommPanel::onStopTcp);
  connect(btnSend, &QPushButton::clicked, this, &CommPanel::onTrialSend);
  connect(payloadEdit_, &QLineEdit::returnPressed, this, &CommPanel::onTrialSend);
  {
    auto* sc = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Return")), payloadEdit_);
    connect(sc, &QShortcut::activated, this, &CommPanel::onTrialSend);
    auto* sc2 = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Enter")), payloadEdit_);
    connect(sc2, &QShortcut::activated, this, &CommPanel::onTrialSend);
  }
  connect(btnClear, &QPushButton::clicked, this, [this]() {
    if (hub_) hub_->clearTranscript();
  });
  {
    auto* sc = new QShortcut(QKeySequence(QStringLiteral("Ctrl+L")), this);
    connect(sc, &QShortcut::activated, this, [this]() {
      if (hub_) hub_->clearTranscript();
    });
  }
  if (hub_) {
    connect(hub_, &CommHub::transcriptChanged, this, &CommPanel::refreshTranscript);
    connect(hub_, &CommHub::statusChanged, this, [this](const QString& s) {
      status_->setText(QStringLiteral("TCP: %1").arg(s));
      status_->setToolTip(QStringLiteral("TCP: %1 · framing/peers 见状态").arg(s));
      if (s.contains(QStringLiteral("reconnect")))
        status_->setStyleSheet(QStringLiteral("color:#e0b84a;font-weight:600;"));
      else if (s.contains(QStringLiteral("connected")) ||
               s.contains(QStringLiteral("listening")) ||
               s.contains(QStringLiteral("peer-connected")))
        status_->setStyleSheet(QStringLiteral("color:#3ecf8e;font-weight:600;"));
      else if (s.contains(QStringLiteral("listen-fail")) ||
               s.contains(QStringLiteral("error")) ||
               s.contains(QStringLiteral("disconnected")))
        status_->setStyleSheet(QStringLiteral("color:#e53935;font-weight:600;"));
      else if (s.contains(QStringLiteral("connecting")))
        status_->setStyleSheet(QStringLiteral("color:#64b5f6;font-weight:600;"));
      else
        status_->setStyleSheet(QString());
    });
  }
}

void CommPanel::bindDocument(const QVariantMap& commManager) {
  if (hub_) hub_->loadFromCommManager(commManager);
  const QVariantMap tcp = commManager.value(QStringLiteral("tcpReal")).toMap();
  hostEdit_->setText(tcp.value(QStringLiteral("host"), QStringLiteral("127.0.0.1")).toString());
  portEdit_->setText(QString::number(tcp.value(QStringLiteral("port"), 19956).toInt()));
  syncFramingFromDoc(tcp);
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
  // Keep status line aware of last TX/RX even when TCP idle (LocalBus path).
  if (status_) {
    const QString tx = hub_->lastTx().left(40);
    const QString rx = hub_->lastRx().left(40);
    if (!tx.isEmpty() || !rx.isEmpty()) {
      status_->setText(QStringLiteral("TCP: %1 · TX %2 · RX %3")
                           .arg(hub_->tcpStatus(),
                                tx.isEmpty() ? QStringLiteral("—") : tx,
                                rx.isEmpty() ? QStringLiteral("—") : rx));
    }
  }
}

void CommPanel::onTrialSend() {
  if (!hub_) return;
  const QString payload = CommHub::expandTemplate(payloadEdit_->text(), vars_);
  QString err;
  hub_->sendPayload(deviceCombo_->currentText(), payload, &err);
}

void CommPanel::onStartTcp() {
  if (!hub_) return;
  pushTcpEndpoint(true);
  QString err;
  if (!hub_->startTcp(&err) && !err.isEmpty())
    status_->setText(QStringLiteral("TCP: %1").arg(err));
}

void CommPanel::onStopTcp() {
  if (hub_) hub_->stopTcp();
}


void CommPanel::syncFramingFromDoc(const QVariantMap& tcp) {
  if (!framingCombo_) return;
  const QString fr = tcp.value(QStringLiteral("framing"), QStringLiteral("lf")).toString();
  const int idx = framingCombo_->findData(fr);
  framingCombo_->blockSignals(true);
  framingCombo_->setCurrentIndex(idx >= 0 ? idx : 0);
  framingCombo_->blockSignals(false);
}

void CommPanel::pushTcpEndpoint(bool emitSave) {
  if (!hub_) return;
  QVariantMap cm = hub_->commManager();
  QVariantMap tcp = cm.value(QStringLiteral("tcpReal")).toMap();
  if (hostEdit_ && !hostEdit_->text().isEmpty())
    tcp.insert(QStringLiteral("host"), hostEdit_->text());
  if (portEdit_ && !portEdit_->text().isEmpty())
    tcp.insert(QStringLiteral("port"), portEdit_->text().toInt());
  if (framingCombo_) {
    const QString fr = framingCombo_->currentData().toString();
    tcp.insert(QStringLiteral("framing"), fr.isEmpty() ? QStringLiteral("lf") : fr);
  }
  cm.insert(QStringLiteral("tcpReal"), tcp);
  hub_->loadFromCommManager(cm);
  if (status_ && framingCombo_) {
    status_->setToolTip(
        QStringLiteral("TCP: %1 · framing=%2")
            .arg(hub_->tcpStatus(),
                 framingCombo_->currentData().toString()));
  }
  if (emitSave) emit requestSaveComm(cm);
}

void CommPanel::onRemarkEdit() {
  if (!deviceTable_ || !hub_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  const QString cur = nameItem->data(Qt::UserRole).toString();
  bool ok = false;
  const QString next = QInputDialog::getText(
      this, QStringLiteral("设备备注"),
      QStringLiteral("备注 · %1").arg(name), QLineEdit::Normal, cur, &ok);
  if (!ok) return;
  nameItem->setData(Qt::UserRole, next);
  // write back into device list in commManager
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  bool found = false;
  for (int i = 0; i < devices.size(); ++i) {
    QVariantMap d = devices[i].toMap();
    if (d.value(QStringLiteral("name")).toString() == name) {
      d.insert(QStringLiteral("remark"), next);
      devices[i] = d;
      found = true;
      break;
    }
  }
  if (found) {
    cm.insert(QStringLiteral("devices"), devices);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  onDeviceRowChanged();
  if (detail_)
    detail_->setText(detail_->text() + QStringLiteral(" · 备注已保存"));
}


}  // namespace sieans_qt
