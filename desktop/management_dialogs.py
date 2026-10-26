"""Project library, plugin administration, accounts and audit/history tables."""
from datetime import datetime
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QPushButton,QLabel,
    QLineEdit,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,QTabWidget,QWidget,QDialogButtonBox)
from desktop.forms import ResultPanel


class RpcDialog(QDialog):
    def __init__(self,backend,parent=None):
        super().__init__(parent);self.backend=backend;self.pending={};self.resize(900,640)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.layout=QVBoxLayout(self);self.message=QLabel();self.message.setWordWrap(True)
        backend.result.connect(self.received);backend.error.connect(self.failed)
    def request(self,method,params,callback):
        try:self.pending[self.backend.request(method,params)]=callback
        except Exception as error:self.message.setText(str(error))
    def received(self,key,value):
        callback=self.pending.pop(key,None)
        if callback:
            try:callback(value)
            except Exception as error:self.message.setText(str(error))
    def failed(self,key,message):
        if key in self.pending:self.pending.pop(key);self.message.setText(message)
    def table(self,labels):
        table=QTableWidget(0,len(labels));table.setHorizontalHeaderLabels(labels)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True);self.layout.addWidget(table);return table
    def buttons(self,entries):
        row=QHBoxLayout();self.layout.addLayout(row)
        for title,callback in entries:
            button=QPushButton(title);button.clicked.connect(callback);row.addWidget(button)
    def footer(self):self.layout.addWidget(self.message)


def populate(table,rows):
    table.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,value in enumerate(row):table.setItem(i,j,QTableWidgetItem(str(value)))

def date(value):
    try:return datetime.fromtimestamp(float(value)/1000).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError,ValueError,OSError):return ''


class LoginDialog(RpcDialog):
    authenticated=Signal()
    def __init__(self,backend,parent=None):
        super().__init__(backend,parent);self.setWindowTitle('管理员登录');self.resize(430,230)
        form=QFormLayout();self.layout.addLayout(form);self.username=QLineEdit('admin');self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('账号',self.username);form.addRow('密码',self.password)
        self.buttons([('登录',self.login)]);self.footer();self.password.returnPressed.connect(self.login)
    def login(self):
        self.request('auth/login',dict(username=self.username.text(),password=self.password.text()),self.accept_login);self.password.clear()
    def accept_login(self,value):self.authenticated.emit();self.accept()


class ProjectsDialog(RpcDialog):
    project_loaded=Signal(dict)
    project_saved=Signal(dict)
    def __init__(self,document,backend,parent=None):
        super().__init__(backend,parent);self.document=document;self.items=[];self.setWindowTitle('本机工程库')
        self.buttons([('刷新',self.refresh),('保存当前工程到库',self.save),('打开所选工程',self.open)])
        self.rows=self.table(['工程名称','模块数','更新时间']);self.rows.itemDoubleClicked.connect(lambda _:self.open());self.footer();self.refresh()
    def refresh(self):self.request('projects/list',{},self.loaded)
    def loaded(self,value):self.items=value['items'];populate(self.rows,[(r['name'],r['modules'],date(r['updatedAt'])) for r in self.items])
    def save(self):self.request('projects/save',{'project':self.document.project},self.saved)
    def saved(self,value):self.project_saved.emit(value['project']);self.message.setText('工程已保存到本机工程库');self.refresh()
    def open(self):
        row=self.rows.currentRow()
        if row<0:return
        self.request('projects/get',{'id':self.items[row]['id']},lambda value:self.project_loaded.emit(value['project']))


class HistoryDialog(RpcDialog):
    def __init__(self,backend,audit=False,parent=None):
        super().__init__(backend,parent);self.audit=audit;self.offset=0;self.items=[];self.setWindowTitle('操作记录' if audit else '检测历史')
        self.buttons([('刷新',self.refresh),('上一页',lambda:self.page(-1)),('下一页',lambda:self.page(1))])
        self.rows=self.table(['时间','账号','操作','结果'] if audit else ['工程','开始时间','状态','耗时 (ms)'])
        if not audit:
            self.details=ResultPanel();self.layout.addWidget(self.details);self.rows.itemSelectionChanged.connect(self.detail)
        self.footer();self.refresh()
    def page(self,delta):
        next_offset=max(0,self.offset+delta*30)
        if delta>0 and next_offset>=getattr(self,'total',0):return
        self.offset=next_offset;self.refresh()
    def refresh(self):
        params=dict(offset=self.offset,limit=30)
        if self.audit:params={k:str(v) for k,v in params.items()}
        self.request('audit/list' if self.audit else 'history/list',params,self.loaded)
    def loaded(self,value):
        self.items=value['items'];self.total=value['total']
        states={'completed':'完成','failed':'失败','cancelled':'取消','succeeded':'成功','rejected':'拒绝','accepted':'已接受'}
        if self.audit:rows=[(date(r['time']),r['actor'],value.get('actions',{}).get(r['action'],r['action']),states.get(r['outcome'],r['outcome'])) for r in self.items]
        else:rows=[(r['projectName'],date(r['startedAt']),states.get(r['state'],r['state']),r.get('elapsedMs','')) for r in self.items]
        populate(self.rows,rows);self.message.setText(f'共 {self.total} 条，当前第 {self.offset//30+1} 页')
    def detail(self):
        row=self.rows.currentRow()
        if row>=0:self.request('history/get',{'id':self.items[row]['id']},lambda value:self.details.set_results(value.get('results',[])))


class PluginsDialog(RpcDialog):
    updated=Signal()
    def __init__(self,backend,parent=None):
        super().__init__(backend,parent);self.items=[];self.setWindowTitle('算子插件管理')
        self.buttons([('刷新',self.refresh),('扫描已安装插件',self.reload),('启用所选',lambda:self.toggle(True)),('停用所选',lambda:self.toggle(False))])
        self.rows=self.table(['插件','版本','算子数','状态']);self.footer();self.refresh()
    def refresh(self):self.request('plugins/list',{},self.loaded)
    def loaded(self,value):
        self.items=value;populate(self.rows,[(p.get('name',p['id']),p['version'],len(p.get('operators',[])),'已启用' if p.get('enabled',True) else '已停用') for p in value])
    def reload(self):self.request('plugins/reload',{},lambda value:(self.loaded(value),self.updated.emit()))
    def toggle(self,enabled):
        row=self.rows.currentRow()
        if row>=0:self.request('plugins/update',dict(id=self.items[row]['id'],enabled=enabled),lambda _:(self.refresh(),self.updated.emit()))


class AccountsDialog(RpcDialog):
    def __init__(self,backend,parent=None):
        super().__init__(backend,parent);self.items=[];self.setWindowTitle('操作员账号管理')
        self.buttons([('刷新',self.refresh),('新建操作员',lambda:self.edit(True)),('修改所选密码 / 状态',lambda:self.edit(False))])
        self.rows=self.table(['账号','角色','状态','来源']);self.footer();self.refresh()
    def refresh(self):self.request('accounts/list',{},self.loaded)
    def loaded(self,value):
        self.items=value['configured']+value['users'];populate(self.rows,[(r['username'],'管理员' if r['role']=='admin' else '操作员','启用' if r['enabled'] else '停用','部署配置' if not r.get('managed') else '本机账号') for r in self.items])
        self.message.setText('本页管理操作员账号。管理员凭据沿用部署配置。' if value['canManage'] else '当前为本机开发模式。配置 ADMIN_PASSWORD_HASH 后可管理账号。')
    def edit(self,new):
        row=self.rows.currentRow();record=None if new else self.items[row] if row>=0 else None
        if not new and (not record or not record.get('managed')):self.message.setText('请选择可管理的操作员账号');return
        dialog=QDialog(self);dialog.setWindowTitle('新建操作员' if new else '修改操作员');form=QFormLayout(dialog)
        name=QLineEdit('' if new else record['username']);name.setReadOnly(not new);password=QLineEdit();password.setEchoMode(QLineEdit.EchoMode.Password)
        password.setPlaceholderText('至少 12 个字符；修改时留空保留密码');enabled=QCheckBox('启用');enabled.setChecked(True if new else record['enabled'])
        form.addRow('账号',name);form.addRow('密码',password);form.addRow('状态',enabled)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        body={'enabled':enabled.isChecked()}
        if new:body['username']=name.text()
        if password.text():body['password']=password.text()
        self.request('accounts/create' if new else 'accounts/update',body if new else {'id':record['id'],'changes':body},lambda _:self.refresh());password.clear()
