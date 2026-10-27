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
| `open-and-run-caliper.sieans` | ▶ 卡尺直线多边缘；lineCount/lineScore/lineRms/passGate |
| `open-and-run-caliper-measure.sieans` | ▶ 卡尺→线线交点→点线距；intersectX/Y·pldDist/passGate |
| `open-and-run-measure.sieans` | ▶ 单次：预处理→圆查找→尺寸测量→门限；有圆且有测量则 OK |
| `open-and-run-barcode.sieans` | ▶ 单次条码/二维码；解码串进结果（样张 `codes.png`） |
| `open-and-run-defects.sieans` | ▶ 单次参考图缺陷；差异区 + OK/NG 语义 |
| `open-and-run-ninepoint.sieans` | ▶ 单次：九点标定→残差门限；`calibRms`/`calibPoints`/`passGate`；OK/NG×4（无厂商标定 SDK） |
| `open-and-run-script.sieans` | ▶ 单次脚本模块；脚本输出写入变量 |
| `open-and-run-format-protocol.sieans` | LocalBus send→recv→parse→format→`passGate`；flow.recvData/formatted |
| `open-and-run-comm-multiproto.sieans` | LocalBus 主路径 + TCP Client/UDP 写出（模拟回退）；OK/NG；无机器人 SDK |
| `open-and-run-format-protocol-demo.sieans` | 无 send：demoPayload 注入→parse→format→`passGate` |
| `open-and-run-group-comm.sieans` | Group+Comm；Listen 徽章、`RUN`/`STOP`、HB→变量 |
| `default-platform.sieans` | 默认产线壳：图源 + **上位机状态机**运行壳 + Comm；底栏 OK/NG；打开即 HMI |
| `mv-camera-ocr.sieans` | 相机/OCR；需 GenTL 相机或离线帧 |

模板（非双击主推，可「从模板新建」）：`templates/measure-chain.sieans`、`defect-inspection.sieans`、`blank-inspection.sieans`、`mv-gentl-ocr.sieans`。

## 属性面板：上游字段挑选

定位/位姿/畸变/变量计算/Group I/O、几何查找、几何测量、九点、收发数据、条件分支、FormatData、ProtocolParse、TextSave 等面板支持 **插入上游字段**（`results.<模块id>.字段`）。先跑一轮再点挑选，字段列表会跟最近运行结果对齐。

## 通信协议深化（环回模拟器 · 非现场设备）

通信管理 → **TCP 测试** → 「启动环回模拟器」(:19880/:19881)，再用「协议预设」试发：

| 报文 | 回包（模拟） |
|------|----------------|
| `PING` | `PONG` |
| `STATUS` | `OK READY sim=1 …` |
| `GET <key>` / `SET <key> <v>` / `VARS` | 内存 KV |
| `MEAS` | `MEAS {ok,x,y,score,seq,ts,sim}` 假量测 JSON |
| `JSON {"cmd":"GET","key":"ok"}` | JSON 读写 |

试收写变量时会解析 `VALUE` / `MEAS` / 纯 JSON 到 sibling 字段（如 `measX`）。**不宣称真机 / PLC / 机器人**。

冒烟：`python3 scripts/smoke-comm-protocol-deepen-e2e.py`

## 通信速验（group-comm / default-platform / format-protocol）

- 工具栏 Listen 徽章：点击打开通信管理；工程切换后徽章状态应保留。
- LocalBus 冒烟：`python3 scripts/smoke-localbus-run-stop.py`（仓库根）。
- Format/协议引擎：`node scripts/smoke-format-protocol-engine.cjs`。
- TCP 示例端口以工程内 Comm 设备为准（常见调试口 `:19777`）。

## 卡尺→几何测量链速验

```bash
node scripts/smoke-caliper-measure-runtime-e2e.cjs
```

期望：passGate=1；intersectX/Y·pldDist；geometry.lines≥2。

## 定位路径速验

```bash
node scripts/smoke-locate-measure-alarmhist-e2e.cjs
```

## 九点 + Comm 多协议 + 报警导出

```bash
node scripts/smoke-ninepoint-comm-alarmexport-e2e.cjs
```

期望：ninepoint `passGate=1`；comm multiproto LocalBus `passGate=1`；Alarm 历史复制/导出按钮存在。

期望：locate 工程 `passGate=1` 且 pose 绑定成功；measure 工程 `passGate=1`。

## 不要做

- 不 push、不接机器人 SDK、不改 HIK 品牌标识。


## open-and-run-caliper-measure.sieans
打开即跑 · 卡尺→几何测量链。样张同卡尺；流程：预处理 → geometry(caliper, maxCount=3) → line_intersect(lines[0]×lines[1]) → point_line_distance(交点→lines[2]) → 门限(intersectX/Y·pldDist/passGate)。叠层含交点+垂距。无 Halcon / 无现场硬件。

## open-and-run-caliper.sieans
打开即跑 · 卡尺直线多边缘。样张 `caliper-line.png` 等；流程：预处理 → geometry(lines, findMethod=caliper, edgeType=all, maxCount=3) → 门限(lineCount/lineScore/lineRms/passGate)。叠层含卡尺框·多直线·rms。全局触发 RUN/CONT/STOP。无 Halcon / 无现场硬件。

## open-and-run-tcp-sim.sieans
打开即跑 · TCP 环回联调。先在通信管理「TCP 测试」启动环回模拟器(:19880)，再单次或发 RUN。无现场硬件。

## 细妆⑬ 相关入口

- 工具 → **产线配方 / 换型**：对本方案参数快照一键换型，或从本目录/模板整案加载。
- 几何直线查找 → **多卡尺 ROI 编辑器**：画布拖 ROI + 卡尺预览。
- 工具 → **真机 Comm 验收壳**：对环回 :19880 干跑协议清单（可改 Host/Port）。
- HMI **结果表**：多列历史 + 导出 CSV。
