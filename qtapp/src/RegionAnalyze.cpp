#include "RegionAnalyze.hpp"

#include <QColor>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <queue>
#include <vector>

namespace sieans_qt {
namespace {

/** 把彩色图转为 8 位灰度；空图返回空。 */
QImage toGray8(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_Grayscale8);
}

/** 在直方图上做 Otsu 阈值；全空或单峰退化时退回 127。 */
int otsuThreshold(const int hist[256], int total) {
  if (total <= 0) return 127;
  double sum = 0.0;
  for (int i = 0; i < 256; ++i) sum += static_cast<double>(i) * hist[i];
  double sumB = 0.0;
  int wB = 0;
  double bestVar = -1.0;
  int best = 127;
  for (int t = 0; t < 256; ++t) {
    wB += hist[t];
    if (wB == 0) continue;
    const int wF = total - wB;
    if (wF == 0) break;
    sumB += static_cast<double>(t) * hist[t];
    const double mB = sumB / wB;
    const double mF = (sum - sumB) / wF;
    const double diff = mB - mF;
    const double var = static_cast<double>(wB) * static_cast<double>(wF) * diff * diff;
    if (var > bestVar) {
      bestVar = var;
      best = t;
    }
  }
  return best;
}

struct Acc {
  int label = 0;
  int area = 0;
  int peri = 0;
  qint64 sx = 0;
  qint64 sy = 0;
  double sxx = 0.0;
  double syy = 0.0;
  double sxy = 0.0;
  int x0 = 0, y0 = 0, x1 = 0, y1 = 0;
  qint64 graySum = 0;
  int grayMin = 255;
  int grayMax = 0;
};

constexpr int kDx8[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
constexpr int kDy8[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
constexpr int kDx4[4] = {-1, 1, 0, 0};
constexpr int kDy4[4] = {0, 0, -1, 1};
constexpr double kEdtInf = 1e20;

/** 一维平方距离变换（Felzenszwalb-Huttenlocher），f 为源代价，d 为结果。 */
void squaredEdt1d(const std::vector<double>& f, std::vector<double>& d, int n,
                  std::vector<int>& v, std::vector<double>& z) {
  if (n <= 0) return;
  int k = 0;
  v[0] = 0;
  z[0] = -kEdtInf;
  z[1] = kEdtInf;
  auto sep = [&](int p, int qv) -> double {
    return ((f[static_cast<size_t>(qv)] + static_cast<double>(qv) * qv) -
            (f[static_cast<size_t>(p)] + static_cast<double>(p) * p)) /
           (2.0 * static_cast<double>(qv - p));
  };
  for (int q = 1; q < n; ++q) {
    double s = sep(v[k], q);
    while (s <= z[k]) {
      --k;
      s = sep(v[k], q);
    }
    ++k;
    v[k] = q;
    z[k] = s;
    z[k + 1] = kEdtInf;
  }
  k = 0;
  for (int q = 0; q < n; ++q) {
    while (z[k + 1] < q) ++k;
    const int p = v[k];
    const double dp = static_cast<double>(q - p);
    d[static_cast<size_t>(q)] = dp * dp + f[static_cast<size_t>(p)];
  }
}

/** 二值前景到最近背景的平方欧氏距离；背景为 0。不把图外像素当作背景。 */
std::vector<double> squaredDistanceToBackground(const QImage& mask) {
  const int w = mask.width();
  const int h = mask.height();
  std::vector<double> dist(static_cast<size_t>(w * h), 0.0);
  const int m = std::max(w, h);
  std::vector<double> f(static_cast<size_t>(m), 0.0);
  std::vector<double> d(static_cast<size_t>(m), 0.0);
  std::vector<int> v(static_cast<size_t>(m), 0);
  std::vector<double> z(static_cast<size_t>(m) + 1, 0.0);
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) f[static_cast<size_t>(x)] = row[x] ? kEdtInf : 0.0;
    squaredEdt1d(f, d, w, v, z);
    for (int x = 0; x < w; ++x) dist[static_cast<size_t>(y * w + x)] = d[static_cast<size_t>(x)];
  }
  for (int x = 0; x < w; ++x) {
    for (int y = 0; y < h; ++y) f[static_cast<size_t>(y)] = dist[static_cast<size_t>(y * w + x)];
    squaredEdt1d(f, d, h, v, z);
    for (int y = 0; y < h; ++y) dist[static_cast<size_t>(y * w + x)] = d[static_cast<size_t>(y)];
  }
  return dist;
}

struct Seed {
  int x = 0;
  int y = 0;
  int idx = 0;
  double dist = 0.0;
};

/** 在距离图上找局部峰（含平台压缩与间距抑制），作为拆分种子。 */
QVector<Seed> findDistancePeaks(const std::vector<double>& dist2, const QImage& mask,
                                double minRadius, double minSeedDist) {
  QVector<Seed> out;
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  const double minR2 = minRadius * minRadius;
  std::vector<char> cand(static_cast<size_t>(n), 0);
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      if (!row[x]) continue;
      const int i = y * w + x;
      const double d2 = dist2[static_cast<size_t>(i)];
      if (d2 < minR2 || d2 >= kEdtInf * 0.5) continue;
      bool geAll = true;
      for (int k = 0; k < 8; ++k) {
        const int nx = x + kDx8[k];
        const int ny = y + kDy8[k];
        if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        if (!mask.constScanLine(ny)[nx]) continue;
        const double nd2 = dist2[static_cast<size_t>(ny * w + nx)];
        if (nd2 > d2 + 1e-9) {
          geAll = false;
          break;
        }
      }
      if (geAll) cand[static_cast<size_t>(i)] = 1;
    }
  }
  std::vector<char> seen(static_cast<size_t>(n), 0);
  std::vector<int> st;
  st.reserve(64);
  QVector<Seed> raw;
  for (int y = 0; y < h; ++y) {
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!cand[static_cast<size_t>(i0)] || seen[static_cast<size_t>(i0)]) continue;
      st.clear();
      st.push_back(i0);
      seen[static_cast<size_t>(i0)] = 1;
      int bestI = i0;
      double bestD2 = dist2[static_cast<size_t>(i0)];
      while (!st.empty()) {
        const int i = st.back();
        st.pop_back();
        if (dist2[static_cast<size_t>(i)] > bestD2) {
          bestD2 = dist2[static_cast<size_t>(i)];
          bestI = i;
        }
        const int cx = i % w;
        const int cy = i / w;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + kDx8[k];
          const int ny = cy + kDy8[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (seen[static_cast<size_t>(ni)] || !cand[static_cast<size_t>(ni)]) continue;
          seen[static_cast<size_t>(ni)] = 1;
          st.push_back(ni);
        }
      }
      Seed s;
      s.idx = bestI;
      s.x = bestI % w;
      s.y = bestI / w;
      s.dist = std::sqrt(std::max(0.0, bestD2));
      raw.push_back(s);
    }
  }
  std::sort(raw.begin(), raw.end(), [](const Seed& a, const Seed& b) { return a.dist > b.dist; });
  for (const Seed& s : raw) {
    bool keep = true;
    if (minSeedDist > 0.0) {
      for (const Seed& k : out) {
        if (std::hypot(static_cast<double>(s.x - k.x), static_cast<double>(s.y - k.y)) < minSeedDist) {
          keep = false;
          break;
        }
      }
    }
    if (keep) out.push_back(s);
  }
  return out;
}

/** 每个尚无种子的连通域补一个最大距离像素，避免孤立小目标在拆分模式下消失。 */
void addFallbackSeeds(QVector<Seed>& seeds, const std::vector<double>& dist2, const QImage& mask,
                      int hardMax) {
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<char> seen(static_cast<size_t>(n), 0);
  std::vector<char> covered(static_cast<size_t>(n), 0);
  for (const Seed& s : seeds) {
    if (s.idx >= 0 && s.idx < n) covered[static_cast<size_t>(s.idx)] = 1;
  }
  std::vector<int> st;
  st.reserve(256);
  int added = 0;
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!row[x] || seen[static_cast<size_t>(i0)]) continue;
      st.clear();
      st.push_back(i0);
      seen[static_cast<size_t>(i0)] = 1;
      int bestI = i0;
      double bestD2 = dist2[static_cast<size_t>(i0)];
      bool hasSeed = covered[static_cast<size_t>(i0)] != 0;
      while (!st.empty()) {
        const int i = st.back();
        st.pop_back();
        if (covered[static_cast<size_t>(i)]) hasSeed = true;
        if (dist2[static_cast<size_t>(i)] > bestD2) {
          bestD2 = dist2[static_cast<size_t>(i)];
          bestI = i;
        }
        const int cx = i % w;
        const int cy = i / w;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + kDx8[k];
          const int ny = cy + kDy8[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (seen[static_cast<size_t>(ni)] || !mask.constScanLine(ny)[nx]) continue;
          seen[static_cast<size_t>(ni)] = 1;
          st.push_back(ni);
        }
      }
      if (hasSeed) continue;
      Seed s;
      s.idx = bestI;
      s.x = bestI % w;
      s.y = bestI / w;
      s.dist = std::sqrt(std::max(0.0, bestD2));
      seeds.push_back(s);
      ++added;
      if (static_cast<int>(seeds.size()) >= hardMax) return;
      Q_UNUSED(added);
    }
  }
}

/** 从种子沿距离从高到低淹没，先到先得；分界落在距离鞍点附近。 */
std::vector<int> watershedFromSeeds(const QImage& mask, const std::vector<double>& dist2,
                                    const QVector<Seed>& seeds, int hardMax) {
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<int> lab(static_cast<size_t>(n), 0);
  struct Cell {
    double dist;
    int idx;
    bool operator<(const Cell& o) const { return dist < o.dist; }
  };
  std::priority_queue<Cell> pq;
  const int nSeeds = std::min(static_cast<int>(seeds.size()), hardMax);
  for (int i = 0; i < nSeeds; ++i) {
    const int idx = seeds[i].idx;
    if (idx < 0 || idx >= n) continue;
    if (lab[static_cast<size_t>(idx)] != 0) continue;
    lab[static_cast<size_t>(idx)] = i + 1;
    pq.push(Cell{dist2[static_cast<size_t>(idx)], idx});
  }
  while (!pq.empty()) {
    const Cell c = pq.top();
    pq.pop();
    const int L = lab[static_cast<size_t>(c.idx)];
    if (L <= 0) continue;
    const int cx = c.idx % w;
    const int cy = c.idx / w;
    for (int k = 0; k < 8; ++k) {
      const int nx = cx + kDx8[k];
      const int ny = cy + kDy8[k];
      if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
      if (!mask.constScanLine(ny)[nx]) continue;
      const int ni = ny * w + nx;
      if (lab[static_cast<size_t>(ni)] != 0) continue;
      lab[static_cast<size_t>(ni)] = L;
      pq.push(Cell{dist2[static_cast<size_t>(ni)], ni});
    }
  }
  return lab;
}

/** 从种子按灰度容差做 8 连通区域生长；先到先得，容差外像素不归属。 */
std::vector<int> growFromSeeds(const QImage& mask, const QImage& gray, const QVector<Seed>& seeds,
                               int growTolerance, int hardMax) {
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<int> lab(static_cast<size_t>(n), 0);
  const int nSeeds = std::min(static_cast<int>(seeds.size()), hardMax);
  std::vector<int> refGray(static_cast<size_t>(nSeeds + 1), 0);
  std::vector<int> q;
  q.reserve(256);
  for (int i = 0; i < nSeeds; ++i) {
    const int idx = seeds[i].idx;
    if (idx < 0 || idx >= n) continue;
    if (lab[static_cast<size_t>(idx)] != 0) continue;
    const int L = i + 1;
    lab[static_cast<size_t>(idx)] = L;
    const int sy = idx / w;
    const int sx = idx % w;
    refGray[static_cast<size_t>(L)] = gray.constScanLine(sy)[sx];
    q.push_back(idx);
  }
  size_t qs = 0;
  while (qs < q.size()) {
    const int i = q[qs++];
    const int L = lab[static_cast<size_t>(i)];
    const int cx = i % w;
    const int cy = i / w;
    for (int k = 0; k < 8; ++k) {
      const int nx = cx + kDx8[k];
      const int ny = cy + kDy8[k];
      if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
      if (!mask.constScanLine(ny)[nx]) continue;
      const int ni = ny * w + nx;
      if (lab[static_cast<size_t>(ni)] != 0) continue;
      const int g = gray.constScanLine(ny)[nx];
      if (std::abs(g - refGray[static_cast<size_t>(L)]) > growTolerance) continue;
      lab[static_cast<size_t>(ni)] = L;
      q.push_back(ni);
    }
  }
  return lab;
}

/** 普通 8 连通标记，得到与分水岭相同格式的标签图。 */
std::vector<int> labelConnected(const QImage& mask, int hardMax) {
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<int> lab(static_cast<size_t>(n), 0);
  std::vector<int> st;
  st.reserve(1024);
  int next = 1;
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!row[x] || lab[static_cast<size_t>(i0)] != 0) continue;
      if (next > hardMax) return lab;
      const int L = next++;
      st.clear();
      st.push_back(i0);
      lab[static_cast<size_t>(i0)] = L;
      while (!st.empty()) {
        const int i = st.back();
        st.pop_back();
        const int cx = i % w;
        const int cy = i / w;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + kDx8[k];
          const int ny = cy + kDy8[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (lab[static_cast<size_t>(ni)] != 0 || !mask.constScanLine(ny)[nx]) continue;
          lab[static_cast<size_t>(ni)] = L;
          st.push_back(ni);
        }
      }
    }
  }
  return lab;
}

/** 按标签图累计矩与灰度；周长按 4 邻域是否仍属同一标签计算。 */
QVector<Acc> accumulateFromLabels(const std::vector<int>& lab, int w, int h, const QImage& gray,
                                  int hardMax) {
  int maxL = 0;
  for (int v : lab)
    if (v > maxL) maxL = v;
  if (maxL <= 0) return {};
  if (maxL > hardMax) maxL = hardMax;
  QVector<Acc> acc(maxL);
  std::vector<char> init(static_cast<size_t>(maxL), 0);
  for (int y = 0; y < h; ++y) {
    const uchar* grow = gray.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int L = lab[static_cast<size_t>(y * w + x)];
      if (L <= 0 || L > maxL) continue;
      Acc& a = acc[L - 1];
      if (!init[static_cast<size_t>(L - 1)]) {
        a.label = L;
        a.x0 = a.x1 = x;
        a.y0 = a.y1 = y;
        a.grayMin = 255;
        a.grayMax = 0;
        init[static_cast<size_t>(L - 1)] = 1;
      }
      a.area += 1;
      a.sx += x;
      a.sy += y;
      if (x < a.x0) a.x0 = x;
      if (x > a.x1) a.x1 = x;
      if (y < a.y0) a.y0 = y;
      if (y > a.y1) a.y1 = y;
      const int g = grow[x];
      a.graySum += g;
      if (g < a.grayMin) a.grayMin = g;
      if (g > a.grayMax) a.grayMax = g;
      bool border = false;
      for (int k = 0; k < 4; ++k) {
        const int nx = x + kDx4[k];
        const int ny = y + kDy4[k];
        if (nx < 0 || ny < 0 || nx >= w || ny >= h ||
            lab[static_cast<size_t>(ny * w + nx)] != L) {
          border = true;
          break;
        }
      }
      if (border) ++a.peri;
    }
  }
  std::vector<double> cx(static_cast<size_t>(maxL), 0.0);
  std::vector<double> cy(static_cast<size_t>(maxL), 0.0);
  for (int i = 0; i < maxL; ++i) {
    if (acc[i].area <= 0) continue;
    const double inv = 1.0 / static_cast<double>(acc[i].area);
    cx[static_cast<size_t>(i)] = static_cast<double>(acc[i].sx) * inv;
    cy[static_cast<size_t>(i)] = static_cast<double>(acc[i].sy) * inv;
  }
  for (int y = 0; y < h; ++y) {
    for (int x = 0; x < w; ++x) {
      const int L = lab[static_cast<size_t>(y * w + x)];
      if (L <= 0 || L > maxL) continue;
      Acc& a = acc[L - 1];
      if (a.area <= 0) continue;
      const double dxv = static_cast<double>(x) - cx[static_cast<size_t>(L - 1)];
      const double dyv = static_cast<double>(y) - cy[static_cast<size_t>(L - 1)];
      a.sxx += dxv * dxv;
      a.syy += dyv * dyv;
      a.sxy += dxv * dyv;
    }
  }
  QVector<Acc> out;
  out.reserve(maxL);
  for (int i = 0; i < maxL; ++i)
    if (init[static_cast<size_t>(i)] && acc[i].area > 0) out.push_back(acc[i]);
  return out;
}

/** 把累计矩转换成对外特征；面积为 0 的退化域返回空。 */
RegionBlob finishBlob(const Acc& a, int label) {
  RegionBlob b;
  b.label = label;
  b.areaPixels = a.area;
  b.perimeterPx = qMax(1, a.peri);
  if (a.area <= 0) return b;
  const double inv = 1.0 / static_cast<double>(a.area);
  b.centroid = QPointF(static_cast<double>(a.sx) * inv, static_cast<double>(a.sy) * inv);
  b.bbox = QRect(QPoint(a.x0, a.y0), QPoint(a.x1, a.y1));
  b.grayMean = static_cast<double>(a.graySum) * inv;
  b.grayMin = a.grayMin;
  b.grayMax = a.grayMax;
  b.circularity = (4.0 * M_PI * static_cast<double>(a.area)) /
                  (static_cast<double>(b.perimeterPx) * b.perimeterPx);
  if (b.circularity > 1.0) b.circularity = 1.0;
  // 协方差特征值 λ = (μxx+μyy)/2 ± sqrt(((μxx-μyy)/2)² + μxy²)，μ=二阶矩/N。
  const double mu20 = a.sxx * inv;
  const double mu02 = a.syy * inv;
  const double mu11 = a.sxy * inv;
  const double half = 0.5 * (mu20 + mu02);
  const double gap = std::sqrt(std::max(0.0, 0.25 * (mu20 - mu02) * (mu20 - mu02) + mu11 * mu11));
  const double l1 = std::max(0.0, half + gap);
  const double l2 = std::max(0.0, half - gap);
  b.majorAxisPx = 2.0 * std::sqrt(l1);
  b.minorAxisPx = 2.0 * std::sqrt(l2);
  if (b.majorAxisPx > 1e-9)
    b.compactness = static_cast<double>(a.area) / (M_PI * (b.majorAxisPx * 0.5) * (b.majorAxisPx * 0.5));
  if (b.majorAxisPx > 1e-9 && b.minorAxisPx <= b.majorAxisPx)
    b.eccentricity = std::sqrt(std::max(0.0, 1.0 - (b.minorAxisPx / b.majorAxisPx) *
                                                       (b.minorAxisPx / b.majorAxisPx)));
  b.orientationDeg = 0.5 * std::atan2(2.0 * mu11, mu20 - mu02) * 180.0 / M_PI;
  return b;
}

/** 在圆盘内填充灰度值，供自测构造已知面积目标。 */
void fillDisk(QImage& img, int cx, int cy, int radius, int gray) {
  const int r2 = radius * radius;
  for (int y = cy - radius; y <= cy + radius; ++y) {
    if (y < 0 || y >= img.height()) continue;
    uchar* row = img.scanLine(y);
    for (int x = cx - radius; x <= cx + radius; ++x) {
      if (x < 0 || x >= img.width()) continue;
      const int dx = x - cx;
      const int dy = y - cy;
      if (dx * dx + dy * dy <= r2) row[x] = static_cast<uchar>(gray);
    }
  }
}

/** 填充轴对齐矩形。 */
void fillRect(QImage& img, const QRect& r, int gray) {
  const QRect clip = r.intersected(img.rect());
  for (int y = clip.top(); y <= clip.bottom(); ++y) {
    uchar* row = img.scanLine(y);
    for (int x = clip.left(); x <= clip.right(); ++x) row[x] = static_cast<uchar>(gray);
  }
}

}  // namespace

RegionResult runRegionAnalyze(const QImage& src, const QVariantMap& params) {
  RegionResult r;
  if (src.isNull() || src.width() <= 0 || src.height() <= 0) {
    r.error = QStringLiteral("区域分析需要非空输入图像");
    return r;
  }
  const QImage gray = toGray8(src);
  const int w = gray.width();
  const int h = gray.height();
  int roiX = params.value(QStringLiteral("roiX"), 0).toInt();
  int roiY = params.value(QStringLiteral("roiY"), 0).toInt();
  int roiW = params.value(QStringLiteral("roiW"), 0).toInt();
  int roiH = params.value(QStringLiteral("roiH"), 0).toInt();
  if (roiW <= 0 || roiH <= 0) {
    roiX = 0;
    roiY = 0;
    roiW = w;
    roiH = h;
  }
  const QRect roi = QRect(roiX, roiY, roiW, roiH).intersected(QRect(0, 0, w, h));
  if (roi.isEmpty()) {
    r.error = QStringLiteral("区域分析 ROI 与图像无交集");
    return r;
  }

  QString method = params.value(QStringLiteral("method"), QStringLiteral("fixed")).toString().trimmed().toLower();
  if (method == QLatin1String("auto") || method == QLatin1String("automatic")) method = QStringLiteral("otsu");
  if (method == QLatin1String("ws") || method == QLatin1String("watersheds")) method = QStringLiteral("watershed");
  if (method == QLatin1String("grow") || method == QLatin1String("regiongrow") ||
      method == QLatin1String("region_growing") || method == QLatin1String("regiongrowing"))
    method = QStringLiteral("growing");
  if (method != QLatin1String("otsu") && method != QLatin1String("watershed") &&
      method != QLatin1String("growing"))
    method = QStringLiteral("fixed");
  r.method = method;
  const bool invert = params.value(QStringLiteral("invert"), false).toBool();
  const bool splitMode = (method == QLatin1String("watershed") || method == QLatin1String("growing"));

  int hist[256] = {};
  int histN = 0;
  for (int y = roi.top(); y <= roi.bottom(); ++y) {
    const uchar* row = gray.constScanLine(y);
    for (int x = roi.left(); x <= roi.right(); ++x) {
      ++hist[row[x]];
      ++histN;
    }
  }
  int thr = params.value(QStringLiteral("threshold"), 127).toInt();
  // 分水岭/区域生长默认用固定阈值二值化；若显式 binarize=otsu 则先做 Otsu。
  const QString binarize =
      params.value(QStringLiteral("binarize"),
                   method == QLatin1String("otsu") ? QStringLiteral("otsu") : QStringLiteral("fixed"))
          .toString()
          .trimmed()
          .toLower();
  if (method == QLatin1String("otsu") || binarize == QLatin1String("otsu") ||
      binarize == QLatin1String("auto") || binarize == QLatin1String("automatic")) {
    // Otsu 把 0..t 划为暗类，前景比较使用 >= t+1，避免阈值落在背景灰度上把整图涂满。
    const int tDark = otsuThreshold(hist, histN);
    thr = qBound(0, tDark + 1, 255);
  }
  thr = qBound(0, thr, 255);
  r.thresholdUsed = thr;

  QImage mask(w, h, QImage::Format_Grayscale8);
  mask.fill(0);
  for (int y = roi.top(); y <= roi.bottom(); ++y) {
    const uchar* row = gray.constScanLine(y);
    uchar* out = mask.scanLine(y);
    for (int x = roi.left(); x <= roi.right(); ++x) {
      const bool on = invert ? (row[x] < thr) : (row[x] >= thr);
      out[x] = on ? 255 : 0;
    }
  }

  const int minArea = qMax(1, params.value(QStringLiteral("minArea"), 20).toInt());
  int maxArea = params.value(QStringLiteral("maxArea"), 0).toInt();
  if (maxArea <= 0) maxArea = w * h;
  const double minCirc = params.value(QStringLiteral("minCircularity"), 0.0).toDouble();
  const double maxCirc = params.value(QStringLiteral("maxCircularity"), 1.0).toDouble();
  const double minGray = params.value(QStringLiteral("minGrayMean"), 0.0).toDouble();
  const double maxGray = params.value(QStringLiteral("maxGrayMean"), 255.0).toDouble();
  const int maxCount = qBound(1, params.value(QStringLiteral("maxCount"), 200).toInt(), 2000);
  const double minSeedRadius = std::max(0.0, params.value(QStringLiteral("minSeedRadius"), 3.0).toDouble());
  const double minSeedDist = std::max(0.0, params.value(QStringLiteral("minSeedDist"), 8.0).toDouble());
  const int growTolerance = qBound(0, params.value(QStringLiteral("growTolerance"), 25).toInt(), 255);
  const int hardMax = 4000;

  std::vector<int> labels;
  if (splitMode) {
    const std::vector<double> dist2 = squaredDistanceToBackground(mask);
    QVector<Seed> seeds = findDistancePeaks(dist2, mask, minSeedRadius, minSeedDist);
    addFallbackSeeds(seeds, dist2, mask, hardMax);
    r.seedCount = seeds.size();
    if (method == QLatin1String("growing"))
      labels = growFromSeeds(mask, gray, seeds, growTolerance, hardMax);
    else
      labels = watershedFromSeeds(mask, dist2, seeds, hardMax);
  } else {
    labels = labelConnected(mask, hardMax);
    r.seedCount = 0;
  }

  const QVector<Acc> raw = accumulateFromLabels(labels, w, h, gray, hardMax);
  r.rawCount = raw.size();
  QVector<RegionBlob> kept;
  for (const Acc& a : raw) {
    if (a.area < minArea || a.area > maxArea) continue;
    RegionBlob b = finishBlob(a, a.label);
    if (b.circularity < minCirc || b.circularity > maxCirc) continue;
    if (b.grayMean < minGray || b.grayMean > maxGray) continue;
    kept.push_back(b);
  }
  std::sort(kept.begin(), kept.end(), [](const RegionBlob& a, const RegionBlob& b) {
    return a.areaPixels > b.areaPixels;
  });
  if (kept.size() > maxCount) kept.resize(maxCount);

  // 掩膜按保留标签直接涂色，避免粘连拆分后又被连通域漫水合并。
  QImage filtered(w, h, QImage::Format_Grayscale8);
  filtered.fill(0);
  if (!kept.isEmpty()) {
    int maxL = 0;
    for (int v : labels)
      if (v > maxL) maxL = v;
    std::vector<char> keep(static_cast<size_t>(std::max(0, maxL) + 1), 0);
    for (const RegionBlob& b : kept) {
      if (b.label > 0 && b.label <= maxL) keep[static_cast<size_t>(b.label)] = 1;
    }
    for (int y = 0; y < h; ++y) {
      uchar* row = filtered.scanLine(y);
      for (int x = 0; x < w; ++x) {
        const int L = labels[static_cast<size_t>(y * w + x)];
        if (L > 0 && L <= maxL && keep[static_cast<size_t>(L)]) row[x] = 255;
      }
    }
  }
  for (int i = 0; i < kept.size(); ++i) kept[i].label = i + 1;
  r.items = kept;
  r.count = kept.size();
  r.mask = filtered;
  r.ok = true;
  if (splitMode) {
    r.note = QStringLiteral("区域 %1 个（%2 阈值 %3，种子 %4，过滤前 %5）")
                 .arg(r.count)
                 .arg(r.method)
                 .arg(r.thresholdUsed)
                 .arg(r.seedCount)
                 .arg(r.rawCount);
  } else {
    r.note = QStringLiteral("区域 %1 个（阈值 %2/%3，过滤前 %4）")
                 .arg(r.count)
                 .arg(r.method, QString::number(r.thresholdUsed))
                 .arg(r.rawCount);
  }
  return r;
}

QStringList regionSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok) fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                        : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  QImage scene(320, 240, QImage::Format_Grayscale8);
  scene.fill(20);
  fillDisk(scene, 80, 80, 20, 220);    // 亮大圆
  fillDisk(scene, 200, 70, 10, 220);   // 亮小圆
  fillDisk(scene, 80, 180, 20, 120);   // 较暗大圆，用于灰度均值过滤
  fillRect(scene, QRect(180, 150, 80, 16), 220);  // 细长矩形

  const QVariantMap base{{QStringLiteral("method"), QStringLiteral("fixed")},
                         {QStringLiteral("threshold"), 80},
                         {QStringLiteral("minArea"), 10},
                         {QStringLiteral("maxCount"), 20}};
  const RegionResult all = runRegionAnalyze(scene, base);
  check("run-ok", all.ok, all.error);
  check("count-4", all.count == 4, QStringLiteral("count=%1").arg(all.count));

  auto findNear = [&](const RegionResult& res, double x, double y) -> const RegionBlob* {
    const RegionBlob* hit = nullptr;
    double best = 1e9;
    for (const RegionBlob& b : res.items) {
      const double d = std::hypot(b.centroid.x() - x, b.centroid.y() - y);
      if (d < best) {
        best = d;
        hit = &b;
      }
    }
    return (hit && best <= 6.0) ? hit : nullptr;
  };
  const RegionBlob* big = findNear(all, 80, 80);
  check("big-found", big != nullptr);
  if (big) {
    // 离散圆面积在 πr² 附近，允许光栅误差。
    const double expect = M_PI * 20 * 20;
    check("big-area", std::fabs(big->areaPixels - expect) <= 40.0,
          QStringLiteral("area=%1").arg(big->areaPixels));
    check("big-circ", big->circularity >= 0.65,
          QStringLiteral("circularity=%1").arg(big->circularity));
    check("big-gray", big->grayMean >= 200.0, QStringLiteral("gray=%1").arg(big->grayMean));
  }
  const RegionBlob* bar = findNear(all, 220, 158);
  check("bar-found", bar != nullptr);
  if (bar) {
    check("bar-circ-lower", bar->circularity <= 0.55,
          QStringLiteral("circularity=%1").arg(bar->circularity));
    check("bar-orient", std::fabs(bar->orientationDeg) <= 15.0 ||
                            std::fabs(std::fabs(bar->orientationDeg) - 180.0) <= 15.0,
          QStringLiteral("orient=%1").arg(bar->orientationDeg));
  }

  QVariantMap byArea = base;
  byArea.insert(QStringLiteral("minArea"), 800);
  const RegionResult areaF = runRegionAnalyze(scene, byArea);
  check("filter-area", areaF.count == 3, QStringLiteral("count=%1").arg(areaF.count));

  QVariantMap byCirc = base;
  byCirc.insert(QStringLiteral("minCircularity"), 0.65);
  const RegionResult circF = runRegionAnalyze(scene, byCirc);
  check("filter-circ", circF.count == 3, QStringLiteral("count=%1").arg(circF.count));
  if (circF.count == 3) {
    for (const RegionBlob& b : circF.items)
      check("filter-circ-only-round", b.circularity >= 0.65,
            QStringLiteral("c=%1").arg(b.circularity));
  }

  QVariantMap byGray = base;
  byGray.insert(QStringLiteral("maxGrayMean"), 160);
  const RegionResult grayF = runRegionAnalyze(scene, byGray);
  check("filter-gray", grayF.count == 1, QStringLiteral("count=%1").arg(grayF.count));
  if (grayF.count == 1)
    check("filter-gray-dark", grayF.items[0].grayMean <= 160.0,
          QStringLiteral("gray=%1").arg(grayF.items[0].grayMean));

  const RegionResult otsu = runRegionAnalyze(
      scene, {{QStringLiteral("method"), QStringLiteral("otsu")},
              {QStringLiteral("minArea"), 10}});
  check("otsu-ok", otsu.ok && otsu.method == QLatin1String("otsu"), otsu.error);
  check("otsu-count", otsu.count == 4, QStringLiteral("count=%1 thr=%2").arg(otsu.count).arg(otsu.thresholdUsed));

  QVariantMap roiP = base;
  roiP.insert(QStringLiteral("roiX"), 40);
  roiP.insert(QStringLiteral("roiY"), 40);
  roiP.insert(QStringLiteral("roiW"), 80);
  roiP.insert(QStringLiteral("roiH"), 80);
  const RegionResult roi = runRegionAnalyze(scene, roiP);
  check("roi-one", roi.count == 1, QStringLiteral("count=%1").arg(roi.count));
  if (roi.count == 1)
    check("roi-center", std::hypot(roi.items[0].centroid.x() - 80, roi.items[0].centroid.y() - 80) <= 6.0,
          QStringLiteral("c=%1,%2").arg(roi.items[0].centroid.x()).arg(roi.items[0].centroid.y()));

  QImage light(200, 160, QImage::Format_Grayscale8);
  light.fill(230);
  fillDisk(light, 100, 80, 18, 30);
  const RegionResult inv = runRegionAnalyze(
      light, {{QStringLiteral("method"), QStringLiteral("fixed")},
              {QStringLiteral("threshold"), 80},
              {QStringLiteral("invert"), true},
              {QStringLiteral("minArea"), 10}});
  check("invert-one", inv.ok && inv.count == 1, QStringLiteral("count=%1").arg(inv.count));

  const RegionResult empty = runRegionAnalyze(QImage(), base);
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  QImage blank(80, 80, QImage::Format_Grayscale8);
  blank.fill(10);
  const RegionResult none = runRegionAnalyze(blank, base);
  check("blank-zero", none.ok && none.count == 0, QStringLiteral("count=%1").arg(none.count));

  if (all.ok && all.count >= 1) {
    int maskPx = 0;
    for (int y = 0; y < all.mask.height(); ++y) {
      const uchar* row = all.mask.constScanLine(y);
      for (int x = 0; x < all.mask.width(); ++x)
        if (row[x]) ++maskPx;
    }
    int sum = 0;
    for (const RegionBlob& b : all.items) sum += b.areaPixels;
    check("mask-area", maskPx == sum, QStringLiteral("mask=%1 sum=%2").arg(maskPx).arg(sum));
  }

  // 两个半径 20、圆心相距 36 的圆盘轻度重叠：普通连通域应合并，分水岭应拆开。
  QImage touch(320, 200, QImage::Format_Grayscale8);
  touch.fill(20);
  fillDisk(touch, 100, 100, 20, 220);
  fillDisk(touch, 136, 100, 20, 220);
  const RegionResult merged = runRegionAnalyze(
      touch, {{QStringLiteral("method"), QStringLiteral("fixed")},
              {QStringLiteral("threshold"), 80},
              {QStringLiteral("minArea"), 50}});
  check("touch-cc-merge", merged.ok && merged.count == 1,
        QStringLiteral("count=%1").arg(merged.count));

  const RegionResult split = runRegionAnalyze(
      touch, {{QStringLiteral("method"), QStringLiteral("watershed")},
              {QStringLiteral("threshold"), 80},
              {QStringLiteral("minArea"), 50},
              {QStringLiteral("minSeedRadius"), 3},
              {QStringLiteral("minSeedDist"), 8}});
  check("watershed-ok", split.ok && split.method == QLatin1String("watershed"), split.error);
  check("watershed-split", split.count == 2,
        QStringLiteral("count=%1 seeds=%2").arg(split.count).arg(split.seedCount));
  if (split.count == 2) {
    auto near = [&](double x, double y) {
      double best = 1e9;
      const RegionBlob* hit = nullptr;
      for (const RegionBlob& b : split.items) {
        const double d = std::hypot(b.centroid.x() - x, b.centroid.y() - y);
        if (d < best) {
          best = d;
          hit = &b;
        }
      }
      return (hit && best <= 10.0) ? hit : nullptr;
    };
    const RegionBlob* a = near(100, 100);
    const RegionBlob* b = near(136, 100);
    check("watershed-centers", a && b && a != b,
          QStringLiteral("a=%1 b=%2")
              .arg(a ? QString::number(a->centroid.x()) : QStringLiteral("miss"),
                   b ? QString::number(b->centroid.x()) : QStringLiteral("miss")));
    if (a)
      check("watershed-area-a", a->areaPixels >= 800, QStringLiteral("area=%1").arg(a->areaPixels));
    if (b)
      check("watershed-area-b", b->areaPixels >= 800, QStringLiteral("area=%1").arg(b->areaPixels));
    int maskPx = 0;
    for (int y = 0; y < split.mask.height(); ++y) {
      const uchar* row = split.mask.constScanLine(y);
      for (int x = 0; x < split.mask.width(); ++x)
        if (row[x]) ++maskPx;
    }
    int sum = 0;
    for (const RegionBlob& it : split.items) sum += it.areaPixels;
    check("watershed-mask-area", maskPx == sum, QStringLiteral("mask=%1 sum=%2").arg(maskPx).arg(sum));
  }

  // 分离目标在分水岭模式下仍应保持 4 个，证明拆分不会把已分开的目标捏在一起。
  const RegionResult wsKeep = runRegionAnalyze(
      scene, {{QStringLiteral("method"), QStringLiteral("watershed")},
              {QStringLiteral("threshold"), 80},
              {QStringLiteral("minArea"), 10}});
  check("watershed-keep-separate", wsKeep.ok && wsKeep.count == 4,
        QStringLiteral("count=%1").arg(wsKeep.count));

  // 不同灰度的粘连圆：普通连通域合并，区域生长按灰度容差拆开。
  QImage touchGray(320, 200, QImage::Format_Grayscale8);
  touchGray.fill(20);
  fillDisk(touchGray, 100, 100, 20, 220);
  fillDisk(touchGray, 136, 100, 20, 130);
  const RegionResult growMerged = runRegionAnalyze(
      touchGray, {{QStringLiteral("method"), QStringLiteral("fixed")},
                  {QStringLiteral("threshold"), 80},
                  {QStringLiteral("minArea"), 50}});
  check("growing-cc-merge", growMerged.ok && growMerged.count == 1,
        QStringLiteral("count=%1").arg(growMerged.count));
  const RegionResult grown = runRegionAnalyze(
      touchGray, {{QStringLiteral("method"), QStringLiteral("growing")},
                  {QStringLiteral("threshold"), 80},
                  {QStringLiteral("minArea"), 50},
                  {QStringLiteral("growTolerance"), 25},
                  {QStringLiteral("minSeedRadius"), 3},
                  {QStringLiteral("minSeedDist"), 8}});
  check("growing-ok", grown.ok && grown.method == QLatin1String("growing"), grown.error);
  check("growing-split", grown.count == 2,
        QStringLiteral("count=%1 seeds=%2").arg(grown.count).arg(grown.seedCount));
  if (grown.count == 2) {
    double g0 = grown.items[0].grayMean;
    double g1 = grown.items[1].grayMean;
    if (g0 > g1) std::swap(g0, g1);
    check("growing-gray-sep", g0 <= 160.0 && g1 >= 180.0,
          QStringLiteral("g0=%1 g1=%2").arg(g0).arg(g1));
  }

  return fails;
}

}  // namespace sieans_qt
