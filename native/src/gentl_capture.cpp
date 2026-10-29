#include "sieans/gentl_capture.hpp"

#include <stdexcept>
#include <sstream>

#if defined(SIEANS_HAS_MVCAM)
#include "MvCameraControl.h"
#include <cstring>
#include <cstdlib>
#endif

namespace sieans {

static inline const char* as_cstr(const unsigned char* p) {
  return reinterpret_cast<const char*>(p);
}


#if !defined(SIEANS_HAS_MVCAM)

struct GenTLCapture::Impl {};

GenTLCapture::GenTLCapture() : impl_(new Impl) {}
GenTLCapture::~GenTLCapture() { delete impl_; }

bool GenTLCapture::available() { return false; }

std::vector<GenTLDeviceInfo> GenTLCapture::enumerate(const std::string&) {
  throw std::runtime_error(
      "sieans_native GenTL: not built with MvCameraControl "
      "(set -DSIEANS_NATIVE_GENTL=ON and install /opt/MVS)");
}

void GenTLCapture::open(const std::string&, const std::string&) {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::close() {}
bool GenTLCapture::is_open() const { return false; }
void GenTLCapture::start() {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::stop() {}
bool GenTLCapture::is_grabbing() const { return false; }
GenTLFrame GenTLCapture::grab(int) {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::set_exposure_us(double) {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::set_gain_db(double) {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::configure_freerun(double, int) {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::set_acquisition_frame_rate(double) {
  throw std::runtime_error("sieans_native GenTL: not available");
}
void GenTLCapture::set_image_node_num(unsigned) {
  throw std::runtime_error("sieans_native GenTL: not available");
}

#else  // SIEANS_HAS_MVCAM

namespace {

std::string err_str(int nRet) {
  std::ostringstream os;
  os << "MvCameraControl error 0x" << std::hex << nRet;
  return os.str();
}

std::vector<std::string> split_cti(const std::string& paths) {
  std::vector<std::string> out;
  std::string cur;
  for (char c : paths) {
    if (c == ':' || c == ';') {
      if (!cur.empty()) out.push_back(cur);
      cur.clear();
    } else {
      cur.push_back(c);
    }
  }
  if (!cur.empty()) out.push_back(cur);
  if (out.empty()) {
    const char* env = std::getenv("SIEANS_GENTL_CTI");
    if (env && *env) return split_cti(env);
    out.push_back("/opt/MVS/lib/64/MvProducerU3V.cti");
    out.push_back("/opt/MVS/lib/64/MvProducerGEV.cti");
  }
  return out;
}

}  // namespace

struct GenTLCapture::Impl {
  void* handle = nullptr;
  bool grabbing = false;
  std::string device_id;
  std::string cti_path;
};

GenTLCapture::GenTLCapture() : impl_(new Impl) {}
GenTLCapture::~GenTLCapture() {
  try {
    close();
  } catch (...) {
  }
  delete impl_;
}

bool GenTLCapture::available() { return true; }

std::vector<GenTLDeviceInfo> GenTLCapture::enumerate(const std::string& cti_paths) {
  std::vector<GenTLDeviceInfo> devices;
  for (const auto& cti : split_cti(cti_paths)) {
    MV_GENTL_IF_INFO_LIST ifList = {};
    int nRet = MV_CC_EnumInterfacesByGenTL(&ifList, cti.c_str());
    if (nRet != MV_OK) continue;
    for (unsigned i = 0; i < ifList.nInterfaceNum; ++i) {
      MV_GENTL_IF_INFO* pIF = ifList.pIFInfo[i];
      if (!pIF) continue;
      MV_GENTL_DEV_INFO_LIST devList = {};
      nRet = MV_CC_EnumDevicesByGenTL(pIF, &devList);
      if (nRet != MV_OK) continue;
      for (unsigned d = 0; d < devList.nDeviceNum; ++d) {
        MV_GENTL_DEV_INFO* pDev = devList.pDeviceInfo[d];
        if (!pDev) continue;
        GenTLDeviceInfo info;
        info.cti_path = cti;
        info.interface_id = as_cstr(pIF->chInterfaceID);
        info.id = pDev->chDeviceID[0] ? as_cstr(pDev->chDeviceID) : as_cstr(pDev->chSerialNumber);
        info.model = as_cstr(pDev->chModelName);
        info.serial = as_cstr(pDev->chSerialNumber);
        info.vendor = as_cstr(pDev->chVendorName);
        devices.push_back(std::move(info));
      }
    }
  }
  return devices;
}

void GenTLCapture::open(const std::string& device_id, const std::string& cti_path) {
  if (impl_->handle) close();
  auto list = enumerate(cti_path);
  GenTLDeviceInfo match;
  bool found = false;
  for (const auto& d : list) {
    if (device_id.empty() || d.id == device_id || d.serial == device_id ||
        d.model.find(device_id) != std::string::npos) {
      match = d;
      found = true;
      if (!device_id.empty()) break;
    }
  }
  if (!found) {
    throw std::runtime_error("GenTL device not found: " + device_id);
  }
  std::string use_cti = match.cti_path.empty() ? cti_path : match.cti_path;

  MV_GENTL_IF_INFO_LIST ifList = {};
  int nRet = MV_CC_EnumInterfacesByGenTL(&ifList, use_cti.c_str());
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
  MV_GENTL_DEV_INFO* pTarget = nullptr;
  for (unsigned i = 0; i < ifList.nInterfaceNum && !pTarget; ++i) {
    MV_GENTL_IF_INFO* pIF = ifList.pIFInfo[i];
    MV_GENTL_DEV_INFO_LIST devList = {};
    nRet = MV_CC_EnumDevicesByGenTL(pIF, &devList);
    if (nRet != MV_OK) continue;
    for (unsigned d = 0; d < devList.nDeviceNum; ++d) {
      MV_GENTL_DEV_INFO* pDev = devList.pDeviceInfo[d];
      if (!pDev) continue;
      std::string id = pDev->chDeviceID[0] ? as_cstr(pDev->chDeviceID) : as_cstr(pDev->chSerialNumber);
      if (id == match.id || std::string(as_cstr(pDev->chSerialNumber)) == match.serial) {
        pTarget = pDev;
        break;
      }
    }
  }
  if (!pTarget) throw std::runtime_error("GenTL open: device vanished during enum");

  void* handle = nullptr;
  nRet = MV_CC_CreateHandleByGenTL(&handle, pTarget);
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
  nRet = MV_CC_OpenDevice(handle, MV_ACCESS_Exclusive, 0);
  if (nRet != MV_OK) {
    MV_CC_DestroyHandle(handle);
    throw std::runtime_error(err_str(nRet));
  }
  impl_->handle = handle;
  impl_->device_id = match.id;
  impl_->cti_path = use_cti;
}

void GenTLCapture::close() {
  if (!impl_->handle) return;
  if (impl_->grabbing) {
    MV_CC_StopGrabbing(impl_->handle);
    impl_->grabbing = false;
  }
  MV_CC_CloseDevice(impl_->handle);
  MV_CC_DestroyHandle(impl_->handle);
  impl_->handle = nullptr;
}

bool GenTLCapture::is_open() const { return impl_->handle != nullptr; }

void GenTLCapture::start() {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  int nRet = MV_CC_StartGrabbing(impl_->handle);
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
  impl_->grabbing = true;
}

void GenTLCapture::stop() {
  if (!impl_->handle || !impl_->grabbing) return;
  MV_CC_StopGrabbing(impl_->handle);
  impl_->grabbing = false;
}

bool GenTLCapture::is_grabbing() const { return impl_->grabbing; }

GenTLFrame GenTLCapture::grab(int timeout_ms) {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  if (!impl_->grabbing) start();
  int to = timeout_ms <= 0 ? 5000 : timeout_ms;
  MV_FRAME_OUT frame = {};
  int nRet = MV_CC_GetImageBuffer(impl_->handle, &frame, to);
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));

  GenTLFrame out;
  out.width = static_cast<int>(frame.stFrameInfo.nWidth);
  out.height = static_cast<int>(frame.stFrameInfo.nHeight);
  out.frame_id = frame.stFrameInfo.nFrameNum;
  out.timestamp_ns = static_cast<int64_t>(frame.stFrameInfo.nHostTimeStamp) * 1000000LL;

  MvGvspPixelType pixelType = frame.stFrameInfo.enPixelType;
  const unsigned char* src = frame.pBufAddr;
  size_t srcLen = frame.stFrameInfo.nFrameLen;

  if (pixelType == PixelType_Gvsp_Mono8) {
    out.pixel_format = "Mono8";
    out.stride = out.width;
    out.data.assign(src, src + static_cast<size_t>(out.width) * out.height);
  } else {
    unsigned int dstLen = static_cast<unsigned int>(out.width * out.height * 3);
    out.data.resize(dstLen);
    MV_CC_PIXEL_CONVERT_PARAM_EX conv = {};
    conv.nWidth = static_cast<unsigned int>(out.width);
    conv.nHeight = static_cast<unsigned int>(out.height);
    conv.pSrcData = const_cast<unsigned char*>(src);
    conv.nSrcDataLen = static_cast<unsigned int>(srcLen);
    conv.enSrcPixelType = pixelType;
    conv.enDstPixelType = PixelType_Gvsp_BGR8_Packed;
    conv.pDstBuffer = out.data.data();
    conv.nDstBufferSize = dstLen;
    nRet = MV_CC_ConvertPixelTypeEx(impl_->handle, &conv);
    if (nRet != MV_OK) {
      MV_CC_FreeImageBuffer(impl_->handle, &frame);
      throw std::runtime_error(err_str(nRet));
    }
    out.pixel_format = "BGR8";
    out.stride = out.width * 3;
  }
  MV_CC_FreeImageBuffer(impl_->handle, &frame);
  return out;
}

void GenTLCapture::set_exposure_us(double us) {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  MV_CC_SetEnumValue(impl_->handle, "ExposureAuto", 0);
  int nRet = MV_CC_SetFloatValue(impl_->handle, "ExposureTime", static_cast<float>(us));
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
}

void GenTLCapture::set_gain_db(double db) {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  MV_CC_SetEnumValue(impl_->handle, "GainAuto", 0);
  int nRet = MV_CC_SetFloatValue(impl_->handle, "Gain", static_cast<float>(db));
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
}

void GenTLCapture::set_image_node_num(unsigned n) {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  if (impl_->grabbing) throw std::runtime_error("GenTL set_image_node_num requires stop");
  unsigned want = n < 1 ? 1u : (n > 64u ? 64u : n);
  int nRet = MV_CC_SetImageNodeNum(impl_->handle, want);
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
}

void GenTLCapture::set_acquisition_frame_rate(double fps) {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  double rate = fps < 1.0 ? 1.0 : (fps > 240.0 ? 240.0 : fps);
  // Best-effort: some models lack the enable flag or rate node.
  MV_CC_SetBoolValue(impl_->handle, "AcquisitionFrameRateEnable", true);
  int nRet = MV_CC_SetFloatValue(impl_->handle, "AcquisitionFrameRate",
                                 static_cast<float>(rate));
  if (nRet != MV_OK) throw std::runtime_error(err_str(nRet));
}

void GenTLCapture::configure_freerun(double fps, int buffer_count) {
  if (!impl_->handle) throw std::runtime_error("GenTL not open");
  if (impl_->grabbing) stop();
  // Drop-old at SDK: always deliver newest frame when host paces slower.
  int nRet = MV_CC_SetGrabStrategy(impl_->handle, MV_GrabStrategy_LatestImagesOnly);
  if (nRet != MV_OK) {
    // Non-fatal on older SDKs — grab still works OneByOne.
  }
  try {
    set_image_node_num(static_cast<unsigned>(buffer_count > 0 ? buffer_count : 16));
  } catch (...) {
  }
  // Continuous + trigger off (freerun). Ignore failures on burst-only models.
  MV_CC_SetEnumValueByString(impl_->handle, "AcquisitionMode", "Continuous");
  MV_CC_SetEnumValueByString(impl_->handle, "TriggerMode", "Off");
  try {
    set_acquisition_frame_rate(fps > 0 ? fps : 10.0);
  } catch (...) {
  }
}

#endif  // SIEANS_HAS_MVCAM

}  // namespace sieans
