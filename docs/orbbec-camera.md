# 奥比中光 Orbbec RGB-D 单帧采集

使用官方 [pyorbbecsdk GitHub 仓库](https://github.com/orbbec/pyorbbecsdk) 的 SDK v2 Python 绑定，固定发行包 `pyorbbecsdk2==2.1.2`，导入名 `pyorbbecsdk`。参考 [官方应用指南](https://orbbec.github.io/pyorbbecsdk/source/5_Application_Guide/ApplicationGuide.html) 的设备枚举、软件 C2D、点云及标定接口。源码参考快照为 `0f089c9bf6e618e7782228ee6bcf666e3339ae78`；执行接口以实际 2.1.2 wheel 为准。

## 安装和设备选择

已有环境可执行 `.venv/Scripts/python.exe -m pip install -r cameras/requirements-orbbec.txt`；Linux 使用 `.venv/bin/python`。部署工具的 `--features orbbec` 自动包含 `camera` 和 `2d` 依赖；需要点云检测时组合 `3d,orbbec`。SDK 是可选依赖，没有安装时其他相机仍可运行。

工作台“相机设备”选择“奥比中光 Orbbec 深度相机”，枚举、选择设备并读取流配置表，然后添加采集节点。序列号精确匹配；设备不在列表或序列号重复时拒绝采集，不改用第一台设备。读取设备参数会打开设备，但不开始流。

网络发现默认关闭，SDK Context 创建前先从已安装的配置副本禁用自动网络枚举，勾选“发现 Orbbec 网络设备”才启用 SDK 网络发现。此设置随节点保存。当前没有实现手工指定相机 IP、跨网段发现或多设备同步。

默认深度 Y16 640×480、30 fps；彩色 RGB 640×480；预热 5 帧。参数表可配置深度/彩色尺寸、整数帧率、彩色格式、是否采集彩色、超时、预热、点云步长和距离范围。所请求组合必须存在于设备流配置中，不静默降级。设备不支持彩色时取消“同时采集彩色图”。预览使用默认自由采集配置，特殊分辨率或深度单路设备请通过节点设置后运行。

SDK v2 的设备/固件兼容性以官方矩阵为准，不承诺所有 Astra/OpenNI 或其他品牌型号通用。本适配器不执行固件升级。Linux 权限/驱动及 Windows 元数据系统配置应按官方说明完成；此次只验证 Windows Python 3.12。

## 输出与测量语义

- 保留原始 Y16 深度为 16 位 PNG，零值无效。米/原始值 = SDK `get_depth_scale()` / 1000。
- 点云使用原生 `PointCloudFilter` 按标定和畸变投影，独立读取 `PointsFrame.get_position_value_scale()`，再统一为毫米坐标；不能假定 SDK 浮点点坐标本来就是毫米。
- RGB/BGR/MJPG/YUYV/UYVY/NV12/NV21 彩色先由 SDK 转为 RGB，再用 `AlignFilter` 做 C2D。输出图像在深度像素栅格；不是图像缩放对齐。校验对齐前后的深度数值与比例完全保留。
- 内参、畸变模型和系数顺序、深度到彩色外参均保留。旋转是二维行列矩阵，外参平移单位明确为米；点云仍为毫米。彩色内参记录原始彩色流，深度内参对应输出对齐栅格。
- SDK 对齐空白像素没有单独有效性掩膜，所以结果标记“彩色有效覆盖已知”为否；“对齐彩色采样点数”不等于实际有效彩色覆盖数。黑色可能是真实黑色或无彩色覆盖，不能据此判定缺陷。
- 深度/彩色帧号、设备与系统时间戳单独记录，主时间戳为主机接收时间。这不构成多相机或硬件曝光同步保证。
- 限制沿用平台：深度 ≤400 万像素、采样候选 ≤20 万点、总进程响应 ≤35 MB。过滤范围单位米，采样和显示范围不修改原始深度。

工作台结果、设备参数、脚本输入输出、三级变量均使用表格/表单；后台数据通过同一帧协议传给 2D/3D 算子和 Python。Node-RED 采集节点也提供相同驱动及参数表单，深度输出为 `msg.depth` 和 `msg.cloud`。

## 验证证据与边界

运行 `npm run test:orbbec`：9 项 Python 测试（原生 SDK 软件帧及明确隔离的生命周期 mock），12 项 Node 测试（包含既有采集、深度回归）。原生测试验证 0.5 mm 深度比例、无效点、毫米点坐标、旋转约定、7 种彩色格式、不同分辨率和 100 mm 外参偏移；跨进程实际接入 Open3D 裁剪/尺寸测量、Python 原始深度解码及变量绑定。

本机实际 SDK 枚举完成，发现 0 台设备。没有相机实物曝光、USB/网络流稳定性、Linux、断线重连或持续采集验收；不能用软件帧替代这些验证。当前是单次打开/采集/释放，没有后台常驻视频流。

原生转换和回归日志：`artifacts/orbbec-runtime-test.log`。原有 `SIEANS-Vision-0.1.0-source.zip` 是此前发布快照，不含本次新增适配器；使用当前源码测试该功能。

浏览器验证：独立 1899 工作台枚举 0 台设备、按驱动显示 SDK 状态、关闭彩色流隐藏对应字段、保存后刷新保持 Orbbec/MJPG 参数。Node-RED 验证节点的 BGR、关闭彩色流、关闭网络发现参数通过表单保存并部署，随后由管理 API 读回核对；节点未接入触发源，未执行实机采集。截图 `artifacts/sieans-orbbec-camera.png`。
