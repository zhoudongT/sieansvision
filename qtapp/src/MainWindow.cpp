#include "MainWindow.hpp"

#include <sieans/barcode.hpp>
#include <sieans/gentl_capture.hpp>

#include <QAction>
#include <QMenu>
#include <QMenuBar>
#include <QKeySequence>
#include <QApplication>
#include <QDateTime>
#include <QDockWidget>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QMessageBox>
#include <QSplitter>
#include <QStatusBar>
#include <QToolBar>
#include <QTreeWidgetItem>
#include <QVBoxLayout>
#include <QTimer>
#include <QDir>
#include <QCoreApplication>
#include <QFileInfo>

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

QString samplePathCandidates() {
  const QStringList cands = {
      QCoreApplication::applicationDirPath() + QStringLiteral("/resources/sample-qr.png"),
      QDir(QCoreApplication::applicationDirPath()).absoluteFilePath(
          QStringLiteral("../resources/sample-qr.png")),
      QStringLiteral("/home/allen/文档/sieansvision/qtapp/resources/sample-qr.png"),
      QStringLiteral("/home/allen/文档/sieansvision/artifacts/qr-t238-grab0.png"),
  };
  for (const auto& p : cands) {
    if (QFileInfo::exists(p)) return p;
  }
  return {};
}

}  // namespace

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle(QStringLiteral("SIEANS Vision — Qt 框架 (C++ core)"));
  resize(1400, 860);
  buildUi();
  buildMenus();
  buildToolbar();
  showStatus(QStringLiteral("就绪 · native %1 · GenTL %2")
                 .arg(QString::fromStdString(sieans::native_version()))
                 .arg(sieans::GenTLCapture::available() ? QStringLiteral("可用")
                                                        : QStringLiteral("桩/不可用")));

  const QByteArray autoSample = qgetenv("SIEANS_QT_AUTO_SAMPLE");
  if (autoSample == "1" || autoSample.compare("true", Qt::CaseInsensitive) == 0) {
    QTimer::singleShot(100, this, &MainWindow::onLoadSample);
  }
  if (qgetenv("SIEANS_QT_AUTO_ENUM") == "1") {
    QTimer::singleShot(400, this, &MainWindow::onEnumerateGenTL);
  }
}

MainWindow::~MainWindow() {
  if (gentl_ && gentl_->is_open()) {
    try {
      if (gentl_->is_grabbing()) gentl_->stop();
      gentl_->close();
    } catch (...) {
    }
  }
}

void MainWindow::buildUi() {
  auto* central = new QWidget(this);
  auto* layout = new QHBoxLayout(central);
  layout->setContentsMargins(4, 4, 4, 4);
  layout->setSpacing(4);

  auto* splitter = new QSplitter(Qt::Horizontal, central);

  // Left: flow / canvas placeholder
  flow_tree_ = new QTreeWidget;
  flow_tree_->setHeaderLabels({QStringLiteral("流程 / 画布 (占位)")});
  flow_tree_->setMinimumWidth(180);
  flow_tree_->setMaximumWidth(320);
  auto* root = new QTreeWidgetItem(flow_tree_, {QStringLiteral("方案 (未加载)")});
  new QTreeWidgetItem(root, {QStringLiteral("① 图像源 — stub")});
  new QTreeWidgetItem(root, {QStringLiteral("② QR 解码 — C++ sieans_algo")});
  new QTreeWidgetItem(root, {QStringLiteral("③ 结果输出 — stub")});
  flow_tree_->expandAll();
  splitter->addWidget(flow_tree_);

  // Center: image view
  image_view_ = new ImageView;
  splitter->addWidget(image_view_);

  // Right: results
  result_panel_ = new QPlainTextEdit;
  result_panel_->setReadOnly(true);
  result_panel_->setPlaceholderText(
      QStringLiteral("结果面板 — 解码文本 / GenTL 日志会显示在这里"));
  result_panel_->setMinimumWidth(260);
  splitter->addWidget(result_panel_);

  splitter->setStretchFactor(0, 0);
  splitter->setStretchFactor(1, 1);
  splitter->setStretchFactor(2, 0);
  splitter->setSizes({220, 900, 280});

  layout->addWidget(splitter);
  setCentralWidget(central);

  status_backend_ = new QLabel(this);
  statusBar()->addPermanentWidget(status_backend_);
  status_backend_->setText(
      QStringLiteral("sieans_algo %1")
          .arg(QString::fromStdString(sieans::native_version())));
}

void MainWindow::buildMenus() {
  auto* fileMenu = menuBar()->addMenu(QStringLiteral("文件(&F)"));
  fileMenu->addAction(QStringLiteral("打开图像…"), this, &MainWindow::onOpenImage,
                      QKeySequence::Open);
  fileMenu->addAction(QStringLiteral("加载示例 QR"), this, &MainWindow::onLoadSample);
  fileMenu->addSeparator();
  fileMenu->addAction(QStringLiteral("退出"), qApp, &QApplication::quit, QKeySequence::Quit);

  auto* runMenu = menuBar()->addMenu(QStringLiteral("运行(&R)"));
  runMenu->addAction(QStringLiteral("C++ QR 解码"), this, &MainWindow::onDecodeQr,
                     QKeySequence(Qt::Key_F5));

  auto* camMenu = menuBar()->addMenu(QStringLiteral("相机(&C)"));
  camMenu->addAction(QStringLiteral("枚举 GenTL"), this, &MainWindow::onEnumerateGenTL);
  camMenu->addAction(QStringLiteral("采一帧"), this, &MainWindow::onGrabOneFrame);

  auto* helpMenu = menuBar()->addMenu(QStringLiteral("帮助(&H)"));
  helpMenu->addAction(QStringLiteral("关于"), this, &MainWindow::onAbout);
}

void MainWindow::buildToolbar() {
  auto* tb = addToolBar(QStringLiteral("主工具栏"));
  tb->setMovable(false);
  tb->addAction(QStringLiteral("打开图像"), this, &MainWindow::onOpenImage);
  tb->addAction(QStringLiteral("示例 QR"), this, &MainWindow::onLoadSample);
  tb->addSeparator();
  tb->addAction(QStringLiteral("▶ C++ 解码"), this, &MainWindow::onDecodeQr);
  tb->addSeparator();
  tb->addAction(QStringLiteral("枚举 GenTL"), this, &MainWindow::onEnumerateGenTL);
  tb->addAction(QStringLiteral("采一帧"), this, &MainWindow::onGrabOneFrame);
}

void MainWindow::logResult(const QString& line) {
  const QString stamp =
      QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss.zzz"));
  result_panel_->appendPlainText(QStringLiteral("[%1] %2").arg(stamp, line));
}

void MainWindow::showStatus(const QString& msg, int timeout_ms) {
  statusBar()->showMessage(msg, timeout_ms);
}

bool MainWindow::loadImagePath(const QString& path) {
  QImage img(path);
  if (img.isNull()) {
    QMessageBox::warning(this, QStringLiteral("打开失败"),
                         QStringLiteral("无法读取图像:\n%1").arg(path));
    return false;
  }
  current_path_ = path;
  image_view_->setImage(img);
  logResult(QStringLiteral("已加载 %1 (%2×%3)")
                .arg(QFileInfo(path).fileName())
                .arg(img.width())
                .arg(img.height()));
  showStatus(QStringLiteral("已加载 %1").arg(path));
  return true;
}

void MainWindow::onOpenImage() {
  const QString path = QFileDialog::getOpenFileName(
      this, QStringLiteral("打开图像"),
      QStringLiteral("/home/allen/文档/sieansvision/artifacts"),
      QStringLiteral("Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"));
  if (path.isEmpty()) return;
  if (loadImagePath(path)) runDecodeOnCurrent();
}

void MainWindow::onLoadSample() {
  const QString path = samplePathCandidates();
  if (path.isEmpty()) {
    QMessageBox::information(
        this, QStringLiteral("无示例"),
        QStringLiteral("未找到 sample-qr.png，请用「打开图像」选择文件。"));
    return;
  }
  if (loadImagePath(path)) runDecodeOnCurrent();
}

void MainWindow::onDecodeQr() { runDecodeOnCurrent(); }

void MainWindow::runDecodeOnCurrent() {
  QImage src = image_view_->currentImage();
  if (src.isNull()) {
    showStatus(QStringLiteral("请先加载图像"));
    return;
  }
  QImage rgb = toRgb888(src);
  if (rgb.isNull()) return;

  // QImage may not be tightly packed; use bytesPerLine as stride.
  sieans::BarcodeOptions opts;
  opts.formats = "QRCode";
  opts.max_codes = 16;
  opts.try_rotate = true;
  opts.try_downscale = true;

  const auto t0 = std::chrono::steady_clock::now();
  std::vector<sieans::BarcodeHit> hits;
  try {
    hits = sieans::decode_barcodes(
        rgb.constBits(), rgb.width(), rgb.height(), rgb.bytesPerLine(),
        sieans::PixelFormat::RGB24, opts);
  } catch (const std::exception& ex) {
    logResult(QStringLiteral("解码异常: %1").arg(QString::fromUtf8(ex.what())));
    return;
  }
  const auto ms = std::chrono::duration<double, std::milli>(
                      std::chrono::steady_clock::now() - t0)
                      .count();

  QVector<OverlayHit> overlays;
  logResult(QStringLiteral("—— C++ 解码 %1 个 · %2 ms ——")
                .arg(hits.size())
                .arg(ms, 0, 'f', 1));
  int i = 0;
  for (const auto& h : hits) {
    OverlayHit o;
    o.text = QString::fromStdString(h.text);
    o.format = QString::fromStdString(h.format);
    for (const auto& p : h.polygon) {
      o.polygon << QPointF(p.x, p.y);
    }
    overlays.push_back(o);
    logResult(QStringLiteral("  [%1] %2 | %3")
                  .arg(++i)
                  .arg(o.format)
                  .arg(o.text.left(80)));
  }
  if (hits.empty()) {
    logResult(QStringLiteral("  (无码)"));
  }
  image_view_->setOverlays(overlays);
  showStatus(QStringLiteral("解码完成: %1 个 / %2 ms")
                 .arg(hits.size())
                 .arg(ms, 0, 'f', 1));
}

void MainWindow::onEnumerateGenTL() {
  if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral(
        "GenTL: sieans_algo 未链接 MvCameraControl（需 /opt/MVS）。仅为桩。"));
    showStatus(QStringLiteral("GenTL 不可用"));
    return;
  }
  try {
    auto devices = sieans::GenTLCapture::enumerate();
    logResult(QStringLiteral("—— GenTL 枚举 %1 台 ——").arg(devices.size()));
    for (const auto& d : devices) {
      logResult(QStringLiteral("  %1 | %2 | %3 | %4")
                    .arg(QString::fromStdString(d.id))
                    .arg(QString::fromStdString(d.model))
                    .arg(QString::fromStdString(d.serial))
                    .arg(QString::fromStdString(d.cti_path)));
      if (last_gentl_device_id_.isEmpty()) {
        last_gentl_device_id_ = QString::fromStdString(d.id);
      }
    }
    if (devices.empty()) {
      logResult(QStringLiteral("  (未发现设备 — 检查 USB/网口与占用)"));
    }
    showStatus(QStringLiteral("枚举完成: %1 台").arg(devices.size()));
  } catch (const std::exception& ex) {
    logResult(QStringLiteral("枚举失败: %1").arg(QString::fromUtf8(ex.what())));
  }
}

void MainWindow::onGrabOneFrame() {
  if (!sieans::GenTLCapture::available()) {
    logResult(QStringLiteral("采一帧: GenTL 不可用（桩）。请先安装 /opt/MVS 并重建。"));
    return;
  }
  try {
    if (last_gentl_device_id_.isEmpty()) {
      auto devices = sieans::GenTLCapture::enumerate();
      if (devices.empty()) {
        logResult(QStringLiteral("采一帧: 无设备"));
        return;
      }
      last_gentl_device_id_ = QString::fromStdString(devices.front().id);
    }

    if (!gentl_) gentl_ = std::make_unique<sieans::GenTLCapture>();
    if (gentl_->is_open()) {
      if (gentl_->is_grabbing()) gentl_->stop();
      gentl_->close();
    }

    logResult(QStringLiteral("打开 %1 …").arg(last_gentl_device_id_));
    gentl_->open(last_gentl_device_id_.toStdString());
    gentl_->configure_freerun(5.0, 8);
    gentl_->start();
    auto frame = gentl_->grab(3000);
    gentl_->stop();
    gentl_->close();

    QImage img;
    if (frame.pixel_format == "Mono8") {
      img = QImage(frame.data.data(), frame.width, frame.height, frame.stride,
                   QImage::Format_Grayscale8)
                .copy();
    } else {
      // BGR8 → RGB for Qt
      img = QImage(frame.width, frame.height, QImage::Format_RGB888);
      for (int y = 0; y < frame.height; ++y) {
        const uint8_t* src = frame.data.data() + y * frame.stride;
        uint8_t* dst = img.scanLine(y);
        for (int x = 0; x < frame.width; ++x) {
          dst[x * 3 + 0] = src[x * 3 + 2];
          dst[x * 3 + 1] = src[x * 3 + 1];
          dst[x * 3 + 2] = src[x * 3 + 0];
        }
      }
    }
    current_path_.clear();
    image_view_->setImage(img);
    logResult(QStringLiteral("采到一帧 %1×%2 %3 id=%4")
                  .arg(frame.width)
                  .arg(frame.height)
                  .arg(QString::fromStdString(frame.pixel_format))
                  .arg(frame.frame_id));
    runDecodeOnCurrent();
  } catch (const std::exception& ex) {
    logResult(QStringLiteral("采一帧失败: %1").arg(QString::fromUtf8(ex.what())));
    showStatus(QStringLiteral("采一帧失败"));
    try {
      if (gentl_ && gentl_->is_open()) {
        if (gentl_->is_grabbing()) gentl_->stop();
        gentl_->close();
      }
    } catch (...) {
    }
  }
}

void MainWindow::onAbout() {
  QMessageBox::about(
      this, QStringLiteral("关于 SIEANS Vision Qt"),
      QStringLiteral(
          "<b>SIEANS Vision Qt 框架</b><br/>"
          "下层 C++ <code>sieans_algo</code>（zxing + GenTL），上层 Qt6 Widgets。<br/>"
          "本波仅骨架：主窗布局、解码打通、GenTL 枚举/采一帧。<br/>"
          "native: %1<br/>"
          "GenTL: %2")
          .arg(QString::fromStdString(sieans::native_version()))
          .arg(sieans::GenTLCapture::available() ? QStringLiteral("built")
                                                 : QStringLiteral("stub")));
}

}  // namespace sieans_qt
