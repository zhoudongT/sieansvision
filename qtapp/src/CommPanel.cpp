#include "CommPanel.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QFormLayout>
#include <QHeaderView>
#include <QScrollBar>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QShortcut>
#include <QKeySequence>
#include <QInputDialog>
#include <QCheckBox>
#include <QMessageBox>
#include <QAbstractItemView>
#include <QClipboard>
#include <QGuiApplication>
#include <QColor>
#include <QEvent>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QKeyEvent>
#include <algorithm>
#include <QTextCursor>
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
  setStatusTip(QStringLiteral("通信面板 · LocalBus/TCP · peers/framing · Ctrl+T 启停 · Ctrl+[ / ] 切帧 · Ctrl+Shift+H 端点 · Ctrl+Shift+P 粘贴端点 · Ctrl+Shift+R/Ctrl+Alt+R RX/TX 末 RX · 状态双击启停/右键装RX · 端口滚轮 · ACK中键快选 · 报文 Alt+Del 删历史 · 抄本双击/右键装入 · 设备中键端点/右键复制 · Alt+↑↓ 历史 · ${flow.x}"));
  status_->setObjectName(QStringLiteral("muted"));
  lay->addWidget(status_);

  hostResultStrip_ = new QLabel(QStringLiteral("Host→Comm · —"));
  hostResultStrip_->setObjectName(QStringLiteral("muted"));
  hostResultStrip_->setWordWrap(true);
  hostResultStrip_->setToolTip(
      QStringLiteral("Host 判定结果与末次 TX · 来自 flow.hostResult / hostLastTx"));
  lay->addWidget(hostResultStrip_);

  deviceTable_ = new QTableWidget(0, 7);
  deviceTable_->setHorizontalHeaderLabels(
      {QStringLiteral("名称"), QStringLiteral("协议"), QStringLiteral("主机"),
       QStringLiteral("端口"), QStringLiteral("启用"), QStringLiteral("末次TX"),
       QStringLiteral("状态")});
  deviceTable_->horizontalHeader()->setStretchLastSection(true);
  deviceTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  deviceTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
  deviceTable_->setSelectionMode(QAbstractItemView::SingleSelection);
  deviceTable_->setMaximumHeight(140);
  deviceTable_->setToolTip(QStringLiteral("设备表 · F2 改名 · Insert/Ctrl+N 增 · Ctrl+D 复制 · Shift+Del 删 · Ctrl+X 剪切 · Ctrl+Shift+V 合并粘贴 · Alt+↑↓ 调序 · Ctrl+Home/End 置顶/底 · Ctrl+Shift+Y 反序 · Ctrl+Shift+S 按名排序 · Ctrl+Shift+U 按名去重 · Ctrl+A 全选 · Alt+Shift+E/D 全启/全停 · Enter 写回 · Space/Alt 启停 · Ctrl+Shift+J/O JSON · 中键端点 · 右键复制 · 双击备注"));
  deviceTable_->setStatusTip(QStringLiteral("通信 · 设备表 · LocalBus/TCP · 中键端点"));
  deviceTable_->installEventFilter(this);
  lay->addWidget(deviceTable_);
  connect(deviceTable_, &QTableWidget::itemSelectionChanged, this,
          &CommPanel::onDeviceRowChanged);
  connect(deviceTable_, &QTableWidget::itemDoubleClicked, this,
          [this](QTableWidgetItem*) { onRemarkEdit();
  connect(deviceTable_, &QTableWidget::itemChanged, this, [this](QTableWidgetItem* it) {
    if (!it || !hub_ || it->column() != 0) return;
    const int row = it->row();
    const QString newName = it->text().trimmed();
    if (newName.isEmpty()) return;
    // Prefer previous name stored in UserRole+1; fall back to current if first edit
    QString oldName = it->data(Qt::UserRole + 1).toString();
    if (oldName.isEmpty()) oldName = newName;
    it->setData(Qt::UserRole + 1, newName);
    QVariantMap cm = hub_->commManager();
    QVariantList devices = cm.value(QStringLiteral("devices")).toList();
    bool found = false;
    for (int i = 0; i < devices.size(); ++i) {
      QVariantMap d = devices[i].toMap();
      if (d.value(QStringLiteral("name")).toString() != oldName) continue;
      d.insert(QStringLiteral("name"), newName);
      devices[i] = d;
      found = true;
      break;
    }
    if (!found) return;
    cm.insert(QStringLiteral("devices"), devices);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
    if (status_)
      status_->setToolTip(QStringLiteral("设备更名 %1 → %2 · F2").arg(oldName, newName));
  }); });

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
      QStringLiteral("帧分隔 · 滚轮/Ctrl+[ ] · Alt+1..4 → LF/CRLF/Raw/Len4"));
  framingCombo_->setStatusTip(QStringLiteral("通信 · framing lf/crlf/raw/len4 · 滚轮切换"));
  framingCombo_->installEventFilter(this);
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
  {
    auto* ackRow = new QWidget;
    auto* ackLay = new QHBoxLayout(ackRow);
    ackLay->setContentsMargins(0, 0, 0, 0);
    ackLay->setSpacing(4);
    const QStringList presets{QStringLiteral("OK"), QStringLiteral("NG"), QStringLiteral("ACK"), QString()};
    for (const QString& val : presets) {
      auto* b = new QPushButton(val.isEmpty() ? QStringLiteral("清") : val);
      b->setObjectName(QStringLiteral("commAckChip"));
      b->setFixedHeight(22);
      b->setStyleSheet(QStringLiteral("font-size:11px;"));
      b->setToolTip(val.isEmpty() ? QStringLiteral("清空 ACK") : QStringLiteral("ACK=%1").arg(val));
      connect(b, &QPushButton::clicked, this, [this, val]() {
        if (!ackEdit_) return;
        ackEdit_->setText(val);
        pushTcpEndpoint(true);
      });
      ackLay->addWidget(b);
    }
    ackLay->addStretch(1);
    form->addRow(QStringLiteral("ACK快选"), ackRow);
  }
  connect(ackEdit_, &QLineEdit::editingFinished, this, [this]() { pushTcpEndpoint(true); });
  if (hostEdit_)
    connect(hostEdit_, &QLineEdit::editingFinished, this, [this]() { pushTcpEndpoint(true); });
  if (portEdit_)
    connect(portEdit_, &QLineEdit::editingFinished, this, [this]() { pushTcpEndpoint(true); });
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
      QStringLiteral("报文模板 · ${flow.x} / {name} / {{name}} · 下方芯片插入 · Enter/Ctrl+Enter 试发 · Alt+↑↓ 历史 · Alt+Del 删当前 · Alt+Shift+Del 清空 · Alt+Shift+D 收录当前 · Alt+Shift+C 复制历史 · Alt+Shift+T/P 帧报复制/粘贴 · Alt+Shift+Y 反序 · Alt+Shift+S 排序 · Alt+Shift+U 去重 · Alt+Shift+J/O JSON导出/导入 · LocalBus echo"));
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
      QStringLiteral("TX/RX 抄本 · LocalBus 软总线 + 真 TCP · peers 见状态行 · 过滤见上方 · 双击行装入报文"));
  transcript_->setToolTip(QStringLiteral("通信抄本 · Ctrl+Shift+C 复制过滤 · 双击行→报文框 · 中键清空过滤"));
  transcript_->installEventFilter(this);
  if (status_) {
    status_->setCursor(Qt::PointingHandCursor);
    status_->setToolTip(QStringLiteral("TCP 状态 · 单击/中键复制 TX/RX · 双击启停 · 右键装入末次RX · framing/peers 见行内"));
    status_->installEventFilter(this);
  }
  if (hostEdit_) hostEdit_->installEventFilter(this);
  if (portEdit_) {
    portEdit_->installEventFilter(this);
    portEdit_->setToolTip(QStringLiteral("TCP port · 滚轮 ±1 · listen/connect · AUTO_TCP 可 bump · 1-65535"));
  }
  if (ackEdit_) {
    ackEdit_->installEventFilter(this);
    ackEdit_->setToolTip(QStringLiteral("ACK · 中键快选 OK/NG/空 · 写入 tcpReal.ack · 空则不回"));
  }
  if (transcript_) {
    transcript_->setToolTip(QStringLiteral("通信抄本 · Ctrl+Shift+C 复制过滤 · 双击/右键行→报文框 · 中键清空过滤"));
  }
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
    auto* scFrL = new QShortcut(QKeySequence(QStringLiteral("Ctrl+[")), this);
    connect(scFrL, &QShortcut::activated, this, [this]() { cycleFraming(-1); });
    auto* scFrR = new QShortcut(QKeySequence(QStringLiteral("Ctrl+]")), this);
    connect(scFrR, &QShortcut::activated, this, [this]() { cycleFraming(+1); });
    auto* scHost = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+H")), this);
    connect(scHost, &QShortcut::activated, this, [this]() { copyEndpoint(); });
    auto* scPasteEp = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+P")), this);
    connect(scPasteEp, &QShortcut::activated, this, [this]() { pasteEndpointFromClipboard(); });
    auto* scRx = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+R")), this);
    connect(scRx, &QShortcut::activated, this, &CommPanel::loadLastRxToPayload);
    auto* scTx = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Alt+R")), this);
    connect(scTx, &QShortcut::activated, this, &CommPanel::loadLastTxToPayload);
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
    connect(hub_, &CommHub::deviceTxChanged, this, [this](const QString&) {
      refreshDeviceTxChrome();
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
  payloadHistory_.clear();
  payloadHistoryIdx_ = -1;
  for (const QVariant& v : commManager.value(QStringLiteral("payloadHistory")).toList()) {
    const QString t = v.toString();
    if (!t.trimmed().isEmpty()) payloadHistory_ << t;
  }
  while (payloadHistory_.size() > 24) payloadHistory_.removeLast();
  if (!payloadHistory_.isEmpty() && payloadEdit_ && payloadEdit_->text().trimmed().isEmpty()) {
    payloadEdit_->setText(payloadHistory_.first());
    payloadHistoryIdx_ = 0;
  }
  refreshDevices();
  refreshTranscript();
}

void CommPanel::refreshDevices() {
  deviceCombo_->clear();
  const bool blocked = deviceTable_ && deviceTable_->blockSignals(true);
  deviceTable_->setRowCount(0);
  if (!hub_) {
    if (deviceTable_) deviceTable_->blockSignals(blocked);
    return;
  }
  const QVariantList list = hub_->deviceList();
  for (const QVariant& v : list) {
    const QVariantMap d = v.toMap();
    const QString name = d.value(QStringLiteral("name")).toString();
    if (name.isEmpty()) continue;
    deviceCombo_->addItem(name);
    const int row = deviceTable_->rowCount();
    deviceTable_->insertRow(row);
    {
      auto* ni = new QTableWidgetItem(name);
      ni->setData(Qt::UserRole + 1, name);
      deviceTable_->setItem(row, 0, ni);
    }
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
    deviceTable_->setItem(row, 5, new QTableWidgetItem(QStringLiteral("—")));
    deviceTable_->setItem(row, 6, new QTableWidgetItem(QStringLiteral("—")));
    deviceTable_->item(row, 0)->setData(Qt::UserRole, d.value(QStringLiteral("remark")));
  }
  if (deviceCombo_->count() == 0) {
    deviceCombo_->addItem(QStringLiteral("LocalLoop"));
    deviceTable_->insertRow(0);
    deviceTable_->setItem(0, 0, new QTableWidgetItem(QStringLiteral("LocalLoop")));
    deviceTable_->setItem(0, 1, new QTableWidgetItem(QStringLiteral("Local Bus")));
    deviceTable_->setItem(0, 5, new QTableWidgetItem(QStringLiteral("—")));
    deviceTable_->setItem(0, 6, new QTableWidgetItem(QStringLiteral("—")));
  }
  if (deviceTable_) deviceTable_->blockSignals(blocked);
  refreshDeviceTxChrome();
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
  QString txBits = QStringLiteral("TX —");
  if (hub_) {
    const auto st = hub_->deviceTxStatus(name);
    if (!st.lastTx.isEmpty() || !st.status.isEmpty() || st.peerAckCount > 0) {
      txBits = QStringLiteral("%1 · ×%2")
                   .arg(st.status.isEmpty() ? QStringLiteral("TX") : st.status)
                   .arg(st.txCount);
      if (!st.lastAck.isEmpty())
        txBits += QStringLiteral(" · ACK %1").arg(st.lastAck.left(24));
      if (st.peerAckCount > 0)
        txBits += QStringLiteral(" · peerACK×%1").arg(st.peerAckCount);
      if (!st.lastPeer.isEmpty())
        txBits += QStringLiteral(" @%1").arg(st.lastPeer);
    }
  }
  detail_->setText(QStringLiteral("[%1] %2 · %3:%4 · %5 · %6")
                       .arg(proto, name, host, port,
                            remark.isEmpty() ? QStringLiteral("(无备注)") : remark,
                            txBits));
  if (!host.isEmpty()) hostEdit_->setText(host);
  if (!port.isEmpty() && port != QLatin1String("0")) portEdit_->setText(port);
}

void CommPanel::setFlowVars(const QVariantMap& vars) {
  vars_ = vars;
  rebuildVarChips();
  refreshHostResultStrip();
  refreshDeviceTxChrome();
}

void CommPanel::refreshHostResultStrip() {
  if (!hostResultStrip_) return;
  const QString result = vars_.value(QStringLiteral("hostResult")).toString();
  const QString mode = vars_.value(QStringLiteral("hostMode")).toString();
  const QString state = vars_.value(QStringLiteral("hostState")).toString();
  const QString lastTx = vars_.value(QStringLiteral("hostLastTx")).toString();
  const QString txDev = hub_ ? hub_->lastTxDevice() : QString();
  QString line = QStringLiteral("Host→Comm · %1")
                     .arg(result.isEmpty() ? QStringLiteral("—") : result);
  if (!mode.isEmpty() || !state.isEmpty())
    line += QStringLiteral(" · %1/%2")
                .arg(mode.isEmpty() ? QStringLiteral("—") : mode,
                     state.isEmpty() ? QStringLiteral("—") : state);
  if (!txDev.isEmpty())
    line += QStringLiteral(" · →%1").arg(txDev);
  if (!lastTx.isEmpty())
    line += QStringLiteral(" · %1").arg(lastTx.left(72));
  if (hub_) {
    const int peers = hub_->livePeerCount();
    const QString peerEp = hub_->lastPeerEndpoint();
    if (peers > 0)
      line += QStringLiteral(" · peers %1").arg(peers);
    if (!peerEp.isEmpty())
      line += QStringLiteral(" · peer %1").arg(peerEp);
    const QString tcpDev = hub_->primaryTcpDevice();
    const auto pst = hub_->deviceTxStatus(tcpDev);
    if (pst.peerAckCount > 0)
      line += QStringLiteral(" · peerACK×%1").arg(pst.peerAckCount);
  }
  hostResultStrip_->setText(line);
  hostResultStrip_->setToolTip(
      QStringLiteral("hostResult=%1 · hostMode=%2 · hostState=%3 · lastTxDevice=%4 · "
                     "hostLastTx=%5 · peers=%6 · lastPeer=%7")
          .arg(result, mode, state, txDev, lastTx.left(200))
          .arg(hub_ ? hub_->livePeerCount() : 0)
          .arg(hub_ ? hub_->lastPeerEndpoint() : QString()));
  if (result == QLatin1String("OK"))
    hostResultStrip_->setStyleSheet(QStringLiteral("color:#3ecf8e;font-weight:600;"));
  else if (result == QLatin1String("NG"))
    hostResultStrip_->setStyleSheet(QStringLiteral("color:#e53935;font-weight:600;"));
  else if (result == QLatin1String("ALARM"))
    hostResultStrip_->setStyleSheet(QStringLiteral("color:#e0b84a;font-weight:600;"));
  else
    hostResultStrip_->setStyleSheet(QString());
}

void CommPanel::refreshDeviceTxChrome() {
  if (!deviceTable_ || !hub_) return;
  const bool blocked = deviceTable_->blockSignals(true);
  for (int r = 0; r < deviceTable_->rowCount(); ++r) {
    auto* nameItem = deviceTable_->item(r, 0);
    if (!nameItem) continue;
    const auto st = hub_->deviceTxStatus(nameItem->text());
    const QString txSnippet =
        st.lastTx.isEmpty() ? QStringLiteral("—") : st.lastTx.left(28);
    QString status = st.status.isEmpty() ? QStringLiteral("—") : st.status;
    if (st.ackCount > 0 && !st.lastAck.isEmpty() &&
        !status.contains(QLatin1String("ACK")))
      status = QStringLiteral("%1·ACK").arg(status);
    auto* txItem = deviceTable_->item(r, 5);
    if (!txItem) {
      txItem = new QTableWidgetItem;
      deviceTable_->setItem(r, 5, txItem);
    }
    txItem->setText(txSnippet);
    txItem->setToolTip(st.lastTx.left(240));
    auto* stItem = deviceTable_->item(r, 6);
    if (!stItem) {
      stItem = new QTableWidgetItem;
      deviceTable_->setItem(r, 6, stItem);
    }
    QString cell =
        st.txCount > 0
            ? QStringLiteral("%1 ×%2").arg(status).arg(st.txCount)
            : status;
    if (st.peerAckCount > 0)
      cell += QStringLiteral(" ·p%1").arg(st.peerAckCount);
    stItem->setText(cell);
    QString tip = QStringLiteral("tx=%1 ack=%2 peerAck=%3 · ACK「%4」")
                      .arg(st.txCount)
                      .arg(st.ackCount)
                      .arg(st.peerAckCount)
                      .arg(st.lastAck.left(80));
    if (!st.lastPeer.isEmpty())
      tip += QStringLiteral(" · peer %1").arg(st.lastPeer);
    if (!st.lastPeerRx.isEmpty())
      tip += QStringLiteral(" · rx「%1」").arg(st.lastPeerRx.left(60));
    stItem->setToolTip(tip);
    QColor fg(0x9e, 0x9e, 0x9e);
    if (st.peerAckCount > 0 || status.contains(QLatin1String("peerACK")))
      fg = QColor(0x26, 0xa6, 0x9a);
    else if (status.contains(QLatin1String("ACK")) ||
             status.contains(QLatin1String("echo")))
      fg = QColor(0x3e, 0xcf, 0x8e);
    else if (status.contains(QLatin1String("soft")))
      fg = QColor(0xe0, 0xb8, 0x4a);
    else if (status.startsWith(QLatin1String("TX")))
      fg = QColor(0x64, 0xb5, 0xf6);
    stItem->setForeground(fg);
  }
  deviceTable_->blockSignals(blocked);
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
                     QStringLiteral("locateScore"), QStringLiteral("hostResult"),
                     QStringLiteral("hostMode"), QStringLiteral("hostState"),
                     QStringLiteral("hostOkStreak"), QStringLiteral("hostLastTx")};
  QStringList keys;
  for (const QString& k : prefer) {
    if (vars_.contains(k)) keys << k;
  }
  for (auto it = vars_.begin(); it != vars_.end(); ++it) {
    if (keys.contains(it.key())) continue;
    if (it.key().startsWith(QStringLiteral("io."))) continue;
    keys << it.key();
    if (keys.size() >= 14) break;
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
  if (obj == deviceTable_ && event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_Space) {
      toggleSelectedDeviceEnabled();
      return true;
    }
    if (ke->key() == Qt::Key_Return || ke->key() == Qt::Key_Enter) {
      writeBackSelectedDeviceEndpoint();
      if (status_) status_->setToolTip(QStringLiteral("已写回设备端点 · Enter"));
      return true;
    }
    if (ke->key() == Qt::Key_C && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      copySelectedDeviceEndpoint();
      return true;
    }
    if (ke->key() == Qt::Key_F2) {
      const auto items = deviceTable_->selectedItems();
      if (!items.isEmpty()) {
        auto* nameItem = deviceTable_->item(items.first()->row(), 0);
        if (nameItem) {
          deviceTable_->editItem(nameItem);
          if (status_) status_->setToolTip(QStringLiteral("编辑设备名 · F2 · Enter 结束写回"));
        }
      }
      return true;
    }
    if (ke->key() == Qt::Key_Insert ||
        (ke->key() == Qt::Key_N && (ke->modifiers() & Qt::ControlModifier))) {
      addDeviceRow();
      return true;
    }
    if (ke->key() == Qt::Key_D && (ke->modifiers() & Qt::ControlModifier)) {
      duplicateSelectedDevice();
      return true;
    }
    if (ke->key() == Qt::Key_Delete && (ke->modifiers() & Qt::ShiftModifier)) {
      removeSelectedDevice();
      return true;
    }
    if (ke->key() == Qt::Key_X && (ke->modifiers() & Qt::ControlModifier) &&
        !(ke->modifiers() & Qt::ShiftModifier) &&
        !(ke->modifiers() & Qt::AltModifier)) {
      cutSelectedDevice();
      return true;
    }
    if (ke->key() == Qt::Key_V && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      mergePasteDevicesFromClipboard();
      return true;
    }
    if (ke->key() == Qt::Key_J && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      exportDevicesJson();
      return true;
    }
    if (ke->key() == Qt::Key_O && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      importDevicesJson();
      return true;
    }
    if ((ke->key() == Qt::Key_Up || ke->key() == Qt::Key_Down) &&
        (ke->modifiers() & Qt::AltModifier)) {
      moveSelectedDevice(ke->key() == Qt::Key_Up ? -1 : +1);
      return true;
    }
    if ((ke->key() == Qt::Key_Home || ke->key() == Qt::Key_End) &&
        (ke->modifiers() & Qt::ControlModifier)) {
      moveSelectedDeviceToEdge(ke->key() == Qt::Key_Home ? -1 : +1);
      return true;
    }
    if (ke->key() == Qt::Key_Y && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      reverseDeviceOrder();
      return true;
    }
    if (ke->key() == Qt::Key_S && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      sortDevicesByName();
      return true;
    }
    if (ke->key() == Qt::Key_U && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      dedupeDevicesByName();
      return true;
    }
    if (ke->key() == Qt::Key_A && (ke->modifiers() & Qt::ControlModifier) &&
        !(ke->modifiers() & Qt::ShiftModifier)) {
      deviceTable_->selectAll();
      if (status_) status_->setToolTip(QStringLiteral("已全选设备 %1 · Ctrl+A").arg(deviceTable_->rowCount()));
      return true;
    }
    if ((ke->modifiers() & Qt::AltModifier) && (ke->modifiers() & Qt::ShiftModifier) &&
        !(ke->modifiers() & Qt::ControlModifier)) {
      if (ke->key() == Qt::Key_E) {
        setAllDevicesEnabled(true);
        return true;
      }
      if (ke->key() == Qt::Key_D) {
        setAllDevicesEnabled(false);
        return true;
      }
    }
  }
  if (obj == deviceTable_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (!deviceTable_) return true;
    const QPoint pos = me->position().toPoint();
    QTableWidgetItem* hit = deviceTable_->itemAt(pos);
    if (!hit) return false;
    const int row = hit->row();
    deviceTable_->selectRow(row);
    const QString host = deviceTable_->item(row, 2) ? deviceTable_->item(row, 2)->text().trimmed() : QString();
    const QString port = deviceTable_->item(row, 3) ? deviceTable_->item(row, 3)->text().trimmed() : QString();
    if (me->button() == Qt::MiddleButton) {
      if (hostEdit_ && !host.isEmpty()) hostEdit_->setText(host);
      if (portEdit_ && !port.isEmpty()) portEdit_->setText(port);
      pushTcpEndpoint(true);
      if (status_)
        status_->setToolTip(QStringLiteral("已装入设备端点 %1:%2 · 中键行").arg(
            host.isEmpty() ? QStringLiteral("—") : host,
            port.isEmpty() ? QStringLiteral("—") : port));
      return true;
    }
    if (me->button() == Qt::RightButton) {
      const QString ep = QStringLiteral("%1:%2")
                             .arg(host.isEmpty() ? QStringLiteral("127.0.0.1") : host,
                                  port.isEmpty() ? QStringLiteral("19956") : port);
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(ep);
      if (status_) status_->setToolTip(QStringLiteral("已复制设备端点 %1 · 右键行").arg(ep));
      return true;
    }
    if (me->button() == Qt::LeftButton && (me->modifiers() & Qt::AltModifier)) {
      deviceTable_->selectRow(row);
      toggleSelectedDeviceEnabled();
      return true;
    }
  }
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
      if (ke->key() == Qt::Key_Delete || ke->key() == Qt::Key_Backspace) {
        if (ke->modifiers() & Qt::ShiftModifier) clearPayloadHistory();
        else removeCurrentPayloadHistory();
        return true;
      }
      if (ke->key() == Qt::Key_Y && (ke->modifiers() & Qt::ShiftModifier)) {
        reversePayloadHistory();
        return true;
      }
      if (ke->key() == Qt::Key_U && (ke->modifiers() & Qt::ShiftModifier)) {
        dedupePayloadHistory();
        return true;
      }
      if (ke->key() == Qt::Key_S && (ke->modifiers() & Qt::ShiftModifier)) {
        sortPayloadHistory();
        return true;
      }
      if (ke->key() == Qt::Key_J && (ke->modifiers() & Qt::ShiftModifier)) {
        exportPayloadHistoryJson();
        return true;
      }
      if (ke->key() == Qt::Key_O && (ke->modifiers() & Qt::ShiftModifier)) {
        importPayloadHistoryJson();
        return true;
      }
      if (ke->key() == Qt::Key_D && (ke->modifiers() & Qt::ShiftModifier)) {
        pushPayloadHistory();
        if (status_)
          status_->setToolTip(QStringLiteral("已收录报文 · Alt+Shift+D · 历史 %1")
                                  .arg(payloadHistory_.size()));
        return true;
      }
      if (ke->key() == Qt::Key_C && (ke->modifiers() & Qt::ShiftModifier)) {
        copyPayloadHistoryText();
        return true;
      }
      if (ke->key() == Qt::Key_T && (ke->modifiers() & Qt::ShiftModifier)) {
        copyFramingPayload();
        return true;
      }
      if (ke->key() == Qt::Key_P && (ke->modifiers() & Qt::ShiftModifier)) {
        pasteFramingPayload();
        return true;
      }
    }
  }
  if (obj == framingCombo_ && event->type() == QEvent::Wheel) {
    auto* we = static_cast<QWheelEvent*>(event);
    cycleFraming(we->angleDelta().y() > 0 ? -1 : +1);
    return true;
  }
  if (obj == framingCombo_ && event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if ((ke->modifiers() & Qt::AltModifier) && ke->key() >= Qt::Key_1 && ke->key() <= Qt::Key_4 &&
        !(ke->modifiers() & Qt::ControlModifier) && framingCombo_) {
      const int idx = ke->key() - Qt::Key_1;
      if (idx < framingCombo_->count()) {
        framingCombo_->setCurrentIndex(idx);
        pushTcpEndpoint(true);
        if (status_)
          status_->setToolTip(QStringLiteral("帧分隔=%1 · Alt+%2")
                                  .arg(framingCombo_->currentText())
                                  .arg(idx + 1));
      }
      return true;
    }
  }
  if (obj == status_ && event->type() == QEvent::MouseButtonDblClick) {
    toggleTcp();
    return true;
  }
  if (obj == status_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::RightButton) {
      loadLastRxToPayload();
      return true;
    }
    if (me->button() == Qt::MiddleButton) {
      loadLastTxToPayload();
      return true;
    }
    if (me->button() == Qt::LeftButton) {
      copyLastTxRx();
      return true;
    }
  }
  if ((obj == hostEdit_ || obj == portEdit_) && event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_V && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      pasteEndpointFromClipboard();
      return true;
    }
  }
    if ((obj == hostEdit_ || obj == portEdit_) && event->type() == QEvent::Wheel) {
    auto* we = static_cast<QWheelEvent*>(event);
    if (!portEdit_) return true;
    bool ok = false;
    int p = portEdit_->text().trimmed().toInt(&ok);
    if (!ok) p = 19956;
    p += (we->angleDelta().y() > 0 ? 1 : -1);
    if (p < 1) p = 1;
    if (p > 65535) p = 65535;
    portEdit_->setText(QString::number(p));
    pushTcpEndpoint(true);
    if (status_) status_->setToolTip(QStringLiteral("端口 %1 · 滚轮").arg(p));
    return true;
  }
  if (obj == ackEdit_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton && ackEdit_) {
      const QString cur = ackEdit_->text().trimmed();
      QString next;
      if (cur.isEmpty()) next = QStringLiteral("OK");
      else if (cur == QLatin1String("OK")) next = QStringLiteral("NG");
      else next = QString();
      ackEdit_->setText(next);
      pushTcpEndpoint(true);
      if (status_)
        status_->setToolTip(QStringLiteral("ACK=%1 · 中键快选").arg(next.isEmpty() ? QStringLiteral("空") : next));
      return true;
    }
  }
  if (obj == transcript_ && event->type() == QEvent::MouseButtonDblClick) {
    if (!transcript_ || !payloadEdit_) return true;
    QTextCursor cur = transcript_->cursorForPosition(
        static_cast<QMouseEvent*>(event)->position().toPoint());
    cur.select(QTextCursor::LineUnderCursor);
    const QString line = cur.selectedText().trimmed();
    if (!line.isEmpty()) {
      payloadEdit_->setText(line);
      payloadEdit_->setFocus(Qt::OtherFocusReason);
      if (status_) status_->setToolTip(QStringLiteral("已装入抄本行 · 双击"));
    }
    return true;
  }
  if (obj == transcript_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::RightButton && transcript_ && payloadEdit_) {
      QTextCursor cur = transcript_->cursorForPosition(me->position().toPoint());
      cur.select(QTextCursor::LineUnderCursor);
      const QString line = cur.selectedText().trimmed();
      if (!line.isEmpty()) {
        payloadEdit_->setText(line);
        payloadEdit_->setFocus(Qt::OtherFocusReason);
        if (status_) status_->setToolTip(QStringLiteral("已装入抄本行 · 右键"));
      }
      return true;
    }
    if (me->button() == Qt::MiddleButton && txFilter_) {
      txFilter_->clear();
      if (status_) status_->setToolTip(QStringLiteral("已清空抄本过滤 · 中键"));
      return true;
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
  // Mirror endpoint into selected device row (same save).
  if (deviceTable_ && hostEdit_ && portEdit_) {
    const auto items = deviceTable_->selectedItems();
    if (!items.isEmpty()) {
      const int row = items.first()->row();
      if (auto* nameItem = deviceTable_->item(row, 0)) {
        const QString name = nameItem->text();
        const QString host = hostEdit_->text().trimmed();
        const QString port = portEdit_->text().trimmed();
        if (deviceTable_->item(row, 2)) deviceTable_->item(row, 2)->setText(host);
        if (deviceTable_->item(row, 3)) deviceTable_->item(row, 3)->setText(port);
        QVariantList devices = cm.value(QStringLiteral("devices")).toList();
        for (int i = 0; i < devices.size(); ++i) {
          QVariantMap d = devices[i].toMap();
          if (d.value(QStringLiteral("name")).toString() != name) continue;
          if (!host.isEmpty()) d.insert(QStringLiteral("host"), host);
          if (!port.isEmpty()) d.insert(QStringLiteral("port"), port.toInt());
          devices[i] = d;
          break;
        }
        cm.insert(QStringLiteral("devices"), devices);
      }
    }
  }
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
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    QVariantList hist;
    for (const QString& s : payloadHistory_) hist << s;
    cm.insert(QStringLiteral("payloadHistory"), hist);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
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



void CommPanel::removeCurrentPayloadHistory() {
  if (!payloadEdit_ || payloadHistory_.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史空 · Alt+Del"));
    return;
  }
  if (payloadHistoryIdx_ < 0 || payloadHistoryIdx_ >= payloadHistory_.size())
    payloadHistoryIdx_ = 0;
  payloadHistory_.removeAt(payloadHistoryIdx_);
  if (payloadHistory_.isEmpty()) {
    payloadHistoryIdx_ = -1;
    payloadEdit_->clear();
    if (hub_) {
      QVariantMap cm = hub_->commManager();
      cm.insert(QStringLiteral("payloadHistory"), QVariantList{});
      hub_->loadFromCommManager(cm);
      emit requestSaveComm(cm);
    }
    if (status_) status_->setToolTip(QStringLiteral("报文历史已清空 · Alt+Del"));
    return;
  }
  if (payloadHistoryIdx_ >= payloadHistory_.size())
    payloadHistoryIdx_ = payloadHistory_.size() - 1;
  payloadEdit_->setText(payloadHistory_.at(payloadHistoryIdx_));
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    QVariantList hist;
    for (const QString& s : payloadHistory_) hist << s;
    cm.insert(QStringLiteral("payloadHistory"), hist);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  if (status_)
    status_->setToolTip(QStringLiteral("已删报文历史 · 剩 %1 · Alt+Del · Alt+↑↓")
                            .arg(payloadHistory_.size()));
}

void CommPanel::clearPayloadHistory() {
  if (payloadHistory_.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史已空 · Alt+Shift+Del"));
    return;
  }
  payloadHistory_.clear();
  payloadHistoryIdx_ = -1;
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    cm.insert(QStringLiteral("payloadHistory"), QVariantList{});
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  if (status_) status_->setToolTip(QStringLiteral("报文历史已清空 · Alt+Shift+Del"));
}



void CommPanel::dedupePayloadHistory() {
  if (payloadHistory_.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史空 · Alt+Shift+U"));
    return;
  }
  QStringList uniq;
  int dropped = 0;
  for (const QString& s : payloadHistory_) {
    if (uniq.contains(s)) { ++dropped; continue; }
    uniq << s;
  }
  if (dropped <= 0) {
    if (status_) status_->setToolTip(QStringLiteral("无重复报文 · Alt+Shift+U"));
    return;
  }
  const QString cur = payloadEdit_ ? payloadEdit_->text() : QString();
  payloadHistory_ = uniq;
  payloadHistoryIdx_ = payloadHistory_.indexOf(cur);
  if (payloadHistoryIdx_ < 0 && !payloadHistory_.isEmpty()) {
    payloadHistoryIdx_ = 0;
    if (payloadEdit_) payloadEdit_->setText(payloadHistory_.first());
  }
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    QVariantList hist;
    for (const QString& s : payloadHistory_) hist << s;
    cm.insert(QStringLiteral("payloadHistory"), hist);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  if (status_)
    status_->setToolTip(QStringLiteral("报文去重 −%1 · 剩 %2 · Alt+Shift+U")
                            .arg(dropped)
                            .arg(payloadHistory_.size()));
}

void CommPanel::reversePayloadHistory() {
  if (payloadHistory_.size() < 2) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史不足 · Alt+Shift+Y"));
    return;
  }
  std::reverse(payloadHistory_.begin(), payloadHistory_.end());
  if (payloadHistoryIdx_ >= 0)
    payloadHistoryIdx_ = payloadHistory_.size() - 1 - payloadHistoryIdx_;
  if (payloadEdit_ && payloadHistoryIdx_ >= 0 && payloadHistoryIdx_ < payloadHistory_.size())
    payloadEdit_->setText(payloadHistory_.at(payloadHistoryIdx_));
  else if (payloadEdit_ && !payloadHistory_.isEmpty()) {
    payloadHistoryIdx_ = 0;
    payloadEdit_->setText(payloadHistory_.first());
  }
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    QVariantList hist;
    for (const QString& s : payloadHistory_) hist << s;
    cm.insert(QStringLiteral("payloadHistory"), hist);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  if (status_)
    status_->setToolTip(QStringLiteral("报文历史已反序 %1 · Alt+Shift+Y").arg(payloadHistory_.size()));
}



void CommPanel::sortPayloadHistory() {
  if (payloadHistory_.size() < 2) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史不足 · Alt+Shift+S"));
    return;
  }
  const QString cur = payloadEdit_ ? payloadEdit_->text() : QString();
  std::sort(payloadHistory_.begin(), payloadHistory_.end(),
            [](const QString& a, const QString& b) {
              return QString::localeAwareCompare(a, b) < 0;
            });
  payloadHistoryIdx_ = payloadHistory_.indexOf(cur);
  if (payloadHistoryIdx_ < 0 && !payloadHistory_.isEmpty()) {
    payloadHistoryIdx_ = 0;
    if (payloadEdit_) payloadEdit_->setText(payloadHistory_.first());
  }
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    QVariantList hist;
    for (const QString& s : payloadHistory_) hist << s;
    cm.insert(QStringLiteral("payloadHistory"), hist);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  if (status_)
    status_->setToolTip(QStringLiteral("报文历史已排序 %1 · Alt+Shift+S").arg(payloadHistory_.size()));
}

void CommPanel::exportPayloadHistoryJson() {
  if (payloadHistory_.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史空 · Alt+Shift+J"));
    return;
  }
  QJsonArray arr;
  for (const QString& s : payloadHistory_) arr.append(s);
  QJsonObject root;
  root.insert(QStringLiteral("payloadHistory"), arr);
  root.insert(QStringLiteral("count"), arr.size());
  const QByteArray bytes = QJsonDocument(root).toJson(QJsonDocument::Compact);
  if (auto* clip = QGuiApplication::clipboard())
    clip->setText(QString::fromUtf8(bytes));
  if (status_)
    status_->setToolTip(QStringLiteral("已导出报文历史JSON %1 · Alt+Shift+J").arg(arr.size()));
}

void CommPanel::importPayloadHistoryJson() {
  const QString clip = QGuiApplication::clipboard() ? QGuiApplication::clipboard()->text().trimmed()
                                                    : QString();
  if (clip.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("剪贴板空 · Alt+Shift+O"));
    return;
  }
  QJsonParseError err;
  const QJsonDocument doc = QJsonDocument::fromJson(clip.toUtf8(), &err);
  QStringList incoming;
  if (err.error == QJsonParseError::NoError) {
    if (doc.isObject()) {
      const QJsonArray arr = doc.object().value(QStringLiteral("payloadHistory")).toArray();
      for (const QJsonValue& v : arr) {
        const QString s = v.toString().trimmed();
        if (!s.isEmpty()) incoming << s;
      }
    } else if (doc.isArray()) {
      for (const QJsonValue& v : doc.array()) {
        const QString s = v.toString().trimmed();
        if (!s.isEmpty()) incoming << s;
      }
    }
  }
  if (incoming.isEmpty()) {
    // Fallback: one payload per non-empty line
    for (QString line : clip.split(QLatin1Char('\n'))) {
      line = line.trimmed();
      if (!line.isEmpty()) incoming << line;
    }
  }
  if (incoming.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("无报文可导入 · Alt+Shift+O"));
    return;
  }
  // Merge unique, newest first
  QStringList merged = incoming;
  for (const QString& s : payloadHistory_) {
    if (!merged.contains(s)) merged << s;
  }
  while (merged.size() > 24) merged.removeLast();
  payloadHistory_ = merged;
  payloadHistoryIdx_ = 0;
  if (payloadEdit_) payloadEdit_->setText(payloadHistory_.first());
  if (hub_) {
    QVariantMap cm = hub_->commManager();
    QVariantList hist;
    for (const QString& s : payloadHistory_) hist << s;
    cm.insert(QStringLiteral("payloadHistory"), hist);
    hub_->loadFromCommManager(cm);
    emit requestSaveComm(cm);
  }
  if (status_)
    status_->setToolTip(QStringLiteral("已导入报文历史 %1 · Alt+Shift+O").arg(incoming.size()));
}

void CommPanel::copyPayloadHistoryText() {
  if (payloadHistory_.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("报文历史空 · Alt+Shift+C"));
    return;
  }
  if (auto* clip = QGuiApplication::clipboard())
    clip->setText(payloadHistory_.join(QLatin1Char('\n')));
  if (status_)
    status_->setToolTip(QStringLiteral("已复制报文历史 %1 行 · Alt+Shift+C").arg(payloadHistory_.size()));
}

void CommPanel::copyFramingPayload() {
  const QString framing = framingCombo_ ? framingCombo_->currentText() : QString();
  const QString payload = payloadEdit_ ? payloadEdit_->text() : QString();
  const QString line = framing.isEmpty() ? payload
                                        : (framing + QLatin1Char('\t') + payload);
  if (line.trimmed().isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("帧/报文空 · Alt+Shift+T"));
    return;
  }
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
  if (status_)
    status_->setToolTip(QStringLiteral("已复制帧+报文 · Alt+Shift+T · %1")
                            .arg(framing.isEmpty() ? QStringLiteral("(无帧)") : framing));
}


void CommPanel::pasteFramingPayload() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text()
                          : QString();
  if (raw.trimmed().isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("剪贴板空 · Alt+Shift+P"));
    return;
  }
  // framing\tpayload or first line only payload
  const QString line = raw.split(QLatin1Char('\n')).value(0);
  const int tab = line.indexOf(QLatin1Char('\t'));
  if (tab >= 0) {
    const QString framing = line.left(tab).trimmed();
    const QString payload = line.mid(tab + 1);
    if (framingCombo_ && !framing.isEmpty()) {
      int idx = framingCombo_->findText(framing);
      if (idx < 0) {
        framingCombo_->addItem(framing);
        idx = framingCombo_->findText(framing);
      }
      if (idx >= 0) framingCombo_->setCurrentIndex(idx);
    }
    if (payloadEdit_) payloadEdit_->setText(payload);
  } else if (payloadEdit_) {
    payloadEdit_->setText(line);
  }
  if (status_) status_->setToolTip(QStringLiteral("已粘贴帧+报文 · Alt+Shift+P"));
}


void CommPanel::cycleFraming(int delta) {
  if (!framingCombo_ || framingCombo_->count() <= 0) return;
  const int n = framingCombo_->count();
  int idx = framingCombo_->currentIndex();
  if (idx < 0) idx = 0;
  idx = ((idx + delta) % n + n) % n;
  framingCombo_->setCurrentIndex(idx);
  pushTcpEndpoint(true);
  if (status_)
    status_->setToolTip(QStringLiteral("帧分隔=%1 · Ctrl+[ / ]")
                            .arg(framingCombo_->currentData().toString()));
}

void CommPanel::loadLastRxToPayload() {
  if (!hub_ || !payloadEdit_) return;
  const QString rx = hub_->lastRx();
  if (rx.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("无末 RX · Ctrl+Shift+R"));
    return;
  }
  payloadEdit_->setText(rx);
  payloadEdit_->setFocus(Qt::OtherFocusReason);
  if (status_) status_->setToolTip(QStringLiteral("已装入末 RX · Ctrl+Shift+R"));
}

void CommPanel::loadLastTxToPayload() {
  if (!hub_ || !payloadEdit_) return;
  const QString tx = hub_->lastTx();
  if (tx.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("无末 TX · Ctrl+Alt+R"));
    return;
  }
  payloadEdit_->setText(tx);
  payloadEdit_->setFocus(Qt::OtherFocusReason);
  if (status_) status_->setToolTip(QStringLiteral("已装入末 TX · Ctrl+Alt+R"));
}


void CommPanel::copyLastTxRx() {
  if (!hub_) return;
  const QString line = QStringLiteral("TX=%1\nRX=%2")
                           .arg(hub_->lastTx().isEmpty() ? QStringLiteral("—") : hub_->lastTx(),
                                hub_->lastRx().isEmpty() ? QStringLiteral("—") : hub_->lastRx());
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
  if (status_) status_->setToolTip(QStringLiteral("已复制 TX/RX · 状态单击/中键"));
}

void CommPanel::copyEndpoint() {
  const QString host = hostEdit_ ? hostEdit_->text().trimmed() : QString();
  const QString port = portEdit_ ? portEdit_->text().trimmed() : QString();
  const QString ep = QStringLiteral("%1:%2").arg(host.isEmpty() ? QStringLiteral("127.0.0.1") : host,
                                                 port.isEmpty() ? QStringLiteral("19956") : port);
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(ep);
  if (status_) status_->setToolTip(QStringLiteral("已复制端点 %1 · Ctrl+Shift+H").arg(ep));
  if (bindSummary_) bindSummary_->setToolTip(QStringLiteral("已复制端点 %1 · Ctrl+Shift+H").arg(ep));
}


void CommPanel::writeBackSelectedDeviceEndpoint() {
  if (!hub_ || !deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  const QString host = hostEdit_ ? hostEdit_->text().trimmed() : QString();
  const QString port = portEdit_ ? portEdit_->text().trimmed() : QString();
  if (deviceTable_->item(row, 2)) deviceTable_->item(row, 2)->setText(host);
  if (deviceTable_->item(row, 3)) deviceTable_->item(row, 3)->setText(port);
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  bool found = false;
  for (int i = 0; i < devices.size(); ++i) {
    QVariantMap d = devices[i].toMap();
    if (d.value(QStringLiteral("name")).toString() != name) continue;
    if (!host.isEmpty()) d.insert(QStringLiteral("host"), host);
    if (!port.isEmpty()) d.insert(QStringLiteral("port"), port.toInt());
    devices[i] = d;
    found = true;
    break;
  }
  if (!found) return;
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  if (detail_) {
    const QString remark = nameItem->data(Qt::UserRole).toString();
    const QString proto =
        deviceTable_->item(row, 1) ? deviceTable_->item(row, 1)->text() : QString();
    detail_->setText(QStringLiteral("[%1] %2 · %3:%4 · %5")
                         .arg(proto, name, host, port,
                              remark.isEmpty() ? QStringLiteral("(无备注)") : remark));
  }
}


void CommPanel::copySelectedDeviceEndpoint() {
  if (!deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("未选设备 · Ctrl+Shift+C"));
    return;
  }
  const int row = items.first()->row();
  QStringList parts;
  const int copyCols = qMin(5, deviceTable_->columnCount());
  for (int c = 0; c < copyCols; ++c) {
    auto* it = deviceTable_->item(row, c);
    parts << (it ? it->text().trimmed() : QString());
  }
  const QString line = parts.join(QLatin1Char('\t'));
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
  if (status_)
    status_->setToolTip(QStringLiteral("已复制设备行 · Ctrl+Shift+C · %1")
                            .arg(parts.value(0)));
}


void CommPanel::setAllDevicesEnabled(bool on) {
  if (!hub_ || !deviceTable_ || deviceTable_->rowCount() <= 0) {
    if (status_) status_->setToolTip(QStringLiteral("无设备 · Alt+Shift+E/D"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  int n = 0;
  for (int i = 0; i < devices.size(); ++i) {
    QVariantMap d = devices[i].toMap();
    if (d.value(QStringLiteral("enabled"), true).toBool() == on) continue;
    d.insert(QStringLiteral("enabled"), on);
    devices[i] = d;
    ++n;
  }
  for (int r = 0; r < deviceTable_->rowCount(); ++r) {
    if (auto* en = deviceTable_->item(r, 4))
      en->setText(on ? QStringLiteral("是") : QStringLiteral("否"));
  }
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  if (status_)
    status_->setToolTip(QStringLiteral("设备已全部%1 %2 · Alt+Shift+%3")
                            .arg(on ? QStringLiteral("启用") : QStringLiteral("禁用"))
                            .arg(deviceTable_->rowCount())
                            .arg(on ? QStringLiteral("E") : QStringLiteral("D")));
}

void CommPanel::toggleSelectedDeviceEnabled() {
  if (!hub_ || !deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  auto* enItem = deviceTable_->item(row, 4);
  if (!nameItem || !enItem) return;
  const QString name = nameItem->text();
  const bool on = enItem->text() != QLatin1String("是");
  enItem->setText(on ? QStringLiteral("是") : QStringLiteral("否"));
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  for (int i = 0; i < devices.size(); ++i) {
    QVariantMap d = devices[i].toMap();
    if (d.value(QStringLiteral("name")).toString() != name) continue;
    d.insert(QStringLiteral("enabled"), on);
    devices[i] = d;
    break;
  }
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  if (status_)
    status_->setToolTip(QStringLiteral("设备 %1 · %2 · Space/Alt+单击")
                            .arg(name, on ? QStringLiteral("启用") : QStringLiteral("禁用")));
}


void CommPanel::addDeviceRow() {
  if (!hub_ || !deviceTable_) return;
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  QString base = QStringLiteral("Device");
  int n = 1;
  QString name;
  for (;;) {
    name = QStringLiteral("%1%2").arg(base).arg(n);
    bool hit = false;
    for (const QVariant& v : devices) {
      if (v.toMap().value(QStringLiteral("name")).toString() == name) { hit = true; break; }
    }
    if (!hit) break;
    ++n;
  }
  const QString host = hostEdit_ ? hostEdit_->text().trimmed() : QStringLiteral("127.0.0.1");
  const int port = portEdit_ ? portEdit_->text().trimmed().toInt() : 19956;
  QVariantMap d;
  d.insert(QStringLiteral("name"), name);
  d.insert(QStringLiteral("protocol"), QStringLiteral("TCP"));
  d.insert(QStringLiteral("host"), host.isEmpty() ? QStringLiteral("127.0.0.1") : host);
  d.insert(QStringLiteral("port"), port > 0 ? port : 19956);
  d.insert(QStringLiteral("enabled"), true);
  d.insert(QStringLiteral("remark"), QString());
  devices.push_back(d);
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  // select new row
  for (int r = 0; r < deviceTable_->rowCount(); ++r) {
    auto* it = deviceTable_->item(r, 0);
    if (it && it->text() == name) { deviceTable_->selectRow(r); break; }
  }
  if (status_) status_->setToolTip(QStringLiteral("已添加设备 %1 · Insert/Ctrl+N").arg(name));
}

void CommPanel::duplicateSelectedDevice() {
  if (!hub_ || !deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString srcName = nameItem->text();
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  QVariantMap src;
  for (const QVariant& v : devices) {
    QVariantMap d = v.toMap();
    if (d.value(QStringLiteral("name")).toString() == srcName) { src = d; break; }
  }
  if (src.isEmpty()) return;
  QString base = srcName + QStringLiteral("_copy");
  QString name = base;
  int n = 2;
  for (;;) {
    bool hit = false;
    for (const QVariant& v : devices) {
      if (v.toMap().value(QStringLiteral("name")).toString() == name) { hit = true; break; }
    }
    if (!hit) break;
    name = QStringLiteral("%1%2").arg(base).arg(n++);
  }
  src.insert(QStringLiteral("name"), name);
  devices.push_back(src);
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  for (int r = 0; r < deviceTable_->rowCount(); ++r) {
    auto* it = deviceTable_->item(r, 0);
    if (it && it->text() == name) { deviceTable_->selectRow(r); break; }
  }
  if (status_) status_->setToolTip(QStringLiteral("已复制设备 %1 → %2 · Ctrl+D").arg(srcName, name));
}

void CommPanel::removeSelectedDevice() {
  if (!hub_ || !deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  if (name == QLatin1String("LocalLoop")) {
    if (status_) status_->setToolTip(QStringLiteral("LocalLoop 不可删 · Shift+Del"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  QVariantList next;
  for (const QVariant& v : devices) {
    if (v.toMap().value(QStringLiteral("name")).toString() != name) next << v;
  }
  if (next.size() == devices.size()) return;
  cm.insert(QStringLiteral("devices"), next);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_) status_->setToolTip(QStringLiteral("已删除设备 %1 · Shift+Del").arg(name));
}

void CommPanel::exportDevicesJson() {
  if (!hub_) return;
  const QVariantList devices = hub_->commManager().value(QStringLiteral("devices")).toList();
  QJsonArray arr;
  for (const QVariant& v : devices) arr.append(QJsonObject::fromVariantMap(v.toMap()));
  const QByteArray bytes = QJsonDocument(arr).toJson(QJsonDocument::Compact);
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(QString::fromUtf8(bytes));
  if (status_)
    status_->setToolTip(QStringLiteral("已导出设备 JSON %1 · Ctrl+Shift+J").arg(arr.size()));
}

void CommPanel::importDevicesJson() {
  if (!hub_) return;
  const QString clip = QGuiApplication::clipboard() ? QGuiApplication::clipboard()->text() : QString();
  if (clip.trimmed().isEmpty()) return;
  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(clip.toUtf8(), &pe);
  if (pe.error != QJsonParseError::NoError || !doc.isArray()) {
    if (status_) status_->setToolTip(QStringLiteral("设备 JSON 无效 · Ctrl+Shift+O"));
    return;
  }
  QVariantList devices;
  for (const QJsonValue& v : doc.array()) {
    if (!v.isObject()) continue;
    QVariantMap d = v.toObject().toVariantMap();
    if (d.value(QStringLiteral("name")).toString().trimmed().isEmpty()) continue;
    devices << d;
  }
  if (devices.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("设备 JSON 无有效项 · Ctrl+Shift+O"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_)
    status_->setToolTip(QStringLiteral("已导入设备 %1 · Ctrl+Shift+O").arg(devices.size()));
}



void CommPanel::cutSelectedDevice() {
  if (!hub_ || !deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("无选中设备 · Ctrl+X"));
    return;
  }
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  if (name == QLatin1String("LocalLoop")) {
    if (status_) status_->setToolTip(QStringLiteral("LocalLoop 不可剪切 · Ctrl+X"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  QVariantMap found;
  QVariantList next;
  for (const QVariant& v : devices) {
    const QVariantMap d = v.toMap();
    if (d.value(QStringLiteral("name")).toString() == name) {
      found = d;
      continue;
    }
    next << v;
  }
  if (found.isEmpty()) return;
  const QJsonArray arr{QJsonObject::fromVariantMap(found)};
  if (auto* clip = QGuiApplication::clipboard())
    clip->setText(QString::fromUtf8(QJsonDocument(arr).toJson(QJsonDocument::Compact)));
  cm.insert(QStringLiteral("devices"), next);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_)
    status_->setToolTip(QStringLiteral("已剪切设备 %1 · Ctrl+X · Ctrl+Shift+V 合并粘贴").arg(name));
}

void CommPanel::mergePasteDevicesFromClipboard() {
  if (!hub_) return;
  const QString clip = QGuiApplication::clipboard() ? QGuiApplication::clipboard()->text() : QString();
  if (clip.trimmed().isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("剪贴板空 · Ctrl+Shift+V"));
    return;
  }
  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(clip.toUtf8(), &pe);
  QVariantList incoming;
  if (pe.error == QJsonParseError::NoError) {
    if (doc.isArray()) {
      for (const QJsonValue& v : doc.array()) {
        if (!v.isObject()) continue;
        QVariantMap d = v.toObject().toVariantMap();
        if (!d.value(QStringLiteral("name")).toString().trimmed().isEmpty()) incoming << d;
      }
    } else if (doc.isObject()) {
      QVariantMap d = doc.object().toVariantMap();
      if (!d.value(QStringLiteral("name")).toString().trimmed().isEmpty()) incoming << d;
    }
  }
  if (incoming.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("无设备 JSON · Ctrl+Shift+V"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  QStringList existing;
  for (const QVariant& v : devices)
    existing << v.toMap().value(QStringLiteral("name")).toString();
  int added = 0;
  for (QVariant v : incoming) {
    QVariantMap d = v.toMap();
    QString name = d.value(QStringLiteral("name")).toString().trimmed();
    if (name.isEmpty()) continue;
    if (existing.contains(name)) {
      // uniquify
      int n = 2;
      QString cand = name + QStringLiteral("_") + QString::number(n);
      while (existing.contains(cand)) {
        ++n;
        cand = name + QStringLiteral("_") + QString::number(n);
      }
      d.insert(QStringLiteral("name"), cand);
      name = cand;
    }
    devices << d;
    existing << name;
    ++added;
  }
  if (added <= 0) return;
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_)
    status_->setToolTip(QStringLiteral("已合并粘贴设备 +%1 · Ctrl+Shift+V").arg(added));
}


void CommPanel::reverseDeviceOrder() {
  if (!hub_ || !deviceTable_ || deviceTable_->rowCount() < 2) {
    if (status_) status_->setToolTip(QStringLiteral("设备不足 · Ctrl+Shift+Y"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  if (devices.size() < 2) {
    if (status_) status_->setToolTip(QStringLiteral("设备不足 · Ctrl+Shift+Y"));
    return;
  }
  std::reverse(devices.begin(), devices.end());
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_)
    status_->setToolTip(QStringLiteral("设备已反序 %1 · Ctrl+Shift+Y").arg(devices.size()));
}


void CommPanel::sortDevicesByName() {
  if (!hub_ || !deviceTable_ || deviceTable_->rowCount() < 2) {
    if (status_) status_->setToolTip(QStringLiteral("设备不足 · Ctrl+Shift+S"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  if (devices.size() < 2) {
    if (status_) status_->setToolTip(QStringLiteral("设备不足 · Ctrl+Shift+S"));
    return;
  }
  std::stable_sort(devices.begin(), devices.end(),
                   [](const QVariant& a, const QVariant& b) {
                     return QString::localeAwareCompare(
                                a.toMap().value(QStringLiteral("name")).toString(),
                                b.toMap().value(QStringLiteral("name")).toString()) < 0;
                   });
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_)
    status_->setToolTip(QStringLiteral("设备已按名排序 %1 · Ctrl+Shift+S").arg(devices.size()));
}


void CommPanel::dedupeDevicesByName() {
  if (!hub_ || !deviceTable_) {
    if (status_) status_->setToolTip(QStringLiteral("无设备 · Ctrl+Shift+U"));
    return;
  }
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  if (devices.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("无设备 · Ctrl+Shift+U"));
    return;
  }
  QVariantList uniq;
  QStringList seen;
  int dropped = 0;
  for (const QVariant& v : devices) {
    const QVariantMap d = v.toMap();
    const QString name = d.value(QStringLiteral("name")).toString().trimmed();
    if (name.isEmpty()) { ++dropped; continue; }
    if (seen.contains(name)) { ++dropped; continue; }
    seen << name;
    uniq << d;
  }
  if (dropped <= 0) {
    if (status_) status_->setToolTip(QStringLiteral("无重复设备名 · Ctrl+Shift+U"));
    return;
  }
  cm.insert(QStringLiteral("devices"), uniq);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  if (status_)
    status_->setToolTip(QStringLiteral("设备去重 −%1 · 剩 %2 · Ctrl+Shift+U")
                            .arg(dropped)
                            .arg(uniq.size()));
}

void CommPanel::moveSelectedDeviceToEdge(int edge) {
  if (!hub_ || !deviceTable_) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) {
    if (status_) status_->setToolTip(QStringLiteral("未选中 · Ctrl+Home/End"));
    return;
  }
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  int idx = -1;
  for (int i = 0; i < devices.size(); ++i) {
    if (devices[i].toMap().value(QStringLiteral("name")).toString() == name) {
      idx = i;
      break;
    }
  }
  if (idx < 0 || devices.size() < 2) return;
  const int dest = edge < 0 ? 0 : devices.size() - 1;
  if (idx == dest) {
    if (status_)
      status_->setToolTip(edge < 0 ? QStringLiteral("已在顶 · Ctrl+Home")
                                   : QStringLiteral("已在底 · Ctrl+End"));
    return;
  }
  const QVariant item = devices.takeAt(idx);
  devices.insert(dest, item);
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  for (int r = 0; r < deviceTable_->rowCount(); ++r) {
    auto* it = deviceTable_->item(r, 0);
    if (it && it->text() == name) {
      deviceTable_->selectRow(r);
      break;
    }
  }
  if (status_)
    status_->setToolTip(QStringLiteral("设备%1 %2 · Ctrl+%3")
                            .arg(edge < 0 ? QStringLiteral("置顶") : QStringLiteral("置底"),
                                 name,
                                 edge < 0 ? QStringLiteral("Home") : QStringLiteral("End")));
}

void CommPanel::moveSelectedDevice(int delta) {
  if (!hub_ || !deviceTable_ || delta == 0) return;
  const auto items = deviceTable_->selectedItems();
  if (items.isEmpty()) return;
  const int row = items.first()->row();
  auto* nameItem = deviceTable_->item(row, 0);
  if (!nameItem) return;
  const QString name = nameItem->text();
  QVariantMap cm = hub_->commManager();
  QVariantList devices = cm.value(QStringLiteral("devices")).toList();
  int idx = -1;
  for (int i = 0; i < devices.size(); ++i) {
    if (devices[i].toMap().value(QStringLiteral("name")).toString() == name) {
      idx = i;
      break;
    }
  }
  if (idx < 0) return;
  const int dest = idx + delta;
  if (dest < 0 || dest >= devices.size()) {
    if (status_) status_->setToolTip(QStringLiteral("已到边界 · Alt+↑↓"));
    return;
  }
  devices.swapItemsAt(idx, dest);
  cm.insert(QStringLiteral("devices"), devices);
  hub_->loadFromCommManager(cm);
  emit requestSaveComm(cm);
  refreshDevices();
  for (int r = 0; r < deviceTable_->rowCount(); ++r) {
    auto* it = deviceTable_->item(r, 0);
    if (it && it->text() == name) {
      deviceTable_->selectRow(r);
      break;
    }
  }
  if (status_)
    status_->setToolTip(QStringLiteral("设备调序 %1 → #%2 · Alt+↑↓").arg(name).arg(dest + 1));
}

}  // namespace sieans_qt
