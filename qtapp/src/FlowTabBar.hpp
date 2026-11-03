#pragma once
#include <QWidget>
class QPushButton;
class QHBoxLayout;
class QLabel;
class QEvent;
class QKeyEvent;

namespace sieans_qt {

/** PySide FlowTabBar subset: 全流程 + current flow tab + run once/continuous. */
class FlowTabBar : public QWidget {
  Q_OBJECT
 public:
  explicit FlowTabBar(QWidget* parent = nullptr);
  void setFlowName(const QString& name);
  void setRunChrome(const QString& mode, int cycle, double lastMs, bool continuous, bool paused);
  void setIntervalMs(int ms);
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
  void modeToggleRequested();
  void cycleResetRequested();
  void intervalChanged(int ms);
 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;
 private:
  QPushButton* allBtn_ = nullptr;
  QPushButton* flowBtn_ = nullptr;
  QPushButton* pauseBtn_ = nullptr;
  QLabel* cycleLabel_ = nullptr;
  QLabel* modeChip_ = nullptr;
  int intervalMs_ = 200;
  int cycle_ = 0;
  double lastMs_ = -1;
  bool continuous_ = false;
  bool paused_ = false;
  void refreshCycleLabel();
};

}  // namespace sieans_qt
