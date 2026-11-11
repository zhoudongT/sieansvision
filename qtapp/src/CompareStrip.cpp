#include "CompareStrip.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QListWidget>
#include <QListWidgetItem>
#include <QAbstractItemModel>
#include <QAbstractItemView>
#include <QSettings>
#include <QTimer>
#include <QToolTip>
#include <QEvent>
#include <QMouseEvent>
#include <QColor>
#include <QBrush>
#include <QIcon>
#include <QPixmap>
#include <QImage>
#include <QFileInfo>
#include <QFile>
#include <QDir>
#include <QTemporaryDir>
#include <QColor>
#include <QSize>
#include <QApplication>

namespace sieans_qt {
namespace {

constexpr int kMaxComparePaths = 6;
constexpr int kThumb = 72;

QStringList cleanComparePaths(const QStringList& in) {
  QStringList out;
  for (const QString& p : in) {
    const QString t = p.trimmed();
    if (t.isEmpty() || out.contains(t)) continue;
    out << t;
    if (out.size() >= kMaxComparePaths) break;
  }
  return out;
}

int indexOfPath(const QStringList& paths, const QString& token) {
  const QString t = token.trimmed();
  if (t.isEmpty()) return -1;
  const int exact = paths.indexOf(t);
  if (exact >= 0) return exact;
  const QString base = QFileInfo(t).fileName();
  for (int i = 0; i < paths.size(); ++i) {
    const QString name = QFileInfo(paths.at(i)).fileName();
    if (name == base || name == t) return i;
  }
  for (int i = 0; i < paths.size(); ++i) {
    if (paths.at(i).contains(t) || QFileInfo(paths.at(i)).fileName().contains(base))
      return i;
  }
  return -1;
}

QIcon thumbIcon(const QString& path) {
  QImage img(path);
  if (img.isNull()) {
    QImage ph(kThumb, kThumb, QImage::Format_RGB32);
    ph.fill(QColor(40, 48, 58));
    return QIcon(QPixmap::fromImage(ph));
  }
  return QIcon(QPixmap::fromImage(
      img.scaled(kThumb, kThumb, Qt::KeepAspectRatio, Qt::SmoothTransformation)));
}

}  // namespace

CompareStrip::CompareStrip(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("compareThumbStrip"));
  setFixedWidth(96);
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(4, 4, 4, 4);
  lay->setSpacing(4);
  auto* head = new QHBoxLayout;
  head->setSpacing(4);
  title_ = new QLabel(QStringLiteral("对比"));
  title_->setObjectName(QStringLiteral("compareThumbTitle"));
  title_->setStyleSheet(
      QStringLiteral("color:#9ec9f0;font-size:11px;font-weight:700;"));
  head->addWidget(title_, 1);
  clearBtn_ = new QPushButton(QStringLiteral("×"));
  clearBtn_->setObjectName(QStringLiteral("compareThumbClear"));
  clearBtn_->setFixedSize(20, 20);
  clearBtn_->setToolTip(QStringLiteral("清除多选对比"));
  connect(clearBtn_, &QPushButton::clicked, this, [this]() {
    clear();
    emit clearRequested();
  });
  head->addWidget(clearBtn_);
  lay->addLayout(head);
  auto* tools = new QHBoxLayout;
  tools->setSpacing(2);
  lockBtn_ = new QPushButton(QStringLiteral("🔓"));
  lockBtn_->setObjectName(QStringLiteral("compareThumbLock"));
  lockBtn_->setFixedSize(20, 20);
  lockBtn_->setCheckable(true);
  lockBtn_->setToolTip(QStringLiteral("锁定对比序（禁止拖拽）"));
  connect(lockBtn_, &QPushButton::toggled, this, [this](bool on) { setOrderLocked(on, true); });
  tools->addWidget(lockBtn_);
  resetBtn_ = new QPushButton(QStringLiteral("↺"));
  resetBtn_->setObjectName(QStringLiteral("compareThumbReset"));
  resetBtn_->setFixedSize(20, 20);
  resetBtn_->setToolTip(QStringLiteral("复位对比序到进入时顺序"));
  connect(resetBtn_, &QPushButton::clicked, this, [this]() { resetOrder(); });
  tools->addWidget(resetBtn_);
  undoBtn_ = new QPushButton(QStringLiteral("↶"));
  undoBtn_->setObjectName(QStringLiteral("compareThumbUndo"));
  undoBtn_->setFixedSize(20, 20);
  undoBtn_->setToolTip(QStringLiteral("撤销对比序（复位/重排）"));
  undoBtn_->setEnabled(false);
  connect(undoBtn_, &QPushButton::clicked, this, [this]() { undoOrder(); });
  tools->addWidget(undoBtn_);
  undoDepth_ = new QLabel(QStringLiteral("0"));
  undoDepth_->setObjectName(QStringLiteral("compareThumbUndoDepth"));
  undoDepth_->setFixedHeight(16);
  undoDepth_->setMinimumWidth(14);
  undoDepth_->setAlignment(Qt::AlignCenter);
  undoDepth_->setStyleSheet(
      QStringLiteral("background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;"
                     "border-radius:3px;padding:0 3px;font-size:9px;font-weight:700;"));
  undoDepth_->setToolTip(QStringLiteral("撤销栈深度"));
  tools->addWidget(undoDepth_);
  lockBadge_ = new QLabel(QStringLiteral("未锁"));
  lockBadge_->setObjectName(QStringLiteral("compareThumbLockBadge"));
  lockBadge_->setFixedHeight(16);
  lockBadge_->setAlignment(Qt::AlignCenter);
  lockBadge_->setCursor(Qt::PointingHandCursor);
  lockBadge_->installEventFilter(this);
  tools->addWidget(lockBadge_);
  undoClearBtn_ = new QPushButton(QStringLiteral("⊘"));
  undoClearBtn_->setObjectName(QStringLiteral("compareThumbUndoClear"));
  undoClearBtn_->setFixedSize(20, 20);
  undoClearBtn_->setEnabled(false);
  undoClearBtn_->setToolTip(QStringLiteral("短按提示 · 长按清空撤销栈 · 无硬件"));
  connect(undoClearBtn_, &QPushButton::pressed, this, [this]() {
    if (!undo_clear_timer_) {
      undo_clear_timer_ = new QTimer(this);
      undo_clear_timer_->setSingleShot(true);
      connect(undo_clear_timer_, &QTimer::timeout, this, [this]() { fireUndoClearLongPress(); });
    }
    undo_clear_timer_->start(undo_clear_long_ms_);
  });
  connect(undoClearBtn_, &QPushButton::released, this, [this]() {
    if (undo_clear_timer_ && undo_clear_timer_->isActive()) {
      undo_clear_timer_->stop();
      undoClearShortPress();
    }
  });
  tools->addWidget(undoClearBtn_);
  tools->addStretch(1);
  lay->addLayout(tools);
  lock_badge_timer_ = new QTimer(this);
  lock_badge_timer_->setSingleShot(true);
  connect(lock_badge_timer_, &QTimer::timeout, this, &CompareStrip::lockBadgeClick);
  list_ = new QListWidget;
  list_->setObjectName(QStringLiteral("compareThumbList"));
  list_->setViewMode(QListWidget::IconMode);
  list_->setFlow(QListWidget::TopToBottom);
  list_->setWrapping(false);
  list_->setMovement(QListWidget::Static);
  list_->setResizeMode(QListWidget::Adjust);
  list_->setIconSize(QSize(kThumb, kThumb));
  list_->setSpacing(4);
  list_->setToolTip(QStringLiteral("对比缩略 · 单击定位胶片 · 拖拽重排 · 锁序后禁止拖拽 · 无硬件"));
  list_->setStyleSheet(
      QStringLiteral("QListWidget{background:#1c1e22;border:1px solid #3a5a7a;"
                     "border-radius:2px;}"
                     "QListWidget::item{border:1px solid #3a5a7a;border-radius:2px;"
                     "padding:2px;}"
                     "QListWidget::item:selected{border:2px solid #6eb6ff;"
                     "background:#1c2a3a;}"));
  connect(list_, &QListWidget::itemClicked, this, [this](QListWidgetItem* item) {
    if (!item) return;
    const QString p = item->data(Qt::UserRole).toString();
    if (p.isEmpty()) return;
    active_ = p;
    emit pathActivated(p);
  });
  if (list_->model()) {
    connect(list_->model(), &QAbstractItemModel::rowsMoved, this, [this]() { onRowsMoved(); });
  }
  applyLockChrome();
  lay->addWidget(list_, 1);
  hide();
}

void CompareStrip::setPaths(const QStringList& paths, const QString& active,
                            bool asBaseline) {
  paths_ = cleanComparePaths(paths);
  const int hit = indexOfPath(paths_, active);
  active_ = hit >= 0 ? paths_.at(hit) : (paths_.isEmpty() ? QString() : paths_.first());
  if (asBaseline) {
    baseline_paths_ = paths_;
    order_undo_.clear();
    undo_should_relock_ = false;
  }
  rebuild();
  emit pathsChanged();
}

bool CompareStrip::addPath(const QString& path) {
  const QString t = path.trimmed();
  if (t.isEmpty()) return false;
  const int have = indexOfPath(paths_, t);
  if (have >= 0) return activatePath(paths_.at(have), false);
  if (paths_.size() >= kMaxComparePaths) return false;
  paths_ << t;
  active_ = t;
  rebuild();
  emit pathsChanged();
  return true;
}

bool CompareStrip::activatePath(const QString& path, bool emitSignal) {
  const int hit = indexOfPath(paths_, path);
  if (hit < 0) return false;
  active_ = paths_.at(hit);
  if (list_) list_->setCurrentRow(hit);
  if (emitSignal) emit pathActivated(active_);
  return true;
}

void CompareStrip::clear() {
  if (paths_.isEmpty() && isHidden()) return;
  paths_.clear();
  active_.clear();
  baseline_paths_.clear();
  order_undo_.clear();
  rebuild();
  emit pathsChanged();
}

void CompareStrip::pushOrderUndo() {
  if (order_undo_.size() >= 16) order_undo_.removeFirst();
  order_undo_.push_back(paths_);
}

void CompareStrip::applyLockChrome() {
  if (lockBtn_) {
    lockBtn_->blockSignals(true);
    lockBtn_->setChecked(order_locked_);
    lockBtn_->setText(order_locked_ ? QStringLiteral("🔒") : QStringLiteral("🔓"));
    lockBtn_->blockSignals(false);
    lockBtn_->setToolTip(order_locked_ ? QStringLiteral("已锁定对比序")
                                       : QStringLiteral("锁定对比序（禁止拖拽）"));
  }
  if (list_) {
    if (order_locked_) {
      list_->setMovement(QListWidget::Static);
      list_->setDragDropMode(QAbstractItemView::NoDragDrop);
    } else {
      list_->setMovement(QListWidget::Snap);
      list_->setDragDropMode(QAbstractItemView::InternalMove);
      list_->setDefaultDropAction(Qt::MoveAction);
    }
  }
  if (undoBtn_) undoBtn_->setEnabled(!order_undo_.isEmpty());
  if (undoDepth_) undoDepth_->setText(QString::number(order_undo_.size()));
  if (undoClearBtn_) {
    undoClearBtn_->setEnabled(!order_undo_.isEmpty());
    undoClearBtn_->setToolTip(
        QStringLiteral("短按提示 · 长按清空（%1ms · 栈%2）· 无硬件")
            .arg(undo_clear_long_ms_)
            .arg(order_undo_.size()));
  }
  if (lockBadge_) {
    if (order_locked_) {
      lockBadge_->setText(QStringLiteral("已锁"));
      lockBadge_->setStyleSheet(
          QStringLiteral("background:#3a3420;color:#e0b84a;border:1px solid #e0b84a;"
                         "border-radius:3px;padding:0 4px;font-size:9px;font-weight:700;"));
      lockBadge_->setToolTip(QStringLiteral("已锁 · 单击解锁 · 双击复位并解锁"));
    } else {
      lockBadge_->setText(QStringLiteral("未锁"));
      lockBadge_->setStyleSheet(
          QStringLiteral("background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;"
                         "border-radius:3px;padding:0 4px;font-size:9px;font-weight:600;"));
      lockBadge_->setToolTip(QStringLiteral("未锁 · 单击锁定 · 双击复位并解锁"));
    }
  }
  if (resetBtn_) {
    resetBtn_->setToolTip(order_locked_
                              ? QStringLiteral("复位对比序到进入时顺序（锁序下仍可用）")
                              : QStringLiteral("复位对比序到进入时顺序"));
  }
}

void CompareStrip::setOrderLocked(bool locked, bool persist) {
  if (order_locked_ == locked) {
    applyLockChrome();
    if (persist) saveOrderLockPref(order_locked_);
    return;
  }
  order_locked_ = locked;
  applyLockChrome();
  rebuild();
  if (persist) saveOrderLockPref(order_locked_);
  emit lockChanged(order_locked_);
}

bool CompareStrip::moveRow(int from, int to) {
  if (order_locked_) return false;
  if (from < 0 || to < 0 || from >= paths_.size() || to >= paths_.size() || from == to)
    return false;
  pushOrderUndo();
  paths_.move(from, to);
  rebuild();
  emit pathsChanged();
  emit pathsReordered(paths_);
  return true;
}

bool CompareStrip::resetOrder() {
  if (paths_ == baseline_paths_ || baseline_paths_.isEmpty()) return false;
  pushOrderUndo();
  paths_ = baseline_paths_;
  if (!active_.isEmpty() && !paths_.contains(active_) && !paths_.isEmpty())
    active_ = paths_.first();
  rebuild();
  emit pathsChanged();
  emit pathsReordered(paths_);
  return true;
}

bool CompareStrip::undoOrder() {
  const bool relock = undo_should_relock_;
  undo_should_relock_ = false;
  bool changed = false;
  if (!order_undo_.isEmpty()) {
    const QStringList prev = order_undo_.takeLast();
    changed = (prev != paths_);
    if (changed) {
      paths_ = prev;
      if (!active_.isEmpty() && !paths_.contains(active_) && !paths_.isEmpty())
        active_ = paths_.first();
      rebuild();
      emit pathsChanged();
      emit pathsReordered(paths_);
    } else {
      applyLockChrome();
    }
  }
  bool relocked = false;
  if (relock) {
    setOrderLocked(true, true);
    relocked = true;
  }
  return changed || relocked;
}

void CompareStrip::onRowsMoved() {
  if (suppress_reorder_ || !list_ || order_locked_) return;
  QStringList next;
  for (int i = 0; i < list_->count(); ++i) {
    auto* it = list_->item(i);
    if (!it) continue;
    const QString p = it->data(Qt::UserRole).toString();
    if (!p.isEmpty()) next << p;
  }
  if (next == paths_ || next.isEmpty()) return;
  pushOrderUndo();
  paths_ = next;
  applyLockChrome();
  emit pathsChanged();
  emit pathsReordered(paths_);
}

void CompareStrip::rebuild() {
  if (title_) {
    QString text = paths_.isEmpty() ? QStringLiteral("对比")
                                    : QStringLiteral("对比·%1").arg(paths_.size());
    if (order_locked_ && !paths_.isEmpty()) text += QStringLiteral("🔒");
    title_->setText(text);
  }
  applyLockChrome();
  if (list_) {
    suppress_reorder_ = true;
    list_->clear();
    int current = -1;
    for (int i = 0; i < paths_.size(); ++i) {
      const QString& fp = paths_.at(i);
      auto* item = new QListWidgetItem(thumbIcon(fp), thumbLabelFor(fp));
      item->setData(Qt::UserRole, fp);
      const QString badge = pathBadge(fp);
      QString tip = fp;
      if (!badge.isEmpty()) tip += QStringLiteral("\n测量判定：%1").arg(badge);
      item->setToolTip(tip);
      if (badge == QLatin1String("NG"))
        item->setForeground(QBrush(QColor(QStringLiteral("#c62828"))));
      else if (badge == QLatin1String("OK"))
        item->setForeground(QBrush(QColor(QStringLiteral("#2e7d32"))));
      list_->addItem(item);
      if (fp == active_) current = i;
    }
    if (current >= 0) list_->setCurrentRow(current);
    suppress_reorder_ = false;
  }
  setVisible(!paths_.isEmpty());
}

void CompareStrip::setCompareSettings(QSettings* settings) { settings_ = settings; }

QSettings* CompareStrip::compareSettings() const { return settings_; }

void CompareStrip::saveOrderLockPref(bool locked) {
  QSettings local(QStringLiteral("SIEANS"), QStringLiteral("VisionDesktop"));
  QSettings* s = settings_ ? settings_ : &local;
  s->setValue(QStringLiteral("film/compareOrderLocked"), locked);
  s->sync();
}

bool CompareStrip::loadOrderLockPref() {
  QSettings local(QStringLiteral("SIEANS"), QStringLiteral("VisionDesktop"));
  QSettings* s = settings_ ? settings_ : &local;
  const QString raw = s->value(QStringLiteral("film/compareOrderLocked"), false).toString().trimmed().toLower();
  const bool locked = (raw == QLatin1String("1") || raw == QLatin1String("true") ||
                       raw == QLatin1String("yes"));
  setOrderLocked(locked, false);
  return locked;
}

bool CompareStrip::loadComparePrefs() {
  QSettings local(QStringLiteral("SIEANS"), QStringLiteral("VisionDesktop"));
  QSettings* s = settings_ ? settings_ : &local;
  const int ms = s->value(QStringLiteral("film/undoClearLongMs"), 650).toInt();
  setUndoClearLongMs(ms, false);
  return loadOrderLockPref();
}

void CompareStrip::lockBadgeClick() {
  if (lock_badge_timer_ && lock_badge_timer_->isActive()) lock_badge_timer_->stop();
  setOrderLocked(!order_locked_, true);
}

void CompareStrip::lockBadgeDoubleClick() {
  if (lock_badge_timer_ && lock_badge_timer_->isActive()) lock_badge_timer_->stop();
  const bool was_locked = order_locked_;
  if (!paths_.isEmpty()) {
    if (paths_ != baseline_paths_ && !baseline_paths_.isEmpty())
      resetOrder();
    else
      pushOrderUndo();
  }
  undo_should_relock_ = was_locked;
  setOrderLocked(false, true);
}

bool CompareStrip::clearOrderUndo() {
  if (order_undo_.isEmpty()) {
    applyLockChrome();
    last_undo_clear_tip_ = QStringLiteral("撤销栈为空");
    return false;
  }
  order_undo_.clear();
  applyLockChrome();
  last_undo_clear_tip_ = QStringLiteral("已清空撤销栈");
  return true;
}

bool CompareStrip::fireUndoClearLongPress() {
  if (undo_clear_timer_ && undo_clear_timer_->isActive()) undo_clear_timer_->stop();
  return clearOrderUndo();
}

QString CompareStrip::undoClearShortPress() {
  if (undo_clear_timer_ && undo_clear_timer_->isActive()) undo_clear_timer_->stop();
  last_undo_clear_tip_ =
      order_undo_.isEmpty()
          ? QStringLiteral("撤销栈为空 · 长按时长 %1ms").arg(undo_clear_long_ms_)
          : QStringLiteral("长按 ⊘ 清空（%1ms · 栈 %2）")
                .arg(undo_clear_long_ms_)
                .arg(order_undo_.size());
  if (undoClearBtn_) undoClearBtn_->setToolTip(last_undo_clear_tip_);
  return last_undo_clear_tip_;
}

int CompareStrip::setUndoClearLongMs(int ms, bool persist) {
  undo_clear_long_ms_ = qBound(300, ms > 0 ? ms : 650, 3000);
  applyLockChrome();
  if (persist) {
    QSettings local(QStringLiteral("SIEANS"), QStringLiteral("VisionDesktop"));
    QSettings* s = settings_ ? settings_ : &local;
    s->setValue(QStringLiteral("film/undoClearLongMs"), undo_clear_long_ms_);
    s->sync();
  }
  return undo_clear_long_ms_;
}

QString CompareStrip::lockBadgeText() const {
  return lockBadge_ ? lockBadge_->text() : QString();
}

void CompareStrip::setPathBadges(const QHash<QString, QString>& badges) {
  path_badges_.clear();
  for (auto it = badges.begin(); it != badges.end(); ++it) {
    const QString k = it.key().trimmed();
    if (k.isEmpty()) continue;
    const QString v = it.value().trimmed().toUpper();
    if (v == QLatin1String("OK") || v == QLatin1String("PASS") || v == QLatin1String("1") ||
        v == QLatin1String("TRUE"))
      path_badges_.insert(k, QStringLiteral("OK"));
    else if (v == QLatin1String("NG") || v == QLatin1String("FAIL") || v == QLatin1String("0") ||
             v == QLatin1String("FALSE"))
      path_badges_.insert(k, QStringLiteral("NG"));
    else if (!v.isEmpty())
      path_badges_.insert(k, v.left(8));
  }
  rebuild();
}

QString CompareStrip::pathBadge(const QString& path) const {
  const QString t = path.trimmed();
  if (path_badges_.contains(t)) return path_badges_.value(t);
  const QString base = QFileInfo(t).fileName();
  for (auto it = path_badges_.begin(); it != path_badges_.end(); ++it) {
    if (QFileInfo(it.key()).fileName() == base) return it.value();
  }
  return {};
}

QString CompareStrip::thumbLabelFor(const QString& path) const {
  const QString leaf = QFileInfo(path).fileName();
  const QString badge = pathBadge(path);
  if (badge.isEmpty()) return leaf;
  return QStringLiteral("[%1] %2").arg(badge, leaf);
}

bool CompareStrip::eventFilter(QObject* obj, QEvent* event) {
  if (obj == lockBadge_ && lockBadge_) {
    if (event->type() == QEvent::MouseButtonPress) {
      auto* me = static_cast<QMouseEvent*>(event);
      if (me->button() == Qt::LeftButton) {
        if (lock_badge_timer_) lock_badge_timer_->start(280);
        return true;
      }
    }
    if (event->type() == QEvent::MouseButtonDblClick) {
      auto* me = static_cast<QMouseEvent*>(event);
      if (me->button() == Qt::LeftButton) {
        lockBadgeDoubleClick();
        return true;
      }
    }
  }
  return QWidget::eventFilter(obj, event);
}

QStringList CompareStrip::compareSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  if (!qApp) {
    fails << QStringLiteral("no-qapp");
    return fails;
  }

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (!tmp.isValid()) return fails;
  const QString a = tmp.filePath(QStringLiteral("frame-a.png"));
  const QString b = tmp.filePath(QStringLiteral("frame-b.png"));
  const QString c = tmp.filePath(QStringLiteral("frame-c.png"));
  {
    QImage ia(16, 16, QImage::Format_RGB888);
    ia.fill(QColor(200, 40, 40));
    check("write-a", ia.save(a));
    QImage ib(16, 16, QImage::Format_RGB888);
    ib.fill(QColor(40, 200, 40));
    check("write-b", ib.save(b));
    QImage ic(16, 16, QImage::Format_RGB888);
    ic.fill(QColor(40, 40, 200));
    check("write-c", ic.save(c));
  }

  CompareStrip strip;
  check("hidden-empty", strip.isHidden() && strip.isEmpty());
  strip.setPaths({a, b}, b);
  check("count2", strip.count() == 2, QString::number(strip.count()));
  check("visible-2", !strip.isHidden());
  check("title", strip.findChild<QLabel*>(QStringLiteral("compareThumbTitle")) &&
                     strip.findChild<QLabel*>(QStringLiteral("compareThumbTitle"))
                         ->text()
                         .contains(QStringLiteral("2")),
        strip.findChild<QLabel*>(QStringLiteral("compareThumbTitle"))
            ? strip.findChild<QLabel*>(QStringLiteral("compareThumbTitle"))->text()
            : QStringLiteral("no-title"));
  check("active-b", strip.activePath() == b, strip.activePath());
  check("activate-a", strip.activatePath(QStringLiteral("frame-a.png"), false));
  check("active-a", QFileInfo(strip.activePath()).fileName() == QLatin1String("frame-a.png"),
        strip.activePath());
  check("add-c", strip.addPath(c));
  check("count3", strip.count() == 3, QString::number(strip.count()));
  check("add-dup", strip.addPath(a) && strip.count() == 3);

  strip.setPaths({a, b, c}, a);
  check("baseline3", strip.baselinePaths() == QStringList({a, b, c}));
  check("unlocked", !strip.isOrderLocked());
  check("reorder", strip.moveRow(2, 0));
  check("reordered", strip.paths().first() == c,
        strip.paths().join(QLatin1Char(',')));
  check("undo-depth", strip.orderUndoDepth() == 1,
        QString::number(strip.orderUndoDepth()));
  strip.setOrderLocked(true);
  check("locked", strip.isOrderLocked());
  check("lock-blocks", !strip.moveRow(0, 2));
  check("lock-keeps", strip.paths().first() == c, strip.paths().join(QLatin1Char(',')));
  check("lock-title",
        strip.findChild<QLabel*>(QStringLiteral("compareThumbTitle")) &&
            strip.findChild<QLabel*>(QStringLiteral("compareThumbTitle"))
                ->text()
                .contains(QStringLiteral("🔒")));
  strip.setOrderLocked(false);
  check("undo", strip.undoOrder());
  check("undone", strip.paths() == QStringList({a, b, c}),
        strip.paths().join(QLatin1Char(',')));
  check("undo-empty", !strip.undoOrder());
  check("reorder2", strip.moveRow(0, 2));
  check("reset", strip.resetOrder());
  check("reset-baseline", strip.paths() == QStringList({a, b, c}),
        strip.paths().join(QLatin1Char(',')));
  check("reset-undo", strip.undoOrder());
  check("reset-undone", strip.paths() == QStringList({b, c, a}),
        strip.paths().join(QLatin1Char(',')));

  // wave257: lock pref, badge double-click reset, long-press undo-clear (headless slots).
  // Temp ini only — never write the user SIEANS/VisionDesktop store.
  const QString ini = tmp.filePath(QStringLiteral("compare-pref.ini"));
  QSettings prefs(ini, QSettings::IniFormat);
  strip.setCompareSettings(&prefs);
  {
    CompareStrip prefStrip;
    prefStrip.setCompareSettings(&prefs);
    prefStrip.setPaths({a, b, c}, a);
    check("pref-unlocked", !prefStrip.isOrderLocked());
    prefStrip.setOrderLocked(true, true);
    prefStrip.setUndoClearLongMs(400, true);
    prefs.sync();
    check("pref-written-lock",
          prefs.value(QStringLiteral("film/compareOrderLocked")).toBool() ||
              prefs.value(QStringLiteral("film/compareOrderLocked")).toString().toLower() ==
                  QLatin1String("true"));
    check("pref-written-ms",
          prefs.value(QStringLiteral("film/undoClearLongMs")).toInt() == 400,
          prefs.value(QStringLiteral("film/undoClearLongMs")).toString());
    CompareStrip loaded;
    loaded.setCompareSettings(&prefs);
    check("pref-load-lock", loaded.loadOrderLockPref() && loaded.isOrderLocked());
    check("pref-load-ms", loaded.loadComparePrefs() && loaded.undoClearLongMs() == 400,
          QString::number(loaded.undoClearLongMs()));
    loaded.setOrderLocked(false, true);
  }
  strip.setPaths({a, b, c}, a);
  check("badge-unlocked", strip.lockBadgeText() == QStringLiteral("未锁"), strip.lockBadgeText());
  check("reorder-for-dbl", strip.moveRow(2, 0) && strip.paths().first() == c);
  strip.setOrderLocked(true, false);
  check("badge-locked", strip.lockBadgeText() == QStringLiteral("已锁"), strip.lockBadgeText());
  strip.lockBadgeDoubleClick();
  check("dbl-unlocked", !strip.isOrderLocked());
  check("dbl-reset", strip.paths() == QStringList({a, b, c}),
        strip.paths().join(QLatin1Char(',')));
  check("dbl-undo-depth", strip.orderUndoDepth() >= 1,
        QString::number(strip.orderUndoDepth()));
  check("dbl-undo-relock", strip.undoOrder() && strip.isOrderLocked());
  check("dbl-undo-order", strip.paths().first() == c, strip.paths().join(QLatin1Char(',')));
  strip.setOrderLocked(false, false);
  const int depth = strip.orderUndoDepth();
  check("short-press-keeps",
        !strip.undoClearShortPress().isEmpty() && strip.orderUndoDepth() == depth);
  check("long-press-clear", strip.fireUndoClearLongPress());
  check("stack-cleared", strip.orderUndoDepth() == 0,
        QString::number(strip.orderUndoDepth()));
  check("long-press-empty", !strip.fireUndoClearLongPress());
  strip.lockBadgeClick();
  check("lock-click-toggle", strip.isOrderLocked());
  strip.lockBadgeClick();

  QStringList many;
  for (int i = 0; i < 8; ++i) {
    const QString p = tmp.filePath(QStringLiteral("cap-%1.png").arg(i));
    QImage im(8, 8, QImage::Format_RGB888);
    im.fill(QColor(20 + i * 20, 40, 60));
    im.save(p);
    many << p;
  }
  strip.setPaths(many);
  check("cap6", strip.count() == 6, QString::number(strip.count()));
  check("cap-add-rejected", !strip.addPath(tmp.filePath(QStringLiteral("overflow.png"))));
  strip.clear();
  check("cleared", strip.isEmpty() && strip.isHidden());
  return fails;
}

}  // namespace sieans_qt
