# Open-and-run 样例覆盖（wave148 收口 · wave149 画布图例）

面向「双击 `.sieans` → 运行」的软平台关闭清单。详细菜单见 `projects/README-open-and-run.md`。
菜单单一来源：`desktop/open_and_run_catalog.py`（「从模板新建」↔「打开示例」↔ 本表同目录）。

## 能力矩阵（软路径 · 无现场硬件）

| 能力簇 | 代表样例 | 结果铬 / 门限 |
|--------|----------|---------------|
| 默认产线壳 | `default-platform` | 上位机状态机 + OK/NG 底栏 |
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

**wave149**：模块结果画布左下角工业暗色图例（OK/NG · ROI · 叠层种类），随 `showOverlay` / overlay bind 开关。
