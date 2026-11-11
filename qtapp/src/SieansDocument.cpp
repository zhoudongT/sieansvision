#include "SieansDocument.hpp"
#include "SubflowExec.hpp"

#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QUuid>
#include <QRect>

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
       }},
      {QStringLiteral("tcpReal"),
       QVariantMap{{QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                   {QStringLiteral("port"), 19956},
                   {QStringLiteral("framing"), QStringLiteral("lf")},
                   {QStringLiteral("role"), QStringLiteral("server")},
                   {QStringLiteral("ack"), QStringLiteral("OK")},
                   {QStringLiteral("autoStart"), true},
                   {QStringLiteral("reconnect"), true}}},
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
  const QVariantMap hw = objectToMap(raw_.value(QStringLiteral("hostWatch")).toObject());
  QStringList keys;
  for (const QVariant& v : hw.value(QStringLiteral("watchKeys")).toList())
    keys << v.toString();
  if (keys.isEmpty()) {
    keys = {QStringLiteral("barcodeCount"), QStringLiteral("barcodeText"),
            QStringLiteral("barcodeAll"), QStringLiteral("barcodeOk"),
            QStringLiteral("ocrCount"), QStringLiteral("ocrText"),
            QStringLiteral("ocrAll"), QStringLiteral("ocrOk"),
            QStringLiteral("caliperDist"), QStringLiteral("caliperOk"),
            QStringLiteral("measureMm"), QStringLiteral("caliperMm"),
            QStringLiteral("passGate"), QStringLiteral("urlOk"),
            QStringLiteral("formatted"), QStringLiteral("lastRecv"),
            QStringLiteral("commPayload"), QStringLiteral("hostResult"),
            QStringLiteral("hostMode"), QStringLiteral("hostState"),
            QStringLiteral("hostOkStreak"), QStringLiteral("hostNgCount"),
            QStringLiteral("conditionPassed"), QStringLiteral("branchTaken"),
            QStringLiteral("branchRoute"), QStringLiteral("mergeFrom"),
            QStringLiteral("skippedCount"), QStringLiteral("subflowPassed"),
            QStringLiteral("subflowCount"), QStringLiteral("loopCompleted"),
            QStringLiteral("loopStoppedEarly"), QStringLiteral("loopCount"),
            QStringLiteral("loopPassed"), QStringLiteral("defectsCount"),
            QStringLiteral("defectsRatio"), QStringLiteral("defectsOk"),
            QStringLiteral("defectsPassed"), QStringLiteral("defectsMaxArea"),
            QStringLiteral("defectsCleanCount"), QStringLiteral("defectsCleanOk"),
            QStringLiteral("locateOk"), QStringLiteral("locateScore"),
            QStringLiteral("locateX"), QStringLiteral("locateY"),
            QStringLiteral("locateAngle"), QStringLiteral("fixtureOk"),
            QStringLiteral("fixtureX"), QStringLiteral("fixtureY"),
            QStringLiteral("fixtureAngle"), QStringLiteral("defectsFollowCount"),
            QStringLiteral("defectsFollowOk"), QStringLiteral("defectsFollowRoiX"),
            QStringLiteral("defectsFollowRoiY")};
  }
  return keys;
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
  raw_ = QJsonObject{{QStringLiteral("version"), 2}};
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


}  // namespace sieans_qt
