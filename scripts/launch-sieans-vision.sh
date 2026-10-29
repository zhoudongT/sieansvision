#!/usr/bin/env bash
# SIEANS Vision — 一键打开「完整视觉检测平台」工作台
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SIEANS_GENTL_CTI="${SIEANS_GENTL_CTI:-/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti}"
export PYTHONPATH="$ROOT/.pydeps${PYTHONPATH:+:$PYTHONPATH}"

# Prefer C++ sieans_native barcode when .pydeps has the module (auto-fallback).
export SIEANS_NATIVE="${SIEANS_NATIVE:-auto}"
# Hikrobot MvCameraControl for optional C++ GenTL
if [[ -d /opt/MVS/lib/64 ]]; then
  export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
fi
export VISION_PYTHON="${VISION_PYTHON:-$(command -v python3)}"
export DISPLAY="${DISPLAY:-:0}"

if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi

DATA="${SIEANS_DATA:-$ROOT/data/native-desktop}"
# Default: blank platform workbench — NOT a locked OCR demo.
# Override: SIEANS_PROJECT=path/to/foo.sieans
PROJECT="${SIEANS_PROJECT:-$ROOT/projects/default-platform.sieans}"
LOG_DIR="$ROOT/artifacts"
LOG="$LOG_DIR/desktop-app.log"
mkdir -p "$DATA" "$LOG_DIR"

say() { printf '%s\n' "$*"; }
die() { say "❌ $*"; exit 1; }

EXISTING="$(pgrep -f 'python3 -m desktop.main' || true)"
if [[ -n "$EXISTING" ]]; then
  say "检测到已有 SIEANS Vision 平台进程（PID: $EXISTING）。"
  if [[ "${SIEANS_FORCE:-}" == "1" ]]; then
    say "SIEANS_FORCE=1：正在结束旧进程以便重新打开平台…"
    pkill -f 'python3 -m desktop.main' 2>/dev/null || true
    pkill -f 'cameras/session_worker.py' 2>/dev/null || true
    sleep 1
  else
    say "将保留已有窗口。强制重启：SIEANS_FORCE=1 $0"
    command -v wmctrl >/dev/null 2>&1 && wmctrl -a 'SIEANS Vision' 2>/dev/null || true
    exit 0
  fi
fi

HOLDERS=()
if pgrep -af 'MvViewer|MVSClient' 2>/dev/null | grep -vq MvLogServer; then
  HOLDERS+=("海康 MVS 客户端可能占用 USB 相机")
fi
if pgrep -af 'node.*(server\.cjs|node-red)' 2>/dev/null | grep -q .; then
  HOLDERS+=("网页视觉服务可能占用相机（请先关掉网页采集）")
fi
if ((${#HOLDERS[@]})); then
  say "⚠️  设备占用提示："
  for h in "${HOLDERS[@]}"; do say "   · $h"; done
fi

say "SIEANS Vision 视觉检测平台 — 启动自检"
CHECK_OUT="$("$VISION_PYTHON" -m desktop.startup_check 2>/dev/null | grep -v 'does not implement' || true)"
say "$CHECK_OUT"
"$VISION_PYTHON" -c "import PySide6" 2>/dev/null || die "缺少 PySide6。请执行：python3 -m pip install -t .pydeps -r desktop/requirements.txt"
[[ -f "$PROJECT" ]] || die "默认工程不存在：$PROJECT"

say ""
say "正在打开完整工作台（算子库 · 流程编辑 · 设备 · 运行 · 演示）…"
say "  工程：$PROJECT"
say "  数据：$DATA"
say "  日志：$LOG"
say ""

if [[ -t 1 && "${SIEANS_FOREGROUND:-}" == "1" ]]; then
  exec "$VISION_PYTHON" -m desktop.main --root "$ROOT" --data "$DATA" --project "$PROJECT"
fi

nohup "$VISION_PYTHON" -m desktop.main --root "$ROOT" --data "$DATA" --project "$PROJECT" \
  >>"$LOG" 2>&1 &
PID=$!
sleep 2
if ! kill -0 "$PID" 2>/dev/null; then
  say "启动失败，最近日志："; tail -40 "$LOG" || true; exit 1
fi
say "✅ 视觉检测平台已启动（PID $PID）"
say "   左侧选算子 → 画布连线 → ▶ 运行流程；或 文件→从模板新建 / 演示工程"
