#pragma once

#include <QString>
#include <QVariant>
#include <QVariantMap>
#include <QHash>
#include <QStringList>

namespace sieans_qt {

/** Per-step run snapshot for steps["id"].field access in var_calc. */
struct StepSnap {
  int count = 0;
  bool ok = false;
  double score = 0;
  double confidence = 0;
  QString text;
  int matches = 0;     // len(steps[id].matches)
  QStringList texts;   // items[].text
  QVariantMap fields;  // arbitrary extras (.field)
};

/**
 * Subset of Python expressions used by open-and-run var_calc rows:
 *  - numbers, strings, identifiers, flow.name
 *  - + - * / // % and comparisons
 *  - or / and / not
 *  - ternary: A if COND else B
 *  - steps["id"].count|ok|score|confidence|text|matches|items|items[N].text
 *  - len(...), int/str/abs/min/max
 *  - "\\n".join(i.text for i in (steps["id"].items or []))
 */
class ExprEval {
 public:
  void setVars(const QVariantMap& vars) { vars_ = vars; }
  void setSteps(const QHash<QString, StepSnap>& steps) { steps_ = steps; }

  QVariant eval(const QString& expr, QString* error = nullptr) const;

 private:
  QVariantMap vars_;
  QHash<QString, StepSnap> steps_;
};

/** Built-in rows from projects/*.sieans. Empty list means all passed. */
QStringList exprSelfTest();

}  // namespace sieans_qt
