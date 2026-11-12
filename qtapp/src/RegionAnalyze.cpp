#include "RegionAnalyze.hpp"

#include <QColor>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
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

/** 8 连通标记并累计矩/灰度；先按 minArea 丢掉碎点以控制后续计算量。 */
QVector<Acc> labelComponents(const QImage& mask, const QImage& gray, int minArea,
                             int hardMax) {
  QVector<Acc> out;
  if (mask.isNull() || gray.isNull()) return out;
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<uchar> seen(static_cast<size_t>(n), 0);
  const int dx[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
  const int dy[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
  std::vector<int> stack;
  stack.reserve(1024);
  auto fg = [&](int x, int y) -> bool { return mask.constScanLine(y)[x] != 0; };
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!row[x] || seen[static_cast<size_t>(i0)]) continue;
      stack.clear();
      stack.push_back(i0);
      seen[static_cast<size_t>(i0)] = 1;
      Acc a;
      a.x0 = a.x1 = x;
      a.y0 = a.y1 = y;
      std::vector<int> pixels;
      pixels.reserve(64);
      while (!stack.empty()) {
        const int i = stack.back();
        stack.pop_back();
        pixels.push_back(i);
        const int cx = i % w;
        const int cy = i / w;
        if (cx < a.x0) a.x0 = cx;
        if (cx > a.x1) a.x1 = cx;
        if (cy < a.y0) a.y0 = cy;
        if (cy > a.y1) a.y1 = cy;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + dx[k];
          const int ny = cy + dy[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (seen[static_cast<size_t>(ni)] || !fg(nx, ny)) continue;
          seen[static_cast<size_t>(ni)] = 1;
          stack.push_back(ni);
        }
      }
      a.area = static_cast<int>(pixels.size());
      if (a.area < minArea) continue;
      for (int i : pixels) {
        const int cx = i % w;
        const int cy = i / w;
        a.sx += cx;
        a.sy += cy;
        const int g = gray.constScanLine(cy)[cx];
        a.graySum += g;
        if (g < a.grayMin) a.grayMin = g;
        if (g > a.grayMax) a.grayMax = g;
        // 4 邻域有背景或越界则计为边界像素，周长用于圆形度，不是亚像素轮廓长。
        bool border = false;
        static const int bdx[4] = {-1, 1, 0, 0};
        static const int bdy[4] = {0, 0, -1, 1};
        for (int k = 0; k < 4; ++k) {
          const int nx = cx + bdx[k];
          const int ny = cy + bdy[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h || !fg(nx, ny)) {
            border = true;
            break;
          }
        }
        if (border) ++a.peri;
      }
      const double inv = 1.0 / static_cast<double>(a.area);
      const double cx = static_cast<double>(a.sx) * inv;
      const double cy = static_cast<double>(a.sy) * inv;
      for (int i : pixels) {
        const double dxv = (i % w) - cx;
        const double dyv = (i / w) - cy;
        a.sxx += dxv * dxv;
        a.syy += dyv * dyv;
        a.sxy += dxv * dyv;
      }
      out.push_back(a);
      if (out.size() >= hardMax) return out;
    }
  }
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
  if (method != QLatin1String("otsu")) method = QStringLiteral("fixed");
  r.method = method;
  const bool invert = params.value(QStringLiteral("invert"), false).toBool();

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
  if (method == QLatin1String("otsu")) {
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

  const QVector<Acc> raw = labelComponents(mask, gray, 1, 4000);
  r.rawCount = raw.size();
  QVector<RegionBlob> kept;
  int label = 1;
  for (const Acc& a : raw) {
    if (a.area < minArea || a.area > maxArea) continue;
    RegionBlob b = finishBlob(a, label);
    if (b.circularity < minCirc || b.circularity > maxCirc) continue;
    if (b.grayMean < minGray || b.grayMean > maxGray) continue;
    kept.push_back(b);
    ++label;
  }
  std::sort(kept.begin(), kept.end(), [](const RegionBlob& a, const RegionBlob& b) {
    return a.areaPixels > b.areaPixels;
  });
  if (kept.size() > maxCount) kept.resize(maxCount);
  for (int i = 0; i < kept.size(); ++i) kept[i].label = i + 1;
  r.items = kept;
  r.count = kept.size();

  // 掩膜只保留过滤后的目标，便于下游几何/测量直接使用。
  QImage filtered(w, h, QImage::Format_Grayscale8);
  filtered.fill(0);
  if (!kept.isEmpty()) {
    // 用质心（或包围盒内前景）在原始二值图上重新漫水，只保留过滤后的目标。
    const int dx[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
    const int dy[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
    std::vector<uchar> seen(static_cast<size_t>(w * h), 0);
    for (const RegionBlob& b : kept) {
      const int sx = qBound(0, qRound(b.centroid.x()), w - 1);
      const int sy = qBound(0, qRound(b.centroid.y()), h - 1);
      if (!mask.constScanLine(sy)[sx]) {
        // 质心可能落在离散空洞，改用包围盒内任意前景像素。
        bool seeded = false;
        const QRect box = b.bbox.intersected(QRect(0, 0, w, h));
        for (int y = box.top(); !seeded && y <= box.bottom(); ++y) {
          const uchar* row = mask.constScanLine(y);
          for (int x = box.left(); x <= box.right(); ++x) {
            if (row[x] && !seen[static_cast<size_t>(y * w + x)]) {
              std::vector<int> st{y * w + x};
              seen[static_cast<size_t>(y * w + x)] = 1;
              while (!st.empty()) {
                const int i = st.back();
                st.pop_back();
                const int cx = i % w;
                const int cy = i / w;
                filtered.scanLine(cy)[cx] = 255;
                for (int k = 0; k < 8; ++k) {
                  const int nx = cx + dx[k];
                  const int ny = cy + dy[k];
                  if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
                  const int ni = ny * w + nx;
                  if (seen[static_cast<size_t>(ni)] || !mask.constScanLine(ny)[nx]) continue;
                  seen[static_cast<size_t>(ni)] = 1;
                  st.push_back(ni);
                }
              }
              seeded = true;
              break;
            }
          }
        }
        continue;
      }
      std::vector<int> st{sy * w + sx};
      seen[static_cast<size_t>(sy * w + sx)] = 1;
      while (!st.empty()) {
        const int i = st.back();
        st.pop_back();
        const int cx = i % w;
        const int cy = i / w;
        filtered.scanLine(cy)[cx] = 255;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + dx[k];
          const int ny = cy + dy[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (seen[static_cast<size_t>(ni)] || !mask.constScanLine(ny)[nx]) continue;
          seen[static_cast<size_t>(ni)] = 1;
          st.push_back(ni);
        }
      }
    }
  }
  r.mask = filtered;
  r.ok = true;
  r.note = QStringLiteral("区域 %1 个（阈值 %2/%3，过滤前 %4）")
               .arg(r.count)
               .arg(r.method, QString::number(r.thresholdUsed))
               .arg(r.rawCount);
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
  return fails;
}

}  // namespace sieans_qt
