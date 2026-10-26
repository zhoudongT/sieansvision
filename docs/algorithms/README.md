# 算法、模型与 SDK 下载及配置

本文集中说明 SIEANS Vision 所引用的算法、依赖、模型下载位置和配置方法。适用于仓库 `0.3.0-dev`；版本依据仓库中的 requirements 文件和 package-lock.json，不代表上游最新版。整理日期：2026-10-17。

## 1. 环境与平台依赖

| 项目 | 本项目要求/版本 | 官方下载与说明 | 配置位置 |
|---|---|---|---|
| Node.js | 24.x | [下载](https://nodejs.org/en/download) | 系统 PATH；部署工具检查主版本 |
| Python | 3.12.x，建议 64 位 | [下载](https://www.python.org/downloads/) | 安装时通过 `--python` 指定解释器 |
| Git | 用于获取源码 | [下载](https://git-scm.com/downloads) | 系统 PATH |
| Node-RED | 5.0.8 | [源码](https://github.com/node-red/node-red) · [文档](https://nodered.org/docs/) | 已嵌入平台，由 npm 安装，无需另起 Node-RED 服务 |
| FlowFuse Dashboard | 1.33.0 | [源码](https://github.com/FlowFuse/node-red-dashboard) | npm 自动安装；平台自有运行画面代码位于 public/vision |
| Express / MQTT / Aedes / bcryptjs | 见 package.json | [npm 包索引](https://www.npmjs.com/) | `npm ci` 根据 package-lock.json 安装 |

## 2. 视觉算法与 Python 依赖

以下包默认从 [PyPI](https://pypi.org/) 下载，官方项目链接用于查阅源码和算法说明。应使用仓库 requirements 安装，避免直接升级导致接口变化。

| 算法/依赖 | 锁定版本 | 本平台用途 | 官方源码/下载 | 安装文件 |
|---|---|---|---|---|
| OpenCV | opencv-python 5.0.0.93 | 灰度、滤波、阈值、形态学、轮廓、模板定位、几何测量、相机标定、手眼标定、UVC 采集 | [源码](https://github.com/opencv/opencv) · [Python 包](https://pypi.org/project/opencv-python/) | vision/requirements.txt |
| NumPy | 2.5.4 | 图像/点云数组、坐标和数值运算 | [源码](https://github.com/numpy/numpy) · [下载](https://pypi.org/project/numpy/) | vision/requirements.txt |
| ZXing-C++ | zxing-cpp 3.1.1 | 一维条码、二维码识别 | [源码](https://github.com/zxing-cpp/zxing-cpp) · [下载](https://pypi.org/project/zxing-cpp/) | vision/requirements.txt |
| RapidOCR / ONNX Runtime | rapidocr-onnxruntime 1.4.4 | 文字区域检测、方向分类和文字识别 | [源码](https://github.com/RapidAI/RapidOCR) · [本项目所用版本](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/) | vision/requirements.txt |
| Pillow | 12.3.0 | 图片读写及辅助处理 | [源码](https://github.com/python-pillow/Pillow) · [下载](https://pypi.org/project/Pillow/) | vision/requirements.txt |
| Open3D | 0.20.0 | 点云读写、滤波、法向、分割、聚类、配准及空间查询 | [源码](https://github.com/isl-org/Open3D) · [安装文档](https://www.open3d.org/docs/release/getting_started.html) · [下载](https://pypi.org/project/open3d/) | vision/requirements-3d.txt |
| SciPy | 1.18.1 | 3D 数值计算、优化等算法辅助 | [源码](https://github.com/scipy/scipy) · [下载](https://pypi.org/project/scipy/) | vision/requirements-3d.txt |
| Ultralytics | 8.4.177 | YOLOv8 / YOLO11 目标检测、实例分割与训练 | [源码](https://github.com/ultralytics/ultralytics) · [下载](https://pypi.org/project/ultralytics/) · [YOLO11 文档](https://docs.ultralytics.com/models/yolo11/) | vision/requirements-yolo.txt |
| PyTorch / torchvision | CUDA 配置为 2.11.0+cu128 / 0.26.0+cu128 | YOLO 深度学习计算 | [安装说明](https://pytorch.org/get-started/locally/) · [CUDA 12.8 wheel 索引](https://download.pytorch.org/whl/cu128) | vision/requirements-cuda.txt |

注意：基础 requirements 固定了直接依赖；CPU YOLO 所需 PyTorch、ONNX Runtime 等传递依赖没有全部单独锁定。需精确复现环境时另行保留 `pip freeze` 和对应 wheel，不能把这些 requirements 当作完整离线依赖锁。

### 不需要额外下载模型的算子

预处理、模板定位、卡尺/圆孔/双圆、斑点/色彩区域、清晰度与曝光检查、几何关系、相机内参/手眼/刚体标定，以及平面/球/圆柱/包围盒、点云偏差、高度与可见体积等算子，使用本仓库代码及上述 OpenCV、NumPy、SciPy、Open3D 组件。它们没有独立的“权重下载文件”。

实现入口：`vision/`、`operator-plugins/`。每个插件的参数、输出、示例及限制见对应 README，例如 [2D 定位跟随](../../operator-plugins/sieans-fixture/README.md)、[圆孔测量](../../operator-plugins/sieans-circle/README.md)、[高度体积](../../operator-plugins/sieans-heightfield/README.md)。模板定位需要用户提供适用的模板图像；标定需要实际采集标定数据。

### OCR 模型配置

项目调用 `rapidocr_onnxruntime.RapidOCR`，使用 1.4.4 包默认配置与随包模型资源，不通过平台模型目录选择 YOLO 权重。安装该包时一并获取其资源；可用下列命令定位本机实际安装目录：

```powershell
.venv/Scripts/python.exe -c "import pathlib, rapidocr_onnxruntime; print(pathlib.Path(rapidocr_onnxruntime.__file__).parent)"
```

Linux 将解释器替换为 `.venv/bin/python`。当前平台没有提供自定义 OCR 模型路径表单；若替换字典、检测/识别模型，需扩展 `vision/engine.py` 并校验兼容性。上游新文档可能使用新版 `rapidocr` 包，本项目仍使用上表的 `rapidocr-onnxruntime` 接口。

## 3. YOLO 权重下载、存放和使用

权重不随 Git 仓库分发，平台推理入口读取本地模型，不自动下载。下载入口为 [Ultralytics 官方资源 v8.4.0](https://github.com/ultralytics/assets/releases/tag/v8.4.0)。

| 模型文件 | 用途 | 官方直接下载 |
|---|---|---|
| yolo11n.pt | YOLO11 目标检测 | [下载](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt) |
| yolov8n.pt | YOLOv8 目标检测 | [下载](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.pt) |
| yolo11n-seg.pt | YOLO11 实例分割 | [下载](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n-seg.pt) |
| yolov8n-seg.pt | YOLOv8 实例分割 | [下载](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n-seg.pt) |

官方资源页为下载入口；若直链不可用，到该页核对附件，不用未知第三方权重替代。本项目已有验证记录的分割文件：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| yolo11n-seg.pt | 6182636 | 55ed65c56c91713d23e8402371c6c49a6fd84f257f7dce452e8d70e41dcbe152 |
| yolov8n-seg.pt | 7071756 | a7cd8f929e1903d78a12a48efecab430209f18dc46cb96c3599a5980c63c423c |

本地校验示例：`Get-FileHash 'D:\SIEANS\runtime\models\yolo11n-seg.pt' -Algorithm SHA256`；Linux 使用 `sha256sum`。上述哈希记录不代替上游发布者签名。

存放规则：

- 开发模式 `npm start`：默认仓库根目录 `models/`，可用 `VISION_MODEL_DIR` 指定其他目录。
- 部署模式：默认 `<运行数据目录>/models/`；使用 `configure --models-dir <绝对路径>` 修改，下次启动生效。
- 在工作台选择“YOLO 目标检测”或“YOLO 实例分割”，在模型下拉框选择对应文件，再设置置信度、类别、ROI、推理尺寸和计算设备。
- 检测与分割权重不能混用。分割入口使用可信本地 `.pt`；检测的 ONNX 支持及限制见 [模型说明](../../models/README.md)。
- 默认 CPU，可选择自动或指定 CUDA 设备；界面“计算设备”查看实际可用状态。指定 GPU 不可用会报错，不保证静默切回 CPU。
- 通用权重用于软件演示；实际工件和缺陷需要自己的图像、标注与训练。训练入口提供检测/分割、数据检查、指标和成功后安装权重，详见 [模型训练说明](../../models/README.md)。

## 4. 安装与启动

命令在仓库根目录执行。以下安装命令面向新部署；已有运行服务应先停止，再安装或更换依赖，避免修改在用环境。

### Windows（PowerShell）

先安装 Node.js 24 与 Python 3.12。将 `--python` 后的示例路径换成本机 Python 3.12 的真实位置。运行数据目录必须在程序目录之外。

```powershell
git clone https://github.com/zhoudongT/sieansvision.git
cd sieansvision
node scripts/platform.cjs install --python 'C:\Python312\python.exe' --data-dir 'D:\SIEANS\runtime' --features 2d,3d,industrial,camera,yolo
node scripts/platform.cjs doctor --data-dir 'D:\SIEANS\runtime'
node scripts/platform.cjs start --data-dir 'D:\SIEANS\runtime'
```

安装器执行 `npm ci`、创建仓库内 `.venv` 并安装所选依赖。默认访问 `http://127.0.0.1:1880/vision/`。仅运行流程编辑器可将 features 设为 `core`；不需要 AI 时省略 `yolo`。

### Linux（Shell）

预先安装 Node.js 24、Python 3.12、pip 和 venv 支持，再执行：

```sh
git clone https://github.com/zhoudongT/sieansvision.git
cd sieansvision
node scripts/platform.cjs install --python /usr/bin/python3.12 --data-dir "$HOME/.local/share/SIEANS/Vision" --features 2d,3d,industrial,camera,yolo
node scripts/platform.cjs doctor --data-dir "$HOME/.local/share/SIEANS/Vision"
node scripts/platform.cjs start --data-dir "$HOME/.local/share/SIEANS/Vision"
```

Python 路径按实际安装位置修改。OpenCV/Open3D 和设备 SDK 所需系统动态库、USB 权限按发行版及厂商说明安装；仓库具备 Linux 部署入口，目前尚无 Linux 实机验收。

### 可选 CUDA 环境

项目提供 `vision/requirements-cuda.txt`，使用官方 cu128 wheel 索引。先安装匹配显卡与运行库的 [NVIDIA 驱动](https://www.nvidia.com/Download/index.aspx)，按 [PyTorch 安装说明](https://pytorch.org/get-started/locally/) 核对支持条件。

新 GPU 部署可在上述 install 命令将 `yolo` 换成 `cuda`；安装器会包含 YOLO。维护现有环境时，可在停服后执行：

```powershell
.venv/Scripts/python.exe -m pip install -r vision/requirements-cuda.txt
.venv/Scripts/python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

Linux 替换解释器路径。CUDA Toolkit 不等于显卡驱动，也不等于 PyTorch 已可用；以检测结果及实际推理为准。建议 GPU 与 CPU 部署使用独立程序目录/虚拟环境。

## 5. 相机 SDK 下载与配置

| 设备/接口 | 下载来源 | Python 依赖 | 配置与当前范围 |
|---|---|---|---|
| USB UVC 摄像头 | 操作系统驱动；特殊设备按厂商说明 | OpenCV、cv2-enumerate-cameras 1.4.0 | 相机管理中选择 UVC、设备、分辨率与帧率；工业 USB 相机不一定是 UVC |
| GenTL / GigE Vision / USB3 Vision | 相机厂商的 GenTL Producer（CTI） | harvesters 1.4.3、genicam 1.6.0 | cameras/requirements.txt；配置 SIEANS_GENTL_CTI，之后选择驱动编号和设备 |
| 海康机器人 | [官方 MVS/SDK 下载中心](https://www.hikrobotics.com/cn/machinevision/service/download/?module=0) | 通用 GenTL 依赖，前提是型号有兼容 Producer | 先用 MVS 验证设备；无兼容 CTI 时需另开发厂商 SDK 适配器 |
| 大华/华睿工业相机 | [华睿官网](https://www.huaraytech.com/) 的服务支持/下载入口，获取对应 MV Viewer/SDK | 同上 | 根据具体型号与系统获取 SDK；未声称所有型号已接入 |
| RealSense RGB-D | [官方 librealsense](https://github.com/realsenseai/librealsense) · [发行版](https://github.com/realsenseai/librealsense/releases) | pyrealsense2 2.59.1.11053 | cameras/requirements-depth.txt；相机管理选择 RealSense、序列号、流尺寸、帧率、深度范围 |
| Orbbec RGB-D | [官方 Python SDK](https://github.com/orbbec/pyorbbecsdk) · [发行版](https://github.com/orbbec/pyorbbecsdk/releases) | pyorbbecsdk2 2.1.2 | cameras/requirements-orbbec.txt；先核对 SDK v2 的设备支持，再选择 Orbbec 及流参数 |

CTI 示例路径是占位符，不是项目附带文件。设置后从同一环境启动服务：

```powershell
$env:SIEANS_GENTL_CTI = 'C:\VendorSDK\Producer.cti'
node scripts/platform.cjs start --data-dir 'D:\SIEANS\runtime'
```

```sh
export SIEANS_GENTL_CTI='/opt/vendor/lib/Producer.cti'
node scripts/platform.cjs start --data-dir "$HOME/.local/share/SIEANS/Vision"
```

多个路径：Windows 用 `;`，Linux 用 `:`。SDK、CTI、Python 位数和平台必须匹配；厂商动态库搜索路径、网卡 IP/子网、GigE 带宽、USB 驱动/权限按厂商配置。使用 WinSW/systemd 时也要把相应环境传给服务进程，终端设置不自动进入已运行服务。

RealSense / Orbbec 可通过 install 的 `--features` 增加 `depth` / `orbbec`。厂商驱动、固件及 CTI 不在 pip 安装范围。当前工业/深度相机实物尚待验收，模拟演示通过不能替代硬件连接与精度验收。详见 [采集配置](../camera-acquisition.md)、[深度采集](../depth-camera.md)、[连续采集与缓存](../camera-session.md)。

## 6. 工业通信依赖

| 协议 | 锁定版本 | 官方源码/下载 | 使用配置 |
|---|---|---|---|
| Modbus TCP/RTU | pymodbus 3.16.1 | [源码](https://github.com/pymodbus-dev/pymodbus) · [包](https://pypi.org/project/pymodbus/) | 设备地址、端口/串口、设备编号、功能与寄存器地址 |
| 串口 | pyserial 3.5 | [源码](https://github.com/pyserial/pyserial) · [包](https://pypi.org/project/pyserial/) | 串口号、波特率、校验、超时 |
| OPC UA | asyncua 2.1.0 | [源码](https://github.com/FreeOpcUa/opcua-asyncio) · [包](https://pypi.org/project/asyncua/) | Endpoint、NodeId、读写/订阅、实际服务要求的认证配置 |
| Siemens S7 | python-snap7 3.2.1 | [源码](https://github.com/gijzelaerr/python-snap7) · [包](https://pypi.org/project/python-snap7/) | PLC 地址、机架/槽位、DB/偏移及数据类型 |
| MQTT | mqtt 5.16.1 | [源码](https://github.com/mqttjs/MQTT.js) | Broker URL、主题、QoS 与认证 |
| TCP/UDP | Node.js 内置模块 | [Node.js 文档](https://nodejs.org/docs/latest-v24.x/api/) | 对端地址、端口、数据编码和超时 |

Python 通信依赖统一在 `industrial/requirements.txt`；MQTT 随 npm 安装。协议参数在工作台表单配置，结果通过表格展示。设备端权限、PLC 访问设置与现场写入联调仍需按实际设备确认。

## 7. 路径与配置速查

| 项目 | 开发模式 | 部署模式 |
|---|---|---|
| Python | VISION_PYTHON / 仓库 .venv | install/configure 的 --python，配置保存在外部数据目录 |
| 运行数据 | MACHINE_DATA_DIR / 仓库 data | --data-dir，必须与程序目录分离 |
| YOLO 权重 | VISION_MODEL_DIR / 仓库 models | --models-dir / 数据目录 models |
| YOLO 配置 | YOLO_CONFIG_DIR / 数据目录 yolo-config | 数据目录 yolo-config |
| CTI | SIEANS_GENTL_CTI | 启动服务时继承的 SIEANS_GENTL_CTI |
| 监听 | HOST / PORT | configure 的 --host / --port |

部署配置修改示例：

```powershell
node scripts/platform.cjs configure --data-dir 'D:\SIEANS\runtime' --models-dir 'D:\SIEANS\models' --host 127.0.0.1 --port 1880
```

局域网监听需要先配置管理员密码哈希；账号、运行画面发布及服务配置见 [部署说明](../deployment.md) 和 [管理员与操作员](../operator-access.md)。这些是服务器维护参数，日常算法参数、变量和结果仍通过表单/表格操作。

## 8. 验证、缺失依赖与来源保留

- `node scripts/platform.cjs doctor --data-dir <外部数据目录>`：检查安装依赖与运行配置。
- `npm run test:yolo` / `npm run test:segmentation`：需先准备测试所需本地模型，缺少模型不等同通过。
- `npm run test:3d`：点云链路；`npm run test:cameras` / `test:depth` / `test:orbbec`：相机软件适配检查，不能替代实机测试。
- 包安装提示无匹配 wheel 时，检查 Python 3.12、系统架构和包索引可达性，不应随意改锁定版本。官方文档的最新版本说明不一定对应项目固定版本。
- 模型下拉框没有文件时，检查实际模型目录、文件扩展名、读取权限以及检测/分割类型；CTI 枚举为空先用厂商工具验证设备和驱动。
- `third_party/` 保存已有第三方许可和声明，不包含所有完整算法源码、模型或厂商 SDK。完整来源还应结合 package-lock.json、requirements 和本文官方链接。
- Ultralytics 软件及模型采用其 [AGPL-3.0 / Enterprise 许可](https://www.ultralytics.com/legal)；具体发布方式按实际使用组件与授权确认。其他依赖及 SDK 以各自版本附带许可为准。
- 演示图像 `segmentation-bus.jpg` 来源为 [Ultralytics 官方素材](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/assets/bus.jpg)。软件仓库公开并不改变第三方软件、模型或素材的许可。

本文仅提供下载与配置指引，不在文档维护过程中自动下载模型、安装驱动或更改现有运行服务。
