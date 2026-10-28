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




## 【细妆96 · copy_orig_len Status 级联 · toggle 表面 status · 2026-10-28】

- **copy_*_orig_len**：out / stash 级联 tip 的 `status` / `status_prop` / `status_prop_ok` / `tip_prop_ok`（原长复制与 tip 状态同源）。
- **toggle**：刷新徽章后顶层表面 `status` / `status_prop_ok` / `strategy_prop_ok` / `tip_prop_ok`（badge 子 dict 仍保留）。
- **FlashMs**：仍未起步 `StrategyBadgeFlashMs`（策略徽章无 `flash_*` 消费者；开 getter/setter 链价值低，留后续若加闪标视觉）。
- **验证**：`scripts/smoke-wave128-copyoriglenstatus-togglecascade-e2e.py` → 9 PASS；regress tip/copy/truncate/set/refresh。非硬件约 **~99.98%**。

## 【细妆95 · 策略 tip/truncate Status 镜像 · copy 级联 status_prop_ok · 2026-10-28】

- **tip**：写回 `dstImportStrategyBadgeStatus`（`策略·合并/覆盖`），stash `hover_status` / `hover_status_prop` / `hover_status_prop_ok`（对齐 tip_prop 往返）。
- **truncate**：last dict 含 `status` / `status_prop` / `status_prop_ok`，并写回徽章 Status。
- **级联**：`copy_*_hover_tip` out 带入 tip 的 `status_prop_ok` / `tip_prop_ok`。未加 `StrategyBadgeFlashMs`（无既有 FlashMs 调用链，留后续）。
- **验证**：`scripts/smoke-wave127-…-e2e.py`；regress wave126/125。非硬件约 **~99.98%**。

## 【细妆94 · 策略 refresh/set/ensure status_prop_ok · tip_max_len Status 级联 · 2026-10-28】

- **DST 策略徽章 refresh**：写回 `dstImportStrategyBadgeStatus`（`策略·合并/覆盖`），out 含 `status` / `status_prop` / `status_prop_ok`。
- **set 策略**：仍返回 `str`（兼容 smoke101）；额外 stash `_last_…_strategy_set` 含 `status_prop_ok` / `strategy_prop_ok` / `tip_prop_ok`。
- **ensure**：新建徽章时初始化 `dstImportStrategyBadgeStatus=策略·合并`。
- **级联**：`set_strategy_badge_hover_tip_max_len` 同步 Status，out 含 `status_prop_ok`。未加策略 flash_ms（无既有 FlashMs 缺口，留后续）。
- **验证**：`scripts/smoke-wave126-…-e2e.py`；regress wave125/120。非硬件约 **~99.98%**。

## 【细妆93 · 策略菜单 status_prop_ok · 短史夹紧 tip/status · 菜单 flash+tip+status 三联回归 · 2026-10-28】

- **DST 策略徽章右键菜单**：同步 `dstImportStrategyBadgeStatus`（`策略·合并/覆盖`），out/`_menu_sync` 含 `status` / `status_prop` / `status_prop_ok`（对齐 tip 往返）。
- **撤销短史夹紧预览**：新增 `clamp_*_pos` + `preview_clamp_*`，写回 Status=`夹紧预览` / HoverTip，含 `tip_prop_ok` / `status_prop_ok`；右键增加「夹紧预览」action。
- **三联回归**：再预览 / 短史 / 档差 / 步进菜单 `flash_ms_prop_ok` + `tip_prop_ok` + `status_prop_ok`；策略 tip+status+strategy。
- **验证**：`scripts/smoke-wave125-…-e2e.py`；regress wave124/123。非硬件约 **~99.98%**。

## 【细妆92 · 夹紧预览 tip_prop_ok · 右键菜单 status_prop_ok 镜像 · 2026-10-28】

- **夹紧预览**：再预览 / 档差 / 步进 clamp out 同步 `*HoverTip`，含 `tip` / `tip_prop` / `tip_prop_ok`（保留既有 `status_prop_ok`）。
- **右键菜单**：再预览 / 短史 / 档差 / 步进 quiet/shown out 镜像 `*BadgeStatus`（`闪标档：Nms`），含 `status` / `status_prop` / `status_prop_ok`。
- **验证**：`scripts/smoke-wave124-…-e2e.py`；regress wave123。非硬件约 **~99.98%**。

## 【细妆91 · 策略菜单 tip_prop 同步 · 档差菜单 tip_prop_ok · 再预览/短史/步进菜单 tip_prop 镜像 · 2026-10-28】

- **DST 策略徽章右键菜单**：同步 `dstImportStrategyBadgeHoverTip`，out/`_menu_sync` 含 `tip` / `tip_prop` / `tip_prop_ok`。
- **档差菜单**：quiet/shown out 增加 `tip_prop` / `tip_prop_ok`（写回 `jumpDeltaBadgeHoverTip`，对齐 flash_ms 往返）。
- **再预览 / 撤销短史 / 滚轮步进菜单**：镜像 set_flash tip，out 含 `tip` / `tip_prop` / `tip_prop_ok` + 既有 `flash_ms_prop_ok`。
- **验证**：`scripts/smoke-wave123-…-e2e.py`；regress wave122。非硬件约 **~99.98%**。

## 【细妆90 · 再预览/短史/步进 set_flash_ms tip_prop · 右键菜单 flash_ms_prop_ok · 2026-10-28】

- **再预览 / 撤销短史 / 滚轮步进**：`set_*_badge_flash_ms` 同步 `*HoverTip`，out 含 `tip_prop` / `tip_prop_ok`（对齐档差 `jumpDeltaBadgeHoverTip`）。
- **右键菜单**：再预览 / 短史 / 步进 quiet/shown out 增加 `flash_ms_prop` / `flash_ms_prop_ok`（写回 FlashMs 往返，对齐档差菜单）。
- **验证**：`scripts/smoke-wave122-…-e2e.py`；regress wave121。非硬件约 **~99.98%**。

## 【细妆89 · 策略 tip/set/refresh tip 文本属性 · 再预览/短史/步进 tip_prop 镜像 · 档差菜单 flash 同步 · 夹紧预览 status_prop_ok · 2026-10-28】

- **策略**：`tip` / `set_strategy_badge_hover_tip_max_len` / `refresh` 同步 `dstImportStrategyBadgeHoverTip`，out 含 `tip_prop` / `tip_prop_ok`。
- **再预览 / 撤销短史 / 滚轮步进**：tip 与 refresh 镜像 `*HoverTip` 属性（同档差 `jumpDeltaBadgeHoverTip`），`tip_prop_ok` 入 `_last_*` 与 refresh out。
- **档差菜单**：quiet/shown out 增加 `flash_ms_prop` / `flash_ms_prop_ok`（写回 `jumpDeltaBadgeFlashMs` 往返）。
- **夹紧预览**：再预览 / 档差 / 步进 clamp out 增加 `status` / `status_prop` / `status_prop_ok`（写「夹紧预览」读回）。
- **验证**：`scripts/smoke-wave121-…-e2e.py` 7/7；regress wave120 6/6。非硬件约 **~99.98%**。

## 【细妆88 · 策略 refresh out 属性同步 · 再预览/短史/步进 tip flash_ms_prop_ok · 档差 refresh tip_prop_ok · FlashMs refresh 往返 · 2026-10-28】

- **DST 策略徽章**：refresh out 同步 `strategy_prop_ok` / `tip_max_len_prop_ok` / `last_toast_brief_prop_ok`。
- **A/B 回滚**：再预览 tip 读回 `flash_ms_prop_ok`；refresh out 带 FlashMs 往返。
- **忽略名单**：短史 tip `flash_ms_prop_ok`；refresh FlashMs 往返。
- **jitter 旁标音量**：步进 tip `flash_ms_prop_ok`；refresh FlashMs 往返。
- **栈预览跳档**：refresh out 带 `tip_prop_ok` / `flash_ms_prop_ok`。
- **验证**：`scripts/smoke-wave120-…-e2e.py` 6/6；regress wave119 7/7。非硬件约 **~99.98%**。

## 【细妆87 · 策略菜单同步 out 属性 · 再预览/短史/步进 set status_prop_ok · 档差 tip/set 读回镜像 · 2026-10-28】

- **DST 策略徽章**：菜单 out 同步 `strategy_prop_ok` / `tip_max_len_prop_ok` / `last_toast_brief_prop_ok`。
- **A/B 回滚**：再预览 `set_repreview_count_badge_flash_ms` out 带 `status_prop_ok` / `flash_ms_prop_ok`。
- **忽略名单**：短史 set flash_ms out 带 `status_prop_ok` / `flash_ms_prop_ok`。
- **jitter 旁标音量**：步进 set flash_ms out 带 `status_prop_ok` / `flash_ms_prop_ok`。
- **栈预览跳档**：tip/set 读回镜像 `tip_prop_ok` / `flash_ms_prop_ok`（旁标 `jumpDeltaBadgeHoverTip`）。
- **验证**：`scripts/smoke-wave119-…-e2e.py` 7/7；regress wave118 6/6。非硬件约 **~99.98%**。

## 【细妆86 · 再预览/短史/步进 refresh status_prop_ok · 策略 tip/set 读回校验 · 档差 set_flash_ms status_prop_ok · 2026-10-28】

- **A/B 回滚**：再预览 refresh out 带 `status_prop` / `status_prop_ok` 读回字段。
- **忽略名单**：短史 refresh out 带 `status_prop_ok`。
- **jitter 旁标音量**：步进 refresh out 带 `status_prop_ok`。
- **DST 策略徽章**：tip/set 读回校验 `tip_max_len_prop_ok` / `last_toast_brief_prop_ok`。
- **栈预览跳档**：`set_jump_delta_badge_flash_ms` out 带 `status_prop_ok`。
- **验证**：`scripts/smoke-wave118-…-e2e.py` 6/6；regress wave117 6/6。非硬件约 **~99.97%**。

## 【细妆85 · 策略旁标 tip_max_len/last_toast_brief 属性 · 再预览/短史/步进 tip status 读回 · 档差 refresh status_prop_ok · 2026-10-28】

- **DST 策略徽章**：旁标属性同步 `dstImportStrategyBadgeHoverTipMaxLen` / `dstImportStrategyBadgeLastToastBrief`（tip + set 截断档）。
- **A/B 回滚**：再预览 tip 写入 status/flash_ms 属性并读回校验（`_…_status_prop_ok`）。
- **忽略名单**：短史 tip 写入 status/flash_ms 属性并读回校验。
- **jitter 旁标音量**：步进 tip 写入 `wheelStepBadgeStatus`/`…FlashMs` 并读回校验。
- **栈预览跳档**：refresh out 带 `status_prop` / `status_prop_ok` 读回字段。
- **验证**：`scripts/smoke-wave117-…-e2e.py` 6/6；regress wave116 6/6。非硬件约 **~99.95%**。

## 【细妆84 · 再预览/短史/步进旁标属性同步 status/flash_ms · 策略截断档改后刷新 tip · 档差 tip status 属性读回校验 · 2026-10-28】

- **A/B 回滚**：再预览角标 `repreviewCountBadgeStatus` / `repreviewCountBadgeFlashMs` 属性同步（set + refresh）。
- **忽略名单**：短史徽章 `batchRemoveUndoToastHistoryBadgeStatus` / `…FlashMs` 属性同步（set + refresh）。
- **jitter 旁标音量**：步进旁标 `wheelStepBadgeStatus` / `wheelStepBadgeFlashMs` 属性同步（set + refresh）。
- **DST 策略徽章**：`set_strategy_badge_hover_tip_max_len` 改截断档后刷新 tip/ToolTip（`tip_refreshed`）。
- **栈预览跳档**：tip 写入 `jumpDeltaBadgeStatus` 后读回校验（`_…_status_prop_ok`）。
- **验证**：`scripts/smoke-wave116-…-e2e.py` 6/6；regress wave115 6/6。非硬件约 **~99.9%**。

## 【细妆83 · 再预览/短史改闪标档后刷新 tip · 步进 tip/status 同步闪标档 · 策略截断后仍见上次 toast · 档差 status 旁标属性同步 · 2026-10-28】

- **A/B 回滚**：再预览角标 `set_repreview_count_badge_flash_ms` 改档后刷新 tip/ToolTip/status（`tip_refreshed`）。
- **忽略名单**：短史徽章 `set_batch_remove_undo_toast_history_badge_flash_ms` 改档后刷新 tip/ToolTip/status。
- **jitter 旁标音量**：步进旁标改闪标档后刷新 tip/status；refresh 写出 `flash_ms`/`status`/`tip`。
- **DST 策略徽章**：tip 截断后仍追加「上次 toast：…」摘要（`_…_toast_brief`；长 toast 截 32 字）。
- **栈预览跳档**：档差旁标 `jumpDeltaBadgeStatus` / `jumpDeltaBadgeFlashMs` 属性与 status 同步（refresh + set）。
- **验证**：`scripts/smoke-wave115-…-e2e.py` 6/6；regress wave114 6/6。非硬件约 **~99.8%**。

## 【细妆82 · 步进闪标时长可配 · 再预览 tip 闪标档 · 短史 tip/status 闪标档 · 策略 tip 显示上次 toast · 档差改闪标档后刷新 tip · 2026-10-28】

- **jitter 旁标音量**：步进旁标闪标时长可配（QSettings `host/wheelStepBadgeFlashMs`；右键子菜单「闪标时长 · Nms」档 300/600/1200/1800；tip 写入「闪标档：Nms」）。
- **A/B 回滚**：再预览悬停 tip/status 写入「闪标档：Nms」。
- **忽略名单**：短史徽章 tip API + refresh tip/status 写入「闪标档：Nms」。
- **DST 策略徽章**：悬停 tip 显示「上次 toast：…」（无 / 已复制原长：N字）。
- **栈预览跳档**：右键改闪标档后刷新 tip/ToolTip/status（`tip_refreshed`）。
- **验证**：`scripts/smoke-wave114-…-e2e.py` 6/6；regress wave113 6/6。非硬件约 **~99.7%**。

## 【细妆81 · 再预览闪标时长可配 · 步进夹紧预览后闪标 · 短史闪标时长可配 · 策略复制原长写入悬停 toast · 档差闪标档写入 tip/status · 2026-10-28】

- **A/B 回滚**：再预览角标闪标时长可配（QSettings `host/repreviewCountBadgeFlashMs`；右键子菜单「闪标时长 · Nms」档 300/600/1200/1800；夹紧预览后闪标沿用配置）。
- **jitter 旁标音量**：步进旁标「夹紧预览」后闪标（橙边高亮）；`flashed` 写入预览结果。
- **忽略名单**：短史徽章闪标时长可配（QSettings `host/batchRemoveUndoToastHistoryBadgeFlashMs`；右键子菜单「闪标时长」）。
- **DST 策略徽章**：「复制原长」写入悬停 toast（`toast`/`_last_…_hover_toast`）；tip 可复制行含「→toast」。
- **栈预览跳档**：档差旁标 tip/refresh status 写入「闪标档：Nms」。
- **验证**：`scripts/smoke-wave113-…-e2e.py` 6/6；regress wave112 6/6。非硬件约 **~99.6%**。

## 【细妆80 · 档差闪标时长可配 · 短史双击复位后闪标 · 策略 tip 原长可复制 · 再预览夹紧预览后闪标 · 步进右键夹紧预览 · 2026-10-28】

- **栈预览跳档**：档差旁标闪标时长可配（QSettings `host/jumpDeltaBadgeFlashMs`；右键子菜单「闪标时长 · Nms」档 300/600/1200/1800；夹紧预览后闪标沿用配置）。
- **忽略名单**：短史徽章双击复位后闪标（绿边高亮）；`flashed` 写入复位结果。
- **DST 策略徽章**：右键「复制原长」剪贴板「原长：N字」；悬停 tip 可复制行含「复制原长」。
- **A/B 回滚**：再预览「夹紧预览」后闪标（橙边 ~600ms）；`flashed` 写入预览结果。
- **jitter 旁标音量**：步进旁标右键「夹紧预览」示意区+现→夹紧。
- **验证**：`scripts/smoke-wave112-…-e2e.py` 6/6；regress wave111 6/6。非硬件约 **~99.5%**。

## 【细妆79 · 档差夹紧预览后闪标 · 短史徽章双击复位 · 策略 tip 截断示原长 · 再预览右键夹紧预览 · 步进拖移夹紧边界 · 2026-10-28】

- **栈预览跳档**：档差旁标「夹紧预览」后闪标（橙边高亮 ~600ms）。
- **忽略名单**：短史徽章双击复位位置 (8,172)（toast「双击已复位短史徽章」）。
- **DST 策略徽章**：截断时悬停 tip 追加「原长：N字」。
- **A/B 回滚**：再预览冲突角标右键「夹紧预览」示意区+现→夹紧。
- **jitter 旁标音量**：步进旁标拖移/move_to 经 clamp API 夹紧到父客户区；悬停含边界提示。
- **验证**：`scripts/smoke-wave111-…-e2e.py` 6/6；regress wave110 6/6。非硬件约 **~99.3%**。

## 【细妆78 · 档差旁标右键夹紧预览 · 短史徽章拖移可定位 · 策略截断当前档写入 tip · 再预览悬停夹紧边界 · 步进旁标拖移可定位 · 2026-10-28】

- **栈预览跳档**：档差旁标右键「夹紧预览」示意（toast 区(0,0)–(max) · 现→夹紧）。
- **忽略名单**：短史徽章拖移可定位并持久（QSettings `icsBatchRemoveUndoToastHistoryBadgePos`）。
- **DST 策略徽章**：悬停 tip 写入「截断档：N字」当前档。
- **A/B 回滚**：再预览冲突角标悬停含「边界：拖移夹紧到父客户区（越界归零）」。
- **jitter 旁标音量**：步进旁标拖移可定位并持久（QSettings `jitterFlashDoneSoundVolumeMuteBadgeBarWheelStepBadgePos`）。
- **验证**：`scripts/smoke-wave110-…-e2e.py` 6/6；regress wave109 6/6。非硬件约 **~99.1%**。

## 【细妆77 · 档差旁标悬停夹紧提示 · 短史徽章右键清短史 · 策略截断长度右键设档 · 再预览角标拖移夹紧 · 步进旁标双击复位 · 2026-10-28】

- **栈预览跳档**：档差旁标悬停含「边界：拖移夹紧到父客户区」提示。
- **忽略名单**：短史徽章右键「清短史」快捷（兼「打开短史菜单…」）。
- **DST 策略徽章**：右键菜单「截断长度 · N字」设档 48/96/160/240。
- **A/B 回滚**：再预览冲突角标拖移/move_to 夹紧到父客户区。
- **jitter 旁标音量**：步进旁标双击复位步进至 5%（toast「双击已复位步进 · 5%」）。
- **验证**：`scripts/smoke-wave109-…-e2e.py` 6/6；regress wave108 6/6。非硬件约 **~98.9%**。

## 【细妆76 · 档差旁标拖移边界夹紧 · 短史徽章点击开菜单 · 策略截断可配置长度 · 再预览角标双击复位 · 步进旁标悬停含已复位状态 · 2026-10-28】

- **栈预览跳档**：档差旁标拖移/move_to 夹紧到父客户区（负坐标与越界归零）。
- **忽略名单**：短史徽章（短史N）左键点击打开短史菜单。
- **DST 策略徽章**：悬停说明截断长度可配置（QSettings `dstImportStrategyBadgeHoverTipMaxLen`，默认 96，范围 16–400）。
- **A/B 回滚**：再预览冲突角标双击复位位置 (8,120) 并清计数。
- **jitter 旁标音量**：步进旁标悬停含「状态：已复位／自定义」；复位 API 回报 tip_has_reset_status。
- **验证**：`scripts/smoke-wave108-…-e2e.py` 6/6；regress wave107 6/6。非硬件约 **~98.7%**。

## 【细妆75 · 档差旁标双击复位确认toast · 清短史后徽章刷新 · 策略悬停说明长度截断 · 再预览角标右键复位 · 步进旁标右键复位步进 · 2026-10-28】

- **栈预览跳档**：档差旁标双击复位位置并确认 toast「双击已复位档差旁标」。
- **忽略名单**：清短史后刷新冲突徽章 tip（撤销短史 · N条）。
- **DST 策略徽章**：悬停说明截断至 96 字（超出加 …）。
- **A/B 回滚**：再预览冲突角标右键「复位位置」回 (8,120)。
- **jitter 旁标音量**：步进旁标右键「复位步进」回 5%。
- **验证**：`scripts/smoke-wave107-…-e2e.py` 6/6；regress wave106 6/6。非硬件约 **~98.5%**。

## 【细妆74 · 档差旁标右键复位 · 短史菜单清短史 · 策略悬停可复制 · 再预览角标拖移 · 步进旁标悬停当前值说明 · 2026-10-28】

- **栈预览跳档**：档差旁标右键「复位位置」回 (8,148)；菜单「复位档差旁标」。
- **忽略名单**：撤销短史菜单新增「清短史」。
- **DST 策略徽章**：悬停说明可复制（菜单「复制悬停说明」→剪贴板）。
- **A/B 回滚**：再预览冲突角标可拖移并持久坐标。
- **jitter 旁标音量**：步进旁标悬停说明当前步进百分点与可选值。
- **验证**：`scripts/smoke-wave106-…-e2e.py` 6/6；regress wave105 6/6。非硬件约 **~98%**。

## 【细妆73 · 档差旁标可拖/双击清 · 撤销短史菜单项 · 策略徽章悬停说明 · 再预览角标双击清计数 · 步进旁标右键设1/5/10 · 2026-10-28】

- **栈预览跳档**：档差旁标可拖移并持久坐标；双击/菜单「清档差旁标」。
- **忽略名单**：撤销短史菜单项列出 toast 短史可逐条回看。
- **DST 策略徽章**：悬停说明含合/覆语义 + 左键切换/右键菜单提示。
- **A/B 回滚**：再预览冲突角标双击清计数。
- **jitter 旁标音量**：步进旁标右键设 1%/5%/10%。
- **验证**：`scripts/smoke-wave105-…-e2e.py` 6/6；regress wave104 6/6。非硬件约 **~97.5%**。

## 【细妆72 · 跳档档差旁标持久 · 撤销批量移除toast可回看 · 策略徽章右键菜单 · 再预览角标点击跳冲突 · 滚轮步进旁标显示 · 2026-10-28】

- **栈预览跳档**：档差浮动旁标 `档差±N` 持久刷新；菜单「档差旁标」。
- **忽略名单**：撤销批量移除 toast 记入短史，可「回看撤销批量移除」再闪。
- **DST 策略徽章**：右键菜单 合/覆/切换；refresh 时绑定点击+右键（避免 ensure↔bind 递归）。
- **A/B 回滚**：再预览冲突角标点击 → 跳冲突 toast（再预览N · 首冲突键）。
- **jitter 旁标音量**：滚轮步进旁标 `步进·N%`；set/cycle 时同步刷新。
- **验证**：`scripts/smoke-wave104-…-e2e.py` 6/6；regress wave103 6/6。非硬件约 **~97%**。

## 【细妆71 · 跳档确认toast档差 · 批量移除撤销 · 策略徽章点击切换 · 再预览冲突计数角标 · 滚轮步进可配 · 2026-10-28】

- **栈预览跳档**：确认 toast 显示 `#{from}→#{to} · 档差±N`；预览条 focus 持久供档差计算。
- **忽略名单**：多选批量移除后可「撤销批量移除」一键回加；smoke `batch_remove_undo`。
- **DST 策略徽章**：点击旁标在 合(merge)↔覆(overwrite) 间切换；菜单「徽章点击切换」。
- **A/B 回滚**：忽略后再预览冲突数浮动角标 `再预览·N`（N=0 隐藏）。
- **jitter 旁标音量**：滚轮步进可配 1/5/10%（getter/setter/cycle）；绑定滚轮读配置步进。
- **验证**：`scripts/smoke-wave103-…-e2e.py` 6/6；regress wave102 6/6。非硬件约 **~96.5%**。

## 【细妆70 · 栈预览条点击跳档 · 多选忽略批量移除 · DST策略徽章 · A/B忽略后再预览 · 旁标滚轮调音 · 2026-10-28】

- **栈预览条点击跳档**：`bind_…_preview_bar_click_jump` + `jump_…_to(index)`；芯片点击 `restore_at`；菜单「点击跳档」。
- **多选忽略批量移除**：`batch_remove_…_overlap_highlight_keys`；按高亮键批量移出忽略名单；菜单「多选批量移除」。
- **DST 策略徽章**：`ensure_/refresh_…_import_strategy_badge`（合/覆）；`set_…_strategy` 自动刷新；菜单「策略徽章」。
- **A/B 忽略后自动再预览**：`ignore_…_rollback_conflicts` 返回 `repreview` / `repreview_conflict_n`；忽略后自动再预览（`repreview`）；按钮 tip「忽略冲突键后自动再预览」。
- **旁标滚轮调音**：`bind_…_volume_mute_badge_bar_wheel` + `wheel_…_by(delta_pct)`；菜单「旁标滚轮调音」。
- 非硬件进度约 **~96%**（细妆持续）。

## 【细妆69 · 频率撤销栈档位预览条 · 忽略高亮多选滚入 · DST diff导入策略合并/覆盖 · A/B回滚冲突一键忽略 · jitter旁标拖拽调音 · 2026-10-28】

- **频率撤销栈档位预览条**：`ensure_/refresh_…_undo_stack_preview_bar`；深度 chips + focus；角标菜单「档位预览条」。
- **忽略高亮多选滚入**：`highlight_…_overlap_rows(keys)` + `scroll_…_highlight_keys_into_view`；菜单「多选高亮滚入」。
- **DST diff 导入策略（合并/覆盖）**：`…_batch_diff_import_strategy` / `set_…`；`import_…_batch_diff(strategy=)`；覆盖先清史再写入；菜单「导入策略·合并 / ·覆盖」。
- **A/B 回滚冲突一键忽略**：`ignore_…_rollback_conflicts`；把预览冲突键写入忽略名单；槽对话框「一键忽略冲突」。
- **jitter 旁标拖拽调音**：`bind_…_volume_mute_badge_bar_drag` + `drag_…_to(pct)`；垂直拖拽写音量；菜单「旁标拖拽调音」。
- 非硬件进度约 **~95.5%**（细妆持续）。

## 【细妆68 · 频率撤销栈按档回退/清空 · 忽略高亮滚入可视 · DST diff导入再应用 · A/B回滚预览冲突列表 · jitter音量旁标条 · 2026-10-28】

- **频率撤销栈按档回退/清空**：`restore_…_undo_stack_at(index)` 恢复指定档并丢弃更新档；`clear_…_undo_stack`；角标菜单「按档回退… / 清空撤销栈」。
- **忽略高亮自动滚入可视**：`scroll_…_overlap_highlight_into_view`；高亮后自动滚入/激活菜单行；浮动 tip「跳 · key」；菜单「滚入高亮行」。
- **DST diff 导入再应用**：`import_…_batch_diff(apply=True)` 读导出 JSON 并写入历史；`apply_…_batch_diff` 对 last diff.added 再应用；历史菜单「导入差异… / 再应用差异」。
- **A/B 回滚预览冲突列表**：`preview_…_rollback_conflicts`；回滚确认框列出冲突 tip；槽对话框「预览冲突」按钮。
- **jitter 音量旁标条**：`ensure_/refresh_…_volume_mute_badge_bar`（QProgressBar 旁标）；`set_volume`/静音刷新联动；旁标菜单「音量旁标条」。
- **验证**：`scripts/smoke-wave100-…-e2e.py` 6/6；regress wave99 6/6。非硬件约 **~95%**。


## 【细妆67 · 频率合并撤销栈多级/对比预览 · 重叠跳转高亮名单行 · DST diff导出/一键清新增 · A/B回滚确认+冲突再检 · jitter wav试听/音量 · 2026-10-28】

- **频率合并撤销栈多级/对比预览**：合并前压栈（最多16）；`list_…_import_merge_undo_stack`；`preview_/show_…_undo_compare_preview`（当前 vs 栈项 +/~/-/~）；角标菜单「撤销上次合并 · 栈N / 撤销栈对比预览」。
- **重叠跳转高亮名单行**：`highlight_…_overlap_row`；跳转写入高亮键；忽略菜单角色行前缀「跳」并勾选；菜单「高亮重叠行」。
- **DST diff 导出/一键清新增**：`export_…_batch_diff`（JSON）；`clear_…_batch_diff_added`（按 last diff.added 剔除历史）；历史菜单「导出差异… / 一键清新增」。
- **A/B 回滚确认+冲突再检**：回滚 UI 确认框；回滚后 `detect_…_default_slot_shortcut_conflicts` 再检写入 out/史；toast 带冲突数。
- **jitter wav 试听/音量**：`…_flash_done_sound_volume` / `prompt_…`；`preview_…_flash_done_sound`（force 绕静音）；`_play_…` 读音量；旁标菜单「试听闪完音 / 闪完音量…」。
- **验证**：`scripts/smoke-wave99-…-e2e.py` 6/6；regress wave98 6/6。非硬件约 **~94.5%**。


## 【细妆66 · 频率预设导入合并策略记忆/撤销 · 忽略策略旁标点击跳重叠项 · DST批量复检差异diff toast · A/B快捷史回滚一键 · jitter闪完音效自定义wav/关声旁标 · 2026-10-28】

- **频率预设导入合并策略记忆/撤销**：`…_badge_freq_import_merge_strategy`；合并默认读记忆；合并前快照；`undo_…_badge_freq_import_merge`；角标菜单「合并策略记忆 · … / 撤销上次合并」。
- **忽略策略旁标点击跳重叠项**：`jump_…_merge_strategy_overlap`；旁标 `mousePressEvent` 连点轮询重叠键；忽略菜单「跳转重叠项」。
- **DST 批量复检差异 diff toast**：批量复检对比上次 hit/keys；`diff{added,cleared,delta_hit}`；`show_…_batch_diff_toast`；历史菜单「差异 toast」。
- **A/B 快捷史回滚一键**：`rollback_…_default_slot_shortcut_history`；槽位对话框「快捷史回滚」。
- **jitter 闪完音效自定义 wav/关声旁标**：`…_flash_done_sound_wav` / `pick_…`；`…_mute_badge` + 旁标刷新/点击切换；`_play_…`（wav→aplay→beep）；旁标菜单「闪完 wav… / 关声旁标」。
- **验证**：`scripts/smoke-wave98-…-e2e.py` 6/6；regress wave97 6/6。非硬件约 **~94%**。


## 【细妆65 · pin频率预设导入冲突预览/一键合并 · 忽略名单合并策略快捷/冲突旁标 · DST复检批量/导出筛选结果 · A/B默认槽改绑冲突检测/最近快捷史 · jitter闪完音效/旁标闪完计数清零 · 2026-10-28】

- **pin 频率预设导入冲突预览/一键合并**：`preview_…_badge_freq_import_conflicts`（name 重叠 / ms 不一致）；`merge_…_badge_freq_import`（replace|merge|prefer_incoming|prefer_existing）；角标菜单「导入冲突预览… / 一键合并导入…」。
- **忽略名单合并策略快捷/冲突旁标**：`…_merge_strategy_shortcut`（默认 Ctrl+Alt+M）；`cycle_…_merge_strategy`；`refresh_…_merge_strategy_conflict_badge`（角色键重叠旁标）；忽略菜单「策略快捷 / 冲突旁标」。
- **DST 复检批量/导出筛选结果**：`recheck_…_conflict_history_batch`；`export_…_conflict_history_filtered`；历史菜单「批量复检 / 导出筛选…」。
- **A/B 默认槽改绑冲突检测/最近快捷史**：`detect_…_default_slot_shortcut_conflicts`；`list_/remember_…_default_slot_shortcut_history`；改绑对话框检测冲突并记史；槽位对话框 smoke 含 `shortcut_history`。
- **jitter 闪完音效/旁标闪完计数清零**：`…_flash_done_sound`（`QApplication.beep`）；`…_flash_done_clear_count`（闪完后置 flash_count=1）；旁标菜单「闪完音效 / 闪完清零计次」。
- **验证**：`scripts/smoke-wave97-…-e2e.py` 6/6；regress wave96 6/6。非硬件约 **~93.5%**。


## 【细妆64 · pin频率预设改名/另存当前ms为档 · 忽略名单导入分组JSON/角色合并策略 · DST冲突历史点选复检/按which筛 · A/B默认槽快捷可改绑/启动开关 · jitter闪完toast文案可配/仅末次提示 · 2026-10-28】

- **pin 频率预设改名/另存当前 ms 为档**：`rename_…_badge_freq_preset`；`save_…_badge_freq_preset_as`；角标菜单「改名… / 另存当前为档…」。
- **忽略名单导入分组 JSON/角色合并策略**：`…_ignore_by_role_merge_strategy`（replace|merge|prefer_incoming|prefer_existing）；`import_…_ignore_by_role`；忽略菜单「导入分组 JSON… / 合并策略」。
- **DST 冲突历史点选复检/按 which 筛**：`…_conflict_history_which_filter`；`list_…_conflict_history_filtered`；`recheck_…_conflict_history_entry`；历史菜单「按 which 筛 / 复检 · …」。
- **A/B 默认槽快捷可改绑/启动开关**：`…_default_slot_autoload_enabled`；`show_…_default_slot_shortcut_rebind_dialog`；槽位对话框「改绑跳默认… / 启动载入开|关」；autoload 尊重开关。
- **jitter 闪完 toast 文案可配/仅末次提示**：`…_flash_toast_text`（`{times}/{color}`）；`…_flash_toast_last_only`；旁标菜单「闪完文案… / 仅末次提示」；`flash_…` 按开关 toast。
- **冒烟**：`smoke-wave96-pinsuggestbadgefreqrenamesaveas-confirmstratignoreimportbyrolemerge-dstconflicthistrecheckwhich-abprevdefaultrebindautoloadtoggle-jitterflashtoasttextlastonly-e2e`（另回归 wave95）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。
- **非硬件粗估**：~93%。

---

## 【细妆63 · pin角标频率预设拖拽排序/右键删档 · 忽略名单按角色批量清/导出分组JSON · DST冲突历史菜单浏览/导出/上限 · A/B默认槽启动自动载入/快捷跳默认 · jitter旁标闪色/次数可配/闪完toast · 2026-10-28】

- **pin 角标频率预设拖拽排序/右键删档**：`reorder/delete_…_badge_freq_presets`；`show_…_badge_freq_presets_manage_dialog`（InternalMove）；角标菜单「管理频率预设… / 删频率档」。
- **忽略名单按角色批量清/导出分组 JSON**：`clear_…_ignore_role`；`export_…_ignore_by_role`（by_role+flat）；忽略菜单「清空角色 / 导出分组 JSON…」。
- **DST 冲突历史菜单浏览/导出/上限**：`…_conflict_history_limit` / `set_…`；`export_…_conflict_history`；`show_…_conflict_history_menu`；DST 撤栈旁标「冲突历史…」。
- **A/B 默认槽启动自动载入/快捷跳默认**：`autoload/jump_…_layout_default_slot`；默认快捷 `Ctrl+Alt+D`；槽位对话框「跳默认」；ensure slots 钩 autoload。
- **jitter 旁标闪色/次数可配/闪完 toast**：`…_flash_color/count/toast`；`flash_…_undo_depth_lab` 多闪；旁标菜单「旁标闪色/闪次/闪完 toast」。
- **冒烟**：`smoke-wave95-pinsuggestbadgefreqmanagedelete-confirmstratignorroleclear-dstconflicthistmenuexportlimit-abprevdefaultautoloadjump-jitterflashcolorcounttoast-e2e`（另回归 wave94）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆62 · pin角标频率预设档/导出 · 忽略名单按角色分组 · DST冲突历史 · A/B槽位拖拽排序/默认槽 · jitter长按时长可配/旁标闪 · 2026-10-28】

- **pin 角标频率预设档/导出**：`list/set/apply_…_badge_freq_presets`；`export/import_…_badge_freq`（JSON）；角标菜单「频率预设… / 导出·导入」；默认档快/标准/慢。
- **忽略名单按角色分组**：`list/set_…_conflict_ignore_by_role`；`add/remove_…_ignore_role`；与扁平 ignore 列表双向同步；忽略菜单按角色分区。
- **DST 冲突历史**：`list/remember/clear_…_reorder_shortcut_conflict_history`；detect 写入；旁标 tip/菜单「冲突历史…」。
- **A/B 槽位拖拽排序/默认槽**：`reorder_…_preview_layout_slots`（InternalMove）；`set/get_…_default_slot`（★）；对话框拖拽 + 设默认。
- **jitter 长按时长可配/旁标闪**：`…_long_press_ms` / `set_…` / `show_…_long_press_ms_dialog`；清栈后 `flash_…_undo_depth_lab`；旁标菜单「长按时长…」。
- **冒烟**：`smoke-wave94-pinsuggestbadgefreqpresets-confirmstratignorebyrole-dstconflicthist-abprevslotsreorderdefault-jitterlongpressflash-e2e`（另回归 wave93）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆61 · pin筛选预设角标右键清零/频率 · 冲突忽略名单菜单管理/导入导出 · DST冲突旁标橙/跳过 · A/B槽位对话框UI/快捷切换 · jitter撤栈深度长按清/冲突检测 · 2026-10-28】

- **pin 筛选预设角标右键清零/频率**：`clear_…_reorder_badge` / `…_badge_freq_ms` / `set_…_badge_freq_ms` / `show_…_reorder_badge_context_menu`；flash 用 freq_ms；预设菜单「排序角标…」。
- **冲突忽略名单菜单管理/导入导出**：`export/import_…_conflict_ignore`（JSON）；`show_…_conflict_ignore_menu`（移除/清空/导入导出）；ICS 旁标菜单「忽略名单…」。
- **DST 冲突旁标橙/跳过**：`…_shortcut_conflicts_acked` / `clear/resume_…_conflicts_badge`；撤栈旁标橙 tip + 菜单跳过/恢复。
- **A/B 槽位对话框 UI/快捷切换**：`show_…_layout_slots_dialog`；`cycle_…_layout_slot`；默认 `Ctrl+Alt+L`；预览「槽位…」。
- **jitter 撤栈深度长按清/冲突检测**：长按清撤栈（QTimer）；`detect/format_…_reorder_shortcut_conflicts`；旁标 tip「长按清栈」+ 冲突橙。
- **冒烟**：`smoke-wave93-pinsuggestfilterpresetbadgefreq-confirmstratignoreio-dstconflictskip-abprevslotsdlg-jitterundolongpress-e2e`（另回归 wave92/91）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆60 · pin筛选预设拖拽排序持久动画/角标 · 冲突检测历史/忽略名单 · DST快捷冲突检测 · A/B布局多槽位/命名 · jitter撤栈旁标右键清栈/可改绑 · 2026-10-28】

- **pin 筛选预设拖拽排序持久动画/角标**：`…_reorder_badge` / `note_…_reorder` / `flash_…_reorder_badge`（QSettings 计数·时刻·长度）；reorder 后 toast「筛选预设排序 · ×N」；对话框 tip / 菜单「拖拽排序… · ×N」角标。
- **冲突检测历史/忽略名单**：`list/remember/clear_…_conflict_history`；`list/add/remove/clear_…_conflict_ignore`；detect 跳过忽略键并写入历史。
- **DST 快捷冲突检测**：`detect/format_…_reorder_shortcut_conflicts(which=undo|redo)`（保留键 + 冲突策略/jitter/筛选预设/对端）；`set_…_shortcuts` 成对 stamp toast。
- **A/B 布局多槽位/命名**：`list/save/load/rename/delete_…_preview_layout_slot(s)`（JSON 命名槽）。
- **jitter 撤栈旁标右键清栈/可改绑**：lab_jud 右键菜单（撤销/清撤栈/改绑）；`show_…_reorder_undo_shortcut_rebind_dialog`；tip「右击菜单/清栈/改绑」。
- **冒烟**：`smoke-wave92-pinsuggestfilterpresetbadge-confirmstrathistoryignore-dstconflict-abprevslots-jitterundomenu-e2e`（另回归 wave91/90）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆59 · pin筛选预设右键/快捷 · 冲突检测一键跳过/清橙 · DST快捷可改绑 · A/B布局导出导入 · jitter撤栈旁标快捷 · 2026-10-28】

- **pin 筛选预设右键/快捷**：默认 `Ctrl+Alt+P` → `_ensure_…_filter_query_presets_shortcut`；`show_…_filter_query_presets_context_menu`（应用/上移下移置顶置底/清空）；最近查询子菜单「预设菜单…」。
- **冲突检测一键跳过/清橙**：`…_conflicts_acked`；旁标 tip 尊重 ack；橙标仅 `conflict && !acked`（修 wave90 重复 cyan 覆盖）；菜单「跳过冲突提示 / 恢复橙标」；detect 增补 jitter撤 + 筛选预设。
- **DST 快捷可改绑**：`show_…_reorder_shortcuts_rebind_dialog`；撤/重做旁标菜单「改绑…」；tooltip「右击菜单/改绑」。
- **A/B 布局导出导入**：`export/import_…_preview_layout`（JSON）；布局对话框「导出布局 / 导入布局」。
- **jitter 撤栈旁标快捷**：默认 `Ctrl+Alt+K`；`lab_jud` 撤栈深度旁标（`_refresh_…_reorder_undo_depth_ui`）；与 redo 旁标并列。
- **冒烟**：`smoke-wave91-pinsuggestfilterpresetctx-confirmstratskip-dstrebind-abprevlayoutio-jitterundohotkey-e2e`（另回归 wave90/89；smoke90 冲突 peer 改读 live 快捷）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆58 · pin建议历史筛选预设拖拽排序 · 冲突策略快捷键冲突检测 · DST旁标快捷键 · A/B预览列宽/持久布局 · jitter旁标快捷键可改绑 · 2026-10-28】

- **pin 建议历史筛选预设拖拽排序**：`reorder/show_…_filter_query_presets_reorder_dialog`（QListWidget InternalMove）；最近查询子菜单「拖拽排序…」；QSettings 持久。
- **冲突策略快捷键冲突检测**：`detect/format_…_strategy_shortcut_conflicts`（保留键 + 吸史撤/重序 + 钉上限 ± + jitter重做 + DST撤/重做）；`set_…` 冲突 toast；旁标 tip ⚠ + 橙标。
- **DST 旁标快捷键**：默认 `Ctrl+Alt+U`/`Ctrl+Alt+D` → `_on_dst_reorder_undo/redo_hotkey`；`get/set/_ensure_…_reorder_shortcuts`；tooltip 标键。
- **A/B 预览列宽/持久布局**：`get/set_…_preview_layout`（columns/widths/dialog_w/h/filter/sort/reverse）；开窗还原 · 关闭写入；`is…PreviewLayout`。
- **jitter 旁标快捷键可改绑**：`show_…_reorder_redo_shortcut_rebind_dialog`；右键菜单「改绑快捷键…」；tooltip「右击菜单/改绑」。
- **冒烟**：`smoke-wave90-pinsuggestfilterpresetreorder-confirmstratconflict-dsthotkey-abprevlayout-jitterrebind-e2e`（另回归 wave89/88/87）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆57 · pin建议历史筛选预设持久/导出 · 冲突策略快捷键可改绑定 · DST旁标右键菜单 · A/B预览列显隐 · jitter旁标快捷键 · 2026-10-28】

- **pin 建议历史筛选预设持久/导出**：`export/import_…_filter_query_presets` JSON；最近查询子菜单「导出预设…/导入预设…」；QSettings 已持久。
- **冲突策略快捷键可改绑定**：`get/set_…_strategy_shortcut` + `_ensure_…`；旁标右键「改绑快捷键…」；`show_…_rebind_dialog`；tooltip 显当前键。
- **DST 旁标右键菜单**：撤/重做旁标 QMenu（撤销·清撤栈 / 重做·清重做栈）；`clear_…_reorder_undo`；`_dst_reorder_depth_lab_menu_no_exec` smoke。
- **A/B 预览列显隐**：`get/set/toggle_…_preview_columns`；对话框列勾选；`format_…` 尊列；至少一列。
- **jitter 旁标快捷键**：默认 `Ctrl+Alt+J` → `_on_jitter_reorder_redo_hotkey`；`_ensure_jitter_reorder_redo_shortcut`；tooltip 标键。
- **冒烟**：`smoke-wave89-pinsuggestfilterpresetio-confirmstratrebind-dstlabmenu-abprevcols-jitterhotkey-e2e`（另回归 wave88/87/86）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆56 · pin建议历史筛选最近查询预设 · 冲突策略旁标快捷键 · DST撤重做旁标 · A/B预览列筛/排序 · jitter旁标右键菜单 · 2026-10-28】

- **pin 建议历史筛选最近查询预设**：`list/remember/apply/clear_…_filter_query_presets`；筛选对话框「最近查询」子菜单 + 清预设；`set_…_filter_query` 顺带 remember。
- **冲突策略旁标快捷键**：`Ctrl+Alt+I` → `_on_confirm_trial_undo_import_conflict_strategy_hotkey` 循环 替/并/跳/询；旁标 tooltip 标快捷键；`is…StrategyShortcut`。
- **DST 撤重做旁标**：`hostDstClearUndoTtlPresetCustomsReorderUndoDepthLab` / `…RedoDepthLab`；`_refresh_…_reorder_depth_ui`；undo/redo/clear/reorder 挂钩刷新。
- **A/B 预览列筛/排序**：`filter/sort_…_preview_rows`；对话框 QComboBox 状态筛 + 列排；表即时 refill。
- **jitter 旁标右键菜单**：`_on_jrd_click` 右击改 QMenu「重做 · N / 清重做栈 · N」；`_jitter_reorder_redo_lab_menu_no_exec` smoke；tooltip「右击菜单」。
- **冒烟**：`smoke-wave88-pinsuggesthistfilterpresets-confirmstrathotkey-dstdepthlab-abprevfiltersort-jitterlabmenu-e2e`（另回归 wave87/86/85）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆55 · pin建议历史筛选高亮/多字段 · 冲突策略指示条右键菜单 · DST自定义排序撤/重做栈 · A/B冲突预览表复制/导出 · jitter重做旁标 chrome · 2026-10-28】

- **pin 建议历史筛选高亮/多字段**：`filter_…` 附 `_matches`/`_highlight`（label/keys/ts）；`highlight_…_suggest_history`；菜单条目「」高亮 + matchFields；对话框「多字段(键/标签/时间)」。
- **冲突策略指示条右键菜单**：旁标左击仍循环；右击 QMenu 替/并/跳/询（可勾选）；`_confirm_trial_undo_ics_lab_menu_no_exec` smoke；tooltip「右击菜单」。
- **DST 自定义排序撤/重做栈**：对齐 jitter；`undo/redo_reorder_…_ttl_preset_customs` + depth/clear_redo；菜单「撤销/重做排序 · N」「清重做栈」。
- **A/B 冲突预览表复制/导出**：`format/copy/export_…_preview_table`；对话框「复制表」「导出…」；TSV。
- **jitter 重做旁标 chrome**：`hostJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLab`；对齐深度 lab；点击重做/右击清栈；`_refresh_…_reorder_redo_depth_ui`。
- **冒烟**：`smoke-wave87-pinsuggesthistfilterhl-confirmstratmenu-dstundoredo-abprevcopyexport-jitterredochrome-e2e`（另回归 wave86/85/84）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆54 · pin建议历史按键过滤/搜索 · 导入冲突策略默认+持久指示条 · DST自定义拖拽排序 · A/B回退冲突预览表 · jitter重做深度/清redo UI · 2026-10-28】

- **pin 建议历史按键过滤/搜索**：`filter/set/get_…_suggest_history_filter_query`；菜单「筛选…」/`清除筛选`；smoke `filter_history`。
- **导入冲突策略默认+持久指示条**：旁标 替/并/跳/询；`refresh_…_import_conflict_strategy_lab`；菜单「· 默认」+「策略默认·持久」；点击循环切换。
- **DST 自定义拖拽排序**：`reorder_…_ttl_preset_customs`；`show_…_reorder_dialog`；菜单「拖拽排序…」；smoke `reorder_customs`。
- **A/B 回退冲突预览表**：`preview_…_import_conflict`（new/same/conflict）；`show_…_preview_dialog`；ask 路径优先预览表。
- **jitter 重做深度指示/清 redo UI**：菜单「重做排序 · N」深度属性；「清重做栈 · N」→ `clear_…_reorder_redo`。
- **冒烟**：`smoke-wave86-pinsuggesthistfilter-confirmstratbar-dstreorder-abprevtable-jitterclearredo-e2e`（另回归 wave85/84/83）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆53 · pin建议历史子菜单UI · 导入冲突策略菜单切换 · DST自定义编辑/删项UI · A/B回退按流程导入/冲突 · jitter排序重做栈 · 2026-10-28】

- **pin 建议历史子菜单 UI**：菜单「历史 · N」；`restore_…_suggest_history(index)`；条目恢复勾选/应用首选；「清空历史」；仅记录所选亦记入历史。
- **导入冲突策略菜单切换**：试键撤栈菜单「导入冲突 · {策略}」可勾选 replace|merge|skip|ask；空栈亦可导入；smoke `set_conflict`/`get_conflict`。
- **DST 自定义编辑/删项 UI**：菜单 ✏/🗑；`edit_…`/`prompt_edit_…_ttl_preset_custom`；smoke `edit_custom`。
- **A/B 回退按流程导入/冲突**：`import_…(flows=, conflict=)`；`get/set_…_import_conflict_strategy`；`import_…_for_flow`；skip/ask/merge/replace。
- **jitter 排序重做栈**：undo 推 `_…_reorder_redo`；`redo_reorder_…(steps=)`；`…_reorder_redo_depth`；新排序清 redo；菜单「重做排序 · N」。
- **冒烟**：`smoke-wave85-pinsuggesthistmenu-confirmstratmenu-dstedit-abflowimp-jitterredo-e2e`（另回归 wave84/83/82）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆52 · pin建议多选持久/历史 · 试键撤栈导入冲突策略 · DST TTL自定义档 · A/B回退记忆按流程导出 · jitter排序多级撤栈 · 2026-10-28】

- **pin 建议多选持久/历史**：`persist/load/set_…_suggest_selected`；`list/remember/clear_…_suggest_history`；apply_all_clean / 菜单勾选记入历史；smoke `history`/`restore_history`/`clear_history`。
- **试键撤栈导入冲突策略**：`get/set_…_import_conflict_strategy`（replace|merge|skip|ask）；`import_…(conflict=…)`；冲突跳过/询问（smoke）；菜单 import 透传 conflict。
- **DST TTL 自定义档**：`list/persist/add/delete/prompt_add_…_ttl_preset_customs`；`list_…_presets` 合并 ★自定义；菜单「添加自定义档…」；smoke `add_custom`/`delete_custom`。
- **A/B 回退记忆按流程导出子集**：`export_…_fallback(flows=…)`；`export_…_fallback_for_flow`；payload `subset`/`flows`。
- **jitter 排序多级撤栈**：reorder 推 `_…_reorder_undo`（深16）；`…_reorder_undo_depth`；`undo_reorder_…(steps=)`；`clear_…_reorder_undo`；兼容单 snap。
- **冒烟**：`smoke-wave84-pinsuggesthist-confirmconflict-dstcustom-abflowexport-jittermultistack-e2e`（另回归 wave83/82/81）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆51 · pin建议批量应用全选干净键 · 试键撤栈JSON导入 · DST TTL预设档 · A/B回退记忆导入 · jitter排序可撤 · 2026-10-28】

- **pin 建议批量应用全选干净键**：`apply_all_clean_…_cycle_key_suggests`；菜单「全选干净并应用」；smoke/resolve `action=apply_all_clean`。
- **试键撤栈 JSON 导入**：`import_…_confirm_undo`（replace/merge）；菜单「导入撤栈 JSON」；smoke `action=import`。
- **DST TTL 预设档**：`list/apply_…_clear_undo_ttl_preset(s)`；`show_…_ttl_preset_menu`（0/3/8/15/30/60s + 自定义）。
- **A/B 回退记忆导入**：`import_…_fallback`（merge/replace）；校验 source 白名单。
- **jitter 排序可撤**：reorder 记 snap；`undo_reorder_…_customs`；菜单「撤销排序」；smoke `ttl_reorder_undo`。
- **冒烟**：`smoke-wave83-pinapplyall-histundoimport-dstttlpreset-abfallbackimp-jitterreorderundo-e2e`（另回归 wave82/81/80）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊿ · pin建议键候选菜单多选 · 试键撤栈导出/清空可撤 · DST撤清TTL · A/B回退记忆清/导出 · jitter自定义拖拽排序 · 2026-10-28】

- **pin 建议键候选菜单多选**：`show_…_cycle_key_suggest_menu`（勾选多项→应用首选/仅记录）；`…_suggest_selected`；resolve `action=menu`。
- **试键撤栈导出/清空可撤**：`export_…_confirm_undo` JSON；`clear/undo_clear_…_confirm_undo`；菜单 export/clear/undo_clear。
- **DST 撤清 TTL**：`get/set/prompt_…_clear_undo_ttl_ms`；`discard_…_clear_snap`；clear→schedule；undo_clear→停表。
- **A/B 回退记忆清/导出**：`clear_…_fallback(flow|all)`；`export_…_fallback` JSON。
- **jitter 自定义拖拽排序**：`reorder_…_customs`；`show_…_reorder_dialog`（QListWidget InternalMove）；菜单 `ttl_reorder`。
- **冒烟**：`smoke-wave82-pinsuggestmenu-histundoexport-dstttl-abfallbackio-jitterreorder-e2e`（另回归 wave81/80/79）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊾ · pin cycle冲突弹窗改键建议 · 试键撤销栈浏览/多级跳 · DST清栈可撤销 · A/B回退源记忆 · jitter自定义预设编辑/删 · 2026-10-28】

- **pin cycle 冲突弹窗改键建议**：`suggest_…_cycle_key`；`prompt_resolve_…_cycle_key_conflicts`（Yes→应用干净建议键）；`prompt_…_cycle_key` 冲突后自动弹建议。
- **试键撤销栈浏览/多级跳**：`list_…_confirm_undo_entries`；`jump_…_confirm_undo(index)`；旁标右击 `show_…_confirm_undo_menu`。
- **DST 清栈可撤销**：`clear_…` 快照；`undo_clear_…_apply_all_undo`；旁标中键撤清。
- **A/B 回退源记忆**：`remember/recall/load/persist_…_fallback`；autoload 无记忆时召回；失败仍记住。
- **jitter 自定义预设编辑/删**：`edit/delete/prompt_edit_…_ttl_preset_custom`；菜单 ✏/🗑；smoke `ttl_edit`/`ttl_delete`。
- **冒烟**：`smoke-wave81-pincyclesuggest-histundojump-dstclearundo-abfallbackmem-jitteredit-e2e`（另回归 wave80/79/78）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊽ · pin锁角标点击切换+cycle键冲突检测 · 试键撤销深度旁标 · DST深度长按清栈 · A/B载源失败回退提示 · jitter预设自定义/单项恢复动画 · 2026-10-28】

- **pin 锁角标点击切换 + cycle 键冲突检测**：角标左键 `toggle_…_lock`；`detect/format_…_cycle_key_conflicts`（保留键/钉加减/吸史/已有快捷）；`set_…_cycle_key` 记冲突并 toast。
- **试键撤销深度旁标**：`…_confirm_undo_depth` + `_refresh_…_depth_ui`；改键钮旁数字；点击撤销。
- **DST 深度长按清栈**：`clear_…_apply_all_undo`；旁标点击撤销、长按（~650ms）清栈。
- **A/B 载源失败回退提示**：`autoload` 无流程记忆→全局；异常→回退原源并 toast。
- **jitter 预设自定义 / 单项恢复动画**：`add/prompt_add_…_ttl_preset_custom`；菜单「自定义…」；`_animate_…_snapshot_restore` 旁标闪绿。
- **冒烟**：`smoke-wave80-pinlockclick-histundodepth-dstlongclear-abfallback-jittercustom-e2e`（另回归 wave79/78/77）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊼ · pin预览锁定态色标角标/快捷改键 · 吸史试键确认可撤销 · DST撤销栈深度旁标 · A/B流程切换自动载源 · jitter快照单项恢复/TTL预设档 · 2026-10-28】

- **pin 预览锁定态色标角标/快捷改键**：`…_lock_badge`「🔒」；`prompt_…_cycle_key`；菜单「改轮换键」；锁定时角标亮橙。
- **吸史试键确认可撤销**：`confirm_trial` 推 before；`undo_confirm_trial_…`；菜单「撤销试键确认(N)」。
- **DST 撤销栈深度旁标**：`…_apply_all_undo_depth` + `_refresh_…_depth_ui`；近旁数字；点击撤销。
- **A/B 流程切换自动载源**：`autoload_…_for_flow` / `switch_ab_trial_flow`；`set_toast_curve_png_project_name` 切名时自动载。
- **jitter 快照单项恢复/TTL 预设档**：`restore_…_snapshot(index)`；`list/apply_…_ttl_preset`（0/3/8/15/30/60s）；菜单可点单项+TTL子菜单。
- **冒烟**：`smoke-wave79-pinlockbadge-histundoconfirm-dstdepth-abautoload-jitterrestore-e2e`（另回归 wave78/77/76）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊻ · pin冲突色预览快捷键/右键锁定 · 吸史悬停tip进试键确认 · DST全应用撤销栈 · A/B试算源按流程记忆 · jitter TTL可配/旁标快照列表 · 2026-10-28】

- **pin 冲突色预览快捷键/右键锁定**：`…_conflict_preview_cycle_key`（默认 Ctrl+Shift+P）+ `_ensure_…_shortcut`；`lock/toggle_…_lock`；右键菜单模式+锁定；锁定时点击不轮换（force/快捷键可）。
- **吸史悬停 tip 进试键确认**：`confirm_trial_…_fix_candidate`；应用最近悬停 trial；菜单「确认悬停试键」。
- **DST 全应用后撤销栈**：`apply_all` 推 before；`undo_apply_all_…_recent`；菜单「撤销全应用」。
- **A/B 试算源按流程记忆**：`current_flow_key_for_ab_trial`；`load/persist_…_by_flow` + map；trial 同步写流程键。
- **jitter TTL 可配 / 旁标快照列表**：`prompt_…_ttl_ms`；`list/show_…_snapshot_menu`；旁标点击开列表、右键配 TTL。
- **冒烟**：`smoke-wave78-pinswlock-histconfirm-dstundostack-abflow-jitterttlcfg-e2e`（另回归 wave77/76/75）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊺ · pin色标点击切冲突色预览 · 吸史候选悬停试键tip · DST全应用/全清 · A/B试算源记忆持久 · jitter撤清深度旁标/超时丢快照 · 2026-10-28】

- **pin 色标点击切冲突色预览**：`cycle/set_…_undo_swatch_conflict_preview`；auto→conflict→clean→swap；色标/条点击轮换。
- **吸史候选悬停试键 tip**：`trial_tip_…_fix_candidate`；QAction.hovered；不改键；tip「试键 · 撤/重 · 干净」。
- **DST 多选全应用/全清**：`select_all/clear_selected/apply_all_selected_…_recent`；菜单全选·全清勾选·全应用勾选。
- **A/B 试算源记忆+持久**：`load/persist_…_source_trial`；QSettings；说明条恢复记源。
- **jitter 撤清深度旁标/超时丢快照**：`…_clear_undo_depth_ui`；`discard/ttl`；QTimer 到期自动丢；「撤清·N」+旁标。
- **冒烟**：`smoke-wave77-pinswatchmode-histhover-dstall-abpersist-jitterttl-e2e`（另回归 wave76/75/74）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊹ · pin撤销预览色标条 · 吸史改键候选菜单 · DST最近右键多选 · A/B说明条点源试算 · jitter清栈确认/撤销 · 2026-10-28】

- **pin 撤销预览色标条**：`preview_…_undo` 增 `swatch_current/restore` · `bar_css/bar_text`；`render/_refresh_…_undo_swatch`；对比条旁 ●⇒● 渐变色标。
- **吸史改键候选菜单**：`list_…_fix_candidates`；`show_…_fix_menu`（左点一键改键 / 右键候选）；smoke `no_exec` + `smoke_index`。
- **DST 最近右键多选**：`selected/set/toggle/apply/remove_…_recent`；右键菜单勾选·应用首条·移除勾选；`menu_no_exec` smoke。
- **A/B 说明条点源试算**：`trial_…_source_explain`；说明条点击轮换 team→local→clipboard→清；团/本/贴芯片；试算高亮。
- **jitter 清栈确认/撤销**：`clear_…_seed_redo(confirm=)` + QMessageBox；快照可 `undo_clear_…`；「撤清」按钮；`_no_confirm` smoke。
- **冒烟**：`smoke-wave76-pinswatch-histcands-dstmulti-abtrial-jitterundoclear-e2e`（另回归 wave75/74/73）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊸ · pin对比条撤销预览tip · 吸史冲突一键改键 · DST范围最近记忆 · A/B按来源说明条 · jitter深度右键清栈 · 2026-10-28】

- **pin 对比条撤销预览 tip**：`preview_…_avoid_compare_bar_undo`；窥栈顶将恢复键；tip「撤销预览 · 深N · 现→恢复」；属性 `UndoPreview`。
- **吸史冲突一键改键**：`suggest/fix_…_shortcut_conflict_fix`；候选 Ctrl+Alt+Z/Y…；「改键」按钮；冲突 tip 示建议键。
- **DST 范围最近记忆**：`list/remember/apply_…_year_range_recent`（≤5）；设定自动记；「近YYYY–YYYY」按钮点首条。
- **A/B 按来源策略说明条**：`render_…_import_conflict_source_explain`；冲突菜单顶说明条；source 时绿字+现源解析。
- **jitter 深度右键清栈**：`clear_…_seed_redo`；深度旁标/重种钮右击清栈；tip「右击清栈」。
- **冒烟**：`smoke-wave75-pinundoprev-histfix-dstrecent-abexplain-jitterclear-e2e`（另回归 wave74/73/72）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊷ · pin对比条应用撤销 · 吸史快捷冲突检测 · DST年范围对话框 · A/B冲突按来源 · jitter重种深度指示 · 2026-10-28】

- **pin 对比条应用撤销**：应用前压撤销栈（≤8）；`undo_…_avoid_compare_bar`；对比条左键应用 / 右键撤销；`undo_depth` tip/属性。
- **吸史快捷冲突检测**：`detect/format_…_order_shortcut_conflicts`；保留键/同键/钉上限碰撞；设定时 warn toast；「键…」tip/样式。
- **DST 年范围对话框**：`prompt_…_dst_calendar_year_range`；「范围…」按钮；年标签可点；`1990,2035` / `2010-2020`。
- **A/B 冲突策略默认按来源**：策略 `source`；`resolve_…_from_source`（team→rename / local→overwrite / clipboard→skip；payload.conflict 优先）；菜单「按来源」。
- **jitter 重种深度指示**：`_refresh_…_seed_redo_depth_ui`；「重种·N」文案+绿字；旁标深度；撤/重/重抽刷新。
- **冒烟**：`smoke-wave74-pinundocmp-histconflict-dstrange-absource-jitterdepth-e2e`（另回归 wave73/72/71）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊶ · pin对比条点击应用 · 吸史快捷自定义 · DST年范围/本月 · A/B导入冲突策略 · jitter撤种重做栈 · 2026-10-28】

- **pin 对比条点击一键应用**：`apply_…_avoid_compare_bar`；对比条可点（手型光标）；刷新色标/条。
- **吸史快捷键自定义**：`set/prompt/reset_…_order_shortcuts`；QSettings 持久化；「键…」按钮；`_ensure` 读自定义。
- **DST 年范围/本月跳回**：`set/get_…_year_range`（默认 1990–2035）；`jump_…_current_month`；「本月」按钮；年切换夹紧。
- **A/B 导入冲突策略**：overwrite/skip/rename；`import(…, conflict=)`；统计覆/跳/改；菜单冲突策略子项。
- **jitter 撤种重做栈**：撤种压重做；`redo_…_seed_reshuffle` +「重种」；新重抽清空重做。
- **冒烟**：`smoke-wave73-pinapply-histkeycfg-dsttoday-abconflict-jitterredo-e2e`（另回归 wave72/71/70）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊵ · pin避让色标对比条 · 吸史重序快捷键 · DST跳月年切换 · A/B自定义预设导出/导入 · jitter重抽历史栈 · 2026-10-28】

- **pin 避让色标对比条**：`render_…_key_avoid_compare_bar`；左当前/右建议渐变条；菜单旁对比条 tip。
- **吸史重序快捷键**：Ctrl+Shift+Z 撤序 / Ctrl+Shift+Y 重序；`_ensure_…_order_shortcuts`；按钮 tip+shortcut。
- **DST 跳月年切换**：`set/bump_…_dst_calendar_year`；◀ 年 ▶；刷新月芯片+聚焦。
- **A/B 自定义预设导出/导入**：`export/import_…_channel_preset_customs` JSON；剪贴板；菜单 ⇪/⇩；merge/replace。
- **jitter 重抽历史栈**：重抽压栈（≤16）；`undo_…_seed_reshuffle` +「撤种」。
- **冒烟**：`smoke-wave72-pincompare-histkeys-dstyear-abio-jitterhist-e2e`（另回归 wave71/70/69）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊴ · pin避让预览色标 · 吸史撤序重做 · DST日历点选跳月 · A/B预设自定义存档 · jitter种子一键重抽 · 2026-10-28】

- **pin 避让预览色标**：`preview/render_…_key_avoid`；当前橙(#e6a23c)/建议绿(#3ecf8e) 色标；「避」旁 ●→● swatch + tip。
- **吸史撤序重做**：撤销压重做栈（≤16）；`redo_…_reorder` +「重序」；新落序清空重做。
- **DST 日历点选跳月**：`jump_…_dst_calendar_month`；月芯片点击聚焦+描边；刷新日详情 tip。
- **A/B 预设自定义存档**：`save/list/delete_…_channel_preset_custom`；★ 菜单存/删；`u_` id；应用优先上次。
- **jitter 种子一键重抽**：`reshuffle_…_jitter_seed`（1–999999）；「重抽」同步旋钮+直方图。
- **冒烟**：`smoke-wave71-pinpreview-histredo-dstjump-abcustom-jitterreshuf-e2e`（另回归 wave70/69/68）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊳ · pin冲突一键避让 · 吸史拖影半透明/撤序 · DST日历hover日详情 · A/B通道预设快切 · jitter粘贴分布种子回写 · 2026-10-28】

- **pin 冲突一键避让**：`suggest/avoid_…_key_conflicts`；候选键对扫无冲突；菜单「避」+「一键避让」；无冲突则保持。
- **吸史拖影半透明+撤序**：幽灵 `windowOpacity=0.55`；落序压栈（≤16）；`undo_…_reorder` +「撤序」按钮。
- **DST 日历 hover 日详情**：`…_dst_day_detail` / `render_…`（日期/☀·标准/UTC偏移/段）；12 月芯片 tip+hover。
- **A/B 通道预设快切**：`both_full` / `a_only` / `b_only`；`apply/cycle_…_channel_preset`（自动切 both）；菜单 ⚡ 预设。
- **jitter 粘贴→分布种子回写**：paste 解析 `dist`/`seed`/`jitter_ms` → `set_…`；芯片/旋钮同步；toast 标明回写项。
- **冒烟**：`smoke-wave70-pinavoid-histundo-dsthover-abpreset-jitterwriteback-e2e`（另回归 wave69/68/67）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊲ · pin快捷冲突提示 · 吸史拖影/落点高亮 · PNG城市DST日历条 · A/B both分通道 · jitter分位剪贴板 · 2026-10-28】

- **pin 快捷冲突提示**：`detect/format_…_max_pin_key_conflicts`；同键 / 保留 Ctrl+C/V/Z… / 其他 QShortcut；改键 toast 警告；「键」按钮 tip+橙字。
- **吸史拖影/落点高亮**：拖拽中 ToolTip 色块幽灵跟随；落点 swatch 金边高亮；松手仍 `reorder`。
- **PNG 城市 DST 日历条**：`…_dst_calendar` / `render_…` 一年 ☀/· 月条 + 区间；模板对话框 DST 行+刷新；切城市联动。
- **A/B both 分通道**：`channels=['a_to_b','b_to_a']`；`effective_dirs` 门控 A/B setter；菜单「通道 A→B / B→A」仅 both 可勾。
- **jitter 分位剪贴板/粘贴回放**：`copy_…tsv|csv|text` → 剪贴板；`paste_…` 解析回放至预览；预览窗「复制分位 / 粘贴回放」。
- **冒烟**：`smoke-wave69-pinconflict-histghost-pngdstcal-abchannels-jitterclip-e2e`（另回归 wave68/67/66）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊱ · pin快捷可改键 · 历史色拖序 · PNG城市夏令时 · A/B镜像双向 · jitter分位表导出 · 2026-10-28】

- **pin 快捷可改键**：`set/reset/prompt_…_max_pin_keys`；默认 `Ctrl+[` / `Ctrl+]` 可改；菜单「键」；force 重建 `QShortcut`。
- **历史色拖序**：吸史色块 OpenHand 拖拽排序；`reorder/move_…_eyedropper_history`；点击仍应用、右键仍删。
- **PNG 城市夏令时标记**：预设带 IANA 区；`…_dst_active` / `…_utc_offset_hours`（DST 感知）；芯片名加 ☀（纽约/洛杉矶夏令中）。
- **A/B 镜像双向**：方向 `a_to_b` / `b_to_a` / `both`（A↔B）；锁定+镜像下双侧互同步；`_ab_mirror_applying` 防环；菜单标 A↔B。
- **jitter 分位表导出**：stats 含 p0…p100；`quantile_table` / `export_…csv|tsv`；预览窗「导出分位」+ 分位行。
- **冒烟**：`smoke-wave68-pinrebind-histreorder-pngdst-abboth-jitterquantile-e2e`（另回归 wave67/66/65）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊰ · pin上限键盘快捷 · 历史色右键删 · PNG城市TZ · A/B镜像方向 · jitter箱线均值 · 2026-10-28】

- **pin 上限键盘快捷**：`Ctrl+[` / `Ctrl+]` 与菜单 −/+；`bump_…_max_pin`；旋钮/角标联动。
- **历史色右键删单条**：吸史色块右键「删除」；`remove_…_eyedropper_history`；清全部仍可用。
- **PNG TZ 城市预设**：本机/UTC/北京/东京/迪拜/伦敦/纽约/洛杉矶；按本机 UTC 差换算相对偏移；手拧旋钮标 custom。
- **A/B 镜像 B→A 方向**：`a_to_b` / `b_to_a`；菜单「方向切换」；锁定+镜像按方向单向同步。
- **jitter 箱线图/均值线**：min/q1/med/q3/max + μ；预览窗箱线行；分布芯片切换同步刷新。
- **冒烟**：`smoke-wave67-maxpinhotkey-eyeremove-pngtzcity-abmirrordir-jitterbox-e2e`（另回归 wave66/65/64）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊯ · pin上限菜单旋钮 · 吸管历史色 · PNG时区偏移 · A/B锁定镜像 · jitter直方图 · 2026-10-28】

- **pin 上限菜单旋钮**：导引带最近色板菜单内嵌 `QSpinBox`（1–6）；空色板亦显示旋钮；改值即时挤出超额钉并刷新角标。
- **eyedropper 历史色**：≤12 持久化；hex 行下历史色块可点应用 / 清空；吸色自动入史（去重置顶）。
- **PNG 时区偏移**：`{datetime}` 相对本机 −12..+14h；命名对话框旋钮；`resolve`/`live strip` 走 `_toast_curve_png_datetime_when`。
- **A/B 锁定时同步镜像可选**：🪞 开关；锁定+镜像时改 A 同步 B；对调仍禁用；`_ab_mirror_applying` 防环。
- **jitter 直方图预览**：脉冲预览窗文本直方图（▁…█）+ 刷新；分布芯片切换即时重采样；jitter=0 显示「无抖动」。
- **冒烟**：`smoke-wave66-maxpinspin-eyehist-pngtz-abmirror-jitterhist-e2e`（另回归 wave65/64/63）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊮ · pin拖序+计数角标 · eyedropper mid/lo · PNG自定义strftime · A/B锁定 · 脉冲jitter分布/种子 · 2026-10-28】

- **pin 列表内拖序 + 计数角标**：`reorder_…_pinned`；钉住色块显示 `📌{序}`；「最近 · 📌n/cap」角标；钉内拖放同步 pinned 序。
- **eyedropper mid/lo**：自定义 hex 行「吸hi / 吸mid / 吸lo」三分吸；写入对应档并切 custom。
- **PNG 自定义 strftime**：「自定义…」芯片 + `prompt_…_custom_strftime`；校验后落盘；非预设标 is_custom。
- **热同步 A/B 锁定**：🔒 开关；锁定时禁用对调并 toast；QSettings 布尔稳健解析。
- **脉冲 jitter 分布/种子**：uniform / triangular / gauss；种子 0=系统随机、>0 可复现；预览窗芯片+旋钮。
- **冒烟**：`smoke-wave65-pinreorder-eyemidlo-pngcustom-ablock-jitterdist-e2e`（另回归 wave64/63/62）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊭ · 导引带pin徽章/上限 · 撤销条hex吸管 · PNG日期格式 · 热同步A↔B对调 · 脉冲gap抖动 · 2026-10-28】

- **导引带最近色板 pin badge + max-pin cap**：置顶色块显示 📌 + 金边；独立 pinned 列表；上限 1–6（默认 3）FIFO 挤出；右键已钉显示「取消置顶」。
- **撤销条色阶 hex eyedropper**：自定义 hex 行旁「吸管」；`QColorDialog` 拾色写 hi 并切 custom；smoke 可用 `_stale_prune_undo_eyedropper_no_dialog`。
- **PNG `{datetime}` format picker**：iso/compact/date/slash/cn 预设芯片；`resolve`/`live strip`/对话框预览按所选 strftime；文件名安全替换。
- **热同步 A↔B swap**：菜单「A ↔ B 对调」交换当前色阶与对比预设并重绘双条。
- **脉冲 gap random jitter**：0–500ms 抖动滑条；循环周期 = 脉冲 + gap + `randint(0,jitter)`；落盘。
- **冒烟**：`smoke-wave64-guidepinbadge-hexeye-pngdtfmt-abswap-gapjitter-e2e`（另回归 wave63/62/61）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊬ · 导引带色板右键clear/pin · 撤销条色阶hex · PNG{datetime}live · 热同步A/B · 脉冲gap芯片 · 2026-10-28】

- **导引带最近色板右键 clear/pin**：色块右键钉住到首位 / 清除此色 / 清空全部；`pin`/`remove` API。
- **撤销条色阶自定义 hex 入口**：菜单内嵌 hex 行 +「自定义 hex…」；支持 hi 或 hi,mid,lo；热同步菜单同步。
- **PNG `{datetime}` live preview strip**：命名展开 `{datetime}`；对话框实时预览条每秒刷新；「日期时间」预设。
- **热同步双条 A/B 对比**：A=当前色阶 / B=对比预设；B 侧勾选热刷。
- **脉冲 gap persist + preset chips**：0/120/300/500/1000 芯片；滑条与芯片双向同步并落盘。
- **冒烟**：`smoke-wave63-guideclearpin-undohex-pngdatetime-hotsyncab-pulsegapchips-e2e`（另回归 wave62/61/60）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊫ · 导引带色板拖拽排序 · 撤销条色阶嵌预览 · PNG工程自动填 · 热同步勾选即时刷新 · 脉冲循环间隔 · 2026-10-28】

- **导引带最近色板拖拽排序**：色块可拖拽重排；`reorder`/`move` API 落盘；单击仍应用自定义色。
- **撤销条色阶菜单嵌预览小条**：仅选删色撤销条右键菜单顶部嵌色阶预览条；切预设同步重绘。
- **PNG 模板工程名自动填**：打开模板对话框/`sync_toast_curve_png_project_from_current` 从当前工程名填 `{project}`；「从工程」按钮。
- **热同步点选后菜单勾选即时刷新**：预览条点选后强制核对勾选态 + `processEvents`。
- **脉冲循环间隔可调**：0–2000ms 滑条；循环周期 = 脉冲时长 + 间隔。
- **冒烟**：`smoke-wave62-guidereorder-undoprevbar-pngautofill-hotsyncrefresh-pulsegap-e2e`（另回归 wave61/60/59）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊪ · 导引带最近色板 · 撤销条色阶切换入口 · PNG项目/工位变量 · 热同步预览条点选 · 脉冲循环播放 · 2026-10-28】

- **导引带最近色板记忆**：自定义色推入最近色板（最多 6）；菜单内嵌色块快捷 + 清空。
- **撤销条色阶预设切换入口**：仅选删色撤销条右键时长菜单追加色阶五项（红绿灯/冷色/琥珀/日落/自定义）。
- **PNG 模板变量更多**：`{project}` / `{station}`；对话框可编辑项目/工位；快捷「项目」「工位」预设。
- **热同步预览条可点选预设**：预览条按 X 五等分点选色阶；refresh 同步勾选态。
- **脉冲预览可循环播放**：预览窗勾选「循环播放」；定时按时长+缓冲再播；关闭停表。
- **冒烟**：`smoke-wave61-guiderecent-undoscaleentry-pngprojsta-hotsyncclick-pulseloop-e2e`（另回归 wave60/59/58）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

## 【细妆㊩ · 导引带α连续滑条 · 撤销条色阶对齐 · PNG模板编辑对话框 · 热同步色阶预览条 · 脉冲预览小窗 · 2026-10-28】

- **导引带 α 连续滑条**：透明度 4–40% 连续可调；8/12/20 仍为快捷；菜单内嵌 `QSlider`。
- **撤销条色阶对齐**：仅选删色撤销条 chunk 走 `_stale_prune_undo_bar_chunk_color`（绿→黄→红 / 当前色阶预设）。
- **PNG 模板编辑对话框**：`show_toast_curve_png_name_template_dialog`；实时预览 + 默认/日期/简名快捷；最近导出菜单入口。
- **热同步色阶预览条**：菜单顶栏渐变预览条；`refresh` 随预设重绘。
- **脉冲预览小窗**：`show_merge_diff_fail_hist_drop_pulse_preview` 演示当前时长/缓动/强度；导引带菜单入口。
- **冒烟**：`smoke-wave60-guidealphaslider-undoscale-pngtmpldlg-hotsyncpreview-pulseprev-e2e`（另回归 wave59/58/57）。
- **边界**：无 push；不碰 Halcon / 真机云 / 机械手 SDK；不碰 `:18280`；`?? os` 独留。

---

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

