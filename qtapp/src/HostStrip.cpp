#include "HostStrip.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QHBoxLayout>

namespace sieans_qt {

HostStrip::HostStrip(QWidget* parent) : QWidget(parent) {
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(8, 4, 8, 4);
  root->setSpacing(2);
  auto* row = new QHBoxLayout;
  row->setSpacing(10);
  badge_ = new QLabel(QStringLiteral("—"));
  badge_->setFixedWidth(72);
  badge_->setAlignment(Qt::AlignCenter);
  badge_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "font-weight:700;font-size:14px;padding:4px;"));
  detail_ = new QLabel(QStringLiteral("Host · 等待运行"));
  detail_->setObjectName(QStringLiteral("muted"));
  alarmLabel_ = new QLabel;
  alarmLabel_->setVisible(false);
  alarmLabel_->setStyleSheet(
      QStringLiteral("background:#c62828;color:#fff;border-radius:3px;"
                     "font-weight:700;padding:2px 8px;"));
  row->addWidget(badge_);
  row->addWidget(detail_, 1);
  row->addWidget(alarmLabel_);
  root->addLayout(row);
  chips_ = new QLabel;
  chips_->setObjectName(QStringLiteral("muted"));
  chips_->setWordWrap(true);
  root->addWidget(chips_);
  setStyleSheet(QStringLiteral("background:#232528;border-top:1px solid #4a4e54;"));
  setMinimumHeight(48);
}

void HostStrip::setWatchKeys(const QStringList& keys) { watchKeys_ = keys; }

void HostStrip::setAlarm(bool on, const QString& reason) {
  alarmOn_ = on;
  alarmReason_ = reason;
  alarmLabel_->setVisible(on);
  alarmLabel_->setText(on ? QStringLiteral("ALARM %1").arg(reason.left(40))
                          : QString());
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
  chips_->setText(parts.join(QStringLiteral("  ·  ")));
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
  detail_->setText(detail);
  refreshChips(vars);
}

}  // namespace sieans_qt
