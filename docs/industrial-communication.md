# 工业通信：Modbus、OPC UA、西门子 S7 与 MQTT

使用 [PyModbus](https://github.com/pymodbus-dev/pymodbus) 3.16.1 与 [pySerial](https://github.com/pyserial/pyserial) 3.5，版本固定在 `industrial/requirements.txt`。上游许可证已保存在 `third_party/pymodbus` 和 `third_party/pyserial`。当前实现 Modbus 读写流程块、本机 TCP 模拟设备，以及下文的 OPC UA 浏览/读写适配。MQTT 发布和限时接收见下文；[TCP/UDP 通用收发](socket-communication.md)、[通用串口](serial-communication.md) 和 [MQTT 持续订阅/事件触发](mqtt-trigger.md) 已有实现与本机验证。现场 PLC、线路与故障恢复仍需目标设备验收。

## 安装和验证

```powershell
.venv/Scripts/python.exe -m pip install -r industrial/requirements.txt
npm run check
npm run test:industrial
```

Linux 安装使用 `.venv/bin/python`；串口还需相应系统访问权限。当前自动化和浏览器验证运行于 Windows。RTU 适配已实现参数校验及客户端调用，但尚未做实际串口/PLC 通信验证；不能以本机 TCP 模拟器测试替代 RTU 或现场 PLC 验收。

## 界面和演示

- 顶部“工业通信”打开本机模拟器状态、启动/停止操作，以及服务器串口枚举。不会扫描局域网设备或自动连接枚举出的串口。
- “工具箱 → 工业通信”提供 **Modbus 读取**、**Modbus 写入**。新增节点默认连接本机模拟设备；显式切换到 TCP 或 RTU 才使用相应配置。导入/接口请求缺少 transport 时按底层默认 TCP 显示和执行，不伪装成模拟设备。
- “演示案例 → 通信”包括：视觉检测 → Modbus 写入 → 读回 → 流程变量，以及浮点数组写入/读回。演示明确使用 `transport:simulator`，不访问现场设备。
- 模块结果表格逐项显示协议地址、数据类型、值。元数据保留原始寄存器、模拟标志、时间戳和数据质量；变量管理可检查写入的流程变量。

本机模拟器是独立 Python 进程，使用真实 Modbus TCP 帧，**仅绑定服务器 127.0.0.1，端口动态分配，站号 1**。四种数据区分别分配地址 0–255；保持寄存器 0–2 为 123/456/250，输入寄存器 0–2 为 100/200/300，线圈为 false，离散输入为 true。停止后状态清除；下次启动恢复初值。模拟节点可自动启动它；服务器退出时关闭模拟器。

## 地址、类型与端序

| 参数 | 含义 |
|---|---|
| transport | `tcp`、`rtu`、`simulator` |
| host / port | TCP IP 或主机名、端口（默认 127.0.0.1:502） |
| serialPort | Windows `COM4` 或 Linux `/dev/ttyUSB0` 等串口路径 |
| baudrate / bytesize / parity / stopbits | 默认 19200 / 8 / N / 1；校验位 N/E/O，数据位 7/8，停止位 1/2 |
| deviceId | TCP 0–255；RTU 1–247，不支持 RTU 广播写 |
| area | `coils` 线圈、`discrete` 离散输入、`holding` 保持寄存器、`input` 输入寄存器 |
| address | **零起始协议地址**，0–65535。常见手册保持寄存器 40001 对应协议地址 0，但必须核对厂商表，不能直接把 40001 自动转换 |
| dataType | uint16/int16/uint32/int32/float32/float64；线圈和离散输入固定为布尔值 |
| count | 读取的**数据值数量**。uint32/float32 每值占 2 个寄存器，float64 占 4 个 |
| value / values | 写入一个值或数组，可用变量/上游结果引用。线圈要求 true/false；整数类型不接受小数或超范围值 |
| byteOrder | 每个 16 位寄存器内字节顺序，big/little |
| wordOrder | 每个多寄存器数据值内的寄存器顺序，big/little；不会把多个独立值整体倒序 |
| timeoutMs | 每次连接/协议请求超时，100–10000 ms，默认 1500 |

读取最多 125 个寄存器或 2000 个位，写入最多 123 个寄存器或 1968 个线圈；单寄存器/单线圈使用 FC6/FC5，多值使用 FC16/FC15；读取使用 FC1/2/3/4。地址范围和数据类型容量会在连接前校验。离散输入及输入寄存器只读。

例：`uint32 0x12345678` 的四种布局为 `[0x1234,0x5678]`、`[0x3412,0x7856]`、`[0x5678,0x1234]`、`[0x7856,0x3412]`。float32 具有精度舍入；写入结果显示实际编码值，发生舍入时另保留 requestedValues。NaN/Infinity 返回错误，不静默转成 0。

## 流程与 API

只做通信的流程不需要图像，但需要从数据源连线以确定依赖。图像和点云数据通道透传；Modbus 输出为结构化数据，不生成伪图像。参数先通过现有变量引用机制解析，例如：

```json
{"transport":"tcp","host":"192.168.1.10","port":502,"deviceId":1,"area":"holding","address":10,"dataType":"uint16","value":{"$ref":"results.检测节点ID.count"},"timeoutMs":1500}
```

以上示例需替换为实际设备配置；开发演示使用 `transport:"simulator"`。结果包含 `values` 数组，单值也可从 `value` 读取。后续变量节点使用 `{"$ref":"results.读取节点ID.value"}`，绑定到全局/流程/模块变量。汇合时只能引用已连接上游结果，不能依赖旁路节点的偶然执行先后。

- `POST /api/vision/industrial/run`：`{operation:"modbus_read"|"modbus_write",params:{...}}`。
- `GET /api/vision/industrial/ports`：枚举服务器本地串口（设备路径、描述、硬件 ID）。
- `GET /api/vision/industrial/simulator`、`POST .../start`、`POST .../stop`：模拟器状态及生命周期。运行流程期间拒绝停止模拟器。
- 流程作业继续通过 `/api/vision/runtime/jobs` 创建/查询/取消。

上述路由使用既有工作台管理员认证。当前端点配置保存在节点参数中，尚无独立连接配置仓库/密钥库和操作员权限策略。

Node-RED 对应 `machine-modbus_read`、`machine-modbus_write` 节点，使用表单配置，参数可由 `msg.industrialParams` 覆盖；输出 `msg.payload` 为结果，`msg.industrial` 为完整输出。用 Catch 节点处理失败。插件依赖平台的 `machineIndustrial` 运行时，单独安装到其他 Node-RED 实例需要配置该服务。

## 超时、取消及外部写入

每次调用在独立 Python 进程内连接、完成一次事务并关闭连接。最多并发 8 个通信任务，同一 TCP host:port 或同一串口互斥；不提供连接池或跨别名识别同一设备的锁。已通过流程依赖串联的读写依次执行。

通信子进程可被取消/超时终止，端点锁在进程实际退出后释放。读写均不自动重试。丢失写入确认时状态可能未知，错误明确提示请求可能已到达设备，应另行读取设备状态；自动重复发送可能触发重复动作。

`acknowledged:true` 仅代表已收到地址/数量/单值相符的协议确认，**不代表电机、阀门等物理动作已完成**。流程失败或取消会回滚运行变量，但不能回滚已经到达设备的外部写入；测试覆盖这一差异。需要可靠动作确认的现场协议应另设计请求编号、状态反馈和幂等规则。

## 已验证与待验证

- `tests/test_modbus.py`：9 项编码、配置、真实本机 TCP 测试，覆盖零起始地址、四类数据区、单/多寄存器和线圈、奇数位数量、浮点字节序/舍入、异常响应、非法参数、写确认丢失且不重试。RTU 当前只有配置验证。
- `tests/test_industrial_runtime.cjs`：6 项模拟器生命周期、无图像通信、变量绑定、外部写入与变量回滚差异、端点锁与取消，以及两种演示的真实算法/协议运行；另验证取消已发送写请求后的状态不确定提示。
- `tests/test_integration.cjs` 的 TEST_INDUSTRIAL 模式：HTTP 实际读写、作业/变量/工程存储、非法区写入拒绝、真实 Node-RED Modbus 节点、模拟器关闭。
- 浏览器已实际运行“检测数量 3 → 保持寄存器 10 → 读回 3 → plcCount=3”，并检查模拟器和串口枚举 UI。
- 尚待：真实 TCP PLC、RTU 串口设备、Linux 现场部署、其他工业协议、订阅/连接池/触发/通信审计和连续运行。


## OPC UA（2026-10-15）

选用 GitHub 官方仓库 [FreeOpcUa/opcua-asyncio](https://github.com/FreeOpcUa/opcua-asyncio)，锁定 `asyncua==2.1.0`，许可证保存在 `third_party/asyncua/COPYING`。独立 Python 进程通过真实 OPC UA 二进制协议连接；工作台、服务器运行时和 Node-RED 共享适配层。

### 操作与界面

工具箱提供 OPC UA 浏览、OPC UA 读取、OPC UA 写入。新增节点默认使用本机模拟设备；切换为 OPC UA 服务器后，表单显示服务器端点、节点地址、可选命名空间 URI、安全策略和认证字段。导入/接口请求未指定 connection 时，按真实服务器处理，缺少 endpoint 会拒绝执行。

“浏览设备节点”沿用当前节点连接配置，从 Objects 根节点开始逐层浏览。表格显示节点名称、类别和地址，可进入、读取预览或选用。预览展示类型、质量、值和两种时间戳；写入节点选用变量时先读取其类型，自动回填节点地址和类型，实际写入值仍由操作者配置。跨服务器引用不能直接选用。

每层浏览上限 1–500，默认 100，使用 OPC UA Browse/BrowseNext 服务并释放 continuation point；超过上限返回 truncated，不声称完整列举。当前没有跨会话分页、设备自动发现、方法调用或历史读取。

两个演示均只连接本机：

1. 视觉检测 → OPC UA → 流程变量：检测 3 个轮廓，写 Count，读回 3，保存 uaCount=3。
2. OPC UA 数组写入与读取：Samples 写入 12.5、-3.25、8 并读回，类型 Double。

### 类型和质量

支持 Boolean、SByte/Byte、Int16/UInt16、Int32/UInt32、Int64/UInt64、Float/Double、String、DateTime、Guid、ByteString，以及最多 1000 项的一维写入数组。写入类型须与服务端一致；不以自动类型转换掩盖 BadTypeMismatch。整数越界、布尔冒充整数、非有限浮点、嵌套写入数组会在连接前拒绝。

Int64/UInt64 读回统一用十进制文本，写入超过 JavaScript 安全整数范围的值也必须使用十进制文本。Float 按 32 位浮点实际编码并同时报告请求值。DateTime 使用带时区 ISO 日期时间文本；ByteString 使用 Base64 文本，最多 16 KB。复杂 ExtensionObject、自定义结构体等尚不支持。

读取保留 OPC UA 状态码、Good/Bad/Uncertain 质量、源端时间戳、服务器时间戳和采集时间。源端未提供时间戳时显示空值，不用本机时间伪造。默认 requireGood=true，非 Good 值使流程失败；浏览预览和显式关闭质量检查时可查看坏质量状态。尚未实现基于时间戳的过期数据策略。

namespaceUri 非空时通过服务器 NamespaceArray 解析当前 namespace index，避免服务器重启后命名空间序号变化造成误读；节点标识符保持不变。只给 nodeId 时按其数字 namespace index 使用。

### 连接与认证

端点格式为 opc.tcp://主机:端口/路径。支持两种模式：

- None：匿名，无加密；带用户名认证参数会被拒绝。
- Basic256Sha256：固定 SignAndEncrypt；填写服务器上的客户端证书、私钥和已信任服务器证书路径，以及与客户端证书 SAN 匹配的应用 URI。服务器证书进行固定证书匹配、有效期及应用 URI 检查，不自动信任网络下载的证书。现场服务器需另行信任客户端证书。当前尚无 CA/CRL 管理、证书生成/轮换界面和加密私钥密码支持。

加密连接可选择用户名认证，密码只从服务器环境变量读取，变量名必须以 SIEANS_OPCUA_ 开头。工程保存用户名和环境变量名，不保存密码；服务器启动前设置该专用环境变量。环境变量管理目前由部署环境负责，不提供浏览器读取密码接口。直接提交 password 参数会被拒绝。

### API、进程与插件

`POST /api/vision/industrial/run` 支持 opcua_browse、opcua_read、opcua_write。公共参数为 connection、endpoint、security、nodeId、namespaceUri、timeoutMs；read 增加 requireGood，browse 增加 browseLimit，write 增加 dataType/value。工作台用表单生成这些后台字段，无需直接编辑结构化协议数据。

OPC UA 模拟器使用 `GET /api/vision/industrial/opcua/simulator` 与对应 `POST .../start`、`POST .../stop`。仅监听 127.0.0.1 动态端口，命名空间 urn:sieans:simulator，根节点 SIEANS，变量为 Count(UInt32)、Passed(Boolean)、Height(Double)、Label(String)、Samples(Double 数组)、Serial(只读 String)。模拟器停止后重置状态，父服务退出后随 stdin EOF 停止。

每次调用建立独立会话并关闭；timeoutMs 100–10000 控制连接、认证与操作总时间，不含进程启动及最长 500 ms 的连接清理。共享最多 8 个通信进程，同一 OPC UA 主机名和端口互斥；主机别名不会自动归并。取消会终止子进程。auto_reconnect=false，不自动重试写入。写确认仅代表 OPC UA 服务端确认，外部写入不会随变量事务回滚；取消或丢失响应时提示外部状态可能未知。

Node-RED 新增 machine-opcua_browse / machine-opcua_read / machine-opcua_write。工业通信节点的参数界面改为表单，写入数组使用表格；msg.industrialParams 可覆盖配置，msg.payload 为结果，msg.industrial 为完整输出。参数的后台存储仍兼容旧 params 字段。

### OPC UA 验证范围

- `npm run test:opcua`：9 项 Python 配置/真实协议测试、5 项运行时测试及 HTTP/Node-RED 集成。
- Python 覆盖类型、数组、64 位精度、节点浏览与截断、命名空间 URI、坏质量、只读/类型不匹配、超时；本机加密服务器验证用户名密码、正确证书、错误证书拒绝、错误密码拒绝及错误信息不包含密码。
- 运行时覆盖模拟器复用/重启、无图像读写、变量绑定、下游失败回滚变量但设备写入保留、端点锁和取消，以及两种真实视觉/协议演示。
- HTTP/Node-RED 验证浏览/读写、质量、变量、工程保存、实际 OPC UA 写入→读取插件流程及模拟器关闭。
- 浏览器实测检测→写入→读回 3、节点逐层浏览、读值预览和节点选用；仍未访问用户的实际 PLC。
- 本轮 `npm run test:industrial` 的 Modbus 全部回归通过；`pip check` 无依赖冲突。测试运行于 Windows，尚无 Linux 实机或现场 OPC UA 服务器验收。


## 西门子 S7（2026-10-16）

采用 [python-snap7](https://github.com/gijzelaerr/python-snap7) 3.2.1 的经典 S7 客户端，MIT 许可证保存在 `third_party/python-snap7/LICENSE`。该版本为纯 Python 实现，无需另装 Snap7 原生 DLL。使用范围依照 [3.2.1 官方说明](https://python-snap7.readthedocs.io/en/3.2.1/introduction.html)：S7-300/400，以及具备 PUT/GET 访问配置和非优化 DB 的 S7-1200/1500。当前适配不包含 S7CommPlus、符号寻址、CPU 启停或程序下载，也不更改 PLC 工程设置。Windows 本机协议模拟通过，真实 PLC 和 Linux 实机尚待验收。

工作台和 Node-RED 分别提供 S7 读取 / 写入、`machine-s7_read` / `machine-s7_write`。新节点默认本机模拟设备；导入或 API 缺少 connection 时为 PLC 连接。界面按连接方式、数据区和类型显示对应表单，写入值可为单值、数组、变量或上游结果绑定。结果逐项显示字节偏移、数据类型和值，原始字节是可展开表格。

| 配置 | 含义 |
|---|---|
| 连接方式 | simulator 或 plc；真实设备配置 host、port（102）、rack（0–7）、slot（0–31） |
| 数据区域 | db 数据块、mk 中间存储 M、pe 输入 I、pa 输出 Q；I 只读 |
| dbNumber | DB 区编号 1–65535，其他区域忽略 |
| byteOffset | 零起始字节地址；DB1.DBW10 对应 DB=1、偏移=10、uint16 |
| dataType | bool、uint8/int8、uint16/int16、uint32/int32、float32/float64；数值固定大端 |
| bitOffset | BOOL 位偏移 0–7；DB1.DBX100.1 对应 DB=1、字节偏移=100、位=1 |
| count | 读取值数量；数值数组按类型宽度连续排列，单次上限 200 字节 |
| 写入值 | 单值或数组；BOOL 每次仅一个开关，整数不接受小数/越界，浮点拒绝 NaN/Infinity |
| 事务超时 | 100–10000 ms，默认 3000；Node 进程监督握手和请求，总期限额外预留 1000 ms 启动子进程。直接调用 Python 函数不具有这一进程期限 |

每次事务连接后关闭，不自动重连或重发写入；位访问使用 S7 BIT 请求，不进行客户端整字节读改写。请求数据限定 200 字节并请求 240 字节 PDU，常规协商下为单次读写。设备写入与变量事务分离：后续失败可回滚变量，不能撤销设备写入；超时/取消可能无法确认写入状态，界面明确提示。设备应答不等于物理动作完成。应用只做本地端点互斥，尚未提供跨进程/跨主机设备锁。

模拟器只绑定服务器 127.0.0.1 的动态端口，提供 DB1（4096 字节）、M/I/Q（各 256 字节），DBW0=123，DBD4 的 float32=12.5。停止后重置；S7 节点可自动启动。`GET /api/vision/industrial/s7/simulator` 查询状态，`POST .../start` / `.../stop` 控制生命周期；工作流执行期间拒绝停止模拟设备。单次请求仍通过 `POST /api/vision/industrial/run`，操作为 s7_read/s7_write。

上游 3.2.1 的模拟服务器丢弃 BIT 偏移并按整字节访问，本项目在 **仅用于本机模拟** 的 `industrial/s7_test_server.py` 子类中补齐单个位处理、范围检查与锁；实际 PLC 客户端未经修改。私有模拟器接口与库版本锁定，升级时必须重跑相邻位保护测试。模拟测试不能代替真实设备协议兼容性验证。

演示：视觉轮廓数量 3 → DBW10 写入 → 读回 → s7Count；两个 float32 写入读回 12.5/-3.25；DBB100 从 170 清除第 1 位后读回 168。`npm run test:s7` 包含 5 项 Python 数值/协议测试、6 项运行时测试，以及 HTTP 工程/变量和实际 Node-RED 写读链路。测试还覆盖全部 8 个位的相邻位保护、地址/类型错误、模拟器重启、超时取消、端点互斥及外部写入不回滚。


## MQTT 发布与限时接收（2026-10-16）

选用官方 [MQTT.js](https://github.com/mqttjs/MQTT.js) 5.16.1 作为 Node.js 客户端，[Aedes](https://github.com/moscajs/aedes) 1.2.0 作为本机模拟消息服务器，均为 MIT；直接依赖固定在 package-lock.json，上游许可副本在 third_party/mqtt、third_party/aedes。选择现有 Node.js 运行时统一通信，不另启 Python MQTT 子进程。

工作台工具箱新增“MQTT 发布”和“MQTT 接收”；Node-RED 对应 machine-mqtt_publish / machine-mqtt_receive。支持 MQTT 3.1.1、TCP/TLS、QoS 0/1/2、保留消息、主题通配符以及 UTF-8 文本、结构化数据、字节数组三种消息体。配置、变量绑定、数组和结构体内容均为表单/表格，没有原始配置编辑框。结构化数据在传输时自动编码；接收时解码成可绑定的 result.value。整数超出安全范围时应使用文本。

### 工作台使用

1. 选择消息服务器：本机模拟设备自动启动 Aedes；外部服务器填写主机、端口及认证。默认新建节点为模拟设备，避免演示访问外部设备。
2. 发布：填写主题，选择格式与 QoS，按字段编辑“发送内容”或绑定上游结果。主题不允许通配符。
3. 接收：填写精确主题或 + / # 通配符（+ 独占单层，# 为末尾整层），等待一条符合条件的消息后结束。可选择是否接收保留消息；禁用后忽略历史保留值，等待新消息。
4. 用“变量赋值”选择接收模块的 value 或嵌套字段，写入全局、流程或模块变量。图像、点云及深度帧继续传给后续视觉模块。
5. 演示案例包含“视觉检测 → MQTT → 流程变量”、中文文本和字节数组往返，全部只访问本机。

“工业通信”窗口可查看、启动或停止模拟服务器。监听仅为 127.0.0.1 的动态端口；最多 32 个连接、100 个保留主题，保留消息体总计 4 MiB。停止/重启清空内存保留消息。流程或 MQTT 任务运行期间不能通过管理接口停止它。此模拟器用于协议验证，不作为生产消息中间件。

### 认证与 TLS

用户名可直接配置；密码只填写服务器环境变量的名称，工程不存储密码值。TLS 始终验证服务器证书和主机名，CA 文件留空时使用系统/Node.js 信任；私有 CA 填写服务器本地证书文件路径。需要双向认证时成对设置客户端证书与私钥；加密私钥密码同样使用环境变量名称。证书文件最多 1 MiB。TCP 模式不会加密用户名、密码及消息。

### 执行语义与限制

- 每次执行使用 clean session，默认随机生成客户端标识，完成后关闭连接。不自动重连或重试；相同端点和显式客户端标识在本进程中互斥，MQTT 并发任务上限 8。
- 总操作超时 100–60000 ms；关闭连接另有最多约 500 ms 清理宽限。支持运行取消。消息体最多 64 KiB；接收长度在解码时校验，不宣称对任意恶意对端具有整个进程的硬内存隔离。
- 发布 QoS 0 的 delivery 为 sent，acknowledged 为否；QoS 1/2 为 broker_acknowledged，acknowledged 为是。协议应答不代表订阅设备已执行，更不代表工业动作恰好一次。
- 接收结果包含实际主题、QoS、retained、duplicate、时间、字节数和解码后的 value。发布 retain 为是且内容为空文本/空字节数组时清除主题保留消息。
- 发布后的超时/断线/取消会提示交付状态可能未知；平台变量回滚不会撤回消息。发送侧需自行设计业务编号、应用应答和幂等处理。
- 上述单次节点不保持长期订阅。工具栏另有 [MQTT 持续订阅与消息触发](mqtt-trigger.md)，支持服务器订阅、重连、队列和工程触发；仍不保存离线会话、不跨服务重启恢复消息队列，不提供 MQTT 5、WebSocket 或共享订阅。

Node-RED 发布节点可选择“输入消息内容”（msg.payload）或“表单常量”；动态连接参数可用 msg.industrialParams，选择消息内容来源时消息体以 msg.payload 为准。输出 msg.payload 为结果，完整结果位于 msg.industrial；Catch 节点接收错误，节点关闭取消其未完成任务。

### 验证

运行 npm run test:mqtt。9 项协议/运行测试覆盖真实 TCP 数据包、QoS/三种消息体、保留清除、通配符新消息、无效配置/解码、并发取消、认证拒绝不重连、CA/主机名/mTLS、应答丢失及变量回滚/数据帧保留。独立 HTTP 测试验证鉴权、三条演示、工程保存、变量和运行历史、取消与模拟器锁；真实 Node-RED 流程验证消息/常量发布、接收及 Catch 错误。完整 npm test：97 项 Node 测试、38 项 Python 测试及三组 HTTP/Node-RED 集成通过。浏览器已验证工作台 TLS 字段、接收结果表和流程变量 3，以及 Node-RED 常量字段修改后重新打开仍为 27。真实厂区 MQTT 中间件与设备尚未验收。
