#include "sieans/barcode.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>
#include <unordered_map>

#include "ReadBarcode.h"

namespace sieans {
namespace {

ZXing::ImageFormat to_zxing_format(PixelFormat format) {
  switch (format) {
    case PixelFormat::Gray8:
      return ZXing::ImageFormat::Lum;
    case PixelFormat::BGR24:
      return ZXing::ImageFormat::BGR;
    case PixelFormat::RGB24:
      return ZXing::ImageFormat::RGB;
    case PixelFormat::BGRA32:
      return ZXing::ImageFormat::BGRX;
    case PixelFormat::RGBA32:
      return ZXing::ImageFormat::RGBX;
  }
  return ZXing::ImageFormat::Lum;
}

ZXing::BarcodeFormats parse_formats(const std::string& raw) {
  if (raw.empty() || raw == "all" || raw == "All" || raw == "*") {
    return ZXing::BarcodeFormat::Any;
  }
  static const std::unordered_map<std::string, ZXing::BarcodeFormat> alias = {
      {"qr", ZXing::BarcodeFormat::QRCode},
      {"qrcode", ZXing::BarcodeFormat::QRCode},
      {"qr_code", ZXing::BarcodeFormat::QRCode},
      {"datamatrix", ZXing::BarcodeFormat::DataMatrix},
      {"dm", ZXing::BarcodeFormat::DataMatrix},
      {"pdf417", ZXing::BarcodeFormat::PDF417},
      {"aztec", ZXing::BarcodeFormat::Aztec},
      {"code128", ZXing::BarcodeFormat::Code128},
      {"code39", ZXing::BarcodeFormat::Code39},
      {"ean13", ZXing::BarcodeFormat::EAN13},
      {"ean8", ZXing::BarcodeFormat::EAN8},
      {"upca", ZXing::BarcodeFormat::UPCA},
      {"upce", ZXing::BarcodeFormat::UPCE},
      {"matrix", ZXing::BarcodeFormat::MatrixCodes},
      {"allmatrix", ZXing::BarcodeFormat::MatrixCodes},
      {"linear", ZXing::BarcodeFormat::LinearCodes},
      {"alllinear", ZXing::BarcodeFormat::LinearCodes},
  };
  ZXing::BarcodeFormats out = ZXing::BarcodeFormat::None;
  std::string token;
  auto flush = [&]() {
    if (token.empty()) return;
    std::string key = token;
    std::transform(key.begin(), key.end(), key.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    auto it = alias.find(key);
    if (it != alias.end()) {
      out |= it->second;
    } else {
      auto fmt = ZXing::BarcodeFormatFromString(token);
      if (fmt != ZXing::BarcodeFormat::None) out |= fmt;
    }
    token.clear();
  };
  for (char c : raw) {
    if (c == ',' || c == ';' || c == '|' || c == ' ')
      flush();
    else
      token.push_back(c);
  }
  flush();
  return out == ZXing::BarcodeFormat::None ? ZXing::BarcodeFormat::Any : out;
}

void draw_line(uint8_t* bgr, int w, int h, int stride, int x0, int y0, int x1,
               int y1, uint8_t b, uint8_t g, uint8_t r) {
  int dx = std::abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
  int dy = -std::abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;
  for (;;) {
    if (x0 >= 0 && x0 < w && y0 >= 0 && y0 < h) {
      uint8_t* p = bgr + y0 * stride + x0 * 3;
      p[0] = b;
      p[1] = g;
      p[2] = r;
    }
    if (x0 == x1 && y0 == y1) break;
    int e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y0 += sy;
    }
  }
}

void put_pixel(uint8_t* bgr, int w, int h, int stride, int x, int y, uint8_t b,
               uint8_t g, uint8_t r) {
  if (x < 0 || y < 0 || x >= w || y >= h) return;
  uint8_t* p = bgr + y * stride + x * 3;
  p[0] = b;
  p[1] = g;
  p[2] = r;
}

void draw_char_mark(uint8_t* bgr, int w, int h, int stride, int x, int y,
                    uint8_t b, uint8_t g, uint8_t r) {
  for (int dy = 0; dy < 7; ++dy)
    for (int dx = 0; dx < 4; ++dx)
      put_pixel(bgr, w, h, stride, x + dx, y + dy, b, g, r);
}

}  // namespace

std::string native_version() { return "sieans_native/0.1.0+zxing-2.2.1"; }

std::vector<BarcodeHit> decode_barcodes(const uint8_t* data, int width,
                                        int height, int stride_bytes,
                                        PixelFormat format,
                                        const BarcodeOptions& options) {
  if (!data || width <= 0 || height <= 0 || stride_bytes <= 0) {
    throw std::invalid_argument("decode_barcodes: invalid image geometry");
  }
  ZXing::ImageView view(data, width, height, to_zxing_format(format),
                        stride_bytes);
  ZXing::ReaderOptions hints;
  hints.setFormats(parse_formats(options.formats));
  hints.setTryRotate(options.try_rotate);
  hints.setTryDownscale(options.try_downscale);
  hints.setMaxNumberOfSymbols(
      static_cast<uint8_t>(std::max(1, std::min(options.max_codes, 255))));

  auto results = ZXing::ReadBarcodes(view, hints);
  std::vector<BarcodeHit> out;
  out.reserve(results.size());
  for (const auto& code : results) {
    if (!code.isValid()) continue;
    BarcodeHit hit;
    hit.valid = true;
    hit.text = code.text();
    hit.format = ZXing::ToString(code.format());
    const auto& pos = code.position();
    float sx = 0.f, sy = 0.f;
    for (int i = 0; i < 4; ++i) {
      Point2f p{static_cast<float>(pos[i].x), static_cast<float>(pos[i].y)};
      hit.polygon.push_back(p);
      sx += p.x;
      sy += p.y;
    }
    hit.center = {sx / 4.f, sy / 4.f};
    out.push_back(std::move(hit));
    if (static_cast<int>(out.size()) >= options.max_codes) break;
  }
  return out;
}

void annotate_barcodes_bgr(uint8_t* bgr, int width, int height, int stride_bytes,
                           const std::vector<BarcodeHit>& hits, bool draw_boxes,
                           bool draw_text, bool draw_format) {
  if (!bgr || width <= 0 || height <= 0 || stride_bytes < width * 3) return;
  for (const auto& hit : hits) {
    if (draw_boxes && hit.polygon.size() >= 4) {
      for (int i = 0; i < 4; ++i) {
        const auto& a = hit.polygon[i];
        const auto& bpt = hit.polygon[(i + 1) % 4];
        draw_line(bgr, width, height, stride_bytes, static_cast<int>(a.x),
                  static_cast<int>(a.y), static_cast<int>(bpt.x),
                  static_cast<int>(bpt.y), 0, 220, 80);
      }
    }
    if (draw_text && !hit.text.empty()) {
      float minx = hit.polygon.empty() ? hit.center.x : hit.polygon[0].x;
      float miny = hit.polygon.empty() ? hit.center.y : hit.polygon[0].y;
      for (const auto& p : hit.polygon) {
        minx = std::min(minx, p.x);
        miny = std::min(miny, p.y);
      }
      std::string tip = hit.text.substr(0, 48);
      if (draw_format && !hit.format.empty()) tip = hit.format + ":" + tip;
      int x = static_cast<int>(minx);
      int y = std::max(8, static_cast<int>(miny) - 10);
      for (size_t i = 0; i < std::min<size_t>(tip.size(), 24); ++i)
        draw_char_mark(bgr, width, height, stride_bytes,
                       x + static_cast<int>(i) * 5, y, 0, 220, 80);
    }
  }
}

}  // namespace sieans
