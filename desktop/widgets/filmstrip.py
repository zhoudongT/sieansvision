"""Local-image filmstrip under the image viewport (VisionMaster 胶片条)."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileDialog, QMessageBox,
)

from .switch import OrangeSwitch

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
        root.addWidget(self.thumbs)
        self.empty_hint = QLabel('未添加图像 — 点 + 或 📁 导入；本地模式下节点会显示红叹号直至添加。')
        self.empty_hint.setObjectName('filmstripEmpty')
        self.empty_hint.setStyleSheet('color:#c62828;font-size:11px;padding:0 2px;')
        self.empty_hint.setWordWrap(True)
        root.addWidget(self.empty_hint)
        self.set_paths([], 0)

    def paths(self):
        return list(self._paths)

    def current_index(self):
        return self._index

    def current_path(self):
        if 0 <= self._index < len(self._paths):
            return self._paths[self._index]
        return ''

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

    def _refresh_count(self):
        n = len(self._paths)
        cur = (self._index + 1) if n else 0
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
        paths = []
        for path in sorted(Path(folder).iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
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

    def set_live_result(self, data_url):
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
                pix = QPixmap.fromImage(img).scaled(
                    self.thumbs.iconSize(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item = self.thumbs.item(row)
                if item is not None:
                    item.setIcon(QIcon(pix))
                    item.setToolTip((item.toolTip() or self._paths[row]) + '\n· 模块结果预览')
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
