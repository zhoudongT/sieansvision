#include "GeometryFind.hpp"
#include "SoftFrame.hpp"
#include "FixturePose.hpp"

#include <QPainter>
#include <QtGlobal>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

namespace sieans_qt {
namespace {

int clampi(int v, int lo, int hi) { return qBound(lo, v, hi); }

QImage toGray(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_Grayscale8);
}

QImage boxBlurGray(const QImage& src, int k) {
  if (src.isNull() || k < 3) return src;
  if (k % 2 == 0) ++k;
  const int r = k / 2;
  QImage img = src.convertToFormat(QImage::Format_Grayscale8);
  const int w = img.width();
  const int h = img.height();
  QImage tmp(w, h, QImage::Format_Grayscale8);
  std::vector<int> acc(static_cast<size_t>(w + 1), 0);
  for (int y = 0; y < h; ++y) {
    const uchar* in = img.constScanLine(y);
    acc[0] = 0;
    for (int x = 0; x < w; ++x) acc[x + 1] = acc[x] + in[x];
    uchar* out = tmp.scanLine(y);
    for (int x = 0; x < w; ++x) {
      const int x0 = qMax(0, x - r);
      const int x1 = qMin(w - 1, x + r);
      const int n = x1 - x0 + 1;
      out[x] = uchar((acc[x1 + 1] - acc[x0] + n / 2) / n);
    }
  }
  QImage dst(w, h, QImage::Format_Grayscale8);
  std::vector<int> pre(static_cast<size_t>(h + 1), 0);
  std::vector<int> col(static_cast<size_t>(h), 0);
  for (int x = 0; x < w; ++x) {
    for (int y = 0; y < h; ++y) col[static_cast<size_t>(y)] = tmp.constScanLine(y)[x];
    pre[0] = 0;
    for (int y = 0; y < h; ++y)
      pre[static_cast<size_t>(y + 1)] = pre[static_cast<size_t>(y)] + col[static_cast<size_t>(y)];
    for (int y = 0; y < h; ++y) {
      const int y0 = qMax(0, y - r);
      const int y1 = qMin(h - 1, y + r);
      const int n = y1 - y0 + 1;
      dst.scanLine(y)[x] = uchar((pre[y1 + 1] - pre[y0] + n / 2) / n);
    }
  }
  return dst;
}

struct WorkGray {
  QImage img;
  int w = 0;
  int h = 0;
  const uchar* row(int y) const { return img.constScanLine(y); }
};

WorkGray makeWork(const QImage& src, int filterSize) {
  WorkGray g;
  g.img = toGray(src);
  if (filterSize > 1) {
    const int k = filterSize * 2 + 1;
    g.img = boxBlurGray(g.img, k);
  }
  g.w = g.img.width();
  g.h = g.img.height();
  return g;
}

QString featureNorm(const QString& raw) {
  const QString f = raw.trimmed().toLower();
  if (f == QLatin1String("line") || f == QLatin1String("lines") ||
      f == QLatin1String("直线"))
    return QStringLiteral("lines");
  if (f == QLatin1String("circle") || f == QLatin1String("circles") ||
      f == QLatin1String("圆") || f == QLatin1String("circles"))
    return QStringLiteral("circles");
  if (f == QLatin1String("rect") || f == QLatin1String("rects") ||
      f == QLatin1String("rectangle") || f == QLatin1String("矩形"))
    return QStringLiteral("rects");
  if (f == QLatin1String("edge") || f == QLatin1String("edges") ||
      f == QLatin1String("边缘"))
    return QStringLiteral("edges");
  return QStringLiteral("contours");
}

struct Blob {
  int x0 = 0, y0 = 0, x1 = 0, y1 = 0;
  int area = 0;
  qint64 sumX = 0, sumY = 0;
  int perimeter = 0;
};

QVector<Blob> labelBlobs(const QImage& mask, int minArea, int collectCap) {
  QVector<Blob> out;
  if (mask.isNull()) return out;
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<uchar> seen(static_cast<size_t>(n), 0);
  const int dx[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
  const int dy[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
  std::vector<int> stack;
  stack.reserve(1024);
  auto at = [&](int x, int y) -> uchar { return mask.constScanLine(y)[x]; };
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!row[x] || seen[static_cast<size_t>(i0)]) continue;
      stack.clear();
      stack.push_back(i0);
      seen[static_cast<size_t>(i0)] = 1;
      Blob b;
      b.x0 = b.x1 = x;
      b.y0 = b.y1 = y;
      b.area = 0;
      b.sumX = 0;
      b.sumY = 0;
      b.perimeter = 0;
      while (!stack.empty()) {
        const int i = stack.back();
        stack.pop_back();
        const int cx = i % w;
        const int cy = i / w;
        ++b.area;
        b.sumX += cx;
        b.sumY += cy;
        if (cx < b.x0) b.x0 = cx;
        if (cx > b.x1) b.x1 = cx;
        if (cy < b.y0) b.y0 = cy;
        if (cy > b.y1) b.y1 = cy;
        int open = 0;
        if (cx == 0 || !at(cx - 1, cy)) ++open;
        if (cx == w - 1 || !at(cx + 1, cy)) ++open;
        if (cy == 0 || !at(cx, cy - 1)) ++open;
        if (cy == h - 1 || !at(cx, cy + 1)) ++open;
        b.perimeter += open;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + dx[k];
          const int ny = cy + dy[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (seen[static_cast<size_t>(ni)] || !at(nx, ny)) continue;
          seen[static_cast<size_t>(ni)] = 1;
          stack.push_back(ni);
        }
      }
      if (b.area < minArea) continue;
      out.push_back(b);
      if (out.size() >= collectCap) {
        // keep going would be slow; stop if we already have plenty
        if (out.size() >= collectCap) return out;
      }
    }
  }
  return out;
}

QImage thresholdMask(const WorkGray& g, int threshold, bool invert) {
  QImage mask(g.w, g.h, QImage::Format_Grayscale8);
  mask.fill(0);
  for (int y = 0; y < g.h; ++y) {
    const uchar* in = g.row(y);
    uchar* out = mask.scanLine(y);
    for (int x = 0; x < g.w; ++x) {
      const bool on = invert ? (in[x] < threshold) : (in[x] >= threshold);
      out[x] = on ? 255 : 0;
    }
  }
  return mask;
}

struct GradField {
  int w = 0, h = 0;
  std::vector<float> gx, gy, mag;
};

GradField computeSobel(const WorkGray& g) {
  GradField f;
  f.w = g.w;
  f.h = g.h;
  const size_t n = static_cast<size_t>(g.w * g.h);
  f.gx.assign(n, 0);
  f.gy.assign(n, 0);
  f.mag.assign(n, 0);
  auto at = [&](int x, int y) -> int {
    x = clampi(x, 0, g.w - 1);
    y = clampi(y, 0, g.h - 1);
    return g.row(y)[x];
  };
  for (int y = 1; y < g.h - 1; ++y) {
    for (int x = 1; x < g.w - 1; ++x) {
      const int i = y * g.w + x;
      const int gx = -at(x - 1, y - 1) + at(x + 1, y - 1) - 2 * at(x - 1, y) +
                     2 * at(x + 1, y) - at(x - 1, y + 1) + at(x + 1, y + 1);
      const int gy = -at(x - 1, y - 1) - 2 * at(x, y - 1) - at(x + 1, y - 1) +
                     at(x - 1, y + 1) + 2 * at(x, y + 1) + at(x + 1, y + 1);
      f.gx[static_cast<size_t>(i)] = float(gx);
      f.gy[static_cast<size_t>(i)] = float(gy);
      f.mag[static_cast<size_t>(i)] = std::sqrt(float(gx * gx + gy * gy));
    }
  }
  return f;
}

QImage cannyEdges(const GradField& f, float low, float high) {
  const int w = f.w, h = f.h;
  QImage nms(w, h, QImage::Format_Grayscale8);
  nms.fill(0);
  auto dirBin = [](float gx, float gy) -> int {
    // 0: 0°, 1: 45°, 2: 90°, 3: 135°
    const float ang = std::atan2(gy, gx) * 180.0f / float(M_PI);
    float a = ang;
    if (a < 0) a += 180.0f;
    if (a < 22.5f || a >= 157.5f) return 0;
    if (a < 67.5f) return 1;
    if (a < 112.5f) return 2;
    return 3;
  };
  const int ox[4] = {1, 1, 0, -1};
  const int oy[4] = {0, 1, 1, 1};
  for (int y = 1; y < h - 1; ++y) {
    uchar* row = nms.scanLine(y);
    for (int x = 1; x < w - 1; ++x) {
      const int i = y * w + x;
      const float m = f.mag[static_cast<size_t>(i)];
      if (m < low) continue;
      const int d = dirBin(f.gx[static_cast<size_t>(i)], f.gy[static_cast<size_t>(i)]);
      const int i1 = (y + oy[d]) * w + (x + ox[d]);
      const int i2 = (y - oy[d]) * w + (x - ox[d]);
      if (m >= f.mag[static_cast<size_t>(i1)] && m >= f.mag[static_cast<size_t>(i2)])
        row[x] = (m >= high) ? 255 : 128;
    }
  }
  // hysteresis
  std::vector<int> stack;
  QImage out(w, h, QImage::Format_Grayscale8);
  out.fill(0);
  for (int y = 1; y < h - 1; ++y) {
    const uchar* row = nms.constScanLine(y);
    for (int x = 1; x < w - 1; ++x) {
      if (row[x] == 255) stack.push_back(y * w + x);
    }
  }
  const int dx[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
  const int dy[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
  while (!stack.empty()) {
    const int i = stack.back();
    stack.pop_back();
    const int x = i % w;
    const int y = i / w;
    uchar* row = out.scanLine(y);
    if (row[x]) continue;
    row[x] = 255;
    for (int k = 0; k < 8; ++k) {
      const int nx = x + dx[k];
      const int ny = y + dy[k];
      if (nx <= 0 || ny <= 0 || nx >= w - 1 || ny >= h - 1) continue;
      if (out.constScanLine(ny)[nx]) continue;
      if (nms.constScanLine(ny)[nx] == 0) continue;
      stack.push_back(ny * w + nx);
    }
  }
  return out;
}

struct EdgePt {
  int x, y;
};

std::vector<EdgePt> collectEdges(const QImage& edges) {
  std::vector<EdgePt> pts;
  if (edges.isNull()) return pts;
  const int w = edges.width(), h = edges.height();
  pts.reserve(static_cast<size_t>(w + h));
  for (int y = 0; y < h; ++y) {
    const uchar* row = edges.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      if (row[x]) pts.push_back({x, y});
    }
  }
  return pts;
}

QPolygonF circlePoly(const QPointF& c, double r, int n = 16) {
  QPolygonF p;
  if (r <= 0) {
    p << c;
    return p;
  }
  p.reserve(n);
  for (int i = 0; i < n; ++i) {
    const double a = (2.0 * M_PI * i) / n;
    p << QPointF(c.x() + r * std::cos(a), c.y() + r * std::sin(a));
  }
  return p;
}

GeometryItem fromBlobContour(const Blob& b) {
  GeometryItem it;
  it.kind = QStringLiteral("contour");
  const double cx = b.area ? double(b.sumX) / b.area : (b.x0 + b.x1) * 0.5;
  const double cy = b.area ? double(b.sumY) / b.area : (b.y0 + b.y1) * 0.5;
  it.center = QPointF(cx, cy);
  it.area = b.area;
  // 4-neighbor openings counted twice (each edge shared) → /2, plus a little
  it.perimeter = 0.5 * b.perimeter;
  if (it.perimeter < 1) it.perimeter = 1;
  it.width = b.x1 - b.x0 + 1;
  it.height = b.y1 - b.y0 + 1;
  it.bbox = QRectF(b.x0, b.y0, it.width, it.height);
  it.fillRatio = it.area / qMax(1.0, it.width * it.height);
  it.circularity =
      (4.0 * M_PI * it.area) / qMax(1.0, it.perimeter * it.perimeter);
  it.polygon << QPointF(b.x0, b.y0) << QPointF(b.x1 + 1, b.y0)
             << QPointF(b.x1 + 1, b.y1 + 1) << QPointF(b.x0, b.y1 + 1);
  return it;
}

GeometryItem fromBlobRect(const QImage& mask, const Blob& b) {
  GeometryItem it = fromBlobContour(b);
  it.kind = QStringLiteral("rect");
  // PCA orientation of the blob pixels
  const double cx = it.center.x();
  const double cy = it.center.y();
  double cxx = 0, cyy = 0, cxy = 0;
  int n = 0;
  const int x0 = b.x0, y0 = b.y0, x1 = b.x1, y1 = b.y1;
  for (int y = y0; y <= y1; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = x0; x <= x1; ++x) {
      if (!row[x]) continue;
      const double dx = x - cx;
      const double dy = y - cy;
      cxx += dx * dx;
      cyy += dy * dy;
      cxy += dx * dy;
      ++n;
    }
  }
  double angle = 0;
  if (n >= 4) {
    cxx /= n;
    cyy /= n;
    cxy /= n;
    angle = 0.5 * std::atan2(2.0 * cxy, cxx - cyy);
  }
  const double c = std::cos(angle);
  const double s = std::sin(angle);
  double minU = 1e18, maxU = -1e18, minV = 1e18, maxV = -1e18;
  for (int y = y0; y <= y1; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = x0; x <= x1; ++x) {
      if (!row[x]) continue;
      const double dx = x - cx;
      const double dy = y - cy;
      const double u = dx * c + dy * s;
      const double v = -dx * s + dy * c;
      if (u < minU) minU = u;
      if (u > maxU) maxU = u;
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }
  }
  double wu = maxU - minU;
  double hv = maxV - minV;
  if (wu <= 0) wu = 1;
  if (hv <= 0) hv = 1;
  // report width = shorter side, height = longer (match engine.geometry)
  it.width = qMin(wu, hv);
  it.height = qMax(wu, hv);
  it.angleDeg = angle * 180.0 / M_PI;
  it.area = wu * hv;
  const double mu = 0.5 * (minU + maxU);
  const double mv = 0.5 * (minV + maxV);
  it.center = QPointF(cx + mu * c - mv * s, cy + mu * s + mv * c);
  auto corner = [&](double u, double v) {
    return QPointF(cx + u * c - v * s, cy + u * s + v * c);
  };
  it.polygon.clear();
  it.polygon << corner(minU, minV) << corner(maxU, minV) << corner(maxU, maxV)
             << corner(minU, maxV);
  it.bbox = it.polygon.boundingRect();
  return it;
}

QVector<GeometryItem> findContoursOrRects(const WorkGray& g, const QVariantMap& p,
                                          bool asRects) {
  const int thr = clampi(p.value(QStringLiteral("threshold"), 127).toInt(), 0, 255);
  const bool invert = p.value(QStringLiteral("invert"), false).toBool();
  const int minArea = qMax(1, p.value(QStringLiteral("minArea"), 50).toInt());
  const int maxCount = clampi(p.value(QStringLiteral("maxCount"), 50).toInt(), 1, 100);
  const QImage mask = thresholdMask(g, thr, invert);
  QVector<Blob> blobs = labelBlobs(mask, minArea, 2000);
  std::sort(blobs.begin(), blobs.end(),
            [](const Blob& a, const Blob& b) { return a.area > b.area; });
  QVector<GeometryItem> items;
  const double minR = p.value(QStringLiteral("minRadius"), 0).toDouble();
  const double maxR = p.value(QStringLiteral("maxRadius"), 0).toDouble();
  for (const Blob& b : blobs) {
    GeometryItem it = asRects ? fromBlobRect(mask, b) : fromBlobContour(b);
    if (asRects) {
      const double half = qMax(it.width, it.height) * 0.5;
      if (minR > 0 && half < minR) continue;
      if (maxR > 0 && half > maxR) continue;
    }
    items.push_back(it);
    if (items.size() >= maxCount) break;
  }
  return items;
}

QVector<GeometryItem> findLines(const WorkGray& g, const QImage& edges,
                                const QVariantMap& p) {
  QVector<GeometryItem> items;
  const auto pts = collectEdges(edges);
  if (pts.size() < 8) return items;
  const int votesThr = qMax(1, p.value(QStringLiteral("votes"), 40).toInt());
  const double minLen = qMax(1.0, p.value(QStringLiteral("minLength"), 40).toDouble());
  const int maxCount = clampi(p.value(QStringLiteral("maxCount"), 50).toInt(), 1, 100);
  const bool reverse = p.value(QStringLiteral("reverseFind"), false).toBool();
  const bool angNorm = p.value(QStringLiteral("angleNormalize"), false).toBool();
  const int nTheta = 180;
  const int maxRho = int(std::ceil(std::hypot(double(g.w), double(g.h)))) + 2;
  const int nRho = maxRho * 2 + 1;
  std::vector<int> acc(static_cast<size_t>(nRho * nTheta), 0);
  std::vector<float> ctab(nTheta), stab(nTheta);
  for (int t = 0; t < nTheta; ++t) {
    const double a = t * M_PI / 180.0;
    ctab[static_cast<size_t>(t)] = float(std::cos(a));
    stab[static_cast<size_t>(t)] = float(std::sin(a));
  }
  for (const EdgePt& e : pts) {
    for (int t = 0; t < nTheta; ++t) {
      const int rho = int(std::lround(e.x * ctab[static_cast<size_t>(t)] +
                                      e.y * stab[static_cast<size_t>(t)])) +
                      maxRho;
      if (rho < 0 || rho >= nRho) continue;
      ++acc[static_cast<size_t>(rho * nTheta + t)];
    }
  }
  struct Peak {
    int rho, theta, votes;
  };
  std::vector<Peak> peaks;
  for (int rho = 2; rho < nRho - 2; ++rho) {
    for (int t = 0; t < nTheta; ++t) {
      const int v = acc[static_cast<size_t>(rho * nTheta + t)];
      if (v < votesThr) continue;
      bool local = true;
      for (int dr = -2; dr <= 2 && local; ++dr) {
        for (int dt = -2; dt <= 2; ++dt) {
          if (!dr && !dt) continue;
          int tt = t + dt;
          int rr = rho + dr;
          if (tt < 0) {
            tt += nTheta;
            rr = 2 * maxRho - rr;
          } else if (tt >= nTheta) {
            tt -= nTheta;
            rr = 2 * maxRho - rr;
          }
          if (rr < 0 || rr >= nRho) continue;
          if (acc[static_cast<size_t>(rr * nTheta + tt)] > v) {
            local = false;
            break;
          }
        }
      }
      if (local) peaks.push_back({rho - maxRho, t, v});
    }
  }
  std::sort(peaks.begin(), peaks.end(),
            [](const Peak& a, const Peak& b) { return a.votes > b.votes; });

  const double distTol = qMax(2.0, p.value(QStringLiteral("maxGap"), 10).toDouble());
  for (const Peak& pk : peaks) {
    if (items.size() >= maxCount) break;
    const double ct = ctab[static_cast<size_t>(pk.theta)];
    const double st = stab[static_cast<size_t>(pk.theta)];
    const double rho = pk.rho;
    // skip peaks too similar to an already accepted line
    bool dup = false;
    for (const GeometryItem& ex : items) {
      const QPointF mid = (ex.start + ex.end) * 0.5;
      const double exAng = std::atan2(ex.end.y() - ex.start.y(),
                                      ex.end.x() - ex.start.x()) *
                           180.0 / M_PI;
      // Candidate segment angle is along the line (normal is pk.theta).
      const double candAng = (pk.theta + 90.0);
      double dang = std::abs(exAng - candAng);
      dang = std::fmod(dang, 180.0);
      if (dang > 90.0) dang = 180.0 - dang;
      const double d = std::abs(mid.x() * ct + mid.y() * st - rho);
      if (dang < 10.0 && d < 12.0) {
        dup = true;
        break;
      }
    }
    if (dup) continue;
    double minP = 1e18, maxP = -1e18;
    int used = 0;
    // direction along the line: (-st, ct)
    for (const EdgePt& e : pts) {
      const double d = std::abs(e.x * ct + e.y * st - rho);
      if (d > distTol) continue;
      const double proj = -e.x * st + e.y * ct;
      if (proj < minP) minP = proj;
      if (proj > maxP) maxP = proj;
      ++used;
    }
    const double length = maxP - minP;
    if (used < 8 || length < minLen) continue;
    // point on line at proj p: x = rho*ct - p*st, y = rho*st + p*ct
    QPointF p0(rho * ct - minP * st, rho * st + minP * ct);
    QPointF p1(rho * ct - maxP * st, rho * st + maxP * ct);
    if (reverse) std::swap(p0, p1);
    GeometryItem it;
    it.kind = QStringLiteral("line");
    it.start = p0;
    it.end = p1;
    it.center = (p0 + p1) * 0.5;
    it.length = length;
    it.angleDeg = std::atan2(p1.y() - p0.y(), p1.x() - p0.x()) * 180.0 / M_PI;
    if (angNorm) {
      it.angleDeg = std::fmod(it.angleDeg + 360.0, 180.0);
    }
    it.score = pk.votes;
    it.polygon << p0 << p1 << p1 << p0;
    it.bbox = QRectF(p0, p1).normalized().adjusted(-1, -1, 1, 1);
    items.push_back(it);
  }
  return items;
}


bool kasaFit(const std::vector<EdgePt>& pts, double& cx, double& cy, double& r) {
  if (pts.size() < 8) return false;
  double sxx = 0, syy = 0, sxy = 0, sx = 0, sy = 0;
  double sxz = 0, syz = 0, sz = 0;
  const int n = int(pts.size());
  for (const EdgePt& e : pts) {
    const double x = e.x, y = e.y, z = x * x + y * y;
    sx += x;
    sy += y;
    sxx += x * x;
    syy += y * y;
    sxy += x * y;
    sxz += x * z;
    syz += y * z;
    sz += z;
  }
  // 3x3: [sxx sxy sx; sxy syy sy; sx sy n] * [A B C] = [sxz syz sz]
  double A[3][4] = {
      {sxx, sxy, sx, sxz},
      {sxy, syy, sy, syz},
      {sx, sy, double(n), sz},
  };
  for (int i = 0; i < 3; ++i) {
    int piv = i;
    for (int r = i + 1; r < 3; ++r)
      if (std::abs(A[r][i]) > std::abs(A[piv][i])) piv = r;
    if (std::abs(A[piv][i]) < 1e-9) return false;
    if (piv != i)
      for (int c = 0; c < 4; ++c) std::swap(A[i][c], A[piv][c]);
    const double d = A[i][i];
    for (int c = i; c < 4; ++c) A[i][c] /= d;
    for (int r = 0; r < 3; ++r) {
      if (r == i) continue;
      const double f = A[r][i];
      for (int c = i; c < 4; ++c) A[r][c] -= f * A[i][c];
    }
  }
  const double a = A[0][3], b = A[1][3], c = A[2][3];
  cx = -0.5 * a;
  cy = -0.5 * b;
  const double r2 = cx * cx + cy * cy - c;
  if (r2 <= 1.0) return false;
  r = std::sqrt(r2);
  return std::isfinite(cx) && std::isfinite(cy) && std::isfinite(r);
}


QVector<GeometryItem> findCirclesFromBlobs(const WorkGray& g, const QVariantMap& p,
                                           int minR, int maxR, int maxCount) {
  QVector<GeometryItem> items;
  const int thr = clampi(p.value(QStringLiteral("threshold"), 127).toInt(), 0, 255);
  const bool userInv = p.value(QStringLiteral("invert"), false).toBool();
  const bool hasInv = p.contains(QStringLiteral("invert"));
  const int tries = hasInv ? 1 : 2;
  for (int t = 0; t < tries; ++t) {
    const bool inv = hasInv ? userInv : (t == 0);  // prefer dark-on-light first
    const QImage mask = thresholdMask(g, thr, inv);
    QVector<Blob> blobs = labelBlobs(mask, qMax(8, int(0.4 * M_PI * minR * minR)), 500);
    for (const Blob& b : blobs) {
      const double eqR = std::sqrt(b.area / M_PI);
      if (eqR < minR - 2 || eqR > maxR + 2) continue;
      GeometryItem it = fromBlobContour(b);
      if (it.circularity < 0.65) continue;
      // mean radius of boundary-ish bbox edge is coarse; use equivalent + bbox
      const double boxR = 0.25 * (it.width + it.height);
      const double r = 0.5 * (eqR + boxR);
      if (r < minR - 1 || r > maxR + 1) continue;
      it.kind = QStringLiteral("circle");
      it.radius = r;
      it.diameter = 2.0 * r;
      it.score = it.circularity * 100.0;
      it.polygon = circlePoly(it.center, r);
      it.bbox = QRectF(it.center.x() - r, it.center.y() - r, 2 * r, 2 * r);
      items.push_back(it);
      if (items.size() >= maxCount) return items;
    }
    if (!items.isEmpty()) break;
  }
  return items;
}

QVector<GeometryItem> findCircles(const WorkGray& g, const GradField& f,
                                  const QImage& edges, const QVariantMap& p) {
  QVector<GeometryItem> items;
  int minR = qMax(2, p.value(QStringLiteral("minRadius"), 5).toInt());
  int maxR = qMax(minR + 1, p.value(QStringLiteral("maxRadius"), 200).toInt());
  const int ai = p.value(QStringLiteral("annulusInner"), 0).toInt();
  const int ao = p.value(QStringLiteral("annulusOuter"), 0).toInt();
  if (ao > 0) {
    if (ai > 0) minR = qMax(minR, ai);
    maxR = (maxR <= 0) ? ao : qMin(maxR, ao);
  }
  if (maxR > qMin(g.w, g.h) / 2) maxR = qMin(g.w, g.h) / 2;
  if (maxR < minR) return items;
  const int minDist =
      qMax(1, p.value(QStringLiteral("minDistance"), 30).toInt());
  const int votesThr = qMax(1, p.value(QStringLiteral("votes"), 30).toInt());
  const int maxCount = clampi(p.value(QStringLiteral("maxCount"), 50).toInt(), 1, 100);

  QVector<GeometryItem> blobHits = findCirclesFromBlobs(g, p, minR, maxR, maxCount);
  if (blobHits.size() >= maxCount) return blobHits;

  const auto pts = collectEdges(edges);
  if (pts.size() < 8) return blobHits;
  items = blobHits;

  const int w = g.w, h = g.h;
  std::vector<int> acc(static_cast<size_t>(w * h), 0);
  const int rStep = (maxR - minR > 80) ? 2 : 1;
  for (const EdgePt& e : pts) {
    const int i = e.y * w + e.x;
    const float mag = f.mag[static_cast<size_t>(i)];
    if (mag < 1.0f) continue;
    const float nx = f.gx[static_cast<size_t>(i)] / mag;
    const float ny = f.gy[static_cast<size_t>(i)] / mag;
    for (int dir = -1; dir <= 1; dir += 2) {
      for (int r = minR; r <= maxR; r += rStep) {
        const int cx = int(std::lround(e.x + dir * r * nx));
        const int cy = int(std::lround(e.y + dir * r * ny));
        if (cx <= 1 || cy <= 1 || cx >= w - 2 || cy >= h - 2) continue;
        ++acc[static_cast<size_t>(cy * w + cx)];
      }
    }
  }

  struct Peak {
    int x, y, votes;
  };
  std::vector<Peak> peaks;
  const int nmsR = 3;
  for (int y = 2; y < h - 2; ++y) {
    for (int x = 2; x < w - 2; ++x) {
      const int v = acc[static_cast<size_t>(y * w + x)];
      if (v < votesThr) continue;
      bool local = true;
      for (int dy = -nmsR; dy <= nmsR && local; ++dy) {
        for (int dx = -nmsR; dx <= nmsR; ++dx) {
          if (!dx && !dy) continue;
          if (acc[static_cast<size_t>((y + dy) * w + (x + dx))] > v) {
            local = false;
            break;
          }
        }
      }
      if (local) peaks.push_back({x, y, v});
    }
  }
  std::sort(peaks.begin(), peaks.end(),
            [](const Peak& a, const Peak& b) { return a.votes > b.votes; });

  for (const Peak& pk : peaks) {
    if (items.size() >= maxCount) break;
    bool near = false;
    for (const GeometryItem& ex : items) {
      const double dx = ex.center.x() - pk.x;
      const double dy = ex.center.y() - pk.y;
      if (std::hypot(dx, dy) < minDist) {
        near = true;
        break;
      }
    }
    if (near) continue;
    // radius histogram
    const int bins = maxR - minR + 3;
    std::vector<int> hist(static_cast<size_t>(bins), 0);
    for (const EdgePt& e : pts) {
      const double d = std::hypot(double(e.x - pk.x), double(e.y - pk.y));
      const int ir = int(std::lround(d));
      if (ir < minR - 1 || ir > maxR + 1) continue;
      const int b = clampi(ir - minR + 1, 0, bins - 1);
      ++hist[static_cast<size_t>(b)];
    }
    int bestB = 0, bestV = 0;
    for (int i = 0; i < bins; ++i) {
      const int sm = hist[static_cast<size_t>(i)] +
                     (i ? hist[static_cast<size_t>(i - 1)] : 0) +
                     (i + 1 < bins ? hist[static_cast<size_t>(i + 1)] : 0);
      if (sm > bestV) {
        bestV = sm;
        bestB = i;
      }
    }
    const double radius = double(bestB + minR - 1);
    if (radius < minR - 0.5 || radius > maxR + 0.5 || bestV < votesThr / 2)
      continue;
    QPointF center(pk.x, pk.y);
    double r = radius;
    std::vector<EdgePt> ring;
    ring.reserve(64);
    for (const EdgePt& e : pts) {
      const double d = std::hypot(double(e.x - pk.x), double(e.y - pk.y));
      if (std::abs(d - radius) <= 3.5) ring.push_back(e);
    }
    double fx = pk.x, fy = pk.y, fr = radius;
    if (kasaFit(ring, fx, fy, fr) && fr >= minR - 1 && fr <= maxR + 1 &&
        std::hypot(fx - pk.x, fy - pk.y) <= 8.0) {
      center = QPointF(fx, fy);
      r = fr;
    } else if (!ring.empty()) {
      double sr = 0;
      for (const EdgePt& e : ring)
        sr += std::hypot(double(e.x - pk.x), double(e.y - pk.y));
      r = sr / ring.size();
    }
    GeometryItem it;
    it.kind = QStringLiteral("circle");
    it.center = center;
    it.radius = r;
    it.diameter = 2.0 * r;
    it.area = M_PI * r * r;
    it.score = pk.votes;
    it.polygon = circlePoly(center, r);
    it.bbox = QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r);
    items.push_back(it);
  }
  return items;
}

void applyJudge(GeometryResult& r, const QVariantMap& p) {
  r.judgeEnable = p.value(QStringLiteral("judgeEnable"), false).toBool();
  double jmin = p.value(QStringLiteral("judgeMin"), 0).toDouble();
  double jmax = p.value(QStringLiteral("judgeMax"), 99999).toDouble();
  if (jmax < jmin) std::swap(jmin, jmax);
  const QString mode = r.feature;
  auto metric = [&](const GeometryItem& it) -> double {
    if (mode == QLatin1String("lines") || mode == QLatin1String("edges"))
      return it.length > 0 ? it.length : it.score;
    if (mode == QLatin1String("circles")) return it.radius;
    if (mode == QLatin1String("rects") || mode == QLatin1String("contours"))
      return it.area;
    return it.score;
  };
  bool allOk = true;
  for (GeometryItem& it : r.items) {
    it.judgeMetric = metric(it);
    it.judgeOk = !r.judgeEnable || (it.judgeMetric >= jmin && it.judgeMetric <= jmax);
    it.judgeStatus = it.judgeOk ? QStringLiteral("OK") : QStringLiteral("NG");
    if (!it.judgeOk) allOk = false;
  }
  if (!r.judgeEnable)
    r.judgeOk = true;
  else
    r.judgeOk = !r.items.isEmpty() && allOk;
}

void mapItemToImage(GeometryItem& it, const Pose2D& pose, const FollowRoi& fr,
                    const QPoint& origin, bool follow) {
  auto mapPt = [&](const QPointF& p) -> QPointF {
    if (follow)
      return poseMap(pose, QPointF(fr.roiX + p.x(), fr.roiY + p.y()));
    return QPointF(p.x() + origin.x(), p.y() + origin.y());
  };
  it.center = mapPt(it.center);
  it.start = mapPt(it.start);
  it.end = mapPt(it.end);
  QPolygonF np;
  for (const QPointF& q : it.polygon) np << mapPt(q);
  it.polygon = np;
  if (!np.isEmpty())
    it.bbox = np.boundingRect();
  else
    it.bbox = QRectF(it.center, it.center);
}

}  // namespace

GeometryResult runGeometry(const QImage& src, const QVariantMap& paramsIn) {
  GeometryResult r;
  QVariantMap params = paramsIn;
  r.feature = featureNorm(params.value(QStringLiteral("feature"),
                                       QStringLiteral("contours"))
                              .toString());
  r.method = QStringLiteral("qimage");
  r.judgeEnable = params.value(QStringLiteral("judgeEnable"), false).toBool();
  if (src.isNull() || src.width() < 8 || src.height() < 8) {
    r.error = QStringLiteral("geometry 需要输入图像");
    r.note = r.error;
    return r;
  }

  // soft-scene auto ROI
  {
    const QString target =
        params.value(QStringLiteral("target")).toString().trimmed().toLower();
    const int w = src.width();
    const int h = src.height();
    const bool follow = params.value(QStringLiteral("followFixture")).toBool();
    const bool hasRoi = params.value(QStringLiteral("roiW"), 0).toInt() > 0 &&
                        params.value(QStringLiteral("roiH"), 0).toInt() > 0;
    if (!follow && !hasRoi &&
        (target == QLatin1String("soft_circle") ||
         target == QLatin1String("soft-circle"))) {
      const QPoint c = softSceneGeomCircleCenter(w, h);
      const int rad = softSceneGeomCircleRadius(w, h);
      const int m = rad + 16;
      params.insert(QStringLiteral("roiX"), c.x() - m);
      params.insert(QStringLiteral("roiY"), c.y() - m);
      params.insert(QStringLiteral("roiW"), 2 * m);
      params.insert(QStringLiteral("roiH"), 2 * m);
      if (!params.contains(QStringLiteral("minRadius")))
        params.insert(QStringLiteral("minRadius"), qMax(8, rad - 10));
      if (!params.contains(QStringLiteral("maxRadius")))
        params.insert(QStringLiteral("maxRadius"), rad + 12);
    } else if (!follow && !hasRoi &&
               (target == QLatin1String("soft_line") ||
                target == QLatin1String("soft-line"))) {
      const QLine L = softSceneGeomLine(w, h);
      const int pad = 18;
      const int x0 = qMin(L.x1(), L.x2()) - pad;
      const int y0 = qMin(L.y1(), L.y2()) - pad;
      const int x1 = qMax(L.x1(), L.x2()) + pad;
      const int y1 = qMax(L.y1(), L.y2()) + pad;
      params.insert(QStringLiteral("roiX"), x0);
      params.insert(QStringLiteral("roiY"), y0);
      params.insert(QStringLiteral("roiW"), x1 - x0);
      params.insert(QStringLiteral("roiH"), y1 - y0);
      if (!params.contains(QStringLiteral("minLength")))
        params.insert(QStringLiteral("minLength"),
                      qMax(40, int(0.5 * std::hypot(double(L.dx()), double(L.dy())))));
    } else if (follow &&
               (target == QLatin1String("soft_follow") ||
                target == QLatin1String("soft-follow") ||
                target == QLatin1String("soft_follow_circle"))) {
      if (!hasRoi) {
        const int rad = softSceneGeomFollowCircleRadius(w, h);
        const QRect plate = softScenePlateRect(w, h);
        const int localY = plate.height() / 2 + 8;
        params.insert(QStringLiteral("roiX"), -rad - 16);
        params.insert(QStringLiteral("roiY"), localY);
        params.insert(QStringLiteral("roiW"), 2 * rad + 32);
        params.insert(QStringLiteral("roiH"), 2 * rad + 28);
      }
      if (!params.contains(QStringLiteral("minRadius")))
        params.insert(QStringLiteral("minRadius"),
                      qMax(6, softSceneGeomFollowCircleRadius(w, h) - 8));
      if (!params.contains(QStringLiteral("maxRadius")))
        params.insert(QStringLiteral("maxRadius"),
                      softSceneGeomFollowCircleRadius(w, h) + 12);
    }
  }

  Pose2D followPose;
  FollowRoi followRoi;
  QImage work = src;
  QPoint origin(0, 0);
  bool follow = false;
  if (params.value(QStringLiteral("followFixture")).toBool()) {
    followRoi = resolveFollowRoi(params, src.width(), src.height());
    if (followRoi.active) {
      followPose = poseFromParams(params);
      followPose.ok = true;
      work = extractFollowPatch(src, followRoi, followPose);
      follow = !work.isNull();
      origin = QPoint(0, 0);
    }
  }
  if (!follow) {
    const int rw = params.value(QStringLiteral("roiW"), 0).toInt();
    const int rh = params.value(QStringLiteral("roiH"), 0).toInt();
    if (rw > 0 && rh > 0) {
      const int rx =
          clampi(params.value(QStringLiteral("roiX"), 0).toInt(), 0, src.width() - 1);
      const int ry = clampi(params.value(QStringLiteral("roiY"), 0).toInt(), 0,
                            src.height() - 1);
      const int ww = clampi(rw, 1, src.width() - rx);
      const int hh = clampi(rh, 1, src.height() - ry);
      work = src.copy(rx, ry, ww, hh);
      origin = QPoint(rx, ry);
    }
  }
  if (work.isNull() || work.width() < 4 || work.height() < 4) {
    r.error = QStringLiteral("geometry ROI 为空");
    r.note = r.error;
    return r;
  }

  const int filt = clampi(params.value(QStringLiteral("filterSize"), 1).toInt(), 1, 31);
  const WorkGray g = makeWork(work, filt);

  float cannyLow = float(params.value(QStringLiteral("cannyLow"), 50).toDouble());
  float cannyHigh = float(params.value(QStringLiteral("cannyHigh"), 150).toDouble());
  if (params.contains(QStringLiteral("edgeThreshold"))) {
    const double et = params.value(QStringLiteral("edgeThreshold")).toDouble();
    if (et >= 1 && et <= 255) {
      cannyLow = float(et);
      cannyHigh = qMax(cannyHigh, float(et * 2));
    }
  }

  const QString mode = r.feature;
  if (mode == QLatin1String("contours")) {
    r.items = findContoursOrRects(g, params, false);
    r.method = QStringLiteral("threshold+cc");
  } else if (mode == QLatin1String("rects")) {
    r.items = findContoursOrRects(g, params, true);
    r.method = QStringLiteral("minrect");
  } else {
    const GradField grad = computeSobel(g);
    const QImage edges = cannyEdges(grad, cannyLow, cannyHigh);
    r.edgePixels = 0;
    for (int y = 0; y < edges.height(); ++y) {
      const uchar* row = edges.constScanLine(y);
      for (int x = 0; x < edges.width(); ++x)
        if (row[x]) ++r.edgePixels;
    }
    if (mode == QLatin1String("edges")) {
      GeometryItem it;
      it.kind = QStringLiteral("edge");
      it.score = r.edgePixels;
      it.length = r.edgePixels;
      r.items.push_back(it);
      r.method = QStringLiteral("canny");
    } else if (mode == QLatin1String("lines")) {
      r.items = findLines(g, edges, params);
      r.method = QStringLiteral("hough");
    } else if (mode == QLatin1String("circles")) {
      r.items = findCircles(g, grad, edges, params);
      r.method = QStringLiteral("hough");
    } else {
      r.error = QStringLiteral("feature 必须是 lines、circles、rects、edges 或 contours");
      r.note = r.error;
      return r;
    }
  }

  for (GeometryItem& it : r.items)
    mapItemToImage(it, followPose, followRoi, origin, follow);

  r.count = r.items.size();
  r.ok = true;
  applyJudge(r, params);
  r.note = QStringLiteral("QImage 几何查找 · %1 · %2 ×%3")
               .arg(r.feature, r.method)
               .arg(r.count);
  if (r.judgeEnable)
    r.note += r.judgeOk ? QStringLiteral(" · 判定OK") : QStringLiteral(" · 判定NG");
  return r;
}

QStringList geometrySelfTest() {
  QStringList fails;
  auto expect = [&](bool cond, const char* msg) {
    if (!cond) fails << QString::fromUtf8(msg);
  };

  // synthetic 240×200 canvas: dark circle + dark line + dark rectangle
  QImage img(240, 200, QImage::Format_RGB888);
  img.fill(QColor(230, 230, 230));
  {
    QPainter p(&img);
    p.setRenderHint(QPainter::Antialiasing, false);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(20, 20, 20));
    p.drawEllipse(QPoint(80, 70), 25, 25);
    p.setPen(QPen(QColor(20, 20, 20), 6, Qt::SolidLine, Qt::FlatCap));
    p.drawLine(QLine(20, 160, 180, 160));
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(20, 20, 20));
    p.drawRect(QRect(150, 30, 50, 30));
    p.end();
  }

  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("circles"));
    p.insert(QStringLiteral("minRadius"), 15);
    p.insert(QStringLiteral("maxRadius"), 40);
    p.insert(QStringLiteral("minDistance"), 20);
    p.insert(QStringLiteral("votes"), 12);
    p.insert(QStringLiteral("roiX"), 40);
    p.insert(QStringLiteral("roiY"), 30);
    p.insert(QStringLiteral("roiW"), 80);
    p.insert(QStringLiteral("roiH"), 80);
    p.insert(QStringLiteral("judgeEnable"), true);
    p.insert(QStringLiteral("judgeMin"), 20);
    p.insert(QStringLiteral("judgeMax"), 30);
    const GeometryResult r = runGeometry(img, p);
    expect(r.ok, "circle ok");
    expect(r.count >= 1, "circle count>=1");
    if (!r.items.isEmpty()) {
      const GeometryItem& it = r.items.first();
      expect(std::abs(it.center.x() - 80) <= 2.5, "circle cx≈80");
      expect(std::abs(it.center.y() - 70) <= 2.5, "circle cy≈70");
      expect(std::abs(it.radius - 25) <= 2.5, "circle r≈25");
      expect(it.judgeOk, "circle judge OK");
    } else {
      expect(false, "circle item");
    }
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("lines"));
    p.insert(QStringLiteral("minLength"), 80);
    p.insert(QStringLiteral("votes"), 20);
    p.insert(QStringLiteral("roiX"), 8);
    p.insert(QStringLiteral("roiY"), 140);
    p.insert(QStringLiteral("roiW"), 200);
    p.insert(QStringLiteral("roiH"), 40);
    p.insert(QStringLiteral("judgeEnable"), true);
    p.insert(QStringLiteral("judgeMin"), 140);
    p.insert(QStringLiteral("judgeMax"), 200);
    const GeometryResult r = runGeometry(img, p);
    expect(r.ok, "line ok");
    expect(r.count >= 1, "line count>=1");
    if (!r.items.isEmpty()) {
      const GeometryItem& it = r.items.first();
      expect(it.length >= 140 && it.length <= 185, "line length≈160");
      const double ang = std::abs(it.angleDeg);
      const double ang2 = std::min(ang, 180.0 - ang);
      expect(ang2 <= 8.0, "line angle≈0");
      expect(it.judgeOk, "line judge OK");
    } else {
      expect(false, "line item");
    }
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("contours"));
    p.insert(QStringLiteral("threshold"), 127);
    p.insert(QStringLiteral("invert"), true);
    p.insert(QStringLiteral("minArea"), 200);
    p.insert(QStringLiteral("maxCount"), 10);
    const GeometryResult r = runGeometry(img, p);
    expect(r.ok, "contour ok");
    expect(r.count >= 2, "contour count>=2");
    bool foundCircle = false;
    for (const GeometryItem& it : r.items) {
      if (std::abs(it.center.x() - 80) <= 4 && std::abs(it.center.y() - 70) <= 4 &&
          it.area >= 1500)
        foundCircle = true;
    }
    expect(foundCircle, "contour includes circle blob");
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("rects"));
    p.insert(QStringLiteral("threshold"), 127);
    p.insert(QStringLiteral("invert"), true);
    p.insert(QStringLiteral("minArea"), 200);
    p.insert(QStringLiteral("roiX"), 140);
    p.insert(QStringLiteral("roiY"), 20);
    p.insert(QStringLiteral("roiW"), 70);
    p.insert(QStringLiteral("roiH"), 50);
    const GeometryResult r = runGeometry(img, p);
    expect(r.ok, "rect ok");
    expect(r.count >= 1, "rect count>=1");
    if (!r.items.isEmpty()) {
      const GeometryItem& it = r.items.first();
      expect(std::abs(it.center.x() - 175) <= 4, "rect cx≈175");
      expect(std::abs(it.center.y() - 45) <= 4, "rect cy≈45");
      expect(it.width >= 24 && it.height >= 24, "rect size");
    }
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("edges"));
    p.insert(QStringLiteral("roiX"), 40);
    p.insert(QStringLiteral("roiY"), 30);
    p.insert(QStringLiteral("roiW"), 80);
    p.insert(QStringLiteral("roiH"), 80);
    const GeometryResult r = runGeometry(img, p);
    expect(r.ok, "edges ok");
    expect(r.edgePixels > 80, "edgePixels>80");
  }
  // followFixture: translate the source, search in fixture-local ROI
  {
    QImage shifted(240, 200, QImage::Format_RGB888);
    shifted.fill(QColor(230, 230, 230));
    {
      QPainter p(&shifted);
      p.setRenderHint(QPainter::Antialiasing, false);
      p.setPen(Qt::NoPen);
      p.setBrush(QColor(20, 20, 20));
      // fixture origin at (40, 20); circle local (40, 50) → image (80, 70)
      p.drawEllipse(QPoint(80, 70), 25, 25);
      p.end();
    }
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("circles"));
    p.insert(QStringLiteral("followFixture"), true);
    p.insert(QStringLiteral("fixtureX"), 40);
    p.insert(QStringLiteral("fixtureY"), 20);
    p.insert(QStringLiteral("fixtureAngle"), 0);
    p.insert(QStringLiteral("fixtureScale"), 1);
    p.insert(QStringLiteral("fixtureOk"), 1);
    p.insert(QStringLiteral("roiX"), 10);
    p.insert(QStringLiteral("roiY"), 20);
    p.insert(QStringLiteral("roiW"), 60);
    p.insert(QStringLiteral("roiH"), 60);
    p.insert(QStringLiteral("minRadius"), 15);
    p.insert(QStringLiteral("maxRadius"), 40);
    p.insert(QStringLiteral("votes"), 12);
    const GeometryResult r = runGeometry(shifted, p);
    expect(r.ok, "follow ok");
    expect(r.count >= 1, "follow count>=1");
    if (!r.items.isEmpty()) {
      const GeometryItem& it = r.items.first();
      expect(std::abs(it.center.x() - 80) <= 3.0, "follow cx image≈80");
      expect(std::abs(it.center.y() - 70) <= 3.0, "follow cy image≈70");
    } else {
      expect(false, "follow item");
    }
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("circles"));
    p.insert(QStringLiteral("minRadius"), 15);
    p.insert(QStringLiteral("maxRadius"), 40);
    p.insert(QStringLiteral("votes"), 12);
    p.insert(QStringLiteral("roiX"), 40);
    p.insert(QStringLiteral("roiY"), 30);
    p.insert(QStringLiteral("roiW"), 80);
    p.insert(QStringLiteral("roiH"), 80);
    p.insert(QStringLiteral("judgeEnable"), true);
    p.insert(QStringLiteral("judgeMin"), 40);
    p.insert(QStringLiteral("judgeMax"), 50);
    const GeometryResult r = runGeometry(img, p);
    expect(r.ok, "judge-ng ran");
    expect(r.count >= 1, "judge-ng count");
    expect(!r.judgeOk, "judge NG when radius out of range");
  }
  return fails;
}

}  // namespace sieans_qt
