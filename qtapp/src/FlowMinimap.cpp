#include "FlowMinimap.hpp"
#include "FlowCanvas.hpp"
#include "Theme.hpp"

#include <QEvent>
#include <QMouseEvent>
#include <QPaintEvent>
#include <QPainter>
#include <QPen>

namespace sieans_qt {

FlowMinimap::FlowMinimap(QGraphicsScene* scene, QGraphicsView* view, QWidget* parent)
    : QWidget(parent), scene_(scene), view_(view) {
  setObjectName(QStringLiteral("flowMinimap"));
  setFixedSize(180, 120);
  setCursor(Qt::OpenHandCursor);
  setToolTip(QStringLiteral("流程概览 · 拖拽平移视口 · 橙框=当前视野"));
  setStatusTip(QStringLiteral("Minimap · 拖拽平移 · 点击定位 · 橙框=当前视野"));
  setAttribute(Qt::WA_TransparentForMouseEvents, false);
  setMouseTracking(true);
  if (scene_) connect(scene_, &QGraphicsScene::changed, this, [this](const QList<QRectF>&) { update(); });
  if (view_ && view_->viewport()) view_->viewport()->installEventFilter(this);
}

void FlowMinimap::setScene(QGraphicsScene* scene) {
  if (scene_ == scene) return;
  if (scene_) disconnect(scene_, nullptr, this, nullptr);
  scene_ = scene;
  if (scene_) connect(scene_, &QGraphicsScene::changed, this, [this](const QList<QRectF>&) { update(); });
  update();
}

void FlowMinimap::setView(QGraphicsView* view) {
  if (view_ && view_->viewport()) view_->viewport()->removeEventFilter(this);
  view_ = view;
  if (view_ && view_->viewport()) view_->viewport()->installEventFilter(this);
  update();
}

bool FlowMinimap::eventFilter(QObject* obj, QEvent* event) {
  if (view_ && obj == view_->viewport()) {
    switch (event->type()) {
      case QEvent::Resize:
      case QEvent::Wheel:
      case QEvent::MouseButtonRelease:
      case QEvent::MouseMove:
      case QEvent::Paint:
        update();
        break;
      default:
        break;
    }
  }
  return QWidget::eventFilter(obj, event);
}

bool FlowMinimap::mapMetrics(QRectF* bounds, qreal* scale, qreal* ox, qreal* oy) const {
  if (!scene_ || !bounds || !scale || !ox || !oy) return false;
  *bounds = scene_->itemsBoundingRect().adjusted(-40, -40, 40, 40);
  if (bounds->width() < 1 || bounds->height() < 1) return false;
  *scale = qMin((width() - 8) / bounds->width(), (height() - 8) / bounds->height());
  *ox = (width() - bounds->width() * (*scale)) / 2.0;
  *oy = (height() - bounds->height() * (*scale)) / 2.0;
  return true;
}

void FlowMinimap::panTo(const QPointF& widgetPos) {
  QRectF bounds;
  qreal scale = 1, ox = 0, oy = 0;
  if (!mapMetrics(&bounds, &scale, &ox, &oy) || !view_) return;
  const qreal sx = bounds.x() + (widgetPos.x() - ox) / scale;
  const qreal sy = bounds.y() + (widgetPos.y() - oy) / scale;
  view_->centerOn(sx, sy);
  emit navigate(sx, sy);
  update();
}

void FlowMinimap::paintEvent(QPaintEvent*) {
  QPainter painter(this);
  painter.setRenderHint(QPainter::Antialiasing);
  painter.fillRect(rect(), QColor(theme::RAIL_BG));
  painter.setPen(QPen(QColor(theme::LINE), 1));
  painter.drawRect(0, 0, width() - 1, height() - 1);

  QRectF bounds;
  qreal scale = 1, ox = 0, oy = 0;
  if (!mapMetrics(&bounds, &scale, &ox, &oy)) {
    painter.setPen(QColor(theme::TEXT_MUTED));
    painter.drawText(rect(), Qt::AlignCenter, QStringLiteral("流程概览"));
    return;
  }

  auto mapPt = [&](const QPointF& p) {
    return QPointF((p.x() - bounds.x()) * scale + ox, (p.y() - bounds.y()) * scale + oy);
  };

  painter.setPen(Qt::NoPen);
  for (QGraphicsItem* item : scene_->items()) {
    if (auto* node = dynamic_cast<FlowNodeItem*>(item)) {
      const QRectF r = node->boundingRect();
      const QPointF tl = mapPt(node->scenePos());
      const qreal w = qMax<qreal>(3, r.width() * scale);
      const qreal h = qMax<qreal>(2, r.height() * scale);
      painter.setBrush(QColor(node->isSource() ? theme::ACCENT : theme::OK));
      painter.drawRoundedRect(QRectF(tl.x(), tl.y(), w, h), 2, 2);
    } else if (auto* edge = dynamic_cast<FlowEdgeItem*>(item)) {
      painter.setPen(QPen(QColor(theme::TEXT_MUTED), 1));
      const QPainterPath path = edge->path();
      if (path.elementCount() >= 2) {
        const auto a = path.elementAt(0);
        const auto b = path.elementAt(path.elementCount() - 1);
        painter.drawLine(QPointF((a.x - bounds.x()) * scale + ox, (a.y - bounds.y()) * scale + oy),
                         QPointF((b.x - bounds.x()) * scale + ox, (b.y - bounds.y()) * scale + oy));
      }
      painter.setPen(Qt::NoPen);
    }
  }

  if (view_) {
    const QPointF tl = view_->mapToScene(view_->viewport()->rect().topLeft());
    const QPointF br = view_->mapToScene(view_->viewport()->rect().bottomRight());
    const QPointF p1 = mapPt(tl);
    const QPointF p2 = mapPt(br);
    painter.setBrush(QColor(230, 122, 46, 40));
    painter.setPen(QPen(QColor(theme::ACCENT), 1));
    painter.drawRect(QRectF(p1, p2));
    const int pct = int(qRound(view_->transform().m11() * 100.0));
    painter.setPen(QColor(theme::TEXT_MUTED));
    painter.drawText(6, height() - 6, QStringLiteral("%1% · 拖拽平移").arg(pct));
  }
}

void FlowMinimap::mousePressEvent(QMouseEvent* event) {
  if (event->button() != Qt::LeftButton) return;
  dragging_ = true;
  setCursor(Qt::ClosedHandCursor);
  panTo(event->position());
  event->accept();
}

void FlowMinimap::mouseMoveEvent(QMouseEvent* event) {
  if (!dragging_ || !(event->buttons() & Qt::LeftButton)) return;
  panTo(event->position());
  event->accept();
}

void FlowMinimap::mouseReleaseEvent(QMouseEvent* event) {
  dragging_ = false;
  setCursor(Qt::OpenHandCursor);
  QWidget::mouseReleaseEvent(event);
}

}  // namespace sieans_qt
