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

/** Center pane: image + barcode overlays (VisionMaster-style viewer). */
class ImageView : public QGraphicsView {
  Q_OBJECT
 public:
  explicit ImageView(QWidget* parent = nullptr);

  void setImage(const QImage& image, bool refitView = true);
  /** Live preview: update pixmap without forced refit / overlay clear. */
  void setLiveImage(const QImage& image);
  void setOverlays(const QVector<OverlayHit>& hits);
  void clearOverlays();
  QImage currentImage() const { return image_; }

 public slots:
  void fitToView();

 protected:
  void resizeEvent(QResizeEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;

 private:
  void redrawOverlays();

  QGraphicsScene scene_;
  QGraphicsPixmapItem* pixmap_item_ = nullptr;
  QVector<QGraphicsItem*> overlay_items_;
  QImage image_;
  QVector<OverlayHit> hits_;
  bool userZoomed_ = false;
};

}  // namespace sieans_qt
