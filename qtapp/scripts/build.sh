#!/usr/bin/env bash
# Build sieans_qt (Qt6 Widgets) linked against native/sieans_algo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
BUILD="$ROOT/build"

export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# User-local Qt from aqt (preferred) or system qt6-base-dev.
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

CMAKE_ARGS=(
  -S "$ROOT"
  -B "$BUILD"
  -DCMAKE_BUILD_TYPE=Release
  -DSIEANS_NATIVE_PYTHON=OFF
  -DSIEANS_NATIVE_GENTL=ON
)
if [[ -n "$QT_PREFIX" ]]; then
  echo "Using Qt at $QT_PREFIX"
  CMAKE_ARGS+=(-DCMAKE_PREFIX_PATH="$QT_PREFIX")
else
  echo "note: no ~/Qt/6.x found — relying on system Qt6 (apt install qt6-base-dev)"
fi

if [[ ! -f /opt/MVS/include/MvCameraControl.h ]]; then
  echo "note: /opt/MVS missing — GenTL stub only"
fi

cmake "${CMAKE_ARGS[@]}"
cmake --build "$BUILD" -j"$(nproc)"

BIN="$BUILD/sieans_qt"
if [[ -x "$BIN" ]]; then
  echo "build ok: $BIN"
  echo "run: $REPO/scripts/launch-sieans-qt.sh"
else
  echo "error: sieans_qt binary missing" >&2
  exit 1
fi
