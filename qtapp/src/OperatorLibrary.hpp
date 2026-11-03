#pragma once
#include <QWidget>
#include <QVector>
#include <QString>

class QListWidget;
class QListWidgetItem;
class QLineEdit;
class QEvent;

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
  static OperatorDef findDef(const QString& key);
  void setCategoryFilter(const QString& category);
  void focusSearch();

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

 signals:
  void operatorActivated(const QString& key, const QString& name);

 private:
  void rebuild();
  void rememberRecent(const QString& key);
  QListWidget* list_ = nullptr;
  QLineEdit* search_ = nullptr;
  QString categoryFilter_;
  QStringList recentKeys_;
};

}  // namespace sieans_qt
