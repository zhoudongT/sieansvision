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
- GenTL **session_worker** / harvesters path used by the App live preview
  (C++ GenTL is available via `sieans_native.GenTLCapture` for next wave swap)
- OCR / YOLO / template matching / Halcon / robot SDK (untouched)

## Architecture

```
PySide6 UI  →  engine-host  →  vision/engine.py::barcode()
                                    ├─ sieans_native.decode_barcodes  (C++ zxing)
                                    └─ fallback: zxingcpp (Python)
GenTL live  →  cameras/session_worker (Python harvesters)  [unchanged]
            ↛  sieans_native.GenTLCapture                  [ready, opt-in]
```
