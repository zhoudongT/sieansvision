#include "OperatorRail.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QToolButton>
#include <QPainter>
#include <QPixmap>
#include <QIcon>
#include <QPen>
#include <QPolygonF>
#include <cstring>

namespace sieans_qt {
namespace {

struct RailItem {
  const char* category;
  const char* tip;
  const char* kind;
};

const RailItem kItems[] = {
    {"相机采集", "图像采集（相机/本地）", "camera"},
    {"图像处理", "图像处理", "image"},
    {"定位与测量", "定位/匹配", "locate"},
    {"识别", "识别 / OCR", "ocr"},
    {"3D 点云", "3D / 点云", "cloud"},
    {"流程控制", "逻辑 / 流程", "logic"},
    {"工业通信", "通信", "comm"},
    {"变量与数据", "变量与数据", "var"},
    {"扩展算子", "扩展", "ext"},
};

QIcon railIcon(const char* kind, bool active) {
  const int size = 28;
  QPixmap pix(size, size);
  pix.fill(Qt::transparent);
  QPainter p(&pix);
  p.setRenderHint(QPainter::Antialiasing);
  QColor accent(active ? theme::ACCENT : theme::TEXT_MUTED);
  p.setPen(QPen(accent, 1.8, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
  p.setBrush(Qt::NoBrush);
  const qreal s = size;
  if (strcmp(kind, "camera") == 0) {
    p.drawRoundedRect(QRectF(5, 9, 18, 12), 2, 2);
    p.drawEllipse(QRectF(10, 11, 8, 8));
    p.drawRoundedRect(QRectF(18, 6, 5, 4), 1, 1);
  } else if (strcmp(kind, "image") == 0) {
    p.drawRect(QRectF(5, 6, 18, 16));
    p.drawLine(QPointF(5, 16), QPointF(12, 11));
    p.drawLine(QPointF(12, 11), QPointF(18, 17));
    p.drawEllipse(QRectF(16, 9, 4, 4));
  } else if (strcmp(kind, "locate") == 0) {
    p.drawEllipse(QRectF(7, 7, 14, 14));
    p.drawLine(QPointF(s / 2, 4), QPointF(s / 2, s - 4));
    p.drawLine(QPointF(4, s / 2), QPointF(s - 4, s / 2));
  } else if (strcmp(kind, "ocr") == 0) {
    p.drawRoundedRect(QRectF(5, 5, 18, 18), 2, 2);
    p.drawLine(QPointF(8, 11), QPointF(20, 11));
    p.drawLine(QPointF(8, 15), QPointF(17, 15));
    p.drawLine(QPointF(8, 19), QPointF(19, 19));
  } else if (strcmp(kind, "cloud") == 0) {
    QPolygonF poly;
    poly << QPointF(14, 4) << QPointF(22, 9) << QPointF(22, 19) << QPointF(14, 24)
         << QPointF(6, 19) << QPointF(6, 9);
    p.drawPolygon(poly);
  } else if (strcmp(kind, "logic") == 0) {
    QPolygonF poly;
    poly << QPointF(14, 4) << QPointF(24, 14) << QPointF(14, 24) << QPointF(4, 14);
    p.drawPolygon(poly);
  } else if (strcmp(kind, "comm") == 0) {
    p.drawEllipse(QRectF(6, 6, 7, 7));
    p.drawEllipse(QRectF(15, 15, 7, 7));
    p.drawLine(QPointF(12, 12), QPointF(16, 16));
  } else if (strcmp(kind, "var") == 0) {
    p.drawText(pix.rect(), Qt::AlignCenter, QStringLiteral("x"));
  } else {
    p.drawRoundedRect(QRectF(6, 6, 16, 16), 3, 3);
    p.drawText(pix.rect(), Qt::AlignCenter, QStringLiteral("+"));
  }
  p.end();
  return QIcon(pix);
}

}  // namespace

OperatorRail::OperatorRail(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("operatorRail"));
  setFixedWidth(44);
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(2, 6, 2, 6);
  lay->setSpacing(2);
  group_ = new QButtonGroup(this);
  group_->setExclusive(true);

  auto* allBtn = new QToolButton;
  allBtn->setCheckable(true);
  allBtn->setChecked(true);
  allBtn->setToolTip(QStringLiteral("全部算子"));
  allBtn->setIcon(railIcon("ext", true));
  allBtn->setIconSize(QSize(28, 28));
  allBtn->setAutoRaise(true);
  allBtn->setFixedSize(40, 36);
  allBtn->setProperty("railCategory", QString());
  group_->addButton(allBtn, 0);
  lay->addWidget(allBtn, 0, Qt::AlignHCenter);

  int id = 1;
  for (const auto& it : kItems) {
    auto* btn = new QToolButton;
    btn->setCheckable(true);
    btn->setToolTip(QString::fromUtf8(it.tip));
    btn->setIcon(railIcon(it.kind, false));
    btn->setIconSize(QSize(28, 28));
    btn->setAutoRaise(true);
    btn->setFixedSize(40, 36);
    btn->setProperty("railCategory", QString::fromUtf8(it.category));
    btn->setProperty("railKind", QString::fromUtf8(it.kind));
    group_->addButton(btn, id++);
    lay->addWidget(btn, 0, Qt::AlignHCenter);
  }
  lay->addStretch(1);

  connect(group_, &QButtonGroup::idClicked, this, [this](int) {
    auto* btn = group_->checkedButton();
    if (!btn) return;
    const QString cat = btn->property("railCategory").toString();
    // refresh icons active state
    for (auto* b : group_->buttons()) {
      auto* tb = qobject_cast<QToolButton*>(b);
      if (!tb) continue;
      const QString kind = tb->property("railKind").toString();
      const QString k = kind.isEmpty() ? QStringLiteral("ext") : kind;
      tb->setIcon(railIcon(k.toUtf8().constData(), tb->isChecked()));
    }
    emit categorySelected(cat);
  });
}

}  // namespace sieans_qt
