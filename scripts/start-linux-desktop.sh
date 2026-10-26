#!/usr/bin/env bash
# Native PySide6 workbench with Hikrobot GenTL env. Do not run web server against the same data dir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/64:${LD_LIBRARY_PATH:-}
export SIEANS_GENTL_CTI=/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti
export PYTHONPATH="$ROOT/.pydeps${PYTHONPATH:+:$PYTHONPATH}"
export VISION_PYTHON="${VISION_PYTHON:-$(command -v python3)}"
export DISPLAY="${DISPLAY:-:0}"
# PySide6 on this GNOME box: wayland works; xcb needs libxcb-cursor0.
if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi
DATA="${1:-$ROOT/data/native-desktop}"
mkdir -p "$DATA"
echo "原生桌面：设备与模型 → 相机与连续采集 → GenTL → 枚举 → 打开所选相机并持续采集"
echo "数据目录：$DATA（与网页服务隔离）"
exec "$VISION_PYTHON" -m desktop.main --root "$ROOT" --data "$DATA"
