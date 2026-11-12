#pragma once

#include <QString>
#include <QStringList>
#include <QVariantMap>

namespace sieans_qt {

struct ClassifyResult {
  bool ok = false;
  QString error;
  QString method;  // knn / svm / gmm / mlp
  QString label;
  int classIndex = -1;
  double score = 0;  // 投票占比、决策间隔映射或后验/softmax，范围约 0–1
  int trainCount = 0;
  int classCount = 0;
  int featureDim = 0;
  QString note;
};

/**
 * 纯 C++ 传统分类器，在本地特征表上训练并预测，不依赖 OpenCV / 机器学习库 / 云。
 *
 * method:
 *  knn   k 近邻，欧氏距离多数投票（可选距离加权）
 *  svm   线性 L2-SVM（主问题铰链损失 + L2，Pegasos 风格）；kernel=rbf 时用对偶铰链
 *        核梯度，不是完整 SMO/QP
 *  gmm   每类一个高斯混合（默认 1 个分量，即二次判别），EM 估计，满协方差+对角加载
 *  mlp   一层隐藏 tanh + Softmax 的小全连接网，批量交叉熵
 *
 * 训练数据（必须本地）：samples 为 JSON 或 CSV 文本；或 samplePath 指向本地文件
 *（CSV：最后一列为标签，# 为注释；JSON：[{features:[...],label:..}]）。
 * 预测向量：features 数组/逗号分隔，或由主窗把 featureVars 展开进来。
 *
 * 诚实限制：这不是 YOLO / 深度学习视觉分类，只吃已经提取好的小特征表；
 * 样本建议从几十到几千，特征维默认不超过 32；线性 SVM 只能分开近似可分数据；
 * GMM 假设每类近似高斯，少样本时协方差加岭；MLP 很小，会过拟合也受初值影响
 *（可用 seed 复现）；每次运行都从样本表重新训练，不读写云端模型。
 */
ClassifyResult runClassify(const QVariantMap& params);

/** 空列表表示全部通过。不需要 QApplication。失败不得静默跳过。 */
QStringList classifySelfTest();

}  // namespace sieans_qt
