#include "SoftFrame.hpp"

#include <QPainter>
#include <QPen>
#include <QLine>
#include <QFont>
#include <QFontMetrics>
#include <QFileInfo>
#include <QDir>
#include <QCoreApplication>
#include <QtMath>
#include <QByteArray>
#include <QtGlobal>

namespace sieans_qt {

QString g_softQrOverride;
QString g_softQrLoadedPath;

namespace {

void drawFinder(QPainter& p, const QRect& r) {
  p.setPen(Qt::NoPen);
  p.setBrush(Qt::black);
  p.drawRect(r);
  p.setBrush(Qt::white);
  p.drawRect(r.adjusted(3, 3, -3, -3));
  p.setBrush(Qt::black);
  p.drawRect(r.adjusted(6, 6, -6, -6));
}

// soft·QR path cands: appDir/cwd/resources + build fallbacks
QImage loadSoftQrSample() {
  static QImage cached;
  static bool tried = false;
  if (!g_softQrOverride.isEmpty()) {
    QImage img(g_softQrOverride);
    if (!img.isNull()) {
      g_softQrLoadedPath = g_softQrOverride;
      return img.convertToFormat(QImage::Format_RGB888);
    }
  }
  // Env override (open-and-run / CI) before built-in candidate scan.
  const QByteArray envSample = qgetenv("SIEANS_QT_SAMPLE_QR");
  if (!envSample.isEmpty()) {
    const QString envPath = QString::fromLocal8Bit(envSample);
    QImage img(envPath);
    if (!img.isNull()) {
      cached = img.convertToFormat(QImage::Format_RGB888);
      g_softQrLoadedPath = envPath;
      tried = true;
      return cached;
    }
    // Env set but unreadable — fall through to built-in candidates.
  }
  if (tried) return cached;
  tried = true;
  const QStringList cands = {
      QCoreApplication::applicationDirPath() + QStringLiteral("/resources/sample-qr.png"),
      QCoreApplication::applicationDirPath() + QStringLiteral("/sample-qr.png"),
      QDir(QCoreApplication::applicationDirPath())
          .absoluteFilePath(QStringLiteral("../resources/sample-qr.png")),
      QDir::currentPath() + QStringLiteral("/resources/sample-qr.png"),
      QDir::currentPath() + QStringLiteral("/sample-qr.png"),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/resources/sample-qr.png"),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/build/resources/sample-qr.png"),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/build/sample-qr.png"),
  };
  for (const QString& p : cands) {
    if (!QFileInfo::exists(p)) continue;
    QImage img(p);
    if (!img.isNull()) {
      cached = img.convertToFormat(QImage::Format_RGB888);
      g_softQrLoadedPath = p;
      break;
    }
  }
  return cached;
}
}  // namespace

void setSoftQrSamplePath(const QString& path) { g_softQrOverride = path; }

QString softQrSampleLoadedPath() { return g_softQrLoadedPath; }

int clampExposureUs(double v) {
  if (!qIsFinite(v)) v = 10000.0;
  const int n = int(v);
  return qBound(100, n, 10000000);
}

double clampGainDb(double v) {
  if (!qIsFinite(v)) v = 0.0;
  return qBound(0.0, v, 48.0);
}

double softToneScale(int exposureUs, double gainDb) {
  const double exp = clampExposureUs(exposureUs);
  double scale = 0.35 + qMin(1.45, (exp / 10000.0) * 0.65);
  scale *= (1.0 + clampGainDb(gainDb) / 24.0);
  return scale;
}

QImage applySoftTone(const QImage& src, int exposureUs, double gainDb, int seq,
                     bool stampHud) {
  if (src.isNull()) return {};
  QImage img = src.convertToFormat(QImage::Format_RGB888);
  const double scale = softToneScale(exposureUs, gainDb);
  if (qAbs(scale - 1.0) > 0.01) {
    for (int y = 0; y < img.height(); ++y) {
      uchar* line = img.scanLine(y);
      const int n = img.width() * 3;
      for (int i = 0; i < n; ++i) {
        line[i] = uchar(qBound(0, int(line[i] * scale + 0.5), 255));
      }
    }
  }
  if (stampHud) {
    QPainter p(&img);
    p.setPen(QColor(40, 220, 40));
    QFont font(QStringLiteral("DejaVu Sans"), 9);
    const int px = qBound(8, qMin(img.width(), img.height()) / 28, 18);
    font.setPixelSize(px);
    p.setFont(font);
    const QString label =
        QStringLiteral("SOFT %1×%2 exp=%3us gain=%4dB #%5")
            .arg(img.width())
            .arg(img.height())
            .arg(clampExposureUs(exposureUs))
            .arg(clampGainDb(gainDb), 0, 'f', 1)
            .arg(seq);
    p.drawText(8, img.height() - 8, label);
  }
  return img;
}


int softSceneGeomCircleRadius(int width, int height) {
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  return qBound(22, qMin(w, h) / 28, 36);
}

QPoint softSceneGeomCircleCenter(int width, int height) {
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  const int r = softSceneGeomCircleRadius(w, h);
  // Bottom-right quiet zone, above the 18px HUD strip.
  return QPoint(w - r - 40, h - 18 - r - 28);
}

QRect softSceneGeomCircleRect(int width, int height) {
  const QPoint c = softSceneGeomCircleCenter(width, height);
  const int r = softSceneGeomCircleRadius(width, height);
  return QRect(c.x() - r, c.y() - r, 2 * r, 2 * r);
}

int softSceneGeomFollowCircleRadius(int width, int height) {
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  return qBound(14, qMin(w, h) / 48, 22);
}

QPoint softSceneGeomFollowCircleCenter(int width, int height) {
  const QRect plate = softScenePlateRect(width, height);
  const int r = softSceneGeomFollowCircleRadius(width, height);
  return QPoint(plate.center().x(), plate.bottom() + 8 + r);
}


QColor softSceneYoloFixtureColor() { return QColor(220, 40, 80); }

/**
 * 计算软仿真场景中 YOLO 特征色斑的外接矩形。
 * 放在卡尺白垫右侧、底部 HUD 上方，避开右下角几何圆/直线，避免遮挡二维码有效区。
 */
QRect softSceneYoloFixtureRect(int width, int height) {
  const int h = qMax(16, height) & ~1;
  const int fw = 80;
  const int fh = 56;
  const int gap = 200;
  const int barW = 6;
  const int x0 = 24;
  const int x = (x0 - 8) + (gap + barW + 16) + 12;  // 250
  const int y = h - 18 - fh - 6;
  return QRect(x, y, fw, fh);
}

/**
 * 计算 YOLO 特征色斑内部的矩形孔（用于分割轮廓的孔洞）。
 * 孔洞完全落在外接矩形内，面积固定为 24×16。
 */
QRect softSceneYoloFixtureHoleRect(int width, int height) {
  const QRect r = softSceneYoloFixtureRect(width, height);
  const int hw = 24;
  const int hh = 16;
  return QRect(r.center().x() - hw / 2, r.center().y() - hh / 2, hw, hh);
}

void drawSoftYoloFixture(QPainter& p, int width, int height) {
  p.setRenderHint(QPainter::Antialiasing, false);
  p.setPen(Qt::NoPen);
  p.setBrush(softSceneYoloFixtureColor());
  p.drawRect(softSceneYoloFixtureRect(width, height));
  p.setBrush(QColor(255, 255, 255));
  p.drawRect(softSceneYoloFixtureHoleRect(width, height));
}

QLine softSceneGeomLine(int width, int height) {
  const QPoint c = softSceneGeomCircleCenter(width, height);
  const int r = softSceneGeomCircleRadius(width, height);
  const int y = c.y() - r - 24;
  const int x1 = qMax(c.x() - 80, (qMax(16, width) & ~1) - 180);
  const int x2 = qMin((qMax(16, width) & ~1) - 16, x1 + 160);
  return QLine(x1, y, x2, y);
}

void drawSoftGeomTargets(QPainter& p, int width, int height) {
  p.setRenderHint(QPainter::Antialiasing, false);
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(15, 15, 15));
  const QPoint fc = softSceneGeomFollowCircleCenter(width, height);
  const int fr = softSceneGeomFollowCircleRadius(width, height);
  p.drawEllipse(fc, fr, fr);
  const QPoint c = softSceneGeomCircleCenter(width, height);
  const int r = softSceneGeomCircleRadius(width, height);
  p.drawEllipse(c, r, r);
  const QLine L = softSceneGeomLine(width, height);
  p.setPen(QPen(QColor(15, 15, 15), 6, Qt::SolidLine, Qt::FlatCap));
  p.setBrush(Qt::NoBrush);
  p.drawLine(L);
}

QImage makeSoftScene(int width, int height) {
  // Force even canvas so letterbox origin & finder stay on integer grid.
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  QImage img(w, h, QImage::Format_RGB888);
  img.fill(QColor(236, 236, 236));
  QPainter p(&img);
  p.setRenderHint(QPainter::SmoothPixmapTransform, false);

  // Letterbox the FULL sample scene so embedded QRs stay decodable at soft sizes.
  const QImage qr = loadSoftQrSample();
  if (!qr.isNull()) {
    // Prefer FastTransformation — Smooth blurs finder patterns at 640×400.
    const QImage scaled =
        qr.scaled(w - 4, h - 4, Qt::KeepAspectRatio, Qt::FastTransformation);
    // Even-pixel origin keeps finder modules on integer grid for ZXing.
    const int x = ((w - scaled.width()) / 2) & ~1;
    const int y = ((h - scaled.height()) / 2) & ~1;
    p.fillRect(QRect(0, 0, w, h), Qt::white);
    p.drawImage(x, y, scaled);
    // Guide frame (outside scaled content — decode uses interior pixels).
    p.setPen(QPen(QColor(0, 188, 212), 1));
    p.setBrush(Qt::NoBrush);
    p.drawRect(x - 1, y - 1, scaled.width() + 1, scaled.height() + 1);
    // Corner SOFT badge (outside QR ROI)
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(0, 0, 0, 150));
    p.drawRoundedRect(QRectF(6, 6, 52, 18), 3, 3);
    p.setPen(QColor(0, 230, 118));
    QFont bf = p.font();
    bf.setPointSize(9);
    bf.setBold(true);
    p.setFont(bf);
    p.drawText(QRectF(6, 6, 52, 18), Qt::AlignCenter, QStringLiteral("SOFT"));
    // OCR plate (top-right, outside QR letterbox) — soft smoke readable by tesseract
    {
      const QString plate = QStringLiteral("SIEANS");
      QFont of(QStringLiteral("DejaVu Sans Mono"), 18);
      of.setBold(true);
      of.setPixelSize(qBound(16, qMin(w, h) / 18, 28));
      p.setFont(of);
      const QFontMetrics fm(of);
      const int tw = fm.horizontalAdvance(plate) + 16;
      const int th = fm.height() + 8;
      const int ox = qMax(6, w - tw - 8);
      const int oy = 6;
      p.setPen(Qt::NoPen);
      p.setBrush(QColor(255, 255, 255, 230));
      p.drawRoundedRect(QRectF(ox, oy, tw, th), 3, 3);
      p.setPen(QColor(20, 20, 20));
      p.drawText(QRectF(ox, oy, tw, th), Qt::AlignCenter, plate);
    }
    // Caliper target: two vertical bars, 200px gap (soft smoke → caliperDist≈200)
    {
      const int gap = 200;
      const int barW = 6;
      const int barH = qBound(28, h / 28, 48);
      const int baseY = h - 18 - barH - 6;
      const int x0 = 24;
      p.setPen(Qt::NoPen);
      p.setBrush(QColor(255, 255, 255, 220));
      p.drawRect(QRect(x0 - 8, baseY - 4, gap + barW + 16, barH + 8));
      p.setBrush(QColor(15, 15, 15));
      p.drawRect(QRect(x0, baseY, barW, barH));
      p.drawRect(QRect(x0 + gap, baseY, barW, barH));
    }
  } else {
    p.setPen(Qt::NoPen);
    p.setBrush(Qt::white);
    const QRect plate(w / 8, h / 10, w * 3 / 4, h * 3 / 5);
    p.drawRect(plate);
    const int fs = qMax(14, qMin(plate.width(), plate.height()) / 5);
    drawFinder(p, QRect(plate.left() + 8, plate.top() + 8, fs, fs));
    drawFinder(p, QRect(plate.right() - fs - 8, plate.top() + 8, fs, fs));
    drawFinder(p, QRect(plate.left() + 8, plate.bottom() - fs - 8, fs, fs));
  }
  drawSoftGeomTargets(p, w, h);
  drawSoftYoloFixture(p, w, h);
  p.end();
  return img;
}

QImage makeSoftSceneBlemish(int width, int height) {
  QImage img = makeSoftScene(width, height);
  if (img.isNull()) return img;
  const int bw = qBound(32, img.width() / 20, 80);
  const int bh = qBound(24, img.height() / 24, 64);
  const int x = qMax(8, img.width() - bw - 48);
  const int y = qBound(80, img.height() / 2 - bh / 2, img.height() - bh - 48);
  QPainter p(&img);
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(18, 18, 18));
  p.drawRect(QRect(x, y, bw, bh));
  p.end();
  return img;
}

QImage makeSoftFrame(int width, int height, int seq, int exposureUs, double gainDb) {
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  QImage img = makeSoftScene(w, h);
  QPainter p(&img);
  p.setPen(QColor(40, 40, 40));
  QFont font(QStringLiteral("DejaVu Sans Mono"), 10);
  font.setBold(true);
  font.setPixelSize(qBound(9, qMin(w, h) / 28, 14));
  p.setFont(font);
  // Keep label in a thin bottom strip so it does not cover QR modules.
  p.fillRect(0, h - 18, w, 18, QColor(236, 236, 236, 220));
  {
    QString hud;
    const QImage qr = loadSoftQrSample();
    if (!qr.isNull()) {
      const QString leaf = QFileInfo(g_softQrLoadedPath).fileName();
      hud = leaf.isEmpty()
                ? QStringLiteral("SIEANS- soft·QR %1×%2 #%3 even·letterbox · Soft").arg(w).arg(h).arg(seq % 1000)
                : QStringLiteral("SIEANS- soft·QR %1×%2 #%3 %4")
                      .arg(w)
                      .arg(h)
                      .arg(seq % 1000)
                      .arg(leaf.left(22));
    } else {
      hud = QStringLiteral("SIEANS- soft %1×%2 #%3").arg(w).arg(h).arg(seq % 1000);
    }
    p.drawText(QRect(0, h - 18, w, 18), Qt::AlignCenter, hud);
  }
  p.end();
  return applySoftTone(img, exposureUs, gainDb, seq, true);
}


QRect softScenePlateRect(int width, int height) {
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  QFont of(QStringLiteral("DejaVu Sans Mono"), 18);
  of.setBold(true);
  of.setPixelSize(qBound(16, qMin(w, h) / 18, 28));
  const QFontMetrics fm(of);
  const QString plate = QStringLiteral("SIEANS");
  const int tw = fm.horizontalAdvance(plate) + 16;
  const int th = fm.height() + 8;
  const int ox = qMax(6, w - tw - 8);
  const int oy = 6;
  return QRect(ox, oy, tw, th);
}

QImage makeSoftScenePlateTemplate(int width, int height) {
  const QImage scene = makeSoftScene(width, height);
  const QRect r = softScenePlateRect(width, height);
  if (scene.isNull() || r.isEmpty()) return {};
  const QRect clipped = r.intersected(scene.rect());
  if (clipped.isEmpty()) return {};
  return scene.copy(clipped);
}


}  // namespace sieans_qt
