#include "TemplateMatch.hpp"

#include <QHash>
#include <QtMath>
#include <algorithm>
#include <cstring>

namespace sieans_qt {
namespace {

QVector<uchar> toGray(const QImage& src, int& w, int& h) {
  QImage g = src.convertToFormat(QImage::Format_Grayscale8);
  w = g.width();
  h = g.height();
  QVector<uchar> out(w * h);
  for (int y = 0; y < h; ++y)
    memcpy(out.data() + y * w, g.constScanLine(y), size_t(w));
  return out;
}

}  // namespace

QImage centerCrop(const QImage& src, int width, int height) {
  if (src.isNull()) return {};
  const int w = qBound(8, width, src.width());
  const int h = qBound(8, height, src.height());
  const int x = qMax(0, (src.width() - w) / 2);
  const int y = qMax(0, (src.height() - h) / 2);
  return src.copy(x, y, w, h);
}

QImage salientCrop(const QImage& src, int maxWidth, int maxHeight) {
  if (src.isNull()) return {};
  const QImage g = src.convertToFormat(QImage::Format_Grayscale8);
  const int tw = qBound(16, maxWidth, g.width());
  const int th = qBound(16, maxHeight, g.height());
  const int step = qMax(4, qMin(tw, th) / 4);
  double best = -1;
  int bx = 0, by = 0;
  for (int y = 0; y <= g.height() - th; y += step) {
    for (int x = 0; x <= g.width() - tw; x += step) {
      long sum = 0;
      int n = 0;
      for (int yy = 0; yy < th; yy += 2) {
        const uchar* row = g.constScanLine(y + yy);
        for (int xx = 0; xx < tw; xx += 2) {
          sum += row[x + xx];
          ++n;
        }
      }
      if (n == 0) continue;
      const double mean = double(sum) / n;
      double var = 0;
      for (int yy = 0; yy < th; yy += 2) {
        const uchar* row = g.constScanLine(y + yy);
        for (int xx = 0; xx < tw; xx += 2) {
          const double d = row[x + xx] - mean;
          var += d * d;
        }
      }
      if (var > best) {
        best = var;
        bx = x;
        by = y;
      }
    }
  }
  if (best < 1.0) return centerCrop(src, tw, th);
  return src.copy(bx, by, tw, th);
}

QVector<TemplateHit> findTemplate(const QImage& scene, const QImage& templ,
                                  double minScore, int maxMatches, int step) {
  QVector<TemplateHit> hits;
  if (scene.isNull() || templ.isNull()) return hits;
  int sw = 0, sh = 0, tw = 0, th = 0;
  const QVector<uchar> S = toGray(scene, sw, sh);
  const QVector<uchar> T = toGray(templ, tw, th);
  if (tw > sw || th > sh || tw < 4 || th < 4) return hits;
  if (step <= 0) {
    const int span = qMax(sw, sh);
    step = span > 900 ? 8 : (span > 480 ? 4 : 2);
  }
  const int n = tw * th;
  const double denom = 255.0 * n;

  struct Cand {
    int x, y;
    double score;
  };
  QVector<Cand> cands;
  cands.reserve(64);
  for (int y = 0; y <= sh - th; y += step) {
    for (int x = 0; x <= sw - tw; x += step) {
      long sad = 0;
      for (int ty = 0; ty < th; ++ty) {
        const uchar* row = S.constData() + (y + ty) * sw + x;
        const uchar* trow = T.constData() + ty * tw;
        for (int tx = 0; tx < tw; ++tx) sad += qAbs(int(row[tx]) - int(trow[tx]));
      }
      const double score = 1.0 - double(sad) / denom;
      if (score + 1e-6 < minScore) continue;
      cands.push_back({x, y, score});
    }
  }
  std::sort(cands.begin(), cands.end(),
            [](const Cand& a, const Cand& b) { return a.score > b.score; });

  const int keep = qMax(1, maxMatches);
  for (const Cand& c : cands) {
    QRect rect(c.x, c.y, tw, th);
    bool overlap = false;
    for (const TemplateHit& kept : hits) {
      const QRect inter = rect.intersected(kept.rect);
      if (!inter.isEmpty()) {
        const double iou =
            double(inter.width() * inter.height()) /
            double(rect.width() * rect.height() + kept.rect.width() * kept.rect.height() -
                   inter.width() * inter.height());
        if (iou > 0.3) {
          overlap = true;
          break;
        }
      }
    }
    if (overlap) continue;
    TemplateHit hit;
    hit.rect = rect;
    hit.score = c.score;
    hits.push_back(hit);
    if (hits.size() >= keep) break;
  }
  return hits;
}

}  // namespace sieans_qt
