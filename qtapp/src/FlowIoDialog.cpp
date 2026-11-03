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
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QGuiApplication>
#include <QApplication>
#include <QInputDialog>
#include <QHBoxLayout>
#include <QPushButton>

namespace sieans_qt {

FlowIoDialog::FlowIoDialog(const QVariantMap& io, QWidget* parent)
    : QDialog(parent), io_(io) {
  setWindowTitle(QStringLiteral("流程参数 · I/O 绑定"));
  setStatusTip(QStringLiteral("流程 I/O · {name}/${flow.x}/{{name}} · Alt+↑↓ 移行 · Ctrl+Shift+Y 反序 · Ctrl+Shift+S 按名排序 · Ctrl+Shift+D 复制到另一表 · Ctrl+Home/End 置顶/底 · Ctrl+Shift+U 去重 · Ctrl+D 复制行 · Ctrl+A 全选 · Ctrl+E 补默认 · Ctrl+Shift+E 清默认 · Ctrl+Tab 切换表 · Ctrl+Shift+C 复制CSV · Ctrl+X 剪切 · Ctrl+Shift+V 粘贴 · Ctrl+Shift+L 清空空行 · binding 芯片 · Esc 取消 · Enter/Ctrl+Enter 确定 · emptyDefault 空结果 · Ctrl+Shift+J/O 导出/导入JSON"));
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
    auto* scTab = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Tab")), this);
    connect(scTab, &QShortcut::activated, this, [this]() {
      if (!inTable_ || !outTable_) return;
      if (outTable_->hasFocus()) {
        inTable_->setFocus(Qt::ShortcutFocusReason);
      } else {
        outTable_->setFocus(Qt::ShortcutFocusReason);
      }
    });
    auto* scJson = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+J")), this);
    connect(scJson, &QShortcut::activated, this, [this]() { exportBindingsJson(); });
    auto* scImp = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+O")), this);
    connect(scImp, &QShortcut::activated, this, [this]() { importBindingsJson(); });
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
      QStringLiteral("I/O 绑定 · Insert/Ctrl+N 增行 · Del 删行 · Alt+↑↓ 移行 · Ctrl+Shift+Y 反序 · Ctrl+Shift+S 按名排序 · Ctrl+Shift+D 复制到另一表 · Ctrl+Home/End 置顶/底 · Ctrl+Shift+U 去重 · Ctrl+D 复制 · Ctrl+X 剪切 · Ctrl+Shift+V 粘贴 · Ctrl+Shift+L 清空空行 · Home/End · binding 芯片 · emptyDefault 空结果占位 · {name}/${flow.x}/{{name}}"));
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
  auto* copyClip = new QPushButton(QStringLiteral("复制行"));
  auto* clearEmpty = new QPushButton(QStringLiteral("清空行"));
  auto* toOther = new QPushButton(QStringLiteral("⇄ 对表"));
  auto* fillDef = new QPushButton(QStringLiteral("补默认"));
  auto* tokPass = new QPushButton(QStringLiteral("${flow.passGate}"));
  auto* tokText = new QPushButton(QStringLiteral("${flow.barcodeText}"));
  auto* tokFmt = new QPushButton(QStringLiteral("${flow.formatted}"));
  auto* tokIo = new QPushButton(QStringLiteral("io.Result"));
  up->setFixedWidth(28);
  down->setFixedWidth(28);
  up->setToolTip(QStringLiteral("上移选中行 · Alt+↑"));
  down->setToolTip(QStringLiteral("下移选中行 · Alt+↓"));
  dup->setToolTip(QStringLiteral("复制选中行 · Ctrl+D"));
  paste->setToolTip(QStringLiteral("从剪贴板粘贴多行绑定 · Ctrl+Shift+V · 每行 name,type,binding,emptyDefault"));
  copyClip->setToolTip(QStringLiteral("复制选中行到剪贴板 · Ctrl+Shift+C · CSV"));
  clearEmpty->setToolTip(QStringLiteral("删除 name/binding 皆空的行"));
  toOther->setToolTip(QStringLiteral("移到另一张表 · Ctrl+Shift+Tab"));
  fillDef->setToolTip(QStringLiteral("空 emptyDefault 补 BARCODE · Ctrl+E"));
  tokPass->setToolTip(QStringLiteral("写入当前行 binding · ${flow.passGate}"));
  tokText->setToolTip(QStringLiteral("写入当前行 binding · ${flow.barcodeText}"));
  tokFmt->setToolTip(QStringLiteral("写入当前行 binding · ${flow.formatted}"));
  tokIo->setToolTip(QStringLiteral("写入当前行 binding · ${flow.io.Result}"));
  for (auto* b : {tokPass, tokText, tokFmt, tokIo, copyClip, clearEmpty, toOther, fillDef})
    b->setStyleSheet(QStringLiteral("font-size:11px;"));
  rowBtns->addWidget(up);
  rowBtns->addWidget(down);
  rowBtns->addWidget(dup);
  rowBtns->addWidget(copyClip);
  rowBtns->addWidget(paste);
  rowBtns->addWidget(clearEmpty);
  rowBtns->addWidget(toOther);
  rowBtns->addWidget(fillDef);
  rowBtns->addWidget(tokPass);
  rowBtns->addWidget(tokText);
  rowBtns->addWidget(tokFmt);
  rowBtns->addWidget(tokIo);
  connect(up, &QPushButton::clicked, this, [this, table]() { moveSelectedRows(table, -1); });
  connect(down, &QPushButton::clicked, this, [this, table]() { moveSelectedRows(table, +1); });
  connect(dup, &QPushButton::clicked, this, [this, table]() { duplicateSelectedRows(table); });
  connect(paste, &QPushButton::clicked, this, [this, table]() { pasteRows(table); });
  connect(copyClip, &QPushButton::clicked, this, [this, table]() { copySelectedRows(table); });
  connect(clearEmpty, &QPushButton::clicked, this, [this, table]() { clearEmptyRows(table); });
  connect(toOther, &QPushButton::clicked, this, [this, table]() { moveSelectedToOtherTable(table); });
  connect(fillDef, &QPushButton::clicked, this, [this, table]() { fillEmptyDefaults(table); });
  connect(tokPass, &QPushButton::clicked, this, [this, table]() {
    insertBindingToken(table, QStringLiteral("${flow.passGate}"));
  });
  connect(tokText, &QPushButton::clicked, this, [this, table]() {
    insertBindingToken(table, QStringLiteral("${flow.barcodeText}"));
  });
  connect(tokFmt, &QPushButton::clicked, this, [this, table]() {
    insertBindingToken(table, QStringLiteral("${flow.formatted}"));
  });
  connect(tokIo, &QPushButton::clicked, this, [this, table]() {
    insertBindingToken(table, QStringLiteral("${flow.io.Result}"));
  });
  auto* scUp = new QShortcut(QKeySequence(QStringLiteral("Alt+Up")), table);
  connect(scUp, &QShortcut::activated, this, [this, table]() { moveSelectedRows(table, -1); });
  auto* scDn = new QShortcut(QKeySequence(QStringLiteral("Alt+Down")), table);
  connect(scDn, &QShortcut::activated, this, [this, table]() { moveSelectedRows(table, +1); });
  auto* scDup = new QShortcut(QKeySequence(QStringLiteral("Ctrl+D")), table);
  connect(scDup, &QShortcut::activated, this, [this, table]() { duplicateSelectedRows(table); });
  auto* scPaste = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+V")), table);
  connect(scPaste, &QShortcut::activated, this, [this, table]() { pasteRows(table); });
  auto* scE = new QShortcut(QKeySequence(QStringLiteral("Ctrl+E")), table);
  connect(scE, &QShortcut::activated, this, [this, table]() { fillEmptyDefaults(table); });
  auto* scClrDef = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+E")), table);
  connect(scClrDef, &QShortcut::activated, this, [this, table]() { clearEmptyDefaults(table); });
  auto* scA = new QShortcut(QKeySequence(QStringLiteral("Ctrl+A")), table);
  connect(scA, &QShortcut::activated, this, [this, table]() { selectAllRows(table); });
  auto* scCopy = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), table);
  connect(scCopy, &QShortcut::activated, this, [this, table]() { copySelectedRows(table); });
  auto* scCut = new QShortcut(QKeySequence(QStringLiteral("Ctrl+X")), table);
  connect(scCut, &QShortcut::activated, this, [this, table]() { cutSelectedRows(table); });
  auto* scOther = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+Tab")), table);
  connect(scOther, &QShortcut::activated, this, [this, table]() { moveSelectedToOtherTable(table); });
  auto* scHome = new QShortcut(QKeySequence(Qt::Key_Home), table);
  connect(scHome, &QShortcut::activated, this, [table]() {
    if (table->rowCount() > 0) {
      table->setCurrentCell(0, table->currentColumn() < 0 ? 0 : table->currentColumn());
      table->selectRow(0);
    }
  });
  auto* scEnd = new QShortcut(QKeySequence(Qt::Key_End), table);
  connect(scEnd, &QShortcut::activated, this, [table]() {
    if (table->rowCount() > 0) {
      const int r = table->rowCount() - 1;
      table->setCurrentCell(r, table->currentColumn() < 0 ? 0 : table->currentColumn());
      table->selectRow(r);
    }
  });
  auto* scRev = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+Y")), table);
  connect(scRev, &QShortcut::activated, this, [this, table]() { reverseRows(table); });
  auto* scSort = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+S")), table);
  connect(scSort, &QShortcut::activated, this, [this, table]() { sortRowsByName(table); });
  auto* scDupOther = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+D")), table);
  connect(scDupOther, &QShortcut::activated, this, [this, table]() { duplicateSelectedToOtherTable(table); });
  auto* scTop = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Home")), table);
  connect(scTop, &QShortcut::activated, this, [this, table]() { moveSelectedToEdge(table, -1); });
  auto* scBot = new QShortcut(QKeySequence(QStringLiteral("Ctrl+End")), table);
  connect(scBot, &QShortcut::activated, this, [this, table]() { moveSelectedToEdge(table, +1); });
  auto* scClrEmpty = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+L")), table);
  connect(scClrEmpty, &QShortcut::activated, this, [this, table]() { clearEmptyRows(table); });
  auto* scDed = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+U")), table);
  connect(scDed, &QShortcut::activated, this, [this, table]() { dedupeRowsByName(table); });
  {
    const char* toks[] = {"${flow.passGate}", "${flow.barcodeText}", "${flow.formatted}",
                          "${flow.io.Result}"};
    for (int i = 0; i < 4; ++i) {
      auto* sc = new QShortcut(QKeySequence(Qt::ALT | static_cast<int>(Qt::Key_1 + i)), table);
      const QString tok = QString::fromUtf8(toks[i]);
      connect(sc, &QShortcut::activated, this, [this, table, tok]() {
        const int row = table->currentRow();
        if (row < 0) return;
        table->setItem(row, 2, new QTableWidgetItem(tok));
        table->setToolTip(QStringLiteral("binding %1 · Alt+1..4").arg(tok));
      });
    }
  }
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


void FlowIoDialog::copySelectedRows(QTableWidget* table) {
  if (!table) return;
  const auto ranges = table->selectionModel() ? table->selectionModel()->selectedRows()
                                              : QModelIndexList{};
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  if (rows.isEmpty() && table->currentRow() >= 0) rows.push_back(table->currentRow());
  if (rows.isEmpty()) return;
  std::sort(rows.begin(), rows.end());
  QStringList lines;
  for (int r : rows) {
    QStringList cols;
    for (int c = 0; c < table->columnCount(); ++c) {
      QTableWidgetItem* it = table->item(r, c);
      cols << (it ? it->text() : QString());
    }
    lines << cols.join(QLatin1Char(','));
  }
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
}

void FlowIoDialog::cutSelectedRows(QTableWidget* table) {
  if (!table) return;
  const auto ranges = table->selectionModel() ? table->selectionModel()->selectedRows()
                                              : QModelIndexList{};
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  if (rows.isEmpty() && table->currentRow() >= 0) rows.push_back(table->currentRow());
  if (rows.isEmpty()) {
    table->setToolTip(QStringLiteral("无选中行 · Ctrl+X"));
    return;
  }
  std::sort(rows.begin(), rows.end());
  QStringList lines;
  for (int r : rows) {
    QStringList cols;
    for (int c = 0; c < table->columnCount(); ++c) {
      QTableWidgetItem* it = table->item(r, c);
      cols << (it ? it->text() : QString());
    }
    lines << cols.join(QLatin1Char(','));
  }
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
  std::sort(rows.begin(), rows.end(), std::greater<int>());
  for (int r : rows) table->removeRow(r);
  table->setToolTip(QStringLiteral("已剪切 I/O 行 %1 · Ctrl+X · Ctrl+Shift+V 粘贴").arg(lines.size()));
}

void FlowIoDialog::clearEmptyRows(QTableWidget* table) {
  if (!table) return;
  for (int r = table->rowCount() - 1; r >= 0; --r) {
    auto* n = table->item(r, 0);
    auto* b = table->item(r, 2);
    const QString name = n ? n->text().trimmed() : QString();
    const QString bind = b ? b->text().trimmed() : QString();
    if (name.isEmpty() && bind.isEmpty()) table->removeRow(r);
  }
}


void FlowIoDialog::fillEmptyDefaults(QTableWidget* table) {
  if (!table) return;
  int n = 0;
  for (int r = 0; r < table->rowCount(); ++r) {
    auto* name = table->item(r, 0);
    auto* def = table->item(r, 3);
    if (!name || name->text().trimmed().isEmpty()) continue;
    if (!def) {
      def = new QTableWidgetItem;
      table->setItem(r, 3, def);
    }
    if (def->text().trimmed().isEmpty()) {
      def->setText(QStringLiteral("BARCODE"));
      ++n;
    }
  }
  table->setToolTip(QStringLiteral("已补 emptyDefault %1 行 · Ctrl+E").arg(n));
}

void FlowIoDialog::selectAllRows(QTableWidget* table) {
  if (!table) return;
  table->selectAll();
}


void FlowIoDialog::clearEmptyDefaults(QTableWidget* table) {
  if (!table) return;
  int n = 0;
  for (int r = 0; r < table->rowCount(); ++r) {
    QTableWidgetItem* it = table->item(r, 3);
    if (!it) continue;
    if (it->text().trimmed().isEmpty()) continue;
    it->setText(QString());
    ++n;
  }
  table->setToolTip(QStringLiteral("已清 emptyDefault %1 行 · Ctrl+Shift+E").arg(n));
}

void FlowIoDialog::exportBindingsJson() {
  QJsonObject root;
  auto pack = [](QTableWidget* table) {
    QJsonArray arr;
    if (!table) return arr;
    for (int r = 0; r < table->rowCount(); ++r) {
      const QString name = table->item(r, 0) ? table->item(r, 0)->text().trimmed() : QString();
      if (name.isEmpty()) continue;
      QJsonObject o;
      o.insert(QStringLiteral("name"), name);
      o.insert(QStringLiteral("type"),
               table->item(r, 1) ? table->item(r, 1)->text().trimmed() : QStringLiteral("ANY"));
      o.insert(QStringLiteral("binding"),
               table->item(r, 2) ? table->item(r, 2)->text().trimmed() : QString());
      const QString ed = table->item(r, 3) ? table->item(r, 3)->text().trimmed() : QString();
      if (!ed.isEmpty()) o.insert(QStringLiteral("emptyDefault"), ed);
      arr.append(o);
    }
    return arr;
  };
  root.insert(QStringLiteral("inputs"), pack(inTable_));
  root.insert(QStringLiteral("outputs"), pack(outTable_));
  const QByteArray bytes = QJsonDocument(root).toJson(QJsonDocument::Compact);
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(QString::fromUtf8(bytes));
  if (inTable_)
    inTable_->setToolTip(QStringLiteral("已导出 I/O JSON · Ctrl+Shift+J"));
}

void FlowIoDialog::applyJsonArray(QTableWidget* table, const QJsonArray& arr) {
  if (!table) return;
  table->setRowCount(0);
  for (const QJsonValue& v : arr) {
    const QJsonObject o = v.toObject();
    const QString name = o.value(QStringLiteral("name")).toString().trimmed();
    if (name.isEmpty()) continue;
    const int r = table->rowCount();
    table->insertRow(r);
    table->setItem(r, 0, new QTableWidgetItem(name));
    table->setItem(r, 1, new QTableWidgetItem(
        o.value(QStringLiteral("type")).toString(QStringLiteral("ANY"))));
    table->setItem(r, 2, new QTableWidgetItem(
        o.value(QStringLiteral("binding")).toString()));
    table->setItem(r, 3, new QTableWidgetItem(
        o.value(QStringLiteral("emptyDefault")).toString()));
  }
}

void FlowIoDialog::importBindingsJson() {
  const QString raw = QGuiApplication::clipboard()
                          ? QGuiApplication::clipboard()->text().trimmed()
                          : QString();
  if (raw.isEmpty()) {
    if (inTable_) inTable_->setToolTip(QStringLiteral("剪贴板空 · Ctrl+Shift+O"));
    return;
  }
  QJsonParseError err;
  const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &err);
  if (err.error != QJsonParseError::NoError || !doc.isObject()) {
    if (inTable_)
      inTable_->setToolTip(QStringLiteral("JSON无效 · Ctrl+Shift+O · %1").arg(err.errorString()));
    return;
  }
  const QJsonObject root = doc.object();
  int nIn = 0, nOut = 0;
  if (root.contains(QStringLiteral("inputs")) && root.value(QStringLiteral("inputs")).isArray()) {
    const QJsonArray a = root.value(QStringLiteral("inputs")).toArray();
    applyJsonArray(inTable_, a);
    nIn = inTable_ ? inTable_->rowCount() : 0;
  }
  if (root.contains(QStringLiteral("outputs")) && root.value(QStringLiteral("outputs")).isArray()) {
    const QJsonArray a = root.value(QStringLiteral("outputs")).toArray();
    applyJsonArray(outTable_, a);
    nOut = outTable_ ? outTable_->rowCount() : 0;
  }
  if (inTable_)
    inTable_->setToolTip(QStringLiteral("已导入 I/O JSON · in=%1 out=%2 · Ctrl+Shift+O").arg(nIn).arg(nOut));
}





void FlowIoDialog::sortRowsByName(QTableWidget* table) {
  if (!table || table->rowCount() < 2) {
    if (table) table->setToolTip(QStringLiteral("行不足 · Ctrl+Shift+S"));
    return;
  }
  const int n = table->rowCount();
  const int cols = table->columnCount();
  struct Row { QString name; QList<QTableWidgetItem*> cells; };
  QList<Row> rows;
  rows.reserve(n);
  table->blockSignals(true);
  for (int r = 0; r < n; ++r) {
    Row row;
    row.name = table->item(r, 0) ? table->item(r, 0)->text() : QString();
    for (int c = 0; c < cols; ++c) row.cells << table->takeItem(r, c);
    rows << row;
  }
  std::stable_sort(rows.begin(), rows.end(),
                   [](const Row& a, const Row& b) {
                     return QString::localeAwareCompare(a.name, b.name) < 0;
                   });
  for (int r = 0; r < n; ++r) {
    for (int c = 0; c < cols; ++c) table->setItem(r, c, rows[r].cells[c]);
  }
  table->blockSignals(false);
  table->setToolTip(QStringLiteral("已按名排序 %1 · Ctrl+Shift+S").arg(n));
}

void FlowIoDialog::reverseRows(QTableWidget* table) {
  if (!table || table->rowCount() < 2) {
    if (table) table->setToolTip(QStringLiteral("行不足 · Ctrl+Shift+Y"));
    return;
  }
  const int n = table->rowCount();
  const int cols = table->columnCount();
  table->blockSignals(true);
  for (int i = 0; i < n / 2; ++i) {
    const int j = n - 1 - i;
    for (int c = 0; c < cols; ++c) {
      QTableWidgetItem* a = table->takeItem(i, c);
      QTableWidgetItem* b = table->takeItem(j, c);
      table->setItem(i, c, b);
      table->setItem(j, c, a);
    }
  }
  table->blockSignals(false);
  table->setToolTip(QStringLiteral("绑定已反序 %1 · Ctrl+Shift+Y").arg(n));
}




void FlowIoDialog::dedupeRowsByName(QTableWidget* table) {
  if (!table || table->rowCount() < 2) {
    if (table) table->setToolTip(QStringLiteral("行不足 · Ctrl+Shift+U"));
    return;
  }
  QSet<QString> seen;
  QList<int> drop;
  for (int r = 0; r < table->rowCount(); ++r) {
    const QString name = table->item(r, 0) ? table->item(r, 0)->text().trimmed() : QString();
    if (name.isEmpty()) continue;
    if (seen.contains(name)) drop << r;
    else seen.insert(name);
  }
  if (drop.isEmpty()) {
    table->setToolTip(QStringLiteral("无重名 · Ctrl+Shift+U"));
    return;
  }
  for (int i = drop.size() - 1; i >= 0; --i) table->removeRow(drop[i]);
  table->setToolTip(QStringLiteral("已去重 −%1 · 剩 %2 · Ctrl+Shift+U")
                        .arg(drop.size())
                        .arg(table->rowCount()));
}

void FlowIoDialog::moveSelectedToEdge(QTableWidget* table, int edge) {
  if (!table || table->rowCount() < 2) {
    if (table) table->setToolTip(QStringLiteral("行不足 · Ctrl+Home/End"));
    return;
  }
  const auto ranges = table->selectionModel() ? table->selectionModel()->selectedRows()
                                              : QModelIndexList{};
  if (ranges.isEmpty()) {
    table->setToolTip(QStringLiteral("未选中 · Ctrl+Home/End"));
    return;
  }
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  std::sort(rows.begin(), rows.end());
  const int cols = table->columnCount();
  QList<QList<QTableWidgetItem*>> taken;
  table->blockSignals(true);
  for (int i = rows.size() - 1; i >= 0; --i) {
    const int r = rows[i];
    QList<QTableWidgetItem*> cells;
    for (int c = 0; c < cols; ++c) cells << table->takeItem(r, c);
    taken.prepend(cells);
    table->removeRow(r);
  }
  int insertAt = edge < 0 ? 0 : table->rowCount();
  for (const auto& cells : taken) {
    table->insertRow(insertAt);
    for (int c = 0; c < cols; ++c) table->setItem(insertAt, c, cells[c]);
    ++insertAt;
  }
  table->blockSignals(false);
  table->clearSelection();
  const int n = taken.size();
  const int start = edge < 0 ? 0 : table->rowCount() - n;
  for (int i = 0; i < n; ++i) table->selectRow(start + i);
  table->setToolTip(QStringLiteral("已%1 %2 行 · Ctrl+%3")
                        .arg(edge < 0 ? QStringLiteral("置顶") : QStringLiteral("置底"))
                        .arg(n)
                        .arg(edge < 0 ? QStringLiteral("Home") : QStringLiteral("End")));
}

void FlowIoDialog::duplicateSelectedToOtherTable(QTableWidget* from) {
  if (!from || !inTable_ || !outTable_) return;
  QTableWidget* to = (from == inTable_) ? outTable_ : inTable_;
  const auto ranges = from->selectionModel() ? from->selectionModel()->selectedRows()
                                             : QModelIndexList{};
  if (ranges.isEmpty()) {
    from->setToolTip(QStringLiteral("未选中 · Ctrl+Shift+D"));
    return;
  }
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  std::sort(rows.begin(), rows.end());
  int n = 0;
  for (int r : rows) {
    const int dest = to->rowCount();
    to->insertRow(dest);
    for (int c = 0; c < from->columnCount() && c < to->columnCount(); ++c) {
      auto* it = from->item(r, c);
      to->setItem(dest, c, new QTableWidgetItem(it ? it->text() : QString()));
    }
    ++n;
  }
  if (to->rowCount() > 0) {
    to->selectRow(to->rowCount() - 1);
    to->setFocus(Qt::OtherFocusReason);
  }
  from->setToolTip(QStringLiteral("已复制到对表 %1 行 · Ctrl+Shift+D").arg(n));
}

void FlowIoDialog::moveSelectedToOtherTable(QTableWidget* from) {
  if (!from || !inTable_ || !outTable_) return;
  QTableWidget* to = (from == inTable_) ? outTable_ : inTable_;
  const auto ranges = from->selectionModel() ? from->selectionModel()->selectedRows()
                                             : QModelIndexList{};
  if (ranges.isEmpty()) return;
  QList<int> rows;
  for (const QModelIndex& ix : ranges) rows.push_back(ix.row());
  std::sort(rows.begin(), rows.end());
  QList<QStringList> moved;
  for (int r : rows) {
    QStringList cells;
    for (int c = 0; c < from->columnCount(); ++c) {
      auto* it = from->item(r, c);
      cells << (it ? it->text() : QString());
    }
    moved << cells;
  }
  for (int i = rows.size() - 1; i >= 0; --i) from->removeRow(rows[i]);
  for (const QStringList& cells : moved) {
    const int r = to->rowCount();
    to->insertRow(r);
    for (int c = 0; c < cells.size() && c < to->columnCount(); ++c)
      to->setItem(r, c, new QTableWidgetItem(cells[c]));
  }
  if (to->rowCount() > 0) {
    to->selectRow(to->rowCount() - 1);
    to->setFocus(Qt::OtherFocusReason);
  }
  from->setToolTip(QStringLiteral("已移到对表 %1 行 · Ctrl+Shift+Tab").arg(moved.size()));
}

}  // namespace sieans_qt
