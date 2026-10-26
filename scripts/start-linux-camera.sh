#!/usr/bin/env bash
# Start sieansvision with Hikrobot GenTL env. Close MVS Client first (exclusive USB).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Stop MVS Client if holding camera (optional prompt-free kill — comment out if undesired)
# pkill -f '/opt/MVS/bin/MVS' || true
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/64:${LD_LIBRARY_PATH:-}
export SIEANS_GENTL_CTI=/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti
export PYTHONPATH="$ROOT/.pydeps${PYTHONPATH:+:$PYTHONPATH}"
export HOST=127.0.0.1
export PORT="${PORT:-1880}"
echo "Close MVS Client before opening the camera in the workbench (USB exclusive)."
echo "Workbench: http://127.0.0.1:${PORT}/vision/"
exec npm start
