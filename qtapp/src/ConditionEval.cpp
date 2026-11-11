#include "ConditionEval.hpp"

#include <QRegularExpression>
#include <cmath>

namespace sieans_qt {
namespace {

bool isFiniteNumber(double v) { return std::isfinite(v); }

bool looksLikeIdentifier(const QString& s) {
  if (s.isEmpty()) return false;
  const QChar c0 = s[0];
  if (!(c0.isLetter() || c0 == QLatin1Char('_'))) return false;
  for (int i = 1; i < s.size(); ++i) {
    const QChar c = s[i];
    if (!(c.isLetterOrNumber() || c == QLatin1Char('_') || c == QLatin1Char('.') ||
          c == QLatin1Char('/')))
      return false;
  }
  return true;
}

bool parseNumberLiteral(const QString& s, double* out) {
  if (s.isEmpty() || !out) return false;
  bool ok = false;
  const double v = s.toDouble(&ok);
  if (!ok || !isFiniteNumber(v)) return false;
  *out = v;
  return true;
}

QString valueAsString(const ConditionValue& v) {
  if (v.kind == ConditionValue::String) return v.string;
  if (v.kind == ConditionValue::Number) {
    if (std::floor(v.number) == v.number && std::fabs(v.number) < 1e15)
      return QString::number(static_cast<qint64>(v.number));
    return QString::number(v.number, 'g', 15);
  }
  if (v.kind == ConditionValue::Boolean)
    return v.boolean ? QStringLiteral("true") : QStringLiteral("false");
  return {};
}

ConditionValue fromVariant(const QVariant& v, const QString& source) {
  ConditionValue out;
  out.source = source;
  if (!v.isValid() || v.isNull()) {
    out.kind = ConditionValue::Null;
    return out;
  }
  const int tid = v.typeId();
  if (tid == QMetaType::Bool) {
    out.kind = ConditionValue::Boolean;
    out.boolean = v.toBool();
    return out;
  }
  if (tid == QMetaType::Int || tid == QMetaType::UInt || tid == QMetaType::LongLong ||
      tid == QMetaType::ULongLong || tid == QMetaType::Double || tid == QMetaType::Float) {
    const double n = v.toDouble();
    if (!isFiniteNumber(n)) {
      out.kind = ConditionValue::Missing;
      return out;
    }
    out.kind = ConditionValue::Number;
    out.number = n;
    return out;
  }
  if (tid == QMetaType::QVariantMap || tid == QMetaType::QVariantList) {
    out.kind = ConditionValue::Missing;
    out.source = source + QStringLiteral(" (结构化值)");
    return out;
  }
  out.kind = ConditionValue::String;
  out.string = v.toString();
  return out;
}

QVariant lookupVar(const QVariantMap& vars, const QString& keyIn) {
  QString key = keyIn;
  if (vars.contains(key)) return vars.value(key);
  if (key.startsWith(QStringLiteral("flow."))) {
    const QString k = key.mid(5);
    if (vars.contains(k)) return vars.value(k);
  }
  if (key.startsWith(QStringLiteral("vars."))) {
    const QString k = key.mid(5);
    if (vars.contains(k)) return vars.value(k);
  }
  if (key.startsWith(QStringLiteral("host.")) && vars.contains(key))
    return vars.value(key);
  if (key.contains(QLatin1Char('.'))) {
    const QString field = key.section(QLatin1Char('.'), -1);
    if (vars.contains(field)) return vars.value(field);
  }
  return {};
}

bool isSwitchTrue(const ConditionValue& v, QString* error) {
  if (v.kind == ConditionValue::Boolean) return v.boolean;
  if (v.kind == ConditionValue::Number) {
    if (v.number == 1.0) return true;
    if (v.number == 0.0) return false;
    if (error)
      *error = QStringLiteral("开关判断要求布尔或 0/1，得到数值 %1").arg(v.number);
    return false;
  }
  if (v.kind == ConditionValue::String) {
    const QString s = v.string.trimmed().toLower();
    if (s == QLatin1String("true") || s == QLatin1String("yes") || s == QLatin1String("ok") ||
        s == QLatin1String("y") || s == QLatin1String("1"))
      return true;
    if (s == QLatin1String("false") || s == QLatin1String("no") || s == QLatin1String("ng") ||
        s == QLatin1String("n") || s == QLatin1String("0") || s.isEmpty())
      return false;
    if (error)
      *error = QStringLiteral("开关判断要求布尔值，得到文本 %1").arg(v.string);
    return false;
  }
  if (error) *error = QStringLiteral("开关判断要求布尔值，左侧无效");
  return false;
}

QVariantList rulesFromParams(const QVariantMap& params) {
  QVariantList rules = params.value(QStringLiteral("rules")).toList();
  if (rules.isEmpty()) {
    QVariantMap r;
    r.insert(QStringLiteral("left"), params.value(QStringLiteral("left"), 0));
    r.insert(QStringLiteral("comparison"),
             params.value(QStringLiteral("comparison"), QStringLiteral("eq")));
    r.insert(QStringLiteral("right"), params.value(QStringLiteral("right"), 0));
    r.insert(QStringLiteral("enabled"), true);
    rules.push_back(r);
  }
  return rules;
}

QString tokenText(const QVariant& v) {
  if (v.typeId() == QMetaType::Bool)
    return v.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  return v.toString();
}

ConditionResult evalOneRule(const QVariantMap& rule, const QVariantMap& vars) {
  ConditionResult r;
  const QString cmp =
      rule.value(QStringLiteral("comparison"), QStringLiteral("eq")).toString();
  const ConditionValue left = resolveConditionToken(tokenText(rule.value(QStringLiteral("left"))),
                                                    vars);
  const ConditionValue right =
      resolveConditionToken(tokenText(rule.value(QStringLiteral("right"))), vars);
  QString err;
  const bool passed = compareCondition(left, cmp, right, &err);
  if (!err.isEmpty()) {
    r.ok = false;
    r.error = err;
    r.note = err;
    return r;
  }
  r.ok = true;
  r.passed = passed;
  r.note = QStringLiteral("%1 %2 %3 → %4")
               .arg(left.source, cmp, right.source, passed ? QStringLiteral("成立")
                                                            : QStringLiteral("不成立"));
  return r;
}

}  // namespace

ConditionValue resolveConditionToken(const QString& raw, const QVariantMap& vars) {
  ConditionValue out;
  const QString s = raw.trimmed();
  out.source = s;
  if (s.isEmpty()) {
    out.kind = ConditionValue::Null;
    return out;
  }

  auto resolveKey = [&](QString key) -> ConditionValue {
    key = key.trimmed();
    if (key.startsWith(QStringLiteral("flow."))) key = key.mid(5);
    if (key.startsWith(QStringLiteral("vars."))) key = key.mid(5);
    const QVariant found = lookupVar(vars, key);
    if (!found.isValid()) {
      ConditionValue miss;
      miss.kind = ConditionValue::Missing;
      miss.source = key;
      return miss;
    }
    return fromVariant(found, key);
  };

  if (s.startsWith(QStringLiteral("${")) && s.endsWith(QLatin1Char('}')))
    return resolveKey(s.mid(2, s.size() - 3));
  if (s.startsWith(QLatin1Char('{')) && s.endsWith(QLatin1Char('}')) &&
      !s.startsWith(QStringLiteral("{{")))
    return resolveKey(s.mid(1, s.size() - 2));

  if ((s.size() >= 2) && ((s.startsWith(QLatin1Char('"')) && s.endsWith(QLatin1Char('"'))) ||
                          (s.startsWith(QLatin1Char('\'')) && s.endsWith(QLatin1Char('\''))))) {
    out.kind = ConditionValue::String;
    out.string = s.mid(1, s.size() - 2);
    return out;
  }

  const QString lower = s.toLower();
  if (lower == QLatin1String("true") || lower == QLatin1String("yes")) {
    out.kind = ConditionValue::Boolean;
    out.boolean = true;
    return out;
  }
  if (lower == QLatin1String("false") || lower == QLatin1String("no")) {
    out.kind = ConditionValue::Boolean;
    out.boolean = false;
    return out;
  }

  double num = 0;
  if (parseNumberLiteral(s, &num) && !looksLikeIdentifier(s)) {
    out.kind = ConditionValue::Number;
    out.number = num;
    return out;
  }

  if (looksLikeIdentifier(s)) return resolveKey(s);

  out.kind = ConditionValue::String;
  out.string = s;
  return out;
}

bool compareCondition(const ConditionValue& left, const QString& comparison,
                      const ConditionValue& right, QString* error) {
  const QString cmp = comparison.isEmpty() ? QStringLiteral("eq") : comparison;
  if (left.kind == ConditionValue::Missing) {
    if (error) *error = QStringLiteral("引用缺失: %1").arg(left.source);
    return false;
  }
  const bool needsRight = cmp != QLatin1String("empty") && cmp != QLatin1String("not_empty") &&
                          cmp != QLatin1String("is_true") && cmp != QLatin1String("is_false");
  if (needsRight && right.kind == ConditionValue::Missing) {
    if (error) *error = QStringLiteral("引用缺失: %1").arg(right.source);
    return false;
  }

  if (cmp == QLatin1String("empty") || cmp == QLatin1String("not_empty")) {
    bool empty = false;
    if (left.kind == ConditionValue::Null) empty = true;
    else if (left.kind == ConditionValue::String) empty = left.string.trimmed().isEmpty();
    else empty = false;
    return (cmp == QLatin1String("empty")) ? empty : !empty;
  }
  if (cmp == QLatin1String("is_true") || cmp == QLatin1String("is_false")) {
    QString swErr;
    const bool truth = isSwitchTrue(left, &swErr);
    if (!swErr.isEmpty()) {
      if (error) *error = swErr;
      return false;
    }
    return (cmp == QLatin1String("is_true")) ? truth : !truth;
  }
  if (cmp == QLatin1String("eq") || cmp == QLatin1String("ne")) {
    bool eq = false;
    if (left.kind != right.kind) {
      eq = false;
    } else if (left.kind == ConditionValue::Number) {
      eq = left.number == right.number;
    } else if (left.kind == ConditionValue::Boolean) {
      eq = left.boolean == right.boolean;
    } else if (left.kind == ConditionValue::Null) {
      eq = true;
    } else {
      eq = left.string == right.string;
    }
    return (cmp == QLatin1String("eq")) ? eq : !eq;
  }
  if (cmp == QLatin1String("gt") || cmp == QLatin1String("gte") || cmp == QLatin1String("lt") ||
      cmp == QLatin1String("lte")) {
    if (left.kind != ConditionValue::Number || right.kind != ConditionValue::Number ||
        !isFiniteNumber(left.number) || !isFiniteNumber(right.number)) {
      if (error) *error = QStringLiteral("大小比较只接受有限数值");
      return false;
    }
    const double a = left.number;
    const double b = right.number;
    if (cmp == QLatin1String("gt")) return a > b;
    if (cmp == QLatin1String("gte")) return a >= b;
    if (cmp == QLatin1String("lt")) return a < b;
    return a <= b;
  }
  if (cmp == QLatin1String("contains")) {
    return valueAsString(left).contains(valueAsString(right));
  }
  if (cmp == QLatin1String("starts_with")) {
    return valueAsString(left).startsWith(valueAsString(right));
  }
  if (cmp == QLatin1String("ends_with")) {
    return valueAsString(left).endsWith(valueAsString(right));
  }
  if (cmp == QLatin1String("regex")) {
    const QRegularExpression re(valueAsString(right));
    if (!re.isValid()) {
      if (error) *error = QStringLiteral("正则无效: %1").arg(valueAsString(right));
      return false;
    }
    return re.match(valueAsString(left)).hasMatch();
  }
  if (error) *error = QStringLiteral("未知比较方式: %1").arg(cmp);
  return false;
}

ConditionResult evaluateCondition(const QVariantMap& params, const QVariantMap& vars) {
  ConditionResult out;
  const QString logic =
      params.value(QStringLiteral("logic"), QStringLiteral("and")).toString().toLower();
  const QVariantList rules = rulesFromParams(params);
  int used = 0;
  bool acc = (logic != QLatin1String("or"));
  QStringList notes;
  for (const QVariant& rv : rules) {
    const QVariantMap rule = rv.toMap();
    if (rule.contains(QStringLiteral("enabled")) && !rule.value(QStringLiteral("enabled")).toBool())
      continue;
    const ConditionResult one = evalOneRule(rule, vars);
    if (!one.ok) return one;
    notes << one.note;
    ++used;
    if (logic == QLatin1String("or"))
      acc = acc || one.passed;
    else
      acc = acc && one.passed;
  }
  if (used == 0) {
    out.ok = false;
    out.error = QStringLiteral("未配置条件规则");
    out.note = out.error;
    return out;
  }
  out.ok = true;
  out.passed = acc;
  out.branchTaken = acc ? QStringLiteral("true") : QStringLiteral("false");
  out.note = notes.join(QStringLiteral("；"));
  return out;
}

ConditionResult evaluateBranch(const QVariantMap& params, const QVariantMap& vars) {
  ConditionResult out;
  const QVariantList paths = params.value(QStringLiteral("paths")).toList();
  const QString defaultId =
      params.value(QStringLiteral("defaultPathId"), QStringLiteral("default")).toString();
  if (paths.isEmpty()) {
    out.ok = false;
    out.error = QStringLiteral("未配置分支路径");
    out.note = out.error;
    return out;
  }

  auto isDefault = [&](const QVariantMap& p) {
    const QString id = p.value(QStringLiteral("id")).toString();
    const QString name = p.value(QStringLiteral("name")).toString();
    return id == defaultId || name == QStringLiteral("默认") ||
           name == QLatin1String("default");
  };

  for (const QVariant& pv : paths) {
    const QVariantMap path = pv.toMap();
    if (path.contains(QStringLiteral("enabled")) && !path.value(QStringLiteral("enabled")).toBool())
      continue;
    if (isDefault(path)) continue;
    const ConditionResult one = evalOneRule(path, vars);
    if (!one.ok) return one;
    if (one.passed) {
      out.ok = true;
      out.passed = true;
      const QString id = path.value(QStringLiteral("id")).toString();
      const QString name = path.value(QStringLiteral("name")).toString();
      out.branchTaken = !name.isEmpty() ? name : id;
      out.note = QStringLiteral("命中路径 %1").arg(out.branchTaken);
      return out;
    }
  }

  // default path
  for (const QVariant& pv : paths) {
    const QVariantMap path = pv.toMap();
    if (path.contains(QStringLiteral("enabled")) && !path.value(QStringLiteral("enabled")).toBool())
      continue;
    if (!isDefault(path) && path.value(QStringLiteral("id")).toString() != defaultId)
      continue;
    out.ok = true;
    out.passed = true;
    const QString id = path.value(QStringLiteral("id")).toString();
    const QString name = path.value(QStringLiteral("name")).toString();
    out.branchTaken = !name.isEmpty() ? name : (id.isEmpty() ? defaultId : id);
    out.note = QStringLiteral("默认路径 %1").arg(out.branchTaken);
    return out;
  }

  out.ok = false;
  out.error = QStringLiteral("无命中路径且缺少默认路径");
  out.note = out.error;
  return out;
}

QStringList conditionSelfTest() {
  QStringList fails;
  auto expect = [&](bool cond, const char* msg) {
    if (!cond) fails << QString::fromUtf8(msg);
  };

  QVariantMap vars;
  vars.insert(QStringLiteral("barcodeCount"), 3);
  vars.insert(QStringLiteral("ocrOk"), 1);
  vars.insert(QStringLiteral("ocrText"), QStringLiteral("ABC"));
  vars.insert(QStringLiteral("flag"), true);
  vars.insert(QStringLiteral("passGate"), 1);

  // strict type: number 1 != text "1"
  {
    QVariantMap p{{QStringLiteral("left"), 1},
                  {QStringLiteral("comparison"), QStringLiteral("eq")},
                  {QStringLiteral("right"), QStringLiteral("\"1\"")}};
    const ConditionResult r = evaluateCondition(p, {});
    expect(r.ok && !r.passed, "eq number-vs-string should be false");
  }
  // numeric eq
  {
    QVariantMap p{{QStringLiteral("left"), 1},
                  {QStringLiteral("comparison"), QStringLiteral("eq")},
                  {QStringLiteral("right"), 1}};
    const ConditionResult r = evaluateCondition(p, {});
    expect(r.ok && r.passed && r.branchTaken == QLatin1String("true"), "eq 1==1");
  }
  // gt type error on text
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("\"a\"")},
                  {QStringLiteral("comparison"), QStringLiteral("gt")},
                  {QStringLiteral("right"), 1}};
    const ConditionResult r = evaluateCondition(p, {});
    expect(!r.ok && r.error.contains(QStringLiteral("数值")), "gt type error");
  }
  // var bind + gte
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("barcodeCount")},
                  {QStringLiteral("comparison"), QStringLiteral("gte")},
                  {QStringLiteral("right"), 3}};
    const ConditionResult r = evaluateCondition(p, vars);
    expect(r.ok && r.passed, "barcodeCount gte 3");
  }
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("${flow.barcodeCount}")},
                  {QStringLiteral("comparison"), QStringLiteral("gt")},
                  {QStringLiteral("right"), 3}};
    const ConditionResult r = evaluateCondition(p, vars);
    expect(r.ok && !r.passed && r.branchTaken == QLatin1String("false"),
           "barcodeCount gt 3 is false");
  }
  // missing ref
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("noSuchVar")},
                  {QStringLiteral("comparison"), QStringLiteral("eq")},
                  {QStringLiteral("right"), 1}};
    const ConditionResult r = evaluateCondition(p, vars);
    expect(!r.ok && r.error.contains(QStringLiteral("缺失")), "missing ref fails");
  }
  // contains case-sensitive
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("ocrText")},
                  {QStringLiteral("comparison"), QStringLiteral("contains")},
                  {QStringLiteral("right"), QStringLiteral("\"BC\"")}};
    const ConditionResult r = evaluateCondition(p, vars);
    expect(r.ok && r.passed, "contains BC");
  }
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("ocrText")},
                  {QStringLiteral("comparison"), QStringLiteral("contains")},
                  {QStringLiteral("right"), QStringLiteral("\"bc\"")}};
    const ConditionResult r = evaluateCondition(p, vars);
    expect(r.ok && !r.passed, "contains is case-sensitive");
  }
  // is_true on 0/1 int
  {
    QVariantMap p{{QStringLiteral("left"), QStringLiteral("ocrOk")},
                  {QStringLiteral("comparison"), QStringLiteral("is_true")},
                  {QStringLiteral("right"), 0}};
    const ConditionResult r = evaluateCondition(p, vars);
    expect(r.ok && r.passed, "ocrOk is_true");
  }
  // AND / OR
  {
    QVariantList rules;
    rules << QVariantMap{{QStringLiteral("left"), 1},
                         {QStringLiteral("comparison"), QStringLiteral("eq")},
                         {QStringLiteral("right"), 1},
                         {QStringLiteral("enabled"), true}};
    rules << QVariantMap{{QStringLiteral("left"), 1},
                         {QStringLiteral("comparison"), QStringLiteral("eq")},
                         {QStringLiteral("right"), 2},
                         {QStringLiteral("enabled"), true}};
    QVariantMap p;
    p.insert(QStringLiteral("logic"), QStringLiteral("and"));
    p.insert(QStringLiteral("rules"), rules);
    expect(evaluateCondition(p, {}).ok && !evaluateCondition(p, {}).passed, "AND false");
    p.insert(QStringLiteral("logic"), QStringLiteral("or"));
    expect(evaluateCondition(p, {}).ok && evaluateCondition(p, {}).passed, "OR true");
  }
  // branch first hit + default
  {
    QVariantList paths;
    paths << QVariantMap{{QStringLiteral("id"), QStringLiteral("path1")},
                         {QStringLiteral("name"), QStringLiteral("分支1")},
                         {QStringLiteral("left"), QStringLiteral("barcodeCount")},
                         {QStringLiteral("comparison"), QStringLiteral("eq")},
                         {QStringLiteral("right"), 3},
                         {QStringLiteral("enabled"), true}};
    paths << QVariantMap{{QStringLiteral("id"), QStringLiteral("default")},
                         {QStringLiteral("name"), QStringLiteral("默认")},
                         {QStringLiteral("left"), QString()},
                         {QStringLiteral("comparison"), QStringLiteral("is_true")},
                         {QStringLiteral("right"), QString()},
                         {QStringLiteral("enabled"), true}};
    QVariantMap p;
    p.insert(QStringLiteral("paths"), paths);
    p.insert(QStringLiteral("defaultPathId"), QStringLiteral("default"));
    const ConditionResult hit = evaluateBranch(p, vars);
    expect(hit.ok && hit.branchTaken == QStringLiteral("分支1"), "branch hit path1");
    vars.insert(QStringLiteral("barcodeCount"), 0);
    const ConditionResult def = evaluateBranch(p, vars);
    expect(def.ok && def.branchTaken == QStringLiteral("默认"), "branch default");
  }
  return fails;
}

}  // namespace sieans_qt
