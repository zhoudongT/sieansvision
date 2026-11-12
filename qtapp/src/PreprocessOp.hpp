#pragma once

#include <QImage>
#include <QString>
#include <QStringList>
#include <QVariantMap>

namespace sieans_qt {

struct PreprocessResult {
  bool ok = false;
  QString error;
  QString method;  // grayscale / invert / threshold / blur / canny / open / close / erode / dilate
  int kernel = 0;
  int threshold = 0;
  QImage image;  // 始终 RGB888，与历史 applyPreprocess 输出一致
  QString note;
};

/**
 * 纯 QImage 图像预处理，不依赖 OpenCV / Halcon。
 *
 * 方法名优先读 method，缺省时回退到旧参数 mode，以兼容已有方案。
 * 认可的方法：
 *  grayscale / gray / mono  转为灰度后再扩成 RGB888
 *  invert                   各通道按 255-x 反色（目录未列出，保留既有能力）
 *  threshold                灰度后按 threshold 二值化（≥ 为 255）
 *  blur                     可分离高斯模糊；kernel 须为奇数，偶数会 +1，范围 1–51
 *  canny                    先高斯再 Sobel、非极大值抑制与双阈值滞后；
 *                           阈值用 cannyLow / cannyHigh，缺省时由 threshold 与 2×threshold 推导
 *  erode / dilate / open / close  方形结构元的灰度最小 / 最大（开=先蚀后胀，闭=先胀后蚀）
 *
 * 诚实限制：不是 OpenCV 的预处理模块；Canny 为 8 方向滞后的经典近似，无亚像素；
 * 形态学只支持方形结构元；大核是逐像素可分离实现，大图会慢；输出为 RGB888。
 */
PreprocessResult runPreprocess(const QImage& src, const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList preprocessSelfTest();

}  // namespace sieans_qt
