#pragma once

#include "SieansDocument.hpp"

#include <QGraphicsItem>
#include <QGraphicsObject>
#include <QGraphicsPathItem>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QHash>

namespace sieans_qt {

class FlowNodeItem;
class FlowEdgeItem;
class FlowScene;

class FlowNodeItem : public QGraphicsObject {
 public:
  static constexpr qreal kWidth = 168;
  static constexpr qreal kHeight = 28;

  FlowNodeItem(const QString& id, const QString& label, bool isSource,
               QGraphicsItem* parent = nullptr);

  QString nodeId() const { return id_; }
  QString label() const { return label_; }
  bool isSource() const { return source_; }
  void setLabel(const QString& label);
  void setRunState(const QString& state, const QColor& badge = {});

  QPointF portScenePos(const QString& side, bool output) const;

  QRectF boundingRect() const override;
  void paint(QPainter* painter, const QStyleOptionGraphicsItem* option,
             QWidget* widget) override;

 protected:
  QVariant itemChange(GraphicsItemChange change, const QVariant& value) override;

 private:
  QString id_;
  QString label_;
  bool source_ = false;
  QString runState_ = QStringLiteral("等待执行");
  QColor badgeColor_;
};

class FlowEdgeItem : public QGraphicsPathItem {
 public:
  FlowEdgeItem(const QString& id, FlowNodeItem* from, FlowNodeItem* to,
               const QString& fromPort, const QString& toPort);
  void refresh();
  QString edgeId() const { return id_; }
  FlowNodeItem* fromNode() const { return from_; }
  FlowNodeItem* toNode() const { return to_; }

 private:
  QString id_;
  FlowNodeItem* from_ = nullptr;
  FlowNodeItem* to_ = nullptr;
  QString fromPort_;
  QString toPort_;
};

class FlowScene : public QGraphicsScene {
  Q_OBJECT
 public:
  explicit FlowScene(QObject* parent = nullptr);

  void loadDocument(SieansDocument* doc);
  void clearGraph();
  void setNodeRunState(const QString& id, const QString& state,
                       const QColor& badge = {});
  void resetRunStates();
  FlowNodeItem* selectedNode() const;
  QString selectedNodeId() const;

 signals:
  void nodeSelected(const QString& nodeId);
  void nodeMoved(const QString& nodeId, const QPointF& pos);
  void canvasBackgroundClicked();

 protected:
  void drawBackground(QPainter* painter, const QRectF& rect) override;
  void mousePressEvent(QGraphicsSceneMouseEvent* event) override;

 private:
  friend class FlowNodeItem;
  void notifyMoved(FlowNodeItem* node);

  SieansDocument* doc_ = nullptr;
  QHash<QString, FlowNodeItem*> nodes_;
  QVector<FlowEdgeItem*> edges_;
};

class FlowView : public QGraphicsView {
  Q_OBJECT
 public:
  explicit FlowView(FlowScene* scene, QWidget* parent = nullptr);
  void fitAll();

 protected:
  void wheelEvent(QWheelEvent* event) override;
};

}  // namespace sieans_qt
