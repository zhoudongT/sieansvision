#include "TemplateMatch.hpp"
#include "SoftFrame.hpp"

#include <QFileInfo>
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

/** 双线性缩放灰度模板，供均匀/各向异性尺度搜索。 */
QVector<uchar> resizeGray(const QVector<uchar>& T, int tw, int th, int nw, int nh) {
  QVector<uchar> out(nw * nh, 0);
  if (tw <= 0 || th <= 0 || nw <= 0 || nh <= 0) return out;
  for (int y = 0; y < nh; ++y) {
    const double oy = (nh == 1) ? 0.0 : (y + 0.5) * th / nh - 0.5;
    const int y0 = qBound(0, int(std::floor(oy)), th - 1);
    const int y1 = qMin(th - 1, y0 + 1);
    const double ty = oy - y0;
    for (int x = 0; x < nw; ++x) {
      const double ox = (nw == 1) ? 0.0 : (x + 0.5) * tw / nw - 0.5;
      const int x0 = qBound(0, int(std::floor(ox)), tw - 1);
      const int x1 = qMin(tw - 1, x0 + 1);
      const double tx = ox - x0;
      const double v = (1 - tx) * (1 - ty) * T[y0 * tw + x0] + tx * (1 - ty) * T[y0 * tw + x1] +
                       (1 - tx) * ty * T[y1 * tw + x0] + tx * ty * T[y1 * tw + x1];
      out[y * nw + x] = static_cast<uchar>(qBound(0, qRound(v), 255));
    }
  }
  return out;
}

enum class MatchMetric { Sad, Ncc };

MatchMetric parseMetric(const QVariantMap& params) {
  const QString m = params.value(QStringLiteral("metric"),
                                 params.value(QStringLiteral("matchMode"), QStringLiteral("sad")))
                        .toString()
                        .trimmed()
                        .toLower();
  if (m == QLatin1String("ncc") || m == QLatin1String("zncc") || m == QLatin1String("correlation") ||
      m == QLatin1String("corr"))
    return MatchMetric::Ncc;
  return MatchMetric::Sad;
}

/** 在掩膜有效像素上计算 SAD（1=相同）或零均值 NCC（[-1,1]）。 */
double scoreWindow(const QVector<uchar>& S, int sw, int sh, const RotatedTpl& rt, int x, int y,
                   MatchMetric metric) {
  if (x < 0 || y < 0 || x > sw - rt.w || y > sh - rt.h) return -1;
  if (metric == MatchMetric::Sad) {
    long sad = 0;
    int maskN = 0;
    for (int ty = 0; ty < rt.h; ++ty) {
      const uchar* row = S.constData() + (y + ty) * sw + x;
      const uchar* trow = rt.gray.constData() + ty * rt.w;
      const uchar* mrow = rt.mask.constData() + ty * rt.w;
      for (int tx = 0; tx < rt.w; ++tx) {
        if (!mrow[tx]) continue;
        sad += qAbs(int(row[tx]) - int(trow[tx]));
        ++maskN;
      }
    }
    if (maskN < 16) return -1;
    return 1.0 - double(sad) / (255.0 * maskN);
  }
  double sumS = 0, sumT = 0, sumSS = 0, sumTT = 0, sumST = 0;
  int n = 0;
  for (int ty = 0; ty < rt.h; ++ty) {
    const uchar* row = S.constData() + (y + ty) * sw + x;
    const uchar* trow = rt.gray.constData() + ty * rt.w;
    const uchar* mrow = rt.mask.constData() + ty * rt.w;
    for (int tx = 0; tx < rt.w; ++tx) {
      if (!mrow[tx]) continue;
      const double sv = row[tx];
      const double tv = trow[tx];
      sumS += sv;
      sumT += tv;
      sumSS += sv * sv;
      sumTT += tv * tv;
      sumST += sv * tv;
      ++n;
    }
  }
  if (n < 16) return -1;
  const double num = n * sumST - sumS * sumT;
  const double denS = n * sumSS - sumS * sumS;
  const double denT = n * sumTT - sumT * sumT;
  if (denS <= 1e-9 || denT <= 1e-9) return -1;
  return num / std::sqrt(denS * denT);
}

struct DeformPart {
  RotatedTpl rt;
  int ox = 0;
  int oy = 0;
};

/** 把旋转/缩放后的模板切成 gx×gy 块，块内有效像素太少则丢弃。 */
QVector<DeformPart> splitDeformParts(const RotatedTpl& src, int gx, int gy) {
  QVector<DeformPart> out;
  gx = qBound(1, gx, 3);
  gy = qBound(1, gy, 3);
  if (src.w < 8 || src.h < 8) return out;
  for (int iy = 0; iy < gy; ++iy) {
    for (int ix = 0; ix < gx; ++ix) {
      const int x0 = ix * src.w / gx;
      const int y0 = iy * src.h / gy;
      const int x1 = (ix + 1) * src.w / gx;
      const int y1 = (iy + 1) * src.h / gy;
      const int pw = x1 - x0;
      const int ph = y1 - y0;
      if (pw < 8 || ph < 8) continue;
      DeformPart part;
      part.ox = x0;
      part.oy = y0;
      part.rt.w = pw;
      part.rt.h = ph;
      part.rt.angleDeg = src.angleDeg;
      part.rt.gray.resize(pw * ph);
      part.rt.mask.resize(pw * ph);
      int on = 0;
      for (int y = 0; y < ph; ++y) {
        for (int x = 0; x < pw; ++x) {
          const int si = (y0 + y) * src.w + (x0 + x);
          part.rt.gray[y * pw + x] = src.gray[si];
          const uchar m = src.mask.isEmpty() ? 255 : src.mask[si];
          part.rt.mask[y * pw + x] = m;
          if (m) ++on;
        }
      }
      if (on < 16) continue;
      part.rt.centerInTpl = QPointF((pw - 1) * 0.5, (ph - 1) * 0.5);
      out.push_back(part);
    }
  }
  return out;
}

/**
 * 在锚点 (x,y)（未变形模板左上）上做分块弹性匹配：每块在 ±radius 内寻找最佳位移，
 * 得分为各块度量均值减去 λ×平均 |位移|/radius。位移超出图像则该块失败。
 */
double scoreDeform(const QVector<uchar>& S, int sw, int sh, const QVector<DeformPart>& parts, int x,
                   int y, int radius, double lambda, MatchMetric metric) {
  if (parts.size() < 2) return -1;
  radius = qBound(1, radius, 24);
  lambda = qBound(0.0, lambda, 1.0);
  double sum = 0;
  double pen = 0;
  int okN = 0;
  for (const DeformPart& part : parts) {
    double best = -1;
    int bestDx = 0, bestDy = 0;
    const int step = radius > 8 ? 2 : 1;
    for (int dy = -radius; dy <= radius; dy += step) {
      for (int dx = -radius; dx <= radius; dx += step) {
        const int px = x + part.ox + dx;
        const int py = y + part.oy + dy;
        const double sc = scoreWindow(S, sw, sh, part.rt, px, py, metric);
        if (sc > best) {
          best = sc;
          bestDx = dx;
          bestDy = dy;
        }
      }
    }
    if (step > 1 && best >= 0) {
      for (int dy = bestDy - 1; dy <= bestDy + 1; ++dy) {
        for (int dx = bestDx - 1; dx <= bestDx + 1; ++dx) {
          if (dx < -radius || dx > radius || dy < -radius || dy > radius) continue;
          const int px = x + part.ox + dx;
          const int py = y + part.oy + dy;
          const double sc = scoreWindow(S, sw, sh, part.rt, px, py, metric);
          if (sc > best) {
            best = sc;
            bestDx = dx;
            bestDy = dy;
          }
        }
      }
    }
    if (best < 0) return -1;
    sum += best;
    pen += std::hypot(double(bestDx), double(bestDy)) / double(radius);
    ++okN;
  }
  if (okN < 2) return -1;
  return sum / okN - lambda * (pen / okN);
}

QVector<double> scaleSteps(double lo, double hi, double step, bool enable) {
  QVector<double> out;
  if (!enable) {
    out.push_back(1.0);
    return out;
  }
  if (hi < lo) std::swap(lo, hi);
  if (step < 1e-4) step = 0.1;
  lo = qBound(0.2, lo, 4.0);
  hi = qBound(0.2, hi, 4.0);
  for (double s = lo; s <= hi + 1e-9; s += step) out.push_back(s);
  if (out.isEmpty()) out.push_back(1.0);
  return out;
}

}  // namespace

QImage resolveLocateTemplate
(const QImage& scene, const QVariantMap& params,
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

  struct TplSrc {
    QImage img;
    QString name;
    QString path;
  };
  QVector<TplSrc> tpls;
  const QVariantList lib = params.value(QStringLiteral("templateLibrary")).toList();
  const QString extraPaths = params.value(QStringLiteral("templatePaths")).toString().trimmed();
  const bool hasLib = !lib.isEmpty() || !extraPaths.isEmpty();
  const QString srcKind =
      params.value(QStringLiteral("templateSource"), QStringLiteral("file")).toString();
  const bool forceSingle =
      (srcKind == QLatin1String("soft_plate") || srcKind == QLatin1String("soft_scene_plate") ||
       srcKind == QLatin1String("capture") ||
       !params.value(QStringLiteral("templatePath")).toString().trimmed().isEmpty() || !hasLib);
  bool created = false;
  QString path;
  QString err;
  if (forceSingle) {
    QImage tpl = resolveLocateTemplate(scene, params, &err, &created, &path);
    r.templateCreated = created;
    r.templatePath = path;
    r.templateUsed = tpl;
    if (!tpl.isNull()) {
      TplSrc ts;
      ts.img = tpl;
      ts.name = QStringLiteral("current");
      ts.path = path;
      tpls.push_back(ts);
    }
  }
  auto addPath = [&](const QString& pth, const QString& name) {
    const QString p = pth.trimmed();
    if (p.isEmpty()) return;
    for (const TplSrc& e : tpls)
      if (e.path == p) return;
    QImage im(p);
    if (im.isNull()) return;
    TplSrc ts;
    ts.img = im;
    ts.name = name.isEmpty() ? QFileInfo(p).completeBaseName() : name;
    ts.path = p;
    tpls.push_back(ts);
    if (r.templateUsed.isNull()) {
      r.templateUsed = im;
      r.templatePath = p;
    }
  };
  for (const QVariant& v : lib) {
    const QVariantMap e = v.toMap();
    addPath(e.value(QStringLiteral("path")).toString(), e.value(QStringLiteral("name")).toString());
  }
  if (!extraPaths.isEmpty()) {
    const QStringList parts = extraPaths.split(QLatin1Char(','), Qt::SkipEmptyParts);
    for (const QString& p : parts) addPath(p, {});
  }
  if (tpls.isEmpty()) {
    r.error = err.isEmpty() ? QStringLiteral("目标定位需要模板图，可上传、从原图框选或加入模板库") : err;
    r.note = r.error;
    return r;
  }

  const double minScore = params.value(QStringLiteral("minScore"), 0.55).toDouble();
  const int maxN = qBound(1, params.value(QStringLiteral("maxMatches"), 1).toInt(), 50);
  const double iouThr = params.value(QStringLiteral("overlapThreshold"), 0.3).toDouble();
  const MatchMetric metric = parseMetric(params);
  const QString modeStr =
      params.value(QStringLiteral("matchMode"), QStringLiteral("fast")).toString().trimmed().toLower();
  const bool deformOn = params.value(QStringLiteral("deformEnable"), false).toBool() ||
                        modeStr == QLatin1String("deform") || modeStr == QLatin1String("deformable") ||
                        modeStr == QLatin1String("elastic");
  int deformGx = params.value(QStringLiteral("deformGridX"), 0).toInt();
  int deformGy = params.value(QStringLiteral("deformGridY"), 0).toInt();
  const int deformRadius = qBound(1, params.value(QStringLiteral("deformRadius"), 16).toInt(), 24);
  const double deformLambda = qBound(0.0, params.value(QStringLiteral("deformLambda"), 0.15).toDouble(), 1.0);
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

  const bool scaleOn = params.value(QStringLiteral("scaleEnable"), false).toBool();
  const bool aniso = params.value(QStringLiteral("scaleAniso"), false).toBool();
  const QVector<double> sxs = scaleSteps(params.value(QStringLiteral("scaleMin"), 1.0).toDouble(),
                                         params.value(QStringLiteral("scaleMax"), 1.0).toDouble(),
                                         params.value(QStringLiteral("scaleStep"), 0.1).toDouble(),
                                         scaleOn);
  const QVector<double> sys =
      aniso ? scaleSteps(
                  params.value(QStringLiteral("scaleYMin"), params.value(QStringLiteral("scaleMin"), 1.0))
                      .toDouble(),
                  params.value(QStringLiteral("scaleYMax"), params.value(QStringLiteral("scaleMax"), 1.0))
                      .toDouble(),
                  params.value(QStringLiteral("scaleYStep"), params.value(QStringLiteral("scaleStep"), 0.1))
                      .toDouble(),
                  scaleOn)
            : sxs;
  const int combos = tpls.size() * sxs.size() * sys.size() * angles.size();
  if (combos > 400) {
    r.error = QStringLiteral("定位搜索组合 %1 超过 400（模板×尺度×角度），请增大步长或减少模板")
                  .arg(combos);
    r.note = r.error;
    return r;
  }

  int sw = 0, sh = 0;
  const QVector<uchar> S = toGray(scene, sw, sh);

  struct Cand {
    int x, y;
    double score;
    double angle;
    double scaleX, scaleY;
    int rw, rh;
    int tw0, th0;
    int tplIndex;
    QString tplName;
    QPointF centerOff;
  };
  QVector<Cand> cands;

  int step = params.value(QStringLiteral("step"), 0).toInt();
  auto autoStep = [&](int tw, int th) {
    int st = step;
    if (st <= 0) {
      const int span = qMax(sw, sh);
      st = span > 900 ? 8 : (span > 480 ? 4 : 2);
      const int shortSide = qMin(tw, th);
      if (shortSide <= 48)
        st = qMin(st, 2);
      else if (shortSide <= 80)
        st = qMin(st, 4);
    }
    return st;
  };

  for (int ti = 0; ti < tpls.size(); ++ti) {
    int tw = 0, th = 0;
    const QVector<uchar> T = toGray(tpls[ti].img, tw, th);
    if (tw < 4 || th < 4) continue;
    for (double sx : sxs) {
      for (double syv : sys) {
        int stw = tw, sth = th;
        QVector<uchar> Ts = T;
        if (std::fabs(sx - 1.0) > 1e-6 || std::fabs(syv - 1.0) > 1e-6) {
          stw = qMax(4, qRound(tw * sx));
          sth = qMax(4, qRound(th * syv));
          Ts = resizeGray(T, tw, th, stw, sth);
        }
        if (stw > sw || sth > sh) continue;
        const int useStep = autoStep(stw, sth);
        for (double ang : angles) {
          RotatedTpl rt;
          if (qAbs(ang) < 1e-9) {
            rt.w = stw;
            rt.h = sth;
            rt.gray = Ts;
            rt.mask = QVector<uchar>(stw * sth, 255);
            rt.centerInTpl = QPointF((stw - 1) * 0.5, (sth - 1) * 0.5);
            rt.angleDeg = 0;
          } else {
            rt = rotateTemplateGray(Ts, stw, sth, ang);
          }
          if (rt.w > sw || rt.h > sh) continue;
          int gx = deformGx, gy = deformGy;
          if (deformOn && gx <= 0 && gy <= 0) {
            if (rt.w >= 2 * rt.h) {
              gx = 2;
              gy = 1;
            } else if (rt.h >= 2 * rt.w) {
              gx = 1;
              gy = 2;
            } else {
              gx = 2;
              gy = 2;
            }
          }
          const QVector<DeformPart> parts =
              deformOn ? splitDeformParts(rt, qMax(gx, 1), qMax(gy, 1)) : QVector<DeformPart>{};
          if (deformOn && parts.size() < 2) continue;
          const int maxX = sw - rt.w;
          const int maxY = sh - rt.h;
          if (maxX < 0 || maxY < 0) continue;
          auto evalAt = [&](int x, int y) -> double {
            if (deformOn) return scoreDeform(S, sw, sh, parts, x, y, deformRadius, deformLambda, metric);
            return scoreWindow(S, sw, sh, rt, x, y, metric);
          };
          const double coarseMin = qMax(-0.2, minScore - 0.25);
          QVector<Cand> coarse;
          for (int y = 0; y <= maxY; y += useStep) {
            for (int x = 0; x <= maxX; x += useStep) {
              const double score = evalAt(x, y);
              if (score + 1e-6 < coarseMin) continue;
              coarse.push_back({x, y, score, ang, sx, syv, rt.w, rt.h, stw, sth, ti, tpls[ti].name,
                                rt.centerInTpl});
            }
          }
          std::sort(coarse.begin(), coarse.end(),
                    [](const Cand& a, const Cand& b) { return a.score > b.score; });
          const int refineN = qMin(coarse.size(), 24);
          const int rad = qMax(useStep, 1);
          for (int i = 0; i < refineN; ++i) {
            const Cand& c0 = coarse[i];
            Cand best = c0;
            const int x0 = qMax(0, c0.x - rad), x1 = qMin(maxX, c0.x + rad);
            const int y0 = qMax(0, c0.y - rad), y1 = qMin(maxY, c0.y + rad);
            for (int y = y0; y <= y1; ++y) {
              for (int x = x0; x <= x1; ++x) {
                const double sc = evalAt(x, y);
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
      }
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
    return poly.boundingRect().toAlignedRect();
  };

  for (const Cand& c : cands) {
    TemplateHit hit;
    hit.score = c.score;
    hit.angleDeg = c.angle;
    hit.scaleX = c.scaleX;
    hit.scaleY = c.scaleY;
    hit.scale = c.scaleX;
    hit.templateIndex = c.tplIndex;
    hit.templateName = c.tplName;
    hit.center = QPointF(c.x + c.centerOff.x(), c.y + c.centerOff.y());
    hit.corners = hitCorners(
        [&]() {
          RotatedTpl dummy;
          dummy.centerInTpl = c.centerOff;
          dummy.w = c.rw;
          dummy.h = c.rh;
          dummy.angleDeg = c.angle;
          return dummy;
        }(),
        c.x, c.y, c.tw0, c.th0, c.angle);
    hit.rect = aabbOf(hit.corners);
    if (hit.rect.isEmpty()) hit.rect = QRect(c.x, c.y, c.rw, c.rh);

    bool overlap = false;
    for (const TemplateHit& kept : r.hits) {
      const QRect inter = hit.rect.intersected(kept.rect);
      if (inter.isEmpty()) continue;
      const double iou = double(inter.width() * inter.height()) /
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
    const TemplateHit& h0 = r.hits.first();
    r.note = QStringLiteral("%1 个 · 分数 %2 · 角度 %3° · 尺度 %4×%5%6")
                 .arg(r.hits.size())
                 .arg(h0.score, 0, 'f', 3)
                 .arg(h0.angleDeg, 0, 'f', 1)
                 .arg(h0.scaleX, 0, 'f', 2)
                 .arg(h0.scaleY, 0, 'f', 2)
                 .arg(deformOn ? QStringLiteral(" · 弹性分块")
                                     : (metric == MatchMetric::Ncc ? QStringLiteral(" · NCC")
                                                                   : QStringLiteral(" · SAD")));
  } else {
    r.note = QStringLiteral("未找到达到分数阈值的匹配");
  }
  return r;
}


}  // namespace sieans_qt
