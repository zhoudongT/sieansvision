# Open-and-run 示例工程（双击即可跑）

面向今晚可用平台：从资源管理器 / 本仓库 `projects/` **双击** `.sieans`，桌面 App 打开后应立刻能走通「采集/图源 → 识别 → 结果/通信」路径，无需先搭流程。

## 怎么开

1. 启动桌面：`python3 -m desktop.main --root <repo> --data <repo>/data/native-desktop --project <本目录某个.sieans>`
   - 或在已开的 App 里 **文件 → 打开工程** 选下列文件。
2. 工具栏点 **运行**（或切「运行模式」点单次 / HMI 注入 RUN；通信示例可用 LocalBus/`RUN` 字符串触发）。
3. 看图像窗 + 模块结果 +（多数样例）**OK/NG** 灯与生产统计。

环境变量：`SIEANS_FORCE=1` 可强制拉起/覆盖单实例锁（本机调试用）。

## 工程一览（双击 → 立刻可跑）

| 文件 | 覆盖能力（一句话怎么验） |
|------|--------------------------|
| `default-platform.sieans` | **默认产线壳**：图源 + 上位机状态机 + Comm；底栏 OK/NG；打开即 HMI |
| `open-and-run-demo.sieans` | 预处理→圆查找→测量→`passGate`；图像窗叠层 + OK/NG |
| `open-and-run-locate.sieans` | 图源→模板匹配→位置修正→分数门限；`passGate`/`matchScore`/`poseX·Y` |
| `open-and-run-match-locate-chrome.sieans` | 匹配/定位 denser 候选铬（#/排名/分数/Δmin/裕度/位姿/判定）；胶片 配N✓/✗ |
| `open-and-run-geom-find-match.sieans` | Hough 直线查找→多模板匹配密度；胶片铬 L/C + 匹配分表 |
| `open-and-run-geom-script.sieans` | 线夹角/点圆距/圆圆距 + 脚本壳 + 变量计算（软几何） |
| `open-and-run-fixture-preprocess.sieans` | 定位→夹具坐标系/仿射→预处理 ROI→`passGate` |
| `open-and-run-fixture-pose-chain.sieans` | 夹具位姿结果铬（矩阵/轴叠层）+ 预处理链密度 |
| `open-and-run-caliper.sieans` | 卡尺直线多边缘；lineCount/lineScore/lineRms/`passGate` |
| `open-and-run-caliper-measure.sieans` | 卡尺→线线交点→点线距；intersectX/Y·pldDist/`passGate` |
| `open-and-run-measure-caliper-chrome.sieans` | 测量/卡尺 denser 铬 + OCR/缺陷工业表 |
| `open-and-run-measure.sieans` | 预处理→圆查找→尺寸测量→门限 OK/NG |
| `open-and-run-contour-color.sieans` | 轮廓/斑点 + HSV 色彩区域结果铬 |
| `open-and-run-barcode.sieans` | **条码/ID denser 铬**：多码表 + 码N✓/✗ 胶片 + 期望串门限；样张 `codes.png` |
| `open-and-run-ocr-defect-chrome.sieans` | **OCR/缺陷 denser 铬**：识N✓缺N✓ 工业表 + 胶片 + ROI叠层；样张 text.png + circle-ring |
| `open-and-run-ocr-gate-comm.sieans` | OCR→门限→format→LocalBus；Host 监视 ocr*；Comm `${}` |
| `open-and-run-locate-measure-defect.sieans` | 定位→位姿→圆测量→参考图缺陷→综合门限；Host 监视 |
| `open-and-run-defects.sieans` | 参考图缺陷；差异区 + OK/NG |
| `open-and-run-ninepoint.sieans` | **九点/门限 denser 铬**：九N✓门✓ 残差工业表 + 胶片 + 叠层；`calibRms`/`passGate`；hostWatch |
| `open-and-run-script.sieans` | Python 脚本模块；脚本输出写变量 |
| `open-and-run-format-protocol.sieans` | LocalBus send→recv→parse→format→`passGate` |
| `open-and-run-format-protocol-demo.sieans` | 无 send：demoPayload 注入→parse→format→`passGate` |
| `open-and-run-comm-multiproto.sieans` | LocalBus 主路径 + TCP/UDP 写出（模拟回退）；无机器人 SDK |
| `open-and-run-group-comm.sieans` | Group+Comm；Listen 徽章、`RUN`/`STOP`、HB→变量 |
| `open-and-run-tcp-sim.sieans` | TCP 环回联调（先启 :19880 模拟器） |
| `mv-camera-ocr.sieans` | 相机/OCR；需 GenTL 相机或离线帧 |

模板（非双击主推，可「从模板新建」）：`templates/measure-chain.sieans`、`defect-inspection.sieans`、`blank-inspection.sieans`、`mv-gentl-ocr.sieans`。

### wave145 打开即跑审计摘要

- **wave148 docs/菜单对齐**：`desktop/open_and_run_catalog.py` 为「从模板新建 / 打开示例」单一来源；补齐 match-locate-chrome、geom-script、fixture-preprocess、ocr-defect-chrome、format-protocol*、demo、script、group-comm、comm-multiproto。触发/变量结果条 denser（触N· / 变N✓）。预算收口后暂停。

- **全量样例**：上表 23 个 open-and-run + default-platform；菜单「从模板新建 / 打开示例」已补 geom-script、fixture-preprocess、match-locate-chrome、条码密度铬。
- **缺 runUi 已补**：contour-color / fixture-pose-chain / measure-caliper-chrome。
- **条码/ID**：新增 denser 结果铬模块（`desktop/barcode_id_chrome.py` + `BarcodePanel`）；样例带 hostWatch + var_calc 门限。
- **九点**：补 hostWatch / 变量种子（残差门限仍走既有 var_calc）。
- **wave147 OCR/缺陷 denser**：`ocr_defect_chrome.py` 工业 8 列表 + 胶片识N✓缺N✓ + ROI叠层；样例 `open-and-run-ocr-defect-chrome.sieans`。预算收口后暂停。
- **wave146 九点/门限 denser**：`nine_point_var_gate_chrome.py` + NinePoint/VarCalc 结果表 + 胶片九N✓门✓；样例种子 rmsGate/gateVar。预算收口后暂停。
- **default-platform**：显示名改为「默认产线 · 上位机运行壳」，保持打开即用。
- **不做**：Comm/HMI cobind、spark/blink 微级联、真机 TCP/Halcon/机器人 SDK。

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

## LocalBus 稠密笔录 + format↔protocol 软往返（无现场 TCP）

发送/接收数据结果页签 → **LocalBus 软笔录**：稠密 TX/RX/WRITE 行（软 preview，进程内总线）。引擎 `lib/comm-bus.cjs` 维护 transcript 环（send=TX、receive=RX），`getTranscript` / `formatTranscript`。

FormatData / ProtocolParse 结果页签 → **format↔protocol 软往返**：模板展开 → LocalBus 软载荷 → 分隔/定长解析字段表（`soft_format_protocol_roundtrip`）。打开即跑：`open-and-run-format-protocol.sieans`。

```bash
python3 scripts/smoke-localbus-transcript-roundtrip-e2e.py
```

期望：引擎 TX+RX≥2；DataIoPanel 软笔录含 TX/RX；Format/Protocol 往返 parsed_code/score/gate。

## production_task HMI 配方/statusVar 回写 + 试跑结果条

生产任务属性结果区：**statusVar 回写预览**（`taskStatus` / `*_recipe` / `hmiRecipe` / `hmiTaskStatus`）+ **HMI 配方条** + **试跑结果条**（OCR链并试跑等 applyFlowAndRun 落盘）。引擎 `productionTask` 同步写 bag 与 `hmiStrip`/`writeback`。无机器人 SDK、无微属性级联。

```bash
python3 scripts/smoke-production-task-hmi-writeback-e2e.py
```

期望：writebackKeys≥6；HMI strip 含配方/状态/链步；试跑条含 status=ready。

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

## OCR→门限→Comm 模板速验

```bash
PYTHONPATH=.pydeps node scripts/smoke-ocr-gate-comm-runtime-e2e.cjs
```

期望：passGate=1；ocrCount≥1；ocrText 含 BATCH；Comm sendEvents/messageTemplates 含 `${flow.}`；LocalBus send_data 展开。

## 定位→测量→缺陷链速验

```bash
node scripts/smoke-locate-measure-defect-runtime-e2e.cjs
python3 scripts/smoke-comm-message-templates-e2e.py
```

期望：passGate=1；matchScore≥0.7；measureCount>0；defectOk=1；Comm 消息模板 `${}` 展开。

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

- 不接机器人 SDK、不改 HIK 品牌标识；不宣称真机 TCP / Halcon / CLR。



## open-and-run-ocr-gate-comm.sieans
打开即跑 · OCR→门限→Comm 模板。样张 `text.png`（BATCH / SN）；流程：ocr(expectedText=BATCH) → var_calc(ocrCount/ocrConf/ocrText/ocrOk/passGate/commPayload) → format_data → send_data LocalBus（`${flow.*}`）。Host watch + Comm messageTemplates。无现场 TCP / 无 Halcon / 无机器人 SDK。

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
