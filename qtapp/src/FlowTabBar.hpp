#pragma once
#include <QWidget>
#include <QVector>
#include <QPair>
class QPushButton;
class QHBoxLayout;
class QLabel;
class QEvent;
class QKeyEvent;
class QWidget;

namespace sieans_qt {

/** PySide FlowTabBar subset: 全流程 + current flow tab + run once/continuous. */
class FlowTabBar : public QWidget {
  Q_OBJECT
 public:
  explicit FlowTabBar(QWidget* parent = nullptr);
  void setFlowName(const QString& name);
  /** 刷新流程 Tab：id/name 列表与当前活动 id（不自动发 flowActivated）。 */
  void setFlows(const QVector<QPair<QString, QString>>& flows, const QString& activeId);
  void setRunChrome(const QString& mode, int cycle, double lastMs, bool continuous, bool paused);
  void setIntervalMs(int ms);
  void pasteIntervalMs();
  void copyCycleChip();
  void setDesignLocked(bool locked);
 signals:
  void flowActivated(const QString& flowId);
  void addFlowRequested();
  void renameFlowRequested(const QString& flowId);
  void duplicateFlowRequested(const QString& flowId);
  void removeFlowRequested(const QString& flowId);
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
  QWidget* flowTabsHost_ = nullptr;
  QHBoxLayout* flowTabsLay_ = nullptr;
  QPushButton* addFlowBtn_ = nullptr;
  QVector<QPair<QString, QString>> flowTabs_;
  QString activeFlowId_;
  bool designLocked_ = false;
  /** 按 flowTabs_ 重建可点选的流程页签和 + 按钮。 */
  void rebuildFlowTabs();
  /** 弹出流程页签的重命名/复制/删除菜单。 */
  void showFlowTabMenu(const QString& flowId, const QPoint& globalPos);
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
