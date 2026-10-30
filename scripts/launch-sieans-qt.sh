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

if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
  else
    export QT_QPA_PLATFORM=xcb
  fi
fi

if [[ ! -x "$BIN" ]]; then
  echo "sieans_qt not built — running qtapp/scripts/build.sh …"
  "$ROOT/qtapp/scripts/build.sh"
fi

mkdir -p "$ROOT/artifacts"
LOG="$ROOT/artifacts/sieans-qt.log"
echo "launching $BIN (log: $LOG)"
exec "$BIN" "$@" >>"$LOG" 2>&1
