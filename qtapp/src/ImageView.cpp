#include "ImageView.hpp"

#include <QGraphicsPathItem>
#include <QPainter>
#include <QGraphicsSimpleTextItem>
#include <QGraphicsRectItem>
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
#include <QResizeEvent>

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

void ImageView::clearOverlays() {
  for (auto* it : overlay_items_) {
    scene_.removeItem(it);
    delete it;
  }
  overlay_items_.clear();
  hits_.clear();
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
  QGraphicsView::mouseMoveEvent(event);
  if (image_.isNull()) {
    updateProbe(-1, -1);
    return;
  }
  const QPointF sp = mapToScene(event->pos());
  updateProbe(int(sp.x()), int(sp.y()));
}


void ImageView::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_Escape ||
      event->key() == Qt::Key_Delete || event->key() == Qt::Key_Backspace ||
      (event->key() == Qt::Key_C && !(event->modifiers() & Qt::ControlModifier))) {
    clearOverlays();
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

}  // namespace sieans_qt
