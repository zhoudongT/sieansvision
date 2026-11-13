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
#include <QCryptographicHash>
#include <QInputDialog>
#include <QListWidget>
#include <QListWidgetItem>
#include <QMessageBox>
#include <QUuid>
#include <QVBoxLayout>
#include <QPainter>
#include <QPaintEvent>
#include <QMouseEvent>
#include <QEvent>

#include <algorithm>
#include <optional>

namespace sieans_qt {
namespace {

/** 属性表单：右对齐标签、字段按内容宽度，避免通栏拉宽。 */
void polishForm(QFormLayout* form) {
  form->setContentsMargins(0, 0, 0, 0);
  form->setHorizontalSpacing(12);
  form->setVerticalSpacing(8);
  form->setLabelAlignment(Qt::AlignRight | Qt::AlignVCenter);
  form->setFormAlignment(Qt::AlignLeft | Qt::AlignTop);
  form->setFieldGrowthPolicy(QFormLayout::FieldsStayAtSizeHint);
}

/** 单行表单标签，不折成叠字。 */
QLabel* formLabel(const QString& text, const QString& tip = {}) {
  auto* lab = new QLabel(text);
  lab->setMinimumWidth(72);
  lab->setWordWrap(false);
  lab->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
  if (!tip.isEmpty()) lab->setToolTip(tip);
  return lab;
}

QWidget* wrapForm(QFormLayout* form) {
  polishForm(form);
  auto* w = new QWidget;
  auto* lay = new QVBoxLayout(w);
  lay->setContentsMargins(14, 10, 16, 12);
  lay->addLayout(form);
  lay->addStretch(1);
  return w;
}


QString newTemplateId() {
  return QUuid::createUuid().toString(QUuid::WithoutBraces).remove(QLatin1Char('-')).left(12);
}

QVariantList normalizedLibrary(const QVariant& raw) {
  QVariantList out;
  if (raw.typeId() != QMetaType::QVariantList) return out;
  for (const QVariant& v : raw.toList()) {
    const QVariantMap e = v.toMap();
    if (e.isEmpty()) continue;
    QVariantMap n;
    n.insert(QStringLiteral("id"), e.value(QStringLiteral("id")).toString());
    n.insert(QStringLiteral("name"), e.value(QStringLiteral("name")).toString());
    n.insert(QStringLiteral("path"), e.value(QStringLiteral("path")).toString());
    n.insert(QStringLiteral("note"), e.value(QStringLiteral("note")).toString());
    if (n.value(QStringLiteral("id")).toString().isEmpty())
      n.insert(QStringLiteral("id"), newTemplateId());
    out.push_back(n);
  }
  return out;
}

double clamp01(double v) {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

std::optional<double> normalizeScore(const QVariant& v) {
  if (!v.isValid() || v.isNull() || (v.typeId() == QMetaType::QString && v.toString().isEmpty()))
    return std::nullopt;
  bool ok = false;
  const double d = v.toDouble(&ok);
  if (!ok) return std::nullopt;
  return clamp01(d);
}

QVariantMap softEstimateScores(const QVariantList& lib, const QString& seed) {
  QVariantMap out;
  const QByteArray seedB = (seed.isEmpty() ? QByteArray("sieans") : seed.toUtf8());
  for (int i = 0; i < lib.size(); ++i) {
    const QVariantMap e = lib[i].toMap();
    const QString eid = e.value(QStringLiteral("id")).toString().isEmpty()
                            ? QStringLiteral("t%1").arg(i)
                            : e.value(QStringLiteral("id")).toString();
    const QString path = e.value(QStringLiteral("path")).toString();
    const QByteArray dig = QCryptographicHash::hash(
        seedB + eid.toUtf8() + path.toUtf8(), QCryptographicHash::Sha1);
    const quint16 n = (static_cast<quint8>(dig[0]) << 8) | static_cast<quint8>(dig[1]);
    const double score = 0.55 + 0.43 * (double(n) / 65535.0);
    out.insert(eid, QString::number(score, 'f', 4).toDouble());
  }
  return out;
}

QVariant lookupScore(const QVariantMap& scores, const QVariantMap& entry) {
  const QString eid = entry.value(QStringLiteral("id")).toString();
  const QString name = entry.value(QStringLiteral("name")).toString();
  const QString path = entry.value(QStringLiteral("path")).toString();
  if (scores.contains(eid)) return scores.value(eid);
  if (!name.isEmpty() && scores.contains(name)) return scores.value(name);
  if (!path.isEmpty() && scores.contains(path)) return scores.value(path);
  return {};
}

QVariantMap buildBatchScoreboard(const QVariantList& lib, const QVariantMap& scores,
                                 double threshold, const QString& activeId) {
  const double thr = clamp01(threshold);
  QVariantList rows;
  struct Ranked {
    int index;
    double score;
    bool has;
  };
  QVector<Ranked> ranked;
  for (int i = 0; i < lib.size(); ++i) {
    const QVariantMap e = lib[i].toMap();
    const QString eid = e.value(QStringLiteral("id")).toString().isEmpty()
                            ? QStringLiteral("t%1").arg(i)
                            : e.value(QStringLiteral("id")).toString();
    const auto sc = normalizeScore(lookupScore(scores, e));
    QVariantMap row;
    row.insert(QStringLiteral("id"), eid);
    row.insert(QStringLiteral("name"),
               e.value(QStringLiteral("name")).toString().isEmpty()
                   ? eid
                   : e.value(QStringLiteral("name")).toString());
    row.insert(QStringLiteral("path"), e.value(QStringLiteral("path")).toString());
    row.insert(QStringLiteral("note"), e.value(QStringLiteral("note")).toString());
    row.insert(QStringLiteral("pending"), !sc.has_value());
    if (sc) {
      row.insert(QStringLiteral("score"), *sc);
      row.insert(QStringLiteral("ok"), *sc >= thr);
    } else {
      row.insert(QStringLiteral("score"), QVariant());
      row.insert(QStringLiteral("ok"), false);
    }
    row.insert(QStringLiteral("rank"), 0);
    row.insert(QStringLiteral("active"), !activeId.isEmpty() && eid == activeId);
    rows.push_back(row);
    ranked.push_back({i, sc ? *sc : -1.0, sc.has_value()});
  }
  std::sort(ranked.begin(), ranked.end(), [](const Ranked& a, const Ranked& b) {
    if (a.has != b.has) return a.has > b.has;
    return a.score > b.score;
  });
  int rank = 1;
  QString bestId;
  double bestScore = 0;
  bool hasBest = false;
  for (const Ranked& r : ranked) {
    QVariantMap row = rows[r.index].toMap();
    if (r.has) {
      row.insert(QStringLiteral("rank"), rank++);
      if (!hasBest) {
        hasBest = true;
        bestId = row.value(QStringLiteral("id")).toString();
        bestScore = r.score;
      }
    } else {
      row.insert(QStringLiteral("rank"), 0);
    }
    rows[r.index] = row;
  }
  int passN = 0, failN = 0;
  for (const QVariant& v : rows) {
    const QVariantMap row = v.toMap();
    if (row.value(QStringLiteral("pending")).toBool()) continue;
    if (row.value(QStringLiteral("ok")).toBool()) ++passN;
    else ++failN;
  }
  QString summary;
  if (!hasBest)
    summary = QStringLiteral("未评分 · %1 项").arg(lib.size());
  else
    summary = QStringLiteral("最优 %1 · 过阈 %2 / 未过 %3 · 阈 %4")
                  .arg(QString::number(bestScore, 'f', 3))
                  .arg(passN)
                  .arg(failN)
                  .arg(QString::number(thr, 'f', 3));
  QVariantMap board;
  board.insert(QStringLiteral("rows"), rows);
  board.insert(QStringLiteral("bestId"), bestId);
  board.insert(QStringLiteral("bestScore"), hasBest ? QVariant(bestScore) : QVariant());
  board.insert(QStringLiteral("passCount"), passN);
  board.insert(QStringLiteral("failCount"), failN);
  board.insert(QStringLiteral("threshold"), thr);
  board.insert(QStringLiteral("summary"), summary);
  return board;
}

}  // namespace


MatchScoreSpark::MatchScoreSpark(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("matchScoreSparkWidget"));
  setFixedHeight(28);
  setMinimumWidth(120);
  setMouseTracking(true);
  setCursor(Qt::PointingHandCursor);
  setToolTip(QStringLiteral("匹配分趋势 · 悬停看点 · 点击跳帧 · 无硬件"));
}

void MatchScoreSpark::setPoints(const QVector<QVariantMap>& pts) {
  points_ = pts;
  const int cap = 16;
  windowStart_ = qMax(0, pts.size() - cap);
  QVector<double> vals;
  for (int i = windowStart_; i < pts.size(); ++i)
    vals.push_back(pts[i].value(QStringLiteral("score")).toDouble());
  heights_.clear();
  if (vals.size() >= 2) {
    double lo = vals[0], hi = vals[0];
    for (double v : vals) {
      lo = qMin(lo, v);
      hi = qMax(hi, v);
    }
    const double span = hi - lo;
    for (double v : vals)
      heights_.push_back(span < 1e-9 ? 0.5 : (v - lo) / span);
  } else if (vals.size() == 1) {
    heights_.push_back(qBound(0.0, vals[0], 1.0));
  }
  hover_ = -1;
  update();
}

int MatchScoreSpark::localAtX(int x) const {
  const int n = heights_.size();
  if (n <= 0) return -1;
  const int pad = 3;
  const int gap = 1;
  const int avail = qMax(1, width() - pad * 2);
  const int barW = qMax(1, (avail - gap * (n - 1)) / n);
  if (x < pad) return 0;
  const int stride = barW + gap;
  const int i = (x - pad) / stride;
  return qBound(0, i, n - 1);
}

QVariantMap MatchScoreSpark::jumpToLocal(int local) {
  if (local < 0 || local >= heights_.size()) return {};
  const int absIndex = windowStart_ + local;
  QVariantMap pt;
  if (absIndex >= 0 && absIndex < points_.size()) pt = points_[absIndex];
  QVariantMap bag;
  bag.insert(QStringLiteral("index"), absIndex);
  bag.insert(QStringLiteral("local"), local);
  bag.insert(QStringLiteral("frame"), pt.value(QStringLiteral("frame")).toString());
  bag.insert(QStringLiteral("label"), pt.value(QStringLiteral("label")).toString());
  bag.insert(QStringLiteral("score"),
             pt.contains(QStringLiteral("score")) ? pt.value(QStringLiteral("score"))
                                                  : QVariant(heights_[local]));
  bag.insert(QStringLiteral("ok"), pt.value(QStringLiteral("ok")));
  bag.insert(QStringLiteral("templateId"), pt.value(QStringLiteral("templateId")).toString());
  emit frameJumpRequested(bag);
  return bag;
}

void MatchScoreSpark::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.fillRect(rect(), QColor(QStringLiteral("#12161c")));
  const int n = heights_.size();
  if (n <= 0) return;
  const int pad = 3;
  const int gap = 1;
  const int avail = qMax(1, width() - pad * 2);
  const int barW = qMax(1, (avail - gap * (n - 1)) / n);
  const int h = height() - 4;
  for (int i = 0; i < n; ++i) {
    const int x = pad + i * (barW + gap);
    const int bh = qMax(2, int(heights_[i] * h));
    const int y = height() - 2 - bh;
    QColor c(QStringLiteral("#5aa0d0"));
    const int absI = windowStart_ + i;
    if (absI >= 0 && absI < points_.size()) {
      const QVariant okv = points_[absI].value(QStringLiteral("ok"));
      if (okv.isValid())
        c = okv.toBool() ? QColor(QStringLiteral("#3ecf8e")) : QColor(QStringLiteral("#d08080"));
    }
    if (i == hover_) c = c.lighter(130);
    p.fillRect(x, y, barW, bh, c);
  }
}

void MatchScoreSpark::mouseMoveEvent(QMouseEvent* event) {
  hover_ = localAtX(event->position().toPoint().x());
  if (hover_ >= 0) {
    const auto bag = [&]() {
      const int absI = windowStart_ + hover_;
      if (absI >= 0 && absI < points_.size()) return points_[absI];
      return QVariantMap{};
    }();
    const bool hasOk = bag.contains(QStringLiteral("ok"));
    const QString mark = hasOk ? (bag.value(QStringLiteral("ok")).toBool() ? QStringLiteral("✓")
                                                                          : QStringLiteral("✗"))
                               : QStringLiteral("·");
    QString tip = QStringLiteral("#%1 %2 %3")
                      .arg(windowStart_ + hover_ + 1)
                      .arg(mark)
                      .arg(bag.value(QStringLiteral("score"), heights_.value(hover_)).toDouble(), 0, 'f', 3);
    if (!bag.value(QStringLiteral("label")).toString().isEmpty())
      tip += QStringLiteral(" · ") + bag.value(QStringLiteral("label")).toString();
    if (!bag.value(QStringLiteral("frame")).toString().isEmpty())
      tip += QStringLiteral(" · frame=") + QFileInfo(bag.value(QStringLiteral("frame")).toString()).fileName();
    tip += QStringLiteral(" · 点击跳到该帧");
    setToolTip(tip);
  }
  update();
}

void MatchScoreSpark::mousePressEvent(QMouseEvent* event) {
  if (event->button() == Qt::LeftButton) jumpToLocal(localAtX(event->position().toPoint().x()));
}

void MatchScoreSpark::leaveEvent(QEvent*) {
  hover_ = -1;
  setToolTip(QStringLiteral("匹配分趋势 · 悬停看点 · 点击跳帧 · 无硬件"));
  update();
}

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
  if (p.value(QStringLiteral("templateLibrary")).typeId() != QMetaType::QVariantList)
    p.insert(QStringLiteral("templateLibrary"), QVariantList{});
  else
    p.insert(QStringLiteral("templateLibrary"),
             normalizedLibrary(p.value(QStringLiteral("templateLibrary"))));
  if (!p.contains(QStringLiteral("activeTemplateId")))
    p.insert(QStringLiteral("activeTemplateId"), QString());
  if (!p.contains(QStringLiteral("batchScoreThreshold")))
    p.insert(QStringLiteral("batchScoreThreshold"),
             p.value(QStringLiteral("minScore"), 0.85).toDouble());
  if (p.value(QStringLiteral("lastBatchScoreboard")).typeId() != QMetaType::QVariantMap)
    p.insert(QStringLiteral("lastBatchScoreboard"), QVariantMap{});
  return p;
}

LocateMatchPanel::LocateMatchPanel(QWidget* parent) : QWidget(parent) {
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(0, 0, 0, 0);
  auto* hint = new QLabel(
      QStringLiteral("对齐 VisionMaster「快速匹配」：基本参数 / 特征模板 / 运行参数 / 结果显示"));
  hint->setObjectName(QStringLiteral("muted"));
  hint->setWordWrap(true);
  hint->setStyleSheet(QStringLiteral("padding:8px 14px 4px 14px;"));
  root->addWidget(hint);

  tabs_ = new QTabWidget;
  root->addWidget(tabs_, 1);

  // 1) 基本参数
  auto* basic = new QFormLayout;
  matchMode_ = new QComboBox;
  matchMode_->addItem(QStringLiteral("快速匹配"), QStringLiteral("fast"));
  matchMode_->addItem(QStringLiteral("灰度模板匹配"), QStringLiteral("gray"));
  matchMode_->addItem(QStringLiteral("归一化相关 NCC"), QStringLiteral("ncc"));
  matchMode_->setToolTip(QStringLiteral("fast/gray 为灰度 SAD；ncc 为零均值归一化互相关。尺度与多模板库见属性或 templateLibrary。不做变形匹配。"));
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
  matchMode_->setMinimumWidth(180);
  templateSource_->setMinimumWidth(180);
  minScore_->setMinimumWidth(96);
  maxMatches_->setMinimumWidth(96);
  overlap_->setMinimumWidth(96);
  overlap_->setToolTip(QStringLiteral("多目标 NMS 的 IoU 阈值（overlapThreshold）"));
  basic->addRow(formLabel(QStringLiteral("匹配模式")), matchMode_);
  basic->addRow(formLabel(QStringLiteral("模板来源")), templateSource_);
  basic->addRow(formLabel(QStringLiteral("最低分数")), minScore_);
  basic->addRow(formLabel(QStringLiteral("最多目标")), maxMatches_);
  basic->addRow(formLabel(QStringLiteral("重叠抑制"),
                         QStringLiteral("多目标 NMS 的 IoU 阈值（overlapThreshold）")),
                overlap_);
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

  auto* libFrame = new QWidget;
  libFrame->setObjectName(QStringLiteral("locateTemplateLibraryFrame"));
  auto* libLay = new QVBoxLayout(libFrame);
  libLay->setContentsMargins(8, 8, 8, 8);
  libLay->setSpacing(6);
  auto* libHead = new QHBoxLayout;
  auto* libTitle = new QLabel(QStringLiteral("模板库"));
  libTitle->setStyleSheet(QStringLiteral("font-weight:600;color:#c8d0d8;"));
  libCount_ = new QLabel(QStringLiteral("0 项"));
  libCount_->setObjectName(QStringLiteral("locateTplLibCount"));
  libCount_->setStyleSheet(QStringLiteral("color:#888;"));
  libHead->addWidget(libTitle);
  libHead->addWidget(libCount_);
  libHead->addStretch(1);
  libLay->addLayout(libHead);
  libList_ = new QListWidget;
  libList_->setObjectName(QStringLiteral("locateTemplateLibraryList"));
  libList_->setMinimumHeight(90);
  libList_->setToolTip(QStringLiteral("双击选用 · 选中后可预览/移除"));
  libLay->addWidget(libList_);
  libPreview_ = new QLabel(QStringLiteral("预览：选中库条目查看路径/备注"));
  libPreview_->setObjectName(QStringLiteral("locateTplLibPreview"));
  libPreview_->setWordWrap(true);
  libPreview_->setStyleSheet(QStringLiteral("color:#8ab;font-size:11px;padding:2px 0;"));
  libLay->addWidget(libPreview_);
  auto* libBtns = new QHBoxLayout;
  auto* addLibBtn = new QPushButton(QStringLiteral("加入库"));
  addLibBtn->setToolTip(QStringLiteral("将当前模板路径加入模板库（可改名）"));
  auto* selLibBtn = new QPushButton(QStringLiteral("选用"));
  auto* prevLibBtn = new QPushButton(QStringLiteral("预览"));
  auto* rmLibBtn = new QPushButton(QStringLiteral("移除"));
  rmLibBtn->setToolTip(QStringLiteral("从模板库移除（不删磁盘文件）"));
  libBtns->addWidget(addLibBtn);
  libBtns->addWidget(selLibBtn);
  libBtns->addWidget(prevLibBtn);
  libBtns->addWidget(rmLibBtn);
  libBtns->addStretch(1);
  libLay->addLayout(libBtns);

  auto* sbHead = new QHBoxLayout;
  auto* sbTitle = new QLabel(QStringLiteral("批量记分板"));
  sbTitle->setStyleSheet(QStringLiteral("font-weight:600;color:#c8d0d8;font-size:12px;"));
  boardSummary_ = new QLabel(QStringLiteral("未评分"));
  boardSummary_->setObjectName(QStringLiteral("locateBatchScoreSummary"));
  boardSummary_->setStyleSheet(QStringLiteral("color:#8ab;font-size:11px;"));
  sbHead->addWidget(sbTitle);
  sbHead->addWidget(boardSummary_, 1);
  libLay->addLayout(sbHead);
  auto* thrRow = new QHBoxLayout;
  thrRow->addWidget(new QLabel(QStringLiteral("阈值")));
  batchThr_ = new QDoubleSpinBox;
  batchThr_->setObjectName(QStringLiteral("locateBatchScoreThr"));
  batchThr_->setRange(0.0, 1.0);
  batchThr_->setDecimals(3);
  batchThr_->setSingleStep(0.01);
  batchThr_->setValue(0.85);
  auto* scoreBtn = new QPushButton(QStringLiteral("批量评分"));
  scoreBtn->setToolTip(QStringLiteral("对模板库全员打分（软估或注入分）；无 Halcon / 无相机"));
  auto* bestBtn = new QPushButton(QStringLiteral("选用最优"));
  bestBtn->setToolTip(QStringLiteral("按记分板选用最高分模板"));
  thrRow->addWidget(batchThr_);
  thrRow->addWidget(scoreBtn);
  thrRow->addWidget(bestBtn);
  thrRow->addStretch(1);
  libLay->addLayout(thrRow);
  boardTable_ = new QTableWidget(0, 4);
  boardTable_->setObjectName(QStringLiteral("locateBatchScoreTable"));
  boardTable_->setHorizontalHeaderLabels(
      {QStringLiteral("模板"), QStringLiteral("分数"), QStringLiteral("判定"), QStringLiteral("序")});
  boardTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  boardTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
  boardTable_->setMaximumHeight(130);
  boardTable_->horizontalHeader()->setStretchLastSection(true);
  libLay->addWidget(boardTable_);
  auto* trendRow = new QHBoxLayout;
  spark_ = new MatchScoreSpark;
  sparkJumpLab_ = new QLabel;
  sparkJumpLab_->setObjectName(QStringLiteral("locateMatchSparkJumpLab"));
  sparkJumpLab_->setStyleSheet(QStringLiteral("color:#9ad;font-size:11px;"));
  sparkJumpLab_->setVisible(false);
  trendRow->addWidget(spark_, 0);
  trendRow->addWidget(sparkJumpLab_, 1);
  libLay->addLayout(trendRow);
  connect(spark_, &MatchScoreSpark::frameJumpRequested, this,
          [this](const QVariantMap& bag) {
            lastSparkJump_ = bag;
            lastSparkJump_.insert(QStringLiteral("nodeId"), nodeId_);
            if (sparkJumpLab_) {
              const QString frame = bag.value(QStringLiteral("frame")).toString();
              sparkJumpLab_->setText(
                  QStringLiteral("跳帧 · #%1 · %2")
                      .arg(bag.value(QStringLiteral("index")).toInt() + 1)
                      .arg(frame.isEmpty() ? bag.value(QStringLiteral("label")).toString()
                                           : QFileInfo(frame).fileName()));
              sparkJumpLab_->setVisible(true);
            }
            emit sparkJumpRequested(lastSparkJump_);
          });
  tplLay->addWidget(libFrame);
  tplLay->addStretch(1);
  tabs_->addTab(tplPage, QStringLiteral("特征模板"));
  connect(addLibBtn, &QPushButton::clicked, this, &LocateMatchPanel::onAddLibraryClicked);
  connect(selLibBtn, &QPushButton::clicked, this, &LocateMatchPanel::onSelectLibraryClicked);
  connect(prevLibBtn, &QPushButton::clicked, this, &LocateMatchPanel::onPreviewLibraryClicked);
  connect(rmLibBtn, &QPushButton::clicked, this, &LocateMatchPanel::onRemoveLibraryClicked);
  connect(scoreBtn, &QPushButton::clicked, this, &LocateMatchPanel::onBatchScoreClicked);
  connect(bestBtn, &QPushButton::clicked, this, &LocateMatchPanel::onSelectBestClicked);
  connect(libList_, &QListWidget::itemDoubleClicked, this,
          [this](QListWidgetItem*) { onSelectLibraryClicked(); });
  connect(libList_, &QListWidget::currentItemChanged, this,
          [this](QListWidgetItem*, QListWidgetItem*) { refreshLibraryPreview(); });
  connect(batchThr_, &QDoubleSpinBox::valueChanged, this, [this](double v) {
    setParam(QStringLiteral("batchScoreThreshold"), v, true);
    if (!params_.value(QStringLiteral("lastBatchScoreboard")).toMap().isEmpty())
      runBatchScoreboard({}, true);
  });
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
  auto* runTip = new QLabel(QStringLiteral("角度范围为闭区间。尺度搜索用 scaleEnable / scaleMin / scaleMax / scaleStep，各向异性再开 scaleAniso。模板×尺度×角度组合上限 400。使能关闭时只按 0° 搜索。"));
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

void LocateMatchPanel::appendTrendPoint(double score, bool ok, const QString& frame,
                                        const QString& label) {
  if (score < 0) return;
  QVariantMap pt;
  pt.insert(QStringLiteral("score"), qBound(0.0, score, 1.0));
  pt.insert(QStringLiteral("ok"), ok);
  pt.insert(QStringLiteral("frame"), frame);
  pt.insert(QStringLiteral("label"),
            label.isEmpty() ? QStringLiteral("#%1").arg(trendPoints_.size() + 1) : label);
  pt.insert(QStringLiteral("templateId"), params_.value(QStringLiteral("activeTemplateId")).toString());
  trendPoints_.push_back(pt);
  while (trendPoints_.size() > kTrendCapacity) trendPoints_.removeFirst();
  refreshTrendSpark();
}

void LocateMatchPanel::refreshTrendSpark() {
  if (spark_) spark_->setPoints(trendPoints_);
}

QVariantMap LocateMatchPanel::jumpTrendLocal(int local) {
  if (!spark_) return {};
  return spark_->jumpToLocal(local);
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
  const QString frame = vars.value(QStringLiteral("filmstripPath")).toString();
  if (vars.contains(QStringLiteral("locateScore")))
    appendTrendPoint(score, ok, frame);
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
  if (batchThr_)
    batchThr_->setValue(params_.value(QStringLiteral("batchScoreThreshold"),
                                      params_.value(QStringLiteral("minScore"), 0.85))
                            .toDouble());
  applying_ = false;
  refreshLibraryList();
  refreshScoreboardTable();
}

void LocateMatchPanel::setParam(const QString& key, const QVariant& value, bool emitChange) {
  if (applying_) {
    params_.insert(key, value);
    return;
  }
  const QVariant old = params_.value(key);
  params_.insert(key, value);
  if (!emitChange || old == value || nodeId_.isEmpty()) return;
  if (value.typeId() == QMetaType::QVariantList || value.typeId() == QMetaType::QVariantMap) {
    emit structuredParamEdited(nodeId_, key, value);
    return;
  }
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


int LocateMatchPanel::libraryCount() const {
  return normalizedLibrary(params_.value(QStringLiteral("templateLibrary"))).size();
}

QString LocateMatchPanel::activeTemplateId() const {
  return params_.value(QStringLiteral("activeTemplateId")).toString();
}

QVariantMap LocateMatchPanel::lastBatchScoreboard() const {
  return params_.value(QStringLiteral("lastBatchScoreboard")).toMap();
}

QString LocateMatchPanel::addLibraryEntry(const QString& path, const QString& name,
                                          const QString& note) {
  const QString p = path.trimmed();
  if (p.isEmpty()) return {};
  QFileInfo fi(p);
  const QString nm = name.trimmed().isEmpty()
                         ? (fi.completeBaseName().isEmpty() ? QStringLiteral("模板")
                                                            : fi.completeBaseName())
                         : name.trimmed();
  QVariantMap entry;
  entry.insert(QStringLiteral("id"), newTemplateId());
  entry.insert(QStringLiteral("name"), nm);
  entry.insert(QStringLiteral("path"), p);
  entry.insert(QStringLiteral("note"), note);
  QVariantList lib = normalizedLibrary(params_.value(QStringLiteral("templateLibrary")));
  QVariantList kept;
  for (const QVariant& v : lib) {
    if (v.toMap().value(QStringLiteral("path")).toString() == p) continue;
    kept.push_back(v);
  }
  kept.push_back(entry);
  setParam(QStringLiteral("templateLibrary"), kept, true);
  if (params_.value(QStringLiteral("templatePath")).toString().trimmed().isEmpty()) {
    setParam(QStringLiteral("templatePath"), p, true);
    setParam(QStringLiteral("activeTemplateId"), entry.value(QStringLiteral("id")), true);
    loadEditorsFromParams();
    refreshTemplateChrome();
  } else {
    refreshLibraryList();
  }
  return entry.value(QStringLiteral("id")).toString();
}

bool LocateMatchPanel::selectLibraryEntry(const QString& id) {
  const QVariantList lib = normalizedLibrary(params_.value(QStringLiteral("templateLibrary")));
  for (const QVariant& v : lib) {
    const QVariantMap e = v.toMap();
    if (e.value(QStringLiteral("id")).toString() != id) continue;
    const QString path = e.value(QStringLiteral("path")).toString().trimmed();
    if (path.isEmpty()) return false;
    setParam(QStringLiteral("templatePath"), path, true);
    setParam(QStringLiteral("activeTemplateId"), id, true);
    loadEditorsFromParams();
    refreshTemplateChrome();
    if (libPreview_) {
      libPreview_->setText(QStringLiteral("已选用「%1」→ %2")
                               .arg(e.value(QStringLiteral("name")).toString(), path));
      libPreview_->setStyleSheet(
          QStringLiteral("color:#2e7d32;font-size:11px;font-weight:600;"));
    }
    return true;
  }
  return false;
}

bool LocateMatchPanel::removeLibraryEntry(const QString& id) {
  if (id.isEmpty()) return false;
  QVariantList lib = normalizedLibrary(params_.value(QStringLiteral("templateLibrary")));
  QVariantList kept;
  bool hit = false;
  for (const QVariant& v : lib) {
    if (v.toMap().value(QStringLiteral("id")).toString() == id) {
      hit = true;
      continue;
    }
    kept.push_back(v);
  }
  if (!hit) return false;
  setParam(QStringLiteral("templateLibrary"), kept, true);
  if (params_.value(QStringLiteral("activeTemplateId")).toString() == id)
    setParam(QStringLiteral("activeTemplateId"), QString(), true);
  refreshLibraryList();
  refreshLibraryPreview();
  return true;
}

QVariantMap LocateMatchPanel::runBatchScoreboard(const QVariantMap& scoresById,
                                                 bool softFallback) {
  const QVariantList lib = normalizedLibrary(params_.value(QStringLiteral("templateLibrary")));
  QVariantMap scores = scoresById;
  if (softFallback) {
    const QVariantMap soft = softEstimateScores(
        lib, nodeId_.isEmpty() ? QStringLiteral("sieans") : nodeId_);
    for (auto it = soft.begin(); it != soft.end(); ++it) {
      if (!scores.contains(it.key())) scores.insert(it.key(), it.value());
    }
  }
  const double thr = params_.value(QStringLiteral("batchScoreThreshold"),
                                   params_.value(QStringLiteral("minScore"), 0.85))
                         .toDouble();
  QVariantMap board =
      buildBatchScoreboard(lib, scores, thr, params_.value(QStringLiteral("activeTemplateId")).toString());
  setParam(QStringLiteral("lastBatchScoreboard"), board, true);
  refreshScoreboardTable();
  if (libPreview_ && !board.value(QStringLiteral("summary")).toString().isEmpty()) {
    libPreview_->setText(QStringLiteral("记分板：%1").arg(board.value(QStringLiteral("summary")).toString()));
  }
  return board;
}

bool LocateMatchPanel::selectBestScoredTemplate(QString* error) {
  QVariantMap board = params_.value(QStringLiteral("lastBatchScoreboard")).toMap();
  if (board.value(QStringLiteral("rows")).toList().isEmpty())
    board = runBatchScoreboard({}, true);
  const QString bestId = board.value(QStringLiteral("bestId")).toString();
  if (bestId.isEmpty()) {
    if (error) *error = QStringLiteral("没有可选用的评分结果");
    return false;
  }
  QVariantMap best;
  for (const QVariant& v : board.value(QStringLiteral("rows")).toList()) {
    const QVariantMap row = v.toMap();
    if (row.value(QStringLiteral("id")).toString() == bestId) {
      best = row;
      break;
    }
  }
  const QString path = best.value(QStringLiteral("path")).toString().trimmed();
  if (path.isEmpty()) {
    if (error) *error = QStringLiteral("最优条目无路径");
    return false;
  }
  const double score = best.value(QStringLiteral("score")).toDouble();
  const double thr = params_.value(QStringLiteral("batchScoreThreshold"), 0.85).toDouble();
  if (best.value(QStringLiteral("score")).isValid() && score < thr && !workbenchIsHeadless()) {
    const auto ans = QMessageBox::question(
        this, QStringLiteral("选用最优"),
        QStringLiteral("最优「%1」=%2 低于阈值 %3，仍选用？")
            .arg(best.value(QStringLiteral("name")).toString())
            .arg(score, 0, 'f', 3)
            .arg(thr, 0, 'f', 3),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
    if (ans != QMessageBox::Yes) {
      if (error) *error = QStringLiteral("低于阈值未选用");
      return false;
    }
  }
  return selectLibraryEntry(bestId);
}

void LocateMatchPanel::refreshLibraryList() {
  if (!libList_) return;
  const QVariantList lib = normalizedLibrary(params_.value(QStringLiteral("templateLibrary")));
  const QString active = params_.value(QStringLiteral("activeTemplateId")).toString();
  const QString curPath = params_.value(QStringLiteral("templatePath")).toString().trimmed();
  const QString prevId = libList_->currentItem()
                             ? libList_->currentItem()->data(Qt::UserRole).toString()
                             : QString();
  libList_->blockSignals(true);
  libList_->clear();
  int restore = -1;
  for (int i = 0; i < lib.size(); ++i) {
    const QVariantMap e = lib[i].toMap();
    const QString eid = e.value(QStringLiteral("id")).toString();
    const QString name = e.value(QStringLiteral("name")).toString().isEmpty()
                             ? QStringLiteral("模板%1").arg(i + 1)
                             : e.value(QStringLiteral("name")).toString();
    const QString path = e.value(QStringLiteral("path")).toString();
    QString mark;
    if (!eid.isEmpty() && eid == active) {
      mark = QStringLiteral(" ★");
      restore = libList_->count();
    } else if (!path.isEmpty() && path == curPath) {
      mark = QStringLiteral(" ●");
      if (restore < 0) restore = libList_->count();
    }
    auto* item = new QListWidgetItem(name + mark);
    item->setData(Qt::UserRole, eid);
    item->setToolTip(path.isEmpty() ? QStringLiteral("(无路径)") : path);
    libList_->addItem(item);
    if (restore < 0 && eid == prevId) restore = libList_->count() - 1;
  }
  if (restore >= 0) libList_->setCurrentRow(restore);
  libList_->blockSignals(false);
  if (libCount_) libCount_->setText(QStringLiteral("%1 项").arg(lib.size()));
}

void LocateMatchPanel::refreshScoreboardTable() {
  const QVariantMap board = params_.value(QStringLiteral("lastBatchScoreboard")).toMap();
  if (boardSummary_)
    boardSummary_->setText(board.value(QStringLiteral("summary")).toString().isEmpty()
                               ? QStringLiteral("未评分")
                               : board.value(QStringLiteral("summary")).toString());
  if (!boardTable_) return;
  const QVariantList rows = board.value(QStringLiteral("rows")).toList();
  boardTable_->setRowCount(rows.size());
  for (int i = 0; i < rows.size(); ++i) {
    const QVariantMap row = rows[i].toMap();
    const bool pending = row.value(QStringLiteral("pending")).toBool();
    const QString scoreTxt =
        pending ? QStringLiteral("—")
                : QString::number(row.value(QStringLiteral("score")).toDouble(), 'f', 3);
    const QString judge = pending ? QStringLiteral("待评")
                                  : (row.value(QStringLiteral("ok")).toBool() ? QStringLiteral("OK")
                                                                             : QStringLiteral("NG"));
    const int rank = row.value(QStringLiteral("rank")).toInt();
    boardTable_->setItem(i, 0, new QTableWidgetItem(row.value(QStringLiteral("name")).toString()));
    boardTable_->setItem(i, 1, new QTableWidgetItem(scoreTxt));
    boardTable_->setItem(i, 2, new QTableWidgetItem(judge));
    boardTable_->setItem(i, 3, new QTableWidgetItem(rank > 0 ? QString::number(rank) : QStringLiteral("—")));
  }
}

void LocateMatchPanel::refreshLibraryPreview() {
  if (!libPreview_ || !libList_) return;
  const QString id = libList_->currentItem() ? libList_->currentItem()->data(Qt::UserRole).toString()
                                             : QString();
  const QVariantList lib = normalizedLibrary(params_.value(QStringLiteral("templateLibrary")));
  QVariantMap entry;
  for (const QVariant& v : lib) {
    if (v.toMap().value(QStringLiteral("id")).toString() == id) {
      entry = v.toMap();
      break;
    }
  }
  if (entry.isEmpty()) {
    libPreview_->setText(QStringLiteral("预览：选中库条目查看路径/备注"));
    libPreview_->setStyleSheet(QStringLiteral("color:#8ab;font-size:11px;padding:2px 0;"));
    return;
  }
  const QString path = entry.value(QStringLiteral("path")).toString();
  const bool active = entry.value(QStringLiteral("id")).toString() ==
                      params_.value(QStringLiteral("activeTemplateId")).toString();
  QString txt = QStringLiteral("预览「%1」%2\n路径：%3")
                    .arg(entry.value(QStringLiteral("name")).toString(),
                         active ? QStringLiteral(" · 当前选用") : QString(),
                         path.isEmpty() ? QStringLiteral("(无路径)") : path);
  if (!entry.value(QStringLiteral("note")).toString().isEmpty())
    txt += QStringLiteral("\n备注：%1").arg(entry.value(QStringLiteral("note")).toString());
  if (!path.isEmpty())
    txt += QFileInfo::exists(path) ? QStringLiteral("\n磁盘：存在")
                                   : QStringLiteral("\n磁盘：未找到（仍可引用方案内路径）");
  libPreview_->setText(txt);
  libPreview_->setStyleSheet(QStringLiteral("color:#9ad;font-size:11px;padding:2px 0;"));
}

void LocateMatchPanel::onAddLibraryClicked() {
  QString path = params_.value(QStringLiteral("templatePath")).toString().trimmed();
  if (path.isEmpty()) {
    if (workbenchIsHeadless()) return;
    path = QFileDialog::getOpenFileName(
        this, QStringLiteral("加入模板库"), workbenchTemplatesDir(),
        QStringLiteral("模板/图像 (*.png *.bmp *.jpg *.jpeg *.tif);;所有文件 (*)"));
    if (path.isEmpty()) return;
  }
  QString name = QFileInfo(path).completeBaseName();
  if (!workbenchIsHeadless()) {
    bool ok = false;
    name = QInputDialog::getText(this, QStringLiteral("加入模板库"), QStringLiteral("模板名称："),
                                 QLineEdit::Normal, name, &ok);
    if (!ok) return;
  }
  addLibraryEntry(path, name);
}

void LocateMatchPanel::onSelectLibraryClicked() {
  const QString id = libList_ && libList_->currentItem()
                         ? libList_->currentItem()->data(Qt::UserRole).toString()
                         : QString();
  if (id.isEmpty()) {
    if (!workbenchIsHeadless())
      QMessageBox::information(this, QStringLiteral("模板库"), QStringLiteral("请先选中一条模板"));
    return;
  }
  if (!selectLibraryEntry(id) && !workbenchIsHeadless())
    QMessageBox::warning(this, QStringLiteral("模板库"), QStringLiteral("该条目无路径"));
}

void LocateMatchPanel::onPreviewLibraryClicked() { refreshLibraryPreview(); }

void LocateMatchPanel::onRemoveLibraryClicked() {
  const QString id = libList_ && libList_->currentItem()
                         ? libList_->currentItem()->data(Qt::UserRole).toString()
                         : QString();
  if (id.isEmpty()) {
    if (!workbenchIsHeadless())
      QMessageBox::information(this, QStringLiteral("模板库"),
                               QStringLiteral("请先选中要移除的条目"));
    return;
  }
  if (!workbenchIsHeadless()) {
    const auto ans = QMessageBox::question(
        this, QStringLiteral("移除模板"),
        QStringLiteral("从模板库移除选中条目？\n（不删除磁盘文件）"),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
    if (ans != QMessageBox::Yes) return;
  }
  removeLibraryEntry(id);
}

void LocateMatchPanel::onBatchScoreClicked() { runBatchScoreboard({}, true); }

void LocateMatchPanel::onSelectBestClicked() {
  QString err;
  if (!selectBestScoredTemplate(&err) && !workbenchIsHeadless() && !err.isEmpty())
    QMessageBox::information(this, QStringLiteral("记分板"), err);
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
                       {QStringLiteral("locateAngle"), 0},
                       {QStringLiteral("filmstripPath"), QStringLiteral("/tmp/frame-a.png")}});
  if (panel.trendCount() < 1) fails << QStringLiteral("trend not recorded");
  panel.setLastResult({{QStringLiteral("locateOk"), 1},
                       {QStringLiteral("locateCount"), 1},
                       {QStringLiteral("locateScore"), 0.80},
                       {QStringLiteral("locateX"), 11},
                       {QStringLiteral("locateY"), 21},
                       {QStringLiteral("locateAngle"), 0},
                       {QStringLiteral("filmstripPath"), QStringLiteral("/tmp/frame-b.png")}});
  const QVariantMap jbag = panel.jumpTrendLocal(1);
  if (jbag.value(QStringLiteral("frame")).toString() != QLatin1String("/tmp/frame-b.png"))
    fails << QStringLiteral("spark jump frame");

  const QString pathA = path;
  const QString pathB = path + QStringLiteral(".alt.png");
  QImage alt(32, 32, QImage::Format_RGB888);
  alt.fill(QColor(10, 80, 10));
  alt.save(pathB);
  const QString idA = panel.addLibraryEntry(pathA, QStringLiteral("模板A"));
  const QString idB = panel.addLibraryEntry(pathB, QStringLiteral("模板B"));
  if (panel.libraryCount() != 2)
    fails << QStringLiteral("libraryCount=%1").arg(panel.libraryCount());
  if (idA.isEmpty() || idB.isEmpty() || idA == idB)
    fails << QStringLiteral("library ids");
  if (!panel.selectLibraryEntry(idA)) fails << QStringLiteral("select library A");
  if (panel.activeTemplateId() != idA) fails << QStringLiteral("activeTemplateId");
  if (panel.currentParams().value(QStringLiteral("templatePath")).toString() != pathA)
    fails << QStringLiteral("select path");
  const QVariantMap board = panel.runBatchScoreboard({}, true);
  const QVariantList rows = board.value(QStringLiteral("rows")).toList();
  if (rows.size() != 2) fails << QStringLiteral("scoreboard rows");
  if (board.value(QStringLiteral("bestId")).toString().isEmpty())
    fails << QStringLiteral("scoreboard bestId");
  int scored = 0;
  for (const QVariant& v : rows) {
    const QVariantMap r = v.toMap();
    if (!r.value(QStringLiteral("pending")).toBool()) {
      ++scored;
      const double sc = r.value(QStringLiteral("score")).toDouble();
      if (sc < 0.55 || sc > 0.98) fails << QStringLiteral("soft score range");
    }
  }
  if (scored != 2) fails << QStringLiteral("soft scores missing");
  QString bestErr;
  if (!panel.selectBestScoredTemplate(&bestErr))
    fails << (QStringLiteral("selectBest: ") + bestErr);
  if (panel.activeTemplateId() != board.value(QStringLiteral("bestId")).toString())
    fails << QStringLiteral("selectBest active");
  const QVariantList persisted =
      panel.currentParams().value(QStringLiteral("templateLibrary")).toList();
  if (persisted.size() != 2) fails << QStringLiteral("params library size");
  QVariantMap snapLib = panel.currentParams();
  if (!panel.removeLibraryEntry(idB) || panel.libraryCount() != 1)
    fails << QStringLiteral("remove library");
  panel.applySnapshot(snapLib);
  if (panel.libraryCount() != 2) fails << QStringLiteral("snapshot restore library");
  if (n.value(QStringLiteral("templateLibrary")).typeId() != QMetaType::QVariantList)
    fails << QStringLiteral("normalize library default");
  return fails;
}

}  // namespace sieans_qt
