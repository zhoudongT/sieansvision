#pragma once

#include <QJsonObject>
#include <QJsonArray>
#include <QString>
#include <QStringList>
#include <QVector>
#include <QPointF>
#include <QRect>
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
  QString when = QStringLiteral("always");  // always|true|false|success|error|path
};

/** One process in a scheme (方案⊃流程), aligned with desktop/scheme.py. */
struct FlowDef {
  QString id;
  QString name;
  QString outputNode;
  QVector<FlowStep> steps;
  QVector<FlowEdge> edges;
  QPointF sourcePosition{300, 40};
  QVariantMap sourceConfig;
  QVariantMap io;
  QVariantMap cardPosition;
  bool enabled = true;
  int runIntervalMs = 0;
  bool stopOnNg = false;
  int timeoutMs = 0;
  int runCount = 0;
  double lastElapsedMs = 0;
};

/** Reusable sub-graph stored in the project (子流程定义). */
struct SubflowDef {
  QString id;
  QString name;
  QString outputNode;
  QVector<FlowStep> steps;
  QVector<FlowEdge> edges;
  QVariantMap variables;
  QPointF sourcePosition{80, 80};
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

  const QVector<SubflowDef>& subflows() const { return subflows_; }
  QVector<SubflowDef>& subflowsMut() { return subflows_; }
  const SubflowDef* findSubflow(const QString& idOrName) const;
  SubflowDef* findSubflow(const QString& idOrName);
  /** True if any subflow/loop step (main or nested) references id. */
  bool subflowIsReferenced(const QString& id) const;

  static FlowStep stepFromJson(const QJsonObject& o);
  static QJsonObject stepToJson(const FlowStep& s);
  static FlowEdge edgeFromJson(const QJsonObject& o);
  static QJsonObject edgeToJson(const FlowEdge& e);
  static SubflowDef subflowFromJson(const QJsonObject& o);
  static QJsonObject subflowToJson(const SubflowDef& d);
  void loadFromSubflow(const SubflowDef& d);
  SubflowDef exportToSubflow(const QString& id, const QString& outputNode) const;

  /** PySide scheme: flows[] + activeFlowId. Legacy single-flow files migrate to 流程1. */
  const QVector<FlowDef>& flows() const { return flows_; }
  QString activeFlowId() const { return activeFlowId_; }
  const FlowDef* findFlow(const QString& id) const;
  FlowDef* findFlow(const QString& id);
  /** 若尚无 flows[]，把当前顶层图包装为「流程1」。 */
  void ensureScheme();
  /** 把当前顶层 steps/edges/source/io 写回活动流程条目。 */
  void syncActiveIntoFlows();
  /** 先保存当前图，再把 flowId 加载为顶层活动流程。失败返回 false。 */
  bool activateFlow(const QString& flowId);
  /** 追加一条空流程（不自动切换）。 */
  FlowDef addFlow(const QString& name = QString());
  /** 复制流程并重映射步骤 id。 */
  FlowDef duplicateFlow(const QString& flowId, QString* error = nullptr);
  /** 至少保留一条流程。若删的是活动流程则切到剩余第一条。 */
  bool removeFlow(const QString& flowId, QString* error = nullptr);
  bool renameFlow(const QString& flowId, const QString& name);
  /** 导出 PySide 兼容的 sieans.prc JSON 对象。 */
  QJsonObject exportPrc(const QString& flowId, QString* error = nullptr) const;
  bool exportPrcToFile(const QString& flowId, const QString& path, QString* error = nullptr) const;
  /** 导入 .prc（完整 sieans.prc 或带 steps 的裸流程）为新流程，步骤 id 会重映射。 */
  FlowDef importPrc(const QJsonObject& payload, QString* error = nullptr);
  FlowDef importPrcFromFile(const QString& path, QString* error = nullptr);
  static FlowDef flowFromJson(const QJsonObject& o);
  static QJsonObject flowToJson(const FlowDef& f);
  /** 多流程往返、.prc 导入导出、旧单流程文件兼容、子流程仍保留。空列表表示通过。 */
  static QStringList schemeSelfTest();

  QPointF sourcePosition() const { return sourcePosition_; }
  void setSourcePosition(const QPointF& p) { sourcePosition_ = p; }
  int runIntervalMs() const { return runIntervalMs_; }
  void setRunIntervalMs(int ms);

  QVariantMap variables() const { return variables_; }
  QVariantMap& variablesMut() { return variables_; }
  void setVariables(const QVariantMap& v) { variables_ = v; }

  QVariantMap commManager() const { return commManager_; }
  QVariantMap& commManagerMut() { return commManager_; }
  void setCommManager(const QVariantMap& c) { commManager_ = c; }

  QVariantMap flowIo() const { return flowIo_; }
  QVariantMap& flowIoMut() { return flowIo_; }
  void setFlowIo(const QVariantMap& io) { flowIo_ = io; }

  QStringList hostWatchKeys() const;
  void setHostWatchKeys(const QStringList& keys);
  /** hostWatch.pinGroups names in file order (also accepts pin_groups). */
  QStringList pinGroupNames() const;
  /** Cleaned watch keys for a named pin group. */
  QStringList pinGroupKeys(const QString& name) const;
  QString activePinGroup() const;
  /** Persist pin groups + activePinGroup into hostWatch (PySide-compatible). */
  void setPinGroups(const QVariantMap& groups, const QString& active = QString(),
                    bool writeWatchKeys = true);
  /** Upsert a named group; does not invent a default group on empty documents. */
  QString ensurePinGroup(const QString& name, const QStringList& keys);
  /** Switch the active group and write its keys to hostWatch.watchKeys. */
  QString activatePinGroup(const QString& name);
  /** Isolated persist/restore/activate pin-group checks. Empty list = pass. */
  static QStringList pinGroupSelfTest();

  /** PySide project["recipes"] snapshots (in-project 产线配方 / 换型 subset). */
  QJsonArray recipesJson() const;
  int recipeCount() const { return recipesJson().size(); }
  QString activeRecipeId() const;
  QString activeRecipeName() const;
  /** Snapshot current top-level step params as a named recipe; becomes active. */
  QVariantMap captureRecipe(const QString& name, const QString& note = QString(),
                            const QString& variant = QString());
  /** Apply snapshot params onto matching live steps (op+name, then id, then op). */
  QVariantMap applyRecipe(const QString& recipeId, QString* error = nullptr);
  bool deleteRecipe(const QString& recipeId);
  /** Isolated capture/apply/delete/save-load recipe checks. Empty list = pass. */
  static QStringList recipeSelfTest();

  /** PySide project["globalTriggers"] bag (events + strings). */
  QVariantMap globalTriggers() const;
  void setGlobalTriggers(const QVariantMap& bag);
  int stringTriggerCount() const;
  /** Append a string-trigger row (dialog schema) and return its pattern. */
  QString addStringTrigger(const QString& pattern, const QString& commandType,
                           bool partial = true, bool enabled = true);
  /** Commands whose string row matches received text (partial or equals). */
  QVector<QVariantMap> collectStringCommands(const QString& received) const;
  /** Isolated match / persist / load trigger checks. Empty list = pass. */
  static QStringList triggerSelfTest();
  QStringList filmstripPaths() const;
  void setFilmstripPaths(const QStringList& paths);
  bool filmstripAutoSwitch() const;
  void setFilmstripAutoSwitch(bool on);
  int filmstripIndex() const;
  void setFilmstripIndex(int index);
  QString hostMode() const;
  void setHostMode(const QString& mode);
  QString alarmPolicy() const;
  void setAlarmPolicy(const QString& policy);
  QStringList varWatchKeys() const;
  void setVarWatchKeys(const QStringList& keys);
  QStringList alarmHistory() const;
  void setAlarmHistory(const QStringList& lines);
  bool recipeLocked() const;
  void setRecipeLocked(bool on);
  bool alarmLatched() const;
  QString alarmLatchReason() const;
  void setAlarmLatched(bool on, const QString& reason = QString());
  QRect propertyFloatGeometry() const;
  void setPropertyFloatGeometry(const QRect& r);

  QString cameraDeviceId() const;
  QString cameraBackend() const;  // gentl | uvc | soft
  bool continuousLive() const;
  double acquisitionFps() const;
  double exposureUs() const;
  double gainDb() const;

  /** Seed a GenTL→QR open-and-run graph if no file loaded. */
  void seedGentlQrDemo();

 private:
  QString path_;
  QString name_ = QStringLiteral("未命名方案");
  QVariantMap sourceConfig_;
  QVector<FlowStep> steps_;
  QVector<FlowEdge> edges_;
  QVector<SubflowDef> subflows_;
  QVector<FlowDef> flows_;
  QString activeFlowId_;
  QString outputNode_;
  QPointF sourcePosition_{80, 160};
  int runIntervalMs_ = 0;
  QVariantMap variables_;
  QVariantMap commManager_;
  QVariantMap flowIo_;
  QJsonObject raw_;

  /** 把当前顶层图做成一条流程条目（新 id）。 */
  FlowDef captureActiveFlow(const QString& name) const;
  /** 用流程条目覆盖顶层 steps/edges/source/io。 */
  void applyFlowToTop(const FlowDef& f);
};

}  // namespace sieans_qt
