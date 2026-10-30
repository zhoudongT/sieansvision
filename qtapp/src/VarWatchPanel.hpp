#pragma once

#include <QWidget>
#include <QTableWidget>
#include <QVariantMap>
#include <QStringList>

namespace sieans_qt {

class VarWatchPanel : public QWidget {
  Q_OBJECT
 public:
  explicit VarWatchPanel(QWidget* parent = nullptr);

  void setWatchKeys(const QStringList& keys);
  void setVariables(const QVariantMap& vars);
  QVariantMap variables() const { return vars_; }

 private:
  void rebuild();

  QTableWidget* table_ = nullptr;
  QStringList keys_;
  QVariantMap vars_;
};

}  // namespace sieans_qt
