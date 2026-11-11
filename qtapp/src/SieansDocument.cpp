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
            QStringLiteral("defectsFollowRoiY"),
            QStringLiteral("geomCircCount"), QStringLiteral("geomCircOk"),
            QStringLiteral("geomCircRadius"), QStringLiteral("geomLineCount"),
            QStringLiteral("geomLineLength"), QStringLiteral("geomFollowCount"),
            QStringLiteral("geomFollowOk"), QStringLiteral("geomFollowRadius"),
            QStringLiteral("measCircDiameter"), QStringLiteral("measCircOk"),
            QStringLiteral("measLineLength"), QStringLiteral("measAngAngle"),
            QStringLiteral("measPtsDist")};
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
