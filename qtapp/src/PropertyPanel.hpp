#pragma once

#include "SieansDocument.hpp"

#include <QFormLayout>
#include <QLabel>
#include <QScrollArea>
#include <QString>
#include <QVector>
#include <QWidget>

class QLineEdit;

namespace sieans_qt {

class PropertyPanel : public QWidget {
  Q_OBJECT
 public:
  explicit PropertyPanel(QWidget* parent = nullptr);

  void showSource(const QVariantMap& sourceConfig);
  void showStep(const FlowStep& step);
  void clear();
  /** Live param map while the float is open (edits applied immediately). */
  QVariantMap currentParams() const { return params_; }
  void focusFilter();
  void copyVisibleParams();
  void pasteKeyValueParams();
  void exportParamsJson();
  void importParamsJson();
  /** Re-apply a param snapshot into live editors (PF Ctrl+R). */
  void applySnapshot(const QVariantMap& snap);
  /** Force QLineEdit editingFinished before OK / Ctrl+S. */
  void flushPendingEdits();

 signals:
  void paramEdited(const QString& nodeId, const QString& key, const QString& value);

 private:
  struct Spec {
    QString key;
    QString label;
    int kind = 0;  // 0 line, 1 int, 2 real, 3 bool, 4 choice
    QString choices;
  };
  static QVector<Spec> specsFor(const QString& op);
  void rebuildForm(const QString& title, const QString& nodeId, const QString& op,
                   const QVariantMap& params);
  void addSpecRow(const Spec& spec, const QVariantMap& params);
  void addExprTable(const QVariantList& rows);
  void addRulesTable(const QVariantList& rows);
  void addPathsTable(const QVariantList& rows);
  void emitEdit(const QString& key, const QString& value);
  void applyFilter();

  QLabel* title_ = nullptr;
  QLineEdit* filterEdit_ = nullptr;
  QLabel* meta_ = nullptr;
  QWidget* formHost_ = nullptr;
  QFormLayout* form_ = nullptr;
  QString currentId_;
  QVariantMap params_;
  bool building_ = false;
};

}  // namespace sieans_qt
