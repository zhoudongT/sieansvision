#!/usr/bin/env bash
# Native App: Hikrobot GenTL live + RapidOCR character recognition.
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
echo "相机 + 字符识别 App（RapidOCR）· 平台 $QT_QPA_PLATFORM"
echo "请先关闭网页 / MVS / 其它占用 U3V 的预览"
echo "窗口内点「字符识别」；回车同效；Q/Esc 退出"
exec python3 -u "$ROOT/scripts/camera-ocr-app.py"
