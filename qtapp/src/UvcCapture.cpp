#include "UvcCapture.hpp"

#include <QDir>
#include <QFileInfo>
#include <QImage>

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <unistd.h>
#include <linux/videodev2.h>

namespace sieans_qt {
namespace {

int xioctl(int fd, unsigned long req, void* arg) {
  int r;
  do {
    r = ioctl(fd, req, arg);
  } while (r == -1 && errno == EINTR);
  return r;
}

QString fourccName(unsigned f) {
  char b[5] = {char(f & 0xff), char((f >> 8) & 0xff), char((f >> 16) & 0xff),
               char((f >> 24) & 0xff), 0};
  return QString::fromLatin1(b);
}

}  // namespace

UvcCapture::UvcCapture() = default;

UvcCapture::~UvcCapture() { close(); }

QVector<UvcDeviceInfo> UvcCapture::enumerate() {
  QVector<UvcDeviceInfo> out;
  QDir dir(QStringLiteral("/dev"));
  const QStringList names =
      dir.entryList(QStringList() << QStringLiteral("video*"), QDir::System,
                    QDir::Name);
  int idx = 0;
  for (const QString& n : names) {
    const QString path = QStringLiteral("/dev/") + n;
    const int fd = ::open(path.toLocal8Bit().constData(), O_RDWR | O_NONBLOCK);
    if (fd < 0) continue;
    v4l2_capability cap{};
    bool ok = xioctl(fd, VIDIOC_QUERYCAP, &cap) == 0;
    const bool capture =
        ok && ((cap.device_caps ? cap.device_caps : cap.capabilities) &
               V4L2_CAP_VIDEO_CAPTURE);
    QString card = ok ? QString::fromLocal8Bit(reinterpret_cast<const char*>(cap.card))
                      : path;
    ::close(fd);
    if (!capture) continue;
    UvcDeviceInfo d;
    d.id = path;
    d.index = idx++;
    d.label = QStringLiteral("%1 (%2)").arg(card, path);
    out.push_back(d);
  }
  return out;
}

bool UvcCapture::open(const QString& deviceId) {
  close();
  QString path = deviceId;
  if (path.isEmpty()) {
    auto list = enumerate();
    if (list.isEmpty()) return false;
    path = list.front().id;
  } else if (!path.startsWith(QLatin1Char('/'))) {
    // numeric index or label containing /dev/videoN
    bool isNum = false;
    const int n = path.toInt(&isNum);
    auto list = enumerate();
    if (isNum && n >= 0 && n < list.size())
      path = list[n].id;
    else {
      for (const auto& d : list) {
        if (path.contains(d.id) || d.label.contains(path) || d.id.endsWith(path)) {
          path = d.id;
          break;
        }
      }
    }
  }
  fd_ = ::open(path.toLocal8Bit().constData(), O_RDWR | O_NONBLOCK);
  if (fd_ < 0) return false;

  v4l2_capability cap{};
  if (xioctl(fd_, VIDIOC_QUERYCAP, &cap) < 0) {
    close();
    return false;
  }

  // Prefer MJPEG then YUYV
  const unsigned candidates[] = {V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_YUYV,
                                 V4L2_PIX_FMT_YUV420};
  bool fmtOk = false;
  for (unsigned pf : candidates) {
    v4l2_format fmt{};
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = 640;
    fmt.fmt.pix.height = 480;
    fmt.fmt.pix.pixelformat = pf;
    fmt.fmt.pix.field = V4L2_FIELD_NONE;
    if (xioctl(fd_, VIDIOC_S_FMT, &fmt) == 0) {
      width_ = fmt.fmt.pix.width;
      height_ = fmt.fmt.pix.height;
      pixfmt_ = fmt.fmt.pix.pixelformat;
      fmtOk = true;
      break;
    }
  }
  if (!fmtOk) {
    close();
    return false;
  }

  if (!initMmap()) {
    close();
    return false;
  }

  v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  if (xioctl(fd_, VIDIOC_STREAMON, &type) < 0) {
    close();
    return false;
  }
  streaming_ = true;
  deviceId_ = path;
  return true;
}

bool UvcCapture::initMmap() {
  v4l2_requestbuffers req{};
  req.count = 4;
  req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  req.memory = V4L2_MEMORY_MMAP;
  if (xioctl(fd_, VIDIOC_REQBUFS, &req) < 0 || req.count < 2) return false;
  bufs_.resize(int(req.count));
  for (unsigned i = 0; i < req.count; ++i) {
    v4l2_buffer buf{};
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index = i;
    if (xioctl(fd_, VIDIOC_QUERYBUF, &buf) < 0) return false;
    bufs_[int(i)].length = buf.length;
    bufs_[int(i)].start =
        mmap(nullptr, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, buf.m.offset);
    if (bufs_[int(i)].start == MAP_FAILED) {
      bufs_[int(i)].start = nullptr;
      return false;
    }
    if (xioctl(fd_, VIDIOC_QBUF, &buf) < 0) return false;
  }
  return true;
}

void UvcCapture::freeMmap() {
  for (Buf& b : bufs_) {
    if (b.start && b.start != MAP_FAILED) munmap(b.start, b.length);
    b.start = nullptr;
    b.length = 0;
  }
  bufs_.clear();
}

void UvcCapture::close() {
  if (fd_ >= 0 && streaming_) {
    v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    xioctl(fd_, VIDIOC_STREAMOFF, &type);
    streaming_ = false;
  }
  freeMmap();
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
  deviceId_.clear();
}

QImage UvcCapture::decodeFrame(const void* data, size_t len) {
  if (!data || len == 0) return {};
  if (pixfmt_ == V4L2_PIX_FMT_MJPEG) {
    QImage img;
    if (img.loadFromData(reinterpret_cast<const uchar*>(data), int(len), "JPEG"))
      return img.convertToFormat(QImage::Format_RGB888);
    return {};
  }
  if (pixfmt_ == V4L2_PIX_FMT_YUYV) {
    const int w = int(width_);
    const int h = int(height_);
    if (len < size_t(w * h * 2)) return {};
    QImage img(w, h, QImage::Format_RGB888);
    const uchar* s = reinterpret_cast<const uchar*>(data);
    for (int y = 0; y < h; ++y) {
      uchar* dst = img.scanLine(y);
      for (int x = 0; x < w; x += 2) {
        const int i = (y * w + x) * 2;
        const int y0 = s[i + 0];
        const int u = s[i + 1];
        const int y1 = s[i + 2];
        const int v = s[i + 3];
        auto put = [&](int Y, int off) {
          const int c = Y - 16;
          const int d = u - 128;
          const int e = v - 128;
          const int r = (298 * c + 409 * e + 128) >> 8;
          const int g = (298 * c - 100 * d - 208 * e + 128) >> 8;
          const int b = (298 * c + 516 * d + 128) >> 8;
          dst[off + 0] = uchar(qBound(0, r, 255));
          dst[off + 1] = uchar(qBound(0, g, 255));
          dst[off + 2] = uchar(qBound(0, b, 255));
        };
        put(y0, x * 3);
        if (x + 1 < w) put(y1, (x + 1) * 3);
      }
    }
    return img;
  }
  Q_UNUSED(fourccName);
  return {};
}

QImage UvcCapture::grab(int timeoutMs) {
  if (fd_ < 0) return {};
  fd_set fds;
  FD_ZERO(&fds);
  FD_SET(fd_, &fds);
  timeval tv{};
  tv.tv_sec = timeoutMs / 1000;
  tv.tv_usec = (timeoutMs % 1000) * 1000;
  const int r = select(fd_ + 1, &fds, nullptr, nullptr, &tv);
  if (r <= 0) return {};

  v4l2_buffer buf{};
  buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  buf.memory = V4L2_MEMORY_MMAP;
  if (xioctl(fd_, VIDIOC_DQBUF, &buf) < 0) return {};
  QImage img;
  if (int(buf.index) < bufs_.size())
    img = decodeFrame(bufs_[int(buf.index)].start, buf.bytesused);
  xioctl(fd_, VIDIOC_QBUF, &buf);
  return img;
}

}  // namespace sieans_qt
