#include "FlowTabBar.hpp"
#include "Theme.hpp"

#include <QHBoxLayout>
#include <QPushButton>
#include <QLabel>

namespace sieans_qt {

FlowTabBar::FlowTabBar(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("flowTabBar"));
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
  runOnce->setToolTip(QStringLiteral("运行当前流程一次"));
  auto* runCont = new QPushButton(QStringLiteral("↻"));
  runCont->setFixedWidth(28);
  runCont->setToolTip(QStringLiteral("连续运行当前流程"));
  auto* hint = new QLabel(QStringLiteral("自动排列 · 适应 · 撤销 · 重做"));
  hint->setObjectName(QStringLiteral("muted"));
  lay->addWidget(allBtn_);
  lay->addWidget(flowBtn_);
  lay->addSpacing(8);
  lay->addWidget(runOnce);
  lay->addWidget(runCont);
  lay->addStretch(1);
  lay->addWidget(hint);
  connect(allBtn_, &QPushButton::clicked, this, &FlowTabBar::allFlowsRequested);
  connect(runOnce, &QPushButton::clicked, this, &FlowTabBar::runOnceRequested);
  connect(runCont, &QPushButton::clicked, this, &FlowTabBar::runContinuousRequested);
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

}  // namespace sieans_qt
