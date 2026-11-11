#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>

namespace sieans_qt {

/** 一次 OPC UA 读/写/浏览/等待结果，字段对齐 catalog 与 Python 适配器。 */
struct OpcUaResult {
  bool ok = false;
  QString error;
  QString note;
  QString protocol = QStringLiteral("opc-ua");
  QString action;
  QString endpoint;
  QString nodeId;
  QString dataType;
  QVariant value;
  QVariantList values;
  QVariantList items;
  bool isArray = false;
  bool acknowledged = false;
  bool triggered = false;
  bool passed = false;
  bool timedOut = false;
  int notificationCount = 0;
  int browseCount = 0;
  bool truncated = false;
  QString status;
  quint32 statusCode = 0;
  QString quality;
  QString sourceTimestamp;
  QString serverTimestamp;
  int elapsedMs = 0;
};

/**
 * 读取一个 OPC UA 变量节点的值、类型与质量。
 * connection=simulator 访问进程内映像；connection=server 走 opc.tcp（可指向软从站）。
 * 每次调用新建会话并在结束时关闭。仅支持 Security=None 匿名。
 */
OpcUaResult runOpcUaRead(const QVariantMap& params);
/** 按指定类型写入标量或一维数组。服务端应答不等于物理完成，失败不回滚。 */
OpcUaResult runOpcUaWrite(const QVariantMap& params);
/** 浏览节点下一层层级引用，结果超过上限时标记截断。 */
OpcUaResult runOpcUaBrowse(const QVariantMap& params);
/**
 * 单次有界等待：条件成立模式在初值满足时立即触发，边沿模式先建立基线。
 * 质量不良、通知溢出或协议错误停止，不作为条件超时继续。
 */
OpcUaResult runOpcUaWait(const QVariantMap& params);

/**
 * 本机 OPC UA 软从站（UACP + UASC Security=None），与 simulator 共用节点映像。
 * 默认监听 127.0.0.1:4840，被占用时由调用方 bump。
 */
class OpcUaSoftServer {
 public:
  bool start(quint16 port, QString* error);
  void stop();
  bool running() const;
  quint16 port() const;
  QString endpoint() const;
};

OpcUaSoftServer& opcUaSoftServer();

/** 无界面自检。空列表表示全部通过。 */
QStringList opcUaSelfTest();

}  // namespace sieans_qt
