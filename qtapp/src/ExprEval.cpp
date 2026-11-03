#include "ExprEval.hpp"
#include <functional>

#include <QRegularExpression>
#include <algorithm>
#include <cmath>

namespace sieans_qt {
namespace {

bool isTruthy(const QVariant& v) {
  if (!v.isValid() || v.isNull()) return false;
  if (v.typeId() == QMetaType::Bool) return v.toBool();
  if (v.typeId() == QMetaType::QString) return !v.toString().isEmpty();
  if (v.canConvert<double>()) return v.toDouble() != 0.0;
  return true;
}

QString stripParensOuter(QString s) {
  s = s.trimmed();
  while (s.size() >= 2 && s.startsWith(QLatin1Char('(')) &&
         s.endsWith(QLatin1Char(')'))) {
    int depth = 0;
    bool wrap = true;
    for (int i = 0; i < s.size(); ++i) {
      if (s[i] == QLatin1Char('(')) ++depth;
      else if (s[i] == QLatin1Char(')')) --depth;
      if (depth == 0 && i + 1 < s.size()) {
        wrap = false;
        break;
      }
    }
    if (!wrap) break;
    s = s.mid(1, s.size() - 2).trimmed();
  }
  return s;
}

int findTopLevel(const QString& s, const QStringList& ops) {
  int depth = 0;
  bool inStr = false;
  QChar q;
  for (int i = s.size() - 1; i >= 0; --i) {
    const QChar c = s[i];
    if (inStr) {
      if (c == q && (i == 0 || s[i - 1] != QLatin1Char('\\'))) inStr = false;
      continue;
    }
    if (c == QLatin1Char('"') || c == QLatin1Char('\'')) {
      inStr = true;
      q = c;
      continue;
    }
    if (c == QLatin1Char(')')) ++depth;
    else if (c == QLatin1Char('(')) --depth;
    if (depth != 0) continue;
    for (const QString& op : ops) {
      const int n = op.size();
      if (i >= n - 1 && s.mid(i - n + 1, n) == op) {
        // avoid matching <= as < etc — handled by ordering longer first
        if (op == QLatin1String("<") || op == QLatin1String(">")) {
          if (i >= n && (s[i - n] == QLatin1Char('<') || s[i - n] == QLatin1Char('>') ||
                         s[i - n] == QLatin1Char('=')))
            continue;
          if (i + 1 < s.size() && s[i + 1] == QLatin1Char('=')) continue;
        }
        // word-boundary for and/or
        if (op == QLatin1String(" or ") || op == QLatin1String(" and ")) {
          return i - n + 1;
        }
        return i - n + 1;
      }
    }
  }
  return -1;
}

QString quoteLit(const QString& text) {
  QString body = text;
  body.replace(QLatin1Char('\\'), QStringLiteral("\\\\"));
  body.replace(QLatin1Char('"'), QStringLiteral("\\\""));
  body.replace(QLatin1Char('\n'), QStringLiteral("\\n"));
  return QStringLiteral("\"%1\"").arg(body);
}

void replaceMatchesReverse(QString& expr, const QRegularExpression& re,
                           const std::function<QString(const QRegularExpressionMatch&)>& repl) {
  QRegularExpressionMatchIterator it = re.globalMatch(expr);
  QList<QRegularExpressionMatch> ms;
  while (it.hasNext()) ms.prepend(it.next());
  for (const auto& m : ms) {
    const int after = m.capturedStart() + m.capturedLength();
    if (after < expr.size() && expr[after] == QLatin1Char('[')) continue;
    expr.replace(m.capturedStart(), m.capturedLength(), repl(m));
  }
}

int listLen(const StepSnap& snap, const QString& field) {
  if (field == QLatin1String("matches"))
    return snap.matches > 0 ? snap.matches : snap.texts.size();
  if (field == QLatin1String("items")) return snap.texts.size();
  return snap.texts.size();
}

QString rewriteStepFields(QString expr, const QHash<QString, StepSnap>& steps) {
  {
    static QRegularExpression lenOr(QStringLiteral(
        R"re(len\s*\(\s*steps\["([^"]+)"\]\.(matches|items)(?:\s+or\s+steps\["([^"]+)"\]\.(matches|items))?(?:\s+or\s+\[\])?\s*\))re"));
    replaceMatchesReverse(expr, lenOr, [&](const QRegularExpressionMatch& m) {
      const StepSnap a = steps.value(m.captured(1));
      const int na = listLen(a, m.captured(2));
      if (na > 0 || m.captured(3).isEmpty()) return QString::number(na);
      return QString::number(listLen(steps.value(m.captured(3)), m.captured(4)));
    });
  }
  {
    static QRegularExpression lenOne(QStringLiteral(
        R"re(len\s*\(\s*steps\["([^"]+)"\]\.(matches|items)\s*\))re"));
    replaceMatchesReverse(expr, lenOne, [&](const QRegularExpressionMatch& m) {
      return QString::number(listLen(steps.value(m.captured(1)), m.captured(2)));
    });
  }
  {
    static QRegularExpression itemText(
        QStringLiteral(R"re(steps\["([^"]+)"\]\.items\[(\d+)\]\.text)re"));
    replaceMatchesReverse(expr, itemText, [&](const QRegularExpressionMatch& m) {
      const StepSnap snap = steps.value(m.captured(1));
      const int idx = m.captured(2).toInt();
      const QString text =
          (idx >= 0 && idx < snap.texts.size()) ? snap.texts[idx] : QString();
      return quoteLit(text);
    });
  }

  auto numField = [&](const QString& field, auto getter) {
    const QRegularExpression re(
        QStringLiteral(R"re(steps\["([^"]+)"\]\.)re") + field +
        QStringLiteral("\\b"));
    replaceMatchesReverse(expr, re, [&](const QRegularExpressionMatch& m) {
      return getter(steps.value(m.captured(1)));
    });
  };
  numField(QStringLiteral("count"), [](const StepSnap& s) { return QString::number(s.count); });
  numField(QStringLiteral("ok"),
           [](const StepSnap& s) { return QString::number(s.ok ? 1 : 0); });
  numField(QStringLiteral("score"),
           [](const StepSnap& s) { return QString::number(s.score, 'g', 8); });
  numField(QStringLiteral("confidence"),
           [](const StepSnap& s) { return QString::number(s.confidence, 'g', 8); });
  numField(QStringLiteral("matches"),
           [](const StepSnap& s) { return QString::number(s.matches); });
  numField(QStringLiteral("text"), [](const StepSnap& s) { return quoteLit(s.text); });
  numField(QStringLiteral("items"), [](const StepSnap& s) {
    return QString::number(s.texts.isEmpty() ? 0 : 1);
  });

  {
    static QRegularExpression extra(
        QStringLiteral(R"re(steps\["([^"]+)"\]\.([A-Za-z_][A-Za-z0-9_]*))re"));
    replaceMatchesReverse(expr, extra, [&](const QRegularExpressionMatch& m) {
      const QVariant v = steps.value(m.captured(1)).fields.value(m.captured(2));
      if (!v.isValid() || v.isNull()) return QStringLiteral("0");
      if (v.typeId() == QMetaType::QString) return quoteLit(v.toString());
      if (v.typeId() == QMetaType::Bool) return v.toBool() ? QStringLiteral("1") : QStringLiteral("0");
      return v.toString().isEmpty() ? QStringLiteral("0") : v.toString();
    });
  }
  return expr;
}

QStringList splitTopArgs(const QString& s) {
  QStringList out;
  int depth = 0;
  bool inStr = false;
  QChar q;
  int start = 0;
  for (int i = 0; i < s.size(); ++i) {
    const QChar c = s[i];
    if (inStr) {
      if (c == q && (i == 0 || s[i - 1] != QLatin1Char('\\'))) inStr = false;
      continue;
    }
    if (c == QLatin1Char('"') || c == QLatin1Char('\'')) {
      inStr = true;
      q = c;
      continue;
    }
    if (c == QLatin1Char('(')) ++depth;
    else if (c == QLatin1Char(')')) --depth;
    else if (c == QLatin1Char(',') && depth == 0) {
      out << s.mid(start, i - start).trimmed();
      start = i + 1;
    }
  }
  out << s.mid(start).trimmed();
  return out;
}

}  // namespace

QVariant ExprEval::eval(const QString& raw, QString* error) const {
  QString expr = raw.trimmed();
  if (expr.isEmpty()) return 0;

  // Whole-expression join used by barcodeAll rows (often wrapped in parens).
  {
    static QRegularExpression joinRe(
        QStringLiteral(
            R"re("[^"]*"\s*\.\s*join\s*\(\s*i\.text\s+for\s+i\s+in\s+\(steps\["([^"]+)"\]\.items(?:\s+or\s+\[\])?\)\s*\))re"));
    const QString stripped = stripParensOuter(expr);
    auto m = joinRe.match(stripped);
    if (m.hasMatch() && m.capturedStart() == 0 &&
        m.capturedLength() == stripped.size()) {
      return steps_.value(m.captured(1)).texts.join(QLatin1Char('\n'));
    }
  }

  expr = rewriteStepFields(expr, steps_);

  // Recursive evaluator on rewritten expr
  std::function<QVariant(QString)> evalRec;
  evalRec = [&](QString s) -> QVariant {
    s = stripParensOuter(s);
    if (s.isEmpty()) return 0;
    if (s == QLatin1String("[]")) return 0;

    if (s.startsWith(QLatin1String("not ")) || s.startsWith(QLatin1String("not("))) {
      const QString rest =
          s.startsWith(QLatin1String("not ")) ? s.mid(4) : s.mid(3);
      return isTruthy(evalRec(rest)) ? 0 : 1;
    }

    // ternary: A if COND else B
    {
      int depth = 0;
      bool inStr = false;
      QChar q;
      int ifPos = -1, elsePos = -1;
      for (int i = 0; i < s.size(); ++i) {
        const QChar c = s[i];
        if (inStr) {
          if (c == q && (i == 0 || s[i - 1] != QLatin1Char('\\'))) inStr = false;
          continue;
        }
        if (c == QLatin1Char('"') || c == QLatin1Char('\'')) {
          inStr = true;
          q = c;
          continue;
        }
        if (c == QLatin1Char('(')) ++depth;
        else if (c == QLatin1Char(')')) --depth;
        if (depth != 0) continue;
        if (i + 4 <= s.size() && s.mid(i, 4) == QLatin1String(" if ") && ifPos < 0)
          ifPos = i;
        if (i + 6 <= s.size() && s.mid(i, 6) == QLatin1String(" else ") && ifPos >= 0) {
          elsePos = i;
          break;
        }
      }
      if (ifPos >= 0 && elsePos > ifPos) {
        const QString a = s.left(ifPos).trimmed();
        const QString cond = s.mid(ifPos + 4, elsePos - (ifPos + 4)).trimmed();
        const QString b = s.mid(elsePos + 6).trimmed();
        return isTruthy(evalRec(cond)) ? evalRec(a) : evalRec(b);
      }
    }

    // or / and (left-associative via rightmost split like Python lower precedence)
    int pos = findTopLevel(s, {QStringLiteral(" or ")});
    if (pos >= 0) {
      QVariant L = evalRec(s.left(pos));
      if (isTruthy(L)) return L;
      return evalRec(s.mid(pos + 4));
    }
    pos = findTopLevel(s, {QStringLiteral(" and ")});
    if (pos >= 0) {
      QVariant L = evalRec(s.left(pos));
      if (!isTruthy(L)) return L;
      return evalRec(s.mid(pos + 5));
    }

    // comparisons
    for (const QString& op :
         {QStringLiteral("=="), QStringLiteral("!="), QStringLiteral("<="),
          QStringLiteral(">="), QStringLiteral("<"), QStringLiteral(">")}) {
      pos = findTopLevel(s, {op});
      if (pos >= 0) {
        QVariant L = evalRec(s.left(pos));
        QVariant R = evalRec(s.mid(pos + op.size()));
        double ld = L.toDouble();
        double rd = R.toDouble();
        bool bothNum = L.canConvert<double>() && R.canConvert<double>() &&
                       L.typeId() != QMetaType::QString &&
                       R.typeId() != QMetaType::QString;
        if (!bothNum && (L.typeId() == QMetaType::QString ||
                         R.typeId() == QMetaType::QString)) {
          const QString ls = L.toString();
          const QString rs = R.toString();
          if (op == QLatin1String("==")) return ls == rs ? 1 : 0;
          if (op == QLatin1String("!=")) return ls != rs ? 1 : 0;
          if (op == QLatin1String("<")) return ls < rs ? 1 : 0;
          if (op == QLatin1String(">")) return ls > rs ? 1 : 0;
          if (op == QLatin1String("<=")) return ls <= rs ? 1 : 0;
          if (op == QLatin1String(">=")) return ls >= rs ? 1 : 0;
        }
        if (op == QLatin1String("==")) return ld == rd ? 1 : 0;
        if (op == QLatin1String("!=")) return ld != rd ? 1 : 0;
        if (op == QLatin1String("<")) return ld < rd ? 1 : 0;
        if (op == QLatin1String(">")) return ld > rd ? 1 : 0;
        if (op == QLatin1String("<=")) return ld <= rd ? 1 : 0;
        if (op == QLatin1String(">=")) return ld >= rd ? 1 : 0;
      }
    }

    // "needle" in haystack  (substring / membership)
    {
      // split on bare " in " outside quotes — simple scan
      int depth = 0;
      bool inStr = false;
      QChar qch;
      for (int i = 0; i + 4 <= s.size(); ++i) {
        const QChar c = s.at(i);
        if (inStr) {
          if (c == qch) inStr = false;
          continue;
        }
        if (c == QLatin1Char('"') || c == QLatin1Char('\'')) {
          inStr = true;
          qch = c;
          continue;
        }
        if (c == QLatin1Char('(')) {
          ++depth;
          continue;
        }
        if (c == QLatin1Char(')')) {
          --depth;
          continue;
        }
        if (depth == 0 && s.mid(i, 4) == QLatin1String(" in ") &&
            (i == 0 || !s.at(i - 1).isLetterOrNumber()) ) {
          const QString L = s.left(i).trimmed();
          const QString R = s.mid(i + 4).trimmed();
          if (!L.isEmpty() && !R.isEmpty()) {
            const QString left = evalRec(L).toString();
            const QString right = evalRec(R).toString();
            return right.contains(left) ? 1 : 0;
          }
        }
      }
    }

    // + -
    pos = findTopLevel(s, {QStringLiteral("+"), QStringLiteral("-")});
    if (pos > 0) {  // pos==0 would be unary
      const QChar op = s[pos];
      QVariant L = evalRec(s.left(pos));
      QVariant R = evalRec(s.mid(pos + 1));
      if (op == QLatin1Char('+') && (L.typeId() == QMetaType::QString ||
                                     R.typeId() == QMetaType::QString))
        return L.toString() + R.toString();
      return op == QLatin1Char('+') ? L.toDouble() + R.toDouble()
                                    : L.toDouble() - R.toDouble();
    }

    // * / // %  (same precedence; longer ops first inside findTopLevel)
    pos = findTopLevel(s, {QStringLiteral("//"), QStringLiteral("%"),
                           QStringLiteral("*"), QStringLiteral("/")});
    if (pos >= 0) {
      QString op = s.mid(pos, 2) == QLatin1String("//") ? QStringLiteral("//")
                                                        : s.mid(pos, 1);
      QVariant L = evalRec(s.left(pos));
      QVariant R = evalRec(s.mid(pos + op.size()));
      if (op == QLatin1String("*")) return L.toDouble() * R.toDouble();
      if (op == QLatin1String("%")) {
        const double den = R.toDouble();
        if (den == 0.0) return 0;
        return std::fmod(L.toDouble(), den);
      }
      const double den = R.toDouble();
      if (den == 0.0) return 0;
      if (op == QLatin1String("//")) return std::floor(L.toDouble() / den);
      return L.toDouble() / den;
    }

    // len / int / str / abs / min / max wrapping the whole atom
    {
      static QRegularExpression callRe(
          QStringLiteral(R"re(^(len|int|str|abs|min|max|startswith|endswith|contains|lower|upper|trim|strip|replace|slice|isdigit|isalpha|lpad|rpad|repeat|substr|default|coalesce|indexof|ifempty|find|left|right|mid|isempty|notempty|zfill|count|clamp|round|floor|ceil|sign|pow|sqrt|trunc|title|capitalize|hypot|log|exp|isalnum|swapcase|radians|degrees|ord|chr|bin|hex|islower|isupper|nvl|lstrip|rstrip|iff|bool|oct|fabs|fmod|cbrt|log10|frac|log2|isfinite|atan2|copysign|bitand|bitor|bitxor|gcd|lcm|clamp01|lerp|invlerp|smoothstep|step|saturate|fract|isnan|isinf|mix|exp2|fma|sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|log1p|expm1|fdim|nearbyint|bitshl|bitshr|remainder|scalbn|nextafter|tgamma|lgamma|erf|erfc|asinh|acosh|atanh|rint|logb|ilogb|signbit|isnormal|fmax|fmin|bitnot|between|approxeq)\((.*)\)$)re"));
      const auto cm = callRe.match(s);
      if (cm.hasMatch()) {
        const QString name = cm.captured(1);
        const QStringList args = splitTopArgs(cm.captured(2));
        if (name == QLatin1String("len")) {
          if (args.isEmpty()) return 0;
          const QVariant v = evalRec(args[0]);
          if (v.typeId() == QMetaType::QString) return v.toString().size();
          return 0;
        }
        if (name == QLatin1String("int"))
          return args.isEmpty() ? 0 : int(evalRec(args[0]).toDouble());
        if (name == QLatin1String("bool"))
          return args.isEmpty() ? 0 : (isTruthy(evalRec(args[0])) ? 1 : 0);
        if (name == QLatin1String("str"))
          return args.isEmpty() ? QString() : evalRec(args[0]).toString();
        if (name == QLatin1String("abs") || name == QLatin1String("fabs"))
          return args.isEmpty() ? 0 : std::fabs(evalRec(args[0]).toDouble());
        if (name == QLatin1String("fmod")) {
          if (args.size() < 2) return 0;
          const double a = evalRec(args[0]).toDouble();
          const double b = evalRec(args[1]).toDouble();
          return b == 0.0 ? 0 : std::fmod(a, b);
        }
        if (name == QLatin1String("cbrt"))
          return args.isEmpty() ? 0 : std::cbrt(evalRec(args[0]).toDouble());
        if (name == QLatin1String("log10")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v <= 0.0 ? 0 : std::log10(v);
        }
        if (name == QLatin1String("frac") ||
            name == QLatin1String("fract")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v - std::trunc(v);
        }
        if (name == QLatin1String("log2")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v <= 0.0 ? 0 : std::log2(v);
        }
        if (name == QLatin1String("isfinite")) {
          if (args.isEmpty()) return 0;
          return std::isfinite(evalRec(args[0]).toDouble()) ? 1 : 0;
        }
        if (name == QLatin1String("isnan")) {
          if (args.isEmpty()) return 0;
          return std::isnan(evalRec(args[0]).toDouble()) ? 1 : 0;
        }
        if (name == QLatin1String("isinf")) {
          if (args.isEmpty()) return 0;
          return std::isinf(evalRec(args[0]).toDouble()) ? 1 : 0;
        }
        if (name == QLatin1String("atan2")) {
          if (args.size() < 2) return 0;
          return std::atan2(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("copysign")) {
          if (args.size() < 2) return 0;
          return std::copysign(evalRec(args[0]).toDouble(),
                               evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("bitand") || name == QLatin1String("bitor") ||
            name == QLatin1String("bitxor")) {
          if (args.size() < 2) return 0;
          const int a = int(evalRec(args[0]).toDouble());
          const int b = int(evalRec(args[1]).toDouble());
          if (name == QLatin1String("bitand")) return a & b;
          if (name == QLatin1String("bitor")) return a | b;
          return a ^ b;
        }
        if (name == QLatin1String("gcd")) {
          if (args.size() < 2) return 0;
          int a = std::abs(int(evalRec(args[0]).toDouble()));
          int b = std::abs(int(evalRec(args[1]).toDouble()));
          while (b != 0) {
            const int t = a % b;
            a = b;
            b = t;
          }
          return a;
        }
        if (name == QLatin1String("lcm")) {
          if (args.size() < 2) return 0;
          int a = std::abs(int(evalRec(args[0]).toDouble()));
          int b = std::abs(int(evalRec(args[1]).toDouble()));
          if (a == 0 || b == 0) return 0;
          int x = a, y = b;
          while (y != 0) {
            const int t = x % y;
            x = y;
            y = t;
          }
          return (a / x) * b;
        }
        if (name == QLatin1String("clamp01") ||
            name == QLatin1String("saturate")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v);
        }
        if (name == QLatin1String("lerp") || name == QLatin1String("mix")) {
          if (args.size() < 3) return 0;
          const double a = evalRec(args[0]).toDouble();
          const double b = evalRec(args[1]).toDouble();
          double tt = evalRec(args[2]).toDouble();
          if (tt < 0.0) tt = 0.0;
          if (tt > 1.0) tt = 1.0;
          return a + (b - a) * tt;
        }
        if (name == QLatin1String("invlerp")) {
          if (args.size() < 3) return 0;
          const double a = evalRec(args[0]).toDouble();
          const double b = evalRec(args[1]).toDouble();
          const double v = evalRec(args[2]).toDouble();
          const double d = b - a;
          if (d == 0.0) return 0;
          double t = (v - a) / d;
          if (t < 0.0) t = 0.0;
          if (t > 1.0) t = 1.0;
          return t;
        }
        if (name == QLatin1String("smoothstep")) {
          if (args.size() < 3) return 0;
          const double e0 = evalRec(args[0]).toDouble();
          const double e1 = evalRec(args[1]).toDouble();
          const double x = evalRec(args[2]).toDouble();
          const double d = e1 - e0;
          if (d == 0.0) return x < e0 ? 0.0 : 1.0;
          double t = (x - e0) / d;
          if (t < 0.0) t = 0.0;
          if (t > 1.0) t = 1.0;
          return t * t * (3.0 - 2.0 * t);
        }
        if (name == QLatin1String("step")) {
          if (args.size() < 2) return 0;
          const double edge = evalRec(args[0]).toDouble();
          const double x = evalRec(args[1]).toDouble();
          return x < edge ? 0.0 : 1.0;
        }
        if (name == QLatin1String("min") || name == QLatin1String("max")) {
          if (args.isEmpty()) return 0;
          double acc = evalRec(args[0]).toDouble();
          for (int i = 1; i < args.size(); ++i) {
            const double v = evalRec(args[i]).toDouble();
            acc = name == QLatin1String("min") ? std::min(acc, v) : std::max(acc, v);
          }
          return acc;
        }
        if (name == QLatin1String("startswith") ||
            name == QLatin1String("endswith") ||
            name == QLatin1String("contains")) {
          if (args.size() < 2) return 0;
          const QString hay = evalRec(args[0]).toString();
          const QString needle = evalRec(args[1]).toString();
          if (name == QLatin1String("startswith"))
            return hay.startsWith(needle) ? 1 : 0;
          if (name == QLatin1String("endswith"))
            return hay.endsWith(needle) ? 1 : 0;
          return hay.contains(needle) ? 1 : 0;
        }
        if (name == QLatin1String("lower"))
          return args.isEmpty() ? QString()
                                : evalRec(args[0]).toString().toLower();
        if (name == QLatin1String("upper"))
          return args.isEmpty() ? QString()
                                : evalRec(args[0]).toString().toUpper();
        if (name == QLatin1String("trim") || name == QLatin1String("strip") ||
            name == QLatin1String("lstrip") || name == QLatin1String("rstrip"))
          return args.isEmpty() ? QString()
                                : evalRec(args[0]).toString().trimmed();
        if (name == QLatin1String("replace")) {
          if (args.size() < 3) return args.isEmpty() ? QString()
                                                     : evalRec(args[0]).toString();
          QString hay = evalRec(args[0]).toString();
          const QString from = evalRec(args[1]).toString();
          const QString to = evalRec(args[2]).toString();
          if (!from.isEmpty()) hay.replace(from, to);
          return hay;
        }
        if (name == QLatin1String("slice") || name == QLatin1String("substr") || name == QLatin1String("mid")) {
          if (args.isEmpty()) return QString();
          const QString hay = evalRec(args[0]).toString();
          int a = args.size() > 1 ? int(evalRec(args[1]).toDouble()) : 0;
          int b = args.size() > 2 ? int(evalRec(args[2]).toDouble()) : hay.size();
          if (a < 0) a = qMax(0, hay.size() + a);
          if (b < 0) b = qMax(0, hay.size() + b);
          a = qBound(0, a, hay.size());
          b = qBound(0, b, hay.size());
          if (b < a) return QString();
          return hay.mid(a, b - a);
        }
        if (name == QLatin1String("isdigit") || name == QLatin1String("isalpha")) {
          if (args.isEmpty()) return 0;
          const QString hay = evalRec(args[0]).toString();
          if (hay.isEmpty()) return 0;
          bool ok = true;
          for (const QChar ch : hay) {
            if (name == QLatin1String("isdigit") ? !ch.isDigit() : !ch.isLetter()) {
              ok = false;
              break;
            }
          }
          return ok ? 1 : 0;
        }
        if (name == QLatin1String("lpad") || name == QLatin1String("rpad")) {
          if (args.isEmpty()) return QString();
          QString hay = evalRec(args[0]).toString();
          const int width = args.size() > 1 ? int(evalRec(args[1]).toDouble()) : hay.size();
          QString fill = args.size() > 2 ? evalRec(args[2]).toString() : QStringLiteral(" ");
          if (fill.isEmpty()) fill = QStringLiteral(" ");
          const QChar ch = fill.at(0);
          if (width <= hay.size()) return hay;
          const int n = width - hay.size();
          const QString pad = QString(n, ch);
          return name == QLatin1String("lpad") ? pad + hay : hay + pad;
        }
        if (name == QLatin1String("repeat")) {
          if (args.isEmpty()) return QString();
          const QString hay = evalRec(args[0]).toString();
          int n = args.size() > 1 ? int(evalRec(args[1]).toDouble()) : 1;
          n = qBound(0, n, 256);
          return hay.repeated(n);
        }
        if (name == QLatin1String("default") || name == QLatin1String("coalesce") ||
            name == QLatin1String("nvl") || name == QLatin1String("ifempty")) {
          for (const QString& a : args) {
            const QVariant v = evalRec(a);
            if (!v.toString().isEmpty()) return v;
          }
          return QString();
        }
        if (name == QLatin1String("iff")) {
          // iff(cond, a, b) — truthy cond → a else b (VM-ish ternary helper)
          if (args.size() < 2) return QString();
          const QVariant cond = evalRec(args[0]);
          if (isTruthy(cond)) return evalRec(args[1]);
          return args.size() >= 3 ? evalRec(args[2]) : QString();
        }
        if (name == QLatin1String("indexof") || name == QLatin1String("find")) {
          if (args.size() < 2) return -1;
          const QString hay = evalRec(args[0]).toString();
          const QString needle = evalRec(args[1]).toString();
          return hay.indexOf(needle);
        }
        if (name == QLatin1String("left") || name == QLatin1String("right")) {
          if (args.isEmpty()) return QString();
          const QString hay = evalRec(args[0]).toString();
          int n = args.size() > 1 ? int(evalRec(args[1]).toDouble()) : hay.size();
          if (n < 0) n = 0;
          return name == QLatin1String("left") ? hay.left(n) : hay.right(n);
        }
        if (name == QLatin1String("isempty") || name == QLatin1String("notempty")) {
          if (args.isEmpty()) return name == QLatin1String("isempty") ? 1 : 0;
          const bool empty = evalRec(args[0]).toString().isEmpty();
          if (name == QLatin1String("isempty")) return empty ? 1 : 0;
          return empty ? 0 : 1;
        }
        if (name == QLatin1String("zfill")) {
          if (args.isEmpty()) return QString();
          QString hay = evalRec(args[0]).toString();
          const int width = args.size() > 1 ? int(evalRec(args[1]).toDouble()) : hay.size();
          if (width <= hay.size()) return hay;
          return QString(width - hay.size(), QLatin1Char('0')) + hay;
        }
        if (name == QLatin1String("count")) {
          if (args.size() < 2) return 0;
          const QString hay = evalRec(args[0]).toString();
          const QString needle = evalRec(args[1]).toString();
          if (needle.isEmpty()) return 0;
          int n = 0;
          int from = 0;
          while (true) {
            const int at = hay.indexOf(needle, from);
            if (at < 0) break;
            ++n;
            from = at + needle.size();
          }
          return n;
        }
        if (name == QLatin1String("clamp")) {
          if (args.isEmpty()) return 0;
          double v = evalRec(args[0]).toDouble();
          if (args.size() > 1) v = std::max(v, evalRec(args[1]).toDouble());
          if (args.size() > 2) v = std::min(v, evalRec(args[2]).toDouble());
          return v;
        }
        if (name == QLatin1String("round")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          const int places = args.size() > 1 ? int(evalRec(args[1]).toDouble()) : 0;
          if (places <= 0) return std::round(v);
          const double f = std::pow(10.0, places);
          return std::round(v * f) / f;
        }
        if (name == QLatin1String("floor") || name == QLatin1String("ceil")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return name == QLatin1String("floor") ? std::floor(v) : std::ceil(v);
        }
        if (name == QLatin1String("sign")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v > 0 ? 1 : (v < 0 ? -1 : 0);
        }
        if (name == QLatin1String("pow")) {
          if (args.size() < 2) return args.isEmpty() ? 0 : evalRec(args[0]).toDouble();
          return std::pow(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("sqrt")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v < 0 ? 0 : std::sqrt(v);
        }
        if (name == QLatin1String("trunc")) {
          if (args.isEmpty()) return 0;
          return std::trunc(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("title") || name == QLatin1String("capitalize")) {
          if (args.isEmpty()) return QString();
          QString s = evalRec(args[0]).toString();
          if (name == QLatin1String("capitalize")) {
            if (s.isEmpty()) return s;
            s[0] = s[0].toUpper();
            return s;
          }
          bool up = true;
          for (int i = 0; i < s.size(); ++i) {
            if (s[i].isSpace()) {
              up = true;
            } else if (up) {
              s[i] = s[i].toUpper();
              up = false;
            } else {
              s[i] = s[i].toLower();
            }
          }
          return s;
        }
        if (name == QLatin1String("hypot")) {
          if (args.size() < 2) return 0;
          return std::hypot(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("log")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          return v <= 0 ? 0 : std::log(v);
        }
        if (name == QLatin1String("exp")) {
          if (args.isEmpty()) return 1;
          return std::exp(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("exp2")) {
          if (args.isEmpty()) return 1;
          return std::exp2(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("fma")) {
          if (args.size() < 3) return 0;
          return std::fma(evalRec(args[0]).toDouble(),
                          evalRec(args[1]).toDouble(),
                          evalRec(args[2]).toDouble());
        }
        if (name == QLatin1String("sin")) {
          if (args.isEmpty()) return 0;
          return std::sin(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("cos")) {
          if (args.isEmpty()) return 1;
          return std::cos(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("tan")) {
          if (args.isEmpty()) return 0;
          return std::tan(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("asin")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          if (v < -1.0 || v > 1.0) return 0;
          return std::asin(v);
        }
        if (name == QLatin1String("acos")) {
          if (args.isEmpty()) return 0;
          const double v = evalRec(args[0]).toDouble();
          if (v < -1.0 || v > 1.0) return 0;
          return std::acos(v);
        }
        if (name == QLatin1String("atan")) {
          if (args.isEmpty()) return 0;
          return std::atan(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("sinh")) {
          if (args.isEmpty()) return 0;
          return std::sinh(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("cosh")) {
          if (args.isEmpty()) return 0;
          return std::cosh(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("tanh")) {
          if (args.isEmpty()) return 0;
          return std::tanh(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("log1p")) {
          if (args.isEmpty()) return 0;
          return std::log1p(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("expm1")) {
          if (args.isEmpty()) return 0;
          return std::expm1(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("fdim")) {
          if (args.size() < 2) return 0;
          return std::fdim(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("nearbyint")) {
          if (args.isEmpty()) return 0;
          return std::nearbyint(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("bitshl")) {
          if (args.size() < 2) return 0;
          const qint64 v = evalRec(args[0]).toLongLong();
          const int n = evalRec(args[1]).toInt();
          if (n < 0 || n > 62) return 0;
          return qint64(v << n);
        }
        if (name == QLatin1String("bitshr")) {
          if (args.size() < 2) return 0;
          const qint64 v = evalRec(args[0]).toLongLong();
          const int n = evalRec(args[1]).toInt();
          if (n < 0 || n > 62) return 0;
          return qint64(v >> n);
        }
        if (name == QLatin1String("remainder")) {
          if (args.size() < 2) return 0;
          return std::remainder(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("scalbn")) {
          if (args.size() < 2) return 0;
          return std::scalbn(evalRec(args[0]).toDouble(), evalRec(args[1]).toInt());
        }
        if (name == QLatin1String("nextafter")) {
          if (args.size() < 2) return 0;
          return std::nextafter(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("tgamma")) {
          if (args.isEmpty()) return 0;
          return std::tgamma(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("lgamma")) {
          if (args.isEmpty()) return 0;
          return std::lgamma(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("erf")) {
          if (args.isEmpty()) return 0;
          return std::erf(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("erfc")) {
          if (args.isEmpty()) return 0;
          return std::erfc(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("asinh")) {
          if (args.isEmpty()) return 0;
          return std::asinh(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("acosh")) {
          if (args.isEmpty()) return 0;
          return std::acosh(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("atanh")) {
          if (args.isEmpty()) return 0;
          return std::atanh(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("rint")) {
          if (args.isEmpty()) return 0;
          return std::rint(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("logb")) {
          if (args.isEmpty()) return 0;
          return std::logb(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("ilogb")) {
          if (args.isEmpty()) return 0;
          return std::ilogb(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("signbit")) {
          if (args.isEmpty()) return 0;
          return std::signbit(evalRec(args[0]).toDouble()) ? 1 : 0;
        }
        if (name == QLatin1String("isnormal")) {
          if (args.isEmpty()) return 0;
          return std::isnormal(evalRec(args[0]).toDouble()) ? 1 : 0;
        }
        if (name == QLatin1String("fmax")) {
          if (args.size() < 2) return 0;
          return std::fmax(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("fmin")) {
          if (args.size() < 2) return 0;
          return std::fmin(evalRec(args[0]).toDouble(), evalRec(args[1]).toDouble());
        }
        if (name == QLatin1String("bitnot")) {
          if (args.isEmpty()) return 0;
          return ~int(evalRec(args[0]).toDouble());
        }
        if (name == QLatin1String("between")) {
          if (args.size() < 3) return 0;
          const double x = evalRec(args[0]).toDouble();
          const double lo = evalRec(args[1]).toDouble();
          const double hi = evalRec(args[2]).toDouble();
          return (x >= lo && x <= hi) ? 1 : 0;
        }
        if (name == QLatin1String("approxeq")) {
          if (args.size() < 2) return 0;
          const double a = evalRec(args[0]).toDouble();
          const double b = evalRec(args[1]).toDouble();
          const double eps = args.size() >= 3 ? evalRec(args[2]).toDouble() : 1e-9;
          return (std::fabs(a - b) <= eps) ? 1 : 0;
        }
        if (name == QLatin1String("isalnum")) {
          if (args.isEmpty()) return 0;
          const QString s = evalRec(args[0]).toString();
          if (s.isEmpty()) return 0;
          for (const QChar ch : s)
            if (!ch.isLetterOrNumber()) return 0;
          return 1;
        }
        if (name == QLatin1String("swapcase")) {
          if (args.isEmpty()) return QString();
          QString s = evalRec(args[0]).toString();
          for (int i = 0; i < s.size(); ++i) {
            if (s[i].isUpper()) s[i] = s[i].toLower();
            else if (s[i].isLower()) s[i] = s[i].toUpper();
          }
          return s;
        }
        if (name == QLatin1String("radians")) {
          if (args.isEmpty()) return 0;
          return evalRec(args[0]).toDouble() * (3.14159265358979323846) / 180.0;
        }
        if (name == QLatin1String("degrees")) {
          if (args.isEmpty()) return 0;
          return evalRec(args[0]).toDouble() * 180.0 / (3.14159265358979323846);
        }
        if (name == QLatin1String("ord")) {
          if (args.isEmpty()) return 0;
          const QString s = evalRec(args[0]).toString();
          return s.isEmpty() ? 0 : int(s.at(0).unicode());
        }
        if (name == QLatin1String("chr")) {
          if (args.isEmpty()) return QString();
          return QString(QChar(ushort(evalRec(args[0]).toInt())));
        }
        if (name == QLatin1String("bin") || name == QLatin1String("hex") ||
            name == QLatin1String("oct")) {
          if (args.isEmpty()) return QString();
          const qint64 v = qint64(evalRec(args[0]).toDouble());
          if (name == QLatin1String("bin"))
            return QStringLiteral("0b") + QString::number(v, 2);
          if (name == QLatin1String("oct"))
            return QStringLiteral("0o") + QString::number(v, 8);
          return QStringLiteral("0x") + QString::number(v, 16);
        }
        if (name == QLatin1String("islower") || name == QLatin1String("isupper")) {
          if (args.isEmpty()) return 0;
          const QString s = evalRec(args[0]).toString();
          if (s.isEmpty()) return 0;
          for (const QChar ch : s) {
            if (name == QLatin1String("islower") ? !ch.isLower() : !ch.isUpper())
              return 0;
          }
          return 1;
        }
      }
    }

    // unary +/-
    if (s.startsWith(QLatin1Char('+')) || s.startsWith(QLatin1Char('-'))) {
      QVariant v = evalRec(s.mid(1));
      return s.startsWith(QLatin1Char('-')) ? -v.toDouble() : v;
    }

    // string literal
    if ((s.startsWith(QLatin1Char('"')) && s.endsWith(QLatin1Char('"'))) ||
        (s.startsWith(QLatin1Char('\'')) && s.endsWith(QLatin1Char('\'')))) {
      QString body = s.mid(1, s.size() - 2);
      body.replace(QStringLiteral("\\n"), QStringLiteral("\n"));
      body.replace(QStringLiteral("\\\""), QStringLiteral("\""));
      body.replace(QStringLiteral("\\'"), QStringLiteral("'"));
      return body;
    }

    // number
    bool okNum = false;
    const double num = s.toDouble(&okNum);
    if (okNum) return num;

    // bool literals
    if (s == QLatin1String("True") || s == QLatin1String("true")) return 1;
    if (s == QLatin1String("False") || s == QLatin1String("false") ||
        s == QLatin1String("None") || s == QLatin1String("null"))
      return 0;

    // identifier → vars (also flow.x)
    QString key = s;
    if (key.startsWith(QLatin1String("flow."))) key = key.mid(5);
    if (vars_.contains(key)) return vars_.value(key);
    if (error) *error = QStringLiteral("未知标识: %1").arg(s);
    return 0;
  };

  try {
    return evalRec(expr);
  } catch (...) {
    if (error) *error = QStringLiteral("求值异常");
    return 0;
  }
}

QStringList exprSelfTest() {
  QStringList fails;
  auto check = [&](const QString& label, const QVariant& got, const QString& expect) {
    if (got.toString() != expect)
      fails << QStringLiteral("%1 → %2 (期望 %3)").arg(label, got.toString(), expect);
  };
  StepSnap snap;
  snap.count = 2;
  snap.ok = true;
  snap.score = 0.8;
  snap.confidence = 0.66;
  snap.text = QStringLiteral("HELLO");
  snap.matches = 3;
  snap.texts = {QStringLiteral("HELLO"), QStringLiteral("WORLD")};
  const QString id = QStringLiteral("b2c3d4e5f6071829");
  QHash<QString, StepSnap> steps;
  steps.insert(id, snap);
  ExprEval ev;
  ev.setSteps(steps);
  ev.setVars({{QStringLiteral("passGate"), 1}, {QStringLiteral("barcodeCount"), 2}});

  const QString sid = QStringLiteral("steps[\"%1\"]").arg(id);
  check(QStringLiteral("count"), ev.eval(QStringLiteral("(%1.count or 0)").arg(sid)),
        QStringLiteral("2"));
  check(QStringLiteral("gate"),
        ev.eval(QStringLiteral("(%1.count or 0) >= 1").arg(sid)), QStringLiteral("1"));
  check(QStringLiteral("item0"),
        ev.eval(QStringLiteral("(%1.items[0].text if (%1.items) else \"\")").arg(sid)),
        QStringLiteral("HELLO"));
  check(QStringLiteral("join"),
        ev.eval(QStringLiteral("(\"\\n\".join(i.text for i in (%1.items or [])))").arg(sid)),
        QStringLiteral("HELLO\nWORLD"));
  check(QStringLiteral("len"),
        ev.eval(QStringLiteral("len(%1.matches or %1.items or [])").arg(sid)),
        QStringLiteral("3"));
  check(QStringLiteral("score"),
        ev.eval(QStringLiteral("(%1.score or 0) >= 0.55").arg(sid)), QStringLiteral("1"));
  check(QStringLiteral("text"), ev.eval(QStringLiteral("(%1.text or \"\")").arg(sid)),
        QStringLiteral("HELLO"));
  check(QStringLiteral("flow"), ev.eval(QStringLiteral("flow.passGate")), QStringLiteral("1"));
  check(QStringLiteral("not"), ev.eval(QStringLiteral("not (0)")), QStringLiteral("1"));
  check(QStringLiteral("mod"), ev.eval(QStringLiteral("10 % 4")), QStringLiteral("2"));
  check(QStringLiteral("floordiv"), ev.eval(QStringLiteral("7 // 2")), QStringLiteral("3"));
  check(QStringLiteral("and"),
        ev.eval(QStringLiteral("((%1.count or 0) >= 1) and ((%1.confidence or 0) > 0.5)")
                    .arg(sid)),
        QStringLiteral("1"));
  check(QStringLiteral("in"),
        ev.eval(QStringLiteral("\"ELL\" in %1.text").arg(sid)), QStringLiteral("1"));
  check(QStringLiteral("in-miss"),
        ev.eval(QStringLiteral("\"ZZZ\" in %1.text").arg(sid)), QStringLiteral("0"));
  check(QStringLiteral("startswith"),
        ev.eval(QStringLiteral("startswith(%1.text, \"HE\")").arg(sid)),
        QStringLiteral("1"));
  check(QStringLiteral("endswith"),
        ev.eval(QStringLiteral("endswith(%1.text, \"LO\")").arg(sid)),
        QStringLiteral("1"));
  check(QStringLiteral("contains-fn"),
        ev.eval(QStringLiteral("contains(%1.text, \"ELL\")").arg(sid)),
        QStringLiteral("1"));
  check(QStringLiteral("lower"),
        ev.eval(QStringLiteral("lower(%1.text)").arg(sid)),
        QStringLiteral("hello"));
  check(QStringLiteral("trim"),
        ev.eval(QStringLiteral("trim('  HI  ')")),
        QStringLiteral("HI"));
  check(QStringLiteral("strip"),
        ev.eval(QStringLiteral("strip('  HI  ')")),
        QStringLiteral("HI"));
  check(QStringLiteral("replace"),
        ev.eval(QStringLiteral("replace(%1.text, 'LL', 'xx')").arg(sid)),
        QStringLiteral("HExxO"));
  check(QStringLiteral("slice"),
        ev.eval(QStringLiteral("slice(%1.text, 0, 2)").arg(sid)),
        QStringLiteral("HE"));
  check(QStringLiteral("isdigit"),
        ev.eval(QStringLiteral("isdigit('123')")),
        QStringLiteral("1"));
  check(QStringLiteral("isdigit-miss"),
        ev.eval(QStringLiteral("isdigit('12a')")),
        QStringLiteral("0"));
  check(QStringLiteral("isalpha"),
        ev.eval(QStringLiteral("isalpha('AbC')")),
        QStringLiteral("1"));
  check(QStringLiteral("lpad"),
        ev.eval(QStringLiteral("lpad('7', 3, '0')")),
        QStringLiteral("007"));
  check(QStringLiteral("rpad"),
        ev.eval(QStringLiteral("rpad('x', 3, '-')")),
        QStringLiteral("x--"));
  check(QStringLiteral("repeat"),
        ev.eval(QStringLiteral("repeat('ab', 3)")),
        QStringLiteral("ababab"));
  check(QStringLiteral("substr"),
        ev.eval(QStringLiteral("substr(%1.text, 0, 4)").arg(sid)),
        QStringLiteral("HELL"));
  check(QStringLiteral("default"),
        ev.eval(QStringLiteral("default('', 'fallback')")),
        QStringLiteral("fallback"));
  check(QStringLiteral("coalesce"),
        ev.eval(QStringLiteral("coalesce('', '', 'z')")),
        QStringLiteral("z"));
  check(QStringLiteral("nvl"),
        ev.eval(QStringLiteral("nvl('', 'z')")),
        QStringLiteral("z"));
  check(QStringLiteral("lstrip"),
        ev.eval(QStringLiteral("lstrip('  ab')")),
        QStringLiteral("ab"));
  check(QStringLiteral("iff-t"),
        ev.eval(QStringLiteral("iff(1, 'y', 'n')")),
        QStringLiteral("y"));
  check(QStringLiteral("iff-f"),
        ev.eval(QStringLiteral("iff(0, 'y', 'n')")),
        QStringLiteral("n"));
  check(QStringLiteral("bool-t"),
        ev.eval(QStringLiteral("bool('x')")),
        QStringLiteral("1"));
  check(QStringLiteral("bool-f"),
        ev.eval(QStringLiteral("bool('')")),
        QStringLiteral("0"));
  check(QStringLiteral("ifempty"),
        ev.eval(QStringLiteral("ifempty('', 'fb')")),
        QStringLiteral("fb"));
  check(QStringLiteral("indexof"),
        ev.eval(QStringLiteral("indexof(%1.text, 'LL')").arg(sid)),
        QStringLiteral("2"));
  check(QStringLiteral("indexof-miss"),
        ev.eval(QStringLiteral("indexof(%1.text, 'ZZ')").arg(sid)),
        QStringLiteral("-1"));
  check(QStringLiteral("find"),
        ev.eval(QStringLiteral("find(%1.text, 'EL')").arg(sid)),
        QStringLiteral("1"));
  check(QStringLiteral("left"),
        ev.eval(QStringLiteral("left(%1.text, 2)").arg(sid)),
        QStringLiteral("HE"));
  check(QStringLiteral("right"),
        ev.eval(QStringLiteral("right(%1.text, 2)").arg(sid)),
        QStringLiteral("LO"));
  check(QStringLiteral("mid"),
        ev.eval(QStringLiteral("mid(%1.text, 1, 4)").arg(sid)),
        QStringLiteral("ELL"));
  check(QStringLiteral("isempty"),
        ev.eval(QStringLiteral("isempty('')")),
        QStringLiteral("1"));
  check(QStringLiteral("notempty"),
        ev.eval(QStringLiteral("notempty(%1.text)").arg(sid)),
        QStringLiteral("1"));
  check(QStringLiteral("zfill"),
        ev.eval(QStringLiteral("zfill('7', 3)")),
        QStringLiteral("007"));
  check(QStringLiteral("count"),
        ev.eval(QStringLiteral("count(%1.text, 'L')").arg(sid)),
        QStringLiteral("2"));
  check(QStringLiteral("clamp"),
        ev.eval(QStringLiteral("clamp(5, 0, 3)")),
        QStringLiteral("3"));
  check(QStringLiteral("round"),
        ev.eval(QStringLiteral("round(3.7)")),
        QStringLiteral("4"));
  check(QStringLiteral("floor"),
        ev.eval(QStringLiteral("floor(3.9)")),
        QStringLiteral("3"));
  check(QStringLiteral("ceil"),
        ev.eval(QStringLiteral("ceil(3.1)")),
        QStringLiteral("4"));
  check(QStringLiteral("sign"),
        ev.eval(QStringLiteral("sign(-2)")),
        QStringLiteral("-1"));
  check(QStringLiteral("pow"),
        ev.eval(QStringLiteral("pow(2, 3)")),
        QStringLiteral("8"));
  check(QStringLiteral("sqrt"),
        ev.eval(QStringLiteral("sqrt(9)")),
        QStringLiteral("3"));
  check(QStringLiteral("trunc"),
        ev.eval(QStringLiteral("trunc(3.9)")),
        QStringLiteral("3"));
  check(QStringLiteral("title"),
        ev.eval(QStringLiteral("title('hello world')")),
        QStringLiteral("Hello World"));
  check(QStringLiteral("capitalize"),
        ev.eval(QStringLiteral("capitalize('hello')")),
        QStringLiteral("Hello"));
  check(QStringLiteral("hypot"),
        ev.eval(QStringLiteral("hypot(3, 4)")),
        QStringLiteral("5"));
  check(QStringLiteral("log"),
        ev.eval(QStringLiteral("round(log(2.718281828), 0)")),
        QStringLiteral("1"));
  check(QStringLiteral("exp"),
        ev.eval(QStringLiteral("round(exp(0))")),
        QStringLiteral("1"));
  check(QStringLiteral("exp2"),
        ev.eval(QStringLiteral("exp2(3)")),
        QStringLiteral("8"));
  check(QStringLiteral("fma"),
        ev.eval(QStringLiteral("fma(2, 3, 4)")),
        QStringLiteral("10"));
  check(QStringLiteral("sin"),
        ev.eval(QStringLiteral("sin(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("cos"),
        ev.eval(QStringLiteral("cos(0)")),
        QStringLiteral("1"));
  check(QStringLiteral("tan"),
        ev.eval(QStringLiteral("tan(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("asin"),
        ev.eval(QStringLiteral("asin(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("acos"),
        ev.eval(QStringLiteral("round(degrees(acos(0)))")),
        QStringLiteral("90"));
  check(QStringLiteral("atan"),
        ev.eval(QStringLiteral("atan(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("sinh"),
        ev.eval(QStringLiteral("sinh(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("cosh"),
        ev.eval(QStringLiteral("cosh(0)")),
        QStringLiteral("1"));
  check(QStringLiteral("tanh"),
        ev.eval(QStringLiteral("tanh(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("log1p"),
        ev.eval(QStringLiteral("log1p(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("expm1"),
        ev.eval(QStringLiteral("expm1(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("fdim"),
        ev.eval(QStringLiteral("fdim(3, 1)")),
        QStringLiteral("2"));
  check(QStringLiteral("nearbyint"),
        ev.eval(QStringLiteral("nearbyint(1.5)")),
        QStringLiteral("2"));
  check(QStringLiteral("bitshl"),
        ev.eval(QStringLiteral("bitshl(1, 3)")),
        QStringLiteral("8"));
  check(QStringLiteral("bitshr"),
        ev.eval(QStringLiteral("bitshr(8, 3)")),
        QStringLiteral("1"));
  check(QStringLiteral("remainder"),
        ev.eval(QStringLiteral("remainder(5, 3)")),
        QStringLiteral("-1"));
  check(QStringLiteral("scalbn"),
        ev.eval(QStringLiteral("scalbn(1.5, 1)")),
        QStringLiteral("3"));
  check(QStringLiteral("nextafter"),
        ev.eval(QStringLiteral("nextafter(1, 1)")),
        QStringLiteral("1"));
  check(QStringLiteral("tgamma"),
        ev.eval(QStringLiteral("tgamma(5)")),
        QStringLiteral("24"));
  check(QStringLiteral("lgamma"),
        ev.eval(QStringLiteral("lgamma(1)")),
        QStringLiteral("0"));
  check(QStringLiteral("erf"),
        ev.eval(QStringLiteral("erf(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("erfc"),
        ev.eval(QStringLiteral("erfc(0)")),
        QStringLiteral("1"));
  check(QStringLiteral("asinh"),
        ev.eval(QStringLiteral("asinh(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("acosh"),
        ev.eval(QStringLiteral("acosh(1)")),
        QStringLiteral("0"));
  check(QStringLiteral("atanh"),
        ev.eval(QStringLiteral("atanh(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("rint"),
        ev.eval(QStringLiteral("rint(1.5)")),
        QStringLiteral("2"));
  check(QStringLiteral("logb"),
        ev.eval(QStringLiteral("logb(8)")),
        QStringLiteral("3"));
  check(QStringLiteral("ilogb"),
        ev.eval(QStringLiteral("ilogb(8)")),
        QStringLiteral("3"));
  check(QStringLiteral("signbit"),
        ev.eval(QStringLiteral("signbit(-1)")),
        QStringLiteral("1"));
  check(QStringLiteral("isnormal"),
        ev.eval(QStringLiteral("isnormal(1)")),
        QStringLiteral("1"));
  check(QStringLiteral("fmax"),
        ev.eval(QStringLiteral("fmax(1, 3)")),
        QStringLiteral("3"));
  check(QStringLiteral("fmin"),
        ev.eval(QStringLiteral("fmin(1, 3)")),
        QStringLiteral("1"));
  check(QStringLiteral("bitnot"),
        ev.eval(QStringLiteral("bitnot(0)")),
        QStringLiteral("-1"));
  check(QStringLiteral("between"),
        ev.eval(QStringLiteral("between(2, 1, 3)")),
        QStringLiteral("1"));
  check(QStringLiteral("approxeq"),
        ev.eval(QStringLiteral("approxeq(1, 1.0000000001)")),
        QStringLiteral("1"));
  check(QStringLiteral("isalnum"),
        ev.eval(QStringLiteral("isalnum('A1')")),
        QStringLiteral("1"));
  check(QStringLiteral("swapcase"),
        ev.eval(QStringLiteral("swapcase('AbC')")),
        QStringLiteral("aBc"));
  check(QStringLiteral("radians"),
        ev.eval(QStringLiteral("round(degrees(radians(90)))")),
        QStringLiteral("90"));
  check(QStringLiteral("ord"),
        ev.eval(QStringLiteral("ord('A')")),
        QStringLiteral("65"));
  check(QStringLiteral("chr"),
        ev.eval(QStringLiteral("chr(65)")),
        QStringLiteral("A"));
  check(QStringLiteral("bin"),
        ev.eval(QStringLiteral("bin(5)")),
        QStringLiteral("0b101"));
  check(QStringLiteral("hex"),
        ev.eval(QStringLiteral("hex(255)")),
        QStringLiteral("0xff"));
  check(QStringLiteral("oct"),
        ev.eval(QStringLiteral("oct(8)")),
        QStringLiteral("0o10"));
  check(QStringLiteral("fabs"),
        ev.eval(QStringLiteral("fabs(-3)")),
        QStringLiteral("3"));
  check(QStringLiteral("fmod"),
        ev.eval(QStringLiteral("fmod(10, 4)")),
        QStringLiteral("2"));
  check(QStringLiteral("cbrt"),
        ev.eval(QStringLiteral("cbrt(8)")),
        QStringLiteral("2"));
  check(QStringLiteral("log10"),
        ev.eval(QStringLiteral("log10(100)")),
        QStringLiteral("2"));
  check(QStringLiteral("frac"),
        ev.eval(QStringLiteral("frac(3.25)")),
        QStringLiteral("0.25"));
  check(QStringLiteral("fract"),
        ev.eval(QStringLiteral("fract(3.25)")),
        QStringLiteral("0.25"));
  check(QStringLiteral("log2"),
        ev.eval(QStringLiteral("log2(8)")),
        QStringLiteral("3"));
  check(QStringLiteral("isfinite"),
        ev.eval(QStringLiteral("isfinite(1)")),
        QStringLiteral("1"));
  check(QStringLiteral("isnan"),
        ev.eval(QStringLiteral("isnan(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("isinf"),
        ev.eval(QStringLiteral("isinf(0)")),
        QStringLiteral("0"));
  check(QStringLiteral("atan2"),
        ev.eval(QStringLiteral("atan2(0, 1)")),
        QStringLiteral("0"));
  check(QStringLiteral("copysign"),
        ev.eval(QStringLiteral("copysign(3, -1)")),
        QStringLiteral("-3"));
  check(QStringLiteral("bitand"),
        ev.eval(QStringLiteral("bitand(6, 3)")),
        QStringLiteral("2"));
  check(QStringLiteral("bitor"),
        ev.eval(QStringLiteral("bitor(4, 1)")),
        QStringLiteral("5"));
  check(QStringLiteral("bitxor"),
        ev.eval(QStringLiteral("bitxor(6, 3)")),
        QStringLiteral("5"));
  check(QStringLiteral("gcd"),
        ev.eval(QStringLiteral("gcd(12, 8)")),
        QStringLiteral("4"));
  check(QStringLiteral("lcm"),
        ev.eval(QStringLiteral("lcm(4, 6)")),
        QStringLiteral("12"));
  check(QStringLiteral("clamp01"),
        ev.eval(QStringLiteral("clamp01(1.5)")),
        QStringLiteral("1"));
  check(QStringLiteral("saturate"),
        ev.eval(QStringLiteral("saturate(-0.2)")),
        QStringLiteral("0"));
  check(QStringLiteral("lerp"),
        ev.eval(QStringLiteral("lerp(0, 10, 0.5)")),
        QStringLiteral("5"));
  check(QStringLiteral("mix"),
        ev.eval(QStringLiteral("mix(0, 10, 0.5)")),
        QStringLiteral("5"));
  check(QStringLiteral("invlerp"),
        ev.eval(QStringLiteral("invlerp(0, 10, 5)")),
        QStringLiteral("0.5"));
  check(QStringLiteral("smoothstep"),
        ev.eval(QStringLiteral("smoothstep(0, 1, 0.5)")),
        QStringLiteral("0.5"));
  check(QStringLiteral("step"),
        ev.eval(QStringLiteral("step(0, 1)")),
        QStringLiteral("1"));
  check(QStringLiteral("islower"),
        ev.eval(QStringLiteral("islower('abc')")),
        QStringLiteral("1"));
  check(QStringLiteral("isupper"),
        ev.eval(QStringLiteral("isupper('ABC')")),
        QStringLiteral("1"));
  return fails;
}

}  // namespace sieans_qt
