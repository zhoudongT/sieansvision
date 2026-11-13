#include "SieansDocument.hpp"
#include "WorkbenchPaths.hpp"
#include "SubflowExec.hpp"

#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QUuid>
#include <QHash>
#include <QRect>
#include <QTemporaryDir>
#include <QDir>
#include <QFileInfo>
#include <QDateTime>
#include <QMetaType>

namespace sieans_qt {
namespace {

QVariantMap objectToMap(const QJsonObject& o) {
  QVariantMap m;
  for (auto it = o.begin(); it != o.end(); ++it) {
    m.insert(it.key(), it.value().toVariant());
  }
  return m;
}

QJsonObject mapToObject(const QVariantMap& m) {
  return QJsonObject::fromVariantMap(m);
}

QString cleanPinGroupName(const QString& name) {
  const QString t = name.trimmed();
  return t.isEmpty() ? QStringLiteral("未命名") : t;
}

QStringList cleanPinGroupKeyList(const QJsonArray& arr) {
  QStringList out;
  for (const QJsonValue& v : arr) {
    const QString k = v.toString().trimmed();
    if (!k.isEmpty() && !out.contains(k)) out << k;
  }
  return out;
}

QStringList cleanPinGroupKeyVariant(const QVariant& v) {
  QStringList raw = v.toStringList();
  if (raw.isEmpty()) {
    for (const QVariant& x : v.toList()) raw << x.toString();
  }
  QStringList out;
  for (const QString& k : raw) {
    const QString t = k.trimmed();
    if (!t.isEmpty() && !out.contains(t)) out << t;
  }
  return out;
}

QJsonObject hostWatchObject(const QJsonObject& raw) {
  return raw.value(QStringLiteral("hostWatch")).toObject();
}

QJsonObject pinGroupsJson(const QJsonObject& hw) {
  QJsonObject g = hw.value(QStringLiteral("pinGroups")).toObject();
  if (g.isEmpty()) g = hw.value(QStringLiteral("pin_groups")).toObject();
  return g;
}

}  // namespace

bool SieansDocument::loadFromFile(const QString& path, QString* error) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly)) {
    if (error) *error = QStringLiteral("无法打开: %1").arg(path);
    return false;
  }
  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &pe);
  if (pe.error != QJsonParseError::NoError || !doc.isObject()) {
    if (error) *error = QStringLiteral("JSON 解析失败: %1").arg(pe.errorString());
    return false;
  }
  raw_ = doc.object();
  path_ = path;
  name_ = raw_.value(QStringLiteral("name")).toString(QStringLiteral("未命名方案"));
  runIntervalMs_ = raw_.value(QStringLiteral("runIntervalMs")).toInt(0);
  sourceConfig_ = objectToMap(raw_.value(QStringLiteral("sourceConfig")).toObject());
  const QJsonObject sp = raw_.value(QStringLiteral("sourcePosition")).toObject();
  sourcePosition_ = QPointF(sp.value(QStringLiteral("x")).toDouble(80),
                            sp.value(QStringLiteral("y")).toDouble(160));

  steps_.clear();
  const QJsonArray stepsArr = raw_.value(QStringLiteral("steps")).toArray();
  for (const QJsonValue& v : stepsArr) {
    const QJsonObject o = v.toObject();
    FlowStep s;
    s.id = o.value(QStringLiteral("id")).toString();
    s.name = o.value(QStringLiteral("name")).toString();
    s.operation = o.value(QStringLiteral("operation")).toString();
    s.imageFrom = o.value(QStringLiteral("imageFrom")).toString();
    s.params = objectToMap(o.value(QStringLiteral("params")).toObject());
    const QJsonObject pos = o.value(QStringLiteral("position")).toObject();
    s.position = QPointF(pos.value(QStringLiteral("x")).toDouble(),
                         pos.value(QStringLiteral("y")).toDouble());
    s.runState = QStringLiteral("等待执行");
    if (s.id.isEmpty()) continue;
    steps_.push_back(s);
  }

  variables_ = objectToMap(raw_.value(QStringLiteral("variables")).toObject());
  commManager_ = objectToMap(raw_.value(QStringLiteral("commManager")).toObject());
  flowIo_ = objectToMap(raw_.value(QStringLiteral("io")).toObject());

  edges_.clear();
  const QJsonArray edgesArr = raw_.value(QStringLiteral("edges")).toArray();
  for (const QJsonValue& v : edgesArr) {
    const QJsonObject o = v.toObject();
    FlowEdge e;
    e.id = o.value(QStringLiteral("id")).toString();
    e.from = o.value(QStringLiteral("from")).toString();
    e.to = o.value(QStringLiteral("to")).toString();
    e.fromPort = o.value(QStringLiteral("fromPort")).toString(QStringLiteral("bottom"));
    e.toPort = o.value(QStringLiteral("toPort")).toString(QStringLiteral("top"));
    e.when = o.value(QStringLiteral("when")).toString(QStringLiteral("always"));
    if (e.when.isEmpty()) e.when = QStringLiteral("always");
    if (e.id.isEmpty())
      e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    if (!e.from.isEmpty() && !e.to.isEmpty()) edges_.push_back(e);
  }

  subflows_.clear();
  const QJsonArray sfArr = raw_.value(QStringLiteral("subflows")).toArray();
  for (const QJsonValue& v : sfArr) {
    SubflowDef d = subflowFromJson(v.toObject());
    if (!d.id.isEmpty()) subflows_.push_back(d);
  }
  outputNode_ = raw_.value(QStringLiteral("outputNode")).toString();
  flows_.clear();
  activeFlowId_.clear();
  const QJsonArray flArr = raw_.value(QStringLiteral("flows")).toArray();
  for (const QJsonValue& v : flArr) {
    FlowDef f = flowFromJson(v.toObject());
    if (!f.id.isEmpty()) flows_.push_back(f);
  }
  activeFlowId_ = raw_.value(QStringLiteral("activeFlowId")).toString();
  ensureScheme();
  if (steps_.isEmpty()) {
    if (const FlowDef* cur = findFlow(activeFlowId_)) {
      steps_ = cur->steps;
      edges_ = cur->edges;
      sourcePosition_ = cur->sourcePosition;
      sourceConfig_ = cur->sourceConfig;
      outputNode_ = cur->outputNode;
      if (!cur->io.isEmpty()) flowIo_ = cur->io;
      if (cur->runIntervalMs > 0) runIntervalMs_ = cur->runIntervalMs;
    }
  }
  resetCanvasUndo();
  return true;
}

bool SieansDocument::saveToFile(const QString& path, QString* error) const {
  QJsonObject root = raw_;
  if (root.isEmpty()) root = QJsonObject{{QStringLiteral("version"), 2}};
  root.insert(QStringLiteral("name"), name_);
  root.insert(QStringLiteral("runIntervalMs"), runIntervalMs_);
  root.insert(QStringLiteral("sourceConfig"), mapToObject(sourceConfig_));
  root.insert(QStringLiteral("sourcePosition"),
              QJsonObject{{QStringLiteral("x"), sourcePosition_.x()},
                          {QStringLiteral("y"), sourcePosition_.y()}});

  QJsonArray stepsArr;
  for (const FlowStep& s : steps_) {
    QJsonObject o;
    o.insert(QStringLiteral("id"), s.id);
    o.insert(QStringLiteral("name"), s.name);
    o.insert(QStringLiteral("operation"), s.operation);
    o.insert(QStringLiteral("imageFrom"), s.imageFrom);
    o.insert(QStringLiteral("params"), mapToObject(s.params));
    o.insert(QStringLiteral("position"),
             QJsonObject{{QStringLiteral("x"), s.position.x()},
                         {QStringLiteral("y"), s.position.y()}});
    stepsArr.append(o);
  }
  root.insert(QStringLiteral("steps"), stepsArr);

  QJsonArray edgesArr;
  for (const FlowEdge& e : edges_) {
    edgesArr.append(QJsonObject{
        {QStringLiteral("id"), e.id},
        {QStringLiteral("from"), e.from},
        {QStringLiteral("to"), e.to},
        {QStringLiteral("fromPort"), e.fromPort},
        {QStringLiteral("toPort"), e.toPort},
        {QStringLiteral("when"), e.when.isEmpty() ? QStringLiteral("always") : e.when},
    });
  }
  root.insert(QStringLiteral("edges"), edgesArr);
  QJsonArray sfArr;
  for (const SubflowDef& d : subflows_) sfArr.append(subflowToJson(d));
  if (!sfArr.isEmpty() || raw_.contains(QStringLiteral("subflows")))
    root.insert(QStringLiteral("subflows"), sfArr);
  root.insert(QStringLiteral("variables"), mapToObject(variables_));
  if (!commManager_.isEmpty())
    root.insert(QStringLiteral("commManager"), mapToObject(commManager_));
  if (!flowIo_.isEmpty())
    root.insert(QStringLiteral("io"), mapToObject(flowIo_));
  if (!outputNode_.isEmpty())
    root.insert(QStringLiteral("outputNode"), outputNode_);

  // Keep top-level graph as the active flow (PySide scheme_for_disk).
  QVector<FlowDef> snap = flows_;
  if (snap.isEmpty()) {
    FlowDef one;
    one.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    one.name = QStringLiteral("流程1");
    one.steps = steps_;
    one.edges = edges_;
    one.sourcePosition = sourcePosition_;
    one.sourceConfig = sourceConfig_;
    one.outputNode = outputNode_;
    one.io = flowIo_;
    one.runIntervalMs = runIntervalMs_;
    snap.push_back(one);
    root.insert(QStringLiteral("activeFlowId"), one.id);
  } else {
    bool hit = false;
    for (FlowDef& f : snap) {
      if (f.id != activeFlowId_) continue;
      f.steps = steps_;
      f.edges = edges_;
      f.sourcePosition = sourcePosition_;
      f.sourceConfig = sourceConfig_;
      f.outputNode = outputNode_;
      f.io = flowIo_;
      f.runIntervalMs = runIntervalMs_;
      hit = true;
      break;
    }
    if (!hit) {
      FlowDef one;
      one.id = activeFlowId_.isEmpty()
                   ? QUuid::createUuid().toString(QUuid::WithoutBraces)
                   : activeFlowId_;
      one.name = QStringLiteral("流程1");
      one.steps = steps_;
      one.edges = edges_;
      one.sourcePosition = sourcePosition_;
      one.sourceConfig = sourceConfig_;
      one.outputNode = outputNode_;
      one.io = flowIo_;
      one.runIntervalMs = runIntervalMs_;
      snap.push_back(one);
      root.insert(QStringLiteral("activeFlowId"), one.id);
    } else {
      root.insert(QStringLiteral("activeFlowId"), activeFlowId_);
    }
  }
  QJsonArray flArr;
  for (const FlowDef& f : snap) flArr.append(flowToJson(f));
  root.insert(QStringLiteral("flows"), flArr);
  if (raw_.contains(QStringLiteral("flowEdges")))
    root.insert(QStringLiteral("flowEdges"), raw_.value(QStringLiteral("flowEdges")));

  QFile f(path);
  if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
    if (error) *error = QStringLiteral("无法写入: %1").arg(path);
    return false;
  }
  f.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
  return true;
}

FlowStep* SieansDocument::findStep(const QString& id) {
  for (FlowStep& s : steps_) {
    if (s.id == id) return &s;
  }
  return nullptr;
}

const FlowStep* SieansDocument::findStep(const QString& id) const {
  for (const FlowStep& s : steps_) {
    if (s.id == id) return &s;
  }
  return nullptr;
}


QString SieansDocument::cameraBackend() const {
  const QVariantMap cam = sourceConfig_.value(QStringLiteral("cameraParams")).toMap();
  QString b = cam.value(QStringLiteral("backendKind")).toString();
  if (b.isEmpty()) b = cam.value(QStringLiteral("driver")).toString();
  if (b.isEmpty()) b = sourceConfig_.value(QStringLiteral("backendKind")).toString();
  if (b.isEmpty()) {
    for (const FlowStep& s : steps_) {
      if (s.operation == QLatin1String("camera_capture")) {
        b = s.params.value(QStringLiteral("backendKind")).toString();
        if (b.isEmpty()) b = s.params.value(QStringLiteral("driver")).toString();
        if (!b.isEmpty()) break;
      }
    }
  }
  b = b.toLower();
  if (b == QLatin1String("usb")) b = QStringLiteral("uvc");
  if (b == QLatin1String("sim") || b == QLatin1String("synthetic"))
    b = QStringLiteral("soft");
  if (b.isEmpty()) b = QStringLiteral("gentl");
  return b;
}

QString SieansDocument::cameraDeviceId() const {
  const QVariantMap cam = sourceConfig_.value(QStringLiteral("cameraParams")).toMap();
  QString id = cam.value(QStringLiteral("deviceId")).toString();
  if (id.isEmpty()) id = sourceConfig_.value(QStringLiteral("cameraId")).toString();
  if (id.isEmpty()) {
    for (const FlowStep& s : steps_) {
      if (s.operation == QLatin1String("camera_capture")) {
        id = s.params.value(QStringLiteral("deviceId")).toString();
        if (!id.isEmpty()) break;
      }
    }
  }
  return id;
}

bool SieansDocument::continuousLive() const {
  const QVariantMap cam = sourceConfig_.value(QStringLiteral("cameraParams")).toMap();
  return cam.value(QStringLiteral("continuousLive"), true).toBool();
}

double SieansDocument::acquisitionFps() const {
  const QVariantMap cam = sourceConfig_.value(QStringLiteral("cameraParams")).toMap();
  return cam.value(QStringLiteral("acquisitionFrameRate"), 15).toDouble();
}

double SieansDocument::exposureUs() const {
  const QVariantMap cam = sourceConfig_.value(QStringLiteral("cameraParams")).toMap();
  if (cam.contains(QStringLiteral("exposureTime")))
    return cam.value(QStringLiteral("exposureTime")).toDouble();
  return sourceConfig_.value(QStringLiteral("exposure"), 2000).toDouble();
}

double SieansDocument::gainDb() const {
  const QVariantMap cam = sourceConfig_.value(QStringLiteral("cameraParams")).toMap();
  if (cam.contains(QStringLiteral("gainDb")))
    return cam.value(QStringLiteral("gainDb")).toDouble();
  return sourceConfig_.value(QStringLiteral("gainDb"), 0).toDouble();
}

void SieansDocument::seedGentlQrDemo() {
  name_ = QStringLiteral("打开即跑 · GenTL/Soft→二维码→TCP");
  path_.clear();
  sourcePosition_ = QPointF(80, 160);
  // Prefer GenTL when present; GenTLWorker soft-fallback keeps open-and-run alive.
  sourceConfig_ = {
      {QStringLiteral("mode"), QStringLiteral("camera")},
      {QStringLiteral("cameraParams"),
       QVariantMap{
           {QStringLiteral("imageSource"), QStringLiteral("camera")},
           {QStringLiteral("driver"), QStringLiteral("gentl")},
           {QStringLiteral("backendKind"), QStringLiteral("gentl")},
           {QStringLiteral("continuousLive"), true},
           {QStringLiteral("sessionPersist"), true},
           {QStringLiteral("trigger"), QStringLiteral("freerun")},
           {QStringLiteral("exposureTime"), 10000},
           {QStringLiteral("gainDb"), 0},
           {QStringLiteral("acquisitionFrameRate"), 15},
       }},
  };
  steps_.clear();
  edges_.clear();

  auto add = [&](const QString& id, const QString& name, const QString& op, qreal x,
                 qreal y, const QString& from, const QVariantMap& params) {
    FlowStep s;
    s.id = id;
    s.name = name;
    s.operation = op;
    s.position = QPointF(x, y);
    s.imageFrom = from;
    s.runState = QStringLiteral("等待执行");
    s.params = params;
    steps_.push_back(s);
  };
  add(QStringLiteral("cam1"), QStringLiteral("MV GenTL 采集"),
      QStringLiteral("camera_capture"), 300, 140, QStringLiteral("source"),
      {{QStringLiteral("backendKind"), QStringLiteral("gentl")},
       {QStringLiteral("driver"), QStringLiteral("gentl")},
       {QStringLiteral("continuousLive"), true}});
  add(QStringLiteral("qr1"), QStringLiteral("二维码/条码识别"),
      QStringLiteral("barcode"), 300, 260, QStringLiteral("cam1"),
      {{QStringLiteral("types"), QStringLiteral("QRCode")},
       {QStringLiteral("maxCodes"), 16},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMinCount"), 1}});
  add(QStringLiteral("ocr1"), QStringLiteral("OCR 文字识别"),
      QStringLiteral("ocr"), 460, 260, QStringLiteral("cam1"),
      {{QStringLiteral("lang"), QStringLiteral("eng")},
       {QStringLiteral("psm"), 6},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMinCount"), 1},
       {QStringLiteral("minConfidence"), 0}});
  add(QStringLiteral("cal1"), QStringLiteral("卡尺测量"),
      QStringLiteral("caliper"), 620, 260, QStringLiteral("cam1"),
      {{QStringLiteral("direction"), QStringLiteral("horizontal")},
       {QStringLiteral("target"), QStringLiteral("soft_bars")},
       {QStringLiteral("threshold"), 18},
       {QStringLiteral("polarity"), QStringLiteral("any")},
       {QStringLiteral("pxPerMm"), 10},
       {QStringLiteral("bandHalf"), 6},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMinPx"), 150},
       {QStringLiteral("judgeMaxPx"), 250},
       {QStringLiteral("showOverlay"), true}});
  add(QStringLiteral("defOk"), QStringLiteral("参考图缺陷 · 清洁"),
      QStringLiteral("defects"), 780, 260, QStringLiteral("cam1"),
      {{QStringLiteral("referenceSource"), QStringLiteral("soft_scene")},
       {QStringLiteral("differenceThreshold"), 30},
       {QStringLiteral("minArea"), 20},
       {QStringLiteral("maxCount"), 200},
       {QStringLiteral("blur"), 3},
       {QStringLiteral("ignoreBottomPx"), 36},
       {QStringLiteral("scaleReference"), true},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMaxCount"), 0},
       {QStringLiteral("judgeMaxRatio"), 0.05},
       {QStringLiteral("resultVar"), QStringLiteral("defectsClean")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("defNg"), QStringLiteral("参考图缺陷 · 斑块"),
      QStringLiteral("defects"), 940, 260, QStringLiteral("cam1"),
      {{QStringLiteral("referenceSource"), QStringLiteral("soft_scene_blemish")},
       {QStringLiteral("differenceThreshold"), 30},
       {QStringLiteral("minArea"), 20},
       {QStringLiteral("maxCount"), 200},
       {QStringLiteral("blur"), 3},
       {QStringLiteral("ignoreBottomPx"), 36},
       {QStringLiteral("scaleReference"), true},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMaxCount"), 0},
       {QStringLiteral("judgeMaxRatio"), 0.05},
       {QStringLiteral("resultVar"), QStringLiteral("defects")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("loc1"), QStringLiteral("模板与定位"),
      QStringLiteral("locate"), 780, 400, QStringLiteral("cam1"),
      {{QStringLiteral("templateSource"), QStringLiteral("soft_plate")},
       {QStringLiteral("minScore"), 0.55},
       {QStringLiteral("maxMatches"), 1},
       {QStringLiteral("overlapThreshold"), 0.3},
       {QStringLiteral("angleEnable"), true},
       {QStringLiteral("angleStart"), 0},
       {QStringLiteral("angleEnd"), 0},
       {QStringLiteral("angleStep"), 10},
       {QStringLiteral("writePassGate"), false}});
  add(QStringLiteral("pose1"), QStringLiteral("位置修正"),
      QStringLiteral("pose_correct"), 780, 520, QStringLiteral("loc1"),
      {{QStringLiteral("fixtureSource"), QStringLiteral("auto")},
       {QStringLiteral("bindStepId"), QStringLiteral("loc1")},
       {QStringLiteral("autoBindLocate"), true},
       {QStringLiteral("followRoi"), true},
       {QStringLiteral("resultVar"), QStringLiteral("fixture")},
       {QStringLiteral("axisLength"), 48},
       {QStringLiteral("showAxes"), true},
       {QStringLiteral("writeFlowVars"), true}});
  add(QStringLiteral("defFollow"), QStringLiteral("缺陷检测 · 跟随ROI"),
      QStringLiteral("defects"), 780, 640, QStringLiteral("pose1"),
      {{QStringLiteral("referenceSource"), QStringLiteral("soft_scene")},
       {QStringLiteral("differenceThreshold"), 30},
       {QStringLiteral("minArea"), 20},
       {QStringLiteral("maxCount"), 200},
       {QStringLiteral("blur"), 3},
       {QStringLiteral("ignoreBottomPx"), 0},
       {QStringLiteral("scaleReference"), true},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMaxCount"), 0},
       {QStringLiteral("judgeMaxRatio"), 0.05},
       {QStringLiteral("resultVar"), QStringLiteral("defectsFollow")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true},
       {QStringLiteral("followFixture"), true},
       {QStringLiteral("fixtureVar"), QStringLiteral("fixture")},
       {QStringLiteral("roiX"), -40},
       {QStringLiteral("roiY"), -18},
       {QStringLiteral("roiW"), 80},
       {QStringLiteral("roiH"), 36}});
  add(QStringLiteral("geomCirc"), QStringLiteral("几何 · 圆"),
      QStringLiteral("geometry"), 940, 400, QStringLiteral("cam1"),
      {{QStringLiteral("feature"), QStringLiteral("circles")},
       {QStringLiteral("target"), QStringLiteral("soft_circle")},
       {QStringLiteral("minRadius"), 22},
       {QStringLiteral("maxRadius"), 50},
       {QStringLiteral("minDistance"), 20},
       {QStringLiteral("votes"), 16},
       {QStringLiteral("maxCount"), 3},
       {QStringLiteral("filterSize"), 1},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 20},
       {QStringLiteral("judgeMax"), 50},
       {QStringLiteral("resultVar"), QStringLiteral("geomCirc")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("geomLine"), QStringLiteral("几何 · 直线"),
      QStringLiteral("geometry"), 940, 520, QStringLiteral("cam1"),
      {{QStringLiteral("feature"), QStringLiteral("lines")},
       {QStringLiteral("target"), QStringLiteral("soft_line")},
       {QStringLiteral("minLength"), 80},
       {QStringLiteral("votes"), 20},
       {QStringLiteral("maxGap"), 12},
       {QStringLiteral("maxCount"), 3},
       {QStringLiteral("filterSize"), 1},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 100},
       {QStringLiteral("judgeMax"), 220},
       {QStringLiteral("resultVar"), QStringLiteral("geomLine")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("geomFollow"), QStringLiteral("几何 · 跟随圆"),
      QStringLiteral("geometry"), 940, 640, QStringLiteral("pose1"),
      {{QStringLiteral("feature"), QStringLiteral("circles")},
       {QStringLiteral("target"), QStringLiteral("soft_follow")},
       {QStringLiteral("followFixture"), true},
       {QStringLiteral("fixtureVar"), QStringLiteral("fixture")},
       {QStringLiteral("roiX"), -40},
       {QStringLiteral("roiY"), 20},
       {QStringLiteral("roiW"), 80},
       {QStringLiteral("roiH"), 70},
       {QStringLiteral("minRadius"), 10},
       {QStringLiteral("maxRadius"), 36},
       {QStringLiteral("minDistance"), 16},
       {QStringLiteral("votes"), 12},
       {QStringLiteral("maxCount"), 3},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 10},
       {QStringLiteral("judgeMax"), 36},
       {QStringLiteral("resultVar"), QStringLiteral("geomFollow")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("measCirc"), QStringLiteral("测量 · 圆直径"),
      QStringLiteral("measure"), 1100, 400, QStringLiteral("cam1"),
      {{QStringLiteral("feature"), QStringLiteral("circles")},
       {QStringLiteral("target"), QStringLiteral("soft_circle")},
       {QStringLiteral("minRadius"), 22},
       {QStringLiteral("maxRadius"), 50},
       {QStringLiteral("votes"), 16},
       {QStringLiteral("pxPerMm"), 10},
       {QStringLiteral("unit"), QStringLiteral("mm")},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 60},
       {QStringLiteral("judgeMax"), 85},
       {QStringLiteral("resultVar"), QStringLiteral("measCirc")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("measLine"), QStringLiteral("测量 · 直线长度"),
      QStringLiteral("measure"), 1100, 520, QStringLiteral("cam1"),
      {{QStringLiteral("feature"), QStringLiteral("lines")},
       {QStringLiteral("target"), QStringLiteral("soft_line")},
       {QStringLiteral("minLength"), 80},
       {QStringLiteral("votes"), 20},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 100},
       {QStringLiteral("judgeMax"), 220},
       {QStringLiteral("resultVar"), QStringLiteral("measLine")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("measAngle"), QStringLiteral("测量 · 夹角"),
      QStringLiteral("measure"), 1100, 640, QStringLiteral("cam1"),
      {{QStringLiteral("feature"), QStringLiteral("angle")},
       {QStringLiteral("target"), QStringLiteral("soft_angle")},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 80},
       {QStringLiteral("judgeMax"), 100},
       {QStringLiteral("resultVar"), QStringLiteral("measAng")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("measPts"), QStringLiteral("测量 · 两点距"),
      QStringLiteral("measure"), 1100, 760, QStringLiteral("cam1"),
      {{QStringLiteral("feature"), QStringLiteral("points")},
       {QStringLiteral("target"), QStringLiteral("soft_points")},
       {QStringLiteral("pxPerMm"), 10},
       {QStringLiteral("unit"), QStringLiteral("mm")},
       {QStringLiteral("judgeEnable"), true},
       {QStringLiteral("judgeMin"), 120},
       {QStringLiteral("judgeMax"), 180},
       {QStringLiteral("resultVar"), QStringLiteral("measPts")},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true}});
  add(QStringLiteral("var1"), QStringLiteral("变量计算 · OK/NG"),
      QStringLiteral("var_calc"), 300, 380, QStringLiteral("qr1"),
      {{QStringLiteral("scope"), QStringLiteral("flow")},
       {QStringLiteral("expressions"),
        QVariantList{
            QVariantMap{{QStringLiteral("name"), QStringLiteral("passGate")},
                        {QStringLiteral("expr"), QStringLiteral("barcodeCount >= 1")},
                        {QStringLiteral("enabled"), true}},
            QVariantMap{{QStringLiteral("name"), QStringLiteral("barcodeOk")},
                        {QStringLiteral("expr"), QStringLiteral("barcodeCount >= 1")},
                        {QStringLiteral("enabled"), true}},
            QVariantMap{{QStringLiteral("name"), QStringLiteral("urlOk")},
                        {QStringLiteral("expr"),
                         QStringLiteral("startswith(barcodeText, \"http\")")},
                        {QStringLiteral("enabled"), true}},
        }}});
  add(QStringLiteral("gate1"), QStringLiteral("结果门限 OK/NG"),
      QStringLiteral("result_gate"), 300, 500, QStringLiteral("var1"),
      {{QStringLiteral("sourceVar"), QStringLiteral("barcodeCount")},
       {QStringLiteral("minCount"), 1},
       {QStringLiteral("passVar"), QStringLiteral("passGate")}});
  add(QStringLiteral("fmt1"), QStringLiteral("格式化报文"),
      QStringLiteral("format_data"), 300, 620, QStringLiteral("gate1"),
      {{QStringLiteral("template"),
        QStringLiteral("BARCODE ok={passGate} count={barcodeCount} text={barcodeText}")},
       {QStringLiteral("args"), QStringLiteral("passGate,barcodeCount,barcodeText")},
       {QStringLiteral("targetVar"), QStringLiteral("formatted")},
       {QStringLiteral("emptyDefault"),
        QStringLiteral("BARCODE empty")}});
  add(QStringLiteral("tx1"), QStringLiteral("发送数据 · LocalLoop/TCP"),
      QStringLiteral("send_data"), 300, 740, QStringLiteral("fmt1"),
      {{QStringLiteral("device"), QStringLiteral("LocalLoop")},
       {QStringLiteral("message"),
        QStringLiteral(
            "BARCODE ok=${flow.passGate} count=${flow.barcodeCount} "
            "text=${flow.barcodeText}")}});
  add(QStringLiteral("rx1"), QStringLiteral("接收回环"),
      QStringLiteral("receive_data"), 300, 860, QStringLiteral("tx1"),
      {{QStringLiteral("device"), QStringLiteral("LocalLoop")},
       {QStringLiteral("targetVar"), QStringLiteral("lastRecv")},
       {QStringLiteral("timeoutMs"), 200}});
  add(QStringLiteral("cond1"), QStringLiteral("条件判断"),
      QStringLiteral("condition"), 520, 500, QStringLiteral("gate1"),
      {{QStringLiteral("logic"), QStringLiteral("and")},
       {QStringLiteral("comparison"), QStringLiteral("gte")},
       {QStringLiteral("left"), QStringLiteral("barcodeCount")},
       {QStringLiteral("right"), 1},
       {QStringLiteral("writePassGate"), false},
       {QStringLiteral("rules"),
        QVariantList{QVariantMap{{QStringLiteral("left"), QStringLiteral("barcodeCount")},
                                 {QStringLiteral("comparison"), QStringLiteral("gte")},
                                 {QStringLiteral("right"), 1},
                                 {QStringLiteral("enabled"), true}}}}});
  add(QStringLiteral("taken1"), QStringLiteral("成立分支"),
      QStringLiteral("format_data"), 460, 640, QStringLiteral("cond1"),
      {{QStringLiteral("template"), QStringLiteral("ROUTE=OK")},
       {QStringLiteral("args"), QString()},
       {QStringLiteral("targetVar"), QStringLiteral("branchRoute")}});
  add(QStringLiteral("skipped1"), QStringLiteral("不成立分支"),
      QStringLiteral("format_data"), 680, 640, QStringLiteral("cond1"),
      {{QStringLiteral("template"), QStringLiteral("ROUTE=NG")},
       {QStringLiteral("args"), QString()},
       {QStringLiteral("targetVar"), QStringLiteral("branchRoute")}});
  add(QStringLiteral("merge1"), QStringLiteral("分支汇合"),
      QStringLiteral("branch_merge"), 560, 760, QStringLiteral("taken1"),
      {});
  add(QStringLiteral("sf1"), QStringLiteral("子流程调用"),
      QStringLiteral("subflow"), 560, 880, QStringLiteral("merge1"),
      {{QStringLiteral("subflowId"), QStringLiteral("counter")},
       {QStringLiteral("stateMode"), QStringLiteral("reset")},
       {QStringLiteral("arguments"), QVariantMap{}}});
  add(QStringLiteral("loop1"), QStringLiteral("循环子流程"),
      QStringLiteral("loop"), 560, 1000, QStringLiteral("sf1"),
      {{QStringLiteral("subflowId"), QStringLiteral("counter")},
       {QStringLiteral("stateMode"), QStringLiteral("reset")},
       {QStringLiteral("mode"), QStringLiteral("until")},
       {QStringLiteral("iterations"), 10},
       {QStringLiteral("frameMode"), QStringLiteral("previous")},
       {QStringLiteral("stopField"), QStringLiteral("passed")},
       {QStringLiteral("stopValue"), true},
       {QStringLiteral("arguments"), QVariantMap{}}});
  add(QStringLiteral("ser1"), QStringLiteral("串口报文 · 回环模拟"),
      QStringLiteral("serial_exchange"), 80, 860, QStringLiteral("rx1"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("mode"), QStringLiteral("exchange")},
       {QStringLiteral("value"), QStringLiteral("SIEANS-SERIAL-00042")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("responseEncoding"), QStringLiteral("text")},
       {QStringLiteral("txFraming"), QStringLiteral("crlf")},
       {QStringLiteral("rxFraming"), QStringLiteral("crlf")},
       {QStringLiteral("timeoutMs"), 2000},
       {QStringLiteral("resultVar"), QStringLiteral("serial")}});
  add(QStringLiteral("serPty"), QStringLiteral("串口报文 · PTY 回环"),
      QStringLiteral("serial_exchange"), 80, 980, QStringLiteral("ser1"),
      {{QStringLiteral("connection"), QStringLiteral("device")},
       {QStringLiteral("mode"), QStringLiteral("exchange")},
       {QStringLiteral("serialPort"), QStringLiteral("SerialLoopback")},
       {QStringLiteral("value"), QStringLiteral("PTY-LOOP-OK")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("responseEncoding"), QStringLiteral("text")},
       {QStringLiteral("txFraming"), QStringLiteral("crlf")},
       {QStringLiteral("rxFraming"), QStringLiteral("crlf")},
       {QStringLiteral("baudrate"), 115200},
       {QStringLiteral("dataBits"), 8},
       {QStringLiteral("parity"), QStringLiteral("N")},
       {QStringLiteral("stopbits"), 1},
       {QStringLiteral("timeoutMs"), 2000},
       {QStringLiteral("resultVar"), QStringLiteral("serialPty")}});
  add(QStringLiteral("mbW"), QStringLiteral("Modbus 写入 · 模拟器"),
      QStringLiteral("modbus_write"), 80, 1100, QStringLiteral("serPty"),
      {{QStringLiteral("transport"), QStringLiteral("simulator")},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 10},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("value"), 4242},
       {QStringLiteral("timeoutMs"), 1500},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbWrite")}});
  add(QStringLiteral("mbR"), QStringLiteral("Modbus 读取 · 模拟器"),
      QStringLiteral("modbus_read"), 80, 1220, QStringLiteral("mbW"),
      {{QStringLiteral("transport"), QStringLiteral("simulator")},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 10},
       {QStringLiteral("count"), 1},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("timeoutMs"), 1500},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbRead")}});
  add(QStringLiteral("mbWait"), QStringLiteral("等待 PLC 信号 · 模拟器"),
      QStringLiteral("modbus_wait"), 80, 1340, QStringLiteral("mbR"),
      {{QStringLiteral("transport"), QStringLiteral("simulator")},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 10},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("comparison"), QStringLiteral("eq")},
       {QStringLiteral("expectedValue"), 4242},
       {QStringLiteral("triggerMode"), QStringLiteral("level")},
       {QStringLiteral("pollIntervalMs"), 50},
       {QStringLiteral("waitTimeoutMs"), 2000},
       {QStringLiteral("onTimeout"), QStringLiteral("error")},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbWait")}});
  add(QStringLiteral("mbTcpW"), QStringLiteral("Modbus 写入 · TCP 回环"),
      QStringLiteral("modbus_write"), 80, 1460, QStringLiteral("mbWait"),
      {{QStringLiteral("transport"), QStringLiteral("tcp")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1502},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 20},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("value"), 9001},
       {QStringLiteral("timeoutMs"), 1500},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbTcpWrite")}});
  add(QStringLiteral("mbTcpR"), QStringLiteral("Modbus 读取 · TCP 回环"),
      QStringLiteral("modbus_read"), 80, 1580, QStringLiteral("mbTcpW"),
      {{QStringLiteral("transport"), QStringLiteral("tcp")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1502},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 20},
       {QStringLiteral("count"), 1},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("timeoutMs"), 1500},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbTcpRead")}});
  add(QStringLiteral("mbRtuW"), QStringLiteral("Modbus 写入 · RTU 回环"),
      QStringLiteral("modbus_write"), 80, 1700, QStringLiteral("mbTcpR"),
      {{QStringLiteral("transport"), QStringLiteral("rtu")},
       {QStringLiteral("serialPort"), QStringLiteral("ModbusRtuLoopback")},
       {QStringLiteral("baudrate"), 115200},
       {QStringLiteral("parity"), QStringLiteral("N")},
       {QStringLiteral("stopbits"), 1},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 30},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("value"), 777},
       {QStringLiteral("timeoutMs"), 2000},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbRtuWrite")}});
  add(QStringLiteral("mbRtuR"), QStringLiteral("Modbus 读取 · RTU 回环"),
      QStringLiteral("modbus_read"), 80, 1820, QStringLiteral("mbRtuW"),
      {{QStringLiteral("transport"), QStringLiteral("rtu")},
       {QStringLiteral("serialPort"), QStringLiteral("ModbusRtuLoopback")},
       {QStringLiteral("baudrate"), 115200},
       {QStringLiteral("parity"), QStringLiteral("N")},
       {QStringLiteral("stopbits"), 1},
       {QStringLiteral("area"), QStringLiteral("holding")},
       {QStringLiteral("address"), 30},
       {QStringLiteral("count"), 1},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("timeoutMs"), 2000},
       {QStringLiteral("deviceId"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("mbRtuRead")}});
  add(QStringLiteral("s7W"), QStringLiteral("S7 写入 · 模拟器"),
      QStringLiteral("s7_write"), 80, 1940, QStringLiteral("mbRtuR"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("area"), QStringLiteral("db")},
       {QStringLiteral("dbNumber"), 1},
       {QStringLiteral("byteOffset"), 10},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("value"), 4242},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("s7Write")}});
  add(QStringLiteral("s7R"), QStringLiteral("S7 读取 · 模拟器"),
      QStringLiteral("s7_read"), 80, 2060, QStringLiteral("s7W"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("area"), QStringLiteral("db")},
       {QStringLiteral("dbNumber"), 1},
       {QStringLiteral("byteOffset"), 10},
       {QStringLiteral("count"), 1},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("s7Read")}});
  add(QStringLiteral("s7TcpW"), QStringLiteral("S7 写入 · TCP 回环"),
      QStringLiteral("s7_write"), 80, 2180, QStringLiteral("s7R"),
      {{QStringLiteral("connection"), QStringLiteral("plc")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1102},
       {QStringLiteral("rack"), 0},
       {QStringLiteral("slot"), 1},
       {QStringLiteral("area"), QStringLiteral("db")},
       {QStringLiteral("dbNumber"), 1},
       {QStringLiteral("byteOffset"), 20},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("value"), 9001},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("s7TcpWrite")}});
  add(QStringLiteral("s7TcpR"), QStringLiteral("S7 读取 · TCP 回环"),
      QStringLiteral("s7_read"), 80, 2300, QStringLiteral("s7TcpW"),
      {{QStringLiteral("connection"), QStringLiteral("plc")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1102},
       {QStringLiteral("rack"), 0},
       {QStringLiteral("slot"), 1},
       {QStringLiteral("area"), QStringLiteral("db")},
       {QStringLiteral("dbNumber"), 1},
       {QStringLiteral("byteOffset"), 20},
       {QStringLiteral("count"), 1},
       {QStringLiteral("dataType"), QStringLiteral("uint16")},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("s7TcpRead")}});
  add(QStringLiteral("opcW"), QStringLiteral("OPC UA 写入 · 模拟器"),
      QStringLiteral("opcua_write"), 80, 2420, QStringLiteral("s7TcpR"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
       {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
       {QStringLiteral("dataType"), QStringLiteral("UInt32")},
       {QStringLiteral("value"), 4242},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("opcWrite")}});
  add(QStringLiteral("opcR"), QStringLiteral("OPC UA 读取 · 模拟器"),
      QStringLiteral("opcua_read"), 80, 2540, QStringLiteral("opcW"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
       {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
       {QStringLiteral("requireGood"), true},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("opcRead")}});
  add(QStringLiteral("opcWait"), QStringLiteral("等待 OPC UA 信号 · 模拟器"),
      QStringLiteral("opcua_wait"), 80, 2660, QStringLiteral("opcR"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
       {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
       {QStringLiteral("comparison"), QStringLiteral("eq")},
       {QStringLiteral("expectedValue"), 4242},
       {QStringLiteral("triggerMode"), QStringLiteral("level")},
       {QStringLiteral("publishingIntervalMs"), 100},
       {QStringLiteral("waitTimeoutMs"), 3000},
       {QStringLiteral("onTimeout"), QStringLiteral("error")},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("opcWait")}});
  add(QStringLiteral("opcBrowse"), QStringLiteral("OPC UA 浏览 · 模拟器"),
      QStringLiteral("opcua_browse"), 80, 2780, QStringLiteral("opcWait"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
       {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS")},
       {QStringLiteral("browseLimit"), 100},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("opcBrowse")}});
  add(QStringLiteral("opcTcpW"), QStringLiteral("OPC UA 写入 · TCP 回环"),
      QStringLiteral("opcua_write"), 80, 2900, QStringLiteral("opcBrowse"),
      {{QStringLiteral("connection"), QStringLiteral("server")},
       {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
       {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
       {QStringLiteral("dataType"), QStringLiteral("UInt32")},
       {QStringLiteral("value"), 9001},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("opcTcpWrite")}});
  add(QStringLiteral("opcTcpR"), QStringLiteral("OPC UA 读取 · TCP 回环"),
      QStringLiteral("opcua_read"), 80, 3020, QStringLiteral("opcTcpW"),
      {{QStringLiteral("connection"), QStringLiteral("server")},
       {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
       {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
       {QStringLiteral("requireGood"), true},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("resultVar"), QStringLiteral("opcTcpRead")}});
  add(QStringLiteral("mqttW"), QStringLiteral("MQTT 发布 · 模拟器"),
      QStringLiteral("mqtt_publish"), 80, 3140, QStringLiteral("opcTcpR"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1883},
       {QStringLiteral("topic"), QStringLiteral("sieans/inspection")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("qos"), 1},
       {QStringLiteral("retain"), true},
       {QStringLiteral("value"), QStringLiteral("4242")},
       {QStringLiteral("timeoutMs"), 5000},
       {QStringLiteral("resultVar"), QStringLiteral("mqttPub")}});
  add(QStringLiteral("mqttR"), QStringLiteral("MQTT 接收 · 模拟器"),
      QStringLiteral("mqtt_receive"), 80, 3260, QStringLiteral("mqttW"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1883},
       {QStringLiteral("topic"), QStringLiteral("sieans/inspection")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("qos"), 1},
       {QStringLiteral("acceptRetained"), true},
       {QStringLiteral("timeoutMs"), 5000},
       {QStringLiteral("resultVar"), QStringLiteral("mqttRecv")}});
  add(QStringLiteral("mqttTcpW"), QStringLiteral("MQTT 发布 · TCP 回环"),
      QStringLiteral("mqtt_publish"), 80, 3380, QStringLiteral("mqttR"),
      {{QStringLiteral("connection"), QStringLiteral("broker")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1883},
       {QStringLiteral("topic"), QStringLiteral("sieans/inspection")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("qos"), 1},
       {QStringLiteral("retain"), true},
       {QStringLiteral("value"), QStringLiteral("9001")},
       {QStringLiteral("timeoutMs"), 5000},
       {QStringLiteral("resultVar"), QStringLiteral("mqttTcpPub")}});
  add(QStringLiteral("mqttTcpR"), QStringLiteral("MQTT 接收 · TCP 回环"),
      QStringLiteral("mqtt_receive"), 80, 3500, QStringLiteral("mqttTcpW"),
      {{QStringLiteral("connection"), QStringLiteral("broker")},
       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
       {QStringLiteral("port"), 1883},
       {QStringLiteral("topic"), QStringLiteral("sieans/inspection")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("qos"), 1},
       {QStringLiteral("acceptRetained"), true},
       {QStringLiteral("timeoutMs"), 5000},
       {QStringLiteral("resultVar"), QStringLiteral("mqttTcpRecv")}});

  add(QStringLiteral("yolo1"), QStringLiteral("YOLO 目标检测"),
      QStringLiteral("yolo"), 80, 3620, QStringLiteral("mqttTcpR"),
      {{QStringLiteral("model"), QStringLiteral("yolo11n.pt")},
       {QStringLiteral("device"), QStringLiteral("cpu")},
       {QStringLiteral("confidence"), 0.25},
       {QStringLiteral("iou"), 0.45},
       {QStringLiteral("imageSize"), 640},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true},
       {QStringLiteral("resultVar"), QStringLiteral("yolo")}});
  add(QStringLiteral("yoloSeg1"), QStringLiteral("YOLO 实例分割"),
      QStringLiteral("yolo_segment"), 80, 3740, QStringLiteral("yolo1"),
      {{QStringLiteral("model"), QStringLiteral("yolo11n-seg.pt")},
       {QStringLiteral("device"), QStringLiteral("cpu")},
       {QStringLiteral("confidence"), 0.25},
       {QStringLiteral("iou"), 0.45},
       {QStringLiteral("imageSize"), 640},
       {QStringLiteral("maxDetections"), 50},
       {QStringLiteral("minArea"), 1},
       {QStringLiteral("contourTolerance"), 0.5},
       {QStringLiteral("overlayAlpha"), 0.35},
       {QStringLiteral("output"), QStringLiteral("overlay")},
       {QStringLiteral("showOverlay"), true},
       {QStringLiteral("showLabels"), true},
       {QStringLiteral("resultVar"), QStringLiteral("yoloSeg")}});

  add(QStringLiteral("cloudFilt"), QStringLiteral("点云滤波 · 软场景裁剪"),
      QStringLiteral("cloud_filter"), 80, 3860, QStringLiteral("yoloSeg1"),
      {{QStringLiteral("inputSource"), QStringLiteral("soft_fixture")},
       {QStringLiteral("method"), QStringLiteral("crop")},
       {QStringLiteral("minX"), -50},
       {QStringLiteral("minY"), -50},
       {QStringLiteral("minZ"), -50},
       {QStringLiteral("maxX"), 50},
       {QStringLiteral("maxY"), 50},
       {QStringLiteral("maxZ"), 50},
       {QStringLiteral("resultVar"), QStringLiteral("cloudFilt")}});
  add(QStringLiteral("cloudPlane"), QStringLiteral("3D 平面分割 · 去地面"),
      QStringLiteral("cloud_plane"), 80, 3980, QStringLiteral("cloudFilt"),
      {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
       {QStringLiteral("distanceThreshold"), 0.5},
       {QStringLiteral("iterations"), 500},
       {QStringLiteral("output"), QStringLiteral("outliers")},
       {QStringLiteral("resultVar"), QStringLiteral("cloudPlane")}});
  add(QStringLiteral("cloudClust"), QStringLiteral("3D 目标聚类"),
      QStringLiteral("cloud_cluster"), 80, 4100, QStringLiteral("cloudPlane"),
      {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
       {QStringLiteral("eps"), 3},
       {QStringLiteral("minPoints"), 8},
       {QStringLiteral("resultVar"), QStringLiteral("cloudClust")}});
  add(QStringLiteral("cloudMeas"), QStringLiteral("3D 尺寸测量 · 标准件"),
      QStringLiteral("cloud_measure"), 80, 4220, QStringLiteral("cloudClust"),
      {{QStringLiteral("inputSource"), QStringLiteral("soft_part")},
       {QStringLiteral("resultVar"), QStringLiteral("cloudMeas")}});
  add(QStringLiteral("cloudHgt"), QStringLiteral("高度与体积估计"),
      QStringLiteral("cloud_height"), 80, 4340, QStringLiteral("cloudMeas"),
      {{QStringLiteral("inputSource"), QStringLiteral("soft_surface")},
       {QStringLiteral("baselineZ"), 0},
       {QStringLiteral("cellSize"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("cloudHgt")}});
  add(QStringLiteral("cloudReg"), QStringLiteral("3D 点云配准 · 已知平移"),
      QStringLiteral("cloud_register"), 80, 4460, QStringLiteral("cloudHgt"),
      {{QStringLiteral("inputSource"), QStringLiteral("soft_register")},
       {QStringLiteral("inputShiftX"), 5},
       {QStringLiteral("inputShiftY"), -3},
       {QStringLiteral("inputShiftZ"), 2},
       {QStringLiteral("targetSource"), QStringLiteral("soft_register")},
       {QStringLiteral("method"), QStringLiteral("icp")},
       {QStringLiteral("maxDistance"), 10},
       {QStringLiteral("iterations"), 40},
       {QStringLiteral("resultVar"), QStringLiteral("cloudReg")}});

  add(QStringLiteral("delay1"), QStringLiteral("延时等待 · 短等待"),
      QStringLiteral("delay"), 80, 4580, QStringLiteral("cloudReg"),
      {{QStringLiteral("milliseconds"), 5},
       {QStringLiteral("resultVar"), QStringLiteral("delay")}});
  add(QStringLiteral("varsSet"), QStringLiteral("变量赋值 · 写入"),
      QStringLiteral("variables"), 80, 4700, QStringLiteral("delay1"),
      {{QStringLiteral("scope"), QStringLiteral("flow")},
       {QStringLiteral("name"), QStringLiteral("varsAssign")},
       {QStringLiteral("mode"), QStringLiteral("set")},
       {QStringLiteral("value"), 4242},
       {QStringLiteral("resultVar"), QStringLiteral("varsSet")}});
  add(QStringLiteral("varsInc"), QStringLiteral("变量赋值 · 累加"),
      QStringLiteral("variables"), 80, 4820, QStringLiteral("varsSet"),
      {{QStringLiteral("scope"), QStringLiteral("flow")},
       {QStringLiteral("name"), QStringLiteral("varsAssign")},
       {QStringLiteral("mode"), QStringLiteral("increment")},
       {QStringLiteral("value"), 1},
       {QStringLiteral("resultVar"), QStringLiteral("varsInc")}});
  add(QStringLiteral("tcpEx"), QStringLiteral("TCP 报文通信 · 回显"),
      QStringLiteral("tcp_exchange"), 80, 4940, QStringLiteral("varsInc"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("mode"), QStringLiteral("exchange")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("value"), QStringLiteral("SIEANS-TCP-4242")},
       {QStringLiteral("txFraming"), QStringLiteral("crlf")},
       {QStringLiteral("rxFraming"), QStringLiteral("crlf")},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("maxBytes"), 65536},
       {QStringLiteral("resultVar"), QStringLiteral("tcpEx")}});
  add(QStringLiteral("udpEx"), QStringLiteral("UDP 报文通信 · 回显"),
      QStringLiteral("udp_exchange"), 80, 5060, QStringLiteral("tcpEx"),
      {{QStringLiteral("connection"), QStringLiteral("simulator")},
       {QStringLiteral("mode"), QStringLiteral("exchange")},
       {QStringLiteral("encoding"), QStringLiteral("text")},
       {QStringLiteral("value"), QStringLiteral("SIEANS-UDP-9001")},
       {QStringLiteral("timeoutMs"), 3000},
       {QStringLiteral("maxBytes"), 65536},
       {QStringLiteral("resultVar"), QStringLiteral("udpEx")}});
  add(QStringLiteral("script1"), QStringLiteral("Python 脚本 · 烟测"),
      QStringLiteral("script"), 80, 5180, QStringLiteral("udpEx"),
      {{QStringLiteral("code"),
        QStringLiteral("def run(ctx):\n"
                       "    count = ctx[\"params\"].get(\"count\", 0)\n"
                       "    return dict(result=dict(scriptOut=4242, count=count, passed=True))\n")},
       {QStringLiteral("timeoutMs"), 5000},
       {QStringLiteral("arguments"), QVariantMap{{QStringLiteral("count"), 1}}},
       {QStringLiteral("outputBindings"),
        QVariantList{QVariantMap{{QStringLiteral("field"), QStringLiteral("scriptOut")},
                                 {QStringLiteral("scope"), QStringLiteral("flow")},
                                 {QStringLiteral("name"), QStringLiteral("scriptOut")}}}},
       {QStringLiteral("resultVar"), QStringLiteral("script")}});
  add(QStringLiteral("plugin1"), QStringLiteral("算子插件 · 软件烟测"),
      QStringLiteral("plugin"), 80, 5300, QStringLiteral("script1"),
      {{QStringLiteral("pluginId"), QStringLiteral("sieans-soft-smoke")},
       {QStringLiteral("pluginVersion"), QStringLiteral("1.0.0")},
       {QStringLiteral("operatorId"), QStringLiteral("fixed-value")},
       {QStringLiteral("arguments"), QVariantMap{{QStringLiteral("value"), 9001}}},
       {QStringLiteral("outputBindings"),
        QVariantList{QVariantMap{{QStringLiteral("field"), QStringLiteral("value")},
                                 {QStringLiteral("scope"), QStringLiteral("flow")},
                                 {QStringLiteral("name"), QStringLiteral("pluginValue")}}}},
       {QStringLiteral("resultVar"), QStringLiteral("plugin")}});

  auto link = [&](const QString& a, const QString& b,
                  const QString& when = QStringLiteral("always")) {
    FlowEdge e;
    e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    e.from = a;
    e.to = b;
    e.when = when;
    edges_.push_back(e);
  };
  link(QStringLiteral("source"), QStringLiteral("cam1"));
  link(QStringLiteral("cam1"), QStringLiteral("qr1"));
  link(QStringLiteral("cam1"), QStringLiteral("ocr1"));
  link(QStringLiteral("cam1"), QStringLiteral("cal1"));
  link(QStringLiteral("cam1"), QStringLiteral("defOk"));
  link(QStringLiteral("cam1"), QStringLiteral("defNg"));
  link(QStringLiteral("cam1"), QStringLiteral("loc1"));
  link(QStringLiteral("loc1"), QStringLiteral("pose1"));
  link(QStringLiteral("pose1"), QStringLiteral("defFollow"));
  link(QStringLiteral("cam1"), QStringLiteral("geomCirc"));
  link(QStringLiteral("cam1"), QStringLiteral("geomLine"));
  link(QStringLiteral("pose1"), QStringLiteral("geomFollow"));
  link(QStringLiteral("cam1"), QStringLiteral("measCirc"));
  link(QStringLiteral("cam1"), QStringLiteral("measLine"));
  link(QStringLiteral("cam1"), QStringLiteral("measAngle"));
  link(QStringLiteral("cam1"), QStringLiteral("measPts"));
  link(QStringLiteral("qr1"), QStringLiteral("var1"));
  link(QStringLiteral("var1"), QStringLiteral("gate1"));
  link(QStringLiteral("gate1"), QStringLiteral("fmt1"));
  link(QStringLiteral("fmt1"), QStringLiteral("tx1"));
  link(QStringLiteral("tx1"), QStringLiteral("rx1"));
  link(QStringLiteral("gate1"), QStringLiteral("cond1"));
  link(QStringLiteral("cond1"), QStringLiteral("taken1"), QStringLiteral("true"));
  link(QStringLiteral("cond1"), QStringLiteral("skipped1"), QStringLiteral("false"));
  link(QStringLiteral("taken1"), QStringLiteral("merge1"));
  link(QStringLiteral("skipped1"), QStringLiteral("merge1"));
  link(QStringLiteral("merge1"), QStringLiteral("sf1"));
  link(QStringLiteral("sf1"), QStringLiteral("loop1"));
  link(QStringLiteral("rx1"), QStringLiteral("ser1"));
  link(QStringLiteral("ser1"), QStringLiteral("serPty"));
  link(QStringLiteral("serPty"), QStringLiteral("mbW"));
  link(QStringLiteral("mbW"), QStringLiteral("mbR"));
  link(QStringLiteral("mbR"), QStringLiteral("mbWait"));
  link(QStringLiteral("mbWait"), QStringLiteral("mbTcpW"));
  link(QStringLiteral("mbTcpW"), QStringLiteral("mbTcpR"));
  link(QStringLiteral("mbTcpR"), QStringLiteral("mbRtuW"));
  link(QStringLiteral("mbRtuW"), QStringLiteral("mbRtuR"));
  link(QStringLiteral("mbRtuR"), QStringLiteral("s7W"));
  link(QStringLiteral("s7W"), QStringLiteral("s7R"));
  link(QStringLiteral("s7R"), QStringLiteral("s7TcpW"));
  link(QStringLiteral("s7TcpW"), QStringLiteral("s7TcpR"));
  link(QStringLiteral("s7TcpR"), QStringLiteral("opcW"));
  link(QStringLiteral("opcW"), QStringLiteral("opcR"));
  link(QStringLiteral("opcR"), QStringLiteral("opcWait"));
  link(QStringLiteral("opcWait"), QStringLiteral("opcBrowse"));
  link(QStringLiteral("opcBrowse"), QStringLiteral("opcTcpW"));
  link(QStringLiteral("opcTcpW"), QStringLiteral("opcTcpR"));
  link(QStringLiteral("opcTcpR"), QStringLiteral("mqttW"));
  link(QStringLiteral("mqttW"), QStringLiteral("mqttR"));
  link(QStringLiteral("mqttR"), QStringLiteral("mqttTcpW"));
  link(QStringLiteral("mqttTcpW"), QStringLiteral("mqttTcpR"));
  link(QStringLiteral("mqttTcpR"), QStringLiteral("yolo1"));
  link(QStringLiteral("yolo1"), QStringLiteral("yoloSeg1"));
  link(QStringLiteral("yoloSeg1"), QStringLiteral("cloudFilt"));
  link(QStringLiteral("cloudFilt"), QStringLiteral("cloudPlane"));
  link(QStringLiteral("cloudPlane"), QStringLiteral("cloudClust"));
  link(QStringLiteral("cloudClust"), QStringLiteral("cloudMeas"));
  link(QStringLiteral("cloudMeas"), QStringLiteral("cloudHgt"));
  link(QStringLiteral("cloudHgt"), QStringLiteral("cloudReg"));
  link(QStringLiteral("cloudReg"), QStringLiteral("delay1"));
  link(QStringLiteral("delay1"), QStringLiteral("varsSet"));
  link(QStringLiteral("varsSet"), QStringLiteral("varsInc"));
  link(QStringLiteral("varsInc"), QStringLiteral("tcpEx"));
  link(QStringLiteral("tcpEx"), QStringLiteral("udpEx"));
  link(QStringLiteral("udpEx"), QStringLiteral("script1"));
  link(QStringLiteral("script1"), QStringLiteral("plugin1"));

  variables_ = {
      {QStringLiteral("barcodeCount"), 0},
      {QStringLiteral("barcodeText"), QString()},
      {QStringLiteral("barcodeAll"), QString()},
      {QStringLiteral("barcodeOk"), 0},
      {QStringLiteral("ocrCount"), 0},
      {QStringLiteral("ocrText"), QString()},
      {QStringLiteral("ocrAll"), QString()},
      {QStringLiteral("ocrOk"), 0},
      {QStringLiteral("caliperDist"), 0},
      {QStringLiteral("caliperOk"), 0},
      {QStringLiteral("measureMm"), 0},
      {QStringLiteral("caliperMm"), 0},
      {QStringLiteral("passGate"), 0},
      {QStringLiteral("formatted"), QString()},
      {QStringLiteral("commPayload"), QString()},
      {QStringLiteral("lastRecv"), QString()},
      {QStringLiteral("conditionPassed"), 0},
      {QStringLiteral("conditionOk"), 0},
      {QStringLiteral("branchTaken"), QString()},
      {QStringLiteral("branchRoute"), QString()},
      {QStringLiteral("mergeFrom"), QString()},
      {QStringLiteral("skippedCount"), 0},
      {QStringLiteral("subflowPassed"), 0},
      {QStringLiteral("subflowCount"), 0},
      {QStringLiteral("loopCompleted"), 0},
      {QStringLiteral("loopStoppedEarly"), 0},
      {QStringLiteral("loopCount"), 0},
      {QStringLiteral("loopPassed"), 0},
      {QStringLiteral("defectsCount"), 0},
      {QStringLiteral("defectsRatio"), 0},
      {QStringLiteral("defectsOk"), 0},
      {QStringLiteral("defectsPassed"), 0},
      {QStringLiteral("defectsMaxArea"), 0},
      {QStringLiteral("defectsTotalArea"), 0},
      {QStringLiteral("defectsCleanCount"), 0},
      {QStringLiteral("defectsCleanOk"), 0},
      {QStringLiteral("defectsCleanRatio"), 0},
      {QStringLiteral("locateOk"), 0},
      {QStringLiteral("locateScore"), 0},
      {QStringLiteral("locateX"), 0},
      {QStringLiteral("locateY"), 0},
      {QStringLiteral("locateAngle"), 0},
      {QStringLiteral("locateCount"), 0},
      {QStringLiteral("fixtureOk"), 0},
      {QStringLiteral("fixtureX"), 0},
      {QStringLiteral("fixtureY"), 0},
      {QStringLiteral("fixtureAngle"), 0},
      {QStringLiteral("defectsFollowCount"), 0},
      {QStringLiteral("defectsFollowOk"), 0},
      {QStringLiteral("defectsFollowRoiX"), 0},
      {QStringLiteral("defectsFollowRoiY"), 0},
      {QStringLiteral("geomCircCount"), 0},
      {QStringLiteral("geomCircOk"), 0},
      {QStringLiteral("geomCircX"), 0},
      {QStringLiteral("geomCircY"), 0},
      {QStringLiteral("geomCircRadius"), 0},
      {QStringLiteral("geomLineCount"), 0},
      {QStringLiteral("geomLineOk"), 0},
      {QStringLiteral("geomLineLength"), 0},
      {QStringLiteral("geomLineAngle"), 0},
      {QStringLiteral("geomFollowCount"), 0},
      {QStringLiteral("geomFollowOk"), 0},
      {QStringLiteral("geomFollowRadius"), 0},
      {QStringLiteral("geomFollowRoiX"), 0},
      {QStringLiteral("geomFollowRoiY"), 0},
      {QStringLiteral("measCircCount"), 0},
      {QStringLiteral("measCircOk"), 0},
      {QStringLiteral("measCircDiameter"), 0},
      {QStringLiteral("measCircRadius"), 0},
      {QStringLiteral("measCircDiameterMm"), 0},
      {QStringLiteral("measLineCount"), 0},
      {QStringLiteral("measLineOk"), 0},
      {QStringLiteral("measLineLength"), 0},
      {QStringLiteral("measAngAngle"), 0},
      {QStringLiteral("measAngOk"), 0},
      {QStringLiteral("measPtsDist"), 0},
      {QStringLiteral("measPtsOk"), 0},
      {QStringLiteral("serialOk"), 0},
      {QStringLiteral("serialRx"), QString()},
      {QStringLiteral("serialTx"), QString()},
      {QStringLiteral("serialBytes"), 0},
      {QStringLiteral("serialSim"), 0},
      {QStringLiteral("serialPort"), QString()},
      {QStringLiteral("serialPtyOk"), 0},
      {QStringLiteral("serialPtyRx"), QString()},
      {QStringLiteral("serialPtyTx"), QString()},
      {QStringLiteral("serialPtyBytes"), 0},
      {QStringLiteral("mbWriteOk"), 0},
      {QStringLiteral("mbWriteValue"), 0},
      {QStringLiteral("mbWriteAck"), 0},
      {QStringLiteral("mbReadOk"), 0},
      {QStringLiteral("mbReadValue"), 0},
      {QStringLiteral("mbWaitOk"), 0},
      {QStringLiteral("mbWaitTriggered"), 0},
      {QStringLiteral("mbWaitValue"), 0},
      {QStringLiteral("mbTcpWriteOk"), 0},
      {QStringLiteral("mbTcpWriteValue"), 0},
      {QStringLiteral("mbTcpReadOk"), 0},
      {QStringLiteral("mbTcpReadValue"), 0},
      {QStringLiteral("mbRtuWriteOk"), 0},
      {QStringLiteral("mbRtuWriteValue"), 0},
      {QStringLiteral("mbRtuReadOk"), 0},
      {QStringLiteral("mbRtuReadValue"), 0},
      {QStringLiteral("s7WriteOk"), 0},
      {QStringLiteral("s7WriteValue"), 0},
      {QStringLiteral("s7WriteAck"), 0},
      {QStringLiteral("s7ReadOk"), 0},
      {QStringLiteral("s7ReadValue"), 0},
      {QStringLiteral("s7TcpWriteOk"), 0},
      {QStringLiteral("s7TcpWriteValue"), 0},
      {QStringLiteral("s7TcpReadOk"), 0},
      {QStringLiteral("s7TcpReadValue"), 0},
      {QStringLiteral("opcWriteOk"), 0},
      {QStringLiteral("opcWriteValue"), 0},
      {QStringLiteral("opcWriteAck"), 0},
      {QStringLiteral("opcReadOk"), 0},
      {QStringLiteral("opcReadValue"), 0},
      {QStringLiteral("opcWaitOk"), 0},
      {QStringLiteral("opcWaitTriggered"), 0},
      {QStringLiteral("opcWaitValue"), 0},
      {QStringLiteral("opcBrowseOk"), 0},
      {QStringLiteral("opcBrowseCount"), 0},
      {QStringLiteral("opcTcpWriteOk"), 0},
      {QStringLiteral("opcTcpWriteValue"), 0},
      {QStringLiteral("opcTcpReadOk"), 0},
      {QStringLiteral("opcTcpReadValue"), 0},
      {QStringLiteral("mqttPubOk"), 0},
      {QStringLiteral("mqttPubValue"), 0},
      {QStringLiteral("mqttPubAck"), 0},
      {QStringLiteral("mqttRecvOk"), 0},
      {QStringLiteral("mqttRecvValue"), 0},
      {QStringLiteral("mqttTcpPubOk"), 0},
      {QStringLiteral("mqttTcpPubValue"), 0},
      {QStringLiteral("mqttTcpRecvOk"), 0},
      {QStringLiteral("mqttTcpRecvValue"), 0},
      {QStringLiteral("yoloOk"), 0},
      {QStringLiteral("yoloCount"), 0},
      {QStringLiteral("yoloScore"), 0},
      {QStringLiteral("yoloLabel"), QString()},
      {QStringLiteral("yoloSegOk"), 0},
      {QStringLiteral("yoloSegCount"), 0},
      {QStringLiteral("yoloSegScore"), 0},
      {QStringLiteral("yoloSegArea"), 0},
      {QStringLiteral("yoloSegLabel"), QString()},
      {QStringLiteral("cloudFiltOk"), 0},
      {QStringLiteral("cloudFiltCount"), 0},
      {QStringLiteral("cloudPlaneOk"), 0},
      {QStringLiteral("cloudPlaneInliers"), 0},
      {QStringLiteral("cloudPlaneRms"), 0},
      {QStringLiteral("cloudClustOk"), 0},
      {QStringLiteral("cloudClustCount"), 0},
      {QStringLiteral("cloudClustNoise"), 0},
      {QStringLiteral("cloudMeasOk"), 0},
      {QStringLiteral("cloudMeasSizeX"), 0},
      {QStringLiteral("cloudMeasSizeY"), 0},
      {QStringLiteral("cloudMeasSizeZ"), 0},
      {QStringLiteral("cloudHgtOk"), 0},
      {QStringLiteral("cloudHgtVolume"), 0},
      {QStringLiteral("cloudHgtMax"), 0},
      {QStringLiteral("cloudRegOk"), 0},
      {QStringLiteral("cloudRegFound"), 0},
      {QStringLiteral("cloudRegDx"), 0},
      {QStringLiteral("cloudRegDy"), 0},
      {QStringLiteral("cloudRegDz"), 0},
      {QStringLiteral("cloudRegFitness"), 0},
      {QStringLiteral("cloudRegRms"), 0},
      {QStringLiteral("delayOk"), 0},
      {QStringLiteral("delayMs"), 0},
      {QStringLiteral("delayElapsed"), 0},
      {QStringLiteral("varsAssign"), 0},
      {QStringLiteral("varsSetOk"), 0},
      {QStringLiteral("varsSetValue"), 0},
      {QStringLiteral("varsIncOk"), 0},
      {QStringLiteral("varsIncValue"), 0},
      {QStringLiteral("tcpExOk"), 0},
      {QStringLiteral("tcpExValue"), QString()},
      {QStringLiteral("tcpExDelivery"), QString()},
      {QStringLiteral("udpExOk"), 0},
      {QStringLiteral("udpExValue"), QString()},
      {QStringLiteral("udpExDelivery"), QString()},
      {QStringLiteral("scriptOk"), 0},
      {QStringLiteral("scriptOut"), 0},
      {QStringLiteral("pluginOk"), 0},
      {QStringLiteral("pluginValue"), 0},
  };
  subflows_.clear();
  subflows_.push_back(makeCounterSubflow());
  commManager_ = {
      {QStringLiteral("devices"),
       QVariantList{
           QVariantMap{{QStringLiteral("id"), QStringLiteral("local-loop")},
                       {QStringLiteral("name"), QStringLiteral("LocalLoop")},
                       {QStringLiteral("protocol"), QStringLiteral("Local Bus")},
                       {QStringLiteral("enabled"), true}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("tcp-real-loopback")},
                       {QStringLiteral("name"), QStringLiteral("TcpRealLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("TCP Server")},
                       {QStringLiteral("enabled"), true},
                       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                       {QStringLiteral("port"), 19956}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("serial-pty-loopback")},
                       {QStringLiteral("name"), QStringLiteral("SerialLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("Serial PTY")},
                       {QStringLiteral("enabled"), true}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("modbus-tcp-loopback")},
                       {QStringLiteral("name"), QStringLiteral("ModbusTcpLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("Modbus TCP")},
                       {QStringLiteral("enabled"), true},
                       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                       {QStringLiteral("port"), 1502}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("modbus-rtu-loopback")},
                       {QStringLiteral("name"), QStringLiteral("ModbusRtuLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("Modbus RTU")},
                       {QStringLiteral("enabled"), true}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("s7-tcp-loopback")},
                       {QStringLiteral("name"), QStringLiteral("S7TcpLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("S7")},
                       {QStringLiteral("enabled"), true},
                       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                       {QStringLiteral("port"), 1102}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("opcua-tcp-loopback")},
                       {QStringLiteral("name"), QStringLiteral("OpcUaLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("OPC UA")},
                       {QStringLiteral("enabled"), true},
                       {QStringLiteral("endpoint"),
                        QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")}},
           QVariantMap{{QStringLiteral("id"), QStringLiteral("mqtt-loopback")},
                       {QStringLiteral("name"), QStringLiteral("MqttLoopback")},
                       {QStringLiteral("protocol"), QStringLiteral("MQTT")},
                       {QStringLiteral("enabled"), true},
                       {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                       {QStringLiteral("port"), 1883}},
       }},
      {QStringLiteral("tcpReal"),
       QVariantMap{{QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                   {QStringLiteral("port"), 19956},
                   {QStringLiteral("framing"), QStringLiteral("lf")},
                   {QStringLiteral("role"), QStringLiteral("server")},
                   {QStringLiteral("ack"), QStringLiteral("OK")},
                   {QStringLiteral("autoStart"), true},
                   {QStringLiteral("reconnect"), true}}},
      {QStringLiteral("serialReal"),
       QVariantMap{{QStringLiteral("autoStart"), true},
                   {QStringLiteral("framing"), QStringLiteral("crlf")},
                   {QStringLiteral("echo"), true}}},
      {QStringLiteral("modbusReal"),
       QVariantMap{{QStringLiteral("autoStart"), true},
                   {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                   {QStringLiteral("port"), 1502}}},
      {QStringLiteral("s7Real"),
       QVariantMap{{QStringLiteral("autoStart"), true},
                   {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                   {QStringLiteral("port"), 1102},
                   {QStringLiteral("rack"), 0},
                   {QStringLiteral("slot"), 1}}},
      {QStringLiteral("opcuaReal"),
       QVariantMap{{QStringLiteral("autoStart"), true},
                   {QStringLiteral("endpoint"),
                    QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
                   {QStringLiteral("port"), 4840}}},
      {QStringLiteral("mqttReal"),
       QVariantMap{{QStringLiteral("autoStart"), true},
                   {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                   {QStringLiteral("port"), 1883}}},
      {QStringLiteral("sendEvents"),
       QVariantList{
           QVariantMap{{QStringLiteral("device"), QStringLiteral("LocalLoop")},
                       {QStringLiteral("on"), QStringLiteral("ok")},
                       {QStringLiteral("message"),
                        QStringLiteral("HOST OK result=${flow.hostResult} "
                                       "pass=${flow.passGate} "
                                       "count=${flow.barcodeCount} "
                                       "mode=${flow.hostMode}")}},
           QVariantMap{{QStringLiteral("device"), QStringLiteral("TcpRealLoopback")},
                       {QStringLiteral("on"), QStringLiteral("ok")},
                       {QStringLiteral("message"),
                        QStringLiteral("HOST OK result=${flow.hostResult} "
                                       "pass=${flow.passGate} "
                                       "count=${flow.barcodeCount} "
                                       "lock=${flow.recipeLocked} "
                                       "mode=${flow.hostMode}")}},
           QVariantMap{{QStringLiteral("device"), QStringLiteral("LocalLoop")},
                       {QStringLiteral("on"), QStringLiteral("ng")},
                       {QStringLiteral("message"),
                        QStringLiteral("HOST NG result=${flow.hostResult} "
                                       "pass=${flow.passGate} "
                                       "mode=${flow.hostMode} "
                                       "streak=${flow.hostOkStreak}")}},
           QVariantMap{{QStringLiteral("device"), QStringLiteral("TcpRealLoopback")},
                       {QStringLiteral("on"), QStringLiteral("ng")},
                       {QStringLiteral("message"),
                        QStringLiteral("HOST NG result=${flow.hostResult} "
                                       "pass=${flow.passGate} "
                                       "lock=${flow.recipeLocked} "
                                       "mode=${flow.hostMode} "
                                       "streak=${flow.hostOkStreak}")}},
           QVariantMap{{QStringLiteral("device"), QStringLiteral("TcpRealLoopback")},
                       {QStringLiteral("on"), QStringLiteral("alarm")},
                       {QStringLiteral("message"),
                        QStringLiteral("HOST ALARM state=${flow.hostState} "
                                       "mode=${flow.hostMode} "
                                       "lock=${flow.recipeLocked} "
                                       "latched=${flow.alarmLatched} "
                                       "result=${flow.hostResult}")}},
       }},
  };
  flowIo_ = {
      {QStringLiteral("inputs"),
       QVariantList{
           QVariantMap{{QStringLiteral("name"), QStringLiteral("ImageData")},
                       {QStringLiteral("type"), QStringLiteral("IMAGE")},
                       {QStringLiteral("binding"), QStringLiteral("source.image")}},
           QVariantMap{{QStringLiteral("name"), QStringLiteral("InputROI")},
                       {QStringLiteral("type"), QStringLiteral("ROI")},
                       {QStringLiteral("binding"), QString()}},
       }},
      {QStringLiteral("outputs"),
       QVariantList{
           QVariantMap{{QStringLiteral("name"), QStringLiteral("ImageData")},
                       {QStringLiteral("type"), QStringLiteral("IMAGE")},
                       {QStringLiteral("binding"), QStringLiteral("source.image")}},
           QVariantMap{{QStringLiteral("name"), QStringLiteral("Result")},
                       {QStringLiteral("type"), QStringLiteral("JSON")},
                       {QStringLiteral("binding"), QStringLiteral("flow.formatted")}},
           QVariantMap{{QStringLiteral("name"), QStringLiteral("PassGate")},
                       {QStringLiteral("type"), QStringLiteral("INT")},
                       {QStringLiteral("binding"), QStringLiteral("flow.passGate")}},
           QVariantMap{{QStringLiteral("name"), QStringLiteral("HostResult")},
                       {QStringLiteral("type"), QStringLiteral("STRING")},
                       {QStringLiteral("binding"), QStringLiteral("flow.hostResult")}},
           QVariantMap{{QStringLiteral("name"), QStringLiteral("HostMode")},
                       {QStringLiteral("type"), QStringLiteral("STRING")},
                       {QStringLiteral("binding"), QStringLiteral("flow.hostMode")}},
           QVariantMap{{QStringLiteral("name"), QStringLiteral("HostState")},
                       {QStringLiteral("type"), QStringLiteral("STRING")},
                       {QStringLiteral("binding"), QStringLiteral("flow.hostState")}},
       }},
      {QStringLiteral("display"),
       QVariantMap{{QStringLiteral("globalImage"), true},
                   {QStringLiteral("note"), QStringLiteral("Qt VM I/O 绑定")}}},
  };
  flows_.clear();
  activeFlowId_.clear();
  ensureScheme();
  resetCanvasUndo();
  // Match official open-and-run-gentl-qr.sieans: only the 二维码链 pin group
  // is visible on the Host strip. Do not dump the seed variable catalog.
  {
    QVariantMap groups;
    groups.insert(QStringLiteral("二维码链"),
                  QStringList{QStringLiteral("barcodeCount"), QStringLiteral("barcodeText"),
                              QStringLiteral("barcodeAll"), QStringLiteral("barcodeOk"),
                              QStringLiteral("passGate"), QStringLiteral("urlOk"),
                              QStringLiteral("formatted")});
    groups.insert(QStringLiteral("门限"),
                  QStringList{QStringLiteral("barcodeOk"), QStringLiteral("passGate"),
                              QStringLiteral("urlOk")});
    groups.insert(QStringLiteral("通信"),
                  QStringList{QStringLiteral("formatted"), QStringLiteral("passGate"),
                              QStringLiteral("barcodeText"), QStringLiteral("lastRecv"),
                              QStringLiteral("urlOk")});
    setPinGroups(groups, QStringLiteral("二维码链"), true);
  }
}


void SieansDocument::setRunIntervalMs(int ms) {
  if (ms < 0) ms = 0;
  if (ms > 60000) ms = 60000;
  runIntervalMs_ = ms;
  raw_.insert(QStringLiteral("runIntervalMs"), runIntervalMs_);
}

void SieansDocument::setHostWatchKeys(const QStringList& keys) {
  QJsonObject hw = raw_.value(QStringLiteral("hostWatch")).toObject();
  QJsonArray arr;
  for (const QString& k : keys) {
    const QString t = k.trimmed();
    if (!t.isEmpty()) arr.append(t);
  }
  hw.insert(QStringLiteral("watchKeys"), arr);
  raw_.insert(QStringLiteral("hostWatch"), hw);
}

QStringList SieansDocument::hostWatchKeys() const {
  const QJsonObject hw = raw_.value(QStringLiteral("hostWatch")).toObject();
  QStringList keys;
  for (const QJsonValue& v : hw.value(QStringLiteral("watchKeys")).toArray()) {
    const QString t = v.toString().trimmed();
    if (!t.isEmpty()) keys << t;
  }
  if (keys.isEmpty()) {
    // A present pin group (even with zero keys) must not fall back to a
    // built-in catalog — that would re-populate chips after 备用 etc.
    const QString act = activePinGroup();
    if (!act.isEmpty()) return pinGroupKeys(act);
    // No watchKeys and no pin group: keep the Host strip empty. The old
    // barcode/ocr/caliper/defects/geom catalog belongs behind the
    // 「全部变量」toggle or in 变量监视, not the default first-open view.
  }
  return keys;
}

QStringList SieansDocument::pinGroupNames() const {
  const QJsonObject g = pinGroupsJson(hostWatchObject(raw_));
  QStringList names;
  for (auto it = g.begin(); it != g.end(); ++it) {
    const QString n = cleanPinGroupName(it.key());
    if (!names.contains(n)) names << n;
  }
  return names;
}

QStringList SieansDocument::pinGroupKeys(const QString& name) const {
  const QString want = cleanPinGroupName(name);
  const QJsonObject g = pinGroupsJson(hostWatchObject(raw_));
  QStringList keys;
  for (auto it = g.begin(); it != g.end(); ++it) {
    if (cleanPinGroupName(it.key()) != want) continue;
    for (const QString& k : cleanPinGroupKeyList(it.value().toArray())) {
      if (!keys.contains(k)) keys << k;
    }
  }
  return keys;
}

QString SieansDocument::activePinGroup() const {
  const QJsonObject hw = hostWatchObject(raw_);
  QString a = hw.value(QStringLiteral("activePinGroup")).toString().trimmed();
  if (a.isEmpty()) a = hw.value(QStringLiteral("active_pin_group")).toString().trimmed();
  // PySide / 早期方案把当前钉组写在 hostWatch.active。
  if (a.isEmpty()) a = hw.value(QStringLiteral("active")).toString().trimmed();
  const QStringList names = pinGroupNames();
  if (names.isEmpty()) return {};
  if (!a.isEmpty()) {
    if (names.contains(a)) return a;
    const QString cleaned = cleanPinGroupName(a);
    if (names.contains(cleaned)) return cleaned;
  }
  return names.first();
}

void SieansDocument::setPinGroups(const QVariantMap& groups, const QString& active,
                                  bool writeWatchKeys) {
  QJsonObject hw = hostWatchObject(raw_);
  QJsonObject cleaned;
  QStringList order;
  for (auto it = groups.begin(); it != groups.end(); ++it) {
    const QString n = cleanPinGroupName(it.key());
    QJsonArray arr;
    for (const QString& k : cleanPinGroupKeyVariant(it.value())) arr.append(k);
    if (cleaned.contains(n)) {
      QJsonArray merged = cleaned.value(n).toArray();
      QStringList have = cleanPinGroupKeyList(merged);
      for (const QString& k : cleanPinGroupKeyVariant(it.value())) {
        if (have.contains(k)) continue;
        have << k;
        merged.append(k);
      }
      cleaned.insert(n, merged);
    } else {
      cleaned.insert(n, arr);
      order << n;
    }
  }
  if (cleaned.isEmpty()) {
    hw.remove(QStringLiteral("pinGroups"));
    hw.remove(QStringLiteral("pin_groups"));
    hw.remove(QStringLiteral("activePinGroup"));
    hw.remove(QStringLiteral("active_pin_group"));
    raw_.insert(QStringLiteral("hostWatch"), hw);
    return;
  }
  hw.insert(QStringLiteral("pinGroups"), cleaned);
  hw.remove(QStringLiteral("pin_groups"));
  QString act = active.trimmed();
  if (act.isEmpty())
    act = hw.value(QStringLiteral("activePinGroup")).toString().trimmed();
  if (act.isEmpty())
    act = hw.value(QStringLiteral("active_pin_group")).toString().trimmed();
  if (!act.isEmpty() && !cleaned.contains(act))
    act = cleanPinGroupName(act);
  if (act.isEmpty() || !cleaned.contains(act))
    act = order.isEmpty() ? cleaned.begin().key() : order.first();
  hw.insert(QStringLiteral("activePinGroup"), act);
  hw.remove(QStringLiteral("active_pin_group"));
  if (writeWatchKeys) {
    QJsonArray keys = cleaned.value(act).toArray();
    hw.insert(QStringLiteral("watchKeys"), keys);
  }
  raw_.insert(QStringLiteral("hostWatch"), hw);
}

QString SieansDocument::ensurePinGroup(const QString& name, const QStringList& keys) {
  const QString n = cleanPinGroupName(name);
  QVariantMap groups;
  const QJsonObject g = pinGroupsJson(hostWatchObject(raw_));
  for (auto it = g.begin(); it != g.end(); ++it)
    groups.insert(cleanPinGroupName(it.key()), cleanPinGroupKeyList(it.value().toArray()));
  groups.insert(n, keys);
  const QString keep = activePinGroup();
  setPinGroups(groups, keep.isEmpty() ? n : keep, false);
  return n;
}

QString SieansDocument::activatePinGroup(const QString& name) {
  QString n = name.trimmed();
  if (n.isEmpty()) n = activePinGroup();
  if (n.isEmpty()) return {};
  n = cleanPinGroupName(n);
  QVariantMap groups;
  const QJsonObject g = pinGroupsJson(hostWatchObject(raw_));
  for (auto it = g.begin(); it != g.end(); ++it)
    groups.insert(cleanPinGroupName(it.key()), cleanPinGroupKeyList(it.value().toArray()));
  if (!groups.contains(n)) groups.insert(n, QStringList());
  setPinGroups(groups, n, true);
  return n;
}

bool SieansDocument::openAndRunDemo() const {
  if (path_.endsWith(QStringLiteral("open-and-run-gentl-qr.sieans"))) return true;
  const QJsonObject meta = raw_.value(QStringLiteral("meta")).toObject();
  if (meta.value(QStringLiteral("openAndRun")).toBool()) return true;
  return name() == QStringLiteral("打开即跑 · GenTL/Soft→二维码→TCP");
}

QStringList SieansDocument::filmstripPaths() const {
  QStringList out;
  for (const QVariant& v : raw_.value(QStringLiteral("filmstripPaths")).toArray().toVariantList()) {
    const QString p = v.toString().trimmed();
    if (!p.isEmpty()) out << p;
  }
  return out;
}

void SieansDocument::setFilmstripPaths(const QStringList& paths) {
  QJsonArray arr;
  for (const QString& p : paths) {
    const QString t = p.trimmed();
    if (!t.isEmpty()) arr.append(t);
  }
  raw_.insert(QStringLiteral("filmstripPaths"), arr);
}

bool SieansDocument::filmstripAutoSwitch() const {
  return raw_.value(QStringLiteral("filmstripAutoSwitch")).toBool(false);
}

void SieansDocument::setFilmstripAutoSwitch(bool on) {
  raw_.insert(QStringLiteral("filmstripAutoSwitch"), on);
}


QString SieansDocument::hostMode() const {
  return raw_.value(QStringLiteral("hostMode")).toString(QStringLiteral("正常生产"));
}

void SieansDocument::setHostMode(const QString& mode) {
  const QString t = mode.trimmed();
  raw_.insert(QStringLiteral("hostMode"), t.isEmpty() ? QStringLiteral("正常生产") : t);
}

QString SieansDocument::alarmPolicy() const {
  return raw_.value(QStringLiteral("alarmPolicy")).toString(QStringLiteral("on_ok"));
}

void SieansDocument::setAlarmPolicy(const QString& policy) {
  const QString t = policy.trimmed();
  raw_.insert(QStringLiteral("alarmPolicy"),
              t.isEmpty() ? QStringLiteral("on_ok") : t);
}


QStringList SieansDocument::varWatchKeys() const {
  QStringList out;
  for (const QVariant& v : raw_.value(QStringLiteral("varWatchKeys")).toArray().toVariantList()) {
    const QString t = v.toString().trimmed();
    if (!t.isEmpty() && !out.contains(t)) out << t;
  }
  return out;
}

void SieansDocument::setVarWatchKeys(const QStringList& keys) {
  QJsonArray arr;
  for (const QString& k : keys) {
    const QString t = k.trimmed();
    if (!t.isEmpty()) arr.append(t);
  }
  raw_.insert(QStringLiteral("varWatchKeys"), arr);
}


int SieansDocument::filmstripIndex() const {
  return raw_.value(QStringLiteral("filmstripIndex")).toInt(-1);
}

void SieansDocument::setFilmstripIndex(int index) {
  raw_.insert(QStringLiteral("filmstripIndex"), index);
}


QStringList SieansDocument::alarmHistory() const {
  QStringList out;
  for (const QVariant& v : raw_.value(QStringLiteral("alarmHistory")).toArray().toVariantList()) {
    const QString t = v.toString().trimmed();
    if (!t.isEmpty()) out << t;
  }
  return out;
}

void SieansDocument::setAlarmHistory(const QStringList& lines) {
  QJsonArray arr;
  int n = 0;
  for (const QString& line : lines) {
    const QString t = line.trimmed();
    if (t.isEmpty()) continue;
    arr.append(t);
    if (++n >= 40) break;
  }
  raw_.insert(QStringLiteral("alarmHistory"), arr);
}

bool SieansDocument::recipeLocked() const {
  return raw_.value(QStringLiteral("recipeLocked")).toBool(false);
}

void SieansDocument::setRecipeLocked(bool on) {
  raw_.insert(QStringLiteral("recipeLocked"), on);
}

bool SieansDocument::alarmLatched() const {
  return raw_.value(QStringLiteral("alarmLatched")).toBool(false);
}

QString SieansDocument::alarmLatchReason() const {
  return raw_.value(QStringLiteral("alarmLatchReason")).toString();
}

void SieansDocument::setAlarmLatched(bool on, const QString& reason) {
  raw_.insert(QStringLiteral("alarmLatched"), on);
  if (on) {
    const QString t = reason.trimmed();
    if (!t.isEmpty())
      raw_.insert(QStringLiteral("alarmLatchReason"), t.left(120));
  } else {
    raw_.insert(QStringLiteral("alarmLatchReason"), QString());
  }
}


QRect SieansDocument::propertyFloatGeometry() const {
  const QJsonObject o = raw_.value(QStringLiteral("propertyFloatGeometry")).toObject();
  if (o.isEmpty()) return {};
  const int w = o.value(QStringLiteral("w")).toInt(0);
  const int h = o.value(QStringLiteral("h")).toInt(0);
  if (w < 200 || h < 200) return {};
  return QRect(o.value(QStringLiteral("x")).toInt(0),
               o.value(QStringLiteral("y")).toInt(0), w, h);
}

void SieansDocument::setPropertyFloatGeometry(const QRect& r) {
  if (!r.isValid() || r.width() < 200 || r.height() < 200) return;
  QJsonObject o;
  o.insert(QStringLiteral("x"), r.x());
  o.insert(QStringLiteral("y"), r.y());
  o.insert(QStringLiteral("w"), r.width());
  o.insert(QStringLiteral("h"), r.height());
  raw_.insert(QStringLiteral("propertyFloatGeometry"), o);
}

FlowStep SieansDocument::stepFromJson(const QJsonObject& o) {
  FlowStep s;
  s.id = o.value(QStringLiteral("id")).toString();
  s.name = o.value(QStringLiteral("name")).toString();
  s.operation = o.value(QStringLiteral("operation")).toString();
  s.imageFrom = o.value(QStringLiteral("imageFrom")).toString();
  s.params = objectToMap(o.value(QStringLiteral("params")).toObject());
  const QJsonObject pos = o.value(QStringLiteral("position")).toObject();
  s.position = QPointF(pos.value(QStringLiteral("x")).toDouble(),
                       pos.value(QStringLiteral("y")).toDouble());
  s.runState = QStringLiteral("等待执行");
  return s;
}

QJsonObject SieansDocument::stepToJson(const FlowStep& s) {
  QJsonObject o;
  o.insert(QStringLiteral("id"), s.id);
  o.insert(QStringLiteral("name"), s.name);
  o.insert(QStringLiteral("operation"), s.operation);
  o.insert(QStringLiteral("imageFrom"), s.imageFrom);
  o.insert(QStringLiteral("params"), mapToObject(s.params));
  o.insert(QStringLiteral("position"),
           QJsonObject{{QStringLiteral("x"), s.position.x()},
                       {QStringLiteral("y"), s.position.y()}});
  return o;
}

FlowEdge SieansDocument::edgeFromJson(const QJsonObject& o) {
  FlowEdge e;
  e.id = o.value(QStringLiteral("id")).toString();
  e.from = o.value(QStringLiteral("from")).toString();
  e.to = o.value(QStringLiteral("to")).toString();
  e.fromPort = o.value(QStringLiteral("fromPort")).toString(QStringLiteral("bottom"));
  e.toPort = o.value(QStringLiteral("toPort")).toString(QStringLiteral("top"));
  e.when = o.value(QStringLiteral("when")).toString(QStringLiteral("always"));
  if (e.when.isEmpty()) e.when = QStringLiteral("always");
  if (e.id.isEmpty()) e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  return e;
}

QJsonObject SieansDocument::edgeToJson(const FlowEdge& e) {
  return QJsonObject{
      {QStringLiteral("id"), e.id},
      {QStringLiteral("from"), e.from},
      {QStringLiteral("to"), e.to},
      {QStringLiteral("fromPort"), e.fromPort},
      {QStringLiteral("toPort"), e.toPort},
      {QStringLiteral("when"), e.when.isEmpty() ? QStringLiteral("always") : e.when},
  };
}

SubflowDef SieansDocument::subflowFromJson(const QJsonObject& o) {
  SubflowDef d;
  d.id = o.value(QStringLiteral("id")).toString();
  d.name = o.value(QStringLiteral("name")).toString();
  d.outputNode = o.value(QStringLiteral("outputNode")).toString();
  d.variables = objectToMap(o.value(QStringLiteral("variables")).toObject());
  const QJsonObject sp = o.value(QStringLiteral("sourcePosition")).toObject();
  d.sourcePosition = QPointF(sp.value(QStringLiteral("x")).toDouble(80),
                             sp.value(QStringLiteral("y")).toDouble(80));
  for (const QJsonValue& v : o.value(QStringLiteral("steps")).toArray()) {
    FlowStep s = stepFromJson(v.toObject());
    if (!s.id.isEmpty()) d.steps.push_back(s);
  }
  for (const QJsonValue& v : o.value(QStringLiteral("edges")).toArray()) {
    FlowEdge e = edgeFromJson(v.toObject());
    if (!e.from.isEmpty() && !e.to.isEmpty()) d.edges.push_back(e);
  }
  return d;
}

QJsonObject SieansDocument::subflowToJson(const SubflowDef& d) {
  QJsonArray steps;
  for (const FlowStep& s : d.steps) steps.append(stepToJson(s));
  QJsonArray edges;
  for (const FlowEdge& e : d.edges) edges.append(edgeToJson(e));
  QJsonObject o;
  o.insert(QStringLiteral("id"), d.id);
  o.insert(QStringLiteral("name"), d.name);
  o.insert(QStringLiteral("outputNode"), d.outputNode);
  o.insert(QStringLiteral("variables"), mapToObject(d.variables));
  o.insert(QStringLiteral("sourcePosition"),
           QJsonObject{{QStringLiteral("x"), d.sourcePosition.x()},
                       {QStringLiteral("y"), d.sourcePosition.y()}});
  o.insert(QStringLiteral("steps"), steps);
  o.insert(QStringLiteral("edges"), edges);
  o.insert(QStringLiteral("version"), 2);
  return o;
}

const SubflowDef* SieansDocument::findSubflow(const QString& idOrName) const {
  for (const SubflowDef& d : subflows_)
    if (d.id == idOrName) return &d;
  for (const SubflowDef& d : subflows_)
    if (d.name == idOrName) return &d;
  return nullptr;
}

SubflowDef* SieansDocument::findSubflow(const QString& idOrName) {
  return const_cast<SubflowDef*>(
      static_cast<const SieansDocument*>(this)->findSubflow(idOrName));
}

bool SieansDocument::subflowIsReferenced(const QString& id) const {
  auto uses = [&](const QVector<FlowStep>& steps) {
    for (const FlowStep& s : steps) {
      if (s.operation != QLatin1String("subflow") &&
          s.operation != QLatin1String("loop"))
        continue;
      if (s.params.value(QStringLiteral("subflowId")).toString() == id)
        return true;
    }
    return false;
  };
  if (uses(steps_)) return true;
  for (const SubflowDef& d : subflows_) {
    if (uses(d.steps)) return true;
  }
  return false;
}


void SieansDocument::loadFromSubflow(const SubflowDef& d) {
  path_.clear();
  name_ = d.name;
  steps_ = d.steps;
  edges_ = d.edges;
  variables_ = d.variables;
  sourcePosition_ = d.sourcePosition;
  sourceConfig_.clear();
  commManager_.clear();
  flowIo_.clear();
  subflows_.clear();
  flows_.clear();
  activeFlowId_.clear();
  outputNode_.clear();
  raw_ = QJsonObject{{QStringLiteral("version"), 2}};
  ensureScheme();
}

SubflowDef SieansDocument::exportToSubflow(const QString& id, const QString& outputNode) const {
  SubflowDef d;
  d.id = id;
  d.name = name_;
  d.outputNode = outputNode;
  d.steps = steps_;
  d.edges = edges_;
  d.variables = variables_;
  d.sourcePosition = sourcePosition_;
  return d;
}



namespace {

QString newSchemeId() {
  return QUuid::createUuid().toString(QUuid::WithoutBraces);
}

QString remapStepId(const QString& id, const QHash<QString, QString>& stepMap) {
  if (id.isEmpty() || id == QLatin1String("source")) return id;
  return stepMap.value(id, id);
}

bool flowHasStep(const QVector<FlowStep>& steps, const QString& id) {
  if (id == QLatin1String("source")) return true;
  for (const FlowStep& s : steps)
    if (s.id == id) return true;
  return false;
}

}  // namespace

FlowDef SieansDocument::captureActiveFlow(const QString& name) const {
  FlowDef f;
  f.id = newSchemeId();
  f.name = name.isEmpty() ? QStringLiteral("流程1") : name;
  f.steps = steps_;
  f.edges = edges_;
  f.sourcePosition = sourcePosition_;
  f.sourceConfig = sourceConfig_;
  f.outputNode = outputNode_;
  f.io = flowIo_;
  f.runIntervalMs = runIntervalMs_;
  return f;
}

void SieansDocument::applyFlowToTop(const FlowDef& f) {
  steps_ = f.steps;
  edges_ = f.edges;
  sourcePosition_ = f.sourcePosition;
  sourceConfig_ = f.sourceConfig;
  outputNode_ = f.outputNode;
  flowIo_ = f.io;
  runIntervalMs_ = f.runIntervalMs;
}

const FlowDef* SieansDocument::findFlow(const QString& id) const {
  for (const FlowDef& f : flows_)
    if (f.id == id) return &f;
  return nullptr;
}

FlowDef* SieansDocument::findFlow(const QString& id) {
  return const_cast<FlowDef*>(static_cast<const SieansDocument*>(this)->findFlow(id));
}

void SieansDocument::ensureScheme() {
  if (!flows_.isEmpty()) {
    bool ok = false;
    for (const FlowDef& f : flows_) {
      if (f.id == activeFlowId_) {
        ok = true;
        break;
      }
    }
    if (!ok) activeFlowId_ = flows_.first().id;
    return;
  }
  FlowDef one = captureActiveFlow(QStringLiteral("流程1"));
  flows_.push_back(one);
  activeFlowId_ = one.id;
}

void SieansDocument::syncActiveIntoFlows() {
  ensureScheme();
  if (FlowDef* f = findFlow(activeFlowId_)) {
    const QString keepId = f->id;
    const QString keepName = f->name;
    const bool en = f->enabled;
    const int runs = f->runCount;
    const double last = f->lastElapsedMs;
    const QVariantMap card = f->cardPosition;
    const bool stopNg = f->stopOnNg;
    const int to = f->timeoutMs;
    *f = captureActiveFlow(keepName);
    f->id = keepId;
    f->name = keepName;
    f->enabled = en;
    f->runCount = runs;
    f->lastElapsedMs = last;
    f->cardPosition = card;
    f->stopOnNg = stopNg;
    f->timeoutMs = to;
    return;
  }
  FlowDef one = captureActiveFlow(QStringLiteral("流程1"));
  one.id = activeFlowId_.isEmpty() ? one.id : activeFlowId_;
  activeFlowId_ = one.id;
  flows_.push_back(one);
}

bool SieansDocument::activateFlow(const QString& flowId) {
  ensureScheme();
  syncActiveIntoFlows();
  FlowDef* target = findFlow(flowId);
  if (!target) return false;
  activeFlowId_ = flowId;
  applyFlowToTop(*target);
  resetCanvasUndo();
  return true;
}

FlowDef SieansDocument::addFlow(const QString& name) {
  ensureScheme();
  syncActiveIntoFlows();
  FlowDef f;
  f.id = newSchemeId();
  const int index = flows_.size();
  f.name = name.trimmed().isEmpty() ? QStringLiteral("流程%1").arg(index + 1)
                                    : name.trimmed().left(80);
  f.sourcePosition = QPointF(300, 40);
  f.cardPosition = QVariantMap{{QStringLiteral("x"), 80 + (index % 3) * 280},
                               {QStringLiteral("y"), 80 + (index / 3) * 200}};
  flows_.push_back(f);
  return f;
}

FlowDef SieansDocument::duplicateFlow(const QString& flowId, QString* error) {
  ensureScheme();
  syncActiveIntoFlows();
  const FlowDef* src = findFlow(flowId);
  if (!src) {
    if (error) *error = QStringLiteral("流程不存在");
    return {};
  }
  FlowDef copy = *src;
  copy.id = newSchemeId();
  copy.name = (src->name.isEmpty() ? QStringLiteral("流程") : src->name) +
              QStringLiteral(" 副本");
  copy.runCount = 0;
  copy.lastElapsedMs = 0;
  QHash<QString, QString> stepMap;
  for (const FlowStep& s : copy.steps) stepMap.insert(s.id, newSchemeId());
  for (FlowStep& s : copy.steps) {
    s.id = stepMap.value(s.id);
    s.imageFrom = remapStepId(s.imageFrom, stepMap);
    s.position += QPointF(40, 40);
  }
  QVector<FlowEdge> edges;
  for (FlowEdge e : copy.edges) {
    e.id = newSchemeId();
    e.from = remapStepId(e.from, stepMap);
    e.to = remapStepId(e.to, stepMap);
    if (!flowHasStep(copy.steps, e.to)) continue;
    if (e.from != QLatin1String("source") && !flowHasStep(copy.steps, e.from)) continue;
    edges.push_back(e);
  }
  copy.edges = edges;
  copy.outputNode = remapStepId(copy.outputNode, stepMap);
  const int idx = flows_.size();
  copy.cardPosition = QVariantMap{{QStringLiteral("x"), 80 + (idx % 3) * 280},
                                  {QStringLiteral("y"), 80 + (idx / 3) * 200}};
  flows_.push_back(copy);
  return copy;
}

bool SieansDocument::removeFlow(const QString& flowId, QString* error) {
  ensureScheme();
  syncActiveIntoFlows();
  if (flows_.size() <= 1) {
    if (error) *error = QStringLiteral("至少保留一个流程");
    return false;
  }
  QVector<FlowDef> kept;
  for (const FlowDef& f : flows_)
    if (f.id != flowId) kept.push_back(f);
  if (kept.size() == flows_.size()) {
    if (error) *error = QStringLiteral("流程不存在");
    return false;
  }
  flows_ = kept;
  if (activeFlowId_ == flowId) return activateFlow(flows_.first().id);
  return true;
}

bool SieansDocument::renameFlow(const QString& flowId, const QString& name) {
  ensureScheme();
  syncActiveIntoFlows();
  FlowDef* f = findFlow(flowId);
  if (!f) return false;
  const QString trimmed = name.trimmed();
  f->name = trimmed.isEmpty() ? QStringLiteral("未命名流程") : trimmed.left(80);
  return true;
}

QJsonObject SieansDocument::exportPrc(const QString& flowId, QString* error) const {
  FlowDef f;
  if (flowId == activeFlowId_ || (flows_.isEmpty() && flowId.isEmpty())) {
    const FlowDef* cur = findFlow(activeFlowId_);
    f = captureActiveFlow(cur ? cur->name : QStringLiteral("流程1"));
    if (cur) {
      f.id = cur->id;
      f.name = cur->name;
      f.enabled = cur->enabled;
      f.cardPosition = cur->cardPosition;
      f.stopOnNg = cur->stopOnNg;
      f.timeoutMs = cur->timeoutMs;
    } else if (!activeFlowId_.isEmpty()) {
      f.id = activeFlowId_;
    }
  } else if (const FlowDef* cur = findFlow(flowId)) {
    f = *cur;
  } else {
    if (error) *error = QStringLiteral("流程不存在");
    return {};
  }
  return QJsonObject{
      {QStringLiteral("format"), QStringLiteral("sieans.prc")},
      {QStringLiteral("version"), 1},
      {QStringLiteral("kind"), QStringLiteral("process")},
      {QStringLiteral("flow"), flowToJson(f)},
      {QStringLiteral("exportedFrom"),
       QJsonObject{{QStringLiteral("schemeId"),
                    raw_.value(QStringLiteral("id")).toString()},
                   {QStringLiteral("schemeName"), name_}}},
  };
}

bool SieansDocument::exportPrcToFile(const QString& flowId, const QString& path,
                                     QString* error) const {
  const QJsonObject obj = exportPrc(flowId, error);
  if (obj.isEmpty()) return false;
  QFile f(path);
  if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
    if (error) *error = QStringLiteral("无法写入: %1").arg(path);
    return false;
  }
  f.write(QJsonDocument(obj).toJson(QJsonDocument::Indented));
  return true;
}

FlowDef SieansDocument::importPrc(const QJsonObject& payload, QString* error) {
  ensureScheme();
  syncActiveIntoFlows();
  FlowDef flow;
  if (payload.contains(QStringLiteral("flow")) && payload.value(QStringLiteral("flow")).isObject()) {
    flow = flowFromJson(payload.value(QStringLiteral("flow")).toObject());
  } else if (payload.contains(QStringLiteral("steps"))) {
    flow = flowFromJson(payload);
    if (flow.name.isEmpty())
      flow.name = payload.value(QStringLiteral("name")).toString(QStringLiteral("导入流程"));
  } else {
    if (error) *error = QStringLiteral("无效的流程文件（.prc）");
    return {};
  }
  flow.id = newSchemeId();
  QHash<QString, QString> stepMap;
  for (const FlowStep& s : flow.steps) stepMap.insert(s.id, newSchemeId());
  for (FlowStep& s : flow.steps) {
    s.id = stepMap.value(s.id, newSchemeId());
    s.imageFrom = remapStepId(s.imageFrom, stepMap);
  }
  QVector<FlowEdge> edges;
  for (FlowEdge e : flow.edges) {
    e.id = newSchemeId();
    if (e.from != QLatin1String("source")) {
      if (!stepMap.contains(e.from)) continue;
      e.from = stepMap.value(e.from);
    }
    if (!stepMap.contains(e.to)) continue;
    e.to = stepMap.value(e.to);
    edges.push_back(e);
  }
  flow.edges = edges;
  flow.outputNode = remapStepId(flow.outputNode, stepMap);
  if (flow.name.trimmed().isEmpty()) flow.name = QStringLiteral("导入流程");
  flow.name = flow.name.left(80);
  flow.runCount = 0;
  flow.lastElapsedMs = 0;
  const int idx = flows_.size();
  flow.cardPosition = QVariantMap{{QStringLiteral("x"), 80 + (idx % 3) * 280},
                                  {QStringLiteral("y"), 80 + (idx / 3) * 200}};
  flows_.push_back(flow);
  return flow;
}

FlowDef SieansDocument::importPrcFromFile(const QString& path, QString* error) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly)) {
    if (error) *error = QStringLiteral("无法打开: %1").arg(path);
    return {};
  }
  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &pe);
  if (pe.error != QJsonParseError::NoError || !doc.isObject()) {
    if (error) *error = QStringLiteral("无效的流程文件（.prc）");
    return {};
  }
  return importPrc(doc.object(), error);
}

FlowDef SieansDocument::flowFromJson(const QJsonObject& o) {
  FlowDef f;
  f.id = o.value(QStringLiteral("id")).toString();
  f.name = o.value(QStringLiteral("name")).toString();
  f.outputNode = o.value(QStringLiteral("outputNode")).toString();
  f.enabled = o.value(QStringLiteral("enabled")).toBool(true);
  f.runIntervalMs = o.value(QStringLiteral("runIntervalMs")).toInt(0);
  f.stopOnNg = o.value(QStringLiteral("stopOnNg")).toBool(false);
  f.timeoutMs = o.value(QStringLiteral("timeoutMs")).toInt(0);
  f.runCount = o.value(QStringLiteral("runCount")).toInt(0);
  f.lastElapsedMs = o.value(QStringLiteral("lastElapsedMs")).toDouble(0);
  f.sourceConfig = objectToMap(o.value(QStringLiteral("sourceConfig")).toObject());
  f.io = objectToMap(o.value(QStringLiteral("io")).toObject());
  f.cardPosition = objectToMap(o.value(QStringLiteral("cardPosition")).toObject());
  const QJsonObject sp = o.value(QStringLiteral("sourcePosition")).toObject();
  f.sourcePosition = QPointF(sp.value(QStringLiteral("x")).toDouble(300),
                             sp.value(QStringLiteral("y")).toDouble(40));
  for (const QJsonValue& v : o.value(QStringLiteral("steps")).toArray()) {
    FlowStep s = stepFromJson(v.toObject());
    if (!s.id.isEmpty()) f.steps.push_back(s);
  }
  for (const QJsonValue& v : o.value(QStringLiteral("edges")).toArray()) {
    FlowEdge e = edgeFromJson(v.toObject());
    if (!e.from.isEmpty() && !e.to.isEmpty()) f.edges.push_back(e);
  }
  if (f.id.isEmpty()) f.id = newSchemeId();
  if (f.name.isEmpty()) f.name = QStringLiteral("流程1");
  return f;
}

QJsonObject SieansDocument::flowToJson(const FlowDef& f) {
  QJsonArray steps;
  for (const FlowStep& s : f.steps) steps.append(stepToJson(s));
  QJsonArray edges;
  for (const FlowEdge& e : f.edges) edges.append(edgeToJson(e));
  QJsonObject o;
  o.insert(QStringLiteral("id"), f.id);
  o.insert(QStringLiteral("name"), f.name);
  o.insert(QStringLiteral("outputNode"), f.outputNode);
  o.insert(QStringLiteral("steps"), steps);
  o.insert(QStringLiteral("edges"), edges);
  o.insert(QStringLiteral("sourcePosition"),
           QJsonObject{{QStringLiteral("x"), f.sourcePosition.x()},
                       {QStringLiteral("y"), f.sourcePosition.y()}});
  o.insert(QStringLiteral("sourceConfig"), mapToObject(f.sourceConfig));
  o.insert(QStringLiteral("io"), mapToObject(f.io));
  o.insert(QStringLiteral("cardPosition"), mapToObject(f.cardPosition));
  o.insert(QStringLiteral("enabled"), f.enabled);
  o.insert(QStringLiteral("runIntervalMs"), f.runIntervalMs);
  o.insert(QStringLiteral("stopOnNg"), f.stopOnNg);
  o.insert(QStringLiteral("timeoutMs"), f.timeoutMs);
  o.insert(QStringLiteral("runCount"), f.runCount);
  o.insert(QStringLiteral("lastElapsedMs"), f.lastElapsedMs);
  return o;
}

QStringList SieansDocument::schemeSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  SieansDocument doc;
  doc.seedGentlQrDemo();
  check("seed-flow-count", doc.flows().size() == 1, QString::number(doc.flows().size()));
  check("seed-active", !doc.activeFlowId().isEmpty());
  check("seed-name", !doc.flows().isEmpty() && doc.flows().first().name == QStringLiteral("流程1"),
        doc.flows().isEmpty() ? QStringLiteral("empty") : doc.flows().first().name);
  check("seed-has-locate", doc.findStep(QStringLiteral("loc1")) != nullptr);
  const int seedSteps = doc.steps().size();
  const int subN = doc.subflows().size();
  check("seed-subflows", subN >= 1, QString::number(subN));
  const QString firstId = doc.activeFlowId();

  const FlowDef added = doc.addFlow(QStringLiteral("流程2"));
  check("add-count", doc.flows().size() == 2, QString::number(doc.flows().size()));
  check("add-id", !added.id.isEmpty() && added.id != firstId);
  check("add-keeps-active", doc.activeFlowId() == firstId, doc.activeFlowId());

  check("activate-2", doc.activateFlow(added.id));
  check("switch-clears-main", doc.findStep(QStringLiteral("loc1")) == nullptr);
  check("activate-1", doc.activateFlow(firstId));
  check("switch-restores-locate", doc.findStep(QStringLiteral("loc1")) != nullptr);
  check("switch-step-count", doc.steps().size() == seedSteps,
        QStringLiteral("%1 vs %2").arg(doc.steps().size()).arg(seedSteps));

  QString err;
  const QJsonObject prc = doc.exportPrc(firstId, &err);
  check("export-prc", prc.value(QStringLiteral("format")).toString() == QLatin1String("sieans.prc"),
        err);
  const FlowDef imported = doc.importPrc(prc, &err);
  check("import-prc", !imported.id.isEmpty() && doc.flows().size() == 3, err);
  check("import-new-id", imported.id != firstId);
  check("import-has-steps", !imported.steps.isEmpty());
  bool remapped = true;
  for (const FlowStep& s : imported.steps) {
    if (s.id == QLatin1String("loc1")) remapped = false;
  }
  check("import-ids-remapped", remapped);
  check("import-keeps-subflows", doc.subflows().size() == subN,
        QString::number(doc.subflows().size()));

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (!tmp.isValid()) return fails;
  const QString sieansPath = tmp.filePath(QStringLiteral("multi.sieans"));
  const QString prcPath = tmp.filePath(QStringLiteral("flow.prc"));
  check("save-sieans", doc.saveToFile(sieansPath, &err), err);
  check("export-prc-file", doc.exportPrcToFile(firstId, prcPath, &err), err);

  SieansDocument loaded;
  check("load-sieans", loaded.loadFromFile(sieansPath, &err), err);
  check("load-flow-count", loaded.flows().size() == 3, QString::number(loaded.flows().size()));
  check("load-active", loaded.activeFlowId() == firstId, loaded.activeFlowId());
  check("load-locate", loaded.findStep(QStringLiteral("loc1")) != nullptr);
  check("load-subflows", loaded.subflows().size() == subN, QString::number(loaded.subflows().size()));

  SieansDocument legacySrc;
  legacySrc.seedGentlQrDemo();
  QJsonObject bare;
  bare.insert(QStringLiteral("name"), QStringLiteral("旧方案"));
  QJsonArray st;
  for (const FlowStep& s : legacySrc.steps()) st.append(stepToJson(s));
  QJsonArray ed;
  for (const FlowEdge& e : legacySrc.edges()) ed.append(edgeToJson(e));
  bare.insert(QStringLiteral("steps"), st);
  bare.insert(QStringLiteral("edges"), ed);
  const QString legacyPath = tmp.filePath(QStringLiteral("legacy.sieans"));
  {
    QFile f(legacyPath);
    const bool ok = f.open(QIODevice::WriteOnly | QIODevice::Truncate);
    check("legacy-write", ok);
    if (ok) f.write(QJsonDocument(bare).toJson(QJsonDocument::Indented));
  }
  SieansDocument leg;
  check("legacy-load", leg.loadFromFile(legacyPath, &err), err);
  check("legacy-migrates", leg.flows().size() == 1, QString::number(leg.flows().size()));
  check("legacy-steps", !leg.steps().isEmpty());
  QString err2;
  const QString outPath = tmp.filePath(QStringLiteral("legacy-saved.sieans"));
  check("legacy-resave", leg.saveToFile(outPath, &err2), err2);
  QJsonObject saved;
  {
    QFile f(outPath);
    const bool ok = f.open(QIODevice::ReadOnly);
    check("legacy-reread", ok);
    if (ok) saved = QJsonDocument::fromJson(f.readAll()).object();
  }
  check("compat-top-steps", saved.value(QStringLiteral("steps")).toArray().size() > 0);
  check("compat-writes-flows", saved.value(QStringLiteral("flows")).toArray().size() == 1);

  QString rmErr;
  check("remove-last-rejected", !leg.removeFlow(leg.activeFlowId(), &rmErr));
  check("import-prc-file", !loaded.importPrcFromFile(prcPath, &err).id.isEmpty(), err);
  check("import-file-count", loaded.flows().size() == 4, QString::number(loaded.flows().size()));
  return fails;
}

QStringList SieansDocument::pinGroupSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  SieansDocument empty;
  check("empty-no-groups", empty.pinGroupNames().isEmpty());
  check("empty-no-active", empty.activePinGroup().isEmpty());
  const int defaultN = empty.hostWatchKeys().size();
  check("empty-no-catalog-dump", defaultN == 0, QString::number(defaultN));

  SieansDocument seeded;
  seeded.seedGentlQrDemo();
  check("seed-active-qr", seeded.activePinGroup() == QStringLiteral("二维码链"),
        seeded.activePinGroup());
  const QStringList qrKeys{QStringLiteral("barcodeCount"), QStringLiteral("barcodeText"),
                           QStringLiteral("barcodeAll"), QStringLiteral("barcodeOk"),
                           QStringLiteral("passGate"), QStringLiteral("urlOk"),
                           QStringLiteral("formatted")};
  check("seed-qr-keys", seeded.hostWatchKeys() == qrKeys,
        seeded.hostWatchKeys().join(QLatin1Char(',')));
  check("seed-not-catalog", seeded.hostWatchKeys().size() == 7,
        QString::number(seeded.hostWatchKeys().size()));
  check("seed-has-gate-group",
        seeded.pinGroupKeys(QStringLiteral("门限")).contains(QStringLiteral("passGate")));

  SieansDocument doc;
  QVariantMap groups;
  groups.insert(QStringLiteral("定位"),
                QStringList{QStringLiteral("locateOk"), QStringLiteral("locateScore"),
                            QStringLiteral("locateOk"), QStringLiteral(" ")});
  groups.insert(QStringLiteral("测量"),
                QStringList{QStringLiteral("caliperMm"), QStringLiteral("measureMm")});
  groups.insert(QStringLiteral("  "), QStringList{QStringLiteral("passGate")});
  doc.setPinGroups(groups, QStringLiteral("测量"), true);
  check("count", doc.pinGroupNames().size() == 3, QString::number(doc.pinGroupNames().size()));
  check("unnamed", doc.pinGroupNames().contains(QStringLiteral("未命名")));
  check("active", doc.activePinGroup() == QStringLiteral("测量"), doc.activePinGroup());
  check("watch-from-active",
        doc.hostWatchKeys() == (QStringList{QStringLiteral("caliperMm"),
                                            QStringLiteral("measureMm")}),
        doc.hostWatchKeys().join(QLatin1Char(',')));
  check("dedup-keys",
        doc.pinGroupKeys(QStringLiteral("定位")) ==
            (QStringList{QStringLiteral("locateOk"), QStringLiteral("locateScore")}),
        doc.pinGroupKeys(QStringLiteral("定位")).join(QLatin1Char(',')));

  // Runtime-only watch edit must not rewrite saved pin groups.
  doc.setHostWatchKeys({QStringLiteral("hostResult"), QStringLiteral("hostMode")});
  check("runtime-watch-keys",
        doc.hostWatchKeys() == (QStringList{QStringLiteral("hostResult"),
                                            QStringLiteral("hostMode")}));
  check("runtime-keeps-groups", doc.pinGroupNames().size() == 3,
        QString::number(doc.pinGroupNames().size()));
  check("runtime-keeps-measure-keys",
        doc.pinGroupKeys(QStringLiteral("测量")) ==
            (QStringList{QStringLiteral("caliperMm"), QStringLiteral("measureMm")}),
        doc.pinGroupKeys(QStringLiteral("测量")).join(QLatin1Char(',')));
  check("runtime-keeps-active", doc.activePinGroup() == QStringLiteral("测量"),
        doc.activePinGroup());

  const QString act = doc.activatePinGroup(QStringLiteral("定位"));
  check("activate-name", act == QStringLiteral("定位"), act);
  check("activate-keys",
        doc.hostWatchKeys() == (QStringList{QStringLiteral("locateOk"),
                                            QStringLiteral("locateScore")}),
        doc.hostWatchKeys().join(QLatin1Char(',')));

  QString err;
  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (!tmp.isValid()) return fails;
  const QString path = tmp.filePath(QStringLiteral("pins.sieans"));
  check("save", doc.saveToFile(path, &err), err);
  SieansDocument loaded;
  check("load", loaded.loadFromFile(path, &err), err);
  check("round-count", loaded.pinGroupNames().size() == 3,
        QString::number(loaded.pinGroupNames().size()));
  check("round-active", loaded.activePinGroup() == QStringLiteral("定位"),
        loaded.activePinGroup());
  check("round-keys",
        loaded.hostWatchKeys() == (QStringList{QStringLiteral("locateOk"),
                                               QStringLiteral("locateScore")}),
        loaded.hostWatchKeys().join(QLatin1Char(',')));
  check("round-measure",
        loaded.pinGroupKeys(QStringLiteral("测量")).size() == 2,
        QString::number(loaded.pinGroupKeys(QStringLiteral("测量")).size()));

  const QString snakePath = tmp.filePath(QStringLiteral("snake.sieans"));
  {
    QJsonObject bag;
    bag.insert(QStringLiteral("name"), QStringLiteral("snake"));
    QJsonObject hw;
    QJsonObject pg;
    pg.insert(QStringLiteral("定位"), QJsonArray{QStringLiteral("locateOk")});
    hw.insert(QStringLiteral("pin_groups"), pg);
    hw.insert(QStringLiteral("active_pin_group"), QStringLiteral("定位"));
    bag.insert(QStringLiteral("hostWatch"), hw);
    QFile f(snakePath);
    const bool ok = f.open(QIODevice::WriteOnly | QIODevice::Truncate);
    check("snake-write", ok);
    if (ok) f.write(QJsonDocument(bag).toJson(QJsonDocument::Indented));
  }
  SieansDocument snake;
  check("snake-load", snake.loadFromFile(snakePath, &err), err);
  check("snake-names", snake.pinGroupNames() == QStringList{QStringLiteral("定位")},
        snake.pinGroupNames().join(QLatin1Char(',')));
  check("snake-active", snake.activePinGroup() == QStringLiteral("定位"),
        snake.activePinGroup());
  check("snake-keys-fallback",
        snake.hostWatchKeys() == QStringList{QStringLiteral("locateOk")},
        snake.hostWatchKeys().join(QLatin1Char(',')));

  const QString aliasPath = tmp.filePath(QStringLiteral("active-alias.sieans"));
  {
    QJsonObject bag;
    bag.insert(QStringLiteral("name"), QStringLiteral("alias"));
    QJsonObject hw;
    QJsonObject pg;
    pg.insert(QStringLiteral("二维码链"),
              QJsonArray{QStringLiteral("barcodeOk"), QStringLiteral("passGate")});
    pg.insert(QStringLiteral("门限"), QJsonArray{QStringLiteral("passGate")});
    hw.insert(QStringLiteral("pinGroups"), pg);
    hw.insert(QStringLiteral("active"), QStringLiteral("二维码链"));
    QJsonArray bloated;
    bloated.append(QStringLiteral("barcodeOk"));
    bloated.append(QStringLiteral("passGate"));
    bloated.append(QStringLiteral("locateOk"));
    bloated.append(QStringLiteral("defectsCount"));
    hw.insert(QStringLiteral("watchKeys"), bloated);
    bag.insert(QStringLiteral("hostWatch"), hw);
    QFile f(aliasPath);
    const bool ok = f.open(QIODevice::WriteOnly | QIODevice::Truncate);
    check("alias-write", ok);
    if (ok) f.write(QJsonDocument(bag).toJson(QJsonDocument::Indented));
  }
  SieansDocument alias;
  check("alias-load", alias.loadFromFile(aliasPath, &err), err);
  check("alias-active", alias.activePinGroup() == QStringLiteral("二维码链"),
        alias.activePinGroup());
  check("alias-group-keys",
        alias.pinGroupKeys(QStringLiteral("二维码链")) ==
            (QStringList{QStringLiteral("barcodeOk"), QStringLiteral("passGate")}),
        alias.pinGroupKeys(QStringLiteral("二维码链")).join(QLatin1Char(',')));

  const QString created = loaded.activatePinGroup(QStringLiteral("备用"));
  check("missing-creates", created == QStringLiteral("备用"), created);
  check("missing-empty-keys", loaded.pinGroupKeys(QStringLiteral("备用")).isEmpty());
  check("missing-in-names", loaded.pinGroupNames().contains(QStringLiteral("备用")));

  const QString ens = loaded.ensurePinGroup(QStringLiteral("测量"),
                                            {QStringLiteral("caliperMm"),
                                             QStringLiteral("caliperOk")});
  check("ensure-name", ens == QStringLiteral("测量"), ens);
  check("ensure-keys",
        loaded.pinGroupKeys(QStringLiteral("测量")) ==
            (QStringList{QStringLiteral("caliperMm"), QStringLiteral("caliperOk")}),
        loaded.pinGroupKeys(QStringLiteral("测量")).join(QLatin1Char(',')));
  // ensure does not rewrite the active group's visible watch keys
  check("ensure-no-watch-rewrite",
        loaded.activePinGroup() == QStringLiteral("备用") &&
            loaded.hostWatchKeys().isEmpty(),
        loaded.activePinGroup() + QLatin1Char('/') + loaded.hostWatchKeys().join(QLatin1Char(',')));
  return fails;
}


QJsonArray SieansDocument::recipesJson() const {
  return raw_.value(QStringLiteral("recipes")).toArray();
}

QString SieansDocument::activeRecipeId() const {
  return raw_.value(QStringLiteral("activeRecipeId")).toString();
}

QString SieansDocument::activeRecipeName() const {
  const QString rid = activeRecipeId();
  for (const QJsonValue& v : recipesJson()) {
    const QJsonObject o = v.toObject();
    if (o.value(QStringLiteral("id")).toString() == rid)
      return o.value(QStringLiteral("name")).toString(rid);
  }
  return {};
}

namespace {
QJsonObject stepRecipeSnapshot(const FlowStep& s) {
  return QJsonObject{
      {QStringLiteral("id"), s.id},
      {QStringLiteral("name"), s.name},
      {QStringLiteral("operation"), s.operation},
      {QStringLiteral("params"), mapToObject(s.params)},
      {QStringLiteral("imageFrom"), s.imageFrom},
  };
}

FlowStep* matchRecipeStep(QVector<FlowStep>& live, const QJsonObject& snap) {
  const QString op = snap.value(QStringLiteral("operation")).toString();
  const QString name = snap.value(QStringLiteral("name")).toString();
  const QString sid = snap.value(QStringLiteral("id")).toString();
  for (FlowStep& s : live) {
    if (s.operation == op && s.name == name) return &s;
  }
  if (!sid.isEmpty()) {
    for (FlowStep& s : live) {
      if (s.id == sid) return &s;
    }
  }
  for (FlowStep& s : live) {
    if (s.operation == op) return &s;
  }
  return nullptr;
}

void syncProductionRecipeField(QVector<FlowStep>& steps, const QString& name) {
  for (FlowStep& s : steps) {
    if (s.operation == QLatin1String("production_task"))
      s.params.insert(QStringLiteral("recipe"), name);
  }
}
}  // namespace

QVariantMap SieansDocument::captureRecipe(const QString& name, const QString& note,
                                          const QString& variant) {
  const QString when = QDateTime::currentDateTime().toString(QStringLiteral("yyyy-MM-dd HH:mm:ss"));
  QString nm = name.trimmed();
  if (nm.isEmpty()) nm = QStringLiteral("配方%1").arg(when);
  const QString var = variant.trimmed();
  QJsonArray snapSteps;
  for (const FlowStep& s : steps_) snapSteps.append(stepRecipeSnapshot(s));
  QJsonObject varsOut;
  for (auto it = variables_.begin(); it != variables_.end(); ++it) {
    if (it.value().typeId() == QMetaType::QVariantMap) {
      QVariantMap slim;
      const QVariantMap bucket = it.value().toMap();
      for (auto jt = bucket.begin(); jt != bucket.end(); ++jt) {
        if (jt.value().typeId() == QMetaType::QString) {
          const QString sv = jt.value().toString();
          if (sv.startsWith(QLatin1String("data:image/")) || sv.size() > 4096) continue;
        }
        slim.insert(jt.key(), jt.value());
      }
      if (!slim.isEmpty()) varsOut.insert(it.key(), mapToObject(slim));
    } else if (it.value().typeId() == QMetaType::QString) {
      const QString sv = it.value().toString();
      if (sv.startsWith(QLatin1String("data:image/")) || sv.size() > 4096) continue;
      varsOut.insert(it.key(), sv);
    } else {
      varsOut.insert(it.key(), QJsonValue::fromVariant(it.value()));
    }
  }
  const QString id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  QJsonObject snap;
  snap.insert(QStringLiteral("steps"), snapSteps);
  snap.insert(QStringLiteral("variables"), varsOut);
  snap.insert(QStringLiteral("productionRecipe"), nm);
  snap.insert(QStringLiteral("variant"), var);
  QJsonObject entry;
  entry.insert(QStringLiteral("id"), id);
  entry.insert(QStringLiteral("name"), nm);
  entry.insert(QStringLiteral("note"), note.trimmed());
  entry.insert(QStringLiteral("variant"), var);
  entry.insert(QStringLiteral("updatedAt"), when);
  entry.insert(QStringLiteral("stepCount"), snapSteps.size());
  entry.insert(QStringLiteral("snapshot"), snap);
  QJsonArray arr = recipesJson();
  arr.append(entry);
  raw_.insert(QStringLiteral("recipes"), arr);
  raw_.insert(QStringLiteral("activeRecipeId"), id);
  if (!var.isEmpty()) raw_.insert(QStringLiteral("activeRecipeVariant"), var);
  syncProductionRecipeField(steps_, nm);
  QVariantMap out = objectToMap(entry);
  out.insert(QStringLiteral("id"), id);
  out.insert(QStringLiteral("name"), nm);
  out.insert(QStringLiteral("stepCount"), snapSteps.size());
  return out;
}

QVariantMap SieansDocument::applyRecipe(const QString& recipeId, QString* error) {
  QVariantMap stats;
  const QString rid = recipeId.trimmed();
  QJsonObject entry;
  for (const QJsonValue& v : recipesJson()) {
    const QJsonObject o = v.toObject();
    if (o.value(QStringLiteral("id")).toString() == rid) {
      entry = o;
      break;
    }
  }
  if (entry.isEmpty()) {
    if (error) *error = QStringLiteral("配方不存在");
    return stats;
  }
  const QJsonObject snap = entry.value(QStringLiteral("snapshot")).toObject();
  const QJsonArray snapSteps = snap.value(QStringLiteral("steps")).toArray();
  int applied = 0, skipped = 0;
  for (const QJsonValue& v : snapSteps) {
    const QJsonObject row = v.toObject();
    FlowStep* target = matchRecipeStep(steps_, row);
    if (!target) {
      ++skipped;
      continue;
    }
    const QJsonObject params = row.value(QStringLiteral("params")).toObject();
    target->params = objectToMap(params);
    if (row.contains(QStringLiteral("imageFrom")))
      target->imageFrom = row.value(QStringLiteral("imageFrom")).toString();
    ++applied;
  }
  int varsApplied = 0;
  const QJsonObject varsIn = snap.value(QStringLiteral("variables")).toObject();
  if (!varsIn.isEmpty()) {
    const QVariantMap incoming = objectToMap(varsIn);
    for (auto it = incoming.begin(); it != incoming.end(); ++it) {
      if (it.value().typeId() == QMetaType::QVariantMap) {
        QVariantMap slot = variables_.value(it.key()).toMap();
        const QVariantMap bucket = it.value().toMap();
        for (auto jt = bucket.begin(); jt != bucket.end(); ++jt) {
          slot.insert(jt.key(), jt.value());
          ++varsApplied;
        }
        variables_.insert(it.key(), slot);
      } else {
        variables_.insert(it.key(), it.value());
        ++varsApplied;
      }
    }
  }
  const QString nm = entry.value(QStringLiteral("name")).toString();
  const QString var = entry.value(QStringLiteral("variant")).toString();
  raw_.insert(QStringLiteral("activeRecipeId"), rid);
  if (!var.isEmpty()) raw_.insert(QStringLiteral("activeRecipeVariant"), var);
  syncProductionRecipeField(steps_, nm);
  stats.insert(QStringLiteral("applied"), applied);
  stats.insert(QStringLiteral("skipped"), skipped);
  stats.insert(QStringLiteral("varsApplied"), varsApplied);
  stats.insert(QStringLiteral("name"), nm);
  stats.insert(QStringLiteral("id"), rid);
  stats.insert(QStringLiteral("variant"), var);
  return stats;
}

bool SieansDocument::deleteRecipe(const QString& recipeId) {
  const QString rid = recipeId.trimmed();
  if (rid.isEmpty()) return false;
  QJsonArray next;
  bool hit = false;
  for (const QJsonValue& v : recipesJson()) {
    const QJsonObject o = v.toObject();
    if (o.value(QStringLiteral("id")).toString() == rid) {
      hit = true;
      continue;
    }
    next.append(o);
  }
  if (!hit) return false;
  raw_.insert(QStringLiteral("recipes"), next);
  if (activeRecipeId() == rid) {
    raw_.insert(QStringLiteral("activeRecipeId"), QString());
  }
  return true;
}

QStringList SieansDocument::recipeSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  SieansDocument doc;
  FlowStep loc;
  loc.id = QStringLiteral("loc-1");
  loc.name = QStringLiteral("定位");
  loc.operation = QStringLiteral("locate");
  loc.params.insert(QStringLiteral("threshold"), 80);
  FlowStep meas;
  meas.id = QStringLiteral("meas-1");
  meas.name = QStringLiteral("测量");
  meas.operation = QStringLiteral("measure");
  meas.params.insert(QStringLiteral("minMm"), 10);
  doc.stepsMut() << loc << meas;
  QVariantMap vars;
  vars.insert(QStringLiteral("limit"), 3);
  doc.setVariables(vars);

  const QVariantMap a = doc.captureRecipe(QStringLiteral("A型"), QStringLiteral("初值"),
                                          QStringLiteral("A"));
  check("capture-a", a.value(QStringLiteral("id")).toString().size() >= 8 &&
                         doc.recipeCount() == 1 && doc.activeRecipeName() == QStringLiteral("A型"),
        doc.activeRecipeName());
  check("capture-count", a.value(QStringLiteral("stepCount")).toInt() == 2);

  doc.stepsMut()[0].params.insert(QStringLiteral("threshold"), 40);
  doc.stepsMut()[1].params.insert(QStringLiteral("minMm"), 99);
  doc.variablesMut().insert(QStringLiteral("limit"), 9);
  const QVariantMap b = doc.captureRecipe(QStringLiteral("B型"), QString(), QStringLiteral("B"));
  check("capture-b", doc.recipeCount() == 2 && doc.activeRecipeName() == QStringLiteral("B型"));

  QString err;
  const QVariantMap appliedA = doc.applyRecipe(a.value(QStringLiteral("id")).toString(), &err);
  check("apply-a-err", err.isEmpty(), err);
  check("apply-a-count", appliedA.value(QStringLiteral("applied")).toInt() == 2,
        QString::number(appliedA.value(QStringLiteral("applied")).toInt()));
  check("apply-a-params",
        doc.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 80 &&
            doc.steps().at(1).params.value(QStringLiteral("minMm")).toInt() == 10);
  check("apply-a-active", doc.activeRecipeId() == a.value(QStringLiteral("id")).toString());
  check("apply-a-vars", doc.variables().value(QStringLiteral("limit")).toInt() == 3,
        doc.variables().value(QStringLiteral("limit")).toString());

  const QVariantMap appliedB = doc.applyRecipe(b.value(QStringLiteral("id")).toString(), &err);
  check("apply-b", appliedB.value(QStringLiteral("applied")).toInt() == 2 &&
                       doc.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 40 &&
                       doc.steps().at(1).params.value(QStringLiteral("minMm")).toInt() == 99);

  // Match by operation+name when live ids differ from the snapshot.
  SieansDocument renamed;
  FlowStep loc2 = loc;
  loc2.id = QStringLiteral("loc-other");
  loc2.params.insert(QStringLiteral("threshold"), 1);
  FlowStep meas2 = meas;
  meas2.id = QStringLiteral("meas-other");
  meas2.params.insert(QStringLiteral("minMm"), 1);
  renamed.stepsMut() << loc2 << meas2;
  renamed.captureRecipe(QStringLiteral("名匹配"));
  renamed.stepsMut()[0].id = QStringLiteral("brand-new");
  renamed.stepsMut()[0].params.insert(QStringLiteral("threshold"), 7);
  const QString mid = renamed.recipesJson().first().toObject().value(QStringLiteral("id")).toString();
  const QVariantMap byName = renamed.applyRecipe(mid, &err);
  check("match-op-name", byName.value(QStringLiteral("applied")).toInt() == 2 &&
                             renamed.steps().at(0).params.value(QStringLiteral("threshold")).toInt() ==
                                 1,
        QString::number(renamed.steps().at(0).params.value(QStringLiteral("threshold")).toInt()));

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (tmp.isValid()) {
    const QString path = tmp.filePath(QStringLiteral("recipes.sieans"));
    QString se;
    check("save", doc.saveToFile(path, &se), se);
    SieansDocument loaded;
    QString le;
    check("load", loaded.loadFromFile(path, &le), le);
    check("load-count", loaded.recipeCount() == 2, QString::number(loaded.recipeCount()));
    check("load-active", loaded.activeRecipeName() == QStringLiteral("B型"),
          loaded.activeRecipeName());
    loaded.applyRecipe(a.value(QStringLiteral("id")).toString(), &err);
    check("load-apply-a",
          loaded.steps().size() >= 2 &&
              loaded.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 80);
  }

  QString missingErr;
  const QVariantMap miss = doc.applyRecipe(QStringLiteral("no-such"), &missingErr);
  check("missing", miss.isEmpty() && missingErr.contains(QStringLiteral("不存在")), missingErr);
  check("delete-b", doc.deleteRecipe(b.value(QStringLiteral("id")).toString()) &&
                        doc.recipeCount() == 1);
  check("delete-missing", !doc.deleteRecipe(b.value(QStringLiteral("id")).toString()));
  check("delete-a", doc.deleteRecipe(a.value(QStringLiteral("id")).toString()) &&
                        doc.recipeCount() == 0 && doc.activeRecipeId().isEmpty());
  return fails;
}


QString SieansDocument::activeRecipeVariant() const {
  return raw_.value(QStringLiteral("activeRecipeVariant")).toString();
}

QStringList SieansDocument::recipeVariants() const {
  QStringList out;
  for (const QJsonValue& v : recipesJson()) {
    const QString var = v.toObject().value(QStringLiteral("variant")).toString().trimmed();
    if (!var.isEmpty() && !out.contains(var)) out.append(var);
  }
  return out;
}

QString SieansDocument::firstRecipeIdForVariant(const QString& variant) const {
  const QString want = variant.trimmed();
  if (want.isEmpty()) return {};
  for (const QJsonValue& v : recipesJson()) {
    const QJsonObject o = v.toObject();
    if (o.value(QStringLiteral("variant")).toString().trimmed() == want)
      return o.value(QStringLiteral("id")).toString();
  }
  return {};
}

namespace {
const char kRollbackStack[] = "_recipeRollbackStack";
const char kRollbackSnap[] = "_recipeRollbackSnap";
constexpr int kRollbackCap = 16;

QJsonObject captureRecipeRollbackSnap(const SieansDocument& doc) {
  QJsonArray steps;
  for (const FlowStep& s : doc.steps()) steps.append(SieansDocument::stepToJson(s));
  QJsonObject o;
  o.insert(QStringLiteral("steps"), steps);
  o.insert(QStringLiteral("variables"), QJsonObject::fromVariantMap(doc.variables()));
  o.insert(QStringLiteral("activeRecipeId"), doc.activeRecipeId());
  o.insert(QStringLiteral("activeRecipeVariant"), doc.activeRecipeVariant());
  return o;
}
}  // namespace


QVariantMap SieansDocument::applyRecipeWithRollback(const QString& recipeId, QString* error) {
  const QJsonObject snap = captureRecipeRollbackSnap(*this);
  const QString beforeId = activeRecipeId();
  const QString beforeVar = activeRecipeVariant();
  const QVariantMap stats = applyRecipe(recipeId, error);
  if (stats.isEmpty()) return stats;
  QJsonObject entry;
  entry.insert(QStringLiteral("snapshot"), snap);
  entry.insert(QStringLiteral("recipeId"), recipeId);
  entry.insert(QStringLiteral("name"), stats.value(QStringLiteral("name")).toString());
  entry.insert(QStringLiteral("appliedAt"),
               QDateTime::currentDateTime().toString(QStringLiteral("yyyy-MM-dd HH:mm:ss")));
  entry.insert(QStringLiteral("beforeId"), beforeId);
  entry.insert(QStringLiteral("beforeVariant"), beforeVar);
  QJsonObject st;
  st.insert(QStringLiteral("applied"), stats.value(QStringLiteral("applied")).toInt());
  st.insert(QStringLiteral("skipped"), stats.value(QStringLiteral("skipped")).toInt());
  st.insert(QStringLiteral("varsApplied"), stats.value(QStringLiteral("varsApplied")).toInt());
  entry.insert(QStringLiteral("stats"), st);
  QJsonArray stack = raw_.value(QLatin1String(kRollbackStack)).toArray();
  if (stack.isEmpty()) {
    const QJsonObject legacy = raw_.value(QLatin1String(kRollbackSnap)).toObject();
    if (legacy.contains(QStringLiteral("snapshot"))) stack.append(legacy);
  }
  stack.append(entry);
  while (stack.size() > kRollbackCap) stack.removeAt(0);
  raw_.insert(QLatin1String(kRollbackStack), stack);
  raw_.insert(QLatin1String(kRollbackSnap), entry);
  QVariantMap out = stats;
  out.insert(QStringLiteral("rollbackReady"), true);
  out.insert(QStringLiteral("rollbackDepth"), stack.size());
  return out;
}

int SieansDocument::recipeRollbackDepth() const {
  const QJsonArray stack = raw_.value(QLatin1String(kRollbackStack)).toArray();
  int n = 0;
  for (const QJsonValue& v : stack) {
    if (v.toObject().value(QStringLiteral("snapshot")).isObject()) ++n;
  }
  if (n == 0) {
    const QJsonObject legacy = raw_.value(QLatin1String(kRollbackSnap)).toObject();
    if (legacy.value(QStringLiteral("snapshot")).isObject()) return 1;
  }
  return n;
}

QVariantMap SieansDocument::rollbackLastRecipe(QString* error) {
  QVariantMap stats;
  QJsonArray stack = raw_.value(QLatin1String(kRollbackStack)).toArray();
  QJsonObject bag;
  if (!stack.isEmpty()) {
    bag = stack.last().toObject();
    stack.removeLast();
    if (stack.isEmpty()) {
      raw_.remove(QLatin1String(kRollbackStack));
      raw_.remove(QLatin1String(kRollbackSnap));
    } else {
      raw_.insert(QLatin1String(kRollbackStack), stack);
      raw_.insert(QLatin1String(kRollbackSnap), stack.last());
    }
  } else {
    bag = raw_.value(QLatin1String(kRollbackSnap)).toObject();
    raw_.remove(QLatin1String(kRollbackSnap));
    raw_.remove(QLatin1String(kRollbackStack));
  }
  const QJsonObject snap = bag.value(QStringLiteral("snapshot")).toObject();
  if (snap.isEmpty()) {
    if (error) *error = QStringLiteral("没有可回滚的配方快照");
    stats.insert(QStringLiteral("ok"), false);
    return stats;
  }
  QVector<FlowStep> steps;
  for (const QJsonValue& v : snap.value(QStringLiteral("steps")).toArray()) {
    FlowStep s = stepFromJson(v.toObject());
    if (s.id.isEmpty()) continue;
    if (s.runState.isEmpty()) s.runState = QStringLiteral("等待执行");
    steps.push_back(s);
  }
  steps_ = steps;
  if (snap.contains(QStringLiteral("variables")))
    variables_ = snap.value(QStringLiteral("variables")).toObject().toVariantMap();
  raw_.insert(QStringLiteral("activeRecipeId"),
              snap.value(QStringLiteral("activeRecipeId")).toString());
  raw_.insert(QStringLiteral("activeRecipeVariant"),
              snap.value(QStringLiteral("activeRecipeVariant")).toString());
  syncActiveIntoFlows();
  stats.insert(QStringLiteral("ok"), true);
  stats.insert(QStringLiteral("rolledBack"), bag.value(QStringLiteral("name")).toString());
  stats.insert(QStringLiteral("recipeId"), bag.value(QStringLiteral("recipeId")).toString());
  stats.insert(QStringLiteral("rollbackDepth"), recipeRollbackDepth());
  stats.insert(QStringLiteral("remaining"), recipeRollbackDepth());
  stats.insert(QStringLiteral("steps"), steps_.size());
  return stats;
}

QVariantMap SieansDocument::applyRecipeVariant(const QString& variant, QString* error) {
  const QString id = firstRecipeIdForVariant(variant);
  if (id.isEmpty()) {
    if (error) *error = QStringLiteral("变体「%1」下无配方").arg(variant.trimmed());
    return {};
  }
  return applyRecipeWithRollback(id, error);
}

QVector<SieansDocument::RecipeLibrarySource> SieansDocument::discoverRecipeLibrary(
    const QString& root) {
  QVector<RecipeLibrarySource> out;
  QString base = root.trimmed();
  if (base.isEmpty()) base = workbenchRepoRoot();
  if (base.isEmpty()) return out;
  QStringList seen;
  auto addDir = [&](const QString& dir, const QString& kind, bool recursive) {
    if (!QDir(dir).exists()) return;
    QDir d(dir);
    const QFileInfoList files =
        recursive ? d.entryInfoList({QStringLiteral("*.sieans")}, QDir::Files, QDir::Name)
                  : d.entryInfoList({QStringLiteral("*.sieans")}, QDir::Files, QDir::Name);
    QFileInfoList all = files;
    if (recursive) {
      all = QDir(dir).entryInfoList({QStringLiteral("*.sieans")},
                                    QDir::Files, QDir::Name);
      // walk one extra level of subdirs, cap 40
      const QFileInfoList sub = QDir(dir).entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot);
      for (const QFileInfo& sd : sub)
        all += QDir(sd.absoluteFilePath())
                   .entryInfoList({QStringLiteral("*.sieans")}, QDir::Files, QDir::Name);
    }
    int added = 0;
    for (const QFileInfo& fi : all) {
      const QString rp = fi.canonicalFilePath();
      if (rp.isEmpty() || seen.contains(rp)) continue;
      seen.append(rp);
      RecipeLibrarySource s;
      s.path = rp;
      s.name = fi.completeBaseName();
      s.kind = (kind == QStringLiteral("工程") && fi.fileName().startsWith(QLatin1String("open-and-run")))
                   ? QStringLiteral("打开即跑")
                   : kind;
      out.append(s);
      ++added;
      if (recursive && added >= 40) break;
    }
  };
  addDir(base + QStringLiteral("/projects"), QStringLiteral("工程"), false);
  addDir(base + QStringLiteral("/projects/templates"), QStringLiteral("模板"), false);
  addDir(base + QStringLiteral("/data/native-desktop/projects"), QStringLiteral("本机库"), true);
  return out;
}

QStringList SieansDocument::recipeChangeoverSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  SieansDocument doc;
  FlowStep loc;
  loc.id = QStringLiteral("loc-1");
  loc.name = QStringLiteral("定位");
  loc.operation = QStringLiteral("locate");
  loc.params.insert(QStringLiteral("threshold"), 80);
  FlowStep meas;
  meas.id = QStringLiteral("meas-1");
  meas.name = QStringLiteral("测量");
  meas.operation = QStringLiteral("measure");
  meas.params.insert(QStringLiteral("minMm"), 10);
  doc.stepsMut() << loc << meas;
  QVariantMap vars;
  vars.insert(QStringLiteral("limit"), 3);
  doc.setVariables(vars);
  const QVariantMap a = doc.captureRecipe(QStringLiteral("A型"), QString(), QStringLiteral("A"));
  doc.stepsMut()[0].params.insert(QStringLiteral("threshold"), 40);
  doc.variablesMut().insert(QStringLiteral("limit"), 9);
  const QVariantMap b = doc.captureRecipe(QStringLiteral("B型"), QString(), QStringLiteral("B"));
  check("variants", doc.recipeVariants() == QStringList({QStringLiteral("A"), QStringLiteral("B")}),
        doc.recipeVariants().join(QLatin1Char(',')));
  check("first-a", doc.firstRecipeIdForVariant(QStringLiteral("A")) ==
                       a.value(QStringLiteral("id")).toString());
  check("empty-var", doc.firstRecipeIdForVariant(QStringLiteral("Z")).isEmpty());
  check("depth0", doc.recipeRollbackDepth() == 0);

  QString err;
  const QVariantMap appliedA = doc.applyRecipeWithRollback(a.value(QStringLiteral("id")).toString(),
                                                           &err);
  check("apply-a", err.isEmpty() && appliedA.value(QStringLiteral("applied")).toInt() == 2, err);
  check("apply-a-params",
        doc.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 80);
  check("depth1", doc.recipeRollbackDepth() == 1, QString::number(doc.recipeRollbackDepth()));
  check("active-a", doc.activeRecipeVariant() == QLatin1String("A"));

  err.clear();
  const QVariantMap appliedB = doc.applyRecipeVariant(QStringLiteral("B"), &err);
  check("apply-b-var", err.isEmpty() && appliedB.value(QStringLiteral("name")).toString() ==
                                             QStringLiteral("B型"),
        err);
  check("apply-b-params",
        doc.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 40);
  check("depth2", doc.recipeRollbackDepth() == 2);

  err.clear();
  const QVariantMap rb1 = doc.rollbackLastRecipe(&err);
  check("rollback1", err.isEmpty() && rb1.value(QStringLiteral("ok")).toBool(), err);
  check("rollback1-params",
        doc.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 80 &&
            doc.activeRecipeVariant() == QLatin1String("A"));
  check("depth-after1", doc.recipeRollbackDepth() == 1);

  err.clear();
  const QVariantMap rb2 = doc.rollbackLastRecipe(&err);
  check("rollback2", err.isEmpty() && rb2.value(QStringLiteral("ok")).toBool(), err);
  check("rollback2-params",
        doc.steps().at(0).params.value(QStringLiteral("threshold")).toInt() == 40 &&
            doc.variables().value(QStringLiteral("limit")).toInt() == 9 &&
            doc.activeRecipeVariant() == QLatin1String("B"));
  check("depth0-again", doc.recipeRollbackDepth() == 0);
  err.clear();
  const QVariantMap rb3 = doc.rollbackLastRecipe(&err);
  check("rollback-empty", !rb3.value(QStringLiteral("ok")).toBool() && !err.isEmpty());

  // isolation: a second seeded document is not mutated
  SieansDocument live;
  live.seedGentlQrDemo();
  const int liveN = live.steps().size();
  const int liveR = live.recipeCount();
  check("live-untouched", live.steps().size() == liveN && live.recipeRollbackDepth() == 0 &&
                              live.recipeCount() == liveR);

  const auto libs = discoverRecipeLibrary();
  check("library-scan", !libs.isEmpty(), QString::number(libs.size()));
  if (!libs.isEmpty()) {
    SieansDocument loaded;
    QString le;
    check("library-load", loaded.loadFromFile(libs.first().path, &le), le);
    check("library-has-steps", loaded.steps().size() > 0,
          QString::number(loaded.steps().size()));
    check("live-after-lib", live.steps().size() == liveN && live.recipeRollbackDepth() == 0);
  }
  return fails;
}


QVariantMap SieansDocument::globalTriggers() const {
  return objectToMap(raw_.value(QStringLiteral("globalTriggers")).toObject());
}

void SieansDocument::setGlobalTriggers(const QVariantMap& bag) {
  QVariantMap clean = bag;
  if (!clean.contains(QStringLiteral("events")))
    clean.insert(QStringLiteral("events"), QVariantList{});
  if (!clean.contains(QStringLiteral("strings")))
    clean.insert(QStringLiteral("strings"), QVariantList{});
  raw_.insert(QStringLiteral("globalTriggers"), mapToObject(clean));
}

int SieansDocument::stringTriggerCount() const {
  return globalTriggers().value(QStringLiteral("strings")).toList().size();
}

namespace {
QString normalizeTriggerCommand(const QString& raw) {
  const QString t = raw.trimmed();
  if (t.isEmpty()) return {};
  static const struct {
    const char* from;
    const char* to;
  } kMap[] = {
      {"run", "执行·单次"},
      {"run_once", "执行·单次"},
      {"once", "执行·单次"},
      {"执行", "执行·单次"},
      {"continuous", "执行·连续"},
      {"run_continuous", "执行·连续"},
      {"stop", "执行·停止"},
      {"pause", "执行·暂停"},
      {"resume", "执行·继续"},
      {"continue", "执行·继续"},
      {"save", "方案保存"},
      {"save_as", "方案另存"},
      {"reset", "复位"},
      {"alarm", "状态·报警"},
      {"clear_alarm", "状态·清除报警"},
      {"注入 RUN", "注入·RUN"},
      {"注入RUN", "注入·RUN"},
      {"注入 STOP", "注入·STOP"},
      {"注入STOP", "注入·STOP"},
  };
  for (const auto& m : kMap) {
    if (t.compare(QLatin1String(m.from), Qt::CaseInsensitive) == 0)
      return QString::fromUtf8(m.to);
  }
  return t;
}

bool triggerRowEnabled(const QVariantMap& row) {
  if (row.contains(QStringLiteral("enabled")) && !row.value(QStringLiteral("enabled")).toBool())
    return false;
  return true;
}

bool matchStringTriggerRow(const QString& text, const QVariantMap& row) {
  const QString mode = row.value(QStringLiteral("match")).toString();
  if (mode == QLatin1String("equals") || mode == QLatin1String("contains") ||
      mode == QLatin1String("partial") || mode == QLatin1String("full")) {
    const QString needle = row.value(QStringLiteral("pattern"),
                                     row.value(QStringLiteral("event")))
                               .toString();
    if (needle.isEmpty()) return false;
    if (mode == QLatin1String("equals") || mode == QLatin1String("full"))
      return needle == text;
    return text.contains(needle);
  }
  const QString needle = row.value(QStringLiteral("event"),
                                   row.value(QStringLiteral("match"),
                                            row.value(QStringLiteral("pattern"))))
                             .toString();
  if (needle.isEmpty()) return false;
  const bool partial = row.contains(QStringLiteral("partial"))
                           ? row.value(QStringLiteral("partial")).toBool()
                           : true;
  return partial ? text.contains(needle) : (needle == text);
}

void appendCommandsFromRow(QVector<QVariantMap>& out, const QVariantMap& row,
                           const QString& source, const QString& match) {
  auto push = [&](const QString& typ, const QString& cfg) {
    const QString mapped = normalizeTriggerCommand(typ);
    if (mapped.isEmpty()) return;
    QVariantMap cmd;
    cmd.insert(QStringLiteral("type"), mapped);
    cmd.insert(QStringLiteral("config"), cfg);
    cmd.insert(QStringLiteral("source"), source);
    cmd.insert(QStringLiteral("match"), match);
    out.push_back(cmd);
  };
  const QString ctype = row.value(QStringLiteral("commandType"),
                                  row.value(QStringLiteral("command")))
                            .toString();
  if (!ctype.isEmpty())
    push(ctype, row.value(QStringLiteral("config")).toString());
  for (const QVariant& c : row.value(QStringLiteral("commands")).toList()) {
    const QVariantMap m = c.toMap();
    const QString action = m.value(QStringLiteral("action"),
                                   m.value(QStringLiteral("type")))
                               .toString()
                               .trimmed();
    if (action.isEmpty() || action == QLatin1String("log")) continue;
    const QString cfg = m.value(QStringLiteral("config"),
                                m.value(QStringLiteral("target"),
                                        m.value(QStringLiteral("text"))))
                            .toString();
    push(action, cfg);
  }
}
}  // namespace

QString SieansDocument::addStringTrigger(const QString& pattern, const QString& commandType,
                                         bool partial, bool enabled) {
  const QString needle = pattern.trimmed();
  const QString typ = normalizeTriggerCommand(commandType);
  if (needle.isEmpty() || typ.isEmpty()) return {};
  QVariantMap bag = globalTriggers();
  QVariantList strings = bag.value(QStringLiteral("strings")).toList();
  QVariantMap row;
  row.insert(QStringLiteral("event"), needle);
  row.insert(QStringLiteral("pattern"), needle);
  row.insert(QStringLiteral("commandType"), typ);
  row.insert(QStringLiteral("partial"), partial);
  row.insert(QStringLiteral("enabled"), enabled);
  strings.append(row);
  bag.insert(QStringLiteral("strings"), strings);
  if (!bag.contains(QStringLiteral("events")))
    bag.insert(QStringLiteral("events"), QVariantList{});
  setGlobalTriggers(bag);
  return needle;
}

QVector<QVariantMap> SieansDocument::collectStringCommands(const QString& received) const {
  QVector<QVariantMap> out;
  const QString text = received;
  if (text.isEmpty()) return out;
  const QVariantList strings =
      globalTriggers().value(QStringLiteral("strings")).toList();
  for (const QVariant& v : strings) {
    const QVariantMap row = v.toMap();
    if (!triggerRowEnabled(row)) continue;
    if (!matchStringTriggerRow(text, row)) continue;
    const QString needle = row.value(QStringLiteral("pattern"),
                                     row.value(QStringLiteral("event"),
                                              row.value(QStringLiteral("match"))))
                               .toString();
    appendCommandsFromRow(out, row, QStringLiteral("string"), needle);
  }
  return out;
}


int SieansDocument::eventTriggerCount() const {
  return globalTriggers().value(QStringLiteral("events")).toList().size();
}

QString SieansDocument::addEventTrigger(const QString& eventName, const QString& commandType,
                                        bool enabled) {
  const QString ev = eventName.trimmed();
  const QString typ = normalizeTriggerCommand(commandType);
  if (ev.isEmpty() || typ.isEmpty()) return {};
  QVariantMap bag = globalTriggers();
  QVariantList events = bag.value(QStringLiteral("events")).toList();
  QVariantMap row;
  row.insert(QStringLiteral("event"), ev);
  row.insert(QStringLiteral("commandType"), typ);
  row.insert(QStringLiteral("enabled"), enabled);
  events.append(row);
  bag.insert(QStringLiteral("events"), events);
  if (!bag.contains(QStringLiteral("strings")))
    bag.insert(QStringLiteral("strings"), QVariantList{});
  setGlobalTriggers(bag);
  return ev;
}

QVector<QVariantMap> SieansDocument::collectEventCommands(const QString& eventName) const {
  QVector<QVariantMap> out;
  const QString name = eventName.trimmed();
  if (name.isEmpty()) return out;
  const QVariantList events =
      globalTriggers().value(QStringLiteral("events")).toList();
  for (const QVariant& v : events) {
    const QVariantMap row = v.toMap();
    if (!triggerRowEnabled(row)) continue;
    if (row.value(QStringLiteral("event")).toString().trimmed() != name) continue;
    appendCommandsFromRow(out, row, QStringLiteral("event"), name);
  }
  for (QVariantMap& cmd : out) cmd.insert(QStringLiteral("event"), name);
  return out;
}

QStringList SieansDocument::triggerEventSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  auto typesOf = [](const QVector<QVariantMap>& cmds) {
    QStringList t;
    for (const QVariantMap& c : cmds) t << c.value(QStringLiteral("type")).toString();
    return t;
  };

  SieansDocument doc;
  check("empty", doc.eventTriggerCount() == 0);
  check("no-match", doc.collectEventCommands(QStringLiteral("流程开始")).isEmpty());
  check("add-start",
        doc.addEventTrigger(QStringLiteral("流程开始"), QStringLiteral("状态·报警")) ==
            QStringLiteral("流程开始"));
  check("add-end",
        !doc.addEventTrigger(QStringLiteral("流程结束"), QStringLiteral("stop")).isEmpty());
  check("add-ng",
        !doc.addEventTrigger(QStringLiteral("流程NG"), QStringLiteral("状态·报警")).isEmpty());
  check("count3", doc.eventTriggerCount() == 3, QString::number(doc.eventTriggerCount()));

  const auto start = doc.collectEventCommands(QStringLiteral("流程开始"));
  check("match-start", typesOf(start).contains(QStringLiteral("状态·报警")),
        typesOf(start).join(QLatin1Char(',')));
  const auto end = doc.collectEventCommands(QStringLiteral("流程结束"));
  check("match-end", typesOf(end).contains(QStringLiteral("执行·停止")),
        typesOf(end).join(QLatin1Char(',')));
  const auto ng = doc.collectEventCommands(QStringLiteral("流程NG"));
  check("match-ng", typesOf(ng).contains(QStringLiteral("状态·报警")),
        typesOf(ng).join(QLatin1Char(',')));
  check("no-camera", doc.collectEventCommands(QStringLiteral("相机连通")).isEmpty());

  QVariantMap bag = doc.globalTriggers();
  QVariantList events = bag.value(QStringLiteral("events")).toList();
  QVariantMap disabled;
  disabled.insert(QStringLiteral("event"), QStringLiteral("流程开始"));
  disabled.insert(QStringLiteral("commandType"), QStringLiteral("执行·连续"));
  disabled.insert(QStringLiteral("enabled"), false);
  events.append(disabled);
  QVariantMap seedRow;
  seedRow.insert(QStringLiteral("event"), QStringLiteral("流程结束"));
  QVariantMap cmd;
  cmd.insert(QStringLiteral("action"), QStringLiteral("alarm"));
  seedRow.insert(QStringLiteral("commands"), QVariantList{cmd});
  events.append(seedRow);
  bag.insert(QStringLiteral("events"), events);
  doc.setGlobalTriggers(bag);
  const auto start2 = doc.collectEventCommands(QStringLiteral("流程开始"));
  check("disabled-skipped", !typesOf(start2).contains(QStringLiteral("执行·连续")),
        typesOf(start2).join(QLatin1Char(',')));
  const auto end2 = doc.collectEventCommands(QStringLiteral("流程结束"));
  check("seed-schema", typesOf(end2).contains(QStringLiteral("状态·报警")),
        typesOf(end2).join(QLatin1Char(',')));

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (tmp.isValid()) {
    const QString path = tmp.filePath(QStringLiteral("events.sieans"));
    QString se;
    check("save", doc.saveToFile(path, &se), se);
    SieansDocument loaded;
    QString le;
    check("load", loaded.loadFromFile(path, &le), le);
    check("load-count", loaded.eventTriggerCount() == doc.eventTriggerCount(),
          QString::number(loaded.eventTriggerCount()));
    check("load-match",
          !loaded.collectEventCommands(QStringLiteral("流程NG")).isEmpty());
  }

  SieansDocument live;
  live.seedGentlQrDemo();
  check("live-untouched", live.eventTriggerCount() == 0 && live.stringTriggerCount() == 0);
  return fails;
}

QStringList SieansDocument::triggerSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  SieansDocument doc;
  check("empty-seed", doc.stringTriggerCount() == 0);
  check("no-match-empty", doc.collectStringCommands(QStringLiteral("RUN")).isEmpty());
  check("add-run", doc.addStringTrigger(QStringLiteral("RUN"), QStringLiteral("执行·单次")) ==
                       QLatin1String("RUN"));
  check("add-stop", !doc.addStringTrigger(QStringLiteral("STOP"), QStringLiteral("stop")).isEmpty());
  check("add-go", !doc.addStringTrigger(QStringLiteral("GO"), QStringLiteral("continuous")).isEmpty());
  check("count3", doc.stringTriggerCount() == 3, QString::number(doc.stringTriggerCount()));

  auto typesOf = [](const QVector<QVariantMap>& cmds) {
    QStringList t;
    for (const QVariantMap& c : cmds) t << c.value(QStringLiteral("type")).toString();
    return t;
  };
  const QVector<QVariantMap> exact = doc.collectStringCommands(QStringLiteral("RUN"));
  check("match-run", typesOf(exact).contains(QStringLiteral("执行·单次")),
        typesOf(exact).join(QLatin1Char(',')));
  const QVector<QVariantMap> part = doc.collectStringCommands(QStringLiteral("please RUN now"));
  check("partial-run", typesOf(part).contains(QStringLiteral("执行·单次")));
  const QVector<QVariantMap> stop = doc.collectStringCommands(QStringLiteral("STOP"));
  check("match-stop", typesOf(stop).contains(QStringLiteral("执行·停止")),
        typesOf(stop).join(QLatin1Char(',')));
  const QVector<QVariantMap> go = doc.collectStringCommands(QStringLiteral("GO-1"));
  check("match-cont", typesOf(go).contains(QStringLiteral("执行·连续")),
        typesOf(go).join(QLatin1Char(',')));
  check("no-match", doc.collectStringCommands(QStringLiteral("IDLE")).isEmpty());

  // equals mode must not fire on a longer payload
  QVariantMap bag = doc.globalTriggers();
  QVariantList strings = bag.value(QStringLiteral("strings")).toList();
  QVariantMap eq;
  eq.insert(QStringLiteral("match"), QStringLiteral("equals"));
  eq.insert(QStringLiteral("pattern"), QStringLiteral("PING"));
  eq.insert(QStringLiteral("commandType"), QStringLiteral("执行·停止"));
  eq.insert(QStringLiteral("enabled"), true);
  strings.append(eq);
  QVariantMap disabled;
  disabled.insert(QStringLiteral("pattern"), QStringLiteral("MAGIC"));
  disabled.insert(QStringLiteral("commandType"), QStringLiteral("执行·单次"));
  disabled.insert(QStringLiteral("enabled"), false);
  disabled.insert(QStringLiteral("partial"), true);
  strings.append(disabled);
  bag.insert(QStringLiteral("strings"), strings);
  doc.setGlobalTriggers(bag);
  check("equals-hit", !doc.collectStringCommands(QStringLiteral("PING")).isEmpty());
  check("equals-miss", doc.collectStringCommands(QStringLiteral("PING-ACK")).isEmpty());
  check("disabled", doc.collectStringCommands(QStringLiteral("MAGIC")).isEmpty());

  // seed-schema commands[]
  QVariantMap seedRow;
  seedRow.insert(QStringLiteral("match"), QStringLiteral("contains"));
  seedRow.insert(QStringLiteral("pattern"), QStringLiteral("ACK"));
  QVariantMap cmd;
  cmd.insert(QStringLiteral("action"), QStringLiteral("stop"));
  seedRow.insert(QStringLiteral("commands"), QVariantList{cmd});
  strings = doc.globalTriggers().value(QStringLiteral("strings")).toList();
  strings.append(seedRow);
  bag = doc.globalTriggers();
  bag.insert(QStringLiteral("strings"), strings);
  doc.setGlobalTriggers(bag);
  const QVector<QVariantMap> ack = doc.collectStringCommands(QStringLiteral("peer ACK ok"));
  check("seed-schema", typesOf(ack).contains(QStringLiteral("执行·停止")),
        typesOf(ack).join(QLatin1Char(',')));

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (tmp.isValid()) {
    const QString path = tmp.filePath(QStringLiteral("triggers.sieans"));
    QString se;
    check("save", doc.saveToFile(path, &se), se);
    SieansDocument loaded;
    QString le;
    check("load", loaded.loadFromFile(path, &le), le);
    check("load-count", loaded.stringTriggerCount() == doc.stringTriggerCount(),
          QString::number(loaded.stringTriggerCount()));
    check("load-match", !loaded.collectStringCommands(QStringLiteral("RUN")).isEmpty());
  }
  return fails;
}

SieansDocument::CanvasSnap SieansDocument::captureCanvasSnap(const QString& label) const {
  CanvasSnap s;
  s.label = label;
  s.steps = steps_;
  for (FlowStep& st : s.steps) st.runState.clear();
  s.edges = edges_;
  s.sourcePosition = sourcePosition_;
  s.sourceConfig = sourceConfig_;
  s.outputNode = outputNode_;
  return s;
}

void SieansDocument::restoreCanvasSnap(const CanvasSnap& snap) {
  steps_ = snap.steps;
  for (FlowStep& st : steps_) {
    if (st.runState.isEmpty()) st.runState = QStringLiteral("等待执行");
  }
  edges_ = snap.edges;
  sourcePosition_ = snap.sourcePosition;
  sourceConfig_ = snap.sourceConfig;
  outputNode_ = snap.outputNode;
  syncActiveIntoFlows();
}

bool SieansDocument::canvasSnapEquals(const CanvasSnap& a, const CanvasSnap& b) {
  if (a.steps.size() != b.steps.size() || a.edges.size() != b.edges.size())
    return false;
  if (a.sourcePosition != b.sourcePosition || a.outputNode != b.outputNode)
    return false;
  if (a.sourceConfig != b.sourceConfig) return false;
  for (int i = 0; i < a.steps.size(); ++i) {
    const FlowStep& l = a.steps[i];
    const FlowStep& r = b.steps[i];
    if (l.id != r.id || l.name != r.name || l.operation != r.operation ||
        l.imageFrom != r.imageFrom || l.position != r.position || l.params != r.params)
      return false;
  }
  for (int i = 0; i < a.edges.size(); ++i) {
    const FlowEdge& l = a.edges[i];
    const FlowEdge& r = b.edges[i];
    if (l.id != r.id || l.from != r.from || l.to != r.to || l.fromPort != r.fromPort ||
        l.toPort != r.toPort || l.when != r.when)
      return false;
  }
  return true;
}

void SieansDocument::resetCanvasUndo() {
  canvas_history_.clear();
  canvas_history_.push_back(captureCanvasSnap(QStringLiteral("打开")));
  canvas_index_ = 0;
  canvas_clean_index_ = 0;
}

void SieansDocument::markCanvasUndoClean() {
  canvas_clean_index_ = canvas_index_;
}

bool SieansDocument::canvasUndoAtClean() const {
  return canvas_clean_index_ >= 0 && canvas_index_ == canvas_clean_index_;
}

void SieansDocument::commitCanvasUndo(const QString& label) {
  if (canvas_history_.isEmpty()) resetCanvasUndo();
  const CanvasSnap now = captureCanvasSnap(label);
  if (canvasSnapEquals(now, canvas_history_.at(canvas_index_))) return;
  if (canvas_index_ + 1 < canvas_history_.size())
    canvas_history_ = canvas_history_.mid(0, canvas_index_ + 1);
  canvas_history_.push_back(now);
  while (canvas_history_.size() > 31) {
    canvas_history_.removeFirst();
    if (canvas_index_ > 0) --canvas_index_;
    if (canvas_clean_index_ > 0)
      --canvas_clean_index_;
    else
      canvas_clean_index_ = -1;
  }
  canvas_index_ = canvas_history_.size() - 1;
}

bool SieansDocument::undoCanvas() {
  if (canvas_history_.isEmpty()) resetCanvasUndo();
  if (canvas_index_ <= 0) return false;
  --canvas_index_;
  restoreCanvasSnap(canvas_history_.at(canvas_index_));
  return true;
}

bool SieansDocument::redoCanvas() {
  if (canvas_history_.isEmpty()) return false;
  if (canvas_index_ + 1 >= canvas_history_.size()) return false;
  ++canvas_index_;
  restoreCanvasSnap(canvas_history_.at(canvas_index_));
  return true;
}

int SieansDocument::canvasUndoDepth() const {
  return canvas_index_;
}

int SieansDocument::canvasRedoDepth() const {
  if (canvas_history_.isEmpty()) return 0;
  return canvas_history_.size() - 1 - canvas_index_;
}

QString SieansDocument::canvasUndoLabel() const {
  if (canvas_index_ <= 0 || canvas_index_ >= canvas_history_.size()) return {};
  return canvas_history_.at(canvas_index_).label;
}

QString SieansDocument::canvasRedoLabel() const {
  if (canvas_index_ + 1 >= canvas_history_.size()) return {};
  return canvas_history_.at(canvas_index_ + 1).label;
}

QStringList SieansDocument::canvasUndoSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  SieansDocument doc;
  doc.seedGentlQrDemo();
  const int n0 = doc.steps().size();
  const int e0 = doc.edges().size();
  check("seed-baseline", doc.canvasUndoDepth() == 0 && doc.canvasRedoDepth() == 0,
        QStringLiteral("undo=%1 redo=%2").arg(doc.canvasUndoDepth()).arg(doc.canvasRedoDepth()));
  check("seed-clean", doc.canvasUndoAtClean());
  check("undo-empty", !doc.undoCanvas());
  check("redo-empty", !doc.redoCanvas());

  FlowStep s;
  s.id = QStringLiteral("undo-tmp");
  s.name = QStringLiteral("撤销测");
  s.operation = QStringLiteral("cloud_measure");
  s.position = QPointF(12, 24);
  doc.stepsMut().push_back(s);
  doc.commitCanvasUndo(QStringLiteral("添加模块"));
  check("add-commit", doc.canvasUndoDepth() == 1 && doc.steps().size() == n0 + 1,
        QStringLiteral("depth=%1 steps=%2").arg(doc.canvasUndoDepth()).arg(doc.steps().size()));
  check("add-dirty", !doc.canvasUndoAtClean());

  // identical commit is a no-op
  doc.commitCanvasUndo(QStringLiteral("重复"));
  check("noop-commit", doc.canvasUndoDepth() == 1);

  FlowEdge e;
  e.id = QStringLiteral("undo-edge");
  e.from = QStringLiteral("source");
  e.to = QStringLiteral("undo-tmp");
  doc.edgesMut().push_back(e);
  doc.commitCanvasUndo(QStringLiteral("连线"));
  check("wire-commit", doc.edges().size() == e0 + 1);

  if (FlowStep* st = doc.findStep(QStringLiteral("undo-tmp"))) {
    st->position = QPointF(90, 110);
    st->params.insert(QStringLiteral("roiX"), 7);
    doc.commitCanvasUndo(QStringLiteral("移动参数"));
  }
  check("param-commit", doc.findStep(QStringLiteral("undo-tmp")) &&
                            doc.findStep(QStringLiteral("undo-tmp"))->params.value(QStringLiteral("roiX")).toInt() == 7);

  check("undo-param", doc.undoCanvas());
  const FlowStep* afterParam = doc.findStep(QStringLiteral("undo-tmp"));
  check("param-restored", afterParam && afterParam->position == QPointF(12, 24) &&
                              afterParam->params.value(QStringLiteral("roiX")).toInt() != 7);
  check("redo-param", doc.redoCanvas());
  check("param-redone", doc.findStep(QStringLiteral("undo-tmp")) &&
                            doc.findStep(QStringLiteral("undo-tmp"))->params.value(QStringLiteral("roiX")).toInt() == 7);

  check("undo-param2", doc.undoCanvas());
  check("undo-wire", doc.undoCanvas());
  check("wire-gone", doc.edges().size() == e0, QString::number(doc.edges().size()));
  check("undo-add", doc.undoCanvas());
  check("add-gone", doc.steps().size() == n0 && !doc.findStep(QStringLiteral("undo-tmp")),
        QString::number(doc.steps().size()));
  check("undone-clean", doc.canvasUndoAtClean());
  check("redo-after-full-undo", doc.canvasRedoDepth() == 3, QString::number(doc.canvasRedoDepth()));

  // new edit must drop the redo tail
  FlowStep s2;
  s2.id = QStringLiteral("undo-tmp2");
  s2.name = QStringLiteral("新编辑");
  s2.operation = QStringLiteral("cloud_filter");
  s2.position = QPointF(1, 2);
  doc.stepsMut().push_back(s2);
  doc.commitCanvasUndo(QStringLiteral("新编辑"));
  check("redo-cleared", doc.canvasRedoDepth() == 0 && doc.findStep(QStringLiteral("undo-tmp2")));
  check("old-add-dropped", !doc.findStep(QStringLiteral("undo-tmp")));
  check("undo-new", doc.undoCanvas());
  check("back-to-seed", doc.steps().size() == n0 && doc.canvasUndoAtClean());

  // cap 31 (baseline + 30 edits)
  SieansDocument cap;
  cap.seedGentlQrDemo();
  FlowStep hold;
  hold.id = QStringLiteral("cap-node");
  hold.name = QStringLiteral("cap");
  hold.operation = QStringLiteral("cloud_measure");
  cap.stepsMut().push_back(hold);
  cap.commitCanvasUndo(QStringLiteral("cap0"));
  if (FlowStep* h = cap.findStep(QStringLiteral("cap-node"))) {
    for (int i = 1; i <= 40; ++i) {
      h->params.insert(QStringLiteral("n"), i);
      cap.commitCanvasUndo(QStringLiteral("cap%1").arg(i));
    }
  }
  check("cap-size", cap.canvasUndoDepth() <= 30,
        QString::number(cap.canvasUndoDepth()));
  check("cap-can-undo", cap.undoCanvas());
  const FlowStep* last = cap.findStep(QStringLiteral("cap-node"));
  check("cap-value", last && last->params.value(QStringLiteral("n")).toInt() == 39,
        last ? QString::number(last->params.value(QStringLiteral("n")).toInt()) : QStringLiteral("missing"));

  // scratch isolation: mutating a second document does not affect a seed copy
  SieansDocument live;
  live.seedGentlQrDemo();
  const int liveN = live.steps().size();
  SieansDocument scratch = live;
  FlowStep sc;
  sc.id = QStringLiteral("scratch-only");
  sc.operation = QStringLiteral("cloud_measure");
  scratch.stepsMut().push_back(sc);
  scratch.commitCanvasUndo(QStringLiteral("scratch"));
  check("scratch-dirty", !scratch.canvasUndoAtClean());
  check("live-untouched", live.steps().size() == liveN && live.canvasUndoDepth() == 0 &&
                              live.canvasUndoAtClean() && !live.findStep(QStringLiteral("scratch-only")));
  check("scratch-undo-restores", scratch.undoCanvas() && scratch.steps().size() == liveN);
  return fails;
}


}  // namespace sieans_qt
