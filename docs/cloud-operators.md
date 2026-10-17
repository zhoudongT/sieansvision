# 3D 点云输入、流程与检测

开发工作目录新增 [旋转包围盒尺寸](../operator-plugins/sieans-box/README.md)，提供凸包优化后的长中短边、公差、角点与原坐标轴尺寸对照。原始点云保留，不把包围体积称为实体体积，不作为唯一工件定位姿态。

新增 [3D 对应点标定与坐标转换插件](../operator-plugins/sieans-rigid/README.md)，用于已知同名物理点的相机/工装坐标衔接，与下文从几何特征寻找对应关系的点云配准分别提供。

当前使用 [Open3D](https://github.com/isl-org/Open3D) **0.20.0**，Python CPU 运行。上游采用 MIT，发行包许可证保存在 `third_party/open3d/LICENSE.txt`。这是首批 3D 算子接入，完整平台仍按 [实施清单](platform-roadmap.md)推进。相机单帧数据接入见 [RGB-D 采集说明](depth-camera.md)。百万点实时渲染、三维模型训练和完整体积重建尚未实现。

## 安装和验证

Windows PowerShell：

```powershell
.venv/Scripts/python.exe -m pip install -r vision/requirements-3d.txt
npm run check
npm test
npm run test:3d
```

Linux 使用 `.venv/bin/python` 安装同一 requirements；Linux 实机验证仍待完成。缺少 Open3D 时 2D/脚本继续可用，首次运行相应 3D 算子将返回依赖错误。Open3D 采用延迟导入。

## 使用

1. 在“打开点云”中声明文件坐标单位，然后选择 PLY、PCD、XYZ、XYZN、XYZRGB、PTS 或 JSON。不会按后缀推测单位，也不自动缩放坐标。JSON 中的 `unit` 优先。
2. 在“3D 点云”工具组点击或拖入算子，连接到数据源或上游算子。参数中的“输入数据来源”决定哪一路提供图像及点云，其余连线为执行依赖。
3. 运行后切换“3D 点云”查看输入/当前结果。拖动旋转，Shift+拖动平移，滚轮缩放，按钮复位/俯视。键盘方向键旋转，`+`/`-` 缩放，Home 复位。颜色为原始 RGB、聚类颜色或高度色。
4. 每一步的数值结果显示在表格和可展开字段。ICP 在参数区上传参考点云；非 JSON 文件沿用“打开点云”内选择的单位。参考点云作为 `params.targetCloud` 随工程保存；输入图像和输入点云仅在当前浏览器会话保留。
5. “演示案例 → 3D”提供标准件尺寸、去平面后聚类、网格体积、局部 ICP、深度投影，以及全局定位成功/质量不足两个分支演示，可返回原工程。另有曲面、球面、圆柱插件演示。

当前输入上限为 12 MB 文件、20 万点、有限 XYZ 坐标；聚类上限 3 万点/100 组。显示最多抽样约 12000 点并明确提示，计算仍使用全部已接收点。原始输入不因预览抽样改变。每作业输出总量仍限 40 MB，Python 脚本输出限 2 MB，后续将改为服务器数据句柄以支持更大的数据。

## 数据格式

点云 JSON（坐标单位 `mm` 或 `m`；RGB 可选，值 0–1；frame 是坐标系标识，当前不自动变换）：

```json
{"points":[[0,0,0],[20,10,5]],"unit":"mm","frame":"sensor","colors":[[1,0,0],[0,1,0]]}
```

也可导入 XYZ 数组，用导入窗口声明单位。文件颜色受 Open3D 对相应格式的读取支持限制。当前标准化帧保留 XYZ、RGB、单位、坐标系，以及可选 timestamp/intrinsics/extrinsics；法线、强度和自定义字段尚未保留。

带内参深度 JSON：

```json
{"depth":[[1000,0],[2000,1000]],"unit":"m","depthScale":1000,"frame":"depth-camera","intrinsics":{"fx":2,"fy":2,"cx":0,"cy":0}}
```

投影公式 `z=depth/depthScale, x=(u-cx)*z/fx, y=(v-cy)*z/fy`；0 表示无效深度并跳过，负数/非有限值拒绝。depthScale 是每个声明长度单位对应的原始深度值数量，例中 1000 原始值=1 米。深度图最多 20 万像素。这里假定已去畸变的针孔相机，当前不做畸变矫正、深度彩色对齐或外参变换。

服务接口继续使用 `POST /api/vision/run`：

- 导入：`{operation:"cloud_import", name:"part.ply", content:"文件 base64", unit:"mm"}`，返回标准化 `cloud`。
- 计算：`{operation:"cloud_measure", cloud:{...}, params:{}}`，返回 `result`、`cloud`、`elapsedMs`。
- 流程：`POST /api/vision/runtime/jobs` 可同时带 `image` 和 `cloud`；缺少某算子需要的数据时，该节点报错并回滚运行变量。
- 脚本：`ctx.cloud` 读入点云，可返回 `{result:{...},cloud:{...}}`。未返回时保留输入云；输出仍接受点数、数值、单位校验。结果通过 `{$ref:"results.节点ID.sizeX"}` 等引用写入变量。

Node-RED 对应节点为 `machine-cloud_filter`、`machine-cloud_plane`、`machine-cloud_cluster`、`machine-cloud_measure`、`machine-cloud_height`、`machine-cloud_register`。输入 `msg.cloud` 或 `msg.payload.cloud`；输出 1 的 `msg.payload` 为结果，`msg.cloud` 为处理后的点云；输出 2 的 payload 是点云对象（不自动作为图像显示）。

## 算子和测量含义

| 操作 | 参数和结果 | 边界 |
|---|---|---|
| cloud_filter | `method:voxel` + voxelSize；crop + minimum/maximum；statistical + neighbors/stdRatio；radius + radius/minPoints | 裁剪/去噪后为空时报错；颜色随点保留或体素平均 |
| cloud_plane | distanceThreshold、iterations、output=inliers/outliers/all；返回 ax+by+cz+d、法向、内点数量与 RMS | RANSAC 主平面；最大绝对法向分量规范为正；去除平面也会移除靠近平面的物体点 |
| cloud_cluster | eps、minPoints；返回聚类点数、各自包围盒和噪声数 | DBSCAN 几何分组，不推断工件类别；灰色为噪声 |
| cloud_measure | 三轴尺寸、最小/最大坐标、中心、boundingBoxVolume | 当前坐标系下的轴对齐包围盒；旋转及缺失表面影响结果；非旋转不变测量 |
| cloud_height | baselineZ、cellSize；最小/最大/平均相对高度、面积和 estimatedVolume | 仅对水平基准 +Z 的单值可见表面做网格积分；每格最高点，负高度归零，缺失格不补齐。每格完整面积计入，边缘存在离散误差 |
| cloud_register | method=icp/global；targetCloud、maxDistance、iterations；局部模式可设 initialTransform 4×4，全局模式设体素/搜索/质量门限 | 默认局部 ICP；全局模式使用 FPFH + RANSAC + 稳健 ICP。目标/输入单位必须一致；成功输出使用目标 frame，质量不合格保留输入 |

尺寸单位跟随输入，面积为单位²，体积为单位³。**包围盒体积和可见表面的网格体积都不能直接当作工件真实实体体积。** 对现场工件还需标定、参考坐标系、遮挡覆盖率和实物量具对比。

## 验证证据

- `tests/test_cloud.py`：11 项实际 Open3D 数值测试；含 20×10×5 mm 标准件，已知 5 mm 高度/1000 mm³ 网格积分，缺失格及重复点处理，平面残差，两组聚类，ICP 已知变换恢复，多格式 ASCII/二进制/压缩文件读取，深度投影和无效输入。
- `tests/test_cloud_runtime.cjs`：4 项实际运行时测试；分支数据隔离、汇合选择、Python 输出点云/结果绑定变量、错误回滚、全部五个演示实际执行。
- `tests/test_integration.cjs` 的 TEST_3D 模式：实际 HTTP 文件导入、流程运行、工程持久化、非法格式拒绝，以及真实 Node-RED 3D 测量节点。
- `npm test` 保留 2D、脚本、变量、自由连线、Node-RED 条码流程回归。
- 浏览器查看聚类演示，验证点云显示、俯视/复位/拖动、参数表单、结果表格。

当前测试为本机 Windows 与确定性合成样本。实际工业相机/体积相机、PLC 联动和 Linux 部署仍需要独立的范围匹配验证。

## 球面几何与偏差

开发预览增加 [倾斜基准高度与可见体积](../operator-plugins/sieans-heightfield/README.md)：先用独立基准点标定，再沿法向建立固定 U/V 网格，报告正向/负向/净观测体积及缺测覆盖。与既有 `cloud_height` 的固定 +Z 积分分开选择，五个演示位于“3D”分类。

新增 [球面检测插件](../operator-plugins/sieans-sphere/README.md)，支持球心、直径、内点质量、基准径向偏差与红绿着色；另有覆盖不足的灰色诊断。数据去重/抽样仅用于拟合，最终对全部输入点计算残差。它不是标准最小区域球度或完整体积重建；五项合成演示位于“演示案例 → 3D”。


### 圆柱拟合与侧面检测

新增 [圆柱检测插件](../operator-plugins/sieans-cylinder/README.md)，提供自由轴圆柱拟合、直径判定、独立基准侧面偏差和覆盖不足诊断。模型与点位通过表格显示；采样轴向跨度不代表完整零件长度，侧面模型不检查端面或实体体积。

## 全局定位与精配准（2026-10-16）

官方参考：[Open3D GitHub RANSAC 示例](https://github.com/isl-org/Open3D/blob/main/examples/python/pipelines/registration_ransac.py)、[全局配准说明](https://www.open3d.org/docs/release/tutorial/pipelines/global_registration.html)。沿用已安装的 Open3D 0.20.0/MIT，无新增依赖。适配代码在 `vision/global_registration.py`，入口仍为 `cloud_register`。

选择“全局定位”后，界面直接显示下表的参数；局部模式显示初始矩阵表，原有工程默认使用局部 ICP。切换模式保留工程配置，但运行时不解析隐藏且未使用的参数绑定。

| 参数 | 默认值与含义 |
|---|---|
| voxelSize | 1，跟随点云单位；特征计算前的体素边长 |
| ransacIterations | 25000 次，上限 100000；有界随机搜索 |
| ransacConfidence | 0.999，算法停止概率，非识别置信度 |
| maxDistance | 5，精配准几何对应距离，与点云同单位 |
| iterations | 50，每个精配准阶段的最大迭代次数，上限 500 |
| minFitness | 0.7，输入独立点中落在参考邻域内的最低比例 |
| minTargetFitness | 0.3，参考独立点反向覆盖的最低比例 |
| maxRmsError | 未设置时取 maxDistance / 2，最终对应点 RMS 上限 |

处理步骤：去重 → 体素采样 → 法向与 FPFH → 双向最近特征对应 → RANSAC → 点到点 ICP → 带 Huber 损失的点到平面 ICP → 双向覆盖与 RMS 验收。法向采用相对于点云质心的朝外定向，缺失大部分表面可能影响匹配。

输入/参考各需至少 30 个独立点，特征采样后为 30–20000 点且有足够局部邻域；近似平面、共线、过稀疏数据返回配置/数据错误。双向特征匹配不足、搜索未找到或质量门限不满足时，正常返回 `found=false, passed=false` 和原因，**不返回 transformation**，保留原点云、颜色、坐标系和采集标定。成功时输出输入到参考坐标系的 4×4 刚体矩阵并变换全量点云；颜色、单位与时间戳保留，清除不再适用的原传感器 intrinsics/extrinsics。局部 ICP 成功后也清除旧坐标系标定。

质量不合格不自动使流程作业失败。现场流程应连接“条件判断”，把“是否找到”绑定到开关条件：成立才测量/发送位姿，否则复检。两个新演示均包含此分支。工作台结果显示特征对应数、双方覆盖比例、RMS、判定和矩阵表；Node-RED 未通过状态显示黄色。

八项数值测试覆盖已知大姿态逆变换、独立重采样/噪声/局部缺失、毫米/米、重复点、输入不变与元数据、异形参考拒绝、退化/无效参数及不足双向特征；五项运行时测试覆盖全部七个基础演示、分支跳过和模式绑定。HTTP、工程保存/读取、实际 Node-RED 成功/拒绝链路由 `npm run test:3d` 验证。

这仍是几何配准，不是语义识别或唯一位姿证明。相同/对称几何可能得到多解，门限要按工件、扫描密度、噪声和覆盖范围设定；随机搜索不保证找到正确解。现有视觉进程最多执行 120 秒，停止请求在当前视觉算子返回后处理。合成样本通过不能替代真实深度相机、现场精度、节拍及 Linux 实机验收。
