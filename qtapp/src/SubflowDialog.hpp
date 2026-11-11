#pragma once

#include "SieansDocument.hpp"

#include <QDialog>

class QCloseEvent;

class QListWidget;
class QComboBox;
class QLabel;

namespace sieans_qt {

class FlowScene;
class FlowView;

/** 子流程管理：新建 / 编辑画布 / 选择输出节点 / 删除未引用定义. */
class SubflowDialog : public QDialog {
  Q_OBJECT
 public:
  explicit SubflowDialog(SieansDocument* host, QWidget* parent = nullptr);

 protected:
  void closeEvent(QCloseEvent* event) override;

 private:
  void refreshList();
  void createDef();
  void chooseCurrent();
  void saveCurrent();
  void removeCurrent();
  void addOperator();
  void addOperatorAt(const QString& key, const QPointF& pos);
  void rebuildOutputCombo();
  void onOutputChanged();

  SieansDocument* host_ = nullptr;
  SieansDocument work_;
  QString currentId_;
  QListWidget* list_ = nullptr;
  QComboBox* catalog_ = nullptr;
  QComboBox* output_ = nullptr;
  QLabel* notice_ = nullptr;
  FlowScene* scene_ = nullptr;
  FlowView* view_ = nullptr;
  bool loading_ = false;
};

}  // namespace sieans_qt
