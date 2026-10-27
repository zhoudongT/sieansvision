"""Shared upstream module+field picker for specialized property panels."""
from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget


def pick_upstream_field(parent: QWidget, project: dict, step_id=None, last_result=None):
    """Dialog: pick upstream module then field. Returns (step_id, field, token) or None."""
    steps = list((project or {}).get('steps') or [])
    upstream = [s for s in steps if isinstance(s, dict) and s.get('id') and s.get('id') != step_id]
    if not upstream:
        QMessageBox.information(parent, '上游字段', '当前流程没有其他模块可供挑选。')
        return None
    labels = [
        f"{i + 1} {s.get('name') or s.get('operation') or s['id']}"
        for i, s in enumerate(upstream)
    ]
    choice, ok = QInputDialog.getItem(parent, '上游模块', '选择模块', labels, 0, False)
    if not ok or not choice:
        return None
    node = upstream[labels.index(choice)]
    try:
        from desktop.forms import result_field_index
        # last_result may be engine payload or already {results:[...]}; normalize
        lr = last_result
        if isinstance(lr, dict) and 'results' not in lr and 'output' in lr:
            lr = {'results': [lr]}
        fi = result_field_index(lr if isinstance(lr, dict) else None, [node])
        fields = [f for f in list(fi.get(node['id']) or []) if isinstance(f, str) and f]
        # de-dupe preserve order
        seen = set(); fields = [f for f in fields if not (f in seen or seen.add(f))]
    except Exception:
        fields = []
    if not fields:
        op = str(node.get('operation') or '')
        geo_fields = [
            'lines', 'lines[0]', 'lines[1]', 'lines.0', 'lines.1',
            'circles', 'circles[0]', 'rects', 'rects[0]',
            'count', 'score', 'bestScore', 'rmsPixels', 'rms',
            'angleDeg', 'lengthPx', 'inlierCount', 'ok', 'status',
        ]
        fields = {
            'locate': ['matches', 'matches[0]', 'matches.0', 'score', 'ok', 'angle', 'x', 'y'],
            'pose_correct': ['fixtureX', 'fixtureY', 'fixtureAngle', 'matrix', 'ok'],
            'distort_correct': ['status', 'mode', 'calibPath', 'coeffs', 'ok'],
            'receive_data': ['payload', 'ok', 'device', 'bytes'],
            'send_data': ['sent', 'ok', 'device', 'bytes'],
            'var_calc': ['value', 'ok', 'values', 'errors'],
            'group': ['ok', 'status', 'outputs'],
            'geometry': list(geo_fields),
            'geometry_find': list(geo_fields),
            'measure_geom': ['ok', 'value', 'distance', 'angle', 'length', 'intersectX', 'intersectY'],
            'point_distance': ['ok', 'value', 'distance', 'length', 'dx', 'dy', 'x1', 'y1', 'x2', 'y2'],
            'point_line_distance': ['ok', 'value', 'distance', 'footX', 'footY', 'px', 'py'],
            'line_intersect': ['ok', 'intersectX', 'intersectY', 'parallel', 'status', 'x', 'y'],
            'measure': ['ok', 'value', 'distance', 'angle', 'length', 'circles', 'circles[0]'],
            'condition': ['ok', 'branch', 'matched', 'passed'],
            'nine_point': ['ok', 'matrix', 'rms', 'resultVar'],
            'format_data': ['ok', 'text', 'targetVar', 'formatted'],
            'protocol_parse': ['ok', 'fields', 'parsed', 'count'],
            'output_image': ['ok', 'savedPath', 'path'],
            'text_save': ['ok', 'path', 'bytes'],
            'condition_branch': ['ok', 'branch', 'matched'],
            'production_task': ['ok', 'status', 'count', 'cycle'],
        }.get(op, ['ok', 'status', 'value', 'count', 'payload'])
    if not fields:
        fields = ['ok', 'status', 'value', 'payload']
    field, ok = QInputDialog.getItem(
        parent, '上游字段',
        f"模块 {node.get('name') or node['id']} 的字段（可手改）",
        fields, 0, True,
    )
    if not ok or not field:
        return None
    nid = node['id']
    token = f'results.{nid}.{field}'
    return nid, field, token


def host_last_result(widget: QWidget):
    host = widget.window() if widget is not None else None
    return getattr(host, 'last_result', None) if host is not None else None


def make_upstream_ref_row(owner, project, step_id, params, set_param, key='upstreamRef', placeholder=None):
    """Build (QHBoxLayout, QLineEdit) for form.addRow('上游参考', row).

    owner: QWidget hosting the panel (for dialogs + last_result).
    set_param: callable(key, value).
    """
    from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton

    row = QHBoxLayout()
    edit = QLineEdit(str((params or {}).get(key) or ''))
    edit.setPlaceholderText(placeholder or 'results.<模块>.字段 — 点击挑选')
    edit.editingFinished.connect(lambda: set_param(key, edit.text().strip()))

    def _pick(*_):
        # Absorb clicked(bool); never bind default-arg widgets into the slot signature.
        picked = pick_upstream_field(
            owner, project, step_id=step_id,
            last_result=host_last_result(owner),
        )
        if not picked:
            return
        _nid, _field, token = picked
        edit.setText(token)
        set_param(key, token)

    btn = QPushButton('插入上游字段')
    btn.setToolTip('从最近运行结果挑选上游模块字段')
    btn.clicked.connect(_pick)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    return row, edit


def fill_line_from_picker(owner, project, step_id, line_edit, set_param=None, key=None, *, field_only=False):
    """Pick upstream field and write into an existing QLineEdit.

    field_only=True → write just the field path (for measure_geom bind rows).
    Default writes results.<id>.<field> token (for free-form refs).
    Returns (nid, field, token) or None.
    """
    picked = pick_upstream_field(
        owner, project, step_id=step_id,
        last_result=host_last_result(owner),
    )
    if not picked:
        return None
    nid, field, token = picked
    value = field if field_only else token
    line_edit.setText(value)
    if set_param and key:
        set_param(key, value)
    return nid, field, token


def default_bind_field_for_op(op, kind='line'):
    """Suggest measure_geom bind field from upstream operation + bind kind."""
    op = str(op or '')
    if kind == 'line':
        if op in ('geometry', 'geometry_find'):
            return 'lines[0]'
        if op == 'measure':
            return 'lines[0]'
        return 'lines[0]'
    # point
    if op == 'locate':
        return 'matches[0]'
    if op in ('geometry', 'geometry_find'):
        return 'lines[0]'  # midpoint via _pickPoint unwrap
    if op in ('line_intersect',):
        return 'intersectX'  # not a full point — prefer manual; still list
    if op == 'measure':
        return 'circles[0]'
    return 'matches[0]'
