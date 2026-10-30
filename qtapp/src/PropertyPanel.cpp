#include "PropertyPanel.hpp"

#include "Theme.hpp"

#include <QVBoxLayout>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMetaType>

namespace sieans_qt {
namespace {

QString stringify(const QVariant& v) {
  if (v.typeId() == QMetaType::QVariantMap || v.typeId() == QMetaType::QVariantList) {
    return QString::fromUtf8(
        QJsonDocument::fromVariant(v).toJson(QJsonDocument::Compact));
  }
  return v.toString();
}

}  // namespace

PropertyPanel::PropertyPanel(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  title_ = new QLabel(QStringLiteral("属性"));
  title_->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title_);
  meta_ = new QLabel(QStringLiteral("选中流程节点以编辑参数"));
  meta_->setObjectName(QStringLiteral("muted"));
  meta_->setWordWrap(true);
  lay->addWidget(meta_);

  auto* scroll = new QScrollArea;
  scroll->setWidgetResizable(true);
  scroll->setFrameShape(QFrame::NoFrame);
  formHost_ = new QWidget;
  form_ = new QFormLayout(formHost_);
  form_->setContentsMargins(0, 0, 0, 0);
  form_->setSpacing(4);
  form_->setLabelAlignment(Qt::AlignLeft);
  scroll->setWidget(formHost_);
  lay->addWidget(scroll, 1);
}

void PropertyPanel::clear() {
  currentId_.clear();
  title_->setText(QStringLiteral("属性"));
  meta_->setText(QStringLiteral("选中流程节点以编辑参数"));
  while (form_->rowCount() > 0) form_->removeRow(0);
}

void PropertyPanel::rebuildForm(const QString& title, const QString& nodeId,
                                const QVariantMap& params,
                                const QStringList& preferKeys) {
  currentId_ = nodeId;
  title_->setText(title);
  while (form_->rowCount() > 0) form_->removeRow(0);

  QStringList keys = preferKeys;
  for (auto it = params.begin(); it != params.end(); ++it) {
    if (!keys.contains(it.key())) keys.push_back(it.key());
  }
  for (const QString& key : keys) {
    if (!params.contains(key) && !preferKeys.contains(key)) continue;
    auto* edit = new QLineEdit(stringify(params.value(key)));
    edit->setProperty("paramKey", key);
    connect(edit, &QLineEdit::editingFinished, this, [this, edit]() {
      emit paramEdited(currentId_, edit->property("paramKey").toString(),
                       edit->text());
    });
    form_->addRow(key, edit);
  }
}

void PropertyPanel::showSource(const QVariantMap& sourceConfig) {
  meta_->setText(QStringLiteral("图像源 · sourceConfig"));
  QVariantMap flat = sourceConfig;
  const QVariantMap cam = sourceConfig.value(QStringLiteral("cameraParams")).toMap();
  for (auto it = cam.begin(); it != cam.end(); ++it)
    flat.insert(QStringLiteral("cam.%1").arg(it.key()), it.value());
  rebuildForm(QStringLiteral("属性 · 图像源"), QStringLiteral("source"), flat,
              {QStringLiteral("mode"), QStringLiteral("cam.deviceId"),
               QStringLiteral("cam.continuousLive"),
               QStringLiteral("cam.exposureTime"),
               QStringLiteral("cam.acquisitionFrameRate"),
               QStringLiteral("cam.backendKind")});
}

void PropertyPanel::showStep(const FlowStep& step) {
  meta_->setText(QStringLiteral("算子 %1 · %2")
                     .arg(step.operation, step.runState));
  rebuildForm(QStringLiteral("属性 · %1").arg(step.name), step.id, step.params,
              {QStringLiteral("deviceId"), QStringLiteral("types"),
               QStringLiteral("maxCodes"), QStringLiteral("showOverlay"),
               QStringLiteral("resultVar"), QStringLiteral("template"),
               QStringLiteral("device"), QStringLiteral("message")});
}

}  // namespace sieans_qt
