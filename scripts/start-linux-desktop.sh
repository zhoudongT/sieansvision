#!/usr/bin/env bash
# SIEANS Vision 原生桌面工作台（PySide6）。默认打开 MV相机→OCR 工程。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/64:${LD_LIBRARY_PATH:-}
export SIEANS_GENTL_CTI=/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti
export PYTHONPATH="$ROOT/.pydeps${PYTHONPATH:+:$PYTHONPATH}"
export VISION_PYTHON="${VISION_PYTHON:-$(command -v python3)}"
export DISPLAY="${DISPLAY:-:0}"
if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi
DATA="${1:-$ROOT/data/native-desktop}"
PROJECT="${SIEANS_PROJECT:-$ROOT/projects/mv-camera-ocr.sieans}"
mkdir -p "$DATA"
echo "SIEANS Vision 原生工作台"
echo "  数据目录：$DATA（与网页服务隔离）"
echo "  工程：$PROJECT"
echo "  用法：工具栏「运行流程」= MV GenTL 取图 → RapidOCR；或 演示工程 → MV相机 → 字符识别 OCR"
echo "  连续预览：设备与模型 → 相机与连续采集（勿与网页/MVS 同时占 USB）"
exec "$VISION_PYTHON" -m desktop.main --root "$ROOT" --data "$DATA" --project "$PROJECT"
