#include "OperatorLibrary.hpp"

#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QHash>

namespace sieans_qt {

QVector<OperatorDef> OperatorLibrary::catalog() {
  return {
      {QStringLiteral("camera_capture"), QStringLiteral("相机采集"),
       QStringLiteral("相机采集"), QStringLiteral("GenTL / UVC 采集")},
      {QStringLiteral("barcode"), QStringLiteral("条码 / 二维码"),
       QStringLiteral("识别"), QStringLiteral("C++ zxing 解码")},
      {QStringLiteral("var_calc"), QStringLiteral("变量计算"),
       QStringLiteral("变量与数据"), QStringLiteral("表达式 / OK-NG")},
      {QStringLiteral("format_data"), QStringLiteral("格式化数据"),
       QStringLiteral("变量与数据"), QStringLiteral("报文模板")},
      {QStringLiteral("send_data"), QStringLiteral("发送数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus")},
      {QStringLiteral("ocr"), QStringLiteral("OCR 字符识别"),
       QStringLiteral("识别"), QStringLiteral("后续波次")},
      {QStringLiteral("caliper"), QStringLiteral("卡尺测量"),
       QStringLiteral("定位与测量"), QStringLiteral("后续波次")},
      {QStringLiteral("preprocess"), QStringLiteral("图像预处理"),
       QStringLiteral("图像处理"), QStringLiteral("后续波次")},
  };
}

OperatorLibrary::OperatorLibrary(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(4, 4, 4, 4);
  lay->setSpacing(4);
  auto* title = new QLabel(QStringLiteral("算子"));
  title->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title);

  list_ = new QListWidget;
  list_->setSpacing(1);
  QHash<QString, QColor> catColor{
      {QStringLiteral("相机采集"), QColor(theme::ACCENT)},
      {QStringLiteral("图像处理"), QColor(QStringLiteral("#3b9db8"))},
      {QStringLiteral("定位与测量"), QColor(theme::OK)},
      {QStringLiteral("识别"), QColor(QStringLiteral("#8a6bc8"))},
      {QStringLiteral("工业通信"), QColor(QStringLiteral("#b8893d"))},
      {QStringLiteral("变量与数据"), QColor(QStringLiteral("#6a8090"))},
  };
  for (const auto& def : catalog()) {
    auto* item = new QListWidgetItem(
        QStringLiteral("● %1").arg(def.name));
    item->setData(Qt::UserRole, def.key);
    item->setData(Qt::UserRole + 1, def.name);
    item->setToolTip(QStringLiteral("[%1] %2").arg(def.category, def.tip));
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
