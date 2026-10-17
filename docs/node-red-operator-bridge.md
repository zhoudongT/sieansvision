# Node-RED 独立算子插件节点

集成版 Node-RED 新增 `SIEANS Vision → 扩展算子`（`machine-operator`）。它执行与视觉工作台相同的已安装 Python 算子包，不需要为每个插件再编写一个 Node-RED 节点。

## 配置与运行

1. 按 [插件安装说明](operator-plugins.md) 安装插件并重启服务。内置插件随服务器加载。工作台插件管理的启停状态同时作用于 Node-RED。
2. 拖入“扩展算子”，在下拉框选择算子。参数依据清单生成数值、开关、枚举、嵌套字段表或固定列点位表；不提供原始 JSON 参数编辑框。
3. 参数取值方式可选“表单值”或“上游消息字段”。字段路径例如 `payload.calibration`；不支持表达式求值。消息缺失或类型不符会报错。固定列点位表可增删行和逐项编辑。
4. 部署后传入数据。输出 1 为结果及完整消息，输出 2 为显示用点云（优先）或图像。用 Catch 节点处理错误。插件标识和精确版本固定在节点中，不接受消息更换插件/版本。

可导入 [演示流程](../examples/operator-plugin-flow.json)：注入 → 平面标定 → 测量 → 结果。四点像素对应 100 × 60 mm，测量从 (100,100) 到 (500,100) 的图像线段，预期约 100 mm。第二个算子的标定参数绑定 `payload.calibration`，编辑界面可直接查看绑定和两点坐标表。

## 消息契约

| 字段 | 用途 |
|---|---|
| 输入 `msg.image` / `msg.cloud` / `msg.depth` | 图像数据、带单位点云、原始深度；缺少顶层字段时也接受 `payload` 对应字段，图像还可直接来自字符串 payload |
| `msg.operatorArgs` | 覆盖表单参数的字段映射；显式消息路径绑定在其后应用，优先级最高 |
| `msg.operatorVariables` | 本条消息携带的 `global`、`flow`、`module` 三个字典，传入插件的 `ctx.vars`。插件返回的范围替换会传给下游消息 |
| 输出 `msg.payload` | 通过插件声明校验的结果字段 |
| 输出 `msg.vision` | 结果、图像/点云/深度、消息变量、耗时与日志 |
| 输出 `msg.image` / `msg.cloud` / `msg.depth` | 沿用或更新数据通道；插件返回空点云/深度时删除旧字段，不恢复上游旧数据 |

`operatorVariables` 是消息上下文，并非 Node-RED 自身的 node/flow/global context，也不自动读写工作台服务器的三级持久化变量。需要完整事务、固定类型及工作台变量保存时，仍应通过视觉工作台运行工程。跨消息的 Node-RED 状态应显式使用 Node-RED context 管理。此桥接没有将两个运行系统的事务或权限混同。

## 执行与边界

- 沿用清单输入/输出类型、范围、列结构、必填字段和精确版本校验。服务端检查图像、点云、深度及消息变量格式；无效输出不会发送到下游。
- 每个节点同时处理一条消息，忙时拒绝新消息并进入 Catch；不自动排队或重试。全部工作台与 Node-RED 插件执行共享最多 4 个并发槽。插件执行期间禁止修改插件启停状态。
- Python 子进程超时取清单值（100–30000 ms），重新部署/删除节点会取消当前子进程；插件发生的文件、设备等外部副作用不能回滚。该机制不是脚本安全沙箱。
- 插件目录在服务启动时加载。刷新按钮只重新读取服务器清单，不热加载文件，也不自动升级固定版本。缺失版本/读取失败保留既有配置，用户需恢复插件或显式选择新版本。
- 元数据端点位于 Node-RED 管理接口并要求 `flows.read` 权限。此节点依赖集成服务器提供的 `machineOperators` 服务，单独安装节点包到普通 Node-RED 不会附带 Python 环境与算子运行时。
- 当前大数据仍走消息序列化，沿用点云/帧/插件输出体积上限；没有共享内存句柄或跨进程零复制。

## 验证与来源

7 项新测试覆盖真实 2D/3D 插件、输入/输出契约、变量范围、空通道、版本/停用状态、字段绑定、并发和取消。HTTP 集成部署真实 Node-RED 节点，验证 100 mm 标定测量链、294000 像素亮度统计、121 点 30° 坡度检测，以及 Catch 错误路径。

节点生命周期和编辑器实现遵循官方 [JavaScript 节点接口](https://nodered.org/docs/creating-nodes/node-js)、[节点属性](https://nodered.org/docs/creating-nodes/properties) 与 [编辑器 HTML 接口](https://nodered.org/docs/creating-nodes/node-html)。代码来源项目为 [Node-RED](https://github.com/node-red/node-red)，此桥接实现为本项目原始代码。

卡尺等测量插件可以输出独立 `annotatedImage`：第一路 `msg.image` 保留算法数据图，`msg.vision.annotatedImage` 与第二路显示标记图（若同时输出点云，第二路仍优先点云）。提供 `image` 的旧插件继续更新下游数据图。HTTP 集成另验证 8.04 mm 合成条带测宽及原图/标记图分离。
