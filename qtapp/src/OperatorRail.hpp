#pragma once
#include <QWidget>
#include <QButtonGroup>
class QToolButton;

namespace sieans_qt {

/** Narrow vertical category rail — VisionMaster / PySide OperatorRail 1:1. */
class OperatorRail : public QWidget {
  Q_OBJECT
 public:
  explicit OperatorRail(QWidget* parent = nullptr);
 signals:
  /** Empty string = show all categories. */
  void categorySelected(const QString& category);
 private:
  QButtonGroup* group_ = nullptr;
};

}  // namespace sieans_qt
