#pragma once

#include <QImage>
#include <QPointF>
#include <QRect>
#include <QString>
#include <QVariantMap>
#include <QVector>
#include <vector>

namespace sieans_qt {

struct CaliperResult {
  bool ok = false;
  double distPx = 0.0;
  double distMm = 0.0;
  double edge0 = 0.0;  // position along scan (px)
  double edge1 = 0.0;
  double strength0 = 0.0;
  double strength1 = 0.0;
  QPointF p0;  // image coords of first edge
  QPointF p1;
  QString note;
};

/**
 * Pure-QImage 1D caliper: sample a scan band, find two strongest opposite
 * (or same-polarity) edges, return distance. No OpenCV / Halcon.
 *
 * Params (defaults):
 *  direction: "horizontal" | "vertical"  (scan along axis)
 *  roiX,roiY,roiW,roiH: optional ROI (empty → mid band of image)
 *  threshold: min |grad| (default 18)
 *  polarity: "any" | "dark_to_light" | "light_to_dark"
 *  pxPerMm: scale (>0 → measureMm); 0 = px only
 *  bandHalf: half-width of averaging band perpendicular to scan (default 4)
 */
CaliperResult runCaliper(const QImage& src, const QVariantMap& params);

/** 沿线段采样的一维灰度剖面（可在垂直方向做带宽平均）。 */
struct Profile1D {
  std::vector<double> samples;
  std::vector<QPointF> pts;
};

struct ProfileEdge {
  int idx = 0;
  double mag = 0;
  double signedG = 0;
  QPointF p;
};

/** 沿 a→b 采样；bandHalf 为垂直于线段的平均半宽。 */
Profile1D sampleLineProfile(const QImage& src, const QPointF& a, const QPointF& b,
                            int bandHalf);

/** 沿轴对齐 ROI 中线采样：vertical 时从上到下，每像素一个样点。 */
Profile1D sampleRoiMidProfile(const QImage& src, const QRect& roi, bool vertical,
                              int bandHalf);

/** 在剖面上找局部峰值边缘；polarity 与卡尺相同（any / dark_to_light / light_to_dark）。 */
QVector<ProfileEdge> findProfileEdges(const Profile1D& prof, double threshold,
                                      const QString& polarity, int minSep = 3);

/** 最强单边缘。找不到返回 false。 */
bool strongestProfileEdge(const Profile1D& prof, double threshold,
                          const QString& polarity, ProfileEdge* out);

}  // namespace sieans_qt
