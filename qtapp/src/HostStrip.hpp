#pragma once

#include <QWidget>
#include <QLabel>
#include <QVariantMap>
#include <QStringList>

class QEvent;

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
  void setTcpStatus(const QString& status);
  /** Last completed-cycle wall time (ms) — shown on cycle chip. */
  void setCycleTiming(double lastMs);
  void resetStreak();
  int okStreak() const { return okStreak_; }
  int ngCount() const { return ngCount_; }

 signals:
  void modeToggleRequested();
  void continuousToggleRequested();
  void cycleResetRequested();
  void openHostRequested();
  void watchKeysChanged(const QStringList& keys);

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

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
  QString tcpStatus_;
  int cycle_ = 0;
  double lastCycleMs_ = -1;
  int okStreak_ = 0;
  int ngCount_ = 0;
};

}  // namespace sieans_qt
