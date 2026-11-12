#pragma once

#include <QImage>
#include <QPointF>
#include <QSize>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

/** 针孔相机内参 + 径向畸变（Brown-Conrady，不含倾斜 skew，切向 p1/p2 固定为 0）。 */
struct CameraIntrinsics {
  double fx = 0, fy = 0, cx = 0, cy = 0;
  double k1 = 0, k2 = 0;
  int width = 0, height = 0;
};

struct CameraCalResult {
  bool ok = false;
  QString error;
  QString method;  // calibrate / undistort
  QString pattern; // checkerboard / circles
  CameraIntrinsics intrinsics;
  double rmse = 0.0;  // 重投影或检测残差，像素
  int views = 0;
  int detected = 0;
  QVector<QPointF> corners;  // 当前图检测到的角点/圆心，已按行主序排列
  QImage image;              // 校正后的图像（undistort 或 calibrate 且 output=undistort）
  QImage overlay;            // 原图尺寸，供叠加检测点（可能为空）
  QString note;
};

/**
 * 纯 QImage 相机标定与去畸变，不依赖 OpenCV / Halcon。
 *
 * method=calibrate: 在当前图（及可选的 imageDir / imagePaths 多视图）上检测棋盘格
 *   内角点或圆点阵列，按平面靶标 Zhang 标定估计 fx,fy,cx,cy,k1,k2，并报告 RMSE。
 *   单视图会锁定 cx,cy 为像主点（默认图像中心）且 fx=fy，只估计焦距与径向畸变。
 * method=undistort: 用给定（或上游）fx,fy,cx,cy,k1,k2 对工作图做反向映射去畸变。
 *
 * Params（摘）：
 *  pattern: checkerboard | circles
 *  rows, cols: 内角点或圆心的行列数（rows 为 Y 方向）
 *  squareSize: 相邻点世界间距，默认 1
 *  imageDir, imagePaths: 额外标定图（png/jpg，逗号分隔或目录）
 *  fx,fy,cx,cy,k1,k2: undistort 使用；calibrate 可用作初值
 *  output: overlay（保留原图）或 undistort（用校正图替换）
 *
 * 诚实限制：这是针孔+2 阶径向畸变，没有切向畸变、薄棱镜或鱼眼模型；
 * 单视图不能独立求出全部内参；检测依赖高对比、完整可见的规则阵列，
 * 模糊、遮挡、过强畸变或非平面靶会失败或偏差较大。不是 measure 里两点 pxPerMm。
 */
CameraCalResult runCameraCal(const QImage& src, const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList cameraCalSelfTest();

}  // namespace sieans_qt
