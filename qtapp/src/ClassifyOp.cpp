#include "ClassifyOp.hpp"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <numeric>
#include <random>
#include <sstream>
#include <vector>

namespace sieans_qt {
namespace {

constexpr int kMaxSamples = 5000;
constexpr int kMaxDim = 32;

struct Sample {
  std::vector<double> x;
  QString label;
};

/** 点积。长度以较短为准。 */
double dot(const std::vector<double>& a, const std::vector<double>& b) {
  const int n = static_cast<int>(std::min(a.size(), b.size()));
  double s = 0;
  for (int i = 0; i < n; ++i) s += a[static_cast<size_t>(i)] * b[static_cast<size_t>(i)];
  return s;
}

/** 欧氏距离平方。 */
double dist2(const std::vector<double>& a, const std::vector<double>& b) {
  const int n = static_cast<int>(std::min(a.size(), b.size()));
  double s = 0;
  for (int i = 0; i < n; ++i) {
    const double d = a[static_cast<size_t>(i)] - b[static_cast<size_t>(i)];
    s += d * d;
  }
  return s;
}

/** 把 QVariant 解析成特征维。 */
bool parseVector(const QVariant& v, std::vector<double>& out, QString* err) {
  out.clear();
  if (v.metaType().id() == QMetaType::QVariantList || v.userType() == QMetaType::QStringList) {
    const QVariantList lst = v.toList();
    out.reserve(lst.size());
    for (const QVariant& x : lst) {
      bool ok = false;
      out.push_back(x.toDouble(&ok));
      if (!ok) {
        if (err) *err = QStringLiteral("non-numeric feature");
        return false;
      }
    }
    return !out.empty();
  }
  const QString s = v.toString().trimmed();
  if (s.isEmpty()) {
    if (err) *err = QStringLiteral("empty features");
    return false;
  }
  if (s.startsWith(QLatin1Char('['))) {
    QJsonParseError pe;
    const QJsonDocument d = QJsonDocument::fromJson(s.toUtf8(), &pe);
    if (pe.error != QJsonParseError::NoError || !d.isArray()) {
      if (err) *err = QStringLiteral("features JSON parse error");
      return false;
    }
    for (const QJsonValue& x : d.array()) out.push_back(x.toDouble());
    return !out.empty();
  }
  const QStringList parts = s.split(QLatin1Char(','), Qt::SkipEmptyParts);
  for (const QString& p : parts) {
    bool ok = false;
    out.push_back(p.trimmed().toDouble(&ok));
    if (!ok) {
      if (err) *err = QStringLiteral("non-numeric feature");
      return false;
    }
  }
  return !out.empty();
}

/** 解析一行 CSV：最后一列是标签，前面是特征。 */
bool parseCsvLine(const QString& line, Sample& s) {
  const QString t = line.trimmed();
  if (t.isEmpty() || t.startsWith(QLatin1Char('#'))) return false;
  const QStringList parts = t.split(QLatin1Char(','), Qt::KeepEmptyParts);
  if (parts.size() < 2) return false;
  s.x.clear();
  for (int i = 0; i < parts.size() - 1; ++i) {
    bool ok = false;
    s.x.push_back(parts[i].trimmed().toDouble(&ok));
    if (!ok) return false;
  }
  s.label = parts.last().trimmed();
  return !s.x.empty() && !s.label.isEmpty();
}

/** 从 JSON 数组解析样本。 */
bool parseJsonSamples(const QJsonArray& arr, std::vector<Sample>& out, QString* err) {
  for (const QJsonValue& v : arr) {
    if (!v.isObject()) {
      if (err) *err = QStringLiteral("sample entry is not an object");
      return false;
    }
    const QJsonObject o = v.toObject();
    Sample s;
    QVariant feats;
    if (o.contains(QStringLiteral("features")))
      feats = o.value(QStringLiteral("features")).toVariant();
    else if (o.contains(QStringLiteral("x")))
      feats = o.value(QStringLiteral("x")).toVariant();
    QString pe;
    if (!parseVector(feats, s.x, &pe)) {
      if (err) *err = pe.isEmpty() ? QStringLiteral("bad sample features") : pe;
      return false;
    }
    if (o.contains(QStringLiteral("label")))
      s.label = o.value(QStringLiteral("label")).toVariant().toString();
    else if (o.contains(QStringLiteral("y")))
      s.label = o.value(QStringLiteral("y")).toVariant().toString();
    if (s.label.isEmpty()) {
      if (err) *err = QStringLiteral("sample missing label");
      return false;
    }
    out.push_back(std::move(s));
  }
  return true;
}

/** 从文本（JSON 或 CSV）解析样本表。 */
bool parseSampleText(const QString& text, std::vector<Sample>& out, QString* err) {
  const QString t = text.trimmed();
  if (t.isEmpty()) {
    if (err) *err = QStringLiteral("empty samples");
    return false;
  }
  if (t.startsWith(QLatin1Char('[')) || t.startsWith(QLatin1Char('{'))) {
    QJsonParseError pe;
    const QJsonDocument d = QJsonDocument::fromJson(t.toUtf8(), &pe);
    if (pe.error != QJsonParseError::NoError) {
      if (err) *err = QStringLiteral("samples JSON parse error");
      return false;
    }
    if (d.isArray()) return parseJsonSamples(d.array(), out, err);
    if (d.isObject()) {
      const QJsonObject o = d.object();
      QJsonArray arr = o.value(QStringLiteral("samples")).toArray();
      if (arr.isEmpty()) arr = o.value(QStringLiteral("data")).toArray();
      if (arr.isEmpty()) {
        if (err) *err = QStringLiteral("JSON object has no samples array");
        return false;
      }
      return parseJsonSamples(arr, out, err);
    }
  }
  const QStringList lines = text.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
  for (const QString& line : lines) {
    Sample s;
    if (parseCsvLine(line, s)) out.push_back(std::move(s));
  }
  if (out.empty()) {
    if (err) *err = QStringLiteral("no CSV samples parsed");
    return false;
  }
  return true;
}

/** 在若干根目录下解析本地样本文件。 */
QString resolveSamplePath(const QString& raw, const QString& baseDir) {
  const QString path = raw.trimmed();
  if (path.isEmpty()) return {};
  const QFileInfo direct(path);
  if (direct.isAbsolute() && direct.isFile()) return direct.absoluteFilePath();
  QStringList roots;
  if (!baseDir.trimmed().isEmpty()) roots << baseDir;
  roots << QDir::currentPath();
  if (direct.isAbsolute()) return direct.exists() ? direct.absoluteFilePath() : QString();
  for (const QString& root : roots) {
    const QFileInfo fi(QDir(root).filePath(path));
    if (fi.isFile()) return fi.absoluteFilePath();
  }
  return {};
}

/** 读本地文件为文本。 */
bool readFileText(const QString& path, QString& text, QString* err) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly)) {
    if (err) *err = QStringLiteral("cannot open sample file %1").arg(path);
    return false;
  }
  text = QString::fromUtf8(f.readAll());
  return true;
}

/** 收集标签并检查维数一致。 */
bool normalizeTable(std::vector<Sample>& tab, QStringList& labels, int& dim, QString* err) {
  if (tab.empty()) {
    if (err) *err = QStringLiteral("no training samples");
    return false;
  }
  if (static_cast<int>(tab.size()) > kMaxSamples) {
    if (err) *err = QStringLiteral("too many samples (max %1)").arg(kMaxSamples);
    return false;
  }
  dim = static_cast<int>(tab.front().x.size());
  if (dim <= 0 || dim > kMaxDim) {
    if (err) *err = QStringLiteral("feature dim must be 1–%1").arg(kMaxDim);
    return false;
  }
  for (const Sample& s : tab) {
    if (static_cast<int>(s.x.size()) != dim) {
      if (err) *err = QStringLiteral("inconsistent feature dim");
      return false;
    }
    if (!labels.contains(s.label)) labels.push_back(s.label);
  }
  if (labels.size() < 2) {
    if (err) *err = QStringLiteral("need at least two classes");
    return false;
  }
  return true;
}

/** 用训练集均值/标准差标准化；标准差下限 1e-6。 */
void fitScaler(const std::vector<Sample>& tab, int dim, std::vector<double>& mean,
               std::vector<double>& invStd) {
  mean.assign(static_cast<size_t>(dim), 0.0);
  invStd.assign(static_cast<size_t>(dim), 1.0);
  const int n = static_cast<int>(tab.size());
  if (n <= 0) return;
  for (const Sample& s : tab)
    for (int d = 0; d < dim; ++d) mean[static_cast<size_t>(d)] += s.x[static_cast<size_t>(d)];
  for (int d = 0; d < dim; ++d) mean[static_cast<size_t>(d)] /= n;
  std::vector<double> var(static_cast<size_t>(dim), 0.0);
  for (const Sample& s : tab) {
    for (int d = 0; d < dim; ++d) {
      const double e = s.x[static_cast<size_t>(d)] - mean[static_cast<size_t>(d)];
      var[static_cast<size_t>(d)] += e * e;
    }
  }
  for (int d = 0; d < dim; ++d) {
    const double sd = std::sqrt(var[static_cast<size_t>(d)] / std::max(1, n - 1));
    invStd[static_cast<size_t>(d)] = 1.0 / std::max(sd, 1e-6);
  }
}

/** 按已拟合的缩放变换一个向量。 */
std::vector<double> applyScaler(const std::vector<double>& x, const std::vector<double>& mean,
                                const std::vector<double>& invStd) {
  std::vector<double> y(x.size(), 0.0);
  const int n = static_cast<int>(std::min({x.size(), mean.size(), invStd.size()}));
  for (int i = 0; i < n; ++i)
    y[static_cast<size_t>(i)] = (x[static_cast<size_t>(i)] - mean[static_cast<size_t>(i)]) *
                                invStd[static_cast<size_t>(i)];
  return y;
}

struct ModelOut {
  int index = -1;
  double score = 0;
};

/** 把决策值映射到 (0,1)。 */
double scoreFromMargin(double z) { return 1.0 / (1.0 + std::exp(-z)); }

/** k 近邻。 */
ModelOut predictKnn(const std::vector<std::vector<double>>& xs, const std::vector<int>& ys,
                    const std::vector<double>& q, int k, bool weighted, int nClass) {
  ModelOut o;
  const int n = static_cast<int>(xs.size());
  k = qBound(1, k, n);
  struct Hit {
    double d;
    int y;
  };
  std::vector<Hit> hits;
  hits.reserve(static_cast<size_t>(n));
  for (int i = 0; i < n; ++i) hits.push_back({dist2(xs[i], q), ys[static_cast<size_t>(i)]});
  std::partial_sort(hits.begin(), hits.begin() + k, hits.end(),
                    [](const Hit& a, const Hit& b) { return a.d < b.d; });
  std::vector<double> votes(static_cast<size_t>(nClass), 0.0);
  for (int i = 0; i < k; ++i) {
    const double w = weighted ? 1.0 / (std::sqrt(hits[static_cast<size_t>(i)].d) + 1e-9) : 1.0;
    votes[static_cast<size_t>(hits[static_cast<size_t>(i)].y)] += w;
  }
  int best = 0;
  for (int c = 1; c < nClass; ++c)
    if (votes[static_cast<size_t>(c)] > votes[static_cast<size_t>(best)]) best = c;
  double tot = 0;
  for (double v : votes) tot += v;
  o.index = best;
  o.score = tot > 0 ? votes[static_cast<size_t>(best)] / tot : 0;
  return o;
}

/**
 * 线性 L2-SVM（Pegasos 风格铰链损失）。两类时训练一个 ±1 分类器；
 * 多类走一对多，取决策值最大的一类。
 */
ModelOut predictSvmLinear(const std::vector<std::vector<double>>& xs, const std::vector<int>& ys,
                          const std::vector<double>& q, int nClass, double C, int epochs, unsigned seed) {
  const int n = static_cast<int>(xs.size());
  const int dim = xs.empty() ? 0 : static_cast<int>(xs.front().size());
  const double lambda = 1.0 / std::max(C, 1e-6);
  auto trainOne = [&](int posClass, std::vector<double>& w, double& b) {
    w.assign(static_cast<size_t>(dim), 0.0);
    b = 0;
    std::mt19937 rng(seed + static_cast<unsigned>(posClass) * 17u + 1u);
    std::vector<int> order(static_cast<size_t>(n));
    std::iota(order.begin(), order.end(), 0);
    int t = 0;
    for (int ep = 0; ep < epochs; ++ep) {
      std::shuffle(order.begin(), order.end(), rng);
      for (int idx : order) {
        ++t;
        const double eta = 1.0 / (lambda * static_cast<double>(t));
        const double y = (ys[static_cast<size_t>(idx)] == posClass) ? 1.0 : -1.0;
        const double m = y * (dot(w, xs[static_cast<size_t>(idx)]) + b);
        for (int d = 0; d < dim; ++d) w[static_cast<size_t>(d)] *= (1.0 - eta * lambda);
        if (m < 1.0) {
          for (int d = 0; d < dim; ++d)
            w[static_cast<size_t>(d)] += eta * y * xs[static_cast<size_t>(idx)][static_cast<size_t>(d)];
          b += eta * y;
        }
      }
    }
  };

  ModelOut o;
  if (nClass == 2) {
    std::vector<double> w;
    double b = 0;
    trainOne(1, w, b);
    const double z = dot(w, q) + b;
    o.index = z >= 0 ? 1 : 0;
    o.score = o.index == 1 ? scoreFromMargin(z) : scoreFromMargin(-z);
    return o;
  }
  std::vector<double> dec(static_cast<size_t>(nClass), 0.0);
  for (int c = 0; c < nClass; ++c) {
    std::vector<double> w;
    double b = 0;
    trainOne(c, w, b);
    dec[static_cast<size_t>(c)] = dot(w, q) + b;
  }
  int best = 0;
  for (int c = 1; c < nClass; ++c)
    if (dec[static_cast<size_t>(c)] > dec[static_cast<size_t>(best)]) best = c;
  o.index = best;
  o.score = scoreFromMargin(dec[static_cast<size_t>(best)]);
  return o;
}

/** RBF 核铰链对偶梯度（不是完整 SMO）。 */
ModelOut predictSvmRbf(const std::vector<std::vector<double>>& xs, const std::vector<int>& ys,
                       const std::vector<double>& q, int nClass, double C, double gamma, int epochs,
                       unsigned seed) {
  const int n = static_cast<int>(xs.size());
  auto kernel = [&](const std::vector<double>& a, const std::vector<double>& b) {
    return std::exp(-gamma * dist2(a, b));
  };
  auto trainOne = [&](int posClass, std::vector<double>& alpha, double& b) {
    alpha.assign(static_cast<size_t>(n), 0.0);
    b = 0;
    const double lr = 0.1;
    std::mt19937 rng(seed + static_cast<unsigned>(posClass) * 31u + 3u);
    std::vector<int> order(static_cast<size_t>(n));
    std::iota(order.begin(), order.end(), 0);
    for (int ep = 0; ep < epochs; ++ep) {
      std::shuffle(order.begin(), order.end(), rng);
      for (int i : order) {
        const double y = (ys[static_cast<size_t>(i)] == posClass) ? 1.0 : -1.0;
        double f = b;
        for (int j = 0; j < n; ++j) f += alpha[static_cast<size_t>(j)] * kernel(xs[static_cast<size_t>(j)], xs[static_cast<size_t>(i)]);
        if (y * f < 1.0) {
          alpha[static_cast<size_t>(i)] += lr * y;
          alpha[static_cast<size_t>(i)] = qBound(-C, alpha[static_cast<size_t>(i)], C);
          b += lr * y;
        }
      }
    }
  };
  auto decision = [&](const std::vector<double>& alpha, double b) {
    double f = b;
    for (int j = 0; j < n; ++j) f += alpha[static_cast<size_t>(j)] * kernel(xs[static_cast<size_t>(j)], q);
    return f;
  };

  ModelOut o;
  if (nClass == 2) {
    std::vector<double> a;
    double b = 0;
    trainOne(1, a, b);
    const double z = decision(a, b);
    o.index = z >= 0 ? 1 : 0;
    o.score = o.index == 1 ? scoreFromMargin(z) : scoreFromMargin(-z);
    return o;
  }
  std::vector<double> dec(static_cast<size_t>(nClass), 0.0);
  for (int c = 0; c < nClass; ++c) {
    std::vector<double> a;
    double b = 0;
    trainOne(c, a, b);
    dec[static_cast<size_t>(c)] = decision(a, b);
  }
  int best = 0;
  for (int c = 1; c < nClass; ++c)
    if (dec[static_cast<size_t>(c)] > dec[static_cast<size_t>(best)]) best = c;
  o.index = best;
  o.score = scoreFromMargin(dec[static_cast<size_t>(best)]);
  return o;
}

struct Gauss {
  std::vector<double> mean;
  std::vector<double> cov;  // dim*dim 行主序
  double logDet = 0;
  std::vector<double> inv;  // 逆协方差
  double weight = 1;
};

/** 给协方差加岭并求逆与 log-det；失败返回 false。 */
bool finishGauss(Gauss& g, int dim, double ridge) {
  const int n = dim * dim;
  g.cov.resize(static_cast<size_t>(n));
  for (int i = 0; i < dim; ++i) g.cov[static_cast<size_t>(i * dim + i)] += ridge;
  // Gauss-Jordan 求逆，同时累乘对角得到 det。
  std::vector<double> a = g.cov;
  std::vector<double> inv(static_cast<size_t>(n), 0.0);
  for (int i = 0; i < dim; ++i) inv[static_cast<size_t>(i * dim + i)] = 1.0;
  double logdet = 0;
  for (int col = 0; col < dim; ++col) {
    int piv = col;
    double best = std::fabs(a[static_cast<size_t>(piv * dim + col)]);
    for (int r = col + 1; r < dim; ++r) {
      const double v = std::fabs(a[static_cast<size_t>(r * dim + col)]);
      if (v > best) {
        best = v;
        piv = r;
      }
    }
    if (best < 1e-14) return false;
    if (piv != col) {
      for (int c = 0; c < dim; ++c) {
        std::swap(a[static_cast<size_t>(col * dim + c)], a[static_cast<size_t>(piv * dim + c)]);
        std::swap(inv[static_cast<size_t>(col * dim + c)], inv[static_cast<size_t>(piv * dim + c)]);
      }
    }
    const double diag = a[static_cast<size_t>(col * dim + col)];
    logdet += std::log(std::fabs(diag));
    const double invd = 1.0 / diag;
    for (int c = 0; c < dim; ++c) {
      a[static_cast<size_t>(col * dim + c)] *= invd;
      inv[static_cast<size_t>(col * dim + c)] *= invd;
    }
    for (int r = 0; r < dim; ++r) {
      if (r == col) continue;
      const double f = a[static_cast<size_t>(r * dim + col)];
      for (int c = 0; c < dim; ++c) {
        a[static_cast<size_t>(r * dim + c)] -= f * a[static_cast<size_t>(col * dim + c)];
        inv[static_cast<size_t>(r * dim + c)] -= f * inv[static_cast<size_t>(col * dim + c)];
      }
    }
  }
  g.inv = std::move(inv);
  g.logDet = logdet;
  return true;
}

/** 对数高斯密度（不含 2π 常数也可以，同类比较时一致；这里带上便于后验）。 */
double logGauss(const Gauss& g, const std::vector<double>& x) {
  const int dim = static_cast<int>(g.mean.size());
  std::vector<double> d(static_cast<size_t>(dim), 0.0);
  for (int i = 0; i < dim; ++i) d[static_cast<size_t>(i)] = x[static_cast<size_t>(i)] - g.mean[static_cast<size_t>(i)];
  double q = 0;
  for (int i = 0; i < dim; ++i) {
    double acc = 0;
    for (int j = 0; j < dim; ++j) acc += g.inv[static_cast<size_t>(i * dim + j)] * d[static_cast<size_t>(j)];
    q += d[static_cast<size_t>(i)] * acc;
  }
  constexpr double log2pi = 1.8378770664093453;  // log(2π)
  return -0.5 * (q + g.logDet + dim * log2pi);
}

/** 用样本拟合单个高斯。 */
bool fitOneGaussian(const std::vector<std::vector<double>>& pts, int dim, double ridge, Gauss& g) {
  const int n = static_cast<int>(pts.size());
  if (n <= 0) return false;
  g.mean.assign(static_cast<size_t>(dim), 0.0);
  g.cov.assign(static_cast<size_t>(dim * dim), 0.0);
  g.weight = 1.0;
  for (const auto& p : pts)
    for (int d = 0; d < dim; ++d) g.mean[static_cast<size_t>(d)] += p[static_cast<size_t>(d)];
  for (int d = 0; d < dim; ++d) g.mean[static_cast<size_t>(d)] /= n;
  const double denom = std::max(1, n - 1);
  for (const auto& p : pts) {
    for (int i = 0; i < dim; ++i) {
      const double di = p[static_cast<size_t>(i)] - g.mean[static_cast<size_t>(i)];
      for (int j = 0; j < dim; ++j) {
        const double dj = p[static_cast<size_t>(j)] - g.mean[static_cast<size_t>(j)];
        g.cov[static_cast<size_t>(i * dim + j)] += di * dj / denom;
      }
    }
  }
  return finishGauss(g, dim, ridge);
}

/** 每类 k 分量的简易 EM（k=1 时即上面的单个高斯）。 */
bool fitClassGmm(const std::vector<std::vector<double>>& pts, int dim, int nComp, double ridge,
                 unsigned seed, std::vector<Gauss>& out, QString* err) {
  const int n = static_cast<int>(pts.size());
  nComp = qBound(1, nComp, std::max(1, n));
  out.clear();
  if (nComp == 1) {
    Gauss g;
    if (!fitOneGaussian(pts, dim, ridge, g)) {
      if (err) *err = QStringLiteral("GMM covariance is singular");
      return false;
    }
    out.push_back(std::move(g));
    return true;
  }
  // 用随机样本做初值均值，协方差先用全局高斯。
  Gauss global;
  if (!fitOneGaussian(pts, dim, ridge, global)) {
    if (err) *err = QStringLiteral("GMM covariance is singular");
    return false;
  }
  std::mt19937 rng(seed + 11u);
  std::vector<int> order(static_cast<size_t>(n));
  std::iota(order.begin(), order.end(), 0);
  std::shuffle(order.begin(), order.end(), rng);
  out.assign(static_cast<size_t>(nComp), global);
  for (int k = 0; k < nComp; ++k) {
    out[static_cast<size_t>(k)].mean = pts[static_cast<size_t>(order[k % n])];
    out[static_cast<size_t>(k)].weight = 1.0 / nComp;
  }
  std::vector<std::vector<double>> resp(static_cast<size_t>(n), std::vector<double>(static_cast<size_t>(nComp), 0.0));
  for (int it = 0; it < 40; ++it) {
    // E
    for (int i = 0; i < n; ++i) {
      double mx = -1e300;
      std::vector<double> lg(static_cast<size_t>(nComp), 0.0);
      for (int k = 0; k < nComp; ++k) {
        lg[static_cast<size_t>(k)] =
            std::log(std::max(out[static_cast<size_t>(k)].weight, 1e-12)) + logGauss(out[static_cast<size_t>(k)], pts[static_cast<size_t>(i)]);
        if (lg[static_cast<size_t>(k)] > mx) mx = lg[static_cast<size_t>(k)];
      }
      double s = 0;
      for (int k = 0; k < nComp; ++k) {
        const double v = std::exp(lg[static_cast<size_t>(k)] - mx);
        resp[static_cast<size_t>(i)][static_cast<size_t>(k)] = v;
        s += v;
      }
      for (int k = 0; k < nComp; ++k) resp[static_cast<size_t>(i)][static_cast<size_t>(k)] /= std::max(s, 1e-18);
    }
    // M
    for (int k = 0; k < nComp; ++k) {
      double nk = 0;
      std::vector<double> mean(static_cast<size_t>(dim), 0.0);
      for (int i = 0; i < n; ++i) {
        const double r = resp[static_cast<size_t>(i)][static_cast<size_t>(k)];
        nk += r;
        for (int d = 0; d < dim; ++d) mean[static_cast<size_t>(d)] += r * pts[static_cast<size_t>(i)][static_cast<size_t>(d)];
      }
      if (nk < 1e-6) continue;
      for (int d = 0; d < dim; ++d) mean[static_cast<size_t>(d)] /= nk;
      std::vector<double> cov(static_cast<size_t>(dim * dim), 0.0);
      for (int i = 0; i < n; ++i) {
        const double r = resp[static_cast<size_t>(i)][static_cast<size_t>(k)];
        for (int a = 0; a < dim; ++a) {
          const double da = pts[static_cast<size_t>(i)][static_cast<size_t>(a)] - mean[static_cast<size_t>(a)];
          for (int b = 0; b < dim; ++b) {
            const double db = pts[static_cast<size_t>(i)][static_cast<size_t>(b)] - mean[static_cast<size_t>(b)];
            cov[static_cast<size_t>(a * dim + b)] += r * da * db / nk;
          }
        }
      }
      Gauss g;
      g.mean = std::move(mean);
      g.cov = std::move(cov);
      g.weight = nk / n;
      if (!finishGauss(g, dim, ridge)) {
        if (err) *err = QStringLiteral("GMM covariance is singular");
        return false;
      }
      out[static_cast<size_t>(k)] = std::move(g);
    }
  }
  return true;
}

/** 按类先验 × 混合密度取后验最大的一类。 */
ModelOut predictGmm(const std::vector<std::vector<Gauss>>& gmms, const std::vector<double>& priors,
                    const std::vector<double>& q) {
  const int nClass = static_cast<int>(gmms.size());
  std::vector<double> logp(static_cast<size_t>(nClass), 0.0);
  for (int c = 0; c < nClass; ++c) {
    double mx = -1e300;
    std::vector<double> terms;
    for (const Gauss& g : gmms[static_cast<size_t>(c)]) {
      const double t = std::log(std::max(g.weight, 1e-12)) + logGauss(g, q);
      terms.push_back(t);
      if (t > mx) mx = t;
    }
    double s = 0;
    for (double t : terms) s += std::exp(t - mx);
    logp[static_cast<size_t>(c)] = std::log(std::max(priors[static_cast<size_t>(c)], 1e-12)) + mx + std::log(std::max(s, 1e-18));
  }
  int best = 0;
  double mx = logp[0];
  for (int c = 1; c < nClass; ++c)
    if (logp[static_cast<size_t>(c)] > mx) {
      mx = logp[static_cast<size_t>(c)];
      best = c;
    }
  double z = 0;
  for (int c = 0; c < nClass; ++c) z += std::exp(logp[static_cast<size_t>(c)] - mx);
  ModelOut o;
  o.index = best;
  o.score = std::exp(logp[static_cast<size_t>(best)] - mx) / std::max(z, 1e-18);
  return o;
}

/** 一层隐藏的小 MLP：tanh + softmax，批量交叉熵。 */
ModelOut predictMlp(const std::vector<std::vector<double>>& xs, const std::vector<int>& ys,
                    const std::vector<double>& q, int nClass, int hidden, int epochs, double lr,
                    unsigned seed) {
  const int n = static_cast<int>(xs.size());
  const int dim = xs.empty() ? 0 : static_cast<int>(xs.front().size());
  hidden = qBound(2, hidden, 64);
  std::mt19937 rng(seed + 99u);
  std::normal_distribution<double> nd(0.0, 0.3);
  const int H = hidden;
  std::vector<double> W1(static_cast<size_t>(H * dim)), b1(static_cast<size_t>(H), 0.0);
  std::vector<double> W2(static_cast<size_t>(nClass * H)), b2(static_cast<size_t>(nClass), 0.0);
  for (double& w : W1) w = nd(rng);
  for (double& w : W2) w = nd(rng);

  auto forward = [&](const std::vector<double>& x, std::vector<double>& h, std::vector<double>& logit,
                     std::vector<double>& prob) {
    h.assign(static_cast<size_t>(H), 0.0);
    for (int j = 0; j < H; ++j) {
      double s = b1[static_cast<size_t>(j)];
      for (int d = 0; d < dim; ++d)
        s += W1[static_cast<size_t>(j * dim + d)] * x[static_cast<size_t>(d)];
      h[static_cast<size_t>(j)] = std::tanh(s);
    }
    logit.assign(static_cast<size_t>(nClass), 0.0);
    double mx = -1e300;
    for (int c = 0; c < nClass; ++c) {
      double s = b2[static_cast<size_t>(c)];
      for (int j = 0; j < H; ++j) s += W2[static_cast<size_t>(c * H + j)] * h[static_cast<size_t>(j)];
      logit[static_cast<size_t>(c)] = s;
      if (s > mx) mx = s;
    }
    prob.assign(static_cast<size_t>(nClass), 0.0);
    double z = 0;
    for (int c = 0; c < nClass; ++c) {
      prob[static_cast<size_t>(c)] = std::exp(logit[static_cast<size_t>(c)] - mx);
      z += prob[static_cast<size_t>(c)];
    }
    for (int c = 0; c < nClass; ++c) prob[static_cast<size_t>(c)] /= std::max(z, 1e-18);
  };

  for (int ep = 0; ep < epochs; ++ep) {
    std::vector<double> dW1(W1.size(), 0.0), db1(b1.size(), 0.0);
    std::vector<double> dW2(W2.size(), 0.0), db2(b2.size(), 0.0);
    for (int i = 0; i < n; ++i) {
      std::vector<double> h, logit, prob;
      forward(xs[static_cast<size_t>(i)], h, logit, prob);
      std::vector<double> dlog(static_cast<size_t>(nClass), 0.0);
      for (int c = 0; c < nClass; ++c) dlog[static_cast<size_t>(c)] = prob[static_cast<size_t>(c)];
      dlog[static_cast<size_t>(ys[static_cast<size_t>(i)])] -= 1.0;
      std::vector<double> dh(static_cast<size_t>(H), 0.0);
      for (int c = 0; c < nClass; ++c) {
        db2[static_cast<size_t>(c)] += dlog[static_cast<size_t>(c)];
        for (int j = 0; j < H; ++j) {
          dW2[static_cast<size_t>(c * H + j)] += dlog[static_cast<size_t>(c)] * h[static_cast<size_t>(j)];
          dh[static_cast<size_t>(j)] += dlog[static_cast<size_t>(c)] * W2[static_cast<size_t>(c * H + j)];
        }
      }
      for (int j = 0; j < H; ++j) {
        const double dt = dh[static_cast<size_t>(j)] * (1.0 - h[static_cast<size_t>(j)] * h[static_cast<size_t>(j)]);
        db1[static_cast<size_t>(j)] += dt;
        for (int d = 0; d < dim; ++d)
          dW1[static_cast<size_t>(j * dim + d)] += dt * xs[static_cast<size_t>(i)][static_cast<size_t>(d)];
      }
    }
    const double invn = 1.0 / n;
    for (size_t i = 0; i < W1.size(); ++i) W1[i] -= lr * dW1[i] * invn;
    for (size_t i = 0; i < b1.size(); ++i) b1[i] -= lr * db1[i] * invn;
    for (size_t i = 0; i < W2.size(); ++i) W2[i] -= lr * dW2[i] * invn;
    for (size_t i = 0; i < b2.size(); ++i) b2[i] -= lr * db2[i] * invn;
  }

  std::vector<double> h, logit, prob;
  forward(q, h, logit, prob);
  int best = 0;
  for (int c = 1; c < nClass; ++c)
    if (prob[static_cast<size_t>(c)] > prob[static_cast<size_t>(best)]) best = c;
  ModelOut o;
  o.index = best;
  o.score = prob[static_cast<size_t>(best)];
  return o;
}

QString normalizeMethod(QString raw) {
  raw = raw.trimmed().toLower();
  if (raw == QLatin1String("k-nn") || raw == QLatin1String("nearest")) return QStringLiteral("knn");
  if (raw == QLatin1String("linear-svm") || raw == QLatin1String("rbf-svm")) return QStringLiteral("svm");
  if (raw == QLatin1String("gaussian") || raw == QLatin1String("qda")) return QStringLiteral("gmm");
  if (raw == QLatin1String("ann") || raw == QLatin1String("neural") || raw == QLatin1String("mlp"))
    return QStringLiteral("mlp");
  return raw;
}

}  // namespace

ClassifyResult runClassify(const QVariantMap& params) {
  ClassifyResult r;
  QString method = normalizeMethod(params.value(QStringLiteral("method"), QStringLiteral("knn")).toString());
  if (method.isEmpty()) method = QStringLiteral("knn");
  r.method = method;

  std::vector<Sample> tab;
  QString err;
  const QString samplePath = params.value(QStringLiteral("samplePath")).toString().trimmed();
  const QString altPath = params.value(QStringLiteral("trainPath")).toString().trimmed();
  const QString pathRaw = !samplePath.isEmpty() ? samplePath : altPath;
  if (!pathRaw.isEmpty()) {
    const QString resolved = resolveSamplePath(pathRaw, params.value(QStringLiteral("baseDir")).toString());
    if (resolved.isEmpty()) {
      r.error = QStringLiteral("sample file not found: %1").arg(pathRaw);
      return r;
    }
    QString text;
    if (!readFileText(resolved, text, &err)) {
      r.error = err;
      return r;
    }
    if (!parseSampleText(text, tab, &err)) {
      r.error = err;
      return r;
    }
  } else if (params.contains(QStringLiteral("samples"))) {
    const QVariant sv = params.value(QStringLiteral("samples"));
    if (sv.metaType().id() == QMetaType::QVariantList) {
      QJsonArray arr = QJsonArray::fromVariantList(sv.toList());
      if (!parseJsonSamples(arr, tab, &err)) {
        r.error = err;
        return r;
      }
    } else if (!parseSampleText(sv.toString(), tab, &err)) {
      r.error = err;
      return r;
    }
  } else {
    r.error = QStringLiteral("need samples or samplePath");
    return r;
  }

  QStringList labels;
  int dim = 0;
  if (!normalizeTable(tab, labels, dim, &err)) {
    r.error = err;
    return r;
  }
  r.trainCount = static_cast<int>(tab.size());
  r.classCount = labels.size();
  r.featureDim = dim;

  std::vector<double> mean, invStd;
  fitScaler(tab, dim, mean, invStd);
  std::vector<std::vector<double>> xs;
  std::vector<int> ys;
  xs.reserve(tab.size());
  ys.reserve(tab.size());
  for (const Sample& s : tab) {
    xs.push_back(applyScaler(s.x, mean, invStd));
    ys.push_back(labels.indexOf(s.label));
  }

  std::vector<double> query;
  if (!parseVector(params.value(QStringLiteral("features")), query, &err)) {
    r.error = err.isEmpty() ? QStringLiteral("missing features") : err;
    return r;
  }
  if (static_cast<int>(query.size()) != dim) {
    r.error = QStringLiteral("query dim %1 != train dim %2").arg(query.size()).arg(dim);
    return r;
  }
  const std::vector<double> q = applyScaler(query, mean, invStd);

  const unsigned seed = static_cast<unsigned>(params.value(QStringLiteral("seed"), 1).toInt());
  ModelOut pred;
  if (method == QLatin1String("knn")) {
    const int k = params.value(QStringLiteral("k"), 3).toInt();
    const bool weighted = params.value(QStringLiteral("weighted"), false).toBool();
    pred = predictKnn(xs, ys, q, k, weighted, r.classCount);
  } else if (method == QLatin1String("svm")) {
    const QString kernel = params.value(QStringLiteral("kernel"), QStringLiteral("linear")).toString().trimmed().toLower();
    const double C = std::max(1e-6, params.value(QStringLiteral("C"), 1.0).toDouble());
    const int epochs = qBound(20, params.value(QStringLiteral("epochs"), 80).toInt(), 2000);
    if (kernel == QLatin1String("rbf") || kernel == QLatin1String("gaussian")) {
      const double gamma = std::max(1e-6, params.value(QStringLiteral("gamma"), 1.0 / dim).toDouble());
      pred = predictSvmRbf(xs, ys, q, r.classCount, C, gamma, epochs, seed);
    } else {
      pred = predictSvmLinear(xs, ys, q, r.classCount, C, epochs, seed);
    }
  } else if (method == QLatin1String("gmm")) {
    const int nComp = qBound(1, params.value(QStringLiteral("components"), 1).toInt(), 8);
    const double ridge = std::max(1e-8, params.value(QStringLiteral("ridge"), 1e-3).toDouble());
    std::vector<std::vector<Gauss>> gmms(static_cast<size_t>(r.classCount));
    std::vector<double> priors(static_cast<size_t>(r.classCount), 0.0);
    for (int c = 0; c < r.classCount; ++c) {
      std::vector<std::vector<double>> pts;
      for (int i = 0; i < static_cast<int>(ys.size()); ++i)
        if (ys[static_cast<size_t>(i)] == c) pts.push_back(xs[static_cast<size_t>(i)]);
      priors[static_cast<size_t>(c)] = static_cast<double>(pts.size()) / static_cast<double>(ys.size());
      if (pts.empty()) {
        r.error = QStringLiteral("class %1 has no samples").arg(labels.value(c));
        return r;
      }
      if (!fitClassGmm(pts, dim, nComp, ridge, seed, gmms[static_cast<size_t>(c)], &err)) {
        r.error = err;
        return r;
      }
    }
    pred = predictGmm(gmms, priors, q);
  } else if (method == QLatin1String("mlp")) {
    const int hidden = params.value(QStringLiteral("hidden"), 8).toInt();
    const int epochs = qBound(20, params.value(QStringLiteral("epochs"), 300).toInt(), 4000);
    const double lr = std::max(1e-4, params.value(QStringLiteral("lr"), 0.2).toDouble());
    pred = predictMlp(xs, ys, q, r.classCount, hidden, epochs, lr, seed);
  } else {
    r.error = QStringLiteral("unknown method %1").arg(method);
    return r;
  }

  if (pred.index < 0 || pred.index >= r.classCount) {
    r.error = QStringLiteral("classifier produced no label");
    return r;
  }
  r.ok = true;
  r.classIndex = pred.index;
  r.label = labels.value(pred.index);
  r.score = pred.score;
  r.note = QStringLiteral("%1 label=%2 score=%3 n=%4")
               .arg(method, r.label)
               .arg(r.score, 0, 'g', 3)
               .arg(r.trainCount);
  return r;
}

QStringList classifySelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const ClassifyResult empty = runClassify({{QStringLiteral("method"), QStringLiteral("knn")}});
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  // 两类分离开的 2D 点：训练 10 个，留出 2 个。
  const QString csv = QStringLiteral(
      "0.0,0.0,0\n0.2,0.1,0\n-0.1,0.2,0\n0.1,-0.2,0\n0.3,0.0,0\n"
      "5.0,5.0,1\n4.8,5.1,1\n5.2,4.9,1\n4.9,4.8,1\n5.1,5.2,1\n");
  const QVariantMap base{{QStringLiteral("samples"), csv}, {QStringLiteral("seed"), 1}};

  auto runOne = [&](const char* method, const QVariantMap& extra, const QString& feats,
                    const char* expect) -> ClassifyResult {
    QVariantMap p = base;
    p.insert(QStringLiteral("method"), QString::fromUtf8(method));
    p.insert(QStringLiteral("features"), feats);
    for (auto it = extra.begin(); it != extra.end(); ++it) p.insert(it.key(), it.value());
    return runClassify(p);
  };

  const QStringList methods{QStringLiteral("knn"), QStringLiteral("svm"), QStringLiteral("gmm"),
                            QStringLiteral("mlp")};
  for (const QString& m : methods) {
    QVariantMap extra;
    if (m == QLatin1String("knn")) extra.insert(QStringLiteral("k"), 3);
    if (m == QLatin1String("svm")) {
      extra.insert(QStringLiteral("kernel"), QStringLiteral("linear"));
      extra.insert(QStringLiteral("epochs"), 80);
    }
    if (m == QLatin1String("mlp")) {
      extra.insert(QStringLiteral("hidden"), 6);
      extra.insert(QStringLiteral("epochs"), 400);
      extra.insert(QStringLiteral("lr"), 0.25);
    }
    const ClassifyResult a = runOne(m.toUtf8().constData(), extra, QStringLiteral("0.05,-0.05"), "0");
    const ClassifyResult b = runOne(m.toUtf8().constData(), extra, QStringLiteral("5.0,4.95"), "1");
    check(QStringLiteral("%1-holdout0").arg(m).toUtf8().constData(),
          a.ok && a.label == QLatin1String("0") && a.classIndex == 0,
          QStringLiteral("ok=%1 label=%2 err=%3 score=%4").arg(a.ok).arg(a.label).arg(a.error).arg(a.score));
    check(QStringLiteral("%1-holdout1").arg(m).toUtf8().constData(),
          b.ok && b.label == QLatin1String("1") && b.classIndex == 1,
          QStringLiteral("ok=%1 label=%2 err=%3 score=%4").arg(b.ok).arg(b.label).arg(b.error).arg(b.score));
  }

  // 线性 SVM 的 RBF 核也要能分对这两点。
  {
    QVariantMap extra;
    extra.insert(QStringLiteral("kernel"), QStringLiteral("rbf"));
    extra.insert(QStringLiteral("epochs"), 120);
    extra.insert(QStringLiteral("gamma"), 0.5);
    const ClassifyResult a = runOne("svm", extra, QStringLiteral("0.05,-0.05"), "0");
    const ClassifyResult b = runOne("svm", extra, QStringLiteral("5.0,4.95"), "1");
    check("svm-rbf-holdout0", a.ok && a.label == QLatin1String("0"),
          QStringLiteral("label=%1 err=%2").arg(a.label, a.error));
    check("svm-rbf-holdout1", b.ok && b.label == QLatin1String("1"),
          QStringLiteral("label=%1 err=%2").arg(b.label, b.error));
  }

  // 本地 CSV 文件路径（不是静默跳过）。
  {
    const QString path = QDir::temp().filePath(QStringLiteral("sieans-classify-selftest.csv"));
    QFile f(path);
    const bool wrote = f.open(QIODevice::WriteOnly | QIODevice::Truncate) && f.write(csv.toUtf8()) > 0;
    f.close();
    check("temp-csv-write", wrote, path);
    if (wrote) {
      const ClassifyResult fileR = runClassify(
          {{QStringLiteral("method"), QStringLiteral("knn")},
           {QStringLiteral("samplePath"), path},
           {QStringLiteral("k"), 3},
           {QStringLiteral("features"), QStringLiteral("5.05,5.02")}});
      check("file-knn", fileR.ok && fileR.label == QLatin1String("1") && fileR.trainCount == 10,
            QStringLiteral("ok=%1 label=%2 n=%3 err=%4")
                .arg(fileR.ok)
                .arg(fileR.label)
                .arg(fileR.trainCount)
                .arg(fileR.error));
    }
    QFile::remove(path);
  }

  const ClassifyResult badM =
      runClassify({{QStringLiteral("method"), QStringLiteral("not-a-clf")},
                   {QStringLiteral("samples"), csv},
                   {QStringLiteral("features"), QStringLiteral("0,0")}});
  check("bad-method", !badM.ok && !badM.error.isEmpty(), badM.error);

  const ClassifyResult dimMismatch =
      runClassify({{QStringLiteral("method"), QStringLiteral("knn")},
                   {QStringLiteral("samples"), csv},
                   {QStringLiteral("features"), QStringLiteral("0,0,1")}});
  check("dim-mismatch", !dimMismatch.ok && !dimMismatch.error.isEmpty(), dimMismatch.error);

  return fails;
}

}  // namespace sieans_qt
