#pragma once

#include <QWidget>
#include <QPoint>

class QGraphicsScene;
class QGraphicsView;
class QEvent;
class QMouseEvent;
class QWheelEvent;
class QPaintEvent;

namespace sieans_qt {

/** VisionMaster-style canvas overview; click/drag to pan the main FlowView. */
class FlowMinimap : public QWidget {
  Q_OBJECT
 public:
  FlowMinimap(QGraphicsScene* scene, QGraphicsView* view, QWidget* parent = nullptr);

  void setScene(QGraphicsScene* scene);
  void setView(QGraphicsView* view);

 signals:
  void navigate(qreal sceneX, qreal sceneY);

 protected:
  void paintEvent(QPaintEvent* event) override;
  void mousePressEvent(QMouseEvent* event) override;
  void mouseMoveEvent(QMouseEvent* event) override;
  void mouseReleaseEvent(QMouseEvent* event) override;
  void mouseDoubleClickEvent(QMouseEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;
  bool eventFilter(QObject* obj, QEvent* event) override;

 private:
  bool mapMetrics(QRectF* bounds, qreal* scale, qreal* ox, qreal* oy) const;
  void panTo(const QPointF& widgetPos);

  QGraphicsScene* scene_ = nullptr;
  QGraphicsView* view_ = nullptr;
  bool dragging_ = false;
};

}  // namespace sieans_qt
