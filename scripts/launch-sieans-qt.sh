#!/usr/bin/env bash
# Launch SIEANS Vision Qt framework shell (C++ core + Qt6 UI).
# Does NOT replace scripts/launch-sieans-vision.sh (PySide path stays intact).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/qtapp/build/sieans_qt"

export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
EXTRA_LIBS="$HOME/Qt/extra-libs"
export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
[[ -d "$EXTRA_LIBS" ]] && export LD_LIBRARY_PATH="$EXTRA_LIBS:$LD_LIBRARY_PATH"
XCB_CURSOR_LIB="${SIEANS_XCB_CURSOR_DIR:-$HOME/.local/opt/xcb-cursor}/usr/lib/x86_64-linux-gnu"
[[ -d "$XCB_CURSOR_LIB" ]] && export LD_LIBRARY_PATH="$XCB_CURSOR_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
ORT_LIB="${SIEANS_ONNXRUNTIME_DIR:-$HOME/.local/opt/onnxruntime}/lib"
[[ -d "$ORT_LIB" ]] && export LD_LIBRARY_PATH="$ORT_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export DISPLAY="${DISPLAY:-:0}"

# Prefer aqt Qt runtime libs when present.
for cand in \
    "$HOME/Qt/6.7.3/gcc_64" \
    "$HOME/Qt/6.8.3/gcc_64" \
    "$HOME/Qt/6.8.0/gcc_64"; do
  if [[ -d "$cand/lib" ]]; then
    export LD_LIBRARY_PATH="$cand/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export QT_PLUGIN_PATH="${QT_PLUGIN_PATH:-$cand/plugins}"
    break
  fi
done


# Prefer Wayland in a Wayland session; otherwise xcb. Allow callers to override.
if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi
# 平台主题由用户/桌面决定；portal 覆盖实测未消除 Gdk 警告，不强改。

if [[ ! -x "$BIN" ]]; then
  echo "sieans_qt not built — running qtapp/scripts/build.sh …"
  "$ROOT/qtapp/scripts/build.sh"
fi

mkdir -p "$ROOT/artifacts"
# stderr 会话按进程隔离；历史聚合日志不再继续无限追加。
LOG_DIR="${SIEANS_QT_LOG_DIR:-$HOME/.local/share/sieans/logs}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/console-$$.log"
# 控制台文件只有启动警告；Qt 持久日志另由 RuntimeDiagnostics 有界轮转。
python3 - "$LOG_DIR" <<'CLEAN'
import sys
from pathlib import Path
files=sorted(Path(sys.argv[1]).glob("console-*.log"), key=lambda p:p.stat().st_mtime, reverse=True)
for p in files[20:]:
    pid=p.stem.split("-")[-1]
    if not Path("/proc",pid).exists(): p.unlink(missing_ok=True)
CLEAN
echo "launching $BIN (log: $LOG)"
exec "$BIN" "$@" >>"$LOG" 2>&1
