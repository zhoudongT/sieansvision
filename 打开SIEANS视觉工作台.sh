#!/usr/bin/env bash
# 双击打开「SIEANS Vision 视觉检测平台」完整工作台
ROOT="$(cd "$(dirname "$0")" && pwd)"
export SIEANS_FORCE="${SIEANS_FORCE:-1}"
exec "$ROOT/scripts/launch-sieans-vision.sh" "$@"
