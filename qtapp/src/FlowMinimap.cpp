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
  setFixedSize(160, 110);
  setAttribute(Qt::WA_TransparentForMouseEvents, false);
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

void FlowMinimap::paintEvent(QPaintEvent*) {
  QPainter painter(this);
  painter.setRenderHint(QPainter::Antialiasing);
  painter.fillRect(rect(), QColor(theme::RAIL_BG));
  painter.setPen(QPen(QColor(theme::LINE), 1));
  painter.drawRect(0, 0, width() - 1, height() - 1);

  QRectF bounds;
  qreal scale = 1, ox = 0, oy = 0;
  if (!mapMetrics(&bounds, &scale, &ox, &oy)) return;

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
    painter.drawText(6, height() - 6, QStringLiteral("%1%").arg(pct));
  }
}

void FlowMinimap::mousePressEvent(QMouseEvent* event) {
  QRectF bounds;
  qreal scale = 1, ox = 0, oy = 0;
  if (!mapMetrics(&bounds, &scale, &ox, &oy) || !view_) return;
  const QPointF pos = event->position();
  const qreal sx = bounds.x() + (pos.x() - ox) / scale;
  const qreal sy = bounds.y() + (pos.y() - oy) / scale;
  view_->centerOn(sx, sy);
  emit navigate(sx, sy);
  update();
}

}  // namespace sieans_qt
