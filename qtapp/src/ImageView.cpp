#include "ImageView.hpp"

#include <QGraphicsPathItem>
#include <QPainter>
#include <QGraphicsSimpleTextItem>
#include <QPainterPath>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QLabel>
#include <QResizeEvent>

namespace sieans_qt {

ImageView::ImageView(QWidget* parent) : QGraphicsView(parent) {
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
  if (image_.isNull()) {
    probe_->setText(QStringLiteral("无图像"));
  } else if (x < 0 || y < 0 || x >= image_.width() || y >= image_.height()) {
    probe_->setText(QStringLiteral("%1*%2").arg(image_.width()).arg(image_.height()));
  } else {
    const QRgb px = image_.pixel(x, y);
    probe_->setText(QStringLiteral("%1*%2 | X %3 Y %4 | R %5 G %6 B %7")
                        .arg(image_.width())
                        .arg(image_.height())
                        .arg(x)
                        .arg(y)
                        .arg(qRed(px))
                        .arg(qGreen(px))
                        .arg(qBlue(px)));
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
  for (const auto& h : hits_) {
    if (h.polygon.size() >= 2) {
      QPainterPath path;
      path.addPolygon(h.polygon);
      path.closeSubpath();
      auto* poly = scene_.addPath(path, pen, Qt::NoBrush);
      overlay_items_.push_back(poly);
    }
    if (!h.text.isEmpty() && !h.polygon.isEmpty()) {
      auto* label = scene_.addSimpleText(h.format + QStringLiteral(": ") + h.text);
      QFont f = label->font();
      f.setPointSize(11);
      f.setBold(true);
      label->setFont(f);
      label->setBrush(QColor(255, 235, 59));
      label->setPos(h.polygon.boundingRect().topLeft() + QPointF(0, -18));
      overlay_items_.push_back(label);
    }
  }
}

}  // namespace sieans_qt
