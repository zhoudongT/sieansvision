#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace sieans {

struct Point2f {
  float x = 0.f;
  float y = 0.f;
};

struct BarcodeHit {
  std::string text;
  std::string format;
  std::vector<Point2f> polygon;  // TL, TR, BR, BL
  Point2f center{};
  bool valid = false;
};

struct BarcodeOptions {
  std::string formats;   // empty / "all" / "QRCode,DataMatrix"
  int max_codes = 16;
  bool try_rotate = true;
  bool try_downscale = true;
};

enum class PixelFormat {
  Gray8 = 0,
  BGR24 = 1,
  RGB24 = 2,
  BGRA32 = 3,
  RGBA32 = 4,
};

/** Decode barcodes from a contiguous image buffer (no OpenCV required). */
std::vector<BarcodeHit> decode_barcodes(
    const uint8_t* data,
    int width,
    int height,
    int stride_bytes,
    PixelFormat format,
    const BarcodeOptions& options = {});

/** Draw simple green polygons onto a BGR24 buffer (in-place). */
void annotate_barcodes_bgr(
    uint8_t* bgr,
    int width,
    int height,
    int stride_bytes,
    const std::vector<BarcodeHit>& hits,
    bool draw_boxes = true,
    bool draw_text = true,
    bool draw_format = true);

std::string native_version();

}  // namespace sieans
