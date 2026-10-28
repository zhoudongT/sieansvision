"""生产任务 — VisionMaster p=40 可模仿薄壳（无机械手 SDK）。

设计态：任务名/配方/状态变量 + 建议流程链（图像→匹配→修正→查找→物理坐标→偏差→发送）。
运行态：productionTask 写入变量；真正视觉步骤由用户用既有算子串接。
"""
from copy import deepcopy

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPlainTextEdit, QHBoxLayout, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton,
)

from desktop.widgets.switch import OrangeSwitch

# Align with p40 mind-map (UI/流程 only; no robot SDK)

# op hint → catalog key (best-effort)
CHAIN_OP_MAP = [
    ('图像源', None),  # source — skip node
    ('camera_capture', 'camera_capture'),
    ('locate', 'locate'),
    ('pose_correct', 'pose_correct'),
    ('geometry', 'geometry'),
    ('nine_point', 'nine_point'),
    ('var_calc', 'var_calc'),
    ('format_data', 'format_data'),
    ('send_data', 'send_data'),
    ('receive_data', 'receive_data'),
    ('display', 'display'),
    ('ocr', 'ocr'),
]


def chain_to_operations(chain):
    """Turn DEFAULT_CHAIN rows into addable operations (skip source).

    Composite hints like ``send_data / format_data`` expand to format then send
    so 「应用到流程」 yields a runnable emit path (P0 p40).
    Physical-coord dual hints (``nine_point / var_calc``) prefer var_calc with
    demo scale expressions so the chain runs without a calibrated nine-point grid.
    """
    out = []
    for row in chain or []:
        op_hint = str(row.get('op') or '').lower()
        step_name = str(row.get('step') or '') or '步骤'
        vars_hint = str(row.get('vars') or '')
        # Composite: format + send → two nodes
        if 'format' in op_hint and 'send' in op_hint:
            out.append({'operation': 'format_data', 'name': f'{step_name}·格式化', 'vars': vars_hint})
            out.append({'operation': 'send_data', 'name': f'{step_name}·发送', 'vars': vars_hint})
            continue
        # Prefer var_calc for 偏差 / 移动量 / 物理坐标 even when nine_point listed
        if 'var_calc' in op_hint and (
            '偏差' in step_name or '移动' in step_name or '物理' in step_name
            or 'nine' not in op_hint
        ):
            out.append({'operation': 'var_calc', 'name': step_name, 'vars': vars_hint})
            continue
        key = None
        for needle, catalog_key in CHAIN_OP_MAP:
            if needle and needle.lower() in op_hint:
                key = catalog_key
                break
        if key is None:
            continue
        out.append({'operation': key, 'name': step_name, 'vars': vars_hint})
    return out


def seed_chain_step_params(operation, name='', vars_hint='', project=None, existing=None):
    """Seed demo-runnable params for a chain-inserted step (no robot SDK).

    - locate / pose_correct / geometry / display: normalize defaults + demo overlays
    - var_calc: expressions from vars_hint (物理坐标用 locate_x/geometry_x 比例)
    - format_data: MoveX/MoveY template → flow.formatted
    - send_data: LocalLoop device + variable formatted
    - nine_point: 3×3 demo grid so status can go ok without arm SDK
    """
    from copy import deepcopy as _dc
    op = str(operation or '')
    params = _dc(existing or {})
    names = [x.strip() for x in str(vars_hint or '').replace(';', ',').split(',') if x.strip()]
    step = str(name or '')

    if op == 'var_calc':
        from desktop.var_calc_panel import normalize_var_calc_params
        exprs = []
        if '偏差' in step or set(names) >= {'dx', 'dy'} or (not names and '偏差' in step):
            exprs = [
                dict(name='dx', expression='target_X_M - start_X_M', initial=0, outType='number', initOnRun=False),
                dict(name='dy', expression='target_Y_M - start_Y_M', initial=0, outType='number', initOnRun=False),
            ]
        elif '移动' in step or set(names) >= {'MoveX', 'MoveY'} or 'MoveX' in names:
            exprs = [
                dict(name='MoveX', expression='dx', initial=0, outType='number', initOnRun=False),
                dict(name='MoveY', expression='dy', initial=0, outType='number', initOnRun=False),
            ]
        elif set(names) >= {'start_X_M', 'start_Y_M'} or 'start_X_M' in names:
            # Demo mm = pixel * 0.1；locate_x 缺失时 varCalc 补 0
            exprs = [
                dict(name='start_X_M', expression='locate_x * 0.1', initial=0, outType='number', initOnRun=True),
                dict(name='start_Y_M', expression='locate_y * 0.1', initial=0, outType='number', initOnRun=True),
            ]
        elif set(names) >= {'target_X_M', 'target_Y_M'} or 'target_X_M' in names:
            exprs = [
                dict(name='target_X_M', expression='geometry_x * 0.1', initial=0, outType='number', initOnRun=True),
                dict(name='target_Y_M', expression='geometry_y * 0.1', initial=0, outType='number', initOnRun=True),
            ]
        elif '物理' in step and '目标' in step:
            exprs = [
                dict(name='target_X_M', expression='geometry_x * 0.1', initial=0, outType='number', initOnRun=True),
                dict(name='target_Y_M', expression='geometry_y * 0.1', initial=0, outType='number', initOnRun=True),
            ]
        elif '物理' in step:
            exprs = [
                dict(name='start_X_M', expression='locate_x * 0.1', initial=0, outType='number', initOnRun=True),
                dict(name='start_Y_M', expression='locate_y * 0.1', initial=0, outType='number', initOnRun=True),
            ]
        elif 'OCR' in step or 'ocr' in step.lower() or set(names) >= {'ocrCount', 'passGate'} or 'ocrCount' in names:
            exprs = [
                dict(name='ocrCount', expression='ocr_count', initial=0, outType='number', initOnRun=True),
                dict(name='ocrConf', expression='ocr_confidence', initial=0, outType='number', initOnRun=True),
                dict(name='ocrText', expression='ocr_text', initial='', outType='string', initOnRun=True),
                dict(name='ocrOk', expression='ocr_judgeOk', initial=0, outType='number', initOnRun=True),
                dict(name='passGate', expression='ocr_count > 0 && ocr_confidence >= 0.5 && ocr_judgeOk > 0', initial=0, outType='number', initOnRun=True),
                dict(name='commPayload', expression='"OCR ok=" + passGate + " count=" + ocrCount + " conf=" + ocrConf', initial='', outType='string', initOnRun=True),
            ]
        elif names:
            # Generic: init named vars to 0 so chain is editable/runnable
            for i, n in enumerate(names[:8]):
                exprs.append(dict(
                    name=n, expression='0', initial=0, outType='number', initOnRun=True,
                ))
        if exprs:
            params['expressions'] = exprs
            params['scope'] = 'flow'
            return normalize_var_calc_params(params)
        return normalize_var_calc_params(params)

    if op == 'format_data':
        params.setdefault('targetVar', 'formatted')
        params.setdefault('scope', 'flow')
        if 'OCR' in step or 'ocr' in step.lower() or 'ocrCount' in names or 'passGate' in names:
            params.setdefault('template', 'OCR ok={0} count={1} conf={2} text={3}')
            params.setdefault('args', 'passGate,ocrCount,ocrConf,ocrText')
        else:
            params.setdefault('template', 'MoveX={MoveX},MoveY={MoveY}')
            params.setdefault('args', 'MoveX,MoveY')
        return params

    if op == 'send_data':
        # Prefer LocalLoop from ensure_comm_manager defaults
        device = str(params.get('device') or '').strip()
        if not device:
            device = 'LocalLoop'
            try:
                from desktop.comm_manager import ensure_comm_manager
                cm = ensure_comm_manager(project or {})
                for d in (cm.get('devices') or []):
                    if (d.get('protocol') or '') == 'Local Bus' or (d.get('name') or '') == 'LocalLoop':
                        device = d.get('name') or 'LocalLoop'
                        break
            except Exception:
                pass
        params['device'] = device
        params.setdefault('channel', 'default')
        params.setdefault('encoding', 'utf-8')
        params.setdefault('appendCrLf', False)
        if 'OCR' in step or 'ocr' in step.lower() or 'LocalBus' in step:
            params['sourceMode'] = 'text'
            params.setdefault(
                'message',
                'RESULT ok=${flow.passGate} count=${flow.ocrCount} conf=${flow.ocrConf} text=${flow.ocrText}',
            )
            params.setdefault('sourceVar', '')
        else:
            params['sourceMode'] = 'variable'
            params['sourceScope'] = 'flow'
            params['sourceVar'] = str(params.get('sourceVar') or 'formatted')
            params.setdefault('message', '')
        return params

    if op == 'locate':
        from desktop.locate_match_panel import normalize_locate_params
        params.setdefault('minScore', 0.5)
        params.setdefault('maxMatches', 1)
        params.setdefault('showMatchBox', True)
        params.setdefault('showScore', True)
        params.setdefault('showCross', True)
        params.setdefault('note', 'prodchain demo · 无模板时仍可透传坐标 0')
        return normalize_locate_params(params)

    if op == 'pose_correct':
        from desktop.pose_correct_panel import normalize_pose_correct_params
        params.setdefault('fixtureSource', 'auto')
        params.setdefault('followRoi', True)
        params.setdefault('outputCoord', 'fixture')
        params.setdefault('bindField', 'matches[0]')
        return normalize_pose_correct_params(params)

    if op == 'geometry':
        from desktop.geometry_find_panel import normalize_geometry_params
        params.setdefault('feature', 'circles')
        params.setdefault('maxCount', 1)
        params.setdefault('showOverlay', True)
        params.setdefault('showCalipers', True)
        params.setdefault('showPoints', True)
        params.setdefault('caliperCount', 12)
        params.setdefault('caliperWidth', 20)
        params.setdefault('caliperLength', 40)
        params.setdefault('findMethod', 'caliper')
        if names:
            params.setdefault('note', f'chain vars: {", ".join(names)} → geometry_x/y')
        return normalize_geometry_params(params)

    if op == 'nine_point':
        from desktop.nine_point_panel import normalize_nine_point_params
        if not params.get('points'):
            pts = []
            for gy in (-1, 0, 1):
                for gx in (-1, 0, 1):
                    pts.append({
                        'index': len(pts) + 1,
                        'enabled': True,
                        'pixelX': float(gx * 100),
                        'pixelY': float(gy * 100),
                        'worldX': float(gx * 10),
                        'worldY': float(gy * 10),
                    })
            params['points'] = pts
        params.setdefault('method', 'affine')
        params.setdefault('unit', 'mm')
        params.setdefault('showPoints', True)
        params.setdefault('note', 'prodchain demo 3×3 grid（无臂测）')
        return normalize_nine_point_params(params)

    if op == 'display':
        from desktop.wave3_thin_panels import normalize_display_params
        params.setdefault('showOverlay', True)
        params.setdefault('showName', True)
        params.setdefault('fitMode', 'contain')
        return normalize_display_params(params)

    if op == 'ocr':
        from desktop.recognize_panels import _norm_ocr
        params.setdefault('minConfidence', 0.5)
        params.setdefault('judgeEnable', True)
        params.setdefault('expectedText', params.get('expectedText') or 'BATCH')
        params.setdefault('judgeMinConfidence', 0.5)
        params.setdefault('resultVar', 'ocr')
        params.setdefault('writeFlowVars', True)
        params.setdefault('showOverlay', True)
        params.setdefault('showBoxes', True)
        params.setdefault('showText', True)
        # vars_hint may carry expected text token
        for tok in names:
            if tok and tok not in ('ocr', 'ocrText', 'passGate') and not tok.startswith('ocr'):
                params['expectedText'] = tok
                break
        return _norm_ocr(params)

    return params or None


OCR_GATE_COMM_CHAIN = [
    {'step': '读取图像', 'op': '图像源', 'vars': ''},
    {'step': '字符识别 OCR', 'op': 'ocr', 'vars': 'BATCH'},
    {'step': 'OCR门限·OK/NG', 'op': 'var_calc', 'vars': 'ocrCount,ocrConf,ocrText,ocrOk,passGate,commPayload'},
    {'step': '格式化OCR报文', 'op': 'format_data', 'vars': ''},
    {'step': 'LocalBus发送', 'op': 'send_data', 'vars': ''},
    {'step': '结果显示', 'op': 'display', 'vars': ''},
]

DEFAULT_CHAIN = [
    {'step': '读取图像', 'op': '图像源 / camera_capture', 'vars': ''},
    {'step': '模板匹配', 'op': 'locate', 'vars': ''},
    {'step': '位置修正', 'op': 'pose_correct', 'vars': ''},
    {'step': '圆/特征查找', 'op': 'geometry (circles)', 'vars': 'target_X, target_Y'},
    {'step': '基准→物理坐标', 'op': 'nine_point / var_calc', 'vars': 'start_X_M, start_Y_M'},
    {'step': '目标→物理坐标', 'op': 'nine_point / var_calc', 'vars': 'target_X_M, target_Y_M'},
    {'step': '偏差', 'op': 'var_calc', 'vars': 'dx, dy'},
    {'step': '最终移动量', 'op': 'var_calc', 'vars': 'MoveX, MoveY'},
    {'step': '发送上位机', 'op': 'send_data / format_data', 'vars': ''},
    {'step': '结果显示', 'op': 'display', 'vars': ''},
]


def normalize_production_task_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('taskName', '')
    p.setdefault('recipe', '')
    p.setdefault('autoStart', False)
    p.setdefault('statusVar', 'taskStatus')
    p.setdefault('scope', 'global')
    p.setdefault('note', '')
    chain = p.get('chain')
    if not isinstance(chain, list) or not chain:
        p['chain'] = deepcopy(DEFAULT_CHAIN)
    else:
        # keep user chain; ensure keys
        norm = []
        for row in chain[:40]:
            if not isinstance(row, dict):
                continue
            norm.append({
                'step': str(row.get('step') or ''),
                'op': str(row.get('op') or ''),
                'vars': str(row.get('vars') or ''),
            })
        p['chain'] = norm or deepcopy(DEFAULT_CHAIN)
    return p


class ProductionTaskPanel(QWidget):
    changed = Signal(dict)
    applyFlow = Signal(list)  # list of {operation,name,params hint}
    applyFlowAndRun = Signal(list)  # apply then ▶单次试跑

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_production_task_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「生产任务设计」(p40)：任务名/配方写入变量，并给出可复用流程链示意。'
            '不接机械手/产线 SDK；请用既有算子（locate / pose_correct / nine_point / var_calc / send_data）串接。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._chain_tab()), '建议流程链')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')

    def _wrap(self, inner):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _emit(self):
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set(self, key, value):
        self.params[key] = value
        self._emit()

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        name = QLineEdit(str(self.params.get('taskName') or ''))
        name.setPlaceholderText('例如：对位贴合任务1')
        name.textChanged.connect(lambda t: self._set('taskName', t))
        form.addRow('任务名称', name)

        recipe = QLineEdit(str(self.params.get('recipe') or ''))
        recipe.setPlaceholderText('配方/方案名')
        recipe.textChanged.connect(lambda t: self._set('recipe', t))
        form.addRow('配方/方案', recipe)
        self._recipe_edit = recipe

        # 细妆⑮：产品变体快切
        var_row = QHBoxLayout()
        self._variant_chip = QComboBox()
        self._variant_chip.setObjectName('productionTaskVariantChip')
        self._variant_chip.setToolTip('产品变体快切：套用该变体下首条配方到当前工程')
        self._variant_chip.addItem('（无变体）', '')
        self._fill_variant_chip()
        self._variant_chip.currentIndexChanged.connect(self._on_variant_chip)
        var_row.addWidget(self._variant_chip, 1)
        b_apply = QPushButton('套用变体')
        b_apply.setObjectName('productionTaskVariantApplyBtn')
        b_apply.setToolTip('将所选变体的首条配方参数套用到当前流程')
        b_apply.clicked.connect(self._apply_variant_chip)
        var_row.addWidget(b_apply)
        form.addRow('产品变体', var_row)
        tip_r = QLabel('变体快切 / 完整换型：工具→产线配方/换型（保存快照 · 一键套用 · 工程库）')
        tip_r.setWordWrap(True); tip_r.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_r)

        scope = QComboBox()
        for k, lab in (('global', '全局'), ('flow', '流程')):
            scope.addItem(lab, k)
        i = scope.findData(self.params.get('scope') or 'global')
        scope.setCurrentIndex(i if i >= 0 else 0)
        scope.currentIndexChanged.connect(lambda *_: self._set('scope', scope.currentData()))
        form.addRow('变量作用域', scope)

        sv = QLineEdit(str(self.params.get('statusVar') or 'taskStatus'))
        sv.textChanged.connect(lambda t: self._set('statusVar', t.strip() or 'taskStatus'))
        from desktop.upstream_field_picker import fill_line_from_picker
        svrow = QHBoxLayout()
        svpick = QPushButton('插入上游字段')
        svpick.setToolTip('也可挑选上游字段；状态变量名仍可手填')
        svpick.clicked.connect(lambda *_: fill_line_from_picker(
            self, self.project, self.step.get('id'), sv, self._set, 'statusVar'))
        svrow.addWidget(sv, 1)
        svrow.addWidget(svpick)
        form.addRow('状态变量', svrow)

        auto = OrangeSwitch(bool(self.params.get('autoStart')))
        auto.toggled.connect(lambda on: self._set('autoStart', bool(on)))
        form.addRow('自动启动标记', auto)

        note = QPlainTextEdit(str(self.params.get('note') or ''))
        note.setPlaceholderText('备注（不落运行）')
        note.setMaximumHeight(80)
        note.textChanged.connect(lambda: self._set('note', note.toPlainText()))
        form.addRow('备注', note)
        return w


    def _fill_variant_chip(self):
        chip = getattr(self, '_variant_chip', None)
        if chip is None:
            return
        try:
            from desktop import recipe_library as rl
            variants = rl.list_variants(self.project)
            active = str((self.project or {}).get('activeRecipeVariant') or '')
        except Exception:
            variants, active = [], ''
        chip.blockSignals(True)
        chip.clear()
        if not variants:
            chip.addItem('（无变体）', '')
        else:
            chip.addItem('选择变体…', '')
            for v in variants:
                chip.addItem(v, v)
            if active:
                i = chip.findData(active)
                if i >= 0:
                    chip.setCurrentIndex(i)
        chip.blockSignals(False)

    def _on_variant_chip(self, *_):
        # selection alone does not apply — user clicks 套用变体, or double-intent via apply btn
        pass

    def _apply_variant_chip(self):
        chip = getattr(self, '_variant_chip', None)
        if chip is None:
            return
        variant = chip.currentData() or ''
        if not variant:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, '产品变体', '请先选择一个产品变体（在「产线配方」中为配方填写变体标签）。')
            return
        try:
            from desktop import recipe_library as rl
            recs = rl.recipes_for_variant(self.project, variant)
            if not recs:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, '产品变体', f'变体「{variant}」下无配方。')
                return
            entry = recs[0]
            stats = rl.apply_recipe(self.project, entry.get('id'))
            # sync recipe field
            name = stats.get('name') or entry.get('name') or ''
            if name and hasattr(self, '_recipe_edit'):
                self._recipe_edit.blockSignals(True)
                self._recipe_edit.setText(name)
                self._recipe_edit.blockSignals(False)
            self._set('recipe', name)
            self._fill_variant_chip()
            # notify parent MainWindow if reachable
            w = self.window()
            if w is not None and hasattr(w, 'refresh_variant_chip'):
                try:
                    w.refresh_variant_chip()
                except Exception:
                    pass
            if w is not None and hasattr(w, 'log'):
                try:
                    w.log(f"生产任务变体快切「{variant}」→ {name}")
                except Exception:
                    pass
            if w is not None and hasattr(w, 'document'):
                try:
                    w.document.mark_dirty()
                    w.document.changed.emit()
                except Exception:
                    pass
            # 细妆⑱：闭环刷 HMI 配方徽章（不强制进运行态）
            if w is not None and hasattr(w, 'sync_after_recipe_apply'):
                try:
                    w.sync_after_recipe_apply({
                        **stats,
                        'enterRun': False,
                        'trialOnce': False,
                    })
                except Exception:
                    pass
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '变体套用失败', str(exc))

    def _chain_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        tip = QLabel('p40 典型链（可编辑；「应用到当前流程」串节点；「并试跑」再▶单次。物理坐标用 var_calc 比例，无需九点标定臂）：')
        tip.setStyleSheet('color:#666;')
        lay.addWidget(tip)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['步骤', '建议算子', '变量'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._on_chain_edit)
        lay.addWidget(self.table, 1)
        bar = QHBoxLayout()
        reset = QPushButton('恢复默认链')
        reset.clicked.connect(self._reset_chain)
        add = QPushButton('添加行')
        add.clicked.connect(self._add_row)
        apply = QPushButton('应用到当前流程')
        apply.setObjectName('primaryButton')
        apply.setToolTip('按建议链依次添加算子并串线（可演示运行；无机械手 SDK）')
        apply.clicked.connect(self._apply_chain)
        trial = QPushButton('应用到流程并试跑')
        trial.setToolTip('应用建议链后立即▶单次试跑（无机械手 SDK；发送走 LocalLoop）')
        trial.clicked.connect(self._apply_chain_and_run)
        ocr_trial = QPushButton('OCR链并试跑')
        ocr_trial.setObjectName('productionTaskOcrChainTrialBtn')
        ocr_trial.setToolTip('套用 OCR→门限→format→LocalBus 发送链并▶单次（样张 text.png；无现场 TCP）')
        ocr_trial.clicked.connect(self._apply_ocr_chain_and_run)
        bar.addWidget(reset)
        bar.addWidget(add)
        bar.addWidget(apply)
        bar.addWidget(trial)
        bar.addWidget(ocr_trial)
        bar.addStretch(1)
        lay.addLayout(bar)
        self._reload_chain()
        return w

    def _reload_chain(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in self.params.get('chain') or []:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, key in enumerate(('step', 'op', 'vars')):
                self.table.setItem(r, c, QTableWidgetItem(str(row.get(key) or '')))
        self.table.blockSignals(False)

    def _on_chain_edit(self, *_):
        rows = []
        for r in range(self.table.rowCount()):
            rows.append({
                'step': (self.table.item(r, 0).text() if self.table.item(r, 0) else ''),
                'op': (self.table.item(r, 1).text() if self.table.item(r, 1) else ''),
                'vars': (self.table.item(r, 2).text() if self.table.item(r, 2) else ''),
            })
        self.params['chain'] = rows
        self._emit()

    def _reset_chain(self):
        self.params['chain'] = deepcopy(DEFAULT_CHAIN)
        self._reload_chain()
        self._emit()

    def _add_row(self):
        self.table.blockSignals(True)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(3):
            self.table.setItem(r, c, QTableWidgetItem(''))
        self.table.blockSignals(False)
        self._on_chain_edit()

    def _apply_chain(self):
        ops = chain_to_operations(self.params.get('chain') or DEFAULT_CHAIN)
        if not ops:
            return
        self.applyFlow.emit(ops)

    def _apply_chain_and_run(self):
        ops = chain_to_operations(self.params.get('chain') or DEFAULT_CHAIN)
        if not ops:
            return
        self.applyFlowAndRun.emit(ops)

    def _apply_ocr_chain_and_run(self):
        """Apply OCR→gate→Comm soft chain then trial-run (no field TCP)."""
        ops = chain_to_operations(OCR_GATE_COMM_CHAIN)
        for item in ops:
            if item.get('operation') == 'format_data':
                item['name'] = item.get('name') or '格式化OCR报文'
                item['vars'] = 'passGate,ocrCount,ocrConf,ocrText'
            if item.get('operation') == 'send_data':
                item['name'] = item.get('name') or 'LocalBus发送'
        self.applyFlowAndRun.emit(ops)

    def _result_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lab = QLabel(
            '运行结果字段：taskName / recipe / status(ready|running|unconfigured) / statusVar / scope。\n会写入 {statusVar}、{statusVar}_name、{statusVar}_recipe。'
        )
        lab.setWordWrap(True)
        lay.addWidget(lab)
        lay.addStretch(1)
        return w
