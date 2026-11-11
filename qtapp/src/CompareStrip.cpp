#include "CompareStrip.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QListWidget>
#include <QListWidgetItem>
#include <QAbstractItemModel>
#include <QAbstractItemView>
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
  connect(lockBtn_, &QPushButton::toggled, this, [this](bool on) { setOrderLocked(on); });
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
  tools->addStretch(1);
  lay->addLayout(tools);
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

void CompareStrip::setPaths(const QStringList& paths, const QString& active) {
  paths_ = cleanComparePaths(paths);
  const int hit = indexOfPath(paths_, active);
  active_ = hit >= 0 ? paths_.at(hit) : (paths_.isEmpty() ? QString() : paths_.first());
  baseline_paths_ = paths_;
  order_undo_.clear();
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
}

void CompareStrip::setOrderLocked(bool locked) {
  if (order_locked_ == locked) {
    applyLockChrome();
    return;
  }
  order_locked_ = locked;
  applyLockChrome();
  rebuild();
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
  if (order_undo_.isEmpty()) return false;
  paths_ = order_undo_.takeLast();
  if (!active_.isEmpty() && !paths_.contains(active_) && !paths_.isEmpty())
    active_ = paths_.first();
  rebuild();
  emit pathsChanged();
  emit pathsReordered(paths_);
  return true;
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
      auto* item = new QListWidgetItem(thumbIcon(fp), QFileInfo(fp).fileName());
      item->setData(Qt::UserRole, fp);
      item->setToolTip(fp);
      list_->addItem(item);
      if (fp == active_) current = i;
    }
    if (current >= 0) list_->setCurrentRow(current);
    suppress_reorder_ = false;
  }
  setVisible(!paths_.isEmpty());
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
