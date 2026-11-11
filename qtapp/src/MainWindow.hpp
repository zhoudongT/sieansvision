#pragma once

#include "FlowCanvas.hpp"
#include "GenTLWorker.hpp"
#include "ImageView.hpp"
#include "OperatorLibrary.hpp"
#include "PropertyPanel.hpp"
#include "SieansDocument.hpp"
#include "CommHub.hpp"
#include "CommPanel.hpp"
#include "VarWatchPanel.hpp"
#include "HostStrip.hpp"
#include "FilmstripBar.hpp"
#include "CompareStrip.hpp"
#include "FlowTabBar.hpp"
#include "PropertyFloat.hpp"
#include "OperatorRail.hpp"
#include "HostStatePanel.hpp"
#include "SubflowExec.hpp"

#include <QMainWindow>
#include <QEvent>
#include <QCloseEvent>
#include <QPlainTextEdit>
#include <QLabel>
#include <QTableWidget>
#include <QThread>
#include <QTimer>
#include <QVariantMap>
#include <QHash>
#include <atomic>

namespace sieans_qt {

class MainWindow : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(QWidget* parent = nullptr);
  ~MainWindow() override;
  bool eventFilter(QObject* obj, QEvent* event) override;
  /** 关闭前提示未保存修改（无界面冒烟跳过对话框）。 */
  void closeEvent(QCloseEvent* event) override;

 private slots:
  void onNewProject();
  void onOpenProject();
  void onSaveProject();
  void onSaveProjectAs();
  void onExportCurrentFlow();
  void onImportFlow();
  void onOpenImage();
  void onLoadSample();
  void onDecodeQr();
  void onEnumerateGenTL();
  void onOpenCameraManager();
  void onOpenCommManager();
  void onOpenFlowIo();
  void onOpenSubflowManager();
  void onStartContinuousPreview();
  void onStopContinuousPreview();
  void onRunOnce();
  void onRunContinuous();
  void onPauseRun();
  void onResumeRun();
  void onStopRun();
  void onToggleRunMode(bool on);
  void onRunAllImages();
  void onAbout();
  void onNodeSelected(const QString& nodeId);
  void onAddOperator(const QString& key, const QString& name);
  void onDropOperator(const QString& key, const QPointF& scenePos);
  void onDuplicateNode(const QString& nodeId);
  void onParamEdited(const QString& nodeId, const QString& key,
                     const QString& value);
  void onStructuredParamEdited(const QString& nodeId, const QString& key, const QVariant& value);
  void onSparkFilmstripJump(const QVariantMap& bag);
  /** 胶片帧对应到结果表行并选中画布节点（不写脏标记）。 */
  void focusFilmstripResult(const QString& path, const QString& nodeId = QString());
  void onParamsReverted(const QString& nodeId, const QVariantMap& snapshot);
  void onPreviewFrame(const QImage& image, qint64 frameId);
  void onWorkerError(const QString& msg);
  void onWorkerStatus(const QString& msg);
  void onContinuousTick();
  void onEdgeConnected(const QString& fromId, const QString& toId,
                       const QString& fromPort, const QString& toPort);
  void onEdgeWhenChanged(const QString& edgeId, const QString& when);
  void onLinkNotice(const QString& msg);

 private:
  void buildUi();
  void buildMenus();
  void buildToolbar();
  void applyDocumentToUi();
  /** Restore Host/VarWatch pin-group chrome from the document without dirtying. */
  void syncHostPinGroups();
  /** Activate a named pin group and refresh chips; marks dirty unless applying. */
  void applyHostPinGroup(const QString& name);
  /** Result-table double-click: jump film and accumulate compare-strip paths (runtime only). */
  void applyResultCompare(const QString& path);
  /** Stash geom/measure pickables for the current film path (runtime-only, cap 32). */
  void cacheFilmstripGeomOverlays(const QVector<OverlayHit>& hits);
  /** Rebuild result-view compare overlays for the selected compare/film frame. */
  void refreshGeomCompareOverlays();
  /** 方案已被用户改过，标题加 *。加载/应用文档期间忽略。 */
  void markProjectDirty();
  /** 保存或重新加载成功后清除脏标记。 */
  void markProjectClean();
  /** 按方案名、设计/运行态和脏标记刷新窗口标题与方案标签。 */
  void refreshProjectTitle();
  /** 有未保存修改时询问保存/放弃/取消；无界面冒烟直接视为放弃。取消则返回 false。 */
  bool confirmDiscardOrSave();
  void logResult(const QString& line);
  void showStatus(const QString& msg, int timeout_ms = 5000);
  bool loadImagePath(const QString& path, bool addToStrip = true);
  void refreshConfigStatus();
  void auditParam(const QString& nodeId, const QString& key, const QString& oldText,
                  const QString& newText);
  void runPipeline(const QImage& src, bool updateFlowStates);
  void runDecodeOnImage(const QImage& src, bool updateFlowStates);
  bool ensureCameraOpen();
  QString defaultProjectsDir() const;
  QString samplePathCandidates() const;
  void setBusy(bool busy);
  void updateRunChrome();
  void syncVarsToUi(bool hostEvaluated = false);
  void pushSoftControls();
  void noteHostResult(bool ok, const QString& detail);
  void applyFlowIoBindings();
  /** Mirror Host mode/state/OK-NG-ALARM/stats into flow_vars for I/O + Comm. */
  void publishHostToFlowVars();
  /** Fire commManager.sendEvents filtered by on=ok|ng|alarm|always. */
  void fireHostCommEvents(const QString& resultTag);
  QVariant resolveIoBinding(const QString& binding) const;
  QStringList topologicalStepIds() const;
  void addOperatorAt(const QString& key, const QString& name,
                     const QPointF& pos, bool autoWire);

  FlowScene* flow_scene_ = nullptr;
  FlowView* flow_view_ = nullptr;
  ImageView* image_view_ = nullptr;
  OperatorRail* op_rail_ = nullptr;
  OperatorLibrary* op_lib_ = nullptr;
  PropertyPanel* prop_panel_ = nullptr;  // embedded fallback / float body
  PropertyFloat* prop_float_ = nullptr;
  FlowTabBar* flow_tabs_ = nullptr;
  FilmstripBar* filmstrip_ = nullptr;
  CompareStrip* compare_strip_ = nullptr;
  QStringList result_compare_paths_;
  QHash<QString, QVector<GeomPickable>> filmstrip_geom_cache_;
  QString last_run_film_path_;
  ImageView* output_view_ = nullptr;
  QTabWidget* image_tabs_ = nullptr;
  QLabel* mode_badge_ = nullptr;
  QLabel* listen_badge_ = nullptr;
  QLabel* brand_label_ = nullptr;

  CommHub* comm_hub_ = nullptr;
  CommPanel* comm_panel_ = nullptr;
  VarWatchPanel* var_watch_ = nullptr;
  HostStrip* host_strip_ = nullptr;
  HostStatePanel* host_sm_ = nullptr;
  QTabWidget* bottom_tabs_ = nullptr;
  QPlainTextEdit* result_log_ = nullptr;
  QTableWidget* result_table_ = nullptr;
  QLineEdit* resultFilter_ = nullptr;
  QLineEdit* resultLogFilter_ = nullptr;
  QStringList resultLogAll_;
  QLabel* status_backend_ = nullptr;
  QLabel* status_busy_ = nullptr;
  QLabel* status_config_ = nullptr;
  QLabel* status_timing_ = nullptr;
  QLabel* project_label_ = nullptr;

  QAction* act_run_ = nullptr;
  QAction* act_cont_ = nullptr;
  QAction* act_pause_ = nullptr;
  QAction* act_stop_ = nullptr;
  QAction* act_mode_ = nullptr;
  QAction* act_preview_ = nullptr;
  QAction* act_preview_stop_ = nullptr;

  SieansDocument document_;
  QString current_path_;
  QVariantMap flow_vars_;
  QHash<QString, SubflowState> subflow_states_;

  QThread* cam_thread_ = nullptr;
  GenTLWorker* cam_worker_ = nullptr;

  QTimer continuous_timer_;
  std::atomic<bool> busy_{false};
  std::atomic<bool> pipeline_cancel_{false};
  QVariantMap global_vars_;
  QHash<QString, QVariantMap> module_vars_;
  bool continuous_run_ = false;
  bool run_paused_ = false;
  bool run_mode_ = false;
  int run_cycle_ = 0;
  double last_cycle_ms_ = -1;
  bool preview_active_ = false;
  bool project_dirty_ = false;
  bool applying_document_ = false;
  qint64 preview_frames_ = 0;
};

}  // namespace sieans_qt
