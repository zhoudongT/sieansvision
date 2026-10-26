"""Searchable native library for the existing web demonstration projects."""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QSplitter,QWidget,QLabel,
    QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QPushButton,QDialogButtonBox,QScrollArea)


class DemoDialog(QDialog):
    load_requested=Signal(str,bool)
    sample_requested=Signal()

    def __init__(self,backend,root,parent=None):
        super().__init__(parent);self.backend=backend;self.root=Path(root);self.items=[];self.visible_items=[]
        self.pending=None;self.busy=False;self.setWindowTitle('视觉演示工程库');self.resize(1180,760)
        self.setMinimumSize(920,620);self.setWindowModality(Qt.WindowModality.WindowModal)
        layout=QVBoxLayout(self)
        intro=QLabel('沿用原网页演示工程与素材。载入时暂存当前工程，可通过“返回原工程”恢复；演示不会自动保存。')
        intro.setWordWrap(True);layout.addWidget(intro)
        filters=QHBoxLayout();self.category=QComboBox();self.category.addItem('全部分类',None)
        self.search=QLineEdit();self.search.setPlaceholderText('搜索名称、算子或预期结果…')
        filters.addWidget(self.category);filters.addWidget(self.search,1);self.count=QLabel();filters.addWidget(self.count);layout.addLayout(filters)
        split=QSplitter();layout.addWidget(split,1)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['分类','演示工程','运行条件'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True);self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        split.addWidget(self.table)
        details=QWidget();right=QVBoxLayout(details)
        self.title=QLabel('选择演示工程');self.title.setWordWrap(True);self.title.setStyleSheet('font-size:18px;font-weight:600;color:#008fbb;')
        self.preview=QLabel('2D 图像 · 3D 点云 · 采集 · 流程 · 通信');self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(280,170);self.preview.setMaximumHeight(245)
        self.preview.setStyleSheet('background:#eef5f9;border:1px solid #d5e3ed;color:#5b778a;')
        self.description=QLabel();self.expected=QLabel();self.requirements=QLabel()
        self.expected.setStyleSheet('color:#087eaa;background:#eaf6fc;padding:10px;')
        for label in (self.title,self.description,self.expected,self.requirements):
            label.setWordWrap(True);label.setTextFormat(Qt.TextFormat.PlainText)
        for widget in (self.title,self.preview,self.description,self.expected,self.requirements):right.addWidget(widget)
        right.addStretch();details_scroll=QScrollArea();details_scroll.setWidgetResizable(True);details_scroll.setMinimumWidth(340)
        details_scroll.setWidget(details);split.addWidget(details_scroll);split.setSizes([690,430])
        self.message=QLabel('正在读取演示工程…');self.message.setWordWrap(True);layout.addWidget(self.message)
        actions=QHBoxLayout();self.sample_button=QPushButton('仅载入当前算子的示例数据');actions.addWidget(self.sample_button);actions.addStretch()
        self.load_button=QPushButton('仅载入工程');self.run_button=QPushButton('载入并运行')
        self.run_button.setStyleSheet('background:#009aca;color:white;border-color:#009aca;')
        actions.addWidget(self.load_button);actions.addWidget(self.run_button);layout.addLayout(actions)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(self.reject);layout.addWidget(close)
        self.table.itemSelectionChanged.connect(self.selected);self.table.itemDoubleClicked.connect(lambda _:self.load(True))
        self.search.textChanged.connect(self.filter);self.category.currentIndexChanged.connect(self.filter)
        self.load_button.clicked.connect(lambda:self.load(False));self.run_button.clicked.connect(lambda:self.load(True))
        self.sample_button.clicked.connect(self.sample_requested.emit)
        backend.result.connect(self.received);backend.error.connect(self.failed)
        self.set_busy(False)
        try:self.pending=backend.request('demos/list',{})
        except Exception as error:self.message.setText(str(error))

    def received(self,key,value):
        if key!=self.pending:return
        self.pending=None;self.items=value['items'];self.category.blockSignals(True)
        self.category.clear();self.category.addItem('全部分类',None)
        for category in dict.fromkeys(i.get('category','其他') for i in self.items):self.category.addItem(category,category)
        self.category.blockSignals(False);self.message.setText('选择案例查看说明与预期结果；AI 权重及可选依赖沿用本机配置。');self.filter()

    def failed(self,key,message):
        if key==self.pending:self.pending=None;self.message.setText(message)

    def filter(self,*_):
        category=self.category.currentData();query=self.search.text().strip().casefold()
        self.visible_items=[i for i in self.items if (category is None or i.get('category')==category) and
                            (not query or query in ' '.join(str(i.get(k,'')) for k in ('name','category','description','expected')).casefold())]
        self.table.blockSignals(True);self.table.setRowCount(len(self.visible_items))
        for row,item in enumerate(self.visible_items):
            condition='需确认脚本' if item.get('hasScripts') else '仅载入' if item.get('loadOnly') else '检查依赖' if item.get('requirements') else '可运行'
            for col,value in enumerate((item.get('category','其他'),item['name'],condition)):
                cell=QTableWidgetItem(value);cell.setToolTip(item.get('description',''));self.table.setItem(row,col,cell)
            self.table.setRowHeight(row,36)
        self.table.blockSignals(False);self.count.setText(f'{len(self.visible_items)} / {len(self.items)} 项')
        if self.visible_items:self.table.selectRow(0)
        self.selected()

    def current(self):
        row=self.table.currentRow();return self.visible_items[row] if 0<=row<len(self.visible_items) else None

    def selected(self):
        item=self.current();self.preview.clear()
        if not item:
            self.title.setText('没有匹配的演示工程');self.description.clear();self.expected.clear();self.requirements.clear();self.set_busy(self.busy);return
        self.title.setText(item['name']);self.description.setText(item.get('description',''));self.expected.setText('预期结果\n'+item.get('expected',''))
        notes=list(item.get('requirements') or [])
        if item.get('unavailableReason'):notes.append(item['unavailableReason'])
        if item.get('hasScripts') and not any('脚本' in n for n in notes):notes.append('含 Python 脚本，仅载入；检查后勾选本次可信执行，再运行。')
        if item.get('loadOnly') and not any('事件' in n for n in notes):notes.append('此案例需先启动事件触发，再发送模拟测试事件。')
        self.requirements.setText('\n'.join(notes))
        asset=item.get('preview') or item.get('image')
        if isinstance(asset,str):
            folder=(self.root/'public/vision/samples').resolve();path=(folder/asset).resolve()
            if path.is_relative_to(folder) and path.is_file() and path.stat().st_size<12_000_000:
                image=QPixmap(str(path))
                if not image.isNull():self.preview.setPixmap(image.scaled(380,225,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        if self.preview.pixmap() is None or self.preview.pixmap().isNull():self.preview.setText(item.get('category','视觉')+' · 演示工程')
        self.set_busy(self.busy)

    def set_busy(self,busy):
        self.busy=bool(busy);item=self.current();enabled=not self.busy and item is not None and item.get('available',True)
        self.load_button.setEnabled(enabled);self.run_button.setEnabled(enabled);self.sample_button.setEnabled(not self.busy)
        self.run_button.setText('载入演示' if item and (item.get('loadOnly') or item.get('hasScripts') or item.get('requirements')) else '载入并运行')
        self.table.setEnabled(not self.busy);self.category.setEnabled(not self.busy);self.search.setEnabled(not self.busy)

    def load(self,run):
        item=self.current()
        if self.busy or not item or not item.get('available',True):return
        self.message.setText('正在载入工程与素材…');self.load_requested.emit(item['id'],run)
