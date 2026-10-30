#include "HostStrip.hpp"

#include "Theme.hpp"

#include <QHBoxLayout>

namespace sieans_qt {

HostStrip::HostStrip(QWidget* parent) : QWidget(parent) {
  setFixedHeight(36);
  auto* lay = new QHBoxLayout(this);
  lay->setContentsMargins(8, 4, 8, 4);
  lay->setSpacing(10);
  badge_ = new QLabel(QStringLiteral("—"));
  badge_->setFixedWidth(72);
  badge_->setAlignment(Qt::AlignCenter);
  badge_->setStyleSheet(
      QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                     "font-weight:700;font-size:14px;padding:4px;"));
  detail_ = new QLabel(QStringLiteral("Host · 等待运行"));
  detail_->setObjectName(QStringLiteral("muted"));
  lay->addWidget(badge_);
  lay->addWidget(detail_, 1);
  setStyleSheet(QStringLiteral("background:#232528;border-top:1px solid #4a4e54;"));
}

void HostStrip::updateFromVars(const QVariantMap& vars, int codeCount) {
  const bool ok = vars.value(QStringLiteral("passGate")).toInt() != 0 ||
                  vars.value(QStringLiteral("passGate")).toBool() ||
                  vars.value(QStringLiteral("barcodeOk")).toInt() != 0 ||
                  vars.value(QStringLiteral("barcodeOk")).toBool();
  const int count = codeCount >= 0
                        ? codeCount
                        : vars.value(QStringLiteral("barcodeCount")).toInt();
  const QString text = vars.value(QStringLiteral("barcodeText")).toString();
  if (ok) {
    badge_->setText(QStringLiteral("OK"));
    badge_->setStyleSheet(
        QStringLiteral("background:#2d9b6c;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else if (count == 0 && text.isEmpty() &&
             !vars.contains(QStringLiteral("barcodeCount"))) {
    badge_->setText(QStringLiteral("—"));
    badge_->setStyleSheet(
        QStringLiteral("background:#3a3d42;color:#a8a8a8;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  } else {
    badge_->setText(QStringLiteral("NG"));
    badge_->setStyleSheet(
        QStringLiteral("background:#e53935;color:#fff;border-radius:3px;"
                       "font-weight:700;font-size:14px;padding:4px;"));
  }
  detail_->setText(QStringLiteral("count=%1 · text=%2 · formatted=%3")
                       .arg(count)
                       .arg(text.left(48))
                       .arg(vars.value(QStringLiteral("formatted")).toString().left(48)));
}

}  // namespace sieans_qt
