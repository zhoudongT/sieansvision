#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>

namespace sieans_qt {

/** 一次 S7 读/写结果，字段对齐 catalog s7_read / s7_write 与既有工业适配器。 */
struct S7Result {
  bool ok = false;
  QString error;
  QString note;
  QString protocol = QStringLiteral("s7");
  QString action;  // read / write
  QString area;    // db / mk / pe / pa
  int dbNumber = 0;
  int byteOffset = 0;
  int bitOffset = 0;
  int count = 0;
  QString dataType;
  QVariantList values;
  QVariant value;
  QVariantList rawBytes;
  bool acknowledged = false;
  int elapsedMs = 0;
  QString quality;
};

/**
 * 通过经典 S7 协议读取 DB / M / I / Q，或访问本机模拟存储。
 * connection=simulator 直接读写进程内映像；connection=plc 走 ISO-on-TCP（可指向软从站）。
 * 每次调用新建并关闭连接。数值采用西门子大端；BOOL 只访问单个位。
 */
S7Result runS7Read(const QVariantMap& params);
/** 向 DB、M 或 Q 写入。输入区 I 只读。设备应答不等于物理完成，失败不回滚。 */
S7Result runS7Write(const QVariantMap& params);

/**
 * 本机 S7 ISO-on-TCP 软从站，与 simulator 共用映像，供无 PLC 冒烟。
 * 默认监听 127.0.0.1:1102（102 需特权），被占用时由调用方 bump。
 */
class S7SoftServer {
 public:
  bool start(quint16 port, QString* error);
  void stop();
  bool running() const;
  quint16 port() const;
  QString endpoint() const;
};

S7SoftServer& s7SoftServer();

/** 无界面自检。空列表表示全部通过。 */
QStringList s7SelfTest();

}  // namespace sieans_qt
