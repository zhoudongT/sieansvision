#include "FilmstripBar.hpp"

#include <QCheckBox>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QIcon>
#include <QLabel>
#include <QListWidget>
#include <QPixmap>
#include <QImage>
#include <QPushButton>
#include <QVBoxLayout>

namespace sieans_qt {

FilmstripBar::FilmstripBar(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("filmstripBar"));
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(6, 2, 6, 4);
  root->setSpacing(2);

  auto* head = new QHBoxLayout;
  head->setSpacing(6);
  countLabel_ = new QLabel(QStringLiteral("图像源 (0/0)"));
  countLabel_->setStyleSheet(QStringLiteral("color:#e8e8e8;font-weight:600;"));
  status_ = new QLabel(QStringLiteral("本地图像"));
  status_->setObjectName(QStringLiteral("muted"));
  autoSwitch_ = new QCheckBox(QStringLiteral("自动切换"));
  autoSwitch_->setToolTip(QStringLiteral("连续运行时切到下一张本地图"));
  auto* runAll = new QPushButton(QStringLiteral("运行全部"));
  auto* add = new QPushButton(QStringLiteral("+"));
  add->setToolTip(QStringLiteral("添加图像"));
  add->setFixedWidth(28);
  auto* folder = new QPushButton(QStringLiteral("文件夹"));
  folder->setToolTip(QStringLiteral("添加图像文件夹"));
  auto* del = new QPushButton(QStringLiteral("删除"));
  del->setToolTip(QStringLiteral("删除选中图像"));
  head->addWidget(countLabel_);
  head->addWidget(status_, 1);
  head->addWidget(autoSwitch_);
  head->addWidget(runAll);
  head->addWidget(add);
  head->addWidget(folder);
  head->addWidget(del);
  root->addLayout(head);

  list_ = new QListWidget;
  list_->setObjectName(QStringLiteral("filmstripList"));
  list_->setViewMode(QListView::IconMode);
  list_->setFlow(QListView::LeftToRight);
  list_->setWrapping(false);
  list_->setMovement(QListView::Static);
  list_->setResizeMode(QListView::Adjust);
  list_->setIconSize(QSize(72, 48));
  list_->setGridSize(QSize(86, 62));
  list_->setFixedHeight(70);
  list_->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
  list_->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
  list_->setSpacing(2);
  root->addWidget(list_);

  connect(add, &QPushButton::clicked, this, &FilmstripBar::addImagesRequested);
  connect(folder, &QPushButton::clicked, this, &FilmstripBar::addFolderRequested);
  connect(runAll, &QPushButton::clicked, this, &FilmstripBar::runAllRequested);
  connect(del, &QPushButton::clicked, this, [this]() {
    if (index_ < 0 || index_ >= paths_.size()) return;
    paths_.removeAt(index_);
    const int next = qMin(index_, paths_.size() - 1);
    rebuildThumbs();
    if (next >= 0) selectIndex(next, true);
    else refreshCount();
  });
  connect(list_, &QListWidget::currentRowChanged, this, [this](int row) {
    if (rebuilding_ || row < 0 || row >= paths_.size()) return;
    index_ = row;
    refreshCount();
    emit imageSelected(paths_.at(row));
  });

  setStyleSheet(QStringLiteral(
      "QWidget#filmstripBar{background:#232528;border-top:1px solid #4a4e54;}"
      "QListWidget#filmstripList{background:#1a1b1d;border:0;color:#ddd;}"));
  refreshCount();
}

void FilmstripBar::setStatus(const QString& text) { status_->setText(text); }

void FilmstripBar::refreshCount() {
  const int n = paths_.size();
  const int show = n == 0 ? 0 : index_ + 1;
  countLabel_->setText(QStringLiteral("图像源 (%1/%2)").arg(show).arg(n));
  if (n == 0) status_->setText(QStringLiteral("本地图像"));
}

void FilmstripBar::rebuildThumbs() {
  rebuilding_ = true;
  list_->clear();
  for (const QString& path : paths_) {
    QPixmap thumb(path);
    if (!thumb.isNull()) thumb = thumb.scaled(72, 48, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    auto* item = new QListWidgetItem(QIcon(thumb), QFileInfo(path).fileName());
    item->setToolTip(path);
    item->setData(Qt::UserRole, path);
    list_->addItem(item);
  }
  rebuilding_ = false;
  refreshCount();
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
  status_->setText(QFileInfo(paths_.at(index)).fileName());
  if (emitSignal) emit imageSelected(paths_.at(index));
}

void FilmstripBar::advance() {
  if (paths_.size() < 2) return;
  const int next = (qMax(0, index_) + 1) % paths_.size();
  selectIndex(next, true);
}

}  // namespace sieans_qt
