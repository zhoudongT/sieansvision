#pragma once

#include <QImage>
#include <QString>
#include <QStringList>
#include <QVariantMap>

namespace sieans_qt {

struct FftResult {
  bool ok = false;
  QString error;
  QString method;  // lowpass / highpass / bandpass / bandstop / spectrum
  int padW = 0;
  int padH = 0;
  double sharpness = 0;  // 输入图高频能量占比，与滤波无关
  QImage image;          // 空域结果或对数幅度谱，RGB888
  QString note;
};

/**
 * 纯 C++ 频域处理，不依赖 FFTW / OpenCV / Halcon。
 *
 * method:
 *  lowpass / highpass / bandpass / bandstop
 *      灰度正变换 → 高斯频率掩膜 → 逆变换回到空域。
 *      cutoff / cutoffHigh 是归一化频率（周期/像素，Nyquist=0.5）。
 *      低通/高通是从直流算起的高斯；带通/带阻是以 (cutoff+cutoffHigh)/2 为中心、
 *      半宽约 (cutoffHigh-cutoff)/4 为 σ 的高斯环带。
 *      高通与带通因去掉直流，显示时把像素偏置 +128，便于看出正负残差。
 *  spectrum
 *      输出 fftshift 后的对数幅度谱（log(1+|F|) 拉伸到 0–255），不回到空域。
 *
 * 其它参数：window=none|hann（正变换前加窗，减轻泄漏，但会压暗边缘）；
 * resultVar 前缀默认 fft，写出 fftOk / fftSharpness。
 *
 * sharpness 是输入（加窗后）频谱中半径大于 sharpCutoff（默认 0.15）的能量
 * 占非直流总能量的比例，可作简单清晰度参考，不是相机自动对焦。
 *
 * 诚实限制：内部补到 2 的幂再裁回原尺寸，单边补齐上限 4096；只处理灰度；
 * 高斯掩膜不是理想矩形带，也不是 Halcon FFT；无窗时周期延拓会在边界产生振铃；
 * 大图按 O(N log N) 仍可能较慢。
 */
FftResult runFft(const QImage& src, const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList fftSelfTest();

}  // namespace sieans_qt
