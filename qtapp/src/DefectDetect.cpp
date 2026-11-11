#include "DefectDetect.hpp"
#include "SoftFrame.hpp"

#include <QColor>
#include <QFileInfo>
#include <QPainter>
#include <QSet>
#include <QtGlobal>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

namespace sieans_qt {
namespace {

QImage toGray(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_Grayscale8);
}

QImage cropBottom(const QImage& src, int ignoreBottom) {
  if (src.isNull()) return {};
  const int cut = qBound(0, ignoreBottom, src.height() - 1);
  if (cut <= 0) return src;
  const int h = src.height() - cut;
  if (h <= 0) return {};
  return src.copy(0, 0, src.width(), h);
}

QImage applyRoi(const QImage& src, const QVariantMap& params, QPoint* origin) {
  const int rw = params.value(QStringLiteral("roiW"), 0).toInt();
  const int rh = params.value(QStringLiteral("roiH"), 0).toInt();
  if (rw <= 0 || rh <= 0) {
    if (origin) *origin = QPoint(0, 0);
    return src;
  }
  const int rx = qBound(0, params.value(QStringLiteral("roiX"), 0).toInt(), src.width() - 1);
  const int ry = qBound(0, params.value(QStringLiteral("roiY"), 0).toInt(), src.height() - 1);
  const int w = qBound(1, rw, src.width() - rx);
  const int h = qBound(1, rh, src.height() - ry);
  if (origin) *origin = QPoint(rx, ry);
  return src.copy(rx, ry, w, h);
}

QImage boxBlurGray(const QImage& src, int k) {
  if (src.isNull() || k < 3) return src;
  if (k % 2 == 0) ++k;
  const int r = k / 2;
  QImage img = src.convertToFormat(QImage::Format_Grayscale8);
  const int w = img.width();
  const int h = img.height();
  // separable box blur, two passes, integer sums
  QImage tmp(w, h, QImage::Format_Grayscale8);
  std::vector<int> acc(w + 1, 0);
  for (int y = 0; y < h; ++y) {
    const uchar* in = img.constScanLine(y);
    acc[0] = 0;
    for (int x = 0; x < w; ++x) acc[x + 1] = acc[x] + in[x];
    uchar* out = tmp.scanLine(y);
    for (int x = 0; x < w; ++x) {
      const int x0 = qMax(0, x - r);
      const int x1 = qMin(w - 1, x + r);
      const int n = x1 - x0 + 1;
      out[x] = uchar((acc[x1 + 1] - acc[x0] + n / 2) / n);
    }
  }
  QImage dst(w, h, QImage::Format_Grayscale8);
  std::vector<int> col(h);
  for (int x = 0; x < w; ++x) {
    for (int y = 0; y < h; ++y) col[y] = tmp.constScanLine(y)[x];
    int run = 0;
    // prefix
    std::vector<int> pre(h + 1, 0);
    for (int y = 0; y < h; ++y) pre[y + 1] = pre[y] + col[y];
    for (int y = 0; y < h; ++y) {
      const int y0 = qMax(0, y - r);
      const int y1 = qMin(h - 1, y + r);
      const int n = y1 - y0 + 1;
      dst.scanLine(y)[x] = uchar((pre[y1 + 1] - pre[y0] + n / 2) / n);
    }
    (void)run;
  }
  return dst;
}

struct Blob {
  int x0 = 0, y0 = 0, x1 = 0, y1 = 0;
  int area = 0;
};

QVector<Blob> labelBlobs(const QImage& mask, int minArea, int maxCount) {
  QVector<Blob> out;
  if (mask.isNull()) return out;
  const int w = mask.width();
  const int h = mask.height();
  const int n = w * h;
  std::vector<uchar> seen(n, 0);
  auto at = [&](int x, int y) -> uchar {
    return mask.constScanLine(y)[x];
  };
  const int dx[8] = {-1, 0, 1, -1, 1, -1, 0, 1};
  const int dy[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
  std::vector<int> stack;
  stack.reserve(1024);
  for (int y = 0; y < h; ++y) {
    const uchar* row = mask.constScanLine(y);
    for (int x = 0; x < w; ++x) {
      const int i0 = y * w + x;
      if (!row[x] || seen[i0]) continue;
      stack.clear();
      stack.push_back(i0);
      seen[i0] = 1;
      Blob b;
      b.x0 = b.x1 = x;
      b.y0 = b.y1 = y;
      b.area = 0;
      while (!stack.empty()) {
        const int i = stack.back();
        stack.pop_back();
        const int cx = i % w;
        const int cy = i / w;
        ++b.area;
        if (cx < b.x0) b.x0 = cx;
        if (cx > b.x1) b.x1 = cx;
        if (cy < b.y0) b.y0 = cy;
        if (cy > b.y1) b.y1 = cy;
        for (int k = 0; k < 8; ++k) {
          const int nx = cx + dx[k];
          const int ny = cy + dy[k];
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const int ni = ny * w + nx;
          if (seen[ni] || !at(nx, ny)) continue;
          seen[ni] = 1;
          stack.push_back(ni);
        }
      }
      if (b.area < minArea) continue;
      out.push_back(b);
      if (out.size() >= maxCount) return out;
    }
  }
  return out;
}

}  // namespace

QImage resolveDefectsReference(const QImage& current, const QVariantMap& params,
                               QString* error) {
  const QString src =
      params.value(QStringLiteral("referenceSource"), QStringLiteral("file")).toString();
  const int w = current.isNull() ? 0 : current.width();
  const int h = current.isNull() ? 0 : current.height();
  if (src == QLatin1String("soft_scene") || src == QLatin1String("soft_clean")) {
    if (w <= 0) {
      if (error) *error = QStringLiteral("当前图像为空，无法生成软参考图");
      return {};
    }
    return makeSoftScene(w, h);
  }
  if (src == QLatin1String("soft_scene_blemish") || src == QLatin1String("soft_blemish")) {
    if (w <= 0) {
      if (error) *error = QStringLiteral("当前图像为空，无法生成软参考图");
      return {};
    }
    return makeSoftSceneBlemish(w, h);
  }
  const QString path = params.value(QStringLiteral("referencePath")).toString().trimmed();
  if (path.isEmpty()) {
    if (error) *error = QStringLiteral("缺陷检测需要同尺寸良品参考图（设置参考图路径或参考来源）");
    return {};
  }
  QImage img(path);
  if (img.isNull()) {
    if (error)
      *error = QStringLiteral("无法读取参考图: %1").arg(path);
    return {};
  }
  return img.convertToFormat(QImage::Format_RGB888);
}

DefectResult runDefects(const QImage& current, const QImage& reference,
                        const QVariantMap& params) {
  DefectResult r;
  r.method = params.value(QStringLiteral("method"), QStringLiteral("absdiff")).toString();
  r.judgeEnable = !params.contains(QStringLiteral("judgeEnable")) ||
                  params.value(QStringLiteral("judgeEnable")).toBool();
  if (current.isNull()) {
    r.error = QStringLiteral("当前图像为空");
    r.note = r.error;
    return r;
  }
  if (reference.isNull()) {
    r.error = QStringLiteral("缺陷检测需要同尺寸、同位置、相同光照的良品参考图");
    r.note = r.error;
    return r;
  }

  const int ignoreBottom = qMax(0, params.value(QStringLiteral("ignoreBottomPx"), 0).toInt());
  QPoint origin(0, 0);
  QImage a = applyRoi(cropBottom(current, ignoreBottom), params, &origin);
  QImage bIn = cropBottom(reference, ignoreBottom);
  // ROI on reference: if same size as current before ROI, apply same crop via origin
  // First match sizes.
  const bool scaleRef = !params.contains(QStringLiteral("scaleReference")) ||
                        params.value(QStringLiteral("scaleReference")).toBool();
  // applyRoi already applied to current (a). If reference was full-size like current
  // before ROI, scale bIn to the pre-ROI cropped current, then apply same ROI.
  QImage croppedCurrent = cropBottom(current, ignoreBottom);
  if (bIn.size() != croppedCurrent.size()) {
    if (!scaleRef) {
      r.error = QStringLiteral("良品参考图必须与检测区域尺寸一致（%1×%2 vs %3×%4）")
                    .arg(bIn.width())
                    .arg(bIn.height())
                    .arg(croppedCurrent.width())
                    .arg(croppedCurrent.height());
      r.note = r.error;
      return r;
    }
    bIn = bIn.scaled(croppedCurrent.size(), Qt::IgnoreAspectRatio, Qt::FastTransformation);
  }
  QImage b = (params.value(QStringLiteral("roiW"), 0).toInt() > 0 &&
              params.value(QStringLiteral("roiH"), 0).toInt() > 0)
                 ? applyRoi(bIn, params, nullptr)
                 : bIn;
  if (b.size() != a.size()) {
    if (!scaleRef) {
      r.error = QStringLiteral("良品参考图必须与检测区域尺寸一致");
      r.note = r.error;
      return r;
    }
    b = b.scaled(a.size(), Qt::IgnoreAspectRatio, Qt::FastTransformation);
  }

  int blurK = params.value(QStringLiteral("blur"), 3).toInt();
  if (blurK > 0 && blurK % 2 == 0) ++blurK;
  QImage ga = toGray(a);
  QImage gb = toGray(b);
  if (blurK >= 3) {
    ga = boxBlurGray(ga, blurK);
    gb = boxBlurGray(gb, blurK);
  }

  int thr = params.contains(QStringLiteral("threshold"))
                ? params.value(QStringLiteral("threshold")).toInt()
                : params.value(QStringLiteral("differenceThreshold"), 30).toInt();
  thr = qBound(1, thr, 255);
  const int minArea = qMax(1, params.value(QStringLiteral("minArea"), 20).toInt());
  const int maxCount = qBound(1, params.value(QStringLiteral("maxCount"), 200).toInt(), 5000);

  const int w = ga.width();
  const int h = ga.height();
  if (w <= 0 || h <= 0) {
    r.error = QStringLiteral("比较区域无效");
    r.note = r.error;
    return r;
  }
  QImage mask(w, h, QImage::Format_Grayscale8);
  mask.fill(0);
  int accepted = 0;
  for (int y = 0; y < h; ++y) {
    const uchar* pa = ga.constScanLine(y);
    const uchar* pb = gb.constScanLine(y);
    uchar* pm = mask.scanLine(y);
    for (int x = 0; x < w; ++x) {
      const int d = std::abs(int(pa[x]) - int(pb[x]));
      if (d >= thr) {
        pm[x] = 255;
        ++accepted;  // temporary; will recompute after minArea filter
      }
    }
  }

  const QVector<Blob> blobs = labelBlobs(mask, minArea, maxCount);
  // recompute accepted pixels belonging to kept blobs
  accepted = 0;
  r.items.reserve(blobs.size());
  for (const Blob& blob : blobs) {
    accepted += blob.area;
    DefectItem it;
    it.areaPixels = blob.area;
    it.bbox = QRect(blob.x0 + origin.x(), blob.y0 + origin.y(),
                    blob.x1 - blob.x0 + 1, blob.y1 - blob.y0 + 1);
    r.items.push_back(it);
    if (blob.area > r.maxArea) r.maxArea = blob.area;
  }
  r.totalArea = accepted;
  r.count = r.items.size();
  const qint64 denom = qint64(w) * h;
  r.defectRatio = denom > 0 ? double(accepted) / double(denom) : 0.0;

  const double allowedLegacy =
      params.contains(QStringLiteral("maxDefectRatio"))
          ? params.value(QStringLiteral("maxDefectRatio")).toDouble()
          : 1.0;
  const bool passedLegacy = r.defectRatio <= allowedLegacy;
  const int judgeMaxCount = qBound(0, params.value(QStringLiteral("judgeMaxCount"), 0).toInt(), 5000);
  const double judgeMaxRatio =
      params.contains(QStringLiteral("judgeMaxRatio"))
          ? params.value(QStringLiteral("judgeMaxRatio")).toDouble()
          : 0.05;
  bool judgeOk = (r.count <= judgeMaxCount) && (r.defectRatio <= judgeMaxRatio);
  r.judgeOk = r.judgeEnable ? judgeOk : true;
  r.passed = r.judgeEnable ? judgeOk : passedLegacy;
  r.ok = true;
  r.note = QStringLiteral("疑似缺陷 %1 处 · 比例 %2 · 最大面积 %3 px")
               .arg(r.count)
               .arg(r.defectRatio, 0, 'f', 5)
               .arg(r.maxArea);
  return r;
}

QStringList defectsSelfTest() {
  QStringList fails;
  auto expect = [&](bool cond, const char* msg) {
    if (!cond) fails << QString::fromUtf8(msg);
  };

  QImage clean(160, 120, QImage::Format_RGB888);
  clean.fill(QColor(180, 180, 180));
  QVariantMap base;
  base.insert(QStringLiteral("differenceThreshold"), 30);
  base.insert(QStringLiteral("minArea"), 20);
  base.insert(QStringLiteral("blur"), 0);
  base.insert(QStringLiteral("judgeEnable"), true);
  base.insert(QStringLiteral("judgeMaxCount"), 0);
  base.insert(QStringLiteral("judgeMaxRatio"), 0.05);

  {
    const DefectResult r = runDefects(clean, clean, base);
    expect(r.ok, "identical ok");
    expect(r.count == 0, "identical count=0");
    expect(r.defectRatio == 0.0, "identical ratio=0");
    expect(r.passed && r.judgeOk, "identical passed");
  }

  QImage spotted = clean.copy();
  {
    QPainter p(&spotted);
    p.fillRect(QRect(40, 30, 28, 22), QColor(10, 10, 10));
    p.end();
  }
  {
    const DefectResult r = runDefects(spotted, clean, base);
    expect(r.ok, "blob ok");
    expect(r.count >= 1, "blob count>=1");
    expect(r.maxArea >= 20, "blob area");
    expect(!r.passed && !r.judgeOk, "blob NG (judgeMaxCount=0)");
    expect(r.defectRatio > 0.0, "blob ratio>0");
    expect(!r.items.isEmpty(), "blob item");
    if (!r.items.isEmpty()) {
      expect(r.items.first().bbox.width() >= 20, "bbox w");
      expect(r.items.first().bbox.height() >= 16, "bbox h");
    }
  }

  // speckle smaller than minArea is ignored
  QImage speck = clean.copy();
  {
    QPainter p(&speck);
    p.fillRect(QRect(10, 10, 2, 2), QColor(0, 0, 0));
    p.end();
  }
  {
    const DefectResult r = runDefects(speck, clean, base);
    expect(r.ok && r.count == 0 && r.passed, "tiny speck filtered");
  }

  {
    QVariantMap p = base;
    p.insert(QStringLiteral("judgeEnable"), false);
    p.insert(QStringLiteral("maxDefectRatio"), 1.0);
    const DefectResult r = runDefects(spotted, clean, p);
    expect(r.ok && r.count >= 1 && r.passed, "legacy ratio=1 passes");
  }

  {
    const DefectResult r = runDefects(clean, QImage(), base);
    expect(!r.ok && r.error.contains(QStringLiteral("参考图")), "missing ref");
  }

  {
    QImage other(80, 60, QImage::Format_RGB888);
    other.fill(QColor(180, 180, 180));
    QVariantMap p = base;
    p.insert(QStringLiteral("scaleReference"), false);
    const DefectResult r = runDefects(clean, other, p);
    expect(!r.ok && r.error.contains(QStringLiteral("尺寸")), "size mismatch");
    p.insert(QStringLiteral("scaleReference"), true);
    const DefectResult r2 = runDefects(clean, other, p);
    expect(r2.ok && r2.count == 0, "scale ref identical content");
  }

  return fails;
}

}  // namespace sieans_qt
