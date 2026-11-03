#pragma once

#include <QWidget>
#include <QLabel>
#include <QVariantMap>
#include <QStringList>

class QEvent;
class QKeyEvent;

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
  /** Continuous run interval (ms) — shown on cycle chip; wheel nudges. */
  void setIntervalMs(int ms);
  int intervalMs() const { return intervalMs_; }
  void resetStreak();
  void copyRunStats();
  void pasteWatchKeysFromClipboard();
  void copyWatchKeys();
  void exportWatchKeysJson();
  void moveWatchKey(int delta);
  void reverseWatchKeys();
  void removeHeadWatchKey();
  void clearWatchKeys();
  void sortWatchKeys();
  void dedupeWatchKeys();
  int okStreak() const { return okStreak_; }
  int ngCount() const { return ngCount_; }

 signals:
  void modeToggleRequested();
  void continuousToggleRequested();
  void pauseRequested();
  void stopRequested();
  void runOnceRequested();
  void runContinuousRequested();
  void cycleResetRequested();
  void openHostRequested();
  void watchKeysChanged(const QStringList& keys);
  void intervalChanged(int ms);

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;

 private:
  void refreshChips(const QVariantMap& vars);
  void refreshCycleChip();

  QLabel* badge_ = nullptr;
  QLabel* detail_ = nullptr;
  QLabel* chips_ = nullptr;
  QLabel* alarmLabel_ = nullptr;
  QLabel* modeChip_ = nullptr;
  QLabel* cycleChip_ = nullptr;
  QStringList watchKeys_;
  QVariantMap lastVars_;
  bool alarmOn_ = false;
  QString alarmReason_;
  QString tcpStatus_;
  QString hostState_ = QStringLiteral("Idle");
  int cycle_ = 0;
  double lastCycleMs_ = -1;
  int intervalMs_ = 200;
  int okStreak_ = 0;
  int ngCount_ = 0;
};

}  // namespace sieans_qt
