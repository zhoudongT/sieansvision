#!/usr/bin/env bash
# 将 Ubuntu 官方 Tesseract（eng + chi_sim + osd）解压到用户前缀，无需 sudo。
# 软件包来自本机已配置的 apt 源（noble: tesseract 5.3.4 / tessdata 4.1.0）。
# apt-get download 会按已签名的 Packages 索引校验 deb 校验和，不使用来路不明的二进制。
#
# 默认安装：
#   二进制包装：$HOME/.local/bin/tesseract
#   前缀：$HOME/.local/opt/tesseract
#   语言包：$HOME/.local/opt/tesseract/usr/share/tesseract-ocr/5/tessdata
#
# 覆盖变量：SIEANS_TESSERACT_PREFIX / SIEANS_TESSERACT_CACHE / SIEANS_TESSERACT_BIN
# Qt OCR 算子会查找 PATH、$HOME/.local/bin、上述前缀，以及 TESSDATA_PREFIX / SIEANS_TESSERACT。
set -euo pipefail

PREFIX="${SIEANS_TESSERACT_PREFIX:-$HOME/.local/opt/tesseract}"
CACHE="${SIEANS_TESSERACT_CACHE:-$HOME/.local/src/tesseract-debs}"
BIN_LINK="${SIEANS_TESSERACT_BIN:-$HOME/.local/bin/tesseract}"

PACKAGES=(
  tesseract-ocr
  tesseract-ocr-eng
  tesseract-ocr-chi-sim
  tesseract-ocr-osd
  libtesseract5
  liblept5
)

mkdir -p "$CACHE" "$PREFIX" "$(dirname "$BIN_LINK")"
cd "$CACHE"
rm -f ./*.deb
echo "downloading official Ubuntu Tesseract debs via apt-get…"
apt-get download "${PACKAGES[@]}"

for deb in ./*.deb; do
  echo "extract $(basename "$deb")"
  dpkg-deb -x "$deb" "$PREFIX"
done

{
  echo "# User-local Tesseract extracted from official Ubuntu debs"
  echo "# apt-get download verifies hashes against the signed Packages index"
  echo "# prefix=$PREFIX"
  echo "# unpacked=$(date -R)"
  echo
  for deb in ./*.deb; do
    echo "file=$(basename "$deb")"
    echo "Package=$(dpkg-deb -f "$deb" Package)"
    echo "Version=$(dpkg-deb -f "$deb" Version)"
    echo "Architecture=$(dpkg-deb -f "$deb" Architecture)"
    sha256sum "$deb"
    echo
  done
} > "$PREFIX/SIEANS-TESSERACT-ORIGIN.txt"

TESSDATA="$PREFIX/usr/share/tesseract-ocr/5/tessdata"
REALBIN="$PREFIX/usr/bin/tesseract"
if [[ ! -x "$REALBIN" ]]; then
  echo "error: $REALBIN missing after extract" >&2
  exit 1
fi
if [[ ! -f "$TESSDATA/eng.traineddata" ]]; then
  echo "error: eng.traineddata missing under $TESSDATA" >&2
  exit 1
fi

# Ubuntu 5.3.4 把 TESSDATA_PREFIX 当作 tessdata 目录本身。
cat > "$BIN_LINK" <<'WRAP'
#!/usr/bin/env bash
# SIEANS user-local Tesseract wrapper (Ubuntu official debs, no sudo).
# Ubuntu 5.3.4 expects TESSDATA_PREFIX to be the tessdata directory itself.
prefix="${HOME}/.local/opt/tesseract"
export LD_LIBRARY_PATH="${prefix}/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if [[ -z "${TESSDATA_PREFIX:-}" ]]; then
  export TESSDATA_PREFIX="${prefix}/usr/share/tesseract-ocr/5/tessdata"
fi
exec "${prefix}/usr/bin/tesseract" "$@"
WRAP
# If the caller overrode the prefix, rewrite wrapper paths accordingly.
if [[ "$PREFIX" != "$HOME/.local/opt/tesseract" ]]; then
  cat > "$BIN_LINK" <<WRAP
#!/usr/bin/env bash
# SIEANS user-local Tesseract wrapper (Ubuntu official debs, no sudo).
prefix="${PREFIX}"
export LD_LIBRARY_PATH="\${prefix}/usr/lib/x86_64-linux-gnu\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
if [[ -z "\${TESSDATA_PREFIX:-}" ]]; then
  export TESSDATA_PREFIX="\${prefix}/usr/share/tesseract-ocr/5/tessdata"
fi
exec "\${prefix}/usr/bin/tesseract" "\$@"
WRAP
fi
chmod +x "$BIN_LINK"

# Only link the default user tessdata path when installing to the default prefix.
# Override prefixes (doctor --prove-install temp dirs) must not steal this symlink.
if [[ "$PREFIX" == "$HOME/.local/opt/tesseract" ]]; then
  mkdir -p "$HOME/.local/share"
  if [[ ! -e "$HOME/.local/share/tessdata" ]]; then
    ln -s "$TESSDATA" "$HOME/.local/share/tessdata"
  fi
fi

export LD_LIBRARY_PATH="$PREFIX/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TESSDATA_PREFIX="$TESSDATA"
"$REALBIN" --version
"$BIN_LINK" --list-langs
echo "installed: $BIN_LINK"
echo "realbin:   $REALBIN"
echo "tessdata:  $TESSDATA"
echo "origin:    $PREFIX/SIEANS-TESSERACT-ORIGIN.txt"
