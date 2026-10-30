#pragma once

#include <QGraphicsPixmapItem>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QImage>
#include <QVector>
#include <QPolygonF>

namespace sieans_qt {

struct OverlayHit {
  QString text;
  QString format;
  QPolygonF polygon;
};

/** Center pane: image + barcode overlays (VisionMaster-style viewer stub). */
class ImageView : public QGraphicsView {
  Q_OBJECT
 public:
  explicit ImageView(QWidget* parent = nullptr);

  void setImage(const QImage& image);
  void setOverlays(const QVector<OverlayHit>& hits);
  void clearOverlays();
  QImage currentImage() const { return image_; }

 protected:
  void resizeEvent(QResizeEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;

 private:
  void refit();
  void redrawOverlays();

  QGraphicsScene scene_;
  QGraphicsPixmapItem* pixmap_item_ = nullptr;
  QVector<QGraphicsItem*> overlay_items_;
  QImage image_;
  QVector<OverlayHit> hits_;
};

}  // namespace sieans_qt
