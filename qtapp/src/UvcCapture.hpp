#pragma once

#include <QImage>
#include <QString>
#include <QStringList>
#include <QVector>

namespace sieans_qt {

struct UvcDeviceInfo {
  QString id;     // /dev/videoN
  QString label;  // card name or path
  int index = 0;
};

/** Minimal V4L2 UVC grabber (YUYV / MJPEG). Graceful empty enum if none. */
class UvcCapture {
 public:
  UvcCapture();
  ~UvcCapture();
  UvcCapture(const UvcCapture&) = delete;
  UvcCapture& operator=(const UvcCapture&) = delete;

  static QVector<UvcDeviceInfo> enumerate();

  bool open(const QString& deviceId);
  void close();
  bool isOpen() const { return fd_ >= 0; }

  /** Grab one frame; empty on failure/timeout. */
  QImage grab(int timeoutMs = 500);

  QString deviceId() const { return deviceId_; }

 private:
  bool initMmap();
  void freeMmap();
  QImage decodeFrame(const void* data, size_t len);

  int fd_ = -1;
  QString deviceId_;
  unsigned width_ = 640;
  unsigned height_ = 480;
  unsigned pixfmt_ = 0;
  struct Buf {
    void* start = nullptr;
    size_t length = 0;
  };
  QVector<Buf> bufs_;
  bool streaming_ = false;
};

}  // namespace sieans_qt
