#pragma once

#include <QGraphicsPixmapItem>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QImage>
#include <QVector>
#include <QPolygonF>
#include "GeomOverlay.hpp"

class QLabel;
class QKeyEvent;

namespace sieans_qt {

struct OverlayHit {
  QString text;
  QString format;
  QPolygonF polygon;
};

/** GEOM / MEASURE / CALIPER OverlayHit rows to pickable lines and points. */
QVector<GeomPickable> pickablesFromOverlayHits(const QVector<OverlayHit>& hits);

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
  /** Color-cycled geom/measure compare overlays (separate from barcode hits). */
  void setGeomOverlays(const QVector<GeomOverlaySpec>& specs);
  /** Drop only the compare geom layer and redraw remaining hits. */
  void clearGeomOverlays();
  int geomOverlayCount() const { return geom_specs_.size(); }
  QVector<GeomOverlaySpec> geomOverlays() const { return geom_specs_; }
  QImage currentImage() const { return image_; }

 signals:
  void imagePasted(const QImage& image);
  void imageSaveToFilmstripRequested(const QImage& image);

 public slots:
  void fitToView();

 protected:
  void resizeEvent(QResizeEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;
  void mouseMoveEvent(QMouseEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;
  void mousePressEvent(QMouseEvent* event) override;

 private:
  void redrawOverlays();
  void updateProbe(int x, int y);

  QGraphicsScene scene_;
  QGraphicsPixmapItem* pixmap_item_ = nullptr;
  QVector<QGraphicsItem*> overlay_items_;
  QImage image_;
  QVector<OverlayHit> hits_;
  QVector<GeomOverlaySpec> geom_specs_;
  bool userZoomed_ = false;
  bool overlaysHidden_ = false;
  bool probeHidden_ = false;
  QLabel* probe_ = nullptr;
  QString lastProbe_;
};

}  // namespace sieans_qt
