#!/usr/bin/env bash
# 仅从自身目录装载发行依赖，不引用开发机器 Qt/用户前缀；不构建、不联网。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export SIEANS_REPO="$ROOT"
export LD_LIBRARY_PATH="$ROOT/lib:$ROOT/ort/lib:$ROOT/tesseract/usr/lib/x86_64-linux-gnu"
export QT_PLUGIN_PATH="$ROOT/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$ROOT/plugins/platforms"
unset QT_QPA_PLATFORMTHEME
export SIEANS_ONNXRUNTIME_DIR="$ROOT/ort"
export SIEANS_TESSERACT="$ROOT/tesseract/usr/bin/tesseract"
export TESSDATA_PREFIX="$ROOT/tesseract/usr/share/tesseract-ocr/5/tessdata"
export SIEANS_QT_USER_DATA="${SIEANS_QT_USER_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/sieans}"
export SIEANS_QT_LOG_DIR="${SIEANS_QT_LOG_DIR:-$SIEANS_QT_USER_DATA/logs}"
export SIEANS_QT_ARTIFACTS="${SIEANS_QT_ARTIFACTS:-$SIEANS_QT_USER_DATA/artifacts}"
if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == wayland || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi
exec "$ROOT/qtapp/build/sieans_qt" "$@"
