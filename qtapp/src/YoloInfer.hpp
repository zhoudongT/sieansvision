#pragma once

#include <QImage>
#include <QPointF>
#include <QRectF>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

/** 一次 YOLO 检测 / 实例分割目标。bbox 为图像坐标 [x,y,w,h]。 */
struct YoloItem {
  int classId = 0;
  QString label;
  double confidence = 0;
  QRectF bbox;
  int areaPixels = 0;
  QPointF center;
  QVector<QVector<QPoint>> contours;
  QVector<bool> contourIsHole;
};

/** YOLO 算子结果，字段对齐 catalog yolo / yolo_segment。 */
struct YoloResult {
  bool ok = false;
  QString error;
  QString note;
  QString model;
  QString backend = QStringLiteral("software");
  QString device = QStringLiteral("cpu");
  QString requestedDevice;
  int count = 0;
  int rawCount = 0;
  int filteredCount = 0;
  bool limitReached = false;
  QString output = QStringLiteral("overlay");
  QVector<YoloItem> items;
  int unionAreaPixels = 0;
  int summedAreaPixels = 0;
  QImage mask;
};

/**
 * YOLO 目标检测（catalog: yolo）。
 * 本地 .onnx + 可用的 ONNX Runtime 时走真实推理（backend=onnx）。
 * 无本地权重、不是 .onnx、或运行时/推理失败时，使用软图确定性检测器（backend=software），
 * 在原图上按特征色寻找目标。不自动下载模型，缺失权重不算失败，不要求 GPU。
 *
 * 权重查找（检测与分割共用）：绝对/相对路径、SIEANS_YOLO_MODELS_DIR、
 * 当前目录 models/、可执行文件旁与仓库 models/、以及 $HOME/.local/share/sieans/models。
 * 检测可放入 yolov8n.onnx / yolo11n.onnx；分割可放入 yolov8n-seg.onnx / yolo11n-seg.onnx
 *（或 yolov8-seg / yolo11-seg 导出的同名 .onnx）。
 *
 * Params:
 *  model: 默认 yolo11n.pt（本地 .onnx 走真实路径；.pt 或缺失时走 software）
 *  device: cpu|auto|cuda:0（software 路径始终在 CPU 上运行）
 *  confidence: 默认 0.25
 *  iou: 默认 0.45（NMS）
 *  imageSize: 32–1920，且为 32 的倍数，默认 640（software 仅记录规格，不缩放）
 *  classes: 空=全部；逗号分隔或列表，按 classId 或标签筛选
 *  minArea: 最小面积，默认 1
 *  maxDetections: 最多检出，默认 50
 *  followFixture / fixtureVar / roiX,roiY,roiW,roiH
 */
YoloResult runYoloDetect(const QImage& image, const QVariantMap& params);

/**
 * YOLO 实例分割（catalog: yolo_segment）。
 * 本地 .onnx + 可用的 ONNX Runtime 时走真实掩膜推理（backend=onnx，YOLOv8/11-seg 双输出）。
 * 无本地权重、不是 .onnx、或运行时/推理失败时，回退软图确定性分割（backend=software），
 * 与检测共用特征色连通域，额外输出掩膜轮廓、孔洞、像素面积与中心。不自动下载，缺失不算失败。
 * 面积按前景像素计（孔洞内像素不计入）；重叠实例的面积之和可能大于并集。
 * 轮廓简化（contourTolerance）不改变掩膜面积。
 *
 * Params: 同检测，另加
 *  model: 默认 yolo11n-seg.pt（本地 .onnx 走真实路径；.pt 或缺失时走 software）
 *  imageSize: 32–1280，且为 32 的倍数；并满足 maxDetections×imageSize² ≤ 32_768_000
 *  maxDetections: 1–100，默认 50
 *  minArea: 默认 1
 *  contourTolerance: 默认 0.5（Ramer–Douglas–Peucker）
 *  overlayAlpha: 默认 0.35
 *  output: overlay|mask（mask 时由调用方用二值图替换下游工作图）
 */
YoloResult runYoloSegment(const QImage& image, const QVariantMap& params);

/** 空列表表示全部通过。不要求 QApplication。 */
QStringList yoloSelfTest();

}  // namespace sieans_qt
