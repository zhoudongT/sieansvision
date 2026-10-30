#pragma once

#include "FlowCanvas.hpp"
#include "GenTLWorker.hpp"
#include "ImageView.hpp"
#include "OperatorLibrary.hpp"
#include "PropertyPanel.hpp"
#include "SieansDocument.hpp"

#include <QMainWindow>
#include <QPlainTextEdit>
#include <QLabel>
#include <QTableWidget>
#include <QThread>
#include <QTimer>
#include <atomic>

namespace sieans_qt {

class MainWindow : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(QWidget* parent = nullptr);
  ~MainWindow() override;

 private slots:
  void onNewProject();
  void onOpenProject();
  void onSaveProject();
  void onSaveProjectAs();
  void onOpenImage();
  void onLoadSample();
  void onDecodeQr();
  void onEnumerateGenTL();
  void onOpenCameraManager();
  void onStartContinuousPreview();
  void onStopContinuousPreview();
  void onRunOnce();
  void onRunContinuous();
  void onStopRun();
  void onAbout();
  void onNodeSelected(const QString& nodeId);
  void onAddOperator(const QString& key, const QString& name);
  void onParamEdited(const QString& nodeId, const QString& key,
                     const QString& value);
  void onPreviewFrame(const QImage& image, qint64 frameId);
  void onWorkerError(const QString& msg);
  void onWorkerStatus(const QString& msg);
  void onContinuousTick();

 private:
  void buildUi();
  void buildMenus();
  void buildToolbar();
  void applyDocumentToUi();
  void logResult(const QString& line);
  void showStatus(const QString& msg, int timeout_ms = 5000);
  bool loadImagePath(const QString& path);
  void runDecodeOnImage(const QImage& src, bool updateFlowStates);
  bool ensureCameraOpen();
  QString defaultProjectsDir() const;
  QString samplePathCandidates() const;
  void setBusy(bool busy);
  void updateRunChrome();

  // Layout
  FlowScene* flow_scene_ = nullptr;
  FlowView* flow_view_ = nullptr;
  ImageView* image_view_ = nullptr;
  OperatorLibrary* op_lib_ = nullptr;
  PropertyPanel* prop_panel_ = nullptr;
  QPlainTextEdit* result_log_ = nullptr;
  QTableWidget* result_table_ = nullptr;
  QLabel* status_backend_ = nullptr;
  QLabel* status_busy_ = nullptr;
  QLabel* project_label_ = nullptr;

  QAction* act_run_ = nullptr;
  QAction* act_cont_ = nullptr;
  QAction* act_stop_ = nullptr;
  QAction* act_preview_ = nullptr;
  QAction* act_preview_stop_ = nullptr;

  SieansDocument document_;
  QString current_path_;

  QThread* cam_thread_ = nullptr;
  GenTLWorker* cam_worker_ = nullptr;

  QTimer continuous_timer_;
  std::atomic<bool> busy_{false};
  bool continuous_run_ = false;
  bool preview_active_ = false;
  qint64 preview_frames_ = 0;
};

}  // namespace sieans_qt
