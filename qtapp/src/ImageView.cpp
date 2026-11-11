#include "ImageView.hpp"

#include <QGraphicsPathItem>
#include <QPainter>
#include <QGraphicsSimpleTextItem>
#include <QGraphicsRectItem>
#include <QGraphicsEllipseItem>
#include <QGraphicsLineItem>
#include <QPen>
#include <QBrush>
#include <QPainterPath>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QLabel>
#include <QMimeData>
#include <QUrl>
#include <QClipboard>
#include <QGuiApplication>
#include <QToolTip>
#include <QCursor>
#include <QApplication>
#include <QTemporaryDir>
#include <QImage>
#include <QColor>
#include <QFile>
#include <QVariantList>
#include <QMetaType>
#include <QResizeEvent>
#include <cmath>

namespace sieans_qt {

ImageView::ImageView(QWidget* parent) : QGraphicsView(parent) {
  setFocusPolicy(Qt::StrongFocus);
  setToolTip(QStringLiteral("F/G/A/Space/Home/0/R 适应 · +/- 缩放 · Alt+/- 微调 · 1=1:1 · 2=200% · 3=50% · O 叠显 · P 探针 · S/Ctrl+Shift+F 存胶片 · Ctrl+C 复制图像 · Ctrl+V 粘贴到胶片 · Ctrl+Shift+C 探针 · Ctrl+H 叠显 · 中键适应 · Esc/C/Del 清叠加 · 滚轮缩放"));
  setStatusTip(QStringLiteral("图像视图 · F/G/A/Space/Home/0/R 适应 · +/- 缩放 · 1=1:1 · 2=200% · O 叠显 · P 探针 · Ctrl+Shift+C 探针 · 中键适应 · Esc/C/Del/Backspace 清叠加 · 码框 hits · 拖拽平移 · 滚轮缩放"));
  setScene(&scene_);
  setRenderHints(QPainter::Antialiasing | QPainter::SmoothPixmapTransform);
  setDragMode(QGraphicsView::ScrollHandDrag);
  setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
  setBackgroundBrush(QColor(18, 20, 24));
  setFrameShape(QFrame::NoFrame);
  pixmap_item_ = scene_.addPixmap(QPixmap());
  probe_ = new QLabel(this);
  probe_->setObjectName(QStringLiteral("pixelProbe"));
  probe_->setStyleSheet(QStringLiteral(
      "background:rgba(0,0,0,170);color:#e8e8e8;padding:2px 8px;font-size:11px;"));
  setMouseTracking(true);
  updateProbe(-1, -1);
}

void ImageView::setImage(const QImage& image, bool refitView) {
  image_ = image;
  pixmap_item_->setPixmap(QPixmap::fromImage(image_));
  scene_.setSceneRect(pixmap_item_->boundingRect());
  clearOverlays();
  redrawRoi();
  if (refitView) {
    userZoomed_ = false;
    fitToView();
  }
  updateProbe(-1, -1);
}

void ImageView::setLiveImage(const QImage& image) {
  if (image.isNull()) return;
  const bool sizeChanged =
      image_.isNull() || image.width() != image_.width() ||
      image.height() != image_.height();
  image_ = image;
  pixmap_item_->setPixmap(QPixmap::fromImage(image_));
  if (sizeChanged) {
    scene_.setSceneRect(pixmap_item_->boundingRect());
    if (!userZoomed_) fitToView();
  }
  setToolTip(QStringLiteral("图像 %1×%2 · F/G/A/Space/Home/0/R 适应 · 码 %3")
                 .arg(image_.width())
                 .arg(image_.height())
                 .arg(hits_.size()));
  updateProbe(-1, -1);
}

void ImageView::setOverlays(const QVector<OverlayHit>& hits) {
  hits_ = hits;
  redrawOverlays();
}

void ImageView::setGeomOverlays(const QVector<GeomOverlaySpec>& specs) {
  geom_specs_ = specs;
  redrawOverlays();
}

void ImageView::clearGeomOverlays() {
  if (geom_specs_.isEmpty()) return;
  geom_specs_.clear();
  redrawOverlays();
}

void ImageView::clearOverlays() {
  for (auto* it : overlay_items_) {
    scene_.removeItem(it);
    delete it;
  }
  overlay_items_.clear();
  hits_.clear();
  geom_specs_.clear();
}

void ImageView::fitToView() {
  if (image_.isNull()) return;
  fitInView(pixmap_item_, Qt::KeepAspectRatio);
  userZoomed_ = false;
}

void ImageView::resizeEvent(QResizeEvent* event) {
  QGraphicsView::resizeEvent(event);
  updateProbe(-1, -1);
  if (!userZoomed_ && !image_.isNull()) fitToView();
}

void ImageView::updateProbe(int x, int y) {
  if (!probe_) return;
  const QString hitChip =
      hits_.isEmpty() ? QString()
                      : QStringLiteral(" · hits %1").arg(hits_.size());
  if (image_.isNull()) {
    probe_->setText(QStringLiteral("无图像"));
  } else if (x < 0 || y < 0 || x >= image_.width() || y >= image_.height()) {
    probe_->setText(QStringLiteral("%1*%2%3")
                        .arg(image_.width())
                        .arg(image_.height())
                        .arg(hitChip));
  } else {
    const QRgb px = image_.pixel(x, y);
    probe_->setText(QStringLiteral("%1*%2 | X %3 Y %4 | R %5 G %6 B %7%8")
                        .arg(image_.width())
                        .arg(image_.height())
                        .arg(x)
                        .arg(y)
                        .arg(qRed(px))
                        .arg(qGreen(px))
                        .arg(qBlue(px))
                        .arg(hitChip));
  }
  lastProbe_ = probe_->text();
  probe_->adjustSize();
  probe_->move(8, qMax(0, height() - probe_->height() - 6));
  probe_->raise();
}

void ImageView::mouseMoveEvent(QMouseEvent* event) {
  if (roi_drag_ != 0 && roi_mode_) {
    applyDragTo(mapToScene(event->pos()));
    event->accept();
    updateProbe(int(roi_.center().x()), int(roi_.center().y()));
    return;
  }
  QGraphicsView::mouseMoveEvent(event);
  if (image_.isNull()) {
    updateProbe(-1, -1);
    return;
  }
  const QPointF sp = mapToScene(event->pos());
  updateProbe(int(sp.x()), int(sp.y()));
}


void ImageView::keyPressEvent(QKeyEvent* event) {
  if (roi_mode_) {
    if (event->key() == Qt::Key_Escape) {
      if (roi_drag_ != 0) {
        roi_drag_ = 0;
        setRoi(roi_start_, false);
      }
      event->accept();
      return;
    }
    if ((event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace) &&
        hasRoi()) {
      clearRoi(true);
      event->accept();
      return;
    }
    const int step = (event->modifiers() & Qt::ShiftModifier) ? 10 : 1;
    int dx = 0, dy = 0;
    if (event->key() == Qt::Key_Left) dx = -step;
    else if (event->key() == Qt::Key_Right) dx = step;
    else if (event->key() == Qt::Key_Up) dy = -step;
    else if (event->key() == Qt::Key_Down) dy = step;
    if (dx != 0 || dy != 0) {
      moveRoiBy(dx, dy);
      event->accept();
      return;
    }
  }
  if (event->key() == Qt::Key_Escape ||
      event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace ||
      (event->key() == Qt::Key_C && !(event->modifiers() & Qt::ControlModifier))) {
    clearOverlays();
    redrawRoi();
    event->accept();
    return;
  }
  if (((event->key() == Qt::Key_F || event->key() == Qt::Key_Home ||
        event->key() == Qt::Key_0 || event->key() == Qt::Key_R ||
        event->key() == Qt::Key_G || event->key() == Qt::Key_A ||
        event->key() == Qt::Key_Space) &&
       !(event->modifiers() & Qt::ControlModifier))) {
    userZoomed_ = false;
    fitToView();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_O) {
    overlaysHidden_ = !overlaysHidden_;
    redrawOverlays();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_P) {
    probeHidden_ = !probeHidden_;
    if (probe_) probe_->setVisible(!probeHidden_);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_1 && !(event->modifiers() & Qt::ControlModifier)) {
    // 1:1 像素
    resetTransform();
    userZoomed_ = true;
    QToolTip::showText(QCursor::pos(), QStringLiteral("缩放 100% · 1:1"), this);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Plus || event->key() == Qt::Key_Equal) {
    userZoomed_ = true;
    const qreal f = (event->modifiers() & Qt::AltModifier) ? 1.05 : 1.15;
    scale(f, f);
    QToolTip::showText(QCursor::pos(),
                       QStringLiteral("缩放 %1%").arg(transform().m11() * 100.0, 0, 'f', 0), this);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Minus) {
    userZoomed_ = true;
    const qreal f = (event->modifiers() & Qt::AltModifier) ? 1.05 : 1.15;
    scale(1.0 / f, 1.0 / f);
    QToolTip::showText(QCursor::pos(),
                       QStringLiteral("缩放 %1%").arg(transform().m11() * 100.0, 0, 'f', 0), this);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_3 && !(event->modifiers() & Qt::ControlModifier)) {
    resetTransform();
    scale(0.5, 0.5);
    userZoomed_ = true;
    QToolTip::showText(QCursor::pos(), QStringLiteral("缩放 50%"), this);
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_2 && !(event->modifiers() & Qt::ControlModifier)) {
    resetTransform();
    scale(2.0, 2.0);
    userZoomed_ = true;
    QToolTip::showText(QCursor::pos(), QStringLiteral("缩放 200%"), this);
    event->accept();
    return;
  }
  if ((event->key() == Qt::Key_S && !(event->modifiers() & Qt::ControlModifier) &&
       !(event->modifiers() & Qt::AltModifier)) ||
      (event->key() == Qt::Key_F && (event->modifiers() & Qt::ControlModifier) &&
       (event->modifiers() & Qt::ShiftModifier))) {
    if (!image_.isNull()) {
      emit imageSaveToFilmstripRequested(image_);
      QToolTip::showText(QCursor::pos(),
                         QStringLiteral("存胶片 %1×%2 · S").arg(image_.width()).arg(image_.height()),
                         this);
    } else {
      QToolTip::showText(QCursor::pos(), QStringLiteral("无图像可存 · S"), this);
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_C && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    if (!lastProbe_.isEmpty()) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(lastProbe_);
      QToolTip::showText(QCursor::pos(), QStringLiteral("已复制探针 · Ctrl+Shift+C"), this);
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_C && (event->modifiers() & Qt::ControlModifier)) {
    if (!image_.isNull()) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setImage(image_);
      QToolTip::showText(QCursor::pos(),
                         QStringLiteral("已复制图像 %1×%2 · Ctrl+C")
                             .arg(image_.width())
                             .arg(image_.height()),
                         this);
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_V && (event->modifiers() & Qt::ControlModifier)) {
    QImage img;
    if (auto* clip = QGuiApplication::clipboard()) {
      img = clip->image();
      if (img.isNull()) {
        const QMimeData* md = clip->mimeData();
        if (md && md->hasUrls()) {
          for (const QUrl& u : md->urls()) {
            if (!u.isLocalFile()) continue;
            QImage probe(u.toLocalFile());
            if (!probe.isNull()) { img = probe; break; }
          }
        }
      }
    }
    if (!img.isNull()) {
      emit imagePasted(img);
      QToolTip::showText(QCursor::pos(),
                         QStringLiteral("已粘贴图像 %1×%2 · Ctrl+V")
                             .arg(img.width())
                             .arg(img.height()),
                         this);
    } else {
      QToolTip::showText(QCursor::pos(), QStringLiteral("剪贴板无图像 · Ctrl+V"), this);
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_H && (event->modifiers() & Qt::ControlModifier)) {
    QStringList lines;
    int i = 0;
    for (const auto& h : hits_) {
      ++i;
      lines << QStringLiteral("#%1\t%2\t%3").arg(i).arg(h.format, h.text);
    }
    if (auto* clip = QGuiApplication::clipboard())
      clip->setText(lines.join(QLatin1Char('\n')));
    QToolTip::showText(QCursor::pos(),
                       QStringLiteral("已复制叠显 %1 · Ctrl+H").arg(lines.size()), this);
    event->accept();
    return;
  }
  QGraphicsView::keyPressEvent(event);
}


void ImageView::mousePressEvent(QMouseEvent* event) {
  if (roi_mode_ && event->button() == Qt::LeftButton && !image_.isNull()) {
    const QPointF sp = mapToScene(event->pos());
    roi_press_ = sp;
    roi_start_ = roi_;
    const int hit = hitRoiHandle(sp);
    if (hit > 0) {
      roi_drag_ = hit;
    } else {
      roi_drag_ = 10;  // draw
    }
    setCursor(Qt::CrossCursor);
    event->accept();
    return;
  }
  if (event->button() == Qt::MiddleButton) {
    userZoomed_ = false;
    fitToView();
    event->accept();
    return;
  }
  if (event->button() == Qt::RightButton) {
    if (!lastProbe_.isEmpty()) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(lastProbe_);
      QToolTip::showText(QCursor::pos(), QStringLiteral("已复制探针 · 右键"), this);
    }
    event->accept();
    return;
  }
  QGraphicsView::mousePressEvent(event);
}

void ImageView::wheelEvent(QWheelEvent* event) {
  userZoomed_ = true;
  const qreal factor = (event->angleDelta().y() > 0) ? 1.15 : (1.0 / 1.15);
  scale(factor, factor);
}

void ImageView::redrawOverlays() {
  for (auto* it : overlay_items_) {
    scene_.removeItem(it);
    delete it;
  }
  overlay_items_.clear();

   if (overlaysHidden_) return;
 QPen pen(QColor(0, 230, 118), 2.5);
  int idx = 0;
  for (const auto& h : hits_) {
    ++idx;
    if (h.polygon.size() >= 2) {
      QPainterPath path;
      path.addPolygon(h.polygon);
      path.closeSubpath();
      auto* poly = scene_.addPath(path, pen, Qt::NoBrush);
      overlay_items_.push_back(poly);
    }
    if (!h.text.isEmpty() && !h.polygon.isEmpty()) {
      const QString text =
          QStringLiteral("#%1 %2: %3").arg(idx).arg(h.format, h.text.left(48));
      auto* label = scene_.addSimpleText(text);
      QFont f = label->font();
      f.setPointSize(11);
      f.setBold(true);
      label->setFont(f);
      label->setBrush(QColor(255, 235, 59));
      const QRectF br = h.polygon.boundingRect();
      const QRectF lr = label->boundingRect();
      auto* bg = scene_.addRect(
          QRectF(0, 0, lr.width() + 8, lr.height() + 4), Qt::NoPen,
          QColor(0, 0, 0, 160));
      bg->setPos(br.topLeft() + QPointF(0, -lr.height() - 6));
      label->setPos(br.topLeft() + QPointF(4, -lr.height() - 4));
      overlay_items_.push_back(bg);
      overlay_items_.push_back(label);
    }
  }
  for (const GeomOverlaySpec& s : geom_specs_) {
    const QColor col(s.color.isEmpty() ? QStringLiteral("#e87722") : s.color);
    QPen pen(col, s.width > 0 ? s.width : 1.5);
    if (s.type == QLatin1String("line")) {
      auto* ln = scene_.addLine(s.x1, s.y1, s.x2, s.y2, pen);
      overlay_items_.push_back(ln);
    } else if (s.type == QLatin1String("point")) {
      const qreal r = s.r > 0 ? s.r : 6.0;
      auto* el = scene_.addEllipse(s.x - r, s.y - r, r * 2, r * 2, pen, Qt::NoBrush);
      overlay_items_.push_back(el);
    } else if (s.type == QLatin1String("label") && !s.text.isEmpty()) {
      auto* label = scene_.addSimpleText(s.text);
      QFont f = label->font();
      f.setPointSize(10);
      f.setBold(true);
      label->setFont(f);
      label->setBrush(col);
      label->setPos(s.x, s.y);
      overlay_items_.push_back(label);
    }
  }
  // Size chip (VM-ish HUD) — always when image present.
  if (!image_.isNull()) {
    auto* sizeChip = scene_.addSimpleText(
        QStringLiteral("%1×%2").arg(image_.width()).arg(image_.height()));
    QFont sf = sizeChip->font();
    sf.setPointSize(11);
    sf.setBold(true);
    sizeChip->setFont(sf);
    sizeChip->setBrush(QColor(180, 220, 255));
    auto* sizeBg = scene_.addRect(
        QRectF(0, 0, sizeChip->boundingRect().width() + 10,
               sizeChip->boundingRect().height() + 6),
        Qt::NoPen, QColor(0, 0, 0, 160));
    sizeBg->setPos(8, 8);
    sizeChip->setPos(13, 11);
    overlay_items_.push_back(sizeBg);
    overlay_items_.push_back(sizeChip);
  }
  if (!hits_.isEmpty()) {
    auto* chip = scene_.addSimpleText(
        QStringLiteral("码 %1").arg(hits_.size()));
    QFont f = chip->font();
    f.setPointSize(12);
    f.setBold(true);
    chip->setFont(f);
    chip->setBrush(QColor(0, 230, 118));
    auto* chipBg = scene_.addRect(
        QRectF(0, 0, chip->boundingRect().width() + 10,
               chip->boundingRect().height() + 6),
        Qt::NoPen, QColor(0, 0, 0, 170));
    const qreal y = image_.isNull() ? 8 : 34;
    chipBg->setPos(8, y);
    chip->setPos(13, y + 3);
    overlay_items_.push_back(chipBg);
    overlay_items_.push_back(chip);
  }
}


namespace {

constexpr int kRoiDraw = 10;
constexpr int kRoiMove = 1;
// handles 2..9: N, S, E, W, NE, NW, SE, SW
const int kHandleN = 2, kHandleS = 3, kHandleE = 4, kHandleW = 5;
const int kHandleNE = 6, kHandleNW = 7, kHandleSE = 8, kHandleSW = 9;

QRect alignedRoi(const QRectF& r) {
  return r.normalized().toAlignedRect();
}

}  // namespace

bool operationSupportsRoi(const QString& op) {
  return op == QLatin1String("defects") || op == QLatin1String("yolo") ||
         op == QLatin1String("yolo_segment") || op == QLatin1String("geometry") ||
         op == QLatin1String("measure") || op == QLatin1String("caliper");
}

QRect roiFromParams(const QVariantMap& params) {
  const QVariant raw = params.value(QStringLiteral("roi"));
  if (raw.typeId() == QMetaType::QVariantList || raw.canConvert<QVariantList>()) {
    const QVariantList lst = raw.toList();
    if (lst.size() == 4) {
      const QRect r(int(std::lround(lst.at(0).toDouble())),
                    int(std::lround(lst.at(1).toDouble())),
                    int(std::lround(lst.at(2).toDouble())),
                    int(std::lround(lst.at(3).toDouble())));
      if (r.width() >= 2 && r.height() >= 2) return r.normalized();
    }
  }
  const int w = params.value(QStringLiteral("roiW"), 0).toInt();
  const int h = params.value(QStringLiteral("roiH"), 0).toInt();
  if (w >= 2 && h >= 2) {
    return QRect(params.value(QStringLiteral("roiX"), 0).toInt(),
                 params.value(QStringLiteral("roiY"), 0).toInt(), w, h)
        .normalized();
  }
  return {};
}

void writeRoiToParams(QVariantMap& params, const QRect& r) {
  const QRect n = r.normalized();
  params.insert(QStringLiteral("roiX"), n.x());
  params.insert(QStringLiteral("roiY"), n.y());
  params.insert(QStringLiteral("roiW"), n.width());
  params.insert(QStringLiteral("roiH"), n.height());
  params.insert(QStringLiteral("roi"),
                QVariantList{n.x(), n.y(), n.width(), n.height()});
}

void clearRoiFromParams(QVariantMap& params) {
  params.remove(QStringLiteral("roiX"));
  params.remove(QStringLiteral("roiY"));
  params.remove(QStringLiteral("roiW"));
  params.remove(QStringLiteral("roiH"));
  params.remove(QStringLiteral("roi"));
}

QRect ImageView::clampRoiRect(const QRect& r) const {
  QRect n = r.normalized();
  if (image_.isNull()) return n;
  const int iw = image_.width();
  const int ih = image_.height();
  if (n.width() < 2) n.setWidth(2);
  if (n.height() < 2) n.setHeight(2);
  if (n.width() > iw) n.setWidth(iw);
  if (n.height() > ih) n.setHeight(ih);
  if (n.x() < 0) n.moveLeft(0);
  if (n.y() < 0) n.moveTop(0);
  if (n.right() >= iw) n.moveLeft(iw - n.width());
  if (n.bottom() >= ih) n.moveTop(ih - n.height());
  if (n.x() < 0) n.setX(0);
  if (n.y() < 0) n.setY(0);
  return n;
}

void ImageView::redrawRoi() {
  if (roi_item_) {
    scene_.removeItem(roi_item_);
    delete roi_item_;
    roi_item_ = nullptr;
  }
  for (auto* h : roi_handles_) {
    if (!h) continue;
    scene_.removeItem(h);
    delete h;
  }
  roi_handles_.clear();
  if (!hasRoi()) return;
  QPen pen(QColor(QStringLiteral("#e67a2e")), 2, Qt::DashLine);
  pen.setCosmetic(true);
  roi_item_ = scene_.addRect(QRectF(roi_), pen);
  roi_item_->setZValue(20);
  roi_item_->setAcceptedMouseButtons(Qt::NoButton);
  if (!roi_mode_) return;
  const qreal scale = std::max(1e-3, std::abs(transform().m11()));
  const qreal hs = std::max(6.0, 8.0 / scale);
  const QPoint pts[8] = {
      QPoint(roi_.center().x(), roi_.top()),
      QPoint(roi_.center().x(), roi_.bottom()),
      QPoint(roi_.right(), roi_.center().y()),
      QPoint(roi_.left(), roi_.center().y()),
      QPoint(roi_.right(), roi_.top()),
      QPoint(roi_.left(), roi_.top()),
      QPoint(roi_.right(), roi_.bottom()),
      QPoint(roi_.left(), roi_.bottom()),
  };
  QPen hp(QColor(QStringLiteral("#e67a2e")), 1);
  hp.setCosmetic(true);
  for (const QPoint& p : pts) {
    auto* box = scene_.addRect(QRectF(p.x() - hs / 2, p.y() - hs / 2, hs, hs), hp,
                               QBrush(QColor(QStringLiteral("#e67a2e"))));
    box->setZValue(21);
    box->setAcceptedMouseButtons(Qt::NoButton);
    roi_handles_.push_back(box);
  }
}

int ImageView::hitRoiHandle(const QPointF& scenePos) const {
  if (!hasRoi()) return 0;
  const qreal scale = std::max(1e-3, std::abs(transform().m11()));
  const qreal hs = std::max(6.0, 10.0 / scale);
  const QRectF r(roi_);
  struct Hit {
    int id;
    QPointF pt;
  };
  const Hit hits[8] = {
      {kHandleN, QPointF(r.center().x(), r.top())},
      {kHandleS, QPointF(r.center().x(), r.bottom())},
      {kHandleE, QPointF(r.right(), r.center().y())},
      {kHandleW, QPointF(r.left(), r.center().y())},
      {kHandleNE, QPointF(r.right(), r.top())},
      {kHandleNW, QPointF(r.left(), r.top())},
      {kHandleSE, QPointF(r.right(), r.bottom())},
      {kHandleSW, QPointF(r.left(), r.bottom())},
  };
  for (const Hit& h : hits) {
    if (QRectF(h.pt.x() - hs, h.pt.y() - hs, hs * 2, hs * 2).contains(scenePos))
      return h.id;
  }
  if (r.adjusted(-1, -1, 1, 1).contains(scenePos)) return kRoiMove;
  return 0;
}

void ImageView::applyDragTo(const QPointF& scenePos) {
  if (roi_drag_ == kRoiDraw) {
    roi_ = clampRoiRect(alignedRoi(QRectF(roi_press_, scenePos)));
    redrawRoi();
    return;
  }
  QRect n = roi_start_;
  const int dx = int(std::lround(scenePos.x() - roi_press_.x()));
  const int dy = int(std::lround(scenePos.y() - roi_press_.y()));
  if (roi_drag_ == kRoiMove) {
    n.translate(dx, dy);
  } else {
    int l = n.left(), t = n.top(), rgt = n.right(), b = n.bottom();
    if (roi_drag_ == kHandleN || roi_drag_ == kHandleNE || roi_drag_ == kHandleNW) t += dy;
    if (roi_drag_ == kHandleS || roi_drag_ == kHandleSE || roi_drag_ == kHandleSW) b += dy;
    if (roi_drag_ == kHandleE || roi_drag_ == kHandleNE || roi_drag_ == kHandleSE) rgt += dx;
    if (roi_drag_ == kHandleW || roi_drag_ == kHandleNW || roi_drag_ == kHandleSW) l += dx;
    n = QRect(QPoint(l, t), QPoint(rgt, b)).normalized();
  }
  roi_ = clampRoiRect(n);
  redrawRoi();
}

void ImageView::setRoiMode(bool on) {
  roi_mode_ = on;
  if (!on) {
    roi_drag_ = 0;
    setCursor(Qt::ArrowCursor);
    setDragMode(QGraphicsView::ScrollHandDrag);
  } else {
    setCursor(Qt::CrossCursor);
    setDragMode(QGraphicsView::NoDrag);
  }
  redrawRoi();
}

void ImageView::setRoi(const QRect& r, bool emitSignal) {
  const QRect n = r.isNull() ? QRect() : clampRoiRect(r);
  const bool changed = n != roi_;
  roi_ = n;
  redrawRoi();
  if (emitSignal && changed) {
    if (hasRoi()) emit roiEdited(roi_);
    else emit roiCleared();
  }
}

void ImageView::clearRoi(bool emitSignal) {
  const bool had = hasRoi();
  roi_ = QRect();
  roi_drag_ = 0;
  redrawRoi();
  if (emitSignal && had) emit roiCleared();
}

bool ImageView::applyRoi(const QRect& r) {
  const QRect raw = r.normalized();
  if (raw.width() < 2 || raw.height() < 2) return false;
  const QRect n = clampRoiRect(raw);
  if (n.width() < 2 || n.height() < 2) return false;
  if (n == roi_) return false;
  roi_ = n;
  redrawRoi();
  emit roiEdited(roi_);
  return true;
}

bool ImageView::moveRoiBy(int dx, int dy) {
  if (!hasRoi() || (dx == 0 && dy == 0)) return false;
  return applyRoi(roi_.translated(dx, dy));
}

bool ImageView::resizeRoi(int dLeft, int dTop, int dRight, int dBottom) {
  if (!hasRoi()) return false;
  if (dLeft == 0 && dTop == 0 && dRight == 0 && dBottom == 0) return false;
  QRect n = roi_;
  n.setLeft(n.left() + dLeft);
  n.setTop(n.top() + dTop);
  n.setRight(n.right() + dRight);
  n.setBottom(n.bottom() + dBottom);
  return applyRoi(n);
}

void ImageView::mouseReleaseEvent(QMouseEvent* event) {
  if (roi_mode_ && roi_drag_ != 0 && event->button() == Qt::LeftButton) {
    applyDragTo(mapToScene(event->pos()));
    const int kind = roi_drag_;
    roi_drag_ = 0;
    setCursor(Qt::CrossCursor);
    if (hasRoi() && roi_ != roi_start_)
      emit roiEdited(roi_);
    else if (kind == kRoiDraw && !hasRoi())
      setRoi(roi_start_, false);
    event->accept();
    return;
  }
  QGraphicsView::mouseReleaseEvent(event);
}

QStringList ImageView::roiEditorSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  if (!qApp) {
    fails << QStringLiteral("no-qapp");
    return fails;
  }
  check("supports-measure", operationSupportsRoi(QStringLiteral("measure")));
  check("supports-not-barcode", !operationSupportsRoi(QStringLiteral("barcode")));

  QVariantMap listed;
  listed.insert(QStringLiteral("roi"), QVariantList{10, 20, 40, 30});
  check("from-list", roiFromParams(listed) == QRect(10, 20, 40, 30));
  QVariantMap keys;
  keys.insert(QStringLiteral("roiX"), 5);
  keys.insert(QStringLiteral("roiY"), 6);
  keys.insert(QStringLiteral("roiW"), 15);
  keys.insert(QStringLiteral("roiH"), 16);
  check("from-xywh", roiFromParams(keys) == QRect(5, 6, 15, 16));
  QVariantMap written;
  writeRoiToParams(written, QRect(8, 9, 12, 14));
  check("write-xywh", written.value(QStringLiteral("roiX")).toInt() == 8 &&
                          written.value(QStringLiteral("roiW")).toInt() == 12);
  check("write-list", written.value(QStringLiteral("roi")).toList().size() == 4 &&
                          written.value(QStringLiteral("roi")).toList().at(2).toInt() == 12);
  clearRoiFromParams(written);
  check("cleared", roiFromParams(written).isNull());

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (!tmp.isValid()) return fails;
  QImage img(200, 150, QImage::Format_RGB888);
  img.fill(QColor(40, 40, 50));
  const QString path = tmp.filePath(QStringLiteral("roi.png"));
  check("write-img", img.save(path));

  ImageView view;
  view.setImage(img, false);
  check("apply", view.applyRoi(QRect(10, 20, 40, 30)) && view.roi() == QRect(10, 20, 40, 30));
  check("apply-same", !view.applyRoi(QRect(10, 20, 40, 30)));
  check("move", view.moveRoiBy(5, -2) && view.roi() == QRect(15, 18, 40, 30),
        QStringLiteral("%1,%2,%3,%4")
            .arg(view.roi().x())
            .arg(view.roi().y())
            .arg(view.roi().width())
            .arg(view.roi().height()));
  check("resize", view.resizeRoi(0, 0, 10, 5) && view.roi() == QRect(15, 18, 50, 35),
        QStringLiteral("%1x%2").arg(view.roi().width()).arg(view.roi().height()));
  check("clamp", view.applyRoi(QRect(-20, -10, 400, 400)) &&
                     view.roi().x() >= 0 && view.roi().y() >= 0 &&
                     view.roi().right() < 200 && view.roi().bottom() < 150);
  const QRect beforeTiny = view.roi();
  check("reject-tiny", !view.applyRoi(QRect(3, 3, 1, 1)) && view.roi() == beforeTiny);
  view.setRoiMode(true);
  check("mode-on", view.roiMode());
  check("clear", view.hasRoi());
  view.clearRoi(false);
  check("cleared-view", !view.hasRoi());
  // Scratch document write-back (not the live seed).
  QVariantMap stepParams;
  writeRoiToParams(stepParams, QRect(11, 12, 21, 22));
  check("scratch-params", roiFromParams(stepParams) == QRect(11, 12, 21, 22));
  return fails;
}

}  // namespace sieans_qt
