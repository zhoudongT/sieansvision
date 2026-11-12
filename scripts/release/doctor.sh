#!/usr/bin/env bash
# 发行目录装前检查：只读 ABI/依赖/完整性，不需要编译器、sudo 或网络。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export LD_LIBRARY_PATH="$ROOT/lib:$ROOT/ort/lib:$ROOT/tesseract/usr/lib/x86_64-linux-gnu"
cd "$ROOT"
sha256sum --quiet -c SHA256SUMS
fail=0
while IFS= read -r -d '' elf; do
  deps="$(ldd "$elf" 2>&1)" || { echo "FAIL ldd $elf: $deps"; fail=1; continue; }
  if [[ "$deps" == *"not found"* ]]; then echo "FAIL $elf: $deps"; fail=1; fi
done < <(find qtapp/build lib plugins ort/lib tesseract/usr/bin -type f \( -name '*.so*' -o -name sieans_qt -o -name tesseract \) -print0)
echo "release: $(cat VERSION)"
echo "host: $(uname -sm); $(getconf GNU_LIBC_VERSION)"
echo 'GenTL / real PLC / official YOLO weights: NOT ACCEPTED; stub models are only software chain tests.'
if compgen -G '/dev/video*' >/dev/null; then echo 'UVC nodes present: validate actual capture separately'; else echo 'UVC: no /dev/video* nodes'; fi
[[ "$fail" == 0 ]] && echo 'doctor PASS (checksum + dynamic dependencies only; display/hardware not certified)'
exit "$fail"
