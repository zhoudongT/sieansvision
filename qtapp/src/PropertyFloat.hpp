#pragma once
#include "PropertyPanel.hpp"
#include "LocateMatchPanel.hpp"
#include <QDialog>
#include <QPoint>
#include <QRect>
#include <QVariantMap>

class QLabel;
class QPushButton;
class QFrame;

namespace sieans_qt {

/** 炭灰+橙属性浮窗（覆盖画布的无框工具窗；快捷键走工具提示与「?」，不在页脚铺快捷键表）。 */
class PropertyFloat : public QDialog {
  Q_OBJECT
 public:
  explicit PropertyFloat(QWidget* parent = nullptr);

  PropertyPanel* panel() const { return panel_; }
  LocateMatchPanel* locatePanel() const { return locatePanel_; }
  /** 把最近一次 locate 运行结果刷进四 Tab 的结果显示页。 */
  void setLocateLastResult(const QVariantMap& vars);
  void setNodeTitle(const QString& title, const QString& subtitle = {});
  void showForSource(const QVariantMap& sourceConfig);
  void showForStep(const FlowStep& step);
  void applyChromeGeometry(const QRect& geom);
  void notifyChromeGeometry();

 signals:
  void paramEdited(const QString& nodeId, const QString& key, const QString& value);
  void structuredParamEdited(const QString& nodeId, const QString& key, const QVariant& value);
  void sparkJumpRequested(const QVariantMap& bag);
  void runModule();
  void runModuleContinuous();
  void acceptedCommit();
  /** ✕ / 取消：把打开浮窗时的参数快照交还，由主窗口写回。 */
  void paramsReverted(const QString& nodeId, const QVariantMap& snapshot);
  void chromeGeometryChanged(const QRect& geom);

 protected:
  void mousePressEvent(QMouseEvent* event) override;
  void mouseDoubleClickEvent(QMouseEvent* event) override;
  void mouseMoveEvent(QMouseEvent* event) override;
  void mouseReleaseEvent(QMouseEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;

 private:
  void revertAndHide();
  /** 提交当前可见属性页（通用或 locate 四 Tab）的未完成编辑。 */
  void flushActiveEditors();
  /** 当前可见属性页的参数快照。 */
  QVariantMap activeParams() const;
  bool showingLocatePanel() const;

  PropertyPanel* panel_ = nullptr;
  LocateMatchPanel* locatePanel_ = nullptr;
  QLabel* title_ = nullptr;
  QLabel* subtitle_ = nullptr;
  QFrame* titleBar_ = nullptr;
  QPushButton* closeBtn_ = nullptr;
  QPushButton* pinBtn_ = nullptr;
  bool pinned_ = false;
  QString nodeId_;
  QVariantMap baseline_;
  QPoint dragOffset_;
  bool dragging_ = false;
  QRect pinnedGeom_;
  qreal opacity_ = 1.0;
};

}  // namespace sieans_qt
