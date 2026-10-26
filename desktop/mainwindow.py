"""Native Qt Widgets application window."""
import base64
import json
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt, QMimeData, QByteArray, QBuffer, QIODevice, QTimer
from PySide6.QtGui import QAction, QKeySequence, QDrag, QPixmap, QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QTreeWidget,QTreeWidgetItem,
    QLineEdit,QToolBar,QLabel,QPushButton,QFileDialog,QMessageBox,QTabWidget,QPlainTextEdit,QGraphicsView,QGraphicsScene)
from desktop.model import Document,empty_project
from desktop.graph import FlowScene,FlowView,Node
from desktop.catalog import all_definitions,definition_for
from desktop.forms import ParameterPanel,ResultPanel
from desktop.backend import Backend
from desktop.toolbox import Toolbox
from desktop.image_view import ImageView
from desktop.cloud_view import CloudView

STYLE='''
QMainWindow,QWidget{font-family:"Microsoft YaHei UI","Noto Sans CJK SC";font-size:13px;color:#183954;}
QMainWindow{background:#e9f0f5;} QMenuBar,QToolBar{background:#fff;border-bottom:1px solid #cbdce8;spacing:9px;padding:7px;}
QToolButton{padding:7px 11px;border-radius:4px;}QToolButton:hover,QPushButton:hover{background:#e6f5fc;}
QPushButton{background:white;border:1px solid #bad2e1;border-radius:4px;padding:6px 10px;}
QPushButton:disabled,QToolButton:disabled{color:#9aabb7;}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{background:#fff;border:1px solid #bed1de;border-radius:3px;padding:5px;}
QTreeWidget,QTableWidget,QPlainTextEdit{background:white;border:1px solid #ccdce8;alternate-background-color:#f4f8fb;}
QHeaderView::section{background:#eef4f8;color:#355a74;padding:7px;border:0;border-bottom:1px solid #cedfe9;}
QTabWidget::pane{border:1px solid #cbdce8;background:#fff;}QTabBar::tab{background:#e9f1f6;padding:8px 15px;}
QTabBar::tab:selected{background:white;color:#008ebd;border-bottom:2px solid #109ecb;}
QSplitter::handle{background:#dae6ee;}QStatusBar{background:#092552;color:white;}
QLabel#brand{color:#0098c7;font-size:22px;font-weight:700;padding:5px 12px;}
'''


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
        self.build_ui();self.document.changed.connect(self.document_changed);self.populate_toolbox()
        self.document_changed();self.statusBar().showMessage('正在启动本机算法引擎…' if start_engine else '离线编辑')
        if start_engine:QTimer.singleShot(0,lambda:self.backend.start(self.root,self.data))

    def action(self,title,callback,shortcut=None):
        action=QAction(title,self);action.triggered.connect(lambda:self.guard(callback))
        if shortcut:action.setShortcut(QKeySequence(shortcut))
        return action

    def build_ui(self):
        files=self.menuBar().addMenu('文件');edit=self.menuBar().addMenu('编辑');view=self.menuBar().addMenu('视图')
        self.new_action=self.action('新建工程',self.new_project,'Ctrl+N');self.open_action=self.action('打开工程',self.open_project,'Ctrl+O')
        self.save_action=self.action('保存工程',self.save_project,'Ctrl+S')
        for a in [self.new_action,self.open_action,self.save_action]:files.addAction(a)
        templates=files.addMenu('从模板新建检测工程')
        for label, relative in [
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
        self.undo_action=self.action('撤销',self.document.undo,'Ctrl+Z');self.redo_action=self.action('重做',self.document.redo,'Ctrl+Y')
        for a in [self.undo_action,self.redo_action]:edit.addAction(a)
        edit.addAction(self.action('复制模块',self.copy_nodes,'Ctrl+Shift+C'));edit.addAction(self.action('粘贴模块',lambda:self.document.paste() if not self.busy else None,'Ctrl+Shift+V'))
        toolbar=QToolBar('工程与运行');toolbar.setMovable(False);self.addToolBar(toolbar)
        brand=QLabel('SIEANS VISION');brand.setObjectName('brand');toolbar.addWidget(brand)
        tag=QLabel('视觉检测平台');tag.setStyleSheet('color:#5a7a90;font-size:12px;padding-right:10px;');toolbar.addWidget(tag)
        for a in [self.open_action,self.save_action]:toolbar.addAction(a)
        self.image_action=self.action('打开图像',self.open_image);toolbar.addAction(self.image_action)
        self.reference_action=self.action('设置参考图',lambda:self.open_image(True));toolbar.addAction(self.reference_action)
        self.demo_action=self.action('演示工程',self.open_demo_library);toolbar.addAction(self.demo_action)
        self.return_demo_action=self.action('返回原工程',self.restore_demo);self.return_demo_action.setVisible(False);toolbar.addAction(self.return_demo_action);toolbar.addSeparator()
        self.run_action=self.action('▶ 运行流程',self.run,'Ctrl+Return');toolbar.addAction(self.run_action)
        self.run_selected_action=self.action('执行所选',lambda:self.run(self.selected));toolbar.addAction(self.run_selected_action)
        self.stop_action=self.action('■ 停止',lambda:self.request('stop',{},lambda _:None));toolbar.addAction(self.stop_action)
        toolbar.addSeparator();self.engine_label=QLabel('引擎启动中');toolbar.addWidget(self.engine_label)
        horizontal=QSplitter(Qt.Orientation.Horizontal);self.setCentralWidget(horizontal)
        library=QWidget();ll=QVBoxLayout(library);ll.setContentsMargins(8,8,8,8)
        ll.addWidget(QLabel('算子工具箱'));self.search=QLineEdit();self.search.setPlaceholderText('搜索算子…');ll.addWidget(self.search)
        self.toolbox=Toolbox();ll.addWidget(self.toolbox)
        self.toolbox.operatorActivated.connect(lambda key:self.guard(lambda:self.add_node(key)))
        self.search.textChanged.connect(self.populate_toolbox);ll.addWidget(QLabel('双击图标添加 · 拖入流程画布'))
        horizontal.addWidget(library)
        flow=QWidget();fl=QVBoxLayout(flow);fl.setContentsMargins(0,6,0,0)
        self.demo_notice=QLabel();self.demo_notice.setWordWrap(True);self.demo_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.demo_notice.setStyleSheet('background:#e4f5fc;color:#16779c;padding:8px;');self.demo_notice.hide();fl.addWidget(self.demo_notice)
        self.project_name=QLineEdit(self.document.project['name']);self.project_name.setAccessibleName('工程名称');self.project_name.editingFinished.connect(self.rename_project);fl.addWidget(self.project_name)
        bar=QHBoxLayout();fl.addLayout(bar)
        self.scene=FlowScene(self.document);self.flow=FlowView(self.scene)
        self.scene.chosen.connect(self.choose_node);self.scene.configure.connect(self.configure_node);self.scene.notice.connect(self.log)
        self.flow.dropped.connect(lambda key,pos:self.guard(lambda:self.add_node(key,pos)))
        for label,callback in [('自动排列',self.document.layout),('适应',self.flow.fit),('撤销',self.document.undo),('重做',self.document.redo)]:
            b=QPushButton(label);b.clicked.connect(lambda checked=False,cb=callback:self.guard(cb) if not self.busy else None);bar.addWidget(b)
        fl.addWidget(self.flow);fl.addWidget(QLabel('端口间拖拽连线 / 依次点击 · Esc 取消 · Ctrl+滚轮缩放'))
        horizontal.addWidget(flow)
        self.parameters=ParameterPanel();self.parameters.setMinimumWidth(320);self.parameters.setMaximumWidth(440);self.parameters.changed.connect(self.update_step);horizontal.addWidget(self.parameters)
        right=QSplitter(Qt.Orientation.Vertical);self.images=QTabWidget();self.input_view=ImageView();self.output_view=ImageView()
        self.images.addTab(self.input_view,'输入图像');self.images.addTab(self.output_view,'处理结果');right.addWidget(self.images)
        self.cloud_view=CloudView();self.images.addTab(self.cloud_view,'3D 点云');self.input_view.roi_changed.connect(self.update_roi)
        depth_page=QWidget();depth_layout=QVBoxLayout(depth_page);self.depth_view=ImageView();self.depth_caption=QLabel('尚无深度数据')
        self.depth_caption.setWordWrap(True);depth_layout.addWidget(self.depth_view,1);depth_layout.addWidget(self.depth_caption);self.images.addTab(depth_page,'深度图')
        self.results=ResultPanel();self.logs=QPlainTextEdit();self.logs.setReadOnly(True);self.logs.document().setMaximumBlockCount(200)
        if hasattr(self.results,'image_requested'):self.results.image_requested.connect(self.output_view.show_data)
        bottom=QTabWidget();bottom.addTab(self.results,'模块结果');bottom.addTab(self.logs,'运行记录');right.addWidget(bottom);right.setSizes([500,230])
        horizontal.addWidget(right);horizontal.setSizes([270,450,340,540]);horizontal.setChildrenCollapsible(False)
        view.addAction(self.action('适应流程',self.flow.fit));view.addAction(self.action('适应图像',lambda:(self.input_view.fit(),self.output_view.fit())))
        self.roi_action=self.action('框选所选模块 ROI',self.roi_mode);self.roi_action.setCheckable(True);view.addAction(self.roi_action)
        view.addAction(self.action('清除所选模块 ROI',lambda:self.update_roi(None)))
        self.menuBar().addAction(self.action('桌面版说明',self.about))

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
        self.toolbox.populate(self.definitions,self.search.text())

    def add_node(self,key,position=None):
        if self.busy or not key:return
        self.selected=self.document.add(self.definitions[key],position,parent=self.selected or 'source')
        self.scene.clearSelection();self.scene.nodes[self.selected].setSelected(True);self.refresh_parameters()

    def choose_node(self,node_id):
        self.selected=None if node_id=='source' else node_id;self.refresh_parameters()

    def configure_node(self,node_id):
        if node_id=='source':self.guard(self.open_image)
        else:self.choose_node(node_id);self.parameters.setFocus()

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

    def document_changed(self):
        p=self.document.project
        if self.selected not in [s['id'] for s in p['steps']]:self.selected=None
        self.setWindowTitle(('● ' if self.document.modified else '')+p['name']+' — SIEANS Vision 原生桌面版')
        self.project_name.setText(p['name']);self.undo_action.setEnabled(not self.busy and self.document.index>0)
        self.redo_action.setEnabled(not self.busy and self.document.index<len(self.document.history)-1)
        self.refresh_parameters();self.set_busy(self.busy)

    def rename_project(self):
        if self.busy:return
        p=deepcopy(self.document.project);p['name']=self.project_name.text().strip() or '未命名工程';self.document.commit(p)

    def confirm_discard(self,include_original=False):
        original_dirty=include_original and self.demo_backup is not None and self.demo_backup['project']!=self.demo_backup['saved']
        if not self.document.modified and not original_dirty:return True
        message='演示前的原工程还有未保存修改。可先取消并“返回原工程”保存；继续退出将放弃未保存内容。' if original_dirty else '放弃当前未保存修改？'
        return QMessageBox.question(self,'未保存修改',message,QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Discard

    def new_project(self):
        if self.busy or not self.confirm_discard():return
        self.document.load(empty_project());self.filename=None;self.image='';self.input_view.show_data('');self.output_view.show_data('');self.results.set_results([])
        self.clear_cloud()
        self.last_result=None
        self.show_platform_welcome()

    def open_project(self):
        if self.busy or not self.engine_ready or not self.confirm_discard():return
        name,_=QFileDialog.getOpenFileName(self,'打开视觉工程','','SIEANS 工程 (*.sieans *.json)')
        if not name:return
        self.open_project_file(Path(name))

    def open_project_file(self, path):
        path=Path(path)
        if not path.is_file():raise ValueError('工程不存在：'+str(path))
        if path.stat().st_size>32*1024*1024:raise ValueError('工程文件不能超过 32 MB')
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        def loaded(reply):
            self.document.load(reply['project']);self.filename=path;self.results.set_results([])
            self.image='';self.input_view.show_data('');self.output_view.show_data('');self.flow.fit()
            self.clear_cloud();self.last_result=None
            ops=', '.join(s.get('name') or s.get('operation') for s in reply['project'].get('steps',[]))
            self.log('已打开工程：'+path.name+' · 模块：'+ops+'（含相机采集时无需预先打开图像，直接运行流程）')
            notes=(reply['project'].get('notes') or '').strip()
            if notes:
                self.demo_notice.setText(notes);self.demo_notice.show()
            elif not reply['project'].get('steps'):
                self.show_platform_welcome()
            else:
                self.demo_notice.hide()
            QTimer.singleShot(300, self.maybe_warm_camera)
        self.request('project/validate',{'project':value},loaded)

    def save_project(self):
        if self.busy or not self.engine_ready:return
        name=str(self.filename) if self.filename else QFileDialog.getSaveFileName(self,'保存视觉工程',self.document.project['name']+'.sieans','SIEANS 工程 (*.sieans)')[0]
        if not name:return
        snapshot=deepcopy(self.document.project)
        def saved(reply):
            destination=Path(name);temporary=destination.with_suffix(destination.suffix+'.tmp')
            temporary.write_text(json.dumps(reply['project'],ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(destination)
            self.filename=destination;self.document.saved=deepcopy(snapshot);self.document_changed();self.log('工程已保存：'+str(destination))
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
        self.image=data;self.input_view.show_data(data);self.output_view.show_data('');self.results.set_results([]);self.log(f'载入图像 {image.width()} × {image.height()}')
        self.clear_cloud();self.last_result=None;self.refresh_parameters()
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
        self.busy=busy;self.flow.setEnabled(not busy);self.parameters.setEnabled(not busy);self.toolbox.setEnabled(not busy);self.project_name.setEnabled(not busy)
        for a in [self.new_action,self.image_action,self.reference_action,self.demo_action]:a.setEnabled(not busy)
        for a in [self.open_action,self.save_action,self.run_action,self.run_selected_action]:a.setEnabled(self.engine_ready and not busy)
        self.stop_action.setEnabled(busy);self.undo_action.setEnabled(not busy and self.document.index>0);self.redo_action.setEnabled(not busy and self.document.index+1<len(self.document.history))
        self.demo_action.setEnabled(self.engine_ready and not busy);self.return_demo_action.setEnabled(not busy and self.demo_backup is not None)
        for action in self.workspace_actions:action.setEnabled(self.engine_ready and (not busy or action.data() in ('continuous','hmi')))
        for key,dialog in list(self.dialogs.items()):
            if hasattr(dialog,'set_busy'):dialog.set_busy(busy)
            elif key!='login':dialog.setEnabled(not busy)

    def run(self,target=None):
        if self.busy or not self.engine_ready:return
        if not self.document.project['steps']:raise ValueError('请先添加流程模块')
        params=dict(project=deepcopy(self.document.project),image=self.image,allowScripts=self.script_action.isChecked())
        self.script_action.setChecked(False)
        if self.cloud:params['cloud']=self.cloud
        if self.depth:params['depth']=self.depth
        if target:params['target']=target
        self.set_busy(True);self.results.set_results([]);self.log('开始执行流程…')
        try:self.run_request=self.request('run',params,self.finished)
        except Exception:self.set_busy(False);raise

    def progress(self,value):
        if value.get('activeStep'):
            step=next((s for s in self.document.project['steps'] if s['id']==value['activeStep']),{})
            self.statusBar().showMessage('正在执行：'+step.get('name','流程模块'))
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
        text={'completed':'运行完成','cancelled':'已停止','failed':'运行失败'}.get(result.get('state'),result.get('state','未知'))
        self.log(f"{text} · {result.get('elapsedMs',0)} ms"+(' · '+result['error'] if result.get('error') else ''))

    def log(self,message):
        self.logs.appendPlainText(str(message));self.statusBar().showMessage(str(message))

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
        self.statusBar().showMessage(report.get('short') or report.get('message','').split('\n')[0])
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
                self.statusBar().showMessage('相机会话运行中 · 可直接运行流程')
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
        self.input_view.show_data(self.image);self.output_view.show_data('');self.cloud_view.set_cloud(self.cloud);self.results.set_results([])
        self.show_depth(self.depth)
        self.images.setCurrentIndex(2 if self.cloud else 0)
        if self.dialogs.get('hmi'):self.dialogs['hmi'].set_source_image(self.image)
        self.log('已接收相机数据，可运行检测流程')

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
            self.closing=True;self.setEnabled(False);self.statusBar().showMessage('正在停止算法进程…');self.backend.shutdown()
        event.ignore()
