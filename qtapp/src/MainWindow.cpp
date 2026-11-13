#include "MainWindow.hpp"
#include <QDebug>
#include <algorithm>
#include "RecentFiles.hpp"
#include "WorkbenchPaths.hpp"
#include "LocateMatchPanel.hpp"
#include "ProtocolNet.hpp"
#include "Theme.hpp"
#include "ExprEval.hpp"
#include "TemplateMatch.hpp"
#include "FixturePose.hpp"
#include "CaliperMeasure.hpp"
#include "DefectDetect.hpp"
#include "RegionAnalyze.hpp"
#include "ColorOp.hpp"
#include "CameraCal.hpp"
#include "WarpOp.hpp"
#include "PreprocessOp.hpp"
#include "FftOp.hpp"
#include "ClassifyOp.hpp"
#include "GeometryFind.hpp"
#include "MeasureDim.hpp"
#include "SerialExchange.hpp"
#include "ModbusClient.hpp"
#include "S7Client.hpp"
#include "OpcUaClient.hpp"
#include "MqttClient.hpp"
#include "YoloInfer.hpp"
#include "CloudOps.hpp"
#include "SocketExchange.hpp"
#include "FlowExtras.hpp"
#include "PythonExt.hpp"
#include "ConditionEval.hpp"
#include "SubflowExec.hpp"
#include "SubflowDialog.hpp"
#include "FlowIoDialog.hpp"
#include "CommHub.hpp"
#include <QInputDialog>
#include <QShortcut>
#include <QScrollBar>
#include <QLineEdit>
#include "UvcCapture.hpp"

#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>

#include <sieans/barcode.hpp>
#include <sieans/ocr.hpp>
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
#include <QColor>
#include <QImage>
#include <QFileDialog>
#include <QFile>
#include <QFileInfo>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QListWidget>
#include <QComboBox>
#include <QCheckBox>
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
  setWindowTitle(QStringLiteral("[*]SIEANS Vision · 设计态"));
  resize(1600, 940);
  {
    const QByteArray sz = qgetenv("SIEANS_QT_WINDOW_SIZE");
    if (!sz.isEmpty()) {
      const QString s = QString::fromUtf8(sz);
      const int x = s.indexOf(QLatin1Char('x'));
      const int w = x > 0 ? s.left(x).toInt() : 0;
      const int h = x > 0 ? s.mid(x + 1).toInt() : 0;
      if (w >= 800 && h >= 600) resize(w, h);
    }
  }

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
  connect(comm_hub_, &CommHub::payloadReceived, this,
          [this](const QString&, const QString& payload) {
            fireStringTrigger(payload, QStringLiteral("通信收数"));
          });

  buildUi();
  buildMenus();
  buildToolbar();

  showStatus(QStringLiteral("就绪 · native %1 · GenTL %2")
                 .arg(QString::fromStdString(sieans::native_version()))
                 .arg(sieans::GenTLCapture::available() ? QStringLiteral("可用")
                                                        : QStringLiteral("桩/不可用")));

  const QByteArray projEnv = qgetenv("SIEANS_QT_PROJECT");
  const QString proj =
      !projEnv.isEmpty() ? QString::fromUtf8(projEnv)
                         : defaultProjectsDir() + QStringLiteral("/open-and-run-gentl-qr.sieans");
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
  markProjectClean();
  maybeLoadOpenAndRunSample();

  {
    const QVariantMap serialReal =
        document_.commManager().value(QStringLiteral("serialReal")).toMap();
    const bool wantPty = serialReal.value(QStringLiteral("autoStart"), false).toBool() ||
                         qgetenv("SIEANS_QT_FORCE_SEED") == "1";
    if (wantPty) {
      QString ptyErr;
      if (serialPtyLoopback().start(&ptyErr)) {
        logResult(QStringLiteral("SerialLoopback PTY: %1")
                      .arg(serialPtyLoopback().slavePath()));
      } else {
        logResult(QStringLiteral("SerialLoopback PTY 启动失败: %1").arg(ptyErr));
      }
    }
  }

  {
    const QVariantMap mb =
        document_.commManager().value(QStringLiteral("modbusReal")).toMap();
    const bool want = mb.value(QStringLiteral("autoStart"), false).toBool() ||
                      qgetenv("SIEANS_QT_FORCE_SEED") == "1";
    if (want) {
      int base = mb.value(QStringLiteral("port"), 1502).toInt();
      if (base <= 0) base = 1502;
      QString mbErr;
      bool ok = false;
      for (int d = 0; d <= 4; ++d) {
        QString e;
        if (modbusSoftServer().start(quint16(base + d), &e)) {
          logResult(QStringLiteral("ModbusTcpLoopback: %1")
                        .arg(modbusSoftServer().endpoint()));
          ok = true;
          break;
        }
        mbErr = e;
      }
      if (!ok)
        logResult(QStringLiteral("ModbusTcpLoopback 启动失败: %1").arg(mbErr));
      QString rtuErr;
      if (modbusRtuPeer().start(&rtuErr)) {
        logResult(QStringLiteral("ModbusRtuLoopback PTY: %1")
                      .arg(modbusRtuPeer().slavePath()));
      } else {
        logResult(QStringLiteral("ModbusRtuLoopback 启动失败: %1").arg(rtuErr));
      }
    }
  }

  {
    const QVariantMap s7 =
        document_.commManager().value(QStringLiteral("s7Real")).toMap();
    const bool want = s7.value(QStringLiteral("autoStart"), false).toBool() ||
                      qgetenv("SIEANS_QT_FORCE_SEED") == "1";
    if (want) {
      int base = s7.value(QStringLiteral("port"), 1102).toInt();
      if (base <= 0) base = 1102;
      QString s7Err;
      bool ok = false;
      for (int d = 0; d <= 4; ++d) {
        QString e;
        if (s7SoftServer().start(quint16(base + d), &e)) {
          logResult(QStringLiteral("S7TcpLoopback: %1").arg(s7SoftServer().endpoint()));
          ok = true;
          break;
        }
        s7Err = e;
      }
      if (!ok) logResult(QStringLiteral("S7TcpLoopback 启动失败: %1").arg(s7Err));
    }
  }

  {
    const QVariantMap opc =
        document_.commManager().value(QStringLiteral("opcuaReal")).toMap();
    const bool want = opc.value(QStringLiteral("autoStart"), false).toBool() ||
                      qgetenv("SIEANS_QT_FORCE_SEED") == "1";
    if (want) {
      int base = opc.value(QStringLiteral("port"), 4840).toInt();
      if (base <= 0) base = 4840;
      QString opcErr;
      bool ok = false;
      for (int d = 0; d <= 4; ++d) {
        QString e;
        if (opcUaSoftServer().start(quint16(base + d), &e)) {
          logResult(QStringLiteral("OpcUaLoopback: %1").arg(opcUaSoftServer().endpoint()));
          ok = true;
          break;
        }
        opcErr = e;
      }
      if (!ok) logResult(QStringLiteral("OpcUaLoopback 启动失败: %1").arg(opcErr));
    }
  }

  {
    const QVariantMap mqtt =
        document_.commManager().value(QStringLiteral("mqttReal")).toMap();
    const bool want = mqtt.value(QStringLiteral("autoStart"), false).toBool() ||
                      qgetenv("SIEANS_QT_FORCE_SEED") == "1";
    if (want) {
      int base = mqtt.value(QStringLiteral("port"), 1883).toInt();
      if (base <= 0) base = 1883;
      QString mqttErr;
      bool ok = false;
      for (int d = 0; d <= 4; ++d) {
        QString e;
        if (mqttSoftBroker().start(quint16(base + d), &e)) {
          logResult(QStringLiteral("MqttLoopback: %1").arg(mqttSoftBroker().endpoint()));
          ok = true;
          break;
        }
        mqttErr = e;
      }
      if (!ok) logResult(QStringLiteral("MqttLoopback 启动失败: %1").arg(mqttErr));
    }
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
  return workbenchProjectsDir();
}

QString MainWindow::samplePathCandidates() const {
  const QString hit = workbenchFirstExistingSampleQr();
  if (!hit.isEmpty()) return hit;
  const QString art = workbenchArtifactsDir() + QStringLiteral("/qr-t238-grab0.png");
  if (QFileInfo::exists(art)) return art;
  return {};
}

void MainWindow::buildUi() {
  // VisionMaster / industrial workbench layout:
  // vertical: [horizontal workbench] / [bottom results tabs]
  // horizontal: [rail|toolbox] | [flow tabs+canvas] | [image tabs+filmstrip]
  // property = light float (VM 属性浮窗), not embedded under canvas
  auto* central = new QWidget(this);
  auto* rootSplit = new QSplitter(Qt::Vertical);
  rootSplit->setObjectName(QStringLiteral("rootSplit"));
  root_split_ = rootSplit;
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
  connect(flow_tabs_, &FlowTabBar::allFlowsRequested, this, &MainWindow::onOpenSubflowManager);
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
  connect(flow_tabs_, &FlowTabBar::flowActivated, this, [this](const QString& id) {
    if (id.isEmpty() || id == document_.activeFlowId()) return;
    if (!document_.activateFlow(id)) {
      showStatus(QStringLiteral("切换流程失败"));
      return;
    }
    applyDocumentToUi();
    QString name;
    if (const FlowDef* f = document_.findFlow(id)) name = f->name;
    showStatus(QStringLiteral("当前流程：%1").arg(name.isEmpty() ? id : name));
  });
  connect(flow_tabs_, &FlowTabBar::addFlowRequested, this, [this]() {
    const FlowDef added = document_.addFlow();
    document_.activateFlow(added.id);
    applyDocumentToUi();
    markProjectDirty();
    showStatus(QStringLiteral("已新建流程：%1").arg(added.name));
  });
  connect(flow_tabs_, &FlowTabBar::renameFlowRequested, this, [this](const QString& id) {
    const FlowDef* cur = document_.findFlow(id);
    if (!cur) return;
    if (workbenchIsHeadless()) return;
    bool ok = false;
    const QString name = QInputDialog::getText(
        this, QStringLiteral("重命名流程"), QStringLiteral("流程名称"),
        QLineEdit::Normal, cur->name, &ok);
    if (!ok) return;
    if (!document_.renameFlow(id, name)) return;
    applyDocumentToUi();
    markProjectDirty();
  });
  connect(flow_tabs_, &FlowTabBar::duplicateFlowRequested, this, [this](const QString& id) {
    QString err;
    const FlowDef copy = document_.duplicateFlow(id, &err);
    if (copy.id.isEmpty()) {
      showStatus(err.isEmpty() ? QStringLiteral("复制流程失败") : err);
      return;
    }
    document_.activateFlow(copy.id);
    applyDocumentToUi();
    markProjectDirty();
    showStatus(QStringLiteral("已复制流程：%1").arg(copy.name));
  });
  connect(flow_tabs_, &FlowTabBar::removeFlowRequested, this, [this](const QString& id) {
    QString err;
    if (!document_.removeFlow(id, &err)) {
      showStatus(err.isEmpty() ? QStringLiteral("删除流程失败") : err);
      return;
    }
    applyDocumentToUi();
    markProjectDirty();
    showStatus(QStringLiteral("已删除流程"));
  });
  horizontal->addWidget(flowPane);

  connect(flow_scene_, &FlowScene::nodeSelected, this, &MainWindow::onNodeSelected);
  connect(flow_scene_, &FlowScene::edgeConnected, this, &MainWindow::onEdgeConnected);
  connect(flow_scene_, &FlowScene::edgeWhenChanged, this, &MainWindow::onEdgeWhenChanged);
  connect(flow_scene_, &FlowScene::nodeMoved, this, [this](const QString&, const QPointF&) {
    markProjectDirty();
  });
  connect(flow_scene_, &FlowScene::nodeMoveFinished, this, [this](const QString&, const QPointF&) {
    commitCanvasUndo(QStringLiteral("移动模块"));
    markProjectDirty();
  });
  connect(flow_scene_, &FlowScene::edgeRemoved, this, [this](const QString&) {
    commitCanvasUndo(QStringLiteral("删除连线"));
    markProjectDirty();
  });
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
    commitCanvasUndo(QStringLiteral("重命名模块"));
    markProjectDirty();
  });

  // Property float (VM light panel) — created lazily-ish but keep ready
  prop_float_ = new PropertyFloat(this);
  prop_panel_ = prop_float_->panel();
  connect(prop_float_, &PropertyFloat::paramEdited, this, &MainWindow::onParamEdited);
  connect(prop_float_, &PropertyFloat::structuredParamEdited, this,
          &MainWindow::onStructuredParamEdited);
  connect(prop_float_, &PropertyFloat::sparkJumpRequested, this,
          &MainWindow::onSparkFilmstripJump);
  connect(prop_float_, &PropertyFloat::runModule, this, &MainWindow::onRunOnce);
  connect(prop_float_, &PropertyFloat::runModuleContinuous, this,
          &MainWindow::onRunContinuous);
  connect(prop_float_, &PropertyFloat::chromeGeometryChanged, this,
          [this](const QRect& g) { document_.setPropertyFloatGeometry(g); });
  connect(prop_float_, &PropertyFloat::paramsReverted, this,
          &MainWindow::onParamsReverted);
  if (prop_float_ && prop_float_->locatePanel()) {
    connect(prop_float_->locatePanel(), &LocateMatchPanel::createTemplateRequested, this,
            [this]() {
              if (!prop_float_ || !prop_float_->locatePanel()) return;
              QImage frame = image_view_ ? image_view_->currentImage() : QImage();
              if (frame.isNull() && cam_worker_) frame = cam_worker_->latestFrame();
              QString err;
              if (!prop_float_->locatePanel()->createTemplateFromImage(frame, &err)) {
                showStatus(err.isEmpty() ? QStringLiteral("创建模板失败") : err, 2500);
                return;
              }
              showStatus(QStringLiteral("已创建模板"), 2000);
            });
  }

  // —— Right: image tabs + host strip + filmstrip ——
  auto* imagePane = new QWidget;
  imagePane->setObjectName(QStringLiteral("imagePane"));
  auto* imgRow = new QHBoxLayout(imagePane);
  imgRow->setContentsMargins(0, 0, 0, 0);
  imgRow->setSpacing(0);
  auto* imageCol = new QWidget;
  auto* imgLay = new QVBoxLayout(imageCol);
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
  connect(image_view_, &ImageView::roiEdited, this, &MainWindow::applyCanvasRoi);
  connect(image_view_, &ImageView::roiCleared, this, &MainWindow::onClearSelectedRoi);
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
    // Runtime-only chip edits persist the visible key list but do not rewrite
    // saved pin groups or mark the live seed dirty.
    document_.setHostWatchKeys(keys);
    if (var_watch_) var_watch_->setWatchKeys(keys);
    showStatus(QStringLiteral("监视键 %1").arg(keys.join(QLatin1Char(','))));
    logResult(QStringLiteral("Host 监视键 → %1").arg(keys.join(QLatin1Char(','))));
  });
  connect(host_strip_, &HostStrip::pinGroupPicked, this, &MainWindow::applyHostPinGroup);
  connect(host_strip_, &HostStrip::openVarWatchRequested, this, [this]() {
    if (var_watch_ && bottom_tabs_) {
      bottom_tabs_->setCurrentWidget(var_watch_);
      var_watch_->setFocus(Qt::OtherFocusReason);
      showStatus(QStringLiteral("变量监视"));
    }
  });
  connect(host_strip_, &HostStrip::openHostRequested, this, [this]() {
    if (host_sm_) {
      if (bottom_tabs_) bottom_tabs_->setCurrentWidget(host_sm_);
      host_sm_->setFocus(Qt::OtherFocusReason);
      host_sm_->raise();
      showStatus(QStringLiteral("Host 面板"));
    }
  });
      connect(host_strip_, &HostStrip::stopRequested, this, &MainWindow::onStopRun);
  connect(host_strip_, &HostStrip::clearAlarmRequested, this, [this]() {
    if (host_strip_) host_strip_->setAlarm(false);
    document_.setAlarmLatched(false);
    if (host_sm_) {
      document_.setAlarmHistory(host_sm_->alarmHistoryLines());
      document_.setRecipeLocked(run_mode_);
      if (continuous_run_ && !run_paused_)
        host_sm_->applyState(QStringLiteral("Running"));
      else if (run_paused_)
        host_sm_->applyState(QStringLiteral("Paused"));
      else
        host_sm_->applyState(QStringLiteral("Idle"));
    }
    publishHostToFlowVars();
    applyFlowIoBindings();
    if (var_watch_) var_watch_->setVariables(flow_vars_);
    if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
    showStatus(QStringLiteral("报警已清除 · 锁存已写回"));
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
  imgRow->addWidget(imageCol, 1);
  compare_strip_ = new CompareStrip;
  compare_strip_->loadComparePrefs();
  imgRow->addWidget(compare_strip_, 0);
  connect(compare_strip_, &CompareStrip::pathActivated, this, [this](const QString& path) {
    if (!filmstrip_ || path.isEmpty()) return;
    QVariantMap bag;
    bag.insert(QStringLiteral("frame"), path);
    const QVariantMap hit = FilmstripBar::seekFromSparkJump(filmstrip_, bag, true);
    if (hit.value(QStringLiteral("ok")).toBool())
      showStatus(QStringLiteral("对比焦点 · %1").arg(QFileInfo(path).fileName()));
    refreshGeomCompareOverlays();
  });
  connect(compare_strip_, &CompareStrip::clearRequested, this, [this]() {
    result_compare_paths_.clear();
    refreshGeomCompareOverlays();
    showStatus(QStringLiteral("对比已清除"));
  });
  connect(compare_strip_, &CompareStrip::pathsReordered, this, [this](const QStringList&) {
    // Runtime-only order; color-cycled overlays follow the new strip order.
    refreshGeomCompareOverlays();
  });
  connect(filmstrip_, &FilmstripBar::addImagesRequested, this, [this]() {
    const QString path = QFileDialog::getOpenFileName(
        this, QStringLiteral("添加图像"),
        workbenchArtifactsDir(),
        QStringLiteral("图像文件 (*.bmp *.jpeg *.jpg *.png *.tif *.tiff)"));
    if (!path.isEmpty() && filmstrip_) filmstrip_->addPaths({path});
  });
  connect(filmstrip_, &FilmstripBar::addFolderRequested, this, [this]() {
    const QString dir = QFileDialog::getExistingDirectory(
        this, QStringLiteral("添加图像文件夹"),
        workbenchArtifactsDir());
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
            if (!applying_document_) focusFilmstripResult(path);
            refreshGeomCompareOverlays();
          });
  connect(filmstrip_, &FilmstripBar::runAllRequested, this, &MainWindow::onRunAllImages);
  connect(filmstrip_, &FilmstripBar::pathsChanged, this, [this]() {
    if (!filmstrip_ || applying_document_) return;
    document_.setFilmstripPaths(filmstrip_->paths());
    document_.setFilmstripIndex(filmstrip_->index());
    markProjectDirty();
  });
  connect(filmstrip_, &FilmstripBar::autoSwitchChanged, this, [this](bool on) {
    if (applying_document_) return;
    document_.setFilmstripAutoSwitch(on);
    markProjectDirty();
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
  // 值列吃剩余宽度，类型列按内容收紧；避免 StretchLast 把「类型」顶到最右而值被省略。
  {
    auto* hdr = result_table_->horizontalHeader();
    hdr->setStretchLastSection(false);
    hdr->setDefaultAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    hdr->setSectionResizeMode(0, QHeaderView::ResizeToContents);
    hdr->setSectionResizeMode(1, QHeaderView::Stretch);
    hdr->setSectionResizeMode(2, QHeaderView::ResizeToContents);
  }
  result_table_->setTextElideMode(Qt::ElideRight);
  result_table_->verticalHeader()->setVisible(false);
  result_table_->setAlternatingRowColors(true);
  result_table_->setSelectionBehavior(QAbstractItemView::SelectRows);
  result_table_->setEditTriggers(QAbstractItemView::NoEditTriggers);
  result_table_->setObjectName(QStringLiteral("resultTree"));
  result_table_->setToolTip(QStringLiteral("当前结果 · Ctrl+C 选中 · Ctrl+Shift+C 可见全部 · Ctrl+Shift+J JSON · Home/End/Pg · 过滤 Ctrl+Shift+F"));
  result_table_->setStatusTip(QStringLiteral("结果表 · Ctrl+C/Ctrl+Shift+C/J · Home/End/Pg · 过滤 Ctrl+Shift+F · 单击定位胶片"));
  connect(result_table_, &QTableWidget::cellClicked, this, [this](int row, int) {
    if (!result_table_ || row < 0) return;
    auto* it = result_table_->item(row, 0);
    if (!it) return;
    const QString path = it->data(Qt::UserRole).toString();
    const int idx = it->data(Qt::UserRole + 1).toInt();
    const QString nodeId = it->data(Qt::UserRole + 2).toString();
    if (filmstrip_) {
      QVariantMap bag;
      bag.insert(QStringLiteral("frame"), path);
      if (idx >= 0) bag.insert(QStringLiteral("index"), idx);
      const QVariantMap hit = FilmstripBar::seekFromSparkJump(filmstrip_, bag, true);
      if (hit.value(QStringLiteral("ok")).toBool())
        showStatus(QStringLiteral("结果表定位胶片 · #%1")
                       .arg(hit.value(QStringLiteral("index")).toInt() + 1));
    }
    if (!nodeId.isEmpty() && flow_scene_) flow_scene_->selectNode(nodeId);
  });
  connect(result_table_, &QTableWidget::cellDoubleClicked, this, [this](int row, int) {
    if (!result_table_ || row < 0) return;
    auto* it = result_table_->item(row, 0);
    if (!it) return;
    QString path = it->data(Qt::UserRole).toString();
    const int idx = it->data(Qt::UserRole + 1).toInt();
    if (path.isEmpty() && filmstrip_ && idx >= 0 && idx < filmstrip_->count())
      path = filmstrip_->paths().value(idx);
    if (path.isEmpty() && filmstrip_) path = filmstrip_->currentPath();
    applyResultCompare(path);
  });
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
  result_log_->setMaximumBlockCount(2000);  // UI 文档也有界，不能只裁剪 resultLogAll_。
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
    // Toggle is a runtime watch edit: update chips, do not rewrite pin groups or dirty.
    document_.setHostWatchKeys(keys);
    if (host_strip_) {
      host_strip_->setWatchKeys(keys);
      host_strip_->updateFromVars(flow_vars_);
    }
    if (var_watch_) var_watch_->setWatchKeys(keys);
    showStatus(QStringLiteral("Host 监视 %1 %2")
                   .arg(keys.contains(key) ? QStringLiteral("＋") : QStringLiteral("－"), key));
  });
  connect(var_watch_, &VarWatchPanel::pinGroupChanged, this, &MainWindow::applyHostPinGroup);
  connect(var_watch_, &VarWatchPanel::pinGroupSaveRequested, this, [this]() {
    if (applying_document_) return;
    QStringList keys = document_.hostWatchKeys();
    if (host_strip_ && !host_strip_->watchChipsText().isEmpty() && !keys.isEmpty()) {
      // keep document keys; HostStrip may have a runtime overlay already written
    }
    QString n = document_.activePinGroup();
    if (n.isEmpty()) n = QStringLiteral("默认");
    document_.ensurePinGroup(n, keys);
    document_.activatePinGroup(n);
    if (host_strip_) {
      host_strip_->setWatchKeys(document_.hostWatchKeys());
      host_strip_->updateFromVars(flow_vars_);
    }
    if (var_watch_) var_watch_->setWatchKeys(document_.hostWatchKeys());
    syncHostPinGroups();
    markProjectDirty();
    showStatus(QStringLiteral("已存钉组 %1 · %2 键").arg(n).arg(keys.size()));
  });
  connect(var_watch_, &VarWatchPanel::pinGroupNewRequested, this, [this](const QString& name) {
    if (applying_document_ || name.trimmed().isEmpty()) return;
    const QStringList keys = document_.hostWatchKeys();
    document_.ensurePinGroup(name, keys);
    applyHostPinGroup(name);
    showStatus(QStringLiteral("已建钉组 %1 · %2 键").arg(document_.activePinGroup()).arg(keys.size()));
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
    publishHostToFlowVars();
    applyFlowIoBindings();
    syncVarsToUi(false);
    showStatus(QStringLiteral("上位机模式 → %1 · I/O/vars 已共更").arg(mode), 2500);
  });
  connect(host_sm_, &HostStatePanel::alarmPolicyChanged, this, [this](const QString& pol) {
    document_.setAlarmPolicy(pol);
    // Policy change co-writes with recipe-lock snapshot.
    document_.setRecipeLocked(run_mode_);
    if (host_sm_) document_.setAlarmHistory(host_sm_->alarmHistoryLines());
    publishHostToFlowVars();
    applyFlowIoBindings();
    syncVarsToUi(false);
  });
  connect(host_sm_, &HostStatePanel::alarmHistoryChanged, this, [this](const QStringList& lines) {
    document_.setAlarmHistory(lines);
    document_.setRecipeLocked(run_mode_);
    // Derive latch from newest hist line (ALARM vs 清除).
    bool latched = false;
    QString reason;
    for (const QString& line : lines) {
      if (line.contains(QStringLiteral("  清除  "))) break;
      const int p = line.indexOf(QStringLiteral("  ALARM  "));
      if (p >= 0) {
        latched = true;
        reason = line.mid(p + 9).trimmed();
        break;
      }
    }
    if (host_sm_ && host_sm_->state() == QLatin1String("Alarm")) latched = true;
    if (!latched && host_strip_ && host_strip_->alarmOn()) latched = true;
    document_.setAlarmLatched(latched, reason);
    publishHostToFlowVars();
    applyFlowIoBindings();
    if (var_watch_) var_watch_->setVariables(flow_vars_);
    if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
  });
  connect(host_sm_, &HostStatePanel::clearAlarmRequested, this, [this]() {
    if (host_strip_) host_strip_->setAlarm(false);
    document_.setAlarmLatched(false);
    if (host_sm_) {
      document_.setAlarmHistory(host_sm_->alarmHistoryLines());
      document_.setRecipeLocked(run_mode_);
    }
    publishHostToFlowVars();
    applyFlowIoBindings();
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
  status_config_->setStyleSheet(QStringLiteral("color:#3ecf8e;padding:0 8px;"));
  statusBar()->addPermanentWidget(status_config_);
  status_timing_ = new QLabel(QStringLiteral("流程 — ms · 工具 — ms · 算法 — ms"));
  status_timing_->setStyleSheet(QStringLiteral("color:#a8a8a8;padding:0 8px;"));
  statusBar()->addPermanentWidget(status_timing_);
  status_busy_ = new QLabel(QStringLiteral("● 空闲"));
  status_busy_->setStyleSheet(QStringLiteral("color:#2d9b6c;padding:0 8px;"));
  statusBar()->addPermanentWidget(status_busy_);
  status_backend_ = new QLabel(
      QStringLiteral("SIEANS Vision · %1")
          .arg(QString::fromStdString(sieans::native_version())));
  status_backend_->setStyleSheet(QStringLiteral("color:#787878;padding:0 8px;"));
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
  recent_menu_ = files->addMenu(QStringLiteral("最近打开"));
  rebuildRecentMenu();
  files->addAction(QStringLiteral("导出当前流程（.prc）…"), this,
                   &MainWindow::onExportCurrentFlow);
  files->addAction(QStringLiteral("导入流程（.prc）…"), this, &MainWindow::onImportFlow);
  files->addSeparator();
  files->addAction(QStringLiteral("打开图像…"), this, &MainWindow::onOpenImage);
  files->addAction(QStringLiteral("加载示例 QR"), this, &MainWindow::onLoadSample);
  files->addSeparator();
  files->addAction(QStringLiteral("退出"), qApp, &QApplication::quit, QKeySequence::Quit);

  auto* settings = menuBar()->addMenu(QStringLiteral("设置"));
  settings->addAction(QStringLiteral("通信管理…"), this, &MainWindow::onOpenCommManager);
  settings->addAction(QStringLiteral("全局触发…"), this, &MainWindow::onOpenGlobalTriggers);
  settings->addAction(QStringLiteral("流程 I/O 绑定…"), this, &MainWindow::onOpenFlowIo);
  settings->addAction(QStringLiteral("子流程管理…"), this, &MainWindow::onOpenSubflowManager);

  auto* tools = menuBar()->addMenu(QStringLiteral("工具"));
  tools->addAction(QStringLiteral("C++ QR 解码"), this, &MainWindow::onDecodeQr,
                   QKeySequence(Qt::Key_F9));
  tools->addAction(QStringLiteral("适应图像窗口"), image_view_, &ImageView::fitToView);
  tools->addAction(QStringLiteral("适应流程画布"), flow_view_, &FlowView::fitAll);
  tools->addAction(QStringLiteral("流程 I/O 绑定…"), this, &MainWindow::onOpenFlowIo);
  tools->addAction(QStringLiteral("子流程管理…"), this, &MainWindow::onOpenSubflowManager);
  tools->addAction(QStringLiteral("产线配方 / 换型…"), this, &MainWindow::onOpenRecipeSwitch);
  tools->addAction(QStringLiteral("全局触发…"), this, &MainWindow::onOpenGlobalTriggers);
  tools->addAction(QStringLiteral("注入RUN"), this, &MainWindow::injectRunTrigger);
  tools->addAction(QStringLiteral("注入STOP"), this, &MainWindow::injectStopTrigger);

  auto* system = menuBar()->addMenu(QStringLiteral("系统"));
  auto* edit = system->addMenu(QStringLiteral("编辑"));
  act_undo_ = edit->addAction(QStringLiteral("撤销"), this, &MainWindow::undoCanvasEdit);
  act_undo_->setShortcut(QKeySequence::Undo);
  act_undo_->setShortcutContext(Qt::WindowShortcut);
  act_redo_ = edit->addAction(QStringLiteral("重做"), this, &MainWindow::redoCanvasEdit);
  act_redo_->setShortcuts({QKeySequence::Redo, QKeySequence(QStringLiteral("Ctrl+Y"))});
  act_redo_->setShortcutContext(Qt::WindowShortcut);
  updateCanvasUndoActions();
  edit->addSeparator();
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
    commitCanvasUndo(QStringLiteral("删除模块"));
    markProjectDirty();
  });
  edit->addAction(QStringLiteral("删除选中连线"), this, [this]() {
    flow_scene_->removeSelectedEdge();
  });
  auto* view = system->addMenu(QStringLiteral("视图"));
  view->addAction(QStringLiteral("适应图像窗口"), image_view_, &ImageView::fitToView);
  view->addAction(QStringLiteral("适应流程画布"), flow_view_, &FlowView::fitAll);
  roi_action_ = view->addAction(QStringLiteral("框选所选模块 ROI"));
  roi_action_->setCheckable(true);
  roi_action_->setToolTip(QStringLiteral("在全局图像上绘制 / 拖动 / 缩放所选算子的 ROI"));
  connect(roi_action_, &QAction::toggled, this, [this](bool on) {
    if (roi_action_ && roi_action_->isChecked() != on) return;
    onToggleRoiMode();
  });
  view->addAction(QStringLiteral("清除所选模块 ROI"), this, &MainWindow::onClearSelectedRoi);

  auto* work = menuBar()->addMenu(QStringLiteral("工程管理"));
  work->addAction(QStringLiteral("产线配方 / 换型…"), this, &MainWindow::onOpenRecipeSwitch);
  work->addAction(QStringLiteral("工程库换型…"), this, &MainWindow::onLoadRecipeLibrary);
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
  devices->addAction(QStringLiteral("导入点云…"), this, &MainWindow::onImportPointCloud);
  devices->addAction(QStringLiteral("设置参考点云…"), this, &MainWindow::onImportCloudTarget);

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
  records->addAction(QStringLiteral("检测历史…"), this, &MainWindow::onOpenInspectionHistory);
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
  {
    auto* a = tb->addAction(QStringLiteral("子流程"), this, &MainWindow::onOpenSubflowManager);
    a->setToolTip(QStringLiteral("子流程管理 · 定义可复用流程并给循环调用"));
  }
  variant_chip_ = new QComboBox;
  variant_chip_->setObjectName(QStringLiteral("recipeVariantChip"));
  variant_chip_->setMinimumWidth(88);
  variant_chip_->setMaximumWidth(140);
  variant_chip_->setToolTip(QStringLiteral("按产品变体一键套用本方案配方（带回滚）"));
  variant_chip_->addItem(QStringLiteral("变体·—"), QString());
  connect(variant_chip_, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
          &MainWindow::onVariantChipChanged);
  tb->addWidget(variant_chip_);
  act_preview_ = tb->addAction(QStringLiteral("连续预览"), this,
                               &MainWindow::onStartContinuousPreview);
  act_preview_->setToolTip(QStringLiteral("连续采集预览 · Soft/UVC/GenTL · 不跑流程"));
  act_preview_->setStatusTip(QStringLiteral("预览 · 连续采集"));
  act_preview_stop_ =
      tb->addAction(QStringLiteral("停预览"), this, &MainWindow::onStopContinuousPreview);
  act_preview_stop_->setToolTip(QStringLiteral("停止连续采集预览 · 不影响流程运行态"));
  act_preview_stop_->setStatusTip(QStringLiteral("预览 · 停止"));
  tb->addSeparator();
  tb->addAction(QStringLiteral("注入RUN"), this, &MainWindow::injectRunTrigger)
      ->setToolTip(QStringLiteral("向字符串触发注入 RUN（软通信环回，无真 PLC）"));
  tb->addAction(QStringLiteral("注入STOP"), this, &MainWindow::injectStopTrigger)
      ->setToolTip(QStringLiteral("向字符串触发注入 STOP（软通信环回，无真 PLC）"));
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
  applying_document_ = true;
  flow_scene_->loadDocument(&document_);
  run_mode_ = document_.recipeLocked();
  if (flow_scene_) flow_scene_->setEditingLocked(run_mode_);
  refreshProjectTitle();
  if (flow_tabs_) {
    document_.ensureScheme();
    QVector<QPair<QString, QString>> tabs;
    QString activeName = QStringLiteral("流程1");
    for (const FlowDef& f : document_.flows()) {
      tabs.append({f.id, f.name});
      if (f.id == document_.activeFlowId()) activeName = f.name;
    }
    flow_tabs_->setFlows(tabs, document_.activeFlowId());
    flow_tabs_->setFlowName(activeName);
  }
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
  if (host_strip_) {
    const QString act = document_.activePinGroup();
    const QStringList groupKeys =
        act.isEmpty() ? QStringList() : document_.pinGroupKeys(act);
    // 打开方案时优先显示当前钉组，避免历史膨胀的 watchKeys 淹没 Host 条。
    host_strip_->setWatchKeys(!groupKeys.isEmpty() ? groupKeys
                                                   : document_.hostWatchKeys());
    host_strip_->updateFromVars(flow_vars_);
  }
  syncHostPinGroups();
  result_compare_paths_.clear();
  if (compare_strip_) compare_strip_->clear();
  filmstrip_geom_cache_.clear();
  filmstrip_measure_badges_.clear();
  last_run_film_path_.clear();
  if (filmstrip_) filmstrip_->clearFrameMeasureBadges();
  if (output_view_) output_view_->clearGeomOverlays();
  if (image_view_) image_view_->clearGeomOverlays();
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
      host_sm_->setRecipeLocked(run_mode_);
      if (host_strip_) host_strip_->setRecipeLocked(run_mode_);
      if (document_.alarmLatched()) {
        QString why = document_.alarmLatchReason();
        if (why.isEmpty()) why = host_sm_->lastAlarmReason();
        if (why.isEmpty()) why = QStringLiteral("方案锁存报警");
        host_sm_->applyState(QStringLiteral("Alarm"));
        if (host_strip_) host_strip_->setAlarm(true, why);
      }
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
  applying_document_ = false;
  refreshProjectTitle();
  syncCanvasRoiFromSelection();
  updateCanvasUndoActions();
  refreshVariantChip();
}

void MainWindow::syncVarsToUi(bool hostEvaluated) {
  if (host_strip_) {
    if (hostEvaluated) {
      host_strip_->updateFromVars(
          flow_vars_, flow_vars_.value(QStringLiteral("barcodeCount")).toInt(), true);
    } else {
      host_strip_->updateFromVars(flow_vars_);
    }
  }
  publishHostToFlowVars();
  applyFlowIoBindings();
  document_.setVariables(flow_vars_);
  if (var_watch_) var_watch_->setVariables(flow_vars_);
  if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
  if (host_sm_ && host_strip_)
    host_sm_->setRunStats(host_strip_->okStreak(), host_strip_->ngCount(), last_cycle_ms_);
  if (hostEvaluated && host_strip_) {
    const QString tag = host_strip_->lastResult();
    if (tag == QLatin1String("OK") || tag == QLatin1String("NG") ||
        tag == QLatin1String("ALARM"))
      fireHostCommEvents(tag);
  }
}

void MainWindow::publishHostToFlowVars() {
  const QString mode =
      host_sm_ ? host_sm_->hostMode() : document_.hostMode();
  QString state = QStringLiteral("Idle");
  if (host_sm_ && !host_sm_->state().isEmpty())
    state = host_sm_->state();
  else if (host_strip_)
    state = host_strip_->hostState();
  const int ok = host_strip_ ? host_strip_->okStreak() : 0;
  const int ng = host_strip_ ? host_strip_->ngCount() : 0;
  const int total = ok + ng;
  const double yld = total > 0 ? (100.0 * ok / total) : 0.0;
  const bool alarm = host_strip_ && host_strip_->alarmOn();
  QString result = QStringLiteral("—");
  if (alarm)
    result = QStringLiteral("ALARM");
  else if (host_strip_)
    result = host_strip_->lastResult();

  flow_vars_.insert(QStringLiteral("host.mode"), mode);
  flow_vars_.insert(QStringLiteral("host.state"), state);
  flow_vars_.insert(QStringLiteral("host.result"), result);
  flow_vars_.insert(QStringLiteral("host.okStreak"), ok);
  flow_vars_.insert(QStringLiteral("host.ngCount"), ng);
  flow_vars_.insert(QStringLiteral("host.yield"), yld);
  flow_vars_.insert(QStringLiteral("host.lastMs"), last_cycle_ms_);
  flow_vars_.insert(QStringLiteral("host.alarm"), alarm ? 1 : 0);
  flow_vars_.insert(QStringLiteral("host.cycle"), run_cycle_);
  // Flat aliases — Comm ${flow.hostResult} / I/O binding tokens
  flow_vars_.insert(QStringLiteral("hostMode"), mode);
  flow_vars_.insert(QStringLiteral("hostState"), state);
  flow_vars_.insert(QStringLiteral("hostResult"), result);
  flow_vars_.insert(QStringLiteral("hostOkStreak"), ok);
  flow_vars_.insert(QStringLiteral("hostNgCount"), ng);
  flow_vars_.insert(QStringLiteral("hostYield"), yld);
  flow_vars_.insert(QStringLiteral("hostAlarm"), alarm ? 1 : 0);
  flow_vars_.insert(QStringLiteral("hostLastMs"), last_cycle_ms_);
  flow_vars_.insert(QStringLiteral("hostCycle"), run_cycle_);
  const int histN = host_sm_ ? host_sm_->alarmCount() : 0;
  const QString alarmLast =
      host_sm_ ? host_sm_->lastAlarmReason()
               : document_.alarmLatchReason();
  const bool latched = alarm || document_.alarmLatched() ||
                       (host_sm_ && host_sm_->state() == QLatin1String("Alarm"));
  flow_vars_.insert(QStringLiteral("recipeLocked"), run_mode_ ? 1 : 0);
  flow_vars_.insert(QStringLiteral("host.recipeLocked"), run_mode_ ? 1 : 0);
  flow_vars_.insert(QStringLiteral("alarmHistCount"), histN);
  flow_vars_.insert(QStringLiteral("host.alarmHistCount"), histN);
  flow_vars_.insert(QStringLiteral("alarmLast"), alarmLast);
  flow_vars_.insert(QStringLiteral("host.alarmLast"), alarmLast);
  flow_vars_.insert(QStringLiteral("alarmLatched"), latched ? 1 : 0);
  flow_vars_.insert(QStringLiteral("host.alarmLatched"), latched ? 1 : 0);
}

void MainWindow::fireHostCommEvents(const QString& resultTag) {
  if (!comm_hub_ || resultTag.isEmpty() || resultTag == QLatin1String("—")) return;
  const QVariantList events =
      document_.commManager().value(QStringLiteral("sendEvents")).toList();
  if (events.isEmpty()) return;
  int n = 0;
  QStringList txDevices;
  for (const QVariant& evV : events) {
    const QVariantMap ev = evV.toMap();
    const QString onRaw =
        ev.value(QStringLiteral("on"),
                 ev.value(QStringLiteral("when"), QStringLiteral("always")))
            .toString();
    const QString on = onRaw.trimmed().toLower();
    bool match = on.isEmpty() || on == QLatin1String("always");
    if (!match) {
      if (resultTag == QLatin1String("OK") &&
          (on == QLatin1String("ok") || on == QLatin1String("pass")))
        match = true;
      else if (resultTag == QLatin1String("NG") &&
               (on == QLatin1String("ng") || on == QLatin1String("fail")))
        match = true;
      else if (resultTag == QLatin1String("ALARM") && on == QLatin1String("alarm"))
        match = true;
    }
    if (!match) continue;
    QString device = ev.value(QStringLiteral("device")).toString().trimmed();
    if (device.isEmpty()) device = QStringLiteral("LocalLoop");
    QString msg = ev.value(QStringLiteral("message")).toString();
    if (msg.isEmpty()) msg = ev.value(QStringLiteral("payload")).toString();
    if (msg.isEmpty()) continue;
    msg = CommHub::expandTemplate(msg, flow_vars_);
    QString err;
    if (!comm_hub_->sendPayload(device, msg, &err)) {
      if (!err.isEmpty())
        logResult(QStringLiteral("Host→Comm 失败 %1: %2").arg(device, err));
      continue;
    }
    ++n;
    if (!txDevices.contains(device)) txDevices << device;
    flow_vars_.insert(QStringLiteral("commPayload"), msg);
    flow_vars_.insert(QStringLiteral("host.lastTx"), msg);
    flow_vars_.insert(QStringLiteral("hostLastTx"), msg);
    flow_vars_.insert(QStringLiteral("hostLastTxDevice"), device);
  }
  if (n > 0) {
    flow_vars_.insert(QStringLiteral("hostTxDevices"),
                      txDevices.join(QLatin1Char(',')));
    flow_vars_.insert(QStringLiteral("host.txDevices"),
                      txDevices.join(QLatin1Char(',')));
    logResult(QStringLiteral("Host→Comm sendEvents ×%1 · %2 · %3")
                  .arg(n)
                  .arg(resultTag)
                  .arg(txDevices.join(QLatin1Char('+'))));
    if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
    if (var_watch_) var_watch_->setVariables(flow_vars_);
  }
}

void MainWindow::logResult(const QString& line) {
  if (line.contains(QStringLiteral("失败")) || line.contains(QStringLiteral("异常")) ||
      line.contains(QStringLiteral("不可用"))) {
    qWarning().noquote() << "workbench:" << line;
  } else {
    qInfo().noquote() << "workbench:" << line;
  }
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
  status_busy_->setText(busy ? QStringLiteral("● 忙碌") : QStringLiteral("● 空闲"));
  status_busy_->setStyleSheet(busy ? QStringLiteral("color:#d4a017;font-weight:600;padding:0 8px;")
                                   : QStringLiteral("color:#2d9b6c;padding:0 8px;"));
  updateRunChrome();
}


QVariant MainWindow::resolveIoBinding(const QString& binding) const {
  const QString imgHint =
      (image_view_ && !image_view_->currentImage().isNull())
          ? QStringLiteral("%1x%2")
                .arg(image_view_->currentImage().width())
                .arg(image_view_->currentImage().height())
          : QString();
  return CommHub::resolveBinding(binding, flow_vars_, document_.sourceConfig(), imgHint);
}

void MainWindow::applyFlowIoBindings() {
  const QVariantMap io = document_.flowIo();
  const QVariantList outs = io.value(QStringLiteral("outputs")).toList();
  for (const QVariant& rowV : outs) {
    const QVariantMap row = rowV.toMap();
    const QString name = row.value(QStringLiteral("name")).toString().trimmed();
    if (name.isEmpty()) continue;
    const QString binding = row.value(QStringLiteral("binding")).toString();
    const QString emptyDef = row.value(QStringLiteral("emptyDefault")).toString();
    const QString imgHint =
        (image_view_ && !image_view_->currentImage().isNull())
            ? QStringLiteral("%1x%2")
                  .arg(image_view_->currentImage().width())
                  .arg(image_view_->currentImage().height())
            : QString();
    QVariant val = CommHub::resolveBindingOrDefault(
        binding, emptyDef, flow_vars_, document_.sourceConfig(), imgHint);
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
  if (host_sm_) host_sm_->setRecipeLocked(run_mode_);
  const QString hostState = host_sm_ ? host_sm_->state() : QStringLiteral("Idle");
  if (host_strip_) {
    host_strip_->setRecipeLocked(run_mode_);
    host_strip_->setIntervalMs(document_.runIntervalMs() > 0 ? document_.runIntervalMs() : 200);
    host_strip_->setRunChrome(modeText, hostState, run_cycle_);
  }
  if (flow_tabs_) {
    flow_tabs_->setIntervalMs(document_.runIntervalMs() > 0 ? document_.runIntervalMs() : 200);
    flow_tabs_->setRunChrome(modeText, run_cycle_, last_cycle_ms_, continuous_run_,
                             run_paused_);
  }
  // Host run-mode co-update → flow_vars / I/O outputs (HostResult/HostState…)
  publishHostToFlowVars();
  applyFlowIoBindings();
  document_.setVariables(flow_vars_);
  if (var_watch_) var_watch_->setVariables(flow_vars_);
  if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
  refreshProjectTitle();
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
    if (host_sm_->state() != QLatin1String("Alarm"))
      document_.setAlarmLatched(false);
    document_.setAlarmHistory(host_sm_->alarmHistoryLines());
    document_.setRecipeLocked(run_mode_);
    if (continuous_run_ && !run_paused_ && host_sm_->state() != QLatin1String("Alarm"))
      host_sm_->applyState(QStringLiteral("Running"));
    publishHostToFlowVars();
    applyFlowIoBindings();
  } else {
    host_sm_->raiseAlarm(detail);
    if (host_strip_) host_strip_->setAlarm(true, detail);
    document_.setAlarmLatched(true, detail);
    document_.setAlarmHistory(host_sm_->alarmHistoryLines());
    document_.setRecipeLocked(run_mode_);
    publishHostToFlowVars();
    applyFlowIoBindings();
    // Worker/alarm path may not go through syncVarsToUi(true)
    fireHostCommEvents(QStringLiteral("ALARM"));
    document_.setVariables(flow_vars_);
    if (var_watch_) var_watch_->setVariables(flow_vars_);
    if (comm_panel_) comm_panel_->setFlowVars(flow_vars_);
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
        s.params.value(QStringLiteral("templatePath")).toString().isEmpty() &&
        s.params.value(QStringLiteral("templateSource")).toString() !=
            QLatin1String("soft_plate") &&
        s.params.value(QStringLiteral("templateSource")).toString() !=
            QLatin1String("soft_scene_plate")) {
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
  QHash<QString, int> indeg;
  for (const FlowStep& s : document_.steps()) indeg[s.id] = 0;
  for (const FlowEdge& e : document_.edges()) {
    if (e.from.isEmpty() || e.to.isEmpty()) continue;
    outs[e.from] << e.to;
    if (indeg.contains(e.to)) indeg[e.to] += 1;
  }
  QQueue<QString> q;
  q.enqueue(QStringLiteral("source"));
  for (const FlowStep& s : document_.steps()) {
    if (indeg.value(s.id, 0) == 0) q.enqueue(s.id);
  }
  while (!q.isEmpty()) {
    const QString id = q.dequeue();
    if (visited.contains(id)) continue;
    visited.insert(id);
    if (id != QLatin1String("source")) ordered << id;
    for (const QString& n : outs.value(id)) {
      if (!indeg.contains(n)) continue;
      indeg[n] -= 1;
      if (indeg[n] <= 0) q.enqueue(n);
    }
  }
  for (const FlowStep& s : document_.steps()) {
    if (!visited.contains(s.id)) ordered << s.id;
  }
  return ordered;
}

void MainWindow::syncHostPinGroups() {
  const QStringList names = document_.pinGroupNames();
  const QString active = document_.activePinGroup();
  if (host_strip_) host_strip_->setPinGroups(names, active);
  if (var_watch_) {
    QHash<QString, QStringList> keys;
    for (const QString& n : names) keys.insert(n, document_.pinGroupKeys(n));
    var_watch_->setPinGroups(names, keys, active);
  }
}

void MainWindow::applyHostPinGroup(const QString& name) {
  if (applying_document_ || name.trimmed().isEmpty()) return;
  document_.activatePinGroup(name);
  const QStringList keys = document_.hostWatchKeys();
  if (host_strip_) {
    host_strip_->setWatchKeys(keys);
    host_strip_->updateFromVars(flow_vars_);
  }
  if (var_watch_) var_watch_->setWatchKeys(keys);
  syncHostPinGroups();
  markProjectDirty();
  showStatus(QStringLiteral("钉组 %1 · %2 键").arg(document_.activePinGroup()).arg(keys.size()));
}

void MainWindow::applyResultCompare(const QString& path) {
  const QString p = path.trimmed();
  if (p.isEmpty()) {
    showStatus(QStringLiteral("对比叠层：无胶片路径"));
    return;
  }
  if (filmstrip_) {
    QVariantMap bag;
    bag.insert(QStringLiteral("frame"), p);
    FilmstripBar::seekFromSparkJump(filmstrip_, bag, true);
  }
  auto samePath = [](const QString& a, const QString& b) {
    if (a == b) return true;
    return QFileInfo(a).fileName() == QFileInfo(b).fileName() && !a.isEmpty() && !b.isEmpty();
  };
  if (result_compare_paths_.size() == 1 && samePath(result_compare_paths_.first(), p)) {
    result_compare_paths_.clear();
    if (compare_strip_) compare_strip_->clear();
    refreshGeomCompareOverlays();
    showStatus(QStringLiteral("再点清除对比 · %1").arg(QFileInfo(p).fileName()));
    return;
  }
  int have = -1;
  for (int i = 0; i < result_compare_paths_.size(); ++i) {
    if (samePath(result_compare_paths_.at(i), p)) {
      have = i;
      break;
    }
  }
  if (have >= 0) {
    if (compare_strip_) compare_strip_->activatePath(result_compare_paths_.at(have), false);
    refreshGeomCompareOverlays();
    showStatus(QStringLiteral("对比焦点 · %1").arg(QFileInfo(p).fileName()));
    return;
  }
  if (result_compare_paths_.size() >= 6) {
    showStatus(QStringLiteral("对比最多 6 帧"));
    return;
  }
  result_compare_paths_ << p;
  // Side rail appears at 2+ paths, matching PySide (single-frame hover does not pop it).
  if (compare_strip_ && result_compare_paths_.size() >= 2) {
    compare_strip_->setPaths(result_compare_paths_, p);
    compare_strip_->setPathBadges(filmstrip_measure_badges_);
  }
  showStatus(QStringLiteral("结果表双击对比 · %1 · %2 帧")
                 .arg(QFileInfo(p).fileName())
                 .arg(result_compare_paths_.size()));
  refreshGeomCompareOverlays();
}

void MainWindow::cacheFilmstripGeomOverlays(const QVector<OverlayHit>& hits) {
  const QString path = filmstrip_ ? filmstrip_->currentPath().trimmed() : QString();
  last_run_film_path_ = path;
  if (path.isEmpty()) return;
  const QVector<GeomPickable> pks = pickablesFromOverlayHits(hits);
  if (pks.isEmpty()) {
    filmstrip_geom_cache_.remove(path);
    return;
  }
  filmstrip_geom_cache_.insert(path, pks);
  while (filmstrip_geom_cache_.size() > 32) {
    const QString first = filmstrip_geom_cache_.constBegin().key();
    if (first == path) {
      // evict some other key
      bool evicted = false;
      for (auto it = filmstrip_geom_cache_.constBegin(); it != filmstrip_geom_cache_.constEnd();
           ++it) {
        if (it.key() != path) {
          filmstrip_geom_cache_.remove(it.key());
          evicted = true;
          break;
        }
      }
      if (!evicted) break;
    } else {
      filmstrip_geom_cache_.remove(first);
    }
  }
}

void MainWindow::refreshGeomCompareOverlays() {
  if (!output_view_) return;
  QStringList order;
  if (compare_strip_ && compare_strip_->count() >= 2)
    order = compare_strip_->paths();
  else if (filmstrip_ && !filmstrip_->currentPath().isEmpty())
    order << filmstrip_->currentPath();
  QString hi;
  if (compare_strip_ && order.contains(compare_strip_->activePath()))
    hi = compare_strip_->activePath();
  else if (!order.isEmpty())
    hi = order.first();
  QVector<QPair<QString, QVector<GeomPickable>>> frames;
  for (const QString& p : order) {
    const auto it = filmstrip_geom_cache_.constFind(p);
    if (it == filmstrip_geom_cache_.constEnd() || it->isEmpty()) continue;
    frames.push_back({p, *it});
  }
  const bool multi = order.size() >= 2;
  const bool review = frames.size() == 1 && !last_run_film_path_.isEmpty() &&
                      frames.first().first != last_run_film_path_;
  if ((multi && !frames.isEmpty()) || review) {
    output_view_->setGeomOverlays(overlaySpecsForMultiframe(frames, hi));
  } else {
    output_view_->clearGeomOverlays();
  }
}

void MainWindow::cacheFilmstripMeasureBadge() {
  const QString path = filmstrip_ ? filmstrip_->currentPath().trimmed() : QString();
  if (path.isEmpty()) {
    syncFilmstripMeasureBadges();
    return;
  }
  const QString tag = FilmstripBar::measureBadgeFromVars(flow_vars_);
  if (tag.isEmpty())
    filmstrip_measure_badges_.remove(path);
  else
    filmstrip_measure_badges_.insert(path, tag);
  while (filmstrip_measure_badges_.size() > 32) {
    const QString first = filmstrip_measure_badges_.constBegin().key();
    if (first == path) {
      bool evicted = false;
      for (auto it = filmstrip_measure_badges_.constBegin();
           it != filmstrip_measure_badges_.constEnd(); ++it) {
        if (it.key() != path) {
          filmstrip_measure_badges_.remove(it.key());
          evicted = true;
          break;
        }
      }
      if (!evicted) break;
    } else {
      filmstrip_measure_badges_.remove(first);
    }
  }
  syncFilmstripMeasureBadges();
}

void MainWindow::syncFilmstripMeasureBadges() {
  if (filmstrip_) filmstrip_->setFrameMeasureBadges(filmstrip_measure_badges_);
  if (compare_strip_) compare_strip_->setPathBadges(filmstrip_measure_badges_);
}

void MainWindow::markProjectDirty() {
  if (applying_document_) return;
  if (project_dirty_) {
    refreshProjectTitle();
    return;
  }
  project_dirty_ = true;
  refreshProjectTitle();
}

void MainWindow::markProjectClean() {
  project_dirty_ = false;
  document_.markCanvasUndoClean();
  refreshProjectTitle();
  updateCanvasUndoActions();
}

void MainWindow::refreshProjectTitle() {
  QString name = document_.name().trimmed();
  if (name.isEmpty()) name = QStringLiteral("未命名方案");
  const QString mode = run_mode_ ? QStringLiteral("运行态") : QStringLiteral("设计态");
  const QString star = project_dirty_ ? QStringLiteral("*") : QString();
  // [*] is required by QWidget::setWindowModified.
  setWindowTitle(QStringLiteral("[*]%1 — SIEANS Vision · %2").arg(name, mode));
  setWindowModified(project_dirty_);
  if (project_label_) {
    const QString path = document_.path();
    const QString hint = path.isEmpty()
                             ? QStringLiteral("未保存")
                             : QFileInfo(path).fileName();
    project_label_->setText(QStringLiteral("方案: %1%2 · %3")
                                .arg(star, name, hint));
  }
}

bool MainWindow::confirmDiscardOrSave() {
  if (!project_dirty_) return true;
  if (workbenchIsHeadless()) return true;
  const QMessageBox::StandardButton ret = QMessageBox::question(
      this, QStringLiteral("方案已修改"),
      QStringLiteral("当前方案有未保存的修改。是否保存？"),
      QMessageBox::Save | QMessageBox::Discard | QMessageBox::Cancel,
      QMessageBox::Save);
  if (ret == QMessageBox::Cancel) return false;
  if (ret == QMessageBox::Discard) return true;
  onSaveProject();
  return !project_dirty_;
}

void MainWindow::applyWorkbenchLayout() {
  if (root_split_) {
    const int h = root_split_->height();
    if (h >= 200) {
      // 底栏保持约 1/5，最多 220px，避免空结果表占掉半个工作区。
      const int bottom = qBound(140, h / 5, 220);
      const int top = qMax(160, h - bottom);
      root_split_->setSizes({top, bottom});
    }
  }
  if (flow_view_) flow_view_->fitAll();
}

void MainWindow::showEvent(QShowEvent* event) {
  QMainWindow::showEvent(event);
  if (layout_applied_) return;
  layout_applied_ = true;
  applyWorkbenchLayout();
  QTimer::singleShot(0, this, &MainWindow::applyWorkbenchLayout);
}

void MainWindow::maybeLoadOpenAndRunSample() {
  // 仅跳过真正无界面（offscreen / HEADLESS）。SIEANS_QT_SCREENSHOT_QUIT 仍算可见启动，
  // 需要预载示例图以便验证普通打开即跑路径；workbenchIsHeadless() 会把 QUIT 当无界面以避开模态框。
  const QByteArray plat = qgetenv("QT_QPA_PLATFORM");
  if (plat == "offscreen" || plat == "minimal" || plat == "minimalegl") return;
  if (qgetenv("SIEANS_QT_HEADLESS") == "1") return;
  if (image_view_ && !image_view_->currentImage().isNull()) return;
  if (filmstrip_ && filmstrip_->count() > 0) return;
  if (!document_.openAndRunDemo()) return;
  const QString sample = samplePathCandidates();
  if (sample.isEmpty()) return;
  applying_document_ = true;
  loadImagePath(sample, true);
  applying_document_ = false;
  markProjectClean();
  logResult(QStringLiteral("打开即跑：已加载示例 QR（未自动运行）"));
}

void MainWindow::closeEvent(QCloseEvent* event) {
  if (!confirmDiscardOrSave()) {
    event->ignore();
    return;
  }
  QMainWindow::closeEvent(event);
}

void MainWindow::onNewProject() {
  if (!confirmDiscardOrSave()) return;
  document_.seedGentlQrDemo();
  applyDocumentToUi();
  markProjectClean();
  logResult(QStringLiteral("新建 GenTL→QR 方案"));
}

void MainWindow::onOpenProject() {
  if (!confirmDiscardOrSave()) return;
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
  markProjectClean();
  rememberRecentFile(path);
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
  markProjectClean();
  rememberRecentFile(path);
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
  markProjectClean();
  rememberRecentFile(path);
  logResult(QStringLiteral("方案已保存：%1").arg(path));
}

void MainWindow::onExportCurrentFlow() {
  document_.ensureScheme();
  QString name = QStringLiteral("流程");
  if (const FlowDef* f = document_.findFlow(document_.activeFlowId()))
    name = f->name;
  QString path;
  if (workbenchIsHeadless()) {
    path = workbenchArtifactsDir() + QLatin1Char('/') + name + QStringLiteral(".prc");
  } else {
    path = QFileDialog::getSaveFileName(
        this, QStringLiteral("导出当前流程"),
        defaultProjectsDir() + QLatin1Char('/') + name + QStringLiteral(".prc"),
        QStringLiteral("SIEANS 流程 (*.prc)"));
  }
  if (path.isEmpty()) return;
  QString err;
  if (!document_.exportPrcToFile(document_.activeFlowId(), path, &err)) {
    if (!workbenchIsHeadless())
      QMessageBox::warning(this, QStringLiteral("导出失败"), err);
    logResult(QStringLiteral("导出流程失败：%1").arg(err));
    return;
  }
  rememberRecentFile(path);
  logResult(QStringLiteral("已导出流程：%1").arg(path));
}

void MainWindow::onImportFlow() {
  QString path;
  if (workbenchIsHeadless()) return;
  path = QFileDialog::getOpenFileName(
      this, QStringLiteral("导入流程"), defaultProjectsDir(),
      QStringLiteral("SIEANS 流程 (*.prc *.json);;全部 (*.*)"));
  if (path.isEmpty()) return;
  QString err;
  const FlowDef imported = document_.importPrcFromFile(path, &err);
  if (imported.id.isEmpty()) {
    QMessageBox::warning(this, QStringLiteral("导入失败"), err);
    return;
  }
  document_.activateFlow(imported.id);
  applyDocumentToUi();
  markProjectDirty();
  rememberRecentFile(path);
  logResult(QStringLiteral("已导入流程：%1").arg(imported.name));
}

void MainWindow::onOpenImage() {
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("打开图像"),
      workbenchArtifactsDir(),
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
  if (updateFlowStates && !dispatching_triggers_)
    fireEventTriggers(QStringLiteral("流程开始"), true);

  QImage working = src;
  PointCloud workingCloud;
  if (!imported_cloud_path_.isEmpty()) {
    QString impErr;
    const PointCloud imported = loadPointCloudFile(imported_cloud_path_, &impErr);
    if (!imported.isEmpty()) workingCloud = imported;
  }
  pipeline_cancel_.store(false);
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
  struct NodeExec {
    bool executed = false;
    bool skipped = false;
    bool ok = true;
    bool passed = false;
    bool evalFailed = false;
    QString branchTaken;
    QString mergeFrom;
  };
  QHash<QString, NodeExec> execInfo;
  {
    NodeExec src;
    src.executed = true;
    src.ok = true;
    execInfo.insert(QStringLiteral("source"), src);
  }
  int skippedCount = 0;

  auto edgeFires = [&](const FlowEdge& e) -> bool {
    if (e.from == QLatin1String("source")) return true;
    const NodeExec up = execInfo.value(e.from);
    if (!up.executed || up.skipped) return false;
    const QString when = e.when.isEmpty() ? QStringLiteral("always") : e.when;
    if (when == QLatin1String("always")) return true;
    if (up.evalFailed &&
        (when == QLatin1String("true") || when == QLatin1String("false")))
      return false;
    if (when == QLatin1String("success")) return up.ok;
    if (when == QLatin1String("error")) return !up.ok;
    if (when == QLatin1String("true")) return up.passed;
    if (when == QLatin1String("false")) return !up.passed;
    return up.branchTaken == when;
  };

  for (const QString& id : order) {
    FlowStep* step = document_.findStep(id);
    if (!step) continue;
    if (pipeline_cancel_.load()) {
      ++skippedCount;
      if (updateFlowStates)
        flow_scene_->setNodeRunState(id, QStringLiteral("SKIP"));
      continue;
    }
    const QString op = step->operation;

    QVector<FlowEdge> incoming;
    for (const FlowEdge& e : document_.edges()) {
      if (e.to == id) incoming.push_back(e);
    }
    bool activate = true;
    QString mergeFromId;
    if (!incoming.isEmpty()) {
      if (op == QLatin1String("branch_merge")) {
        int live = 0;
        for (const FlowEdge& e : incoming) {
          if (edgeFires(e)) {
            ++live;
            mergeFromId = e.from;
          }
        }
        if (live == 0) {
          activate = false;
        } else if (live > 1) {
          if (updateFlowStates)
            flow_scene_->setNodeRunState(id, QStringLiteral("NG"));
          NodeExec ng;
          ng.executed = true;
          ng.ok = false;
          execInfo.insert(id, ng);
          flow_vars_.insert(QStringLiteral("mergeFrom"), QString());
          logResult(QStringLiteral("%1 [branch_merge] 多路同时激活，汇合失败")
                        .arg(step->name));
          continue;
        }
      } else {
        for (const FlowEdge& e : incoming) {
          if (!edgeFires(e)) {
            activate = false;
            break;
          }
        }
      }
    }
    if (!activate) {
      ++skippedCount;
      NodeExec sk;
      sk.skipped = true;
      execInfo.insert(id, sk);
      if (updateFlowStates)
        flow_scene_->setNodeRunState(id, QStringLiteral("已跳过"));
      logResult(QStringLiteral("%1 [%2] 已跳过").arg(step->name, op));
      continue;
    }

    if (updateFlowStates)
      flow_scene_->setNodeRunState(id, QStringLiteral("运行中"));

    bool ok = true;
    QString note;

    if (op == QLatin1String("camera_capture")) {
      note = QStringLiteral("采图 %1×%2").arg(working.width()).arg(working.height());
    } else if (op == QLatin1String("preprocess")) {
      QVariantMap pp = step->params;
      if (!current_path_.isEmpty())
        pp.insert(QStringLiteral("baseDir"), QFileInfo(current_path_).absolutePath());
      injectFixtureFromVars(pp, flow_vars_);
      if (pp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(pp, working.width(), working.height());
        if (fr.active && !fr.aabb.isEmpty()) {
          pp.insert(QStringLiteral("roiX"), fr.aabb.x());
          pp.insert(QStringLiteral("roiY"), fr.aabb.y());
          pp.insert(QStringLiteral("roiW"), fr.aabb.width());
          pp.insert(QStringLiteral("roiH"), fr.aabb.height());
        }
      }
      const PreprocessResult pr = runPreprocess(working, pp);
      if (!pr.image.isNull()) working = pr.image;
      image_view_->setLiveImage(working);
      note = pr.ok ? (pr.note.isEmpty() ? QStringLiteral("预处理 %1").arg(pr.method)
                                        : pr.note)
                   : QStringLiteral("预处理失败 %1").arg(pr.error);
    } else if (op == QLatin1String("color")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap cp = step->params;
      injectFixtureFromVars(cp, flow_vars_);
      if (cp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(cp, working.width(), working.height());
        if (fr.active && !fr.aabb.isEmpty()) {
          cp.insert(QStringLiteral("roiX"), fr.aabb.x());
          cp.insert(QStringLiteral("roiY"), fr.aabb.y());
          cp.insert(QStringLiteral("roiW"), fr.aabb.width());
          cp.insert(QStringLiteral("roiH"), fr.aabb.height());
        }
      }
      const ColorResult cr = runColorOp(working, cp);
      const double cMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += cMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("color"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("color");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = cr.ok ? 1 : 0;
      const int passed = (cr.ok && (cr.method != QLatin1String("threshold") || cr.fgCount >= 1)) ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), passed);
      put(QStringLiteral("Method"), cr.method);
      put(QStringLiteral("Space"), cr.space);
      put(QStringLiteral("Channel"), cr.channel);
      put(QStringLiteral("FgCount"), cr.fgCount);
      if (prefix == QLatin1String("color")) {
        flow_vars_.insert(QStringLiteral("color_ok"), okI);
        flow_vars_.insert(QStringLiteral("color_fg"), cr.fgCount);
      }
      if (cr.ok && !cr.image.isNull()) {
        working = cr.image.convertToFormat(QImage::Format_RGB888);
        image_view_->setLiveImage(working);
      }
      if (step->params.value(QStringLiteral("writePassGate")).toBool())
        flow_vars_.insert(QStringLiteral("passGate"), passed);
      {
        StepSnap snap;
        snap.ok = cr.ok;
        snap.count = cr.fgCount;
        snap.matches = cr.fgCount;
        snap.text = cr.note;
        snap.fields.insert(QStringLiteral("fgCount"), cr.fgCount);
        snap.fields.insert(QStringLiteral("method"), cr.method);
        step_snaps.insert(id, snap);
      }
      ok = cr.ok;
      note = cr.ok ? QStringLiteral("%1 · %2 ms").arg(cr.note).arg(cMs, 0, 'f', 1)
                   : cr.error;
    } else if (op == QLatin1String("warp")) {
      const auto t0 = std::chrono::steady_clock::now();
      const WarpResult wr = runWarp(working, step->params);
      const double wMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += wMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("warp"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("warp");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = wr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Method"), wr.method);
      put(QStringLiteral("Width"), wr.outWidth);
      put(QStringLiteral("Height"), wr.outHeight);
      if (prefix == QLatin1String("warp"))
        flow_vars_.insert(QStringLiteral("warp_ok"), okI);
      if (wr.ok && !wr.image.isNull()) {
        working = wr.image.convertToFormat(QImage::Format_RGB888);
        image_view_->setLiveImage(working);
      }
      if (step->params.value(QStringLiteral("writePassGate")).toBool())
        flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.ok = wr.ok;
        snap.text = wr.note;
        snap.fields.insert(QStringLiteral("method"), wr.method);
        step_snaps.insert(id, snap);
      }
      ok = wr.ok;
      note = wr.ok ? QStringLiteral("%1 · %2 ms").arg(wr.note).arg(wMs, 0, 'f', 1)
                   : wr.error;
    } else if (op == QLatin1String("fft")) {
      const auto t0 = std::chrono::steady_clock::now();
      const FftResult fr = runFft(working, step->params);
      const double fMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += fMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("fft"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("fft");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = fr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Method"), fr.method);
      put(QStringLiteral("Sharpness"), fr.sharpness);
      put(QStringLiteral("PadW"), fr.padW);
      put(QStringLiteral("PadH"), fr.padH);
      if (prefix == QLatin1String("fft")) {
        flow_vars_.insert(QStringLiteral("fft_ok"), okI);
        flow_vars_.insert(QStringLiteral("fft_sharpness"), fr.sharpness);
      }
      if (fr.ok && !fr.image.isNull()) {
        working = fr.image.convertToFormat(QImage::Format_RGB888);
        image_view_->setLiveImage(working);
      }
      if (step->params.value(QStringLiteral("writePassGate")).toBool())
        flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.ok = fr.ok;
        snap.score = fr.sharpness;
        snap.text = fr.note;
        snap.fields.insert(QStringLiteral("method"), fr.method);
        snap.fields.insert(QStringLiteral("sharpness"), fr.sharpness);
        step_snaps.insert(id, snap);
      }
      ok = fr.ok;
      note = fr.ok ? QStringLiteral("%1 · %2 ms").arg(fr.note).arg(fMs, 0, 'f', 1)
                   : fr.error;
    } else if (op == QLatin1String("classify")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap cp = step->params;
      if (!current_path_.isEmpty())
        cp.insert(QStringLiteral("baseDir"), QFileInfo(current_path_).absolutePath());
      const bool hasFeat = !cp.value(QStringLiteral("features")).toString().trimmed().isEmpty() ||
                           cp.value(QStringLiteral("features")).metaType().id() == QMetaType::QVariantList;
      if (!hasFeat) {
        const QString names = cp.value(QStringLiteral("featureVars")).toString();
        QVariantList feats;
        for (const QString& raw : names.split(QLatin1Char(','), Qt::SkipEmptyParts)) {
          const QString key = raw.trimmed();
          if (key.isEmpty()) continue;
          feats << flow_vars_.value(key);
        }
        if (!feats.isEmpty()) cp.insert(QStringLiteral("features"), feats);
      }
      const ClassifyResult cr = runClassify(cp);
      const double cMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += cMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("classify"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("classify");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = cr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Method"), cr.method);
      put(QStringLiteral("Label"), cr.label);
      put(QStringLiteral("Index"), cr.classIndex);
      put(QStringLiteral("Score"), cr.score);
      put(QStringLiteral("TrainCount"), cr.trainCount);
      if (prefix == QLatin1String("classify")) {
        flow_vars_.insert(QStringLiteral("classify_ok"), okI);
        flow_vars_.insert(QStringLiteral("classify_label"), cr.label);
        flow_vars_.insert(QStringLiteral("classify_score"), cr.score);
      }
      if (step->params.value(QStringLiteral("writePassGate")).toBool())
        flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.ok = cr.ok;
        snap.score = cr.score;
        snap.text = cr.ok ? cr.label : cr.error;
        snap.fields.insert(QStringLiteral("method"), cr.method);
        snap.fields.insert(QStringLiteral("label"), cr.label);
        snap.fields.insert(QStringLiteral("score"), cr.score);
        step_snaps.insert(id, snap);
      }
      ok = cr.ok;
      note = cr.ok ? QStringLiteral("%1 · %2 ms").arg(cr.note).arg(cMs, 0, 'f', 1)
                   : cr.error;
    } else if (op == QLatin1String("camera_cal")) {
      const auto t0 = std::chrono::steady_clock::now();
      const CameraCalResult cc = runCameraCal(working, step->params);
      const double cMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += cMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("cal"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("cal");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = cc.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Method"), cc.method);
      put(QStringLiteral("Pattern"), cc.pattern);
      put(QStringLiteral("Fx"), cc.intrinsics.fx);
      put(QStringLiteral("Fy"), cc.intrinsics.fy);
      put(QStringLiteral("Cx"), cc.intrinsics.cx);
      put(QStringLiteral("Cy"), cc.intrinsics.cy);
      put(QStringLiteral("K1"), cc.intrinsics.k1);
      put(QStringLiteral("K2"), cc.intrinsics.k2);
      put(QStringLiteral("Rmse"), cc.rmse);
      put(QStringLiteral("Views"), cc.views);
      put(QStringLiteral("Detected"), cc.detected);
      if (prefix == QLatin1String("cal")) {
        flow_vars_.insert(QStringLiteral("cal_ok"), okI);
        flow_vars_.insert(QStringLiteral("cal_rmse"), cc.rmse);
      }
      if (cc.ok && !cc.image.isNull()) {
        working = cc.image.convertToFormat(QImage::Format_RGB888);
        image_view_->setLiveImage(working);
      }
      if (step->params.value(QStringLiteral("writePassGate")).toBool())
        flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.ok = cc.ok;
        snap.count = cc.detected;
        snap.matches = cc.views;
        snap.score = cc.rmse;
        snap.text = cc.note;
        snap.fields.insert(QStringLiteral("fx"), cc.intrinsics.fx);
        snap.fields.insert(QStringLiteral("rmse"), cc.rmse);
        step_snaps.insert(id, snap);
      }
      ok = cc.ok;
      note = cc.ok ? QStringLiteral("%1 · %2 ms").arg(cc.note).arg(cMs, 0, 'f', 1)
                   : cc.error;
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
        for (const QPointF& pt : cc.corners) {
          OverlayHit o;
          o.format = QStringLiteral("CAL");
          o.text = QString();
          o.polygon = QPolygonF(QRectF(pt.x() - 3, pt.y() - 3, 6, 6));
          overlays.push_back(o);
        }
      }
    } else if (op == QLatin1String("locate")) {
      QVariantMap lp = step->params;
      const auto t0 = std::chrono::steady_clock::now();
      LocateResult lr = runLocate(working, lp);
      if (lr.templateCreated && !lr.templateUsed.isNull()) {
        const QString dir =
            workbenchTemplatesDir();
        QDir().mkpath(dir);
        const QString tplPath = dir + QLatin1Char('/') + id + QStringLiteral(".png");
        lr.templateUsed.save(tplPath);
        step->params.insert(QStringLiteral("templatePath"), tplPath);
        step->params.insert(QStringLiteral("templateCaptured"), true);
        lr.templatePath = tplPath;
      }
      const double matchMs = std::chrono::duration<double, std::milli>(
                                 std::chrono::steady_clock::now() - t0)
                                 .count();
      algoMs += matchMs;
      const QVector<TemplateHit>& found = lr.hits;
      const double best = found.isEmpty() ? 0.0 : found.first().score;
      const QPointF c0 = found.isEmpty() ? QPointF() : found.first().center;
      ok = lr.ok && !found.isEmpty();
      flow_vars_.insert(QStringLiteral("locateScore"), best);
      flow_vars_.insert(QStringLiteral("locateCount"), found.size());
      flow_vars_.insert(QStringLiteral("locateX"), c0.x());
      flow_vars_.insert(QStringLiteral("locateY"), c0.y());
      flow_vars_.insert(QStringLiteral("locateAngle"),
                        found.isEmpty() ? 0 : found.first().angleDeg);
      flow_vars_.insert(QStringLiteral("locateScale"),
                        found.isEmpty() ? 1 : found.first().scale);
      flow_vars_.insert(QStringLiteral("locateScaleX"),
                        found.isEmpty() ? 1 : found.first().scaleX);
      flow_vars_.insert(QStringLiteral("locateScaleY"),
                        found.isEmpty() ? 1 : found.first().scaleY);
      flow_vars_.insert(QStringLiteral("locateTemplate"),
                        found.isEmpty() ? QString() : found.first().templateName);
      flow_vars_.insert(QStringLiteral("locateW"),
                        found.isEmpty() ? 0 : found.first().rect.width());
      flow_vars_.insert(QStringLiteral("locateH"),
                        found.isEmpty() ? 0 : found.first().rect.height());
      flow_vars_.insert(QStringLiteral("locateOk"), ok ? 1 : 0);
      if (!flow_vars_.contains(QStringLiteral("barcodeCount")) &&
          step->params.value(QStringLiteral("writePassGate")).toBool()) {
        flow_vars_.insert(QStringLiteral("passGate"), ok ? 1 : 0);
      }
      StepSnap snap;
      snap.ok = ok;
      snap.count = found.size();
      snap.matches = found.size();
      snap.score = best;
      snap.confidence = best;
      snap.text = QString::number(best, 'f', 3);
      snap.fields.insert(QStringLiteral("x"), c0.x());
      snap.fields.insert(QStringLiteral("y"), c0.y());
      snap.fields.insert(QStringLiteral("angle"),
                         found.isEmpty() ? 0 : found.first().angleDeg);
      step_snaps.insert(id, snap);
      int hi = 0;
      const bool showBox = !step->params.contains(QStringLiteral("showOverlay")) ||
                           step->params.value(QStringLiteral("showOverlay")).toBool();
      const bool showOrigin = step->params.value(QStringLiteral("showOrigin")).toBool();
      const bool showAng = !step->params.contains(QStringLiteral("showAngleDeg")) ||
                           step->params.value(QStringLiteral("showAngleDeg")).toBool();
      for (const TemplateHit& hit : found) {
        OverlayHit o;
        o.format = QStringLiteral("定位");
        o.text = showAng ? QStringLiteral("分数 %1  角度 %2")
                               .arg(hit.score, 0, 'f', 2)
                               .arg(hit.angleDeg, 0, 'f', 1)
                         : QStringLiteral("分数 %1").arg(hit.score, 0, 'f', 2);
        if (!hit.corners.isEmpty())
          o.polygon = hit.corners;
        else {
          const QRect r = hit.rect;
          o.polygon << r.topLeft() << r.topRight() << r.bottomRight() << r.bottomLeft();
        }
        if (showBox) overlays.push_back(o);
        if (showOrigin) {
          OverlayHit org;
          org.format = QStringLiteral("原点");
          org.text = QStringLiteral("原点");
          const QPointF c = hit.center;
          org.polygon << QPointF(c.x() - 6, c.y()) << QPointF(c.x() + 6, c.y())
                      << QPointF(c.x(), c.y() - 6) << QPointF(c.x(), c.y() + 6);
          overlays.push_back(org);
        }
        if (result_table_) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          auto* keyItem = new QTableWidgetItem(QStringLiteral("locate[%1].score").arg(hi));
          const QString filmPath = filmstrip_ ? filmstrip_->currentPath() : QString();
          keyItem->setData(Qt::UserRole, filmPath);
          keyItem->setData(Qt::UserRole + 1, filmstrip_ ? filmstrip_->index() : -1);
          keyItem->setData(Qt::UserRole + 2, id);
          result_table_->setItem(row, 0, keyItem);
          result_table_->setItem(
              row, 1, new QTableWidgetItem(QString::number(hit.score, 'f', 3)));
          result_table_->setItem(row, 2, new QTableWidgetItem(QStringLiteral("float")));
        }
        ++hi;
      }
      if (output_view_) output_view_->setLiveImage(working);
      if (prop_float_) {
        QVariantMap locVars = flow_vars_;
        if (filmstrip_)
          locVars.insert(QStringLiteral("filmstripPath"), filmstrip_->currentPath());
        prop_float_->setLocateLastResult(locVars);
      }
      note = lr.templateCreated
                 ? QStringLiteral("已创建模板 · %1 · %2 ms").arg(lr.note).arg(matchMs, 0, 'f', 1)
                 : (lr.ok ? QStringLiteral("%1 · %2 ms").arg(lr.note).arg(matchMs, 0, 'f', 1)
                          : (lr.error.isEmpty() ? lr.note : lr.error));
    } else if (op == QLatin1String("pose_correct")) {
      const PoseCorrectResult pr = runPoseCorrect(step->params, flow_vars_);
      ok = pr.ok;
      note = pr.note;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("fixture"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("fixture");
      const bool writeVars = !step->params.contains(QStringLiteral("writeFlowVars")) ||
                             step->params.value(QStringLiteral("writeFlowVars")).toBool();
      if (writeVars) {
        flow_vars_.insert(prefix + QStringLiteral("X"), pr.pose.x);
        flow_vars_.insert(prefix + QStringLiteral("Y"), pr.pose.y);
        flow_vars_.insert(prefix + QStringLiteral("Angle"), pr.pose.angleDeg);
        flow_vars_.insert(prefix + QStringLiteral("Scale"), pr.pose.scale);
        flow_vars_.insert(prefix + QStringLiteral("Ok"), pr.ok ? 1 : 0);
        flow_vars_.insert(prefix + QStringLiteral("Status"), pr.status);
        flow_vars_.insert(prefix + QStringLiteral("Score"), pr.score);
        flow_vars_.insert(prefix + QStringLiteral("BaseX"), pr.pose.x);
        flow_vars_.insert(prefix + QStringLiteral("BaseY"), pr.pose.y);
        flow_vars_.insert(prefix + QStringLiteral("BaseAngle"), pr.pose.angleDeg);
        if (prefix == QLatin1String("fixture")) {
          flow_vars_.insert(QStringLiteral("fixture_x"), pr.pose.x);
          flow_vars_.insert(QStringLiteral("fixture_y"), pr.pose.y);
          flow_vars_.insert(QStringLiteral("fixture_angle"), pr.pose.angleDeg);
          flow_vars_.insert(QStringLiteral("fixture_ok"), pr.ok ? 1 : 0);
        }
      }
      if ((!step->params.contains(QStringLiteral("showAxes")) ||
           step->params.value(QStringLiteral("showAxes")).toBool()) &&
          pr.ok) {
        OverlayHit ax;
        ax.format = QStringLiteral("FIXTURE");
        ax.text = QStringLiteral("X");
        ax.polygon = pr.axisX;
        overlays.push_back(ax);
        OverlayHit ay;
        ay.format = QStringLiteral("FIXTURE");
        ay.text = QStringLiteral("Y");
        ay.polygon = pr.axisY;
        overlays.push_back(ay);
      }
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("X"), QString::number(pr.pose.x, 'f', 1),
               QStringLiteral("px"));
        addRow(prefix + QStringLiteral("Y"), QString::number(pr.pose.y, 'f', 1),
               QStringLiteral("px"));
        addRow(prefix + QStringLiteral("Angle"),
               QString::number(pr.pose.angleDeg, 'f', 2), QStringLiteral("deg"));
        addRow(prefix + QStringLiteral("Ok"), QString::number(pr.ok ? 1 : 0),
               QStringLiteral("gate"));
      }
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
    } else if (op == QLatin1String("ocr")) {
      QImage rgb = toRgb888(working);
      sieans::OcrOptions opts;
      opts.lang =
          step->params.value(QStringLiteral("lang"), QStringLiteral("eng"))
              .toString()
              .toStdString();
      opts.psm = step->params.value(QStringLiteral("psm"), 6).toInt();
      opts.min_confidence =
          step->params.value(QStringLiteral("minConfidence"), 0).toInt();
      std::vector<sieans::OcrHit> ocrHits;
      const auto t0 = std::chrono::steady_clock::now();
      try {
        ocrHits = sieans::recognize_text(
            rgb.constBits(), rgb.width(), rgb.height(), rgb.bytesPerLine(),
            sieans::PixelFormat::RGB24, opts);
      } catch (const std::exception& ex) {
        ok = false;
        note = QString::fromUtf8(ex.what());
        ocrHits.clear();
      }
      const double ocrMs = std::chrono::duration<double, std::milli>(
                               std::chrono::steady_clock::now() - t0)
                               .count();
      algoMs += ocrMs;
      decodeMs = ocrMs;
      QStringList texts;
      for (const auto& h : ocrHits) {
        const QString tx = QString::fromStdString(h.text).trimmed();
        if (!tx.isEmpty()) texts << tx;
      }
      // Prefer a line containing SIEANS when soft plate is present
      QString best;
      for (const QString& tx : texts) {
        if (tx.contains(QStringLiteral("SIEANS"), Qt::CaseInsensitive)) {
          best = tx;
          break;
        }
      }
      if (best.isEmpty() && !texts.isEmpty()) best = texts.first();
      flow_vars_.insert(QStringLiteral("ocrCount"), texts.size());
      flow_vars_.insert(QStringLiteral("ocrText"), best);
      flow_vars_.insert(QStringLiteral("ocrAll"), texts.join(QLatin1Char('\n')));
      const int minC = step->params.value(QStringLiteral("judgeMinCount"), 1).toInt();
      const bool gate = texts.size() >= minC && !best.isEmpty();
      flow_vars_.insert(QStringLiteral("ocrOk"), gate ? 1 : 0);
      if (!flow_vars_.contains(QStringLiteral("passGate")))
        flow_vars_.insert(QStringLiteral("passGate"), gate ? 1 : 0);
      {
        StepSnap snap;
        snap.count = texts.size();
        snap.ok = gate;
        snap.matches = texts.size();
        snap.text = best;
        snap.score = gate ? 1.0 : 0.0;
        snap.confidence = snap.score;
        snap.fields.insert(QStringLiteral("text"), best);
        for (const QString& tx : texts) snap.texts << tx;
        step_snaps.insert(id, snap);
      }
      ok = gate || !step->params.value(QStringLiteral("judgeEnable"), true).toBool();
      note = QStringLiteral("OCR %1 行 · %2 ms · %3")
                 .arg(texts.size())
                 .arg(ocrMs, 0, 'f', 1)
                 .arg(best.left(40));
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool() &&
          !best.isEmpty()) {
        OverlayHit o;
        o.text = best;
        o.format = QStringLiteral("OCR");
        const int bw = qMin(working.width() / 3, 160);
        const int bh = 36;
        const int ox = qMax(0, working.width() - bw - 8);
        o.polygon << QPointF(ox, 6) << QPointF(ox + bw, 6)
                  << QPointF(ox + bw, 6 + bh) << QPointF(ox, 6 + bh);
        overlays.push_back(o);
      }
      int i = 0;
      for (const QString& tx : texts) {
        const int row = result_table_->rowCount();
        result_table_->insertRow(row);
        result_table_->setItem(
            row, 0, new QTableWidgetItem(QStringLiteral("ocr[%1].text").arg(i)));
        result_table_->setItem(row, 1, new QTableWidgetItem(tx));
        result_table_->setItem(row, 2, new QTableWidgetItem(QStringLiteral("OCR")));
        ++i;
      }
    } else if (op == QLatin1String("caliper")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap cp = step->params;
      injectFixtureFromVars(cp, flow_vars_);
      if (cp.value(QStringLiteral("followFixture")).toBool() &&
          cp.value(QStringLiteral("target")).toString().toLower() !=
              QLatin1String("soft_bars")) {
        const FollowRoi fr = resolveFollowRoi(cp, working.width(), working.height());
        if (fr.active && !fr.aabb.isEmpty()) {
          cp.insert(QStringLiteral("roiX"), fr.aabb.x());
          cp.insert(QStringLiteral("roiY"), fr.aabb.y());
          cp.insert(QStringLiteral("roiW"), fr.aabb.width());
          cp.insert(QStringLiteral("roiH"), fr.aabb.height());
          cp.insert(QStringLiteral("target"), QString());
        }
      }
      const CaliperResult cr = runCaliper(working, cp);
      const double calMs = std::chrono::duration<double, std::milli>(
                               std::chrono::steady_clock::now() - t0)
                               .count();
      algoMs += calMs;
      flow_vars_.insert(QStringLiteral("caliperDist"), cr.distPx);
      flow_vars_.insert(QStringLiteral("caliperEdge0"), cr.edge0);
      flow_vars_.insert(QStringLiteral("caliperEdge1"), cr.edge1);
      flow_vars_.insert(QStringLiteral("measureMm"), cr.distMm);
      flow_vars_.insert(QStringLiteral("caliperMm"), cr.distMm);
      const double minPx =
          step->params.value(QStringLiteral("judgeMinPx"), 1.0).toDouble();
      const double maxPx =
          step->params.value(QStringLiteral("judgeMaxPx"), 1e9).toDouble();
      const bool inRange = cr.ok && cr.distPx >= minPx && cr.distPx <= maxPx;
      const bool gate = inRange;
      flow_vars_.insert(QStringLiteral("caliperOk"), gate ? 1 : 0);
      {
        StepSnap snap;
        snap.count = cr.ok ? 2 : 0;
        snap.ok = gate;
        snap.matches = cr.ok ? 1 : 0;
        snap.score = cr.distPx;
        snap.confidence = (cr.strength0 + cr.strength1) * 0.5;
        snap.text = QStringLiteral("%1 px").arg(cr.distPx, 0, 'f', 1);
        snap.fields.insert(QStringLiteral("distPx"), cr.distPx);
        snap.fields.insert(QStringLiteral("distMm"), cr.distMm);
        step_snaps.insert(id, snap);
      }
      ok = gate || !step->params.value(QStringLiteral("judgeEnable"), true).toBool();
      note = QStringLiteral("卡尺 %1 px · %2 mm · %3 ms · %4")
                 .arg(cr.distPx, 0, 'f', 1)
                 .arg(cr.distMm, 0, 'f', 3)
                 .arg(calMs, 0, 'f', 1)
                 .arg(cr.note);
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool() &&
          cr.ok) {
        OverlayHit o;
        o.text = QStringLiteral("%1px").arg(cr.distPx, 0, 'f', 1);
        o.format = QStringLiteral("CALIPER");
        // box around the two edge points + scan line
        const qreal pad = 6.0;
        const qreal x0 = qMin(cr.p0.x(), cr.p1.x()) - pad;
        const qreal y0 = qMin(cr.p0.y(), cr.p1.y()) - pad;
        const qreal x1 = qMax(cr.p0.x(), cr.p1.x()) + pad;
        const qreal y1 = qMax(cr.p0.y(), cr.p1.y()) + pad;
        o.polygon << QPointF(x0, y0) << QPointF(x1, y0) << QPointF(x1, y1)
                  << QPointF(x0, y1);
        overlays.push_back(o);
        OverlayHit line;
        line.text = o.text;
        line.format = QStringLiteral("CALIPER");
        line.polygon << cr.p0 << cr.p1 << cr.p1 << cr.p0;
        overlays.push_back(line);
      }
      {
        const int row = result_table_->rowCount();
        result_table_->insertRow(row);
        result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("caliperDist")));
        result_table_->setItem(
            row, 1, new QTableWidgetItem(QString::number(cr.distPx, 'f', 2)));
        result_table_->setItem(row, 2, new QTableWidgetItem(QStringLiteral("px")));
        const int row2 = result_table_->rowCount();
        result_table_->insertRow(row2);
        result_table_->setItem(row2, 0, new QTableWidgetItem(QStringLiteral("measureMm")));
        result_table_->setItem(
            row2, 1, new QTableWidgetItem(QString::number(cr.distMm, 'f', 4)));
        result_table_->setItem(row2, 2, new QTableWidgetItem(QStringLiteral("mm")));
        const int row3 = result_table_->rowCount();
        result_table_->insertRow(row3);
        result_table_->setItem(row3, 0, new QTableWidgetItem(QStringLiteral("caliperOk")));
        result_table_->setItem(row3, 1, new QTableWidgetItem(gate ? QStringLiteral("1")
                                                                  : QStringLiteral("0")));
        result_table_->setItem(row3, 2, new QTableWidgetItem(QStringLiteral("gate")));
      }
    } else if (op == QLatin1String("measure")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap mp = step->params;
      injectFixtureFromVars(mp, flow_vars_);
      if (mp.value(QStringLiteral("followFixture")).toBool() &&
          flow_vars_.contains(QStringLiteral("locateW"))) {
        if (!mp.contains(QStringLiteral("locateW")))
          mp.insert(QStringLiteral("locateW"), flow_vars_.value(QStringLiteral("locateW")));
        if (!mp.contains(QStringLiteral("locateH")))
          mp.insert(QStringLiteral("locateH"), flow_vars_.value(QStringLiteral("locateH")));
      }
      const MeasureResult mr = runMeasure(working, mp);
      const double mMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += mMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("measure"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("measure");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = (mr.ok && (!mr.judgeEnable || mr.judgeOk)) ? 1 : 0;
      put(QStringLiteral("Count"), mr.count);
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Mode"), mr.mode);
      put(QStringLiteral("Unit"), mr.unit);
      put(QStringLiteral("Px"), mr.valuePx);
      put(QStringLiteral("Value"), mr.value);
      put(QStringLiteral("Mm"), mr.value);
      put(QStringLiteral("Radius"), mr.radiusPx);
      put(QStringLiteral("Diameter"), mr.diameterPx);
      put(QStringLiteral("RadiusMm"), mr.radius);
      put(QStringLiteral("DiameterMm"), mr.diameter);
      put(QStringLiteral("Length"), mr.lengthPx);
      put(QStringLiteral("LengthMm"), mr.length);
      put(QStringLiteral("Angle"), mr.angleDeg);
      put(QStringLiteral("Width"), mr.widthPx);
      put(QStringLiteral("Height"), mr.heightPx);
      put(QStringLiteral("Area"), mr.areaPx);
      put(QStringLiteral("X"), mr.center.x());
      put(QStringLiteral("Y"), mr.center.y());
      put(QStringLiteral("X1"), mr.p0.x());
      put(QStringLiteral("Y1"), mr.p0.y());
      put(QStringLiteral("X2"), mr.p1.x());
      put(QStringLiteral("Y2"), mr.p1.y());
      put(QStringLiteral("Dist"), mr.lengthPx > 0 ? mr.lengthPx : mr.valuePx);
      if (prefix == QLatin1String("measure") && mr.mode == QLatin1String("caliper")) {
        flow_vars_.insert(QStringLiteral("measureMm"), mr.value);
        flow_vars_.insert(QStringLiteral("caliperDist"), mr.valuePx);
        flow_vars_.insert(QStringLiteral("caliperOk"), okI);
        flow_vars_.insert(QStringLiteral("caliperMm"), mr.value);
      }
      if (mp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(mp, working.width(), working.height());
        if (fr.active) {
          put(QStringLiteral("RoiX"), fr.center.x());
          put(QStringLiteral("RoiY"), fr.center.y());
          if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
            OverlayHit fo;
            fo.format = QStringLiteral("FOLLOW");
            fo.text = QStringLiteral("跟随ROI");
            fo.polygon = fr.corners;
            overlays.push_back(fo);
          }
        }
      }
      if (step->params.value(QStringLiteral("writePassGate")).toBool())
        flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.count = mr.count;
        snap.ok = okI != 0;
        snap.matches = mr.count;
        snap.score = mr.valuePx;
        snap.text = mr.note;
        snap.fields.insert(QStringLiteral("value"), mr.value);
        snap.fields.insert(QStringLiteral("px"), mr.valuePx);
        step_snaps.insert(id, snap);
      }
      ok = mr.ok && (!mr.judgeEnable || mr.judgeOk);
      if (!mr.ok) ok = false;
      note = mr.ok ? QStringLiteral("%1 · %2 ms").arg(mr.note).arg(mMs, 0, 'f', 1)
                   : (mr.error.isEmpty() ? mr.note : mr.error);
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
        const bool showLab =
            !step->params.contains(QStringLiteral("showLabels")) ||
            step->params.value(QStringLiteral("showLabels")).toBool();
        int idx = 1;
        for (const MeasureItem& it : mr.items) {
          OverlayHit o;
          o.format = QStringLiteral("MEASURE");
          if (showLab) {
            if (it.kind == QLatin1String("circle"))
              o.text = QStringLiteral("d=%1").arg(it.diameterPx, 0, 'f', 1);
            else if (it.kind == QLatin1String("angle"))
              o.text = QStringLiteral("%1deg").arg(it.angleDeg, 0, 'f', 1);
            else if (it.kind == QLatin1String("line") || it.kind == QLatin1String("points") ||
                     it.kind == QLatin1String("caliper"))
              o.text = QStringLiteral("L=%1").arg(it.lengthPx, 0, 'f', 1);
            else
              o.text = QStringLiteral("%1x%2")
                           .arg(it.widthPx, 0, 'f', 0)
                           .arg(it.heightPx, 0, 'f', 0);
            if (idx > 1) o.text = QStringLiteral("%1 ").arg(idx) + o.text;
          }
          if (it.polygon.size() >= 2)
            o.polygon = it.polygon;
          overlays.push_back(o);
          ++idx;
        }
      }
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI),
               QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Px"), QString::number(mr.valuePx, 'f', 2),
               mr.mode == QLatin1String("angle") ? QStringLiteral("deg")
                                                : QStringLiteral("px"));
        if (mr.calibrated && mr.mode != QLatin1String("angle"))
          addRow(prefix + QStringLiteral("Value"), QString::number(mr.value, 'f', 3),
                 mr.unit);
        if (mr.mode == QLatin1String("circles")) {
          addRow(prefix + QStringLiteral("Diameter"),
                 QString::number(mr.diameterPx, 'f', 2), QStringLiteral("px"));
          addRow(prefix + QStringLiteral("Radius"),
                 QString::number(mr.radiusPx, 'f', 2), QStringLiteral("px"));
        } else if (mr.mode == QLatin1String("lines") ||
                   mr.mode == QLatin1String("points")) {
          addRow(prefix + QStringLiteral("Length"),
                 QString::number(mr.lengthPx, 'f', 2), QStringLiteral("px"));
        } else if (mr.mode == QLatin1String("angle")) {
          addRow(prefix + QStringLiteral("Angle"),
                 QString::number(mr.angleDeg, 'f', 2), QStringLiteral("deg"));
        }
      }
    } else if (op == QLatin1String("region")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap rp = step->params;
      injectFixtureFromVars(rp, flow_vars_);
      if (rp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(rp, working.width(), working.height());
        if (fr.active && !fr.aabb.isEmpty()) {
          rp.insert(QStringLiteral("roiX"), fr.aabb.x());
          rp.insert(QStringLiteral("roiY"), fr.aabb.y());
          rp.insert(QStringLiteral("roiW"), fr.aabb.width());
          rp.insert(QStringLiteral("roiH"), fr.aabb.height());
        }
      }
      const RegionResult rr = runRegionAnalyze(working, rp);
      const double rMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += rMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("region"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("region");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const RegionBlob b0 = rr.items.isEmpty() ? RegionBlob{} : rr.items.first();
      const int okI = (rr.ok && rr.count >= 1) ? 1 : 0;
      put(QStringLiteral("Count"), rr.count);
      put(QStringLiteral("RawCount"), rr.rawCount);
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Method"), rr.method);
      put(QStringLiteral("Threshold"), rr.thresholdUsed);
      put(QStringLiteral("SeedCount"), rr.seedCount);
      put(QStringLiteral("X"), b0.centroid.x());
      put(QStringLiteral("Y"), b0.centroid.y());
      put(QStringLiteral("Area"), b0.areaPixels);
      put(QStringLiteral("Circularity"), b0.circularity);
      put(QStringLiteral("Orientation"), b0.orientationDeg);
      put(QStringLiteral("GrayMean"), b0.grayMean);
      put(QStringLiteral("GrayMin"), b0.grayMin);
      put(QStringLiteral("GrayMax"), b0.grayMax);
      put(QStringLiteral("Width"), b0.bbox.width());
      put(QStringLiteral("Height"), b0.bbox.height());
      put(QStringLiteral("Major"), b0.majorAxisPx);
      put(QStringLiteral("Minor"), b0.minorAxisPx);
      if (prefix == QLatin1String("region")) {
        flow_vars_.insert(QStringLiteral("region_count"), rr.count);
        flow_vars_.insert(QStringLiteral("region_ok"), okI);
      }
      const QString outMode =
          step->params.value(QStringLiteral("output"), QStringLiteral("overlay")).toString();
      if (outMode == QLatin1String("mask") && !rr.mask.isNull())
        working = rr.mask.convertToFormat(QImage::Format_RGB888);
      const bool writeGate = step->params.value(QStringLiteral("writePassGate")).toBool();
      if (writeGate) flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.count = rr.count;
        snap.ok = rr.ok && rr.count >= 1;
        snap.matches = rr.count;
        snap.score = b0.areaPixels;
        snap.text = rr.note;
        snap.fields.insert(QStringLiteral("count"), rr.count);
        snap.fields.insert(QStringLiteral("area"), b0.areaPixels);
        step_snaps.insert(id, snap);
      }
      ok = rr.ok;
      note = rr.ok ? QStringLiteral("%1 · %2 ms").arg(rr.note).arg(rMs, 0, 'f', 1)
                   : rr.error;
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
        const bool showLab =
            !step->params.contains(QStringLiteral("showLabels")) ||
            step->params.value(QStringLiteral("showLabels")).toBool();
        if (rp.value(QStringLiteral("followFixture")).toBool()) {
          const FollowRoi fr = resolveFollowRoi(rp, working.width(), working.height());
          if (fr.active) {
            OverlayHit fo;
            fo.format = QStringLiteral("FOLLOW");
            fo.text = QStringLiteral("跟随ROI");
            fo.polygon = fr.corners;
            overlays.push_back(fo);
          }
        }
        for (const RegionBlob& it : rr.items) {
          OverlayHit o;
          o.format = QStringLiteral("REGION");
          o.text = showLab ? QStringLiteral("A%1").arg(it.areaPixels) : QString();
          const QRect rct = it.bbox;
          o.polygon << rct.topLeft() << rct.topRight() << rct.bottomRight()
                    << rct.bottomLeft();
          overlays.push_back(o);
        }
      }
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Count"), QString::number(rr.count),
               QStringLiteral("count"));
        addRow(prefix + QStringLiteral("Threshold"), QString::number(rr.thresholdUsed),
               QStringLiteral("gray"));
        int rowLimit = 0;
        for (const RegionBlob& it : rr.items) {
          if (rowLimit++ >= 20) break;
          addRow(QStringLiteral("%1#%2.Area").arg(prefix).arg(it.label),
                 QString::number(it.areaPixels), QStringLiteral("px"));
          addRow(QStringLiteral("%1#%2.XY").arg(prefix).arg(it.label),
                 QStringLiteral("%1,%2")
                     .arg(it.centroid.x(), 0, 'f', 1)
                     .arg(it.centroid.y(), 0, 'f', 1),
                 QStringLiteral("px"));
          addRow(QStringLiteral("%1#%2.Circ").arg(prefix).arg(it.label),
                 QString::number(it.circularity, 'f', 3), QStringLiteral("ratio"));
          addRow(QStringLiteral("%1#%2.Gray").arg(prefix).arg(it.label),
                 QString::number(it.grayMean, 'f', 1), QStringLiteral("gray"));
        }
      }
    } else if (op == QLatin1String("defects")) {

      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap dp = step->params;
      injectFixtureFromVars(dp, flow_vars_);
      if (dp.value(QStringLiteral("followFixture")).toBool() &&
          flow_vars_.contains(QStringLiteral("locateW"))) {
        if (!dp.contains(QStringLiteral("locateW")))
          dp.insert(QStringLiteral("locateW"), flow_vars_.value(QStringLiteral("locateW")));
        if (!dp.contains(QStringLiteral("locateH")))
          dp.insert(QStringLiteral("locateH"), flow_vars_.value(QStringLiteral("locateH")));
      }
      QString refErr;
      const QImage ref = resolveDefectsReference(working, dp, &refErr);
      DefectResult dr = runDefects(working, ref, dp);
      if (!dr.ok && dr.error.isEmpty()) dr.error = refErr;
      const double defMs = std::chrono::duration<double, std::milli>(
                               std::chrono::steady_clock::now() - t0)
                               .count();
      algoMs += defMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("defects"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("defects");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = (dr.ok && dr.passed) ? 1 : 0;
      put(QStringLiteral("Count"), dr.count);
      put(QStringLiteral("Ratio"), dr.defectRatio);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("MaxArea"), dr.maxArea);
      put(QStringLiteral("TotalArea"), dr.totalArea);
      if (prefix == QLatin1String("defects")) {
        flow_vars_.insert(QStringLiteral("defects_count"), dr.count);
        flow_vars_.insert(QStringLiteral("defects_ratio"), dr.defectRatio);
        flow_vars_.insert(QStringLiteral("defects_passed"), okI);
      }
      if (dp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(dp, working.width(), working.height());
        if (fr.active) {
          put(QStringLiteral("RoiX"), fr.center.x());
          put(QStringLiteral("RoiY"), fr.center.y());
          if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
            OverlayHit fo;
            fo.format = QStringLiteral("FOLLOW");
            fo.text = QStringLiteral("跟随ROI");
            fo.polygon = fr.corners;
            overlays.push_back(fo);
          }
        }
      }
      const bool writeGate = step->params.value(QStringLiteral("writePassGate")).toBool();
      if (writeGate) flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.count = dr.count;
        snap.ok = dr.ok && dr.passed;
        snap.matches = dr.count;
        snap.score = dr.defectRatio;
        snap.text = dr.note;
        snap.fields.insert(QStringLiteral("count"), dr.count);
        snap.fields.insert(QStringLiteral("ratio"), dr.defectRatio);
        step_snaps.insert(id, snap);
      }
      ok = dr.ok && (dr.passed || !dr.judgeEnable);
      // algo failure (no ref) is NG even if judge is off
      if (!dr.ok) ok = false;
      note = dr.ok ? QStringLiteral("%1 · %2 ms").arg(dr.note).arg(defMs, 0, 'f', 1)
                   : dr.error;
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
        const bool showLab =
            !step->params.contains(QStringLiteral("showLabels")) ||
            step->params.value(QStringLiteral("showLabels")).toBool();
        for (const DefectItem& it : dr.items) {
          OverlayHit o;
          o.text = showLab ? QStringLiteral("A%1").arg(it.areaPixels) : QString();
          o.format = QStringLiteral("DEFECT");
          const QRect rct = it.bbox;
          o.polygon << rct.topLeft() << rct.topRight() << rct.bottomRight()
                    << rct.bottomLeft();
          overlays.push_back(o);
        }
      }
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Count"), QString::number(dr.count),
               QStringLiteral("count"));
        addRow(prefix + QStringLiteral("Ratio"),
               QString::number(dr.defectRatio, 'f', 5), QStringLiteral("ratio"));
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI),
               QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("MaxArea"), QString::number(dr.maxArea),
               QStringLiteral("px"));
      }
    } else if (op == QLatin1String("geometry")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap gp = step->params;
      injectFixtureFromVars(gp, flow_vars_);
      if (gp.value(QStringLiteral("followFixture")).toBool() &&
          flow_vars_.contains(QStringLiteral("locateW"))) {
        if (!gp.contains(QStringLiteral("locateW")))
          gp.insert(QStringLiteral("locateW"), flow_vars_.value(QStringLiteral("locateW")));
        if (!gp.contains(QStringLiteral("locateH")))
          gp.insert(QStringLiteral("locateH"), flow_vars_.value(QStringLiteral("locateH")));
      }
      GeometryResult gr = runGeometry(working, gp);
      const double gMs = std::chrono::duration<double, std::milli>(
                             std::chrono::steady_clock::now() - t0)
                             .count();
      algoMs += gMs;
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("geom"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("geom");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const GeometryItem g0 = gr.items.isEmpty() ? GeometryItem{} : gr.items.first();
      const int okI = (gr.ok && (!gr.judgeEnable || gr.judgeOk) && gr.count >= 1) ? 1 : 0;
      put(QStringLiteral("Count"), gr.count);
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Passed"), okI);
      put(QStringLiteral("Feature"), gr.feature);
      put(QStringLiteral("EdgePixels"), gr.edgePixels);
      put(QStringLiteral("X"), g0.center.x());
      put(QStringLiteral("Y"), g0.center.y());
      put(QStringLiteral("Radius"), g0.radius);
      put(QStringLiteral("Diameter"), g0.diameter);
      put(QStringLiteral("Length"), g0.length);
      put(QStringLiteral("Angle"), g0.angleDeg);
      put(QStringLiteral("Area"), g0.area);
      put(QStringLiteral("Width"), g0.width);
      put(QStringLiteral("Height"), g0.height);
      put(QStringLiteral("Perimeter"), g0.perimeter);
      put(QStringLiteral("Circularity"), g0.circularity);
      put(QStringLiteral("X1"), g0.start.x());
      put(QStringLiteral("Y1"), g0.start.y());
      put(QStringLiteral("X2"), g0.end.x());
      put(QStringLiteral("Y2"), g0.end.y());
      if (gp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(gp, working.width(), working.height());
        if (fr.active) {
          put(QStringLiteral("RoiX"), fr.center.x());
          put(QStringLiteral("RoiY"), fr.center.y());
          if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
            OverlayHit fo;
            fo.format = QStringLiteral("FOLLOW");
            fo.text = QStringLiteral("跟随ROI");
            fo.polygon = fr.corners;
            overlays.push_back(fo);
          }
        }
      }
      const bool writeGate = step->params.value(QStringLiteral("writePassGate")).toBool();
      if (writeGate) flow_vars_.insert(QStringLiteral("passGate"), okI);
      {
        StepSnap snap;
        snap.count = gr.count;
        snap.ok = okI != 0;
        snap.matches = gr.count;
        snap.score = g0.radius > 0 ? g0.radius : (g0.length > 0 ? g0.length : g0.area);
        snap.text = gr.note;
        snap.fields.insert(QStringLiteral("count"), gr.count);
        snap.fields.insert(QStringLiteral("x"), g0.center.x());
        snap.fields.insert(QStringLiteral("y"), g0.center.y());
        step_snaps.insert(id, snap);
      }
      ok = gr.ok && (!gr.judgeEnable || gr.judgeOk);
      if (!gr.ok) ok = false;
      note = gr.ok ? QStringLiteral("%1 · %2 ms").arg(gr.note).arg(gMs, 0, 'f', 1)
                   : (gr.error.isEmpty() ? gr.note : gr.error);
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
        const bool showLab =
            !step->params.contains(QStringLiteral("showLabels")) ||
            step->params.value(QStringLiteral("showLabels")).toBool();
        int idx = 1;
        for (const GeometryItem& it : gr.items) {
          OverlayHit o;
          o.format = QStringLiteral("GEOM");
          if (showLab) {
            if (it.kind == QLatin1String("circle"))
              o.text = QStringLiteral("%1 r=%2").arg(idx).arg(it.radius, 0, 'f', 1);
            else if (it.kind == QLatin1String("line"))
              o.text = QStringLiteral("%1 L=%2").arg(idx).arg(it.length, 0, 'f', 1);
            else if (it.kind == QLatin1String("rect"))
              o.text = QStringLiteral("%1 %2x%3")
                           .arg(idx)
                           .arg(it.width, 0, 'f', 0)
                           .arg(it.height, 0, 'f', 0);
            else
              o.text = QStringLiteral("%1 A=%2").arg(idx).arg(int(it.area));
          }
          if (it.polygon.size() >= 2)
            o.polygon = it.polygon;
          else if (it.bbox.isValid()) {
            const QRectF b = it.bbox;
            o.polygon << b.topLeft() << b.topRight() << b.bottomRight()
                      << b.bottomLeft();
          }
          overlays.push_back(o);
          ++idx;
        }
      }
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Count"), QString::number(gr.count),
               QStringLiteral("count"));
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI),
               QStringLiteral("gate"));
        if (gr.feature == QLatin1String("circles")) {
          addRow(prefix + QStringLiteral("X"), QString::number(g0.center.x(), 'f', 2),
                 QStringLiteral("px"));
          addRow(prefix + QStringLiteral("Y"), QString::number(g0.center.y(), 'f', 2),
                 QStringLiteral("px"));
          addRow(prefix + QStringLiteral("Radius"),
                 QString::number(g0.radius, 'f', 2), QStringLiteral("px"));
        } else if (gr.feature == QLatin1String("lines")) {
          addRow(prefix + QStringLiteral("Length"),
                 QString::number(g0.length, 'f', 2), QStringLiteral("px"));
          addRow(prefix + QStringLiteral("Angle"),
                 QString::number(g0.angleDeg, 'f', 2), QStringLiteral("deg"));
        } else if (gr.feature == QLatin1String("edges")) {
          addRow(prefix + QStringLiteral("EdgePixels"),
                 QString::number(gr.edgePixels), QStringLiteral("px"));
        } else {
          addRow(prefix + QStringLiteral("Area"), QString::number(g0.area, 'f', 1),
                 QStringLiteral("px"));
        }
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
      if (target == QLatin1String("formatted") || target.isEmpty())
        flow_vars_.insert(QStringLiteral("formatted"), out);
      if (target == QLatin1String("commPayload") || target == QLatin1String("formatted") ||
          target.isEmpty())
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
      const QString dir = workbenchResolveArtifactsDir(
          step->params
              .value(QStringLiteral("dir"), workbenchArtifactsDir())
              .toString());
      QDir().mkpath(dir);
      const QString path =
          dir + QStringLiteral("/sieans-qt-run-%1.png")
                    .arg(QDateTime::currentDateTime().toString(
                        QStringLiteral("HHmmss")));
      ok = working.save(path);
      note = path;
    } else if (op == QLatin1String("condition") || op == QLatin1String("branch")) {
      QVariantMap params = step->params;
      const QByteArray rightOv = qgetenv("SIEANS_QT_CONDITION_RIGHT");
      if (op == QLatin1String("condition") && !rightOv.isEmpty()) {
        params.insert(QStringLiteral("right"), QString::fromUtf8(rightOv));
        QVariantList rules = params.value(QStringLiteral("rules")).toList();
        if (rules.isEmpty()) {
          QVariantMap r0;
          r0.insert(QStringLiteral("left"), params.value(QStringLiteral("left")));
          r0.insert(QStringLiteral("comparison"), params.value(QStringLiteral("comparison")));
          r0.insert(QStringLiteral("right"), QString::fromUtf8(rightOv));
          r0.insert(QStringLiteral("enabled"), true);
          rules.push_back(r0);
        } else {
          QVariantMap r0 = rules.first().toMap();
          r0.insert(QStringLiteral("right"), QString::fromUtf8(rightOv));
          rules[0] = r0;
        }
        params.insert(QStringLiteral("rules"), rules);
      }
      const ConditionResult cr = (op == QLatin1String("branch"))
                                     ? evaluateBranch(params, flow_vars_)
                                     : evaluateCondition(params, flow_vars_);
      if (!cr.ok) {
        ok = false;
        note = cr.error;
        flow_vars_.insert(QStringLiteral("conditionOk"), 0);
        flow_vars_.insert(QStringLiteral("conditionPassed"), 0);
        flow_vars_.insert(QStringLiteral("branchTaken"), QString());
        NodeExec ng;
        ng.executed = true;
        ng.ok = false;
        ng.evalFailed = true;
        execInfo.insert(id, ng);
      } else {
        ok = true;
        note = cr.note;
        flow_vars_.insert(QStringLiteral("conditionOk"), 1);
        flow_vars_.insert(QStringLiteral("conditionPassed"), cr.passed ? 1 : 0);
        flow_vars_.insert(QStringLiteral("branchTaken"), cr.branchTaken);
        const bool writeGate =
            !params.contains(QStringLiteral("writePassGate")) ||
            params.value(QStringLiteral("writePassGate")).toBool();
        if (writeGate && op == QLatin1String("condition"))
          flow_vars_.insert(QStringLiteral("passGate"), cr.passed ? 1 : 0);
        NodeExec nx;
        nx.executed = true;
        nx.ok = true;
        nx.passed = cr.passed;
        nx.branchTaken = cr.branchTaken;
        execInfo.insert(id, nx);
      }
      if (result_table_) {
        const int row = result_table_->rowCount();
        result_table_->insertRow(row);
        result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("condition.passed")));
        result_table_->setItem(
            row, 1,
            new QTableWidgetItem(flow_vars_.value(QStringLiteral("conditionPassed")).toString()));
        const int row2 = result_table_->rowCount();
        result_table_->insertRow(row2);
        result_table_->setItem(row2, 0, new QTableWidgetItem(QStringLiteral("condition.branchTaken")));
        result_table_->setItem(
            row2, 1, new QTableWidgetItem(flow_vars_.value(QStringLiteral("branchTaken")).toString()));
      }
    } else if (op == QLatin1String("branch_merge")) {
      const FlowStep* src = document_.findStep(mergeFromId);
      const QString fromName = src ? src->name : mergeFromId;
      flow_vars_.insert(QStringLiteral("mergeFrom"), fromName);
      note = QStringLiteral("汇合自 %1").arg(fromName);
      ok = true;
      NodeExec nx;
      nx.executed = true;
      nx.ok = true;
      nx.mergeFrom = fromName;
      execInfo.insert(id, nx);
    } else if (op == QLatin1String("subflow") || op == QLatin1String("loop")) {
      const bool isLoop = op == QLatin1String("loop");
      const SubflowCallParams cp = parseSubflowParams(step->params, isLoop);
      const SubflowDef* def = document_.findSubflow(cp.subflowId);
      if (!def) {
        ok = false;
        note = cp.subflowId.isEmpty() ? QStringLiteral("请选择子流程")
                                      : QStringLiteral("子流程不存在: %1").arg(cp.subflowId);
        NodeExec ng;
        ng.executed = true;
        ng.ok = false;
        execInfo.insert(id, ng);
      } else {
        SubflowState* st = nullptr;
        if (cp.stateMode == QLatin1String("preserve")) st = &subflow_states_[id];
        int visits = 0;
        const SubflowResult r = runSubflowCall(*def, document_.subflows(), cp, flow_vars_,
                                               st, 0, visits, {});
        if (!r.ok) {
          ok = false;
          note = r.error;
          NodeExec ng;
          ng.executed = true;
          ng.ok = false;
          execInfo.insert(id, ng);
        } else {
          ok = true;
          note = r.note;
          if (isLoop) {
            flow_vars_.insert(QStringLiteral("loopCompleted"), r.completedIterations);
            flow_vars_.insert(QStringLiteral("loopStoppedEarly"), r.stoppedEarly ? 1 : 0);
            flow_vars_.insert(QStringLiteral("loopCount"),
                             r.localVars.value(QStringLiteral("count"),
                                               r.value.value(QStringLiteral("count"))));
            flow_vars_.insert(QStringLiteral("loopPassed"), r.passed ? 1 : 0);
          } else {
            flow_vars_.insert(QStringLiteral("subflowPassed"), r.passed ? 1 : 0);
            flow_vars_.insert(QStringLiteral("subflowCount"),
                             r.localVars.value(QStringLiteral("count"),
                                               r.value.value(QStringLiteral("count"))));
          }
          NodeExec nx;
          nx.executed = true;
          nx.ok = true;
          nx.passed = r.passed;
          execInfo.insert(id, nx);
        }
      }
      if (result_table_) {
        if (!isLoop) {
          int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("subflowPassed")));
          result_table_->setItem(
              row, 1,
              new QTableWidgetItem(flow_vars_.value(QStringLiteral("subflowPassed")).toString()));
          row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("subflowCount")));
          result_table_->setItem(
              row, 1,
              new QTableWidgetItem(flow_vars_.value(QStringLiteral("subflowCount")).toString()));
        } else {
          int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("loopCompleted")));
          result_table_->setItem(
              row, 1,
              new QTableWidgetItem(flow_vars_.value(QStringLiteral("loopCompleted")).toString()));
          row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("loopStoppedEarly")));
          result_table_->setItem(
              row, 1,
              new QTableWidgetItem(
                  flow_vars_.value(QStringLiteral("loopStoppedEarly")).toString()));
          row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("loopCount")));
          result_table_->setItem(
              row, 1,
              new QTableWidgetItem(flow_vars_.value(QStringLiteral("loopCount")).toString()));
          row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(QStringLiteral("loopPassed")));
          result_table_->setItem(
              row, 1,
              new QTableWidgetItem(flow_vars_.value(QStringLiteral("loopPassed")).toString()));
        }
      }
    } else if (op == QLatin1String("serial_exchange")) {
      QVariantMap sp = step->params;
      if (sp.contains(QStringLiteral("value"))) {
        const QString expanded =
            CommHub::expandTemplate(sp.value(QStringLiteral("value")).toString(), flow_vars_);
        sp.insert(QStringLiteral("value"), expanded);
      }
      const SerialResult sr = runSerialExchange(sp);
      QString prefix =
          step->params.value(QStringLiteral("resultVar"), QStringLiteral("serial"))
              .toString()
              .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("serial");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = sr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Rx"), sr.value);
      put(QStringLiteral("Tx"), sr.sentValue);
      put(QStringLiteral("Bytes"), sr.byteLength);
      put(QStringLiteral("SentBytes"), sr.sentBytes);
      put(QStringLiteral("Port"), sr.serialPort);
      put(QStringLiteral("Mode"), sr.mode);
      put(QStringLiteral("Sim"), sr.simulated ? 1 : 0);
      put(QStringLiteral("Elapsed"), sr.elapsedMs);
      put(QStringLiteral("Trailing"), sr.trailingBytes);
      put(QStringLiteral("Discarded"), sr.discardedInputBytes);
      put(QStringLiteral("Delivery"), sr.delivery);
      put(QStringLiteral("Error"), sr.error);
      ok = sr.ok;
      note = sr.ok ? sr.note : sr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI),
               QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Rx"), sr.value, QStringLiteral("text"));
        addRow(prefix + QStringLiteral("Tx"), sr.sentValue, QStringLiteral("text"));
        addRow(prefix + QStringLiteral("Bytes"), QString::number(sr.byteLength),
               QStringLiteral("bytes"));
        addRow(prefix + QStringLiteral("Port"), sr.serialPort, QStringLiteral("port"));
      }
    } else if (op == QLatin1String("modbus_read") ||
               op == QLatin1String("modbus_write") ||
               op == QLatin1String("modbus_wait")) {
      QVariantMap mp = step->params;
      if (mp.contains(QStringLiteral("value")) &&
          mp.value(QStringLiteral("value")).typeId() == QMetaType::QString) {
        const QString expanded = CommHub::expandTemplate(
            mp.value(QStringLiteral("value")).toString(), flow_vars_);
        // 纯数字模板展开后仍按数值写入，避免把 "4242" 当成非法结构。
        bool isNum = false;
        const double d = expanded.toDouble(&isNum);
        if (isNum && !expanded.contains(QLatin1Char(' '))) {
          if (expanded.contains(QLatin1Char('.')))
            mp.insert(QStringLiteral("value"), d);
          else
            mp.insert(QStringLiteral("value"), expanded.toLongLong());
        } else if (expanded == QLatin1String("true") || expanded == QLatin1String("false")) {
          mp.insert(QStringLiteral("value"), expanded == QLatin1String("true"));
        } else {
          mp.insert(QStringLiteral("value"), expanded);
        }
      }
      ModbusResult mr;
      if (op == QLatin1String("modbus_write"))
        mr = runModbusWrite(mp);
      else if (op == QLatin1String("modbus_wait"))
        mr = runModbusWait(mp);
      else
        mr = runModbusRead(mp);
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty()) {
        if (op == QLatin1String("modbus_write"))
          prefix = QStringLiteral("mbWrite");
        else if (op == QLatin1String("modbus_wait"))
          prefix = QStringLiteral("mbWait");
        else
          prefix = QStringLiteral("mbRead");
      }
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = mr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Value"), mr.value);
      put(QStringLiteral("Values"), mr.values);
      put(QStringLiteral("Registers"), mr.registers);
      put(QStringLiteral("Count"), mr.count);
      put(QStringLiteral("Address"), mr.address);
      put(QStringLiteral("Area"), mr.area);
      put(QStringLiteral("Protocol"), mr.protocol);
      put(QStringLiteral("Ack"), mr.acknowledged ? 1 : 0);
      put(QStringLiteral("Triggered"), mr.triggered ? 1 : 0);
      put(QStringLiteral("Passed"), mr.passed ? 1 : 0);
      put(QStringLiteral("Samples"), mr.samples);
      put(QStringLiteral("Reason"), mr.reason);
      put(QStringLiteral("Error"), mr.error);
      put(QStringLiteral("Elapsed"), mr.elapsedMs);
      ok = mr.ok;
      note = mr.ok ? mr.note : mr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Value"), mr.value.toString(), mr.dataType);
        if (op == QLatin1String("modbus_write"))
          addRow(prefix + QStringLiteral("Ack"), QString::number(mr.acknowledged ? 1 : 0),
                 QStringLiteral("ack"));
        if (op == QLatin1String("modbus_wait"))
          addRow(prefix + QStringLiteral("Triggered"),
                 QString::number(mr.triggered ? 1 : 0), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Protocol"), mr.protocol, QStringLiteral("proto"));
      }
    } else if (op == QLatin1String("s7_read") || op == QLatin1String("s7_write")) {
      QVariantMap mp = step->params;
      if (mp.contains(QStringLiteral("value")) &&
          mp.value(QStringLiteral("value")).typeId() == QMetaType::QString) {
        const QString expanded = CommHub::expandTemplate(
            mp.value(QStringLiteral("value")).toString(), flow_vars_);
        bool isNum = false;
        const double d = expanded.toDouble(&isNum);
        if (isNum && !expanded.contains(QLatin1Char(' '))) {
          if (expanded.contains(QLatin1Char('.')))
            mp.insert(QStringLiteral("value"), d);
          else
            mp.insert(QStringLiteral("value"), expanded.toLongLong());
        } else if (expanded == QLatin1String("true") || expanded == QLatin1String("false")) {
          mp.insert(QStringLiteral("value"), expanded == QLatin1String("true"));
        } else {
          mp.insert(QStringLiteral("value"), expanded);
        }
      }
      const S7Result sr = (op == QLatin1String("s7_write")) ? runS7Write(mp)
                                                            : runS7Read(mp);
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty())
        prefix = (op == QLatin1String("s7_write")) ? QStringLiteral("s7Write")
                                                   : QStringLiteral("s7Read");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = sr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Value"), sr.value);
      put(QStringLiteral("Values"), sr.values);
      put(QStringLiteral("Count"), sr.count);
      put(QStringLiteral("Area"), sr.area);
      put(QStringLiteral("Db"), sr.dbNumber);
      put(QStringLiteral("Offset"), sr.byteOffset);
      put(QStringLiteral("Ack"), sr.acknowledged ? 1 : 0);
      put(QStringLiteral("Error"), sr.error);
      put(QStringLiteral("Elapsed"), sr.elapsedMs);
      put(QStringLiteral("Quality"), sr.quality);
      ok = sr.ok;
      note = sr.ok ? sr.note : sr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Value"), sr.value.toString(), sr.dataType);
        if (op == QLatin1String("s7_write"))
          addRow(prefix + QStringLiteral("Ack"), QString::number(sr.acknowledged ? 1 : 0),
                 QStringLiteral("ack"));
        addRow(prefix + QStringLiteral("Area"),
               QStringLiteral("%1 DB%2.%3").arg(sr.area).arg(sr.dbNumber).arg(sr.byteOffset),
               QStringLiteral("addr"));
      }
    } else if (op == QLatin1String("opcua_read") || op == QLatin1String("opcua_write") ||
               op == QLatin1String("opcua_browse") || op == QLatin1String("opcua_wait")) {
      QVariantMap mp = step->params;
      if (mp.contains(QStringLiteral("value")) &&
          mp.value(QStringLiteral("value")).typeId() == QMetaType::QString) {
        const QString expanded = CommHub::expandTemplate(
            mp.value(QStringLiteral("value")).toString(), flow_vars_);
        bool isNum = false;
        const double d = expanded.toDouble(&isNum);
        if (isNum && !expanded.contains(QLatin1Char(' '))) {
          if (expanded.contains(QLatin1Char('.')))
            mp.insert(QStringLiteral("value"), d);
          else
            mp.insert(QStringLiteral("value"), expanded.toLongLong());
        } else if (expanded == QLatin1String("true") || expanded == QLatin1String("false")) {
          mp.insert(QStringLiteral("value"), expanded == QLatin1String("true"));
        } else {
          mp.insert(QStringLiteral("value"), expanded);
        }
      }
      OpcUaResult orr;
      if (op == QLatin1String("opcua_write"))
        orr = runOpcUaWrite(mp);
      else if (op == QLatin1String("opcua_browse"))
        orr = runOpcUaBrowse(mp);
      else if (op == QLatin1String("opcua_wait"))
        orr = runOpcUaWait(mp);
      else
        orr = runOpcUaRead(mp);
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty()) {
        if (op == QLatin1String("opcua_write"))
          prefix = QStringLiteral("opcWrite");
        else if (op == QLatin1String("opcua_browse"))
          prefix = QStringLiteral("opcBrowse");
        else if (op == QLatin1String("opcua_wait"))
          prefix = QStringLiteral("opcWait");
        else
          prefix = QStringLiteral("opcRead");
      }
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = orr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Value"), orr.value);
      put(QStringLiteral("Ack"), orr.acknowledged ? 1 : 0);
      put(QStringLiteral("Triggered"), orr.triggered ? 1 : 0);
      put(QStringLiteral("Passed"), orr.passed ? 1 : 0);
      put(QStringLiteral("TimedOut"), orr.timedOut ? 1 : 0);
      put(QStringLiteral("Count"), orr.browseCount ? orr.browseCount : orr.notificationCount);
      put(QStringLiteral("Items"), QVariant(orr.items));
      put(QStringLiteral("NodeId"), orr.nodeId);
      put(QStringLiteral("DataType"), orr.dataType);
      put(QStringLiteral("Status"), orr.status);
      put(QStringLiteral("Quality"), orr.quality);
      put(QStringLiteral("Error"), orr.error);
      put(QStringLiteral("Elapsed"), orr.elapsedMs);
      ok = orr.ok;
      note = orr.ok ? orr.note : orr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Value"), orr.value.toString(),
               orr.dataType.isEmpty() ? QStringLiteral("value") : orr.dataType);
        if (op == QLatin1String("opcua_write"))
          addRow(prefix + QStringLiteral("Ack"), QString::number(orr.acknowledged ? 1 : 0),
                 QStringLiteral("ack"));
        if (op == QLatin1String("opcua_wait"))
          addRow(prefix + QStringLiteral("Triggered"),
                 QString::number(orr.triggered ? 1 : 0), QStringLiteral("trig"));
        if (op == QLatin1String("opcua_browse"))
          addRow(prefix + QStringLiteral("Count"), QString::number(orr.browseCount),
                 QStringLiteral("refs"));
        addRow(prefix + QStringLiteral("NodeId"), orr.nodeId, QStringLiteral("addr"));
      }
    } else if (op == QLatin1String("mqtt_publish") ||
               op == QLatin1String("mqtt_receive")) {
      QVariantMap mp = step->params;
      if (mp.contains(QStringLiteral("value")) &&
          mp.value(QStringLiteral("value")).typeId() == QMetaType::QString) {
        const QString expanded = CommHub::expandTemplate(
            mp.value(QStringLiteral("value")).toString(), flow_vars_);
        mp.insert(QStringLiteral("value"), expanded);
      }
      const MqttResult mr = (op == QLatin1String("mqtt_publish")) ? runMqttPublish(mp)
                                                                 : runMqttReceive(mp);
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty())
        prefix = (op == QLatin1String("mqtt_publish")) ? QStringLiteral("mqttPub")
                                                       : QStringLiteral("mqttRecv");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = mr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Value"), mr.value);
      put(QStringLiteral("Ack"), mr.acknowledged ? 1 : 0);
      put(QStringLiteral("Topic"), mr.topic);
      put(QStringLiteral("Qos"), mr.qos);
      put(QStringLiteral("Retained"), mr.retained ? 1 : 0);
      put(QStringLiteral("Delivery"), mr.delivery);
      put(QStringLiteral("Bytes"), mr.byteLength);
      put(QStringLiteral("Error"), mr.error);
      put(QStringLiteral("Elapsed"), mr.elapsedMs);
      ok = mr.ok;
      note = mr.ok ? mr.note : mr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Value"), mr.value.toString(), mr.encoding);
        if (op == QLatin1String("mqtt_publish"))
          addRow(prefix + QStringLiteral("Ack"), QString::number(mr.acknowledged ? 1 : 0),
                 QStringLiteral("ack"));
        addRow(prefix + QStringLiteral("Topic"), mr.topic, QStringLiteral("topic"));
      }
    } else if (op == QLatin1String("yolo") || op == QLatin1String("yolo_segment")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap yp = step->params;
      injectFixtureFromVars(yp, flow_vars_);
      if (yp.value(QStringLiteral("followFixture")).toBool() &&
          flow_vars_.contains(QStringLiteral("locateW"))) {
        if (!yp.contains(QStringLiteral("locateW")))
          yp.insert(QStringLiteral("locateW"), flow_vars_.value(QStringLiteral("locateW")));
        if (!yp.contains(QStringLiteral("locateH")))
          yp.insert(QStringLiteral("locateH"), flow_vars_.value(QStringLiteral("locateH")));
      }
      const bool isSeg = (op == QLatin1String("yolo_segment"));
      YoloResult yr = isSeg ? runYoloSegment(working, yp) : runYoloDetect(working, yp);
      const double yoloMs = std::chrono::duration<double, std::milli>(
                                std::chrono::steady_clock::now() - t0)
                                .count();
      algoMs += yoloMs;
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty())
        prefix = isSeg ? QStringLiteral("yoloSeg") : QStringLiteral("yolo");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int foundI = (yr.ok && yr.count >= 1) ? 1 : 0;
      const double bestScore =
          yr.items.isEmpty() ? 0.0 : yr.items.front().confidence;
      const QString bestLabel =
          yr.items.isEmpty() ? QString() : yr.items.front().label;
      const int bestArea = yr.items.isEmpty() ? 0 : yr.items.front().areaPixels;
      put(QStringLiteral("Ok"), foundI);
      put(QStringLiteral("RunOk"), yr.ok ? 1 : 0);
      put(QStringLiteral("Count"), yr.count);
      put(QStringLiteral("Score"), bestScore);
      put(QStringLiteral("Label"), bestLabel);
      put(QStringLiteral("Class"), yr.items.isEmpty() ? QString()
                                                      : QString::number(yr.items.front().classId));
      put(QStringLiteral("Backend"), yr.backend);
      put(QStringLiteral("Device"), yr.device);
      put(QStringLiteral("Model"), yr.model);
      put(QStringLiteral("Error"), yr.error);
      if (isSeg) {
        put(QStringLiteral("Area"), bestArea);
        put(QStringLiteral("UnionArea"), yr.unionAreaPixels);
        put(QStringLiteral("SummedArea"), yr.summedAreaPixels);
      }
      if (yp.value(QStringLiteral("followFixture")).toBool()) {
        const FollowRoi fr = resolveFollowRoi(yp, working.width(), working.height());
        if (fr.active) {
          put(QStringLiteral("RoiX"), fr.center.x());
          put(QStringLiteral("RoiY"), fr.center.y());
          if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
            OverlayHit fo;
            fo.format = QStringLiteral("FOLLOW");
            fo.text = QStringLiteral("跟随ROI");
            fo.polygon = fr.corners;
            overlays.push_back(fo);
          }
        }
      }
      ok = yr.ok;
      note = yr.ok ? QStringLiteral("%1 · %2 ms").arg(yr.note).arg(yoloMs, 0, 'f', 1)
                   : yr.error;
      if (isSeg && yr.output == QLatin1String("mask") && !yr.mask.isNull()) {
        working = yr.mask;
        if (output_view_) output_view_->setLiveImage(working);
      }
      if (step->params.value(QStringLiteral("showOverlay"), true).toBool()) {
        const bool showLab =
            !step->params.contains(QStringLiteral("showLabels")) ||
            step->params.value(QStringLiteral("showLabels")).toBool();
        for (int i = 0; i < yr.items.size(); ++i) {
          const YoloItem& it = yr.items[i];
          OverlayHit box;
          box.format = isSeg ? QStringLiteral("YOLOSEG") : QStringLiteral("YOLO");
          box.text = showLab ? QStringLiteral("%1 %2").arg(it.label).arg(it.confidence, 0, 'f', 2)
                             : QString();
          const QRectF rct = it.bbox;
          box.polygon << rct.topLeft() << rct.topRight() << rct.bottomRight()
                      << rct.bottomLeft();
          overlays.push_back(box);
          if (isSeg) {
            for (int c = 0; c < it.contours.size(); ++c) {
              OverlayHit ch;
              ch.format = it.contourIsHole.value(c) ? QStringLiteral("YOLOHOLE")
                                                    : QStringLiteral("YOLOMASK");
              ch.text = showLab ? (it.contourIsHole.value(c)
                                       ? QStringLiteral("hole")
                                       : QStringLiteral("A%1").arg(it.areaPixels))
                                : QString();
              for (const QPoint& pt : it.contours[c]) ch.polygon << QPointF(pt);
              if (ch.polygon.size() >= 2) overlays.push_back(ch);
            }
          }
        }
      }
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Count"), QString::number(yr.count),
               QStringLiteral("count"));
        addRow(prefix + QStringLiteral("Score"), QString::number(bestScore, 'f', 3),
               QStringLiteral("score"));
        addRow(prefix + QStringLiteral("Label"), bestLabel, QStringLiteral("class"));
        addRow(prefix + QStringLiteral("Ok"), QString::number(foundI), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Backend"), yr.backend, QStringLiteral("backend"));
        if (isSeg)
          addRow(prefix + QStringLiteral("Area"), QString::number(bestArea),
                 QStringLiteral("px"));
        for (int i = 0; i < yr.items.size(); ++i) {
          const YoloItem& it = yr.items[i];
          addRow(QStringLiteral("%1[%2].label").arg(prefix).arg(i), it.label,
                 QStringLiteral("class"));
          addRow(QStringLiteral("%1[%2].score").arg(prefix).arg(i),
                 QString::number(it.confidence, 'f', 3), QStringLiteral("score"));
          if (isSeg)
            addRow(QStringLiteral("%1[%2].area").arg(prefix).arg(i),
                   QString::number(it.areaPixels), QStringLiteral("px"));
        }
      }
    } else if (op == QLatin1String("cloud_filter") || op == QLatin1String("cloud_plane") ||
               op == QLatin1String("cloud_cluster") || op == QLatin1String("cloud_measure") ||
               op == QLatin1String("cloud_height") || op == QLatin1String("cloud_register")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap cp = step->params;
      QString inErr;
      PointCloud inCloud = resolveCloudInput(workingCloud, cp, &inErr);
      CloudResult cr = runCloudOp(op, inCloud, cp);
      if (!cr.ok && cr.error.isEmpty()) cr.error = inErr;
      const double cloudMs = std::chrono::duration<double, std::milli>(
                                 std::chrono::steady_clock::now() - t0)
                                 .count();
      algoMs += cloudMs;
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty()) {
        if (op == QLatin1String("cloud_filter")) prefix = QStringLiteral("cloudFilt");
        else if (op == QLatin1String("cloud_plane")) prefix = QStringLiteral("cloudPlane");
        else if (op == QLatin1String("cloud_cluster")) prefix = QStringLiteral("cloudClust");
        else if (op == QLatin1String("cloud_measure")) prefix = QStringLiteral("cloudMeas");
        else if (op == QLatin1String("cloud_height")) prefix = QStringLiteral("cloudHgt");
        else prefix = QStringLiteral("cloudReg");
      }
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      const int okI = cr.ok ? 1 : 0;
      put(QStringLiteral("Ok"), okI);
      put(QStringLiteral("Count"), cr.pointCount);
      put(QStringLiteral("InputCount"), cr.inputCount);
      put(QStringLiteral("Backend"), cr.backend);
      put(QStringLiteral("Error"), cr.error);
      put(QStringLiteral("Unit"), cr.cloud.unit.isEmpty() ? QString() : cr.cloud.unit);
      if (op == QLatin1String("cloud_filter")) {
        put(QStringLiteral("Method"), cr.method);
      } else if (op == QLatin1String("cloud_plane")) {
        put(QStringLiteral("Inliers"), cr.inlierCount);
        put(QStringLiteral("InlierRatio"), cr.inlierRatio);
        put(QStringLiteral("Rms"), cr.rmsError);
        put(QStringLiteral("Nx"), cr.nx);
        put(QStringLiteral("Ny"), cr.ny);
        put(QStringLiteral("Nz"), cr.nz);
        put(QStringLiteral("D"), cr.d);
        put(QStringLiteral("Output"), cr.output);
      } else if (op == QLatin1String("cloud_cluster")) {
        put(QStringLiteral("Count"), cr.clusterCount);
        put(QStringLiteral("Noise"), cr.noiseCount);
        put(QStringLiteral("PointCount"), cr.pointCount);
      } else if (op == QLatin1String("cloud_measure")) {
        put(QStringLiteral("SizeX"), cr.bounds.sizeX);
        put(QStringLiteral("SizeY"), cr.bounds.sizeY);
        put(QStringLiteral("SizeZ"), cr.bounds.sizeZ);
        put(QStringLiteral("Volume"), cr.bounds.boundingBoxVolume);
        put(QStringLiteral("CenterX"), cr.bounds.centerX);
        put(QStringLiteral("CenterY"), cr.bounds.centerY);
        put(QStringLiteral("CenterZ"), cr.bounds.centerZ);
        put(QStringLiteral("MinX"), cr.bounds.minX);
        put(QStringLiteral("MinY"), cr.bounds.minY);
        put(QStringLiteral("MinZ"), cr.bounds.minZ);
        put(QStringLiteral("MaxX"), cr.bounds.maxX);
        put(QStringLiteral("MaxY"), cr.bounds.maxY);
        put(QStringLiteral("MaxZ"), cr.bounds.maxZ);
      } else if (op == QLatin1String("cloud_height")) {
        put(QStringLiteral("Volume"), cr.estimatedVolume);
        put(QStringLiteral("Max"), cr.maxHeight);
        put(QStringLiteral("Min"), cr.minHeight);
        put(QStringLiteral("Mean"), cr.meanHeight);
        put(QStringLiteral("Cells"), cr.occupiedCells);
        put(QStringLiteral("Area"), cr.sampledArea);
        put(QStringLiteral("BaselineZ"), cr.baselineZ);
        put(QStringLiteral("CellSize"), cr.cellSize);
      } else if (op == QLatin1String("cloud_register")) {
        put(QStringLiteral("Found"), cr.found ? 1 : 0);
        put(QStringLiteral("Dx"), cr.dx);
        put(QStringLiteral("Dy"), cr.dy);
        put(QStringLiteral("Dz"), cr.dz);
        put(QStringLiteral("Fitness"), cr.fitness);
        put(QStringLiteral("Rms"), cr.rmsError);
        put(QStringLiteral("TargetFitness"), cr.targetFitness);
        put(QStringLiteral("Method"), cr.method);
      }
      if (cr.ok) workingCloud = cr.cloud;
      ok = cr.ok;
      note = cr.ok ? QStringLiteral("%1 · %2 ms").arg(cr.note).arg(cloudMs, 0, 'f', 1)
                   : cr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(okI), QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Count"), QString::number(cr.pointCount),
               QStringLiteral("pts"));
        if (op == QLatin1String("cloud_plane")) {
          addRow(prefix + QStringLiteral("Inliers"), QString::number(cr.inlierCount),
                 QStringLiteral("pts"));
          addRow(prefix + QStringLiteral("Rms"), QString::number(cr.rmsError, 'g', 6),
                 QStringLiteral("rms"));
        } else if (op == QLatin1String("cloud_cluster")) {
          addRow(prefix + QStringLiteral("Count"), QString::number(cr.clusterCount),
                 QStringLiteral("clusters"));
          addRow(prefix + QStringLiteral("Noise"), QString::number(cr.noiseCount),
                 QStringLiteral("pts"));
        } else if (op == QLatin1String("cloud_measure")) {
          addRow(prefix + QStringLiteral("SizeX"), QString::number(cr.bounds.sizeX, 'f', 4),
                 cr.cloud.unit);
          addRow(prefix + QStringLiteral("SizeY"), QString::number(cr.bounds.sizeY, 'f', 4),
                 cr.cloud.unit);
          addRow(prefix + QStringLiteral("SizeZ"), QString::number(cr.bounds.sizeZ, 'f', 4),
                 cr.cloud.unit);
          addRow(prefix + QStringLiteral("Volume"),
                 QString::number(cr.bounds.boundingBoxVolume, 'f', 4),
                 cr.cloud.unit + QStringLiteral("³"));
        } else if (op == QLatin1String("cloud_height")) {
          addRow(prefix + QStringLiteral("Volume"),
                 QString::number(cr.estimatedVolume, 'f', 4), cr.volumeUnit);
          addRow(prefix + QStringLiteral("Max"), QString::number(cr.maxHeight, 'f', 4),
                 cr.cloud.unit);
          addRow(prefix + QStringLiteral("Cells"), QString::number(cr.occupiedCells),
                 QStringLiteral("cells"));
        } else if (op == QLatin1String("cloud_register")) {
          addRow(prefix + QStringLiteral("Found"), QString::number(cr.found ? 1 : 0),
                 QStringLiteral("gate"));
          addRow(prefix + QStringLiteral("Dx"), QString::number(cr.dx, 'f', 4), cr.cloud.unit);
          addRow(prefix + QStringLiteral("Dy"), QString::number(cr.dy, 'f', 4), cr.cloud.unit);
          addRow(prefix + QStringLiteral("Dz"), QString::number(cr.dz, 'f', 4), cr.cloud.unit);
          addRow(prefix + QStringLiteral("Fitness"), QString::number(cr.fitness, 'f', 4),
                 QStringLiteral("ratio"));
          addRow(prefix + QStringLiteral("Rms"), QString::number(cr.rmsError, 'g', 6),
                 QStringLiteral("rms"));
        } else {
          addRow(prefix + QStringLiteral("Method"), cr.method, QStringLiteral("method"));
        }
      }
    } else if (op == QLatin1String("delay")) {
      const DelayResult dr = runDelay(step->params, &pipeline_cancel_);
      QString prefix = step->params.value(QStringLiteral("resultVar"), QStringLiteral("delay"))
                           .toString()
                           .trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("delay");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      put(QStringLiteral("Ok"), dr.ok ? 1 : 0);
      put(QStringLiteral("Ms"), dr.milliseconds);
      put(QStringLiteral("Elapsed"), dr.elapsedMs);
      put(QStringLiteral("Cancelled"), dr.cancelled ? 1 : 0);
      ok = dr.ok;
      note = dr.ok ? dr.note : dr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(dr.ok ? 1 : 0),
               QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Elapsed"), QString::number(dr.elapsedMs),
               QStringLiteral("ms"));
      }
    } else if (op == QLatin1String("variables")) {
      QVariantMap& module = module_vars_[id];
      const VarsAssignResult vr = runVariables(step->params, flow_vars_, global_vars_, module);
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty()) prefix = QStringLiteral("vars");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      put(QStringLiteral("Ok"), vr.ok ? 1 : 0);
      put(QStringLiteral("Value"), vr.value);
      put(QStringLiteral("Name"), vr.name);
      put(QStringLiteral("Scope"), vr.scope);
      put(QStringLiteral("Mode"), vr.mode);
      ok = vr.ok;
      note = vr.ok ? vr.note : vr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(vr.ok ? 1 : 0),
               QStringLiteral("gate"));
        addRow(vr.scope + QLatin1Char('.') + vr.name, vr.value.toString(), vr.mode);
      }
    } else if (op == QLatin1String("tcp_exchange") || op == QLatin1String("udp_exchange")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap sp = step->params;
      if (sp.contains(QStringLiteral("value")) &&
          sp.value(QStringLiteral("value")).typeId() == QMetaType::QString) {
        sp.insert(QStringLiteral("value"),
                  CommHub::expandTemplate(sp.value(QStringLiteral("value")).toString(),
                                          flow_vars_));
      }
      const SocketXferResult xr = (op == QLatin1String("tcp_exchange"))
                                      ? runTcpExchange(sp, &pipeline_cancel_)
                                      : runUdpExchange(sp, &pipeline_cancel_);
      const double xferMs = std::chrono::duration<double, std::milli>(
                                std::chrono::steady_clock::now() - t0)
                                .count();
      algoMs += xferMs;
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty())
        prefix = (op == QLatin1String("tcp_exchange")) ? QStringLiteral("tcpEx")
                                                       : QStringLiteral("udpEx");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      put(QStringLiteral("Ok"), xr.ok ? 1 : 0);
      put(QStringLiteral("Value"), xr.value);
      put(QStringLiteral("Delivery"), xr.delivery);
      put(QStringLiteral("Ack"), xr.acknowledged ? 1 : 0);
      put(QStringLiteral("Bytes"), xr.byteLength);
      put(QStringLiteral("SentBytes"), xr.sentBytes);
      put(QStringLiteral("Trailing"), xr.trailingBytes);
      put(QStringLiteral("Host"), xr.host);
      put(QStringLiteral("Port"), xr.port);
      put(QStringLiteral("Sim"), xr.simulated ? 1 : 0);
      put(QStringLiteral("Error"), xr.error);
      ok = xr.ok;
      note = xr.ok ? QStringLiteral("%1 · %2 ms").arg(xr.note).arg(xferMs, 0, 'f', 1)
                   : xr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(xr.ok ? 1 : 0),
               QStringLiteral("gate"));
        addRow(prefix + QStringLiteral("Value"), xr.value.toString(), xr.encoding);
        addRow(prefix + QStringLiteral("Delivery"), xr.delivery, QStringLiteral("delivery"));
      }
    } else if (op == QLatin1String("script") || op == QLatin1String("plugin")) {
      const auto t0 = std::chrono::steady_clock::now();
      QVariantMap& module = module_vars_[id];
      const PythonExtResult pr = (op == QLatin1String("script"))
                                     ? runScript(step->params, flow_vars_, global_vars_, module,
                                                 {}, &pipeline_cancel_)
                                     : runPlugin(step->params, flow_vars_, global_vars_, module,
                                                 {}, &pipeline_cancel_);
      const double pyMs = std::chrono::duration<double, std::milli>(
                              std::chrono::steady_clock::now() - t0)
                              .count();
      algoMs += pyMs;
      QString prefix = step->params.value(QStringLiteral("resultVar")).toString().trimmed();
      if (prefix.isEmpty())
        prefix = (op == QLatin1String("script")) ? QStringLiteral("script")
                                                 : QStringLiteral("plugin");
      auto put = [&](const QString& suffix, const QVariant& v) {
        flow_vars_.insert(prefix + suffix, v);
      };
      put(QStringLiteral("Ok"), pr.ok ? 1 : 0);
      put(QStringLiteral("Elapsed"), pr.elapsedMs);
      put(QStringLiteral("Error"), pr.error);
      if (op == QLatin1String("script")) {
        if (pr.result.contains(QStringLiteral("scriptOut")))
          put(QStringLiteral("Out"), pr.result.value(QStringLiteral("scriptOut")));
      } else {
        if (pr.result.contains(QStringLiteral("value")))
          put(QStringLiteral("Value"), pr.result.value(QStringLiteral("value")));
        put(QStringLiteral("Id"), pr.pluginId);
        put(QStringLiteral("Op"), pr.operatorId);
      }
      ok = pr.ok;
      note = pr.ok ? QStringLiteral("%1 · %2 ms").arg(pr.note).arg(pyMs, 0, 'f', 1) : pr.error;
      if (result_table_) {
        auto addRow = [&](const QString& k, const QString& v, const QString& unit) {
          const int row = result_table_->rowCount();
          result_table_->insertRow(row);
          result_table_->setItem(row, 0, new QTableWidgetItem(k));
          result_table_->setItem(row, 1, new QTableWidgetItem(v));
          result_table_->setItem(row, 2, new QTableWidgetItem(unit));
        };
        addRow(prefix + QStringLiteral("Ok"), QString::number(pr.ok ? 1 : 0),
               QStringLiteral("gate"));
        if (op == QLatin1String("script"))
          addRow(prefix + QStringLiteral("Out"),
                 pr.result.value(QStringLiteral("scriptOut")).toString(),
                 QStringLiteral("result"));
        else
          addRow(prefix + QStringLiteral("Value"),
                 pr.result.value(QStringLiteral("value")).toString(),
                 QStringLiteral("result"));
        addRow(prefix + QStringLiteral("Elapsed"), QString::number(pr.elapsedMs),
               QStringLiteral("ms"));
      }
    } else {
      note = QStringLiteral("透传 / 未实现执行体");
      ok = true;
    }

    if (!execInfo.contains(id)) {
      NodeExec nx;
      nx.executed = true;
      nx.ok = ok;
      nx.passed = ok;
      execInfo.insert(id, nx);
    }
    if (updateFlowStates) {
      flow_scene_->setNodeRunState(
          id, ok ? QStringLiteral("OK") : QStringLiteral("NG"));
    }
    logResult(QStringLiteral("%1 [%2] %3").arg(step->name, op, note));
  }
  flow_vars_.insert(QStringLiteral("skippedCount"), skippedCount);

  image_view_->setOverlays(overlays);
  if (output_view_) output_view_->setOverlays(overlays);
  cacheFilmstripGeomOverlays(overlays);
  cacheFilmstripMeasureBadge();
  refreshGeomCompareOverlays();
  if (flow_vars_.contains(QStringLiteral("passGate"))) {
    const bool gateOk = flow_vars_.value(QStringLiteral("passGate")).toInt() != 0 ||
                        flow_vars_.value(QStringLiteral("passGate")).toBool();
    if (gateOk)
      noteHostResult(true, QString());
    else if (host_strip_)
      host_strip_->setAlarm(false);
  }
  ++run_cycle_;
  syncVarsToUi(true);
  updateRunChrome();
  const double flowMs = std::chrono::duration<double, std::milli>(
                            std::chrono::steady_clock::now() - flowT0)
                            .count();
  const double toolMs = qMax(0.0, flowMs - algoMs);
  last_cycle_ms_ = flowMs;
  cycle_samples_ms_.push_back(flowMs);
  if (cycle_samples_ms_.size() > 200) cycle_samples_ms_.removeFirst();
  QVector<double> sortedCycles = cycle_samples_ms_;
  std::sort(sortedCycles.begin(), sortedCycles.end());
  // nearest-rank P95；小样本明确标注 n，不假称现场节拍或含曝光时间。
  const int p95Index = qMax(0, (sortedCycles.size() * 95 + 99) / 100 - 1);
  const double p95Ms = sortedCycles.at(p95Index);
  setProperty("completedCycles", run_cycle_);
  setProperty("cycleP95Ms", p95Ms);
  appendInspectionHistory();
  if (updateFlowStates && !dispatching_triggers_) {
    const bool hasGate = flow_vars_.contains(QStringLiteral("passGate"));
    const bool gateOk = !hasGate || flow_vars_.value(QStringLiteral("passGate")).toInt() != 0 ||
                        flow_vars_.value(QStringLiteral("passGate")).toBool();
    if (hasGate && !gateOk)
      fireEventTriggers(QStringLiteral("流程NG"), false);
    fireEventTriggers(QStringLiteral("流程结束"), continuous_run_);
  }
  if (host_strip_) host_strip_->setCycleTiming(flowMs);
  if (host_sm_ && host_strip_)
    host_sm_->setRunStats(host_strip_->okStreak(), host_strip_->ngCount(), flowMs);
  if (status_timing_) {
    status_timing_->setText(QStringLiteral("软件 %1 ms · 工具 %2 · 算法 %3 · P95 %4 ms (n=%5)")
                                .arg(flowMs, 0, 'f', 2)
                                .arg(toolMs, 0, 'f', 2)
                                .arg(algoMs, 0, 'f', 2)
                                .arg(p95Ms, 0, 'f', 2).arg(sortedCycles.size()));
  }
  refreshConfigStatus();
  if (result_table_) {
    result_table_->resizeColumnToContents(0);
    result_table_->resizeColumnToContents(2);
  }
  showStatus(QStringLiteral("流水线完成 · 码 %1 · %2 ms")
                 .arg(hits.size())
                 .arg(decodeMs, 0, 'f', 1));

  const QByteArray smoke = qgetenv("SIEANS_QT_SMOKE_REPORT");
  if (!smoke.isEmpty()) {
    QFile f(QString::fromUtf8(smoke));
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
      QString peerProbe = QStringLiteral("skipped");
      QString okPeerTx = QStringLiteral("skipped");
      int peerAck = 0;
      int stripLock = host_strip_ && host_strip_->recipeLocked() ? 1 : 0;
      QString peerEp;
      QString hostTxDevs =
          flow_vars_.value(QStringLiteral("hostTxDevices")).toString();
      if (comm_hub_) {
        QString detail;
        const bool ok = comm_hub_->probeLocalPeerAck(&detail);
        peerProbe = ok ? QStringLiteral("ok:%1").arg(detail)
                       : QStringLiteral("fail:%1").arg(detail);
        QString txDetail;
        const QString okPayload =
            QStringLiteral("HOST OK result=%1 pass=%2 lock=%3 smoke=1")
                .arg(flow_vars_.value(QStringLiteral("hostResult")).toString())
                .arg(flow_vars_.value(QStringLiteral("passGate")).toString())
                .arg(flow_vars_.value(QStringLiteral("recipeLocked")).toString());
        const bool txOk = comm_hub_->smokePeerHostTx(okPayload, &txDetail);
        okPeerTx = txOk ? QStringLiteral("ok:%1").arg(txDetail)
                        : QStringLiteral("fail:%1").arg(txDetail);
        const QString tcpDev = comm_hub_->primaryTcpDevice();
        peerAck = comm_hub_->deviceTxStatus(tcpDev).peerAckCount;
        peerEp = comm_hub_->lastPeerEndpoint();
        if (hostTxDevs.isEmpty())
          hostTxDevs =
              flow_vars_.value(QStringLiteral("hostTxDevices")).toString();
      }
      QString txDevSummary;
      if (comm_hub_) {
        const auto map = comm_hub_->deviceTxMap();
        QStringList bits;
        for (auto it = map.constBegin(); it != map.constEnd(); ++it) {
          bits << QStringLiteral("%1:%2x%3p%4")
                      .arg(it.key(), it.value().status)
                      .arg(it.value().txCount)
                      .arg(it.value().peerAckCount);
          if (bits.size() >= 4) break;
        }
        txDevSummary = bits.join(QLatin1Char(','));
      }
      QString line =
          QStringLiteral(
              "codes=%1 ms=%2 w=%3 h=%4 passGate=%5 barcodeText=%6 "
              "formatted=%7 lastRecv=%8 urlOk=%9 tcp=%10 "
              "hostResult=%11 hostMode=%12 hostState=%13 "
              "hostLastTx=%14 ioHostResult=%15 lastTxDevice=%16 "
              "deviceTx=%17 recipeLocked=%18 alarmHist=%19 "
              "alarmLatched=%20 alarmLast=%21 "
              "peerAck=%22 peerProbe=%23 lastPeer=%24 "
              "okPeerTx=%25 hostTxDevices=%26 stripLock=%27\n")
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
              .arg(comm_hub_ ? comm_hub_->tcpStatus() : QStringLiteral("n/a"))
              .arg(flow_vars_.value(QStringLiteral("hostResult")).toString())
              .arg(flow_vars_.value(QStringLiteral("hostMode")).toString())
              .arg(flow_vars_.value(QStringLiteral("hostState")).toString())
              .arg(flow_vars_.value(QStringLiteral("hostLastTx")).toString()
                       .left(100).replace(QLatin1Char('\n'), QLatin1Char('|')))
              .arg(flow_vars_.value(QStringLiteral("io.HostResult")).toString())
              .arg(comm_hub_ ? comm_hub_->lastTxDevice() : QString())
              .arg(txDevSummary.left(120))
              .arg(run_mode_ ? 1 : 0)
              .arg(host_sm_ ? host_sm_->alarmCount() : 0)
              .arg((host_strip_ && host_strip_->alarmOn()) ||
                           document_.alarmLatched()
                       ? 1
                       : 0)
              .arg((host_sm_ ? host_sm_->lastAlarmReason()
                             : document_.alarmLatchReason())
                       .left(80)
                       .replace(QLatin1Char('\n'), QLatin1Char('|')))
              .arg(peerAck)
              .arg(peerProbe.left(120).replace(QLatin1Char('\n'),
                                               QLatin1Char('|')))
              .arg(peerEp.left(64))
              .arg(okPeerTx.left(140).replace(QLatin1Char('\n'),
                                              QLatin1Char('|')))
              .arg(hostTxDevs.left(80))
              .arg(stripLock);
      if (line.endsWith(QLatin1Char('\n'))) line.chop(1);
      line += QLatin1Char(' ');
      line += QStringLiteral("ocrText=%1 ocrCount=%2 ocrOk=%3 ocrAvail=%4")
                  .arg(flow_vars_.value(QStringLiteral("ocrText")).toString()
                           .left(80)
                           .replace(QLatin1Char('\n'), QLatin1Char('|')))
                  .arg(flow_vars_.value(QStringLiteral("ocrCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("ocrOk")).toString())
                  .arg(sieans::ocr_available() ? 1 : 0);
      line += QLatin1Char(' ');
      line += QStringLiteral("projectDirty=%1 projectSaved=%2 projectName=%3 projectsDirOk=%4")
                  .arg(project_dirty_ ? 1 : 0)
                  .arg(document_.path().isEmpty() ? 0 : 1)
                  .arg(document_.name().left(80).replace(QLatin1Char('\n'), QLatin1Char('|')))
                  .arg(QFileInfo::exists(workbenchProjectsDir()) ? 1 : 0);

      line += QLatin1Char(' ');
      line += QStringLiteral("caliperDist=%1 caliperOk=%2 measureMm=%3")
                  .arg(flow_vars_.value(QStringLiteral("caliperDist")).toString())
                  .arg(flow_vars_.value(QStringLiteral("caliperOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measureMm")).toString());
      line += QLatin1Char(' ');
      line += QStringLiteral(
                  "conditionPassed=%1 branchTaken=%2 branchRoute=%3 "
                  "mergeFrom=%4 skippedCount=%5 conditionOk=%6")
                  .arg(flow_vars_.value(QStringLiteral("conditionPassed")).toString())
                  .arg(flow_vars_.value(QStringLiteral("branchTaken")).toString())
                  .arg(flow_vars_.value(QStringLiteral("branchRoute")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mergeFrom")).toString()
                           .left(40)
                           .replace(QLatin1Char('\n'), QLatin1Char('|')))
                  .arg(flow_vars_.value(QStringLiteral("skippedCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("conditionOk")).toString());
      line += QLatin1Char(' ');
      line += QStringLiteral(
                  "subflowPassed=%1 subflowCount=%2 loopCompleted=%3 "
                  "loopStoppedEarly=%4 loopCount=%5 loopPassed=%6")
                  .arg(flow_vars_.value(QStringLiteral("subflowPassed")).toString())
                  .arg(flow_vars_.value(QStringLiteral("subflowCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("loopCompleted")).toString())
                  .arg(flow_vars_.value(QStringLiteral("loopStoppedEarly")).toString())
                  .arg(flow_vars_.value(QStringLiteral("loopCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("loopPassed")).toString());
      line += QLatin1Char(' ');
      line += QStringLiteral(
                  "defectsCleanCount=%1 defectsCleanOk=%2 defectsCleanRatio=%3 "
                  "defectsCount=%4 defectsOk=%5 defectsRatio=%6 defectsMaxArea=%7 "
                  "defectsPassed=%8")
                  .arg(flow_vars_.value(QStringLiteral("defectsCleanCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsCleanOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsCleanRatio")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsRatio")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsMaxArea")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsPassed")).toString());
      line += QLatin1Char(' ');
      {
        const QStringList locFails = LocateMatchPanel::selfTest();
        const FlowStep* locStep = document_.findStep(QStringLiteral("loc1"));
        QVariantMap lp = locStep ? LocateMatchPanel::normalizeParams(locStep->params)
                                 : LocateMatchPanel::normalizeParams({});
        LocateMatchPanel probe;
        if (locStep) probe.bindStep(*locStep);
        else {
          FlowStep tmp;
          tmp.id = QStringLiteral("loc1");
          tmp.operation = QStringLiteral("locate");
          tmp.params = lp;
          probe.bindStep(tmp);
        }
        {
          const QString dir = workbenchTemplatesDir() + QStringLiteral("/smoke-lib");
          QDir().mkpath(dir);
          const QString a = dir + QStringLiteral("/a.png");
          const QString b = dir + QStringLiteral("/b.png");
          QImage ia(16, 16, QImage::Format_RGB888);
          ia.fill(QColor(200, 40, 40));
          ia.save(a);
          QImage ib(16, 16, QImage::Format_RGB888);
          ib.fill(QColor(40, 200, 40));
          ib.save(b);
          probe.addLibraryEntry(a, QStringLiteral("烟测A"));
          probe.addLibraryEntry(b, QStringLiteral("烟测B"));
          probe.runBatchScoreboard({}, true);
          probe.selectBestScoredTemplate();
        }
        line += QStringLiteral(
                    "locatePanelOk=%1 locateTabs=%2 locateTplReady=%3 "
                    "locateMatchMode=%4 locateAngleEnable=%5 locatePanelFails=%6 "
                    "locateLibCount=%7 locateLibOk=%8 locateBoardOk=%9 "
                    "locateBoardBest=%10 locateBoardPass=%11 ")
                    .arg(locFails.isEmpty() ? 1 : 0)
                    .arg(probe.tabCount())
                    .arg(probe.templateReady() ? 1 : 0)
                    .arg(lp.value(QStringLiteral("matchMode")).toString())
                    .arg(lp.value(QStringLiteral("angleEnable")).toBool() ? 1 : 0)
                    .arg(locFails.isEmpty() ? QStringLiteral("0")
                                            : locFails.join(QLatin1Char('|')).left(80))
                    .arg(probe.libraryCount())
                    .arg(probe.libraryCount() == 2 && locFails.isEmpty() ? 1 : 0)
                    .arg(probe.lastBatchScoreboard().value(QStringLiteral("rows")).toList().size()
                                 >= 2 && locFails.isEmpty()
                             ? 1
                             : 0)
                    .arg(probe.lastBatchScoreboard().value(QStringLiteral("bestId")).toString().left(16))
                    .arg(probe.lastBatchScoreboard().value(QStringLiteral("passCount")).toInt());
        {
          const QStringList jf = FilmstripBar::jumpSelfTest();
          QVariantMap demo;
          // last successful spark-index style check is represented by empty fails
          line += QStringLiteral(
                      "filmJumpOk=%1 filmJumpFails=%2 filmJumpBy=%3 ")
                      .arg(jf.isEmpty() ? 1 : 0)
                      .arg(jf.isEmpty() ? QStringLiteral("0")
                                        : jf.join(QLatin1Char('|')).left(120))
                      .arg(jf.isEmpty() ? QStringLiteral("path") : QStringLiteral("fail"));
        }
        {
          const QStringList iof = CommHub::ioResolveSelfTest();
          line += QStringLiteral("ioResolveOk=%1 ioResolveFails=%2 ")
                      .arg(iof.isEmpty() ? 1 : 0)
                      .arg(iof.isEmpty() ? QStringLiteral("0")
                                         : iof.join(QLatin1Char('|')).left(120));
        }
        {
          const QStringList pf = SieansDocument::pinGroupSelfTest();
          const QStringList cf = HostStrip::pinGroupChromeSelfTest();
          QStringList all = pf;
          all << cf;
          line += QStringLiteral(
                      "pinGroupOk=%1 pinGroupFails=%2 pinGroupCount=%3 "
                      "pinGroupActive=%4 pinGroupRound=%5 pinGroupChipOk=%6 "
                      "pinGroupLive=%7 ")
                      .arg(all.isEmpty() ? 1 : 0)
                      .arg(all.isEmpty() ? QStringLiteral("0")
                                         : all.join(QLatin1Char('|')).left(160))
                      .arg(all.isEmpty() ? 2 : 0)
                      .arg(all.isEmpty() ? QStringLiteral("测量") : QStringLiteral("fail"))
                      .arg(pf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(document_.pinGroupNames().size());
        }
        {
          const QStringList cf = CompareStrip::compareSelfTest();
          line += QStringLiteral(
                      "compareStripOk=%1 compareStripFails=%2 compareStripCount=%3 "
                      "compareStripCap=%4 compareLive=%5 compareLockOk=%6 "
                      "compareUndoOk=%7 compareReorderOk=%8 comparePresetOk=%9 ")
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? QStringLiteral("0")
                                         : cf.join(QLatin1Char('|')).left(160))
                      .arg(cf.isEmpty() ? 2 : 0)
                      .arg(cf.isEmpty() ? 6 : 0)
                      .arg(compare_strip_ ? compare_strip_->count() : 0)
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? 1 : 0);
        }
        {
          const QStringList gf = geomOverlaySelfTest();
          line += QStringLiteral(
                      "geomOverlayOk=%1 geomOverlayFails=%2 geomOverlayFrames=%3 "
                      "geomOverlayHi=%4 geomOverlayCached=%5 geomOverlayLive=%6 ")
                      .arg(gf.isEmpty() ? 1 : 0)
                      .arg(gf.isEmpty() ? QStringLiteral("0")
                                         : gf.join(QLatin1Char('|')).left(160))
                      .arg(gf.isEmpty() ? 2 : 0)
                      .arg(gf.isEmpty() ? 1 : 0)
                      .arg(filmstrip_geom_cache_.size())
                      .arg(output_view_ ? output_view_->geomOverlayCount() : 0);
        }
        {
          const QStringList bf = FilmstripBar::measureBadgeSelfTest();
          int live = 0;
          if (filmstrip_) {
            for (const QString& path : filmstrip_->paths()) {
              if (!filmstrip_->frameMeasureBadge(path).isEmpty()) ++live;
            }
          }
          line += QStringLiteral(
                      "filmBadgeOk=%1 filmBadgeFails=%2 filmBadgeLive=%3 ")
                      .arg(bf.isEmpty() ? 1 : 0)
                      .arg(bf.isEmpty() ? QStringLiteral("0")
                                         : bf.join(QLatin1Char('|')).left(160))
                      .arg(live);
        }
      }
      line += QStringLiteral(
                  "locateOk=%1 locateScore=%2 locateX=%3 locateY=%4 locateAngle=%5 "
                  "locateCount=%6 fixtureOk=%7 fixtureX=%8 fixtureY=%9")
                  .arg(flow_vars_.value(QStringLiteral("locateOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("locateScore")).toString())
                  .arg(flow_vars_.value(QStringLiteral("locateX")).toString())
                  .arg(flow_vars_.value(QStringLiteral("locateY")).toString())
                  .arg(flow_vars_.value(QStringLiteral("locateAngle")).toString())
                  .arg(flow_vars_.value(QStringLiteral("locateCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("fixtureOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("fixtureX")).toString())
                  .arg(flow_vars_.value(QStringLiteral("fixtureY")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "fixtureAngle=%1 defectsFollowCount=%2 defectsFollowOk=%3 "
                  "defectsFollowRoiX=%4 defectsFollowRoiY=%5")
                  .arg(flow_vars_.value(QStringLiteral("fixtureAngle")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsFollowCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsFollowOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsFollowRoiX")).toString())
                  .arg(flow_vars_.value(QStringLiteral("defectsFollowRoiY")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "geomCircCount=%1 geomCircOk=%2 geomCircX=%3 geomCircY=%4 "
                  "geomCircRadius=%5")
                  .arg(flow_vars_.value(QStringLiteral("geomCircCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomCircOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomCircX")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomCircY")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomCircRadius")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "geomLineCount=%1 geomLineOk=%2 geomLineLength=%3 geomLineAngle=%4 "
                  "geomFollowCount=%5 geomFollowOk=%6 geomFollowRadius=%7 "
                  "geomFollowRoiX=%8 geomFollowRoiY=%9")
                  .arg(flow_vars_.value(QStringLiteral("geomLineCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomLineOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomLineLength")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomLineAngle")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomFollowCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomFollowOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomFollowRadius")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomFollowRoiX")).toString())
                  .arg(flow_vars_.value(QStringLiteral("geomFollowRoiY")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "measCircCount=%1 measCircOk=%2 measCircDiameter=%3 "
                  "measCircRadius=%4 measCircDiameterMm=%5")
                  .arg(flow_vars_.value(QStringLiteral("measCircCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measCircOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measCircDiameter")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measCircRadius")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measCircDiameterMm")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "measLineCount=%1 measLineOk=%2 measLineLength=%3 "
                  "measAngAngle=%4 measAngOk=%5 measPtsDist=%6 measPtsOk=%7")
                  .arg(flow_vars_.value(QStringLiteral("measLineCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measLineOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measLineLength")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measAngAngle")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measAngOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measPtsDist")).toString())
                  .arg(flow_vars_.value(QStringLiteral("measPtsOk")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "serialOk=%1 serialRx=%2 serialTx=%3 serialBytes=%4 serialSim=%5 "
                  "serialPort=%6 serialPtyOk=%7 serialPtyRx=%8")
                  .arg(flow_vars_.value(QStringLiteral("serialOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("serialRx")).toString()
                           .left(80)
                           .replace(QLatin1Char('\n'), QLatin1Char('|')))
                  .arg(flow_vars_.value(QStringLiteral("serialTx")).toString()
                           .left(80)
                           .replace(QLatin1Char('\n'), QLatin1Char('|')))
                  .arg(flow_vars_.value(QStringLiteral("serialBytes")).toString())
                  .arg(flow_vars_.value(QStringLiteral("serialSim")).toString())
                  .arg(flow_vars_.value(QStringLiteral("serialPort")).toString()
                           .left(40)
                           .replace(QLatin1Char('\n'), QLatin1Char('|')))
                  .arg(flow_vars_.value(QStringLiteral("serialPtyOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("serialPtyRx")).toString()
                           .left(80)
                           .replace(QLatin1Char('\n'), QLatin1Char('|')));
      line += QChar(' ');
      line += QStringLiteral(
                  "mbWriteOk=%1 mbWriteValue=%2 mbWriteAck=%3 "
                  "mbReadOk=%4 mbReadValue=%5 mbWaitOk=%6 mbWaitTriggered=%7 "
                  "mbWaitValue=%8")
                  .arg(flow_vars_.value(QStringLiteral("mbWriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbWriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbWriteAck")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbReadValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbWaitOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbWaitTriggered")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbWaitValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "mbTcpWriteOk=%1 mbTcpWriteValue=%2 mbTcpReadOk=%3 mbTcpReadValue=%4 "
                  "mbRtuWriteOk=%5 mbRtuWriteValue=%6 mbRtuReadOk=%7 mbRtuReadValue=%8")
                  .arg(flow_vars_.value(QStringLiteral("mbTcpWriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbTcpWriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbTcpReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbTcpReadValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbRtuWriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbRtuWriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbRtuReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mbRtuReadValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "s7WriteOk=%1 s7WriteValue=%2 s7WriteAck=%3 "
                  "s7ReadOk=%4 s7ReadValue=%5 "
                  "s7TcpWriteOk=%6 s7TcpWriteValue=%7 s7TcpReadOk=%8 s7TcpReadValue=%9")
                  .arg(flow_vars_.value(QStringLiteral("s7WriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7WriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7WriteAck")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7ReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7ReadValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7TcpWriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7TcpWriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7TcpReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("s7TcpReadValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "opcWriteOk=%1 opcWriteValue=%2 opcWriteAck=%3 "
                  "opcReadOk=%4 opcReadValue=%5 "
                  "opcWaitOk=%6 opcWaitTriggered=%7 opcWaitValue=%8")
                  .arg(flow_vars_.value(QStringLiteral("opcWriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcWriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcWriteAck")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcReadValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcWaitOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcWaitTriggered")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcWaitValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "opcBrowseOk=%1 opcBrowseCount=%2 "
                  "opcTcpWriteOk=%3 opcTcpWriteValue=%4 opcTcpReadOk=%5 opcTcpReadValue=%6")
                  .arg(flow_vars_.value(QStringLiteral("opcBrowseOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcBrowseCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcTcpWriteOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcTcpWriteValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcTcpReadOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("opcTcpReadValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "mqttPubOk=%1 mqttPubValue=%2 mqttPubAck=%3 "
                  "mqttRecvOk=%4 mqttRecvValue=%5 "
                  "mqttTcpPubOk=%6 mqttTcpPubValue=%7 mqttTcpRecvOk=%8 mqttTcpRecvValue=%9")
                  .arg(flow_vars_.value(QStringLiteral("mqttPubOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttPubValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttPubAck")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttRecvOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttRecvValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttTcpPubOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttTcpPubValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttTcpRecvOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("mqttTcpRecvValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "yoloOk=%1 yoloCount=%2 yoloScore=%3 yoloLabel=%4 yoloBackend=%5 "
                  "yoloSegOk=%6 yoloSegCount=%7 yoloSegScore=%8 yoloSegArea=%9 "
                  "yoloSegLabel=%10 yoloSegBackend=%11")
                  .arg(flow_vars_.value(QStringLiteral("yoloOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloScore")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloLabel")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloBackend")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloSegOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloSegCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloSegScore")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloSegArea")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloSegLabel")).toString())
                  .arg(flow_vars_.value(QStringLiteral("yoloSegBackend")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "cloudFiltOk=%1 cloudFiltCount=%2 "
                  "cloudPlaneOk=%3 cloudPlaneInliers=%4 cloudPlaneRms=%5 "
                  "cloudClustOk=%6 cloudClustCount=%7 cloudClustNoise=%8")
                  .arg(flow_vars_.value(QStringLiteral("cloudFiltOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudFiltCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudPlaneOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudPlaneInliers")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudPlaneRms")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudClustOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudClustCount")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudClustNoise")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "cloudMeasOk=%1 cloudMeasSizeX=%2 cloudMeasSizeY=%3 cloudMeasSizeZ=%4 "
                  "cloudHgtOk=%5 cloudHgtVolume=%6 cloudHgtMax=%7 "
                  "cloudRegOk=%8 cloudRegFound=%9")
                  .arg(flow_vars_.value(QStringLiteral("cloudMeasOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudMeasSizeX")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudMeasSizeY")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudMeasSizeZ")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudHgtOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudHgtVolume")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudHgtMax")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudRegOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudRegFound")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "cloudRegDx=%1 cloudRegDy=%2 cloudRegDz=%3 cloudRegFitness=%4 cloudRegRms=%5")
                  .arg(flow_vars_.value(QStringLiteral("cloudRegDx")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudRegDy")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudRegDz")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudRegFitness")).toString())
                  .arg(flow_vars_.value(QStringLiteral("cloudRegRms")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "delayOk=%1 delayMs=%2 delayElapsed=%3 "
                  "varsAssign=%4 varsSetOk=%5 varsSetValue=%6 varsIncOk=%7 varsIncValue=%8")
                  .arg(flow_vars_.value(QStringLiteral("delayOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("delayMs")).toString())
                  .arg(flow_vars_.value(QStringLiteral("delayElapsed")).toString())
                  .arg(flow_vars_.value(QStringLiteral("varsAssign")).toString())
                  .arg(flow_vars_.value(QStringLiteral("varsSetOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("varsSetValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("varsIncOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("varsIncValue")).toString());
      line += QChar(' ');
      line += QStringLiteral(
                  "tcpExOk=%1 tcpExValue=%2 tcpExDelivery=%3 "
                  "udpExOk=%4 udpExValue=%5 udpExDelivery=%6")
                  .arg(flow_vars_.value(QStringLiteral("tcpExOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("tcpExValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("tcpExDelivery")).toString())
                  .arg(flow_vars_.value(QStringLiteral("udpExOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("udpExValue")).toString())
                  .arg(flow_vars_.value(QStringLiteral("udpExDelivery")).toString());
      line += QLatin1Char(' ');
      line += QStringLiteral(
                  "scriptOk=%1 scriptOut=%2 "
                  "pluginOk=%3 pluginValue=%4")
                  .arg(flow_vars_.value(QStringLiteral("scriptOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("scriptOut")).toString())
                  .arg(flow_vars_.value(QStringLiteral("pluginOk")).toString())
                  .arg(flow_vars_.value(QStringLiteral("pluginValue")).toString());
      {
        const QStringList pf = protocolRobustnessSelfTest();
        line += QLatin1Char(' ');
        line += QStringLiteral(
                    "protoRobustOk=%1 protoRobustFails=%2 protoFailClass=%3")
                    .arg(pf.isEmpty() ? 1 : 0)
                    .arg(pf.isEmpty() ? QStringLiteral("0")
                                      : pf.join(QLatin1Char('|')).left(120))
                    .arg(lastProtocolRobustClass());
      }
      {
        const QStringList sf = SieansDocument::schemeSelfTest();
        QString activeName;
        for (const FlowDef& f : document_.flows()) {
          if (f.id == document_.activeFlowId()) {
            activeName = f.name;
            break;
          }
        }
        if (activeName.isEmpty() && !document_.flows().isEmpty())
          activeName = document_.flows().first().name;
        line += QLatin1Char(' ');
        line += QStringLiteral(
                    "flowCount=%1 activeFlowName=%2 schemeSelfOk=%3 schemeSelfFails=%4")
                    .arg(document_.flows().size())
                    .arg(activeName.left(40).replace(QLatin1Char('\n'), QLatin1Char('|')))
                    .arg(sf.isEmpty() ? 1 : 0)
                    .arg(sf.isEmpty() ? QStringLiteral("0")
                                      : sf.join(QLatin1Char('|')).left(160));
        {
          const QStringList rf = SieansDocument::recipeSelfTest();
          line += QChar(' ');
          line += QStringLiteral("recipeOk=%1 recipeFails=%2 recipeLive=%3")
                      .arg(rf.isEmpty() ? 1 : 0)
                      .arg(rf.isEmpty() ? QStringLiteral("0")
                                         : rf.join(QLatin1Char('|')).left(160))
                      .arg(document_.recipeCount());
        }
        {
          const QStringList rf = ImageView::roiEditorSelfTest();
          line += QChar(' ');
          line += QStringLiteral("roiEditorOk=%1 roiEditorFails=%2 roiEditorLive=%3")
                      .arg(rf.isEmpty() ? 1 : 0)
                      .arg(rf.isEmpty() ? QStringLiteral("0")
                                         : rf.join(QLatin1Char('|')).left(160))
                      .arg((image_view_ && image_view_->roiMode()) ? 1 : 0);
        }
        {
          const QStringList tf = SieansDocument::triggerSelfTest();
          line += QChar(' ');
          line += QStringLiteral("triggerOk=%1 triggerFails=%2 triggerLive=%3")
                      .arg(tf.isEmpty() ? 1 : 0)
                      .arg(tf.isEmpty() ? QStringLiteral("0")
                                         : tf.join(QLatin1Char('|')).left(160))
                      .arg(document_.stringTriggerCount());
        }
        {
          const QStringList uf = SieansDocument::canvasUndoSelfTest();
          line += QChar(' ');
          line += QStringLiteral("flowUndoOk=%1 flowUndoFails=%2 flowUndoLive=%3")
                      .arg(uf.isEmpty() ? 1 : 0)
                      .arg(uf.isEmpty() ? QStringLiteral("0")
                                         : uf.join(QLatin1Char('|')).left(160))
                      .arg(document_.canvasUndoDepth());
        }
        {
          const QStringList cf = cloudFileSelfTest();
          line += QChar(' ');
          line += QStringLiteral("cloudFileOk=%1 cloudFileFails=%2 cloudFileLive=%3")
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? QStringLiteral("0")
                                         : cf.join(QLatin1Char('|')).left(160))
                      .arg(imported_cloud_path_.isEmpty() ? 0 : 1);
        }
        {
          const QStringList hf = InspectionHistory::historySelfTest();
          line += QChar(' ');
          line += QStringLiteral("histOk=%1 histFails=%2 histLive=%3")
                      .arg(hf.isEmpty() ? 1 : 0)
                      .arg(hf.isEmpty() ? QStringLiteral("0")
                                         : hf.join(QLatin1Char('|')).left(160))
                      .arg(inspection_history_.count());
        }
        {
          const QStringList cf = SieansDocument::recipeChangeoverSelfTest();
          line += QChar(' ');
          line += QStringLiteral(
                      "recipeRollbackOk=%1 recipeRollbackFails=%2 recipeRollbackLive=%3 "
                      "recipeLibOk=%4 recipeVariantLive=%5")
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(cf.isEmpty() ? QStringLiteral("0")
                                         : cf.join(QLatin1Char('|')).left(160))
                      .arg(document_.recipeRollbackDepth())
                      .arg(cf.isEmpty() ? 1 : 0)
                      .arg(document_.recipeVariants().size());
        }
        {
          const QStringList rf = RecentFiles::recentFilesSelfTest();
          line += QChar(' ');
          line += QStringLiteral("recentOk=%1 recentFails=%2 recentLive=%3")
                      .arg(rf.isEmpty() ? 1 : 0)
                      .arg(rf.isEmpty() ? QStringLiteral("0")
                                         : rf.join(QLatin1Char('|')).left(160))
                      .arg(recent_files_.paths().size());
        }
        {
          const QStringList ef = SieansDocument::triggerEventSelfTest();
          line += QChar(' ');
          line += QStringLiteral("triggerEventOk=%1 triggerEventFails=%2 triggerEventLive=%3")
                      .arg(ef.isEmpty() ? 1 : 0)
                      .arg(ef.isEmpty() ? QStringLiteral("0")
                                         : ef.join(QLatin1Char('|')).left(160))
                      .arg(document_.eventTriggerCount());
        }
      }


line += QLatin1Char('\n');
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
        workbenchArtifactsDir() + QStringLiteral("/soft-live-%1.png")
            .arg(run_cycle_ % 8);
    QDir().mkpath(QFileInfo(snap).absolutePath());
    if (frame.save(snap)) {
      // Runtime soft snapshots are preview chrome, not a user recipe edit.
      applying_document_ = true;
      filmstrip_->addPaths({snap});
      applying_document_ = false;
    }
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
  pipeline_cancel_.store(true);
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
  document_.setRecipeLocked(on);
  if (host_sm_) {
    host_sm_->setRecipeLocked(on);
    document_.setAlarmHistory(host_sm_->alarmHistoryLines());
    const bool latched = host_sm_->state() == QLatin1String("Alarm") ||
                         (host_strip_ && host_strip_->alarmOn());
    document_.setAlarmLatched(latched, host_sm_->lastAlarmReason());
    if (!continuous_run_ && host_sm_->state() != QLatin1String("Alarm")) {
      host_sm_->applyState(on ? QStringLiteral("Running") : QStringLiteral("Idle"));
    }
  }
  if (prop_float_ && on) prop_float_->hide();
  updateRunChrome();
  logResult(on ? QStringLiteral("运行模式：画布/算子库已锁定 · 报警历史已写回")
               : QStringLiteral("设计态：画布可编辑 · 配方锁已解除写回"));
  showStatus(on ? QStringLiteral("运行模式 · 配方锁") : QStringLiteral("设计态"));
  updateCanvasUndoActions();
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
    if (prop_float_->panel()) {
      QStringList choices;
      for (const SubflowDef& d : document_.subflows())
        choices << QStringLiteral("%1|%2").arg(d.id, d.name.isEmpty() ? d.id : d.name);
      prop_float_->panel()->setSubflowChoices(choices);
    }
    prop_float_->showForStep(*s);
    const QRect saved = document_.propertyFloatGeometry();
    if (saved.isValid()) {
      prop_float_->applyChromeGeometry(saved);
    } else if (flow_view_) {
      const QPoint g = flow_view_->mapToGlobal(QPoint(flow_view_->width() - 20, 40));
      prop_float_->move(g);
    }
  }
  syncCanvasRoiFromSelection();
}

void MainWindow::onEdgeConnected(const QString&, const QString&, const QString&,
                                 const QString&) {
  // document already updated by FlowScene
  commitCanvasUndo(QStringLiteral("连线"));
  markProjectDirty();
}

void MainWindow::onEdgeWhenChanged(const QString& edgeId, const QString& when) {
  for (FlowEdge& e : document_.edgesMut()) {
    if (e.id != edgeId) continue;
    e.when = when.isEmpty() ? QStringLiteral("always") : when;
    const QString label = (e.when == QLatin1String("true"))
                              ? QStringLiteral("成立")
                              : (e.when == QLatin1String("false")
                                     ? QStringLiteral("不成立")
                                     : e.when);
    logResult(QStringLiteral("连线条件: %1 → %2  when=%3")
                  .arg(e.from, e.to, label));
    showStatus(QStringLiteral("连线触发条件：%1").arg(label), 2500);
    commitCanvasUndo(QStringLiteral("连线条件"));
    markProjectDirty();
    return;
  }
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
  commitCanvasUndo(QStringLiteral("复制模块"));
  markProjectDirty();
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
  } else if (key == QLatin1String("ocr")) {
    s.params = {{QStringLiteral("lang"), QStringLiteral("eng")},
                {QStringLiteral("psm"), 6},
                {QStringLiteral("judgeEnable"), true},
                {QStringLiteral("judgeMinCount"), 1},
                {QStringLiteral("minConfidence"), 0},
                {QStringLiteral("showOverlay"), true}};
  } else if (key == QLatin1String("caliper")) {
    s.params = {{QStringLiteral("direction"), QStringLiteral("horizontal")},
                {QStringLiteral("target"), QStringLiteral("soft_bars")},
                {QStringLiteral("threshold"), 18},
                {QStringLiteral("polarity"), QStringLiteral("any")},
                {QStringLiteral("pxPerMm"), 0},
                {QStringLiteral("bandHalf"), 4},
                {QStringLiteral("judgeEnable"), true},
                {QStringLiteral("judgeMinPx"), 50},
                {QStringLiteral("judgeMaxPx"), 400},
                {QStringLiteral("showOverlay"), true}};
  } else if (key == QLatin1String("measure")) {
    s.params = {{QStringLiteral("feature"), QStringLiteral("circles")},
                {QStringLiteral("target"), QStringLiteral("soft_circle")},
                {QStringLiteral("threshold"), 127},
                {QStringLiteral("minArea"), 50},
                {QStringLiteral("invert"), true},
                {QStringLiteral("pxPerMm"), 0},
                {QStringLiteral("unit"), QStringLiteral("px")},
                {QStringLiteral("judgeEnable"), false},
                {QStringLiteral("resultVar"), QStringLiteral("measure")},
                {QStringLiteral("writePassGate"), false},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("showLabels"), true},
                {QStringLiteral("followFixture"), false}};
  } else if (key == QLatin1String("region")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("fixed")},
                {QStringLiteral("threshold"), 127},
                {QStringLiteral("invert"), false},
                {QStringLiteral("minSeedRadius"), 3},
                {QStringLiteral("minSeedDist"), 8},
                {QStringLiteral("growTolerance"), 25},
                {QStringLiteral("minArea"), 20},
                {QStringLiteral("maxArea"), 0},
                {QStringLiteral("minCircularity"), 0.0},
                {QStringLiteral("maxCircularity"), 1.0},
                {QStringLiteral("minGrayMean"), 0.0},
                {QStringLiteral("maxGrayMean"), 255.0},
                {QStringLiteral("maxCount"), 200},
                {QStringLiteral("resultVar"), QStringLiteral("region")},
                {QStringLiteral("output"), QStringLiteral("overlay")},
                {QStringLiteral("writePassGate"), false},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("showLabels"), true},
                {QStringLiteral("followFixture"), false}};
  } else if (key == QLatin1String("defects")) {
    s.params = {{QStringLiteral("referenceSource"), QStringLiteral("file")},
                {QStringLiteral("referencePath"), QString()},
                {QStringLiteral("differenceThreshold"), 30},
                {QStringLiteral("minArea"), 20},
                {QStringLiteral("maxCount"), 200},
                {QStringLiteral("blur"), 3},
                {QStringLiteral("ignoreBottomPx"), 0},
                {QStringLiteral("scaleReference"), true},
                {QStringLiteral("judgeEnable"), true},
                {QStringLiteral("judgeMaxCount"), 0},
                {QStringLiteral("judgeMaxRatio"), 0.05},
                {QStringLiteral("maxDefectRatio"), 1},
                {QStringLiteral("resultVar"), QStringLiteral("defects")},
                {QStringLiteral("writePassGate"), false},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("showLabels"), true}};
  } else if (key == QLatin1String("geometry")) {
    s.params = {{QStringLiteral("feature"), QStringLiteral("contours")},
                {QStringLiteral("threshold"), 127},
                {QStringLiteral("minArea"), 50},
                {QStringLiteral("invert"), false},
                {QStringLiteral("filterSize"), 1},
                {QStringLiteral("maxCount"), 50},
                {QStringLiteral("cannyLow"), 50},
                {QStringLiteral("cannyHigh"), 150},
                {QStringLiteral("votes"), 30},
                {QStringLiteral("minLength"), 40},
                {QStringLiteral("minRadius"), 5},
                {QStringLiteral("maxRadius"), 200},
                {QStringLiteral("minDistance"), 30},
                {QStringLiteral("judgeEnable"), false},
                {QStringLiteral("resultVar"), QStringLiteral("geom")},
                {QStringLiteral("writePassGate"), false},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("showLabels"), true},
                {QStringLiteral("followFixture"), false}};
  } else if (key == QLatin1String("camera_capture")) {
    s.params = {{QStringLiteral("driver"), QStringLiteral("gentl")},
                {QStringLiteral("backendKind"), QStringLiteral("gentl")},
                {QStringLiteral("continuousLive"), true}};
  } else if (key == QLatin1String("preprocess")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("grayscale")},
                {QStringLiteral("mode"), QStringLiteral("grayscale")},
                {QStringLiteral("threshold"), 128},
                {QStringLiteral("kernel"), 5},
                {QStringLiteral("cannyLow"), 50},
                {QStringLiteral("cannyHigh"), 150}};
  } else if (key == QLatin1String("color")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("convert")},
                {QStringLiteral("space"), QStringLiteral("hsv")},
                {QStringLiteral("channel"), QStringLiteral("h")},
                {QStringLiteral("hMin"), 0},
                {QStringLiteral("hMax"), 255},
                {QStringLiteral("sMin"), 0},
                {QStringLiteral("sMax"), 255},
                {QStringLiteral("vMin"), 0},
                {QStringLiteral("vMax"), 255},
                {QStringLiteral("rMin"), 0},
                {QStringLiteral("rMax"), 255},
                {QStringLiteral("gMin"), 0},
                {QStringLiteral("gMax"), 255},
                {QStringLiteral("bMin"), 0},
                {QStringLiteral("bMax"), 255},
                {QStringLiteral("invert"), false},
                {QStringLiteral("resultVar"), QStringLiteral("color")},
                {QStringLiteral("writePassGate"), false},
                {QStringLiteral("followFixture"), false}};
  } else if (key == QLatin1String("warp")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("affine")},
                {QStringLiteral("a00"), 1},
                {QStringLiteral("a01"), 0},
                {QStringLiteral("a02"), 0},
                {QStringLiteral("a10"), 0},
                {QStringLiteral("a11"), 1},
                {QStringLiteral("a12"), 0},
                {QStringLiteral("angleStart"), 0},
                {QStringLiteral("angleSpan"), 360},
                {QStringLiteral("invert"), false},
                {QStringLiteral("resultVar"), QStringLiteral("warp")}};
  } else if (key == QLatin1String("fft")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("lowpass")},
                {QStringLiteral("cutoff"), 0.08},
                {QStringLiteral("cutoffHigh"), 0.25},
                {QStringLiteral("window"), QStringLiteral("none")},
                {QStringLiteral("sharpCutoff"), 0.15},
                {QStringLiteral("resultVar"), QStringLiteral("fft")},
                {QStringLiteral("writePassGate"), false}};
  } else if (key == QLatin1String("classify")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("knn")},
                {QStringLiteral("k"), 3},
                {QStringLiteral("weighted"), false},
                {QStringLiteral("kernel"), QStringLiteral("linear")},
                {QStringLiteral("C"), 1.0},
                {QStringLiteral("gamma"), 0.5},
                {QStringLiteral("components"), 1},
                {QStringLiteral("hidden"), 8},
                {QStringLiteral("epochs"), 200},
                {QStringLiteral("lr"), 0.2},
                {QStringLiteral("seed"), 1},
                {QStringLiteral("resultVar"), QStringLiteral("classify")},
                {QStringLiteral("writePassGate"), false}};
  } else if (key == QLatin1String("camera_cal")) {
    s.params = {{QStringLiteral("method"), QStringLiteral("calibrate")},
                {QStringLiteral("pattern"), QStringLiteral("checkerboard")},
                {QStringLiteral("rows"), 6},
                {QStringLiteral("cols"), 9},
                {QStringLiteral("squareSize"), 1.0},
                {QStringLiteral("output"), QStringLiteral("overlay")},
                {QStringLiteral("resultVar"), QStringLiteral("cal")},
                {QStringLiteral("writePassGate"), false},
                {QStringLiteral("showOverlay"), true}};
  } else if (key == QLatin1String("locate")) {
    s.params = {{QStringLiteral("minScore"), 0.55},
                {QStringLiteral("maxMatches"), 1},
                {QStringLiteral("templateW"), 80},
                {QStringLiteral("templateH"), 64},
                {QStringLiteral("templatePath"), QString()},
                {QStringLiteral("templateSource"), QStringLiteral("file")},
                {QStringLiteral("matchMode"), QStringLiteral("fast")},
                {QStringLiteral("overlapThreshold"), 0.3},
                {QStringLiteral("angleEnable"), true},
                {QStringLiteral("angleStart"), 0},
                {QStringLiteral("angleEnd"), 0},
                {QStringLiteral("angleStep"), 10},
                {QStringLiteral("writePassGate"), false}};
    s.runState = QStringLiteral("未配置");
  } else if (key == QLatin1String("pose_correct")) {
    s.params = {{QStringLiteral("fixtureSource"), QStringLiteral("auto")},
                {QStringLiteral("autoBindLocate"), true},
                {QStringLiteral("followRoi"), true},
                {QStringLiteral("resultVar"), QStringLiteral("fixture")},
                {QStringLiteral("baseX"), 0},
                {QStringLiteral("baseY"), 0},
                {QStringLiteral("baseAngle"), 0},
                {QStringLiteral("baseScale"), 1},
                {QStringLiteral("axisLength"), 40},
                {QStringLiteral("showAxes"), true},
                {QStringLiteral("writeFlowVars"), true}};
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
  } else if (key == QLatin1String("serial_exchange")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("mode"), QStringLiteral("exchange")},
                {QStringLiteral("serialPort"), QString()},
                {QStringLiteral("baudrate"), 115200},
                {QStringLiteral("dataBits"), 8},
                {QStringLiteral("parity"), QStringLiteral("N")},
                {QStringLiteral("stopbits"), 1},
                {QStringLiteral("flowControl"), QStringLiteral("none")},
                {QStringLiteral("rts"), true},
                {QStringLiteral("dtr"), true},
                {QStringLiteral("encoding"), QStringLiteral("text")},
                {QStringLiteral("responseEncoding"), QStringLiteral("text")},
                {QStringLiteral("value"), QStringLiteral("SIEANS-SERIAL-00042")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("maxBytes"), 65536},
                {QStringLiteral("clearInput"), false},
                {QStringLiteral("txFraming"), QStringLiteral("crlf")},
                {QStringLiteral("rxFraming"), QStringLiteral("crlf")},
                {QStringLiteral("responseBytes"), 8},
                {QStringLiteral("resultVar"), QStringLiteral("serial")}};
    } else if (key == QLatin1String("modbus_read")) {
    s.params = {{QStringLiteral("transport"), QStringLiteral("simulator")},
                {QStringLiteral("area"), QStringLiteral("holding")},
                {QStringLiteral("address"), 0},
                {QStringLiteral("count"), 1},
                {QStringLiteral("dataType"), QStringLiteral("uint16")},
                {QStringLiteral("byteOrder"), QStringLiteral("big")},
                {QStringLiteral("wordOrder"), QStringLiteral("big")},
                {QStringLiteral("timeoutMs"), 1500},
                {QStringLiteral("deviceId"), 1},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1502},
                {QStringLiteral("resultVar"), QStringLiteral("mbRead")}};
  } else if (key == QLatin1String("modbus_write")) {
    s.params = {{QStringLiteral("transport"), QStringLiteral("simulator")},
                {QStringLiteral("area"), QStringLiteral("holding")},
                {QStringLiteral("address"), 10},
                {QStringLiteral("dataType"), QStringLiteral("uint16")},
                {QStringLiteral("byteOrder"), QStringLiteral("big")},
                {QStringLiteral("wordOrder"), QStringLiteral("big")},
                {QStringLiteral("value"), 0},
                {QStringLiteral("timeoutMs"), 1500},
                {QStringLiteral("deviceId"), 1},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1502},
                {QStringLiteral("resultVar"), QStringLiteral("mbWrite")}};
  } else if (key == QLatin1String("modbus_wait")) {
    s.params = {{QStringLiteral("transport"), QStringLiteral("simulator")},
                {QStringLiteral("area"), QStringLiteral("holding")},
                {QStringLiteral("address"), 0},
                {QStringLiteral("dataType"), QStringLiteral("uint16")},
                {QStringLiteral("comparison"), QStringLiteral("eq")},
                {QStringLiteral("expectedValue"), 123},
                {QStringLiteral("triggerMode"), QStringLiteral("level")},
                {QStringLiteral("pollIntervalMs"), 100},
                {QStringLiteral("stableMs"), 0},
                {QStringLiteral("waitTimeoutMs"), 10000},
                {QStringLiteral("onTimeout"), QStringLiteral("error")},
                {QStringLiteral("timeoutMs"), 1500},
                {QStringLiteral("deviceId"), 1},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1502},
                {QStringLiteral("resultVar"), QStringLiteral("mbWait")}};
  } else if (key == QLatin1String("s7_read")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1102},
                {QStringLiteral("rack"), 0},
                {QStringLiteral("slot"), 1},
                {QStringLiteral("area"), QStringLiteral("db")},
                {QStringLiteral("dbNumber"), 1},
                {QStringLiteral("byteOffset"), 0},
                {QStringLiteral("bitOffset"), 0},
                {QStringLiteral("dataType"), QStringLiteral("uint16")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("count"), 1},
                {QStringLiteral("resultVar"), QStringLiteral("s7Read")}};
  } else if (key == QLatin1String("s7_write")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1102},
                {QStringLiteral("rack"), 0},
                {QStringLiteral("slot"), 1},
                {QStringLiteral("area"), QStringLiteral("db")},
                {QStringLiteral("dbNumber"), 1},
                {QStringLiteral("byteOffset"), 10},
                {QStringLiteral("bitOffset"), 0},
                {QStringLiteral("dataType"), QStringLiteral("uint16")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("value"), 0},
                {QStringLiteral("resultVar"), QStringLiteral("s7Write")}};
  } else if (key == QLatin1String("opcua_read")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
                {QStringLiteral("security"), QStringLiteral("None")},
                {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("requireGood"), true},
                {QStringLiteral("resultVar"), QStringLiteral("opcRead")}};
  } else if (key == QLatin1String("opcua_write")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
                {QStringLiteral("security"), QStringLiteral("None")},
                {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
                {QStringLiteral("dataType"), QStringLiteral("UInt32")},
                {QStringLiteral("value"), 0},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("resultVar"), QStringLiteral("opcWrite")}};
  } else if (key == QLatin1String("opcua_browse")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
                {QStringLiteral("security"), QStringLiteral("None")},
                {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS")},
                {QStringLiteral("browseLimit"), 100},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("resultVar"), QStringLiteral("opcBrowse")}};
  } else if (key == QLatin1String("opcua_wait")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("endpoint"), QStringLiteral("opc.tcp://127.0.0.1:4840/sieans/")},
                {QStringLiteral("security"), QStringLiteral("None")},
                {QStringLiteral("nodeId"), QStringLiteral("ns=2;s=SIEANS.Count")},
                {QStringLiteral("comparison"), QStringLiteral("eq")},
                {QStringLiteral("expectedValue"), 0},
                {QStringLiteral("triggerMode"), QStringLiteral("level")},
                {QStringLiteral("publishingIntervalMs"), 100},
                {QStringLiteral("waitTimeoutMs"), 10000},
                {QStringLiteral("onTimeout"), QStringLiteral("error")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("resultVar"), QStringLiteral("opcWait")}};
  } else if (key == QLatin1String("mqtt_publish")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1883},
                {QStringLiteral("security"), QStringLiteral("plain")},
                {QStringLiteral("topic"), QStringLiteral("sieans/inspection")},
                {QStringLiteral("encoding"), QStringLiteral("structured")},
                {QStringLiteral("qos"), 1},
                {QStringLiteral("retain"), true},
                {QStringLiteral("timeoutMs"), 5000},
                {QStringLiteral("value"), 0},
                {QStringLiteral("resultVar"), QStringLiteral("mqttPub")}};
  } else if (key == QLatin1String("mqtt_receive")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 1883},
                {QStringLiteral("security"), QStringLiteral("plain")},
                {QStringLiteral("topic"), QStringLiteral("sieans/inspection")},
                {QStringLiteral("encoding"), QStringLiteral("structured")},
                {QStringLiteral("qos"), 1},
                {QStringLiteral("acceptRetained"), true},
                {QStringLiteral("timeoutMs"), 5000},
                {QStringLiteral("resultVar"), QStringLiteral("mqttRecv")}};
  } else if (key == QLatin1String("yolo")) {
    s.params = {{QStringLiteral("model"), QStringLiteral("yolo11n.pt")},
                {QStringLiteral("device"), QStringLiteral("cpu")},
                {QStringLiteral("confidence"), 0.25},
                {QStringLiteral("iou"), 0.45},
                {QStringLiteral("imageSize"), 640},
                {QStringLiteral("classes"), QString()},
                {QStringLiteral("maxDetections"), 50},
                {QStringLiteral("minArea"), 1},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("showLabels"), true},
                {QStringLiteral("resultVar"), QStringLiteral("yolo")}};
  } else if (key == QLatin1String("yolo_segment")) {
    s.params = {{QStringLiteral("model"), QStringLiteral("yolo11n-seg.pt")},
                {QStringLiteral("device"), QStringLiteral("cpu")},
                {QStringLiteral("confidence"), 0.25},
                {QStringLiteral("iou"), 0.45},
                {QStringLiteral("imageSize"), 640},
                {QStringLiteral("classes"), QString()},
                {QStringLiteral("maxDetections"), 50},
                {QStringLiteral("minArea"), 1},
                {QStringLiteral("contourTolerance"), 0.5},
                {QStringLiteral("overlayAlpha"), 0.35},
                {QStringLiteral("output"), QStringLiteral("overlay")},
                {QStringLiteral("showOverlay"), true},
                {QStringLiteral("showLabels"), true},
                {QStringLiteral("resultVar"), QStringLiteral("yoloSeg")}};
  } else if (key == QLatin1String("cloud_filter")) {
    s.params = {{QStringLiteral("inputSource"), QStringLiteral("soft_fixture")},
                {QStringLiteral("method"), QStringLiteral("voxel")},
                {QStringLiteral("voxelSize"), 1},
                {QStringLiteral("minX"), -100},
                {QStringLiteral("minY"), -100},
                {QStringLiteral("minZ"), -100},
                {QStringLiteral("maxX"), 100},
                {QStringLiteral("maxY"), 100},
                {QStringLiteral("maxZ"), 100},
                {QStringLiteral("neighbors"), 20},
                {QStringLiteral("stdRatio"), 2},
                {QStringLiteral("radius"), 3},
                {QStringLiteral("minPoints"), 6},
                {QStringLiteral("resultVar"), QStringLiteral("cloudFilt")}};
  } else if (key == QLatin1String("cloud_plane")) {
    s.params = {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
                {QStringLiteral("distanceThreshold"), 0.5},
                {QStringLiteral("iterations"), 500},
                {QStringLiteral("output"), QStringLiteral("inliers")},
                {QStringLiteral("resultVar"), QStringLiteral("cloudPlane")}};
  } else if (key == QLatin1String("cloud_cluster")) {
    s.params = {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
                {QStringLiteral("eps"), 3},
                {QStringLiteral("minPoints"), 8},
                {QStringLiteral("resultVar"), QStringLiteral("cloudClust")}};
  } else if (key == QLatin1String("cloud_measure")) {
    s.params = {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
                {QStringLiteral("resultVar"), QStringLiteral("cloudMeas")}};
  } else if (key == QLatin1String("cloud_height")) {
    s.params = {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
                {QStringLiteral("baselineZ"), 0},
                {QStringLiteral("cellSize"), 1},
                {QStringLiteral("resultVar"), QStringLiteral("cloudHgt")}};
  } else if (key == QLatin1String("cloud_register")) {
    s.params = {{QStringLiteral("inputSource"), QStringLiteral("upstream")},
                {QStringLiteral("targetSource"), QStringLiteral("soft_register")},
                {QStringLiteral("method"), QStringLiteral("icp")},
                {QStringLiteral("maxDistance"), 5},
                {QStringLiteral("iterations"), 50},
                {QStringLiteral("resultVar"), QStringLiteral("cloudReg")}};
  } else if (key == QLatin1String("delay")) {
    s.params = {{QStringLiteral("milliseconds"), 100},
                {QStringLiteral("resultVar"), QStringLiteral("delay")}};
  } else if (key == QLatin1String("variables")) {
    s.params = {{QStringLiteral("scope"), QStringLiteral("flow")},
                {QStringLiteral("name"), QStringLiteral("counter")},
                {QStringLiteral("mode"), QStringLiteral("increment")},
                {QStringLiteral("value"), 1},
                {QStringLiteral("resultVar"), QStringLiteral("vars")}};
  } else if (key == QLatin1String("tcp_exchange")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("mode"), QStringLiteral("exchange")},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 9000},
                {QStringLiteral("encoding"), QStringLiteral("text")},
                {QStringLiteral("value"), QStringLiteral("SIEANS 检测完成")},
                {QStringLiteral("txFraming"), QStringLiteral("crlf")},
                {QStringLiteral("rxFraming"), QStringLiteral("crlf")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("maxBytes"), 65536},
                {QStringLiteral("responseBytes"), 8},
                {QStringLiteral("resultVar"), QStringLiteral("tcpEx")}};
  } else if (key == QLatin1String("udp_exchange")) {
    s.params = {{QStringLiteral("connection"), QStringLiteral("simulator")},
                {QStringLiteral("mode"), QStringLiteral("exchange")},
                {QStringLiteral("host"), QStringLiteral("127.0.0.1")},
                {QStringLiteral("port"), 9000},
                {QStringLiteral("encoding"), QStringLiteral("text")},
                {QStringLiteral("value"), QStringLiteral("SIEANS 检测完成")},
                {QStringLiteral("timeoutMs"), 3000},
                {QStringLiteral("maxBytes"), 65536},
                {QStringLiteral("localPort"), 0},
                {QStringLiteral("resultVar"), QStringLiteral("udpEx")}};
  } else if (key == QLatin1String("script")) {
    s.params = {{QStringLiteral("code"),
                 QStringLiteral("def run(ctx):\n"
                                "    return dict(result=dict(scriptOut=4242, passed=True))\n")},
                {QStringLiteral("timeoutMs"), 5000},
                {QStringLiteral("arguments"), QVariantMap{{QStringLiteral("count"), 0}}},
                {QStringLiteral("resultVar"), QStringLiteral("script")}};
  } else if (key == QLatin1String("plugin")) {
    s.params = {{QStringLiteral("pluginId"), QStringLiteral("sieans-soft-smoke")},
                {QStringLiteral("pluginVersion"), QStringLiteral("1.0.0")},
                {QStringLiteral("operatorId"), QStringLiteral("fixed-value")},
                {QStringLiteral("arguments"), QVariantMap{{QStringLiteral("value"), 9001}}},
                {QStringLiteral("resultVar"), QStringLiteral("plugin")}};
  } else if (key == QLatin1String("result_gate")) {
    s.params = {{QStringLiteral("minCount"), 1},
                {QStringLiteral("sourceVar"), QStringLiteral("barcodeCount")},
                {QStringLiteral("passVar"), QStringLiteral("passGate")}};
  } else if (key == QLatin1String("save_image")) {
    s.params = {{QStringLiteral("dir"),
                 workbenchArtifactsDir()}};
  } else if (key == QLatin1String("condition")) {
    s.params = {
        {QStringLiteral("logic"), QStringLiteral("and")},
        {QStringLiteral("comparison"), QStringLiteral("eq")},
        {QStringLiteral("left"), QStringLiteral("barcodeCount")},
        {QStringLiteral("right"), 1},
        {QStringLiteral("writePassGate"), true},
        {QStringLiteral("rules"),
         QVariantList{QVariantMap{{QStringLiteral("left"), QStringLiteral("barcodeCount")},
                                  {QStringLiteral("comparison"), QStringLiteral("eq")},
                                  {QStringLiteral("right"), 1},
                                  {QStringLiteral("enabled"), true}}}}};
  } else if (key == QLatin1String("branch")) {
    s.params = {
        {QStringLiteral("defaultPathId"), QStringLiteral("default")},
        {QStringLiteral("paths"),
         QVariantList{
             QVariantMap{{QStringLiteral("id"), QStringLiteral("path1")},
                         {QStringLiteral("name"), QStringLiteral("分支1")},
                         {QStringLiteral("left"), QStringLiteral("barcodeCount")},
                         {QStringLiteral("comparison"), QStringLiteral("eq")},
                         {QStringLiteral("right"), 1},
                         {QStringLiteral("enabled"), true}},
             QVariantMap{{QStringLiteral("id"), QStringLiteral("path2")},
                         {QStringLiteral("name"), QStringLiteral("分支2")},
                         {QStringLiteral("left"), QStringLiteral("barcodeCount")},
                         {QStringLiteral("comparison"), QStringLiteral("eq")},
                         {QStringLiteral("right"), 0},
                         {QStringLiteral("enabled"), true}},
             QVariantMap{{QStringLiteral("id"), QStringLiteral("default")},
                         {QStringLiteral("name"), QStringLiteral("默认")},
                         {QStringLiteral("left"), QString()},
                         {QStringLiteral("comparison"), QStringLiteral("is_true")},
                         {QStringLiteral("right"), QString()},
                         {QStringLiteral("enabled"), true}},
         }}};
  } else if (key == QLatin1String("branch_merge")) {
    s.params = {};
  } else if (key == QLatin1String("subflow")) {
    QString sfId;
    if (!document_.subflows().isEmpty()) sfId = document_.subflows().first().id;
    s.params = {{QStringLiteral("subflowId"), sfId},
                {QStringLiteral("stateMode"), QStringLiteral("reset")},
                {QStringLiteral("arguments"), QVariantMap{}}};
  } else if (key == QLatin1String("loop")) {
    QString sfId;
    if (!document_.subflows().isEmpty()) sfId = document_.subflows().first().id;
    s.params = {{QStringLiteral("subflowId"), sfId},
                {QStringLiteral("stateMode"), QStringLiteral("reset")},
                {QStringLiteral("mode"), QStringLiteral("count")},
                {QStringLiteral("iterations"), 3},
                {QStringLiteral("frameMode"), QStringLiteral("previous")},
                {QStringLiteral("stopField"), QStringLiteral("passed")},
                {QStringLiteral("stopValue"), true},
                {QStringLiteral("arguments"), QVariantMap{}}};
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
    e.when = QStringLiteral("always");
    if (const FlowStep* fs = document_.findStep(from)) {
      if (fs->operation == QLatin1String("condition")) {
        bool hasTrue = false, hasFalse = false;
        for (const FlowEdge& ex : document_.edges()) {
          if (ex.from != from) continue;
          if (ex.when == QLatin1String("true")) hasTrue = true;
          if (ex.when == QLatin1String("false")) hasFalse = true;
        }
        if (!hasTrue) e.when = QStringLiteral("true");
        else if (!hasFalse) e.when = QStringLiteral("false");
      }
    }
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
  commitCanvasUndo(QStringLiteral("添加模块"));
  markProjectDirty();
}

void MainWindow::onStructuredParamEdited(const QString& nodeId, const QString& key,
                                         const QVariant& value) {
  if (FlowStep* s = document_.findStep(nodeId)) {
    s->params.insert(key, value);
    auditParam(nodeId, key, QStringLiteral("…"),
               key == QLatin1String("templateLibrary")
                   ? QStringLiteral("%1 项").arg(value.toList().size())
                   : key);
  }
  commitCanvasUndo(QStringLiteral("参数"));
  markProjectDirty();
}

void MainWindow::focusFilmstripResult(const QString& path, const QString& nodeId) {
  int first = -1;
  if (result_table_ && !path.isEmpty()) {
    const QString base = QFileInfo(path).fileName();
    for (int r = 0; r < result_table_->rowCount(); ++r) {
      auto* it = result_table_->item(r, 0);
      if (!it) continue;
      const QString stamped = it->data(Qt::UserRole).toString();
      const bool match = stamped == path || QFileInfo(stamped).fileName() == base;
      if (match && first < 0) {
        first = r;
        result_table_->selectRow(r);
        result_table_->scrollToItem(it);
      }
    }
    if (first >= 0 && bottom_tabs_) {
      for (int i = 0; i < bottom_tabs_->count(); ++i) {
        QWidget* w = bottom_tabs_->widget(i);
        if (w && (w == result_table_->parentWidget() || w->isAncestorOf(result_table_))) {
          bottom_tabs_->setCurrentIndex(i);
          break;
        }
      }
    }
  }
  QString focusId = nodeId;
  if (focusId.isEmpty() && result_table_) {
    if (auto* it = result_table_->currentItem() ? result_table_->item(result_table_->currentRow(), 0)
                                                : nullptr)
      focusId = it->data(Qt::UserRole + 2).toString();
  }
  if (focusId.isEmpty() && first >= 0 && document_.findStep(QStringLiteral("loc1")))
    focusId = QStringLiteral("loc1");
  if (!focusId.isEmpty() && flow_scene_) flow_scene_->selectNode(focusId);
}

void MainWindow::onSparkFilmstripJump(const QVariantMap& bag) {
  QVariantMap hit;
  if (filmstrip_) hit = FilmstripBar::seekFromSparkJump(filmstrip_, bag, true);
  const QString path = hit.value(QStringLiteral("path")).toString().isEmpty()
                           ? bag.value(QStringLiteral("frame")).toString()
                           : hit.value(QStringLiteral("path")).toString();
  const QString nodeId = bag.value(QStringLiteral("nodeId")).toString();
  focusFilmstripResult(path, nodeId);
  if (hit.value(QStringLiteral("ok")).toBool())
    showStatus(QStringLiteral("跳帧 · 胶片#%1 · %2")
                   .arg(hit.value(QStringLiteral("index")).toInt() + 1)
                   .arg(hit.value(QStringLiteral("matchedBy")).toString()));
  else
    showStatus(QStringLiteral("跳帧 · 胶片未命中"));
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
    if (s->operation == QLatin1String("condition") &&
        (key == QLatin1String("left") || key == QLatin1String("right") ||
         key == QLatin1String("comparison") || key == QLatin1String("logic"))) {
      QVariantList rules = s->params.value(QStringLiteral("rules")).toList();
      if (rules.isEmpty()) {
        QVariantMap r0;
        r0.insert(QStringLiteral("left"), s->params.value(QStringLiteral("left")));
        r0.insert(QStringLiteral("comparison"), s->params.value(QStringLiteral("comparison")));
        r0.insert(QStringLiteral("right"), s->params.value(QStringLiteral("right")));
        r0.insert(QStringLiteral("enabled"), true);
        rules.push_back(r0);
      } else {
        QVariantMap r0 = rules.first().toMap();
        if (key != QLatin1String("logic")) r0.insert(key, s->params.value(key));
        rules[0] = r0;
      }
      s->params.insert(QStringLiteral("rules"), rules);
    }
    if (s->operation == QLatin1String("condition") && key == QLatin1String("rules")) {
      const QVariantList rules = s->params.value(QStringLiteral("rules")).toList();
      if (!rules.isEmpty()) {
        const QVariantMap r0 = rules.first().toMap();
        s->params.insert(QStringLiteral("left"), r0.value(QStringLiteral("left")));
        s->params.insert(QStringLiteral("comparison"), r0.value(QStringLiteral("comparison")));
        s->params.insert(QStringLiteral("right"), r0.value(QStringLiteral("right")));
      }
    }
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
    if (key == QLatin1String("roiX") || key == QLatin1String("roiY") ||
        key == QLatin1String("roiW") || key == QLatin1String("roiH") ||
        key == QLatin1String("roi"))
      syncCanvasRoiFromSelection();
  }
  commitCanvasUndo(QStringLiteral("参数"));
  markProjectDirty();
}

void MainWindow::onParamsReverted(const QString& nodeId, const QVariantMap& snapshot) {
  if (nodeId == QLatin1String("source")) {
    document_.sourceConfigMut() = snapshot;
  } else if (FlowStep* s = document_.findStep(nodeId)) {
    s->params = snapshot;
  }
  pushSoftControls();
  logResult(QStringLiteral("已放弃属性修改: %1").arg(nodeId));
  commitCanvasUndo(QStringLiteral("放弃属性"));
  markProjectDirty();
}

void MainWindow::onOpenSubflowManager() {
  SubflowDialog dlg(&document_, this);
  dlg.exec();
  applyDocumentToUi();
  const int n = document_.subflows().size();
  logResult(QStringLiteral("子流程管理已关闭 · 定义 %1 个").arg(n));
  showStatus(QStringLiteral("子流程定义 %1 个").arg(n), 2500);
}

void MainWindow::onOpenFlowIo() {
  FlowIoDialog dlg(document_.flowIo(), this);
  dlg.setPreviewVars(flow_vars_);
  if (workbenchIsHeadless()) return;
  if (dlg.exec() != QDialog::Accepted) return;
  document_.setFlowIo(dlg.resultIo());
  publishHostToFlowVars();
  syncVarsToUi(false);
  const int nin = document_.flowIo().value(QStringLiteral("inputs")).toList().size();
  const int nout = document_.flowIo().value(QStringLiteral("outputs")).toList().size();
  logResult(QStringLiteral("流程 I/O 已更新 · 输入 %1 · 输出 %2").arg(nin).arg(nout));
  showStatus(QStringLiteral("流程 I/O 绑定已保存"));
  refreshConfigStatus();
}

void MainWindow::syncCanvasRoiFromSelection() {
  if (!image_view_) return;
  const QString id = flow_scene_ ? flow_scene_->selectedNodeId() : QString();
  if (const FlowStep* s = document_.findStep(id)) {
    if (operationSupportsRoi(s->operation)) {
      const QRect r = roiFromParams(s->params);
      if (r.isValid())
        image_view_->setRoi(r, false);
      else
        image_view_->clearRoi(false);
      return;
    }
  }
  image_view_->clearRoi(false);
}

void MainWindow::onToggleRoiMode() {
  if (!image_view_ || !roi_action_) return;
  const bool want = roi_action_->isChecked();
  if (!want) {
    image_view_->setRoiMode(false);
    return;
  }
  const QString id = flow_scene_ ? flow_scene_->selectedNodeId() : QString();
  const FlowStep* s = document_.findStep(id);
  if (!s || !operationSupportsRoi(s->operation)) {
    roi_action_->blockSignals(true);
    roi_action_->setChecked(false);
    roi_action_->blockSignals(false);
    image_view_->setRoiMode(false);
    showStatus(QStringLiteral("请先选择带 ROI 的检测模块"));
    logResult(QStringLiteral("框选 ROI · 请先选择带 ROI 的检测模块"));
    return;
  }
  syncCanvasRoiFromSelection();
  image_view_->setRoiMode(true);
  if (image_tabs_ && image_view_) image_tabs_->setCurrentWidget(image_view_);
  showStatus(QStringLiteral("ROI 编辑：拖画新框，拖内部移动，拖角/边缩放"));
}

void MainWindow::applyCanvasRoi(const QRect& r) {
  if (applying_document_) return;
  const QString id = flow_scene_ ? flow_scene_->selectedNodeId() : QString();
  FlowStep* s = document_.findStep(id);
  if (!s || !operationSupportsRoi(s->operation)) return;
  const QRect cur = roiFromParams(s->params);
  const QRect n = r.normalized();
  if (cur == n) return;
  writeRoiToParams(s->params, n);
  document_.syncActiveIntoFlows();
  commitCanvasUndo(QStringLiteral("ROI"));
  markProjectDirty();
  if (prop_float_) prop_float_->showForStep(*s);
  logResult(QStringLiteral("ROI 已更新 · %1 [%2,%3,%4,%5]")
                .arg(s->name)
                .arg(n.x())
                .arg(n.y())
                .arg(n.width())
                .arg(n.height()));
}

void MainWindow::onClearSelectedRoi() {
  if (applying_document_) return;
  const QString id = flow_scene_ ? flow_scene_->selectedNodeId() : QString();
  FlowStep* s = document_.findStep(id);
  if (!s || !operationSupportsRoi(s->operation)) {
    if (image_view_) image_view_->clearRoi(false);
    return;
  }
  const QRect cur = roiFromParams(s->params);
  if (cur.isNull()) {
    if (image_view_) image_view_->clearRoi(false);
    return;
  }
  clearRoiFromParams(s->params);
  document_.syncActiveIntoFlows();
  if (image_view_) image_view_->clearRoi(false);
  commitCanvasUndo(QStringLiteral("清除 ROI"));
  markProjectDirty();
  if (prop_float_) prop_float_->showForStep(*s);
  logResult(QStringLiteral("已清除模块 ROI · %1").arg(s->name));
}

bool MainWindow::fireStringTrigger(const QString& text, const QString& reason) {
  const QString payload = text;
  if (payload.isEmpty()) return false;
  const QVector<QVariantMap> cmds = document_.collectStringCommands(payload);
  if (cmds.isEmpty()) return false;
  const QString why = reason.isEmpty() ? QStringLiteral("外部字符串") : reason;
  logResult(QStringLiteral("字符串触发匹配「%1」×%2 · %3")
                .arg(payload.left(48))
                .arg(cmds.size())
                .arg(why));
  dispatchGlobalTriggers(cmds);
  return true;
}

void MainWindow::injectRunTrigger() {
  const bool hit = fireStringTrigger(QStringLiteral("RUN"), QStringLiteral("注入RUN"));
  showStatus(hit ? QStringLiteral("已注入 RUN") : QStringLiteral("注入 RUN：无匹配字符串触发"));
}

void MainWindow::injectStopTrigger() {
  const bool hit = fireStringTrigger(QStringLiteral("STOP"), QStringLiteral("注入STOP"));
  showStatus(hit ? QStringLiteral("已注入 STOP") : QStringLiteral("注入 STOP：无匹配字符串触发"));
}

void MainWindow::fireEventTriggers(const QString& eventName, bool skipRerun) {
  if (dispatching_triggers_) return;
  const QString name = eventName.trimmed();
  if (name.isEmpty()) return;
  QVector<QVariantMap> cmds = document_.collectEventCommands(name);
  if (skipRerun) {
    QVector<QVariantMap> kept;
    for (const QVariantMap& c : cmds) {
      const QString typ = c.value(QStringLiteral("type")).toString();
      if (typ == QStringLiteral("执行·单次") || typ == QStringLiteral("执行") ||
          typ == QStringLiteral("执行·连续") || typ == QStringLiteral("执行·继续"))
        continue;
      kept.append(c);
    }
    cmds = kept;
  }
  if (cmds.isEmpty()) return;
  logResult(QStringLiteral("事件触发「%1」×%2").arg(name).arg(cmds.size()));
  dispatching_triggers_ = true;
  dispatchGlobalTriggers(cmds);
  dispatching_triggers_ = false;
}

void MainWindow::rememberRecentFile(const QString& path) {
  if (path.trimmed().isEmpty()) return;
  recent_files_.remember(path);
  rebuildRecentMenu();
}

void MainWindow::rebuildRecentMenu() {
  if (!recent_menu_) return;
  recent_menu_->clear();
  int shown = 0;
  for (const QString& raw : recent_files_.paths()) {
    const QFileInfo fi(raw);
    if (!fi.exists()) continue;
    auto* act = recent_menu_->addAction(fi.fileName());
    act->setToolTip(fi.absoluteFilePath());
    const QString abs = fi.absoluteFilePath();
    QObject::connect(act, &QAction::triggered, this, [this, abs]() { openRecentFile(abs); });
    ++shown;
  }
  if (shown == 0) {
    auto* empty = recent_menu_->addAction(QStringLiteral("（无最近方案）"));
    empty->setEnabled(false);
  }
  recent_menu_->addSeparator();
  auto* clr = recent_menu_->addAction(QStringLiteral("清除最近记录"));
  QObject::connect(clr, &QAction::triggered, this, [this]() {
    recent_files_.clear();
    rebuildRecentMenu();
  });
}

void MainWindow::openRecentFile(const QString& path) {
  const QFileInfo fi(path);
  if (!fi.exists()) {
    recent_files_.remove(path);
    rebuildRecentMenu();
    showStatus(QStringLiteral("最近方案已缺失，已从列表移除"));
    return;
  }
  if (!confirmDiscardOrSave()) return;
  const QString abs = fi.absoluteFilePath();
  const QString suffix = fi.suffix().toLower();
  QString err;
  if (suffix == QLatin1String("prc")) {
    const FlowDef imported = document_.importPrcFromFile(abs, &err);
    if (imported.id.isEmpty()) {
      if (!workbenchIsHeadless())
        QMessageBox::warning(this, QStringLiteral("打开失败"), err);
      logResult(QStringLiteral("打开最近流程失败：%1").arg(err));
      return;
    }
    document_.activateFlow(imported.id);
    applyDocumentToUi();
    markProjectDirty();
    rememberRecentFile(abs);
    logResult(QStringLiteral("已从最近列表导入流程：%1").arg(imported.name));
    return;
  }
  if (!document_.loadFromFile(abs, &err)) {
    if (!workbenchIsHeadless())
      QMessageBox::warning(this, QStringLiteral("打开失败"), err);
    logResult(QStringLiteral("打开最近方案失败：%1").arg(err));
    return;
  }
  applyDocumentToUi();
  markProjectClean();
  rememberRecentFile(abs);
  logResult(QStringLiteral("已打开最近方案：%1 · %2 步").arg(abs).arg(document_.steps().size()));
}

void MainWindow::dispatchGlobalTriggers(const QVector<QVariantMap>& cmds) {
  for (const QVariantMap& cmd : cmds) {
    const QString typ = cmd.value(QStringLiteral("type")).toString();
    const QString cfg = cmd.value(QStringLiteral("config")).toString();
    if (typ == QStringLiteral("执行·单次") || typ == QStringLiteral("执行")) {
      onRunOnce();
    } else if (typ == QStringLiteral("执行·连续") || typ == QStringLiteral("执行·继续")) {
      onRunContinuous();
    } else if (typ == QStringLiteral("执行·停止")) {
      onStopRun();
    } else if (typ == QStringLiteral("执行·暂停")) {
      if (act_pause_ && act_pause_->isEnabled()) act_pause_->trigger();
    } else if (typ == QStringLiteral("状态·报警")) {
      const QString why = cfg.isEmpty() ? QStringLiteral("触发·报警") : cfg;
      if (host_sm_) host_sm_->applyState(QStringLiteral("Alarm"));
      if (host_strip_) host_strip_->setAlarm(true, why);
    } else if (typ == QStringLiteral("状态·清除报警")) {
      if (host_sm_) host_sm_->applyState(QStringLiteral("Idle"));
      if (host_strip_) host_strip_->setAlarm(false);
    } else if (typ == QStringLiteral("注入·RUN")) {
      fireStringTrigger(QStringLiteral("RUN"), QStringLiteral("注入·RUN"));
    } else if (typ == QStringLiteral("注入·STOP")) {
      fireStringTrigger(QStringLiteral("STOP"), QStringLiteral("注入·STOP"));
    } else if (typ == QStringLiteral("方案保存") || typ == QStringLiteral("方案另存")) {
      if (!workbenchIsHeadless()) onSaveProject();
    } else {
      logResult(QStringLiteral("未接线触发命令：%1").arg(typ) +
                (cfg.isEmpty() ? QString() : QStringLiteral(" · %1").arg(cfg)));
    }
  }
}

void MainWindow::onOpenGlobalTriggers() {
  if (workbenchIsHeadless()) return;
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("全局触发"));
  dlg.resize(560, 560);
  auto* lay = new QVBoxLayout(&dlg);
  const QStringList cmdItems = {QStringLiteral("执行·单次"), QStringLiteral("执行·连续"),
                                QStringLiteral("执行·停止"), QStringLiteral("执行·暂停"),
                                QStringLiteral("状态·报警"), QStringLiteral("状态·清除报警"),
                                QStringLiteral("注入·RUN"), QStringLiteral("注入·STOP")};
  lay->addWidget(new QLabel(
      QStringLiteral("字符串触发（部分匹配）→ 执行·单次 / 连续 / 停止。由通信收数或注入派发。配置随方案保存。无真 PLC。")));
  auto* list = new QListWidget;
  lay->addWidget(list, 1);
  auto* patEdit = new QLineEdit;
  patEdit->setPlaceholderText(QStringLiteral("匹配字符串，如 RUN / STOP"));
  auto* cmdBox = new QComboBox;
  cmdBox->addItems(cmdItems);
  auto* partial = new QCheckBox(QStringLiteral("部分匹配"));
  partial->setChecked(true);
  lay->addWidget(patEdit);
  lay->addWidget(cmdBox);
  lay->addWidget(partial);
  auto* btns = new QHBoxLayout;
  auto* addBtn = new QPushButton(QStringLiteral("添加"));
  auto* delBtn = new QPushButton(QStringLiteral("删除"));
  btns->addWidget(addBtn);
  btns->addWidget(delBtn);
  btns->addStretch();
  lay->addLayout(btns);

  lay->addWidget(new QLabel(
      QStringLiteral("事件触发：流程开始（过滤再跑）、流程结束、流程NG（passGate 失败）。不写到冒烟种子。")));
  auto* evList = new QListWidget;
  lay->addWidget(evList, 1);
  auto* evBox = new QComboBox;
  evBox->addItems({QStringLiteral("流程开始"), QStringLiteral("流程结束"),
                   QStringLiteral("流程NG")});
  auto* evCmd = new QComboBox;
  evCmd->addItems(cmdItems);
  evCmd->setCurrentText(QStringLiteral("状态·报警"));
  lay->addWidget(evBox);
  lay->addWidget(evCmd);
  auto* evBtns = new QHBoxLayout;
  auto* evAdd = new QPushButton(QStringLiteral("添加事件"));
  auto* evDel = new QPushButton(QStringLiteral("删除事件"));
  auto* closeBtn = new QPushButton(QStringLiteral("关闭"));
  evBtns->addWidget(evAdd);
  evBtns->addWidget(evDel);
  evBtns->addStretch();
  evBtns->addWidget(closeBtn);
  lay->addLayout(evBtns);

  auto reload = [this, list, evList]() {
    list->clear();
    const QVariantList rows =
        document_.globalTriggers().value(QStringLiteral("strings")).toList();
    for (int i = 0; i < rows.size(); ++i) {
      const QVariantMap row = rows.at(i).toMap();
      const QString needle = row.value(QStringLiteral("pattern"),
                                       row.value(QStringLiteral("event")))
                                 .toString();
      const QString typ = row.value(QStringLiteral("commandType"),
                                    row.value(QStringLiteral("command")))
                              .toString();
      const bool en = !row.contains(QStringLiteral("enabled")) ||
                      row.value(QStringLiteral("enabled")).toBool();
      const bool part = row.contains(QStringLiteral("partial"))
                            ? row.value(QStringLiteral("partial")).toBool()
                            : true;
      auto* item = new QListWidgetItem(
          QStringLiteral("%1  →  %2  (%3%4)")
              .arg(needle, typ.isEmpty() ? QStringLiteral("commands[]") : typ,
                   part ? QStringLiteral("部分") : QStringLiteral("全等"),
                   en ? QString() : QStringLiteral(" · 禁用")));
      item->setData(Qt::UserRole, i);
      list->addItem(item);
    }
    evList->clear();
    const QVariantList evs =
        document_.globalTriggers().value(QStringLiteral("events")).toList();
    for (int i = 0; i < evs.size(); ++i) {
      const QVariantMap row = evs.at(i).toMap();
      const QString ev = row.value(QStringLiteral("event")).toString();
      const QString typ = row.value(QStringLiteral("commandType"),
                                    row.value(QStringLiteral("command")))
                              .toString();
      const bool en = !row.contains(QStringLiteral("enabled")) ||
                      row.value(QStringLiteral("enabled")).toBool();
      auto* item = new QListWidgetItem(
          QStringLiteral("%1  →  %2%3")
              .arg(ev, typ.isEmpty() ? QStringLiteral("commands[]") : typ,
                   en ? QString() : QStringLiteral("  · 禁用")));
      item->setData(Qt::UserRole, i);
      evList->addItem(item);
    }
  };
  reload();

  QDialog* box = &dlg;
  QObject::connect(addBtn, &QPushButton::clicked, box, [=]() {
    const QString pat = patEdit->text().trimmed();
    if (pat.isEmpty()) {
      QMessageBox::information(box, QStringLiteral("全局触发"),
                               QStringLiteral("请填写匹配字符串"));
      return;
    }
    document_.addStringTrigger(pat, cmdBox->currentText(), partial->isChecked(), true);
    document_.syncActiveIntoFlows();
    markProjectDirty();
    reload();
    logResult(QStringLiteral("已添加字符串触发 · %1 → %2").arg(pat, cmdBox->currentText()));
  });
  QObject::connect(delBtn, &QPushButton::clicked, box, [this, list, reload]() {
    auto* item = list->currentItem();
    if (!item) return;
    const int idx = item->data(Qt::UserRole).toInt();
    QVariantMap bag = document_.globalTriggers();
    QVariantList rows = bag.value(QStringLiteral("strings")).toList();
    if (idx < 0 || idx >= rows.size()) return;
    rows.removeAt(idx);
    bag.insert(QStringLiteral("strings"), rows);
    document_.setGlobalTriggers(bag);
    document_.syncActiveIntoFlows();
    markProjectDirty();
    reload();
    logResult(QStringLiteral("已删除字符串触发"));
  });
  QObject::connect(evAdd, &QPushButton::clicked, box, [=]() {
    const QString ev = evBox->currentText().trimmed();
    if (document_.addEventTrigger(ev, evCmd->currentText(), true).isEmpty()) return;
    document_.syncActiveIntoFlows();
    markProjectDirty();
    reload();
    logResult(QStringLiteral("已添加事件触发 · %1 → %2").arg(ev, evCmd->currentText()));
  });
  QObject::connect(evDel, &QPushButton::clicked, box, [this, evList, reload]() {
    auto* item = evList->currentItem();
    if (!item) return;
    const int idx = item->data(Qt::UserRole).toInt();
    QVariantMap bag = document_.globalTriggers();
    QVariantList rows = bag.value(QStringLiteral("events")).toList();
    if (idx < 0 || idx >= rows.size()) return;
    rows.removeAt(idx);
    bag.insert(QStringLiteral("events"), rows);
    document_.setGlobalTriggers(bag);
    document_.syncActiveIntoFlows();
    markProjectDirty();
    reload();
    logResult(QStringLiteral("已删除事件触发"));
  });
  QObject::connect(closeBtn, &QPushButton::clicked, box, &QDialog::accept);
  dlg.exec();
}

void MainWindow::onOpenRecipeSwitch() {
  if (workbenchIsHeadless()) return;
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("产线配方 / 换型"));
  dlg.resize(460, 360);
  auto* lay = new QVBoxLayout(&dlg);
  lay->addWidget(new QLabel(
      QStringLiteral("本方案配方快照（按步骤名+算子套用参数）。不打开其它工程、不新增算子。")));
  auto* list = new QListWidget;
  lay->addWidget(list, 1);
  auto* nameEdit = new QLineEdit;
  nameEdit->setPlaceholderText(QStringLiteral("配方名（保存时必填）"));
  auto* noteEdit = new QLineEdit;
  noteEdit->setPlaceholderText(QStringLiteral("备注（可选）"));
  auto* varEdit = new QLineEdit;
  varEdit->setPlaceholderText(QStringLiteral("产品变体，如 A型（可选）"));
  lay->addWidget(nameEdit);
  lay->addWidget(noteEdit);
  lay->addWidget(varEdit);
  auto* btns = new QHBoxLayout;
  auto* saveBtn = new QPushButton(QStringLiteral("保存当前为配方"));
  auto* applyBtn = new QPushButton(QStringLiteral("套用"));
  auto* rollbackBtn = new QPushButton(QStringLiteral("一键回滚"));
  auto* libBtn = new QPushButton(QStringLiteral("工程库换型…"));
  auto* delBtn = new QPushButton(QStringLiteral("删除"));
  auto* closeBtn = new QPushButton(QStringLiteral("关闭"));
  auto* depthLab = new QLabel;
  depthLab->setStyleSheet(QStringLiteral("color:#b9a;font-size:11px;"));
  btns->addWidget(saveBtn);
  btns->addWidget(applyBtn);
  btns->addWidget(rollbackBtn);
  btns->addWidget(depthLab);
  btns->addWidget(libBtn);
  btns->addWidget(delBtn);
  btns->addStretch();
  btns->addWidget(closeBtn);
  lay->addLayout(btns);

  auto reload = [this, list]() {
    list->clear();
    for (const QJsonValue& v : document_.recipesJson()) {
      const QJsonObject o = v.toObject();
      const QString id = o.value(QStringLiteral("id")).toString();
      const QString name = o.value(QStringLiteral("name")).toString();
      const QString variant = o.value(QStringLiteral("variant")).toString();
      const int n = o.value(QStringLiteral("stepCount")).toInt();
      QString lab = name;
      if (!variant.isEmpty()) lab += QStringLiteral(" · %1").arg(variant);
      lab += QStringLiteral("  (%1步)").arg(n);
      if (id == document_.activeRecipeId()) lab += QStringLiteral("  ←当前");
      auto* item = new QListWidgetItem(lab);
      item->setData(Qt::UserRole, id);
      list->addItem(item);
    }
  };
  reload();

  auto selectedId = [list]() -> QString {
    auto* item = list->currentItem();
    return item ? item->data(Qt::UserRole).toString() : QString();
  };

  auto refreshRollback = [this, rollbackBtn, depthLab]() {
    const int d = document_.recipeRollbackDepth();
    rollbackBtn->setEnabled(d > 0);
    depthLab->setText(d > 0 ? QStringLiteral("回滚栈 %1").arg(d) : QString());
  };
  refreshRollback();

  QDialog* box = &dlg;
  QObject::connect(saveBtn, &QPushButton::clicked, box, [this, box, nameEdit, noteEdit, varEdit, reload]() {
    QString name = nameEdit->text().trimmed();
    if (name.isEmpty()) {
      QMessageBox::information(box, QStringLiteral("产线配方"),
                               QStringLiteral("请填写配方名"));
      return;
    }
    const QVariantMap entry =
        document_.captureRecipe(name, noteEdit->text(), varEdit->text());
    document_.syncActiveIntoFlows();
    markProjectDirty();
    refreshVariantChip();
    reload();
    logResult(QStringLiteral("已保存配方 · %1 · %2 步")
                  .arg(entry.value(QStringLiteral("name")).toString())
                  .arg(entry.value(QStringLiteral("stepCount")).toInt()));
  });
  QObject::connect(applyBtn, &QPushButton::clicked, box, [this, box, selectedId, reload]() {
    const QString id = selectedId();
    if (id.isEmpty()) {
      QMessageBox::information(box, QStringLiteral("产线配方"),
                               QStringLiteral("请选择要套用的配方"));
      return;
    }
    QString err;
    const QVariantMap st = document_.applyRecipeWithRollback(id, &err);
    if (!err.isEmpty()) {
      QMessageBox::warning(box, QStringLiteral("产线配方"), err);
      return;
    }
    document_.syncActiveIntoFlows();
    markProjectDirty();
    refreshVariantChip();
    reload();
    logResult(QStringLiteral("已套用配方 · %1 · 步骤 %2 · 跳过 %3")
                  .arg(st.value(QStringLiteral("name")).toString())
                  .arg(st.value(QStringLiteral("applied")).toInt())
                  .arg(st.value(QStringLiteral("skipped")).toInt()));
    commitCanvasUndo(QStringLiteral("套用配方"));
    showStatus(QStringLiteral("已套用配方 %1").arg(st.value(QStringLiteral("name")).toString()));
  });
  QObject::connect(delBtn, &QPushButton::clicked, box, [this, selectedId, reload, refreshRollback]() {
    const QString id = selectedId();
    if (id.isEmpty()) return;
    if (!document_.deleteRecipe(id)) return;
    document_.syncActiveIntoFlows();
    markProjectDirty();
    refreshVariantChip();
    reload();
    refreshRollback();
    logResult(QStringLiteral("已删除配方"));
  });
  QObject::connect(rollbackBtn, &QPushButton::clicked, box, [this, box, reload, refreshRollback]() {
    QString err;
    const QVariantMap st = document_.rollbackLastRecipe(&err);
    if (!st.value(QStringLiteral("ok")).toBool()) {
      QMessageBox::information(box, QStringLiteral("产线配方"),
                               err.isEmpty() ? QStringLiteral("没有可回滚的配方快照") : err);
      return;
    }
    document_.syncActiveIntoFlows();
    markProjectDirty();
    commitCanvasUndo(QStringLiteral("回滚配方"));
    refreshVariantChip();
    reload();
    refreshRollback();
    logResult(QStringLiteral("已回滚配方 · %1").arg(st.value(QStringLiteral("rolledBack")).toString()));
    showStatus(QStringLiteral("已回滚配方"));
  });
  QObject::connect(libBtn, &QPushButton::clicked, box, [this, &dlg]() {
    dlg.accept();
    onLoadRecipeLibrary();
  });
  QObject::connect(applyBtn, &QPushButton::clicked, box, [refreshRollback]() { refreshRollback(); });
  // applyBtn already has a previous connect; this extra one just refreshes depth
  QObject::connect(closeBtn, &QPushButton::clicked, &dlg, &QDialog::accept);
  dlg.exec();
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


void MainWindow::commitCanvasUndo(const QString& label) {
  if (applying_document_ || restoring_canvas_undo_) return;
  document_.commitCanvasUndo(label);
  updateCanvasUndoActions();
}

void MainWindow::updateCanvasUndoActions() {
  if (act_undo_) {
    const bool ok = document_.canvasUndoDepth() > 0 && !run_mode_;
    act_undo_->setEnabled(ok);
    const QString lab = document_.canvasUndoLabel();
    act_undo_->setText(lab.isEmpty() ? QStringLiteral("撤销")
                                     : QStringLiteral("撤销 %1").arg(lab));
  }
  if (act_redo_) {
    const bool ok = document_.canvasRedoDepth() > 0 && !run_mode_;
    act_redo_->setEnabled(ok);
    const QString lab = document_.canvasRedoLabel();
    act_redo_->setText(lab.isEmpty() ? QStringLiteral("重做")
                                     : QStringLiteral("重做 %1").arg(lab));
  }
}

void MainWindow::reloadCanvasFromDocument() {
  applying_document_ = true;
  if (flow_scene_) flow_scene_->loadDocument(&document_);
  applying_document_ = false;
  if (prop_float_) prop_float_->hide();
  else if (prop_panel_) prop_panel_->clear();
  syncCanvasRoiFromSelection();
}

void MainWindow::undoCanvasEdit() {
  if (run_mode_) {
    showStatus(QStringLiteral("运行模式已锁定画布"));
    return;
  }
  if (!document_.undoCanvas()) {
    showStatus(QStringLiteral("无法撤销"));
    return;
  }
  restoring_canvas_undo_ = true;
  reloadCanvasFromDocument();
  restoring_canvas_undo_ = false;
  if (document_.canvasUndoAtClean())
    markProjectClean();
  else
    markProjectDirty();
  updateCanvasUndoActions();
  showStatus(QStringLiteral("已撤销画布编辑"));
  logResult(QStringLiteral("画布撤销"));
}

void MainWindow::redoCanvasEdit() {
  if (run_mode_) {
    showStatus(QStringLiteral("运行模式已锁定画布"));
    return;
  }
  if (!document_.redoCanvas()) {
    showStatus(QStringLiteral("无法重做"));
    return;
  }
  restoring_canvas_undo_ = true;
  reloadCanvasFromDocument();
  restoring_canvas_undo_ = false;
  if (document_.canvasUndoAtClean())
    markProjectClean();
  else
    markProjectDirty();
  updateCanvasUndoActions();
  showStatus(QStringLiteral("已重做画布编辑"));
  logResult(QStringLiteral("画布重做"));
}

bool MainWindow::importPointCloudPath(const QString& path, bool asTarget) {
  if (path.isEmpty()) return false;
  QString err;
  const PointCloud cloud = loadPointCloudFile(path, &err);
  if (cloud.isEmpty()) {
    showStatus(err.isEmpty() ? QStringLiteral("点云导入失败") : err);
    logResult(QStringLiteral("点云导入失败: %1").arg(err));
    return false;
  }
  imported_cloud_path_ = path;
  const QString id = flow_scene_ ? flow_scene_->selectedNodeId() : QString();
  if (FlowStep* s = document_.findStep(id)) {
    const bool isCloud =
        s->operation.startsWith(QLatin1String("cloud_"));
    if (isCloud) {
      if (asTarget && s->operation == QLatin1String("cloud_register")) {
        s->params.insert(QStringLiteral("targetSource"), QStringLiteral("file"));
        s->params.insert(QStringLiteral("targetPath"), path);
      } else {
        s->params.insert(QStringLiteral("inputSource"), QStringLiteral("file"));
        s->params.insert(QStringLiteral("cloudPath"), path);
      }
      document_.syncActiveIntoFlows();
      commitCanvasUndo(asTarget ? QStringLiteral("参考点云") : QStringLiteral("导入点云"));
      markProjectDirty();
      if (prop_float_) prop_float_->showForStep(*s);
    }
  }
  logResult(QStringLiteral("已导入点云 %1 · %2 点 · %3")
                .arg(QFileInfo(path).fileName())
                .arg(cloud.points.size())
                .arg(cloud.unit));
  showStatus(QStringLiteral("已导入点云 · %1 点").arg(cloud.points.size()));
  return true;
}

void MainWindow::onImportPointCloud() {
  if (workbenchIsHeadless()) return;
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("导入点云"), QString(),
      QStringLiteral("点云 (*.ply *.pcd *.xyz *.txt *.csv);;全部 (*.*)"));
  if (path.isEmpty()) return;
  importPointCloudPath(path, false);
}

void MainWindow::onImportCloudTarget() {
  if (workbenchIsHeadless()) return;
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("设置参考点云"), QString(),
      QStringLiteral("点云 (*.ply *.pcd *.xyz *.txt *.csv);;全部 (*.*)"));
  if (path.isEmpty()) return;
  importPointCloudPath(path, true);
}



void MainWindow::appendInspectionHistory() {
  if (applying_document_) return;
  InspectionRecord rec;
  rec.projectName = document_.name();
  QString flow;
  for (const FlowDef& f : document_.flows()) {
    if (f.id == document_.activeFlowId()) {
      flow = f.name;
      break;
    }
  }
  if (flow.isEmpty() && !document_.flows().isEmpty())
    flow = document_.flows().first().name;
  rec.flowName = flow;
  rec.recipeName = document_.activeRecipeName();
  bool ok = true;
  if (flow_vars_.contains(QStringLiteral("passGate"))) {
    const QVariant g = flow_vars_.value(QStringLiteral("passGate"));
    ok = g.toInt() != 0 || g.toBool();
  } else {
    const QString hr = flow_vars_.value(QStringLiteral("hostResult")).toString();
    if (!hr.isEmpty())
      ok = hr.compare(QLatin1String("OK"), Qt::CaseInsensitive) == 0 || hr == QLatin1String("1");
  }
  rec.verdict = ok ? QStringLiteral("OK") : QStringLiteral("NG");
  rec.elapsedMs = qint64(last_cycle_ms_ + 0.5);
  rec.detail = QStringLiteral("passGate=%1").arg(
      flow_vars_.value(QStringLiteral("passGate")).toString());
  inspection_history_.append(rec);
}

void MainWindow::onOpenInspectionHistory() {
  if (workbenchIsHeadless()) return;
  inspection_history_.load();
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("检测历史"));
  dlg.resize(760, 420);
  auto* lay = new QVBoxLayout(&dlg);
  auto* table = new QTableWidget(0, 6);
  table->setHorizontalHeaderLabels({QStringLiteral("时间"), QStringLiteral("工程"),
                                    QStringLiteral("流程"), QStringLiteral("配方"),
                                    QStringLiteral("判定"), QStringLiteral("耗时 (ms)")});
  table->setEditTriggers(QAbstractItemView::NoEditTriggers);
  table->setSelectionBehavior(QAbstractItemView::SelectRows);
  table->setSelectionMode(QAbstractItemView::SingleSelection);
  table->horizontalHeader()->setStretchLastSection(true);
  table->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
  const auto rows = inspection_history_.records();
  table->setRowCount(rows.size());
  for (int i = 0; i < rows.size(); ++i) {
    const InspectionRecord& r = rows[i];
    table->setItem(i, 0, new QTableWidgetItem(r.startedAt));
    table->setItem(i, 1, new QTableWidgetItem(r.projectName));
    table->setItem(i, 2, new QTableWidgetItem(r.flowName));
    table->setItem(i, 3, new QTableWidgetItem(r.recipeName));
    table->setItem(i, 4, new QTableWidgetItem(r.verdict));
    table->setItem(i, 5, new QTableWidgetItem(QString::number(r.elapsedMs)));
  }
  lay->addWidget(table);
  auto* hint = new QLabel(QStringLiteral("共 %1 条 · 本机记录，不写入方案文件")
                              .arg(inspection_history_.count()));
  hint->setWordWrap(true);
  lay->addWidget(hint);
  auto* close = new QPushButton(QStringLiteral("关闭"));
  QObject::connect(close, &QPushButton::clicked, &dlg, &QDialog::accept);
  lay->addWidget(close, 0, Qt::AlignRight);
  dlg.exec();
}

void MainWindow::refreshVariantChip() {
  if (!variant_chip_) return;
  refreshing_variant_chip_ = true;
  const QString current = variant_chip_->currentData().toString();
  const QString active = document_.activeRecipeVariant();
  variant_chip_->clear();
  variant_chip_->addItem(QStringLiteral("变体·—"), QString());
  const QStringList vars = document_.recipeVariants();
  int select = 0;
  const QString prefer = active.isEmpty() ? current : active;
  for (const QString& v : vars) {
    variant_chip_->addItem(QStringLiteral("变体·%1").arg(v), v);
    if (!prefer.isEmpty() && v == prefer) select = variant_chip_->count() - 1;
  }
  variant_chip_->setCurrentIndex(select);
  QString tip = QStringLiteral("按产品变体一键套用本方案配方（带回滚）");
  if (!vars.isEmpty()) tip += QStringLiteral("\n已登记：%1").arg(vars.join(QStringLiteral("、")));
  variant_chip_->setToolTip(tip);
  refreshing_variant_chip_ = false;
}

void MainWindow::onVariantChipChanged(int) {
  if (refreshing_variant_chip_ || applying_document_ || !variant_chip_) return;
  const QString variant = variant_chip_->currentData().toString().trimmed();
  if (variant.isEmpty()) return;
  QString err;
  const QVariantMap st = document_.applyRecipeVariant(variant, &err);
  if (st.isEmpty()) {
    showStatus(err.isEmpty() ? QStringLiteral("变体套用失败") : err);
    logResult(QStringLiteral("变体套用失败：%1").arg(err));
    refreshVariantChip();
    return;
  }
  document_.syncActiveIntoFlows();
  markProjectDirty();
  commitCanvasUndo(QStringLiteral("变体换型"));
  refreshVariantChip();
  logResult(QStringLiteral("变体快切「%1」→ 配方 %2 · 写入%3 跳过%4")
                .arg(variant, st.value(QStringLiteral("name")).toString())
                .arg(st.value(QStringLiteral("applied")).toInt())
                .arg(st.value(QStringLiteral("skipped")).toInt()));
  showStatus(QStringLiteral("已套用变体 %1").arg(variant));
}

void MainWindow::onLoadRecipeLibrary() {
  if (workbenchIsHeadless()) return;
  const auto libs = SieansDocument::discoverRecipeLibrary();
  if (libs.isEmpty()) {
    QMessageBox::information(this, QStringLiteral("工程库换型"),
                             QStringLiteral("未发现本机 .sieans 工程库文件"));
    return;
  }
  QDialog dlg(this);
  dlg.setWindowTitle(QStringLiteral("工程库换型"));
  dlg.resize(560, 420);
  auto* lay = new QVBoxLayout(&dlg);
  lay->addWidget(new QLabel(QStringLiteral("从本机工程库加载整案（替换当前方案）：")));
  auto* list = new QListWidget;
  for (const auto& s : libs) {
    auto* item = new QListWidgetItem(QStringLiteral("%1  ·  %2").arg(s.name, s.kind));
    item->setData(Qt::UserRole, s.path);
    item->setToolTip(s.path);
    list->addItem(item);
  }
  list->setCurrentRow(0);
  lay->addWidget(list);
  auto* btns = new QHBoxLayout;
  auto* ok = new QPushButton(QStringLiteral("加载"));
  auto* cancel = new QPushButton(QStringLiteral("取消"));
  btns->addStretch();
  btns->addWidget(ok);
  btns->addWidget(cancel);
  lay->addLayout(btns);
  QObject::connect(ok, &QPushButton::clicked, &dlg, &QDialog::accept);
  QObject::connect(cancel, &QPushButton::clicked, &dlg, &QDialog::reject);
  QObject::connect(list, &QListWidget::itemDoubleClicked, &dlg,
                   [&dlg](QListWidgetItem*) { dlg.accept(); });
  if (dlg.exec() != QDialog::Accepted) return;
  auto* item = list->currentItem();
  if (!item) return;
  const QString path = item->data(Qt::UserRole).toString();
  if (path.isEmpty()) return;
  if (!confirmDiscardOrSave()) return;
  QString err;
  if (!document_.loadFromFile(path, &err)) {
    QMessageBox::warning(this, QStringLiteral("工程库换型"), err);
    return;
  }
  applyDocumentToUi();
  markProjectClean();
  rememberRecentFile(path);
  logResult(QStringLiteral("工程库换型已加载 · %1").arg(document_.name()));
  showStatus(QStringLiteral("工程库换型 · %1").arg(document_.name()));
}


}  // namespace sieans_qt
