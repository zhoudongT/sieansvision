#pragma once

#include <QImage>
#include <QPointF>
#include <QRect>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

/** 单个连通域的几何与灰度特征，坐标均为原图像素。 */
struct RegionBlob {
  int label = 0;
  int areaPixels = 0;
  int perimeterPx = 0;
  QPointF centroid;
  double orientationDeg = 0.0;  // 等效椭圆长轴，+x 为 0，逆时针为正
  QRect bbox;
  double majorAxisPx = 0.0;  // 等效椭圆长轴长度（2√λ_max）
  double minorAxisPx = 0.0;
  double circularity = 0.0;  // 4πA/P²，P 为离散边界像素数，理想连续圆为 1
  double compactness = 0.0;  // A / (π (major/2)²)，细长目标更小
  double eccentricity = 0.0;  // √(1-(b/a)²)，圆为 0
  double grayMean = 0.0;
  int grayMin = 0;
  int grayMax = 0;
};

struct RegionResult {
  bool ok = false;
  QString error;
  QString method;  // fixed / otsu / watershed / growing
  int thresholdUsed = 0;
  int rawCount = 0;
  int count = 0;
  int seedCount = 0;  // 分水岭/区域生长使用的种子数；普通连通域为 0
  QVector<RegionBlob> items;
  QImage mask;  // 与输入同尺寸的二值掩膜（0/255），仅保留过滤后目标
  QString note;
};

/**
 * 纯 QImage 区域分析：固定或 Otsu 阈值、连通域、特征表与属性过滤。
 * method=watershed 时在二值距离变换上做标记分水岭，用于拆分有颈缩的粘连目标。
 * method=growing 时从距离峰种子按灰度容差生长，用于灰度有差别的粘连目标。
 * 不依赖 OpenCV / Halcon。
 *
 * Params:
 *  method: fixed（默认）/ otsu / watershed / growing
 *  threshold: 固定阈值 0–255，默认 127（Otsu 时忽略；watershed/growing 用于二值化）
 *  invert: 提取暗目标
 *  roiX,roiY,roiW,roiH: 可选 ROI；宽或高为 0 表示整图
 *  minArea / maxArea: 面积过滤，maxArea<=0 表示无上限
 *  minCircularity / maxCircularity: 圆形度，默认 0–1
 *  minGrayMean / maxGrayMean: 灰度均值，默认 0–255
 *  minSeedRadius: 距离峰最小半径，默认 3（仅 watershed/growing）
 *  minSeedDist: 种子最小间距，默认 8（仅 watershed/growing）
 *  growTolerance: 区域生长灰度容差，默认 25（仅 growing）
 *  maxCount: 过滤后最多保留个数，默认 200
 *  output: overlay（下游仍用原图）或 mask（用二值掩膜替换工作图）
 *
 * 诚实限制：严重重叠、没有稳定距离峰、或目标与背景粘成一片时仍可能合并；
 * 分水岭对近圆凸目标更有效，不是通用实例分割。区域生长在灰度接近时主要
 * 靠多种子先到先得拆分，分界不一定落在最窄颈缩处。
 */
RegionResult runRegionAnalyze(const QImage& src, const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList regionSelfTest();

}  // namespace sieans_qt
