#pragma once

#include <QByteArray>
#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>

namespace sieans_qt {

/** 串口报文一次收发的结果，字段对齐 catalog serial_exchange / 既有工业适配器。 */
struct SerialResult {
  bool ok = false;
  QString error;
  QString note;
  QString mode;         // exchange / send / receive
  QString serialPort;   // 回环模拟 or /dev/...
  bool simulated = false;
  QString delivery;     // received / sent
  QString encoding;
  QString sentEncoding;
  QString value;        // 解码后的接收（仅发送则为发出内容）
  QString sentValue;    // 发送侧原文，接收解码不会覆盖
  QVariant decoded;     // 文本/结构化对象/字节数组
  QByteArray payload;   // 去掉分帧后的接收体（仅发送为空）
  QByteArray sentWire;  // 实际写入的带分帧报文
  int sentBytes = 0;
  int byteLength = 0;
  int trailingBytes = 0;
  int discardedInputBytes = 0;
  int elapsedMs = 0;
  int baudrate = 115200;
  int dataBits = 8;
  QString parity = QStringLiteral("N");
  double stopbits = 1;
  QString flowControl = QStringLiteral("none");
};

/**
 * 执行一次串口报文通信（打开、可选清空、发送、按分帧接收、关闭）。
 * connection=simulator 使用进程内软件回环（等同 pySerial loop://），不访问真实端口；
 * connection=device 经 POSIX termios 打开 serialPort（可为 SerialPtyLoopback 从设备）。
 * 每次调用独立开关端口，不跨节点占用。无自动重试。
 */
SerialResult runSerialExchange(const QVariantMap& params);

/** 枚举本机可见串口（/dev/ttyUSB* / ttyACM* / ttyS* 等，含已启动的 PTY 回环从设备）。 */
QStringList listSerialPorts();

/**
 * 进程内 PTY 回环对端：从设备路径可供 connection=device 打开；
 * 主端线程把读到的字节立即写回，相当于串口环回插头，供无硬件冒烟。
 */
class SerialPtyLoopback {
 public:
  /** 若尚未运行则创建 PTY 并启动回显线程。 */
  bool start(QString* error);
  /** 停止回显线程并关闭主/从描述符。 */
  void stop();
  bool running() const;
  /** 供算子打开的从设备路径，例如 /dev/pts/N。未启动时为空。 */
  QString slavePath() const;

 private:
  void peerLoop();
  int masterFd_ = -1;
  int slaveFd_ = -1;
  QString slavePath_;
  bool running_ = false;
};

/** 全局 PTY 回环，供流程、通信面板和自测共用。 */
SerialPtyLoopback& serialPtyLoopback();

/** 无 QApplication 依赖的冒烟自检。空列表表示全部通过。 */
QStringList serialSelfTest();

}  // namespace sieans_qt
