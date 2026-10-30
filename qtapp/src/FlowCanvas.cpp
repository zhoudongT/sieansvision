#include "FlowCanvas.hpp"

#include "Theme.hpp"

#include <QGraphicsSceneMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QFont>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QUuid>
#include <algorithm>
#include <QtMath>
#include <cmath>

namespace sieans_qt {

// ── Port ─────────────────────────────────────────────────────────────

FlowPortItem::FlowPortItem(FlowNodeItem* owner, const QString& side, bool output)
    : QGraphicsObject(owner), owner_(owner), side_(side), output_(output) {
  setZValue(4);
  setFlag(ItemIgnoresTransformations);
  setAcceptedMouseButtons(Qt::LeftButton);
  setCursor(Qt::CrossCursor);
  setToolTip(QStringLiteral("%1 · %2 — 拖到对端端口连线；Esc 取消")
                 .arg(output ? QStringLiteral("输出") : QStringLiteral("输入"),
                      side));
  const qreal w = FlowNodeItem::kWidth;
  const qreal h = FlowNodeItem::kHeight;
  if (side == QLatin1String("top"))
    setPos(w / 2, 0);
  else if (side == QLatin1String("bottom"))
    setPos(w / 2, h);
  else if (side == QLatin1String("left"))
    setPos(0, h / 2);
  else
    setPos(w, h / 2);
}

void FlowPortItem::setHighlight(const QString& h) {
  if (highlight_ == h) return;
  highlight_ = h;
  update();
}

QRectF FlowPortItem::boundingRect() const { return QRectF(-7, -7, 14, 14); }

void FlowPortItem::paint(QPainter* painter, const QStyleOptionGraphicsItem*,
                         QWidget*) {
  QColor color(theme::ACCENT);
  if (side_ == QLatin1String("left") || side_ == QLatin1String("right"))
    color = QColor(QStringLiteral("#b0b0b0"));
  if (highlight_ == QLatin1String("valid"))
    color = QColor(theme::OK);
  else if (highlight_ == QLatin1String("invalid"))
    color = QColor(QStringLiteral("#d26345"));
  painter->setRenderHint(QPainter::Antialiasing);
  painter->setPen(QPen(color, highlight_.isEmpty() ? 1.0 : 1.4));
  painter->setBrush(output_ || highlight_ == QLatin1String("valid")
                        ? color
                        : QColor(QStringLiteral("#f5f5f5")));
  if (!highlight_.isEmpty())
    painter->drawEllipse(QRectF(-6, -6, 12, 12));
  painter->drawEllipse(QRectF(-3.5, -3.5, 7, 7));
}

void FlowPortItem::mousePressEvent(QGraphicsSceneMouseEvent* event) {
  if (event->button() == Qt::LeftButton) {
    if (auto* sc = qobject_cast<FlowScene*>(scene())) {
      if (sc->isLinking())
        sc->finishLink(this);
      else
        sc->startLink(this);
      event->accept();
      return;
    }
  }
  QGraphicsObject::mousePressEvent(event);
}

// ── Node ─────────────────────────────────────────────────────────────

FlowNodeItem::FlowNodeItem(const QString& id, const QString& label, bool isSource,
                           QGraphicsItem* parent)
    : QGraphicsObject(parent), id_(id), label_(label), source_(isSource) {
  setFlags(ItemIsMovable | ItemIsSelectable | ItemSendsGeometryChanges);
  setZValue(2);
  setToolTip(label + QStringLiteral("\n拖动移动 · 端口拖拽连线 · Delete 删连线"));
  badgeColor_ = QColor(theme::ACCENT);

  const QStringList sides = isSource
                                ? QStringList{QStringLiteral("bottom"),
                                              QStringLiteral("right")}
                                : QStringList{QStringLiteral("top"),
                                              QStringLiteral("bottom"),
                                              QStringLiteral("left"),
                                              QStringLiteral("right")};
  for (const QString& side : sides) {
    const bool out = (side == QLatin1String("bottom") ||
                      side == QLatin1String("right"));
    auto* p = new FlowPortItem(this, side, out);
    ports_.insert(side, p);
  }
}

void FlowNodeItem::setLabel(const QString& label) {
  label_ = label;
  update();
}

void FlowNodeItem::setRunState(const QString& state, const QColor& badge) {
  runState_ = state;
  if (badge.isValid())
    badgeColor_ = badge;
  else if (state.startsWith(QStringLiteral("OK")) ||
           state == QStringLiteral("完成"))
    badgeColor_ = QColor(theme::OK);
  else if (state.startsWith(QStringLiteral("NG")) ||
           state.contains(QStringLiteral("失败")))
    badgeColor_ = QColor(QStringLiteral("#e53935"));
  else if (state.contains(QStringLiteral("运行")))
    badgeColor_ = QColor(theme::WARN);
  else
    badgeColor_ = QColor(theme::ACCENT);
  update();
}

FlowPortItem* FlowNodeItem::port(const QString& side) const {
  return ports_.value(side);
}

QPointF FlowNodeItem::portScenePos(const QString& side) const {
  if (FlowPortItem* p = ports_.value(side)) return p->scenePos();
  return scenePos() + QPointF(kWidth / 2, kHeight / 2);
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

// ── Edge ─────────────────────────────────────────────────────────────

FlowEdgeItem::FlowEdgeItem(const QString& id, FlowNodeItem* from, FlowNodeItem* to,
                           const QString& fromPort, const QString& toPort)
    : id_(id), from_(from), to_(to), fromPort_(fromPort), toPort_(toPort) {
  setZValue(1);
  setFlag(ItemIsSelectable);
  setPen(QPen(QColor(theme::ACCENT), 1.6));
  setToolTip(QStringLiteral("连线 · Delete 删除"));
  refresh();
}

void FlowEdgeItem::refresh() {
  if (!from_ || !to_) return;
  const QPointF a = from_->portScenePos(fromPort_);
  const QPointF b = to_->portScenePos(toPort_);
  QPainterPath path(a);
  const qreal dy = qAbs(b.y() - a.y());
  const qreal cx = qMax(40.0, dy * 0.45);
  if (fromPort_ == QLatin1String("bottom") && toPort_ == QLatin1String("top")) {
    path.cubicTo(a + QPointF(0, cx), b - QPointF(0, cx), b);
  } else if (fromPort_ == QLatin1String("right") ||
             toPort_ == QLatin1String("left")) {
    const qreal mid = (a.x() + b.x()) / 2;
    path.lineTo(mid, a.y());
    path.lineTo(mid, b.y());
    path.lineTo(b);
  } else {
    path.cubicTo(a + QPointF(cx, 0), b - QPointF(cx, 0), b);
  }
  setPath(path);
}

void FlowEdgeItem::mousePressEvent(QGraphicsSceneMouseEvent* event) {
  setSelected(true);
  QGraphicsPathItem::mousePressEvent(event);
}

// ── Scene ────────────────────────────────────────────────────────────

FlowScene::FlowScene(QObject* parent) : QGraphicsScene(parent) {
  setSceneRect(-500, -200, 3000, 2500);
  connect(this, &QGraphicsScene::selectionChanged, this, [this]() {
    emit nodeSelected(selectedNodeId());
  });
}

void FlowScene::clearGraph() {
  cancelLink();
  clear();
  nodes_.clear();
  edges_.clear();
  linkPreview_ = nullptr;
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
  rebuildEdgesFromDoc();
}

void FlowScene::rebuildEdgesFromDoc() {
  for (FlowEdgeItem* e : edges_) {
    removeItem(e);
    delete e;
  }
  edges_.clear();
  if (!doc_) return;
  for (const FlowEdge& e : doc_->edges()) {
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
  for (QGraphicsItem* it : selectedItems()) {
    if (auto* n = dynamic_cast<FlowNodeItem*>(it)) return n;
  }
  return nullptr;
}

QString FlowScene::selectedNodeId() const {
  if (auto* n = selectedNode()) return n->nodeId();
  return {};
}

FlowEdgeItem* FlowScene::selectedEdge() const {
  for (QGraphicsItem* it : selectedItems()) {
    if (auto* e = dynamic_cast<FlowEdgeItem*>(it)) return e;
  }
  return nullptr;
}

void FlowScene::notifyMoved(FlowNodeItem* node) {
  for (FlowEdgeItem* e : edges_) {
    if (e->fromNode() == node || e->toNode() == node) e->refresh();
  }
  if (doc_ && node) {
    if (node->nodeId() != QLatin1String("source")) {
      if (auto* s = doc_->findStep(node->nodeId())) s->position = node->pos();
    }
    emit nodeMoved(node->nodeId(), node->pos());
  }
  if (linking_ && linkPreview_) {
    // keep preview if mid-drag from moved node — rare
  }
}

void FlowScene::startLink(FlowPortItem* port) {
  if (!port || !port->owner()) return;
  cancelLink();
  linking_ = true;
  linkNodeId_ = port->owner()->nodeId();
  linkSide_ = port->side();
  linkOutput_ = port->isOutput();
  linkPreview_ = addPath(QPainterPath(),
                         QPen(QColor(theme::ACCENT), 2, Qt::DashLine));
  linkPreview_->setZValue(100);
  linkPreview_->setAcceptedMouseButtons(Qt::NoButton);
  updateLinkPreview(port->scenePos(), nullptr);
  emit linkNotice(QStringLiteral("拖到另一模块的%1端口松开；Esc 取消")
                      .arg(linkOutput_ ? QStringLiteral("输入")
                                       : QStringLiteral("输出")));
}

void FlowScene::updateLinkPreview(const QPointF& scenePos, FlowPortItem* hover) {
  if (!linking_ || !linkPreview_) return;
  FlowNodeItem* origin = nodes_.value(linkNodeId_);
  if (!origin) {
    cancelLink();
    return;
  }
  const QPointF start = origin->portScenePos(linkSide_);
  for (auto it = nodes_.begin(); it != nodes_.end(); ++it) {
    for (const QString& side :
         {QStringLiteral("top"), QStringLiteral("bottom"), QStringLiteral("left"),
          QStringLiteral("right")}) {
      FlowPortItem* p = it.value()->port(side);
      if (!p) continue;
      QString hl;
      if (p == hover) {
        hl = (p->isOutput() != linkOutput_ &&
              p->owner()->nodeId() != linkNodeId_)
                 ? QStringLiteral("valid")
                 : QStringLiteral("invalid");
      }
      p->setHighlight(hl);
    }
  }
  const QPointF end = hover ? hover->scenePos() : scenePos;
  QPointF a = start, b = end;
  if (!linkOutput_) std::swap(a, b);
  QPainterPath path(a);
  const qreal midY = (a.y() + b.y()) / 2;
  path.lineTo(a.x(), midY);
  path.lineTo(b.x(), midY);
  path.lineTo(b);
  linkPreview_->setPath(path);
}

void FlowScene::finishLink(FlowPortItem* target) {
  if (!linking_) return;
  const QString fromId = linkNodeId_;
  const QString fromSide = linkSide_;
  const bool fromOut = linkOutput_;
  cancelLink();
  if (!target || !target->owner()) {
    emit linkNotice(QStringLiteral("已取消连线"));
    return;
  }
  if (target->isOutput() == fromOut) {
    emit linkNotice(QStringLiteral("请将输出端口连接到输入端口"));
    return;
  }
  if (target->owner()->nodeId() == fromId) {
    emit linkNotice(QStringLiteral("不能连到自身"));
    return;
  }
  QString outId, inId, outPort, inPort;
  if (fromOut) {
    outId = fromId;
    outPort = fromSide;
    inId = target->owner()->nodeId();
    inPort = target->side();
  } else {
    outId = target->owner()->nodeId();
    outPort = target->side();
    inId = fromId;
    inPort = fromSide;
  }
  if (!doc_) return;
  // Remove existing edge into same input (single subscription)
  auto& edges = doc_->edgesMut();
  edges.erase(std::remove_if(edges.begin(), edges.end(),
                             [&](const FlowEdge& e) { return e.to == inId; }),
              edges.end());
  FlowEdge ne;
  ne.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  ne.from = outId;
  ne.to = inId;
  ne.fromPort = outPort;
  ne.toPort = inPort;
  edges.push_back(ne);
  if (FlowStep* s = doc_->findStep(inId)) s->imageFrom = outId;
  rebuildEdgesFromDoc();
  emit edgeConnected(outId, inId, outPort, inPort);
  emit linkNotice(QStringLiteral("已建立连线"));
}

void FlowScene::cancelLink() {
  linking_ = false;
  linkNodeId_.clear();
  linkSide_.clear();
  if (linkPreview_) {
    removeItem(linkPreview_);
    delete linkPreview_;
    linkPreview_ = nullptr;
  }
  for (auto it = nodes_.begin(); it != nodes_.end(); ++it) {
    for (const QString& side :
         {QStringLiteral("top"), QStringLiteral("bottom"), QStringLiteral("left"),
          QStringLiteral("right")}) {
      if (FlowPortItem* p = it.value()->port(side)) p->setHighlight({});
    }
  }
}

FlowPortItem* FlowScene::portAt(const QPointF& scenePos) const {
  const QList<QGraphicsItem*> hits = items(scenePos);
  for (QGraphicsItem* it : hits) {
    if (auto* p = dynamic_cast<FlowPortItem*>(it)) return p;
  }
  // nearby search
  const QRectF r(scenePos.x() - 10, scenePos.y() - 10, 20, 20);
  for (QGraphicsItem* it : items(r)) {
    if (auto* p = dynamic_cast<FlowPortItem*>(it)) return p;
  }
  return nullptr;
}

void FlowScene::removeSelectedEdge() {
  if (FlowEdgeItem* e = selectedEdge()) removeEdgeById(e->edgeId());
}

void FlowScene::removeEdgeById(const QString& edgeId) {
  if (!doc_ || edgeId.isEmpty()) return;
  auto& edges = doc_->edgesMut();
  edges.erase(std::remove_if(edges.begin(), edges.end(),
                             [&](const FlowEdge& e) { return e.id == edgeId; }),
              edges.end());
  rebuildEdgesFromDoc();
  emit edgeRemoved(edgeId);
  emit linkNotice(QStringLiteral("已删除连线"));
}

void FlowScene::drawBackground(QPainter* painter, const QRectF& rect) {
  painter->fillRect(rect, QColor(theme::CANVAS));
  const int grid = 20;
  QPen pen(QColor(theme::CANVAS_DOT), 1);
  pen.setCosmetic(true);
  painter->setPen(pen);
  const int left = int(std::floor(rect.left() / grid) * grid);
  const int top = int(std::floor(rect.top() / grid) * grid);
  const int maxSpan = grid * 256;
  const int right = std::min(int(rect.right()), left + maxSpan);
  const int bottom = std::min(int(rect.bottom()), top + maxSpan);
  for (int x = left; x < right; x += grid) {
    for (int y = top; y < bottom; y += grid) {
      painter->drawPoint(x, y);
    }
  }
}

void FlowScene::mousePressEvent(QGraphicsSceneMouseEvent* event) {
  if (event->button() == Qt::LeftButton) {
    if (FlowPortItem* p = portAt(event->scenePos())) {
      if (linking_)
        finishLink(p);
      else
        startLink(p);
      event->accept();
      return;
    }
  }
  QGraphicsScene::mousePressEvent(event);
  if (!itemAt(event->scenePos(), QTransform()) && !linking_) {
    clearSelection();
    emit canvasBackgroundClicked();
  }
}

void FlowScene::mouseMoveEvent(QGraphicsSceneMouseEvent* event) {
  if (linking_) {
    updateLinkPreview(event->scenePos(), portAt(event->scenePos()));
    event->accept();
    return;
  }
  QGraphicsScene::mouseMoveEvent(event);
}

void FlowScene::mouseReleaseEvent(QGraphicsSceneMouseEvent* event) {
  if (linking_ && event->button() == Qt::LeftButton) {
    FlowPortItem* p = portAt(event->scenePos());
    if (p && (p->owner()->nodeId() != linkNodeId_ || p->side() != linkSide_))
      finishLink(p);
    // if released on empty / same port, keep linking until second click or Esc
    event->accept();
    return;
  }
  QGraphicsScene::mouseReleaseEvent(event);
}

void FlowScene::handleKey(QKeyEvent* event) {
  keyPressEvent(event);
}

void FlowScene::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_Escape && linking_) {
    cancelLink();
    emit linkNotice(QStringLiteral("已取消连线"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace) {
    if (selectedEdge()) {
      removeSelectedEdge();
      event->accept();
      return;
    }
  }
  QGraphicsScene::keyPressEvent(event);
}

// ── View ─────────────────────────────────────────────────────────────

FlowView::FlowView(FlowScene* scene, QWidget* parent)
    : QGraphicsView(scene, parent) {
  setRenderHints(QPainter::Antialiasing | QPainter::TextAntialiasing);
  setDragMode(QGraphicsView::RubberBandDrag);
  setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
  setFrameShape(QFrame::NoFrame);
  setBackgroundBrush(QColor(theme::CANVAS));
  setFocusPolicy(Qt::StrongFocus);
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

void FlowView::keyPressEvent(QKeyEvent* event) {
  if (auto* sc = qobject_cast<FlowScene*>(scene())) {
    if (event->key() == Qt::Key_Escape || event->key() == Qt::Key_Delete ||
        event->key() == Qt::Key_Backspace) {
      sc->handleKey(event);
      if (event->isAccepted()) return;
    }
  }
  QGraphicsView::keyPressEvent(event);
}

}  // namespace sieans_qt
