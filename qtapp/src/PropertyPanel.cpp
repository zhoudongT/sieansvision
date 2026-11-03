#include "PropertyPanel.hpp"

#include "Theme.hpp"

#include <QCheckBox>
#include <QComboBox>
#include <QDoubleSpinBox>
#include <QFormLayout>
#include <QHeaderView>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLineEdit>
#include <QMetaType>
#include <QSpinBox>
#include <QTableWidget>
#include <QShortcut>
#include <QClipboard>
#include <QGuiApplication>
#include <QKeySequence>
#include <QFrame>

namespace sieans_qt {
namespace {

QString stringify(const QVariant& v) {
  if (v.typeId() == QMetaType::QVariantMap || v.typeId() == QMetaType::QVariantList) {
    return QString::fromUtf8(
        QJsonDocument::fromVariant(v).toJson(QJsonDocument::Compact));
  }
  if (v.typeId() == QMetaType::Bool)
    return v.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  return v.toString();
}

}  // namespace

QVector<PropertyPanel::Spec> PropertyPanel::specsFor(const QString& op) {
  auto S = [](const char* key, const char* label, int kind, const char* choices) {
    Spec spec;
    spec.key = QString::fromUtf8(key);
    spec.label = QString::fromUtf8(label);
    spec.kind = kind;
    spec.choices = QString::fromUtf8(choices);
    return spec;
  };
  constexpr int kLine = 0, kInt = 1, kReal = 2, kBool = 3, kChoice = 4;
  if (op == QLatin1String("source:local")) {
    return {S("cam.imageSource", "图像源", kChoice, "local|本地图像;camera|相机;sdk|SDK"),
            S("cam.pixelFormat", "像素格式", kChoice, "MONO8|MONO8;RGB24|RGB24"),
            S("cam.autoSwitch", "自动切换", kBool, "")};
  }
  if (op == QLatin1String("source:sdk")) {
    return {S("cam.imageSource", "图像源", kChoice, "local|本地图像;camera|相机;sdk|SDK"),
            S("cam.sdkNote", "SDK 说明", kLine, "")};
  }
  if (op == QLatin1String("source") || op == QLatin1String("source:camera")) {
    return {S("cam.imageSource", "图像源", kChoice, "local|本地图像;camera|相机;sdk|SDK"),
            S("cam.backendKind", "采集后端", kChoice, "gentl|GenTL;uvc|UVC;soft|Soft 仿真"),
            S("cam.deviceId", "设备", kLine, ""),
            S("cam.continuousLive", "连续预览", kBool, ""),
            S("cam.exposureTime", "曝光 µs", kReal, ""),
            S("cam.gainDb", "增益 dB", kReal, ""),
            S("cam.acquisitionFrameRate", "帧率", kReal, ""),
            S("cam.trigger", "触发", kChoice, "freerun|自由运行;software|软触发;line0|Line0")};
  }
  if (op == QLatin1String("camera_capture")) {
    return {S("backendKind", "采集后端", kChoice, "gentl|GenTL;uvc|UVC;soft|Soft 仿真"),
            S("deviceId", "设备", kLine, ""),
            S("continuousLive", "连续预览", kBool, ""),
            S("exposureTime", "曝光 µs", kReal, ""),
            S("gainDb", "增益 dB", kReal, ""),
            S("trigger", "触发", kChoice, "freerun|自由运行;software|软触发;line0|Line0")};
  }
  if (op == QLatin1String("locate")) {
    return {S("minScore", "最小分数", kReal, ""),
            S("maxMatches", "最大个数", kInt, ""),
            S("templateW", "模板宽", kInt, ""),
            S("templateH", "模板高", kInt, ""),
            S("templatePath", "模板文件", kLine, "")};
  }
  if (op == QLatin1String("preprocess")) {
    return {S("mode", "方法", kChoice, "gray|灰度;mono|灰度;invert|反色;threshold|阈值"),
            S("threshold", "阈值", kInt, "")};
  }
  if (op == QLatin1String("barcode") || op == QLatin1String("qr_decode")) {
    return {S("types", "码制", kLine, ""),
            S("maxCodes", "最多码数", kInt, ""),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMinCount", "最少码数", kInt, ""),
            S("showOverlay", "显示码框", kBool, "")};
  }
  if (op == QLatin1String("var_calc")) {
    return {S("scope", "作用域", kChoice, "flow|流程;global|全局")};
  }
  if (op == QLatin1String("format_data")) {
    return {S("template", "模板 {name}/${flow.x}/{{name}}", kLine, ""),
            S("args", "参数变量 CSV", kLine, ""),
            S("targetVar", "目标变量", kLine, ""),
            S("emptyDefault", "空结果默认", kLine, "空输出时的占位报文（如 BARCODE empty）")};
  }
  if (op == QLatin1String("result_gate")) {
    return {S("minCount", "最少码数", kInt, ""),
            S("sourceVar", "源变量", kLine, ""),
            S("passVar", "输出变量", kLine, "")};
  }
  if (op == QLatin1String("send_data")) {
    return {S("device", "设备 LocalLoop/TCP", kLine, ""),
            S("message", "报文 ${flow.x}", kLine, "")};
  }
  if (op == QLatin1String("receive_data")) {
    return {S("device", "设备 LocalLoop/TCP", kLine, ""),
            S("targetVar", "目标变量", kLine, ""),
            S("timeoutMs", "超时 ms", kInt, "")};
  }
  if (op == QLatin1String("save_image")) {
    return {S("dir", "目录", kLine, "")};
  }
  return {};
}

PropertyPanel::PropertyPanel(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  title_ = new QLabel(QStringLiteral("属性"));
  title_->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title_);
  meta_ = new QLabel(QStringLiteral("选中流程节点以编辑参数"));
  meta_->setObjectName(QStringLiteral("muted"));
  meta_->setWordWrap(true);
  lay->addWidget(meta_);
  filterEdit_ = new QLineEdit;
  filterEdit_->setObjectName(QStringLiteral("propFilter"));
  filterEdit_->setPlaceholderText(QStringLiteral("过滤参数 · Ctrl+F · Esc 清空"));
  filterEdit_->setClearButtonEnabled(true);
  filterEdit_->setToolTip(QStringLiteral("属性过滤 · 匹配键/标签 · Ctrl+F 聚焦 · Esc 清空"));
  lay->addWidget(filterEdit_);
  connect(filterEdit_, &QLineEdit::textChanged, this, [this](const QString&) { applyFilter(); });
  {
    auto* scF = new QShortcut(QKeySequence(QStringLiteral("Ctrl+F")), this);
    connect(scF, &QShortcut::activated, this, &PropertyPanel::focusFilter);
    auto* scEsc = new QShortcut(QKeySequence(Qt::Key_Escape), filterEdit_);
    connect(scEsc, &QShortcut::activated, this, [this]() {
      if (filterEdit_ && !filterEdit_->text().isEmpty()) filterEdit_->clear();
    });
  }
  {
    auto* scCopy = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), this);
    connect(scCopy, &QShortcut::activated, this, &PropertyPanel::copyVisibleParams);
    auto* scPaste = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+V")), this);
    connect(scPaste, &QShortcut::activated, this, &PropertyPanel::pasteKeyValueParams);
  }
  setStatusTip(QStringLiteral("属性面板 · Ctrl+F 过滤 · Esc 清过滤 · Ctrl+Shift+C 复制可见 · Ctrl+Shift+V 粘贴键值 · emptyDefault/{name}"));

  auto* scroll = new QScrollArea;
  scroll->setWidgetResizable(true);
  scroll->setFrameShape(QFrame::NoFrame);
  formHost_ = new QWidget;
  form_ = new QFormLayout(formHost_);
  form_->setContentsMargins(0, 0, 0, 0);
  form_->setSpacing(4);
  form_->setLabelAlignment(Qt::AlignLeft);
  scroll->setWidget(formHost_);
  lay->addWidget(scroll, 1);
}

void PropertyPanel::clear() {
  params_.clear();
  currentId_.clear();
  title_->setText(QStringLiteral("属性"));
  meta_->setText(QStringLiteral("选中流程节点以编辑参数"));
  while (form_->rowCount() > 0) form_->removeRow(0);
}

void PropertyPanel::emitEdit(const QString& key, const QString& value) {
  if (building_) return;
  params_.insert(key, value);
  emit paramEdited(currentId_, key, value);
}

void PropertyPanel::addExprTable(const QVariantList& rows) {
  auto* table = new QTableWidget(rows.size(), 3);
  table->setProperty("propKey", QStringLiteral("expressions"));
  table->setObjectName(QStringLiteral("exprTable"));
  table->setHorizontalHeaderLabels(
      {QStringLiteral("启用"), QStringLiteral("变量"), QStringLiteral("表达式")});
  table->horizontalHeader()->setStretchLastSection(true);
  table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::ResizeToContents);
  table->verticalHeader()->setVisible(false);
  table->setMinimumHeight(140);
  for (int i = 0; i < rows.size(); ++i) {
    const QVariantMap row = rows[i].toMap();
    auto* en = new QTableWidgetItem;
    en->setFlags(Qt::ItemIsUserCheckable | Qt::ItemIsEnabled);
    const bool enabled =
        !row.contains(QStringLiteral("enabled")) || row.value(QStringLiteral("enabled")).toBool();
    en->setCheckState(enabled ? Qt::Checked : Qt::Unchecked);
    table->setItem(i, 0, en);
    auto* name = new QTableWidgetItem(row.value(QStringLiteral("name")).toString());
    table->setItem(i, 1, name);
    QString expr = row.value(QStringLiteral("expr")).toString();
    if (expr.isEmpty()) expr = row.value(QStringLiteral("expression")).toString();
    table->setItem(i, 2, new QTableWidgetItem(expr));
  }
  connect(table, &QTableWidget::itemChanged, this, [this, table](QTableWidgetItem*) {
    if (building_) return;
    QVariantList out;
    for (int r = 0; r < table->rowCount(); ++r) {
      QTableWidgetItem* en = table->item(r, 0);
      QTableWidgetItem* name = table->item(r, 1);
      QTableWidgetItem* expr = table->item(r, 2);
      if (!name || name->text().trimmed().isEmpty()) continue;
      QVariantMap row;
      row.insert(QStringLiteral("enabled"),
                 en && en->checkState() == Qt::Checked);
      row.insert(QStringLiteral("name"), name->text().trimmed());
      row.insert(QStringLiteral("expr"), expr ? expr->text() : QString());
      out.push_back(row);
    }
    emitEdit(QStringLiteral("expressions"),
             QString::fromUtf8(QJsonDocument::fromVariant(out).toJson(QJsonDocument::Compact)));
  });
  auto* exprLab = new QLabel(QStringLiteral("表达式"));
  exprLab->setProperty("propKey", QStringLiteral("expressions"));
  exprLab->setProperty("propLabel", QStringLiteral("表达式"));
  form_->addRow(exprLab, table);
}


void PropertyPanel::addSpecRow(const Spec& spec, const QVariantMap& params) {
  const QString key = spec.key;
  const QString label = spec.label;
  const QVariant value = params.value(key);
  auto* lab = new QLabel(label);
  lab->setProperty("propKey", key);
  lab->setProperty("propLabel", label);
  const auto tipFor = [](const QString& k) -> QString {
    if (k == QLatin1String("emptyDefault"))
      return QStringLiteral("模板展开为空时写入的默认值（如 BARCODE empty）");
    if (k == QLatin1String("template"))
      return QStringLiteral("支持 {name} / ${flow.x} / {{name}}");
    if (k == QLatin1String("message"))
      return QStringLiteral("发送报文 · 支持 ${flow.x}/{name}/{{name}}");
    if (k == QLatin1String("sourceVar"))
      return QStringLiteral("result_gate 读取的源变量");
    if (k == QLatin1String("passVar"))
      return QStringLiteral("判定通过时写入的变量名（默认 passGate）");
    if (k == QLatin1String("deviceId") || k == QLatin1String("cam.deviceId"))
      return QStringLiteral("soft:0 / GenTL ID / /dev/videoN");
    if (k == QLatin1String("binding"))
      return QStringLiteral("通信绑定 · flow.formatted / LocalBus 设备名");
    if (k == QLatin1String("expressions") || k == QLatin1String("expression"))
      return QStringLiteral("expr · in/startswith/…/isempty/notempty · 见底部提示");
    return {};
  };
  const QString tip = tipFor(key);
  if (!tip.isEmpty()) lab->setToolTip(tip);
  switch (spec.kind) {
    case 3: {
      auto* box = new QCheckBox(QStringLiteral("启用"));
      const QString s = stringify(value);
      box->setChecked(value.toBool() || s == QLatin1String("true") || s == QLatin1String("1"));
      connect(box, &QCheckBox::toggled, this, [this, key](bool on) {
        emitEdit(key, on ? QStringLiteral("true") : QStringLiteral("false"));
      });
      form_->addRow(lab, box);
      break;
    }
    case 1: {
      auto* spin = new QSpinBox;
      spin->setRange(-1000000, 10000000);
      spin->setValue(value.toInt());
      connect(spin, QOverload<int>::of(&QSpinBox::valueChanged), this,
              [this, key](int v) { emitEdit(key, QString::number(v)); });
      form_->addRow(lab, spin);
      break;
    }
    case 2: {
      auto* spin = new QDoubleSpinBox;
      const bool unit = key.contains(QStringLiteral("Score"), Qt::CaseInsensitive);
      const bool gain = key.contains(QStringLiteral("gain"), Qt::CaseInsensitive);
      const bool exposure = key.contains(QStringLiteral("exposure"), Qt::CaseInsensitive) ||
                            key.contains(QStringLiteral("Exposure"));
      if (unit) spin->setRange(0, 1);
      else if (gain) spin->setRange(0, 48);
      else if (exposure) spin->setRange(100, 10000000);
      else spin->setRange(0, 10000000);
      spin->setDecimals(gain || unit ? 2 : (exposure ? 0 : 2));
      spin->setSingleStep(unit ? 0.05 : (gain ? 0.5 : (exposure ? 100 : 1)));
      spin->setKeyboardTracking(false);
      spin->setValue(value.toDouble());
      connect(spin, QOverload<double>::of(&QDoubleSpinBox::valueChanged), this,
              [this, key](double v) { emitEdit(key, QString::number(v, 'g', 8)); });
      form_->addRow(lab, spin);
      break;
    }
    case 4: {
      auto* combo = new QComboBox;
      const QString cur = value.toString();
      int pick = 0;
      const QStringList opts = spec.choices.split(QLatin1Char(';'), Qt::SkipEmptyParts);
      for (int i = 0; i < opts.size(); ++i) {
        const QStringList pair = opts[i].split(QLatin1Char('|'));
        const QString val = pair.value(0);
        combo->addItem(pair.value(1, val), val);
        if (val == cur) pick = i;
      }
      combo->setCurrentIndex(pick);
      connect(combo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
              [this, key, combo](int) { emitEdit(key, combo->currentData().toString()); });
      form_->addRow(lab, combo);
      break;
    }
    case 0:
    default: {
      auto* edit = new QLineEdit(stringify(value));
      if (!tip.isEmpty()) edit->setToolTip(tip);
      connect(edit, &QLineEdit::editingFinished, this, [this, key, edit]() {
        emitEdit(key, edit->text());
      });
      form_->addRow(lab, edit);
      break;
    }
  }
}

void PropertyPanel::rebuildForm(const QString& title, const QString& nodeId,
                                const QString& op, const QVariantMap& params) {
  params_ = params;
  building_ = true;
  currentId_ = nodeId;
  title_->setText(title);
  while (form_->rowCount() > 0) form_->removeRow(0);

  if (op == QLatin1String("var_calc"))
    addExprTable(params.value(QStringLiteral("expressions")).toList());

  QStringList used;
  used << QStringLiteral("expressions");
  for (const Spec& spec : specsFor(op)) {
    addSpecRow(spec, params);
    used << spec.key;
  }
  if (!op.startsWith(QLatin1String("source"))) {
    for (auto it = params.begin(); it != params.end(); ++it) {
      if (used.contains(it.key())) continue;
      Spec extra;
      extra.key = it.key();
      extra.label = it.key();
      extra.kind = 0;
      addSpecRow(extra, params);
    }
  }
  building_ = false;
  applyFilter();
}

void PropertyPanel::showSource(const QVariantMap& sourceConfig) {
  meta_->setText(QStringLiteral("图像源 · 本地图像 / 相机 / SDK，曝光增益热更新"));
  QVariantMap flat = sourceConfig;
  const QVariantMap cam = sourceConfig.value(QStringLiteral("cameraParams")).toMap();
  for (auto it = cam.begin(); it != cam.end(); ++it)
    flat.insert(QStringLiteral("cam.%1").arg(it.key()), it.value());
  QString kind = flat.value(QStringLiteral("cam.imageSource")).toString();
  if (kind.isEmpty()) {
    const QString mode = flat.value(QStringLiteral("mode")).toString();
    kind = (mode == QLatin1String("camera") || mode == QLatin1String("sdk")) ? mode
                                                                              : QStringLiteral("local");
    flat.insert(QStringLiteral("cam.imageSource"), kind);
  }
  if (!flat.contains(QStringLiteral("cam.pixelFormat")))
    flat.insert(QStringLiteral("cam.pixelFormat"), QStringLiteral("RGB24"));
  rebuildForm(QStringLiteral("属性 · 图像源"), QStringLiteral("source"),
              QStringLiteral("source:%1").arg(kind), flat);
}

void PropertyPanel::showStep(const FlowStep& step) {
  QString hint = QStringLiteral("算子 %1 · %2").arg(step.operation, step.runState);
  if (step.operation == QLatin1String("format_data"))
    hint += QStringLiteral(" · 支持 {name} / ${flow.x} / {{name}} · emptyDefault 空结果 · expr 见白名单");
  else if (step.operation == QLatin1String("send_data") ||
           step.operation == QLatin1String("receive_data"))
    hint += QStringLiteral(" · LocalLoop 回环 / TCP");
  else if (step.operation == QLatin1String("result_gate"))
    hint += QStringLiteral(" · sourceVar → passVar");
  else if (step.operation == QLatin1String("var_calc"))
    hint += QStringLiteral(
        " · expr: in / startswith|endswith|contains / lower|upper / trim|strip|replace / slice|substr|mid|isdigit|isalpha|lpad|rpad|repeat|default|coalesce|nvl|ifempty|indexof|find|left|right|isempty|notempty|zfill|count|clamp|round|floor|ceil|sign|pow|sqrt|trunc|title|capitalize|hypot|log|exp|isalnum|swapcase|radians|degrees|ord|chr|bin|hex|islower|isupper|nvl|lstrip|rstrip|iff|bool|oct|fabs|fmod|cbrt|log10|frac|log2|isfinite|atan2|copysign|bitand|bitor|bitxor|gcd|lcm|clamp01|lerp|invlerp|smoothstep|step|saturate|fract|isnan|isinf|mix|exp2|fma|sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|log1p|expm1|fdim|nearbyint|bitshl|bitshr|remainder|scalbn|nextafter|tgamma|lgamma|erf|erfc|asinh|acosh|atanh|rint|logb|ilogb|signbit|isnormal|fmax|fmin|bitnot|between|approxeq|inrange|nan|inf|reverse|join|cmp|eq|ne|gt|lt|ge|le|choose|nth|ifelse|nullif|iif|not_|and_|or_|xor_|truthy|falsy|ifnull|nonempty|strlen|tostring|toint|todouble|tonumber");
  else if (step.operation == QLatin1String("barcode") ||
           step.operation == QLatin1String("qr_decode"))
    hint += QStringLiteral(" · ZXing 多码 · 判定 judgeMinCount");
  meta_->setText(hint);
  rebuildForm(QStringLiteral("属性 · %1").arg(step.name), step.id, step.operation,
              step.params);
}


void PropertyPanel::applySnapshot(const QVariantMap& snap) {
  if (!form_) return;
  building_ = true;
  params_ = snap;
  for (int r = 0; r < form_->rowCount(); ++r) {
    QLayoutItem* labItem = form_->itemAt(r, QFormLayout::LabelRole);
    QLayoutItem* fieldItem = form_->itemAt(r, QFormLayout::FieldRole);
    if (!labItem || !fieldItem) continue;
    QWidget* labW = labItem->widget();
    QWidget* field = fieldItem->widget();
    if (!labW || !field) continue;
    const QString key = labW->property("propKey").toString();
    if (key.isEmpty() || !snap.contains(key)) continue;
    const QVariant v = snap.value(key);
    if (auto* le = qobject_cast<QLineEdit*>(field)) {
      le->setText(stringify(v));
    } else if (auto* sp = qobject_cast<QSpinBox*>(field)) {
      sp->setValue(v.toInt());
    } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(field)) {
      dsp->setValue(v.toDouble());
    } else if (auto* box = qobject_cast<QCheckBox*>(field)) {
      const QString s = stringify(v);
      box->setChecked(v.toBool() || s == QLatin1String("true") || s == QLatin1String("1"));
    } else if (auto* combo = qobject_cast<QComboBox*>(field)) {
      const int idx = combo->findData(v.toString());
      if (idx >= 0) combo->setCurrentIndex(idx);
    }
  }
  building_ = false;
  for (auto it = snap.begin(); it != snap.end(); ++it)
    emitEdit(it.key(), stringify(it.value()));
}

void PropertyPanel::focusFilter() {
  if (!filterEdit_) return;
  filterEdit_->setFocus(Qt::ShortcutFocusReason);
  filterEdit_->selectAll();
}

void PropertyPanel::applyFilter() {
  if (!form_ || !filterEdit_) return;
  const QString f = filterEdit_->text().trimmed();
  for (int r = 0; r < form_->rowCount(); ++r) {
    QString hay;
    if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) {
      if (auto* w = li->widget()) {
        hay += w->property("propKey").toString() + QLatin1Char(' ');
        hay += w->property("propLabel").toString() + QLatin1Char(' ');
        if (auto* lab = qobject_cast<QLabel*>(w)) hay += lab->text() + QLatin1Char(' ');
        else hay += w->objectName() + QLatin1Char(' ');
      }
    }
    if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) {
      if (auto* w = fi->widget()) {
        hay += w->property("propKey").toString() + QLatin1Char(' ');
        if (qobject_cast<QTableWidget*>(w)) hay += QStringLiteral("expressions expr 表达式 ");
      }
    }
    // spanning full-row widgets (expr table)
    if (auto* si = form_->itemAt(r, QFormLayout::SpanningRole)) {
      if (auto* w = si->widget()) {
        hay += w->property("propKey").toString() + QStringLiteral(" expressions expr 表达式 ");
      }
    }
    const bool show = f.isEmpty() || hay.contains(f, Qt::CaseInsensitive);
    form_->setRowVisible(r, show);
  }
  if (meta_ && !f.isEmpty()) {
    int vis = 0;
    for (int r = 0; r < form_->rowCount(); ++r) {
      // setRowVisible doesn't expose getter easily — count via label visibility
      if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) {
        if (li->widget() && li->widget()->isVisibleTo(formHost_)) ++vis;
      } else if (auto* si = form_->itemAt(r, QFormLayout::SpanningRole)) {
        if (si->widget() && si->widget()->isVisibleTo(formHost_)) ++vis;
      }
    }
    Q_UNUSED(vis);
  }
  filterEdit_->setToolTip(
      QStringLiteral("属性过滤 · %1 · Ctrl+F 聚焦 · Esc 清空")
          .arg(f.isEmpty() ? QStringLiteral("全部") : QStringLiteral("「%1」").arg(f)));
}


void PropertyPanel::copyVisibleParams() {
  if (!form_) return;
  QStringList lines;
  for (int r = 0; r < form_->rowCount(); ++r) {
    QWidget* labW = nullptr;
    QWidget* fieldW = nullptr;
    if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) labW = li->widget();
    if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) fieldW = fi->widget();
    if (labW && !labW->isVisibleTo(formHost_)) continue;
    QString key = labW ? labW->property("propKey").toString() : QString();
    if (key.isEmpty() && fieldW) key = fieldW->property("propKey").toString();
    if (key.isEmpty()) continue;
    QString val;
    if (auto* le = qobject_cast<QLineEdit*>(fieldW)) {
      val = le->text();
    } else if (auto* sp = qobject_cast<QSpinBox*>(fieldW)) {
      val = QString::number(sp->value());
    } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(fieldW)) {
      val = QString::number(dsp->value());
    } else if (auto* box = qobject_cast<QCheckBox*>(fieldW)) {
      val = box->isChecked() ? QStringLiteral("true") : QStringLiteral("false");
    } else if (auto* combo = qobject_cast<QComboBox*>(fieldW)) {
      val = combo->currentData().toString();
      if (val.isEmpty()) val = combo->currentText();
    } else if (fieldW) {
      val = fieldW->property("text").toString();
    }
    lines << QStringLiteral("%1=%2").arg(key, val);
  }
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
  if (filterEdit_)
    filterEdit_->setToolTip(QStringLiteral("已复制可见参数 %1 · Ctrl+Shift+C").arg(lines.size()));
}


void PropertyPanel::pasteKeyValueParams() {
  const QString clip = QGuiApplication::clipboard() ? QGuiApplication::clipboard()->text() : QString();
  if (clip.trimmed().isEmpty() || !form_) return;
  int n = 0;
  for (const QString& line : clip.split(QLatin1Char('\n'))) {
    const int eq = line.indexOf(QLatin1Char('='));
    if (eq <= 0) continue;
    const QString key = line.left(eq).trimmed();
    const QString val = line.mid(eq + 1).trimmed();
    if (key.isEmpty()) continue;
    for (int r = 0; r < form_->rowCount(); ++r) {
      QWidget* fieldW = nullptr;
      if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) fieldW = fi->widget();
      if (!fieldW) continue;
      if (fieldW->property("propKey").toString() != key) continue;
      if (auto* le = qobject_cast<QLineEdit*>(fieldW)) {
        le->setText(val);
        ++n;
      } else if (auto* sp = qobject_cast<QSpinBox*>(fieldW)) {
        bool ok = false;
        const int iv = val.toInt(&ok);
        if (ok) { sp->setValue(iv); ++n; }
      } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(fieldW)) {
        bool ok = false;
        const double dv = val.toDouble(&ok);
        if (ok) { dsp->setValue(dv); ++n; }
      } else if (auto* box = qobject_cast<QCheckBox*>(fieldW)) {
        box->setChecked(val == QLatin1String("true") || val == QLatin1String("1"));
        ++n;
      } else if (auto* combo = qobject_cast<QComboBox*>(fieldW)) {
        int cidx = combo->findData(val);
        if (cidx < 0) cidx = combo->findText(val);
        if (cidx >= 0) { combo->setCurrentIndex(cidx); ++n; }
      }
      break;
    }
  }
  if (filterEdit_)
    filterEdit_->setToolTip(QStringLiteral("已粘贴参数 %1 · Ctrl+Shift+V").arg(n));
}

}  // namespace sieans_qt
