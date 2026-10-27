# 茗工-JGTech《海康VisionMaster系列教程》对照笔记

| 项 | 内容 |
|----|------|
| 来源 | Bilibili [BV19vUfBVEpp](https://www.bilibili.com/video/BV19vUfBVEpp/) · 65 分页 |
| 本批已看 | **p=1–30**（Wrap：含轻看 p1–3 安装/卸载；Wave1–4 功能集齐；约 30 集素材） |
| 素材路径 | `docs/vm-bilibili-jgtech/videos/` · `docs/vm-bilibili-jgtech/frames/` |
| 关键帧策略 | ~1 帧 / 9s（OpenCV；PC 无 ffmpeg/yt-dlp，用 `bin/bili_fetch.py`） |
| 目标 | 先看视频再改 sieansvision；本文记录 **UI 步骤 / 中文标签 / 已有 vs 缺口** |
| 总览 | 功能+设计综合见 `docs/VisionMaster完整功能与设计总览.md` |
| 日期 | 2026-10-27（Asia/Shanghai） |

> 不复刻海康算法内核；对齐 **交互分区、标签、未配置态、运行壳**。品牌色保留 sieans 橙。

---

## 全系列 1–65 状态总表（Wrap / 2026-10-27）

图例：**Watched**=已下帧/笔记 · **Implemented**=设计态+可跑（含实用运行） · **Shell**=设计态/目录薄壳或透传 · **Skip(industry)**=行业/机器人深度刻意不做 SDK · **Unwatched**=未下帧。

一集可兼有 Watched + Implemented/Shell。Skip 行通常 Unwatched。

| p | 标题（episodes.txt） | Watched | 落地 | sieans 映射 / 备注 |
|---|----------------------|---------|------|-------------------|
| 1 | VisionMaster4.2试用一月安装 | ✓ | Skip(installer) | 网盘/试用包分发；**不克隆海康安装器**。sieans：自带 App/工程即可 |
| 2 | MVS和VisionMaster的卸载 | ✓ | Skip(installer) | 官方 uninstall.exe；sieans 无对标卸载向导 |
| 3 | MVS和VisionMaster的安装 | ✓ | Skip(installer) | MVS+VM 安装包；**首启相关**：设备树/虚拟相机概念 → 已有相机管理+图像源本地/SDK |
| 4 | 图像源 | ✓ | Implemented | ~35（含 p41–43 上位机状态机） |
| 5 | 直线查找 | ✓ | Implemented | `GeometryFindPanel` feature=lines |
| 6 | 圆查找 | ✓ | Implemented | `GeometryFindPanel` feature=circles |
| 7 | 快速模板匹配 | ✓ | Implemented | `LocateMatchPanel` 四 Tab |
| 8 | 灰度模板匹配 | ✓ | Implemented | locate `matchMode=gray` |
| 9 | 位置修正 | ✓ | Implemented | `pose_correct` |
| 10 | 通信管理 | ✓ | Implemented | `CommManagerDialog` 设备/收发/心跳/响应 + **TCP 测试** Tab |
| 11 | 收发数据 / 全局变量 | ✓ | Implemented | `receive_data`/`send_data` + 变量表 UX |
| 12 | C#脚本 | ✓ | Implemented | `csharp_script`：C#=unsupported；**Python+OpenCV 可跑**（需允许脚本） |
| 13 | 畸变矫正 | ✓ | Implemented | `distort_correct` → vision OpenCV undistort；未标定显式 uncalibrated |
| 14 | 线与线的交点 | ✓ | Implemented | `line_intersect` |
| 15 | 矩形查找 | ✓ | Implemented | `rect_find` → geometry.rects |
| 16 | 点与点距离 | ✓ | Implemented | `point_distance` |
| 17 | 点与线距离 | ✓ | Implemented | `point_line_distance` |
| 18 | 条件分支 | ✓ | Implemented | condition 规则表 |
| 19 | 分支模块 | ✓ | Implemented | `branch` |
| 20 | 平移九点标定 | ✓ | Implemented | `nine_point` 仿射最小二乘（AtA/Gaussian，满秩等价 SVD） |
| 21 | 格式化（发出数据） | ✓ | Implemented | `format_data` `{0}`/`{name}` 模板 → 变量 |
| 22 | 输出(保存)图像 | ✓ | Implemented | `output_image` 落盘 base64（可选格式转换） |
| 23 | 变量计算 | ✓ | Implemented | `var_calc` |
| 24 | 协议解析 | ✓ | Implemented | `protocol_parse` delimited/json/regex/**fixed** |
| 25 | 文本保存 | ✓ | Implemented | `text_save` 追加/覆盖写文件 |
| 26 | 组合模块 | ✓ | Implemented | Group + N4 |
| 27 | 耗时统计 | ✓ | Implemented | `elapsed_stats` |
| 28 | 运行界面设计1 | ✓ | Implemented | 运行界面设计器 + **VM 默认壳**（图像/OKNG/日志） |
| 29 | 运行界面设计2 | ✓ | Implemented | 控件库四分类 + 触发命令 + 固定栏；深度可再贴帧 |
| 30 | 全局触发 | ✓ | Implemented | 部分匹配列 |
| 31 | 远程通信连接其他电脑如何设置ip | ✓ | Shell* | CommManager+TCP 测试可写变量；教程式 |
| 32 | 定位引导·自动化九点标定_（副本） | ✓ | Skip(industry) | 机器人引导；复用 `nine_point` 即可 |
| 33 | 定位引导·文件夹模拟_（副本） | ✓ | Skip(industry) | 同上 |
| 34 | 定位引导·自动化九点标定 | ✓ | Skip(industry) | 机械手链路；不做厂商 SDK |
| 35 | 定位引导·文件夹模拟 | ✓ | Skip(industry) | 图像文件夹模拟；可用图像源胶片条近似 |
| 36 | 验证九点标定 | ✓ | Skip(industry) | 验证九点：图像位→机械坐标→机械手测；复用 nine_point，无臂 SDK |
| 37 | 相对移动定位纠偏法 | ✓ | Skip(industry) | 机械手纠偏 |
| 38 | 设置图像基准位置 | ✓ | Skip(industry) | 引导项目子步 |
| 39 | 设置机械手基准位置 | ✓ | Skip(industry) | 机械手基准；Skip SDK |
| 40 | 生产任务设计 | ✓ | Implemented | `production_task` 面板+建议流程链（图像→匹配→修正→物理坐标→偏差→发送）；无机械手 SDK |
| 41 | 上位机状态机·UI设计1 | ✓ | Implemented | HostStateMachine：手动/自动·Idle/Run/Pause/Alarm；默认运行壳；无臂 SDK |
| 42 | 上位机状态机·UI设计2 | ✓ | Implemented | 同上（运动/吸嘴/三模式组） |
| 43 | 上位机状态机·UI设计3 | ✓ | Implemented | 同上（开始/暂停/继续/停止→流程触发） |
| 44 | 为什么用旋转中心标定 | ✓ | Skip(industry) | 理论课：为何旋转中心标定（一句话看过） |
| 45 | 旋转中心·原理公式 | ✓ | Skip(industry) | 理论课：旋转中心原理公式 |
| 46 | 旋转中心·公式基础 | ✓ | Skip(industry) | 理论课：旋转中心公式基础 |
| 47 | 旋转中心·原点为旋转中心 | ✓ | Skip(industry) | 理论课：原点为旋转中心 |
| 48 | 旋转中心·旋转点表示公式 | ✓ | Skip(industry) | 理论课：旋转点表示公式 |
| 49 | 旋转中心·任意点为旋转中心 | ✓ | Skip(industry) | 理论课：任意点为旋转中心 |
| 50 | 完整课程（短宣） | ✓ | Skip | 宣发短片 |
| 51 | 上下相机对位贴合 | ✓ | Skip(industry) | 上下相机对位贴合；无专有多相机 SDK |
| 52 | 平移旋转标定（十二点）-介绍 | ✓ | Skip(industry) | 十二点标定介绍；远期可扩 nine_point |
| 53 | 实现十二点标定 | ✓ | Skip(industry) | 实现十二点；不做厂商旋转标定 SDK |
| 54 | 九点平移标定（行业复述） | ✓ | Implemented | 复用 `nine_point`（平移九点/标定转换）；无新 SDK |
| 55 | 十二点标定完整课程（短） | ✓ | Skip | 宣发短片 |
| 56 | 单点抓取 | ✓ | Skip(industry) | 单点抓取；机械手链路 Skip SDK |
| 57 | 对位贴合·角度验证-1 | ✓ | Skip(industry) | 角度验证理论-1 |
| 58 | 对位贴合·角度验证-2 | ✓ | Skip(industry) | 角度验证理论-2 |
| 59 | 十二点标定与单点抓取（短） | ✓ | Skip | 宣发短片 |
| 60 | 旋转标定数学公式几何本质 | ✓ | Skip(industry) | 旋转标定几何本质（理论） |
| 61 | 旋转标定优化圆心 | ✓ | Skip(industry) | 优化圆心（理论） |
| 62 | C#脚本使用 OpenCV-1 | ✓ | Implemented | `csharp_script`→Python+OpenCV（无 CLR）；默认 Canny |
| 63 | C#脚本使用 OpenCV-2 | ✓ | Implemented | 同上 |
| 64 | 旋转标定模块使用注意 | ✓ | Skip(industry) | VM 旋转标定模块注意项 |
| 65 | 官网精品免费课程 | ✓ | Skip | 官网宣发 |

### 统计（约）
| 类别 | 数量 |
|------|------|
| Watched（有帧） | 65（p1–65 齐） |
| Implemented | ~28（p1–30 壳已加深） |
| Shell / Shell* | ~2（p31 等） |
| Skip(industry) / Skip | ~21 |
| 纯 Unwatched 且待定 | 0（31–65 均已归类） |

### p1–3 首启笔记（轻看；不装海康）
- **p1**：试用包/网盘链接与测试图 zip（平移标定图、测试图像）— sieans 可维护 `projects/` 示例工程 + `data/` 样图，**不要**接入海康安装包分发。
- **p2**：`Program Files/VisionMaster*/uninstall.exe` — sieans 用系统包管理/直接删目录即可，无需卸载向导。
- **p3**：先装 **MVS**（设备树、虚拟相机）再装 **VisionMaster** — sieans 对应：**相机管理（GenTL）+ 图像源本地/SDK**；首启检查「能枚举设备 / 能开默认工程」即可，勿复刻安装向导 UI。

### 行业案例策略（p31–65）重申

> **Allen（t187u）**：p31+ **不能砍掉**，仍需继续看帧。对照表保持 Skip(industry)/Shell*/Unwatched，**不要**标 Dropped。下帧用 `docs/vm-bilibili-jgtech/` + `bin/bili_fetch.py`；行业集只记 UI/流程缺口，不做机器人厂商 SDK 深克隆。
1. **不做**机械手/旋转中心/十二点/单点抓取等厂商 SDK 深实现。
2. **可复用已有**：`nine_point`、`pose_correct`、CommManager、运行 HMI、`csharp_script`/`script`、`production_task`。
3. 若 Allen 点名某集要「可跑 demo」，再对该集下帧 + 最小壳，仍避免机器人运行时。


### p31–43 下帧速记（UI/流程缺口；无机器人 SDK）
- **p31 远程通信/IP**：CommManager 主机/端口 + TCP 测试即可对标；教程式网络设置，无新算子。
- **p32–39 定位引导/九点/纠偏/基准**：流程上复用 `nine_point` + `pose_correct` + 图像源胶片；机械手链路保持 Skip(industry)，对照只记步骤名。
- **p40 生产任务**：已有 `production_task` 薄壳（任务名/配方→变量）。
- **p41–43 上位机状态机 UI**：`HostStateMachineWidget` 已嵌入默认运行壳 + 控件库「上位机状态机」；开始/停止绑流程；无机械手协议。

- **p31 帧观感**：空流程 + 全局图像棋盘；通讯侧靠系统/通信管理配 IP（对标 CommManager host/port + TCP 测试）。
- **p40 帧观感**：生产任务=图像→模板匹配→位置修正→圆查找→基准/目标物理坐标→偏差 dx/dy→MoveX/Y→发送上位机；sieans 可用 locate+pose_correct+geometry+var_calc+send_data 串，机械手 SDK 仍 Skip。
- **p41 帧观感**：上位机 UI 含 IP/端口、连接机械手、回原点、XYZ/角度/速度、吸嘴开闭、信息栏；对标 HMI 控件+Comm TCP，不做厂商机械手协议深实现。

---

## 已看分集速览

| p | 标题 | 关键帧目录 | sieans 现状 | 缺口（本批优先级） |
|---|------|----------|-------------|-------------------|
| 1–3 | 试用/卸载/安装 | `frames/p01…p03` | **Skip 安装器**；首启→相机管理+默认工程 | 勿克隆 HIK 安装/卸载向导 |
| 4 | 图像源 | `frames/p04_…` | `ImageSourceForm` 本地/相机/SDK + 相机管理入口 | 胶片条+自动切换+最后一张停止+空态红字；状态栏「组件参数未配置完整」与 N4 同源 |
| 5 | 直线查找 | `frames/p05_…` | **GeometryFindPanel** feature=lines | **Wave4**：三 Tab + ROI/极性/长度间隙/结果显示 |
| 6 | 圆查找 | `frames/p06_…` | **GeometryFindPanel** feature=circles | **Wave4**：半径范围/分数等同壳 |
| 7 | **快速模板匹配** | `frames/p07_…` | `locate` 扁平参数 | **四 Tab 壳已落地**（基本参数/特征模板/运行参数/结果显示） |
| 8 | 灰度模板匹配 | `frames/p08_…` | locate + matchMode | **Wave2**：matchMode gray/fast + 灰度模板 Tab/参数 |
| 9 | 位置修正 | `frames/p09_…` | **pose_correct** 算子+三 Tab | Wave2 设计态+运行透传 |
| 10 | 通信管理 | `frames/p10_…` | **通信管理**五 Tab 窗 | Wave2：设备/收发/心跳/响应 |
| 11 | 收发数据 / 全局变量 | `frames/p11_…` | **receive/send_data** + 变量表 | Wave3 收发；**Wave4** 全局表 UX（备注/持久/仅全局/复制） |
| 12 | C#脚本 | `frames/p12_…` | **csharp_script** | **Wave4** 设计态编辑器壳；CLR 本机不执行 |
| 13 | 畸变矫正 | `frames/p13_…` | **distort_correct** | Wave3 三 Tab 壳 + 透传 |
| 14 | 线与线的交点 | `frames/p14_…` | **line_intersect** | **Wave4** 绑定/手动 + 运行求交 |
| 15 | 矩形查找 | `frames/p15_…` | **rect_find** → geometry.rects | **Wave4** 三 Tab + minAreaRect 运行 |
| 16 | 点与点距离 | `frames/p16_…` | **point_distance** | **Wave4** 绑定/手动欧氏距 |
| 17 | 点与线距离 | `frames/p17_…` | **point_line_distance** | **Wave4** 垂距 |
| 20 | 平移九点标定 | `frames/p20_…` | **nine_point** | Wave3 九点表 + 仿射估 |
| 23 | 变量计算 | `frames/p23_…` | **var_calc** | Wave3 表达式表 + 求值 |
| 27 | 耗时统计 | `frames/p27_…` | **elapsed_stats** | Wave3 起止下拉 + 累计 |
| 18 | 条件分支 | `frames/p18_…` | condition 规则表 + AND/OR | Wave2 表格式 UX；引擎多规则 |
| 19 | 分支模块 | `frames/p19_…` | **branch** 路径表 | Wave2；出边 when=路径名 |
| 26 | **组合模块** | `frames/p26_…` | Group 四 Tab + 进组 | 组内未配置节点 **红叹号**（本批 N4 覆盖） |
| 28 | 运行界面设计1 | `frames/p28_…` | 运行界面设计器 + 操作员 HMI | Wave2：VM默认运行壳一键 |
| 29 | 运行界面设计2 | `frames/p29_…` | 控件库+触发命令已有 | Wave2 补默认壳 |
| 30 | **全局触发** | `frames/p30_…` | 事件/字符串表 | Wave2：**部分匹配**列 |

---

## p=4 图像源 — 交互笔记


### p47–65 下帧速记（理论/行业；可模仿处已挂钩）
- **p44–50 / 60–61 / 64–65**：理论或宣发 — 一句话看过即可，不实现旋转中心 SDK。
- **p51–53 / 55–59**：十二点/对位/抓取 — Skip(industry)；流程叙事可参考，无厂商臂。
- **p54**：VM「平移九点标定」生产流程多 Tab（上相机九点/基准/生产/旋转中心）；sieans 用已有 `nine_point`+多流程。
- **p36 验证九点**：①图像目标位 ②转机械坐标 ③臂测 — 仅前两步可本地 mimic。
- **p40**：建议链已写入 `production_task` 面板。
- **p41–43**：上位机 UI（IP/端口/连接/运动/吸嘴/信息栏）→ HMI 控件库示意；不做机械手协议。
- **p62–63**：C# OpenCV → 本机 Python `csharp_script`/`script` + OpenCV。


### UI 步骤（课内）
1. 工具箱拖入 **图像源**（画布序号 `0 图像源1`）。
2. 双击打开属性浮窗：模式 **本地图像 / 相机 / SDK**。
3. 本地：加图 → 胶片条；开关 **自动切换 / 到末停**。
4. 相机：打开 **相机管理**，选设备；未选时状态栏/节点示警「组件参数未配置完整」。
5. 底栏：**连续执行 / 执行 / 确定**。

### 标签摘录
图像源｜本地图像｜相机｜SDK｜像素格式｜采集间隔｜保存到方案｜显示图像名｜自动切换｜相机管理

### sieans vs 缺口
| 已有 | 缺口 |
|------|------|
| `ImageSourceForm` 三模式、相机管理信号 | 状态栏精确红字与节点红叹号联动（本批 N4 覆盖 source） |
| 属性浮窗浅色叠深色画布 | 胶片条 UX 细节对照帧再贴 |

---

## p=7 快速模板匹配 — 交互笔记（本批核心）

### UI 步骤
1. 已有图像源；拖入 **快速匹配**，连线 `0 图像源1 → 1 快速匹配1`。
2. 双击 → 属性顶栏 **四 Tab**：
   - **基本参数**：输入源（`0 图像源1.图像`）、ROI（继承/绘制）
   - **特征模板**：创建 / 载入 / 编辑模板；模板配置子窗（画笔、对比度阈值）
   - **运行参数**：最小匹配分数、最大匹配个数、角度/尺度、超时等
   - **结果显示**：匹配框/分数/轮廓开关、结果判断
3. 底栏：连续执行 / 执行 / 确定。
4. 未配模板或未订图像 → **红叹号**。

### 与旧笔记差异
点测表曾写「基本/高级/结果/ROI」；**本系列与既有 UX 课一致为「基本参数 / 特征模板 / 运行参数 / 结果显示」**。实施以本系列为准。

### sieans 映射
- Catalog：`locate`＝「模板匹配定位」
- **本批**：`LocateMatchPanel` 四 Tab 壳 + `hasTemplate`/`templatePath` 驱动 N4

---

## p=8 灰度模板匹配

- 与快速匹配同壳，算法模式不同（灰度相关）。
- sieans：**Wave2** `locate.matchMode` = `fast` | `gray`；Tab 标题切「特征模板/灰度模板」；灰度运行参数含级数/评分/亚像素/超时。

## p=9 位置修正

- 典型链：`快速匹配 → 位置修正 → 后续检测`。
- 用匹配位姿校正后续 ROI/坐标系。
- sieans：**Wave2** 算子 `pose_correct` + 三 Tab（基本/基准位姿/输出）；运行透传图像并输出 fixture 字段。

## p=5 / p=6 直线 · 圆查找

- 几何查找：ROI、阈值、极性、结果叠加。
- sieans：`geometry` + feature 枚举已有；属性仍扁平，可后续套同类四 Tab（非本批）。

## p=10 / p=11 通信 · 收发 · 全局变量

- **通信管理**集中配设备；流程里放 **接收数据 / 发送数据**。
- 全局变量表：名/类型/值；模块可绑定。
- 帧证：发送数据未配通道时 **红叹号**（支撑 N4）。
- sieans：**Wave2** `CommManagerDialog`（设备管理/接收事件/发送事件/心跳/响应）→ `project.commManager`；菜单「通信管理…」/工具栏「通信」。收发专用节点仍弱 → 后续。

## p=18 / p=19 条件分支 · 分支模块

- 条件分支：规则表（变量、比较、常量）→ 真/假出边。
- 分支模块：多路分支壳。
- sieans：**Wave2** `ConditionBranchPanel`；condition 多规则 AND/OR（引擎 `flow-control.condition`）；branch 路径表 + 出边 `when=路径名`。

## p=26 组合模块

- 进组前绑 **ImageData / InputROI**；组内可再放匹配等；未配节点整颗偏红/叹号。
- sieans：`GroupParamPanel` 四 Tab + 进组已有；本批 N4 对 group 绑定不齐也亮叹号。

## p=28 / p=29 运行界面设计 1/2

- 设计态 ≠ 运行态；**运行界面设计器**：分栏、固定栏、控件库（按钮/信号灯/文本/统计…）。
- 按钮 **触发命令**：执行/停止/模块动作/界面链接…
- 帧见 Play/Stop/NG 运行壳。
- sieans：设计器+操作员 HMI 已有；**Wave2** 一键「VM默认运行壳」（图像/OK·NG/运行控制/运行状态）。

## p=30 全局触发

- 表：触发字符串 / 部分匹配 / 执行流程（或模块）。
- 与通讯收数联动：收到串 → 匹配 → 跑流程。
- sieans：**Wave2** 字符串触发表增加 **部分匹配** 列 + `match_string` 助手。

---

## 本批落地（Phase B / Wave1）

1. **N4 未配置红叹号** — `desktop/config_status.py` + `Node` 右上角红三角叹号。
2. **locate 四 Tab** — `desktop/locate_match_panel.py`。
3. 文档：本文 + `VM-UX对照要点.md` JGTech 增补。

## Wave2 落地（2026-10-27）

1. **灰度模板匹配** — `locate.matchMode` fast|gray；灰度模板 Tab + 运行参数。
2. **位置修正** — `pose_correct` 目录项 + `PoseCorrectPanel` + 运行透传。
3. **通信管理** — `CommManagerDialog` 五 Tab + 菜单/工具栏。
4. **条件分支 / 分支模块** — `ConditionBranchPanel`；引擎多规则 / branch 路径。
5. **全局触发** — 字符串表 **部分匹配** 列。
6. **运行界面** — 设计器「VM默认运行壳」一键布局。



## Wave3 落地（2026-10-27）

1. **畸变矫正** `distort_correct` — 三 Tab（基本/内参/结果）；标定文件或手动系数；运行透传。
2. **九点标定** `nine_point` — 像素↔世界九点表；≥3 点估简易仿射。
3. **变量计算** `var_calc` — 表达式表（名称/公式/初始/类型/初始化）；安全算术求值写入变量。
4. **耗时统计** `elapsed_stats` — 开始/结束模块下拉；区间 elapsedMs 累计。
5. **接收/发送数据** `receive_data` / `send_data` — 绑定通信管理设备；收写变量 / 发文本。
6. **薄壳** `format_data`（格式化）、`output_image`（输出图像）、`protocol_parse`（协议解析）、`text_save`（文本保存）— 对应 p21/22/24/25。

### Wave3 新看 / 下帧
- p21 格式化（发出数据）、p22 输出(保存)图像、p24 协议解析、p25 文本保存（下载帧后薄壳已对齐笔记）。

### 仍可加深
- 畸变真实 undistort / OpenCV 标定流程；九点 SVD；通信真实收发；输出图像宿主落盘；HMI 控件库；直线/圆亚像素与卡尺；C# CLR/真实 script 宿主；p=1–3 入门、p=31–65 行业案例。


## Wave4 落地（2026-10-27）

1. **矩形查找** `rect_find` — `GeometryFindPanel` 强制 feature=rects；运行 remap→`geometry` + `vision/engine.py` minAreaRect。
2. **线与线交点** `line_intersect` — `MeasureGeomPanel` 绑定/手动；`flow-control.lineIntersect` 解析几何。
3. **点与点距离** `point_distance` / **点与线距离** `point_line_distance` — 同上壳 + 运行欧氏/垂距。
4. **直线/圆查找属性抛光** — 共用三 Tab：ROI 绘制|继承、跟随位姿、边缘极性、minLength/maxGap、半径范围、角度容差、结果显示/判断。
5. **全局变量表 UX** — 备注列、持久化列、「仅全局」过滤、复制变量/复制名称；工程字段 `variableNotes` / `variablePersist`。
6. **C#脚本** `csharp_script` — 设计态代码区（C#/Python 切换）、超时/入口/IO 变量表；运行返回 `unsupported`（无 CLR）；真实执行请用既有 `script`。

### Wave4 分页对照（Bilibili p ↔ 集标题）
| B站 p | 集内标题 | sieans op |
|------|----------|-----------|
| 12 | C#脚本 | csharp_script |
| 14 | 线与线的交点 | line_intersect |
| 15 | 矩形查找 | rect_find |
| 16 | 点与点之间的距离 | point_distance |
| 17 | 点与线之间的距离 | point_line_distance |

### Wave4 新看 / 下帧
- 帧已齐：`frames/p12_*`、`p14_*`–`p17_*`（及既有 p05/p06 抛光对照）。

## 65 集下一步建议顺序

1. 未下未看优先：p=1–3 入门；**p=31–65 行业案例**（见下「行业案例策略」）。  
2. 功能加深：通信真实后端、畸变/九点算法、输出图像落盘、HMI 控件深度、script/CLR 宿主、几何亚像素。  
3. 点测表更新 Wave2–Wave4 项为 PASS（壳级）。

### 行业案例策略（p=31–65）
- 详见上方 **「全系列 1–65 状态总表」**。
- Wrap 已加 **`production_task`（生产任务）** 薄壳；其余机器人/旋转/十二点/抓取保持 Skip(industry)。
- 深机器人/机械臂/多机联动：只做目录壳与流程示意，不深接厂商 SDK（除非 Allen 点名某集要可跑 demo）。

---

*帧证据均在 `docs/vm-bilibili-jgtech/frames/pXX_*`；对照时打开同名片关键帧即可。*


---

## Wave2 新看分集笔记（p=13 / 20 / 23 / 27）

> 用户点名「p=12 畸变 / p=20 九点 / p=22 变量 / p=27 耗时」；Bilibili 分页实际为 **p=13 畸变矫正、p=20 九点、p=23 变量计算、p=27 耗时**（p=12=C#脚本、p=22=输出图像）。Wave2 已下帧；**Wave3 已实现**畸变/九点/变量计算/耗时壳。

### p=13 畸变矫正
- 工具箱可见标定类算子；流程常与图像源串联。
- sieans：无畸变矫正独立 op → 记入后续（可挂 camera / measure.calibration）。

### p=20 平移九点标定
- 长课时；标定表 + 坐标系；工具箱有「九点标定」。
- sieans：`measure.calibration` 字段已有但无九点表 UX → 后续。

### p=23 变量计算
- 浮窗 Tab：**基本参数 / 结果显示**。
- 表列：名称（var0…）/ 表达式（公式编辑）/ 初始值 / 输出类型 / 初始化开关。
- sieans：`variables` 仅 set/increment → 后续可加 `var_calc` 表达式表壳。

### p=27 耗时统计
- 浮窗：**基本参数** 里 **开始 / 结束** 下拉选上游模块；**结果显示** Tab。
- sieans：节点已有 `elapsedMs`；缺「起止模块」统计壳 → 后续小项。


### p=21 格式化（发出数据）
- 模板字符串 + 参数 → 发出/写入；sieans：`format_data` 薄壳。

### p=22 输出(保存)图像
- 保存上游图像路径/格式；sieans：`output_image` 薄壳（落盘宿主侧后续）。

### p=24 协议解析
- 从接收缓冲按分隔/JSON/正则拆字段；sieans：`protocol_parse`。

### p=25 文本保存
- 写/追加文本文件；sieans：`text_save`（运行可写盘）。

## 【2026-10-27 续】P2 卡尺级 · 暂停

Geometry/Locate 运行参数对齐 p05/p06/p07 帧字段密度（边缘类型/滤波/卡尺宽/剔除/扇环/全部搜索/极性/级数等）；引擎 OpenCV 软用，无假 Halcon。工具栏轻抛光。**暂停等 Allen 试用反馈。**

## 【2026-10-27 深夜】九点 OK/NG · Comm 多协议 · 报警导出 · 细妆续

- **九点打开即跑**：`open-and-run-ninepoint.sieans` → nine_point→var_calc；注入 `nine_point_rms/_count/_ok`；`passGate`（点数≥9 且 rms<0.5）；runUi OK/NG×4。
- **Comm 多协议样例**：`open-and-run-comm-multiproto.sieans` — LocalBus 主路径 + TCP Client/UDP 写出（socket 模拟回退）；冒烟 PASS。
- **报警历史导出**：上位机状态机「复制CSV」「导出…」（`alarm_history_csv`）。
- **细妆**：九点属性「验证示意」三步 Tab；`script` 红叹号；`default-platform` 默认壳=图像+上位机状态机；固定栏实况（状态/判定/计数）。
- **冒烟**：`node scripts/smoke-ninepoint-comm-alarmexport-e2e.cjs` → 18 PASS。
- **不做**：无 push、无机械手 SDK、无 HIK logo。

