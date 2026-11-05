#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "sieans/ocr.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>

namespace sieans {
namespace {

std::string find_tessdata_prefix(const std::string& override_path) {
  if (!override_path.empty()) return override_path;
  if (const char* env = std::getenv("TESSDATA_PREFIX")) {
    if (env[0] != '\0') return env;
  }
  static const char* cands[] = {
      "/usr/share/tesseract-ocr/5/tessdata",
      "/usr/share/tesseract-ocr/4.00/tessdata",
      "/usr/share/tessdata",
  };
  for (const char* c : cands) {
    std::string eng = std::string(c) + "/eng.traineddata";
    if (access(eng.c_str(), R_OK) == 0) return c;
  }
  return {};
}

bool to_gray(const uint8_t* data, int width, int height, int stride,
             PixelFormat format, std::vector<uint8_t>& out) {
  out.resize(static_cast<size_t>(width) * static_cast<size_t>(height));
  for (int y = 0; y < height; ++y) {
    const uint8_t* row = data + static_cast<size_t>(y) * static_cast<size_t>(stride);
    uint8_t* dst = out.data() + static_cast<size_t>(y) * static_cast<size_t>(width);
    switch (format) {
      case PixelFormat::Gray8:
        std::memcpy(dst, row, static_cast<size_t>(width));
        break;
      case PixelFormat::RGB24:
        for (int x = 0; x < width; ++x) {
          const uint8_t* px = row + x * 3;
          dst[x] = static_cast<uint8_t>((px[0] * 77 + px[1] * 150 + px[2] * 29) >> 8);
        }
        break;
      case PixelFormat::BGR24:
        for (int x = 0; x < width; ++x) {
          const uint8_t* px = row + x * 3;
          dst[x] = static_cast<uint8_t>((px[2] * 77 + px[1] * 150 + px[0] * 29) >> 8);
        }
        break;
      case PixelFormat::RGBA32:
        for (int x = 0; x < width; ++x) {
          const uint8_t* px = row + x * 4;
          dst[x] = static_cast<uint8_t>((px[0] * 77 + px[1] * 150 + px[2] * 29) >> 8);
        }
        break;
      case PixelFormat::BGRA32:
        for (int x = 0; x < width; ++x) {
          const uint8_t* px = row + x * 4;
          dst[x] = static_cast<uint8_t>((px[2] * 77 + px[1] * 150 + px[0] * 29) >> 8);
        }
        break;
      default:
        return false;
    }
  }
  return true;
}

bool write_pgm(const std::string& path, int width, int height,
               const std::vector<uint8_t>& gray) {
  std::ofstream f(path, std::ios::binary);
  if (!f) return false;
  f << "P5\n" << width << " " << height << "\n255\n";
  f.write(reinterpret_cast<const char*>(gray.data()),
          static_cast<std::streamsize>(gray.size()));
  return static_cast<bool>(f);
}

std::string run_tesseract(const std::string& img_path, const OcrOptions& opt) {
  const std::string tessdata = find_tessdata_prefix(opt.tessdata_prefix);
  const std::string lang = opt.lang.empty() ? "eng" : opt.lang;
  int psm = opt.psm;
  if (psm < 0 || psm > 13) psm = 6;

  int pipefd[2];
  if (pipe(pipefd) != 0) return {};
  const pid_t pid = fork();
  if (pid < 0) {
    close(pipefd[0]);
    close(pipefd[1]);
    return {};
  }
  if (pid == 0) {
    close(pipefd[0]);
    dup2(pipefd[1], STDOUT_FILENO);
    // keep stderr quiet for soft smoke
    int devnull = open("/dev/null", O_WRONLY);
    if (devnull >= 0) {
      dup2(devnull, STDERR_FILENO);
      close(devnull);
    }
    close(pipefd[1]);
    if (!tessdata.empty()) setenv("TESSDATA_PREFIX", tessdata.c_str(), 1);
    const std::string psm_s = std::to_string(psm);
    execlp("tesseract", "tesseract", img_path.c_str(), "stdout", "-l", lang.c_str(),
           "--psm", psm_s.c_str(), static_cast<char*>(nullptr));
    _exit(127);
  }
  close(pipefd[1]);
  std::string out;
  char buf[4096];
  ssize_t n;
  while ((n = read(pipefd[0], buf, sizeof(buf))) > 0) {
    out.append(buf, static_cast<size_t>(n));
  }
  close(pipefd[0]);
  int status = 0;
  waitpid(pid, &status, 0);
  if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
    // still return whatever stdout we got
  }
  return out;
}

std::vector<OcrHit> parse_lines(const std::string& raw, int min_conf) {
  std::vector<OcrHit> hits;
  std::istringstream iss(raw);
  std::string line;
  int idx = 0;
  while (std::getline(iss, line)) {
    // trim CR
    while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
    size_t start = 0;
    while (start < line.size() && line[start] == ' ') ++start;
    if (start >= line.size()) continue;
    OcrHit h;
    h.text = line.substr(start);
    h.confidence = 0.f;
    h.line_index = idx++;
    if (min_conf > 0 && h.confidence < static_cast<float>(min_conf) &&
        h.confidence > 0.f) {
      continue;
    }
    hits.push_back(std::move(h));
  }
  return hits;
}

}  // namespace

bool ocr_available() {
  return access("/usr/bin/tesseract", X_OK) == 0 ||
         access("/usr/local/bin/tesseract", X_OK) == 0;
}

std::vector<OcrHit> recognize_text(const uint8_t* data, int width, int height,
                                   int stride_bytes, PixelFormat format,
                                   const OcrOptions& options) {
  if (!data || width <= 0 || height <= 0 || stride_bytes <= 0) return {};
  if (!ocr_available()) return {};

  std::vector<uint8_t> gray;
  if (!to_gray(data, width, height, stride_bytes, format, gray)) return {};

  char tmpl[] = "/tmp/sieans-ocr-XXXXXX.pgm";
  const int fd = mkstemps(tmpl, 4);
  if (fd < 0) return {};
  close(fd);
  const std::string path(tmpl);
  if (!write_pgm(path, width, height, gray)) {
    unlink(path.c_str());
    return {};
  }
  const std::string raw = run_tesseract(path, options);
  unlink(path.c_str());
  return parse_lines(raw, options.min_confidence);
}

}  // namespace sieans
