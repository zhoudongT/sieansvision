#include "ColorOp.hpp"

#include <QColor>
#include <QRect>
#include <QtGlobal>

#include <algorithm>
#include <cmath>

namespace sieans_qt {
namespace {

/** 把输入转成 RGB888；空图返回空。 */
QImage toRgb888(const QImage& src) {
  if (src.isNull()) return {};
  return src.convertToFormat(QImage::Format_RGB888);
}

/** RGB → 打包 HSV，H 映射 0–255 对应 0–360°，S/V 为 0–255。 */
void rgbToHsv8(int r, int g, int b, int& h8, int& s, int& v) {
  const int maxc = std::max(r, std::max(g, b));
  const int minc = std::min(r, std::min(g, b));
  v = maxc;
  const int d = maxc - minc;
  if (maxc == 0 || d == 0) {
    s = 0;
    h8 = 0;
    return;
  }
  s = (d * 255 + maxc / 2) / maxc;
  double hd = 0.0;
  if (maxc == r)
    hd = 60.0 * static_cast<double>(g - b) / d;
  else if (maxc == g)
    hd = 60.0 * static_cast<double>(b - r) / d + 120.0;
  else
    hd = 60.0 * static_cast<double>(r - g) / d + 240.0;
  if (hd < 0.0) hd += 360.0;
  if (hd >= 360.0) hd -= 360.0;
  h8 = qBound(0, qRound(hd * 255.0 / 360.0), 255);
}

/** 打包 HSV → RGB。h8=255 视作 360°，与 0° 同为红。 */
void hsv8ToRgb(int h8, int s, int v, int& r, int& g, int& b) {
  if (s <= 0) {
    r = g = b = v;
    return;
  }
  const double hh = (h8 >= 255 ? 0.0 : static_cast<double>(h8) * 360.0 / 255.0) / 60.0;
  const double vf = static_cast<double>(v) / 255.0;
  const double sf = static_cast<double>(s) / 255.0;
  const double c = vf * sf;
  const double x = c * (1.0 - std::fabs(std::fmod(hh, 2.0) - 1.0));
  const double m = vf - c;
  double rf = 0, gf = 0, bf = 0;
  if (hh < 1.0) {
    rf = c;
    gf = x;
  } else if (hh < 2.0) {
    rf = x;
    gf = c;
  } else if (hh < 3.0) {
    gf = c;
    bf = x;
  } else if (hh < 4.0) {
    gf = x;
    bf = c;
  } else if (hh < 5.0) {
    rf = x;
    bf = c;
  } else {
    rf = c;
    bf = x;
  }
  r = qBound(0, qRound((rf + m) * 255.0), 255);
  g = qBound(0, qRound((gf + m) * 255.0), 255);
  b = qBound(0, qRound((bf + m) * 255.0), 255);
}

/** 色相是否落入 [lo,hi]；lo>hi 时按 0–255 环绕（用于红色）。 */
bool hueInRange(int h, int lo, int hi) {
  if (lo <= hi) return h >= lo && h <= hi;
  return h >= lo || h <= hi;
}

/** 读取 RGB888 像素。 */
void readRgb(const QImage& img, int x, int y, int& r, int& g, int& b) {
  const uchar* p = img.constScanLine(y) + x * 3;
  r = p[0];
  g = p[1];
  b = p[2];
}

/** 写入 RGB888 像素。 */
void writeRgb(QImage& img, int x, int y, int r, int g, int b) {
  uchar* p = img.scanLine(y) + x * 3;
  p[0] = static_cast<uchar>(r);
  p[1] = static_cast<uchar>(g);
  p[2] = static_cast<uchar>(b);
}

/** 在测试图上填实心矩形。 */
void fillRgbRect(QImage& img, int x0, int y0, int x1, int y1, int r, int g, int b) {
  for (int y = y0; y <= y1; ++y) {
    if (y < 0 || y >= img.height()) continue;
    for (int x = x0; x <= x1; ++x) {
      if (x < 0 || x >= img.width()) continue;
      writeRgb(img, x, y, r, g, b);
    }
  }
}

}  // namespace

ColorResult runColorOp(const QImage& src, const QVariantMap& params) {
  ColorResult r;
  if (src.isNull() || src.width() <= 0 || src.height() <= 0) {
    r.error = QStringLiteral("颜色处理需要非空输入图像");
    return r;
  }
  QString method = params.value(QStringLiteral("method"), QStringLiteral("convert")).toString().trimmed().toLower();
  if (method == QLatin1String("rgb2hsv") || method == QLatin1String("hsv") ||
      method == QLatin1String("hsv2rgb") || method == QLatin1String("to_hsv") ||
      method == QLatin1String("to_rgb"))
    method = QStringLiteral("convert");
  if (method == QLatin1String("extract") || method == QLatin1String("extract_channel"))
    method = QStringLiteral("channel");
  if (method == QLatin1String("color_threshold") || method == QLatin1String("inrange") ||
      method == QLatin1String("in_range"))
    method = QStringLiteral("threshold");
  if (method != QLatin1String("channel") && method != QLatin1String("threshold"))
    method = QStringLiteral("convert");
  r.method = method;

  QString space = params.value(QStringLiteral("space"), QStringLiteral("hsv")).toString().trimmed().toLower();
  if (space != QLatin1String("rgb")) space = QStringLiteral("hsv");
  r.space = space;
  QString channel = params.value(QStringLiteral("channel"), QStringLiteral("r")).toString().trimmed().toLower();
  if (channel == QLatin1String("red")) channel = QStringLiteral("r");
  if (channel == QLatin1String("green")) channel = QStringLiteral("g");
  if (channel == QLatin1String("blue")) channel = QStringLiteral("b");
  if (channel == QLatin1String("hue")) channel = QStringLiteral("h");
  if (channel == QLatin1String("sat") || channel == QLatin1String("saturation")) channel = QStringLiteral("s");
  if (channel == QLatin1String("val") || channel == QLatin1String("value") || channel == QLatin1String("brightness"))
    channel = QStringLiteral("v");
  r.channel = channel;

  const QImage rgb = toRgb888(src);
  const int w = rgb.width();
  const int h = rgb.height();
  int roiX = params.value(QStringLiteral("roiX"), 0).toInt();
  int roiY = params.value(QStringLiteral("roiY"), 0).toInt();
  int roiW = params.value(QStringLiteral("roiW"), 0).toInt();
  int roiH = params.value(QStringLiteral("roiH"), 0).toInt();
  if (roiW <= 0 || roiH <= 0) {
    roiX = 0;
    roiY = 0;
    roiW = w;
    roiH = h;
  }
  const QRect roi = QRect(roiX, roiY, roiW, roiH).intersected(QRect(0, 0, w, h));
  if (roi.isEmpty()) {
    r.error = QStringLiteral("颜色处理 ROI 与图像无交集");
    return r;
  }
  const bool invert = params.value(QStringLiteral("invert"), false).toBool();
  const int rMin = qBound(0, params.value(QStringLiteral("rMin"), 0).toInt(), 255);
  const int rMax = qBound(0, params.value(QStringLiteral("rMax"), 255).toInt(), 255);
  const int gMin = qBound(0, params.value(QStringLiteral("gMin"), 0).toInt(), 255);
  const int gMax = qBound(0, params.value(QStringLiteral("gMax"), 255).toInt(), 255);
  const int bMin = qBound(0, params.value(QStringLiteral("bMin"), 0).toInt(), 255);
  const int bMax = qBound(0, params.value(QStringLiteral("bMax"), 255).toInt(), 255);
  const int hMin = qBound(0, params.value(QStringLiteral("hMin"), 0).toInt(), 255);
  const int hMax = qBound(0, params.value(QStringLiteral("hMax"), 255).toInt(), 255);
  const int sMin = qBound(0, params.value(QStringLiteral("sMin"), 0).toInt(), 255);
  const int sMax = qBound(0, params.value(QStringLiteral("sMax"), 255).toInt(), 255);
  const int vMin = qBound(0, params.value(QStringLiteral("vMin"), 0).toInt(), 255);
  const int vMax = qBound(0, params.value(QStringLiteral("vMax"), 255).toInt(), 255);

  if (method == QLatin1String("convert")) {
    QImage out = rgb.copy();
    for (int y = roi.top(); y <= roi.bottom(); ++y) {
      for (int x = roi.left(); x <= roi.right(); ++x) {
        int pr, pg, pb;
        readRgb(rgb, x, y, pr, pg, pb);
        int a, b2, c;
        if (space == QLatin1String("hsv")) {
          rgbToHsv8(pr, pg, pb, a, b2, c);
        } else {
          hsv8ToRgb(pr, pg, pb, a, b2, c);
        }
        writeRgb(out, x, y, a, b2, c);
      }
    }
    r.image = out;
    r.ok = true;
    r.note = QStringLiteral("颜色转换 %1").arg(space == QLatin1String("hsv")
                                                   ? QStringLiteral("RGB→HSV")
                                                   : QStringLiteral("HSV→RGB"));
    return r;
  }

  if (method == QLatin1String("channel")) {
    QImage out(w, h, QImage::Format_Grayscale8);
    out.fill(0);
    const bool fromHsv = (channel == QLatin1String("h") || channel == QLatin1String("s") ||
                          channel == QLatin1String("v"));
    if (!fromHsv && channel != QLatin1String("r") && channel != QLatin1String("g") &&
        channel != QLatin1String("b")) {
      r.error = QStringLiteral("通道提取仅支持 r/g/b/h/s/v");
      return r;
    }
    for (int y = roi.top(); y <= roi.bottom(); ++y) {
      uchar* row = out.scanLine(y);
      for (int x = roi.left(); x <= roi.right(); ++x) {
        int pr, pg, pb;
        readRgb(rgb, x, y, pr, pg, pb);
        int val = 0;
        if (fromHsv) {
          int hh, ss, vv;
          rgbToHsv8(pr, pg, pb, hh, ss, vv);
          val = (channel == QLatin1String("h") ? hh : channel == QLatin1String("s") ? ss : vv);
        } else if (channel == QLatin1String("r")) {
          val = pr;
        } else if (channel == QLatin1String("g")) {
          val = pg;
        } else {
          val = pb;
        }
        row[x] = static_cast<uchar>(val);
      }
    }
    r.image = out;
    r.ok = true;
    r.note = QStringLiteral("提取通道 %1").arg(channel);
    return r;
  }

  // method == threshold
  QImage out(w, h, QImage::Format_Grayscale8);
  out.fill(0);
  int fg = 0;
  const bool useHsv = (space == QLatin1String("hsv"));
  for (int y = roi.top(); y <= roi.bottom(); ++y) {
    uchar* row = out.scanLine(y);
    for (int x = roi.left(); x <= roi.right(); ++x) {
      int pr, pg, pb;
      readRgb(rgb, x, y, pr, pg, pb);
      bool on = false;
      if (useHsv) {
        int hh, ss, vv;
        rgbToHsv8(pr, pg, pb, hh, ss, vv);
        on = hueInRange(hh, hMin, hMax) && ss >= sMin && ss <= sMax && vv >= vMin && vv <= vMax;
      } else {
        on = pr >= rMin && pr <= rMax && pg >= gMin && pg <= gMax && pb >= bMin && pb <= bMax;
      }
      if (invert) on = !on;
      if (on) {
        row[x] = 255;
        ++fg;
      }
    }
  }
  r.fgCount = fg;
  r.image = out;
  r.ok = true;
  r.note = QStringLiteral("颜色阈值 %1，前景 %2 像素").arg(space).arg(fg);
  return r;
}

QStringList colorSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = {}) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const ColorResult empty = runColorOp(QImage(), {{QStringLiteral("method"), QStringLiteral("convert")}});
  check("empty-fail", !empty.ok && !empty.error.isEmpty(), empty.error);

  QImage patch(8, 8, QImage::Format_RGB888);
  auto put = [&](int x, int y, int r, int g, int b) { writeRgb(patch, x, y, r, g, b); };
  // 已知纯色与一个中间色，验证 RGB→HSV→RGB 往返。
  put(0, 0, 255, 0, 0);
  put(1, 0, 0, 255, 0);
  put(2, 0, 0, 0, 255);
  put(3, 0, 255, 255, 255);
  put(4, 0, 0, 0, 0);
  put(5, 0, 128, 64, 200);
  // 其余填灰，避免未初始化。
  for (int y = 0; y < 8; ++y)
    for (int x = 0; x < 8; ++x)
      if (!(y == 0 && x <= 5)) writeRgb(patch, x, y, 16, 16, 16);

  const ColorResult toHsv = runColorOp(patch, {{QStringLiteral("method"), QStringLiteral("convert")},
                                               {QStringLiteral("space"), QStringLiteral("hsv")}});
  check("rgb2hsv-ok", toHsv.ok && toHsv.method == QLatin1String("convert") &&
                          toHsv.space == QLatin1String("hsv"),
        toHsv.error);
  auto hsvPx = [&](int x, int y, int& h, int& s, int& v) {
    readRgb(toHsv.image, x, y, h, s, v);
  };
  int h, s, v;
  hsvPx(0, 0, h, s, v);
  check("red-h", h <= 8 || h >= 247, QStringLiteral("H=%1 S=%2 V=%3").arg(h).arg(s).arg(v));
  check("red-sv", s >= 250 && v >= 250, QStringLiteral("S=%1 V=%2").arg(s).arg(v));
  hsvPx(1, 0, h, s, v);
  // 120° → 120/360*255 ≈ 85
  check("green-h", std::abs(h - 85) <= 4, QStringLiteral("H=%1").arg(h));
  check("green-sv", s >= 250 && v >= 250, QStringLiteral("S=%1 V=%2").arg(s).arg(v));
  hsvPx(2, 0, h, s, v);
  // 240° → 170
  check("blue-h", std::abs(h - 170) <= 4, QStringLiteral("H=%1").arg(h));
  hsvPx(3, 0, h, s, v);
  check("white-s", s <= 2 && v >= 250, QStringLiteral("S=%1 V=%2").arg(s).arg(v));
  hsvPx(4, 0, h, s, v);
  check("black-v", v <= 2, QStringLiteral("V=%1").arg(v));

  const ColorResult back = runColorOp(toHsv.image, {{QStringLiteral("method"), QStringLiteral("convert")},
                                                    {QStringLiteral("space"), QStringLiteral("rgb")}});
  check("hsv2rgb-ok", back.ok, back.error);
  auto nearRgb = [&](const char* name, int x, int y, int er, int eg, int eb, int tol) {
    int r, g, b;
    readRgb(back.image, x, y, r, g, b);
    check(name, std::abs(r - er) <= tol && std::abs(g - eg) <= tol && std::abs(b - eb) <= tol,
          QStringLiteral("got=%1,%2,%3").arg(r).arg(g).arg(b));
  };
  nearRgb("roundtrip-red", 0, 0, 255, 0, 0, 2);
  nearRgb("roundtrip-green", 1, 0, 0, 255, 0, 2);
  nearRgb("roundtrip-blue", 2, 0, 0, 0, 255, 2);
  nearRgb("roundtrip-white", 3, 0, 255, 255, 255, 2);
  nearRgb("roundtrip-black", 4, 0, 0, 0, 0, 2);
  nearRgb("roundtrip-mid", 5, 0, 128, 64, 200, 3);

  QImage scene(80, 60, QImage::Format_RGB888);
  scene.fill(QColor(128, 128, 128));
  fillRgbRect(scene, 8, 8, 27, 27, 220, 30, 30);    // 红 20×20
  fillRgbRect(scene, 48, 8, 67, 27, 30, 30, 220);    // 蓝 20×20
  fillRgbRect(scene, 8, 36, 27, 51, 30, 200, 40);    // 绿

  const ColorResult chR = runColorOp(scene, {{QStringLiteral("method"), QStringLiteral("channel")},
                                             {QStringLiteral("channel"), QStringLiteral("r")}});
  check("channel-ok", chR.ok && chR.method == QLatin1String("channel") &&
                          chR.image.format() == QImage::Format_Grayscale8,
        chR.error);
  if (chR.ok) {
    check("channel-r-red", chR.image.constScanLine(10)[10] == 220,
          QStringLiteral("v=%1").arg(chR.image.constScanLine(10)[10]));
    check("channel-r-blue", chR.image.constScanLine(10)[50] == 30,
          QStringLiteral("v=%1").arg(chR.image.constScanLine(10)[50]));
  }
  const ColorResult chH = runColorOp(scene, {{QStringLiteral("method"), QStringLiteral("channel")},
                                             {QStringLiteral("channel"), QStringLiteral("h")}});
  check("channel-h-ok", chH.ok, chH.error);
  if (chH.ok) {
    const int hRed = chH.image.constScanLine(10)[10];
    const int hBlue = chH.image.constScanLine(10)[50];
    check("channel-h-red", hRed <= 10 || hRed >= 245, QStringLiteral("h=%1").arg(hRed));
    check("channel-h-blue", std::abs(hBlue - 170) <= 8, QStringLiteral("h=%1").arg(hBlue));
  }

  const ColorResult thrRed = runColorOp(
      scene, {{QStringLiteral("method"), QStringLiteral("threshold")},
              {QStringLiteral("space"), QStringLiteral("hsv")},
              {QStringLiteral("hMin"), 230},
              {QStringLiteral("hMax"), 20},
              {QStringLiteral("sMin"), 80},
              {QStringLiteral("sMax"), 255},
              {QStringLiteral("vMin"), 80},
              {QStringLiteral("vMax"), 255}});
  check("thr-ok", thrRed.ok && thrRed.method == QLatin1String("threshold"), thrRed.error);
  // 红块 20×20=400，环绕色相应只收红、不收蓝/绿。
  check("thr-red-count", thrRed.fgCount == 400, QStringLiteral("fg=%1").arg(thrRed.fgCount));
  if (thrRed.ok) {
    check("thr-red-on", thrRed.image.constScanLine(10)[10] == 255);
    check("thr-blue-off", thrRed.image.constScanLine(10)[50] == 0);
    check("thr-green-off", thrRed.image.constScanLine(40)[10] == 0);
    check("thr-gray-off", thrRed.image.constScanLine(5)[5] == 0);
  }

  const ColorResult thrRgb = runColorOp(
      scene, {{QStringLiteral("method"), QStringLiteral("threshold")},
              {QStringLiteral("space"), QStringLiteral("rgb")},
              {QStringLiteral("rMin"), 180},
              {QStringLiteral("rMax"), 255},
              {QStringLiteral("gMin"), 0},
              {QStringLiteral("gMax"), 80},
              {QStringLiteral("bMin"), 0},
              {QStringLiteral("bMax"), 80}});
  check("thr-rgb-count", thrRgb.ok && thrRgb.fgCount == 400, QStringLiteral("fg=%1").arg(thrRgb.fgCount));

  const ColorResult inv = runColorOp(
      scene, {{QStringLiteral("method"), QStringLiteral("threshold")},
              {QStringLiteral("space"), QStringLiteral("rgb")},
              {QStringLiteral("rMin"), 180},
              {QStringLiteral("rMax"), 255},
              {QStringLiteral("gMin"), 0},
              {QStringLiteral("gMax"), 80},
              {QStringLiteral("bMin"), 0},
              {QStringLiteral("bMax"), 80},
              {QStringLiteral("invert"), true}});
  check("thr-invert", inv.ok && inv.fgCount == (80 * 60 - 400),
        QStringLiteral("fg=%1").arg(inv.fgCount));

  QVariantMap roiP{{QStringLiteral("method"), QStringLiteral("threshold")},
                   {QStringLiteral("space"), QStringLiteral("rgb")},
                   {QStringLiteral("rMin"), 180},
                   {QStringLiteral("gMax"), 80},
                   {QStringLiteral("bMax"), 80},
                   {QStringLiteral("roiX"), 8},
                   {QStringLiteral("roiY"), 8},
                   {QStringLiteral("roiW"), 20},
                   {QStringLiteral("roiH"), 20}};
  const ColorResult roi = runColorOp(scene, roiP);
  check("thr-roi", roi.ok && roi.fgCount == 400, QStringLiteral("fg=%1").arg(roi.fgCount));

  const ColorResult badCh = runColorOp(scene, {{QStringLiteral("method"), QStringLiteral("channel")},
                                               {QStringLiteral("channel"), QStringLiteral("zzz")}});
  check("bad-channel", !badCh.ok && !badCh.error.isEmpty(), badCh.error);

  return fails;
}

}  // namespace sieans_qt
