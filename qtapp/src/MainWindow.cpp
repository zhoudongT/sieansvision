#include "MainWindow.hpp"
#include "Theme.hpp"
#include "ExprEval.hpp"
#include "TemplateMatch.hpp"
#include "FlowIoDialog.hpp"
#include <QInputDialog>
#include <QShortcut>
#include <QScrollBar>
#include <QLineEdit>
#include "UvcCapture.hpp"

#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>

#include <sieans/barcode.hpp>
#include <sieans/gentl_capture.hpp>

#include <QAction>
#include <QEvent>
#include <QMouseEvent>
#include <QApplication>
#include <QClipboard>
#include <QGuiApplication>
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
#include <QDoubleSpinBox>
#include <QSpinBox>
#include <QStyle>
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

QVariant coerceParam(const QString& key, const QString& value, const QVariant& old) {
  const QString trimmed = value.trimmed();
  if (trimmed.startsWith(QLatin1Char('[')) || trimmed.startsWith(QLatin1Char('{'))) {
    QJsonParseError err;
    const QJsonDocument doc = QJsonDocument::fromJson(trimmed.toUtf8(), &err);
    if (err.error == QJsonParseError::NoError && !doc.isNull()) return doc.toVariant();
  }
  if (trimmed == QLatin1String("true")) return true;
  if (trimmed == QLatin1String("false")) return false;
  if (old.typeId() == QMetaType::Bool)
    return trimmed == QLatin1String("1") || trimmed == QLatin1String("true");
  if (old.typeId() == QMetaType::Int || old.typeId() == QMetaType::LongLong)
    return trimmed.toInt();
  if (old.typeId() == QMetaType::Double) return trimmed.toDouble();
  if (key == QLatin1String("expressions")) return value;
  return value;
}

bool isExposureKey(const QString& key) {
  return key == QLatin1String("cam.exposureTime") || key == QLatin1String("exposureTime") ||
         key == QLatin1String("cam.gainDb") || key == QLatin1String("gainDb");
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
  connect(cam_worker_, &GenTLWorker::opened, this, [this](const QString&) {
    if (!preview_active_) return;
    QMetaObject::invokeMethod(cam_worker_, "startPreview", Qt::QueuedConnection);
  });
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
  if (qgetenv("SIEANS_QT_FORCE_SEED") == "1") {
    document_.seedGentlQrDemo();
    applyDocumentToUi();
    logResult(QStringLiteral("FORCE_SEED · GenTL→QR 演示流程"));
  } else if (QFileInfo::exists(proj) && document_.loadFromFile(proj, &err)) {
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
  if (qgetenv("SIEANS_QT_AUTO_SOFT") == "1") {
    QTimer::singleShot(250, this, [this]() {
      auto cam = document_.sourceConfig().value(QStringLiteral("cameraParams")).toMap();
      cam.insert(QStringLiteral("backendKind"), QStringLiteral("soft"));
      cam.insert(QStringLiteral("driver"), QStringLiteral("soft"));
      cam.insert(QStringLiteral("deviceId"), QStringLiteral("soft:0"));
      if (!cam.contains(QStringLiteral("exposureTime")))
        cam.insert(QStringLiteral("exposureTime"), 10000);
      cam.insert(QStringLiteral("gainDb"), document_.gainDb());
      auto sc = document_.sourceConfig();
      sc.insert(QStringLiteral("cameraParams"), cam);
      document_.sourceConfigMut() = sc;
      onStartContinuousPreview();
    });
  } else if (qgetenv("SIEANS_QT_AUTO_PROJECT") == "1" ||
             qgetenv("SIEANS_QT_AUTO_PREVIEW") == "1") {
    QTimer::singleShot(600, this, &MainWindow::onStartContinuousPreview);
  }
  if (qgetenv("SIEANS_QT_AUTO_MATCH") == "1") {
    QTimer::singleShot(900, this, [this]() {
      onAddOperator(QStringLiteral("locate"), QStringLiteral("快速匹配"));
      onRunOnce();
    });
  }
  if (qgetenv("SIEANS_QT_AUTO_TCP") == "1") {
    QTimer::singleShot(900, this, [this]() {
      if (!comm_hub_) return;
      QString e;
      if (comm_hub_->startTcp(&e)) {
        logResult(QStringLiteral("AUTO_TCP: %1").arg(comm_hub_->tcpStatus()));
        return;
      }
      // Port busy (live App / prior listen) — bump base+1..+4.
      QVariantMap cm = comm_hub_->commManager();
      QVariantMap tcp = cm.value(QStringLiteral("tcpReal")).toMap();
      const int base = tcp.value(QStringLiteral("port"), 19956).toInt();
      for (int d = 1; d <= 4; ++d) {
        tcp.insert(QStringLiteral("port"), base + d);
        cm.insert(QStringLiteral("tcpReal"), tcp);
        comm_hub_->loadFromCommManager(cm);
        QString e2;
        if (comm_hub_->startTcp(&e2)) {
          logResult(QStringLiteral("AUTO_TCP port bump %1: %2")
                        .arg(base + d)
                        .arg(comm_hub_->tcpStatus()));
          return;
        }
      }
      logResult(QStringLiteral("AUTO_TCP 失败: %1").arg(e));
    });
  }
  // Soft/open-and-run: grab one soft frame + full pipeline (GenTL→QR→TCP chain).
  if (qgetenv("SIEANS_QT_AUTO_RUN") == "1") {
    const int runDelay = (qgetenv("SIEANS_QT_AUTO_SOFT") == "1") ? 900 : 1400;
    QTimer::singleShot(runDelay, this, [this]() {
      logResult(QStringLiteral("AUTO_RUN · GenTL→QR open-and-run"));
      // Soft warm-up: ensure latest_ soft frame before pipeline decode.
      if (qgetenv("SIEANS_QT_AUTO_SOFT") == "1" && cam_worker_) {
        QMetaObject::invokeMethod(cam_worker_, "grabOne",
                                  Qt::BlockingQueuedConnection);
        // Extra warm-up grabs improve GenTL→QR open-and-run reliability.
        QMetaObject::invokeMethod(cam_worker_, "grabOne",
                                  Qt::BlockingQueuedConnection);
        QMetaObject::invokeMethod(cam_worker_, "grabOne",
                                  Qt::BlockingQueuedConnection);
        logResult(QStringLiteral("AUTO_RUN · soft warm-up grab×3"));
      }
      onRunOnce();
    });
  }
  const QByteArray shot = qgetenv("SIEANS_QT_SCREENSHOT");
  if (!shot.isEmpty()) {
    const int shotDelay =
        (qgetenv("SIEANS_QT_AUTO_PREVIEW") == "1" ||
         qgetenv("SIEANS_QT_AUTO_SOFT") == "1" ||
         qgetenv("SIEANS_QT_AUTO_MATCH") == "1" ||
         qgetenv("SIEANS_QT_AUTO_RUN") == "1")
            ? 3200
            : 1100;
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
    cam_worker_->requestStop();
    QMetaObject::invokeMethod(cam_worker_, "stopPreview", Qt::QueuedConnection);
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
  connect(flow_view_, &FlowView::ioRequested, this, &MainWindow::onOpenFlowIo);
  connect(flow_tabs_, &FlowTabBar::runOnceRequested, this, &MainWindow::onRunOnce);
  connect(flow_tabs_, &FlowTabBar::runContinuousRequested, this,
          &MainWindow::onRunContinuous);
  connect(flow_tabs_, &FlowTabBar::stopRequested, this, &MainWindow::onStopRun);
  connect(flow_tabs_, &FlowTabBar::pauseRequested, this, [this]() {
    if (run_paused_) onResumeRun();
    else onPauseRun();
  });
  connect(flow_tabs_, &FlowTabBar::ioRequested, this, &MainWindow::onOpenFlowIo);
  connect(flow_tabs_, &FlowTabBar::fitRequested, flow_view_, &FlowView::fitAll);
    connect(flow_tabs_, &FlowTabBar::modeToggleRequested, this, [this]() {
    if (act_mode_) act_mode_->toggle();
  });
  connect(flow_tabs_, &FlowTabBar::continuousToggleRequested, this, [this]() {
    if (continuous_run_ && !run_paused_) {
      onStopRun();
      showStatus(QStringLiteral("连续已停 · 流程条模式"));
    } else {
      onRunContinuous();
      showStatus(QStringLiteral("连续已启 · 流程条模式"));
    }
  });
  connect(flow_tabs_, &FlowTabBar::intervalChanged, this, [this](int ms) {
    document_.setRunIntervalMs(ms);
    if (host_sm_) host_sm_->setRunIntervalMs(ms);
    if (host_strip_) host_strip_->setIntervalMs(ms);
    if (continuous_run_ && !run_paused_)
      continuous_timer_.setInterval(ms > 0 ? ms : 200);
    showStatus(QStringLiteral("连续节拍 %1 ms · 流程条滚轮").arg(ms));
  });
  connect(flow_tabs_, &FlowTabBar::cycleResetRequested, this, [this]() {
    run_cycle_ = 0;
    last_cycle_ms_ = -1;
    if (host_strip_) host_strip_->setCycleTiming(-1);
    updateRunChrome();
    showStatus(QStringLiteral("周期已清零"));
  });
  horizontal->addWidget(flowPane);

  connect(flow_scene_, &FlowScene::nodeSelected, this, &MainWindow::onNodeSelected);
  connect(flow_scene_, &FlowScene::edgeConnected, this, &MainWindow::onEdgeConnected);
  connect(flow_scene_, &FlowScene::linkNotice, this, &MainWindow::onLinkNotice);
  connect(flow_scene_, &FlowScene::duplicateRequested, this, &MainWindow::onDuplicateNode);
  connect(flow_scene_, &FlowScene::renameRequested, this, [this](const QString& nodeId) {
    FlowStep* step = document_.findStep(nodeId);
    if (!step) return;
    bool ok = false;
    const QString neu = QInputDialog::getText(
        this, QStringLiteral("重命名模块"), QStringLiteral("显示名称"),
        QLineEdit::Normal, step->name, &ok);
    if (!ok) return;
    const QString name = neu.trimmed();
    if (name.isEmpty() || name == step->name) return;
    step->name = name;
    if (flow_scene_) flow_scene_->setNodeLabel(nodeId, name);
    if (prop_float_ && prop_float_->isVisible())
      prop_float_->setNodeTitle(name, step->operation);
    showStatus(QStringLiteral("已重命名 · %1").arg(name));
    logResult(QStringLiteral("重命名模块 %1 → %2").arg(nodeId, name));
  });

  // Property float (VM light panel) — created lazily-ish but keep ready
  prop_float_ = new PropertyFloat(this);
  prop_panel_ = prop_float_->panel();
  connect(prop_float_, &PropertyFloat::paramEdited, this, &MainWindow::onParamEdited);
  connect(prop_float_, &PropertyFloat::runModule, this, &MainWindow::onRunOnce);
  connect(prop_float_, &PropertyFloat::runModuleContinuous, this,
          &MainWindow::onRunContinuous);
  connect(prop_float_, &PropertyFloat::chromeGeometryChanged, this,
          [this](const QRect& g) { document_.setPropertyFloatGeometry(g); });
  connect(prop_float_, &PropertyFloat::paramsReverted, this,
          &MainWindow::onParamsReverted);

  // —— Right: image tabs + host strip + filmstrip ——
  auto* imagePane = new QWidget;
  imagePane->setObjectName(QStringLiteral("imagePane"));
  auto* imgLay = new QVBoxLayout(imagePane);
  imgLay->setContentsMargins(0, 0, 0, 0);
  imgLay->setSpacing(0);
  image_tabs_ = new QTabWidget;
  image_view_ = new ImageView;
  output_view_ = new ImageView;
  connect(image_view_, &ImageView::imagePasted, this, [this](const QImage& img) {
    if (img.isNull()) return;
    const QString dir = QDir::temp().filePath(QStringLiteral("sieans_paste"));
    QDir().mkpath(dir);
    const QString path = QDir(dir).filePath(
        QStringLiteral("paste_%1.png")
            .arg(QDateTime::currentDateTime().toString(QStringLiteral("yyyyMMdd_hhmmss_zzz"))));
    if (!img.save(path, "PNG")) {
      showStatus(QStringLiteral("粘贴图像保存失败"));
      return;
    }
    loadImagePath(path, true);
    showStatus(QStringLiteral("已粘贴图像 %1×%2 → 胶片").arg(img.width()).arg(img.height()));
  });
  auto saveViewToFilmstrip = [this](const QImage& img) {
    if (img.isNull()) return;
    const QString dir = QDir::temp().filePath(QStringLiteral("sieans_snap"));
    QDir().mkpath(dir);
    const QString path = QDir(dir).filePath(
        QStringLiteral("snap_%1.png")
            .arg(QDateTime::currentDateTime().toString(QStringLiteral("yyyyMMdd_hhmmss_zzz"))));
    if (!img.save(path, "PNG")) {
      showStatus(QStringLiteral("存胶片失败"));
      return;
    }
    loadImagePath(path, true);
    showStatus(QStringLiteral("已存胶片 %1×%2").arg(img.width()).arg(img.height()));
  };
  connect(image_view_, &ImageView::imageSaveToFilmstripRequested, this, saveViewToFilmstrip);
  connect(output_view_, &ImageView::imageSaveToFilmstripRequested, this, saveViewToFilmstrip);
  image_tabs_->addTab(image_view_, QStringLiteral("全局图像"));
  image_tabs_->addTab(output_view_, QStringLiteral("模块结果"));
  imgLay->addWidget(image_tabs_, 1);
  host_strip_ = new HostStrip;
  imgLay->addWidget(host_strip_);
  connect(host_strip_, &HostStrip::modeToggleRequested, this, [this]() {
    if (act_mode_) act_mode_->toggle();
  });
  connect(host_strip_, &HostStrip::cycleResetRequested, this, [this]() {
    run_cycle_ = 0;
    last_cycle_ms_ = -1;
    if (host_strip_) host_strip_->setCycleTiming(-1);
    updateRunChrome();
    showStatus(QStringLiteral("周期已清零"));
  });
  connect(host_strip_, &HostStrip::continuousToggleRequested, this, [this]() {
    if (continuous_run_ && !run_paused_) {
      onStopRun();
      showStatus(QStringLiteral("连续已停 · Host 右键"));
    } else {
      onRunContinuous();
      showStatus(QStringLiteral("连续已启 · Host 右键"));
    }
  });
  connect(host_strip_, &HostStrip::intervalChanged, this, [this](int ms) {
    document_.setRunIntervalMs(ms);
    if (host_sm_) host_sm_->setRunIntervalMs(ms);
    if (flow_tabs_) flow_tabs_->setIntervalMs(ms);
    if (continuous_run_ && !run_paused_)
      continuous_timer_.setInterval(ms > 0 ? ms : 200);
    showStatus(QStringLiteral("连续节拍 %1 ms · Host条滚轮").arg(ms));
  });
  connect(host_strip_, &HostStrip::watchKeysChanged, this, [this](const QStringList& keys) {
    if (host_strip_) host_strip_->setWatchKeys(keys);
    document_.setHostWatchKeys(keys);
    if (var_watch_) var_watch_->setWatchKeys(keys);
    showStatus(QStringLiteral("监视键 %1").arg(keys.join(QLatin1Char(','))));
    logResult(QStringLiteral("Host 监视键 → %1").arg(keys.join(QLatin1Char(','))));
  });
  connect(host_strip_, &HostStrip::openHostRequested, this, [this]() {
    if (host_sm_) {
      if (bottom_tabs_) bottom_tabs_->setCurrentWidget(host_sm_);
      host_sm_->setFocus(Qt::OtherFocusReason);
      host_sm_->raise();
      showStatus(QStringLiteral("Host 面板"));
    }
  });
    connect(host_strip_, &HostStrip::runOnceRequested, this, [this]() {
    onRunOnce();
  });
  connect(host_strip_, &HostStrip::runContinuousRequested, this, [this]() {
    onRunContinuous();
  });
  connect(host_strip_, &HostStrip::pauseRequested, this, [this]() {
    if (continuous_run_ && !run_paused_) {
      onPauseRun();
      showStatus(QStringLiteral("已暂停 · Host Alt+模式"));
    } else if (run_paused_) {
      onResumeRun();
      showStatus(QStringLiteral("已继续 · Host Alt+模式"));
    } else {
      showStatus(QStringLiteral("无连续可暂停 · Host Alt+模式"));
    }
  });
  if (comm_hub_) {
    connect(comm_hub_, &CommHub::statusChanged, host_strip_,
            [this](const QString& s) {
              if (host_strip_) host_strip_->setTcpStatus(s);
            });
    if (!comm_hub_->tcpStatus().isEmpty())
      host_strip_->setTcpStatus(comm_hub_->tcpStatus());
  }
  filmstrip_ = new FilmstripBar;
  imgLay->addWidget(filmstrip_);
  connect(filmstrip_, &FilmstripBar::addImagesRequested, this, [this]() {
    const QString path = QFileDialog::getOpenFileName(
        this, QStringLiteral("添加图像"),
        QStringLiteral("/home/allen/文档/sieansvision/artifacts"),
        QStringLiteral("图像文件 (*.bmp *.jpeg *.jpg *.png *.tif *.tiff)"));
    if (!path.isEmpty() && filmstrip_) filmstrip_->addPaths({path});
  });
  connect(filmstrip_, &FilmstripBar::addFolderRequested, this, [this]() {
    const QString dir = QFileDialog::getExistingDirectory(
        this, QStringLiteral("添加图像文件夹"),
        QStringLiteral("/home/allen/文档/sieansvision/artifacts"));
    if (dir.isEmpty() || !filmstrip_) return;
    QDir folder(dir);
    const QStringList names = folder.entryList(
        {QStringLiteral("*.bmp"), QStringLiteral("*.jpeg"), QStringLiteral("*.jpg"),
         QStringLiteral("*.png"), QStringLiteral("*.tif"), QStringLiteral("*.tiff")},
        QDir::Files, QDir::Name);
    QStringList paths;
    for (const QString& name : names) paths << folder.absoluteFilePath(name);
    const int before = filmstrip_->count();
    filmstrip_->addPaths(paths);
    logResult(QStringLiteral("文件夹导入 %1 张（跳过非图像）")
                  .arg(filmstrip_->count() - before));
  });
  connect(filmstrip_, &FilmstripBar::imageSelected, this,
          [this](const QString& path) {
            loadImagePath(path, false);
            if (filmstrip_) document_.setFilmstripIndex(filmstrip_->index());
          });
  connect(filmstrip_, &FilmstripBar::runAllRequested, this, &MainWindow::onRunAllImages);
  connect(filmstrip_, &FilmstripBar::pathsChanged, this, [this]() {
    if (!filmstrip_) return;
    document_.setFilmstripPaths(filmstrip_->paths());
    document_.setFilmstripIndex(filmstrip_->index());
  });
  connect(filmstrip_, &FilmstripBar::autoSwitchChanged, this, [this](bool on) {
    document_.setFilmstripAutoSwitch(on);
  });
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
  result_table_->setToolTip(QStringLiteral("当前结果 · Ctrl+C 选中 · Ctrl+Shift+C 可见全部 · Ctrl+Shift+J JSON · Home/End/Pg · 过滤 Ctrl+Shift+F"));
  result_table_->setStatusTip(QStringLiteral("结果表 · Ctrl+C/Ctrl+Shift+C/J · Home/End/Pg · 过滤 Ctrl+Shift+F"));
  auto* resultHost = new QWidget;
  auto* resultLay = new QVBoxLayout(resultHost);
  resultLay->setContentsMargins(0, 0, 0, 0);
  resultLay->setSpacing(2);
  resultFilter_ = new QLineEdit;
  resultFilter_->setObjectName(QStringLiteral("resultFilter"));
  resultFilter_->setPlaceholderText(QStringLiteral("过滤结果 · Ctrl+Shift+F · Esc 清空"));
  resultFilter_->setClearButtonEnabled(true);
  resultFilter_->setToolTip(QStringLiteral("当前结果过滤 · 匹配模块/值/类型"));
  resultLay->addWidget(resultFilter_);
  resultLay->addWidget(result_table_, 1);
  connect(resultFilter_, &QLineEdit::textChanged, this, [this](const QString& s) {
    if (!result_table_) return;
    const QString f = s.trimmed();
    for (int r = 0; r < result_table_->rowCount(); ++r) {
      QString hay;
      for (int c = 0; c < result_table_->columnCount(); ++c) {
        if (auto* it = result_table_->item(r, c)) hay += it->text() + QLatin1Char(' ');
      }
      result_table_->setRowHidden(r, !f.isEmpty() && !hay.contains(f, Qt::CaseInsensitive));
    }
  });
  {
    auto* sc = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+F")), this);
    connect(sc, &QShortcut::activated, this, [this]() {
      if (!resultFilter_) return;
      if (auto* tabs = resultFilter_->parentWidget()
                           ? resultFilter_->parentWidget()->parentWidget()
                           : nullptr) {
        if (auto* tw = qobject_cast<QTabWidget*>(tabs)) tw->setCurrentWidget(resultFilter_->parentWidget());
      }
      resultFilter_->setFocus(Qt::ShortcutFocusReason);
      resultFilter_->selectAll();
    });
    auto* scEsc = new QShortcut(QKeySequence(Qt::Key_Escape), resultFilter_);
    connect(scEsc, &QShortcut::activated, this, [this]() {
      if (resultFilter_ && !resultFilter_->text().isEmpty()) resultFilter_->clear();
    });
  }
  bottom->addTab(resultHost, QStringLiteral("当前结果"));


  {
    auto* scCopy = new QShortcut(QKeySequence(QStringLiteral("Ctrl+C")), result_table_);
    connect(scCopy, &QShortcut::activated, this, [this]() {
      if (!result_table_) return;
      QStringList lines;
      const auto ranges = result_table_->selectedRanges();
      QSet<int> rows;
      for (const auto& rg : ranges)
        for (int r = rg.topRow(); r <= rg.bottomRow(); ++r) rows.insert(r);
      if (rows.isEmpty() && result_table_->currentRow() >= 0)
        rows.insert(result_table_->currentRow());
      QList<int> sorted = rows.values();
      std::sort(sorted.begin(), sorted.end());
      for (int r : sorted) {
        if (result_table_->isRowHidden(r)) continue;
        QStringList cols;
        for (int c = 0; c < result_table_->columnCount(); ++c) {
          auto* it = result_table_->item(r, c);
          cols << (it ? it->text() : QString());
        }
        lines << cols.join(QLatin1Char('\t'));
      }
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
      if (resultFilter_)
        resultFilter_->setToolTip(QStringLiteral("已复制结果 %1 行 · Ctrl+C").arg(lines.size()));
    });
    auto* scAll = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), result_table_);
    connect(scAll, &QShortcut::activated, this, [this]() {
      if (!result_table_) return;
      QStringList lines;
      for (int r = 0; r < result_table_->rowCount(); ++r) {
        if (result_table_->isRowHidden(r)) continue;
        QStringList cols;
        for (int c = 0; c < result_table_->columnCount(); ++c) {
          auto* it = result_table_->item(r, c);
          cols << (it ? it->text() : QString());
        }
        lines << cols.join(QLatin1Char('\t'));
      }
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
      if (resultFilter_)
        resultFilter_->setToolTip(QStringLiteral("已复制可见结果 %1 · Ctrl+Shift+C").arg(lines.size()));
    });
    auto* scJson = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+J")), result_table_);
    connect(scJson, &QShortcut::activated, this, [this]() {
      if (!result_table_) return;
      QJsonArray rows;
      for (int r = 0; r < result_table_->rowCount(); ++r) {
        if (result_table_->isRowHidden(r)) continue;
        QJsonObject o;
        auto* a = result_table_->item(r, 0);
        auto* b = result_table_->item(r, 1);
        auto* c = result_table_->item(r, 2);
        o.insert(QStringLiteral("module"), a ? a->text() : QString());
        o.insert(QStringLiteral("value"), b ? b->text() : QString());
        o.insert(QStringLiteral("type"), c ? c->text() : QString());
        rows.append(o);
      }
      const QByteArray bytes = QJsonDocument(rows).toJson(QJsonDocument::Compact);
      if (auto* clip = QGuiApplication::clipboard())
        clip->setText(QString::fromUtf8(bytes));
      if (resultFilter_)
        resultFilter_->setToolTip(QStringLiteral("已复制结果JSON %1 · Ctrl+Shift+J").arg(rows.size()));
    });
    auto jumpResult = [this](int mode) {
      if (!result_table_) return;
      QList<int> vis;
      for (int r = 0; r < result_table_->rowCount(); ++r)
        if (!result_table_->isRowHidden(r)) vis << r;
      if (vis.isEmpty()) return;
      int cur = result_table_->currentRow();
      int idx = 0;
      for (int i = 0; i < vis.size(); ++i) {
        if (vis[i] == cur) { idx = i; break; }
        if (vis[i] < cur) idx = i;
      }
      if (mode == 0) idx = 0;
      else if (mode == 1) idx = vis.size() - 1;
      else if (mode == 2) idx = qMax(0, idx - 5);
      else idx = qMin(vis.size() - 1, idx + 5);
      result_table_->setCurrentCell(vis[idx], 0);
      if (auto* it = result_table_->item(vis[idx], 0)) result_table_->scrollToItem(it);
    };
    auto* scHome = new QShortcut(QKeySequence(Qt::Key_Home), result_table_);
    connect(scHome, &QShortcut::activated, this, [jumpResult]() { jumpResult(0); });
    auto* scEnd = new QShortcut(QKeySequence(Qt::Key_End), result_table_);
    connect(scEnd, &QShortcut::activated, this, [jumpResult]() { jumpResult(1); });
    auto* scPu = new QShortcut(QKeySequence(Qt::Key_PageUp), result_table_);
    connect(scPu, &QShortcut::activated, this, [jumpResult]() { jumpResult(2); });
    auto* scPd = new QShortcut(QKeySequence(Qt::Key_PageDown), result_table_);
    connect(scPd, &QShortcut::activated, this, [jumpResult]() { jumpResult(3); });
  }
  result_log_ = new QPlainTextEdit;
  result_log_->setReadOnly(true);
  result_log_->setPlaceholderText(
      QStringLiteral("历史结果 / 运行日志 / GenTL / 解码 / Comm"));
  auto* logHost = new QWidget;
  auto* logLay = new QVBoxLayout(logHost);
  logLay->setContentsMargins(0, 0, 0, 0);
  logLay->setSpacing(2);
  resultLogFilter_ = new QLineEdit;
  resultLogFilter_->setObjectName(QStringLiteral("resultLogFilter"));
  resultLogFilter_->setPlaceholderText(QStringLiteral("过滤历史 · Ctrl+Alt+F · Esc 清空"));
  resultLogFilter_->setClearButtonEnabled(true);
  resultLogFilter_->setToolTip(QStringLiteral("历史结果过滤 · 匹配时间戳/正文"));
  logLay->addWidget(resultLogFilter_);
  logLay->addWidget(result_log_, 1);
  connect(resultLogFilter_, &QLineEdit::textChanged, this, [this](const QString&) {
    if (!result_log_) return;
    const QString f = resultLogFilter_ ? resultLogFilter_->text().trimmed() : QString();
    QStringList lines;
    if (f.isEmpty()) lines = resultLogAll_;
    else {
      for (const QString& line : resultLogAll_) {
        if (line.contains(f, Qt::CaseInsensitive)) lines << line;
      }
    }
    result_log_->setPlainText(lines.join(QLatin1Char('\n')));
    auto* bar = result_log_->verticalScrollBar();
    if (bar) bar->setValue(bar->maximum());
  });
  {
    auto* sc = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Alt+F")), this);
    connect(sc, &QShortcut::activated, this, [this]() {
      if (!resultLogFilter_) return;
      if (auto* parent = resultLogFilter_->parentWidget()) {
        if (auto* tw = qobject_cast<QTabWidget*>(parent->parentWidget()))
          tw->setCurrentWidget(parent);
      }
      resultLogFilter_->setFocus(Qt::ShortcutFocusReason);
      resultLogFilter_->selectAll();
    });
    auto* scEsc = new QShortcut(QKeySequence(Qt::Key_Escape), resultLogFilter_);
    connect(scEsc, &QShortcut::activated, this, [this]() {
      if (resultLogFilter_ && !resultLogFilter_->text().isEmpty()) resultLogFilter_->clear();
    });
    auto* scCopyLog = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), result_log_);
    connect(scCopyLog, &QShortcut::activated, this, [this]() {
      if (!result_log_) return;
      const QString text = result_log_->toPlainText();
      if (auto* clip = QGuiApplication::clipboard()) clip->setText(text);
      if (resultLogFilter_)
        resultLogFilter_->setToolTip(QStringLiteral("已复制历史 %1 字 · Ctrl+Shift+C").arg(text.size()));
    });
    {
      auto* scLogJson = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+J")), result_log_);
      connect(scLogJson, &QShortcut::activated, this, [this]() {
        if (!result_log_) return;
        const QString text = result_log_->toPlainText();
        QStringList lines = text.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
        QJsonArray arr;
        for (const QString& line : lines) arr.append(line);
        if (auto* clip = QGuiApplication::clipboard())
          clip->setText(QString::fromUtf8(QJsonDocument(arr).toJson(QJsonDocument::Compact)));
        result_log_->setToolTip(QStringLiteral("已复制历史JSON %1 · Ctrl+Shift+J").arg(arr.size()));
      });
    }
    result_log_->setToolTip(QStringLiteral("历史结果 · Ctrl+Shift+C 复制 · Ctrl+Shift+J JSON · Ctrl+Alt+F 过滤"));
  }
  bottom->addTab(logHost, QStringLiteral("历史结果"));

  auto* helpPad = new QPlainTextEdit;
  helpPad->setReadOnly(true);
  helpPad->setPlainText(
      QStringLiteral("帮助：胶片条可添加图像/文件夹，运行全部，自动切换。"
                     "工具栏「运行模式」锁定画布。快速匹配首次执行会从当前图建模板。\n"
                     "底栏「上位机」：开始 / 暂停 / 继续 / 停止 / 报警历史。"
                     "状态栏显示流程 / 工具 / 算法耗时。"));
  bottom->addTab(helpPad, QStringLiteral("帮助"));

  var_watch_ = new VarWatchPanel;
  bottom->addTab(var_watch_, QStringLiteral("变量监视"));
  connect(var_watch_, &VarWatchPanel::hostWatchToggleRequested, this, [this](const QString& key) {
    if (key.isEmpty()) return;
    QStringList keys = document_.hostWatchKeys();
    if (keys.contains(key)) keys.removeAll(key);
    else keys << key;
    document_.setHostWatchKeys(keys);
    if (host_strip_) {
      host_strip_->setWatchKeys(keys);
      host_strip_->updateFromVars(flow_vars_);
    }
    if (var_watch_) var_watch_->setWatchKeys(keys);
    showStatus(QStringLiteral("Host 监视 %1 %2")
                   .arg(keys.contains(key) ? QStringLiteral("＋") : QStringLiteral("－"), key));
  });
  connect(var_watch_, &VarWatchPanel::watchListChanged, this, [this](const QStringList& keys) {
    document_.setVarWatchKeys(keys);
    showStatus(QStringLiteral("变量监视列表 %1 项").arg(keys.size()));
  });
  comm_panel_ = new CommPanel(comm_hub_);
  connect(comm_panel_, &CommPanel::requestSaveComm, this,
          [this](const QVariantMap& cm) { document_.setCommManager(cm); });
  bottom->addTab(comm_panel_, QStringLiteral("通信"));
  host_sm_ = new HostStatePanel;
  bottom->addTab(host_sm_, QStringLiteral("上位机"));
  connect(host_sm_, &HostStatePanel::startRequested, this, &MainWindow::onRunContinuous);
  connect(host_sm_, &HostStatePanel::pauseRequested, this, &MainWindow::onPauseRun);
  connect(host_sm_, &HostStatePanel::resumeRequested, this, &MainWindow::onResumeRun);
  connect(host_sm_, &HostStatePanel::stopRequested, this, &MainWindow::onStopRun);
  connect(host_sm_, &HostStatePanel::intervalChanged, this, [this](int ms) {
    document_.setRunIntervalMs(ms);
    if (host_strip_) host_strip_->setIntervalMs(ms);
    if (flow_tabs_) flow_tabs_->setIntervalMs(ms);
    if (continuous_run_ && !run_paused_) {
      continuous_timer_.setInterval(ms > 0 ? ms : 200);
    }
    showStatus(QStringLiteral("连续间隔 %1 ms").arg(ms > 0 ? ms : 200));
  });
  connect(host_sm_, &HostStatePanel::hostModeChanged, this, [this](const QString& mode) {
    document_.setHostMode(mode);
  });
  connect(host_sm_, &HostStatePanel::alarmPolicyChanged, this, [this](const QString& pol) {
    document_.setAlarmPolicy(pol);
  });
  connect(host_sm_, &HostStatePanel::alarmHistoryChanged, this, [this](const QStringList& lines) {
    document_.setAlarmHistory(lines);
  });
  connect(host_sm_, &HostStatePanel::clearAlarmRequested, this, [this]() {
    if (host_strip_) host_strip_->setAlarm(false);
    if (!host_sm_) return;
    if (continuous_run_ && !run_paused_)
      host_sm_->applyState(QStringLiteral("Running"));
    else if (run_paused_)
      host_sm_->applyState(QStringLiteral("Paused"));
  });
  bottom_tabs_ = bottom;

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
  status_config_ = new QLabel(QStringLiteral("组件配置完成"));
  status_config_->setStyleSheet(QStringLiteral("color:#3ecf8e;"));
  statusBar()->addPermanentWidget(status_config_);
  status_timing_ = new QLabel(QStringLiteral("流程 — ms · 工具 — ms · 算法 — ms"));
  statusBar()->addPermanentWidget(status_timing_);
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
  settings->addAction(QStringLiteral("流程 I/O 绑定…"), this, &MainWindow::onOpenFlowIo);

  auto* tools = menuBar()->addMenu(QStringLiteral("工具"));
  tools->addAction(QStringLiteral("C++ QR 解码"), this, &MainWindow::onDecodeQr,
                   QKeySequence(Qt::Key_F9));
  tools->addAction(QStringLiteral("适应图像窗口"), image_view_, &ImageView::fitToView);
  tools->addAction(QStringLiteral("适应流程画布"), flow_view_, &FlowView::fitAll);
  tools->addAction(QStringLiteral("流程 I/O 绑定…"), this, &MainWindow::onOpenFlowIo);

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
    if (bottom_tabs_ && var_watch_) {
      bottom_tabs_->setCurrentWidget(var_watch_);
      showStatus(QStringLiteral("变量监视"));
    }
  });

  auto* devices = menuBar()->addMenu(QStringLiteral("设备与模型"));
  devices->addAction(QStringLiteral("相机管理…"), this, &MainWindow::onOpenCameraManager);
  devices->addAction(QStringLiteral("枚举 GenTL"), this, &MainWindow::onEnumerateGenTL);
  devices->addAction(QStringLiteral("连续采集预览"), this,
                     &MainWindow::onStartContinuousPreview);
  devices->addAction(QStringLiteral("停止预览"), this, &MainWindow::onStopContinuousPreview);
  devices->addAction(QStringLiteral("通信管理…"), this, &MainWindow::onOpenCommManager);
  devices->addAction(QStringLiteral("上位机控制…"), this, [this]() {
    if (bottom_tabs_ && host_sm_)
      bottom_tabs_->setCurrentWidget(host_sm_);
  });

  auto* records = menuBar()->addMenu(QStringLiteral("记录与账号"));
  records->addAction(QStringLiteral("当前结果…"), this, [this]() {
    if (bottom_tabs_ && result_table_) {
      for (int i = 0; i < bottom_tabs_->count(); ++i) {
        QWidget* w = bottom_tabs_->widget(i);
        if (w && (w == result_table_->parentWidget() || w->isAncestorOf(result_table_))) {
          bottom_tabs_->setCurrentIndex(i);
          result_table_->setFocus(Qt::OtherFocusReason);
          break;
        }
      }
      showStatus(QStringLiteral("当前结果"));
    }
  });
    records->addAction(QStringLiteral("运行日志…"), this, [this]() {
    if (bottom_tabs_ && result_log_) {
      for (int i = 0; i < bottom_tabs_->count(); ++i) {
        QWidget* w = bottom_tabs_->widget(i);
        if (w && (w == result_log_->parentWidget() || w->isAncestorOf(result_log_))) {
          bottom_tabs_->setCurrentIndex(i);
          result_log_->setFocus(Qt::OtherFocusReason);
          break;
        }
      }
      showStatus(QStringLiteral("历史结果"));
    }
  });
  records->addAction(QStringLiteral("变量监视…"), this, [this]() {
    if (bottom_tabs_ && var_watch_) {
      bottom_tabs_->setCurrentWidget(var_watch_);
      showStatus(QStringLiteral("变量监视"));
    }
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
  tb->addAction(QStringLiteral("通信"), this, [this]() {
    if (bottom_tabs_ && comm_panel_) {
      bottom_tabs_->setCurrentWidget(comm_panel_);
      comm_panel_->bindDocument(document_.commManager());
      comm_panel_->setFlowVars(flow_vars_);
      showStatus(QStringLiteral("通信面板"));
    } else {
      onOpenCommManager();
    }
  });
  {
    auto* a = tb->addAction(QStringLiteral("I/O"), this, &MainWindow::onOpenFlowIo);
    a->setShortcut(QKeySequence(QStringLiteral("Ctrl+I")));
    a->setToolTip(QStringLiteral("流程 I/O 绑定 · Ctrl+I · emptyDefault/{name}/${flow.x}"));
  }
  act_preview_ = tb->addAction(QStringLiteral("连续预览"), this,
                               &MainWindow::onStartContinuousPreview);
  act_preview_->setToolTip(QStringLiteral("连续采集预览 · Soft/UVC/GenTL · 不跑流程"));
  act_preview_->setStatusTip(QStringLiteral("预览 · 连续采集"));
  act_preview_stop_ =
      tb->addAction(QStringLiteral("停预览"), this, &MainWindow::onStopContinuousPreview);
  act_preview_stop_->setToolTip(QStringLiteral("停止连续采集预览 · 不影响流程运行态"));
  act_preview_stop_->setStatusTip(QStringLiteral("预览 · 停止"));
  tb->addSeparator();
  act_run_ = tb->addAction(QStringLiteral("▶ 运行"), this, &MainWindow::onRunOnce);
  act_run_->setShortcut(QKeySequence(Qt::Key_F5));
  act_run_->setToolTip(QStringLiteral("运行当前流程一次 · F5 · F9 同效"));
  act_run_->setStatusTip(QStringLiteral("运行 · F5"));
  act_cont_ =
      tb->addAction(QStringLiteral("↻ 连续"), this, &MainWindow::onRunContinuous);
  act_cont_->setShortcut(QKeySequence(Qt::Key_F6));
  act_cont_->setToolTip(QStringLiteral("连续运行当前流程 · F6 · Esc 停止 · F7 暂停/继续"));
  act_cont_->setStatusTip(QStringLiteral("连续 · F6"));
  act_pause_ = tb->addAction(QStringLiteral("⏸ 暂停"));
  act_pause_->setShortcut(QKeySequence(Qt::Key_F7));
  act_pause_->setToolTip(QStringLiteral("暂停/继续连续运行 · F7 · 仅连续态有效"));
  act_pause_->setStatusTip(QStringLiteral("暂停 · F7"));
  connect(act_pause_, &QAction::triggered, this, [this]() {
    if (run_paused_) onResumeRun();
    else onPauseRun();
  });
  act_stop_ = tb->addAction(QStringLiteral("■ 停止"), this, &MainWindow::onStopRun);
  act_stop_->setShortcut(QKeySequence(Qt::Key_Escape));
  act_stop_->setToolTip(QStringLiteral("停止运行 / 连续 · Esc · 预览中亦停采集"));
  act_stop_->setStatusTip(QStringLiteral("停止 · Esc"));
  tb->addSeparator();
  act_mode_ = tb->addAction(QStringLiteral("运行模式"));
  act_mode_->setCheckable(true);
  act_mode_->setShortcut(QKeySequence(Qt::Key_F8));
  act_mode_->setToolTip(QStringLiteral("设计态可编辑画布；运行态锁定拖拽、连线和删除 · F8 切换 · F5/F9 仍可运行"));
  connect(act_mode_, &QAction::toggled, this, &MainWindow::onToggleRunMode);
  tb->addSeparator();
  tb->addAction(QStringLiteral("示例 QR"), this, &MainWindow::onLoadSample);
  tb->addAction(QStringLiteral("解码"), this, &MainWindow::onDecodeQr);
  tb->addSeparator();
  mode_badge_ = new QLabel(QStringLiteral("设计态"));
  mode_badge_->setObjectName(QStringLiteral("modeBadge"));
  mode_badge_->setToolTip(QStringLiteral("设计态可编辑 · 运行态锁定画布 · 单击/F8 切换 · Alt暂停/继续 · 中键运行一次 · 右键连续/暂停 · 双击停连续"));
  mode_badge_->setStatusTip(QStringLiteral("模式徽章 · 设计/运行 · Alt暂停 · 中键一次 · 右键连续 · 双击停"));
  mode_badge_->setProperty("runMode", false);
  mode_badge_->setCursor(Qt::PointingHandCursor);
  mode_badge_->installEventFilter(this);
  tb->addWidget(mode_badge_);
  listen_badge_ = new QLabel(QStringLiteral("监听·—"));
  listen_badge_->setObjectName(QStringLiteral("commListenBadge"));
  listen_badge_->setToolTip(QStringLiteral("通信状态 · 单击底栏通信 · 中键/右键通信管理对话框"));
  listen_badge_->setStatusTip(QStringLiteral("通信徽章 · 单击底栏通信 · 中键/右键通信管理对话框 · tcp=/listen/reconnect"));
  listen_badge_->setCursor(Qt::PointingHandCursor);
  listen_badge_->setStyleSheet(
      QStringLiteral("padding:2px 8px;border-radius:3px;background:#3a3d42;color:#a8a8a8;"));
  tb->addWidget(listen_badge_);
  listen_badge_->installEventFilter(this);
  if (comm_hub_) {
    connect(comm_hub_, &CommHub::statusChanged, this, [this](const QString& s) {
      if (!listen_badge_) return;
      listen_badge_->setText(QStringLiteral("通信·%1").arg(s.left(40)));
      statusBar()->showMessage(QStringLiteral("通信 %1").arg(s), 2500);
      if (s.contains(QStringLiteral("listen")) || s.contains(QStringLiteral("connected")) ||
          s.contains(QStringLiteral("peers")))
        listen_badge_->setStyleSheet(
            QStringLiteral("padding:2px 8px;border-radius:3px;background:#1e3d2f;color:#3ecf8e;font-weight:600;"));
      else if (s.contains(QStringLiteral("fail")) || s.contains(QStringLiteral("error")) ||
               s.contains(QStringLiteral("disconnected")))
        listen_badge_->setStyleSheet(
            QStringLiteral("padding:2px 8px;border-radius:3px;background:#3a1c1c;color:#e35d6a;font-weight:600;"));
      else if (s.contains(QStringLiteral("reconnect")) || s.contains(QStringLiteral("connecting")))
        listen_badge_->setStyleSheet(
            QStringLiteral("padding:2px 8px;border-radius:3px;background:#3a3420;color:#e0b84a;font-weight:600;"));
      else
        listen_badge_->setStyleSheet(
            QStringLiteral("padding:2px 8px;border-radius:3px;background:#3a3d42;color:#a8a8a8;"));
    });
  }
}

void MainWindow::applyDocumentToUi() {
  flow_scene_->loadDocument(&document_);
  if (run_mode_) flow_scene_->setEditingLocked(true);
  project_label_->setText(QStringLiteral("方案: %1").arg(document_.name()));
  setWindowTitle(QStringLiteral("%1 — SIEANS Vision · 设计态").arg(document_.name()));
  if (flow_tabs_) flow_tabs_->setFlowName(QStringLiteral("流程1"));
  QTimer::singleShot(0, flow_view_, &FlowView::fitAll);
  if (prop_float_) prop_float_->hide();
  else if (prop_panel_) prop_panel_->clear();
  flow_vars_ = document_.variables();
  if (var_watch_) {
    var_watch_->setWatchKeys(document_.hostWatchKeys());
    {
      const QStringList vwk = document_.varWatchKeys();
      if (!vwk.isEmpty()) var_watch_->setKeyList(vwk);
    }
    var_watch_->setVariables(flow_vars_);
  }
  if (host_strip_) host_strip_->setWatchKeys(document_.hostWatchKeys());
  {
    const int iv = document_.runIntervalMs() > 0 ? document_.runIntervalMs() : 200;
    if (host_sm_) host_sm_->setRunIntervalMs(iv);
    if (host_strip_) host_strip_->setIntervalMs(iv);
    if (flow_tabs_) flow_tabs_->setIntervalMs(iv);
    if (host_sm_) {
      host_sm_->setHostMode(document_.hostMode());
      host_sm_->setAlarmPolicy(document_.alarmPolicy());
      const QStringList ah = document_.alarmHistory();
      if (!ah.isEmpty()) host_sm_->setAlarmHistoryLines(ah);
    }
  }
  if (filmstrip_) {
    const QStringList fps = document_.filmstripPaths();
    if (!fps.isEmpty()) filmstrip_->setPaths(fps);
    filmstrip_->setAutoSwitch(document_.filmstripAutoSwitch());
    const int fidx = document_.filmstripIndex();
    if (fidx >= 0 && fidx < filmstrip_->count())
      filmstrip_->setCurrentIndex(fidx, true);
  }
  if (comm_panel_) comm_panel_->bindDocument(document_.commManager());
  if (comm_hub_) {
    comm_hub_->loadFromCommManager(document_.commManager());
    const QVariantMap tcp = document_.commManager().value(QStringLiteral("tcpReal")).toMap();
    if (tcp.value(QStringLiteral("autoStart")).toBool() && !comm_hub_->tcpActive()) {
      QString e;
      if (comm_hub_->startTcp(&e)) {
        logResult(QStringLiteral("TCP autoStart: %1").arg(comm_hub_->tcpStatus()));
      } else {
        QVariantMap cm = document_.commManager();
        QVariantMap tcp2 = cm.value(QStringLiteral("tcpReal")).toMap();
        const int base = tcp2.value(QStringLiteral("port"), 19956).toInt();
        bool ok = false;
        for (int d = 1; d <= 4 && !ok; ++d) {
          tcp2.insert(QStringLiteral("port"), base + d);
          cm.insert(QStringLiteral("tcpReal"), tcp2);
          comm_hub_->loadFromCommManager(cm);
          QString e2;
          ok = comm_hub_->startTcp(&e2);
          if (ok)
            logResult(QStringLiteral("TCP autoStart port bump %1: %2")
                          .arg(base + d)
                          .arg(comm_hub_->tcpStatus()));
        }
        if (!ok && !e.isEmpty())
          logResult(QStringLiteral("TCP autoStart 失败: %1").arg(e));
      }
    }
  }
  if (host_strip_) host_strip_->updateFromVars(flow_vars_);
  if (host_sm_) host_sm_->bindFlow(document_.name(), document_.steps().size());
  applyFlowIoBindings();
  syncVarsToUi();
  updateRunChrome();
  refreshConfigStatus();
}

void MainWindow::syncVarsToUi() {
  document_.setVariables(flow_vars_);
  if (var_watch_) var_watch_->setVariables(flow_vars_);
  if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
  if (host_strip_)
    host_strip_->updateFromVars(
        flow_vars_, flow_vars_.value(QStringLiteral("barcodeCount")).toInt(), true);
  if (host_sm_ && host_strip_)
    host_sm_->setRunStats(host_strip_->okStreak(), host_strip_->ngCount(), last_cycle_ms_);
}

void MainWindow::logResult(const QString& line) {
  const QString stamp =
      QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss.zzz"));
  const QString entry = QStringLiteral("[%1] %2").arg(stamp, line);
  resultLogAll_.push_back(entry);
  while (resultLogAll_.size() > 2000) resultLogAll_.removeFirst();
  if (!result_log_) return;
  const QString f = resultLogFilter_ ? resultLogFilter_->text().trimmed() : QString();
  if (f.isEmpty() || entry.contains(f, Qt::CaseInsensitive))
    result_log_->appendPlainText(entry);
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


QVariant MainWindow::resolveIoBinding(const QString& binding) const {
  const QString b = binding.trimmed();
  if (b.isEmpty() || b == QLatin1String("—") || b == QLatin1String("-")) return {};
  if (b.startsWith(QStringLiteral("flow."))) {
    const QString key = b.mid(5);
    if (key == QLatin1String("vars")) return flow_vars_;
    return flow_vars_.value(key);
  }
  if (b.startsWith(QStringLiteral("source."))) {
    const QString key = b.mid(7);
    if (key == QLatin1String("image") || key.startsWith(QStringLiteral("image")))
      return QStringLiteral("%1x%2")
          .arg(image_view_ ? image_view_->currentImage().width() : 0)
          .arg(image_view_ ? image_view_->currentImage().height() : 0);
    return document_.sourceConfig().value(key);
  }
  // "0 模块.字段" or "模块.字段"
  QString path = b;
  const int sp = path.indexOf(QLatin1Char(' '));
  if (sp > 0) {
    bool idxOk = false;
    path.left(sp).toInt(&idxOk);
    if (idxOk) path = path.mid(sp + 1).trimmed();
  }
  path.replace(QStringLiteral("[]"), QString());
  if (path.contains(QLatin1Char('.'))) {
    const QString field = path.section(QLatin1Char('.'), -1);
    if (flow_vars_.contains(field)) return flow_vars_.value(field);
    if (field == QLatin1String("图像") || field.compare(QStringLiteral("image"), Qt::CaseInsensitive) == 0)
      return resolveIoBinding(QStringLiteral("source.image"));
  }
  if (flow_vars_.contains(b)) return flow_vars_.value(b);
  return b;
}

void MainWindow::applyFlowIoBindings() {
  const QVariantMap io = document_.flowIo();
  const QVariantList outs = io.value(QStringLiteral("outputs")).toList();
  for (const QVariant& rowV : outs) {
    const QVariantMap row = rowV.toMap();
    const QString name = row.value(QStringLiteral("name")).toString().trimmed();
    if (name.isEmpty()) continue;
    const QString binding = row.value(QStringLiteral("binding")).toString();
    QVariant val = resolveIoBinding(binding);
    const QString emptyDef = row.value(QStringLiteral("emptyDefault")).toString();
    const bool emptyVal = !val.isValid() || val.isNull() ||
                          (val.typeId() == QMetaType::QString && val.toString().isEmpty());
    if (emptyVal && !emptyDef.isEmpty()) val = emptyDef;
    flow_vars_.insert(QStringLiteral("io.%1").arg(name), val);
    // also mirror Result / common names into plain vars for Comm/HMI
    if (name == QLatin1String("Result") && !flow_vars_.contains(QStringLiteral("formatted"))) {
      if (val.typeId() == QMetaType::QString) flow_vars_.insert(QStringLiteral("formatted"), val);
    }
  }
  const QVariantList ins = io.value(QStringLiteral("inputs")).toList();
  for (const QVariant& rowV : ins) {
    const QVariantMap row = rowV.toMap();
    const QString name = row.value(QStringLiteral("name")).toString().trimmed();
    if (name.isEmpty()) continue;
    const QString binding = row.value(QStringLiteral("binding")).toString();
    flow_vars_.insert(QStringLiteral("io.in.%1").arg(name), resolveIoBinding(binding));
  }
}

void MainWindow::updateRunChrome() {
  const bool busy = busy_.load();
  if (act_run_) act_run_->setEnabled(!busy || continuous_run_);
  if (act_stop_) act_stop_->setEnabled(busy || continuous_run_ || preview_active_);
  if (act_pause_) {
    act_pause_->setEnabled(continuous_run_);
    act_pause_->setText(run_paused_ ? QStringLiteral("▶ 继续") : QStringLiteral("⏸ 暂停"));
  }
  QString modeText = QStringLiteral("设计态");
  if (run_mode_)
    modeText = QStringLiteral("运行态");
  else if (continuous_run_)
    modeText = run_paused_ ? QStringLiteral("已暂停") : QStringLiteral("连续");
  if (mode_badge_) {
    mode_badge_->setText(modeText);
    mode_badge_->setProperty("runMode", run_mode_ || continuous_run_);
    mode_badge_->style()->unpolish(mode_badge_);
    mode_badge_->style()->polish(mode_badge_);
  }
  if (op_lib_) op_lib_->setEnabled(!run_mode_);
  if (op_rail_) op_rail_->setEnabled(!run_mode_);
  if (flow_tabs_) flow_tabs_->setDesignLocked(run_mode_);
  if (act_mode_) act_mode_->setChecked(run_mode_);
  const QString hostState = host_sm_ ? host_sm_->state() : QStringLiteral("Idle");
  if (host_strip_) {
    host_strip_->setIntervalMs(document_.runIntervalMs() > 0 ? document_.runIntervalMs() : 200);
    host_strip_->setRunChrome(modeText, hostState, run_cycle_);
  }
  if (flow_tabs_) {
    flow_tabs_->setIntervalMs(document_.runIntervalMs() > 0 ? document_.runIntervalMs() : 200);
    flow_tabs_->setRunChrome(modeText, run_cycle_, last_cycle_ms_, continuous_run_,
                             run_paused_);
  }
}

void MainWindow::pushSoftControls() {
  if (!cam_worker_) return;
  cam_worker_->setSoftControls(document_.exposureUs(), document_.gainDb());
}

void MainWindow::noteHostResult(bool ok, const QString& detail) {
  if (!host_sm_) return;
  if (ok) {
    host_sm_->notifyOk();
    if (host_strip_) host_strip_->setAlarm(false);
    if (continuous_run_ && !run_paused_ && host_sm_->state() != QLatin1String("Alarm"))
      host_sm_->applyState(QStringLiteral("Running"));
  } else {
    host_sm_->raiseAlarm(detail);
    if (host_strip_) host_strip_->setAlarm(true, detail);
  }
}

bool MainWindow::loadImagePath(const QString& path, bool addToStrip) {
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
  if (filmstrip_) {
    if (addToStrip) filmstrip_->addPaths({path});
    else filmstrip_->setStatus(QFileInfo(path).fileName());
  }
  showStatus(QStringLiteral("已加载 %1").arg(path));
  return true;
}

void MainWindow::refreshConfigStatus() {
  if (!status_config_ || !flow_scene_) return;
  int missing = 0;
  for (const FlowStep& s : document_.steps()) {
    if (s.operation == QLatin1String("locate") &&
        s.params.value(QStringLiteral("templatePath")).toString().isEmpty()) {
      const QString st = s.runState;
      if (st != QLatin1String("OK") && st != QLatin1String("NG") &&
          !st.contains(QStringLiteral("运行")))
        flow_scene_->setNodeRunState(s.id, QStringLiteral("未配置"));
      ++missing;
    }
  }
  if (missing == 0) {
    status_config_->setText(QStringLiteral("组件配置完成"));
    status_config_->setStyleSheet(QStringLiteral("color:#3ecf8e;"));
  } else {
    status_config_->setText(QStringLiteral("%1 个模块未配置").arg(missing));
    status_config_->setStyleSheet(QStringLiteral("color:#e53935;font-weight:600;"));
  }
}

void MainWindow::auditParam(const QString& nodeId, const QString& key,
                            const QString& oldText, const QString& newText) {
  QString module = nodeId;
  if (nodeId == QLatin1String("source"))
    module = QStringLiteral("图像源1");
  else if (const FlowStep* s = document_.findStep(nodeId))
    module = s->name;
  logResult(QStringLiteral("流程1.%1.%2 参数已修改, 旧值:%3, 新值:%4")
                .arg(module, key, oldText, newText));
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
  double algoMs = 0;
  const auto flowT0 = std::chrono::steady_clock::now();
  QVector<OverlayHit> overlays;
  if (result_table_) result_table_->setRowCount(0);

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
    } else if (op == QLatin1String("locate")) {
      QString tplPath = step->params.value(QStringLiteral("templatePath")).toString();
      QImage tpl;
      if (!tplPath.isEmpty()) tpl.load(tplPath);
      bool created = false;
      if (tpl.isNull()) {
        const int tw = step->params.value(QStringLiteral("templateW"), 80).toInt();
        const int th = step->params.value(QStringLiteral("templateH"), 64).toInt();
        tpl = salientCrop(working, tw, th);
        const QString dir =
            QStringLiteral("/home/allen/文档/sieansvision/artifacts/qt-templates");
        QDir().mkpath(dir);
        tplPath = dir + QLatin1Char('/') + id + QStringLiteral(".png");
        tpl.save(tplPath);
        step->params.insert(QStringLiteral("templatePath"), tplPath);
        step->params.insert(QStringLiteral("templateCaptured"), true);
        created = true;
      }
      const double minScore = step->params.value(QStringLiteral("minScore"), 0.55).toDouble();
      const int maxN = qMax(1, step->params.value(QStringLiteral("maxMatches"), 1).toInt());
      const auto t0 = std::chrono::steady_clock::now();
      const QVector<TemplateHit> found =
          findTemplate(working, tpl, minScore, maxN);
      const double matchMs = std::chrono::duration<double, std::milli>(
                                 std::chrono::steady_clock::now() - t0)
                                 .count();
      algoMs += matchMs;
      const double best = found.isEmpty() ? 0.0 : found.first().score;
      ok = !found.isEmpty();
      flow_vars_.insert(QStringLiteral("locateScore"), best);
      flow_vars_.insert(QStringLiteral("locateCount"), found.size());
      flow_vars_.insert(QStringLiteral("locateX"),
                        found.isEmpty() ? 0 : found.first().rect.center().x());
      flow_vars_.insert(QStringLiteral("locateY"),
                        found.isEmpty() ? 0 : found.first().rect.center().y());
      flow_vars_.insert(QStringLiteral("locateOk"), ok ? 1 : 0);
      if (!flow_vars_.contains(QStringLiteral("barcodeCount"))) {
        flow_vars_.insert(QStringLiteral("passGate"), ok ? 1 : 0);
      }
      StepSnap snap;
      snap.ok = ok;
      snap.count = found.size();
      snap.matches = found.size();
      snap.score = best;
      snap.confidence = best;
      snap.text = QString::number(best, 'f', 3);
      step_snaps.insert(id, snap);
      for (const TemplateHit& hit : found) {
        OverlayHit o;
        o.format = QStringLiteral("匹配");
        o.text = QStringLiteral("分数 %1  角度 0").arg(hit.score, 0, 'f', 2);
        const QRect r = hit.rect;
        o.polygon << r.topLeft() << r.topRight() << r.bottomRight() << r.bottomLeft();
        overlays.push_back(o);
        const int row = result_table_->rowCount();
        result_table_->insertRow(row);
        result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("locate.score")));
        result_table_->setItem(row, 1,
                               new QTableWidgetItem(QString::number(hit.score, 'f', 3)));
        result_table_->setItem(row, 2, new QTableWidgetItem(QStringLiteral("float")));
      }
      if (output_view_) output_view_->setLiveImage(working);
      note = created
                 ? QStringLiteral("已创建模板 · %1 个 · %2 · %3 ms")
                       .arg(found.size())
                       .arg(best, 0, 'f', 2)
                       .arg(matchMs, 0, 'f', 1)
                 : QStringLiteral("%1 个 · 分数 %2 · %3 ms")
                       .arg(found.size())
                       .arg(best, 0, 'f', 2)
                       .arg(matchMs, 0, 'f', 1);
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
      algoMs += decodeMs;
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
        snap.matches = int(hits.size());
        snap.text = texts.isEmpty() ? QString() : texts.first();
        snap.score = hits.empty() ? 0.0 : 1.0;
        snap.confidence = snap.score;
        snap.fields.insert(QStringLiteral("text"), snap.text);
        snap.fields.insert(QStringLiteral("score"), snap.score);
        for (const auto& h : hits) snap.texts << QString::fromStdString(h.text);
        step_snaps.insert(id, snap);
      }
      ok = gate || !step->params.value(QStringLiteral("judgeEnable"), true).toBool();
      note = QStringLiteral("%1 码 · %2 ms").arg(hits.size()).arg(decodeMs, 0, 'f', 1);

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
      const QString srcVar =
          step->params
              .value(QStringLiteral("sourceVar"), QStringLiteral("barcodeCount"))
              .toString();
      QVariant src = flow_vars_.value(srcVar);
      bool gate = false;
      int count = 0;
      if (src.typeId() == QMetaType::Bool) {
        gate = src.toBool();
        count = gate ? 1 : 0;
      } else if (src.canConvert<double>()) {
        const double d = src.toDouble();
        count = int(d);
        // bool-ish 0/1 or numeric threshold
        if (srcVar.contains(QStringLiteral("Ok"), Qt::CaseInsensitive) ||
            srcVar.contains(QStringLiteral("Gate"), Qt::CaseInsensitive) ||
            srcVar.contains(QStringLiteral("pass"), Qt::CaseInsensitive))
          gate = d != 0.0;
        else
          gate = count >= minC;
      } else {
        const QString s = src.toString().trimmed();
        gate = !s.isEmpty() && s != QLatin1String("0") &&
               s.compare(QStringLiteral("false"), Qt::CaseInsensitive) != 0;
        count = gate ? 1 : 0;
      }
      flow_vars_.insert(QStringLiteral("barcodeOk"), gate ? 1 : 0);
      flow_vars_.insert(QStringLiteral("passGate"), gate ? 1 : 0);
      const QString passVar =
          step->params.value(QStringLiteral("passVar"), QStringLiteral("passGate"))
              .toString();
      if (!passVar.isEmpty()) flow_vars_.insert(passVar, gate ? 1 : 0);
      ok = gate;
      note = QStringLiteral("passGate=%1 src=%2=%3 min=%4")
                 .arg(gate ? 1 : 0)
                 .arg(srcVar)
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
        const QString val = flow_vars_.value(key).toString();
        out.replace(QStringLiteral("{%1}").arg(i), val);
        out.replace(QStringLiteral("{%1}").arg(key), val);  // named braces
      }
      // also ${flow.x} / remaining {name} / {{name}}
      out = CommHub::expandTemplate(out, flow_vars_);
      bool usedEmpty = false;
      if (out.trimmed().isEmpty()) {
        out = step->params.value(QStringLiteral("emptyDefault")).toString();
        out = CommHub::expandTemplate(out, flow_vars_);
        usedEmpty = !out.isEmpty();
      }
      const QString target =
          step->params.value(QStringLiteral("targetVar"), QStringLiteral("formatted"))
              .toString();
      flow_vars_.insert(target, out);
      flow_vars_.insert(QStringLiteral("formatted"), out);
      flow_vars_.insert(QStringLiteral("commPayload"), out);
      note = usedEmpty ? QStringLiteral("emptyDefault→%1").arg(out.left(64))
                       : out.left(80);
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
      QString rx = comm_hub_->lastRx();
      if (rx.isEmpty()) rx = comm_hub_->lastTx();  // LocalBus echo race-safe
      const QString target =
          step->params.value(QStringLiteral("targetVar"), QStringLiteral("lastRecv"))
              .toString();
      flow_vars_.insert(target, rx);
      ok = !rx.isEmpty();
      note = rx.isEmpty() ? QStringLiteral("(空 RX)") : rx.left(60);
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

  image_view_->setOverlays(overlays);
  if (output_view_) output_view_->setOverlays(overlays);
  if (flow_vars_.contains(QStringLiteral("passGate"))) {
    const bool gateOk = flow_vars_.value(QStringLiteral("passGate")).toInt() != 0 ||
                        flow_vars_.value(QStringLiteral("passGate")).toBool();
    if (gateOk)
      noteHostResult(true, QString());
    else if (host_strip_)
      host_strip_->setAlarm(false);
  }
  ++run_cycle_;
  applyFlowIoBindings();
  syncVarsToUi();
  updateRunChrome();
  const double flowMs = std::chrono::duration<double, std::milli>(
                            std::chrono::steady_clock::now() - flowT0)
                            .count();
  const double toolMs = qMax(0.0, flowMs - algoMs);
  last_cycle_ms_ = flowMs;
  if (host_strip_) host_strip_->setCycleTiming(flowMs);
  if (host_sm_ && host_strip_)
    host_sm_->setRunStats(host_strip_->okStreak(), host_strip_->ngCount(), flowMs);
  if (status_timing_) {
    status_timing_->setText(QStringLiteral("流程 %1 ms · 工具 %2 ms · 算法 %3 ms")
                                .arg(flowMs, 0, 'f', 2)
                                .arg(toolMs, 0, 'f', 2)
                                .arg(algoMs, 0, 'f', 2));
  }
  refreshConfigStatus();
  showStatus(QStringLiteral("流水线完成 · 码 %1 · %2 ms")
                 .arg(hits.size())
                 .arg(decodeMs, 0, 'f', 1));

  const QByteArray smoke = qgetenv("SIEANS_QT_SMOKE_REPORT");
  if (!smoke.isEmpty()) {
    QFile f(QString::fromUtf8(smoke));
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
      const QString line =
          QStringLiteral(
              "codes=%1 ms=%2 w=%3 h=%4 passGate=%5 barcodeText=%6 "
              "formatted=%7 lastRecv=%8 urlOk=%9 tcp=%10\n")
              .arg(hits.size())
              .arg(decodeMs, 0, 'f', 2)
              .arg(src.width())
              .arg(src.height())
              .arg(flow_vars_.value(QStringLiteral("passGate")).toString())
              .arg(flow_vars_.value(QStringLiteral("barcodeText")).toString()
                       .left(80).replace(QLatin1Char('\n'), QLatin1Char('|')))
              .arg(flow_vars_.value(QStringLiteral("formatted")).toString()
                       .left(120).replace(QLatin1Char('\n'), QLatin1Char('|')))
              .arg(flow_vars_.value(QStringLiteral("lastRecv")).toString()
                       .left(120).replace(QLatin1Char('\n'), QLatin1Char('|')))
              .arg(flow_vars_.value(QStringLiteral("urlOk")).toString())
              .arg(comm_hub_ ? comm_hub_->tcpStatus() : QStringLiteral("n/a"));
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

bool MainWindow::eventFilter(QObject* obj, QEvent* event) {
  if (obj == listen_badge_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton) {
      if (bottom_tabs_ && comm_panel_) {
        bottom_tabs_->setCurrentWidget(comm_panel_);
        if (comm_panel_) {
          comm_panel_->bindDocument(document_.commManager());
          comm_panel_->setFlowVars(flow_vars_);
          comm_panel_->setFocus(Qt::OtherFocusReason);
        }
        showStatus(QStringLiteral("通信面板"));
      }
      return true;
    }
    if (me->button() == Qt::MiddleButton || me->button() == Qt::RightButton) {
      onOpenCommManager();
      return true;
    }
  }
  if (obj == mode_badge_ && event->type() == QEvent::MouseButtonDblClick) {
    if (continuous_run_) {
      onStopRun();
      showStatus(QStringLiteral("已停连续 · 模式双击"));
    } else if (act_mode_) {
      act_mode_->toggle();
    }
    return true;
  }
  if (obj == mode_badge_ && event->type() == QEvent::MouseButtonRelease) {
    auto* me = static_cast<QMouseEvent*>(event);
    if (me->button() == Qt::LeftButton) {
      if (me->modifiers() & Qt::AltModifier) {
        if (continuous_run_ && !run_paused_) {
          onPauseRun();
          showStatus(QStringLiteral("已暂停 · Alt+模式"));
        } else if (run_paused_) {
          onResumeRun();
          showStatus(QStringLiteral("已继续 · Alt+模式"));
        } else {
          showStatus(QStringLiteral("无连续可暂停 · Alt+模式"));
        }
        return true;
      }
      if (act_mode_) act_mode_->toggle();
      return true;
    }
    if (me->button() == Qt::MiddleButton) {
      onRunOnce();
      showStatus(QStringLiteral("运行一次 · 模式中键"));
      return true;
    }
    if (me->button() == Qt::RightButton) {
      // VisionMaster-ish: right-click mode badge toggles continuous
      if (continuous_run_ && !run_paused_) {
        onPauseRun();
      } else if (run_paused_) {
        onResumeRun();
      } else {
        onRunContinuous();
      }
      return true;
    }
  }
  return QMainWindow::eventFilter(obj, event);
}

void MainWindow::onOpenCommManager() {
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("通信管理 · TCP / LocalBus"));
  dlg.resize(640, 480);
  auto* lay = new QVBoxLayout(&dlg);
  auto* panel = new CommPanel(comm_hub_, &dlg);
  panel->bindDocument(document_.commManager());
  panel->setFlowVars(flow_vars_);
  connect(panel, &CommPanel::requestSaveComm, this, [this](const QVariantMap& cm) {
    document_.setCommManager(cm);
  });
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
  backend->addItem(QStringLiteral("Soft 仿真"), QStringLiteral("soft"));
  const QString cur = document_.cameraBackend();
  backend->setCurrentIndex(backend->findData(cur) >= 0 ? backend->findData(cur) : 0);
  lay->addWidget(new QLabel(QStringLiteral("采集后端")));
  lay->addWidget(backend);
  auto* exp = new QDoubleSpinBox;
  exp->setRange(100, 10000000);
  exp->setDecimals(0);
  exp->setSuffix(QStringLiteral(" µs"));
  exp->setValue(document_.exposureUs());
  auto* gain = new QDoubleSpinBox;
  gain->setRange(0, 48);
  gain->setDecimals(1);
  gain->setSuffix(QStringLiteral(" dB"));
  gain->setValue(document_.gainDb());
  auto* ctl = new QHBoxLayout;
  ctl->addWidget(new QLabel(QStringLiteral("曝光")));
  ctl->addWidget(exp, 1);
  ctl->addWidget(new QLabel(QStringLiteral("增益")));
  ctl->addWidget(gain, 1);
  lay->addLayout(ctl);
  auto writeControls = [&]() {
    auto cam = document_.sourceConfig().value(QStringLiteral("cameraParams")).toMap();
    cam.insert(QStringLiteral("exposureTime"), exp->value());
    cam.insert(QStringLiteral("gainDb"), gain->value());
    auto sc = document_.sourceConfig();
    sc.insert(QStringLiteral("cameraParams"), cam);
    document_.sourceConfigMut() = sc;
    pushSoftControls();
  };
  connect(exp, QOverload<double>::of(&QDoubleSpinBox::valueChanged), &dlg,
          [&](double) { writeControls(); });
  connect(gain, QOverload<double>::of(&QDoubleSpinBox::valueChanged), &dlg,
          [&](double) { writeControls(); });
  auto* list = new QListWidget;
  lay->addWidget(new QLabel(QStringLiteral("设备列表")));
  lay->addWidget(list, 1);
  QStringList ids;

  auto refill = [&]() {
    list->clear();
    ids.clear();
    const QString kind = backend->currentData().toString();
    if (kind == QLatin1String("soft")) {
      list->addItem(QStringLiteral("SoftCam-0 仿真帧（无硬件）"));
      ids.push_back(QStringLiteral("soft:0"));
    } else if (kind == QLatin1String("uvc")) {
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
  if (backend != QLatin1String("uvc") && backend != QLatin1String("soft") &&
      !sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("GenTL 不可用 — 可切 UVC 或 Soft 仿真"));
    return false;
  }
  pushSoftControls();
  // Soft/UVC: block until open returns so open-and-run GenTL→QR can grab immediately.
  const Qt::ConnectionType openHow =
      (backend == QLatin1String("soft") || backend == QLatin1String("uvc"))
          ? Qt::BlockingQueuedConnection
          : Qt::QueuedConnection;
  QMetaObject::invokeMethod(
      cam_worker_, "openDeviceWithBackend", openHow,
      Q_ARG(QString, backend),
      Q_ARG(QString, document_.cameraDeviceId()),
      Q_ARG(double, document_.acquisitionFps()),
      Q_ARG(double, document_.exposureUs()));
  if (backend == QLatin1String("soft") && cam_worker_ && cam_worker_->isOpen())
    logResult(QStringLiteral("Soft 相机已打开 · GenTL→QR 就绪"));
  return true;
}

void MainWindow::onStartContinuousPreview() {
  const QString backend = document_.cameraBackend();
  if (backend != QLatin1String("uvc") && backend != QLatin1String("soft") &&
      !sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("连续预览: GenTL 不可用（可在相机管理切 UVC 或 Soft）"));
    return;
  }
  preview_active_ = true;
  updateRunChrome();
  const bool same =
      cam_worker_ && cam_worker_->isOpen() && cam_worker_->backend() == backend;
  if (same) {
    QMetaObject::invokeMethod(cam_worker_, "startPreview", Qt::QueuedConnection);
  } else {
    ensureCameraOpen();
  }
  logResult(QStringLiteral("连续预览已请求启动"));
}

void MainWindow::onStopContinuousPreview() {
  preview_active_ = false;
  if (cam_worker_) {
    cam_worker_->requestStop();
    QMetaObject::invokeMethod(cam_worker_, "stopPreview", Qt::QueuedConnection);
  }
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
  if (msg.contains(QStringLiteral("打开")) || msg.contains(QStringLiteral("未发现")) ||
      msg.contains(QStringLiteral("请先打开"))) {
    preview_active_ = false;
    updateRunChrome();
  }
  noteHostResult(false, msg);
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

  const QString backend = document_.cameraBackend();
  const bool canGrab = backend == QLatin1String("soft") ||
                       backend == QLatin1String("uvc") ||
                       sieans::GenTLCapture::available();
  if (frame.isNull() && canGrab) {
    ensureCameraOpen();
    // Soft/UVC: block so GenTL→QR open-and-run sees a frame immediately.
    const Qt::ConnectionType grabHow =
        (backend == QLatin1String("soft") || backend == QLatin1String("uvc"))
            ? Qt::BlockingQueuedConnection
            : Qt::QueuedConnection;
    QMetaObject::invokeMethod(cam_worker_, "grabOne", grabHow);
    frame = cam_worker_ ? cam_worker_->latestFrame() : QImage();
    for (int i = 0; i < 40 && frame.isNull(); ++i) {
      QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
      QThread::msleep(50);
      frame = cam_worker_->latestFrame();
    }
    // Soft open-and-run: one more blocking grab if first pass still empty.
    if (frame.isNull() && backend == QLatin1String("soft") && cam_worker_) {
      QMetaObject::invokeMethod(cam_worker_, "grabOne",
                                Qt::BlockingQueuedConnection);
      frame = cam_worker_->latestFrame();
      if (!frame.isNull())
        logResult(QStringLiteral("Soft 二次 grab 成功 · GenTL→QR"));
    }
  }

  if (frame.isNull()) {
    logResult(QStringLiteral("运行失败: 无图像（请连续预览、采图或打开示例）"));
    setBusy(false);
    return;
  }
  if (backend == QLatin1String("soft")) {
    showStatus(QStringLiteral("Soft 帧 %1×%2 · GenTL→QR").arg(frame.width()).arg(frame.height()),
               1800);
  }

  image_view_->setLiveImage(frame);
  if (filmstrip_ && document_.cameraBackend() == QLatin1String("soft")) {
    const QString snap =
        QStringLiteral("/home/allen/文档/sieansvision/artifacts/soft-live-%1.png")
            .arg(run_cycle_ % 8);
    QDir().mkpath(QFileInfo(snap).absolutePath());
    if (frame.save(snap)) filmstrip_->addPaths({snap});
  }
  runPipeline(frame, true);
  if (filmstrip_ && document_.cameraBackend() == QLatin1String("soft")) {
    filmstrip_->setStatus(
        QStringLiteral("soft %1×%2 · 码%3 · gate%4")
            .arg(frame.width())
            .arg(frame.height())
            .arg(flow_vars_.value(QStringLiteral("barcodeCount")).toInt())
            .arg(flow_vars_.value(QStringLiteral("passGate")).toInt()));
  }
  setBusy(false);
}

void MainWindow::onRunContinuous() {
  if (continuous_run_ && !run_paused_) return;
  run_paused_ = false;
  continuous_run_ = true;
  int interval = document_.runIntervalMs();
  if (interval <= 0) interval = 200;
  continuous_timer_.start(interval);
  if (!preview_active_) onStartContinuousPreview();
  if (host_sm_ && host_sm_->state() != QLatin1String("Alarm"))
    host_sm_->applyState(QStringLiteral("Running"));
  logResult(QStringLiteral("连续运行已启动 · 间隔 %1 ms").arg(interval));
  showStatus(QStringLiteral("连续运行中"));
  updateRunChrome();
  onContinuousTick();
}

void MainWindow::onPauseRun() {
  if (!continuous_run_) return;
  run_paused_ = true;
  continuous_timer_.stop();
  if (host_sm_) host_sm_->applyState(QStringLiteral("Paused"));
  logResult(QStringLiteral("连续运行已暂停"));
  showStatus(QStringLiteral("已暂停"));
  updateRunChrome();
}

void MainWindow::onResumeRun() {
  if (!continuous_run_) {
    onRunContinuous();
    return;
  }
  run_paused_ = false;
  int interval = document_.runIntervalMs();
  if (interval <= 0) interval = 200;
  continuous_timer_.start(interval);
  if (host_sm_ && host_sm_->state() != QLatin1String("Alarm"))
    host_sm_->applyState(QStringLiteral("Running"));
  logResult(QStringLiteral("连续运行继续"));
  showStatus(QStringLiteral("连续运行中"));
  updateRunChrome();
}

void MainWindow::onStopRun() {
  continuous_run_ = false;
  run_paused_ = false;
  continuous_timer_.stop();
  busy_.store(false);
  setBusy(false);
  if (host_sm_ && host_sm_->state() != QLatin1String("Alarm"))
    host_sm_->applyState(QStringLiteral("Stopped"));
  logResult(QStringLiteral("已停止运行"));
  showStatus(QStringLiteral("已停止"));
  updateRunChrome();
}

void MainWindow::onContinuousTick() {
  if (!continuous_run_ || run_paused_) return;
  if (busy_.load()) return;
  if (filmstrip_ && filmstrip_->autoSwitch() && filmstrip_->count() > 1)
    filmstrip_->advance();
  onRunOnce();
}

void MainWindow::onToggleRunMode(bool on) {
  run_mode_ = on;
  if (flow_scene_) flow_scene_->setEditingLocked(on);
  if (host_sm_ && !continuous_run_) {
    host_sm_->applyState(on ? QStringLiteral("Running") : QStringLiteral("Idle"));
  }
  if (prop_float_ && on) prop_float_->hide();
  updateRunChrome();
  logResult(on ? QStringLiteral("运行模式：画布/算子库已锁定")
               : QStringLiteral("设计态：画布可编辑"));
  showStatus(on ? QStringLiteral("运行模式") : QStringLiteral("设计态"));
}

void MainWindow::onRunAllImages() {
  if (!filmstrip_ || filmstrip_->count() == 0) {
    onRunOnce();
    return;
  }
  const QStringList paths = filmstrip_->paths();
  logResult(QStringLiteral("运行全部 · %1 张").arg(paths.size()));
  for (const QString& path : paths) {
    if (!loadImagePath(path, false)) continue;
    runPipeline(image_view_->currentImage(), true);
  }
}

void MainWindow::onNodeSelected(const QString& nodeId) {
  if (!prop_float_) return;
  if (nodeId.isEmpty()) {
    prop_float_->hide();
    return;
  }
  if (nodeId == QLatin1String("source")) {
    prop_float_->showForSource(document_.sourceConfig());
    const QRect saved = document_.propertyFloatGeometry();
    if (saved.isValid()) {
      prop_float_->applyChromeGeometry(saved);
    } else if (flow_view_) {
      const QPoint g = flow_view_->mapToGlobal(QPoint(flow_view_->width() - 20, 40));
      prop_float_->move(g);
    }
    return;
  }
  if (const FlowStep* s = document_.findStep(nodeId)) {
    prop_float_->showForStep(*s);
    const QRect saved = document_.propertyFloatGeometry();
    if (saved.isValid()) {
      prop_float_->applyChromeGeometry(saved);
    } else if (flow_view_) {
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


void MainWindow::onDuplicateNode(const QString& nodeId) {
  if (run_mode_) {
    showStatus(QStringLiteral("运行模式已锁定画布"));
    return;
  }
  if (nodeId.isEmpty() || nodeId == QLatin1String("source")) {
    showStatus(QStringLiteral("无法复制图像源 · Ctrl+D"));
    return;
  }
  const FlowStep* src = document_.findStep(nodeId);
  if (!src) {
    showStatus(QStringLiteral("未找到模块 · Ctrl+D"));
    return;
  }
  FlowStep s = *src;
  s.id = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
  s.name = src->name + QStringLiteral(" 副本");
  s.position = src->position + QPointF(36, 48);
  s.runState = QStringLiteral("等待执行");
  // keep operation + params
  document_.stepsMut().push_back(s);
  applyDocumentToUi();
  logResult(QStringLiteral("已复制模块: %1 → %2").arg(src->name, s.name));
  showStatus(QStringLiteral("已复制模块 · Ctrl+D · %1").arg(s.name));
}

void MainWindow::onAddOperator(const QString& key, const QString& name) {
  if (run_mode_) {
    showStatus(QStringLiteral("运行模式已锁定画布"));
    return;
  }
  addOperatorAt(key, name, QPointF(300, 160 + document_.steps().size() * 120), true);
}

void MainWindow::onDropOperator(const QString& key, const QPointF& scenePos) {
  if (run_mode_) {
    showStatus(QStringLiteral("运行模式已锁定画布"));
    return;
  }
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
  } else if (key == QLatin1String("locate")) {
    s.params = {{QStringLiteral("minScore"), 0.55},
                {QStringLiteral("maxMatches"), 1},
                {QStringLiteral("templateW"), 80},
                {QStringLiteral("templateH"), 64},
                {QStringLiteral("templatePath"), QString()}};
    s.runState = QStringLiteral("未配置");
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
    s.params = {{QStringLiteral("minCount"), 1},
                {QStringLiteral("sourceVar"), QStringLiteral("barcodeCount")},
                {QStringLiteral("passVar"), QStringLiteral("passGate")}};
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
  QString oldText;
  if (nodeId == QLatin1String("source")) {
    auto& sc = document_.sourceConfigMut();
    if (key.startsWith(QStringLiteral("cam."))) {
      auto cam = sc.value(QStringLiteral("cameraParams")).toMap();
      const QString camKey = key.mid(4);
      oldText = cam.value(camKey).toString();
      cam.insert(camKey, coerceParam(camKey, value, cam.value(camKey)));
      sc.insert(QStringLiteral("cameraParams"), cam);
      if (camKey == QLatin1String("imageSource"))
        sc.insert(QStringLiteral("mode"),
                  value == QLatin1String("local") ? QStringLiteral("local")
                                                  : QStringLiteral("camera"));
    } else {
      oldText = sc.value(key).toString();
      sc.insert(key, coerceParam(key, value, sc.value(key)));
    }
    if (isExposureKey(key)) pushSoftControls();
    auditParam(nodeId, key, oldText, value);
    if (key == QLatin1String("cam.imageSource") && prop_float_) {
      QTimer::singleShot(0, this, [this]() {
        if (prop_float_) prop_float_->showForSource(document_.sourceConfig());
      });
    }
    return;
  }
  if (FlowStep* s = document_.findStep(nodeId)) {
    oldText = s->params.value(key).toString();
    s->params.insert(key, coerceParam(key, value, s->params.value(key)));
    auditParam(nodeId, key, oldText, value);
    if (isExposureKey(key)) {
      auto cam = document_.sourceConfig().value(QStringLiteral("cameraParams")).toMap();
      cam.insert(key, s->params.value(key));
      auto sc = document_.sourceConfig();
      sc.insert(QStringLiteral("cameraParams"), cam);
      document_.sourceConfigMut() = sc;
      pushSoftControls();
    }
    if (key == QLatin1String("templatePath")) refreshConfigStatus();
  }
}

void MainWindow::onParamsReverted(const QString& nodeId, const QVariantMap& snapshot) {
  if (nodeId == QLatin1String("source")) {
    document_.sourceConfigMut() = snapshot;
  } else if (FlowStep* s = document_.findStep(nodeId)) {
    s->params = snapshot;
  }
  pushSoftControls();
  logResult(QStringLiteral("已放弃属性修改: %1").arg(nodeId));
}

void MainWindow::onOpenFlowIo() {
  FlowIoDialog dlg(document_.flowIo(), this);
  if (dlg.exec() != QDialog::Accepted) return;
  document_.setFlowIo(dlg.resultIo());
  applyFlowIoBindings();
  syncVarsToUi();
  const int nin = document_.flowIo().value(QStringLiteral("inputs")).toList().size();
  const int nout = document_.flowIo().value(QStringLiteral("outputs")).toList().size();
  logResult(QStringLiteral("流程 I/O 已更新 · 输入 %1 · 输出 %2").arg(nin).arg(nout));
  showStatus(QStringLiteral("流程 I/O 绑定已保存"));
  refreshConfigStatus();
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
