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
        if key in ('taskName', 'recipe', 'statusVar', 'scope', 'autoStart', 'chain', 'note'):
            try:
                self._refresh_production_result()
            except Exception:
                pass

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
        self._soft_writeback_status_vars(trial=True)
        self._soft_push_hmi_recipe(trial=True)
        self.applyFlowAndRun.emit(ops)
        self._record_trial_strip('建议链并试跑', ops)
        self._soft_co_update_trial_result(phase='trial', title='建议链并试跑', ops=ops)
        try:
            self._refresh_production_result()
        except Exception:
            pass

    def _apply_ocr_chain_and_run(self):
        """Apply OCR→gate→Comm soft chain then trial-run (no field TCP)."""
        ops = chain_to_operations(OCR_GATE_COMM_CHAIN)
        for item in ops:
            if item.get('operation') == 'format_data':
                item['name'] = item.get('name') or '格式化OCR报文'
                item['vars'] = 'passGate,ocrCount,ocrConf,ocrText'
            if item.get('operation') == 'send_data':
                item['name'] = item.get('name') or 'LocalBus发送'
        self._soft_writeback_status_vars(trial=True)
        self._soft_push_hmi_recipe(trial=True)
        self.applyFlowAndRun.emit(ops)
        self._record_trial_strip('OCR链并试跑', ops)
        self._soft_co_update_trial_result(phase='trial', title='OCR链并试跑', ops=ops)
        try:
            self._refresh_production_result()
        except Exception:
            pass

    def _result_tab(self):
        """结果显示：statusVar/recipe 写回预览 + HMI 条 + 试跑结果条（无微级 prop  cascade）。"""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        tip = QLabel(
            '运行写回 {statusVar} / {statusVar}_name / {statusVar}_recipe / {statusVar}_steps；'
            '下方为设计态写回预览、HMI 配方条与试跑结果条（软联调，无机械手 SDK）。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        lay.addWidget(tip)

        self._prod_writeback = QPlainTextEdit()
        self._prod_writeback.setObjectName('productionTaskWritebackPreview')
        self._prod_writeback.setReadOnly(True)
        self._prod_writeback.setMaximumHeight(140)
        self._prod_writeback.setStyleSheet('font-family:monospace;font-size:11px;background:#1e1e1e;color:#c5e1a5;')
        lay.addWidget(QLabel('statusVar / recipe 写回'))
        lay.addWidget(self._prod_writeback)

        self._prod_hmi_strip = QLabel()
        self._prod_hmi_strip.setObjectName('productionTaskHmiStrip')
        self._prod_hmi_strip.setWordWrap(True)
        self._prod_hmi_strip.setStyleSheet(
            'background:#2a3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
            'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
        )
        lay.addWidget(QLabel('HMI 配方/状态条（软预览）'))
        lay.addWidget(self._prod_hmi_strip)

        # Page-level chrome binding (substantial soft; not prop-chip cascade)
        lay.addWidget(QLabel('HMI 页铬绑定（配方/状态 → 运行页页眉·固定栏·状态轨）'))
        self._prod_page_chrome = QPlainTextEdit()
        self._prod_page_chrome.setObjectName('productionTaskPageChrome')
        self._prod_page_chrome.setReadOnly(True)
        self._prod_page_chrome.setMaximumHeight(130)
        self._prod_page_chrome.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#9ec9f0;'
        )
        lay.addWidget(self._prod_page_chrome)
        self._prod_page_chrome_meta = QLabel()
        self._prod_page_chrome_meta.setObjectName('productionTaskPageChromeMeta')
        self._prod_page_chrome_meta.setWordWrap(True)
        self._prod_page_chrome_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_page_chrome_meta)

        self._prod_trial_strip = QPlainTextEdit()
        self._prod_trial_strip.setObjectName('productionTaskTrialStrip')
        self._prod_trial_strip.setReadOnly(True)
        self._prod_trial_strip.setMaximumHeight(120)
        self._prod_trial_strip.setStyleSheet('font-family:monospace;font-size:11px;background:#263238;color:#80cbc4;')
        lay.addWidget(QLabel('试跑结果条'))
        lay.addWidget(self._prod_trial_strip)

        # Page-level trial→result co-update strip (HMI page-chrome + OK-NG dashboard)
        lay.addWidget(QLabel('试跑→结果 页铬联更（HMI 页铬 + OK-NG 看板）'))
        self._prod_trial_result_strip = QPlainTextEdit()
        self._prod_trial_result_strip.setObjectName('productionTaskTrialResultStrip')
        self._prod_trial_result_strip.setReadOnly(True)
        self._prod_trial_result_strip.setMaximumHeight(110)
        self._prod_trial_result_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
        )
        lay.addWidget(self._prod_trial_result_strip)
        self._prod_trial_result_meta = QLabel('(尚无试跑→结果联更)')
        self._prod_trial_result_meta.setObjectName('productionTaskTrialResultMeta')
        self._prod_trial_result_meta.setWordWrap(True)
        self._prod_trial_result_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_trial_result_meta)

        # Page-level Host SM liaison / Alarm clear closed loop (not micro chips)
        lay.addWidget(QLabel('试跑→结果 · Host SM 联调 / 报警清除闭环（页铬）'))
        self._prod_hostsm_loop_strip = QPlainTextEdit()
        self._prod_hostsm_loop_strip.setObjectName('productionTaskHostSmClosedLoopStrip')
        self._prod_hostsm_loop_strip.setReadOnly(True)
        self._prod_hostsm_loop_strip.setMaximumHeight(110)
        self._prod_hostsm_loop_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
        )
        self._prod_hostsm_loop_strip.setPlainText(
            '(尚无 Host SM 联调/报警清除闭环 — trial→result 后在此汇总)'
        )
        lay.addWidget(self._prod_hostsm_loop_strip)
        self._prod_hostsm_loop_meta = QLabel('(Host SM 闭环待命)')
        self._prod_hostsm_loop_meta.setObjectName('productionTaskHostSmClosedLoopMeta')
        self._prod_hostsm_loop_meta.setWordWrap(True)
        self._prod_hostsm_loop_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_hostsm_loop_meta)
        self._hostsm_loop_lines = []

        # Page-level variant + statusVar co-bind strip (recipe handoff target)
        lay.addWidget(QLabel('换型手递 · statusVar + 变体 页铬共绑（非属性芯片）'))
        self._prod_variant_status_strip = QPlainTextEdit()
        self._prod_variant_status_strip.setObjectName('productionTaskVariantStatusCoBindStrip')
        self._prod_variant_status_strip.setReadOnly(True)
        self._prod_variant_status_strip.setMaximumHeight(90)
        self._prod_variant_status_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#c5e1a5;'
        )
        self._prod_variant_status_strip.setPlainText('(尚未换型手递共绑 statusVar/变体)')
        lay.addWidget(self._prod_variant_status_strip)
        self._prod_variant_status_meta = QLabel('(变体·statusVar 共绑待命)')
        self._prod_variant_status_meta.setObjectName('productionTaskVariantStatusCoBindMeta')
        self._prod_variant_status_meta.setWordWrap(True)
        self._prod_variant_status_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_variant_status_meta)

        # Page-level result OK/NG → Comm sendEvents soft TX (closed-loop out; LocalBus only)
        lay.addWidget(QLabel('结果 OK/NG → Comm sendEvents 软 TX（闭环出站 · LocalBus）'))
        self._prod_result_comm_tx_strip = QPlainTextEdit()
        self._prod_result_comm_tx_strip.setObjectName('productionTaskResultOkNgCommTxStrip')
        self._prod_result_comm_tx_strip.setReadOnly(True)
        self._prod_result_comm_tx_strip.setMaximumHeight(110)
        self._prod_result_comm_tx_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2030;color:#9ec9f0;'
        )
        self._prod_result_comm_tx_strip.setPlainText(
            '(尚无结果 OK/NG → sendEvents 软 TX — trial→result 后在此汇总)'
        )
        lay.addWidget(self._prod_result_comm_tx_strip)
        self._prod_result_comm_tx_meta = QLabel('(结果→Comm 软 TX 待命)')
        self._prod_result_comm_tx_meta.setObjectName('productionTaskResultOkNgCommTxMeta')
        self._prod_result_comm_tx_meta.setWordWrap(True)
        self._prod_result_comm_tx_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_result_comm_tx_meta)
        self._result_comm_tx_lines = []

        # Page-level recipe variant ↔ chain soft preview chrome
        lay.addWidget(QLabel('配方变体列表 ↔ 生产链 软预览（页铬）'))
        self._prod_variant_chain_preview = QPlainTextEdit()
        self._prod_variant_chain_preview.setObjectName('productionTaskVariantChainPreviewStrip')
        self._prod_variant_chain_preview.setReadOnly(True)
        self._prod_variant_chain_preview.setMaximumHeight(110)
        self._prod_variant_chain_preview.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#c5e1a5;'
        )
        self._prod_variant_chain_preview.setPlainText('(尚未变体→生产链软预览)')
        lay.addWidget(self._prod_variant_chain_preview)
        self._prod_variant_chain_meta = QLabel('(变体·链预览待命)')
        self._prod_variant_chain_meta.setObjectName('productionTaskVariantChainPreviewMeta')
        self._prod_variant_chain_meta.setWordWrap(True)
        self._prod_variant_chain_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_variant_chain_meta)

        self._prod_result_meta = QLabel()
        self._prod_result_meta.setObjectName('productionTaskResultMeta')
        self._prod_result_meta.setWordWrap(True)
        self._prod_result_meta.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(self._prod_result_meta)

        bar = QHBoxLayout()
        refresh = QPushButton('刷新结果显示')
        refresh.setObjectName('productionTaskResultRefresh')
        refresh.clicked.connect(self._refresh_production_result)
        bar.addWidget(refresh)
        wb = QPushButton('写回工程变量')
        wb.setObjectName('productionTaskWritebackBtn')
        wb.setToolTip('把 recipe / statusVar 软写回工程变量表（设计态；不接产线 SDK）')
        wb.clicked.connect(lambda: self._soft_writeback_status_vars(trial=False))
        bar.addWidget(wb)
        hmi = QPushButton('推送到 HMI 条')
        hmi.setObjectName('productionTaskHmiPushBtn')
        hmi.setToolTip('把当前配方名推到运行态 HMI 配方徽章（若已打开）')
        hmi.clicked.connect(lambda: self._soft_push_hmi_recipe(trial=False))
        bar.addWidget(hmi)
        page = QPushButton('绑定 HMI 页铬')
        page.setObjectName('productionTaskPageChromeBindBtn')
        page.setToolTip(
            '把 recipe / statusVar / 任务状态一次性绑定到操作员 HMI 页级铬'
            '（页眉徽章·状态轨·固定栏·页铬横幅；非属性芯片级联）'
        )
        page.clicked.connect(lambda: self._soft_bind_hmi_page_chrome(trial=False))
        bar.addWidget(page)
        bar.addStretch(1)
        lay.addLayout(bar)
        lay.addStretch(1)
        self._trial_strip_lines = list(getattr(self, '_trial_strip_lines', []) or [])
        self._refresh_production_result()
        return w

    def _compute_status(self):
        name = str(self.params.get('taskName') or '').strip()
        if not name:
            return 'unconfigured'
        return 'running' if bool(self.params.get('autoStart')) else 'ready'

    def _writeback_map(self):
        status = self._compute_status()
        sv = str(self.params.get('statusVar') or 'taskStatus').strip() or 'taskStatus'
        scope = self.params.get('scope') or 'global'
        name = str(self.params.get('taskName') or '').strip()
        recipe = str(self.params.get('recipe') or '').strip()
        chain = self.params.get('chain') or []
        steps_n = len([r for r in chain if isinstance(r, dict) and (r.get('step') or r.get('op'))])
        hmi_recipe = recipe or name or '—'
        banner = (
            f'页铬 · 配方 {hmi_recipe} · 状态 {status} · {scope}.{sv} · 链 {steps_n} 步'
        )
        mapping = {
            f'{scope}.{sv}': status,
            f'{scope}.{sv}_name': name or '—',
            f'{scope}.{sv}_recipe': recipe or '—',
            f'{scope}.{sv}_steps': steps_n,
            f'{scope}.hmiRecipe': hmi_recipe,
            f'{scope}.hmiTaskStatus': status,
            f'{scope}.hmiPageChromeBanner': banner,
        }
        return mapping, status, sv, scope, name, recipe, steps_n

    def _soft_writeback_status_vars(self, *, trial=False):
        """Design-time soft write-back of recipe/statusVar into project variable bags."""
        mapping, status, sv, scope, name, recipe, steps_n = self._writeback_map()
        proj = self.project if isinstance(self.project, dict) else {}
        bag_key = 'globalVariables' if scope == 'global' else 'variables'
        # Also mirror into nested variables.{scope} shape used by some hosts
        try:
            flat = proj.setdefault('variables', {})
            if not isinstance(flat, dict):
                flat = {}
                proj['variables'] = flat
            scope_bag = flat.setdefault(scope if scope in ('flow', 'global', 'module') else 'global', {})
            if not isinstance(scope_bag, dict):
                scope_bag = {}
                flat[scope if scope in ('flow', 'global', 'module') else 'global'] = scope_bag
            for full, val in mapping.items():
                short = full.split('.', 1)[-1]
                scope_bag[short] = val
            # host chrome mirrors
            proj['activeRecipeName'] = recipe or name or proj.get('activeRecipeName') or ''
            if trial:
                proj['lastProductionTrial'] = {
                    'status': status,
                    'recipe': recipe,
                    'taskName': name,
                    'statusVar': sv,
                    'scope': scope,
                    'steps': steps_n,
                }
        except Exception:
            pass
        w = self.window()
        if w is not None and hasattr(w, 'document') and getattr(w, 'document', None) is not None:
            try:
                w.document.mark_dirty()
            except Exception:
                pass
        try:
            self._refresh_production_result()
        except Exception:
            pass
        return mapping

    def _soft_push_hmi_recipe(self, *, trial=False):
        """Push recipe/status soft chrome to operator HMI when available."""
        _mapping, status, sv, scope, name, recipe, steps_n = self._writeback_map()
        label = recipe or name or '—'
        # Update local HMI strip immediately
        if hasattr(self, '_prod_hmi_strip') and self._prod_hmi_strip is not None:
            trial_tag = ' · 试跑待回填' if trial else ''
            self._prod_hmi_strip.setText(
                f'配方 · {label}  │  状态 {status}  │  {scope}.{sv}  │  链 {steps_n} 步{trial_tag}'
            )
        w = self.window()
        if w is None:
            return
        hmi = getattr(w, 'operator_hmi', None)
        if hmi is not None and hasattr(hmi, 'set_recipe_chrome'):
            try:
                variant = ''
                try:
                    variant = str((self.project or {}).get('activeRecipeVariant') or '')
                except Exception:
                    variant = ''
                hmi.set_recipe_chrome(label, variant)
            except Exception:
                pass
        if trial and hmi is not None and hasattr(hmi, 'set_trial_backfill_pending'):
            try:
                hmi.set_trial_backfill_pending(True)
            except Exception:
                pass
        if hmi is not None and hasattr(hmi, 'update_fixed_bar_live'):
            try:
                hmi.update_fixed_bar_live(
                    run_status='试跑' if trial else status,
                    okng='—' if trial else ('OK' if status == 'ready' else status.upper()),
                    counters=f'链{steps_n}',
                    comm='LocalBus',
                )
            except Exception:
                pass
        # Always refresh page-chrome soft preview; bind live when HMI open
        try:
            self._soft_bind_hmi_page_chrome(trial=trial, push_live=hmi is not None)
        except Exception:
            pass

    def _page_chrome_snapshot(self, *, trial=False):
        """Page-level recipe/status chrome contract (not prop chips)."""
        mapping, status, sv, scope, name, recipe, steps_n = self._writeback_map()
        label = recipe or name or '—'
        banner = mapping.get(f'{scope}.hmiPageChromeBanner') or (
            f'页铬 · 配方 {label} · 状态 {status} · {scope}.{sv} · 链 {steps_n} 步'
        )
        variant = ''
        try:
            variant = str((self.project or {}).get('activeRecipeVariant') or '')
        except Exception:
            variant = ''
        host_state = 'Running' if status == 'running' else (
            'Idle' if status in ('ready', 'unconfigured') else 'Idle'
        )
        if trial:
            host_state = 'Running'
        return {
            'recipe': label,
            'variant': variant,
            'status': status,
            'statusVar': sv,
            'scope': scope,
            'taskName': name or '—',
            'chainSteps': steps_n,
            'banner': banner,
            'strip': (
                f'配方 · {label}  │  状态 {status}  │  {scope}.{sv}  │  链 {steps_n} 步'
                + (' · 试跑待回填' if trial else '')
            ),
            'runStatus': '试跑' if trial else status,
            'okng': '—' if trial else ('OK' if status == 'ready' else status.upper()),
            'counters': f'链{steps_n}',
            'comm': 'LocalBus',
            'hostState': host_state,
            'trial': bool(trial),
            'writeback': dict(mapping),
        }

    def _soft_bind_hmi_page_chrome(self, *, trial=False, push_live=True):
        """Bind production_task recipe/status into operator HMI page chrome."""
        snap = self._page_chrome_snapshot(trial=trial)
        # Local page-chrome preview (design-time)
        if hasattr(self, '_prod_page_chrome') and self._prod_page_chrome is not None:
            lines = [
                f"banner   = {snap['banner']}",
                f"recipe   = {snap['recipe']}"
                + (f" / {snap['variant']}" if snap.get('variant') else ''),
                f"status   = {snap['status']}  ·  hostState = {snap['hostState']}",
                f"bind     = {snap['scope']}.{snap['statusVar']}",
                f"task     = {snap['taskName']}  ·  chainSteps = {snap['chainSteps']}",
                f"run/okng = {snap['runStatus']} / {snap['okng']}  ·  counters = {snap['counters']}",
                f"comm     = {snap['comm']}  ·  trial = {snap['trial']}",
                'targets  = header.recipeBadge · stateRail · fixedBars · pageChromeBanner · strip.recipe',
            ]
            self._prod_page_chrome.setPlainText('\n'.join(lines))
        if hasattr(self, '_prod_page_chrome_meta') and self._prod_page_chrome_meta is not None:
            self._prod_page_chrome_meta.setText(
                f"页铬契约 · recipe↔徽章 · statusVar↔状态轨/固定栏 · "
                f"{snap['scope']}.{snap['statusVar']}={snap['status']} · "
                f"非属性芯片级联"
            )
        # Persist soft chrome bag on project
        proj = self.project if isinstance(self.project, dict) else {}
        try:
            proj['hmiPageChrome'] = {
                'recipe': snap['recipe'],
                'variant': snap.get('variant') or '',
                'status': snap['status'],
                'statusVar': snap['statusVar'],
                'scope': snap['scope'],
                'taskName': snap['taskName'],
                'chainSteps': snap['chainSteps'],
                'banner': snap['banner'],
                'hostState': snap['hostState'],
            }
        except Exception:
            pass
        if not push_live:
            return snap
        w = self.window()
        if w is None:
            return snap
        hmi = getattr(w, 'operator_hmi', None)
        if hmi is not None and hasattr(hmi, 'apply_production_page_chrome'):
            try:
                hmi.apply_production_page_chrome(snap)
            except Exception:
                pass
        return snap

    def _record_trial_strip(self, title, ops):
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        _mapping, status, sv, scope, name, recipe, steps_n = self._writeback_map()
        op_names = []
        for o in (ops or [])[:10]:
            op_names.append(str(o.get('name') or o.get('operation') or '?'))
        line = (
            f'[{ts}] {title} · status={status} · recipe={recipe or "—"} · '
            f'task={name or "—"} · {scope}.{sv} · ops={len(ops or [])} · '
            f'{" → ".join(op_names)}'
        )
        lines = list(getattr(self, '_trial_strip_lines', []) or [])
        lines.append(line)
        self._trial_strip_lines = lines[-12:]
        if hasattr(self, '_prod_trial_strip') and self._prod_trial_strip is not None:
            self._prod_trial_strip.setPlainText('\n'.join(self._trial_strip_lines))

    def _refresh_production_result(self):
        mapping, status, sv, scope, name, recipe, steps_n = self._writeback_map()
        lines = [f'{k} = {v!r}' for k, v in mapping.items()]
        if hasattr(self, '_prod_writeback') and self._prod_writeback is not None:
            self._prod_writeback.setPlainText('\n'.join(lines))
        label = recipe or name or '—'
        if hasattr(self, '_prod_hmi_strip') and self._prod_hmi_strip is not None:
            self._prod_hmi_strip.setText(
                f'配方 · {label}  │  状态 {status}  │  {scope}.{sv}  │  链 {steps_n} 步'
            )
        # Soft page-chrome preview (no live push on plain refresh)
        try:
            self._soft_bind_hmi_page_chrome(trial=False, push_live=False)
        except Exception:
            pass
        if hasattr(self, '_prod_trial_strip') and self._prod_trial_strip is not None:
            hist = list(getattr(self, '_trial_strip_lines', []) or [])
            if hist:
                self._prod_trial_strip.setPlainText('\n'.join(hist))
            else:
                self._prod_trial_strip.setPlainText(
                    '(尚无试跑记录 — 点「应用到流程并试跑」或「OCR链并试跑」后在此汇总)'
                )
        if hasattr(self, '_prod_result_meta') and self._prod_result_meta is not None:
            self._prod_result_meta.setText(
                f'taskName={name or "—"} · recipe={recipe or "—"} · status={status} · '
                f'statusVar={sv} · scope={scope} · chainSteps={steps_n} · '
                f'writebackKeys={len(mapping)}'
            )

    def _soft_co_update_trial_result(self, *, phase='trial', title='', ops=None, judge=None, result=None):
        """Page-level trial→result co-update: HMI page-chrome + OK-NG dashboard together."""
        from datetime import datetime
        result = result or {}
        snap = self._page_chrome_snapshot(trial=(phase == 'trial'))
        if phase == 'result':
            j = judge or result.get('judge') or 'OK'
            snap['trial'] = False
            snap['runStatus'] = 'completed'
            snap['okng'] = j
            snap['hostState'] = 'Idle' if str(j).upper() in ('OK', 'PASS', '良', '通过') else 'Alarm'
            snap['banner'] = (
                f"页铬 · 配方 {snap['recipe']} · 试跑结果 {j} · "
                f"{snap['scope']}.{snap['statusVar']} · 链 {snap['chainSteps']} 步"
            )
            # soft bump project counters for OK-NG dashboard
            proj = self.project if isinstance(self.project, dict) else {}
            try:
                bag = proj.setdefault('softOkNg', {'ok': 0, 'ng': 0})
                if str(j).upper() in ('OK', 'PASS', '良', '通过'):
                    bag['ok'] = int(bag.get('ok') or 0) + 1
                else:
                    bag['ng'] = int(bag.get('ng') or 0) + 1
                snap['okCount'] = bag['ok']
                snap['ngCount'] = bag['ng']
            except Exception:
                snap['okCount'] = 1 if str(j).upper() in ('OK', 'PASS') else 0
                snap['ngCount'] = 0 if str(j).upper() in ('OK', 'PASS') else 1
        else:
            snap['okng'] = '试跑中'
            snap['runStatus'] = '试跑'
            snap['hostState'] = 'Running'
            j = '—'

        ts = datetime.now().strftime('%H:%M:%S')
        op_n = len(ops or [])
        line = (
            f'[{ts}] {phase.upper()} · {title or "试跑"} · recipe={snap["recipe"]} · '
            f'status={snap["status"]} · host={snap["hostState"]} · okng={snap["okng"]} · '
            f'ops={op_n} · banner={snap["banner"][:48]}'
        )
        hist = list(getattr(self, '_trial_result_lines', []) or [])
        hist.append(line)
        self._trial_result_lines = hist[-16:]
        if hasattr(self, '_prod_trial_result_strip') and self._prod_trial_result_strip is not None:
            hdr = '── trial→result page-chrome co-update (HMI + OK-NG) ──'
            self._prod_trial_result_strip.setPlainText(hdr + '\n' + '\n'.join(self._trial_result_lines))
        if hasattr(self, '_prod_trial_result_meta') and self._prod_trial_result_meta is not None:
            self._prod_trial_result_meta.setText(
                f'联更 · phase={phase} · recipe={snap["recipe"]} · okng={snap["okng"]} · '
                f'host={snap["hostState"]} · 页铬+看板同刷 · 非属性芯片'
            )
        # Local page chrome preview
        try:
            self._soft_bind_hmi_page_chrome(trial=(phase == 'trial'), push_live=False)
            if hasattr(self, '_prod_page_chrome') and self._prod_page_chrome is not None:
                extra = (
                    f"\ncoUpdate = phase={phase} · okng={snap['okng']} · "
                    f"hostState={snap['hostState']} · targets=pageChrome+okNgDashboard"
                )
                self._prod_page_chrome.setPlainText(
                    self._prod_page_chrome.toPlainText() + extra
                )
        except Exception:
            pass
        # Live HMI co-update when open
        w = self.window()
        hmi = getattr(w, 'operator_hmi', None) if w is not None else None
        if hmi is not None:
            try:
                if hasattr(hmi, 'apply_trial_result_co_update'):
                    hmi.apply_trial_result_co_update(phase=phase, snapshot=snap, judge=j, result=result)
                elif hasattr(hmi, 'apply_production_page_chrome'):
                    hmi.apply_production_page_chrome(snap)
                    if hasattr(hmi, 'refresh_okng_dashboard_strip'):
                        hmi.refresh_okng_dashboard_strip(
                            ok_n=snap.get('okCount'),
                            ng_n=snap.get('ngCount'),
                            judge=snap.get('okng'),
                            host_state=snap.get('hostState'),
                            recipe=snap.get('recipe'),
                            status=snap.get('runStatus'),
                            status_var=f"{snap['scope']}.{snap['statusVar']}",
                        )
            except Exception:
                pass
        # Soft-simulate result phase shortly after trial when no live engine (design-time)
        if phase == 'trial' and not getattr(self, '_pending_live_trial', False):
            try:
                from PySide6.QtCore import QTimer
                def _soft_result(t=title, o=list(ops or [])):
                    try:
                        self._soft_co_update_trial_result(
                            phase='result', title=t or '试跑回填', ops=o,
                            judge='OK', result={'state': 'completed', 'judge': 'OK'},
                        )
                    except Exception:
                        pass
                QTimer.singleShot(220, _soft_result)
            except Exception:
                try:
                    self._soft_co_update_trial_result(
                        phase='result', title=title or '试跑回填', ops=ops,
                        judge='OK', result={'state': 'completed', 'judge': 'OK'},
                    )
                except Exception:
                    pass
        # Host SM liaison / Alarm clear closed loop (page chrome)
        try:
            self._soft_host_sm_liaison_alarm_closed_loop(
                phase=phase, snap=snap, judge=j if phase == 'result' else '—', result=result,
            )
        except Exception:
            pass
        # Result OK/NG → Comm sendEvents soft TX closed-loop out (LocalBus only)
        if phase == 'result':
            try:
                self._soft_result_okng_comm_send_tx(
                    judge=j, snap=snap, result=result,
                )
            except Exception:
                pass
        return snap


    def _soft_host_sm_liaison_alarm_closed_loop(self, *, phase='trial', snap=None, judge='—', result=None):
        """trial→result → Host SM liaison + Alarm clear closed loop (page chrome; no chips)."""
        from datetime import datetime
        snap = dict(snap or {})
        result = result or {}
        phase = str(phase or 'trial')
        j = str(judge or snap.get('okng') or '—')
        recipe = str(snap.get('recipe') or self.params.get('recipe') or '—')
        sv = str(snap.get('statusVar') or self.params.get('statusVar') or 'taskStatus')
        scope = str(snap.get('scope') or self.params.get('scope') or 'global')
        ts = datetime.now().strftime('%H:%M:%S')
        lines = list(getattr(self, '_hostsm_loop_lines', []) or [])
        host = None
        hmi = None
        w = self.window()
        if w is not None:
            hmi = getattr(w, 'operator_hmi', None)
            host = getattr(w, 'host_state_machine', None) or getattr(w, 'host_sm', None)
            if host is None and hmi is not None:
                host = getattr(hmi, '_host_sm', None)
        loop = {
            'phase': phase, 'judge': j, 'recipe': recipe,
            'statusVar': f'{scope}.{sv}', 'host': None,
            'liaison': [], 'alarm': None, 'cleared': False,
        }
        if phase == 'trial':
            lines.append(
                f'[{ts}] TRIAL · recipe={recipe} · {scope}.{sv} · host→Running · liaison=TRIAL_FIRE'
            )
            if host is not None:
                try:
                    if hasattr(host, 'set_state'):
                        host.set_state('Running', f'试跑 · {recipe}')
                    if hasattr(host, 'push_liaison_event'):
                        host.push_liaison_event(
                            f'试跑启动 · 配方 {recipe} · {scope}.{sv}',
                            kind='试跑启动', code='TRIAL_FIRE',
                        )
                        loop['liaison'].append('TRIAL_FIRE')
                    loop['host'] = getattr(host, '_state', None) or 'Running'
                except Exception:
                    pass
            loop['alarm'] = False
        else:
            failed = str(j).upper() in ('NG', 'FAIL', '拒', '不良') or result.get('state') == 'failed'
            if failed:
                lines.append(
                    f'[{ts}] RESULT NG · recipe={recipe} · host→Alarm · liaison=TRIAL_ALARM · 闭环待清除'
                )
                if host is not None:
                    try:
                        if hasattr(host, 'set_state'):
                            host.set_state('Alarm', f'试跑结果 {j} · {recipe}')
                        if hasattr(host, 'push_liaison_event'):
                            host.push_liaison_event(
                                f'试跑报警 · {j} · 配方 {recipe}',
                                kind='试跑报警', code='TRIAL_ALARM',
                            )
                            loop['liaison'].append('TRIAL_ALARM')
                        loop['host'] = getattr(host, '_state', None) or 'Alarm'
                    except Exception:
                        pass
                loop['alarm'] = True
                loop['cleared'] = False
            else:
                was_alarm = False
                if host is not None:
                    try:
                        was_alarm = getattr(host, '_state', '') == 'Alarm'
                    except Exception:
                        was_alarm = False
                lines.append(
                    f'[{ts}] RESULT OK · recipe={recipe} · '
                    + ('Alarm→Clear→Idle' if was_alarm else 'host→Idle')
                    + ' · liaison=ALARM_CLEAR/TRIAL_OK · 闭环闭合'
                )
                if host is not None:
                    try:
                        if was_alarm and hasattr(host, '_clear_alarm'):
                            host._clear_alarm()
                            loop['cleared'] = True
                        elif hasattr(host, 'set_state'):
                            host.set_state('Idle', f'试跑结果 OK · {recipe}')
                        if hasattr(host, 'push_liaison_event'):
                            code = 'ALARM_CLEAR' if was_alarm or loop.get('cleared') else 'TRIAL_OK'
                            kind = '报警清除' if code == 'ALARM_CLEAR' else '试跑通过'
                            host.push_liaison_event(
                                f'试跑闭环 · {kind} · 配方 {recipe} · {scope}.{sv}',
                                kind=kind, code=code,
                            )
                            loop['liaison'].append(code)
                        loop['host'] = getattr(host, '_state', None) or 'Idle'
                    except Exception:
                        pass
                loop['alarm'] = False
                if was_alarm:
                    loop['cleared'] = True
        self._hostsm_loop_lines = lines[-16:]
        hdr = '── trial→result ↔ Host SM liaison / Alarm clear closed loop ──'
        text = hdr + '\n' + '\n'.join(self._hostsm_loop_lines)
        if hasattr(self, '_prod_hostsm_loop_strip') and self._prod_hostsm_loop_strip is not None:
            self._prod_hostsm_loop_strip.setPlainText(text)
            if loop.get('alarm'):
                self._prod_hostsm_loop_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
                )
            elif loop.get('cleared') or (phase == 'result' and not loop.get('alarm')):
                self._prod_hostsm_loop_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
                )
            else:
                self._prod_hostsm_loop_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1a2430;color:#9ec9f0;'
                )
        if hasattr(self, '_prod_hostsm_loop_meta') and self._prod_hostsm_loop_meta is not None:
            self._prod_hostsm_loop_meta.setText(
                f"闭环 · phase={phase} · judge={j} · host={loop.get('host') or '—'} · "
                f"liaison={','.join(loop['liaison']) or '—'} · "
                f"{'已清除' if loop.get('cleared') else ('报警中' if loop.get('alarm') else '空闲')} · 页铬非芯片"
            )
        loop['driven'] = True
        if hmi is not None and hasattr(hmi, 'apply_host_sm_alarm_closed_loop'):
            try:
                hmi.apply_host_sm_alarm_closed_loop(
                    phase=phase, judge=j, snapshot=snap, loop=loop, result=result,
                )
            except Exception:
                pass
        return loop

    def soft_co_bind_variant_status_page_chrome(self, *, recipe=None, variant=None,
                                               status_var=None, scope=None, host_state=None,
                                               note='换型手递'):
        """Recipe lock handoff → statusVar + variant page-level co-bind (not micro chips)."""
        from datetime import datetime
        _mapping, status, sv0, scope0, name, recipe0, steps_n = self._writeback_map()
        recipe = str(recipe if recipe is not None else recipe0 or name or '—')
        sv = str(status_var if status_var is not None else sv0)
        scope = str(scope if scope is not None else scope0)
        if variant is None:
            try:
                variant = str((self.project or {}).get('activeRecipeVariant') or '')
            except Exception:
                variant = ''
        variant = str(variant or '')
        try:
            if recipe and recipe != '—':
                self.params['recipe'] = recipe
            self.params['statusVar'] = sv
            proj = self.project if isinstance(self.project, dict) else {}
            if variant:
                proj['activeRecipeVariant'] = variant
            proj['activeRecipeName'] = recipe
            chip = getattr(self, '_variant_chip', None)
            if chip is not None and variant:
                i = chip.findData(variant)
                if i < 0:
                    chip.addItem(variant, variant)
                    i = chip.findData(variant)
                if i >= 0:
                    chip.blockSignals(True)
                    chip.setCurrentIndex(i)
                    chip.blockSignals(False)
        except Exception:
            pass
        host_state = host_state or ('Running' if status == 'running' else 'Idle')
        ts = datetime.now().strftime('%H:%M:%S')
        snap = self._page_chrome_snapshot(trial=False)
        snap['recipe'] = recipe
        snap['variant'] = variant
        snap['statusVar'] = sv
        snap['scope'] = scope
        snap['hostState'] = host_state
        snap['banner'] = (
            f"页铬 · 配方 {recipe}"
            + (f"/{variant}" if variant else '')
            + f" · {scope}.{sv}={snap['status']} · 手递共绑 · {host_state}"
        )
        lines = [
            f'[{ts}] {note} · recipe={recipe}' + (f'/{variant}' if variant else ''),
            f'  statusVar = {scope}.{sv} = {snap["status"]}',
            f'  hostState = {host_state} · chainSteps = {snap["chainSteps"]}',
            f'  targets   = pageChromeBanner · recipeBadge · variantChip · statusRail · fixedBars',
            f'  banner    = {snap["banner"]}',
        ]
        if hasattr(self, '_prod_variant_status_strip') and self._prod_variant_status_strip is not None:
            self._prod_variant_status_strip.setPlainText('\n'.join(lines))
        if hasattr(self, '_prod_variant_status_meta') and self._prod_variant_status_meta is not None:
            self._prod_variant_status_meta.setText(
                f'共绑 · {scope}.{sv} · 变体 {variant or "—"} · 配方 {recipe} · '
                f'host={host_state} · 页铬非芯片'
            )
        try:
            self._soft_bind_hmi_page_chrome(trial=False, push_live=True)
        except Exception:
            pass
        w = self.window()
        hmi = getattr(w, 'operator_hmi', None) if w is not None else None
        if hmi is not None:
            try:
                if hasattr(hmi, 'co_bind_variant_status_page_chrome'):
                    hmi.co_bind_variant_status_page_chrome(
                        recipe=recipe, variant=variant, status_var=sv,
                        scope=scope, host_state=host_state, snapshot=snap, note=note,
                    )
                elif hasattr(hmi, 'apply_production_page_chrome'):
                    hmi.apply_production_page_chrome(snap)
            except Exception:
                pass
        return snap


    def _soft_result_okng_comm_send_tx(self, *, judge='OK', snap=None, result=None):
        """production_task result OK/NG → Comm sendEvents soft TX page strip (LocalBus only)."""
        from datetime import datetime
        snap = dict(snap or {})
        result = result or {}
        j = str(judge or snap.get('okng') or result.get('judge') or 'OK')
        upper = j.upper()
        is_ok = upper in ('OK', 'PASS', '良', '通过', 'TRUE', '1')
        recipe = str(snap.get('recipe') or self.params.get('recipe') or self.params.get('taskName') or '')
        sv = str(snap.get('statusVar') or self.params.get('statusVar') or 'taskStatus')
        scope = str(snap.get('scope') or self.params.get('scope') or 'global')
        ts = datetime.now().strftime('%H:%M:%S')
        # Resolve project + sendEvents
        proj = self.project if isinstance(self.project, dict) else {}
        w = self.window()
        if w is not None:
            try:
                doc = getattr(w, 'document', None) or getattr(w, 'doc', None)
                if doc is not None and getattr(doc, 'project', None):
                    proj = doc.project
            except Exception:
                pass
        cm = (proj.get('commManager') or {}) if isinstance(proj, dict) else {}
        send_rows = list(cm.get('sendEvents') or [])
        # Soft expand vars
        soft_vars = {
            'flow': {
                'okng': j, 'judge': j,
                'resultOk': 1 if is_ok else 0,
                'resultNg': 0 if is_ok else 1,
                'lastResult': j,
                'taskStatus': 'ready' if is_ok else 'alarm',
                'recipe': recipe,
            },
            'global': {
                'taskStatus': 'ready' if is_ok else 'alarm',
                'recipe': recipe,
                sv: 'ready' if is_ok else 'alarm',
            },
        }
        # Prefer live CommManagerDialog when open
        tx_n = 0
        devices = []
        lines = list(getattr(self, '_result_comm_tx_lines', []) or [])
        entries = []
        dlg = None
        if w is not None:
            try:
                dlg = getattr(w, 'comm_manager', None) or getattr(w, '_comm_manager', None)
            except Exception:
                dlg = None
            if dlg is None:
                try:
                    from desktop.comm_manager import CommManagerDialog
                    for child in w.findChildren(CommManagerDialog):
                        dlg = child
                        break
                except Exception:
                    pass
        if dlg is not None and hasattr(dlg, 'soft_result_okng_send_tx'):
            try:
                bag = dlg.soft_result_okng_send_tx(
                    judge=j, recipe=recipe, status_var=f'{scope}.{sv}',
                    vars_bag=soft_vars, snapshot=snap,
                )
                tx_n = int(bag.get('tx') or 0)
                devices = list(bag.get('devices') or [])
                entries = list(bag.get('entries') or [])
                for e in entries:
                    lines.append(e.get('line') or str(e))
            except Exception:
                dlg = None
        if not entries:
            # Local soft expand without dialog
            if not send_rows:
                send_rows = [
                    {'name': 'resultOkNg', 'device': 'LocalLoop',
                     'message': 'RESULT okng=${flow.okng} ok=${flow.resultOk} ng=${flow.resultNg} recipe=${flow.recipe}'},
                    {'name': 'status', 'device': 'LocalLoop',
                     'message': 'status=${flow.taskStatus} judge=${flow.judge}'},
                ]
            def _expand(msg, bag):
                out = str(msg or '')
                # flatten bag for ${a.b}
                flat = {}
                for scope_k, vals in (bag or {}).items():
                    if isinstance(vals, dict):
                        for k, v in vals.items():
                            flat[f'{scope_k}.{k}'] = v
                            flat[k] = v
                i = 0
                while '${' in out and i < 64:
                    i += 1
                    s = out.find('${')
                    e = out.find('}', s)
                    if s < 0 or e < 0:
                        break
                    key = out[s + 2:e].strip()
                    out = out[:s] + str(flat.get(key, '')) + out[e + 1:]
                return out
            for ev in send_rows:
                if not isinstance(ev, dict):
                    continue
                device = str(ev.get('device') or ev.get('deviceName') or 'LocalLoop')
                channel = str(ev.get('name') or ev.get('channel') or ev.get('topic') or 'result')
                raw = str(ev.get('message') or '')
                formatted = _expand(raw or f'RESULT okng={j}', soft_vars)
                note = 'format_data-expand' if '${' in raw else 'sendEvent-plain'
                line = (
                    f'[{ts}] TX→result {device}/{channel} okng={j} path={note} '
                    f'bytes={len(formatted.encode("utf-8"))} │ {formatted[:80]}'
                )
                entries.append({
                    'device': device, 'channel': channel, 'payload': formatted,
                    'note': note, 'okng': j, 'line': line,
                })
                lines.append(line)
                if device not in devices:
                    devices.append(device)
            tx_n = len(entries)
            # Optional node engine parity
            try:
                import json as _json, subprocess
                from pathlib import Path as _P
                root = _P(__file__).resolve().parents[1]
                eng = {
                    'commManager': {
                        'devices': cm.get('devices') or [{'name': 'LocalLoop', 'protocol': 'Local Bus'}],
                        'sendEvents': send_rows,
                    }
                }
                js = (
                    "const bus=require('./lib/comm-bus.cjs');bus.reset();"
                    f"const r=bus.softResultOkNgSendEventsTx({_json.dumps(eng)},{_json.dumps(j)},"
                    f"{_json.dumps({'recipe': recipe, 'taskStatus': soft_vars['flow']['taskStatus']})});"
                    "process.stdout.write(JSON.stringify({tx:(r.sendEntries||[]).length,devices:r.devices,okng:r.okng}));"
                )
                subprocess.run(
                    ['node', '-e', js], cwd=str(root),
                    capture_output=True, text=True, timeout=4,
                )
            except Exception:
                pass
        self._result_comm_tx_lines = lines[-20:]
        hdr = '── production_task result OK/NG → Comm sendEvents soft TX ──'
        text = hdr + '\n' + f'okng={j} · resultOk={1 if is_ok else 0} · TX={tx_n} · devices={",".join(devices) or "—"} · LocalBus\n'
        text += '\n'.join(self._result_comm_tx_lines)
        if hasattr(self, '_prod_result_comm_tx_strip') and self._prod_result_comm_tx_strip is not None:
            self._prod_result_comm_tx_strip.setPlainText(text)
            if is_ok:
                self._prod_result_comm_tx_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
                )
            else:
                self._prod_result_comm_tx_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
                )
        if hasattr(self, '_prod_result_comm_tx_meta') and self._prod_result_comm_tx_meta is not None:
            self._prod_result_comm_tx_meta.setText(
                f'闭环出站 · okng={j} · TX={tx_n} · devices={",".join(devices) or "—"} · '
                f'{scope}.{sv} · LocalBus · 无现场 TCP'
            )
        return {
            'okng': j, 'tx': tx_n, 'devices': devices, 'entries': entries,
            'resultOk': 1 if is_ok else 0, 'recipe': recipe,
        }

    def soft_preview_variant_prod_chain(self, *, recipe=None, variant=None, modules=None, note='变体链预览'):
        """Recipe variant list → production_task chain soft preview page chrome (not chips)."""
        from datetime import datetime
        _mapping, status, sv, scope, name, recipe0, steps_n = self._writeback_map()
        recipe = str(recipe if recipe is not None else recipe0 or name or '—')
        variant = str(variant or (self.project or {}).get('activeRecipeVariant') or '')
        chain = list(self.params.get('chain') or [])
        mods = list(modules or [])
        # Soft preview: if recipe modules given, show as alternate chain preview
        preview_rows = []
        if mods:
            for m in mods:
                if isinstance(m, dict):
                    preview_rows.append({
                        'step': str(m.get('name') or m.get('operation') or '步骤'),
                        'op': str(m.get('operation') or ''),
                        'vars': '',
                    })
        if not preview_rows:
            preview_rows = [
                {'step': str(r.get('step') or ''), 'op': str(r.get('op') or ''), 'vars': str(r.get('vars') or '')}
                for r in chain
            ]
        ts = datetime.now().strftime('%H:%M:%S')
        lines = [
            f'[{ts}] {note} · recipe={recipe}' + (f'/{variant}' if variant else ''),
            f'  statusVar={scope}.{sv} · liveChain={steps_n} · previewSteps={len(preview_rows)}',
            '  ── production_task chain soft preview ──',
        ]
        for i, r in enumerate(preview_rows[:24], 1):
            lines.append(f"  {i:02d}. {r.get('step') or '—'}  ·  op={r.get('op') or '—'}  ·  vars={r.get('vars') or '—'}")
        if hasattr(self, '_prod_variant_chain_preview') and self._prod_variant_chain_preview is not None:
            self._prod_variant_chain_preview.setPlainText('\n'.join(lines))
        if hasattr(self, '_prod_variant_chain_meta') and self._prod_variant_chain_meta is not None:
            self._prod_variant_chain_meta.setText(
                f'软预览 · 配方 {recipe}' + (f'/{variant}' if variant else '') +
                f' · 链 {len(preview_rows)} 步 · statusVar={scope}.{sv} · 页铬非芯片'
            )
        # Mirror onto HMI page chrome banner when open
        w = self.window()
        hmi = getattr(w, 'operator_hmi', None) if w is not None else None
        if hmi is not None and hasattr(hmi, 'apply_variant_chain_preview_chrome'):
            try:
                hmi.apply_variant_chain_preview_chrome(
                    recipe=recipe, variant=variant, steps=preview_rows,
                    status_var=f'{scope}.{sv}', note=note,
                )
            except Exception:
                pass
        return {
            'recipe': recipe, 'variant': variant, 'steps': preview_rows,
            'statusVar': sv, 'scope': scope, 'chainSteps': len(preview_rows),
        }
