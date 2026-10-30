#pragma once

#include <QJsonObject>
#include <QJsonArray>
#include <QString>
#include <QVector>
#include <QPointF>
#include <QVariantMap>

namespace sieans_qt {

struct FlowStep {
  QString id;
  QString name;
  QString operation;
  QPointF position;
  QString imageFrom;
  QVariantMap params;
  QString runState;  // 等待执行 / OK / NG / 运行中
};

struct FlowEdge {
  QString id;
  QString from;
  QString to;
  QString fromPort = QStringLiteral("bottom");
  QString toPort = QStringLiteral("top");
};

/** Minimal .sieans project model for GenTL→QR open-and-run parity. */
class SieansDocument {
 public:
  bool loadFromFile(const QString& path, QString* error = nullptr);
  bool saveToFile(const QString& path, QString* error = nullptr) const;

  QString path() const { return path_; }
  QString name() const { return name_; }
  void setName(const QString& n) { name_ = n; }

  QVariantMap sourceConfig() const { return sourceConfig_; }
  QVariantMap& sourceConfigMut() { return sourceConfig_; }

  const QVector<FlowStep>& steps() const { return steps_; }
  QVector<FlowStep>& stepsMut() { return steps_; }
  const QVector<FlowEdge>& edges() const { return edges_; }
  QVector<FlowEdge>& edgesMut() { return edges_; }

  FlowStep* findStep(const QString& id);
  const FlowStep* findStep(const QString& id) const;

  QPointF sourcePosition() const { return sourcePosition_; }
  void setSourcePosition(const QPointF& p) { sourcePosition_ = p; }
  int runIntervalMs() const { return runIntervalMs_; }

  QVariantMap variables() const { return variables_; }
  QVariantMap& variablesMut() { return variables_; }
  void setVariables(const QVariantMap& v) { variables_ = v; }

  QVariantMap commManager() const { return commManager_; }
  QVariantMap& commManagerMut() { return commManager_; }
  void setCommManager(const QVariantMap& c) { commManager_ = c; }

  QStringList hostWatchKeys() const;

  QString cameraDeviceId() const;
  bool continuousLive() const;
  double acquisitionFps() const;
  double exposureUs() const;

  /** Seed a GenTL→QR open-and-run graph if no file loaded. */
  void seedGentlQrDemo();

 private:
  QString path_;
  QString name_ = QStringLiteral("未命名方案");
  QVariantMap sourceConfig_;
  QVector<FlowStep> steps_;
  QVector<FlowEdge> edges_;
  QPointF sourcePosition_{80, 160};
  int runIntervalMs_ = 0;
  QVariantMap variables_;
  QVariantMap commManager_;
  QJsonObject raw_;
};

}  // namespace sieans_qt
