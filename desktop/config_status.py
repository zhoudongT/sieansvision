"""Node config completeness — VisionMaster「未配置完整」红叹号依据."""
from __future__ import annotations

from copy import deepcopy


def source_incomplete_reason(config) -> str:
    """Empty → complete; else Chinese reason for N4 bang / panel banner."""
    cfg = config or {}
    mode = cfg.get('mode') or 'local'
    if mode == 'local':
        if not bool(cfg.get('images')):
            return '本地图像列表为空（请在胶片条添加图像）'
        return ''
    cam = cfg.get('cameraId') or (cfg.get('cameraParams') or {}).get('deviceId')
    if not cam:
        if mode == 'sdk':
            return '未关联 SDK/GenTL 相机（请在相机管理中连接）'
        return '未选择关联相机（请打开相机管理）'
    return ''


def source_incomplete(config) -> bool:
    return bool(source_incomplete_reason(config))


def _img_reason(step) -> str:
    return '' if step.get('imageFrom') else '未接线输入图像（imageFrom）'


def step_incomplete_reason(step, project=None) -> str:
    """Empty → complete; else one Chinese reason (first missing)."""
    if not step:
        return ''
    op = step.get('operation') or ''
    params = step.get('params') or {}

    if op == 'camera_capture':
        if not (params.get('deviceId') or params.get('cameraId')):
            return '未选择相机设备'
        return ''

    if op == 'locate':
        r = _img_reason(step)
        if r:
            return r
        has_tpl = bool(
            step.get('reference')
            or params.get('templatePath')
            or params.get('modelPath')
            or params.get('hasTemplate')
            or params.get('templateReady')
        )
        if not has_tpl:
            return '未加载匹配模板'
        return ''

    if op == 'group':
        try:
            from desktop.group_module import group_bindings_ready
            if not group_bindings_ready(params):
                return '组合模块绑定未完成（图像/ROI）'
            return ''
        except Exception:
            if not (
                str(params.get('imageData') or '').strip()
                and str(params.get('inputRoi') or '').strip()
            ):
                return '组合模块绑定未完成（图像/ROI）'
            return ''

    if op in (
        'tcp_exchange', 'udp_exchange', 'serial_exchange',
        'mqtt_publish', 'mqtt_receive', 'modbus_read', 'modbus_write', 'modbus_wait',
        's7_read', 's7_write',
    ):
        if not bool(
            params.get('host') or params.get('address') or params.get('port')
            or params.get('topic') or params.get('device') or params.get('channel')
            or params.get('endpoint')
        ):
            return '未填写主机/端口/Topic/设备'
        return ''

    if op in ('opcua_read', 'opcua_write', 'opcua_browse', 'opcua_wait'):
        if not (
            str(params.get('endpoint') or '').strip()
            or str(params.get('connection') or '').strip()
            or str(params.get('nodeId') or '').strip()
        ):
            return '未填写 OPC UA 端点或节点（endpoint/nodeId）'
        if op in ('opcua_read', 'opcua_write', 'opcua_wait') and not str(params.get('nodeId') or '').strip():
            return '未填写 OPC UA 节点 nodeId'
        return ''

    if op == 'condition':
        rules = params.get('rules') or params.get('table') or []
        def _rule_ready(r):
            if not isinstance(r, dict):
                return False
            if (r.get('comparison') or '') in ('is_true', 'is_false'):
                return r.get('left') is not None and str(r.get('left')).strip() != ''
            return str(r.get('left', '')).strip() != '' or r.get('left') == 0
        if isinstance(rules, list) and rules:
            if not any(_rule_ready(r) for r in rules):
                return '条件规则未填写左值'
            return ''
        if not bool(
            params.get('expression') or params.get('condition')
            or params.get('left') is not None
        ):
            return '未填写条件表达式'
        return ''

    if op == 'branch':
        paths = params.get('paths') or []
        if not (isinstance(paths, list) and len(paths) >= 1):
            return '分支路径为空'
        return ''

    if op == 'pose_correct':
        return _img_reason(step)

    if op in ('comm_send', 'comm_recv', 'send_data', 'receive_data'):
        if not bool(params.get('device') or params.get('channel') or params.get('message')):
            return '未绑定通讯设备/通道/报文'
        return ''

    if op == 'distort_correct':
        mode = params.get('mode') or 'file'
        if mode == 'file':
            if not bool(str(params.get('calibPath') or '').strip()):
                return '未指定标定文件路径'
            return ''
        if mode == 'coeffs':
            return ''
        return _img_reason(step)

    if op == 'nine_point':
        pts = params.get('points') or []
        enabled = [p for p in pts if isinstance(p, dict) and p.get('enabled', True)]
        filled = any(
            abs(float(p.get('pixelX') or 0)) + abs(float(p.get('pixelY') or 0))
            + abs(float(p.get('worldX') or 0)) + abs(float(p.get('worldY') or 0)) > 0
            for p in enabled
        )
        if not filled:
            return '九点标定尚未录入有效点'
        return ''

    if op == 'var_calc':
        rows = params.get('expressions') or []
        if not any(isinstance(r, dict) and str(r.get('name') or '').strip() for r in rows):
            return '变量计算表达式为空'
        return ''

    if op == 'variables':
        # 变量赋值：需要 name
        if not str(params.get('name') or '').strip():
            return '未填写变量名'
        return ''

    if op == 'elapsed_stats':
        if not (str(params.get('startStepId') or '').strip() and str(params.get('endStepId') or '').strip()):
            return '未选择起止步骤'
        return ''

    if op == 'format_data':
        if not str(params.get('template') or '').strip():
            return '未填写格式化模板'
        return ''

    if op == 'output_image':
        if not step.get('imageFrom'):
            return '未接线输入图像'
        if not str(params.get('path') or '').strip():
            return '未填写输出路径'
        return ''

    if op == 'protocol_parse':
        if not str(params.get('sourceVar') or '').strip():
            return '未指定源变量 sourceVar'
        return ''

    if op == 'text_save':
        if not str(params.get('path') or '').strip():
            return '未填写保存路径'
        return ''

    if op in ('geometry', 'rect_find', 'measure', 'caliper'):
        return _img_reason(step)

    if op in ('line_intersect', 'point_distance', 'point_line_distance', 'line_angle', 'point_circle_distance', 'circle_circle_distance'):
        if (params.get('mode') or 'bind') == 'manual':
            # still bang if judgeEnable but no resultVar alias for Host watch
            if params.get('judgeEnable') and not str(params.get('resultVar') or '').strip():
                return '已启用判定但未设置 resultVar'
            return ''
        keys = ('line1From', 'line2From', 'point1From', 'point2From', 'pointFrom', 'lineFrom', 'circleFrom', 'circle1From', 'circle2From')
        if not any(str(params.get(k) or '').strip() for k in keys):
            return '绑定模式下未选择几何输入'
        if params.get('judgeEnable') and not str(params.get('resultVar') or '').strip():
            return '已启用判定但未设置 resultVar'
        return ''

    if op == 'csharp_script':
        if not str(params.get('code') or '').strip():
            return '脚本代码为空'
        return ''

    if op == 'script':
        if not str(params.get('code') or params.get('script') or '').strip():
            return '脚本代码为空'
        return ''

    if op == 'production_task':
        if not str(params.get('taskName') or '').strip():
            return '未填写任务名'
        return ''

    if op == 'preprocess':
        return _img_reason(step)

    if op == 'display':
        return _img_reason(step)

    if op == 'defects':
        r = _img_reason(step)
        if r:
            return r
        if not (params.get('referencePath') or params.get('hasReference') or step.get('reference')):
            return '未加载缺陷参考图'
        return ''

    if op == 'barcode':
        return _img_reason(step)

    if op in ('yolo', 'yolo_segment'):
        r = _img_reason(step)
        if r:
            return r
        if not str(params.get('model') or '').strip():
            return '未指定 YOLO 模型'
        return ''

    if op == 'delay':
        return ''

    if op == 'branch_merge':
        return ''

    if op == 'loop':
        if not str(params.get('subflowId') or params.get('targetFlow') or '').strip():
            return '未指定子流程'
        return ''

    if op == 'subflow':
        if not str(params.get('subflowId') or '').strip():
            return '未指定子流程'
        return ''

    if op == 'ocr':
        r = _img_reason(step)
        if r:
            return r
        if str(params.get('roiMode') or 'inherit') == 'draw':
            roi = params.get('roi')
            if not (isinstance(roi, list) and len(roi) == 4):
                return 'OCR 绘制模式未设置 ROI'
        return ''

    if op in ('fixture', 'blob'):
        return _img_reason(step)

    # Point cloud family — need an input cloud / image binding when present
    if op in ('cloud_filter', 'cloud_plane', 'cloud_measure', 'cloud_height', 'cloud_register', 'cloud_cluster'):
        if not (
            step.get('imageFrom')
            or str(params.get('cloudFrom') or '').strip()
            or str(params.get('inputCloud') or '').strip()
            or str(params.get('source') or '').strip()
        ):
            return '未接线点云/图像输入'
        return ''

    return ''


def step_incomplete(step, project=None) -> bool:
    return bool(step_incomplete_reason(step, project))


def node_incomplete_reason(project, node_id: str) -> str:
    if node_id == 'source':
        return source_incomplete_reason(project.get('sourceConfig') if project else None)
    step = next((s for s in (project.get('steps') or []) if s.get('id') == node_id), None) if project else None
    return step_incomplete_reason(step, project)


def node_needs_bang(project, node_id: str) -> bool:
    """True → 画红叹号（未配置完整）。运行失败由 Node.run_failed 另画。"""
    return bool(node_incomplete_reason(project, node_id))


def project_incomplete_summary(project) -> tuple:
    """Return (ok: bool, message: str, incomplete_ids: list)."""
    project = project or {}
    bad = []
    reasons = []
    if node_needs_bang(project, 'source'):
        bad.append('source')
        reasons.append(node_incomplete_reason(project, 'source'))
    for step in project.get('steps') or []:
        sid = step.get('id')
        if sid and node_needs_bang(project, sid):
            bad.append(sid)
            reasons.append(node_incomplete_reason(project, sid))
    if not bad:
        return True, '组件配置完成', []
    n = len(bad)
    tip = reasons[0] if reasons else ''
    msg = f'组件参数未配置完整（{n}）'
    if tip:
        msg = f'{msg}：{tip}'
    return False, msg, bad
