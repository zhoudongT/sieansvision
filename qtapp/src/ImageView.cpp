#include "ImageView.hpp"

#include <QGraphicsPathItem>
#include <QPainter>
#include <QGraphicsSimpleTextItem>
#include <QGraphicsRectItem>
#include <QPainterPath>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QLabel>
#include <QResizeEvent>

namespace sieans_qt {

ImageView::ImageView(QWidget* parent) : QGraphicsView(parent) {
  setFocusPolicy(Qt::StrongFocus);
  setToolTip(QStringLiteral("F/Home/0 适应 · +/- 缩放 · 拖拽平移"));
  setStatusTip(QStringLiteral("图像视图 · F/Home/0 适应 · +/- 缩放 · 码框叠加 hits"));
  setScene(&scene_);
  setRenderHints(QPainter::Antialiasing | QPainter::SmoothPixmapTransform);
  setDragMode(QGraphicsView::ScrollHandDrag);
  setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
  setBackgroundBrush(QColor(18, 20, 24));
  setFrameShape(QFrame::NoFrame);
  pixmap_item_ = scene_.addPixmap(QPixmap());
  probe_ = new QLabel(this);
  probe_->setObjectName(QStringLiteral("pixelProbe"));
  probe_->setStyleSheet(QStringLiteral(
      "background:rgba(0,0,0,170);color:#e8e8e8;padding:2px 8px;font-size:11px;"));
  setMouseTracking(true);
  updateProbe(-1, -1);
}

void ImageView::setImage(const QImage& image, bool refitView) {
  image_ = image;
  pixmap_item_->setPixmap(QPixmap::fromImage(image_));
  scene_.setSceneRect(pixmap_item_->boundingRect());
  clearOverlays();
  if (refitView) {
    userZoomed_ = false;
    fitToView();
  }
  updateProbe(-1, -1);
}

void ImageView::setLiveImage(const QImage& image) {
  if (image.isNull()) return;
  const bool sizeChanged =
      image_.isNull() || image.width() != image_.width() ||
      image.height() != image_.height();
  image_ = image;
  pixmap_item_->setPixmap(QPixmap::fromImage(image_));
  if (sizeChanged) {
    scene_.setSceneRect(pixmap_item_->boundingRect());
    if (!userZoomed_) fitToView();
  }
  setToolTip(QStringLiteral("图像 %1×%2 · F/Home/0 适应 · 码 %3")
                 .arg(image_.width())
                 .arg(image_.height())
                 .arg(hits_.size()));
  updateProbe(-1, -1);
}

void ImageView::setOverlays(const QVector<OverlayHit>& hits) {
  hits_ = hits;
  redrawOverlays();
}

void ImageView::clearOverlays() {
  for (auto* it : overlay_items_) {
    scene_.removeItem(it);
    delete it;
  }
  overlay_items_.clear();
  hits_.clear();
}

void ImageView::fitToView() {
  if (image_.isNull()) return;
  fitInView(pixmap_item_, Qt::KeepAspectRatio);
  userZoomed_ = false;
}

void ImageView::resizeEvent(QResizeEvent* event) {
  QGraphicsView::resizeEvent(event);
  updateProbe(-1, -1);
  if (!userZoomed_ && !image_.isNull()) fitToView();
}

void ImageView::updateProbe(int x, int y) {
  if (!probe_) return;
  const QString hitChip =
      hits_.isEmpty() ? QString()
                      : QStringLiteral(" · hits %1").arg(hits_.size());
  if (image_.isNull()) {
    probe_->setText(QStringLiteral("无图像"));
  } else if (x < 0 || y < 0 || x >= image_.width() || y >= image_.height()) {
    probe_->setText(QStringLiteral("%1*%2%3")
                        .arg(image_.width())
                        .arg(image_.height())
                        .arg(hitChip));
  } else {
    const QRgb px = image_.pixel(x, y);
    probe_->setText(QStringLiteral("%1*%2 | X %3 Y %4 | R %5 G %6 B %7%8")
                        .arg(image_.width())
                        .arg(image_.height())
                        .arg(x)
                        .arg(y)
                        .arg(qRed(px))
                        .arg(qGreen(px))
                        .arg(qBlue(px))
                        .arg(hitChip));
  }
  probe_->adjustSize();
  probe_->move(8, qMax(0, height() - probe_->height() - 6));
  probe_->raise();
}

void ImageView::mouseMoveEvent(QMouseEvent* event) {
  QGraphicsView::mouseMoveEvent(event);
  if (image_.isNull()) {
    updateProbe(-1, -1);
    return;
  }
  const QPointF sp = mapToScene(event->pos());
  updateProbe(int(sp.x()), int(sp.y()));
}


void ImageView::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_F || event->key() == Qt::Key_Home ||
      event->key() == Qt::Key_0) {
    userZoomed_ = false;
    fitToView();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Plus || event->key() == Qt::Key_Equal) {
    userZoomed_ = true;
    scale(1.15, 1.15);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Minus) {
    userZoomed_ = true;
    scale(1.0 / 1.15, 1.0 / 1.15);
    event->accept();
    return;
  }
  QGraphicsView::keyPressEvent(event);
}

void ImageView::wheelEvent(QWheelEvent* event) {
  userZoomed_ = true;
  const qreal factor = (event->angleDelta().y() > 0) ? 1.15 : (1.0 / 1.15);
  scale(factor, factor);
}

void ImageView::redrawOverlays() {
  for (auto* it : overlay_items_) {
    scene_.removeItem(it);
    delete it;
  }
  overlay_items_.clear();

  QPen pen(QColor(0, 230, 118), 2.5);
  int idx = 0;
  for (const auto& h : hits_) {
    ++idx;
    if (h.polygon.size() >= 2) {
      QPainterPath path;
      path.addPolygon(h.polygon);
      path.closeSubpath();
      auto* poly = scene_.addPath(path, pen, Qt::NoBrush);
      overlay_items_.push_back(poly);
    }
    if (!h.text.isEmpty() && !h.polygon.isEmpty()) {
      const QString text =
          QStringLiteral("#%1 %2: %3").arg(idx).arg(h.format, h.text.left(48));
      auto* label = scene_.addSimpleText(text);
      QFont f = label->font();
      f.setPointSize(11);
      f.setBold(true);
      label->setFont(f);
      label->setBrush(QColor(255, 235, 59));
      const QRectF br = h.polygon.boundingRect();
      const QRectF lr = label->boundingRect();
      auto* bg = scene_.addRect(
          QRectF(0, 0, lr.width() + 8, lr.height() + 4), Qt::NoPen,
          QColor(0, 0, 0, 160));
      bg->setPos(br.topLeft() + QPointF(0, -lr.height() - 6));
      label->setPos(br.topLeft() + QPointF(4, -lr.height() - 4));
      overlay_items_.push_back(bg);
      overlay_items_.push_back(label);
    }
  }
  // Size chip (VM-ish HUD) — always when image present.
  if (!image_.isNull()) {
    auto* sizeChip = scene_.addSimpleText(
        QStringLiteral("%1×%2").arg(image_.width()).arg(image_.height()));
    QFont sf = sizeChip->font();
    sf.setPointSize(11);
    sf.setBold(true);
    sizeChip->setFont(sf);
    sizeChip->setBrush(QColor(180, 220, 255));
    auto* sizeBg = scene_.addRect(
        QRectF(0, 0, sizeChip->boundingRect().width() + 10,
               sizeChip->boundingRect().height() + 6),
        Qt::NoPen, QColor(0, 0, 0, 160));
    sizeBg->setPos(8, 8);
    sizeChip->setPos(13, 11);
    overlay_items_.push_back(sizeBg);
    overlay_items_.push_back(sizeChip);
  }
  if (!hits_.isEmpty()) {
    auto* chip = scene_.addSimpleText(
        QStringLiteral("码 %1").arg(hits_.size()));
    QFont f = chip->font();
    f.setPointSize(12);
    f.setBold(true);
    chip->setFont(f);
    chip->setBrush(QColor(0, 230, 118));
    auto* chipBg = scene_.addRect(
        QRectF(0, 0, chip->boundingRect().width() + 10,
               chip->boundingRect().height() + 6),
        Qt::NoPen, QColor(0, 0, 0, 170));
    const qreal y = image_.isNull() ? 8 : 34;
    chipBg->setPos(8, y);
    chip->setPos(13, y + 3);
    overlay_items_.push_back(chipBg);
    overlay_items_.push_back(chip);
  }
}

}  // namespace sieans_qt
