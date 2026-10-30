#pragma once
#include <QWidget>
class QLabel;
class QHBoxLayout;

namespace sieans_qt {

/** PySide FilmstripBar chrome placeholder under image tabs. */
class FilmstripBar : public QWidget {
  Q_OBJECT
 public:
  explicit FilmstripBar(QWidget* parent = nullptr);
  void setStatus(const QString& text);
 signals:
  void openImageRequested();
  void runAllRequested();
 private:
  QLabel* status_ = nullptr;
};

}  // namespace sieans_qt
