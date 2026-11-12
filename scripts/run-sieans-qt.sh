#!/usr/bin/env bash
# Foreground launch (stdout to terminal). For debug / smoke.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/qtapp/build/sieans_qt"
export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
EXTRA_LIBS="$HOME/Qt/extra-libs"
export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
[[ -d "$EXTRA_LIBS" ]] && export LD_LIBRARY_PATH="$EXTRA_LIBS:$LD_LIBRARY_PATH"
XCB_CURSOR_LIB="${SIEANS_XCB_CURSOR_DIR:-$HOME/.local/opt/xcb-cursor}/usr/lib/x86_64-linux-gnu"
[[ -d "$XCB_CURSOR_LIB" ]] && export LD_LIBRARY_PATH="$XCB_CURSOR_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export DISPLAY="${DISPLAY:-:0}"
for cand in "$HOME/Qt/6.7.3/gcc_64" "$HOME/Qt/6.8.3/gcc_64" "$HOME/Qt/6.8.0/gcc_64"; do
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
[[ -x "$BIN" ]] || "$ROOT/qtapp/scripts/build.sh"
exec "$BIN" "$@"
