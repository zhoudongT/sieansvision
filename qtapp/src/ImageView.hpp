#pragma once

#include <QGraphicsPixmapItem>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QImage>
#include <QVector>
#include <QPolygonF>
#include <QRect>
#include <QStringList>
#include <QVariantMap>
#include "GeomOverlay.hpp"

class QLabel;
class QGraphicsRectItem;
class QKeyEvent;

namespace sieans_qt {

struct OverlayHit {
  QString text;
  QString format;
  QPolygonF polygon;
};

/** GEOM / MEASURE / CALIPER OverlayHit rows to pickable lines and points. */
QVector<GeomPickable> pickablesFromOverlayHits(const QVector<OverlayHit>& hits);

/** True when the operator stores a drawable axis-aligned ROI (roiX/Y/W/H). */
bool operationSupportsRoi(const QString& op);
/** Read roiX/Y/W/H, or a 4-list params["roi"] (PySide). Empty if absent. */
QRect roiFromParams(const QVariantMap& params);
/** Write both roiX/Y/W/H and params["roi"] = [x,y,w,h] for Qt + PySide. */
void writeRoiToParams(QVariantMap& params, const QRect& r);
/** Drop roiX/Y/W/H and params["roi"]. */
void clearRoiFromParams(QVariantMap& params);

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

  /** Enter/leave rubber-band + handle edit mode (PySide set_roi_mode). */
  void setRoiMode(bool on);
  bool roiMode() const { return roi_mode_; }
  QRect roi() const { return roi_; }
  bool hasRoi() const { return roi_.width() >= 2 && roi_.height() >= 2; }
  /** Show a rect without emitting (selection sync / load). */
  void setRoi(const QRect& r, bool emitSignal = false);
  void clearRoi(bool emitSignal = false);
  /** Headless stand-ins for draw / move / resize; emit if the rect actually changes. */
  bool applyRoi(const QRect& r);
  bool moveRoiBy(int dx, int dy);
  bool resizeRoi(int dLeft, int dTop, int dRight, int dBottom);
  /** Isolated draw/move/resize + param write-back checks. Empty list = pass. Needs QApplication. */
  static QStringList roiEditorSelfTest();

 signals:
  void imagePasted(const QImage& image);
  void imageSaveToFilmstripRequested(const QImage& image);
  void roiEdited(const QRect& r);
  void roiCleared();

 public slots:
  void fitToView();

 protected:
  void resizeEvent(QResizeEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;
  void mouseMoveEvent(QMouseEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;
  void mousePressEvent(QMouseEvent* event) override;
  void mouseReleaseEvent(QMouseEvent* event) override;

 private:
  void redrawOverlays();
  void updateProbe(int x, int y);
  /** Rebuild the dashed ROI rect and (in edit mode) resize handles. */
  void redrawRoi();
  /** Which handle (or move/draw) is under a scene point; 0 = none. */
  int hitRoiHandle(const QPointF& scenePos) const;
  QRect clampRoiRect(const QRect& r) const;
  void applyDragTo(const QPointF& scenePos);


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
  bool roi_mode_ = false;
  QRect roi_;
  QGraphicsRectItem* roi_item_ = nullptr;
  QVector<QGraphicsRectItem*> roi_handles_;
  int roi_drag_ = 0;  // 0 none, 1 move, 2–9 handles, 10 draw
  QPointF roi_press_;
  QRect roi_start_;
};

}  // namespace sieans_qt
