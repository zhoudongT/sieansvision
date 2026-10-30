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
| 右侧 | 结果表 + 运行日志 |
| 工具栏 | 打开/保存方案 · 相机 · 连续预览 · ▶运行 / ↻连续 / ■停止 |

## 构建 / 运行

```bash
./qtapp/scripts/build.sh
./scripts/run-sieans-qt.sh          # 前台
./scripts/launch-sieans-qt.sh       # 日志 → artifacts/sieans-qt.log
```

环境变量：

- `SIEANS_QT_AUTO_SAMPLE=1` — 启动后加载示例 QR 并解码
- `SIEANS_QT_AUTO_ENUM=1` — 枚举 GenTL
- `SIEANS_QT_AUTO_PREVIEW=1` — 启动连续预览（相机空闲时）

启动默认尝试加载 `projects/open-and-run-gentl-qr.sieans`。

## 已落地 vs NEXT

**已落地：** `.sieans` 加载/保存 · 流程画布 · 算子库/属性 · 连续 GenTL 预览线程 · ▶/连续运行 + C++ QR 叠层/结果表 · VisionMaster 炭黑橙强调色。

**NEXT：** TCP/Comm 真连 · Host 运行态 HMI · 变量监视板完整 · 拖线新建连线 · UVC · 更多算子 C++ 化 · 报警/OK-NG 壳。
