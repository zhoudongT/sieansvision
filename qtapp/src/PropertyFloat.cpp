#include "PropertyFloat.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QFrame>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QWheelEvent>
#include <QLineEdit>
#include <QVariantMap>
#include <QtGlobal>
#include <QClipboard>
#include <QGuiApplication>

namespace sieans_qt {

PropertyFloat::PropertyFloat(QWidget* parent) : QDialog(parent) {
  setStatusTip(QStringLiteral("属性浮窗 · Esc/Ctrl+W 放弃 · Enter 保留 · F2 首字段 · Tab/Home/End/PgUp/PgDn/滚轮 · Alt+滚轮透明度 · Ctrl+0 透明度重置 · Ctrl+[ / ] 宽度 · Ctrl+Shift+[ / ] 高度 · Ctrl+Shift+0 复位尺寸 · Ctrl+R 还原 · Ctrl+Shift+C 复制可见 · 双击/中键标题钉住 · 右键标题复制节点 · Ctrl/Alt/Shift+Enter 确定 · F5/F9 执行 · F6 连续 · Ctrl+S 确定 · Ctrl+Shift+S 应用保持 · F4 末字段 · Alt+1/2/3 透明度 · Ctrl+Shift+方向吸附"));
  setWhatsThis(QStringLiteral("属性浮窗 · Esc/Ctrl+W 放弃 · Enter 保留 · Tab/Home/End/PgUp/PgDn · Ctrl/Alt/Shift+Enter/Ctrl+S 确定 · F5/F9 单次 · F6 连续"));
  setObjectName(QStringLiteral("propertyFloat"));
  setWindowFlags(Qt::Tool | Qt::FramelessWindowHint);
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
  pinBtn_ = new QPushButton(QStringLiteral("📌"));
  pinBtn_->setObjectName(QStringLiteral("propertyFloatPin"));
  pinBtn_->setFixedSize(28, 28);
  pinBtn_->setCheckable(true);
  pinBtn_->setCursor(Qt::PointingHandCursor);
  pinBtn_->setFocusPolicy(Qt::NoFocus);
  pinBtn_->setToolTip(QStringLiteral("钉住浮窗置顶 · Ctrl+P · 中键/双击标题"));
  titleLay->addWidget(pinBtn_, 0, Qt::AlignTop);
  connect(pinBtn_, &QPushButton::toggled, this, [this](bool on) {
    pinned_ = on;
    if (on) pinnedGeom_ = geometry();
    setWindowFlag(Qt::WindowStaysOnTopHint, on);
    // re-show to apply flag
    const bool vis = isVisible();
    if (vis) {
      hide();
      show();
      if (on && pinnedGeom_.isValid()) setGeometry(pinnedGeom_);
    }
    pinBtn_->setText(on ? QStringLiteral("📍") : QStringLiteral("📌"));
    pinBtn_->setToolTip(on ? QStringLiteral("取消钉住 · Ctrl+P") : QStringLiteral("钉住浮窗 · 置顶 · Ctrl+P"));
  });
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
  ok->setToolTip(QStringLiteral("保留修改并关闭 · Ctrl/Alt/Shift+Enter · Ctrl+S · Ctrl+Shift+S 应用保持 · Esc 相反"));
  auto* hint = new QLabel(QStringLiteral("Esc/Ctrl+W 放弃 · Enter 保留 · Tab/Home/End/PgUp/PgDn 切换 · Ctrl+R 还原 · Alt+滚轮透明度 · Ctrl+S 确定 · Ctrl+Shift+S 应用保持 · Ctrl+Enter 确定 · F5/F9 · F6"));
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
  if (titleBar_ && titleBar_->geometry().contains(event->position().toPoint())) {
    if (event->button() == Qt::MiddleButton) {
      if (pinBtn_) pinBtn_->toggle();
      event->accept();
      return;
    }
    if (event->button() == Qt::RightButton) {
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(nodeId_.isEmpty() ? title_->text() : nodeId_);
        if (subtitle_) subtitle_->setText(QStringLiteral("已复制节点 · 右键标题"));
      }
      event->accept();
      return;
    }
  }
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
  if (pinned_) {
    setWindowFlag(Qt::WindowStaysOnTopHint, true);
    show();
  }
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
  if (pinned_) {
    setWindowFlag(Qt::WindowStaysOnTopHint, true);
    show();
  }
  if (QLineEdit* le = findChild<QLineEdit*>()) {
    le->setFocus(Qt::OtherFocusReason);
    le->selectAll();
  }
}

void PropertyFloat::mouseDoubleClickEvent(QMouseEvent* event) {
  if (event->button() == Qt::LeftButton && titleBar_ &&
      titleBar_->geometry().contains(event->position().toPoint())) {
    if (pinBtn_) pinBtn_->toggle();
    event->accept();
    return;
  }
  QDialog::mouseDoubleClickEvent(event);
}

void PropertyFloat::keyPressEvent(QKeyEvent* event) {
  if (event->key() == Qt::Key_R && (event->modifiers() & Qt::ControlModifier)) {
    // Restore baseline into editors without closing (VM-ish revert).
    if (panel_) panel_->applySnapshot(baseline_);
    emit paramsReverted(nodeId_, baseline_);
    if (subtitle_) {
      const QString s = subtitle_->text();
      if (!s.contains(QStringLiteral("已还原")))
        subtitle_->setText(s + QStringLiteral(" · 已还原"));
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_BracketLeft && (event->modifiers() & Qt::ControlModifier)) {
    if (event->modifiers() & Qt::ShiftModifier) {
      resize(width(), qMax(280, height() - 40));
      if (subtitle_) subtitle_->setText(QStringLiteral("高度 %1 · Ctrl+Shift+[").arg(height()));
      event->accept();
      return;
    }
    resize(qMax(280, width() - 40), height());
    if (subtitle_) subtitle_->setText(QStringLiteral("宽度 %1 · Ctrl+[").arg(width()));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_BracketRight && (event->modifiers() & Qt::ControlModifier)) {
    if (event->modifiers() & Qt::ShiftModifier) {
      resize(width(), qMin(900, height() + 40));
      if (subtitle_) subtitle_->setText(QStringLiteral("高度 %1 · Ctrl+Shift+]").arg(height()));
      event->accept();
      return;
    }
    resize(qMin(720, width() + 40), height());
    if (subtitle_) subtitle_->setText(QStringLiteral("宽度 %1 · Ctrl+]").arg(width()));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_0 && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    resize(460, 560);
    opacity_ = 1.0;
    setWindowOpacity(opacity_);
    if (subtitle_) subtitle_->setText(QStringLiteral("尺寸已复位 · Ctrl+Shift+0"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_0 && (event->modifiers() & Qt::ControlModifier)) {
    opacity_ = 1.0;
    setWindowOpacity(opacity_);
    if (subtitle_) {
      const QString s = subtitle_->text();
      if (!s.contains(QStringLiteral("透明度")))
        subtitle_->setText(s + QStringLiteral(" · 透明度 100%"));
    }
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_S && (event->modifiers() & Qt::ControlModifier)) {
    if (panel_) baseline_ = panel_->currentParams();
    emit acceptedCommit();
    if (event->modifiers() & Qt::ShiftModifier) {
      if (subtitle_) subtitle_->setText(QStringLiteral("已应用 · 保持浮窗 · Ctrl+Shift+S"));
      event->accept();
      return;
    }
    hide();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_P && (event->modifiers() & Qt::ControlModifier)) {
    if (pinBtn_) pinBtn_->toggle();
    event->accept();
    return;
  }
  if ((event->key() == Qt::Key_F && (event->modifiers() & Qt::ControlModifier)) ||
      event->key() == Qt::Key_F3) {
    if (panel_) panel_->focusFilter();
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_C && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    if (panel_) panel_->copyVisibleParams();
    if (subtitle_) subtitle_->setText(QStringLiteral("已复制可见参数 · Ctrl+Shift+C"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_V && (event->modifiers() & Qt::ControlModifier) &&
      (event->modifiers() & Qt::ShiftModifier)) {
    if (panel_) panel_->pasteKeyValueParams();
    if (subtitle_) subtitle_->setText(QStringLiteral("已粘贴参数 · Ctrl+Shift+V"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F4) {
    const auto kids = findChildren<QWidget*>();
    QWidget* last = nullptr;
    for (QWidget* w : kids) {
      if (!w->isVisible() || !w->isEnabled() || w->focusPolicy() == Qt::NoFocus)
        continue;
      if (w == this || w == titleBar_ || w == closeBtn_ || w == pinBtn_ || w == title_ || w == subtitle_)
        continue;
      last = w;
    }
    if (last) {
      last->setFocus(Qt::ShortcutFocusReason);
      if (subtitle_) subtitle_->setText(QStringLiteral("末字段 · F4"));
    }
    event->accept();
    return;
  }
  if ((event->modifiers() & Qt::AltModifier) &&
      (event->key() == Qt::Key_1 || event->key() == Qt::Key_2 || event->key() == Qt::Key_3)) {
    if (event->key() == Qt::Key_1) opacity_ = 1.0;
    else if (event->key() == Qt::Key_2) opacity_ = 0.85;
    else opacity_ = 0.7;
    setWindowOpacity(opacity_);
    if (subtitle_)
      subtitle_->setText(QStringLiteral("透明度 %1% · Alt+%2")
                             .arg(int(opacity_ * 100))
                             .arg(event->key() - Qt::Key_0));
    event->accept();
    return;
  }
  if ((event->modifiers() & Qt::ControlModifier) && (event->modifiers() & Qt::ShiftModifier) &&
      (event->key() == Qt::Key_Left || event->key() == Qt::Key_Right ||
       event->key() == Qt::Key_Up || event->key() == Qt::Key_Down)) {
    QWidget* host = parentWidget() ? parentWidget()->window() : nullptr;
    const QRect area = host ? host->geometry() : screen()->availableGeometry();
    QRect g = geometry();
    if (event->key() == Qt::Key_Left) g.moveLeft(area.left() + 8);
    else if (event->key() == Qt::Key_Right) g.moveRight(area.right() - 8);
    else if (event->key() == Qt::Key_Up) g.moveTop(area.top() + 8);
    else g.moveBottom(area.bottom() - 8);
    setGeometry(g);
    if (subtitle_) subtitle_->setText(QStringLiteral("已吸附 · Ctrl+Shift+方向"));
    event->accept();
    return;
  }
  if (event->key() == Qt::Key_F2) {
    // Focus first editable field in the float (VM-ish).
    const auto kids = findChildren<QWidget*>();
    for (QWidget* w : kids) {
      if (!w->isVisible() || !w->isEnabled() || w->focusPolicy() == Qt::NoFocus)
        continue;
      if (w == this || w == titleBar_ || w == closeBtn_ || w == pinBtn_ || w == title_ || w == subtitle_)
        continue;
      w->setFocus(Qt::ShortcutFocusReason);
      event->accept();
      return;
    }
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


void PropertyFloat::wheelEvent(QWheelEvent* event) {
  // Scroll wheel cycles focus among editable fields (VM-ish).
  // Alt+wheel adjusts float opacity (VM chrome depth).
  if (!event) return;
  if (event->modifiers() & Qt::AltModifier) {
    const qreal delta = event->angleDelta().y() > 0 ? 0.05 : -0.05;
    opacity_ = qBound(0.45, opacity_ + delta, 1.0);
    setWindowOpacity(opacity_);
    if (subtitle_)
      subtitle_->setText(QStringLiteral("透明度 %1% · Ctrl+0 重置")
                             .arg(int(opacity_ * 100 + 0.5)));
    event->accept();
    return;
  }
  const bool next = event->angleDelta().y() < 0 || event->angleDelta().x() < 0;
  focusNextPrevChild(next);
  event->accept();
}

}  // namespace sieans_qt
