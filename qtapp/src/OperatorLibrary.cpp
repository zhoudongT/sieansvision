#include "OperatorLibrary.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QHash>
#include <QDrag>
#include <QMimeData>
#include <QApplication>

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
    setCursor(Qt::ClosedHandCursor);
    drag.exec(Qt::CopyAction, Qt::CopyAction);
    setCursor(Qt::ArrowCursor);
  }
};

}  // namespace

QVector<OperatorDef> OperatorLibrary::catalog() {
  return {
      {QStringLiteral("camera_capture"), QStringLiteral("相机采集"),
       QStringLiteral("相机采集"), QStringLiteral("GenTL / UVC 采集")},
      {QStringLiteral("preprocess"), QStringLiteral("图像预处理"),
       QStringLiteral("图像处理"), QStringLiteral("灰度 / 反色 / 阈值（QImage）")},
      {QStringLiteral("barcode"), QStringLiteral("条码 / 二维码"),
       QStringLiteral("识别"), QStringLiteral("C++ zxing 解码")},
      {QStringLiteral("var_calc"), QStringLiteral("变量计算"),
       QStringLiteral("变量与数据"), QStringLiteral("表达式求值 / OK-NG")},
      {QStringLiteral("format_data"), QStringLiteral("格式化数据"),
       QStringLiteral("变量与数据"), QStringLiteral("报文模板 {0}{1}…")},
      {QStringLiteral("send_data"), QStringLiteral("发送数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus TX")},
      {QStringLiteral("receive_data"), QStringLiteral("接收数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus RX → 变量")},
      {QStringLiteral("result_gate"), QStringLiteral("结果门限 OK/NG"),
       QStringLiteral("变量与数据"), QStringLiteral("passGate 门限")},
      {QStringLiteral("save_image"), QStringLiteral("保存图像"),
       QStringLiteral("图像处理"), QStringLiteral("运行时落盘（可选）")},
  };
}

OperatorDef OperatorLibrary::findDef(const QString& key) {
  for (const auto& d : catalog())
    if (d.key == key) return d;
  return {key, key, QStringLiteral("其它"), {}};
}

OperatorLibrary::OperatorLibrary(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(4, 4, 4, 4);
  lay->setSpacing(4);
  auto* title = new QLabel(QStringLiteral("算子"));
  title->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title);
  auto* hint = new QLabel(QStringLiteral("双击或拖到画布"));
  hint->setObjectName(QStringLiteral("muted"));
  lay->addWidget(hint);

  list_ = new OperatorListWidget;
  list_->setSpacing(1);
  list_->setDragEnabled(true);
  list_->setDragDropMode(QAbstractItemView::DragOnly);
  list_->setDefaultDropAction(Qt::CopyAction);
  QHash<QString, QColor> catColor{
      {QStringLiteral("相机采集"), QColor(theme::ACCENT)},
      {QStringLiteral("图像处理"), QColor(QStringLiteral("#3b9db8"))},
      {QStringLiteral("定位与测量"), QColor(theme::OK)},
      {QStringLiteral("识别"), QColor(QStringLiteral("#8a6bc8"))},
      {QStringLiteral("工业通信"), QColor(QStringLiteral("#b8893d"))},
      {QStringLiteral("变量与数据"), QColor(QStringLiteral("#6a8090"))},
  };
  for (const auto& def : catalog()) {
    auto* item = new QListWidgetItem(QStringLiteral("● %1").arg(def.name));
    item->setData(Qt::UserRole, def.key);
    item->setData(Qt::UserRole + 1, def.name);
    item->setToolTip(QStringLiteral("[%1] %2 · 拖到画布").arg(def.category, def.tip));
    item->setForeground(catColor.value(def.category, QColor(theme::ACCENT)));
    list_->addItem(item);
  }
  lay->addWidget(list_, 1);
  connect(list_, &QListWidget::itemDoubleClicked, this,
          [this](QListWidgetItem* item) {
            if (!item) return;
            emit operatorActivated(item->data(Qt::UserRole).toString(),
                                   item->data(Qt::UserRole + 1).toString());
          });
}

}  // namespace sieans_qt
