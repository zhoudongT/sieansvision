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

#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>

namespace sieans {
namespace {

/** 判断 path 是否为可执行的普通文件（目录对 X_OK 也会成功，必须排除）。 */
bool is_executable_file(const std::string& path) {
  if (path.empty()) return false;
  struct stat st {};
  if (stat(path.c_str(), &st) != 0) return false;
  if (!S_ISREG(st.st_mode)) return false;
  return access(path.c_str(), X_OK) == 0;
}

/** 去掉末尾斜杠，避免拼接 tessdata 时出现双分隔符。 */
std::string trim_trailing_slash(std::string path) {
  while (path.size() > 1 && path.back() == '/') path.pop_back();
  return path;
}

/** 若 path 本身或 path/tessdata 含 eng.traineddata，返回 tessdata 目录。 */
std::string tessdata_if_valid(const std::string& path) {
  if (path.empty()) return {};
  const std::string direct = trim_trailing_slash(path);
  if (access((direct + "/eng.traineddata").c_str(), R_OK) == 0) return direct;
  const std::string nested = direct + "/tessdata";
  if (access((nested + "/eng.traineddata").c_str(), R_OK) == 0) return nested;
  return {};
}

/** 当前用户主目录；无 HOME 时返回空，跳过用户前缀查找。 */
std::string home_dir() {
  const char* home = std::getenv("HOME");
  if (!home || home[0] == '\0') return {};
  return trim_trailing_slash(home);
}

/**
 * 解析 tesseract 可执行文件：SIEANS_TESSERACT、PATH、用户前缀，最后才是系统路径。
 * 用户前缀默认 $HOME/.local/bin/tesseract 与 $HOME/.local/opt/tesseract/usr/bin/tesseract。
 */
std::string find_tesseract_bin() {
  if (const char* env = std::getenv("SIEANS_TESSERACT")) {
    if (is_executable_file(env)) return env;
  }
  if (const char* path = std::getenv("PATH")) {
    std::string cur;
    for (const char* p = path;; ++p) {
      if (*p == ':' || *p == '\0') {
        if (!cur.empty()) {
          const std::string cand = trim_trailing_slash(cur) + "/tesseract";
          if (is_executable_file(cand)) return cand;
        }
        cur.clear();
        if (*p == '\0') break;
      } else {
        cur.push_back(*p);
      }
    }
  }
  const std::string home = home_dir();
  if (!home.empty()) {
    static const char* user_bins[] = {
        "/.local/bin/tesseract",
        "/.local/opt/tesseract/usr/bin/tesseract",
    };
    for (const char* rel : user_bins) {
      const std::string cand = home + rel;
      if (is_executable_file(cand)) return cand;
    }
  }
  static const char* system_bins[] = {
      "/usr/local/bin/tesseract",
      "/usr/bin/tesseract",
  };
  for (const char* c : system_bins) {
    if (is_executable_file(c)) return c;
  }
  return {};
}

/**
 * 定位 tessdata 目录（内含 eng.traineddata）。
 * 优先覆盖路径与 TESSDATA_PREFIX，再查用户前缀，最后才是发行版路径。
 */
std::string find_tessdata_prefix(const std::string& override_path) {
  if (const std::string hit = tessdata_if_valid(override_path); !hit.empty()) return hit;
  if (const char* env = std::getenv("TESSDATA_PREFIX")) {
    if (const std::string hit = tessdata_if_valid(env); !hit.empty()) return hit;
  }
  const std::string home = home_dir();
  if (!home.empty()) {
    static const char* user_dirs[] = {
        "/.local/share/tessdata",
        "/.local/opt/tesseract/usr/share/tesseract-ocr/5/tessdata",
        "/.local/share/tesseract-ocr/5/tessdata",
    };
    for (const char* rel : user_dirs) {
      if (const std::string hit = tessdata_if_valid(home + rel); !hit.empty()) return hit;
    }
  }
  static const char* cands[] = {
      "/usr/share/tesseract-ocr/5/tessdata",
      "/usr/share/tesseract-ocr/4.00/tessdata",
      "/usr/share/tessdata",
  };
  for (const char* c : cands) {
    if (const std::string hit = tessdata_if_valid(c); !hit.empty()) return hit;
  }
  return {};
}

/**
 * 若二进制位于用户前缀（.../usr/bin/tesseract），把同前缀的 lib 目录前置到
 * LD_LIBRARY_PATH，这样不经过包装脚本也能找到 libtesseract/liblept。
 */
void prepend_user_tesseract_libs(const std::string& bin) {
  const auto slash = bin.find_last_of('/');
  if (slash == std::string::npos || slash == 0) return;
  const std::string bindir = bin.substr(0, slash);
  const std::string cands[] = {
      bindir + "/../lib/x86_64-linux-gnu",
      bindir + "/../lib",
  };
  for (const std::string& raw : cands) {
    const std::string dir = trim_trailing_slash(raw);
    if (access((dir + "/libtesseract.so.5").c_str(), R_OK) != 0 &&
        access((dir + "/liblept.so.5").c_str(), R_OK) != 0) {
      continue;
    }
    const char* old = std::getenv("LD_LIBRARY_PATH");
    std::string neu = dir;
    if (old && old[0] != '\0') {
      neu.push_back(':');
      neu += old;
    }
    setenv("LD_LIBRARY_PATH", neu.c_str(), 1);
    return;
  }
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

/** 调用已定位的 tesseract CLI；用 --tessdata-dir 显式传入语言包目录。 */
std::string run_tesseract(const std::string& img_path, const OcrOptions& opt) {
  const std::string bin = find_tesseract_bin();
  if (bin.empty()) return {};
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
    prepend_user_tesseract_libs(bin);
    // Ubuntu 5.3.4 把 TESSDATA_PREFIX 当作 tessdata 目录本身。
    if (!tessdata.empty()) setenv("TESSDATA_PREFIX", tessdata.c_str(), 1);
    const std::string psm_s = std::to_string(psm);
    if (!tessdata.empty()) {
      execl(bin.c_str(), "tesseract", img_path.c_str(), "stdout", "-l", lang.c_str(),
            "--psm", psm_s.c_str(), "--tessdata-dir", tessdata.c_str(),
            static_cast<char*>(nullptr));
    } else {
      execl(bin.c_str(), "tesseract", img_path.c_str(), "stdout", "-l", lang.c_str(),
            "--psm", psm_s.c_str(), static_cast<char*>(nullptr));
    }
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
  return !find_tesseract_bin().empty() && !find_tessdata_prefix({}).empty();
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
