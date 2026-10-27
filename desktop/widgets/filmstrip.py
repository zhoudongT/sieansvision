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
    runAllRequested = Signal()
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
        self.run_all = QPushButton('运行全部')
        self.run_all.setObjectName('filmstripRun')
        self.run_all.clicked.connect(self.runAllRequested.emit)
        bar.addWidget(self.run_all)
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

    def set_paths(self, paths, index=0):
        self._paths = [str(p) for p in paths]
        self._index = max(0, min(index, max(0, len(self._paths) - 1)))
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for path in self._paths:
            item = QListWidgetItem(Path(path).name)
            pix = QPixmap(path)
            if not pix.isNull():
                item.setIcon(QIcon(pix.scaled(72, 54, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.thumbs.addItem(item)
        if self._paths:
            self.thumbs.setCurrentRow(self._index)
        self.thumbs.blockSignals(False)
        self._refresh_count()

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

    def advance(self):
        """Move to next image when 自动切换 is on. Returns False if stopped at end."""
        if not self._paths:
            return False
        if self._index + 1 >= len(self._paths):
            return False
        self.thumbs.setCurrentRow(self._index + 1)
        return True
