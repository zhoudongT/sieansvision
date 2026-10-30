#pragma once

#include <QListWidget>
#include <QWidget>

namespace sieans_qt {

struct OperatorDef {
  QString key;
  QString name;
  QString category;
  QString tip;
};

class OperatorLibrary : public QWidget {
  Q_OBJECT
 public:
  explicit OperatorLibrary(QWidget* parent = nullptr);
  static QVector<OperatorDef> catalog();

 signals:
  void operatorActivated(const QString& key, const QString& name);

 private:
  QListWidget* list_ = nullptr;
};

}  // namespace sieans_qt
