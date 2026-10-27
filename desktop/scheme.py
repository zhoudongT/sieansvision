"""Multi-flow scheme helpers — VisionMaster 方案(.sol) ⊃ 流程(.prc) layering.

Top-level steps/edges/source* remain the *active* flow for the engine.
`flows[]` holds all processes; sync helpers keep them consistent.
"""
from copy import deepcopy
from desktop.model import uid


FLOW_KEYS = (
    'steps', 'edges', 'sourcePosition', 'sourceConfig', 'outputNode',
)


def empty_flow(name='流程1', index=0):
    from desktop.image_source import DEFAULT_SOURCE
    return dict(
        id=uid(),
        name=name,
        steps=[],
        edges=[],
        sourcePosition=dict(x=300, y=40),
        sourceConfig=deepcopy(DEFAULT_SOURCE),
        enabled=True,
        runIntervalMs=0,
        stopOnNg=False,
        timeoutMs=0,
        runCount=0,
        lastElapsedMs=0,
        cardPosition=dict(x=80 + (index % 3) * 280, y=80 + (index // 3) * 200),
        io=dict(inputs=[], outputs=[], display={}),
    )


def _flow_payload_from_top(project):
    payload = {}
    for key in FLOW_KEYS:
        if key in project:
            payload[key] = deepcopy(project[key])
    return payload


def _apply_payload_to_top(project, payload):
    for key in FLOW_KEYS:
        if key in payload:
            project[key] = deepcopy(payload[key])
        elif key in ('outputNode',):
            project.pop(key, None)
    if 'sourceConfig' not in project:
        from desktop.image_source import DEFAULT_SOURCE
        project['sourceConfig'] = deepcopy(DEFAULT_SOURCE)
    if 'sourcePosition' not in project:
        project['sourcePosition'] = dict(x=300, y=40)
    project.setdefault('steps', [])
    project.setdefault('edges', [])


def ensure_scheme(project):
    """Ensure project has flows[] + activeFlowId; migrate legacy single-flow."""
    if not isinstance(project, dict):
        raise ValueError('工程无效')
    flows = project.get('flows')
    if isinstance(flows, list) and flows:
        active = project.get('activeFlowId')
        ids = {f.get('id') for f in flows if isinstance(f, dict)}
        if active not in ids:
            project['activeFlowId'] = flows[0]['id']
            active = project['activeFlowId']
        # Keep top-level in sync with active if steps look empty but flow has content
        current = next((f for f in flows if f.get('id') == active), flows[0])
        if not project.get('steps') and current.get('steps'):
            _apply_payload_to_top(project, current)
        project.setdefault('flowEdges', [])
        return project
    # Migrate: wrap current top-level as 流程1
    flow = empty_flow('流程1', 0)
    flow.update(_flow_payload_from_top(project))
    if not flow.get('name'):
        flow['name'] = '流程1'
    project['flows'] = [flow]
    project['activeFlowId'] = flow['id']
    project.setdefault('flowEdges', [])
    return project


def sync_active_into_flows(project):
    """Write top-level module graph into the active flow entry."""
    ensure_scheme(project)
    active = project['activeFlowId']
    for flow in project['flows']:
        if flow.get('id') == active:
            flow.update(_flow_payload_from_top(project))
            return flow
    # orphan active id — append
    flow = empty_flow('流程1', len(project['flows']))
    flow['id'] = active
    flow.update(_flow_payload_from_top(project))
    project['flows'].append(flow)
    return flow


def activate_flow(project, flow_id):
    """Persist current top-level into old active, then load flow_id to top-level."""
    ensure_scheme(project)
    sync_active_into_flows(project)
    target = next((f for f in project['flows'] if f.get('id') == flow_id), None)
    if target is None:
        raise ValueError('流程不存在')
    project['activeFlowId'] = flow_id
    _apply_payload_to_top(project, target)
    return target


def add_flow(project, name=None):
    ensure_scheme(project)
    sync_active_into_flows(project)
    index = len(project['flows'])
    flow = empty_flow(name or f'流程{index + 1}', index)
    project['flows'].append(flow)
    return flow


def duplicate_flow(project, flow_id):
    ensure_scheme(project)
    sync_active_into_flows(project)
    src = next((f for f in project['flows'] if f.get('id') == flow_id), None)
    if src is None:
        raise ValueError('流程不存在')
    copy = deepcopy(src)
    copy['id'] = uid()
    copy['name'] = (src.get('name') or '流程') + ' 副本'
    copy['runCount'] = 0
    copy['lastElapsedMs'] = 0
    # Remap step ids so copies are independent
    step_map = {s['id']: uid() for s in copy.get('steps', [])}
    for step in copy.get('steps', []):
        old = step['id']
        step['id'] = step_map[old]
        if step.get('imageFrom') in step_map:
            step['imageFrom'] = step_map[step['imageFrom']]
        elif step.get('imageFrom') == 'source':
            pass
        pos = step.get('position') or {}
        step['position'] = dict(x=min(9800, (pos.get('x') or 0) + 40),
                                y=min(9800, (pos.get('y') or 0) + 40))
    new_edges = []
    for edge in copy.get('edges', []):
        e = deepcopy(edge)
        e['id'] = uid()
        if e.get('from') in step_map:
            e['from'] = step_map[e['from']]
        if e.get('to') in step_map:
            e['to'] = step_map[e['to']]
        else:
            continue
        new_edges.append(e)
    copy['edges'] = new_edges
    if copy.get('outputNode') in step_map:
        copy['outputNode'] = step_map[copy['outputNode']]
    idx = len(project['flows'])
    copy['cardPosition'] = dict(x=80 + (idx % 3) * 280, y=80 + (idx // 3) * 200)
    project['flows'].append(copy)
    return copy


def remove_flow(project, flow_id):
    ensure_scheme(project)
    sync_active_into_flows(project)
    if len(project['flows']) <= 1:
        raise ValueError('至少保留一个流程')
    project['flows'] = [f for f in project['flows'] if f.get('id') != flow_id]
    project['flowEdges'] = [e for e in project.get('flowEdges', [])
                            if e.get('from') != flow_id and e.get('to') != flow_id]
    if project.get('activeFlowId') == flow_id:
        activate_flow(project, project['flows'][0]['id'])
    return project


def rename_flow(project, flow_id, name):
    ensure_scheme(project)
    sync_active_into_flows(project)
    name = (name or '').strip() or '未命名流程'
    for flow in project['flows']:
        if flow.get('id') == flow_id:
            flow['name'] = name[:80]
            return flow
    raise ValueError('流程不存在')


def update_flow_meta(project, flow_id, **meta):
    ensure_scheme(project)
    sync_active_into_flows(project)
    for flow in project['flows']:
        if flow.get('id') == flow_id:
            for key, value in meta.items():
                if key in ('runIntervalMs', 'stopOnNg', 'timeoutMs', 'enabled',
                           'runCount', 'lastElapsedMs', 'cardPosition', 'io', 'name'):
                    flow[key] = value
            return flow
    raise ValueError('流程不存在')


def export_prc(project, flow_id):
    """Serialize one flow as .prc JSON (VM label; JSON under the hood)."""
    ensure_scheme(project)
    sync_active_into_flows(project)
    flow = next((f for f in project['flows'] if f.get('id') == flow_id), None)
    if flow is None:
        raise ValueError('流程不存在')
    return dict(
        format='sieans.prc',
        version=1,
        kind='process',
        flow=deepcopy(flow),
        exportedFrom=dict(schemeId=project.get('id'), schemeName=project.get('name')),
    )


def import_prc(project, payload):
    """Import a .prc into the scheme as a new flow."""
    ensure_scheme(project)
    sync_active_into_flows(project)
    if isinstance(payload, dict) and 'flow' in payload:
        flow = deepcopy(payload['flow'])
    elif isinstance(payload, dict) and 'steps' in payload:
        flow = empty_flow(payload.get('name') or '导入流程', len(project['flows']))
        flow.update({k: deepcopy(payload[k]) for k in FLOW_KEYS if k in payload})
        for k in ('enabled', 'runIntervalMs', 'stopOnNg', 'timeoutMs', 'io'):
            if k in payload:
                flow[k] = deepcopy(payload[k])
    else:
        raise ValueError('无效的流程文件（.prc）')
    flow['id'] = uid()
    # Remap step ids to avoid collisions
    step_map = {s['id']: uid() for s in flow.get('steps', [])}
    for step in flow.get('steps', []):
        step['id'] = step_map[step['id']]
        if step.get('imageFrom') in step_map:
            step['imageFrom'] = step_map[step['imageFrom']]
    new_edges = []
    for edge in flow.get('edges', []):
        e = deepcopy(edge)
        e['id'] = uid()
        if e.get('from') in step_map:
            e['from'] = step_map[e['from']]
        elif e.get('from') != 'source':
            continue
        if e.get('to') in step_map:
            e['to'] = step_map[e['to']]
        else:
            continue
        new_edges.append(e)
    flow['edges'] = new_edges
    if flow.get('outputNode') in step_map:
        flow['outputNode'] = step_map[flow['outputNode']]
    flow['name'] = (flow.get('name') or '导入流程')[:80]
    flow['runCount'] = 0
    flow['lastElapsedMs'] = 0
    idx = len(project['flows'])
    flow['cardPosition'] = dict(x=80 + (idx % 3) * 280, y=80 + (idx // 3) * 200)
    project['flows'].append(flow)
    return flow


def scheme_for_disk(project):
    """Snapshot suitable for .sol / .sieans save (includes flows)."""
    out = deepcopy(project)
    ensure_scheme(out)
    sync_active_into_flows(out)
    return out
