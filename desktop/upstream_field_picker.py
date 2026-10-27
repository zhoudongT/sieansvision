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
            'var_calc': ['value', 'ok', 'values', 'errors'],
            'group': ['ok', 'status', 'outputs'],
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
