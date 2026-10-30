#pragma once

#include <QWidget>
#include <QLabel>
#include <QVariantMap>

namespace sieans_qt {

/** Thin OK/NG host strip under the image (cheap Host HMI slice). */
class HostStrip : public QWidget {
  Q_OBJECT
 public:
  explicit HostStrip(QWidget* parent = nullptr);
  void updateFromVars(const QVariantMap& vars, int codeCount = -1);

 private:
  QLabel* badge_ = nullptr;
  QLabel* detail_ = nullptr;
};

}  // namespace sieans_qt
