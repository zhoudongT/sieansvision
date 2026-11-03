#include "FlowIoDialog.hpp"
#include "Theme.hpp"

#include <QCheckBox>
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QHeaderView>
#include <QLabel>
#include <QTabWidget>
#include <QTableWidget>
#include <QAbstractItemView>
#include <QModelIndex>
#include <QItemSelectionModel>
#include <QSet>
#include <algorithm>
#include <QVBoxLayout>
#include <QShortcut>
#include <QKeySequence>
#include <QClipboard>
#include <QGuiApplication>
#include <QApplication>
#include <QInputDialog>
#include <QHBoxLayout>
#include <QPushButton>

namespace sieans_qt {

FlowIoDialog::FlowIoDialog(const QVariantMap& io, QWidget* parent)
    : QDialog(parent), io_(io) {
  setWindowTitle(QStringLiteral("流程参数 · I/O 绑定"));
  setStatusTip(QStringLiteral("流程 I/O · {name}/${flow.x}/{{name}} · Alt+↑↓ 移行 · Ctrl+D 复制 · Ctrl+Shift+V 粘贴 · binding 芯片 · Esc 取消 · Enter/Ctrl+Enter 确定 · emptyDefault 空结果"));
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
  {
    auto* rowBtns = new QHBoxLayout;
    auto* add = new QPushButton(QStringLiteral("＋ 行"));
    auto* rem = new QPushButton(QStringLiteral("－ 行"));
    add->setToolTip(QStringLiteral("插入绑定行 · Insert / Ctrl+N"));
    rem->setToolTip(QStringLiteral("删除选中行 · Del"));
    rowBtns->addWidget(add);
    rowBtns->addWidget(rem);
    wireRowOps(inTable_, rowBtns);
    rowBtns->addStretch(1);
    inLay->addLayout(rowBtns);
    connect(add, &QPushButton::clicked, this, [this]() { addRow(inTable_); });
    connect(rem, &QPushButton::clicked, this, [this]() { removeSelectedRows(inTable_); });
    auto* scN = new QShortcut(QKeySequence(QStringLiteral("Ctrl+N")), inTable_);
    connect(scN, &QShortcut::activated, this, [this]() { addRow(inTable_); });
    auto* scIns = new QShortcut(QKeySequence(Qt::Key_Insert), inTable_);
    connect(scIns, &QShortcut::activated, this, [this]() { addRow(inTable_); });
    auto* scDel = new QShortcut(QKeySequence(Qt::Key_Delete), inTable_);
    connect(scDel, &QShortcut::activated, this, [this]() { removeSelectedRows(inTable_); });
  }
  inLay->addWidget(new QLabel(QStringLiteral("空行忽略；订阅关系例：0 图像源1.图像[] / flow.var · emptyDefault 空结果")));
  auto* outHost = new QWidget;
  auto* outLay = new QVBoxLayout(outHost);
  outLay->setContentsMargins(4, 4, 4, 4);
  outLay->addWidget(outTable_);
  {
    auto* rowBtns = new QHBoxLayout;
    auto* add = new QPushButton(QStringLiteral("＋ 行"));
    auto* rem = new QPushButton(QStringLiteral("－ 行"));
    add->setToolTip(QStringLiteral("插入输出绑定 · Insert / Ctrl+N"));
    rem->setToolTip(QStringLiteral("删除选中行 · Del"));
    rowBtns->addWidget(add);
    rowBtns->addWidget(rem);
    wireRowOps(outTable_, rowBtns);
    rowBtns->addStretch(1);
    outLay->addLayout(rowBtns);
    connect(add, &QPushButton::clicked, this, [this]() { addRow(outTable_); });
    connect(rem, &QPushButton::clicked, this, [this]() { removeSelectedRows(outTable_); });
    auto* scN = new QShortcut(QKeySequence(QStringLiteral("Ctrl+N")), outTable_);
    connect(scN, &QShortcut::activated, this, [this]() { addRow(outTable_); });
    auto* scIns = new QShortcut(QKeySequence(Qt::Key_Insert), outTable_);
    connect(scIns, &QShortcut::activated, this, [this]() { addRow(outTable_); });
    auto* scDel = new QShortcut(QKeySequence(Qt::Key_Delete), outTable_);
    connect(scDel, &QShortcut::activated, this, [this]() { removeSelectedRows(outTable_); });
  }
  outLay->addWidget(new QLabel(QStringLiteral("输出可绑结果变量 / 图像口；空行忽略 · emptyDefault 占位报文")));
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
  auto* table = new QTableWidget(qMax(4, rows.isEmpty() ? 2 : rows.size()), 4);
  table->setObjectName(QStringLiteral("flowIoTable"));
  table->setHorizontalHeaderLabels(
      {QStringLiteral("参数名称"), QStringLiteral("类型"), QStringLiteral("订阅关系"),
       QStringLiteral("emptyDefault")});
  table->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  table->verticalHeader()->setVisible(false);
  table->setSelectionBehavior(QAbstractItemView::SelectRows);
  table->setSelectionMode(QAbstractItemView::ExtendedSelection);
  table->setToolTip(
      QStringLiteral("I/O 绑定 · Insert/Ctrl+N 增行 · Del 删行 · Alt+↑↓ 移行 · Ctrl+D 复制 · Ctrl+Shift+V 粘贴 · binding 芯片 · emptyDefault 空结果占位 · {name}/${flow.x}/{{name}}"));
  table->setStatusTip(QStringLiteral("流程 I/O 表 · emptyDefault"));
  if (rows.isEmpty()) {
    const QList<QStringList> demo =
        kind == QLatin1String("输入")
            ? QList<QStringList>{{QStringLiteral("ImageData"), QStringLiteral("IMAGE"),
                                  QStringLiteral("—"), QString()},
                                 {QStringLiteral("InputROI"), QStringLiteral("ROI"),
                                  QStringLiteral("—"), QString()}}
            : QList<QStringList>{{QStringLiteral("ImageData"), QStringLiteral("IMAGE"),
                                  QStringLiteral("0 图像源1.图像[]"), QString()},
                                 {QStringLiteral("Result"), QStringLiteral("JSON"),
                                  QStringLiteral("—"), QStringLiteral("BARCODE empty")}};
    for (int r = 0; r < demo.size(); ++r)
      for (int c = 0; c < 4; ++c) table->setItem(r, c, new QTableWidgetItem(demo[r][c]));
  } else {
    for (int r = 0; r < rows.size(); ++r) {
      const QVariantMap row = rows[r].toMap();
      table->setItem(r, 0, new QTableWidgetItem(row.value(QStringLiteral("name")).toString()));
      table->setItem(r, 1, new QTableWidgetItem(row.value(QStringLiteral("type")).toString()));
      table->setItem(r, 2, new QTableWidgetItem(row.value(QStringLiteral("binding")).toString()));
      table->setItem(r, 3, new QTableWidgetItem(row.value(QStringLiteral("emptyDefault")).toString()));
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
    const QString ed =
        table->item(r, 3) ? table->item(r, 3)->text().trimmed() : QString();
    if (!ed.isEmpty()) row.insert(QStringLiteral("emptyDefault"), ed);
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


void FlowIoDialog::addRow(QTableWidget* table) {
  if (!table) return;
  const int r = table->rowCount();
  table->insertRow(r);
  table->setItem(r, 0, new QTableWidgetItem(QStringLiteral("Param%1").arg(r + 1)));
  table->setItem(r, 1, new QTableWidgetItem(QStringLiteral("ANY")));
  table->setItem(r, 2, new QTableWidgetItem(QString()));
  table->setItem(r, 3, new QTableWidgetItem(QString()));
  table->setCurrentCell(r, 0);
  table->editItem(table->item(r, 0));
}

void FlowIoDialog::removeSelectedRows(QTableWidget* table) {
  if (!table) return;
  auto ranges = table->selectionModel() ? table->selectionModel()->selectedRows() : QModelIndexList();
  if (ranges.isEmpty()) {
    const int r = table->currentRow();
    if (r >= 0) table->removeRow(r);
    return;
  }
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  std::sort(rows.begin(), rows.end(), std::greater<int>());
  for (int r : rows) table->removeRow(r);
}


void FlowIoDialog::wireRowOps(QTableWidget* table, QHBoxLayout* rowBtns) {
  auto* up = new QPushButton(QStringLiteral("↑"));
  auto* down = new QPushButton(QStringLiteral("↓"));
  auto* dup = new QPushButton(QStringLiteral("复制"));
  auto* paste = new QPushButton(QStringLiteral("粘贴行"));
  auto* tokPass = new QPushButton(QStringLiteral("${flow.passGate}"));
  auto* tokText = new QPushButton(QStringLiteral("${flow.barcodeText}"));
  up->setFixedWidth(28);
  down->setFixedWidth(28);
  up->setToolTip(QStringLiteral("上移选中行 · Alt+↑"));
  down->setToolTip(QStringLiteral("下移选中行 · Alt+↓"));
  dup->setToolTip(QStringLiteral("复制选中行 · Ctrl+D"));
  paste->setToolTip(QStringLiteral("从剪贴板粘贴多行绑定 · Ctrl+Shift+V · 每行 name,type,binding,emptyDefault"));
  tokPass->setToolTip(QStringLiteral("写入当前行 binding · ${flow.passGate}"));
  tokText->setToolTip(QStringLiteral("写入当前行 binding · ${flow.barcodeText}"));
  tokPass->setStyleSheet(QStringLiteral("font-size:11px;"));
  tokText->setStyleSheet(QStringLiteral("font-size:11px;"));
  rowBtns->addWidget(up);
  rowBtns->addWidget(down);
  rowBtns->addWidget(dup);
  rowBtns->addWidget(paste);
  rowBtns->addWidget(tokPass);
  rowBtns->addWidget(tokText);
  connect(up, &QPushButton::clicked, this, [this, table]() { moveSelectedRows(table, -1); });
  connect(down, &QPushButton::clicked, this, [this, table]() { moveSelectedRows(table, +1); });
  connect(dup, &QPushButton::clicked, this, [this, table]() { duplicateSelectedRows(table); });
  connect(paste, &QPushButton::clicked, this, [this, table]() { pasteRows(table); });
  connect(tokPass, &QPushButton::clicked, this, [this, table]() {
    insertBindingToken(table, QStringLiteral("${flow.passGate}"));
  });
  connect(tokText, &QPushButton::clicked, this, [this, table]() {
    insertBindingToken(table, QStringLiteral("${flow.barcodeText}"));
  });
  auto* scUp = new QShortcut(QKeySequence(QStringLiteral("Alt+Up")), table);
  connect(scUp, &QShortcut::activated, this, [this, table]() { moveSelectedRows(table, -1); });
  auto* scDn = new QShortcut(QKeySequence(QStringLiteral("Alt+Down")), table);
  connect(scDn, &QShortcut::activated, this, [this, table]() { moveSelectedRows(table, +1); });
  auto* scDup = new QShortcut(QKeySequence(QStringLiteral("Ctrl+D")), table);
  connect(scDup, &QShortcut::activated, this, [this, table]() { duplicateSelectedRows(table); });
  auto* scPaste = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+V")), table);
  connect(scPaste, &QShortcut::activated, this, [this, table]() { pasteRows(table); });
}

void FlowIoDialog::moveSelectedRows(QTableWidget* table, int delta) {
  if (!table || delta == 0) return;
  const auto ranges = table->selectionModel() ? table->selectionModel()->selectedRows() : QModelIndexList{};
  if (ranges.isEmpty()) return;
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  std::sort(rows.begin(), rows.end());
  if (delta > 0) std::reverse(rows.begin(), rows.end());
  table->blockSignals(true);
  for (int r : rows) {
    const int dest = r + delta;
    if (dest < 0 || dest >= table->rowCount()) continue;
    for (int c = 0; c < table->columnCount(); ++c) {
      QTableWidgetItem* a = table->takeItem(r, c);
      QTableWidgetItem* b = table->takeItem(dest, c);
      table->setItem(r, c, b);
      table->setItem(dest, c, a);
    }
  }
  table->blockSignals(false);
  table->clearSelection();
  for (int r : rows) {
    const int dest = qBound(0, r + delta, table->rowCount() - 1);
    table->selectRow(dest);
  }
}

void FlowIoDialog::duplicateSelectedRows(QTableWidget* table) {
  if (!table) return;
  const auto ranges = table->selectionModel() ? table->selectionModel()->selectedRows() : QModelIndexList{};
  if (ranges.isEmpty()) {
    addRow(table);
    return;
  }
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  std::sort(rows.begin(), rows.end());
  for (int r : rows) {
    const int dest = table->rowCount();
    table->insertRow(dest);
    for (int c = 0; c < table->columnCount(); ++c) {
      QTableWidgetItem* src = table->item(r, c);
      table->setItem(dest, c, new QTableWidgetItem(src ? src->text() : QString()));
    }
  }
}
void FlowIoDialog::insertBindingToken(QTableWidget* table, const QString& token) {
  if (!table || token.isEmpty()) return;
  int r = table->currentRow();
  if (r < 0) {
    addRow(table);
    r = table->rowCount() - 1;
  }
  if (!table->item(r, 2)) table->setItem(r, 2, new QTableWidgetItem);
  table->item(r, 2)->setText(token);
  table->setCurrentCell(r, 2);
}

void FlowIoDialog::pasteRows(QTableWidget* table) {
  if (!table) return;
  const QClipboard* clip = QGuiApplication::clipboard();
  if (!clip) return;
  const QString text = clip->text().trimmed();
  if (text.isEmpty()) return;
  int added = 0;
  for (const QString& line : text.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
    const QStringList parts = line.split(QLatin1Char(','));
    if (parts.isEmpty()) continue;
    const int r = table->rowCount();
    table->insertRow(r);
    table->setItem(r, 0, new QTableWidgetItem(parts.value(0).trimmed().isEmpty()
                                                  ? QStringLiteral("Param%1").arg(r + 1)
                                                  : parts.value(0).trimmed()));
    table->setItem(r, 1, new QTableWidgetItem(parts.value(1).trimmed().isEmpty()
                                                  ? QStringLiteral("ANY")
                                                  : parts.value(1).trimmed()));
    table->setItem(r, 2, new QTableWidgetItem(parts.value(2).trimmed()));
    table->setItem(r, 3, new QTableWidgetItem(parts.value(3).trimmed()));
    ++added;
  }
  if (added > 0) table->selectRow(table->rowCount() - 1);
}

}  // namespace sieans_qt
