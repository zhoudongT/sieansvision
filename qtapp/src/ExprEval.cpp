#include "ExprEval.hpp"
#include <functional>

#include <QRegularExpression>
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

}  // namespace

QVariant ExprEval::eval(const QString& raw, QString* error) const {
  QString expr = raw.trimmed();
  if (expr.isEmpty()) return 0;

  // Special-case join of step items texts (open-and-run barcodeAll)
  {
    static QRegularExpression joinRe(
        QStringLiteral(
            R"re("[^"]*"\s*\.\s*join\s*\(\s*i\.text\s+for\s+i\s+in\s+\(steps\["([^"]+)"\]\.items(?:\s+or\s+\[\])?\)\s*\))re"));
    auto m = joinRe.match(expr);
    if (m.hasMatch()) {
      const QString sid = m.captured(1);
      const StepSnap snap = steps_.value(sid);
      return snap.texts.join(QLatin1Char('\n'));
    }
  }

  // Rewrite steps["id"].items[N].text
  {
    static QRegularExpression itemText(
        QStringLiteral(R"re(steps\["([^"]+)"\]\.items\[(\d+)\]\.text)re"));
    QRegularExpressionMatchIterator it = itemText.globalMatch(expr);
    QList<QRegularExpressionMatch> ms;
    while (it.hasNext()) ms.prepend(it.next());
    for (const auto& m : ms) {
      const StepSnap snap = steps_.value(m.captured(1));
      const int idx = m.captured(2).toInt();
      const QString text =
          (idx >= 0 && idx < snap.texts.size()) ? snap.texts[idx] : QString();
      QString lit = QStringLiteral("\"%1\"").arg(
          QString(text).replace(QLatin1Char('\\'), QStringLiteral("\\\\"))
              .replace(QLatin1Char('"'), QStringLiteral("\\\"")));
      expr.replace(m.capturedStart(), m.capturedLength(), lit);
    }
  }
  // steps["id"].count
  {
    static QRegularExpression countRe(
        QStringLiteral(R"re(steps\["([^"]+)"\]\.count)re"));
    QRegularExpressionMatchIterator it = countRe.globalMatch(expr);
    QList<QRegularExpressionMatch> ms;
    while (it.hasNext()) ms.prepend(it.next());
    for (const auto& m : ms) {
      const int c = steps_.value(m.captured(1)).count;
      expr.replace(m.capturedStart(), m.capturedLength(), QString::number(c));
    }
  }
  // steps["id"].ok
  {
    static QRegularExpression okRe(QStringLiteral(R"re(steps\["([^"]+)"\]\.ok)re"));
    QRegularExpressionMatchIterator it = okRe.globalMatch(expr);
    QList<QRegularExpressionMatch> ms;
    while (it.hasNext()) ms.prepend(it.next());
    for (const auto& m : ms) {
      const int v = steps_.value(m.captured(1)).ok ? 1 : 0;
      expr.replace(m.capturedStart(), m.capturedLength(), QString::number(v));
    }
  }
  // steps["id"].items  (truthiness)
  {
    static QRegularExpression itemsRe(
        QStringLiteral(R"re(steps\["([^"]+)"\]\.items)re"));
    QRegularExpressionMatchIterator it = itemsRe.globalMatch(expr);
    QList<QRegularExpressionMatch> ms;
    while (it.hasNext()) ms.prepend(it.next());
    for (const auto& m : ms) {
      // skip if already rewritten as items[N]
      const int after = m.capturedStart() + m.capturedLength();
      if (after < expr.size() && expr[after] == QLatin1Char('[')) continue;
      const int v = steps_.value(m.captured(1)).texts.isEmpty() ? 0 : 1;
      expr.replace(m.capturedStart(), m.capturedLength(), QString::number(v));
    }
  }

  // Recursive evaluator on rewritten expr
  std::function<QVariant(QString)> evalRec;
  evalRec = [&](QString s) -> QVariant {
    s = stripParensOuter(s);
    if (s.isEmpty()) return 0;

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

    // * /
    pos = findTopLevel(s, {QStringLiteral("*"), QStringLiteral("/")});
    if (pos >= 0) {
      const QChar op = s[pos];
      QVariant L = evalRec(s.left(pos));
      QVariant R = evalRec(s.mid(pos + 1));
      if (op == QLatin1Char('*')) return L.toDouble() * R.toDouble();
      const double den = R.toDouble();
      return den == 0.0 ? QVariant(0) : QVariant(L.toDouble() / den);
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

}  // namespace sieans_qt
