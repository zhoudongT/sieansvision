#pragma once

#include "SieansDocument.hpp"

#include <QFormLayout>
#include <QLabel>
#include <QLineEdit>
#include <QScrollArea>
#include <QWidget>

namespace sieans_qt {

class PropertyPanel : public QWidget {
  Q_OBJECT
 public:
  explicit PropertyPanel(QWidget* parent = nullptr);

  void showSource(const QVariantMap& sourceConfig);
  void showStep(const FlowStep& step);
  void clear();

 signals:
  void paramEdited(const QString& nodeId, const QString& key, const QString& value);

 private:
  void rebuildForm(const QString& title, const QString& nodeId,
                   const QVariantMap& params, const QStringList& preferKeys);

  QLabel* title_ = nullptr;
  QLabel* meta_ = nullptr;
  QWidget* formHost_ = nullptr;
  QFormLayout* form_ = nullptr;
  QString currentId_;
};

}  // namespace sieans_qt
