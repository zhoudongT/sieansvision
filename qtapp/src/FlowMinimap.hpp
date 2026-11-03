#pragma once

#include <QWidget>

class QGraphicsScene;
class QGraphicsView;
class QEvent;

namespace sieans_qt {

/** VisionMaster-style canvas overview; click to pan the main FlowView. */
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
  bool eventFilter(QObject* obj, QEvent* event) override;

 private:
  bool mapMetrics(QRectF* bounds, qreal* scale, qreal* ox, qreal* oy) const;

  QGraphicsScene* scene_ = nullptr;
  QGraphicsView* view_ = nullptr;
};

}  // namespace sieans_qt
