"""Qt scene-based native flow editor. No browser or embedded HTML."""
from copy import deepcopy
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, Signal, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QFont, QPolygonF
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsItem, QGraphicsPathItem, QMenu, QApplication


class Port(QGraphicsObject):
    def __init__(self, owner, side, output):
        super().__init__(owner)
        self.node_id, self.side, self.output = owner.node_id, side, output
        x,y={'top':(110,0),'bottom':(110,owner.height),'left':(0,owner.height/2),'right':(220,owner.height/2)}[side]
        self.setPos(x,y);self.setZValue(4)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.highlight=None
        kind='图像订阅' if side in ('top','bottom') else '数据/控制';self.setToolTip(('输出' if output else '输入')+' · '+kind+'（'+( '实线=图像订阅' if side in ('top','bottom') else '虚线=数据/控制' )+'）：拖到目标端口；下方模块订阅上方；Esc 取消')
        self.setCursor(Qt.CursorShape.CrossCursor)

    def boundingRect(self):
        return QRectF(-8,-8,16,16)

    def paint(self,painter,option,widget=None):
        # Halcon-inspired: top/bottom ≈ iconic image chain (cyan); left/right ≈ control/data (amber).
        base='#e67a2e' if self.side in ('top','bottom') else '#d4a017'
        color=QColor('#d26345' if self.highlight=='invalid' else '#18a66d' if self.highlight=='valid' else base)
        painter.setPen(QPen(color,2 if self.highlight else 1.5));painter.setBrush(color if self.output or self.highlight=='valid' else QColor('white'))
        if self.highlight:painter.drawEllipse(QRectF(-8,-8,16,16))
        painter.drawEllipse(QRectF(-5,-5,10,10))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.scene().port_clicked(self);event.accept()
        else: super().mousePressEvent(event)


class Node(QGraphicsObject):
    def __init__(self,node_id,label,position,source=False):
        super().__init__()
        self.node_id,self.label,self.source=node_id,label,source
        self.height=44 if source else 80
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemIsSelectable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(position['x'],position['y']);self.setZValue(2)
        self.state='图像输入' if source else '等待执行'
        self.color='#2d9b6c'
        self.setToolTip(label+'\n拖动移动 · 双击配置 · Ctrl 多选')
        self.ports={side:Port(self,side,side in ('bottom','right')) for side in (('bottom','right') if source else ('top','left','bottom','right'))}

    def boundingRect(self):
        return QRectF(-2,-2,224,self.height+4)

    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected=self.isSelected()
        if self.source:
            fill=QColor('#3a2a1c' if selected else '#2f3a28')
            border=QColor('#e67a2e' if selected else '#5a8a4a')
        else:
            fill=QColor('#3a2a1c' if selected else '#2b333d')
            border=QColor('#e67a2e' if selected else '#4a5562')
        painter.setPen(QPen(border,2.4 if selected else 1.4))
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(0,0,220,self.height),14 if self.source else 8,14 if self.source else 8)
        painter.setPen(QColor('#f0f4f8'));painter.setFont(QFont('Microsoft YaHei UI',10,QFont.Weight.DemiBold))
        painter.drawText(QRectF(14,6,192,32),Qt.AlignmentFlag.AlignVCenter,painter.fontMetrics().elidedText(self.label,Qt.TextElideMode.ElideRight,190))
        if not self.source:
            painter.setPen(QPen(QColor('#3a4552'),1));painter.drawLine(12,42,208,42)
            painter.setPen(QColor(self.color));painter.setFont(QFont('Microsoft YaHei UI',9))
            painter.drawText(QRectF(14,46,192,28),Qt.AlignmentFlag.AlignVCenter,self.state)

    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return QPointF(max(0,min(9800,value.x())),max(0,min(9800,value.y())))
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            self.scene().update_edges()
        return super().itemChange(change,value)

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        scene=self.scene()
        QTimer.singleShot(0,scene.save_positions)

    def mouseDoubleClickEvent(self,event):
        self.scene().configure.emit(self.node_id);event.accept()


class Edge(QGraphicsPathItem):
    def __init__(self,edge,scene):
        super().__init__();self.edge=edge;self.host=scene
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(0);self.refresh()
        self.setToolTip('连线/订阅：'+edge.get('when','always')+' · 实线=图像订阅 虚线=数据控制 · 角标为模块序号 · Delete 删除')

    def refresh(self):
        origin=self.host.nodes.get(self.edge['from']);target=self.host.nodes.get(self.edge['to'])
        if not origin or not target:return
        a=origin.ports[self.edge.get('fromPort','bottom')].scenePos()
        b=target.ports[self.edge.get('toPort','top')].scenePos()
        path=QPainterPath(a)
        if self.edge.get('fromPort')=='right':
            mid=(a.x()+b.x())/2;path.lineTo(mid,a.y());path.lineTo(mid,b.y())
        else:
            mid=(a.y()+b.y())/2;path.lineTo(a.x(),mid);path.lineTo(b.x(),mid)
        path.lineTo(b);self.setPath(path)

    def paint(self,painter,option,widget=None):
        # B1: 实线=图像订阅(imageFrom)；虚线=数据/控制连线；选中橙
        step=next((s for s in self.host.document.project['steps'] if s['id']==self.edge['to']),None)
        is_image_sub = bool(step and step.get('imageFrom')==self.edge['from'])
        side_wire = self.edge.get('fromPort')=='right' or self.edge.get('toPort')=='left'
        color = QColor('#e67a2e' if self.isSelected() else ('#3a9a6c' if is_image_sub else '#d4a017'))
        p=QPen(color, 2.6 if self.isSelected() else 1.9)
        if (not is_image_sub) or side_wire:
            p.setStyle(Qt.PenStyle.DashLine)
        else:
            p.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(p);super().paint(painter,option,widget)
        end=self.path().pointAtPercent(1);painter.setBrush(p.color())
        if self.edge.get('toPort','top')=='left':points=[end,end+QPointF(-8,-4),end+QPointF(-8,4)]
        else:points=[end,end+QPointF(-4,-8),end+QPointF(4,-8)]
        painter.drawPolygon(QPolygonF(points))
        # 线序角标：上游序号 → 下游序号
        proj=self.host.document.project
        index_map={'source':0}
        for i,s in enumerate(proj.get('steps') or [], start=1):
            index_map[s['id']]=i
        a_i=index_map.get(self.edge['from'], '?')
        b_i=index_map.get(self.edge['to'], '?')
        mid=self.path().pointAtPercent(.5)
        badge=f'{a_i}→{b_i}'
        if is_image_sub:
            badge += ' ·图'
        painter.setPen(QColor('#c8d0d8'))
        painter.setFont(QFont('Microsoft YaHei UI', 8))
        painter.drawText(mid+QPointF(8, -4), badge)
        when=self.edge.get('when','always')
        if when not in ('always','success'):
            painter.setPen(QColor('#9aa7b5'));painter.drawText(mid+QPointF(6,12),{'true':'成立','false':'不成立','error':'失败'}.get(when,when))


class FlowScene(QGraphicsScene):
    chosen=Signal(str)
    configure=Signal(str)
    notice=Signal(str)

    def __init__(self,document):
        super().__init__();self.document=document;self.nodes={};self.edges=[];self.link=None;self.link_preview=None
        self.edit_locked=False
        self.selectionChanged.connect(self.selection_changed)
        document.changed.connect(self.rebuild)
        self.rebuild()

    def set_edit_locked(self, locked):
        self.edit_locked=bool(locked)
        if self.edit_locked:
            self.cancel_link()
        for node in self.nodes.values():
            node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.edit_locked)

    def rebuild(self):
        ids={n.node_id for n in self.selectedItems() if isinstance(n,Node)}
        self.blockSignals(True);self.link=None;self.link_preview=None;self.clear();self.nodes={};self.edges=[]
        p=self.document.project
        nodes=[dict(id='source',name='图像源1',position=p['sourcePosition']),*p['steps']]
        for i,n in enumerate(nodes):
            label=n.get('name',n.get('operation','图像源'))
            if i==0:
                label=f'0 {label}'
            else:
                label=f'{i} {label}'
            item=Node(n['id'],label,n.get('position',dict(x=60,y=40+i*130)),i==0)
            item.setToolTip(label+'\n序号 '+str(i)+' · 拖动移动 · 双击配置 · 端口拖拽订阅（下方←上方）')
            self.addItem(item);self.nodes[n['id']]=item
            if n['id'] in ids:item.setSelected(True)
            if self.edit_locked:
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        for e in p['edges']:
            item=Edge(e,self);self.addItem(item);self.edges.append(item)
        self.setSceneRect(self.itemsBoundingRect().adjusted(-40,-30,160,160));self.blockSignals(False)

    def selection_changed(self):
        nodes=[n.node_id for n in self.selectedItems() if isinstance(n,Node)]
        if nodes:self.chosen.emit(nodes[0])

    def update_edges(self):
        for edge in self.edges:edge.refresh()

    def save_positions(self):
        if self.edit_locked:return
        p=deepcopy(self.document.project)
        for node_id,item in self.nodes.items():
            pos=dict(x=round(item.x()/10)*10,y=round(item.y()/10)*10)
            if node_id=='source':p['sourcePosition']=pos
            else:next(s for s in p['steps'] if s['id']==node_id)['position']=pos
        self.document.commit(p)

    def port_clicked(self,port):
        if self.edit_locked:
            self.notice.emit('运行模式：画布编辑已锁定');return
        if self.link and self.link[2]!=port.output:self.finish_link(port)
        else:self.start_link(port)

    def start_link(self,port):
        self.cancel_link();self.link=(port.node_id,port.side,port.output)
        self.link_preview=self.addPath(QPainterPath(),QPen(QColor('#e67a2e'),2,Qt.PenStyle.DashLine))
        self.link_preview.setZValue(100);self.link_preview.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.update_link(port.scenePos())
        self.notice.emit('拖到另一模块的'+('输入' if port.output else '输出')+'端口松开，或点击目标端口；Esc 取消')

    def cancel_link(self):
        self.link=None
        if self.link_preview is not None:self.removeItem(self.link_preview);self.link_preview=None
        for node in self.nodes.values():
            for port in node.ports.values():
                if port.highlight:port.highlight=None;port.update()

    def update_link(self,point,target=None):
        if not self.link or self.link_preview is None:return
        origin=self.nodes.get(self.link[0])
        if not origin:self.cancel_link();return
        start=origin.ports[self.link[1]].scenePos()
        for node in self.nodes.values():
            for port in node.ports.values():
                highlight=('valid' if port.output!=self.link[2] and port.node_id!=self.link[0] else 'invalid') if port is target else None
                if port.highlight!=highlight:port.highlight=highlight;port.update()
        end=target.scenePos() if target else point
        a,b=(start,end) if self.link[2] else (end,start)
        side=self.link[1] if self.link[2] else target.side if target else 'bottom'
        path=QPainterPath(a)
        if side=='right':
            mid=(a.x()+b.x())/2;path.lineTo(mid,a.y());path.lineTo(mid,b.y())
        else:
            mid=(a.y()+b.y())/2;path.lineTo(a.x(),mid);path.lineTo(b.x(),mid)
        path.lineTo(b);self.link_preview.setPath(path)

    def finish_link(self,port):
        if self.edit_locked:self.cancel_link();return
        origin=self.link
        if origin is None:return
        target=(port.node_id,port.side,port.output) if port else None
        self.cancel_link()
        if target is None:self.notice.emit('已取消连线');return
        if origin[2]==target[2]:self.notice.emit('请将输出端口连接到输入端口');return
        output,input_=(origin,target) if origin[2] else (target,origin)
        try:
            self.document.connect(output[0],input_[0],output[1],input_[1]);self.notice.emit('已建立连线')
        except (ValueError,StopIteration) as error:self.notice.emit(str(error))

    def show_results(self,results):
        for record in results:
            item=self.nodes.get(record['id'])
            if not item:continue
            item.state='执行失败' if record.get('error') else '已跳过' if record.get('skipped') else f"完成 · {record.get('output',{}).get('elapsedMs',0)} ms"
            item.color='#e05555' if record.get('error') else '#2d9b6c';item.update()

    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QColor('#1e242c'))
        painter.setPen(QPen(QColor('#2a323c'),1))
        left=int(rect.left()/20)*20;top=int(rect.top()/20)*20
        # VisionMaster-style dotted grid
        for x in range(left,int(rect.right())+20,20):
            for y in range(top,int(rect.bottom())+20,20):
                painter.drawPoint(x,y)


class FlowView(QGraphicsView):
    dropped=Signal(str,object)

    def __init__(self,scene):
        super().__init__(scene);self.setAcceptDrops(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumWidth(360);self.setMouseTracking(True);self._port_press=None;self._link_dragged=False

    def port_at(self,point):
        point=point.toPoint() if isinstance(point,QPointF) else point
        candidates=[]
        for item in self.items(QRect(point.x()-12,point.y()-12,25,25)):
            if isinstance(item,Port):
                delta=self.mapFromScene(item.scenePos())-point;distance=delta.x()**2+delta.y()**2
                if distance<=12**2:candidates.append((distance,item))
        return min(candidates,key=lambda pair:pair[0])[1] if candidates else None

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            port=self.port_at(event.position())
            if port:
                scene=self.scene()
                completing=scene.link is not None and scene.link[2]!=port.output
                # Handle the gesture at view level so a document rebuild cannot
                # delete the QGraphicsObject currently processing a mouse event.
                self._port_press=None if completing else event.position()
                self._link_dragged=False;scene.port_clicked(port);event.accept();return
            self.scene().cancel_link()
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.scene().link:
            if self._port_press is not None and (event.position()-self._port_press).manhattanLength()>=QApplication.startDragDistance():self._link_dragged=True
            self.scene().update_link(self.mapToScene(event.position().toPoint()),self.port_at(event.position()))
            event.accept();return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._port_press is not None:
            moved=(event.position()-self._port_press).manhattanLength()>=QApplication.startDragDistance()
            self._port_press=None
            if self._link_dragged or moved:self.scene().finish_link(self.port_at(event.position()))
            self._link_dragged=False;event.accept();return
        super().mouseReleaseEvent(event)

    def focusOutEvent(self,event):
        self.scene().cancel_link();self._port_press=None;self._link_dragged=False;super().focusOutEvent(event)

    def fit(self):
        self.fitInView(self.scene().itemsBoundingRect().adjusted(-40,-40,40,40),Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11()>1.2:self.resetTransform()

    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor=1.15 if event.angleDelta().y()>0 else 1/1.15
            if .2 < self.transform().m11()*factor < 2.5:self.scale(factor,factor)
            event.accept()
        else:super().wheelEvent(event)

    def dragEnterEvent(self,event):
        if self.scene().edit_locked:event.ignore();return
        if event.mimeData().hasFormat('application/x-sieans-operator'):event.acceptProposedAction()

    def dragMoveEvent(self,event):
        if event.mimeData().hasFormat('application/x-sieans-operator'):event.acceptProposedAction()

    def dropEvent(self,event):
        if self.scene().edit_locked:
            event.ignore();return
        key=bytes(event.mimeData().data('application/x-sieans-operator')).decode('utf-8')
        pos=self.mapToScene(event.position().toPoint())
        self.dropped.emit(key,dict(x=max(0,min(9800,pos.x())),y=max(0,min(9800,pos.y()))));event.acceptProposedAction()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            self.scene().cancel_link();self._port_press=None;self._link_dragged=False;event.accept()
        elif event.key()==Qt.Key.Key_Delete:self.delete_selected()
        else:super().keyPressEvent(event)

    def delete_selected(self):
        if self.scene().edit_locked:
            self.scene().notice.emit('运行模式：画布编辑已锁定');return
        nodes=[n.node_id for n in self.scene().selectedItems() if isinstance(n,Node) and not n.source]
        edges=[n.edge['id'] for n in self.scene().selectedItems() if isinstance(n,Edge)]
        self.scene().document.remove(nodes,edges)

    def contextMenuEvent(self,event):
        if self.scene().edit_locked:
            event.accept();return
        self.scene().cancel_link();self._port_press=None
        item=self.itemAt(event.pos())
        if isinstance(item,Port):item=item.parentItem()
        menu=QMenu(self)
        if isinstance(item,Edge):
            origin=next((s for s in self.scene().document.project['steps'] if s['id']==item.edge['from']),None)
            conditions=[('always','正常完成后'),('success','成功时')]
            if origin:conditions.append(('error','失败时'))
            if origin and origin['operation']=='condition':conditions.extend([('true','判断成立时'),('false','判断不成立时')])
            for value,label in conditions:
                action=menu.addAction(label,lambda v=value,e=dict(item.edge):self.set_condition(e['id'],v))
                action.setCheckable(True);action.setChecked(item.edge.get('when','always')==value)
            menu.addSeparator()
        if isinstance(item,Node):
            if not item.isSelected():self.scene().clearSelection();item.setSelected(True)
            menu.addAction('配置模块',lambda:self.scene().configure.emit(item.node_id))
            menu.addAction('复制模块',lambda:self.scene().document.copy([n.node_id for n in self.scene().selectedItems() if isinstance(n,Node) and not n.source]))
        menu.addAction('粘贴模块',self.paste)
        menu.addAction('删除所选',self.delete_selected)
        menu.exec(event.globalPos())

    def paste(self):
        try:self.scene().document.paste()
        except ValueError as error:self.scene().notice.emit(str(error))

    def set_condition(self,edge_id,when):
        project=deepcopy(self.scene().document.project)
        next(e for e in project['edges'] if e['id']==edge_id)['when']=when
        self.scene().document.commit(project)
