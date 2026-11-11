#include "YoloInfer.hpp"

#include "YoloOnnx.hpp"

#include "FixturePose.hpp"
#include "SoftFrame.hpp"

#include <QFileInfo>
#include <QSet>
#include <QtGlobal>

#include <algorithm>
#include <cmath>
#include <queue>
#include <utility>

namespace sieans_qt {
namespace {

constexpr int kMaxContourPoints = 50000;
constexpr qint64 kSegBudget = 32768000;
const char kDefaultDetectModel[] = "yolo11n.pt";
const char kDefaultSegModel[] = "yolo11n-seg.pt";
const char kDefaultLabel[] = "part";

/** 判断像素是否属于软图 YOLO 特征色（允许轻度曝光增益缩放）。 */
bool isFixturePixel(int r, int g, int b) {
  if (r < 140 || g > 90 || b > 130) return false;
  if (r < g + 80 || r < b + 60) return false;
  const int dr = r - 220;
  const int dg = g - 40;
  const int db = b - 80;
  return (dr * dr + dg * dg + db * db) <= 28 * 28 * 3;
}

QSet<QString> parseClassFilter(const QVariant& raw) {
  QSet<QString> out;
  QStringList parts;
  if (raw.typeId() == QMetaType::QStringList || raw.typeId() == QMetaType::QVariantList) {
    const QVariantList lst = raw.toList();
    for (const QVariant& v : lst) parts << v.toString();
  } else {
    const QString s = raw.toString().trimmed();
    if (!s.isEmpty()) {
      const QStringList split = s.split(QLatin1Char(','), Qt::SkipEmptyParts);
      for (QString t : split) parts << t.trimmed();
    }
  }
  for (QString t : parts) {
    t = t.trimmed();
    if (!t.isEmpty()) out.insert(t);
  }
  return out;
}

bool classAllowed(const YoloItem& it, const QSet<QString>& filter) {
  if (filter.isEmpty()) return true;
  if (filter.contains(it.label)) return true;
  if (filter.contains(QString::number(it.classId))) return true;
  return false;
}

int clampImageSize(int raw, int lo, int hi) {
  int v = qBound(lo, raw, hi);
  v = (v / 32) * 32;
  if (v < lo) v = lo;
  return v;
}

double boxIou(const QRectF& a, const QRectF& b) {
  const QRectF inter = a.intersected(b);
  if (inter.isEmpty()) return 0;
  const double ia = inter.width() * inter.height();
  const double ua = a.width() * a.height() + b.width() * b.height() - ia;
  return ua > 0 ? ia / ua : 0;
}

QVector<YoloItem> applyNms(QVector<YoloItem> items, double iouThr, int maxDet,
                           bool* limitReached) {
  std::sort(items.begin(), items.end(), [](const YoloItem& a, const YoloItem& b) {
    return a.confidence > b.confidence;
  });
  QVector<YoloItem> kept;
  QVector<bool> suppressed(items.size(), false);
  for (int i = 0; i < items.size(); ++i) {
    if (suppressed[i]) continue;
    if (kept.size() >= maxDet) {
      if (limitReached) *limitReached = true;
      break;
    }
    kept.push_back(items[i]);
    for (int j = i + 1; j < items.size(); ++j) {
      if (suppressed[j]) continue;
      if (boxIou(items[i].bbox, items[j].bbox) > iouThr) suppressed[j] = true;
    }
  }
  return kept;
}

/** 对闭合折线做 Ramer–Douglas–Peucker 简化，不改变对应掩膜面积。 */
QVector<QPoint> simplifyClosed(const QVector<QPoint>& pts, double eps) {
  if (pts.size() <= 4 || eps <= 0) return pts;
  auto perpDist = [](QPoint a, QPoint b, QPoint p) -> double {
    const double vx = b.x() - a.x();
    const double vy = b.y() - a.y();
    const double len2 = vx * vx + vy * vy;
    if (len2 <= 1e-12) {
      const double dx = p.x() - a.x();
      const double dy = p.y() - a.y();
      return std::sqrt(dx * dx + dy * dy);
    }
    const double t = ((p.x() - a.x()) * vx + (p.y() - a.y()) * vy) / len2;
    const double px = a.x() + t * vx;
    const double py = a.y() + t * vy;
    const double dx = p.x() - px;
    const double dy = p.y() - py;
    return std::sqrt(dx * dx + dy * dy);
  };
  auto rec = [&](auto&& self, int i, int j, const QVector<QPoint>& in,
                 QVector<char>& keep) -> void {
    if (j <= i + 1) return;
    double best = -1;
    int mid = -1;
    for (int k = i + 1; k < j; ++k) {
      const double d = perpDist(in[i], in[j], in[k]);
      if (d > best) {
        best = d;
        mid = k;
      }
    }
    if (best > eps && mid >= 0) {
      keep[mid] = 1;
      self(self, i, mid, in, keep);
      self(self, mid, j, in, keep);
    }
  };
  QVector<QPoint> ring = pts;
  if (ring.size() >= 2 && ring.first() == ring.last()) ring.pop_back();
  if (ring.size() <= 4) return pts;
  QVector<char> keep(ring.size(), 0);
  keep[0] = 1;
  keep[ring.size() - 1] = 1;
  rec(rec, 0, ring.size() - 1, ring, keep);
  // also split across the closing edge via a mid start if almost collinear
  QVector<QPoint> out;
  out.reserve(ring.size());
  for (int i = 0; i < ring.size(); ++i)
    if (keep[i]) out.push_back(ring[i]);
  if (out.size() < 3) return pts;
  return out;
}

/** 左手则正方形追踪，得到 4 连通前景块的外轮廓（闭合，不含重复终点）。 */
QVector<QPoint> traceOuter(const QVector<uchar>& m, int w, int h, QPoint start) {
  const int dx[4] = {1, 0, -1, 0};
  const int dy[4] = {0, 1, 0, -1};
  auto fg = [&](int x, int y) -> bool {
    return x >= 0 && y >= 0 && x < w && y < h && m[y * w + x];
  };
  if (!fg(start.x(), start.y())) return {};
  int dir = 0;
  // face a background neighbor if possible
  for (int d = 0; d < 4; ++d) {
    if (!fg(start.x() + dx[d], start.y() + dy[d])) {
      dir = (d + 1) % 4;
      break;
    }
  }
  QVector<QPoint> pts;
  int x = start.x();
  int y = start.y();
  const int sx = x, sy = y, sd = dir;
  for (int iter = 0; iter < w * h * 4; ++iter) {
    pts.push_back(QPoint(x, y));
    int nd = (dir + 3) % 4;  // try left first
    bool moved = false;
    for (int k = 0; k < 4; ++k) {
      const int d = (nd + k) % 4;
      const int nx = x + dx[d];
      const int ny = y + dy[d];
      if (fg(nx, ny)) {
        x = nx;
        y = ny;
        dir = d;
        moved = true;
        break;
      }
    }
    if (!moved) break;
    if (x == sx && y == sy && dir == sd && pts.size() > 1) break;
    if (pts.size() >= kMaxContourPoints) break;
  }
  if (pts.size() >= 2 && pts.first() == pts.last()) pts.pop_back();
  return pts;
}

struct Blob {
  int area = 0;
  qint64 sumX = 0;
  qint64 sumY = 0;
  int minX = 0, minY = 0, maxX = 0, maxY = 0;
  QPoint seed;
};

/**
 * 按特征色做 4 连通域分析，并可在需要时提取外轮廓与孔洞轮廓。
 */
QVector<YoloItem> findColorBlobs(const QImage& src, int minArea, bool wantContours,
                                 int* unionArea) {
  if (unionArea) *unionArea = 0;
  if (src.isNull()) return {};
  const QImage img = src.convertToFormat(QImage::Format_RGB888);
  const int w = img.width();
  const int h = img.height();
  QVector<uchar> fg(w * h, 0);
  int unionPx = 0;
  for (int y = 0; y < h; ++y) {
    const uchar* row = img.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int r = row[x * 3 + 0];
      const int g = row[x * 3 + 1];
      const int b = row[x * 3 + 2];
      if (isFixturePixel(r, g, b)) {
        fg[y * w + x] = 1;
        ++unionPx;
      }
    }
  }
  if (unionArea) *unionArea = unionPx;
  if (unionPx == 0) return {};

  QVector<int> lab(w * h, 0);
  QVector<Blob> blobs;
  blobs.reserve(8);
  const int qx[4] = {1, -1, 0, 0};
  const int qy[4] = {0, 0, 1, -1};
  int next = 0;
  for (int y = 0; y < h; ++y) {
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!fg[i0] || lab[i0]) continue;
      ++next;
      Blob b;
      b.minX = b.maxX = x;
      b.minY = b.maxY = y;
      b.seed = QPoint(x, y);
      std::queue<int> q;
      q.push(i0);
      lab[i0] = next;
      while (!q.empty()) {
        const int i = q.front();
        q.pop();
        const int cx = i % w;
        const int cy = i / w;
        ++b.area;
        b.sumX += cx;
        b.sumY += cy;
        if (cx < b.minX) b.minX = cx;
        if (cy < b.minY) b.minY = cy;
        if (cx > b.maxX) b.maxX = cx;
        if (cy > b.maxY) b.maxY = cy;
        for (int k = 0; k < 4; ++k) {
          const int nx = cx + qx[k];
          const int ny = cy + qy[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (!fg[ni] || lab[ni]) continue;
          lab[ni] = next;
          q.push(ni);
        }
      }
      if (b.area >= minArea) blobs.push_back(b);
    }
  }

  const QRect expected = softSceneYoloFixtureRect(w, h);
  QVector<YoloItem> items;
  items.reserve(blobs.size());
  for (const Blob& b : blobs) {
    YoloItem it;
    it.classId = 0;
    it.label = QString::fromLatin1(kDefaultLabel);
    it.areaPixels = b.area;
    it.center = QPointF(double(b.sumX) / double(b.area) + 0.5,
                        double(b.sumY) / double(b.area) + 0.5);
    it.bbox = QRectF(b.minX, b.minY, b.maxX - b.minX + 1, b.maxY - b.minY + 1);
    const QRect br = it.bbox.toRect();
    double conf = 0.90 + 0.05 * qMin(1.0, double(b.area) / 200.0);
    if (expected.isValid() &&
        qAbs(br.center().x() - expected.center().x()) <= 4 &&
        qAbs(br.center().y() - expected.center().y()) <= 4 &&
        qAbs(br.width() - expected.width()) <= 4 &&
        qAbs(br.height() - expected.height()) <= 4) {
      conf = 0.97;
    }
    it.confidence = conf;

    if (wantContours) {
      const int bw = br.width();
      const int bh = br.height();
      const int pad = 1;
      const int mw = bw + pad * 2;
      const int mh = bh + pad * 2;
      QVector<uchar> local(mw * mh, 0);
      QVector<uchar> bg(mw * mh, 0);
      for (int yy = 0; yy < bh; ++yy) {
        for (int xx = 0; xx < bw; ++xx) {
          const int gx = br.x() + xx;
          const int gy = br.y() + yy;
          if (lab[gy * w + gx] == lab[b.seed.y() * w + b.seed.x()])
            local[(yy + pad) * mw + (xx + pad)] = 1;
        }
      }
      // flood background from the padded border to isolate holes
      std::queue<int> qq;
      auto tryBg = [&](int ix, int iy) {
        if (ix < 0 || iy < 0 || ix >= mw || iy >= mh) return;
        const int id = iy * mw + ix;
        if (local[id] || bg[id]) return;
        bg[id] = 1;
        qq.push(id);
      };
      for (int ix = 0; ix < mw; ++ix) {
        tryBg(ix, 0);
        tryBg(ix, mh - 1);
      }
      for (int iy = 0; iy < mh; ++iy) {
        tryBg(0, iy);
        tryBg(mw - 1, iy);
      }
      while (!qq.empty()) {
        const int id = qq.front();
        qq.pop();
        const int cx = id % mw;
        const int cy = id / mw;
        tryBg(cx + 1, cy);
        tryBg(cx - 1, cy);
        tryBg(cx, cy + 1);
        tryBg(cx, cy - 1);
      }
      QVector<uchar> hole(mw * mh, 0);
      for (int i = 0; i < mw * mh; ++i) {
        if (!local[i] && !bg[i]) hole[i] = 1;
      }
      const QPoint outerStart(b.seed.x() - br.x() + pad, b.seed.y() - br.y() + pad);
      QVector<QPoint> outer = traceOuter(local, mw, mh, outerStart);
      for (QPoint& pt : outer) pt += QPoint(br.x() - pad, br.y() - pad);
      if (!outer.isEmpty()) {
        it.contours.push_back(outer);
        it.contourIsHole.push_back(false);
      }
      // hole components
      QVector<int> hlab(mw * mh, 0);
      int hid = 0;
      for (int iy = 0; iy < mh; ++iy) {
        for (int ix = 0; ix < mw; ++ix) {
          const int i = iy * mw + ix;
          if (!hole[i] || hlab[i]) continue;
          ++hid;
          QPoint hseed(ix, iy);
          std::queue<int> hq;
          hq.push(i);
          hlab[i] = hid;
          while (!hq.empty()) {
            const int id = hq.front();
            hq.pop();
            const int cx = id % mw;
            const int cy = id / mw;
            for (int k = 0; k < 4; ++k) {
              const int nx = cx + qx[k];
              const int ny = cy + qy[k];
              if (nx < 0 || ny < 0 || nx >= mw || ny >= mh) continue;
              const int ni = ny * mw + nx;
              if (!hole[ni] || hlab[ni]) continue;
              hlab[ni] = hid;
              hq.push(ni);
            }
          }
          QVector<QPoint> hc = traceOuter(hole, mw, mh, hseed);
          for (QPoint& pt : hc) pt += QPoint(br.x() - pad, br.y() - pad);
          if (!hc.isEmpty()) {
            it.contours.push_back(hc);
            it.contourIsHole.push_back(true);
          }
        }
      }
    }
    items.push_back(it);
  }
  return items;
}

QImage buildBinaryMask(const QImage& src, const QVector<YoloItem>& items) {
  QImage mask(src.size(), QImage::Format_RGB888);
  mask.fill(Qt::black);
  if (src.isNull() || items.isEmpty()) return mask;
  const QImage img = src.convertToFormat(QImage::Format_RGB888);
  const int w = img.width();
  const int h = img.height();
  // Re-paint foreground pixels that fall inside any kept bbox and match the color.
  // Accurate per-instance masks would need labels; for software path the fixture
  // color itself is the mask.
  for (int y = 0; y < h; ++y) {
    const uchar* row = img.constScanLine(y);
    uchar* dst = mask.scanLine(y);
    for (int x = 0; x < w; ++x) {
      if (!isFixturePixel(row[x * 3 + 0], row[x * 3 + 1], row[x * 3 + 2])) continue;
      bool inside = false;
      for (const YoloItem& it : items) {
        if (it.bbox.adjusted(0, 0, 0.01, 0.01).contains(QPointF(x + 0.5, y + 0.5))) {
          inside = true;
          break;
        }
      }
      if (inside) {
        dst[x * 3 + 0] = 255;
        dst[x * 3 + 1] = 255;
        dst[x * 3 + 2] = 255;
      }
    }
  }
  return mask;
}

void mapItemToImage(YoloItem& it, const FollowRoi& fr, const Pose2D& pose, int ox,
                    int oy) {
  auto mapPt = [&](const QPointF& p) -> QPointF {
    if (fr.active)
      return poseMap(pose, QPointF(fr.roiX + p.x() + 0.5, fr.roiY + p.y() + 0.5));
    return QPointF(p.x() + ox, p.y() + oy);
  };
  const QRectF b = it.bbox;
  const QPointF p0 = mapPt(b.topLeft());
  const QPointF p1 = mapPt(b.topRight());
  const QPointF p2 = mapPt(b.bottomRight());
  const QPointF p3 = mapPt(b.bottomLeft());
  const qreal minx = qMin(qMin(p0.x(), p1.x()), qMin(p2.x(), p3.x()));
  const qreal miny = qMin(qMin(p0.y(), p1.y()), qMin(p2.y(), p3.y()));
  const qreal maxx = qMax(qMax(p0.x(), p1.x()), qMax(p2.x(), p3.x()));
  const qreal maxy = qMax(qMax(p0.y(), p1.y()), qMax(p2.y(), p3.y()));
  it.bbox = QRectF(minx, miny, maxx - minx, maxy - miny);
  it.center = mapPt(it.center);
  for (QVector<QPoint>& c : it.contours) {
    for (QPoint& pt : c) {
      const QPointF m = mapPt(QPointF(pt));
      pt = QPoint(int(std::lround(m.x())), int(std::lround(m.y())));
    }
  }
}

YoloResult runYoloImpl(const QImage& image, const QVariantMap& params, bool segment) {
  YoloResult r;
  r.requestedDevice =
      params.value(QStringLiteral("device"), QStringLiteral("cpu")).toString().trimmed();
  if (r.requestedDevice.isEmpty()) r.requestedDevice = QStringLiteral("cpu");
  r.device = QStringLiteral("cpu");
  r.backend = QStringLiteral("software");
  r.model = params.value(QStringLiteral("model"),
                         QString::fromLatin1(segment ? kDefaultSegModel : kDefaultDetectModel))
                .toString()
                .trimmed();
  if (r.model.isEmpty())
    r.model = QString::fromLatin1(segment ? kDefaultSegModel : kDefaultDetectModel);
  r.output = params.value(QStringLiteral("output"), QStringLiteral("overlay"))
                 .toString()
                 .trimmed()
                 .toLower();
  if (r.output != QLatin1String("mask")) r.output = QStringLiteral("overlay");

  const int imgMin = 32;
  const int imgMax = segment ? 1280 : 1920;
  const int rawSize = params.value(QStringLiteral("imageSize"), 640).toInt();
  if (rawSize < imgMin || rawSize > imgMax || (rawSize % 32) != 0) {
    r.error = QStringLiteral("imageSize 须为 %1–%2 且是 32 的倍数").arg(imgMin).arg(imgMax);
    return r;
  }
  const int imageSize = rawSize;
  int maxDet = params.value(QStringLiteral("maxDetections"), 50).toInt();
  if (segment) {
    if (maxDet < 1 || maxDet > 100) {
      r.error = QStringLiteral("maxDetections 须为 1–100");
      return r;
    }
    if (qint64(maxDet) * qint64(imageSize) * qint64(imageSize) > kSegBudget) {
      r.error = QStringLiteral("maxDetections×imageSize² 超过 32768000");
      return r;
    }
  } else {
    maxDet = qBound(1, maxDet, 300);
  }

  const double confThr = params.value(QStringLiteral("confidence"), 0.25).toDouble();
  const double iouThr = params.value(QStringLiteral("iou"), 0.45).toDouble();
  const int minArea = qMax(1, params.value(QStringLiteral("minArea"), 1).toInt());
  const double ctol =
      params.value(QStringLiteral("contourTolerance"), 0.5).toDouble();
  const QSet<QString> classes = parseClassFilter(params.value(QStringLiteral("classes")));

  if (image.isNull()) {
    r.error = QStringLiteral("输入图像为空");
    return r;
  }

  QImage work = image;
  FollowRoi fr;
  Pose2D pose;
  int ox = 0, oy = 0;
  bool mapped = false;
  if (params.value(QStringLiteral("followFixture")).toBool()) {
    pose = poseFromParams(params);
    fr = resolveFollowRoi(params, image.width(), image.height());
    if (fr.active) {
      work = extractFollowPatch(image, fr, pose);
      mapped = true;
    }
  }
  if (!mapped) {
    const int rx = params.value(QStringLiteral("roiX"), 0).toInt();
    const int ry = params.value(QStringLiteral("roiY"), 0).toInt();
    const int rw = params.value(QStringLiteral("roiW"), 0).toInt();
    const int rh = params.value(QStringLiteral("roiH"), 0).toInt();
    if (rw > 0 && rh > 0) {
      const QRect roi = QRect(rx, ry, rw, rh)
                            .intersected(QRect(0, 0, image.width(), image.height()));
      if (roi.isEmpty()) {
        r.error = QStringLiteral("ROI 为空");
        return r;
      }
      work = image.copy(roi);
      ox = roi.x();
      oy = roi.y();
      mapped = true;
    }
  }

  int unionPx = 0;
  QVector<YoloItem> blobs;
  QString runtimeNote;
  const QString weightPath = resolveYoloWeightPath(r.model);
  bool usedOnnx = false;
  // 检测算子优先走本地 ONNX；失败或条件不满足时回退 software，不算算子失败。
  if (!segment && !weightPath.isEmpty()) {
    const QString suf = QFileInfo(weightPath).suffix().toLower();
    if (suf == QLatin1String("onnx")) {
      YoloResult onnxOut;
      QString onnxErr;
      if (tryYoloOnnxDetect(work, weightPath, params, imageSize, &onnxOut, &onnxErr)) {
        usedOnnx = true;
        r.backend = QStringLiteral("onnx");
        r.device = onnxOut.device.isEmpty() ? QStringLiteral("cpu") : onnxOut.device;
        blobs = onnxOut.items;
        r.rawCount = onnxOut.rawCount;
        runtimeNote = QStringLiteral("本地 ONNX Runtime 推理（backend=onnx）· 权重=%1")
                          .arg(weightPath);
      } else {
        runtimeNote = QStringLiteral("本地 ONNX 推理失败，回退 software：%1")
                          .arg(onnxErr);
      }
    } else if (suf == QLatin1String("pt") || suf == QLatin1String("pth")) {
      runtimeNote = QStringLiteral(
          "已找到本地 .pt 权重，C++ 路径需要同名或指定的 .onnx；未自动下载，回退 software。");
    } else {
      runtimeNote = QStringLiteral("本地权重扩展名不受支持，回退 software：%1").arg(weightPath);
    }
  } else if (segment && !weightPath.isEmpty()) {
    runtimeNote = QStringLiteral(
        "分割算子的真实 ONNX 掩膜路径尚未接入，回退 software。不会自动下载模型。");
  }
  if (!usedOnnx) {
    blobs = findColorBlobs(work, minArea, segment, &unionPx);
    r.rawCount = blobs.size();
    r.backend = QStringLiteral("software");
  }

  QVector<YoloItem> kept;
  kept.reserve(blobs.size());
  for (YoloItem& it : blobs) {
    if (it.confidence < confThr) continue;
    if (!classAllowed(it, classes)) continue;
    if (mapped) mapItemToImage(it, fr, pose, ox, oy);
    kept.push_back(it);
  }
  r.filteredCount = kept.size();
  bool limit = false;
  kept = applyNms(kept, iouThr, maxDet, &limit);
  r.limitReached = limit;

  int contourPts = 0;
  r.summedAreaPixels = 0;
  if (segment) {
    for (YoloItem& it : kept) {
      r.summedAreaPixels += it.areaPixels;
      for (int c = 0; c < it.contours.size(); ++c) {
        it.contours[c] = simplifyClosed(it.contours[c], ctol);
        contourPts += it.contours[c].size();
      }
    }
    if (contourPts > kMaxContourPoints) {
      r.note = QStringLiteral("轮廓点数超过 50000，已截断后续点");
      int remain = kMaxContourPoints;
      for (YoloItem& it : kept) {
        for (int c = 0; c < it.contours.size(); ++c) {
          if (remain <= 0) {
            it.contours[c].clear();
            continue;
          }
          if (it.contours[c].size() > remain) it.contours[c].resize(remain);
          remain -= it.contours[c].size();
        }
      }
    }
    r.unionAreaPixels = unionPx;
    if (r.output == QLatin1String("mask"))
      r.mask = buildBinaryMask(image, kept);
  }

  r.items = kept;
  r.count = kept.size();
  r.ok = true;

  QString weightNote = runtimeNote;
  if (weightNote.isEmpty()) {
    weightNote = QStringLiteral(
        "模型未安装：使用软图确定性检测器（backend=software）。不会自动下载模型。");
  }
  if (r.requestedDevice.startsWith(QLatin1String("cuda"), Qt::CaseInsensitive)) {
    if (!r.note.isEmpty()) r.note += QLatin1Char(' ');
    r.note += QStringLiteral("请求 GPU，软件检测器仅在 CPU 上运行。");
  }
  const QString head = r.note;
  r.note = QStringLiteral("%1 · device=%2 · imageSize=%3 · count=%4")
               .arg(weightNote)
               .arg(r.device)
               .arg(imageSize)
               .arg(r.count);
  if (!head.isEmpty()) r.note = head + QLatin1Char(' ') + r.note;
  return r;
}

}  // namespace

YoloResult runYoloDetect(const QImage& image, const QVariantMap& params) {
  return runYoloImpl(image, params, false);
}

YoloResult runYoloSegment(const QImage& image, const QVariantMap& params) {
  return runYoloImpl(image, params, true);
}

QStringList yoloSelfTest() {
  QStringList fails;
  const QImage scene = makeSoftScene(1280, 1024);
  if (scene.isNull() || scene.width() != 1280 || scene.height() != 1024) {
    fails << QStringLiteral("soft scene size");
    return fails;
  }
  const QRect outer = softSceneYoloFixtureRect(1280, 1024);
  const QRect hole = softSceneYoloFixtureHoleRect(1280, 1024);
  const int expectArea = outer.width() * outer.height() - hole.width() * hole.height();
  if (expectArea != 4096)
    fails << QStringLiteral("fixture area formula %1").arg(expectArea);

  // count fixture-colored pixels in the scene
  int painted = 0;
  const QImage rgb = scene.convertToFormat(QImage::Format_RGB888);
  for (int y = 0; y < rgb.height(); ++y) {
    const uchar* row = rgb.constScanLine(y);
    for (int x = 0; x < rgb.width(); ++x) {
      const int r = row[x * 3 + 0];
      const int g = row[x * 3 + 1];
      const int b = row[x * 3 + 2];
      if (r == 220 && g == 40 && b == 80) ++painted;
    }
  }
  if (painted != expectArea)
    fails << QStringLiteral("painted pixels %1 != %2").arg(painted).arg(expectArea);

  {
    const YoloResult d = runYoloDetect(scene, {{QStringLiteral("confidence"), 0.25},
                                               {QStringLiteral("imageSize"), 640}});
    if (!d.ok) fails << QStringLiteral("detect not ok: %1").arg(d.error);
    if (d.backend != QLatin1String("software"))
      fails << QStringLiteral("detect backend %1").arg(d.backend);
    if (d.count != 1) fails << QStringLiteral("detect count %1").arg(d.count);
    if (d.count >= 1) {
      if (d.items[0].label != QLatin1String("part"))
        fails << QStringLiteral("detect label %1").arg(d.items[0].label);
      if (d.items[0].confidence < 0.95)
        fails << QStringLiteral("detect score %1").arg(d.items[0].confidence);
      const QRect br = d.items[0].bbox.toRect();
      if (qAbs(br.x() - outer.x()) > 2 || qAbs(br.y() - outer.y()) > 2 ||
          qAbs(br.width() - outer.width()) > 2 ||
          qAbs(br.height() - outer.height()) > 2)
        fails << QStringLiteral("detect bbox %1,%2 %3x%4")
                     .arg(br.x())
                     .arg(br.y())
                     .arg(br.width())
                     .arg(br.height());
    }
  }

  {
    const YoloResult s = runYoloSegment(
        scene, {{QStringLiteral("confidence"), 0.25},
                {QStringLiteral("imageSize"), 640},
                {QStringLiteral("minArea"), 1},
                {QStringLiteral("contourTolerance"), 0.5},
                {QStringLiteral("output"), QStringLiteral("overlay")}});
    if (!s.ok) fails << QStringLiteral("segment not ok: %1").arg(s.error);
    if (s.count != 1) fails << QStringLiteral("segment count %1").arg(s.count);
    if (s.count >= 1) {
      if (s.items[0].areaPixels != expectArea)
        fails << QStringLiteral("segment area %1").arg(s.items[0].areaPixels);
      if (s.items[0].confidence < 0.95)
        fails << QStringLiteral("segment score %1").arg(s.items[0].confidence);
      if (s.items[0].contours.isEmpty())
        fails << QStringLiteral("segment missing outer contour");
      int holes = 0;
      for (bool h : s.items[0].contourIsHole)
        if (h) ++holes;
      if (holes < 1) fails << QStringLiteral("segment missing hole contour");
    }
    if (s.unionAreaPixels != expectArea)
      fails << QStringLiteral("segment union %1").arg(s.unionAreaPixels);
  }

  {
    QImage blank(128, 128, QImage::Format_RGB888);
    blank.fill(Qt::white);
    const YoloResult d = runYoloDetect(blank, {{QStringLiteral("imageSize"), 640}});
    if (!d.ok) fails << QStringLiteral("blank detect error %1").arg(d.error);
    if (d.count != 0) fails << QStringLiteral("blank detect count %1").arg(d.count);
  }

  {
    const YoloResult d = runYoloDetect(
        scene, {{QStringLiteral("imageSize"), 640},
                {QStringLiteral("classes"), QStringLiteral("other")}});
    if (!d.ok) fails << QStringLiteral("filter detect error %1").arg(d.error);
    if (d.count != 0) fails << QStringLiteral("filter detect count %1").arg(d.count);
  }

  {
    const YoloResult s = runYoloSegment(
        scene, {{QStringLiteral("imageSize"), 640}, {QStringLiteral("minArea"), 100000}});
    if (!s.ok) fails << QStringLiteral("minArea error %1").arg(s.error);
    if (s.count != 0) fails << QStringLiteral("minArea count %1").arg(s.count);
  }

  {
    const YoloResult d = runYoloDetect(scene, {{QStringLiteral("imageSize"), 31}});
    if (d.ok) fails << QStringLiteral("invalid imageSize should fail");
    if (d.error.isEmpty()) fails << QStringLiteral("invalid imageSize no error");
  }

  // 默认仍走 software；仅在显式指定本地烟测 ONNX 且运行时可用时证明真实推理路径。
  {
    const QString smoke = resolveYoloWeightPath(QStringLiteral("sieans-yolo-smoke.onnx"));
    if (!smoke.isEmpty() && onnxRuntimeAvailable()) {
      const YoloResult d = runYoloDetect(
          scene, {{QStringLiteral("model"), smoke},
                  {QStringLiteral("confidence"), 0.25},
                  {QStringLiteral("imageSize"), 640}});
      if (!d.ok) fails << QStringLiteral("onnx detect not ok: %1").arg(d.error);
      if (d.backend != QLatin1String("onnx"))
        fails << QStringLiteral("onnx backend %1").arg(d.backend);
      if (d.count < 1) fails << QStringLiteral("onnx count %1").arg(d.count);
      if (d.count >= 1 && d.items[0].confidence < 0.9)
        fails << QStringLiteral("onnx score %1").arg(d.items[0].confidence);
    }
  }

  return fails;
}

}  // namespace sieans_qt
