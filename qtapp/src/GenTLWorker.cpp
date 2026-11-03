#include "GenTLWorker.hpp"
#include "SoftFrame.hpp"
#include <QFileInfo>
#include "UvcCapture.hpp"

#include <sieans/gentl_capture.hpp>

#include <QMetaObject>
#include <QThread>
#include <chrono>
#include <exception>

namespace sieans_qt {

GenTLWorker::GenTLWorker(QObject* parent) : QObject(parent) {}

GenTLWorker::~GenTLWorker() {
  stopPreview_.store(true);
  previewing_.store(false);
  if (previewTimer_) previewTimer_->stop();
  try {
    if (capture_) {
      if (capture_->is_grabbing()) capture_->stop();
      if (capture_->is_open()) capture_->close();
    }
  } catch (...) {
  }
  if (uvc_) uvc_->close();
}

QImage GenTLWorker::latestFrame() const {
  QMutexLocker lock(&frameMutex_);
  return latest_;
}

namespace {
QImage frameToImage(const sieans::GenTLFrame& frame) {
  if (frame.width <= 0 || frame.height <= 0 || frame.data.empty()) return {};
  if (frame.pixel_format == "Mono8") {
    return QImage(frame.data.data(), frame.width, frame.height, frame.stride,
                  QImage::Format_Grayscale8)
        .copy();
  }
  QImage img(frame.width, frame.height, QImage::Format_RGB888);
  for (int y = 0; y < frame.height; ++y) {
    const uint8_t* s = frame.data.data() + y * frame.stride;
    uint8_t* d = img.scanLine(y);
    for (int x = 0; x < frame.width; ++x) {
      d[x * 3 + 0] = s[x * 3 + 2];
      d[x * 3 + 1] = s[x * 3 + 1];
      d[x * 3 + 2] = s[x * 3 + 0];
    }
  }
  return img;
}
}  // namespace

void GenTLWorker::openDevice(const QString& deviceId, double fps,
                             double exposureUs) {
  openDeviceWithBackend(backend_.isEmpty() ? QStringLiteral("gentl") : backend_,
                        deviceId, fps, exposureUs);
}

void GenTLWorker::openDeviceWithBackend(const QString& backend,
                                        const QString& deviceId, double fps,
                                        double exposureUs) {
  stopPreview();
  // tear down other backend
  try {
    if (capture_ && capture_->is_open()) {
      if (capture_->is_grabbing()) capture_->stop();
      capture_->close();
    }
  } catch (...) {
  }
  if (uvc_) uvc_->close();
  open_.store(false);

  backend_ = backend.toLower();
  if (backend_.isEmpty()) backend_ = QStringLiteral("gentl");
  if (backend_ == QLatin1String("usb")) backend_ = QStringLiteral("uvc");
  if (backend_ == QLatin1String("sim") || backend_ == QLatin1String("synthetic"))
    backend_ = QStringLiteral("soft");
  fps_ = fps > 0 ? fps : 15.0;
  if (exposureUs > 0) exposureUs_.store(clampExposureUs(exposureUs));
  if (backend_ == QLatin1String("uvc")) {
    openUvc(deviceId);
  } else if (backend_ == QLatin1String("soft")) {
    openSoft(deviceId);
  } else {
    openGentl(deviceId, fps_, exposureUs_.load());
  }
}

void GenTLWorker::setSoftControls(double exposureUs, double gainDb) {
  exposureUs_.store(clampExposureUs(exposureUs));
  gainMilliDb_.store(int(clampGainDb(gainDb) * 1000.0));
  controlsDirty_.store(true);
}

QImage GenTLWorker::renderSoftFrame() {
  return makeSoftFrame(1280, 1024, softSeq_++, exposureUs(), gainDb());
}

QImage GenTLWorker::toneIfNeeded(const QImage& src) {
  if (src.isNull()) return {};
  if (backend_ != QLatin1String("uvc") && backend_ != QLatin1String("soft")) return src;
  return applySoftTone(src, exposureUs(), gainDb(), int(frameCounter_), true);
}

void GenTLWorker::applyDirtyHardware() {
  if (!controlsDirty_.exchange(false)) return;
  if (backend_ == QLatin1String("uvc") && uvc_ && uvc_->isOpen()) {
    uvc_->applyHardwareControls(exposureUs(), gainDb());
  } else if (backend_ == QLatin1String("gentl") && capture_ && capture_->is_open()) {
    try {
      capture_->set_exposure_us(exposureUs());
    } catch (...) {
    }
  }
}

void GenTLWorker::openSoft(const QString& deviceId) {
  deviceId_ = deviceId.isEmpty() ? QStringLiteral("soft:0") : deviceId;
  open_.store(true);
  QImage img = renderSoftFrame();
  {
    QMutexLocker lock(&frameMutex_);
    latest_ = img;
  }
  emit opened(deviceId_);
  emit frameReady(img, ++frameCounter_);
  const QString qrPath = softQrSampleLoadedPath();
  const QByteArray sampleEnv = qgetenv("SIEANS_QT_SAMPLE_QR");
  QString qrNote;
  if (!qrPath.isEmpty())
    qrNote = QStringLiteral(" · QR:%1").arg(QFileInfo(qrPath).fileName());
  else if (!sampleEnv.isEmpty())
    qrNote = QStringLiteral(" · SAMPLE_QR");
  emit statusChanged(QStringLiteral("Soft 仿真相机已打开 %1 · %2×%3 · exp=%4µs gain=%5dB%6")
                         .arg(deviceId_)
                         .arg(img.width())
                         .arg(img.height())
                         .arg(exposureUs())
                         .arg(gainDb(), 0, 'f', 1)
                         .arg(qrNote));
}

void GenTLWorker::openUvc(const QString& deviceId) {
  try {
    if (!uvc_) uvc_ = std::make_unique<UvcCapture>();
    if (!uvc_->open(deviceId)) {
      auto list = UvcCapture::enumerate();
      const QString why =
          list.isEmpty()
              ? QStringLiteral("未发现 UVC 设备（/dev/video*）")
              : QStringLiteral("打开 UVC 失败: %1").arg(deviceId);
      emit statusChanged(QStringLiteral("%1 · 回退 Soft 仿真").arg(why));
      backend_ = QStringLiteral("soft");
      openSoft(QStringLiteral("soft:uvc-fallback"));
      return;
    }
    deviceId_ = uvc_->deviceId();
    open_.store(true);
    emit opened(deviceId_);
    emit statusChanged(QStringLiteral("UVC 已打开 %1").arg(deviceId_));
  } catch (const std::exception& ex) {
    emit statusChanged(
        QStringLiteral("UVC 打开失败: %1 · 回退 Soft 仿真")
            .arg(QString::fromUtf8(ex.what())));
    backend_ = QStringLiteral("soft");
    openSoft(QStringLiteral("soft:uvc-fallback"));
  }
}

void GenTLWorker::openGentl(const QString& deviceId, double fps,
                            double exposureUs) {
  try {
    if (!sieans::GenTLCapture::available()) {
      emit statusChanged(QStringLiteral("GenTL 不可用 · 回退 Soft 仿真"));
      backend_ = QStringLiteral("soft");
      openSoft(QStringLiteral("soft:gentl-unavailable"));
      return;
    }
    if (!capture_) capture_ = std::make_unique<sieans::GenTLCapture>();
    if (capture_->is_open()) {
      if (capture_->is_grabbing()) capture_->stop();
      capture_->close();
    }
    QString id = deviceId;
    if (id.isEmpty()) {
      auto devices = sieans::GenTLCapture::enumerate();
      if (devices.empty()) {
        emit statusChanged(QStringLiteral("未发现 GenTL 设备 · 回退 Soft 仿真"));
        backend_ = QStringLiteral("soft");
        openSoft(QStringLiteral("soft:gentl-empty"));
        return;
      }
      id = QString::fromStdString(devices.front().id);
    }
    try {
      capture_->open(id.toStdString());
    } catch (const std::exception&) {
      auto devices = sieans::GenTLCapture::enumerate();
      std::string resolved;
      for (const auto& d : devices) {
        const QString label =
            QStringLiteral("%1 %2 (%3)")
                .arg(QString::fromStdString(d.vendor),
                     QString::fromStdString(d.model),
                     QString::fromStdString(d.serial));
        if (id.contains(QString::fromStdString(d.serial)) ||
            id.contains(QString::fromStdString(d.model)) ||
            id == QString::fromStdString(d.id) || id == label) {
          resolved = d.id;
          break;
        }
      }
      if (resolved.empty() && !devices.empty()) resolved = devices.front().id;
      if (resolved.empty()) throw;
      capture_->open(resolved);
      id = QString::fromStdString(resolved);
    }
    fps_ = fps > 0 ? fps : 15.0;
    capture_->configure_freerun(fps_, 8);
    if (exposureUs > 0) {
      try {
        capture_->set_exposure_us(exposureUs);
      } catch (...) {
      }
    }
    deviceId_ = id;
    open_.store(true);
    emit opened(id);
    emit statusChanged(QStringLiteral("GenTL 已打开 %1").arg(id));
  } catch (const std::exception& ex) {
    emit statusChanged(
        QStringLiteral("GenTL 打开失败: %1 · 回退 Soft 仿真")
            .arg(QString::fromUtf8(ex.what())));
    backend_ = QStringLiteral("soft");
    openSoft(QStringLiteral("soft:gentl-fallback"));
  }
}

void GenTLWorker::closeDevice() {
  stopPreview();
  try {
    if (capture_ && capture_->is_open()) capture_->close();
  } catch (const std::exception& ex) {
    emit errorOccurred(QStringLiteral("关闭失败: %1").arg(QString::fromUtf8(ex.what())));
  }
  if (uvc_) uvc_->close();
  open_.store(false);
  emit closed();
  emit statusChanged(QStringLiteral("相机已关闭"));
}

void GenTLWorker::startPreview() {
  if (!open_.load()) {
    emit errorOccurred(QStringLiteral("请先打开相机"));
    return;
  }
  if (previewing_.load() && previewTimer_ && previewTimer_->isActive()) return;
  stopPreview_.store(false);
  previewing_.store(true);
  if (!previewTimer_) {
    previewTimer_ = new QTimer(this);
    connect(previewTimer_, &QTimer::timeout, this, &GenTLWorker::grabPreviewFrame);
  }
  const bool paced = backend_ == QLatin1String("soft") ||
                     backend_ == QLatin1String("uvc") ||
                     backend_ == QLatin1String("usb");
  const int period =
      paced ? qBound(30, int(1000.0 / (fps_ > 0 ? fps_ : 15.0)), 1000) : 1;
  previewTimer_->start(period);
  if (backend_ == QLatin1String("soft")) {
    QImage soft;
    {
      QMutexLocker lock(&frameMutex_);
      soft = latest_;
    }
    emit statusChanged(QStringLiteral("连续预览中… Soft %1×%2 @%3fps")
                           .arg(soft.isNull() ? 1280 : soft.width())
                           .arg(soft.isNull() ? 1024 : soft.height())
                           .arg(fps_, 0, 'f', 1));
  } else {
    emit statusChanged(QStringLiteral("连续预览中…"));
  }
  grabPreviewFrame();
}

void GenTLWorker::requestStop() { stopPreview_.store(true); }

void GenTLWorker::stopPreview() {
  stopPreview_.store(true);
  if (QThread::currentThread() == thread()) shutdownPreview();
}

void GenTLWorker::shutdownPreview() {
  if (previewTimer_) previewTimer_->stop();
  const bool was = previewing_.exchange(false);
  try {
    if (capture_ && capture_->is_grabbing()) capture_->stop();
  } catch (...) {
  }
  if (was) emit statusChanged(QStringLiteral("预览已停止"));
}

void GenTLWorker::grabPreviewFrame() {
  if (stopPreview_.load() || !open_.load()) {
    shutdownPreview();
    return;
  }
  try {
    QImage img;
    qint64 fid = ++frameCounter_;
    if (backend_ == QLatin1String("soft")) {
      img = renderSoftFrame();
    } else if (backend_ == QLatin1String("uvc") || backend_ == QLatin1String("usb")) {
      if (!uvc_ || !uvc_->isOpen()) {
        emit errorOccurred(QStringLiteral("UVC 已断开"));
        shutdownPreview();
        return;
      }
      applyDirtyHardware();
      img = toneIfNeeded(uvc_->grab(500));
    } else {
      if (!capture_) {
        shutdownPreview();
        return;
      }
      applyDirtyHardware();
      if (!capture_->is_grabbing()) capture_->start();
      auto frame = capture_->grab(500);
      img = frameToImage(frame);
      fid = static_cast<qint64>(frame.frame_id);
    }
    if (stopPreview_.load()) {
      shutdownPreview();
      return;
    }
    if (!img.isNull()) {
      {
        QMutexLocker lock(&frameMutex_);
        latest_ = img;
      }
      emit frameReady(img, fid);
    }
  } catch (const std::exception& ex) {
    if (stopPreview_.load()) {
      shutdownPreview();
      return;
    }
    const QString msg = QString::fromUtf8(ex.what());
    if (!msg.contains(QStringLiteral("timeout"), Qt::CaseInsensitive) &&
        !msg.contains(QStringLiteral("超时"))) {
      emit errorOccurred(QStringLiteral("预览: %1").arg(msg));
    }
  }
}

void GenTLWorker::grabOne() {
  try {
    if (!open_.load()) {
      emit errorOccurred(
          backend_ == QLatin1String("soft")
              ? QStringLiteral("Soft 未打开 — 请先 openDevice / AUTO_SOFT")
              : QStringLiteral("请先打开相机"));
      return;
    }
    if (backend_ == QLatin1String("soft")) {
      applyDirtyHardware();
      QImage img = renderSoftFrame();
      {
        QMutexLocker lock(&frameMutex_);
        latest_ = img;
      }
      emit frameReady(img, ++frameCounter_);
      return;
    }
    if (backend_ == QLatin1String("uvc") || backend_ == QLatin1String("usb")) {
      if (!uvc_) return;
      applyDirtyHardware();
      QImage img = toneIfNeeded(uvc_->grab(3000));
      if (img.isNull()) {
        emit errorOccurred(QStringLiteral("UVC 采到空帧"));
        return;
      }
      {
        QMutexLocker lock(&frameMutex_);
        latest_ = img;
      }
      emit frameReady(img, ++frameCounter_);
      return;
    }
    if (!capture_) return;
    const bool wasPreview = previewing_.load();
    if (!wasPreview) {
      if (!capture_->is_grabbing()) capture_->start();
    }
    auto frame = capture_->grab(3000);
    if (!wasPreview) {
      try {
        capture_->stop();
      } catch (...) {
      }
    }
    QImage img = frameToImage(frame);
    if (img.isNull()) {
      emit errorOccurred(QStringLiteral("采到空帧"));
      return;
    }
    {
      QMutexLocker lock(&frameMutex_);
      latest_ = img;
    }
    emit frameReady(img, static_cast<qint64>(frame.frame_id));
  } catch (const std::exception& ex) {
    emit errorOccurred(QStringLiteral("采一帧失败: %1")
                           .arg(QString::fromUtf8(ex.what())));
  }
}

}  // namespace sieans_qt
