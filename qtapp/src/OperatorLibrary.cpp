#include "OperatorLibrary.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QHash>
#include <QDrag>
#include <QMimeData>
#include <QLineEdit>
#include <QListWidget>
#include <QPainter>
#include <QPixmap>
#include <QIcon>
#include <QPen>
#include <QPolygonF>
#include <cstring>

namespace sieans_qt {
namespace {

class OperatorListWidget : public QListWidget {
 public:
  using QListWidget::QListWidget;
 protected:
  void startDrag(Qt::DropActions) override {
    QListWidgetItem* item = currentItem();
    if (!item) return;
    const QString key = item->data(Qt::UserRole).toString();
    if (key.isEmpty()) return;
    auto* mime = new QMimeData;
    mime->setData(QStringLiteral("application/x-sieans-operator"), key.toUtf8());
    mime->setText(key);
    QDrag drag(this);
    drag.setMimeData(mime);
    drag.setPixmap(item->icon().pixmap(36, 28));
    drag.exec(Qt::CopyAction, Qt::CopyAction);
  }
};

const char* glyphKindFor(const QString& key, const QString& category) {
  if (key == QLatin1String("camera_capture")) return "camera";
  if (key == QLatin1String("preprocess") || key == QLatin1String("save_image")) return "image";
  if (key == QLatin1String("locate")) return "locate";
  if (key == QLatin1String("barcode") || key == QLatin1String("qr_decode")) return "ocr";
  if (key == QLatin1String("send_data") || key == QLatin1String("receive_data")) return "comm";
  if (key == QLatin1String("var_calc") || key == QLatin1String("format_data") ||
      key == QLatin1String("result_gate"))
    return "var";
  if (category.contains(QStringLiteral("3D"))) return "cloud";
  if (category.contains(QStringLiteral("流程"))) return "logic";
  return "ext";
}

QIcon opGlyph(const char* kind, const QColor& accent) {
  const int w = 36, h = 28;
  QPixmap pix(w, h);
  pix.fill(Qt::transparent);
  QPainter p(&pix);
  p.setRenderHint(QPainter::Antialiasing);
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(theme::CARD));
  p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 3, 3);
  p.setPen(QPen(accent, 1.6, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
  p.setBrush(Qt::NoBrush);
  const qreal cx = w / 2.0, cy = h / 2.0;
  if (std::strcmp(kind, "camera") == 0) {
    p.drawRoundedRect(QRectF(8, 8, 18, 12), 2, 2);
    p.drawEllipse(QRectF(13, 10, 8, 8));
    p.drawRoundedRect(QRectF(21, 5, 5, 4), 1, 1);
  } else if (std::strcmp(kind, "image") == 0) {
    p.drawRect(QRectF(8, 6, 20, 16));
    p.drawLine(QPointF(8, 16), QPointF(15, 11));
    p.drawLine(QPointF(15, 11), QPointF(22, 18));
    p.drawEllipse(QRectF(22, 8, 4, 4));
  } else if (std::strcmp(kind, "locate") == 0) {
    p.drawEllipse(QRectF(cx - 8, cy - 8, 16, 16));
    p.drawLine(QPointF(cx, 4), QPointF(cx, h - 4));
    p.drawLine(QPointF(4, cy), QPointF(w - 4, cy));
  } else if (std::strcmp(kind, "ocr") == 0) {
    p.drawRoundedRect(QRectF(8, 5, 20, 18), 2, 2);
    p.drawLine(QPointF(11, 10), QPointF(25, 10));
    p.drawLine(QPointF(11, 14), QPointF(22, 14));
    p.drawLine(QPointF(11, 18), QPointF(24, 18));
  } else if (std::strcmp(kind, "cloud") == 0) {
    QPolygonF poly;
    poly << QPointF(cx, 4) << QPointF(28, 10) << QPointF(28, 18) << QPointF(cx, 24)
         << QPointF(8, 18) << QPointF(8, 10);
    p.drawPolygon(poly);
  } else if (std::strcmp(kind, "logic") == 0) {
    QPolygonF poly;
    poly << QPointF(cx, 4) << QPointF(28, cy) << QPointF(cx, h - 4) << QPointF(8, cy);
    p.drawPolygon(poly);
  } else if (std::strcmp(kind, "comm") == 0) {
    p.drawEllipse(QRectF(8, 6, 8, 8));
    p.drawEllipse(QRectF(20, 14, 8, 8));
    p.drawLine(QPointF(15, 12), QPointF(21, 16));
  } else if (std::strcmp(kind, "var") == 0) {
    QFont f = p.font();
    f.setBold(true);
    f.setPointSize(11);
    p.setFont(f);
    p.drawText(pix.rect(), Qt::AlignCenter, QStringLiteral("x"));
  } else {
    p.drawRoundedRect(QRectF(9, 6, 18, 16), 3, 3);
    p.drawText(pix.rect(), Qt::AlignCenter, QStringLiteral("+"));
  }
  p.end();
  return QIcon(pix);
}

}  // namespace

QVector<OperatorDef> OperatorLibrary::catalog() {
  return {
      {QStringLiteral("camera_capture"), QStringLiteral("相机采集"),
       QStringLiteral("相机采集"), QStringLiteral("GenTL / UVC 采集")},
      {QStringLiteral("preprocess"), QStringLiteral("图像预处理"),
       QStringLiteral("图像处理"), QStringLiteral("灰度 / 反色 / 阈值（QImage）")},
      {QStringLiteral("locate"), QStringLiteral("快速匹配"),
       QStringLiteral("定位与测量"), QStringLiteral("从当前图中心建模板并搜索")},
      {QStringLiteral("save_image"), QStringLiteral("保存图像"),
       QStringLiteral("图像处理"), QStringLiteral("运行时落盘（可选）")},
      {QStringLiteral("barcode"), QStringLiteral("条码 / 二维码"),
       QStringLiteral("识别"), QStringLiteral("C++ zxing 解码")},
      {QStringLiteral("var_calc"), QStringLiteral("变量计算"),
       QStringLiteral("变量与数据"), QStringLiteral("表达式求值 / OK-NG")},
      {QStringLiteral("format_data"), QStringLiteral("格式化数据"),
       QStringLiteral("变量与数据"), QStringLiteral("报文模板 {0}{1}…")},
      {QStringLiteral("result_gate"), QStringLiteral("结果门限 OK/NG"),
       QStringLiteral("变量与数据"), QStringLiteral("passGate 门限")},
      {QStringLiteral("send_data"), QStringLiteral("发送数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus TX")},
      {QStringLiteral("receive_data"), QStringLiteral("接收数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus RX → 变量")},
  };
}

OperatorDef OperatorLibrary::findDef(const QString& key) {
  for (const auto& d : catalog())
    if (d.key == key) return d;
  return {key, key, QStringLiteral("其它"), {}};
}

OperatorLibrary::OperatorLibrary(QWidget* parent) : QWidget(parent) {
  setObjectName(QStringLiteral("libraryPane"));
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  lay->setSpacing(0);
  auto* title = new QLabel(QStringLiteral("算子"));
  title->setObjectName(QStringLiteral("libraryTitle"));
  lay->addWidget(title);
  search_ = new QLineEdit;
  search_->setObjectName(QStringLiteral("operatorSearch"));
  search_->setPlaceholderText(QStringLiteral("搜索…"));
  search_->setClearButtonEnabled(true);
  lay->addWidget(search_);
  list_ = new OperatorListWidget;
  list_->setSpacing(1);
  list_->setDragEnabled(true);
  list_->setDragDropMode(QAbstractItemView::DragOnly);
  list_->setDefaultDropAction(Qt::CopyAction);
  list_->setIconSize(QSize(36, 28));
  list_->setUniformItemSizes(true);
  list_->setObjectName(QStringLiteral("operatorTiles"));
  lay->addWidget(list_, 1);
  connect(list_, &QListWidget::itemDoubleClicked, this,
          [this](QListWidgetItem* item) {
            if (!item || item->data(Qt::UserRole).toString().isEmpty()) return;
            emit operatorActivated(item->data(Qt::UserRole).toString(),
                                   item->data(Qt::UserRole + 1).toString());
          });
  connect(search_, &QLineEdit::textChanged, this, [this](const QString&) { rebuild(); });
  rebuild();
}

void OperatorLibrary::setCategoryFilter(const QString& category) {
  categoryFilter_ = category;
  rebuild();
}

void OperatorLibrary::rebuild() {
  list_->clear();
  const QString q = search_ ? search_->text().trimmed() : QString();
  QHash<QString, QColor> catColor{
      {QStringLiteral("相机采集"), QColor(theme::ACCENT)},
      {QStringLiteral("图像处理"), QColor(QStringLiteral("#3b9db8"))},
      {QStringLiteral("定位与测量"), QColor(theme::OK)},
      {QStringLiteral("识别"), QColor(QStringLiteral("#8a6bc8"))},
      {QStringLiteral("工业通信"), QColor(QStringLiteral("#b8893d"))},
      {QStringLiteral("变量与数据"), QColor(QStringLiteral("#6a8090"))},
      {QStringLiteral("流程控制"), QColor(QStringLiteral("#6a7a90"))},
      {QStringLiteral("3D 点云"), QColor(QStringLiteral("#4a7fc5"))},
  };
  QString lastCat;
  for (const auto& def : catalog()) {
    if (!categoryFilter_.isEmpty() && def.category != categoryFilter_) continue;
    if (!q.isEmpty() && !def.name.contains(q, Qt::CaseInsensitive) &&
        !def.key.contains(q, Qt::CaseInsensitive) &&
        !def.category.contains(q, Qt::CaseInsensitive))
      continue;
    if (def.category != lastCat) {
      lastCat = def.category;
      auto* hdr = new QListWidgetItem(QStringLiteral("▾ %1").arg(def.category));
      hdr->setFlags(Qt::ItemIsEnabled);
      hdr->setForeground(QColor(theme::TEXT));
      hdr->setBackground(QColor(theme::CARD));
      QFont f = hdr->font();
      f.setBold(true);
      f.setPointSize(10);
      hdr->setFont(f);
      list_->addItem(hdr);
    }
    const QColor accent = catColor.value(def.category, QColor(theme::ACCENT));
    const char* kind = glyphKindFor(def.key, def.category);
    auto* item = new QListWidgetItem(opGlyph(kind, accent), def.name);
    item->setData(Qt::UserRole, def.key);
    item->setData(Qt::UserRole + 1, def.name);
    item->setToolTip(QStringLiteral("[%1] %2 · 拖到画布").arg(def.category, def.tip));
    item->setForeground(accent);
    item->setSizeHint(QSize(0, 32));
    list_->addItem(item);
  }
  if (list_->count() == 0) {
    auto* empty = new QListWidgetItem(QStringLiteral("（无匹配算子）"));
    empty->setFlags(Qt::NoItemFlags);
    empty->setForeground(QColor(theme::TEXT_DIM));
    list_->addItem(empty);
  }
}

}  // namespace sieans_qt
