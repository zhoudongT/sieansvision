# sieans_qt — Qt6 工作台（C++ core）对等波

下层 `native/sieans_algo`（zxing QR + Hikrobot GenTL），上层 **Qt6 Widgets**。
本波对齐 PySide **GenTL→QR 打开即跑** 主路径；`scripts/launch-sieans-vision.sh` 保留不动。

## 布局（对齐工业壳）

| 区域 | 内容 |
|------|------|
| 菜单 | 文件 / 设置 / 工具 / 系统 / 工程管理 / 设备与模型 / 帮助 |
| 左轨 | 算子库（双击添加） |
| 左中 | 真实流程画布（节点+连线）+ 属性面板 |
| 中央 | 图像视图（缩放/拖拽 + 码框叠层，连续预览不强制重 fit） |
| 右侧 | 结果 / 变量监视 / 通信（LocalBus+TCP）三页 |
| 底条 | Host OK/NG 条（hostWatch 键） |
| 工具栏 | 打开/保存 · 相机 · 连续预览 · ▶运行 / ↻连续 / ■停止 · 通信启停 |

## 构建 / 运行

新机器从检出构建、用户级依赖（无 sudo）与自检见 [docs/qt-workbench-setup.md](../docs/qt-workbench-setup.md)。先跑 `./scripts/doctor-sieans-qt.sh` 查看本机缺什么。

```bash
./qtapp/scripts/build.sh
./scripts/run-sieans-qt.sh          # 前台
./scripts/launch-sieans-qt.sh       # 日志 → artifacts/sieans-qt.log
```

环境变量：

- `SIEANS_QT_AUTO_SAMPLE=1` — 启动后加载示例 QR 并解码
- `SIEANS_QT_AUTO_ENUM=1` — 枚举 GenTL
- `SIEANS_QT_AUTO_PREVIEW=1` — 启动连续预览（相机空闲时）
- `SIEANS_QT_AUTO_SOFT=1` — 切到 Soft 仿真相机并连续预览（不需要硬件）
- `SIEANS_QT_AUTO_MATCH=1` — 追加快速匹配并单次运行（可与 `AUTO_SOFT` 同用）
- `SIEANS_QT_AUTO_TCP=1` — 启动后按方案 tcpReal 配置监听/连接
- `SIEANS_QT_SCREENSHOT=/path.png` — 启动后抓窗（配合 `SIEANS_QT_SCREENSHOT_QUIT=1` 可退出）
- `SIEANS_QT_SMOKE_REPORT=/path.txt` — 写出 codes/ms/passGate 一行

OCR 依赖本机 `tesseract` 与 `eng` 语言包。无 sudo 时执行 `scripts/install-tesseract-user.sh`，把 Ubuntu 官方 deb 解压到 `$HOME/.local/opt/tesseract`，并安装 `$HOME/.local/bin/tesseract` 包装脚本（eng + chi_sim）。算子会查找 PATH、该用户前缀、`SIEANS_TESSERACT` 与 `TESSDATA_PREFIX`；系统已安装 `/usr/bin/tesseract` 时仍优先使用 PATH 上的版本。

YOLO 真实推理（可选）：将检测用 `.onnx`（如 `yolo11n.onnx`）放到仓库 `models/` 或 `$HOME/.local/share/sieans/models/`（或 `SIEANS_YOLO_MODELS_DIR`）。无权重或只有 `.pt` 时算子回退 software，不会自动下载。ONNX Runtime 可用 `scripts/install-onnxruntime-user.sh` 安装到 `$HOME/.local/opt/onnxruntime`。本地烟测桩 `models/sieans-yolo-smoke.onnx` 仅用于验证推理链路，不是工业模型。

启动默认尝试加载 `projects/open-and-run-gentl-qr.sieans`。

## 已落地 vs NEXT

**已落地（wave-5，对齐 VM P0）：** 本地图胶片条（图像源 n/N、添加图像、添加文件夹、删除、自动切换、运行全部）· 状态栏「组件配置完成 / 未配置」与「流程 · 工具 · 算法 ms」· 参数修改写历史日志（旧值/新值）· 工具栏「运行模式」锁定画布拖拽、连线和删除 · 图像源三种取图（本地图像 / 相机 / SDK）字段随模式切换 · 视口像素条 `宽×高 | X Y | R G B` · **快速匹配**：首次执行从当前图高对比区域建模板，绿框叠加分数。

**已落地（wave247）：** 定位/快速匹配属性浮窗四 Tab（基本参数 / 特征或灰度模板 / 运行参数 / 结果显示），含载入与从当前图创建模板、角度搜索和结果回显；与已有 SAD 匹配及 `templateSource`/`angle*` 参数兼容。

**NEXT：** 多流程 Tab 与 `.prc` 导入导出（PySide `desktop/scheme.py` 已有，Qt 仍是单主流程 + 子流程）· 运行界面设计器（不在目录中新增 HMI 算子）。

## VM chrome (2026-11-03)

- FilmstripBar: real local-image thumbs, add/folder/run-all/auto-switch
- PropertyFloat: typed editors + revert on ✕/取消; drag title
- OperatorLibrary: painted glyphs; FlowView corner FlowMinimap
- Flow I/O dialog (输入/输出/显示) ↔ document `io`
- HostStatePanel bottom tab + toolbar 运行模式 lock

