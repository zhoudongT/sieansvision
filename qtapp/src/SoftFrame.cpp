#include "SoftFrame.hpp"

#include <QPainter>
#include <QFont>
#include <QFileInfo>
#include <QDir>
#include <QCoreApplication>
#include <QtMath>

namespace sieans_qt {

QString g_softQrOverride;

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

QImage loadSoftQrSample() {
  static QImage cached;
  static bool tried = false;
  if (!g_softQrOverride.isEmpty()) {
    QImage img(g_softQrOverride);
    if (!img.isNull()) {
      return img.convertToFormat(QImage::Format_RGB888);
    }
  }
  if (tried) return cached;
  tried = true;
  const QStringList cands = {
      QCoreApplication::applicationDirPath() + QStringLiteral("/resources/sample-qr.png"),
      QDir(QCoreApplication::applicationDirPath())
          .absoluteFilePath(QStringLiteral("../resources/sample-qr.png")),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/resources/sample-qr.png"),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/build/resources/sample-qr.png"),
  };
  for (const QString& p : cands) {
    if (!QFileInfo::exists(p)) continue;
    QImage img(p);
    if (!img.isNull()) {
      cached = img.convertToFormat(QImage::Format_RGB888);
      break;
    }
  }
  return cached;
}
}  // namespace

void setSoftQrSamplePath(const QString& path) { g_softQrOverride = path; }

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
        QStringLiteral("SOFT exp=%1us gain=%2dB #%3")
            .arg(clampExposureUs(exposureUs))
            .arg(clampGainDb(gainDb), 0, 'f', 1)
            .arg(seq);
    p.drawText(8, img.height() - 8, label);
  }
  return img;
}

QImage makeSoftFrame(int width, int height, int seq, int exposureUs, double gainDb) {
  const int w = qMax(16, width);
  const int h = qMax(16, height);
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
    const int x = (w - scaled.width()) / 2;
    const int y = (h - scaled.height()) / 2;
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
  p.drawText(QRect(0, h - 18, w, 18), Qt::AlignCenter,
             drewQr ? QStringLiteral("SIEANS- soft·QR #%1").arg(seq % 1000)
                    : QStringLiteral("SIEANS- soft #%1").arg(seq % 1000));
  p.end();
  return applySoftTone(img, exposureUs, gainDb, seq, true);
}

}  // namespace sieans_qt
