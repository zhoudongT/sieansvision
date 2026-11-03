#include "PropertyFloat.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QFrame>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QLineEdit>
#include <QVariantMap>

namespace sieans_qt {

PropertyFloat::PropertyFloat(QWidget* parent) : QDialog(parent) {
  setStatusTip(QStringLiteral("属性浮窗 · Esc/Ctrl+W 放弃 · Enter 保留 · Tab/Home/End/PgUp/PgDn/滚轮 · Ctrl/Alt/Shift+Enter 确定 · F5/F9 执行 · F6 连续"));
  setWhatsThis(QStringLiteral("属性浮窗 · Esc/Ctrl+W 放弃 · Enter 保留 · Tab/Home/End/PgUp/PgDn · Ctrl/Alt/Shift+Enter/Ctrl+S 确定 · F5/F9 单次 · F6 连续"));
  setObjectName(QStringLiteral("propertyFloat"));
  setWindowFlags(Qt::Tool | Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint);
  setModal(false);
  resize(460, 560);
  setStyleSheet(theme::propertyFloatStyleSheet());

  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(0, 0, 0, 0);
  root->setSpacing(0);

  titleBar_ = new QFrame;
  titleBar_->setObjectName(QStringLiteral("propertyFloatTitle"));
  auto* titleLay = new QHBoxLayout(titleBar_);
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
  closeBtn_ = new QPushButton(QStringLiteral("✕"));
  closeBtn_->setObjectName(QStringLiteral("propertyFloatClose"));
  closeBtn_->setFixedSize(28, 28);
  closeBtn_->setCursor(Qt::PointingHandCursor);
  closeBtn_->setFocusPolicy(Qt::NoFocus);
  closeBtn_->setToolTip(QStringLiteral("关闭并放弃本次修改"));
  connect(closeBtn_, &QPushButton::clicked, this, &PropertyFloat::revertAndHide);
  titleLay->addWidget(closeBtn_, 0, Qt::AlignTop);
  root->addWidget(titleBar_);

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
  cont->setToolTip(QStringLiteral("连续运行本模块 · 保持浮窗 · F6 · Esc 仍可放弃"));
  auto* exec = new QPushButton(QStringLiteral("执行"));
  exec->setObjectName(QStringLiteral("propertyFloatRun"));
  exec->setToolTip(QStringLiteral("单次运行本模块 · F5/F9 · 保留浮窗"));
  auto* cancel = new QPushButton(QStringLiteral("取消"));
  cancel->setObjectName(QStringLiteral("propertyFloatRun"));
  cancel->setToolTip(QStringLiteral("放弃修改并关闭 · Esc/Ctrl+W · 不写回属性"));
  auto* ok = new QPushButton(QStringLiteral("确定"));
  ok->setObjectName(QStringLiteral("propertyFloatOk"));
  ok->setToolTip(QStringLiteral("保留修改并关闭 · Ctrl/Alt/Shift+Enter · Ctrl+S · Esc 相反"));
  auto* hint = new QLabel(QStringLiteral("Esc/Ctrl+W 放弃 · Enter 保留 · Tab/Home/End/PgUp/PgDn 切换 · Ctrl+S/Ctrl+Enter 确定 · F5/F9 执行 · F6 连续"));
  hint->setObjectName(QStringLiteral("propertyFloatHint"));
  hint->setStyleSheet(QStringLiteral("color:#8a9098;font-size:11px;"));
  foot->addWidget(cont);
  foot->addWidget(exec);
  foot->addWidget(hint, 1);
  foot->addWidget(cancel);
  foot->addWidget(ok);
  root->addWidget(footer);

  connect(cont, &QPushButton::clicked, this, &PropertyFloat::runModuleContinuous);
  connect(exec, &QPushButton::clicked, this, &PropertyFloat::runModule);
  connect(cancel, &QPushButton::clicked, this, &PropertyFloat::revertAndHide);
  connect(ok, &QPushButton::clicked, this, [this]() {
    if (panel_) baseline_ = panel_->currentParams();
    emit acceptedCommit();
    hide();
  });
}

void PropertyFloat::revertAndHide() {
  emit paramsReverted(nodeId_, baseline_);
  hide();
}

void PropertyFloat::mousePressEvent(QMouseEvent* event) {
  if (event->button() == Qt::LeftButton && titleBar_ &&
      titleBar_->geometry().contains(event->position().toPoint())) {
    const QPoint local = titleBar_->mapFrom(this, event->position().toPoint());
    if (closeBtn_ && closeBtn_->geometry().contains(local)) {
      revertAndHide();
      event->accept();
      return;
    }
    dragging_ = true;
    dragOffset_ = event->globalPosition().toPoint() - frameGeometry().topLeft();
    event->accept();
    return;
  }
  QDialog::mousePressEvent(event);
}

void PropertyFloat::mouseMoveEvent(QMouseEvent* event) {
  if (dragging_ && (event->buttons() & Qt::LeftButton)) {
    move(event->globalPosition().toPoint() - dragOffset_);
    event->accept();
    return;
  }
  QDialog::mouseMoveEvent(event);
}

void PropertyFloat::mouseReleaseEvent(QMouseEvent* event) {
  dragging_ = false;
  QDialog::mouseReleaseEvent(event);
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
  baseline_ = QVariantMap(sourceConfig);  // deep-ish snapshot for ✕/Esc
  setNodeTitle(QStringLiteral("属性 · 图像源"), QStringLiteral("sourceConfig"));
  panel_->showSource(sourceConfig);
  show();
  raise();
  activateWindow();
  if (QLineEdit* le = findChild<QLineEdit*>()) {
    le->setFocus(Qt::OtherFocusReason);
    le->selectAll();
  }
}

void PropertyFloat::showForStep(const FlowStep& step) {
  nodeId_ = step.id;
  baseline_ = QVariantMap(step.params);
  setNodeTitle(QStringLiteral("属性 · %1").arg(step.name),
               QStringLiteral("%1 · %2 · %3")
                   .arg(step.operation, step.runState, step.id.left(8)));
  panel_->showStep(step);
  show();
  raise();
  activateWindow();
  if (QLineEdit* le = findChild<QLineEdit*>()) {
    le->setFocus(Qt::OtherFocusReason);
    le->selectAll();
  }
}

void PropertyFloat::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_S && (event->modifiers() & Qt::ControlModifier)) {
    if (panel_) baseline_ = panel_->currentParams();
    emit acceptedCommit();
    hide();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Escape ||
      (event->key() == Qt::Key_W && (event->modifiers() & Qt::ControlModifier))) {
    revertAndHide();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Tab ||
      (event->key() == Qt::Key_Backtab) ||
      (event->key() == Qt::Key_Tab && event->modifiers() & Qt::ShiftModifier)) {
    // Cycle editable line edits inside the float (VM property sheet feel).
    focusNextPrevChild(!(event->key() == Qt::Key_Backtab ||
                         (event->modifiers() & Qt::ShiftModifier)));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Home || event->key() == Qt::Key_End ||
      event->key() == Qt::Key_PageUp || event->key() == Qt::Key_PageDown) {
    // Jump to first/last focusable child in the float (PgUp≈Home / PgDn≈End).
    QWidget* first = nullptr;
    QWidget* last = nullptr;
    const auto kids = findChildren<QWidget*>();
    for (QWidget* w : kids) {
      if (!w->isVisible() || !w->isEnabled() || w->focusPolicy() == Qt::NoFocus)
        continue;
      if (!first) first = w;
      last = w;
    }
    const bool toFirst = event->key() == Qt::Key_Home || event->key() == Qt::Key_PageUp;
    QWidget* target = toFirst ? first : last;
    if (target) {
      target->setFocus(Qt::ShortcutFocusReason);
      event->accept();
      return;
    }
  }
  if (event->key() == Qt::Key_F5 || event->key() == Qt::Key_F9) {
    emit runModule();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F6) {
    emit runModuleContinuous();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter) {
    // Enter: keep float open (edits already flushed via editingFinished).
    // Ctrl+Enter: commit baseline + hide (VM-ish apply).
    if ((event->modifiers() & Qt::ControlModifier) ||
        (event->modifiers() & Qt::AltModifier) ||
        (event->modifiers() & Qt::ShiftModifier)) {
      if (panel_) baseline_ = panel_->currentParams();
      emit acceptedCommit();
      hide();
    }
    event->accept();
    return;
  }
  QDialog::keyPressEvent(event);
}

}  // namespace sieans_qt
