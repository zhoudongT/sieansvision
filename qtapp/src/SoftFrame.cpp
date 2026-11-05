#include "SoftFrame.hpp"

#include <QPainter>
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

QImage makeSoftFrame(int width, int height, int seq, int exposureUs, double gainDb) {
  // Force even canvas so letterbox origin & finder stay on integer grid.
  const int w = qMax(16, width) & ~1;
  const int h = qMax(16, height) & ~1;
  QImage img(w, h, QImage::Format_RGB888);
  img.fill(QColor(236, 236, 236));
  QPainter p(&img);
  p.setRenderHint(QPainter::SmoothPixmapTransform, false);

  // Letterbox the FULL sample scene so embedded QRs stay decodable at soft sizes.
  const QImage qr = loadSoftQrSample();
  bool drewQr = false;
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
    drewQr = true;
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

  p.setPen(QColor(40, 40, 40));
  QFont font(QStringLiteral("DejaVu Sans Mono"), 10);
  font.setBold(true);
  font.setPixelSize(qBound(9, qMin(w, h) / 28, 14));
  p.setFont(font);
  // Keep label in a thin bottom strip so it does not cover QR modules.
  p.fillRect(0, h - 18, w, 18, QColor(236, 236, 236, 220));
  {
    QString hud;
    if (drewQr) {
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

}  // namespace sieans_qt
