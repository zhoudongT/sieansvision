#include "FlowExtras.hpp"

#include "CommHub.hpp"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QRegularExpression>
#include <QThread>
#include <QtGlobal>

namespace sieans_qt {
namespace {

bool cancelled(std::atomic<bool>* cancel) { return cancel && cancel->load(); }

bool validVarName(const QString& name) {
  static const QRegularExpression re(QStringLiteral("^[A-Za-z_][A-Za-z0-9_]{0,63}$"));
  if (!re.match(name).hasMatch()) return false;
  if (name == QLatin1String("__proto__") || name == QLatin1String("constructor") ||
      name == QLatin1String("prototype"))
    return false;
  return true;
}

QVariant resolveAssignValue(const QVariant& raw, const QVariantMap& flowVars) {
  if (raw.typeId() != QMetaType::QString) return raw;
  const QString s = raw.toString();
  if (s.contains(QLatin1Char('{')) || s.contains(QLatin1Char('$'))) {
    const QString expanded = CommHub::expandTemplate(s, flowVars);
    bool ok = false;
    const int n = expanded.toInt(&ok);
    if (ok && expanded == QString::number(n)) return n;
    bool dok = false;
    const double d = expanded.toDouble(&dok);
    if (dok && !expanded.contains(QLatin1Char(' '))) return d;
    if (expanded == QLatin1String("true")) return true;
    if (expanded == QLatin1String("false")) return false;
    return expanded;
  }
  // bare identifier → existing flow var
  if (validVarName(s) && flowVars.contains(s)) return flowVars.value(s);
  return raw;
}

}  // namespace

DelayResult runDelay(const QVariantMap& params, std::atomic<bool>* cancel) {
  DelayResult r;
  const QVariant raw = params.value(QStringLiteral("milliseconds"), 100);
  bool ok = false;
  const int ms = raw.toInt(&ok);
  if (!ok || ms < 0 || ms > 30000) {
    r.error = QStringLiteral("延时必须为 0–30000 的整数毫秒");
    return r;
  }
  r.milliseconds = ms;
  QElapsedTimer t;
  t.start();
  if (cancelled(cancel)) {
    r.cancelled = true;
    r.error = QStringLiteral("延时已取消");
    r.elapsedMs = int(t.elapsed());
    r.note = r.error;
    return r;
  }
  while (t.elapsed() < ms) {
    if (cancelled(cancel)) {
      r.cancelled = true;
      r.error = QStringLiteral("延时已取消");
      r.elapsedMs = int(t.elapsed());
      r.note = r.error;
      return r;
    }
    const int left = ms - int(t.elapsed());
    QThread::msleep(quint32(qBound(0, qMin(5, left), 5)));
    if (QCoreApplication::instance())
      QCoreApplication::processEvents(QEventLoop::AllEvents, 5);
  }
  r.ok = true;
  r.elapsedMs = int(t.elapsed());
  r.note = QStringLiteral("delay %1 ms · elapsed %2 ms").arg(ms).arg(r.elapsedMs);
  return r;
}

VarsAssignResult runVariables(const QVariantMap& params, QVariantMap& flowVars,
                              QVariantMap& globalVars, QVariantMap& moduleVars) {
  VarsAssignResult r;
  r.scope = params.value(QStringLiteral("scope"), QStringLiteral("flow")).toString().trimmed();
  r.name = params.value(QStringLiteral("name")).toString().trimmed();
  r.mode = params.value(QStringLiteral("mode"), QStringLiteral("set")).toString().trimmed();
  if (r.scope != QLatin1String("global") && r.scope != QLatin1String("flow") &&
      r.scope != QLatin1String("module")) {
    r.error = QStringLiteral("变量作用域或名称无效");
    return r;
  }
  if (!validVarName(r.name)) {
    r.error = QStringLiteral("变量作用域或名称无效");
    return r;
  }
  QVariantMap* store = &flowVars;
  if (r.scope == QLatin1String("global"))
    store = &globalVars;
  else if (r.scope == QLatin1String("module"))
    store = &moduleVars;

  r.previous = store->value(r.name);
  QVariant value = params.contains(QStringLiteral("valueFrom"))
                       ? flowVars.value(params.value(QStringLiteral("valueFrom")).toString())
                       : params.value(QStringLiteral("value"));
  value = resolveAssignValue(value, flowVars);

  if (r.mode == QLatin1String("increment")) {
    bool vOk = false;
    const double add = value.toDouble(&vOk);
    if (!vOk) {
      r.error = QStringLiteral("累加操作只接受数字");
      return r;
    }
    if (store->contains(r.name)) {
      bool pOk = false;
      store->value(r.name).toDouble(&pOk);
      if (!pOk) {
        r.error = QStringLiteral("累加操作只接受数字");
        return r;
      }
    }
    const double prev = store->contains(r.name) ? store->value(r.name).toDouble() : 0.0;
    const double next = prev + add;
    // keep int if both were ints
    const bool keepInt = value.typeId() == QMetaType::Int ||
                         value.typeId() == QMetaType::LongLong ||
                         (value.typeId() == QMetaType::QString &&
                          value.toString() == QString::number(value.toInt()));
    r.value = keepInt && qFuzzyCompare(next, qRound(next)) ? QVariant(int(qRound(next)))
                                                           : QVariant(next);
  } else if (r.mode == QLatin1String("set")) {
    r.value = value;
  } else {
    r.error = QStringLiteral("未知变量操作");
    return r;
  }
  store->insert(r.name, r.value);
  r.ok = true;
  r.note = QStringLiteral("%1.%2 %3 → %4").arg(r.scope, r.name, r.mode, r.value.toString());
  return r;
}

QStringList flowExtrasSelfTest() {
  QStringList fails;
  auto check = [&](bool cond, const QString& msg) {
    if (!cond) fails << msg;
  };

  {
    const DelayResult r = runDelay({{QStringLiteral("milliseconds"), 5}});
    check(r.ok, QStringLiteral("delay 5 not ok: %1").arg(r.error));
    check(r.elapsedMs >= 5, QStringLiteral("delay elapsed %1").arg(r.elapsedMs));
    check(r.elapsedMs < 500, QStringLiteral("delay too slow %1").arg(r.elapsedMs));
    check(r.milliseconds == 5, QStringLiteral("delay ms field"));
  }
  {
    const DelayResult r = runDelay({{QStringLiteral("milliseconds"), 0}});
    check(r.ok, QStringLiteral("delay 0 not ok"));
  }
  {
    std::atomic<bool> cancel{true};
    const DelayResult r = runDelay({{QStringLiteral("milliseconds"), 1000}}, &cancel);
    check(!r.ok && r.cancelled, QStringLiteral("delay cancel should abort"));
  }
  {
    const DelayResult r = runDelay({{QStringLiteral("milliseconds"), 30001}});
    check(!r.ok, QStringLiteral("delay over limit should fail"));
  }

  {
    QVariantMap flow, global, module;
    const VarsAssignResult a = runVariables({{QStringLiteral("scope"), QStringLiteral("flow")},
                                             {QStringLiteral("name"), QStringLiteral("varsAssign")},
                                             {QStringLiteral("mode"), QStringLiteral("set")},
                                             {QStringLiteral("value"), 4242}},
                                            flow, global, module);
    check(a.ok && flow.value(QStringLiteral("varsAssign")).toInt() == 4242,
          QStringLiteral("vars set"));
    const VarsAssignResult b = runVariables({{QStringLiteral("scope"), QStringLiteral("flow")},
                                             {QStringLiteral("name"), QStringLiteral("varsAssign")},
                                             {QStringLiteral("mode"), QStringLiteral("increment")},
                                             {QStringLiteral("value"), 1}},
                                            flow, global, module);
    check(b.ok && flow.value(QStringLiteral("varsAssign")).toInt() == 4243,
          QStringLiteral("vars inc %1").arg(flow.value(QStringLiteral("varsAssign")).toString()));
  }
  {
    QVariantMap flow, global, module;
    flow.insert(QStringLiteral("src"), 7);
    const VarsAssignResult a = runVariables(
        {{QStringLiteral("name"), QStringLiteral("dst")},
         {QStringLiteral("mode"), QStringLiteral("set")},
         {QStringLiteral("value"), QStringLiteral("${flow.src}")}},
        flow, global, module);
    check(a.ok && flow.value(QStringLiteral("dst")).toInt() == 7,
          QStringLiteral("vars ref %1").arg(a.note));
  }
  {
    QVariantMap flow, global, module;
    const VarsAssignResult a = runVariables({{QStringLiteral("name"), QStringLiteral("bad-name")},
                                             {QStringLiteral("value"), 1}},
                                            flow, global, module);
    check(!a.ok, QStringLiteral("invalid name should fail"));
  }
  {
    QVariantMap flow, global, module;
    flow.insert(QStringLiteral("t"), QStringLiteral("abc"));
    const VarsAssignResult a = runVariables({{QStringLiteral("name"), QStringLiteral("t")},
                                             {QStringLiteral("mode"), QStringLiteral("increment")},
                                             {QStringLiteral("value"), 1}},
                                            flow, global, module);
    check(!a.ok, QStringLiteral("increment string should fail"));
  }
  {
    QVariantMap flow, global, module;
    const VarsAssignResult a = runVariables({{QStringLiteral("scope"), QStringLiteral("global")},
                                             {QStringLiteral("name"), QStringLiteral("g1")},
                                             {QStringLiteral("value"), 9}},
                                            flow, global, module);
    check(a.ok && global.value(QStringLiteral("g1")).toInt() == 9 && !flow.contains(QStringLiteral("g1")),
          QStringLiteral("global scope"));
  }

  return fails;
}

}  // namespace sieans_qt
