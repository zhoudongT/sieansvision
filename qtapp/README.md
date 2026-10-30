# sieans_qt — Qt6 上层框架（C++ core）

工业视觉工作台 **骨架**：下层 `native/sieans_algo`（zxing QR + Hikrobot GenTL），
上层 **Qt6 Widgets**。本波不做全量算子迁移；PySide 路径保留
（`scripts/launch-sieans-vision.sh` 不动）。

## 布局

| 区域 | 内容 |
|------|------|
| 菜单 / 工具栏 | 打开图像、示例 QR、C++ 解码、枚举 GenTL、采一帧 |
| 左侧 | 流程 / 画布占位树 |
| 中央 | 图像视图（缩放拖拽 + 码框叠加） |
| 右侧 | 结果面板（解码文本 / GenTL 日志） |
| 状态栏 | native 版本 + 消息 |

## 依赖（allen-MCLG-XX）

- `cmake` ≥ 3.16、`g++`（C++17）
- **Qt6 Widgets**：推荐用户目录 aqt 安装（本机已用）
  ```bash
  pip install --user aqtinstall   # 或 venv
  aqt install-qt linux desktop 6.7.3 linux_gcc_64 -O ~/Qt
  ```
  或系统包：`sudo apt install qt6-base-dev`
- GenTL（可选）：`/opt/MVS`（MvCameraControl）

## 构建

```bash
./qtapp/scripts/build.sh
# 或
cmake -S qtapp -B qtapp/build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH=$HOME/Qt/6.7.3/gcc_64 \
  -DSIEANS_NATIVE_PYTHON=OFF
cmake --build qtapp/build -j$(nproc)
```

## 运行

```bash
./scripts/run-sieans-qt.sh          # 前台
./scripts/launch-sieans-qt.sh       # 日志写 artifacts/sieans-qt.log
```

启动后点 **「示例 QR」** → 自动 C++ 解码并画框；或 **「枚举 GenTL」/「采一帧」**
（相机空闲时会真采；占用则结果面板报错）。

## 与 PySide 的关系

| 入口 | 技术 |
|------|------|
| `scripts/launch-sieans-vision.sh` | PySide6 + `sieans_native` pybind（完整工作台） |
| `scripts/launch-sieans-qt.sh` | Qt6 C++ + `sieans_algo` 直链（框架波） |

两者共用 `native/` 源码；Qt 可执行文件 **不依赖** pybind。

## 后续

- 流程画布（算子图）
- GenTL 连续采集 + 预览线程
- 工程 / `.sieans` 加载
- 更多算子 C++ 化

## Runtime note (xcb)

Qt ≥ 6.5 xcb plugin needs `libxcb-cursor0`. If system package is missing:

```bash
cd /tmp && apt-get download libxcb-cursor0
mkdir -p ~/Qt/extra-libs
dpkg-deb -x libxcb-cursor0_*.deb /tmp/xcb-c
cp -a /tmp/xcb-c/usr/lib/x86_64-linux-gnu/* ~/Qt/extra-libs/
# launch scripts prepend ~/Qt/extra-libs to LD_LIBRARY_PATH
```
