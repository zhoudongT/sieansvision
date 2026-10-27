# Open-and-run 示例工程（双击即可跑）

面向今晚可用平台：从资源管理器 / 本仓库 `projects/` **双击** `.sieans`，桌面 App 打开后应立刻能走通「采集/图源 → 识别 → 结果/通信」路径，无需先搭流程。

## 怎么开

1. 启动桌面：`python3 -m desktop.main --root <repo> --data <repo>/data/native-desktop --project <本目录某个.sieans>`
   - 或在已开的 App 里 **文件 → 打开工程** 选下列文件。
2. 工具栏点 **运行**（或切「运行模式」点单次 / HMI 注入 RUN；通信示例可用 LocalBus/`RUN` 字符串触发）。
3. 看图像窗 + 模块结果 +（多数样例）**OK/NG** 灯与生产统计。

环境变量：`SIEANS_FORCE=1` 可强制拉起/覆盖单实例锁（本机调试用）。

## 工程一览（双击 → 立刻可跑）

| 文件 | 一句话怎么验 |
|------|----------------|
| `open-and-run-demo.sieans` | ▶ 单次：预处理→圆查找→测量→`passGate`；图像窗叠层 + OK/NG |
| `open-and-run-locate.sieans` | ▶ 单次：图源→模板匹配→位置修正→分数门限；`passGate`/`matchScore`/`poseX·Y`；OK/NG |
| `open-and-run-measure.sieans` | ▶ 单次：预处理→圆查找→尺寸测量→门限；有圆且有测量则 OK |
| `open-and-run-barcode.sieans` | ▶ 单次条码/二维码；解码串进结果（样张 `codes.png`） |
| `open-and-run-defects.sieans` | ▶ 单次参考图缺陷；差异区 + OK/NG 语义 |
| `open-and-run-ninepoint.sieans` | 打开看九点参数表；运行写标定结果变量（无厂商标定 SDK） |
| `open-and-run-script.sieans` | ▶ 单次脚本模块；脚本输出写入变量 |
| `open-and-run-format-protocol.sieans` | LocalBus send→recv→parse→format→`passGate`；flow.recvData/formatted |
| `open-and-run-format-protocol-demo.sieans` | 无 send：demoPayload 注入→parse→format→`passGate` |
| `open-and-run-group-comm.sieans` | Group+Comm；Listen 徽章、`RUN`/`STOP`、HB→变量 |
| `default-platform.sieans` | 默认产线壳：图源 + HMI 生产统计 + Comm；打开即 HMI |
| `mv-camera-ocr.sieans` | 相机/OCR；需 GenTL 相机或离线帧 |

模板（非双击主推，可「从模板新建」）：`templates/measure-chain.sieans`、`defect-inspection.sieans`、`blank-inspection.sieans`、`mv-gentl-ocr.sieans`。

## 属性面板：上游字段挑选

定位/位姿/畸变/变量计算/Group I/O、几何查找、几何测量、九点、收发数据、条件分支、FormatData、ProtocolParse、TextSave 等面板支持 **插入上游字段**（`results.<模块id>.字段`）。先跑一轮再点挑选，字段列表会跟最近运行结果对齐。

## 通信速验（group-comm / default-platform / format-protocol）

- 工具栏 Listen 徽章：点击打开通信管理；工程切换后徽章状态应保留。
- LocalBus 冒烟：`python3 scripts/smoke-localbus-run-stop.py`（仓库根）。
- Format/协议引擎：`node scripts/smoke-format-protocol-engine.cjs`。
- TCP 示例端口以工程内 Comm 设备为准（常见调试口 `:19777`）。

## 定位路径速验

```bash
node scripts/smoke-locate-measure-alarmhist-e2e.cjs
```

期望：locate 工程 `passGate=1` 且 pose 绑定成功；measure 工程 `passGate=1`。

## 不要做

- 不 push、不接机器人 SDK、不改 HIK 品牌标识。
