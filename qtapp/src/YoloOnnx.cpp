#include "YoloOnnx.hpp"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QTextStream>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <queue>
#include <vector>

#ifdef SIEANS_HAS_ONNXRUNTIME
#include "onnxruntime_c_api.h"
#include <dlfcn.h>
#endif

namespace sieans_qt {
namespace {

/** 去掉末尾斜杠，便于拼接 models 子目录。 */
QString trimSlash(QString p) {
  while (p.size() > 1 && (p.endsWith(QLatin1Char('/')) || p.endsWith(QLatin1Char('\\'))))
    p.chop(1);
  return p;
}

/** 若 dir/base 是普通文件则返回规范路径。 */
QString fileIfExists(const QString& dir, const QString& base) {
  if (dir.isEmpty() || base.isEmpty()) return {};
  const QFileInfo fi(QDir(dir).filePath(base));
  if (fi.isFile()) return fi.canonicalFilePath();
  return {};
}

}  // namespace

QString resolveYoloWeightPath(const QString& model) {
  const QString raw = model.trimmed();
  if (raw.isEmpty()) return {};
  const QFileInfo given(raw);
  if (given.isFile()) return given.canonicalFilePath();

  const QString base = given.fileName();
  QStringList roots;
  const QByteArray env = qgetenv("SIEANS_YOLO_MODELS_DIR");
  if (!env.isEmpty()) roots << trimSlash(QString::fromUtf8(env));
  roots << QDir::current().absoluteFilePath(QStringLiteral("models"));
  const QDir app(QCoreApplication::applicationDirPath());
  roots << app.absoluteFilePath(QStringLiteral("models"));
  // qtapp/build/sieans_qt → 仓库 models/
  roots << QDir(app.absoluteFilePath(QStringLiteral("../.."))).absoluteFilePath(
      QStringLiteral("models"));
  roots << QDir::home().absoluteFilePath(QStringLiteral(".local/share/sieans/models"));
  QStringList seen;
  for (const QString& root : roots) {
    const QString key = QFileInfo(root).absoluteFilePath();
    if (seen.contains(key)) continue;
    seen << key;
    if (const QString hit = fileIfExists(root, base); !hit.isEmpty()) return hit;
  }
  return {};
}

#ifdef SIEANS_HAS_ONNXRUNTIME

namespace {

/** 解析候选 libonnxruntime.so 路径，供 dlopen 使用。 */
QStringList onnxLibCandidates() {
  QStringList out;
  auto add = [&](const QString& p) {
    if (!p.isEmpty() && !out.contains(p)) out << p;
  };
  const QByteArray env = qgetenv("SIEANS_ONNXRUNTIME_DIR");
  if (!env.isEmpty()) {
    const QString root = trimSlash(QString::fromUtf8(env));
    add(root + QStringLiteral("/lib/libonnxruntime.so"));
    add(root + QStringLiteral("/lib/libonnxruntime.so.1"));
  }
  const QString home = QDir::homePath();
  add(home + QStringLiteral("/.local/opt/onnxruntime/lib/libonnxruntime.so"));
  add(home + QStringLiteral("/.local/opt/onnxruntime/lib/libonnxruntime.so.1"));
  const QDir app(QCoreApplication::applicationDirPath());
  add(app.absoluteFilePath(QStringLiteral("libonnxruntime.so")));
  add(QStringLiteral("libonnxruntime.so.1"));
  add(QStringLiteral("libonnxruntime.so"));
  return out;
}

struct OrtApiHold {
  void* handle = nullptr;
  const OrtApi* api = nullptr;
};

/** 加载官方 ONNX Runtime C API；句柄保持到进程结束，避免使用中被卸载。 */
OrtApiHold loadOrt() {
  OrtApiHold hold;
  for (const QString& path : onnxLibCandidates()) {
    void* h = nullptr;
    if (path.startsWith(QLatin1Char('/'))) {
      if (!QFileInfo::exists(path)) continue;
      h = dlopen(path.toUtf8().constData(), RTLD_NOW | RTLD_LOCAL);
    } else {
      h = dlopen(path.toUtf8().constData(), RTLD_NOW | RTLD_LOCAL);
    }
    if (!h) continue;
    using GetBaseFn = const OrtApiBase* (*)();
    auto getBase = reinterpret_cast<GetBaseFn>(dlsym(h, "OrtGetApiBase"));
    if (!getBase) {
      dlclose(h);
      continue;
    }
    const OrtApiBase* base = getBase();
    if (!base || !base->GetApi) {
      dlclose(h);
      continue;
    }
    const OrtApi* api = base->GetApi(ORT_API_VERSION);
    if (!api) {
      dlclose(h);
      continue;
    }
    hold.handle = h;
    hold.api = api;
    return hold;
  }
  return hold;
}

OrtApiHold& ortHold() {
  static OrtApiHold h = loadOrt();
  return h;
}

const OrtApi* ortApi() { return ortHold().api; }

/** 把 OrtStatus 转成异常信息并释放。 */
void checkOrt(const OrtApi* api, OrtStatus* st, const char* what) {
  if (!st) return;
  const char* msg = api->GetErrorMessage(st);
  const std::string text = msg ? msg : "unknown ORT error";
  api->ReleaseStatus(st);
  throw std::runtime_error(std::string(what) + ": " + text);
}

struct Letterbox {
  int input = 64;
  double scale = 1;
  double padX = 0;
  double padY = 0;
  int dstW = 0;
  int dstH = 0;
};

/** 按 YOLO 惯例把原图等比缩放到 input×input，剩余区域填 114。 */
Letterbox makeLetterbox(int srcW, int srcH, int input) {
  Letterbox lb;
  lb.input = input;
  if (srcW <= 0 || srcH <= 0 || input <= 0) return lb;
  lb.scale = std::min(double(input) / double(srcW), double(input) / double(srcH));
  lb.dstW = std::max(1, int(std::lround(srcW * lb.scale)));
  lb.dstH = std::max(1, int(std::lround(srcH * lb.scale)));
  if (lb.dstW > input) lb.dstW = input;
  if (lb.dstH > input) lb.dstH = input;
  lb.padX = (input - lb.dstW) / 2.0;
  lb.padY = (input - lb.dstH) / 2.0;
  return lb;
}

/** 生成 NCHW float32、[0,1] 归一化、灰色填充的 letterbox 输入。 */
std::vector<float> preprocessNchw(const QImage& src, const Letterbox& lb) {
  const int in = lb.input;
  std::vector<float> out(static_cast<size_t>(3 * in * in), 114.f / 255.f);
  if (src.isNull() || in <= 0) return out;
  const QImage rgb = src.convertToFormat(QImage::Format_RGB888);
  const QImage scaled =
      rgb.scaled(lb.dstW, lb.dstH, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
  const int ox = int(std::floor(lb.padX));
  const int oy = int(std::floor(lb.padY));
  const int plane = in * in;
  for (int y = 0; y < scaled.height(); ++y) {
    const int dy = oy + y;
    if (dy < 0 || dy >= in) continue;
    const uchar* row = scaled.constScanLine(y);
    for (int x = 0; x < scaled.width(); ++x) {
      const int dx = ox + x;
      if (dx < 0 || dx >= in) continue;
      const int idx = dy * in + dx;
      out[idx] = row[x * 3 + 0] / 255.f;
      out[plane + idx] = row[x * 3 + 1] / 255.f;
      out[2 * plane + idx] = row[x * 3 + 2] / 255.f;
    }
  }
  return out;
}

/** 把 letterbox 坐标反映射回 work 图像坐标。 */
QRectF unletterbox(const Letterbox& lb, double x1, double y1, double x2, double y2,
                   int srcW, int srcH) {
  if (lb.scale <= 1e-12) return {};
  const double xa = (x1 - lb.padX) / lb.scale;
  const double ya = (y1 - lb.padY) / lb.scale;
  const double xb = (x2 - lb.padX) / lb.scale;
  const double yb = (y2 - lb.padY) / lb.scale;
  const double l = std::min(xa, xb);
  const double t = std::min(ya, yb);
  const double r = std::max(xa, xb);
  const double b = std::max(ya, yb);
  const QRectF box(l, t, r - l, b - t);
  return box.intersected(QRectF(0, 0, srcW, srcH));
}

/** 读取与权重同名的 .names/.txt 标签，每行一个类名。 */
QStringList loadLabelFile(const QString& weightPath) {
  const QFileInfo fi(weightPath);
  const QString stem = fi.absolutePath() + QLatin1Char('/') + fi.completeBaseName();
  for (const char* ext : {".names", ".txt", ".labels"}) {
    QFile f(stem + QString::fromLatin1(ext));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text)) continue;
    QStringList names;
    QTextStream in(&f);
    while (!in.atEnd()) {
      const QString line = in.readLine().trimmed();
      if (!line.isEmpty() && !line.startsWith(QLatin1Char('#'))) names << line;
    }
    if (!names.isEmpty()) return names;
  }
  return {};
}

QString classLabel(int id, int nc, const QStringList& names) {
  if (id >= 0 && id < names.size()) return names[id];
  if (nc == 1 && id == 0) return QStringLiteral("part");
  return QString::number(id);
}

/** 解析 YOLOv8/11 检测头或 [N,6] 后处理输出，坐标为 letterbox 输入像素。 */
QVector<YoloItem> decodeYoloOutput(const float* data, const std::vector<int64_t>& shape,
                                   double confThr, const Letterbox& lb, int srcW, int srcH,
                                   const QStringList& names) {
  QVector<YoloItem> items;
  if (!data || shape.empty()) return items;

  // 去掉前导 batch=1。
  std::vector<int64_t> dims;
  size_t start = 0;
  if (shape.size() == 3 && shape[0] == 1) start = 1;
  else if (shape.size() == 2) start = 0;
  else if (shape.size() == 1) return items;
  else if (shape.size() == 3) start = 0;
  else return items;
  for (size_t i = start; i < shape.size(); ++i) dims.push_back(shape[i]);
  if (dims.size() != 2) return items;
  const int a = int(dims[0]);
  const int b = int(dims[1]);
  if (a <= 0 || b <= 0) return items;

  const auto pushBox = [&](double x1, double y1, double x2, double y2, double score, int cls,
                        int nc) {
    if (score < confThr) return;
    const QRectF box = unletterbox(lb, x1, y1, x2, y2, srcW, srcH);
    if (box.width() < 1 || box.height() < 1) return;
    YoloItem it;
    it.classId = cls;
    it.label = classLabel(cls, nc, names);
    it.confidence = score;
    it.bbox = box;
    it.center = box.center();
    it.areaPixels = int(std::lround(box.width() * box.height()));
    items.push_back(it);
  };

  // [C, N]：C=4+nc（cx,cy,w,h,scores）或少见的 6 列转置。
  auto decodeCN = [&](int c, int n, bool channelMajor) {
    auto at = [&](int ci, int ni) -> float {
      return channelMajor ? data[ci * n + ni] : data[ni * c + ci];
    };
    if (c < 5) return;
    const int nc = c - 4;
    for (int i = 0; i < n; ++i) {
      const double cx = at(0, i);
      const double cy = at(1, i);
      const double w = at(2, i);
      const double h = at(3, i);
      int best = 0;
      double score = at(4, i);
      for (int k = 1; k < nc; ++k) {
        const double s = at(4 + k, i);
        if (s > score) {
          score = s;
          best = k;
        }
      }
      pushBox(cx - w * 0.5, cy - h * 0.5, cx + w * 0.5, cy + h * 0.5, score, best, nc);
    }
  };

  // 优先按 YOLOv8 常见的 [4+nc, anchors]；若另一维更像通道数则转置理解。
  if (a >= 5 && a <= 512 && b >= 1) {
    decodeCN(a, b, true);
  } else if (b >= 5 && b <= 512 && a >= 1) {
    decodeCN(b, a, false);
  }
  return items;
}

struct OrtTensorCopy {
  std::vector<int64_t> dims;
  std::vector<float> data;
};

/** 去掉单一前导 batch=1，保留 nm=1 的原型维（勿把 [1,1,H,W] 挤成 [H,W]）。 */
std::vector<int64_t> squeezeLeadingOnes(const std::vector<int64_t>& shape) {
  std::vector<int64_t> d = shape;
  if (d.size() > 1 && d[0] == 1) d.erase(d.begin());
  return d;
}

/** 判断是否为分割原型张量 [nm, mh, mw]（可带 batch=1）。 */
bool asProto(const OrtTensorCopy& t, int* nm, int* mh, int* mw) {
  const auto d = squeezeLeadingOnes(t.dims);
  if (d.size() != 3) return false;
  if (d[0] < 1 || d[0] > 128 || d[1] < 8 || d[2] < 8) return false;
  if (nm) *nm = int(d[0]);
  if (mh) *mh = int(d[1]);
  if (mw) *mw = int(d[2]);
  return true;
}

/** 判断是否为 [C, N] 或 [N, C] 检测/分割头。 */
bool asPreds(const OrtTensorCopy& t, int* a, int* b) {
  const auto d = squeezeLeadingOnes(t.dims);
  if (d.size() != 2) return false;
  if (d[0] <= 0 || d[1] <= 0) return false;
  if (a) *a = int(d[0]);
  if (b) *b = int(d[1]);
  return true;
}

float sigmoidf(float x) {
  if (x > 20.f) return 1.f;
  if (x < -20.f) return 0.f;
  return 1.f / (1.f + std::exp(-x));
}

/**
 * 从二值掩膜填写面积、质心、外接框与外/孔轮廓（4 连通）。
 * 若已有有效 bbox，则只扫描该框（外扩 1px）。
 */
void fillItemFromMask(YoloItem& it, const QVector<uchar>& fg, int w, int h) {
  int x0 = 0, y0 = 0, x1 = w, y1 = h;
  if (it.bbox.width() >= 1 && it.bbox.height() >= 1) {
    x0 = std::max(0, int(std::floor(it.bbox.left())) - 1);
    y0 = std::max(0, int(std::floor(it.bbox.top())) - 1);
    x1 = std::min(w, int(std::ceil(it.bbox.right())) + 1);
    y1 = std::min(h, int(std::ceil(it.bbox.bottom())) + 1);
  }
  int area = 0;
  qint64 sumX = 0, sumY = 0;
  int minX = w, minY = h, maxX = -1, maxY = -1;
  QPoint seed;
  for (int y = y0; y < y1; ++y) {
    for (int x = x0; x < x1; ++x) {
      if (!fg[y * w + x]) continue;
      if (area == 0) seed = QPoint(x, y);
      ++area;
      sumX += x;
      sumY += y;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  it.areaPixels = area;
  if (area <= 0) return;
  it.center = QPointF(double(sumX) / double(area) + 0.5, double(sumY) / double(area) + 0.5);
  it.bbox = QRectF(minX, minY, maxX - minX + 1, maxY - minY + 1);
  const QRect br = it.bbox.toRect();
  const int pad = 1;
  const int mw = br.width() + pad * 2;
  const int mh = br.height() + pad * 2;
  QVector<uchar> local(mw * mh, 0);
  for (int yy = 0; yy < br.height(); ++yy) {
    for (int xx = 0; xx < br.width(); ++xx) {
      const int gx = br.x() + xx;
      const int gy = br.y() + yy;
      if (gx >= 0 && gy >= 0 && gx < w && gy < h && fg[gy * w + gx])
        local[(yy + pad) * mw + (xx + pad)] = 1;
    }
  }
  QVector<uchar> bg(mw * mh, 0);
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
  for (int i = 0; i < mw * mh; ++i)
    if (!local[i] && !bg[i]) hole[i] = 1;
  const QPoint outerStart(seed.x() - br.x() + pad, seed.y() - br.y() + pad);
  // Local 4-connected outline (same left-hand walk as the software path).
  const int dx[4] = {1, 0, -1, 0};
  const int dy[4] = {0, 1, 0, -1};
  auto trace = [&](const QVector<uchar>& m, QPoint start) -> QVector<QPoint> {
    auto on = [&](int x, int y) -> bool {
      return x >= 0 && y >= 0 && x < mw && y < mh && m[y * mw + x];
    };
    if (!on(start.x(), start.y())) return {};
    int dir = 0;
    for (int d = 0; d < 4; ++d) {
      if (!on(start.x() + dx[d], start.y() + dy[d])) {
        dir = (d + 1) % 4;
        break;
      }
    }
    QVector<QPoint> pts;
    int x = start.x(), y = start.y();
    const int sx = x, sy = y, sd = dir;
    for (int iter = 0; iter < mw * mh * 4; ++iter) {
      pts.push_back(QPoint(x, y));
      int nd = (dir + 3) % 4;
      bool moved = false;
      for (int k = 0; k < 4; ++k) {
        const int d = (nd + k) % 4;
        const int nx = x + dx[d];
        const int ny = y + dy[d];
        if (on(nx, ny)) {
          x = nx;
          y = ny;
          dir = d;
          moved = true;
          break;
        }
      }
      if (!moved) break;
      if (x == sx && y == sy && dir == sd && pts.size() > 1) break;
      if (pts.size() >= 50000) break;
    }
    if (pts.size() >= 2 && pts.first() == pts.last()) pts.pop_back();
    return pts;
  };
  QVector<QPoint> outer = trace(local, outerStart);
  for (QPoint& pt : outer) pt += QPoint(br.x() - pad, br.y() - pad);
  if (!outer.isEmpty()) {
    it.contours.push_back(outer);
    it.contourIsHole.push_back(false);
  }
  QVector<int> hlab(mw * mh, 0);
  int hid = 0;
  const int qx[4] = {1, -1, 0, 0};
  const int qy[4] = {0, 0, 1, -1};
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
      QVector<QPoint> hc = trace(hole, hseed);
      for (QPoint& pt : hc) pt += QPoint(br.x() - pad, br.y() - pad);
      if (!hc.isEmpty()) {
        it.contours.push_back(hc);
        it.contourIsHole.push_back(true);
      }
    }
  }
}

}  // namespace

bool onnxRuntimeAvailable() { return ortApi() != nullptr; }

bool tryYoloOnnxDetect(const QImage& work, const QString& weightPath,
                       const QVariantMap& params, int imageSize,
                       YoloResult* out, QString* error) {
  if (out) *out = YoloResult{};
  const OrtApi* api = ortApi();
  if (!api) {
    if (error) *error = QStringLiteral("未找到 ONNX Runtime（可运行 scripts/install-onnxruntime-user.sh）");
    return false;
  }
  if (work.isNull()) {
    if (error) *error = QStringLiteral("输入图像为空");
    return false;
  }

  try {
    OrtEnv* env = nullptr;
    checkOrt(api, api->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "sieans-yolo", &env), "CreateEnv");
    OrtSessionOptions* opts = nullptr;
    checkOrt(api, api->CreateSessionOptions(&opts), "CreateSessionOptions");
    checkOrt(api, api->SetIntraOpNumThreads(opts, 1), "SetIntraOpNumThreads");
    OrtSession* session = nullptr;
    const QByteArray pathUtf8 = QFileInfo(weightPath).absoluteFilePath().toUtf8();
    if (pathUtf8.isEmpty() || !QFileInfo::exists(weightPath)) {
      api->ReleaseSessionOptions(opts);
      api->ReleaseEnv(env);
      if (error) *error = QStringLiteral("未指定本地 ONNX 权重");
      return false;
    }
    checkOrt(api, api->CreateSession(env, pathUtf8.constData(), opts, &session), "CreateSession");

    OrtAllocator* allocator = nullptr;
    checkOrt(api, api->GetAllocatorWithDefaultOptions(&allocator), "GetAllocator");

    size_t inCount = 0, outCount = 0;
    checkOrt(api, api->SessionGetInputCount(session, &inCount), "InputCount");
    checkOrt(api, api->SessionGetOutputCount(session, &outCount), "OutputCount");
    if (inCount < 1 || outCount < 1) {
      api->ReleaseSession(session);
      api->ReleaseSessionOptions(opts);
      api->ReleaseEnv(env);
      if (error) *error = QStringLiteral("ONNX 模型缺少输入或输出");
      return false;
    }

    char* inName = nullptr;
    char* outName = nullptr;
    checkOrt(api, api->SessionGetInputName(session, 0, allocator, &inName), "InputName");
    checkOrt(api, api->SessionGetOutputName(session, 0, allocator, &outName), "OutputName");

    OrtTypeInfo* tinfo = nullptr;
    checkOrt(api, api->SessionGetInputTypeInfo(session, 0, &tinfo), "InputTypeInfo");
    const OrtTensorTypeAndShapeInfo* tshape = nullptr;
    checkOrt(api, api->CastTypeInfoToTensorInfo(tinfo, &tshape), "CastTypeInfo");
    size_t dimCount = 0;
    checkOrt(api, api->GetDimensionsCount(tshape, &dimCount), "DimCount");
    std::vector<int64_t> inDims(dimCount, 0);
    checkOrt(api, api->GetDimensions(tshape, inDims.data(), dimCount), "GetDimensions");
    api->ReleaseTypeInfo(tinfo);

    int inputSize = imageSize > 0 ? imageSize : 640;
    // 静态方形输入优先采用模型维度，避免把 64 的烟测模型强行拉到 640。
    if (inDims.size() == 4) {
      const int64_t d2 = inDims[2];
      const int64_t d3 = inDims[3];
      if (d2 > 0 && d3 > 0 && d2 == d3) inputSize = int(d2);
      else if (d2 > 0 && d3 < 0) inputSize = int(d2);
      else if (d3 > 0 && d2 < 0) inputSize = int(d3);
    }
    const Letterbox lb = makeLetterbox(work.width(), work.height(), inputSize);
    std::vector<float> tensor = preprocessNchw(work, lb);
    std::vector<int64_t> feedDims = {1, 3, inputSize, inputSize};

    OrtMemoryInfo* mem = nullptr;
    checkOrt(api, api->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &mem),
             "CreateCpuMemoryInfo");
    OrtValue* inputVal = nullptr;
    checkOrt(api,
             api->CreateTensorWithDataAsOrtValue(mem, tensor.data(),
                                                 tensor.size() * sizeof(float), feedDims.data(),
                                                 feedDims.size(), ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,
                                                 &inputVal),
             "CreateTensor");

    const char* inNames[] = {inName};
    const char* outNames[] = {outName};
    OrtValue* outputVal = nullptr;
    checkOrt(api, api->Run(session, nullptr, inNames, &inputVal, 1, outNames, 1, &outputVal),
             "Run");

    OrtTensorTypeAndShapeInfo* oinfo = nullptr;
    checkOrt(api, api->GetTensorTypeAndShape(outputVal, &oinfo), "GetTensorTypeAndShape");
    size_t odCount = 0;
    checkOrt(api, api->GetDimensionsCount(oinfo, &odCount), "OutDimCount");
    std::vector<int64_t> outDims(odCount, 0);
    checkOrt(api, api->GetDimensions(oinfo, outDims.data(), odCount), "OutDims");
    ONNXTensorElementDataType etype;
    checkOrt(api, api->GetTensorElementType(oinfo, &etype), "ElemType");
    api->ReleaseTensorTypeAndShapeInfo(oinfo);
    if (etype != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) {
      api->ReleaseValue(outputVal);
      api->ReleaseValue(inputVal);
      api->ReleaseMemoryInfo(mem);
      if (inName) allocator->Free(allocator, inName);
      if (outName) allocator->Free(allocator, outName);
      api->ReleaseSession(session);
      api->ReleaseSessionOptions(opts);
      api->ReleaseEnv(env);
      if (error) *error = QStringLiteral("ONNX 输出不是 float32，无法解析为检测框");
      return false;
    }
    void* raw = nullptr;
    checkOrt(api, api->GetTensorMutableData(outputVal, &raw), "GetTensorMutableData");

    const double confThr = params.value(QStringLiteral("confidence"), 0.25).toDouble();
    QStringList names = loadLabelFile(QString::fromUtf8(pathUtf8));
    const QVariant labVar = params.value(QStringLiteral("labels"));
    if (labVar.typeId() == QMetaType::QStringList || labVar.typeId() == QMetaType::QVariantList) {
      names.clear();
      for (const QVariant& v : labVar.toList()) names << v.toString();
    } else if (!labVar.toString().trimmed().isEmpty()) {
      names = labVar.toString().split(QLatin1Char(','), Qt::SkipEmptyParts);
      for (QString& s : names) s = s.trimmed();
    }

    const QVector<YoloItem> items = decodeYoloOutput(
        static_cast<const float*>(raw), outDims, confThr, lb, work.width(), work.height(), names);

    if (out) {
      out->ok = true;
      out->backend = QStringLiteral("onnx");
      out->device = QStringLiteral("cpu");
      out->items = items;
      out->rawCount = items.size();
      out->count = items.size();
    }

    api->ReleaseValue(outputVal);
    api->ReleaseValue(inputVal);
    api->ReleaseMemoryInfo(mem);
    if (inName) allocator->Free(allocator, inName);
    if (outName) allocator->Free(allocator, outName);
    api->ReleaseSession(session);
    api->ReleaseSessionOptions(opts);
    api->ReleaseEnv(env);
    return true;
  } catch (const std::exception& ex) {
    if (error) *error = QString::fromUtf8(ex.what());
    return false;
  }
}

bool tryYoloOnnxSegment(const QImage& work, const QString& weightPath,
                        const QVariantMap& params, int imageSize,
                        YoloResult* out, QString* error) {
  if (out) *out = YoloResult{};
  const OrtApi* api = ortApi();
  if (!api) {
    if (error) *error = QStringLiteral("未找到 ONNX Runtime（可运行 scripts/install-onnxruntime-user.sh）");
    return false;
  }
  if (work.isNull()) {
    if (error) *error = QStringLiteral("输入图像为空");
    return false;
  }

  try {
    OrtEnv* env = nullptr;
    checkOrt(api, api->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "sieans-yolo-seg", &env), "CreateEnv");
    OrtSessionOptions* opts = nullptr;
    checkOrt(api, api->CreateSessionOptions(&opts), "CreateSessionOptions");
    checkOrt(api, api->SetIntraOpNumThreads(opts, 1), "SetIntraOpNumThreads");
    OrtSession* session = nullptr;
    const QByteArray pathUtf8 = QFileInfo(weightPath).absoluteFilePath().toUtf8();
    if (pathUtf8.isEmpty() || !QFileInfo::exists(weightPath)) {
      api->ReleaseSessionOptions(opts);
      api->ReleaseEnv(env);
      if (error) *error = QStringLiteral("未指定本地 ONNX 权重");
      return false;
    }
    checkOrt(api, api->CreateSession(env, pathUtf8.constData(), opts, &session), "CreateSession");

    OrtAllocator* allocator = nullptr;
    checkOrt(api, api->GetAllocatorWithDefaultOptions(&allocator), "GetAllocator");

    size_t inCount = 0, outCount = 0;
    checkOrt(api, api->SessionGetInputCount(session, &inCount), "InputCount");
    checkOrt(api, api->SessionGetOutputCount(session, &outCount), "OutputCount");
    if (inCount < 1 || outCount < 2) {
      api->ReleaseSession(session);
      api->ReleaseSessionOptions(opts);
      api->ReleaseEnv(env);
      if (error) *error = QStringLiteral("ONNX 分割模型需要至少两个输出（preds + proto）");
      return false;
    }

    char* inName = nullptr;
    checkOrt(api, api->SessionGetInputName(session, 0, allocator, &inName), "InputName");
    std::vector<char*> outNamePtrs(outCount, nullptr);
    std::vector<const char*> outNames(outCount, nullptr);
    for (size_t i = 0; i < outCount; ++i) {
      checkOrt(api, api->SessionGetOutputName(session, i, allocator, &outNamePtrs[i]), "OutputName");
      outNames[i] = outNamePtrs[i];
    }

    OrtTypeInfo* tinfo = nullptr;
    checkOrt(api, api->SessionGetInputTypeInfo(session, 0, &tinfo), "InputTypeInfo");
    const OrtTensorTypeAndShapeInfo* tshape = nullptr;
    checkOrt(api, api->CastTypeInfoToTensorInfo(tinfo, &tshape), "CastTypeInfo");
    size_t dimCount = 0;
    checkOrt(api, api->GetDimensionsCount(tshape, &dimCount), "DimCount");
    std::vector<int64_t> inDims(dimCount, 0);
    checkOrt(api, api->GetDimensions(tshape, inDims.data(), dimCount), "GetDimensions");
    api->ReleaseTypeInfo(tinfo);

    int inputSize = imageSize > 0 ? imageSize : 640;
    if (inDims.size() == 4) {
      const int64_t d2 = inDims[2];
      const int64_t d3 = inDims[3];
      if (d2 > 0 && d3 > 0 && d2 == d3) inputSize = int(d2);
      else if (d2 > 0 && d3 < 0) inputSize = int(d2);
      else if (d3 > 0 && d2 < 0) inputSize = int(d3);
    }
    const Letterbox lb = makeLetterbox(work.width(), work.height(), inputSize);
    std::vector<float> tensor = preprocessNchw(work, lb);
    std::vector<int64_t> feedDims = {1, 3, inputSize, inputSize};

    OrtMemoryInfo* mem = nullptr;
    checkOrt(api, api->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &mem),
             "CreateCpuMemoryInfo");
    OrtValue* inputVal = nullptr;
    checkOrt(api,
             api->CreateTensorWithDataAsOrtValue(mem, tensor.data(),
                                                 tensor.size() * sizeof(float), feedDims.data(),
                                                 feedDims.size(), ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,
                                                 &inputVal),
             "CreateTensor");

    const char* inNames[] = {inName};
    std::vector<OrtValue*> outputVals(outCount, nullptr);
    checkOrt(api,
             api->Run(session, nullptr, inNames, &inputVal, 1, outNames.data(), outCount,
                      outputVals.data()),
             "Run");

    std::vector<OrtTensorCopy> copies(outCount);
    bool typeOk = true;
    for (size_t i = 0; i < outCount; ++i) {
      OrtTensorTypeAndShapeInfo* oinfo = nullptr;
      checkOrt(api, api->GetTensorTypeAndShape(outputVals[i], &oinfo), "GetTensorTypeAndShape");
      size_t odCount = 0;
      checkOrt(api, api->GetDimensionsCount(oinfo, &odCount), "OutDimCount");
      copies[i].dims.assign(odCount, 0);
      checkOrt(api, api->GetDimensions(oinfo, copies[i].dims.data(), odCount), "OutDims");
      ONNXTensorElementDataType etype;
      checkOrt(api, api->GetTensorElementType(oinfo, &etype), "ElemType");
      size_t nElem = 0;
      checkOrt(api, api->GetTensorShapeElementCount(oinfo, &nElem), "ElemCount");
      api->ReleaseTensorTypeAndShapeInfo(oinfo);
      if (etype != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) {
        typeOk = false;
        break;
      }
      void* raw = nullptr;
      checkOrt(api, api->GetTensorMutableData(outputVals[i], &raw), "GetTensorMutableData");
      const float* fp = static_cast<const float*>(raw);
      copies[i].data.assign(fp, fp + nElem);
    }

    auto releaseAll = [&]() {
      for (OrtValue* v : outputVals)
        if (v) api->ReleaseValue(v);
      api->ReleaseValue(inputVal);
      api->ReleaseMemoryInfo(mem);
      if (inName) allocator->Free(allocator, inName);
      for (char* n : outNamePtrs)
        if (n) allocator->Free(allocator, n);
      api->ReleaseSession(session);
      api->ReleaseSessionOptions(opts);
      api->ReleaseEnv(env);
    };

    if (!typeOk) {
      releaseAll();
      if (error) *error = QStringLiteral("ONNX 分割输出不是 float32");
      return false;
    }

    int protoIdx = -1, predIdx = -1;
    int nm = 0, mh = 0, mw = 0;
    int pa = 0, pb = 0;
    for (size_t i = 0; i < copies.size(); ++i) {
      if (protoIdx < 0 && asProto(copies[i], &nm, &mh, &mw)) protoIdx = int(i);
      else if (predIdx < 0 && asPreds(copies[i], &pa, &pb)) predIdx = int(i);
    }
    if (protoIdx < 0 || predIdx < 0 || nm < 1) {
      releaseAll();
      if (error) *error = QStringLiteral("无法识别 YOLO-seg 的 preds + proto 输出布局");
      return false;
    }

    const OrtTensorCopy& preds = copies[size_t(predIdx)];
    const OrtTensorCopy& proto = copies[size_t(protoIdx)];
    // Prefer the dim that equals 4+nc+nm with nc>=1, or 4+nm with nc inferred.
    int c = 0, nAnch = 0;
    bool cMajor = true;
    if (pa >= 4 + nm && pa <= 4 + nm + 512 && pb >= 1) {
      c = pa;
      nAnch = pb;
      cMajor = true;
    } else if (pb >= 4 + nm && pb <= 4 + nm + 512 && pa >= 1) {
      c = pb;
      nAnch = pa;
      cMajor = false;
    } else {
      releaseAll();
      if (error)
        *error = QStringLiteral("preds 通道数与 proto 的 nm=%1 不匹配（%2×%3）")
                     .arg(nm)
                     .arg(pa)
                     .arg(pb);
      return false;
    }
    const int nc = c - 4 - nm;
    if (nc < 1) {
      releaseAll();
      if (error) *error = QStringLiteral("preds 通道不足以同时容纳类别与掩膜系数");
      return false;
    }

    const double confThr = params.value(QStringLiteral("confidence"), 0.25).toDouble();
    QStringList names = loadLabelFile(QString::fromUtf8(pathUtf8));
    const QVariant labVar = params.value(QStringLiteral("labels"));
    if (labVar.typeId() == QMetaType::QStringList || labVar.typeId() == QMetaType::QVariantList) {
      names.clear();
      for (const QVariant& v : labVar.toList()) names << v.toString();
    } else if (!labVar.toString().trimmed().isEmpty()) {
      names = labVar.toString().split(QLatin1Char(','), Qt::SkipEmptyParts);
      for (QString& s : names) s = s.trimmed();
    }

    auto at = [&](int ci, int ni) -> float {
      return cMajor ? preds.data[size_t(ci) * size_t(nAnch) + size_t(ni)]
                    : preds.data[size_t(ni) * size_t(c) + size_t(ci)];
    };

    const int srcW = work.width();
    const int srcH = work.height();
    QVector<YoloItem> items;
    QVector<uchar> unionFg(srcW * srcH, 0);
    const float* protoData = proto.data.data();
    const int plane = mh * mw;

    for (int i = 0; i < nAnch; ++i) {
      const double cx = at(0, i);
      const double cy = at(1, i);
      const double bw = at(2, i);
      const double bh = at(3, i);
      int best = 0;
      double score = at(4, i);
      for (int k = 1; k < nc; ++k) {
        const double s = at(4 + k, i);
        if (s > score) {
          score = s;
          best = k;
        }
      }
      if (score < confThr) continue;
      const QRectF box = unletterbox(lb, cx - bw * 0.5, cy - bh * 0.5, cx + bw * 0.5,
                                    cy + bh * 0.5, srcW, srcH);
      if (box.width() < 1 || box.height() < 1) continue;

      std::vector<float> coeff(size_t(nm), 0.f);
      for (int k = 0; k < nm; ++k) coeff[size_t(k)] = at(4 + nc + k, i);

      YoloItem it;
      it.classId = best;
      it.label = classLabel(best, nc, names);
      it.confidence = score;
      it.bbox = box;

      const int x0 = std::max(0, int(std::floor(box.left())));
      const int y0 = std::max(0, int(std::floor(box.top())));
      const int x1 = std::min(srcW, int(std::ceil(box.right())));
      const int y1 = std::min(srcH, int(std::ceil(box.bottom())));
      QVector<uchar> fg(srcW * srcH, 0);
      for (int y = y0; y < y1; ++y) {
        for (int x = x0; x < x1; ++x) {
          const double lbx = x * lb.scale + lb.padX;
          const double lby = y * lb.scale + lb.padY;
          const double px = lbx * double(mw) / double(lb.input);
          const double py = lby * double(mh) / double(lb.input);
          const int ix = int(std::floor(px));
          const int iy = int(std::floor(py));
          if (ix < 0 || iy < 0 || ix >= mw || iy >= mh) continue;
          float acc = 0.f;
          const int base = iy * mw + ix;
          for (int k = 0; k < nm; ++k)
            acc += coeff[size_t(k)] * protoData[k * plane + base];
          if (sigmoidf(acc) > 0.5f) {
            fg[y * srcW + x] = 1;
            unionFg[y * srcW + x] = 1;
          }
        }
      }
      fillItemFromMask(it, fg, srcW, srcH);
      items.push_back(it);
    }

    int unionPx = 0;
    for (uchar v : unionFg)
      if (v) ++unionPx;

    if (out) {
      out->ok = true;
      out->backend = QStringLiteral("onnx");
      out->device = QStringLiteral("cpu");
      out->items = items;
      out->rawCount = items.size();
      out->count = items.size();
      out->unionAreaPixels = unionPx;
    }

    releaseAll();
    return true;
  } catch (const std::exception& ex) {
    if (error) *error = QString::fromUtf8(ex.what());
    return false;
  }
}

#else  // !SIEANS_HAS_ONNXRUNTIME

bool onnxRuntimeAvailable() { return false; }

bool tryYoloOnnxDetect(const QImage&, const QString&, const QVariantMap&, int, YoloResult*,
                       QString* error) {
  if (error)
    *error = QStringLiteral("本次构建未包含 ONNX Runtime 头文件，检测回退 software");
  return false;
}

bool tryYoloOnnxSegment(const QImage&, const QString&, const QVariantMap&, int, YoloResult*,
                        QString* error) {
  if (error)
    *error = QStringLiteral("本次构建未包含 ONNX Runtime 头文件，分割回退 software");
  return false;
}

#endif

}  // namespace sieans_qt
