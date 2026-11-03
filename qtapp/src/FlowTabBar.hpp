#pragma once
#include <QWidget>
class QPushButton;
class QHBoxLayout;
class QLabel;
class QEvent;

namespace sieans_qt {

/** PySide FlowTabBar subset: 全流程 + current flow tab + run once/continuous. */
class FlowTabBar : public QWidget {
  Q_OBJECT
 public:
  explicit FlowTabBar(QWidget* parent = nullptr);
  void setFlowName(const QString& name);
  void setRunChrome(const QString& mode, int cycle, double lastMs, bool continuous, bool paused);
  void setDesignLocked(bool locked);
 signals:
  void allFlowsRequested();
  void runOnceRequested();
  void runContinuousRequested();
  void stopRequested();
  void pauseRequested();
  void fitRequested();
  void ioRequested();
  void continuousToggleRequested();
  void cycleResetRequested();
 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;
 private:
  QPushButton* allBtn_ = nullptr;
  QPushButton* flowBtn_ = nullptr;
  QPushButton* pauseBtn_ = nullptr;
  QLabel* cycleLabel_ = nullptr;
  QLabel* modeChip_ = nullptr;
};

}  // namespace sieans_qt
