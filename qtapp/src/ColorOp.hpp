#pragma once

#include <QImage>
#include <QString>
#include <QStringList>
#include <QVariantMap>

namespace sieans_qt {

struct ColorResult {
  bool ok = false;
  QString error;
  QString method;  // convert / channel / threshold
  QString space;   // rgb / hsv
  QString channel; // r/g/b/h/s/v，仅 channel
  int fgCount = 0; // 颜色阈值前景像素数
  QImage image;    // 转换结果、单通道灰度或二值掩膜
  QString note;
};

/**
 * 纯 QImage 颜色处理，不依赖 OpenCV / Halcon。
 *
 * method:
 *  convert   色彩空间转换。space=hsv 把 RGB 转为打包 HSV（R=H, G=S, B=V）；
 *            space=rgb 把打包 HSV 转回 RGB。H 以 0–255 表示 0–360°。
 *  channel   提取通道 r/g/b（直接取输入 RGB）或 h/s/v（始终从输入 RGB 现算 HSV）。
 *  threshold 颜色阈值。space=rgb 或 hsv，输出 0/255 掩膜。色相在 hMin>hMax 时按环绕
 *            处理（例如红）。invert 可反色。
 *
 * 其它参数：roiX/Y/W/H（宽或高为 0 表示整图）；阈值各通道 min/max（rMin..vMax，默认 0–255）；
 * invert；minFgCount 仅用于注释，本函数不做判定。
 *
 * 诚实限制：打包 HSV 不是标准图像格式，算子不能自动识别输入是否已是打包 HSV；
 * 8 位色相约 1.4° 分辨率，RGB↔HSV 往返允许数个灰阶误差；不是相机色彩标定。
 */
ColorResult runColorOp(const QImage& src, const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList colorSelfTest();

}  // namespace sieans_qt
