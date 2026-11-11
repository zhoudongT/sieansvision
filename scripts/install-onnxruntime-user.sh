#!/usr/bin/env bash
# 将官方 Microsoft ONNX Runtime（Linux x64 CPU）安装到用户前缀，无需 sudo。
# 来源：https://github.com/microsoft/onnxruntime/releases/tag/v1.31.1
# 资源：onnxruntime-linux-x64-1.31.1.tgz
# SHA-256（GitHub API asset digest，安装时校验）：
#   c849e36a1ef3e22d4ff217b9d1ce4a3cf5b9467b975610913ae959ad5b16bdc9
#
# 默认前缀：$HOME/.local/opt/onnxruntime
# 覆盖：SIEANS_ONNXRUNTIME_DIR（安装目标） / SIEANS_ONNXRUNTIME_CACHE
# 直连 GitHub 较慢时可设 SIEANS_ONNXRUNTIME_URL 指向同一文件的镜像，仍按上述 SHA 校验。
set -euo pipefail

VER="1.31.1"
FILE="onnxruntime-linux-x64-${VER}.tgz"
SHA="c849e36a1ef3e22d4ff217b9d1ce4a3cf5b9467b975610913ae959ad5b16bdc9"
DEFAULT_URL="https://github.com/microsoft/onnxruntime/releases/download/v${VER}/${FILE}"
URL="${SIEANS_ONNXRUNTIME_URL:-$DEFAULT_URL}"
PREFIX="${SIEANS_ONNXRUNTIME_DIR:-$HOME/.local/opt/onnxruntime}"
CACHE="${SIEANS_ONNXRUNTIME_CACHE:-$HOME/.local/src/onnxruntime}"

mkdir -p "$CACHE"
cd "$CACHE"
if [[ ! -f "$FILE" ]] || ! echo "$SHA  $FILE" | sha256sum -c --status -; then
  rm -f "$FILE"
  echo "downloading official ONNX Runtime $VER from $URL"
  curl -L --fail --retry 3 --connect-timeout 20 -o "$FILE" "$URL"
fi
echo "$SHA  $FILE" | sha256sum -c -

rm -rf "$PREFIX" "${CACHE}/onnxruntime-linux-x64-${VER}"
tar -xzf "$FILE"
mkdir -p "$(dirname "$PREFIX")"
mv "onnxruntime-linux-x64-${VER}" "$PREFIX"
{
  echo "# Official Microsoft ONNX Runtime Linux x64"
  echo "# url=$URL"
  echo "# release=https://github.com/microsoft/onnxruntime/releases/tag/v${VER}"
  echo "# sha256=$SHA"
  echo "# unpacked=$(date -R)"
  sha256sum "$FILE"
} > "$PREFIX/SIEANS-ONNXRUNTIME-ORIGIN.txt"

test -f "$PREFIX/include/onnxruntime_c_api.h"
test -e "$PREFIX/lib/libonnxruntime.so"
echo "installed: $PREFIX"
echo "lib:       $PREFIX/lib/libonnxruntime.so"
echo "origin:    $PREFIX/SIEANS-ONNXRUNTIME-ORIGIN.txt"
