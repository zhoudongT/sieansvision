#pragma once

#include <QDialog>
#include <QVariantMap>
#include <QJsonArray>

class QTableWidget;
class QCheckBox;
class QHBoxLayout;

namespace sieans_qt {

/** VM-like 流程参数：输入 / 输出 / 显示 — editable bindings written back to flow.io. */
class FlowIoDialog : public QDialog {
  Q_OBJECT
 public:
  explicit FlowIoDialog(const QVariantMap& io, QWidget* parent = nullptr);
  QVariantMap resultIo() const;

 private:
  QTableWidget* makeTable(const QVariantList& rows, const QString& kind);
  QVariantList readTable(QTableWidget* table) const;
  void addRow(QTableWidget* table);
  void removeSelectedRows(QTableWidget* table);
  void moveSelectedRows(QTableWidget* table, int delta);
  void duplicateSelectedRows(QTableWidget* table);
  void pasteRows(QTableWidget* table);
  void copySelectedRows(QTableWidget* table);
  void cutSelectedRows(QTableWidget* table);
  void clearEmptyRows(QTableWidget* table);
  void fillEmptyDefaults(QTableWidget* table);
  void clearEmptyDefaults(QTableWidget* table);
  void exportBindingsJson();
  void importBindingsJson();
  void applyJsonArray(QTableWidget* table, const QJsonArray& arr);
  void selectAllRows(QTableWidget* table);
  void insertBindingToken(QTableWidget* table, const QString& token);
  void wireRowOps(QTableWidget* table, QHBoxLayout* rowBtns);
  void moveSelectedToOtherTable(QTableWidget* from);
  void reverseRows(QTableWidget* table);

  QTableWidget* inTable_ = nullptr;
  QTableWidget* outTable_ = nullptr;
  QCheckBox* globalImage_ = nullptr;
  QVariantMap io_;
};

}  // namespace sieans_qt
