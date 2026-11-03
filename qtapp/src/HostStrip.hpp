#pragma once

#include <QWidget>
#include <QLabel>
#include <QVariantMap>
#include <QStringList>

namespace sieans_qt {

/** Host OK/NG/ALARM strip + watch chips under the image (VM 运行条). */
class HostStrip : public QWidget {
  Q_OBJECT
 public:
  explicit HostStrip(QWidget* parent = nullptr);
  void updateFromVars(const QVariantMap& vars, int codeCount = -1, bool evaluated = false);
  void setWatchKeys(const QStringList& keys);
  void setAlarm(bool on, const QString& reason = {});
  /** 设计态 / 运行态 / 连续 / 暂停 — thin HMI chrome. */
  void setRunChrome(const QString& mode, const QString& hostState, int cycle = 0);

 private:
  void refreshChips(const QVariantMap& vars);

  QLabel* badge_ = nullptr;
  QLabel* detail_ = nullptr;
  QLabel* chips_ = nullptr;
  QLabel* alarmLabel_ = nullptr;
  QLabel* modeChip_ = nullptr;
  QLabel* cycleChip_ = nullptr;
  QStringList watchKeys_;
  bool alarmOn_ = false;
  QString alarmReason_;
};

}  // namespace sieans_qt
