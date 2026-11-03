#include "FilmstripBar.hpp"
#include <QSet>
#include <algorithm>

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
#include <QInputDialog>
#include <QDesktopServices>
#include <QUrl>
#include <QMouseEvent>
#include <QClipboard>
#include <QGuiApplication>
#include <QApplication>
#include <QFileInfo>
#include <QEvent>
#include <QApplication>
#include <QWidget>
#include <QWheelEvent>
#include <QScrollBar>
#include <QRandomGenerator>

namespace sieans_qt {
namespace {
constexpr int kThumbW = 80;
constexpr int kThumbH = 52;
}  // namespace

FilmstripBar::FilmstripBar(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("filmstripBar"));
  setStatusTip(QStringLiteral("胶片条 · ←→/Ctrl+←→/Alt+←→ Home/End/PgUp/PgDn · 0/A/1-9 跳转 · Space 自动切换 · Ctrl+C 路径 · Ctrl+Shift+C 文件名 · Ctrl+D 复制 · Ctrl+Shift+I 反选 · Ctrl+Shift+S 排序 · Ctrl+Shift+M 剔缺失 · Ctrl+Shift+R 乱序 · Ctrl+E 导出 · Ctrl+Shift+E 导出选中 · 右键复制路径 · F5/F9 运行全部 · Insert 添加 · F7 文件夹 · Ctrl+G 跳转 · Ctrl+Shift+B 全名 · Ctrl+Shift+O 打开目录 · Ctrl+Shift+U 剔重 · 计数双击跳转/中键乱序/右键全名 · Del"));
  setFocusPolicy(Qt::StrongFocus);
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(6, 2, 6, 4);
  root->setSpacing(2);

  auto* head = new QHBoxLayout;
  head->setSpacing(6);
  countLabel_ = new QLabel(QStringLiteral("图像源 (0/0)"));
  countLabel_->setStyleSheet(QStringLiteral("color:#e8e8e8;font-weight:600;"));
  countLabel_->setToolTip(QStringLiteral("←→/Ctrl+←→ Home/End/PgUp/PgDn/滚轮 · 0/A/1-9 跳转 · Del 删除 · Ctrl+A 全选 · 拖拽重排"));
  countLabel_->setCursor(Qt::PointingHandCursor);
  countLabel_->installEventFilter(this);
  status_ = new QLabel(QStringLiteral("本地图像"));
  status_->setObjectName(QStringLiteral("muted"));
  status_->setCursor(Qt::PointingHandCursor);
  status_->setToolTip(QStringLiteral("中键打开当前目录 · 右键剔重 · Ctrl+Shift+O/U"));
  status_->installEventFilter(this);
  autoSwitch_ = new QCheckBox(QStringLiteral("自动切换"));
  autoSwitch_->setToolTip(QStringLiteral("连续运行时切到下一张本地图 · Space/F6 · 勾选后连续自动翻帧"));
  auto* runAll = new QPushButton(QStringLiteral("运行全部"));
  runAll->setToolTip(QStringLiteral("运行全部本地图 · F5/F9"));
  runAll->setStatusTip(QStringLiteral("胶片 · 运行全部 · F5/F9"));
  auto* add = new QPushButton(QStringLiteral("+"));
  add->setToolTip(QStringLiteral("添加图像 · Insert · 多选可一次加入"));
  add->setFixedWidth(28);
  auto* folder = new QPushButton(QStringLiteral("文件夹"));
  folder->setToolTip(QStringLiteral("添加图像文件夹 · F7 · 递归常见图格式"));
  auto* prev = new QPushButton(QStringLiteral("◀"));
  prev->setToolTip(QStringLiteral("上一张 · ← · Home 到首张"));
  prev->setFixedWidth(28);
  auto* next = new QPushButton(QStringLiteral("▶"));
  next->setToolTip(QStringLiteral("下一张 · → · End 到末张"));
  next->setFixedWidth(28);
  auto* pinFront = new QPushButton(QStringLiteral("⇈"));
  pinFront->setToolTip(QStringLiteral("选中置顶 · Ctrl+Shift+Home · Ctrl+单击缩略图"));
  pinFront->setFixedWidth(28);
  auto* pinEnd = new QPushButton(QStringLiteral("⇊"));
  pinEnd->setToolTip(QStringLiteral("选中置底 · Ctrl+Shift+End · Ctrl+Shift+单击缩略图"));
  pinEnd->setFixedWidth(28);
  auto* del = new QPushButton(QStringLiteral("删除"));
  del->setToolTip(QStringLiteral("删除选中 · Del · Ctrl+Del 清空 · 不可撤销"));
  head->addWidget(countLabel_);
  head->addWidget(status_, 1);
  head->addWidget(autoSwitch_);
  head->addWidget(runAll);
  head->addWidget(prev);
  head->addWidget(next);
  head->addWidget(add);
  head->addWidget(folder);
  head->addWidget(pinFront);
  head->addWidget(pinEnd);
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
  list_->setStatusTip(QStringLiteral("胶片 · ←→ Home/End · Ctrl+单击置顶 · Ctrl+Shift+单击置底 · 中键删除 · Space/F6 · F5/F9 · Del"));
  list_->setSpacing(2);
  list_->setSelectionMode(QAbstractItemView::ExtendedSelection);
  root->addWidget(list_);

  connect(add, &QPushButton::clicked, this, &FilmstripBar::addImagesRequested);
  connect(folder, &QPushButton::clicked, this, &FilmstripBar::addFolderRequested);
  connect(runAll, &QPushButton::clicked, this, &FilmstripBar::runAllRequested);
  connect(prev, &QPushButton::clicked, this, &FilmstripBar::selectPrev);
  connect(next, &QPushButton::clicked, this, &FilmstripBar::selectNext);
  connect(pinFront, &QPushButton::clicked, this, [this]() { moveSelectedToFront(); });
  connect(pinEnd, &QPushButton::clicked, this, [this]() { moveSelectedToEnd(); });
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
    } else if (event->modifiers() & Qt::AltModifier) {
      if (!paths_.isEmpty())
        selectIndex(qMax(0, qMax(0, index_) - 10), true);
    } else {
      selectPrev();
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Right) {
    if (event->modifiers() & Qt::ControlModifier) {
      if (!paths_.isEmpty()) selectIndex(paths_.size() - 1, true);
    } else if (event->modifiers() & Qt::AltModifier) {
      if (!paths_.isEmpty())
        selectIndex(qMin(paths_.size() - 1, qMax(0, index_) + 10), true);
    } else {
      selectNext();
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Home) {
    if ((event->modifiers() & Qt::ControlModifier) &&
        (event->modifiers() & Qt::ShiftModifier)) {
      moveSelectedToFront();
      event->accept();
      return;
    }
    if (!paths_.isEmpty()) selectIndex(0, true);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_End) {
    if ((event->modifiers() & Qt::ControlModifier) &&
        (event->modifiers() & Qt::ShiftModifier)) {
      moveSelectedToEnd();
      event->accept();
      return;
    }
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
  if (event->key() == Qt::Key_C && (event->modifiers() & Qt::ControlModifier)) {
    if (event->modifiers() & Qt::ShiftModifier) {
      copySelectedBasenames();
    } else {
      copySelectedPaths();
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_I && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    invertSelection();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_S && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    sortByName();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_M && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    removeMissing();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_R && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    shufflePaths();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_K && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    keepOnlySelected();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_P && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    moveSelectedToFront();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_E && (event->modifiers() & Qt::ControlModifier)) {
    if (event->modifiers() & Qt::ShiftModifier) {
      exportSelectedPathList();
    } else {
      exportPathList();
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_D && (event->modifiers() & Qt::ControlModifier)) {
    duplicateSelected();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_G && (event->modifiers() & Qt::ControlModifier)) {
    gotoIndexDialog();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_B && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    copyAllBasenames();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_O && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    revealCurrent();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_U && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    removeDuplicatePaths();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_A && (event->modifiers() & Qt::ControlModifier)) {
    if (list_ && list_->count() > 0) {
      list_->selectAll();
      setStatus(QStringLiteral("已全选 %1 张").arg(list_->count()));
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_0 ||
      (event->key() == Qt::Key_A && !(event->modifiers() & Qt::ControlModifier))) {
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
    if (list_) {
      const auto selected = list_->selectedItems();
      if (selected.size() > 1) {
        QSet<int> rows;
        for (auto* it : selected) rows.insert(list_->row(it));
        QList<int> sorted = rows.values();
        std::sort(sorted.begin(), sorted.end(), std::greater<int>());
        for (int r : sorted) {
          if (r >= 0 && r < paths_.size()) paths_.removeAt(r);
        }
        rebuildThumbs();
        if (!paths_.isEmpty())
          selectIndex(qMin(sorted.last(), paths_.size() - 1), true);
        else {
          index_ = -1;
          refreshCount();
        }
        setStatus(QStringLiteral("已删除 %1 张").arg(selected.size()));
        event->accept();
        return;
      }
    }
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
  if (obj == list_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::RightButton) {
      QListWidgetItem* hit = list_->itemAt(me->position().toPoint());
      if (hit) {
        const int r = list_->row(hit);
        if (r >= 0 && r < paths_.size()) {
          if (auto* clip = QGuiApplication::clipboard()) clip->setText(paths_.at(r));
          setStatus(QStringLiteral("已复制路径 · 右键"));
        }
      }
      return true;
    }
    if (me->button() == Qt::LeftButton && (me->modifiers() & Qt::ControlModifier)) {
      QListWidgetItem* hit = list_->itemAt(me->position().toPoint());
      if (hit) {
        list_->setCurrentItem(hit);
        index_ = list_->row(hit);
        if (me->modifiers() & Qt::ShiftModifier) moveSelectedToEnd();
        else moveSelectedToFront();
      }
      return true;
    }
    if (me->button() == Qt::MiddleButton) {
      // Middle-click: delete thumb under cursor (or current)
      QListWidgetItem* hit = list_->itemAt(me->position().toPoint());
      if (hit) {
        list_->setCurrentItem(hit);
        index_ = list_->row(hit);
      }
      QKeyEvent del(QEvent::KeyPress, Qt::Key_Delete, Qt::NoModifier);
      keyPressEvent(&del);
      return true;
    }
  }
  if (obj == countLabel_ && event->type() == QEvent::MouseButtonDblClick) {
    gotoIndexDialog();
    return true;
  }
  if (obj == countLabel_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      shufflePaths();
      return true;
    }
    if (me->button() == Qt::RightButton) {
      copyAllBasenames();
      return true;
    }
    if (me->button() == Qt::LeftButton) {
      exportPathList();
      return true;
    }
  }
  if (obj == status_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      revealCurrent();
      return true;
    }
    if (me->button() == Qt::RightButton) {
      removeDuplicatePaths();
      return true;
    }
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


void FilmstripBar::copySelectedPaths() {
  if (!list_) return;
  QStringList lines;
  const auto selected = list_->selectedItems();
  if (!selected.isEmpty()) {
    for (auto* it : selected) {
      const int r = list_->row(it);
      if (r >= 0 && r < paths_.size()) lines << paths_.at(r);
    }
  } else if (index_ >= 0 && index_ < paths_.size()) {
    lines << paths_.at(index_);
  }
  if (lines.isEmpty()) return;
  if (auto* clip = QApplication::clipboard())
    clip->setText(lines.join(QLatin1Char('\n')));
  setStatus(QStringLiteral("已复制 %1 路径").arg(lines.size()));
}

void FilmstripBar::duplicateSelected() {
  if (!list_) return;
  QList<int> rows;
  for (auto* it : list_->selectedItems()) rows.push_back(list_->row(it));
  if (rows.isEmpty() && index_ >= 0) rows.push_back(index_);
  if (rows.isEmpty()) return;
  std::sort(rows.begin(), rows.end());
  QStringList add;
  for (int r : rows) {
    if (r >= 0 && r < paths_.size()) add << paths_.at(r);
  }
  if (add.isEmpty()) return;
  const int at = paths_.size();
  addPaths(add);
  selectIndex(at, true);
  setStatus(QStringLiteral("已复制插入 %1 张").arg(add.size()));
}
void FilmstripBar::copySelectedBasenames() {
  if (!list_) return;
  QStringList lines;
  const auto selected = list_->selectedItems();
  if (!selected.isEmpty()) {
    for (auto* it : selected) {
      const int r = list_->row(it);
      if (r >= 0 && r < paths_.size()) lines << QFileInfo(paths_.at(r)).fileName();
    }
  } else if (index_ >= 0 && index_ < paths_.size()) {
    lines << QFileInfo(paths_.at(index_)).fileName();
  }
  if (lines.isEmpty()) return;
  if (auto* clip = QApplication::clipboard())
    clip->setText(lines.join(QLatin1Char('\n')));
  setStatus(QStringLiteral("已复制 %1 文件名").arg(lines.size()));
}

void FilmstripBar::invertSelection() {
  if (!list_ || list_->count() == 0) return;
  for (int i = 0; i < list_->count(); ++i) {
    auto* it = list_->item(i);
    if (!it) continue;
    it->setSelected(!it->isSelected());
  }
  setStatus(QStringLiteral("已反选 %1 张").arg(list_->selectedItems().size()));
}

void FilmstripBar::sortByName() {
  if (paths_.size() < 2) return;
  const QString cur = currentPath();
  std::sort(paths_.begin(), paths_.end(), [](const QString& a, const QString& b) {
    return QFileInfo(a).fileName().localeAwareCompare(QFileInfo(b).fileName()) < 0;
  });
  rebuildThumbs();
  int idx = paths_.indexOf(cur);
  if (idx < 0) idx = 0;
  selectIndex(idx, true);
  setStatus(QStringLiteral("已按文件名排序 · %1").arg(paths_.size()));
}

void FilmstripBar::removeMissing() {
  const QString cur = currentPath();
  const int before = paths_.size();
  QStringList keep;
  for (const QString& p : paths_) {
    if (QFileInfo::exists(p)) keep << p;
  }
  paths_ = keep;
  rebuildThumbs();
  int idx = paths_.indexOf(cur);
  if (idx < 0) idx = paths_.isEmpty() ? -1 : 0;
  if (idx >= 0) selectIndex(idx, true);
  else { index_ = -1; refreshCount(); }
  setStatus(QStringLiteral("已剔除缺失 %1 · 剩 %2 · Ctrl+Shift+M")
                .arg(before - paths_.size()).arg(paths_.size()));
}

void FilmstripBar::shufflePaths() {
  if (paths_.size() < 2) return;
  const QString cur = currentPath();
  for (int i = paths_.size() - 1; i > 0; --i) {
    const int j = QRandomGenerator::global()->bounded(i + 1);
    paths_.swapItemsAt(i, j);
  }
  rebuildThumbs();
  int idx = paths_.indexOf(cur);
  if (idx < 0) idx = 0;
  selectIndex(idx, true);
  setStatus(QStringLiteral("已乱序 · %1 · Ctrl+Shift+R").arg(paths_.size()));
}


void FilmstripBar::keepOnlySelected() {
  if (!list_) return;
  QStringList keep;
  for (auto* it : list_->selectedItems()) {
    const int row = list_->row(it);
    if (row >= 0 && row < paths_.size()) keep << paths_.at(row);
  }
  if (keep.isEmpty()) return;
  paths_ = keep;
  index_ = 0;
  rebuildThumbs();
  refreshCount();
  if (!paths_.isEmpty()) emit imageSelected(paths_.first());
  if (status_) status_->setText(QStringLiteral("仅保留选中 %1 · Ctrl+Shift+K").arg(paths_.size()));
}

void FilmstripBar::exportPathList() {
  if (paths_.isEmpty()) return;
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(paths_.join(QLatin1Char('\n')));
  if (status_) status_->setText(QStringLiteral("已导出路径 %1 · Ctrl+E").arg(paths_.size()));
}


void FilmstripBar::exportSelectedPathList() {
  if (!list_) return;
  QStringList lines;
  for (auto* it : list_->selectedItems()) {
    const int r = list_->row(it);
    if (r >= 0 && r < paths_.size()) lines << paths_.at(r);
  }
  if (lines.isEmpty() && index_ >= 0 && index_ < paths_.size())
    lines << paths_.at(index_);
  if (lines.isEmpty()) return;
  if (auto* clip = QGuiApplication::clipboard())
    clip->setText(lines.join(QLatin1Char('\n')));
  if (status_) status_->setText(QStringLiteral("已导出选中 %1 · Ctrl+Shift+E").arg(lines.size()));
}

void FilmstripBar::gotoIndexDialog() {
  if (paths_.isEmpty()) {
    setStatus(QStringLiteral("胶片空 · Ctrl+G"));
    return;
  }
  bool ok = false;
  const int cur = index_ >= 0 ? index_ + 1 : 1;
  const int want = QInputDialog::getInt(this, QStringLiteral("跳转胶片"),
                                        QStringLiteral("序号 1-%1").arg(paths_.size()),
                                        cur, 1, paths_.size(), 1, &ok);
  if (!ok) return;
  selectIndex(want - 1, true);
  setStatus(QStringLiteral("跳到 #%1 · Ctrl+G").arg(want));
}

void FilmstripBar::copyAllBasenames() {
  QStringList names;
  for (const QString& p : paths_) names << QFileInfo(p).fileName();
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(names.join(QLatin1Char('\n')));
  setStatus(QStringLiteral("已复制全部文件名 %1 · Ctrl+Shift+B").arg(names.size()));
}

void FilmstripBar::revealCurrent() {
  const QString path = currentPath();
  if (path.isEmpty()) {
    setStatus(QStringLiteral("无当前图 · Ctrl+Shift+O"));
    return;
  }
  const QFileInfo fi(path);
  const QString dir = fi.exists() ? fi.absolutePath() : QFileInfo(path).absolutePath();
  if (dir.isEmpty()) {
    setStatus(QStringLiteral("目录无效 · Ctrl+Shift+O"));
    return;
  }
  QDesktopServices::openUrl(QUrl::fromLocalFile(dir));
  setStatus(QStringLiteral("已打开目录 · %1").arg(QFileInfo(dir).fileName()));
}

void FilmstripBar::removeDuplicatePaths() {
  if (paths_.isEmpty()) {
    setStatus(QStringLiteral("胶片空 · Ctrl+Shift+U"));
    return;
  }
  QStringList uniq;
  QSet<QString> seen;
  const QString cur = currentPath();
  for (const QString& p : paths_) {
    const QString key = QFileInfo(p).absoluteFilePath();
    if (seen.contains(key)) continue;
    seen.insert(key);
    uniq << p;
  }
  const int removed = paths_.size() - uniq.size();
  if (removed <= 0) {
    setStatus(QStringLiteral("无重复 · Ctrl+Shift+U"));
    return;
  }
  paths_ = uniq;
  rebuildThumbs();
  int want = uniq.indexOf(cur);
  if (want < 0) want = 0;
  selectIndex(want, true);
  setStatus(QStringLiteral("已剔重 %1 · 剩 %2 · Ctrl+Shift+U").arg(removed).arg(paths_.size()));
}



void FilmstripBar::moveSelectedToFront() {
  if (!list_ || paths_.isEmpty()) return;
  QList<int> rows;
  for (QListWidgetItem* it : list_->selectedItems()) {
    const int r = list_->row(it);
    if (r >= 0) rows << r;
  }
  if (rows.isEmpty() && index_ >= 0) rows << index_;
  if (rows.isEmpty()) return;
  std::sort(rows.begin(), rows.end());
  QStringList moved;
  for (int i = rows.size() - 1; i >= 0; --i) {
    const int r = rows[i];
    if (r < 0 || r >= paths_.size()) continue;
    moved.prepend(paths_.takeAt(r));
  }
  for (int i = moved.size() - 1; i >= 0; --i) paths_.prepend(moved[i]);
  const QString cur = currentPath();
  rebuildThumbs();
  if (!cur.isEmpty()) {
    const int ni = paths_.indexOf(cur);
    if (ni >= 0) selectIndex(ni, true);
  }
  setStatus(QStringLiteral("已置顶 %1 · Ctrl+Shift+Home").arg(moved.size()));
}

void FilmstripBar::moveSelectedToEnd() {
  if (!list_ || paths_.isEmpty()) return;
  QList<int> rows;
  for (QListWidgetItem* it : list_->selectedItems()) {
    const int r = list_->row(it);
    if (r >= 0) rows << r;
  }
  if (rows.isEmpty() && index_ >= 0) rows << index_;
  if (rows.isEmpty()) return;
  std::sort(rows.begin(), rows.end());
  QStringList moved;
  for (int i = rows.size() - 1; i >= 0; --i) {
    const int r = rows[i];
    if (r < 0 || r >= paths_.size()) continue;
    moved.prepend(paths_.takeAt(r));
  }
  paths_.append(moved);
  const QString cur = currentPath();
  rebuildThumbs();
  if (!cur.isEmpty()) {
    const int ni = paths_.indexOf(cur);
    if (ni >= 0) selectIndex(ni, true);
  }
  setStatus(QStringLiteral("已置底 %1 · Ctrl+Shift+End").arg(moved.size()));
}

}  // namespace sieans_qt
