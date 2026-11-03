#include "FilmstripBar.hpp"

#include <QCheckBox>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QIcon>
#include <QLabel>
#include <QListWidget>
#include <QPixmap>
#include <QImage>
#include <QPainter>
#include <QPushButton>
#include <QVBoxLayout>
#include <QKeyEvent>
#include <QEvent>
#include <QApplication>
#include <QWidget>
#include <QWheelEvent>
#include <QScrollBar>

namespace sieans_qt {
namespace {
constexpr int kThumbW = 80;
constexpr int kThumbH = 52;
}  // namespace

FilmstripBar::FilmstripBar(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("filmstripBar"));
  setStatusTip(QStringLiteral("胶片条 · ←→/Ctrl+←→ Home/End/PgUp/PgDn · 0/A/1-9 跳转 · Space 自动切换 · F5/F9 运行全部 · Insert 添加 · F7 文件夹 · Del"));
  setFocusPolicy(Qt::StrongFocus);
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(6, 2, 6, 4);
  root->setSpacing(2);

  auto* head = new QHBoxLayout;
  head->setSpacing(6);
  countLabel_ = new QLabel(QStringLiteral("图像源 (0/0)"));
  countLabel_->setStyleSheet(QStringLiteral("color:#e8e8e8;font-weight:600;"));
  countLabel_->setToolTip(QStringLiteral("←→/Ctrl+←→ Home/End/PgUp/PgDn/滚轮 · 0/A/1-9 跳转 · Del 删除 · Ctrl+A 全选 · 拖拽重排"));
  status_ = new QLabel(QStringLiteral("本地图像"));
  status_->setObjectName(QStringLiteral("muted"));
  autoSwitch_ = new QCheckBox(QStringLiteral("自动切换"));
  autoSwitch_->setToolTip(QStringLiteral("连续运行时切到下一张本地图 · Space/F6"));
  auto* runAll = new QPushButton(QStringLiteral("运行全部"));
  runAll->setToolTip(QStringLiteral("运行全部本地图 · F5/F9"));
  runAll->setStatusTip(QStringLiteral("胶片 · 运行全部 · F5/F9"));
  auto* add = new QPushButton(QStringLiteral("+"));
  add->setToolTip(QStringLiteral("添加图像 · Insert"));
  add->setFixedWidth(28);
  auto* folder = new QPushButton(QStringLiteral("文件夹"));
  folder->setToolTip(QStringLiteral("添加图像文件夹 · F7"));
  auto* prev = new QPushButton(QStringLiteral("◀"));
  prev->setToolTip(QStringLiteral("上一张 · ←"));
  prev->setFixedWidth(28);
  auto* next = new QPushButton(QStringLiteral("▶"));
  next->setToolTip(QStringLiteral("下一张 · →"));
  next->setFixedWidth(28);
  auto* del = new QPushButton(QStringLiteral("删除"));
  del->setToolTip(QStringLiteral("删除选中 · Del · Ctrl+Del 清空"));
  head->addWidget(countLabel_);
  head->addWidget(status_, 1);
  head->addWidget(autoSwitch_);
  head->addWidget(runAll);
  head->addWidget(prev);
  head->addWidget(next);
  head->addWidget(add);
  head->addWidget(folder);
  head->addWidget(del);
  root->addLayout(head);

  list_ = new QListWidget;
  list_->setObjectName(QStringLiteral("filmstripList"));
  list_->setViewMode(QListView::IconMode);
  list_->setFlow(QListView::LeftToRight);
  list_->setWrapping(false);
  list_->setMovement(QListView::Snap);  // drag-reorder thumbs
  list_->setDragDropMode(QAbstractItemView::InternalMove);
  list_->setDefaultDropAction(Qt::MoveAction);
  list_->setResizeMode(QListView::Adjust);
  list_->setIconSize(QSize(kThumbW, kThumbH));
  list_->setGridSize(QSize(kThumbW + 14, kThumbH + 18));
  list_->setFixedHeight(kThumbH + 22);
  list_->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
  list_->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
  list_->setStatusTip(QStringLiteral("胶片 · ←→ Home/End/PgUp/PgDn · 0/A/1-9 · Space/F6 · F5/F9 运行全部 · Insert 添加 · F7 文件夹 · Del"));
  list_->setSpacing(2);
  list_->setSelectionMode(QAbstractItemView::SingleSelection);
  root->addWidget(list_);

  connect(add, &QPushButton::clicked, this, &FilmstripBar::addImagesRequested);
  connect(folder, &QPushButton::clicked, this, &FilmstripBar::addFolderRequested);
  connect(runAll, &QPushButton::clicked, this, &FilmstripBar::runAllRequested);
  connect(prev, &QPushButton::clicked, this, &FilmstripBar::selectPrev);
  connect(next, &QPushButton::clicked, this, &FilmstripBar::selectNext);
  connect(del, &QPushButton::clicked, this, [this]() {
    if (index_ < 0 || index_ >= paths_.size()) return;
    paths_.removeAt(index_);
    const int next = qMin(index_, paths_.size() - 1);
    rebuildThumbs();
    if (next >= 0) selectIndex(next, true);
    else {
      index_ = -1;
      refreshCount();
    }
  });
  connect(list_, &QListWidget::currentRowChanged, this, [this](int row) {
    if (rebuilding_ || row < 0 || row >= paths_.size()) return;
    // Keep N/M · WxH · name via selectIndex (rebuilding_ guards recursion)
    selectIndex(row, true);
  });
  connect(list_->model(), &QAbstractItemModel::rowsMoved, this,
          [this](const QModelIndex&, int, int, const QModelIndex&, int) {
            if (rebuilding_) return;
            QStringList next;
            next.reserve(list_->count());
            for (int i = 0; i < list_->count(); ++i) {
              auto* it = list_->item(i);
              if (it) next.push_back(it->data(Qt::UserRole).toString());
            }
            if (next.size() == paths_.size()) {
              paths_ = next;
              index_ = list_->currentRow();
              refreshCount();
              setStatus(QStringLiteral("已重排 %1 张").arg(paths_.size()));
            }
          });

  setStyleSheet(QStringLiteral(
      "QWidget#filmstripBar{background:#232528;border-top:1px solid #4a4e54;}"
      "QListWidget#filmstripList{background:#1a1b1d;border:0;color:#ddd;outline:0;}"
      "QListWidget#filmstripList::item{padding:1px;border:1px solid #3a3d42;border-radius:3px;}"
      "QListWidget#filmstripList::item:hover{border:1px solid #6a7078;background:#26282c;}"
      "QListWidget#filmstripList::item:selected{"
      "border:2px solid #e67a2e;background:#322820;color:#f0e6dc;}"));
  setFocusPolicy(Qt::StrongFocus);
  list_->setFocusPolicy(Qt::StrongFocus);
  list_->installEventFilter(this);
  refreshCount();
}

void FilmstripBar::setStatus(const QString& text) { status_->setText(text); }

void FilmstripBar::refreshCount() {
  const int n = paths_.size();
  const int show = n == 0 ? 0 : index_ + 1;
  countLabel_->setText(QStringLiteral("图像源 (%1/%2)").arg(show).arg(n));
  if (n == 0) status_->setText(QStringLiteral("本地图像"));
}

QIcon FilmstripBar::makeThumb(const QString& path) const {
  QImage src(path);
  QImage canvas(kThumbW, kThumbH, QImage::Format_RGB32);
  canvas.fill(QColor(0x1a, 0x1b, 0x1d));
  QPainter p(&canvas);
  p.setRenderHint(QPainter::SmoothPixmapTransform);
  if (src.isNull()) {
    p.setPen(QColor(0x88, 0x88, 0x88));
    p.drawRect(2, 2, kThumbW - 5, kThumbH - 5);
    p.drawText(canvas.rect(), Qt::AlignCenter, QStringLiteral("?"));
  } else {
    const QImage scaled =
        src.scaled(kThumbW - 2, kThumbH - 2, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    const int x = (kThumbW - scaled.width()) / 2;
    const int y = (kThumbH - scaled.height()) / 2;
    // letterbox bars (VM filmstrip density)
    if (x > 1 || y > 1) {
      p.fillRect(0, 0, kThumbW, kThumbH, QColor(0x12, 0x13, 0x14));
      p.fillRect(x, y, scaled.width(), scaled.height(), QColor(0x1a, 0x1b, 0x1d));
    }
    p.drawImage(x, y, scaled);
    p.setPen(QColor(0x3a, 0x3d, 0x42));
    p.drawRect(0, 0, kThumbW - 1, kThumbH - 1);
  }
  p.end();
  return QIcon(QPixmap::fromImage(canvas));
}

void FilmstripBar::rebuildThumbs() {
  rebuilding_ = true;
  list_->clear();
  for (const QString& path : paths_) {
    const QFileInfo fi(path);
    auto* item = new QListWidgetItem(makeThumb(path), fi.completeBaseName().left(10));
    QImage probe(path);
    const QString tip = probe.isNull()
                            ? path
                            : QStringLiteral("%1\n%2×%3")
                                  .arg(path)
                                  .arg(probe.width())
                                  .arg(probe.height());
    item->setToolTip(tip);
    item->setData(Qt::UserRole, path);
    item->setTextAlignment(Qt::AlignHCenter | Qt::AlignTop);
    list_->addItem(item);
  }
  rebuilding_ = false;
  refreshCount();
}

void FilmstripBar::clearPaths() {
  paths_.clear();
  index_ = -1;
  rebuildThumbs();
}

void FilmstripBar::addPaths(const QStringList& paths) {
  bool changed = false;
  for (const QString& path : paths) {
    if (path.isEmpty() || paths_.contains(path)) continue;
    QImage probe(path);
    if (probe.isNull()) continue;
    paths_.push_back(path);
    changed = true;
  }
  if (!changed) return;
  const int keep = index_ < 0 ? paths_.size() - 1 : index_;
  rebuildThumbs();
  selectIndex(qBound(0, keep, paths_.size() - 1), true);
}

QString FilmstripBar::currentPath() const {
  if (index_ < 0 || index_ >= paths_.size()) return {};
  return paths_.at(index_);
}

int FilmstripBar::count() const { return paths_.size(); }
int FilmstripBar::index() const { return index_; }
bool FilmstripBar::autoSwitch() const { return autoSwitch_ && autoSwitch_->isChecked(); }

void FilmstripBar::selectIndex(int index, bool emitSignal) {
  if (index < 0 || index >= paths_.size()) return;
  index_ = index;
  rebuilding_ = true;
  list_->setCurrentRow(index);
  rebuilding_ = false;
  refreshCount();
  QImage probe(paths_.at(index));
  const QString fname = QFileInfo(paths_.at(index)).fileName();
  status_->setText(probe.isNull()
                       ? QStringLiteral("%1/%2 · %3")
                             .arg(index + 1)
                             .arg(paths_.size())
                             .arg(fname)
                       : QStringLiteral("%1/%2 · %3×%4 · %5")
                             .arg(index + 1)
                             .arg(paths_.size())
                             .arg(probe.width())
                             .arg(probe.height())
                             .arg(fname));
  if (emitSignal) emit imageSelected(paths_.at(index));
  if (list_ && !list_->hasFocus()) list_->setFocus(Qt::OtherFocusReason);
}

void FilmstripBar::advance() {
  if (paths_.size() < 2) return;
  const int next = (qMax(0, index_) + 1) % paths_.size();
  selectIndex(next, true);
}

void FilmstripBar::selectPrev() {
  if (paths_.isEmpty()) return;
  const int cur = qMax(0, index_);
  selectIndex((cur - 1 + paths_.size()) % paths_.size(), true);
}

void FilmstripBar::selectNext() {
  if (paths_.isEmpty()) return;
  const int cur = qMax(0, index_);
  selectIndex((cur + 1) % paths_.size(), true);
}

void FilmstripBar::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_Insert) {
    emit addImagesRequested();
    setStatus(QStringLiteral("添加图像…"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F7) {
    emit addFolderRequested();
    setStatus(QStringLiteral("添加文件夹…"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F5 || event->key() == Qt::Key_F9) {
    emit runAllRequested();
    setStatus(QStringLiteral("运行全部"));
    event->accept();
    return;
  }
  if ((event->key() == Qt::Key_Space || event->key() == Qt::Key_F6) &&
      autoSwitch_) {
    autoSwitch_->setChecked(!autoSwitch_->isChecked());
    setStatus(autoSwitch_->isChecked() ? QStringLiteral("自动切换 开")
                                       : QStringLiteral("自动切换 关"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Left) {
    if (event->modifiers() & Qt::ControlModifier) {
      if (!paths_.isEmpty()) selectIndex(0, true);
    } else {
      selectPrev();
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Right) {
    if (event->modifiers() & Qt::ControlModifier) {
      if (!paths_.isEmpty()) selectIndex(paths_.size() - 1, true);
    } else {
      selectNext();
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Home) {
    // Home / Ctrl+Home → first thumb
    if (!paths_.isEmpty()) selectIndex(0, true);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_End) {
    // End / Ctrl+End → last thumb
    if (!paths_.isEmpty()) selectIndex(paths_.size() - 1, true);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_PageUp) {
    if (!paths_.isEmpty())
      selectIndex(qMax(0, qMax(0, index_) - 5), true);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_PageDown) {
    if (!paths_.isEmpty())
      selectIndex(qMin(paths_.size() - 1, qMax(0, index_) + 5), true);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_0 || event->key() == Qt::Key_A) {
    if (!paths_.isEmpty()) {
      selectIndex(0, true);
      setStatus(QStringLiteral("跳到 #1"));
    }
    event->accept();
    return;
  }
  if (event->key() >= Qt::Key_1 && event->key() <= Qt::Key_9) {
    const int want = event->key() - Qt::Key_1;  // 0-based
    if (want < paths_.size()) {
      selectIndex(want, true);
      setStatus(QStringLiteral("跳到 #%1").arg(want + 1));
    }
    event->accept();
    return;
  }
  if ((event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace) &&
      (event->modifiers() & Qt::ControlModifier)) {
    paths_.clear();
    index_ = -1;
    rebuildThumbs();
    refreshCount();
    setStatus(QStringLiteral("已清空胶片"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace) {
    if (index_ >= 0 && index_ < paths_.size()) {
      paths_.removeAt(index_);
      const int next = qMin(index_, paths_.size() - 1);
      rebuildThumbs();
      if (next >= 0) selectIndex(next, true);
      else {
        index_ = -1;
        refreshCount();
      }
    }
    event->accept();
    return;
  }
  QWidget::keyPressEvent(event);
}

bool FilmstripBar::eventFilter(QObject* obj, QEvent* event) {
  if (obj == list_ && event->type() == QEvent::KeyPress) {
    keyPressEvent(static_cast<QKeyEvent*>(event));
    return event->isAccepted();
  }
  if (obj == list_ && event->type() == QEvent::Wheel) {
    auto* we = static_cast<QWheelEvent*>(event);
    if (list_ && list_->horizontalScrollBar()) {
      const int delta = we->angleDelta().y() != 0 ? we->angleDelta().y()
                                                 : we->angleDelta().x();
      list_->horizontalScrollBar()->setValue(
          list_->horizontalScrollBar()->value() - delta);
      return true;
    }
  }
  return QWidget::eventFilter(obj, event);
}

}  // namespace sieans_qt
