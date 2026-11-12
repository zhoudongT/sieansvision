#pragma once

#include <QImage>
#include <QString>
#include <QStringList>
#include <QVariantMap>

namespace sieans_qt {

struct WarpResult {
  bool ok = false;
  QString error;
  QString method;  // affine / perspective / polar
  int outWidth = 0;
  int outHeight = 0;
  QImage image;
  QString note;
};

/**
 * 纯 QImage 几何变换，不依赖 OpenCV / Halcon。
 *
 * method=affine: 2×3 仿射（a00..a12），或 3 组 src/dst 点估计。invert 使用逆变换。
 * method=perspective: 3×3 单应（h00..h22），或 4 组 src/dst 点估计。invert 使用逆单应。
 * method=polar: 环形展开。以 (centerX,centerY) 为圆心，半径 [rMin,rMax]、
 *   角度 [angleStart, angleStart+angleSpan]（度，逆时针，+x 为 0）展开到矩形，
 *   列=角度、行=半径（上内下外）。invert 则从展开图映射回直角坐标。
 *
 * 采样为双线性。输出尺寸默认与输入相同；polar 默认为宽约 2πrMax、高为径向像素。
 *
 * 诚实限制：不是相机标定去畸变；双线性在强透视或大旋转下会有插值模糊；
 * 逆变换在接近奇异的矩阵上会失败。
 */
WarpResult runWarp(const QImage& src, const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList warpSelfTest();

}  // namespace sieans_qt
