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

/** Off-UI GenTL continuous grab; drops stale frames; emits latest QImage. */
class GenTLWorker : public QObject {
  Q_OBJECT
 public:
  explicit GenTLWorker(QObject* parent = nullptr);
  ~GenTLWorker() override;

 public slots:
  void openDevice(const QString& deviceId, double fps, double exposureUs);
  void closeDevice();
  void startPreview();
  void stopPreview();
  void grabOne();  // single frame into latest_, emit frameReady

 signals:
  void opened(const QString& deviceId);
  void closed();
  void frameReady(const QImage& image, qint64 frameId);
  void errorOccurred(const QString& message);
  void statusChanged(const QString& message);

 public:
  bool isOpen() const { return open_.load(); }
  bool isPreviewing() const { return previewing_.load(); }
  QImage latestFrame() const;

 private:
  void previewLoop();

  std::unique_ptr<sieans::GenTLCapture> capture_;
  mutable QMutex frameMutex_;
  QImage latest_;
  std::atomic<bool> open_{false};
  std::atomic<bool> previewing_{false};
  std::atomic<bool> stopPreview_{false};
  QString deviceId_;
  double fps_ = 15.0;
};

}  // namespace sieans_qt
