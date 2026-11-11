#include "PythonExt.hpp"

#include <QCoreApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QProcess>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSet>
#include <QtGlobal>

#include <limits>

namespace sieans_qt {
namespace {

constexpr int kMaxCodeBytes = 100000;
constexpr int kMaxStdoutBytes = 2000000;
constexpr int kMinTimeoutMs = 100;
constexpr int kMaxTimeoutMs = 30000;

bool cancelled(std::atomic<bool>* cancel) { return cancel && cancel->load(); }

/** 定位含 vision/script_worker.py 的仓库根目录。 */
QString findRepoRoot() {
  QStringList seeds;
  const QString envRoot = qEnvironmentVariable("SIEANS_ROOT");
  if (!envRoot.isEmpty()) seeds << envRoot;
  if (QCoreApplication::instance()) seeds << QCoreApplication::applicationDirPath();
  seeds << QDir::currentPath();
  for (const QString& seed : seeds) {
    QDir d(seed);
    for (int i = 0; i < 6; ++i) {
      if (QFileInfo::exists(d.filePath(QStringLiteral("vision/script_worker.py"))) &&
          QFileInfo::exists(d.filePath(QStringLiteral("desktop/builtin-catalog.json"))))
        return d.absolutePath();
      if (!d.cdUp()) break;
    }
  }
  return {};
}

QString pythonBinary(const QString& root) {
  const QString env = qEnvironmentVariable("VISION_PYTHON");
  if (!env.isEmpty() && QFileInfo::exists(env)) return env;
  if (!root.isEmpty()) {
    const QString venv = root + QStringLiteral("/.venv/bin/python");
    if (QFileInfo::exists(venv)) return venv;
  }
  return QStringLiteral("python3");
}

QVariant jsonToVariant(const QJsonValue& v) {
  if (v.isNull() || v.isUndefined()) return QVariant();
  if (v.isBool()) return v.toBool();
  if (v.isDouble()) {
    const double d = v.toDouble();
    if (qFuzzyCompare(d + 1.0, double(qRound(d)) + 1.0) &&
        d >= double(std::numeric_limits<int>::min()) &&
        d <= double(std::numeric_limits<int>::max()))
      return int(qRound(d));
    return d;
  }
  if (v.isString()) return v.toString();
  if (v.isArray()) {
    QVariantList lst;
    const QJsonArray a = v.toArray();
    lst.reserve(a.size());
    for (const QJsonValue& item : a) lst.append(jsonToVariant(item));
    return lst;
  }
  if (v.isObject()) {
    QVariantMap m;
    const QJsonObject o = v.toObject();
    for (auto it = o.begin(); it != o.end(); ++it) m.insert(it.key(), jsonToVariant(it.value()));
    return m;
  }
  return v.toVariant();
}

QJsonValue variantToJson(const QVariant& v);

QJsonObject mapToJson(const QVariantMap& m) {
  QJsonObject o;
  for (auto it = m.cbegin(); it != m.cend(); ++it) o.insert(it.key(), variantToJson(it.value()));
  return o;
}

QJsonValue variantToJson(const QVariant& v) {
  if (!v.isValid() || v.isNull()) return QJsonValue();
  switch (v.typeId()) {
    case QMetaType::Bool:
      return v.toBool();
    case QMetaType::Int:
    case QMetaType::UInt:
    case QMetaType::Long:
    case QMetaType::LongLong:
    case QMetaType::ULong:
    case QMetaType::ULongLong:
    case QMetaType::Short:
    case QMetaType::UShort:
      return QJsonValue(static_cast<qint64>(v.toLongLong()));
    case QMetaType::Double:
    case QMetaType::Float:
      return v.toDouble();
    case QMetaType::QString:
      return v.toString();
    case QMetaType::QVariantList: {
      QJsonArray a;
      for (const QVariant& item : v.toList()) a.append(variantToJson(item));
      return a;
    }
    case QMetaType::QVariantMap:
      return mapToJson(v.toMap());
    default:
      if (v.canConvert<QVariantMap>()) return mapToJson(v.toMap());
      if (v.canConvert<QVariantList>()) {
        QJsonArray a;
        for (const QVariant& item : v.toList()) a.append(variantToJson(item));
        return a;
      }
      return v.toString();
  }
}

QVariantList asList(const QVariant& v) {
  if (v.typeId() == QMetaType::QVariantList) return v.toList();
  if (v.typeId() == QMetaType::QString) {
    const QString s = v.toString().trimmed();
    if (s.isEmpty()) return {};
    QJsonParseError pe;
    const QJsonDocument doc = QJsonDocument::fromJson(s.toUtf8(), &pe);
    if (pe.error == QJsonParseError::NoError && doc.isArray()) return doc.array().toVariantList();
  }
  return {};
}

QVariantMap asMap(const QVariant& v) {
  if (v.typeId() == QMetaType::QVariantMap) return v.toMap();
  if (v.typeId() == QMetaType::QString) {
    const QString s = v.toString().trimmed();
    if (s.isEmpty()) return {};
    QJsonParseError pe;
    const QJsonDocument doc = QJsonDocument::fromJson(s.toUtf8(), &pe);
    if (pe.error == QJsonParseError::NoError && doc.isObject()) return doc.object().toVariantMap();
  }
  return {};
}

bool validVarName(const QString& name) {
  static const QRegularExpression re(QStringLiteral("^[A-Za-z_][A-Za-z0-9_]{0,63}$"));
  if (!re.match(name).hasMatch()) return false;
  return name != QLatin1String("__proto__") && name != QLatin1String("constructor") &&
         name != QLatin1String("prototype");
}

bool validPluginId(const QString& id) {
  static const QRegularExpression re(QStringLiteral("^[a-z][a-z0-9-]{0,63}$"));
  return re.match(id).hasMatch() && id != QLatin1String("constructor") &&
         id != QLatin1String("prototype");
}

QVariant lookupField(const QVariant& root, const QString& field, QString* error) {
  if (field.isEmpty()) {
    if (error) *error = QStringLiteral("脚本输出绑定的结果字段无效");
    return {};
  }
  QVariant cur = root;
  const QStringList parts = field.split(QLatin1Char('.'));
  QString path;
  for (const QString& key : parts) {
    path = path.isEmpty() ? key : (path + QLatin1Char('.') + key);
    if (cur.typeId() == QMetaType::QVariantMap) {
      const QVariantMap m = cur.toMap();
      if (!m.contains(key)) {
        if (error) *error = QStringLiteral("引用不存在：results.output.%1").arg(path);
        return {};
      }
      cur = m.value(key);
    } else if (cur.typeId() == QMetaType::QVariantList) {
      bool ok = false;
      const int i = key.toInt(&ok);
      const QVariantList lst = cur.toList();
      if (!ok || i < 0 || i >= lst.size()) {
        if (error) *error = QStringLiteral("引用不存在：results.output.%1").arg(path);
        return {};
      }
      cur = lst.at(i);
    } else {
      if (error) *error = QStringLiteral("引用不存在：results.output.%1").arg(path);
      return {};
    }
  }
  return cur;
}

bool applyReturnedVariables(const QVariant& variables, QVariantMap& flowVars,
                            QVariantMap& globalVars, QVariantMap& moduleVars,
                            QString* error) {
  if (!variables.isValid() || variables.isNull()) return true;
  if (variables.typeId() != QMetaType::QVariantMap) {
    if (error) *error = QStringLiteral("脚本变量 必须是对象");
    return false;
  }
  const QVariantMap scopes = variables.toMap();
  for (auto it = scopes.cbegin(); it != scopes.cend(); ++it) {
    const QString scope = it.key();
    if (scope != QLatin1String("global") && scope != QLatin1String("flow") &&
        scope != QLatin1String("module")) {
      if (error) *error = QStringLiteral("未知脚本变量作用域：%1").arg(scope);
      return false;
    }
    if (it.value().typeId() != QMetaType::QVariantMap) {
      if (error) *error = QStringLiteral("脚本变量 必须是对象");
      return false;
    }
    if (scope == QLatin1String("global"))
      globalVars = it.value().toMap();
    else if (scope == QLatin1String("flow"))
      flowVars = it.value().toMap();
    else
      moduleVars = it.value().toMap();
  }
  return true;
}

bool applyOutputBindings(const QVariant& bindingsVar, const QVariantMap& result,
                         QVariantMap& flowVars, QVariantMap& globalVars,
                         QVariantMap& moduleVars, QString* error) {
  if (!bindingsVar.isValid() || bindingsVar.isNull()) return true;
  if (bindingsVar.typeId() == QMetaType::QString && bindingsVar.toString().trimmed().isEmpty())
    return true;
  const QVariantList bindings = asList(bindingsVar);
  if (bindingsVar.typeId() == QMetaType::QString && bindings.isEmpty() &&
      !bindingsVar.toString().trimmed().isEmpty()) {
    if (error) *error = QStringLiteral("脚本输出绑定最多 100 项");
    return false;
  }
  if (bindings.size() > 100) {
    if (error) *error = QStringLiteral("脚本输出绑定最多 100 项");
    return false;
  }
  QSet<QString> targets;
  for (const QVariant& item : bindings) {
    const QVariantMap b = item.toMap();
    const QString scope = b.value(QStringLiteral("scope")).toString().trimmed();
    const QString name = b.value(QStringLiteral("name")).toString().trimmed();
    const QString field = b.value(QStringLiteral("field")).toString().trimmed();
    if ((scope != QLatin1String("global") && scope != QLatin1String("flow") &&
         scope != QLatin1String("module")) ||
        !validVarName(name) || field.isEmpty()) {
      if (error) *error = QStringLiteral("脚本输出绑定的范围、变量名或结果字段无效");
      return false;
    }
    const QString target = scope + QLatin1Char('.') + name;
    if (targets.contains(target)) {
      if (error) *error = QStringLiteral("脚本输出重复写入同一变量：%1").arg(name);
      return false;
    }
    targets.insert(target);
    QString lookErr;
    const QVariant value = lookupField(QVariant(result), field, &lookErr);
    if (!lookErr.isEmpty()) {
      if (error) *error = lookErr;
      return false;
    }
    if (scope == QLatin1String("global"))
      globalVars.insert(name, value);
    else if (scope == QLatin1String("flow"))
      flowVars.insert(name, value);
    else
      moduleVars.insert(name, value);
  }
  return true;
}

void stopProcess(QProcess& proc) {
  if (proc.state() == QProcess::NotRunning) return;
  proc.terminate();
  if (!proc.waitForFinished(200)) proc.kill();
  proc.waitForFinished(200);
}

PythonExtResult failResult(const QString& error, bool cancelledFlag, int elapsed) {
  PythonExtResult r;
  r.error = error;
  r.note = error;
  r.cancelled = cancelledFlag;
  r.elapsedMs = elapsed;
  return r;
}

struct WorkerReply {
  PythonExtResult status;
  QVariantMap data;
};

/**
 * 调用已有的 vision/script_worker.py：stdin JSON {code, context}，
 * stdout JSON {ok, data, logs, elapsedMs}。超限或取消时杀掉子进程。
 */
WorkerReply invokeWorker(const QString& code, const QVariantMap& context, int timeoutMs,
                         std::atomic<bool>* cancel) {
  WorkerReply wr;
  QElapsedTimer clock;
  clock.start();
  if (cancelled(cancel)) {
    wr.status = failResult(QStringLiteral("Python 脚本已取消"), true, int(clock.elapsed()));
    return wr;
  }
  if (code.toUtf8().size() > kMaxCodeBytes) {
    wr.status = failResult(QStringLiteral("Python 脚本超过 100 KB 或类型无效"), false,
                           int(clock.elapsed()));
    return wr;
  }
  if (timeoutMs < kMinTimeoutMs || timeoutMs > kMaxTimeoutMs) {
    wr.status = failResult(QStringLiteral("脚本超时必须是 100–30000 ms"), false,
                           int(clock.elapsed()));
    return wr;
  }

  const QString root = findRepoRoot();
  if (root.isEmpty()) {
    wr.status = failResult(QStringLiteral("未找到 vision/script_worker.py，请在仓库根目录运行"),
                           false, int(clock.elapsed()));
    return wr;
  }
  const QString worker = root + QStringLiteral("/vision/script_worker.py");
  const QString py = pythonBinary(root);

  QJsonObject req;
  req.insert(QStringLiteral("code"), code);
  req.insert(QStringLiteral("context"), mapToJson(context));
  const QByteArray payload = QJsonDocument(req).toJson(QJsonDocument::Compact);

  QProcess proc;
  proc.setWorkingDirectory(root);
  proc.setProgram(py);
  proc.setArguments({QStringLiteral("-X"), QStringLiteral("utf8"), QStringLiteral("-u"), worker});
  QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
  env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));
  const QString pydeps = root + QStringLiteral("/.pydeps");
  if (QDir(pydeps).exists()) {
    const QString cur = env.value(QStringLiteral("PYTHONPATH"));
    env.insert(QStringLiteral("PYTHONPATH"),
               cur.isEmpty() ? pydeps : (cur + QDir::listSeparator() + pydeps));
  }
  proc.setProcessEnvironment(env);
  proc.start();
  if (!proc.waitForStarted(qMin(2000, timeoutMs))) {
    stopProcess(proc);
    wr.status = failResult(QStringLiteral("无法启动 Python 解释器：%1").arg(proc.errorString()),
                           false, int(clock.elapsed()));
    return wr;
  }
  proc.write(payload);
  proc.closeWriteChannel();

  QByteArray out;
  QByteArray err;
  bool oversize = false;
  auto pump = [&]() {
    out += proc.readAllStandardOutput();
    err += proc.readAllStandardError();
    if (out.size() > kMaxStdoutBytes) oversize = true;
  };
  while (proc.state() != QProcess::NotRunning) {
    if (cancelled(cancel)) {
      stopProcess(proc);
      wr.status = failResult(QStringLiteral("Python 脚本已取消"), true, int(clock.elapsed()));
      return wr;
    }
    if (clock.elapsed() >= timeoutMs) {
      stopProcess(proc);
      wr.status = failResult(QStringLiteral("Python 脚本执行超时（%1 ms）").arg(timeoutMs), false,
                             int(clock.elapsed()));
      return wr;
    }
    proc.waitForFinished(20);
    pump();
    if (oversize) {
      stopProcess(proc);
      wr.status = failResult(QStringLiteral("脚本输出超过 2 MB"), false, int(clock.elapsed()));
      return wr;
    }
    if (QCoreApplication::instance())
      QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
  }
  pump();
  const int elapsed = int(clock.elapsed());
  if (oversize) {
    wr.status = failResult(QStringLiteral("脚本输出超过 2 MB"), false, elapsed);
    return wr;
  }

  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(out, &pe);
  if (pe.error != QJsonParseError::NoError || !doc.isObject()) {
    const QString tail = QString::fromUtf8(err.isEmpty() ? out.right(800) : err.right(800));
    wr.status = failResult(QStringLiteral("脚本进程退出：%1").arg(tail.trimmed()), false, elapsed);
    return wr;
  }
  const QJsonObject obj = doc.object();
  if (!obj.value(QStringLiteral("ok")).toBool()) {
    wr.status = failResult(
        obj.value(QStringLiteral("error")).toString(QStringLiteral("脚本执行失败")), false,
        elapsed);
    return wr;
  }
  wr.data = jsonToVariant(obj.value(QStringLiteral("data"))).toMap();
  wr.status.ok = true;
  wr.status.result = wr.data.value(QStringLiteral("result")).toMap();
  wr.status.logs = obj.value(QStringLiteral("logs")).toString();
  wr.status.elapsedMs = elapsed;
  wr.status.note = QStringLiteral("Python 脚本完成 %1 ms").arg(elapsed);
  return wr;
}

QVariantMap buildContext(const QVariantMap& arguments, const QVariantMap& flowVars,
                         const QVariantMap& globalVars, const QVariantMap& moduleVars,
                         const QVariantMap& upstreamResults) {
  QVariantMap vars;
  vars.insert(QStringLiteral("global"), globalVars);
  vars.insert(QStringLiteral("flow"), flowVars);
  vars.insert(QStringLiteral("module"), moduleVars);
  QVariantMap ctx;
  ctx.insert(QStringLiteral("vars"), vars);
  ctx.insert(QStringLiteral("results"), upstreamResults);
  ctx.insert(QStringLiteral("image"), QString());
  ctx.insert(QStringLiteral("cloud"), QVariant());
  ctx.insert(QStringLiteral("depth"), QVariant());
  ctx.insert(QStringLiteral("params"), arguments);
  ctx.insert(QStringLiteral("inputs"), QVariantMap{});
  return ctx;
}

int timeoutOf(const QVariantMap& params, int def = 5000) {
  if (!params.contains(QStringLiteral("timeoutMs"))) return def;
  bool ok = false;
  const int n = params.value(QStringLiteral("timeoutMs")).toInt(&ok);
  if (!ok) return -1;
  return n;
}

QVariantMap prepareArguments(const QVariantMap& given, const QVariantList& parameters,
                             QString* error) {
  QVariantMap out = given;
  QSet<QString> known;
  for (const QVariant& item : parameters) {
    const QVariantMap f = item.toMap();
    const QString key = f.value(QStringLiteral("key")).toString();
    if (key.isEmpty()) continue;
    known.insert(key);
    if (!out.contains(key) && f.contains(QStringLiteral("default")))
      out.insert(key, f.value(QStringLiteral("default")));
    if (f.value(QStringLiteral("required")).toBool() && !out.contains(key)) {
      if (error) *error = QStringLiteral("插件缺少参数：%1").arg(f.value(QStringLiteral("label")).toString());
      return {};
    }
  }
  return out;
}

bool checkDeclaredOutputs(const QVariantMap& result, const QVariantList& outputs, QString* error) {
  QSet<QString> known;
  for (const QVariant& item : outputs) {
    const QVariantMap f = item.toMap();
    const QString key = f.value(QStringLiteral("key")).toString();
    if (key.isEmpty()) continue;
    known.insert(key);
    if (f.value(QStringLiteral("required")).toBool() && !result.contains(key)) {
      if (error) *error = QStringLiteral("插件缺少结果：%1").arg(f.value(QStringLiteral("label")).toString());
      return false;
    }
  }
  for (auto it = result.cbegin(); it != result.cend(); ++it) {
    if (!known.contains(it.key())) {
      if (error) *error = QStringLiteral("插件返回未声明结果：%1").arg(it.key());
      return false;
    }
  }
  return true;
}

struct PluginOp {
  QString pluginId;
  QString version;
  QString operatorId;
  QString code;
  QString input;
  int timeoutMs = 5000;
  QVariantList parameters;
  QVariantList outputs;
  QString error;
  bool ok = false;
};

bool isRegularFile(const QString& path, qint64 maxBytes, QString* error, const QString& label) {
  QFileInfo info(path);
  if (!info.exists() || !info.isFile() || info.isSymLink()) {
    if (error) *error = label + QStringLiteral("必须是普通文件");
    return false;
  }
  if (info.size() > maxBytes) {
    if (error) *error = label + QStringLiteral("超出大小上限");
    return false;
  }
  return true;
}

PluginOp loadPluginOp(const QString& pluginId, const QString& pluginVersion,
                      const QString& operatorId) {
  PluginOp out;
  out.pluginId = pluginId;
  out.version = pluginVersion;
  out.operatorId = operatorId;
  if (!validPluginId(pluginId) || !validPluginId(operatorId)) {
    out.error = QStringLiteral("插件名称、标识或版本无效");
    return out;
  }
  const QString root = findRepoRoot();
  if (root.isEmpty()) {
    out.error = QStringLiteral("未找到插件目录（仓库根不存在）");
    return out;
  }
  const QStringList roots = {root + QStringLiteral("/operator-plugins"),
                             root + QStringLiteral("/data/operator-plugins")};
  QString found;
  QJsonObject manifest;
  for (const QString& base : roots) {
    QDir dir(base);
    if (!dir.exists()) continue;
    const QFileInfoList entries = dir.entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
    for (const QFileInfo& ent : entries) {
      if (ent.isSymLink()) continue;
      const QString mf = ent.absoluteFilePath() + QStringLiteral("/operator-plugin.json");
      if (!QFileInfo::exists(mf) || QFileInfo(mf).isSymLink()) continue;
      if (QFileInfo(mf).size() > 128000) continue;
      QFile f(mf);
      if (!f.open(QIODevice::ReadOnly)) continue;
      QJsonParseError pe;
      const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &pe);
      if (pe.error != QJsonParseError::NoError || !doc.isObject()) continue;
      const QJsonObject m = doc.object();
      if (m.value(QStringLiteral("id")).toString() != pluginId) continue;
      found = ent.absoluteFilePath();
      manifest = m;
      break;
    }
    if (!found.isEmpty()) break;
  }
  if (found.isEmpty()) {
    out.error = QStringLiteral("插件未安装或已停用：%1").arg(pluginId);
    return out;
  }
  if (manifest.value(QStringLiteral("apiVersion")).toInt() != 1) {
    out.error = QStringLiteral("不兼容的插件接口版本，仅支持 1");
    return out;
  }
  const QString ver = manifest.value(QStringLiteral("version")).toString();
  if (ver != pluginVersion) {
    out.error = QStringLiteral("插件版本不匹配：工程 %1，已安装 %2").arg(pluginVersion, ver);
    return out;
  }
  const QJsonArray ops = manifest.value(QStringLiteral("operators")).toArray();
  QJsonObject opObj;
  for (const QJsonValue& v : ops) {
    const QJsonObject o = v.toObject();
    if (o.value(QStringLiteral("id")).toString() == operatorId) {
      opObj = o;
      break;
    }
  }
  if (opObj.isEmpty()) {
    out.error = QStringLiteral("插件中不存在该算子");
    return out;
  }
  const QString entry = opObj.value(QStringLiteral("entry")).toString();
  static const QRegularExpression entryRe(QStringLiteral("^[A-Za-z0-9_-]+\\.py$"));
  if (!entryRe.match(entry).hasMatch()) {
    out.error = QStringLiteral("入口必须是插件目录中的 Python 文件名");
    return out;
  }
  const QString pyPath = found + QLatin1Char('/') + entry;
  QString fileErr;
  if (!isRegularFile(pyPath, 100000, &fileErr, QStringLiteral("插件入口"))) {
    out.error = fileErr;
    return out;
  }
  QFile pf(pyPath);
  if (!pf.open(QIODevice::ReadOnly)) {
    out.error = QStringLiteral("无法读取插件入口");
    return out;
  }
  out.code = QString::fromUtf8(pf.readAll());
  out.input = opObj.value(QStringLiteral("input")).toString(QStringLiteral("none"));
  out.timeoutMs = opObj.value(QStringLiteral("timeoutMs")).toInt(5000);
  if (out.timeoutMs < kMinTimeoutMs || out.timeoutMs > kMaxTimeoutMs) {
    out.error = QStringLiteral("插件超时范围为 100–30000 ms");
    return out;
  }
  out.parameters = opObj.value(QStringLiteral("parameters")).toArray().toVariantList();
  out.outputs = opObj.value(QStringLiteral("outputs")).toArray().toVariantList();
  out.ok = true;
  return out;
}

PythonExtResult finishApply(WorkerReply wr, const QVariantMap& params, QVariantMap& flowVars,
                            QVariantMap& globalVars, QVariantMap& moduleVars) {
  if (!wr.status.ok) return wr.status;
  QString err;
  if (!applyReturnedVariables(wr.data.value(QStringLiteral("variables")), flowVars, globalVars,
                              moduleVars, &err)) {
    wr.status.ok = false;
    wr.status.error = err;
    wr.status.note = err;
    return wr.status;
  }
  if (!applyOutputBindings(params.value(QStringLiteral("outputBindings")), wr.status.result,
                           flowVars, globalVars, moduleVars, &err)) {
    wr.status.ok = false;
    wr.status.error = err;
    wr.status.note = err;
    return wr.status;
  }
  return wr.status;
}

}  // namespace

PythonExtResult runScript(const QVariantMap& params, QVariantMap& flowVars,
                          QVariantMap& globalVars, QVariantMap& moduleVars,
                          const QVariantMap& upstreamResults, std::atomic<bool>* cancel) {
  const QString code = params.value(QStringLiteral("code")).toString();
  if (code.trimmed().isEmpty())
    return failResult(QStringLiteral("脚本必须定义 run(ctx) 函数"), false, 0);
  const int timeoutMs = timeoutOf(params, 5000);
  if (timeoutMs < kMinTimeoutMs || timeoutMs > kMaxTimeoutMs)
    return failResult(QStringLiteral("脚本超时必须是 100–30000 ms"), false, 0);
  const QVariantMap arguments = asMap(params.value(QStringLiteral("arguments")));
  const QVariantMap ctx = buildContext(arguments, flowVars, globalVars, moduleVars, upstreamResults);
  return finishApply(invokeWorker(code, ctx, timeoutMs, cancel), params, flowVars, globalVars,
                     moduleVars);
}

PythonExtResult runPlugin(const QVariantMap& params, QVariantMap& flowVars,
                          QVariantMap& globalVars, QVariantMap& moduleVars,
                          const QVariantMap& upstreamResults, std::atomic<bool>* cancel) {
  const QString pluginId = params.value(QStringLiteral("pluginId")).toString().trimmed();
  const QString pluginVersion = params.value(QStringLiteral("pluginVersion")).toString().trimmed();
  const QString operatorId = params.value(QStringLiteral("operatorId")).toString().trimmed();
  if (pluginId.isEmpty() || pluginVersion.isEmpty() || operatorId.isEmpty())
    return failResult(QStringLiteral("插件未安装或已停用：%1").arg(pluginId), false, 0);
  const PluginOp op = loadPluginOp(pluginId, pluginVersion, operatorId);
  if (!op.ok) return failResult(op.error, false, 0);
  if (op.input != QLatin1String("none")) {
    // 烟测与默认种子使用 input=none；需要图像/点云的插件须由调用方提供通道。
    const bool hasImage = !upstreamResults.value(QStringLiteral("__image")).toString().isEmpty();
    const bool hasCloud = upstreamResults.contains(QStringLiteral("__cloud"));
    if ((op.input == QLatin1String("image") && !hasImage) ||
        (op.input == QLatin1String("cloud") && !hasCloud) ||
        (op.input == QLatin1String("depth") && !upstreamResults.contains(QStringLiteral("__depth"))))
      return failResult(QStringLiteral("插件需要输入%1")
                            .arg(op.input == QLatin1String("image")
                                     ? QStringLiteral("图像")
                                     : (op.input == QLatin1String("cloud") ? QStringLiteral("点云")
                                                                           : QStringLiteral("深度图"))),
                        false, 0);
  }
  QString err;
  const QVariantMap arguments =
      prepareArguments(asMap(params.value(QStringLiteral("arguments"))), op.parameters, &err);
  if (!err.isEmpty()) return failResult(err, false, 0);
  const QVariantMap ctx = buildContext(arguments, flowVars, globalVars, moduleVars, upstreamResults);
  WorkerReply wr = invokeWorker(op.code, ctx, op.timeoutMs, cancel);
  wr.status.pluginId = pluginId;
  wr.status.pluginVersion = pluginVersion;
  wr.status.operatorId = operatorId;
  if (!wr.status.ok) return wr.status;
  if (!checkDeclaredOutputs(wr.status.result, op.outputs, &err)) {
    wr.status.ok = false;
    wr.status.error = err;
    wr.status.note = err;
    return wr.status;
  }
  wr.status.note = QStringLiteral("插件 %1/%2 完成 %3 ms")
                       .arg(pluginId, operatorId)
                       .arg(wr.status.elapsedMs);
  return finishApply(wr, params, flowVars, globalVars, moduleVars);
}

QStringList pythonExtSelfTest() {
  QStringList fails;
  auto check = [&](bool cond, const QString& msg) {
    if (!cond) fails << msg;
  };

  {
    QVariantMap flow, global, module;
    flow.insert(QStringLiteral("keep"), 1);
    const QString code =
        QStringLiteral("def run(ctx):\n    return dict(result=dict(scriptOut=4242, passed=True))\n");
    QVariantMap params;
    params.insert(QStringLiteral("code"), code);
    params.insert(QStringLiteral("timeoutMs"), 5000);
    params.insert(QStringLiteral("arguments"), QVariantMap{{QStringLiteral("count"), 1}});
    params.insert(QStringLiteral("outputBindings"),
                  QVariantList{QVariantMap{{QStringLiteral("field"), QStringLiteral("scriptOut")},
                                           {QStringLiteral("scope"), QStringLiteral("flow")},
                                           {QStringLiteral("name"), QStringLiteral("scriptOut")}}});
    const PythonExtResult r = runScript(params, flow, global, module);
    check(r.ok, QStringLiteral("script ok: %1").arg(r.error));
    check(r.result.value(QStringLiteral("scriptOut")).toInt() == 4242,
          QStringLiteral("script result %1").arg(r.result.value(QStringLiteral("scriptOut")).toString()));
    check(flow.value(QStringLiteral("scriptOut")).toInt() == 4242,
          QStringLiteral("scriptOut binding %1").arg(flow.value(QStringLiteral("scriptOut")).toString()));
    check(flow.value(QStringLiteral("keep")).toInt() == 1, QStringLiteral("script kept flow.keep"));
  }

  {
    QVariantMap flow, global, module;
    QVariantMap params;
    params.insert(QStringLiteral("code"), QStringLiteral("x = 1\n"));
    params.insert(QStringLiteral("timeoutMs"), 5000);
    const PythonExtResult r = runScript(params, flow, global, module);
    check(!r.ok && r.error.contains(QStringLiteral("run(ctx)")),
          QStringLiteral("script missing run: %1").arg(r.error));
  }

  {
    QVariantMap flow, global, module;
    QVariantMap params;
    params.insert(QStringLiteral("code"),
                  QStringLiteral("def run(ctx):\n    import time\n    time.sleep(3)\n"
                                 "    return dict(result=dict())\n"));
    params.insert(QStringLiteral("timeoutMs"), 400);
    const PythonExtResult r = runScript(params, flow, global, module);
    check(!r.ok && r.error.contains(QStringLiteral("超时")),
          QStringLiteral("script timeout: %1").arg(r.error));
  }

  {
    std::atomic<bool> cancel{true};
    QVariantMap flow, global, module;
    QVariantMap params;
    params.insert(QStringLiteral("code"),
                  QStringLiteral("def run(ctx):\n    return dict(result=dict(ok=True))\n"));
    params.insert(QStringLiteral("timeoutMs"), 5000);
    const PythonExtResult r = runScript(params, flow, global, module, {}, &cancel);
    check(!r.ok && r.cancelled && r.error.contains(QStringLiteral("取消")),
          QStringLiteral("script cancel: %1").arg(r.error));
  }

  {
    QVariantMap flow, global, module;
    QVariantMap params;
    params.insert(QStringLiteral("pluginId"), QStringLiteral("sieans-soft-smoke"));
    params.insert(QStringLiteral("pluginVersion"), QStringLiteral("1.0.0"));
    params.insert(QStringLiteral("operatorId"), QStringLiteral("fixed-value"));
    params.insert(QStringLiteral("arguments"), QVariantMap{{QStringLiteral("value"), 9001}});
    params.insert(QStringLiteral("outputBindings"),
                  QVariantList{QVariantMap{{QStringLiteral("field"), QStringLiteral("value")},
                                           {QStringLiteral("scope"), QStringLiteral("flow")},
                                           {QStringLiteral("name"), QStringLiteral("pluginValue")}}});
    const PythonExtResult r = runPlugin(params, flow, global, module);
    check(r.ok, QStringLiteral("plugin ok: %1").arg(r.error));
    check(r.result.value(QStringLiteral("value")).toInt() == 9001,
          QStringLiteral("plugin result %1").arg(r.result.value(QStringLiteral("value")).toString()));
    check(r.result.value(QStringLiteral("passed")).toBool(), QStringLiteral("plugin passed"));
    check(flow.value(QStringLiteral("pluginValue")).toInt() == 9001,
          QStringLiteral("pluginValue %1").arg(flow.value(QStringLiteral("pluginValue")).toString()));
    check(r.pluginId == QLatin1String("sieans-soft-smoke"), QStringLiteral("plugin id"));
  }

  {
    QVariantMap flow, global, module;
    QVariantMap params;
    params.insert(QStringLiteral("pluginId"), QStringLiteral("sieans-soft-smoke"));
    params.insert(QStringLiteral("pluginVersion"), QStringLiteral("9.9.9"));
    params.insert(QStringLiteral("operatorId"), QStringLiteral("fixed-value"));
    const PythonExtResult r = runPlugin(params, flow, global, module);
    check(!r.ok && r.error.contains(QStringLiteral("版本不匹配")),
          QStringLiteral("plugin version: %1").arg(r.error));
  }

  {
    QVariantMap flow, global, module;
    QVariantMap params;
    params.insert(QStringLiteral("pluginId"), QStringLiteral("not-a-real-plugin"));
    params.insert(QStringLiteral("pluginVersion"), QStringLiteral("1.0.0"));
    params.insert(QStringLiteral("operatorId"), QStringLiteral("fixed-value"));
    const PythonExtResult r = runPlugin(params, flow, global, module);
    check(!r.ok && r.error.contains(QStringLiteral("未安装")),
          QStringLiteral("plugin missing: %1").arg(r.error));
  }

  return fails;
}

}  // namespace sieans_qt
