# VisionMaster 风格流程编辑对照

2026-10-23，以本机 VisionMaster 4.4.50 的公开 XML API 文档和托管接口元数据为依据，增强现有 SIEANS 自由连线编辑器。此记录描述功能语义对照，不表示像素级复刻、工程文件互通或厂商插件二进制兼容。

## 使用方式

- 自由拖动节点；输出端口连接输入端口。已有多入、多出、条件分支和汇合继续按依赖运行，画布位置不决定执行顺序。
- Ctrl / Command 点击多选；Shift 在画布空白处拖动框选；拖动选中模块可成组移动。
- 工具栏可复制、粘贴、删除、撤销、重做。流程区域内支持 Ctrl / Command+C/V/Z、Ctrl+Y、Ctrl+Shift+Z、Ctrl+A、Delete；文本框保留原生快捷键。
- 右键模块可配置、重命名、复制、粘贴、删除；F2 打开名称表单。名称最长 80 字符，随工程保存。
- 点击连线后再点击工具箱算子，将模块插入该连线。右键连线也可选择插入或断开；Esc 取消。原始条件保留在进入新模块的连线上，原来选中的数据来源才被改接；其他上游依赖不变。
- 复制保留参数、模块初始变量、内部连线和同流程上游引用；新模块使用新 ID，递归重映射内部 `results` 引用。运行中的变量值不复制，输出变量绑定仍沿用原配置，可在输出表中修改。
- 撤销历史只存于当前浏览器，最多 50 步，并按约 24 MiB 字符存储预算提前截断。打开工程、进入/退出子流程和重新载入时重置，避免跨流程误粘贴。超出预算的单个当前快照仍保留。

## 证据与实现映射

只读目标：`C:/Program Files/VisionMaster4.4.50/Applications/myLibs/`，未拷贝厂商 DLL、源码或资源进仓库。

| 证据 | 已观察声明 | 本平台实现 |
|---|---|---|
| `VMControls.WPF.xml` | `DataForUI.Clipboard.copyInfos`、`VmModuleDecorator.IsUnsupportCopyParams` | 多选复制/粘贴、参数和内部引用重映射 |
| 同上 | `VmConnectionDecorator.InsertModule` / `DeleteConnection` | 选中连线插入模块、断开连线 |
| 同上 | `DiagramItem.Connect`、`GetAllConnectors`、ConnectorInfo.Position/Orientation | 沿用已有自由布局、上下左右端口、多个输入输出 |
| 同上 | `UnRedo_NameData.ModuleFullName` / `OldName` / `NewName` | 模块名称表单、持久化和撤销 |
| REA 接口元数据 | `IUnRedo.StepBack_Connection/Module/Config/CopyModules` 及对应 StepForward；`IUnRedoSchedule.CanUndo/CanRedo/Undo/Redo` | 当前工程编辑快照撤销/重做 |

REA `VMControls.Interface.dll` 成员证据：`ev_e0c9e67313a985b7a319cf58ad052a00546fe0a3b0788560fe9ff149540dec79`，覆盖为 partial。这里只引用实际返回的声明。

REA `VMControls.WPF.dll` 成员证据：`ev_92f770141cfc3e5989ea6eb075d885fdcc0fae1610254db7311e9424c35ecd92`，因 64 MiB 元数据表示预算而 unavailable；未重复扫描或据此推测内部实现。多选手势、历史容量和样式属于 SIEANS 实现选择，未以 VisionMaster 运行画面逐项验证。

## 验收

`node --test tests/test_flow_edit.cjs tests/test_flow_graph.cjs tests/test_subflows.cjs tests/test_error_routes.cjs`

覆盖复制后引用隔离、同流程上游保留、跨流程拒绝、条件插入、数据/依赖区分、组删除、历史分支和容量、既有执行/子流程/错误路由，共 36 项通过。

隔离浏览器预览使用 1931 端口及 `artifacts/vm-alignment-preview-data`：已验证节点插入、Ctrl 多选复制/粘贴、撤销/重做、成组移动、右键重命名、保存重新加载、Delete 只删除选中连线。未启动生产相机服务。

插件输入/参数/输出契约和边界见 [插件对照](visionmaster-plugin-contract.md)，制作方法见 [算子插件](operator-plugins.md)。当前没有厂商原生 DLL ABI 加载、厂商工程导入、动态端口生命周期或完整 VisionMaster 编辑器行为等价验证。
