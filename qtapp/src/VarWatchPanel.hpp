#pragma once

#include <QWidget>
#include <QEvent>
#include <QTableWidget>
#include <QVariantMap>
#include <QStringList>

class QLineEdit;

namespace sieans_qt {

class VarWatchPanel : public QWidget {
  Q_OBJECT
 public:
  explicit VarWatchPanel(QWidget* parent = nullptr);

  void setWatchKeys(const QStringList& keys);
  void setVariables(const QVariantMap& vars);
  QVariantMap variables() const { return vars_; }

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

private:
  void rebuild();

  QTableWidget* table_ = nullptr;
  QLineEdit* filterEdit_ = nullptr;
  QStringList keys_;
  QVariantMap vars_;
  QString filter_;
};

}  // namespace sieans_qt
