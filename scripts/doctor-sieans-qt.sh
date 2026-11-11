#!/usr/bin/env bash
# Verify the no-sudo sieans_qt build/launch path on this checkout.
# Default: check only. Exit 0 when required items pass (optional deps warn).
#   --selftest        run SIEANS_QT_PROJECT_SELFTEST after checks (needs a built binary)
#   --prove-install   rerun user-local Tesseract/ORT installers into a temp prefix
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WANT_SELFTEST=0
WANT_PROVE=0
for arg in "$@"; do
  case "$arg" in
    --selftest) WANT_SELFTEST=1 ;;
    --prove-install) WANT_PROVE=1 ;;
    -h|--help)
      sed -n '2,6p' "$0"
      exit 0
      ;;
    *)
      echo "unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

PASS=0
WARN=0
FAIL=0
ok() { printf '  PASS  %s\n' "$1"; PASS=$((PASS + 1)); }
warn() { printf '  WARN  %s\n' "$1"; WARN=$((WARN + 1)); }
fail() { printf '  FAIL  %s\n' "$1"; FAIL=$((FAIL + 1)); }

echo "SIEANS Qt workbench doctor"
echo "repo: $ROOT"
echo

echo "toolchain (required)"
if command -v cmake >/dev/null && cmake --version | head -n1 | grep -q .; then
  ok "cmake $(cmake --version | head -n1 | awk '{print $3}') ($(command -v cmake))"
else
  fail "cmake missing — install cmake (>=3.16) or ask an admin (one-time sudo apt)"
fi
if command -v g++ >/dev/null; then
  ok "g++ $(g++ -dumpfullversion 2>/dev/null || g++ -dumpversion) ($(command -v g++))"
else
  fail "g++ missing — install build-essential or ask an admin"
fi
if command -v make >/dev/null; then
  ok "make $(command -v make)"
else
  fail "make missing"
fi
if command -v curl >/dev/null; then
  ok "curl $(command -v curl)"
else
  fail "curl missing (needed by install-onnxruntime-user.sh)"
fi
if command -v python3 >/dev/null; then
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
else
  warn "python3 missing — only needed to install Qt via aqt, not to build"
fi
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ok "PATH contains \$HOME/.local/bin" ;;
  *) warn "\$HOME/.local/bin is not on PATH — user-local tesseract wrapper may be invisible" ;;
esac

echo
echo "Qt (required to build)"
QT_PREFIX="${SIEANS_QT_PREFIX:-}"
if [[ -z "$QT_PREFIX" ]]; then
  for cand in \
      "$HOME/Qt/6.7.3/gcc_64" \
      "$HOME/Qt/6.8.3/gcc_64" \
      "$HOME/Qt/6.8.0/gcc_64" \
      "$HOME/Qt/6.6.3/gcc_64"; do
    if [[ -f "$cand/lib/cmake/Qt6/Qt6Config.cmake" ]]; then
      QT_PREFIX="$cand"
      break
    fi
  done
fi
if [[ -n "$QT_PREFIX" && -f "$QT_PREFIX/lib/cmake/Qt6/Qt6Config.cmake" ]]; then
  ok "Qt prefix $QT_PREFIX"
else
  fail "Qt 6 not found. Install user-local 6.7.3 (no sudo): python3 -m pip install --user aqtinstall && python3 -m aqt install-qt linux desktop 6.7.3 gcc_64 --outputdir \"\$HOME/Qt\""
fi

echo
echo "checkout scripts (required)"
if [[ -x "$ROOT/qtapp/scripts/build.sh" && -x "$ROOT/scripts/launch-sieans-qt.sh" ]]; then
  ok "build.sh and launch-sieans-qt.sh are executable"
else
  fail "qtapp/scripts/build.sh or scripts/launch-sieans-qt.sh missing / not executable"
fi
if [[ -d "$ROOT/projects" ]]; then
  ok "projects/ present"
else
  warn "projects/ missing — first launch will seed a demo flow"
fi

echo
echo "Tesseract OCR (optional)"
TESS_WRAP="${SIEANS_TESSERACT_BIN:-$HOME/.local/bin/tesseract}"
TESS_PREFIX="${SIEANS_TESSERACT_PREFIX:-$HOME/.local/opt/tesseract}"
TESS_DATA="${TESSDATA_PREFIX:-$TESS_PREFIX/usr/share/tesseract-ocr/5/tessdata}"
TESS_BIN=""
if command -v tesseract >/dev/null; then
  TESS_BIN="$(command -v tesseract)"
elif [[ -x "$TESS_WRAP" ]]; then
  TESS_BIN="$TESS_WRAP"
elif [[ -x "$TESS_PREFIX/usr/bin/tesseract" ]]; then
  TESS_BIN="$TESS_PREFIX/usr/bin/tesseract"
fi
if [[ -n "$TESS_BIN" ]]; then
  ok "tesseract $TESS_BIN"
  if [[ -f "$TESS_DATA/eng.traineddata" && -f "$TESS_DATA/chi_sim.traineddata" ]]; then
    ok "tessdata eng+chi_sim in $TESS_DATA"
  elif "$TESS_BIN" --list-langs 2>/dev/null | grep -q '^eng$' && \
       "$TESS_BIN" --list-langs 2>/dev/null | grep -q '^chi_sim$'; then
    ok "tesseract lists eng+chi_sim"
  else
    warn "tesseract found but eng/chi_sim traineddata not confirmed — run scripts/install-tesseract-user.sh"
  fi
else
  warn "tesseract not found — OCR unavailable until scripts/install-tesseract-user.sh (no sudo)"
fi

echo
echo "ONNX Runtime (optional, YOLO)"
ORT="${SIEANS_ONNXRUNTIME_DIR:-$HOME/.local/opt/onnxruntime}"
if [[ -f "$ORT/include/onnxruntime_c_api.h" && -e "$ORT/lib/libonnxruntime.so" ]]; then
  ok "ONNX Runtime $ORT"
else
  warn "ONNX Runtime missing at $ORT — YOLO uses software fallback until scripts/install-onnxruntime-user.sh (no sudo)"
fi
if [[ -f "$ROOT/models/sieans-yolo-smoke.onnx" ]]; then
  ok "smoke stub models/sieans-yolo-smoke.onnx present (not official YOLO weights)"
else
  warn "models/sieans-yolo-smoke.onnx missing — official YOLO weights are never auto-downloaded"
fi

echo
echo "Qt xcb cursor (optional, xcb platform plugin)"
XCB_PREFIX="${SIEANS_XCB_CURSOR_DIR:-$HOME/.local/opt/xcb-cursor}"
XCB_LIB="$XCB_PREFIX/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0"
if [[ -e "$XCB_LIB" ]]; then
  ok "libxcb-cursor $XCB_LIB"
elif ldconfig -p 2>/dev/null | grep -q 'libxcb-cursor.so.0'; then
  ok "libxcb-cursor from system (libxcb-cursor0)"
else
  warn "libxcb-cursor0 missing — xcb plugin needs it (Qt 6.5+). Run scripts/install-xcb-cursor-user.sh (no sudo). Wayland sessions do not require it."
fi

echo
echo "hardware (optional)"
if [[ -f /opt/MVS/include/MvCameraControl.h ]]; then
  ok "Hikrobot /opt/MVS present"
else
  warn "/opt/MVS missing — GenTL is stub-only; use Soft camera (SIEANS_QT_AUTO_SOFT=1)"
fi

echo
echo "build output"
BIN="$ROOT/qtapp/build/sieans_qt"
if [[ -x "$BIN" ]]; then
  ok "sieans_qt $BIN"
else
  warn "sieans_qt not built yet — run: SIEANS_QT_PREFIX=\$HOME/Qt/6.7.3/gcc_64 ./qtapp/scripts/build.sh"
fi

if [[ "$WANT_PROVE" == 1 ]]; then
  echo
  echo "prove user-local install scripts (temp prefixes, no sudo)"
  if ! command -v apt-get >/dev/null || ! command -v dpkg-deb >/dev/null; then
    warn "skip Tesseract prove — apt-get/dpkg-deb not available"
  else
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/sieans-doctor-tess-XXXXXX")"
    if SIEANS_TESSERACT_PREFIX="$tmp/opt" \
       SIEANS_TESSERACT_CACHE="$tmp/cache" \
       SIEANS_TESSERACT_BIN="$tmp/bin/tesseract" \
       "$ROOT/scripts/install-tesseract-user.sh"; then
      if [[ -x "$tmp/bin/tesseract" ]] && \
         "$tmp/bin/tesseract" --list-langs 2>/dev/null | grep -q '^eng$' && \
         "$tmp/bin/tesseract" --list-langs 2>/dev/null | grep -q '^chi_sim$'; then
        ok "install-tesseract-user.sh works in $tmp (eng+chi_sim)"
      else
        fail "install-tesseract-user.sh finished but langs not listed from $tmp/bin/tesseract"
      fi
    else
      fail "install-tesseract-user.sh failed in temp prefix"
    fi
    rm -rf "$tmp"
  fi

  if ! command -v curl >/dev/null; then
    warn "skip ONNX Runtime prove — curl missing"
  else
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/sieans-doctor-ort-XXXXXX")"
    cache_args=()
    live_cache="${SIEANS_ONNXRUNTIME_CACHE:-$HOME/.local/src/onnxruntime}"
    live_tgz="$live_cache/onnxruntime-linux-x64-1.31.1.tgz"
    if [[ -f "$live_tgz" ]]; then
      mkdir -p "$tmp/cache"
      # reuse already-verified tarball; installer still sha256-checks it
      cp -a "$live_tgz" "$tmp/cache/"
    fi
    if SIEANS_ONNXRUNTIME_DIR="$tmp/opt" \
       SIEANS_ONNXRUNTIME_CACHE="$tmp/cache" \
       "$ROOT/scripts/install-onnxruntime-user.sh"; then
      if [[ -f "$tmp/opt/include/onnxruntime_c_api.h" && -e "$tmp/opt/lib/libonnxruntime.so" ]]; then
        ok "install-onnxruntime-user.sh works in $tmp"
      else
        fail "install-onnxruntime-user.sh finished but prefix incomplete"
      fi
    else
      fail "install-onnxruntime-user.sh failed in temp prefix"
    fi
    rm -rf "$tmp"
  fi
  if ! command -v dpkg-deb >/dev/null || ! command -v curl >/dev/null; then
    warn "skip libxcb-cursor prove — curl or dpkg-deb missing"
  else
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/sieans-doctor-xcb-XXXXXX")"
    cache_args=()
    live_cache="${SIEANS_XCB_CURSOR_CACHE:-$HOME/.local/src/xcb-cursor}"
    live_deb="$live_cache/libxcb-cursor0_0.1.4-1build1_amd64.deb"
    if [[ -f "$live_deb" ]]; then
      mkdir -p "$tmp/cache"
      cp -a "$live_deb" "$tmp/cache/"
    fi
    if SIEANS_XCB_CURSOR_DIR="$tmp/opt"        SIEANS_XCB_CURSOR_CACHE="$tmp/cache"        "$ROOT/scripts/install-xcb-cursor-user.sh"; then
      if [[ -e "$tmp/opt/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0" ]]; then
        ok "install-xcb-cursor-user.sh works in $tmp"
      else
        fail "install-xcb-cursor-user.sh finished but lib missing"
      fi
    else
      fail "install-xcb-cursor-user.sh failed in temp prefix"
    fi
    rm -rf "$tmp"
  fi
fi

if [[ "$WANT_SELFTEST" == 1 ]]; then
  echo
  echo "project path selftest"
  if [[ ! -x "$BIN" ]]; then
    fail "cannot --selftest: $BIN is not built"
  else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
    export SIEANS_QT_PREFIX="${SIEANS_QT_PREFIX:-$QT_PREFIX}"
    export SIEANS_QT_PROJECT_SELFTEST=1
    export SIEANS_QT_PROJECT_SELFTEST_QUIT=1
    unset SIEANS_QT_FORCE_SEED SIEANS_QT_AUTO_SOFT SIEANS_QT_AUTO_RUN SIEANS_QT_AUTO_TCP
    unset SIEANS_QT_SCREENSHOT SIEANS_QT_SCREENSHOT_QUIT SIEANS_QT_SMOKE_REPORT
    if "$ROOT/scripts/launch-sieans-qt.sh"; then
      if grep -q 'project-selftest ok' "$ROOT/artifacts/sieans-qt.log"; then
        ok "SIEANS_QT_PROJECT_SELFTEST ok"
      else
        fail "launch exited 0 but artifacts/sieans-qt.log has no 'project-selftest ok'"
      fi
    else
      fail "project selftest launch failed"
    fi
  fi
fi

echo
echo "summary: PASS=$PASS WARN=$WARN FAIL=$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo "required checks failed — see docs/qt-workbench-setup.md"
  exit 1
fi
echo "required checks passed. optional WARNs do not block a Soft-camera software build."
echo "build: SIEANS_QT_PREFIX=\${SIEANS_QT_PREFIX:-$HOME/Qt/6.7.3/gcc_64} ./qtapp/scripts/build.sh"
echo "run:   ./scripts/launch-sieans-qt.sh"
exit 0
