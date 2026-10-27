# Open-and-run 示例工程（双击即可跑）

面向今晚可用平台：从资源管理器 / 本仓库 `projects/` **双击** `.sieans`，桌面 App 打开后应立刻能走通「采集/图源 → 识别 → 结果/通信」路径，无需先搭流程。

## 怎么开

1. 启动桌面：`python3 -m desktop.main --root <repo> --data <repo>/data/native-desktop --project <本目录某个.sieans>`
   - 或在已开的 App 里 **文件 → 打开工程** 选下列文件。
2. 工具栏点 **运行**（或 HMI 注入 RUN；通信示例可用 LocalBus/`RUN` 字符串触发）。
3. 看图像窗 + 模块结果；`default-platform` / `open-and-run-group-comm` 还可看工具栏 **Listen** 徽章与 HMI 生产统计。

环境变量：`SIEANS_FORCE=1` 可强制拉起/覆盖单实例锁（本机调试用）。

## 工程一览（双击 → 立刻可跑的识别路径）

| 文件 | 路径摘要 | 怎么验 |
|------|----------|--------|
| `open-and-run-demo.sieans` | 图源 → 基础识别演示 | 运行后图像窗有结果叠层 |
| `open-and-run-locate.sieans` | 图源 → 定位匹配 | `locate` 出 matches/score |
| `open-and-run-barcode.sieans` | 图源 → 条码/二维码 | 解码字符串进结果/变量 |
| `open-and-run-defects.sieans` | 图源 → 缺陷检测 | OK/NG + 区域 |
| `open-and-run-ninepoint.sieans` | 标定九点 | 基本参数表 + 结果变量 |
| `open-and-run-script.sieans` | 脚本模块 | 脚本输出写入变量 |
| `open-and-run-format-protocol.sieans` | 样例 → LocalBus send/recv → protocol_parse(recvData) → format → passGate | Comm E2E；flow.recvData/formatted/passGate；面板可插上游字段 |
| `open-and-run-group-comm.sieans` | Group + Comm（TCP/LocalBus）+ 触发串 | Listen 徽章、`RUN`/`STOP`、HB→变量 |
| `default-platform.sieans` | 默认产线壳：图源 + HMI 生产统计 + Comm | 打开即 HMI；计数/历史/复制历史 |
| `mv-camera-ocr.sieans` | 相机/OCR 样例 | 需相机或离线帧 |

## 属性面板：上游字段挑选

定位/位姿/畸变/变量计算/Group I/O、几何查找、几何测量、九点、收发数据、条件分支、FormatData、ProtocolParse、TextSave 等面板支持 **插入上游字段**（`results.<模块id>.字段`）。先跑一轮再点挑选，字段列表会跟最近运行结果对齐。

## 通信速验（group-comm / default-platform）

- 工具栏 Listen 徽章：点击打开通信管理；工程切换后徽章状态应保留。
- LocalBus 冒烟：`python3 scripts/smoke-localbus-run-stop.py`（仓库根）。
- TCP 示例端口以工程内 Comm 设备为准（常见调试口 `:19777`）。

## 不要做

- 不 push、不接机器人 SDK、不改 HIK 品牌标识。
