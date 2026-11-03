#include "VarWatchPanel.hpp"

#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QHeaderView>
#include <QAbstractItemView>
#include <QColor>
#include <QClipboard>
#include <QApplication>
#include <QToolTip>
#include <QCursor>
#include <QShortcut>
#include <QKeySequence>
#include <QKeyEvent>
#include <QEvent>

namespace sieans_qt {

VarWatchPanel::VarWatchPanel(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  auto* title = new QLabel(QStringLiteral("变量监视"));
  title->setObjectName(QStringLiteral("sectionTitle"));
  title->setToolTip(QStringLiteral("变量监视 · passGate/urlOk/lastRecv 高亮 · F2 聚焦表格"));
  lay->addWidget(title);
  table_ = new QTableWidget(0, 2);
  table_->setHorizontalHeaderLabels(
      {QStringLiteral("变量"), QStringLiteral("值")});
  table_->horizontalHeader()->setStretchLastSection(true);
  table_->verticalHeader()->setVisible(false);
  table_->setAlternatingRowColors(true);
  table_->setSelectionBehavior(QAbstractItemView::SelectRows);
  table_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  lay->addWidget(table_, 1);
  connect(table_, &QTableWidget::cellDoubleClicked, this,
          [this](int row, int) {
            if (!table_) return;
            auto* val = table_->item(row, 1);
            auto* key = table_->item(row, 0);
            if (!val) return;
            const QString raw = key ? vars_.value(key->text()).toString() : val->text();
            if (auto* clip = QApplication::clipboard()) {
              clip->setText(raw.isEmpty() ? val->text() : raw);
              QToolTip::showText(QCursor::pos(),
                                 QStringLiteral("已复制 %1").arg(key ? key->text() : QStringLiteral("值")),
                                 table_);
            }
          });
  table_->setToolTip(QStringLiteral("双击或 Ctrl+C/C 复制 · Ctrl+A 全选 · Home/End/PgUp/PgDn · Esc 取消选中 · F2 聚焦表"));
  table_->installEventFilter(this);
  setStatusTip(QStringLiteral("变量监视 · 双击/Ctrl+C/C 复制 · Home/End/PgUp/PgDn · Esc 取消选中 · F2 聚焦 · Ctrl+A 全选 · passGate/urlOk/lastRecv 高亮"));
  keys_ = {QStringLiteral("barcodeCount"), QStringLiteral("barcodeText"),
           QStringLiteral("barcodeAll"), QStringLiteral("barcodeOk"),
           QStringLiteral("passGate"), QStringLiteral("urlOk"),
           QStringLiteral("formatted"),
           QStringLiteral("commPayload"), QStringLiteral("lastRecv")};
  auto copySel = [this]() {
    if (!table_) return;
    const int row = table_->currentRow();
    if (row < 0) return;
    auto* val = table_->item(row, 1);
    auto* key = table_->item(row, 0);
    if (!val) return;
    const QString raw = key ? vars_.value(key->text()).toString() : val->text();
    if (auto* clip = QApplication::clipboard()) {
      clip->setText(raw.isEmpty() ? val->text() : raw);
      QToolTip::showText(QCursor::pos(),
                         QStringLiteral("已复制 %1").arg(key ? key->text() : QStringLiteral("值")),
                         table_);
    }
  };
  auto* sc = new QShortcut(QKeySequence::Copy, this);
  connect(sc, &QShortcut::activated, this, copySel);
  {
    auto* scC = new QShortcut(QKeySequence(Qt::Key_C), table_);
    scC->setContext(Qt::WidgetWithChildrenShortcut);
    connect(scC, &QShortcut::activated, this, copySel);
  }
  rebuild();
}


bool VarWatchPanel::eventFilter(QObject* obj, QEvent* event) {
  if (obj == table_ && event->type() == QEvent::KeyPress && table_) {
    auto* ke = static_cast<QKeyEvent*>(event);
        if (ke->key() == Qt::Key_F2) {
      table_->setFocus(Qt::ShortcutFocusReason);
      return true;
    }
if (ke->key() == Qt::Key_Escape) {
      table_->clearSelection();
      table_->setCurrentCell(-1, -1);
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) && ke->key() == Qt::Key_A) {
      table_->selectAll();
      return true;
    }
    if (ke->key() == Qt::Key_Home || ke->key() == Qt::Key_End ||
        ke->key() == Qt::Key_PageUp || ke->key() == Qt::Key_PageDown) {
      const int rows = table_->rowCount();
      if (rows <= 0) return true;
      int row = table_->currentRow();
      if (row < 0) row = 0;
      if (ke->key() == Qt::Key_Home) row = 0;
      else if (ke->key() == Qt::Key_End) row = rows - 1;
      else if (ke->key() == Qt::Key_PageUp) row = qMax(0, row - 5);
      else row = qMin(rows - 1, row + 5);
      table_->setCurrentCell(row, 0);
      table_->scrollToItem(table_->item(row, 0));
      return true;
    }
  }
  return QWidget::eventFilter(obj, event);
}

void VarWatchPanel::setWatchKeys(const QStringList& keys) {
  if (!keys.isEmpty()) keys_ = keys;
  rebuild();
}

void VarWatchPanel::setVariables(const QVariantMap& vars) {
  vars_ = vars;
  rebuild();
}

void VarWatchPanel::rebuild() {
  QStringList show = keys_;
  for (auto it = vars_.begin(); it != vars_.end(); ++it) {
    if (!show.contains(it.key())) show << it.key();
  }
  table_->setRowCount(0);
  for (const QString& k : show) {
    const int row = table_->rowCount();
    table_->insertRow(row);
    table_->setItem(row, 0, new QTableWidgetItem(k));
    const QString raw = vars_.value(k).toString();
    const QString shown = raw.size() > 96 ? raw.left(93) + QStringLiteral("…") : raw;
    auto* val = new QTableWidgetItem(shown);
    if (raw.size() > 96) val->setToolTip(raw);
    // OK/NG tint for gate-ish vars
    if (k.contains(QStringLiteral("pass"), Qt::CaseInsensitive) ||
        k.contains(QStringLiteral("Gate"), Qt::CaseInsensitive) ||
        k.endsWith(QStringLiteral("Ok"))) {
      const bool okish = vars_.value(k).toInt() != 0 || vars_.value(k).toBool() ||
                         (raw != QLatin1String("0") && !raw.isEmpty() &&
                          raw.compare(QStringLiteral("false"), Qt::CaseInsensitive) != 0 &&
                          raw.compare(QStringLiteral("NG"), Qt::CaseInsensitive) != 0);
      val->setForeground(okish ? QColor(theme::OK) : QColor(theme::NG));
      if (k.compare(QStringLiteral("passGate"), Qt::CaseInsensitive) == 0) {
        QFont f = val->font();
        f.setBold(true);
        val->setFont(f);
      }
    }
    table_->setItem(row, 1, val);
    if (k.compare(QStringLiteral("passGate"), Qt::CaseInsensitive) == 0 ||
        k.compare(QStringLiteral("urlOk"), Qt::CaseInsensitive) == 0 ||
        k.compare(QStringLiteral("lastRecv"), Qt::CaseInsensitive) == 0) {
      if (auto* keyItem = table_->item(row, 0)) {
        QFont f = keyItem->font();
        f.setBold(true);
        keyItem->setFont(f);
      }
      QFont vf = val->font();
      vf.setBold(true);
      val->setFont(vf);
    }
  }
}

}  // namespace sieans_qt
