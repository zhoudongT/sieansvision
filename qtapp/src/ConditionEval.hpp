#pragma once

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>
#include <functional>

namespace sieans_qt {

/** Resolved operand for strict-type condition compares. */
struct ConditionValue {
  enum Kind { Null, Number, String, Boolean, Missing } kind = Null;
  double number = 0.0;
  QString string;
  bool boolean = false;
  QString source;  // original token, for error text
};

/** Outcome of a condition / branch evaluation. */
struct ConditionResult {
  bool ok = false;       // false = missing ref / type error (job fails)
  bool passed = false;   // valid only when ok
  QString branchTaken;   // "true"/"false" or path id/name
  QString note;
  QString error;
};

/**
 * Resolve a form token against flow variables.
 * Supports literals, quoted strings, ${name} / ${flow.name} / {name},
 * and bare identifiers. Missing identifiers yield Kind::Missing.
 */
ConditionValue resolveConditionToken(const QString& raw, const QVariantMap& vars);

/** Compare two resolved values. On type error sets *error and returns false. */
bool compareCondition(const ConditionValue& left, const QString& comparison,
                      const ConditionValue& right, QString* error);

/**
 * Evaluate 条件判断: rules[] with AND/OR, or flat left/comparison/right.
 * Does not execute expression code. Missing refs / type errors fail (ok=false)
 * and must not be treated as "不成立".
 */
ConditionResult evaluateCondition(const QVariantMap& params,
                                  const QVariantMap& vars);

/**
 * Evaluate 分支模块: first enabled non-default path whose compare passes,
 * otherwise defaultPathId.
 */
ConditionResult evaluateBranch(const QVariantMap& params, const QVariantMap& vars);

/** Built-in unit checks (no QApplication). Empty list = all passed. */
QStringList conditionSelfTest();

}  // namespace sieans_qt
