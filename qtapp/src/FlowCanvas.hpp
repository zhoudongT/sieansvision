#pragma once

#include "SieansDocument.hpp"

#include <QGraphicsItem>
#include <QGraphicsObject>
#include <QGraphicsPathItem>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QHash>
#include <QDragEnterEvent>
#include <QDropEvent>

namespace sieans_qt {

class FlowNodeItem;
class FlowEdgeItem;
class FlowPortItem;
class FlowScene;

class FlowPortItem : public QGraphicsObject {
 public:
  FlowPortItem(FlowNodeItem* owner, const QString& side, bool output);

  FlowNodeItem* owner() const { return owner_; }
  QString side() const { return side_; }
  bool isOutput() const { return output_; }
  void setHighlight(const QString& h);  // "", "valid", "invalid"

  QRectF boundingRect() const override;
  void paint(QPainter* painter, const QStyleOptionGraphicsItem* option,
             QWidget* widget) override;

 protected:
  void mousePressEvent(QGraphicsSceneMouseEvent* event) override;

 private:
  FlowNodeItem* owner_ = nullptr;
  QString side_;
  bool output_ = true;
  QString highlight_;
};

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

  FlowPortItem* port(const QString& side) const;
  QPointF portScenePos(const QString& side) const;

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
  QHash<QString, FlowPortItem*> ports_;
};

class FlowEdgeItem : public QGraphicsPathItem {
 public:
  FlowEdgeItem(const QString& id, FlowNodeItem* from, FlowNodeItem* to,
               const QString& fromPort, const QString& toPort);
  void refresh();
  QString edgeId() const { return id_; }
  FlowNodeItem* fromNode() const { return from_; }
  FlowNodeItem* toNode() const { return to_; }
  QString fromPort() const { return fromPort_; }
  QString toPort() const { return toPort_; }

 protected:
  void mousePressEvent(QGraphicsSceneMouseEvent* event) override;

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
  FlowEdgeItem* selectedEdge() const;

  void startLink(FlowPortItem* port);
  void updateLinkPreview(const QPointF& scenePos, FlowPortItem* hover);
  void finishLink(FlowPortItem* target);
  void cancelLink();
  bool isLinking() const { return linking_; }
  void removeSelectedEdge();
  void removeEdgeById(const QString& edgeId);
  void handleKey(QKeyEvent* event);

  FlowPortItem* portAt(const QPointF& scenePos) const;

 signals:
  void nodeSelected(const QString& nodeId);
  void nodeMoved(const QString& nodeId, const QPointF& pos);
  void canvasBackgroundClicked();
  void edgeConnected(const QString& fromId, const QString& toId,
                     const QString& fromPort, const QString& toPort);
  void edgeRemoved(const QString& edgeId);
  void linkNotice(const QString& msg);

 protected:
  void drawBackground(QPainter* painter, const QRectF& rect) override;
  void mousePressEvent(QGraphicsSceneMouseEvent* event) override;
  void mouseMoveEvent(QGraphicsSceneMouseEvent* event) override;
  void mouseReleaseEvent(QGraphicsSceneMouseEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;

 private:
  friend class FlowNodeItem;
  friend class FlowPortItem;
  void notifyMoved(FlowNodeItem* node);
  void rebuildEdgesFromDoc();

  SieansDocument* doc_ = nullptr;
  QHash<QString, FlowNodeItem*> nodes_;
  QVector<FlowEdgeItem*> edges_;

  bool linking_ = false;
  QString linkNodeId_;
  QString linkSide_;
  bool linkOutput_ = true;
  QGraphicsPathItem* linkPreview_ = nullptr;
};

class FlowView : public QGraphicsView {
  Q_OBJECT
 public:
  explicit FlowView(FlowScene* scene, QWidget* parent = nullptr);
  void fitAll();

 signals:
  void operatorDropped(const QString& key, const QPointF& scenePos);

 protected:
  void wheelEvent(QWheelEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;
  void dragEnterEvent(QDragEnterEvent* event) override;
  void dragMoveEvent(QDragMoveEvent* event) override;
  void dropEvent(QDropEvent* event) override;
};

}  // namespace sieans_qt
