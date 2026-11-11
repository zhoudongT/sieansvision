#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>

namespace sieans_qt {

/** 一次 Modbus 读/写/等待的结果，字段对齐 catalog 与既有工业适配器。 */
struct ModbusResult {
  bool ok = false;
  QString error;
  QString note;
  QString protocol;  // modbus-simulator / modbus-tcp / modbus-rtu
  QString action;    // read / write / wait
  QString area;      // holding / input / coils / discrete
  int deviceId = 1;
  int address = 0;
  int count = 0;
  QString dataType;
  QVariantList values;
  QVariant value;
  QVariantList registers;
  bool acknowledged = false;
  bool triggered = false;
  bool passed = false;
  int samples = 0;
  int elapsedMs = 0;
  QString quality;
  QString reason;
  QVariant firstValue;
  QVariant expectedValue;
};

/**
 * 读取线圈 / 离散输入 / 保持 / 输入寄存器。
 * transport=simulator 使用进程内寄存器表；tcp 走真实 Modbus TCP；
 * rtu 走串口上的 Modbus RTU（可指向单独的 RTU PTY 从站）。
 * 每次调用新建并关闭连接（等待节点除外，等待期间保持一条连接）。
 */
ModbusResult runModbusRead(const QVariantMap& params);
/** 写入线圈或保持寄存器。设备应答不等于物理动作完成，失败不回滚。 */
ModbusResult runModbusWrite(const QVariantMap& params);
/** 轮询单个值直到条件满足或超时；边沿模式每次调用重新建立基线。 */
ModbusResult runModbusWait(const QVariantMap& params);

/**
 * 本机 Modbus TCP 软从站，与 simulator 共用寄存器表，供无 PLC 冒烟。
 * 默认监听 127.0.0.1:1502，被占用时由调用方 bump。
 */
class ModbusSoftServer {
 public:
  bool start(quint16 port, QString* error);
  void stop();
  bool running() const;
  quint16 port() const;
  QString endpoint() const;  // 127.0.0.1:port
};

ModbusSoftServer& modbusSoftServer();

/**
 * 可选 RTU 从站：第二路 PTY，主端按 Modbus RTU 应答，与 TCP/模拟器共用寄存器表。
 * 不占用 SerialLoopback 回显 PTY，避免干扰串口报文算子。
 */
class ModbusRtuPeer {
 public:
  bool start(QString* error);
  void stop();
  bool running() const;
  QString slavePath() const;
};

ModbusRtuPeer& modbusRtuPeer();

/** 无界面自检。空列表表示全部通过。 */
QStringList modbusSelfTest();

}  // namespace sieans_qt
