#include "VarWatchPanel.hpp"

#include "Theme.hpp"

#include <QVBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QHeaderView>
#include <QAbstractItemView>
#include <QItemSelectionModel>
#include <QColor>
#include <algorithm>
#include <QClipboard>
#include <QApplication>
#include <QToolTip>
#include <QCursor>
#include <QShortcut>
#include <QKeySequence>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QEvent>
#include <QRegularExpression>
#include <QSet>
#include <QChar>

namespace sieans_qt {

VarWatchPanel::VarWatchPanel(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  auto* title = new QLabel(QStringLiteral("变量监视"));
  title->setObjectName(QStringLiteral("sectionTitle"));
  title->setToolTip(QStringLiteral("变量监视 · passGate/urlOk/lastRecv 高亮 · F2 聚焦表格 · 双击复制 · Ctrl+F 过滤"));
  lay->addWidget(title);
  filterEdit_ = new QLineEdit;
  filterEdit_->setObjectName(QStringLiteral("varWatchFilter"));
  filterEdit_->setPlaceholderText(QStringLiteral("过滤变量名/值 · Ctrl+F · Esc 清空"));
  filterEdit_->setClearButtonEnabled(true);
  filterEdit_->setToolTip(QStringLiteral("变量监视过滤 · 匹配键或值 · Ctrl+F 聚焦 · Esc/Ctrl+L 清空"));
  lay->addWidget(filterEdit_);
  connect(filterEdit_, &QLineEdit::textChanged, this, [this](const QString& s) {
    filter_ = s.trimmed();
    rebuild();
  });
  {
    auto* scF = new QShortcut(QKeySequence(QStringLiteral("Ctrl+F")), this);
    connect(scF, &QShortcut::activated, this, [this]() {
      if (!filterEdit_) return;
      filterEdit_->setFocus(Qt::ShortcutFocusReason);
      filterEdit_->selectAll();
    });
    auto* scL = new QShortcut(QKeySequence(QStringLiteral("Ctrl+L")), this);
    connect(scL, &QShortcut::activated, this, [this]() {
      if (filterEdit_) filterEdit_->clear();
    });
    auto* scExp = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), this);
    connect(scExp, &QShortcut::activated, this, &VarWatchPanel::exportFiltered);
    auto* scKv = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+K")), this);
    connect(scKv, &QShortcut::activated, this, &VarWatchPanel::copyKeyEqualsValue);
    auto* scTok = new QShortcut(QKeySequence(QStringLiteral("Ctrl+I")), this);
    connect(scTok, &QShortcut::activated, this, &VarWatchPanel::copyFlowToken);
    auto* scJson = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+J")), this);
    connect(scJson, &QShortcut::activated, this, &VarWatchPanel::exportJsonFiltered);
    auto* scAdd = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+V")), this);
    connect(scAdd, &QShortcut::activated, this, &VarWatchPanel::addKeysFromClipboard);
    auto* scIns = new QShortcut(QKeySequence(Qt::Key_Insert), this);
    connect(scIns, &QShortcut::activated, this, &VarWatchPanel::addKeysFromClipboard);
    auto* scRm = new QShortcut(QKeySequence(Qt::Key_Delete), this);
    connect(scRm, &QShortcut::activated, this, &VarWatchPanel::removeSelectedKeys);
    auto* scX = new QShortcut(QKeySequence(QStringLiteral("Ctrl+X")), this);
    connect(scX, &QShortcut::activated, this, &VarWatchPanel::cutSelectedKeys);
    auto* scHost = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+H")), this);
    connect(scHost, &QShortcut::activated, this, &VarWatchPanel::copyHostWatchKeys);
    auto* scRev = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+Y")), this);
    connect(scRev, &QShortcut::activated, this, &VarWatchPanel::reverseWatchKeys);
    auto* scHome = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Home")), this);
    connect(scHome, &QShortcut::activated, this, [this]() { moveSelectedToEdge(-1); });
    auto* scEnd = new QShortcut(QKeySequence(QStringLiteral("Ctrl+End")), this);
    connect(scEnd, &QShortcut::activated, this, [this]() { moveSelectedToEdge(+1); });
  }
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
            QString kn;
            if (key) {
              kn = key->data(Qt::UserRole).toString();
              if (kn.isEmpty()) kn = key->text();
            }
            const QString raw = kn.isEmpty() ? val->text() : vars_.value(kn).toString();
            if (auto* clip = QApplication::clipboard()) {
              clip->setText(raw.isEmpty() ? val->text() : raw);
              QToolTip::showText(QCursor::pos(),
                                 QStringLiteral("已复制 %1").arg(kn.isEmpty() ? QStringLiteral("值") : kn),
                                 table_);
            }
          });
  table_->setToolTip(QStringLiteral("双击或 Ctrl+C/C 复制 · 中键 ${flow} · 右键键=值 · Ctrl+A 全选 · Home/End/PgUp/PgDn · Alt+↑↓ 调序 · Ctrl+Home/End 置顶/置底 · Esc 取消选中 · F2 聚焦表 · Ctrl+Shift+J JSON"));
  table_->installEventFilter(this);
  if (filterEdit_) filterEdit_->installEventFilter(this);
  setStatusTip(QStringLiteral("变量监视 · ★=Host条 · 过滤 Ctrl+F · 双击/Ctrl+C/C 复制 · Ctrl+Shift+C 导出 · Ctrl+Shift+K键=值 · Ctrl+I ${flow.x} · Ctrl+Shift+J JSON · 中键token/右键键=值 · Home/End/PgUp/PgDn · Alt+↑↓ 调序 · Ctrl+Home/End 置顶/置底 · Ctrl+X 剪切 · Ctrl+Shift+H ★键 · Ctrl+Shift+Y 反序 · Esc 取消选中/清过滤 · F2 聚焦 · Ctrl+A 全选 · passGate/urlOk/lastRecv 高亮"));
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
    QString kn;
    if (key) {
      kn = key->data(Qt::UserRole).toString();
      if (kn.isEmpty()) kn = key->text();
    }
    const QString raw = kn.isEmpty() ? val->text() : vars_.value(kn).toString();
    if (auto* clip = QApplication::clipboard()) {
      clip->setText(raw.isEmpty() ? val->text() : raw);
      QToolTip::showText(QCursor::pos(),
                         QStringLiteral("已复制 %1").arg(kn.isEmpty() ? QStringLiteral("值") : kn),
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
  if (obj == filterEdit_ && event->type() == QEvent::KeyPress) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_Escape) {
      filterEdit_->clear();
      if (table_) table_->setFocus(Qt::OtherFocusReason);
      return true;
    }
    if (ke->key() == Qt::Key_Down && table_ && table_->rowCount() > 0) {
      table_->setFocus(Qt::OtherFocusReason);
      table_->setCurrentCell(0, 0);
      return true;
    }
  }
  if (obj == table_ && event->type() == QEvent::MouseButtonDblClick && table_) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton) {
      const QPoint pos = me->position().toPoint();
      if (auto* hit = table_->itemAt(pos)) {
        if (auto* keyItem = table_->item(hit->row(), 0)) {
          const QString rawKey = keyItem->data(Qt::UserRole).toString();
          emit hostWatchToggleRequested(rawKey.isEmpty() ? keyItem->text() : rawKey);
          return true;
        }
      }
    }
  }
  if (obj == table_ && event->type() == QEvent::MouseButtonRelease && table_) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::MiddleButton) {
      copyFlowToken();
      return true;
    }
    if (me->button() == Qt::RightButton) {
      copyKeyEqualsValue();
      return true;
    }
  }
  if (obj == table_ && event->type() == QEvent::KeyPress && table_) {
    auto* ke = static_cast<QKeyEvent*>(event);
    if (ke->key() == Qt::Key_F2) {
      table_->setFocus(Qt::ShortcutFocusReason);
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) && ke->key() == Qt::Key_F) {
      if (filterEdit_) {
        filterEdit_->setFocus(Qt::ShortcutFocusReason);
        filterEdit_->selectAll();
      }
      return true;
    }
    if (ke->key() == Qt::Key_Escape) {
      if (filterEdit_ && !filterEdit_->text().isEmpty()) {
        filterEdit_->clear();
        return true;
      }
      table_->clearSelection();
      table_->setCurrentCell(-1, -1);
      return true;
    }
    if ((ke->modifiers() & Qt::ControlModifier) && ke->key() == Qt::Key_A) {
      table_->selectAll();
      return true;
    }
    if (ke->key() == Qt::Key_Space) {
      const int row = table_->currentRow();
      auto* it = row >= 0 ? table_->item(row, 0) : nullptr;
      if (it && !it->text().isEmpty()) {
        const QString rawKey = it->data(Qt::UserRole).toString();
        emit hostWatchToggleRequested(rawKey.isEmpty() ? it->text() : rawKey);
        return true;
      }
    }
    if ((ke->key() == Qt::Key_Up || ke->key() == Qt::Key_Down) &&
        (ke->modifiers() & Qt::AltModifier)) {
      moveSelectedKey(ke->key() == Qt::Key_Up ? -1 : +1);
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

void VarWatchPanel::setKeyList(const QStringList& keys) {
  QStringList next;
  for (const QString& k : keys) {
    const QString t = k.trimmed();
    if (!t.isEmpty() && !next.contains(t)) next << t;
  }
  if (!next.isEmpty()) keys_ = next;
  rebuild();
}

void VarWatchPanel::setWatchKeys(const QStringList& keys) {
  hostWatch_ = keys;
  // Prefer host-watched keys at top of the table; keep defaults for the rest.
  if (!keys.isEmpty()) {
    QStringList ordered = keys;
    for (const QString& k : keys_)
      if (!ordered.contains(k)) ordered << k;
    keys_ = ordered;
  }
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
  int matched = 0;
  for (const QString& k : show) {
    const QString rawProbe = vars_.value(k).toString();
    if (!filter_.isEmpty()) {
      if (!k.contains(filter_, Qt::CaseInsensitive) &&
          !rawProbe.contains(filter_, Qt::CaseInsensitive))
        continue;
    }
    ++matched;
    const int row = table_->rowCount();
    table_->insertRow(row);
    const bool watched = hostWatch_.contains(k);
    auto* keyItem = new QTableWidgetItem(watched ? (QStringLiteral("★ ") + k) : k);
    if (watched) {
      keyItem->setForeground(QColor(0x9a, 0xd0, 0xff));
      keyItem->setToolTip(QStringLiteral("Host 监视中 · Space/双击取消"));
      QFont kf = keyItem->font();
      kf.setBold(true);
      keyItem->setFont(kf);
    } else {
      keyItem->setToolTip(QStringLiteral("Space/双击加入 Host 监视条"));
    }
    keyItem->setData(Qt::UserRole, k);  // raw key without ★
    table_->setItem(row, 0, keyItem);
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
  if (filterEdit_) {
    filterEdit_->setToolTip(
        QStringLiteral("变量监视过滤 · 匹配 %1 · Ctrl+F 聚焦 · Esc/Ctrl+L 清空")
            .arg(matched));
  }
}


void VarWatchPanel::exportFiltered() {
  if (!table_) return;
  QStringList lines;
  for (int r = 0; r < table_->rowCount(); ++r) {
    auto* k = table_->item(r, 0);
    auto* v = table_->item(r, 1);
    if (!k) continue;
    QString kn = k->data(Qt::UserRole).toString();
    if (kn.isEmpty()) kn = k->text();
    const QString raw = vars_.value(kn).toString();
    lines << QStringLiteral("%1\t%2").arg(kn, raw.isEmpty() && v ? v->text() : raw);
  }
  if (auto* clip = QApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
  QToolTip::showText(QCursor::pos(),
                     QStringLiteral("已导出 %1 行 · Ctrl+Shift+C").arg(lines.size()), table_);
}

void VarWatchPanel::copyKeyEqualsValue() {
  if (!table_) return;
  const int row = table_->currentRow();
  if (row < 0) return;
  auto* k = table_->item(row, 0);
  if (!k) return;
  QString kn = k->data(Qt::UserRole).toString();
  if (kn.isEmpty()) kn = k->text();
  const QString raw = vars_.value(kn).toString();
  const QString line = QStringLiteral("%1=%2").arg(kn, raw);
  if (auto* clip = QApplication::clipboard()) clip->setText(line);
  QToolTip::showText(QCursor::pos(), QStringLiteral("已复制 %1 · Ctrl+Shift+K").arg(line.left(40)), table_);
}

void VarWatchPanel::copyFlowToken() {
  if (!table_) return;
  const int row = table_->currentRow();
  if (row < 0) return;
  auto* k = table_->item(row, 0);
  if (!k) return;
  QString kn = k->data(Qt::UserRole).toString();
  if (kn.isEmpty()) kn = k->text();
  const QString tok = QStringLiteral("${flow.%1}").arg(kn);
  if (auto* clip = QApplication::clipboard()) clip->setText(tok);
  QToolTip::showText(QCursor::pos(), QStringLiteral("已复制 %1 · Ctrl+I").arg(tok), table_);
}

void VarWatchPanel::exportJsonFiltered() {
  if (!table_) return;
  QStringList parts;
  for (int r = 0; r < table_->rowCount(); ++r) {
    if (table_->isRowHidden(r)) continue;
    auto* k = table_->item(r, 0);
    auto* v = table_->item(r, 1);
    if (!k) continue;
    QString key = k->data(Qt::UserRole).toString();
    if (key.isEmpty()) key = k->text();
    const QString val = vars_.value(key).toString();
    const QString shown = val.isEmpty() && v ? v->text() : val;
    QString esc = shown;
    esc.replace(QLatin1Char('\\'), QStringLiteral("\\\\"));
    esc.replace(QLatin1Char('"'), QStringLiteral("\\\""));
    parts << QStringLiteral("\"%1\": \"%2\"").arg(key, esc);
  }
  const QString body = QStringLiteral("{ %1 }").arg(parts.join(QStringLiteral(", ")));
  if (auto* clip = QApplication::clipboard()) clip->setText(body);
  QToolTip::showText(QCursor::pos(),
                     QStringLiteral("已导出 JSON %1 · Ctrl+Shift+J").arg(parts.size()), table_);
}


void VarWatchPanel::addKeysFromClipboard() {
  const QString clip = QApplication::clipboard() ? QApplication::clipboard()->text() : QString();
  if (clip.trimmed().isEmpty()) return;
  int added = 0;
  for (QString line : clip.split(QRegularExpression(QStringLiteral("[\n,;]+")))) {
    line = line.trimmed();
    if (line.isEmpty()) continue;
    // accept key=value or ${flow.key} or bare key
    if (line.startsWith(QLatin1String("${flow.")) && line.endsWith(QLatin1Char('}')))
      line = line.mid(7, line.size() - 8);
    const int eq = line.indexOf(QLatin1Char('='));
    if (eq > 0) line = line.left(eq).trimmed();
    const int tab = line.indexOf(QChar(QChar::Tabulation));
    if (tab > 0) line = line.left(tab).trimmed();
    if (line.isEmpty() || keys_.contains(line)) continue;
    keys_.push_back(line);
    ++added;
  }
  if (added > 0) {
    rebuild();
    emit watchListChanged(keys_);
    QToolTip::showText(QCursor::pos(),
                       QStringLiteral("已加入监视 %1 · Insert/Ctrl+Shift+V").arg(added), table_);
  }
}

void VarWatchPanel::removeSelectedKeys() {
  if (!table_) return;
  const auto ranges = table_->selectedRanges();
  QSet<int> rows;
  for (const auto& r : ranges)
    for (int i = r.topRow(); i <= r.bottomRow(); ++i) rows.insert(i);
  if (rows.isEmpty() && table_->currentRow() >= 0) rows.insert(table_->currentRow());
  if (rows.isEmpty()) return;
  QStringList remove;
  for (int row : rows) {
    auto* it = table_->item(row, 0);
    if (!it) continue;
    QString kn = it->data(Qt::UserRole).toString();
    if (kn.isEmpty()) kn = it->text();
    if (kn.startsWith(QStringLiteral("★ "))) kn = kn.mid(2);
    remove << kn;
  }
  int n = 0;
  for (const QString& kn : remove) {
    if (keys_.removeAll(kn) > 0) ++n;
    if (hostWatch_.contains(kn)) emit hostWatchToggleRequested(kn);
  }
  if (n > 0) {
    rebuild();
    emit watchListChanged(keys_);
    QToolTip::showText(QCursor::pos(),
                       QStringLiteral("已移除监视 %1 · Del").arg(n), table_);
  }
}


void VarWatchPanel::cutSelectedKeys() {
  if (!table_) return;
  QStringList lines;
  QStringList remove;
  const auto ranges = table_->selectionModel() ? table_->selectionModel()->selectedRows() : QModelIndexList();
  if (ranges.isEmpty()) {
    const int row = table_->currentRow();
    if (row < 0) {
      QToolTip::showText(QCursor::pos(), QStringLiteral("无选中 · Ctrl+X"), table_);
      return;
    }
    auto* it = table_->item(row, 0);
    if (!it) return;
    QString kn = it->data(Qt::UserRole).toString();
    if (kn.isEmpty()) kn = it->text().trimmed();
    if (kn.startsWith(QStringLiteral("★ "))) kn = kn.mid(2).trimmed();
    remove << kn;
    const QString val = vars_.value(kn).toString();
    lines << (val.isEmpty() ? kn : (kn + QLatin1Char('=') + val));
  } else {
    for (const QModelIndex& idx : ranges) {
      auto* it = table_->item(idx.row(), 0);
      if (!it) continue;
      QString kn = it->data(Qt::UserRole).toString();
      if (kn.isEmpty()) kn = it->text().trimmed();
      if (kn.startsWith(QStringLiteral("★ "))) kn = kn.mid(2).trimmed();
      if (kn.isEmpty() || remove.contains(kn)) continue;
      remove << kn;
      const QString val = vars_.value(kn).toString();
      lines << (val.isEmpty() ? kn : (kn + QLatin1Char('=') + val));
    }
  }
  if (remove.isEmpty()) return;
  if (auto* clip = QApplication::clipboard())
    clip->setText(lines.join(QLatin1Char('\n')));
  int n = 0;
  for (const QString& kn : remove) {
    if (keys_.removeAll(kn) > 0) ++n;
    if (hostWatch_.contains(kn)) emit hostWatchToggleRequested(kn);
  }
  if (n > 0) {
    rebuild();
    emit watchListChanged(keys_);
    QToolTip::showText(QCursor::pos(),
                       QStringLiteral("已剪切监视 %1 · Ctrl+X · Ctrl+Shift+V 粘贴").arg(n),
                       table_);
  }
}


void VarWatchPanel::copyHostWatchKeys() {
  QStringList keys = hostWatch_;
  if (keys.isEmpty()) {
    QToolTip::showText(QCursor::pos(), QStringLiteral("无 Host★ 监视 · Ctrl+Shift+H · Space 钉选"), table_);
    return;
  }
  if (auto* clip = QApplication::clipboard()) clip->setText(keys.join(QLatin1Char(',')));
  QToolTip::showText(QCursor::pos(),
                     QStringLiteral("已复制 Host★ 键 %1 · Ctrl+Shift+H").arg(keys.size()), table_);
}

void VarWatchPanel::reverseWatchKeys() {
  if (keys_.size() < 2) {
    QToolTip::showText(QCursor::pos(), QStringLiteral("监视不足 · Ctrl+Shift+Y"), table_);
    return;
  }
  std::reverse(keys_.begin(), keys_.end());
  rebuild();
  emit watchListChanged(keys_);
  QToolTip::showText(QCursor::pos(),
                     QStringLiteral("监视已反序 %1 · Ctrl+Shift+Y").arg(keys_.size()), table_);
}


void VarWatchPanel::moveSelectedKey(int delta) {
  if (!table_ || keys_.isEmpty() || delta == 0) return;
  const int row = table_->currentRow();
  if (row < 0) return;
  auto* keyItem = table_->item(row, 0);
  if (!keyItem) return;
  QString kn = keyItem->data(Qt::UserRole).toString();
  if (kn.isEmpty()) kn = keyItem->text().trimmed();
  if (kn.startsWith(QStringLiteral("★ "))) kn = kn.mid(2).trimmed();
  const int idx = keys_.indexOf(kn);
  if (idx < 0) {
    QToolTip::showText(QCursor::pos(), QStringLiteral("非监视列表键 · 无法调序"), table_);
    return;
  }
  const int dest = idx + delta;
  if (dest < 0 || dest >= keys_.size()) {
    QToolTip::showText(QCursor::pos(), QStringLiteral("已到边界 · Alt+↑↓"), table_);
    return;
  }
  keys_.swapItemsAt(idx, dest);
  rebuild();
  for (int r = 0; r < table_->rowCount(); ++r) {
    auto* it = table_->item(r, 0);
    if (!it) continue;
    QString raw = it->data(Qt::UserRole).toString();
    if (raw.isEmpty()) raw = it->text().trimmed();
    if (raw.startsWith(QStringLiteral("★ "))) raw = raw.mid(2).trimmed();
    if (raw == kn) {
      table_->setCurrentCell(r, 0);
      table_->scrollToItem(it);
      break;
    }
  }
  emit watchListChanged(keys_);
  QToolTip::showText(QCursor::pos(),
                     QStringLiteral("监视调序 %1 → #%2 · Alt+↑↓").arg(kn).arg(dest + 1),
                     table_);
}


void VarWatchPanel::moveSelectedToEdge(int edge) {
  if (!table_ || keys_.size() < 2) {
    QToolTip::showText(QCursor::pos(), QStringLiteral("监视不足 · Ctrl+Home/End"), table_);
    return;
  }
  const int row = table_->currentRow();
  if (row < 0) {
    QToolTip::showText(QCursor::pos(), QStringLiteral("未选中 · Ctrl+Home/End"), table_);
    return;
  }
  auto* keyItem = table_->item(row, 0);
  if (!keyItem) return;
  QString kn = keyItem->data(Qt::UserRole).toString();
  if (kn.isEmpty()) kn = keyItem->text().trimmed();
  if (kn.startsWith(QStringLiteral("★ "))) kn = kn.mid(2).trimmed();
  const int idx = keys_.indexOf(kn);
  if (idx < 0) return;
  const int dest = edge < 0 ? 0 : keys_.size() - 1;
  if (idx == dest) {
    QToolTip::showText(QCursor::pos(),
                       edge < 0 ? QStringLiteral("已在顶 · Ctrl+Home")
                                : QStringLiteral("已在底 · Ctrl+End"),
                       table_);
    return;
  }
  keys_.move(idx, dest);
  rebuild();
  emit watchListChanged(keys_);
  // reselect
  for (int r = 0; r < table_->rowCount(); ++r) {
    auto* it = table_->item(r, 0);
    if (!it) continue;
    QString k = it->data(Qt::UserRole).toString();
    if (k.isEmpty()) k = it->text().trimmed();
    if (k.startsWith(QStringLiteral("★ "))) k = k.mid(2).trimmed();
    if (k == kn) {
      table_->setCurrentCell(r, 0);
      table_->selectRow(r);
      break;
    }
  }
  QToolTip::showText(QCursor::pos(),
                     edge < 0 ? QStringLiteral("已置顶 %1 · Ctrl+Home").arg(kn)
                              : QStringLiteral("已置底 %1 · Ctrl+End").arg(kn),
                     table_);
}


}  // namespace sieans_qt
