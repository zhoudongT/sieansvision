#pragma once

#include <QWidget>
#include <QLabel>
#include <QVariantMap>
#include <QStringList>

namespace sieans_qt {

/** Host OK/NG/ALARM strip + watch chips under the image. */
class HostStrip : public QWidget {
  Q_OBJECT
 public:
  explicit HostStrip(QWidget* parent = nullptr);
  void updateFromVars(const QVariantMap& vars, int codeCount = -1);
  void setWatchKeys(const QStringList& keys);
  void setAlarm(bool on, const QString& reason = {});

 private:
  void refreshChips(const QVariantMap& vars);

  QLabel* badge_ = nullptr;
  QLabel* detail_ = nullptr;
  QLabel* chips_ = nullptr;
  QLabel* alarmLabel_ = nullptr;
  QStringList watchKeys_;
  bool alarmOn_ = false;
  QString alarmReason_;
};

}  // namespace sieans_qt
