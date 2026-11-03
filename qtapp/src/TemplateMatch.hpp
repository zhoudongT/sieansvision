#pragma once

#include <QImage>
#include <QRect>
#include <QVector>

namespace sieans_qt {

struct TemplateHit {
  QRect rect;
  double score = 0;
};

/** Grayscale SAD match. step>1 skips positions. Scores are 1 = identical. */
QVector<TemplateHit> findTemplate(const QImage& scene, const QImage& templ,
                                  double minScore, int maxMatches, int step = 0);

/** Center crop used as the VM “从当前图创建模板” default. */
QImage centerCrop(const QImage& src, int width, int height);

/** Crop around the brightest blob so a Soft 帧的白块能被当成模板。 */
QImage salientCrop(const QImage& src, int maxWidth, int maxHeight);

}  // namespace sieans_qt
