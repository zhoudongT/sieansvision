#include "OperatorLibrary.hpp"
#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QHBoxLayout>
#include <QPushButton>
#include <QHash>
#include <QDrag>
#include <QMimeData>
#include <QLineEdit>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QClipboard>
#include <QGuiApplication>
#include <QEvent>
#include <QListWidget>
#include <QPainter>
#include <QPixmap>
#include <QIcon>
#include <QPen>
#include <QPolygonF>
#include <QRect>
#include <QColor>
#include <QFont>
#include <QPoint>
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
    // VM-ish drag chrome: icon + operator title
    const QString title = item->text().section(QLatin1Char('\n'), 0, 0);
    QPixmap tip(148, 36);
    tip.fill(QColor(QStringLiteral("#2a2d32")));
    QPainter p(&tip);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(QColor(QStringLiteral("#e67a2e")));
    p.drawRoundedRect(0.5, 0.5, 147, 35, 4, 4);
    const QPixmap ic = item->icon().pixmap(28, 22);
    if (!ic.isNull()) p.drawPixmap(6, 7, ic);
    p.setPen(QColor(QStringLiteral("#f0e6dc")));
    p.setFont(QFont(QStringLiteral("Sans"), 10, QFont::DemiBold));
    p.drawText(QRect(38, 0, 104, 36), Qt::AlignVCenter | Qt::AlignLeft,
               title.left(14));
    p.end();
    QDrag drag(this);
    drag.setMimeData(mime);
    drag.setPixmap(tip);
    drag.setHotSpot(QPoint(16, 18));
    drag.exec(Qt::CopyAction, Qt::CopyAction);
  }
};

const char* glyphKindFor(const QString& key, const QString& category) {
  if (key == QLatin1String("camera_capture")) return "camera";
  if (key == QLatin1String("preprocess")) return "image";
  if (key == QLatin1String("save_image")) return "save";
  if (key == QLatin1String("locate")) return "locate";
  if (key == QLatin1String("caliper") || key == QLatin1String("measure")) return "caliper";
  if (key == QLatin1String("geometry")) return "geometry";
  if (key == QLatin1String("barcode") || key == QLatin1String("qr_decode")) return "barcode";
  if (key == QLatin1String("ocr")) return "ocr";
  if (key == QLatin1String("send_data")) return "tx";
  if (key == QLatin1String("receive_data")) return "rx";
  if (key == QLatin1String("serial_exchange")) return "serial";
  if (key == QLatin1String("modbus_read")) return "mbread";
  if (key == QLatin1String("modbus_write")) return "mbwrite";
  if (key == QLatin1String("modbus_wait")) return "mbwait";
  if (key == QLatin1String("s7_read") || key == QLatin1String("s7_write")) return "s7";
  if (key == QLatin1String("opcua_read") || key == QLatin1String("opcua_write") ||
      key == QLatin1String("opcua_browse") || key == QLatin1String("opcua_wait"))
    return "opcua";
  if (key == QLatin1String("result_gate")) return "gate";
  if (key == QLatin1String("format_data")) return "format";
  if (key == QLatin1String("var_calc")) return "var";
  if (key == QLatin1String("condition")) return "condition";
  if (key == QLatin1String("branch")) return "branch";
  if (key == QLatin1String("branch_merge")) return "merge";
  if (category.contains(QStringLiteral("3D"))) return "cloud";
  if (category.contains(QStringLiteral("流程"))) return "logic";
  return "ext";
}

QIcon opGlyph(const char* kind, const QColor& accent) {
  const int w = 32, h = 24;
  QPixmap pix(w, h);
  pix.fill(Qt::transparent);
  QPainter p(&pix);
  p.setRenderHint(QPainter::Antialiasing);
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(theme::CARD));
  p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 3, 3);
  // left accent rail (VM toolbox density cue)
  p.setBrush(accent);
  p.drawRoundedRect(QRectF(1, 2, 3, h - 4), 1, 1);
  p.setPen(QPen(accent, 1.5, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
  p.setBrush(Qt::NoBrush);
  const qreal cx = w / 2.0 + 1, cy = h / 2.0;
  if (std::strcmp(kind, "camera") == 0) {
    p.drawRoundedRect(QRectF(9, 7, 16, 11), 2, 2);
    p.drawEllipse(QRectF(13, 9, 7, 7));
    p.drawRoundedRect(QRectF(20, 4, 4, 3), 1, 1);
  } else if (std::strcmp(kind, "image") == 0) {
    p.drawRect(QRectF(9, 5, 17, 14));
    p.drawLine(QPointF(9, 14), QPointF(15, 9));
    p.drawLine(QPointF(15, 9), QPointF(21, 16));
    p.drawEllipse(QRectF(20, 7, 3.5, 3.5));
  } else if (std::strcmp(kind, "save") == 0) {
    p.drawRoundedRect(QRectF(10, 5, 14, 14), 1, 1);
    p.drawRect(QRectF(13, 5, 8, 5));
    p.drawLine(QPointF(12, 14), QPointF(22, 14));
  } else if (std::strcmp(kind, "locate") == 0) {
    p.drawEllipse(QRectF(cx - 7, cy - 7, 14, 14));
    p.drawLine(QPointF(cx, 3), QPointF(cx, h - 3));
    p.drawLine(QPointF(6, cy), QPointF(w - 3, cy));
  } else if (std::strcmp(kind, "caliper") == 0) {
    p.drawLine(QPointF(10, 6), QPointF(10, 18));
    p.drawLine(QPointF(24, 6), QPointF(24, 18));
    p.drawLine(QPointF(10, cy), QPointF(24, cy));
    p.drawLine(QPointF(12, cy - 2), QPointF(10, cy));
    p.drawLine(QPointF(12, cy + 2), QPointF(10, cy));
    p.drawLine(QPointF(22, cy - 2), QPointF(24, cy));
    p.drawLine(QPointF(22, cy + 2), QPointF(24, cy));
  } else if (std::strcmp(kind, "barcode") == 0) {
    for (int i = 0; i < 7; ++i) {
      const qreal x = 10 + i * 2.4;
      if (i % 2 == 0) p.drawLine(QPointF(x, 5), QPointF(x, 19));
    }
    p.drawRect(QRectF(20, 6, 7, 7));
  } else if (std::strcmp(kind, "ocr") == 0) {
    p.drawRoundedRect(QRectF(9, 4, 17, 16), 2, 2);
    p.drawLine(QPointF(11, 9), QPointF(23, 9));
    p.drawLine(QPointF(11, 12), QPointF(20, 12));
    p.drawLine(QPointF(11, 15), QPointF(22, 15));
  } else if (std::strcmp(kind, "cloud") == 0) {
    QPolygonF poly;
    poly << QPointF(cx, 3) << QPointF(26, 9) << QPointF(26, 16) << QPointF(cx, 21)
         << QPointF(9, 16) << QPointF(9, 9);
    p.drawPolygon(poly);
  } else if (std::strcmp(kind, "logic") == 0) {
    QPolygonF poly;
    poly << QPointF(cx, 3) << QPointF(26, cy) << QPointF(cx, h - 3) << QPointF(9, cy);
    p.drawPolygon(poly);
  } else if (std::strcmp(kind, "comm") == 0 || std::strcmp(kind, "tx") == 0) {
    p.drawEllipse(QRectF(9, 5, 7, 7));
    p.drawLine(QPointF(16, 10), QPointF(22, 15));
    QPolygonF arrow;
    arrow << QPointF(20, 12) << QPointF(26, 16) << QPointF(19, 18);
    p.setBrush(accent);
    p.drawPolygon(arrow);
    p.setBrush(Qt::NoBrush);
  } else if (std::strcmp(kind, "rx") == 0) {
    p.drawEllipse(QRectF(18, 12, 7, 7));
    p.drawLine(QPointF(12, 8), QPointF(19, 14));
    QPolygonF arrow;
    arrow << QPointF(14, 5) << QPointF(9, 9) << QPointF(15, 11);
    p.setBrush(accent);
    p.drawPolygon(arrow);
    p.setBrush(Qt::NoBrush);
  } else if (std::strcmp(kind, "gate") == 0) {
    p.drawRoundedRect(QRectF(10, 5, 14, 14), 2, 2);
    p.drawLine(QPointF(13, 9), QPointF(21, 9));
    p.drawLine(QPointF(13, 12), QPointF(18, 12));
    p.drawLine(QPointF(13, 15), QPointF(20, 15));
    p.drawEllipse(QRectF(19, 13, 4, 4));
  } else if (std::strcmp(kind, "format") == 0) {
    p.drawLine(QPointF(10, 6), QPointF(24, 6));
    p.drawLine(QPointF(10, 12), QPointF(20, 12));
    p.drawLine(QPointF(10, 18), QPointF(24, 18));
    p.drawText(QRectF(18, 8, 10, 10), Qt::AlignCenter, QStringLiteral("{}"));
  } else if (std::strcmp(kind, "var") == 0) {
    QFont f = p.font();
    f.setBold(true);
    f.setPointSize(10);
    p.setFont(f);
    p.drawText(QRectF(6, 0, w - 6, h), Qt::AlignCenter, QStringLiteral("x"));
  } else if (std::strcmp(kind, "condition") == 0) {
    QPolygonF poly;
    poly << QPointF(cx, 3) << QPointF(26, cy) << QPointF(cx, h - 3) << QPointF(9, cy);
    p.drawPolygon(poly);
    QFont f = p.font();
    f.setBold(true);
    f.setPointSize(8);
    p.setFont(f);
    p.drawText(QRectF(6, 0, w - 4, h), Qt::AlignCenter, QStringLiteral("?"));
  } else if (std::strcmp(kind, "branch") == 0) {
    p.drawLine(QPointF(10, cy), QPointF(16, cy));
    p.drawLine(QPointF(16, cy), QPointF(24, 7));
    p.drawLine(QPointF(16, cy), QPointF(24, 17));
    p.drawLine(QPointF(10, 6), QPointF(10, 18));
  } else if (std::strcmp(kind, "geometry") == 0) {
    p.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12));
    p.drawLine(QPointF(9, 18), QPointF(25, 7));
    p.drawPoint(QPointF(cx, cy));
  } else if (std::strcmp(kind, "merge") == 0) {
    QPolygonF bow;
    bow << QPointF(10, 5) << QPointF(cx, cy) << QPointF(24, 5);
    p.drawPolyline(bow);
    QPolygonF bow2;
    bow2 << QPointF(10, 19) << QPointF(cx, cy) << QPointF(24, 19);
    p.drawPolyline(bow2);
  } else if (std::strcmp(kind, "serial") == 0) {
    p.drawRoundedRect(QRectF(9, 6, 16, 12), 2, 2);
    p.drawLine(QPointF(9, 9), QPointF(6, 9));
    p.drawLine(QPointF(9, 15), QPointF(6, 15));
    p.drawLine(QPointF(25, 9), QPointF(28, 9));
    p.drawLine(QPointF(25, 15), QPointF(28, 15));
    p.drawLine(QPointF(13, 10), QPointF(21, 10));
    p.drawLine(QPointF(13, 14), QPointF(18, 14));
  } else if (std::strcmp(kind, "mbread") == 0) {
    p.drawRoundedRect(QRectF(10, 5, 14, 14), 2, 2);
    p.drawText(QRectF(10, 5, 14, 14), Qt::AlignCenter, QStringLiteral("R"));
  } else if (std::strcmp(kind, "mbwrite") == 0) {
    p.drawRoundedRect(QRectF(10, 5, 14, 14), 2, 2);
    p.drawText(QRectF(10, 5, 14, 14), Qt::AlignCenter, QStringLiteral("W"));
  } else if (std::strcmp(kind, "mbwait") == 0) {
    p.drawLine(QPointF(cx, 5), QPointF(cx + 5, cy));
    p.drawLine(QPointF(cx + 5, cy), QPointF(cx - 2, cy));
    p.drawLine(QPointF(cx - 2, cy), QPointF(cx + 3, h - 5));
  } else if (std::strcmp(kind, "s7") == 0) {
    p.drawRoundedRect(QRectF(8, 5, 18, 14), 2, 2);
    QFont f = p.font();
    f.setPointSize(7);
    f.setBold(true);
    p.setFont(f);
    p.drawText(QRectF(8, 5, 18, 14), Qt::AlignCenter, QStringLiteral("S7"));
  } else if (std::strcmp(kind, "opcua") == 0) {
    p.drawRoundedRect(QRectF(6, 5, 22, 14), 2, 2);
    QFont f = p.font();
    f.setPointSize(6);
    f.setBold(true);
    p.setFont(f);
    p.drawText(QRectF(6, 5, 22, 14), Qt::AlignCenter, QStringLiteral("UA"));
  } else {
    p.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12));
    p.drawPoint(QPointF(cx, cy));
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
      {QStringLiteral("locate"), QStringLiteral("模板与定位"),
       QStringLiteral("定位与测量"),
       QStringLiteral("模板匹配 · 旋转搜索 · 定位跟随位姿")},
      {QStringLiteral("pose_correct"), QStringLiteral("位置修正"),
       QStringLiteral("定位与测量"),
       QStringLiteral("绑定上游定位，输出夹具位姿供 ROI/测量跟随")},
      {QStringLiteral("caliper"), QStringLiteral("卡尺测量"),
       QStringLiteral("定位与测量"), QStringLiteral("QImage 边缘间距（px/mm）")},
      {QStringLiteral("measure"), QStringLiteral("尺寸测量与标定"),
       QStringLiteral("定位与测量"),
       QStringLiteral("直径 · 线长 · 两点距 · 夹角 · 轮廓尺寸 · 等比例标定")},
      {QStringLiteral("geometry"), QStringLiteral("几何特征查找"),
       QStringLiteral("定位与测量"),
       QStringLiteral("直线 · 圆 · 矩形 · 轮廓 · 边缘（QImage）")},
      {QStringLiteral("save_image"), QStringLiteral("保存图像"),
       QStringLiteral("图像处理"), QStringLiteral("运行时落盘（可选）")},
      {QStringLiteral("barcode"), QStringLiteral("条码 / 二维码"),
       QStringLiteral("识别"), QStringLiteral("C++ zxing 解码")},
      {QStringLiteral("ocr"), QStringLiteral("OCR 文字识别"),
       QStringLiteral("识别"), QStringLiteral("Tesseract OCR（CLI）")},
      {QStringLiteral("defects"), QStringLiteral("参考图缺陷检测"),
       QStringLiteral("识别"),
       QStringLiteral("灰度差影 · 连通域面积 · 比例判定")},
      {QStringLiteral("var_calc"), QStringLiteral("变量计算"),
       QStringLiteral("变量与数据"),
       QStringLiteral("expr: in / startswith / endswith / contains")},
      {QStringLiteral("format_data"), QStringLiteral("格式化数据"),
       QStringLiteral("变量与数据"),
       QStringLiteral("模板 {name}/${flow.x}/{{name}} · emptyDefault")},
      {QStringLiteral("result_gate"), QStringLiteral("结果门限 OK/NG"),
       QStringLiteral("变量与数据"), QStringLiteral("passGate 门限")},
      {QStringLiteral("send_data"), QStringLiteral("发送数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus TX")},
      {QStringLiteral("receive_data"), QStringLiteral("接收数据"),
       QStringLiteral("工业通信"), QStringLiteral("TCP / LocalBus RX → 变量")},
      {QStringLiteral("serial_exchange"), QStringLiteral("串口报文通信"),
       QStringLiteral("工业通信"),
       QStringLiteral("串口收发 · 回环模拟 / 真实端口 / PTY 回环")},
      {QStringLiteral("modbus_read"), QStringLiteral("Modbus 读取"),
       QStringLiteral("工业通信"),
       QStringLiteral("TCP / RTU / 模拟器 · 寄存器 / 线圈")},
      {QStringLiteral("modbus_write"), QStringLiteral("Modbus 写入"),
       QStringLiteral("工业通信"),
       QStringLiteral("TCP / RTU / 模拟器 · 检测结果输出")},
      {QStringLiteral("modbus_wait"), QStringLiteral("等待 PLC 信号"),
       QStringLiteral("工业通信"),
       QStringLiteral("Modbus 条件 / 边沿触发")},
      {QStringLiteral("s7_read"), QStringLiteral("S7 读取"),
       QStringLiteral("工业通信"),
       QStringLiteral("西门子 · DB / M / I / Q")},
      {QStringLiteral("s7_write"), QStringLiteral("S7 写入"),
       QStringLiteral("工业通信"),
       QStringLiteral("西门子 · 检测结果输出")},
      {QStringLiteral("opcua_read"), QStringLiteral("OPC UA 读取"),
       QStringLiteral("工业通信"),
       QStringLiteral("状态码 · 时间戳 · 变量")},
      {QStringLiteral("opcua_write"), QStringLiteral("OPC UA 写入"),
       QStringLiteral("工业通信"),
       QStringLiteral("带类型写入 · 检测结果")},
      {QStringLiteral("opcua_browse"), QStringLiteral("OPC UA 浏览"),
       QStringLiteral("工业通信"),
       QStringLiteral("设备 · 地址空间")},
      {QStringLiteral("opcua_wait"), QStringLiteral("等待 OPC UA 信号"),
       QStringLiteral("工业通信"),
       QStringLiteral("订阅 · 条件 / 边沿触发")},
      {QStringLiteral("condition"), QStringLiteral("条件判断"),
       QStringLiteral("流程控制"),
       QStringLiteral("数值 / 文本 / 开关分支 · 真/假出边 when=true/false")},
      {QStringLiteral("branch"), QStringLiteral("分支模块"),
       QStringLiteral("流程控制"),
       QStringLiteral("多路径表 · 出边 when=路径名，未命中走默认")},
      {QStringLiteral("branch_merge"), QStringLiteral("分支汇合"),
       QStringLiteral("流程控制"),
       QStringLiteral("等待互斥分支，接收唯一激活路的结果")},
      {QStringLiteral("subflow"), QStringLiteral("子流程调用"),
       QStringLiteral("流程控制"),
       QStringLiteral("调用工程内可复用子流程，局部变量按调用点隔离")},
      {QStringLiteral("loop"), QStringLiteral("循环子流程"),
       QStringLiteral("流程控制"),
       QStringLiteral("重复执行子流程：固定次数或直到输出开关成立")},
  };
}

OperatorDef OperatorLibrary::findDef(const QString& key) {
  for (const auto& d : catalog())
    if (d.key == key) return d;
  return {key, key, QStringLiteral("其它"), {}};
}

OperatorLibrary::OperatorLibrary(QWidget* parent) : QWidget(parent) {
  setStatusTip(QStringLiteral("Toolbox · / 或 Ctrl+F/L 搜索 · 最近 · Ctrl+1-9 最近项 · Ctrl+0 清过滤 · Ctrl+C 复制算子 · Ctrl+Shift+Del 清最近 · 分类芯片 · Enter 添加(列表/搜索) · Enter/中键 添加 · Home/End/PgUp/PgDn · Esc 清空 · 右键复制 · Ctrl+Shift+C 可见键 · 中键分类芯片"));
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
  catChipHost_ = new QWidget;
  catChipHost_->setObjectName(QStringLiteral("toolboxCatChips"));
  catChipLay_ = new QHBoxLayout(catChipHost_);
  catChipLay_->setContentsMargins(4, 2, 4, 2);
  catChipLay_->setSpacing(3);
  lay->addWidget(catChipHost_);
  rebuildCategoryChips();
  list_ = new OperatorListWidget;
  list_->setSpacing(0);
  list_->setUniformItemSizes(true);
  list_->setDragEnabled(true);
  list_->setToolTip(QStringLiteral("Toolbox · 拖入画布 / 双击添加 · 拖拽显示算子标题条 · Enter 激活"));
  list_->setDragDropMode(QAbstractItemView::DragOnly);
  list_->setDefaultDropAction(Qt::CopyAction);
  list_->setIconSize(QSize(32, 24));
  list_->setUniformItemSizes(true);
  list_->setObjectName(QStringLiteral("operatorTiles"));
  list_->setToolTip(QStringLiteral("双击/Enter 添加算子 · 中键添加 · 右键复制 · ↑↓/Home/End/Pg · Esc 清空搜索 · Ctrl+C 复制 · Ctrl+Shift+C 可见键"));
  list_->setStatusTip(QStringLiteral("Toolbox 列表 · 双击或 Enter 添加 · / 聚焦搜索"));
  lay->addWidget(list_, 1);
  connect(list_, &QListWidget::itemDoubleClicked, this,
          [this](QListWidgetItem* item) {
            if (!item || item->data(Qt::UserRole).toString().isEmpty()) return;
            const QString k = item->data(Qt::UserRole).toString();
            const QString n = item->data(Qt::UserRole + 1).toString();
            rememberRecent(k);
            emit operatorActivated(k, n);
          });
  connect(list_, &QListWidget::itemActivated, this,
          [this](QListWidgetItem* item) {
            if (!item || item->data(Qt::UserRole).toString().isEmpty()) return;
            const QString k = item->data(Qt::UserRole).toString();
            const QString n = item->data(Qt::UserRole + 1).toString();
            rememberRecent(k);
            emit operatorActivated(k, n);
          });
  connect(search_, &QLineEdit::textChanged, this, [this](const QString&) { rebuild(); });
  search_->setPlaceholderText(QStringLiteral("搜索… / 或 Ctrl+F · Esc 清空"));
  search_->setToolTip(QStringLiteral("Toolbox 搜索 · Esc/Del/Backspace 清空(搜索/列表) · / 或 Ctrl+F/L 聚焦 · Enter 添加 · 模糊匹配 tip"));
  search_->installEventFilter(this);
  list_->installEventFilter(this);
  installEventFilter(this);
  rebuild();
}

void OperatorLibrary::setCategoryFilter(const QString& category) {
  categoryFilter_ = category;
  rebuild();
  // chips may be driven externally (rail) — keep checked state in sync when host exists
  if (catChipLay_) rebuildCategoryChips();
}

void OperatorLibrary::rememberRecent(const QString& key) {
  if (key.isEmpty()) return;
  recentKeys_.removeAll(key);
  recentKeys_.prepend(key);
  while (recentKeys_.size() > 8) recentKeys_.removeLast();
  // soft refresh headers without losing selection heavily
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
  if (categoryFilter_.isEmpty() && !recentKeys_.isEmpty()) {
    bool anyRecent = false;
    for (const QString& rk : recentKeys_) {
      const OperatorDef def = findDef(rk);
      if (!q.isEmpty() && !def.name.contains(q, Qt::CaseInsensitive) &&
          !def.key.contains(q, Qt::CaseInsensitive) &&
          !def.tip.contains(q, Qt::CaseInsensitive))
        continue;
      if (!anyRecent) {
        anyRecent = true;
        auto* hdr = new QListWidgetItem(QStringLiteral("▾ 最近"));
        hdr->setFlags(Qt::ItemIsEnabled);
        hdr->setForeground(QColor(theme::ACCENT));
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
      item->setToolTip(QStringLiteral("最近 · [%1] %2").arg(def.category, def.tip));
      item->setForeground(accent);
      item->setSizeHint(QSize(0, 28));
      list_->addItem(item);
    }
  }
  for (const auto& def : catalog()) {
    if (!categoryFilter_.isEmpty() && def.category != categoryFilter_) continue;
    if (!q.isEmpty() && !def.name.contains(q, Qt::CaseInsensitive) &&
        !def.key.contains(q, Qt::CaseInsensitive) &&
        !def.category.contains(q, Qt::CaseInsensitive) &&
        !def.tip.contains(q, Qt::CaseInsensitive))
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
    item->setSizeHint(QSize(0, 28));
    list_->addItem(item);
  }
  if (list_->count() == 0) {
    auto* empty = new QListWidgetItem(QStringLiteral("（无匹配算子）"));
    empty->setFlags(Qt::NoItemFlags);
    empty->setForeground(QColor(theme::TEXT_DIM));
    list_->addItem(empty);
  }
  int ops = 0;
  for (int i = 0; i < list_->count(); ++i) {
    auto* it = list_->item(i);
    if (it && !it->data(Qt::UserRole).toString().isEmpty()) ++ops;
  }
  if (search_) {
    const QString filt = categoryFilter_.isEmpty()
                             ? QStringLiteral("全部")
                             : categoryFilter_;
    search_->setToolTip(
        QStringLiteral("Toolbox 搜索 · %1 · 匹配 %2 个 · Esc/Backspace 清空 · / 或 Ctrl+F/L 聚焦")
            .arg(filt)
            .arg(ops));
    if (auto* title = findChild<QLabel*>(QStringLiteral("libraryTitle")))
      title->setText(QStringLiteral("算子 · %1").arg(ops));
  }
}

void OperatorLibrary::activateRecentAt(int index) {
  if (index < 0 || index >= recentKeys_.size()) return;
  const QString key = recentKeys_.at(index);
  const OperatorDef def = findDef(key);
  rememberRecent(key);
  emit operatorActivated(def.key, def.name.isEmpty() ? def.key : def.name);
  if (search_)
    search_->setToolTip(QStringLiteral("已激活最近 #%1 · %2 · Ctrl+1-9")
                            .arg(index + 1)
                            .arg(def.name));
}

void OperatorLibrary::rebuildCategoryChips() {
  if (!catChipLay_) return;
  while (catChipLay_->count() > 0) {
    QLayoutItem* it = catChipLay_->takeAt(0);
    if (it->widget()) it->widget()->deleteLater();
    delete it;
  }
  QStringList cats{QStringLiteral("全部")};
  for (const auto& def : catalog()) {
    if (!cats.contains(def.category)) cats << def.category;
  }
  for (const QString& c : cats) {
    auto* b = new QPushButton(c == QLatin1String("全部") ? QStringLiteral("全部") : c);
    b->setFlat(true);
    b->setCheckable(true);
    const bool on = (c == QLatin1String("全部") && categoryFilter_.isEmpty()) ||
                    (c == categoryFilter_);
    b->setChecked(on);
    b->setCursor(Qt::PointingHandCursor);
    b->setStyleSheet(
        QStringLiteral("QPushButton{background:#2a2d32;color:#a8a8a8;border-radius:3px;"
                       "padding:2px 6px;font-size:10px;}"
                       "QPushButton:checked{background:#1e3d2f;color:#3ecf8e;font-weight:600;}"
                       "QPushButton:hover{color:#e8e8e8;}"));
    b->setToolTip(QStringLiteral("Toolbox 分类 · %1").arg(c));
    connect(b, &QPushButton::clicked, this, [this, c]() {
      setCategoryFilter(c == QLatin1String("全部") ? QString() : c);
    });
    b->setProperty("sieansCat", c);
    b->setToolTip(c == QLatin1String("全部")
                      ? QStringLiteral("全部分类 · 中键同单击")
                      : QStringLiteral("分类 %1 · 单击/中键过滤").arg(c));
    b->installEventFilter(this);
    catChipLay_->addWidget(b);
  }
    {
    auto* clr = new QPushButton(QStringLiteral("清最近"));
    clr->setFlat(true);
    clr->setCursor(Qt::PointingHandCursor);
    clr->setToolTip(QStringLiteral("清空最近算子 · Ctrl+Shift+Del"));
    clr->setStyleSheet(
        QStringLiteral("QPushButton{background:#3a2a2a;color:#e0a0a0;border-radius:3px;"
                       "padding:2px 6px;font-size:10px;}"
                       "QPushButton:hover{background:#e53935;color:#fff;}"));
    connect(clr, &QPushButton::clicked, this, [this]() {
      recentKeys_.clear();
      rebuild();
    });
    catChipLay_->addWidget(clr);
  }
  catChipLay_->addStretch(1);
}

void OperatorLibrary::focusSearch() {
  if (!search_) return;
  search_->setFocus(Qt::ShortcutFocusReason);
  search_->selectAll();
}

bool OperatorLibrary::eventFilter(QObject* obj, QEvent* event) {
  if (event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      const QVariant cat = obj->property("sieansCat");
      if (cat.isValid()) {
        const QString c = cat.toString();
        setCategoryFilter(c == QLatin1String("全部") ? QString() : c);
        if (list_) list_->setFocus(Qt::OtherFocusReason);
        if (search_) search_->setToolTip(QStringLiteral("分类 · 中键芯片 · %1").arg(c));
        return true;
      }
    }
  }
  if (obj == list_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      QListWidgetItem* hit = list_->itemAt(me->position().toPoint());
      if (!hit) hit = list_->currentItem();
      if (hit && !hit->data(Qt::UserRole).toString().isEmpty()) {
        list_->setCurrentItem(hit);
        const QString k = hit->data(Qt::UserRole).toString();
        const QString n = hit->data(Qt::UserRole + 1).toString();
        rememberRecent(k);
        emit operatorActivated(k, n);
        if (search_) search_->setToolTip(QStringLiteral("已添加 · 中键 · %1").arg(k));
      }
      return true;
    }
    if (me->button() == Qt::RightButton) {
      QListWidgetItem* hit = list_->itemAt(me->position().toPoint());
      if (!hit) hit = list_->currentItem();
      if (hit) {
        const QString k = hit->data(Qt::UserRole).toString();
        const QString tip = hit->toolTip().isEmpty() ? hit->text() : hit->toolTip();
        if (auto* clip = QGuiApplication::clipboard())
          clip->setText(k.isEmpty() ? tip : k + QLatin1Char('\t') + tip);
        if (search_) search_->setToolTip(QStringLiteral("已复制算子 · 右键"));
      }
      return true;
    }
  }
  if (event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if ((ke->modifiers() & Qt::ControlModifier) &&
        ke->key() >= Qt::Key_1 && ke->key() <= Qt::Key_9) {
      activateRecentAt(ke->key() - Qt::Key_1);
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) && ke->key() == Qt::Key_C && list_) {
      if (ke->modifiers() & Qt::ShiftModifier) {
        QStringList lines;
        for (int i = 0; i < list_->count(); ++i) {
          auto* it = list_->item(i);
          if (!it) continue;
          const QString key = it->data(Qt::UserRole).toString();
          if (key.isEmpty()) continue;
          lines << key;
        }
        if (auto* clip = QGuiApplication::clipboard())
          clip->setText(lines.join(QLatin1Char('\n')));
        if (search_)
          search_->setToolTip(QStringLiteral("已复制可见算子 %1 · Ctrl+Shift+C").arg(lines.size()));
        return true;
      }
      QListWidgetItem* it = list_->currentItem();
      if (it) {
        const QString tip = it->toolTip().isEmpty() ? it->text() : it->toolTip();
        const QString key = it->data(Qt::UserRole).toString();
        if (auto* clip = QGuiApplication::clipboard())
          clip->setText(key.isEmpty() ? tip : key + QLatin1Char('\t') + tip);
        if (search_) search_->setToolTip(QStringLiteral("已复制算子 · Ctrl+C"));
      }
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) && ke->key() == Qt::Key_0) {
      setCategoryFilter(QString());
      if (search_) search_->clear();
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) &&
        (ke->modifiers() & Qt::ShiftModifier) &&
        (ke->key() == Qt::Key_Delete || ke->key() == Qt::Key_Backspace)) {
      recentKeys_.clear();
      rebuild();
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) &&
        (ke->key() == Qt::Key_F || ke->key() == Qt::Key_L)) {
      focusSearch();
      return true;
    }
    if ((ke->key() == Qt::Key_Escape ||
         ((ke->key() == Qt::Key_Delete || ke->key() == Qt::Key_Backspace) &&
          obj == search_)) &&
        search_ && !search_->text().isEmpty() &&
        (obj == search_ || obj == list_)) {
      search_->clear();
      if (obj == list_) list_->setFocus(Qt::OtherFocusReason);
      return true;
    }
    if (ke->key() == Qt::Key_Slash && obj != search_ &&
        !(ke->modifiers() & (Qt::ControlModifier | Qt::AltModifier))) {
      focusSearch();
      return true;
    }
    if ((ke->key() == Qt::Key_Home || ke->key() == Qt::Key_End) && list_ &&
        (obj == list_ || obj == search_)) {
      if (list_->count() <= 0) return true;
      const int row = ke->key() == Qt::Key_Home ? 0 : list_->count() - 1;
      list_->setCurrentRow(row);
      if (auto* it = list_->item(row)) list_->scrollToItem(it);
      return true;
    }
    if ((ke->key() == Qt::Key_PageUp || ke->key() == Qt::Key_PageDown) && list_ &&
        (obj == list_ || obj == search_)) {
      if (list_->count() <= 0) return true;
      const int cur = list_->currentRow() < 0 ? 0 : list_->currentRow();
      const int step = 8;
      int row = ke->key() == Qt::Key_PageUp ? cur - step : cur + step;
      row = qBound(0, row, list_->count() - 1);
      list_->setCurrentRow(row);
      if (auto* it = list_->item(row)) list_->scrollToItem(it);
      return true;
    }
    if ((ke->key() == Qt::Key_Return || ke->key() == Qt::Key_Enter) && list_ &&
        (obj == search_ || obj == list_)) {
      // Prefer current list row; else first activatable match (search Enter).
      QListWidgetItem* pick = list_->currentItem();
      if (!pick || pick->data(Qt::UserRole).toString().isEmpty()) {
        for (int i = 0; i < list_->count(); ++i) {
          auto* it = list_->item(i);
          if (it && !it->data(Qt::UserRole).toString().isEmpty()) {
            pick = it;
            break;
          }
        }
      }
      if (pick && !pick->data(Qt::UserRole).toString().isEmpty()) {
        list_->setCurrentItem(pick);
        const QString k = pick->data(Qt::UserRole).toString();
        const QString n = pick->data(Qt::UserRole + 1).toString();
        rememberRecent(k);
        emit operatorActivated(k, n);
        return true;
      }
    }
  }
  return QWidget::eventFilter(obj, event);
}

}  // namespace sieans_qt
