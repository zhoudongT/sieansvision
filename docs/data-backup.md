# 运行数据备份与恢复（0.3.0 开发版）

维护工具需要 Node.js 24 和 Python 3.12，使用 Python 标准库，无需额外安装 ZIP 库。当前提供命令行入口；不在浏览器中展示配置源码。0.2.0 已发布压缩包不含此功能。

## 备份

先正常停止使用该目录的服务以及外部训练、模型下载和文件写入程序。工具不会自动停止服务；备份期间取得与服务共用的数据目录锁，运行中的服务或另一次维护会使备份拒绝。数据须在程序目录之外，源码默认 `data` 目录需先离线迁移到外部目录。

```powershell
node scripts/platform.cjs backup --data-dir 'D:\SIEANS\runtime' --output 'D:\Backups\vision-20261016.zip'
node scripts/platform.cjs backup-info --archive 'D:\Backups\vision-20261016.zip'
```

默认使用部署配置中的 Python 和模型目录。没有部署配置时使用当前程序 `.venv`；额外模型目录用 `--models-dir` 指定。模型源目录必须与程序目录分离。可用 `--python` 指定维护解释器。

备份包括工程、流程与 Node-RED 隐藏凭据密钥、变量、历史、运行监控、训练数据/标注/训练任务、自定义数据目录插件、插件启停、设备配置和部署配置。位于数据目录内的模型只保存一次；独立模型目录另行打包。空目录与隐藏文件也保留。根目录的 `cache`、`logs`、运行锁及恢复标记不备份。程序、程序目录内插件、Node/Python 依赖、厂商 SDK、系统服务配置及数据目录之外的其他引用文件不包含在内，需要分别迁移。

输出必须是数据、模型和程序目录以外的新文件；已有备份绝不覆盖。工具流式计算每个文件的 SHA-256，检查复制前后大小、修改时间和目录集合；外部程序并不遵守目录锁，因此仍须停止所有相关写入。异常退出可能留下未完成的输出预留文件或唯一临时文件，检查后改用新文件名重试。

备份包含密钥、地址和图片，应放在具有适当访问权限的目录。ZIP 不加密；摘要用于完整性检查，不代表发布者签名。只恢复可信备份，恢复后的 Python 插件和流程可以包含可执行代码。

## 恢复到新目录

```powershell
node scripts/platform.cjs restore --archive 'D:\Backups\vision-20261016.zip' --data-dir 'D:\SIEANS\runtime-restored' --python 'D:\SIEANS\app\.venv\Scripts\python.exe'
node scripts/platform.cjs doctor --data-dir 'D:\SIEANS\runtime-restored'
node scripts/platform.cjs start --data-dir 'D:\SIEANS\runtime-restored'
```

Linux 使用相同命令结构，例如 `--data-dir /var/lib/sieans-restored --python /opt/sieans/.venv/bin/python`。尚未在 Linux 实机验收；Windows 的验证结果不能代替跨系统验证。

目标必须是尚不存在且位于程序目录之外的新目录，已有空目录也拒绝。先完整校验归档再创建目标，随后持有目录锁、写入恢复标记、逐文件校验与解压；不覆盖现有运行数据、不自动启动服务。恢复失败或进程中断时保留目标及 `.sieans-restore-incomplete`，服务会拒绝启动该目录。保留现场排查，重试时选择另一个新目录；不要仅删除标记来绕过检查。

恢复时自动改为当前 Python、重新定位模型目录。独立模型写到新数据目录内的唯一 `.sieans-models-*` 文件夹。保留原来的功能选择、管理员账户、密码哈希和端口；默认改为本机监听 `127.0.0.1`，明确传入 `--host` 可恢复局域网监听，仍需有效的管理员密码哈希。环境变量 `ADMIN_PASSWORD_HASH` 与普通 `configure` 一样可覆盖密码哈希。

原始部署配置与恢复回执保存在唯一 `.sieans-restore-*` 子目录，供维护核对；它们不会作为活动部署配置加载。操作员用户名/密码哈希和已发布运行快照一并保留。工具不重写工程中的自定义脚本绝对路径、外部资源、相机/PLC 地址或第三方 Node-RED 节点配置。跨操作系统时需要核对这些项目以及文件权限和驱动。

## 校验范围

当前格式上限为 100000 个文件及目录、20 GiB 解压总量、单文件 5 GiB。拒绝路径穿越、大小写/Unicode 冲突、Windows 保留名称、链接/设备文件、清单外条目、加密或非支持的压缩方式；SHA、ZIP CRC 或大小校验失败会停止操作。目录锁适用于本机磁盘，不支持多主机共享写入。失败不会自动删除部分恢复目录。

`npm run test:backup` 验证格式校验、异常拒绝、目录锁、失败标记、部署路径与认证迁移，以及真实 HTTP 工程/变量/历史/训练图片和标注/模型的备份恢复。未承诺跨数据格式自动迁移、自动回滚、物理设备或 Linux 验收。
