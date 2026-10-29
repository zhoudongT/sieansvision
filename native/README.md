# sieans_native — C++ algorithm layer

Vertical slice: **QR/barcode decode** (+ optional **GenTL capture** via Hikrobot
MvCameraControl) behind the existing PySide6 shell. UI / Host / camera dialogs
stay Python; set `SIEANS_NATIVE=1` (default `auto`) to prefer C++ decode.

## Layout

| Path | Role |
|------|------|
| `include/sieans/` | C++ public headers (`barcode`, `gentl_capture`) |
| `src/` | Implementations |
| `python/module.cpp` | pybind11 module `sieans_native` |
| `third_party/zxing-cpp` | Vendored [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp) v2.2.1 |
| `scripts/build.sh` | Configure + build + install `.so` into `../.pydeps/` |

## Build (Ubuntu / allen-MCLG-XX)

```bash
# deps already on MCLG-XX: cmake, g++, python3-dev, pybind11-dev, /opt/MVS
./native/scripts/build.sh
```

Manual:

```bash
cmake -S native -B native/build -DCMAKE_BUILD_TYPE=Release -DSIEANS_NATIVE_GENTL=ON
cmake --build native/build -j$(nproc)
# module copied to .pydeps/sieans_native*.so
```

## Feature flag

| `SIEANS_NATIVE` | Behavior |
|-----------------|----------|
| `auto` (default) | Try C++ decode; fall back to Python `zxingcpp` |
| `1` / `on` / `force` | Require C++ (`sieans_native` must import) |
| `0` / `off` / `python` | Force Python zxing-cpp path |

Launch script adds `REPO/.pydeps` to `PYTHONPATH` (unchanged). After rebuild,
restart App (`SIEANS_FORCE=1 ./打开SIEANS视觉工作台.sh`).

## Smoke

```bash
PYTHONPATH=.pydeps python3 native/scripts/smoke_decode.py
# optional live GenTL (only if built with MVS):
PYTHONPATH=.pydeps python3 - <<'PY'
import sieans_native as n
print(n.gentl_available())
if n.gentl_available():
    print(n.GenTLCapture.enumerate())
PY
```

## What stays Python (this wave)

- PySide6 shell, Host, camera manager dialogs, TCP/comms
- GenTL **inspect / 3D / software·external trigger** still use harvesters
- OCR / YOLO / template matching / Halcon / robot SDK (untouched)

## Live GenTL acquire (wave2)

Continuous 2D freerun (`session_worker` → `cameras.adapter.acquire_gentl_frames`)
prefers **C++ `sieans_native.GenTLCapture`** when the module is built with MVS.
Hang mitigations kept: `LatestImagesOnly` drop-old, `acquisitionFrameRate` cap,
`previewBufferCount`, paced interval + idle heartbeat (no JPEG flood), off-GUI
JPEG decode (fd72066 lineage).

| Env | Acquire path |
|-----|----------------|
| `SIEANS_NATIVE=auto` (default) | C++ if `gentl_available()`, else harvesters |
| `SIEANS_NATIVE=1` / `force` | Require C++ GenTL |
| `SIEANS_NATIVE=python` | Force harvesters |
| `SIEANS_NATIVE_GENTL_ACQUIRE=0` | Force harvesters (decode may still be C++) |
| `SIEANS_NATIVE_GENTL_ACQUIRE=1` | Require C++ GenTL acquire |

Evidence: frame `result.acquireBackend=sieans_native`, stderr
`[sieans] GenTL acquire backend=sieans_native`, `/tmp/sieans-gentl-acquire-backend.txt`.

## Architecture

```
PySide6 UI  →  engine-host  →  vision/engine.py::barcode()
                                    ├─ sieans_native.decode_barcodes  (C++ zxing)
                                    └─ fallback: zxingcpp (Python)
GenTL live  →  cameras/session_worker
                  └─ adapter.acquire_gentl_frames
                        ├─ sieans_native.GenTLCapture   (2D freerun, preferred)
                        └─ harvesters                   (fallback / 3D / inspect)
```
