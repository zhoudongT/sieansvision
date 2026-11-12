# sieans_qt — Qt6 工作台（C++ core）对等波

下层 `native/sieans_algo`（zxing QR + Hikrobot GenTL），上层 **Qt6 Widgets**。
本波对齐 PySide **GenTL→QR 打开即跑** 主路径；`scripts/launch-sieans-vision.sh` 保留不动。

## 布局（对齐工业壳）

| 区域 | 内容 |
|------|------|
| 菜单 | 文件 / 设置 / 工具 / 系统 / 工程管理 / 设备与模型 / 帮助 |
| 左轨 | 算子库（双击添加） |
| 左中 | 真实流程画布（节点+连线）+ 属性面板 |
| 中央 | 图像视图（缩放/拖拽 + 码框叠层，连续预览不强制重 fit） |
| 右侧 | 结果 / 变量监视 / 通信（LocalBus+TCP）三页 |
| 底条 | Host OK/NG 条（hostWatch 键） |
| 工具栏 | 打开/保存 · 相机 · 连续预览 · ▶运行 / ↻连续 / ■停止 · 通信启停 |

## 构建 / 运行

新机器从检出构建、用户级依赖（无 sudo）与自检见 [docs/qt-workbench-setup.md](../docs/qt-workbench-setup.md)。先跑 `./scripts/doctor-sieans-qt.sh` 查看本机缺什么。

```bash
./qtapp/scripts/build.sh
./scripts/run-sieans-qt.sh          # 前台
./scripts/launch-sieans-qt.sh       # 日志 → artifacts/sieans-qt.log
```

环境变量：

- `SIEANS_QT_AUTO_SAMPLE=1` — 启动后加载示例 QR 并解码
- `SIEANS_QT_AUTO_ENUM=1` — 枚举 GenTL
- `SIEANS_QT_AUTO_PREVIEW=1` — 启动连续预览（相机空闲时）
- `SIEANS_QT_AUTO_SOFT=1` — 切到 Soft 仿真相机并连续预览（不需要硬件）
- `SIEANS_QT_AUTO_MATCH=1` — 追加快速匹配并单次运行（可与 `AUTO_SOFT` 同用）
- `SIEANS_QT_AUTO_TCP=1` — 启动后按方案 tcpReal 配置监听/连接
- `SIEANS_QT_SCREENSHOT=/path.png` — 启动后抓窗（配合 `SIEANS_QT_SCREENSHOT_QUIT=1` 可退出）
- `SIEANS_QT_SMOKE_REPORT=/path.txt` — 写出 codes/ms/passGate 一行

OCR 依赖本机 `tesseract` 与 `eng` 语言包。无 sudo 时执行 `scripts/install-tesseract-user.sh`，把 Ubuntu 官方 deb 解压到 `$HOME/.local/opt/tesseract`，并安装 `$HOME/.local/bin/tesseract` 包装脚本（eng + chi_sim）。算子会查找 PATH、该用户前缀、`SIEANS_TESSERACT` 与 `TESSDATA_PREFIX`；系统已安装 `/usr/bin/tesseract` 时仍优先使用 PATH 上的版本。

YOLO 真实推理（可选）：将检测用 `.onnx`（如 `yolo11n.onnx` / `yolov8n.onnx`）或分割用 `.onnx`（如 `yolo11n-seg.onnx` / `yolov8n-seg.onnx`）放到仓库 `models/`、可执行文件旁 `models/`，或 `$HOME/.local/share/sieans/models/`（或 `SIEANS_YOLO_MODELS_DIR`），也可在算子参数里给绝对/相对路径。无权重或只有 `.pt` 时算子回退 software，不会自动下载。ONNX Runtime 可用 `scripts/install-onnxruntime-user.sh` 安装到 `$HOME/.local/opt/onnxruntime`。本地烟测桩 `models/sieans-yolo-smoke.onnx` 与 `models/sieans-yolo-seg-smoke.onnx` 仅用于验证推理链路，不是工业模型。

启动默认尝试加载 `projects/open-and-run-gentl-qr.sieans`。

## 已落地 vs NEXT

**已落地（wave-5，对齐 VM P0）：** 本地图胶片条（图像源 n/N、添加图像、添加文件夹、删除、自动切换、运行全部）· 状态栏「组件配置完成 / 未配置」与「流程 · 工具 · 算法 ms」· 参数修改写历史日志（旧值/新值）· 工具栏「运行模式」锁定画布拖拽、连线和删除 · 图像源三种取图（本地图像 / 相机 / SDK）字段随模式切换 · 视口像素条 `宽×高 | X Y | R G B` · **快速匹配**：首次执行从当前图高对比区域建模板，绿框叠加分数。

**已落地（wave247）：** 定位/快速匹配属性浮窗四 Tab（基本参数 / 特征或灰度模板 / 运行参数 / 结果显示），含载入与从当前图创建模板、角度搜索和结果回显；与已有 SAD 匹配及 `templateSource`/`angle*` 参数兼容。

**已落地（wave248）：** 协议连接超时与失败分类（拒绝/超时/对端关闭），断连后在同一端口重连；烟测 `protoRobustOk`。

**已落地（wave249）：** Qt 方案多流程 Tab（方案⊃流程，对齐 PySide `desktop/scheme.py`）：同一 `.sieans` 可保存 `flows[]`+`activeFlowId`，并继续写出顶层 `steps` 以兼容旧单流程文件；支持流程切换、新建/复制/重命名/删除（至少一条）；`sieans.prc` 导入导出（完整 prc 或带 `steps` 的裸对象，步骤 id 重映射）。子流程仍为方案级。无界面自测：`SIEANS_QT_SCHEME_SELFTEST=1`。

**已落地（wave250）：** 定位四 Tab 面板补上模板库（加入/选用/预览/移除，本机文件，不删磁盘）与批量记分板（软估或注入分、阈值、选用最优），参数写入 `templateLibrary` / `lastBatchScoreboard`，无 Halcon / 无云市场。

**已落地（wave251）：** 定位火花线点击跳到胶片帧（路径/基名/下标），缩略图短暂高亮；结果表行点击同样定位胶片并选中对应画布节点。无界面自测 `SIEANS_QT_FILMSTRIP_JUMP_SELFTEST=1`。不写脏方案。

**已落地（wave252）：** 流程 I/O 与通信共用同一套 ${flow.x}/{name}/{{name}} 解析；空绑定走 emptyDefault（可再展开模板）。I/O 对话框显示选中行的解析预览。无界面自测 `SIEANS_QT_IO_RESOLVE_SELFTEST=1`。

**已落地（wave253）：** Host 钉组与监视芯片（对齐 PySide `hostWatch.pinGroups` / `activePinGroup`）：分组持久化与恢复、Host 条钉组芯片与变量监视下拉切换、存组/建组；运行期改监视键不改写钉组、不脏污现场种子。无界面自测 `SIEANS_QT_PIN_GROUP_SELFTEST=1`。

**已落地（wave254）：** 结果表双击多选对比侧栏（对齐 PySide `CompareThumbStrip` 子集）：两帧及以上显示缩略条、单击定位胶片、再点同帧或 × 清除；运行期对比不写方案、不脏污现场种子。不发明几何叠层。无界面自测 `SIEANS_QT_COMPARE_STRIP_SELFTEST=1`。

**已落地（wave255）：** 结果视图多帧几何/测量叠层（对齐 PySide `_filmstrip_results` / `set_geom_overlays`）：按胶片路径缓存 GEOM/MEASURE/CALIPER 拾取项，对比侧栏或回看其它帧时用强调色+轮换色绘制，不写方案、不新增测量算子。无界面自测 `SIEANS_QT_GEOM_OVERLAY_SELFTEST=1`。

**已落地（wave256）：** 对比缩略条锁序 / 撤销 / 重排（对齐 PySide `CompareThumbStrip` 余下抛光）：锁后禁止拖拽与编程重排，复位回进入序，撤销栈（最多 16）；仅运行期，不写方案。无界面自测仍走 `SIEANS_QT_COMPARE_STRIP_SELFTEST=1`。

**已落地（wave257）：** 对比条锁序 `QSettings` 偏好（`SIEANS/VisionDesktop`：`film/compareOrderLocked`、`film/undoClearLongMs`）、锁徽章单击切换并持久化、双击复位到进入序并解锁（撤销可按进入时锁态重新上锁）、⊘ 长按清空撤销栈（短按仅提示）。构造时不自动读用户偏好，由主窗 `loadComparePrefs()` 加载；无界面自测注入临时 ini，不写用户仓库。`SIEANS_QT_COMPARE_STRIP_SELFTEST=1`。

**已落地（wave258）：** 胶片条 OK/NG 测量判定徽章（对齐 PySide `set_frame_measure_badges`）：优先测量/卡尺/几何键，无则回退 `locateOk`/`passGate`；运行期缓存，不写方案。对比侧栏同步路径徽章。无界面自测 `SIEANS_QT_FILM_BADGE_SELFTEST=1`。

**已落地（wave259）：** 对比条 ⊘ 右键长按时长预设（400 / 650 默认 / 1000 / 1500 ms），写入同一 `film/undoClearLongMs` 偏好；无界面自测只走临时 ini，不写用户仓库。`SIEANS_QT_COMPARE_STRIP_SELFTEST=1`。

**已落地（wave260）：** 本方案产线配方 / 换型子集（对齐 PySide `project["recipes"]`）：按名称保存当前步骤参数快照、套用到匹配步骤（算子+名称，其次 id，再次算子）、删除、随 `.sieans` 往返。工具 / 工程管理菜单可打开对话框。无界面自测 `SIEANS_QT_RECIPE_SELFTEST=1`。不打开其它工程库、不新增目录算子。

**已落地（wave261）：** 画布 ROI 编辑（对齐 PySide `set_roi_mode` + 对话框拖拽缩放）：在全局图像上绘制 / 移动 / 缩放所选算子 ROI，写回 `roiX/Y/W/H` 与 `roi` 列表；仅实际改动时脏污方案。无界面自测 `SIEANS_QT_ROI_EDITOR_SELFTEST=1`。

**已落地（wave262）：** 全局字符串触发（对齐 PySide `globalTriggers` / `fire_string_trigger`）：通信 `payloadReceived` 与设置菜单配置的字符串行（部分/全等）可派发执行·单次/连续/停止（软通信环回，无真 PLC）。配置随方案保存。无界面自测 `SIEANS_QT_TRIGGER_SELFTEST=1`。

**已落地（wave263）：** 流程画布撤销/重做（对齐 PySide `Document.commit/undo/redo` 的画布子集）：有界栈（最多 31）快照当前活动流程的 steps/edges/source/outputNode，覆盖添加/删除/复制/连线/移动（鼠标松开合并）/参数/ROI；快捷键 Ctrl+Z、Ctrl+Shift+Z 与 Ctrl+Y，系统>编辑菜单。不覆盖配方/通信/胶片等整案事务。无界面自测 `SIEANS_QT_FLOW_UNDO_SELFTEST=1`，不脏污现场 FORCE_SEED。

**已落地（wave264）：** 本地点云文件导入，喂给已有 `cloud_*` 算子（非新目录算子）：ASCII PLY / PCD / XYZ / TXT / CSV，无新第三方依赖；`inputSource=file` + `cloudPath`（配准可用 `targetSource=file` + `targetPath`），设备菜单「导入点云 / 设置参考点云」。无界面自测 `SIEANS_QT_CLOUD_FILE_SELFTEST=1`（临时生成小文件）。

**已落地（wave265）：** 本机检测历史（对齐 PySide「记录与账号 → 检测历史」的本地子集，不接 RPC 账号服务）：每次跑程追加 OK/NG、时间、方案/流程/配方名与耗时，写入用户数据目录（不写入现场 .sieans）；有界 200 条。FORCE_SEED / 无界面冒烟改走进程临时文件，不污染用户真实历史。记录菜单可打开表格（无界面跳过）。无界面自测 `SIEANS_QT_HISTORY_SELFTEST=1`。

**已落地（wave266）：** 配方换型余下子集：套用带回滚栈（最多 16，对齐 PySide `_recipeRollbackStack`）、工具条变体芯片一键套用、本机工程库 `.sieans` 整案换型（projects/ 及模板，无界面跳过对话框）。无界面自测 `SIEANS_QT_RECIPE_CHANGE_SELFTEST=1`，不脏污现场种子。

**已落地（wave267）：** 最近打开菜单（对齐 PySide `recentSchemes`，最多 12 条）：成功打开/保存 `.sieans` 以及导入/导出/工程库换型的 `.prc`/`.sieans` 后写入列表，文件菜单「最近打开」可再开，缺失项跳过。FORCE_SEED / 无界面 / `SIEANS_QT_RECENT_PATH` 走临时或注入 ini，不写用户 `SIEANS/VisionDesktop` 仓库。无界面自测 `SIEANS_QT_RECENT_SELFTEST=1`，不脏污现场种子。

**已落地（wave268）：** 全局触发事件行（流程开始/结束/NG）与工具条「注入RUN / 注入STOP」。流程开始过滤再跑命令，流程结束在连续运行时同样过滤，流程NG 在 `passGate` 失败时触发；`dispatching_triggers_` 防止嵌套再入。注入走已有字符串触发（软通信环回，无真 PLC）。无界面自测 `SIEANS_QT_TRIGGER_EVENT_SELFTEST=1`，不把事件行写入现场种子。

**已落地（wave269）：** `yolo_segment` 接入与检测相同的本机 ONNX Runtime 掩膜路径（dlopen，用户前缀 `$HOME/.local/opt/onnxruntime`）。YOLOv8/11-seg 双输出（preds + proto）还原到工作图；失败或无 `.onnx` 回退 software，不自动下载。无界面自测在存在 `sieans-yolo-seg-smoke.onnx` 且运行时可用时证明 `backend=onnx`；FORCE_SEED 默认权重仍走 `yoloSegBackend=software`。

**已落地（wave270）：** 普通启动可用性收尾：显示后重设垂直分割（底栏约 1/5，避免空结果表占半屏）再 `fitAll`；打开即跑演示预载示例 QR（不自动运行、不脏污方案）；Host 条优先当前钉组（识别历史 `hostWatch.active`，避免膨胀 watchKeys 刷屏）；通信 `autoStart` 缺省改为 false（官方演示仍显式 loopback TCP）；用户级 `install-xcb-cursor-user.sh` + 启动脚本统一 Wayland/xcb，GNOME 上默认 portal 主题以减少 gdk 警告。无界面自测仍走既有 pin-group / protocol-robust。验证截图用 `SIEANS_QT_SCREENSHOT`（应用自身 grab），不要绕过 OS 截屏控制。

**已落地（wave271）：** 用户级可搬迁 Linux 交付目录（Qt/ORT/Tesseract + 依赖闭包、SHA256SUMS、版本/来源、装前 doctor、版本独立桌面项，拒绝覆盖安装）。新增隔离 20 自测 + smoke + 同进程有界 soak + 双实例回归脚本；Qt 会话分 PID 有界日志与启动自检、未捕获 C++ 异常提示；历史文本控件也限 2000 blocks；状态栏显示最近 200 次软件流程 P95（nearest-rank，含 n，不是现场端到端节拍）。详见 [用户级交付](../docs/qt-release.md)。真实 UVC 仅在有 `/dev/video*` 时另验，本机没有设备节点，不宣称采集通过。

**已落地（wave272）：** 新目录算子 `region`（区域分析）：固定/Otsu 阈值、可选反色与 ROI、8 连通域、面积/质心/方向/等效椭圆/圆形度/灰度统计，并按面积及圆形度或灰度均值过滤；可输出二值掩膜给下游，叠加与 followFixture 对齐既有算子。纯 QImage，无 OpenCV/Halcon。粘连目标会合并。无界面自测 `SIEANS_QT_REGION_SELFTEST=1`。

**已落地（wave273）：** `region` 增加 `watershed`（距离变换标记分水岭）与 `growing`（距离峰种子+灰度容差区域生长），用于拆分有颈缩或灰度差别的粘连目标。普通阈值连通域仍会合并。无新第三方库。自测仍走 `SIEANS_QT_REGION_SELFTEST=1`：两粘连圆盘连通域 count=1、分水岭/区域生长 count=2。诚实限制见属性提示：严重重叠或无稳定距离峰时仍可能合并。

**已落地（wave274）：** 新目录算子 `color`（颜色处理）：RGB↔HSV 转换（HSV 以 8 位打包进 RGB 通道，H 为 0–255 对应 0–360°）、通道提取（R/G/B 或从 RGB 现算的 H/S/V）、RGB/HSV 颜色阈值（色相 hMin>hMax 时环绕）。纯 QImage，无 OpenCV/Halcon。无界面自测 `SIEANS_QT_COLOR_SELFTEST=1`。诚实限制：不能自动识别输入是否已是打包 HSV；往返允许数个灰阶误差；不是相机色彩标定。

**已落地（wave275）：** 新目录算子 `camera_cal`（相机标定）：棋盘格内角点或圆点阵列的针孔+2 阶径向畸变标定（fx,fy,cx,cy,k1,k2 + RMSE）与去畸变。单视图锁定 fx=fy 且主点居中。不是 measure 的两点 pxPerMm。纯 QImage。无界面自测 `SIEANS_QT_CAMERA_CAL_SELFTEST=1`：精确对应点恢复内参，再用已知畸变生成的圆点阵列做检测与端到端标定。诚实限制见属性提示（无切向/鱼眼；检测需完整高对比阵列）。

**已落地（wave276）：** 新目录算子 `warp`（图像变换）：仿射、透视（单应）与环形展开。可用矩阵或 3/4 点对；invert 走逆变换。环形展开列=角度、行=半径（上内下外）。纯 QImage 双线性采样。无界面自测 `SIEANS_QT_WARP_SELFTEST=1`：已知平移/透视往返与 0° 亮点展开位置。诚实限制：奇异矩阵失败；插值在大变形下会模糊；不是相机去畸变。

**已落地（wave277）：** 加深 `locate`：仔细读过 TemplateMatch.cpp 后确认原先只有灰度 SAD、旋转与多目标，没有 NCC、尺度搜索或真正的多模板匹配（面板虽有 templateLibrary 但引擎未用；目录文案里的均匀缩放此前也未实现）。现支持 metric/matchMode=ncc（零均值 NCC）、scaleEnable 均匀尺度与 scaleAniso 各向异性（X/Y 独立）尺度搜索、以及 templateLibrary/templatePaths 多模板一起搜（NMS 跨模板）。组合上限 400。变形/变化模型匹配做不到诚实的有限实现，已推迟。自测仍走 `SIEANS_QT_LOCATE_SELFTEST=1`。

**已落地（wave278）：** 补齐目录已宣传但 C++ 原先只有灰度/反色/阈值的 `preprocess`：可分离高斯模糊、Canny 风格边缘（Sobel + 非极大值抑制 + 双阈值滞后）、方形结构元灰度开/闭/腐蚀/膨胀。参数对齐目录 `method` / `threshold` / `kernel`，并增加 `cannyLow` / `cannyHigh`；旧方案 `mode=gray|mono|invert|threshold` 仍可用。invert 为既有能力，予以保留。纯 QImage，无 OpenCV/Halcon。无界面自测 `SIEANS_QT_PREPROCESS_SELFTEST=1`：冲激平滑且能量近似守恒、已知竖直阶跃边被 Canny 检出、形态学对已知斑块面积变化符合方形结构元预期。诚实限制：Canny 无亚像素；形态学仅方形核；大核大图会慢。

**已落地（wave279）：** 新目录算子 `fft`（频域处理）：自研基数 2 二维 FFT，高斯低通/高通/带通/带阻后逆变换回空域，或输出对数幅度谱。截止频率为归一化频率（Nyquist=0.5）。内部补到 2 的幂（上限 4096）再裁回；可选 Hann 窗。写出 `fftOk` / `fftSharpness`（输入高频能量比，不是自动对焦）。纯 C++/QImage，无 FFTW/OpenCV/Halcon。无界面自测 `SIEANS_QT_FFT_SELFTEST=1`：低频正弦能通过低通、被高通衰减；高频正弦相反；带通/带阻方向正确；幅度谱在已知频率出现峰。诚实限制见属性提示：只处理灰度；无窗时周期延拓可能振铃；高通/带通显示偏置 +128。

**已落地（wave280）：** 新目录算子 `classify`（传统分类）：本地特征表上的 KNN、线性 L2-SVM（可选 RBF 铰链核梯度）、每类 GMM（EM，默认 1 个分量）和一层隐藏的小 MLP。训练数据来自方案内 `samples` 文本或本地 `samplePath`（CSV/JSON），每次运行重训；预测可用 `features` 或流程变量 `featureVars`。写出 `classifyOk` / `classifyLabel` / `classifyScore`。无新库、无云、不自动下载。不是 YOLO。无界面自测 `SIEANS_QT_CLASSIFY_SELFTEST=1`：四类方法都在两类合成点上对留出样本预测正确，并覆盖本地 CSV 路径。诚实限制见属性提示：样本/维数上限、线性可分、GMM 高斯假设、小 MLP 过拟合、RBF 不是完整 SMO。

**已落地（wave281）：** `locate` 增加有限弹性分块（`matchMode=deform` / `deformEnable`）：将模板分成最多 3×3 块，每块在 `deformRadius`（≤24px）内平移，分数=块度量均值−λ×平均位移。这是 pictorial-structure / 弹性匹配的有限实现，不是 Halcon 变化模型，不是 TPS/FEM，也不用多张图训练外观方差。自测仍走 `SIEANS_QT_LOCATE_SELFTEST=1`：中段错开 14px 的水平条，刚体 NCC 找不到，弹性分块能找到；换成圆盘则拒绝。

**已落地（wave282）：** `preprocess` 再补图像增强、算术、插值与裁剪：`equalize` 全图亮度直方图均衡（彩色按比例缩放通道，不是 CLAHE）、`gamma`、`contrast`/`brightness`、`add`/`subtract`/`multiply`/`absdiff`（第二图 `otherPath`/`_otherImage` 或常量 `value`，尺寸不同取左上重叠，不是 defects 判定）、`resize`（`scale` 或 `outW`/`outH`，`interp=nearest|bilinear|bicubic`，边长上限 4096）、`crop`（ROI，可 `followFixture`）。通道提取仍走 `color`。自测仍走 `SIEANS_QT_PREPROCESS_SELFTEST=1`：已知伽马曲线、斜坡均衡后对比度上升、相同图相减为 0、最近邻/双线性缩放结构保持、裁剪像素与 ROI 完全一致。先前模糊/Canny/形态学用例保留。

**NEXT：** 运行界面设计器（不在目录中新增 HMI 算子）。操作员账号（PySide 走独立 RPC/部署凭据，未在本机落地）。云 SaaS / 模板市场。真机硬件（`/opt/MVS`、真实 PLC）。官方 YOLO 权重需自行放入上述模型目录。

## VM chrome (2026-11-03)

- FilmstripBar: real local-image thumbs, add/folder/run-all/auto-switch
- PropertyFloat: typed editors + revert on ✕/取消; drag title
- OperatorLibrary: painted glyphs; FlowView corner FlowMinimap
- Flow I/O dialog (输入/输出/显示) ↔ document `io`
- HostStatePanel bottom tab + toolbar 运行模式 lock

