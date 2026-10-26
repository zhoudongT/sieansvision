from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QSplitter,QWidget,QListWidget,QPushButton,QInputDialog,QComboBox,QLabel,QMessageBox
from desktop.model import Document,empty_project
from desktop.graph import FlowScene,FlowView,Node
from desktop.forms import ParameterPanel
from desktop.catalog import definition_for


class SubflowsDialog(QDialog):
    def __init__(self,document,definitions,parent=None):
        super().__init__(parent);self.document=document;self.definitions=definitions;self.current=None;self.selected=None;self.loading=False
        self.setWindowTitle('子流程管理');self.resize(1150,760);self.work=Document()
        layout=QVBoxLayout(self);tools=QHBoxLayout();layout.addLayout(tools)
        for title,callback in [('新建子流程',self.create),('保存子流程修改',self.save),('删除未引用定义',self.remove)]:
            b=QPushButton(title);b.clicked.connect(lambda _=False,cb=callback:self.guard(cb));tools.addWidget(b)
        split=QSplitter();layout.addWidget(split);self.list=QListWidget();self.list.setMaximumWidth(230);split.addWidget(self.list)
        middle=QWidget();ml=QVBoxLayout(middle);self.catalog=QComboBox()
        for key,d in definitions.items():self.catalog.addItem(d['name'],key)
        ml.addWidget(self.catalog);add=QPushButton('添加所选算子');add.clicked.connect(lambda:self.guard(self.add));ml.addWidget(add)
        self.scene=FlowScene(self.work);self.view=FlowView(self.scene);ml.addWidget(self.view);split.addWidget(middle)
        self.parameters=ParameterPanel();split.addWidget(self.parameters);self.output=QComboBox();ml.addWidget(QLabel('子流程输出节点'));ml.addWidget(self.output)
        self.notice=QLabel('修改后保存；主工程保存时一并持久化。子流程使用独立变量作用域。');layout.addWidget(self.notice)
        self.list.currentRowChanged.connect(lambda _:self.guard(self.choose));self.scene.chosen.connect(self.select)
        self.scene.notice.connect(self.notice.setText);self.parameters.changed.connect(self.update_step)
        self.work.changed.connect(self.render);self.output.currentIndexChanged.connect(self.output_changed)
        self.view.dropped.connect(lambda key,pos:self.guard(lambda:self.add(key,pos)))
        self.refresh_list()
    def guard(self,callback):
        try:callback()
        except Exception as error:self.notice.setText(str(error))
    def refresh_list(self):
        self.list.blockSignals(True);self.list.clear()
        for d in self.document.project.get('subflows',[]):self.list.addItem(d['name'])
        self.list.blockSignals(False)
    def create(self):
        self.save();name,ok=QInputDialog.getText(self,'新建子流程','名称')
        if not ok or not name.strip():return
        p=deepcopy(self.document.project);library=p.setdefault('subflows',[])
        if len(library)>=20:raise ValueError('最多 20 个子流程')
        item=empty_project();item['name']=name.strip();item['outputNode']=None;library.append(item)
        self.document.commit(p);self.refresh_list();self.list.setCurrentRow(len(library)-1)
    def choose(self):
        row=self.list.currentRow()
        if row<0:return
        self.save();definition=self.document.project.get('subflows',[])[row];self.current=definition['id'];self.selected=None
        self.work.load(definition);self.render();self.view.fit()
    def select(self,node_id):self.selected=None if node_id=='source' else node_id;self.render()
    def add(self,key=None,position=None):
        if not self.current:raise ValueError('请先新建或选择子流程')
        key=key or self.catalog.currentData();self.selected=self.work.add(self.definitions[key],position,self.selected or 'source');self.render();self.view.fit()
    def render(self):
        self.loading=True;self.output.clear();self.output.addItem('选择输出节点',None)
        for s in self.work.project['steps']:self.output.addItem(s.get('name',s['operation']),s['id'])
        self.output.setCurrentIndex(max(0,self.output.findData(self.work.project.get('outputNode'))));self.loading=False
        step=next((s for s in self.work.project['steps'] if s['id']==self.selected),None)
        definition=deepcopy(definition_for(step,self.definitions)) if step else None
        if step and step['operation'] in ('subflow','loop'):
            for f in definition['parameters']:
                if f['key']=='subflowId':f['choices']=[{'value':s['id'],'label':s['name']} for s in self.document.project.get('subflows',[]) if s['id']!=self.current]
        self.parameters.set_step(step,definition,self.work.project)
    def update_step(self,step):
        p=deepcopy(self.work.project);p['steps']=[step if s['id']==step['id'] else s for s in p['steps']];self.guard(lambda:self.work.commit(p))
    def output_changed(self):
        if self.loading or not self.current:return
        p=deepcopy(self.work.project);p['outputNode']=self.output.currentData();self.work.commit(p)
    def save(self):
        if not self.current:return
        p=deepcopy(self.document.project);value=deepcopy(self.work.project);value.pop('subflows',None)
        p['subflows']=[value if s['id']==self.current else s for s in p.get('subflows',[])]
        self.document.commit(p);self.work.saved=deepcopy(self.work.project);self.notice.setText('子流程已更新到主工程；请保存主工程文件')
    def remove(self):
        if not self.current:return
        p=deepcopy(self.document.project);steps=p['steps']+[s for d in p.get('subflows',[]) for s in d['steps']]
        if any(s['operation'] in ('loop','subflow') and s.get('params',{}).get('subflowId')==self.current for s in steps):raise ValueError('子流程已被引用，请先移除调用')
        p['subflows']=[s for s in p.get('subflows',[]) if s['id']!=self.current];self.document.commit(p);self.current=None;self.work.load(empty_project());self.refresh_list()
    def closeEvent(self,event):
        try:self.save();event.accept()
        except Exception as error:self.notice.setText(str(error));event.ignore()
