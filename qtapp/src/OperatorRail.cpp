#include "OperatorRail.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QToolButton>
#include <QAbstractButton>
#include <QPainter>
#include <QPixmap>
#include <QIcon>
#include <QPen>
#include <QPolygonF>
#include <cstring>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QClipboard>
#include <QGuiApplication>
#include <QEvent>

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
  setStatusTip(QStringLiteral("Toolbox 分类轨 · ↑↓/←→/Home/End/PgUp/PgDn · Esc/A/0 全部"));
  setObjectName(QStringLiteral("operatorRail"));
  setFixedWidth(44);
  setFocusPolicy(Qt::StrongFocus);
  setToolTip(QStringLiteral("算子分类轨 · ↑↓/←→/Home/End/PgUp/PgDn · Esc/A/0 全部 · 点击筛选"));
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(2, 6, 2, 6);
  lay->setSpacing(2);
  group_ = new QButtonGroup(this);
  group_->setExclusive(true);

  auto* allBtn = new QToolButton;
  allBtn->setCheckable(true);
  allBtn->setChecked(true);
  allBtn->setToolTip(QStringLiteral("全部算子 · 清除分类筛选 · ↑↓ 切换"));
  allBtn->setStatusTip(QStringLiteral("Toolbox · 显示全部算子"));
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
    btn->setToolTip(QStringLiteral("%1 · %2 · 点击筛选")
                        .arg(QString::fromUtf8(it.category),
                             QString::fromUtf8(it.tip)));
    btn->setStatusTip(QStringLiteral("Toolbox · 筛选「%1」")
                          .arg(QString::fromUtf8(it.category)));
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
  installEventFilter(this);
  setFocusPolicy(Qt::StrongFocus);
  setStatusTip(QStringLiteral("Toolbox 轨 · ↑↓/Home/End · 1-9 跳分类 · Esc/0/A/中键 全部 · Ctrl+C 分类名"));
}

bool OperatorRail::eventFilter(QObject* obj, QEvent* event) {
  if (event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton && group_) {
      if (auto* b = group_->button(0)) {
        b->setChecked(true);
        for (auto* bb : group_->buttons()) {
          auto* tb = qobject_cast<QToolButton*>(bb);
          if (!tb) continue;
          const QString kind = tb->property("railKind").toString();
          const QString k = kind.isEmpty() ? QStringLiteral("ext") : kind;
          tb->setIcon(railIcon(k.toUtf8().constData(), tb->isChecked()));
        }
        emit categorySelected(QString());
      }
      return true;
    }
  }
  if (event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if ((ke->key() == Qt::Key_Escape || ke->key() == Qt::Key_A ||
         ke->key() == Qt::Key_0) &&
        group_) {
      // Esc → 全部 (first button / id 0)
      if (auto* b = group_->button(0)) {
        b->setChecked(true);
        for (auto* bb : group_->buttons()) {
          auto* tb = qobject_cast<QToolButton*>(bb);
          if (!tb) continue;
          const QString kind = tb->property("railKind").toString();
          const QString k = kind.isEmpty() ? QStringLiteral("ext") : kind;
          tb->setIcon(railIcon(k.toUtf8().constData(), tb->isChecked()));
        }
        emit categorySelected(QString());
      }
      return true;
    }
    if (ke->key() == Qt::Key_Up || ke->key() == Qt::Key_Down ||
        ke->key() == Qt::Key_Left || ke->key() == Qt::Key_Right ||
        ke->key() == Qt::Key_Home || ke->key() == Qt::Key_End ||
        ke->key() == Qt::Key_PageUp || ke->key() == Qt::Key_PageDown) {
      if (!group_) return QWidget::eventFilter(obj, event);
      const QList<QAbstractButton*> btns = group_->buttons();
      if (btns.isEmpty()) return true;
      int cur = group_->checkedId();
      if (cur < 0) cur = 0;
      int next = cur;
      if (ke->key() == Qt::Key_Home || ke->key() == Qt::Key_PageUp) next = 0;
      else if (ke->key() == Qt::Key_End || ke->key() == Qt::Key_PageDown)
        next = btns.size() - 1;
      else
        next = (ke->key() == Qt::Key_Up || ke->key() == Qt::Key_Left)
                           ? (cur - 1 + btns.size()) % btns.size()
                           : (cur + 1) % btns.size();
      if (auto* b = group_->button(next)) {
        b->setChecked(true);
        // mirror idClicked path
        for (auto* bb : group_->buttons()) {
          auto* tb = qobject_cast<QToolButton*>(bb);
          if (!tb) continue;
          const QString kind = tb->property("railKind").toString();
          const QString k = kind.isEmpty() ? QStringLiteral("ext") : kind;
          tb->setIcon(railIcon(k.toUtf8().constData(), tb->isChecked()));
        }
        emit categorySelected(b->property("railCategory").toString());
      }
      return true;
    }
    if (ke->key() == Qt::Key_C && (ke->modifiers() & Qt::ControlModifier) && group_) {
      if (auto* b = group_->checkedButton()) {
        const QString cat = b->property("railCategory").toString();
        const QString tip = b->toolTip();
        if (auto* clip = QGuiApplication::clipboard())
          clip->setText(cat.isEmpty() ? QStringLiteral("全部") : cat + QLatin1Char('\n') + tip);
      }
      return true;
    }
    if (ke->key() >= Qt::Key_1 && ke->key() <= Qt::Key_9 && group_) {
      const int want = ke->key() - Qt::Key_1;  // 0-based; 1→相机
      if (auto* b = group_->button(want)) {
        b->setChecked(true);
        for (auto* bb : group_->buttons()) {
          auto* tb = qobject_cast<QToolButton*>(bb);
          if (!tb) continue;
          const QString kind = tb->property("railKind").toString();
          const QString k = kind.isEmpty() ? QStringLiteral("ext") : kind;
          tb->setIcon(railIcon(k.toUtf8().constData(), tb->isChecked()));
        }
        emit categorySelected(b->property("railCategory").toString());
      }
      return true;
    }
  }
  return QWidget::eventFilter(obj, event);
}


}  // namespace sieans_qt
