#!/usr/bin/env bash
# Foreground launch (stdout to terminal). For debug / smoke.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/qtapp/build/sieans_qt"
export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
EXTRA_LIBS="$HOME/Qt/extra-libs"
export LD_LIBRARY_PATH="/opt/MVS/lib/64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
[[ -d "$EXTRA_LIBS" ]] && export LD_LIBRARY_PATH="$EXTRA_LIBS:$LD_LIBRARY_PATH"
export DISPLAY="${DISPLAY:-:0}"
for cand in "$HOME/Qt/6.7.3/gcc_64" "$HOME/Qt/6.8.3/gcc_64" "$HOME/Qt/6.8.0/gcc_64"; do
  if [[ -d "$cand/lib" ]]; then
    export LD_LIBRARY_PATH="$cand/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export QT_PLUGIN_PATH="${QT_PLUGIN_PATH:-$cand/plugins}"
    break
  fi
done
[[ -z "${QT_QPA_PLATFORM:-}" ]] && export QT_QPA_PLATFORM=xcb
[[ -x "$BIN" ]] || "$ROOT/qtapp/scripts/build.sh"
exec "$BIN" "$@"
