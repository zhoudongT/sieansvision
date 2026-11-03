#include "HostStatePanel.hpp"

#include <algorithm>

#include <QComboBox>
#include <QSpinBox>
#include <QDateTime>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QAbstractItemView>
#include <QPushButton>
#include <QVBoxLayout>
#include <QTimer>
#include <QShortcut>
#include <QKeySequence>
#include <QApplication>
#include <QClipboard>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QEvent>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QWheelEvent>

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
  setFocusPolicy(Qt::StrongFocus);
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
  badge_->setToolTip(QStringLiteral("上位机状态 · Idle/Running/Paused/Alarm/Stopped"));
  head->addWidget(badge_);
  root->addLayout(head);

  flowLabel_ = new QLabel(QStringLiteral("绑定流程：—"));
  flowLabel_->setObjectName(QStringLiteral("muted"));
  flowLabel_->setCursor(Qt::PointingHandCursor);
  flowLabel_->setToolTip(QStringLiteral("流程绑定 · 双击复制 · 中键启动 · 右键停止"));
  flowLabel_->installEventFilter(this);
  root->addWidget(flowLabel_);
  statsLabel_ = new QLabel(QStringLiteral("连OK 0 · NG 0 · — ms"));
  statsLabel_->setObjectName(QStringLiteral("hostRunStats"));
  statsLabel_->setToolTip(QStringLiteral("运行统计 · 连OK/NG/上次周期 ms · 来自 Host 条 · 单击/Ctrl+Shift+S 复制 · 中键JSON · 右键清报警 · Ctrl+Shift+C"));
  statsLabel_->setCursor(Qt::PointingHandCursor);
  statsLabel_->installEventFilter(this);
  root->addWidget(statsLabel_);

  auto* quick = new QHBoxLayout;
  quick->setSpacing(4);
  btnStart_ = new QPushButton(QStringLiteral("▶ 开始"));
  btnPause_ = new QPushButton(QStringLiteral("⏸ 暂停"));
  btnResume_ = new QPushButton(QStringLiteral("▶ 继续"));
  btnStop_ = new QPushButton(QStringLiteral("■ 停止"));
  btnClear_ = new QPushButton(QStringLiteral("清除报警"));
  btnStart_->setObjectName(QStringLiteral("primaryButton"));
  btnStart_->setToolTip(QStringLiteral("开始运行当前绑定流程 · F5/F9 · 连续 F6 · 已运行则重入"));
  btnStart_->setStatusTip(QStringLiteral("Host · 开始运行"));
  btnPause_->setToolTip(QStringLiteral("暂停连续运行 · F7 · 连续中可暂停 · 单次运行无效"));
  btnPause_->setStatusTip(QStringLiteral("Host · 暂停"));
  btnResume_->setToolTip(QStringLiteral("从暂停/报警继续 · Idle 时无效"));
  btnResume_->setStatusTip(QStringLiteral("Host · 继续"));
  btnStop_->setToolTip(QStringLiteral("停止运行并回 Idle · Esc · 清连续标志"));
  btnStop_->setStatusTip(QStringLiteral("Host · 停止 · Esc"));
  btnClear_->setToolTip(QStringLiteral("清除报警锁存 · 不清运行状态 · Alarm→可继续"));
  btnClear_->setStatusTip(QStringLiteral("Host · 清除报警"));
  setStatusTip(QStringLiteral("上位机控制 · F5/F9 开始 · F6 连续 · F7 暂停/继续 · Space 开始/暂停 · 暂停/继续 · Esc 停止 · 清报警 · 双击徽章清报警 · 右键徽章清除 · Ctrl+Shift+C 复制历史"));
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
  policy_ = new QComboBox;
  policy_->addItem(QStringLiteral("下次运行成功清除"), QStringLiteral("on_ok"));
  policy_->addItem(QStringLiteral("关闭（需手动清除）"), QStringLiteral("off"));
  modeRow->addWidget(new QLabel(QStringLiteral("模式")));
  modeRow->addWidget(mode_, 1);
  mode_->installEventFilter(this);
  mode_->setToolTip(QStringLiteral("标定模式 · 滚轮/中键/F8 切换 · Alt+1/2/3 → 生产/九点/旋转 · 双击复制 · 开始仍跑当前视觉流程 · 非标定=生产"));
  modeRow->addWidget(new QLabel(QStringLiteral("报警清除")));
  modeRow->addWidget(policy_, 1);
  policy_->installEventFilter(this);
  policy_->setToolTip(QStringLiteral("报警清除策略 · 滚轮/中键/F4 切换 · Alt+1/2 → on_ok/手动 · 双击复制"));
  root->addLayout(modeRow);

  auto* ivRow = new QHBoxLayout;
  ivRow->addWidget(new QLabel(QStringLiteral("连续间隔")));
  intervalSpin_ = new QSpinBox;
  intervalSpin_->setRange(20, 60000);
  intervalSpin_->setSingleStep(50);
  intervalSpin_->setSuffix(QStringLiteral(" ms"));
  intervalSpin_->setValue(200);
  intervalSpin_->setToolTip(QStringLiteral("连续运行节拍 · 写入方案 runIntervalMs · 滚轮±50 · Ctrl+↑↓/[] ±50 · Ctrl+Shift+↑↓/[] ±200 · Alt+1/2/3/4 → 50/100/200/500 · 双击复制 · 中键复位200 · 运行中即时生效"));
  intervalSpin_->setStatusTip(QStringLiteral("Host · 连续间隔 ms"));
  intervalSpin_->installEventFilter(this);
  ivRow->addWidget(intervalSpin_, 1);
  ivRow->addStretch(1);
  root->addLayout(ivRow);
  connect(intervalSpin_, QOverload<int>::of(&QSpinBox::valueChanged), this, [this](int v) {
    emit intervalChanged(v);
    if (modeHint_)
      modeHint_->setText(QStringLiteral("连续间隔 %1 ms").arg(v));
  });

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
  history_->setToolTip(QStringLiteral("报警历史 · Esc停止 · Space/F5/F9 启停 · F6/F7 暂停续 · F8/Shift+F8 切模式 · F4 策略 · 双击/中键复制 · 右键/Ctrl+L 清空 · Del 删行 · Ctrl+A 全选 · Ctrl+D 复制行 · Ctrl+X 剪切 · Alt+↑↓ 调序 · Ctrl+Home/End 置顶/底 · Ctrl+Shift+Y 反序 · Ctrl+Shift+S 排序 · Ctrl+Shift+U 去重 · Ctrl+Shift+J/V JSON导出/粘贴 · 最近 40 条"));
  history_->setStatusTip(QStringLiteral("Host · 报警历史 · Ctrl+L/Del/双击/中键"));
  history_->installEventFilter(this);
  history_->setSelectionMode(QAbstractItemView::ExtendedSelection);
  root->addWidget(history_, 1);
  {
    auto* scL = new QShortcut(QKeySequence(QStringLiteral("Ctrl+L")), history_);
    connect(scL, &QShortcut::activated, this, [this]() {
      if (!history_) return;
      history_->clear();
      emit alarmHistoryChanged(alarmHistoryLines());
      if (modeHint_)
        modeHint_->setText(QStringLiteral("报警历史已清空 · Ctrl+L"));
    });
    auto* scDel = new QShortcut(QKeySequence(Qt::Key_Delete), history_);
    connect(scDel, &QShortcut::activated, this, [this]() {
      if (!history_) return;
      for (auto* it : history_->selectedItems()) delete history_->takeItem(history_->row(it));
      emit alarmHistoryChanged(alarmHistoryLines());
    });
    auto* scJ = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+J")), history_);
    connect(scJ, &QShortcut::activated, this, [this]() {
      if (!history_) return;
      QJsonArray arr;
      for (int i = 0; i < history_->count(); ++i) {
        auto* it = history_->item(i);
        if (it) arr.append(it->text());
      }
      QJsonObject root;
      root.insert(QStringLiteral("alarms"), arr);
      root.insert(QStringLiteral("state"), state_);
      root.insert(QStringLiteral("count"), arr.size());
      const QByteArray bytes = QJsonDocument(root).toJson(QJsonDocument::Compact);
      if (auto* clip = QGuiApplication::clipboard())
        clip->setText(QString::fromUtf8(bytes));
      if (modeHint_)
        modeHint_->setText(QStringLiteral("已导出报警JSON %1 · Ctrl+Shift+J").arg(arr.size()));
    });
    auto* scV = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+V")), history_);
    connect(scV, &QShortcut::activated, this, [this]() { pasteAlarmHistoryFromClipboard(); });
    auto* scX = new QShortcut(QKeySequence(QStringLiteral("Ctrl+X")), history_);
    connect(scX, &QShortcut::activated, this, [this]() { cutSelectedAlarmHistory(); });
    auto* scY = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+Y")), history_);
    connect(scY, &QShortcut::activated, this, [this]() { reverseAlarmHistory(); });
    auto* scS = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+S")), history_);
    connect(scS, &QShortcut::activated, this, [this]() { sortAlarmHistory(); });
    auto* scU = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+U")), history_);
    connect(scU, &QShortcut::activated, this, [this]() { dedupeAlarmHistory(); });
    auto* scHome = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Home")), history_);
    connect(scHome, &QShortcut::activated, this, [this]() { moveSelectedAlarmToEdge(-1); });
    auto* scEnd = new QShortcut(QKeySequence(QStringLiteral("Ctrl+End")), history_);
    connect(scEnd, &QShortcut::activated, this, [this]() { moveSelectedAlarmToEdge(+1); });
    auto* scUp = new QShortcut(QKeySequence(QStringLiteral("Alt+Up")), history_);
    connect(scUp, &QShortcut::activated, this, [this]() { moveSelectedAlarm(-1); });
    auto* scDn = new QShortcut(QKeySequence(QStringLiteral("Alt+Down")), history_);
    connect(scDn, &QShortcut::activated, this, [this]() { moveSelectedAlarm(+1); });
    auto* scA = new QShortcut(QKeySequence(QStringLiteral("Ctrl+A")), history_);
    connect(scA, &QShortcut::activated, this, [this]() { selectAllAlarmHistory(); });
    auto* scDup = new QShortcut(QKeySequence(QStringLiteral("Ctrl+D")), history_);
    connect(scDup, &QShortcut::activated, this, [this]() { duplicateSelectedAlarmHistory(); });

    connect(history_, &QListWidget::itemDoubleClicked, this, [this](QListWidgetItem* it) {
      if (!it) return;
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(it->text());
        if (modeHint_)
          modeHint_->setText(QStringLiteral("已复制报警行 · 双击"));
      }
    });
  }

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
    emit alarmPolicyChanged(alarmPolicy_);
  });
  connect(mode_, &QComboBox::currentIndexChanged, this, [this](int) {
    if (!mode_) return;
    emit hostModeChanged(mode_->currentText());
  });
  {
    auto* sc = new QShortcut(QKeySequence(Qt::Key_F5), this);
    connect(sc, &QShortcut::activated, this, &HostStatePanel::startRequested);
    auto* sc9 = new QShortcut(QKeySequence(Qt::Key_F9), this);
    connect(sc9, &QShortcut::activated, this, &HostStatePanel::startRequested);
    auto* sc6 = new QShortcut(QKeySequence(Qt::Key_F6), this);
    connect(sc6, &QShortcut::activated, this, [this]() {
      if (state_ == QLatin1String("Running")) emit pauseRequested();
      else if (state_ == QLatin1String("Paused")) emit resumeRequested();
      else emit startRequested();
    });
    auto* sc7 = new QShortcut(QKeySequence(Qt::Key_F7), this);
    connect(sc7, &QShortcut::activated, this, [this]() {
      if (state_ == QLatin1String("Paused")) emit resumeRequested();
      else if (state_ == QLatin1String("Running")) emit pauseRequested();
    });
    auto* scEsc = new QShortcut(QKeySequence(Qt::Key_Escape), this);
    connect(scEsc, &QShortcut::activated, this, &HostStatePanel::stopRequested);
    auto* scSp = new QShortcut(QKeySequence(Qt::Key_Space), this);
    connect(scSp, &QShortcut::activated, this, [this]() {
      if (state_ == QLatin1String("Running")) emit pauseRequested();
      else if (state_ == QLatin1String("Paused")) emit resumeRequested();
      else emit startRequested();
    });
    auto* scF8 = new QShortcut(QKeySequence(Qt::Key_F8), this);
    connect(scF8, &QShortcut::activated, this, [this]() { cycleHostMode(+1); });
    auto* scF8b = new QShortcut(QKeySequence(QStringLiteral("Shift+F8")), this);
    connect(scF8b, &QShortcut::activated, this, [this]() { cycleHostMode(-1); });
    auto* scF4 = new QShortcut(QKeySequence(Qt::Key_F4), this);
    connect(scF4, &QShortcut::activated, this, [this]() { cycleAlarmPolicy(+1); });
    auto* scF4b = new QShortcut(QKeySequence(QStringLiteral("Shift+F4")), this);
    connect(scF4b, &QShortcut::activated, this, [this]() { cycleAlarmPolicy(-1); });
    auto* scCopyHist = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), this);
    connect(scCopyHist, &QShortcut::activated, this, [this]() {
      if (!history_) return;
      QStringList lines;
      for (int i = 0; i < history_->count(); ++i)
        if (auto* it = history_->item(i)) lines << it->text();
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
      if (modeHint_)
        modeHint_->setText(QStringLiteral("已复制报警历史 %1 行 · Ctrl+Shift+C").arg(lines.size()));
    });
  }
  if (badge_) {
    badge_->setCursor(Qt::PointingHandCursor);
    badge_->setToolTip(QStringLiteral("上位机状态 · Idle/Running/Paused/Alarm/Stopped · 双击清除报警 · 右键清除 · 中键暂停/继续"));
    badge_->installEventFilter(this);
  }

  applyState(QStringLiteral("Idle"));
}

void HostStatePanel::setRunStats(int okStreak, int ngCount, double lastMs) {
  if (!statsLabel_) return;
  const int total = okStreak + ngCount;
  const double yld = total > 0 ? (100.0 * okStreak / total) : 0.0;
  QString ms = lastMs >= 0 ? QStringLiteral("%1 ms").arg(lastMs, 0, 'f', 1)
                          : QStringLiteral("— ms");
  statsLabel_->setText(
      QStringLiteral("连OK %1 · NG %2 · 良率 %3% · %4")
          .arg(okStreak).arg(ngCount).arg(yld, 0, 'f', 1).arg(ms));
}

void HostStatePanel::bindFlow(const QString& name, int steps) {
  flowLabel_->setText(QStringLiteral("流程 · %1 · %2 步").arg(name).arg(steps));
  if (modeHint_ && modeHint_->text().isEmpty())
    modeHint_->setText(QStringLiteral("HMI · Idle/Running/Paused/Alarm · 开始驱动当前流程 · 历史 Ctrl+L/Del/双击"));
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
  emit alarmHistoryChanged(alarmHistoryLines());
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

void HostStatePanel::setRunIntervalMs(int ms) {
  if (!intervalSpin_) return;
  const int v = qBound(20, ms > 0 ? ms : 200, 60000);
  const bool blocked = intervalSpin_->blockSignals(true);
  intervalSpin_->setValue(v);
  intervalSpin_->blockSignals(blocked);
}

int HostStatePanel::runIntervalMs() const {
  return intervalSpin_ ? intervalSpin_->value() : 200;
}

bool HostStatePanel::eventFilter(QObject* obj, QEvent* event) {
  if (obj == badge_ && event->type() == QEvent::MouseButtonDblClick) {
    appendAlarm(QStringLiteral("双击徽章清除"), true);
    applyState(QStringLiteral("Idle"));
    emit clearAlarmRequested();
    if (modeHint_)
      modeHint_->setText(QStringLiteral("报警已清除 · 双击徽章"));
    return true;
  }
  if (obj == badge_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::RightButton) {
      appendAlarm(QStringLiteral("右键徽章清除"), true);
      applyState(QStringLiteral("Idle"));
      emit clearAlarmRequested();
      if (modeHint_)
        modeHint_->setText(QStringLiteral("报警已清除 · 右键徽章"));
      return true;
    }
    if (me->button() == Qt::MiddleButton) {
      if (state_ == QLatin1String("Running")) {
        emit pauseRequested();
        if (modeHint_) modeHint_->setText(QStringLiteral("暂停 · 中键徽章"));
      } else if (state_ == QLatin1String("Paused")) {
        emit resumeRequested();
        if (modeHint_) modeHint_->setText(QStringLiteral("继续 · 中键徽章"));
      }
      return true;
    }
  }
  if (obj == intervalSpin_ && event->type() == QEvent::MouseButtonDblClick) {
    if (intervalSpin_) {
      if (auto* clip = QGuiApplication::clipboard())
        clip->setText(QString::number(intervalSpin_->value()));
      if (modeHint_)
        modeHint_->setText(QStringLiteral("已复制节拍 %1 ms · 双击").arg(intervalSpin_->value()));
    }
    return true;
  }
  if (obj == intervalSpin_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton && intervalSpin_) {
      if (intervalSpin_->value() != 200) intervalSpin_->setValue(200);
      if (modeHint_) modeHint_->setText(QStringLiteral("节拍复位 200 ms · 中键"));
      return true;
    }
  }
  if (obj == flowLabel_ && event->type() == QEvent::MouseButtonDblClick) {
    if (flowLabel_) {
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(flowLabel_->text());
        if (modeHint_)
          modeHint_->setText(QStringLiteral("已复制流程绑定 · 双击"));
      }
    }
    return true;
  }
  if (obj == flowLabel_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      emit startRequested();
      if (modeHint_) modeHint_->setText(QStringLiteral("启动 · 中键流程名"));
      return true;
    }
    if (me->button() == Qt::RightButton) {
      emit stopRequested();
      if (modeHint_) modeHint_->setText(QStringLiteral("停止 · 右键流程名"));
      return true;
    }
  }
  if (obj == statsLabel_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton && statsLabel_) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(statsLabel_->text());
      if (modeHint_) modeHint_->setText(QStringLiteral("已复制运行统计 · 单击"));
      return true;
    }
    if (me->button() == Qt::MiddleButton && statsLabel_) {
      const QString raw = statsLabel_->text();
      if (auto* clip = QGuiApplication::clipboard())
        clip->setText(QStringLiteral("{\"stats\":\"%1\",\"state\":\"%2\"}")
                          .arg(raw, state_));
      if (modeHint_) modeHint_->setText(QStringLiteral("已复制统计JSON · 中键"));
      return true;
    }
    if (me->button() == Qt::RightButton) {
      emit clearAlarmRequested();
      if (modeHint_) modeHint_->setText(QStringLiteral("清报警 · 右键统计"));
      return true;
    }
  }
  if (obj == history_ && event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_Space &&
        !(ke->modifiers() & (Qt::ControlModifier | Qt::AltModifier | Qt::ShiftModifier))) {
      if (state_ == QLatin1String("Running")) emit pauseRequested();
      else if (state_ == QLatin1String("Paused")) emit resumeRequested();
      else emit startRequested();
      if (modeHint_) modeHint_->setText(QStringLiteral("Space · 开始/暂停"));
      return true;
    }
    if (ke->key() == Qt::Key_Escape) {
      emit stopRequested();
      if (modeHint_) modeHint_->setText(QStringLiteral("停止 · Esc"));
      return true;
    }
    if (ke->key() == Qt::Key_F5 || ke->key() == Qt::Key_F9) {
      emit startRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F6) {
      if (state_ == QLatin1String("Running")) emit pauseRequested();
      else if (state_ == QLatin1String("Paused")) emit resumeRequested();
      else emit startRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F7) {
      if (state_ == QLatin1String("Paused")) emit resumeRequested();
      else if (state_ == QLatin1String("Running")) emit pauseRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F8) {
      cycleHostMode((ke->modifiers() & Qt::ShiftModifier) ? -1 : +1);
      return true;
    }
    if (ke->key() == Qt::Key_F4) {
      cycleAlarmPolicy((ke->modifiers() & Qt::ShiftModifier) ? -1 : +1);
      return true;
    }
  }
  if (obj == history_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton && history_) {
      QListWidgetItem* hit = history_->itemAt(me->position().toPoint());
      if (!hit) hit = history_->currentItem();
      if (hit) {
        if (auto* clip = QGuiApplication::clipboard()) clip->setText(hit->text());
        if (modeHint_) modeHint_->setText(QStringLiteral("已复制报警行 · 中键"));
      }
      return true;
    }
    if (me->button() == Qt::RightButton && history_) {
      history_->clear();
      emit alarmHistoryChanged(alarmHistoryLines());
      if (modeHint_) modeHint_->setText(QStringLiteral("报警历史已清空 · 右键"));
      return true;
    }
  }
  if (obj == policy_ && event->type() == QEvent::Wheel) {
    auto* we = static_cast<QWheelEvent*>(event);
    if (!policy_ || policy_->count() <= 0) return true;
    int i = policy_->currentIndex();
    i += (we->angleDelta().y() > 0 ? -1 : +1);
    if (i < 0) i = policy_->count() - 1;
    if (i >= policy_->count()) i = 0;
    policy_->setCurrentIndex(i);
    if (modeHint_)
      modeHint_->setText(QStringLiteral("报警策略 %1 · 滚轮").arg(policy_->currentText()));
    return true;
  }
  if (obj == mode_ && event->type() == QEvent::MouseButtonDblClick) {
    if (mode_) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(mode_->currentText());
      if (modeHint_) modeHint_->setText(QStringLiteral("已复制模式 · 双击"));
    }
    return true;
  }
  if (obj == mode_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      cycleHostMode(+1);
      return true;
    }
  }
  if (obj == policy_ && event->type() == QEvent::MouseButtonDblClick) {
    if (policy_) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(policy_->currentText());
      if (modeHint_) modeHint_->setText(QStringLiteral("已复制报警策略 · 双击"));
    }
    return true;
  }
  if (obj == policy_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      cycleAlarmPolicy(+1);
      return true;
    }
  }
  if (obj == mode_ && event->type() == QEvent::Wheel) {
    auto* we = static_cast<QWheelEvent*>(event);
    if (!mode_ || mode_->count() <= 0) return true;
    int i = mode_->currentIndex();
    i += (we->angleDelta().y() > 0 ? -1 : +1);
    if (i < 0) i = mode_->count() - 1;
    if (i >= mode_->count()) i = 0;
    mode_->setCurrentIndex(i);
    if (modeHint_) modeHint_->setText(QStringLiteral("模式 %1 · 滚轮").arg(mode_->currentText()));
    return true;
  }
  if (event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_C && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier) && statsLabel_) {
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(statsLabel_->text());
      if (modeHint_) modeHint_->setText(QStringLiteral("已复制运行统计 · Ctrl+Shift+C"));
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) && intervalSpin_ &&
        (ke->key() == Qt::Key_Up || ke->key() == Qt::Key_Down ||
         ke->key() == Qt::Key_BracketLeft || ke->key() == Qt::Key_BracketRight)) {
      const int step = (ke->modifiers() & Qt::ShiftModifier) ? 200 : 50;
      int delta = 0;
      if (ke->key() == Qt::Key_Up || ke->key() == Qt::Key_BracketRight) delta = step;
      else delta = -step;
      const int next = qBound(20, intervalSpin_->value() + delta, 60000);
      if (next != intervalSpin_->value()) {
        intervalSpin_->setValue(next);  // emits intervalChanged
        if (modeHint_)
          modeHint_->setText(QStringLiteral("连续间隔 %1 ms · Ctrl+↑↓/[]").arg(next));
      }
      return true;
    }
    if ((ke->modifiers() & Qt::AltModifier) && !(ke->modifiers() & Qt::ControlModifier) &&
        ke->key() >= Qt::Key_1 && ke->key() <= Qt::Key_4) {
      if (obj == mode_ && mode_) {
        const int idx = ke->key() - Qt::Key_1;
        if (idx < mode_->count()) {
          mode_->setCurrentIndex(idx);
          if (modeHint_)
            modeHint_->setText(QStringLiteral("模式 %1 · Alt+%2").arg(mode_->currentText()).arg(idx + 1));
        }
        return true;
      }
      if (obj == policy_ && policy_) {
        const int idx = ke->key() - Qt::Key_1;
        if (idx < policy_->count()) {
          policy_->setCurrentIndex(idx);
          if (modeHint_)
            modeHint_->setText(
                QStringLiteral("报警策略 %1 · Alt+%2").arg(policy_->currentText()).arg(idx + 1));
        }
        return true;
      }
      if (intervalSpin_) {
        static const int kPresets[] = {50, 100, 200, 500};
        const int next = kPresets[ke->key() - Qt::Key_1];
        if (next != intervalSpin_->value()) intervalSpin_->setValue(next);
        if (modeHint_)
          modeHint_->setText(QStringLiteral("节拍 %1 ms · Alt+%2").arg(next).arg(ke->key() - Qt::Key_0));
        return true;
      }
    }

  }
  return QWidget::eventFilter(obj, event);
}


void HostStatePanel::setHostMode(const QString& mode) {
  if (!mode_) return;
  const QString t = mode.trimmed();
  int idx = mode_->findText(t);
  if (idx < 0 && !t.isEmpty()) {
    // tolerate stored index as string
    bool ok = false;
    const int asInt = t.toInt(&ok);
    if (ok && asInt >= 0 && asInt < mode_->count()) idx = asInt;
  }
  if (idx < 0) idx = 0;
  const bool blocked = mode_->blockSignals(true);
  mode_->setCurrentIndex(idx);
  mode_->blockSignals(blocked);
}

QString HostStatePanel::hostMode() const {
  return mode_ ? mode_->currentText() : QStringLiteral("正常生产");
}

void HostStatePanel::setAlarmPolicy(const QString& policy) {
  if (!policy_) return;
  QString t = policy.trimmed();
  if (t.isEmpty()) t = QStringLiteral("on_ok");
  int idx = policy_->findData(t);
  if (idx < 0) idx = policy_->findText(t);
  if (idx < 0) idx = 0;
  const bool blocked = policy_->blockSignals(true);
  policy_->setCurrentIndex(idx);
  policy_->blockSignals(blocked);
  alarmPolicy_ = policy_->currentData().toString();
}

QString HostStatePanel::alarmPolicy() const {
  return alarmPolicy_;
}


QStringList HostStatePanel::alarmHistoryLines() const {
  QStringList out;
  if (!history_) return out;
  for (int i = 0; i < history_->count(); ++i) {
    if (auto* it = history_->item(i)) out << it->text();
  }
  return out;
}

void HostStatePanel::setAlarmHistoryLines(const QStringList& lines) {
  if (!history_) return;
  history_->clear();
  for (const QString& line : lines) {
    const QString t = line.trimmed();
    if (!t.isEmpty()) history_->addItem(t);
  }
  while (history_->count() > 40) delete history_->takeItem(history_->count() - 1);
}



void HostStatePanel::cutSelectedAlarmHistory() {
  if (!history_) return;
  QList<QListWidgetItem*> selected = history_->selectedItems();
  if (selected.isEmpty()) {
    if (modeHint_) modeHint_->setText(QStringLiteral("无选中报警行 · Ctrl+X"));
    return;
  }
  QStringList lines;
  QList<int> rows;
  for (auto* it : selected) {
    if (!it) continue;
    lines << it->text();
    rows << history_->row(it);
  }
  if (auto* clip = QGuiApplication::clipboard())
    clip->setText(lines.join(QLatin1Char('\n')));
  std::sort(rows.begin(), rows.end(), std::greater<int>());
  for (int r : rows) {
    if (r >= 0) delete history_->takeItem(r);
  }
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("已剪切报警 %1 · Ctrl+X · Ctrl+Shift+V 粘贴").arg(lines.size()));
}

void HostStatePanel::cycleHostMode(int delta) {
  if (!mode_ || mode_->count() == 0) return;
  const int n = mode_->count();
  int i = mode_->currentIndex();
  if (i < 0) i = 0;
  i = (i + delta) % n;
  if (i < 0) i += n;
  mode_->setCurrentIndex(i);
  if (modeHint_)
    modeHint_->setText(QStringLiteral("模式 · %1 · F8").arg(mode_->currentText()));
}

void HostStatePanel::cycleAlarmPolicy(int delta) {
  if (!policy_ || policy_->count() == 0) return;
  const int n = policy_->count();
  int i = policy_->currentIndex();
  if (i < 0) i = 0;
  i = (i + delta) % n;
  if (i < 0) i += n;
  policy_->setCurrentIndex(i);
  if (modeHint_)
    modeHint_->setText(QStringLiteral("报警策略 · %1 · F4").arg(policy_->currentText()));
}


void HostStatePanel::pasteAlarmHistoryFromClipboard() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text().trimmed()
                          : QString();
  if (raw.isEmpty() || !history_) {
    if (modeHint_) modeHint_->setText(QStringLiteral("剪贴板空 · Ctrl+Shift+V"));
    return;
  }
  QStringList lines;
  // Prefer JSON {"alarms":[...]} from Ctrl+Shift+J export
  QJsonParseError err;
  const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &err);
  if (err.error == QJsonParseError::NoError && doc.isObject()) {
    const QJsonArray arr = doc.object().value(QStringLiteral("alarms")).toArray();
    for (const QJsonValue& v : arr) {
      const QString t = v.toString().trimmed();
      if (!t.isEmpty()) lines << t;
    }
  }
  if (lines.isEmpty()) {
    for (QString line : raw.split(QLatin1Char('\n'))) {
      line = line.trimmed();
      if (!line.isEmpty()) lines << line;
    }
  }
  if (lines.isEmpty()) {
    if (modeHint_) modeHint_->setText(QStringLiteral("无报警行 · Ctrl+Shift+V"));
    return;
  }
  // Prepend (newest first), cap 40
  for (int i = lines.size() - 1; i >= 0; --i)
    history_->insertItem(0, lines.at(i));
  while (history_->count() > 40) delete history_->takeItem(history_->count() - 1);
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("已粘贴报警 %1 · Ctrl+Shift+V").arg(lines.size()));
}

void HostStatePanel::reverseAlarmHistory() {
  if (!history_ || history_->count() < 2) {
    if (modeHint_) modeHint_->setText(QStringLiteral("报警不足 · Ctrl+Shift+Y"));
    return;
  }
  QStringList lines = alarmHistoryLines();
  std::reverse(lines.begin(), lines.end());
  history_->clear();
  for (const QString& line : lines) history_->addItem(line);
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("报警已反序 %1 · Ctrl+Shift+Y").arg(lines.size()));
}


void HostStatePanel::sortAlarmHistory() {
  if (!history_ || history_->count() < 2) {
    if (modeHint_) modeHint_->setText(QStringLiteral("报警不足 · Ctrl+Shift+S"));
    return;
  }
  QStringList lines = alarmHistoryLines();
  std::sort(lines.begin(), lines.end(),
            [](const QString& a, const QString& b) {
              return QString::localeAwareCompare(a, b) < 0;
            });
  history_->clear();
  for (const QString& line : lines) history_->addItem(line);
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("报警已排序 %1 · Ctrl+Shift+S").arg(lines.size()));
}


void HostStatePanel::dedupeAlarmHistory() {
  if (!history_ || history_->count() <= 0) {
    if (modeHint_) modeHint_->setText(QStringLiteral("报警空 · Ctrl+Shift+U"));
    return;
  }
  QStringList lines = alarmHistoryLines();
  QStringList uniq;
  int dropped = 0;
  for (const QString& line : lines) {
    if (uniq.contains(line)) { ++dropped; continue; }
    uniq << line;
  }
  if (dropped <= 0) {
    if (modeHint_) modeHint_->setText(QStringLiteral("无重复报警 · Ctrl+Shift+U"));
    return;
  }
  history_->clear();
  for (const QString& line : uniq) history_->addItem(line);
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("报警去重 −%1 · 剩 %2 · Ctrl+Shift+U")
                           .arg(dropped)
                           .arg(uniq.size()));
}



void HostStatePanel::moveSelectedAlarm(int delta) {
  if (!history_ || history_->count() < 2 || delta == 0) {
    if (modeHint_) modeHint_->setText(QStringLiteral("报警不足 · Alt+↑↓"));
    return;
  }
  const auto selected = history_->selectedItems();
  if (selected.isEmpty()) {
    if (modeHint_) modeHint_->setText(QStringLiteral("未选中 · Alt+↑↓"));
    return;
  }
  // Move contiguous selection as a block (first selected as anchor)
  QList<int> rows;
  for (auto* it : selected) rows << history_->row(it);
  std::sort(rows.begin(), rows.end());
  if (delta < 0) {
    if (rows.first() <= 0) {
      if (modeHint_) modeHint_->setText(QStringLiteral("已在顶 · Alt+↑"));
      return;
    }
    for (int r : rows) {
      auto* it = history_->takeItem(r);
      history_->insertItem(r - 1, it);
      it->setSelected(true);
    }
  } else {
    if (rows.last() >= history_->count() - 1) {
      if (modeHint_) modeHint_->setText(QStringLiteral("已在底 · Alt+↓"));
      return;
    }
    for (int i = rows.size() - 1; i >= 0; --i) {
      const int r = rows[i];
      auto* it = history_->takeItem(r);
      history_->insertItem(r + 1, it);
      it->setSelected(true);
    }
  }
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("报警调序 %1 行 · Alt+↑↓").arg(rows.size()));
}

void HostStatePanel::moveSelectedAlarmToEdge(int edge) {
  if (!history_ || history_->count() < 2) {
    if (modeHint_) modeHint_->setText(QStringLiteral("报警不足 · Ctrl+Home/End"));
    return;
  }
  const auto selected = history_->selectedItems();
  if (selected.isEmpty()) {
    if (modeHint_) modeHint_->setText(QStringLiteral("未选中 · Ctrl+Home/End"));
    return;
  }
  QList<int> rows;
  for (auto* it : selected) rows << history_->row(it);
  std::sort(rows.begin(), rows.end());
  QStringList texts;
  for (int r : rows) texts << history_->item(r)->text();
  // Remove from bottom so indices stay valid
  for (int i = rows.size() - 1; i >= 0; --i) delete history_->takeItem(rows[i]);
  if (edge < 0) {
    for (int i = texts.size() - 1; i >= 0; --i) {
      history_->insertItem(0, texts[i]);
      history_->item(0)->setSelected(true);
    }
    if (modeHint_) modeHint_->setText(QStringLiteral("报警已置顶 %1 · Ctrl+Home").arg(texts.size()));
  } else {
    for (const QString& tx : texts) {
      history_->addItem(tx);
      history_->item(history_->count() - 1)->setSelected(true);
    }
    if (modeHint_) modeHint_->setText(QStringLiteral("报警已置底 %1 · Ctrl+End").arg(texts.size()));
  }
  emit alarmHistoryChanged(alarmHistoryLines());
}


void HostStatePanel::selectAllAlarmHistory() {
  if (!history_ || history_->count() <= 0) {
    if (modeHint_) modeHint_->setText(QStringLiteral("报警空 · Ctrl+A"));
    return;
  }
  history_->selectAll();
  if (modeHint_)
    modeHint_->setText(QStringLiteral("已全选报警 %1 · Ctrl+A").arg(history_->count()));
}

void HostStatePanel::duplicateSelectedAlarmHistory() {
  if (!history_) return;
  const auto selected = history_->selectedItems();
  if (selected.isEmpty()) {
    if (modeHint_) modeHint_->setText(QStringLiteral("未选中 · Ctrl+D"));
    return;
  }
  QList<int> rows;
  for (auto* it : selected) rows << history_->row(it);
  std::sort(rows.begin(), rows.end());
  // Insert copies after each original, bottom-up to keep indices
  int added = 0;
  for (int i = rows.size() - 1; i >= 0; --i) {
    const int r = rows[i];
    auto* src = history_->item(r);
    if (!src) continue;
    history_->insertItem(r + 1, src->text());
    ++added;
  }
  // Cap at 40
  while (history_->count() > 40) delete history_->takeItem(history_->count() - 1);
  emit alarmHistoryChanged(alarmHistoryLines());
  if (modeHint_)
    modeHint_->setText(QStringLiteral("已复制报警 %1 · Ctrl+D").arg(added));
}

}  // namespace sieans_qt
