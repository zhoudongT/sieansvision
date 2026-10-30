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
  QStringList texts;  // items[].text
  QVariantMap fields; // arbitrary extras
};

/**
 * Useful subset for open-and-run / passgate templates:
 *  - numbers, "strings", identifiers → vars
 *  - + - * / ( ) and comparisons == != < > <= >=
 *  - Python-ish `or` / `and`
 *  - ternary: A if COND else B
 *  - steps["id"].count / .ok / .items / .items[N].text
 *  - "\\n".join(i.text for i in (steps["id"].items or []))  → join texts
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

}  // namespace sieans_qt
