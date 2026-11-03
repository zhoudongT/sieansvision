#include "FlowTabBar.hpp"
#include "Theme.hpp"

#include <QHBoxLayout>
#include <QPushButton>
#include <QLabel>
#include <QEvent>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QClipboard>
#include <QGuiApplication>

namespace sieans_qt {

FlowTabBar::FlowTabBar(QWidget* parent) : QWidget(parent) {
  setFocusPolicy(Qt::StrongFocus);
  setObjectName(QStringLiteral("flowTabBar"));
  setStatusTip(QStringLiteral("流程条 · ▶一次 F5/F9 / ↻连续 F6 / ■停止 Esc · F/G/A/Space/R 适应 · 暂停/周期芯片 · 单击模式连续 · 右键模式暂停 · 中键模式适应 · 周期单击复制/Ctrl清零"));
  setFixedHeight(28);
  auto* lay = new QHBoxLayout(this);
  lay->setContentsMargins(4, 2, 4, 2);
  lay->setSpacing(2);
  allBtn_ = new QPushButton(QStringLiteral("全流程"));
  allBtn_->setCheckable(true);
  allBtn_->setFlat(true);
  allBtn_->setObjectName(QStringLiteral("flowTab"));
  flowBtn_ = new QPushButton(QStringLiteral("流程1"));
  flowBtn_->setCheckable(true);
  flowBtn_->setChecked(true);
  flowBtn_->setFlat(true);
  flowBtn_->setObjectName(QStringLiteral("flowTabActive"));
  auto* runOnce = new QPushButton(QStringLiteral("▶"));
  runOnce->setFixedWidth(28);
  runOnce->setToolTip(QStringLiteral("运行当前流程一次 · F5/F9 · 设计/运行态均可"));
  runOnce->setStatusTip(QStringLiteral("流程 · 运行一次"));
  auto* runCont = new QPushButton(QStringLiteral("↻"));
  runCont->setFixedWidth(28);
  runCont->setToolTip(QStringLiteral("连续运行当前流程 · F6 · Esc 停止"));
  runCont->setStatusTip(QStringLiteral("流程 · 连续运行"));
  pauseBtn_ = new QPushButton(QStringLiteral("Ⅱ"));
  pauseBtn_->setFixedWidth(28);
  pauseBtn_->setEnabled(false);
  pauseBtn_->setToolTip(QStringLiteral("暂停连续运行 · Space/Host 暂停 · 再次继续"));
  pauseBtn_->setStatusTip(QStringLiteral("流程 · 暂停"));
  pauseBtn_->setObjectName(QStringLiteral("flowPauseBtn"));
  auto* stop = new QPushButton(QStringLiteral("■"));
  stop->setFixedWidth(28);
  stop->setToolTip(QStringLiteral("停止运行 / 连续 · Esc · 单次运行中也可打断"));
  stop->setStatusTip(QStringLiteral("流程 · 停止"));
  auto* fit = new QPushButton(QStringLiteral("适应"));
  fit->setFixedWidth(40);
  fit->setToolTip(QStringLiteral("适应流程画布 · F/G/A/Space/Home/0/R · 含选中节点"));
  fit->setStatusTip(QStringLiteral("流程 · 适应画布"));
  auto* ioBtn = new QPushButton(QStringLiteral("I/O"));
  ioBtn->setFixedWidth(36);
  ioBtn->setToolTip(QStringLiteral("流程 I/O 绑定 · Ctrl+I · emptyDefault/{name}/${flow.x}/{{name}}"));
  ioBtn->setStatusTip(QStringLiteral("流程 · I/O 绑定"));
  ioBtn->setObjectName(QStringLiteral("flowIoBtn"));
  modeChip_ = new QLabel(QStringLiteral("设计"));
  modeChip_->setObjectName(QStringLiteral("flowModeChip"));
  modeChip_->setStyleSheet(
      QStringLiteral("QLabel{color:#c8ccd0;background:#2a2e32;border:1px solid #4a4e54;"
                     "border-radius:3px;padding:1px 6px;font-size:11px;}"));
  modeChip_->setToolTip(QStringLiteral("运行模式芯片 · 设计/单次/连续/暂停 · 单击连续 · Alt/右键暂停 · 中键适应"));
  modeChip_->setCursor(Qt::PointingHandCursor);
  modeChip_->installEventFilter(this);
  cycleLabel_ = new QLabel(QStringLiteral("周期 0"));
  cycleLabel_->setObjectName(QStringLiteral("flowCycleChip"));
  cycleLabel_->setStyleSheet(
      QStringLiteral("QLabel{color:#9ad0ff;background:#1e2830;border:1px solid #3a5060;"
                     "border-radius:3px;padding:1px 6px;font-size:11px;}"));
  cycleLabel_->setToolTip(QStringLiteral("流程条周期 · 节拍 · 滚轮±50 · Ctrl+滚轮±200 · Alt+1/2/3/4→50/100/200/500 · 单击复制 · Ctrl+单击/双击清零 · 右键清零"));
  cycleLabel_->setCursor(Qt::PointingHandCursor);
  cycleLabel_->setFocusPolicy(Qt::ClickFocus);
  cycleLabel_->installEventFilter(this);
  auto* hint = new QLabel(QStringLiteral("F5 一次 · F6 连续 · F/R 适应 · I/O 绑定 · Esc 取消连线 · Del 删连线"));
  hint->setObjectName(QStringLiteral("muted"));
  lay->addWidget(allBtn_);
  lay->addWidget(flowBtn_);
  lay->addSpacing(8);
  lay->addWidget(runOnce);
  lay->addWidget(runCont);
  lay->addWidget(pauseBtn_);
  lay->addWidget(stop);
  lay->addWidget(fit);
  lay->addWidget(ioBtn);
  lay->addSpacing(6);
  lay->addWidget(modeChip_);
  lay->addWidget(cycleLabel_);
  lay->addStretch(1);
  lay->addWidget(hint);
  connect(allBtn_, &QPushButton::clicked, this, &FlowTabBar::allFlowsRequested);
  connect(runOnce, &QPushButton::clicked, this, &FlowTabBar::runOnceRequested);
  connect(runCont, &QPushButton::clicked, this, &FlowTabBar::runContinuousRequested);
  connect(pauseBtn_, &QPushButton::clicked, this, &FlowTabBar::pauseRequested);
  connect(stop, &QPushButton::clicked, this, &FlowTabBar::stopRequested);
  connect(fit, &QPushButton::clicked, this, &FlowTabBar::fitRequested);
  connect(ioBtn, &QPushButton::clicked, this, &FlowTabBar::ioRequested);
  setStyleSheet(QStringLiteral(
      "QWidget#flowTabBar{background:#232528;border-bottom:1px solid #4a4e54;}"
      "QPushButton#flowTab,QPushButton#flowTabActive{border:0;padding:3px 10px;"
      "color:#a8a8a8;background:transparent;border-bottom:2px solid transparent;}"
      "QPushButton#flowTabActive{color:#e67a2e;font-weight:600;"
      "border-bottom:2px solid #e67a2e;}"));
}

void FlowTabBar::setFlowName(const QString& name) {
  flowBtn_->setText(name.isEmpty() ? QStringLiteral("流程1") : name);
}

void FlowTabBar::setRunChrome(const QString& mode, int cycle, double lastMs,
                              bool continuous, bool paused) {
  if (modeChip_) {
    modeChip_->setText(mode.isEmpty() ? QStringLiteral("设计") : mode);
    const QString bg = paused ? QStringLiteral("#4a3a18")
                       : continuous ? QStringLiteral("#1e3a28")
                       : QStringLiteral("#2a2e32");
    modeChip_->setStyleSheet(
        QStringLiteral("QLabel{color:#e8ecf0;background:%1;border:1px solid #4a4e54;"
                       "border-radius:3px;padding:1px 6px;font-size:11px;}")
            .arg(bg));
  }
  cycle_ = cycle;
  lastMs_ = lastMs;
  refreshCycleLabel();
  if (pauseBtn_) {
    pauseBtn_->setEnabled(continuous);
    pauseBtn_->setText(paused ? QStringLiteral("▶") : QStringLiteral("Ⅱ"));
    pauseBtn_->setToolTip(paused ? QStringLiteral("继续连续 · 流程条 ▶ / Host 继续")
                                 : QStringLiteral("暂停连续 · 流程条 Ⅱ / Host 暂停"));
  }
}

void FlowTabBar::setDesignLocked(bool locked) {
  if (allBtn_) allBtn_->setEnabled(!locked);
  if (flowBtn_) flowBtn_->setEnabled(!locked);
  // run/pause/stop/fit/io stay usable in 运行态 (VisionMaster HMI)
}


void FlowTabBar::setIntervalMs(int ms) {
  intervalMs_ = qBound(20, ms > 0 ? ms : 200, 60000);
  refreshCycleLabel();
}

void FlowTabBar::refreshCycleLabel() {
  if (!cycleLabel_) return;
  QString text;
  if (lastMs_ >= 0)
    text = QStringLiteral("周期 %1 · %2 ms").arg(cycle_).arg(lastMs_, 0, 'f', 1);
  else
    text = QStringLiteral("周期 %1").arg(cycle_);
  text += QStringLiteral(" · 节拍 %1").arg(intervalMs_);
  cycleLabel_->setText(text);
  cycleLabel_->setToolTip(
      QStringLiteral("周期 · 上次 ms · 节拍 %1 ms · 滚轮±50 · Ctrl+滚轮±200 · Alt+1/2/3/4→50/100/200/500 · 单击复制 · Ctrl+单击/双击清零")
          .arg(intervalMs_));
}

bool FlowTabBar::eventFilter(QObject* obj, QEvent* event) {
  if (event->type() == QEvent::Wheel && obj == cycleLabel_) {
    auto* we = static_cast<QWheelEvent*>(event);
    const int step = (we->modifiers() & Qt::ControlModifier) ? 200 : 50;
    const int delta = we->angleDelta().y() > 0 ? step : -step;
    const int next = qBound(20, intervalMs_ + delta, 60000);
    if (next != intervalMs_) {
      intervalMs_ = next;
      refreshCycleLabel();
      emit intervalChanged(intervalMs_);
    }
    return true;
  }
  if (event->type() == QEvent::MouseButtonDblClick) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton && obj == cycleLabel_) {
      emit cycleResetRequested();
      return true;
    }
  }
  if (event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (obj == modeChip_) {
      if (me->button() == Qt::LeftButton) {
        if (me->modifiers() & Qt::AltModifier) {
          emit pauseRequested();
          return true;
        }
        emit continuousToggleRequested();
        return true;
      }
      if (me->button() == Qt::RightButton) {
        emit pauseRequested();
        return true;
      }
      if (me->button() == Qt::MiddleButton) {
        emit fitRequested();
        return true;
      }
    }
    if (obj == cycleLabel_) {
      if (me->button() == Qt::RightButton ||
          (me->button() == Qt::LeftButton && (me->modifiers() & Qt::ControlModifier))) {
        emit cycleResetRequested();
        return true;
      }
      if (me->button() == Qt::LeftButton && cycleLabel_) {
        if (auto* clip = QGuiApplication::clipboard()) clip->setText(cycleLabel_->text());
        cycleLabel_->setToolTip(QStringLiteral("已复制周期 · 单击 · Ctrl+单击清零"));
        return true;
      }
    }
  }
  if (event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if ((ke->modifiers() & Qt::AltModifier) && ke->key() >= Qt::Key_1 && ke->key() <= Qt::Key_4 &&
        !(ke->modifiers() & Qt::ControlModifier)) {
      static const int kPresets[] = {50, 100, 200, 500};
      const int next = kPresets[ke->key() - Qt::Key_1];
      if (next != intervalMs_) {
        intervalMs_ = next;
        refreshCycleLabel();
        emit intervalChanged(intervalMs_);
      }
      if (cycleLabel_)
        cycleLabel_->setToolTip(
            QStringLiteral("节拍 %1 ms · Alt+%2").arg(next).arg(ke->key() - Qt::Key_0));
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) &&
        (ke->key() == Qt::Key_BracketLeft || ke->key() == Qt::Key_BracketRight ||
         ke->key() == Qt::Key_Up || ke->key() == Qt::Key_Down)) {
      const int step = (ke->modifiers() & Qt::ShiftModifier) ? 200 : 50;
      const int delta =
          (ke->key() == Qt::Key_BracketRight || ke->key() == Qt::Key_Up) ? step : -step;
      const int next = qBound(20, intervalMs_ + delta, 60000);
      if (next != intervalMs_) {
        intervalMs_ = next;
        refreshCycleLabel();
        emit intervalChanged(intervalMs_);
      }
      return true;
    }
  }
  return QWidget::eventFilter(obj, event);
}

void FlowTabBar::keyPressEvent(QKeyEvent* event) {
  if (event && eventFilter(this, event)) return;
  QWidget::keyPressEvent(event);
}

}  // namespace sieans_qt
