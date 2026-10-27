"""产线配方 / 一键换型 dialog — industrial one-click UX on project recipes + library."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QTextEdit, QMessageBox, QTabWidget, QWidget,
    QFormLayout, QGroupBox, QAbstractItemView, QSplitter, QComboBox, QCheckBox,
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

        row = QHBoxLayout()
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

    def _apply_selected(self):
        rid = self._selected_id()
        if not rid:
            QMessageBox.warning(self, '换型', '请先选择一个配方')
            return
        ans = QMessageBox.question(
            self, '一键换型',
            '将把所选配方的模块参数套用到当前流程（按算子+名称匹配）。\n继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        try:
            stats = rl.apply_recipe(p, rid)
        except Exception as err:
            QMessageBox.warning(self, '换型失败', str(err))
            return
        self.document.commit(p)
        self.refresh()
        self.recipeApplied.emit(stats)
        self.recipesChanged.emit()
        QMessageBox.information(
            self, '换型完成',
            f"已套用「{stats.get('name')}」\n匹配写入 {stats.get('applied')} · 跳过 {stats.get('skipped')} · 变量 {stats.get('varsApplied')}",
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
        ans = QMessageBox.question(
            self, '部分套用',
            '按局部规则套用所选配方：\n' + ' · '.join(hint) + '\n继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        p = deepcopy(self.document.project)
        try:
            stats = rl.apply_recipe(
                p, rid, var_keys=var_keys, step_ops=step_ops,
                steps_only=steps_only, vars_only=vars_only,
            )
        except Exception as err:
            QMessageBox.warning(self, '部分套用失败', str(err))
            return
        self.document.commit(p)
        self.refresh()
        self.recipeApplied.emit(stats)
        self.recipesChanged.emit()
        QMessageBox.information(
            self, '部分套用完成',
            '「%s」变体 %s\n模块写入 %s · 跳过 %s · 变量 %s' % (
                stats.get('name'), stats.get('variant') or '—',
                stats.get('applied'), stats.get('skipped'), stats.get('varsApplied'),
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
