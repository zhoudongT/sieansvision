# -*- coding: utf-8 -*-
"""Host 变量监视板 — 只读实况 + 测量链/Comm/${} 过滤（VisionMaster 变量监视风格）。

细妆 wave：样张 open 自动种子 watchKeys/resultVar；Comm/flow `${}` 实况展开。
"""
from __future__ import annotations

import re
from typing import Iterable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QInputDialog,
)


# Preset filters (name → predicate over (scope, key))
_MEASURE_RE = re.compile(
    r'^(ixPt|pldDist|pointDist|intersectPt|pointLineDist|pdLive|pd2|'
    r'geometry_|locate_|measure_|line_intersect|point_distance|point_line_distance|'
    r'passGate|ixJudge|pldJudge|pld$|intersect)',
    re.I,
)
_DEFECTS_OCR_RE = re.compile(r'^(defects|ocr|defLive)', re.I)
_COMM_RE = re.compile(r'^(commAccept|commRecv|commSend|commVar|\$\{)', re.I)
_TEMPLATE_RE = re.compile(r'\$\{[^}]+\}')


def classify_watch_key(name: str) -> str:
    n = str(name or '')
    if _TEMPLATE_RE.search(n) or n.startswith('${'):
        return 'template'
    if _COMM_RE.search(n):
        return 'comm'
    if _DEFECTS_OCR_RE.search(n):
        return 'defects_ocr'
    if _MEASURE_RE.search(n):
        return 'measure'
    return 'other'


def collect_watch_keys_from_project(project=None) -> list:
    """Harvest watchKeys / resultVar / judge aliases from a project (sample open seed)."""
    keys = []
    seen = set()

    def _add(name):
        n = str(name or '').strip()
        if not n or n in seen:
            return
        seen.add(n)
        keys.append(n)

    proj = project if isinstance(project, dict) else {}
    meta = ((proj.get('runUi') or {}).get('meta') or {})
    for k in (meta.get('watchKeys') or []):
        _add(k)
    # top-level meta / hostWatch aliases
    for bag in (proj.get('meta') or {}, proj.get('hostWatch') or {}):
        if isinstance(bag, dict):
            for k in (bag.get('watchKeys') or bag.get('keys') or []):
                _add(k)
        elif isinstance(bag, (list, tuple)):
            for k in bag:
                _add(k)
    for step in (proj.get('steps') or []):
        if not isinstance(step, dict):
            continue
        params = step.get('params') if isinstance(step.get('params'), dict) else {}
        rv = params.get('resultVar') or step.get('resultVar')
        if rv:
            _add(rv)
            # common judge / scalar aliases seeded for Host board
            base = str(rv).strip()
            if base:
                _add(f'{base}_judgeOk')
                _add(f'{base}_ok')
                if params.get('judgeEnable') or step.get('operation') in (
                    'line_intersect', 'point_line_distance', 'point_distance',
                    'geometry', 'measure',
                ):
                    _add(f'{base}_x')
                    _add(f'{base}_y')
                    _add(f'{base}_distance')
    # seed passGate / common gate when present in variables
    vars_ = proj.get('variables') or {}
    if isinstance(vars_, dict):
        for k in ('passGate', 'ixJudge', 'pldJudge'):
            if k in vars_:
                _add(k)
    return keys


def host_watch_bag(project=None) -> dict:
    """Return mutable project['hostWatch'] dict (creates if needed)."""
    proj = project if isinstance(project, dict) else {}
    bag = proj.get('hostWatch')
    if not isinstance(bag, dict):
        bag = {}
        if isinstance(project, dict):
            project['hostWatch'] = bag
    return bag


def pin_groups_from_project(project=None) -> tuple:
    """Load (groups:dict, active:str) from project.hostWatch for save/open round-trip."""
    bag = project.get('hostWatch') if isinstance(project, dict) else None
    if not isinstance(bag, dict):
        return {}, ''
    groups = bag.get('pinGroups') or bag.get('pin_groups') or {}
    if not isinstance(groups, dict):
        groups = {}
    cleaned = {}
    for name, keys in groups.items():
        n = str(name or '').strip() or '未命名'
        bag_keys = []
        seen = set()
        for k in (keys or []):
            kk = str(k or '').strip()
            if kk and kk not in seen:
                seen.add(kk)
                bag_keys.append(kk)
        cleaned[n] = bag_keys
    active = str(bag.get('activePinGroup') or bag.get('active_pin_group') or '')
    return cleaned, active




def pin_group_picker_entries(groups=None, *, active: str = '') -> list:
    """Compact pin-group rows for chip RMB picker: [{name,nKeys,active,keysSample}].

    Soft / no hardware — used by canvas hostWatch chip right-click menu.
    """
    groups = groups if isinstance(groups, dict) else {}
    act = str(active or '').strip()
    rows = []
    for name, keys in groups.items():
        n = str(name or '').strip()
        if not n:
            continue
        lst = [str(k).strip() for k in (keys or []) if str(k or '').strip()]
        rows.append({
            'name': n,
            'nKeys': len(lst),
            'active': bool(act and n == act),
            'keysSample': lst[:6],
        })
    rows.sort(key=lambda r: (0 if r.get('active') else 1, r.get('name') or ''))
    return rows



def pin_group_picker_accel_entries(groups=None, *, active: str = '') -> list:
    """Pin-group picker rows with keyboard accelerators 1–9 (soft).

    Adds accel / accelKey / accelHint onto pin_group_picker_entries rows.
    """
    rows = pin_group_picker_entries(groups, active=active)
    out = []
    for i, r in enumerate(rows):
        row = dict(r)
        if i < 9:
            digit = str(i + 1)
            row['accel'] = digit
            row['accelKey'] = f'Key_{digit}'
            row['accelHint'] = digit
        else:
            row['accel'] = ''
            row['accelKey'] = ''
            row['accelHint'] = ''
        out.append(row)
    return out


def pin_group_picker_accel_tip(entries=None) -> str:
    """Discoverability tip for chip RMB pin-group 1–9 accelerators. Soft."""
    entries = list(entries or [])
    n = sum(1 for e in entries if str((e or {}).get('accel') or '').strip())
    if n <= 0:
        n = min(9, len(entries)) if entries else 0
    if n <= 0:
        return '右键钉组 · 建组后可用数字键 1–9 加速选择 · 无硬件'
    hi = min(9, n)
    return f'数字键 1–{hi} 快速选钉组 · 菜单前缀同号 · 无硬件'


def apply_pin_group_picker_accel_tip(menu, entries=None) -> dict:
    """Insert a disabled tip action at the top of the pin-group picker menu. Soft.

    Returns {ok, tip, inserted}.
    """
    tip = pin_group_picker_accel_tip(entries)
    out = {'ok': False, 'tip': tip, 'inserted': False}
    if menu is None:
        out['reason'] = 'no menu'
        return out
    try:
        # avoid duplicate tip
        for a in list(menu.actions()):
            try:
                if a.objectName() == 'hostWatchPinGroupAccelTip':
                    a.setText(tip)
                    out.update(ok=True, inserted=False, updated=True)
                    return out
            except Exception:
                pass
        act = menu.addAction(tip)
        try:
            act.setObjectName('hostWatchPinGroupAccelTip')
        except Exception:
            pass
        try:
            act.setEnabled(False)
        except Exception:
            pass
        # move to top
        try:
            actions = list(menu.actions())
            if actions and actions[-1] is act and len(actions) > 1:
                menu.removeAction(act)
                menu.insertAction(actions[0], act)
                # separator after tip
                sep = menu.insertSeparator(actions[0])
                try:
                    sep.setObjectName('hostWatchPinGroupAccelTipSep')
                except Exception:
                    pass
        except Exception:
            pass
        out.update(ok=True, inserted=True)
    except Exception as err:
        out['reason'] = str(err)
    return out


def apply_pin_group_picker_accels(menu, entries=None):
    """Stamp 1–9 shortcuts onto QMenu actions (data = group name). Soft.

    Returns list of {name, accel, actionText}. Does not exec the menu.
    """
    from PySide6.QtGui import QKeySequence
    entries = list(entries or [])
    stamped = []
    actions = list(menu.actions()) if menu is not None else []
    # Prefer matching by data/name order
    for i, e in enumerate(entries):
        if i >= len(actions):
            break
        a = actions[i]
        name = str(e.get('name') or '')
        accel = str(e.get('accel') or (str(i + 1) if i < 9 else ''))
        if accel:
            try:
                a.setShortcut(QKeySequence(accel))
            except Exception:
                pass
            # Prefix digit for discoverability
            txt = a.text() or ''
            if not txt.lstrip().startswith(accel):
                try:
                    a.setText(f'{accel}  {txt}')
                except Exception:
                    pass
        stamped.append({'name': name, 'accel': accel, 'actionText': a.text()})
    return stamped


def resolve_pin_group_from_chip(chip=None, *, name: str = '', project=None) -> dict:
    """Resolve a pin-group pick from chip/project into an open payload.

    Returns {ok, active, chip, nKeys, nGroups, groups}. Soft / no hardware.
    """
    chip = dict(chip) if isinstance(chip, dict) else {}
    pick = str(name or '').strip()
    groups = {}
    if isinstance(project, dict):
        try:
            groups, act_proj = pin_groups_from_project(project)
            if not chip.get('active') and act_proj:
                chip.setdefault('active', act_proj)
        except Exception:
            groups = {}
    if not groups and chip.get('groupNames'):
        groups = {str(n): [] for n in (chip.get('groupNames') or []) if str(n or '').strip()}
        for e in (chip.get('pinGroupEntries') or []):
            if isinstance(e, dict) and e.get('name') in groups and e.get('keysSample'):
                groups[str(e['name'])] = list(e.get('keysSample') or [])
        sample = list(chip.get('sampleKeys') or [])
        act0 = str(chip.get('active') or '').strip()
        if act0 and act0 in groups and sample and not groups[act0]:
            groups[act0] = list(sample)
    if pick and pick not in groups:
        groups[pick] = list(chip.get('sampleKeys') or []) if pick == str(chip.get('active') or '') else []
    if pick:
        chip['active'] = pick
    elif not chip.get('active') and groups:
        chip['active'] = next(iter(groups))
    chip['groupNames'] = list(groups.keys()) if groups else list(chip.get('groupNames') or [])
    chip['pinGroupEntries'] = pin_group_picker_accel_entries(groups, active=str(chip.get('active') or ''))
    chip['restored'] = True
    chip['kind'] = 'hostWatch'
    chip['clickAction'] = 'openVarWatch'
    act = str(chip.get('active') or '')
    n_keys = len(groups.get(act) or chip.get('sampleKeys') or [])
    return {
        'ok': bool(act or groups or chip.get('sampleKeys')),
        'active': act,
        'chip': chip,
        'nKeys': n_keys,
        'nGroups': len(groups) or len(chip.get('groupNames') or []),
        'groups': {k: list(v) for k, v in groups.items()},
    }


def format_host_watch_open_chip(keys=None, groups=None, *, active: str = '',
                                label: str = '') -> dict:
    """Industrial open-chip bag when a project restores hostWatch pins/keys.

    Returns {text, short, nKeys, nGroups, active, restored, tone}.
    Soft / no hardware — for canvas chip + status bar on open.
    """
    keys = [str(k).strip() for k in (keys or []) if str(k or '').strip()]
    groups = groups if isinstance(groups, dict) else {}
    gnames = [str(n) for n in groups.keys() if str(n or '').strip()]
    n_keys = len(keys)
    n_groups = len(gnames)
    act = str(active or '').strip()
    if not act and gnames:
        act = gnames[0]
    restored = bool(n_keys or n_groups)
    if not restored:
        return {
            'text': '', 'short': '', 'nKeys': 0, 'nGroups': 0,
            'active': '', 'restored': False, 'tone': 'dim',
            'label': str(label or ''),
        }
    # sample keys (compact)
    sample = '、'.join(keys[:4])
    if n_keys > 4:
        sample += f'…(+{n_keys - 4})'
    ghint = ''
    if n_groups:
        ghint = f'钉组×{n_groups}'
        if act:
            ghint += f'·活动「{act}」'
    parts = ['监视已恢复']
    if ghint:
        parts.append(ghint)
    if n_keys:
        parts.append(f'键{n_keys}')
        if sample:
            parts.append(sample)
    if label:
        parts.append(str(label))
    text_full = ' · '.join(parts)
    short = f'监视·{ghint or f"键{n_keys}"}' if (ghint or n_keys) else '监视已恢复'
    return {
        'text': text_full,
        'short': short,
        'nKeys': n_keys,
        'nGroups': n_groups,
        'active': act,
        'restored': True,
        'tone': 'ok',
        'label': str(label or ''),
        'sampleKeys': keys[:8],
        'groupNames': gnames,
        'kind': 'hostWatch',
        'clickAction': 'openVarWatch',
        'clickHint': '点击打开变量监视板（恢复钉组）· 右键选钉组',
        'rmbAction': 'pickPinGroup',
        'rmbHint': '右键选择钉组后打开监视板',
        'pinGroupEntries': pin_group_picker_accel_entries(groups, active=act),
    }


def write_pin_groups_to_project(project, groups=None, *, active: str = '',
                                watch_keys=None) -> dict:
    """Persist pin groups into project['hostWatch'] for .sieans/.sol save."""
    if not isinstance(project, dict):
        return {}
    bag = host_watch_bag(project)
    cleaned = {}
    src = groups if isinstance(groups, dict) else {}
    for name, keys in src.items():
        n = str(name or '').strip() or '未命名'
        lst = []
        seen = set()
        for k in (keys or []):
            kk = str(k or '').strip()
            if kk and kk not in seen:
                seen.add(kk)
                lst.append(kk)
        cleaned[n] = lst
    if cleaned:
        bag['pinGroups'] = cleaned
    if active:
        bag['activePinGroup'] = str(active)
    elif cleaned and not bag.get('activePinGroup'):
        bag['activePinGroup'] = next(iter(cleaned))
    if watch_keys is not None:
        wk = []
        seen = set()
        for k in (watch_keys or []):
            kk = str(k or '').strip()
            if kk and kk not in seen:
                seen.add(kk)
                wk.append(kk)
        bag['watchKeys'] = wk
    project['hostWatch'] = bag
    return bag


def expand_watch_value(project, value, last_result=None):
    """Live-expand Comm/flow `${}` in a watch value; leave non-templates untouched."""
    if value is None:
        return value, False
    if isinstance(value, (int, float, bool)):
        return value, False
    raw = str(value)
    if '${' not in raw:
        return value, False
    # Prefer runtime flow overlay into a shallow project copy for expand
    proj = project if isinstance(project, dict) else {}
    try:
        from desktop.comm_manager import expand_payload_placeholders
    except Exception:
        return value, False
    overlay = None
    if last_result and isinstance(last_result, dict):
        vars_bag = last_result.get('variables') or {}
        flow = vars_bag.get('flow') if isinstance(vars_bag, dict) else None
        if isinstance(flow, dict) and flow:
            overlay = dict(proj)
            merged = dict(proj.get('variables') or {})
            merged.update(flow)
            overlay['variables'] = merged
    try:
        expanded = expand_payload_placeholders(overlay or proj, raw)
    except Exception:
        return value, False
    if expanded == raw:
        return value, False
    return expanded, True


def collect_comm_template_entries(document=None, last_result=None) -> list:
    """Synthesize Comm send-event rows with live-expanded `${}` payloads."""
    entries = []
    try:
        proj = getattr(document, 'project', None) or {}
    except Exception:
        proj = {}
    if not isinstance(proj, dict):
        return entries
    cm = proj.get('commManager') or {}
    events = []
    if isinstance(cm, dict):
        for bag_key in ('sendEvents', 'events', 'send'):
            bag = cm.get(bag_key)
            if isinstance(bag, list):
                events.extend(bag)
    try:
        from desktop.comm_manager import (
            expand_payload_placeholders, resolve_send_event_payload,
        )
    except Exception:
        return entries
    # merge runtime flow for expand
    overlay = dict(proj)
    if last_result and isinstance(last_result, dict):
        vars_bag = last_result.get('variables') or {}
        flow = vars_bag.get('flow') if isinstance(vars_bag, dict) else None
        if isinstance(flow, dict):
            merged = dict(proj.get('variables') or {})
            merged.update(flow)
            overlay['variables'] = merged
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            continue
        name = str(ev.get('name') or ev.get('id') or f'send#{i+1}')
        msg = ev.get('message') if ev.get('message') is not None else ev.get('topic')
        msg = '' if msg is None else str(msg)
        try:
            payload, src = resolve_send_event_payload(overlay, ev)
        except Exception:
            payload = expand_payload_placeholders(overlay, msg) if '${' in msg else msg
            src = 'message' if payload else 'empty'
        # always expose the template expression itself when present
        if '${' in msg:
            entries.append(('comm', f'${{{name}}}', msg))
            entries.append(('comm', f'commSend:{name}', payload if payload else '(空)'))
            entries.append(('comm', f'commSend:{name}:src', src))
        elif payload:
            entries.append(('comm', f'commSend:{name}', payload))
    return entries


def filter_entries(entries: Iterable[tuple], preset: str, query: str) -> list:
    q = (query or '').strip().lower()
    out = []
    for scope, name, value in entries:
        cat = classify_watch_key(name)
        if preset == 'measure' and cat != 'measure':
            continue
        if preset == 'comm' and cat != 'comm':
            continue
        if preset == 'defects_ocr' and cat != 'defects_ocr':
            continue
        if preset == 'template' and cat != 'template':
            # also show keys that look like flow inject commonly used in ${}
            if '${' not in str(name) and '${' not in str(value):
                continue
        if preset == 'inject' and cat == 'other':
            continue
        if q and q not in str(name).lower() and q not in str(scope).lower() and q not in str(value).lower():
            continue
        out.append((scope, name, value, cat))
    return out


def collect_flow_entries(document=None, last_result=None, extra_flow: dict | None = None,
                         pinned_keys: list | None = None) -> list:
    """Gather (scope, name, value) from project variables + last_result.variables.

    pinned_keys: seed rows (e.g. watchKeys/resultVar) shown even before first run.
    """
    entries = []
    seen = set()

    def _add(scope, bag):
        if not isinstance(bag, dict):
            return
        for k, v in bag.items():
            key = (scope, str(k))
            if key in seen:
                continue
            seen.add(key)
            entries.append((scope, str(k), v))

    if extra_flow:
        _add('flow', extra_flow)

    if last_result and isinstance(last_result, dict):
        vars_bag = last_result.get('variables') or {}
        if isinstance(vars_bag, dict):
            for scope in ('flow', 'global', 'module', 'modules'):
                bag = vars_bag.get(scope)
                if scope == 'modules' and isinstance(bag, dict):
                    for mid, mv in bag.items():
                        if isinstance(mv, dict):
                            for k, v in mv.items():
                                _add(f'module:{mid}', {k: v})
                else:
                    _add('flow' if scope == 'module' else scope, bag if isinstance(bag, dict) else {})

    try:
        proj = getattr(document, 'project', None) or {}
        _add('flow', proj.get('variables') or {})
        g = (proj.get('globalVariables') or proj.get('globals') or {})
        if isinstance(g, dict):
            _add('global', g)
    except Exception:
        pass

    # Prefer last_result values — re-merge so runtime wins
    if last_result and isinstance(last_result, dict):
        vars_bag = last_result.get('variables') or {}
        flow = vars_bag.get('flow') if isinstance(vars_bag, dict) else None
        if isinstance(flow, dict):
            # update existing flow entries
            idx = {(s, n): i for i, (s, n, _) in enumerate(entries)}
            for k, v in flow.items():
                key = ('flow', str(k))
                if key in idx:
                    entries[idx[key]] = ('flow', str(k), v)
                else:
                    entries.append(('flow', str(k), v))
                    seen.add(key)

    # Seed pinned watch keys (sample open) so board is useful before run
    for name in (pinned_keys or []):
        key = ('flow', str(name))
        if key in seen:
            continue
        seen.add(key)
        entries.append(('flow', str(name), None))  # placeholder → 待运行

    # Comm `${}` live rows
    for scope, name, value in collect_comm_template_entries(document, last_result):
        key = (scope, name)
        if key in seen:
            continue
        seen.add(key)
        entries.append((scope, name, value))

    return entries


class HostVarWatchBoard(QWidget):
    """Read-only live watch table for Host / measure / Comm vars."""

    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('hostVarWatchBoard')
        self._document = None
        self._last_result = None
        self._auto = True
        self._pinned_keys: list[str] = []
        self._seed_label = ''
        self._pin_groups: dict[str, list[str]] = {'默认': []}
        self._active_pin_group = '默认'

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        head = QHBoxLayout()
        title = QLabel('变量监视板')
        title.setObjectName('hostVarWatchTitle')
        title.setStyleSheet('font-weight:600;color:#ddd;')
        head.addWidget(title)
        self.count_lab = QLabel('0 项')
        self.count_lab.setObjectName('hostVarWatchCount')
        self.count_lab.setStyleSheet('color:#888;')
        head.addWidget(self.count_lab)
        self.seed_lab = QLabel('')
        self.seed_lab.setObjectName('hostVarWatchSeed')
        self.seed_lab.setStyleSheet('color:#6a9;font-size:11px;')
        head.addWidget(self.seed_lab)
        head.addStretch(1)
        root.addLayout(head)

        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.setObjectName('hostVarWatchPreset')
        for lab, key in (
            ('全部', 'all'),
            ('测量链', 'measure'),
            ('缺陷/OCR', 'defects_ocr'),
            ('Comm / 收发', 'comm'),
            ('注入标量', 'inject'),
            ('${} 模板', 'template'),
        ):
            self.preset.addItem(lab, key)
        self.search = QLineEdit()
        self.search.setObjectName('hostVarWatchSearch')
        self.search.setPlaceholderText('过滤名称 / 值 / ${flow.xxx}')
        self.refresh_btn = QPushButton('刷新')
        self.refresh_btn.setObjectName('hostVarWatchRefreshBtn')
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        row.addWidget(self.preset)
        row.addWidget(self.search, 1)
        row.addWidget(self.refresh_btn)
        root.addLayout(row)

        grow = QHBoxLayout()
        grow.addWidget(QLabel('钉组'))
        self.pin_group = QComboBox()
        self.pin_group.setObjectName('hostVarWatchPinGroup')
        self.pin_group.setToolTip('监视钉组：切换显示的种子键集合')
        self.pin_group.addItem('默认', '默认')
        self.pin_group.currentIndexChanged.connect(self._on_pin_group_changed)
        grow.addWidget(self.pin_group)
        self.pin_group_new_btn = QPushButton('建组')
        self.pin_group_new_btn.setObjectName('hostVarWatchPinGroupNewBtn')
        self.pin_group_new_btn.setToolTip('用当前种子键新建钉组')
        self.pin_group_new_btn.clicked.connect(self._on_new_pin_group)
        grow.addWidget(self.pin_group_new_btn)
        self.pin_group_save_btn = QPushButton('存组')
        self.pin_group_save_btn.setObjectName('hostVarWatchPinGroupSaveBtn')
        self.pin_group_save_btn.setToolTip('把当前种子键写入活动钉组')
        self.pin_group_save_btn.clicked.connect(self._save_active_pin_group)
        grow.addWidget(self.pin_group_save_btn)
        self.export_csv_btn = QPushButton('导出CSV')
        self.export_csv_btn.setObjectName('hostVarWatchExportCsvBtn')
        self.export_csv_btn.setToolTip('导出当前监视表（含展开列）为 CSV')
        self.export_csv_btn.clicked.connect(self._on_export_csv_clicked)
        grow.addWidget(self.export_csv_btn)
        grow.addStretch(1)
        self.pin_group_lab = QLabel('')
        self.pin_group_lab.setObjectName('hostVarWatchPinGroupLab')
        self.pin_group_lab.setStyleSheet('color:#6a9;font-size:11px;')
        grow.addWidget(self.pin_group_lab)
        root.addLayout(grow)

        tip = QLabel(
            '只读 · 打开样张自动种子 watchKeys/resultVar · '
            '运行后跟随 last_result · Comm/flow `${}` 实况展开'
        )
        tip.setStyleSheet('color:#666;font-size:11px;')
        tip.setWordWrap(True)
        root.addWidget(tip)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName('hostVarWatchTable')
        self.table.setHorizontalHeaderLabels(['作用域', '名称', '值', '展开', '类'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        self.preset.currentIndexChanged.connect(self.render)
        self.search.textChanged.connect(self.render)

        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._auto_tick)
        self._timer.start()

    def bind(self, document=None, last_result=None):
        self._document = document
        self._last_result = last_result
        self.render()

    def set_last_result(self, result):
        self._last_result = result
        self.render()

    def seed_watch_keys(self, keys=None, *, label: str = ''):
        """Pin keys from sample open (watchKeys / resultVar) so board shows before run."""
        cleaned = []
        seen = set()
        for k in (keys or []):
            n = str(k or '').strip()
            if not n or n in seen:
                continue
            seen.add(n)
            cleaned.append(n)
        self._pinned_keys = cleaned
        self._seed_label = str(label or '')
        # keep active pin group in sync when seeding from project
        gname = self._active_pin_group or '默认'
        if gname not in self._pin_groups:
            self._pin_groups[gname] = []
        if cleaned and (not self._pin_groups.get(gname) or gname == '默认'):
            self._pin_groups[gname] = list(cleaned)
        try:
            self._rebuild_pin_group_combo()
        except Exception:
            pass
        if cleaned:
            self.seed_lab.setText(
                f'已种子 {len(cleaned)}' + (f' · {self._seed_label}' if self._seed_label else '')
            )
        else:
            self.seed_lab.setText('')
        self.render()

    def seed_from_project(self, project=None, *, label: str = ''):
        keys = collect_watch_keys_from_project(project)
        groups, active = pin_groups_from_project(project)
        if groups:
            # restore saved pin groups; fall back keys into 默认 if empty
            if keys and '默认' in groups and not groups.get('默认'):
                groups['默认'] = list(keys)
            elif keys and active and active in groups and not groups.get(active):
                groups[active] = list(keys)
            self.set_pin_groups(groups, active=active or '')
        else:
            self.seed_watch_keys(keys, label=label or (project or {}).get('name') or '')
        # Prefer measure preset when measure keys dominate
        measure_n = sum(1 for k in (self._pinned_keys or keys) if classify_watch_key(k) == 'measure')
        if measure_n >= 2:
            idx = self.preset.findData('measure')
            if idx >= 0:
                self.preset.setCurrentIndex(idx)
        return keys

    def persist_pin_groups_to_project(self, project=None) -> dict:
        """Write current pin groups into project JSON (hostWatch)."""
        proj = project
        if proj is None and self._document is not None:
            proj = getattr(self._document, 'project', None)
        if not isinstance(proj, dict):
            return {}
        # flush active group keys first
        try:
            self._save_active_pin_group()
        except Exception:
            pass
        return write_pin_groups_to_project(
            proj,
            self.pin_groups(),
            active=self.active_pin_group(),
            watch_keys=self.pinned_keys(),
        )

    def pinned_keys(self) -> list:
        return list(self._pinned_keys)

    def pin_groups(self) -> dict:
        return {k: list(v) for k, v in self._pin_groups.items()}

    def active_pin_group(self) -> str:
        return str(self._active_pin_group or '默认')

    def activate_pin_group(self, name: str = '') -> str:
        """Switch active pin group (restored open-chip click target). Soft / no hardware."""
        n = str(name or '').strip()
        if not n:
            n = self.active_pin_group()
        if n not in self._pin_groups:
            # create empty group so UI can still open on named restored group
            self._pin_groups[n] = list(self._pin_groups.get(n) or [])
            self._rebuild_pin_group_combo()
        self._active_pin_group = n
        self._rebuild_pin_group_combo()
        keys = list(self._pin_groups.get(n) or [])
        self.seed_watch_keys(keys, label=f'钉组:{n}')
        self._sync_pin_group_lab()
        return n

    def set_pin_groups(self, groups: dict | None, *, active: str = ''):
        cleaned = {}
        if isinstance(groups, dict):
            for name, keys in groups.items():
                n = str(name or '').strip() or '未命名'
                bag = []
                seen = set()
                for k in (keys or []):
                    kk = str(k or '').strip()
                    if kk and kk not in seen:
                        seen.add(kk)
                        bag.append(kk)
                cleaned[n] = bag
        if not cleaned:
            cleaned = {'默认': list(self._pinned_keys)}
        self._pin_groups = cleaned
        self._active_pin_group = str(active or self._active_pin_group or '默认')
        if self._active_pin_group not in self._pin_groups:
            self._active_pin_group = next(iter(self._pin_groups))
        self._rebuild_pin_group_combo()
        self.seed_watch_keys(
            self._pin_groups.get(self._active_pin_group) or [],
            label=f'钉组:{self._active_pin_group}',
        )

    def ensure_pin_group(self, name: str, keys=None) -> str:
        n = str(name or '').strip() or '未命名'
        bag = []
        seen = set()
        for k in (keys if keys is not None else self._pinned_keys):
            kk = str(k or '').strip()
            if kk and kk not in seen:
                seen.add(kk)
                bag.append(kk)
        self._pin_groups[n] = bag
        self._rebuild_pin_group_combo()
        return n

    def _rebuild_pin_group_combo(self):
        cb = getattr(self, 'pin_group', None)
        if cb is None:
            return
        cur = self._active_pin_group
        cb.blockSignals(True)
        cb.clear()
        for name in self._pin_groups:
            cb.addItem(name, name)
        idx = cb.findData(cur)
        cb.setCurrentIndex(idx if idx >= 0 else 0)
        cb.blockSignals(False)
        self._sync_pin_group_lab()

    def _sync_pin_group_lab(self):
        lab = getattr(self, 'pin_group_lab', None)
        if lab is None:
            return
        keys = self._pin_groups.get(self._active_pin_group) or []
        lab.setText(f'{self._active_pin_group} · {len(keys)}键')

    def _on_pin_group_changed(self, *_):
        cb = self.pin_group
        name = cb.currentData() or cb.currentText() or '默认'
        self._active_pin_group = str(name)
        keys = list(self._pin_groups.get(self._active_pin_group) or [])
        self.seed_watch_keys(keys, label=f'钉组:{self._active_pin_group}')
        self._sync_pin_group_lab()

    def _save_active_pin_group(self):
        name = self.active_pin_group()
        self._pin_groups[name] = list(self._pinned_keys)
        self._sync_pin_group_lab()
        try:
            if self._document is not None and getattr(self._document, 'project', None):
                self.persist_pin_groups_to_project(self._document.project)
        except Exception:
            pass

    def _on_new_pin_group(self):
        name, ok = QInputDialog.getText(self, '新建钉组', '钉组名称：', text='测量')
        if not ok:
            return
        name = (name or '').strip() or '未命名'
        self.ensure_pin_group(name, self._pinned_keys)
        self._active_pin_group = name
        self._rebuild_pin_group_combo()
        self.seed_watch_keys(self._pin_groups.get(name) or [], label=f'钉组:{name}')

    def export_csv(self, path: str | None = None) -> str:
        """Export current rendered table to CSV. Returns path written."""
        import csv
        from pathlib import Path as _P
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, '导出监视变量 CSV', 'host-watch.csv', 'CSV (*.csv)'
            )
            if not path:
                return ''
        path = str(_P(path))
        rows = []
        headers = []
        for c in range(self.table.columnCount()):
            h = self.table.horizontalHeaderItem(c)
            headers.append(h.text() if h else f'c{c}')
        # meta
        rows.append(['#pin_group', self.active_pin_group()])
        rows.append(['#pinned', ','.join(self._pinned_keys)])
        rows.append(headers)
        for r in range(self.table.rowCount()):
            rows.append([
                (self.table.item(r, c).text() if self.table.item(r, c) else '')
                for c in range(self.table.columnCount())
            ])
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerows(rows)
        return path

    def export_csv_text(self) -> str:
        """Return CSV text for current table (no dialog) — for smoke/tests."""
        import io, csv
        buf = io.StringIO()
        w = csv.writer(buf)
        headers = []
        for c in range(self.table.columnCount()):
            h = self.table.horizontalHeaderItem(c)
            headers.append(h.text() if h else f'c{c}')
        w.writerow(['#pin_group', self.active_pin_group()])
        w.writerow(['#pinned', ','.join(self._pinned_keys)])
        w.writerow(headers)
        for r in range(self.table.rowCount()):
            w.writerow([
                (self.table.item(r, c).text() if self.table.item(r, c) else '')
                for c in range(self.table.columnCount())
            ])
        return buf.getvalue()

    def _on_export_csv_clicked(self):
        out = self.export_csv()
        if out:
            try:
                QMessageBox.information(self, '导出CSV', f'已导出：\n{out}')
            except Exception:
                pass

    def _on_refresh_clicked(self):
        self.refreshRequested.emit()
        self.render()

    def _auto_tick(self):
        if not self._auto or not self.isVisible():
            return
        # pull latest from parent host if available
        try:
            host = self.window()
            lr = getattr(host, 'last_result', None)
            if lr is not None and lr is not self._last_result:
                self._last_result = lr
                self.render()
                return
            doc = getattr(host, 'document', None)
            if doc is not None:
                self._document = doc
        except Exception:
            pass

    def render(self, *_):
        entries = collect_flow_entries(
            self._document, self._last_result, pinned_keys=self._pinned_keys,
        )
        preset = self.preset.currentData() or 'all'
        rows = filter_entries(entries, preset if preset != 'all' else 'all', self.search.text())
        # when preset all, filter_entries with 'all' — need to allow all
        if preset == 'all':
            q = (self.search.text() or '').strip().lower()
            rows = []
            for scope, name, value in entries:
                cat = classify_watch_key(name)
                if q and q not in str(name).lower() and q not in str(scope).lower() and q not in str(value).lower():
                    continue
                rows.append((scope, name, value, cat))

        proj = {}
        try:
            proj = getattr(self._document, 'project', None) or {}
        except Exception:
            proj = {}

        self.table.setRowCount(0)
        cat_colors = {
            'measure': QColor('#1a2e24'),
            'defects_ocr': QColor('#2a1e2e'),
            'comm': QColor('#1a2a33'),
            'template': QColor('#2e2a1a'),
            'other': QColor('#1e2228'),
        }
        cat_labels = {
            'measure': '测量',
            'defects_ocr': '缺陷OCR',
            'comm': 'Comm',
            'template': '${}',
            'other': '—',
        }
        for scope, name, value, cat in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            expanded, did = expand_watch_value(proj, value, self._last_result)
            # For template-named keys that ARE the expression, expand against project
            if not did and ('${' in str(name) or cat == 'template'):
                expr = str(name) if '${' in str(name) else str(value or '')
                if '${' in expr:
                    expanded2, did2 = expand_watch_value(proj, expr, self._last_result)
                    if did2:
                        expanded, did = expanded2, True
            val_txt = _fmt(value) if value is not None else '待运行'
            exp_txt = _fmt(expanded) if did else ('—' if value is not None else '')
            if did and str(expanded) == str(value):
                exp_txt = '—'
                did = False
            texts = [str(scope), str(name), val_txt, exp_txt, cat_labels.get(cat, '—')]
            bg = cat_colors.get(cat)
            for c, text in enumerate(texts):
                it = QTableWidgetItem(text)
                if bg is not None:
                    it.setBackground(QBrush(bg))
                if c == 3 and did:
                    it.setForeground(QBrush(QColor('#8fd98f')))
                if c == 2 and value is None:
                    it.setForeground(QBrush(QColor('#888')))
                self.table.setItem(r, c, it)
        self.count_lab.setText(f'{self.table.rowCount()} 项')


def _fmt(value) -> str:
    if value is None:
        return '空'
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, float):
        return f'{value:.6g}'
    s = str(value)
    return s if len(s) <= 120 else s[:117] + '…'




def open_var_watch_on_restored_group(board, chip=None, *, project=None, label: str = '') -> dict:
    """Apply open-chip payload onto an existing HostVarWatchBoard (restored group).

    Returns {ok, active, nKeys, nGroups, seeded}. Soft / no hardware.
    """
    out = {'ok': False, 'active': '', 'nKeys': 0, 'nGroups': 0, 'seeded': False}
    if board is None:
        return out
    chip = chip if isinstance(chip, dict) else {}
    act = str(chip.get('active') or '').strip()
    groups = {}
    # Prefer live project groups; fall back to chip.groupNames as empty shells
    if isinstance(project, dict):
        try:
            groups, act_proj = pin_groups_from_project(project)
            if not act:
                act = str(act_proj or '')
        except Exception:
            groups = {}
    if not groups and chip.get('groupNames'):
        groups = {str(n): [] for n in (chip.get('groupNames') or []) if str(n or '').strip()}
        sample = list(chip.get('sampleKeys') or [])
        if act and act in groups and sample:
            groups[act] = list(sample)
        elif sample and groups:
            first = next(iter(groups))
            groups[first] = list(sample)
            if not act:
                act = first
    try:
        if groups:
            board.set_pin_groups(groups, active=act or '')
            out['seeded'] = True
        elif isinstance(project, dict) and hasattr(board, 'seed_from_project'):
            board.seed_from_project(project, label=label or str(chip.get('label') or ''))
            out['seeded'] = True
        elif chip.get('sampleKeys') and hasattr(board, 'seed_watch_keys'):
            board.seed_watch_keys(chip.get('sampleKeys') or [], label=label or str(chip.get('label') or ''))
            out['seeded'] = True
        if act and hasattr(board, 'activate_pin_group'):
            board.activate_pin_group(act)
        out['ok'] = True
        out['active'] = board.active_pin_group() if hasattr(board, 'active_pin_group') else act
        out['nKeys'] = len(board.pinned_keys()) if hasattr(board, 'pinned_keys') else 0
        out['nGroups'] = len(board.pin_groups()) if hasattr(board, 'pin_groups') else 0
    except Exception as err:
        out['error'] = str(err)
    return out


class HostVarWatchDialog(QDialog):
    """Dialog shell around HostVarWatchBoard."""

    def __init__(self, document=None, last_result=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Host 变量监视板')
        self.setObjectName('hostVarWatchDialog')
        self.resize(780, 500)
        lay = QVBoxLayout(self)
        self.board = HostVarWatchBoard(self)
        self.board.bind(document, last_result)
        # auto-seed from project if present
        try:
            proj = getattr(document, 'project', None)
            if isinstance(proj, dict):
                self.board.seed_from_project(proj, label=str(proj.get('name') or ''))
        except Exception:
            pass
        lay.addWidget(self.board, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        close = bb.button(QDialogButtonBox.StandardButton.Close)
        if close:
            close.clicked.connect(self.reject)
        lay.addWidget(bb)
