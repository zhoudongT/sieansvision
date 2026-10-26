# VisionMaster 4.4.50 插件契约对照

日期：2026-10-23。目标是按本机公开 SDK 已确认的输入、参数、结果分层改进 SIEANS 插件体验。实施使用原创 JavaScript / Python 作业契约；没有复制厂商源代码或 DLL，也没有执行厂商程序集。本记录不能证明与 VisionMaster 二进制插件兼容、算法一致或界面完全相同。

## 观察证据

根目录：`C:/Program Files/VisionMaster4.4.50/Development/V4.x/`。下列头文件和示例仅只读核对接口名称及类型；未纳入仓库。

| 标识 | 本机相对路径及位置 | 观察 | SHA-256 |
|---|---|---|---|
| SDK-PARAM | Includes/VmModuleParamBase.h，326–460 行 | 参数项有名称、值、上下限及基本类型访问；输入项单独定义，含点、线、圆、图像等类型 | `415fd2738ba5c0a8b4301ca13ce327297400cfdc4adbbed73ae7859a5c3d6b16` |
| SDK-IO | Includes/IVmDynamicIoDefine.h，15–38 行及数组定义 | IO 具有整型、浮点、字符串、图像、几何类型区分；数值及文本可带数量 | `03a5379f00b06f47764d53c6f40fddccea934fc0191b04bf5d6688b0f39be64e` |
| SDK-RESULT | Includes/VmModuleResultBase.h，结果结构及 CModuleResultBase | 结果字段携带数量/状态，模块结果基类可取错误码和执行时间 | `1f428dfdae4b953873d1ef26c51f24cae51bcd3dd14373f9f859ff0acbe7110b` |
| SDK-SAMPLE | Samples/C#/PlatformSDKSampleCS/CircleFind/Form1.cs，167–174 行 | 示例从 ModuResult 读取圆结果及中心坐标，从输出路径读取模块状态 | `cc5a85a23f8e79e93060b835a25d040d08ee5669a7349eb3ebc4005ae8cdc927` |

REA 托管静态核对：

- `ev_f5c5361bcf60e5207f71788a47ce59e5ee13fc7e19cce6e712cb455ac77fac76`：`ComControls/Assembly/VM.Core.dll`，SHA-256 `6698828cec20db765d814a1561d1c6d709985b4fc38017844043346aa0a07323`；程序集身份与元数据读取完整，框架 `.NETFramework,Version=v4.6.1`。
- `ev_359bbd93ea792c3d0289344ab683192c1695f13c8457d9124b8ddd60bca4e2e4`：上述 Core 的成员检查因 64 MiB 表示预算不可用。未用此结果推断成员或实现。
- `ev_ffafe54a3032b1f4d5ae050af0cd3a1b2cf7f931ab4b9e33e4ddc372a4e9d2cd`：`ComControls/Assembly/IMVSCircleFindModuCs.dll`，SHA-256 `505b2fc984452ccad2fc1a96b2893ee67a9ff79fba0991a7541c1cc54f94cbdc`；成员覆盖标记为 `partial`。已观察到 `get_ModuParams`、`get_ModuResult`、`Run`、输入图像 setter 和圆结果 getter。仅以这些被返回的声明佐证分层，不将静态证据描述为实际运行或完整实现恢复。

## 实施映射与验收

| 已观察语义 | 本平台实现 | 验收 |
|---|---|---|
| 模块输入和参数分开 | 新增可选 inputs，运行时为 ctx.inputs；原参数仍为 ctx.params | 实际 Python 子进程接收二者；上游结果经标准运行时解析到命名输入 |
| 输入/结果带类型，几何对象含子字段 | properties、items、输出 columns | 缺字段、多字段、错误类型、范围和数量不合法时拒绝；输出不补默认值 |
| 有名称、范围和枚举的参数 | 复用现有类型表单，新增组/单位/帮助说明 | UI 控件更新参数，必要开关不隐式选为 false |
| 可独立获取结果 | 输出页签及结构子字段快捷绑定 | point.x 可绑定流程变量，目标名冲突生成后缀 |

三页签属于结合 SDK 分层作出的产品设计选择；本次未观察厂商窗口的所有交互，因此不主张其页签位置、名称或视觉细节等价。typed arrays / properties 是本平台声明式表示，不复刻厂商内存布局、类型编号、指针或生命周期 ABI。

验证命令：`node --test tests/test_operator_plugin_contract.cjs tests/test_operator_plugin_contract_ui.cjs`（10/10）；`node --test tests/test_operator_plugins.cjs`（14/14）；`node --test tests/test_operator_bridge.cjs`（7/7）。新增 UI 验证是执行真实页面脚本的 DOM 交互测试，不能代替浏览器视觉验收。语法检查通过。20 个内置包 / 44 个算子无扫描错误。测试使用隔离临时目录和 Python 作业，没有启动 1930 服务或连接相机。

仍未实现：厂商二进制插件装载、厂商专有点/线/ROI/图像内存协议、动态增删端口及其生命周期回调、厂商模块状态码映射、Node-RED 新契约表单；未宣称覆盖 VisionMaster 所有插件入口。当前交付覆盖工作台的声明式数据输入、参数编辑和结果绑定。
