#include "PreprocessOp.hpp"

#include <QColor>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRect>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <cstring>
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
  if (raw == QLatin1String("histeq") || raw == QLatin1String("histogram") ||
      raw == QLatin1String("histequal") || raw == QLatin1String("equalizehist"))
    return QStringLiteral("equalize");
  if (raw == QLatin1String("brightness") || raw == QLatin1String("enhance"))
    return QStringLiteral("contrast");
  if (raw == QLatin1String("plus")) return QStringLiteral("add");
  if (raw == QLatin1String("sub") || raw == QLatin1String("minus")) return QStringLiteral("subtract");
  if (raw == QLatin1String("mul") || raw == QLatin1String("times")) return QStringLiteral("multiply");
  if (raw == QLatin1String("abs_diff") || raw == QLatin1String("abs-diff") ||
      raw == QLatin1String("difference") || raw == QLatin1String("diff"))
    return QStringLiteral("absdiff");
  if (raw == QLatin1String("scale") || raw == QLatin1String("interpolate") ||
      raw == QLatin1String("interp") || raw == QLatin1String("zoom"))
    return QStringLiteral("resize");
  if (raw == QLatin1String("extract") || raw == QLatin1String("roi")) return QStringLiteral("crop");
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


constexpr int kMaxResize = 4096;

/** 把路径解析成可读文件；失败返回空。 */
QString resolveOtherPath(const QString& raw, const QString& baseDir) {
  const QString path = raw.trimmed();
  if (path.isEmpty()) return {};
  const QFileInfo direct(path);
  if (direct.isAbsolute() && direct.isFile()) return direct.absoluteFilePath();
  QStringList roots;
  if (!baseDir.trimmed().isEmpty()) roots << baseDir;
  roots << QDir::currentPath();
  for (const QString& root : roots) {
    const QFileInfo fi(QDir(root).filePath(path));
    if (fi.isFile()) return fi.absoluteFilePath();
  }
  return {};
}

/** 加载算术运算的第二幅图：优先 _otherImage，其次 otherPath/secondPath。 */
QImage loadOtherImage(const QVariantMap& params, QString* err) {
  const QVariant packed = params.value(QStringLiteral("_otherImage"));
  if (packed.canConvert<QImage>()) {
    const QImage im = packed.value<QImage>();
    if (!im.isNull()) return im.convertToFormat(QImage::Format_RGB888);
  }
  const QString raw = params.contains(QStringLiteral("otherPath"))
                          ? params.value(QStringLiteral("otherPath")).toString()
                          : params.value(QStringLiteral("secondPath")).toString();
  if (raw.trimmed().isEmpty()) return {};
  const QString path = resolveOtherPath(raw, params.value(QStringLiteral("baseDir")).toString());
  if (path.isEmpty()) {
    if (err) *err = QStringLiteral("other image not found: %1").arg(raw);
    return {};
  }
  QImage im(path);
  if (im.isNull()) {
    if (err) *err = QStringLiteral("cannot read other image: %1").arg(path);
    return {};
  }
  return im.convertToFormat(QImage::Format_RGB888);
}

/** 标准 8 位直方图均衡查找表。 */
void equalizeLut(const int hist[256], int n, int lut[256]) {
  int cdfMin = 0;
  int acc = 0;
  int cdf[256];
  for (int i = 0; i < 256; ++i) {
    acc += hist[i];
    cdf[i] = acc;
    if (cdfMin == 0 && hist[i] > 0) cdfMin = acc;
  }
  const int denom = std::max(1, n - cdfMin);
  for (int i = 0; i < 256; ++i) {
    if (cdf[i] <= cdfMin)
      lut[i] = 0;
    else
      lut[i] = qBound(0, qRound(255.0 * (cdf[i] - cdfMin) / denom), 255);
  }
}

/** 全图亮度直方图均衡，彩色通道按亮度比例缩放。不是 CLAHE。 */
QImage equalizeImage(const QImage& src) {
  QImage rgb = toRgb888(src);
  if (rgb.isNull()) return rgb;
  const int w = rgb.width();
  const int h = rgb.height();
  int hist[256];
  for (int i = 0; i < 256; ++i) hist[i] = 0;
  std::vector<int> yv(static_cast<size_t>(w * h), 0);
  for (int y = 0; y < h; ++y) {
    const uchar* row = rgb.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int Y = (299 * row[x * 3] + 587 * row[x * 3 + 1] + 114 * row[x * 3 + 2] + 500) / 1000;
      yv[static_cast<size_t>(y * w + x)] = qBound(0, Y, 255);
      ++hist[yv[static_cast<size_t>(y * w + x)]];
    }
  }
  int lut[256];
  equalizeLut(hist, w * h, lut);
  for (int y = 0; y < h; ++y) {
    uchar* row = rgb.scanLine(y);
    for (int x = 0; x < w; ++x) {
      const int Y = yv[static_cast<size_t>(y * w + x)];
      const int Y2 = lut[Y];
      if (Y <= 0) {
        row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = static_cast<uchar>(Y2);
        continue;
      }
      for (int c = 0; c < 3; ++c) {
        const int v = qBound(0, qRound(row[x * 3 + c] * (double(Y2) / Y)), 255);
        row[x * 3 + c] = static_cast<uchar>(v);
      }
    }
  }
  return rgb;
}

/** 每通道伽马校正，out=255*(in/255)^gamma。 */
QImage applyGamma(const QImage& src, double gamma) {
  QImage rgb = toRgb888(src).copy();
  if (rgb.isNull()) return rgb;
  if (gamma < 1e-6) gamma = 1e-6;
  uchar lut[256];
  for (int i = 0; i < 256; ++i)
    lut[i] = static_cast<uchar>(qBound(0, qRound(255.0 * std::pow(i / 255.0, gamma)), 255));
  for (int y = 0; y < rgb.height(); ++y) {
    uchar* row = rgb.scanLine(y);
    const int n = rgb.width() * 3;
    for (int i = 0; i < n; ++i) row[i] = lut[row[i]];
  }
  return rgb;
}

/** 线性对比度与亮度。 */
QImage applyContrast(const QImage& src, double contrast, double brightness) {
  QImage rgb = toRgb888(src).copy();
  if (rgb.isNull()) return rgb;
  int lut[256];
  for (int i = 0; i < 256; ++i)
    lut[i] = qBound(0, qRound(contrast * (i - 128.0) + 128.0 + brightness), 255);
  for (int y = 0; y < rgb.height(); ++y) {
    uchar* row = rgb.scanLine(y);
    const int n = rgb.width() * 3;
    for (int i = 0; i < n; ++i) row[i] = static_cast<uchar>(lut[row[i]]);
  }
  return rgb;
}

/** 把第二幅图铺到与第一幅相同的画布：重叠区复制，其余为 fill。 */
QImage alignOther(const QImage& a, const QImage& b, int fill) {
  QImage out(a.size(), QImage::Format_RGB888);
  out.fill(QColor(fill, fill, fill));
  if (b.isNull()) return out;
  const QImage bb = b.convertToFormat(QImage::Format_RGB888);
  const int w = std::min(a.width(), bb.width());
  const int h = std::min(a.height(), bb.height());
  for (int y = 0; y < h; ++y) {
    uchar* d = out.scanLine(y);
    const uchar* s = bb.constScanLine(y);
    std::memcpy(d, s, static_cast<size_t>(w * 3));
  }
  return out;
}

/** 逐像素算术：add/subtract/multiply/absdiff。other 空则用常量 value。 */
QImage arithImages(const QImage& aIn, const QImage& bIn, const QString& op, int value, int bias) {
  QImage a = toRgb888(aIn).copy();
  if (a.isNull()) return a;
  const bool haveB = !bIn.isNull();
  QImage b = haveB ? alignOther(a, bIn, value) : QImage();
  for (int y = 0; y < a.height(); ++y) {
    uchar* da = a.scanLine(y);
    const uchar* db = haveB ? b.constScanLine(y) : nullptr;
    const int n = a.width() * 3;
    for (int i = 0; i < n; ++i) {
      const int va = da[i];
      const int vb = haveB ? db[i] : value;
      int out = va;
      if (op == QLatin1String("add"))
        out = va + vb;
      else if (op == QLatin1String("subtract"))
        out = va - vb + bias;
      else if (op == QLatin1String("multiply"))
        out = (va * vb + 127) / 255;
      else if (op == QLatin1String("absdiff"))
        out = std::abs(va - vb);
      da[i] = static_cast<uchar>(qBound(0, out, 255));
    }
  }
  return a;
}

/** 采样一个通道像素，越界复制边界。 */
double sampleChannel(const QImage& rgb, double x, double y, int ch, const QString& interp) {
  const int w = rgb.width();
  const int h = rgb.height();
  if (w <= 0 || h <= 0) return 0;
  auto at = [&](int ix, int iy) -> double {
    ix = qBound(0, ix, w - 1);
    iy = qBound(0, iy, h - 1);
    return rgb.constScanLine(iy)[ix * 3 + ch];
  };
  if (interp == QLatin1String("nearest")) {
    return at(qRound(x), qRound(y));
  }
  if (interp == QLatin1String("bicubic")) {
    const int x0 = int(std::floor(x));
    const int y0 = int(std::floor(y));
    const double fx = x - x0;
    const double fy = y - y0;
    auto keys = [](double t, double p0, double p1, double p2, double p3) {
      const double a = -0.5;
      const double t2 = t * t;
      const double t3 = t2 * t;
      return (a * t3 - 2 * a * t2 + a * t) * p0 +
             ((a + 2) * t3 - (a + 3) * t2 + 1) * p1 +
             ((-a - 2) * t3 + (2 * a + 3) * t2 - a * t) * p2 +
             (-a * t3 + a * t2) * p3;
    };
    double col[4];
    for (int m = 0; m < 4; ++m) {
      const int yy = y0 - 1 + m;
      col[m] = keys(fx, at(x0 - 1, yy), at(x0, yy), at(x0 + 1, yy), at(x0 + 2, yy));
    }
    return keys(fy, col[0], col[1], col[2], col[3]);
  }
  // bilinear default
  const int x0 = int(std::floor(x));
  const int y0 = int(std::floor(y));
  const double tx = x - x0;
  const double ty = y - y0;
  const double v00 = at(x0, y0), v10 = at(x0 + 1, y0), v01 = at(x0, y0 + 1), v11 = at(x0 + 1, y0 + 1);
  return (1 - tx) * (1 - ty) * v00 + tx * (1 - ty) * v10 + (1 - tx) * ty * v01 + tx * ty * v11;
}

/** 缩放到指定尺寸。interp=nearest|bilinear|bicubic。 */
QImage resizeImage(const QImage& src, int nw, int nh, const QString& interp) {
  QImage rgb = toRgb888(src);
  if (rgb.isNull() || nw <= 0 || nh <= 0) return {};
  if (nw == rgb.width() && nh == rgb.height()) return rgb;
  QImage out(nw, nh, QImage::Format_RGB888);
  const double sx = (nw == 1) ? 0.0 : (rgb.width()) / double(nw);
  const double sy = (nh == 1) ? 0.0 : (rgb.height()) / double(nh);
  for (int y = 0; y < nh; ++y) {
    uchar* row = out.scanLine(y);
    const double oy = (y + 0.5) * sy - 0.5;
    for (int x = 0; x < nw; ++x) {
      const double ox = (x + 0.5) * sx - 0.5;
      for (int c = 0; c < 3; ++c)
        row[x * 3 + c] = static_cast<uchar>(qBound(0, qRound(sampleChannel(rgb, ox, oy, c, interp)), 255));
    }
  }
  return out;
}

/** 抠出 ROI，超出部分与图像求交；空交返回空图。 */
QImage cropRoi(const QImage& src, int x, int y, int w, int h, QString* err) {
  QImage rgb = toRgb888(src);
  if (rgb.isNull()) return rgb;
  if (w <= 0) w = rgb.width() - x;
  if (h <= 0) h = rgb.height() - y;
  const QRect full(0, 0, rgb.width(), rgb.height());
  const QRect want(x, y, w, h);
  const QRect hit = full.intersected(want);
  if (hit.isEmpty()) {
    if (err) *err = QStringLiteral("crop ROI is empty");
    return {};
  }
  return rgb.copy(hit);
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

  if (method == QLatin1String("equalize")) {
    r.image = equalizeImage(src);
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("直方图均衡");
    return r;
  }
  if (method == QLatin1String("gamma")) {
    const double gamma = params.value(QStringLiteral("gamma"), 1.0).toDouble();
    r.image = applyGamma(src, gamma);
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("伽马 %1").arg(gamma, 0, 'g', 4);
    return r;
  }
  if (method == QLatin1String("contrast")) {
    const double contrast = params.value(QStringLiteral("contrast"), 1.0).toDouble();
    const double brightness = params.value(QStringLiteral("brightness"), 0.0).toDouble();
    r.image = applyContrast(src, contrast, brightness);
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("对比度 %1 亮度 %2").arg(contrast, 0, 'g', 3).arg(brightness, 0, 'g', 3);
    return r;
  }
  if (method == QLatin1String("add") || method == QLatin1String("subtract") ||
      method == QLatin1String("multiply") || method == QLatin1String("absdiff")) {
    QString loadErr;
    const QImage other = loadOtherImage(params, &loadErr);
    if (!loadErr.isEmpty()) {
      r.error = loadErr;
      r.image = toRgb888(src);
      return r;
    }
    const bool haveConst = params.contains(QStringLiteral("value"));
    if (other.isNull() && !haveConst) {
      r.error = QStringLiteral("need otherPath, _otherImage or value");
      r.image = toRgb888(src);
      return r;
    }
    const int value = qBound(0, params.value(QStringLiteral("value"), 0).toInt(), 255);
    const int bias = params.value(QStringLiteral("bias"), 0).toInt();
    r.image = arithImages(src, other, method, value, bias);
    r.ok = !r.image.isNull();
    r.note = other.isNull() ? QStringLiteral("%1 value=%2").arg(method).arg(value)
                            : QStringLiteral("%1 第二图 %2×%3").arg(method).arg(other.width()).arg(other.height());
    return r;
  }
  if (method == QLatin1String("resize")) {
    const double scale = params.value(QStringLiteral("scale"), 1.0).toDouble();
    int nw = params.value(QStringLiteral("outW"), 0).toInt();
    int nh = params.value(QStringLiteral("outH"), 0).toInt();
    if (nw <= 0 && nh <= 0) {
      nw = qMax(1, qRound(src.width() * (scale > 0 ? scale : 1.0)));
      nh = qMax(1, qRound(src.height() * (scale > 0 ? scale : 1.0)));
    } else if (nw <= 0) {
      nw = qMax(1, qRound(src.width() * (double(nh) / std::max(1, src.height()))));
    } else if (nh <= 0) {
      nh = qMax(1, qRound(src.height() * (double(nw) / std::max(1, src.width()))));
    }
    if (nw > kMaxResize || nh > kMaxResize) {
      r.error = QStringLiteral("resize output exceeds %1").arg(kMaxResize);
      r.image = toRgb888(src);
      return r;
    }
    QString interp = params.value(QStringLiteral("interp"), QStringLiteral("bilinear")).toString().trimmed().toLower();
    if (interp == QLatin1String("nn") || interp == QLatin1String("point")) interp = QStringLiteral("nearest");
    if (interp == QLatin1String("cubic") || interp == QLatin1String("bicubic8")) interp = QStringLiteral("bicubic");
    if (interp != QLatin1String("nearest") && interp != QLatin1String("bicubic")) interp = QStringLiteral("bilinear");
    r.image = resizeImage(src, nw, nh, interp);
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("缩放 %1×%2 %3").arg(nw).arg(nh).arg(interp);
    return r;
  }
  if (method == QLatin1String("crop")) {
    const int x = params.value(QStringLiteral("roiX"), 0).toInt();
    const int y = params.value(QStringLiteral("roiY"), 0).toInt();
    const int w = params.value(QStringLiteral("roiW"), 0).toInt();
    const int h = params.value(QStringLiteral("roiH"), 0).toInt();
    QString err;
    r.image = cropRoi(src, x, y, w, h, &err);
    if (r.image.isNull()) {
      r.error = err.isEmpty() ? QStringLiteral("crop failed") : err;
      return r;
    }
    r.ok = true;
    r.note = QStringLiteral("裁剪 %1,%2 %3×%4").arg(x).arg(y).arg(r.image.width()).arg(r.image.height());
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

  // 伽马：中灰 128，gamma=2.2，应等于 255*(128/255)^2.2。
  {
    QImage mid(8, 8, QImage::Format_RGB888);
    mid.fill(QColor(128, 128, 128));
    const PreprocessResult g = runPreprocess(mid, {{QStringLiteral("method"), QStringLiteral("gamma")},
                                                   {QStringLiteral("gamma"), 2.2}});
    const int expect = qBound(0, qRound(255.0 * std::pow(128.0 / 255.0, 2.2)), 255);
    check("gamma-ok", g.ok, g.error);
    if (g.ok) {
      const int v = g.image.constScanLine(0)[0];
      check("gamma-curve", std::abs(v - expect) <= 1,
            QStringLiteral("v=%1 expect=%2").arg(v).arg(expect));
    }
    const PreprocessResult ident = runPreprocess(mid, {{QStringLiteral("method"), QStringLiteral("gamma")},
                                                       {QStringLiteral("gamma"), 1.0}});
    check("gamma-identity", ident.ok && ident.image.constScanLine(0)[0] == 128);
  }

  // 均衡：64–191 的斜坡，均衡后动态范围应拉开。
  {
    QImage ramp(64, 16, QImage::Format_RGB888);
    for (int y = 0; y < 16; ++y) {
      uchar* row = ramp.scanLine(y);
      for (int x = 0; x < 64; ++x) {
        const uchar v = static_cast<uchar>(64 + 2 * x);  // 64..190
        row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = v;
      }
    }
    const PreprocessResult eq = runPreprocess(ramp, {{QStringLiteral("method"), QStringLiteral("equalize")}});
    check("equalize-ok", eq.ok, eq.error);
    if (eq.ok) {
      QImage g = eq.image.convertToFormat(QImage::Format_Grayscale8);
      int mn = 255, mx = 0;
      for (int y = 0; y < 16; ++y) {
        const uchar* b = g.constScanLine(y);
        for (int x = 0; x < 64; ++x) {
          mn = std::min(mn, int(b[x]));
          mx = std::max(mx, int(b[x]));
        }
      }
      check("equalize-range", mn <= 8 && mx >= 247, QStringLiteral("min=%1 max=%2").arg(mn).arg(mx));
      const double c0 = 190 - 64;
      const double c1 = mx - mn;
      check("equalize-contrast-up", c1 > c0 + 20, QStringLiteral("c0=%1 c1=%2").arg(c0).arg(c1));
    }
  }

  // 对比度 2 应把 64 推到 0 附近、192 推到 255 附近。
  {
    QImage mid(4, 4, QImage::Format_RGB888);
    mid.fill(QColor(64, 64, 64));
    mid.scanLine(0)[0] = mid.scanLine(0)[1] = mid.scanLine(0)[2] = 192;
    const PreprocessResult c = runPreprocess(mid, {{QStringLiteral("method"), QStringLiteral("contrast")},
                                                   {QStringLiteral("contrast"), 2.0},
                                                   {QStringLiteral("brightness"), 0}});
    check("contrast-ok", c.ok && c.image.constScanLine(1)[0] == 0 && c.image.constScanLine(0)[0] == 255,
          QStringLiteral("lo=%1 hi=%2").arg(c.image.isNull() ? -1 : c.image.constScanLine(1)[0])
              .arg(c.image.isNull() ? -1 : c.image.constScanLine(0)[0]));
  }

  // 相同图相减应为 0；加常量；乘 128≈减半。
  {
    QImage a(8, 8, QImage::Format_RGB888);
    a.fill(QColor(80, 100, 120));
    QVariantMap sub;
    sub.insert(QStringLiteral("method"), QStringLiteral("subtract"));
    sub.insert(QStringLiteral("_otherImage"), QVariant::fromValue(a));
    const PreprocessResult d = runPreprocess(a, sub);
    check("subtract-same", d.ok && d.image.constScanLine(0)[0] == 0 && d.image.constScanLine(0)[1] == 0 &&
                               d.image.constScanLine(0)[2] == 0,
          QStringLiteral("%1,%2,%3 err=%4")
              .arg(d.image.isNull() ? -1 : d.image.constScanLine(0)[0])
              .arg(d.image.isNull() ? -1 : d.image.constScanLine(0)[1])
              .arg(d.image.isNull() ? -1 : d.image.constScanLine(0)[2])
              .arg(d.error));
    const PreprocessResult ad = runPreprocess(a, {{QStringLiteral("method"), QStringLiteral("add")},
                                                  {QStringLiteral("value"), 10}});
    check("add-const", ad.ok && ad.image.constScanLine(0)[0] == 90 && ad.image.constScanLine(0)[2] == 130,
          QStringLiteral("%1,%2").arg(ad.image.isNull() ? -1 : ad.image.constScanLine(0)[0])
              .arg(ad.image.isNull() ? -1 : ad.image.constScanLine(0)[2]));
    const PreprocessResult mul = runPreprocess(a, {{QStringLiteral("method"), QStringLiteral("multiply")},
                                                   {QStringLiteral("value"), 128}});
    const int mv = mul.ok ? mul.image.constScanLine(0)[0] : -1;
    check("multiply-half", mul.ok && std::abs(mv - 40) <= 1, QStringLiteral("v=%1").arg(mv));
    const PreprocessResult absd = runPreprocess(a, {{QStringLiteral("method"), QStringLiteral("absdiff")},
                                                    {QStringLiteral("value"), 100}});
    check("absdiff-const", absd.ok && absd.image.constScanLine(0)[0] == 20 &&
                               absd.image.constScanLine(0)[2] == 20,
          QStringLiteral("%1,%2")
              .arg(absd.image.isNull() ? -1 : absd.image.constScanLine(0)[0])
              .arg(absd.image.isNull() ? -1 : absd.image.constScanLine(0)[2]));
  }

  // 缩放：4×4 左上白点，最近邻 2 倍应为 2×2 白块，其余为 0。
  {
    QImage dot(4, 4, QImage::Format_RGB888);
    dot.fill(0);
    dot.scanLine(0)[0] = dot.scanLine(0)[1] = dot.scanLine(0)[2] = 255;
    const PreprocessResult nn = runPreprocess(dot, {{QStringLiteral("method"), QStringLiteral("resize")},
                                                    {QStringLiteral("scale"), 2.0},
                                                    {QStringLiteral("interp"), QStringLiteral("nearest")}});
    check("resize-nn-size", nn.ok && nn.image.width() == 8 && nn.image.height() == 8, nn.error);
    if (nn.ok) {
      QImage g = nn.image.convertToFormat(QImage::Format_Grayscale8);
      int on = 0;
      for (int y = 0; y < 8; ++y)
        for (int x = 0; x < 8; ++x)
          if (g.constScanLine(y)[x] >= 250) ++on;
      check("resize-nn-block", on == 4 && g.constScanLine(0)[0] >= 250 && g.constScanLine(1)[1] >= 250 &&
                                   g.constScanLine(2)[2] <= 5,
            QStringLiteral("on=%1 p00=%2 p22=%3").arg(on).arg(g.constScanLine(0)[0]).arg(g.constScanLine(2)[2]));
    }
    const PreprocessResult bl = runPreprocess(dot, {{QStringLiteral("method"), QStringLiteral("resize")},
                                                    {QStringLiteral("outW"), 8},
                                                    {QStringLiteral("outH"), 8},
                                                    {QStringLiteral("interp"), QStringLiteral("bilinear")}});
    check("resize-bilinear", bl.ok && bl.image.width() == 8);
    if (bl.ok) {
      QImage g = bl.image.convertToFormat(QImage::Format_Grayscale8);
      check("resize-bilinear-peak", g.constScanLine(0)[0] >= 200, QStringLiteral("v=%1").arg(g.constScanLine(0)[0]));
      check("resize-bilinear-far", g.constScanLine(7)[7] <= 20, QStringLiteral("v=%1").arg(g.constScanLine(7)[7]));
    }
    const PreprocessResult bc = runPreprocess(dot, {{QStringLiteral("method"), QStringLiteral("resize")},
                                                    {QStringLiteral("scale"), 2.0},
                                                    {QStringLiteral("interp"), QStringLiteral("bicubic")}});
    check("resize-bicubic", bc.ok && bc.image.width() == 8 &&
                                bc.image.convertToFormat(QImage::Format_Grayscale8).constScanLine(0)[0] >= 200,
          bc.error);
  }

  // 裁剪必须原样返回 ROI 像素。
  {
    QImage src(8, 8, QImage::Format_RGB888);
    src.fill(QColor(1, 2, 3));
    for (int y = 0; y < 8; ++y)
      for (int x = 0; x < 8; ++x) {
        uchar* p = src.scanLine(y) + x * 3;
        p[0] = static_cast<uchar>(10 * y + x);
        p[1] = static_cast<uchar>(40 + y);
        p[2] = static_cast<uchar>(80 + x);
      }
    const PreprocessResult cr = runPreprocess(src, {{QStringLiteral("method"), QStringLiteral("crop")},
                                                    {QStringLiteral("roiX"), 2},
                                                    {QStringLiteral("roiY"), 3},
                                                    {QStringLiteral("roiW"), 3},
                                                    {QStringLiteral("roiH"), 2}});
    check("crop-ok", cr.ok && cr.image.width() == 3 && cr.image.height() == 2, cr.error);
    if (cr.ok) {
      bool same = true;
      QString detail;
      for (int y = 0; y < 2 && same; ++y)
        for (int x = 0; x < 3; ++x) {
          const uchar* a = src.constScanLine(3 + y) + (2 + x) * 3;
          const uchar* b = cr.image.constScanLine(y) + x * 3;
          if (a[0] != b[0] || a[1] != b[1] || a[2] != b[2]) {
            same = false;
            detail = QStringLiteral("x=%1 y=%2 src=%3,%4,%5 out=%6,%7,%8")
                         .arg(x)
                         .arg(y)
                         .arg(a[0])
                         .arg(a[1])
                         .arg(a[2])
                         .arg(b[0])
                         .arg(b[1])
                         .arg(b[2]);
          }
        }
      check("crop-pixels", same, detail);
    }
  }

  return fails;
}

}  // namespace sieans_qt
