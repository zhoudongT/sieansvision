"""Local-image filmstrip under the image viewport (VisionMaster 胶片条)."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileDialog, QMessageBox, QComboBox,
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

