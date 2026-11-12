#include "PreprocessOp.hpp"

#include <QColor>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <vector>

namespace sieans_qt {
namespace {

constexpr double kPi = 3.14159265358979323846;

/** 空图返回空，否则转为 RGB888。 */
QImage toRgb888(const QImage& src) {
  if (src.isNull()) return {};
  if (src.format() == QImage::Format_RGB888) return src;
  return src.convertToFormat(QImage::Format_RGB888);
}

/** 转为 8 位灰度。 */
QImage toGray8(const QImage& src) {
  if (src.isNull()) return {};
  if (src.format() == QImage::Format_Grayscale8) return src;
  return src.convertToFormat(QImage::Format_Grayscale8);
}

/** 灰度图扩成 RGB888，便于下游与历史预处理输出一致。 */
QImage grayToRgb(const QImage& g) {
  if (g.isNull()) return {};
  return g.convertToFormat(QImage::Format_RGB888);
}

/** 把 kernel 夹到 1–51，并强制为奇数（偶数 +1）。 */
int normalizeKernel(int k) {
  k = qBound(1, k, 51);
  if ((k % 2) == 0) ++k;
  if (k > 51) k = 51;
  return k;
}

/** 归一化方法名，兼容目录 method 与旧参数 mode。空串表示未提供。 */
QString normalizeMethod(QString raw) {
  raw = raw.trimmed().toLower();
  if (raw == QLatin1String("gray") || raw == QLatin1String("mono") ||
      raw == QLatin1String("grayscale"))
    return QStringLiteral("grayscale");
  if (raw == QLatin1String("gaussian") || raw == QLatin1String("gauss"))
    return QStringLiteral("blur");
  if (raw == QLatin1String("edge") || raw == QLatin1String("edges"))
    return QStringLiteral("canny");
  if (raw == QLatin1String("binary")) return QStringLiteral("threshold");
  return raw;
}

/** 复制边界，取出灰度像素。 */
int grayAt(const QImage& g, int x, int y) {
  const int w = g.width();
  const int h = g.height();
  if (w <= 0 || h <= 0) return 0;
  x = qBound(0, x, w - 1);
  y = qBound(0, y, h - 1);
  return g.constScanLine(y)[x];
}

/**
 * 可分离高斯模糊。k=1 时原样返回。
 * sigma 采用常见公式 0.3*((k-1)/2-1)+0.8；k=3 时退到 0.8。
 */
QImage gaussianBlur(const QImage& gray, int k) {
  k = normalizeKernel(k);
  QImage src = toGray8(gray);
  if (src.isNull() || k <= 1) return src;

  const int w = src.width();
  const int h = src.height();
  const int r = k / 2;
  const double sigma = (k == 3) ? 0.8 : (0.3 * ((k - 1) * 0.5 - 1.0) + 0.8);
  std::vector<double> ker(static_cast<size_t>(k), 0.0);
  double sum = 0.0;
  for (int i = 0; i < k; ++i) {
    const double x = static_cast<double>(i - r);
    ker[static_cast<size_t>(i)] = std::exp(-(x * x) / (2.0 * sigma * sigma));
    sum += ker[static_cast<size_t>(i)];
  }
  if (sum <= 0.0) return src;
  for (double& v : ker) v /= sum;

  std::vector<float> tmp(static_cast<size_t>(w * h), 0.0f);
  for (int y = 0; y < h; ++y) {
    for (int x = 0; x < w; ++x) {
      double acc = 0.0;
      for (int i = -r; i <= r; ++i) acc += ker[static_cast<size_t>(i + r)] * grayAt(src, x + i, y);
      tmp[static_cast<size_t>(y * w + x)] = static_cast<float>(acc);
    }
  }

  QImage out(w, h, QImage::Format_Grayscale8);
  for (int y = 0; y < h; ++y) {
    uchar* row = out.scanLine(y);
    for (int x = 0; x < w; ++x) {
      double acc = 0.0;
      for (int i = -r; i <= r; ++i) {
        const int yy = qBound(0, y + i, h - 1);
        acc += ker[static_cast<size_t>(i + r)] * tmp[static_cast<size_t>(yy * w + x)];
      }
      row[x] = static_cast<uchar>(qBound(0, qRound(acc), 255));
    }
  }
  return out;
}

/** 方形结构元灰度腐蚀（最小）或膨胀（最大）；可分离，复制边界。 */
QImage morphMinMax(const QImage& gray, int k, bool dilate) {
  k = normalizeKernel(k);
  QImage src = toGray8(gray);
  if (src.isNull()) return src;
  if (k <= 1) return src;

  const int w = src.width();
  const int h = src.height();
  const int r = k / 2;
  std::vector<int> tmp(static_cast<size_t>(w * h), 0);

  for (int y = 0; y < h; ++y) {
    const uchar* row = src.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      int v = dilate ? 0 : 255;
      for (int i = -r; i <= r; ++i) {
        const int xx = qBound(0, x + i, w - 1);
        const int p = row[xx];
        v = dilate ? std::max(v, p) : std::min(v, p);
      }
      tmp[static_cast<size_t>(y * w + x)] = v;
    }
  }

  QImage out(w, h, QImage::Format_Grayscale8);
  for (int y = 0; y < h; ++y) {
    uchar* row = out.scanLine(y);
    for (int x = 0; x < w; ++x) {
      int v = dilate ? 0 : 255;
      for (int i = -r; i <= r; ++i) {
        const int yy = qBound(0, y + i, h - 1);
        const int p = tmp[static_cast<size_t>(yy * w + x)];
        v = dilate ? std::max(v, p) : std::min(v, p);
      }
      row[x] = static_cast<uchar>(v);
    }
  }
  return out;
}

/** 开运算：先腐蚀后膨胀。 */
QImage morphOpen(const QImage& gray, int k) { return morphMinMax(morphMinMax(gray, k, false), k, true); }

/** 闭运算：先膨胀后腐蚀。 */
QImage morphClose(const QImage& gray, int k) { return morphMinMax(morphMinMax(gray, k, true), k, false); }

/**
 * Canny 风格边缘：高斯平滑、Sobel、非极大值抑制、双阈值滞后。
 * 输出 0/255 灰度图。不是亚像素边缘。
 */
QImage cannyEdges(const QImage& gray, int k, float low, float high) {
  if (low > high) std::swap(low, high);
  if (low < 0) low = 0;
  const QImage blur = gaussianBlur(gray, k);
  if (blur.isNull()) return blur;
  const int w = blur.width();
  const int h = blur.height();
  const size_t n = static_cast<size_t>(w * h);
  std::vector<float> gx(n, 0.0f), gy(n, 0.0f), mag(n, 0.0f);

  auto at = [&](int x, int y) { return grayAt(blur, x, y); };
  for (int y = 0; y < h; ++y) {
    for (int x = 0; x < w; ++x) {
      const int i = y * w + x;
      const int sx = -at(x - 1, y - 1) + at(x + 1, y - 1) - 2 * at(x - 1, y) +
                     2 * at(x + 1, y) - at(x - 1, y + 1) + at(x + 1, y + 1);
      const int sy = -at(x - 1, y - 1) - 2 * at(x, y - 1) - at(x + 1, y - 1) +
                     at(x - 1, y + 1) + 2 * at(x, y + 1) + at(x + 1, y + 1);
      gx[static_cast<size_t>(i)] = static_cast<float>(sx);
      gy[static_cast<size_t>(i)] = static_cast<float>(sy);
      mag[static_cast<size_t>(i)] = std::sqrt(static_cast<float>(sx * sx + sy * sy));
    }
  }

  auto dirBin = [](float vx, float vy) -> int {
    float a = std::atan2(vy, vx) * 180.0f / static_cast<float>(kPi);
    if (a < 0) a += 180.0f;
    if (a < 22.5f || a >= 157.5f) return 0;
    if (a < 67.5f) return 1;
    if (a < 112.5f) return 2;
    return 3;
  };
  const int ox[4] = {1, 1, 0, -1};
  const int oy[4] = {0, 1, 1, 1};

  QImage nms(w, h, QImage::Format_Grayscale8);
  nms.fill(0);
  for (int y = 1; y < h - 1; ++y) {
    uchar* row = nms.scanLine(y);
    for (int x = 1; x < w - 1; ++x) {
      const int i = y * w + x;
      const float m = mag[static_cast<size_t>(i)];
      if (m < low) continue;
      const int d = dirBin(gx[static_cast<size_t>(i)], gy[static_cast<size_t>(i)]);
      const int i1 = (y + oy[d]) * w + (x + ox[d]);
      const int i2 = (y - oy[d]) * w + (x - ox[d]);
      if (m >= mag[static_cast<size_t>(i1)] && m >= mag[static_cast<size_t>(i2)])
        row[x] = (m >= high) ? 255 : 128;
    }
  }

  QImage out(w, h, QImage::Format_Grayscale8);
  out.fill(0);
  std::vector<int> stack;
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
    for (int t = 0; t < 8; ++t) {
      const int nx = x + dx[t];
      const int ny = y + dy[t];
      if (nx <= 0 || ny <= 0 || nx >= w - 1 || ny >= h - 1) continue;
      if (out.constScanLine(ny)[nx]) continue;
      if (nms.constScanLine(ny)[nx] == 0) continue;
      stack.push_back(ny * w + nx);
    }
  }
  return out;
}

/** 按阈值把灰度变成 0/255。 */
QImage thresholdGray(const QImage& gray, int thr) {
  QImage g = toGray8(gray);
  if (g.isNull()) return g;
  thr = qBound(0, thr, 255);
  for (int y = 0; y < g.height(); ++y) {
    uchar* row = g.scanLine(y);
    for (int x = 0; x < g.width(); ++x) row[x] = row[x] >= thr ? 255 : 0;
  }
  return g;
}

/** RGB 各通道按 255-x 反色。 */
QImage invertRgb(const QImage& src) {
  QImage out = toRgb888(src).copy();
  if (out.isNull()) return out;
  for (int y = 0; y < out.height(); ++y) {
    uchar* line = out.scanLine(y);
    const int n = out.width() * 3;
    for (int i = 0; i < n; ++i) line[i] = static_cast<uchar>(255 - line[i]);
  }
  return out;
}

/** 统计灰度图中等于 255 的像素数。 */
int countWhite(const QImage& img) {
  QImage g = toGray8(img);
  if (g.isNull()) return 0;
  int n = 0;
  for (int y = 0; y < g.height(); ++y) {
    const uchar* row = g.constScanLine(y);
    for (int x = 0; x < g.width(); ++x)
      if (row[x] == 255) ++n;
  }
  return n;
}

/** 像素强度和（用于模糊守恒检查）。 */
long long sumGray(const QImage& img) {
  QImage g = toGray8(img);
  if (g.isNull()) return 0;
  long long s = 0;
  for (int y = 0; y < g.height(); ++y) {
    const uchar* row = g.constScanLine(y);
    for (int x = 0; x < g.width(); ++x) s += row[x];
  }
  return s;
}

}  // namespace

PreprocessResult runPreprocess(const QImage& src, const QVariantMap& params) {
  PreprocessResult r;
  if (src.isNull()) {
    r.error = QStringLiteral("empty image");
    return r;
  }

  QString method = normalizeMethod(params.value(QStringLiteral("method")).toString());
  if (method.isEmpty())
    method = normalizeMethod(params.value(QStringLiteral("mode"), QStringLiteral("gray")).toString());
  if (method.isEmpty()) method = QStringLiteral("grayscale");

  const int threshold = qBound(0, params.value(QStringLiteral("threshold"), 128).toInt(), 255);
  const int kernel = normalizeKernel(params.value(QStringLiteral("kernel"), 5).toInt());
  r.method = method;
  r.threshold = threshold;
  r.kernel = kernel;

  if (method == QLatin1String("grayscale")) {
    r.image = grayToRgb(toGray8(src));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("灰度");
    return r;
  }
  if (method == QLatin1String("invert")) {
    r.image = invertRgb(src);
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("反色");
    return r;
  }
  if (method == QLatin1String("threshold")) {
    r.image = grayToRgb(thresholdGray(src, threshold));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("阈值 %1").arg(threshold);
    return r;
  }
  if (method == QLatin1String("blur")) {
    r.image = grayToRgb(gaussianBlur(src, kernel));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("高斯模糊 k=%1").arg(kernel);
    return r;
  }
  if (method == QLatin1String("canny")) {
    float low = 50.0f;
    float high = 150.0f;
    if (params.contains(QStringLiteral("cannyLow")))
      low = static_cast<float>(params.value(QStringLiteral("cannyLow")).toDouble());
    else
      low = static_cast<float>(threshold);
    if (params.contains(QStringLiteral("cannyHigh")))
      high = static_cast<float>(params.value(QStringLiteral("cannyHigh")).toDouble());
    else
      high = std::max(low + 1.0f, 2.0f * low);
    r.image = grayToRgb(cannyEdges(src, kernel, low, high));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("Canny low=%1 high=%2 k=%3")
                 .arg(static_cast<double>(low), 0, 'g', 4)
                 .arg(static_cast<double>(high), 0, 'g', 4)
                 .arg(kernel);
    return r;
  }
  if (method == QLatin1String("erode")) {
    r.image = grayToRgb(morphMinMax(src, kernel, false));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("腐蚀 k=%1").arg(kernel);
    return r;
  }
  if (method == QLatin1String("dilate")) {
    r.image = grayToRgb(morphMinMax(src, kernel, true));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("膨胀 k=%1").arg(kernel);
    return r;
  }
  if (method == QLatin1String("open")) {
    r.image = grayToRgb(morphOpen(src, kernel));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("开运算 k=%1").arg(kernel);
    return r;
  }
  if (method == QLatin1String("close")) {
    r.image = grayToRgb(morphClose(src, kernel));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("闭运算 k=%1").arg(kernel);
    return r;
  }

  r.error = QStringLiteral("unknown method %1").arg(method);
  r.image = toRgb888(src);
  return r;
}

QStringList preprocessSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const PreprocessResult empty = runPreprocess(QImage(), {{QStringLiteral("method"), QStringLiteral("blur")}});
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  QImage patch(8, 8, QImage::Format_RGB888);
  patch.fill(QColor(16, 32, 64));
  // 中心一个红像素，验证灰度与反色、阈值。
  {
    uchar* row = patch.scanLine(3);
    row[3 * 3 + 0] = 255;
    row[3 * 3 + 1] = 0;
    row[3 * 3 + 2] = 0;
  }

  const PreprocessResult gray = runPreprocess(patch, {{QStringLiteral("mode"), QStringLiteral("gray")}});
  check("gray-ok", gray.ok && gray.method == QLatin1String("grayscale") &&
                       gray.image.format() == QImage::Format_RGB888,
        gray.error);
  if (gray.ok) {
    const uchar* p = gray.image.constScanLine(3) + 3 * 3;
    check("gray-equal-channels", p[0] == p[1] && p[1] == p[2],
          QStringLiteral("%1,%2,%3").arg(p[0]).arg(p[1]).arg(p[2]));
    check("gray-red-mid", p[0] > 40 && p[0] < 200, QStringLiteral("y=%1").arg(p[0]));
    const uchar* bg = gray.image.constScanLine(0);
    check("gray-bg-equal", bg[0] == bg[1] && bg[1] == bg[2]);
  }

  const PreprocessResult inv = runPreprocess(patch, {{QStringLiteral("method"), QStringLiteral("invert")}});
  check("invert-ok", inv.ok, inv.error);
  if (inv.ok) {
    const uchar* p = inv.image.constScanLine(3) + 3 * 3;
    check("invert-red", p[0] == 0 && p[1] == 255 && p[2] == 255,
          QStringLiteral("%1,%2,%3").arg(p[0]).arg(p[1]).arg(p[2]));
    const uchar* bg = inv.image.constScanLine(0);
    check("invert-bg", bg[0] == 239 && bg[1] == 223 && bg[2] == 191,
          QStringLiteral("%1,%2,%3").arg(bg[0]).arg(bg[1]).arg(bg[2]));
  }

  QImage step(32, 16, QImage::Format_RGB888);
  for (int y = 0; y < 16; ++y) {
    uchar* row = step.scanLine(y);
    for (int x = 0; x < 32; ++x) {
      const uchar v = x < 16 ? 0 : 255;
      row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = v;
    }
  }
  const PreprocessResult thr = runPreprocess(step, {{QStringLiteral("method"), QStringLiteral("threshold")},
                                                   {QStringLiteral("threshold"), 128}});
  check("thr-ok", thr.ok, thr.error);
  if (thr.ok) {
    check("thr-left", thr.image.constScanLine(8)[0] == 0);
    check("thr-right", thr.image.constScanLine(8)[20 * 3] == 255);
  }

  // 模糊：冲激应被摊开，中心下降，近邻升高，总强度近似守恒。
  QImage impulse(48, 48, QImage::Format_RGB888);
  impulse.fill(0);
  {
    uchar* row = impulse.scanLine(24);
    row[24 * 3] = row[24 * 3 + 1] = row[24 * 3 + 2] = 255;
  }
  const PreprocessResult blur = runPreprocess(impulse, {{QStringLiteral("method"), QStringLiteral("blur")},
                                                        {QStringLiteral("kernel"), 5}});
  check("blur-ok", blur.ok && blur.kernel == 5, blur.error);
  if (blur.ok) {
    const int c = blur.image.constScanLine(24)[24 * 3];
    const int n1 = blur.image.constScanLine(24)[25 * 3];
    const int n2 = blur.image.constScanLine(25)[24 * 3];
    check("blur-center-down", c > 8 && c < 255, QStringLiteral("c=%1").arg(c));
    check("blur-neighbor-up", n1 > 0 && n2 > 0, QStringLiteral("n1=%1 n2=%2").arg(n1).arg(n2));
    const long long s0 = sumGray(impulse);
    const long long s1 = sumGray(blur.image);
    check("blur-energy", std::llabs(s1 - s0) * 20 <= s0,  // 允许 5% 量化误差
          QStringLiteral("s0=%1 s1=%2").arg(s0).arg(s1));
  }

  // 偶数核应升为奇数 6→7，且仍能平滑。
  const PreprocessResult blurEven =
      runPreprocess(impulse, {{QStringLiteral("method"), QStringLiteral("blur")},
                              {QStringLiteral("kernel"), 6}});
  check("blur-even-odd", blurEven.ok && blurEven.kernel == 7, QStringLiteral("k=%1").arg(blurEven.kernel));

  // 阶跃边总变差守恒，改看相邻像素的最大跳变：模糊后应变软。
  auto maxAdj = [](const QImage& im) {
    QImage g = im.convertToFormat(QImage::Format_Grayscale8);
    int m = 0;
    const int y = g.height() / 2;
    const uchar* row = g.constScanLine(y);
    for (int x = 1; x < g.width(); ++x)
      m = std::max(m, std::abs(int(row[x]) - int(row[x - 1])));
    return m;
  };
  const PreprocessResult blurStep =
      runPreprocess(step, {{QStringLiteral("method"), QStringLiteral("blur")}, {QStringLiteral("kernel"), 5}});
  check("blur-smooths-edge",
        blurStep.ok && maxAdj(step) == 255 && maxAdj(blurStep.image) < 200,
        QStringLiteral("before=%1 after=%2").arg(maxAdj(step)).arg(maxAdj(blurStep.image)));

  // Canny：已知竖直阶跃边应在 x≈31–33 检出，远离边界几乎无边缘。
  QImage wall(64, 40, QImage::Format_RGB888);
  wall.fill(0);
  for (int y = 0; y < 40; ++y) {
    uchar* row = wall.scanLine(y);
    for (int x = 32; x < 64; ++x) row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = 255;
  }
  const PreprocessResult canny =
      runPreprocess(wall, {{QStringLiteral("method"), QStringLiteral("canny")},
                           {QStringLiteral("kernel"), 3},
                           {QStringLiteral("cannyLow"), 40},
                           {QStringLiteral("cannyHigh"), 120}});
  check("canny-ok", canny.ok, canny.error);
  if (canny.ok) {
    QImage g = canny.image.convertToFormat(QImage::Format_Grayscale8);
    int near = 0, far = 0, rowsHit = 0;
    for (int y = 4; y < 36; ++y) {
      const uchar* row = g.constScanLine(y);
      bool hit = false;
      for (int x = 1; x < 63; ++x) {
        if (!row[x]) continue;
        if (x >= 29 && x <= 35) {
          ++near;
          hit = true;
        } else {
          ++far;
        }
      }
      if (hit) ++rowsHit;
    }
    check("canny-finds-edge", near >= 20 && rowsHit >= 20,
          QStringLiteral("near=%1 rows=%2 far=%3").arg(near).arg(rowsHit).arg(far));
    check("canny-few-false", far <= 8, QStringLiteral("far=%1 near=%2").arg(far).arg(near));
  }

  // 形态学：5×5 白块在 32×32 黑底上。
  QImage blob(32, 32, QImage::Format_RGB888);
  blob.fill(0);
  for (int y = 10; y < 15; ++y) {
    uchar* row = blob.scanLine(y);
    for (int x = 10; x < 15; ++x) row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = 255;
  }
  check("blob-area", countWhite(blob) == 25, QStringLiteral("a=%1").arg(countWhite(blob)));

  const PreprocessResult dil =
      runPreprocess(blob, {{QStringLiteral("method"), QStringLiteral("dilate")}, {QStringLiteral("kernel"), 3}});
  check("dilate-area", dil.ok && countWhite(dil.image) == 49,  // 7×7
        QStringLiteral("a=%1").arg(countWhite(dil.image)));

  const PreprocessResult ero =
      runPreprocess(blob, {{QStringLiteral("method"), QStringLiteral("erode")}, {QStringLiteral("kernel"), 3}});
  check("erode-area", ero.ok && countWhite(ero.image) == 9,  // 3×3
        QStringLiteral("a=%1").arg(countWhite(ero.image)));

  const PreprocessResult opn =
      runPreprocess(blob, {{QStringLiteral("method"), QStringLiteral("open")}, {QStringLiteral("kernel"), 3}});
  check("open-keeps-blob", opn.ok && countWhite(opn.image) == 25,
        QStringLiteral("a=%1").arg(countWhite(opn.image)));

  // 开运算应去掉 1 像素噪点，保留 5×5。
  QImage speck = blob.copy();
  {
    uchar* row = speck.scanLine(2);
    row[2 * 3] = row[2 * 3 + 1] = row[2 * 3 + 2] = 255;
  }
  check("speck-area", countWhite(speck) == 26);
  const PreprocessResult opnSpeck =
      runPreprocess(speck, {{QStringLiteral("method"), QStringLiteral("open")}, {QStringLiteral("kernel"), 3}});
  check("open-removes-speck", opnSpeck.ok && countWhite(opnSpeck.image) == 25,
        QStringLiteral("a=%1").arg(countWhite(opnSpeck.image)));

  // 闭运算应填上 7×7 中的 1 像素孔。
  QImage holed(32, 32, QImage::Format_RGB888);
  holed.fill(0);
  for (int y = 8; y < 15; ++y) {
    uchar* row = holed.scanLine(y);
    for (int x = 8; x < 15; ++x) row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = 255;
  }
  {
    uchar* row = holed.scanLine(11);
    row[11 * 3] = row[11 * 3 + 1] = row[11 * 3 + 2] = 0;
  }
  check("hole-area", countWhite(holed) == 48, QStringLiteral("a=%1").arg(countWhite(holed)));
  const PreprocessResult cls =
      runPreprocess(holed, {{QStringLiteral("method"), QStringLiteral("close")}, {QStringLiteral("kernel"), 3}});
  check("close-fills-hole", cls.ok && countWhite(cls.image) == 49,
        QStringLiteral("a=%1").arg(countWhite(cls.image)));

  const PreprocessResult bad =
      runPreprocess(patch, {{QStringLiteral("method"), QStringLiteral("not-a-filter")}});
  check("bad-method", !bad.ok && !bad.error.isEmpty(), bad.error);

  return fails;
}

}  // namespace sieans_qt
