# Qt 工作台：从检出构建并运行（无需 sudo）

本文说明如何在一台新的 Linux 机器上，从本仓库检出构建并启动 `sieans_qt`（Qt 6 Widgets 工作台）。目标是**用户目录即可跑起来**，不提供沉重的安装包。已在 Ubuntu 24.04（B760M）上按本文路径核过。

配套自检：

```bash
./scripts/doctor-sieans-qt.sh            # 检查依赖与路径
./scripts/doctor-sieans-qt.sh --selftest # 再跑路径/存档自检
./scripts/doctor-sieans-qt.sh --prove-install  # 在临时目录重跑用户级安装脚本并校验
```

`--prove-install` 只写到临时前缀，不会覆盖已有的 `$HOME/.local/opt/tesseract` 或 `$HOME/.local/opt/onnxruntime`。工作台**不会自动下载**官方 YOLO 权重。

## 1. 一次性系统工具（仅在缺失时需要 sudo）

构建需要：`cmake`（≥ 3.16）、`g++`、`make`、`curl`、`python3`。Ubuntu 24.04 可用：

```bash
sudo apt-get install -y build-essential cmake curl python3
```

若没有 sudo，这些工具必须已经在 PATH 上；其余依赖都可以装到 `$HOME` 下。图形会话下一般已有 Qt 运行所需的 X11/Wayland 库（如 `libgl1`）。Qt 6.5+ 的 xcb 插件还需要 `libxcb-cursor0`；没有系统包时运行 `scripts/install-xcb-cursor-user.sh` 解压到 `$HOME/.local/opt/xcb-cursor`（Ubuntu 官方 deb，SHA-256 校验，无需 sudo）。不要用整套 FreeCAD 库充当 Qt 运行依赖。Wayland 会话下启动脚本默认走 wayland 平台。无界面冒烟用 `QT_QPA_PLATFORM=offscreen`，不依赖显示器。

把 `$HOME/.local/bin` 放进 PATH（未加时用户级 `tesseract` 包装可能找不到）：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 2. 用户级 Qt 6.7.3

构建脚本按以下顺序查找前缀（可用 `SIEANS_QT_PREFIX` 覆盖）：

- `$HOME/Qt/6.7.3/gcc_64`（推荐，本文路径）
- `$HOME/Qt/6.8.3/gcc_64`、`$HOME/Qt/6.8.0/gcc_64`、`$HOME/Qt/6.6.3/gcc_64`
- 系统 Qt 6（`qt6-base-dev`，通常需要 sudo）

在已有 Python 3 的机器上用官方 aqt 安装到用户目录（无需 sudo）：

```bash
python3 -m pip install --user aqtinstall
python3 -m aqt install-qt linux desktop 6.7.3 gcc_64 --outputdir "$HOME/Qt"
```

装好后应存在 `$HOME/Qt/6.7.3/gcc_64/lib/cmake/Qt6/Qt6Config.cmake`。

## 3. 可选用户级算法运行时（无需 sudo）

| 能力 | 安装脚本 | 默认位置 | 缺失时的行为 |
|------|----------|----------|--------------|
| OCR（Tesseract，eng + chi_sim） | `scripts/install-tesseract-user.sh` | 包装 `$HOME/.local/bin/tesseract`，前缀 `$HOME/.local/opt/tesseract` | OCR 算子报告不可用，其他流程可跑 |
| YOLO ONNX Runtime（官方 CPU v1.31.1，安装时校验 SHA-256） | `scripts/install-onnxruntime-user.sh` | `$HOME/.local/opt/onnxruntime` | 检测算子回退 `backend=software`，算子仍成功 |
| Qt xcb 光标库（libxcb-cursor0，安装时校验 SHA-256） | `scripts/install-xcb-cursor-user.sh` | `$HOME/.local/opt/xcb-cursor` | xcb 平台插件无法加载；Wayland / offscreen 不受影响 |

Tesseract 脚本通过已配置 apt 源的 `apt-get download` 拉取 **Ubuntu 官方 deb**（不需要 sudo），解压到用户前缀。本机 Ubuntu 5.3.4 要求 `TESSDATA_PREFIX` 指向 **tessdata 目录本身**（包装脚本已处理）。

ONNX Runtime 默认从 [Microsoft 官方 Release v1.31.1](https://github.com/microsoft/onnxruntime/releases/tag/v1.31.1) 下载 `onnxruntime-linux-x64-1.31.1.tgz`。直连 GitHub 较慢时可设 `SIEANS_ONNXRUNTIME_URL` 指向**同一文件**的镜像，脚本仍按内置 SHA-256 校验。

YOLO 权重需自行放到仓库 `models/`、`$HOME/.local/share/sieans/models/`，或设 `SIEANS_YOLO_MODELS_DIR`。无 `.onnx`、只有 `.pt`、或推理失败时回退 software，**不会自动下载官方权重**。仓库内 `models/sieans-yolo-smoke.onnx` 只是链路烟测桩，不是工业模型。详见 [models/README.md](../models/README.md)。

海康 `/opt/MVS`（GenTL）是可选硬件依赖；没有时构建走桩 API，可用 Soft 仿真相机。

## 4. 构建与启动

```bash
export SIEANS_QT_PREFIX="${SIEANS_QT_PREFIX:-$HOME/Qt/6.7.3/gcc_64}"
./qtapp/scripts/build.sh
./scripts/launch-sieans-qt.sh          # 日志写入 artifacts/sieans-qt.log
# 或前台：./scripts/run-sieans-qt.sh
```

`launch-sieans-qt.sh` 会把用户级 Qt、`$HOME/.local/opt/onnxruntime/lib` 与可选的 `$HOME/.local/opt/xcb-cursor` 加进 `LD_LIBRARY_PATH`。Wayland 会话默认 `QT_QPA_PLATFORM=wayland`，并把 `QT_QPA_PLATFORMTHEME` 设为 `xdgdesktopportal`（避免 GNOME 上 gtk3 主题刷屏 `gdk_monitor_get_scale_factor`）。可用 `SIEANS_QT_WINDOW_SIZE=WxH` 仅用于验证窗口尺寸。方案、产物、示例图按检出根目录解析（`SIEANS_REPO` 可覆盖），不再写死某一台机器的路径。

无界面打开即跑冒烟（跑完退出，不要把 App 留在后台）：

```bash
export QT_QPA_PLATFORM=offscreen
export SIEANS_QT_HEADLESS=1
export SIEANS_QT_FORCE_SEED=1
export SIEANS_QT_AUTO_SOFT=1
export SIEANS_QT_AUTO_RUN=1
export SIEANS_QT_AUTO_TCP=1
export SIEANS_QT_SMOKE_REPORT="$PWD/artifacts/qt-smoke.txt"
export SIEANS_QT_SCREENSHOT="$PWD/artifacts/qt-smoke.png"
export SIEANS_QT_SCREENSHOT_QUIT=1
./scripts/launch-sieans-qt.sh
```

成功时报告中应能看到 `ocrAvail=1`（若已装用户级 Tesseract）、`yoloBackend=software`（无工业权重时的预期回退）、`projectDirty=0`。路径自检：`SIEANS_QT_PROJECT_SELFTEST=1 SIEANS_QT_PROJECT_SELFTEST_QUIT=1 QT_QPA_PLATFORM=offscreen ./scripts/launch-sieans-qt.sh`。

## 5. 覆盖变量

| 变量 | 用途 |
|------|------|
| `SIEANS_QT_PREFIX` | Qt 前缀 |
| `SIEANS_REPO` | 仓库根（一般不用设） |
| `SIEANS_TESSERACT` / `TESSDATA_PREFIX` / `SIEANS_TESSERACT_PREFIX` | OCR 路径 |
| `SIEANS_ONNXRUNTIME_DIR` / `SIEANS_ONNXRUNTIME_URL` / `SIEANS_ONNXRUNTIME_CACHE` | ORT 前缀、下载 URL、缓存 |
| `SIEANS_YOLO_MODELS_DIR` | 本地 YOLO 权重目录 |

更多工作台说明见 [qtapp/README.md](../qtapp/README.md)。
