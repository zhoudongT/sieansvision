#!/usr/bin/env bash
# 复制到全新用户目录；拒绝覆盖已有版本，不改现场工程/偏好。可选创建用户桌面启动项。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$HOME/.local/opt/sieans-$(cat "$ROOT/VERSION")}"
"$ROOT/doctor.sh"
[[ ! -e "$DEST" ]] || { echo "refuse existing destination: $DEST" >&2; exit 2; }
mkdir -p "$(dirname "$DEST")"
cp -a "$ROOT" "$DEST"
if [[ "${2:-}" == --desktop ]]; then
  # desktop Exec uses double-quote escaping, not a shell command; reject newlines/metacharacters.
  [[ "$DEST" != *$'\n'* && "$DEST" != *'"'* && "$DEST" != *'`'* && "$DEST" != *'$'* && "$DEST" != *'%'* && "$DEST" != *'\'* ]] || { echo 'unsupported desktop path' >&2; exit 2; }
  dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$dir"
  file="$dir/sieans-$(cat "$ROOT/VERSION").desktop"
  [[ ! -e "$file" ]] || { echo "refuse existing desktop entry: $file" >&2; exit 2; }
  printf '[Desktop Entry]\nType=Application\nName=SIEANS Vision\nExec="%s/run.sh"\nPath=%s\nTerminal=false\nCategories=Graphics;Engineering;\n' "$DEST" "$DEST" > "$file"
fi
printf 'installed %s; run %s/run.sh\n' "$DEST" "$DEST"
