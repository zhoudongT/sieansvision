#pragma once

#include <QImage>
#include <QRect>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

struct DefectItem {
  QRect bbox;
  int areaPixels = 0;
};

struct DefectResult {
  bool ok = false;          // algorithm ran (reference present, sizes usable)
  QString error;
  bool passed = false;      // judge / legacy ratio gate
  bool judgeEnable = true;
  bool judgeOk = true;
  int count = 0;
  double defectRatio = 0.0;
  int totalArea = 0;
  int maxArea = 0;
  QVector<DefectItem> items;
  QString note;
  QString method = QStringLiteral("absdiff");
};

/** Load or synthesize the reference image (file / soft_scene / soft_scene_blemish). */
QImage resolveDefectsReference(const QImage& current, const QVariantMap& params,
                               QString* error = nullptr);

/**
 * Pure-QImage 参考图缺陷检测（absdiff + 阈值 + 连通域），对齐 PySide/engine.defects。
 * No OpenCV / Halcon.
 *
 * Params:
 *  differenceThreshold|threshold: 1–255 (default 30)
 *  minArea: default 20
 *  maxCount: default 200
 *  blur: odd kernel, 0 = 不模糊, default 3
 *  maxDefectRatio: legacy pass gate when judgeEnable=false (default 1)
 *  judgeEnable: default true
 *  judgeMaxCount: default 0 (any blob → NG)
 *  judgeMaxRatio: default 0.05
 *  ignoreBottomPx: crop this many rows from the bottom of both images (soft HUD)
 *  roiX,roiY,roiW,roiH: optional compare ROI
 *  scaleReference: default true — scale reference to the compare size
 *  showOverlay / showBoxes / showLabels
 */
DefectResult runDefects(const QImage& current, const QImage& reference,
                        const QVariantMap& params);

/** Empty list = all passed. Does not require QApplication. */
QStringList defectsSelfTest();

}  // namespace sieans_qt
