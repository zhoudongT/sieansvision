#include "HostStrip.hpp"
#include <QInputDialog>
#include <QLineEdit>
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QCursor>
#include <QGuiApplication>
#include <QRegularExpression>
#include <QClipboard>
#include <QApplication>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QEvent>
#include <algorithm>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMenu>
#include <QAction>
#include <QKeySequence>
#include "VarWatchPanel.hpp"

namespace sieans_qt {

HostStrip::HostStrip(QWidget* parent) : QWidget(parent) {
  setFocusPolicy(Qt::StrongFocus);
  setStatusTip(QStringLiteral("Host 条 · OK/NG/ALARM · tcp= 摘要(lf/crlf/raw/len4) · Esc 停止 · Space 开始/暂停 · F5/F9 单次 · F6 连续 · F7 暂停 · 周期 chip 见右侧 · 单击模式切换 · 右键连续 · Ctrl+单击周期清零 · 双击明细复制 · Ctrl+Shift+V 粘贴监视键 · Ctrl+Shift+P 粘贴 Host 配置 · 周期中键良率 · 周期 ms"));
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(8, 4, 8, 4);
  root->setSpacing(2);
  auto* row = new QHBoxLayout;
  row->setSpacing(8);
  badge_ = new QLabel(QStringLiteral("—"));
  badge_->setFixedWidth(72);
  badge_->setAlignment(Qt::AlignCenter);
  badge_->setToolTip(QStringLiteral("OK/NG/ALARM · passGate 判定 · tcp= 见明细"));
  badge_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "font-weight:700;font-size:14px;padding:4px;"));
  modeChip_ = new QLabel(QStringLiteral("设计态"));
  modeChip_->setToolTip(QStringLiteral("运行模式 · 单击/F8 设计/运行 · Shift+F8 连续 · 设计态/运行/连续/暂停 · 运行态锁画布 · F5/F9 仍可单次"));
  modeChip_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "padding:3px 8px;font-size:11px;font-weight:600;"));
  cycleChip_ = new QLabel(QStringLiteral("周期 0"));
  cycleChip_->setToolTip(QStringLiteral("运行周期计数 · 每次流程完成 +1 · 滚轮调节拍 · Ctrl+Shift+T 复制 · Ctrl+Shift+I 粘贴节拍 · 中键良率 · 右键清连OK"));
  cycleChip_->setStyleSheet(
      QStringLiteral("background:#32353a;color:#a8a8a8;border-radius:3px;"
                     "padding:3px 8px;font-size:11px;"));
  detail_ = new QLabel(QStringLiteral("Host · 等待运行"));
  detail_->setObjectName(QStringLiteral("muted"));
  detail_->setToolTip(QStringLiteral("count/text/RX/urlOk/tcp 摘要 · framing lf/crlf/raw/len4 见 tcp= · 悬停看全文"));
  alarmLabel_ = new QLabel;
  alarmLabel_->setVisible(false);
  alarmLabel_->setToolTip(QStringLiteral("报警锁存 · Host 清报警解除 · 不影响周期计数"));
  alarmLabel_->setStyleSheet(
      QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                     "font-weight:700;padding:2px 8px;"));
  lockChip_ = new QLabel(QStringLiteral("锁"));
  lockChip_->setVisible(false);
  lockChip_->setStyleSheet(
      QStringLiteral("background:#e67a2e;color:#fff;border-radius:3px;"
                     "padding:3px 8px;font-size:11px;font-weight:700;"));
  lockChip_->setToolTip(QStringLiteral("配方锁 · 运行态 · 单击切换设计/运行"));
  lockChip_->setCursor(Qt::PointingHandCursor);
  row->addWidget(badge_);
  row->addWidget(modeChip_);
  row->addWidget(lockChip_);
  row->addWidget(cycleChip_);
  row->addWidget(detail_, 1);
  row->addWidget(alarmLabel_);
  root->addLayout(row);
  badge_->setCursor(Qt::PointingHandCursor);
  modeChip_->setCursor(Qt::PointingHandCursor);
  cycleChip_->setCursor(Qt::PointingHandCursor);
  cycleChip_->setFocusPolicy(Qt::ClickFocus);
  detail_->setCursor(Qt::PointingHandCursor);
  badge_->setToolTip(QStringLiteral("OK/NG/ALARM · passGate 判定 · 单击打开 Host 面板 · F8 设计/运行 · Alt+单击清连OK/NG · 中键复制运行统计 · tcp= 见明细"));
  modeChip_->setToolTip(QStringLiteral("运行模式 · 单击/F8 设计/运行 · Shift+F8/右键/中键连续 · Alt 暂停/继续"));
  cycleChip_->setToolTip(QStringLiteral("周期 · 上次 ms · 节拍 · 滚轮±50 · Ctrl+滚轮±200 · Alt+1/2/3/4→50/100/200/500 · Ctrl+单击/双击清零 · 右键/Alt+单击/Ctrl+Shift+0 清连OK · 中键良率"));
  detail_->setToolTip(QStringLiteral("count/text/RX/urlOk/tcp/良率 摘要 · framing lf/crlf/raw/len4 见 tcp= · 双击复制全文 · 中键复制连OK/NG · 右键/Ctrl+Shift+C 运行统计 · 悬停看全文"));
  badge_->installEventFilter(this);
  modeChip_->installEventFilter(this);
  if (lockChip_) lockChip_->installEventFilter(this);
  cycleChip_->installEventFilter(this);
  detail_->installEventFilter(this);
  auto* chipRow = new QHBoxLayout;
  chipRow->setSpacing(6);
  pinGroupChip_ = new QLabel;
  pinGroupChip_->setObjectName(QStringLiteral("hostPinGroupChip"));
  pinGroupChip_->setVisible(false);
  pinGroupChip_->setCursor(Qt::PointingHandCursor);
  pinGroupChip_->setStyleSheet(
      QStringLiteral("background:#2a3340;color:#8ec8ff;border-radius:3px;"
                     "padding:2px 8px;font-size:11px;font-weight:600;"));
  pinGroupChip_->setToolTip(
      QStringLiteral("钉组 · 单击打开变量监视 · 右键选组 · 数字键 1–9 加速 · 无硬件"));
  pinGroupChip_->installEventFilter(this);
  chipRow->addWidget(pinGroupChip_, 0);
  chips_ = new QLabel;
  chips_->setObjectName(QStringLiteral("muted"));
  chips_->setWordWrap(true);
  chips_->setCursor(Qt::PointingHandCursor);
  chips_->setToolTip(QStringLiteral("监视变量芯片 · 双击编辑 · Ctrl+Shift+K/V 复制/粘贴键(JSON) · Ctrl+Shift+E JSON导出 · Alt+←→ 调序 · Ctrl+Home/End 置顶末/置底首 · Ctrl+Shift+Y 反序 · Ctrl+Shift+S 排序 · Ctrl+Shift+U 去重 · Del/Bksp 删首 · Shift+Del 删末 · Ctrl+Shift+Bksp 清空 · 单击复制全文"));
  chips_->installEventFilter(this);
  chipRow->addWidget(chips_, 1);
  root->addLayout(chipRow);
  setStyleSheet(QStringLiteral("background:#232528;border-top:1px solid #4a4e54;"));
  setMinimumHeight(52);
}

void HostStrip::setWatchKeys(const QStringList& keys) { watchKeys_ = keys; }

void HostStrip::setAlarm(bool on, const QString& reason) {
  alarmOn_ = on;
  if (on) lastResult_ = QStringLiteral("ALARM");
  alarmReason_ = reason;
  refreshAlarmLockChrome();
}

void HostStrip::setRecipeLocked(bool locked) {
  recipeLocked_ = locked;
  if (lockChip_) {
    lockChip_->setVisible(locked);
    lockChip_->setText(locked ? QStringLiteral("锁") : QString());
  }
  refreshAlarmLockChrome();
}

void HostStrip::refreshAlarmLockChrome() {
  if (!alarmLabel_) return;
  alarmLabel_->setVisible(alarmOn_);
  if (!alarmOn_) {
    alarmLabel_->setText({});
    alarmLabel_->setStyleSheet(
        QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                       "font-weight:700;padding:2px 8px;"));
    return;
  }
  QString text = QStringLiteral("ALARM");
  if (recipeLocked_) text += QStringLiteral(" · 锁");
  if (!alarmReason_.isEmpty())
    text += QStringLiteral(" %1").arg(alarmReason_.left(28));
  alarmLabel_->setText(text);
  // Locked+alarm: amber-red to show co-bind without new tip spam.
  alarmLabel_->setStyleSheet(
      recipeLocked_
          ? QStringLiteral("background:#b71c1c;color:#ffe082;border-radius:3px;"
                           "font-weight:700;padding:2px 8px;"
                           "border:1px solid #e67a2e;")
          : QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                           "font-weight:700;padding:2px 8px;"));
  alarmLabel_->setToolTip(
      recipeLocked_
          ? QStringLiteral("报警锁存 · 配方锁开 · Host 清报警 / F8 解锁")
          : QStringLiteral("报警锁存 · Host 清报警解除"));
}

void HostStrip::setRunChrome(const QString& mode, const QString& hostState, int cycle) {
  cycle_ = cycle;
  hostState_ = hostState.isEmpty() ? QStringLiteral("Idle") : hostState;
  continuous_ = mode.contains(QStringLiteral("连续")) || mode.contains(QStringLiteral("暂停"));
  const bool run = mode.contains(QStringLiteral("运行")) || mode.contains(QStringLiteral("连续")) ||
                   mode.contains(QStringLiteral("暂停"));
  modeChip_->setText(QStringLiteral("%1 · %2").arg(mode, hostState_));
  modeChip_->setStyleSheet(
      run ? QStringLiteral("background:#1e3d2f;color:#3ecf8e;border-radius:3px;"
                           "padding:3px 8px;font-size:11px;font-weight:600;")
          : QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                           "padding:3px 8px;font-size:11px;font-weight:600;"));
  refreshCycleChip();
}

void HostStrip::setCycleTiming(double lastMs) {
  lastCycleMs_ = lastMs;
  refreshCycleChip();
}

void HostStrip::setIntervalMs(int ms) {
  intervalMs_ = qBound(20, ms > 0 ? ms : 200, 60000);
  refreshCycleChip();
}

void HostStrip::refreshCycleChip() {
  if (!cycleChip_) return;
  QString text;
  if (lastCycleMs_ >= 0)
    text = QStringLiteral("周期 %1 · %2 ms").arg(cycle_).arg(lastCycleMs_, 0, 'f', 1);
  else
    text = QStringLiteral("周期 %1").arg(cycle_);
  text += QStringLiteral(" · 节拍 %1").arg(intervalMs_);
  cycleChip_->setText(text);
  cycleChip_->setToolTip(
      QStringLiteral("周期 %1 · 上次 %2 ms · 连续节拍 %3 ms · 滚轮±50 · Ctrl+滚轮±200 · Alt+1..4 预设 · Ctrl+单击清零 · 双击清零 · 右键清连OK")
          .arg(cycle_)
          .arg(lastCycleMs_ >= 0 ? lastCycleMs_ : 0.0, 0, 'f', 1)
          .arg(intervalMs_));
}

void HostStrip::refreshChips(const QVariantMap& vars) {
  if (!vars.isEmpty()) lastVars_ = vars;
  const QVariantMap& src = vars.isEmpty() ? lastVars_ : vars;
  if (watchKeys_.isEmpty()) {
    chips_->setText({});
    return;
  }
  QStringList parts;
  for (const QString& k : watchKeys_) {
    parts << QStringLiteral("%1=%2").arg(k, src.value(k).toString().left(24));
  }
  // also surface bound I/O output names if present
  for (auto it = src.begin(); it != src.end(); ++it) {
    if (it.key().startsWith(QStringLiteral("io.")))
      parts << QStringLiteral("%1=%2").arg(it.key(), it.value().toString().left(20));
  }
  chips_->setText(parts.join(QStringLiteral("  ·  ")));
}

void HostStrip::setTcpStatus(const QString& status) {
  tcpStatus_ = status;
  // Soft refresh of last detail line without needing vars — keep tcp visible.
  QString d = detail_ ? detail_->text() : QString();
  const QString marker = QStringLiteral(" · tcp=");
  const int at = d.indexOf(marker);
  if (at >= 0) d = d.left(at);
  if (!tcpStatus_.isEmpty())
    d += marker + tcpStatus_.left(36);
  if (detail_) {
    detail_->setText(d.isEmpty() ? QStringLiteral("Host · tcp=%1").arg(tcpStatus_.left(36))
                                 : d);
    if (!tcpStatus_.isEmpty())
      detail_->setToolTip(QStringLiteral("tcp=%1").arg(tcpStatus_));
  }
}

void HostStrip::updateFromVars(const QVariantMap& vars, int codeCount, bool evaluated) {
  bool ok = false;
  if (vars.contains(QStringLiteral("passGate"))) {
    ok = vars.value(QStringLiteral("passGate")).toInt() != 0 ||
         vars.value(QStringLiteral("passGate")).toBool();
  } else {
    ok = vars.value(QStringLiteral("barcodeOk")).toInt() != 0 ||
         vars.value(QStringLiteral("barcodeOk")).toBool() ||
         vars.value(QStringLiteral("locateOk")).toInt() != 0;
  }
  const int count = codeCount >= 0
                        ? codeCount
                        : vars.value(QStringLiteral("barcodeCount")).toInt();
  const QString text = vars.value(QStringLiteral("barcodeText")).toString();
  const bool ran = evaluated;
  if (ran) {
    if (ok) {
      ++okStreak_;
    } else {
      okStreak_ = 0;
      ++ngCount_;
    }
  }

  if (alarmOn_) {
    lastResult_ = QStringLiteral("ALARM");
    badge_->setText(lastResult_);
    badge_->setStyleSheet(
        QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else if (!ran) {
    lastResult_ = QStringLiteral("—");
    badge_->setText(lastResult_);
    badge_->setStyleSheet(
        QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else if (ok) {
    lastResult_ = QStringLiteral("OK");
    badge_->setText(lastResult_);
    badge_->setStyleSheet(
        QStringLiteral("background:#2d9b6c;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else {
    lastResult_ = QStringLiteral("NG");
    badge_->setText(lastResult_);
    badge_->setStyleSheet(
        QStringLiteral("background:#e53935;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  }
  QString detail = QStringLiteral("count=%1 · text=%2")
                       .arg(count)
                       .arg(text.left(32));
  if (vars.contains(QStringLiteral("locateScore"))) {
    detail += QStringLiteral(" · 匹配=%1")
                  .arg(vars.value(QStringLiteral("locateScore")).toDouble(), 0, 'f', 2);
  }
  const QString formatted = vars.value(QStringLiteral("formatted")).toString();
  if (!formatted.isEmpty()) detail += QStringLiteral(" · %1").arg(formatted.left(32));
  const QString lastRecv = vars.value(QStringLiteral("lastRecv")).toString();
  if (!lastRecv.isEmpty())
    detail += QStringLiteral(" · RX=%1").arg(lastRecv.left(28));
  const QString urlOk = vars.value(QStringLiteral("urlOk")).toString();
  if (!urlOk.isEmpty())
    detail += QStringLiteral(" · urlOk=%1").arg(urlOk);
  const QString ioOut = vars.value(QStringLiteral("io.Result")).toString();
  if (!ioOut.isEmpty()) detail += QStringLiteral(" · I/O.Result=%1").arg(ioOut.left(24));
  if (!tcpStatus_.isEmpty())
    detail += QStringLiteral(" · tcp=%1").arg(tcpStatus_.left(36));
  const bool vLock =
      recipeLocked_ ||
      vars.value(QStringLiteral("recipeLocked")).toInt() != 0 ||
      vars.value(QStringLiteral("host.recipeLocked")).toInt() != 0;
  const bool vLatch =
      alarmOn_ ||
      vars.value(QStringLiteral("alarmLatched")).toInt() != 0 ||
      vars.value(QStringLiteral("host.alarmLatched")).toInt() != 0;
  if (vLock) detail += QStringLiteral(" · 锁");
  if (vLatch) detail += QStringLiteral(" · 锁存");
  if (ran) {
    const int total = okStreak_ + ngCount_;
    const double yld = total > 0 ? (100.0 * okStreak_ / total) : 0.0;
    detail += QStringLiteral(" · 连OK %1 · NG %2 · 良率 %3%")
                  .arg(okStreak_).arg(ngCount_).arg(yld, 0, 'f', 1);
  }
  if (lastCycleMs_ >= 0)
    detail += QStringLiteral(" · %1 ms").arg(lastCycleMs_, 0, 'f', 1);
  detail_->setText(detail);
  refreshChips(vars);
}


void HostStrip::resetStreak() {
  okStreak_ = 0;
  ngCount_ = 0;
  if (detail_) {
    QString d = detail_->text();
    const int at = d.indexOf(QStringLiteral(" · 连OK"));
    if (at >= 0) d = d.left(at);
    detail_->setText(d + QStringLiteral(" · 连OK 0 · NG 0 · 良率 0.0%"));
    detail_->setToolTip(QStringLiteral("连OK/NG 已清零 · Alt+单击徽章 / 右键周期"));
  }
}

bool HostStrip::eventFilter(QObject* obj, QEvent* event) {
  if (event->type() == QEvent::Wheel && obj == cycleChip_) {
    auto* we = static_cast<QWheelEvent*>(event);
    const int step = (we->modifiers() & Qt::ControlModifier) ? 200 : 50;
    const int delta = we->angleDelta().y() > 0 ? step : -step;
    const int next = qBound(20, intervalMs_ + delta, 60000);
    if (next != intervalMs_) {
      intervalMs_ = next;
      refreshCycleChip();
      emit intervalChanged(intervalMs_);
    }
    return true;
  }
  if (event->type() == QEvent::MouseButtonDblClick) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton && obj == chips_) {
      bool ok = false;
      const QString cur = watchKeys_.join(QLatin1Char(','));
      const QString neu = QInputDialog::getText(
          this, QStringLiteral("监视变量"), QStringLiteral("逗号分隔变量名"),
          QLineEdit::Normal, cur, &ok);
      if (ok) {
        QStringList keys;
        for (const QString& p : neu.split(QLatin1Char(','))) {
          const QString k = p.trimmed();
          if (!k.isEmpty()) keys << k;
        }
        watchKeys_ = keys;
        emit watchKeysChanged(watchKeys_);
        refreshChips({});
      }
      return true;
    }
    if (me->button() == Qt::LeftButton && obj == cycleChip_) {
      emit cycleResetRequested();
      return true;
    }
    if (me->button() == Qt::LeftButton && obj == detail_ && detail_) {
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(detail_->text());
        detail_->setToolTip(QStringLiteral("已复制 Host 明细 · 双击"));
      }
      return true;
    }
  }
  if (event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::RightButton && obj == modeChip_) {
      emit continuousToggleRequested();
      return true;
    }
    if (me->button() == Qt::RightButton && obj == cycleChip_) {
      resetStreak();
      return true;
    }
    if (me->button() == Qt::MiddleButton && obj == cycleChip_) {
      const int total = okStreak_ + ngCount_;
      const double yld = total > 0 ? (100.0 * okStreak_ / total) : 0.0;
      const QString line = QStringLiteral("yield=%1%% ok=%2 ng=%3 cycle=%4 lastMs=%5")
                               .arg(yld, 0, 'f', 1)
                               .arg(okStreak_)
                               .arg(ngCount_)
                               .arg(cycle_)
                               .arg(lastCycleMs_, 0, 'f', 1);
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
      if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("已复制良率 · 中键周期"));
      return true;
    }
    if (me->button() == Qt::MiddleButton && obj == detail_ && detail_) {
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(QStringLiteral("连OK=%1 NG=%2").arg(okStreak_).arg(ngCount_));
        detail_->setToolTip(QStringLiteral("已复制良率摘要 · 中键"));
      }
      return true;
    }
    if (me->button() == Qt::MiddleButton && obj == badge_) {
      copyRunStats();
      return true;
    }
    if (me->button() == Qt::MiddleButton && obj == modeChip_) {
      emit continuousToggleRequested();
      return true;
    }
    if (me->button() == Qt::RightButton && obj == detail_ && detail_) {
      copyRunStats();
      return true;
    }
    if (me->button() == Qt::RightButton && obj == pinGroupChip_ && pinGroupChip_) {
      showPinGroupPicker();
      return true;
    }
    if (me->button() != Qt::LeftButton) return QWidget::eventFilter(obj, event);
    if (obj == lockChip_) {
      emit modeToggleRequested();
      return true;
    }
    if (obj == modeChip_) {
      if (me->modifiers() & Qt::AltModifier) {
        emit pauseRequested();
        return true;
      }
      emit modeToggleRequested();
      return true;
    }
    if (obj == cycleChip_) {
      if (me->modifiers() & Qt::ControlModifier) {
        emit cycleResetRequested();
        return true;
      }
      if (me->modifiers() & Qt::AltModifier) {
        resetStreak();
        return true;
      }
    }
    if (obj == pinGroupChip_ && pinGroupChip_) {
      emit openVarWatchRequested();
      return true;
    }
    if (obj == chips_ && chips_) {
      if (chips_->text().trimmed().isEmpty() || watchKeys_.isEmpty()) {
        // Empty: open editor (same as double-click) so first pin is one click.
        const QString cur = watchKeys_.join(QLatin1Char(','));
        bool ok = false;
        const QString text = QInputDialog::getText(
            this, QStringLiteral("Host 监视键"),
            QStringLiteral("逗号分隔变量名 · 空=清除"),
            QLineEdit::Normal, cur, &ok);
        if (ok) {
          QStringList keys;
          for (const QString& p : text.split(QLatin1Char(','))) {
            const QString t = p.trimmed();
            if (!t.isEmpty()) keys << t;
          }
          watchKeys_ = keys;
          emit watchKeysChanged(watchKeys_);
        }
        return true;
      }
      if (auto* clip = QGuiApplication::clipboard()) {
        clip->setText(chips_->text());
        chips_->setToolTip(QStringLiteral("已复制监视芯片 · 双击编辑键列表"));
      }
      return true;
    }
    if (obj == badge_) {
      if (me->modifiers() & Qt::AltModifier) {
        resetStreak();
        return true;
      }
      emit openHostRequested();
      return true;
    }
    if (obj == alarmLabel_) {
      emit openHostRequested();
      return true;
    }
  }
  if (event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_C && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      copyRunStats();
      return true;
    }
    if (ke->key() == Qt::Key_T && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      copyCycleChip();
      return true;
    }
    if (ke->key() == Qt::Key_I && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      pasteIntervalMs();
      return true;
    }
    if (ke->key() == Qt::Key_P && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      pasteHostConfig();
      return true;
    }
    if (ke->key() == Qt::Key_R && (ke->modifiers() & Qt::ControlModifier)) {
      resetStreak();
      return true;
    }
    if (ke->key() == Qt::Key_J && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      const int total = okStreak_ + ngCount_;
      const double yld = total > 0 ? (100.0 * okStreak_ / total) : 0.0;
      const QString js = QStringLiteral(
          "{\"cycle\":%1,\"lastMs\":%2,\"okStreak\":%3,\"ng\":%4,\"yield\":%5}")
          .arg(cycle_)
          .arg(lastCycleMs_, 0, 'f', 1)
          .arg(okStreak_)
          .arg(ngCount_)
          .arg(yld, 0, 'f', 1);
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(js);
      if (detail_) detail_->setToolTip(QStringLiteral("已复制良率JSON · Ctrl+Shift+J"));
      return true;
    }
    if (ke->key() == Qt::Key_V && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      pasteWatchKeysFromClipboard();
      return true;
    }
    if (ke->key() == Qt::Key_K && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      copyWatchKeys();
      return true;
    }
    if (ke->key() == Qt::Key_E && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      exportWatchKeysJson();
      return true;
    }
    if (ke->key() == Qt::Key_Escape) {
      if (alarmOn_ && (hostState_ == QLatin1String("Idle") || hostState_ == QLatin1String("Alarm") ||
                       hostState_ == QLatin1String("Stopped"))) {
        setAlarm(false);
        if (detail_) detail_->setToolTip(QStringLiteral("报警已清除 · Esc"));
        emit clearAlarmRequested();
        return true;
      }
      emit stopRequested();
      return true;
    }
    if (ke->key() == Qt::Key_Space &&
        !(ke->modifiers() & (Qt::ControlModifier | Qt::AltModifier | Qt::ShiftModifier))) {
      if (hostState_ == QLatin1String("Running") || hostState_ == QLatin1String("Paused"))
        emit pauseRequested();
      else
        emit runContinuousRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F5 || ke->key() == Qt::Key_F9) {
      emit runOnceRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F6) {
      if (continuous_ && (hostState_ == QLatin1String("Running") ||
                          hostState_ == QLatin1String("Paused")))
        emit pauseRequested();
      else
        emit runContinuousRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F7) {
      emit pauseRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F8) {
      if (ke->modifiers() & Qt::ShiftModifier)
        emit continuousToggleRequested();
      else
        emit modeToggleRequested();
      return true;
    }
    if (ke->key() == Qt::Key_F3) {
      emit openHostRequested();
      return true;
    }
    if (ke->key() == Qt::Key_Y && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      reverseWatchKeys();
      return true;
    }
    if (ke->key() == Qt::Key_S && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      sortWatchKeys();
      return true;
    }
    if (ke->key() == Qt::Key_U && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      dedupeWatchKeys();
      return true;
    }
    if ((ke->key() == Qt::Key_Delete || ke->key() == Qt::Key_Backspace) &&
        (ke->modifiers() & Qt::ControlModifier) && (ke->modifiers() & Qt::ShiftModifier)) {
      clearWatchKeys();
      return true;
    }
    if ((ke->key() == Qt::Key_Delete || ke->key() == Qt::Key_Backspace) &&
        (ke->modifiers() & Qt::ShiftModifier) &&
        !(ke->modifiers() & Qt::ControlModifier) && !(ke->modifiers() & Qt::AltModifier)) {
      removeTailWatchKey();
      return true;
    }
    if ((ke->key() == Qt::Key_Delete || ke->key() == Qt::Key_Backspace) &&
        !(ke->modifiers() & Qt::ControlModifier) && !(ke->modifiers() & Qt::AltModifier) &&
        !(ke->modifiers() & Qt::ShiftModifier)) {
      removeHeadWatchKey();
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
        refreshCycleChip();
        emit intervalChanged(intervalMs_);
      }
      if (cycleChip_)
        cycleChip_->setToolTip(QStringLiteral("节拍 %1 ms · Ctrl+↑↓/[]").arg(next));
      return true;
    }
    if (ke->key() == Qt::Key_0 && (ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier)) {
      resetStreak();
      if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("连OK/NG 已清零 · Ctrl+Shift+0"));
      return true;
    }
    if ((ke->key() == Qt::Key_Left || ke->key() == Qt::Key_Right) &&
        (ke->modifiers() & Qt::AltModifier)) {
      moveWatchKey(ke->key() == Qt::Key_Left ? -1 : +1);
      return true;
    }
    if ((ke->key() == Qt::Key_Home || ke->key() == Qt::Key_End) &&
        (ke->modifiers() & Qt::ControlModifier)) {
      moveWatchKeyToEdge(ke->key() == Qt::Key_Home ? -1 : +1);
      return true;
    }
    if ((ke->modifiers() & Qt::AltModifier) && ke->key() >= Qt::Key_1 && ke->key() <= Qt::Key_4 &&
        !(ke->modifiers() & Qt::ControlModifier)) {
      static const int kPresets[] = {50, 100, 200, 500};
      const int next = kPresets[ke->key() - Qt::Key_1];
      if (next != intervalMs_) {
        intervalMs_ = next;
        refreshCycleChip();
        emit intervalChanged(intervalMs_);
      }
      if (cycleChip_)
        cycleChip_->setToolTip(QStringLiteral("节拍 %1 ms · Alt+%2").arg(next).arg(ke->key() - Qt::Key_0));
      return true;
    }
  }
  return QWidget::eventFilter(obj, event);
}

void HostStrip::copyRunStats() {
  const int total = okStreak_ + ngCount_;
  const double yld = total > 0 ? (100.0 * okStreak_ / total) : 0.0;
  const QString line = QStringLiteral(
      "cycle=%1 lastMs=%2 okStreak=%3 ng=%4 yield=%5%% mode=%6 detail=%7")
      .arg(cycle_)
      .arg(lastCycleMs_, 0, 'f', 1)
      .arg(okStreak_)
      .arg(ngCount_)
      .arg(yld, 0, 'f', 1)
      .arg(modeChip_ ? modeChip_->text() : QString())
      .arg(detail_ ? detail_->text() : QString());
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
  if (detail_) detail_->setToolTip(QStringLiteral("已复制运行统计 · Ctrl+Shift+C"));
}


void HostStrip::copyCycleChip() {
  const QString text = cycleChip_ ? cycleChip_->text() : QString();
  if (text.isEmpty()) {
    if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("周期条空 · Ctrl+Shift+T"));
    return;
  }
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(text);
  if (cycleChip_)
    cycleChip_->setToolTip(QStringLiteral("已复制周期条 · Ctrl+Shift+T · 节拍 %1").arg(intervalMs_));
}


void HostStrip::pasteIntervalMs() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text().trimmed()
                          : QString();
  if (raw.isEmpty()) {
    if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("剪贴板空 · Ctrl+Shift+I"));
    return;
  }
  // accept plain int, or ...intervalMs=200..., or "200 ms"
  QString s = raw;
  const int eq = s.lastIndexOf(QLatin1String("intervalMs="));
  if (eq >= 0) s = s.mid(eq + 11);
  s = s.split(QRegularExpression(QStringLiteral("[^0-9]"))).value(0);
  bool ok = false;
  const int ms = s.toInt(&ok);
  if (!ok || ms <= 0) {
    if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("无效节拍 · Ctrl+Shift+I"));
    return;
  }
  const int next = qBound(20, ms, 60000);
  if (next != intervalMs_) {
    intervalMs_ = next;
    refreshCycleChip();
    emit intervalChanged(intervalMs_);
  }
  if (cycleChip_)
    cycleChip_->setToolTip(QStringLiteral("已粘贴节拍 %1 ms · Ctrl+Shift+I").arg(intervalMs_));
}


void HostStrip::pasteHostConfig() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text().trimmed()
                          : QString();
  if (raw.isEmpty()) {
    if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("剪贴板空 · Ctrl+Shift+P"));
    return;
  }
  int ms = -1;
  QString mode, policy;
  for (const QString& part : raw.split(QRegularExpression(QStringLiteral("[\t\n;]+")))) {
    const QString p = part.trimmed();
    if (p.startsWith(QLatin1String("intervalMs="))) {
      bool ok = false;
      const int v = p.mid(11).trimmed().toInt(&ok);
      if (ok) ms = v;
    } else if (p.startsWith(QLatin1String("mode="))) {
      mode = p.mid(5).trimmed();
    } else if (p.startsWith(QLatin1String("policy="))) {
      policy = p.mid(7).trimmed();
    }
  }
  if (ms < 0) {
    // fall back to pasteIntervalMs parser path
    pasteIntervalMs();
    return;
  }
  int applied = 0;
  if (ms >= 20 && ms <= 60000) {
    if (ms != intervalMs_) {
      intervalMs_ = ms;
      refreshCycleChip();
      emit intervalChanged(intervalMs_);
    }
    ++applied;
  }
  QString tip = QStringLiteral("已粘贴 Host 配置");
  if (applied) tip += QStringLiteral(" 节拍%1").arg(intervalMs_);
  if (!mode.isEmpty()) tip += QStringLiteral(" mode=%1").arg(mode);
  if (!policy.isEmpty()) tip += QStringLiteral(" policy=%1").arg(policy);
  tip += QStringLiteral(" · Ctrl+Shift+P");
  if (!applied && mode.isEmpty() && policy.isEmpty()) {
    if (cycleChip_) cycleChip_->setToolTip(QStringLiteral("无匹配配置 · Ctrl+Shift+P"));
    return;
  }
  if (cycleChip_) cycleChip_->setToolTip(tip);
  else if (detail_) detail_->setToolTip(tip);
}


void HostStrip::pasteWatchKeysFromClipboard() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text().trimmed()
                          : QString();
  if (raw.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("剪贴板空 · Ctrl+Shift+V"));
    return;
  }
  QStringList keys;
  {
    QJsonParseError err;
    const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &err);
    if (err.error == QJsonParseError::NoError) {
      if (doc.isObject()) {
        const QJsonObject o = doc.object();
        QJsonArray arr = o.value(QStringLiteral("keys")).toArray();
        if (arr.isEmpty()) arr = o.value(QStringLiteral("watchKeys")).toArray();
        if (arr.isEmpty()) arr = o.value(QStringLiteral("varWatchKeys")).toArray();
        for (const QJsonValue& v : arr) {
          const QString k = v.toString().trimmed();
          if (!k.isEmpty() && !keys.contains(k)) keys << k;
        }
        if (keys.isEmpty()) {
          for (auto it = o.begin(); it != o.end(); ++it) {
            const QString k = it.key().trimmed();
            if (k == QLatin1String("keys") || k == QLatin1String("watchKeys") ||
                k == QLatin1String("varWatchKeys") || k == QLatin1String("count"))
              continue;
            if (!k.isEmpty() && !keys.contains(k)) keys << k;
          }
        }
      } else if (doc.isArray()) {
        for (const QJsonValue& v : doc.array()) {
          const QString k = v.toString().trimmed();
          if (!k.isEmpty() && !keys.contains(k)) keys << k;
        }
      }
    }
  }
  if (keys.isEmpty()) {
    const QString norm = QString(raw).replace(QLatin1Char('\n'), QLatin1Char(','))
                             .replace(QLatin1Char(';'), QLatin1Char(','))
                             .replace(QLatin1Char('\t'), QLatin1Char(','));
    for (const QString& p : norm.split(QLatin1Char(','))) {
      const QString k = p.trimmed();
      if (!k.isEmpty() && !keys.contains(k)) keys << k;
    }
  }
  if (keys.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("无有效监视键 · Ctrl+Shift+V"));
    return;
  }
  watchKeys_ = keys;
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("已粘贴监视键 %1 · Ctrl+Shift+V").arg(keys.size()));
}



void HostStrip::moveWatchKey(int delta) {
  if (watchKeys_.size() < 2 || delta == 0) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键不足 · Alt+←→"));
    return;
  }
  if (delta < 0) {
    const QString head = watchKeys_.takeFirst();
    watchKeys_.append(head);
  } else {
    const QString tail = watchKeys_.takeLast();
    watchKeys_.prepend(tail);
  }
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("监视键轮转 · 首=%1 · Alt+←→").arg(watchKeys_.first()));
}

void HostStrip::moveWatchKeyToEdge(int edge) {
  if (watchKeys_.size() < 2) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键不足 · Ctrl+Home/End"));
    return;
  }
  if (edge < 0) {
    // Ctrl+Home: pin last key to front
    const QString tail = watchKeys_.takeLast();
    watchKeys_.prepend(tail);
    if (chips_)
      chips_->setToolTip(QStringLiteral("末键置顶 %1 · Ctrl+Home").arg(watchKeys_.first()));
  } else {
    // Ctrl+End: pin first key to end
    const QString head = watchKeys_.takeFirst();
    watchKeys_.append(head);
    if (chips_)
      chips_->setToolTip(QStringLiteral("首键置底 · 现首=%1 · Ctrl+End").arg(watchKeys_.first()));
  }
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
}

void HostStrip::reverseWatchKeys() {
  if (watchKeys_.size() < 2) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键不足 · Ctrl+Shift+Y"));
    return;
  }
  std::reverse(watchKeys_.begin(), watchKeys_.end());
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("监视键已反序 %1 · Ctrl+Shift+Y · 首=%2")
                           .arg(watchKeys_.size())
                           .arg(watchKeys_.first()));
}




void HostStrip::dedupeWatchKeys() {
  if (watchKeys_.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键空 · Ctrl+Shift+U"));
    return;
  }
  QStringList uniq;
  int dropped = 0;
  for (const QString& k : watchKeys_) {
    if (uniq.contains(k)) { ++dropped; continue; }
    uniq << k;
  }
  if (dropped <= 0) {
    if (chips_) chips_->setToolTip(QStringLiteral("无重复 · Ctrl+Shift+U"));
    return;
  }
  watchKeys_ = uniq;
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("监视键去重 −%1 · 剩 %2 · Ctrl+Shift+U")
                           .arg(dropped)
                           .arg(watchKeys_.size()));
}

void HostStrip::sortWatchKeys() {
  if (watchKeys_.size() < 2) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键不足 · Ctrl+Shift+S"));
    return;
  }
  std::sort(watchKeys_.begin(), watchKeys_.end(),
            [](const QString& a, const QString& b) {
              return QString::localeAwareCompare(a, b) < 0;
            });
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("监视键已排序 %1 · Ctrl+Shift+S · 首=%2")
                           .arg(watchKeys_.size())
                           .arg(watchKeys_.first()));
}

void HostStrip::removeHeadWatchKey() {
  if (watchKeys_.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键空 · Del"));
    return;
  }
  const QString gone = watchKeys_.takeFirst();
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("已删首键 %1 · 剩 %2 · Del")
                           .arg(gone)
                           .arg(watchKeys_.size()));
}

void HostStrip::removeTailWatchKey() {
  if (watchKeys_.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键空 · Shift+Del"));
    return;
  }
  const QString gone = watchKeys_.takeLast();
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("已删末键 %1 · Shift+Del · 余 %2").arg(gone).arg(watchKeys_.size()));
}


void HostStrip::clearWatchKeys() {
  if (watchKeys_.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键已空 · Ctrl+Shift+Bksp"));
    return;
  }
  const int n = watchKeys_.size();
  watchKeys_.clear();
  emit watchKeysChanged(watchKeys_);
  refreshChips({});
  if (chips_)
    chips_->setToolTip(QStringLiteral("已清空监视键 %1 · Ctrl+Shift+Bksp").arg(n));
}

void HostStrip::copyWatchKeys() {
  const QString line = watchKeys_.join(QLatin1Char(','));
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
  if (chips_)
    chips_->setToolTip(
        line.isEmpty() ? QStringLiteral("监视键空 · Ctrl+Shift+K")
                       : QStringLiteral("已复制监视键 %1 · Ctrl+Shift+K").arg(watchKeys_.size()));
}


void HostStrip::exportWatchKeysJson() {
  if (watchKeys_.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("监视键空 · Ctrl+Shift+E"));
    return;
  }
  QJsonArray arr;
  for (const QString& k : watchKeys_) arr.append(k);
  QJsonObject root;
  root.insert(QStringLiteral("watchKeys"), arr);
  root.insert(QStringLiteral("keys"), arr);
  root.insert(QStringLiteral("count"), arr.size());
  const QByteArray bytes = QJsonDocument(root).toJson(QJsonDocument::Compact);
  if (auto* clip = QGuiApplication::clipboard())
    clip->setText(QString::fromUtf8(bytes));
  if (chips_)
    chips_->setToolTip(QStringLiteral("已导出监视键JSON %1 · Ctrl+Shift+E").arg(watchKeys_.size()));
}

void HostStrip::setPinGroups(const QStringList& names, const QString& active) {
  pinGroupNames_.clear();
  for (const QString& n : names) {
    const QString t = n.trimmed();
    if (!t.isEmpty() && !pinGroupNames_.contains(t)) pinGroupNames_ << t;
  }
  QString act = active.trimmed();
  if (!act.isEmpty() && pinGroupNames_.contains(act))
    activePinGroup_ = act;
  else
    activePinGroup_ = pinGroupNames_.isEmpty() ? QString() : pinGroupNames_.first();
  refreshPinGroupChip();
}

bool HostStrip::selectPinGroup(const QString& name) {
  const QString n = name.trimmed();
  if (n.isEmpty() || !pinGroupNames_.contains(n)) return false;
  activePinGroup_ = n;
  refreshPinGroupChip();
  emit pinGroupPicked(n);
  return true;
}

QString HostStrip::pinGroupChipText() const {
  return pinGroupChip_ ? pinGroupChip_->text() : QString();
}

bool HostStrip::pinGroupChipVisible() const {
  // isHidden() is the local flag; isVisible() is false while the strip itself
  // has not been shown (offscreen selftest constructs a bare HostStrip).
  return pinGroupChip_ && !pinGroupChip_->isHidden();
}

QString HostStrip::watchChipsText() const {
  return chips_ ? chips_->text() : QString();
}

void HostStrip::refreshPinGroupChip() {
  if (!pinGroupChip_) return;
  if (pinGroupNames_.isEmpty()) {
    pinGroupChip_->clear();
    pinGroupChip_->setVisible(false);
    return;
  }
  const QString act = activePinGroup_.isEmpty() ? pinGroupNames_.first() : activePinGroup_;
  QString text = QStringLiteral("钉组:%1").arg(act);
  if (pinGroupNames_.size() > 1)
    text += QStringLiteral(" ×%1").arg(pinGroupNames_.size());
  pinGroupChip_->setText(text);
  pinGroupChip_->setVisible(true);
  pinGroupChip_->setToolTip(
      QStringLiteral("钉组 %1 · 共 %2 组 · 单击打开变量监视 · 右键选组 · 数字键 1–9 加速 · 无硬件")
          .arg(act)
          .arg(pinGroupNames_.size()));
}

void HostStrip::showPinGroupPicker() {
  if (pinGroupNames_.isEmpty()) return;
  QMenu menu(this);
  int i = 0;
  for (const QString& n : pinGroupNames_) {
    const QString label = (i < 9) ? QStringLiteral("%1  %2").arg(i + 1).arg(n) : n;
    QAction* a = menu.addAction(label);
    a->setCheckable(true);
    a->setChecked(n == activePinGroup_);
    if (i < 9) a->setShortcut(QKeySequence(QString::number(i + 1)));
    connect(a, &QAction::triggered, this, [this, n]() { selectPinGroup(n); });
    ++i;
  }
  menu.setToolTipsVisible(true);
  menu.exec(QCursor::pos());
}

QStringList HostStrip::pinGroupChromeSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };
  if (!qApp) {
    fails << QStringLiteral("no-qapp");
    return fails;
  }

  HostStrip strip;
  check("hidden-when-empty", !strip.pinGroupChipVisible());
  strip.setPinGroups({QStringLiteral("定位"), QStringLiteral("测量")},
                     QStringLiteral("测量"));
  check("chip-visible", strip.pinGroupChipVisible());
  check("chip-text", strip.pinGroupChipText().contains(QStringLiteral("测量")),
        strip.pinGroupChipText());
  check("chip-count", strip.pinGroupChipText().contains(QStringLiteral("×2")),
        strip.pinGroupChipText());
  check("select", strip.selectPinGroup(QStringLiteral("定位")));
  check("active-after-select", strip.activePinGroup() == QStringLiteral("定位"),
        strip.activePinGroup());
  check("chip-after-select", strip.pinGroupChipText().contains(QStringLiteral("定位")),
        strip.pinGroupChipText());
  check("select-missing", !strip.selectPinGroup(QStringLiteral("不存在")));
  strip.setWatchKeys({QStringLiteral("locateOk"), QStringLiteral("locateScore")});
  QVariantMap vars;
  vars.insert(QStringLiteral("locateOk"), 1);
  vars.insert(QStringLiteral("locateScore"), 0.91);
  strip.updateFromVars(vars);
  check("chips-locate", strip.watchChipsText().contains(QStringLiteral("locateOk=")),
        strip.watchChipsText());
  check("chips-score", strip.watchChipsText().contains(QStringLiteral("locateScore=")),
        strip.watchChipsText());

  VarWatchPanel vw;
  QHash<QString, QStringList> keys;
  keys.insert(QStringLiteral("定位"), QStringList{QStringLiteral("locateOk")});
  keys.insert(QStringLiteral("测量"),
              QStringList{QStringLiteral("caliperMm"), QStringLiteral("measureMm")});
  vw.setPinGroups({QStringLiteral("定位"), QStringLiteral("测量")}, keys,
                  QStringLiteral("测量"));
  check("vw-count", vw.pinGroupCount() == 2, QString::number(vw.pinGroupCount()));
  check("vw-active", vw.activePinGroup() == QStringLiteral("测量"), vw.activePinGroup());
  check("vw-lab", vw.pinGroupLabelText().contains(QStringLiteral("2键")),
        vw.pinGroupLabelText());
  vw.selectPinGroup(QStringLiteral("定位"));
  check("vw-switched", vw.activePinGroup() == QStringLiteral("定位"),
        vw.activePinGroup());
  check("vw-lab-switched", vw.pinGroupLabelText().contains(QStringLiteral("定位")),
        vw.pinGroupLabelText());
  return fails;
}

void HostStrip::keyPressEvent(QKeyEvent* event) {
  if (event && eventFilter(this, event)) return;
  QWidget::keyPressEvent(event);
}

}  // namespace sieans_qt

