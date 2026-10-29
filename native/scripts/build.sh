#!/usr/bin/env bash
# Build sieans_native on Ubuntu (allen-MCLG-XX / similar).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
BUILD="$ROOT/build"
mkdir -p "$BUILD"
export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

GENTL=ON
if [[ ! -f /opt/MVS/include/MvCameraControl.h ]]; then
  echo "note: /opt/MVS missing — building barcode-only (GenTL stub)"
  GENTL=OFF
fi

cmake -S "$ROOT" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release \
  -DSIEANS_NATIVE_GENTL="$GENTL" \
  -DSIEANS_NATIVE_PYTHON=ON
cmake --build "$BUILD" -j"$(nproc)"

# Ensure module lands in repo .pydeps
MOD="$(find "$BUILD" "$REPO/.pydeps" -maxdepth 3 -name 'sieans_native*.so' 2>/dev/null | head -1 || true)"
if [[ -n "$MOD" ]]; then
  mkdir -p "$REPO/.pydeps"
  cp -f "$MOD" "$REPO/.pydeps/"
  echo "installed: $REPO/.pydeps/$(basename "$MOD")"
else
  echo "warning: sieans_native.so not found after build" >&2
  exit 1
fi
echo "build ok — try: PYTHONPATH=$REPO/.pydeps python3 -c 'import sieans_native as n; print(n.version(), n.gentl_available())'"
