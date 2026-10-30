#pragma once
#include "PropertyPanel.hpp"
#include <QDialog>

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

 private:
  PropertyPanel* panel_ = nullptr;
  QLabel* title_ = nullptr;
  QLabel* subtitle_ = nullptr;
  QString nodeId_;
};

}  // namespace sieans_qt
