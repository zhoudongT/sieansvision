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
class QListWidget;

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
  int libraryCount() const;
  QString activeTemplateId() const;
  QVariantMap lastBatchScoreboard() const;
  QString nodeId() const { return nodeId_; }

  /** 将路径加入模板库（同路径则替换）。返回条目 id。 */
  QString addLibraryEntry(const QString& path, const QString& name = QString(),
                          const QString& note = QString());
  /** 把库中条目设为当前模板。 */
  bool selectLibraryEntry(const QString& id);
  /** 从模板库移除（不删磁盘文件）。 */
  bool removeLibraryEntry(const QString& id);
  /** 对模板库打分（可注入分数，缺项用软估）。写入 lastBatchScoreboard。 */
  QVariantMap runBatchScoreboard(const QVariantMap& scoresById = {},
                                 bool softFallback = true);
  /** 选用记分板最高分模板。无界面时低于阈值也选用。 */
  bool selectBestScoredTemplate(QString* error = nullptr);

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
  /** 列表/对象参数（模板库、记分板）写回步骤，避免 toString 丢失结构。 */
  void structuredParamEdited(const QString& nodeId, const QString& key, const QVariant& value);
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
  void onAddLibraryClicked();
  void onSelectLibraryClicked();
  void onRemoveLibraryClicked();
  void onPreviewLibraryClicked();
  void onBatchScoreClicked();
  void onSelectBestClicked();
  /** 刷新模板库列表和选中标记。 */
  void refreshLibraryList();
  /** 用 lastBatchScoreboard 刷新记分板表格。 */
  void refreshScoreboardTable();
  /** 按当前选中库条目更新预览文字。 */
  void refreshLibraryPreview();

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
  QLabel* libCount_ = nullptr;
  QListWidget* libList_ = nullptr;
  QLabel* libPreview_ = nullptr;
  QDoubleSpinBox* batchThr_ = nullptr;
  QLabel* boardSummary_ = nullptr;
  QTableWidget* boardTable_ = nullptr;
};

}  // namespace sieans_qt
