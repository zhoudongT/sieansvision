#!/usr/bin/env bash
# 兼容入口：转入 sieansvision 原生工作台的「MV相机 → 字符识别」工程。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SIEANS_PROJECT="${SIEANS_PROJECT:-$ROOT/projects/mv-camera-ocr.sieans}"
exec "$ROOT/scripts/start-linux-desktop.sh" "$@"
