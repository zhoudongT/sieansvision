#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>

#include <atomic>

namespace sieans_qt {

/** TCP / UDP 报文通信结果，字段对齐 catalog tcp_exchange / udp_exchange。 */
struct SocketXferResult {
  bool ok = false;
  QString error;
  QString note;
  QString protocol;  // TCP / UDP
  QString mode;      // exchange / send / receive
  QString encoding;
  QString host;
  int port = 0;
  int localPort = 0;
  bool simulated = false;
  QString delivery;  // sent / received
  bool acknowledged = false;
  QVariant value;
  int byteLength = 0;
  int sentBytes = 0;
  int trailingBytes = 0;
  int elapsedMs = 0;
};

/**
 * 连接远端 TCP 服务，按分帧规则发送和/或接收一帧。
 * connection=simulator 使用进程内 127.0.0.1 原样回显（与 CommHub :19956 无关）。
 * 每次调用新建连接并在结束时关闭。无自动重试；发送完成不代表设备已执行。
 * cancel 置位时中止等待（数据若已发出则不能回滚）。
 */
SocketXferResult runTcpExchange(const QVariantMap& params,
                                std::atomic<bool>* cancel = nullptr);

/**
 * 发送或接收一个 UDP 数据报，并按远端 IP/端口筛选来源。
 * 不保证送达、顺序或不重复；不支持广播/组播。发送上限 65507 字节。
 */
SocketXferResult runUdpExchange(const QVariantMap& params,
                                std::atomic<bool>* cancel = nullptr);

/** 空列表表示全部通过。 */
QStringList socketExchangeSelfTest();

}  // namespace sieans_qt
