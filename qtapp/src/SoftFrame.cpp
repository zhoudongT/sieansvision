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
        QStringLiteral("exp=%1us gain=%2dB #%3")
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
  img.fill(Qt::black);
  QPainter p(&img);
  p.setPen(Qt::NoPen);
  p.setBrush(Qt::white);
  p.drawRect(QRect(w / 10, h / 8, (w * 4 / 10) - (w / 10), (h * 4 / 10) - (h / 8)));
  const int r = qMax(2, qMin(w, h) / 9);
  p.drawEllipse(QPoint(w * 7 / 10, h / 4), r, r);
  p.setPen(QPen(QColor(255, 200, 200), qMax(1, h / 80)));
  const int x = (seq * 17) % qMax(1, w - 20) + 10;
  const int y = h * 3 / 4;
  p.drawLine(x, y, qMin(w - 10, x + 40), y);
  p.end();
  return applySoftTone(img, exposureUs, gainDb, seq, true);
}

}  // namespace sieans_qt
