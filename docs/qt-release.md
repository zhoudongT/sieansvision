# Qt 用户级交付

适用 Ubuntu 24.04 x86_64 / ABI 兼容 Linux；glibc 和图形驱动由宿主提供。不是跨发行版通用镜像。
`python3 scripts/package-sieans-qt.py --output artifacts/release/<new-name>` 从已构建二进制、Qt6.7.3、用户 ORT/Tesseract 及依赖闭包装配；不联网、不 sudo、不含 FreeCAD、用户工程、偏好或真实设备 SDK。
同一输入内容及 Git 提交产生确定顺序/mtime 的 `.tar`，SHA256SUMS 校验文件；dirty 构建明确标记，RELEASE.json 记录源提交与 ABI/依赖来源。不能把同输入重打包等同跨工具链 bit-for-bit 编译复现。

解压或移动目录后执行 `./doctor.sh`（装前只读完整性/动态库检查，不要求编译器）；`./run.sh` 可直接启动。
`./install.sh "$HOME/.local/opt/sieans-<version>" --desktop` 安装到全新用户目录并创建版本独立 .desktop；拒绝覆盖旧安装。移动后需重新生成桌面项。无自动删除/升级现场工程。
`VERSION` / `RELEASE.json` / `notices` 随包保留；外部分发前审查第三方许可证与对应源码交付责任。

出厂工程仅 127.0.0.1 TCP 软件环回，打开有样张、不自动运行。GenTL/真实 PLC/官方模型均未验收。无官方模型时明确 software fallback，smoke ONNX 仅证明调用链。
运行时产物写 `$XDG_DATA_HOME/sieans`（缺省 ~/.local/share/sieans），发行目录无需可写；工程保存应另存用户路径。
Qt 日志每 PID 会话独立，2MiB×3 轮转，保留最近约20个已退出会话；`SIEANS_QT_LOG_LEVEL=debug|info|warning|error`。
Qt fatal/critical 保留 stderr，正常退出标记 session-clean-exit；信号崩溃只由回归监督器记录退出码，不声称有 crash dump/自动恢复。日志可能含工程变量，发给他人前脱敏。
状态栏 P95 是最近200个完整软件流程 nearest-rank（含 n），不含触发等待、相机曝光、现场链路端到端延迟。

回归：`python3 scripts/verify-qt-delivery.py --cycles 40`：20项隔离自测、FORCE_SEED smoke、同进程有界 soak、并发独立实例，产出 JSON 和日志。可指定 `--launcher <bundle>/run.sh` 验证搬迁包。测试使用临时 QSettings/历史目录，最大每进程330秒；不会停止用户窗口。

## 回归界限

同进程 soak 以完成的真实软件流程次数计数，不是重复启动冒充长跑；RSS 来自 /proc，采集 FD 和本次 PID 持有的 loopback 监听端口，退出后逐一 bind 检查释放。
64MiB 后半段 RSS 增长是有界回归预算，不是无内存泄漏证明；单次 P95 会随并行编译/负载变化，不能作工厂产能承诺。
`SIEANS_QT_LOG_MAX_BYTES=16384` 在 soak 中强制覆盖默认2MiB，实际验证三文件轮转上限。原生库直接写 stderr 的输出不经过 Qt 等级过滤，启动控制台文件仍需运维留意；不宣称捕获所有第三方诊断。
严格 YOLO 自测设置 `SIEANS_QT_REQUIRE_ONNX_SELFTEST=1`，缺 ORT/桩时失败而非静默跳过；额外验证缺模型/损坏 ONNX 的诚实 software 回退。
