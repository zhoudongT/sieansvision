#include "LocateMatchPanel.hpp"
#include "TemplateMatch.hpp"
#include "WorkbenchPaths.hpp"

#include <QCheckBox>
#include <QComboBox>
#include <QCoreApplication>
#include <QDir>
#include <QDoubleSpinBox>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QTabWidget>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QAbstractItemView>
#include <QColor>
#include <QVBoxLayout>

namespace sieans_qt {
namespace {

QWidget* wrapForm(QFormLayout* form) {
  auto* w = new QWidget;
  auto* lay = new QVBoxLayout(w);
  lay->setContentsMargins(10, 8, 10, 8);
  lay->addLayout(form);
  lay->addStretch(1);
  return w;
}

}  // namespace

QVariantMap LocateMatchPanel::normalizeParams(const QVariantMap& in) {
  QVariantMap p = in;
  auto setd = [&](const QString& k, const QVariant& v) {
    if (!p.contains(k) || p.value(k).toString().trimmed().isEmpty()) p.insert(k, v);
  };
  setd(QStringLiteral("matchMode"), QStringLiteral("fast"));
  setd(QStringLiteral("templateSource"), QStringLiteral("file"));
  setd(QStringLiteral("templatePath"), QString());
  setd(QStringLiteral("templateW"), 64);
  setd(QStringLiteral("templateH"), 64);
  setd(QStringLiteral("minScore"), 0.55);
  setd(QStringLiteral("maxMatches"), 1);
  setd(QStringLiteral("overlapThreshold"), 0.3);
  if (!p.contains(QStringLiteral("angleEnable"))) p.insert(QStringLiteral("angleEnable"), true);
  setd(QStringLiteral("angleStart"), 0);
  setd(QStringLiteral("angleEnd"), 0);
  setd(QStringLiteral("angleStep"), 10);
  if (!p.contains(QStringLiteral("showOverlay"))) p.insert(QStringLiteral("showOverlay"), true);
  if (!p.contains(QStringLiteral("showOrigin"))) p.insert(QStringLiteral("showOrigin"), false);
  if (!p.contains(QStringLiteral("showAngleDeg"))) p.insert(QStringLiteral("showAngleDeg"), true);
  if (!p.contains(QStringLiteral("resultJudgeEnable")))
    p.insert(QStringLiteral("resultJudgeEnable"), false);
  return p;
}

LocateMatchPanel::LocateMatchPanel(QWidget* parent) : QWidget(parent) {
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(0, 0, 0, 0);
  auto* hint = new QLabel(
      QStringLiteral("对齐 VisionMaster「快速匹配」：基本参数 / 模板 / 运行参数 / 结果显示"));
  hint->setWordWrap(true);
  hint->setStyleSheet(QStringLiteral("color:#8a9098;font-size:11px;padding:6px 10px 0 10px;"));
  root->addWidget(hint);

  tabs_ = new QTabWidget;
  root->addWidget(tabs_, 1);

  // 1) 基本参数
  auto* basic = new QFormLayout;
  matchMode_ = new QComboBox;
  matchMode_->addItem(QStringLiteral("快速匹配"), QStringLiteral("fast"));
  matchMode_->addItem(QStringLiteral("灰度模板匹配"), QStringLiteral("gray"));
  matchMode_->setToolTip(QStringLiteral("Qt 工作台两种模式共用灰度 SAD 引擎，参数与 PySide 对齐。"));
  templateSource_ = new QComboBox;
  templateSource_->addItem(QStringLiteral("文件路径"), QStringLiteral("file"));
  templateSource_->addItem(QStringLiteral("软场景标牌"), QStringLiteral("soft_plate"));
  templateSource_->addItem(QStringLiteral("从当前图截取"), QStringLiteral("capture"));
  minScore_ = new QDoubleSpinBox;
  minScore_->setRange(0.0, 1.0);
  minScore_->setSingleStep(0.05);
  minScore_->setDecimals(2);
  maxMatches_ = new QSpinBox;
  maxMatches_->setRange(1, 50);
  overlap_ = new QDoubleSpinBox;
  overlap_->setRange(0.0, 1.0);
  overlap_->setSingleStep(0.05);
  overlap_->setDecimals(2);
  basic->addRow(QStringLiteral("匹配模式"), matchMode_);
  basic->addRow(QStringLiteral("模板来源"), templateSource_);
  basic->addRow(QStringLiteral("最低分数"), minScore_);
  basic->addRow(QStringLiteral("最多目标"), maxMatches_);
  basic->addRow(QStringLiteral("去重重叠"), overlap_);
  tabs_->addTab(wrapForm(basic), QStringLiteral("基本参数"));

  // 2) 模板
  auto* tplPage = new QWidget;
  auto* tplLay = new QVBoxLayout(tplPage);
  tplLay->setContentsMargins(10, 8, 10, 8);
  auto* tplForm = new QFormLayout;
  pathEdit_ = new QLineEdit;
  pathEdit_->setPlaceholderText(QStringLiteral("当前选用模板路径 / 方案内引用"));
  tplForm->addRow(QStringLiteral("当前模板"), pathEdit_);
  auto* row = new QWidget;
  auto* hl = new QHBoxLayout(row);
  hl->setContentsMargins(0, 0, 0, 0);
  auto* loadBtn = new QPushButton(QStringLiteral("载入模板…"));
  auto* createBtn = new QPushButton(QStringLiteral("创建模板…"));
  auto* clearBtn = new QPushButton(QStringLiteral("清除模板"));
  hl->addWidget(loadBtn);
  hl->addWidget(createBtn);
  hl->addWidget(clearBtn);
  hl->addStretch(1);
  tplLay->addLayout(tplForm);
  tplLay->addWidget(row);
  tplStatus_ = new QLabel;
  tplLay->addWidget(tplStatus_);
  auto* tplTip = new QLabel(QStringLiteral(
      "创建模板从当前画面高对比区域截取并保存到本检出 artifacts/qt-templates，不下载官方模型、不用 Halcon。"));
  tplTip->setWordWrap(true);
  tplTip->setStyleSheet(QStringLiteral("color:#8a9098;font-size:11px;"));
  tplLay->addWidget(tplTip);
  tplLay->addStretch(1);
  tabs_->addTab(tplPage, QStringLiteral("特征模板"));
  connect(loadBtn, &QPushButton::clicked, this, &LocateMatchPanel::onLoadTemplate);
  connect(createBtn, &QPushButton::clicked, this, &LocateMatchPanel::createTemplateRequested);
  connect(clearBtn, &QPushButton::clicked, this, &LocateMatchPanel::onClearTemplate);
  connect(pathEdit_, &QLineEdit::editingFinished, this, [this]() {
    setParam(QStringLiteral("templatePath"), pathEdit_->text().trimmed(), true);
    refreshTemplateChrome();
  });

  // 3) 运行参数
  auto* run = new QFormLayout;
  angleEnable_ = new QCheckBox(QStringLiteral("搜索旋转"));
  angleStart_ = new QDoubleSpinBox;
  angleStart_->setRange(-180, 180);
  angleStart_->setDecimals(1);
  angleEnd_ = new QDoubleSpinBox;
  angleEnd_->setRange(-180, 180);
  angleEnd_->setDecimals(1);
  angleStep_ = new QDoubleSpinBox;
  angleStep_->setRange(0.5, 180);
  angleStep_->setDecimals(1);
  run->addRow(QStringLiteral("角度搜索使能"), angleEnable_);
  run->addRow(QStringLiteral("起始角度"), angleStart_);
  run->addRow(QStringLiteral("终止角度"), angleEnd_);
  run->addRow(QStringLiteral("角度步长"), angleStep_);
  auto* runTip = new QLabel(QStringLiteral("角度范围为闭区间；步长过小会增加耗时。使能关闭时只按 0° 搜索。"));
  runTip->setWordWrap(true);
  runTip->setStyleSheet(QStringLiteral("color:#8a9098;font-size:11px;"));
  auto* runBox = wrapForm(run);
  static_cast<QVBoxLayout*>(runBox->layout())->insertWidget(1, runTip);
  tabs_->addTab(runBox, QStringLiteral("运行参数"));

  // 4) 结果显示
  auto* res = new QFormLayout;
  showOverlay_ = new QCheckBox(QStringLiteral("显示匹配框"));
  showOrigin_ = new QCheckBox(QStringLiteral("显示模板原点"));
  showAngleDeg_ = new QCheckBox(QStringLiteral("显示角度标注"));
  res->addRow(showOverlay_);
  res->addRow(showOrigin_);
  res->addRow(showAngleDeg_);
  resultSummary_ = new QLabel(QStringLiteral("尚未运行"));
  resultSummary_->setWordWrap(true);
  res->addRow(QStringLiteral("结果回显"), resultSummary_);
  hitTable_ = new QTableWidget(0, 4);
  hitTable_->setHorizontalHeaderLabels(
      {QStringLiteral("序"), QStringLiteral("分数"), QStringLiteral("X"), QStringLiteral("Y")});
  hitTable_->horizontalHeader()->setStretchLastSection(true);
  hitTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  hitTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
  hitTable_->setMaximumHeight(140);
  auto* resBox = wrapForm(res);
  static_cast<QVBoxLayout*>(resBox->layout())->insertWidget(2, hitTable_);
  tabs_->addTab(resBox, QStringLiteral("结果显示"));

  auto hookCombo = [this](QComboBox* box, const QString& key) {
    connect(box, &QComboBox::currentIndexChanged, this, [this, box, key](int) {
      setParam(key, box->currentData().toString(), true);
      if (key == QLatin1String("matchMode") || key == QLatin1String("templateSource"))
        refreshTemplateChrome();
    });
  };
  hookCombo(matchMode_, QStringLiteral("matchMode"));
  hookCombo(templateSource_, QStringLiteral("templateSource"));
  connect(minScore_, &QDoubleSpinBox::valueChanged, this, [this](double v) {
    setParam(QStringLiteral("minScore"), v, true);
  });
  connect(maxMatches_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int v) {
    setParam(QStringLiteral("maxMatches"), v, true);
  });
  connect(overlap_, &QDoubleSpinBox::valueChanged, this, [this](double v) {
    setParam(QStringLiteral("overlapThreshold"), v, true);
  });
  connect(angleEnable_, &QCheckBox::toggled, this, [this](bool on) {
    setParam(QStringLiteral("angleEnable"), on, true);
  });
  connect(angleStart_, &QDoubleSpinBox::valueChanged, this, [this](double v) {
    setParam(QStringLiteral("angleStart"), v, true);
  });
  connect(angleEnd_, &QDoubleSpinBox::valueChanged, this, [this](double v) {
    setParam(QStringLiteral("angleEnd"), v, true);
  });
  connect(angleStep_, &QDoubleSpinBox::valueChanged, this, [this](double v) {
    setParam(QStringLiteral("angleStep"), v, true);
  });
  connect(showOverlay_, &QCheckBox::toggled, this, [this](bool on) {
    setParam(QStringLiteral("showOverlay"), on, true);
  });
  connect(showOrigin_, &QCheckBox::toggled, this, [this](bool on) {
    setParam(QStringLiteral("showOrigin"), on, true);
  });
  connect(showAngleDeg_, &QCheckBox::toggled, this, [this](bool on) {
    setParam(QStringLiteral("showAngleDeg"), on, true);
  });
}

void LocateMatchPanel::bindStep(const FlowStep& step) {
  nodeId_ = step.id;
  params_ = normalizeParams(step.params);
  loadEditorsFromParams();
  refreshTemplateChrome();
  refreshResultSummary();
}

QVariantMap LocateMatchPanel::currentParams() const {
  const_cast<LocateMatchPanel*>(this)->flushPendingEdits();
  return params_;
}

void LocateMatchPanel::applySnapshot(const QVariantMap& snap) {
  applying_ = true;
  params_ = normalizeParams(snap);
  loadEditorsFromParams();
  refreshTemplateChrome();
  applying_ = false;
}

void LocateMatchPanel::flushPendingEdits() {
  if (pathEdit_) pathEdit_->clearFocus();
  if (minScore_) minScore_->interpretText();
  if (maxMatches_) maxMatches_->interpretText();
  if (overlap_) overlap_->interpretText();
  if (angleStart_) angleStart_->interpretText();
  if (angleEnd_) angleEnd_->interpretText();
  if (angleStep_) angleStep_->interpretText();
}

void LocateMatchPanel::setLastResult(const QVariantMap& vars) {
  const int count = vars.value(QStringLiteral("locateCount")).toInt();
  const bool ok = vars.value(QStringLiteral("locateOk")).toInt() != 0;
  const double score = vars.value(QStringLiteral("locateScore")).toDouble();
  const double x = vars.value(QStringLiteral("locateX")).toDouble();
  const double y = vars.value(QStringLiteral("locateY")).toDouble();
  const double ang = vars.value(QStringLiteral("locateAngle")).toDouble();
  if (resultSummary_) {
    resultSummary_->setText(
        QStringLiteral("%1 · 目标 %2 · 分数 %3 · (%4, %5) · 角 %6°")
            .arg(ok ? QStringLiteral("OK") : QStringLiteral("NG"))
            .arg(count)
            .arg(score, 0, 'f', 3)
            .arg(x, 0, 'f', 1)
            .arg(y, 0, 'f', 1)
            .arg(ang, 0, 'f', 1));
  }
  if (hitTable_) {
    hitTable_->setRowCount(count > 0 ? 1 : 0);
    if (count > 0) {
      hitTable_->setItem(0, 0, new QTableWidgetItem(QStringLiteral("1")));
      hitTable_->setItem(0, 1, new QTableWidgetItem(QString::number(score, 'f', 3)));
      hitTable_->setItem(0, 2, new QTableWidgetItem(QString::number(x, 'f', 1)));
      hitTable_->setItem(0, 3, new QTableWidgetItem(QString::number(y, 'f', 1)));
    }
  }
}

int LocateMatchPanel::tabCount() const { return tabs_ ? tabs_->count() : 0; }

bool LocateMatchPanel::templateReady() const {
  const QString src = params_.value(QStringLiteral("templateSource")).toString();
  if (src == QLatin1String("soft_plate") || src == QLatin1String("capture")) return true;
  if (params_.value(QStringLiteral("templateCaptured")).toBool()) return true;
  const QString path = params_.value(QStringLiteral("templatePath")).toString().trimmed();
  return !path.isEmpty() && QFileInfo::exists(path);
}

bool LocateMatchPanel::createTemplateFromImage(const QImage& scene, QString* error) {
  if (scene.isNull()) {
    if (error) *error = QStringLiteral("当前没有可截取的画面");
    return false;
  }
  const int tw = params_.value(QStringLiteral("templateW"), 64).toInt();
  const int th = params_.value(QStringLiteral("templateH"), 64).toInt();
  QImage tpl = salientCrop(scene, tw > 0 ? tw : 64, th > 0 ? th : 64);
  if (tpl.isNull()) tpl = centerCrop(scene, tw > 0 ? tw : 64, th > 0 ? th : 64);
  if (tpl.isNull()) {
    if (error) *error = QStringLiteral("截取模板失败");
    return false;
  }
  const QString dir = workbenchTemplatesDir();
  QDir().mkpath(dir);
  const QString id = nodeId_.isEmpty() ? QStringLiteral("locate") : nodeId_;
  const QString path = dir + QLatin1Char('/') + id + QStringLiteral(".png");
  if (!tpl.save(path)) {
    if (error) *error = QStringLiteral("无法写入 %1").arg(path);
    return false;
  }
  setParam(QStringLiteral("templatePath"), path, true);
  setParam(QStringLiteral("templateSource"), QStringLiteral("file"), true);
  setParam(QStringLiteral("templateCaptured"), true, true);
  loadEditorsFromParams();
  refreshTemplateChrome();
  return true;
}

void LocateMatchPanel::loadEditorsFromParams() {
  applying_ = true;
  const auto setCombo = [](QComboBox* box, const QString& value) {
    if (!box) return;
    const int i = box->findData(value);
    box->setCurrentIndex(i >= 0 ? i : 0);
  };
  setCombo(matchMode_, params_.value(QStringLiteral("matchMode")).toString());
  setCombo(templateSource_, params_.value(QStringLiteral("templateSource")).toString());
  if (minScore_) minScore_->setValue(params_.value(QStringLiteral("minScore")).toDouble());
  if (maxMatches_) maxMatches_->setValue(params_.value(QStringLiteral("maxMatches")).toInt());
  if (overlap_) overlap_->setValue(params_.value(QStringLiteral("overlapThreshold")).toDouble());
  if (pathEdit_) pathEdit_->setText(params_.value(QStringLiteral("templatePath")).toString());
  if (angleEnable_) angleEnable_->setChecked(params_.value(QStringLiteral("angleEnable")).toBool());
  if (angleStart_) angleStart_->setValue(params_.value(QStringLiteral("angleStart")).toDouble());
  if (angleEnd_) angleEnd_->setValue(params_.value(QStringLiteral("angleEnd")).toDouble());
  if (angleStep_) angleStep_->setValue(params_.value(QStringLiteral("angleStep")).toDouble());
  if (showOverlay_) showOverlay_->setChecked(params_.value(QStringLiteral("showOverlay")).toBool());
  if (showOrigin_) showOrigin_->setChecked(params_.value(QStringLiteral("showOrigin")).toBool());
  if (showAngleDeg_)
    showAngleDeg_->setChecked(params_.value(QStringLiteral("showAngleDeg")).toBool());
  applying_ = false;
}

void LocateMatchPanel::setParam(const QString& key, const QVariant& value, bool emitChange) {
  if (applying_) {
    params_.insert(key, value);
    return;
  }
  const QVariant old = params_.value(key);
  params_.insert(key, value);
  if (!emitChange || old == value || nodeId_.isEmpty()) return;
  QString text;
  if (value.typeId() == QMetaType::Bool)
    text = value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  else if (value.typeId() == QMetaType::Double)
    text = QString::number(value.toDouble(), 'g', 10);
  else
    text = value.toString();
  emit paramEdited(nodeId_, key, text);
}

void LocateMatchPanel::refreshTemplateChrome() {
  const QString mode = params_.value(QStringLiteral("matchMode")).toString();
  if (tabs_ && tabs_->count() > 1) {
    tabs_->setTabText(1, mode == QLatin1String("gray") ? QStringLiteral("灰度模板")
                                                       : QStringLiteral("特征模板"));
  }
  if (tplStatus_) {
    tplStatus_->setText(templateReady() ? QStringLiteral("模板状态：已就绪（已创建/载入/软标牌）")
                                        : QStringLiteral("模板状态：未配置"));
  }
}

void LocateMatchPanel::refreshResultSummary() {
  if (resultSummary_ && resultSummary_->text().isEmpty())
    resultSummary_->setText(QStringLiteral("尚未运行"));
}

void LocateMatchPanel::onLoadTemplate() {
  if (workbenchIsHeadless()) return;
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("载入模板"), workbenchTemplatesDir(),
      QStringLiteral("图像 (*.png *.bmp *.jpg *.jpeg *.tif);;所有文件 (*)"));
  if (path.isEmpty()) return;
  setParam(QStringLiteral("templatePath"), path, true);
  setParam(QStringLiteral("templateSource"), QStringLiteral("file"), true);
  loadEditorsFromParams();
  refreshTemplateChrome();
}

void LocateMatchPanel::onClearTemplate() {
  setParam(QStringLiteral("templatePath"), QString(), true);
  setParam(QStringLiteral("templateCaptured"), false, true);
  loadEditorsFromParams();
  refreshTemplateChrome();
}

QStringList LocateMatchPanel::selfTest() {
  QStringList fails;
  const QVariantMap n = normalizeParams({});
  if (n.value(QStringLiteral("matchMode")).toString() != QLatin1String("fast"))
    fails << QStringLiteral("normalize matchMode");
  if (!n.value(QStringLiteral("angleEnable")).toBool())
    fails << QStringLiteral("normalize angleEnable");

  LocateMatchPanel panel;
  FlowStep s;
  s.id = QStringLiteral("loc-selftest");
  s.name = QStringLiteral("模板与定位");
  s.operation = QStringLiteral("locate");
  s.params.insert(QStringLiteral("templateSource"), QStringLiteral("soft_plate"));
  s.params.insert(QStringLiteral("minScore"), 0.55);
  s.params.insert(QStringLiteral("angleEnable"), true);
  panel.bindStep(s);
  if (panel.tabCount() != 4) fails << QStringLiteral("tabCount=%1").arg(panel.tabCount());
  if (!panel.templateReady()) fails << QStringLiteral("soft_plate should be ready");
  const QVariantMap cur = panel.currentParams();
  if (cur.value(QStringLiteral("matchMode")).toString() != QLatin1String("fast"))
    fails << QStringLiteral("default matchMode");
  if (!cur.value(QStringLiteral("angleEnable")).toBool())
    fails << QStringLiteral("angleEnable lost");

  QVariantMap snap = cur;
  snap.insert(QStringLiteral("angleStart"), -15);
  snap.insert(QStringLiteral("angleEnd"), 15);
  panel.applySnapshot(snap);
  if (qAbs(panel.currentParams().value(QStringLiteral("angleStart")).toDouble() + 15) > 0.01)
    fails << QStringLiteral("applySnapshot angleStart");

  QImage img(80, 80, QImage::Format_RGB888);
  img.fill(QColor(20, 20, 20));
  for (int y = 20; y < 60; ++y)
    for (int x = 20; x < 60; ++x) img.setPixelColor(x, y, QColor(240, 240, 240));
  QString err;
  if (!panel.createTemplateFromImage(img, &err))
    fails << (QStringLiteral("createTemplate: ") + err);
  if (!panel.templateReady()) fails << QStringLiteral("created template not ready");
  const QString path = panel.currentParams().value(QStringLiteral("templatePath")).toString();
  if (path.isEmpty() || !QFileInfo::exists(path))
    fails << QStringLiteral("template file missing");

  panel.setLastResult({{QStringLiteral("locateOk"), 1},
                       {QStringLiteral("locateCount"), 1},
                       {QStringLiteral("locateScore"), 0.97},
                       {QStringLiteral("locateX"), 10},
                       {QStringLiteral("locateY"), 20},
                       {QStringLiteral("locateAngle"), 0}});
  return fails;
}

}  // namespace sieans_qt
