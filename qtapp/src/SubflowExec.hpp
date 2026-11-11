#pragma once

#include "SieansDocument.hpp"

#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>
#include <QVector>

namespace sieans_qt {

/** Parameters of a 子流程调用 / 循环子流程 node. */
struct SubflowCallParams {
  QString subflowId;
  QVariantMap arguments;  // name → literal or parent binding token
  QString stateMode = QStringLiteral("reset");  // reset | preserve
  QString mode = QStringLiteral("count");       // count | until (loop)
  int iterations = 1;                           // 1–100
  QString frameMode = QStringLiteral("previous");  // original | previous
  QString stopField = QStringLiteral("passed");
  QVariant stopValue = true;
};

/** Preserved per-call-site local state (stateMode=preserve). */
struct SubflowState {
  QString definitionId;
  QVariantMap flow;
};

/** Outcome of one subflow or loop invocation. */
struct SubflowResult {
  bool ok = false;
  QString error;
  int completedIterations = 0;
  bool stoppedEarly = false;
  bool passed = false;
  QVariantMap value;      // output-node result (passed is boolean)
  QVariantMap localVars;  // isolated flow scope (no _iteration leak if stripped)
  QString subflowId;
  QString subflowName;
  QString note;
  int visitCount = 0;
};

/** Read call params from an operator's param map. */
SubflowCallParams parseSubflowParams(const QVariantMap& params, bool isLoop);

/**
 * Run a subflow (once) or a loop over it.
 * Local variables are isolated; parentVars are read-only except we never write
 * them here — the caller publishes selected outputs.
 * depth is the current nesting (0 = root call). Max 4. Max 1000 visits.
 * If stateMode=preserve and *state matches definitionId, local vars start from
 * that snapshot; on success *state is updated.
 */
SubflowResult runSubflowCall(const SubflowDef& def,
                             const QVector<SubflowDef>& library,
                             const SubflowCallParams& params,
                             const QVariantMap& parentVars,
                             SubflowState* state,
                             int depth,
                             int& visitCount,
                             const QStringList& callStack);

/** Built-in 计数子流程 used by the seed demo and self-test. */
SubflowDef makeCounterSubflow();

/** Empty list = all passed. No QApplication required. */
QStringList subflowSelfTest();

}  // namespace sieans_qt
