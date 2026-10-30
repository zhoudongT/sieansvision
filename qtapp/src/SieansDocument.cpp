#include "SieansDocument.hpp"

#include <QFile>
#include <QJsonDocument>
#include <QJsonValue>
#include <QUuid>

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
    if (e.id.isEmpty())
      e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    if (!e.from.isEmpty() && !e.to.isEmpty()) edges_.push_back(e);
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
    });
  }
  root.insert(QStringLiteral("edges"), edgesArr);
  root.insert(QStringLiteral("variables"), mapToObject(variables_));
  if (!commManager_.isEmpty())
    root.insert(QStringLiteral("commManager"), mapToObject(commManager_));

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

void SieansDocument::seedGentlQrDemo() {
  name_ = QStringLiteral("打开即跑 · GenTL相机→二维码");
  path_.clear();
  sourcePosition_ = QPointF(80, 160);
  sourceConfig_ = {
      {QStringLiteral("mode"), QStringLiteral("local")},
      {QStringLiteral("cameraParams"),
       QVariantMap{
           {QStringLiteral("driver"), QStringLiteral("gentl")},
           {QStringLiteral("backendKind"), QStringLiteral("gentl")},
           {QStringLiteral("continuousLive"), true},
           {QStringLiteral("sessionPersist"), true},
           {QStringLiteral("trigger"), QStringLiteral("freerun")},
           {QStringLiteral("exposureTime"), 2000},
           {QStringLiteral("acquisitionFrameRate"), 15},
       }},
  };
  steps_.clear();
  edges_.clear();

  auto add = [&](const QString& id, const QString& name, const QString& op, qreal x,
                 qreal y, const QString& from) {
    FlowStep s;
    s.id = id;
    s.name = name;
    s.operation = op;
    s.position = QPointF(x, y);
    s.imageFrom = from;
    s.runState = QStringLiteral("等待执行");
    steps_.push_back(s);
  };
  add(QStringLiteral("cam1"), QStringLiteral("MV GenTL 采集"),
      QStringLiteral("camera_capture"), 300, 160, QStringLiteral("source"));
  add(QStringLiteral("qr1"), QStringLiteral("二维码/条码识别"),
      QStringLiteral("barcode"), 300, 300, QStringLiteral("cam1"));
  add(QStringLiteral("var1"), QStringLiteral("二维码结果·OK/NG"),
      QStringLiteral("var_calc"), 300, 440, QStringLiteral("qr1"));

  auto link = [&](const QString& a, const QString& b) {
    FlowEdge e;
    e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    e.from = a;
    e.to = b;
    edges_.push_back(e);
  };
  link(QStringLiteral("source"), QStringLiteral("cam1"));
  link(QStringLiteral("cam1"), QStringLiteral("qr1"));
  link(QStringLiteral("qr1"), QStringLiteral("var1"));

  variables_ = {
      {QStringLiteral("barcodeCount"), 0},
      {QStringLiteral("barcodeText"), QString()},
      {QStringLiteral("barcodeAll"), QString()},
      {QStringLiteral("barcodeOk"), 0},
      {QStringLiteral("passGate"), 0},
      {QStringLiteral("formatted"), QString()},
      {QStringLiteral("commPayload"), QString()},
  };
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
                   {QStringLiteral("ack"), QStringLiteral("OK")}}},
  };
}

QStringList SieansDocument::hostWatchKeys() const {
  const QVariantMap hw = objectToMap(raw_.value(QStringLiteral("hostWatch")).toObject());
  QStringList keys;
  for (const QVariant& v : hw.value(QStringLiteral("watchKeys")).toList())
    keys << v.toString();
  if (keys.isEmpty()) {
    keys = {QStringLiteral("barcodeCount"), QStringLiteral("barcodeText"),
            QStringLiteral("barcodeAll"), QStringLiteral("barcodeOk"),
            QStringLiteral("passGate"), QStringLiteral("formatted"),
            QStringLiteral("commPayload")};
  }
  return keys;
}

}  // namespace sieans_qt
