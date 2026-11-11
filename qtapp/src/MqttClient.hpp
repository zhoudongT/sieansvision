#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>

namespace sieans_qt {

/** 一次 MQTT 发布/接收结果，字段对齐 catalog mqtt_publish / mqtt_receive。 */
struct MqttResult {
  bool ok = false;
  QString error;
  QString note;
  QString protocol = QStringLiteral("MQTT 3.1.1");
  QString action;  // publish / receive
  QString topic;
  QString encoding;
  int qos = 0;
  QString clientId;
  bool simulated = false;
  bool retained = false;
  bool duplicate = false;
  bool acknowledged = false;
  QString delivery;
  QVariant value;
  int byteLength = 0;
  int elapsedMs = 0;
};

/**
 * 将文本、结构化数据或字节发布到 MQTT 主题。
 * connection=simulator 写入进程内映像（可保留）；connection=broker 走 MQTT 3.1.1（可指向软代理）。
 * 每次调用新建连接并在结束时断开。仅支持 security=plain。
 * QoS 0 表示已发送；QoS 1/2 表示代理协议应答，不代表下游已执行。发布不重试、不回滚。
 */
MqttResult runMqttPublish(const QVariantMap& params);
/**
 * 订阅主题，在时限内接收一条消息后结束。关闭保留消息后只接收新消息。
 * 支持 + 单层与 # 多层通配符。每次执行建立新连接，不自动重连。
 */
MqttResult runMqttReceive(const QVariantMap& params);

/**
 * 本机 MQTT 3.1.1 软代理，与 simulator 共用主题映像，供无外部 broker 冒烟。
 * 默认监听 127.0.0.1:1883，被占用时由调用方 bump。
 */
class MqttSoftBroker {
 public:
  bool start(quint16 port, QString* error);
  void stop();
  bool running() const;
  quint16 port() const;
  QString endpoint() const;
};

MqttSoftBroker& mqttSoftBroker();

/** 无界面自检。空列表表示全部通过。 */
QStringList mqttSelfTest();

}  // namespace sieans_qt
