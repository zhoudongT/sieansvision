# -*- coding: utf-8 -*-
"""缺陷检测 / OCR 结果显示与判定面板（OpenCV 壳 · 无 Halcon）。

与 MeasureGeomPanel / LocateResultPanel 同风格：参数 + 结果叠层 + Host 实况绑定。
细妆：缺陷参考图绑定 UX · OCR ROI 绘制/绑定。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox, QDoubleSpinBox,
    QSpinBox, QLineEdit, QHBoxLayout, QPushButton, QTabWidget, QTextEdit,
    QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from desktop.widgets.switch import OrangeSwitch


def _norm_defects(params: dict | None) -> dict:
    p = dict(params or {})
    p.setdefault('method', 'absdiff')
    p.setdefault('threshold', 30)
    p.setdefault('minArea', 50)
    p.setdefault('maxCount', 200)
    p.setdefault('blur', 3)
    p.setdefault('showOverlay', True)
    p.setdefault('showBoxes', True)
    p.setdefault('showLabels', True)
    p.setdefault('resultVar', 'defects')
    p.setdefault('writeFlowVars', True)
    p.setdefault('judgeEnable', True)
    p.setdefault('judgeMaxCount', 0)  # 0 = any defect → NG when enable
    p.setdefault('judgeMaxRatio', 0.05)
    p.setdefault('referencePath', '')
    p.setdefault('hasReference', False)
    return p


def _norm_ocr(params: dict | None) -> dict:
    p = dict(params or {})
    p.setdefault('lang', 'ch')
    p.setdefault('minConfidence', 0.5)
    p.setdefault('maxItems', 50)
    p.setdefault('showOverlay', True)
    p.setdefault('showBoxes', True)
    p.setdefault('showText', True)
    p.setdefault('resultVar', 'ocr')
    p.setdefault('writeFlowVars', True)
    p.setdefault('judgeEnable', False)
    p.setdefault('expectedText', '')
    p.setdefault('judgeMinConfidence', 0.5)
    p.setdefault('roiMode', 'inherit')  # inherit | draw
    if 'roi' not in p:
        p['roi'] = None
    return p


def _has_ref(step: dict, params: dict) -> bool:
    if step.get('reference'):
        return True
    if params.get('hasReference'):
        return True
    if str(params.get('referencePath') or '').strip():
        return True
    return False


class _RecognizeShell(QWidget):
    changed = Signal(dict)

    def __init__(self, step: dict, definition=None, project=None, parent=None):
        super().__init__(parent)
        from copy import deepcopy as _dc
        self.step = _dc(step) if isinstance(step, dict) else {}
        self.definition = definition or {}
        self.project = project or {}
        self.params = dict(self.step.get('params') or {})
        self._live_lab = None
        self._build()

    def _emit(self):
        from copy import deepcopy as _dc
        self.step['params'] = _dc(self.params)
        self.changed.emit(_dc(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = value
            self._emit()

    def _host_last(self) -> dict:
        try:
            from desktop.upstream_field_picker import host_last_result
            return host_last_result(self) or {}
        except Exception:
            return {}

    def _find_step_result(self) -> dict:
        lr = self._host_last()
        sid = self.step.get('id')
        for rec in (lr.get('results') or []):
            if isinstance(rec, dict) and rec.get('id') == sid:
                return (rec.get('output') or {}).get('result') or rec.get('result') or {}
        if isinstance(lr.get('results'), dict) and sid in lr['results']:
            hit = lr['results'][sid]
            if isinstance(hit, dict):
                return (hit.get('output') or {}).get('result') or hit.get('result') or hit
        return {}

    def _host_sample_image(self):
        """Best-effort current image for ROI editor background."""
        try:
            w = self.window()
            for attr in ('image', 'last_image', '_preview_image'):
                v = getattr(w, attr, None)
                if isinstance(v, str) and v.startswith('data:image'):
                    return v
            # filmstrip current path
            fs = getattr(w, 'filmstrip', None)
            if fs is not None and hasattr(fs, 'current_path'):
                path = fs.current_path()
                if path:
                    return path
            cfg = (self.project or {}).get('sourceConfig') or {}
            imgs = cfg.get('images') or []
            idx = int(cfg.get('currentIndex') or 0)
            if imgs:
                return imgs[max(0, min(idx, len(imgs) - 1))]
        except Exception:
            pass
        return None


class DefectsPanel(_RecognizeShell):
    """缺陷检测：参考图绑定 + 阈值 + 结果显示 + 判定 + 流程变量。"""

    def _build(self):
        self.params = _norm_defects(self.params)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.setObjectName('defectsTabs')
        tabs.addTab(self._ref_tab(), '参考图')
        tabs.addTab(self._params_tab(), '参数')
        tabs.addTab(self._result_tab(), '结果与判定')
        root.addWidget(tabs)

    def _ref_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        tip = QLabel(
            '工业视觉「良品参考图」：与检测图同尺寸、同位姿、相近光照。'
            '未绑定 → 画布节点红叹号；也可工具栏「设置参考图」。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        lay.addWidget(tip)

        form = QFormLayout()
        self._ref_path = QLineEdit(str(self.params.get('referencePath') or ''))
        self._ref_path.setObjectName('defectsReferencePath')
        self._ref_path.setPlaceholderText('参考图路径 / 方案内 data URL 已绑定时可留路径备注')
        self._ref_path.editingFinished.connect(self._on_ref_path_edit)
        form.addRow('参考路径', self._ref_path)
        lay.addLayout(form)

        row = QHBoxLayout()
        load_btn = QPushButton('载入参考图…')
        load_btn.setObjectName('defectsRefLoadBtn')
        load_btn.clicked.connect(self._load_reference)
        use_cur = QPushButton('用当前图像')
        use_cur.setObjectName('defectsRefUseCurrentBtn')
        use_cur.setToolTip('将主机当前预览/胶片图设为参考（写入 step.reference）')
        use_cur.clicked.connect(self._use_current_as_ref)
        clear_btn = QPushButton('清除')
        clear_btn.setObjectName('defectsRefClearBtn')
        clear_btn.clicked.connect(self._clear_reference)
        row.addWidget(load_btn)
        row.addWidget(use_cur)
        row.addWidget(clear_btn)
        row.addStretch(1)
        lay.addLayout(row)

        ready = _has_ref(self.step, self.params)
        self._ref_status = QLabel('参考图状态：已加载' if ready else '参考图状态：未绑定（缺配）')
        self._ref_status.setObjectName('defectsRefStatus')
        self._ref_status.setStyleSheet(
            'font-weight:600;color:#2e7d32;' if ready else 'font-weight:600;color:#c62828;'
        )
        lay.addWidget(self._ref_status)

        self._ref_meta = QLabel(self._ref_meta_text())
        self._ref_meta.setObjectName('defectsRefMeta')
        self._ref_meta.setWordWrap(True)
        self._ref_meta.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        lay.addWidget(self._ref_meta)
        lay.addStretch(1)
        return w

    def _ref_meta_text(self) -> str:
        bits = []
        path = str(self.params.get('referencePath') or '').strip()
        if path:
            bits.append(f'path={path[-64:]}')
        ref = self.step.get('reference')
        if isinstance(ref, str) and ref.startswith('data:image'):
            bits.append(f'dataURL≈{len(ref)}B')
            # try dimensions via Qt
            try:
                from PySide6.QtGui import QImage
                import base64
                b64 = ref.split(',', 1)[-1]
                img = QImage.fromData(base64.b64decode(b64))
                if not img.isNull():
                    bits.append(f'{img.width()}×{img.height()}')
            except Exception:
                pass
        elif ref:
            bits.append('reference=set')
        if self.params.get('hasReference'):
            bits.append('hasReference=1')
        return '绑定信息：' + (' · '.join(bits) if bits else '无')

    def _sync_ref_status(self):
        ready = _has_ref(self.step, self.params)
        if getattr(self, '_ref_status', None):
            self._ref_status.setText('参考图状态：已加载' if ready else '参考图状态：未绑定（缺配）')
            self._ref_status.setStyleSheet(
                'font-weight:600;color:#2e7d32;' if ready else 'font-weight:600;color:#c62828;'
            )
        if getattr(self, '_ref_meta', None):
            self._ref_meta.setText(self._ref_meta_text())
        if getattr(self, '_ref_path', None):
            cur = str(self.params.get('referencePath') or '')
            if self._ref_path.text() != cur:
                self._ref_path.setText(cur)

    def _on_ref_path_edit(self):
        path = self._ref_path.text().strip()
        self.params['referencePath'] = path
        if path:
            self.params['hasReference'] = True
        elif not self.step.get('reference'):
            self.params['hasReference'] = False
        self._sync_ref_status()
        self._emit()

    def _load_reference(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '载入缺陷参考图', '',
            '图像 (*.png *.bmp *.jpg *.jpeg *.tif);;所有文件 (*)'
        )
        if not path:
            return
        try:
            from pathlib import Path
            import base64
            raw = Path(path).read_bytes()
            if len(raw) > 12 * 1024 * 1024:
                QMessageBox.warning(self, '参考图', '图像不能超过 12 MB')
                return
            suf = Path(path).suffix.lower().lstrip('.') or 'png'
            if suf in ('jpg', 'jpeg'):
                mime = 'jpeg'
            else:
                mime = suf if suf in ('png', 'bmp', 'tif', 'tiff', 'webp') else 'png'
            data = f'data:image/{mime};base64,' + base64.b64encode(raw).decode()
            self.step['reference'] = data
            self.params['referencePath'] = path
            self.params['hasReference'] = True
            self._sync_ref_status()
            self._emit()
        except Exception as exc:
            QMessageBox.warning(self, '参考图', f'载入失败：{exc}')

    def _use_current_as_ref(self):
        img = self._host_sample_image()
        if not img:
            QMessageBox.information(self, '参考图', '当前无可用预览/胶片图像')
            return
        if isinstance(img, str) and img.startswith('data:image'):
            self.step['reference'] = img
            self.params['referencePath'] = self.params.get('referencePath') or '（当前预览）'
            self.params['hasReference'] = True
        else:
            # path — load as data URL
            try:
                from pathlib import Path
                import base64
                p = Path(str(img))
                raw = p.read_bytes()
                suf = p.suffix.lower().lstrip('.') or 'png'
                mime = 'jpeg' if suf in ('jpg', 'jpeg') else suf
                self.step['reference'] = f'data:image/{mime};base64,' + base64.b64encode(raw).decode()
                self.params['referencePath'] = str(p)
                self.params['hasReference'] = True
            except Exception as exc:
                QMessageBox.warning(self, '参考图', f'读取失败：{exc}')
                return
        self._sync_ref_status()
        self._emit()

    def _clear_reference(self):
        self.step['reference'] = ''
        self.params['referencePath'] = ''
        self.params['hasReference'] = False
        self._sync_ref_status()
        self._emit()

    def _params_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        method = QComboBox(); method.addItems(['absdiff', 'threshold', 'blob'])
        method.setCurrentText(str(self.params.get('method') or 'absdiff'))
        method.currentTextChanged.connect(lambda v: self._set_param('method', v))
        form.addRow('方法', method)
        thr = QSpinBox(); thr.setRange(1, 255); thr.setValue(int(self.params.get('threshold') or 30))
        thr.valueChanged.connect(lambda v: self._set_param('threshold', int(v)))
        form.addRow('差分阈值', thr)
        ma = QSpinBox(); ma.setRange(1, 1_000_000); ma.setValue(int(self.params.get('minArea') or 50))
        ma.valueChanged.connect(lambda v: self._set_param('minArea', int(v)))
        form.addRow('最小面积', ma)
        mc = QSpinBox(); mc.setRange(1, 5000); mc.setValue(int(self.params.get('maxCount') or 200))
        mc.valueChanged.connect(lambda v: self._set_param('maxCount', int(v)))
        form.addRow('最大缺陷数', mc)
        blur = QSpinBox(); blur.setRange(0, 31); blur.setSingleStep(2)
        blur.setValue(int(self.params.get('blur') or 3))
        blur.valueChanged.connect(lambda v: self._set_param('blur', int(v)))
        form.addRow('模糊核', blur)
        tip = QLabel('OpenCV absdiff / contour 壳 · 无 Halcon。参考图见「参考图」页。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;'); form.addRow(tip)
        return w

    def _result_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        for key, lab in (
            ('showOverlay', '显示叠加'),
            ('showBoxes', '显示缺陷框'),
            ('showLabels', '显示标签'),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, True)))
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)

        wv = OrangeSwitch(bool(self.params.get('writeFlowVars', True)))
        wv.toggled.connect(lambda c: self._set_param('writeFlowVars', bool(c)))
        form.addRow('写入流程变量', wv)
        out_var = QLineEdit(str(self.params.get('resultVar') or 'defects'))
        out_var.setObjectName('defectsResultVar')
        out_var.editingFinished.connect(
            lambda: self._set_param('resultVar', out_var.text().strip() or 'defects')
        )
        form.addRow('结果变量前缀', out_var)

        je = OrangeSwitch(bool(self.params.get('judgeEnable', True)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断使能', je)
        jmc = QSpinBox(); jmc.setRange(0, 5000)
        jmc.setValue(int(self.params.get('judgeMaxCount') if self.params.get('judgeMaxCount') is not None else 0))
        jmc.valueChanged.connect(lambda v: self._set_param('judgeMaxCount', int(v)))
        form.addRow('允许最大缺陷数', jmc)
        jmr = QDoubleSpinBox(); jmr.setRange(0, 1); jmr.setDecimals(4); jmr.setSingleStep(0.01)
        jmr.setValue(float(self.params.get('judgeMaxRatio') or 0.05))
        jmr.valueChanged.connect(lambda v: self._set_param('judgeMaxRatio', float(v)))
        form.addRow('允许最大缺陷比', jmr)
        tip_j = QLabel('count ≤ 最大数 且 defectRatio ≤ 最大比 → judgeOk；否则 NG。')
        tip_j.setWordWrap(True); tip_j.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_j)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('defectsLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)
        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('defectsLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)

        self._defects_items_table = QTableWidget(0, 4)
        self._defects_items_table.setObjectName('defectsItemsTable')
        self._defects_items_table.setHorizontalHeaderLabels(['#', '面积', 'bbox', '判定'])
        self._defects_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._defects_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._defects_items_table.setMaximumHeight(120)
        form.addRow('缺陷明细', self._defects_items_table)

        try:
            self._refresh_live()
        except Exception:
            pass
        return w

    def _refresh_live(self):
        lab = self._live_lab
        if lab is None:
            return
        res = self._find_step_result()
        if not res:
            lab.setText('实况：尚无本模块运行结果')
            self._fill_defects_items([])
            return
        bits = []
        for k in ('status', 'count', 'defectRatio', 'passed', 'judgeOk', 'judgeStatus', 'method'):
            if k in res and res[k] is not None:
                bits.append(f'{k}={res[k]}')
        items = res.get('items') or []
        bits.append(f'items={len(items) if isinstance(items, list) else items}')
        self._fill_defects_items(items if isinstance(items, list) else [])
        flow = ((self._host_last().get('variables') or {}).get('flow') or {})
        prefix = str(self.params.get('resultVar') or 'defects')
        for suffix in ('', '_count', '_ratio', '_passed', '_judgeOk', '_ok'):
            key = prefix if suffix == '' else prefix + suffix
            if key in flow:
                bits.append(f'flow.{key}={flow[key]}')
        for k in ('defects_count', 'defects_ratio', 'defects_passed', 'defects_judgeOk'):
            if k in flow:
                bits.append(f'flow.{k}={flow[k]}')
        lab.setText('实况：' + (' · '.join(bits[:12]) if bits else str(list(res.keys())[:8])))


class OcrPanel(_RecognizeShell):
    """OCR：ROI + 参数 + 结果显示 + 文本判定 + 流程变量。"""

    def _build(self):
        self.params = _norm_ocr(self.params)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.setObjectName('ocrTabs')
        tabs.addTab(self._params_tab(), '参数')
        tabs.addTab(self._roi_tab(), 'ROI')
        tabs.addTab(self._result_tab(), '结果与判定')
        root.addWidget(tabs)

    def _params_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        lang = QComboBox(); lang.addItems(['ch', 'en', 'ch_en'])
        lang.setCurrentText(str(self.params.get('lang') or 'ch'))
        lang.currentTextChanged.connect(lambda v: self._set_param('lang', v))
        form.addRow('语言', lang)
        mc = QDoubleSpinBox(); mc.setRange(0, 1); mc.setDecimals(3); mc.setSingleStep(0.05)
        mc.setValue(float(self.params.get('minConfidence') or 0.5))
        mc.valueChanged.connect(lambda v: self._set_param('minConfidence', float(v)))
        form.addRow('最小置信度', mc)
        mi = QSpinBox(); mi.setRange(1, 500); mi.setValue(int(self.params.get('maxItems') or 50))
        mi.valueChanged.connect(lambda v: self._set_param('maxItems', int(v)))
        form.addRow('最大条目', mi)
        tip = QLabel('RapidOCR / OpenCV 壳 · 无 Halcon。ROI 见「ROI」页；文本写入 flow 前缀。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;'); form.addRow(tip)
        return w

    def _roi_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        tip = QLabel(
            'OCR 识别区：继承=全图/上游 ROI；绘制=引擎按 params.roi=[x,y,w,h] 裁剪后识别。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        lay.addWidget(tip)

        form = QFormLayout()
        roi = QComboBox()
        roi.setObjectName('ocrRoiMode')
        roi.addItem('继承（连线 ROI / 全图）', 'inherit')
        roi.addItem('绘制 ROI', 'draw')
        idx = max(0, roi.findData(self.params.get('roiMode') or 'inherit'))
        roi.setCurrentIndex(idx)
        roi.currentIndexChanged.connect(lambda _: self._set_param('roiMode', roi.currentData()))
        form.addRow('ROI 模式', roi)

        self._roi_lab = QLabel(self._roi_summary())
        self._roi_lab.setObjectName('ocrRoiSummary')
        self._roi_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('当前 ROI', self._roi_lab)
        lay.addLayout(form)

        row = QHBoxLayout()
        edit_btn = QPushButton('绘制 / 编辑 ROI…')
        edit_btn.setObjectName('ocrRoiEditBtn')
        edit_btn.clicked.connect(self._edit_roi)
        clear_btn = QPushButton('清除 ROI')
        clear_btn.setObjectName('ocrRoiClearBtn')
        clear_btn.clicked.connect(self._clear_roi)
        row.addWidget(edit_btn)
        row.addWidget(clear_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _roi_summary(self) -> str:
        mode = self.params.get('roiMode') or 'inherit'
        roi = self.params.get('roi')
        if mode != 'draw':
            return f'模式=继承 · roi={"已忽略" if not roi else roi}'
        if isinstance(roi, list) and len(roi) == 4:
            x, y, w, h = roi
            return f'模式=绘制 · [{x:.0f},{y:.0f},{w:.0f},{h:.0f}]'
        return '模式=绘制 · 尚未设置矩形（将回退全图）'

    def _sync_roi_lab(self):
        if getattr(self, '_roi_lab', None):
            self._roi_lab.setText(self._roi_summary())

    def _edit_roi(self):
        from desktop.simple_roi_editor import SimpleRoiEditorDialog
        from PySide6.QtWidgets import QDialog
        img = self._host_sample_image()
        dlg = SimpleRoiEditorDialog(self.params, parent=self, image_data=img, title='OCR ROI 编辑器')
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        for k, v in dlg.result_params().items():
            self.params[k] = v
        # when draw mode, ensure engine sees roi; inherit clears use of stale? keep roi for re-enable
        self._sync_roi_lab()
        self._emit()

    def _clear_roi(self):
        self.params['roi'] = None
        self.params['roiMode'] = 'inherit'
        self._sync_roi_lab()
        # sync combo if present
        try:
            box = self.findChild(QComboBox, 'ocrRoiMode')
            if box is not None:
                idx = max(0, box.findData('inherit'))
                box.blockSignals(True)
                box.setCurrentIndex(idx)
                box.blockSignals(False)
        except Exception:
            pass
        self._emit()

    def _result_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        for key, lab in (
            ('showOverlay', '显示叠加'),
            ('showBoxes', '显示文字框'),
            ('showText', '显示识别文字'),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, True)))
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)

        wv = OrangeSwitch(bool(self.params.get('writeFlowVars', True)))
        wv.toggled.connect(lambda c: self._set_param('writeFlowVars', bool(c)))
        form.addRow('写入流程变量', wv)
        out_var = QLineEdit(str(self.params.get('resultVar') or 'ocr'))
        out_var.setObjectName('ocrResultVar')
        out_var.editingFinished.connect(
            lambda: self._set_param('resultVar', out_var.text().strip() or 'ocr')
        )
        form.addRow('结果变量前缀', out_var)

        je = OrangeSwitch(bool(self.params.get('judgeEnable', False)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断使能', je)
        exp = QLineEdit(str(self.params.get('expectedText') or ''))
        exp.setObjectName('ocrExpectedText')
        exp.setPlaceholderText('期望文本（空=只看置信度）')
        exp.editingFinished.connect(lambda: self._set_param('expectedText', exp.text()))
        form.addRow('期望文本', exp)
        jmc = QDoubleSpinBox(); jmc.setRange(0, 1); jmc.setDecimals(3); jmc.setSingleStep(0.05)
        jmc.setValue(float(self.params.get('judgeMinConfidence') or 0.5))
        jmc.valueChanged.connect(lambda v: self._set_param('judgeMinConfidence', float(v)))
        form.addRow('判定最低置信度', jmc)
        tip_j = QLabel('使能后：整体 confidence ≥ 阈值，且（若填期望）识别文本包含期望 → judgeOk。')
        tip_j.setWordWrap(True); tip_j.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_j)

        self._text_preview = QTextEdit()
        self._text_preview.setObjectName('ocrTextPreview')
        self._text_preview.setReadOnly(True)
        self._text_preview.setMaximumHeight(90)
        self._text_preview.setPlaceholderText('识别文本预览…')
        form.addRow('文本预览', self._text_preview)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('ocrLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)
        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('ocrLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)

        self._ocr_items_table = QTableWidget(0, 3)
        self._ocr_items_table.setObjectName('ocrItemsTable')
        self._ocr_items_table.setHorizontalHeaderLabels(['#', '文本', '置信度'])
        self._ocr_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ocr_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._ocr_items_table.setMaximumHeight(120)
        form.addRow('识别明细', self._ocr_items_table)

        try:
            self._refresh_live()
        except Exception:
            pass
        return w

    def _fill_ocr_items(self, items):
        table = getattr(self, '_ocr_items_table', None)
        if table is None:
            return
        table.setRowCount(0)
        for i, it in enumerate((items or [])[:40]):
            if not isinstance(it, dict):
                continue
            txt = str(it.get('text') or '')[:48]
            conf = it.get('confidence')
            conf_txt = f'{float(conf):.3f}' if conf is not None else '—'
            row = table.rowCount()
            table.insertRow(row)
            for c, t in enumerate((str(i + 1), txt, conf_txt)):
                table.setItem(row, c, QTableWidgetItem(t))

    def _refresh_live(self):
        lab = self._live_lab
        if lab is None:
            return
        res = self._find_step_result()
        if not res:
            lab.setText('实况：尚无本模块运行结果')
            if getattr(self, '_text_preview', None):
                self._text_preview.setPlainText('')
            self._fill_ocr_items([])
            return
        bits = []
        for k in ('status', 'count', 'text', 'confidence', 'passed', 'judgeOk', 'judgeStatus'):
            if k in res and res[k] is not None:
                val = res[k]
                if k == 'text' and isinstance(val, str) and len(val) > 40:
                    val = val[:40] + '…'
                bits.append(f'{k}={val}')
        if getattr(self, '_text_preview', None):
            self._text_preview.setPlainText(str(res.get('text') or ''))
        items = res.get('items') or []
        self._fill_ocr_items(items if isinstance(items, list) else [])
        flow = ((self._host_last().get('variables') or {}).get('flow') or {})
        prefix = str(self.params.get('resultVar') or 'ocr')
        for suffix in ('', '_text', '_count', '_confidence', '_judgeOk', '_ok'):
            key = prefix if suffix == '' else prefix + suffix
            if key in flow:
                bits.append(f'flow.{key}={flow[key]}')
        for k in ('ocr_count', 'ocr_confidence', 'ocr_text', 'ocr_judgeOk'):
            if k in flow:
                bits.append(f'flow.{k}={flow[k]}')
        lab.setText('实况：' + (' · '.join(bits[:12]) if bits else str(list(res.keys())[:8])))
