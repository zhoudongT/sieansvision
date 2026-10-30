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

```bash
./qtapp/scripts/build.sh
./scripts/run-sieans-qt.sh          # 前台
./scripts/launch-sieans-qt.sh       # 日志 → artifacts/sieans-qt.log
```

环境变量：

- `SIEANS_QT_AUTO_SAMPLE=1` — 启动后加载示例 QR 并解码
- `SIEANS_QT_AUTO_ENUM=1` — 枚举 GenTL
- `SIEANS_QT_AUTO_PREVIEW=1` — 启动连续预览（相机空闲时）
- `SIEANS_QT_AUTO_TCP=1` — 启动后按方案 tcpReal 配置监听/连接
- `SIEANS_QT_SCREENSHOT=/path.png` — 启动后抓窗（配合 `SIEANS_QT_SCREENSHOT_QUIT=1` 可退出）
- `SIEANS_QT_SMOKE_REPORT=/path.txt` — 写出 codes/ms/passGate 一行

启动默认尝试加载 `projects/open-and-run-gentl-qr.sieans`。

## 已落地 vs NEXT

**已落地（wave-2）：** `.sieans` 加载/保存（含 variables/commManager）· 流程画布 **拖线连/断**（端口拖拽、Delete 删边、Esc 取消）· 算子库扩展（preprocess / receive_data / result_gate / save_image 可执行桩）· 连续 GenTL 预览线程 · ▶/连续运行 + C++ QR 叠层 · **变量监视** 接运行结果 · **通信面板** LocalBus 抄本 + 真实 TCP（默认 127.0.0.1:19956，模板 `${flow.x}`）· Host OK/NG 底条 · VisionMaster 炭黑橙强调色。

**NEXT：** 完整 Python 表达式 var_calc · 算子库拖入画布 · UVC · 多设备 Comm UI 对等 · 更丰富 Host HMI · 报警壳。
