# 原生桌面引擎协议

`desktop/engine-host.cjs` 是 Qt Widgets 桌面进程独占的 Node 子进程，通过 stdin/stdout 的 UTF-8 逐行 JSON 通信。它直接复用 `Runtime`、视觉 Python 引擎、插件与变量存储，不启动 HTTP 服务、Node-RED 或网页。标准错误输出用于启动诊断。

启动：`node desktop/engine-host.cjs --data <独立目录>`。默认目录为项目下的 `native-data`；不继承旧服务的 `MACHINE_DATA_DIR`、YOLO 配置或相机自动启动。目录有独占锁，两个窗口不得同时写同一目录。启动成功先发送：

```json
{"event":"ready","data":{"protocolVersion":1,"pid":123,"dataDirectory":"..."}}
```

请求格式为 `{ "id": "唯一字符串", "method": "方法", "params": {} }`。响应为 `{ "id": "原请求ID", "result": ... }` 或 `{ "id": "原请求ID", "error": "可显示的错误" }`。单个请求最大 80 MB，未完成请求最多 32 个。请求异步处理，长时间运行不阻塞停止命令。

| 方法 | params | result |
| --- | --- | --- |
| `plugins/list` | 无 | 现有 `OperatorPlugins.list()` 清单数组 |
| `demos/list` | 无 | `{items:[{id,name,category,description,expected,image?,preview?,loadOnly,hasScripts,requirements,available,unavailableReason,autoRun}]}`；素材名相对 `public/vision/samples` |
| `demos/load` | `{id}` | `{item,project,image,cloud,depth,autoRun,requirements}`；`image` 为 data URL 或空串，`cloud/depth` 为标准帧或 `null`；不自动运行或保存 |
| `demos/sample` | `{operation?}` | `{image,cloud,depth}`；`barcode/ocr` 对应二维码/文本图，`cloud_plane/cloud_cluster` 对应场景点云，其余 `cloud_*` 对应箱体点云，默认零件图 |
| `project/validate` | `{project}` | `{valid:true,project:规范化工程,plan:[拓扑排序节点ID]}`；允许未连接草稿，run 时再检查可执行性；错误以 RPC error 返回 |
| `run` | `{project,image?,cloud?,depth?,allowScripts?:false,target?}` | 运行结束时的完整 `Runtime.poll()`，见下文；可信脚本需要显式 `allowScripts:true` |
| `stop` | 无 | 停止连续/MQTT会话和当前执行；有活动执行返回其最终状态，否则 `{state:"idle"}` |
| `status` | 无 | `{state,pid,dataDirectory,workerPids,job}`；仅本宿主的子进程 PID |
| `variables/get` | `{project}` | 当前变量快照 |
| `variables/set` | `{project,state,revision}` | 更新后的变量快照；执行时禁止修改 |
| `runtime/view` | `{project,since?}` | `Runtime.view()` 的变量、监视与最近执行状态 |
| `monitor/ack` | `{projectId,id,comment?}` | 原监视服务的报警确认结果 |
| `camera/list`、`camera/providers`、`camera/inspect`、`camera/capture` | 现有相机参数 | 原相机客户端结果；只有显式请求才执行。预览图为 `annotatedImage`；RGB-D 另有 `cloud`、`depth` |
| `camera/cancel` | `{requestId}` | `{cancelled:bool}`；只取消本宿主对应相机请求，取消连续会话取帧不会关闭连接 |
| `camera/session/status` | 无 | 当前桌面数据目录的会话状态 |
| `camera/session/start` | `{params,intervalMs?,reconnectAttempts?,reconnectMs?}` | 会话状态；强制 `autoStart:false` |
| `camera/session/stop` | `{id?}` | 停止后的会话状态 |
| `models/list` | 无 | `{models:[本地模型文件名]}` |
| `training/status` | 无 | `{busy,datasetRoot,datasets,models,job}`；不启动训练 |
| `training/datasets/create` | `{id,task,names,demo?}` | 创建的数据集；`task` 为 `detect` / `segment`，合成示例只使用 `part` 类别 |
| `training/datasets/check` | `{datasetId}` | 原数据检查服务的 `{summary,...}` |
| `training/annotations` | `{datasetId,action,body?}` | `action` 为 `list/load/save/upload/suggest/history/history_load`，直接复用 `Training.annotate()` |
| `training/start` | `{datasetId,model,device?,epochs?,imageSize?,batch?,learningRate?,seed?}` | 立即返回训练任务；随后通过 status 轮询进度 |
| `training/cancel` | `{id}` | 停止中的任务状态 |
| `training/publish` | `{id,name}` | `{name,task,demo}`；仅成功任务可安装，不覆盖同名文件 |
| `continuous/status` | 无 | 原 `ContinuousRun.status()`；含 `busy`、轮次统计、错误与最近任务编号 |
| `continuous/start` | `{project,image?,cloud?,depth?,intervalMs?,maxCycles?,allowScripts?}` | 当前会话；启动时保存工程与输入快照，次数 `0` 表示直到停止 |
| `continuous/stop` | `{id?}` | 等待本会话退出后返回最终状态；间隔等待会被立即唤醒 |
| `mqtt/status` | 无 | 原 `MqttTrigger.status()`；含队列、完成、丢弃、过期、去重计数 |
| `mqtt/start` | `{project,image?,cloud?,depth?,connection,variable?,keyField?,capacity?,maxAgeMs?,reconnectMs?,overflow?,allowScripts?}` | 原 MQTT 触发会话；连接参数复用 `mqtt-client.config` |
| `mqtt/stop` | `{id?}` | 等待订阅与当前事件退出后返回状态 |
| `mqtt/test` | 无 | 仅已显式开启的本机模拟订阅允许发送测试事件；不向外部 Broker 发送测试消息 |
| `shutdown` | 无 | `{state:"stopped"}`，随后正常退出 |

`run` 保持该请求未决直到算法、变量提交和历史归档结束。示例终态：

```json
{
  "id": "运行UUID",
  "state": "completed",
  "results": [
    {
      "id": "contours",
      "inputFrom": "source",
      "output": {
        "operation": "geometry",
        "result": {"feature":"contours","count":2,"items":[]},
        "annotatedImage": "data:image/jpeg;base64,...",
        "elapsedMs": 4.3
      }
    }
  ],
  "cursor": 1,
  "elapsedMs": 20,
  "archive": {"state":"saved"},
  "variables": {},
  "monitor": {}
}
```

`state` 可为 `completed`、`failed` 或 `cancelled`。算法错误以终态 `state:"failed"` 和 `error` 字段返回；无效请求、工程预检错误以 RPC error 返回。界面应检查两种错误。显示图像优先取节点 `output.annotatedImage`，输出数值取 `output.result`。自由 Python 脚本默认关闭，只有本次请求显式 `allowScripts:true` 才交给原脚本执行器；界面每次启动后清空授权复选框。它是本地可信代码执行机制，不是沙箱。已安装的显式插件节点复用插件运行机制。

所有 RPC 在执行前调用 `management.authorize(method)`。配置管理员密码时须先通过 `auth/login`，开发、设备及训练操作仅管理员可用；未配置时沿用本地开发模式。`auth/status/login/logout` 和 `shutdown` 可在未登录时调用。操作结束调用 `management.record(method,params,ok,elapsedMs)`，审计不记录密码内容。其他工程库、历史、账号、插件管理和 3D 导入方法由 `desktop/management-service.cjs` 分发。`project/validate` 先规范化并校验；返回工程中的 HMI 数据保留源对象的兼容附加字段。

演示库由 `desktop/demo-service.cjs` 读取与网页相同的 31 份清单，保留原顺序的 149 个案例；不复制或重写原始清单。`demos/list` 只读取清单、插件状态和模型是否存在，不启动算法或设备。每次 `demos/load` 创建新工程及节点编号，重映射结果引用、索引绑定、分支边、图像来源、HMI 绑定和子流程内部编号，保留变量及类型定义。点云与深度导入复用原视觉引擎，加载/示例导入占用 Runtime 独占锁，失败及退出都会释放。当前工程的临时备份和返回原工程由 Qt 主窗处理，后端不会写入工程库。

`requirements` 为供界面展示的中文说明；含自由脚本、`loadOnly` 事件触发、缺少本地 AI 权重或非模拟设备的案例返回 `autoRun:false`。权重检查不加载或下载模型。插件停用、缺失或版本不匹配时，清单返回 `available:false` 和 `unavailableReason`，载入以 RPC error 拒绝。只有明确载入连续相机案例才准备模拟会话，并注入当前 session ID；已有其他设备会话时拒绝，不替换连接。关闭演示或返回原工程不释放该模拟连接，可在相机管理中停止，退出引擎统一清理。

训练数据存入独立桌面数据目录下 `training/`，模型目录继续沿用 `VISION_MODEL_DIR` 或项目 `models/`，与推理服务一致。数据检查与训练复用 Runtime 独占锁。标注保存要求 `name/split/revision/records`；版本冲突由原服务拒绝，覆盖前自动保留旧标注。图像导入仍受 12 MB / 1600 万像素限制。模型候选只生成建议，用户逐项指定数据集类别、加入并保存后才写入标注。

相机状态初始化不会调用 `CameraSession.restore()`；应用重开后只恢复状态记录，不自动连接物理相机。`camera/session/start` 强制关闭自动启动。停止流程、取消缓存取帧、关闭相机窗口均不释放连续连接。连续会话取帧的稳定引用为状态中的 `bindingId`，可与 `driver:'session'`、`framePolicy:'next'` / `'latest'` 一起使用。

连续运行和 MQTT 窗口打开只读取状态；启动按钮才提交工程快照。MQTT 默认选择模拟器但不会自动连接；显式启动模拟订阅会创建仅监听 loopback 的临时 MQTT 端口。外部 Broker、TLS、证书与凭据环境变量均由原 MQTT 服务校验。关闭窗口保留会话，退出应用或全局 stop 结束会话。

运行期间可收到 `{event:"progress",data:{requestId,...运行状态}}`。`requestId` 是 RPC 请求 ID，`data.id` 是运行 UUID；`results` 仅含上次通知后的新增记录，`cursor` 是累计结果数。最终 run 响应始终含全部节点结果。

`desktop/backend.py` 提供 `Backend(QObject)`：`start(root:Path,data:Path)`、`request(method,params=None)->str`、`shutdown()`；信号包括 `ready()`、`result(str,object)`、`error(str,str)`、`progress(object)`、`stopped()`。所有过程使用异步 `QProcess`，不会等待阻塞 Qt 事件循环。启动或全局错误使用空请求 ID。`ready()` 在握手后发出，界面应在此后请求数据。

视觉 Python 按 `VISION_PYTHON`、项目 `.venv` 的顺序选择；未打包时可使用当前 Python。冻结打包后只从 PATH 查找真实 Python，找不到会报错，不把桌面 exe 当作 Python 启动。

窗口关闭应先忽略 closeEvent，调用 `shutdown()`，收到 `stopped()` 再允许窗口退出。引擎取消运行、关闭自己启动的视觉/相机/通信子进程、释放数据锁后退出；stdin 关闭同样触发清理。Qt 有 10 秒兜底，只结束自己持有的 QProcess，不按名称扫描或关闭其他 Node/Python 服务。原生端没有 1930 端口或旧网页服务依赖。

`desktop/device_dialogs.py` 提供 `CameraDialog(backend,parent=None)`、`TrainingDialog(backend,parent=None)`、`ContinuousDialog(document,backend,parent=None)`。每个窗口只处理自己 pending 的请求 ID。相机 `camera_selected(dict,bool)` 第二参数表示应用到当前节点，`frame_ready(dict)` 保留完整图像、点云与深度；仅需 2D 的调用者可使用 `image_ready(str)`，不要同时连接两种输入信号。训练 `model_selected(operation,model)` 用于添加推理节点。连续窗口 `set_input(image,cloud,depth)` 接收当前输入，`busy_changed(bool)` 可控制主窗，`result_ready(dict)` 输出轮询到的最新终态结果供主窗更新图像与模块结果；界面轮询可能跳过短间隔中间轮次，所有执行仍由原历史服务归档。该窗口在会话活跃时保持后台轮询，不能设置 `WA_DeleteOnClose`。

验证命令：`node --test tests/test_native_engine.cjs tests/test_native_devices.cjs`、`.venv/Scripts/python.exe -m unittest discover -s tests -p test_native_devices.py`、`.venv/Scripts/python.exe -m unittest discover -s tests -p test_native_backend.py`。新增设备测试仅使用模拟相机、loopback MQTT 模拟器、合成图片、临时数据与无副作用脚本；不枚举或打开物理设备，也不启动实际模型训练。训练安装测试使用临时固定字节产物，仅验证发布与哈希逻辑，不加载该产物推理。

演示回归：`node --test tests/test_native_demos.cjs`。覆盖 149 案例素材与工程校验、清单顺序和哈希、鉴权、脚本/模型门槛、插件停用、Runtime 锁及模拟会话准备；实际运行 2D、3D、条件、子流程/循环、HMI、插件、深度，以及 Modbus、S7、串口、TCP、UDP、MQTT、OPC UA 本机模拟案例。演示测试使用空模型目录，不下载权重、不执行自由脚本、不接触真实设备或训练任务。
