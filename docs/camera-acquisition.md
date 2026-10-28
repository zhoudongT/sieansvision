## wave156 软控 + 设备选择 + 整屏适配

- Soft/UVC：**曝光 / 增益 / 触发**软控（UVC 尝试 CAP_PROP；Soft 在预览帧仿真）
- 多设备 picker 富标签；**last-device** JSON 持久化；UVC/GenTL 会话 reconnect 韧性标志
- 相机管理对话框 `setMinimumSize(640,420)` + splitter stretch
- 主窗 `setMinimumSize(1024,640)` + `apply_responsive_layout`；运行态预览 minH 下调适配 720p
- 冒烟：`python3 scripts/smoke-wave156-tcp-camera-adapt-e2e.py`（1280×720 / 1600×900 / 1920×1080 / 1280×1024）

## wave154 UVC 实采连续 live + GenTL Producer 开流

在 wave153 可插拔壳之上：

| 能力 | 实现 | 无硬件 / CI |
|------|------|-------------|
| UVC 实采 | `UvcLiveSession`：`VideoCapture` **打开一次**，`grab_many` 连续取帧 → PNG → `PreviewFrameGate` / `show_live_frame` | 无设备时 Soft 回退（不假装 UVC） |
| GenTL 开流 | `discover_gentl_ctis`（`SIEANS_GENTL_CTI` + Hikrobot `/opt/MVS` 自动发现）→ `gentl_load_producer` → `gentl_enumerate_devices` → `GentlLiveSession` 开流 grab | Producer 在但无相机 → **空设备列表**，grab 拒绝假帧 |
| 对话框 | 相机管理 / 设备工作台 Soft \| UVC \| GenTL 均可走同一 live 预览路径 | Soft 始终可预览 |

启动脚本 `scripts/launch-sieans-vision.sh` 默认设置：

```sh
export SIEANS_GENTL_CTI=/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti
export MVCAM_COMMON_RUNENV=/opt/MVS/lib
export LD_LIBRARY_PATH=/opt/MVS/lib/64:$LD_LIBRARY_PATH
```

冒烟：`python3 scripts/smoke-wave154-uvc-gentl-live-e2e.py`（不要求物理相机；有 UVC/海康时额外走实采断言）。

本波**不含** TCP 产品化、Halcon/CLR、机器人 SDK、云。

---

## wave153 真机路径（Soft / UVC / GenTL 壳）

桌面端新增可插拔后端 `desktop/camera_backends.py`：

| 后端 | 驱动 | 无硬件行为 | 持久会话 |
|------|------|------------|----------|
| Soft | simulator | 始终可用 | 是（模拟） |
| USB UVC | uvc / OpenCV VideoCapture | 枚举空则 Soft 回退（CI-safe） | **是**（打开后跨帧保持，不每 grab 开关） |
| GenTL / GigE | gentl | 无 CTI/harvesters → `not_loaded`/`unsupported`，不假帧 | 是（Producer 就绪后） |

操作：相机管理 →「采集后端」选 Soft/UVC/GenTL → 刷新枚举 → 连接相机 → 预览（`PreviewFrameGate`）。
图像源「相机」页同步有采集后端下拉。完整工作台驱动下拉仍含 RealSense/Orbbec（本波不扩）。

# 相机采集：USB UVC / GenTL

## 海康 USB 实机兼容修复（2026-10-23）

Windows 11 x64、MVS 4.5.1 / SDK Runtime 4.6.1.103、海康 **MV-CB013-A0UM-C** 已通过本平台后台的 GenTL 取图：1280 × 1024、Mono8，三次独立单帧取图、五次连续新帧读取，以及“相机→几何检测→流程变量”实际执行和停止释放。测试图像只用于采集链路验证，不作为检测精度依据；其他型号、GigE、外部触发和 Linux 仍需各自实测。

该版本海康 CTI 的部分错误描述含非 UTF-8 字节，使 GenICam 将原始状态转换为 UnicodeDecodeError。`cameras/gentl_compat.py` 在 Windows 的 MvProducerU3V/MvProducerGEV 连接期间，仅为已识别的可选 URL 查询、事件注册和取帧轮询恢复对应 GenTL 异常类型，让 Harvesters 继续使用原有处理和超时逻辑。未知错误仍抛出，退出时还原兼容钩子；不修改已安装的 SDK 或 Python 包。

此相机只公布 FrameBurstStart 触发选择项。自由采集关闭该触发即可，不再强制写入不存在的 FrameStart；软件/外部突发触发尚未适配，选择时明确报错，不将一次突发当作单帧触发。连续 worker 在启动停止监听线程之前加载 Harvesters，避免本机 Windows 环境下首次导入的子进程阻塞。

启动服务前配置本机实际 CTI 路径，例如：

```powershell
$env:SIEANS_GENTL_CTI = 'C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvProducerU3V.cti;C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvProducerGEV.cti'
npm start
```

网页“相机设备”选择 GenTL → MvProducerU3V.cti → 枚举 → 选择实际相机 → 预览采集 / 添加采集节点，触发模式用“自由采集”。连续使用见下文链接。上述环境变量只在当前终端及其子进程生效；现有部署使用相同环境启动其原部署命令，服务方式需向对应服务传递变量。

已增加 [连续相机连接与帧缓存](camera-session.md)：SDK 连接/预热跨帧复用，提供下一帧/缓存取图、过期检查、统计及明确停止。下文单帧接口仍保持采集后释放。

RealSense RGB-D、原始 16 位深度和点云通道另见 [深度相机说明](depth-camera.md)。

本轮实现的是服务器端单帧采集：打开设备 → 应用本节点配置 → 获取图像 → 释放设备。采集节点输出新的图像，后续预处理、识别、测量、脚本及变量节点可直接使用。浏览器只操作服务器上的相机，不调用浏览器摄像头权限。

## 开源依赖与驱动条件

| 组件 | 固定版本 | 用途 |
|---|---|---|
| [OpenCV](https://github.com/opencv/opencv) | 与 vision/requirements.txt 一致 | Windows DirectShow / Linux V4L2 USB 视频采集、像素转换及 PNG 编码 |
| [cv2-enumerate-cameras](https://github.com/lukehugh/cv2_enumerate_cameras) | 1.4.0，MIT | 从系统枚举设备名称、设备路径及对应 OpenCV 索引，不逐台打开试拍 |
| [Harvesters](https://github.com/genicam/harvesters) | 1.4.3，Apache-2.0 | 加载厂商 GenTL Producer，枚举与选择设备、访问 GenICam 参数、获取及归还缓冲区 |
| GenICam Python binding | 1.6.0，发行包标注 LicenseRef-GenICam-1.6 | GenApi / GenTL 本地运行库；许可证和附带组件声明保存在 third_party/genicam |

安装已有视觉依赖后执行：

```sh
python -m pip install -r cameras/requirements.txt
```

Windows 使用 `.venv/Scripts/python.exe`，Linux 使用 `.venv/bin/python`。Python、厂商 SDK 和 CTI 必须匹配系统及位数。第三方声明已复制到 `third_party/harvesters`、`third_party/cv2-enumerate-cameras`、`third_party/genicam`。厂商 SDK/CTI 不随项目分发，部署前按其许可证与支持矩阵检查。

工业 USB 相机通常不是 UVC 摄像头。海康、大华/华睿等型号是否可通过此适配器连接，取决于该型号、固件和厂商 Producer 对 GenTL 的支持；不能用“支持 GenTL”替代型号实测。没有兼容 CTI 的设备需要后续厂商 SDK 适配器。

## 配置 GenTL

由服务器维护者配置已安装且可信的 CTI 文件。工作台只选择服务器公开的驱动编号，不接受客户端任意原生库路径。

PowerShell 示例（替换为真实安装路径）：

```powershell
$env:SIEANS_GENTL_CTI = 'C:\VendorSDK\Producer.cti'
npm start
```

Linux 示例：

```sh
export SIEANS_GENTL_CTI='/opt/vendor/lib/Producer.cti'
npm start
```

多个路径用操作系统路径分隔符分隔：Windows `;`，Linux `:`。厂商要求的动态库搜索路径、网卡配置、USB 权限、驱动安装由服务器部署完成。修改环境变量后重启服务。路径不存在的 Producer 会在设备面板标记，不自动下载安装 SDK。

## 工作台操作

1. 打开“相机设备”，选择 USB UVC、GenTL 或模拟零件相机，点击“枚举设备”。
2. 设备表显示名称、稳定标识、型号、序列号与接口。选择设备后，可“读取设备参数”或“采集一帧预览”。参数读取只读，可能短暂占用设备；预览使用自由采集，不采用现有节点的曝光/触发配置。
3. 点击“添加采集节点”，或对现有采集模块选择“配置到所选采集节点”。同驱动更换设备保留现有可选采集设置；更换驱动清理不兼容参数。新增节点接在当前选择节点后，可自由调整连线。
4. 在节点表单里填写尺寸、超时、触发等参数，连接采集节点 → 检测节点 → 变量或通信节点。采集节点的上游连线用于启动顺序，不需要预先上传图像。
5. 使用“演示案例 → 采集 → 相机采集 → 检测 → 变量”验证模拟链路。结果为 640 × 400、3 个轮廓、`cameraCount=3`，明确标记模拟。

选中下游视觉节点后，“输入图像”按其上游来源展示上次运行图像，可直接框选 ROI 或裁切定位模板。该预览不会覆盖上传图像或改变其他分支的输入；新一轮运行会重新采集。

所有设备参数、采集元数据和结果均以表格/表单展示。后台工程和接口仍使用结构化数据。

## 行为约定

- USB 按所选系统设备路径重新枚举并解析索引，避免仅保存易变索引。设备拔插、驱动切换或标识变化后重新选择；枚举与打开之间的硬件变化仍需现场验证。支持宽、高、帧率和 0–30 帧预热；空白设置沿用驱动当前值。设置被拒绝或回读不匹配会失败，不假装成功。曝光/增益的 OpenCV 单位在不同驱动间不一致，当前 UVC 不设置它们。
- GenTL 按明确的 Producer 和设备 `id_` 唯一选择。要求标准 `AcquisitionMode=Continuous`、`TriggerSelector=FrameStart` 和相应触发节点；不满足的设备会返回配置错误。支持自由采集、一次软件触发、等待 Line0–Line3 外部触发。读取的参数表可检查设备实际能力。触发和相机参数修改是外部动作，不随流程变量事务回滚，也不自动重试。
- 可选宽高、PixelFormat、ExposureTime（µs）、Gain 使用 SFNC 节点名。设置曝光/增益时先关闭对应 Auto 节点；没有这些标准节点的型号可能需要厂商适配。不会写 UserSetSave 等持久化命令，但设备当前参数可能留存。
- 2D 模式支持 Mono8、非打包 Mono10/12/16、RGB8/BGR8/RGBA8/BGRA8、BayerRG8/BG8/GR8/GB8。缓冲区在归还前复制，拒绝不完整帧、错误长度或类型、未知/打包格式和多分量帧。多分量点云应显式选择下文的 3D 模式。
- 当前 2D 管线使用 8 位图像。10/12/16 位灰度按固定位深右移为 8 位，输出原始位深、输出位深及转换说明；不宣称保留高位深测量精度。
- 输出 PNG 不超过 12 MB、图像不超过 1600 万像素。新采集图像清空上游旧点云，防止不同时间的 2D/3D 数据混用。模块结果含设备、主机收到帧的 UTC 时间、可用的设备纳秒时间戳（文本，避免整数精度损失）、格式与参数回读。
- 每次操作使用独立 Python 子进程；外层总时限为 `timeoutMs + 2000 ms`（含启动/清理预算），GenTL fetch 另有 `timeoutMs` 时限。取消或原生 SDK 卡死时终止进程；普通完成/异常通过 finally 归还缓冲区并释放设备。强制终止后的设备恢复行为须实测。
- 当前同一服务器进程保守串行化所有实体相机操作，模拟操作另有独占锁。多服务实例/外部厂商软件的竞争由驱动处理；暂不支持多相机同步、长连接、连续视频、硬触发循环或自动重连。

## API 与 Node-RED

`POST /api/vision/cameras/run`：操作 `camera_providers` / `camera_list` / `camera_inspect` / `camera_capture`，参数由工作台表单生成。返回的图像放在 `annotatedImage`，元数据放在 `result`。沿用现有工作台管理员认证；客户端取消请求会取消所属采集子进程。

Node-RED 节点 `machine-camera_capture` 提供条件显示的字段表单。输出 `msg.image`（PNG），`msg.camera` 和 `msg.payload`（元数据）；2D 采集清除旧 `msg.cloud` 和 `msg.depth`；深度设备更新两者，见 [深度相机说明](depth-camera.md)。`msg.cameraParams` 可覆盖配置。连到 `machine-geometry` 等现有视觉节点即可处理。错误交给 Catch；节点关闭会取消采集。设备 ID/驱动 ID 可从工作台选好设备后的模块参数表复制。

## 验证范围与剩余工作

`npm run test:cameras` 包含 9 项 Python 测试、5 项运行时测试及 HTTP / Node-RED 集成：颜色顺序、Bayer、位深缩放、复制缓冲区、异常/超时释放、参数回读、设备锁、取消、失败回滚、新图像下游传递、旧点云清理和项目保存。GenTL/UVC 生命周期测试使用替身，模拟采集通过真实 OpenCV 生成 PNG，再通过真实检测引擎计算；不是硬件采集验收。

本机 Windows 已通过系统枚举发现 HP Wide Vision HD Camera，未采集其图像。尚无厂商 CTI/工业相机或 Linux 实机采集证据。RealSense、Orbbec 和 GenTL 3D 已有软件适配，实机接入、其他厂商专用 SDK、连续运行与同步、断线恢复和现场精度仍属于完整平台目标的待完成项。

浏览器联调另验证了：模拟设备枚举/参数表/单帧预览；640 × 400 采集图上拖拽 ROI 后，检测结果从 3 个变为 1 个，流程变量同步变为 1，清除 ROI 后恢复 3。

## GenTL 标定点云与多分量采集

工作台及 Node-RED 的“采集驱动 → GenTL → GenTL 输出 → 3D 标定点云”提供功能表单。后台仍使用同一采集接口；原有工程默认 2D，不自动把灰度帧解释成深度。

新增实现 `cameras/gentl3d.py` 沿用固定版本 Harvesters 1.4.3 / GenICam 1.6.0，无新运行依赖。参考 [Harvesters GitHub](https://github.com/genicam/harvesters)、[Photoneo 官方多分量示例](https://github.com/photoneo-3d/photoneo-python-examples/blob/main/GigE-V/harvesters/basic/connect_and_grab.py)、[Basler Harvester 指南](https://docs.baslerweb.com/python-prog-guide) 和 [GenICam SFNC 2.3](https://www.emva.org/wp-content/uploads/GenICam_SFNC_2_3.pdf)。没有复制厂商示例代码，也没有打包厂商 CTI；参考并不表示这些厂商的所有型号已验证兼容。

设备契约：Range 必须是 `CalibratedABC_Grid`、`Cartesian`，支持交错/单分量平面式 `Coord3D_ABC32f`、`Coord3D_ABC32f_Planar`，以及当前工作源码新增的无符号 16 位 `Coord3D_ABC16`、`Coord3D_ABC16_Planar`。读取 SFNC 的 `Millimeter` / `Inch` 单位、各 A/B/C 轴 scale/offset、无效值标记，转换为毫米。无效标记在换算前逐轴检查；不把合法的零坐标或负坐标统一删除。非有限坐标一律剔除。Anchor / Transformed 参考系随结果保留；Transformed 读取六个变换参数用于标识坐标系，不重复施加设备已完成的变换。元数据缺失、不支持的坐标制/输出模式/格式直接失败，不猜比例或标定。

“配置 Range 为标定 XYZ”默认启用，选择 Range、启用它、配置输出模式和格式，并逐项回读。关闭该选项保留现有 Range 模式/格式但仍校验。存在可用 GenDC 开关时关闭 GenDC，因为当前 Harvesters 不支持该流格式。读取各轴前切换坐标选择器，结束恢复原选择器；设备仍停留在 Range 分量。原有 FrameStart / Continuous / 触发节点要求不变。设备设置不会事务回滚，也不加载/保存 UserSet。

| 表单字段 | 语义 |
|---|---|
| XYZ 分量索引 | 从 0 起；-1 自动寻找唯一匹配格式，多个匹配时要求明确选择 |
| 亮度分量索引 | -1 关闭；支持 Mono8 / Mono16；Mono16 固定右移 8 位用于预览和灰度点云颜色 |
| 置信度分量索引 | -1 关闭；支持 Confidence8 / Confidence16，或用户明确选择的 Mono8 / Mono16 |
| 置信度最低原始值 | 1–65535；按设备原始编码比较，超过分量位深报错，不假设 0–1 概率 |
| 所选分量与 XYZ 逐像素对应 | 亮度/置信度启用时必须确认；仅检查尺寸和格式不能证明几何对齐 |
| 点云采样步长 | 在原栅格上等步长采样，1–64；输出最多 20 万点，超限要求增大步长 |

亮度和置信度分量先通过厂商设备工具启用，再按该型号文档确认顺序及栅格对应。当前表单不自动打开这些附加分量。分量索引不得重复；不依赖通用固定顺序，不把任意 Mono16 自动当作置信度。收到的分量列表、尺寸、实际索引及筛选数量输出为结果表。

3D 输出为 `cloud`（毫米坐标，源相机/坐标参考标识）及预览图。未选亮度时生成 Z 坐标伪彩预览，记录毫米色标范围；此图不是传感器原始深度，`depth` 为 null，旧深度被清除。XYZ 原始栅格上限 400 万点；无有效采样点则失败，不制造零点或空测量结果。选中同一设备和驱动的已有 3D 节点时，设备面板的单帧预览沿用其 3D 分量配置，但仍使用自由采集和默认超时。

`npm run test:gentl3d` 验证：真实 Harvesters PFNC 代码解码合成缓冲区；交错/平面式一致性、单位和负轴、无效点、灰度/置信度映射、格式与尺寸错误、点数预算、参数回读/选择器恢复、释放与超时；并将解码结果送入真实 Open3D、Python、固定类型流程变量及全局/模块绑定。缺失 CTI 通过实际子进程失败并回滚变量。软件帧、设备替身与实际硬件验收是不同证据。

尚未验证真实 CTI/相机及 Linux；暂不处理分离 A/B/C 的三个 payload parts、其余整数及打包坐标格式、投影/视差深度、非规则/无组织点集、线扫编码器、厂商私有拓扑、硬件同步或持续事件。以上需继续添加适配与实机验收，不能宣称覆盖全部工业 3D 相机。已有封存的 0.1.0 源码发布包不包含本次新增内容。

2026-10-16：候选 4 独立安装目录的实际 UVC 枚举成功返回本机 HP Wide Vision HD Camera，回执为 `artifacts/candidate-4-uvc-enumeration.json`。本次仅读取设备元数据，没有打开采集流或保存图像，不代表工业相机、深度相机或实际成像采集已验收。


## 16 位整数 XYZ 扩展（候选 5 之后的源码）

工作台和 Node-RED 的 XYZ 格式下拉框增加 `Coord3D_ABC16` 与 `Coord3D_ABC16_Planar`；原默认仍为 32 位浮点，原工程不改写。格式名称/编码见 [EMVA PFNC 官方表](https://www.emva.org/wp-content/uploads/GenICamPixelFormatValues.pdf)，解码使用已安装 Harvesters 1.4.3 的真实 Component2DImage / PFNC 实现，上游参考 [Harvesters 源码](https://github.com/genicam/harvesters/blob/master/src/harvesters/util/pfnc.py)。不新增依赖或打包厂商 CTI。

16 位格式接受 Harvesters 解码后的 uint16 栅格，先按原始 A/B/C 数值排除无效标记，再按各轴 scale/offset 和设备单位转换为毫米 float64 点云。合法的原始零值、65534 和转换后负坐标不会统一删除。启用了无效值标记时，设备声明必须是 0–65535 内可表示的整数；负值、小数、非有限值及空标记拒绝，不把 -1 猜成 65535。缓冲区的有符号/浮点类型、类型与实际声明不符或长度错误均拒绝。

源位深按坐标编码报告 16 或 32，不把 Z 伪彩预览当作原始深度文件。分量对应、置信度、采样点数限制、坐标系标识和释放/超时规则沿用原契约。现有“保留 Range 配置”模式可读取已配置的 16 位 Range，不强制改回浮点。

`npm run test:gentl3d` 覆盖真实 PFNC 库解码的交错/平面整数缓冲区、与已知浮点几何结果一致、毫米/英寸和负坐标、无效码/错类型拒绝、选择器恢复、SDK 替身释放及 uint16 点云进入实际 Open3D、Python 和模块/流程/全局变量。这里没有连接真实相机；厂商 Producer、设备固件及系统平台的实机兼容性仍待验。冻结候选 5 不包含此扩展，当前预览未重启。
