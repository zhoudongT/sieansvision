# VisionMaster 完整功能与设计总览

| 项 | 内容 |
|----|------|
| 目的 | 回答「看完全系列后，VM 软件功能与设计到底是什么」——**不是**分集对照表的替代品，而是可落地的产品/交互总览 |
| 主要依据 | Bilibili 茗工-JGTech《海康 VisionMaster 系列》**BV19vUfBVEpp** 全 65 集帧（`docs/vm-bilibili-jgtech/frames/`）+ `docs/VM-Bilibili-JGTech对照.md` + `docs/VM-UX对照要点.md` + 点测 `docs/VM功能对比与点测-2026-10-27.md` |
| 参考版本（帧内） | VM **V4.2 / V4.3** 工作台；上位机课为 WinForms + ReaLTaiizor 自建壳 |
| 日期 | 2026-10-27（Asia/Shanghai） |
| 边界 | **描述 VM 可见功能与设计规律**；不复刻海康算法内核 / 安装器 / 厂商机械手 SDK。sieans 品牌色为橙，交互分区对齐本文 |

> 阅读顺序建议：§1 定位 → §2 工作台 → §3 功能清单 → §4 设计原则 → §5 sieans 落地 → §6 优先级。

---

## 1. 产品定位与整体架构

### 1.1 产品是什么

VisionMaster（海康机器人视觉平台）在教程里呈现为：

- **方案工程工作台**：拖拽算子组成检测/定位流程，本地图或工业相机取流，一次/连续运行，看结果与耗时。
- **方案文件**：`.sol`（整案）；单流程可导出 `.prc`。
- **设计态 vs 运行态**：设计态编流程与参数；运行态切到操作员 HMI（画布锁定），用按钮/信号灯/图像窗操作产线。
- **外围能力**：通信管理（TCP/串口/PLC 等）、全局变量、全局触发、脚本、标定、运行界面设计器；行业课再接到**上位机状态机**与机械手引导（属扩展，非核心视觉内核）。

### 1.2 逻辑分层（从视频归纳）

```
┌─────────────────────────────────────────────────────────────┐
│ 运行态 HMI / 上位机状态机（手动·自动 · Idle/Run/Pause/Alarm） │
├─────────────────────────────────────────────────────────────┤
│ 运行界面设计器（控件库 · 触发命令 · 固定栏 · 分屏）            │
├──────────────┬──────────────────────┬───────────────────────┤
│ 全局触发      │ 通信管理 + 收发数据   │ 全局变量 / 变量计算    │
├──────────────┴──────────────────────┴───────────────────────┤
│ 流程引擎：图像源 → 定位/几何/标定/逻辑 → 格式化/发送/存图     │
├─────────────────────────────────────────────────────────────┤
│ 图像采集：本地胶片 / 相机(MVS) / SDK 嵌入；标定与畸变         │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心对象

| 对象 | 含义（教程用语） |
|------|------------------|
| **方案** | 工程容器：多流程、变量、通信、运行界面、触发 |
| **流程** | 画布上的有向算子图；Tab「流程1」…；可「全流程」 |
| **模块/算子** | 节点：`{序号}{名称}{实例}`，如 `0图像源1`、`1快速匹配1` |
| **图像源** | **一个**节点，属性里切「本地图像 / 相机 / SDK」，不是三个算子 |
| **组合模块** | 进组前绑 ImageData / InputROI；组内再挂子流程 |
| **生产任务** | 面向产线的任务名/配方 + 建议检测链（常接到上位机发送） |
| **上位机** | 独立 WinForms 壳：连机械手 IP/端口、运动/吸嘴、自动运行状态机（教程后半段） |

---

## 2. 工作台信息架构

### 2.1 五区布局（设计态）

```
┌──────────────────────────────────────────────────────────────────┐
│ ① 标题：Vision Master + 菜单 + 方案名 +「运行模式」切换            │
├──────────────────────────────────────────────────────────────────┤
│ ② 工具栏：新建打开保存 · 撤销重做 · 相机 · var · 通信 · 脚本     │
│          · ▶单次 / ↻连续 / ■停止                                 │
├────┬─────────────────────────────┬───────────────────────────────┤
│ ③  │ ④ 流程画布（点阵 · pill 节点 │ ⑤ 图像 / 模块结果 Tab          │
│算子│    · 橙连线 · 小地图）        │    棋盘空态 · 缩放 · 像素条     │
│纵栏│                             ├───────────────────────────────┤
│分类│                             │ ⑥ 胶片条（本地图）：n/N · 自动  │
│图标│                             │    切换 · 运行全部 · 添加文件夹 │
│    ├─────────────────────────────┴───────────────────────────────┤
│    │ ⑦ 底栏：当前结果 / 历史结果 / 帮助                            │
├────┴─────────────────────────────────────────────────────────────┤
│ ⑧ 状态栏：组件配置完成 | 流程/工具/算法 ms | 日志 | 版本           │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 菜单（中文原文习惯）

| 菜单 | 典型内容 |
|------|----------|
| **文件** | 新建/打开/保存方案（`.sol`）；导入导出流程（`.prc`） |
| **设置** | 显示/全局；设计态↔运行模式 |
| **工具** | 运行界面设计、全局触发、脚本等 |
| **系统** | 系统级 |
| **帮助** | 帮助 |

右侧常驻 **运行模式** 开关（设计 ↔ 运行）。

### 2.3 算子库分区（纵栏分类，教程可见类目）

常见分组标签（不同版本略有出入，交互一致）：

`通用 / 采集 / 定位 / 测量 / 图像生成 / 识别 / 深度学习 / 标定 / 运算 / 图像处理 / 颜色处理 / 缺陷检测 / 逻辑工具 / 通信 / 全局 / 拆分组合 / 基础库`

**图像采集**信息树（三课统一）：

```
图像采集
├── 图像源          ← 核心：本地 / 相机 / SDK 三态下拉
├── 多图采集 / 输出图像 / 缓存图像 / 光源 …
```

交互：**搜索 → 拖到画布 → 自动命名 → 双击开属性浮窗**；底栏日志形如 `添加模块: 流程1.图像源1`。

### 2.4 属性浮窗壳

- **浅色面板**叠在深色画布上；标题 `{序号} {模块名}`。
- 底栏固定：**连续执行 / 执行 / 确定**（模块级，与工具栏全局运行分离）。
- 控件：胶囊 Toggle（ON=橙）、SpinBox + 右侧**变量绑定**小图标、下拉激活橙边框。
- **快速/灰度匹配**顶栏 **四 Tab**：`基本参数 | 特征模板(或灰度模板) | 运行参数 | 结果显示`。
- **图像源**多为单页分组滚动（无四 Tab）。
- 变更审计日志：`时间 流程名.模块名.参数 参数已修改, 旧值:x, 新值:y`。

### 2.5 运行态 / HMI

- 切运行模式 → 操作员界面；画布不可编。
- **运行界面设计器**：分屏预设（1/2/3/4/6/8/9）、固定栏、控件库四分类：
  - **基础**：图像、多图像、运行控制、运行状态、OK/NG、文本、按钮、开关、信号灯、IP、端口、连接状态…
  - **布局**：组合框、子界面、Tab 页
  - **图表**：表格、线图、生产统计、饼图…
  - **其他**：图片、世界时钟、界面日志、信息提示栏
- 按钮 **触发命令**（可多条自上而下）：界面链接 / 参数配置 / 复位 / 方案保存 / 执行·单次|连续|停止 / 模块动作…
- 默认运行壳常见：大图 + OK/NG + 日志 + 单次/连续/停止。

### 2.6 上位机状态机 UI（p41–43 帧归纳，独立壳）

教程用 VS WinForms + Material/ReaLTaiizor 做「上位机控制程序」：

| Tab | 内容 |
|-----|------|
| **手动控制** | 连接机械手：IP、端口、连接、回原点；运动控制：X/Y/Z/角度/速度 + 运动；吸嘴：吸力 + 开启/关闭 |
| **自动运行** | 三组并行：**正常生产 / 九点标定 / 旋转标定**，各组「开始/暂停/继续/停止」；旋转组旁常有 X/Y/Z 偏移；底部 **信息显示栏** |

状态语义（产品层）：**Idle（空闲）/ Running / Paused / Alarm / Stopped**；开始跑检测流，停止取消；报警需清除。  
**注意**：这是上位机 UI 与状态编排，**不等于**已实现某家机械手协议 SDK。

---

## 3. 完整功能清单（按模块）

下列条目来自 65 集标题 + 帧内可见控件/流程，按产品模块归并。  
标注：`[核心视觉]` / `[平台]` / `[行业扩展]`。

### 3.1 图像采集 `[核心视觉]`

| 能力 | 视频中的具体表现 |
|------|------------------|
| 本地图像 | 图像源=本地；胶片条 `图像源(n/N)`；添加文件/文件夹；**自动切换**；**运行全部** |
| 相机取图 | 图像源=相机；「相机管理」连设备；曝光/增益；未配时状态栏红字「组件参数未配置完整」 |
| SDK / 嵌入 | 图像源=SDK；与第三方控件嵌入取流（教程有专用课） |
| 输出/保存图像 | 流程末「输出(保存)图像」落盘；可格式转换 |
| 虚拟相机 / MVS | 安装课：先 MVS 设备树再 VM（产品依赖采集中间件，非工作台本体） |

### 3.2 定位与匹配 `[核心视觉]`

| 能力 | 要点 |
|------|------|
| 快速模板匹配 | 四 Tab；特征模板创建/载入/编辑；ROI；评分/角度/极性/超时；多模板「全部搜索」 |
| 灰度模板匹配 | 同壳，`matchMode=灰度`；级数/亚像素等运行参数 |
| 位置修正 | 匹配位姿 → 校正后续 ROI/坐标系；链：`匹配 → 位置修正 → 检测` |

### 3.3 几何与测量 `[核心视觉]`

| 能力 | 要点 |
|------|------|
| 直线查找 / 圆查找 / 矩形查找 | ROI、阈值、极性、结果叠加；矩形多为 minAreaRect 类 |
| 线线交点 / 点点距离 / 点线距离 | 绑定上游几何或手填；输出交点/距离供变量与发送 |

### 3.4 标定与畸变 `[核心视觉]` + 部分 `[行业扩展]`

| 能力 | 要点 |
|------|------|
| 畸变矫正 | 内参/标定文件；未标定要明确提示 |
| 平移九点标定 | 像素↔世界九点表；仿射/最小二乘；生产流程多 Tab 复述（p54） |
| 验证九点 | 图像位 → 机械坐标 →（臂测）三步；后步依赖机械手 |
| 旋转中心 / 十二点 / 单点抓取 | p44–61、64 等：**理论 + 行业模块**；依赖机械手与旋转标定 SDK |
| 上下相机对位贴合 | 多相机对位流程（行业） |

### 3.5 流程控制与逻辑 `[平台]`

| 能力 | 要点 |
|------|------|
| 条件分支 | 规则表（变量、比较、常量）→ 真/假出边；AND/OR |
| 分支模块 | 多路径表 + 出边 `when=路径名` |
| 组合模块 | ImageData / InputROI；进组编辑；未配整颗告警 |
| 耗时统计 | 开始/结束模块下拉；区间 ms |
| 全局触发 | 触发串 / **部分匹配** / 执行流程或模块；常与通信收数联动 |
| 生产任务 | 任务名、配方、状态变量；建议链：图像→匹配→修正→特征→物理坐标→偏差→发送上位机（p40） |

### 3.6 变量与脚本 `[平台]`

| 能力 | 要点 |
|------|------|
| 全局变量表 | 名/类型/值；备注、持久化；模块参数右侧绑定 |
| 变量计算 | 表达式表：名称 / 公式 / 初始 / 类型 / 初始化开关 |
| 格式化（发出数据） | `{0}` / `{name}` 模板 → 字符串变量 |
| 协议解析 | 分隔 / JSON / 正则 / **定长** |
| C# 脚本 | 设计态代码；教程后期用 C#+OpenCV；产品侧常有 CLR 宿主（sieans **无 CLR**，用 Python+OpenCV 等价） |

### 3.7 通信与协议 `[平台]`

| 能力 | 要点 |
|------|------|
| 通信管理 | 设备列表（TCP Client/Server、UDP、串口、MQTT、Modbus、OPC UA、S7…）；接收/发送事件；心跳；响应 |
| 接收数据 / 发送数据 | 流程算子绑定设备名；收→写变量；发←文本/变量 |
| TCP 连通测试 | 主机/端口发一行读回（教程与管理面对齐） |
| 远程 IP 设置 | p31 教程式；本质是通讯主机配置 |

### 3.8 数据存取 `[平台]`

| 能力 | 要点 |
|------|------|
| 文本保存 | 追加/覆盖写文件 |
| 输出图像 | 见采集 |
| 历史结果 / 运行日志 | 底栏与界面日志控件 |

### 3.9 运行界面与状态机 `[平台]` + `[行业扩展]`

| 能力 | 要点 |
|------|------|
| 运行界面设计 1/2 | 分屏、控件库、触发命令、固定栏、模板保存 |
| 默认运行壳 | 图像 + OK/NG + 运行状态 + 日志 + 运行控制 |
| 上位机状态机 UI | 见 §2.6；**无厂商臂协议不算「机械手功能完成」** |

### 3.10 行业引导能力边界 `[行业扩展 · 刻意非 SDK]`

| 主题（集） | 可借鉴的 UI/流程 | 不做的深度 |
|-----------|-----------------|------------|
| 定位引导 · 自动化九点 / 文件夹模拟 | 复用九点 + 胶片模拟 | 机械手闭环 |
| 相对移动纠偏 / 图像·机械基准 | 流程步骤名、变量命名 | 臂控 SDK |
| 生产任务设计 | 任务链面板、可应用为流程节点 | 产线 PLC 整包 |
| 旋转中心理论 / 十二点 / 抓取 / 对位角度 | 文档级公式与步骤 | 旋转标定与抓取运行时 |
| 安装/卸载/宣发短片 | 无 | 海康安装器克隆 |

---

## 4. 交互与视觉设计原则（从视频归纳）

1. **Dark 工作台 + 浅色属性浮窗**：画布炭黑点阵；浮窗浅底深标题；强调色橙（开关 ON、主按钮、选中边）。
2. **一个图像源节点、三种取图模式**：禁止拆成三个拖拽算子。
3. **双击 = 配置**：属性浮窗是调参主路径；底栏「执行」只跑当前模块。
4. **未配置必须可见**：节点右上 **红叹号**；状态栏「组件参数未配置完整」；通讯未绑通道同样告警（N4）。
5. **匹配类四 Tab 定律**：基本 / 模板 / 运行 / 结果 —— 其它复杂算子可同构（几何、组合等可收敛到 3–4 Tab）。
6. **命名与连线**：`序号+名称+实例`；连线表示数据订阅；输入源下拉写 `0 图像源1.图像`。
7. **本地图胶片条是一等公民**：计数、自动切换、运行全部与属性 `autoSwitch` 联动。
8. **设计态 ≠ 运行态**：运行态锁画布；HMI 用触发命令驱动执行/停止/界面链接。
9. **通信集中配置、流程薄引用**：设备在「通信管理」；流程里只放收发算子并选设备名。
10. **生产链可复述为算子串**：p40 心智图可直接映射到 locate → pose_correct → geometry → nine_point/var_calc → send_data。
11. **上位机是状态机 UX，不是算法**：手动/自动 Tab + Idle/Run/Pause/Alarm；运动/吸嘴可为示意，协议另接。
12. **日志可审计**：添加模块、参数新旧值、运行完成耗时，底栏/界面日志双通道。

---

## 5. 与 sieansvision 落地对照

仓库：`/home/allen/文档/sieansvision`。品牌：**sieans 橙**；**不**克隆 HIK Logo / 安装器；**不**接机器人厂商 SDK。

### 5.1 已实现（设计态 + 可跑，含实用运行）

| 域 | sieans 落点（摘要） |
|----|---------------------|
| 工作台五区 | Dark 壳、算子纵栏、点阵画布、pill 节点、图像/结果、胶片条、状态栏 |
| 图像源 | 本地/相机/SDK；胶片；自动切换；相机管理 GenTL |
| 定位 | `LocateMatchPanel` 四 Tab；fast/gray；`pose_correct` |
| 几何 | 线/圆/矩形查找；交点/点距/点线距 |
| 标定 | `distort_correct`（OpenCV undistort）；`nine_point` 仿射 |
| 流程逻辑 | condition / branch / group+N4 / elapsed_stats / 全局触发部分匹配 |
| 变量脚本 | 变量表 UX；`var_calc`；`format_data`；`protocol_parse`；`text_save`；`csharp_script`→**Python+OpenCV**（无 CLR） |
| 通信 | `CommManagerDialog`（设备/收发/心跳/响应/**TCP 测试**）；`receive_data`/`send_data` |
| 运行 HMI | 运行界面设计器；控件库四分类；OperatorHmiView；默认壳；触发命令 |
| 生产任务 | `production_task` 面板 + 建议链；可「应用到当前流程」串节点（深化中） |
| 九点行业复述 | 复用 `nine_point`（p54） |

### 5.2 壳 / 部分（可用但薄）

| 项 | 说明 |
|----|------|
| p41–43 上位机状态机 | 已有/在建 Host 状态机控件（手动/自动 · Idle/Run/Pause/Alarm · IP/端口）；**无机械手协议** |
| p31 远程 IP | 复用 CommManager，教程式 |
| N4 红叹号 | 已覆盖 source/locate/group/通讯/condition 等；覆盖面可再扫 |
| 工具栏纯图标 / 算子密度 | 点测 Partial，需人工观感 |
| 通信收发 ↔ 变量深绑定 | 事件表有，运行时变量回写可再加深 |
| 几何亚像素/卡尺级 | 有结果，未对齐 VM 全部精细参数 |

### 5.3 刻意不做

| 项 | 原因 |
|----|------|
| 海康安装器 / MVS 卸载向导 / HIK Logo | 产品边界 |
| 机械手厂商 SDK、十二点/旋转中心运行时、单点抓取闭环 | Allen 明确无 robot vendor SDK；对照标 Skip(industry) |
| C# CLR 宿主 | 本机用 Python+OpenCV 替代可跑路径 |
| 海康算法比特级复刻 | 只对齐交互与流程 |

### 5.4 分集状态速查

详见 `docs/VM-Bilibili-JGTech对照.md` 全表：**p1–65 均 Watched**；p1–30 及 p40/54/62–63 等为 Implemented 或可模仿落地；p32–39、44–53、55–61、64 等为 Skip(industry)/理论/宣发。

---

## 6. 推荐后续深化优先级

面向「用户打开 App 立刻能点」的可见 UX（与 Allen t189「开启引擎疯狂修改」一致）：

| 优先级 | 项 | 理由 |
|--------|----|------|
| **P0** | 上位机状态机 HMI 做深（默认运行壳嵌入；开始/停止绑流程；信息栏） | p41–43 最大剩余 Shell*；帧控件清晰 |
| **P0** | `production_task`「应用到流程」可一键跑通 demo 链 | p40 心智图闭环 |
| **P1** | CommManager 收发事件 ↔ 流程变量写回；TCP 测试结果进变量 | p10/11/31 |
| **P1** | N4 红叹号全算子扫盲；属性面板密度贴帧 | 设计可信度 |
| **P1** | 胶片条/自动切换/运行全部与图像源属性持续对齐 | p4 核心 UX |
| **P2** | Locate/Geometry 结果显示与卡尺级参数 | 匹配/测量课 |
| **P2** | 运行界面模板「上位机」一键套用；触发命令暂停/继续/报警 | p28/29/41–43 |
| **P3** | 九点验证 UI 三步示意（无臂测） | p36 流程叙事 |
| **不做** | 旋转中心/十二点/抓取 SDK、安装器、CLR | 边界不变 |

---

## 7. 典型可复述流程（给实施同学）

### 7.1 本地快速匹配 demo（p4+p7）

1. 拖「图像源」→ 本地图像 → 胶片加图 → 自动切换可选  
2. 拖「快速匹配」→ 四 Tab 建模板 → 输入源选 `图像源.图像`  
3. ▶ 单次 / 连续；看模块结果与 OK/NG  

### 7.2 定位纠偏到发送（p40 建议链，无机械手）

`图像源 → locate → pose_correct → geometry(圆) → nine_point/var_calc → var_calc(dx,dy) → format_data → send_data`  
通信管理里配 TCP；上位机 HMI 仅示意接收。

### 7.3 运行态操作员（p28/29 + p41–43）

设计态配好流程与运行界面 → 开运行模式 → 用「开始运行」连续跑 → 「停止」→ 报警示意与清除 → 看信息栏与 OK/NG。

---

## 8. 文档与素材索引

| 路径 | 用途 |
|------|------|
| `docs/VM-Bilibili-JGTech对照.md` | 65 集逐条 Watched / Implemented / Shell / Skip |
| `docs/VM-UX对照要点.md` | 工作台分区、图像源字段、匹配四 Tab 细表 |
| `docs/VM功能对比与点测-2026-10-27.md` | sieans 点测 PASS/FAIL 矩阵 |
| `docs/vm-bilibili-jgtech/frames/pXX_*` | 帧证据 |
| `bin/bili_fetch.py` | 下集与抽帧 |

---

*本文是「看完视频后的功能+设计总览」，供产品对齐与 sieans 深化排期；算法数值与厂商协议以现场 SDK 为准，sieans 侧不宣称机械手/旋转标定 SDK 已实现。*

> 2026-10-27：打开即跑默认工程 + 打开/运行自动载入源图 + 运行态生产统计（OK/NG/历史/报警/暂停）已落地，engine-host 样张链 E2E 通过。

## 【2026-10-27 深夜】九点 OK/NG · Comm 多协议 · 报警导出 · 细妆续

- **九点打开即跑**：`open-and-run-ninepoint.sieans` → nine_point→var_calc；注入 `nine_point_rms/_count/_ok`；`passGate`（点数≥9 且 rms<0.5）；runUi OK/NG×4。
- **Comm 多协议样例**：`open-and-run-comm-multiproto.sieans` — LocalBus 主路径 + TCP Client/UDP 写出（socket 模拟回退）；冒烟 PASS。
- **报警历史导出**：上位机状态机「复制CSV」「导出…」（`alarm_history_csv`）。
- **细妆**：九点属性「验证示意」三步 Tab；`script` 红叹号；`default-platform` 默认壳=图像+上位机状态机；固定栏实况（状态/判定/计数）。
- **冒烟**：`node scripts/smoke-ninepoint-comm-alarmexport-e2e.cjs` → 18 PASS。
- **不做**：无 push、无机械手 SDK、无 HIK logo。

### 细妆续 · 工具栏/算子库密度 + 固定栏通讯实况

- 主工具栏 `ToolButtonIconOnly` + 18px 图标 + 紧间距（对标 VM 纯图标观感；文案走 ToolTip）。
- 算子库 IconSize 24 / Grid 64×52。
- 固定栏 `_refresh_fixed_bar_device_status` 读通讯徽章；HMI IP/端口/连接状态可 `set_device_chrome` 实况刷新。


## 【细妆进度 · 2026-10-27 续】

已闭合本批：胶片条**格式过滤下拉**（显 N / 文件夹导入同步）；报警历史**关键字筛选**；Host 信息栏 ↔ HMI「信息提示栏」单向镜像；Group **显示设置**开关（showInnerImage/ROI）+ 循环引擎展开文案；进组**组内红叹号**扫盲 chip。


## 【细妆进度 · 2026-10-27 续②】

已闭合：设置菜单「运行间隔/流程超时」；胶片格式↔sourceConfig 双向；浮窗连续跑热更新字幕；N4 状态栏 ToolTip 计数；HMI 表格/饼图/线图可视化；固定栏绑定「实况」文案；从模板「多协议通信」；all_flows 显示说明。


## 【细妆进度 · 2026-10-27 续③】

已闭合：模板**编辑子窗**（对比度阈值 / 画笔 / 特征尺度 / 灰度级数）；固定栏相机会话缓存 `_note_camera_session` 非阻塞实况。

## 【代码细妆已收口 · 外依赖未做 · 2026-10-27 22:10】

> Allen t194：每一处细妆完成。下列为收口声明（无 robot SDK / 无 push）。

### 代码细妆已收口（本机可验）
- 主工具栏 `mainToolBar`：18px **单色矢量图标**（无 emoji）、CN ToolTip、品牌条 `brandStrip` 与分隔线分区
- overlay→engine/canvas 实绘（locate / geometry / measure_geom）
- HMI：连接灯、变量/参数格、组合框 QStackedWidget 嵌套页、Tab 嵌套下拉 + 拖放约束文案、子界面壳
- harvest 全覆盖；全流程 I/O 回写；Comm 试收→`fire_string_trigger(RUN/CONT)` 活路
- 行业运行壳模板 ×4（电子点检 / 尺寸测量 / 包装缺陷 / **印刷字符读码**）
- labels EN→CN 扫尾；Group/连续路径 tip；卡尺σ/投影角 UI

### 外依赖未做（明确不宣称完成）
- **真机 TCP / 现场设备** 联调（环回模拟器已接，硬件未验）
- **真实远端云 / 模板市场后端**（本地站 :19779 已接为替身）
- **Halcon 卡尺核**（几何直线已接 OpenCV 多卡尺边缘拟合；非 Halcon）
- **robot / 机械手 SDK**（按 Allen 指示跳过）
- chrome **人工观感签字**（截图已留档时可人工复核）

## 【细妆剩余清单 · 持续更新 · 2026-10-27 深夜】

> Allen t194：每一处细妆完成；下列为仍未闭合项（无 robot SDK / 无 push）。

| 域 | 剩余细妆 |
|----|----------|
| chrome | **单色图标已接** + 截图留档（artifacts/toolbar-chrome-mono.png）；人工观感签字仍外置 |
| panels | overlay 实绘已接；**measure_geom 上游挑选/字段绑定/叠层开关即时同步**；geometry 卡尺σ/投影角 UI 已补 |
| harvest | 全覆盖（elapsed 下拉选步，无需 harvest） |
| HMI | 组合框嵌套已接；**趋势 spark / 饼图 / 结果表**跟生产统计 elapsed+OK/NG 实时刷新 |
| filmstrip / 全流程 | 已接；**流程参数 I/O 可回写**；卡片间顺序 → 已示意 |
| float | 已接 |
| nest/Group | 引擎展开 tip 已接 |
| labels | EN→CN 扫尾已接 |
| settings | 已接 |
| samples | 四行业 UI 壳 + 打开即跑卡尺/卡尺→几何测量/测量/TCP环回；**卡尺·卡尺测量 Runtime e2e（live）** 已接 |
| Comm | 试收触发活路已验；**环回协议模拟器**（:19880）可本机联调；真机 TCP 仍外置 |
| Host SM | 已接 |
| 云/市场 | 模板市场 + **本地云同步站**（:19779 list/publish/sync）已接；真实远端后端仍外置 |
| 算法核 | 直线 **多卡尺+多边缘分带**（OpenCV）；Halcon 核仍外置 |
| 扩展插件 | 第三方 plugin 无专用属性页时走通用保留（catalog 回退文案） |




## 【细妆㊨ · 导引带自定义色拾取 · 撤销条可拖时长 · PNG命名模板 · 热同步α滑条 · 脉冲强度 · 2026-10-28】

- **导引带自定义色拾取**：`custom` 预设 + `mergeDiffFailHistDropSnapGuideCustomHex`；`prompt_merge_diff_fail_hist_drop_snap_guide_custom_color`（QColorDialog）；菜单「自定义色拾取…」。
- **撤销条可拖时长**：`sevPinSoloDeleteUndoMs` 1.5–12s；滚轮 / Shift·Ctrl·Alt+左右拖 / 右键 2/4/6/8/10s 预设；`set_sev_pin_solo_delete_undo_ms(rescale_left=True)`。
- **PNG 导出命名模板**：`toastCurvePngNameTemplate` 默认 `tip-anim-{easing}-{ts}.png`；占位 `{ts}/{date}/{easing}/{name}`；另存对话框默认文件名展开。
- **热同步 α 滑条**：色阶热同步菜单内嵌 `QSlider` 0–255；`refresh` 同步勾选与滑条值。
- **脉冲强度独立旋钮**：`mergeDiffFailHistDropPulseIntensityPct` 40–100%；缩放脉冲起/峰/终 opacity；导引带菜单内嵌强度滑条。
- **冒烟**：`smoke-wave59-guidecustom-undoms-pngtmpl-alphaslider-pulseinten-e2e`（另回归 wave58/57/56）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊧ · 导引带色/透明度预设 · 仅选删色短撤销 · PNG目录记忆/最近导出 · 热同步α步进 · 脉冲缓动 · 2026-10-28】

- **吸附导引带透明度/颜色预设菜单**：green/amber/cyan/soft/strong + α 8/12/20%；`_build_merge_diff_fail_hist_drop_snap_guide_menu`；同菜单含脉冲缓动快捷。
- **仅选删色撤销条**：删色后 4s 短撤销条 + toast 单击 `undo_solo_delete` → `undo_sev_pin_arc_seize_recent_shift_range_solo`。
- **PNG 另存默认目录记忆 + 最近导出清单**：`toastCurvePngExportDir` / `toastCurvePngRecentExports`；预览窗「最近导出」菜单。
- **热同步菜单内嵌 α 步进快捷项**：±5/±10/±20 勾选 + α±N；`refresh` 同步勾选态。
- **脉冲 easing 曲线可选**：`mergeDiffFailHistDropPulseEasing` 对齐 toast（OutCubic/InOutQuad/OutBounce/Linear）。
- **冒烟**：`smoke-wave58-guidepreset-soloundo-pngmem-hotsyncalpha-pulseeasing-e2e`（另回归 wave57/56/55）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊦ · 吸附预设可视化/脉冲时长 · 仅选快捷删色 · PNG另存再复制 · 热同步勾选实时 · α步进5/10/20 · 2026-10-28】

- **吸附预设可视化 / 脉冲时长可配**：`mergeDiffFailHistDropSnapThresh` 预设 10/18/28 + 虚线导引带 `hostMergeDiffFailHistDropSnapGuide`；`mergeDiffFailHistDropPulseMs` 控制落点高亮脉冲时长。
- **右键仅选后快捷删色**：Shift 区间条右键仅选后，再右键同色或 Del → `delete_sev_pin_arc_seize_recent_shift_range_solo`。
- **PNG 预览窗另存/再复制**：曲线剪贴板预览对话框增加「另存为…」「再复制」按钮。
- **热同步菜单勾选态实时刷新**：`refresh_undo_color_scale_hot_sync_menu` + `aboutToShow`；切换预设后 ✓ 即时同步。
- **α 步进可配 5/10/20**：`stalePruneUndoColorCustomAlphaStep`；预览窗「步进±N」循环；± 按钮跟步进。
- **冒烟**：`smoke-wave57-snapviz-pulsems-solodel-pngsave-hotsynclive-alphastepcfg-e2e`（另回归 wave56/55/54）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊥ · 落点高亮动画/跨日吸附 · Shift右键仅选 · 剪贴板toast预览 · 徽章色阶热同步 · α步进重置 · 2026-10-28】

- **落点高亮动画 / 跨日组吸附**：组头切换时 opacity 脉冲；`_snap_merge_diff_fail_hist_drop_target` 磁吸最近组头。
- **Shift 色块右键仅选该段**：右键清选后仅选该行；左键仍为跳转。
- **剪贴板 toast 单击预览 PNG**：toast action=`preview_curve_png`；`show_toast_hist_cap_tip_anim_curve_clipboard_preview`。
- **徽章条与 undo 预设热同步菜单**：改色阶预设热刷徽章条；右键徽章条弹出热同步菜单。
- **α 旋钮步进/重置默认**：`±10` / `重置默认`；`adjust_` / `reset_stale_prune_undo_color_custom_alpha_default`。
- **冒烟**：`smoke-wave56-dropanim-chipsolo-clippreview-hotsync-alphastep-e2e`（另回归 wave55/54/53）。

---

## 【细妆㊤ · 组头落点高亮/折叠态保留 · Shift色块可点跳 · 曲线剪贴板toast · 徽章色阶对齐 · α旋钮默认 · 2026-10-28】

- **组头拖拽落点高亮 / 折叠态保留**：拖拽中组头绿框高亮；`persist_merge_diff_batch_fail_history_collapsed` 写入 QSettings；重排后折叠态不丢。
- **Shift 区间条可点跳 / 色块**：条宽 10px，按选区色块分段；单击跳到对应行并 scrollTo。
- **曲线剪贴板后 toast**：复制后 `✓ 曲线 PNG 已入剪贴板 · W×H`；quiet 旗可关。
- **徽章倒计时条色阶对齐 undo**：复用 `_stale_prune_undo_bar_chunk_color`。
- **custom α 持久化 UI 旋钮默认**：`stale_prune_undo_color_custom_alpha_default`；预览旋钮读持久化 α。
- **冒烟**：`smoke-wave55-drophl-foldpersist-chipjump-cliptoast-badgealign-alphadef-e2e`（另回归 wave54/53/52）。

---

## 【细妆㊣ · 组头拖拽重排 · Shift区间视觉条 · 曲线PNG剪贴板 · 徽章撤销倒计时条 · undo α/渐变预览 · 2026-10-28】

- **失败历史组头拖拽重排**：列表 InternalMove；组头可拖、子项不可拖；`reorder_merge_diff_batch_fail_history_groups` 持久化顺序。
- **Shift 连选区间视觉条**：选区 ≥2 时左侧蓝条覆盖 min–max 行；`_update_sev_pin_arc_seize_recent_shift_range_bar`。
- **曲线 PNG 剪贴板**：小窗「复制剪贴板」；`copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard`。
- **徽章撤销倒计时条**：清历史后显示进度条（贴徽章下）；tick 色阶；左键撤销；`_show/_update/_hide_path_copy_badge_fail_hist_undo_bar`。
- **undo 色阶 α/渐变预览**：custom 含 α；chunk 用 rgba；`show_stale_prune_undo_color_custom_preview` + α 旋钮实时刷。
- **冒烟**：`smoke-wave54-groupdrag-shiftrange-curveclip-undobar-alphapreview-e2e`（另回归 wave53/52/51）。

---

## 【细妆㊢ · 组头计数徽章 · Shift连选提示 · 曲线导出PNG · 徽章撤销倒计时 · undo自定义RGB · 2026-10-28】

- **失败历史组头计数徽章**：日组头圆形数字图标（≥5 红 / ≥2 黄 / 否则蓝）；`_merge_diff_fail_hist_group_count_badge_icon`。
- **拖拽 Shift 连选提示**：tooltip/WhatsThis + Shift 键/选区变化时 `QToolTip`「Shift 连选 · 已选 N 项」；`_show_sev_pin_arc_seize_recent_shift_hint`。
- **曲线导出 PNG**：小窗「导出 PNG」；`export_toast_hist_cap_tip_anim_easing_curve_png`（grab 面板）。
- **徽章撤销倒计时**：清历史后 8s 窗口；菜单「撤销… · Ns」；tick/expire；`path_copy_badge_fail_history_undo_left_ms`。
- **undo 色阶自定义 RGB**：`custom` 预设 + hi/mid/lo 持久化；菜单「自定义 RGB…」；`set_/prompt_stale_prune_undo_color_custom_rgb`。
- **冒烟**：`smoke-wave53-groupbadge-shifthint-curvepng-undocountdown-customrgb-e2e`（另回归 wave52/51/50）。

---

## 【细妆㊡ · 失败历史全展/全折 · Ctrl+A · 双缓动对比 · 清历史撤销 · undo色阶预设 · 2026-10-28】

- **失败历史全展/全折**：对话框「全展/全折」按钮；`expand_/collapse_merge_diff_batch_fail_history_groups`。
- **拖拽列表 Ctrl+A**：全选最近色以便批量 Delete。
- **曲线小窗对比双缓动**：主/对比下拉；蓝/红双曲线；`show_toast_hist_cap_tip_anim_easing_curve_compare`。
- **徽章清历史撤销**：清除时快照；菜单「撤销清除失败历史」(Z)；`undo_path_copy_badge_fail_history_clear`。
- **undo 色阶预设**：traffic/cool/mono/sunset；右键菜单勾选；`set_stale_prune_undo_color_scale_preset`。
- **冒烟**：`smoke-wave52-failexpand-ctrla-curvecompare-badgeundo-colorscale-e2e`（另回归 wave51/50/49）。

---

## 【细妆㊠ · 失败历史分组折叠 · 多选Del · easing曲线小窗 · 徽章清历史 · undo色阶 · 2026-10-28】

- **失败历史分组折叠**：按日分组 ▾/▸ 头；单击折叠/展开；`_merge_diff_fail_hist_collapsed`。
- **拖拽列表多选 Delete**：ExtendedSelection；Del/Backspace 批量删选中。
- **tip 预览曲线小窗**：`show_toast_hist_cap_tip_anim_easing_curve` + 采样绘制；随 preview 弹出（quiet/no_exec 可关）。
- **徽章菜单清除历史**：`清除失败历史`（X）+ `clear_path_copy_badge_fail_history`；零条禁用。
- **undo 倒计时色阶**：绿→黄→红（`_stale_prune_undo_bar_chunk_color` / `_apply_…_color_scale`）。
- **冒烟**：`smoke-wave51-failgroup-multidel-curvepane-badgeclear-undocolor-e2e`（另回归 wave50/49/48）。

---

## 【细妆㊟ · 失败历史多选重开/导出 · Del/Home置顶 · easing预览 · 徽章红点 · undo自定义ms · 2026-10-28】

- **失败历史多选批量重开/导出**：ExtendedSelection；「批量重开选中」「导出选中」；`export_merge_diff_batch_fail_history` / `retry_merge_diff_batch_fail_history_selected`。
- **最近色拖拽列表键盘**：Delete/Backspace 删除单项；Home 置顶。
- **tip easing 预览脉冲**：`preview_toast_hist_cap_tip_anim_easing`；`set_…_easing` 默认触发（quiet 可关）。
- **徽章角标红点样式**：`_path_copy_badge_fail_history_icon` 叠加红点；count=0 无红点且无「·N」。
- **undo 预设自定义 ms**：菜单「自定义步进/延长 ms…」+ `prompt_stale_prune_undo_extend_step_ms` / `prompt_stale_prune_undo_extend_ms`。
- **冒烟**：`smoke-wave50-failmulti-dragkeys-easingpreview-reddot-undocustom-e2e`（另回归 wave49/48/47）。

---

## 【细妆㊞ · 失败历史排序 · 最近色右键置顶/删除 · tip easing · 徽章失败数角标 · undo步进±1s/±3s · 2026-10-28】

- **失败历史排序切换**：`merge_diff_batch_fail_history_sort_mode` time|path；对话框 `QComboBox`；`sorted_merge_diff_batch_fail_history`。
- **最近色拖拽列表右键菜单**：置顶 / 删除单项（`isSeizeRecentPinTop` / `isSeizeRecentDeleteOne`）。
- **tip 动画 easing 可配**：`toast_hist_cap_tip_anim_easing`（OutCubic/InOutQuad/OutBounce/Linear）；容量菜单；`_pulse_host_toast` 用配置曲线。
- **徽章菜单失败数角标**：`打开历史失败 · N` + `failHistoryCount` / `isPathCopyBadgeFailHistoryBadge`。
- **undo 步进快捷预设**：右键菜单 ±1s/±3s 延长；步进设为 1s/3s/0；`extend_stale_prune_undo_by` / `adjust_stale_prune_undo_extend_step_ms`。
- **冒烟**：`smoke-wave49-failsort-dragctx-easing-badgecount-undopreset-e2e`（另回归 wave48/47/46）。

---

## 【细妆㊽ · 失败历史搜索/过滤 · 最近色菜单内拖拽 · tip动画时长可配 · 徽章打开历史失败 · undo延长步进可配 · 2026-10-28】

- **失败历史搜索/过滤**：历史对话框 `QLineEdit` 过滤；`filter_merge_diff_batch_fail_history(query)`。
- **最近色菜单内拖拽**：`QWidgetAction` + InternalMove 列表；单击应用 · 右键清除 · 拖拽落盘。
- **tip 动画时长可配**：`toast_hist_cap_tip_anim_ms`（`host/toastHistCapTipAnimMs`）；容量菜单 200/320/500/800；`_pulse_host_toast` 用配置时长。
- **徽章「打开历史失败」**：菜单项 + 图标 + 快捷键 H → `show_merge_diff_batch_fail_history`。
- **undo 延长步进可配**：`stale_prune_undo_extend_step_ms`（0=重置全长兼容㊼；>0 则 left+step）。
- **冒烟**：`smoke-wave48-failfilter-menudrag-animms-badgehist-undostep-e2e`（另回归 wave47/46/41）。

---

## 【细妆㊼ · 失败清单持久化/历史 · 最近色Alt↑↓ · tip动画可关 · 徽章菜单图标 · undo点击延长 · 2026-10-28】

- **失败清单持久化/历史**：`remember_merge_diff_batch_fails` → QSettings；`merge_diff_batch_fail_history` / `show_merge_diff_batch_fail_history`；失败对话框「失败历史」。
- **最近色菜单 Alt↑↓**：色板 eventFilter Alt+Up/Down → `move_sev_pin_arc_seize_recent_color` 热更最近区。
- **tip 动画可关**：`toast_hist_cap_tip_anim_enabled`（`host/toastHistCapTipAnim`）；容量菜单「tip 热更动画」；关则 `_pulse_host_toast` 跳过。
- **徽章菜单图标**：`_path_copy_badge_menu_icon`（SP_FileDialogContentsView / SP_ArrowBack）。
- **undo 点击延长倒计时**：中/右键 → `extend_stale_prune_undo`；左键仍撤销。
- **冒烟**：`smoke-wave47-failhist-altmove-tipanimoff-badgeicon-undoextend-e2e`（另回归 wave46/45/41）。

---

## 【细妆㊻ · 失败项可点重开 · 最近色拖拽排序 · tip热更动画 · 徽章菜单快捷键 · undo悬停剩余秒 · 2026-10-28】

- **失败项可点重开**：批量 tip「点此重开失败」→ `show_merge_diff_batch_fails`（双击/重开选中/重开全部）；`retry_merge_diff_batch_fails`。
- **最近色拖拽排序**：`reorder_sev_pin_arc_seize_recent_colors` / `move_…`；菜单「拖拽排序最近色…」→ InternalMove 列表对话框。
- **tip 热更动画**：`_refresh_toast_hist_cap_keep_exit_tip_action` 热更后 `_pulse_host_toast` 淡入脉冲；`_flash_host_toast(..., animate=True)`。
- **徽章菜单快捷键**：再复制 `C` · 中键回退开关 `F`（`setShortcutVisibleInContextMenu`）。
- **undo 悬停剩余秒**：enter 放大同时 `剩余 Ns` tip/条内文案；tick 同步；leave 恢复。
- **冒烟**：`smoke-wave46-failreopen-recentdrag-tipanim-badgeshortcut-undohoversec-e2e`（另回归 wave45/44/41）。

---

## 【细妆㊺ · diff批量失败汇总tip · 最近色右键清除 · tip开关热更勾 · 回退开关挂徽章菜单 · undo条悬停放大 · 2026-10-28】

- **diff 批量开失败汇总 tip**：`open_merge_diff_paths` 统计 ok/fail；tip「已开 N · 失败 M · 首败名」；`_last_merge_diff_batch_fail`；quiet 抑单项 tip。
- **最近色右键清除**：色板菜单 eventFilter RMB → `clear_sev_pin_arc_seize_recent_color`；「清除全部最近色」；热更最近区。
- **tip 开关热更菜单勾**：`set_toast_hist_cap_keep_exit_tip_enabled` → `_refresh_toast_hist_cap_keep_exit_tip_action`。
- **回退开关挂徽章菜单**：右键 → `hostPathCopyBadgeMenu`（再复制 + 中键失败回退本级）；setter 热更勾。
- **undo 条悬停放大**：enter 10→16px / leave 恢复。
- **冒烟**：`smoke-wave45-batchfail-recentrmb-tiphot-badgemenu-hoverbar-e2e`（另回归 wave44/43/41）。

---

## 【细妆㊹ · diff多选批量开目录 · 色板自定义/最近色 · 保持tip可关 · 中键回退可配 · undo条可点撤销 · 2026-10-28】

- **diff 多选批量开目录**：清单 ExtendedSelection；「打开选中」→ `open_merge_diff_selected` / `open_merge_diff_paths`（去重批量）。
- **色板自定义/最近色**：`pick_sev_pin_arc_seize_custom_color`（QColorDialog）+ `remember_sev_pin_arc_seize_color`（最多 6）；菜单「最近」+「自定义…」。
- **保持 tip 可关**：`toast_hist_cap_keep_exit_tip_enabled` / 容量菜单「退出保持提示」开关（`host/toastHistCapKeepExitTip`）。
- **中键回退可配**：`path_copy_badge_parent_fallback_enabled`（`host/pathCopyBadgeParentFallback`）；关则失败不回退本级。
- **undo 条可点撤销**：进度条增高可点；`_on_stale_prune_undo_bar_clicked` → `undo_prune_stale_alarm_film_csv_dirs`。
- **冒烟**：`smoke-wave44-diffbatch-recentcolor-tiptoggle-fallbackcfg-undoclick-e2e`（另回归 wave43/42）。

---

## 【细妆㊸ · diff清单可点开目录 · 抢占预设色板 · 保持退出确认tip · 中键失败回退本级 · undo进度条 · 2026-10-28】

- **diff 清单可点开目录**：`show_last_merge_diff` 交互对话框（`hostMergeDiffList`）；双击/「打开目录」→ `open_merge_diff_path`；`_merge_diff_no_exec` 供冒烟。
- **抢占预设色板菜单**：`sev_pin_arc_seize_color_presets` + `_build_sev_pin_arc_seize_color_menu`（白/金/绿/青/粉/橙/红/紫 + 蜂鸣开关）；挂在「最近另存」子菜单。
- **保持退出确认短 tip**：「✓ 已退出保持 · 数字键将关闭菜单」（`_last_toast_hist_cap_keep_exit_tip`）。
- **中键失败回退本级**：父目录不可开时回退徽章路径本身并 tip「父目录失败 · 已回退本级」。
- **undo 进度条可视化**：`hostStalePruneUndoBar` 贴 toast 下方，随倒计时缩短；到期/撤销后隐藏。
- **冒烟**：`smoke-wave43-diffopen-seizepalette-exittip-midfallback-undobar-e2e`（另回归 wave42/41）。

---

## 【细妆㊷ · 合并tip点开diff · 抢占音/色可配 · 保持徽标一键退出 · 徽章中键父目录 · undo倒计时失效 · 2026-10-28】

- **合并 tip 点开 diff 清单**：合并 toast 带「点开清单」；`_host_toast_click_action=merge_diff` → `show_last_merge_diff`（新增/冲突/裁剪分类 QMessageBox）；`_last_merge_diff`。
- **抢占音/色可配**：`set_sev_pin_arc_seize_color` / `set_sev_pin_arc_seize_sound`（设置键 `host/sevPinArcSeizeColor` · `host/sevPinArcSeizeSound`）；闪色默认 `#ffffff`；音开则 `QApplication.beep()`。
- **保持徽标一键退出**：徽标文案「◉ 保持中 · 点此退出」（`isKeepExit`）；`exit_toast_hist_cap_keep` 清 keep 并移除徽标。
- **徽章中键开父目录**：`open_path_copy_badge_parent`；左开/右再复制/中开父。
- **undo 倒计时失效**：默认 8s（`set_stale_prune_undo_ms`）；toast 倒数；`expire_stale_prune_undo`；到期清 can_undo。
- **冒烟**：`smoke-wave42-mergediff-seizecfg-keepexit-midparent-undotimer-e2e`（另回归 wave41/40）。

---

## 【细妆㊶ · 合并冲突计数tip · 共享弧抢占可视化 · 容量保持徽标 · 徽章右键再复制 · 失效清理undo · 2026-10-28】

- **合并导入冲突计数 tip**：`merge_alarm_film_csv_dirs` 记录 conflict/new/trimmed；toast「已合并导入 · N 档 · 冲突x · 新增y · 裁剪z」。
- **共享弧 owner 互斥抢占可视化**：`claim_sev_pin_arc(owner)` 停前主 tick；抢占时弧闪白 + tip「进度弧抢占 · chip→bubble」；`_last_sev_pin_arc_seize`。
- **容量菜单「保持」徽标**：keep_open 时菜单顶栏「◉ 保持中 · 数字不关菜单」（`hostToastHistCapKeepBadge` / `isKeepBadge`）；长按触发后可注入已开菜单。
- **徽章右键再复制路径**：左键仍打开目录；右键 `copy_path_copy_badge_path` → 剪贴板 +「已再复制」。
- **失效清理 undo**：清理前快照；toast「点此撤销」/`undo_prune` 点击；菜单「撤销上次清理」；`undo_prune_stale_alarm_film_csv_dirs`。
- **冒烟**：`smoke-wave41-mergeconflict-seize-keepbadge-rmbcopy-pruneundo-e2e`（另回归 wave40/39）。

---

## 【细妆㊵ · 多档JSON合并导入 · 共享进度弧 · Alt+H长按H保持 · 徽章再点开目录 · 失效清理预览 · 2026-10-28】

- **多档 JSON 合并导入**：右键「最近另存」→「合并导入 JSON…」；去重并集（导入项置前 + 保留旧项，裁剪上限）；「导入记忆 JSON…」仍为覆盖写入。API：`merge_import_alarm_film_csv_dirs_json` / `merge_alarm_film_csv_dirs`；`import_…(merge=True|False)`。
- **气泡/芯片进度弧共享 overlay 单例**：`_sev_pin_arc`（`hostSevPinArc`）一实例，`_sev_chip_pin_arc` / `_sev_bubble_pin_arc` 为别名；`_sev_pin_arc_owner` 区分 chip|bubble，减双实例。
- **Alt+H 长按 H 保持菜单不关**：450ms 长按置 `_toast_hist_cap_keep_open`；数字键仍应用容量但不 `menu.close()`（`digit-hold`）；Esc 清除保持。对照：短按/未保持时数字键仍自动关。
- **复制徽章再点打开目录**：`hostPathCopyBadge` 文案「✓ 已复制 · … · 再点打开」；点击 → `open_host_toast_path`。
- **失效清理预览清单确认**：`preview_stale_alarm_film_csv_dirs`；`prune_stale_…(confirm=True)` 先 QMessageBox 清单再删；取消保留；菜单「清理失效目录（N）…」。
- **冒烟**：`smoke-wave40-mergejson-sharearc-holdh-badgeopen-prunepreview-e2e`（另回归 wave39/38）。

---

## 【细妆㊴ · 多档JSON导入导出 · 气泡弧同步 · Alt+H数字关 · 复制确认徽章 · 失效清理 · 2026-10-28】

- **多档记忆导出/导入 JSON**：`export`/`import_alarm_film_csv_dirs_json`（file 或文本）；子菜单「导出/导入记忆 JSON…」。
- **进度弧气泡同步**：`hostSevBubblePinArc` + tick；`sync_sev_bubble_pin_from_chip`；`set_sev_chip_pin_ms/color` 同步气泡时长/色。
- **Alt+H 数字键直达后自动关**：`toast_hist_cap_menu_key` 1–4 → 3/5/8/12 并 `close`；`_last_toast_hist_cap_closed_by=digit`。
- **路径回看复制确认徽章**：`hostPathCopyBadge`「✓ 已复制」；`flash_path_copy_badge`。
- **失效目录灰显/一键清理**：标题「（失效）」；另存禁用；`prune_stale_alarm_film_csv_dirs`。
- **冒烟**：`smoke-wave39-jsonio-bubblesync-digitclose-copybadge-prune-e2e`（另回归 wave38/37）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㊳ · 多档置顶拖序 · 进度弧时长/色 · Alt+H键导航 · 开目录tip回看 · 单项删除 · 2026-10-28】

- **多档记忆拖序/置顶**：`promote`/`move`/`reorder_alarm_film_csv_dirs`；最近子菜单每项 → 另存/置顶/删除此项。
- **进度弧可配时长/色**：`host/sevChipPinMs` 300/550/800；`host/sevChipPinArcColor`；`set`/`cycle`。
- **Alt+H Esc/方向键导航**：`navigate_toast_hist_cap_menu` / `toast_hist_cap_menu_key`；eventFilter Esc 关闭、↑↓ 移焦、回车触发。
- **开目录 tip 可点回看路径**：成功 tip 绑路径 → 单击 `review_host_toast_path`（全路径 tip + 剪贴板）；再点开目录。
- **最近另存单项删除**：`remove_alarm_film_csv_dir`；菜单「删除此项」（非整清）。
- **冒烟**：`smoke-wave38-promote-pinms-harnav-reviewpath-rmslot-e2e`（另回归 wave37/36）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㊲ · 多档上限可配 · Alt+H焦点键选 · 长按落钉进度弧 · 开目录成功tip · 最近另存清档 · 2026-10-28】

- **多档记忆上限可配**：`host/alarmFilmCsvDirsMax`（3/5/8）；`set`/`cycle`/`_apply`；超限裁剪；子菜单「记忆上限」。
- **Alt+H 菜单焦点键选**：`_focus_toast_hist_cap_menu` 将焦点落在当前容量项；右键同样；toast 提示焦点。
- **长按落钉进度弧**：`hostSevChipPinArc` + tick 40ms；按下推进、松开/离开收弧、满弧落钉。
- **开目录成功 tip 区分**：成功「已打开目录」；软成功「目录已就绪（系统未打开）」；失败仍「打开目录失败」。
- **最近另存清档**：`clear_alarm_film_csv_dirs`；子菜单「清空最近另存」。
- **冒烟**：`smoke-wave37-dirsmax-hfocus-pinarc-oktip-clearslots-e2e`（另回归 wave36/35）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㊱ · 容量Alt+H · Shift+Alt+P回退 · 预览钉长按落钉 · 开目录失败tip · CSV多档记忆 · 2026-10-28】

- **容量菜单快捷键**：`Alt+H` 弹出容量菜单；菜单项标 `[1]–[4]`；tip 含 Alt+H。
- **Shift+Alt+P 回退切档**：已钉时反向循环 all/error/warning/info；toast「切档 ← {档}」。
- **预览钉长按落钉**：芯片悬停 📍 预览后长按 ~550ms → 真正钉住 + toast「长按落钉」；短按仍筛档。
- **toast 开目录失败 tip**：无路径/目录不存在/系统无法打开 → `_flash_open_dir_fail_tip`。
- **CSV 多档另存记忆**：`host/alarmFilmCsvDirs`（最多 5）；`remember_alarm_film_csv_dir`；右键「最近另存目录」子菜单；`save_all_alarm_film_paths_csv_to_dir`。
- **冒烟**：`smoke-wave36-caphotkey-pback-chiplong-opendfail-csvslots-e2e`（另回归 wave35/34）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉟ · CSV toast开目录 · 容量右键菜单 · 解钉tip驻留 · chip悬停预览钉 · Alt+P切档 · 2026-10-28】

- **CSV toast 单击开目录**：另存成功 toast 绑定 `open_path`；单击/`open_host_toast_path` → `QDesktopServices` 打开目录；tip「单击打开目录」。
- **容量右键菜单**：切窗史右键弹出 3/5/8/12（✓ 当前 · 5 默认）+ 清空；中键仍循环。
- **pin 徽章解钉确认 tip 驻留**：单击解钉后徽章暂显 ✓ + tip「已解钉 · 原 {档}」驻留 ~2.2s。
- **sev chip 悬停预览钉**：悬停芯片虚线金边 + 📍 预览（不真正钉住）；离开 `_sync` 还原。
- **Alt+P 再按切档**：未钉 → 钉住；已钉再按循环 all/error/warning/info 切档 toast；徽章仍解钉。
- **冒烟**：`smoke-wave35-csvtoastopen-capmenu-pintip-chiphover-pgear-e2e`（另回归 wave34/33）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉞ · pin悬停解钉动画 · CSV另存toast · 容量可配 · 预设标默认 · Alt+P toast · 2026-10-28】

- **pin badge 悬停解钉 tip 动画**：悬停 `hostAlarmSevPinBadge` → tip「单击解钉」+ 金边脉冲（`_sev_pin_badge_pulse_timer`）；离开关闭。
- **CSV 另存后 toast**：`save_all_alarm_film_paths_csv` 成功 → `_flash_host_toast`「已另存 CSV · N · 文件名」；失败亦 toast。
- **toast-hist 容量可配**：`host/liaisonToastHistMax`（3/5/8/12）；中键循环；`set_liaison_toast_history_max` / `cycle_liaison_toast_history_max`；tip 显示容量与中键提示。
- **preset 菜单标记默认**：⊘ 右键菜单 650 标「（默认）」+ `isDefault`；当前项仍 ✓。
- **Alt+P toast 反馈**：钉住/取消钉时 `_flash_host_toast`「已钉住 · {key}」/「已取消钉住」。
- **冒烟**：`smoke-wave34-pinhover-csvtoast-histcap-presetdefault-ptoast-e2e`（另回归 wave33）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉝ · pin徽章 · CSV另存记目录 · toast容量tip · 时长预设菜单 · Alt+P钉住 · 2026-10-28】

- **pin badge on sev chip**：钉住时芯片文案加 📌、金边；行尾 `hostAlarmSevPinBadge` 显示 📌档，单击取消钉。
- **CSV 另存 remember dir**：`host/alarmFilmCsvDir`；对话框默认进上次目录，成功另存后更新。
- **toast-hist capacity tip**：历史条 tip 显示 `容量 used/max`（默认 5）+ 回切/清空提示。
- **undo-clear 预设菜单**：⊘ 右键弹出 400/650/1000/1500 菜单（✓ 当前），非仅循环。
- **sev pin hotkey**：`Alt+P` 钉住/取消当前严重度筛。
- **冒烟**：`smoke-wave33-pinbadge-csvdir-histcap-presetmenu-pinhotkey-e2e`（另回归 wave32）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉜ · 气泡长按钉住 · 进度弧可配时长 · CSV另存/cleared · toast史右键清空 · 锁双击可撤销 · 2026-10-28】

- **气泡长按钉住 sev 筛**：左键短按筛；长按钉住（`host/alarmSevPinned`）；钉住后非 force 拒切换；再长按同键或中键取消钉。
- **进度弧可配置时长 tip**：`film/undoClearLongMs`（300–3000）；⊘ tip 显示 ms；右键循环 400/650/1000/1500。
- **CSV 另存文件 / 含已清除列**：`ts,cleared,cleared_at,severity,path,reason`；菜单「另存 paths CSV…」→ `save_all_alarm_film_paths_csv`。
- **toast 史右键清空史**：`clear_liaison_toast_history`；左键仍回切时段。
- **锁徽章双击可撤销**：双击先压入 undo，复位并解锁；↶ 恢复序并可 `_undo_should_relock` 回锁。
- **冒烟**：`smoke-wave32-bubblepin-arcdur-csvsave-histclear-lockundo-e2e`（另回归 wave31）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉛ · 气泡右/中键 · 长按进度弧 · paths CSV · toast史回切 · 锁徽章双击复位 · 2026-10-28】

- **气泡右键仅看该 sev / 中键清筛**：左键筛；右键强制仅看该档；中键 → `all`。
- **长按清空进度弧**：`compareThumbUndoClearArc` 覆盖 ⊘，长按期间描橙弧至满后清空。
- **复制全部 paths CSV**：`ts,severity,path,reason` 头 + 去重行；菜单「复制全部 paths CSV（N）」。
- **toast 史单击回切**：`hostLiaisonToastHistory` 按点击位置回切对应联调时段（secs 并行表）。
- **锁序徽章双击**：复位对比序到基线并解锁（单击仍切换；280ms 单击延迟）。
- **冒烟**：`smoke-wave31-bubblermb-cleararc-pathcsv-histclick-lockdbl-e2e`（另回归 wave30）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉚ · 气泡单击筛 · 清空长按确认 · 复制全部paths · Alt+L toast历史 · 锁徽章单击 · 2026-10-28】

- **芯片气泡单击筛**：`hostAlarmSevCount_*` 手型+单击 → `set_alarm_severity_filter`（与芯片条同源）。
- **撤销清空短按 tip / 长按清空**：`compareThumbUndoClear` 短按 `QToolTip` 确认；长按 ≥650ms → `clear_order_undo`。
- **报警右键复制全部 paths**：`复制全部 paths（N）` → `copy_all_alarm_film_paths`（历史去重、换行剪贴板）。
- **Alt+L toast 历史条**：`hostLiaisonToastHistory` 显示最近 ≤5 次切窗标签（`A → B → C`）；随 toast ~2.2s。
- **锁序徽章单击切换**：`compareThumbLockBadge` 单击 → `set_order_locked` 并持久。
- **冒烟**：`smoke-wave30-bubbleclick-undolongpress-copyall-toasthist-lockbadgeclick-e2e`（另回归 wave29）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉙ · 芯片计数气泡 · 撤销清空钮 · 报警右键复制path · Alt+L全局态提示 · 锁序徽章 · 2026-10-28】

- **严重度芯片计数气泡**：`hostAlarmSevCount_{all|error|warning|info}` 随 `_alarm_severity_counts` 刷新；错红/警黄/讯青。
- **撤销栈清空钮**：`compareThumbUndoClear` ⊘；`clear_order_undo` 清栈并同步深度徽章；空栈禁用。
- **报警右键复制 path**：上下文菜单「复制 path」→ `copy_alarm_film_path` 写剪贴板（无 path 禁用）。
- **Alt+L 全局态提示**：`_on_liaison_hotkey` → `cycle_liaison_window(from_hotkey=True)` + host 顶栏 overlay `hostLiaisonHotkeyToast`（~2.2s）+ statusTip。
- **锁序徽章**：`compareThumbLockBadge` 已锁/未锁；锁态橙底；随 `set_order_locked` 同步。
- **冒烟**：`smoke-wave29-chipcounts-undoclear-copypath-altltoast-lockbadge-e2e`（另回归 wave28）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉘ · 撤销深度徽章 · 严重度芯片条 · 报警右键定位 · 锁序复位提示 · Alt+L切窗 · 2026-10-28】

- **撤销栈深度徽章**：`compareThumbUndoDepth` 显示栈深；有条目时青边高亮。
- **严重度筛芯片条**：全部/错/警/讯 `hostAlarmSevChip_*` 与 combo/spark/持久同步高亮。
- **报警列表右键定位胶片**：上下文菜单「定位胶片」→ `alarmFilmLocateRequested`（无 path 时禁用）。
- **锁序时复位仍可用提示**：锁态下 ↺ tip「锁序下仍可用」+ 青边；复位不解锁、不禁拖以外的复位。
- **联调切窗快捷键**：`Alt+L` → `cycle_liaison_window`；combo/徽章 tip 标注。
- **冒烟**：`smoke-wave28-undodepth-sevchips-alarmctx-lockresettip-altl-e2e`（另回归 wave27）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉗ · 对比锁序持久 · 运行报警filmPath · 严重度筛持久 · 徽章切窗 · 复位撤销栈 · 2026-10-28】

- **对比锁序 QSettings 持久**：`film/compareOrderLocked`；`load_order_lock_pref` / `save_order_lock_pref`；MW 启动加载；锁钮切换即时写回。
- **运行报警自动带 filmPath**：Host SM `note_film_path`；`set_state(Alarm)` → `_record_alarm(..., film_path=)`；MW 报警同步前从胶片 `current_path` 注入。
- **严重度筛持久**：`host/alarmSevFilter`；打开恢复；combo / spark / `set_alarm_severity_filter` 写回。
- **联调徽章单击切窗**：`cycle_liaison_window` 循环 全部→5分→15分→1时→24时；徽章手型+tip。
- **胶片复位撤销栈**：重排/复位先压栈；↶ `undo_order`（深≤16）；新基线清空栈。
- **冒烟**：`smoke-wave27-lockpersist-alarmfilm-sevpersist-badgecycle-undostack-e2e`（另回归 wave26）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉖ · 侧栏锁定/复位 · 联调时段徽章 · 高亮双击胶片 · UPH常用还原 · spark筛严重度 · 2026-10-28】

- **侧栏对比序锁定/复位**：`CompareThumbStrip` 🔓/🔒 禁止拖拽；↺ 复位到进入对比时的 `_baseline_paths`；`lockChanged` / `reset_order`。
- **联调时段徽章**：`hostLiaisonWindowBadge` 随 combo 同步「⏱ 近15分」等；全部时灰态。
- **高亮首条双击定位胶片**：跳失败码可带 `film_path`；列表项 UserRole 存 entry/`filmPath`；双击 → `alarmFilmLocateRequested` → HMI `filmLocateRequested`；`note_film_path` 记最近胶片。
- **UPH 常用一键还原**：`prodUphRestoreRecent`「常用」→ `prod/uphPresetLast`（否则 recent[0]）。
- **spark 单击筛严重度**：循环 all→error→warning→info；`hostAlarmSevFilter` 同步；列表按 severity 过滤。
- **冒烟**：`smoke-wave26-lockreset-liaisonbadge-alarmfilm-uphrestore-sparksev-e2e`（另回归 wave25）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉕ · 侧栏拖拽重排 · 联调时段持久 · 跳后高亮首条 · UPH快捷记忆 · Alarm spark染色 · 2026-10-28】

- **侧栏缩略拖拽重排对比序**：`CompareThumbStrip` InternalMove；`pathsReordered` → MW 更新 `_filmstrip_compare_paths` 并刷新叠层色序。
- **联调时段持久**：`QSettings host/liaisonWindowSec`；打开恢复；切换即时写回。
- **失败码跳后列表高亮首条**：`jump_to_alarm_for_code` → `_highlight_alarm_list_first`（选中/滚入/1.8s 红选闪）。
- **UPH 预设 QSettings 快捷记忆**：`prod/uphPresetRecent` + `prod/uphPresetLast`；常用钮青边 tip「常用」。
- **严重度 → Alarm spark 染色**：富文本 ▇/▁ 按 error 红 / warning 琥珀 / info 蓝 / 已清除灰。
- **冒烟**：`smoke-wave25-reorder-liaisonpersist-failhighlight-uphrecent-sparkssev-e2e`（另回归 wave24）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉔ · 多选对比侧栏 · 联调CSV时段 · 失败码跳Alarm · UPH预设 · 联闪严重度 · 2026-10-28】

- **胶片多选对比侧栏缩略条**：`CompareThumbStrip` 贴图像右侧；多选≥2 帧时竖向展示 ≤6 缩略；点击聚焦胶片+保持对比；× / ESC 清除。
- **联调 CSV 时段过滤**：`hostLiaisonWindow`（全部/近5分/近15分/近1时/近24时）；`filtered_liaison_events` / `liaison_events_csv(window_sec)`；导出含 severity 列；事件带 `epoch/ts_full`。
- **换型失败码 → Alarm 一键跳**：HMI `hmiFailCodeBadge` 单击 → `jump_fail_code_to_alarm` → Host SM `jump_to_alarm_for_code`（切「报警历史」+ 关键字 + 联调筛）；右键清除。
- **UPH 窗口预设快捷**：`prodUphPreset{8,16,24,32,48}` 一键设窗口；当前值高亮。
- **Host SM 联闪颜色按严重度**：`_liaison_severity` → error 红 / warn 琥珀 / ok 绿 / info 蓝；固定栏短闪跟色。
- **冒烟**：`smoke-wave24-comparestrip-liaisonwin-failjump-uphpreset-sevflash-e2e`（另回归 wave23）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉓ · 多选对比 · UPH窗口持久 · 联调CSV · 失败码徽章 · Comm簇计数 · 联调固定栏闪 · 2026-10-28】

- **结果表↔胶片多选对比**：结果表 `ExtendedSelection`；「多选对比」/ 多行双击 → `filmCompareRequested({paths, multi})`；`_show_filmstrip_compare_overlays(highlight_paths=)` 优先多选帧（≤6）；同组再点 / ESC 清除。
- **UPH 窗口持久**：`QSettings prod/uphWindow`；`ProductionStatsPanel` 启动加载、`set_uph_window` 写回。
- **联调条导出 CSV**：`liaison_events_csv` / 复制联调CSV / 导出联调…。
- **换型失败码 HMI 徽章**：`hmiFailCodeBadge`（⚠ CODE）；`_report_variant_fail` 置位；换型成功 / 点击 / 8s 清除。
- **Comm 折叠按簇计数徽章**：折叠勾选文案「簇 N」/「已藏 N」。
- **Host SM 联调 → 固定栏短闪**：`liaisonPushed` → HMI `_on_liaison_pushed` 蓝闪 1.4s。
- **冒烟**：`smoke-wave23-multi-uphpersist-liaisoncsv-failbadge-foldbadge-flash-e2e`（另回归 wave22）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉒ · ESC/再点清除对比 · UPH窗口 · Comm折叠持久 · 换型失败码 · Alarm联调条 · 2026-10-28】

- **结果表↔对比叠层 ESC / 再点清除**：`keyPressEvent` Esc 优先清 `_filmstrip_compare_active`；再双击同帧路径 toggle `_clear_filmstrip_compare_overlays`；状态栏提示「ESC/再点清除」。
- **UPH 趋势窗口可调**：`ProductionStatsPanel._uph_window` + `prodUphWindowSpin`（8–48，步进 8）；`trend_uph_text` 按窗口切片 spark/均/峰（`n=k/win`）。
- **Comm 折叠态持久**：`QSettings('SIEANS','VisionDesktop')` 键 `vars/foldCommAccept`；Variables 打开恢复勾选，切换即时写回。
- **配方换型失败码细分**：`VARIANT_EMPTY` / `VARIANT_NO_RECIPES` / `RECIPE_MISSING` / `APPLY_ERROR` / `ENTER_RUN_FAIL` / `TRIAL_FIRE_FAIL`；`_report_variant_fail` → 日志+状态栏+联调条；`recipe_library.FAIL_CODES`。
- **Host SM Alarm 历史联调条**：`hostLiaisonStrip` + `push_liaison_event`；试跑清除/`TRIAL_CLEAR`、换型失败码、报警清除写入；筛选「联调」+ 列表 `·联调` 标记。
- **冒烟**：`smoke-wave22-esc-uphwin-foldpersist-failcode-liaison-e2e`（另回归 wave21 / film-locate）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆㉑ · 结果表双击对比叠层 · 试跑失败Alarm联调 · Comm折叠 · UPH趋势 · 补stamp · 2026-10-28】

- **结果表双击 → 该帧对比叠层**：`cellDoubleClicked` → `filmCompareRequested`（先 `filmLocateRequested`）；`MainWindow._on_hmi_film_compare` 定位胶片后调 `_show_filmstrip_compare_overlays(highlight_path=)`；行 tip「单击定位 · 双击对比叠层」。
- **变体/测量链试跑失败 → Alarm → 清除恢复联调**：`backfill_after_trial` 在 failed/NG 时置 `_trial_fail_alarm` 并 `_paint_machine_chrome(Alarm)`；清除边沿 `_pulse_alarm_cleared` 文案「✓ 试跑失败已清除 · 联调已恢复」。
- **Comm 簇折叠分组**：Variables「折叠 commAccept*」勾选；隐藏 `commAccept_<项>` 明细，保留 Pass/Fail/Skip/Overall/At/Host/Port；插入「▼ commAccept* 簇（已折叠 N 项明细）」分组行。
- **产线 UPH 趋势看板**：`ProductionStatsPanel._uph_hist` + `trend_uph_text` + `prodUphTrend` spark；线图控件同步 `hmiTrendUphSpark`；`_refresh_trend_charts` 推送。
- **胶片缺 path 人工补 stamp**：结果表「补 stamp」→ `filmStampRequest` → MW 取当前胶片 → `apply_manual_film_stamp(seq,path,index)`。
- **冒烟**：`smoke-wave21-dblclick-commfold-uph-stamp-e2e`（另回归 film-locate / wave20-vars-alarm-variant）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑳ · 结果表↔胶片定位 · commAccept簇滚动 · 试跑回填 · Alarm恢复 · 变体试跑 · 2026-10-28】

- **结果表行点击 ↔ 胶片定位加深**：历史行 stamp `filmPath/filmIndex`（`set_film_stamp` ← finished）；`UserRole` 元数据；`cellClicked` → `filmLocateRequested`；`FilmstripBar.select_path/select_index` 滚入视口；胶片选中反查 `highlight_rows_for_film`。
- **Variables 高亮后自动滚到 commAccept* 簇**：`highlight_written_keys` 优先 `scrollToItem(PositionAtCenter)` 首条 `commAccept*`，簇行青蓝高亮并 `setRangeSelected`；message 提示「已滚到 commAccept* 簇」。
- **测量链/换型试跑后 HMI 判定/配方徽章实跑回填**：`set_trial_backfill_pending` → `finished` 调 `backfill_after_trial`（徽章 tip「试跑回填 · OK/NG · ms」、短暂 OK/NG 边框、strip 标签闪「试跑OK」、固定栏 okng）。
- **Alarm 清除 → 固定栏恢复动画/短提示**：`_paint_machine_chrome` 边沿检测 Alarm→非 Alarm → `_pulse_alarm_cleared`（固定栏绿闪「✓ 报警已清除」+ 日志，1.6s 后 settle）。
- **产线变体快切可选 trialOnce**：工具栏 `recipeVariantTrialChk`「试跑」；`apply_variant_quick(..., trial_once=)` 勾选则 `enterRun+trialOnce`。
- **冒烟**：`smoke-hmi-result-film-locate-e2e` / `smoke-wave20-vars-alarm-variant-trial-e2e`（另回归 vars-highlight / chrome-recipe）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑲ · 结果表配方联动 · Comm→变量高亮 · 换型试跑 · Alarm栏 · 2026-10-28】

- **结果表 / 胶片 ↔ 配方徽章联动加深**：结果表第 10 列「配方」；历史行 stamp `_live_recipe/_live_variant`；CSV 含 recipe/variant；点击配方徽章或「配方筛选」按当前配方过滤；strip 配方标签显示「筛选中」。
- **Comm dump → Variables 即时高亮**：`VariablesDialog.highlight_written_keys`；`live_patch_flow_var` 同步闪行；验收「一键写入变量」经 `MainWindow.highlight_variables_keys` 打开/聚焦三级变量并高亮 keys。
- **打开即跑测量链 · 一键「换型→试跑」**：工具菜单「一键「换型→试跑」·测量链」→ `open_measure_chain_trial`（caliper-measure / measure 模板 + enterRun+trialOnce）；配方对话框工程库「测量链 · 换型→试跑」按钮；工程库换型尊重对话框 enterRun/trialOnce。
- **Host SM Alarm ↔ 固定栏色联动 polish（代码级，非人工签字）**：`_paint_machine_chrome(Alarm)` 重刷固定栏；Alarm 主导色 + tip「⚠ 报警」；离开 Alarm 清 `_live_host_alarm`。
- **冒烟**：`smoke-hmi-recipe-result-filter-e2e` / `smoke-vars-highlight-commdump-e2e` / `smoke-measure-chain-trial-alarmbar-e2e`。

## 【细妆⑱ · 运行态chrome收束 · 配方换型闭环 · Comm验收落盘 · 2026-10-28】

- **运行模式 chrome 观感收束（代码级，非人工签字）**：`StatusLamp` NG 边沿闪烁；HMI 头栏/底条 `配方徽章`；固定栏结构化 chip（📷相机│📡通讯│门│配方│●状态│◆判定│＃计数）并按 OK/NG/Alarm 变色；默认运行条分组分隔 + 配方标签；`set_recipe_chrome` / `update_fixed_bar_live` 驱动灯与栏。
- **配方/换型 → 产线闭环**：换型对话框「套用后切运行态 / 套用后单次试跑」；`_stamp_post_apply` → `MainWindow.sync_after_recipe_apply`（刷生产任务字段、HMI 徽章、可选 `set_app_mode('run')` + 单次试跑）；工具栏变体快切 / 生产任务「套用变体」同样刷徽章。
- **Comm 验收→变量一键落盘**：`dump_acceptance_to_variables` + 对话框「一键写入变量」；写 `flow.commAcceptPass/Fail/Skip/At/Host/Port/Overall`、按项 `flow.commAccept_<id>`，并解析 VALUE/MEAS sibling。
- **打开即跑 measure 链**：`open-and-run-caliper-measure` 种子配方「卡尺测宽·默认 / A型」、固定栏计数+判定门；`measure_geom` 绑定 tip 点明换型→运行试跑。
- **Smokes**：`smoke-hmi-chrome-recipe-fixedbar-e2e` / `smoke-recipe-apply-run-loop-e2e` / `smoke-comm-accept-vars-dump-e2e`（全部 PASS）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑰ · 生产链路/报警加深 · Comm写回 · 绑定制导 · 2026-10-28】

- **生产链路 / 报警历史 UX**：Host SM 报警页生产条（OK/NG/良率/状态）、报警序列 spark（▇未清/▁已清）、状态筛选（全部/未清除/已清除）、severity（错/警/讯）+ 清除历时；CSV 增 `cleared_at/severity`。`ProductionStatsPanel` 上位机状态镜像、判定序列、节拍/UPH、导出CSV；HMI chrome ↔ Host SM `set_production_snapshot` 双向跟。
- **Comm 变量写回 deepen**：`parse_protocol_writeback_extras` 升模块级；VALUE 多键、MEAS 扩展字段（angle/dist/pass…）+ leftover `meas_*`；live `comm_listener` 与「模拟写回」均写 sibling 字段到同 scope。
- **measure_geom 绑定制导**：基本参数「绑定制导…」逐步走完槽位（画布点选 / 插入字段 / 跳过 / 下一步）；覆盖 line_intersect / point_distance / point_line_distance。
- **Smokes**：`smoke-prodchain-alarm-deepen-e2e` / `smoke-comm-writeback-extras-live-e2e` / `smoke-measure-geom-bind-wizard-e2e`（全部 PASS）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑯ · 胶片悬停对比 · 配方差分预览 · Comm复测spark/FAIL · 门限筛选 · 2026-10-28】

- **measure_geom 胶片悬停 / 多帧对比叠层**：`FilmstripBar.thumbHovered`（viewport hover）；`MainWindow._show_filmstrip_compare_overlays` 用 `_filmstrip_results` + `overlay_specs_for_multiframe` 色环叠层（当前帧高亮）；离开恢复 `_apply_measure_geom_overlays`。画布点选中不抢叠层。
- **配方变体差分预览**：`recipe_library.diff_recipe` / `format_diff_chip`（模块Δ/变量Δ/缺/同）；换型对话框 `recipeDiffChip` 选中即预览；一键换型/部分套用确认框带差分；工具栏变体快切写 statusBar/日志差分。
- **Comm 定时历史 spark + FAIL toast**：`_schedule_hist` unicode 复测序列；FAIL 次刷红差分横幅 + summary + parent statusBar 8s 告警。
- **HMI 门限 spark 点击筛选**：点击循环 全部→仅通→仅拒，过滤结果表（`gatePass` / 判定列）；spark 文案带「筛选:」。
- **九点 / 变量计算 live bind**：结果显示「刷新实况」跟 `host_last_result` 读 rms/usedPoints / values·errors。
- **Smokes**：`smoke-geom-filmstrip-hover-compare-e2e` / `smoke-recipe-diff-preview-e2e` / `smoke-comm-schedule-hist-toast-e2e` / `smoke-hmi-gate-filter-e2e`（全部 PASS）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑮ · 多源嵌套点选 · 变体快切 · Comm定时差分 · 门限序列spark · 2026-10-28】

- **measure_geom 多源/嵌套绑定**：`geom_canvas_pick` 展开 `group/subflow` 的 `result.trace` 为子级候选；`merge_last_results` 合并胶片多帧缓存；`MainWindow._filmstrip_results`（≤32）在 finished 按路径落盘，画布点选合并当前结果+胶片缓存+组合内层。
- **配方变体快切 chip**：工具栏 `recipeVariantChip`（选变体→套用该变体首条配方）；生产任务面板「产品变体」下拉 +「套用变体」；与 `activeRecipeVariant` / 配方对话框联动刷新。
- **Comm 验收定时复测 / 上次↔本次差分**：间隔分钟 QTimer 自动重跑；`diff_reports` 项级 PASS/FAIL 变更；差分横幅 + 「对比上次↔当前」按钮；跑完自动对比磁盘上次再落盘。
- **HMI 门限列序列 spark**：`_gate_hist` 记 recent passGate 真值；结果表上方 unicode 门限序列（高=通）；`gate_spark_text` / `_refresh_gate_spark`。
- **Smokes**：`smoke-geom-multisource-nested-e2e` / `smoke-recipe-variant-chip-e2e` / `smoke-comm-schedule-diff-e2e` / `smoke-hmi-gate-spark-e2e`（全部 PASS）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑭ · 画布点选绑定 · 配方变体子集 · Comm报告落盘 · 门限列 live passGate · 2026-10-28】

- **Canvas 点选加深（measure_geom 绑定）**：`desktop/geom_canvas_pick.py` 从 last_result 收集 lines/matches/circles/交点/垂足；`ImageView` 点选模式（左键命中 / 右键·Esc 取消）+ 预览叠层；几何量测面板每条绑定旁「画布点选」→ `MainWindow.begin_geom_canvas_pick` 写回来源 stepId + 字段路径。
- **配方产品变体 / 变量子集 / 部分套用**：`recipe_library.capture_recipe(variant/var_keys/step_ops)`；`apply_recipe(..., var_keys/step_ops/steps_only/vars_only)`；`list_variants` / `recipes_for_variant`；换型对话框产品变体筛选 + 部分套用白名单（算子/变量）+ 只模块/只变量开关。
- **Comm 验收报告落盘**：`data/.../comm-acceptance/last-report.json`（+ 时间戳副本）；对话框横幅显示上次 PASS/FAIL；「载入上次报告」回填表格；打开即 bootstrap。
- **HMI 结果表门限列**：跟 live `passGate=<值>`（或判定门 gateKey 实值）；`_last_gate_detail` + `update_gate_column_live` 刷新最新行。
- **Smokes**：`smoke-geom-canvas-pick-e2e` / `smoke-recipe-variants-partial-e2e` / `smoke-comm-acceptance-persist-e2e` / `smoke-hmi-passgate-column-e2e`（全部 PASS）。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑬ · 产线配方换型 · 多卡尺ROI编辑 · 结果表CSV · Comm验收壳 · 2026-10-28】

- **产线配方 / 一键换型**：`desktop/recipe_library.py` + `recipe_switch_dialog.py`；本方案 `project.recipes[]` 参数快照保存/套用（按算子+名称匹配）；工程库/模板/打开即跑整案换型；菜单「工具→产线配方/换型…」+ 工具栏「配方」；生产任务面板 tip。
- **ROI 多卡尺编辑器**：`desktop/caliper_roi_editor.py` — 画布拖拽 ROI 四角 + 卡尺探针即时预览（数量/宽/投影长/角/搜索方向）；几何面板「多卡尺 ROI 编辑器…」写入 `roi` + `caliper*`（roiPreset=draw）。非 Halcon。
- **HMI 结果表加深**：9 列历史（时间/序号/模块/耗时/判定/OK/NG/门限/备注）+ 复制CSV / 导出CSV / 清空；跟末次步骤名与生产统计。
- **真机 Comm 验收壳**：`desktop/comm_acceptance_dialog.py` — PING/STATUS/HELP/GET/SET/VARS/MEAS/JSON 清单干跑（默认环回 :19880，Host/Port 可改）；导出报告 CSV；无现场硬件宣称 / 无 robot SDK。
- **Smokes**：`smoke-recipe-switch-e2e` / `smoke-caliper-roi-editor-e2e` / `smoke-hmi-result-table-csv-e2e` / `smoke-comm-acceptance-e2e`。

### 仍外置
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑫ · 卡尺→几何测量链 · Comm 协议深化 · 结果表末步名 · 2026-10-28】

- **打开即跑 · 卡尺→几何测量**：`projects/open-and-run-caliper-measure.sieans`（预处理→caliper→line_intersect→point_line_distance→门限）；菜单/打开示例/README 已登记。
- **Runtime bind 硬化**：`_pickPoint` 认 `intersectX/Y`·`footX/Y`；`_injectResultScalars` 注入 distance / intersectX·Y / dx·dy → var_calc。
- **Comm 协议深化（仍为环回模拟，非现场）**：`tcp_device_sim` 增 GET/SET/VARS/MEAS/JSON；通信管理 TCP「协议预设」+ 结构化试收写回（VALUE/MEAS→measX…）。
- **HMI 结果表**：「模块」列跟末次步骤名（不再硬编码「流程」）；finished 向 HMI 注入命名 records。
- **插件专用属性页**：跳过（ParameterPanel 已覆盖 plugin arguments；无薄缺口）。
- **冒烟**：`smoke-caliper-measure-runtime-e2e.cjs`；`smoke-comm-protocol-deepen-e2e.py`；`smoke-hmi-result-table-laststep-e2e.py`。

### 仍外置

- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑪ · 卡尺 Runtime e2e · measure_geom 绑定 · HMI 趋势计时 · 2026-10-28】

> Allen t196 连续自驱 — 无真机 / 无 robot SDK / 无 push；把 ⑩ 后仍薄的 Runtime 路径、几何测量绑定、HMI 图表计时收实。

### 已落地
- **Live Runtime e2e · 卡尺**：`scripts/smoke-caliper-runtime-e2e.cjs`（对齐 locate/measure e2e 模式）跑通 `open-and-run-caliper.sieans`：passGate/lineCount/lineScore/lineRms + geometry.lines；并顺带验 measure_geom bind（line_intersect / point_line_distance）。
- **measure_geom 绑定抛光**：`flow-control` `_pickLine/_pickPoint` 解包 `lines[]/matches[]`；bind 缺字段默认 `lines[0]`/`matches[0]`；line2 与 line1 同级 fallback；面板「插入上游字段」只写字段路径并同步来源；切换来源按算子建议字段；geometry 字段索引补 `lines[0]/rmsPixels/…`；改 show* 后按 `last_result` 即时重绘矢量叠层。
- **HMI 图表计时加深**：`ProductionStatsPanel` 记 elapsed/OK 历史；多数据线图 unicode spark + OK 序列；饼图良率条与结果表耗时/OK/NG 跟统计面板实时刷新。
- **冒烟**：caliper-runtime-e2e 12 PASS；multi-sample 8 PASS；locate-measure 9 PASS。

### 仍为外依赖
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑩ · 多卡尺多边缘 · 打开即跑卡尺 · 诊断字段 · 2026-10-28】

> Allen t196/t191 连续自驱 — 无真机；把 ⑨ 仍薄的多边缘/样例/诊断/触发文案收实。

### 已落地
- **多直线分带拟合**：`caliper_line` 在 `edgeType=all` + `maxCount>1` 时按扫描轴分带；不足时残差剥离补线；叠层分色 + `residualsSummary`（score/rms/inliers/angle/length）。
- **结果诊断 UI**：几何面板「结果显示」诊断字段说明；`flow-control` 注入 `geometry_rms`（rmsPixels）/ `_angle` / `_length` / `_inliers`。
- **打开即跑 · 卡尺**：`projects/open-and-run-caliper.sieans`（预处理→多卡尺直线→门限）；菜单/打开示例/README 已登记（含 measure/tcp-sim）。
- **HMI/触发细妆**：嵌套壳 tip；全局触发文案接 TCP 环回 :19880。
- **冒烟**：`scripts/smoke-caliper-multi-sample-e2e.py` → 8 PASS。

### 仍为外依赖
- 真机 TCP / 现场设备；真实远端云；Halcon 卡尺核；robot SDK；chrome 人工观感签字

## 【细妆⑨ · 卡尺核深化 · 本地模板云 · TCP环回 · 2026-10-28】


> Allen t196「那么继续开发吧」— 无真机/无 robot SDK；把原「外依赖」中可本机落地的三项推进为可跑代码。

### 已落地（本机可验）
- **几何直线查找 · 多卡尺边缘拟合**：`vision/caliper_line.py` + `engine.geometry(feature=lines, findMethod=caliper|hough|auto)`；接入卡尺数量/宽/投影长/σ/投影角/极性/边缘类型/残差/最低分/ROI 预设；叠层画卡尺框·边缘点·拟合线·RMS；默认 caliper，可切 Hough。
- **模板市场本地云同步站**：`desktop/template_market_local.py` HTTP `127.0.0.1:19779`（list/get/publish/sync）；设计器「模板市场」含启动本地站 / 云同步 / 发布当前；seed=`projects/run-ui-templates`，store=`data/.../template-market`。
- **TCP/UDP 环回协议模拟器**：`desktop/tcp_device_sim.py`（:19880/:19881）；PING→PONG、RUN/STOP→ACK；通信管理「TCP 测试」灯+启动/停止/填入地址；样例 `projects/open-and-run-tcp-sim.sieans`。
- **冒烟**：`scripts/smoke-caliper-market-tcpsim-e2e.py` → 9 PASS。

### 仍为外依赖（明确不宣称完成）
- **真机 TCP / 现场设备** 联调（环回模拟器≠现场设备）
- **真实远端云 / 模板市场后端**（本地站为替身）
- **Halcon 卡尺核**（现为 OpenCV 强度剖面+稳健拟合；文档已声明）
- **robot / 机械手 SDK**（按 Allen 指示跳过）
- chrome **人工观感签字**

### 进度续⑧ · 2026-10-27 深夜

- chrome：`desktop/toolbar_icons.py` 单色图标；`brandStrip` 分区；ToolTip 全中文
- HMI：组合框真·栈页（外观灯/尺寸表/拖放约束）；Tab 嵌套源下拉
- samples：`行业-印刷字符读码.ruitpl.json`
- 总览：明确「代码细妆已收口」vs「外依赖未做」

### 进度续⑦ · 2026-10-27 深夜
- HMI：连接状态 ●灯；设置变量/参数设置 tip+Enter 派发；组合框/Tab/子界面嵌套 StatusLamp·良率条·连接灯
- Comm：`_commit_test_writeback` → `fire_string_trigger` 活路 smoke（RUN/CONT）
- panels：叠层实绘 tip；geometry 卡尺高斯σ / 投影角
- smoke：`scripts/smoke-ux-polish-hmi-comm-e2e-live.py` 6 PASS；overlay 11 PASS
- 全流程：FlowParamDialog I/O 表可编辑回写 flow.io；显示全局图像开关可写；卡片间 → 顺序示意
- run_ui：操作员态触发接线说明已去「后续批次」措辞

### 进度续⑥ · 2026-10-27 深夜
- measure_geom：`annotate_geom` 引擎实绘 + runtime 调用 + ImageView/mainwindow 画布矢量叠层
- geometry_find / locate：`show*` 开关门控 `vision/engine.py` / `template_matching.py` 真实绘制
- labels：operator_hmi 开/关·趋势；locate（编辑器创建）；wave3 占位；SDK 取图分组
- HMI：组合框 QComboBox 栈、Tab 三页签、子界面嵌套壳
- smoke：`scripts/smoke-ux-polish-overlay-draw-comm-hmi-e2e.py` 11 PASS

### 进度续⑤ · 2026-10-27 深夜
- Comm 事件表「挑选变量…」写入当前行变量列
- op_rail 纵栏 tip 对齐 VM 纯图标分区

### 进度续④ · 2026-10-27 深夜
- measure_geom 结果显示：点/线/标签/距离文字独立开关
- geometry_find：拟合曲线/标签/卡尺标尺叠层
- locate：搜索区/特征点/全画布描摹开关；模板子窗文案更新
- Comm↔全局触发双向按钮；通信→变量联调指引
- HMI 模板市场 + 三行业 .ruitpl.json；float 底栏 QSS objectName
- filmstrip 缩略尺寸；settings 连续跑路径说明；nest/chrome tip
- csharp 插入上游→输入绑定；elapsed 合计/分步/趋势开关

