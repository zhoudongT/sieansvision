#pragma once
#include "sieans/barcode.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace sieans {

struct OcrHit {
  std::string text;
  float confidence = 0.f;  // 0..100 when available; else 0
  int line_index = 0;
};

struct OcrOptions {
  std::string lang = "eng";   // tessdata lang, e.g. eng
  int psm = 6;                // page segmentation (6=block, 7=line)
  int min_confidence = 0;     // drop lines below this (0 = keep all)
  std::string tessdata_prefix;  // empty → auto /usr/share/tesseract-ocr/5/tessdata
};

/** OCR a contiguous image buffer via system tesseract CLI (no Halcon). */
std::vector<OcrHit> recognize_text(
    const uint8_t* data,
    int width,
    int height,
    int stride_bytes,
    PixelFormat format,
    const OcrOptions& options = {});

/** True when `tesseract` is on PATH. */
bool ocr_available();

}  // namespace sieans
