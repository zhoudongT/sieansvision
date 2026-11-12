#include "CaliperMeasure.hpp"

#include <QVector>
#include <QtGlobal>
#include <algorithm>
#include <cmath>
#include <vector>

namespace sieans_qt {
namespace {

QImage toGray(const QImage& src) {
  return src.convertToFormat(QImage::Format_Grayscale8);
}

int clampi(int v, int lo, int hi) { return qBound(lo, v, hi); }

}  // namespace

CaliperResult runCaliper(const QImage& src, const QVariantMap& params) {
  CaliperResult r;
  if (src.isNull() || src.width() < 8 || src.height() < 8) {
    r.note = QStringLiteral("empty image");
    return r;
  }
  const QImage gray = toGray(src);
  const int W = gray.width();
  const int H = gray.height();

  QString dir =
      params.value(QStringLiteral("direction"), QStringLiteral("horizontal"))
          .toString()
          .toLower();
  const bool horiz = !(dir.startsWith(QLatin1String("v")) ||
                       dir == QLatin1String("vertical") ||
                       dir == QLatin1String("vert"));

  int roiX = params.value(QStringLiteral("roiX"), -1).toInt();
  int roiY = params.value(QStringLiteral("roiY"), -1).toInt();
  int roiW = params.value(QStringLiteral("roiW"), -1).toInt();
  int roiH = params.value(QStringLiteral("roiH"), -1).toInt();

  const QString target =
      params.value(QStringLiteral("target"), QString()).toString().toLower();
  if (target == QLatin1String("soft_bars") ||
      target == QLatin1String("soft") ||
      params.value(QStringLiteral("softBars"), false).toBool()) {
    // Matches SoftFrame caliper plate: x0=24, gap=200, bottom above HUD
    const int gap = 200;
    const int barH = qBound(28, H / 28, 48);
    const int baseY = H - 18 - barH - 6;
    roiX = 16;
    roiW = gap + 40;
    roiH = barH + 16;
    roiY = qMax(0, baseY - 8);
    // force horizontal for soft bars
  } else if (roiW <= 0 || roiH <= 0 || roiX < 0 || roiY < 0) {
    // Default mid band: horizontal scan across middle 60% width, thin height
    if (horiz) {
      roiX = W / 5;
      roiW = qMax(16, (W * 3) / 5);
      roiH = qBound(8, H / 20, 48);
      roiY = (H - roiH) / 2;
    } else {
      roiY = H / 5;
      roiH = qMax(16, (H * 3) / 5);
      roiW = qBound(8, W / 20, 48);
      roiX = (W - roiW) / 2;
    }
  }
  roiX = clampi(roiX, 0, W - 2);
  roiY = clampi(roiY, 0, H - 2);
  roiW = clampi(roiW, 4, W - roiX);
  roiH = clampi(roiH, 4, H - roiY);

  const double thr = params.value(QStringLiteral("threshold"), 18).toDouble();
  const QString pol =
      params.value(QStringLiteral("polarity"), QStringLiteral("any"))
          .toString()
          .toLower();
  const double pxPerMm = params.value(QStringLiteral("pxPerMm"), 0.0).toDouble();
  const int bandHalf = qMax(0, params.value(QStringLiteral("bandHalf"), 4).toInt());

  const int n = horiz ? roiW : roiH;
  if (n < 8) {
    r.note = QStringLiteral("ROI too small");
    return r;
  }
  std::vector<double> profile(static_cast<size_t>(n), 0.0);

  if (horiz) {
    const int y0 = roiY + roiH / 2;
    for (int i = 0; i < n; ++i) {
      const int x = roiX + i;
      double sum = 0;
      int cnt = 0;
      for (int dy = -bandHalf; dy <= bandHalf; ++dy) {
        const int y = clampi(y0 + dy, roiY, roiY + roiH - 1);
        sum += gray.constScanLine(y)[x];
        ++cnt;
      }
      profile[static_cast<size_t>(i)] = sum / qMax(1, cnt);
    }
  } else {
    const int x0 = roiX + roiW / 2;
    for (int i = 0; i < n; ++i) {
      const int y = roiY + i;
      double sum = 0;
      int cnt = 0;
      for (int dx = -bandHalf; dx <= bandHalf; ++dx) {
        const int x = clampi(x0 + dx, roiX, roiX + roiW - 1);
        sum += gray.constScanLine(y)[x];
        ++cnt;
      }
      profile[static_cast<size_t>(i)] = sum / qMax(1, cnt);
    }
  }

  // 1D gradient; find two strongest edges matching polarity
  struct EdgeCand {
    int idx = 0;
    double mag = 0;
    double signedG = 0;
  };
  std::vector<EdgeCand> cands;
  cands.reserve(static_cast<size_t>(n));
  for (int i = 1; i < n - 1; ++i) {
    const double g = profile[static_cast<size_t>(i + 1)] -
                     profile[static_cast<size_t>(i - 1)];
    const double mag = std::abs(g);
    if (mag < thr) continue;
    if (pol.contains(QLatin1String("dark_to_light")) ||
        pol == QLatin1String("rising")) {
      if (g <= 0) continue;
    } else if (pol.contains(QLatin1String("light_to_dark")) ||
               pol == QLatin1String("falling")) {
      if (g >= 0) continue;
    }
    cands.push_back({i, mag, g});
  }
  if (cands.size() < 2) {
    r.note = QStringLiteral("edges<%1").arg(cands.size());
    return r;
  }

  // Non-maximum suppression: keep local peaks spaced ≥ 3 px
  std::vector<EdgeCand> peaks;
  for (const auto& c : cands) {
    bool dominated = false;
    for (const auto& p : peaks) {
      if (std::abs(p.idx - c.idx) < 3) {
        if (c.mag <= p.mag) {
          dominated = true;
          break;
        }
      }
    }
    if (dominated) continue;
    // drop weaker nearby
    peaks.erase(std::remove_if(peaks.begin(), peaks.end(),
                               [&](const EdgeCand& p) {
                                 return std::abs(p.idx - c.idx) < 3 &&
                                        p.mag < c.mag;
                               }),
                peaks.end());
    peaks.push_back(c);
  }
  if (peaks.size() < 2) {
    r.note = QStringLiteral("peaks<%1").arg(peaks.size());
    return r;
  }

  // Prefer two strongest with reasonable separation
  std::sort(peaks.begin(), peaks.end(),
            [](const EdgeCand& a, const EdgeCand& b) { return a.mag > b.mag; });
  EdgeCand e0 = peaks[0];
  EdgeCand e1 = peaks[1];
  // If top two are too close, search for next far enough
  const int minSep = qMax(6, n / 20);
  if (std::abs(e0.idx - e1.idx) < minSep) {
    for (size_t i = 2; i < peaks.size(); ++i) {
      if (std::abs(peaks[i].idx - e0.idx) >= minSep) {
        e1 = peaks[i];
        break;
      }
    }
  }
  if (e0.idx > e1.idx) std::swap(e0, e1);

  r.edge0 = e0.idx;
  r.edge1 = e1.idx;
  r.strength0 = e0.mag;
  r.strength1 = e1.mag;
  r.distPx = static_cast<double>(e1.idx - e0.idx);
  if (pxPerMm > 1e-9) r.distMm = r.distPx / pxPerMm;

  if (horiz) {
    const double y = roiY + roiH / 2.0;
    r.p0 = QPointF(roiX + e0.idx, y);
    r.p1 = QPointF(roiX + e1.idx, y);
  } else {
    const double x = roiX + roiW / 2.0;
    r.p0 = QPointF(x, roiY + e0.idx);
    r.p1 = QPointF(x, roiY + e1.idx);
  }
  r.ok = r.distPx >= 1.0;
  r.note = QStringLiteral("d=%1px").arg(r.distPx, 0, 'f', 1);
  return r;
}

namespace {

QImage profileGray(const QImage& src) {
  return src.convertToFormat(QImage::Format_Grayscale8);
}

bool polarityKeeps(double g, const QString& pol) {
  if (pol.contains(QLatin1String("dark_to_light")) || pol == QLatin1String("rising"))
    return g > 0;
  if (pol.contains(QLatin1String("light_to_dark")) || pol == QLatin1String("falling"))
    return g < 0;
  return true;
}

}  // namespace

Profile1D sampleLineProfile(const QImage& src, const QPointF& a, const QPointF& b,
                            int bandHalf) {
  Profile1D out;
  if (src.isNull()) return out;
  const QImage g = profileGray(src);
  const double dx = b.x() - a.x();
  const double dy = b.y() - a.y();
  const double len = std::hypot(dx, dy);
  if (len < 1.0) return out;
  const int n = qMax(2, qRound(len) + 1);
  const double px = -dy / len;
  const double py = dx / len;
  bandHalf = qMax(0, bandHalf);
  out.samples.resize(static_cast<size_t>(n), 0.0);
  out.pts.resize(static_cast<size_t>(n));
  const int W = g.width();
  const int H = g.height();
  for (int i = 0; i < n; ++i) {
    const double t = (n == 1) ? 0.0 : i / double(n - 1);
    const double x = a.x() + t * dx;
    const double y = a.y() + t * dy;
    double sum = 0;
    int cnt = 0;
    for (int k = -bandHalf; k <= bandHalf; ++k) {
      const int ix = qRound(x + k * px);
      const int iy = qRound(y + k * py);
      if (ix < 0 || iy < 0 || ix >= W || iy >= H) continue;
      sum += g.constScanLine(iy)[ix];
      ++cnt;
    }
    out.samples[static_cast<size_t>(i)] = cnt ? sum / cnt : 0;
    out.pts[static_cast<size_t>(i)] = QPointF(x, y);
  }
  return out;
}

Profile1D sampleRoiMidProfile(const QImage& src, const QRect& roiIn, bool vertical,
                              int bandHalf) {
  Profile1D out;
  if (src.isNull()) return out;
  const QImage g = profileGray(src);
  const QRect roi = roiIn.intersected(QRect(0, 0, g.width(), g.height()));
  if (roi.width() < 2 || roi.height() < 2) return out;
  bandHalf = qMax(0, bandHalf);
  const int n = vertical ? roi.height() : roi.width();
  out.samples.resize(static_cast<size_t>(n), 0.0);
  out.pts.resize(static_cast<size_t>(n));
  if (vertical) {
    const double x0 = roi.x() + roi.width() * 0.5;
    const int xMin = roi.x();
    const int xMax = roi.x() + roi.width() - 1;
    for (int i = 0; i < n; ++i) {
      const int y = roi.y() + i;
      double sum = 0;
      int cnt = 0;
      const int xc = qRound(x0);
      for (int k = -bandHalf; k <= bandHalf; ++k) {
        const int x = qBound(xMin, xc + k, xMax);
        sum += g.constScanLine(y)[x];
        ++cnt;
      }
      out.samples[static_cast<size_t>(i)] = sum / qMax(1, cnt);
      out.pts[static_cast<size_t>(i)] = QPointF(x0, y);
    }
  } else {
    const double y0 = roi.y() + roi.height() * 0.5;
    const int yMin = roi.y();
    const int yMax = roi.y() + roi.height() - 1;
    for (int i = 0; i < n; ++i) {
      const int x = roi.x() + i;
      double sum = 0;
      int cnt = 0;
      const int yc = qRound(y0);
      for (int k = -bandHalf; k <= bandHalf; ++k) {
        const int y = qBound(yMin, yc + k, yMax);
        sum += g.constScanLine(y)[x];
        ++cnt;
      }
      out.samples[static_cast<size_t>(i)] = sum / qMax(1, cnt);
      out.pts[static_cast<size_t>(i)] = QPointF(x, y0);
    }
  }
  return out;
}

QVector<ProfileEdge> findProfileEdges(const Profile1D& prof, double threshold,
                                      const QString& polarity, int minSep) {
  QVector<ProfileEdge> peaks;
  const int n = int(prof.samples.size());
  if (n < 3) return peaks;
  const QString pol = polarity.trimmed().toLower();
  const int sep = qMax(1, minSep);
  std::vector<ProfileEdge> cands;
  for (int i = 1; i < n - 1; ++i) {
    const double g = prof.samples[static_cast<size_t>(i + 1)] -
                     prof.samples[static_cast<size_t>(i - 1)];
    const double mag = std::abs(g);
    if (mag < threshold) continue;
    if (!polarityKeeps(g, pol)) continue;
    ProfileEdge e;
    e.idx = i;
    e.mag = mag;
    e.signedG = g;
    e.p = (i >= 0 && i < int(prof.pts.size())) ? prof.pts[static_cast<size_t>(i)]
                                               : QPointF();
    cands.push_back(e);
  }
  for (const auto& c : cands) {
    bool dominated = false;
    for (const auto& p : peaks) {
      if (std::abs(p.idx - c.idx) < sep && c.mag <= p.mag) {
        dominated = true;
        break;
      }
    }
    if (dominated) continue;
    peaks.erase(std::remove_if(peaks.begin(), peaks.end(),
                               [&](const ProfileEdge& p) {
                                 return std::abs(p.idx - c.idx) < sep && p.mag < c.mag;
                               }),
                peaks.end());
    peaks.push_back(c);
  }
  std::sort(peaks.begin(), peaks.end(),
            [](const ProfileEdge& a, const ProfileEdge& b) { return a.idx < b.idx; });
  return peaks;
}

bool strongestProfileEdge(const Profile1D& prof, double threshold,
                          const QString& polarity, ProfileEdge* out) {
  const QVector<ProfileEdge> edges = findProfileEdges(prof, threshold, polarity, 3);
  if (edges.isEmpty() || !out) return false;
  ProfileEdge best = edges.front();
  for (const auto& e : edges)
    if (e.mag > best.mag) best = e;
  *out = best;
  return true;
}

}  // namespace sieans_qt
