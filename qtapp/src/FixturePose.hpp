#pragma once

#include "TemplateMatch.hpp"

#include <QImage>
#include <QPointF>
#include <QPolygonF>
#include <QRect>
#include <QString>
#include <QStringList>
#include <QVariantMap>

namespace sieans_qt {

struct Pose2D {
  double x = 0;
  double y = 0;
  double angleDeg = 0;
  double scale = 1;
  bool ok = false;
};

/** Similarity (image y-down): x' = fx + s*(c*x - s*y), y' = fy + s*(s*x + c*y). */
QPointF poseMap(const Pose2D& pose, const QPointF& local);
QPointF poseUnmap(const Pose2D& pose, const QPointF& image);

struct FollowRoi {
  bool active = false;
  QPolygonF corners;  // image-space quad, clockwise from local top-left
  QRect aabb;
  QPointF center;
  int patchW = 0;
  int patchH = 0;
  double roiX = 0;
  double roiY = 0;
};

Pose2D poseFromParams(const QVariantMap& params, const QString& prefix = QString());
/** If followFixture is set, copy fixture* from flow vars into params (for algo calls). */
void injectFixtureFromVars(QVariantMap& params, const QVariantMap& vars);

FollowRoi resolveFollowRoi(const QVariantMap& params, int imageW, int imageH);
/** Warp a fixture-local ROI into an axis-aligned patch (nearest neighbor). */
QImage extractFollowPatch(const QImage& src, const FollowRoi& roi, const Pose2D& pose);

struct PoseCorrectResult {
  bool ok = false;
  bool boundOk = false;
  QString error;
  QString note;
  QString status;
  Pose2D pose;
  QString boundFrom;
  double score = 0;
  QPolygonF axisX;
  QPolygonF axisY;
  QPointF origin;
};

/** Bind upstream locate (from params / injected locate* / bind fields) into a fixture pose. */
PoseCorrectResult runPoseCorrect(const QVariantMap& params, const QVariantMap& vars);

QStringList locateSelfTest();

}  // namespace sieans_qt
