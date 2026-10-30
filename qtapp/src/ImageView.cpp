#include "ImageView.hpp"

#include <QGraphicsPathItem>
#include <QPainter>
#include <QGraphicsSimpleTextItem>
#include <QPainterPath>
#include <QWheelEvent>

namespace sieans_qt {

ImageView::ImageView(QWidget* parent) : QGraphicsView(parent) {
  setScene(&scene_);
  setRenderHints(QPainter::Antialiasing | QPainter::SmoothPixmapTransform);
  setDragMode(QGraphicsView::ScrollHandDrag);
  setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
  setBackgroundBrush(QColor(18, 20, 24));
  setFrameShape(QFrame::NoFrame);
  pixmap_item_ = scene_.addPixmap(QPixmap());
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
  if (!userZoomed_ && !image_.isNull()) fitToView();
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
