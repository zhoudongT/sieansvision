#include "OperatorLibrary.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QHash>
#include <QDrag>
#include <QMimeData>
#include <QLineEdit>
#include <QListWidget>

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
    drag.exec(Qt::CopyAction, Qt::CopyAction);
  }
};

}  // namespace

QVector<OperatorDef> OperatorLibrary::catalog() {
  return {
      {QStringLiteral("camera_capture"), QStringLiteral("相机采集"),
       QStringLiteral("相机采集"), QStringLiteral("GenTL / UVC 采集")},
      {QStringLiteral("preprocess"), QStringLiteral("图像预处理"),
       QStringLiteral("图像处理"), QStringLiteral("灰度 / 反色 / 阈值（QImage）")},
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
    auto* item = new QListWidgetItem(QStringLiteral("  ● %1").arg(def.name));
    item->setData(Qt::UserRole, def.key);
    item->setData(Qt::UserRole + 1, def.name);
    item->setToolTip(QStringLiteral("[%1] %2 · 拖到画布").arg(def.category, def.tip));
    item->setForeground(catColor.value(def.category, QColor(theme::ACCENT)));
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
