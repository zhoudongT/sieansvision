#include "MainWindow.hpp"
#include "Theme.hpp"
#include "ExprEval.hpp"
#include "UvcCapture.hpp"

#include <sieans/barcode.hpp>
#include <sieans/gentl_capture.hpp>

#include <QAction>
#include <QApplication>
#include <QCoreApplication>
#include <QDateTime>
#include <QDialog>
#include <QDialogButtonBox>
#include <QDir>
#include <QFileDialog>
#include <QFile>
#include <QFileInfo>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QListWidget>
#include <QComboBox>
#include <QMenu>
#include <QMenuBar>
#include <QMessageBox>
#include <QSplitter>
#include <QStatusBar>
#include <QToolBar>
#include <QUuid>
#include <QVBoxLayout>
#include <QKeySequence>
#include <QTabWidget>
#include <QPushButton>
#include <QEventLoop>
#include <QTimer>
#include <QLabel>
#include <QSize>
#include <QPixmap>
#include <QAbstractItemView>
#include <QSet>
#include <QHash>
#include <QQueue>

#include <algorithm>
#include <chrono>
#include <exception>
#include <vector>

namespace sieans_qt {
namespace {

QImage toRgb888(const QImage& src) {
  if (src.isNull()) return {};
  if (src.format() == QImage::Format_RGB888) return src;
  return src.convertToFormat(QImage::Format_RGB888);
}

QImage applyPreprocess(const QImage& src, const QVariantMap& params) {
  if (src.isNull()) return src;
  QString mode = params.value(QStringLiteral("mode"), QStringLiteral("gray")).toString();
  QImage out = src;
  if (mode == QLatin1String("gray") || mode == QLatin1String("mono")) {
    out = src.convertToFormat(QImage::Format_Grayscale8)
              .convertToFormat(QImage::Format_RGB888);
  } else if (mode == QLatin1String("invert")) {
    out = src.convertToFormat(QImage::Format_RGB888).copy();
    for (int y = 0; y < out.height(); ++y) {
      uchar* line = out.scanLine(y);
      for (int x = 0; x < out.width() * 3; ++x) line[x] = 255 - line[x];
    }
  } else if (mode == QLatin1String("threshold")) {
    const int thr = params.value(QStringLiteral("threshold"), 128).toInt();
    QImage g = src.convertToFormat(QImage::Format_Grayscale8);
    for (int y = 0; y < g.height(); ++y) {
      uchar* line = g.scanLine(y);
      for (int x = 0; x < g.width(); ++x) line[x] = line[x] >= thr ? 255 : 0;
    }
    out = g.convertToFormat(QImage::Format_RGB888);
  }
  return out;
}

}  // namespace

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle(QStringLiteral("SIEANS Vision · 设计态"));
  resize(1600, 940);

  cam_thread_ = new QThread(this);
  cam_worker_ = new GenTLWorker();
  cam_worker_->moveToThread(cam_thread_);
  connect(cam_thread_, &QThread::finished, cam_worker_, &QObject::deleteLater);
  connect(cam_worker_, &GenTLWorker::frameReady, this, &MainWindow::onPreviewFrame,
          Qt::QueuedConnection);
  connect(cam_worker_, &GenTLWorker::errorOccurred, this, &MainWindow::onWorkerError,
          Qt::QueuedConnection);
  connect(cam_worker_, &GenTLWorker::statusChanged, this, &MainWindow::onWorkerStatus,
          Qt::QueuedConnection);
  cam_thread_->start();

  continuous_timer_.setSingleShot(false);
  connect(&continuous_timer_, &QTimer::timeout, this, &MainWindow::onContinuousTick);

  comm_hub_ = new CommHub(this);

  buildUi();
  buildMenus();
  buildToolbar();

  showStatus(QStringLiteral("就绪 · native %1 · GenTL %2")
                 .arg(QString::fromStdString(sieans::native_version()))
                 .arg(sieans::GenTLCapture::available() ? QStringLiteral("可用")
                                                        : QStringLiteral("桩/不可用")));

  const QString proj =
      defaultProjectsDir() + QStringLiteral("/open-and-run-gentl-qr.sieans");
  QString err;
  if (QFileInfo::exists(proj) && document_.loadFromFile(proj, &err)) {
    applyDocumentToUi();
    logResult(QStringLiteral("已加载方案: %1").arg(document_.name()));
  } else {
    document_.seedGentlQrDemo();
    applyDocumentToUi();
    logResult(QStringLiteral("已种子 GenTL→QR 演示流程"));
  }

  if (qgetenv("SIEANS_QT_AUTO_SAMPLE") == "1") {
    QTimer::singleShot(120, this, &MainWindow::onLoadSample);
  }
  if (qgetenv("SIEANS_QT_AUTO_ENUM") == "1") {
    QTimer::singleShot(400, this, &MainWindow::onEnumerateGenTL);
  }
  if (qgetenv("SIEANS_QT_AUTO_PROJECT") == "1" ||
      qgetenv("SIEANS_QT_AUTO_PREVIEW") == "1") {
    QTimer::singleShot(600, this, &MainWindow::onStartContinuousPreview);
  }
  if (qgetenv("SIEANS_QT_AUTO_TCP") == "1") {
    QTimer::singleShot(900, this, [this]() {
      QString e;
      comm_hub_->startTcp(&e);
    });
  }
  const QByteArray shot = qgetenv("SIEANS_QT_SCREENSHOT");
  if (!shot.isEmpty()) {
    const int shotDelay =
        (qgetenv("SIEANS_QT_AUTO_PREVIEW") == "1") ? 2800 : 1100;
    QTimer::singleShot(shotDelay, this, [this, shot]() {
      const QPixmap px = grab();
      const QString out = QString::fromUtf8(shot);
      QDir().mkpath(QFileInfo(out).absolutePath());
      if (px.save(out)) {
        logResult(QStringLiteral("截图已保存: %1").arg(out));
        showStatus(QStringLiteral("截图 %1").arg(out));
      } else {
        logResult(QStringLiteral("截图失败: %1").arg(out));
      }
      if (qgetenv("SIEANS_QT_SCREENSHOT_QUIT") == "1") {
        onStopContinuousPreview();
        QTimer::singleShot(400, qApp, &QApplication::quit);
      }
    });
  }
}

MainWindow::~MainWindow() {
  continuous_timer_.stop();
  continuous_run_ = false;
  preview_active_ = false;
  if (comm_hub_) comm_hub_->stopTcp();
  if (cam_worker_) {
    QMetaObject::invokeMethod(cam_worker_, "stopPreview", Qt::DirectConnection);
    for (int i = 0; i < 60 && cam_worker_->isPreviewing(); ++i)
      QThread::msleep(50);
  }
  if (cam_thread_ && cam_thread_->isRunning()) {
    if (cam_worker_ && !cam_worker_->isPreviewing()) {
      QMetaObject::invokeMethod(cam_worker_, "closeDevice",
                                Qt::BlockingQueuedConnection);
    }
    cam_thread_->quit();
    if (!cam_thread_->wait(3000)) {
      cam_thread_->terminate();
      cam_thread_->wait(1000);
    }
  }
}

QString MainWindow::defaultProjectsDir() const {
  return QStringLiteral("/home/allen/文档/sieansvision/projects");
}

QString MainWindow::samplePathCandidates() const {
  const QStringList cands = {
      QCoreApplication::applicationDirPath() + QStringLiteral("/resources/sample-qr.png"),
      QDir(QCoreApplication::applicationDirPath())
          .absoluteFilePath(QStringLiteral("../resources/sample-qr.png")),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/resources/sample-qr.png"),
      QStringLiteral("/home/allen/文档/sieansvision/artifacts/qr-t238-grab0.png"),
  };
  for (const auto& p : cands) {
    if (QFileInfo::exists(p)) return p;
  }
  return {};
}

void MainWindow::buildUi() {
  // VisionMaster / industrial workbench layout:
  // vertical: [horizontal workbench] / [bottom results tabs]
  // horizontal: [rail|toolbox] | [flow tabs+canvas] | [image tabs+filmstrip]
  // property = light float (VM 属性浮窗), not embedded under canvas
  auto* central = new QWidget(this);
  auto* rootSplit = new QSplitter(Qt::Vertical);
  auto* rootLay = new QVBoxLayout(central);
  rootLay->setContentsMargins(0, 0, 0, 0);
  rootLay->setSpacing(0);
  rootLay->addWidget(rootSplit);

  auto* horizontal = new QSplitter(Qt::Horizontal);

  // —— Left: category rail + operator library ——
  auto* left = new QWidget;
  left->setObjectName(QStringLiteral("libraryPane"));
  auto* leftLay = new QHBoxLayout(left);
  leftLay->setContentsMargins(0, 0, 0, 0);
  leftLay->setSpacing(0);
  op_rail_ = new OperatorRail;
  leftLay->addWidget(op_rail_);
  op_lib_ = new OperatorLibrary;
  leftLay->addWidget(op_lib_, 1);
  left->setMinimumWidth(220);
  left->setMaximumWidth(320);
  connect(op_lib_, &OperatorLibrary::operatorActivated, this,
          &MainWindow::onAddOperator);
  connect(op_rail_, &OperatorRail::categorySelected, op_lib_,
          &OperatorLibrary::setCategoryFilter);
  horizontal->addWidget(left);

  // —— Center-left: flow tab bar + canvas ——
  auto* flowPane = new QWidget;
  flowPane->setObjectName(QStringLiteral("flowPane"));
  auto* flowLay = new QVBoxLayout(flowPane);
  flowLay->setContentsMargins(0, 0, 0, 0);
  flowLay->setSpacing(0);
  flow_tabs_ = new FlowTabBar;
  flowLay->addWidget(flow_tabs_);
  flow_scene_ = new FlowScene(this);
  flow_view_ = new FlowView(flow_scene_);
  flowLay->addWidget(flow_view_, 1);
  connect(flow_view_, &FlowView::operatorDropped, this, &MainWindow::onDropOperator);
  connect(flow_tabs_, &FlowTabBar::runOnceRequested, this, &MainWindow::onRunOnce);
  connect(flow_tabs_, &FlowTabBar::runContinuousRequested, this,
          &MainWindow::onRunContinuous);
  horizontal->addWidget(flowPane);

  connect(flow_scene_, &FlowScene::nodeSelected, this, &MainWindow::onNodeSelected);
  connect(flow_scene_, &FlowScene::edgeConnected, this, &MainWindow::onEdgeConnected);
  connect(flow_scene_, &FlowScene::linkNotice, this, &MainWindow::onLinkNotice);

  // Property float (VM light panel) — created lazily-ish but keep ready
  prop_float_ = new PropertyFloat(this);
  prop_panel_ = prop_float_->panel();
  connect(prop_float_, &PropertyFloat::paramEdited, this, &MainWindow::onParamEdited);
  connect(prop_float_, &PropertyFloat::runModule, this, &MainWindow::onRunOnce);
  connect(prop_float_, &PropertyFloat::runModuleContinuous, this,
          &MainWindow::onRunContinuous);

  // —— Right: image tabs + host strip + filmstrip ——
  auto* imagePane = new QWidget;
  imagePane->setObjectName(QStringLiteral("imagePane"));
  auto* imgLay = new QVBoxLayout(imagePane);
  imgLay->setContentsMargins(0, 0, 0, 0);
  imgLay->setSpacing(0);
  image_tabs_ = new QTabWidget;
  image_view_ = new ImageView;
  output_view_ = new ImageView;
  image_tabs_->addTab(image_view_, QStringLiteral("全局图像"));
  image_tabs_->addTab(output_view_, QStringLiteral("模块结果"));
  imgLay->addWidget(image_tabs_, 1);
  host_strip_ = new HostStrip;
  imgLay->addWidget(host_strip_);
  filmstrip_ = new FilmstripBar;
  imgLay->addWidget(filmstrip_);
  connect(filmstrip_, &FilmstripBar::openImageRequested, this, &MainWindow::onOpenImage);
  connect(filmstrip_, &FilmstripBar::runAllRequested, this, &MainWindow::onRunOnce);
  horizontal->addWidget(imagePane);

  horizontal->setChildrenCollapsible(false);
  horizontal->setStretchFactor(0, 0);
  horizontal->setStretchFactor(1, 2);
  horizontal->setStretchFactor(2, 2);
  horizontal->setSizes({260, 560, 520});
  flowPane->setMinimumWidth(240);
  imagePane->setMinimumWidth(280);
  rootSplit->addWidget(horizontal);

  // —— Bottom: 当前结果 / 历史结果 / 帮助 / 变量 / 通信 ——
  auto* bottom = new QTabWidget;
  result_table_ = new QTableWidget(0, 3);
  result_table_->setHorizontalHeaderLabels(
      {QStringLiteral("模块/字段"), QStringLiteral("值"), QStringLiteral("类型")});
  result_table_->horizontalHeader()->setStretchLastSection(true);
  result_table_->verticalHeader()->setVisible(false);
  result_table_->setAlternatingRowColors(true);
  result_table_->setSelectionBehavior(QAbstractItemView::SelectRows);
  result_table_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  result_table_->setObjectName(QStringLiteral("resultTree"));
  bottom->addTab(result_table_, QStringLiteral("当前结果"));

  result_log_ = new QPlainTextEdit;
  result_log_->setReadOnly(true);
  result_log_->setPlaceholderText(
      QStringLiteral("历史结果 / 运行日志 / GenTL / 解码 / Comm"));
  bottom->addTab(result_log_, QStringLiteral("历史结果"));

  auto* helpPad = new QPlainTextEdit;
  helpPad->setReadOnly(true);
  helpPad->setPlainText(
      QStringLiteral("帮助：左侧分类算子库拖入画布连线；双击节点打开属性浮窗；"
                     "工具栏 ▶单次 / ↻连续 / ■停止；胶片条可打开本地图。\n"
                     "交互对齐 VisionMaster：纵栏分类 · 属性浮窗 · 底栏结果。"));
  bottom->addTab(helpPad, QStringLiteral("帮助"));

  var_watch_ = new VarWatchPanel;
  bottom->addTab(var_watch_, QStringLiteral("变量监视"));
  comm_panel_ = new CommPanel(comm_hub_);
  bottom->addTab(comm_panel_, QStringLiteral("通信"));

  rootSplit->addWidget(bottom);
  rootSplit->setChildrenCollapsible(false);
  rootSplit->setStretchFactor(0, 4);
  rootSplit->setStretchFactor(1, 1);
  rootSplit->setSizes({700, 200});
  bottom->setMinimumHeight(100);

  setCentralWidget(central);

  project_label_ = new QLabel(QStringLiteral("方案: —"));
  statusBar()->setObjectName(QStringLiteral("workbenchStatus"));
  statusBar()->addWidget(project_label_, 1);
  status_busy_ = new QLabel(QStringLiteral("● 空闲"));
  statusBar()->addPermanentWidget(status_busy_);
  status_backend_ = new QLabel(
      QStringLiteral("SIEANS Vision · %1")
          .arg(QString::fromStdString(sieans::native_version())));
  statusBar()->addPermanentWidget(status_backend_);
}

void MainWindow::buildMenus() {
  auto* files = menuBar()->addMenu(QStringLiteral("文件(&F)"));
  files->addAction(QStringLiteral("新建方案"), this, &MainWindow::onNewProject,
                   QKeySequence::New);
  files->addAction(QStringLiteral("打开方案…"), this, &MainWindow::onOpenProject,
                   QKeySequence::Open);
  files->addAction(QStringLiteral("保存方案"), this, &MainWindow::onSaveProject,
                   QKeySequence::Save);
  files->addAction(QStringLiteral("方案另存为…"), this, &MainWindow::onSaveProjectAs);
  files->addSeparator();
  files->addAction(QStringLiteral("打开图像…"), this, &MainWindow::onOpenImage);
  files->addAction(QStringLiteral("加载示例 QR"), this, &MainWindow::onLoadSample);
  files->addSeparator();
  files->addAction(QStringLiteral("退出"), qApp, &QApplication::quit, QKeySequence::Quit);

  auto* settings = menuBar()->addMenu(QStringLiteral("设置"));
  settings->addAction(QStringLiteral("通信管理…"), this, &MainWindow::onOpenCommManager);

  auto* tools = menuBar()->addMenu(QStringLiteral("工具"));
  tools->addAction(QStringLiteral("C++ QR 解码"), this, &MainWindow::onDecodeQr,
                   QKeySequence(Qt::Key_F5));
  tools->addAction(QStringLiteral("适应图像窗口"), image_view_, &ImageView::fitToView);
  tools->addAction(QStringLiteral("适应流程画布"), flow_view_, &FlowView::fitAll);

  auto* system = menuBar()->addMenu(QStringLiteral("系统"));
  auto* edit = system->addMenu(QStringLiteral("编辑"));
  edit->addAction(QStringLiteral("删除选中节点"), this, [this]() {
    const QString id = flow_scene_->selectedNodeId();
    if (id.isEmpty() || id == QLatin1String("source")) return;
    auto& steps = document_.stepsMut();
    steps.erase(std::remove_if(steps.begin(), steps.end(),
                               [&](const FlowStep& s) { return s.id == id; }),
                steps.end());
    auto& edges = document_.edgesMut();
    edges.erase(std::remove_if(edges.begin(), edges.end(),
                               [&](const FlowEdge& e) {
                                 return e.from == id || e.to == id;
                               }),
                edges.end());
    applyDocumentToUi();
  });
  edit->addAction(QStringLiteral("删除选中连线"), this, [this]() {
    flow_scene_->removeSelectedEdge();
  });

  auto* work = menuBar()->addMenu(QStringLiteral("工程管理"));
  work->addAction(QStringLiteral("变量监视"), this, [this]() {
    showStatus(QStringLiteral("见右侧「变量」页"));
  });

  auto* devices = menuBar()->addMenu(QStringLiteral("设备与模型"));
  devices->addAction(QStringLiteral("相机管理…"), this, &MainWindow::onOpenCameraManager);
  devices->addAction(QStringLiteral("枚举 GenTL"), this, &MainWindow::onEnumerateGenTL);
  devices->addAction(QStringLiteral("连续采集预览"), this,
                     &MainWindow::onStartContinuousPreview);
  devices->addAction(QStringLiteral("停止预览"), this, &MainWindow::onStopContinuousPreview);
  devices->addAction(QStringLiteral("通信管理…"), this, &MainWindow::onOpenCommManager);

  auto* records = menuBar()->addMenu(QStringLiteral("记录与账号"));
  records->addAction(QStringLiteral("运行日志…"), this, [this]() {
    showStatus(QStringLiteral("见底栏「历史结果」"));
  });
  records->addAction(QStringLiteral("变量监视…"), this, [this]() {
    showStatus(QStringLiteral("见底栏「变量监视」"));
  });

  auto* help = menuBar()->addMenu(QStringLiteral("帮助(&H)"));
  help->addAction(QStringLiteral("关于"), this, &MainWindow::onAbout);
}

void MainWindow::buildToolbar() {
  auto* tb = addToolBar(QStringLiteral("工程与运行"));
  tb->setObjectName(QStringLiteral("mainToolBar"));
  tb->setMovable(false);
  tb->setIconSize(QSize(20, 20));
  brand_label_ = new QLabel(QStringLiteral("SIEANS"));
  brand_label_->setObjectName(QStringLiteral("brand"));
  tb->addWidget(brand_label_);
  tb->addSeparator();
  tb->addAction(QStringLiteral("打开"), this, &MainWindow::onOpenProject);
  tb->addAction(QStringLiteral("保存"), this, &MainWindow::onSaveProject);
  tb->addSeparator();
  tb->addAction(QStringLiteral("相机"), this, &MainWindow::onOpenCameraManager);
  tb->addAction(QStringLiteral("通信"), this, &MainWindow::onOpenCommManager);
  act_preview_ = tb->addAction(QStringLiteral("连续预览"), this,
                               &MainWindow::onStartContinuousPreview);
  act_preview_stop_ =
      tb->addAction(QStringLiteral("停预览"), this, &MainWindow::onStopContinuousPreview);
  tb->addSeparator();
  act_run_ = tb->addAction(QStringLiteral("▶ 运行"), this, &MainWindow::onRunOnce);
  act_cont_ =
      tb->addAction(QStringLiteral("↻ 连续"), this, &MainWindow::onRunContinuous);
  act_stop_ = tb->addAction(QStringLiteral("■ 停止"), this, &MainWindow::onStopRun);
  tb->addSeparator();
  tb->addAction(QStringLiteral("示例 QR"), this, &MainWindow::onLoadSample);
  tb->addAction(QStringLiteral("解码"), this, &MainWindow::onDecodeQr);
  tb->addSeparator();
  mode_badge_ = new QLabel(QStringLiteral("设计态"));
  mode_badge_->setObjectName(QStringLiteral("modeBadge"));
  mode_badge_->setProperty("runMode", false);
  tb->addWidget(mode_badge_);
  auto* listen = new QLabel(QStringLiteral("监听·—"));
  listen->setObjectName(QStringLiteral("commListenBadge"));
  listen->setToolTip(QStringLiteral("通信监听状态 — 点击打开通信管理"));
  listen->setCursor(Qt::PointingHandCursor);
  tb->addWidget(listen);
}

void MainWindow::applyDocumentToUi() {
  flow_scene_->loadDocument(&document_);
  project_label_->setText(QStringLiteral("方案: %1").arg(document_.name()));
  setWindowTitle(QStringLiteral("%1 — SIEANS Vision · 设计态").arg(document_.name()));
  if (flow_tabs_) flow_tabs_->setFlowName(QStringLiteral("流程1"));
  QTimer::singleShot(0, flow_view_, &FlowView::fitAll);
  if (prop_float_) prop_float_->hide();
  else if (prop_panel_) prop_panel_->clear();
  flow_vars_ = document_.variables();
  if (var_watch_) {
    var_watch_->setWatchKeys(document_.hostWatchKeys());
    var_watch_->setVariables(flow_vars_);
  }
  if (comm_panel_) comm_panel_->bindDocument(document_.commManager());
  if (comm_hub_) comm_hub_->loadFromCommManager(document_.commManager());
  if (host_strip_) host_strip_->updateFromVars(flow_vars_);
}

void MainWindow::syncVarsToUi() {
  document_.setVariables(flow_vars_);
  if (var_watch_) var_watch_->setVariables(flow_vars_);
  if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
  if (host_strip_)
    host_strip_->updateFromVars(
        flow_vars_, flow_vars_.value(QStringLiteral("barcodeCount")).toInt());
}

void MainWindow::logResult(const QString& line) {
  const QString stamp =
      QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss.zzz"));
  result_log_->appendPlainText(QStringLiteral("[%1] %2").arg(stamp, line));
}

void MainWindow::showStatus(const QString& msg, int timeout_ms) {
  statusBar()->showMessage(msg, timeout_ms);
}

void MainWindow::setBusy(bool busy) {
  busy_.store(busy);
  status_busy_->setText(busy ? QStringLiteral("忙碌") : QStringLiteral("空闲"));
  status_busy_->setStyleSheet(busy ? QStringLiteral("color:#d4a017;")
                                   : QStringLiteral("color:#2d9b6c;"));
  updateRunChrome();
}

void MainWindow::updateRunChrome() {
  const bool busy = busy_.load();
  if (act_run_) act_run_->setEnabled(!busy || continuous_run_);
  if (act_stop_) act_stop_->setEnabled(busy || continuous_run_ || preview_active_);
}

bool MainWindow::loadImagePath(const QString& path) {
  QImage img(path);
  if (img.isNull()) {
    QMessageBox::warning(this, QStringLiteral("打开失败"),
                         QStringLiteral("无法读取图像:\n%1").arg(path));
    return false;
  }
  current_path_ = path;
  image_view_->setImage(img, true);
  if (output_view_) output_view_->setImage(img, true);
  logResult(QStringLiteral("已加载 %1 (%2×%3)")
                .arg(QFileInfo(path).fileName())
                .arg(img.width())
                .arg(img.height()));
  if (filmstrip_)
    filmstrip_->setStatus(QStringLiteral("本地 · %1").arg(QFileInfo(path).fileName()));
  showStatus(QStringLiteral("已加载 %1").arg(path));
  return true;
}

QStringList MainWindow::topologicalStepIds() const {
  QStringList ordered;
  QSet<QString> visited;
  QHash<QString, QStringList> outs;
  for (const FlowEdge& e : document_.edges()) outs[e.from] << e.to;
  QQueue<QString> q;
  q.enqueue(QStringLiteral("source"));
  while (!q.isEmpty()) {
    const QString id = q.dequeue();
    if (visited.contains(id)) continue;
    visited.insert(id);
    if (id != QLatin1String("source")) ordered << id;
    for (const QString& n : outs.value(id)) q.enqueue(n);
  }
  for (const FlowStep& s : document_.steps()) {
    if (!visited.contains(s.id)) ordered << s.id;
  }
  return ordered;
}

void MainWindow::onNewProject() {
  document_.seedGentlQrDemo();
  applyDocumentToUi();
  logResult(QStringLiteral("新建 GenTL→QR 方案"));
}

void MainWindow::onOpenProject() {
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("打开方案"), defaultProjectsDir(),
      QStringLiteral("SIEANS 工程 (*.sieans *.json *.sol);;全部 (*.*)"));
  if (path.isEmpty()) return;
  QString err;
  if (!document_.loadFromFile(path, &err)) {
    QMessageBox::warning(this, QStringLiteral("打开失败"), err);
    return;
  }
  applyDocumentToUi();
  logResult(QStringLiteral("已打开方案：%1 · %2 步")
                .arg(path)
                .arg(document_.steps().size()));
}

void MainWindow::onSaveProject() {
  QString path = document_.path();
  if (path.isEmpty()) {
    onSaveProjectAs();
    return;
  }
  document_.setVariables(flow_vars_);
  QString err;
  if (!document_.saveToFile(path, &err)) {
    QMessageBox::warning(this, QStringLiteral("保存失败"), err);
    return;
  }
  logResult(QStringLiteral("方案已保存：%1").arg(path));
}

void MainWindow::onSaveProjectAs() {
  const QString path = QFileDialog::getSaveFileName(
      this, QStringLiteral("方案另存为"),
      defaultProjectsDir() + QLatin1Char('/') + document_.name() +
          QStringLiteral(".sieans"),
      QStringLiteral("SIEANS 工程 (*.sieans)"));
  if (path.isEmpty()) return;
  document_.setVariables(flow_vars_);
  QString err;
  if (!document_.saveToFile(path, &err)) {
    QMessageBox::warning(this, QStringLiteral("保存失败"), err);
    return;
  }
  document_.loadFromFile(path);
  logResult(QStringLiteral("方案已保存：%1").arg(path));
}

void MainWindow::onOpenImage() {
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("打开图像"),
      QStringLiteral("/home/allen/文档/sieansvision/artifacts"),
      QStringLiteral("Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"));
  if (path.isEmpty()) return;
  if (loadImagePath(path)) runPipeline(image_view_->currentImage(), true);
}

void MainWindow::onLoadSample() {
  const QString path = samplePathCandidates();
  if (path.isEmpty()) {
    QMessageBox::information(this, QStringLiteral("无示例"),
                             QStringLiteral("未找到 sample-qr.png"));
    return;
  }
  if (loadImagePath(path)) runPipeline(image_view_->currentImage(), true);
}

void MainWindow::onDecodeQr() {
  runPipeline(image_view_->currentImage(), true);
}

void MainWindow::runDecodeOnImage(const QImage& src, bool updateFlowStates) {
  runPipeline(src, updateFlowStates);
}

void MainWindow::runPipeline(const QImage& src, bool updateFlowStates) {
  if (src.isNull()) {
    showStatus(QStringLiteral("请先加载图像或开启预览"));
    return;
  }

  QImage working = src;
  image_view_->setLiveImage(working);
  std::vector<sieans::BarcodeHit> hits;
  double decodeMs = 0;

  if (updateFlowStates) flow_scene_->resetRunStates();

  const QStringList order = topologicalStepIds();
  QHash<QString, StepSnap> step_snaps;
  for (const QString& id : order) {
    FlowStep* step = document_.findStep(id);
    if (!step) continue;
    const QString op = step->operation;
    if (updateFlowStates)
      flow_scene_->setNodeRunState(id, QStringLiteral("运行中"));

    bool ok = true;
    QString note;

    if (op == QLatin1String("camera_capture")) {
      note = QStringLiteral("采图 %1×%2").arg(working.width()).arg(working.height());
    } else if (op == QLatin1String("preprocess")) {
      working = applyPreprocess(working, step->params);
      image_view_->setLiveImage(working);
      note = QStringLiteral("预处理 %1")
                 .arg(step->params.value(QStringLiteral("mode"), QStringLiteral("gray"))
                          .toString());
    } else if (op == QLatin1String("barcode") || op == QLatin1String("qr_decode")) {
      QImage rgb = toRgb888(working);
      sieans::BarcodeOptions opts;
      opts.formats =
          step->params.value(QStringLiteral("types"), QStringLiteral("QRCode"))
              .toString()
              .toStdString();
      opts.max_codes = step->params.value(QStringLiteral("maxCodes"), 16).toInt();
      opts.try_rotate = true;
      opts.try_downscale = true;
      const auto t0 = std::chrono::steady_clock::now();
      try {
        hits = sieans::decode_barcodes(rgb.constBits(), rgb.width(), rgb.height(),
                                       rgb.bytesPerLine(), sieans::PixelFormat::RGB24,
                                       opts);
      } catch (const std::exception& ex) {
        ok = false;
        note = QString::fromUtf8(ex.what());
        hits.clear();
      }
      decodeMs = std::chrono::duration<double, std::milli>(
                     std::chrono::steady_clock::now() - t0)
                     .count();
      QStringList texts;
      for (const auto& h : hits) texts << QString::fromStdString(h.text);
      flow_vars_.insert(QStringLiteral("barcodeCount"), int(hits.size()));
      flow_vars_.insert(QStringLiteral("barcodeText"),
                        texts.isEmpty() ? QString() : texts.first());
      flow_vars_.insert(QStringLiteral("barcodeAll"), texts.join(QLatin1Char('\n')));
      const int minC = step->params.value(QStringLiteral("judgeMinCount"), 1).toInt();
      const bool gate = int(hits.size()) >= minC;
      flow_vars_.insert(QStringLiteral("barcodeOk"), gate ? 1 : 0);
      flow_vars_.insert(QStringLiteral("passGate"), gate ? 1 : 0);
      {
        StepSnap snap;
        snap.count = int(hits.size());
        snap.ok = gate;
        for (const auto& h : hits) snap.texts << QString::fromStdString(h.text);
        step_snaps.insert(id, snap);
      }
      ok = gate || !step->params.value(QStringLiteral("judgeEnable"), true).toBool();
      note = QStringLiteral("%1 码 · %2 ms").arg(hits.size()).arg(decodeMs, 0, 'f', 1);

      QVector<OverlayHit> overlays;
      result_table_->setRowCount(0);
      int i = 0;
      for (const auto& h : hits) {
        OverlayHit o;
        o.text = QString::fromStdString(h.text);
        o.format = QString::fromStdString(h.format);
        for (const auto& p : h.polygon) o.polygon << QPointF(p.x, p.y);
        overlays.push_back(o);
        const int row = result_table_->rowCount();
        result_table_->insertRow(row);
        result_table_->setItem(
            row, 0,
            new QTableWidgetItem(QStringLiteral("barcode[%1].text").arg(i)));
        result_table_->setItem(row, 1, new QTableWidgetItem(o.text));
        result_table_->setItem(row, 2, new QTableWidgetItem(o.format));
        ++i;
      }
      image_view_->setOverlays(overlays);
    } else if (op == QLatin1String("var_calc")) {
      ExprEval ev;
      ev.setVars(flow_vars_);
      ev.setSteps(step_snaps);
      const QVariantList rows = step->params.value(QStringLiteral("expressions")).toList();
      QStringList done;
      if (!rows.isEmpty()) {
        for (const QVariant& rv : rows) {
          const QVariantMap row = rv.toMap();
          if (row.contains(QStringLiteral("enabled")) && !row.value(QStringLiteral("enabled")).toBool())
            continue;
          const QString name = row.value(QStringLiteral("name")).toString();
          QString expr = row.value(QStringLiteral("expr")).toString();
          if (expr.isEmpty()) expr = row.value(QStringLiteral("expression")).toString();
          if (name.isEmpty()) continue;
          QString err;
          QVariant val = ev.eval(expr, &err);
          // bool-ish to int for gate vars
          if (val.typeId() == QMetaType::Bool) val = val.toBool() ? 1 : 0;
          flow_vars_.insert(name, val);
          done << QStringLiteral("%1=%2").arg(name, val.toString());
          // refresh evaluator vars for chained rows
          ev.setVars(flow_vars_);
        }
      } else {
        // fallback: ensure passGate from barcodeCount
        const int count = flow_vars_.value(QStringLiteral("barcodeCount")).toInt();
        flow_vars_.insert(QStringLiteral("barcodeOk"), count >= 1 ? 1 : 0);
        flow_vars_.insert(QStringLiteral("passGate"), count >= 1 ? 1 : 0);
        done << QStringLiteral("passGate(fallback)");
      }
      ok = flow_vars_.value(QStringLiteral("passGate")).toInt() != 0 ||
           flow_vars_.value(QStringLiteral("passGate")).toBool();
      note = done.join(QLatin1Char(' '));
      StepSnap snap;
      snap.ok = ok;
      snap.count = flow_vars_.value(QStringLiteral("barcodeCount")).toInt();
      step_snaps.insert(id, snap);
    } else if (op == QLatin1String("result_gate")) {
      const int minC = step->params.value(QStringLiteral("minCount"), 1).toInt();
      const int count = flow_vars_.value(QStringLiteral("barcodeCount")).toInt();
      const bool gate = count >= minC;
      flow_vars_.insert(QStringLiteral("barcodeOk"), gate ? 1 : 0);
      flow_vars_.insert(QStringLiteral("passGate"), gate ? 1 : 0);
      ok = gate;
      note = QStringLiteral("passGate=%1 count=%2 min=%3")
                 .arg(gate ? 1 : 0)
                 .arg(count)
                 .arg(minC);
    } else if (op == QLatin1String("format_data")) {
      const QString tmpl =
          step->params
              .value(QStringLiteral("template"),
                     QStringLiteral("BARCODE ok={0} count={1} text={2}"))
              .toString();
      const QString argsCsv =
          step->params
              .value(QStringLiteral("args"),
                     QStringLiteral("passGate,barcodeCount,barcodeText"))
              .toString();
      QString out = tmpl;
      const QStringList args = argsCsv.split(QLatin1Char(','), Qt::SkipEmptyParts);
      for (int i = 0; i < args.size(); ++i) {
        const QString key = args[i].trimmed();
        out.replace(QStringLiteral("{%1}").arg(i), flow_vars_.value(key).toString());
      }
      // also ${flow.x}
      out = CommHub::expandTemplate(out, flow_vars_);
      const QString target =
          step->params.value(QStringLiteral("targetVar"), QStringLiteral("formatted"))
              .toString();
      flow_vars_.insert(target, out);
      flow_vars_.insert(QStringLiteral("formatted"), out);
      flow_vars_.insert(QStringLiteral("commPayload"), out);
      note = out.left(80);
    } else if (op == QLatin1String("send_data")) {
      QString msg = step->params.value(QStringLiteral("message")).toString();
      if (msg.isEmpty())
        msg = flow_vars_.value(QStringLiteral("formatted")).toString();
      if (msg.isEmpty())
        msg = flow_vars_.value(QStringLiteral("commPayload")).toString();
      msg = CommHub::expandTemplate(msg, flow_vars_);
      const QString device =
          step->params.value(QStringLiteral("device"), QStringLiteral("LocalLoop"))
              .toString();
      QString err;
      ok = comm_hub_->sendPayload(device, msg, &err);
      flow_vars_.insert(QStringLiteral("commPayload"), msg);
      note = QStringLiteral("TX→%1: %2").arg(device, msg.left(60));
    } else if (op == QLatin1String("receive_data")) {
      const QString rx = comm_hub_->lastRx();
      const QString target =
          step->params.value(QStringLiteral("targetVar"), QStringLiteral("lastRecv"))
              .toString();
      flow_vars_.insert(target, rx);
      ok = !rx.isEmpty();
      note = rx.isEmpty() ? QStringLiteral("(无 RX)") : rx.left(60);
    } else if (op == QLatin1String("save_image")) {
      const QString dir =
          step->params
              .value(QStringLiteral("dir"),
                     QStringLiteral("/home/allen/文档/sieansvision/artifacts"))
              .toString();
      QDir().mkpath(dir);
      const QString path =
          dir + QStringLiteral("/sieans-qt-run-%1.png")
                    .arg(QDateTime::currentDateTime().toString(
                        QStringLiteral("HHmmss")));
      ok = working.save(path);
      note = path;
    } else {
      note = QStringLiteral("透传 / 未实现执行体");
      ok = true;
    }

    if (updateFlowStates) {
      flow_scene_->setNodeRunState(
          id, ok ? QStringLiteral("OK") : QStringLiteral("NG"));
    }
    logResult(QStringLiteral("%1 [%2] %3").arg(step->name, op, note));
  }

  syncVarsToUi();
  if (host_strip_) {
    const bool gateOk = flow_vars_.value(QStringLiteral("passGate")).toInt() != 0 ||
                        flow_vars_.value(QStringLiteral("passGate")).toBool();
    host_strip_->setAlarm(!gateOk && flow_vars_.contains(QStringLiteral("passGate")),
                          gateOk ? QString() : QStringLiteral("passGate=0"));
  }
  showStatus(QStringLiteral("流水线完成 · 码 %1 · %2 ms")
                 .arg(hits.size())
                 .arg(decodeMs, 0, 'f', 1));

  const QByteArray smoke = qgetenv("SIEANS_QT_SMOKE_REPORT");
  if (!smoke.isEmpty()) {
    QFile f(QString::fromUtf8(smoke));
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
      const QString line =
          QStringLiteral("codes=%1 ms=%2 w=%3 h=%4 passGate=%5\n")
              .arg(hits.size())
              .arg(decodeMs, 0, 'f', 2)
              .arg(src.width())
              .arg(src.height())
              .arg(flow_vars_.value(QStringLiteral("passGate")).toString());
      f.write(line.toUtf8());
    }
  }
}

void MainWindow::onEnumerateGenTL() {
  // GenTL
  if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("GenTL: 未链接 MvCameraControl（需 /opt/MVS）"));
  } else {
    try {
      auto devices = sieans::GenTLCapture::enumerate();
      logResult(QStringLiteral("—— GenTL 枚举 %1 台 ——").arg(devices.size()));
      for (const auto& d : devices) {
        logResult(QStringLiteral("  %1 | %2 | %3")
                      .arg(QString::fromStdString(d.id),
                           QString::fromStdString(d.model),
                           QString::fromStdString(d.serial)));
      }
      if (devices.empty()) logResult(QStringLiteral("  (未发现 GenTL 设备)"));
    } catch (const std::exception& ex) {
      logResult(QStringLiteral("GenTL 枚举失败: %1").arg(QString::fromUtf8(ex.what())));
    }
  }
  // UVC
  {
    const auto uvs = UvcCapture::enumerate();
    logResult(QStringLiteral("—— UVC 枚举 %1 台 ——").arg(uvs.size()));
    for (const auto& d : uvs)
      logResult(QStringLiteral("  %1").arg(d.label));
    if (uvs.isEmpty()) logResult(QStringLiteral("  (未发现 /dev/video*)"));
    showStatus(QStringLiteral("枚举完成 · UVC %1").arg(uvs.size()));
  }
}

void MainWindow::onOpenCommManager() {
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("通信管理 · TCP / LocalBus"));
  dlg.resize(640, 480);
  auto* lay = new QVBoxLayout(&dlg);
  auto* panel = new CommPanel(comm_hub_, &dlg);
  panel->bindDocument(document_.commManager());
  panel->setFlowVars(flow_vars_);
  lay->addWidget(panel);
  auto* box = new QDialogButtonBox(QDialogButtonBox::Close);
  lay->addWidget(box);
  connect(box, &QDialogButtonBox::rejected, &dlg, &QDialog::reject);
  connect(box, &QDialogButtonBox::clicked, &dlg, &QDialog::accept);
  dlg.exec();
}

void MainWindow::onOpenCameraManager() {
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("相机管理 · Soft / UVC / GenTL"));
  dlg.resize(560, 480);
  auto* lay = new QVBoxLayout(&dlg);
  auto* backend = new QComboBox;
  backend->addItem(QStringLiteral("GenTL 工业相机"), QStringLiteral("gentl"));
  backend->addItem(QStringLiteral("USB UVC"), QStringLiteral("uvc"));
  const QString cur = document_.cameraBackend();
  backend->setCurrentIndex(backend->findData(cur) >= 0 ? backend->findData(cur) : 0);
  lay->addWidget(new QLabel(QStringLiteral("采集后端")));
  lay->addWidget(backend);
  auto* list = new QListWidget;
  lay->addWidget(new QLabel(QStringLiteral("设备列表")));
  lay->addWidget(list, 1);
  QStringList ids;

  auto refill = [&]() {
    list->clear();
    ids.clear();
    const QString kind = backend->currentData().toString();
    if (kind == QLatin1String("uvc")) {
      const auto uvs = UvcCapture::enumerate();
      if (uvs.isEmpty()) {
        list->addItem(QStringLiteral("(未发现 UVC — 插入摄像头后刷新)"));
      } else {
        for (const auto& d : uvs) {
          list->addItem(d.label);
          ids.push_back(d.id);
        }
      }
    } else if (sieans::GenTLCapture::available()) {
      try {
        for (const auto& d : sieans::GenTLCapture::enumerate()) {
          list->addItem(QStringLiteral("%1 | %2 | %3")
                            .arg(QString::fromStdString(d.model),
                                 QString::fromStdString(d.serial),
                                 QString::fromStdString(d.id)));
          ids.push_back(QString::fromStdString(d.id));
        }
        if (ids.isEmpty()) list->addItem(QStringLiteral("(未发现 GenTL 设备)"));
      } catch (const std::exception& ex) {
        list->addItem(QStringLiteral("枚举失败: %1").arg(QString::fromUtf8(ex.what())));
      }
    } else {
      list->addItem(QStringLiteral("(GenTL 不可用)"));
    }
    const QString want = document_.cameraDeviceId();
    for (int i = 0; i < ids.size(); ++i) {
      if (!want.isEmpty() &&
          (ids[i] == want || list->item(i)->text().contains(want) ||
           want.contains(ids[i]))) {
        list->setCurrentRow(i);
        break;
      }
    }
  };
  refill();
  connect(backend, QOverload<int>::of(&QComboBox::currentIndexChanged), &dlg,
          [&](int) { refill(); });

  auto* btns = new QHBoxLayout;
  auto* btnRefresh = new QPushButton(QStringLiteral("刷新"));
  auto* btnOpen = new QPushButton(QStringLiteral("连接并连续预览"));
  btnOpen->setObjectName(QStringLiteral("accentBtn"));
  auto* btnStop = new QPushButton(QStringLiteral("停止预览"));
  auto* btnClose = new QPushButton(QStringLiteral("断开"));
  btns->addWidget(btnRefresh);
  btns->addWidget(btnOpen);
  btns->addWidget(btnStop);
  btns->addWidget(btnClose);
  lay->addLayout(btns);
  auto* box = new QDialogButtonBox(QDialogButtonBox::Close);
  lay->addWidget(box);
  connect(box, &QDialogButtonBox::rejected, &dlg, &QDialog::reject);
  connect(box, &QDialogButtonBox::clicked, &dlg, &QDialog::accept);
  connect(btnRefresh, &QPushButton::clicked, &dlg, [&]() { refill(); });

  connect(btnOpen, &QPushButton::clicked, &dlg, [&]() {
    const int row = list->currentRow();
    QString id = (row >= 0 && row < ids.size()) ? ids[row] : document_.cameraDeviceId();
    auto cam = document_.sourceConfig().value(QStringLiteral("cameraParams")).toMap();
    cam.insert(QStringLiteral("backendKind"), backend->currentData().toString());
    cam.insert(QStringLiteral("driver"), backend->currentData().toString());
    cam.insert(QStringLiteral("deviceId"),
               list->currentItem() ? list->currentItem()->text() : id);
    if (row >= 0 && row < ids.size()) cam.insert(QStringLiteral("deviceId"), ids[row]);
    auto sc = document_.sourceConfig();
    sc.insert(QStringLiteral("cameraParams"), cam);
    document_.sourceConfigMut() = sc;
    // also stamp first camera_capture step
    for (FlowStep& s : document_.stepsMut()) {
      if (s.operation == QLatin1String("camera_capture")) {
        s.params.insert(QStringLiteral("backendKind"), backend->currentData().toString());
        s.params.insert(QStringLiteral("driver"), backend->currentData().toString());
        s.params.insert(QStringLiteral("deviceId"), cam.value(QStringLiteral("deviceId")));
        break;
      }
    }
    onStartContinuousPreview();
  });
  connect(btnStop, &QPushButton::clicked, this, &MainWindow::onStopContinuousPreview);
  connect(btnClose, &QPushButton::clicked, this, [this]() {
    onStopContinuousPreview();
    QMetaObject::invokeMethod(cam_worker_, "closeDevice", Qt::QueuedConnection);
  });
  dlg.exec();
}

bool MainWindow::ensureCameraOpen() {
  const QString backend = document_.cameraBackend();
  if (backend == QLatin1String("uvc")) {
    // UVC always attempted; empty enum reported by worker
  } else if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("GenTL 不可用 — 可切 UVC"));
    return false;
  }
  QMetaObject::invokeMethod(
      cam_worker_, "openDeviceWithBackend", Qt::QueuedConnection,
      Q_ARG(QString, backend),
      Q_ARG(QString, document_.cameraDeviceId()),
      Q_ARG(double, document_.acquisitionFps()),
      Q_ARG(double, document_.exposureUs()));
  return true;
}

void MainWindow::onStartContinuousPreview() {
  const QString backend = document_.cameraBackend();
  if (backend != QLatin1String("uvc") && !sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("连续预览: GenTL 不可用（可在相机管理切 UVC）"));
    return;
  }
  ensureCameraOpen();
  QTimer::singleShot(200, this, [this]() {
    preview_active_ = true;
    updateRunChrome();
    QMetaObject::invokeMethod(cam_worker_, "startPreview", Qt::QueuedConnection);
    logResult(QStringLiteral("连续预览已请求启动"));
  });
}

void MainWindow::onStopContinuousPreview() {
  preview_active_ = false;
  QMetaObject::invokeMethod(cam_worker_, "stopPreview", Qt::QueuedConnection);
  updateRunChrome();
  logResult(QStringLiteral("连续预览停止请求已发送"));
}

void MainWindow::onPreviewFrame(const QImage& image, qint64 frameId) {
  ++preview_frames_;
  image_view_->setLiveImage(image);
  if (preview_frames_ == 1 || preview_frames_ % 30 == 0) {
    showStatus(QStringLiteral("预览帧 #%1 · %2×%3")
                   .arg(frameId)
                   .arg(image.width())
                   .arg(image.height()),
               2000);
  }
}

void MainWindow::onWorkerError(const QString& msg) {
  logResult(msg);
  showStatus(msg, 8000);
  if (host_strip_) host_strip_->setAlarm(true, msg);
}

void MainWindow::onWorkerStatus(const QString& msg) {
  showStatus(msg, 4000);
  logResult(msg);
}

void MainWindow::onRunOnce() {
  if (busy_.load()) {
    showStatus(QStringLiteral("忙碌中 — 忽略重复运行"), 1500);
    return;
  }
  setBusy(true);

  QImage frame = cam_worker_ ? cam_worker_->latestFrame() : QImage();
  if (frame.isNull()) frame = image_view_->currentImage();

  if (frame.isNull() && sieans::GenTLCapture::available()) {
    ensureCameraOpen();
    QMetaObject::invokeMethod(cam_worker_, "grabOne", Qt::QueuedConnection);
    for (int i = 0; i < 40 && frame.isNull(); ++i) {
      QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
      QThread::msleep(50);
      frame = cam_worker_->latestFrame();
    }
  }

  if (frame.isNull()) {
    logResult(QStringLiteral("运行失败: 无图像（请连续预览、采图或打开示例）"));
    setBusy(false);
    return;
  }

  image_view_->setLiveImage(frame);
  runPipeline(frame, true);
  setBusy(false);
}

void MainWindow::onRunContinuous() {
  if (continuous_run_) return;
  continuous_run_ = true;
  int interval = document_.runIntervalMs();
  if (interval <= 0) interval = 200;
  continuous_timer_.start(interval);
  if (!preview_active_) onStartContinuousPreview();
  logResult(QStringLiteral("连续运行已启动 · 间隔 %1 ms").arg(interval));
  showStatus(QStringLiteral("连续运行中"));
  updateRunChrome();
  onContinuousTick();
}

void MainWindow::onStopRun() {
  continuous_run_ = false;
  continuous_timer_.stop();
  busy_.store(false);
  setBusy(false);
  logResult(QStringLiteral("已停止运行"));
  showStatus(QStringLiteral("已停止"));
}

void MainWindow::onContinuousTick() {
  if (!continuous_run_) return;
  if (busy_.load()) return;
  onRunOnce();
}

void MainWindow::onNodeSelected(const QString& nodeId) {
  if (!prop_float_) return;
  if (nodeId.isEmpty()) {
    prop_float_->hide();
    return;
  }
  if (nodeId == QLatin1String("source")) {
    prop_float_->showForSource(document_.sourceConfig());
    // place float near right of flow canvas
    if (flow_view_) {
      const QPoint g = flow_view_->mapToGlobal(QPoint(flow_view_->width() - 20, 40));
      prop_float_->move(g);
    }
    return;
  }
  if (const FlowStep* s = document_.findStep(nodeId)) {
    prop_float_->showForStep(*s);
    if (flow_view_) {
      const QPoint g = flow_view_->mapToGlobal(QPoint(flow_view_->width() - 20, 40));
      prop_float_->move(g);
    }
  }
}

void MainWindow::onEdgeConnected(const QString&, const QString&, const QString&,
                                 const QString&) {
  // document already updated by FlowScene
}

void MainWindow::onLinkNotice(const QString& msg) {
  showStatus(msg, 2500);
  logResult(msg);
}

void MainWindow::onAddOperator(const QString& key, const QString& name) {
  addOperatorAt(key, name, QPointF(300, 160 + document_.steps().size() * 120), true);
}

void MainWindow::onDropOperator(const QString& key, const QPointF& scenePos) {
  const OperatorDef def = OperatorLibrary::findDef(key);
  addOperatorAt(key, def.name, scenePos, false);
}

void MainWindow::addOperatorAt(const QString& key, const QString& name,
                               const QPointF& pos, bool autoWire) {
  FlowStep s;
  s.id = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
  s.name = name.isEmpty() ? key : name;
  s.operation = key;
  s.position = pos;
  s.runState = QStringLiteral("等待执行");
  if (key == QLatin1String("barcode")) {
    s.params = {{QStringLiteral("types"), QStringLiteral("QRCode")},
                {QStringLiteral("maxCodes"), 16},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("judgeMinCount"), 1}};
  } else if (key == QLatin1String("camera_capture")) {
    s.params = {{QStringLiteral("driver"), QStringLiteral("gentl")},
                {QStringLiteral("backendKind"), QStringLiteral("gentl")},
                {QStringLiteral("continuousLive"), true}};
  } else if (key == QLatin1String("preprocess")) {
    s.params = {{QStringLiteral("mode"), QStringLiteral("gray")},
                {QStringLiteral("threshold"), 128}};
  } else if (key == QLatin1String("var_calc")) {
    s.params = {
        {QStringLiteral("scope"), QStringLiteral("flow")},
        {QStringLiteral("expressions"),
         QVariantList{
             QVariantMap{{QStringLiteral("name"), QStringLiteral("passGate")},
                         {QStringLiteral("expr"), QStringLiteral("barcodeCount >= 1")},
                         {QStringLiteral("enabled"), true}},
             QVariantMap{{QStringLiteral("name"), QStringLiteral("barcodeOk")},
                         {QStringLiteral("expr"), QStringLiteral("barcodeCount >= 1")},
                         {QStringLiteral("enabled"), true}},
         }}};
  } else if (key == QLatin1String("format_data")) {
    s.params = {
        {QStringLiteral("template"),
         QStringLiteral("BARCODE ok={0} count={1} text={2}")},
        {QStringLiteral("args"), QStringLiteral("passGate,barcodeCount,barcodeText")},
        {QStringLiteral("targetVar"), QStringLiteral("formatted")}};
  } else if (key == QLatin1String("send_data")) {
    s.params = {
        {QStringLiteral("device"), QStringLiteral("LocalLoop")},
        {QStringLiteral("message"),
         QStringLiteral(
             "BARCODE ok=${flow.passGate} count=${flow.barcodeCount} "
             "text=${flow.barcodeText}")}};
  } else if (key == QLatin1String("receive_data")) {
    s.params = {{QStringLiteral("targetVar"), QStringLiteral("lastRecv")}};
  } else if (key == QLatin1String("result_gate")) {
    s.params = {{QStringLiteral("minCount"), 1}};
  } else if (key == QLatin1String("save_image")) {
    s.params = {{QStringLiteral("dir"),
                 QStringLiteral("/home/allen/文档/sieansvision/artifacts")}};
  }
  if (autoWire) {
    QString from = QStringLiteral("source");
    if (!document_.steps().isEmpty()) from = document_.steps().last().id;
    s.imageFrom = from;
    document_.stepsMut().push_back(s);
    FlowEdge e;
    e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    e.from = from;
    e.to = s.id;
    document_.edgesMut().push_back(e);
  } else {
    document_.stepsMut().push_back(s);
  }
  applyDocumentToUi();
  logResult(QStringLiteral("已添加算子: %1 @ (%2,%3)%4")
                .arg(s.name)
                .arg(int(pos.x()))
                .arg(int(pos.y()))
                .arg(autoWire ? QStringLiteral(" · 已串线") : QStringLiteral(" · 拖放")));
}

void MainWindow::onParamEdited(const QString& nodeId, const QString& key,
                               const QString& value) {
  if (nodeId == QLatin1String("source")) {
    auto& sc = document_.sourceConfigMut();
    if (key.startsWith(QStringLiteral("cam."))) {
      auto cam = sc.value(QStringLiteral("cameraParams")).toMap();
      cam.insert(key.mid(4), value);
      sc.insert(QStringLiteral("cameraParams"), cam);
    } else {
      sc.insert(key, value);
    }
    return;
  }
  if (FlowStep* s = document_.findStep(nodeId)) {
    QVariant old = s->params.value(key);
    if (old.typeId() == QMetaType::Bool)
      s->params.insert(key, value == QLatin1String("true") || value == QLatin1String("1"));
    else if (old.typeId() == QMetaType::Int)
      s->params.insert(key, value.toInt());
    else if (old.typeId() == QMetaType::Double)
      s->params.insert(key, value.toDouble());
    else
      s->params.insert(key, value);
  }
}

void MainWindow::onAbout() {
  QMessageBox::about(
      this, QStringLiteral("关于 SIEANS Vision Qt"),
      QStringLiteral(
          "<b>SIEANS Vision Qt</b> — VisionMaster 交互/画面一比一：纵栏·属性浮窗·底栏结果<br/>"
          "下层 C++ <code>sieans_algo</code>，上层 Qt6 Widgets。<br/>"
          "native: %1<br/>GenTL: %2")
          .arg(QString::fromStdString(sieans::native_version()))
          .arg(sieans::GenTLCapture::available() ? QStringLiteral("built")
                                                 : QStringLiteral("stub")));
}

}  // namespace sieans_qt
