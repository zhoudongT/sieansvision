#include "MainWindow.hpp"
#include "Theme.hpp"

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
#include <QFormLayout>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QListWidget>
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
#include <QPixmap>
#include <QAbstractItemView>

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

}  // namespace

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle(QStringLiteral("SIEANS Vision — Qt"));
  resize(1540, 920);

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

  buildUi();
  buildMenus();
  buildToolbar();

  showStatus(QStringLiteral("就绪 · native %1 · GenTL %2")
                 .arg(QString::fromStdString(sieans::native_version()))
                 .arg(sieans::GenTLCapture::available() ? QStringLiteral("可用")
                                                        : QStringLiteral("桩/不可用")));

  // Prefer open-and-run-gentl-qr.sieans
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
  const QByteArray shot = qgetenv("SIEANS_QT_SCREENSHOT");
  if (!shot.isEmpty()) {
    const int shotDelay =
        (qgetenv("SIEANS_QT_AUTO_PREVIEW") == "1") ? 2800 : 900;
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
  if (cam_worker_) {
    // Atomically request loop exit (safe cross-thread); also stop MV grab.
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
      // last resort — avoid QThread destroy warning
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
  auto* central = new QWidget(this);
  auto* root = new QHBoxLayout(central);
  root->setContentsMargins(0, 0, 0, 0);
  root->setSpacing(0);

  // Left rail: operator library
  auto* leftRail = new QFrame;
  leftRail->setObjectName(QStringLiteral("rail"));
  leftRail->setFixedWidth(168);
  auto* leftLay = new QVBoxLayout(leftRail);
  leftLay->setContentsMargins(0, 0, 0, 0);
  op_lib_ = new OperatorLibrary;
  leftLay->addWidget(op_lib_);
  connect(op_lib_, &OperatorLibrary::operatorActivated, this,
          &MainWindow::onAddOperator);
  root->addWidget(leftRail);

  auto* splitter = new QSplitter(Qt::Horizontal);

  // Flow canvas + property under tab / vertical split
  auto* leftSplit = new QSplitter(Qt::Vertical);
  flow_scene_ = new FlowScene(this);
  flow_view_ = new FlowView(flow_scene_);
  leftSplit->addWidget(flow_view_);
  prop_panel_ = new PropertyPanel;
  leftSplit->addWidget(prop_panel_);
  leftSplit->setStretchFactor(0, 3);
  leftSplit->setStretchFactor(1, 2);
  leftSplit->setSizes({480, 240});
  splitter->addWidget(leftSplit);

  connect(flow_scene_, &FlowScene::nodeSelected, this, &MainWindow::onNodeSelected);
  connect(prop_panel_, &PropertyPanel::paramEdited, this, &MainWindow::onParamEdited);

  // Center image
  image_view_ = new ImageView;
  splitter->addWidget(image_view_);

  // Right: results table + log
  auto* right = new QWidget;
  auto* rightLay = new QVBoxLayout(right);
  rightLay->setContentsMargins(4, 4, 4, 4);
  rightLay->setSpacing(4);
  auto* resTitle = new QLabel(QStringLiteral("结果"));
  resTitle->setObjectName(QStringLiteral("sectionTitle"));
  rightLay->addWidget(resTitle);
  result_table_ = new QTableWidget(0, 3);
  result_table_->setHorizontalHeaderLabels(
      {QStringLiteral("#"), QStringLiteral("格式"), QStringLiteral("内容")});
  result_table_->horizontalHeader()->setStretchLastSection(true);
  result_table_->verticalHeader()->setVisible(false);
  result_table_->setAlternatingRowColors(true);
  result_table_->setSelectionBehavior(QAbstractItemView::SelectRows);
  result_table_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  result_table_->setMaximumHeight(220);
  rightLay->addWidget(result_table_);
  result_log_ = new QPlainTextEdit;
  result_log_->setReadOnly(true);
  result_log_->setPlaceholderText(
      QStringLiteral("运行日志 / GenTL / 解码结果"));
  rightLay->addWidget(result_log_, 1);
  splitter->addWidget(right);

  splitter->setStretchFactor(0, 0);
  splitter->setStretchFactor(1, 1);
  splitter->setStretchFactor(2, 0);
  splitter->setSizes({340, 820, 320});
  root->addWidget(splitter, 1);
  setCentralWidget(central);

  project_label_ = new QLabel(QStringLiteral("方案: —"));
  statusBar()->addWidget(project_label_, 1);
  status_busy_ = new QLabel(QStringLiteral("空闲"));
  statusBar()->addPermanentWidget(status_busy_);
  status_backend_ = new QLabel(
      QStringLiteral("sieans_algo %1")
          .arg(QString::fromStdString(sieans::native_version())));
  statusBar()->addPermanentWidget(status_backend_);
}

void MainWindow::buildMenus() {
  // Mirror PySide: 文件 / 设置 / 工具 / 系统 / 帮助 + 工程管理 / 设备与模型
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
  settings->addAction(QStringLiteral("设计态 / 运行模式…"), this, [this]() {
    QMessageBox::information(
        this, QStringLiteral("运行模式"),
        QStringLiteral("本波 Qt 以设计态工作台为主；运行模式 HMI 壳列入 NEXT。"));
  });
  settings->addAction(QStringLiteral("通信管理…"), this, [this]() {
    QMessageBox::information(
        this, QStringLiteral("通信管理"),
        QStringLiteral("TCP/Comm 管理器列入下一波；.sieans 内 commManager 已保留。"));
  });

  auto* tools = menuBar()->addMenu(QStringLiteral("工具"));
  tools->addAction(QStringLiteral("C++ QR 解码"), this, &MainWindow::onDecodeQr,
                   QKeySequence(Qt::Key_F5));
  tools->addAction(QStringLiteral("适应图像窗口"), image_view_, &ImageView::fitToView);

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

  auto* work = menuBar()->addMenu(QStringLiteral("工程管理"));
  work->addAction(QStringLiteral("三级变量"), this, [this]() {
    QStringList lines;
    lines << QStringLiteral("barcodeCount / barcodeText / passGate（流程变量）");
    for (const FlowStep& s : document_.steps()) {
      if (s.operation == QLatin1String("barcode") ||
          s.operation == QLatin1String("var_calc")) {
        lines << QStringLiteral("· %1 [%2]").arg(s.name, s.operation);
      }
    }
    QMessageBox::information(this, QStringLiteral("变量"), lines.join(QLatin1Char('\n')));
  });

  auto* devices = menuBar()->addMenu(QStringLiteral("设备与模型"));
  devices->addAction(QStringLiteral("相机管理…"), this, &MainWindow::onOpenCameraManager);
  devices->addAction(QStringLiteral("枚举 GenTL"), this, &MainWindow::onEnumerateGenTL);
  devices->addAction(QStringLiteral("连续采集预览"), this,
                     &MainWindow::onStartContinuousPreview);
  devices->addAction(QStringLiteral("停止预览"), this, &MainWindow::onStopContinuousPreview);
  devices->addAction(QStringLiteral("通信管理…"), this, [this]() {
    QMessageBox::information(this, QStringLiteral("通信管理"),
                             QStringLiteral("下一波接入 TCP/LocalBus（见 .sieans commManager）。"));
  });

  auto* help = menuBar()->addMenu(QStringLiteral("帮助(&H)"));
  help->addAction(QStringLiteral("关于"), this, &MainWindow::onAbout);
}

void MainWindow::buildToolbar() {
  auto* tb = addToolBar(QStringLiteral("工程与运行"));
  tb->setObjectName(QStringLiteral("mainToolBar"));
  tb->setMovable(false);
  tb->addAction(QStringLiteral("打开方案"), this, &MainWindow::onOpenProject);
  tb->addAction(QStringLiteral("保存"), this, &MainWindow::onSaveProject);
  tb->addSeparator();
  tb->addAction(QStringLiteral("相机"), this, &MainWindow::onOpenCameraManager);
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
}

void MainWindow::applyDocumentToUi() {
  flow_scene_->loadDocument(&document_);
  project_label_->setText(QStringLiteral("方案: %1").arg(document_.name()));
  setWindowTitle(QStringLiteral("SIEANS Vision — Qt · %1").arg(document_.name()));
  QTimer::singleShot(0, flow_view_, &FlowView::fitAll);
  prop_panel_->clear();
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
  // Allow stop always when continuous
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
  logResult(QStringLiteral("已加载 %1 (%2×%3)")
                .arg(QFileInfo(path).fileName())
                .arg(img.width())
                .arg(img.height()));
  showStatus(QStringLiteral("已加载 %1").arg(path));
  return true;
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
  QString err;
  if (!document_.saveToFile(path, &err)) {
    QMessageBox::warning(this, QStringLiteral("保存失败"), err);
    return;
  }
  document_.loadFromFile(path);  // refresh path_
  logResult(QStringLiteral("方案已保存：%1").arg(path));
}

void MainWindow::onOpenImage() {
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("打开图像"),
      QStringLiteral("/home/allen/文档/sieansvision/artifacts"),
      QStringLiteral("Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"));
  if (path.isEmpty()) return;
  if (loadImagePath(path)) runDecodeOnImage(image_view_->currentImage(), true);
}

void MainWindow::onLoadSample() {
  const QString path = samplePathCandidates();
  if (path.isEmpty()) {
    QMessageBox::information(this, QStringLiteral("无示例"),
                             QStringLiteral("未找到 sample-qr.png"));
    return;
  }
  if (loadImagePath(path)) runDecodeOnImage(image_view_->currentImage(), true);
}

void MainWindow::onDecodeQr() {
  runDecodeOnImage(image_view_->currentImage(), true);
}

void MainWindow::runDecodeOnImage(const QImage& src, bool updateFlowStates) {
  if (src.isNull()) {
    showStatus(QStringLiteral("请先加载图像或开启预览"));
    return;
  }
  QImage rgb = toRgb888(src);
  if (rgb.isNull()) return;

  sieans::BarcodeOptions opts;
  opts.formats = "QRCode";
  opts.max_codes = 16;
  opts.try_rotate = true;
  opts.try_downscale = true;

  const auto t0 = std::chrono::steady_clock::now();
  std::vector<sieans::BarcodeHit> hits;
  try {
    hits = sieans::decode_barcodes(rgb.constBits(), rgb.width(), rgb.height(),
                                   rgb.bytesPerLine(), sieans::PixelFormat::RGB24,
                                   opts);
  } catch (const std::exception& ex) {
    logResult(QStringLiteral("解码异常: %1").arg(QString::fromUtf8(ex.what())));
    if (updateFlowStates) {
      for (const FlowStep& s : document_.steps()) {
        if (s.operation == QLatin1String("barcode"))
          flow_scene_->setNodeRunState(s.id, QStringLiteral("失败"));
      }
    }
    return;
  }
  const auto ms = std::chrono::duration<double, std::milli>(
                      std::chrono::steady_clock::now() - t0)
                      .count();

  QVector<OverlayHit> overlays;
  result_table_->setRowCount(0);
  logResult(QStringLiteral("—— C++ 解码 %1 个 · %2 ms ——")
                .arg(hits.size())
                .arg(ms, 0, 'f', 1));
  int i = 0;
  for (const auto& h : hits) {
    OverlayHit o;
    o.text = QString::fromStdString(h.text);
    o.format = QString::fromStdString(h.format);
    for (const auto& p : h.polygon) o.polygon << QPointF(p.x, p.y);
    overlays.push_back(o);
    const int row = result_table_->rowCount();
    result_table_->insertRow(row);
    result_table_->setItem(row, 0, new QTableWidgetItem(QString::number(++i)));
    result_table_->setItem(row, 1, new QTableWidgetItem(o.format));
    result_table_->setItem(row, 2, new QTableWidgetItem(o.text));
    logResult(QStringLiteral("  [%1] %2 | %3").arg(i).arg(o.format, o.text.left(80)));
  }
  if (hits.empty()) logResult(QStringLiteral("  (无码)"));
  image_view_->setOverlays(overlays);

  if (updateFlowStates) {
    for (const FlowStep& s : document_.steps()) {
      if (s.operation == QLatin1String("camera_capture"))
        flow_scene_->setNodeRunState(s.id, QStringLiteral("OK"));
      else if (s.operation == QLatin1String("barcode"))
        flow_scene_->setNodeRunState(
            s.id, hits.empty() ? QStringLiteral("NG") : QStringLiteral("OK"));
      else if (s.operation == QLatin1String("var_calc"))
        flow_scene_->setNodeRunState(
            s.id, hits.empty() ? QStringLiteral("NG") : QStringLiteral("OK"));
      else
        flow_scene_->setNodeRunState(s.id, QStringLiteral("OK"));
    }
  }
  showStatus(QStringLiteral("解码完成: %1 个 / %2 ms")
                 .arg(hits.size())
                 .arg(ms, 0, 'f', 1));
  const QByteArray smoke = qgetenv("SIEANS_QT_SMOKE_REPORT");
  if (!smoke.isEmpty()) {
    QFile f(QString::fromUtf8(smoke));
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
      const QString line = QStringLiteral("codes=%1 ms=%2 w=%3 h=%4\n")
                               .arg(hits.size())
                               .arg(ms, 0, 'f', 2)
                               .arg(src.width())
                               .arg(src.height());
      f.write(line.toUtf8());
    }
  }
}


void MainWindow::onEnumerateGenTL() {
  if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("GenTL: 未链接 MvCameraControl（需 /opt/MVS）"));
    showStatus(QStringLiteral("GenTL 不可用"));
    return;
  }
  try {
    auto devices = sieans::GenTLCapture::enumerate();
    logResult(QStringLiteral("—— GenTL 枚举 %1 台 ——").arg(devices.size()));
    for (const auto& d : devices) {
      logResult(QStringLiteral("  %1 | %2 | %3")
                    .arg(QString::fromStdString(d.id),
                         QString::fromStdString(d.model),
                         QString::fromStdString(d.serial)));
    }
    if (devices.empty()) logResult(QStringLiteral("  (未发现设备)"));
    showStatus(QStringLiteral("枚举完成: %1 台").arg(devices.size()));
  } catch (const std::exception& ex) {
    logResult(QStringLiteral("枚举失败: %1").arg(QString::fromUtf8(ex.what())));
  }
}

void MainWindow::onOpenCameraManager() {
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("相机管理 / 连续采集"));
  dlg.resize(520, 420);
  auto* lay = new QVBoxLayout(&dlg);
  auto* list = new QListWidget;
  lay->addWidget(new QLabel(QStringLiteral("GenTL 设备")));
  lay->addWidget(list, 1);
  QStringList ids;
  if (sieans::GenTLCapture::available()) {
    try {
      for (const auto& d : sieans::GenTLCapture::enumerate()) {
        const QString line =
            QStringLiteral("%1 | %2 | %3")
                .arg(QString::fromStdString(d.model),
                     QString::fromStdString(d.serial),
                     QString::fromStdString(d.id));
        list->addItem(line);
        ids.push_back(QString::fromStdString(d.id));
      }
    } catch (const std::exception& ex) {
      list->addItem(QStringLiteral("枚举失败: %1").arg(QString::fromUtf8(ex.what())));
    }
  } else {
    list->addItem(QStringLiteral("(GenTL 不可用)"));
  }
  // Preselect from project
  const QString want = document_.cameraDeviceId();
  for (int i = 0; i < list->count() && i < ids.size(); ++i) {
    if (!want.isEmpty() &&
        (ids[i] == want || list->item(i)->text().contains(want) ||
         want.contains(ids[i]))) {
      list->setCurrentRow(i);
      break;
    }
  }

  auto* btns = new QHBoxLayout;
  auto* btnOpen = new QPushButton(QStringLiteral("连接并连续预览"));
  btnOpen->setObjectName(QStringLiteral("accentBtn"));
  auto* btnStop = new QPushButton(QStringLiteral("停止预览"));
  auto* btnClose = new QPushButton(QStringLiteral("断开"));
  btns->addWidget(btnOpen);
  btns->addWidget(btnStop);
  btns->addWidget(btnClose);
  lay->addLayout(btns);
  auto* box = new QDialogButtonBox(QDialogButtonBox::Close);
  lay->addWidget(box);
  connect(box, &QDialogButtonBox::rejected, &dlg, &QDialog::reject);
  connect(box, &QDialogButtonBox::clicked, &dlg, &QDialog::accept);

  connect(btnOpen, &QPushButton::clicked, &dlg, [&]() {
    const int row = list->currentRow();
    QString id = (row >= 0 && row < ids.size()) ? ids[row] : want;
    auto cam = document_.sourceConfig().value(QStringLiteral("cameraParams")).toMap();
    cam.insert(QStringLiteral("deviceId"), list->currentItem()
                                               ? list->currentItem()->text()
                                               : id);
    auto sc = document_.sourceConfig();
    sc.insert(QStringLiteral("cameraParams"), cam);
    document_.sourceConfigMut() = sc;
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
  if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("GenTL 不可用"));
    return false;
  }
  QMetaObject::invokeMethod(
      cam_worker_, "openDevice", Qt::QueuedConnection,
      Q_ARG(QString, document_.cameraDeviceId()),
      Q_ARG(double, document_.acquisitionFps()),
      Q_ARG(double, document_.exposureUs()));
  return true;
}

void MainWindow::onStartContinuousPreview() {
  if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("连续预览: GenTL 不可用"));
    return;
  }
  ensureCameraOpen();
  // Delay startPreview slightly so openDevice runs first on worker thread
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
  flow_scene_->resetRunStates();

  // Prefer latest live frame; else grab one; else current image
  QImage frame = cam_worker_ ? cam_worker_->latestFrame() : QImage();
  if (frame.isNull()) frame = image_view_->currentImage();

  if (frame.isNull() && sieans::GenTLCapture::available()) {
    // Synchronous open+grab on worker is hard while loop blocked; try invoke grabOne
    // and fall through after short wait using local GenTL on UI — avoid UI grab.
    // Fallback: load sample if nothing.
    ensureCameraOpen();
    QMetaObject::invokeMethod(cam_worker_, "grabOne", Qt::QueuedConnection);
    // Wait briefly for frame
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
  // Mark camera step
  for (const FlowStep& s : document_.steps()) {
    if (s.operation == QLatin1String("camera_capture"))
      flow_scene_->setNodeRunState(s.id, QStringLiteral("OK"));
  }
  runDecodeOnImage(frame, true);
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
  if (busy_.load()) return;  // drop tick if previous still running
  onRunOnce();
}

void MainWindow::onNodeSelected(const QString& nodeId) {
  if (nodeId.isEmpty()) {
    prop_panel_->clear();
    return;
  }
  if (nodeId == QLatin1String("source")) {
    prop_panel_->showSource(document_.sourceConfig());
    return;
  }
  if (const FlowStep* s = document_.findStep(nodeId)) {
    prop_panel_->showStep(*s);
  }
}

void MainWindow::onAddOperator(const QString& key, const QString& name) {
  FlowStep s;
  s.id = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
  s.name = name;
  s.operation = key;
  s.position = QPointF(300, 160 + document_.steps().size() * 120);
  s.runState = QStringLiteral("等待执行");
  if (key == QLatin1String("barcode")) {
    s.params = {{QStringLiteral("types"), QStringLiteral("QRCode")},
                {QStringLiteral("maxCodes"), 16},
                {QStringLiteral("showOverlay"), true}};
  }
  // Link from last step or source
  QString from = QStringLiteral("source");
  if (!document_.steps().isEmpty()) from = document_.steps().last().id;
  s.imageFrom = from;
  document_.stepsMut().push_back(s);
  FlowEdge e;
  e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  e.from = from;
  e.to = s.id;
  document_.edgesMut().push_back(e);
  applyDocumentToUi();
  logResult(QStringLiteral("已添加算子: %1").arg(name));
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
    // keep type when possible
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
          "<b>SIEANS Vision Qt</b> — GenTL→QR 工作台对等波<br/>"
          "下层 C++ <code>sieans_algo</code>，上层 Qt6 Widgets。<br/>"
          "已对齐：方案 .sieans、流程画布、算子库、属性、连续 GenTL 预览、"
          "运行/连续运行 + C++ QR 叠层。<br/>"
          "native: %1<br/>GenTL: %2")
          .arg(QString::fromStdString(sieans::native_version()))
          .arg(sieans::GenTLCapture::available() ? QStringLiteral("built")
                                                 : QStringLiteral("stub")));
}

}  // namespace sieans_qt
