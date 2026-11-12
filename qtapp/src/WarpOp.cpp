#include "WarpOp.hpp"

#include <QColor>
#include <QPointF>
#include <functional>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <vector>

namespace sieans_qt {
namespace {

/** 高斯消元求解 n×n，失败返回 false。 */
bool solveLinear(std::vector<double> a, std::vector<double> b, int n, std::vector<double>& x) {
  x.assign(static_cast<size_t>(n), 0.0);
  if (n <= 0) return false;
  for (int k = 0; k < n; ++k) {
    int piv = k;
    double best = std::fabs(a[static_cast<size_t>(k * n + k)]);
    for (int i = k + 1; i < n; ++i) {
      const double v = std::fabs(a[static_cast<size_t>(i * n + k)]);
      if (v > best) {
        best = v;
        piv = i;
      }
    }
    if (best < 1e-14) return false;
    if (piv != k) {
      for (int j = k; j < n; ++j)
        std::swap(a[static_cast<size_t>(k * n + j)], a[static_cast<size_t>(piv * n + j)]);
      std::swap(b[static_cast<size_t>(k)], b[static_cast<size_t>(piv)]);
    }
    const double diag = a[static_cast<size_t>(k * n + k)];
    for (int i = k + 1; i < n; ++i) {
      const double f = a[static_cast<size_t>(i * n + k)] / diag;
      b[static_cast<size_t>(i)] -= f * b[static_cast<size_t>(k)];
      for (int j = k; j < n; ++j)
        a[static_cast<size_t>(i * n + j)] -= f * a[static_cast<size_t>(k * n + j)];
    }
  }
  for (int i = n - 1; i >= 0; --i) {
    double s = b[static_cast<size_t>(i)];
    for (int j = i + 1; j < n; ++j) s -= a[static_cast<size_t>(i * n + j)] * x[static_cast<size_t>(j)];
    const double diag = a[static_cast<size_t>(i * n + i)];
    if (std::fabs(diag) < 1e-14) return false;
    x[static_cast<size_t>(i)] = s / diag;
  }
  return true;
}

struct Affine {
  double a[6] = {1, 0, 0, 0, 1, 0};  // [a00 a01 a02; a10 a11 a12]
};

struct Homography {
  double h[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
};

/** 读点对：src1X/src1Y/dst1X/dst1Y … 最多 4 组。 */
int readPointPairs(const QVariantMap& p, QPointF src[4], QPointF dst[4]) {
  int n = 0;
  for (int i = 1; i <= 4; ++i) {
    const QString sx = QStringLiteral("src%1X").arg(i);
    const QString sy = QStringLiteral("src%1Y").arg(i);
    const QString dx = QStringLiteral("dst%1X").arg(i);
    const QString dy = QStringLiteral("dst%1Y").arg(i);
    if (!p.contains(sx) && !p.contains(dx)) continue;
    src[n] = QPointF(p.value(sx, 0).toDouble(), p.value(sy, 0).toDouble());
    dst[n] = QPointF(p.value(dx, 0).toDouble(), p.value(dy, 0).toDouble());
    ++n;
  }
  return n;
}

/** 由 3 组点估计仿射：dst = A * src。 */
bool affineFromPoints(const QPointF src[4], const QPointF dst[4], int n, Affine& a) {
  if (n < 3) return false;
  // [x y 1 0 0 0] [a00..] = x'
  // [0 0 0 x y 1]         = y'
  std::vector<double> M(6 * 6, 0.0), b(6, 0.0);
  // 用正规方程  (各点两行累加)
  for (int i = 0; i < n && i < 4; ++i) {
    const double x = src[i].x(), y = src[i].y();
    const double u = dst[i].x(), v = dst[i].y();
    const double r1[6] = {x, y, 1, 0, 0, 0};
    const double r2[6] = {0, 0, 0, x, y, 1};
    for (int c = 0; c < 6; ++c) {
      b[static_cast<size_t>(c)] += r1[c] * u + r2[c] * v;
      for (int d = 0; d < 6; ++d)
        M[static_cast<size_t>(c * 6 + d)] += r1[c] * r1[d] + r2[c] * r2[d];
    }
  }
  std::vector<double> x;
  if (!solveLinear(M, b, 6, x)) return false;
  for (int i = 0; i < 6; ++i) a.a[i] = x[static_cast<size_t>(i)];
  return std::isfinite(a.a[0]);
}

/** 由 4 组点估计单应，h22=1。 */
bool homographyFromPoints(const QPointF src[4], const QPointF dst[4], int n, Homography& h) {
  if (n < 4) return false;
  std::vector<double> M(8 * 8, 0.0), b(8, 0.0);
  for (int i = 0; i < 4; ++i) {
    const double x = src[i].x(), y = src[i].y();
    const double u = dst[i].x(), v = dst[i].y();
    // x' = (h00 x + h01 y + h02) / (h20 x + h21 y + 1)
    const int r0 = i * 2;
    const int r1 = i * 2 + 1;
    auto put = [&](int r, const double row[8], double rhs) {
      for (int c = 0; c < 8; ++c) M[static_cast<size_t>(r * 8 + c)] = row[c];
      b[static_cast<size_t>(r)] = rhs;
    };
    const double row0[8] = {x, y, 1, 0, 0, 0, -u * x, -u * y};
    const double row1[8] = {0, 0, 0, x, y, 1, -v * x, -v * y};
    put(r0, row0, u);
    put(r1, row1, v);
  }
  std::vector<double> x;
  if (!solveLinear(M, b, 8, x)) return false;
  for (int i = 0; i < 8; ++i) h.h[i] = x[static_cast<size_t>(i)];
  h.h[8] = 1.0;
  return std::isfinite(h.h[0]);
}

bool invertAffine(const Affine& a, Affine& inv) {
  const double det = a.a[0] * a.a[4] - a.a[1] * a.a[3];
  if (std::fabs(det) < 1e-14) return false;
  inv.a[0] = a.a[4] / det;
  inv.a[1] = -a.a[1] / det;
  inv.a[3] = -a.a[3] / det;
  inv.a[4] = a.a[0] / det;
  inv.a[2] = -(inv.a[0] * a.a[2] + inv.a[1] * a.a[5]);
  inv.a[5] = -(inv.a[3] * a.a[2] + inv.a[4] * a.a[5]);
  return true;
}

bool invertHomography(const Homography& h, Homography& inv) {
  const double* m = h.h;
  const double det =
      m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) +
      m[2] * (m[3] * m[7] - m[4] * m[6]);
  if (std::fabs(det) < 1e-14) return false;
  inv.h[0] = (m[4] * m[8] - m[5] * m[7]) / det;
  inv.h[1] = (m[2] * m[7] - m[1] * m[8]) / det;
  inv.h[2] = (m[1] * m[5] - m[2] * m[4]) / det;
  inv.h[3] = (m[5] * m[6] - m[3] * m[8]) / det;
  inv.h[4] = (m[0] * m[8] - m[2] * m[6]) / det;
  inv.h[5] = (m[2] * m[3] - m[0] * m[5]) / det;
  inv.h[6] = (m[3] * m[7] - m[4] * m[6]) / det;
  inv.h[7] = (m[1] * m[6] - m[0] * m[7]) / det;
  inv.h[8] = (m[0] * m[4] - m[1] * m[3]) / det;
  return std::isfinite(inv.h[0]);
}

void applyAffine(const Affine& a, double x, double y, double& u, double& v) {
  u = a.a[0] * x + a.a[1] * y + a.a[2];
  v = a.a[3] * x + a.a[4] * y + a.a[5];
}

void applyHomography(const Homography& h, double x, double y, double& u, double& v) {
  const double w = h.h[6] * x + h.h[7] * y + h.h[8];
  u = (h.h[0] * x + h.h[1] * y + h.h[2]) / (std::fabs(w) < 1e-14 ? 1e-14 : w);
  v = (h.h[3] * x + h.h[4] * y + h.h[5]) / (std::fabs(w) < 1e-14 ? 1e-14 : w);
}

QImage toRgb888(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_RGB888);
}

/** 双线性采样 RGB888，越界返回 0。 */
void sampleBilinear(const QImage& img, double x, double y, int& r, int& g, int& b) {
  const int w = img.width();
  const int h = img.height();
  if (x < 0 || y < 0 || x >= w - 1 || y >= h - 1) {
    r = g = b = 0;
    return;
  }
  const int x0 = static_cast<int>(std::floor(x));
  const int y0 = static_cast<int>(std::floor(y));
  const double tx = x - x0;
  const double ty = y - y0;
  auto ch = [&](int ix, int iy, int c) { return img.constScanLine(iy)[ix * 3 + c]; };
  const double v0 = (1 - tx) * (1 - ty) * ch(x0, y0, 0) + tx * (1 - ty) * ch(x0 + 1, y0, 0) +
                    (1 - tx) * ty * ch(x0, y0 + 1, 0) + tx * ty * ch(x0 + 1, y0 + 1, 0);
  const double v1 = (1 - tx) * (1 - ty) * ch(x0, y0, 1) + tx * (1 - ty) * ch(x0 + 1, y0, 1) +
                    (1 - tx) * ty * ch(x0, y0 + 1, 1) + tx * ty * ch(x0 + 1, y0 + 1, 1);
  const double v2 = (1 - tx) * (1 - ty) * ch(x0, y0, 2) + tx * (1 - ty) * ch(x0 + 1, y0, 2) +
                    (1 - tx) * ty * ch(x0, y0 + 1, 2) + tx * ty * ch(x0 + 1, y0 + 1, 2);
  r = qBound(0, qRound(v0), 255);
  g = qBound(0, qRound(v1), 255);
  b = qBound(0, qRound(v2), 255);
}

/** 按源坐标映射填充输出图。srcOfOut(ox,oy)->(sx,sy)。 */
QImage remap(const QImage& src, int ow, int oh,
             const std::function<void(int, int, double&, double&)>& srcOfOut) {
  const QImage in = toRgb888(src);
  QImage out(ow, oh, QImage::Format_RGB888);
  out.fill(0);
  for (int y = 0; y < oh; ++y) {
    uchar* row = out.scanLine(y);
    for (int x = 0; x < ow; ++x) {
      double sx = 0, sy = 0;
      srcOfOut(x, y, sx, sy);
      int r, g, b;
      sampleBilinear(in, sx, sy, r, g, b);
      row[x * 3 + 0] = static_cast<uchar>(r);
      row[x * 3 + 1] = static_cast<uchar>(g);
      row[x * 3 + 2] = static_cast<uchar>(b);
    }
  }
  return out;
}

void fillRgbRect(QImage& img, int x0, int y0, int x1, int y1, int r, int g, int b) {
  for (int y = y0; y <= y1; ++y) {
    if (y < 0 || y >= img.height()) continue;
    uchar* row = img.scanLine(y);
    for (int x = x0; x <= x1; ++x) {
      if (x < 0 || x >= img.width()) continue;
      row[x * 3 + 0] = static_cast<uchar>(r);
      row[x * 3 + 1] = static_cast<uchar>(g);
      row[x * 3 + 2] = static_cast<uchar>(b);
    }
  }
}

double meanAbsDiff(const QImage& a, const QImage& b) {
  const QImage A = toRgb888(a);
  const QImage B = toRgb888(b);
  if (A.size() != B.size()) return 1e9;
  double s = 0;
  int n = 0;
  for (int y = 0; y < A.height(); ++y) {
    const uchar* ra = A.constScanLine(y);
    const uchar* rb = B.constScanLine(y);
    for (int x = 0; x < A.width() * 3; ++x) {
      s += std::abs(int(ra[x]) - int(rb[x]));
      ++n;
    }
  }
  return n ? s / n : 1e9;
}

}  // namespace

WarpResult runWarp(const QImage& src, const QVariantMap& params) {
  WarpResult r;
  if (src.isNull() || src.width() <= 0 || src.height() <= 0) {
    r.error = QStringLiteral("图像变换需要非空输入图像");
    return r;
  }
  QString method = params.value(QStringLiteral("method"), QStringLiteral("affine")).toString().trimmed().toLower();
  if (method == QLatin1String("unroll") || method == QLatin1String("circular") ||
      method == QLatin1String("ring") || method == QLatin1String("polar_unroll"))
    method = QStringLiteral("polar");
  if (method == QLatin1String("homography") || method == QLatin1String("projective"))
    method = QStringLiteral("perspective");
  if (method != QLatin1String("perspective") && method != QLatin1String("polar"))
    method = QStringLiteral("affine");
  r.method = method;
  const bool invert = params.value(QStringLiteral("invert"), false).toBool();
  int outW = params.value(QStringLiteral("outW"), 0).toInt();
  int outH = params.value(QStringLiteral("outH"), 0).toInt();

  if (method == QLatin1String("affine")) {
    Affine a;
    a.a[0] = params.value(QStringLiteral("a00"), 1.0).toDouble();
    a.a[1] = params.value(QStringLiteral("a01"), 0.0).toDouble();
    a.a[2] = params.value(QStringLiteral("a02"), 0.0).toDouble();
    a.a[3] = params.value(QStringLiteral("a10"), 0.0).toDouble();
    a.a[4] = params.value(QStringLiteral("a11"), 1.0).toDouble();
    a.a[5] = params.value(QStringLiteral("a12"), 0.0).toDouble();
    QPointF sp[4], dp[4];
    const int np = readPointPairs(params, sp, dp);
    if (np >= 3) {
      if (!affineFromPoints(sp, dp, np, a)) {
        r.error = QStringLiteral("仿射点对求解失败");
        return r;
      }
    }
    Affine used = a;
    if (invert && !invertAffine(a, used)) {
      r.error = QStringLiteral("仿射矩阵接近奇异，无法求逆");
      return r;
    }
    if (outW <= 0) outW = src.width();
    if (outH <= 0) outH = src.height();
    // 正向定义为输出点 = A * 输入点，采样时要从输出反查输入，故用逆。
    Affine sample;
    if (!invertAffine(used, sample)) {
      r.error = QStringLiteral("仿射矩阵接近奇异，无法映射");
      return r;
    }
    r.image = remap(src, outW, outH, [&](int x, int y, double& sx, double& sy) {
      applyAffine(sample, x, y, sx, sy);
    });
    r.outWidth = outW;
    r.outHeight = outH;
    r.ok = true;
    r.note = QStringLiteral("仿射变换 %1×%2%3").arg(outW).arg(outH).arg(
        invert ? QStringLiteral("（逆）") : QString());
    return r;
  }

  if (method == QLatin1String("perspective")) {
    Homography h;
    h.h[0] = params.value(QStringLiteral("h00"), 1.0).toDouble();
    h.h[1] = params.value(QStringLiteral("h01"), 0.0).toDouble();
    h.h[2] = params.value(QStringLiteral("h02"), 0.0).toDouble();
    h.h[3] = params.value(QStringLiteral("h10"), 0.0).toDouble();
    h.h[4] = params.value(QStringLiteral("h11"), 1.0).toDouble();
    h.h[5] = params.value(QStringLiteral("h12"), 0.0).toDouble();
    h.h[6] = params.value(QStringLiteral("h20"), 0.0).toDouble();
    h.h[7] = params.value(QStringLiteral("h21"), 0.0).toDouble();
    h.h[8] = params.value(QStringLiteral("h22"), 1.0).toDouble();
    QPointF sp[4], dp[4];
    const int np = readPointPairs(params, sp, dp);
    if (np >= 4) {
      if (!homographyFromPoints(sp, dp, np, h)) {
        r.error = QStringLiteral("透视点对求解失败");
        return r;
      }
    }
    Homography used = h;
    if (invert && !invertHomography(h, used)) {
      r.error = QStringLiteral("单应接近奇异，无法求逆");
      return r;
    }
    if (outW <= 0) outW = src.width();
    if (outH <= 0) outH = src.height();
    Homography sample;
    if (!invertHomography(used, sample)) {
      r.error = QStringLiteral("单应接近奇异，无法映射");
      return r;
    }
    r.image = remap(src, outW, outH, [&](int x, int y, double& sx, double& sy) {
      applyHomography(sample, x, y, sx, sy);
    });
    r.outWidth = outW;
    r.outHeight = outH;
    r.ok = true;
    r.note = QStringLiteral("透视变换 %1×%2%3").arg(outW).arg(outH).arg(
        invert ? QStringLiteral("（逆）") : QString());
    return r;
  }

  // polar
  const double cx = params.value(QStringLiteral("centerX"), (src.width() - 1) * 0.5).toDouble();
  const double cy = params.value(QStringLiteral("centerY"), (src.height() - 1) * 0.5).toDouble();
  double rMin = params.value(QStringLiteral("rMin"), 0.0).toDouble();
  double rMax = params.value(QStringLiteral("rMax"), 0.0).toDouble();
  if (rMax <= rMin) {
    const double dx = std::max(cx, src.width() - 1 - cx);
    const double dy = std::max(cy, src.height() - 1 - cy);
    rMax = std::sqrt(dx * dx + dy * dy);
  }
  if (rMin < 0) rMin = 0;
  const double ang0 = params.value(QStringLiteral("angleStart"), 0.0).toDouble();
  double span = params.value(QStringLiteral("angleSpan"), 360.0).toDouble();
  if (std::fabs(span) < 1e-6) span = 360.0;
  if (outW <= 0) outW = qBound(32, qRound(2.0 * M_PI * std::max(8.0, rMax)), 4096);
  if (outH <= 0) outH = qBound(8, qRound(rMax - rMin + 1.0), 4096);
  r.outWidth = outW;
  r.outHeight = outH;
  const QImage in = toRgb888(src);
  if (!invert) {
    r.image = remap(src, outW, outH, [&](int x, int y, double& sx, double& sy) {
      const double t = ang0 + (outW <= 1 ? 0.0 : static_cast<double>(x) / (outW - 1) * span);
      const double rad = rMin + (outH <= 1 ? 0.0 : static_cast<double>(y) / (outH - 1) * (rMax - rMin));
      const double th = t * M_PI / 180.0;
      sx = cx + rad * std::cos(th);
      sy = cy - rad * std::sin(th);  // 图像 y 向下，角度逆时针
    });
    r.ok = true;
    r.note = QStringLiteral("环形展开 %1×%2  r=%3..%4")
                 .arg(outW)
                 .arg(outH)
                 .arg(rMin, 0, 'f', 1)
                 .arg(rMax, 0, 'f', 1);
    return r;
  }
  // invert: 从展开图映射回直角坐标，输出默认与“展开前”同尺寸，需提供原图尺寸 outW/outH
  // 这里 src 是展开图，输出是笛卡尔图。
  int cartW = params.value(QStringLiteral("cartW"), 0).toInt();
  int cartH = params.value(QStringLiteral("cartH"), 0).toInt();
  if (cartW <= 0) cartW = qRound(2.0 * rMax + 2);
  if (cartH <= 0) cartH = qRound(2.0 * rMax + 2);
  r.image = remap(src, cartW, cartH, [&](int x, int y, double& sx, double& sy) {
    const double dx = x - cx;
    const double dy = cy - y;  // 与正向一致
    const double rad = std::hypot(dx, dy);
    double deg = std::atan2(dy, dx) * 180.0 / M_PI;
    // atan2 范围 -180..180，转到与 angleStart/span 相同的覆盖
    auto inSpan = [&](double a) {
      double t = a - ang0;
      while (t < 0) t += 360.0;
      while (t >= 360.0) t -= 360.0;
      return t;
    };
    const double t = inSpan(deg);
    if (t > std::fabs(span) + 1e-6 || rad < rMin || rad > rMax) {
      sx = sy = -1;
      return;
    }
    sx = (std::fabs(span) < 1e-6) ? 0.0 : t / span * (src.width() - 1);
    sy = (rMax - rMin < 1e-6) ? 0.0 : (rad - rMin) / (rMax - rMin) * (src.height() - 1);
  });
  r.outWidth = cartW;
  r.outHeight = cartH;
  r.ok = true;
  r.note = QStringLiteral("环形还原 %1×%2").arg(cartW).arg(cartH);
  return r;
}

QStringList warpSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const WarpResult empty = runWarp(QImage(), {{QStringLiteral("method"), QStringLiteral("affine")}});
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  QImage scene(80, 60, QImage::Format_RGB888);
  scene.fill(QColor(16, 16, 16));
  fillRgbRect(scene, 18, 12, 29, 23, 220, 40, 40);  // 12×12 红块

  // 平移 (10, 5) 再逆回去，红块应回到原位。
  const WarpResult moved = runWarp(scene, {{QStringLiteral("method"), QStringLiteral("affine")},
                                           {QStringLiteral("a00"), 1},
                                           {QStringLiteral("a01"), 0},
                                           {QStringLiteral("a02"), 10},
                                           {QStringLiteral("a10"), 0},
                                           {QStringLiteral("a11"), 1},
                                           {QStringLiteral("a12"), 5}});
  check("affine-ok", moved.ok && !moved.image.isNull(), moved.error);
  const WarpResult back = runWarp(moved.image, {{QStringLiteral("method"), QStringLiteral("affine")},
                                                {QStringLiteral("a00"), 1},
                                                {QStringLiteral("a02"), 10},
                                                {QStringLiteral("a11"), 1},
                                                {QStringLiteral("a12"), 5},
                                                {QStringLiteral("invert"), true}});
  check("affine-inv-ok", back.ok, back.error);
  if (back.ok) {
    // 平移后移出画幅的边界无法还原，只在重叠区域内比较。
    const QImage A = scene.convertToFormat(QImage::Format_RGB888);
    const QImage B = back.image.convertToFormat(QImage::Format_RGB888);
    double s = 0;
    int n = 0;
    for (int y = 0; y < 55; ++y) {
      const uchar* ra = A.constScanLine(y);
      const uchar* rb = B.constScanLine(y);
      for (int x = 0; x < 70; ++x) {
        for (int c = 0; c < 3; ++c) {
          s += std::abs(int(ra[x * 3 + c]) - int(rb[x * 3 + c]));
          ++n;
        }
      }
    }
    const double mad = n ? s / n : 1e9;
    check("affine-roundtrip", mad <= 2.5, QStringLiteral("mad=%1").arg(mad));
    const uchar* p = back.image.constScanLine(15) + 20 * 3;
    check("affine-spot", p[0] >= 180 && p[1] <= 80, QStringLiteral("rgb=%1,%2,%3").arg(p[0]).arg(p[1]).arg(p[2]));
  }

  // 3 点估计：同一平移。
  const WarpResult fromPts = runWarp(
      scene, {{QStringLiteral("method"), QStringLiteral("affine")},
              {QStringLiteral("src1X"), 0},
              {QStringLiteral("src1Y"), 0},
              {QStringLiteral("dst1X"), 10},
              {QStringLiteral("dst1Y"), 5},
              {QStringLiteral("src2X"), 10},
              {QStringLiteral("src2Y"), 0},
              {QStringLiteral("dst2X"), 20},
              {QStringLiteral("dst2Y"), 5},
              {QStringLiteral("src3X"), 0},
              {QStringLiteral("src3Y"), 10},
              {QStringLiteral("dst3X"), 10},
              {QStringLiteral("dst3Y"), 15}});
  check("affine-pts-ok", fromPts.ok, fromPts.error);
  if (fromPts.ok && moved.ok) {
    const double mad = meanAbsDiff(moved.image, fromPts.image);
    check("affine-pts-match", mad <= 1.0, QStringLiteral("mad=%1").arg(mad));
  }

  // 透视：四点把整幅图映到自己（单位单应），再做一个已知梯形并逆回。
  const WarpResult ident = runWarp(
      scene, {{QStringLiteral("method"), QStringLiteral("perspective")},
              {QStringLiteral("src1X"), 0},
              {QStringLiteral("src1Y"), 0},
              {QStringLiteral("dst1X"), 0},
              {QStringLiteral("dst1Y"), 0},
              {QStringLiteral("src2X"), 79},
              {QStringLiteral("src2Y"), 0},
              {QStringLiteral("dst2X"), 79},
              {QStringLiteral("dst2Y"), 0},
              {QStringLiteral("src3X"), 79},
              {QStringLiteral("src3Y"), 59},
              {QStringLiteral("dst3X"), 79},
              {QStringLiteral("dst3Y"), 59},
              {QStringLiteral("src4X"), 0},
              {QStringLiteral("src4Y"), 59},
              {QStringLiteral("dst4X"), 0},
              {QStringLiteral("dst4Y"), 59}});
  check("persp-ident", ident.ok && meanAbsDiff(scene, ident.image) <= 1.5,
        ident.ok ? QStringLiteral("mad=%1").arg(meanAbsDiff(scene, ident.image)) : ident.error);

  const WarpResult persp = runWarp(
      scene, {{QStringLiteral("method"), QStringLiteral("perspective")},
              {QStringLiteral("src1X"), 0},
              {QStringLiteral("src1Y"), 0},
              {QStringLiteral("dst1X"), 8},
              {QStringLiteral("dst1Y"), 4},
              {QStringLiteral("src2X"), 79},
              {QStringLiteral("src2Y"), 0},
              {QStringLiteral("dst2X"), 74},
              {QStringLiteral("dst2Y"), 6},
              {QStringLiteral("src3X"), 79},
              {QStringLiteral("src3Y"), 59},
              {QStringLiteral("dst3X"), 72},
              {QStringLiteral("dst3Y"), 56},
              {QStringLiteral("src4X"), 0},
              {QStringLiteral("src4Y"), 59},
              {QStringLiteral("dst4X"), 6},
              {QStringLiteral("dst4Y"), 54}});
  check("persp-ok", persp.ok, persp.error);
  const WarpResult perspBack = runWarp(
      persp.image, {{QStringLiteral("method"), QStringLiteral("perspective")},
                    {QStringLiteral("src1X"), 0},
                    {QStringLiteral("src1Y"), 0},
                    {QStringLiteral("dst1X"), 8},
                    {QStringLiteral("dst1Y"), 4},
                    {QStringLiteral("src2X"), 79},
                    {QStringLiteral("src2Y"), 0},
                    {QStringLiteral("dst2X"), 74},
                    {QStringLiteral("dst2Y"), 6},
                    {QStringLiteral("src3X"), 79},
                    {QStringLiteral("src3Y"), 59},
                    {QStringLiteral("dst3X"), 72},
                    {QStringLiteral("dst3Y"), 56},
                    {QStringLiteral("src4X"), 0},
                    {QStringLiteral("src4Y"), 59},
                    {QStringLiteral("dst4X"), 6},
                    {QStringLiteral("dst4Y"), 54},
                    {QStringLiteral("invert"), true}});
  check("persp-inv-ok", perspBack.ok, perspBack.error);
  if (perspBack.ok) {
    // 边缘因插值与透视会糊，只在红块内部取样。
    const uchar* p = perspBack.image.constScanLine(16) + 22 * 3;
    check("persp-roundtrip-spot", p[0] >= 150 && p[1] <= 100,
          QStringLiteral("rgb=%1,%2,%3").arg(p[0]).arg(p[1]).arg(p[2]));
    const double mad = meanAbsDiff(scene, perspBack.image);
    check("persp-roundtrip", mad <= 20.0, QStringLiteral("mad=%1").arg(mad));
  }

  // 环形展开：在半径 30、角度 0°（正右）放一个亮点，展开后应落在第一列、对应行。
  QImage ring(120, 120, QImage::Format_RGB888);
  ring.fill(QColor(8, 8, 8));
  const int rcx = 60, rcy = 60, rr = 30;
  fillRgbRect(ring, rcx + rr - 2, rcy - 2, rcx + rr + 2, rcy + 2, 240, 240, 40);
  const int outW = 180, outH = 50;
  const double rMin = 10, rMax = 50;
  const WarpResult pol = runWarp(ring, {{QStringLiteral("method"), QStringLiteral("polar")},
                                        {QStringLiteral("centerX"), rcx},
                                        {QStringLiteral("centerY"), rcy},
                                        {QStringLiteral("rMin"), rMin},
                                        {QStringLiteral("rMax"), rMax},
                                        {QStringLiteral("angleStart"), 0},
                                        {QStringLiteral("angleSpan"), 360},
                                        {QStringLiteral("outW"), outW},
                                        {QStringLiteral("outH"), outH}});
  check("polar-ok", pol.ok && pol.image.width() == outW && pol.image.height() == outH, pol.error);
  if (pol.ok) {
    const int expectY = qRound((rr - rMin) / (rMax - rMin) * (outH - 1));
    int bestX = 0, bestY = 0, best = -1;
    for (int y = 0; y < outH; ++y) {
      const uchar* row = pol.image.constScanLine(y);
      for (int x = 0; x < outW; ++x) {
        const int v = row[x * 3 + 0] + row[x * 3 + 1];
        if (v > best) {
          best = v;
          bestX = x;
          bestY = y;
        }
      }
    }
    check("polar-angle0", bestX <= 6 || bestX >= outW - 6,
          QStringLiteral("peak=(%1,%2) v=%3").arg(bestX).arg(bestY).arg(best));
    check("polar-radius", std::abs(bestY - expectY) <= 3,
          QStringLiteral("y=%1 expect=%2").arg(bestY).arg(expectY));
  }

  // 奇异仿射应失败。
  const WarpResult singular = runWarp(scene, {{QStringLiteral("method"), QStringLiteral("affine")},
                                              {QStringLiteral("a00"), 0},
                                              {QStringLiteral("a01"), 0},
                                              {QStringLiteral("a10"), 0},
                                              {QStringLiteral("a11"), 0}});
  check("singular-fail", !singular.ok && !singular.error.isEmpty(), singular.error);

  return fails;
}

}  // namespace sieans_qt
