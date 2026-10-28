# Open-and-run 样例覆盖（wave148–wave153：软采集 · 运行态预览 · 连续预览 · 真机路径壳）

面向「双击 `.sieans` → 运行」的软平台关闭清单。详细菜单见 `projects/README-open-and-run.md`。
菜单单一来源：`desktop/open_and_run_catalog.py`（「从模板新建」↔「打开示例」↔ 本表同目录）。

## 能力矩阵（软路径 · 无现场硬件）

| 能力簇 | 代表样例 | 结果铬 / 门限 |
|--------|----------|---------------|
| 默认产线壳 | `default-platform` | 上位机状态机 + OK/NG 底栏 |
| **软模拟采集** | `soft-camera` | **采软✓ 会话铬 · 无闪烁预览 · 打开即采跑** |
| 匹配/定位 | `locate`, `match-locate-chrome`, `fixture-*` | 配N✓ 候选表 / 夹具位姿 |
| 几何/卡尺/测量 | `caliper*`, `measure*`, `geom-*` | 卡尺铬 / 交点垂距 / 夹角圆距 |
| 轮廓/色彩 | `contour-color` | 轮廓+HSV 区域表 |
| **条码/ID** | `barcode` | **码N✓ 多码工业表 + 期望串门限** |
| **OCR/缺陷** | `ocr-defect-chrome`, `ocr-gate-comm`, `defects`, `locate-measure-defect` | **识N✓缺N✓ 工业表 + 胶片铬 + ROI叠层** |
| **九点/门限** | `ninepoint` | **九N✓门✓ 残差工业表 + 胶片铬 + 叠层** |
| 脚本/协议/通信 | `script`, `format-protocol*`, `comm-*`, `group-comm`, `tcp-sim` | LocalBus / 环回模拟 |
| 变量/触发壳 | （任意样例 + 三级变量 / 全局触发） | **变N✓ / 触N· 徽标 + 命中密度表** |

## 打开即用检查

1. 文件 → 从模板新建 / 打开示例 → 选样例（两处列表与 catalog 对齐，含 match-locate / ocr-defect / ninepoint / format-protocol* 等）。
2. ▶ 单次（或运行模式开始）。
3. 看图像叠层 + 模块结果表 + 胶片铬 +（多数）OK/NG。

环境：`SIEANS_FORCE=1` 强制单实例。默认调试口 `:19777`。**勿动** `:18280` 与未跟踪的 `os`。

冒烟：`python3 scripts/smoke-wave148-docs-menu-triggers-e2e.py`；wave149 图例：`python3 scripts/smoke-wave149-canvas-legend-e2e.py`

**wave150**：软模拟采集会话铬 · 无闪烁预览（`LIVE_PREVIEW_POLICY` / in-place pixmap）。

**wave149**：模块结果画布左下角工业暗色图例（OK/NG · ROI · 叠层种类），随 `showOverlay` / overlay bind 开关。

**wave151**：openAndRun → 运行模式默认折叠 Host/配方/通讯「待命」联调墙；主视图为图像预览/画布 + OK/NG + 运行控制（`hmiCobindStatusToggle` 可展开）。

**wave152**：软连续预览节拍 — `PreviewFrameGate` 丢旧帧 + UI 节流；`ImageView.show_live_frame` 同尺寸原地 setPixmap（无 scene.clear 闪烁）；相机管理/会话对话框/`framePolicy=latest` 贯通。

**wave153**：真机采集路径开工 — `desktop/camera_backends.py` 可插拔 Soft / USB UVC / GenTL 壳；
相机管理与图像源可切换后端；UVC 走 OpenCV `VideoCapture` 持久会话（`keepConnectionOpen`，不每帧开关）；
GenTL 无 Producer/CTI 时如实 `not_loaded`/`unsupported`，**不伪造 GenTL 帧**。
冒烟：`python3 scripts/smoke-wave153-real-camera-path-e2e.py`（无硬件时 Soft 回退 + 断言 UVC 枚举/持久会话契约）。
TCP 仍未做（下一波等 Allen）。
