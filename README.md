# SIEANS Vision

仓库包含平台源码、算子插件、演示素材、测试和部署脚本。依赖、模型权重、账号与工程运行数据需在部署时安装或创建。下文 localhost 地址仅指开发机预览服务。

当前工作源码预览：[1920 工程副本](http://127.0.0.1:1920/vision/)。原 1919 服务保留，副本不自动同步原工程、账号或运行数据，见 [预览说明](docs/current-preview.md)。

最新已独立验收的开发候选为 **0.3.0-dev / candidate 8**，候选包与验收回执保存在开发机的 artifacts/releases 目录，不随 Git 源码提交；源码打包入口为 `deploy/build_release.py`。它纳入逐单元格绑定、完整检测链、运行画面，以及浏览器复核后修正的卡片高度、中文状态和无符号距离表头。

候选 8 是需要联网安装依赖的源码包，独立 Windows 安装、21 项运行检查、38 项 Node 与 19 项 Python 新功能测试及部署验收通过。2D/3D 的限定浏览器复核与六个关键文件关联校验通过，不代表所有编辑器和算子的完整视觉验收。现场设备、Linux、局域网和耐久仍待验。当前 [1930 独立测试实例](http://127.0.0.1:1930/vision/) 运行工作源码；1919/1920 原实例保留。旧候选包保持冻结。

开发预览新增 [账号与操作记录](docs/accounts-operations.md) 及 [操作员连续检测](docs/operator-continuous.md)，采用表单配置和表格展示。

开发预览新增 [运行画面 3D 点云组件](docs/hmi-cloud.md)：绑定检测点云、拖动旋转/平移、缩放及视角复位，预览抽样与计算数据分离，支持操作员发布画面。验证：`npm run test:cloud-widget`。

开发预览新增 [管理员发布与操作员运行](docs/operator-access.md)：固定已保存方案快照、操作员独立 HMI、组件级设定值校验与后台权限隔离。管理员维护工程和设备，操作员只运行发布方案。验证：`npm run test:operator-access`。

开发预览新增 [倾斜基准高度与可见体积](operator-plugins/sieans-heightfield/README.md)：独立基准点表、沿法向网格积分、正/负/净体积、缺测和层叠诊断，含五个演示及数值/表格运行画面。验证：`npm run test:heightfield`。

开发预览新增 [多目标模板定位与定位跟随](operator-plugins/sieans-fixture/README.md)：旋转/缩放候选去重、目标表、唯一目标分支、点位转换及图像校正后检测，含五个演示。验证：`npm run test:fixture`。

开发预览新增 [圆孔与双圆测量](operator-plugins/sieans-circle/README.md)：圆形卡尺、圆心/直径、公差及双圆中心偏移/理想壁厚，包含七个演示和表格式运行画面。验证：`npm run test:circle`。

开发预览新增 [流程记录整理与采样](operator-plugins/sieans-records/README.md)：七个数据算子、HMI 记录表及条件采样接手眼，无需自定义脚本。

开发预览 **0.3.0-dev** 新增 [眼在手上标定与独立验证](operator-plugins/sieans-handeye/README.md)。该新增功能尚未打入下面的 0.2.0 安装包。

当前源码安装版：**0.2.0**。功能、安装与验证范围见 [版本说明](docs/release-0.2.0.md)。

新增 [3D 对应点标定与坐标转换](operator-plugins/sieans-rigid/README.md)：点位表、独立验证、正反向点位/点云转换及模拟 Modbus 演示。验证：`npm run test:rigid`。

新增 [连续相机连接与帧缓存](docs/camera-session.md)：复用工业/深度相机 SDK 连接，支持等待新帧、缓存过期检查、停止释放和模拟检测演示。验证：`npm run test:camera-session`。

新增 [相机内参与畸变校正插件](operator-plugins/sieans-intrinsics/README.md)：角点表采集、标定变量绑定、校正图下游处理及三个演示。验证：`npm run test:intrinsics`。

当前可运行原型：嵌入 Node-RED，提供视觉算子工作台、自由连线流程、插件和网页运行画面。已实现 2D、ZXing、OCR、YOLOv8 / YOLO11 检测，Python 脚本、三级变量，以及 Open3D 点云导入、交互预览、滤波/分割/聚类/测量/高度体积估计/配准。工业通信已实现 Modbus TCP/RTU、经典 S7 读写、OPC UA 浏览/读写及 MQTT 发布/限时接收适配；USB UVC / GenTL / RealSense / Orbbec 单帧采集适配器已加入；运行画面支持网格拖动与属性表单。其他深度/体积相机、其余协议、现场硬件验证和离线安装器尚待完成。

流程已增加条件判断、互斥分支汇合和可取消延时，参数与连线规则使用表单配置，见 [流程控制说明](docs/flow-control.md)。

三级变量支持可选固定类型：在变量管理表格中定义整数、数值、文本、开关和同类型数组等；变量节点、Python、插件绑定与 HMI 写值均由服务器校验。类型错误会停止后续节点并回滚本轮变量，详见 [变量类型说明](docs/variable-types.md)。

工具栏“事件触发”提供 [MQTT 持续订阅与消息触发](docs/mqtt-trigger.md)：服务器长期接收、断线重连、有界消息队列、业务字段去重及逐条完整工程执行，接收对象在该轮事务内写入流程变量。配置为表单，统计和消息为表格；关闭浏览器后继续运行，另一客户端可查看与停止。失败停止且不自动重放设备动作。

独立 Python 算子插件现已支持清单发现、版本检查、启停、自动参数表单和三级变量输出绑定；包含亮度检测和点云质心示例，见 [插件开发与安装](docs/operator-plugins.md)。

Node-RED 新增通用“扩展算子”节点，可直接选择已安装插件，使用参数表单/点位表及上游消息字段绑定；支持图像、点云和深度通道，见 [Node-RED 插件桥接](docs/node-red-operator-bridge.md)。

新增 HSV 色彩区域、灰度斑点分析、3D 平面偏差检测三个插件算子，支持区域/公差表单、明细表格和变量绑定；“演示案例”提供红色筛选、掩膜串联及凸起/凹陷检测。

平面透视标定与坐标/长度测量插件已加入，支持点位对应表、RANSAC 异常点剔除、标定变量绑定及分段/周长结果表。“测量”演示包括 60 mm 线段、180 mm 周长及错误对应点剔除，详见 [平面标定插件](operator-plugins/sieans-planar/README.md)。

新增 [2D 卡尺](operator-plugins/sieans-caliper/README.md) 与 [3D 球面检测](operator-plugins/sieans-sphere/README.md)：支持亚像素直线/宽度、球心/直径、径向偏差、公差与无效输入诊断。球面插件需安装 `vision/requirements-3d.txt` 中的 SciPy；演示、参数和结果均通过表单/表格使用。

新增 [3D 圆柱检测](operator-plugins/sieans-cylinder/README.md)：自由轴线拟合、直径公差与侧面径向偏差，支持模型变量传递、点位明细与红绿点云；提供五个合成演示。

完整功能、安装与插件接口见 [视觉平台说明](docs/vision-platform.md)。

0.3.0 开发源码提供 [运行数据备份与恢复](docs/data-backup.md)：停止服务后校验备份工程、变量、历史、训练数据、隐藏凭据及独立模型，恢复到新目录并调整部署路径。验证：`npm run test:backup`。

3D 法向与坡度插件已加入，参数表单控制邻域、参考方向和公差，结果表格显示法向、坡度、局部拟合残差以及无效原因；提供 30° 斜面合格、超差和邻域不足演示，详见 [局部表面检测](operator-plugins/sieans-normals/README.md)。

“画面组态”支持文本、数值、指示灯、图像、结果表格、运行/停止/切页按钮、变量输入、报警和趋势。组件通过表单绑定变量和模块结果，布局随工程保存，运行模式按布局显示；支持多页面及后台监控。操作及限制见 [运行画面组态](docs/hmi-editor.md) 和 [多页面说明](docs/hmi-pages.md)。

“连续检测”支持服务器按轮次间隔执行完整工程、有限次数或运行到停止；浏览器刷新后可重新接管，异常停止后续轮次。设置和统计均使用表单/表格，详见 [连续检测](docs/continuous-runtime.md)。

“运行历史”按工程、状态和时间筛选已结束的工作台运行；只读明细包含本次参数、脚本、结果、日志及变量快照，工程选项可保留输入/输出图像、深度和点云。记录持久化，默认保留最近 200 条、有效明细共 256 MiB；单条上限 50 MiB。归档失败会提示，连续检测停止后续轮次，已提交变量保留。使用方式和范围见 [运行历史归档](docs/continuous-runtime.md#运行历史归档)。

3D 安装与数据格式见 [点云算子说明](docs/cloud-operators.md)。使用“演示案例 → 3D”运行五种合成数据示例。点云文件和现场相机接入是不同能力，当前尚无实际工业/深度相机验证。

工业通信已加入 Modbus TCP/RTU、OPC UA 浏览/读写、节点浏览器、证书加密认证，以及经典西门子 S7 数值/数组/单个位读写。三类协议均有本机模拟器及检测结果写入/读回绑定变量演示，见 [工业通信说明](docs/industrial-communication.md)。`npm run test:s7` 验证 S7 适配、流程和 HTTP/Node-RED 链路；其余协议及实际 PLC/RTU 验收仍待完成。

MQTT 已加入发布和限时接收流程块，支持 QoS 0/1/2、保留消息、UTF-8 文本/结构化数据/字节数组、TLS 与客户端证书。使用表单配置，检测结果可经本机 Aedes 服务器收发后写入三级变量；Node-RED 有对应节点。`npm run test:mqtt` 验证真实协议、认证、TLS、运行时和 HTTP/Node-RED 链路；长期订阅与设备事件触发尚待实现。

相机适配器支持服务器设备枚举、参数读取、单帧采集节点和模拟演示，见 [相机采集说明](docs/camera-acquisition.md)。GenTL 需厂商 CTI；当前仅有 USB 系统枚举和模拟流程验证，没有工业相机/深度相机采集验收。RealSense 原始深度与毫米点云、模拟采集到 3D 测量链路见 [深度相机说明](docs/depth-camera.md)。奥比中光 SDK v2 的 C2D 对齐、原始 Y16 与点云接入见 [Orbbec 说明](docs/orbbec-camera.md)。

## 部署

已提供带摘要清单的源码发布包、按功能安装、独立数据/模型目录、依赖检查和启动命令；Windows/ Linux 服务配置可生成，系统服务与 Linux 实机验收仍待完成。操作见 [部署说明](docs/deployment.md)。

## 启动

使用 Node.js 24 LTS，在 Windows PowerShell 或 Linux 终端执行：

```sh
npm ci
npm start
```

- 首页：http://127.0.0.1:1880/
- 视觉工作台：http://127.0.0.1:1880/vision/
- 视觉运行平台：http://127.0.0.1:1880/vision/?mode=run
- 流程编辑：http://127.0.0.1:1880/editor/
- 运行画面：http://127.0.0.1:1880/dashboard/

示例运行画面点击“执行示例”，消息通过自定义插件，在画面显示“运行成功”，在编辑器调试栏输出完整消息。

## 画面与插件

在编辑器 Dashboard 2.0 侧栏管理页面和分组，设置组件顺序及宽度；把按钮、文本、图表等节点拖入流程，绑定消息并部署。这是栅格式画面配置，并非自由拖拽 WYSIWYG 网页设计器。

插件模板在 `plugins/node-red-contrib-machine`：`package.json` 注册节点，`relay.js` 提供运行逻辑，`relay.html` 提供参数表单和帮助。新增插件可以打包为 npm 模块，通过 Node-RED 的管理面板安装，或使用 `npm install /path/to/plugin` 后重启。第一版插件使用可信本地代码，不提供进程隔离或热卸载。

流程和凭据存储在 `data/`，首次启动从 `examples/flows.json` 初始化，之后启动不覆盖用户流程。备份时应保留整个数据目录。可通过 `MACHINE_DATA_DIR`、`PORT` 调整存储位置和端口。

## 局域网

先运行 `npx node-red admin hash-pw`，交互输入密码，取得 bcrypt 哈希。

Windows PowerShell：

```powershell
$env:HOST = '0.0.0.0'
$env:ADMIN_PASSWORD_HASH = '这里填写生成的完整哈希'
npm start
```

Linux：

```sh
export HOST=0.0.0.0
export ADMIN_PASSWORD_HASH='这里填写生成的完整哈希'
npm start
```

其他电脑访问 `http://服务器局域网IP:1880/vision/`。管理员用户名默认 `admin`，密码是生成哈希时输入的密码。服务器防火墙需允许相应端口。视觉工作台/API 与编辑器都要求管理员身份；原有 `/dashboard/` 示例仍允许局域网访客访问。独立操作员权限后续增加。没有密码哈希时只允许默认本机绑定。

## 后续架构

1. 流程层：保留 Node-RED 编排、节点参数、部署及调试能力，通过扩展接口逐步加入工业视觉的流程校验、单步执行和结果追踪。
2. 画面层：已有独立的 12 列网页组件画布、属性面板、变量/结果绑定和工程内布局保存；继续增加多页面、趋势、报警、操作员权限和发布版本管理。
3. 插件层：已有 Node-RED 节点包及 SIEANS 独立 Python 算子插件清单、接口版本、字段契约、加载/启停和本地安装；后续增加依赖隔离、迁移与升级机制。
4. 算法层：已加入本地 Python 子进程与任务队列、超时机制，完成 2D 和 YOLO 检测。后续为高帧率采集增加共享图像引用和任务取消协议。
5. 部署层：当前为跨平台 Node 服务；后续增加 Linux systemd、Windows 服务和可选桌面壳。相机 SDK 是否支持 Linux 需按厂商逐项验证。

## 上游来源

- Node-RED：https://github.com/node-red/node-red （Apache-2.0）
- 嵌入接口：https://nodered.org/docs/user-guide/runtime/embedding
- 插件文档：https://nodered.org/docs/creating-nodes/
- FlowFuse Dashboard：https://dashboard.flowfuse.com/ （Apache-2.0）

当前使用 npm 发行包并通过 lockfile 固定依赖。GitHub 源码克隆因连接重置未成功；没有在此目录保存完整上游 Git 仓库。后续修改上游源码时需保留许可证和版权声明。

TCP/UDP 报文流程块、分帧、表单和回显演示见 [网络通信说明](docs/socket-communication.md)。

通用串口、软件回环及 Windows 虚拟串口验收见 [串口通信说明](docs/serial-communication.md)。



工作台新增 [子流程与有界循环](docs/subflows.md)：工程内可复用拖拽流程、独立局部变量、固定次数/布尔条件停止、轮次与内部明细表、统一取消/信任预检/变量事务。配合 [成功/失败连线](docs/error-routes.md) 完成错误恢复；演示分类“流程控制”提供 2D、3D 和条件循环示例。


“画面组态”新增报警列表与趋势曲线，服务器按作业/变量事件采样并持久保存；支持回差、连续样本确认、人工确认/恢复、缺失数据断点和采样表。运行模式可打开“报警与趋势记录”，浏览器关闭不影响连续作业采样。使用及保留限制见 [服务器报警与趋势](docs/runtime-monitor.md)。
