"""Editable graph document; runtime validation remains authoritative in the engine."""
from copy import deepcopy
import uuid
from PySide6.QtCore import QObject, Signal


def uid():
    return uuid.uuid4().hex[:16]


def empty_project():
    from desktop.image_source import DEFAULT_SOURCE
    from copy import deepcopy as _dc
    proj = dict(version=2, id=uid(), name='未命名方案', steps=[], edges=[],
                sourcePosition=dict(x=300, y=40), variables={},
                sourceConfig=_dc(DEFAULT_SOURCE))
    try:
        from desktop import scheme as flow_scheme
        flow_scheme.ensure_scheme(proj)
    except Exception:
        pass
    return proj


class Document(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.project = empty_project()
        self.history = [deepcopy(self.project)]
        self.history_labels = ['']  # parallel to history; tip label for undo status
        self.index = 0
        self.saved = deepcopy(self.project)
        self.clipboard = None

    @property
    def modified(self):
        return self.project != self.saved

    def load(self, project):
        self.validate(project)
        project = deepcopy(project)
        if 'sourceConfig' not in project:
            from desktop.image_source import DEFAULT_SOURCE
            project['sourceConfig'] = deepcopy(DEFAULT_SOURCE)
        try:
            from desktop import scheme as flow_scheme
            flow_scheme.ensure_scheme(project)
        except Exception:
            pass
        self.project = project
        self.history, self.index = [deepcopy(project)], 0
        self.history_labels = ['']
        self.saved, self.clipboard = deepcopy(project), None
        self.changed.emit()

    @staticmethod
    def validate(p):
        if p.get('version') != 2 or not isinstance(p.get('steps'), list) or len(p['steps']) > 50:
            raise ValueError('工程版本无效或超过 50 个模块')
        ids = ['source'] + [s['id'] for s in p['steps']]
        if len(ids) != len(set(ids)):
            raise ValueError('模块编号重复')
        pairs = set()
        for e in p['edges']:
            if e['from'] not in ids or e['to'] not in ids or e['to'] == 'source' or e['from'] == e['to']:
                raise ValueError('连线端点无效')
            pair = (e['from'], e['to'])
            if pair in pairs:
                raise ValueError('连线已存在')
            pairs.add(pair)
        done = {'source'}
        remaining = set(ids) - done
        while remaining:
            ready = {n for n in remaining if all(e['from'] in done for e in p['edges'] if e['to'] == n)}
            if not ready:
                raise ValueError('不允许循环连线，请使用循环模块')
            remaining -= ready
            done |= ready

    def commit(self, p, label=None):
        self.validate(p)
        if p == self.project:
            return
        self.project = deepcopy(p)
        labels = list(getattr(self, 'history_labels', None) or [])
        # Keep labels aligned with truncated history prefix
        labels = labels[: self.index + 1]
        while len(labels) < self.index + 1:
            labels.append('')
        self.history = self.history[:self.index + 1] + [deepcopy(p)]
        labels = labels + [str(label) if label else '']
        if len(self.history) > 31:
            self.history.pop(0)
            if labels:
                labels.pop(0)
        self.history_labels = labels
        self.index = len(self.history) - 1
        self.changed.emit()

    def sync_history_labels(self):
        """Pad/trim history_labels after manual history assign (nest enter/exit)."""
        hist = list(getattr(self, 'history', None) or [])
        labels = list(getattr(self, 'history_labels', None) or [])
        while len(labels) < len(hist):
            labels.append('')
        if len(labels) > len(hist):
            labels = labels[: len(hist)]
        self.history_labels = labels

    def undo(self):
        if self.index:
            self.index -= 1
            self.project = deepcopy(self.history[self.index])
            self.changed.emit()

    def redo(self):
        if self.index + 1 < len(self.history):
            self.index += 1
            self.project = deepcopy(self.history[self.index])
            self.changed.emit()

    def jump_history(self, target_index):
        """Jump undo stack to target_index in one shot (labelled history menu)."""
        hist = list(getattr(self, 'history', None) or [])
        if not hist:
            return
        ti = int(target_index)
        if ti < 0 or ti >= len(hist):
            return
        if ti == self.index:
            return
        self.index = ti
        self.project = deepcopy(hist[self.index])
        self.changed.emit()

    def add(self, definition, position=None, parent='source'):
        p = deepcopy(self.project)
        pos = position or dict(x=300, y=160 + len(p['steps']) * 110)
        params = deepcopy(definition.get('defaults', {}))
        if definition.get('pluginId'):
            params = dict(pluginId=definition['pluginId'], pluginVersion=definition['pluginVersion'],
                          operatorId=definition['id'], arguments=params, inputs={})
        node = dict(id=uid(), operation=definition['operation'], name=definition['name'],
                    params=params, position=pos, imageFrom=parent if position is None else None,
                    variables={})
        p['steps'].append(node)
        if position is None:
            p['edges'].append(dict(id=uid(), **{'from': parent, 'to': node['id']}, fromPort='bottom', toPort='top'))
        self.commit(p)
        return node['id']

    def connect(self, origin, target, from_port='bottom', to_port='top'):
        p = deepcopy(self.project)
        # B1: 订阅线序 — 下方模块才能订阅上方（按画布 Y；同源链允许）
        def _pos(node_id):
            if node_id == 'source':
                return p.get('sourcePosition') or dict(x=0, y=0)
            step = next((s for s in p['steps'] if s['id'] == node_id), None)
            return (step or {}).get('position') or dict(x=0, y=0)
        oy, ty = _pos(origin).get('y', 0), _pos(target).get('y', 0)
        if ty + 8 < oy and from_port in ('bottom', 'right') and to_port in ('top', 'left'):
            raise ValueError('订阅线序：下方模块才能订阅上方模块输出（请将目标模块放到上游下方）')
        p['edges'].append(dict(id=uid(), **{'from': origin, 'to': target}, fromPort=from_port, toPort=to_port))
        node = next(s for s in p['steps'] if s['id'] == target)
        # 图像端口连线默认建立 imageFrom 订阅；侧向数据口不覆盖已有图像订阅
        if from_port in ('bottom', 'top') or not node.get('imageFrom'):
            if from_port != 'right' or not node.get('imageFrom'):
                if from_port in ('bottom',) or not node.get('imageFrom'):
                    node['imageFrom'] = origin
        self.commit(p)

    def remove(self, nodes=(), edges=()):
        p = deepcopy(self.project)
        p['steps'] = [s for s in p['steps'] if s['id'] not in nodes]
        p['edges'] = [e for e in p['edges'] if e['id'] not in edges and e['from'] not in nodes and e['to'] not in nodes]
        for step in p['steps']:
            incoming = [e['from'] for e in p['edges'] if e['to'] == step['id']]
            if step.get('imageFrom') not in incoming:
                step['imageFrom'] = next(iter(incoming), None)
        if p.get('outputNode') in nodes:
            p['outputNode'] = p['steps'][-1]['id'] if p['steps'] else None
        self.commit(p)

    def copy(self, ids):
        p = self.project
        self.clipboard = dict(project=p['id'], steps=deepcopy([s for s in p['steps'] if s['id'] in ids]),
                              edges=deepcopy([e for e in p['edges'] if e['to'] in ids]))

    def paste(self):
        clip = self.clipboard
        if not clip or clip['project'] != self.project['id']:
            return []
        mapping = {s['id']: uid() for s in clip['steps']}
        existing = {'source', *[s['id'] for s in self.project['steps']]}
        def remap(v):
            if isinstance(v, list):
                return [remap(x) for x in v]
            if not isinstance(v, dict):
                return v
            if set(v) == {'$ref'}:
                parts = v['$ref'].split('.')
                if len(parts) > 2 and parts[0] == 'results':
                    if parts[1] in mapping:
                        return {'$ref': '.'.join([parts[0], mapping[parts[1]], *parts[2:]])}
                    if parts[1] not in existing:
                        raise ValueError('复制内容引用了已删除的模块')
            return {k: remap(x) for k, x in v.items()}
        p = deepcopy(self.project)
        for node in clip['steps']:
            n = remap(deepcopy(node)); n['id'] = mapping[node['id']]
            n['imageFrom'] = mapping.get(node.get('imageFrom'), node.get('imageFrom'))
            n['position'] = {k: min(9800, v + 40) for k, v in n['position'].items()}
            n['name'] = (n.get('name', n['operation']) + ' 副本')[:80]
            p['steps'].append(n)
        for e in clip['edges']:
            if e['from'] in mapping or e['from'] in existing:
                p['edges'].append({**e, 'id': uid(), 'from': mapping.get(e['from'], e['from']), 'to': mapping[e['to']]})
        self.commit(p)
        return list(mapping.values())

    def layout(self):
        p = deepcopy(self.project)
        levels = {'source': 0}
        todo = list(p['steps'])
        while todo:
            for node in list(todo):
                parents = [e['from'] for e in p['edges'] if e['to'] == node['id']]
                if all(x in levels for x in parents):
                    levels[node['id']] = 1 + max([levels[x] for x in parents] or [0]);todo.remove(node)
        rows = {}
        for n in p['steps']:
            row = rows.setdefault(levels[n['id']], [])
            n['position'] = dict(x=60 + (len(row) % 8) * 270, y=60 + levels[n['id']] * 140 + (len(row) // 8) * 100)
            row.append(n)
        p['sourcePosition'] = dict(x=60, y=40)
        self.commit(p)
