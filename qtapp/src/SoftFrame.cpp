#include "SoftFrame.hpp"

#include <QPainter>
#include <QFont>
#include <QtMath>

namespace sieans_qt {

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

static void drawFinder(QPainter& p, int x, int y, int s) {
  p.setPen(Qt::NoPen);
  p.setBrush(Qt::black);
  p.drawRect(x, y, s, s);
  p.setBrush(Qt::white);
  p.drawRect(x + s / 7, y + s / 7, s - 2 * s / 7, s - 2 * s / 7);
  p.setBrush(Qt::black);
  p.drawRect(x + 2 * s / 7, y + 2 * s / 7, s - 4 * s / 7, s - 4 * s / 7);
}

QImage makeSoftFrame(int width, int height, int seq, int exposureUs, double gainDb) {
  const int w = qMax(16, width);
  const int h = qMax(16, height);
  QImage img(w, h, QImage::Format_RGB888);
  img.fill(QColor(245, 245, 245));
  QPainter p(&img);
  p.setRenderHint(QPainter::Antialiasing, false);

  // geometric targets for locate / template match
  p.setPen(Qt::NoPen);
  p.setBrush(Qt::white);
  p.drawRect(QRect(w / 10, h / 8, (w * 4 / 10) - (w / 10), (h * 4 / 10) - (h / 8)));
  const int r = qMax(2, qMin(w, h) / 9);
  p.setBrush(QColor(30, 30, 30));
  p.drawEllipse(QPoint(w * 7 / 10, h / 4), r, r);

  // QR-like module block (visual target; not a real QR payload)
  const int qs = qMin(w, h) / 3;
  const int qx = w / 2 - qs / 2;
  const int qy = h / 2 - qs / 4;
  p.setBrush(Qt::white);
  p.setPen(QPen(Qt::black, 1));
  p.drawRect(qx, qy, qs, qs);
  drawFinder(p, qx + 2, qy + 2, qs / 4);
  drawFinder(p, qx + qs - qs / 4 - 2, qy + 2, qs / 4);
  drawFinder(p, qx + 2, qy + qs - qs / 4 - 2, qs / 4);
  p.setPen(Qt::NoPen);
  p.setBrush(Qt::black);
  for (int i = 0; i < 9; ++i) {
    const int bx = qx + qs / 3 + (i % 3) * (qs / 9);
    const int by = qy + qs / 3 + (i / 3) * (qs / 9);
    if ((i + seq) % 2 == 0) p.drawRect(bx, by, qs / 10, qs / 10);
  }
  p.setPen(QColor(20, 20, 20));
  QFont font(QStringLiteral("DejaVu Sans Mono"), 10);
  font.setBold(true);
  font.setPixelSize(qBound(10, qs / 8, 18));
  p.setFont(font);
  p.drawText(QRect(qx, qy + qs - qs / 5, qs, qs / 5), Qt::AlignCenter,
             QStringLiteral("SIEANS-%1").arg(seq % 1000));

  // moving tick for motion / FPS feel
  p.setPen(QPen(QColor(200, 40, 40), qMax(1, h / 80)));
  const int x = (seq * 17) % qMax(1, w - 20) + 10;
  const int y = h * 7 / 8;
  p.drawLine(x, y, qMin(w - 10, x + 40), y);
  p.end();
  return applySoftTone(img, exposureUs, gainDb, seq, true);
}

}  // namespace sieans_qt
