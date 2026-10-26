import base64
from PySide6.QtCore import Qt,Signal,QRectF
from PySide6.QtGui import QPixmap,QColor,QPen
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene


class ImageView(QGraphicsView):
    roi_changed=Signal(list)
    def __init__(self):
        super().__init__();self.setScene(QGraphicsScene(self));self.setBackgroundBrush(QColor('#f1f5f8'))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag);self.setMinimumSize(230,150)
        self.select_roi=False;self.origin=None;self.overlay=None;self.bounds=QRectF()
        self.scene().addText('打开图像，或载入演示').setDefaultTextColor(QColor('#7893a7'))

    def show_data(self,data):
        pixmap=QPixmap()
        if data:pixmap.loadFromData(base64.b64decode(data.split(',',1)[-1]))
        self.scene().clear();self.overlay=None;self.bounds=QRectF()
        if not pixmap.isNull():self.scene().addPixmap(pixmap);self.bounds=QRectF(pixmap.rect());self.scene().setSceneRect(self.bounds);self.fit()

    def set_roi_mode(self,enabled):
        self.select_roi=enabled;self.setDragMode(QGraphicsView.DragMode.NoDrag if enabled else QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def show_roi(self,roi):
        if self.overlay:self.scene().removeItem(self.overlay);self.overlay=None
        if isinstance(roi,list) and len(roi)==4 and all(isinstance(x,(int,float)) for x in roi):
            pen=QPen(QColor('#00acd4'),2,Qt.PenStyle.DashLine);pen.setCosmetic(True)
            self.overlay=self.scene().addRect(QRectF(*roi),pen);self.overlay.setZValue(10)

    def fit(self):
        if not self.bounds.isEmpty():self.fitInView(self.bounds,Qt.AspectRatioMode.KeepAspectRatio)
    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            scale=1.2 if event.angleDelta().y()>0 else 1/1.2
            if .01<self.transform().m11()*scale<40:self.scale(scale,scale)
        else:super().wheelEvent(event)
    def mousePressEvent(self,event):
        if self.select_roi and event.button()==Qt.MouseButton.LeftButton and not self.bounds.isEmpty():self.origin=self.mapToScene(event.position().toPoint());event.accept()
        else:super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.origin is not None:
            rect=QRectF(self.origin,self.mapToScene(event.position().toPoint())).normalized().intersected(self.bounds)
            self.show_roi([rect.x(),rect.y(),rect.width(),rect.height()]);event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.origin is not None:
            rect=QRectF(self.origin,self.mapToScene(event.position().toPoint())).normalized().intersected(self.bounds).toAlignedRect();self.origin=None
            if rect.width()>=2 and rect.height()>=2:self.roi_changed.emit([rect.x(),rect.y(),rect.width(),rect.height()])
            event.accept()
        else:super().mouseReleaseEvent(event)
