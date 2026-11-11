#pragma once

#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

/** 单个点（XYZ，可选 0–1 颜色）。 */
struct CloudPoint {
  double x = 0;
  double y = 0;
  double z = 0;
  double r = 0.5;
  double g = 0.55;
  double b = 0.6;
  bool hasColor = false;
};

/** 流程中传递的点云缓冲（单位 / 坐标系随点保留）。 */
struct PointCloud {
  QVector<CloudPoint> points;
  QString unit = QStringLiteral("mm");
  QString frame = QStringLiteral("sensor");
  bool isEmpty() const { return points.isEmpty(); }
};

/** 轴对齐包围盒测量（当前坐标系，体积不是实体体积）。 */
struct CloudBounds {
  double minX = 0, minY = 0, minZ = 0;
  double maxX = 0, maxY = 0, maxZ = 0;
  double centerX = 0, centerY = 0, centerZ = 0;
  double sizeX = 0, sizeY = 0, sizeZ = 0;
  double boundingBoxVolume = 0;
  bool valid = false;
};

/** 3D 点云算子统一结果，字段对齐 catalog cloud_* 。 */
struct CloudResult {
  bool ok = false;
  QString error;
  QString note;
  QString operation;
  QString method;
  QString backend = QStringLiteral("software");
  int inputCount = 0;
  int pointCount = 0;
  PointCloud cloud;

  // plane
  double nx = 0, ny = 0, nz = 0, d = 0;
  int inlierCount = 0;
  double inlierRatio = 0;
  double rmsError = 0;
  QString output;

  // cluster
  int clusterCount = 0;
  int noiseCount = 0;

  // measure / shared bounds
  CloudBounds bounds;

  // height
  double minHeight = 0, maxHeight = 0, meanHeight = 0;
  double baselineZ = 0, cellSize = 0;
  int occupiedCells = 0;
  double sampledArea = 0, estimatedVolume = 0;
  QString volumeUnit;

  // register
  bool found = false;
  double fitness = 0;
  double targetFitness = 0;
  double dx = 0, dy = 0, dz = 0;
  double transform[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
};

/** 软仿真完整场景：水平面 + 两团目标 + 一颗远离噪点。 */
PointCloud makeSoftCloudFixture();
/** 20×10×5 mm 标准件八角点，供尺寸测量。 */
PointCloud makeSoftCloudPart();
/** 20×10 顶面 z=5，cellSize=1 时网格体积为 1000。 */
PointCloud makeSoftCloudSurface();
/** 较密的标准件采样，供 ICP / 全局配准。 */
PointCloud makeSoftCloudRegisterSet();

/**
 * 按 inputSource 解析输入点云（upstream / soft_fixture / soft_part /
 * soft_surface / soft_register），并可叠加 inputShiftX/Y/Z。
 */
PointCloud resolveCloudInput(const PointCloud& upstream, const QVariantMap& params,
                             QString* error = nullptr);

/** catalog: cloud_filter（voxel / crop / statistical / radius）。 */
CloudResult runCloudFilter(const PointCloud& input, const QVariantMap& params);
/** catalog: cloud_plane（RANSAC 主平面）。 */
CloudResult runCloudPlane(const PointCloud& input, const QVariantMap& params);
/** catalog: cloud_cluster（DBSCAN）。 */
CloudResult runCloudCluster(const PointCloud& input, const QVariantMap& params);
/** catalog: cloud_measure（轴对齐包围盒）。 */
CloudResult runCloudMeasure(const PointCloud& input, const QVariantMap& params);
/** catalog: cloud_height（相对 +Z 基准的可见表面网格体积）。 */
CloudResult runCloudHeight(const PointCloud& input, const QVariantMap& params);
/** catalog: cloud_register（点到点 ICP，或 PCA 粗对齐 + ICP 的软件全局定位）。 */
CloudResult runCloudRegister(const PointCloud& input, const QVariantMap& params);

/** 按 operation 键分发。空列表表示自测全部通过。不要求 QApplication。 */
CloudResult runCloudOp(const QString& operation, const PointCloud& input,
                       const QVariantMap& params);
QStringList cloudSelfTest();

}  // namespace sieans_qt
