#pragma once

#include <QString>
#include <QStringList>

namespace sieans_qt {

/**
 * 在 timeoutMs 内连接 TCP（非阻塞 connect + poll），成功返回阻塞套接字并设好收发超时。
 * 失败返回 -1，并写入带原因分类的中文错误（被拒绝 / 超时 / 已断开 / 其它）。
 */
int connectTcpTimeout(const QString& host, quint16 port, int timeoutMs, QString* error,
                      const QString& label);

/**
 * 将协议错误归为 refused / timeout / closed / other，便于界面和冒烟报告。
 */
QString classifyProtocolFailure(const QString& error);

/**
 * 对已有软从站做停机失败、分类报错、再启动后重连成功。
 * 若本进程已有软从站在跑，测完会按原端口恢复监听。空列表表示通过。
 */
QStringList protocolRobustnessSelfTest();
/** 最近一次自检里“软从站停机”失败的分类（refused/timeout/closed/other）。 */
QString lastProtocolRobustClass();

}  // namespace sieans_qt
