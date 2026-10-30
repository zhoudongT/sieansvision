#pragma once

#include <QImage>
#include <QMutex>
#include <QObject>
#include <QString>
#include <atomic>
#include <memory>

namespace sieans {
class GenTLCapture;
}

namespace sieans_qt {
class UvcCapture;

/** Off-UI continuous grab (GenTL or UVC); drops stale frames; emits latest QImage. */
class GenTLWorker : public QObject {
  Q_OBJECT
 public:
  explicit GenTLWorker(QObject* parent = nullptr);
  ~GenTLWorker() override;

 public slots:
  /** backend: "gentl" | "uvc" (default gentl). */
  void openDevice(const QString& deviceId, double fps, double exposureUs);
  void openDeviceWithBackend(const QString& backend, const QString& deviceId,
                             double fps, double exposureUs);
  void closeDevice();
  void startPreview();
  void stopPreview();
  void grabOne();

 signals:
  void opened(const QString& deviceId);
  void closed();
  void frameReady(const QImage& image, qint64 frameId);
  void errorOccurred(const QString& message);
  void statusChanged(const QString& message);

 public:
  bool isOpen() const { return open_.load(); }
  bool isPreviewing() const { return previewing_.load(); }
  QString backend() const { return backend_; }
  QImage latestFrame() const;

 private:
  void previewLoop();
  void openGentl(const QString& deviceId, double fps, double exposureUs);
  void openUvc(const QString& deviceId);

  std::unique_ptr<sieans::GenTLCapture> capture_;
  std::unique_ptr<UvcCapture> uvc_;
  QString backend_ = QStringLiteral("gentl");
  mutable QMutex frameMutex_;
  QImage latest_;
  std::atomic<bool> open_{false};
  std::atomic<bool> previewing_{false};
  std::atomic<bool> stopPreview_{false};
  QString deviceId_;
  double fps_ = 15.0;
  qint64 frameCounter_ = 0;
};

}  // namespace sieans_qt
