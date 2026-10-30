#include "FilmstripBar.hpp"
#include "Theme.hpp"

#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>

namespace sieans_qt {

FilmstripBar::FilmstripBar(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("filmstripBar"));
  setFixedHeight(36);
  auto* lay = new QHBoxLayout(this);
  lay->setContentsMargins(6, 2, 6, 2);
  lay->setSpacing(6);
  auto* title = new QLabel(QStringLiteral("胶片"));
  title->setObjectName(QStringLiteral("muted"));
  status_ = new QLabel(QStringLiteral("本地图列表 · 可批量跑"));
  status_->setObjectName(QStringLiteral("muted"));
  auto* openBtn = new QPushButton(QStringLiteral("打开图像"));
  auto* runAll = new QPushButton(QStringLiteral("全部运行"));
  lay->addWidget(title);
  lay->addWidget(status_, 1);
  lay->addWidget(openBtn);
  lay->addWidget(runAll);
  connect(openBtn, &QPushButton::clicked, this, &FilmstripBar::openImageRequested);
  connect(runAll, &QPushButton::clicked, this, &FilmstripBar::runAllRequested);
  setStyleSheet(QStringLiteral(
      "QWidget#filmstripBar{background:#232528;border-top:1px solid #4a4e54;}"));
}

void FilmstripBar::setStatus(const QString& text) { status_->setText(text); }

}  // namespace sieans_qt
