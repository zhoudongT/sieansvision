# SIEANS 算子插件接口 v1

2026-10-23 开发源码增加输入 / 参数 / 输出三个配置页签、独立命名输入与递归结构字段契约，兼容现有 `apiVersion: 1` 插件。依据和边界见 [VisionMaster SDK 对照记录](visionmaster-plugin-contract.md)。这些是本平台的独立实现；不加载 VisionMaster DLL，不表示兼容其二进制插件或完成全部界面与接口等价。

开发工作目录新增 [三维旋转包围盒](../operator-plugins/sieans-box/README.md)：Open3D 凸包优化、全输入点重新投影包围、长中短边公差与角点表。含毫米/米、超差和等边提示演示，不输出机器人定位位姿或实体体积。冻结候选包尚不包含。

开发工作目录新增 [轮廓建模与形状识别](../operator-plugins/sieans-shape/README.md)：参考区域建模、Hu 外轮廓匹配、孔洞数量/面积比例和匹配数量保护，支持完整分割轮廓的旋转缩放比较。五个演示含表单、候选表与 HMI。此功能不输出定位角度，不用于正反面判定，冻结的 0.3.0 开发候选 2 尚不包含。

开发预览新增 [倾斜基准高度与可见体积](../operator-plugins/sieans-heightfield/README.md)：独立基准点表标定、同单位/坐标系模型绑定、法向高度网格、缺测/层叠/覆盖诊断。报告可见表面估计，不把缺失格填零或称为封闭实体真实体积。

开发预览新增 [2D 定位跟随](../operator-plugins/sieans-fixture/README.md)：既有模板定位增加多目标去重、位姿和完整性状态；插件可转换点位、校正同帧检测区域，接后续算子检测。五个图/表运行画面演示包含唯一目标条件保护。

开发预览新增 [圆孔与双圆测量](../operator-plugins/sieans-circle/README.md)：径向卡尺/亚像素边缘、稳健圆拟合、原图校验、直径公差、双圆中心偏移与理想圆壁厚。七个演示包含数值/状态灯/标记图和检测明细表，原图继续传递给下游。

开发预览新增 [流程记录处理插件](../operator-plugins/sieans-records/README.md)：字段创建、追加/去重、筛选、排序、行读取、字段映射与统计，可用流程变量累积检测或标定采样。包含 HMI 记录表和条件采样接手眼演示。

开发预览新增 [眼在手上标定插件](../operator-plugins/sieans-handeye/README.md)：棋盘位姿、十二列同步姿态表求解和独立姿态验证，输出兼容现有刚体坐标转换。此新增部分未包含在已发布的 0.2.0 源码包。

新增 [3D 对应点标定与坐标转换](../operator-plugins/sieans-rigid/README.md)：六列对应点表、正反向点位/点云转换、单位/坐标系检查和独立验证，含模拟 Modbus 链路。

新增 [相机内参与畸变校正插件](../operator-plugins/sieans-intrinsics/README.md)：棋盘格角点累积、多视图针孔标定和校正图输出，全部通过点位表、功能表单及变量绑定操作。包含三个合成演示及数值/运行时/HTTP 验证。

新增可选的输入表格列契约：数组参数可声明 `columns`（1–12 个基础类型列）及 `minimumRows` / `maximumRows`（0–1000）。列沿用名称、类型、数值范围、选项及默认值定义，不允许嵌套数组/结构体列；每一行必须完整包含声明列，不接受额外字段。前端按列生成表格、分批显示并支持增删行，后台在执行插件前校验，旧清单无需修改。整张表仍可绑定变量或上游结果。内置平面标定插件使用图像 X/Y、实际 X/Y 四列表格，详见 [平面插件说明](../operator-plugins/sieans-planar/README.md)。

新增独立 Python 算子不再需要修改主程序。服务器读取清单，工具箱显示算子，参数按类型自动生成表单，输出按字段表显示，并可绑定全局、流程、模块变量。插件源代码和清单在服务器目录维护；工作台不显示原始配置数据。

## 已交付

- 自动发现随软件提供的 `operator-plugins/<目录>`，以及数据目录下的 `operator-plugins/<目录>`。
- 插件管理表：名称、版本、算子、加载状态、错误、启用/停用。运行期间服务器拒绝启停。
- 工程保存 `pluginId`、`pluginVersion`、`operatorId`，运行前检查安装状态及精确版本，避免前面的设备节点已执行才发现插件缺失。
- 兼容接口为 `apiVersion: 1`，版本为三段数字。重复 ID 的所有副本不可执行；无效插件独立报告错误，不阻止其他插件和内置算子启动。
- 输入参数：数值、整数、文本、开关、数组、结构体、枚举，必填、默认值、数值范围；参数支持三级变量和上游结果绑定。绑定解析后再次按契约验证。
- 结果：声明字段及其类型，缺少必填字段或返回未声明字段会失败；可选 `properties` / `items` / `columns` 进一步检查结构、数组元素与记录表，未声明子结构时保留原容器校验。
- 每次调用独立 Python 子进程，超时 100–30000 ms，停止时中止子进程；遵循平台变量事务。插件有服务器账户权限，**不是沙箱**，只能安装可信本地代码。

本接口是 SIEANS 作业式算子接口，和现有 Node-RED 节点包分开。它不自动产生 Node-RED 编辑器节点，也不直接运行任意 Node-RED 插件。

## 开发与安装

以 `operator-plugins/sieans-inspection` 为完整样例：

| 文件 | 用途 |
|---|---|
| operator-plugin.json | 插件 ID、版本、API 版本、许可证、算子、输入与结果字段定义 |
| brightness.py | OpenCV 全图灰度亮度统计与范围判定 |
| centroid.py | 点云采样质心及到目标的距离判定 |
| LICENSE | 样例代码许可证 |

复制到新的开发目录，修改插件 ID、名称和实现。清单每个算子声明 `id/name/description/entry/input/timeoutMs/parameters/outputs`。入口必须是目录内的单个 `.py` 文件名；不支持路径跳转、符号链接或加载入口以外的同目录 Python 模块。单入口文件上限 100 KB，清单上限 128 KB。多算子可以共用入口，但应通过不同参数表达行为。

每个参数/结果字段声明 `key/label/type`，可选 `required`。参数可增加 `default/minimum/maximum/choices`；choices 是带 `value/label` 的选项。标识用英文，label 用操作员能理解的中文。清单由插件开发者维护；操作员只填写工作台表单。

入口实现 `def run(ctx)`，返回字典。`ctx` 提供：

| 内容 | 说明 |
|---|---|
| params | 表单填写并解析绑定后的参数 |
| inputs | 命名输入字段；由步骤的 inputs 传入，和 params 分开，旧插件得到空对象 |
| image | 图像 data URL，未输入时为空字符串 |
| cloud | 点云数据或空值，含 points、unit，可含 colors/frame |
| depth | 原始深度帧或空值，含 PNG16、比例、内参等 |
| vars | global / flow / module 变量副本 |
| results | 可访问的上游已执行节点结果，以节点 ID 为键 |

### 命名输入和结构字段（2026-10-23 开发源码）

算子可增加 `inputs` 字段列表，沿用 `key/label/type/required/default`。工程步骤把输入写在 `params.inputs`，算法参数仍在 `params.arguments`。工作台的“输入”页签编辑这些字段，绑定格式仍为 `{$ref: 'results.模块ID.字段路径'}` 或三级变量引用。运行时解析绑定、补全声明的默认值、校验后注入 `ctx.inputs`。原有 `input: image/cloud/depth/none` 继续决定主要数据通道。

| 可选定义 | 适用字段 | 行为 |
|---|---|---|
| `properties` | object | 1–100 个字段定义；检查必填、数值范围及子字段，不接受未声明键；输入对象存在时补齐子字段显式默认值 |
| `items` | array | 单个元素定义，不带 `key`；支持基础类型或嵌套结构，按项检查 |
| `columns` | array | 1–12 个基础类型列；输入与输出均可声明，所有列均必须存在 |
| `minimumRows` / `maximumRows` | 含 items 或 columns 的 array | 0–1000 项；默认为 0–1000，items 与 columns 互斥 |
| `group` / `unit` / `description` | 输入、参数、结果字段 | 显示参数组、单位及帮助说明；仅为展示元数据 |
| `category` | 算子 | 可选分类元数据，供调用方使用 |

递归字段定义最多 6 层；每组输入、参数或输出定义最多 500 个字段。结果不会补全默认值，算法必须真正返回必需字段。新的输出字段表支持为结构体子字段直接添加输出绑定。旧清单无需增加上述字段，现有 20 个内置插件 / 44 个算子均通过扫描。

以下是插件开发者可用的字段定义示例；工作台操作者通过表单编辑，无需输入这段清单：

```json
{
  "key": "point",
  "label": "参考点",
  "type": "object",
  "required": true,
  "properties": [
    {"key": "x", "label": "X", "type": "number", "required": true, "unit": "mm"},
    {"key": "y", "label": "Y", "type": "number", "required": true, "default": 0}
  ]
}
```

工作台和 `OperatorPlugins.run` 支持命名输入；通用 Node-RED 节点的配置编辑器尚未增加命名输入/递归字段表单。其既有插件参数和消息桥回归已通过；不把它视为本轮新增 UI 的验收范围。

返回 `result` 字典；可选 `image/annotatedImage/cloud/depth/variables`，遵循现有脚本契约。省略数据通道时保留输入；cloud/depth 显式为空值时清除。结果可以经输出绑定表写入变量。标准输出进入运行日志，结构化数据按表格展示。整个子进程响应当前限制 2 MB，适合检测结果和中小数据输出；大图/大点云应等待后续数据句柄接口，不通过本接口返回超大数据。

Python 解释器沿用 `VISION_PYTHON` 或项目 `.venv`。第三方依赖需要管理员预先安装并锁定版本；安装命令不会联网安装依赖或运行安装脚本。示例亮度算子使用项目已有 OpenCV/Numpy，质心算子仅使用 Python 标准库。

在项目根目录执行（Windows/Linux 相同）：

```sh
node scripts/operator-plugin.cjs validate /path/to/my-plugin
node scripts/operator-plugin.cjs install /path/to/my-plugin
node scripts/operator-plugin.cjs list
```

`install` 复制清单、声明的入口及可选 README/LICENSE 到数据目录。已有 ID/目录会拒绝覆盖。安装后重启服务；到“插件管理”检查状态，再从“算子插件”工具箱点击或拖入节点。

更新现有插件时，先停止服务并备份整个数据目录和原插件，人工替换经验证的新版本后启动。旧工程会明确提示版本不匹配。参数面板的“采用已安装版本并重置参数”用于显式迁移到当前版本，须重新配置和保存工程。自动迁移、在线市场、依赖隔离、签名校验和热更新不在 v1 能力内。

启停状态保存在数据目录 `operator-plugin-state.json`，不是工程文件的一部分。停用保留节点配置及原版本；恢复启用后原工程可继续运行。

## 演示与验收

新增两个可独立安装的检测包，原 `sieans-inspection` 版本保持 1.0.0：

| 插件 | 算子 | 使用说明 |
|---|---|---|
| sieans-regions 1.0.0 | HSV 色彩区域、灰度斑点分析 | [参数、坐标与像素面积](../operator-plugins/sieans-regions/README.md) |
| sieans-surface 1.0.0 | 3D 基准/拟合平面偏差 | [符号、公差带与测量限制](../operator-plugins/sieans-surface/README.md) |

新算子增加 12 项已知数值测试，以及 HTTP 下的色彩掩膜→斑点串联、3D 超差着色、变量绑定和工程保存测试。`scripts/generate-inspection-samples.py` 可复现合成图与点云、三项演示；不修改用户工程。

“演示案例”新增亮度检测和点云质心两项。前者对合成零件图输出 294000 像素、平均灰度约 27.308724，写入 `brightnessOK`；后者对箱体采样输出质心 (10, 5, 2.5) mm。采样质心不等于实体质量重心，不承诺真实物体质量测量。

- `node --test tests/test_operator_plugins.cjs`：10 项测试，真实 Python 入口、已知 2×2 灰度数据均值/标准差、已知点云质心、契约拒绝、变量回滚、版本/停用、取消/超时、本地安装、重复 ID、通道清除。
- `npm test`：43 项 Node 测试、11 项 Python 2D 测试；HTTP 插件发现、启停、活动作业锁、工程持久化、真实执行及变量绑定，以及现有 Node-RED ZXing 集成。
- `node --test tests/test_cloud_runtime.cjs tests/test_depth_runtime.cjs`：9 项点云/深度回归。
- 浏览器验证插件表、启停、参数表、亮度结果和输出绑定。其余现场设备与 Linux 验收仍按平台清单推进。

## 上游依据

[Node-RED 包装文档](https://nodered.org/docs/creating-nodes/packaging)说明节点包的清单、版本、依赖和本地测试方式；本实现采用适合 SIEANS Python 作业的独立契约，没有复制 Node-RED 加载器。[OpenCV 官方仓库](https://github.com/opencv/opencv)是亮度示例使用的算法库，沿用项目已安装版本。本次没有新增或下载安装外部算法依赖。

## Node-RED 通用节点

集成版 Node-RED 的“扩展算子”节点可选择同一插件清单，参数使用表单/点位表，支持上游消息字段绑定、固定版本和取消。用法、消息通道及与工作台持久化变量的边界见 [Node-RED 桥接](node-red-operator-bridge.md)。

## 2D 卡尺与显示图像通道

内置 [sieans-caliper](../operator-plugins/sieans-caliper/README.md) 提供边缘直线拟合与双边缘测宽，参数和结果由清单生成表格。演示涵盖离群点、倾斜条带、超差与无边缘。

脚本和插件可以返回 `annotatedImage` 作为独立显示图；它不改变下游图像。`image` 仍为算法数据通道，省略时保留输入，空字符串清除。未提供 `annotatedImage` 的旧插件行为不变：显示图仍来自 `image` 或输入图。运行结果在独立显示图存在时另带 `image`，供输入预览使用；归档关闭数据帧时同时移除这两个图像字段。

## 三维球面插件

[sieans-sphere](../operator-plugins/sieans-sphere/README.md) 增加 RANSAC/几何优化球面拟合与径向偏差检测。球面模型可经三级变量或 Node-RED 消息绑定传递；单位和坐标系不一致时拒绝执行。参数、模型、结果均由字段表和明细表展示。依赖锁定 SciPy 1.18.1，安装说明见插件文档。


### 圆柱拟合与侧面检测

[sieans-cylinder](../operator-plugins/sieans-cylinder/README.md) 提供自由轴圆柱拟合和侧面偏差算子，沿用 NumPy/SciPy 依赖。圆柱模型通过三级变量或 Node-RED 的 payload.cylinder 传递，单位/坐标系严格一致；表单、明细表、着色与五项演示已接入。

### 几何关系与参考点云偏差

[几何关系算子](geometry-relations.md) 提供两直线交点/夹角和两平面夹角/参考间距，附带角度上下限判定。[参考点云偏差检测](cloud-deviation.md) 基于 Open3D 双向最近点距离检查偏移与缺失采样。参数表及结果可使用现有变量绑定。五条演示已通过带登录与写入校验的真实 HTTP 执行；证据为 `artifacts/geometry-http-acceptance.json`，不代表实物精度或当前旧预览已经加载。

管理员可在支持新接口的服务中点击“重新扫描插件”。流程、连续运行或 MQTT 事件会话活动期间拒绝扫描，插件启停状态保留。扫描更新已安装源码和元数据，不替工程升级固定版本。旧服务未声明能力时隐藏按钮；需要正常重启一次以加载新增接口。演示卡片会检查插件缺失、停用、版本和算子是否匹配，再允许载入。


### 参数表逐单元格绑定（候选 6 之后的源码）

声明 columns 的参数表中，每个单元格均可通过“绑定变量或结果”选择现有变量或上游字段，再用“使用固定值”恢复列默认值。运行时先解析绑定，再按清单检查值类型和范围；例如直线起点 X 可以绑定上游直线模型的起点坐标，平面 c 可绑定流程法向量。模块范围指当前模块变量，其他模块输出应通过上游结果或流程/全局变量传递。原有整表绑定保留。演示中的直线 X 和平面 c 已采用单元格绑定；已冻结候选 6 不包含此后续改动。


2026-10-17 浏览器单元格验证：实际载入双卡尺演示，在展开编辑中将起点 X 从上游绑定切换为固定数值，再用来源/模块/字段选择框恢复第一卡尺的 line.start.0；关闭表单并重新执行，交点 (159.490868,119.490815)、夹角 89.999956°。未输入 JSON；这是页面内改参和执行验证，不包含本次修改保存后重启的持久化验收。截图及范围见 artifacts/table-cell-binding-browser-acceptance.json。
