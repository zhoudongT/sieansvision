#pragma once
#include <QWidget>
class QPushButton;
class QHBoxLayout;

namespace sieans_qt {

/** PySide FlowTabBar subset: 全流程 + current flow tab + run once/continuous. */
class FlowTabBar : public QWidget {
  Q_OBJECT
 public:
  explicit FlowTabBar(QWidget* parent = nullptr);
  void setFlowName(const QString& name);
 signals:
  void allFlowsRequested();
  void runOnceRequested();
  void runContinuousRequested();
 private:
  QPushButton* allBtn_ = nullptr;
  QPushButton* flowBtn_ = nullptr;
};

}  // namespace sieans_qt
