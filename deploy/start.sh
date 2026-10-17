#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
  echo "Usage: sh deploy/start.sh /absolute/runtime-data-directory" >&2
  exit 2
fi
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec node "$SCRIPT_DIR/../scripts/platform.cjs" start --data-dir "$1"
