#!/usr/bin/env bash
# 将 Ubuntu 官方 libxcb-cursor0 解压到用户前缀，无需 sudo。
# 用于 Qt xcb 平台插件（6.5+ 需要 libxcb-cursor）。不安装 FreeCAD 或其它整套库。
# 来源：Ubuntu noble universe amd64 libxcb-cursor0 0.1.4-1build1
# SHA-256（Packages 记录，安装时校验）：
#   137cf52479b5a9d8c5926d70d311af04be41941a32ee777340d704cc458c06d8
#
# 默认前缀：$HOME/.local/opt/xcb-cursor
# 覆盖：SIEANS_XCB_CURSOR_DIR / SIEANS_XCB_CURSOR_CACHE / SIEANS_XCB_CURSOR_URL
set -euo pipefail

VER="0.1.4-1build1"
FILE="libxcb-cursor0_${VER}_amd64.deb"
SHA="137cf52479b5a9d8c5926d70d311af04be41941a32ee777340d704cc458c06d8"
DEFAULT_URL="http://cn.archive.ubuntu.com/ubuntu/pool/universe/x/xcb-util-cursor/${FILE}"
URL="${SIEANS_XCB_CURSOR_URL:-$DEFAULT_URL}"
PREFIX="${SIEANS_XCB_CURSOR_DIR:-$HOME/.local/opt/xcb-cursor}"
CACHE="${SIEANS_XCB_CURSOR_CACHE:-$HOME/.local/src/xcb-cursor}"

mkdir -p "$CACHE"
cd "$CACHE"
if [[ ! -f "$FILE" ]] || ! echo "$SHA  $FILE" | sha256sum -c --status -; then
  rm -f "$FILE"
  echo "downloading Ubuntu $FILE from $URL"
  curl -L --fail --retry 3 --connect-timeout 20 -o "$FILE" "$URL"
fi
echo "$SHA  $FILE" | sha256sum -c -

rm -rf "$PREFIX"
mkdir -p "$PREFIX"
dpkg-deb -x "$FILE" "$PREFIX"
LIBDIR="$PREFIX/usr/lib/x86_64-linux-gnu"
if [[ ! -e "$LIBDIR/libxcb-cursor.so.0" ]]; then
  echo "extract failed: $LIBDIR/libxcb-cursor.so.0 missing" >&2
  exit 1
fi
{
  echo "# Ubuntu libxcb-cursor0 $VER (user prefix, no sudo)"
  echo "# url=$URL"
  echo "# sha256=$SHA"
  echo "# unpacked=$(date -R)"
  sha256sum "$FILE"
} > "$PREFIX/SIEANS-ORIGIN.txt"
echo "installed $LIBDIR/libxcb-cursor.so.0"
echo "launch scripts add this directory to LD_LIBRARY_PATH"
