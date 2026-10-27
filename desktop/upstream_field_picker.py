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
        fi = result_field_index(last_result, [node])
        fields = list(fi.get(node['id']) or [])
    except Exception:
        fields = []
    if not fields:
        op = node.get('operation') or ''
        fields = {
            'locate': ['matches', 'matches.0', 'score', 'ok', 'angle', 'x', 'y'],
            'pose_correct': ['fixtureX', 'fixtureY', 'fixtureAngle', 'matrix', 'ok'],
            'distort_correct': ['status', 'mode', 'calibPath', 'coeffs', 'ok'],
            'receive_data': ['payload', 'ok', 'device', 'bytes'],
            'send_data': ['sent', 'ok', 'device', 'bytes'],
            'var_calc': ['value', 'ok', 'values', 'errors'],
            'group': ['ok', 'status', 'outputs'],
            'geometry_find': ['ok', 'count', 'shapes', 'shapes.0', 'x', 'y'],
            'measure_geom': ['ok', 'value', 'distance', 'angle', 'length'],
            'nine_point': ['ok', 'matrix', 'rms', 'resultVar'],
            'format_data': ['ok', 'text', 'targetVar', 'formatted'],
            'protocol_parse': ['ok', 'fields', 'parsed', 'count'],
            'output_image': ['ok', 'savedPath', 'path'],
            'text_save': ['ok', 'path', 'bytes'],
            'condition_branch': ['ok', 'branch', 'matched'],
            'production_task': ['ok', 'status', 'count', 'cycle'],
        }.get(op, ['ok', 'status', 'value', 'count', 'payload'])
    field, ok = QInputDialog.getItem(
        parent, '上游字段',
        f"模块 {node.get('name') or node['id']} 的字段",
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

    def _pick():
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


def fill_line_from_picker(owner, project, step_id, line_edit, set_param=None, key=None):
    """Pick upstream field and write token into an existing QLineEdit."""
    picked = pick_upstream_field(
        owner, project, step_id=step_id,
        last_result=host_last_result(owner),
    )
    if not picked:
        return None
    _nid, _field, token = picked
    line_edit.setText(token)
    if set_param and key:
        set_param(key, token)
    return token
