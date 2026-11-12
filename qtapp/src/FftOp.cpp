#include "FftOp.hpp"

#include <QColor>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <vector>

namespace sieans_qt {
namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr int kMaxPad = 4096;

struct Cpx {
  double re = 0;
  double im = 0;
};

/** 复数乘法。 */
Cpx mul(const Cpx& a, const Cpx& b) {
  return {a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re};
}

/** 大于等于 n 的 2 的幂；n<=0 返回 1。超过上限时返回值可能仍小于 n，由调用方检查。 */
int nextPow2(int n) {
  if (n <= 1) return 1;
  int p = 1;
  while (p < n) {
    if (p >= kMaxPad) return p;
    p <<= 1;
  }
  return p;
}

/**
 * 基数 2 原地 FFT。n 必须是 2 的幂。
 * inv=false 为正变换（不除 n），inv=true 为逆变换并除以 n。
 */
void fft1d(Cpx* a, int n, bool inv) {
  int j = 0;
  for (int i = 1; i < n; ++i) {
    int bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) std::swap(a[i], a[j]);
  }
  for (int len = 2; len <= n; len <<= 1) {
    const double ang = 2.0 * kPi / static_cast<double>(len) * (inv ? 1.0 : -1.0);
    const Cpx wlen{std::cos(ang), std::sin(ang)};
    for (int i = 0; i < n; i += len) {
      Cpx w{1.0, 0.0};
      const int half = len / 2;
      for (int k = 0; k < half; ++k) {
        const Cpx u = a[i + k];
        const Cpx v = mul(a[i + k + half], w);
        a[i + k] = {u.re + v.re, u.im + v.im};
        a[i + k + half] = {u.re - v.re, u.im - v.im};
        w = mul(w, wlen);
      }
    }
  }
  if (inv) {
    const double invn = 1.0 / static_cast<double>(n);
    for (int i = 0; i < n; ++i) {
      a[i].re *= invn;
      a[i].im *= invn;
    }
  }
}

/** 对 pw×ph 缓冲做二维 FFT 或 IFFT（先按行后按列）。 */
void fft2d(std::vector<Cpx>& grid, int pw, int ph, bool inv) {
  std::vector<Cpx> tmp(static_cast<size_t>(std::max(pw, ph)));
  if (!inv) {
    for (int y = 0; y < ph; ++y) fft1d(&grid[static_cast<size_t>(y * pw)], pw, false);
    for (int x = 0; x < pw; ++x) {
      for (int y = 0; y < ph; ++y) tmp[static_cast<size_t>(y)] = grid[static_cast<size_t>(y * pw + x)];
      fft1d(tmp.data(), ph, false);
      for (int y = 0; y < ph; ++y) grid[static_cast<size_t>(y * pw + x)] = tmp[static_cast<size_t>(y)];
    }
  } else {
    // 逆变换先列后行，与正变换顺序相反，每维各除一次长度。
    for (int x = 0; x < pw; ++x) {
      for (int y = 0; y < ph; ++y) tmp[static_cast<size_t>(y)] = grid[static_cast<size_t>(y * pw + x)];
      fft1d(tmp.data(), ph, true);
      for (int y = 0; y < ph; ++y) grid[static_cast<size_t>(y * pw + x)] = tmp[static_cast<size_t>(y)];
    }
    for (int y = 0; y < ph; ++y) fft1d(&grid[static_cast<size_t>(y * pw)], pw, true);
  }
}

/** 周期频率坐标：把下标映射到 [-0.5, 0.5)。 */
double freqBin(int i, int n) {
  if (n <= 0) return 0;
  if (i <= n / 2) return static_cast<double>(i) / static_cast<double>(n);
  return static_cast<double>(i - n) / static_cast<double>(n);
}

/** 高斯低通 H=exp(-r²/(2σ²))；σ<=0 时只保留直流。 */
double gaussLow(double r2, double sigma) {
  if (sigma <= 1e-12) return 0.0;
  return std::exp(-r2 / (2.0 * sigma * sigma));
}

/** 高斯环带：中心 (lo+hi)/2，σ=(hi-lo)/4，使通带中心增益≈1、边沿约 2σ。 */
double gaussAnnulus(double r, double lo, double hi) {
  if (hi < lo) std::swap(hi, lo);
  const double center = 0.5 * (lo + hi);
  double sigma = 0.25 * (hi - lo);
  if (sigma < 1e-6) sigma = 1e-6;
  const double d = r - center;
  return std::exp(-(d * d) / (2.0 * sigma * sigma));
}

/** 按方法计算频率增益，r2 为 fx²+fy²。 */
double filterGain(const QString& method, double r2, double lo, double hi) {
  if (method == QLatin1String("lowpass")) return gaussLow(r2, lo);
  if (method == QLatin1String("highpass")) return 1.0 - gaussLow(r2, lo);
  const double r = std::sqrt(r2);
  const double band = gaussAnnulus(r, lo, hi);
  if (method == QLatin1String("bandpass")) return band;
  if (method == QLatin1String("bandstop")) return 1.0 - band;
  return 1.0;
}

/** 可分离 Hann 窗，N=1 时为 1。 */
double hann1d(int i, int n) {
  if (n <= 1) return 1.0;
  return 0.5 - 0.5 * std::cos(2.0 * kPi * static_cast<double>(i) / static_cast<double>(n - 1));
}

/** 灰度像素，越界返回 fill。 */
int grayAtFill(const QImage& g, int x, int y, int fill) {
  if (x < 0 || y < 0 || x >= g.width() || y >= g.height()) return fill;
  return g.constScanLine(y)[x];
}

/** 把幅度谱做 fftshift 后按 log(1+|F|) 拉到 0–255。 */
QImage magnitudeSpectrum(const std::vector<Cpx>& grid, int pw, int ph) {
  std::vector<double> mag(static_cast<size_t>(pw * ph), 0.0);
  double mx = 0.0;
  for (int y = 0; y < ph; ++y) {
    for (int x = 0; x < pw; ++x) {
      const Cpx c = grid[static_cast<size_t>(y * pw + x)];
      const double m = std::log1p(std::hypot(c.re, c.im));
      mag[static_cast<size_t>(y * pw + x)] = m;
      if (m > mx) mx = m;
    }
  }
  QImage out(pw, ph, QImage::Format_Grayscale8);
  out.fill(0);
  if (mx <= 0.0) return out;
  const int sx = pw / 2;
  const int sy = ph / 2;
  for (int y = 0; y < ph; ++y) {
    uchar* row = out.scanLine(y);
    for (int x = 0; x < pw; ++x) {
      const int sxo = (x + sx) % pw;
      const int syo = (y + sy) % ph;
      const double m = mag[static_cast<size_t>(syo * pw + sxo)];
      row[x] = static_cast<uchar>(qBound(0, qRound(m * 255.0 / mx), 255));
    }
  }
  return out;
}

/** 输入频谱的高频能量占比（半径大于 cutoff 的 |F|² / 非直流总能量）。 */
double highFreqRatio(const std::vector<Cpx>& grid, int pw, int ph, double cutoff) {
  double total = 0.0;
  double high = 0.0;
  const double c2 = cutoff * cutoff;
  for (int y = 0; y < ph; ++y) {
    const double fy = freqBin(y, ph);
    for (int x = 0; x < pw; ++x) {
      if (x == 0 && y == 0) continue;  // 直流不参与，否则均值亮度会淹没清晰度
      const double fx = freqBin(x, pw);
      const Cpx c = grid[static_cast<size_t>(y * pw + x)];
      const double e = c.re * c.re + c.im * c.im;
      total += e;
      if (fx * fx + fy * fy > c2) high += e;
    }
  }
  if (total <= 0.0) return 0.0;
  return high / total;
}

QImage toRgb888(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_RGB888);
}

QString normalizeMethod(QString raw) {
  raw = raw.trimmed().toLower();
  if (raw == QLatin1String("lp") || raw == QLatin1String("low") || raw == QLatin1String("low-pass"))
    return QStringLiteral("lowpass");
  if (raw == QLatin1String("hp") || raw == QLatin1String("high") || raw == QLatin1String("high-pass"))
    return QStringLiteral("highpass");
  if (raw == QLatin1String("bp") || raw == QLatin1String("band-pass")) return QStringLiteral("bandpass");
  if (raw == QLatin1String("bs") || raw == QLatin1String("band-stop") || raw == QLatin1String("notch"))
    return QStringLiteral("bandstop");
  if (raw == QLatin1String("mag") || raw == QLatin1String("magnitude") || raw == QLatin1String("preview"))
    return QStringLiteral("spectrum");
  return raw;
}

/** 一行的像素均值，用于标准差。 */
double imageStd(const QImage& img) {
  const QImage g = img.convertToFormat(QImage::Format_Grayscale8);
  if (g.isNull() || g.width() <= 0 || g.height() <= 0) return 0.0;
  const int n = g.width() * g.height();
  long double sum = 0;
  long double q = 0;
  for (int y = 0; y < g.height(); ++y) {
    const uchar* row = g.constScanLine(y);
    for (int x = 0; x < g.width(); ++x) {
      sum += row[x];
      q += static_cast<long double>(row[x]) * row[x];
    }
  }
  const long double mean = sum / n;
  const long double var = q / n - mean * mean;
  return var > 0 ? std::sqrt(static_cast<double>(var)) : 0.0;
}

/** 两幅已对齐灰度图的平均绝对差。 */
double meanAbsDiff(const QImage& a, const QImage& b) {
  const QImage ga = a.convertToFormat(QImage::Format_Grayscale8);
  const QImage gb = b.convertToFormat(QImage::Format_Grayscale8);
  if (ga.size() != gb.size() || ga.isNull()) return 1e9;
  long double s = 0;
  const int n = ga.width() * ga.height();
  for (int y = 0; y < ga.height(); ++y) {
    const uchar* ra = ga.constScanLine(y);
    const uchar* rb = gb.constScanLine(y);
    for (int x = 0; x < ga.width(); ++x) s += std::abs(int(ra[x]) - int(rb[x]));
  }
  return n ? static_cast<double>(s / n) : 1e9;
}

}  // namespace

FftResult runFft(const QImage& src, const QVariantMap& params) {
  FftResult r;
  if (src.isNull()) {
    r.error = QStringLiteral("empty image");
    return r;
  }

  QString method = normalizeMethod(params.value(QStringLiteral("method"), QStringLiteral("lowpass")).toString());
  if (method.isEmpty()) method = QStringLiteral("lowpass");
  r.method = method;

  const QString window = params.value(QStringLiteral("window"), QStringLiteral("none")).toString().trimmed().toLower();
  const bool useHann = (window == QLatin1String("hann") || window == QLatin1String("hanning"));

  double cutoff = params.value(QStringLiteral("cutoff"), 0.08).toDouble();
  double cutoffHigh = params.value(QStringLiteral("cutoffHigh"), 0.25).toDouble();
  cutoff = qBound(0.0, cutoff, 0.5);
  cutoffHigh = qBound(0.0, cutoffHigh, 0.5);
  if (cutoffHigh < cutoff) std::swap(cutoffHigh, cutoff);

  const double sharpCutoff = qBound(0.0, params.value(QStringLiteral("sharpCutoff"), 0.15).toDouble(), 0.5);

  const QImage gray = src.convertToFormat(QImage::Format_Grayscale8);
  const int w = gray.width();
  const int h = gray.height();
  if (w <= 0 || h <= 0) {
    r.error = QStringLiteral("empty image");
    return r;
  }

  const int pw = nextPow2(w);
  const int ph = nextPow2(h);
  r.padW = pw;
  r.padH = ph;
  if (pw < w || ph < h || pw > kMaxPad || ph > kMaxPad) {
    r.error = QStringLiteral("image too large for FFT pad (max %1, got %2×%3)").arg(kMaxPad).arg(w).arg(h);
    return r;
  }

  // 用原图均值填充补边，减轻零填充造成的台阶。
  long long sum = 0;
  for (int y = 0; y < h; ++y) {
    const uchar* row = gray.constScanLine(y);
    for (int x = 0; x < w; ++x) sum += row[x];
  }
  const int fill = qBound(0, static_cast<int>((sum + (w * h) / 2) / (w * h)), 255);

  std::vector<Cpx> grid(static_cast<size_t>(pw * ph));
  for (int y = 0; y < ph; ++y) {
    for (int x = 0; x < pw; ++x) {
      double v = grayAtFill(gray, x, y, fill);
      if (useHann && x < w && y < h) v *= hann1d(x, w) * hann1d(y, h);
      grid[static_cast<size_t>(y * pw + x)] = {v, 0.0};
    }
  }

  fft2d(grid, pw, ph, false);
  r.sharpness = highFreqRatio(grid, pw, ph, sharpCutoff);

  if (method == QLatin1String("spectrum")) {
    r.image = toRgb888(magnitudeSpectrum(grid, pw, ph));
    r.ok = !r.image.isNull();
    r.note = QStringLiteral("幅度谱 %1×%2").arg(pw).arg(ph);
    return r;
  }
  if (method != QLatin1String("lowpass") && method != QLatin1String("highpass") &&
      method != QLatin1String("bandpass") && method != QLatin1String("bandstop")) {
    r.error = QStringLiteral("unknown method %1").arg(method);
    return r;
  }

  for (int y = 0; y < ph; ++y) {
    const double fy = freqBin(y, ph);
    for (int x = 0; x < pw; ++x) {
      const double fx = freqBin(x, pw);
      const double r2 = fx * fx + fy * fy;
      const double g = filterGain(method, r2, cutoff, cutoffHigh);
      Cpx& c = grid[static_cast<size_t>(y * pw + x)];
      c.re *= g;
      c.im *= g;
    }
  }

  fft2d(grid, pw, ph, true);

  const bool midGray = (method == QLatin1String("highpass") || method == QLatin1String("bandpass"));
  QImage out(w, h, QImage::Format_Grayscale8);
  for (int y = 0; y < h; ++y) {
    uchar* row = out.scanLine(y);
    for (int x = 0; x < w; ++x) {
      double v = grid[static_cast<size_t>(y * pw + x)].re;
      if (midGray) v += 128.0;
      row[x] = static_cast<uchar>(qBound(0, qRound(v), 255));
    }
  }
  r.image = toRgb888(out);
  r.ok = !r.image.isNull();
  r.note = QStringLiteral("%1 cutoff=%2/%3 pad=%4×%5 sharp=%6")
               .arg(method)
               .arg(cutoff, 0, 'g', 3)
               .arg(cutoffHigh, 0, 'g', 3)
               .arg(pw)
               .arg(ph)
               .arg(r.sharpness, 0, 'g', 3);
  return r;
}

QStringList fftSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const FftResult empty = runFft(QImage(), {{QStringLiteral("method"), QStringLiteral("lowpass")}});
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  auto makeCos = [](int w, int h, int cycles, double amp, double dc) {
    QImage im(w, h, QImage::Format_RGB888);
    for (int y = 0; y < h; ++y) {
      uchar* row = im.scanLine(y);
      for (int x = 0; x < w; ++x) {
        const double v = dc + amp * std::cos(2.0 * kPi * cycles * x / static_cast<double>(w));
        const uchar p = static_cast<uchar>(qBound(0, qRound(v), 255));
        row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = p;
      }
    }
    return im;
  };

  // 64×64、2 周期水平余弦：频率 2/64=0.03125，远低于 cutoff=0.2。
  const QImage low = makeCos(64, 64, 2, 80.0, 128.0);
  const FftResult lpLow = runFft(low, {{QStringLiteral("method"), QStringLiteral("lowpass")},
                                       {QStringLiteral("cutoff"), 0.2}});
  check("lp-ok", lpLow.ok && lpLow.method == QLatin1String("lowpass") && lpLow.padW == 64 &&
                     lpLow.padH == 64,
        lpLow.error);
  const double madLp = meanAbsDiff(lpLow.image, low);
  check("lp-survives-low-sinusoid", lpLow.ok && madLp <= 3.0,
        QStringLiteral("MAD=%1").arg(madLp, 0, 'f', 3));

  const FftResult hpLow = runFft(low, {{QStringLiteral("method"), QStringLiteral("highpass")},
                                       {QStringLiteral("cutoff"), 0.2}});
  check("hp-ok", hpLow.ok, hpLow.error);
  const double std0 = imageStd(low);
  const double stdHp = imageStd(hpLow.image);
  check("hp-attenuates-low-sinusoid", hpLow.ok && std0 > 40.0 && stdHp <= 0.12 * std0,
        QStringLiteral("std0=%1 stdHp=%2").arg(std0, 0, 'f', 2).arg(stdHp, 0, 'f', 2));

  // 16 周期：频率 0.25，高于低通 0.08，应被挡住；高通应保留大部分。
  const QImage high = makeCos(64, 64, 16, 80.0, 128.0);
  const FftResult lpHigh = runFft(high, {{QStringLiteral("method"), QStringLiteral("lowpass")},
                                         {QStringLiteral("cutoff"), 0.08}});
  const double stdLpH = imageStd(lpHigh.image);
  const double stdH = imageStd(high);
  check("lp-attenuates-high-sinusoid", lpHigh.ok && stdH > 40.0 && stdLpH <= 0.12 * stdH,
        QStringLiteral("stdH=%1 stdLp=%2").arg(stdH, 0, 'f', 2).arg(stdLpH, 0, 'f', 2));

  const FftResult hpHigh = runFft(high, {{QStringLiteral("method"), QStringLiteral("highpass")},
                                         {QStringLiteral("cutoff"), 0.08}});
  const double madHpH = meanAbsDiff(hpHigh.image, high);
  check("hp-survives-high-sinusoid", hpHigh.ok && madHpH <= 8.0,
        QStringLiteral("MAD=%1").arg(madHpH, 0, 'f', 3));

  // 带通保留 16 周期（0.25 落在 0.15–0.35），挡住 2 周期。
  const FftResult bpHigh = runFft(high, {{QStringLiteral("method"), QStringLiteral("bandpass")},
                                         {QStringLiteral("cutoff"), 0.15},
                                         {QStringLiteral("cutoffHigh"), 0.35}});
  const FftResult bpLow = runFft(low, {{QStringLiteral("method"), QStringLiteral("bandpass")},
                                       {QStringLiteral("cutoff"), 0.15},
                                       {QStringLiteral("cutoffHigh"), 0.35}});
  check("bp-keeps-mid", bpHigh.ok && imageStd(bpHigh.image) >= 0.5 * stdH,
        QStringLiteral("std=%1").arg(imageStd(bpHigh.image), 0, 'f', 2));
  check("bp-blocks-low", bpLow.ok && imageStd(bpLow.image) <= 0.2 * std0,
        QStringLiteral("std=%1").arg(imageStd(bpLow.image), 0, 'f', 2));

  // 带阻相反：挡住 16 周期，保留 2 周期。
  const FftResult bsHigh = runFft(high, {{QStringLiteral("method"), QStringLiteral("bandstop")},
                                         {QStringLiteral("cutoff"), 0.15},
                                         {QStringLiteral("cutoffHigh"), 0.35}});
  const FftResult bsLow = runFft(low, {{QStringLiteral("method"), QStringLiteral("bandstop")},
                                       {QStringLiteral("cutoff"), 0.15},
                                       {QStringLiteral("cutoffHigh"), 0.35}});
  check("bs-blocks-mid", bsHigh.ok && imageStd(bsHigh.image) <= 0.2 * stdH,
        QStringLiteral("std=%1").arg(imageStd(bsHigh.image), 0, 'f', 2));
  const double madBs = meanAbsDiff(bsLow.image, low);
  check("bs-keeps-low", bsLow.ok && madBs <= 4.0, QStringLiteral("MAD=%1").arg(madBs, 0, 'f', 3));

  // 幅度谱：未移位频谱在 (2,0) 与 (62,0) 应明显强于其它非直流点；移位图中心附近左右应有亮点。
  const FftResult spec = runFft(low, {{QStringLiteral("method"), QStringLiteral("spectrum")}});
  check("spectrum-ok", spec.ok && spec.image.width() == 64 && spec.image.height() == 64, spec.error);
  if (spec.ok) {
    const QImage g = spec.image.convertToFormat(QImage::Format_Grayscale8);
    const int c = g.constScanLine(32)[32];  // 直流，移位后在中心
    const int p1 = g.constScanLine(32)[32 + 2];
    const int p2 = g.constScanLine(32)[32 - 2];
    const int far = g.constScanLine(10)[10];
    check("spectrum-dc-bright", c >= 200, QStringLiteral("dc=%1").arg(c));
    check("spectrum-peaks", p1 >= 80 && p2 >= 80 && p1 > far + 20 && p2 > far + 20,
          QStringLiteral("p1=%1 p2=%2 far=%3 dc=%4").arg(p1).arg(p2).arg(far).arg(c));
  }

  // 清晰度：高频正弦应高于低频正弦，常数图接近 0。
  QImage flat(64, 64, QImage::Format_RGB888);
  flat.fill(QColor(128, 128, 128));
  const FftResult shFlat = runFft(flat, {{QStringLiteral("method"), QStringLiteral("spectrum")},
                                         {QStringLiteral("sharpCutoff"), 0.15}});
  const FftResult shLow = runFft(low, {{QStringLiteral("method"), QStringLiteral("lowpass")},
                                       {QStringLiteral("cutoff"), 0.2},
                                       {QStringLiteral("sharpCutoff"), 0.15}});
  const FftResult shHigh = runFft(high, {{QStringLiteral("method"), QStringLiteral("lowpass")},
                                         {QStringLiteral("cutoff"), 0.4},
                                         {QStringLiteral("sharpCutoff"), 0.15}});
  check("sharp-flat", shFlat.ok && shFlat.sharpness <= 1e-6,
        QStringLiteral("s=%1").arg(shFlat.sharpness, 0, 'g', 6));
  check("sharp-low-small", shLow.ok && shLow.sharpness < 0.05,
        QStringLiteral("s=%1").arg(shLow.sharpness, 0, 'g', 4));
  check("sharp-high-larger", shHigh.ok && shHigh.sharpness > 0.8 && shHigh.sharpness > shLow.sharpness + 0.7,
        QStringLiteral("high=%1 low=%2").arg(shHigh.sharpness, 0, 'g', 4).arg(shLow.sharpness, 0, 'g', 4));

  const FftResult bad = runFft(low, {{QStringLiteral("method"), QStringLiteral("not-a-fft")}});
  check("bad-method", !bad.ok && !bad.error.isEmpty(), bad.error);

  // 奇数尺寸应能补到 2 的幂并裁回，且不得静默失败。
  const QImage odd = makeCos(33, 17, 1, 60.0, 128.0);
  const FftResult oddR = runFft(odd, {{QStringLiteral("method"), QStringLiteral("lowpass")},
                                      {QStringLiteral("cutoff"), 0.25}});
  check("odd-pad", oddR.ok && oddR.image.width() == 33 && oddR.image.height() == 17 &&
                       oddR.padW == 64 && oddR.padH == 32,
        QStringLiteral("ok=%1 %2x%3 pad=%4x%5 err=%6")
            .arg(oddR.ok)
            .arg(oddR.image.width())
            .arg(oddR.image.height())
            .arg(oddR.padW)
            .arg(oddR.padH)
            .arg(oddR.error));

  return fails;
}

}  // namespace sieans_qt
