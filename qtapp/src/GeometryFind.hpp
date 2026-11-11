#pragma once

#include <QImage>
#include <QLineF>
#include <QPointF>
#include <QPolygonF>
#include <QRectF>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

struct GeometryItem {
  QString kind;  // circle / line / rect / contour / edge
  QPointF center;
  QPointF start;
  QPointF end;
  double radius = 0;
  double diameter = 0;
  double length = 0;
  double angleDeg = 0;
  double area = 0;
  double perimeter = 0;
  double width = 0;
  double height = 0;
  double fillRatio = 0;
  double circularity = 0;
  double score = 0;
  QRectF bbox;
  QPolygonF polygon;
  bool judgeOk = true;
  QString judgeStatus = QStringLiteral("OK");
  double judgeMetric = 0;
};

struct GeometryResult {
  bool ok = false;
  QString error;
  QString feature;
  QString method;
  int count = 0;
  int edgePixels = 0;
  bool judgeEnable = false;
  bool judgeOk = true;
  QVector<GeometryItem> items;
  QString note;
};

/**
 * Pure-QImage 几何特征查找，对齐 PySide/engine.geometry。
 * 支持 contours / lines / circles / rects / edges。No OpenCV / Halcon.
 *
 * Params (defaults):
 *  feature: contours|lines|circles|rects|edges
 *  threshold: 轮廓二值阈值 0–255 (default 127)
 *  minArea: 最小轮廓/矩形面积 (default 50)
 *  invert: 反色提取深色目标
 *  filterSize: 平滑半径 1–31 (1=不模糊)
 *  maxCount: 最多输出 1–100 (default 50)
 *  cannyLow/cannyHigh / edgeThreshold: 边缘阈值
 *  votes, minLength, maxGap, minDistance
 *  minRadius, maxRadius, annulusInner, annulusOuter
 *  angleNormalize, reverseFind
 *  judgeEnable / judgeMin / judgeMax
 *  roiX,roiY,roiW,roiH
 *  target: soft_circle | soft_line | soft_follow （软场景自动 ROI）
 *  followFixture: 在夹具坐标系搜索
 */
GeometryResult runGeometry(const QImage& src, const QVariantMap& params);

/** Empty list = all passed. Does not require QApplication. */
QStringList geometrySelfTest();

}  // namespace sieans_qt
