#include "SubflowDialog.hpp"

#include "FlowCanvas.hpp"
#include "OperatorLibrary.hpp"

#include <QCloseEvent>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QSplitter>
#include <QListWidget>
#include <QComboBox>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QMessageBox>
#include <QDialogButtonBox>
#include <QUuid>

namespace sieans_qt {
namespace {

QVariantMap defaultParamsFor(const QString& key) {
  if (key == QLatin1String("var_calc")) {
    return {{QStringLiteral("scope"), QStringLiteral("flow")},
            {QStringLiteral("expressions"),
             QVariantList{QVariantMap{{QStringLiteral("name"), QStringLiteral("count")},
                                      {QStringLiteral("expr"), QStringLiteral("count + 1")},
                                      {QStringLiteral("enabled"), true}}}}};
  }
  if (key == QLatin1String("format_data")) {
    return {{QStringLiteral("template"), QStringLiteral("{count}")},
            {QStringLiteral("args"), QStringLiteral("count")},
            {QStringLiteral("targetVar"), QStringLiteral("formatted")}};
  }
  if (key == QLatin1String("result_gate")) {
    return {{QStringLiteral("minCount"), 1},
            {QStringLiteral("sourceVar"), QStringLiteral("count")},
            {QStringLiteral("passVar"), QStringLiteral("passGate")}};
  }
  if (key == QLatin1String("condition")) {
    return {{QStringLiteral("logic"), QStringLiteral("and")},
            {QStringLiteral("comparison"), QStringLiteral("gte")},
            {QStringLiteral("left"), QStringLiteral("count")},
            {QStringLiteral("right"), QStringLiteral("limit")},
            {QStringLiteral("writePassGate"), false},
            {QStringLiteral("rules"),
             QVariantList{QVariantMap{{QStringLiteral("left"), QStringLiteral("count")},
                                      {QStringLiteral("comparison"), QStringLiteral("gte")},
                                      {QStringLiteral("right"), QStringLiteral("limit")},
                                      {QStringLiteral("enabled"), true}}}}};
  }
  if (key == QLatin1String("branch")) {
    return {{QStringLiteral("defaultPathId"), QStringLiteral("default")},
            {QStringLiteral("paths"),
             QVariantList{QVariantMap{{QStringLiteral("id"), QStringLiteral("default")},
                                      {QStringLiteral("name"), QStringLiteral("默认")},
                                      {QStringLiteral("left"), QString()},
                                      {QStringLiteral("comparison"), QStringLiteral("is_true")},
                                      {QStringLiteral("right"), QString()},
                                      {QStringLiteral("enabled"), true}}}}};
  }
  if (key == QLatin1String("subflow") || key == QLatin1String("loop")) {
    QVariantMap p{{QStringLiteral("subflowId"), QString()},
                  {QStringLiteral("arguments"), QVariantMap{}},
                  {QStringLiteral("stateMode"), QStringLiteral("reset")}};
    if (key == QLatin1String("loop")) {
      p.insert(QStringLiteral("mode"), QStringLiteral("count"));
      p.insert(QStringLiteral("iterations"), 3);
      p.insert(QStringLiteral("frameMode"), QStringLiteral("previous"));
      p.insert(QStringLiteral("stopField"), QStringLiteral("passed"));
      p.insert(QStringLiteral("stopValue"), true);
    }
    return p;
  }
  return {};
}

}  // namespace

SubflowDialog::SubflowDialog(SieansDocument* host, QWidget* parent)
    : QDialog(parent), host_(host) {
  setWindowTitle(QStringLiteral("子流程管理"));
  setModal(true);
  resize(980, 640);

  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(10, 10, 10, 10);
  auto* split = new QSplitter(Qt::Horizontal);
  root->addWidget(split, 1);

  auto* left = new QWidget;
  auto* leftLay = new QVBoxLayout(left);
  leftLay->setContentsMargins(0, 0, 0, 0);
  auto* title = new QLabel(QStringLiteral("子流程定义（最多 20 个，每个最多 50 节点）"));
  title->setObjectName(QStringLiteral("muted"));
  leftLay->addWidget(title);
  list_ = new QListWidget;
  leftLay->addWidget(list_, 1);
  auto* btns = new QHBoxLayout;
  auto* neu = new QPushButton(QStringLiteral("新建"));
  auto* save = new QPushButton(QStringLiteral("保存修改"));
  auto* del = new QPushButton(QStringLiteral("删除未引用"));
  btns->addWidget(neu);
  btns->addWidget(save);
  btns->addWidget(del);
  leftLay->addLayout(btns);
  split->addWidget(left);

  auto* right = new QWidget;
  auto* rightLay = new QVBoxLayout(right);
  rightLay->setContentsMargins(0, 0, 0, 0);
  auto* top = new QHBoxLayout;
  auto* nameLab = new QLabel(QStringLiteral("名称"));
  auto* nameEdit = new QLineEdit;
  nameEdit->setObjectName(QStringLiteral("subflowNameEdit"));
  top->addWidget(nameLab);
  top->addWidget(nameEdit, 1);
  top->addWidget(new QLabel(QStringLiteral("输出节点")));
  output_ = new QComboBox;
  output_->setMinimumWidth(160);
  top->addWidget(output_);
  rightLay->addLayout(top);

  auto* addRow = new QHBoxLayout;
  catalog_ = new QComboBox;
  for (const OperatorDef& d : OperatorLibrary::catalog())
    catalog_->addItem(QStringLiteral("%1  ·  %2").arg(d.name, d.category), d.key);
  addRow->addWidget(catalog_, 1);
  auto* addBtn = new QPushButton(QStringLiteral("添加算子"));
  addRow->addWidget(addBtn);
  rightLay->addLayout(addRow);

  scene_ = new FlowScene(this);
  view_ = new FlowView(scene_);
  rightLay->addWidget(view_, 1);
  notice_ = new QLabel(
      QStringLiteral("局部变量在调用点隔离。循环可按次数或直到输出开关成立；禁止递归，最多 4 层。"));
  notice_->setObjectName(QStringLiteral("muted"));
  notice_->setWordWrap(true);
  rightLay->addWidget(notice_);
  split->addWidget(right);
  split->setStretchFactor(0, 1);
  split->setStretchFactor(1, 3);

  auto* box = new QDialogButtonBox(QDialogButtonBox::Close);
  root->addWidget(box);
  connect(box, &QDialogButtonBox::rejected, this, &QDialog::reject);
  connect(box, &QDialogButtonBox::accepted, this, &QDialog::accept);

  connect(neu, &QPushButton::clicked, this, &SubflowDialog::createDef);
  connect(save, &QPushButton::clicked, this, &SubflowDialog::saveCurrent);
  connect(del, &QPushButton::clicked, this, &SubflowDialog::removeCurrent);
  connect(addBtn, &QPushButton::clicked, this, &SubflowDialog::addOperator);
  connect(list_, &QListWidget::currentRowChanged, this, [this](int) { chooseCurrent(); });
  connect(output_, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
          [this](int) { onOutputChanged(); });
  connect(nameEdit, &QLineEdit::editingFinished, this, [this, nameEdit]() {
    if (loading_ || currentId_.isEmpty()) return;
    work_.setName(nameEdit->text().trimmed().isEmpty() ? QStringLiteral("未命名子流程")
                                                       : nameEdit->text().trimmed());
  });
  connect(view_, &FlowView::operatorDropped, this,
          [this](const QString& key, const QPointF& pos) { addOperatorAt(key, pos); });

  refreshList();
  if (list_->count() > 0) list_->setCurrentRow(0);
}

void SubflowDialog::closeEvent(QCloseEvent* event) {
  saveCurrent();
  QDialog::closeEvent(event);
}

void SubflowDialog::refreshList() {
  loading_ = true;
  const QString keep = currentId_;
  list_->clear();
  if (!host_) {
    loading_ = false;
    return;
  }
  int pick = -1;
  for (int i = 0; i < host_->subflows().size(); ++i) {
    const SubflowDef& d = host_->subflows()[i];
    auto* item = new QListWidgetItem(
        QStringLiteral("%1  (%2 · %3 节点)").arg(d.name, d.id).arg(d.steps.size()));
    item->setData(Qt::UserRole, d.id);
    list_->addItem(item);
    if (d.id == keep) pick = i;
  }
  loading_ = false;
  if (pick >= 0) list_->setCurrentRow(pick);
}

void SubflowDialog::createDef() {
  if (!host_) return;
  if (host_->subflows().size() >= 20) {
    QMessageBox::warning(this, windowTitle(), QStringLiteral("最多 20 个子流程定义"));
    return;
  }
  saveCurrent();
  SubflowDef d;
  d.id = QUuid::createUuid().toString(QUuid::WithoutBraces).left(12);
  d.name = QStringLiteral("子流程 %1").arg(host_->subflows().size() + 1);
  host_->subflowsMut().push_back(d);
  refreshList();
  list_->setCurrentRow(list_->count() - 1);
}

void SubflowDialog::chooseCurrent() {
  if (loading_) return;
  saveCurrent();
  if (!list_->currentItem() || !host_) {
    currentId_.clear();
    return;
  }
  currentId_ = list_->currentItem()->data(Qt::UserRole).toString();
  const SubflowDef* d = host_->findSubflow(currentId_);
  if (!d) return;
  loading_ = true;
  work_.loadFromSubflow(*d);
  if (auto* nameEdit = findChild<QLineEdit*>(QStringLiteral("subflowNameEdit")))
    nameEdit->setText(d->name);
  scene_->loadDocument(&work_);
  rebuildOutputCombo();
  loading_ = false;
}

void SubflowDialog::saveCurrent() {
  if (loading_ || !host_ || currentId_.isEmpty()) return;
  if (auto* nameEdit = findChild<QLineEdit*>(QStringLiteral("subflowNameEdit"))) {
    const QString n = nameEdit->text().trimmed();
    if (!n.isEmpty()) work_.setName(n);
  }
  const QString out = output_ ? output_->currentData().toString() : QString();
  const SubflowDef exported = work_.exportToSubflow(currentId_, out);
  if (SubflowDef* dst = host_->findSubflow(currentId_)) {
    *dst = exported;
  }
  // refresh labels only
  loading_ = true;
  for (int i = 0; i < list_->count(); ++i) {
    if (list_->item(i)->data(Qt::UserRole).toString() != currentId_) continue;
    list_->item(i)->setText(QStringLiteral("%1  (%2 · %3 节点)")
                                .arg(exported.name, exported.id)
                                .arg(exported.steps.size()));
    break;
  }
  loading_ = false;
}

void SubflowDialog::removeCurrent() {
  if (!host_ || currentId_.isEmpty()) return;
  if (host_->subflowIsReferenced(currentId_)) {
    QMessageBox::warning(this, windowTitle(),
                         QStringLiteral("该子流程仍被主流程或其它子流程引用，无法删除"));
    return;
  }
  if (QMessageBox::question(this, windowTitle(), QStringLiteral("删除当前子流程定义？")) !=
      QMessageBox::Yes)
    return;
  auto& vec = host_->subflowsMut();
  for (int i = 0; i < vec.size(); ++i) {
    if (vec[i].id == currentId_) {
      vec.removeAt(i);
      break;
    }
  }
  currentId_.clear();
  work_.loadFromSubflow(SubflowDef{});
  scene_->loadDocument(&work_);
  refreshList();
  if (list_->count() > 0) list_->setCurrentRow(0);
}

void SubflowDialog::addOperator() {
  if (currentId_.isEmpty()) {
    QMessageBox::information(this, windowTitle(), QStringLiteral("请先新建或选择一个子流程"));
    return;
  }
  const QString key = catalog_ ? catalog_->currentData().toString() : QString();
  if (key.isEmpty()) return;
  const qreal y = 120 + work_.steps().size() * 120;
  addOperatorAt(key, QPointF(300, y));
}

void SubflowDialog::addOperatorAt(const QString& key, const QPointF& pos) {
  if (currentId_.isEmpty()) return;
  if (work_.steps().size() >= 50) {
    QMessageBox::warning(this, windowTitle(), QStringLiteral("子流程最多 50 个节点"));
    return;
  }
  const OperatorDef def = OperatorLibrary::findDef(key);
  FlowStep s;
  s.id = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
  s.name = def.name.isEmpty() ? key : def.name;
  s.operation = key;
  s.position = pos;
  s.runState = QStringLiteral("等待执行");
  s.params = defaultParamsFor(key);
  if (!work_.steps().isEmpty()) {
    s.imageFrom = work_.steps().last().id;
    FlowEdge e;
    e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    e.from = s.imageFrom;
    e.to = s.id;
    work_.edgesMut().push_back(e);
  } else {
    s.imageFrom = QStringLiteral("source");
    FlowEdge e;
    e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    e.from = QStringLiteral("source");
    e.to = s.id;
    work_.edgesMut().push_back(e);
  }
  work_.stepsMut().push_back(s);
  scene_->loadDocument(&work_);
  rebuildOutputCombo();
  if (output_ && output_->currentIndex() < 0 && output_->count() > 0)
    output_->setCurrentIndex(output_->count() - 1);
}

void SubflowDialog::rebuildOutputCombo() {
  if (!output_) return;
  const QString keep = output_->currentData().toString();
  const bool wasLoading = loading_;
  loading_ = true;
  output_->clear();
  output_->addItem(QStringLiteral("（未指定）"), QString());
  int pick = 0;
  for (const FlowStep& s : work_.steps()) {
    output_->addItem(QStringLiteral("%1  ·  %2").arg(s.name, s.id), s.id);
    if (s.id == keep) pick = output_->count() - 1;
  }
  // prefer stored output from host if keep empty
  if (keep.isEmpty() && host_) {
    if (const SubflowDef* d = host_->findSubflow(currentId_)) {
      for (int i = 0; i < output_->count(); ++i) {
        if (output_->itemData(i).toString() == d->outputNode) {
          pick = i;
          break;
        }
      }
    }
  }
  output_->setCurrentIndex(pick);
  loading_ = wasLoading;
}

void SubflowDialog::onOutputChanged() {
  if (loading_) return;
  // persisted on saveCurrent
}

}  // namespace sieans_qt
