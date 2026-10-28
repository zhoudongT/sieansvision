"""产线配方 / 一键换型 dialog — industrial one-click UX on project recipes + library."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QTextEdit, QMessageBox, QTabWidget, QWidget,
    QFormLayout, QGroupBox, QAbstractItemView, QSplitter, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QFileDialog,
)

from desktop.theme import TEXT, TEXT_MUTED, CARD, LINE
from desktop import recipe_library as rl


class RecipeSwitchDialog(QDialog):
    """One-click recipe switch / 换型 grounded in project.recipes + .sieans library."""

    recipeApplied = Signal(dict)   # stats from apply_recipe
    schemeLoaded = Signal(dict)    # full project dict for 换型 load
    recipesChanged = Signal()

    def __init__(self, document, root, parent=None):
        super().__init__(parent)
        self.document = document
        self.root = Path(root)
        self.setWindowTitle('产线配方 / 换型')
        self.resize(760, 520)
        self.setObjectName('recipeSwitchDialog')

        lay = QVBoxLayout(self)
        tip = QLabel(
            '产线换型：保存当前参数为命名配方，一键套用；或从工程库/模板整案换型。'
            '无云端 / 无机械手 SDK。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        lay.addWidget(tip)

        active = rl.active_recipe_name(document.project) or '（未指定）'
        self._active_lab = QLabel(f'当前配方：{active}')
        self._active_lab.setObjectName('recipeActiveLabel')
        self._active_lab.setStyleSheet(f'font-weight:600;color:{TEXT};padding:4px 0;')
        lay.addWidget(self._active_lab)

        tabs = QTabWidget()
        tabs.setObjectName('recipeSwitchTabs')
        lay.addWidget(tabs, 1)

        tabs.addTab(self._build_project_tab(), '本方案配方')
        tabs.addTab(self._build_library_tab(), '工程库换型')

        # 细妆⑱：换型 → 运行壳闭环选项
        loop = QHBoxLayout()
        self._chk_enter_run = QCheckBox('套用后切运行态')
        self._chk_enter_run.setObjectName('recipeEnterRunChk')
        self._chk_enter_run.setToolTip('一键换型后自动进入运行模式（操作员 HMI）')
        self._chk_enter_run.setChecked(True)
        loop.addWidget(self._chk_enter_run)
        self._chk_trial_once = QCheckBox('套用后单次试跑')
        self._chk_trial_once.setObjectName('recipeTrialOnceChk')
        self._chk_trial_once.setToolTip('切运行态后自动触发 ▶ 单次（需主窗在场）')
        loop.addWidget(self._chk_trial_once)
        loop.addStretch(1)
        lay.addLayout(loop)

        self._post_banner = QLabel('换型后：套用 → 可选切运行 / 单次试跑 → 状态栏提示可 ▶ 运行')
        self._post_banner.setObjectName('recipePostApplyBanner')
        self._post_banner.setWordWrap(True)
        self._post_banner.setStyleSheet(
            'background:#1a2430;color:#9ad;border:1px solid #3a5a7a;border-radius:4px;'
            'padding:6px 8px;font-size:12px;'
        )
        self._post_banner.setToolTip('套用成功后此处提示下一步：切运行 / 试跑 / 手动 ▶')
        lay.addWidget(self._post_banner)

        row = QHBoxLayout()
        # 细妆：明确「去运行」入口（无硬件）
        self._goto_run_btn = QPushButton('套用并去运行')
        self._goto_run_btn.setObjectName('recipeGotoRunBtn')
        self._goto_run_btn.setStyleSheet(
            'QPushButton{background:#2e7d32;color:#fff;font-weight:600;padding:6px 12px;}'
        )
        self._goto_run_btn.setToolTip('勾选切运行态后一键套用当前选中配方并进入运行闭环')
        self._goto_run_btn.clicked.connect(self._apply_and_goto_run)
        row.addWidget(self._goto_run_btn)
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(close_btn)
        lay.addLayout(row)

        self.refresh()

    # ----- 本方案配方 -----
    def _build_project_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        left = QVBoxLayout()
        self._recipe_list = QListWidget()
        self._recipe_list.setObjectName('recipeList')
        self._recipe_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._recipe_list.currentItemChanged.connect(self._on_sel)
        self._recipe_list.currentItemChanged.connect(self._refresh_diff_chip)
        left.addWidget(self._recipe_list, 1)

        btns = QHBoxLayout()
        b_save = QPushButton('保存当前为配方…')
        b_save.setObjectName('recipeSaveBtn')
        b_save.setToolTip('把当前流程各模块参数快照成命名配方')
        b_save.clicked.connect(self._save_current)
        btns.addWidget(b_save)
        b_apply = QPushButton('一键换型')
        b_apply.setObjectName('recipeApplyBtn')
        b_apply.setStyleSheet('QPushButton{background:#e87722;color:#111;font-weight:600;padding:6px 14px;}')
        b_apply.setToolTip('套用所选配方参数到匹配模块（按算子+名称）')
        b_apply.clicked.connect(self._apply_selected)
        btns.addWidget(b_apply)
        b_del = QPushButton('删除')
        b_del.setObjectName('recipeDeleteBtn')
        b_del.clicked.connect(self._delete_selected)
        btns.addWidget(b_del)
        left.addLayout(btns)
        # 细妆⑯：套用前 params delta chip
        self._diff_chip = QLabel('参数差分：选中配方后预览')
        self._diff_chip.setObjectName('recipeDiffChip')
        self._diff_chip.setWordWrap(True)
        self._diff_chip.setStyleSheet('color:#9ad;font-size:11px;padding:2px 4px;')
        self._diff_chip.setToolTip('套用前的参数/变量差分预览（不改工程）')
        left.addWidget(self._diff_chip)
        self._diff_list = QListWidget()
        self._diff_list.setObjectName('recipeDiffDetailList')
        self._diff_list.setMaximumHeight(90)
        self._diff_list.setStyleSheet('QListWidget{font-size:11px;color:#c8d0d8;background:#1a1e24;}')
        self._diff_list.setToolTip('行级差分：模块参数键 / 变量值（只读预览）')
        left.addWidget(self._diff_list)
        # 换型 dry-run 左右对照
        sb_head = QHBoxLayout()
        sb_lab = QLabel('换型对照（当前 | 配方）')
        sb_lab.setStyleSheet('color:#9ad;font-size:11px;font-weight:600;')
        sb_head.addWidget(sb_lab)
        self._dry_run_btn = QPushButton('Dry-run 对照')
        self._dry_run_btn.setObjectName('recipeDryRunDiffBtn')
        self._dry_run_btn.setToolTip('只刷新左右对照，不写入工程')
        self._dry_run_btn.clicked.connect(self._dry_run_side_by_side)
        sb_head.addWidget(self._dry_run_btn)
        self._preview_apply_btn = QPushButton('预览套用')
        self._preview_apply_btn.setObjectName('recipePreviewApplyBtn')
        self._preview_apply_btn.setToolTip(
            '在副本上 dry-run 套用并刷新对照（不写工程）；确认后可用「一键换型」写入并保留回滚点'
        )
        self._preview_apply_btn.clicked.connect(self._preview_apply)
        sb_head.addWidget(self._preview_apply_btn)
        self._rollback_btn = QPushButton('一键回滚')
        self._rollback_btn.setObjectName('recipeRollbackBtn')
        self._rollback_btn.setToolTip('撤销最近一次换型（多步回滚栈）；无硬件动作')
        self._rollback_btn.clicked.connect(self._rollback_last_apply)
        self._rollback_btn.setEnabled(False)
        sb_head.addWidget(self._rollback_btn)
        self._rollback_depth_lab = QLabel('')
        self._rollback_depth_lab.setObjectName('recipeRollbackDepthLab')
        self._rollback_depth_lab.setStyleSheet('color:#b9a;font-size:11px;')
        self._rollback_depth_lab.setToolTip('换型回滚历史栈深度（多步 · 无硬件）')
        sb_head.addWidget(self._rollback_depth_lab)
        sb_head.addStretch(1)
        left.addLayout(sb_head)
        self._diff_side = QTableWidget(0, 3)
        self._diff_side.setObjectName('recipeDiffSideBySide')
        self._diff_side.setHorizontalHeaderLabels(['键', '当前', '配方'])
        self._diff_side.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._diff_side.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._diff_side.setMaximumHeight(160)
        self._diff_side.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._diff_side.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._diff_side.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._diff_side.setStyleSheet(
            'QTableWidget{font-size:11px;color:#c8d0d8;background:#1a1e24;}'
        )
        self._diff_side.setToolTip('Dry-run 左右对照：当前工程 vs 配方快照（不改工程）')
        left.addWidget(self._diff_side)

        # Rollback history stack panel — pick / n-step (soft, no hardware)
        stack_box = QGroupBox('回滚历史栈')
        stack_box.setObjectName('recipeRollbackStackBox')
        stack_box.setStyleSheet('QGroupBox{font-size:11px;color:#b9a;font-weight:600;}')
        stack_lay = QVBoxLayout(stack_box)
        stack_lay.setContentsMargins(6, 8, 6, 6)
        stack_lay.setSpacing(4)
        self._rollback_stack_list = QListWidget()
        self._rollback_stack_list.setObjectName('recipeRollbackStackList')
        self._rollback_stack_list.setMaximumHeight(110)
        self._rollback_stack_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._rollback_stack_list.setStyleSheet(
            'QListWidget{font-size:11px;color:#c8d0d8;background:#1a1e24;}'
        )
        self._rollback_stack_list.setToolTip(
            '换型回滚历史（新→旧）。选中一条后「回滚到选中」会撤销该次及之后的套用。'
        )
        stack_lay.addWidget(self._rollback_stack_list)
        row = QHBoxLayout()
        self._rollback_n_spin = QSpinBox()
        self._rollback_n_spin.setObjectName('recipeRollbackNSpin')
        self._rollback_n_spin.setRange(1, 32)
        self._rollback_n_spin.setValue(1)
        self._rollback_n_spin.setToolTip('从栈顶回滚 N 步')
        self._rollback_n_spin.setFixedWidth(56)
        row.addWidget(QLabel('N步'))
        row.addWidget(self._rollback_n_spin)
        self._rollback_n_btn = QPushButton('回滚N步')
        self._rollback_n_btn.setObjectName('recipeRollbackNBtn')
        self._rollback_n_btn.setToolTip('从栈顶回滚 N 步（软回滚 · 无硬件）')
        self._rollback_n_btn.clicked.connect(self._rollback_n_steps)
        self._rollback_n_btn.setEnabled(False)
        row.addWidget(self._rollback_n_btn)
        self._rollback_pick_btn = QPushButton('回滚到选中')
        self._rollback_pick_btn.setObjectName('recipeRollbackPickBtn')
        self._rollback_pick_btn.setToolTip('回滚到选中历史项（含该项）· 软回滚 · 无硬件')
        self._rollback_pick_btn.clicked.connect(self._rollback_to_selected)
        self._rollback_pick_btn.setEnabled(False)
        row.addWidget(self._rollback_pick_btn)
        self._rollback_export_snap_chk = QCheckBox('含快照')
        self._rollback_export_snap_chk.setObjectName('recipeRollbackExportSnapChk')
        self._rollback_export_snap_chk.setToolTip(
            '导出时附带步骤快照体积（JSON 体积更大；CSV 仍不含快照）· 默认关 · 无硬件'
        )
        self._rollback_export_snap_chk.setChecked(False)
        self._rollback_export_snap_chk.toggled.connect(self._refresh_rollback_export_size_lab)
        row.addWidget(self._rollback_export_snap_chk)
        self._rollback_export_size_lab = QLabel('')
        self._rollback_export_size_lab.setObjectName('recipeRollbackExportSizeLab')
        self._rollback_export_size_lab.setStyleSheet('color:#8ab;font-size:11px;')
        self._rollback_export_size_lab.setToolTip('导出 JSON 体积估算（含/不含快照）· 无硬件')
        row.addWidget(self._rollback_export_size_lab)
        self._rollback_export_btn = QPushButton('导出栈')
        self._rollback_export_btn.setObjectName('recipeRollbackExportBtn')
        self._rollback_export_btn.setToolTip('导出回滚历史栈为 JSON/CSV（默认不含快照体积；勾选「含快照」写入）· 无硬件')
        self._rollback_export_btn.clicked.connect(self._export_rollback_stack)
        self._rollback_export_btn.setEnabled(False)
        row.addWidget(self._rollback_export_btn)
        self._rollback_clear_btn = QPushButton('清空栈')
        self._rollback_clear_btn.setObjectName('recipeRollbackClearBtn')
        self._rollback_clear_btn.setToolTip('清空回滚历史栈（不可恢复 · 软清除 · 无硬件）')
        self._rollback_clear_btn.clicked.connect(self._clear_rollback_stack)
        self._rollback_clear_btn.setEnabled(False)
        row.addWidget(self._rollback_clear_btn)
        row.addStretch(1)
        stack_lay.addLayout(row)
        left.addWidget(stack_box)
        lay.addLayout(left, 2)

        right = QVBoxLayout()
        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText('配方名')
        form.addRow('名称', self._name_edit)
        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText('备注（机台/产品/线体…）')
        self._note_edit.setMaximumHeight(100)
        form.addRow('备注', self._note_edit)
        self._meta_lab = QLabel('—')
        self._meta_lab.setStyleSheet(f'color:{TEXT_MUTED};')
        form.addRow('信息', self._meta_lab)
        self._variant_edit = QLineEdit()
        self._variant_edit.setObjectName('recipeVariantEdit')
        self._variant_edit.setPlaceholderText('产品型号 / 变体（如 A型）')
        form.addRow('产品变体', self._variant_edit)
        right.addLayout(form)
        b_rename = QPushButton('更新名称/备注/变体')
        b_rename.clicked.connect(self._update_meta)
        right.addWidget(b_rename)

        partial = QGroupBox('部分套用（变量子集 / 算子子集）')
        partial.setObjectName('recipePartialBox')
        pf = QFormLayout(partial)
        self._filter_variant = QComboBox()
        self._filter_variant.setObjectName('recipeVariantFilter')
        self._filter_variant.setEditable(False)
        self._filter_variant.currentIndexChanged.connect(lambda *_: self.refresh())
        pf.addRow('按变体筛选', self._filter_variant)
        self._partial_ops = QLineEdit()
        self._partial_ops.setObjectName('recipePartialOps')
        self._partial_ops.setPlaceholderText('算子白名单，逗号分隔；空=全部（例 measure_geom,caliper）')
        pf.addRow('仅算子', self._partial_ops)
        self._partial_vars = QLineEdit()
        self._partial_vars.setObjectName('recipePartialVars')
        self._partial_vars.setPlaceholderText('变量名白名单，逗号分隔；空=快照内全部')
        pf.addRow('仅变量', self._partial_vars)
        self._chk_steps_only = QCheckBox('只套用模块参数（跳过变量）')
        self._chk_vars_only = QCheckBox('只套用变量（跳过模块）')
        pf.addRow(self._chk_steps_only)
        pf.addRow(self._chk_vars_only)
        b_partial = QPushButton('部分套用所选配方')
        b_partial.setObjectName('recipePartialApplyBtn')
        b_partial.setToolTip('按上方白名单/开关做局部换型，不覆盖未选模块')
        b_partial.clicked.connect(self._apply_partial)
        pf.addRow(b_partial)
        right.addWidget(partial)
        right.addStretch(1)
        box = QGroupBox('配方详情')
        box.setLayout(right)
        lay.addWidget(box, 1)
        return w

    # ----- 工程库换型 -----
    def _build_library_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        tip = QLabel('从打开即跑 / 模板 / 本机库选择整案加载（等同换型号工程）。当前未保存改动请先另存。')
        tip.setWordWrap(True)
        tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        lay.addWidget(tip)
        self._lib_list = QListWidget()
        self._lib_list.setObjectName('recipeLibraryList')
        lay.addWidget(self._lib_list, 1)
        row = QHBoxLayout()
        b_ref = QPushButton('刷新列表')
        b_ref.clicked.connect(self._refresh_library)
        row.addWidget(b_ref)
        b_load = QPushButton('加载为当前方案（换型）')
        b_load.setObjectName('recipeLibraryLoadBtn')
        b_load.setStyleSheet('QPushButton{background:#e87722;color:#111;font-weight:600;padding:6px 14px;}')
        b_load.clicked.connect(self._load_library)
        row.addWidget(b_load)
        b_meas = QPushButton('测量链 · 换型→试跑')
        b_meas.setObjectName('recipeMeasureChainTrialBtn')
        b_meas.setToolTip(
            '一键选中 open-and-run-caliper-measure（或 measure）整案，'
            '并勾选「切运行态 + 单次试跑」后加载'
        )
        b_meas.setStyleSheet(
            'QPushButton{background:#2a4a3a;color:#9ed9a8;font-weight:700;padding:6px 12px;}'
        )
        b_meas.clicked.connect(self._load_measure_chain_trial)
        row.addWidget(b_meas)
        row.addStretch(1)
        lay.addLayout(row)
        return w

    def refresh(self):
        self._recipe_list.clear()
        project = self.document.project
        active = rl.active_recipe_id(project)
        # variant filter combo
        if hasattr(self, '_filter_variant'):
            cur = self._filter_variant.currentData() if self._filter_variant.count() else None
            self._filter_variant.blockSignals(True)
            self._filter_variant.clear()
            self._filter_variant.addItem('全部变体', '')
            for v in rl.list_variants(project):
                self._filter_variant.addItem(v, v)
            # restore
            if cur:
                i = self._filter_variant.findData(cur)
                if i >= 0:
                    self._filter_variant.setCurrentIndex(i)
            self._filter_variant.blockSignals(False)
            filt = self._filter_variant.currentData() or ''
        else:
            filt = ''
        recipes = rl.recipes_for_variant(project, filt) if filt else rl.list_recipes(project)
        for r in recipes:
            if not isinstance(r, dict):
                continue
            mark = '● ' if r.get('id') == active else '○ '
            tag = f" [{r.get('variant')}]" if r.get('variant') else ''
            sub = ''
            if r.get('stepOps') or r.get('varKeys'):
                sub = ' ·子集'
            item = QListWidgetItem(f"{mark}{r.get('name') or r.get('id')}{tag}{sub}")
            item.setData(Qt.ItemDataRole.UserRole, r.get('id'))
            self._recipe_list.addItem(item)
        name = rl.active_recipe_name(project) or '（未指定）'
        var_active = project.get('activeRecipeVariant') or ''
        extra = f' · 变体 {var_active}' if var_active else ''
        self._active_lab.setText(f'当前配方：{name}{extra}')
        self._refresh_library()
        try:
            self._refresh_diff_chip()
        except Exception:
            pass

        try:
            self._sync_rollback_btn()
        except Exception:
            pass

    def _refresh_library(self):
        self._lib_list.clear()
        for src in rl.discover_library_sources(self.root):
            item = QListWidgetItem(f"[{src['kind']}] {src['name']}")
            item.setData(Qt.ItemDataRole.UserRole, src['path'])
            item.setToolTip(src['path'])
            self._lib_list.addItem(item)

    def _selected_id(self):
        it = self._recipe_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_sel(self, cur, _prev=None):
        rid = cur.data(Qt.ItemDataRole.UserRole) if cur else None
        entry = next((r for r in rl.list_recipes(self.document.project)
                      if isinstance(r, dict) and r.get('id') == rid), None)
        if not entry:
            self._name_edit.clear(); self._note_edit.clear(); self._meta_lab.setText('—')
            if hasattr(self, '_variant_edit'):
                self._variant_edit.clear()
            return
        self._name_edit.setText(str(entry.get('name') or ''))
        self._note_edit.setPlainText(str(entry.get('note') or ''))
        if hasattr(self, '_variant_edit'):
            self._variant_edit.setText(str(entry.get('variant') or ''))
        sc = entry.get('stepCount') or len((entry.get('snapshot') or {}).get('steps') or [])
        ops = ','.join(entry.get('stepOps') or []) or '全部'
        vks = ','.join(entry.get('varKeys') or []) or '全部'
        self._meta_lab.setText(
            f"id={entry.get('id')} · 模块 {sc} · 算子[{ops}] · 变量[{vks}] · 更新 {entry.get('updatedAt') or '—'}"
        )

    def _save_current(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, '保存配方', '配方名称（产品型号/线体）：',
                                        text=rl.active_recipe_name(self.document.project) or '默认配方')
        if not ok:
            return
        note, ok2 = QInputDialog.getText(self, '保存配方', '备注（可选）：')
        if not ok2:
            note = ''
        variant, ok3 = QInputDialog.getText(self, '保存配方', '产品变体/型号（可选，如 A型）：',
                                            text=(self._variant_edit.text().strip()
                                                  if hasattr(self, '_variant_edit') else ''))
        if not ok3:
            variant = ''
        ops_txt, ok4 = QInputDialog.getText(
            self, '保存配方', '仅包含算子（逗号分隔，空=全部）：',
            text=self._partial_ops.text().strip() if hasattr(self, '_partial_ops') else '')
        if not ok4:
            ops_txt = ''
        vars_txt, ok5 = QInputDialog.getText(
            self, '保存配方', '仅包含变量名（逗号分隔，空=全部）：',
            text=self._partial_vars.text().strip() if hasattr(self, '_partial_vars') else '')
        if not ok5:
            vars_txt = ''
        step_ops = [x.strip() for x in ops_txt.split(',') if x.strip()] or None
        var_keys = [x.strip() for x in vars_txt.split(',') if x.strip()] or None
        p = deepcopy(self.document.project)
        entry = rl.capture_recipe(p, name, note, variant=variant,
                                  var_keys=var_keys, step_ops=step_ops)
        self.document.commit(p)
        self.refresh()
        self.recipesChanged.emit()
        QMessageBox.information(self, '配方已保存',
                                f"已保存「{entry['name']}」· {entry.get('stepCount', 0)} 个模块参数快照")


    def _refresh_diff_chip(self, *_):
        """细妆⑯：选中配方 → 参数差分 chip + 行级详情列表."""
        chip = getattr(self, '_diff_chip', None)
        dlist = getattr(self, '_diff_list', None)
        if chip is None:
            return
        rid = self._selected_id()
        if not rid:
            chip.setText('参数差分：选中配方后预览')
            chip.setStyleSheet('color:#9ad;font-size:11px;padding:2px 4px;')
            if dlist is not None:
                dlist.clear()
            self._fill_side_by_side(None)
            return
        try:
            diff = rl.diff_recipe(self.document.project, rid)
            chip_txt = rl.format_diff_chip(diff)
            n = ((diff.get('summary') or {}).get('stepsChanged', 0)
                 + (diff.get('summary') or {}).get('varsChanged', 0)
                 + (diff.get('summary') or {}).get('stepsMissing', 0))
            color = '#e87722' if n else '#3ecf8e'
            chip.setStyleSheet(f'color:{color};font-size:11px;padding:2px 4px;')
            chip.setText(f'参数差分：{chip_txt}')
            tip_lines = [chip_txt]
            for d in (diff.get('stepDeltas') or [])[:8]:
                tip_lines.append(
                    f"· {d.get('name') or d.get('op')}: "
                    f"{d.get('sample') or ','.join(d.get('changedKeys') or [])}"
                )
            for vd in (diff.get('varDeltas') or [])[:6]:
                tip_lines.append(
                    f"· {vd['scope']}.{vd['key']}: {vd.get('from')!r}→{vd.get('to')!r}"
                )
            chip.setToolTip('\n'.join(tip_lines))
            if dlist is not None:
                dlist.clear()
                for row in rl.format_diff_detail(diff):
                    item = QListWidgetItem(row.get('text') or '')
                    kind = row.get('kind') or 'info'
                    if kind == 'missing':
                        item.setForeground(Qt.GlobalColor.red)
                    elif kind == 'var':
                        item.setForeground(Qt.GlobalColor.cyan)
                    elif kind == 'step':
                        item.setForeground(Qt.GlobalColor.yellow)
                    dlist.addItem(item)
            self._fill_side_by_side(diff)
        except Exception as err:
            chip.setText(f'参数差分：{err}')
            chip.setStyleSheet('color:#e35d6a;font-size:11px;padding:2px 4px;')
            if dlist is not None:
                dlist.clear()
                dlist.addItem(QListWidgetItem(str(err)))




    def _fill_side_by_side(self, diff):
        table = getattr(self, '_diff_side', None)
        if table is None:
            return
        rows = rl.format_diff_side_by_side(diff) if diff else []
        table.setRowCount(0)
        if not diff:
            return
        for row in rows:
            i = table.rowCount()
            table.insertRow(i)
            kind = row.get('kind') or 'info'
            texts = [
                str(row.get('key') or ''),
                str(row.get('current') or ''),
                str(row.get('recipe') or ''),
            ]
            for c, text in enumerate(texts):
                it = QTableWidgetItem(text)
                if kind == 'missing':
                    it.setForeground(Qt.GlobalColor.red)
                elif kind == 'var':
                    it.setForeground(Qt.GlobalColor.cyan)
                elif kind == 'step':
                    it.setForeground(Qt.GlobalColor.yellow)
                table.setItem(i, c, it)

    def _dry_run_side_by_side(self):
        """Explicit dry-run: refresh chip + side-by-side without applying."""
        rid = self._selected_id()
        if not rid:
            banner = getattr(self, '_post_banner', None)
            if banner is not None:
                banner.setText('Dry-run：请先选中一条配方（未写入工程）')
            self._fill_side_by_side(None)
            return None
        try:
            diff = rl.diff_recipe(self.document.project, rid)
        except Exception as err:
            banner = getattr(self, '_post_banner', None)
            if banner is not None:
                banner.setText(f'Dry-run 失败：{err}')
            return None
        self._refresh_diff_chip()
        self._fill_side_by_side(diff)
        n = ((diff.get('summary') or {}).get('stepsChanged', 0)
             + (diff.get('summary') or {}).get('varsChanged', 0)
             + (diff.get('summary') or {}).get('stepsMissing', 0))
        banner = getattr(self, '_post_banner', None)
        if banner is not None:
            banner.setText(
                f'Dry-run 对照「{diff.get("name") or rid}」· Δ{n} · '
                f'{rl.format_diff_chip(diff)} · 未写入工程'
            )
            banner.setStyleSheet(
                'background:#1a2430;color:#9ad;border:1px solid #3a5a7a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;'
            )
        return diff

    def _preview_apply(self):
        """Dry-run apply-preview on a copy — refreshes side-by-side; never mutates project."""
        rid = self._selected_id()
        banner = getattr(self, '_post_banner', None)
        if not rid:
            if banner is not None:
                banner.setText('预览套用：请先选中一条配方（未写入工程）')
            self._fill_side_by_side(None)
            return None
        try:
            bag = rl.preview_apply_recipe(self.document.project, rid)
        except Exception as err:
            if banner is not None:
                banner.setText(f'预览套用失败：{err}')
                banner.setStyleSheet(
                    'background:#3a1a1a;color:#f88;border:1px solid #a44;border-radius:4px;'
                    'padding:6px 8px;font-size:12px;font-weight:600;'
                )
            return None
        diff = bag.get('diff')
        self._refresh_diff_chip()
        self._fill_side_by_side(diff)
        wa = bag.get('wouldApply') or {}
        if banner is not None:
            banner.setText(
                f'预览套用「{bag.get("name") or rid}」· 将写{wa.get("applied", 0)}'
                f' 跳过{wa.get("skipped", 0)} 变量{wa.get("varsApplied", 0)} · '
                f'{bag.get("chip") or ""} · 未写入工程 · 确认后点「一键换型」'
            )
            banner.setStyleSheet(
                'background:#1a2430;color:#9ad;border:1px solid #3a5a7a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;'
            )
        return bag

    def _rollback_last_apply(self):
        """One-click rollback of last apply_recipe_with_rollback — soft, no hardware."""
        p = deepcopy(self.document.project)
        try:
            stats = rl.rollback_last_recipe_apply(p)
        except Exception as err:
            QMessageBox.warning(self, '回滚失败', str(err))
            return
        if not stats.get('ok'):
            QMessageBox.information(self, '回滚', f"无可回滚快照：{stats.get('reason') or '—'}")
            self._sync_rollback_btn()
            return
        self.document.commit(p)
        self.refresh()
        self._sync_rollback_btn()
        self.recipesChanged.emit()
        banner = getattr(self, '_post_banner', None)
        if banner is not None:
            rem = stats.get('remaining')
            if rem is None:
                rem = stats.get('rollbackDepth')
            rem_txt = f' · 栈余{rem}' if rem is not None else ''
            banner.setText(
                f'已回滚换型「{stats.get("rolledBack") or "—"}」· 步骤{stats.get("steps", 0)}'
                f'{rem_txt} · 无硬件动作'
            )
            banner.setStyleSheet(
                'background:#2a2430;color:#d9b;border:1px solid #7a5a9a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;font-weight:600;'
            )
        QMessageBox.information(
            self, '回滚完成',
            f'已撤销「{stats.get("rolledBack") or "—"}」的套用（软回滚，无硬件）。',
        )

    def _sync_rollback_btn(self):
        btn = getattr(self, '_rollback_btn', None)
        if btn is None:
            return
        try:
            ready = rl.has_recipe_rollback(self.document.project)
            depth = rl.recipe_rollback_depth(self.document.project) if hasattr(rl, 'recipe_rollback_depth') else (1 if ready else 0)
            hist = rl.list_recipe_rollback_stack(self.document.project) if hasattr(rl, 'list_recipe_rollback_stack') else []
        except Exception:
            ready = False
            depth = 0
            hist = []
        btn.setEnabled(bool(ready))
        lab = getattr(self, '_rollback_depth_lab', None)
        if lab is not None:
            if depth:
                names = ' → '.join((h.get('name') or h.get('recipeId') or '?') for h in hist[-4:])
                lab.setText(f'栈×{depth}' + (f' · {names}' if names else ''))
            else:
                lab.setText('')
        if ready:
            top = hist[-1] if hist else {}
            name = top.get('name') or top.get('recipeId') or ''
            if not name:
                bag = (self.document.project or {}).get('_recipeRollbackSnap') or {}
                name = bag.get('name') or bag.get('recipeId') or ''
            btn.setToolTip(
                f'撤销最近换型「{name}」（栈深 {depth} · 软回滚 · 无硬件）'
            )
            btn.setText('一键回滚' if depth <= 1 else f'一键回滚×{depth}')
        else:
            btn.setToolTip('无可回滚快照 — 先经「一键换型/部分套用」写入回滚点')
            btn.setText('一键回滚')
        self._refresh_rollback_stack_list(hist if ready else [], depth=depth)



    def _refresh_rollback_stack_list(self, hist=None, *, depth: int = 0):
        """Fill history list (newest first) + enable pick/n buttons."""
        lst = getattr(self, '_rollback_stack_list', None)
        if lst is None:
            return
        hist = list(hist or [])
        lst.blockSignals(True)
        lst.clear()
        # newest first for operator UX
        for i, h in enumerate(reversed(hist)):
            name = h.get('name') or h.get('recipeId') or '—'
            when = str(h.get('appliedAt') or '')
            # stack index from oldest (keep-count target for to_index)
            oldest_idx = len(hist) - 1 - i
            label = f'#{len(hist) - i}  {name}'
            if when:
                label += f'  · {when[-19:]}'
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {
                'oldestIndex': oldest_idx,
                'fromTop': i + 1,  # steps to pop to remove this + newer
                'name': name,
            })
            lst.addItem(item)
        lst.blockSignals(False)
        spin = getattr(self, '_rollback_n_spin', None)
        if spin is not None:
            spin.setMaximum(max(1, int(depth or 1)))
            if depth:
                spin.setValue(min(spin.value(), depth))
        n_btn = getattr(self, '_rollback_n_btn', None)
        pick_btn = getattr(self, '_rollback_pick_btn', None)
        if n_btn is not None:
            n_btn.setEnabled(bool(depth))
        if pick_btn is not None:
            pick_btn.setEnabled(bool(depth) and lst.count() > 0)
        exp_btn = getattr(self, '_rollback_export_btn', None)
        clr_btn = getattr(self, '_rollback_clear_btn', None)
        snap_chk = getattr(self, '_rollback_export_snap_chk', None)
        if exp_btn is not None:
            exp_btn.setEnabled(bool(depth))
        if clr_btn is not None:
            clr_btn.setEnabled(bool(depth))
        if snap_chk is not None:
            snap_chk.setEnabled(bool(depth))
        try:
            self._refresh_rollback_export_size_lab()
        except Exception:
            pass


    def _export_include_snapshots(self) -> bool:
        chk = getattr(self, '_rollback_export_snap_chk', None)
        try:
            return bool(chk.isChecked()) if chk is not None else False
        except Exception:
            return False

    def _refresh_rollback_export_size_lab(self, *_):
        """Update snap-size estimate label beside 含快照 checkbox. Soft."""
        lab = getattr(self, '_rollback_export_size_lab', None)
        if lab is None:
            return {'ok': False, 'reason': 'no lab'}
        try:
            est = rl.estimate_rollback_export_bytes(
                self.document.project,
                include_snapshots=self._export_include_snapshots(),
            )
        except Exception as err:
            lab.setText('')
            return {'ok': False, 'reason': str(err)}
        if not est.get('depth'):
            lab.setText('')
            return est
        if est.get('includeSnapshots'):
            lab.setText(
                f"约 {est.get('human')}（含快照 · 无快照 {est.get('withoutSnapHuman')}）"
            )
        else:
            lab.setText(
                f"约 {est.get('human')}（无快照 · 含则 {est.get('withSnapHuman')}）"
            )
        return est

    def _export_rollback_stack(self):
        """Export rollback history stack to JSON or CSV (soft; optional snapshots)."""
        p = self.document.project
        include_snap = self._export_include_snapshots()
        bag = rl.export_recipe_rollback_stack(p, include_snapshots=include_snap)
        if not bag.get('ok') or not bag.get('depth'):
            QMessageBox.information(self, '导出栈', '回滚历史栈为空，无可导出。')
            return
        path, _filt = QFileDialog.getSaveFileName(
            self, '导出回滚历史栈',
            str(self.root / 'recipe-rollback-stack.json'),
            'JSON (*.json);;CSV (*.csv)',
        )
        if not path:
            return
        path = str(path)
        try:
            if path.lower().endswith('.csv'):
                import csv
                rows = rl.rollback_stack_export_csv_rows(bag)
                with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                    csv.writer(f).writerows(rows)
                snap_note = 'CSV 不含快照'
            else:
                import json
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(bag, f, ensure_ascii=False, indent=2)
                snap_note = '含快照体积' if include_snap else '无快照体积'
        except Exception as err:
            QMessageBox.warning(self, '导出失败', str(err))
            return
        banner = getattr(self, '_post_banner', None)
        if banner is not None:
            banner.setText(
                f'已导出回滚栈 {bag.get("depth")} 条 → {path} · {snap_note} · 无硬件'
            )
            banner.setStyleSheet(
                'background:#1a2430;color:#9cd;border:1px solid #3a6a8a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;font-weight:600;'
            )
        QMessageBox.information(
            self, '导出完成',
            f'已导出 {bag.get("depth")} 条回滚历史（{snap_note}）。\n{path}',
        )

    def _clear_rollback_stack(self):
        """Clear rollback history stack after confirm (soft / irreversible)."""
        depth = rl.recipe_rollback_depth(self.document.project)
        if depth <= 0:
            QMessageBox.information(self, '清空栈', '回滚历史栈已空。')
            return
        ans = QMessageBox.question(
            self, '清空回滚栈',
            f'将清空全部 {depth} 条回滚历史（不可恢复 · 软清除 · 无硬件）。继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        stats = rl.clear_recipe_rollback_stack(p)
        self.document.commit(p)
        self.refresh()
        self._sync_rollback_btn()
        self.recipesChanged.emit()
        banner = getattr(self, '_post_banner', None)
        if banner is not None:
            banner.setText(
                f'已清空回滚栈 {stats.get("cleared", 0)} 条 · 无硬件'
            )
            banner.setStyleSheet(
                'background:#2a2430;color:#d9b;border:1px solid #7a5a9a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;font-weight:600;'
            )
        QMessageBox.information(
            self, '已清空',
            f'已清空 {stats.get("cleared", 0)} 条回滚历史（软清除，无硬件）。',
        )

    def _rollback_n_steps(self):
        """N-step rollback from stack top (soft)."""
        spin = getattr(self, '_rollback_n_spin', None)
        n = int(spin.value()) if spin is not None else 1
        p = deepcopy(self.document.project)
        try:
            stats = rl.rollback_recipe_n_steps(p, n)
        except Exception as err:
            QMessageBox.warning(self, '回滚失败', str(err))
            return
        if not stats.get('ok'):
            QMessageBox.information(self, '回滚', f"未能回滚：{stats.get('reason') or '—'}")
            self._sync_rollback_btn()
            return
        self.document.commit(p)
        self.refresh()
        self._sync_rollback_btn()
        self.recipesChanged.emit()
        banner = getattr(self, '_post_banner', None)
        if banner is not None:
            names = '、'.join(str(x) for x in (stats.get('rolledBack') or []) if x) or '—'
            banner.setText(
                f'已回滚 {stats.get("steps")} 步 · {names} · 栈余{stats.get("remaining", 0)} · 无硬件'
            )
            banner.setStyleSheet(
                'background:#2a2430;color:#d9b;border:1px solid #7a5a9a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;font-weight:600;'
            )
        QMessageBox.information(
            self, '回滚完成',
            f'已回滚 {stats.get("steps")} 步（软回滚，无硬件）。\n栈余 {stats.get("remaining", 0)}',
        )

    def _rollback_to_selected(self):
        """Pick history row → roll back that entry and everything newer."""
        lst = getattr(self, '_rollback_stack_list', None)
        if lst is None or lst.currentItem() is None:
            QMessageBox.information(self, '回滚', '请先在回滚历史栈中选中一条。')
            return
        data = lst.currentItem().data(Qt.ItemDataRole.UserRole) or {}
        from_top = int(data.get('fromTop') or 0)
        name = data.get('name') or '—'
        if from_top <= 0:
            QMessageBox.information(self, '回滚', '选中项无效。')
            return
        ans = QMessageBox.question(
            self, '回滚到选中',
            f'将回滚 {from_top} 步至「{name}」及之后（软回滚，无硬件）。继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        try:
            if hasattr(rl, 'rollback_recipe_to_index'):
                # keep entries before selected → oldestIndex means keep that many? 
                # fromTop = steps to pop; keep = depth - fromTop
                depth = rl.recipe_rollback_depth(p)
                keep = max(0, depth - from_top)
                stats = rl.rollback_recipe_to_index(p, keep)
            else:
                stats = rl.rollback_recipe_n_steps(p, from_top)
        except Exception as err:
            QMessageBox.warning(self, '回滚失败', str(err))
            return
        if not stats.get('ok'):
            QMessageBox.information(self, '回滚', f"未能回滚：{stats.get('reason') or '—'}")
            self._sync_rollback_btn()
            return
        self.document.commit(p)
        self.refresh()
        self._sync_rollback_btn()
        self.recipesChanged.emit()
        banner = getattr(self, '_post_banner', None)
        if banner is not None:
            banner.setText(
                f'已回滚到「{name}」· {stats.get("steps")}步 · 栈余{stats.get("remaining", 0)} · 无硬件'
            )
            banner.setStyleSheet(
                'background:#2a2430;color:#d9b;border:1px solid #7a5a9a;border-radius:4px;'
                'padding:6px 8px;font-size:12px;font-weight:600;'
            )
        QMessageBox.information(
            self, '回滚完成',
            f'已回滚到「{name}」（{stats.get("steps")} 步 · 软回滚，无硬件）。',
        )


    def _update_post_banner(self, stats=None, *, error: str = ''):
        banner = getattr(self, '_post_banner', None)
        if banner is None:
            return
        if error:
            banner.setText(f'换型失败：{error}')
            banner.setStyleSheet(
                'background:#3a1a1a;color:#f88;border:1px solid #a44;border-radius:4px;'
                'padding:6px 8px;font-size:12px;font-weight:600;'
            )
            return
        stats = stats or {}
        name = str(stats.get('name') or '')
        enter = bool(stats.get('enterRun'))
        trial = bool(stats.get('trialOnce'))
        applied = stats.get('applied', 0)
        skipped = stats.get('skipped', 0)
        bits = [f'已套用「{name or "—"}」· 写入{applied} 跳过{skipped}']
        if enter and trial:
            bits.append('下一步：切运行态 → 自动单次试跑')
        elif enter:
            bits.append('下一步：已切/将切运行态 · 点 ▶ 开始 或工具栏运行')
        elif trial:
            bits.append('下一步：设计态单次试跑（未勾选切运行）')
        else:
            bits.append('下一步：关闭本窗 → 点工具栏 ▶ 运行（或勾选上方闭环选项再套用）')
        banner.setText(' · '.join(bits))
        banner.setStyleSheet(
            'background:#1a2e24;color:#8fd98f;border:1px solid #2e7d32;border-radius:4px;'
            'padding:6px 8px;font-size:12px;font-weight:600;'
        )

    def _apply_and_goto_run(self):
        """Force enterRun on, then apply selected (project tab) for clear apply→run path."""
        if getattr(self, '_chk_enter_run', None) is not None:
            self._chk_enter_run.setChecked(True)
        # Prefer project-tab selection; fall back to library measure trial
        rid = self._selected_id()
        if rid:
            self._apply_selected()
        else:
            # try library measure chain as soft fallback
            try:
                self._load_measure_chain_trial()
            except Exception:
                QMessageBox.information(self, '去运行', '请先在「本方案配方」选中一条，或使用工程库换型。')
                return

    def _stamp_post_apply(self, stats: dict) -> dict:
        """细妆⑱：把闭环选项写入 stats，供 MainWindow.sync_after_recipe_apply."""
        stats = dict(stats or {})
        stats['enterRun'] = bool(getattr(self, '_chk_enter_run', None) and self._chk_enter_run.isChecked())
        stats['trialOnce'] = bool(getattr(self, '_chk_trial_once', None) and self._chk_trial_once.isChecked())
        return stats

    def _apply_selected(self):
        rid = self._selected_id()
        if not rid:
            QMessageBox.warning(self, '换型', '请先选择一个配方')
            return
        try:
            diff = rl.diff_recipe(self.document.project, rid)
            chip = rl.format_diff_chip(diff)
        except Exception as err:
            chip = str(err)
        ans = QMessageBox.question(
            self, '一键换型',
            '将把所选配方的模块参数套用到当前流程（按算子+名称匹配）。\n'
            f'差分预览：{chip}\n继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        try:
            stats = rl.apply_recipe_with_rollback(p, rid)
        except Exception as err:
            QMessageBox.warning(self, '换型失败', str(err))
            return
        self.document.commit(p)
        self.refresh()
        self._sync_rollback_btn()
        stats = self._stamp_post_apply(stats)
        self.recipeApplied.emit(stats)
        self.recipesChanged.emit()
        self._update_post_banner(stats)
        next_hint = '已勾选切运行' if stats.get('enterRun') else '可点「套用并去运行」或工具栏 ▶'
        if stats.get('trialOnce'):
            next_hint += ' · 将单次试跑'
        if stats.get('rollbackReady'):
            next_hint += ' · 可一键回滚'
        QMessageBox.information(
            self, '换型完成 · 可运行',
            f"已套用「{stats.get('name')}」\n匹配写入 {stats.get('applied')} · 跳过 {stats.get('skipped')} · 变量 {stats.get('varsApplied')}\n下一步：{next_hint}",
        )

    def _parse_csv_field(self, edit):
        txt = (edit.text() if edit is not None else '') or ''
        items = [x.strip() for x in txt.split(',') if x.strip()]
        return items or None

    def _apply_partial(self):
        rid = self._selected_id()
        if not rid:
            QMessageBox.warning(self, '部分套用', '请先选择一个配方')
            return
        step_ops = self._parse_csv_field(getattr(self, '_partial_ops', None))
        var_keys = self._parse_csv_field(getattr(self, '_partial_vars', None))
        steps_only = bool(getattr(self, '_chk_steps_only', None) and self._chk_steps_only.isChecked())
        vars_only = bool(getattr(self, '_chk_vars_only', None) and self._chk_vars_only.isChecked())
        if steps_only and vars_only:
            QMessageBox.warning(self, '部分套用', '「只套用模块」与「只套用变量」不能同时勾选')
            return
        hint = []
        if step_ops:
            hint.append('算子=' + ','.join(step_ops))
        if var_keys:
            hint.append('变量=' + ','.join(var_keys))
        if steps_only:
            hint.append('仅模块')
        if vars_only:
            hint.append('仅变量')
        if not hint:
            hint.append('（使用配方自带子集；若无子集则等同全量）')
        try:
            diff = rl.diff_recipe(
                self.document.project, rid,
                var_keys=var_keys, step_ops=step_ops,
                steps_only=steps_only, vars_only=vars_only,
            )
            chip = rl.format_diff_chip(diff)
        except Exception as err:
            chip = str(err)
        ans = QMessageBox.question(
            self, '部分套用',
            '按局部规则套用所选配方：\n' + ' · '.join(hint)
            + '\n差分预览：' + chip + '\n继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        try:
            stats = rl.apply_recipe_with_rollback(
                p, rid, var_keys=var_keys, step_ops=step_ops,
                steps_only=steps_only, vars_only=vars_only,
            )
        except Exception as err:
            QMessageBox.warning(self, '部分套用失败', str(err))
            return
        self.document.commit(p)
        self.refresh()
        self._sync_rollback_btn()
        stats = self._stamp_post_apply(stats)
        self.recipeApplied.emit(stats)
        self._update_post_banner(stats)
        self.recipesChanged.emit()
        QMessageBox.information(
            self, '部分套用完成',
            '「%s」变体 %s\n模块写入 %s · 跳过 %s · 变量 %s%s' % (
                stats.get('name'), stats.get('variant') or '—',
                stats.get('applied'), stats.get('skipped'), stats.get('varsApplied'),
                ' · 可一键回滚' if stats.get('rollbackReady') else '',
            ),
        )

    def _delete_selected(self):
        rid = self._selected_id()
        if not rid:
            return
        ans = QMessageBox.question(self, '删除配方', '删除所选配方快照？不可撤销。',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        rl.delete_recipe(p, rid)
        self.document.commit(p)
        self.refresh()
        self.recipesChanged.emit()

    def _update_meta(self):
        rid = self._selected_id()
        if not rid:
            return
        p = deepcopy(self.document.project)
        for r in rl.ensure_recipes(p):
            if isinstance(r, dict) and r.get('id') == rid:
                r['name'] = self._name_edit.text().strip() or r.get('name')
                r['note'] = self._note_edit.toPlainText().strip()
                if hasattr(self, '_variant_edit'):
                    r['variant'] = self._variant_edit.text().strip()
                    snap = r.get('snapshot')
                    if isinstance(snap, dict):
                        snap['variant'] = r['variant']
                break
        self.document.commit(p)
        self.refresh()
        self.recipesChanged.emit()

    def _load_measure_chain_trial(self):
        """细妆⑲：工程库一键选中测量链并强制 enterRun+trialOnce."""
        prefer = (
            'open-and-run-caliper-measure',
            'open-and-run-measure',
            'caliper-measure',
        )
        hit = None
        for i in range(self._lib_list.count()):
            it = self._lib_list.item(i)
            tip = (it.toolTip() or '') + ' ' + (it.text() or '')
            low = tip.lower().replace('\\', '/')
            for key in prefer:
                if key in low:
                    hit = it
                    break
            if hit is not None:
                break
        if hit is None:
            QMessageBox.warning(
                self, '测量链',
                '工程库未找到 open-and-run-caliper-measure / measure 模板。',
            )
            return
        self._lib_list.setCurrentItem(hit)
        # force post-apply loop flags
        try:
            self._chk_enter_run.setChecked(True)
            self._chk_trial_once.setChecked(True)
        except Exception:
            pass
        self._pending_scheme_trial = True
        self._load_library()

    def post_apply_flags(self):
        """Public: enterRun/trialOnce from dialog checkboxes (细妆⑲)."""
        return {
            'enterRun': bool(getattr(self, '_chk_enter_run', None) and self._chk_enter_run.isChecked()),
            'trialOnce': bool(getattr(self, '_chk_trial_once', None) and self._chk_trial_once.isChecked())
                         or bool(getattr(self, '_pending_scheme_trial', False)),
        }

    def _load_library(self):
        it = self._lib_list.currentItem()
        if not it:
            QMessageBox.warning(self, '换型', '请选择一个工程/模板')
            return
        path = it.data(Qt.ItemDataRole.UserRole)
        ans = QMessageBox.question(
            self, '工程库换型',
            f'加载整案作为当前方案？\n{path}\n未保存改动将丢失。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            proj = rl.load_sieans(path)
        except Exception as err:
            QMessageBox.warning(self, '加载失败', str(err))
            return
        self.schemeLoaded.emit(proj)
        self.accept()
