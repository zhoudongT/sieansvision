#pragma once
#include "PropertyPanel.hpp"
#include <QDialog>
#include <QPoint>
#include <QVariantMap>

class QLabel;
class QPushButton;
class QFrame;

namespace sieans_qt {

/** Light property float over dark canvas — PySide PropertyFloat 1:1 chrome. */
class PropertyFloat : public QDialog {
  Q_OBJECT
 public:
  explicit PropertyFloat(QWidget* parent = nullptr);

  PropertyPanel* panel() const { return panel_; }
  void setNodeTitle(const QString& title, const QString& subtitle = {});
  void showForSource(const QVariantMap& sourceConfig);
  void showForStep(const FlowStep& step);

 signals:
  void paramEdited(const QString& nodeId, const QString& key, const QString& value);
  void runModule();
  void runModuleContinuous();
  void acceptedCommit();
  /** ✕ / 取消：把打开浮窗时的参数快照交还，由主窗口写回。 */
  void paramsReverted(const QString& nodeId, const QVariantMap& snapshot);

 protected:
  void mousePressEvent(QMouseEvent* event) override;
  void mouseMoveEvent(QMouseEvent* event) override;
  void mouseReleaseEvent(QMouseEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;

 private:
  void revertAndHide();

  PropertyPanel* panel_ = nullptr;
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
};

}  // namespace sieans_qt
