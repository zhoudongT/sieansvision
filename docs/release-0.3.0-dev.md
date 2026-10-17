# SIEANS Vision 0.3.0-dev 开发候选包

此候选汇总 0.2.0 之后的开发功能，供独立安装、联调及验收，不表示工业设备、Linux、GPU 或全部界面已通过验收。已有 0.1.0/0.2.0 发布包保留不变，当前版本号继续为 `0.3.0-dev`。

候选 5 归档为 `SIEANS-Vision-0.3.0-dev-candidate-5.zip`，附同名 `.sha256`；其独立安装结果以同名 `-acceptance.json` 回执为准。候选 2 的既有验收基线仍保留为 `SIEANS-Vision-0.3.0-dev-candidate-2.zip`。候选 1 保留，候选 2 修正解压包验收脚本中管理员用户名与配置不一致的问题，运行软件功能不因此变更。

## 候选 5 增补

- [网页登录、退出与会话](web-login.md)：已有账号登录、角色入口、空闲/最长过期、可信人工活动续期、同源与写入校验、账号变更撤销及登录失败限流。
- 操作记录按当前筛选条件导出全部保留记录 CSV，支持中文/BOM/UTC、表格公式文本处理；管理员权限与存储异常拒绝。
- 非浏览器 Basic API 与 Node-RED 独立登录保留。未配置管理员密码时仍为本机开发模式，不创建默认密码；退出不停止后台检测。
- 本候选的新增能力在独立安装目录执行 `npm run test:sessions` 和 `npm run test:operator-access` 验证；原解压包验收继续同时设置 `SIEANS_ACCEPTANCE_RECENT=1`、`SIEANS_ACCEPTANCE_INPUTS=1`。实际结果以候选 5 同名回执为准。
- 原候选 4 与历史回执保持原样。候选 5 不代表 Linux、系统服务、真实设备/工件、局域网或原生浏览器验收完成。

## 候选 4 增补

- 部署账号一致性预检与只读账号/记录诊断，拒绝冲突配置并保留原文件。
- [操作员点云文件输入](operator-cloud-input.md)：显式单位、导入预览、单次及固定策略连续测量。
- 图像异步读取保护：读取时禁止启动，清除/切换发布方案/重选后忽略迟到回调，失败输入须重选或清除。
- 增补独立解压包验收路径；结果以候选 4 同名回执为准。此前冻结的候选 3 ZIP 保留不变。

## 候选 3 纳入的后续能力

- [轮廓建模与多目标匹配](../operator-plugins/sieans-shape/README.md)。
- [3D 定向包围盒](../operator-plugins/sieans-box/README.md)与角点、尺寸公差表。
- [PNG16 深度文件导入](depth-file-import.md)与显式内参投影。
- [OPC UA 单点有界订阅等待](opcua-wait.md)。
- [运行诊断与有限压力验证](runtime-diagnostics.md)，不代表 24/72 小时现场运行通过。
- [多操作员账号与操作记录](accounts-operations.md)，不代表完整安全审计。
- [按已发布设置执行操作员连续检测](operator-continuous.md)。

## 原候选能力

- [圆孔/双圆测量](../operator-plugins/sieans-circle/README.md)：径向卡尺、稳健拟合、直径、公差、中心偏移与理想圆壁厚。
- [多目标模板与定位跟随](../operator-plugins/sieans-fixture/README.md)：旋转/缩放去重、唯一目标保护、点位转换、校正图像接后续检测。
- [倾斜基准高度/体积](../operator-plugins/sieans-heightfield/README.md)：独立基准、法向网格、覆盖/层叠诊断，正/负/净观测体积估计。
- [眼在手上标定](../operator-plugins/sieans-handeye/README.md)：棋盘位姿、姿态表求解及独立验证，尚需真实机器人/相机准确度验证。
- [记录算子](../operator-plugins/sieans-records/README.md)：字段创建、累积、去重、筛选、排序、映射、数值统计及有界采样。
- [管理员发布/操作员运行](operator-access.md)：固定服务器保存工程快照、脚本信任、操作员独立 HMI、输入组件范围和修订校验，后台权限隔离及内置 Dashboard 连接保护。
- [HMI 点云窗口](hmi-cloud.md)：旋转/缩放/平移、着色及有界预览，计算数据保持完整。
- [运行数据备份/恢复](data-backup.md)：隐藏凭据、工程/变量/历史/训练数据和独立模型，完整性校验、新目录恢复、账号与发布快照保留。

参数/变量/模型和结果继续采用功能表单与表格。Python 源代码在开发编辑器中查看，操作员不能提交新流程/参数或读取未发布数据；可信代码仍以服务账户执行，不是进程沙箱。

## 安装与迁移

要求 Node.js 24、Python 3.12，交付为源码 ZIP 加在线安装。包内不含 Node/Python 运行时、依赖目录、模型权重、SDK、设备驱动、凭据或用户数据。解压到新的程序目录，运行数据与模型保持在程序目录之外，按 [部署说明](deployment.md) 安装和配置。

先保留旧程序和数据备份，用备份副本验证新版本，再考虑现场切换。新 HMI/发布快照等格式不能假设旧版本可读；回退使用升级前的备份，不能直接让旧程序读取新版本修改过的数据。无自动跨格式迁移或一键回滚保证。

启用管理员认证后，Node-RED HTTP 运行入口与内置 Dashboard 连接也需管理员认证。原有无凭据外部调用需要调整；操作员账户只使用独立运行页。生成的系统服务配置仍需在目标系统安装及验证。

## 验收入口

- `npm test`：工作目录的核心、算法、HTTP 和 Node-RED 集成回归；具体数量和跳过项以执行日志为准。
- `npm run check`：源代码和编辑器脚本语法检查。
- `SIEANS_RELEASE_ROOT` 指向已解压并独立安装依赖的程序后，执行 `node tests/test_deployment_http.cjs`，可用 `SIEANS_DEPLOY_TEST_FULL=1` 扩展 2D/3D、相机模拟、通信、标定和 HMI 验证。
- `npm run test:release-030`：强制使用候选包自己的 Node 模块/Python `.venv`，验证多目标/跟随、圆孔、手眼、记录、倾斜体积、操作员点云 HMI、备份/恢复及恢复后再次执行。需先设置 `SIEANS_RELEASE_ROOT`；候选 3 另设 `SIEANS_ACCEPTANCE_RECENT=1` 强制验证上述新算法、深度、OPC UA、诊断、多账号与连续检测及备份恢复。候选 4 同时设置 `SIEANS_ACCEPTANCE_RECENT=1` 和 `SIEANS_ACCEPTANCE_INPUTS=1`，另验点云文件导入、连续测量、部署预检与输入保护文件；迟到读取行为另由包内 `npm run test:operator-access` 验证。`SIEANS_ACCEPTANCE_REPORT` 可指定一个新验收回执文件。

候选包的实际 SHA-256、安装环境和执行结果保存在同次验收记录中；测试命令的存在不等于通过。归档完整性检查不是发布者数字签名。

候选 2 当时的工作目录完整回归为 235 项 Node 和 152 项 Python 通过，另 1 项 POSIX 专用用例在 Windows 跳过；HTTP/Node-RED 集成通过，日志为 `artifacts/integration-030-full-test.log`。独立依赖安装、实际包运行及恢复回执另存于验收目录。源码 ZIP 可重复生成不表示所有传递依赖已跨平台锁定；本次实际 Python 解析结果另存 `pip freeze` 记录。

## 明确尚未完成

真实海康/大华及其他工业/体积相机、厂商 CTI/SDK、硬件同步、PLC/机器人现场通信与精度；真实工件模型训练和 GPU/深度 SDK 新环境验收；Linux/系统服务安装；新界面真实窗口可视验收；长期压力与数据库、更多设备事件订阅、登录会话/注销、完整安全审计及离线交付。完整平台目标仍按 [实施清单](platform-roadmap.md) 推进。

当前验收机未安装 WSL 发行版，且未发现 Docker/Podman，不能执行 Linux 实机验收。候选包提供的 sh/systemd 文件与 Windows 上的通过结果不能替代目标 Linux 主机测试。

2026-10-16 用户确认暂时没有 Linux 测试环境，Linux 实机验收继续待验，不安装额外系统。
