#pragma once

#include "SieansDocument.hpp"

#include <QImage>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QWidget>

class QTabWidget;
class QComboBox;
class QDoubleSpinBox;
class QSpinBox;
class QCheckBox;
class QLineEdit;
class QLabel;
class QTableWidget;

namespace sieans_qt {

/**
 * VisionMaster / PySide 快速匹配四 Tab 属性页（基本参数 / 模板 / 运行参数 / 结果显示）。
 * 复用已有 locate 参数与 SAD 匹配，不引入新算子或 Halcon。
 */
class LocateMatchPanel : public QWidget {
  Q_OBJECT
 public:
  explicit LocateMatchPanel(QWidget* parent = nullptr);

  /** 绑定一个 locate 步骤并刷新四个页签。 */
  void bindStep(const FlowStep& step);
  /** 当前编辑器中的参数（会先提交未完成的数值编辑）。 */
  QVariantMap currentParams() const;
  /** 用快照覆盖编辑器，不发 paramEdited（用于还原）。 */
  void applySnapshot(const QVariantMap& snap);
  /** 提交仍在编辑的数值框。 */
  void flushPendingEdits();
  /** 用最近一次运行的 locate* 流程变量刷新结果显示。 */
  void setLastResult(const QVariantMap& vars);

  int tabCount() const;
  bool templateReady() const;
  QString nodeId() const { return nodeId_; }

  /**
   * 从当前图截取模板并落到工作台 templates 目录，写入 templatePath。
   * 供「创建模板」按钮和冒烟自检使用。
   */
  bool createTemplateFromImage(const QImage& scene, QString* error = nullptr);

  /** 补齐 PySide normalize_locate_params 的默认键，不覆盖已有值。 */
  static QVariantMap normalizeParams(const QVariantMap& in);
  /** 四 Tab 绑定、默认值和模板落盘往返。空列表表示通过。需要 QApplication。 */
  static QStringList selfTest();

 signals:
  void paramEdited(const QString& nodeId, const QString& key, const QString& value);
  /** 主窗口用当前画面图调用 createTemplateFromImage。 */
  void createTemplateRequested();

 private:
  void rebuildEditors();
  void loadEditorsFromParams();
  void setParam(const QString& key, const QVariant& value, bool emitChange);
  void refreshTemplateChrome();
  void refreshResultSummary();
  void onLoadTemplate();
  void onClearTemplate();

  QString nodeId_;
  QVariantMap params_;
  bool applying_ = false;

  QTabWidget* tabs_ = nullptr;
  QComboBox* matchMode_ = nullptr;
  QComboBox* templateSource_ = nullptr;
  QDoubleSpinBox* minScore_ = nullptr;
  QSpinBox* maxMatches_ = nullptr;
  QDoubleSpinBox* overlap_ = nullptr;
  QLineEdit* pathEdit_ = nullptr;
  QLabel* tplStatus_ = nullptr;
  QCheckBox* angleEnable_ = nullptr;
  QDoubleSpinBox* angleStart_ = nullptr;
  QDoubleSpinBox* angleEnd_ = nullptr;
  QDoubleSpinBox* angleStep_ = nullptr;
  QCheckBox* showOverlay_ = nullptr;
  QCheckBox* showOrigin_ = nullptr;
  QCheckBox* showAngleDeg_ = nullptr;
  QLabel* resultSummary_ = nullptr;
  QTableWidget* hitTable_ = nullptr;
};

}  // namespace sieans_qt
