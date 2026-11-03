#include "FlowIoDialog.hpp"
#include "Theme.hpp"

#include <QCheckBox>
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QHeaderView>
#include <QLabel>
#include <QTabWidget>
#include <QTableWidget>
#include <QVBoxLayout>
#include <QShortcut>
#include <QKeySequence>

namespace sieans_qt {

FlowIoDialog::FlowIoDialog(const QVariantMap& io, QWidget* parent)
    : QDialog(parent), io_(io) {
  setWindowTitle(QStringLiteral("流程参数 · I/O 绑定"));
  setStatusTip(QStringLiteral("流程 I/O · {name}/${flow.x}/{{name}} · Esc 取消 · Enter/Ctrl+Enter 确定 · emptyDefault 空结果"));
  resize(560, 440);
  setStyleSheet(theme::workbenchStyleSheet());
  auto* root = new QVBoxLayout(this);
  auto* hint = new QLabel(
      QStringLiteral(
          "流程级 I/O 与显示：表格可编辑；确定后写回 flow.io（订阅 模块.字段 / flow.var；"
          "报文模板支持 {name} / ${flow.x} / {{name}}）· Esc 取消 · Enter/Ctrl+Enter 确定"));
  hint->setObjectName(QStringLiteral("muted"));
  hint->setWordWrap(true);
  root->addWidget(hint);
  auto* tabs = new QTabWidget;
  inTable_ = makeTable(io.value(QStringLiteral("inputs")).toList(), QStringLiteral("输入"));
  outTable_ = makeTable(io.value(QStringLiteral("outputs")).toList(), QStringLiteral("输出"));
  auto* inHost = new QWidget;
  auto* inLay = new QVBoxLayout(inHost);
  inLay->setContentsMargins(4, 4, 4, 4);
  inLay->addWidget(inTable_);
  inLay->addWidget(new QLabel(QStringLiteral("空行忽略；订阅关系例：0 图像源1.图像[] / flow.var")));
  auto* outHost = new QWidget;
  auto* outLay = new QVBoxLayout(outHost);
  outLay->setContentsMargins(4, 4, 4, 4);
  outLay->addWidget(outTable_);
  outLay->addWidget(new QLabel(QStringLiteral("输出可绑结果变量 / 图像口；空行忽略")));
  auto* disp = new QWidget;
  auto* form = new QFormLayout(disp);
  const QVariantMap display = io.value(QStringLiteral("display")).toMap();
  globalImage_ = new QCheckBox(QStringLiteral("启用"));
  globalImage_->setChecked(
      !display.contains(QStringLiteral("globalImage")) ||
      display.value(QStringLiteral("globalImage")).toBool());
  form->addRow(QStringLiteral("显示全局图像"), globalImage_);
  form->addRow(QStringLiteral("说明"),
               new QLabel(display.value(QStringLiteral("note"),
                                        QStringLiteral("与运行界面分屏 / 固定栏配置联动"))
                              .toString()));
  tabs->addTab(inHost, QStringLiteral("输入设置"));
  tabs->addTab(outHost, QStringLiteral("输出设置"));
  tabs->addTab(disp, QStringLiteral("显示设置"));
  root->addWidget(tabs, 1);
  auto* buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
  connect(buttons, &QDialogButtonBox::accepted, this, &QDialog::accept);
  connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
  root->addWidget(buttons);
  {
    auto* sc = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Return")), this);
    connect(sc, &QShortcut::activated, this, &QDialog::accept);
    auto* sc2 = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Enter")), this);
    connect(sc2, &QShortcut::activated, this, &QDialog::accept);
  }
}

QTableWidget* FlowIoDialog::makeTable(const QVariantList& rows, const QString& kind) {
  auto* table = new QTableWidget(qMax(4, rows.isEmpty() ? 2 : rows.size()), 3);
  table->setObjectName(QStringLiteral("flowIoTable"));
  table->setHorizontalHeaderLabels(
      {QStringLiteral("参数名称"), QStringLiteral("类型"), QStringLiteral("订阅关系")});
  table->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  table->verticalHeader()->setVisible(false);
  if (rows.isEmpty()) {
    const QList<QStringList> demo =
        kind == QLatin1String("输入")
            ? QList<QStringList>{{QStringLiteral("ImageData"), QStringLiteral("IMAGE"),
                                  QStringLiteral("—")},
                                 {QStringLiteral("InputROI"), QStringLiteral("ROI"),
                                  QStringLiteral("—")}}
            : QList<QStringList>{{QStringLiteral("ImageData"), QStringLiteral("IMAGE"),
                                  QStringLiteral("0 图像源1.图像[]")},
                                 {QStringLiteral("Result"), QStringLiteral("JSON"),
                                  QStringLiteral("—")}};
    for (int r = 0; r < demo.size(); ++r)
      for (int c = 0; c < 3; ++c) table->setItem(r, c, new QTableWidgetItem(demo[r][c]));
  } else {
    for (int r = 0; r < rows.size(); ++r) {
      const QVariantMap row = rows[r].toMap();
      table->setItem(r, 0, new QTableWidgetItem(row.value(QStringLiteral("name")).toString()));
      table->setItem(r, 1, new QTableWidgetItem(row.value(QStringLiteral("type")).toString()));
      table->setItem(r, 2, new QTableWidgetItem(row.value(QStringLiteral("binding")).toString()));
    }
  }
  return table;
}

QVariantList FlowIoDialog::readTable(QTableWidget* table) const {
  QVariantList rows;
  if (!table) return rows;
  for (int r = 0; r < table->rowCount(); ++r) {
    const QString name = table->item(r, 0) ? table->item(r, 0)->text().trimmed() : QString();
    if (name.isEmpty()) continue;
    QVariantMap row;
    row.insert(QStringLiteral("name"), name);
    row.insert(QStringLiteral("type"),
               table->item(r, 1) ? table->item(r, 1)->text().trimmed() : QStringLiteral("ANY"));
    row.insert(QStringLiteral("binding"),
               table->item(r, 2) ? table->item(r, 2)->text().trimmed() : QString());
    rows.push_back(row);
  }
  return rows;
}

QVariantMap FlowIoDialog::resultIo() const {
  QVariantMap io = io_;
  io.insert(QStringLiteral("inputs"), readTable(inTable_));
  io.insert(QStringLiteral("outputs"), readTable(outTable_));
  QVariantMap display = io.value(QStringLiteral("display")).toMap();
  display.insert(QStringLiteral("globalImage"), globalImage_ && globalImage_->isChecked());
  io.insert(QStringLiteral("display"), display);
  return io;
}

}  // namespace sieans_qt
