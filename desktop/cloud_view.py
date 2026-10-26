"""Native, bounded point-cloud preview; computation always uses the full cloud."""
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QWidget


class CloudView(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.cloud=None;self.points=[];self.colors=[]
        self.setMinimumSize(180,140);self.setMouseTracking(True);self.max_points=8000;self.point_size=2
        self.yaw=-.65;self.pitch=.6;self.zoom=1;self.pan=[0,0];self.last=None
        self.setToolTip('左键旋转 · 右键平移 · 滚轮缩放 · 双击复位；预览抽样不改变计算数据')

    def set_cloud(self,cloud):
        self.cloud=cloud;self.points=[];self.colors=[]
        if cloud and cloud.get('points'):
            source=cloud['points'];limit=max(100,min(30000,int(self.max_points)));stride=max(1,math.ceil(len(source)/limit));sample=source[::stride]
            valid=[p for p in sample if len(p)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in p)]
            if valid:
                low=[min(p[i] for p in valid) for i in range(3)];high=[max(p[i] for p in valid) for i in range(3)]
                center=[(a+b)/2 for a,b in zip(low,high)];scale=max(max(b-a for a,b in zip(low,high)),1e-9)
                self.points=[[(v-center[i])/scale for i,v in enumerate(p)] for p in valid]
                self.colors=cloud.get('colors',[])[::stride] if len(valid)==len(sample) else []
        self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor('#0d2135'))
        p.setPen(QColor('#aac4d5'))
        if not self.points:p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'导入点云，或从相机采集');return
        cy,sy,cp,sp=math.cos(self.yaw),math.sin(self.yaw),math.cos(self.pitch),math.sin(self.pitch)
        scale=min(self.width(),self.height())*.7*self.zoom;points=[]
        for i,(x,y,z) in enumerate(self.points):
            xx=x*cy-y*sy;yy=x*sy+y*cy;points.append((yy*sp+z*cp,xx,yy*cp-z*sp,i))
        for depth,x,y,i in sorted(points):
            if i<len(self.colors):color=QColor.fromRgbF(*[max(0,min(1,float(v))) for v in self.colors[i]])
            else:color=QColor.fromHsvF(.55-.18*max(0,min(1,depth+.5)),.65,.95)
            p.setPen(QPen(color,max(1,min(12,float(self.point_size)))));p.drawPoint(QPointF(self.width()/2+x*scale+self.pan[0],self.height()/2-y*scale+self.pan[1]))
        p.setPen(QColor('#bdd7e5'));p.drawText(10,22,f"{len(self.cloud['points']):,} 点 · {self.cloud.get('unit','')} · 预览 {len(self.points):,} 点")
        p.drawText(10,self.height()-12,'左键旋转 / 右键平移 / 滚轮缩放 / 双击复位')

    def mousePressEvent(self,event):self.last=event.position()
    def mouseReleaseEvent(self,event):self.last=None
    def mouseMoveEvent(self,event):
        if self.last is None:return
        delta=event.position()-self.last;self.last=event.position()
        if event.buttons() & Qt.MouseButton.RightButton:self.pan[0]+=delta.x();self.pan[1]+=delta.y()
        elif event.buttons() & Qt.MouseButton.LeftButton:self.yaw+=delta.x()*.01;self.pitch=max(-1.55,min(1.55,self.pitch+delta.y()*.01))
        self.update()
    def wheelEvent(self,event):self.zoom=max(.05,min(30,self.zoom*(1.15 if event.angleDelta().y()>0 else 1/1.15)));self.update();event.accept()
    def mouseDoubleClickEvent(self,event):self.yaw=-.65;self.pitch=.6;self.zoom=1;self.pan=[0,0];self.update()
