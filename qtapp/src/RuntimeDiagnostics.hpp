#pragma once
#include <QString>

namespace sieans_qt {
/** 安装线程安全 Qt 日志：每 PID 独立文件，2MiB×3 轮转，缺省 info；失败留 stderr。 */
void installRuntimeDiagnostics();
/** 记录本次启动的版本、依赖及硬件边界，不连接外部设备。 */
void logStartupDiagnostics();
}
