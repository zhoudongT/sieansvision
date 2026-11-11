#pragma once

#include <QImage>
#include <QString>

namespace sieans_qt {

/** Python camera_backends.clamp_exposure_us — 100 .. 10_000_000 µs. */
int clampExposureUs(double v);

/** Python camera_backends.clamp_gain_db — 0 .. 48 dB. */
double clampGainDb(double v);

/**
 * Brightness scale used by apply_soft_controls_to_bgr.
 * 10000 µs and 0 dB → 1.0.
 */
double softToneScale(int exposureUs, double gainDb);

/**
 * CI-safe synthetic frame with a real sample QR composited when available,
 * so soft/GenTL-fallback open-and-run can decode barcodes.
 */
QImage makeSoftFrame(int width, int height, int seq, int exposureUs, double gainDb);

/** Soft 场景本体（QR / 标牌 / 卡尺条），不含 HUD 条和曝光增益字。
 *  与 makeSoftFrame 在 tone=1 时的画面主体一致，供参考图缺陷检测对齐。 */
QImage makeSoftScene(int width, int height);
/** makeSoftScene 上叠加一块固定位置的深色斑块，供缺陷检出烟雾。 */
QImage makeSoftSceneBlemish(int width, int height);

/**
 * Exposure/gain simulation. stampHud draws `exp=… gain=… #seq` so a live
 * preview shows the control took effect without hardware.
 */
QImage applySoftTone(const QImage& src, int exposureUs, double gainDb, int seq,
                     bool stampHud);

/** Optional override path for the embedded QR (tests / packaging). */
void setSoftQrSamplePath(const QString& path);

/** Last path that successfully loaded for soft·QR (empty if synthetic). */
QString softQrSampleLoadedPath();

}  // namespace sieans_qt
