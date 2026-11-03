#include "HostStrip.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>

namespace sieans_qt {

HostStrip::HostStrip(QWidget* parent) : QWidget(parent) {
  setStatusTip(QStringLiteral("Host 条 · OK/NG/ALARM · tcp= 摘要"));
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(8, 4, 8, 4);
  root->setSpacing(2);
  auto* row = new QHBoxLayout;
  row->setSpacing(8);
  badge_ = new QLabel(QStringLiteral("—"));
  badge_->setFixedWidth(72);
  badge_->setAlignment(Qt::AlignCenter);
  badge_->setToolTip(QStringLiteral("OK/NG/ALARM · passGate 判定"));
  badge_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "font-weight:700;font-size:14px;padding:4px;"));
  modeChip_ = new QLabel(QStringLiteral("设计态"));
  modeChip_->setToolTip(QStringLiteral("运行模式 · 设计态/运行/连续/暂停"));
  modeChip_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "padding:3px 8px;font-size:11px;font-weight:600;"));
  cycleChip_ = new QLabel(QStringLiteral("周期 0"));
  cycleChip_->setToolTip(QStringLiteral("运行周期计数"));
  cycleChip_->setStyleSheet(
      QStringLiteral("background:#32353a;color:#a8a8a8;border-radius:3px;"
                     "padding:3px 8px;font-size:11px;"));
  detail_ = new QLabel(QStringLiteral("Host · 等待运行"));
  detail_->setObjectName(QStringLiteral("muted"));
  detail_->setToolTip(QStringLiteral("count/text/RX/urlOk/tcp 摘要"));
  alarmLabel_ = new QLabel;
  alarmLabel_->setVisible(false);
  alarmLabel_->setToolTip(QStringLiteral("报警锁存 · Host 清报警解除"));
  alarmLabel_->setStyleSheet(
      QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                     "font-weight:700;padding:2px 8px;"));
  row->addWidget(badge_);
  row->addWidget(modeChip_);
  row->addWidget(cycleChip_);
  row->addWidget(detail_, 1);
  row->addWidget(alarmLabel_);
  root->addLayout(row);
  chips_ = new QLabel;
  chips_->setObjectName(QStringLiteral("muted"));
  chips_->setWordWrap(true);
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
  const bool run = mode.contains(QStringLiteral("运行")) || mode.contains(QStringLiteral("连续")) ||
                   mode.contains(QStringLiteral("暂停"));
  modeChip_->setText(QStringLiteral("%1 · %2").arg(mode, hostState.isEmpty() ? QStringLiteral("Idle")
                                                                          : hostState));
  modeChip_->setStyleSheet(
      run ? QStringLiteral("background:#1e3d2f;color:#3ecf8e;border-radius:3px;"
                           "padding:3px 8px;font-size:11px;font-weight:600;")
          : QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                           "padding:3px 8px;font-size:11px;font-weight:600;"));
  cycleChip_->setText(QStringLiteral("周期 %1").arg(cycle));
}

void HostStrip::refreshChips(const QVariantMap& vars) {
  if (watchKeys_.isEmpty()) {
    chips_->setText({});
    return;
  }
  QStringList parts;
  for (const QString& k : watchKeys_) {
    parts << QStringLiteral("%1=%2").arg(k, vars.value(k).toString().left(24));
  }
  // also surface bound I/O output names if present
  for (auto it = vars.begin(); it != vars.end(); ++it) {
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
  detail_->setText(detail);
  refreshChips(vars);
}

}  // namespace sieans_qt
