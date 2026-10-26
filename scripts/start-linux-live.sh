#!/usr/bin/env bash
# Smooth GenTL continuous preview (PySide6 App — not web, not OpenCV HighGUI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/64:${LD_LIBRARY_PATH:-}
export SIEANS_GENTL_CTI=/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti
export PYTHONPATH="$ROOT/.pydeps${PYTHONPATH:+:$PYTHONPATH}"
export DISPLAY="${DISPLAY:-:0}"
if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi
export PYTHONUNBUFFERED=1
echo "原生连续预览（App）：$QT_QPA_PLATFORM  关闭窗口或按 Q/Esc 结束"
echo "请先关闭网页 :1880 / MVS Client / 其它占用 U3V 的进程"
exec python3 -u "$ROOT/scripts/live-mv-preview.py"
