#pragma once

#include <QImage>
#include <QPointF>
#include <QRect>
#include <QString>
#include <QVariantMap>

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

}  // namespace sieans_qt
