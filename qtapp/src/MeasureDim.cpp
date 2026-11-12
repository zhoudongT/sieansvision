#include "MeasureDim.hpp"
#include "GeometryFind.hpp"
#include "SoftFrame.hpp"
#include "FixturePose.hpp"

#include <QLineF>
#include <QRect>
#include <QPainter>
#include <QVariant>
#include <QtGlobal>
#include <algorithm>
#include <cmath>
#include <vector>

namespace sieans_qt {
namespace {

QString modeNorm(const QVariantMap& p) {
  QString f = p.value(QStringLiteral("feature")).toString().trimmed().toLower();
  if (f.isEmpty())
    f = p.value(QStringLiteral("mode")).toString().trimmed().toLower();
  if (f == QLatin1String("circle") || f == QLatin1String("circles") ||
      f == QLatin1String("diameter") || f == QLatin1String("radius") ||
      f == QLatin1String("圆"))
    return QStringLiteral("circles");
  if (f == QLatin1String("contour") || f == QLatin1String("contours") ||
      f == QLatin1String("rect") || f == QLatin1String("rects") ||
      f == QLatin1String("轮廓") || f == QLatin1String("矩形"))
    return QStringLiteral("contours");
  if (f == QLatin1String("line") || f == QLatin1String("lines") ||
      f == QLatin1String("length") || f == QLatin1String("直线"))
    return QStringLiteral("lines");
  if (f == QLatin1String("point") || f == QLatin1String("points") ||
      f == QLatin1String("distance") || f == QLatin1String("两点") ||
      f == QLatin1String("point_distance"))
    return QStringLiteral("points");
  if (f == QLatin1String("angle") || f == QLatin1String("line_angle") ||
      f == QLatin1String("夹角") || f == QLatin1String("角度"))
    return QStringLiteral("angle");
  if (f == QLatin1String("caliper") || f == QLatin1String("edge") ||
      f == QLatin1String("edges") || f == QLatin1String("卡尺"))
    return QStringLiteral("caliper");
  if (f == QLatin1String("arc") || f == QLatin1String("circular") ||
      f == QLatin1String("arc_measure") || f == QLatin1String("圆弧") ||
      f == QLatin1String("弧"))
    return QStringLiteral("arc");
  if (f == QLatin1String("profile") || f == QLatin1String("profile1d") ||
      f == QLatin1String("1d") || f == QLatin1String("1d_profile") ||
      f == QLatin1String("line_profile") || f == QLatin1String("剖面") ||
      f == QLatin1String("一维"))
    return QStringLiteral("profile");
  if (f == QLatin1String("level") || f == QLatin1String("liquid") ||
      f == QLatin1String("liquid_level") || f == QLatin1String("液位") ||
      f == QLatin1String("液面"))
    return QStringLiteral("level");

  const QString target =
      p.value(QStringLiteral("target")).toString().trimmed().toLower();
  if (target == QLatin1String("soft_bars") || target == QLatin1String("soft-bars"))
    return QStringLiteral("caliper");
  if (target == QLatin1String("soft_circle") || target == QLatin1String("soft-circle"))
    return QStringLiteral("circles");
  if (target == QLatin1String("soft_line") || target == QLatin1String("soft-line"))
    return QStringLiteral("lines");
  if (target == QLatin1String("soft_angle") || target == QLatin1String("soft-angle"))
    return QStringLiteral("angle");
  if (target == QLatin1String("soft_points") || target == QLatin1String("soft-points"))
    return QStringLiteral("points");

  // Explicit two-point list → points mode (engine.measure).
  if (p.contains(QStringLiteral("points")) ||
      (p.contains(QStringLiteral("x1")) && p.contains(QStringLiteral("x2")))) {
    if (f.isEmpty()) return QStringLiteral("points");
  }
  if (f.isEmpty()) return QStringLiteral("contours");  // catalog default
  return f;
}

struct Scale {
  bool calibrated = false;
  double pxPerMm = 0;       // pixels per unit; 0 → unit=px
  double unitsPerPixel = 1; // unit per pixel
  QString unit = QStringLiteral("px");
};

Scale resolveScale(const QVariantMap& p) {
  Scale s;
  const QVariant calVar = p.value(QStringLiteral("calibration"));
  QVariantMap cal = calVar.toMap();
  double calDist = 0;
  QPointF a, b;
  bool haveCalPts = false;
  if (!cal.isEmpty()) {
    calDist = cal.value(QStringLiteral("distance"), 0).toDouble();
    const QVariant pts = cal.value(QStringLiteral("points"));
    const QVariantList lst = pts.toList();
    if (lst.size() >= 2) {
      const QVariantList p0 = lst[0].toList();
      const QVariantList p1 = lst[1].toList();
      if (p0.size() >= 2 && p1.size() >= 2) {
        a = QPointF(p0[0].toDouble(), p0[1].toDouble());
        b = QPointF(p1[0].toDouble(), p1[1].toDouble());
        haveCalPts = true;
      }
    }
    const QString u = cal.value(QStringLiteral("unit")).toString().trimmed();
    if (!u.isEmpty()) s.unit = u;
  }
  if (!haveCalPts && p.contains(QStringLiteral("calX1"))) {
    a = QPointF(p.value(QStringLiteral("calX1")).toDouble(),
                p.value(QStringLiteral("calY1")).toDouble());
    b = QPointF(p.value(QStringLiteral("calX2")).toDouble(),
                p.value(QStringLiteral("calY2")).toDouble());
    calDist = p.value(QStringLiteral("calDistance"),
                      p.value(QStringLiteral("calibrationDistance"), 0))
                  .toDouble();
    haveCalPts = true;
    const QString u = p.value(QStringLiteral("unit")).toString().trimmed();
    if (!u.isEmpty()) s.unit = u;
  }
  if (haveCalPts && calDist > 1e-12) {
    const double pix = QLineF(a, b).length();
    if (pix >= 1.0) {
      s.calibrated = true;
      s.unitsPerPixel = calDist / pix;
      s.pxPerMm = 1.0 / s.unitsPerPixel;
      if (s.unit.isEmpty() || s.unit == QLatin1String("px"))
        s.unit = QStringLiteral("mm");
      return s;
    }
  }
  const double pxPerMm = p.value(QStringLiteral("pxPerMm"), 0.0).toDouble();
  if (pxPerMm > 1e-12) {
    s.calibrated = true;
    s.pxPerMm = pxPerMm;
    s.unitsPerPixel = 1.0 / pxPerMm;
    const QString u = p.value(QStringLiteral("unit")).toString().trimmed();
    s.unit = u.isEmpty() ? QStringLiteral("mm") : u;
    return s;
  }
  const QString u = p.value(QStringLiteral("unit")).toString().trimmed();
  s.unit = u.isEmpty() ? QStringLiteral("px") : u;
  s.unitsPerPixel = 1;
  s.pxPerMm = 0;
  s.calibrated = false;
  return s;
}

double toUnit(const Scale& s, double px) {
  if (s.pxPerMm > 1e-12) return px / s.pxPerMm;
  return px * s.unitsPerPixel;
}

double acuteAngleDeg(const QPointF& a0, const QPointF& a1, const QPointF& b0,
                     const QPointF& b1) {
  const QPointF da = a1 - a0;
  const QPointF db = b1 - b0;
  const double la = std::hypot(da.x(), da.y());
  const double lb = std::hypot(db.x(), db.y());
  if (la < 1e-9 || lb < 1e-9) return 0;
  double cosv = (da.x() * db.x() + da.y() * db.y()) / (la * lb);
  cosv = qBound(-1.0, cosv, 1.0);
  double deg = std::acos(cosv) * 180.0 / M_PI;
  if (deg > 90.0) deg = 180.0 - deg;
  return deg;
}

double lineAngleFromHorizontal(const QPointF& a, const QPointF& b) {
  double deg = std::atan2(b.y() - a.y(), b.x() - a.x()) * 180.0 / M_PI;
  // fold to [-90, 90]
  while (deg > 90.0) deg -= 180.0;
  while (deg < -90.0) deg += 180.0;
  return deg;
}

bool readPointPair(const QVariantMap& p, const char* xa, const char* ya,
                   const char* xb, const char* yb, QPointF* a, QPointF* b) {
  if (!p.contains(QString::fromUtf8(xa)) || !p.contains(QString::fromUtf8(xb)))
    return false;
  *a = QPointF(p.value(QString::fromUtf8(xa)).toDouble(),
               p.value(QString::fromUtf8(ya)).toDouble());
  *b = QPointF(p.value(QString::fromUtf8(xb)).toDouble(),
               p.value(QString::fromUtf8(yb)).toDouble());
  return true;
}

bool readPointsList(const QVariantMap& p, QPointF* a, QPointF* b) {
  const QVariant v = p.value(QStringLiteral("points"));
  const QVariantList lst = v.toList();
  if (lst.size() >= 2) {
    const QVariantList p0 = lst[0].toList();
    const QVariantList p1 = lst[1].toList();
    if (p0.size() >= 2 && p1.size() >= 2) {
      *a = QPointF(p0[0].toDouble(), p0[1].toDouble());
      *b = QPointF(p1[0].toDouble(), p1[1].toDouble());
      return true;
    }
  }
  return readPointPair(p, "x1", "y1", "x2", "y2", a, b);
}

QPointF maybeMap(const QPointF& local, bool follow, const Pose2D& pose) {
  if (!follow) return local;
  return poseMap(pose, local);
}

void applyJudge(MeasureResult& r, const QVariantMap& p) {
  r.judgeEnable = p.value(QStringLiteral("judgeEnable"), false).toBool();
  double jmin = p.value(QStringLiteral("judgeMin"),
                       p.value(QStringLiteral("judgeMinPx"), 0))
                    .toDouble();
  double jmax = p.value(QStringLiteral("judgeMax"),
                       p.value(QStringLiteral("judgeMaxPx"), 99999))
                    .toDouble();
  if (jmax < jmin) std::swap(jmin, jmax);
  const double m = r.valuePx;
  if (!r.judgeEnable)
    r.judgeOk = true;
  else
    r.judgeOk = r.ok && m >= jmin && m <= jmax;
}

void fillPrimary(MeasureResult& r, const MeasureItem& it, const Scale& sc) {
  r.center = it.center;
  r.p0 = it.p0;
  r.p1 = it.p1;
  r.radiusPx = it.radiusPx;
  r.diameterPx = it.diameterPx;
  r.lengthPx = it.lengthPx;
  r.angleDeg = it.angleDeg;
  r.widthPx = it.widthPx;
  r.heightPx = it.heightPx;
  r.areaPx = it.areaPx;
  r.radius = toUnit(sc, it.radiusPx);
  r.diameter = toUnit(sc, it.diameterPx);
  r.length = toUnit(sc, it.lengthPx);
  r.width = toUnit(sc, it.widthPx);
  r.height = toUnit(sc, it.heightPx);
  r.area = toUnit(sc, it.areaPx) * (sc.pxPerMm > 1e-12 || sc.calibrated
                                        ? toUnit(sc, 1.0) / 1.0 * (sc.unitsPerPixel)
                                        : 1.0);
  // area scales with unit²
  if (sc.calibrated || sc.pxPerMm > 1e-12)
    r.area = it.areaPx * sc.unitsPerPixel * sc.unitsPerPixel;
  else
    r.area = it.areaPx;
  r.valuePx = it.valuePx;
  r.value = toUnit(sc, it.valuePx);
}

QVariantMap geometryParams(const QVariantMap& p, const QString& feature) {
  QVariantMap gp = p;
  gp.insert(QStringLiteral("feature"), feature);
  return gp;
}

/** Kasa 代数圆拟合；点数少于 8 或矩阵退化时返回 false。 */
bool kasaFitPoints(const std::vector<QPointF>& pts, double& cx, double& cy, double& r) {
  if (pts.size() < 8) return false;
  double sxx = 0, syy = 0, sxy = 0, sx = 0, sy = 0;
  double sxz = 0, syz = 0, sz = 0;
  const int n = int(pts.size());
  for (const QPointF& e : pts) {
    const double x = e.x(), y = e.y(), z = x * x + y * y;
    sx += x;
    sy += y;
    sxx += x * x;
    syy += y * y;
    sxy += x * y;
    sxz += x * z;
    syz += y * z;
    sz += z;
  }
  double A[3][4] = {
      {sxx, sxy, sx, sxz},
      {sxy, syy, sy, syz},
      {sx, sy, double(n), sz},
  };
  for (int i = 0; i < 3; ++i) {
    int piv = i;
    for (int row = i + 1; row < 3; ++row)
      if (std::abs(A[row][i]) > std::abs(A[piv][i])) piv = row;
    if (std::abs(A[piv][i]) < 1e-9) return false;
    if (piv != i)
      for (int c = 0; c < 4; ++c) std::swap(A[i][c], A[piv][c]);
    const double d = A[i][i];
    for (int c = i; c < 4; ++c) A[i][c] /= d;
    for (int row = 0; row < 3; ++row) {
      if (row == i) continue;
      const double f = A[row][i];
      for (int c = i; c < 4; ++c) A[row][c] -= f * A[i][c];
    }
  }
  const double a = A[0][3], b = A[1][3], c = A[2][3];
  cx = -0.5 * a;
  cy = -0.5 * b;
  const double r2 = cx * cx + cy * cy - c;
  if (r2 <= 1.0) return false;
  r = std::sqrt(r2);
  return std::isfinite(cx) && std::isfinite(cy) && std::isfinite(r);
}

QRect readRoiOrDefault(const QVariantMap& p, int W, int H, bool vertical) {
  int roiX = p.value(QStringLiteral("roiX"), -1).toInt();
  int roiY = p.value(QStringLiteral("roiY"), -1).toInt();
  int roiW = p.value(QStringLiteral("roiW"), -1).toInt();
  int roiH = p.value(QStringLiteral("roiH"), -1).toInt();
  if (roiW <= 0 || roiH <= 0 || roiX < 0 || roiY < 0) {
    if (vertical) {
      roiY = H / 5;
      roiH = qMax(16, (H * 3) / 5);
      roiW = qBound(8, W / 20, 48);
      roiX = (W - roiW) / 2;
    } else {
      roiX = W / 5;
      roiW = qMax(16, (W * 3) / 5);
      roiH = qBound(8, H / 20, 48);
      roiY = (H - roiH) / 2;
    }
  }
  roiX = qBound(0, roiX, qMax(0, W - 2));
  roiY = qBound(0, roiY, qMax(0, H - 2));
  roiW = qBound(2, roiW, W - roiX);
  roiH = qBound(2, roiH, H - roiY);
  return QRect(roiX, roiY, roiW, roiH);
}

}  // namespace

MeasureResult runMeasure(const QImage& src, const QVariantMap& paramsIn) {
  MeasureResult r;
  QVariantMap params = paramsIn;
  r.mode = modeNorm(params);
  const Scale sc = resolveScale(params);
  r.calibrated = sc.calibrated;
  r.pxPerMm = sc.pxPerMm;
  r.unitsPerPixel = sc.unitsPerPixel;
  r.unit = sc.unit;

  Pose2D followPose;
  bool follow = false;
  if (params.value(QStringLiteral("followFixture")).toBool()) {
    followPose = poseFromParams(params);
    follow = followPose.ok || params.contains(QStringLiteral("fixtureX"));
    if (follow) followPose.ok = true;
  }

  auto finish = [&]() {
    applyJudge(r, params);
    if (r.ok) {
      r.note = QStringLiteral("QImage 尺寸测量 · %1 · %2 %3%4")
                   .arg(r.mode)
                   .arg(r.value, 0, 'f', 3)
                   .arg(r.unit)
                   .arg(r.calibrated ? QStringLiteral(" · 已标定") : QString());
      if (r.judgeEnable)
        r.note += r.judgeOk ? QStringLiteral(" · 判定OK") : QStringLiteral(" · 判定NG");
    } else if (r.note.isEmpty()) {
      r.note = r.error;
    }
    return r;
  };

  if (r.mode == QLatin1String("caliper")) {
    r.caliper = runCaliper(src, params);
    r.ok = r.caliper.ok;
    r.error = r.ok ? QString() : r.caliper.note;
    r.count = r.ok ? 1 : 0;
    r.valuePx = r.caliper.distPx;
    r.lengthPx = r.caliper.distPx;
    r.value = r.caliper.distMm > 0 ? r.caliper.distMm : toUnit(sc, r.caliper.distPx);
    r.length = r.value;
    r.p0 = r.caliper.p0;
    r.p1 = r.caliper.p1;
    if (r.ok && r.caliper.distMm <= 0 && sc.calibrated)
      r.caliper.distMm = toUnit(sc, r.caliper.distPx);
    MeasureItem it;
    it.kind = QStringLiteral("caliper");
    it.p0 = r.p0;
    it.p1 = r.p1;
    it.lengthPx = r.lengthPx;
    it.valuePx = r.valuePx;
    it.value = r.value;
    it.polygon << r.p0 << r.p1 << r.p1 << r.p0;
    r.items.push_back(it);
    return finish();
  }

  // soft-scene helpers for points / angle
  const QString target =
      params.value(QStringLiteral("target")).toString().trimmed().toLower();
  const int w = src.isNull() ? 0 : src.width();
  const int h = src.isNull() ? 0 : src.height();
  if (!src.isNull() &&
      (target == QLatin1String("soft_line") ||
       target == QLatin1String("soft_points") ||
       target == QLatin1String("soft_angle") ||
       target == QLatin1String("soft-line") ||
       target == QLatin1String("soft-points") ||
       target == QLatin1String("soft-angle"))) {
    const QLine L = softSceneGeomLine(w, h);
    if (r.mode == QLatin1String("points") &&
        !params.contains(QStringLiteral("x1")) &&
        !params.contains(QStringLiteral("points"))) {
      params.insert(QStringLiteral("x1"), L.x1());
      params.insert(QStringLiteral("y1"), L.y1());
      params.insert(QStringLiteral("x2"), L.x2());
      params.insert(QStringLiteral("y2"), L.y2());
    }
    if (r.mode == QLatin1String("angle") &&
        !params.contains(QStringLiteral("x1"))) {
      // soft line vs vertical through midpoint → 90°
      const QPoint mid((L.x1() + L.x2()) / 2, (L.y1() + L.y2()) / 2);
      params.insert(QStringLiteral("x1"), L.x1());
      params.insert(QStringLiteral("y1"), L.y1());
      params.insert(QStringLiteral("x2"), L.x2());
      params.insert(QStringLiteral("y2"), L.y2());
      params.insert(QStringLiteral("x3"), mid.x());
      params.insert(QStringLiteral("y3"), mid.y() - 40);
      params.insert(QStringLiteral("x4"), mid.x());
      params.insert(QStringLiteral("y4"), mid.y() + 40);
    }
  }

  if (r.mode == QLatin1String("points")) {
    QPointF a, b;
    if (!readPointsList(params, &a, &b)) {
      r.error = QStringLiteral("两点测距需要 points 或 x1,y1,x2,y2");
      return finish();
    }
    a = maybeMap(a, follow, followPose);
    b = maybeMap(b, follow, followPose);
    const double dist = QLineF(a, b).length();
    MeasureItem it;
    it.kind = QStringLiteral("points");
    it.p0 = a;
    it.p1 = b;
    it.center = (a + b) * 0.5;
    it.lengthPx = dist;
    it.valuePx = dist;
    it.value = toUnit(sc, dist);
    it.polygon << a << b << b << a;
    r.items.push_back(it);
    r.count = 1;
    r.ok = dist >= 0;
    fillPrimary(r, it, sc);
    return finish();
  }

  if (r.mode == QLatin1String("angle")) {
    QPointF a0, a1, b0, b1;
    const bool hasA = readPointPair(params, "x1", "y1", "x2", "y2", &a0, &a1);
    const bool hasB = readPointPair(params, "x3", "y3", "x4", "y4", &b0, &b1);
    if (hasA && hasB) {
      a0 = maybeMap(a0, follow, followPose);
      a1 = maybeMap(a1, follow, followPose);
      b0 = maybeMap(b0, follow, followPose);
      b1 = maybeMap(b1, follow, followPose);
      const double ang = acuteAngleDeg(a0, a1, b0, b1);
      MeasureItem it;
      it.kind = QStringLiteral("angle");
      it.p0 = a0;
      it.p1 = a1;
      it.center = (a0 + a1) * 0.5;
      it.angleDeg = ang;
      it.valuePx = ang;  // degrees, not pixels
      it.value = ang;
      it.polygon << a0 << a1 << b1 << b0;
      r.items.push_back(it);
      r.count = 1;
      r.ok = true;
      r.unit = QStringLiteral("deg");
      r.angleDeg = ang;
      r.valuePx = ang;
      r.value = ang;
      r.p0 = a0;
      r.p1 = a1;
      return finish();
    }
    // Fall through: measure first found line vs horizontal, or two found lines.
    QVariantMap gp = geometryParams(params, QStringLiteral("lines"));
    if (target.isEmpty() && !gp.contains(QStringLiteral("target")))
      gp.insert(QStringLiteral("target"), QStringLiteral("soft_line"));
    if (src.isNull()) {
      r.error = QStringLiteral("夹角测量需要输入图像或两组端点");
      return finish();
    }
    const GeometryResult g = runGeometry(src, gp);
    if (!g.ok || g.items.size() < 1) {
      r.error = g.error.isEmpty() ? QStringLiteral("未找到直线，无法测角") : g.error;
      r.note = r.error;
      return finish();
    }
    if (g.items.size() >= 2) {
      const GeometryItem& l0 = g.items[0];
      const GeometryItem& l1 = g.items[1];
      const double ang = acuteAngleDeg(l0.start, l0.end, l1.start, l1.end);
      MeasureItem it;
      it.kind = QStringLiteral("angle");
      it.p0 = l0.start;
      it.p1 = l0.end;
      it.center = l0.center;
      it.angleDeg = ang;
      it.valuePx = ang;
      it.value = ang;
      it.polygon << l0.start << l0.end << l1.end << l1.start;
      r.items.push_back(it);
      r.count = 1;
      r.ok = true;
      r.unit = QStringLiteral("deg");
      r.angleDeg = ang;
      r.valuePx = ang;
      r.value = ang;
      r.p0 = it.p0;
      r.p1 = it.p1;
      return finish();
    }
    const GeometryItem& l0 = g.items[0];
    const double ang = lineAngleFromHorizontal(l0.start, l0.end);
    MeasureItem it;
    it.kind = QStringLiteral("angle");
    it.p0 = l0.start;
    it.p1 = l0.end;
    it.center = l0.center;
    it.angleDeg = ang;
    it.valuePx = std::abs(ang);
    it.value = std::abs(ang);
    it.polygon << l0.start << l0.end << l0.end << l0.start;
    r.items.push_back(it);
    r.count = 1;
    r.ok = true;
    r.unit = QStringLiteral("deg");
    r.angleDeg = ang;
    r.valuePx = std::abs(ang);
    r.value = std::abs(ang);
    r.p0 = it.p0;
    r.p1 = it.p1;
    return finish();
  }

  if (src.isNull() || src.width() < 8 || src.height() < 8) {
    r.error = QStringLiteral("尺寸测量需要输入图像");
    return finish();
  }

  if (r.mode == QLatin1String("arc")) {
    const int W = src.width();
    const int H = src.height();
    QRect roi = readRoiOrDefault(params, W, H, false);
    const bool hasRoi = params.value(QStringLiteral("roiW"), 0).toInt() > 0 &&
                        params.value(QStringLiteral("roiH"), 0).toInt() > 0;
    if (!hasRoi) roi = QRect(0, 0, W, H);
    double cx = params.contains(QStringLiteral("centerX"))
                    ? params.value(QStringLiteral("centerX")).toDouble()
                    : (params.contains(QStringLiteral("cx"))
                           ? params.value(QStringLiteral("cx")).toDouble()
                           : roi.center().x());
    double cy = params.contains(QStringLiteral("centerY"))
                    ? params.value(QStringLiteral("centerY")).toDouble()
                    : (params.contains(QStringLiteral("cy"))
                           ? params.value(QStringLiteral("cy")).toDouble()
                           : roi.center().y());
    if (follow) {
      const QPointF c = maybeMap(QPointF(cx, cy), true, followPose);
      cx = c.x();
      cy = c.y();
    }
    double rMin = params.contains(QStringLiteral("rMin"))
                      ? params.value(QStringLiteral("rMin")).toDouble()
                      : params.value(QStringLiteral("minRadius"), 0).toDouble();
    double rMax = params.contains(QStringLiteral("rMax"))
                      ? params.value(QStringLiteral("rMax")).toDouble()
                      : params.value(QStringLiteral("maxRadius"), 0).toDouble();
    if (rMax <= rMin) {
      const double cap = std::min({double(cx), double(W - 1 - cx), double(cy),
                                   double(H - 1 - cy),
                                   0.5 * std::min(roi.width(), roi.height())});
      if (rMin <= 0) rMin = qMax(2.0, cap * 0.3);
      rMax = qMax(rMin + 4.0, cap);
    }
    const double ang0 = params.value(QStringLiteral("angleStart"), 0.0).toDouble();
    double span = params.value(QStringLiteral("angleSpan"), 360.0).toDouble();
    if (std::abs(span) < 1.0) span = 360.0;
    const double thr = params.value(QStringLiteral("threshold"), 18).toDouble();
    const QString pol =
        params.value(QStringLiteral("polarity"), QStringLiteral("any")).toString();
    const double step = qBound(0.5, params.value(QStringLiteral("angleStep"), 1.0).toDouble(), 5.0);
    std::vector<QPointF> pts;
    std::vector<double> rs, thetas;
    for (double a = ang0;; a += (span >= 0 ? step : -step)) {
      const bool done = (span >= 0) ? (a > ang0 + span + 1e-9) : (a < ang0 + span - 1e-9);
      if (done) break;
      const double rad = a * M_PI / 180.0;
      // 0°=+x，逆时针指向图像 -y（与 QPainter 角定义一致）。
      const double ux = std::cos(rad);
      const double uy = -std::sin(rad);
      const QPointF pa(cx + rMin * ux, cy + rMin * uy);
      const QPointF pb(cx + rMax * ux, cy + rMax * uy);
      const Profile1D prof = sampleLineProfile(src, pa, pb, 0);
      ProfileEdge e;
      if (!strongestProfileEdge(prof, thr, pol, &e)) continue;
      const double rr = std::hypot(e.p.x() - cx, e.p.y() - cy);
      if (rr < rMin - 1 || rr > rMax + 1) continue;
      pts.push_back(e.p);
      rs.push_back(rr);
      thetas.push_back(a);
    }
    if (pts.size() < 6) {
      r.error = QStringLiteral("圆弧采样点不足 %1").arg(int(pts.size()));
      return finish();
    }
    double meanR = 0;
    for (double v : rs) meanR += v;
    meanR /= double(rs.size());
    double fx = cx, fy = cy, fr = meanR;
    if (kasaFitPoints(pts, fx, fy, fr) && std::hypot(fx - cx, fy - cy) < qMax(8.0, meanR * 0.5) &&
        fr > 1.0) {
      // 用拟合半径，圆心若明显漂移则退回给定圆心的平均半径。
    } else {
      fx = cx;
      fy = cy;
      fr = meanR;
    }
    const double inc = std::abs(thetas.back() - thetas.front());
    const double included = (inc >= 359.0 ? 360.0 : inc);
    const double arcLen = fr * included * M_PI / 180.0;
    MeasureItem it;
    it.kind = QStringLiteral("arc");
    it.center = QPointF(fx, fy);
    it.p0 = pts.front();
    it.p1 = pts.back();
    it.radiusPx = fr;
    it.diameterPx = 2.0 * fr;
    it.lengthPx = arcLen;
    it.angleDeg = included;
    it.valuePx = fr;
    it.value = toUnit(sc, fr);
    for (const QPointF& q : pts) it.polygon << q;
    r.items.push_back(it);
    r.count = 1;
    r.ok = true;
    fillPrimary(r, it, sc);
    r.angleDeg = included;
    return finish();
  }

  if (r.mode == QLatin1String("profile")) {
    const int W = src.width();
    const int H = src.height();
    const int bandHalf = qMax(0, params.value(QStringLiteral("bandHalf"), 4).toInt());
    const double thr = params.value(QStringLiteral("threshold"), 18).toDouble();
    const QString pol =
        params.value(QStringLiteral("polarity"), QStringLiteral("any")).toString();
    QPointF a, b;
    Profile1D prof;
    const bool hasLine = readPointsList(params, &a, &b);
    if (hasLine) {
      a = maybeMap(a, follow, followPose);
      b = maybeMap(b, follow, followPose);
      prof = sampleLineProfile(src, a, b, bandHalf);
    } else {
      const QString dir =
          params.value(QStringLiteral("direction"), QString()).toString().toLower();
      const QRect roi = readRoiOrDefault(params, W, H, dir.startsWith(QLatin1String("v")));
      const bool vertical = dir.startsWith(QLatin1String("v")) ||
                            (dir.isEmpty() && roi.height() >= roi.width());
      prof = sampleRoiMidProfile(src, roi, vertical, bandHalf);
      if (!prof.pts.empty()) {
        a = prof.pts.front();
        b = prof.pts.back();
      }
    }
    ProfileEdge e;
    if (!strongestProfileEdge(prof, thr, pol, &e)) {
      r.error = QStringLiteral("一维剖面未找到边缘");
      return finish();
    }
    const QVector<ProfileEdge> edges = findProfileEdges(prof, thr, pol, 3);
    MeasureItem it;
    it.kind = QStringLiteral("profile");
    it.p0 = e.p;
    it.p1 = b;
    it.center = e.p;
    it.valuePx = e.idx;  // 沿剖面从起点计的像素下标
    // 若用任意线段采样，下标约等于到起点的弧长。
    if (!prof.pts.empty())
      it.valuePx = QLineF(prof.pts.front(), e.p).length();
    it.lengthPx = it.valuePx;
    if (edges.size() >= 2) {
      const ProfileEdge& e0 = edges.front();
      const ProfileEdge& e1 = edges.back();
      it.lengthPx = QLineF(e0.p, e1.p).length();
      it.p1 = e1.p;
    }
    it.value = toUnit(sc, it.valuePx);
    it.polygon << a << b << e.p << e.p;
    r.items.push_back(it);
    r.count = 1;
    r.ok = true;
    fillPrimary(r, it, sc);
    return finish();
  }

  if (r.mode == QLatin1String("level")) {
    const int bandHalf = qMax(0, params.value(QStringLiteral("bandHalf"), 4).toInt());
    const double thr = params.value(QStringLiteral("threshold"), 18).toDouble();
    const QString pol =
        params.value(QStringLiteral("polarity"), QStringLiteral("any")).toString();
    QImage work = src;
    QRect roi;
    bool usedPatch = false;
    FollowRoi fr;
    if (follow) {
      fr = resolveFollowRoi(params, src.width(), src.height());
      if (fr.active) {
        work = extractFollowPatch(src, fr, followPose);
        usedPatch = !work.isNull();
      }
    }
    if (usedPatch)
      roi = QRect(0, 0, work.width(), work.height());
    else
      roi = readRoiOrDefault(params, src.width(), src.height(), true);
    const Profile1D prof = sampleRoiMidProfile(work, roi, true, bandHalf);
    ProfileEdge e;
    if (!strongestProfileEdge(prof, thr, pol, &e)) {
      r.error = QStringLiteral("液位剖面未找到界面");
      return finish();
    }
    QPointF iface = e.p;
    const double roiBottom = roi.y() + roi.height();
    double heightPx = roiBottom - iface.y();
    if (heightPx < 0) heightPx = 0;
    if (usedPatch) {
      iface = poseMap(followPose, QPointF(fr.roiX + iface.x() + 0.5, fr.roiY + iface.y() + 0.5));
      // 高度沿夹具局部竖直方向，单位为补丁像素；尺度≠1 时再按尺度换到图像像素。
      if (followPose.scale > 1e-9 && std::abs(followPose.scale - 1.0) > 1e-6)
        heightPx *= followPose.scale;
    }
    MeasureItem it;
    it.kind = QStringLiteral("level");
    it.center = iface;
    it.p0 = iface;
    it.p1 = QPointF(iface.x(), iface.y() + heightPx);
    it.heightPx = heightPx;
    it.valuePx = heightPx;
    it.value = toUnit(sc, heightPx);
    it.polygon << iface << it.p1 << it.p1 << iface;
    r.items.push_back(it);
    r.count = 1;
    r.ok = true;
    fillPrimary(r, it, sc);
    return finish();
  }

  QString gf = r.mode;
  if (gf == QLatin1String("contours"))
    gf = QStringLiteral("rects");  // min-area rect like engine.measure
  QVariantMap gp = geometryParams(params, gf);
  if (r.mode == QLatin1String("circles") && target.isEmpty() &&
      !gp.contains(QStringLiteral("target")) &&
      gp.value(QStringLiteral("roiW"), 0).toInt() <= 0)
    gp.insert(QStringLiteral("target"), QStringLiteral("soft_circle"));
  if (r.mode == QLatin1String("lines") && target.isEmpty() &&
      !gp.contains(QStringLiteral("target")) &&
      gp.value(QStringLiteral("roiW"), 0).toInt() <= 0)
    gp.insert(QStringLiteral("target"), QStringLiteral("soft_line"));

  const GeometryResult g = runGeometry(src, gp);
  if (!g.ok) {
    r.error = g.error.isEmpty() ? g.note : g.error;
    r.note = r.error;
    return finish();
  }
  for (const GeometryItem& gi : g.items) {
    MeasureItem it;
    it.center = gi.center;
    it.p0 = gi.start;
    it.p1 = gi.end;
    it.polygon = gi.polygon;
    if (r.mode == QLatin1String("circles")) {
      it.kind = QStringLiteral("circle");
      it.radiusPx = gi.radius;
      it.diameterPx = gi.diameter > 0 ? gi.diameter : 2.0 * gi.radius;
      it.valuePx = it.diameterPx;
    } else if (r.mode == QLatin1String("lines")) {
      it.kind = QStringLiteral("line");
      it.lengthPx = gi.length;
      it.angleDeg = gi.angleDeg;
      it.valuePx = it.lengthPx;
      if (it.polygon.size() < 2) it.polygon << gi.start << gi.end << gi.end << gi.start;
    } else {
      it.kind = QStringLiteral("contour");
      it.widthPx = gi.width;
      it.heightPx = gi.height;
      it.areaPx = gi.area;
      it.angleDeg = gi.angleDeg;
      it.valuePx = gi.height > 0 ? gi.height : gi.area;  // longer side, like engine
      if (it.polygon.isEmpty() && gi.bbox.isValid()) {
        const QRectF b = gi.bbox;
        it.polygon << b.topLeft() << b.topRight() << b.bottomRight() << b.bottomLeft();
      }
    }
    it.value = (r.mode == QLatin1String("circles") || r.mode == QLatin1String("lines") ||
                r.mode == QLatin1String("contours"))
                   ? toUnit(sc, it.valuePx)
                   : it.valuePx;
    r.items.push_back(it);
  }
  r.count = r.items.size();
  r.ok = r.count >= 1;
  if (!r.ok)
    r.error = QStringLiteral("未找到可测量的 %1").arg(r.mode);
  else
    fillPrimary(r, r.items.first(), sc);
  return finish();
}

QStringList measureSelfTest() {
  QStringList fails;
  auto expect = [&](bool cond, const char* msg) {
    if (!cond) fails << QString::fromUtf8(msg);
  };

  QImage img(240, 200, QImage::Format_RGB888);
  img.fill(QColor(230, 230, 230));
  {
    QPainter p(&img);
    p.setRenderHint(QPainter::Antialiasing, false);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(20, 20, 20));
    p.drawEllipse(QPoint(80, 70), 25, 25);
    p.setPen(QPen(QColor(20, 20, 20), 6, Qt::SolidLine, Qt::FlatCap));
    p.drawLine(QLine(20, 160, 180, 160));
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(20, 20, 20));
    p.drawRect(QRect(150, 30, 50, 30));
    p.end();
  }

  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("circles"));
    p.insert(QStringLiteral("minRadius"), 15);
    p.insert(QStringLiteral("maxRadius"), 40);
    p.insert(QStringLiteral("votes"), 12);
    p.insert(QStringLiteral("roiX"), 40);
    p.insert(QStringLiteral("roiY"), 30);
    p.insert(QStringLiteral("roiW"), 80);
    p.insert(QStringLiteral("roiH"), 80);
    p.insert(QStringLiteral("pxPerMm"), 10);
    p.insert(QStringLiteral("judgeEnable"), true);
    p.insert(QStringLiteral("judgeMin"), 45);
    p.insert(QStringLiteral("judgeMax"), 55);
    const MeasureResult r = runMeasure(img, p);
    expect(r.ok, "circle ok");
    expect(r.mode == QLatin1String("circles"), "circle mode");
    expect(std::abs(r.radiusPx - 25) <= 2.5, "circle r≈25");
    expect(std::abs(r.diameterPx - 50) <= 5.0, "circle d≈50");
    expect(r.calibrated, "circle calibrated");
    expect(std::abs(r.diameter - r.diameterPx / 10.0) <= 0.6, "circle d mm");
    expect(r.judgeOk, "circle judge");
    expect(r.unit == QLatin1String("mm"), "circle unit mm");
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("lines"));
    p.insert(QStringLiteral("minLength"), 80);
    p.insert(QStringLiteral("votes"), 20);
    p.insert(QStringLiteral("roiX"), 8);
    p.insert(QStringLiteral("roiY"), 140);
    p.insert(QStringLiteral("roiW"), 200);
    p.insert(QStringLiteral("roiH"), 40);
    const MeasureResult r = runMeasure(img, p);
    expect(r.ok, "line ok");
    expect(r.lengthPx >= 140 && r.lengthPx <= 185, "line length≈160");
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("points"));
    p.insert(QStringLiteral("x1"), 10);
    p.insert(QStringLiteral("y1"), 20);
    p.insert(QStringLiteral("x2"), 10);
    p.insert(QStringLiteral("y2"), 120);
    p.insert(QStringLiteral("pxPerMm"), 10);
    const MeasureResult r = runMeasure(img, p);
    expect(r.ok, "points ok");
    expect(std::abs(r.lengthPx - 100) <= 1e-6, "points dist=100");
    expect(std::abs(r.value - 10.0) <= 1e-6, "points 10mm");
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("angle"));
    p.insert(QStringLiteral("x1"), 0);
    p.insert(QStringLiteral("y1"), 0);
    p.insert(QStringLiteral("x2"), 100);
    p.insert(QStringLiteral("y2"), 0);
    p.insert(QStringLiteral("x3"), 0);
    p.insert(QStringLiteral("y3"), 0);
    p.insert(QStringLiteral("x4"), 0);
    p.insert(QStringLiteral("y4"), 80);
    const MeasureResult r = runMeasure(img, p);
    expect(r.ok, "angle ok");
    expect(std::abs(r.angleDeg - 90.0) <= 0.01, "angle 90");
    expect(r.unit == QLatin1String("deg"), "angle unit deg");
  }
  {
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("contours"));
    p.insert(QStringLiteral("threshold"), 127);
    p.insert(QStringLiteral("invert"), true);
    p.insert(QStringLiteral("minArea"), 200);
    p.insert(QStringLiteral("roiX"), 140);
    p.insert(QStringLiteral("roiY"), 20);
    p.insert(QStringLiteral("roiW"), 70);
    p.insert(QStringLiteral("roiH"), 50);
    const MeasureResult r = runMeasure(img, p);
    expect(r.ok, "contour ok");
    expect(r.widthPx >= 24 && r.heightPx >= 24, "contour size");
    expect(std::abs(r.center.x() - 175) <= 5, "contour cx");
  }
  {
    // calibration via two points: 50 px = 5 mm → 10 px/mm
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("points"));
    p.insert(QStringLiteral("x1"), 0);
    p.insert(QStringLiteral("y1"), 0);
    p.insert(QStringLiteral("x2"), 80);
    p.insert(QStringLiteral("y2"), 0);
    QVariantMap cal;
    cal.insert(QStringLiteral("distance"), 10);
    cal.insert(QStringLiteral("unit"), QStringLiteral("mm"));
    cal.insert(QStringLiteral("points"),
               QVariantList{QVariantList{0, 0}, QVariantList{20, 0}});
    p.insert(QStringLiteral("calibration"), cal);
    const MeasureResult r = runMeasure(img, p);
    expect(r.ok && r.calibrated, "cal points ok");
    expect(std::abs(r.value - 40.0) <= 1e-6, "cal 80px → 40mm");
  }

  // 已知半径圆弧：半径 40，180° 上半弧，圆心 (100,100)。
  {
    QImage arc(200, 200, QImage::Format_RGB888);
    arc.fill(Qt::black);
    const double cx = 100, cy = 100, rad = 40;
    for (int a = 0; a <= 180; ++a) {
      const double th = a * M_PI / 180.0;
      const int x = qRound(cx + rad * std::cos(th));
      const int y = qRound(cy - rad * std::sin(th));
      for (int dy = -1; dy <= 1; ++dy)
        for (int dx = -1; dx <= 1; ++dx) {
          const int xx = x + dx, yy = y + dy;
          if (xx >= 0 && yy >= 0 && xx < 200 && yy < 200) {
            uchar* p = arc.scanLine(yy) + xx * 3;
            p[0] = p[1] = p[2] = 255;
          }
        }
    }
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("arc"));
    p.insert(QStringLiteral("centerX"), 100);
    p.insert(QStringLiteral("centerY"), 100);
    p.insert(QStringLiteral("rMin"), 30);
    p.insert(QStringLiteral("rMax"), 50);
    p.insert(QStringLiteral("angleStart"), 0);
    p.insert(QStringLiteral("angleSpan"), 180);
    p.insert(QStringLiteral("threshold"), 12);
    const MeasureResult r = runMeasure(arc, p);
    expect(r.ok, "arc ok");
    expect(r.mode == QLatin1String("arc"), "arc mode");
    expect(std::abs(r.radiusPx - 40) <= 2.5, "arc r≈40");
    expect(std::abs(r.diameterPx - 80) <= 5.0, "arc d≈80");
    expect(std::abs(r.angleDeg - 180) <= 8.0, "arc included≈180");
    const double expectLen = 40.0 * M_PI;  // 半圆
    expect(std::abs(r.lengthPx - expectLen) <= 12.0, "arc length≈πr");
  }

  // 水平线上已知阶跃：x=80。
  {
    QImage step(200, 80, QImage::Format_RGB888);
    for (int y = 0; y < 80; ++y) {
      uchar* row = step.scanLine(y);
      for (int x = 0; x < 200; ++x) {
        const uchar v = (x < 80) ? 20 : 220;
        row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = v;
      }
    }
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("profile"));
    p.insert(QStringLiteral("x1"), 0);
    p.insert(QStringLiteral("y1"), 40);
    p.insert(QStringLiteral("x2"), 199);
    p.insert(QStringLiteral("y2"), 40);
    p.insert(QStringLiteral("threshold"), 18);
    p.insert(QStringLiteral("bandHalf"), 2);
    const MeasureResult r = runMeasure(step, p);
    expect(r.ok, "profile ok");
    expect(r.mode == QLatin1String("profile"), "profile mode");
    expect(std::abs(r.valuePx - 80) <= 2.0, "profile step@80");
  }

  // 两段罐体：下 80 行亮，界面 y=120，液位高度 80。标定 10 px/mm → 8 mm。
  {
    QImage tank(80, 200, QImage::Format_RGB888);
    for (int y = 0; y < 200; ++y) {
      uchar* row = tank.scanLine(y);
      const uchar v = (y >= 120) ? 220 : 30;
      for (int x = 0; x < 80; ++x)
        row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = v;
    }
    QVariantMap p;
    p.insert(QStringLiteral("feature"), QStringLiteral("level"));
    p.insert(QStringLiteral("roiX"), 10);
    p.insert(QStringLiteral("roiY"), 0);
    p.insert(QStringLiteral("roiW"), 60);
    p.insert(QStringLiteral("roiH"), 200);
    p.insert(QStringLiteral("threshold"), 18);
    p.insert(QStringLiteral("pxPerMm"), 10);
    const MeasureResult r = runMeasure(tank, p);
    expect(r.ok, "level ok");
    expect(r.mode == QLatin1String("level"), "level mode");
    expect(std::abs(r.heightPx - 80) <= 2.0, "level height≈80");
    expect(std::abs(r.value - 8.0) <= 0.3, "level 8mm");
    expect(std::abs(r.center.y() - 120) <= 2.0, "level y≈120");
    expect(r.unit == QLatin1String("mm"), "level unit mm");
  }
  return fails;
}

}  // namespace sieans_qt
