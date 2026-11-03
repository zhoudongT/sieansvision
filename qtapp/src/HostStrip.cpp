#include "HostStrip.hpp"
#include <QInputDialog>
#include <QLineEdit>
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QCursor>
#include <QGuiApplication>
#include <QClipboard>
#include <QApplication>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QEvent>

namespace sieans_qt {

HostStrip::HostStrip(QWidget* parent) : QWidget(parent) {
  setFocusPolicy(Qt::StrongFocus);
  setStatusTip(QStringLiteral("Host 条 · OK/NG/ALARM · tcp= 摘要(lf/crlf/raw/len4) · Esc 停止运行 · 周期 chip 见右侧 · 单击模式切换 · 右键连续 · Ctrl+单击周期清零 · 双击明细复制 · Ctrl+Shift+V 粘贴监视键 · 周期中键良率 · 周期 ms"));
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
  modeChip_->setToolTip(QStringLiteral("运行模式 · 设计态/运行/连续/暂停 · 运行态锁画布 · F5/F9 仍可单次"));
  modeChip_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "padding:3px 8px;font-size:11px;font-weight:600;"));
  cycleChip_ = new QLabel(QStringLiteral("周期 0"));
  cycleChip_->setToolTip(QStringLiteral("运行周期计数 · 每次流程完成 +1"));
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
  row->addWidget(badge_);
  row->addWidget(modeChip_);
  row->addWidget(cycleChip_);
  row->addWidget(detail_, 1);
  row->addWidget(alarmLabel_);
  root->addLayout(row);
  badge_->setCursor(Qt::PointingHandCursor);
  modeChip_->setCursor(Qt::PointingHandCursor);
  cycleChip_->setCursor(Qt::PointingHandCursor);
  cycleChip_->setFocusPolicy(Qt::ClickFocus);
  detail_->setCursor(Qt::PointingHandCursor);
  badge_->setToolTip(QStringLiteral("OK/NG/ALARM · passGate 判定 · 单击打开 Host 面板 · Alt+单击清连OK/NG · 中键复制运行统计 · tcp= 见明细"));
  modeChip_->setToolTip(QStringLiteral("运行模式 · 单击设计/运行 · Alt 暂停/继续 · 右键/中键连续"));
  cycleChip_->setToolTip(QStringLiteral("周期 · 上次 ms · 节拍 · 滚轮±50 · Ctrl+滚轮±200 · Alt+1/2/3/4→50/100/200/500 · Ctrl+单击/双击清零 · 右键/Alt+单击清连OK · 中键良率"));
  detail_->setToolTip(QStringLiteral("count/text/RX/urlOk/tcp/良率 摘要 · framing lf/crlf/raw/len4 见 tcp= · 双击复制全文 · 中键复制连OK/NG · 右键/Ctrl+Shift+C 运行统计 · 悬停看全文"));
  badge_->installEventFilter(this);
  modeChip_->installEventFilter(this);
  cycleChip_->installEventFilter(this);
  detail_->installEventFilter(this);
  chips_ = new QLabel;
  chips_->setObjectName(QStringLiteral("muted"));
  chips_->setWordWrap(true);
  chips_->setCursor(Qt::PointingHandCursor);
  chips_->setToolTip(QStringLiteral("监视变量芯片 · 双击编辑 · Ctrl+Shift+K/V 复制/粘贴键 · Alt+←→ 调序 · 单击复制全文"));
  chips_->installEventFilter(this);
  root->addWidget(chips_);
  setStyleSheet(QStringLiteral("background:#232528;border-top:1px solid #4a4e54;"));
  setMinimumHeight(52);
}

void HostStrip::setWatchKeys(const QStringList& keys) { watchKeys_ = keys; }

void HostStrip::setAlarm(bool on, const QString& reason) {
  alarmOn_ = on;
  alarmReason_ = reason;
  alarmLabel_->setVisible(on);
  alarmLabel_->setText(on ? QStringLiteral("ALARM %1").arg(reason.left(40))
                          : QString());
}

void HostStrip::setRunChrome(const QString& mode, const QString& hostState, int cycle) {
  cycle_ = cycle;
  const bool run = mode.contains(QStringLiteral("运行")) || mode.contains(QStringLiteral("连续")) ||
                   mode.contains(QStringLiteral("暂停"));
  modeChip_->setText(QStringLiteral("%1 · %2").arg(mode, hostState.isEmpty() ? QStringLiteral("Idle")
                                                                          : hostState));
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
    badge_->setText(QStringLiteral("ALARM"));
    badge_->setStyleSheet(
        QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else if (!ran) {
    badge_->setText(QStringLiteral("—"));
    badge_->setStyleSheet(
        QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else if (ok) {
    badge_->setText(QStringLiteral("OK"));
    badge_->setStyleSheet(
        QStringLiteral("background:#2d9b6c;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else {
    badge_->setText(QStringLiteral("NG"));
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
    if (me->button() != Qt::LeftButton) return QWidget::eventFilter(obj, event);
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
    if (ke->key() == Qt::Key_F7) {
      emit pauseRequested();
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
    if ((ke->key() == Qt::Key_Left || ke->key() == Qt::Key_Right) &&
        (ke->modifiers() & Qt::AltModifier)) {
      moveWatchKey(ke->key() == Qt::Key_Left ? -1 : +1);
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


void HostStrip::pasteWatchKeysFromClipboard() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text().trimmed()
                          : QString();
  if (raw.isEmpty()) {
    if (chips_) chips_->setToolTip(QStringLiteral("剪贴板空 · Ctrl+Shift+V"));
    return;
  }
  QStringList keys;
  const QString norm = QString(raw).replace(QLatin1Char('\n'), QLatin1Char(','))
                           .replace(QLatin1Char(';'), QLatin1Char(','))
                           .replace(QLatin1Char('\t'), QLatin1Char(','));
  for (const QString& p : norm.split(QLatin1Char(','))) {
    const QString k = p.trimmed();
    if (!k.isEmpty() && !keys.contains(k)) keys << k;
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

void HostStrip::copyWatchKeys() {
  const QString line = watchKeys_.join(QLatin1Char(','));
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(line);
  if (chips_)
    chips_->setToolTip(
        line.isEmpty() ? QStringLiteral("监视键空 · Ctrl+Shift+K")
                       : QStringLiteral("已复制监视键 %1 · Ctrl+Shift+K").arg(watchKeys_.size()));
}


void HostStrip::keyPressEvent(QKeyEvent* event) {
  if (event && eventFilter(this, event)) return;
  QWidget::keyPressEvent(event);
}

}  // namespace sieans_qt

