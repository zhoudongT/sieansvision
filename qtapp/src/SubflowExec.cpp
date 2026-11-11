#include "SubflowExec.hpp"

#include "ConditionEval.hpp"
#include "ExprEval.hpp"
#include "CommHub.hpp"

#include <QQueue>
#include <QSet>
#include <QHash>
#include <QRegularExpression>
#include <QUuid>

namespace sieans_qt {
namespace {

constexpr int kMaxDepth = 4;
constexpr int kMaxVisits = 1000;
constexpr int kMaxIterations = 100;
constexpr int kMaxNodes = 50;

QStringList topologicalIds(const QVector<FlowStep>& steps, const QVector<FlowEdge>& edges) {
  QStringList ordered;
  QSet<QString> visited;
  QHash<QString, QStringList> outs;
  QHash<QString, int> indeg;
  for (const FlowStep& s : steps) indeg[s.id] = 0;
  for (const FlowEdge& e : edges) {
    if (e.from.isEmpty() || e.to.isEmpty()) continue;
    outs[e.from] << e.to;
    if (indeg.contains(e.to)) indeg[e.to] += 1;
  }
  QQueue<QString> q;
  q.enqueue(QStringLiteral("source"));
  for (const FlowStep& s : steps) {
    if (indeg.value(s.id, 0) == 0) q.enqueue(s.id);
  }
  while (!q.isEmpty()) {
    const QString id = q.dequeue();
    if (visited.contains(id)) continue;
    visited.insert(id);
    if (id != QLatin1String("source")) ordered << id;
    for (const QString& n : outs.value(id)) {
      if (!indeg.contains(n)) continue;
      indeg[n] -= 1;
      if (indeg[n] <= 0) q.enqueue(n);
    }
  }
  for (const FlowStep& s : steps) {
    if (!visited.contains(s.id)) ordered << s.id;
  }
  return ordered;
}

const FlowStep* findStep(const QVector<FlowStep>& steps, const QString& id) {
  for (const FlowStep& s : steps)
    if (s.id == id) return &s;
  return nullptr;
}

const SubflowDef* findDef(const QVector<SubflowDef>& library, const QString& id) {
  for (const SubflowDef& d : library)
    if (d.id == id || d.name == id) return &d;
  return nullptr;
}

QString expandTemplate(const QString& tmpl, const QVariantMap& vars) {
  return CommHub::expandTemplate(tmpl, vars);
}

bool validArgName(const QString& name) {
  static const QRegularExpression re(QStringLiteral("^[A-Za-z_][A-Za-z0-9_]{0,63}$"));
  return re.match(name).hasMatch() && name != QLatin1String("_iteration") &&
         name != QLatin1String("_iterations");
}

QVariant tokenToVariant(const QString& raw, const QVariantMap& vars, QString* err) {
  const ConditionValue v = resolveConditionToken(raw, vars);
  if (v.kind == ConditionValue::Missing) {
    if (err) *err = QStringLiteral("引用缺失: %1").arg(v.source);
    return {};
  }
  if (v.kind == ConditionValue::Number) return v.number;
  if (v.kind == ConditionValue::Boolean) return v.boolean;
  if (v.kind == ConditionValue::Null) return {};
  return v.string;
}

struct NodeExec {
  bool executed = false;
  bool skipped = false;
  bool ok = true;
  bool passed = false;
  bool evalFailed = false;
  QString branchTaken;
  QVariantMap result;
};

struct GraphOut {
  bool ok = true;
  QString error;
  QVariantMap localVars;
  QVariantMap outputValue;
  bool passed = false;
  QString outputId;
  QString note;
};

GraphOut runInnerGraph(const SubflowDef& def, const QVector<SubflowDef>& library,
                       QVariantMap vars, int depth, int& visitCount,
                       const QStringList& callStack);

bool isBoolVariant(const QVariant& v) { return v.typeId() == QMetaType::Bool; }

GraphOut runInnerGraph(const SubflowDef& def, const QVector<SubflowDef>& library,
                       QVariantMap vars, int depth, int& visitCount,
                       const QStringList& callStack) {
  GraphOut out;
  out.localVars = vars;
  if (def.steps.size() > kMaxNodes) {
    out.ok = false;
    out.error = QStringLiteral("子流程最多 50 个节点");
    return out;
  }

  struct NodeExecInfo : NodeExec {};
  QHash<QString, NodeExec> execInfo;
  {
    NodeExec src;
    src.executed = true;
    src.ok = true;
    execInfo.insert(QStringLiteral("source"), src);
  }

  auto edgeFires = [&](const FlowEdge& e) -> bool {
    if (e.from == QLatin1String("source")) return true;
    const NodeExec up = execInfo.value(e.from);
    if (!up.executed || up.skipped) return false;
    const QString when = e.when.isEmpty() ? QStringLiteral("always") : e.when;
    if (when == QLatin1String("always")) return true;
    if (up.evalFailed &&
        (when == QLatin1String("true") || when == QLatin1String("false")))
      return false;
    if (when == QLatin1String("success")) return up.ok;
    if (when == QLatin1String("error")) return !up.ok;
    if (when == QLatin1String("true")) return up.passed;
    if (when == QLatin1String("false")) return !up.passed;
    return up.branchTaken == when;
  };

  const QStringList order = topologicalIds(def.steps, def.edges);
  QStringList notes;
  QHash<QString, StepSnap> snaps;

  for (const QString& id : order) {
    const FlowStep* step = findStep(def.steps, id);
    if (!step) continue;
    ++visitCount;
    if (visitCount > kMaxVisits) {
      out.ok = false;
      out.error = QStringLiteral("整轮节点访问超过 1000 次");
      return out;
    }

    QVector<FlowEdge> incoming;
    for (const FlowEdge& e : def.edges)
      if (e.to == id) incoming.push_back(e);

    bool activate = true;
    QString mergeFromId;
    const QString op = step->operation;
    if (!incoming.isEmpty()) {
      if (op == QLatin1String("branch_merge")) {
        int live = 0;
        for (const FlowEdge& e : incoming) {
          if (edgeFires(e)) {
            ++live;
            mergeFromId = e.from;
          }
        }
        if (live == 0) {
          activate = false;
        } else if (live > 1) {
          out.ok = false;
          out.error = QStringLiteral("%1: 多路同时激活，汇合失败").arg(step->name);
          return out;
        }
      } else {
        for (const FlowEdge& e : incoming) {
          if (!edgeFires(e)) {
            activate = false;
            break;
          }
        }
      }
    }
    if (!activate) {
      NodeExec sk;
      sk.skipped = true;
      execInfo.insert(id, sk);
      continue;
    }

    bool ok = true;
    QString note;
    NodeExec nx;
    nx.executed = true;

    if (op == QLatin1String("var_calc")) {
      ExprEval ev;
      ev.setVars(vars);
      ev.setSteps(snaps);
      const QVariantList rows = step->params.value(QStringLiteral("expressions")).toList();
      for (const QVariant& rv : rows) {
        const QVariantMap row = rv.toMap();
        if (row.contains(QStringLiteral("enabled")) &&
            !row.value(QStringLiteral("enabled")).toBool())
          continue;
        const QString name = row.value(QStringLiteral("name")).toString();
        QString expr = row.value(QStringLiteral("expr")).toString();
        if (expr.isEmpty()) expr = row.value(QStringLiteral("expression")).toString();
        if (name.isEmpty()) continue;
        QString err;
        QVariant val = ev.eval(expr, &err);
        if (!err.isEmpty()) {
          out.ok = false;
          out.error = QStringLiteral("%1: %2").arg(step->name, err);
          return out;
        }
        vars.insert(name, val);
        ev.setVars(vars);
      }
      note = QStringLiteral("变量计算");
    } else if (op == QLatin1String("format_data")) {
      QString tmpl = step->params.value(QStringLiteral("template")).toString();
      QString outv = expandTemplate(tmpl, vars);
      const QString emptyDef = step->params.value(QStringLiteral("emptyDefault")).toString();
      if (outv.isEmpty() && !emptyDef.isEmpty()) outv = emptyDef;
      const QString target =
          step->params.value(QStringLiteral("targetVar"), QStringLiteral("formatted"))
              .toString();
      vars.insert(target, outv);
      if (target == QLatin1String("formatted") || target.isEmpty())
        vars.insert(QStringLiteral("formatted"), outv);
      note = outv.left(80);
    } else if (op == QLatin1String("result_gate")) {
      const int minC = step->params.value(QStringLiteral("minCount"), 1).toInt();
      const QString srcVar =
          step->params.value(QStringLiteral("sourceVar"), QStringLiteral("barcodeCount"))
              .toString();
      const QString passVar =
          step->params.value(QStringLiteral("passVar"), QStringLiteral("passGate"))
              .toString();
      const int count = vars.value(srcVar).toInt();
      const bool gate = count >= minC;
      vars.insert(passVar, gate ? 1 : 0);
      nx.passed = gate;
      ok = gate;
      note = QStringLiteral("gate %1").arg(gate ? 1 : 0);
    } else if (op == QLatin1String("condition") || op == QLatin1String("branch")) {
      const ConditionResult cr = (op == QLatin1String("branch"))
                                     ? evaluateBranch(step->params, vars)
                                     : evaluateCondition(step->params, vars);
      if (!cr.ok) {
        ok = false;
        nx.evalFailed = true;
        nx.ok = false;
        vars.insert(QStringLiteral("conditionOk"), 0);
        vars.insert(QStringLiteral("conditionPassed"), 0);
        vars.insert(QStringLiteral("passed"), false);
        execInfo.insert(id, nx);
        out.ok = false;
        out.error = QStringLiteral("%1: %2").arg(step->name, cr.error);
        out.localVars = vars;
        return out;
      }
      ok = true;
      nx.passed = cr.passed;
      nx.branchTaken = cr.branchTaken;
      vars.insert(QStringLiteral("conditionOk"), 1);
      vars.insert(QStringLiteral("conditionPassed"), cr.passed ? 1 : 0);
      vars.insert(QStringLiteral("passed"), cr.passed);  // boolean for until-stop
      vars.insert(QStringLiteral("branchTaken"), cr.branchTaken);
      const bool writeGate =
          !step->params.contains(QStringLiteral("writePassGate")) ||
          step->params.value(QStringLiteral("writePassGate")).toBool();
      if (writeGate && op == QLatin1String("condition"))
        vars.insert(QStringLiteral("passGate"), cr.passed ? 1 : 0);
      note = cr.note;
      nx.result.insert(QStringLiteral("passed"), cr.passed);
      nx.result.insert(QStringLiteral("branchTaken"), cr.branchTaken);
    } else if (op == QLatin1String("branch_merge")) {
      const FlowStep* src = findStep(def.steps, mergeFromId);
      vars.insert(QStringLiteral("mergeFrom"), src ? src->name : mergeFromId);
      note = QStringLiteral("汇合自 %1").arg(src ? src->name : mergeFromId);
      if (execInfo.contains(mergeFromId)) {
        nx.passed = execInfo.value(mergeFromId).passed;
        nx.result = execInfo.value(mergeFromId).result;
      }
    } else if (op == QLatin1String("subflow") || op == QLatin1String("loop")) {
      const SubflowCallParams cp = parseSubflowParams(step->params, op == QLatin1String("loop"));
      const SubflowDef* inner = findDef(library, cp.subflowId);
      if (!inner) {
        out.ok = false;
        out.error = cp.subflowId.isEmpty() ? QStringLiteral("请选择子流程")
                                           : QStringLiteral("子流程不存在: %1").arg(cp.subflowId);
        return out;
      }
      SubflowResult r = runSubflowCall(*inner, library, cp, vars, nullptr, depth + 1,
                                       visitCount, callStack);
      if (!r.ok) {
        out.ok = false;
        out.error = r.error;
        return out;
      }
      nx.passed = r.passed;
      nx.result = r.value;
      vars.insert(QStringLiteral("subflowPassed"), r.passed);
      vars.insert(QStringLiteral("passed"), r.passed);
      note = r.note;
    } else {
      // camera / barcode / etc. are no-ops inside the isolated exec
      note = QStringLiteral("透传");
    }

    nx.ok = ok;
    execInfo.insert(id, nx);
    notes << QStringLiteral("%1:%2").arg(step->name, note);
    if (!ok) {
      out.ok = false;
      out.error = QStringLiteral("%1 失败").arg(step->name);
      out.localVars = vars;
      return out;
    }
  }

  out.ok = true;
  out.localVars = vars;
  out.note = notes.join(QLatin1Char(' '));
  if (!def.outputNode.isEmpty()) {
    const NodeExec n = execInfo.value(def.outputNode);
    if (n.skipped || !n.executed) {
      out.ok = false;
      out.error = QStringLiteral("输出节点未激活或失败");
      return out;
    }
    if (!n.ok) {
      out.ok = false;
      out.error = QStringLiteral("输出节点失败");
      return out;
    }
    out.outputId = def.outputNode;
    out.outputValue = n.result;
    if (!out.outputValue.contains(QStringLiteral("passed"))) {
      if (vars.contains(QStringLiteral("passed")) &&
          vars.value(QStringLiteral("passed")).typeId() == QMetaType::Bool)
        out.outputValue.insert(QStringLiteral("passed"),
                               vars.value(QStringLiteral("passed")));
      else
        out.outputValue.insert(QStringLiteral("passed"), n.passed);
    }
    out.passed = out.outputValue.value(QStringLiteral("passed")).toBool();
  } else if (!def.steps.isEmpty()) {
    out.error = QString();  // no output node: still success, no passed field
  }
  return out;
}

}  // namespace

SubflowCallParams parseSubflowParams(const QVariantMap& params, bool isLoop) {
  SubflowCallParams p;
  p.subflowId = params.value(QStringLiteral("subflowId")).toString();
  {
    const QVariant rawArgs = params.value(QStringLiteral("arguments"));
    if (rawArgs.typeId() == QMetaType::QVariantList) {
      for (const QVariant& rv : rawArgs.toList()) {
        const QVariantMap row = rv.toMap();
        const QString name = row.value(QStringLiteral("name")).toString().trimmed();
        if (name.isEmpty()) continue;
        p.arguments.insert(name, row.value(QStringLiteral("value")));
      }
    } else {
      p.arguments = rawArgs.toMap();
    }
  }
  p.stateMode = params.value(QStringLiteral("stateMode"), QStringLiteral("reset")).toString();
  if (isLoop) {
    p.mode = params.value(QStringLiteral("mode"), QStringLiteral("count")).toString();
    p.iterations = params.value(QStringLiteral("iterations"), 1).toInt();
    p.frameMode =
        params.value(QStringLiteral("frameMode"), QStringLiteral("previous")).toString();
    p.stopField =
        params.value(QStringLiteral("stopField"), QStringLiteral("passed")).toString();
    if (params.contains(QStringLiteral("stopValue")))
      p.stopValue = params.value(QStringLiteral("stopValue"));
  } else {
    p.mode = QStringLiteral("count");
    p.iterations = 1;
  }
  return p;
}

SubflowDef makeCounterSubflow() {
  SubflowDef d;
  d.id = QStringLiteral("counter");
  d.name = QStringLiteral("计数子流程");
  d.outputNode = QStringLiteral("done");
  d.variables.insert(QStringLiteral("count"), 0);
  d.variables.insert(QStringLiteral("limit"), 3);
  FlowStep inc;
  inc.id = QStringLiteral("inc");
  inc.name = QStringLiteral("计数加一");
  inc.operation = QStringLiteral("var_calc");
  inc.position = QPointF(300, 140);
  inc.params = {
      {QStringLiteral("scope"), QStringLiteral("flow")},
      {QStringLiteral("expressions"),
       QVariantList{QVariantMap{{QStringLiteral("name"), QStringLiteral("count")},
                                {QStringLiteral("expr"), QStringLiteral("count + 1")},
                                {QStringLiteral("enabled"), true}}}},
  };
  FlowStep done;
  done.id = QStringLiteral("done");
  done.name = QStringLiteral("是否达到上限");
  done.operation = QStringLiteral("condition");
  done.position = QPointF(300, 260);
  done.imageFrom = QStringLiteral("inc");
  done.params = {
      {QStringLiteral("logic"), QStringLiteral("and")},
      {QStringLiteral("comparison"), QStringLiteral("gte")},
      {QStringLiteral("left"), QStringLiteral("count")},
      {QStringLiteral("right"), QStringLiteral("limit")},
      {QStringLiteral("writePassGate"), false},
      {QStringLiteral("rules"),
       QVariantList{QVariantMap{{QStringLiteral("left"), QStringLiteral("count")},
                                {QStringLiteral("comparison"), QStringLiteral("gte")},
                                {QStringLiteral("right"), QStringLiteral("limit")},
                                {QStringLiteral("enabled"), true}}}},
  };
  d.steps << inc << done;
  FlowEdge e1;
  e1.id = QStringLiteral("e-src-inc");
  e1.from = QStringLiteral("source");
  e1.to = QStringLiteral("inc");
  FlowEdge e2;
  e2.id = QStringLiteral("e-inc-done");
  e2.from = QStringLiteral("inc");
  e2.to = QStringLiteral("done");
  d.edges << e1 << e2;
  return d;
}

SubflowResult runSubflowCall(const SubflowDef& def,
                             const QVector<SubflowDef>& library,
                             const SubflowCallParams& params,
                             const QVariantMap& parentVars,
                             SubflowState* state,
                             int depth,
                             int& visitCount,
                             const QStringList& callStack) {
  SubflowResult r;
  r.subflowId = def.id;
  r.subflowName = def.name;

  if (params.subflowId.isEmpty() && def.id.isEmpty()) {
    r.error = QStringLiteral("请选择子流程");
    return r;
  }
  if (depth >= kMaxDepth) {
    r.error = QStringLiteral("同一作业最多 4 层调用");
    return r;
  }
  if (callStack.contains(def.id)) {
    r.error = QStringLiteral("禁止直接或间接递归: %1").arg(def.name);
    return r;
  }
  if (params.stateMode != QLatin1String("reset") &&
      params.stateMode != QLatin1String("preserve")) {
    r.error = QStringLiteral("子流程状态、图像或循环模式无效");
    return r;
  }
  if (params.mode != QLatin1String("count") && params.mode != QLatin1String("until")) {
    r.error = QStringLiteral("子流程状态、图像或循环模式无效");
    return r;
  }
  if (params.frameMode != QLatin1String("original") &&
      params.frameMode != QLatin1String("previous")) {
    r.error = QStringLiteral("子流程状态、图像或循环模式无效");
    return r;
  }

  const int count = (params.mode == QLatin1String("count") && params.iterations == 0)
                        ? 0
                        : params.iterations;
  const bool isLoop = (count != 1 || params.mode == QLatin1String("until"));
  const int rounds = isLoop ? params.iterations : 1;
  if (rounds < 1 || rounds > kMaxIterations) {
    r.error = QStringLiteral("循环次数须为 1–100");
    return r;
  }

  for (auto it = params.arguments.constBegin(); it != params.arguments.constEnd(); ++it) {
    if (!validArgName(it.key())) {
      r.error = QStringLiteral("子流程输入变量名称无效或占用了只读轮次变量");
      return r;
    }
  }

  QVariantMap local;
  if (params.stateMode == QLatin1String("preserve") && state &&
      state->definitionId == def.id) {
    local = state->flow;
  } else {
    local = def.variables;
  }

  for (auto it = params.arguments.constBegin(); it != params.arguments.constEnd(); ++it) {
    QString err;
    QVariant val = it.value();
    if (val.typeId() == QMetaType::QString) {
      val = tokenToVariant(val.toString(), parentVars, &err);
      if (!err.isEmpty()) {
        r.error = err;
        return r;
      }
    }
    local.insert(it.key(), val);
  }

  QStringList stack = callStack;
  stack << def.id;
  bool stopped = false;
  int completed = 0;
  GraphOut last;
  last.ok = true;

  for (int i = 1; i <= rounds; ++i) {
    local.insert(QStringLiteral("_iteration"), i);
    local.insert(QStringLiteral("_iterations"), rounds);
    last = runInnerGraph(def, library, local, depth, visitCount, stack);
    if (!last.ok) {
      r.error = def.name + QStringLiteral(" · 第 %1 轮：%2").arg(i).arg(last.error);
      r.completedIterations = completed;
      r.visitCount = visitCount;
      return r;
    }
    local = last.localVars;
    local.remove(QStringLiteral("_iteration"));
    local.remove(QStringLiteral("_iterations"));
    ++completed;

    if (params.mode == QLatin1String("until")) {
      if (!last.outputValue.contains(params.stopField)) {
        r.error = QStringLiteral("停止条件字段不存在: %1").arg(params.stopField);
        r.completedIterations = completed;
        return r;
      }
      const QVariant field = last.outputValue.value(params.stopField);
      if (!isBoolVariant(field)) {
        r.error = QStringLiteral("停止条件字段必须为开关（布尔）值");
        r.completedIterations = completed;
        return r;
      }
      const bool want = params.stopValue.isValid() ? params.stopValue.toBool() : true;
      if (field.toBool() == want) {
        stopped = true;
        break;
      }
    }
  }

  if (params.mode == QLatin1String("until") && !stopped) {
    r.error = QStringLiteral("循环达到最大轮数，仍未满足停止条件");
    r.completedIterations = completed;
    r.visitCount = visitCount;
    return r;
  }

  if (state) {
    state->definitionId = def.id;
    state->flow = local;
  }

  r.ok = true;
  r.completedIterations = completed;
  r.stoppedEarly = stopped && completed < rounds;
  r.passed = last.passed;
  r.value = last.outputValue;
  if (!r.value.contains(QStringLiteral("count")) && local.contains(QStringLiteral("count")))
    r.value.insert(QStringLiteral("count"), local.value(QStringLiteral("count")));
  r.localVars = local;
  r.visitCount = visitCount;
  r.note = QStringLiteral("%1 · %2 轮%3")
               .arg(def.name)
               .arg(completed)
               .arg(r.stoppedEarly ? QStringLiteral(" · 提前停止") : QString());
  return r;
}

QStringList subflowSelfTest() {
  QStringList fails;
  auto expect = [&](bool cond, const char* msg) {
    if (!cond) fails << QString::fromUtf8(msg);
  };

  const SubflowDef counter = makeCounterSubflow();
  QVector<SubflowDef> lib{counter};

  // single call isolates parent and increments once
  {
    QVariantMap parent{{QStringLiteral("count"), 99}};
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.stateMode = QStringLiteral("reset");
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, parent, nullptr, 0, visits, {});
    expect(r.ok, "single call ok");
    expect(r.completedIterations == 1, "single call 1 iter");
    expect(r.localVars.value(QStringLiteral("count")).toInt() == 1, "count==1");
    expect(!r.passed, "1>=3 is false");
    expect(parent.value(QStringLiteral("count")).toInt() == 99, "parent isolated");
  }

  // arguments override
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.arguments.insert(QStringLiteral("count"), 4);
    p.arguments.insert(QStringLiteral("limit"), 5);
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, {}, nullptr, 0, visits, {});
    expect(r.ok && r.localVars.value(QStringLiteral("count")).toInt() == 5, "args count 5");
    expect(r.passed, "4+1>=5 passed");
  }

  // until loop stops at 3
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.mode = QStringLiteral("until");
    p.iterations = 10;
    p.stopField = QStringLiteral("passed");
    p.stopValue = true;
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, {}, nullptr, 0, visits, {});
    expect(r.ok, "until ok");
    expect(r.completedIterations == 3, "until stops at 3");
    expect(r.stoppedEarly, "until early stop");
    expect(r.passed && r.localVars.value(QStringLiteral("count")).toInt() == 3,
           "until count==3");
  }

  // fixed count
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.mode = QStringLiteral("count");
    p.iterations = 5;
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, {}, nullptr, 0, visits, {});
    expect(r.ok && r.completedIterations == 5, "count 5");
    expect(r.localVars.value(QStringLiteral("count")).toInt() == 5, "count mode count==5");
    expect(!r.stoppedEarly, "count not early");
  }

  // until exhaustion fails
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.mode = QStringLiteral("until");
    p.iterations = 2;
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, {}, nullptr, 0, visits, {});
    expect(!r.ok && r.error.contains(QStringLiteral("最大轮数")), "until exhaust");
  }

  // reserved arg name
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.arguments.insert(QStringLiteral("_iteration"), 99);
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, {}, nullptr, 0, visits, {});
    expect(!r.ok && r.error.contains(QStringLiteral("只读轮次")), "reserved arg");
  }

  // iterations bounds
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.mode = QStringLiteral("count");
    p.iterations = 0;
    int visits = 0;
    const SubflowResult r =
        runSubflowCall(counter, lib, p, {}, nullptr, 0, visits, {});
    expect(!r.ok && r.error.contains(QStringLiteral("1–100")), "iter 0 invalid");
  }

  // preserve state across two calls
  {
    SubflowCallParams p;
    p.subflowId = QStringLiteral("counter");
    p.stateMode = QStringLiteral("preserve");
    SubflowState st;
    int visits = 0;
    const SubflowResult a =
        runSubflowCall(counter, lib, p, {}, &st, 0, visits, {});
    visits = 0;
    const SubflowResult b =
        runSubflowCall(counter, lib, p, {}, &st, 0, visits, {});
    expect(a.ok && b.ok, "preserve ok");
    expect(a.localVars.value(QStringLiteral("count")).toInt() == 1, "preserve first 1");
    expect(b.localVars.value(QStringLiteral("count")).toInt() == 2, "preserve second 2");
  }

  // recursion rejected
  {
    SubflowDef self;
    self.id = QStringLiteral("self");
    self.name = QStringLiteral("self");
    FlowStep c;
    c.id = QStringLiteral("call");
    c.name = QStringLiteral("call");
    c.operation = QStringLiteral("subflow");
    c.params.insert(QStringLiteral("subflowId"), QStringLiteral("self"));
    self.steps << c;
    self.outputNode = QStringLiteral("call");
    QVector<SubflowDef> lib2{self};
    SubflowCallParams p;
    p.subflowId = QStringLiteral("self");
    int visits = 0;
    const SubflowResult r = runSubflowCall(self, lib2, p, {}, nullptr, 0, visits, {});
    expect(!r.ok && r.error.contains(QStringLiteral("递归")), "recursion");
  }

  return fails;
}

}  // namespace sieans_qt
