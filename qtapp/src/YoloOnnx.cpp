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

#else  // !SIEANS_HAS_ONNXRUNTIME

bool onnxRuntimeAvailable() { return false; }

bool tryYoloOnnxDetect(const QImage&, const QString&, const QVariantMap&, int, YoloResult*,
                       QString* error) {
  if (error)
    *error = QStringLiteral("本次构建未包含 ONNX Runtime 头文件，检测回退 software");
  return false;
}

#endif

}  // namespace sieans_qt
