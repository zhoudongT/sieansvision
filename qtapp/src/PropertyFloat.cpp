#include "PropertyFloat.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QFrame>
#include <QMouseEvent>

namespace sieans_qt {

PropertyFloat::PropertyFloat(QWidget* parent) : QDialog(parent) {
  setObjectName(QStringLiteral("propertyFloat"));
  setWindowFlags(Qt::Tool | Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint);
  setModal(false);
  resize(460, 560);
  setStyleSheet(theme::propertyFloatStyleSheet());

  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(0, 0, 0, 0);
  root->setSpacing(0);

  auto* titleBar = new QFrame;
  titleBar->setObjectName(QStringLiteral("propertyFloatTitle"));
  auto* titleLay = new QHBoxLayout(titleBar);
  titleLay->setContentsMargins(12, 6, 6, 6);
  auto* titleCol = new QVBoxLayout;
  titleCol->setContentsMargins(0, 0, 0, 0);
  titleCol->setSpacing(0);
  title_ = new QLabel(QStringLiteral("属性"));
  title_->setObjectName(QStringLiteral("propertyFloatTitleLabel"));
  subtitle_ = new QLabel;
  subtitle_->setObjectName(QStringLiteral("propertyFloatSubtitle"));
  subtitle_->setVisible(false);
  titleCol->addWidget(title_);
  titleCol->addWidget(subtitle_);
  titleLay->addLayout(titleCol, 1);
  auto* closeBtn = new QPushButton(QStringLiteral("✕"));
  closeBtn->setObjectName(QStringLiteral("propertyFloatClose"));
  closeBtn->setFixedSize(28, 28);
  closeBtn->setCursor(Qt::PointingHandCursor);
  closeBtn->setFocusPolicy(Qt::NoFocus);
  connect(closeBtn, &QPushButton::clicked, this, &QWidget::hide);
  titleLay->addWidget(closeBtn, 0, Qt::AlignTop);
  root->addWidget(titleBar);

  auto* body = new QWidget;
  body->setObjectName(QStringLiteral("propertyFloatBody"));
  auto* bodyLay = new QVBoxLayout(body);
  bodyLay->setContentsMargins(0, 0, 0, 0);
  panel_ = new PropertyPanel;
  bodyLay->addWidget(panel_, 1);
  root->addWidget(body, 1);
  connect(panel_, &PropertyPanel::paramEdited, this, &PropertyFloat::paramEdited);

  auto* footer = new QFrame;
  footer->setObjectName(QStringLiteral("propertyFloatFooter"));
  auto* foot = new QHBoxLayout(footer);
  foot->setContentsMargins(10, 6, 10, 8);
  auto* cont = new QPushButton(QStringLiteral("连续执行"));
  cont->setObjectName(QStringLiteral("propertyFloatRunContinuous"));
  auto* exec = new QPushButton(QStringLiteral("执行"));
  exec->setObjectName(QStringLiteral("propertyFloatRun"));
  auto* ok = new QPushButton(QStringLiteral("确定"));
  ok->setObjectName(QStringLiteral("propertyFloatOk"));
  foot->addWidget(cont);
  foot->addWidget(exec);
  foot->addStretch(1);
  foot->addWidget(ok);
  root->addWidget(footer);

  connect(cont, &QPushButton::clicked, this, &PropertyFloat::runModuleContinuous);
  connect(exec, &QPushButton::clicked, this, &PropertyFloat::runModule);
  connect(ok, &QPushButton::clicked, this, [this]() {
    emit acceptedCommit();
    hide();
  });
}

void PropertyFloat::setNodeTitle(const QString& title, const QString& subtitle) {
  title_->setText(title);
  if (subtitle.isEmpty()) {
    subtitle_->clear();
    subtitle_->setVisible(false);
  } else {
    subtitle_->setText(subtitle);
    subtitle_->setVisible(true);
  }
}

void PropertyFloat::showForSource(const QVariantMap& sourceConfig) {
  nodeId_ = QStringLiteral("source");
  setNodeTitle(QStringLiteral("属性 · 图像源"), QStringLiteral("sourceConfig"));
  panel_->showSource(sourceConfig);
  show();
  raise();
  activateWindow();
}

void PropertyFloat::showForStep(const FlowStep& step) {
  nodeId_ = step.id;
  setNodeTitle(QStringLiteral("属性 · %1").arg(step.name),
               QStringLiteral("%1 · %2").arg(step.operation, step.runState));
  panel_->showStep(step);
  show();
  raise();
  activateWindow();
}

}  // namespace sieans_qt
