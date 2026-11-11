#pragma once

#include "CaliperMeasure.hpp"

#include <QImage>
#include <QPointF>
#include <QPolygonF>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

struct MeasureItem {
  QString kind;  // circle / line / contour / points / angle
  QPointF center;
  QPointF p0;
  QPointF p1;
  QPolygonF polygon;
  double radiusPx = 0;
  double diameterPx = 0;
  double lengthPx = 0;
  double angleDeg = 0;
  double widthPx = 0;
  double heightPx = 0;
  double areaPx = 0;
  double valuePx = 0;
  double value = 0;  // scaled into unit
};

struct MeasureResult {
  bool ok = false;
  QString error;
  QString note;
  QString mode;  // caliper / circles / contours / lines / points / angle
  QString unit;  // px | mm | ...
  bool calibrated = false;
  double pxPerMm = 0;        // pixels per millimetre (0 = px only)
  double unitsPerPixel = 1;  // unit per pixel (1 if px)
  int count = 0;
  double valuePx = 0;
  double value = 0;
  double radiusPx = 0;
  double diameterPx = 0;
  double lengthPx = 0;
  double angleDeg = 0;
  double widthPx = 0;
  double heightPx = 0;
  double areaPx = 0;
  double radius = 0;
  double diameter = 0;
  double length = 0;
  double width = 0;
  double height = 0;
  double area = 0;
  QPointF center;
  QPointF p0;
  QPointF p1;
  QVector<MeasureItem> items;
  bool judgeEnable = false;
  bool judgeOk = true;
  CaliperResult caliper;
};

/**
 * 尺寸测量与标定，对齐 PySide/engine.measure，并补齐直线长度与夹角。
 * modes/feature: caliper | circles | contours | lines | points | angle
 * 标定：pxPerMm，或 calibration.points + distance + unit（等比例平面）。
 * 卡尺模式转调 runCaliper，不改变原卡尺行为。No OpenCV / Halcon.
 */
MeasureResult runMeasure(const QImage& src, const QVariantMap& params);

/** Empty list = all passed. Does not require QApplication. */
QStringList measureSelfTest();

}  // namespace sieans_qt
