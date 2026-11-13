#include "FlowCanvas.hpp"
#include "FlowMinimap.hpp"

#include "Theme.hpp"
#include <QMimeData>
#include <QDragEnterEvent>
#include <QDropEvent>

#include <QGraphicsSceneMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QFont>
#include <QApplication>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QClipboard>
#include <QGuiApplication>
#include <QToolTip>
#include <QCursor>
#include <QLabel>
#include <QPushButton>
#include <QHBoxLayout>
#include <QWhatsThis>
#include <QWidget>
#include <QSizePolicy>
#include <QUuid>
#include <QMenu>
#include <QGraphicsSimpleTextItem>
#include <QGraphicsSceneContextMenuEvent>
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
           state.contains(QStringLiteral("失败")) ||
           state.contains(QStringLiteral("未配置")))
    badgeColor_ = QColor(QStringLiteral("#e53935"));
  else if (state.contains(QStringLiteral("运行")))
    badgeColor_ = QColor(theme::WARN);
  else if (state.contains(QStringLiteral("跳过")))
    badgeColor_ = QColor(theme::TEXT_DIM);
  else
    badgeColor_ = QColor(theme::ACCENT);
  setToolTip(QStringLiteral("%1\n状态：%2").arg(label_, runState_));
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
  QPen pen(border, selected ? 2.0 : 1.1);
  painter->setPen(pen);
  painter->setBrush(fill);
  painter->drawRoundedRect(QRectF(0, 0, kWidth, kHeight), 4, 4);
  if (selected) {
    painter->setPen(Qt::NoPen);
    painter->setBrush(QColor(theme::ACCENT));
    painter->drawRoundedRect(QRectF(0, 0, 3, kHeight), 1, 1);
  }

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

  painter->setRenderHint(QPainter::TextAntialiasing, true);
  painter->setPen(QColor(QStringLiteral("#222222")));
  QFont font = QApplication::font();
  font.setPointSize(9);
  font.setWeight(QFont::Medium);
  painter->setFont(font);
  const bool showState =
      !runState_.isEmpty() && runState_ != QStringLiteral("等待执行");
  const qreal stateW = showState ? 46.0 : 8.0;
  const QRectF textRect(28, 0, kWidth - 28 - stateW, kHeight);
  painter->drawText(
      textRect, Qt::AlignVCenter | Qt::AlignLeft,
      painter->fontMetrics().elidedText(label_, Qt::ElideRight,
                                        int(textRect.width())));
  if (showState) {
    painter->setPen(badgeColor_);
    QFont sf = font;
    sf.setPointSize(8);
    sf.setBold(true);
    painter->setFont(sf);
    const QString st =
        painter->fontMetrics().elidedText(runState_, Qt::ElideRight, int(stateW));
    painter->drawText(QRectF(kWidth - stateW - 4, 0, stateW, kHeight),
                      Qt::AlignVCenter | Qt::AlignRight, st);
  }
  // Right-edge run-state chrome
  QColor strip = badgeColor_;
  strip.setAlpha(210);
  painter->setPen(Qt::NoPen);
  painter->setBrush(strip);
  painter->drawRoundedRect(QRectF(kWidth - 5, 3, 3, kHeight - 6), 1, 1);
  if (runState_.contains(QStringLiteral("未配置"))) {
    painter->setPen(QColor(QStringLiteral("#e53935")));
    QFont bang = font;
    bang.setBold(true);
    bang.setPointSize(12);
    painter->setFont(bang);
    painter->drawText(QRectF(kWidth - 16, 0, 14, kHeight), Qt::AlignCenter,
                      QStringLiteral("!"));
  } else if (runState_.contains(QStringLiteral("运行"))) {
    painter->setPen(QColor(theme::WARN));
    painter->setBrush(Qt::NoBrush);
    painter->setPen(QPen(QColor(theme::WARN), 1.6));
    painter->drawRoundedRect(QRectF(1.5, 1.5, kWidth - 3, kHeight - 3), 3, 3);
  } else if (runState_.startsWith(QStringLiteral("OK")) ||
             runState_ == QStringLiteral("完成")) {
    // tiny OK tick in badge already colored; keep strip
  }
}

QVariant FlowNodeItem::itemChange(GraphicsItemChange change,
                                  const QVariant& value) {
  if (change == ItemPositionHasChanged) {
    if (auto* sc = qobject_cast<FlowScene*>(scene())) sc->notifyMoved(this);
  }
  return QGraphicsObject::itemChange(change, value);
}

// ── Edge ─────────────────────────────────────────────────────────────

static QString whenLabelText(const QString& when) {
  if (when.isEmpty() || when == QLatin1String("always")) return {};
  if (when == QLatin1String("true")) return QStringLiteral("成立");
  if (when == QLatin1String("false")) return QStringLiteral("不成立");
  if (when == QLatin1String("success")) return QStringLiteral("成功时");
  if (when == QLatin1String("error")) return QStringLiteral("失败时");
  return when;
}

static QColor whenPenColor(const QString& when) {
  if (when == QLatin1String("true")) return QColor(theme::OK);
  if (when == QLatin1String("false")) return QColor(theme::NG);
  if (when == QLatin1String("error")) return QColor(theme::NG);
  if (when == QLatin1String("success")) return QColor(theme::OK);
  return QColor(theme::ACCENT);
}

FlowEdgeItem::FlowEdgeItem(const QString& id, FlowNodeItem* from, FlowNodeItem* to,
                           const QString& fromPort, const QString& toPort,
                           const QString& when)
    : id_(id), from_(from), to_(to), fromPort_(fromPort), toPort_(toPort),
      when_(when.isEmpty() ? QStringLiteral("always") : when) {
  setZValue(1);
  setFlag(ItemIsSelectable);
  label_ = new QGraphicsSimpleTextItem(this);
  QFont f = label_->font();
  f.setPointSize(8);
  f.setBold(true);
  label_->setFont(f);
  updateWhenChrome();
  refresh();
}

void FlowEdgeItem::setWhen(const QString& when) {
  when_ = when.isEmpty() ? QStringLiteral("always") : when;
  updateWhenChrome();
  refresh();
}

void FlowEdgeItem::updateWhenChrome() {
  setPen(QPen(isSelected() ? QColor(theme::ACCENT) : whenPenColor(when_),
              isSelected() ? 2.4 : 1.6));
  const QString text = whenLabelText(when_);
  if (label_) {
    label_->setText(text);
    label_->setBrush(whenPenColor(when_));
    label_->setVisible(!text.isEmpty());
  }
  const QString tipWhen = text.isEmpty() ? QStringLiteral("始终") : text;
  setToolTip(QStringLiteral("连线 · %1 · 右键设置触发条件 · Delete 删除").arg(tipWhen));
}

QVariant FlowEdgeItem::itemChange(GraphicsItemChange change, const QVariant& value) {
  if (change == ItemSelectedHasChanged) updateWhenChrome();
  return QGraphicsPathItem::itemChange(change, value);
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
  if (label_ && label_->isVisible()) {
    const QPointF mid = path.pointAtPercent(0.5);
    label_->setPos(mid + QPointF(6, -8));
  }
}

void FlowEdgeItem::mousePressEvent(QGraphicsSceneMouseEvent* event) {
  setSelected(true);
  QGraphicsPathItem::mousePressEvent(event);
}

void FlowEdgeItem::contextMenuEvent(QGraphicsSceneContextMenuEvent* event) {
  auto* sc = qobject_cast<FlowScene*>(scene());
  QMenu menu;
  auto addWhen = [&](const QString& value, const QString& title) {
    QAction* act = menu.addAction(title);
    act->setCheckable(true);
    act->setChecked(when_ == value);
    QObject::connect(act, &QAction::triggered, [this, sc, value]() {
      setWhen(value);
      if (sc) emit sc->edgeWhenChanged(id_, value);
    });
  };
  addWhen(QStringLiteral("always"), QStringLiteral("始终（正常完成后）"));
  addWhen(QStringLiteral("success"), QStringLiteral("成功时"));
  addWhen(QStringLiteral("error"), QStringLiteral("失败时"));
  bool isCondition = false;
  bool isBranch = false;
  QVariantList paths;
  if (sc) {
    // Peek document through friend access in this method? FlowEdgeItem is not a friend.
    // Use dynamic property stored on the from node? We'll set node operation via tooltip...
    // FlowScene is friend of itself; we'll query via a helper on FlowScene later.
  }
  if (from_ && from_->data(Qt::UserRole + 2).isValid()) {
    const QString op = from_->data(Qt::UserRole + 2).toString();
    isCondition = (op == QLatin1String("condition"));
    isBranch = (op == QLatin1String("branch"));
    paths = from_->data(Qt::UserRole + 3).toList();
  }
  if (isCondition) {
    menu.addSeparator();
    addWhen(QStringLiteral("true"), QStringLiteral("判断成立时"));
    addWhen(QStringLiteral("false"), QStringLiteral("判断不成立时"));
  }
  if (isBranch) {
    menu.addSeparator();
    for (const QVariant& pv : paths) {
      const QVariantMap path = pv.toMap();
      const QString name = path.value(QStringLiteral("name")).toString();
      const QString id = path.value(QStringLiteral("id")).toString();
      const QString key = name.isEmpty() ? id : name;
      if (key.isEmpty()) continue;
      addWhen(key, QStringLiteral("路径：%1").arg(key));
    }
  }
  menu.exec(event->screenPos());
  event->accept();
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
    n->setData(Qt::UserRole + 2, s.operation);
    n->setData(Qt::UserRole + 3, s.params.value(QStringLiteral("paths")));
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
    auto* edge = new FlowEdgeItem(e.id, a, b, e.fromPort, e.toPort, e.when);
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

void FlowScene::setEditingLocked(bool locked) {
  editingLocked_ = locked;
  for (FlowNodeItem* node : nodes_) {
    node->setFlag(QGraphicsItem::ItemIsMovable, !locked);
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

void FlowScene::selectNode(const QString& id) {
  clearSelection();
  if (id.isEmpty()) return;
  FlowNodeItem* n = nodes_.value(id, nullptr);
  if (!n) return;
  n->setSelected(true);
  for (QGraphicsView* v : views()) v->ensureVisible(n);
  emit nodeSelected(id);
}

void FlowScene::setNodeLabel(const QString& id, const QString& label) {
  if (auto* n = nodes_.value(id, nullptr)) n->setLabel(label);
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
  if (editingLocked_) {
    emit linkNotice(QStringLiteral("运行模式已锁定画布"));
    return;
  }
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
  auto& edges = doc_->edgesMut();
  const FlowStep* inStep = doc_->findStep(inId);
  const bool mergeTarget =
      inStep && inStep->operation == QLatin1String("branch_merge");
  // Ordinary nodes keep a single image subscription; 分支汇合 accepts many inputs.
  if (!mergeTarget) {
    edges.erase(std::remove_if(edges.begin(), edges.end(),
                               [&](const FlowEdge& e) { return e.to == inId; }),
                edges.end());
  } else {
    edges.erase(std::remove_if(edges.begin(), edges.end(),
                               [&](const FlowEdge& e) {
                                 return e.from == outId && e.to == inId;
                               }),
                edges.end());
  }
  FlowEdge ne;
  ne.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  ne.from = outId;
  ne.to = inId;
  ne.fromPort = outPort;
  ne.toPort = inPort;
  ne.when = QStringLiteral("always");
  const FlowStep* outStep = doc_->findStep(outId);
  if (outStep && outStep->operation == QLatin1String("condition")) {
    bool hasTrue = false, hasFalse = false;
    for (const FlowEdge& e : edges) {
      if (e.from != outId) continue;
      if (e.when == QLatin1String("true")) hasTrue = true;
      if (e.when == QLatin1String("false")) hasFalse = true;
    }
    if (!hasTrue) ne.when = QStringLiteral("true");
    else if (!hasFalse) ne.when = QStringLiteral("false");
  }
  edges.push_back(ne);
  if (FlowStep* s = doc_->findStep(inId)) s->imageFrom = outId;
  rebuildEdgesFromDoc();
  emit edgeConnected(outId, inId, outPort, inPort);
  const QString whenTxt = (ne.when == QLatin1String("true"))
                              ? QStringLiteral("成立")
                              : (ne.when == QLatin1String("false")
                                     ? QStringLiteral("不成立")
                                     : QString());
  emit linkNotice(whenTxt.isEmpty()
                      ? QStringLiteral("已建立连线")
                      : QStringLiteral("已建立连线 · %1").arg(whenTxt));
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
  } else if (event->button() == Qt::LeftButton && !linking_ && !editingLocked_) {
    if (FlowNodeItem* n = selectedNode()) {
      move_tracking_ = true;
      move_id_ = n->nodeId();
      move_origin_ = n->pos();
    }
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
  if (move_tracking_) {
    if (FlowNodeItem* n = nodes_.value(move_id_)) {
      if (n->pos() != move_origin_) emit nodeMoveFinished(move_id_, n->pos());
    }
    move_tracking_ = false;
    move_id_.clear();
  }
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
  if (event->key() == Qt::Key_A && (event->modifiers() & Qt::ControlModifier)) {
    for (auto* n : nodes_) {
      if (n) n->setSelected(true);
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F2) {
    if (editingLocked_) {
      emit linkNotice(QStringLiteral("运行模式已锁定画布"));
      event->accept();
      return;
    }
    const QString id = selectedNodeId();
    if (!id.isEmpty() && id != QLatin1String("source")) {
      emit renameRequested(id);
      event->accept();
      return;
    }
  }
  if (event->key() == Qt::Key_D && (event->modifiers() & Qt::ControlModifier)) {
    if (editingLocked_) {
      emit linkNotice(QStringLiteral("运行模式已锁定画布"));
      event->accept();
      return;
    }
    const QString id = selectedNodeId();
    if (!id.isEmpty() && id != QLatin1String("source")) {
      emit duplicateRequested(id);
      event->accept();
      return;
    }
    emit linkNotice(QStringLiteral("请先选中模块 · Ctrl+D"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace) {
    if (editingLocked_) {
      emit linkNotice(QStringLiteral("运行模式已锁定画布"));
      event->accept();
      return;
    }
    if (selectedEdge()) {
      removeSelectedEdge();
      event->accept();
      return;
    }
  }
  QGraphicsScene::keyPressEvent(event);
}

// ── View ─────────────────────────────────────────────────────────────

/** 画布完整快捷键说明，用于多行工具提示和 What's This，避免单行长条盖住左侧工具箱。 */
static QString flowViewKeymapHelp() {
  return QStringLiteral(
      "快捷键\n"
      "滚轮/+/- 缩放 · Alt+/- 微调\n"
      "F/G/A/Space/Home/0/R 适应画布\n"
      "Ctrl+Shift+F 适应选中\n"
      "F2 重命名 · Ctrl+A 全选节点\n"
      "Ctrl+C/Ctrl+Shift+C 复制选中节点\n"
      "Ctrl+D 复制模块\n"
      "中键/空白右键适应\n"
      "Del/Backspace 删连线\n"
      "Esc 取消连线\n"
      "I 打开 I/O");
}

FlowView::FlowView(FlowScene* scene, QWidget* parent)
    : QGraphicsView(scene, parent) {
  // 视图本体只用短提示；完整键表走底栏多行 tooltip / What's This，避免再弹出超宽顶层提示。
  setToolTip(QStringLiteral("流程画布 · 滚轮缩放 · F 适应 · I 打开 I/O"));
  setStatusTip(QStringLiteral("流程画布 · F/G/A/Space/Home/0/R 适应 · I→I/O · +/- 缩放 · Ctrl+C 节点 · Ctrl+D 复制模块 · 中键适应 · Esc 取消连线 · Del/Backspace 删连线 · 滚轮缩放"));
  setWhatsThis(flowViewKeymapHelp());
  setRenderHints(QPainter::Antialiasing | QPainter::TextAntialiasing);
  setDragMode(QGraphicsView::RubberBandDrag);
  setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
  setFrameShape(QFrame::NoFrame);
  setBackgroundBrush(QColor(theme::CANVAS));
  setFocusPolicy(Qt::StrongFocus);
  setAcceptDrops(true);

  hintBar_ = new QWidget(this);
  hintBar_->setObjectName(QStringLiteral("flowCanvasHint"));
  hintBar_->setAutoFillBackground(true);
  hintBar_->setAttribute(Qt::WA_StyledBackground, true);
  hintBar_->setStyleSheet(
      QStringLiteral("QWidget#flowCanvasHint{background:#2d2f33;border:1px solid #4a4e54;}"
                     "QPushButton#flowCanvasHintHelp{min-height:16px;min-width:16px;padding:0;"
                     "font-weight:600;}"));
  auto* hintLay = new QHBoxLayout(hintBar_);
  hintLay->setContentsMargins(8, 2, 4, 2);
  hintLay->setSpacing(4);
  auto* hintLabel = new QLabel(QStringLiteral("滚轮缩放 · F 适应 · I 打开 I/O · ? 全部快捷键"));
  hintLabel->setObjectName(QStringLiteral("muted"));
  hintLabel->setTextInteractionFlags(Qt::NoTextInteraction);
  hintLabel->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
  hintLabel->setMinimumWidth(0);
  hintLabel->setToolTip(flowViewKeymapHelp());
  hintLabel->setWhatsThis(flowViewKeymapHelp());
  auto* help = new QPushButton(QStringLiteral("?"));
  help->setObjectName(QStringLiteral("flowCanvasHintHelp"));
  help->setFixedSize(22, 22);
  help->setCursor(Qt::PointingHandCursor);
  help->setFocusPolicy(Qt::NoFocus);
  help->setToolTip(flowViewKeymapHelp());
  help->setWhatsThis(flowViewKeymapHelp());
  QObject::connect(help, &QPushButton::clicked, hintBar_, [help]() {
    QWhatsThis::showText(help->mapToGlobal(QPoint(0, help->height())), help->whatsThis(),
                         help);
  });
  hintLay->addWidget(hintLabel, 1);
  hintLay->addWidget(help, 0, Qt::AlignVCenter);

  minimap_ = new FlowMinimap(scene, this, this);
  placeMinimap();
}


/** 适应画布：能放下就放下；过大时不缩到标签不可读，而是按最小比例对准流程顶部。 */
void FlowView::fitAll() {
  if (!scene() || scene()->items().isEmpty()) return;
  const QRectF br = scene()->itemsBoundingRect().adjusted(-40, -40, 40, 40);
  if (!br.isValid() || br.width() < 1.0 || br.height() < 1.0) return;
  fitInView(br, Qt::KeepAspectRatio);
  const qreal s = transform().m11();
  constexpr qreal kMin = 0.72;
  constexpr qreal kMax = 1.25;
  if (s >= kMin && s <= kMax) return;
  QTransform xf;
  const qreal target = qBound(kMin, s, kMax);
  xf.scale(target, target);
  setTransform(xf);
  const QRectF vis = mapToScene(viewport()->rect()).boundingRect();
  centerOn(QPointF(br.center().x(), br.top() + vis.height() * 0.42));
}

void FlowView::wheelEvent(QWheelEvent* event) {
  const qreal factor = event->angleDelta().y() > 0 ? 1.12 : (1.0 / 1.12);
  scale(factor, factor);
  if (minimap_) minimap_->update();
}

void FlowView::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_I) {
    emit ioRequested();
    event->accept();
    return;
  }
  if (((event->key() == Qt::Key_F || event->key() == Qt::Key_Home ||
        event->key() == Qt::Key_0 || event->key() == Qt::Key_R ||
        event->key() == Qt::Key_G || event->key() == Qt::Key_A ||
        event->key() == Qt::Key_Space) &&
       !(event->modifiers() & Qt::ControlModifier))) {
    fitAll();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Plus || event->key() == Qt::Key_Equal) {
    const qreal f = (event->modifiers() & Qt::AltModifier) ? 1.04 : 1.12;
    scale(f, f);
    if (minimap_) minimap_->update();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Minus) {
    const qreal f = (event->modifiers() & Qt::AltModifier) ? 1.04 : 1.12;
    scale(1.0 / f, 1.0 / f);
    if (minimap_) minimap_->update();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    if (auto* sc = qobject_cast<FlowScene*>(scene())) {
      QRectF r;
      for (QGraphicsItem* it : sc->selectedItems()) {
        if (dynamic_cast<FlowNodeItem*>(it))
          r = r.isNull() ? it->sceneBoundingRect() : r.united(it->sceneBoundingRect());
      }
      if (!r.isNull()) {
        fitInView(r.adjusted(-40, -40, 40, 40), Qt::KeepAspectRatio);
        if (minimap_) minimap_->update();
        QToolTip::showText(QCursor::pos(), QStringLiteral("适应选中 · Ctrl+Shift+F"), this);
      } else {
        fitAll();
      }
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_C && (event->modifiers() & Qt::ControlModifier)) {
    if (auto* sc = qobject_cast<FlowScene*>(scene())) {
      QStringList ids;
      for (QGraphicsItem* it : sc->selectedItems()) {
        if (auto* n = dynamic_cast<FlowNodeItem*>(it)) {
          if (event->modifiers() & Qt::ShiftModifier)
            ids << n->nodeId();
          else
            ids << QStringLiteral("%1\t%2").arg(n->nodeId(), n->label());
        }
      }
      if (!ids.isEmpty()) {
        if (auto* clip = QGuiApplication::clipboard())
          clip->setText(ids.join(QLatin1Char('\n')));
        QToolTip::showText(QCursor::pos(),
                           QStringLiteral("已复制节点 %1 · Ctrl+C").arg(ids.size()), this);
      }
      event->accept();
      return;
    }
  }
  if (auto* sc = qobject_cast<FlowScene*>(scene())) {
    if (event->key() == Qt::Key_Escape || event->key() == Qt::Key_Delete ||
        event->key() == Qt::Key_Backspace ||
        (event->key() == Qt::Key_D && (event->modifiers() & Qt::ControlModifier)) ||
        event->key() == Qt::Key_F2 ||
        (event->key() == Qt::Key_A && (event->modifiers() & Qt::ControlModifier))) {
      sc->handleKey(event);
      if (event->isAccepted()) return;
    }
  }
  QGraphicsView::keyPressEvent(event);
}


void FlowView::mousePressEvent(QMouseEvent* event) {
  if (event->button() == Qt::MiddleButton) {
    fitAll();
    event->accept();
    return;
  }
  if (event->button() == Qt::RightButton && !(event->modifiers() & Qt::ControlModifier)) {
    // empty canvas right-click → fit (ports/nodes still get scene handlers via itemAt)
    if (!itemAt(event->position().toPoint())) {
      fitAll();
      event->accept();
      return;
    }
  }
  QGraphicsView::mousePressEvent(event);
}

void FlowView::dragEnterEvent(QDragEnterEvent* event) {
  if (auto* sc = qobject_cast<FlowScene*>(scene())) {
    if (sc->editingLocked()) {
      event->ignore();
      return;
    }
  }
  if (event->mimeData() &&
      event->mimeData()->hasFormat(QStringLiteral("application/x-sieans-operator"))) {
    event->setDropAction(Qt::CopyAction);
    event->accept();
    return;
  }
  event->ignore();
}

void FlowView::dragMoveEvent(QDragMoveEvent* event) {
  if (event->mimeData() &&
      event->mimeData()->hasFormat(QStringLiteral("application/x-sieans-operator"))) {
    event->setDropAction(Qt::CopyAction);
    event->accept();
    return;
  }
  event->ignore();
}

void FlowView::dropEvent(QDropEvent* event) {
  if (auto* sc = qobject_cast<FlowScene*>(scene())) {
    if (sc->editingLocked()) {
      event->ignore();
      return;
    }
  }
  if (!event->mimeData() ||
      !event->mimeData()->hasFormat(QStringLiteral("application/x-sieans-operator"))) {
    event->ignore();
    return;
  }
  const QString key = QString::fromUtf8(
      event->mimeData()->data(QStringLiteral("application/x-sieans-operator"))).trimmed();
  if (key.isEmpty()) {
    event->ignore();
    return;
  }
  const QPointF sp = mapToScene(event->position().toPoint());
  emit operatorDropped(key, sp);
  event->setDropAction(Qt::CopyAction);
  event->accept();
}

/** 把概览和快捷键摘要都放回本视图客户区，避免子控件画出画布外。 */
void FlowView::placeMinimap() {
  if (minimap_) {
    const int m = 8;
    minimap_->move(width() - minimap_->width() - m, height() - minimap_->height() - m);
    minimap_->update();
  }
  placeHintBar();
  if (minimap_) minimap_->raise();
}

/** 将快捷键摘要条贴在画布底部并夹在本视图宽度内，不按文案撑开。 */
void FlowView::placeHintBar() {
  if (!hintBar_) return;
  const int m = 8;
  // 右下角留给概览；宽度按本视图计算，不按文案 sizeHint 撑开。
  const int reserve = (minimap_ && minimap_->isVisible()) ? (minimap_->width() + m) : 0;
  const int barH = qMax(hintBar_->sizeHint().height(), 22);
  const int barW = qMax(0, width() - m * 2 - reserve);
  hintBar_->setGeometry(m, height() - barH - m, barW, barH);
  hintBar_->raise();
}

void FlowView::resizeEvent(QResizeEvent* event) {
  QGraphicsView::resizeEvent(event);
  placeMinimap();
}

}  // namespace sieans_qt
