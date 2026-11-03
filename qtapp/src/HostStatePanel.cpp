#include "HostStatePanel.hpp"

#include <QComboBox>
#include <QDateTime>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QPushButton>
#include <QVBoxLayout>
#include <QTimer>

namespace sieans_qt {
namespace {

struct BadgeStyle {
  const char* bg;
  const char* fg;
  const char* zh;
};

BadgeStyle styleFor(const QString& state) {
  if (state == QLatin1String("Running"))
    return {"#1c3a2a", "#3ecf8e", "运行中"};
  if (state == QLatin1String("Paused"))
    return {"#3a3420", "#e0b84a", "已暂停"};
  if (state == QLatin1String("Alarm"))
    return {"#3a1c1c", "#e35d6a", "报警"};
  if (state == QLatin1String("Stopped"))
    return {"#2a3340", "#8a9bb0", "已停止"};
  return {"#2a3340", "#8a9bb0", "空闲"};
}

}  // namespace

HostStatePanel::HostStatePanel(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("hostStateMachine"));
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(8, 6, 8, 6);
  root->setSpacing(6);

  auto* head = new QHBoxLayout;
  auto* title = new QLabel(QStringLiteral("上位机控制程序"));
  title->setStyleSheet(QStringLiteral("font-weight:700;font-size:13px;"));
  head->addWidget(title);
  head->addStretch(1);
  badge_ = new QLabel;
  badge_->setAlignment(Qt::AlignCenter);
  badge_->setMinimumWidth(72);
  head->addWidget(badge_);
  root->addLayout(head);

  flowLabel_ = new QLabel(QStringLiteral("绑定流程：—"));
  flowLabel_->setObjectName(QStringLiteral("muted"));
  root->addWidget(flowLabel_);

  auto* quick = new QHBoxLayout;
  quick->setSpacing(4);
  btnStart_ = new QPushButton(QStringLiteral("▶ 开始"));
  btnPause_ = new QPushButton(QStringLiteral("⏸ 暂停"));
  btnResume_ = new QPushButton(QStringLiteral("▶ 继续"));
  btnStop_ = new QPushButton(QStringLiteral("■ 停止"));
  btnClear_ = new QPushButton(QStringLiteral("清除报警"));
  btnStart_->setObjectName(QStringLiteral("primaryButton"));
  for (QPushButton* b : {btnStart_, btnPause_, btnResume_, btnStop_, btnClear_}) {
    b->setMinimumHeight(28);
    quick->addWidget(b);
  }
  quick->addStretch(1);
  root->addLayout(quick);

  auto* modeRow = new QHBoxLayout;
  mode_ = new QComboBox;
  mode_->addItems({QStringLiteral("正常生产"), QStringLiteral("九点标定"),
                   QStringLiteral("旋转标定")});
  mode_->setToolTip(QStringLiteral("标定模式只切换壳状态；开始仍跑当前视觉流程"));
  policy_ = new QComboBox;
  policy_->addItem(QStringLiteral("下次运行成功清除"), QStringLiteral("on_ok"));
  policy_->addItem(QStringLiteral("关闭（需手动清除）"), QStringLiteral("off"));
  modeRow->addWidget(new QLabel(QStringLiteral("模式")));
  modeRow->addWidget(mode_, 1);
  modeRow->addWidget(new QLabel(QStringLiteral("报警清除")));
  modeRow->addWidget(policy_, 1);
  root->addLayout(modeRow);

  modeHint_ = new QLabel;
  modeHint_->setObjectName(QStringLiteral("muted"));
  modeHint_->setWordWrap(true);
  root->addWidget(modeHint_);

  auto* histTitle = new QLabel(QStringLiteral("报警历史"));
  histTitle->setStyleSheet(QStringLiteral("font-weight:600;"));
  root->addWidget(histTitle);
  history_ = new QListWidget;
  history_->setObjectName(QStringLiteral("alarmHistory"));
  history_->setMinimumHeight(72);
  root->addWidget(history_, 1);

  connect(btnStart_, &QPushButton::clicked, this, [this]() {
    if (mode_->currentIndex() > 0) {
      modeHint_->setText(
          QStringLiteral("%1：本壳不驱动标定轴，开始仍执行当前绑定流程。")
              .arg(mode_->currentText()));
    } else {
      modeHint_->clear();
    }
    emit startRequested();
  });
  connect(btnPause_, &QPushButton::clicked, this, &HostStatePanel::pauseRequested);
  connect(btnResume_, &QPushButton::clicked, this, &HostStatePanel::resumeRequested);
  connect(btnStop_, &QPushButton::clicked, this, &HostStatePanel::stopRequested);
  connect(btnClear_, &QPushButton::clicked, this, [this]() {
    appendAlarm(QStringLiteral("手动清除"), true);
    applyState(QStringLiteral("Idle"));
    emit clearAlarmRequested();
  });
  connect(policy_, &QComboBox::currentIndexChanged, this, [this](int) {
    alarmPolicy_ = policy_->currentData().toString();
  });

  applyState(QStringLiteral("Idle"));
}

void HostStatePanel::bindFlow(const QString& name, int steps) {
  flowLabel_->setText(QStringLiteral("流程 · %1 · %2 步").arg(name).arg(steps));
  if (modeHint_ && modeHint_->text().isEmpty())
    modeHint_->setText(QStringLiteral("HMI · Idle/Running/Paused/Alarm · 开始驱动当前流程"));
}

void HostStatePanel::paintBadge() {
  const BadgeStyle s = styleFor(state_);
  badge_->setText(QString::fromUtf8(s.zh));
  QString extra;
  if (state_ == QLatin1String("Running") && (pulsePhase_ & 1))
    extra = QStringLiteral("outline:1px solid %1;").arg(QString::fromUtf8(s.fg));
  badge_->setStyleSheet(
      QStringLiteral("background:%1;color:%2;border-radius:3px;font-weight:700;"
                     "padding:4px 8px;%3")
          .arg(QString::fromUtf8(s.bg), QString::fromUtf8(s.fg), extra));
}

void HostStatePanel::tickPulse() {
  if (state_ != QLatin1String("Running")) {
    if (pulseTimer_) pulseTimer_->stop();
    return;
  }
  ++pulsePhase_;
  paintBadge();
}

void HostStatePanel::setButtons() {
  const bool alarm = state_ == QLatin1String("Alarm");
  const bool running = state_ == QLatin1String("Running");
  const bool paused = state_ == QLatin1String("Paused");
  btnStart_->setEnabled(!running);
  btnPause_->setEnabled(running);
  btnResume_->setEnabled(paused || alarm);
  btnStop_->setEnabled(running || paused || alarm);
  btnClear_->setEnabled(alarm);
}

void HostStatePanel::applyState(const QString& state) {
  state_ = state;
  if (state != QLatin1String("Alarm")) latchedRun_ = state;
  if (state == QLatin1String("Running")) {
    if (!pulseTimer_) {
      pulseTimer_ = new QTimer(this);
      pulseTimer_->setInterval(550);
      connect(pulseTimer_, &QTimer::timeout, this, &HostStatePanel::tickPulse);
    }
    pulsePhase_ = 0;
    if (!pulseTimer_->isActive()) pulseTimer_->start();
  } else if (pulseTimer_) {
    pulseTimer_->stop();
    pulsePhase_ = 0;
  }
  paintBadge();
  setButtons();
}

void HostStatePanel::appendAlarm(const QString& reason, bool cleared) {
  const QString ts =
      QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss"));
  const QString line =
      cleared ? QStringLiteral("%1  清除  %2").arg(ts, reason)
              : QStringLiteral("%1  ALARM  %2").arg(ts, reason);
  history_->insertItem(0, line);
  while (history_->count() > 40) delete history_->takeItem(history_->count() - 1);
  if (!cleared) ++alarmCount_;
}

void HostStatePanel::raiseAlarm(const QString& reason) {
  const QString why = reason.isEmpty() ? QStringLiteral("未命名报警") : reason;
  if (state_ == QLatin1String("Alarm") && history_->count() > 0 &&
      history_->item(0)->text().contains(why))
    return;
  appendAlarm(why, false);
  applyState(QStringLiteral("Alarm"));
}

void HostStatePanel::notifyOk() {
  if (state_ != QLatin1String("Alarm")) return;
  if (alarmPolicy_ != QLatin1String("on_ok")) return;
  appendAlarm(QStringLiteral("运行成功自动清除"), true);
  const QString back = (latchedRun_ == QLatin1String("Running") ||
                        latchedRun_ == QLatin1String("Paused"))
                           ? latchedRun_
                           : QStringLiteral("Idle");
  applyState(back);
}

}  // namespace sieans_qt
