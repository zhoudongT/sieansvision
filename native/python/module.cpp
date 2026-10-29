#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "sieans/barcode.hpp"
#include "sieans/gentl_capture.hpp"

namespace py = pybind11;

namespace {

sieans::PixelFormat parse_pixel_format(const std::string& name) {
  if (name == "gray" || name == "gray8" || name == "mono8" || name == "Lum")
    return sieans::PixelFormat::Gray8;
  if (name == "bgr" || name == "bgr24" || name == "BGR")
    return sieans::PixelFormat::BGR24;
  if (name == "rgb" || name == "rgb24" || name == "RGB")
    return sieans::PixelFormat::RGB24;
  if (name == "bgra" || name == "BGRA")
    return sieans::PixelFormat::BGRA32;
  if (name == "rgba" || name == "RGBA")
    return sieans::PixelFormat::RGBA32;
  throw std::invalid_argument("unknown pixel format: " + name);
}

py::dict hit_to_dict(const sieans::BarcodeHit& hit) {
  py::list poly;
  for (const auto& p : hit.polygon) {
    poly.append(py::make_tuple(p.x, p.y));
  }
  py::dict d;
  d["text"] = hit.text;
  d["format"] = hit.format;
  d["polygon"] = poly;
  d["center"] = py::make_tuple(hit.center.x, hit.center.y);
  d["valid"] = hit.valid;
  return d;
}

}  // namespace

PYBIND11_MODULE(sieans_native, m) {
  m.doc() = "SIEANS native algorithm layer (C++ barcode + optional GenTL)";
  m.def("version", &sieans::native_version);
  m.def("gentl_available", &sieans::GenTLCapture::available);

  m.def(
      "decode_barcodes",
      [](py::array image, const std::string& formats, int max_codes,
         bool try_rotate, bool try_downscale, const std::string& pixel_format) {
        py::buffer_info info = image.request();
        if (info.ndim != 2 && info.ndim != 3) {
          throw std::invalid_argument("image must be HxW or HxWxC");
        }
        if (info.itemsize != 1) {
          throw std::invalid_argument("image dtype must be uint8");
        }
        const int height = static_cast<int>(info.shape[0]);
        const int width = static_cast<int>(info.shape[1]);
        sieans::PixelFormat fmt;
        int stride = static_cast<int>(info.strides[0]);
        if (info.ndim == 2) {
          fmt = sieans::PixelFormat::Gray8;
        } else {
          const int channels = static_cast<int>(info.shape[2]);
          if (!pixel_format.empty()) {
            fmt = parse_pixel_format(pixel_format);
          } else if (channels == 4) {
            fmt = sieans::PixelFormat::BGRA32;
          } else if (channels == 1) {
            fmt = sieans::PixelFormat::Gray8;
          } else {
            fmt = sieans::PixelFormat::BGR24;
          }
        }
        sieans::BarcodeOptions opt;
        opt.formats = formats;
        opt.max_codes = max_codes;
        opt.try_rotate = try_rotate;
        opt.try_downscale = try_downscale;
        auto hits = sieans::decode_barcodes(
            static_cast<const uint8_t*>(info.ptr), width, height, stride, fmt,
            opt);
        py::list out;
        for (const auto& h : hits) out.append(hit_to_dict(h));
        return out;
      },
      py::arg("image"), py::arg("formats") = "", py::arg("max_codes") = 16,
      py::arg("try_rotate") = true, py::arg("try_downscale") = true,
      py::arg("pixel_format") = "");

  m.def(
      "annotate_barcodes",
      [](py::array image, const py::list& hits, bool draw_boxes, bool draw_text,
         bool draw_format) {
        py::buffer_info info = image.request();
        if (info.ndim != 3 || info.shape[2] != 3 || info.itemsize != 1) {
          throw std::invalid_argument("annotate expects contiguous HxWx3 uint8 BGR");
        }
        std::vector<sieans::BarcodeHit> parsed;
        for (auto item : hits) {
          py::dict d = item.cast<py::dict>();
          sieans::BarcodeHit h;
          h.text = py::str(d["text"]);
          h.format = d.contains("format") ? std::string(py::str(d["format"])) : "";
          h.valid = true;
          if (d.contains("polygon")) {
            for (auto pt : d["polygon"]) {
              py::tuple t = pt.cast<py::tuple>();
              h.polygon.push_back({t[0].cast<float>(), t[1].cast<float>()});
            }
          }
          if (d.contains("center")) {
            py::tuple c = d["center"].cast<py::tuple>();
            h.center = {c[0].cast<float>(), c[1].cast<float>()};
          }
          parsed.push_back(std::move(h));
        }
        sieans::annotate_barcodes_bgr(
            static_cast<uint8_t*>(info.ptr), static_cast<int>(info.shape[1]),
            static_cast<int>(info.shape[0]), static_cast<int>(info.strides[0]),
            parsed, draw_boxes, draw_text, draw_format);
      },
      py::arg("image"), py::arg("hits"), py::arg("draw_boxes") = true,
      py::arg("draw_text") = true, py::arg("draw_format") = true);

  py::class_<sieans::GenTLCapture>(m, "GenTLCapture")
      .def(py::init<>())
      .def_static("available", &sieans::GenTLCapture::available)
      .def_static(
          "enumerate",
          [](const std::string& cti) {
            py::list out;
            for (const auto& d : sieans::GenTLCapture::enumerate(cti)) {
              py::dict info;
              info["id"] = d.id;
              info["model"] = d.model;
              info["serial"] = d.serial;
              info["vendor"] = d.vendor;
              info["interface_id"] = d.interface_id;
              info["cti_path"] = d.cti_path;
              out.append(info);
            }
            return out;
          },
          py::arg("cti_paths") = "")
      .def("open", &sieans::GenTLCapture::open, py::arg("device_id") = "",
           py::arg("cti_path") = "")
      .def("close", &sieans::GenTLCapture::close)
      .def("is_open", &sieans::GenTLCapture::is_open)
      .def("start", &sieans::GenTLCapture::start)
      .def("stop", &sieans::GenTLCapture::stop)
      .def("is_grabbing", &sieans::GenTLCapture::is_grabbing)
      .def(
          "grab",
          [](sieans::GenTLCapture& self, int timeout_ms) {
            sieans::GenTLFrame frame;
            {
              py::gil_scoped_release release;
              frame = self.grab(timeout_ms);
            }
            py::array_t<uint8_t> arr;
            if (frame.pixel_format == "Mono8") {
              arr = py::array_t<uint8_t>({frame.height, frame.width});
            } else {
              arr = py::array_t<uint8_t>({frame.height, frame.width, 3});
            }
            auto buf = arr.request();
            if (frame.data.size() > static_cast<size_t>(buf.size)) {
              throw std::runtime_error("frame buffer size mismatch");
            }
            std::memcpy(buf.ptr, frame.data.data(), frame.data.size());
            py::dict d;
            d["image"] = arr;
            d["width"] = frame.width;
            d["height"] = frame.height;
            d["pixel_format"] = frame.pixel_format;
            d["frame_id"] = frame.frame_id;
            d["timestamp_ns"] = frame.timestamp_ns;
            d["acquire_backend"] = "sieans_native";
            return d;
          },
          py::arg("timeout_ms") = 5000)
      .def("set_exposure_us", &sieans::GenTLCapture::set_exposure_us)
      .def("set_gain_db", &sieans::GenTLCapture::set_gain_db)
      .def("configure_freerun", &sieans::GenTLCapture::configure_freerun,
           py::arg("fps") = 10.0, py::arg("buffer_count") = 16)
      .def("set_acquisition_frame_rate",
           &sieans::GenTLCapture::set_acquisition_frame_rate, py::arg("fps"))
      .def("set_image_node_num", &sieans::GenTLCapture::set_image_node_num,
           py::arg("n"));
}
