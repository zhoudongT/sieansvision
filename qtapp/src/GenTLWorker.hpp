#pragma once

#include <QImage>
#include <QMutex>
#include <QObject>
#include <QString>
#include <QTimer>
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
  /** backend: "gentl" | "uvc" | "soft" (default gentl). */
  void openDevice(const QString& deviceId, double fps, double exposureUs);
  void openDeviceWithBackend(const QString& backend, const QString& deviceId,
                             double fps, double exposureUs);
  void closeDevice();
  void startPreview();
  void stopPreview();
  void grabOne();
  /** Thread-safe. Sets the stop flag; the worker applies it between frames. */
  void requestStop();
  /** Thread-safe. Preview reads these every frame; hardware apply is deferred. */
  void setSoftControls(double exposureUs, double gainDb);

 signals:
  void opened(const QString& deviceId);
  void closed();
  void frameReady(const QImage& image, qint64 frameId);
  void errorOccurred(const QString& message);
  void statusChanged(const QString& message);

 private slots:
  void grabPreviewFrame();

 public:
  bool isOpen() const { return open_.load(); }
  bool isPreviewing() const { return previewing_.load(); }
  QString backend() const { return backend_; }
  QImage latestFrame() const;

 private:
  void openGentl(const QString& deviceId, double fps, double exposureUs);
  void openUvc(const QString& deviceId);
  void openSoft(const QString& deviceId);
  void shutdownPreview();
  QImage renderSoftFrame();
  QImage toneIfNeeded(const QImage& src);
  void applyDirtyHardware();
  int exposureUs() const { return exposureUs_.load(); }
  double gainDb() const { return gainMilliDb_.load() / 1000.0; }

  std::unique_ptr<sieans::GenTLCapture> capture_;
  std::unique_ptr<UvcCapture> uvc_;
  QString backend_ = QStringLiteral("gentl");
  mutable QMutex frameMutex_;
  QImage latest_;
  std::atomic<bool> open_{false};
  std::atomic<bool> previewing_{false};
  std::atomic<bool> stopPreview_{false};
  std::atomic<int> exposureUs_{10000};
  std::atomic<int> gainMilliDb_{0};
  std::atomic<bool> controlsDirty_{false};
  QTimer* previewTimer_ = nullptr;
  QString deviceId_;
  double fps_ = 15.0;
  qint64 frameCounter_ = 0;
  int softSeq_ = 0;
};

}  // namespace sieans_qt
