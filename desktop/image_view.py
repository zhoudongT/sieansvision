import base64
from PySide6.QtCore import Qt, Signal, QRectF, QTimer, QPoint
from PySide6.QtGui import QPixmap, QColor, QPen, QPainter, QBrush
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QFrame, QLabel, QVBoxLayout

from desktop.theme import CANVAS, TEXT_MUTED, PANEL, LINE, TEXT


class ImageView(QGraphicsView):
    """Full-frame KeepAspectRatio image pane (全局图像 / 模块结果 / 深度图).

    fitInView while the viewport is hidden or tiny is a Qt no-op — transform
    stays ~1:1 and the user only sees a dark top strip of the frame
    (「图像只有上面一条」). Defer fit until the view is visible with a real size.
    """
    roi_changed = Signal(list)
    geom_picked = Signal(dict)  # canvas click-to-bind hit

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(QColor(CANVAS)))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumSize(230, 180)
        # Live setPixmap same-size updates must dirty the viewport (wave152).
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # Scrollbars during fitInView shrink the viewport mid-fit and leave a
        # letterboxed / top-strip look; zoom still works via Ctrl+wheel + hand drag.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.select_roi = False
        self.origin = None
        self.overlay = None
        self._geom_pick = False
        self._geom_pick_kind = 'line'
        self._geom_pickables = []
        self._geom_pick_tol = 14.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.bounds = QRectF()
        self._needs_fit = False
        self._fit_mode = 'contain'  # contain | cover | actual (Display 适应模式)
        # wave152: stable pixmap item for continuous soft preview (in-place setPixmap)
        self._live_pixmap = QPixmap()
        self._live_pixmap_item = None
        self._empty_hint = self.scene().addText('打开图像，或载入演示')
        self._empty_hint.setDefaultTextColor(QColor(TEXT_MUTED))
        # wave149: VisionMaster-style on-canvas legend chrome (annotate/display)
        self._legend_frame = None
        self._legend_label = None
        self._legend_visible = True
        self._legend_entries = []
        self._legend_bound = False
        QTimer.singleShot(0, self._ensure_legend_chrome)

    def drawBackground(self, painter, rect):
        # VisionMaster-style dark gray checkerboard when empty / around image
        painter.fillRect(rect, QColor(CANVAS))
        cell = 12
        c0 = QColor('#2a2c30')
        c1 = QColor('#34363b')
        left = int(rect.left() // cell) * cell
        top = int(rect.top() // cell) * cell
        y = top
        while y < rect.bottom() + cell:
            x = left
            row = int(y // cell)
            while x < rect.right() + cell:
                col = int(x // cell)
                painter.fillRect(QRectF(x, y, cell, cell), c0 if (row + col) % 2 == 0 else c1)
                x += cell
            y += cell

    def show_data(self, data):
        self.clear_geom_overlays()
        # keep legend visibility preference; clear bound rows until overlays rebind
        try:
            self.clear_canvas_legend()
        except Exception:
            pass
        pixmap = QPixmap()
        if data and isinstance(data, str):
            try:
                raw = data.split(',', 1)[-1]
                pixmap.loadFromData(base64.b64decode(raw, validate=False))
            except Exception:
                pixmap = QPixmap()
        if not pixmap.isNull():
            image = pixmap.toImage()
            if image.format() not in (
                image.Format.Format_RGB32,
                image.Format.Format_ARGB32,
                image.Format.Format_ARGB32_Premultiplied,
            ):
                pixmap = QPixmap.fromImage(image.convertToFormat(image.Format.Format_RGB32))
        self.scene().clear()
        self.overlay = None
        self._live_pixmap_item = None
        self._live_pixmap = QPixmap()
        self.bounds = QRectF()
        self._empty_hint = None
        if not pixmap.isNull():
            self._live_pixmap = pixmap
            self._live_pixmap_item = self.scene().addPixmap(pixmap)
            self._live_pixmap_item.setZValue(0)
            self.bounds = QRectF(pixmap.rect())
            self.scene().setSceneRect(self.bounds)
            self._needs_fit = True
            self.fit()
            # Layout / tab show often finishes after this call — refit next tick.
            QTimer.singleShot(0, self.fit)
        else:
            self._needs_fit = False
            self._empty_hint = self.scene().addText('打开图像，或载入演示')
            self._empty_hint.setDefaultTextColor(QColor(TEXT_MUTED))
            self.scene().setSceneRect(QRectF(0, 0, 400, 300))

    def show_live_frame(self, data):
        """Continuous soft/session preview: in-place setPixmap (no scene.clear flicker).

        Same-size frames update the stable pixmap item and dirty the viewport only.
        Size changes or first frame fall back to a single addPixmap + fit.
        Empty / undecodable data is ignored (keeps last good frame).
        """
        if not data or not isinstance(data, str):
            return False
        pixmap = QPixmap()
        try:
            raw = data.split(',', 1)[-1]
            if not pixmap.loadFromData(base64.b64decode(raw, validate=False)):
                return False
        except Exception:
            return False
        image = pixmap.toImage()
        if image.format() not in (
            image.Format.Format_RGB32,
            image.Format.Format_ARGB32,
            image.Format.Format_ARGB32_Premultiplied,
        ):
            pixmap = QPixmap.fromImage(image.convertToFormat(image.Format.Format_RGB32))
        return self._set_live_pixmap(pixmap)

    def _set_live_pixmap(self, pixmap: QPixmap, *, refit: bool | None = None) -> bool:
        if pixmap.isNull():
            return False
        size_changed = self._live_pixmap.isNull() or pixmap.size() != self._live_pixmap.size()
        self._live_pixmap = pixmap
        if self._live_pixmap_item is None:
            # Drop empty-hint / stale scene once, then keep a stable item.
            self.clear_geom_overlays()
            self.scene().clear()
            self.overlay = None
            self._empty_hint = None
            self._live_pixmap_item = self.scene().addPixmap(pixmap)
            self._live_pixmap_item.setZValue(0)
            self.bounds = QRectF(pixmap.rect())
            self.scene().setSceneRect(self.bounds)
            self._needs_fit = True
            self.fit()
            QTimer.singleShot(0, self._fit_if_needed)
            QTimer.singleShot(50, self._fit_if_needed)
            QTimer.singleShot(200, self._fit_if_needed)
            return True
        self._live_pixmap_item.setPixmap(pixmap)
        if refit is True or (refit is None and size_changed):
            self.bounds = QRectF(pixmap.rect())
            self.scene().setSceneRect(self.bounds)
            self._needs_fit = True
            self.fit()
            QTimer.singleShot(50, self._fit_if_needed)
            QTimer.singleShot(200, self._fit_if_needed)
        else:
            self.viewport().update()
            if self._needs_fit or self._transform_looks_like_strip():
                self.fit()
            elif self.isVisible():
                # Periodic heal: live path used to skip fit on same-size frames forever
                # after a bad first fitInView → permanent 一条线.
                now = getattr(self, '_last_live_fit_check', 0.0)
                import time as _time
                tnow = _time.monotonic()
                if tnow - now > 1.0:
                    self._last_live_fit_check = tnow
                    if self._transform_looks_like_strip():
                        self._needs_fit = True
                        self.fit()
        return True

    def set_roi_mode(self, enabled):
        self.select_roi = enabled
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag if enabled else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def show_roi(self, roi):
        if self.overlay:
            self.scene().removeItem(self.overlay)
            self.overlay = None
        if isinstance(roi, list) and len(roi) == 4 and all(isinstance(x, (int, float)) for x in roi):
            pen = QPen(QColor('#e67a2e'), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.overlay = self.scene().addRect(QRectF(*roi), pen)
            self.overlay.setZValue(10)

    def set_fit_mode(self, mode):
        """Display fitMode → 模块结果 pane: contain | cover | actual."""
        mode = mode if mode in ('contain', 'cover', 'actual') else 'contain'
        self._fit_mode = mode
        if not self.bounds.isEmpty():
            self.fit()

    def _viewport_ready_for_fit(self) -> bool:
        """Avoid fitInView while the pane is still a few pixels tall (→ 一条线)."""
        if not self.isVisible():
            return False
        vw = self.viewport().width()
        vh = self.viewport().height()
        # 8px was too low: 1280×1024 fit into ~400×10 collapses to a hairline strip.
        return vw >= 64 and vh >= 64

    def _transform_looks_like_strip(self) -> bool:
        """True when current transform would paint a full frame as a thin band."""
        if self.bounds.isEmpty() or self._live_pixmap.isNull():
            return False
        vh = max(1, self.viewport().height())
        vw = max(1, self.viewport().width())
        bh = max(1.0, float(self.bounds.height()))
        bw = max(1.0, float(self.bounds.width()))
        # After KeepAspectRatio fit, displayed height should be min(vh, vw*bh/bw)
        m11 = abs(float(self.transform().m11()))
        m22 = abs(float(self.transform().m22()))
        if m11 < 1e-6 or m22 < 1e-6:
            return True
        disp_h = bh * m22
        disp_w = bw * m11
        # Hairline: image taller than 64px but draws under ~24px, while viewport is roomy
        if bh >= 64 and vh >= 64 and disp_h < 24:
            return True
        if bw >= 64 and vw >= 64 and disp_w < 24:
            return True
        return False

    def fit(self):
        """Fit per _fit_mode. Defer when hidden / viewport still tiny."""
        if self.bounds.isEmpty():
            self._needs_fit = False
            return
        if not self._viewport_ready_for_fit():
            self._needs_fit = True
            # Retry after layout settles (tab switch / first live frame).
            QTimer.singleShot(50, self._fit_if_needed)
            QTimer.singleShot(200, self._fit_if_needed)
            return
        mode = getattr(self, '_fit_mode', 'contain') or 'contain'
        if mode == 'actual':
            self.resetTransform()
            # Center on image
            self.centerOn(self.bounds.center())
            self._needs_fit = False
            self.viewport().update()
            return
        h_policy = self.horizontalScrollBarPolicy()
        v_policy = self.verticalScrollBarPolicy()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vw = float(max(1, self.viewport().width()))
        vh = float(max(1, self.viewport().height()))
        bw = float(max(1.0, self.bounds.width()))
        bh = float(max(1.0, self.bounds.height()))
        if mode == 'cover':
            scale = max(vw / bw, vh / bh)
        else:
            scale = min(vw / bw, vh / bh)
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(self.bounds.center())
        self.setHorizontalScrollBarPolicy(h_policy)
        self.setVerticalScrollBarPolicy(v_policy)
        # Layout race: keep retrying instead of clearing the flag while still a strip.
        if self._transform_looks_like_strip():
            self._needs_fit = True
            QTimer.singleShot(50, self._fit_if_needed)
            QTimer.singleShot(200, self._fit_if_needed)
        else:
            self._needs_fit = False
        self.viewport().update()

    def _fit_if_needed(self):
        if self._needs_fit or self._transform_looks_like_strip():
            self.fit()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.bounds.isEmpty():
            QTimer.singleShot(0, self.fit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.bounds.isEmpty():
            self.fit()
        try:
            self._position_legend_chrome()
        except Exception:
            pass

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            scale = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
            if .01 < self.transform().m11() * scale < 40:
                self.scale(scale, scale)
        else:
            super().wheelEvent(event)


    # —— wave149 on-canvas legend chrome ————————————————

    def _ensure_legend_chrome(self):
        """Lazy-create floating industrial-dark legend on the viewport."""
        if self._legend_frame is not None:
            return self._legend_frame
        frame = QFrame(self.viewport())
        frame.setObjectName('canvasLegendChrome')
        frame.setStyleSheet(
            f'QFrame#canvasLegendChrome {{'
            f'  background-color: rgba(26,27,29,210);'
            f'  border: 1px solid {LINE};'
            f'  border-radius: 2px;'
            f'}}'
            f'QLabel#canvasLegendBody {{'
            f'  background: transparent; color: {TEXT}; padding: 4px 6px;'
            f'}}'
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lab = QLabel(frame)
        lab.setObjectName('canvasLegendBody')
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        lay.addWidget(lab)
        frame.hide()
        self._legend_frame = frame
        self._legend_label = lab
        return frame

    def legend_visible(self) -> bool:
        return bool(getattr(self, '_legend_visible', True))

    def set_legend_visible(self, visible: bool):
        self._legend_visible = bool(visible)
        self._refresh_legend_chrome()

    def toggle_legend(self) -> bool:
        self.set_legend_visible(not self.legend_visible())
        return self.legend_visible()

    def canvas_legend_entries(self) -> list:
        return list(getattr(self, '_legend_entries', None) or [])

    def set_canvas_legend(self, entries=None):
        """Push explicit legend rows (list of dicts from canvas_legend_chrome)."""
        self._legend_entries = [e for e in (entries or []) if isinstance(e, dict)]
        self._legend_bound = bool(self._legend_entries)
        self._refresh_legend_chrome()

    def bind_legend_from_specs(self, specs=None, *, judge_ok=None, show_roi: bool = True):
        """Infer + show legend from overlay specs (annotate/display path)."""
        try:
            from desktop.canvas_legend_chrome import entries_from_overlay_specs
            entries = entries_from_overlay_specs(
                specs, judge_ok=judge_ok, show_roi=show_roi)
        except Exception:
            entries = []
        self.set_canvas_legend(entries)
        return entries

    def clear_canvas_legend(self):
        self._legend_entries = []
        self._legend_bound = False
        self._refresh_legend_chrome()

    def _refresh_legend_chrome(self):
        frame = self._ensure_legend_chrome()
        lab = self._legend_label
        entries = list(getattr(self, '_legend_entries', None) or [])
        show = bool(getattr(self, '_legend_visible', True)) and bool(entries)
        if not show:
            frame.hide()
            return
        try:
            from desktop.canvas_legend_chrome import html_legend_block
            lab.setText(html_legend_block(entries))
        except Exception:
            bits = ' · '.join(
                f"{e.get('label') or e.get('key')}" for e in entries)
            lab.setText(f'图例\n{bits}' if bits else '图例')
        frame.adjustSize()
        self._position_legend_chrome()
        frame.show()
        frame.raise_()

    def _position_legend_chrome(self):
        frame = getattr(self, '_legend_frame', None)
        if frame is None:
            return
        margin = 8
        vp = self.viewport()
        frame.adjustSize()
        # Bottom-left — VisionMaster-style compact key, clear of top chrome.
        x = margin
        y = max(margin, vp.height() - frame.height() - margin)
        frame.move(QPoint(x, y))

    
    def clear_geom_overlays(self):
        """Remove measure/locate canvas overlays (product-visible draw path)."""
        for item in getattr(self, '_geom_items', []) or []:
            try:
                self.scene().removeItem(item)
            except Exception:
                pass
        self._geom_items = []

    def set_geom_overlays(self, specs):
        """Draw vector overlays on top of the current image.

        specs: list of dicts:
          {'type':'line','x1','y1','x2','y2','color'?}
          {'type':'point','x','y','color'?}
          {'type':'label','x','y','text','color'?}
          {'type':'rect','x','y','w','h','color'?}
          {'type':'ellipse','x','y','rx','ry','color'?}  # center + radii
          {'type':'circle','x','y','r','color'?}
          {'type':'cross','x','y','size'?, 'color'?}
          {'type':'polygon','points':[[x,y],...],'color'?}
        """
        from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsSimpleTextItem, QGraphicsRectItem, QGraphicsPolygonItem
        from PySide6.QtGui import QFont
        self.clear_geom_overlays()
        items = []
        for spec in specs or []:
            if not isinstance(spec, dict):
                continue
            kind = spec.get('type')
            color = QColor(spec.get('color') or '#00d250')
            try:
                w = float(spec.get('width') or 2)
            except Exception:
                w = 2.0
            pen = QPen(color, max(1.0, w))
            pen.setCosmetic(True)
            if kind == 'line':
                item = QGraphicsLineItem(float(spec['x1']), float(spec['y1']), float(spec['x2']), float(spec['y2']))
                item.setPen(pen); item.setZValue(20); items.append(item); self.scene().addItem(item)
            elif kind == 'point':
                r = float(spec.get('r') or 4)
                x, y = float(spec['x']), float(spec['y'])
                item = QGraphicsEllipseItem(x - r, y - r, r * 2, r * 2)
                item.setPen(pen); item.setBrush(QBrush(color)); item.setZValue(21)
                items.append(item); self.scene().addItem(item)
            elif kind == 'label':
                item = QGraphicsSimpleTextItem(str(spec.get('text') or ''))
                item.setBrush(QBrush(color))
                item.setFont(QFont('Sans', 10))
                item.setPos(float(spec.get('x') or 0), float(spec.get('y') or 0))
                item.setZValue(22); items.append(item); self.scene().addItem(item)
            elif kind == 'rect':
                item = QGraphicsRectItem(float(spec['x']), float(spec['y']), float(spec['w']), float(spec['h']))
                item.setPen(pen); item.setZValue(19); items.append(item); self.scene().addItem(item)
            elif kind == 'ellipse':
                cx, cy = float(spec['x']), float(spec['y'])
                rx = float(spec.get('rx') or spec.get('r') or 8)
                ry = float(spec.get('ry') or rx)
                item = QGraphicsEllipseItem(cx - rx, cy - ry, rx * 2, ry * 2)
                item.setPen(pen); item.setZValue(19); items.append(item); self.scene().addItem(item)
            elif kind == 'circle':
                cx, cy = float(spec['x']), float(spec['y'])
                r = float(spec.get('r') or spec.get('rx') or 8)
                item = QGraphicsEllipseItem(cx - r, cy - r, r * 2, r * 2)
                item.setPen(pen); item.setZValue(19); items.append(item); self.scene().addItem(item)
            elif kind == 'cross':
                cx, cy = float(spec['x']), float(spec['y'])
                sz = float(spec.get('size') or 8)
                h = QGraphicsLineItem(cx - sz, cy, cx + sz, cy)
                v = QGraphicsLineItem(cx, cy - sz, cx, cy + sz)
                h.setPen(pen); v.setPen(pen)
                h.setZValue(21); v.setZValue(21)
                items.append(h); items.append(v)
                self.scene().addItem(h); self.scene().addItem(v)
            elif kind == 'polygon':
                from PySide6.QtCore import QPointF
                from PySide6.QtGui import QPolygonF, QBrush as _QB
                pts = spec.get('points') or []
                poly = QPolygonF()
                for p in pts:
                    if isinstance(p, (list, tuple)) and len(p) >= 2:
                        poly.append(QPointF(float(p[0]), float(p[1])))
                if poly.count() >= 2:
                    item = QGraphicsPolygonItem(poly)
                    item.setPen(pen)
                    # hollow fill — industrial outline
                    item.setBrush(_QB(Qt.BrushStyle.NoBrush))
                    item.setZValue(19); items.append(item); self.scene().addItem(item)
        self._geom_items = items

    def set_geom_pick_mode(self, enabled, kind='line', pickables=None, tol=14.0):
        """Enable click-to-bind: left-click nearest line/point pickable."""
        self._geom_pick = bool(enabled)
        self._geom_pick_kind = kind or 'line'
        self._geom_pickables = list(pickables or [])
        self._geom_pick_tol = float(tol or 14.0)
        if self._geom_pick:
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            # preview candidates
            try:
                from desktop.geom_canvas_pick import overlay_specs_for_pickables
                specs = overlay_specs_for_pickables(self._geom_pickables)
                if specs:
                    self.set_geom_overlays(specs)
            except Exception:
                pass
        else:
            self.unsetCursor()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def geom_pick_active(self):
        return bool(getattr(self, '_geom_pick', False))


    def keyPressEvent(self, event):
        if getattr(self, '_geom_pick', False) and event.key() == Qt.Key.Key_Escape:
            cancel = getattr(self, '_geom_pick_cancel', None)
            if callable(cancel):
                cancel()
            event.accept()
            return
        super().keyPressEvent(event)


    def mousePressEvent(self, event):
        if getattr(self, '_geom_pick', False) and event.button() == Qt.MouseButton.RightButton:
            cancel = getattr(self, '_geom_pick_cancel', None)
            if callable(cancel):
                cancel()
            event.accept()
            return
        if getattr(self, '_geom_pick', False) and event.button() == Qt.MouseButton.LeftButton:
            pt = self.mapToScene(event.position().toPoint())
            try:
                from desktop.geom_canvas_pick import hit_test
                hit = hit_test(self._geom_pickables, float(pt.x()), float(pt.y()),
                               kind=self._geom_pick_kind, tol=self._geom_pick_tol)
            except Exception:
                hit = None
            if hit:
                self.geom_picked.emit(hit)
                event.accept()
                return
            # miss: still accept so user knows pick mode is on
            event.accept()
            return
        if self.select_roi and event.button() == Qt.MouseButton.LeftButton and not self.bounds.isEmpty():
            self.origin = self.mapToScene(event.position().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            rect = QRectF(self.origin, self.mapToScene(event.position().toPoint())).normalized().intersected(self.bounds)
            self.show_roi([rect.x(), rect.y(), rect.width(), rect.height()])
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            rect = QRectF(self.origin, self.mapToScene(event.position().toPoint())).normalized().intersected(self.bounds).toAlignedRect()
            self.origin = None
            if rect.width() >= 2 and rect.height() >= 2:
                self.roi_changed.emit([rect.x(), rect.y(), rect.width(), rect.height()])
            event.accept()
        else:
            super().mouseReleaseEvent(event)
