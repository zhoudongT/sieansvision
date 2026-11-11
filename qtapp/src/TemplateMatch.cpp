#include "TemplateMatch.hpp"
#include "SoftFrame.hpp"

#include <QHash>
#include <QtMath>
#include <algorithm>
#include <cmath>
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
    hit.angleDeg = 0;
    hit.scale = 1;
    hit.center = rect.center();
    hit.corners << rect.topLeft() << rect.topRight() << rect.bottomRight()
                << rect.bottomLeft();
    hits.push_back(hit);
    if (hits.size() >= keep) break;
  }
  return hits;
}

namespace {

struct RotatedTpl {
  QVector<uchar> gray;
  QVector<uchar> mask;
  int w = 0;
  int h = 0;
  double angleDeg = 0;
  QPointF centerInTpl;  // template center mapped into rotated bitmap
};

RotatedTpl rotateTemplateGray(const QVector<uchar>& T, int tw, int th, double angleDeg) {
  RotatedTpl out;
  out.angleDeg = angleDeg;
  const double rad = qDegreesToRadians(angleDeg);
  const double c = std::cos(rad);
  const double s = std::sin(rad);
  const double cx = (tw - 1) * 0.5;
  const double cy = (th - 1) * 0.5;
  auto map = [&](double x, double y) -> QPointF {
    const double dx = x - cx, dy = y - cy;
    return QPointF(c * dx - s * dy, s * dx + c * dy);
  };
  const QPointF p0 = map(0, 0), p1 = map(tw - 1, 0), p2 = map(tw - 1, th - 1),
                p3 = map(0, th - 1);
  const double minX = std::min(std::min(p0.x(), p1.x()), std::min(p2.x(), p3.x()));
  const double maxX = std::max(std::max(p0.x(), p1.x()), std::max(p2.x(), p3.x()));
  const double minY = std::min(std::min(p0.y(), p1.y()), std::min(p2.y(), p3.y()));
  const double maxY = std::max(std::max(p0.y(), p1.y()), std::max(p2.y(), p3.y()));
  const int rw = qMax(4, int(std::ceil(maxX - minX + 1)));
  const int rh = qMax(4, int(std::ceil(maxY - minY + 1)));
  out.w = rw;
  out.h = rh;
  out.gray.fill(0, rw * rh);
  out.mask.fill(0, rw * rh);
  // inverse map: from rotated pixel to original
  const double ic = c, is_ = s;  // rotation inverse is -angle: c, -s / s stays with signs
  out.centerInTpl = QPointF(-minX, -minY);  // where (0,0) local center lands
  // For dest pixel (x,y), local rot = (x + minX, y + minY), then unrotate to template
  for (int y = 0; y < rh; ++y) {
    for (int x = 0; x < rw; ++x) {
      const double rx = x + minX;
      const double ry = y + minY;
      const double ox = ic * rx + is_ * ry + cx;   // R(-θ) = [c s; -s c]? 
      // Forward: [c -s; s c] * (dx,dy)
      // Inverse: [c s; -s c] * r
      const double oy = -is_ * rx + ic * ry + cy;
      const int ix = int(std::floor(ox + 0.5));
      const int iy = int(std::floor(oy + 0.5));
      if (ix < 0 || iy < 0 || ix >= tw || iy >= th) continue;
      out.gray[y * rw + x] = T[iy * tw + ix];
      out.mask[y * rw + x] = 255;
    }
  }
  out.centerInTpl = QPointF(-minX, -minY);
  return out;
}

QPolygonF hitCorners(const RotatedTpl& rt, int x, int y, int tw, int th, double angleDeg) {
  const double rad = qDegreesToRadians(angleDeg);
  const double c = std::cos(rad), s = std::sin(rad);
  const double cx = (tw - 1) * 0.5, cy = (th - 1) * 0.5;
  const QPointF origin(x + rt.centerInTpl.x(), y + rt.centerInTpl.y());
  auto map = [&](double px, double py) {
    const double dx = px - cx, dy = py - cy;
    return QPointF(origin.x() + c * dx - s * dy, origin.y() + s * dx + c * dy);
  };
  QPolygonF poly;
  poly << map(0, 0) << map(tw - 1, 0) << map(tw - 1, th - 1) << map(0, th - 1);
  return poly;
}

}  // namespace

QImage resolveLocateTemplate(const QImage& scene, const QVariantMap& params,
                             QString* error, bool* created, QString* pathOut) {
  if (created) *created = false;
  const QString src =
      params.value(QStringLiteral("templateSource"), QStringLiteral("file")).toString();
  if (src == QLatin1String("soft_plate") || src == QLatin1String("soft_scene_plate")) {
    if (scene.isNull()) {
      if (error) *error = QStringLiteral("当前图像为空，无法生成标牌模板");
      return {};
    }
    QImage tpl = makeSoftScenePlateTemplate(scene.width(), scene.height());
    if (tpl.isNull() && error) *error = QStringLiteral("无法从 soft 场景裁出标牌模板");
    return tpl;
  }
  QString path = params.value(QStringLiteral("templatePath")).toString().trimmed();
  if (!path.isEmpty()) {
    QImage tpl(path);
    if (tpl.isNull()) {
      if (error) *error = QStringLiteral("无法读取模板: %1").arg(path);
      return {};
    }
    if (pathOut) *pathOut = path;
    return tpl;
  }
  // capture from current
  const int tw = params.value(QStringLiteral("templateW"), 80).toInt();
  const int th = params.value(QStringLiteral("templateH"), 64).toInt();
  QImage tpl = salientCrop(scene, tw, th);
  if (tpl.isNull()) {
    if (error) *error = QStringLiteral("目标定位需要模板图，可上传或从原图框选模板");
    return {};
  }
  if (created) *created = true;
  return tpl;
}

LocateResult runLocate(const QImage& scene, const QVariantMap& params) {
  LocateResult r;
  if (scene.isNull()) {
    r.error = QStringLiteral("当前图像为空");
    r.note = r.error;
    return r;
  }
  bool created = false;
  QString path;
  QString err;
  QImage tpl = resolveLocateTemplate(scene, params, &err, &created, &path);
  r.templateCreated = created;
  r.templatePath = path;
  r.templateUsed = tpl;
  if (tpl.isNull()) {
    r.error = err.isEmpty() ? QStringLiteral("目标定位需要模板图，可上传或从原图框选模板") : err;
    r.note = r.error;
    return r;
  }
  const double minScore = params.value(QStringLiteral("minScore"), 0.55).toDouble();
  const int maxN = qBound(1, params.value(QStringLiteral("maxMatches"), 1).toInt(), 50);
  const double iouThr =
      params.value(QStringLiteral("overlapThreshold"), 0.3).toDouble();
  double a0 = params.value(QStringLiteral("angleStart"), 0).toDouble();
  double a1 = params.value(QStringLiteral("angleEnd"), a0).toDouble();
  double aStep = params.value(QStringLiteral("angleStep"), 10).toDouble();
  const bool angleOn = !params.contains(QStringLiteral("angleEnable")) ||
                       params.value(QStringLiteral("angleEnable")).toBool();
  if (!angleOn) {
    a1 = a0;
    aStep = 10;
  }
  if (a1 < a0) {
    r.error = QStringLiteral("angleEnd 必须大于等于 angleStart");
    r.note = r.error;
    return r;
  }
  if (aStep < 1) aStep = 1;
  QVector<double> angles;
  for (double a = a0; a <= a1 + 1e-6; a += aStep) angles.push_back(a);
  if (angles.isEmpty() || qAbs(angles.last() - a1) > 1e-6) angles.push_back(a1);
  if (angles.size() > 256) {
    r.error = QStringLiteral("旋转搜索超过 256 档，请增大角度步长");
    r.note = r.error;
    return r;
  }

  int sw = 0, sh = 0, tw = 0, th = 0;
  const QVector<uchar> S = toGray(scene, sw, sh);
  const QVector<uchar> T = toGray(tpl, tw, th);
  if (tw > sw || th > sh || tw < 4 || th < 4) {
    r.error = QStringLiteral("模板需至少 4×4 且不大于搜索图");
    r.note = r.error;
    return r;
  }

  int step = params.value(QStringLiteral("step"), 0).toInt();
  if (step <= 0) {
    const int span = qMax(sw, sh);
    step = span > 900 ? 8 : (span > 480 ? 4 : 2);
    const int shortSide = qMin(tw, th);
    if (shortSide <= 48) step = qMin(step, 2);
    else if (shortSide <= 80) step = qMin(step, 4);
  }

  struct Cand {
    int x, y;
    double score;
    double angle;
    int rw, rh;
    QPointF centerOff;  // center in rotated bitmap
  };
  QVector<Cand> cands;

  for (double ang : angles) {
    RotatedTpl rt;
    if (qAbs(ang) < 1e-9) {
      rt.w = tw;
      rt.h = th;
      rt.gray = T;
      rt.mask = QVector<uchar>(tw * th, 255);
      rt.centerInTpl = QPointF((tw - 1) * 0.5, (th - 1) * 0.5);
      rt.angleDeg = 0;
    } else {
      rt = rotateTemplateGray(T, tw, th, ang);
    }
    if (rt.w > sw || rt.h > sh) continue;
    int maskN = 0;
    for (uchar m : rt.mask)
      if (m) ++maskN;
    if (maskN < 16) continue;
    const double denom = 255.0 * maskN;
    const double coarseMin = qMax(0.2, minScore - 0.25);
    auto scoreAt = [&](int x, int y) -> double {
      if (x < 0 || y < 0 || x > sw - rt.w || y > sh - rt.h) return -1;
      long sad = 0;
      for (int ty = 0; ty < rt.h; ++ty) {
        const uchar* row = S.constData() + (y + ty) * sw + x;
        const uchar* trow = rt.gray.constData() + ty * rt.w;
        const uchar* mrow = rt.mask.constData() + ty * rt.w;
        for (int tx = 0; tx < rt.w; ++tx) {
          if (!mrow[tx]) continue;
          sad += qAbs(int(row[tx]) - int(trow[tx]));
        }
      }
      return 1.0 - double(sad) / denom;
    };
    QVector<Cand> coarse;
    for (int y = 0; y <= sh - rt.h; y += step) {
      for (int x = 0; x <= sw - rt.w; x += step) {
        const double score = scoreAt(x, y);
        if (score + 1e-6 < coarseMin) continue;
        coarse.push_back({x, y, score, ang, rt.w, rt.h, rt.centerInTpl});
      }
    }
    std::sort(coarse.begin(), coarse.end(), [](const Cand& a, const Cand& b) {
      return a.score > b.score;
    });
    const int refineN = qMin(coarse.size(), 24);
    const int rad = qMax(step, 1);
    for (int i = 0; i < refineN; ++i) {
      const Cand& c0 = coarse[i];
      Cand best = c0;
      const int x0 = qMax(0, c0.x - rad), x1 = qMin(sw - rt.w, c0.x + rad);
      const int y0 = qMax(0, c0.y - rad), y1 = qMin(sh - rt.h, c0.y + rad);
      for (int y = y0; y <= y1; ++y) {
        for (int x = x0; x <= x1; ++x) {
          const double sc = scoreAt(x, y);
          if (sc > best.score) {
            best.x = x;
            best.y = y;
            best.score = sc;
          }
        }
      }
      if (best.score + 1e-6 >= minScore) cands.push_back(best);
    }
  }

  std::sort(cands.begin(), cands.end(), [](const Cand& a, const Cand& b) {
    if (a.score != b.score) return a.score > b.score;
    if (a.angle != b.angle) return a.angle < b.angle;
    if (a.y != b.y) return a.y < b.y;
    return a.x < b.x;
  });

  auto aabbOf = [](const QPolygonF& poly) {
    if (poly.isEmpty()) return QRect();
    QRectF b = poly.boundingRect();
    return b.toAlignedRect();
  };

  for (const Cand& c : cands) {
    TemplateHit hit;
    hit.score = c.score;
    hit.angleDeg = c.angle;
    hit.scale = 1;
    hit.center = QPointF(c.x + c.centerOff.x(), c.y + c.centerOff.y());
    hit.corners = hitCorners([&]() {
      RotatedTpl dummy;
      dummy.centerInTpl = c.centerOff;
      dummy.w = c.rw;
      dummy.h = c.rh;
      dummy.angleDeg = c.angle;
      return dummy;
    }(), c.x, c.y, tw, th, c.angle);
    hit.rect = aabbOf(hit.corners);
    if (hit.rect.isEmpty())
      hit.rect = QRect(c.x, c.y, c.rw, c.rh);

    bool overlap = false;
    for (const TemplateHit& kept : r.hits) {
      const QRect inter = hit.rect.intersected(kept.rect);
      if (inter.isEmpty()) continue;
      const double iou =
          double(inter.width() * inter.height()) /
          double(qMax(1, hit.rect.width() * hit.rect.height() +
                             kept.rect.width() * kept.rect.height() -
                             inter.width() * inter.height()));
      if (iou > iouThr) {
        overlap = true;
        break;
      }
    }
    if (overlap) continue;
    r.hits.push_back(hit);
    if (r.hits.size() >= maxN) break;
  }

  r.ok = !r.hits.isEmpty();
  if (r.ok) {
    r.note = QStringLiteral("%1 个 · 分数 %2 · 角度 %3°")
                 .arg(r.hits.size())
                 .arg(r.hits.first().score, 0, 'f', 3)
                 .arg(r.hits.first().angleDeg, 0, 'f', 1);
  } else {
    r.note = QStringLiteral("未找到达到分数阈值的匹配");
  }
  return r;
}


}  // namespace sieans_qt
