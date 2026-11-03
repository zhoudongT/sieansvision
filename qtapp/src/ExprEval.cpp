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
          QStringLiteral(R"re(^(len|int|str|abs|min|max|startswith|endswith|contains|lower|upper|trim|strip|replace|slice|isdigit|isalpha|lpad|rpad|repeat|substr)\((.*)\)$)re"));
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
        if (name == QLatin1String("str"))
          return args.isEmpty() ? QString() : evalRec(args[0]).toString();
        if (name == QLatin1String("abs"))
          return args.isEmpty() ? 0 : std::fabs(evalRec(args[0]).toDouble());
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
        if (name == QLatin1String("trim") || name == QLatin1String("strip"))
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
        if (name == QLatin1String("slice") || name == QLatin1String("substr")) {
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
  return fails;
}

}  // namespace sieans_qt
