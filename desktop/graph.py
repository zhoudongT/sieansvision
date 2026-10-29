"""Qt scene-based native flow editor. No browser or embedded HTML."""
from copy import deepcopy
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, Signal, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QFont, QPolygonF
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsItem, QGraphicsPathItem, QMenu, QApplication
from desktop.theme import ACCENT, CANVAS, CANVAS_DOT, CARD, LINE, SELECTED, TEXT, TEXT_MUTED, OK, WARN
from desktop.config_status import node_needs_bang, node_incomplete_reason


class Port(QGraphicsObject):
    def __init__(self, owner, side, output):
        super().__init__(owner)
        self.node_id, self.side, self.output = owner.node_id, side, output
        w, h = owner.width, owner.height
        x, y = {
            'top': (w / 2, 0),
            'bottom': (w / 2, h),
            'left': (0, h / 2),
            'right': (w, h / 2),
        }[side]
        self.setPos(x, y)
        self.setZValue(4)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.highlight = None
        kind = '图像订阅' if side in ('top', 'bottom') else '数据/控制'
        self._base_tip = (
            ('输出' if output else '输入') + ' · ' + kind
            + '（' + ('实线=图像订阅' if side in ('top', 'bottom') else '虚线=数据/控制')
            + '）：拖到目标端口；下方模块订阅上方；Esc 取消'
        )
        self.setToolTip(self._base_tip)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def boundingRect(self):
        return QRectF(-6, -6, 12, 12)

    def paint(self, painter, option, widget=None):
        # Compact VM-style ports; accent on highlight only.
        if self.highlight == 'invalid':
            color = QColor('#d26345')
        elif self.highlight == 'valid':
            color = QColor('#18a66d')
        else:
            color = QColor(ACCENT if self.side in ('top', 'bottom') else '#b0b0b0')
        painter.setPen(QPen(color, 1.4 if self.highlight else 1.0))
        painter.setBrush(color if self.output or self.highlight == 'valid' else QColor('#f5f5f5'))
        if self.highlight:
            painter.drawEllipse(QRectF(-6, -6, 12, 12))
        painter.drawEllipse(QRectF(-3.5, -3.5, 7, 7))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.scene().port_clicked(self)
            event.accept()
        else:
            super().mousePressEvent(event)


class Node(QGraphicsObject):
    """VisionMaster-style compact light pill node."""
    WIDTH = 168
    HEIGHT = 28
    WORLD_MIN = -4000
    WORLD_MAX = 12000

    def __init__(self, node_id, label, position, source=False):
        super().__init__()
        self.node_id, self.label, self.source = node_id, label, source
        self.width = Node.WIDTH
        self.height = Node.HEIGHT
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setPos(position['x'], position['y'])
        self.setZValue(2)
        self.state = '图像输入' if source else '等待执行'
        self.color = '#2d9b6c'
        self.needs_config = False  # N4: 未配置完整 → 红叹号
        self.run_failed = False    # 运行失败 → 红叹号（与未配置同徽章）
        self.setToolTip(label + '\n拖动移动 · 双击配置 · Ctrl 多选')
        sides = ('bottom', 'right') if source else ('top', 'left', 'bottom', 'right')
        self.ports = {side: Port(self, side, side in ('bottom', 'right')) for side in sides}

    def boundingRect(self):
        # Extra pad on top-right for N4 red bang badge.
        return QRectF(-3, -8, self.width + 14, self.height + 14)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isSelected()
        # Light / white pill like VM; source slightly warm.
        if self.source:
            fill = QColor('#e8e4d4' if not selected else '#f0e8d0')
            border = QColor(ACCENT if selected else '#c4b896')
        else:
            fill = QColor('#f2f2f2' if not selected else '#fff8f0')
            border = QColor(ACCENT if selected else '#c8c8c8')
        pen = QPen(border, 1.8 if selected else 1.1)
        if selected:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(0, 0, self.width, self.height), 3, 3)
        # Orange icon badge on the left (status color after run)
        badge = QRectF(5, 5, 18, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        badge_color = ACCENT
        if not self.source and self.state and not self.state.startswith('等待'):
            badge_color = self.color or ACCENT
        painter.setBrush(QColor(badge_color))
        painter.drawRoundedRect(badge, 2, 2)
        painter.setPen(QPen(QColor('#ffffff'), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self.source:
            painter.drawRoundedRect(QRectF(8, 9, 12, 9), 1, 1)
            painter.drawEllipse(QRectF(11.5, 11, 5, 5))
        else:
            painter.drawEllipse(QRectF(9, 9, 10, 10))
            painter.drawPoint(QPointF(14, 14))
        # Index + name
        painter.setPen(QColor('#222222'))
        painter.setFont(QFont('Microsoft YaHei UI', 9, QFont.Weight.Medium))
        text_rect = QRectF(28, 0, self.width - 34, self.height)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            painter.fontMetrics().elidedText(self.label, Qt.TextElideMode.ElideRight, int(text_rect.width())),
        )
        # N4: VisionMaster 未配置/失败红叹号（节点右上角）
        if self.needs_config or self.run_failed:
            cx = self.width - 2
            cy = 2
            tri = QPolygonF([
                QPointF(cx, cy - 7),
                QPointF(cx + 8, cy + 7),
                QPointF(cx - 8, cy + 7),
            ])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#e53935'))
            painter.drawPolygon(tri)
            painter.setPen(QPen(QColor('#ffffff'), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx, cy - 2), QPointF(cx, cy + 3))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#ffffff'))
            painter.drawEllipse(QPointF(cx, cy + 5.5), 1.1, 1.1)
            # Soft red border cue when incomplete
            if self.needs_config and not selected:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor('#e05555'), 1.4))
                painter.drawRoundedRect(QRectF(0, 0, self.width, self.height), 3, 3)

    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Soft world bounds only. A hard y>=0 floor left an empty band at the
            # top of the canvas (sceneRect is padded above items), so nodes could
            # never reach the visible top edge — Allen: 「允许移动上画布最上边」.
            return QPointF(
                max(Node.WORLD_MIN, min(Node.WORLD_MAX, value.x())),
                max(Node.WORLD_MIN, min(Node.WORLD_MAX, value.y())),
            )
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
        # VM: solid orange vertical image chain; dashed for side data wires.
        step=next((s for s in self.host.document.project['steps'] if s['id']==self.edge['to']),None)
        is_image_sub = bool(step and step.get('imageFrom')==self.edge['from'])
        side_wire = self.edge.get('fromPort')=='right' or self.edge.get('toPort')=='left'
        color = QColor(ACCENT)
        p=QPen(color, 2.2 if self.isSelected() else 1.6)
        if (not is_image_sub) or side_wire:
            p.setStyle(Qt.PenStyle.DashLine)
        else:
            p.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(p);super().paint(painter,option,widget)
        end=self.path().pointAtPercent(1);painter.setBrush(p.color());painter.setPen(Qt.PenStyle.NoPen)
        if self.edge.get('toPort','top')=='left':
            points=[end,end+QPointF(-7,-3.5),end+QPointF(-7,3.5)]
        else:
            points=[end,end+QPointF(-3.5,-7),end+QPointF(3.5,-7)]
        painter.drawPolygon(QPolygonF(points))
        when=self.edge.get('when','always')
        if when not in ('always','success'):
            mid=self.path().pointAtPercent(.5)
            painter.setPen(QColor(TEXT_MUTED));painter.setFont(QFont('Microsoft YaHei UI', 8))
            painter.drawText(mid+QPointF(6,4),{'true':'成立','false':'不成立','error':'失败'}.get(when,when))


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
            item=Node(n['id'],label,n.get('position',dict(x=60,y=40+i*56)),i==0)
            item.needs_config = node_needs_bang(p, n['id'])
            tip = label+'\n序号 '+str(i)+' · 拖动移动 · 双击配置 · 端口拖拽订阅（下方←上方）'
            if item.needs_config:
                why = node_incomplete_reason(p, n['id']) or '请检查必填项'
                tip += '\n⚠ 组件参数未配置完整：' + why
            item.setToolTip(tip)
            self.addItem(item);self.nodes[n['id']]=item
            if n['id'] in ids:item.setSelected(True)
            if self.edit_locked:
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        for e in p['edges']:
            item=Edge(e,self);self.addItem(item);self.edges.append(item)
        # Stable world-sized sceneRect (not itemsBoundingRect). Growing/shrinking the
        # rect while dragging — as 4f55066 did via expand_for_item — shifts QGraphicsView
        # alignment/scroll and makes undragged siblings appear to teleport on screen.
        # Soft WORLD_MIN/MAX clamps still let nodes reach the canvas top; fit()/minimap
        # frame itemsBoundingRect, so the large rect does not change navigation UX.
        self.setSceneRect(QRectF(
            Node.WORLD_MIN, Node.WORLD_MIN,
            Node.WORLD_MAX - Node.WORLD_MIN, Node.WORLD_MAX - Node.WORLD_MIN,
        ))
        self.blockSignals(False)

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
        self.link_preview=self.addPath(QPainterPath(),QPen(QColor(ACCENT),2,Qt.PenStyle.DashLine))
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
                if port.highlight!=highlight:
                    port.highlight=highlight
                    port.update()
                    base = getattr(port, '_base_tip', None) or (port.toolTip() or '')
                    if highlight == 'invalid':
                        port.setToolTip(base + '\n✗ 无效：同向端口或连到自身 — 请拖到对端输入/输出')
                    elif highlight == 'valid':
                        port.setToolTip(base + '\n✓ 可连：松开完成订阅')
                    else:
                        port.setToolTip(base)
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
            failed = bool(record.get('error'))
            item.state='执行失败' if failed else '已跳过' if record.get('skipped') else f"完成 · {record.get('output',{}).get('elapsedMs',0)} ms"
            item.color='#e05555' if failed else OK
            item.run_failed = failed
            item.update()

    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QColor(CANVAS))
        painter.setPen(QPen(QColor(CANVAS_DOT),1.2))
        step=16
        left=int(rect.left()/step)*step;top=int(rect.top()/step)*step
        # t249u: cap dotted-grid loops (huge exposed sceneRect → GUI spin / 无响应)
        max_span = step * 256
        right = min(int(rect.right()) + step, left + max_span)
        bottom = min(int(rect.bottom()) + step, top + max_span)
        for x in range(left, right, step):
            for y in range(top, bottom, step):
                painter.drawPoint(x,y)


class FlowView(QGraphicsView):
    dropped=Signal(str,object)

    def __init__(self,scene):
        super().__init__(scene);self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumWidth(360);self.setMouseTracking(True);self._port_press=None;self._link_dragged=False

    def port_at(self,point):
        """Hit-test ports in viewport space.

        Ports use ItemIgnoresTransformations so they stay easy to click when
        zoomed out. Compact VM nodes are only ~28px tall, so a fixed 12px
        radius used to cover the whole pill and steal node moves. Prefer an
        exact Port under the cursor; expand the radius only over empty canvas.
        """
        point=point.toPoint() if isinstance(point,QPointF) else point
        for item in self.items(point):
            if isinstance(item,Port):
                return item
            if isinstance(item,Node):
                break
        over_node=any(isinstance(item,Node) for item in self.items(point))
        # Tight on node body so repositioning still works; generous on empty
        # canvas so zoomed-out port linking stays easy (see test_native_graph).
        radius=4 if over_node else 12
        candidates=[]
        for item in self.items(QRect(point.x()-radius,point.y()-radius,2*radius+1,2*radius+1)):
            if isinstance(item,Port):
                delta=self.mapFromScene(item.scenePos())-point
                distance=delta.x()**2+delta.y()**2
                if distance<=radius*radius:
                    candidates.append((distance,item))
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
        if self.scene().edit_locked or not event.mimeData().hasFormat('application/x-sieans-operator'):
            event.ignore();return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragMoveEvent(self,event):
        if self.scene().edit_locked or not event.mimeData().hasFormat('application/x-sieans-operator'):
            event.ignore();return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dropEvent(self,event):
        if self.scene().edit_locked or not event.mimeData().hasFormat('application/x-sieans-operator'):
            event.ignore();return
        raw=bytes(event.mimeData().data('application/x-sieans-operator')).decode('utf-8').strip()
        if not raw:
            event.ignore();return
        pos=self.mapToScene(event.position().toPoint())
        self.dropped.emit(raw,dict(
            x=max(Node.WORLD_MIN,min(Node.WORLD_MAX,pos.x())),
            y=max(Node.WORLD_MIN,min(Node.WORLD_MAX,pos.y())),
        ))
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

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
