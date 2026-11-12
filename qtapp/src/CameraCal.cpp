#include "CameraCal.hpp"

#include "RegionAnalyze.hpp"

#include <QColor>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <vector>

namespace sieans_qt {
namespace {

constexpr double kPi = 3.14159265358979323846;

struct Vec3 {
  double x = 0, y = 0, z = 0;
};

struct Mat3 {
  double m[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
  double operator()(int r, int c) const { return m[r * 3 + c]; }
  double& operator()(int r, int c) { return m[r * 3 + c]; }
};

/** 3×3 矩阵乘。 */
Mat3 mul3(const Mat3& a, const Mat3& b) {
  Mat3 c;
  for (int r = 0; r < 3; ++r)
    for (int col = 0; col < 3; ++col)
      c(r, col) = a(r, 0) * b(0, col) + a(r, 1) * b(1, col) + a(r, 2) * b(2, col);
  return c;
}

Vec3 mul3v(const Mat3& a, const Vec3& v) {
  return Vec3{a(0, 0) * v.x + a(0, 1) * v.y + a(0, 2) * v.z,
              a(1, 0) * v.x + a(1, 1) * v.y + a(1, 2) * v.z,
              a(2, 0) * v.x + a(2, 1) * v.y + a(2, 2) * v.z};
}

/** 高斯消元求解 n×n 线性方程组 Ax=b，失败返回 false。 */
bool solveLinear(std::vector<double> a, std::vector<double> b, int n, std::vector<double>& x) {
  x.assign(static_cast<size_t>(n), 0.0);
  if (n <= 0) return false;
  for (int k = 0; k < n; ++k) {
    int piv = k;
    double best = std::fabs(a[k * n + k]);
    for (int i = k + 1; i < n; ++i) {
      const double v = std::fabs(a[i * n + k]);
      if (v > best) {
        best = v;
        piv = i;
      }
    }
    if (best < 1e-14) return false;
    if (piv != k) {
      for (int j = k; j < n; ++j) std::swap(a[k * n + j], a[piv * n + j]);
      std::swap(b[k], b[piv]);
    }
    const double diag = a[k * n + k];
    for (int i = k + 1; i < n; ++i) {
      const double f = a[i * n + k] / diag;
      b[i] -= f * b[k];
      for (int j = k; j < n; ++j) a[i * n + j] -= f * a[k * n + j];
    }
  }
  for (int i = n - 1; i >= 0; --i) {
    double s = b[i];
    for (int j = i + 1; j < n; ++j) s -= a[i * n + j] * x[static_cast<size_t>(j)];
    const double diag = a[i * n + i];
    if (std::fabs(diag) < 1e-14) return false;
    x[static_cast<size_t>(i)] = s / diag;
  }
  return true;
}

/** 对称矩阵 Jacobi 特征值分解，V 按列存特征向量。 */
bool jacobiEigen(const std::vector<double>& aIn, int n, std::vector<double>& eig,
                 std::vector<double>& vOut) {
  if (n <= 0) return false;
  std::vector<double> a = aIn;
  vOut.assign(static_cast<size_t>(n * n), 0.0);
  eig.assign(static_cast<size_t>(n), 0.0);
  for (int i = 0; i < n; ++i) vOut[static_cast<size_t>(i * n + i)] = 1.0;
  for (int iter = 0; iter < 40 * n * n; ++iter) {
    int p = 0, q = 1;
    double mx = 0.0;
    for (int i = 0; i < n; ++i)
      for (int j = i + 1; j < n; ++j) {
        const double v = std::fabs(a[i * n + j]);
        if (v > mx) {
          mx = v;
          p = i;
          q = j;
        }
      }
    if (mx < 1e-15) break;
    const double app = a[p * n + p];
    const double aqq = a[q * n + q];
    const double apq = a[p * n + q];
    const double tau = (aqq - app) / (2.0 * apq);
    const double t = (tau >= 0 ? 1.0 : -1.0) / (std::fabs(tau) + std::sqrt(1.0 + tau * tau));
    const double c = 1.0 / std::sqrt(1.0 + t * t);
    const double s = t * c;
    for (int k = 0; k < n; ++k) {
      if (k == p || k == q) continue;
      const double akp = a[k * n + p];
      const double akq = a[k * n + q];
      a[k * n + p] = a[p * n + k] = c * akp - s * akq;
      a[k * n + q] = a[q * n + k] = s * akp + c * akq;
    }
    a[p * n + p] = app - t * apq;
    a[q * n + q] = aqq + t * apq;
    a[p * n + q] = a[q * n + p] = 0.0;
    for (int k = 0; k < n; ++k) {
      const double vkp = vOut[static_cast<size_t>(k * n + p)];
      const double vkq = vOut[static_cast<size_t>(k * n + q)];
      vOut[static_cast<size_t>(k * n + p)] = c * vkp - s * vkq;
      vOut[static_cast<size_t>(k * n + q)] = s * vkp + c * vkq;
    }
  }
  for (int i = 0; i < n; ++i) eig[static_cast<size_t>(i)] = a[i * n + i];
  return true;
}

/** 取对称矩阵绝对值最小特征值对应的特征向量。 */
bool smallestEigenvec(const std::vector<double>& ata, int n, std::vector<double>& vec) {
  std::vector<double> eig, v;
  if (!jacobiEigen(ata, n, eig, v)) return false;
  int best = 0;
  for (int i = 1; i < n; ++i)
    if (std::fabs(eig[static_cast<size_t>(i)]) < std::fabs(eig[static_cast<size_t>(best)])) best = i;
  vec.resize(static_cast<size_t>(n));
  for (int i = 0; i < n; ++i) vec[static_cast<size_t>(i)] = v[static_cast<size_t>(i * n + best)];
  return true;
}

struct Homography {
  Mat3 h;
  bool ok = false;
};

/** 用 Hartley 归一化后的 DLT 估计平面单应。 */
Homography estimateHomography(const QVector<QPointF>& obj, const QVector<QPointF>& img) {
  Homography out;
  const int n = std::min(obj.size(), img.size());
  if (n < 4) return out;
  auto normalize = [](const QVector<QPointF>& pts, int n, QPointF& iso, double& scale, Mat3& t) {
    double sx = 0, sy = 0;
    for (int i = 0; i < n; ++i) {
      sx += pts[i].x();
      sy += pts[i].y();
    }
    iso = QPointF(sx / n, sy / n);
    double mean = 0;
    for (int i = 0; i < n; ++i) mean += std::hypot(pts[i].x() - iso.x(), pts[i].y() - iso.y());
    mean /= n;
    scale = (mean > 1e-9) ? (std::sqrt(2.0) / mean) : 1.0;
    t(0, 0) = scale;
    t(0, 1) = 0;
    t(0, 2) = -scale * iso.x();
    t(1, 0) = 0;
    t(1, 1) = scale;
    t(1, 2) = -scale * iso.y();
    t(2, 0) = 0;
    t(2, 1) = 0;
    t(2, 2) = 1;
  };
  QPointF oIso, iIso;
  double oS = 1, iS = 1;
  Mat3 tObj, tImg;
  normalize(obj, n, oIso, oS, tObj);
  normalize(img, n, iIso, iS, tImg);
  std::vector<double> ata(81, 0.0);
  for (int i = 0; i < n; ++i) {
    const double x = oS * (obj[i].x() - oIso.x());
    const double y = oS * (obj[i].y() - oIso.y());
    const double u = iS * (img[i].x() - iIso.x());
    const double v = iS * (img[i].y() - iIso.y());
    const double r1[9] = {x, y, 1, 0, 0, 0, -u * x, -u * y, -u};
    const double r2[9] = {0, 0, 0, x, y, 1, -v * x, -v * y, -v};
    for (int a = 0; a < 9; ++a)
      for (int b = 0; b < 9; ++b) {
        ata[static_cast<size_t>(a * 9 + b)] += r1[a] * r1[b] + r2[a] * r2[b];
      }
  }
  std::vector<double> hv;
  if (!smallestEigenvec(ata, 9, hv)) return out;
  Mat3 hn;
  for (int i = 0; i < 9; ++i) hn.m[i] = hv[static_cast<size_t>(i)];
  if (std::fabs(hn(2, 2)) > 1e-15) {
    for (int i = 0; i < 9; ++i) hn.m[i] /= hn(2, 2);
  }
  // H = Timg^{-1} * Hn * Tobj
  Mat3 tImgInv;
  tImgInv(0, 0) = 1.0 / iS;
  tImgInv(0, 2) = iIso.x();
  tImgInv(1, 1) = 1.0 / iS;
  tImgInv(1, 2) = iIso.y();
  out.h = mul3(mul3(tImgInv, hn), tObj);
  if (std::fabs(out.h(2, 2)) > 1e-15) {
    for (int i = 0; i < 9; ++i) out.h.m[i] /= out.h(2, 2);
  }
  out.ok = std::isfinite(out.h(0, 0)) && std::isfinite(out.h(2, 2));
  return out;
}

/** Rodrigues 向量转旋转矩阵。 */
Mat3 rodrigues(const Vec3& r) {
  const double th = std::sqrt(r.x * r.x + r.y * r.y + r.z * r.z);
  Mat3 R;
  if (th < 1e-12) {
    R(0, 1) = -r.z;
    R(0, 2) = r.y;
    R(1, 0) = r.z;
    R(1, 2) = -r.x;
    R(2, 0) = -r.y;
    R(2, 1) = r.x;
    return R;
  }
  const double c = std::cos(th);
  const double s = std::sin(th);
  const double kx = r.x / th, ky = r.y / th, kz = r.z / th;
  // R = I c + (1-c) kk^T + s [k]_x
  R(0, 0) = c + (1 - c) * kx * kx;
  R(0, 1) = (1 - c) * kx * ky - s * kz;
  R(0, 2) = (1 - c) * kx * kz + s * ky;
  R(1, 0) = (1 - c) * ky * kx + s * kz;
  R(1, 1) = c + (1 - c) * ky * ky;
  R(1, 2) = (1 - c) * ky * kz - s * kx;
  R(2, 0) = (1 - c) * kz * kx - s * ky;
  R(2, 1) = (1 - c) * kz * ky + s * kx;
  R(2, 2) = c + (1 - c) * kz * kz;
  return R;
}

/** 旋转矩阵转 Rodrigues 向量。 */
Vec3 rodriguesInv(const Mat3& R) {
  const double tr = R(0, 0) + R(1, 1) + R(2, 2);
  const double c = std::max(-1.0, std::min(1.0, (tr - 1.0) * 0.5));
  const double th = std::acos(c);
  const double s = std::sin(th);
  if (th < 1e-12) return Vec3{0, 0, 0};
  if (s < 1e-8) {
    // 接近 π，用对角近似
    return Vec3{std::sqrt(std::max(0.0, (R(0, 0) + 1) * 0.5)) * th,
                std::sqrt(std::max(0.0, (R(1, 1) + 1) * 0.5)) * th,
                std::sqrt(std::max(0.0, (R(2, 2) + 1) * 0.5)) * th};
  }
  const double k = th / (2.0 * s);
  return Vec3{k * (R(2, 1) - R(1, 2)), k * (R(0, 2) - R(2, 0)), k * (R(1, 0) - R(0, 1))};
}

/** 把归一化平面上的点按 k1、k2 径向畸变后再投影到像素。 */
void projectPoint(const CameraIntrinsics& k, const Mat3& R, const Vec3& t, const QPointF& obj,
                  double& u, double& v) {
  const Vec3 pw{obj.x(), obj.y(), 0};
  const Vec3 pc{R(0, 0) * pw.x + R(0, 1) * pw.y + R(0, 2) * pw.z + t.x,
                R(1, 0) * pw.x + R(1, 1) * pw.y + R(1, 2) * pw.z + t.y,
                R(2, 0) * pw.x + R(2, 1) * pw.y + R(2, 2) * pw.z + t.z};
  if (std::fabs(pc.z) < 1e-12) {
    u = k.cx;
    v = k.cy;
    return;
  }
  const double x = pc.x / pc.z;
  const double y = pc.y / pc.z;
  const double r2 = x * x + y * y;
  const double s = 1.0 + k.k1 * r2 + k.k2 * r2 * r2;
  u = k.fx * x * s + k.cx;
  v = k.fy * y * s + k.cy;
}

/** 迭代求径向畸变的逆（切向为 0）。 */
void undistortNormalized(double xd, double yd, double k1, double k2, double& x, double& y) {
  x = xd;
  y = yd;
  for (int i = 0; i < 12; ++i) {
    const double r2 = x * x + y * y;
    const double s = 1.0 + k1 * r2 + k2 * r2 * r2;
    if (std::fabs(s) < 1e-12) break;
    x = xd / s;
    y = yd / s;
  }
}

/** 从单应与内参分解 R、t；对旋转做极分解正交化。 */
bool poseFromHomography(const Mat3& H, const CameraIntrinsics& k, Mat3& R, Vec3& t) {
  if (k.fx < 1e-6 || k.fy < 1e-6) return false;
  Mat3 kinv;
  kinv(0, 0) = 1.0 / k.fx;
  kinv(0, 2) = -k.cx / k.fx;
  kinv(1, 1) = 1.0 / k.fy;
  kinv(1, 2) = -k.cy / k.fy;
  const Mat3 kh = mul3(kinv, H);
  auto col = [&](int c) { return Vec3{kh(0, c), kh(1, c), kh(2, c)}; };
  const Vec3 h1 = col(0);
  const Vec3 h2 = col(1);
  const Vec3 h3 = col(2);
  const double n1 = std::sqrt(h1.x * h1.x + h1.y * h1.y + h1.z * h1.z);
  const double n2 = std::sqrt(h2.x * h2.x + h2.y * h2.y + h2.z * h2.z);
  const double lam = 1.0 / ((n1 + n2) * 0.5);
  auto scale = [&](const Vec3& v) { return Vec3{lam * v.x, lam * v.y, lam * v.z}; };
  Vec3 r1 = scale(h1);
  Vec3 r2 = scale(h2);
  Vec3 r3{r1.y * r2.z - r1.z * r2.y, r1.z * r2.x - r1.x * r2.z, r1.x * r2.y - r1.y * r2.x};
  t = scale(h3);
  // 若相机在靶标背面则翻转
  if (t.z < 0) {
    r1 = Vec3{-r1.x, -r1.y, -r1.z};
    r2 = Vec3{-r2.x, -r2.y, -r2.z};
    r3 = Vec3{-r3.x, -r3.y, -r3.z};
    t = Vec3{-t.x, -t.y, -t.z};
  }
  // SVD/极分解：用行正交化近似
  auto norm = [](Vec3& v) {
    const double n = std::sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
    if (n < 1e-12) return false;
    v.x /= n;
    v.y /= n;
    v.z /= n;
    return true;
  };
  if (!norm(r1)) return false;
  r2 = Vec3{r2.x - r1.x * (r1.x * r2.x + r1.y * r2.y + r1.z * r2.z),
            r2.y - r1.y * (r1.x * r2.x + r1.y * r2.y + r1.z * r2.z),
            r2.z - r1.z * (r1.x * r2.x + r1.y * r2.y + r1.z * r2.z)};
  if (!norm(r2)) return false;
  r3 = Vec3{r1.y * r2.z - r1.z * r2.y, r1.z * r2.x - r1.x * r2.z, r1.x * r2.y - r1.y * r2.x};
  R(0, 0) = r1.x;
  R(1, 0) = r1.y;
  R(2, 0) = r1.z;
  R(0, 1) = r2.x;
  R(1, 1) = r2.y;
  R(2, 1) = r2.z;
  R(0, 2) = r3.x;
  R(1, 2) = r3.y;
  R(2, 2) = r3.z;
  return std::isfinite(t.z) && std::fabs(t.z) > 1e-9;
}

struct CalibView {
  QVector<QPointF> object;
  QVector<QPointF> image;
  Mat3 R;
  Vec3 t;
  Vec3 rvec;
};

double reprojectionRmse(const CameraIntrinsics& k, const std::vector<CalibView>& views) {
  double ss = 0;
  int n = 0;
  for (const CalibView& v : views) {
    const int m = std::min(v.object.size(), v.image.size());
    for (int i = 0; i < m; ++i) {
      double u = 0, vv = 0;
      projectPoint(k, v.R, v.t, v.object[i], u, vv);
      const double du = u - v.image[i].x();
      const double dv = vv - v.image[i].y();
      ss += du * du + dv * dv;
      ++n;
    }
  }
  return n ? std::sqrt(ss / n) : 0.0;
}

/** 用数值雅可比的阻尼高斯-牛顿 refined 内参与各视图位姿。 */
bool refineCalibration(CameraIntrinsics& k, std::vector<CalibView>& views, int maxIter = 25) {
  const int nViews = static_cast<int>(views.size());
  if (nViews <= 0) return false;
  const int nParam = 6 + 6 * nViews;  // fx fy cx cy k1 k2 + 6 per view
  auto pack = [&](std::vector<double>& p) {
    p.assign(static_cast<size_t>(nParam), 0.0);
    p[0] = k.fx;
    p[1] = k.fy;
    p[2] = k.cx;
    p[3] = k.cy;
    p[4] = k.k1;
    p[5] = k.k2;
    for (int i = 0; i < nViews; ++i) {
      p[static_cast<size_t>(6 + 6 * i + 0)] = views[static_cast<size_t>(i)].rvec.x;
      p[static_cast<size_t>(6 + 6 * i + 1)] = views[static_cast<size_t>(i)].rvec.y;
      p[static_cast<size_t>(6 + 6 * i + 2)] = views[static_cast<size_t>(i)].rvec.z;
      p[static_cast<size_t>(6 + 6 * i + 3)] = views[static_cast<size_t>(i)].t.x;
      p[static_cast<size_t>(6 + 6 * i + 4)] = views[static_cast<size_t>(i)].t.y;
      p[static_cast<size_t>(6 + 6 * i + 5)] = views[static_cast<size_t>(i)].t.z;
    }
  };
  auto unpack = [&](const std::vector<double>& p) {
    k.fx = p[0];
    k.fy = p[1];
    k.cx = p[2];
    k.cy = p[3];
    k.k1 = p[4];
    k.k2 = p[5];
    for (int i = 0; i < nViews; ++i) {
      auto& v = views[static_cast<size_t>(i)];
      v.rvec = Vec3{p[static_cast<size_t>(6 + 6 * i + 0)], p[static_cast<size_t>(6 + 6 * i + 1)],
                    p[static_cast<size_t>(6 + 6 * i + 2)]};
      v.t = Vec3{p[static_cast<size_t>(6 + 6 * i + 3)], p[static_cast<size_t>(6 + 6 * i + 4)],
                 p[static_cast<size_t>(6 + 6 * i + 5)]};
      v.R = rodrigues(v.rvec);
    }
  };
  auto residuals = [&](const std::vector<double>& p, std::vector<double>& r) {
    CameraIntrinsics kk = k;
    std::vector<CalibView> vv = views;
    // temporary unpack
    kk.fx = p[0];
    kk.fy = p[1];
    kk.cx = p[2];
    kk.cy = p[3];
    kk.k1 = p[4];
    kk.k2 = p[5];
    r.clear();
    for (int i = 0; i < nViews; ++i) {
      const Vec3 rvec{p[static_cast<size_t>(6 + 6 * i + 0)], p[static_cast<size_t>(6 + 6 * i + 1)],
                      p[static_cast<size_t>(6 + 6 * i + 2)]};
      const Vec3 t{p[static_cast<size_t>(6 + 6 * i + 3)], p[static_cast<size_t>(6 + 6 * i + 4)],
                   p[static_cast<size_t>(6 + 6 * i + 5)]};
      const Mat3 R = rodrigues(rvec);
      const auto& view = views[static_cast<size_t>(i)];
      const int m = std::min(view.object.size(), view.image.size());
      for (int j = 0; j < m; ++j) {
        double u = 0, vv2 = 0;
        projectPoint(kk, R, t, view.object[j], u, vv2);
        r.push_back(u - view.image[j].x());
        r.push_back(vv2 - view.image[j].y());
      }
    }
  };

  std::vector<double> p;
  pack(p);
  double lambda = 1e-3;
  std::vector<double> r0;
  residuals(p, r0);
  auto rss = [](const std::vector<double>& r) {
    double s = 0;
    for (double v : r) s += v * v;
    return s;
  };
  double best = rss(r0);
  const int nRes = static_cast<int>(r0.size());
  if (nRes < nParam) return false;
  for (int it = 0; it < maxIter; ++it) {
    std::vector<double> J(static_cast<size_t>(nRes * nParam), 0.0);
    for (int j = 0; j < nParam; ++j) {
      std::vector<double> p2 = p;
      const double eps = std::max(1e-7, 1e-6 * std::fabs(p2[static_cast<size_t>(j)]));
      p2[static_cast<size_t>(j)] += eps;
      std::vector<double> r2;
      residuals(p2, r2);
      if (static_cast<int>(r2.size()) != nRes) return false;
      for (int i = 0; i < nRes; ++i)
        J[static_cast<size_t>(i * nParam + j)] = (r2[static_cast<size_t>(i)] - r0[static_cast<size_t>(i)]) / eps;
    }
    std::vector<double> jtJ(static_cast<size_t>(nParam * nParam), 0.0);
    std::vector<double> jtr(static_cast<size_t>(nParam), 0.0);
    for (int i = 0; i < nRes; ++i) {
      for (int a = 0; a < nParam; ++a) {
        const double jia = J[static_cast<size_t>(i * nParam + a)];
        jtr[static_cast<size_t>(a)] += jia * r0[static_cast<size_t>(i)];
        for (int b = 0; b < nParam; ++b)
          jtJ[static_cast<size_t>(a * nParam + b)] += jia * J[static_cast<size_t>(i * nParam + b)];
      }
    }
    bool stepped = false;
    for (int attempt = 0; attempt < 8 && !stepped; ++attempt) {
      std::vector<double> A = jtJ;
      for (int i = 0; i < nParam; ++i) A[static_cast<size_t>(i * nParam + i)] += lambda;
      std::vector<double> dp;
      // 解 JtJ dp = -Jt r
      std::vector<double> rhs(static_cast<size_t>(nParam), 0.0);
      for (int i = 0; i < nParam; ++i) rhs[static_cast<size_t>(i)] = -jtr[static_cast<size_t>(i)];
      if (!solveLinear(A, rhs, nParam, dp)) {
        lambda *= 8.0;
        continue;
      }
      std::vector<double> pNew = p;
      for (int i = 0; i < nParam; ++i) pNew[static_cast<size_t>(i)] += dp[static_cast<size_t>(i)];
      if (pNew[0] < 1.0 || pNew[1] < 1.0) {
        lambda *= 8.0;
        continue;
      }
      std::vector<double> rNew;
      residuals(pNew, rNew);
      const double sNew = rss(rNew);
      if (sNew < best && rNew.size() == r0.size()) {
        p.swap(pNew);
        r0.swap(rNew);
        best = sNew;
        lambda = std::max(1e-9, lambda * 0.3);
        stepped = true;
      } else {
        lambda *= 6.0;
      }
    }
    if (!stepped) break;
    if (best / std::max(1, nRes) < 1e-8) break;
  }
  unpack(p);
  return std::isfinite(k.fx) && k.fx > 1.0 && k.fy > 1.0;
}

/** 把点按 PCA 主轴排成 rows×cols 行主序网格。失败返回空。 */
QVector<QPointF> orderGrid(QVector<QPointF> pts, int rows, int cols) {
  const int need = rows * cols;
  if (pts.size() != need || rows <= 0 || cols <= 0) return {};
  double mx = 0, my = 0;
  for (const QPointF& p : pts) {
    mx += p.x();
    my += p.y();
  }
  mx /= need;
  my /= need;
  double xx = 0, yy = 0, xy = 0;
  for (const QPointF& p : pts) {
    const double dx = p.x() - mx;
    const double dy = p.y() - my;
    xx += dx * dx;
    yy += dy * dy;
    xy += dx * dy;
  }
  const double half = 0.5 * (xx + yy);
  const double gap = std::sqrt(std::max(0.0, 0.25 * (xx - yy) * (xx - yy) + xy * xy));
  // 主轴（较大特征值）
  const double l1 = half + gap;
  QPointF a1 = (std::fabs(xy) > 1e-9 || std::fabs(l1 - yy) > 1e-9)
                   ? QPointF(l1 - yy, xy)
                   : QPointF(1, 0);
  const double n1 = std::hypot(a1.x(), a1.y());
  if (n1 < 1e-12) a1 = QPointF(1, 0);
  else a1 = QPointF(a1.x() / n1, a1.y() / n1);
  QPointF a2(-a1.y(), a1.x());  // 次轴
  auto project = [&](const QPointF& p) {
    const double dx = p.x() - mx, dy = p.y() - my;
    return QPointF(dx * a1.x() + dy * a1.y(), dx * a2.x() + dy * a2.y());
  };
  auto tryOrder = [&](int rN, int cN, const QPointF& ax, const QPointF& ay) -> QVector<QPointF> {
    struct Node {
      QPointF p, q;
    };
    QVector<Node> nodes;
    nodes.reserve(need);
    for (const QPointF& p : pts) {
      const double dx = p.x() - mx, dy = p.y() - my;
      nodes.push_back(Node{p, QPointF(dx * ax.x() + dy * ax.y(), dx * ay.x() + dy * ay.y())});
    }
    std::sort(nodes.begin(), nodes.end(),
              [](const Node& a, const Node& b) { return a.q.y() < b.q.y(); });
    QVector<QPointF> out;
    out.reserve(need);
    for (int r = 0; r < rN; ++r) {
      QVector<Node> row;
      for (int c = 0; c < cN; ++c) row.push_back(nodes[r * cN + c]);
      std::sort(row.begin(), row.end(),
                [](const Node& a, const Node& b) { return a.q.x() < b.q.x(); });
      // 行内 x 应单调且间距相近，否则视为分组失败
      QVector<double> gaps;
      for (int c = 1; c < cN; ++c) {
        const double g = row[c].q.x() - row[c - 1].q.x();
        if (g <= 1e-6) return {};
        gaps.push_back(g);
      }
      if (!gaps.isEmpty()) {
        std::sort(gaps.begin(), gaps.end());
        const double med = gaps[gaps.size() / 2];
        for (double g : gaps)
          if (g < 0.35 * med || g > 2.8 * med) return {};
      }
      for (const Node& nd : row) out.push_back(nd.p);
    }
    return out;
  };
  // 主轴对应列方向（cols 个点）
  QVector<QPointF> a = tryOrder(rows, cols, a1, a2);
  if (!a.isEmpty()) return a;
  a = tryOrder(rows, cols, a1, QPointF(-a2.x(), -a2.y()));
  if (!a.isEmpty()) return a;
  a = tryOrder(rows, cols, QPointF(-a1.x(), -a1.y()), a2);
  if (!a.isEmpty()) return a;
  a = tryOrder(rows, cols, QPointF(-a1.x(), -a1.y()), QPointF(-a2.x(), -a2.y()));
  if (!a.isEmpty()) return a;
  // 交换行列再试（靶标旋转 90°）
  if (rows != cols) {
    a = tryOrder(cols, rows, a2, a1);
    if (!a.isEmpty()) return {};  // 行列与用户声明不符，宁可不排
  }
  return {};
}

QImage toGray8(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_Grayscale8);
}

/** 在灰度图上找棋盘格内角点：对角象限差 + 非极大值抑制。 */
QVector<QPointF> detectCheckerboard(const QImage& gray, int rows, int cols) {
  const int need = rows * cols;
  if (gray.isNull() || need <= 0) return {};
  const int w = gray.width();
  const int h = gray.height();
  const int half = qBound(2, std::min(w, h) / std::max(8, std::max(rows, cols) * 2), 10);
  std::vector<float> score(static_cast<size_t>(w * h), 0.0f);
  float smax = 0;
  for (int y = half; y < h - half; ++y) {
    for (int x = half; x < w - half; ++x) {
      double m1 = 0, m2 = 0;
      int n1 = 0, n2 = 0;
      for (int dy = -half; dy <= half; ++dy) {
        const uchar* row = gray.constScanLine(y + dy);
        for (int dx = -half; dx <= half; ++dx) {
          if (dx == 0 || dy == 0) continue;
          const int val = row[x + dx];
          if (dx * dy > 0) {
            m1 += val;
            ++n1;
          } else {
            m2 += val;
            ++n2;
          }
        }
      }
      if (n1 == 0 || n2 == 0) continue;
      m1 /= n1;
      m2 /= n2;
      const float sc = static_cast<float>(std::fabs(m1 - m2));
      // 两个对角应分别偏亮/偏暗
      if (sc < 25.0f) continue;
      score[static_cast<size_t>(y * w + x)] = sc;
      if (sc > smax) smax = sc;
    }
  }
  if (smax < 25.0f) return {};
  const float thr = smax * 0.45f;
  const int rad = std::max(2, half);
  QVector<QPointF> cand;
  for (int y = half; y < h - half; ++y) {
    for (int x = half; x < w - half; ++x) {
      const float sc = score[static_cast<size_t>(y * w + x)];
      if (sc < thr) continue;
      bool peak = true;
      for (int dy = -rad; dy <= rad && peak; ++dy)
        for (int dx = -rad; dx <= rad; ++dx) {
          if (dx == 0 && dy == 0) continue;
          const int nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          if (score[static_cast<size_t>(ny * w + nx)] > sc) {
            peak = false;
            break;
          }
        }
      if (!peak) continue;
      // 3×3 加权亚像素
      double sw = 0, sx = 0, sy = 0;
      for (int dy = -1; dy <= 1; ++dy)
        for (int dx = -1; dx <= 1; ++dx) {
          const float s = score[static_cast<size_t>((y + dy) * w + (x + dx))];
          sw += s;
          sx += s * (x + dx);
          sy += s * (y + dy);
        }
      if (sw > 1e-6) cand.push_back(QPointF(sx / sw, sy / sw));
      else cand.push_back(QPointF(x, y));
    }
  }
  if (cand.size() < need) return {};
  if (cand.size() > need) {
    // 保留得分最高的 need 个（用最近整数坐标的 score）
    std::sort(cand.begin(), cand.end(), [&](const QPointF& a, const QPointF& b) {
      const int ia = qBound(0, qRound(a.y()), h - 1) * w + qBound(0, qRound(a.x()), w - 1);
      const int ib = qBound(0, qRound(b.y()), h - 1) * w + qBound(0, qRound(b.x()), w - 1);
      return score[static_cast<size_t>(ia)] > score[static_cast<size_t>(ib)];
    });
    cand.resize(need);
  }
  return orderGrid(cand, rows, cols);
}

/** 用区域分析提取高圆度斑点，作为圆点阵列的圆心。 */
QVector<QPointF> detectCircleGrid(const QImage& src, int rows, int cols) {
  const int need = rows * cols;
  if (src.isNull() || need <= 0) return {};
  auto attempt = [&](bool invert, int minArea) -> QVector<QPointF> {
    QVariantMap p;
    p.insert(QStringLiteral("method"), QStringLiteral("otsu"));
    p.insert(QStringLiteral("invert"), invert);
    p.insert(QStringLiteral("minArea"), minArea);
    p.insert(QStringLiteral("minCircularity"), 0.55);
    p.insert(QStringLiteral("maxCount"), need * 4);
    const RegionResult rr = runRegionAnalyze(src, p);
    if (!rr.ok || rr.items.size() < need) return {};
    QVector<RegionBlob> blobs = rr.items;
    if (blobs.size() > need) {
      // 面积接近中位数的 need 个
      std::sort(blobs.begin(), blobs.end(),
                [](const RegionBlob& a, const RegionBlob& b) { return a.areaPixels < b.areaPixels; });
      const int mid = blobs[blobs.size() / 2].areaPixels;
      std::sort(blobs.begin(), blobs.end(), [&](const RegionBlob& a, const RegionBlob& b) {
        return std::abs(a.areaPixels - mid) < std::abs(b.areaPixels - mid);
      });
      blobs.resize(need);
    }
    if (blobs.size() != need) return {};
    QVector<QPointF> pts;
    pts.reserve(need);
    for (const RegionBlob& b : blobs) pts.push_back(b.centroid);
    return orderGrid(pts, rows, cols);
  };
  const int areaHint = std::max(8, src.width() * src.height() / (need * 40));
  QVector<QPointF> a = attempt(true, areaHint);
  if (!a.isEmpty()) return a;
  a = attempt(false, areaHint);
  if (!a.isEmpty()) return a;
  a = attempt(true, 8);
  if (!a.isEmpty()) return a;
  return attempt(false, 8);
}

QVector<QPointF> objectGrid(int rows, int cols, double square) {
  QVector<QPointF> o;
  o.reserve(rows * cols);
  for (int r = 0; r < rows; ++r)
    for (int c = 0; c < cols; ++c) o.push_back(QPointF(c * square, r * square));
  return o;
}

/** 双线性采样灰度或 RGB888。 */
QRgb sampleBilinear(const QImage& img, double x, double y) {
  const int w = img.width();
  const int h = img.height();
  if (x < 0 || y < 0 || x >= w - 1 || y >= h - 1) return qRgb(0, 0, 0);
  const int x0 = static_cast<int>(std::floor(x));
  const int y0 = static_cast<int>(std::floor(y));
  const double tx = x - x0;
  const double ty = y - y0;
  auto px = [&](int ix, int iy) -> QRgb {
    if (img.format() == QImage::Format_Grayscale8) {
      const int g = img.constScanLine(iy)[ix];
      return qRgb(g, g, g);
    }
    const QImage rgb = (img.format() == QImage::Format_RGB888) ? img : img.convertToFormat(QImage::Format_RGB888);
    // 若转换发生则效率差；调用方应先转 RGB888
    const uchar* p = rgb.constScanLine(iy) + ix * 3;
    return qRgb(p[0], p[1], p[2]);
  };
  // 上面 px 在非 RGB888 时每像素都 convert，下面先假定已是 RGB888 或灰度
  if (img.format() == QImage::Format_Grayscale8) {
    auto g = [&](int ix, int iy) { return img.constScanLine(iy)[ix]; };
    const double v = (1 - tx) * (1 - ty) * g(x0, y0) + tx * (1 - ty) * g(x0 + 1, y0) +
                     (1 - tx) * ty * g(x0, y0 + 1) + tx * ty * g(x0 + 1, y0 + 1);
    const int gi = qBound(0, qRound(v), 255);
    return qRgb(gi, gi, gi);
  }
  auto ch = [&](int ix, int iy, int c) { return img.constScanLine(iy)[ix * 3 + c]; };
  int out[3];
  for (int c = 0; c < 3; ++c) {
    const double v = (1 - tx) * (1 - ty) * ch(x0, y0, c) + tx * (1 - ty) * ch(x0 + 1, y0, c) +
                     (1 - tx) * ty * ch(x0, y0 + 1, c) + tx * ty * ch(x0 + 1, y0 + 1, c);
    out[c] = qBound(0, qRound(v), 255);
  }
  return qRgb(out[0], out[1], out[2]);
}

/** 按针孔+径向模型反向映射去畸变，输出与输入同尺寸。 */
QImage undistortImage(const QImage& src, const CameraIntrinsics& k) {
  if (src.isNull() || k.fx < 1e-6 || k.fy < 1e-6) return {};
  const QImage in = (src.format() == QImage::Format_Grayscale8)
                        ? src
                        : src.convertToFormat(QImage::Format_RGB888);
  QImage out(in.size(), in.format());
  out.fill(0);
  const int w = in.width();
  const int h = in.height();
  for (int y = 0; y < h; ++y) {
    uchar* row = out.scanLine(y);
    for (int x = 0; x < w; ++x) {
      const double xn = (x - k.cx) / k.fx;
      const double yn = (y - k.cy) / k.fy;
      const double r2 = xn * xn + yn * yn;
      const double s = 1.0 + k.k1 * r2 + k.k2 * r2 * r2;
      const double u = k.fx * xn * s + k.cx;
      const double v = k.fy * yn * s + k.cy;
      const QRgb pix = sampleBilinear(in, u, v);
      if (in.format() == QImage::Format_Grayscale8) {
        row[x] = static_cast<uchar>(qRed(pix));
      } else {
        row[x * 3 + 0] = static_cast<uchar>(qRed(pix));
        row[x * 3 + 1] = static_cast<uchar>(qGreen(pix));
        row[x * 3 + 2] = static_cast<uchar>(qBlue(pix));
      }
    }
  }
  return out;
}

QStringList listCalibImages(const QVariantMap& params) {
  QStringList paths;
  const QString listed = params.value(QStringLiteral("imagePaths")).toString().trimmed();
  if (!listed.isEmpty()) {
    const QStringList parts = listed.split(QRegularExpression(QStringLiteral("[,;\n]")), Qt::SkipEmptyParts);
    for (QString p : parts) {
      p = p.trimmed();
      if (!p.isEmpty()) paths << p;
    }
  }
  const QString dirPath = params.value(QStringLiteral("imageDir")).toString().trimmed();
  if (!dirPath.isEmpty()) {
    QDir dir(dirPath);
    const QStringList names =
        dir.entryList(QStringList() << QStringLiteral("*.png") << QStringLiteral("*.jpg")
                                    << QStringLiteral("*.jpeg") << QStringLiteral("*.bmp"),
                      QDir::Files, QDir::Name);
    for (const QString& n : names) paths << dir.absoluteFilePath(n);
  }
  paths.removeDuplicates();
  return paths;
}

QVector<QPointF> detectPattern(const QImage& img, const QString& pattern, int rows, int cols) {
  if (pattern == QLatin1String("circles") || pattern == QLatin1String("circle") ||
      pattern == QLatin1String("circle_grid"))
    return detectCircleGrid(img, rows, cols);
  return detectCheckerboard(toGray8(img), rows, cols);
}

/** 在给定相机与位姿下把世界平面点投到像素。 */
QPointF projectObj(const CameraIntrinsics& k, const Mat3& R, const Vec3& t, const QPointF& obj) {
  double u = 0, v = 0;
  projectPoint(k, R, t, obj, u, v);
  return QPointF(u, v);
}

Mat3 rotX(double a) {
  Mat3 r;
  r(1, 1) = std::cos(a);
  r(1, 2) = -std::sin(a);
  r(2, 1) = std::sin(a);
  r(2, 2) = std::cos(a);
  return r;
}
Mat3 rotY(double a) {
  Mat3 r;
  r(0, 0) = std::cos(a);
  r(0, 2) = std::sin(a);
  r(2, 0) = -std::sin(a);
  r(2, 2) = std::cos(a);
  return r;
}
Mat3 rotZ(double a) {
  Mat3 r;
  r(0, 0) = std::cos(a);
  r(0, 1) = -std::sin(a);
  r(1, 0) = std::sin(a);
  r(1, 1) = std::cos(a);
  return r;
}

/** 反向映射渲染圆点阵列（黑圆白底）或棋盘格，供自测。 */
QImage renderPattern(const CameraIntrinsics& k, const Mat3& R, const Vec3& t, int rows, int cols,
                     double square, bool circles) {
  QImage img(k.width, k.height, QImage::Format_RGB888);
  img.fill(QColor(255, 255, 255));
  // 世界到相机的逆：board Z=0 上的点
  const Mat3 Rt = [&]() {
    Mat3 m;
    // R^T
    m(0, 0) = R(0, 0);
    m(0, 1) = R(1, 0);
    m(0, 2) = R(2, 0);
    m(1, 0) = R(0, 1);
    m(1, 1) = R(1, 1);
    m(1, 2) = R(2, 1);
    m(2, 0) = R(0, 2);
    m(2, 1) = R(1, 2);
    m(2, 2) = R(2, 2);
    return m;
  }();
  const double radius = 0.32 * square;
  const double boardW = (cols - 1) * square;
  const double boardH = (rows - 1) * square;
  for (int y = 0; y < k.height; ++y) {
    uchar* rowp = img.scanLine(y);
    for (int x = 0; x < k.width; ++x) {
      const double xd = (x - k.cx) / k.fx;
      const double yd = (y - k.cy) / k.fy;
      double xn, yn;
      undistortNormalized(xd, yd, k.k1, k.k2, xn, yn);
      const Vec3 dir{xn, yn, 1.0};
      // s * dir = R * Pw + t, Pw.z=0 → R^T (s dir - t) . z = 0
      const Vec3 rtd = mul3v(Rt, dir);
      const Vec3 rtt = mul3v(Rt, t);
      if (std::fabs(rtd.z) < 1e-12) continue;
      const double s = rtt.z / rtd.z;
      if (s <= 0) continue;
      const Vec3 pcam{s * dir.x, s * dir.y, s * dir.z};
      const Vec3 pw = mul3v(Rt, Vec3{pcam.x - t.x, pcam.y - t.y, pcam.z - t.z});
      const double X = pw.x, Y = pw.y;
      bool black = false;
      if (circles) {
        // 只在阵列范围内找最近圆心
        if (X < -radius || Y < -radius || X > boardW + radius || Y > boardH + radius) {
          black = false;
        } else {
          const int c0 = qBound(0, qRound(X / square), cols - 1);
          const int r0 = qBound(0, qRound(Y / square), rows - 1);
          for (int rr = std::max(0, r0 - 1); rr <= std::min(rows - 1, r0 + 1) && !black; ++rr)
            for (int cc = std::max(0, c0 - 1); cc <= std::min(cols - 1, c0 + 1); ++cc) {
              const double dx = X - cc * square;
              const double dy = Y - rr * square;
              if (dx * dx + dy * dy <= radius * radius) {
                black = true;
                break;
              }
            }
        }
      } else {
        // 棋盘格覆盖到内角点外围各一格
        if (X < -square || Y < -square || X > boardW + square || Y > boardH + square)
          black = false;
        else {
          const int cx = static_cast<int>(std::floor(X / square));
          const int cy = static_cast<int>(std::floor(Y / square));
          black = ((cx + cy) & 1) == 0;
        }
      }
      if (black) {
        rowp[x * 3 + 0] = 10;
        rowp[x * 3 + 1] = 10;
        rowp[x * 3 + 2] = 10;
      }
    }
  }
  return img;
}

struct PoseSpec {
  Mat3 R;
  Vec3 t;
};

std::vector<PoseSpec> testPoses() {
  std::vector<PoseSpec> v;
  v.push_back(PoseSpec{mul3(rotX(0.18), rotY(-0.22)), Vec3{-40, -25, 300}});
  v.push_back(PoseSpec{mul3(rotX(-0.15), rotY(0.28)), Vec3{-55, -10, 280}});
  v.push_back(PoseSpec{mul3(rotX(0.10), rotZ(0.12)), Vec3{-30, -35, 320}});
  return v;
}

CameraIntrinsics testCamera() {
  CameraIntrinsics k;
  k.fx = 800;
  k.fy = 800;
  k.cx = 320;
  k.cy = 240;
  k.k1 = -0.22;
  k.k2 = 0.05;
  k.width = 640;
  k.height = 480;
  return k;
}

bool calibrateFromViews(std::vector<CalibView>& views, int width, int height, bool singleLock,
                        CameraIntrinsics& k, QString& err) {
  if (views.empty()) {
    err = QStringLiteral("没有可用的标定视图");
    return false;
  }
  k.width = width;
  k.height = height;
  if (k.cx <= 0 || k.cy <= 0) {
    k.cx = (width - 1) * 0.5;
    k.cy = (height - 1) * 0.5;
  }
  if (k.fx <= 1.0) k.fx = 0.9 * width;
  if (k.fy <= 1.0) k.fy = k.fx;
  // 用各视图单应初始化位姿
  for (CalibView& v : views) {
    const Homography ho = estimateHomography(v.object, v.image);
    if (!ho.ok || !poseFromHomography(ho.h, k, v.R, v.t)) {
      err = QStringLiteral("单应或位姿分解失败");
      return false;
    }
    v.rvec = rodriguesInv(v.R);
  }
  if (singleLock) {
    k.fy = k.fx;
    // cx,cy 保持锁定到中心（已在上面赋值时设定，refine 时仍让它们浮动会把单视图放飞）
    // 单视图：只优化 fx=fy 与 k1,k2，以及该视图位姿。通过 refine 后强制 fy=fx 再微调。
  }
  if (!refineCalibration(k, views, singleLock ? 20 : 30)) {
    err = QStringLiteral("非线性精化失败");
    return false;
  }
  if (singleLock) {
    k.fy = k.fx;
    k.cx = (width - 1) * 0.5;
    k.cy = (height - 1) * 0.5;
    // 再精化一次畸变与位姿（内参焦距仍可动，但下面把 cx,cy 拉回）
    if (!refineCalibration(k, views, 12)) {
      err = QStringLiteral("单视图精化失败");
      return false;
    }
    k.fy = k.fx;
    k.cx = (width - 1) * 0.5;
    k.cy = (height - 1) * 0.5;
  }
  if (!std::isfinite(k.fx) || k.fx < 10 || k.fy < 10) {
    err = QStringLiteral("求得的焦距无效");
    return false;
  }
  return true;
}

}  // namespace

CameraCalResult runCameraCal(const QImage& src, const QVariantMap& params) {
  CameraCalResult r;
  QString method = params.value(QStringLiteral("method"), QStringLiteral("calibrate")).toString().trimmed().toLower();
  if (method == QLatin1String("undistortion") || method == QLatin1String("rectify"))
    method = QStringLiteral("undistort");
  if (method != QLatin1String("undistort")) method = QStringLiteral("calibrate");
  r.method = method;
  QString pattern = params.value(QStringLiteral("pattern"), QStringLiteral("checkerboard"))
                        .toString()
                        .trimmed()
                        .toLower();
  if (pattern == QLatin1String("circle") || pattern == QLatin1String("circle_grid") ||
      pattern == QLatin1String("circles"))
    pattern = QStringLiteral("circles");
  else
    pattern = QStringLiteral("checkerboard");
  r.pattern = pattern;

  if (method == QLatin1String("undistort")) {
    if (src.isNull() || src.width() <= 0) {
      r.error = QStringLiteral("去畸变需要非空输入图像");
      return r;
    }
    CameraIntrinsics k;
    k.fx = params.value(QStringLiteral("fx"), 0).toDouble();
    k.fy = params.value(QStringLiteral("fy"), k.fx).toDouble();
    k.cx = params.value(QStringLiteral("cx"), (src.width() - 1) * 0.5).toDouble();
    k.cy = params.value(QStringLiteral("cy"), (src.height() - 1) * 0.5).toDouble();
    k.k1 = params.value(QStringLiteral("k1"), 0).toDouble();
    k.k2 = params.value(QStringLiteral("k2"), 0).toDouble();
    k.width = src.width();
    k.height = src.height();
    if (k.fx < 1.0 || k.fy < 1.0) {
      r.error = QStringLiteral("去畸变需要有效的 fx/fy");
      return r;
    }
    r.image = undistortImage(src, k);
    if (r.image.isNull()) {
      r.error = QStringLiteral("去畸变失败");
      return r;
    }
    r.intrinsics = k;
    r.ok = true;
    r.note = QStringLiteral("去畸变 fx=%1 fy=%2 k1=%3 k2=%4")
                 .arg(k.fx, 0, 'f', 1)
                 .arg(k.fy, 0, 'f', 1)
                 .arg(k.k1, 0, 'f', 4)
                 .arg(k.k2, 0, 'f', 4);
    return r;
  }

  const int rows = qBound(2, params.value(QStringLiteral("rows"), 6).toInt(), 40);
  const int cols = qBound(2, params.value(QStringLiteral("cols"), 9).toInt(), 40);
  const double square = std::max(1e-6, params.value(QStringLiteral("squareSize"), 1.0).toDouble());
  const QVector<QPointF> obj = objectGrid(rows, cols, square);

  QVector<QImage> images;
  if (!src.isNull() && src.width() > 0) images.push_back(src);
  for (const QString& path : listCalibImages(params)) {
    QImage im(path);
    if (!im.isNull()) images.push_back(im);
  }
  if (images.isEmpty()) {
    r.error = QStringLiteral("相机标定需要至少一张输入图像");
    return r;
  }

  std::vector<CalibView> views;
  QVector<QPointF> firstCorners;
  int w = images[0].width();
  int h = images[0].height();
  for (int i = 0; i < images.size(); ++i) {
    const QImage& im = images[i];
    const QVector<QPointF> pts = detectPattern(im, pattern, rows, cols);
    if (pts.size() != rows * cols) {
      // 当前工作图检测失败则整次失败，避免 silently 丢掉视图却仍报告成功
      r.error = QStringLiteral("第 %1 张图未检测到完整的 %2×%3 阵列（找到 %4）")
                    .arg(i + 1)
                    .arg(rows)
                    .arg(cols)
                    .arg(pts.size());
      r.detected = pts.size();
      return r;
    }
    if (i == 0) firstCorners = pts;
    CalibView v;
    v.object = obj;
    v.image = pts;
    views.push_back(v);
    w = im.width();
    h = im.height();
  }
  r.corners = firstCorners;
  r.detected = firstCorners.size();
  r.views = static_cast<int>(views.size());

  CameraIntrinsics k;
  k.fx = params.value(QStringLiteral("fx"), 0).toDouble();
  k.fy = params.value(QStringLiteral("fy"), 0).toDouble();
  k.cx = params.value(QStringLiteral("cx"), 0).toDouble();
  k.cy = params.value(QStringLiteral("cy"), 0).toDouble();
  k.k1 = params.value(QStringLiteral("k1"), 0).toDouble();
  k.k2 = params.value(QStringLiteral("k2"), 0).toDouble();
  const bool singleLock = views.size() < 2;
  QString err;
  if (!calibrateFromViews(views, w, h, singleLock, k, err)) {
    r.error = err;
    return r;
  }
  r.intrinsics = k;
  r.rmse = reprojectionRmse(k, views);
  r.ok = true;
  const QString outMode =
      params.value(QStringLiteral("output"), QStringLiteral("overlay")).toString().trimmed().toLower();
  if (outMode == QLatin1String("undistort") && !src.isNull()) r.image = undistortImage(src, k);
  r.note = QStringLiteral("标定 %1 视图 RMSE=%2 px  fx=%3 fy=%4 k1=%5%6")
               .arg(r.views)
               .arg(r.rmse, 0, 'f', 3)
               .arg(k.fx, 0, 'f', 1)
               .arg(k.fy, 0, 'f', 1)
               .arg(k.k1, 0, 'f', 4)
               .arg(singleLock ? QStringLiteral("（单视图约束 fx=fy，主点居中）")
                               : QString());
  return r;
}

QStringList cameraCalSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const CameraIntrinsics truth = testCamera();
  const int rows = 6, cols = 8;
  const double square = 15.0;
  const QVector<QPointF> obj = objectGrid(rows, cols, square);
  const auto poses = testPoses();

  // 1) 用精确对应点（无检测）恢复内参。
  std::vector<CalibView> exact;
  for (const PoseSpec& ps : poses) {
    CalibView v;
    v.object = obj;
    v.R = ps.R;
    v.t = ps.t;
    v.rvec = rodriguesInv(ps.R);
    for (const QPointF& p : obj) v.image.push_back(projectObj(truth, ps.R, ps.t, p));
    exact.push_back(v);
  }
  CameraIntrinsics rec;
  rec.cx = 0;
  rec.cy = 0;
  rec.fx = 0;
  QString err;
  const bool solved = calibrateFromViews(exact, truth.width, truth.height, false, rec, err);
  check("solver-ok", solved, err);
  if (solved) {
    const double rmse = reprojectionRmse(rec, exact);
    check("solver-rmse", rmse <= 0.15, QStringLiteral("rmse=%1").arg(rmse));
    check("solver-fx", std::fabs(rec.fx - truth.fx) <= 25.0,
          QStringLiteral("fx=%1").arg(rec.fx));
    check("solver-fy", std::fabs(rec.fy - truth.fy) <= 25.0,
          QStringLiteral("fy=%1").arg(rec.fy));
    check("solver-cx", std::fabs(rec.cx - truth.cx) <= 8.0, QStringLiteral("cx=%1").arg(rec.cx));
    check("solver-cy", std::fabs(rec.cy - truth.cy) <= 8.0, QStringLiteral("cy=%1").arg(rec.cy));
    check("solver-k1", std::fabs(rec.k1 - truth.k1) <= 0.04, QStringLiteral("k1=%1").arg(rec.k1));
    check("solver-k2", std::fabs(rec.k2 - truth.k2) <= 0.04, QStringLiteral("k2=%1").arg(rec.k2));
  }

  // 2) 渲染单视图圆点阵列并检测。
  const QImage view0 = renderPattern(truth, poses[0].R, poses[0].t, rows, cols, square, true);
  const QVector<QPointF> det = detectCircleGrid(view0, rows, cols);
  check("detect-count", det.size() == rows * cols, QStringLiteral("n=%1").arg(det.size()));
  if (det.size() == rows * cols) {
    double maxd = 0;
    int hits = 0;
    for (int i = 0; i < det.size(); ++i) {
      const QPointF pred = projectObj(truth, poses[0].R, poses[0].t, obj[i]);
      const double d = std::hypot(det[i].x() - pred.x(), det[i].y() - pred.y());
      if (d > maxd) maxd = d;
      if (d <= 2.5) ++hits;
    }
    // 排列若整体平移/翻转会全偏；要求大多数点贴近真值投影
    check("detect-acc", hits >= rows * cols - 2 && maxd <= 3.5,
          QStringLiteral("hits=%1 maxd=%2").arg(hits).arg(maxd));
  }

  // 3) 端到端：三张渲染图写入临时文件后走 runCameraCal。
  QStringList tmpPaths;
  const QString tmpDir = QDir::temp().filePath(QStringLiteral("sieans-camcal-selftest"));
  QDir().mkpath(tmpDir);
  for (int i = 0; i < static_cast<int>(poses.size()); ++i) {
    const QImage im = renderPattern(truth, poses[static_cast<size_t>(i)].R,
                                    poses[static_cast<size_t>(i)].t, rows, cols, square, true);
    const QString path = tmpDir + QStringLiteral("/view%1.png").arg(i);
    const bool saved = im.save(path);
    check("save-view", saved, path);
    tmpPaths << path;
  }
  const CameraCalResult e2e = runCameraCal(
      QImage(tmpPaths[0]),
      {{QStringLiteral("method"), QStringLiteral("calibrate")},
       {QStringLiteral("pattern"), QStringLiteral("circles")},
       {QStringLiteral("rows"), rows},
       {QStringLiteral("cols"), cols},
       {QStringLiteral("squareSize"), square},
       {QStringLiteral("imagePaths"), tmpPaths.join(QLatin1Char(','))}});
  // imagePaths 含第一张，会重复加入；检测仍应成功。允许 fx 相对误差与 k1 符号/量级。
  check("e2e-ok", e2e.ok, e2e.error);
  if (e2e.ok) {
    check("e2e-views", e2e.views >= 3, QStringLiteral("views=%1").arg(e2e.views));
    check("e2e-rmse", e2e.rmse <= 1.5, QStringLiteral("rmse=%1").arg(e2e.rmse));
    check("e2e-fx", std::fabs(e2e.intrinsics.fx - truth.fx) / truth.fx <= 0.08,
          QStringLiteral("fx=%1").arg(e2e.intrinsics.fx));
    check("e2e-k1", std::fabs(e2e.intrinsics.k1 - truth.k1) <= 0.08,
          QStringLiteral("k1=%1").arg(e2e.intrinsics.k1));
  }

  // 4) 用真值去畸变：把畸变图拉回后，圆点应接近无畸变投影。
  const CameraCalResult und = runCameraCal(
      view0, {{QStringLiteral("method"), QStringLiteral("undistort")},
              {QStringLiteral("fx"), truth.fx},
              {QStringLiteral("fy"), truth.fy},
              {QStringLiteral("cx"), truth.cx},
              {QStringLiteral("cy"), truth.cy},
              {QStringLiteral("k1"), truth.k1},
              {QStringLiteral("k2"), truth.k2}});
  check("undistort-ok", und.ok && !und.image.isNull(), und.error);
  if (und.ok) {
    CameraIntrinsics noD = truth;
    noD.k1 = 0;
    noD.k2 = 0;
    const QVector<QPointF> ud = detectCircleGrid(und.image, rows, cols);
    check("undistort-detect", ud.size() == rows * cols, QStringLiteral("n=%1").arg(ud.size()));
    if (ud.size() == rows * cols) {
      double maxd = 0;
      int hits = 0;
      for (int i = 0; i < ud.size(); ++i) {
        const QPointF pred = projectObj(noD, poses[0].R, poses[0].t, obj[i]);
        const double d = std::hypot(ud[i].x() - pred.x(), ud[i].y() - pred.y());
        if (d > maxd) maxd = d;
        if (d <= 3.0) ++hits;
      }
      check("undistort-acc", hits >= rows * cols - 3 && maxd <= 5.0,
            QStringLiteral("hits=%1 maxd=%2").arg(hits).arg(maxd));
    }
  }

  const CameraCalResult empty = runCameraCal(QImage(), {{QStringLiteral("method"), QStringLiteral("calibrate")},
                                                        {QStringLiteral("rows"), 6},
                                                        {QStringLiteral("cols"), 8}});
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  const CameraCalResult bad = runCameraCal(
      view0, {{QStringLiteral("method"), QStringLiteral("calibrate")},
              {QStringLiteral("pattern"), QStringLiteral("circles")},
              {QStringLiteral("rows"), 3},
              {QStringLiteral("cols"), 3}});
  check("wrong-grid-fail", !bad.ok && !bad.error.isEmpty(), bad.error);

  for (const QString& p : tmpPaths) QFile::remove(p);
  return fails;
}

}  // namespace sieans_qt
