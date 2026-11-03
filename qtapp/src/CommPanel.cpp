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
#include <QCheckBox>
#include <QMessageBox>
#include <QAbstractItemView>
#include <QClipboard>
#include <QGuiApplication>
#include <QEvent>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QRegularExpression>
#include <initializer_list>
#include <utility>
#include <QPushButton>
#include <QScrollArea>

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
  setStatusTip(QStringLiteral("通信面板 · LocalBus/TCP · peers/framing(lf/crlf/raw/len4) · 快选芯片 · 模板预设 · Ctrl+T 启停 · 右键摘要粘贴端点 · Alt+↑↓ 报文历史 · ${flow.x} · AUTO_TCP bump"));
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
  {
    auto* frChips = new QHBoxLayout;
    frChips->setSpacing(4);
    for (const auto& pair : std::initializer_list<std::pair<const char*, const char*>>{
             {"LF", "lf"}, {"CRLF", "crlf"}, {"Raw", "raw"}, {"Len4", "len4"}}) {
      auto* b = new QPushButton(QString::fromUtf8(pair.first));
      b->setFlat(true);
      b->setCursor(Qt::PointingHandCursor);
      b->setObjectName(QStringLiteral("commFramingChip"));
      b->setStyleSheet(
          QStringLiteral("QPushButton{background:#32353a;color:#c8cdd4;border-radius:3px;"
                         "padding:2px 8px;font-size:11px;}"
                         "QPushButton:hover{background:#64b5f6;color:#102018;}"));
      const QString fr = QString::fromUtf8(pair.second);
      b->setToolTip(QStringLiteral("快速帧分隔 · %1").arg(fr));
      connect(b, &QPushButton::clicked, this, [this, fr]() { applyFraming(fr); });
      frChips->addWidget(b);
    }
    frChips->addStretch(1);
    form->addRow(QStringLiteral("快选"), frChips);
  }
  ackEdit_ = new QLineEdit;
  ackEdit_->setPlaceholderText(QStringLiteral("ACK 应答 · 空=不回"));
  ackEdit_->setToolTip(QStringLiteral("收到报文后自动回 ACK · 写入 tcpReal.ack · 空则不回 · 随 framing 附加换行"));
  form->addRow(QStringLiteral("ACK"), ackEdit_);
  connect(ackEdit_, &QLineEdit::editingFinished, this, [this]() { pushTcpEndpoint(true); });
  reconnectCheck_ = new QCheckBox(QStringLiteral("客户端断线重连"));
  reconnectCheck_->setChecked(true);
  reconnectCheck_->setToolTip(QStringLiteral("tcpReal.reconnect · client 模式断线自动重连 · 最多约 40 次"));
  form->addRow(QStringLiteral("重连"), reconnectCheck_);
  connect(reconnectCheck_, &QCheckBox::toggled, this, [this](bool) { pushTcpEndpoint(true); });
  bindSummary_ = new QLabel(QStringLiteral("绑定 · —"));
  bindSummary_->setObjectName(QStringLiteral("commBindSummary"));
  bindSummary_->setWordWrap(true);
  bindSummary_->setCursor(Qt::PointingHandCursor);
  bindSummary_->setToolTip(QStringLiteral("tcpReal 绑定摘要 · host:port · framing · ack · reconnect · 单击复制 · 右键从剪贴板粘贴 host:port · 中键切换重连"));
  bindSummary_->installEventFilter(this);
  form->addRow(QStringLiteral("摘要"), bindSummary_);
  payloadEdit_ = new QLineEdit(
      QStringLiteral("BARCODE ok=${flow.passGate} text=${flow.barcodeText}"));
  payloadEdit_->setToolTip(
      QStringLiteral("报文模板 · ${flow.x} / {name} / {{name}} · 下方芯片插入 · Enter/Ctrl+Enter 试发 · Alt+↑↓ 历史 · LocalBus echo"));
  form->addRow(QStringLiteral("报文"), payloadEdit_);
  payloadEdit_->installEventFilter(this);
  lay->addLayout(form);

  varChipHost_ = new QWidget;
  varChipHost_->setObjectName(QStringLiteral("commVarChips"));
  varChipLay_ = new QHBoxLayout(varChipHost_);
  varChipLay_->setContentsMargins(0, 0, 0, 2);
  varChipLay_->setSpacing(4);
  varChipLay_->addWidget(new QLabel(QStringLiteral("插入")));
  varChipLay_->addStretch(1);
  lay->addWidget(varChipHost_);
  {
    auto* presetRow = new QHBoxLayout;
    presetRow->setSpacing(4);
    presetRow->addWidget(new QLabel(QStringLiteral("模板")));
    for (const auto& pair : std::initializer_list<std::pair<const char*, const char*>>{
             {"OK", "ok"}, {"NG", "ng"}, {"Echo", "echo"}, {"RawText", "raw"}}) {
      auto* b = new QPushButton(QString::fromUtf8(pair.first));
      b->setFlat(true);
      b->setCursor(Qt::PointingHandCursor);
      b->setStyleSheet(
          QStringLiteral("QPushButton{background:#2a3340;color:#c8cdd4;border-radius:3px;"
                         "padding:2px 8px;font-size:11px;}"
                         "QPushButton:hover{background:#3ecf8e;color:#102018;}"));
      const QString kind = QString::fromUtf8(pair.second);
      b->setToolTip(QStringLiteral("报文预设 · %1").arg(kind));
      connect(b, &QPushButton::clicked, this, [this, kind]() { applyPayloadPreset(kind); });
      presetRow->addWidget(b);
    }
    presetRow->addStretch(1);
    lay->addLayout(presetRow);
  }

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

  txFilter_ = new QLineEdit;
  txFilter_->setObjectName(QStringLiteral("commTxFilter"));
  txFilter_->setPlaceholderText(QStringLiteral("过滤抄本 · Ctrl+F · Esc 清空"));
  txFilter_->setClearButtonEnabled(true);
  txFilter_->setToolTip(QStringLiteral("通信抄本过滤 · TX/RX/状态行 · Ctrl+F 聚焦"));
  lay->addWidget(txFilter_);
  connect(txFilter_, &QLineEdit::textChanged, this, [this](const QString&) { refreshTranscript(); });
  {
    auto* scF = new QShortcut(QKeySequence(QStringLiteral("Ctrl+F")), this);
    connect(scF, &QShortcut::activated, this, [this]() {
      if (!txFilter_) return;
      txFilter_->setFocus(Qt::ShortcutFocusReason);
      txFilter_->selectAll();
    });
    auto* scEsc = new QShortcut(QKeySequence(Qt::Key_Escape), txFilter_);
    connect(scEsc, &QShortcut::activated, this, [this]() {
      if (txFilter_ && !txFilter_->text().isEmpty()) txFilter_->clear();
    });
  }
  transcript_ = new QPlainTextEdit;
  transcript_->setReadOnly(true);
  transcript_->setPlaceholderText(
      QStringLiteral("TX/RX 抄本 · LocalBus 软总线 + 真 TCP · peers 见状态行 · 过滤见上方"));
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
    auto* scCopy = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), this);
    connect(scCopy, &QShortcut::activated, this, &CommPanel::copyTranscriptFiltered);
    auto* scT = new QShortcut(QKeySequence(QStringLiteral("Ctrl+T")), this);
    connect(scT, &QShortcut::activated, this, &CommPanel::toggleTcp);
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
  if (ackEdit_) {
    ackEdit_->blockSignals(true);
    ackEdit_->setText(tcp.value(QStringLiteral("ack")).toString());
    ackEdit_->blockSignals(false);
  }
  if (reconnectCheck_) {
    reconnectCheck_->blockSignals(true);
    reconnectCheck_->setChecked(tcp.value(QStringLiteral("reconnect"), true).toBool());
    reconnectCheck_->blockSignals(false);
  }
  if (bindSummary_) {
    const QString host = tcp.value(QStringLiteral("host")).toString();
    const int port = tcp.value(QStringLiteral("port"), 9000).toInt();
    const QString fr = tcp.value(QStringLiteral("framing"), QStringLiteral("lf")).toString();
    const QString ack = tcp.value(QStringLiteral("ack")).toString();
    const bool rc = tcp.value(QStringLiteral("reconnect"), true).toBool();
    bindSummary_->setText(
        QStringLiteral("%1:%2 · %3 · ACK %4 · 重连 %5")
            .arg(host.isEmpty() ? QStringLiteral("0.0.0.0") : host)
            .arg(port).arg(fr)
            .arg(ack.isEmpty() ? QStringLiteral("关") : ack.left(16))
            .arg(rc ? QStringLiteral("开") : QStringLiteral("关")));
  }
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

void CommPanel::setFlowVars(const QVariantMap& vars) {
  vars_ = vars;
  rebuildVarChips();
}

void CommPanel::insertFlowToken(const QString& key) {
  if (!payloadEdit_ || key.isEmpty()) return;
  const QString tok = QStringLiteral("${flow.%1}").arg(key);
  const int pos = payloadEdit_->cursorPosition();
  QString cur = payloadEdit_->text();
  cur.insert(pos, tok);
  payloadEdit_->setText(cur);
  payloadEdit_->setCursorPosition(pos + tok.size());
  payloadEdit_->setFocus(Qt::OtherFocusReason);
  if (status_)
    status_->setToolTip(QStringLiteral("已插入 %1").arg(tok));
}

void CommPanel::rebuildVarChips() {
  if (!varChipLay_) return;
  while (varChipLay_->count() > 0) {
    QLayoutItem* it = varChipLay_->takeAt(0);
    if (it->widget()) it->widget()->deleteLater();
    delete it;
  }
  varChipLay_->addWidget(new QLabel(QStringLiteral("插入")));
  // Prefer common VM keys first, then remaining flow vars (cap ~10).
  QStringList prefer{QStringLiteral("passGate"), QStringLiteral("barcodeText"),
                     QStringLiteral("barcodeCount"), QStringLiteral("formatted"),
                     QStringLiteral("lastRecv"), QStringLiteral("urlOk"),
                     QStringLiteral("locateScore")};
  QStringList keys;
  for (const QString& k : prefer) {
    if (vars_.contains(k)) keys << k;
  }
  for (auto it = vars_.begin(); it != vars_.end(); ++it) {
    if (keys.contains(it.key())) continue;
    if (it.key().startsWith(QStringLiteral("io."))) continue;
    keys << it.key();
    if (keys.size() >= 10) break;
  }
  if (keys.isEmpty()) {
    auto* empty = new QLabel(QStringLiteral("（无 flow 变量）"));
    empty->setObjectName(QStringLiteral("muted"));
    varChipLay_->addWidget(empty);
  } else {
    for (const QString& k : keys) {
      auto* b = new QPushButton(k);
      b->setFlat(true);
      b->setCursor(Qt::PointingHandCursor);
      b->setStyleSheet(
          QStringLiteral("QPushButton{background:#32353a;color:#c8cdd4;border-radius:3px;"
                         "padding:2px 8px;font-size:11px;}"
                         "QPushButton:hover{background:#3ecf8e;color:#102018;}"));
      b->setToolTip(QStringLiteral("插入 ${flow.%1} · 当前=%2")
                        .arg(k, vars_.value(k).toString().left(40)));
      connect(b, &QPushButton::clicked, this, [this, k]() { insertFlowToken(k); });
      varChipLay_->addWidget(b);
    }
  }
  varChipLay_->addStretch(1);
}

void CommPanel::copyTranscriptFiltered() {
  if (!transcript_) return;
  const QString text = transcript_->toPlainText();
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(text);
  if (status_)
    status_->setToolTip(QStringLiteral("已复制抄本 %1 行 · Ctrl+Shift+C")
                            .arg(text.isEmpty() ? 0 : text.split(QLatin1Char('\n')).size()));
}

bool CommPanel::eventFilter(QObject* obj, QEvent* event) {
  if (obj == bindSummary_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton && bindSummary_) {
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(bindSummary_->text());
        bindSummary_->setToolTip(QStringLiteral("已复制绑定摘要 · 单击"));
      }
      return true;
    }
    if (me->button() == Qt::RightButton) {
      pasteEndpointFromClipboard();
      return true;
    }
    if (me->button() == Qt::MiddleButton && reconnectCheck_) {
      reconnectCheck_->toggle();
      if (bindSummary_)
        bindSummary_->setToolTip(QStringLiteral("已切换重连 %1 · 中键")
                                     .arg(reconnectCheck_->isChecked() ? QStringLiteral("开")
                                                                       : QStringLiteral("关")));
      return true;
    }
  }
  if (obj == payloadEdit_ && event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->modifiers() & Qt::AltModifier) {
      if (ke->key() == Qt::Key_Up) {
        recallPayloadHistory(-1);
        return true;
      }
      if (ke->key() == Qt::Key_Down) {
        recallPayloadHistory(+1);
        return true;
      }
    }
  }
  return QWidget::eventFilter(obj, event);
}

void CommPanel::refreshTranscript() {
  if (!hub_ || !transcript_) return;
  transcriptAll_ = hub_->transcript();
  const QString f = txFilter_ ? txFilter_->text().trimmed() : QString();
  QStringList lines;
  if (f.isEmpty()) {
    lines = transcriptAll_;
  } else {
    for (const QString& line : transcriptAll_) {
      if (line.contains(f, Qt::CaseInsensitive)) lines << line;
    }
  }
  transcript_->setPlainText(lines.join(QLatin1Char('\n')));
  if (txFilter_) {
    txFilter_->setToolTip(
        QStringLiteral("通信抄本过滤 · 显示 %1/%2 · Ctrl+F")
            .arg(lines.size())
            .arg(transcriptAll_.size()));
  }
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
  pushPayloadHistory();
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



void CommPanel::toggleTcp() {
  if (!hub_) return;
  const QString st = hub_->tcpStatus();
  if (st.contains(QStringLiteral("listening")) ||
      st.contains(QStringLiteral("connected")) ||
      st.contains(QStringLiteral("connecting")) ||
      st.contains(QStringLiteral("peer"))) {
    onStopTcp();
    if (status_) status_->setToolTip(QStringLiteral("TCP 已停 · Ctrl+T"));
  } else {
    onStartTcp();
    if (status_) status_->setToolTip(QStringLiteral("TCP 启动 · Ctrl+T"));
  }
}

void CommPanel::applyFraming(const QString& framing) {
  if (!framingCombo_ || framing.isEmpty()) return;
  const int idx = framingCombo_->findData(framing);
  if (idx < 0) return;
  framingCombo_->setCurrentIndex(idx);
  if (status_)
    status_->setToolTip(QStringLiteral("帧分隔=%1 · 快选").arg(framing));
}

void CommPanel::applyPayloadPreset(const QString& kind) {
  if (!payloadEdit_) return;
  QString tpl;
  if (kind == QLatin1String("ok"))
    tpl = QStringLiteral("OK passGate=${flow.passGate} text=${flow.barcodeText}");
  else if (kind == QLatin1String("ng"))
    tpl = QStringLiteral("NG passGate=${flow.passGate} text=${flow.barcodeText}");
  else if (kind == QLatin1String("echo"))
    tpl = QStringLiteral("ECHO count=${flow.barcodeCount} formatted=${flow.formatted}");
  else
    tpl = QStringLiteral("${flow.barcodeText}");
  payloadEdit_->setText(tpl);
  payloadEdit_->setFocus(Qt::OtherFocusReason);
  if (status_)
    status_->setToolTip(QStringLiteral("报文预设 · %1").arg(kind));
}

void CommPanel::pasteEndpointFromClipboard() {
  const QClipboard* clip = QGuiApplication::clipboard();
  if (!clip) return;
  QString text = clip->text().trimmed();
  // Accept "host:port" or "绑定 · host:port · ..."
  if (text.contains(QLatin1Char(' '))) {
    const QStringList toks = text.split(QRegularExpression(QStringLiteral("[· ]+")), Qt::SkipEmptyParts);
    for (const QString& tok : toks) {
      if (tok.contains(QLatin1Char(':')) && tok.count(QLatin1Char('.')) >= 1) {
        text = tok;
        break;
      }
      if (tok.contains(QLatin1Char(':')) && !tok.contains(QLatin1Char(' '))) {
        text = tok;
        break;
      }
    }
  }
  const int colon = text.lastIndexOf(QLatin1Char(':'));
  if (colon <= 0) {
    if (status_) status_->setToolTip(QStringLiteral("剪贴板无 host:port · 右键摘要"));
    return;
  }
  const QString host = text.left(colon).trimmed();
  const QString port = text.mid(colon + 1).trimmed();
  bool ok = false;
  const int p = port.toInt(&ok);
  if (host.isEmpty() || !ok || p <= 0 || p > 65535) {
    if (status_) status_->setToolTip(QStringLiteral("端点解析失败 · 右键摘要"));
    return;
  }
  if (hostEdit_) hostEdit_->setText(host);
  if (portEdit_) portEdit_->setText(QString::number(p));
  pushTcpEndpoint(true);
  if (bindSummary_)
    bindSummary_->setToolTip(QStringLiteral("已粘贴端点 %1:%2 · 右键").arg(host).arg(p));
  if (status_)
    status_->setToolTip(QStringLiteral("端点 %1:%2 · 右键摘要").arg(host).arg(p));
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
  if (ackEdit_) tcp.insert(QStringLiteral("ack"), ackEdit_->text());
  if (reconnectCheck_)
    tcp.insert(QStringLiteral("reconnect"), reconnectCheck_->isChecked());
  if (bindSummary_) {
    const QString host = hostEdit_ ? hostEdit_->text().trimmed() : QString();
    const QString port = portEdit_ ? portEdit_->text().trimmed() : QString();
    const QString fr = framingCombo_ ? framingCombo_->currentData().toString() : QStringLiteral("lf");
    const QString ack = ackEdit_ ? ackEdit_->text() : QString();
    const bool rc = reconnectCheck_ && reconnectCheck_->isChecked();
    bindSummary_->setText(
        QStringLiteral("%1:%2 · %3 · ACK %4 · 重连 %5")
            .arg(host.isEmpty() ? QStringLiteral("0.0.0.0") : host, port.isEmpty() ? QStringLiteral("9000") : port,
                 fr, ack.isEmpty() ? QStringLiteral("关") : ack.left(16),
                 rc ? QStringLiteral("开") : QStringLiteral("关")));
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



void CommPanel::pushPayloadHistory() {
  if (!payloadEdit_) return;
  const QString t = payloadEdit_->text();
  if (t.trimmed().isEmpty()) return;
  if (!payloadHistory_.isEmpty() && payloadHistory_.first() == t) {
    payloadHistoryIdx_ = 0;
    return;
  }
  payloadHistory_.prepend(t);
  while (payloadHistory_.size() > 24) payloadHistory_.removeLast();
  payloadHistoryIdx_ = 0;
}

void CommPanel::recallPayloadHistory(int delta) {
  if (!payloadEdit_ || payloadHistory_.isEmpty()) return;
  if (payloadHistoryIdx_ < 0) payloadHistoryIdx_ = 0;
  payloadHistoryIdx_ = qBound(0, payloadHistoryIdx_ + delta, payloadHistory_.size() - 1);
  payloadEdit_->setText(payloadHistory_.at(payloadHistoryIdx_));
  if (status_)
    status_->setToolTip(QStringLiteral("报文历史 %1/%2 · Alt+↑↓")
                            .arg(payloadHistoryIdx_ + 1)
                            .arg(payloadHistory_.size()));
}

}  // namespace sieans_qt
