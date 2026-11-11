#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>

#include <atomic>

namespace sieans_qt {

/** catalog delay：可取消的毫秒等待。 */
struct DelayResult {
  bool ok = false;
  bool cancelled = false;
  QString error;
  QString note;
  int milliseconds = 0;
  int elapsedMs = 0;
};

/**
 * 延时 milliseconds（0–30000）后返回，保留调用方的图像/点云。
 * cancel 置位时立即结束，不用于硬实时触发。
 */
DelayResult runDelay(const QVariantMap& params, std::atomic<bool>* cancel = nullptr);

/** catalog variables：写入或累加变量。 */
struct VarsAssignResult {
  bool ok = false;
  QString error;
  QString note;
  QString scope;
  QString name;
  QString mode;
  QVariant value;
  QVariant previous;
};

/**
 * 按 scope/name/mode 写入或累加变量。
 * scope=flow 写入 flowVars；global / module 写入对应作用域表。
 * value 可为字面量，或 ${name} / ${flow.name} 引用；increment 仅接受数值。
 */
VarsAssignResult runVariables(const QVariantMap& params, QVariantMap& flowVars,
                              QVariantMap& globalVars, QVariantMap& moduleVars);

QStringList flowExtrasSelfTest();

}  // namespace sieans_qt
