"""Native Qt Widgets application window."""
import base64
import json
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import QSize, Qt, QMimeData, QByteArray, QBuffer, QIODevice, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence, QDrag, QPixmap, QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QTreeWidget,QTreeWidgetItem,
    QLineEdit,QToolBar,QLabel,QPushButton,QFileDialog,QMessageBox,QTabWidget,QPlainTextEdit,QGraphicsView,QGraphicsScene,
    QStackedWidget,QInputDialog,QSpinBox,QDialog,QDialogButtonBox,QFormLayout,QComboBox,QMenu)
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
        self.continuous=False;self.run_all_filmstrip=False;self._run_target=None;self.rail_category='';self.property_float=None;self._group_stack=[];self._group_breadcrumb=None
        self.app_mode='design'  # design | run
        self.showing_all_flows=False
        self._left_pane=None;self._center_stack=None;self.run_mode_pane=None
        self.build_ui();self.document.changed.connect(self.document_changed);self.populate_toolbox()
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
        tools_menu.addAction(self.action('全局触发…',self.open_global_triggers))
        self.undo_action=self.action('撤销',self.document.undo,'Ctrl+Z');self.redo_action=self.action('重做',self.document.redo,'Ctrl+Y')
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
        for label,callback in [('自动排列',self.document.layout),('适应',lambda:self.flow.fit()),('撤销',self.document.undo),('重做',self.document.redo)]:
            b=QPushButton(label);b.clicked.connect(lambda checked=False,cb=callback:self.guard(cb) if not self.busy else None);name_row.addWidget(b)
        fl.addLayout(name_row)
        self.scene=FlowScene(self.document);self.flow=FlowView(self.scene)
        self.scene.chosen.connect(self.choose_node);self.scene.configure.connect(self.configure_node);self.scene.notice.connect(self.log)
        self.flow.dropped.connect(lambda key,pos:self.guard(lambda:self.add_node(key,pos)))
        self._group_breadcrumb=GroupBreadcrumb()
        self._group_breadcrumb.setVisible(False)
        self._group_breadcrumb.exitGroup.connect(self.exit_group_module)
        canvas_host=QWidget();chl=QVBoxLayout(canvas_host);chl.setContentsMargins(0,0,0,0);chl.addWidget(self._group_breadcrumb);chl.addWidget(self.flow,1)
        self.minimap=MiniMap(self.scene,self.flow,canvas_host)
        self._canvas_host=canvas_host
        canvas_host.installEventFilter(self)
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
            self.document.commit(proj)
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
        return self.property_float

    def open_property_float(self,node_id):
        flo=self.ensure_property_float()
        if node_id=='source':
            cfg=normalize_source(self.document.project.get('sourceConfig'))
            flo.show_source(cfg, title='0 图像源')
            # sync filmstrip visibility for local mode
            self.filmstrip.setVisible(cfg.get('mode','local')=='local')
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
        self.filmstrip.set_paths(paths, int(p['sourceConfig'].get('currentIndex') or 0))
        self.filmstrip.set_auto_switch(bool(p['sourceConfig'].get('autoSwitch')))
        self.filmstrip.set_stop_at_last(bool(p['sourceConfig'].get('stopAtLast')))
        self.filmstrip.setVisible(p['sourceConfig'].get('mode','local')=='local')
        self._sync_filmstrip_interval_hint()
        self.guard(lambda:self.document.commit(p))

    def on_param_audited(self,module,param,old,new):
        flow=self.document.project.get('name') or '流程1'
        msg=self.wb_status.log_param_change(flow, module, param, old, new)
        self.logs.appendPlainText(msg)

    def refresh_parameters(self):
        step=next((s for s in self.document.project['steps'] if s['id']==self.selected),None)
        definition=deepcopy(definition_for(step,self.definitions)) if step else None
        if step and step.get('operation') in ('subflow','loop'):
            for field in definition.get('parameters',[]):
                if field['key']=='subflowId':field['choices']=[dict(value=s['id'],label=s['name']) for s in self.document.project.get('subflows',[])]
        self.parameters.set_step(step,definition,self.document.project)
        self.input_view.show_roi(step.get('params',{}).get('roi') if step else None)

    def update_step(self,step):
        if self.busy:return
        p=deepcopy(self.document.project);p['steps']=[step if s['id']==step['id'] else s for s in p['steps']]
        self.guard(lambda:self.document.commit(p))

    
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
        self.refresh_parameters();self.set_busy(self.busy)
        if hasattr(self,'flow_tab_bar'):self.refresh_flow_tabs()
        cfg=normalize_source(p.get('sourceConfig'))
        if hasattr(self,'filmstrip'):
            self.filmstrip.thumbs.blockSignals(True)
            self.filmstrip.auto_switch.blockSignals(True)
            if hasattr(self.filmstrip,'stop_at_last'):
                self.filmstrip.stop_at_last.blockSignals(True)
            self.filmstrip.set_paths(list(cfg.get('images') or []), int(cfg.get('currentIndex') or 0))
            self.filmstrip.set_auto_switch(bool(cfg.get('autoSwitch')))
            self.filmstrip.set_stop_at_last(bool(cfg.get('stopAtLast')))
            self.filmstrip.thumbs.blockSignals(False)
            self.filmstrip.auto_switch.blockSignals(False)
            if hasattr(self.filmstrip,'stop_at_last'):
                self.filmstrip.stop_at_last.blockSignals(False)
            self.filmstrip.setVisible(cfg.get('mode','local')=='local' and self.app_mode=='design')
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
        proj=empty_project();proj['name']='未命名方案';flow_scheme.ensure_scheme(proj)
        self.document.load(proj);self.filename=None;self.image='';self.input_view.show_data('');self.output_view.show_data('');self.results.set_results([])
        self.clear_cloud()
        self.last_result=None;self.showing_all_flows=False
        if hasattr(self,'_center_stack'):self._center_stack.setCurrentIndex(0)
        self.set_app_mode('design')
        self.show_platform_welcome()

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
            project=reply['project']
            # Preserve multi-flow scheme fields stripped by engine normalize
            for key in ('flows','activeFlowId','flowEdges'):
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
        self.demo_action.setEnabled(self.engine_ready and not busy and design);self.return_demo_action.setEnabled(not busy and self.demo_backup is not None)
        if hasattr(self,'filmstrip'):self.filmstrip.setEnabled(not busy and design)
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
        self.continuous=True;self.run_all_filmstrip=False;self._run_target=None;self.log('连续运行已启动');self.run()

    def stop_run(self):
        self.continuous=False;self.run_all_filmstrip=False;self._run_target=None
        self.request('stop',{},lambda _:None)
        self.wb_status.push_log('已请求停止')

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

    def finished(self,result,release=True):
        self.last_result=result
        if release:self.set_busy(False)
        records=result.get('results',[])
        names={s['id']:s.get('name',s['operation']) for s in self.document.project['steps']}
        self.results.set_results([{**r,'name':names.get(r['id'],r['id'])} for r in records]);self.scene.show_results(records)
        for record in reversed(records):
            image=record.get('output',{}).get('annotatedImage')
            if image:self.output_view.show_data(image);self.images.setCurrentIndex(1);break
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
                annotated=''
                for record in reversed(records):
                    annotated=record.get('output',{}).get('annotatedImage') or ''
                    if annotated:break
                self.operator_hmi.set_runtime(result, image=self.image, annotated=annotated)
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
            self.continuous=False;self.run_all_filmstrip=False;self._run_target=None;return
        if self.run_all_filmstrip and state=='completed':
            if self.filmstrip.advance():
                QTimer.singleShot(self._filmstrip_advance_delay_ms(), lambda:self.guard(self.run))
            else:
                self.run_all_filmstrip=False;self.log('运行全部完成')
            return
        if self.continuous and state=='completed':
            cfg=normalize_source(self.document.project.get('sourceConfig'))
            target=self._run_target
            if cfg.get('mode')=='local' and self.filmstrip.auto_switch.isChecked() and not target:
                if self.filmstrip.advance():
                    QTimer.singleShot(self._filmstrip_advance_delay_ms(), lambda:self.guard(lambda:self.run(None)));return
                if cfg.get('stopAtLast'):
                    self.continuous=False;self._run_target=None;self.log('已到最后一张，连续运行停止');return
            delay=self._active_run_interval_ms()
            QTimer.singleShot(delay, lambda t=target: self.guard(lambda:self.run(t)) if self.continuous else None)

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
        return super().eventFilter(obj, event)

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
        if not p.is_file():return
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
        self.continuous=False;self.run_all_filmstrip=True
        # jump to first
        self.filmstrip.thumbs.setCurrentRow(0)
        self.guard(self.run)


    def _ensure_camera_frame_for_run(self, cfg):
        """Pull latest session frame into self.image; raise clear Chinese errors if not connected."""
        if not self.backend.is_ready:
            raise ValueError('原生引擎未就绪，无法从相机 SDK 取图')
        # Synchronous-ish: use a tiny nested event loop for one capture; keep UI responsive.
        from PySide6.QtCore import QEventLoop, QTimer
        status_box = {'value': None, 'error': None}
        loop = QEventLoop(self)
        rid = self.backend.request('camera/session/status', {})
        def on_result(request_id, value):
            if request_id != rid and status_box.get('cap_rid') != request_id:
                return
            if request_id == rid:
                status_box['value'] = value
                st = (value or {}).get('state') if isinstance(value, dict) else None
                if st != 'running':
                    loop.quit()
                    return
                # capture latest
                sid = value.get('id')
                cap = self.backend.request('camera/capture', {
                    'driver': 'session', 'sessionId': sid,
                    'framePolicy': 'latest', 'maxAgeMs': 5000, 'timeoutMs': 5000,
                })
                status_box['cap_rid'] = cap
                return
            if request_id == status_box.get('cap_rid'):
                status_box['frame'] = value
                loop.quit()
        def on_error(request_id, message):
            if request_id in (rid, status_box.get('cap_rid')):
                status_box['error'] = message
                loop.quit()
        self.backend.result.connect(on_result)
        self.backend.error.connect(on_error)
        QTimer.singleShot(12000, loop.quit)
        loop.exec()
        try:
            self.backend.result.disconnect(on_result)
            self.backend.error.disconnect(on_error)
        except Exception:
            pass
        if status_box.get('error'):
            raise ValueError('相机 SDK 取图失败：'+str(status_box['error']))
        st = (status_box.get('value') or {}).get('state')
        if st != 'running':
            cam = cfg.get('cameraId') or (cfg.get('cameraParams') or {}).get('deviceId') or '未选择'
            raise ValueError(
                f'图像源为相机/SDK，但相机会话未连接（状态：{st or "未知"}，设备：{cam}）。'
                '请打开「相机管理」→ 选择相机 → 打开「连接相机」。'
            )
        frame = status_box.get('frame') or {}
        image = frame.get('annotatedImage') or frame.get('image') or ''
        if not image:
            raise ValueError('相机会话已连接但尚无有效帧，请稍候再「运行」或在相机管理中点「取最新缓存帧」。')
        self.image = image
        self.cloud = frame.get('cloud')
        self.depth = frame.get('depth')
        self.input_view.show_data(self.image)
        self.images.setCurrentIndex(0)
        self._mirror_preview_to_operator()

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
    def enter_group_module(self, node_id):
        step = next((s for s in self.document.project.get('steps', []) if s.get('id') == node_id), None)
        if not step or step.get('operation') != 'group':
            self.log('仅组合模块可进入'); return
        from copy import deepcopy
        params = normalize_group_params(step.get('params'))
        step['params'] = params
        if not group_bindings_ready(params):
            self.log('提示：进组前建议绑定 ImageData / InputROI（属性浮窗 · 输入设置）')
        inner = params.get('inner') or default_group_inner()
        params['inner'] = inner
        # 先把当前外层写入 history，再切换视图
        self.document.commit(deepcopy(self.document.project))
        self._group_stack.append({
            'node_id': node_id,
            'name': step.get('name') or '组合模块',
            'outer_project': deepcopy(self.document.project),
        })
        view_project = deepcopy(self.document.project)
        view_project['steps'] = deepcopy(inner.get('steps') or [])
        view_project['edges'] = deepcopy(inner.get('edges') or [])
        view_project['sourcePosition'] = deepcopy(inner.get('sourcePosition') or dict(x=300, y=40))
        view_project['name'] = f'{self.document.project.get("name","方案")} / {step.get("name") or "组合模块"}'
        # 软切换：不走 validate 的完整 load（内层可为空）
        self.document.project = view_project
        self.selected = None
        self.scene.rebuild()
        self.document_changed()
        self._group_breadcrumb.set_path('主流程', step.get('name') or '组合模块')
        self._group_breadcrumb.setVisible(True)
        self.log(f'已进入组合模块「{step.get("name") or node_id}」· ImageData/InputROI 绑定可在属性中配置')

    def exit_group_module(self):
        if not self._group_stack:
            self._group_breadcrumb.setVisible(False); return
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
        self.document.load(outer)
        # load 已 emit changed → document_changed + 需 rebuild
        self.scene.rebuild()
        if self._group_stack:
            top = self._group_stack[-1]
            self._group_breadcrumb.set_path('主流程', top['name'])
            self._group_breadcrumb.setVisible(True)
        else:
            self._group_breadcrumb.setVisible(False)
        self.log(f'已退出组合模块「{frame["name"]}」')

    # ---- Wave2 通信管理 / B4 全局触发壳 ----
    def open_comm_manager(self):
        """Wave2: 通信管理窗（VM p=10）."""
        from desktop.comm_manager import CommManagerDialog
        dlg = CommManagerDialog(self.document, self)
        if dlg.exec():
            self.log('通信管理已更新')

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
        cmds = list(commands or [])
        if not cmds:
            return
        for cmd in cmds:
            ctype = (cmd or {}).get('type') or ''
            cfg = (cmd or {}).get('config') or ''
            if ctype in ('执行·单次', '执行'):
                self.run_once(); return  # run is async; further cmds after finish not chained yet
            if ctype == '执行·连续':
                self.run_continuous(); return
            if ctype == '执行·停止':
                self.stop_run(); continue
            if ctype == '执行·暂停':
                self.stop_run()
                if hasattr(self, 'operator_hmi') and getattr(self.operator_hmi, '_host_sm', None):
                    self.operator_hmi._host_sm.set_state('Paused', '触发·暂停')
                continue
            if ctype == '执行·继续':
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

    def _sync_filmstrip_interval_hint(self):
        if not hasattr(self, 'filmstrip'):
            return
        try:
            cfg = normalize_source(self.document.project.get('sourceConfig'))
            self.filmstrip.set_interval_hint(cfg.get('intervalMs') or 0)
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
        if self.engine_stopped:
            if not self.closing and not self.confirm_discard(include_original=True):event.ignore();return
            event.accept();return
        if not self.closing:
            if not self.confirm_discard(include_original=True):event.ignore();return
            self.closing=True;self.setEnabled(False);self.wb_status.push_log('正在停止算法进程…');self.backend.shutdown()
        event.ignore()
