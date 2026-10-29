#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace sieans {

struct GenTLDeviceInfo {
  std::string id;
  std::string model;
  std::string serial;
  std::string vendor;
  std::string interface_id;
  std::string cti_path;
};

struct GenTLFrame {
  std::vector<uint8_t> data;  // Mono8 or BGR24 contiguous
  int width = 0;
  int height = 0;
  int stride = 0;
  std::string pixel_format;  // "Mono8" | "BGR8"
  uint64_t frame_id = 0;
  int64_t timestamp_ns = 0;
};

/**
 * Thin C++ GenTL / Hikrobot MvCameraControl capture handle.
 * Built only when SIEANS_NATIVE_GENTL=ON and /opt/MVS is present.
 * When unavailable, methods throw std::runtime_error with a clear message;
 * Python GenTL (harvesters) remains the App default path.
 */
class GenTLCapture {
 public:
  GenTLCapture();
  ~GenTLCapture();
  GenTLCapture(const GenTLCapture&) = delete;
  GenTLCapture& operator=(const GenTLCapture&) = delete;

  static bool available();
  static std::vector<GenTLDeviceInfo> enumerate(
      const std::string& cti_paths = "");

  void open(const std::string& device_id,
            const std::string& cti_path = "");
  void close();
  bool is_open() const;

  void start();
  void stop();
  bool is_grabbing() const;

  /** Blocking grab; timeout_ms <= 0 uses 5000. Returns Mono8 or BGR8. */
  GenTLFrame grab(int timeout_ms = 5000);

  void set_exposure_us(double us);
  void set_gain_db(double db);

 private:
  struct Impl;
  Impl* impl_ = nullptr;
};

}  // namespace sieans
