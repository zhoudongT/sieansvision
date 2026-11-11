#pragma once

#include "YoloInfer.hpp"

#include <QImage>
#include <QString>
#include <QVariantMap>

namespace sieans_qt {

/**
 * 解析本地 YOLO 权重路径，不下载、不创建文件。
 * 查找顺序：绝对/相对已存在路径、SIEANS_YOLO_MODELS_DIR、当前目录 models/、
 * 可执行文件旁与仓库 models/、以及 $HOME/.local/share/sieans/models。
 * @return 找到时为规范路径，否则空串。
 */
QString resolveYoloWeightPath(const QString& model);

/** 运行时能否加载用户前缀或系统中的 ONNX Runtime 动态库。 */
bool onnxRuntimeAvailable();

/**
 * 用本地 .onnx 与 ONNX Runtime 做 YOLO 检测推理（YOLOv8/YOLO11 常见输出布局）。
 * 成功时写出 work 坐标系下的候选框（已按置信度过滤，尚未做类别筛选/NMS/ROI 反映射）。
 * 失败（无运行时、不是检测输出、推理异常等）返回 false 并填写 error，由调用方回退 software。
 * 不处理 .pt，不自动下载权重。
 */
bool tryYoloOnnxDetect(const QImage& work, const QString& weightPath,
                       const QVariantMap& params, int imageSize,
                       YoloResult* out, QString* error);

/**
 * 用本地 .onnx 与 ONNX Runtime 做 YOLO 实例分割推理（YOLOv8/YOLO11-seg 双输出：
 * preds [4+nc+nm, N] + proto [nm, mh, mw]）。
 * 成功时写出 work 坐标系下的框、掩膜面积、中心与轮廓。
 * 失败（无运行时、不是分割输出、推理异常等）返回 false 并填写 error，由调用方回退 software。
 * 不处理 .pt，不自动下载权重。
 */
bool tryYoloOnnxSegment(const QImage& work, const QString& weightPath,
                        const QVariantMap& params, int imageSize,
                        YoloResult* out, QString* error);

}  // namespace sieans_qt
