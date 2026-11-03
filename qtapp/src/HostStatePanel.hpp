#pragma once

#include <QWidget>
#include <QString>
#include <QStringList>

class QTimer;

class QLabel;
class QListWidget;
class QComboBox;
class QSpinBox;
class QPushButton;
class QEvent;

namespace sieans_qt {

/**
 * Compact host HMI: Idle / Running / Paused / Alarm / Stopped,
 * start-pause-resume-stop, and an alarm history list.
 * Mechanical-arm jogs stay illustrative; start/stop drive the vision flow.
 */
class HostStatePanel : public QWidget {
  Q_OBJECT
 public:
  explicit HostStatePanel(QWidget* parent = nullptr);

  QString state() const { return state_; }
  void applyState(const QString& state);
  void raiseAlarm(const QString& reason);
  /** Next OK clears a latched alarm when policy is "下次运行成功清除". */
  void notifyOk();
  void bindFlow(const QString& name, int steps);
  /** Sync OK/NG/ms from HostStrip into HMI chrome. */
  void setRunStats(int okStreak, int ngCount, double lastMs = -1);
  void setRunIntervalMs(int ms);
  int runIntervalMs() const;
  void setHostMode(const QString& mode);
  QString hostMode() const;
  void setAlarmPolicy(const QString& policy);
  QString alarmPolicy() const;
  QStringList alarmHistoryLines() const;
  void setAlarmHistoryLines(const QStringList& lines);

 signals:
  void startRequested();
  void pauseRequested();
  void resumeRequested();
  void stopRequested();
  void clearAlarmRequested();
  void intervalChanged(int ms);
  void hostModeChanged(const QString& mode);
  void alarmPolicyChanged(const QString& policy);
  void alarmHistoryChanged(const QStringList& lines);

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

 private:
  void paintBadge();
  void appendAlarm(const QString& reason, bool cleared);
  void setButtons();
  void tickPulse();

  QString state_ = QStringLiteral("Idle");
  QString latchedRun_ = QStringLiteral("Idle");
  QString alarmPolicy_ = QStringLiteral("on_ok");
  QLabel* badge_ = nullptr;
  QLabel* flowLabel_ = nullptr;
  QLabel* modeHint_ = nullptr;
  QLabel* statsLabel_ = nullptr;
  QListWidget* history_ = nullptr;
  QComboBox* mode_ = nullptr;
  QComboBox* policy_ = nullptr;
  QSpinBox* intervalSpin_ = nullptr;
  QPushButton* btnStart_ = nullptr;
  QPushButton* btnPause_ = nullptr;
  QPushButton* btnResume_ = nullptr;
  QPushButton* btnStop_ = nullptr;
  QPushButton* btnClear_ = nullptr;
  QTimer* pulseTimer_ = nullptr;
  int pulsePhase_ = 0;
  int alarmCount_ = 0;
};

}  // namespace sieans_qt
