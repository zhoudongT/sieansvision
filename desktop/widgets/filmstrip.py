"""Local-image filmstrip under the image viewport (VisionMaster 胶片条)."""
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, Signal, QSize, QTimer, QEvent, QPoint
from PySide6.QtGui import QIcon, QPixmap, QImage, QAction
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileDialog, QMessageBox, QComboBox,
    QScrollArea, QFrame, QToolTip, QMenu,
)

from .switch import OrangeSwitch
try:
    from desktop.theme import CANVAS, BG
except Exception:  # pragma: no cover
    CANVAS, BG = '#2d2f33', '#2a2c30'

IMAGE_FILTER = '图像文件 (*.bmp *.jpeg *.jpg *.png *.tif *.tiff);;所有文件 (*)'
IMAGE_EXTS = {'.bmp', '.jpeg', '.jpg', '.png', '.tif', '.tiff'}


class FilmstripBar(QWidget):
    """图像源 (n/N) | 自动切换 | 运行全部 | + 文件夹 🗑 + horizontal thumbs."""
    imageSelected = Signal(str)          # data-url or file path load request via path
    pathSelected = Signal(str)           # absolute path
    autoSwitchChanged = Signal(bool)
    stopAtLastChanged = Signal(bool)
    runAllRequested = Signal()
    continuousPauseToggled = Signal(bool)  # True=paused
    listChanged = Signal(list)           # paths
    formatFilterChanged = Signal(str)    # 全部|.bmp|.jpg|.png|.tif
    thumbHovered = Signal(str)           # 细妆⑯：悬停缩略路径（空=离开）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('filmstripBar')
        self._paths = []
        self._index = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.count_label = QLabel('图像源 (0/0)')
        self.count_label.setObjectName('filmstripCount')
        bar.addWidget(self.count_label)
        bar.addWidget(QLabel('自动切换'))
        self.auto_switch = OrangeSwitch(False)
        self.auto_switch.toggled.connect(self.autoSwitchChanged.emit)
        bar.addWidget(self.auto_switch)
        bar.addWidget(QLabel('最后一张停止'))
        self.stop_at_last = OrangeSwitch(False)
        self.stop_at_last.toggled.connect(self.stopAtLastChanged.emit)
        bar.addWidget(self.stop_at_last)
        self.run_all = QPushButton('运行全部')
        self.run_all.setObjectName('filmstripRun')
        self.run_all.clicked.connect(self.runAllRequested.emit)
        bar.addWidget(self.run_all)
        self.pause_btn = QPushButton('⏸ 暂停')
        self.pause_btn.setObjectName('filmstripPause')
        self.pause_btn.setCheckable(True)
        self._pause_owner = None  # 'continuous' | 'run_all' | None — single control owns both
        self.pause_btn.setToolTip(
            '连续运行 / 运行全部共用：暂停/继续切图调度（可中途改间隔）'
        )
        self.pause_btn.setEnabled(False)
        self.pause_btn.toggled.connect(self._on_pause_toggled)
        bar.addWidget(self.pause_btn)
        bar.addStretch(1)
        self.add_btn = QPushButton('+')
        self.add_btn.setToolTip('添加图像')
        self.add_btn.setFixedWidth(32)
        self.add_btn.clicked.connect(self.add_images)
        bar.addWidget(self.add_btn)
        self.folder_btn = QPushButton('📁')
        self.folder_btn.setToolTip('添加图像文件夹')
        self.folder_btn.setFixedWidth(32)
        self.folder_btn.clicked.connect(self.add_folder)
        bar.addWidget(self.folder_btn)
        self.del_btn = QPushButton('🗑')
        self.del_btn.setToolTip('删除选中')
        self.del_btn.setFixedWidth(32)
        self.del_btn.clicked.connect(self.remove_selected)
        bar.addWidget(self.del_btn)
        self.clear_btn = QPushButton('清空')
        self.clear_btn.setToolTip('清空全部本地图')
        self.clear_btn.clicked.connect(self.clear_all)
        bar.addWidget(self.clear_btn)
        bar.addWidget(QLabel('格式'))
        self.format_filter = QComboBox()
        self.format_filter.setObjectName('filmstripFormatFilter')
        self.format_filter.setToolTip('本地图像格式过滤（与属性/导入一致）')
        self.format_filter.addItem('全部', '全部')
        self.format_filter.addItem('BMP', '.bmp')
        self.format_filter.addItem('JPEG', '.jpg')
        self.format_filter.addItem('PNG', '.png')
        self.format_filter.addItem('TIFF', '.tif')
        self.format_filter.setFixedWidth(72)
        self.format_filter.currentIndexChanged.connect(self._on_format_filter_changed)
        bar.addWidget(self.format_filter)
        self._format_filter_key = '全部'
        bar.addWidget(QLabel('缩略'))
        self.thumb_size = QComboBox()
        self.thumb_size.setObjectName('filmstripThumbSize')
        self.thumb_size.setToolTip('胶片条缩略图尺寸（属性级）')
        for lab, px in (('小', 48), ('中', 72), ('大', 96)):
            self.thumb_size.addItem(lab, px)
        self.thumb_size.setCurrentIndex(1)
        self.thumb_size.setFixedWidth(52)
        self.thumb_size.currentIndexChanged.connect(self._on_thumb_size_changed)
        bar.addWidget(self.thumb_size)
        self._thumb_px = 72
        self.interval_label = QLabel('')
        self.interval_label.setObjectName('filmstripInterval')
        self.interval_label.setStyleSheet('color:#888;font-size:11px;')
        bar.addWidget(self.interval_label)
        root.addLayout(bar)
        self.thumbs = QListWidget()
        self.thumbs.setObjectName('filmstripThumbs')
        self.thumbs.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbs.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbs.setWrapping(False)
        self.thumbs.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbs.setMovement(QListWidget.Movement.Static)
        self.thumbs.setIconSize(QSize(72, 54))
        self.thumbs.setGridSize(QSize(88, 78))
        self.thumbs.setFixedHeight(86)
        self.thumbs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thumbs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumbs.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.thumbs.currentRowChanged.connect(self._row_changed)
        # 细妆⑯：缩略悬停 → 几何预览 / 多帧对比
        self.thumbs.setMouseTracking(True)
        self.thumbs.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        try:
            self.thumbs.itemEntered.connect(self._on_thumb_entered)
        except Exception:
            pass
        self.thumbs.viewport().setMouseTracking(True)
        self._hover_path = ''
        self.thumbs.viewport().installEventFilter(self)
        root.addWidget(self.thumbs)
        self.empty_hint = QLabel('未添加图像 — 点 + 或 📁 导入；本地模式下节点会显示红叹号直至添加。')
        self.empty_hint.setObjectName('filmstripEmpty')
        self.empty_hint.setStyleSheet('color:#c62828;font-size:11px;padding:0 2px;')
        self.empty_hint.setWordWrap(True)
        root.addWidget(self.empty_hint)
        self.set_paths([], 0)
        self._live_fit_mode = 'contain'
        self._actual_letterbox = True  # pad with theme CANVAS when src < thumb
        self._actual_pad_color = None  # None → theme CANVAS
        self._live_src_pixmap = None  # last pre-fit src for pad-only refresh


    def _on_thumb_entered(self, item):
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole) or ''
        if not path:
            # fallback: match by row
            row = self.thumbs.row(item)
            if 0 <= row < len(self._paths):
                path = self._paths[row]
        self._emit_hover(path)

    def _emit_hover(self, path: str):
        path = path or ''
        if path == getattr(self, '_hover_path', None):
            return
        self._hover_path = path
        try:
            self.thumbHovered.emit(path)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            from PySide6.QtCore import QEvent
            if obj is self.thumbs.viewport():
                et = event.type()
                if et == QEvent.Type.MouseMove:
                    pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
                    item = self.thumbs.itemAt(pos)
                    if item is None:
                        self._emit_hover('')
                    else:
                        self._on_thumb_entered(item)
                elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                    self._emit_hover('')
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def paths(self):
        return list(self._paths)

    def current_index(self):
        return self._index

    def current_path(self):
        if 0 <= self._index < len(self._paths):
            return self._paths[self._index]
        return ''

    def select_index(self, index, *, emit=True):
        """细妆⑳：按序号定位缩略并滚入视口（结果表 ↔ 胶片）。"""
        if not self._paths:
            return False
        try:
            index = int(index)
        except Exception:
            return False
        if index < 0 or index >= len(self._paths):
            return False
        self._index = index
        try:
            self.thumbs.blockSignals(True)
            self.thumbs.setCurrentRow(index)
            item = self.thumbs.item(index)
            if item is not None:
                self.thumbs.scrollToItem(item)
            self.thumbs.blockSignals(False)
        except Exception:
            try:
                self.thumbs.blockSignals(False)
            except Exception:
                pass
            return False
        self._refresh_count()
        if emit:
            try:
                self.pathSelected.emit(self._paths[index])
            except Exception:
                pass
        return True

    def select_path(self, path, *, emit=True):
        """细妆⑳：按路径定位缩略（规范化比对）；找不到返回 False。"""
        path = str(path or '').strip()
        if not path or not self._paths:
            return False
        try:
            target = str(Path(path).resolve())
        except Exception:
            target = path
        hit = -1
        for i, pth in enumerate(self._paths):
            try:
                if str(Path(pth).resolve()) == target or pth == path or pth == target:
                    hit = i
                    break
            except Exception:
                if pth == path:
                    hit = i
                    break
        if hit < 0:
            # basename fallback when only filename stamped
            base = Path(path).name
            for i, pth in enumerate(self._paths):
                if Path(pth).name == base:
                    hit = i
                    break
        if hit < 0:
            return False
        return self.select_index(hit, emit=emit)

    def _exts_for_filter(self, key=None):
        key = key if key is not None else getattr(self, '_format_filter_key', '全部')
        if key in (None, '', '全部'):
            return set(IMAGE_EXTS)
        if key == '.jpg':
            return {'.jpg', '.jpeg'}
        if key == '.tif':
            return {'.tif', '.tiff'}
        return {key}

    def _on_format_filter_changed(self, *_):
        key = self.format_filter.currentData()
        self._format_filter_key = key or '全部'
        self._apply_format_filter_visibility()
        tip = '本地图像格式过滤：' + (
            ', '.join(sorted(self._exts_for_filter())) if self._format_filter_key != '全部'
            else ', '.join(sorted(IMAGE_EXTS))
        )
        self.set_format_filter_hint(tip)
        self.formatFilterChanged.emit(str(self._format_filter_key))

    def set_format_filter(self, key='全部'):
        """属性面板 / 外部同步格式过滤。"""
        key = key or '全部'
        combo = getattr(self, 'format_filter', None)
        if combo is None:
            self._format_filter_key = key
            return
        idx = combo.findData(key)
        if idx < 0 and key in ('.jpeg',):
            idx = combo.findData('.jpg')
        if idx < 0 and key in ('.tiff',):
            idx = combo.findData('.tif')
        if idx < 0:
            idx = 0
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        self._format_filter_key = combo.currentData() or '全部'
        self._apply_format_filter_visibility()

    def _apply_format_filter_visibility(self):
        """Hide thumbs whose suffix is outside current format filter (paths kept)."""
        allowed = self._exts_for_filter()
        for i in range(self.thumbs.count()):
            item = self.thumbs.item(i)
            if item is None:
                continue
            path = item.data(Qt.ItemDataRole.UserRole) or ''
            suf = Path(str(path)).suffix.lower()
            show = (self._format_filter_key == '全部') or (suf in allowed)
            item.setHidden(not show)
        # Recount visible
        n = len(self._paths)
        vis = sum(1 for i in range(self.thumbs.count()) if not self.thumbs.item(i).isHidden())
        cur = (self._index + 1) if n else 0
        if self._format_filter_key != '全部':
            self.count_label.setText(f'图像源 ({cur}/{n} · 显{vis})')
        else:
            self.count_label.setText(f'图像源 ({cur}/{n})')

    def set_format_filter_hint(self, text=''):
        """细妆：胶片条格式过滤提示（ToolTip；不污染取图间隔文案）。"""
        tip = text or ('本地图像格式过滤：' + ', '.join(sorted(IMAGE_EXTS)))
        if hasattr(self, 'interval_label') and self.interval_label is not None:
            base = self.interval_label.toolTip() or ''
            if '格式' not in base:
                self.interval_label.setToolTip((base + chr(10) + tip).strip() if base else tip)
        if hasattr(self, 'empty_hint') and self.empty_hint is not None:
            msg = self.empty_hint.toolTip() or ''
            if '格式' not in msg:
                self.empty_hint.setToolTip(tip)

    def set_auto_switch(self, enabled):
        self.auto_switch.setChecked(bool(enabled), animate=False)

    def set_stop_at_last(self, enabled):
        self.stop_at_last.setChecked(bool(enabled), animate=False)

    def set_paths(self, paths, index=0, root=None):
        resolved = []
        for p in paths:
            s = str(p)
            pp = Path(s)
            if not pp.is_file() and not pp.is_absolute() and root:
                cand = Path(root) / s
                if cand.is_file():
                    s = str(cand.resolve())
                    pp = Path(s)
            elif pp.is_file():
                try:
                    s = str(pp.resolve())
                except Exception:
                    pass
            resolved.append(s)
        self._paths = resolved
        self._index = max(0, min(index, max(0, len(self._paths) - 1)))
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for path in self._paths:
            pp = Path(path)
            missing = not pp.is_file()
            item = QListWidgetItem(pp.name + (' ⚠' if missing else ''))
            pix = QPixmap(path) if not missing else QPixmap()
            if not pix.isNull():
                item.setIcon(QIcon(pix.scaled(72, 54, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(('缺失文件：' if missing else '') + path)
            if missing:
                item.setForeground(Qt.GlobalColor.red)
            self.thumbs.addItem(item)
        if self._paths:
            self.thumbs.setCurrentRow(self._index)
        self.thumbs.blockSignals(False)
        self._refresh_count()
        if hasattr(self, 'empty_hint'):
            self.empty_hint.setVisible(len(self._paths) == 0)
            self.thumbs.setVisible(len(self._paths) > 0)
        self.set_format_filter_hint()
        if hasattr(self, '_apply_format_filter_visibility'):
            self._apply_format_filter_visibility()

    def _refresh_count(self):
        n = len(self._paths)
        cur = (self._index + 1) if n else 0
        key = getattr(self, '_format_filter_key', '全部')
        if key != '全部' and hasattr(self, 'thumbs'):
            vis = sum(
                1 for i in range(self.thumbs.count())
                if self.thumbs.item(i) is not None and not self.thumbs.item(i).isHidden()
            )
            self.count_label.setText(f'图像源 ({cur}/{n} · 显{vis})')
        else:
            self.count_label.setText(f'图像源 ({cur}/{n})')

    def _row_changed(self, row):
        if row < 0 or row >= len(self._paths):
            return
        self._index = row
        self._refresh_count()
        self.pathSelected.emit(self._paths[row])

    def add_images(self):
        names, _ = QFileDialog.getOpenFileNames(self, '添加图像', '', IMAGE_FILTER)
        if not names:
            return
        self._append(names)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '添加图像文件夹')
        if not folder:
            return
        allowed = self._exts_for_filter() if hasattr(self, '_exts_for_filter') else IMAGE_EXTS
        paths = []
        for path in sorted(Path(folder).iterdir()):
            if path.is_file() and path.suffix.lower() in allowed:
                paths.append(str(path))
        if not paths:
            QMessageBox.information(self, '添加图像文件夹', '文件夹内没有可导入的图像格式。')
            return
        self._append(paths)

    def _append(self, names):
        added = 0
        for name in names:
            path = str(Path(name).resolve())
            if path in self._paths:
                continue
            if Path(path).suffix.lower() not in IMAGE_EXTS:
                continue
            img = QImage(path)
            if img.isNull():
                continue
            self._paths.append(path)
            added += 1
        if not added:
            return
        self.set_paths(self._paths, len(self._paths) - 1)
        self.listChanged.emit(self.paths())
        if self._paths:
            self.pathSelected.emit(self.current_path())

    def remove_selected(self):
        row = self.thumbs.currentRow()
        if row < 0 or row >= len(self._paths):
            return
        del self._paths[row]
        index = min(row, max(0, len(self._paths) - 1))
        self.set_paths(self._paths, index)
        self.listChanged.emit(self.paths())
        if self._paths:
            self.pathSelected.emit(self.current_path())

    def set_run_all_enabled(self, enabled, reason=''):
        """Soft-disable 运行全部 (e.g. camera/SDK mode) without hiding the bar."""
        on = bool(enabled)
        if hasattr(self, 'run_all'):
            self.run_all.setEnabled(on)
            tip = (reason or '').strip() or (
                '' if on else '当前图像源非本地 — 运行全部仅用于胶片条图集'
            )
            self.run_all.setToolTip(tip)


    def _on_pause_toggled(self, on):
        self.pause_btn.setText('▶ 继续' if on else '⏸ 暂停')
        self.continuousPauseToggled.emit(bool(on))

    def set_continuous_paused(self, paused):
        """Sync UI from MainWindow pause/resume/stop without re-emitting."""
        if not hasattr(self, 'pause_btn'):
            return
        paused = bool(paused)
        self.pause_btn.blockSignals(True)
        self.pause_btn.setChecked(paused)
        self.pause_btn.setText('▶ 继续' if paused else '⏸ 暂停')
        self.pause_btn.blockSignals(False)
        # Enable pause control whenever continuous UI is relevant (caller enables)
        self.pause_btn.setEnabled(True)

    def set_continuous_controls_enabled(self, enabled):
        if hasattr(self, 'pause_btn'):
            self.pause_btn.setEnabled(bool(enabled))
            if not enabled:
                self.pause_btn.blockSignals(True)
                self.pause_btn.setChecked(False)
                self.pause_btn.setText('⏸ 暂停')
                self.pause_btn.blockSignals(False)
                if getattr(self, '_pause_owner', None) is not None and not enabled:
                    # leave owner until set_pause_owner(None) from host stop; tip stays dual-mode
                    pass

    def set_interval_hint(self, ms):
        """Show 取图间隔 from sourceConfig (0 → hide)."""
        try:
            ms = int(ms or 0)
        except Exception:
            ms = 0
        if not hasattr(self, 'interval_label'):
            return
        if ms > 0:
            self.interval_label.setText(f'间隔 {ms} ms')
            self.interval_label.setVisible(True)
        else:
            self.interval_label.setText('')
            self.interval_label.setVisible(False)


    def set_pause_owner(self, mode):
        """Single pause control owns ContinuousRun and 运行全部 (mutual exclusive modes)."""
        mode = mode if mode in ('continuous', 'run_all') else None
        self._pause_owner = mode
        if not hasattr(self, 'pause_btn'):
            return
        if mode == 'run_all':
            tip = '运行全部（与连续运行共用同一暂停控件）：暂停/继续切图调度'
        elif mode == 'continuous':
            tip = '连续运行（与运行全部共用同一暂停控件）：暂停/继续调度（可改间隔）'
        else:
            tip = '连续运行 / 运行全部共用：暂停/继续切图调度（可中途改间隔）'
        self.pause_btn.setToolTip(tip)

    def _fit_pixmap_to_thumb(self, pix, fit_mode=None):
        """Scale/crop pixmap to iconSize honoring Display fitMode: contain|cover|actual."""
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QRect, QPoint
        size = self.thumbs.iconSize() if hasattr(self, 'thumbs') else QSize(72, 54)
        tw, th = size.width(), size.height()
        if tw < 1 or th < 1 or pix is None or pix.isNull():
            return pix
        mode = fit_mode if fit_mode in ('contain', 'cover', 'actual') else getattr(self, '_live_fit_mode', 'contain')
        mode = mode if mode in ('contain', 'cover', 'actual') else 'contain'
        if mode == 'contain':
            return pix.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        if mode == 'actual':
            # 1:1 center-crop; when src smaller than thumb → letterbox with theme pad
            from PySide6.QtGui import QColor
            src = pix
            letterbox = bool(getattr(self, '_actual_letterbox', True))
            pad = getattr(self, '_actual_pad_color', None)
            if pad is None:
                try:
                    pad = QColor(CANVAS)
                except Exception:
                    pad = QColor('#2d2f33')
            elif not isinstance(pad, QColor):
                pad = QColor(str(pad))
            if letterbox and (src.width() < tw or src.height() < th):
                out = QPixmap(size)
                out.fill(pad)
                p = QPainter(out)
                x = max(0, (tw - src.width()) // 2)
                y = max(0, (th - src.height()) // 2)
                # clip if one dim still larger
                sw = min(src.width(), tw)
                sh = min(src.height(), th)
                sx = max(0, (src.width() - sw) // 2)
                sy = max(0, (src.height() - sh) // 2)
                p.drawPixmap(x, y, src, sx, sy, sw, sh)
                p.end()
                return out
            if src.width() < tw or src.height() < th:
                # letterbox disabled → transparent pad (legacy)
                out = QPixmap(size)
                out.fill(Qt.GlobalColor.transparent)
                p = QPainter(out)
                x = max(0, (tw - src.width()) // 2)
                y = max(0, (th - src.height()) // 2)
                p.drawPixmap(x, y, src)
                p.end()
                return out
            x = max(0, (src.width() - tw) // 2)
            y = max(0, (src.height() - th) // 2)
            return src.copy(x, y, tw, th)
        # cover: expand then center-crop
        scaled = pix.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - tw) // 2)
        y = max(0, (scaled.height() - th) // 2)
        return scaled.copy(x, y, tw, th)

    def set_actual_pad_color(self, color, *, refresh=True):
        """Override actual-mode letterbox pad (theme / Display channel). None → CANVAS.

        When refresh=True, re-fit current live thumb so channel-only Display edits
        update pad without a new frame.
        """
        from PySide6.QtGui import QColor
        if color is None or color == '':
            self._actual_pad_color = None
        elif isinstance(color, QColor):
            self._actual_pad_color = QColor(color)
        else:
            self._actual_pad_color = QColor(str(color))
        if refresh:
            try:
                self.refresh_live_thumb_fit()
            except Exception:
                pass

    def set_live_fit_mode(self, fit_mode, *, refresh=True):
        """Change Display fitMode on live thumb; optionally re-fit without new frame."""
        if fit_mode in ('contain', 'cover', 'actual'):
            self._live_fit_mode = fit_mode
        if refresh:
            try:
                return bool(self.refresh_live_thumb_fit())
            except Exception:
                return False
        return False

    def refresh_live_thumb_fit(self):
        """Re-apply _fit_pixmap_to_thumb on last live src (pad/fit change, same frame)."""
        src = getattr(self, '_live_src_pixmap', None)
        if src is None or not hasattr(self, 'thumbs'):
            return False
        row = self.thumbs.currentRow()
        if row < 0:
            return False
        item = self.thumbs.item(row)
        if item is None:
            return False
        mode = getattr(self, '_live_fit_mode', 'contain')
        from PySide6.QtGui import QIcon
        pix = self._fit_pixmap_to_thumb(src, mode)
        item.setIcon(QIcon(pix))
        return True

    def set_live_display(self, data_url, fit_mode=None, pad_color=None):
        """Push Display result + honor fitMode crop on current thumb."""
        if fit_mode in ('contain', 'cover', 'actual'):
            self._live_fit_mode = fit_mode
        if pad_color is not None:
            try:
                # Frame reload below will re-fit; pad-only refresh when no data_url
                self.set_actual_pad_color(pad_color, refresh=not bool(data_url))
            except TypeError:
                self.set_actual_pad_color(pad_color)
            except Exception:
                pass
        self.set_live_result(data_url, fit_mode=fit_mode or getattr(self, '_live_fit_mode', None))
        try:
            row = self.thumbs.currentRow() if hasattr(self, 'thumbs') else -1
            item = self.thumbs.item(row) if row >= 0 else None
            if item is not None and fit_mode:
                tip = item.toolTip() or ''
                tag = f'· fitMode={fit_mode}'
                if tag not in tip:
                    item.setToolTip((tip + '\n' + tag).strip())
        except Exception:
            pass

    def set_live_result(self, data_url, fit_mode=None):
        """Push display/engine annotatedImage onto current filmstrip thumb (live preview)."""
        if not data_url or not hasattr(self, 'thumbs'):
            return
        row = self.thumbs.currentRow()
        if row < 0 or row >= len(self._paths):
            return
        try:
            raw = data_url
            if isinstance(raw, str) and raw.startswith('data:image'):
                import base64
                # data:image/png;base64,....
                b64 = raw.split(',', 1)[-1]
                ba = base64.b64decode(b64)
                img = QImage.fromData(ba)
                if img.isNull():
                    return
                src_pix = QPixmap.fromImage(img)
                self._live_src_pixmap = src_pix
                mode = fit_mode if fit_mode in ('contain', 'cover', 'actual') else getattr(self, '_live_fit_mode', 'contain')
                if fit_mode in ('contain', 'cover', 'actual'):
                    self._live_fit_mode = mode
                pix = self._fit_pixmap_to_thumb(src_pix, mode)
                item = self.thumbs.item(row)
                if item is not None:
                    item.setIcon(QIcon(pix))
                    base_tip = item.toolTip() or self._paths[row]
                    extra = '· 模块结果预览'
                    if mode:
                        extra = f'{extra} · fitMode={mode}'
                    if extra not in base_tip:
                        item.setToolTip((base_tip + '\n' + extra).strip())
        except Exception:
            pass

    def clear_all(self):
        if not self._paths:
            return
        self.set_paths([], 0)
        self.listChanged.emit(self.paths())

    def advance(self):
        """Move to next image when 自动切换 is on. Returns False if stopped at end."""
        if not self._paths:
            return False
        if self._index + 1 >= len(self._paths):
            return False
        self.thumbs.setCurrentRow(self._index + 1)
        return True

    def _on_thumb_size_changed(self, *_):
        px = self.thumb_size.currentData()
        self._thumb_px = int(px or 72)
        from PySide6.QtCore import QSize
        if hasattr(self, 'thumbs') and self.thumbs is not None:
            self.thumbs.setIconSize(QSize(self._thumb_px, self._thumb_px))
        self.set_format_filter_hint(
            f'缩略图 {self._thumb_px}px · 格式 ' + (
                ', '.join(sorted(self._exts_for_filter()))
                if getattr(self, '_format_filter_key', '全部') != '全部'
                else '全部'))
        # Re-render thumbs at new size when helper exists
        if hasattr(self, 'refresh_thumbs'):
            try:
                self.refresh_thumbs()
            except Exception:
                pass
        elif hasattr(self, '_reload_thumbs'):
            try:
                self._reload_thumbs()
            except Exception:
                pass



class _UndoClearProgressArc(QWidget):
    """wave31: 长按清空进度弧 overlay."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._p = 0.0
        self.setFixedSize(22, 22)
        self.setObjectName('compareThumbUndoClearArc')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def set_progress(self, p: float):
        self._p = max(0.0, min(1.0, float(p or 0.0)))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # track
        track = QPen(QColor('#3a3d42'), 2)
        p.setPen(track)
        rect = self.rect().adjusted(2, 2, -2, -2)
        p.drawEllipse(rect)
        if self._p <= 0:
            return
        arc = QPen(QColor('#e0b84a'), 2)
        p.setPen(arc)
        # Qt angles: 1/16 degree; 90*16 = top; span clockwise negative
        p.drawArc(rect, 90 * 16, -int(self._p * 360 * 16))


class CompareThumbStrip(QWidget):
    """wave24–26: 多选对比侧栏缩略条（拖拽重排 / 锁定 / 复位）."""
    pathActivated = Signal(str)   # click a thumb → focus that path
    clearRequested = Signal()     # clear compare
    pathsReordered = Signal(list)  # wave25: drag reorder → new path order
    lockChanged = Signal(bool)    # wave26: order lock

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('compareThumbStrip')
        self.setFixedWidth(96)
        self._paths = []
        self._baseline_paths = []  # wave26: order at set_paths / unlock baseline
        self._order_locked = False
        self._order_undo_stack = []  # wave27: 复位/重排撤销栈
        self._order_undo_max = 16
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        head = QHBoxLayout()
        self._title = QLabel('对比')
        self._title.setObjectName('compareThumbTitle')
        self._title.setStyleSheet('color:#9ec9f0;font-size:11px;font-weight:700;')
        head.addWidget(self._title, 1)
        self._lock_btn = QPushButton('🔓')
        self._lock_btn.setObjectName('compareThumbLock')
        self._lock_btn.setFixedSize(20, 20)
        self._lock_btn.setCheckable(True)
        self._lock_btn.setToolTip('锁定对比序（禁止拖拽）')
        self._lock_btn.toggled.connect(self._on_lock_toggled)
        head.addWidget(self._lock_btn)
        # wave29–31: 锁序徽章 · 单击切换 · 双击复位并解锁
        self._lock_badge = QLabel('未锁')
        self._lock_badge.setObjectName('compareThumbLockBadge')
        self._lock_badge.setFixedHeight(16)
        self._lock_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lock_badge.setStyleSheet(
            'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
            'border-radius:3px;padding:0 4px;font-size:9px;font-weight:600;'
        )
        self._lock_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lock_badge.setToolTip('单击切换锁 · 双击复位并解锁')
        self._lock_badge_click_timer = QTimer(self)
        self._lock_badge_click_timer.setSingleShot(True)
        self._lock_badge_click_timer.timeout.connect(self._on_lock_badge_single_click)
        self._lock_badge.mousePressEvent = lambda e: self._on_lock_badge_press(e)
        self._lock_badge.mouseDoubleClickEvent = lambda e: self._on_lock_badge_double(e)
        head.addWidget(self._lock_badge)
        self._reset_btn = QPushButton('↺')
        self._reset_btn.setObjectName('compareThumbReset')
        self._reset_btn.setFixedSize(20, 20)
        self._reset_btn.setToolTip('复位对比序到进入时顺序')
        self._reset_btn.clicked.connect(self.reset_order)
        head.addWidget(self._reset_btn)
        self._undo_btn = QPushButton('↶')
        self._undo_btn.setObjectName('compareThumbUndo')
        self._undo_btn.setFixedSize(20, 20)
        self._undo_btn.setToolTip('撤销对比序（复位/重排）')
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo_order)
        head.addWidget(self._undo_btn)
        # wave28: 撤销栈深度徽章
        self._undo_depth_badge = QLabel('0')
        self._undo_depth_badge.setObjectName('compareThumbUndoDepth')
        self._undo_depth_badge.setFixedHeight(16)
        self._undo_depth_badge.setMinimumWidth(14)
        self._undo_depth_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._undo_depth_badge.setStyleSheet(
            'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
            'border-radius:3px;padding:0 3px;font-size:9px;font-weight:700;'
        )
        self._undo_depth_badge.setToolTip('撤销栈深度')
        head.addWidget(self._undo_depth_badge)
        # wave29–31: 撤销清空 · 短按 tip / 长按清空 + 进度弧
        self._undo_clear_btn = QPushButton('⊘')
        self._undo_clear_btn.setObjectName('compareThumbUndoClear')
        self._undo_clear_btn.setFixedSize(20, 20)
        self._undo_clear_btn.setToolTip('短按提示 · 长按清空撤销栈')
        self._undo_clear_btn.setEnabled(False)
        self._undo_clear_long_ms = 650
        try:
            raw_ms = self._compare_settings().value('film/undoClearLongMs', 650)
            self._undo_clear_long_ms = max(300, min(3000, int(raw_ms or 650)))
        except Exception:
            self._undo_clear_long_ms = 650
        self._undo_clear_long_fired = False
        self._undo_clear_press_ms = 0
        self._undo_clear_btn.setToolTip(
            f'短按提示 · 长按清空（{self._undo_clear_long_ms}ms）· 右键调时长'
        )
        self._undo_clear_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._undo_clear_btn.customContextMenuRequested.connect(self._on_undo_clear_ctx)
        self._undo_clear_timer = QTimer(self)
        self._undo_clear_timer.setSingleShot(True)
        self._undo_clear_timer.timeout.connect(self._on_undo_clear_long_press)
        self._undo_clear_tick = QTimer(self)
        self._undo_clear_tick.setInterval(40)
        self._undo_clear_tick.timeout.connect(self._on_undo_clear_tick)
        self._undo_clear_btn.pressed.connect(self._on_undo_clear_pressed)
        self._undo_clear_btn.released.connect(self._on_undo_clear_released)
        head.addWidget(self._undo_clear_btn)
        self._undo_clear_arc = _UndoClearProgressArc(self)
        self._clear_btn = QPushButton('×')
        self._clear_btn.setObjectName('compareThumbClear')
        self._clear_btn.setFixedSize(20, 20)
        self._clear_btn.setToolTip('清除多选对比叠层')
        self._clear_btn.clicked.connect(self.clearRequested.emit)
        head.addWidget(self._clear_btn)
        lay.addLayout(head)
        self._list = QListWidget()
        self._list.setObjectName('compareThumbList')
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setFlow(QListWidget.Flow.TopToBottom)
        self._list.setWrapping(False)
        self._list.setMovement(QListWidget.Movement.Snap)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setIconSize(QSize(72, 72))
        self._list.setSpacing(4)
        self._list.setToolTip('拖拽缩略可重排对比叠层顺序（上→下 = 优先色）')
        self._list.setStyleSheet(
            'QListWidget{background:#1c1e22;border:1px solid #3a5a7a;border-radius:2px;}'
            'QListWidget::item{border:1px solid #3a5a7a;border-radius:2px;padding:2px;}'
            'QListWidget::item:selected{border:2px solid #6eb6ff;background:#1c2a3a;}'
        )
        self._list.itemClicked.connect(self._on_item)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        # also catch drop via event filter when InternalMove finishes
        self._list.installEventFilter(self)
        self._suppress_reorder = False
        lay.addWidget(self._list, 1)
        self.hide()

    def paths(self):
        return list(self._paths)

    def set_paths(self, paths, *, active: str = '', as_baseline: bool = True):
        paths = [str(x) for x in (paths or []) if str(x).strip()][:6]
        self._paths = paths
        if as_baseline:
            self._baseline_paths = list(paths)
            self._order_undo_stack = []
            self._sync_undo_btn()
        self._suppress_reorder = True
        self._list.clear()
        if not paths:
            self.hide()
            self._title.setText('对比')
            self._baseline_paths = []
            return
        lock_mark = '🔒' if self._order_locked else ''
        self._title.setText(f'对比·{len(paths)}{lock_mark}')
        active_row = -1
        for i, fp in enumerate(paths):
            leaf = Path(fp).name
            item = QListWidgetItem(leaf)
            item.setData(Qt.ItemDataRole.UserRole, fp)
            item.setToolTip(fp)
            pix = QPixmap(fp)
            if not pix.isNull():
                item.setIcon(QIcon(pix.scaled(
                    72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)))
            else:
                item.setIcon(QIcon())
            self._list.addItem(item)
            if active and (fp == active or Path(fp).name == Path(active).name):
                active_row = i
        if active_row >= 0:
            self._list.setCurrentRow(active_row)
        self._suppress_reorder = False
        self.show()

    def clear(self):
        self.set_paths([])

    def _read_list_paths(self):
        out = []
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it is None:
                continue
            fp = it.data(Qt.ItemDataRole.UserRole) or ''
            if fp:
                out.append(str(fp))
        return out

    def _emit_reorder_if_changed(self):
        if getattr(self, '_suppress_reorder', False):
            return
        if getattr(self, '_order_locked', False):
            # revert visual order if somehow moved while locked
            try:
                self.set_paths(self._paths, active='', as_baseline=False)
            except Exception:
                pass
            return
        new_paths = self._read_list_paths()
        if new_paths and new_paths != list(self._paths):
            self._push_order_undo(list(self._paths))
            self._paths = list(new_paths)
            lock_mark = '🔒' if self._order_locked else ''
            self._title.setText(f'对比·{len(self._paths)}{lock_mark}')
            try:
                self.pathsReordered.emit(list(self._paths))
            except Exception:
                pass

    def is_order_locked(self) -> bool:
        return bool(getattr(self, '_order_locked', False))

    def set_order_locked(self, locked: bool, *, persist: bool = False):
        locked = bool(locked)
        self._order_locked = locked
        btn = getattr(self, '_lock_btn', None)
        if btn is not None:
            try:
                btn.blockSignals(True)
                btn.setChecked(locked)
                btn.blockSignals(False)
            except Exception:
                pass
        self._apply_lock_chrome()
        if persist:
            try:
                self.save_order_lock_pref(locked)
            except Exception:
                pass
        try:
            self.lockChanged.emit(locked)
        except Exception:
            pass

    def _on_lock_badge_press(self, event=None):
        """wave30–31: 单击延迟切换；双击走 double handler."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        timer = getattr(self, '_lock_badge_click_timer', None)
        if timer is not None:
            timer.start(280)

    def _on_lock_badge_single_click(self):
        """wave30: 锁序徽章单击切换锁."""
        new_locked = not bool(getattr(self, '_order_locked', False))
        self.set_order_locked(new_locked, persist=True)

    def _on_lock_badge_clicked(self, event=None):
        """兼容旧 API / 冒烟：立即切换."""
        timer = getattr(self, '_lock_badge_click_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._on_lock_badge_single_click()

    def _on_lock_badge_double(self, event=None):
        """wave31–32: 双击 → 复位并解锁；先压入 undo（可 ↶ 撤销序，并可恢复锁）."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        timer = getattr(self, '_lock_badge_click_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        was_locked = bool(getattr(self, '_order_locked', False))
        cur = list(getattr(self, '_paths', None) or [])
        # wave32: always push current order so double-click is undoable
        if cur:
            self._push_order_undo(cur)
        base = list(getattr(self, '_baseline_paths', None) or [])
        if base and base != list(self._paths):
            active = ''
            try:
                row = self._list.currentRow()
                if 0 <= row < len(self._paths):
                    active = self._paths[row]
            except Exception:
                active = ''
            self.set_paths(base, active=active or (base[0] if base else ''), as_baseline=False)
            try:
                self.pathsReordered.emit(list(self._paths))
            except Exception:
                pass
        self._undo_should_relock = was_locked
        self.set_order_locked(False, persist=True)
        lb = getattr(self, '_lock_badge', None)
        try:
            if lb is not None:
                tip = '已复位并解锁（↶ 可撤销）' if was_locked or cur else '已解锁'
                QToolTip.showText(lb.mapToGlobal(QPoint(0, lb.height())), tip, lb)
        except Exception:
            pass

    def _on_undo_clear_pressed(self):
        """wave30–31: 按下开始长按计时 + 进度弧."""
        self._undo_clear_long_fired = False
        self._undo_clear_press_ms = 0
        long_ms = int(getattr(self, '_undo_clear_long_ms', 650) or 650)
        timer = getattr(self, '_undo_clear_timer', None)
        if timer is not None:
            timer.start(long_ms)
        tick = getattr(self, '_undo_clear_tick', None)
        if tick is not None:
            tick.start()
        self._show_undo_clear_arc(0.0)

    def _on_undo_clear_tick(self):
        """wave31: 刷新长按进度弧."""
        long_ms = float(getattr(self, '_undo_clear_long_ms', 650) or 650)
        self._undo_clear_press_ms = int(getattr(self, '_undo_clear_press_ms', 0) or 0) + int(
            getattr(self, '_undo_clear_tick', None).interval() if getattr(self, '_undo_clear_tick', None) else 40
        )
        p = min(1.0, float(self._undo_clear_press_ms) / max(1.0, long_ms))
        self._show_undo_clear_arc(p)

    def _show_undo_clear_arc(self, p: float):
        arc = getattr(self, '_undo_clear_arc', None)
        btn = getattr(self, '_undo_clear_btn', None)
        if arc is None or btn is None:
            return
        try:
            # overlay centered on clear button
            gp = btn.mapTo(self, QPoint(0, 0))
            arc.move(gp.x() - 1, gp.y() - 1)
            arc.set_progress(p)
            arc.show()
            arc.raise_()
        except Exception:
            pass

    def _hide_undo_clear_arc(self):
        arc = getattr(self, '_undo_clear_arc', None)
        tick = getattr(self, '_undo_clear_tick', None)
        if tick is not None and tick.isActive():
            tick.stop()
        if arc is not None:
            arc.set_progress(0.0)
            arc.hide()

    def _on_undo_clear_released(self):
        """wave30: 短按 → 确认 tip；长按已触发则跳过."""
        timer = getattr(self, '_undo_clear_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._hide_undo_clear_arc()
        if getattr(self, '_undo_clear_long_fired', False):
            return
        n = len(getattr(self, '_order_undo_stack', None) or [])
        ms = int(getattr(self, '_undo_clear_long_ms', 650) or 650)
        tip = f'长按 ⊘ 清空（{ms}ms · 栈 {n}）' if n else f'撤销栈为空 · 长按时长 {ms}ms'
        btn = getattr(self, '_undo_clear_btn', None)
        try:
            if btn is not None:
                QToolTip.showText(btn.mapToGlobal(QPoint(0, btn.height())), tip, btn)
                btn.setToolTip(tip + ' · 右键调时长')
        except Exception:
            pass

    def _on_undo_clear_long_press(self):
        """wave30–31: 长按确认清空（进度弧满）."""
        self._undo_clear_long_fired = True
        self._show_undo_clear_arc(1.0)
        ok = self.clear_order_undo()
        self._hide_undo_clear_arc()
        btn = getattr(self, '_undo_clear_btn', None)
        tip = '已清空撤销栈' if ok else '撤销栈为空'
        try:
            if btn is not None:
                QToolTip.showText(btn.mapToGlobal(QPoint(0, btn.height())), tip, btn)
        except Exception:
            pass

    def _on_lock_toggled(self, on: bool):
        self._order_locked = bool(on)
        self._apply_lock_chrome()
        try:
            self.save_order_lock_pref(self._order_locked)
        except Exception:
            pass
        try:
            self.lockChanged.emit(self._order_locked)
        except Exception:
            pass

    def _apply_lock_chrome(self):
        locked = bool(getattr(self, '_order_locked', False))
        btn = getattr(self, '_lock_btn', None)
        if btn is not None:
            btn.setText('🔒' if locked else '🔓')
            btn.setToolTip('已锁定对比序（点击解锁）' if locked else '锁定对比序（禁止拖拽）')
        # wave29: 锁序徽章
        lb = getattr(self, '_lock_badge', None)
        if lb is not None:
            if locked:
                lb.setText('已锁')
                lb.setStyleSheet(
                    'background:#3a3420;color:#e0b84a;border:1px solid #e0b84a;'
                    'border-radius:3px;padding:0 4px;font-size:9px;font-weight:700;'
                )
                lb.setToolTip('已锁 · 单击解锁 · 双击复位并解锁')
            else:
                lb.setText('未锁')
                lb.setStyleSheet(
                    'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                    'border-radius:3px;padding:0 4px;font-size:9px;font-weight:600;'
                )
                lb.setToolTip('未锁 · 单击锁定 · 双击复位并解锁')
        # wave28: 锁序时复位仍可用提示
        rbtn = getattr(self, '_reset_btn', None)
        if rbtn is not None:
            if locked:
                rbtn.setToolTip('复位对比序到进入时顺序（锁序下仍可用）')
                rbtn.setStyleSheet(
                    'color:#9ec9f0;border:1px solid #3a5a7a;border-radius:2px;'
                )
            else:
                rbtn.setToolTip('复位对比序到进入时顺序')
                rbtn.setStyleSheet('')
        try:
            if locked:
                self._list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
                self._list.setMovement(QListWidget.Movement.Static)
            else:
                self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
                self._list.setMovement(QListWidget.Movement.Snap)
        except Exception:
            pass
        lock_mark = '🔒' if locked else ''
        n = len(self._paths)
        if n:
            self._title.setText(f'对比·{n}{lock_mark}')

    def reset_order(self):
        """wave26–28: 复位到进入对比时的基线序（先压入撤销栈；锁序下仍可用）."""
        base = list(getattr(self, '_baseline_paths', None) or [])
        if not base:
            return False
        if base == list(self._paths):
            return False
        self._push_order_undo(list(self._paths))
        active = ''
        try:
            row = self._list.currentRow()
            if 0 <= row < len(self._paths):
                active = self._paths[row]
        except Exception:
            active = ''
        self.set_paths(base, active=active or (base[0] if base else ''), as_baseline=False)
        try:
            self.pathsReordered.emit(list(self._paths))
        except Exception:
            pass
        return True

    def _push_order_undo(self, paths):
        paths = [str(x) for x in (paths or []) if str(x).strip()]
        if not paths:
            return
        stack = getattr(self, '_order_undo_stack', None)
        if stack is None:
            self._order_undo_stack = []
            stack = self._order_undo_stack
        if stack and stack[-1] == paths:
            return
        stack.append(list(paths))
        max_n = int(getattr(self, '_order_undo_max', 16) or 16)
        if len(stack) > max_n:
            del stack[:-max_n]
        self._sync_undo_btn()

    def _sync_undo_btn(self):
        btn = getattr(self, '_undo_btn', None)
        n = len(getattr(self, '_order_undo_stack', None) or [])
        if btn is not None:
            btn.setEnabled(n > 0)
            btn.setToolTip(f'撤销对比序（{n}）' if n else '撤销对比序（空）')
        badge = getattr(self, '_undo_depth_badge', None)
        if badge is not None:
            badge.setText(str(n))
            badge.setToolTip(f'撤销栈深度 · {n}' + (f'/{self._order_undo_max}' if getattr(self, '_order_undo_max', None) else ''))
            if n > 0:
                badge.setStyleSheet(
                    'background:#1c2a3a;color:#9ec9f0;border:1px solid #6eb6ff;'
                    'border-radius:3px;padding:0 3px;font-size:9px;font-weight:700;'
                )
            else:
                badge.setStyleSheet(
                    'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                    'border-radius:3px;padding:0 3px;font-size:9px;font-weight:700;'
                )
        cbtn = getattr(self, '_undo_clear_btn', None)
        if cbtn is not None:
            cbtn.setEnabled(n > 0)
            ms = int(getattr(self, '_undo_clear_long_ms', 650) or 650)
            cbtn.setToolTip(
                f'短按提示 · 长按清空（{ms}ms · 栈{n}）· 右键调时长'
                if n else f'短按提示 · 长按清空（{ms}ms · 空）· 右键调时长'
            )

    def clear_order_undo(self) -> bool:
        """wave29: 清空对比序撤销栈."""
        stack = getattr(self, '_order_undo_stack', None)
        if not stack:
            self._sync_undo_btn()
            return False
        stack.clear()
        self._sync_undo_btn()
        return True

    def set_undo_clear_long_ms(self, ms: int, *, persist: bool = True) -> int:
        """wave32: 配置长按清空时长（300–3000ms）."""
        ms = max(300, min(3000, int(ms or 650)))
        self._undo_clear_long_ms = ms
        btn = getattr(self, '_undo_clear_btn', None)
        if btn is not None:
            n = len(getattr(self, '_order_undo_stack', None) or [])
            btn.setToolTip(f'短按提示 · 长按清空（{ms}ms）· 右键选时长' + (f' · 栈{n}' if n else ''))
        if persist:
            try:
                self._compare_settings().setValue('film/undoClearLongMs', ms)
            except Exception:
                pass
        return ms

    def undo_clear_long_ms(self) -> int:
        return int(getattr(self, '_undo_clear_long_ms', 650) or 650)

    def _on_undo_clear_ctx(self, pos=None):
        """wave32–33: 右键弹出时长预设菜单（非仅循环）."""
        menu = self._build_undo_clear_preset_menu()
        btn = getattr(self, '_undo_clear_btn', None)
        if menu is None or btn is None:
            return
        if getattr(self, '_undo_clear_ctx_no_exec', False):
            self._last_undo_clear_ctx_menu = menu
            return menu
        try:
            gp = btn.mapToGlobal(pos) if pos is not None else btn.mapToGlobal(QPoint(0, btn.height()))
            menu.exec(gp)
        except Exception:
            pass

    def _build_undo_clear_preset_menu(self):
        """wave33–34: 时长预设菜单；标记默认 650ms."""
        presets = (400, 650, 1000, 1500)
        default_ms = 650
        cur = self.undo_clear_long_ms()
        menu = QMenu(self)
        menu.setObjectName('compareThumbUndoClearPresetMenu')
        for ms in presets:
            lab = f'{ms} ms'
            if ms == default_ms:
                lab = f'{lab}（默认）'
            if ms == cur:
                lab = f'✓ {lab}'
            act = QAction(lab, self)
            act.setData(ms)
            act.setProperty('isDefault', ms == default_ms)
            act.triggered.connect(lambda *_a, m=ms: self._apply_undo_clear_preset(m))
            menu.addAction(act)
        return menu

    def _apply_undo_clear_preset(self, ms: int):
        """Apply duration preset and tip."""
        self.set_undo_clear_long_ms(int(ms))
        btn = getattr(self, '_undo_clear_btn', None)
        try:
            if btn is not None:
                QToolTip.showText(
                    btn.mapToGlobal(QPoint(0, btn.height())),
                    f'长按时长 → {int(ms)}ms',
                    btn,
                )
        except Exception:
            pass

    def undo_order(self) -> bool:
        """wave27: 弹出撤销栈恢复上一对比序."""
        stack = getattr(self, '_order_undo_stack', None) or []
        if not stack:
            return False
        prev = stack.pop()
        self._sync_undo_btn()
        changed = bool(prev) and prev != list(self._paths)
        if changed:
            active = ''
            try:
                row = self._list.currentRow()
                if 0 <= row < len(self._paths):
                    active = self._paths[row]
            except Exception:
                active = ''
            self.set_paths(prev, active=active or (prev[0] if prev else ''), as_baseline=False)
            try:
                self.pathsReordered.emit(list(self._paths))
            except Exception:
                pass
        # wave32: 双击解锁后的 ↶ 可恢复锁态（即使序未变）
        relocked = False
        if getattr(self, '_undo_should_relock', False):
            self._undo_should_relock = False
            try:
                self.set_order_locked(True, persist=True)
                relocked = True
            except Exception:
                pass
        return bool(changed or relocked)

    def order_undo_depth(self) -> int:
        return len(getattr(self, '_order_undo_stack', None) or [])

    def baseline_paths(self):
        return list(getattr(self, '_baseline_paths', None) or [])

    # --- wave27: lock QSettings 持久 ---
    @staticmethod
    def _compare_settings():
        return QSettings('SIEANS', 'VisionDesktop')

    def load_order_lock_pref(self) -> bool:
        try:
            raw = self._compare_settings().value('film/compareOrderLocked', False)
            locked = str(raw).strip().lower() in ('1', 'true', 'yes')
        except Exception:
            locked = False
        self.set_order_locked(locked)
        return locked

    def save_order_lock_pref(self, locked: bool | None = None):
        if locked is None:
            locked = self.is_order_locked()
        try:
            self._compare_settings().setValue('film/compareOrderLocked', bool(locked))
        except Exception:
            pass

    def _on_rows_moved(self, *args):
        self._emit_reorder_if_changed()

    def eventFilter(self, obj, event):
        # wave25: InternalMove drop → sync order
        try:
            if obj is self._list and event is not None:
                et = event.type()
                if et in (QEvent.Type.Drop, QEvent.Type.ChildRemoved):
                    # defer so model settles
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self._emit_reorder_if_changed)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _on_item(self, item):
        if item is None:
            return
        fp = item.data(Qt.ItemDataRole.UserRole) or ''
        if fp:
            self.pathActivated.emit(str(fp))
