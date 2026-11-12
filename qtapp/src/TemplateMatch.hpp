#pragma once

#include <QImage>
#include <QPointF>
#include <QPolygonF>
#include <QRect>
#include <QString>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

struct TemplateHit {
  QRect rect;
  QPolygonF corners;
  QPointF center;
  double score = 0;
  double angleDeg = 0;
  double scale = 1;    // 兼容：均匀尺度，或各向异性时取 scaleX
  double scaleX = 1;
  double scaleY = 1;
  int templateIndex = 0;
  QString templateName;
};

/** Grayscale SAD match. step>1 skips positions. Scores are 1 = identical. */
QVector<TemplateHit> findTemplate(const QImage& scene, const QImage& templ,
                                  double minScore, int maxMatches, int step = 0);

/** Center crop used as the VM “从当前图创建模板” default. */
QImage centerCrop(const QImage& src, int width, int height);

/** Crop around the brightest blob so a Soft 帧的白块能被当成模板。 */
QImage salientCrop(const QImage& src, int maxWidth, int maxHeight);

struct LocateResult {
  bool ok = false;
  QString error;
  QString note;
  QVector<TemplateHit> hits;
  QImage templateUsed;
  QString templatePath;
  bool templateCreated = false;
};

/** Resolve file / soft_plate / capture template. */
QImage resolveLocateTemplate(const QImage& scene, const QVariantMap& params,
                             QString* error = nullptr, bool* created = nullptr,
                             QString* pathOut = nullptr);

/**
 * Template locate with optional rotation, uniform or anisotropic scale search,
 * SAD or NCC metric, and a multi-template library. Overlap NMS and pose
 * (center, angle, AABB + corners). No OpenCV / Halcon. No deformable /
 * variation-model matching (deferred; would not be an honest subset here).
 */
LocateResult runLocate(const QImage& scene, const QVariantMap& params);

}  // namespace sieans_qt
