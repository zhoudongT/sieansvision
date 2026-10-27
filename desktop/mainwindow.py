"""Native Qt Widgets application window."""
import base64
import json
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import QSize, Qt, QMimeData, QByteArray, QBuffer, QIODevice, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence, QDrag, QPixmap, QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QTreeWidget,QTreeWidgetItem,
    QLineEdit,QToolBar,QLabel,QPushButton,QFileDialog,QMessageBox,QTabWidget,QPlainTextEdit,QGraphicsView,QGraphicsScene,
    QStackedWidget,QInputDialog,QSpinBox,QDialog,QDialogButtonBox,QFormLayout,QComboBox,QMenu,QListWidget,QListWidgetItem)
from desktop.model import Document,empty_project
from desktop.graph import FlowScene,FlowView,Node
from desktop.catalog import all_definitions,definition_for
from desktop.forms import ParameterPanel,ResultPanel
from desktop.backend import Backend
from desktop.toolbox import Toolbox
from desktop.image_view import ImageView
from desktop.cloud_view import CloudView

from desktop.theme import WORKBENCH_QSS
from desktop.widgets import OperatorRail, FilmstripBar, MiniMap, WorkbenchStatusBar, FlowTabBar, AllFlowsPanel, OrangeSwitch
from desktop.property_float import PropertyFloat
from desktop.group_module import GroupBreadcrumb, normalize_group_params, group_bindings_ready, default_group_inner
from desktop.config_status import project_incomplete_summary, node_needs_bang
from desktop.image_source import normalize_source
from desktop import scheme as flow_scheme
from desktop.operator_hmi import OperatorHmiView
STYLE = WORKBENCH_QSS


class MainWindow(QMainWindow):
    def __init__(self,root,data,start_engine=True,project=None):
        super().__init__();self.root=Path(root);self.data=Path(data);self.document=Document()
        self.definitions=all_definitions([]);self.selected=None;self.image='';self.filename=None;self.busy=False;self.pending_project=Path(project) if project else None
        self.pending={};self.closing=False;self.engine_stopped=not start_engine;self.engine_ready=False
        self.cloud=None;self.depth=None;self.dialogs={};self.last_result=None
        self.demo_backup=None;self.demo_loading=False;self.demo_request=None
        self.setWindowTitle('SIEANS Vision · 视觉检测平台');self.resize(1600,950);self.setMinimumSize(1080,700)
        self.setStyleSheet(STYLE)
        self.backend=Backend(self)
        self.backend.ready.connect(self.engine_online);self.backend.result.connect(self.engine_result)
        self.backend.error.connect(self.engine_error);self.backend.stopped.connect(self.engine_closed)
        if hasattr(self.backend,'progress'):self.backend.progress.connect(self.progress)
        self.continuous=False;self._continuous_paused=False;self.run_all_filmstrip=False;self._run_target=None;self.rail_category='';self.property_float=None;self._group_stack=[];self._group_breadcrumb=None;self._pending_trigger_cmds=[];self._pending_after_continuous=[];self._comm_listener=None;self._nest_fold_marks=[];self._undo_index_before=None;self._canvas_chip_queue=[];self._jump_confirm_skip=set();self._canvas_chip_max_ms=6000;self._jump_skip_persist=False
        self.app_mode='design'  # design | run
        self.showing_all_flows=False
        self._left_pane=None;self._center_stack=None;self.run_mode_pane=None
        self.build_ui();self._load_jump_skip_settings();self.document.changed.connect(self.document_changed);self.populate_toolbox()
        self.document_changed()
        self.wb_status.push_log('正在启动本机算法引擎…' if start_engine else '离线编辑')
        if start_engine:QTimer.singleShot(0,lambda:self.backend.start(self.root,self.data))

    def action(self,title,callback,shortcut=None):
        action=QAction(title,self);action.triggered.connect(lambda:self.guard(callback))
        if shortcut:action.setShortcut(QKeySequence(shortcut))
        return action

    def build_ui(self):
        # VM shell order: 文件 / 设置 / 工具 / 系统 / 帮助（保留 sieans 扩展菜单）
        files=self.menuBar().addMenu('文件')
        settings_menu=self.menuBar().addMenu('设置')
        tools_menu=self.menuBar().addMenu('工具')
        system_menu=self.menuBar().addMenu('系统')
        help_menu=self.menuBar().addMenu('帮助')
        edit=system_menu.addMenu('编辑')
        view=system_menu.addMenu('视图')
        # A4: 方案 .sol vs 流程 .prc
        self.new_action=self.action('新建方案',self.new_project,'Ctrl+N')
        self.open_action=self.action('打开方案',self.open_project,'Ctrl+O')
        self.save_action=self.action('保存方案',self.save_project,'Ctrl+S')
        self.save_as_action=self.action('方案另存为…',self.save_project_as)
        for a in [self.new_action,self.open_action,self.save_action,self.save_as_action]:files.addAction(a)
        self.recent_menu=files.addMenu('最近打开')
        self._rebuild_recent_menu()
        files.addAction(self.action('打开示例…',self.open_example_scheme))
        files.addSeparator()
        files.addAction(self.action('导出流程…',self.export_process_prc))
        files.addAction(self.action('导入流程…',self.import_process_prc))
        files.addSeparator()
        templates=files.addMenu('从模板新建检测工程')
        for label, relative in [
            ('打开即跑 · 圆查找', 'projects/default-platform.sieans'),
            ('打开即跑 · 模板匹配', 'projects/open-and-run-locate.sieans'),
            ('打开即跑 · 九点标定', 'projects/open-and-run-ninepoint.sieans'),
            ('打开即跑 · 参考图缺陷', 'projects/open-and-run-defects.sieans'),
            ('打开即跑 · 条码识别', 'projects/open-and-run-barcode.sieans'),
            ('打开即跑 · 组合+通信', 'projects/open-and-run-group-comm.sieans'),
            ('空白检测工程', 'projects/templates/blank-inspection.sieans'),
            ('采集 → 几何 → 尺寸', 'projects/templates/measure-chain.sieans'),
            ('参考图缺陷检测', 'projects/templates/defect-inspection.sieans'),
            ('MV GenTL → OCR（真实相机）', 'projects/templates/mv-gentl-ocr.sieans'),
        ]:
            templates.addAction(self.action(label, lambda r=relative: self.open_template(r)))
        files.addSeparator();files.addAction(self.action('退出',self.close))
        self.workspace_actions=[]
        work=self.menuBar().addMenu('工程管理');devices=self.menuBar().addMenu('设备与模型');records=self.menuBar().addMenu('记录与账号')
        for menu,label,key in [(work,'本机工程库','projects'),(work,'三级变量','variables'),(work,'子流程管理','subflows'),(work,'运行画面编辑 / 运行','hmi'),(work,'算子插件管理','plugins'),
                               (devices,'相机与连续采集','camera'),(devices,'连续检测 / 事件触发','continuous'),(devices,'模型训练管理','training'),(records,'检测历史','history'),(records,'操作记录','audit'),(records,'操作员账号','accounts')]:
            action=self.action(label,lambda k=key:self.open_panel(k));action.setData(key);menu.addAction(action);self.workspace_actions.append(action)
        records.addAction(self.action('管理员登录',lambda:self.open_panel('login')))
        self.script_action=self.action('本次运行可信 Python 脚本',lambda:None);self.script_action.setCheckable(True)
        work.addAction(self.action('导入 Python 脚本文件',self.import_script));work.addAction(self.script_action)
        devices.addAction(self.action('导入点云',self.open_cloud));devices.addAction(self.action('设置参考点云',lambda:self.open_cloud(True)))
        devices.addAction(self.action('清除点云输入',self.clear_cloud))
        devices.addAction(self.action('相机管理…',self.open_camera_manager))
        devices.addAction(self.action('通信管理…',self.open_comm_manager))
        tools_menu.addAction(self.action('运行界面设计',self.open_run_ui_designer))
        tools_menu.addAction(self.action('一键套用上位机运行壳',self.apply_host_run_ui_template))
        tools_menu.addAction(self.action('应用上位机状态机模板',self.apply_host_run_ui_template))
        tools_menu.addAction(self.action('插入生产任务建议链…',self.apply_production_demo_chain))
        tools_menu.addAction(self.action('运行画面编辑（经典）',lambda:self.open_panel('hmi')))
        settings_menu.addAction(self.action('设计态 / 运行模式…',self.toggle_app_mode))
        settings_menu.addAction(self.action('全局触发…',self.open_global_triggers))
        self._jump_skip_persist_action = self.action(
            '跨会话记住跳层确认跳过', self._toggle_jump_skip_persist)
        self._jump_skip_persist_action.setCheckable(True)
        settings_menu.addAction(self._jump_skip_persist_action)
        settings_menu.addAction(self.action('清除已记住的跳层跳过…', self._clear_persisted_jump_skip))
        settings_menu.addAction(self.action('编辑已记住的跳层跳过…', self._edit_jump_skip_keys))
        tools_menu.addAction(self.action('全局触发…',self.open_global_triggers))
        self.undo_action=self.action('撤销',self._undo_with_fold_tip,'Ctrl+Z');self.redo_action=self.action('重做',self._redo_with_fold_tip,'Ctrl+Y')
        self._undo_history_menu=QMenu(self);self._undo_history_menu.aboutToShow.connect(self._populate_undo_history_menu)
        self.undo_action.setMenu(self._undo_history_menu)
        for a in [self.undo_action,self.redo_action]:edit.addAction(a)
        edit.addAction(self.action('复制模块',self.copy_nodes,'Ctrl+Shift+C'));edit.addAction(self.action('粘贴模块',lambda:self.document.paste() if not self.busy else None,'Ctrl+Shift+V'))
        toolbar=QToolBar('工程与运行');toolbar.setObjectName('mainToolBar');toolbar.setMovable(False);toolbar.setIconSize(QSize(16,16));toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);self.addToolBar(toolbar)
        brand=QLabel('SIEANS');brand.setObjectName('brand');brand.setToolTip('SIEANS Vision');toolbar.addWidget(brand)
        for a in [self.open_action,self.save_action]:toolbar.addAction(a)
        self.image_action=self.action('打开图像',self.open_image);toolbar.addAction(self.image_action)
        self.reference_action=self.action('设置参考图',lambda:self.open_image(True));toolbar.addAction(self.reference_action)
        self.demo_action=self.action('演示工程',self.open_demo_library);toolbar.addAction(self.demo_action)
        self.return_demo_action=self.action('返回原工程',self.restore_demo);self.return_demo_action.setVisible(False);toolbar.addAction(self.return_demo_action);toolbar.addSeparator()
        self.cam_mgr_action=self.action('📷 相机',self.open_camera_manager);self.cam_mgr_action.setToolTip('相机管理');toolbar.addAction(self.cam_mgr_action)
        a_comm=self.action('通信',self.open_comm_manager);a_comm.setToolTip('通信管理（设备 / 收发 / 心跳）');toolbar.addAction(a_comm)
        a_host=self.action('上位机',self.apply_host_run_ui_template);a_host.setToolTip('一键套用上位机运行壳');toolbar.addAction(a_host)
        a_chain=self.action('产线链',self.apply_production_demo_chain);a_chain.setToolTip('插入生产任务建议链');toolbar.addAction(a_chain)
        a_var=self.action('变量',lambda:self.open_panel('variables'));a_var.setToolTip('全局 / 流程变量');toolbar.addAction(a_var)
        a_trig=self.action('触发',self.open_global_triggers);a_trig.setToolTip('全局触发（字符串 / 事件）');toolbar.addAction(a_trig)
        a_inj=self.action('注入RUN',lambda:self.guard(self.inject_run_trigger));a_inj.setToolTip('一键注入字符串 RUN → 全局触发（不打开对话框）');toolbar.addAction(a_inj)
        a_inj_stop=self.action('注入STOP',lambda:self.guard(self.inject_stop_trigger));a_inj_stop.setToolTip('一键注入字符串 STOP → 全局触发');toolbar.addAction(a_inj_stop)
        toolbar.addSeparator()
        self.run_action=self.action('▶ 单次',self.run_once,'Ctrl+Return');self.run_action.setToolTip('单次执行流程 (Ctrl+Return)');toolbar.addAction(self.run_action)
        self.cont_action=self.action('↻ 连续',self.run_continuous);self.cont_action.setToolTip('连续执行');toolbar.addAction(self.cont_action)
        self.stop_action=self.action('■ 停止',self.stop_run);self.stop_action.setToolTip('停止运行');toolbar.addAction(self.stop_action)
        self.run_selected_action=self.action('执行所选',lambda:self.run(self.selected));self.run_selected_action.setToolTip('仅执行当前选中模块');toolbar.addAction(self.run_selected_action)
        toolbar.addSeparator()
        # A1: 设计态 ↔ 运行模式
        mode_lab=QLabel('运行模式');mode_lab.setStyleSheet('color:#a8a8a8;padding-left:6px;font-size:11px;')
        toolbar.addWidget(mode_lab)
        self.mode_switch=OrangeSwitch(False)
        self.mode_switch.setToolTip('关闭=设计态（可编辑）；打开=运行模式（操作员界面，锁定画布）')
        self.mode_switch.toggled.connect(self.on_mode_switch)
        toolbar.addWidget(self.mode_switch)
        self.mode_badge=QLabel('设计态');self.mode_badge.setObjectName('modeBadge');self.mode_badge.setProperty('runMode','false')
        toolbar.addWidget(self.mode_badge)
        toolbar.addSeparator();self.engine_label=QLabel('引擎启动中');toolbar.addWidget(self.engine_label)
        self.comm_listen_badge=QLabel('监听·—');self.comm_listen_badge.setObjectName('commListenBadge')
        self.comm_listen_badge.setStyleSheet('color:#888;padding:0 8px;font-size:11px;')
        self.comm_listen_badge.setToolTip('通信监听状态 — 点击打开通信管理')
        self.comm_listen_badge.setCursor(__import__('PySide6.QtCore', fromlist=['Qt']).Qt.CursorShape.PointingHandCursor)
        self.comm_listen_badge.mousePressEvent = lambda e: self.guard(self.open_comm_manager)  # noqa: E731
        self._last_listen_badge = '监听·—'
        toolbar.addWidget(self.comm_listen_badge)

        # ===== Five-region shell: left(rail+lib) | center flow | right image =====
        root_split=QSplitter(Qt.Orientation.Vertical);self.setCentralWidget(root_split)
        horizontal=QSplitter(Qt.Orientation.Horizontal)

        left=QWidget();left_l=QHBoxLayout(left);left_l.setContentsMargins(0,0,0,0);left_l.setSpacing(0)
        self.op_rail=OperatorRail();self.op_rail.categorySelected.connect(self.filter_rail_category)
        left_l.addWidget(self.op_rail)
        library=QWidget();library.setObjectName('libraryPane');ll=QVBoxLayout(library);ll.setContentsMargins(4,4,4,4);ll.setSpacing(4)
        lib_title=QLabel('算子');lib_title.setObjectName('libraryTitle');ll.addWidget(lib_title)
        self.search=QLineEdit();self.search.setObjectName('operatorSearch');self.search.setPlaceholderText('搜索…');self.search.setClearButtonEnabled(True);ll.addWidget(self.search)
        self.toolbox=Toolbox();ll.addWidget(self.toolbox, 1)
        self.toolbox.operatorActivated.connect(lambda key:self.guard(lambda:self.add_node(key)))
        self.search.textChanged.connect(self.populate_toolbox)
        left_l.addWidget(library,1)
        left.setMinimumWidth(220);left.setMaximumWidth(320)
        self._left_pane=left
        horizontal.addWidget(left)

        flow=QWidget();flow.setObjectName('flowPane');fl=QVBoxLayout(flow);fl.setContentsMargins(0,0,0,0);fl.setSpacing(0)
        self.demo_notice=QLabel();self.demo_notice.setWordWrap(True);self.demo_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.demo_notice.setStyleSheet('background:#3a3d42;color:#c8c8c8;padding:8px 10px;border:1px solid #4a4e54;border-radius:2px;margin:4px;');self.demo_notice.hide();fl.addWidget(self.demo_notice)
        # A2: multi-flow tab bar
        self.flow_tab_bar=FlowTabBar()
        self.flow_tab_bar.allFlowsRequested.connect(self.show_all_flows)
        self.flow_tab_bar.flowSelected.connect(self.select_flow_tab)
        self.flow_tab_bar.addFlowRequested.connect(lambda:self.guard(self.add_flow_tab))
        self.flow_tab_bar.runOnceRequested.connect(self.run_flow_once)
        self.flow_tab_bar.runContinuousRequested.connect(self.run_flow_continuous)
        self.flow_tab_bar.contextAction.connect(self.flow_tab_context)
        fl.addWidget(self.flow_tab_bar)
        name_row=QHBoxLayout();name_row.setContentsMargins(8,4,8,4);name_row.setSpacing(6)
        self.project_name=QLineEdit(self.document.project['name']);self.project_name.setAccessibleName('方案名称');self.project_name.setPlaceholderText('方案名称');self.project_name.editingFinished.connect(self.rename_project)
        name_row.addWidget(QLabel('方案'),0)
        name_row.addWidget(self.project_name,1)
        for label,callback in [('自动排列',self.document.layout),('适应',lambda:self.flow.fit()),('撤销',self._undo_with_fold_tip),('重做',self._redo_with_fold_tip)]:
            b=QPushButton(label);b.clicked.connect(lambda checked=False,cb=callback:self.guard(cb) if not self.busy else None);name_row.addWidget(b)
        fl.addLayout(name_row)
        self.scene=FlowScene(self.document);self.flow=FlowView(self.scene)
        self.scene.chosen.connect(self.choose_node);self.scene.configure.connect(self.configure_node);self.scene.notice.connect(self.log)
        self.flow.dropped.connect(lambda key,pos:self.guard(lambda:self.add_node(key,pos)))
        self._group_breadcrumb=GroupBreadcrumb()
        self._group_breadcrumb.setVisible(False)
        self._group_breadcrumb.exitGroup.connect(self.exit_group_module)
        if hasattr(self._group_breadcrumb, 'jumpExit'):
            self._group_breadcrumb.jumpExit.connect(self.jump_exit_group_to)
        canvas_host=QWidget();chl=QVBoxLayout(canvas_host);chl.setContentsMargins(0,0,0,0);chl.addWidget(self._group_breadcrumb);chl.addWidget(self.flow,1)
        self.minimap=MiniMap(self.scene,self.flow,canvas_host)
        self._canvas_host=canvas_host
        canvas_host.installEventFilter(self)
        # Transient canvas status chip (fold-boundary / nest tips) — overlays flow area
        self._canvas_status_chip = QLabel('', canvas_host)
        self._canvas_status_chip.setObjectName('canvasStatusChip')
        self._canvas_status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas_status_chip.setWordWrap(True)
        self._canvas_status_chip.setVisible(False)
        self._canvas_status_chip.setStyleSheet(
            'QLabel#canvasStatusChip{background:rgba(32,32,36,0.92);color:#f0f0f0;'
            'border:1px solid #e67a2e;border-radius:4px;padding:6px 12px;font-size:12px;}'
        )
        self._canvas_chip_timer = QTimer(self)
        self._canvas_chip_timer.setSingleShot(True)
        self._canvas_chip_timer.timeout.connect(self._advance_canvas_status_chip)
        self._canvas_status_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._canvas_status_chip.setToolTip('点击/Esc 关闭 · 多条折叠提示排队显示 · 单条最长 6s')
        self._canvas_status_chip.installEventFilter(self)
        self._canvas_chip_queue = []
        # A5: 全流程 panel in stack with canvas
        self.all_flows_panel=AllFlowsPanel()
        self.all_flows_panel.runOnce.connect(self.run_flow_once)
        self.all_flows_panel.runContinuous.connect(self.run_flow_continuous)
        self.all_flows_panel.openFlow.connect(self.select_flow_tab)
        self.all_flows_panel.metaChanged.connect(self.on_flow_meta_changed)
        design_stack=QStackedWidget();self._center_stack=design_stack
        design_stack.addWidget(canvas_host)          # 0 = single-flow canvas
        design_stack.addWidget(self.all_flows_panel) # 1 = 全流程
        fl.addWidget(design_stack,1)
        hint=QLabel('双击节点打开属性浮窗 · 端口拖拽连线 · Esc 取消 · Ctrl+滚轮缩放 · 右键流程 Tab 可导出/拷贝/间隔/NG停止/超时')
        hint.setStyleSheet('color:#787878;padding:2px 6px;font-size:11px;');fl.addWidget(hint)
        self._flow_pane=flow
        horizontal.addWidget(flow)

        # A1 run-mode operator HMI (hidden until toggled) — driven by project.runUi
        self.operator_hmi=OperatorHmiView()
        self.operator_hmi.triggerCommands.connect(lambda cmds:self.guard(lambda:self._run_hmi_commands(cmds)))
        self.operator_hmi.designRequested.connect(lambda:self.guard(self.open_run_ui_designer))
        self.operator_hmi.backToDesign.connect(lambda:self.set_app_mode('design'))
        if hasattr(self.operator_hmi,'runUiChanged'):
            self.operator_hmi.runUiChanged.connect(lambda patch:self.guard(lambda:self._on_hmi_run_ui_changed(patch)))
        if hasattr(self.operator_hmi, 'pauseToggled'):
            self.operator_hmi.pauseToggled.connect(self._on_hmi_pause_toggled)
        self._run_pane=self.operator_hmi
        self.run_mode_image=None  # image panes live inside operator_hmi
        horizontal.addWidget(self.operator_hmi)
        self.operator_hmi.hide()

        # Right: image | filmstrip (module-result lives in bottom)
        right=QWidget();right.setObjectName('imagePane');rl=QVBoxLayout(right);rl.setContentsMargins(0,0,0,0);rl.setSpacing(0)
        self.images=QTabWidget();self.input_view=ImageView();self.output_view=ImageView()
        self.images.addTab(self.input_view,'全局图像');self.images.addTab(self.output_view,'模块结果')
        self.cloud_view=CloudView();self.images.addTab(self.cloud_view,'3D 点云');self.input_view.roi_changed.connect(self.update_roi)
        depth_page=QWidget();depth_layout=QVBoxLayout(depth_page);self.depth_view=ImageView();self.depth_caption=QLabel('尚无深度数据')
        self.depth_caption.setWordWrap(True);depth_layout.addWidget(self.depth_view,1);depth_layout.addWidget(self.depth_caption);self.images.addTab(depth_page,'深度图')
        self.images.currentChanged.connect(self._on_images_tab)
        rl.addWidget(self.images,1)
        self.filmstrip=FilmstripBar()
        self.filmstrip.pathSelected.connect(self.load_filmstrip_path)
        self.filmstrip.listChanged.connect(self.filmstrip_list_changed)
        self.filmstrip.autoSwitchChanged.connect(self.filmstrip_auto_changed)
        self.filmstrip.stopAtLastChanged.connect(self.filmstrip_stop_at_last_changed)
        if hasattr(self.filmstrip, 'continuousPauseToggled'):
            self.filmstrip.continuousPauseToggled.connect(self._on_filmstrip_continuous_pause)
        self.filmstrip.runAllRequested.connect(self.run_all_images)
        rl.addWidget(self.filmstrip)
        # Keep ParameterPanel as hidden fallback for programmatic refresh; property float is primary
        self.parameters=ParameterPanel();self.parameters.hide();self.parameters.changed.connect(self.update_step)
        horizontal.addWidget(right)
        self._image_pane=right
        horizontal.setSizes([300,560,520,0]);horizontal.setChildrenCollapsible(False)
        self._main_horizontal=horizontal
        root_split.addWidget(horizontal)

        self.results=ResultPanel();self.logs=QPlainTextEdit();self.logs.setReadOnly(True);self.logs.document().setMaximumBlockCount(200)
        if hasattr(self.results,'image_requested'):self.results.image_requested.connect(self.output_view.show_data)
        bottom=QTabWidget();bottom.addTab(self.results,'当前结果');bottom.addTab(self.logs,'历史结果')
        help_pad=QPlainTextEdit();help_pad.setReadOnly(True)
        help_pad.setPlainText('帮助：双击「0 图像源1」配置本地/相机/SDK；工具栏 ▶单次 / ↻连续 / ■停止；胶片条可批量跑本地图。')
        bottom.addTab(help_pad,'帮助')
        root_split.addWidget(bottom);root_split.setSizes([700,220]);root_split.setChildrenCollapsible(False)

        self.wb_status=WorkbenchStatusBar(self);self.setStatusBar(self.wb_status)
        self.wb_status.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.wb_status.customContextMenuRequested.connect(self._on_status_chip_context_menu)
        view.addAction(self.action('适应流程',self.flow.fit));view.addAction(self.action('适应图像',lambda:(self.input_view.fit(),self.output_view.fit())))
        self.roi_action=self.action('框选所选模块 ROI',self.roi_mode);self.roi_action.setCheckable(True);view.addAction(self.roi_action)
        view.addAction(self.action('清除所选模块 ROI',lambda:self.update_roi(None)))
        help_menu.addAction(self.action('桌面版说明',self.about))
        # Ensure multi-flow scheme shell exists even on blank doc
        try:
            flow_scheme.ensure_scheme(self.document.project)
            self.refresh_flow_tabs()
        except Exception as err:
            self.log(str(err))
        QTimer.singleShot(0,self._place_minimap)

    def guard(self,callback):
        try:callback()
        except Exception as error:self.log(str(error));QMessageBox.warning(self,'操作未完成',str(error))

    def request(self,method,params,callback):
        request_id=self.backend.request(method,params);self.pending[request_id]=callback
        return request_id

    def engine_online(self):
        self.request('auth/status',{},self.authorized)

    def authorized(self,state):
        if not state.get('identity'):
            self.engine_label.setText('等待管理员登录');self.open_panel('login');return
        self.engine_ready=True;self.engine_label.setText('● 本机引擎就绪');self.set_busy(False)
        self.request('plugins/list',{},self.plugins_loaded);self.log('原生桌面工作台就绪：本机进程通信，无浏览器服务')

    def plugins_loaded(self,plugins):
        self.definitions=all_definitions(plugins);self.populate_toolbox();self.refresh_parameters()
        self.log(f'已加载 {len(plugins)} 个插件包，{len(self.definitions)} 个可添加算子')
        if self.pending_project:
            path=self.pending_project;self.pending_project=None
            self.guard(lambda:self.open_project_file(path))
        else:
            self.show_platform_welcome()
            self.reload_comm_listener()
        QTimer.singleShot(200, self.run_platform_health)

    def engine_result(self,request_id,result):
        callback=self.pending.pop(request_id,None)
        if callback:self.guard(lambda:callback(result))

    def engine_error(self,request_id,message):
        self.pending.pop(request_id,None);self.log(message)
        if request_id==getattr(self,'run_request',None):self.set_busy(False)
        if request_id==self.demo_request:
            self.demo_loading=False;self.demo_request=None;self.set_busy(False)
            if self.dialogs.get('demos'):self.dialogs['demos'].message.setText(message)

    def engine_closed(self):
        self.engine_stopped=True;self.engine_ready=False;self.set_busy(False);self.engine_label.setText('引擎已停止')
        if self.closing:self.close()

    def populate_toolbox(self):
        query=self.search.text()
        defs=self.definitions
        if self.rail_category:
            defs={k:v for k,v in defs.items() if v.get('category')==self.rail_category}
        self.toolbox.populate(defs,query)

    def filter_rail_category(self, category):
        self.rail_category=category or ''
        self.populate_toolbox()


    def apply_production_chain(self, ops):
        """Insert production_task suggested chain as real flow nodes (p40 demo)."""
        ops = list(ops or [])
        if not ops:
            self.log('建议链为空'); return
        if self.busy:
            raise ValueError('运行中不可改流程')
        parent = self.selected or 'source'
        added = []
        for item in ops:
            key = item.get('operation')
            if not key or key not in self.definitions:
                self.log(f'跳过未知算子：{key}'); continue
            nid = self.document.add(self.definitions[key], parent=parent)
            # rename to step label
            name = item.get('name') or self.definitions[key].get('name')
            proj = __import__('copy').deepcopy(self.document.project)
            for s in proj['steps']:
                if s['id'] == nid:
                    s['name'] = name
                    break
            self.document.commit(proj, label=f'产线链·{name}')
            added.append(nid)
            parent = nid
            self.selected = nid
        self.scene.clearSelection()
        if added and added[-1] in self.scene.nodes:
            self.scene.nodes[added[-1]].setSelected(True)
        self.scene.rebuild()
        self.refresh_parameters()
        self.log(f'已应用生产任务链：{len(added)} 个模块（可▶运行；无机械手 SDK）')

    def add_node(self,key,position=None):
        if self.busy or not key:return
        self.selected=self.document.add(self.definitions[key],position,parent=self.selected or 'source')
        # B3: 组合模块默认参数（ImageData / InputROI / 循环壳）
        if key=='group' or (self.definitions.get(key) or {}).get('operation')=='group':
            p=deepcopy(self.document.project)
            for s in p['steps']:
                if s['id']==self.selected:
                    s['params']=normalize_group_params(s.get('params')); break
            self.document.commit(p)
        self.scene.clearSelection();self.scene.nodes[self.selected].setSelected(True);self.refresh_parameters()

    def choose_node(self,node_id):
        self.selected=None if node_id=='source' else node_id;self.refresh_parameters()

    def configure_node(self,node_id):
        # B3: 组合模块双击 → 进入嵌套画布；其它模块仍开属性浮窗
        if node_id and node_id != 'source':
            step = next((s for s in self.document.project.get('steps', []) if s.get('id') == node_id), None)
            if step and step.get('operation') == 'group':
                self.guard(lambda: self.enter_group_module(node_id)); return
        self.guard(lambda:self.open_property_float(node_id))

    def ensure_property_float(self):
        if self.property_float is None:
            self.property_float=PropertyFloat(self)
            self.property_float.changed.connect(self.update_step)
            self.property_float.sourceChanged.connect(self.update_source_config)
            self.property_float.paramAudited.connect(self.on_param_audited)
            self.property_float.runModule.connect(lambda nid:self.guard(lambda:self.run(None if nid=='source' else nid)))
            self.property_float.runModuleContinuous.connect(self.run_module_continuous)
            self.property_float.openCameraManager.connect(self.open_camera_manager)
            self.property_float.enterGroup.connect(self.enter_group_module)
            self.property_float.applyProductionChain.connect(lambda ops: self.guard(lambda: self.apply_production_chain(ops)))
            if hasattr(self.property_float, 'hybridCommitted'):
                self.property_float.hybridCommitted.connect(self.update_hybrid_commit)
        return self.property_float

    def open_property_float(self,node_id):
        flo=self.ensure_property_float()
        if node_id=='source':
            cfg=normalize_source(self.document.project.get('sourceConfig'))
            flo.show_source(cfg, title='0 图像源')
            # sync filmstrip visibility for local mode
            self._sync_filmstrip_visibility()
            return
        step=next((s for s in self.document.project['steps'] if s['id']==node_id),None)
        if not step:return
        self.selected=node_id
        definition=deepcopy(definition_for(step,self.definitions)) if step else None
        if step and step.get('operation') in ('subflow','loop') and definition:
            for field in definition.get('parameters',[]):
                if field['key']=='subflowId':field['choices']=[dict(value=s['id'],label=s['name']) for s in self.document.project.get('subflows',[])]
        index=1+next((i for i,s in enumerate(self.document.project['steps']) if s['id']==node_id),0)
        flo.show_step(step,definition,self.document.project,index=index)

    def update_source_config(self,config):
        if self.busy:return
        p=deepcopy(self.document.project)
        p['sourceConfig']=normalize_source(config)
        # mirror filmstrip paths / autoSwitch
        paths=list(p['sourceConfig'].get('images') or [])
        self.filmstrip.set_paths(paths, int(p['sourceConfig'].get('currentIndex') or 0), root=self.root)
        self.filmstrip.set_auto_switch(bool(p['sourceConfig'].get('autoSwitch')))
        self.filmstrip.set_stop_at_last(bool(p['sourceConfig'].get('stopAtLast')))
        # Commit BEFORE visibility sync — _sync_* reads document.project.sourceConfig.mode
        # (stale pre-commit mode left camera↔local soft-disable / interval hint wrong).
        self.guard(lambda:self.document.commit(p))
        self._sync_filmstrip_visibility()
        self._sync_filmstrip_interval_hint()

    def on_param_audited(self,module,param,old,new):
        try:
            flow=self.document.project.get('name') or '流程1'
            msg=self.wb_status.log_param_change(flow, module, param, old, new)
            if hasattr(self, 'logs') and self.logs is not None:
                self.logs.appendPlainText(msg)
        except Exception:
            pass
        # sourceConfig.mode (and sibling source fields) → keep filmstrip visibility/run-all soft-disable in sync
        # even if the float panel is closed as a "dialog OK" without another changed emit.
        if param == 'mode' or (isinstance(module, str) and module.startswith('图像源')):
            try:
                self._sync_filmstrip_visibility()
                self._sync_filmstrip_interval_hint()
            except Exception:
                pass

    def refresh_parameters(self):
        step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
        definition=deepcopy(definition_for(step,self.definitions)) if step else None
        if step and step.get('operation') in ('subflow','loop'):
            for field in definition.get('parameters',[]):
                if field['key']=='subflowId':field['choices']=[dict(value=s['id'],label=s['name']) for s in self.document.project.get('subflows',[])]
        self.parameters.set_step(step,definition,self.document.project,last_result=self.last_result)
        self.input_view.show_roi(step.get('params',{}).get('roi') if step else None)

    def update_step(self,step):
        if self.busy:return
        p=deepcopy(self.document.project);p['steps']=[step if s['id']==step['id'] else s for s in p['steps']]
        self.guard(lambda:self.document.commit(p))
        # Display fitMode/channel → 模块结果 pane live (no re-run required for fit)
        try:
            if (step or {}).get('operation') == 'display':
                self._apply_display_to_result_pane(step)
        except Exception:
            pass

    def update_hybrid_commit(self, payload):
        """Atomic PropertyFloat hybrid OK: source+step in ONE document.commit (single undo tip)."""
        if self.busy:
            return
        payload = payload or {}
        src = payload.get('source')
        step = payload.get('step')
        if src is None and step is None:
            return
        p = deepcopy(self.document.project)
        if src is not None:
            p['sourceConfig'] = normalize_source(src)
            try:
                paths = list(p['sourceConfig'].get('images') or [])
                self.filmstrip.set_paths(paths, int(p['sourceConfig'].get('currentIndex') or 0), root=self.root)
                self.filmstrip.set_auto_switch(bool(p['sourceConfig'].get('autoSwitch')))
                self.filmstrip.set_stop_at_last(bool(p['sourceConfig'].get('stopAtLast')))
            except Exception:
                pass
        if step is not None and step.get('id'):
            p['steps'] = [step if s['id'] == step['id'] else s for s in p['steps']]
        # Single undo tip labelled 图像源+模块
        self.guard(lambda: self.document.commit(p, label='图像源+模块'))
        try:
            self._sync_filmstrip_visibility()
            self._sync_filmstrip_interval_hint()
        except Exception:
            pass
        try:
            if (step or {}).get('operation') == 'display':
                self._apply_display_to_result_pane(step)
        except Exception:
            pass
        try:
            self.log('混合属性已原子提交（图像源+模块 · 单条撤销）')
        except Exception:
            pass

    def refresh_config_status(self):
        """N4: 状态栏「组件参数未配置完整」与画布红叹号同源。"""
        if not hasattr(self, 'wb_status'):
            return
        try:
            ok, msg, bad = project_incomplete_summary(self.document.project)
        except Exception:
            ok, msg, bad = True, '组件配置完成', []
        self.wb_status.set_config(msg, ok=ok)
        if not ok and bad:
            # tip names for first few
            names = []
            p = self.document.project
            for sid in bad[:3]:
                if sid == 'source':
                    names.append('图像源')
                else:
                    step = next((s for s in (p.get('steps') or []) if s.get('id') == sid), None)
                    names.append((step or {}).get('name') or sid)
            more = '…' if len(bad) > 3 else ''
            self.wb_status.config_label.setToolTip('未配置：' + '、'.join(names) + more)
        else:
            self.wb_status.config_label.setToolTip('')

    def document_changed(self):
        p=self.document.project
        try:flow_scheme.ensure_scheme(p)
        except Exception:pass
        if self.selected not in [s['id'] for s in p['steps']]:self.selected=None
        mode_tag='运行模式' if self.app_mode=='run' else '设计态'
        self.setWindowTitle(('● ' if self.document.modified else '')+p['name']+f' — SIEANS Vision · {mode_tag}')
        self.project_name.setText(p['name']);self.undo_action.setEnabled(not self.busy and self.document.index>0)
        self.redo_action.setEnabled(not self.busy and self.document.index<len(self.document.history)-1)
        try:
            self._refresh_undo_redo_labels()
        except Exception:
            pass
        self.refresh_parameters();self.set_busy(self.busy)
        if hasattr(self,'flow_tab_bar'):self.refresh_flow_tabs()
        cfg=normalize_source(p.get('sourceConfig'))
        if hasattr(self,'filmstrip'):
            self.filmstrip.thumbs.blockSignals(True)
            self.filmstrip.auto_switch.blockSignals(True)
            if hasattr(self.filmstrip,'stop_at_last'):
                self.filmstrip.stop_at_last.blockSignals(True)
            self.filmstrip.set_paths(list(cfg.get('images') or []), int(cfg.get('currentIndex') or 0), root=self.root)
            self.filmstrip.set_auto_switch(bool(cfg.get('autoSwitch')))
            self.filmstrip.set_stop_at_last(bool(cfg.get('stopAtLast')))
            self.filmstrip.thumbs.blockSignals(False)
            self.filmstrip.auto_switch.blockSignals(False)
            if hasattr(self.filmstrip,'stop_at_last'):
                self.filmstrip.stop_at_last.blockSignals(False)
            self._sync_filmstrip_visibility()
            self._sync_filmstrip_interval_hint()
        self.refresh_config_status()
        if self.app_mode=='run' and hasattr(self,'operator_hmi'):
            self.operator_hmi.reload_layout(p)

    def rename_project(self):
        if self.busy:return
        p=deepcopy(self.document.project);p['name']=self.project_name.text().strip() or '未命名方案';self.document.commit(p)

    def confirm_discard(self,include_original=False):
        original_dirty=include_original and self.demo_backup is not None and self.demo_backup['project']!=self.demo_backup['saved']
        if not self.document.modified and not original_dirty:return True
        message='演示前的原工程还有未保存修改。可先取消并“返回原工程”保存；继续退出将放弃未保存内容。' if original_dirty else '放弃当前未保存修改？'
        return QMessageBox.question(self,'未保存修改',message,QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Discard

    def new_project(self):
        if self.busy or not self.confirm_discard():return
        try:
            self._clear_jump_confirm_skip()
        except Exception:
            pass
        try:
            self._group_stack = []
            self._nest_fold_marks = []
        except Exception:
            pass
        proj=empty_project();proj['name']='未命名方案';flow_scheme.ensure_scheme(proj)
        self.document.load(proj);self.filename=None;self.image='';self.input_view.show_data('');self.output_view.show_data('');self.results.set_results([])
        self.clear_cloud()
        self.last_result=None;self.showing_all_flows=False
        if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(0)
        self.set_app_mode('design')
        self.show_platform_welcome()
        self.reload_comm_listener()  # persist/refresh listen badge across project switch

    def open_project(self):
        if self.busy or not self.engine_ready or not self.confirm_discard():return
        name,_=QFileDialog.getOpenFileName(self,'打开方案','',
            'VisionMaster 方案 / SIEANS (*.sol *.sieans *.json);;方案 .sol (*.sol);;SIEANS 工程 (*.sieans);;全部 (*.*)')
        if not name:return
        self.open_project_file(Path(name))

    def open_project_file(self, path):
        path=Path(path)
        if not path.is_file():raise ValueError('工程不存在：'+str(path))
        if path.stat().st_size>32*1024*1024:raise ValueError('工程文件不能超过 32 MB')
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        def loaded(reply):
            try:
                self._clear_jump_confirm_skip()
            except Exception:
                pass
            try:
                self._group_stack = []
                self._nest_fold_marks = []
            except Exception:
                pass
            project=reply['project']
            # Preserve multi-flow + native editor extension fields (normalize may drop/reshape them).
            # runUi.fixedBars.gateKey (判定门) and sourceConfig must survive save→reopen.
            for key in ('flows','activeFlowId','flowEdges','runUi','commManager','globalTriggers','notes','sourceConfig'):
                if key in value:project[key]=value[key]
            flow_scheme.ensure_scheme(project)
            # Prefer active flow payload on top-level
            try:flow_scheme.activate_flow(project, project['activeFlowId'])
            except Exception:pass
            self.document.load(project);self.filename=path;self.results.set_results([])
            self.image='';self.input_view.show_data('');self.output_view.show_data('');self.flow.fit()
            self.clear_cloud();self.last_result=None;self.showing_all_flows=False
            if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(0)
            ops=', '.join(s.get('name') or s.get('operation') for s in project.get('steps',[]))
            nflows=len(project.get('flows') or [])
            self.log(f'已打开方案：{path.name} · {nflows} 个流程 · 模块：{ops}（含相机采集时无需预先打开图像，直接运行流程）')
            self.reload_comm_listener()
            notes=(project.get('notes') or '').strip()
            if notes:
                self.demo_notice.setText(notes);self.demo_notice.show()
            elif not project.get('steps'):
                self.show_platform_welcome()
            else:
                self.demo_notice.hide()
            self.refresh_flow_tabs()
            self._remember_recent(path)
            QTimer.singleShot(300, self.maybe_warm_camera)
            # Open-and-run: auto-load first local sourceConfig image into global 图像
            QTimer.singleShot(50, lambda: self.guard(lambda: self._autoload_source_image(force=True)))
        self.request('project/validate',{'project':value},loaded)

    def save_project(self):
        if self.busy or not self.engine_ready:return
        if self.filename:
            name=str(self.filename)
        else:
            name,_=QFileDialog.getSaveFileName(self,'保存方案',self.document.project['name']+'.sol',
                '方案 .sol (*.sol);;SIEANS 工程 (*.sieans)')
        if not name:return
        self._write_scheme_file(Path(name))

    def save_project_as(self):
        if self.busy or not self.engine_ready:return
        name,_=QFileDialog.getSaveFileName(self,'方案另存为',self.document.project['name']+'.sol',
            '方案 .sol (*.sol);;SIEANS 工程 (*.sieans)')
        if not name:return
        self._write_scheme_file(Path(name))

    def _write_scheme_file(self, destination):
        snapshot=flow_scheme.scheme_for_disk(self.document.project)
        def saved(reply):
            # Keep multi-flow fields from client snapshot (normalize strips them)
            out=deepcopy(snapshot)
            for key in ('steps','edges','sourcePosition','sourceConfig','variables','variableTypes','subflows','hmi','outputNode','name','id','version'):
                if key in reply.get('project',{}):
                    out[key]=reply['project'][key]
            # Prefer client snapshot for HMI / Comm / triggers (判定门 gateKey lives in runUi.fixedBars)
            for key in ('runUi','commManager','globalTriggers','notes'):
                if key in snapshot:
                    out[key]=deepcopy(snapshot[key])
            # Re-sync active into flows after any normalize of top-level
            try:
                flow_scheme.ensure_scheme(out)
                flow_scheme.sync_active_into_flows(out)
            except Exception:pass
            temporary=destination.with_suffix(destination.suffix+'.tmp')
            temporary.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(destination)
            self.filename=destination;self.document.saved=deepcopy(out)
            # Keep live doc flows in sync
            self.document.project['flows']=deepcopy(out.get('flows',[]))
            self.document.project['activeFlowId']=out.get('activeFlowId')
            self.document.project['flowEdges']=deepcopy(out.get('flowEdges',[]))
            self.document_changed();self.log('方案已保存：'+str(destination)+f'（{len(out.get("flows") or [])} 个流程）')
            self._remember_recent(destination)
        self.request('project/validate',{'project':snapshot},saved)

    def open_image(self,reference=False):
        if self.busy:return
        if reference and not self.selected:raise ValueError('请先选择模板定位或差异检测模块')
        name,_=QFileDialog.getOpenFileName(self,'打开图像','','图像 (*.png *.jpg *.jpeg *.bmp)')
        if not name:return
        path=Path(name)
        if path.stat().st_size>12*1024*1024:raise ValueError('图像不能超过 12 MB')
        raw=path.read_bytes();image=QImage.fromData(raw)
        if image.isNull() or image.width()*image.height()>16000000:raise ValueError('无效图像，或超过 1600 万像素')
        data='data:image/'+('jpeg' if path.suffix.lower() in ('.jpg','.jpeg') else path.suffix[1:])+';base64,'+base64.b64encode(raw).decode()
        if reference:
            p=deepcopy(self.document.project);step=next(s for s in p['steps'] if s['id']==self.selected)
            if step['operation'] not in ('locate','defects'):raise ValueError('当前模块不使用参考图')
            step['reference']=data;self.document.commit(p);self.log('已设置所选模块参考图');return
        self.image=data;self.input_view.show_data(data);self.output_view.show_data('');self.results.set_results([]);self._mirror_preview_to_operator();self.log(f'载入图像 {image.width()} × {image.height()}')
        self.clear_cloud();self.last_result=None;self.refresh_parameters()
        # keep filmstrip in sync for local source
        try:
            resolved=str(path.resolve())
            p=deepcopy(self.document.project);cfg=normalize_source(p.get('sourceConfig'))
            images=list(cfg.get('images') or [])
            if resolved not in images:images.append(resolved)
            cfg['images']=images;cfg['currentIndex']=images.index(resolved);cfg['mode']='local'
            p['sourceConfig']=cfg;self.document.commit(p)
        except Exception:
            pass
        if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)

    def demo(self):
        if self.busy or not self.confirm_discard():return
        self.clear_cloud();self.last_result=None
        self.document.load(empty_project());self.document.project['name']='演示 · 工件轮廓检测';self.filename=None
        first=self.document.add(self.definitions['preprocess']);second=self.document.add(self.definitions['geometry'],parent=first)
        p=deepcopy(self.document.project);p['steps'][1]['params']['invert']=True;self.document.commit(p);self.document.layout()
        image=QImage(800,520,QImage.Format.Format_RGB32);image.fill(QColor('#fafafa'))
        painter=QPainter(image);painter.setBrush(QColor('#173851'));painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(90,110,230,170,12,12);painter.drawEllipse(450,140,160,160);painter.drawRect(150,350,470,55);painter.end()
        buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG')
        self.image='data:image/png;base64,'+bytes(buffer.data().toBase64()).decode();self.input_view.show_data(self.image)
        self.output_view.show_data('');self.results.set_results([]);self.selected=second;self.refresh_parameters();self.flow.fit();self.log('已载入合成工件图，点击“运行流程”执行真实算法')
        if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)

    def open_demo_library(self):
        if self.busy or not self.engine_ready:return
        if self.dialogs.get('demos'):
            self.dialogs['demos'].show();self.dialogs['demos'].raise_();return
        from desktop.demo_dialog import DemoDialog
        dialog=DemoDialog(self.backend,self.root,self);self.dialogs['demos']=dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.destroyed.connect(lambda *_:self.dialogs.pop('demos',None))
        dialog.load_requested.connect(lambda key,run:self.guard(lambda:self.load_demo(key,run)))
        dialog.sample_requested.connect(lambda:self.guard(self.load_demo_sample));dialog.show()

    def load_demo(self,demo_id,run=True):
        if self.busy or not self.engine_ready:return
        self.demo_loading=True;self.set_busy(True)
        try:self.demo_request=self.request('demos/load',{'id':demo_id},lambda reply:self.apply_demo(reply,run))
        except Exception:
            self.demo_loading=False;self.set_busy(False);raise

    def backup_workspace(self):
        return dict(project=deepcopy(self.document.project),history=deepcopy(self.document.history),index=self.document.index,
                    saved=deepcopy(self.document.saved),clipboard=deepcopy(self.document.clipboard),selected=self.selected,
                    filename=self.filename,image=self.image,cloud=deepcopy(self.cloud),depth=deepcopy(self.depth),
                    last_result=deepcopy(self.last_result),view=self.images.currentIndex(),transform=self.flow.transform(),
                    center=self.flow.mapToScene(self.flow.viewport().rect().center()))

    def apply_demo(self,reply,run):
        try:
            Document.validate(reply['project'])
            if self.demo_backup is None:self.demo_backup=self.backup_workspace()
            self.script_action.setChecked(False);self.last_result=None;self.filename=None
            self.document.load(reply['project']);self.document.saved={};self.document_changed()
            self.image=reply.get('image') or '';self.cloud=reply.get('cloud');self.depth=reply.get('depth')
            self.input_view.show_data(self.image);self.output_view.show_data('');self.cloud_view.set_cloud(self.cloud);self.results.set_results([])
            self.show_depth(self.depth)
            self.selected=self.document.project['steps'][-1]['id'] if self.document.project['steps'] else None
            self.refresh_parameters();self.flow.fit();self.images.setCurrentIndex(3 if self.depth and not self.image else 2 if self.cloud else 0)
            item=reply['item'];self.demo_notice.setText('演示：'+item['name']+'\n预期：'+item.get('expected',''))
            self.demo_notice.show();self.return_demo_action.setVisible(True)
            if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)
            if self.dialogs.get('demos'):self.dialogs['demos'].accept()
            self.log('已载入演示工程：'+item['name'])
            for requirement in reply.get('requirements') or []:self.log(requirement)
            if self.document.project.get('hmi'):self.log('此演示包含运行画面：从“工程管理 → 运行画面编辑 / 运行”打开，再选择“运行画面”。')
        finally:
            self.demo_request=None;self.demo_loading=False;self.set_busy(False)
        if run and reply.get('autoRun'):self.run()
        elif run:self.log('演示已载入；按案例说明准备依赖或启动方式后再运行。')

    def load_demo_sample(self):
        if self.busy or not self.engine_ready:return
        step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
        operation=step['operation'] if step else 'geometry'
        self.demo_loading=True;self.set_busy(True)
        def loaded(frame):
            self.demo_request=None;self.demo_loading=False;self.set_busy(False);self.accept_frame(frame)
            if not self.document.project['steps']:self.add_node('geometry')
            if self.dialogs.get('demos'):self.dialogs['demos'].accept()
            self.log('当前算子的示例数据已载入')
        try:self.demo_request=self.request('demos/sample',{'operation':operation},loaded)
        except Exception:
            self.demo_loading=False;self.set_busy(False);raise

    def restore_demo(self):
        if self.busy or self.demo_backup is None:return
        saved=self.demo_backup;self.demo_backup=None;self.script_action.setChecked(False)
        self.document.load(saved['project'])
        for key in ('history','index','saved','clipboard'):setattr(self.document,key,deepcopy(saved[key]))
        for key in ('selected','filename','image','cloud','depth','last_result'):setattr(self,key,saved[key])
        self.document.changed.emit();self.input_view.show_data(self.image);self.output_view.show_data('');self.cloud_view.set_cloud(self.cloud)
        self.show_depth(self.depth)
        self.results.set_results([])
        if self.last_result:self.finished(self.last_result,release=False)
        if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)
        self.refresh_parameters();self.images.setCurrentIndex(saved['view']);self.flow.setTransform(saved['transform']);self.flow.centerOn(saved['center'])
        self.demo_notice.hide();self.return_demo_action.setVisible(False);self.log('已恢复进入演示前的工程、输入和编辑历史')

    def copy_nodes(self):
        self.document.copy([n.node_id for n in self.scene.selectedItems() if isinstance(n,Node) and not n.source])

    def set_busy(self,busy):
        self.busy=busy
        design=self.app_mode=='design'
        # In run mode keep view navigable but graph edit locked via scene.edit_locked
        self.flow.setEnabled(not busy)
        self.parameters.setEnabled(not busy and design)
        self.toolbox.setEnabled(not busy and design)
        if hasattr(self,'op_rail'):self.op_rail.setEnabled(not busy and design)
        self.project_name.setEnabled(not busy and design)
        if hasattr(self,'flow_tab_bar'):self.flow_tab_bar.setEnabled(not busy)
        for a in [self.new_action,self.image_action,self.reference_action,self.demo_action]:a.setEnabled(not busy and design)
        for a in [self.open_action,self.save_action,self.run_action,self.run_selected_action,self.cont_action]:a.setEnabled(self.engine_ready and not busy)
        self.stop_action.setEnabled(busy or self.continuous);self.undo_action.setEnabled(not busy and design and self.document.index>0);self.redo_action.setEnabled(not busy and design and self.document.index+1<len(self.document.history))
        try:
            self._refresh_undo_redo_labels()
        except Exception:
            pass
        self.demo_action.setEnabled(self.engine_ready and not busy and design);self.return_demo_action.setEnabled(not busy and self.demo_backup is not None)
        if hasattr(self,'filmstrip'):
            self.filmstrip.setEnabled(not busy and design)
            # Parent setEnabled(True) re-enables children — re-apply camera soft-disable
            if not busy and design:
                try: self._sync_filmstrip_visibility()
                except Exception: pass
        for action in self.workspace_actions:action.setEnabled(self.engine_ready and (not busy or action.data() in ('continuous','hmi')))
        for key,dialog in list(self.dialogs.items()):
            if hasattr(dialog,'set_busy'):
                dialog.set_busy(busy)
            elif key not in ('login','camera','training'):
                # Never setEnabled(False) on camera/training — that freezes Close/Esc/X.
                dialog.setEnabled(not busy)

    def run_once(self):
        self.continuous=False;self.run_all_filmstrip=False;self._run_target=None;self.run()

    def run_continuous(self):
        if self.busy or not self.engine_ready:return
        self.continuous=True;self._continuous_paused=False;self.run_all_filmstrip=False;self._run_target=None
        try:
            if hasattr(self, 'filmstrip'):
                if hasattr(self.filmstrip, 'set_pause_owner'):
                    self.filmstrip.set_pause_owner('continuous')
                self._sync_pause_owner_badges('continuous')
                if hasattr(self.filmstrip, 'set_continuous_controls_enabled'):
                    self.filmstrip.set_continuous_controls_enabled(True)
                if hasattr(self.filmstrip, 'set_continuous_paused'):
                    self.filmstrip.set_continuous_paused(False)
        except Exception:
            pass
        self.log('连续运行已启动');self.run()

    def stop_run(self):
        was_continuous = bool(self.continuous)
        self.continuous=False;self._continuous_paused=False;self.run_all_filmstrip=False;self._run_target=None
        try:
            if hasattr(self, 'filmstrip'):
                if hasattr(self.filmstrip, 'set_continuous_paused'):
                    self.filmstrip.set_continuous_paused(False)
                if hasattr(self.filmstrip, 'set_continuous_controls_enabled'):
                    self.filmstrip.set_continuous_controls_enabled(False)
                if hasattr(self.filmstrip, 'set_pause_owner'):
                    self.filmstrip.set_pause_owner(None)
                self._sync_pause_owner_badges(None)
        except Exception:
            pass
        self.request('stop',{},lambda _:None)
        self.wb_status.push_log('已请求停止')
        if was_continuous:
            self._flush_after_continuous()



    def _sync_pause_owner_badges(self, mode=None):
        """Mirror filmstrip pause-owner tip onto HMI 生产统计 badge."""
        if mode is None and hasattr(self, 'filmstrip'):
            mode = getattr(self.filmstrip, '_pause_owner', None)
        try:
            if hasattr(self, 'filmstrip') and hasattr(self.filmstrip, 'set_pause_owner'):
                # keep filmstrip tip in sync when called with explicit mode
                if mode is not None or mode is None:
                    pass
            if hasattr(self, 'operator_hmi') and self.operator_hmi is not None:
                if hasattr(self.operator_hmi, 'set_pause_owner_badge'):
                    self.operator_hmi.set_pause_owner_badge(mode)
        except Exception:
            pass

    def pause_continuous(self):
        """Soft-pause ContinuousRun or 运行全部: skip next QTimer schedule."""
        if not (self.continuous or self.run_all_filmstrip):
            return
        self._continuous_paused = True
        try:
            if hasattr(self, 'filmstrip') and hasattr(self.filmstrip, 'set_continuous_paused'):
                self.filmstrip.set_continuous_paused(True)
        except Exception:
            pass
        # Bridge → HMI 生产统计 pause buttons (avoid re-entry)
        try:
            self._sync_hmi_pause_buttons(True)
        except Exception:
            pass
        kind = '运行全部' if self.run_all_filmstrip and not self.continuous else '连续运行'
        self.log(f'{kind}已暂停（可改间隔后继续）')

    def resume_continuous(self):
        """Resume paused ContinuousRun / 运行全部; schedule next tick if not busy."""
        if not (self.continuous or self.run_all_filmstrip):
            return
        was = bool(getattr(self, '_continuous_paused', False))
        self._continuous_paused = False
        try:
            if hasattr(self, 'filmstrip') and hasattr(self.filmstrip, 'set_continuous_paused'):
                self.filmstrip.set_continuous_paused(False)
        except Exception:
            pass
        try:
            self._sync_hmi_pause_buttons(False)
        except Exception:
            pass
        kind = '运行全部' if self.run_all_filmstrip and not self.continuous else '连续运行'
        self.log(f'{kind}已继续')
        if was and not self.busy:
            from PySide6.QtCore import QTimer
            delay = self._filmstrip_advance_delay_ms()
            if self.run_all_filmstrip:
                QTimer.singleShot(delay, lambda: self.guard(self.run) if self.run_all_filmstrip and not getattr(self, '_continuous_paused', False) else None)
            else:
                QTimer.singleShot(delay, lambda: self.guard(lambda: self.run(self._run_target) if self.continuous and not getattr(self, '_continuous_paused', False) else None))

    def _flush_after_continuous(self):
        """Chain non-run commands that followed 执行·连续 once continuous ends."""
        pending = list(getattr(self, '_pending_after_continuous', None) or [])
        self._pending_after_continuous = []
        if not pending:
            return
        self.log(f'连续后链式 · 续派 {len(pending)} 条')
        QTimer.singleShot(0, lambda p=pending: self.guard(
            lambda: self._dispatch_global_triggers(p, reason='连续后链式')))

    def run_module_continuous(self,node_id):
        # B2: 模块级连续执行 — 与全局连续分离，保留 target
        if node_id=='source':node_id=None
        self.continuous=True;self.run_all_filmstrip=False;self._run_target=node_id
        self.log('模块连续执行已启动' + (f' · {node_id}' if node_id else ''))
        self.guard(lambda:self.run(node_id))

    def run(self,target=None):
        if self.busy or not self.engine_ready:return
        # 允许仅跑图像源/空链时给出提示；有 target 时至少需要该模块
        if not self.document.project['steps'] and target is None and not self._group_stack:
            raise ValueError('请先添加流程模块')
        if target is not None:
            self._run_target=target
        elif not self.continuous:
            self._run_target=None
        effective=target if target is not None else (self._run_target if self.continuous else None)
        # 图像源 · 相机/SDK：运行前从持久会话取最新帧填入全局图像（无会话则给明确错误）
        cfg=normalize_source(self.document.project.get('sourceConfig'))
        if cfg.get('mode') in ('camera', 'sdk') and not any(
            s.get('operation')=='camera_capture' for s in self.document.project.get('steps') or []
        ):
            self._ensure_camera_frame_for_run(cfg)
        elif not self.image and cfg.get('mode', 'local') == 'local':
            # Open-and-run: pull filmstrip / sourceConfig image if global 图像 empty
            self._autoload_source_image(force=False)
        if not self.image and cfg.get('mode', 'local') == 'local' and (cfg.get('images') or []):
            raise ValueError('本地源图未能载入，请检查胶片条路径是否存在')
        params=dict(project=deepcopy(self.document.project),image=self.image,allowScripts=self.script_action.isChecked())
        self.script_action.setChecked(False)
        if self.cloud:params['cloud']=self.cloud
        if self.depth:params['depth']=self.depth
        if effective:params['target']=effective
        self.set_busy(True);self.results.set_results([])
        self.log('开始执行' + ('模块 ' + str(effective) if effective else '流程') + '…')
        if not getattr(self, '_dispatching_triggers', False) and not effective:
            try:
                from desktop.global_triggers import collect_event_commands
                cmds = [c for c in collect_event_commands(self.document.project, '流程开始')
                        if (c.get('type') or '') not in ('执行·单次', '执行', '执行·连续', '执行·继续')]
                self._dispatch_global_triggers(cmds, reason='流程开始')
            except Exception:
                pass
        try:self.run_request=self.request('run',params,self.finished)
        except Exception:self.set_busy(False);self.continuous=False;self._run_target=None;raise

    def progress(self,value):
        if value.get('activeStep'):
            step=next((s for s in self.document.project['steps'] if s['id']==value['activeStep']),{})
            self.wb_status.push_log('正在执行：'+step.get('name','流程模块'))
        dialog=self.dialogs.get('hmi')
        if dialog:dialog.set_runtime(value,self.image)


    def _pick_annotated_image(self, records):
        """Prefer 图像显示(display) engine annotatedImage, else last non-empty annotated.

        Returns data-url string ( falsy if none).
        """
        img, _sid = self._pick_annotated_with_step(records)
        return img

    def _pick_annotated_with_step(self, records):
        records = list(records or [])
        steps = {s['id']: s for s in (self.document.project.get('steps') or [])}
        preferred = None
        preferred_id = None
        fallback = None
        fallback_id = None
        for record in reversed(records):
            image = (record.get('output') or {}).get('annotatedImage') or ''
            if not image:
                continue
            sid = record.get('id')
            op = (steps.get(sid) or {}).get('operation') or (record.get('output') or {}).get('operation')
            if op == 'display' and preferred is None:
                preferred, preferred_id = image, sid
            if fallback is None:
                fallback, fallback_id = image, sid
        if preferred:
            return preferred, preferred_id
        return fallback or '', fallback_id

    def _apply_display_to_result_pane(self, step=None, image=None):
        """Live-apply Display fitMode/channel on 模块结果 + HMI panes + filmstrip thumb."""
        step = step or {}
        params = step.get('params') or {}
        fit = params.get('fitMode') or 'contain'
        if image:
            self._last_display_image = image
        src = image or getattr(self, '_last_display_image', None) or ''
        ch = params.get('channel') or 'auto'
        show = src
        if src and ch not in (None, '', 'auto'):
            try:
                show = self._client_channel_preview(src, ch) or src
            except Exception:
                show = src
        # 模块结果 pane
        ov = getattr(self, 'output_view', None)
        if ov is not None:
            if hasattr(ov, 'set_fit_mode'):
                ov.set_fit_mode(fit)
            if show and (image or ch not in (None, '', 'auto')):
                ov.show_data(show)
                if hasattr(self, 'images'):
                    self.images.setCurrentIndex(1)
            elif hasattr(ov, 'bounds') and not ov.bounds.isEmpty():
                ov.fit()
        # Filmstrip live thumb (channelled frame + fit tip + actual pad from theme/channel)
        fit_only = False
        try:
            pad = self._display_actual_pad_color(ch)
            fs = getattr(self, 'filmstrip', None)
            if fs is not None:
                new_frame = bool(image)
                same_show = (show == getattr(self, '_last_filmstrip_show', object()))
                has_live = getattr(fs, '_live_src_pixmap', None) is not None
                # fitMode/pad-only (cover↔actual) without new frame: re-fit cached src (no fancy re-decode)
                if (not new_frame) and same_show and has_live and show:
                    fit_only = True
                    if hasattr(fs, 'set_actual_pad_color'):
                        try:
                            fs.set_actual_pad_color(pad, refresh=False)
                        except TypeError:
                            fs.set_actual_pad_color(pad)
                    if hasattr(fs, 'set_live_fit_mode'):
                        fs.set_live_fit_mode(fit, refresh=True)
                    else:
                        if fit in ('contain', 'cover', 'actual'):
                            fs._live_fit_mode = fit
                        if hasattr(fs, 'refresh_live_thumb_fit'):
                            fs.refresh_live_thumb_fit()
                elif show:
                    if hasattr(fs, 'set_live_display'):
                        try:
                            fs.set_live_display(show, fit_mode=fit, pad_color=pad)
                        except TypeError:
                            if hasattr(fs, 'set_actual_pad_color'):
                                fs.set_actual_pad_color(pad)
                            fs.set_live_display(show, fit_mode=fit)
                    elif hasattr(fs, 'set_live_result'):
                        if hasattr(fs, 'set_actual_pad_color'):
                            fs.set_actual_pad_color(pad)
                        fs.set_live_result(show, fit_mode=fit)
                    self._last_filmstrip_show = show
                elif hasattr(fs, 'set_actual_pad_color'):
                    fs.set_actual_pad_color(pad)
        except Exception:
            pass
        # HMI panes: always sync fitMode; on fit-only skip costly image re-push
        hmi_image = None if fit_only else (show or None)
        try:
            if hasattr(self, 'operator_hmi') and self.operator_hmi is not None:
                if hasattr(self.operator_hmi, 'apply_display'):
                    self.operator_hmi.apply_display(
                        fit_mode=fit, image=hmi_image, channel=ch,
                    )
                else:
                    for view in getattr(self.operator_hmi, '_image_views', None) or []:
                        if hasattr(view, 'set_fit_mode'):
                            view.set_fit_mode(fit)
                        if hmi_image:
                            view.show_data(hmi_image)
                        elif fit and hasattr(view, 'fit'):
                            try:
                                if not getattr(view, 'bounds', None).isEmpty():
                                    view.fit()
                            except Exception:
                                pass
        except Exception:
            pass
        # HMI dialog (if open)
        try:
            dialog = (getattr(self, 'dialogs', None) or {}).get('hmi')
            if dialog is not None and hasattr(dialog, 'apply_display'):
                dialog.apply_display(fit_mode=fit, image=hmi_image, channel=ch)
        except Exception:
            pass

    def _display_actual_pad_color(self, channel=None):
        """Filmstrip actual-mode letterbox pad from Display channel / theme."""
        try:
            from desktop.theme import CANVAS, BG, CARD, ACCENT_DEEP
        except Exception:
            CANVAS, BG, CARD, ACCENT_DEEP = '#2d2f33', '#2a2c30', '#3a3d42', '#c45f18'
        ch = (channel or 'auto')
        if isinstance(ch, str):
            ch = ch.lower().strip()
        else:
            ch = 'auto'
        if ch == 'gray':
            return BG
        if ch == 'r':
            return '#3a2222'
        if ch == 'g':
            return '#223a22'
        if ch == 'b':
            return '#22223a'
        if ch in ('auto', '', None):
            return CANVAS
        return CARD

    def _client_channel_preview(self, data_url, channel):
        """Live channel preview (cv2) without engine re-run; returns new data-url or None."""
        import base64
        if not data_url or channel in (None, '', 'auto'):
            return None
        try:
            import cv2
            import numpy as np
            raw = base64.b64decode(data_url.split(',', 1)[-1], validate=False)
            arr = np.frombuffer(raw, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                return None
            if channel in ('r', 'g', 'b'):
                idx = {'b': 0, 'g': 1, 'r': 2}[channel]
                plane = bgr[:, :, idx]
                bgr = cv2.merge([plane, plane, plane])
            elif channel == 'gray':
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                return None
            ok, enc = cv2.imencode('.png', bgr)
            if not ok:
                return None
            return 'data:image/png;base64,' + base64.b64encode(enc).decode()
        except Exception:
            return None

    def finished(self,result,release=True):
        self.last_result=result
        if release:self.set_busy(False)
        records=result.get('results',[])
        names={s['id']:s.get('name',s['operation']) for s in self.document.project['steps']}
        self.results.set_results([{**r,'name':names.get(r['id'],r['id'])} for r in records]);self.scene.show_results(records)
        annotated_live, ann_sid = self._pick_annotated_with_step(records)
        _disp_applied = False
        if annotated_live:
            disp_step = next((s for s in (self.document.project.get('steps') or []) if s.get('id')==ann_sid), None)
            if disp_step and disp_step.get('operation')=='display':
                self._apply_display_to_result_pane(disp_step, image=annotated_live)
                _disp_applied = True
            else:
                self.output_view.show_data(annotated_live);self.images.setCurrentIndex(1)
                try:
                    if hasattr(self,'filmstrip') and hasattr(self.filmstrip,'set_live_result'):
                        self.filmstrip.set_live_result(annotated_live)
                except Exception:
                    pass
        for record in reversed(records):
            cloud=record.get('output',{}).get('cloud')
            if cloud:self.cloud_view.set_cloud(cloud);self.images.setCurrentIndex(2);break
        for record in reversed(records):
            depth=record.get('output',{}).get('depth')
            if depth:self.show_depth(depth);break
        dialog=self.dialogs.get('hmi')
        if dialog:dialog.set_runtime(result,self.image)
        elapsed=result.get('elapsedMs',0) or 0
        # Approximate VM timing triad from total elapsed
        process_ms=elapsed
        tool_ms=round(elapsed*0.15,2) if elapsed else 0
        algo_ms=round(elapsed*0.75,2) if elapsed else 0
        self.wb_status.set_timing(process_ms, tool_ms, algo_ms)
        self.refresh_config_status()
        if result.get('state')=='failed':
            self.wb_status.set_config('运行失败 · 见日志', ok=False)
        # A5: update active flow card stats
        try:
            p=self.document.project
            flow_scheme.ensure_scheme(p)
            flow_scheme.sync_active_into_flows(p)
            fid=p.get('activeFlowId')
            for f in p.get('flows') or []:
                if f.get('id')==fid:
                    if result.get('state')=='completed':
                        f['runCount']=int(f.get('runCount') or 0)+1
                    f['lastElapsedMs']=float(elapsed)
                    break
            if hasattr(self,'all_flows_panel') and self.showing_all_flows:
                self.all_flows_panel.set_flows(p.get('flows') or [])
        except Exception:
            pass
        # Mirror result into run-mode operator HMI
        if hasattr(self,'operator_hmi') and self.operator_hmi is not None:
            try:
                annotated=self._pick_annotated_image(records) or ''
                self.operator_hmi.set_runtime(result, image=self.image, annotated=annotated)
                # Re-apply Display fit/channel after set_runtime so HMI panes keep live mode
                if _disp_applied:
                    disp_step = next((s for s in (self.document.project.get('steps') or []) if s.get('id')==ann_sid), None)
                    if disp_step:
                        self._apply_display_to_result_pane(disp_step, image=annotated_live)
            except Exception:
                pass
        text={'completed':'运行完成','cancelled':'已停止','failed':'运行失败'}.get(result.get('state'),result.get('state','未知'))
        self.log(f"{text} · {elapsed} ms"+(' · '+result['error'] if result.get('error') else ''))
        state=result.get('state')
        # Global triggers: string match on receive_data payloads; event 流程结束/NG
        if not getattr(self, '_dispatching_triggers', False):
            try:
                if state == 'completed':
                    self._fire_string_triggers_from_results(records)
                    # 流程结束：连续/运行全部进行中时跳过「再执行」类，避免打断切图
                    if not self.continuous and not self.run_all_filmstrip:
                        self._fire_event_triggers('流程结束')
                    else:
                        from desktop.global_triggers import collect_event_commands
                        cmds = [c for c in collect_event_commands(self.document.project, '流程结束')
                                if (c.get('type') or '') not in ('执行·单次', '执行', '执行·连续', '执行·继续')]
                        self._dispatch_global_triggers(cmds, reason='流程结束')
                elif state == 'failed':
                    self._fire_event_triggers('流程NG')
            except Exception as err:
                self.log(f'全局触发派发异常：{err}')
        if state=='cancelled':
            was_c = bool(self.continuous)
            self.continuous=False;self.run_all_filmstrip=False;self._run_target=None
            if was_c:
                self._flush_after_continuous()
            return
        if self.run_all_filmstrip and state=='completed':
            if getattr(self, '_continuous_paused', False):
                self.log('运行全部暂停中 — 跳过下次切图')
                return
            if self.filmstrip.advance():
                QTimer.singleShot(self._filmstrip_advance_delay_ms(), lambda:self.guard(self.run) if self.run_all_filmstrip and not getattr(self,'_continuous_paused',False) else None)
            else:
                self.run_all_filmstrip=False
                self._continuous_paused=False
                try:
                    if hasattr(self,'filmstrip') and hasattr(self.filmstrip,'set_continuous_paused'):
                        self.filmstrip.set_continuous_paused(False)
                    if hasattr(self,'filmstrip') and hasattr(self.filmstrip,'set_continuous_controls_enabled'):
                        self.filmstrip.set_continuous_controls_enabled(False)
                    if hasattr(self,'filmstrip') and hasattr(self.filmstrip,'set_pause_owner'):
                        self.filmstrip.set_pause_owner(None)
                    self._sync_pause_owner_badges(None)
                except Exception:
                    pass
                self.log('运行全部完成')
            return
        if state in ('failed', 'cancelled'):
            self._pending_trigger_cmds = []
        elif state == 'completed' and not self.continuous and not self.run_all_filmstrip:
            pending = list(getattr(self, '_pending_trigger_cmds', None) or [])
            self._pending_trigger_cmds = []
            if pending:
                self.log(f'链式触发 · 续派 {len(pending)} 条')
                QTimer.singleShot(0, lambda p=pending: self.guard(
                    lambda: self._dispatch_global_triggers(p, reason='链式触发')))
        if self.continuous and state=='completed':
            if getattr(self, '_continuous_paused', False):
                self.log('连续运行暂停中 — 跳过下次调度')
                return
            cfg=normalize_source(self.document.project.get('sourceConfig'))
            target=self._run_target
            if cfg.get('mode')=='local' and self.filmstrip.auto_switch.isChecked() and not target:
                if self.filmstrip.advance():
                    QTimer.singleShot(self._filmstrip_advance_delay_ms(), lambda:self.guard(lambda:self.run(None) if self.continuous and not getattr(self,'_continuous_paused',False) else None));return
                if cfg.get('stopAtLast'):
                    self.continuous=False;self._continuous_paused=False;self._run_target=None;self.log('已到最后一张，连续运行停止')
                    try:
                        if hasattr(self,'filmstrip') and hasattr(self.filmstrip,'set_continuous_paused'):
                            self.filmstrip.set_continuous_paused(False)
                    except Exception:
                        pass
                    self._flush_after_continuous();return
            delay=self._active_run_interval_ms()
            QTimer.singleShot(delay, lambda t=target: self.guard(lambda:self.run(t) if self.continuous and not getattr(self,'_continuous_paused',False) else None))

    def log(self,message):
        self.logs.appendPlainText(str(message))
        if hasattr(self,'wb_status'):self.wb_status.push_log(str(message))
        else:self.statusBar().showMessage(str(message))
        if self.app_mode=='run' and hasattr(self,'operator_hmi'):
            try:self.operator_hmi.append_log(str(message))
            except Exception:pass

    def _mirror_preview_to_operator(self):
        if self.app_mode=='run' and hasattr(self,'operator_hmi') and self.image:
            try:self.operator_hmi.set_preview_image(self.image)
            except Exception:pass

    def open_template(self, relative):
        if self.busy or not self.engine_ready:return
        if not self.confirm_discard():return
        path=(self.root/relative).resolve()
        if not path.is_file():raise ValueError('模板不存在：'+str(path))
        # Copy into memory as a new unsaved project so templates stay pristine
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        value['id']=__import__('uuid').uuid4().hex
        value['name']=value.get('name') or path.stem
        def loaded(reply):
            self.document.load(reply['project']);self.filename=None;self.results.set_results([])
            self.image='';self.input_view.show_data('');self.output_view.show_data('');self.flow.fit()
            self.clear_cloud();self.last_result=None
            notes=(reply['project'].get('notes') or '').strip()
            if notes:self.demo_notice.setText(notes);self.demo_notice.show()
            else:self.demo_notice.hide()
            self.log('已从模板新建：'+reply['project']['name']+'（尚未保存，可用 Ctrl+S 存到本机工程）')
            QTimer.singleShot(300, self.maybe_warm_camera)
        self.request('project/validate',{'project':value},loaded)

    def show_platform_welcome(self):
        cats={}
        for d in self.definitions.values():
            cats[d.get('category','其他')]=cats.get(d.get('category','其他'),0)+1
        summary='、'.join(f'{c} {n}' for c,n in sorted(cats.items(), key=lambda x:-x[1])[:6])
        self.demo_notice.setText(
            'SIEANS Vision 视觉检测平台已就绪。\n'
            f'算子库 {len(self.definitions)} 个（{summary}…）。\n'
            '开始：左侧拖入算子连线，或 文件→从模板新建检测工程 / 工具栏「演示工程」。\n'
            '设备：设备与模型 → 相机与连续采集。运行：工具栏「▶ 运行流程」。'
        )
        self.demo_notice.show()

    def run_platform_health(self):
        try:
            from desktop.startup_check import run_check
            report=run_check(self.root)
        except Exception as error:
            self.log('启动自检未完成：'+str(error));return
        self._health=report
        self.wb_status.push_log(report.get('short') or report.get('message','').split('\n')[0])
        self.log(report.get('message',''))
        if report.get('camera_ready'):
            self.engine_label.setText('● 引擎就绪 · 相机在线')
        elif report.get('ok'):
            self.engine_label.setText('● 引擎就绪 · 等待相机')
        else:
            self.engine_label.setText('● 引擎就绪 · 依赖告警')

    def maybe_warm_camera(self):
        if self.busy or not self.engine_ready:return
        step=next((s for s in self.document.project.get('steps',[])
                   if s.get('operation')=='camera_capture'
                   and (s.get('params') or {}).get('driver') in ('gentl','uvc')
                   and (s.get('params') or {}).get('trigger','freerun')=='freerun'), None)
        if not step:return
        params=dict(step.get('params') or {})
        if not params.get('deviceId') and params.get('driver')=='gentl':
            self.log('相机预热跳过：尚未选择 GenTL 设备编号');return
        def done(status):
            state=status.get('state') if isinstance(status,dict) else None
            if state=='running':
                self.log('相机会话已预热，首次「运行流程」将直接取帧')
                self.wb_status.push_log('相机会话运行中 · 可直接运行流程')
            else:
                self.log('相机会话状态：'+str(state or status))
        def failed_msg(msg):
            # soft — do not block platform
            self.log('相机预热未成功（可稍后在「设备与模型→相机」连接）：'+str(msg))
        try:
            rid=self.backend.request('camera/session/start', dict(
                params=params, intervalMs=100, reconnectAttempts=2, reconnectMs=1000, autoStart=False))
            self.pending[rid]=done
        except Exception as error:
            failed_msg(error)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is getattr(self,'_canvas_host',None) and event.type()==QEvent.Type.Resize:
            self._place_minimap()
            try:
                self._place_canvas_status_chip()
            except Exception:
                pass
        # Chip click-to-dismiss / Esc on chip (advances queue)
        if obj is getattr(self, '_canvas_status_chip', None):
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                if event.type() == QEvent.Type.MouseButtonRelease:
                    try:
                        self._dismiss_canvas_status_chip()
                    except Exception:
                        pass
                return True
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                try:
                    self._dismiss_canvas_status_chip()
                except Exception:
                    pass
                return True
        return super().eventFilter(obj, event)

    def _chip_esc_blocked_by_focus(self):
        """True when Esc should go to property float / modal, not dismiss chip."""
        from PySide6.QtWidgets import QApplication, QDialog
        app = QApplication.instance()
        if app is None:
            return False
        try:
            modal = app.activeModalWidget()
            if modal is not None and modal is not self:
                return True
        except Exception:
            pass
        fw = None
        try:
            fw = app.focusWidget()
        except Exception:
            fw = None
        if fw is None:
            return False
        pf = getattr(self, 'property_float', None)
        w = fw
        while w is not None:
            if pf is not None and w is pf:
                return True
            try:
                if isinstance(w, QDialog) and w is not self and w.isVisible():
                    return True
            except Exception:
                pass
            try:
                w = w.parentWidget()
            except Exception:
                break
        return False

    def keyPressEvent(self, event):
        # Esc dismisses canvas status chip — but not when float/modal owns focus
        if event.key() == Qt.Key.Key_Escape:
            chip = getattr(self, '_canvas_status_chip', None)
            if chip is not None and chip.isVisible():
                if self._chip_esc_blocked_by_focus():
                    super().keyPressEvent(event)
                    return
                try:
                    self._dismiss_canvas_status_chip()
                except Exception:
                    pass
                event.accept()
                return
        super().keyPressEvent(event)

    def _place_minimap(self):
        host=getattr(self,'_canvas_host',None);mm=getattr(self,'minimap',None)
        if not host or not mm:return
        mm.adjustSize()
        mm.move(max(8, host.width()-mm.width()-12), max(8, host.height()-mm.height()-12))
        mm.raise_()
        mm.show()

    def _autoload_source_image(self, force=False):
        """Load current local sourceConfig / filmstrip image into self.image (open-and-run)."""
        if self.busy and not force:
            return bool(self.image)
        if self.image and not force:
            return True
        cfg = normalize_source(self.document.project.get('sourceConfig'))
        if cfg.get('mode', 'local') not in ('local', '', None):
            return bool(self.image)
        images = list(cfg.get('images') or [])
        if not images and hasattr(self, 'filmstrip'):
            images = list(self.filmstrip.paths() or [])
        if not images:
            return bool(self.image)
        idx = int(cfg.get('currentIndex') or 0)
        if idx < 0 or idx >= len(images):
            idx = 0
        target = images[idx]
        try:
            self.load_filmstrip_path(target)
        except Exception as err:
            self.log(f'自动载入源图失败：{err}')
            return False
        return bool(self.image)

    def load_filmstrip_path(self, path):
        if self.busy or not path:return
        from pathlib import Path as P
        p=P(path)
        if not p.is_file() and not p.is_absolute():
            cand=self.root/path
            if cand.is_file():p=cand
        if not p.is_file():
            self.log(f'胶片条路径不存在：{path}');return
        if p.stat().st_size>12*1024*1024:raise ValueError('图像不能超过 12 MB')
        raw=p.read_bytes();image=QImage.fromData(raw)
        if image.isNull() or image.width()*image.height()>16000000:raise ValueError('无效图像，或超过 1600 万像素')
        data='data:image/'+('jpeg' if p.suffix.lower() in ('.jpg','.jpeg') else p.suffix[1:].lstrip('.') or 'png')+';base64,'+base64.b64encode(raw).decode()
        self.image=data;self.input_view.show_data(data);self.output_view.show_data('');self.results.set_results([])
        self.clear_cloud();self.last_result=None;self._mirror_preview_to_operator()
        # persist currentIndex
        proj=deepcopy(self.document.project)
        cfg=normalize_source(proj.get('sourceConfig'))
        try:cfg['currentIndex']=list(cfg.get('images') or self.filmstrip.paths()).index(str(p.resolve()))
        except ValueError:cfg['currentIndex']=self.filmstrip.current_index()
        proj['sourceConfig']=cfg
        # avoid history spam — soft assign without commit when only index changes during run-all
        if not self.busy and not self.continuous and not self.run_all_filmstrip:
            self.document.project=proj  # soft; document_changed not forced
        self.log(f'胶片条载入 {image.width()} × {image.height()} · {p.name}')
        if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)

    def filmstrip_list_changed(self, paths):
        if self.busy:return
        p=deepcopy(self.document.project)
        cfg=normalize_source(p.get('sourceConfig'))
        cfg['images']=list(paths)
        cfg['currentIndex']=self.filmstrip.current_index() if paths else 0
        cfg['mode']='local'
        p['sourceConfig']=cfg
        self.guard(lambda:self.document.commit(p))
        self._sync_filmstrip_interval_hint()
        self.log(f'添加模块: 流程1.图像源1 · 本地图 {len(paths)} 张' if paths else '图像源本地列表已清空')

    def _sync_hmi_pause_buttons(self, paused):
        """Mirror ContinuousRun / 运行全部 pause onto HMI 生产统计 buttons."""
        hmi = getattr(self, 'operator_hmi', None)
        if hmi is None:
            return
        paused = bool(paused)
        panels = list(getattr(hmi, '_stats_panels', None) or [])
        for panel in panels:
            btn = getattr(panel, '_pause_btn', None)
            if btn is None:
                continue
            if btn.isChecked() == paused:
                continue
            btn.blockSignals(True)
            btn.setChecked(paused)
            panel._paused = paused
            btn.setText('▶ 继续计数' if paused else '⏸ 暂停计数')
            btn.blockSignals(False)

    def _on_hmi_pause_toggled(self, paused):
        """Bridge OperatorHmiView 暂停计数 ↔ ContinuousRun / 运行全部 pause."""
        if paused:
            if self.continuous or self.run_all_filmstrip:
                self.pause_continuous()
        else:
            if self.continuous or self.run_all_filmstrip:
                self.resume_continuous()

    def _on_filmstrip_continuous_pause(self, paused):
        if paused:
            self.pause_continuous()
        else:
            self.resume_continuous()

    def filmstrip_stop_at_last_changed(self, enabled):
        if self.busy:return
        p=deepcopy(self.document.project)
        cfg=normalize_source(p.get('sourceConfig'))
        cfg['stopAtLast']=bool(enabled)
        p['sourceConfig']=cfg
        self.guard(lambda:self.document.commit(p))

    def filmstrip_auto_changed(self, enabled):
        if self.busy:return
        p=deepcopy(self.document.project)
        cfg=normalize_source(p.get('sourceConfig'))
        cfg['autoSwitch']=bool(enabled)
        p['sourceConfig']=cfg
        self.guard(lambda:self.document.commit(p))

    def run_all_images(self):
        if self.busy or not self.engine_ready:return
        if not self.filmstrip.paths():raise ValueError('请先在胶片条添加本地图像')
        self.continuous=False;self.run_all_filmstrip=True;self._continuous_paused=False
        try:
            if hasattr(self.filmstrip, 'set_pause_owner'):
                self.filmstrip.set_pause_owner('run_all')
            self._sync_pause_owner_badges('run_all')
            if hasattr(self.filmstrip, 'set_continuous_controls_enabled'):
                self.filmstrip.set_continuous_controls_enabled(True)
            if hasattr(self.filmstrip, 'set_continuous_paused'):
                self.filmstrip.set_continuous_paused(False)
        except Exception:
            pass
        # jump to first
        self.filmstrip.thumbs.setCurrentRow(0)
        self.guard(self.run)


    def _ensure_camera_frame_for_run(self, cfg):
        """Pull latest session frame into self.image; raise clear Chinese errors if not connected."""
        if not self.backend.is_ready:
            raise ValueError('原生引擎未就绪，无法从相机 SDK 取图')
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication
        cam = cfg.get('cameraId') or (cfg.get('cameraParams') or {}).get('deviceId') or '未选择'
        mode = cfg.get('mode') or 'camera'
        self.log(f'相机取图中… 模式={mode} · 设备={cam}')
        self._sync_filmstrip_visibility()
        status_box = {'value': None, 'error': None, 'timed_out': False}
        loop = QEventLoop(self)
        try:
            rid = self.backend.request('camera/session/status', {})
        except Exception as exc:
            raise ValueError(f'无法查询相机会话状态：{exc}') from exc

        def on_result(request_id, value):
            if request_id != rid and status_box.get('cap_rid') != request_id:
                return
            if request_id == rid:
                status_box['value'] = value if isinstance(value, dict) else {}
                st = status_box['value'].get('state')
                if st != 'running':
                    loop.quit()
                    return
                sid = status_box['value'].get('id')
                if not sid:
                    status_box['error'] = '相机会话缺少 id'
                    loop.quit()
                    return
                try:
                    cap = self.backend.request('camera/capture', {
                        'driver': 'session', 'sessionId': sid,
                        'framePolicy': 'latest', 'maxAgeMs': 5000, 'timeoutMs': 5000,
                    })
                except Exception as exc:
                    status_box['error'] = f'发起取帧失败：{exc}'
                    loop.quit()
                    return
                status_box['cap_rid'] = cap
                return
            if request_id == status_box.get('cap_rid'):
                status_box['frame'] = value if isinstance(value, dict) else {}
                loop.quit()

        def on_error(request_id, message):
            if request_id in (rid, status_box.get('cap_rid')):
                status_box['error'] = message
                loop.quit()

        def on_timeout():
            status_box['timed_out'] = True
            loop.quit()

        self.backend.result.connect(on_result)
        self.backend.error.connect(on_error)
        QTimer.singleShot(12000, on_timeout)
        loop.exec()
        try:
            self.backend.result.disconnect(on_result)
            self.backend.error.disconnect(on_error)
        except Exception:
            pass
        QApplication.processEvents()
        if status_box.get('error'):
            raise ValueError('相机 SDK 取图失败：' + str(status_box['error']))
        if status_box.get('timed_out') and not status_box.get('frame'):
            raise ValueError(
                f'相机取图超时（12s）。模式={mode} · 设备={cam}。'
                '请确认「相机管理」已连接且有实时预览，或切回本地图源用胶片条调试。'
            )
        st = (status_box.get('value') or {}).get('state')
        if st != 'running':
            raise ValueError(
                f'图像源为相机/SDK，但相机会话未连接（状态：{st or "未知"}，设备：{cam}）。'
                '请打开「相机管理」→ 选择相机 → 打开「连接相机」。'
                '调试可用：图像源属性切回「本地」以显示胶片条。'
            )
        frame = status_box.get('frame') or {}
        image = frame.get('annotatedImage') or frame.get('image') or ''
        if not image:
            raise ValueError(
                '相机会话已连接但尚无有效帧。请稍候再「运行」，'
                '或在相机管理中点「取最新缓存帧」；也可切回本地图源。'
            )
        self.image = image
        self.cloud = frame.get('cloud')
        self.depth = frame.get('depth')
        self.input_view.show_data(self.image)
        self.images.setCurrentIndex(0)
        self._mirror_preview_to_operator()
        self.log(f'相机帧已载入 · 设备={cam}')

    def open_camera_manager(self):
        if self.busy:return
        if not self.engine_ready or not self.backend.is_ready:
            self.log('引擎未就绪，无法打开相机管理（请等待原生引擎启动）')
            return
        from desktop.camera_manager import CameraManagerDialog
        dlg=CameraManagerDialog(self.backend, self)
        def _open_full_camera_workbench():
            # CameraManager is ApplicationModal via exec(); leaving it open makes
            # CameraDialog appear on top but receive no clicks (Close/X dead).
            dlg.reject()
            QTimer.singleShot(0, lambda: self.open_panel('camera'))
        dlg.openFullWorkbench.connect(_open_full_camera_workbench)
        def accepted(name):
            p=deepcopy(self.document.project)
            cfg=normalize_source(p.get('sourceConfig'))
            if cfg.get('mode') not in ('camera', 'sdk'):
                cfg['mode']='camera'
            cfg['cameraId']=name
            p['sourceConfig']=cfg
            self.guard(lambda:self.document.commit(p))
            self.log(f'图像源已关联相机：{name}')
        def on_params(params):
            p=deepcopy(self.document.project)
            cfg=normalize_source(p.get('sourceConfig'))
            if cfg.get('mode') not in ('camera', 'sdk'):
                cfg['mode']='camera'
            cfg['cameraId']=params.get('deviceId') or cfg.get('cameraId') or ''
            cfg['cameraParams']=deepcopy(params)
            p['sourceConfig']=cfg
            # soft+commit so run path can warm session
            self.guard(lambda:self.document.commit(p))
            self.log('已保存相机 SDK 参数：'+str(params.get('driver'))+' · '+str(params.get('deviceId') or ''))
        def on_frame(frame):
            self.accept_frame(frame)
        dlg.acceptedDevice.connect(accepted)
        dlg.deviceParams.connect(on_params)
        dlg.frame_ready.connect(on_frame)
        dlg.exec()


    # ---------- A1–A6: design/run · multi-flow · .prc · 全流程 · 运行界面设计 ----------
    def refresh_flow_tabs(self):
        if not hasattr(self,'flow_tab_bar'):return
        p=self.document.project
        flow_scheme.ensure_scheme(p)
        self.flow_tab_bar.set_flows(p.get('flows') or [], p.get('activeFlowId'), self.showing_all_flows)
        if hasattr(self,'all_flows_panel') and self.showing_all_flows:
            self.all_flows_panel.set_flows(p.get('flows') or [])

    def show_all_flows(self):
        if self.busy:return
        p=deepcopy(self.document.project)
        flow_scheme.ensure_scheme(p)
        flow_scheme.sync_active_into_flows(p)
        self.document.project.update({k:p[k] for k in ('flows','activeFlowId','flowEdges') if k in p})
        # commit without history noise: write through load-less sync
        self.document.project['flows']=p['flows']
        self.showing_all_flows=True
        if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(1)
        self.all_flows_panel.set_flows(p.get('flows') or [])
        self.refresh_flow_tabs()
        self.log('全流程视图')

    def select_flow_tab(self, flow_id):
        if self.busy:return
        self.guard(lambda:self._select_flow_tab(flow_id))

    def _select_flow_tab(self, flow_id):
        p=deepcopy(self.document.project)
        flow_scheme.activate_flow(p, flow_id)
        # Prefer commit so scheme.flows stays in history; then align saved if only activeFlowId changed
        before_saved=deepcopy(self.document.saved)
        self.document.commit(p)
        try:
            flow_scheme.ensure_scheme(before_saved)
            flow_scheme.sync_active_into_flows(before_saved)
            cur=flow_scheme.scheme_for_disk(self.document.project)
            # Tab switch alone should not dirty an otherwise clean scheme
            saved_flows=[{k:v for k,v in f.items() if k!='cardPosition'} for f in (before_saved.get('flows') or [])]
            cur_flows=[{k:v for k,v in f.items() if k!='cardPosition'} for f in (cur.get('flows') or [])]
            if saved_flows==cur_flows and before_saved.get('name')==cur.get('name'):
                self.document.saved=deepcopy(self.document.project)
        except Exception:
            pass
        self.showing_all_flows=False
        if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(0)
        self.selected=None;self.refresh_parameters();self.flow.fit()
        self.refresh_flow_tabs()
        name=next((f.get('name') for f in self.document.project.get('flows') or [] if f.get('id')==flow_id),'流程')
        self.log(f'已切换到流程：{name}')

    def add_flow_tab(self):
        if self.busy:return
        p=deepcopy(self.document.project)
        flow=flow_scheme.add_flow(p)
        flow_scheme.activate_flow(p, flow['id'])
        self.document.commit(p)
        self.showing_all_flows=False
        if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(0)
        self.flow.fit();self.refresh_flow_tabs()
        self.log(f'已新建流程：{flow.get("name")}')

    def run_flow_once(self, flow_id):
        def go():
            if self.document.project.get('activeFlowId')!=flow_id and not self.showing_all_flows:
                self._select_flow_tab(flow_id)
            elif self.showing_all_flows or self.document.project.get('activeFlowId')!=flow_id:
                self._select_flow_tab(flow_id)
            self.run_once()
        self.guard(go)

    def run_flow_continuous(self, flow_id):
        def go():
            if self.document.project.get('activeFlowId')!=flow_id:
                self._select_flow_tab(flow_id)
            self.run_continuous()
        self.guard(go)

    def on_flow_meta_changed(self, flow_id, meta):
        if self.busy:return
        p=deepcopy(self.document.project)
        flow_scheme.update_flow_meta(p, flow_id, **meta)
        # keep top-level if active
        if p.get('activeFlowId')==flow_id:
            flow_scheme.activate_flow(p, flow_id)
        self.document.commit(p)

    def flow_tab_context(self, flow_id, action):
        if self.busy and action not in ('export',):return
        self.guard(lambda:self._flow_tab_context(flow_id, action))

    def _flow_tab_context(self, flow_id, action):
        p=deepcopy(self.document.project)
        flow_scheme.ensure_scheme(p)
        flow=next((f for f in p['flows'] if f.get('id')==flow_id), None)
        if not flow:raise ValueError('流程不存在')
        if action=='export':
            self.export_process_prc(flow_id);return
        if action=='copy':
            flow_scheme.sync_active_into_flows(p)
            copy=flow_scheme.duplicate_flow(p, flow_id)
            self.document.commit(p);self.refresh_flow_tabs();self.log(f'已拷贝流程：{copy.get("name")}');return
        if action=='delete':
            if len(p.get('flows') or [])<=1:raise ValueError('至少保留一个流程')
            if QMessageBox.question(self,'删除流程',f'删除「{flow.get("name")}」？',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
                return
            flow_scheme.remove_flow(p, flow_id)
            self.document.commit(p)
            self.showing_all_flows=False
            if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(0)
            self.flow.fit();self.refresh_flow_tabs();self.log('流程已删除');return
        if action=='rename':
            name,ok=QInputDialog.getText(self,'重命名', '流程名称', text=flow.get('name') or '')
            if not ok:return
            flow_scheme.rename_flow(p, flow_id, name)
            if p.get('activeFlowId')==flow_id:
                # name only — top-level name is scheme name, not flow
                pass
            self.document.commit(p);self.refresh_flow_tabs();return
        if action=='interval':
            cur=int(flow.get('runIntervalMs') or 0)
            val=self._ask_run_interval(cur)
            if val is None:return
            flow_scheme.update_flow_meta(p, flow_id, runIntervalMs=val)
            self.document.commit(p);self.refresh_flow_tabs();self.log(f'运行间隔：{val} ms（上限 100000）');return
        if action=='stop_on_ng':
            flow_scheme.update_flow_meta(p, flow_id, stopOnNg=not bool(flow.get('stopOnNg')))
            self.document.commit(p);self.refresh_flow_tabs()
            self.log('流程执行NG时停止：'+('开' if not flow.get('stopOnNg') else '关'));return
        if action=='timeout':
            cur=int(flow.get('timeoutMs') or 0)
            val,ok=QInputDialog.getInt(self,'设置流程超时时间','超时时间(ms)，0=不限制',cur,0,3600000,100)
            if not ok:return
            flow_scheme.update_flow_meta(p, flow_id, timeoutMs=val)
            self.document.commit(p);self.log(f'流程超时：{val} ms');return

    def export_process_prc(self, flow_id=None):
        if self.busy:return
        p=deepcopy(self.document.project)
        flow_scheme.ensure_scheme(p);flow_scheme.sync_active_into_flows(p)
        flows=p.get('flows') or []
        if not flows:raise ValueError('无流程可导出')
        if flow_id is None:
            names=[f.get('name') or '流程' for f in flows]
            name,ok=QInputDialog.getItem(self,'导出流程','选择要导出的流程',names,0,False)
            if not ok:return
            flow_id=flows[names.index(name)]['id']
        payload=flow_scheme.export_prc(p, flow_id)
        fname=(payload['flow'].get('name') or '流程')+'.prc'
        path,_=QFileDialog.getSaveFileName(self,'导出流程',fname,'流程 .prc (*.prc);;JSON (*.json)')
        if not path:return
        Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        self.log('已导出流程：'+path)

    def import_process_prc(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,'导入流程','','流程 .prc (*.prc);;JSON (*.json);;全部 (*.*)')
        if not path:return
        payload=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        p=deepcopy(self.document.project)
        flow=flow_scheme.import_prc(p, payload)
        self.document.commit(p)
        self.refresh_flow_tabs()
        self.log(f'已导入流程：{flow.get("name")}')

    def on_mode_switch(self, checked):
        self.set_app_mode('run' if checked else 'design')

    def toggle_app_mode(self):
        self.set_app_mode('design' if self.app_mode=='run' else 'run')

    def set_app_mode(self, mode):
        mode='run' if mode=='run' else 'design'
        self.app_mode=mode
        try:
            self._sync_filmstrip_visibility()
        except Exception:
            pass
        if hasattr(self,'mode_switch'):
            self.mode_switch.blockSignals(True)
            self.mode_switch.setChecked(mode=='run', animate=False)
            self.mode_switch.blockSignals(False)
        if hasattr(self,'mode_badge'):
            self.mode_badge.setText('运行模式' if mode=='run' else '设计态')
            self.mode_badge.setProperty('runMode','true' if mode=='run' else 'false')
            self.mode_badge.style().unpolish(self.mode_badge);self.mode_badge.style().polish(self.mode_badge)
        # Lock graph edit
        if hasattr(self,'scene'):
            self.scene.set_edit_locked(mode=='run')
        # Layout: hide toolbox / flow canvas / design image in run mode; show operator HMI
        if hasattr(self,'_left_pane') and self._left_pane is not None:
            self._left_pane.setVisible(mode=='design')
        if hasattr(self,'_flow_pane'):
            self._flow_pane.setVisible(mode=='design')
        if hasattr(self,'_image_pane') and self._image_pane is not None:
            self._image_pane.setVisible(mode=='design')
        if hasattr(self,'_run_pane'):
            self._run_pane.setVisible(mode=='run')
        if hasattr(self,'_main_horizontal'):
            if mode=='run':
                self._main_horizontal.setSizes([0,0,0,1600])
            else:
                self._main_horizontal.setSizes([300,560,520,0])
        # Close property float in run mode
        if mode=='run' and self.property_float:
            try:self.property_float.close()
            except Exception:pass
            self.property_float=None
        if mode=='run' and hasattr(self,'operator_hmi'):
            self.operator_hmi.reload_layout(self.document.project)
            # Seed image panes with last annotated / current source
            annotated=''
            if self.last_result:
                for record in reversed(self.last_result.get('results') or []):
                    annotated=(record.get('output') or {}).get('annotatedImage') or ''
                    if annotated:break
                self.operator_hmi.set_runtime(self.last_result, image=self.image, annotated=annotated)
            elif self.image:
                self.operator_hmi.set_preview_image(self.image)
        self.set_busy(self.busy)
        self.document_changed()
        self.log('已切换到'+('运行模式（操作员 HMI · 画布锁定）' if mode=='run' else '设计态（完整工作台）'))


    # ---- B3 组合模块：进入 / 退出嵌套画布 ----
    def _group_breadcrumb_parts(self):
        """Full nest path: 主流程 › G1 › G2 …"""
        parts = ['主流程']
        for fr in (self._group_stack or []):
            parts.append(fr.get('name') or '组合模块')
        return parts

    def _refresh_group_breadcrumb(self):
        if not hasattr(self, '_group_breadcrumb') or self._group_breadcrumb is None:
            return
        if self._group_stack:
            self._group_breadcrumb.set_path(None, parts=self._group_breadcrumb_parts())
            self._group_breadcrumb.setVisible(True)
        else:
            self._group_breadcrumb.setVisible(False)
        # Breadcrumb show/hide changes chip Y; re-place after layout
        try:
            self._place_canvas_status_chip()
        except Exception:
            pass
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._place_canvas_status_chip)
        except Exception:
            pass

    def enter_group_module(self, node_id):
        step = next((s for s in self.document.project.get('steps', []) if s.get('id') == node_id), None)
        if not step or step.get('operation') != 'group':
            self.log('仅组合模块可进入'); return
        from copy import deepcopy
        params = normalize_group_params(step.get('params'))
        step['params'] = params
        if not group_bindings_ready(params):
            self.log('进组被拒绝：须绑定 ImageData / InputROI（属性浮窗 · 输入设置）')
            return
        inner = params.get('inner') or default_group_inner()
        params['inner'] = inner
        # Snapshot outer project + undo history so mid-nest undo stays on this nest level
        try:
            self.document.commit(deepcopy(self.document.project))
        except Exception:
            pass
        self._group_stack.append({
            'node_id': node_id,
            'name': step.get('name') or '组合模块',
            'outer_project': deepcopy(self.document.project),
            'outer_history': deepcopy(getattr(self.document, 'history', None) or []),
            'outer_history_labels': list(getattr(self.document, 'history_labels', None) or []),
            'outer_index': int(getattr(self.document, 'index', 0) or 0),
            'outer_saved': deepcopy(getattr(self.document, 'saved', None)),
        })
        view_project = deepcopy(self.document.project)
        view_project['steps'] = deepcopy(inner.get('steps') or [])
        view_project['edges'] = deepcopy(inner.get('edges') or [])
        view_project['sourcePosition'] = deepcopy(inner.get('sourcePosition') or dict(x=300, y=40))
        nest_names = ' / '.join(fr.get('name') or '组合' for fr in self._group_stack)
        view_project['name'] = f'{self.document.project.get("name","方案")} / {nest_names}'
        # Soft switch + fresh history branch for this nest (mid-nest undo/redo)
        self.document.project = view_project
        self.document.history = [deepcopy(view_project)]
        self.document.history_labels = ['']
        self.document.index = 0
        self.document.saved = deepcopy(view_project)
        self.selected = None
        self.scene.rebuild()
        self.document_changed()
        self._refresh_group_breadcrumb()
        self.log(f'已进入组合模块「{step.get("name") or node_id}」· 深度 {len(self._group_stack)} · 可撤销/重做本层编辑')

    def exit_group_module(self):
        if not self._group_stack:
            self._refresh_group_breadcrumb(); return
        from copy import deepcopy
        frame = self._group_stack.pop()
        inner_steps = deepcopy(self.document.project.get('steps') or [])
        inner_edges = deepcopy(self.document.project.get('edges') or [])
        inner_sp = deepcopy(self.document.project.get('sourcePosition') or dict(x=300, y=40))
        outer = frame['outer_project']
        for s in outer.get('steps', []):
            if s.get('id') == frame['node_id'] and s.get('operation') == 'group':
                params = normalize_group_params(s.get('params'))
                params['inner'] = {
                    'steps': inner_steps,
                    'edges': inner_edges,
                    'sourcePosition': inner_sp,
                    'localVariables': (s.get('params') or {}).get('inner', {}).get('localVariables') or {},
                }
                s['params'] = params
                break
        # Restore outer history: keep pre-enter tip; fold nest history tips into
        # successive merged outer tips so Undo/Redo chain survives multi-exit (depth≥3).
        hist = list(frame.get('outer_history') or [])
        idx = int(frame.get('outer_index') or 0)
        nest_hist = list(getattr(self.document, 'history', None) or [])
        nest_idx = int(getattr(self.document, 'index', 0) or 0)
        # Current merged outer (from live document.project inner) already in `outer`
        if hist:
            if 0 <= idx < len(hist):
                base = hist[:idx + 1]
            else:
                base = list(hist)
                idx = len(base) - 1 if base else 0
            tips = []
            # nest_hist[0] ≈ enter snapshot (≡ pre-enter inner); map k>=1 → outer tips
            # Always include tips through nest tip AND remaining redo beyond nest_idx
            def _merge_inner(outer_proj, nest_proj):
                o = deepcopy(outer_proj)
                for s in o.get('steps', []):
                    if s.get('id') == frame['node_id'] and s.get('operation') == 'group':
                        params = normalize_group_params(s.get('params'))
                        params['inner'] = {
                            'steps': deepcopy(nest_proj.get('steps') or []),
                            'edges': deepcopy(nest_proj.get('edges') or []),
                            'sourcePosition': deepcopy(nest_proj.get('sourcePosition') or dict(x=300, y=40)),
                            'localVariables': (s.get('params') or {}).get('inner', {}).get('localVariables') or {},
                        }
                        s['params'] = params
                        break
                return o
            pre_outer = deepcopy(frame.get('outer_project') or outer)
            if len(nest_hist) <= 1:
                tips = [deepcopy(outer)]
                new_index = len(base)  # tip after append
            else:
                for k in range(1, len(nest_hist)):
                    tips.append(_merge_inner(pre_outer, nest_hist[k]))
                if not tips:
                    tips = [deepcopy(outer)]
                # Map nest_idx → position in tips (nest 0 = pre-enter = base[-1])
                # nest_idx 1 → tips[0], nest_idx 2 → tips[1], ...
                new_index = (idx + nest_idx) if nest_idx >= 1 else idx
                # Ensure current live merge is last tip when at nest tip with no extra redo
                # Replace tips[nest_idx-1] with live `outer` so unsaved-equal commits match
                if nest_idx >= 1 and (nest_idx - 1) < len(tips):
                    tips[nest_idx - 1] = deepcopy(outer)
                elif nest_idx >= len(nest_hist):
                    pass
                elif nest_idx == 0:
                    new_index = idx
                    # keep tips as redo stack beyond pre-enter
            hist = base + tips
            if nest_idx >= 1:
                new_index = idx + nest_idx
            else:
                new_index = idx  # exited at enter snapshot; redos available after
            new_index = max(0, min(new_index, len(hist) - 1))
            self.document.project = deepcopy(hist[new_index])
            self.document.history = hist
            self.document.index = new_index
            # Rebuild labels: outer prefix + empty tip slots (hybrid label only on explicit commits)
            try:
                olabels = list(frame.get('outer_history_labels') or [])
                if 0 <= idx < len(olabels):
                    olabels = olabels[: idx + 1]
                while len(olabels) < len(base):
                    olabels.append('')
                tip_labels = [''] * max(0, len(hist) - len(base))
                self.document.history_labels = (olabels + tip_labels)[: len(hist)]
            except Exception:
                try:
                    self.document.sync_history_labels()
                except Exception:
                    pass
            if frame.get('outer_saved') is not None:
                self.document.saved = frame['outer_saved']
            # Fold boundary: pre-enter tip index `idx` — undo/redo across logs a tip
            try:
                marks = list(getattr(self, '_nest_fold_marks', None) or [])
                marks.append({
                    'index': int(idx),
                    'name': frame.get('name') or '组合模块',
                    'tips': max(0, len(hist) - len(base)),
                    'depth_after': len(self._group_stack),
                })
                # Cap
                self._nest_fold_marks = marks[-32:]
            except Exception:
                pass
            self.document.changed.emit()
        else:
            self.document.load(outer)
        self.scene.rebuild()
        self._refresh_group_breadcrumb()
        self.log(f'已退出组合模块「{frame["name"]}」· 剩余深度 {len(self._group_stack)}')
        # Leave nest → drop session skip for this frame (or all if back to root)
        try:
            if not self._group_stack:
                self._clear_jump_confirm_skip()
            else:
                self._clear_jump_confirm_skip(frame.get('node_id') or frame.get('name'))
        except Exception:
            pass
        try:
            if hasattr(self.document, 'sync_history_labels'):
                self.document.sync_history_labels()
        except Exception:
            pass

    def _refresh_undo_redo_labels(self):
        """Show history label on undo/redo menu text + tooltips + status-bar hover."""
        labels = list(getattr(self.document, 'history_labels', None) or [])
        idx = int(getattr(self.document, 'index', 0) or 0)
        undo_label = ''
        if idx > 0 and 0 <= idx < len(labels):
            undo_label = (labels[idx] or '').strip()
        redo_label = ''
        if 0 <= idx + 1 < len(labels):
            redo_label = (labels[idx + 1] or '').strip()
        ua = getattr(self, 'undo_action', None)
        ra = getattr(self, 'redo_action', None)
        if ua is not None:
            if undo_label:
                ua.setText(f'撤销「{undo_label}」')
                ua.setToolTip(f'撤销：{undo_label} (Ctrl+Z)')
            else:
                ua.setText('撤销')
                ua.setToolTip('撤销 (Ctrl+Z)')
        if ra is not None:
            if redo_label:
                ra.setText(f'重做「{redo_label}」')
                ra.setToolTip(f'重做：{redo_label} (Ctrl+Y)')
            else:
                ra.setText('重做')
                ra.setToolTip('重做 (Ctrl+Y)')
        try:
            wb = getattr(self, 'wb_status', None)
            if wb is not None:
                parts = []
                if undo_label and idx > 0:
                    parts.append(f'可撤销：{undo_label}')
                if redo_label:
                    parts.append(f'可重做：{redo_label}')
                tip = ' · '.join(parts) if parts else '撤销/重做'
                wb.setToolTip(tip)
        except Exception:
            pass

    def _jump_skip_persist_enabled(self):
        return bool(getattr(self, '_jump_skip_persist', False))

    def _load_jump_skip_settings(self):
        """Load persist toggle + optional per-nest skip keys from QSettings."""
        try:
            s = self._settings()
            persist = s.value('jumpConfirmSkipPersist', False)
            if isinstance(persist, str):
                persist = persist.lower() in ('1', 'true', 'yes')
            self._jump_skip_persist = bool(persist)
            act = getattr(self, '_jump_skip_persist_action', None)
            if act is not None:
                act.blockSignals(True)
                act.setChecked(self._jump_skip_persist)
                act.blockSignals(False)
            if self._jump_skip_persist:
                raw = s.value('jumpConfirmSkipKeys', [])
                if isinstance(raw, str):
                    raw = [raw] if raw else []
                keys = [str(k) for k in (raw or []) if str(k).strip()]
                self._jump_confirm_skip = set(keys)
        except Exception:
            self._jump_skip_persist = False

    def _save_jump_skip_keys(self):
        if not self._jump_skip_persist_enabled():
            return
        try:
            keys = sorted(str(k) for k in (getattr(self, '_jump_confirm_skip', None) or set()))
            self._settings().setValue('jumpConfirmSkipKeys', keys)
        except Exception:
            pass

    def _toggle_jump_skip_persist(self, checked=None):
        act = getattr(self, '_jump_skip_persist_action', None)
        if checked is None and act is not None:
            checked = act.isChecked()
        self._jump_skip_persist = bool(checked)
        try:
            self._settings().setValue('jumpConfirmSkipPersist', self._jump_skip_persist)
        except Exception:
            pass
        if self._jump_skip_persist:
            self._save_jump_skip_keys()
            try:
                self.log('已开启：跨会话记住跳层确认跳过')
            except Exception:
                pass
        else:
            try:
                self._settings().setValue('jumpConfirmSkipKeys', [])
            except Exception:
                pass
            try:
                self.log('已关闭：跨会话跳层跳过（磁盘记录已清除；本会话仍有效）')
            except Exception:
                pass

    def _clear_persisted_jump_skip(self):
        try:
            self._clear_jump_confirm_skip(force=True)
            self._jump_confirm_skip = set()
            try:
                self._settings().setValue('jumpConfirmSkipKeys', [])
            except Exception:
                pass
            self.log('已清除全部已记住的跳层确认跳过')
            QMessageBox.information(self, '跳层跳过', '已清除全部已记住的跳层确认跳过。')
        except Exception as e:
            try:
                self.log(str(e))
            except Exception:
                pass

    def _edit_jump_skip_keys(self):
        """Settings list editor for remembered nest jump-skip keys."""
        keys = sorted(str(k) for k in (getattr(self, '_jump_confirm_skip', None) or set()) if str(k).strip())
        dlg = QDialog(self)
        dlg.setWindowTitle('已记住的跳层跳过')
        dlg.resize(480, 320)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel('嵌套确认跳过键（可删除单项；确定后写回本会话' +
                                ('并持久化' if self._jump_skip_persist_enabled() else '') + '）：'))
        lst = QListWidget(dlg)
        for k in keys:
            lst.addItem(QListWidgetItem(k))
        layout.addWidget(lst)
        bar = QHBoxLayout()
        rm = QPushButton('删除所选')
        def _rm():
            for item in lst.selectedItems():
                lst.takeItem(lst.row(item))
        rm.clicked.connect(_rm)
        clr = QPushButton('全部清除')
        clr.clicked.connect(lst.clear)
        bar.addWidget(rm)
        bar.addWidget(clr)
        bar.addStretch(1)
        layout.addLayout(bar)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_keys = set()
        for i in range(lst.count()):
            text = (lst.item(i).text() or '').strip()
            if text:
                new_keys.add(text)
        self._jump_confirm_skip = new_keys
        try:
            if self._jump_skip_persist_enabled():
                self._settings().setValue('jumpConfirmSkipKeys', sorted(new_keys))
            self.log(f'已更新跳层跳过列表：{len(new_keys)} 项')
        except Exception as e:
            try:
                self.log(str(e))
            except Exception:
                pass

    def _on_status_chip_context_menu(self, pos):
        """Status-bar right-click: peek chip queue / drop selected tips."""
        wb = getattr(self, 'wb_status', None)
        if wb is None:
            return
        menu = QMenu(wb)
        chip = getattr(self, '_canvas_status_chip', None)
        cur = ''
        try:
            if chip is not None and chip.isVisible():
                cur = (chip.text() or '').strip()
        except Exception:
            cur = ''
        if cur:
            short = cur if len(cur) <= 42 else (cur[:42] + '…')
            head = menu.addAction(f'当前：{short}')
            head.setEnabled(False)
            act = menu.addAction('关闭当前提示')
            act.triggered.connect(self._dismiss_canvas_status_chip)
            menu.addSeparator()
        q = list(getattr(self, '_canvas_chip_queue', None) or [])
        if q:
            peek = menu.addMenu(f'排队中（{len(q)}）')
            for i, (msg, _ms) in enumerate(q):
                short = msg if len(msg) <= 36 else (msg[:36] + '…')
                sub = peek.addMenu(f'{i + 1}. {short}')
                drop = sub.addAction('丢弃此条')
                drop.triggered.connect(lambda _=False, idx=i: self._drop_chip_queue_item(idx))
            clr = menu.addAction('清空排队')
            clr.triggered.connect(self._clear_chip_queue)
        else:
            empty = menu.addAction('排队为空')
            empty.setEnabled(False)
        try:
            menu.exec(wb.mapToGlobal(pos))
        except Exception:
            pass

    def _drop_chip_queue_item(self, index):
        q = getattr(self, '_canvas_chip_queue', None)
        if not isinstance(q, list):
            return
        try:
            i = int(index)
        except (TypeError, ValueError):
            return
        if 0 <= i < len(q):
            q.pop(i)
            try:
                chip = getattr(self, '_canvas_status_chip', None)
                if chip is not None and chip.isVisible():
                    n = len(q)
                    tip = '点击/Esc 关闭 · 多条折叠提示排队显示 · 单条最长 6s'
                    if n:
                        tip = f'点击/Esc 关闭 · 另有 {n} 条排队'
                    chip.setToolTip(tip)
            except Exception:
                pass
            try:
                self.log(f'已丢弃排队提示 #{i + 1}（剩余 {len(q)}）')
            except Exception:
                pass

    def _clear_chip_queue(self):
        self._canvas_chip_queue = []
        try:
            chip = getattr(self, '_canvas_status_chip', None)
            if chip is not None and chip.isVisible():
                chip.setToolTip('点击/Esc 关闭 · 多条折叠提示排队显示 · 单条最长 6s')
        except Exception:
            pass
        try:
            self.log('已清空画布提示排队')
        except Exception:
            pass

    def _populate_undo_history_menu(self):
        """Dropdown of last N labelled history tips under 撤销."""
        menu = getattr(self, '_undo_history_menu', None)
        if menu is None:
            return
        menu.clear()
        labels = list(getattr(self.document, 'history_labels', None) or [])
        idx = int(getattr(self.document, 'index', 0) or 0)
        n_max = int(getattr(self, '_undo_history_menu_n', 12) or 12)
        entries = []
        for k in range(idx, 0, -1):
            lab = ''
            if k < len(labels):
                lab = (labels[k] or '').strip()
            if not lab:
                lab = f'步骤 #{k}'
            entries.append((k, lab))
            if len(entries) >= n_max:
                break
        if not entries:
            a = menu.addAction('（无可撤销历史）')
            a.setEnabled(False)
            return
        for k, lab in entries:
            act = menu.addAction(f'撤销「{lab}」')
            act.setToolTip(f'回到该步之前（历史 #{k - 1}）')
            act.triggered.connect(
                lambda _=False, target=k - 1, tip=lab: self._undo_to_history_index(target, tip))

    def _undo_to_history_index(self, target_index, tip_label=''):
        """Jump undo stack to target tip (labelled history menu)."""
        before = int(getattr(self.document, 'index', 0) or 0)
        try:
            ti = int(target_index)
        except (TypeError, ValueError):
            return
        if ti < 0 or ti >= before:
            return
        if hasattr(self.document, 'jump_history'):
            self.document.jump_history(ti)
        else:
            while int(getattr(self.document, 'index', 0) or 0) > ti:
                self.document.undo()
        after = int(getattr(self.document, 'index', 0) or 0)
        if before == after:
            return
        msg = f'已撤销：{tip_label}' if tip_label else f'已撤销到历史 #{after}'
        try:
            self.log(msg)
        except Exception:
            pass
        try:
            self._show_canvas_status_chip(msg)
        except Exception:
            pass
        try:
            self._maybe_log_fold_cross(before, after, 'undo')
        except Exception:
            pass
        try:
            self._refresh_undo_redo_labels()
        except Exception:
            pass

    def _clear_jump_confirm_skip(self, nest_key=None, *, force=False):
        """Clear session jump-confirm skip on leave nest / project reload.

        nest_key=None → clear all. Else drop keys equal to or containing that id.
        When jump-skip persist is on, leave/reload clears are no-ops unless force=True.
        """
        try:
            persist_on = bool(self._jump_skip_persist_enabled())
        except Exception:
            persist_on = False
        if persist_on and not force:
            return
        skip = getattr(self, '_jump_confirm_skip', None)
        if not skip:
            return
        if nest_key is None:
            skip.clear()
            if force:
                try:
                    self._settings().setValue('jumpConfirmSkipKeys', [])
                except Exception:
                    pass
            return
        key = str(nest_key)
        drop = [
            k for k in list(skip)
            if k == key or key in str(k).split('/') or str(k).startswith(key + '/')
            or str(k).endswith('/' + key)
        ]
        for k in drop:
            skip.discard(k)
        if force:
            self._save_jump_skip_keys()

    def _confirm_jump_exit(self, reason, levels, nest_key, cancel_why=''):
        """Ask before breadcrumb jump; session/persist-remember via checkbox → _jump_confirm_skip.

        Returns True to proceed with jump. Stub-friendly for smokes.
        """
        skip = getattr(self, '_jump_confirm_skip', None)
        if skip is None:
            self._jump_confirm_skip = set()
            skip = self._jump_confirm_skip
        if nest_key in skip:
            try:
                try:
                    persist = bool(self._jump_skip_persist_enabled())
                except Exception:
                    persist = False
                kind = '跨会话' if persist else '本会话'
                self.log(f'跳层确认已跳过（{kind}记住）：{nest_key}')
            except Exception:
                pass
            return True
        from PySide6.QtWidgets import QCheckBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle('跳层退出确认')
        box.setText(
            f'当前嵌套：{reason}。\n'
            f'跳层退出 {levels} 层会折叠撤销/重做链到上层，未保存编辑将随退出合并。\n\n仍要跳层？'
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        try:
            persist = bool(self._jump_skip_persist_enabled())
        except Exception:
            persist = False
        cb = QCheckBox('跨会话不再询问此嵌套' if persist else '本会话不再询问此嵌套')
        box.setCheckBox(cb)
        ans = box.exec()
        if cb.isChecked() and ans == QMessageBox.StandardButton.Yes:
            skip.add(nest_key)
            try:
                self._save_jump_skip_keys()
            except Exception:
                pass
            try:
                kind = '跨会话' if persist else '本会话'
                self.log(f'{kind}跳过嵌套跳层确认：{nest_key}')
            except Exception:
                pass
        if ans != QMessageBox.StandardButton.Yes:
            try:
                self.log(f'已取消面包屑跳层（{cancel_why or "用户取消"}）')
            except Exception:
                pass
            return False
        return True

    def jump_exit_group_to(self, target_depth: int = 0):
        """Breadcrumb jump: exit until stack depth == target (0=主流程). Each exit folds hist."""
        try:
            target = max(0, int(target_depth))
        except Exception:
            target = 0
        depth = len(self._group_stack or [])
        if depth <= target:
            return
        # Confirm when mid-redo OR nest tip dirty vs enter/outer_saved (unsaved nest edits)
        try:
            hist = list(getattr(self.document, 'history', None) or [])
            idx = int(getattr(self.document, 'index', 0) or 0)
            mid_redo = bool(hist) and idx + 1 < len(hist)
            # enter_group: document.saved = nest enter tip; frame.outer_saved = outer saved.
            # modified() ⇒ unsaved nest edits relative to that enter/outer_saved contract.
            try:
                nest_dirty = bool(self.document.modified())
            except Exception:
                nest_dirty = self.document.project != getattr(self.document, 'saved', None)
            levels = depth - target
            # Session skip key: stack node_ids from target..tip (this nest path)
            nest_key = '/'.join(
                str(fr.get('node_id') or fr.get('name') or i)
                for i, fr in enumerate(self._group_stack[target:])
            ) or f'depth:{depth}->{target}'
            skip = getattr(self, '_jump_confirm_skip', None)
            if skip is None:
                self._jump_confirm_skip = set()
                skip = self._jump_confirm_skip
            if (mid_redo or nest_dirty) and levels >= 1:
                bits = []
                if mid_redo:
                    redo_n = len(hist) - 1 - idx
                    bits.append(f'尚有 {redo_n} 步可重做')
                if nest_dirty:
                    bits.append('嵌套内有未保存编辑（相对进组快照 / outer_saved）')
                reason = '；'.join(bits) if bits else '嵌套状态未落定'
                why = (
                    '保留嵌套中段重做' if mid_redo and not nest_dirty else
                    '保留未保存嵌套编辑' if nest_dirty and not mid_redo else
                    '保留嵌套重做与未保存编辑'
                )
                if not self._confirm_jump_exit(reason, levels, nest_key, why):
                    return
        except Exception:
            pass
        n = 0
        while len(self._group_stack or []) > target:
            before = len(self._group_stack)
            self.exit_group_module()
            n += 1
            if len(self._group_stack) >= before:
                break  # safety
            if n > 64:
                break
        if n:
            where = '主流程' if not self._group_stack else (self._group_stack[-1].get('name') or '组合')
            self.log(f'面包屑跳层：退出 {n} 层 → {where}（撤销/重做链已折叠保留）')

    def _undo_with_fold_tip(self):
        before = int(getattr(self.document, 'index', 0) or 0)
        # Label of the tip being undone lives at `before`
        label = ''
        try:
            labels = getattr(self.document, 'history_labels', None) or []
            if 0 <= before < len(labels):
                label = labels[before] or ''
        except Exception:
            label = ''
        self.document.undo()
        after = int(getattr(self.document, 'index', 0) or 0)
        if before != after and label:
            try:
                self.log(f'已撤销：{label}')
            except Exception:
                pass
            try:
                self._show_canvas_status_chip(f'已撤销：{label}')
            except Exception:
                pass
        self._maybe_log_fold_cross(before, after, 'undo')

    def _redo_with_fold_tip(self):
        before = int(getattr(self.document, 'index', 0) or 0)
        self.document.redo()
        after = int(getattr(self.document, 'index', 0) or 0)
        if before != after:
            label = ''
            try:
                labels = getattr(self.document, 'history_labels', None) or []
                if 0 <= after < len(labels):
                    label = labels[after] or ''
            except Exception:
                label = ''
            if label:
                try:
                    self.log(f'已重做：{label}')
                except Exception:
                    pass
                try:
                    self._show_canvas_status_chip(f'已重做：{label}')
                except Exception:
                    pass
        self._maybe_log_fold_cross(before, after, 'redo')

    def _maybe_log_fold_cross(self, before, after, direction):
        """Status/log when undo/redo crosses a nest exit-fold boundary."""
        if before == after:
            return
        marks = getattr(self, '_nest_fold_marks', None) or []
        if not marks:
            return
        lo, hi = (after, before) if after < before else (before, after)
        crossed = [m for m in marks if lo <= int(m.get('index', -1)) < hi]
        # Also: crossing FROM tip side INTO pre-enter means after <= mark.index < before (undo)
        if not crossed:
            # Boundary sits at pre-enter index; undo from mark.index+1 → mark.index crosses it
            for m in marks:
                bi = int(m.get('index', -1))
                if direction == 'undo' and before > bi >= after:
                    crossed.append(m)
                elif direction == 'redo' and before <= bi < after:
                    crossed.append(m)
        if not crossed:
            return
        # Dedup by index
        seen = set()
        uniq = []
        for m in crossed:
            k = int(m.get('index', -1))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(m)
        for m in uniq:
            name = m.get('name') or '组合模块'
            if direction == 'undo':
                msg = f'撤销越过嵌套退出折叠点 · 「{name}」进组前快照（重做可回到组内编辑）'
            else:
                msg = f'重做越过嵌套退出折叠点 · 「{name}」组内编辑（撤销可回进组前）'
            try:
                self.log(msg)
            except Exception:
                pass
            try:
                if hasattr(self, 'wb_status') and hasattr(self.wb_status, 'set_config'):
                    self.wb_status.set_config(msg, ok=True)
            except Exception:
                pass
            try:
                self._show_canvas_status_chip(msg)
            except Exception:
                pass

    def _place_canvas_status_chip(self):
        """Reposition canvas status chip (host resize / breadcrumb show-hide)."""
        chip = getattr(self, '_canvas_status_chip', None)
        host = getattr(self, '_canvas_host', None)
        if chip is None or host is None:
            return
        if not chip.isVisible():
            return
        chip.adjustSize()
        hw = max(120, host.width() - 24)
        chip.setFixedWidth(min(hw, max(280, chip.sizeHint().width() + 8)))
        chip.adjustSize()
        x = max(8, (host.width() - chip.width()) // 2)
        y = 8
        try:
            bc = getattr(self, '_group_breadcrumb', None)
            if bc is not None and bc.isVisible():
                y = bc.geometry().bottom() + 6
        except Exception:
            y = 8
        chip.move(x, y)
        chip.raise_()

    def _dismiss_canvas_status_chip(self):
        """Click/API dismiss current chip; advance queue if more fold tips pending."""
        timer = getattr(self, '_canvas_chip_timer', None)
        if timer is not None:
            timer.stop()
        self._advance_canvas_status_chip()

    def _advance_canvas_status_chip(self):
        """Timer/click: show next queued tip or hide."""
        chip = getattr(self, '_canvas_status_chip', None)
        queue = getattr(self, '_canvas_chip_queue', None)
        if queue is None:
            self._canvas_chip_queue = []
            queue = self._canvas_chip_queue
        if queue:
            msg, ms = queue.pop(0)
            self._show_canvas_status_chip(msg, ms=ms, _from_queue=True)
            return
        if chip is not None:
            chip.setVisible(False)
            chip.setText('')

    def _show_canvas_status_chip(self, message, ms=3200, *, _from_queue=False):
        """Transient chip over canvas; queues when already showing (multi fold tips)."""
        chip = getattr(self, '_canvas_status_chip', None)
        host = getattr(self, '_canvas_host', None)
        if chip is None or host is None:
            return
        text = str(message or '').strip()
        if not text:
            if not _from_queue:
                self._dismiss_canvas_status_chip()
            return
        # Queue when a chip is already visible (don't clobber mid-tip)
        if (not _from_queue) and chip.isVisible() and (chip.text() or '').strip():
            q = getattr(self, '_canvas_chip_queue', None)
            if q is None:
                self._canvas_chip_queue = []
                q = self._canvas_chip_queue
            max_ms = int(getattr(self, '_canvas_chip_max_ms', 6000) or 6000)
            dur = int(ms) if ms else 3200
            if dur < 400:
                dur = 400
            if dur > max_ms:
                dur = max_ms
            q.append((text, dur))
            # Cap queue; keep newest
            if len(q) > 8:
                del q[:-8]
            # Hint remaining count on current chip tooltip
            try:
                chip.setToolTip(f'点击/Esc 关闭 · 另有 {len(q)} 条排队')
            except Exception:
                pass
            return
        chip.setText(text)
        qn = len(getattr(self, '_canvas_chip_queue', None) or [])
        try:
            tip = '点击/Esc 关闭 · 多条折叠提示排队显示 · 单条最长 6s'
            if qn:
                tip = f'点击/Esc 关闭 · 另有 {qn} 条排队'
            chip.setToolTip(tip)
        except Exception:
            pass
        chip.setVisible(True)
        self._place_canvas_status_chip()
        timer = getattr(self, '_canvas_chip_timer', None)
        if timer is not None:
            timer.stop()
            max_ms = int(getattr(self, '_canvas_chip_max_ms', 6000) or 6000)
            dur = int(ms) if ms else 3200
            if dur < 400:
                dur = 400
            if dur > max_ms:
                dur = max_ms
            timer.start(dur)

    def reload_comm_listener(self):
        """Start/refresh live Comm recvEvents listeners (TCP Server/UDP/Serial)."""
        try:
            from desktop.comm_listener import CommRecvListener
            if self._comm_listener is None:
                self._comm_listener = CommRecvListener(host=self, parent=self)
                self._comm_listener.status.connect(self._on_comm_listener_status)
                self._comm_listener.listeningChanged.connect(self._on_comm_listening_changed)
                self._comm_listener.heartbeatTick.connect(self._on_comm_heartbeat_tick)
            else:
                self._comm_listener.set_host(self)
            started = self._comm_listener.reload(self.document.project)
            if started:
                self.log('通信监听已启动：' + '、'.join(started))
            elif hasattr(self, 'comm_listen_badge') and getattr(self, '_last_listen_badge', None):
                # Keep prior badge text until listeningChanged fires (project switch)
                if self.comm_listen_badge.text() in ('监听·—', '监听·关', ''):
                    self.comm_listen_badge.setText(self._last_listen_badge)
        except Exception as err:
            self.log(f'通信监听启动失败：{err}')
            if hasattr(self, 'comm_listen_badge'):
                self.comm_listen_badge.setText('监听·失败')
                self.comm_listen_badge.setStyleSheet('color:#e07070;padding:0 8px;font-size:11px;')

    def _on_comm_listener_status(self, message):
        msg = str(message or '')
        if msg.startswith('心跳'):
            return  # badge handles live tick; avoid log flood
        self.log(msg)

    def _on_comm_listening_changed(self, active, summary):
        if not hasattr(self, 'comm_listen_badge'):
            return
        text = str(summary or ('监听·开' if active else '监听·关'))
        self._last_listen_badge = text
        self.comm_listen_badge.setText(text)
        color = '#5ecf8a' if active else '#888'
        self.comm_listen_badge.setStyleSheet(f'color:{color};padding:0 8px;font-size:11px;font-weight:600;')
        self.comm_listen_badge.setToolTip(text + ' — 点击打开通信管理')

    def _on_comm_heartbeat_tick(self, payload):
        if not hasattr(self, 'comm_listen_badge'):
            return
        base = (self._last_listen_badge or self.comm_listen_badge.text()).split(' · tick')[0]
        if not base.startswith('监听'):
            base = '监听·开'
        text = f'{base} · tick'
        self.comm_listen_badge.setText(text)
        self.comm_listen_badge.setToolTip(f'最近心跳：{payload} — 点击打开通信管理')
        # Live-patch open Variables dialog for flow.heartbeatTick
        try:
            dlg = (self.dialogs or {}).get('variables')
            if dlg is not None and dlg.isVisible():
                dlg.live_patch_flow_var('heartbeatTick', payload)
                dlg.live_patch_flow_var('heartbeatAt', str(
                    getattr(self._comm_listener, '_last_hb_ms', '') or ''))
        except Exception:
            pass

    def inject_run_trigger(self):
        """Toolbar one-shot: inject string RUN without opening 全局触发 dialog."""
        try:
            # Prefer live recv pipeline so recvEvents variable writebacks also run
            if self._comm_listener is not None:
                self._comm_listener.push_local('LocalLoop', 'RUN')
                return
            ok = bool(self.fire_string_trigger('RUN', reason='工具栏注入RUN'))
            if not ok:
                self.log('注入RUN：无匹配的字符串触发（请在全局触发中配置 RUN → 执行·单次）')
        except Exception as err:
            self.log(f'注入RUN失败：{err}')

    def inject_stop_trigger(self):
        """Toolbar / HMI: inject string STOP → 全局触发（通常绑定 执行·停止）."""
        try:
            if self._comm_listener is not None:
                self._comm_listener.push_local('LocalLoop', 'STOP')
                return
            ok = bool(self.fire_string_trigger('STOP', reason='工具栏注入STOP'))
            if not ok:
                self.log('注入STOP：无匹配的字符串触发（请在全局触发中配置 STOP → 执行·停止）')
        except Exception as err:
            self.log(f'注入STOP失败：{err}')

    # ---- Wave2 通信管理 / B4 全局触发壳 ----
    def open_comm_manager(self):
        """Wave2: 通信管理窗（VM p=10）."""
        from desktop.comm_manager import CommManagerDialog
        dlg = CommManagerDialog(self.document, self)
        if dlg.exec():
            self.log('通信管理已更新')
            self.reload_comm_listener()

    def open_global_triggers(self):
        from desktop.global_triggers import GlobalTriggersDialog
        dlg = GlobalTriggersDialog(
            self.document, self,
            execute_commands=lambda cmds: self.guard(lambda: self._run_hmi_commands(cmds)),
        )
        if dlg.exec():
            self.log('全局触发已更新')
            self.scene.rebuild()

    def _dispatch_global_triggers(self, commands, reason=''):
        """Fire global-trigger command list once; re-entrancy guarded."""
        cmds = list(commands or [])
        if not cmds:
            return
        if getattr(self, '_dispatching_triggers', False):
            self.log(f'全局触发嵌套跳过（{reason or "busy"}）')
            return
        self._dispatching_triggers = True
        try:
            label = reason or '触发'
            types = '、'.join((c.get('type') or '?') for c in cmds[:4])
            self.log(f'全局触发 · {label} → {types}' + ('…' if len(cmds) > 4 else ''))
            self._run_hmi_commands(cmds)
        finally:
            self._dispatching_triggers = False

    def _fire_event_triggers(self, event_name):
        from desktop.global_triggers import collect_event_commands
        cmds = collect_event_commands(self.document.project, event_name)
        self._dispatch_global_triggers(cmds, reason=event_name)

    def fire_string_trigger(self, text, reason='外部字符串'):
        """Live string-trigger entry: Comm / HMI / inject "RUN" → _run_hmi_commands."""
        from desktop.global_triggers import collect_string_commands
        payload = '' if text is None else str(text)
        if not payload:
            return False
        cmds = collect_string_commands(self.document.project, payload)
        if not cmds:
            return False
        self.log(f'字符串触发匹配「{payload[:48]}」×{len(cmds)}')
        self._dispatch_global_triggers(cmds, reason=reason or '外部字符串')
        return True

    def _fire_string_triggers_from_results(self, records):
        from desktop.global_triggers import collect_string_commands, payloads_from_run_results
        steps = self.document.project.get('steps') or []
        payloads = payloads_from_run_results(records, steps)
        if not payloads:
            return
        all_cmds = []
        for text in payloads:
            cmds = collect_string_commands(self.document.project, text)
            if cmds:
                self.log(f'字符串触发匹配「{text[:48]}」×{len(cmds)}')
                all_cmds.extend(cmds)
        # de-dupe by type+config keep order
        seen = set()
        uniq = []
        for c in all_cmds:
            key = (c.get('type'), c.get('config'))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)
        self._dispatch_global_triggers(uniq, reason='通信/收数')

    def _run_hmi_commands(self, commands):
        """Execute trigger-command list from operator HMI buttons (B5)."""
        from desktop.global_triggers import ACTION_TO_COMMAND, COMMAND_TYPES
        cmds = list(commands or [])
        if not cmds:
            return
        for i, cmd in enumerate(cmds):
            raw = (cmd or {}).get('type') or ''
            ctype = ACTION_TO_COMMAND.get(raw) or raw
            if ctype not in COMMAND_TYPES and raw in COMMAND_TYPES:
                ctype = raw
            cfg = (cmd or {}).get('config') or ''
            if ctype in ('执行·单次', '执行'):
                # Chain remaining commands after async run_once finishes
                self._pending_trigger_cmds = list(cmds[i + 1:])
                self.run_once()
                return
            if ctype == '执行·连续':
                # Policy: stash non-run cmds to flush after continuous stops
                rest = list(cmds[i + 1:])
                run_types = {'执行·单次', '执行', '执行·连续', '执行·继续'}
                after = []
                for c in rest:
                    raw_t = (c or {}).get('type') or ''
                    ct = ACTION_TO_COMMAND.get(raw_t) or raw_t
                    if ct not in run_types:
                        after.append(c)
                self._pending_after_continuous = after
                self._pending_trigger_cmds = []
                self.run_continuous(); return
            if ctype in ('注入·RUN', '字符串·注入RUN'):
                self.inject_run_trigger(); continue
            if ctype in ('注入·STOP', '字符串·注入STOP'):
                self.inject_stop_trigger(); continue
            if ctype == '执行·停止':
                self._pending_trigger_cmds = []
                self.stop_run(); continue
            if ctype == '执行·暂停':
                self.stop_run()
                if hasattr(self, 'operator_hmi') and getattr(self.operator_hmi, '_host_sm', None):
                    self.operator_hmi._host_sm.set_state('Paused', '触发·暂停')
                continue
            if ctype == '执行·继续':
                self._pending_trigger_cmds = []
                self.run_continuous(); return
            if ctype == '状态·报警':
                if hasattr(self, 'operator_hmi') and getattr(self.operator_hmi, '_host_sm', None):
                    self.operator_hmi._host_sm.set_state('Alarm', cfg or '触发')
                self.log('状态·报警'); continue
            if ctype == '状态·清除报警':
                if hasattr(self, 'operator_hmi') and getattr(self.operator_hmi, '_host_sm', None):
                    self.operator_hmi._host_sm.set_state('Idle', '清除报警')
                continue
            if ctype == '方案保存':
                self.save_project(); continue
            if ctype == '方案另存':
                self.save_project_as() if hasattr(self, 'save_project_as') else self.save_project(); continue
            if ctype == '复位':
                self.results.set_results([])
                if hasattr(self, 'operator_hmi'):
                    self.operator_hmi.set_runtime({}, image=self.image, annotated='')
                self.log('复位'); continue
            if ctype == '界面链接':
                target = cfg or '日志'
                if target == '日志':
                    # bottom tabs: 0 results, 1 logs
                    try:
                        # find bottom QTabWidget among central children — best-effort focus logs via status
                        self.log(f'界面链接 → {target}')
                    except Exception:
                        pass
                elif target == '全局相机':
                    self.log('界面链接 → 全局相机（请从设备菜单打开）')
                elif target == '通讯':
                    self.log('界面链接 → 通讯（请从设备菜单打开）')
                elif target == '变量':
                    try:
                        from desktop.variables_dialog import VariablesDialog
                        VariablesDialog(self.document, self).exec()
                    except Exception as err:
                        self.log(f'变量对话框：{err}')
                else:
                    self.log(f'界面链接 → {target}')
                continue
            if ctype == '参数配置':
                self.log('参数配置：请返回设计态编辑模块属性')
                continue
            if ctype == '模块动作':
                # config may hold module id; fall back to selected / full run
                target = cfg.strip() or self.selected
                if target:
                    self.run(target)
                else:
                    self.run_once()
                return
            self.log(f'未接线触发命令：{ctype}' + (f' · {cfg}' if cfg else ''))

    def apply_host_run_ui_template(self):
        """Install p41–43 上位机 layout; optional switch to run mode (one-click shell)."""
        from desktop.run_ui_designer import default_host_run_ui
        from copy import deepcopy
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setWindowTitle('上位机运行壳')
        box.setText('一键套用 VisionMaster 式上位机运行界面（图像 + 状态机）。\n无机械手 SDK。')
        box.setInformativeText('将写入 project.runUi，并可切换到运行模式预览。')
        apply_btn = box.addButton('套用模板', QMessageBox.ButtonRole.AcceptRole)
        apply_run = box.addButton('套用并切运行态', QMessageBox.ButtonRole.ActionRole)
        cancel = box.addButton('取消', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel or clicked is None:
            return
        p = deepcopy(self.document.project)
        p['runUi'] = default_host_run_ui()
        self.document.commit(p)
        if hasattr(self, 'operator_hmi'):
            self.operator_hmi.reload_layout(self.document.project)
        self.log('已应用上位机状态机运行界面模板（图像+状态机）')
        if clicked is apply_run:
            if getattr(self, 'app_mode', 'design') != 'run':
                self.guard(lambda: self.toggle_app_mode())
            self.log('已切换运行态 · 上位机壳可见')

    def apply_production_demo_chain(self):
        """Tools menu: insert production_task node then apply DEFAULT_CHAIN (p40)."""
        from copy import deepcopy
        from desktop.production_task_panel import DEFAULT_CHAIN, chain_to_operations, normalize_production_task_params
        from PySide6.QtWidgets import QMessageBox
        if self.busy:
            raise ValueError('运行中不可改流程')
        ops = chain_to_operations(DEFAULT_CHAIN)
        if not ops:
            self.log('建议链为空'); return
        ans = QMessageBox.question(
            self, '生产任务建议链',
            f'将插入「生产任务」模块，并按建议链添加 {len(ops)} 个算子节点。\n'
            '无机械手 SDK；发送上位机仅走既有通讯算子。\n继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        # Ensure production_task node exists / add one
        if 'production_task' in self.definitions:
            nid = self.document.add(self.definitions['production_task'], parent=self.selected or 'source')
            proj = deepcopy(self.document.project)
            for s in proj['steps']:
                if s['id'] == nid:
                    s['name'] = '生产任务1'
                    s['params'] = normalize_production_task_params({
                        'taskName': 'DemoTask',
                        'recipe': 'default',
                        'chain': deepcopy(DEFAULT_CHAIN),
                    })
                    break
            self.document.commit(proj)
            self.selected = nid
        self.apply_production_chain(ops)

    def open_run_ui_designer(self):
        if self.dialogs.get('run_ui'):
            self.dialogs['run_ui'].show();self.dialogs['run_ui'].raise_();return
        from desktop.run_ui_designer import RunUiDesignerDialog
        dlg=RunUiDesignerDialog(self.document,self,templates_root=self.root)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        def _on_designer_gone(*_):
            self.dialogs.pop('run_ui', None)
            if self.app_mode == 'run' and hasattr(self, 'operator_hmi'):
                self.operator_hmi.reload_layout(self.document.project)
        dlg.destroyed.connect(_on_designer_gone)
        self.dialogs['run_ui']=dlg
        dlg.show()

    # ----- P2 C4/C5 helpers -----
    def _settings(self):
        return QSettings('SIEANS', 'VisionDesktop')

    def _recent_paths(self):
        raw = self._settings().value('recentSchemes', [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        paths = []
        for item in list(raw or []):
            s = str(item).strip()
            if s and s not in paths:
                paths.append(s)
        return paths[:12]

    def _remember_recent(self, path):
        try:
            path = str(Path(path).resolve())
        except Exception:
            path = str(path)
        if not path:
            return
        items = [path] + [p for p in self._recent_paths() if p != path]
        self._settings().setValue('recentSchemes', items[:12])
        if hasattr(self, 'recent_menu'):
            self._rebuild_recent_menu()

    def _rebuild_recent_menu(self):
        menu = getattr(self, 'recent_menu', None)
        if menu is None:
            return
        menu.clear()
        paths = self._recent_paths()
        if not paths:
            empty = menu.addAction('（无最近方案）')
            empty.setEnabled(False)
        else:
            for path in paths:
                label = Path(path).name
                act = menu.addAction(label)
                act.setToolTip(path)
                act.triggered.connect(lambda _=False, p=path: self.guard(lambda: self._open_recent(p)))
            menu.addSeparator()
            menu.addAction(self.action('清除最近打开列表', self._clear_recent))

    def _open_recent(self, path):
        if self.busy or not self.engine_ready or not self.confirm_discard():
            return
        path = Path(path)
        if not path.is_file():
            # drop missing entry
            items = [p for p in self._recent_paths() if p != str(path)]
            self._settings().setValue('recentSchemes', items)
            self._rebuild_recent_menu()
            raise ValueError('最近方案不存在：' + str(path))
        self.open_project_file(path)

    def _clear_recent(self):
        self._settings().setValue('recentSchemes', [])
        self._rebuild_recent_menu()
        self.log('已清除最近打开列表')

    def open_example_scheme(self):
        """文件→打开示例：快捷打开演示/模板工程（VM「打开示例」对齐）。"""
        if self.busy or not self.engine_ready or not self.confirm_discard():
            return
        examples = []
        for rel in (
            'projects/default-platform.sieans',
            'projects/open-and-run-demo.sieans',
            'projects/open-and-run-locate.sieans',
            'projects/open-and-run-ninepoint.sieans',
            'projects/open-and-run-script.sieans',
            'projects/open-and-run-barcode.sieans',
            'projects/open-and-run-defects.sieans',
            'projects/templates/blank-inspection.sieans',
            'projects/templates/measure-chain.sieans',
            'projects/templates/defect-inspection.sieans',
            'projects/templates/mv-gentl-ocr.sieans',
            'projects/mv-camera-ocr.sieans',
        ):
            path = (self.root / rel).resolve()
            if path.is_file():
                examples.append((path.name + '  ·  ' + rel, path))
        if not examples:
            raise ValueError('未找到示例方案')
        names = [e[0] for e in examples]
        choice, ok = QInputDialog.getItem(self, '打开示例', '选择示例方案', names, 0, False)
        if not ok:
            return
        path = next(p for n, p in examples if n == choice)
        # templates stay pristine via open_template for template paths
        if 'templates/' in str(path).replace('\\', '/'):
            rel = str(path.relative_to(self.root)).replace('\\', '/')
            self.open_template(rel)
        else:
            self.open_project_file(path)

    def _ask_run_interval(self, current=0):
        """C4: 「设置运行间隔」对话框，单位 ms，上限 100000。"""
        dlg = QDialog(self)
        dlg.setWindowTitle('设置运行间隔')
        dlg.setMinimumWidth(360)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        spin = QSpinBox()
        spin.setRange(0, 100000)
        spin.setSingleStep(10)
        spin.setValue(max(0, min(100000, int(current or 0))))
        spin.setSuffix(' ms')
        form.addRow('运行间隔时间(ms)', spin)
        hint = QLabel('连续执行时，两次运行之间的等待时间。上限 100000 ms。')
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        lay.addLayout(form)
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return flow_scheme.clamp_run_interval_ms(spin.value())

    def _active_run_interval_ms(self):
        """连续运行延迟：读活动流程 runIntervalMs，缺省 120，钳制 ≤100000。"""
        try:
            p = self.document.project
            flow_scheme.ensure_scheme(p)
            fid = p.get('activeFlowId')
            flow = next((f for f in (p.get('flows') or []) if f.get('id') == fid), None)
            raw = (flow or {}).get('runIntervalMs')
            if raw is None or int(raw) <= 0:
                return 120
            return flow_scheme.clamp_run_interval_ms(raw)
        except Exception:
            return 120

    def _filmstrip_advance_delay_ms(self):
        """胶片条切图间隔：优先 sourceConfig.intervalMs，否则流程连续间隔，最低 50。"""
        try:
            cfg = normalize_source(self.document.project.get('sourceConfig'))
            ms = int(cfg.get('intervalMs') or 0)
            if ms > 0:
                return max(50, min(ms, 100000))
        except Exception:
            pass
        return max(50, self._active_run_interval_ms())


    def _on_hmi_run_ui_changed(self, patch):
        """Persist OperatorHmiView patches (e.g. 判定门 → runUi.fixedBars.gateKey)."""
        if self.busy or not isinstance(patch, dict):
            return
        p = deepcopy(self.document.project)
        runUi = dict(p.get('runUi') or {})
        if 'fixedBars' in patch and isinstance(patch.get('fixedBars'), dict):
            runUi['fixedBars'] = dict(patch['fixedBars'])
            p['runUi'] = runUi
            self.document.commit(p)
            # Keep live HMI tip in sync without full rebuild
            try:
                if hasattr(self, 'operator_hmi'):
                    self.operator_hmi._apply_fixed_bars(runUi['fixedBars'])
            except Exception:
                pass

    def _sync_filmstrip_visibility(self):
        """Local+design: show filmstrip. Camera/SDK: hide bar but still wire interval/auto-switch;
        soft-disable 运行全部 so a later mode flip does not leave a stale enabled button."""
        if not hasattr(self, 'filmstrip'):
            return
        try:
            from desktop.image_source import normalize_source
            cfg = normalize_source(self.document.project.get('sourceConfig'))
            mode = cfg.get('mode') or 'local'
            local = mode == 'local'
            show = local and getattr(self, 'app_mode', 'design') == 'design'
            self.filmstrip.setVisible(show)
            # Always keep interval hint + auto-switch / stop-at-last synced from sourceConfig
            # (even while hidden) so camera→local flip restores correct controls.
            try:
                self.filmstrip.set_interval_hint(cfg.get('intervalMs') or 0)
            except Exception:
                pass
            try:
                self.filmstrip.auto_switch.blockSignals(True)
                self.filmstrip.set_auto_switch(bool(cfg.get('autoSwitch')))
                self.filmstrip.auto_switch.blockSignals(False)
            except Exception:
                pass
            try:
                if hasattr(self.filmstrip, 'stop_at_last'):
                    self.filmstrip.stop_at_last.blockSignals(True)
                    self.filmstrip.set_stop_at_last(bool(cfg.get('stopAtLast')))
                    self.filmstrip.stop_at_last.blockSignals(False)
            except Exception:
                pass
            # Soft-disable run-all outside local mode (camera/SDK take-frame path).
            try:
                if hasattr(self.filmstrip, 'set_run_all_enabled'):
                    self.filmstrip.set_run_all_enabled(
                        local,
                        '' if local else '图像源为相机/SDK — 运行全部已软禁用（仅本地图集可用）',
                    )
                elif hasattr(self.filmstrip, 'run_all'):
                    self.filmstrip.run_all.setEnabled(local)
            except Exception:
                pass
            if mode in ('camera', 'sdk'):
                self.filmstrip.setToolTip(
                    '图像源为相机/SDK — 胶片条已隐藏；间隔/自动切换仍随 sourceConfig 同步；'
                    '切回本地可导入图集并启用「运行全部」'
                )
            else:
                self.filmstrip.setToolTip('')
        except Exception:
            pass

    def _sync_filmstrip_interval_hint(self):
        if not hasattr(self, 'filmstrip'):
            return
        try:
            from desktop.image_source import normalize_source
            cfg = normalize_source(self.document.project.get('sourceConfig'))
            self.filmstrip.set_interval_hint(cfg.get('intervalMs') or 0)
            # Keep soft-disable in sync when only interval is refreshed.
            mode = cfg.get('mode') or 'local'
            local = mode == 'local'
            if hasattr(self.filmstrip, 'set_run_all_enabled'):
                self.filmstrip.set_run_all_enabled(
                    local,
                    '' if local else '图像源为相机/SDK — 运行全部已软禁用（仅本地图集可用）',
                )
        except Exception:
            pass

    def about(self):
        QMessageBox.information(self,'SIEANS Vision 视觉检测平台',
            '完整工业视觉检测工作台（流程编辑 · 算子库 · 设备与模型 · 运行画面 · 记录）。\n\n'
            '· 左侧：分类算子库（采集 / 图像 / 定位测量 / 识别 / 3D / 通信 / 流程）\n'
            '· 中间：流程图连线；右侧：选中算子属性（Halcon/VM 风格分区）\n'
            '· 设备与模型 → 相机与连续采集 / 连续检测 / 模型训练\n'
            '· 工程管理 → 本机工程库 / 变量 / 子流程 / 运行画面\n'
            '· 文件 → 从模板新建检测工程；工具栏 → 演示工程\n\n'
            '硬件与算法依赖沿用本机配置；界面可用不代表所有现场设备已验收。')

    def open_panel(self,key):
        if self.busy and key not in ('hmi','continuous'):return
        if key in self.dialogs:
            if key=='continuous':self.dialogs[key].set_input(self.image,self.cloud,self.depth)
            self.dialogs[key].show();self.dialogs[key].raise_();return
        if key in ('camera','training'):
            from desktop.device_dialogs import CameraDialog,TrainingDialog
            dialog=(CameraDialog if key=='camera' else TrainingDialog)(self.backend,self)
            if key=='camera':
                dialog.frame_ready.connect(self.accept_frame);dialog.camera_selected.connect(self.camera_selected)
                step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
                if step and step['operation']=='camera_capture':dialog.set_params(step['params'])
            else:dialog.model_selected.connect(self.model_selected)
        elif key=='continuous':
            from desktop.device_dialogs import ContinuousDialog
            dialog=ContinuousDialog(self.document,self.backend,self);dialog.set_input(self.image,self.cloud,self.depth)
            dialog.busy_changed.connect(self.set_busy)
            dialog.result_ready.connect(lambda result:self.finished(result,release=False))
        elif key=='variables':
            from desktop.variables_dialog import VariablesDialog
            dialog=VariablesDialog(self.document,self.backend,self)
        elif key=='hmi':
            from desktop.hmi_editor import HmiDialog
            dialog=HmiDialog(self.document,self.backend,self)
            dialog.run_requested.connect(lambda:self.guard(self.run));dialog.stop_requested.connect(lambda:self.request('stop',{},lambda _:None))
            dialog.set_source_image(self.image)
            if self.last_result:dialog.set_runtime(self.last_result,self.image)
        elif key=='subflows':
            from desktop.subflows import SubflowsDialog
            dialog=SubflowsDialog(self.document,self.definitions,self)
            dialog.setWindowModality(Qt.WindowModality.WindowModal)
        else:
            from desktop.management_dialogs import LoginDialog,ProjectsDialog,HistoryDialog,PluginsDialog,AccountsDialog
            if key=='login':
                dialog=LoginDialog(self.backend,self);dialog.authenticated.connect(lambda:self.request('auth/status',{},self.authorized))
            elif key=='projects':
                dialog=ProjectsDialog(self.document,self.backend,self);dialog.project_loaded.connect(lambda p:self.guard(lambda:self.use_project(p)))
            elif key in ('history','audit'):dialog=HistoryDialog(self.backend,key=='audit',self)
            elif key=='plugins':
                dialog=PluginsDialog(self.backend,self);dialog.updated.connect(lambda:self.request('plugins/list',{},self.plugins_loaded))
            else:dialog=AccountsDialog(self.backend,self)
        self.dialogs[key]=dialog
        if key!='continuous':dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if hasattr(dialog,'set_busy'):dialog.set_busy(self.busy)
        dialog.destroyed.connect(lambda *_,k=key:self.dialogs.pop(k,None));dialog.show()

    def use_project(self,project):
        if self.busy or not self.confirm_discard():return
        self.document.load(project);self.filename=None;self.image='';self.last_result=None
        self.input_view.show_data('');self.output_view.show_data('');self.clear_cloud();self.results.set_results([]);self.flow.fit()

    def accept_frame(self,frame):
        if self.busy:return
        self.image=frame.get('image') or frame.get('annotatedImage') or '';self.cloud=frame.get('cloud');self.depth=frame.get('depth')
        self.last_result=None
        # Prefer 全局图像 so KeepAspectRatio fit runs on a visible viewport (not a hidden tab).
        self.images.setCurrentIndex(0)
        self.input_view.show_data(self.image);self.output_view.show_data('');self.cloud_view.set_cloud(self.cloud);self.results.set_results([])
        self.show_depth(self.depth)
        if self.cloud and not self.image:
            self.images.setCurrentIndex(2)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.input_view.fit)
        if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)
        self.log('已接收相机数据，可运行检测流程')

    def _on_images_tab(self, index):
        # Refit when user switches back to an image tab after frames arrived hidden.
        try:
            from PySide6.QtCore import QTimer
            from desktop.image_view import ImageView
            w = self.images.widget(index)
            targets = []
            if isinstance(w, ImageView):
                targets = [w]
            elif w is not None:
                targets = list(w.findChildren(ImageView))
            for iv in targets:
                if not iv.bounds.isEmpty():
                    QTimer.singleShot(0, iv.fit)
        except Exception:
            pass

    def camera_selected(self,params,apply_selected):
        if self.busy:return
        step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
        if not apply_selected or not step or step['operation']!='camera_capture':self.add_node('camera_capture')
        project=deepcopy(self.document.project);step=next(s for s in project['steps'] if s['id']==self.selected)
        step['params']=deepcopy(params);self.document.commit(project)

    def import_script(self):
        if self.busy:return
        name,_=QFileDialog.getOpenFileName(self,'导入 Python 脚本','','Python 脚本 (*.py)')
        if not name:return
        path=Path(name)
        if path.stat().st_size>64000:raise ValueError('脚本不能超过 64 KB')
        code=path.read_text(encoding='utf-8-sig')
        import ast
        tree=ast.parse(code)
        if not any(isinstance(n,ast.FunctionDef) and n.name=='run' for n in tree.body):raise ValueError('脚本需定义 run(ctx) 函数')
        step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
        if not step or step['operation']!='script':self.add_node('script')
        project=deepcopy(self.document.project);step=next(s for s in project['steps'] if s['id']==self.selected)
        step['params']['code']=code;step['name']=path.stem;self.document.commit(project)
        self.log('脚本已导入；运行时使用本机账号权限，请确认来源后勾选本次可信执行')

    def model_selected(self,operation,model):
        if self.busy:return
        step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
        if not step or step['operation']!=operation:self.add_node(operation)
        project=deepcopy(self.document.project);next(s for s in project['steps'] if s['id']==self.selected)['params']['model']=model;self.document.commit(project)

    def roi_mode(self):
        if self.busy or not self.selected:
            self.roi_action.setChecked(False);self.input_view.set_roi_mode(False);self.log('请先选择检测模块');return
        self.images.setCurrentIndex(0);self.input_view.set_roi_mode(self.roi_action.isChecked())

    def update_roi(self,roi):
        if self.busy or not self.selected:return
        p=deepcopy(self.document.project);step=next(s for s in p['steps'] if s['id']==self.selected)
        params=step.setdefault('params',{})
        if roi is None:params.pop('roi',None)
        else:params['roi']=roi
        self.document.commit(p);self.input_view.show_roi(roi)

    def clear_cloud(self):
        if self.busy:return
        self.cloud=None;self.depth=None;self.cloud_view.set_cloud(None);self.show_depth(None)

    def show_depth(self,depth):
        self.depth_view.show_data((depth or {}).get('preview',''))
        if not depth:self.depth_caption.setText('尚无深度数据');return
        scale=float(depth.get('scaleMeters',0))*1000
        self.depth_caption.setText(f"{depth.get('width','—')} × {depth.get('height','—')} · 原始 16 位 · 每单位 {scale:g} mm\n色标 {depth.get('minMeters','—')}–{depth.get('maxMeters','—')} m；黑色为无效或超出范围。")

    def open_cloud(self,reference=False):
        if self.busy:return
        if reference and not self.selected:raise ValueError('请先选择点云配准模块')
        if reference and next(s for s in self.document.project['steps'] if s['id']==self.selected)['operation']!='cloud_register':raise ValueError('请先选择点云配准模块')
        name,_=QFileDialog.getOpenFileName(self,'导入参考点云' if reference else '导入点云','','点云 (*.ply *.pcd *.xyz *.txt *.csv *.json)')
        if not name:return
        from PySide6.QtWidgets import QInputDialog
        unit,ok=QInputDialog.getItem(self,'点云单位','文件中的坐标单位',['mm','m'],0,False)
        if not ok:return
        path=Path(name)
        if path.stat().st_size>12_000_000:raise ValueError('点云文件不能超过 12 MB')
        node_id=self.selected;project_id=self.document.project['id']
        content='data:application/octet-stream;base64,'+base64.b64encode(path.read_bytes()).decode()
        def imported(value):
            if self.document.project['id']!=project_id:return
            cloud=value['cloud']
            if reference:
                p=deepcopy(self.document.project);step=next((s for s in p['steps'] if s['id']==node_id),None)
                if not step:raise ValueError('原模块已移除')
                step.setdefault('params',{})['targetCloud']=cloud;self.document.commit(p)
            else:self.cloud=cloud;self.depth=None;self.show_depth(None)
            self.cloud_view.set_cloud(cloud);self.images.setCurrentIndex(2);self.log('点云已导入：'+str(len(cloud['points']))+' 点')
        self.request('cloud/import',dict(name=path.name,content=content,unit=unit),imported)

    def closeEvent(self,event):
        try:
            if getattr(self, '_comm_listener', None) is not None:
                self._comm_listener.stop()
        except Exception:
            pass
        if self.engine_stopped:
            if not self.closing and not self.confirm_discard(include_original=True):event.ignore();return
            event.accept();return
        if not self.closing:
            if not self.confirm_discard(include_original=True):event.ignore();return
            self.closing=True;self.setEnabled(False);self.wb_status.push_log('正在停止算法进程…');self.backend.shutdown()
        event.ignore()
