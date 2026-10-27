"""Node config completeness — VisionMaster「未配置完整」红叹号依据."""
from __future__ import annotations

from copy import deepcopy


def source_incomplete(config) -> bool:
    cfg = config or {}
    mode = cfg.get('mode') or 'local'
    if mode == 'local':
        return not bool(cfg.get('images'))
    # camera / sdk
    cam = cfg.get('cameraId') or (cfg.get('cameraParams') or {}).get('deviceId')
    return not bool(cam)


def step_incomplete(step, project=None) -> bool:
    if not step:
        return False
    op = step.get('operation') or ''
    params = step.get('params') or {}
    if op == 'camera_capture':
        return not bool(params.get('deviceId') or params.get('cameraId'))
    if op == 'locate':
        has_img = bool(step.get('imageFrom'))
        has_tpl = bool(
            step.get('reference')
            or params.get('templatePath')
            or params.get('modelPath')
            or params.get('hasTemplate')
            or params.get('templateReady')
        )
        return not (has_img and has_tpl)
    if op == 'group':
        try:
            from desktop.group_module import group_bindings_ready
            return not group_bindings_ready(params)
        except Exception:
            return not (
                str(params.get('imageData') or '').strip()
                and str(params.get('inputRoi') or '').strip()
            )
    if op in (
        'tcp_exchange', 'udp_exchange', 'serial_exchange',
        'mqtt_publish', 'mqtt_receive', 'modbus_read', 'modbus_write', 'modbus_wait',
        's7_read', 's7_write',
    ):
        return not bool(
            params.get('host') or params.get('address') or params.get('port')
            or params.get('topic') or params.get('device') or params.get('channel')
            or params.get('endpoint')
        )
    if op == 'condition':
        rules = params.get('rules') or params.get('table') or []
        def _rule_ready(r):
            if not isinstance(r, dict):
                return False
            if (r.get('comparison') or '') in ('is_true', 'is_false'):
                return r.get('left') is not None and str(r.get('left')).strip() != ''
            return str(r.get('left', '')).strip() != '' or r.get('left') == 0
        if isinstance(rules, list) and rules:
            return not any(_rule_ready(r) for r in rules)
        return not bool(
            params.get('expression') or params.get('condition')
            or params.get('left') is not None
        )
    if op == 'branch':
        paths = params.get('paths') or []
        return not (isinstance(paths, list) and len(paths) >= 1)
    if op == 'pose_correct':
        return not bool(step.get('imageFrom'))
    if op in ('comm_send', 'comm_recv', 'send_data', 'receive_data'):
        return not bool(params.get('device') or params.get('channel') or params.get('message'))

    if op == 'distort_correct':
        mode = params.get('mode') or 'file'
        if mode == 'file':
            return not bool(str(params.get('calibPath') or '').strip())
        if mode == 'coeffs':
            return False  # coeffs always considered filled (defaults)
        return not bool(step.get('imageFrom'))
    if op == 'nine_point':
        pts = params.get('points') or []
        enabled = [p for p in pts if isinstance(p, dict) and p.get('enabled', True)]
        # need at least one non-zero world or pixel to count as started; else bang if no image
        filled = any(
            abs(float(p.get('pixelX') or 0)) + abs(float(p.get('pixelY') or 0))
            + abs(float(p.get('worldX') or 0)) + abs(float(p.get('worldY') or 0)) > 0
            for p in enabled
        )
        return not filled
    if op == 'var_calc':
        rows = params.get('expressions') or []
        return not any(isinstance(r, dict) and str(r.get('name') or '').strip() for r in rows)
    if op == 'elapsed_stats':
        return not (str(params.get('startStepId') or '').strip() and str(params.get('endStepId') or '').strip())
    if op == 'format_data':
        return not str(params.get('template') or '').strip()
    if op == 'output_image':
        return not (step.get('imageFrom') and str(params.get('path') or '').strip())
    if op == 'protocol_parse':
        return not str(params.get('sourceVar') or '').strip()
    if op == 'text_save':
        return not str(params.get('path') or '').strip()
    if op in ('geometry', 'rect_find'):
        return not bool(step.get('imageFrom'))
    if op in ('line_intersect', 'point_distance', 'point_line_distance'):
        if (params.get('mode') or 'bind') == 'manual':
            return False
        # bind mode: at least one source field filled
        keys = ('line1From', 'line2From', 'point1From', 'point2From', 'pointFrom', 'lineFrom')
        return not any(str(params.get(k) or '').strip() for k in keys)
    if op == 'csharp_script':
        return not str(params.get('code') or '').strip()
    if op == 'production_task':
        return not str(params.get('taskName') or '').strip()
    return False


def node_needs_bang(project, node_id: str) -> bool:
    """True → 画红叹号（未配置完整）。运行失败由 Node.run_failed 另画。"""
    if node_id == 'source':
        return source_incomplete(project.get('sourceConfig'))
    step = next((s for s in (project.get('steps') or []) if s.get('id') == node_id), None)
    return step_incomplete(step, project)
