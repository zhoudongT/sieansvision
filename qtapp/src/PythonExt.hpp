#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>

#include <atomic>

namespace sieans_qt {

/** catalog script / plugin：Python 子进程执行结果。 */
struct PythonExtResult {
  bool ok = false;
  bool cancelled = false;
  QString error;
  QString note;
  QString logs;
  QVariantMap result;
  int elapsedMs = 0;
  QString pluginId;
  QString pluginVersion;
  QString operatorId;
};

/**
 * 以独立 Python 子进程执行用户脚本的 run(ctx)。
 * 将 arguments 注入 ctx.params，并把 vars / results 交给脚本；返回后把
 * data.variables 与 outputBindings 写回现有 flow/global/module 表。
 * cancel 置位或超时时终止子进程。不是安全沙箱，只运行可信代码。
 */
PythonExtResult runScript(const QVariantMap& params, QVariantMap& flowVars,
                          QVariantMap& globalVars, QVariantMap& moduleVars,
                          const QVariantMap& upstreamResults = {},
                          std::atomic<bool>* cancel = nullptr);

/**
 * 按清单加载已安装/随仓库的算子插件并调用其入口（同样走 script_worker）。
 * 工程钉死 pluginId / pluginVersion / operatorId；仅接受已声明的结果字段。
 */
PythonExtResult runPlugin(const QVariantMap& params, QVariantMap& flowVars,
                          QVariantMap& globalVars, QVariantMap& moduleVars,
                          const QVariantMap& upstreamResults = {},
                          std::atomic<bool>* cancel = nullptr);

QStringList pythonExtSelfTest();

}  // namespace sieans_qt
