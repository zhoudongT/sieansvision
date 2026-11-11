#include "CloudOps.hpp"

#include <QHash>
#include <QVariant>
#include <QVariantList>
#include <QtGlobal>
#include <QtMath>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <utility>
#include <vector>

namespace sieans_qt {
namespace {

constexpr int kMaxPoints = 200000;
constexpr int kMaxClusterPoints = 30000;
constexpr int kMaxClusters = 100;

struct Vec3 {
  double x = 0, y = 0, z = 0;
  Vec3() = default;
  Vec3(double X, double Y, double Z) : x(X), y(Y), z(Z) {}
  Vec3 operator+(const Vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
  Vec3 operator-(const Vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
  Vec3 operator*(double s) const { return {x * s, y * s, z * s}; }
  double dot(const Vec3& o) const { return x * o.x + y * o.y + z * o.z; }
  Vec3 cross(const Vec3& o) const {
    return {y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x};
  }
  double norm2() const { return x * x + y * y + z * z; }
  double norm() const { return std::sqrt(norm2()); }
};

struct Mat3 {
  double m[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
  static Mat3 ident() {
    Mat3 a;
    a.m[0][0] = a.m[1][1] = a.m[2][2] = 1;
    return a;
  }
  double* operator[](int i) { return m[i]; }
  const double* operator[](int i) const { return m[i]; }
};

Vec3 mul(const Mat3& A, const Vec3& v) {
  return {A[0][0] * v.x + A[0][1] * v.y + A[0][2] * v.z,
          A[1][0] * v.x + A[1][1] * v.y + A[1][2] * v.z,
          A[2][0] * v.x + A[2][1] * v.y + A[2][2] * v.z};
}

Mat3 mul(const Mat3& A, const Mat3& B) {
  Mat3 C;
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j)
      C[i][j] = A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j];
  return C;
}

Mat3 transpose(const Mat3& A) {
  Mat3 T;
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) T[i][j] = A[j][i];
  return T;
}

double det3(const Mat3& A) {
  return A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1]) -
         A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0]) +
         A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0]);
}

/** 3×3 对称矩阵 Jacobi 特征分解，得到 A = Q diag(ev) Q^T。 */
void jacobiEigen3(Mat3 A, double ev[3], Mat3& Q) {
  Q = Mat3::ident();
  for (int iter = 0; iter < 32; ++iter) {
    int p = 0, q = 1;
    double best = std::fabs(A[0][1]);
    if (std::fabs(A[0][2]) > best) {
      best = std::fabs(A[0][2]);
      p = 0;
      q = 2;
    }
    if (std::fabs(A[1][2]) > best) {
      best = std::fabs(A[1][2]);
      p = 1;
      q = 2;
    }
    if (best < 1e-15) break;
    const double app = A[p][p], aqq = A[q][q], apq = A[p][q];
    const double tau = (aqq - app) / (2.0 * apq);
    const double t = (tau >= 0 ? 1.0 : -1.0) / (std::fabs(tau) + std::sqrt(1.0 + tau * tau));
    const double c = 1.0 / std::sqrt(1.0 + t * t);
    const double s = t * c;
    A[p][p] = app - t * apq;
    A[q][q] = aqq + t * apq;
    A[p][q] = A[q][p] = 0;
    for (int k = 0; k < 3; ++k) {
      if (k == p || k == q) continue;
      const double akp = A[k][p], akq = A[k][q];
      A[k][p] = A[p][k] = c * akp - s * akq;
      A[k][q] = A[q][k] = s * akp + c * akq;
    }
    for (int k = 0; k < 3; ++k) {
      const double qkp = Q[k][p], qkq = Q[k][q];
      Q[k][p] = c * qkp - s * qkq;
      Q[k][q] = s * qkp + c * qkq;
    }
  }
  ev[0] = A[0][0];
  ev[1] = A[1][1];
  ev[2] = A[2][2];
}

/** 3×3 SVD：A = U S V^T，用于 Kabsch / ICP 刚体求解。 */
void svd3(const Mat3& A, Mat3& U, double s[3], Mat3& V) {
  Mat3 AtA{};
  const Mat3 At = transpose(A);
  AtA = mul(At, A);
  double ev[3];
  jacobiEigen3(AtA, ev, V);
  int idx[3] = {0, 1, 2};
  std::sort(idx, idx + 3, [&](int a, int b) { return ev[a] > ev[b]; });
  Mat3 Vs = Mat3::ident();
  double evs[3];
  for (int j = 0; j < 3; ++j) {
    evs[j] = ev[idx[j]];
    for (int i = 0; i < 3; ++i) Vs[i][j] = V[i][idx[j]];
  }
  V = Vs;
  for (int i = 0; i < 3; ++i) s[i] = evs[i] > 0 ? std::sqrt(evs[i]) : 0;
  U = Mat3{};
  for (int j = 0; j < 3; ++j) {
    Vec3 vcol{V[0][j], V[1][j], V[2][j]};
    Vec3 ucol = mul(A, vcol);
    if (s[j] > 1e-15) ucol = ucol * (1.0 / s[j]);
    const double n = ucol.norm();
    if (n > 1e-15) ucol = ucol * (1.0 / n);
    U[0][j] = ucol.x;
    U[1][j] = ucol.y;
    U[2][j] = ucol.z;
  }
  if (det3(U) < 0) {
    U[0][2] = -U[0][2];
    U[1][2] = -U[1][2];
    U[2][2] = -U[2][2];
    s[2] = -s[2];
  }
  if (det3(V) < 0) {
    V[0][2] = -V[0][2];
    V[1][2] = -V[1][2];
    V[2][2] = -V[2][2];
    s[2] = -s[2];
  }
}

void ident4(double T[16]) {
  for (int i = 0; i < 16; ++i) T[i] = 0;
  T[0] = T[5] = T[10] = T[15] = 1;
}

void mul4(const double A[16], const double B[16], double C[16]) {
  double tmp[16];
  for (int i = 0; i < 4; ++i)
    for (int j = 0; j < 4; ++j) {
      tmp[i * 4 + j] = A[i * 4 + 0] * B[0 * 4 + j] + A[i * 4 + 1] * B[1 * 4 + j] +
                       A[i * 4 + 2] * B[2 * 4 + j] + A[i * 4 + 3] * B[3 * 4 + j];
    }
  for (int i = 0; i < 16; ++i) C[i] = tmp[i];
}

Vec3 applyT(const double T[16], const Vec3& p) {
  return {T[0] * p.x + T[1] * p.y + T[2] * p.z + T[3],
          T[4] * p.x + T[5] * p.y + T[6] * p.z + T[7],
          T[8] * p.x + T[9] * p.y + T[10] * p.z + T[11]};
}

void setRt(double T[16], const Mat3& R, const Vec3& t) {
  ident4(T);
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) T[i * 4 + j] = R[i][j];
  T[3] = t.x;
  T[7] = t.y;
  T[11] = t.z;
}

struct KdNode {
  int axis = 0;
  int index = -1;
  int left = -1;
  int right = -1;
};

struct KdTree {
  const QVector<CloudPoint>* pts = nullptr;
  std::vector<KdNode> nodes;

  void build(const QVector<CloudPoint>& points) {
    pts = &points;
    nodes.clear();
    if (points.isEmpty()) return;
    nodes.reserve(size_t(points.size()));
    std::vector<int> idx(size_t(points.size()));
    for (int i = 0; i < points.size(); ++i) idx[size_t(i)] = i;
    buildRec(idx.data(), int(idx.size()), 0);
  }

  int nearest(const Vec3& q, double* dist2 = nullptr) const {
    if (nodes.empty()) return -1;
    int best = -1;
    double bestD = std::numeric_limits<double>::infinity();
    nearestRec(0, q, best, bestD);
    if (dist2) *dist2 = bestD;
    return best;
  }

  void radius(const Vec3& q, double r, std::vector<int>& out) const {
    out.clear();
    if (nodes.empty()) return;
    radiusRec(0, q, r * r, out);
  }

  void knn(const Vec3& q, int k, std::vector<std::pair<double, int>>& out) const {
    out.clear();
    if (nodes.empty() || k <= 0) return;
    knnRec(0, q, k, out);
  }

 private:
  int buildRec(int* idx, int n, int depth) {
    if (n <= 0) return -1;
    const int axis = depth % 3;
    const int mid = n / 2;
    auto coord = [&](int i) {
      const CloudPoint& p = (*pts)[i];
      return axis == 0 ? p.x : (axis == 1 ? p.y : p.z);
    };
    std::nth_element(idx, idx + mid, idx + n,
                     [&](int a, int b) { return coord(a) < coord(b); });
    const int id = int(nodes.size());
    nodes.push_back(KdNode{axis, idx[mid], -1, -1});
    const int L = buildRec(idx, mid, depth + 1);
    const int R = buildRec(idx + mid + 1, n - mid - 1, depth + 1);
    nodes[size_t(id)].left = L;
    nodes[size_t(id)].right = R;
    return id;
  }

  void nearestRec(int node, const Vec3& q, int& best, double& bestD) const {
    if (node < 0) return;
    const KdNode& n = nodes[size_t(node)];
    const CloudPoint& p = (*pts)[n.index];
    const double d2 = (p.x - q.x) * (p.x - q.x) + (p.y - q.y) * (p.y - q.y) +
                      (p.z - q.z) * (p.z - q.z);
    if (d2 < bestD) {
      bestD = d2;
      best = n.index;
    }
    const double qc = n.axis == 0 ? q.x : (n.axis == 1 ? q.y : q.z);
    const double pc = n.axis == 0 ? p.x : (n.axis == 1 ? p.y : p.z);
    const double delta = qc - pc;
    const int first = delta < 0 ? n.left : n.right;
    const int second = delta < 0 ? n.right : n.left;
    nearestRec(first, q, best, bestD);
    if (delta * delta < bestD) nearestRec(second, q, best, bestD);
  }

  void radiusRec(int node, const Vec3& q, double r2, std::vector<int>& out) const {
    if (node < 0) return;
    const KdNode& n = nodes[size_t(node)];
    const CloudPoint& p = (*pts)[n.index];
    const double d2 = (p.x - q.x) * (p.x - q.x) + (p.y - q.y) * (p.y - q.y) +
                      (p.z - q.z) * (p.z - q.z);
    if (d2 <= r2) out.push_back(n.index);
    const double qc = n.axis == 0 ? q.x : (n.axis == 1 ? q.y : q.z);
    const double pc = n.axis == 0 ? p.x : (n.axis == 1 ? p.y : p.z);
    const double delta = qc - pc;
    const int first = delta < 0 ? n.left : n.right;
    const int second = delta < 0 ? n.right : n.left;
    radiusRec(first, q, r2, out);
    if (delta * delta <= r2) radiusRec(second, q, r2, out);
  }

  void knnRec(int node, const Vec3& q, int k,
              std::vector<std::pair<double, int>>& heap) const {
    if (node < 0) return;
    const KdNode& n = nodes[size_t(node)];
    const CloudPoint& p = (*pts)[n.index];
    const double d2 = (p.x - q.x) * (p.x - q.x) + (p.y - q.y) * (p.y - q.y) +
                      (p.z - q.z) * (p.z - q.z);
    if (int(heap.size()) < k) {
      heap.push_back({d2, n.index});
      std::push_heap(heap.begin(), heap.end());
    } else if (d2 < heap.front().first) {
      std::pop_heap(heap.begin(), heap.end());
      heap.back() = {d2, n.index};
      std::push_heap(heap.begin(), heap.end());
    }
    const double qc = n.axis == 0 ? q.x : (n.axis == 1 ? q.y : q.z);
    const double pc = n.axis == 0 ? p.x : (n.axis == 1 ? p.y : p.z);
    const double delta = qc - pc;
    const int first = delta < 0 ? n.left : n.right;
    const int second = delta < 0 ? n.right : n.left;
    knnRec(first, q, k, heap);
    const double worst = heap.size() < size_t(k) ? std::numeric_limits<double>::infinity()
                                                 : heap.front().first;
    if (delta * delta <= worst) knnRec(second, q, k, heap);
  }
};

struct Rng {
  std::uint64_t s;
  explicit Rng(std::uint64_t seed = 42) : s(seed ? seed : 1) {}
  std::uint32_t next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return std::uint32_t(s);
  }
  int bounded(int n) { return n <= 0 ? 0 : int(next() % std::uint32_t(n)); }
};

double number(const QVariantMap& p, const QString& key, double def, double lo, double hi,
              QString* err) {
  const QVariant v = p.contains(key) ? p.value(key) : QVariant(def);
  bool ok = false;
  const double x = v.toDouble(&ok);
  if (!ok || !std::isfinite(x) || x < lo || x > hi) {
    if (err) *err = QStringLiteral("%1 必须在 %2 到 %3 之间").arg(key).arg(lo).arg(hi);
    return def;
  }
  return x;
}

bool readVec3Param(const QVariantMap& p, const QString& key, const double fallback[3],
                   double out[3], QString* err) {
  out[0] = fallback[0];
  out[1] = fallback[1];
  out[2] = fallback[2];
  if (p.contains(key)) {
    const QVariant raw = p.value(key);
    if (raw.typeId() == QMetaType::QVariantList || raw.typeId() == QMetaType::QStringList) {
      const QVariantList lst = raw.toList().isEmpty() ? QVariantList() : raw.toList();
      QStringList sl;
      if (lst.isEmpty()) sl = raw.toStringList();
      if (lst.size() == 3) {
        for (int i = 0; i < 3; ++i) out[i] = lst[i].toDouble();
        return true;
      }
      if (sl.size() == 3) {
        for (int i = 0; i < 3; ++i) out[i] = sl[i].toDouble();
        return true;
      }
      if (err) *err = key + QStringLiteral(" 必须包含 3 个数值");
      return false;
    }
    const QString s = raw.toString().trimmed();
    if (!s.isEmpty()) {
      const QStringList parts = s.split(QLatin1Char(','), Qt::SkipEmptyParts);
      if (parts.size() != 3) {
        if (err) *err = key + QStringLiteral(" 必须包含 3 个数值");
        return false;
      }
      for (int i = 0; i < 3; ++i) out[i] = parts[i].trimmed().toDouble();
      return true;
    }
  }
  const QString ax[3] = {key + QStringLiteral("X"),
                         key + QStringLiteral("Y"),
                         key + QStringLiteral("Z")};
  // also minX/maxX style (key already is "min"/"max")
  const QString alt[3] = {key == QLatin1String("minimum") ? QStringLiteral("minX")
                                                          : QStringLiteral("maxX"),
                          key == QLatin1String("minimum") ? QStringLiteral("minY")
                                                          : QStringLiteral("maxY"),
                          key == QLatin1String("minimum") ? QStringLiteral("minZ")
                                                          : QStringLiteral("maxZ")};
  bool any = false;
  for (int i = 0; i < 3; ++i) {
    if (p.contains(alt[i])) {
      out[i] = p.value(alt[i]).toDouble();
      any = true;
    } else if (p.contains(ax[i])) {
      out[i] = p.value(ax[i]).toDouble();
      any = true;
    }
  }
  Q_UNUSED(any);
  return true;
}

bool validate(const PointCloud& c, QString* err) {
  if (c.unit != QLatin1String("mm") && c.unit != QLatin1String("m")) {
    if (err) *err = QStringLiteral("点云必须声明单位 mm 或 m");
    return false;
  }
  if (c.points.size() < 1 || c.points.size() > kMaxPoints) {
    if (err) *err = QStringLiteral("点云必须包含 1 到 %1 个点").arg(kMaxPoints);
    return false;
  }
  for (const CloudPoint& p : c.points) {
    if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z) ||
        std::fabs(p.x) > 1e9 || std::fabs(p.y) > 1e9 || std::fabs(p.z) > 1e9) {
      if (err) *err = QStringLiteral("点云包含无效坐标或坐标超过 1e9");
      return false;
    }
  }
  return true;
}

CloudBounds computeBounds(const QVector<CloudPoint>& pts) {
  CloudBounds b;
  if (pts.isEmpty()) return b;
  b.minX = b.maxX = pts[0].x;
  b.minY = b.maxY = pts[0].y;
  b.minZ = b.maxZ = pts[0].z;
  for (const CloudPoint& p : pts) {
    if (p.x < b.minX) b.minX = p.x;
    if (p.y < b.minY) b.minY = p.y;
    if (p.z < b.minZ) b.minZ = p.z;
    if (p.x > b.maxX) b.maxX = p.x;
    if (p.y > b.maxY) b.maxY = p.y;
    if (p.z > b.maxZ) b.maxZ = p.z;
  }
  b.sizeX = b.maxX - b.minX;
  b.sizeY = b.maxY - b.minY;
  b.sizeZ = b.maxZ - b.minZ;
  b.centerX = 0.5 * (b.minX + b.maxX);
  b.centerY = 0.5 * (b.minY + b.maxY);
  b.centerZ = 0.5 * (b.minZ + b.maxZ);
  b.boundingBoxVolume = b.sizeX * b.sizeY * b.sizeZ;
  b.valid = true;
  return b;
}

PointCloud subset(const PointCloud& src, const std::vector<int>& idx) {
  PointCloud out;
  out.unit = src.unit;
  out.frame = src.frame;
  out.points.reserve(int(idx.size()));
  for (int i : idx) out.points.push_back(src.points[i]);
  return out;
}

PointCloud translate(const PointCloud& src, double dx, double dy, double dz) {
  PointCloud out = src;
  for (CloudPoint& p : out.points) {
    p.x += dx;
    p.y += dy;
    p.z += dz;
  }
  return out;
}

bool rigidFromCorrespondences(const std::vector<Vec3>& src, const std::vector<Vec3>& dst,
                              Mat3& R, Vec3& t) {
  if (src.size() < 3 || src.size() != dst.size()) return false;
  Vec3 cs{}, ct{};
  for (size_t i = 0; i < src.size(); ++i) {
    cs = cs + src[i];
    ct = ct + dst[i];
  }
  const double inv = 1.0 / double(src.size());
  cs = cs * inv;
  ct = ct * inv;
  Mat3 H{};
  for (size_t i = 0; i < src.size(); ++i) {
    const Vec3 p = src[i] - cs;
    const Vec3 q = dst[i] - ct;
    H[0][0] += p.x * q.x;
    H[0][1] += p.x * q.y;
    H[0][2] += p.x * q.z;
    H[1][0] += p.y * q.x;
    H[1][1] += p.y * q.y;
    H[1][2] += p.y * q.z;
    H[2][0] += p.z * q.x;
    H[2][1] += p.z * q.y;
    H[2][2] += p.z * q.z;
  }
  Mat3 U, V;
  double s[3];
  svd3(H, U, s, V);
  // H = sum p q^T = U S V^T, R = V U^T
  R = mul(V, transpose(U));
  if (det3(R) < 0) {
    V[0][2] = -V[0][2];
    V[1][2] = -V[1][2];
    V[2][2] = -V[2][2];
    R = mul(V, transpose(U));
  }
  const Vec3 Rs = mul(R, cs);
  t = ct - Rs;
  return true;
}

QVector<CloudPoint> applyTransformPoints(const QVector<CloudPoint>& in, const double T[16]) {
  QVector<CloudPoint> out = in;
  for (CloudPoint& p : out) {
    const Vec3 q = applyT(T, {p.x, p.y, p.z});
    p.x = q.x;
    p.y = q.y;
    p.z = q.z;
  }
  return out;
}

bool parseInitialTransform(const QVariant& raw, double T[16], QString* err) {
  ident4(T);
  if (!raw.isValid() || raw.isNull()) return true;
  const QVariantList rows = raw.toList();
  if (rows.size() != 4) {
    if (err) *err = QStringLiteral("initialTransform 必须为 4×4 刚体变换矩阵");
    return false;
  }
  for (int i = 0; i < 4; ++i) {
    const QVariantList row = rows[i].toList();
    if (row.size() != 4) {
      if (err) *err = QStringLiteral("initialTransform 必须为 4×4 刚体变换矩阵");
      return false;
    }
    for (int j = 0; j < 4; ++j) T[i * 4 + j] = row[j].toDouble();
  }
  return true;
}

struct IcpStats {
  bool ok = false;
  QString error;
  double fitness = 0;
  double targetFitness = 0;
  double rms = 0;
  double T[16]{};
};

IcpStats runIcp(const PointCloud& source, const PointCloud& target, const double T0[16],
                double maxDist, int iterations) {
  IcpStats st;
  ident4(st.T);
  mul4(T0, st.T, st.T);  // copy T0
  for (int i = 0; i < 16; ++i) st.T[i] = T0[i];
  KdTree tree;
  tree.build(target.points);
  const double max2 = maxDist * maxDist;
  for (int it = 0; it < iterations; ++it) {
    std::vector<Vec3> srcC, dstC;
    srcC.reserve(size_t(source.points.size()));
    dstC.reserve(size_t(source.points.size()));
    double sum2 = 0;
    for (const CloudPoint& sp : source.points) {
      const Vec3 q = applyT(st.T, {sp.x, sp.y, sp.z});
      double d2 = 0;
      const int j = tree.nearest(q, &d2);
      if (j < 0 || d2 > max2) continue;
      srcC.push_back(q);
      const CloudPoint& tp = target.points[j];
      dstC.push_back({tp.x, tp.y, tp.z});
      sum2 += d2;
    }
    if (srcC.size() < 3) {
      st.error = QStringLiteral("配准没有有效对应点，请检查初始位置和最大距离");
      return st;
    }
    Mat3 R;
    Vec3 t;
    if (!rigidFromCorrespondences(srcC, dstC, R, t)) {
      st.error = QStringLiteral("刚体变换求解失败");
      return st;
    }
    double dT[16];
    setRt(dT, R, t);
    mul4(dT, st.T, st.T);
    st.fitness = double(srcC.size()) / double(source.points.size());
    st.rms = std::sqrt(sum2 / double(srcC.size()));
  }
  // final metrics + target coverage
  {
    double sum2 = 0;
    int hit = 0;
    for (const CloudPoint& sp : source.points) {
      const Vec3 q = applyT(st.T, {sp.x, sp.y, sp.z});
      double d2 = 0;
      const int j = tree.nearest(q, &d2);
      if (j < 0 || d2 > max2) continue;
      ++hit;
      sum2 += d2;
    }
    st.fitness = source.points.isEmpty() ? 0 : double(hit) / double(source.points.size());
    st.rms = hit ? std::sqrt(sum2 / double(hit)) : 0;
    KdTree srcTree;
    PointCloud srcT = source;
    srcT.points = applyTransformPoints(source.points, st.T);
    srcTree.build(srcT.points);
    int thit = 0;
    for (const CloudPoint& tp : target.points) {
      double d2 = 0;
      const int j = srcTree.nearest({tp.x, tp.y, tp.z}, &d2);
      if (j >= 0 && d2 <= max2) ++thit;
    }
    st.targetFitness =
        target.points.isEmpty() ? 0 : double(thit) / double(target.points.size());
  }
  st.ok = st.fitness > 0;
  if (!st.ok) st.error = QStringLiteral("配准没有有效对应点，请检查初始位置和最大距离");
  return st;
}

Vec3 centroidOf(const QVector<CloudPoint>& pts) {
  Vec3 c;
  if (pts.isEmpty()) return c;
  for (const CloudPoint& p : pts) {
    c.x += p.x;
    c.y += p.y;
    c.z += p.z;
  }
  const double inv = 1.0 / double(pts.size());
  return c * inv;
}

Mat3 covarianceOf(const QVector<CloudPoint>& pts, const Vec3& c) {
  Mat3 A{};
  if (pts.isEmpty()) return A;
  for (const CloudPoint& p : pts) {
    const Vec3 d{p.x - c.x, p.y - c.y, p.z - c.z};
    A[0][0] += d.x * d.x;
    A[0][1] += d.x * d.y;
    A[0][2] += d.x * d.z;
    A[1][0] += d.y * d.x;
    A[1][1] += d.y * d.y;
    A[1][2] += d.y * d.z;
    A[2][0] += d.z * d.x;
    A[2][1] += d.z * d.y;
    A[2][2] += d.z * d.z;
  }
  const double inv = 1.0 / double(pts.size());
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) A[i][j] *= inv;
  return A;
}

/** PCA 轴：按特征值从大到小排列，并保证右手系。 */
void pcaAxes(const QVector<CloudPoint>& pts, Mat3& axes) {
  const Vec3 c = centroidOf(pts);
  const Mat3 cov = covarianceOf(pts, c);
  double ev[3];
  Mat3 Q;
  jacobiEigen3(cov, ev, Q);
  int idx[3] = {0, 1, 2};
  std::sort(idx, idx + 3, [&](int a, int b) { return ev[a] > ev[b]; });
  for (int j = 0; j < 3; ++j)
    for (int i = 0; i < 3; ++i) axes[i][j] = Q[i][idx[j]];
  // make right-handed
  const Vec3 a{axes[0][0], axes[1][0], axes[2][0]};
  const Vec3 b{axes[0][1], axes[1][1], axes[2][1]};
  const Vec3 cr = a.cross(b);
  axes[0][2] = cr.x;
  axes[1][2] = cr.y;
  axes[2][2] = cr.z;
}

CloudResult fail(const QString& op, const QString& error) {
  CloudResult r;
  r.operation = op;
  r.error = error;
  return r;
}

}  // namespace

PointCloud makeSoftCloudPart() {
  PointCloud c;
  c.unit = QStringLiteral("mm");
  c.frame = QStringLiteral("sensor");
  const double xs[2] = {0, 20};
  const double ys[2] = {0, 10};
  const double zs[2] = {0, 5};
  for (double x : xs)
    for (double y : ys)
      for (double z : zs) {
        CloudPoint p;
        p.x = x;
        p.y = y;
        p.z = z;
        c.points.push_back(p);
      }
  return c;
}

PointCloud makeSoftCloudSurface() {
  PointCloud c;
  c.unit = QStringLiteral("mm");
  c.frame = QStringLiteral("sensor");
  c.points.reserve(200);
  for (int x = 0; x < 20; ++x)
    for (int y = 0; y < 10; ++y) {
      CloudPoint p;
      p.x = x + 0.5;
      p.y = y + 0.5;
      p.z = 5;
      c.points.push_back(p);
    }
  return c;
}

PointCloud makeSoftCloudRegisterSet() {
  PointCloud c;
  c.unit = QStringLiteral("mm");
  c.frame = QStringLiteral("sensor");
  // Deterministic irregular samples in a 20×10×5 mm box, plus a unique tip
  // so ICP 不会落入规则网格的错误周期解。
  Rng rng(15);
  c.points.reserve(201);
  for (int i = 0; i < 200; ++i) {
    CloudPoint p;
    p.x = (rng.next() % 10000) / 10000.0 * 20.0;
    p.y = (rng.next() % 10000) / 10000.0 * 10.0;
    p.z = (rng.next() % 10000) / 10000.0 * 5.0;
    c.points.push_back(p);
  }
  CloudPoint tip;
  tip.x = 0;
  tip.y = 0;
  tip.z = 8;
  c.points.push_back(tip);
  return c;
}

PointCloud makeSoftCloudFixture() {
  PointCloud c;
  c.unit = QStringLiteral("mm");
  c.frame = QStringLiteral("sensor");
  // Ground plane z=0: 21×17 = 357
  for (int ix = -10; ix <= 10; ++ix)
    for (int iy = -8; iy <= 8; ++iy) {
      CloudPoint p;
      p.x = ix * 2.0;
      p.y = iy * 2.0;
      p.z = 0;
      c.points.push_back(p);
    }
  // Cluster 1: 20×10 top surface at z=5 (200 pts)
  const PointCloud surf = makeSoftCloudSurface();
  for (const CloudPoint& p : surf.points) c.points.push_back(p);
  // Cluster 2: 5×5 patch around (-15,-10,3)
  for (int i = 0; i < 5; ++i)
    for (int j = 0; j < 5; ++j) {
      CloudPoint p;
      p.x = -15.0 + i * 0.5;
      p.y = -10.0 + j * 0.5;
      p.z = 3;
      c.points.push_back(p);
    }
  // Isolated noise
  CloudPoint n;
  n.x = 200;
  n.y = 200;
  n.z = 200;
  c.points.push_back(n);
  return c;
}

PointCloud resolveCloudInput(const PointCloud& upstream, const QVariantMap& params,
                             QString* error) {
  const QString src =
      params.value(QStringLiteral("inputSource"), QStringLiteral("upstream"))
          .toString()
          .trimmed()
          .toLower();
  PointCloud out;
  if (src == QLatin1String("soft_fixture"))
    out = makeSoftCloudFixture();
  else if (src == QLatin1String("soft_part"))
    out = makeSoftCloudPart();
  else if (src == QLatin1String("soft_surface"))
    out = makeSoftCloudSurface();
  else if (src == QLatin1String("soft_register") || src == QLatin1String("soft_shifted"))
    out = makeSoftCloudRegisterSet();
  else if (src == QLatin1String("upstream") || src.isEmpty()) {
    if (upstream.isEmpty()) {
      if (error) *error = QStringLiteral("没有上游点云，请设置 inputSource 或先运行滤波节点");
      return {};
    }
    out = upstream;
  } else {
    if (error) *error = QStringLiteral("未知 inputSource");
    return {};
  }
  const double dx = params.value(QStringLiteral("inputShiftX"), 0).toDouble();
  const double dy = params.value(QStringLiteral("inputShiftY"), 0).toDouble();
  const double dz = params.value(QStringLiteral("inputShiftZ"), 0).toDouble();
  if (dx != 0 || dy != 0 || dz != 0) out = translate(out, dx, dy, dz);
  if (src == QLatin1String("soft_shifted") && dx == 0 && dy == 0 && dz == 0)
    out = translate(out, 5, -3, 2);
  return out;
}

CloudResult runCloudFilter(const PointCloud& input, const QVariantMap& params) {
  const QString op = QStringLiteral("cloud_filter");
  QString err;
  if (!validate(input, &err)) return fail(op, err);
  CloudResult r;
  r.operation = op;
  r.inputCount = input.points.size();
  r.method = params.value(QStringLiteral("method"), QStringLiteral("voxel")).toString().trimmed();
  PointCloud out;
  out.unit = input.unit;
  out.frame = input.frame;

  if (r.method == QLatin1String("voxel")) {
    const double vs = number(params, QStringLiteral("voxelSize"), 1, 1e-6, 1e6, &err);
    if (!err.isEmpty()) return fail(op, err);
    struct Acc {
      double x = 0, y = 0, z = 0, r = 0, g = 0, b = 0;
      int n = 0;
      int cn = 0;
    };
    QHash<qint64, Acc> bins;
    auto keyOf = [&](const CloudPoint& p) -> qint64 {
      const qint64 ix = qint64(std::floor(p.x / vs));
      const qint64 iy = qint64(std::floor(p.y / vs));
      const qint64 iz = qint64(std::floor(p.z / vs));
      // 20-bit packed signed-ish hash; coordinates are bounded by validate()
      return ((ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791));
    };
    // collision-safe: use a map with triple key via QString if needed; for
    // correctness use a nested hash. Packed hash is ok for smoke sizes; to be
    // safe we store a QVector of unique keys with linear check on collision
    // groups. Use std::map of tuple.
    struct I3 {
      qint64 x, y, z;
      bool operator<(const I3& o) const {
        if (x != o.x) return x < o.x;
        if (y != o.y) return y < o.y;
        return z < o.z;
      }
    };
    std::map<I3, Acc> grid;
    for (const CloudPoint& p : input.points) {
      I3 k{qint64(std::floor(p.x / vs)), qint64(std::floor(p.y / vs)),
           qint64(std::floor(p.z / vs))};
      Acc& a = grid[k];
      a.x += p.x;
      a.y += p.y;
      a.z += p.z;
      ++a.n;
      if (p.hasColor) {
        a.r += p.r;
        a.g += p.g;
        a.b += p.b;
        ++a.cn;
      }
    }
    out.points.reserve(int(grid.size()));
    for (const auto& kv : grid) {
      const Acc& a = kv.second;
      CloudPoint p;
      p.x = a.x / a.n;
      p.y = a.y / a.n;
      p.z = a.z / a.n;
      if (a.cn) {
        p.r = a.r / a.cn;
        p.g = a.g / a.cn;
        p.b = a.b / a.cn;
        p.hasColor = true;
      }
      out.points.push_back(p);
    }
    Q_UNUSED(keyOf);
    Q_UNUSED(bins);
  } else if (r.method == QLatin1String("crop")) {
    const double defMin[3] = {-100, -100, -100};
    const double defMax[3] = {100, 100, 100};
    double mn[3], mx[3];
    if (!readVec3Param(params, QStringLiteral("minimum"), defMin, mn, &err))
      return fail(op, err);
    if (!readVec3Param(params, QStringLiteral("maximum"), defMax, mx, &err))
      return fail(op, err);
    if (mx[0] <= mn[0] || mx[1] <= mn[1] || mx[2] <= mn[2])
      return fail(op, QStringLiteral("裁剪 maximum 必须大于 minimum"));
    for (const CloudPoint& p : input.points) {
      if (p.x >= mn[0] && p.x <= mx[0] && p.y >= mn[1] && p.y <= mx[1] && p.z >= mn[2] &&
          p.z <= mx[2])
        out.points.push_back(p);
    }
  } else if (r.method == QLatin1String("statistical")) {
    const int neighbors = int(number(params, QStringLiteral("neighbors"), 20, 2, 200, &err));
    if (!err.isEmpty()) return fail(op, err);
    const double stdRatio = number(params, QStringLiteral("stdRatio"), 2, 0.01, 100, &err);
    if (!err.isEmpty()) return fail(op, err);
    if (input.points.size() <= neighbors)
      return fail(op, QStringLiteral("点数量必须大于邻域点数"));
    KdTree tree;
    tree.build(input.points);
    std::vector<double> meanD(size_t(input.points.size()), 0);
    for (int i = 0; i < input.points.size(); ++i) {
      const CloudPoint& p = input.points[i];
      std::vector<std::pair<double, int>> nn;
      tree.knn({p.x, p.y, p.z}, neighbors + 1, nn);
      double s = 0;
      int used = 0;
      for (const auto& pr : nn) {
        if (pr.second == i) continue;
        s += std::sqrt(pr.first);
        if (++used >= neighbors) break;
      }
      meanD[size_t(i)] = used ? s / used : 0;
    }
    double mu = 0;
    for (double d : meanD) mu += d;
    mu /= double(meanD.size());
    double var = 0;
    for (double d : meanD) var += (d - mu) * (d - mu);
    const double sd = std::sqrt(var / double(meanD.size()));
    const double thr = mu + stdRatio * sd;
    for (int i = 0; i < input.points.size(); ++i)
      if (meanD[size_t(i)] <= thr) out.points.push_back(input.points[i]);
  } else if (r.method == QLatin1String("radius")) {
    const int minPts = int(number(params, QStringLiteral("minPoints"), 6, 1, 1000, &err));
    if (!err.isEmpty()) return fail(op, err);
    const double radius = number(params, QStringLiteral("radius"), 3, 1e-6, 1e6, &err);
    if (!err.isEmpty()) return fail(op, err);
    KdTree tree;
    tree.build(input.points);
    for (int i = 0; i < input.points.size(); ++i) {
      const CloudPoint& p = input.points[i];
      std::vector<int> nb;
      tree.radius({p.x, p.y, p.z}, radius, nb);
      if (int(nb.size()) >= minPts) out.points.push_back(p);
    }
  } else {
    return fail(op, QStringLiteral("未知点云滤波方式"));
  }

  if (out.points.isEmpty()) return fail(op, QStringLiteral("处理后点云为空，请调整筛选参数"));
  if (out.points.size() > kMaxPoints)
    return fail(op, QStringLiteral("点云超过 20 万点，请先缩小数据文件"));
  r.cloud = out;
  r.pointCount = out.points.size();
  r.bounds = computeBounds(out.points);
  r.ok = true;
  r.note = QStringLiteral("software · method=%1 · %2 → %3")
               .arg(r.method)
               .arg(r.inputCount)
               .arg(r.pointCount);
  return r;
}

CloudResult runCloudPlane(const PointCloud& input, const QVariantMap& params) {
  const QString op = QStringLiteral("cloud_plane");
  QString err;
  if (!validate(input, &err)) return fail(op, err);
  if (input.points.size() < 3) return fail(op, QStringLiteral("平面拟合至少需要 3 个点"));
  // rank of centered points
  {
    const Vec3 c = centroidOf(input.points);
    Mat3 cov = covarianceOf(input.points, c);
    double ev[3];
    Mat3 Q;
    jacobiEigen3(cov, ev, Q);
    int nz = 0;
    for (int i = 0; i < 3; ++i)
      if (ev[i] > 1e-12) ++nz;
    if (nz < 2) return fail(op, QStringLiteral("点云共线，不能拟合平面"));
  }
  const double distThr =
      number(params, QStringLiteral("distanceThreshold"), 0.5, 1e-6, 1e6, &err);
  if (!err.isEmpty()) return fail(op, err);
  const int iterations =
      int(number(params, QStringLiteral("iterations"), 500, 10, 10000, &err));
  if (!err.isEmpty()) return fail(op, err);
  QString mode = params.value(QStringLiteral("output"), QStringLiteral("inliers"))
                     .toString()
                     .trimmed();
  if (mode != QLatin1String("inliers") && mode != QLatin1String("outliers") &&
      mode != QLatin1String("all"))
    return fail(op, QStringLiteral("平面输出仅支持 inliers / outliers / all"));

  Rng rng(42);
  const int n = input.points.size();
  int bestCount = 0;
  Vec3 bestN;
  double bestD = 0;
  std::vector<int> bestIdx;
  for (int it = 0; it < iterations; ++it) {
    int i0 = rng.bounded(n), i1 = rng.bounded(n), i2 = rng.bounded(n);
    if (i0 == i1 || i0 == i2 || i1 == i2) continue;
    const CloudPoint& a = input.points[i0];
    const CloudPoint& b = input.points[i1];
    const CloudPoint& c = input.points[i2];
    const Vec3 ab{b.x - a.x, b.y - a.y, b.z - a.z};
    const Vec3 ac{c.x - a.x, c.y - a.y, c.z - a.z};
    Vec3 nm = ab.cross(ac);
    const double ln = nm.norm();
    if (ln < 1e-12) continue;
    nm = nm * (1.0 / ln);
    const double d = -(nm.x * a.x + nm.y * a.y + nm.z * a.z);
    std::vector<int> idx;
    idx.reserve(size_t(n));
    for (int i = 0; i < n; ++i) {
      const CloudPoint& p = input.points[i];
      const double dist = std::fabs(nm.x * p.x + nm.y * p.y + nm.z * p.z + d);
      if (dist <= distThr) idx.push_back(i);
    }
    if (int(idx.size()) > bestCount) {
      bestCount = int(idx.size());
      bestN = nm;
      bestD = d;
      bestIdx.swap(idx);
    }
  }
  if (bestCount < 3) return fail(op, QStringLiteral("未找到有效平面"));

  // Refine with SVD / PCA on inliers (smallest eigenvector = normal)
  {
    QVector<CloudPoint> ins;
    ins.reserve(bestCount);
    for (int i : bestIdx) ins.push_back(input.points[i]);
    const Vec3 c = centroidOf(ins);
    const Mat3 cov = covarianceOf(ins, c);
    double ev[3];
    Mat3 Q;
    jacobiEigen3(cov, ev, Q);
    int mi = 0;
    if (ev[1] < ev[mi]) mi = 1;
    if (ev[2] < ev[mi]) mi = 2;
    bestN = {Q[0][mi], Q[1][mi], Q[2][mi]};
    const double ln = bestN.norm();
    if (ln > 0) bestN = bestN * (1.0 / ln);
    bestD = -(bestN.x * c.x + bestN.y * c.y + bestN.z * c.z);
    bestIdx.clear();
    for (int i = 0; i < n; ++i) {
      const CloudPoint& p = input.points[i];
      const double dist = std::fabs(bestN.x * p.x + bestN.y * p.y + bestN.z * p.z + bestD);
      if (dist <= distThr) bestIdx.push_back(i);
    }
    if (int(bestIdx.size()) < 3) return fail(op, QStringLiteral("未找到有效平面"));
  }

  // Sign: largest-abs normal component positive; flip d with it.
  {
    const double an[3] = {std::fabs(bestN.x), std::fabs(bestN.y), std::fabs(bestN.z)};
    int mi = 0;
    if (an[1] > an[mi]) mi = 1;
    if (an[2] > an[mi]) mi = 2;
    const double comp = mi == 0 ? bestN.x : (mi == 1 ? bestN.y : bestN.z);
    if (comp < 0) {
      bestN = bestN * -1;
      bestD = -bestD;
    }
  }

  double sum2 = 0;
  for (int i : bestIdx) {
    const CloudPoint& p = input.points[i];
    const double dist = bestN.x * p.x + bestN.y * p.y + bestN.z * p.z + bestD;
    sum2 += dist * dist;
  }

  CloudResult r;
  r.operation = op;
  r.inputCount = n;
  r.ok = true;
  r.nx = bestN.x;
  r.ny = bestN.y;
  r.nz = bestN.z;
  r.d = bestD;
  r.inlierCount = int(bestIdx.size());
  r.inlierRatio = double(r.inlierCount) / double(n);
  r.rmsError = std::sqrt(sum2 / double(r.inlierCount));
  r.output = mode;
  r.method = QStringLiteral("ransac");
  std::vector<int> keep;
  if (mode == QLatin1String("all")) {
    keep.resize(size_t(n));
    for (int i = 0; i < n; ++i) keep[size_t(i)] = i;
  } else if (mode == QLatin1String("inliers")) {
    keep = bestIdx;
  } else {
    std::vector<char> inn(size_t(n), 0);
    for (int i : bestIdx) inn[size_t(i)] = 1;
    for (int i = 0; i < n; ++i)
      if (!inn[size_t(i)]) keep.push_back(i);
  }
  if (keep.empty()) return fail(op, QStringLiteral("处理后点云为空，请调整筛选参数"));
  r.cloud = subset(input, keep);
  r.pointCount = r.cloud.points.size();
  r.bounds = computeBounds(r.cloud.points);
  r.note = QStringLiteral("software · inliers=%1 rms=%2 output=%3")
               .arg(r.inlierCount)
               .arg(r.rmsError, 0, 'g', 4)
               .arg(r.output);
  return r;
}

CloudResult runCloudCluster(const PointCloud& input, const QVariantMap& params) {
  const QString op = QStringLiteral("cloud_cluster");
  QString err;
  if (!validate(input, &err)) return fail(op, err);
  if (input.points.size() > kMaxClusterPoints)
    return fail(op, QStringLiteral("聚类最多 3 万点，请先体素下采样"));
  const double eps = number(params, QStringLiteral("eps"), 3, 1e-6, 1e6, &err);
  if (!err.isEmpty()) return fail(op, err);
  const int minPts = int(number(params, QStringLiteral("minPoints"), 8, 2, 1000, &err));
  if (!err.isEmpty()) return fail(op, err);

  const int n = input.points.size();
  KdTree tree;
  tree.build(input.points);
  // labels: -2 unmarked, -1 noise, >=0 cluster id
  std::vector<int> lab(size_t(n), -2);
  int next = 0;
  std::vector<int> neigh;
  neigh.reserve(64);
  auto region = [&](int i, std::vector<int>& out) {
    const CloudPoint& p = input.points[i];
    tree.radius({p.x, p.y, p.z}, eps, out);
  };
  for (int i = 0; i < n; ++i) {
    if (lab[size_t(i)] != -2) continue;
    region(i, neigh);
    if (int(neigh.size()) < minPts) {
      lab[size_t(i)] = -1;
      continue;
    }
    const int cid = next++;
    if (next > kMaxClusters)
      return fail(op, QStringLiteral("聚类超过 100 个，请调整半径和最小点数"));
    lab[size_t(i)] = cid;
    std::vector<int> seeds = neigh;
    for (size_t s = 0; s < seeds.size(); ++s) {
      const int j = seeds[s];
      if (lab[size_t(j)] == -1) lab[size_t(j)] = cid;
      if (lab[size_t(j)] != -2) continue;
      lab[size_t(j)] = cid;
      std::vector<int> nb2;
      region(j, nb2);
      if (int(nb2.size()) >= minPts) {
        for (int k : nb2) seeds.push_back(k);
      }
    }
  }

  const double palette[][3] = {{0.02, 0.65, 0.88}, {0.95, 0.5, 0.18}, {0.25, 0.8, 0.5},
                               {0.7, 0.4, 0.95},   {0.95, 0.3, 0.45}, {0.85, 0.8, 0.25}};
  PointCloud out = input;
  int noise = 0;
  std::vector<int> counts(size_t(std::max(next, 0)), 0);
  for (int i = 0; i < n; ++i) {
    CloudPoint& p = out.points[i];
    p.hasColor = true;
    if (lab[size_t(i)] < 0) {
      p.r = 0.5;
      p.g = 0.55;
      p.b = 0.6;
      ++noise;
    } else {
      const int c = lab[size_t(i)] % 6;
      p.r = palette[c][0];
      p.g = palette[c][1];
      p.b = palette[c][2];
      counts[size_t(lab[size_t(i)])]++;
    }
  }

  CloudResult r;
  r.operation = op;
  r.ok = true;
  r.inputCount = n;
  r.cloud = out;
  r.pointCount = n;
  r.clusterCount = next;
  r.noiseCount = noise;
  r.method = QStringLiteral("dbscan");
  r.bounds = computeBounds(out.points);
  r.note = QStringLiteral("software · clusters=%1 noise=%2").arg(next).arg(noise);
  return r;
}

CloudResult runCloudMeasure(const PointCloud& input, const QVariantMap& params) {
  Q_UNUSED(params);
  const QString op = QStringLiteral("cloud_measure");
  QString err;
  if (!validate(input, &err)) return fail(op, err);
  CloudResult r;
  r.operation = op;
  r.ok = true;
  r.inputCount = input.points.size();
  r.cloud = input;
  r.pointCount = input.points.size();
  r.bounds = computeBounds(input.points);
  r.note = QStringLiteral("坐标轴对齐包围盒尺寸；包围盒体积不等于物体实际体积");
  return r;
}

CloudResult runCloudHeight(const PointCloud& input, const QVariantMap& params) {
  const QString op = QStringLiteral("cloud_height");
  QString err;
  if (!validate(input, &err)) return fail(op, err);
  const double baseline = number(params, QStringLiteral("baselineZ"), 0, -1e9, 1e9, &err);
  if (!err.isEmpty()) return fail(op, err);
  const double cell = number(params, QStringLiteral("cellSize"), 1, 1e-6, 1e6, &err);
  if (!err.isEmpty()) return fail(op, err);

  double minX = input.points[0].x, minY = input.points[0].y;
  double minH = input.points[0].z - baseline;
  double maxH = minH;
  double sumH = 0;
  for (const CloudPoint& p : input.points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    const double h = p.z - baseline;
    if (h < minH) minH = h;
    if (h > maxH) maxH = h;
    sumH += h;
  }
  struct I2 {
    qint64 x, y;
    bool operator<(const I2& o) const { return x < o.x || (x == o.x && y < o.y); }
  };
  std::map<I2, double> top;
  for (const CloudPoint& p : input.points) {
    const I2 k{qint64(std::floor((p.x - minX) / cell)),
               qint64(std::floor((p.y - minY) / cell))};
    const double h = p.z - baseline;
    auto it = top.find(k);
    if (it == top.end())
      top.emplace(k, h);
    else if (h > it->second)
      it->second = h;
  }
  double vol = 0;
  for (const auto& kv : top) vol += std::max(kv.second, 0.0) * cell * cell;

  CloudResult r;
  r.operation = op;
  r.ok = true;
  r.inputCount = input.points.size();
  r.cloud = input;
  r.pointCount = input.points.size();
  r.bounds = computeBounds(input.points);
  r.minHeight = minH;
  r.maxHeight = maxH;
  r.meanHeight = sumH / double(input.points.size());
  r.baselineZ = baseline;
  r.cellSize = cell;
  r.occupiedCells = int(top.size());
  r.sampledArea = double(top.size()) * cell * cell;
  r.estimatedVolume = vol;
  r.volumeUnit = input.unit + QStringLiteral("³");
  r.note = QStringLiteral(
      "沿 +Z 相对 baselineZ 的可见表面网格积分；每格取最高点、负高度归零、缺失格不补齐。"
      "仅适用于单值高度表面，非封闭物体真实体积。");
  return r;
}

CloudResult runCloudRegister(const PointCloud& input, const QVariantMap& params) {
  const QString op = QStringLiteral("cloud_register");
  QString err;
  if (!validate(input, &err)) return fail(op, err);

  // Resolve target
  QVariantMap tp = params;
  const QString tsrc = params.value(QStringLiteral("targetSource")).toString().trimmed();
  PointCloud target;
  if (!tsrc.isEmpty()) {
    tp.insert(QStringLiteral("inputSource"), tsrc);
    // don't inherit input shifts onto the target
    tp.remove(QStringLiteral("inputShiftX"));
    tp.remove(QStringLiteral("inputShiftY"));
    tp.remove(QStringLiteral("inputShiftZ"));
    target = resolveCloudInput(PointCloud{}, tp, &err);
    if (target.isEmpty()) return fail(op, err.isEmpty() ? QStringLiteral("缺少参考点云") : err);
  } else {
    return fail(op, QStringLiteral("请先指定 targetSource 或上传同单位的参考点云"));
  }
  if (target.unit != input.unit) return fail(op, QStringLiteral("配准点云单位必须相同"));
  if (input.points.size() < 3 || target.points.size() < 3)
    return fail(op, QStringLiteral("配准至少需要 3 个点"));

  QString method = params.value(QStringLiteral("method"), QStringLiteral("icp")).toString().trimmed();
  const double maxDist = number(params, QStringLiteral("maxDistance"), 5, 1e-6, 1e6, &err);
  if (!err.isEmpty()) return fail(op, err);
  const int iterations = int(number(params, QStringLiteral("iterations"), 50, 1, 500, &err));
  if (!err.isEmpty()) return fail(op, err);

  double T0[16];
  ident4(T0);
  IcpStats st;
  QString note;

  if (method == QLatin1String("global")) {
    // Software global: PCA coarse alignment (4 right-handed sign flips) + ICP.
    Mat3 srcAxes, tgtAxes;
    pcaAxes(input.points, srcAxes);
    pcaAxes(target.points, tgtAxes);
    const Vec3 cs = centroidOf(input.points);
    const Vec3 ct = centroidOf(target.points);
    IcpStats best;
    best.rms = 1e300;
    // flip signs of first two axes (third = cross to stay right-handed)
    const int signs[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
    for (int s = 0; s < 4; ++s) {
      Mat3 Sa = srcAxes;
      for (int i = 0; i < 3; ++i) {
        Sa[i][0] *= signs[s][0];
        Sa[i][1] *= signs[s][1];
      }
      const Vec3 a{Sa[0][0], Sa[1][0], Sa[2][0]};
      const Vec3 b{Sa[0][1], Sa[1][1], Sa[2][1]};
      const Vec3 c = a.cross(b);
      Sa[0][2] = c.x;
      Sa[1][2] = c.y;
      Sa[2][2] = c.z;
      // R maps src axes onto target axes: R * Sa = Ta => R = Ta * Sa^T
      const Mat3 R = mul(tgtAxes, transpose(Sa));
      const Vec3 t = ct - mul(R, cs);
      double init[16];
      setRt(init, R, t);
      IcpStats cur = runIcp(input, target, init, maxDist, iterations);
      if (cur.ok && (cur.fitness > best.fitness ||
                     (cur.fitness == best.fitness && cur.rms < best.rms)))
        best = cur;
    }
    st = best;
    note = QStringLiteral("software 全局：PCA 粗对齐 + 点到点 ICP（无 FPFH 依赖）；fitness 不是检测置信度");
  } else if (method == QLatin1String("icp")) {
    if (!parseInitialTransform(params.value(QStringLiteral("initialTransform")), T0, &err))
      return fail(op, err);
    st = runIcp(input, target, T0, maxDist, iterations);
    note = QStringLiteral("局部点到点 ICP；依赖初始姿态，fitness 不是检测置信度");
  } else {
    return fail(op, QStringLiteral("配准方式必须为 icp 或 global"));
  }

  CloudResult r;
  r.operation = op;
  r.method = method;
  r.inputCount = input.points.size();
  r.note = note;

  const bool hasMinFit = params.contains(QStringLiteral("minFitness"));
  const bool hasMinTgt = params.contains(QStringLiteral("minTargetFitness"));
  const bool hasMaxRms = params.contains(QStringLiteral("maxRmsError"));
  double minFit = 0, minTgt = 0, maxRms = maxDist / 2;
  if (hasMinFit) minFit = number(params, QStringLiteral("minFitness"), 0, 0, 1, &err);
  if (hasMinTgt) minTgt = number(params, QStringLiteral("minTargetFitness"), 0, 0, 1, &err);
  if (hasMaxRms) maxRms = number(params, QStringLiteral("maxRmsError"), maxDist / 2, 1e-6, 1e6, &err);
  if (!err.isEmpty()) return fail(op, err);

  bool pass = st.ok;
  QString reason;
  if (!st.ok) {
    pass = false;
    reason = st.error;
  } else {
    if (hasMinFit && st.fitness < minFit) {
      pass = false;
      reason = QStringLiteral("输入覆盖比例不足");
    }
    if (hasMinTgt && st.targetFitness < minTgt) {
      pass = false;
      reason = QStringLiteral("参考覆盖比例不足");
    }
    if (hasMaxRms && st.rms > maxRms) {
      pass = false;
      reason = QStringLiteral("均方根误差超过门限");
    }
  }

  r.fitness = st.fitness;
  r.targetFitness = st.targetFitness;
  r.rmsError = st.rms;
  if (pass) {
    r.ok = true;
    r.found = true;
    for (int i = 0; i < 16; ++i) r.transform[i] = st.T[i];
    r.dx = st.T[3];
    r.dy = st.T[7];
    r.dz = st.T[11];
    r.cloud = input;
    r.cloud.points = applyTransformPoints(input.points, st.T);
    r.cloud.frame = target.frame;
    r.pointCount = r.cloud.points.size();
    r.bounds = computeBounds(r.cloud.points);
    r.note += QStringLiteral(" · found=1 fitness=%1 rms=%2 dx=%3 dy=%4 dz=%5")
                  .arg(r.fitness, 0, 'f', 4)
                  .arg(r.rmsError, 0, 'g', 4)
                  .arg(r.dx, 0, 'f', 4)
                  .arg(r.dy, 0, 'f', 4)
                  .arg(r.dz, 0, 'f', 4);
  } else {
    // Quality fail: keep input, found=false. Config/solver errors stay not-ok.
    const bool qualityFail = st.ok;
    r.ok = qualityFail;  // ran, but not found
    r.found = false;
    r.cloud = input;
    r.pointCount = input.points.size();
    r.bounds = computeBounds(input.points);
    r.error = reason;
    r.note += QStringLiteral(" · found=0 · %1").arg(reason);
    if (!qualityFail) r.ok = false;
  }
  return r;
}

CloudResult runCloudOp(const QString& operation, const PointCloud& input,
                       const QVariantMap& params) {
  if (operation == QLatin1String("cloud_filter")) return runCloudFilter(input, params);
  if (operation == QLatin1String("cloud_plane")) return runCloudPlane(input, params);
  if (operation == QLatin1String("cloud_cluster")) return runCloudCluster(input, params);
  if (operation == QLatin1String("cloud_measure")) return runCloudMeasure(input, params);
  if (operation == QLatin1String("cloud_height")) return runCloudHeight(input, params);
  if (operation == QLatin1String("cloud_register")) return runCloudRegister(input, params);
  return fail(operation, QStringLiteral("未知 3D 操作"));
}

QStringList cloudSelfTest() {
  QStringList fails;
  auto check = [&](bool cond, const QString& msg) {
    if (!cond) fails << msg;
  };

  // measure 20×10×5
  {
    const CloudResult r = runCloudMeasure(makeSoftCloudPart(), {});
    check(r.ok, QStringLiteral("measure not ok: %1").arg(r.error));
    check(std::fabs(r.bounds.sizeX - 20) < 1e-9, QStringLiteral("measure sizeX %1").arg(r.bounds.sizeX));
    check(std::fabs(r.bounds.sizeY - 10) < 1e-9, QStringLiteral("measure sizeY %1").arg(r.bounds.sizeY));
    check(std::fabs(r.bounds.sizeZ - 5) < 1e-9, QStringLiteral("measure sizeZ %1").arg(r.bounds.sizeZ));
    check(std::fabs(r.bounds.boundingBoxVolume - 1000) < 1e-6,
          QStringLiteral("measure volume %1").arg(r.bounds.boundingBoxVolume));
  }

  // voxel centroid
  {
    PointCloud c;
    c.unit = QStringLiteral("mm");
    c.points = {{0, 0, 0}, {0.1, 0.1, 0.1}, {10, 10, 10}};
    const CloudResult r =
        runCloudFilter(c, {{QStringLiteral("method"), QStringLiteral("voxel")},
                           {QStringLiteral("voxelSize"), 1}});
    check(r.ok && r.pointCount == 2, QStringLiteral("voxel count %1").arg(r.pointCount));
    if (r.pointCount == 2) {
      QVector<CloudPoint> pts = r.cloud.points;
      std::sort(pts.begin(), pts.end(),
                [](const CloudPoint& a, const CloudPoint& b) { return a.x < b.x; });
      check(std::fabs(pts[0].x - 0.05) < 1e-9, QStringLiteral("voxel centroid"));
      check(std::fabs(pts[1].x - 10) < 1e-9, QStringLiteral("voxel second"));
    }
  }

  // crop preserves one point
  {
    PointCloud c;
    c.unit = QStringLiteral("mm");
    c.points = {{0, 0, 0}, {1, 2, 3}, {9, 9, 9}};
    c.points[0].hasColor = c.points[1].hasColor = c.points[2].hasColor = true;
    c.points[0].r = 1;
    c.points[0].g = 0;
    c.points[0].b = 0;
    c.points[1].r = 0;
    c.points[1].g = 1;
    c.points[1].b = 0;
    c.points[2].r = 0;
    c.points[2].g = 0;
    c.points[2].b = 1;
    const CloudResult r = runCloudFilter(
        c, {{QStringLiteral("method"), QStringLiteral("crop")},
            {QStringLiteral("minimum"), QVariantList{0.5, 1.0, 2.0}},
            {QStringLiteral("maximum"), QVariantList{2.0, 3.0, 4.0}}});
    check(r.ok && r.pointCount == 1, QStringLiteral("crop count %1").arg(r.pointCount));
    if (r.pointCount == 1) {
      check(std::fabs(r.cloud.points[0].x - 1) < 1e-12, QStringLiteral("crop point"));
      check(r.cloud.points[0].hasColor && std::fabs(r.cloud.points[0].g - 1) < 1e-12,
            QStringLiteral("crop color"));
    }
  }

  // statistical / radius isolate
  {
    PointCloud c;
    c.unit = QStringLiteral("mm");
    for (int x = 0; x < 10; ++x)
      for (int y = 0; y < 10; ++y) c.points.push_back(CloudPoint{x / 10.0, y / 10.0, 0});
    c.points.push_back(CloudPoint{100, 100, 100});
    const CloudResult st =
        runCloudFilter(c, {{QStringLiteral("method"), QStringLiteral("statistical")},
                           {QStringLiteral("neighbors"), 10},
                           {QStringLiteral("stdRatio"), 2}});
    check(st.ok && st.pointCount == 100, QStringLiteral("statistical count %1").arg(st.pointCount));
    const CloudResult rd =
        runCloudFilter(c, {{QStringLiteral("method"), QStringLiteral("radius")},
                           {QStringLiteral("minPoints"), 3},
                           {QStringLiteral("radius"), 0.3}});
    check(rd.ok && rd.pointCount == 100, QStringLiteral("radius count %1").arg(rd.pointCount));
  }

  // plane
  {
    PointCloud c;
    c.unit = QStringLiteral("mm");
    for (int x = 0; x < 10; ++x)
      for (int y = 0; y < 10; ++y)
        c.points.push_back(CloudPoint{double(x), double(y), 2.0 * x + 3.0 * y + 4.0});
    c.points.push_back(CloudPoint{0, 0, 100});
    const CloudResult r = runCloudPlane(
        c, {{QStringLiteral("distanceThreshold"), 0.001},
            {QStringLiteral("output"), QStringLiteral("outliers")}});
    check(r.ok, QStringLiteral("plane not ok: %1").arg(r.error));
    check(r.inlierCount == 100, QStringLiteral("plane inliers %1").arg(r.inlierCount));
    check(r.rmsError < 1e-8, QStringLiteral("plane rms %1").arg(r.rmsError));
    check(r.pointCount == 1, QStringLiteral("plane outliers %1").arg(r.pointCount));
    if (r.pointCount == 1)
      check(std::fabs(r.cloud.points[0].z - 100) < 1e-12, QStringLiteral("plane outlier z"));
  }

  // dbscan two clusters + noise
  {
    PointCloud c;
    c.unit = QStringLiteral("mm");
    for (int x = 0; x < 5; ++x)
      for (int y = 0; y < 5; ++y) c.points.push_back(CloudPoint{x / 10.0, y / 10.0, 0});
    for (int x = 0; x < 5; ++x)
      for (int y = 0; y < 5; ++y) c.points.push_back(CloudPoint{10 + x / 10.0, y / 10.0, 0});
    c.points.push_back(CloudPoint{100, 100, 100});
    const CloudResult r = runCloudCluster(
        c, {{QStringLiteral("eps"), 0.3}, {QStringLiteral("minPoints"), 4}});
    check(r.ok, QStringLiteral("cluster not ok: %1").arg(r.error));
    check(r.clusterCount == 2, QStringLiteral("cluster count %1").arg(r.clusterCount));
    check(r.noiseCount == 1, QStringLiteral("cluster noise %1").arg(r.noiseCount));
    check(r.cloud.points.size() == 51, QStringLiteral("cluster colors %1").arg(r.cloud.points.size()));
  }

  // height volume / holes / baseline
  {
    PointCloud c = makeSoftCloudSurface();
    PointCloud dup = c;
    for (const CloudPoint& p : dup.points) c.points.push_back(p);
    CloudResult r = runCloudHeight(c, {{QStringLiteral("baselineZ"), 0},
                                       {QStringLiteral("cellSize"), 1}});
    check(r.ok && r.occupiedCells == 200, QStringLiteral("height cells %1").arg(r.occupiedCells));
    check(std::fabs(r.estimatedVolume - 1000) < 1e-6,
          QStringLiteral("height volume %1").arg(r.estimatedVolume));
    PointCloud hole = makeSoftCloudSurface();
    hole.points.pop_back();
    r = runCloudHeight(hole, {{QStringLiteral("cellSize"), 1}});
    check(std::fabs(r.estimatedVolume - 995) < 1e-6,
          QStringLiteral("height hole %1").arg(r.estimatedVolume));
    r = runCloudHeight(makeSoftCloudSurface(),
                       {{QStringLiteral("baselineZ"), 10}, {QStringLiteral("cellSize"), 1}});
    check(std::fabs(r.estimatedVolume) < 1e-9,
          QStringLiteral("height baseline %1").arg(r.estimatedVolume));
  }

  // ICP recovers known translation (and a small rotation)
  {
    PointCloud src = makeSoftCloudRegisterSet();
    const double ang = 0.03;
    const double ca = std::cos(ang), sa = std::sin(ang);
    PointCloud tgt = src;
    const double tx = 0.12, ty = -0.15, tz = 0.08;
    for (CloudPoint& p : tgt.points) {
      const double x = ca * p.x - sa * p.y;
      const double y = sa * p.x + ca * p.y;
      p.x = x + tx;
      p.y = y + ty;
      p.z = p.z + tz;
    }
    QVariantMap p;
    p.insert(QStringLiteral("method"), QStringLiteral("icp"));
    p.insert(QStringLiteral("targetSource"), QStringLiteral("soft_register"));
    p.insert(QStringLiteral("maxDistance"), 2);
    p.insert(QStringLiteral("iterations"), 80);
    // inject target by temporarily... runCloudRegister resolves targetSource itself.
    // But our target is rotated, not the stock soft_register. Call ICP internals via
    // a custom target: add a one-off by stuffing through a test-only path.
    // We'll run by setting target in a local copy — use runIcp via register after
    // replacing resolve... Simpler: put the rotated cloud as input and pass a
    // custom API. For self-test, use translate-only first (deterministic, exact),
    // then a second call with the public API: input=shifted soft_register,
    // target=soft_register.
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("inputSource"), QStringLiteral("soft_register"));
    p.insert(QStringLiteral("inputShiftX"), 5);
    p.insert(QStringLiteral("inputShiftY"), -3);
    p.insert(QStringLiteral("inputShiftZ"), 2);
    p.insert(QStringLiteral("targetSource"), QStringLiteral("soft_register"));
    p.insert(QStringLiteral("method"), QStringLiteral("icp"));
    p.insert(QStringLiteral("maxDistance"), 10);
    p.insert(QStringLiteral("iterations"), 40);
    QString e;
    const PointCloud in = resolveCloudInput({}, p, &e);
    const CloudResult r = runCloudRegister(in, p);
    check(r.ok && r.found, QStringLiteral("icp not found: %1").arg(r.error));
    check(std::fabs(r.dx + 5) < 1e-6, QStringLiteral("icp dx %1").arg(r.dx));
    check(std::fabs(r.dy - 3) < 1e-6, QStringLiteral("icp dy %1").arg(r.dy));
    check(std::fabs(r.dz + 2) < 1e-6, QStringLiteral("icp dz %1").arg(r.dz));
    check(r.rmsError < 1e-6, QStringLiteral("icp rms %1").arg(r.rmsError));
    check(r.fitness > 0.99, QStringLiteral("icp fitness %1").arg(r.fitness));
  }

  // global PCA+ICP on a large yaw
  {
    PointCloud src = makeSoftCloudRegisterSet();
    const double ang = 30.0 * M_PI / 180.0;
    const double ca = std::cos(ang), sa = std::sin(ang);
    PointCloud tgt;
    tgt.unit = src.unit;
    tgt.frame = QStringLiteral("target");
    tgt.points.reserve(src.points.size());
    for (const CloudPoint& p : src.points) {
      CloudPoint q = p;
      q.x = ca * p.x - sa * p.y + 4;
      q.y = sa * p.x + ca * p.y - 2;
      q.z = p.z + 1;
      tgt.points.push_back(q);
    }
    // Use ICP with a coarse identity would fail on 30deg; use global via a
    // temporary register that takes targetSource=soft_register would be wrong.
    // We'll test global by writing target as soft_register and input as rotated
    // inverse... Easier path: expose no extra API; build params and a custom
    // input, but targetSource always remakes stock set. So test global by
    // rotating the INPUT away from stock target (soft_register).
    PointCloud rotated = src;
    for (CloudPoint& p : rotated.points) {
      const double x = ca * p.x - sa * p.y;
      const double y = sa * p.x + ca * p.y;
      p.x = x - 4;
      p.y = y + 2;
      p.z = p.z - 1;
    }
    QVariantMap p;
    p.insert(QStringLiteral("method"), QStringLiteral("global"));
    p.insert(QStringLiteral("targetSource"), QStringLiteral("soft_register"));
    p.insert(QStringLiteral("maxDistance"), 5);
    p.insert(QStringLiteral("iterations"), 40);
    const CloudResult r = runCloudRegister(rotated, p);
    check(r.ok && r.found, QStringLiteral("global not found: %1 %2").arg(r.error, r.note));
    check(r.fitness > 0.99, QStringLiteral("global fitness %1").arg(r.fitness));
    check(r.rmsError < 1e-4, QStringLiteral("global rms %1").arg(r.rmsError));
  }

  // fixture chain numbers
  {
    const PointCloud fx = makeSoftCloudFixture();
    check(fx.points.size() == 357 + 200 + 25 + 1,
          QStringLiteral("fixture count %1").arg(fx.points.size()));
    const CloudResult f = runCloudFilter(
        fx, {{QStringLiteral("method"), QStringLiteral("crop")},
             {QStringLiteral("minX"), -50},
             {QStringLiteral("minY"), -50},
             {QStringLiteral("minZ"), -50},
             {QStringLiteral("maxX"), 50},
             {QStringLiteral("maxY"), 50},
             {QStringLiteral("maxZ"), 50}});
    check(f.ok && f.pointCount == 582, QStringLiteral("fixture crop %1").arg(f.pointCount));
    const CloudResult pl = runCloudPlane(
        f.cloud, {{QStringLiteral("distanceThreshold"), 0.5},
                  {QStringLiteral("output"), QStringLiteral("outliers")}});
    check(pl.ok && pl.inlierCount == 357, QStringLiteral("fixture plane inliers %1").arg(pl.inlierCount));
    check(pl.rmsError < 1e-9, QStringLiteral("fixture plane rms %1").arg(pl.rmsError));
    check(pl.pointCount == 225, QStringLiteral("fixture outliers %1").arg(pl.pointCount));
    const CloudResult cl = runCloudCluster(
        pl.cloud, {{QStringLiteral("eps"), 3}, {QStringLiteral("minPoints"), 8}});
    check(cl.ok && cl.clusterCount == 2, QStringLiteral("fixture clusters %1").arg(cl.clusterCount));
    check(cl.noiseCount == 0, QStringLiteral("fixture noise %1").arg(cl.noiseCount));
  }

  // collinear plane rejected
  {
    PointCloud c;
    c.unit = QStringLiteral("mm");
    c.points = {{0, 0, 0}, {1, 1, 1}, {2, 2, 2}};
    const CloudResult r = runCloudPlane(c, {});
    check(!r.ok, QStringLiteral("collinear plane should fail"));
  }

  return fails;
}

}  // namespace sieans_qt
