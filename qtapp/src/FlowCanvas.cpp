#include "FlowCanvas.hpp"

#include "Theme.hpp"

#include <QGraphicsSceneMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QFont>
#include <QWheelEvent>
#include <QtMath>
#include <cmath>

namespace sieans_qt {

FlowNodeItem::FlowNodeItem(const QString& id, const QString& label, bool isSource,
                           QGraphicsItem* parent)
    : QGraphicsObject(parent), id_(id), label_(label), source_(isSource) {
  setFlags(ItemIsMovable | ItemIsSelectable | ItemSendsGeometryChanges);
  setZValue(2);
  setToolTip(label + QStringLiteral("\n拖动移动 · 单击选中看属性"));
  badgeColor_ = QColor(theme::ACCENT);
}

void FlowNodeItem::setLabel(const QString& label) {
  label_ = label;
  update();
}

void FlowNodeItem::setRunState(const QString& state, const QColor& badge) {
  runState_ = state;
  if (badge.isValid()) badgeColor_ = badge;
  else if (state.startsWith(QStringLiteral("OK")) || state == QStringLiteral("完成"))
    badgeColor_ = QColor(theme::OK);
  else if (state.startsWith(QStringLiteral("NG")) || state.contains(QStringLiteral("失败")))
    badgeColor_ = QColor(QStringLiteral("#e53935"));
  else if (state.contains(QStringLiteral("运行")))
    badgeColor_ = QColor(theme::WARN);
  else
    badgeColor_ = QColor(theme::ACCENT);
  update();
}

QPointF FlowNodeItem::portScenePos(const QString& side, bool /*output*/) const {
  const QRectF r(0, 0, kWidth, kHeight);
  QPointF local;
  if (side == QLatin1String("top"))
    local = QPointF(r.center().x(), r.top());
  else if (side == QLatin1String("bottom"))
    local = QPointF(r.center().x(), r.bottom());
  else if (side == QLatin1String("left"))
    local = QPointF(r.left(), r.center().y());
  else
    local = QPointF(r.right(), r.center().y());
  return mapToScene(local);
}

QRectF FlowNodeItem::boundingRect() const {
  return QRectF(-3, -8, kWidth + 14, kHeight + 14);
}

void FlowNodeItem::paint(QPainter* painter, const QStyleOptionGraphicsItem*,
                         QWidget*) {
  painter->setRenderHint(QPainter::Antialiasing);
  const bool selected = isSelected();
  QColor fill, border;
  if (source_) {
    fill = QColor(selected ? QStringLiteral("#f0e8d0") : QStringLiteral("#e8e4d4"));
    border = QColor(selected ? theme::ACCENT : QStringLiteral("#c4b896"));
  } else {
    fill = QColor(selected ? QStringLiteral("#fff8f0") : QStringLiteral("#f2f2f2"));
    border = QColor(selected ? theme::ACCENT : QStringLiteral("#c8c8c8"));
  }
  QPen pen(border, selected ? 1.8 : 1.1);
  if (selected) pen.setStyle(Qt::DashLine);
  painter->setPen(pen);
  painter->setBrush(fill);
  painter->drawRoundedRect(QRectF(0, 0, kWidth, kHeight), 3, 3);

  painter->setPen(Qt::NoPen);
  painter->setBrush(badgeColor_);
  painter->drawRoundedRect(QRectF(5, 5, 18, 18), 2, 2);
  painter->setPen(QPen(Qt::white, 1.4, Qt::SolidLine, Qt::RoundCap));
  if (source_) {
    painter->drawRoundedRect(QRectF(8, 9, 12, 9), 1, 1);
    painter->drawEllipse(QRectF(11.5, 11, 5, 5));
  } else {
    painter->drawEllipse(QRectF(9, 9, 10, 10));
    painter->drawPoint(QPointF(14, 14));
  }

  painter->setPen(QColor(QStringLiteral("#222222")));
  QFont font(QStringLiteral("Microsoft YaHei UI"), 9, QFont::Medium);
  painter->setFont(font);
  const QRectF textRect(28, 0, kWidth - 34, kHeight);
  painter->drawText(
      textRect, Qt::AlignVCenter | Qt::AlignLeft,
      painter->fontMetrics().elidedText(label_, Qt::ElideRight,
                                        int(textRect.width())));
}

QVariant FlowNodeItem::itemChange(GraphicsItemChange change,
                                  const QVariant& value) {
  if (change == ItemPositionHasChanged) {
    if (auto* sc = qobject_cast<FlowScene*>(scene())) sc->notifyMoved(this);
  }
  return QGraphicsObject::itemChange(change, value);
}

FlowEdgeItem::FlowEdgeItem(const QString& id, FlowNodeItem* from, FlowNodeItem* to,
                           const QString& fromPort, const QString& toPort)
    : id_(id), from_(from), to_(to), fromPort_(fromPort), toPort_(toPort) {
  setZValue(1);
  setPen(QPen(QColor(theme::ACCENT), 1.6));
  refresh();
}

void FlowEdgeItem::refresh() {
  if (!from_ || !to_) return;
  const QPointF a = from_->portScenePos(fromPort_, true);
  const QPointF b = to_->portScenePos(toPort_, false);
  QPainterPath path(a);
  const qreal dy = qAbs(b.y() - a.y());
  const qreal cx = qMax(40.0, dy * 0.45);
  if (fromPort_ == QLatin1String("bottom") && toPort_ == QLatin1String("top")) {
    path.cubicTo(a + QPointF(0, cx), b - QPointF(0, cx), b);
  } else {
    path.cubicTo(a + QPointF(cx, 0), b - QPointF(cx, 0), b);
  }
  setPath(path);
}

FlowScene::FlowScene(QObject* parent) : QGraphicsScene(parent) {
  setSceneRect(-500, -200, 3000, 2500);
  connect(this, &QGraphicsScene::selectionChanged, this, [this]() {
    emit nodeSelected(selectedNodeId());
  });
}

void FlowScene::clearGraph() {
  clear();
  nodes_.clear();
  edges_.clear();
}

void FlowScene::loadDocument(SieansDocument* doc) {
  clearGraph();
  doc_ = doc;
  if (!doc) return;

  auto* source = new FlowNodeItem(QStringLiteral("source"),
                                  QStringLiteral("0 图像源1"), true);
  source->setPos(doc->sourcePosition());
  addItem(source);
  nodes_.insert(QStringLiteral("source"), source);

  for (const FlowStep& s : doc->steps()) {
    auto* n = new FlowNodeItem(s.id, s.name, false);
    n->setPos(s.position);
    n->setRunState(s.runState);
    addItem(n);
    nodes_.insert(s.id, n);
  }

  for (const FlowEdge& e : doc->edges()) {
    FlowNodeItem* a = nodes_.value(e.from);
    FlowNodeItem* b = nodes_.value(e.to);
    if (!a || !b) continue;
    auto* edge = new FlowEdgeItem(e.id, a, b, e.fromPort, e.toPort);
    addItem(edge);
    edges_.push_back(edge);
  }
}

void FlowScene::setNodeRunState(const QString& id, const QString& state,
                                const QColor& badge) {
  if (auto* n = nodes_.value(id)) n->setRunState(state, badge);
  if (doc_) {
    if (auto* s = doc_->findStep(id)) s->runState = state;
  }
}

void FlowScene::resetRunStates() {
  for (auto it = nodes_.begin(); it != nodes_.end(); ++it) {
    if (it.key() == QLatin1String("source")) continue;
    it.value()->setRunState(QStringLiteral("等待执行"));
  }
}

FlowNodeItem* FlowScene::selectedNode() const {
  const auto items = selectedItems();
  for (QGraphicsItem* it : items) {
    if (auto* n = dynamic_cast<FlowNodeItem*>(it)) return n;
  }
  return nullptr;
}

QString FlowScene::selectedNodeId() const {
  if (auto* n = selectedNode()) return n->nodeId();
  return {};
}

void FlowScene::notifyMoved(FlowNodeItem* node) {
  for (FlowEdgeItem* e : edges_) {
    if (e->fromNode() == node || e->toNode() == node) e->refresh();
  }
  if (doc_ && node) {
    if (node->nodeId() == QLatin1String("source")) {
      // source position kept in document on save via raw; update steps only
    } else if (auto* s = doc_->findStep(node->nodeId())) {
      s->position = node->pos();
    }
    emit nodeMoved(node->nodeId(), node->pos());
  }
}

void FlowScene::drawBackground(QPainter* painter, const QRectF& rect) {
  painter->fillRect(rect, QColor(theme::CANVAS));
  const int grid = 20;
  QPen pen(QColor(theme::CANVAS_DOT), 1);
  pen.setCosmetic(true);
  painter->setPen(pen);
  const int left = int(std::floor(rect.left() / grid) * grid);
  const int top = int(std::floor(rect.top() / grid) * grid);
  for (int x = left; x < rect.right(); x += grid) {
    for (int y = top; y < rect.bottom(); y += grid) {
      painter->drawPoint(x, y);
    }
  }
}

void FlowScene::mousePressEvent(QGraphicsSceneMouseEvent* event) {
  QGraphicsScene::mousePressEvent(event);
  if (!itemAt(event->scenePos(), QTransform())) {
    clearSelection();
    emit canvasBackgroundClicked();
  }
}

FlowView::FlowView(FlowScene* scene, QWidget* parent)
    : QGraphicsView(scene, parent) {
  setRenderHints(QPainter::Antialiasing | QPainter::TextAntialiasing);
  setDragMode(QGraphicsView::RubberBandDrag);
  setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
  setFrameShape(QFrame::NoFrame);
  setBackgroundBrush(QColor(theme::CANVAS));
}

void FlowView::fitAll() {
  if (!scene() || scene()->items().isEmpty()) return;
  fitInView(scene()->itemsBoundingRect().adjusted(-40, -40, 40, 40),
            Qt::KeepAspectRatio);
}

void FlowView::wheelEvent(QWheelEvent* event) {
  const qreal factor = event->angleDelta().y() > 0 ? 1.12 : (1.0 / 1.12);
  scale(factor, factor);
}

}  // namespace sieans_qt
