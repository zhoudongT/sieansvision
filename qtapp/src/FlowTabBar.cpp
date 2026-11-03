#include "FlowTabBar.hpp"
#include "Theme.hpp"

#include <QHBoxLayout>
#include <QPushButton>
#include <QLabel>

namespace sieans_qt {

FlowTabBar::FlowTabBar(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("flowTabBar"));
  setStatusTip(QStringLiteral("流程条 · ▶一次 F5/F9 / ↻连续 F6 / ■停止 Esc · F/G/A/Space/R 适应 · 暂停/周期芯片"));
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
  modeChip_->setToolTip(QStringLiteral("运行模式芯片 · 设计/单次/连续/暂停"));
  cycleLabel_ = new QLabel(QStringLiteral("周期 0"));
  cycleLabel_->setObjectName(QStringLiteral("flowCycleChip"));
  cycleLabel_->setStyleSheet(
      QStringLiteral("QLabel{color:#9ad0ff;background:#1e2830;border:1px solid #3a5060;"
                     "border-radius:3px;padding:1px 6px;font-size:11px;}"));
  cycleLabel_->setToolTip(QStringLiteral("流程条周期 · 与 HostStrip 同步"));
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
  if (cycleLabel_) {
    if (lastMs >= 0)
      cycleLabel_->setText(QStringLiteral("周期 %1 · %2 ms").arg(cycle).arg(lastMs, 0, 'f', 1));
    else
      cycleLabel_->setText(QStringLiteral("周期 %1").arg(cycle));
  }
  if (pauseBtn_) {
    pauseBtn_->setEnabled(continuous && !paused);
    pauseBtn_->setText(paused ? QStringLiteral("▶") : QStringLiteral("Ⅱ"));
    pauseBtn_->setToolTip(paused ? QStringLiteral("已暂停 · Host 继续 / F6 重入")
                                 : QStringLiteral("暂停连续运行 · Space/Host 暂停 · 再次继续"));
  }
}

void FlowTabBar::setDesignLocked(bool locked) {
  if (allBtn_) allBtn_->setEnabled(!locked);
  if (flowBtn_) flowBtn_->setEnabled(!locked);
  // run/pause/stop/fit/io stay usable in 运行态 (VisionMaster HMI)
}

}  // namespace sieans_qt
