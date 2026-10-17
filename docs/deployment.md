# Windows / Linux 部署

稳定源码安装版为 [0.2.0](release-0.2.0.md)，新增功能以 [0.3.0-dev 开发候选](release-0.3.0-dev.md) 交付。启动器停止等待已改为 45 秒，新生成的 WinSW/systemd 模板为 60 秒；旧模板不会自动更新。发布生成器拒绝改写不同内容的同名发行包，同内容生成保持幂等。

发布形式目前为源码 ZIP 加在线依赖安装，包含网页、Node-RED 节点、独立算子插件及演示。它不包含 Node.js、Python、模型权重、厂商驱动、已有工程或运行数据，也不是离线安装器。应用参数、变量及脚本输入输出仍通过网页表单/表格配置；下列命令用于服务器安装维护，不需要手工编辑后台配置文件。

## 环境与安装功能

- Node.js **24.x**，Python **3.12.x**。安装工具检查实际解释器版本。
- Windows x64；Linux 建议 Ubuntu 22.04 或更新版本。Open3D 的平台依赖见其[官方安装说明](https://www.open3d.org/docs/latest/getting_started.html)。Linux 启动脚本及 systemd 生成逻辑已提供，尚未在 Linux 主机验收。
- npm 使用 `package-lock.json`，Python 使用功能对应的固定直接依赖版本；Python 的所有传递依赖尚未做跨平台哈希锁定。安装需要访问清单内 npm 地址及 pip 软件源。

| 功能名称 | 安装内容 |
| --- | --- |
| `core` | Node-RED、网页、流程控制、Python 标准库脚本与变量；视觉/相机/部分协议节点仍可见，使用前须安装相应功能 |
| `2d` | NumPy、OpenCV、ZXing-C++、OCR |
| `3d` | 2D 依赖、Open3D、SciPy，包括现有独立 3D 插件 |
| `industrial` | Modbus、串口、OPC UA、S7；MQTT/TCP/UDP 依赖随 Node 安装 |
| `camera` | 2D 依赖、UVC 枚举及 GenTL；厂商 CTI/SDK 另装 |
| `yolo` | 2D 依赖、Ultralytics；模型权重另行放入模型目录 |
| `depth` | camera、2D 及 RealSense；设备驱动和 USB 权限另配 |
| `orbbec` | camera、2D 及奥比中光 SDK v2；设备/固件与系统权限另配，详见 [接入说明](orbbec-camera.md) |

不指定 `--features` 时安装 `2d,3d,industrial,camera`。不同功能通过逗号组合，`core` 单独使用。厂商驱动、GPU、现场设备和模型授权需按实际使用的组件配置。

## 发布包生成与校验

开发机执行：

```powershell
.venv/Scripts/python.exe deploy/build_release.py
```

默认输出 `artifacts/releases/SIEANS-Vision-<版本>-source.zip` 和同名 `.sha256`。包内 `release-manifest.json` 记录每个发行文件的 SHA-256；同样的源码生成相同的 ZIP 字节。仅收录明确的程序目录，排除用户数据、虚拟环境、依赖、缓存及模型权重。

解压后进入版本目录，执行：

```sh
node scripts/platform.cjs verify
```

校验会拒绝缺失、改动或链接替换的发行文件。摘要用于发现损坏或不一致，不代表发布者身份签名；新增的外部插件不在原清单中。

## Windows 安装与启动

先准备 Node.js 24 和 Python 3.12。以下路径是示例，按实际安装位置替换：

```powershell
node scripts/platform.cjs install --python 'C:\Python312\python.exe' --data-dir 'D:\SIEANS\runtime' --features '2d,3d,industrial,camera'
node scripts/platform.cjs doctor --data-dir 'D:\SIEANS\runtime'
node scripts/platform.cjs start --data-dir 'D:\SIEANS\runtime'
```

也可用 `deploy/start.ps1 -DataDir 'D:\SIEANS\runtime'` 启动。安装会执行 npm ci、在当前版本目录创建 `.venv`、安装所选 Python 依赖并检查版本及导入能力。不要在正在运行的程序目录执行安装；新版本应解压到新的目录。

## Linux 安装与启动

在目标机准备 Node.js 24、Python 3.12 及其 venv 支持。相机和图像库需要的系统动态库、USB/串口权限由目标机提供。

```sh
node scripts/platform.cjs install --python /usr/bin/python3.12 --data-dir /var/lib/sieans-vision --features 2d,3d,industrial,camera
node scripts/platform.cjs doctor --data-dir /var/lib/sieans-vision
sh deploy/start.sh /var/lib/sieans-vision
```

安装时使用对程序目录和数据目录有权限的维护账户；服务账户权限另行配置。未完成 Linux 实机运行验证，不能把 Windows 测试结果当作跨平台验收。

## 数据、模型、访问地址

0.3.0 开发源码增加 `OPERATOR_USER` / `OPERATOR_PASSWORD_HASH` 及发布运行快照，配置方式和权限边界见 [操作员运行说明](operator-access.md)。启用管理员认证后，Node-RED HTTP 运行入口和内置 Dashboard 连接也需管理员认证；已有无凭据集成需调整。

程序目录与运行数据目录必须分离。数据目录保存工程、Node-RED 流程及凭据文件、变量、运行历史、插件启停状态、部署配置、日志与缓存。数据目录应位于本机磁盘；运行目录锁不支持多主机共享写入。

默认模型目录为数据目录下的 `models`，默认缓存为 `cache` 和 `yolo-config`。需要另存模型或切换端口时使用：

```powershell
node scripts/platform.cjs configure --data-dir 'D:\SIEANS\runtime' --models-dir 'D:\SIEANS\models' --port 1880
```

修改配置在下次启动生效。开发者直接 `npm start` 仍兼容原来的源码 `data`/`models` 路径；部署入口显式传入外部目录。跨目录升级后用 `configure --python <新版本虚拟环境解释器路径>` 更新解释器路径。

默认仅监听 `127.0.0.1`，工作台地址为 `http://127.0.0.1:1880/vision/`，运行画面为 `/vision/?mode=run`。局域网监听需要提供 `ADMIN_PASSWORD_HASH` 环境变量，然后执行 `configure --host <服务器局域网IP> --admin-user <账户>`。密码哈希可以通过已安装 Node-RED 的 `node-red admin hash-pw` 交互生成；不要把明文密码放在命令参数或工程中。配置保存后启动器从数据目录读取哈希，检查输出不打印哈希。

0.3.0 开发候选中管理员维护工作台，操作员通过独立运行页访问已发布快照，后台执行权限隔离；详见 [操作员运行](operator-access.md)。HTTP Basic 应通过 HTTPS 反向代理提供给远程浏览器；本工具不自动打开防火墙或生成证书。

## 系统服务配置

工具只生成新配置文件，不修改账户、ACL 或系统服务，不自动安装第三方服务包装器。

Windows 使用 GitHub [WinSW 2.x](https://github.com/winsw/winsw)；配置格式按其[官方文档](https://github.com/winsw/winsw/blob/v2/doc/xmlConfigFile.md)。

```powershell
node scripts/platform.cjs service --data-dir 'D:\SIEANS\runtime' --format winsw --output 'D:\SIEANS\SIEANSVision.xml'
```

生成文件明确指定 `NT AUTHORITY\LocalService`，服务 ID 为 `SIEANSVision`。管理员须授予该账户程序/Node/Python/厂商 SDK 读取执行权限，以及数据、模型和日志目录所需权限；不要直接使用普通用户私有目录作为服务程序路径。按 WinSW 说明准备同名可执行文件后安装、启动。尚未在 Windows 服务管理器实际安装验收。

Linux 在目标机执行：

```sh
node scripts/platform.cjs service --data-dir /var/lib/sieans-vision --format systemd --service-user sieans --output /tmp/sieans-vision.service
```

由管理员创建专用账户并配置设备和目录权限，再安装 unit。服务配置使用绝对路径；更换程序目录或 Node 路径后需要重新生成。systemd 验收尚待 Linux 主机完成。

## 停止、升级与备份

0.3.0 开发源码新增 `backup`、`backup-info` 和 `restore` 命令，支持隐藏凭据、运行数据及独立模型的校验备份、恢复到新目录和部署路径调整，见 [备份与恢复](data-backup.md)。0.2.0 发布包不包含这些命令。

前台用 Ctrl+C 正常停止。停止时拒绝新请求，取消手动/连续检测，等待运行归档与变量回滚，然后停止工作进程及 Node-RED。已经发生的 PLC 写入或脚本外部操作不能回滚。

同一运行数据目录仅允许一个服务进程；重复启动会拒绝。强制结束可能遗留锁文件，下次启动只恢复本机已消失 PID 的锁，并保留旧锁记录。锁损坏、其他主机、恢复中断或仍有活进程时拒绝接管；须由维护人员查明状态，不应直接删除正在使用的锁。

升级步骤：停止服务 → 备份整个数据目录（包括 Node-RED 隐藏凭据密钥文件）及独立模型目录 → 保留旧版本程序 → 将新包解压到新版本目录 → 安装依赖并使用同一个数据目录配置 → doctor → 启动并验收。自定义插件在程序 `operator-plugins` 或 Node-RED 安装位置，需另行备份、迁移并核对工程固定版本；它们不自动迁入新的程序版本。升级失败时停止新服务，恢复升级前备份并使用旧程序和旧解释器配置。

目前没有跨数据版本自动迁移或一键回滚保证；在首次运行新版本前保留完整备份。历史中的示例图片/参考数据及设备地址会随工程保存，发布包不包含运行数据。

## 验证入口与界限

`npm run test:deployment` 覆盖配置、依赖检查、锁竞争、启动/退出、工程/变量/历史持久化和停止回滚。`tests/test_release.py` 检查 ZIP 可重复生成、内容排除、逐文件摘要和篡改拒绝。`tests/test_deployment_http.cjs` 可通过 `SIEANS_RELEASE_ROOT` 指定解压后的程序目录，`SIEANS_DEPLOY_TEST_FULL=1` 增加实际 2D/3D 流程验证；`VISION_PYTHON` 指定测试解释器。

依赖导入通过不能代替现场工业相机、体积相机、PLC、GPU或操作系统服务验收。平台还需持续采集/设备事件、子流程、角色与审计等能力，完整软件目标仍在进行。

### 2026-10-16 Windows 验收记录

- 完整回归通过 130 项 Node 测试、70 项 Python 测试，另有 1 项 POSIX 串口测试在 Windows 跳过；HTTP/Node-RED 集成通过。日志：`artifacts/deployment-full-test.log`，语法检查：`artifacts/deployment-check.log`。
- 将发布候选包解压到独立目录，真实执行 `install --features core`，新建独立 `.venv`，安装 396 个 npm 包；基础版启动、Python 标准库脚本、工程/变量/历史保存及重启恢复通过。
- 随后在同一独立环境真实安装 `2d,3d,industrial,camera`，依赖版本和模块导入全部通过。运行发布包中的 2D/3D、独立插件、Modbus 模拟读写、模拟图像/深度相机及变量绑定通过，未借用源码环境的 Python 包。
- 生命周期补测覆盖真实执行中的 Python 子进程：停止服务后子进程退出、未提交变量回滚、取消历史保留；监督进程断开和强制结束后的重启恢复通过。
- 安装和运行日志保存在 `artifacts/deployment-acceptance/`。测试数据位于各日志记录的独立临时目录，未覆盖 1880 原工程。
- 没有实际安装 WinSW 服务，也没有 Linux 发行版可供运行；YOLO/RealSense 可选依赖未在本次干净环境安装，不计入此次发布包验收。

## 工作源码：账号一致性预检

工作源码的 `configure` 在写入部署配置和创建新模型目录前，会校验已有的平台操作员账号文件。管理员或部署操作员用户名与平台账号冲突、已有平台账号却清空管理员密码，以及账号文件损坏时拒绝保存，保留原配置。管理员正常改名和密码更新仍按既有配置规则执行。变更部署账号应在停机维护期间进行；保存前校验是当时文件的快照，不保证随后没有其他进程修改账号。

`doctor` 增加平台账号数量/启用数量和操作记录文件状态。账号格式或配置冲突使诊断失败；操作记录文件异常显示非阻断警告，服务仍可启动但记录会暂停追加。检查只读取账号和记录文件，不自动修复、不输出密码哈希或损坏文件原文。配置文件解析失败也只返回通用提示，避免把凭据片段打印到命令行。依赖导入、设备接入、运行时写权限及现场行为仍须按实际环境验证。

验证入口：`npm run test:deployment`。此预检修复在当前工作源码中，先前冻结的 candidate 3 ZIP 保持不变。

候选 4 已纳入上述源码变更，独立安装与运行验证以候选 4 同名验收回执为准；候选 3 及更早的冻结 ZIP 不变。

局域网监听、账号与发布画面隔离验证入口见 [局域网验收](lan-acceptance.md)。当前本机经网卡地址的连接超时，不能视作已通过局域网验收。
