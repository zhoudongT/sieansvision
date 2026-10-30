#include "GenTLWorker.hpp"
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
  if (backend_ == QLatin1String("uvc") || backend_ == QLatin1String("usb")) {
    openUvc(deviceId);
  } else {
    openGentl(deviceId, fps, exposureUs);
  }
}

void GenTLWorker::openUvc(const QString& deviceId) {
  try {
    if (!uvc_) uvc_ = std::make_unique<UvcCapture>();
    if (!uvc_->open(deviceId)) {
      auto list = UvcCapture::enumerate();
      emit errorOccurred(
          list.isEmpty()
              ? QStringLiteral("未发现 UVC 设备（/dev/video*）")
              : QStringLiteral("打开 UVC 失败: %1").arg(deviceId));
      return;
    }
    deviceId_ = uvc_->deviceId();
    open_.store(true);
    emit opened(deviceId_);
    emit statusChanged(QStringLiteral("UVC 已打开 %1").arg(deviceId_));
  } catch (const std::exception& ex) {
    open_.store(false);
    emit errorOccurred(
        QStringLiteral("UVC 打开失败: %1").arg(QString::fromUtf8(ex.what())));
  }
}

void GenTLWorker::openGentl(const QString& deviceId, double fps,
                            double exposureUs) {
  try {
    if (!sieans::GenTLCapture::available()) {
      emit errorOccurred(QStringLiteral("GenTL 不可用（未链接 MvCameraControl）"));
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
        emit errorOccurred(QStringLiteral("未发现 GenTL 设备"));
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
    open_.store(false);
    emit errorOccurred(QStringLiteral("打开失败: %1").arg(QString::fromUtf8(ex.what())));
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
  if (previewing_.load()) return;
  stopPreview_.store(false);
  previewing_.store(true);
  emit statusChanged(QStringLiteral("连续预览中…"));
  previewLoop();
}

void GenTLWorker::stopPreview() {
  stopPreview_.store(true);
  previewing_.store(false);
  try {
    if (capture_ && capture_->is_grabbing()) capture_->stop();
  } catch (...) {
  }
}

void GenTLWorker::previewLoop() {
  if (backend_ == QLatin1String("uvc") || backend_ == QLatin1String("usb")) {
    while (!stopPreview_.load()) {
      if (!uvc_ || !uvc_->isOpen()) break;
      QImage img = uvc_->grab(500);
      if (!img.isNull()) {
        {
          QMutexLocker lock(&frameMutex_);
          latest_ = img;
        }
        emit frameReady(img, ++frameCounter_);
      }
      if (stopPreview_.load()) break;
    }
    previewing_.store(false);
    emit statusChanged(QStringLiteral("预览已停止"));
    return;
  }

  try {
    if (!capture_->is_grabbing()) capture_->start();
    while (!stopPreview_.load()) {
      try {
        auto frame = capture_->grab(500);
        QImage img = frameToImage(frame);
        if (!img.isNull()) {
          {
            QMutexLocker lock(&frameMutex_);
            latest_ = img;
          }
          emit frameReady(img, static_cast<qint64>(frame.frame_id));
        }
      } catch (const std::exception& ex) {
        if (stopPreview_.load()) break;
        const QString msg = QString::fromUtf8(ex.what());
        if (!msg.contains(QStringLiteral("timeout"), Qt::CaseInsensitive) &&
            !msg.contains(QStringLiteral("超时"))) {
          emit errorOccurred(QStringLiteral("预览: %1").arg(msg));
          QThread::msleep(50);
        }
      }
      if (stopPreview_.load()) break;
    }
  } catch (const std::exception& ex) {
    emit errorOccurred(QStringLiteral("预览循环异常: %1")
                           .arg(QString::fromUtf8(ex.what())));
  }
  previewing_.store(false);
  try {
    if (capture_ && capture_->is_grabbing()) capture_->stop();
  } catch (...) {
  }
  emit statusChanged(QStringLiteral("预览已停止"));
}

void GenTLWorker::grabOne() {
  try {
    if (!open_.load()) {
      emit errorOccurred(QStringLiteral("请先打开相机"));
      return;
    }
    if (backend_ == QLatin1String("uvc") || backend_ == QLatin1String("usb")) {
      if (!uvc_) return;
      QImage img = uvc_->grab(3000);
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
