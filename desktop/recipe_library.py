"""产线配方 / 换型 — project-level recipe snapshots + library sources.

Grounded in existing scheme/project library (no cloud / no robot SDK).
`project["recipes"]` holds named snapshots of step params (+ optional variables
and production_task recipe string). Switching applies params onto matching
steps by (operation, name) then id; full 换型 can also open a .sieans from
templates / projects / 本机工程库.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path

from desktop.model import uid


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def ensure_recipes(project: dict) -> list:
    """Ensure project['recipes'] list exists; return it."""
    recipes = project.get('recipes')
    if not isinstance(recipes, list):
        recipes = []
        project['recipes'] = recipes
    return recipes


def list_recipes(project: dict) -> list:
    return list(ensure_recipes(project))


def active_recipe_id(project: dict) -> str:
    return str(project.get('activeRecipeId') or '')


def active_recipe_name(project: dict) -> str:
    rid = active_recipe_id(project)
    for r in ensure_recipes(project):
        if isinstance(r, dict) and r.get('id') == rid:
            return str(r.get('name') or rid)
    # fallback: production_task recipe field
    for s in project.get('steps') or []:
        if not isinstance(s, dict):
            continue
        if s.get('operation') == 'production_task':
            return str((s.get('params') or {}).get('recipe') or '')
    return ''


def _step_snapshot(step: dict) -> dict:
    return {
        'id': step.get('id'),
        'name': step.get('name'),
        'operation': step.get('operation'),
        'params': deepcopy(step.get('params') or {}),
        'imageFrom': step.get('imageFrom'),
    }


def capture_recipe(project: dict, name: str, note: str = '',
                   variant: str = '', var_keys=None, step_ops=None) -> dict:
    """Snapshot current top-level steps (+ variables shell) as a named recipe.

    variant: product variant label (e.g. A型/B型) for partial-apply grouping.
    var_keys: optional list of variable names to keep in snapshot (subset).
    step_ops: optional list of operations to keep in snapshot (subset).
    """
    name = (name or '').strip() or f'配方{_now()}'
    variant = (variant or '').strip()
    want_ops = {str(x).strip() for x in (step_ops or []) if str(x).strip()} or None
    want_vars = {str(x).strip() for x in (var_keys or []) if str(x).strip()} or None
    snap_steps = []
    for s in (project.get('steps') or []):
        if not isinstance(s, dict):
            continue
        if want_ops and (s.get('operation') or '') not in want_ops:
            continue
        snap_steps.append(_step_snapshot(s))
    # light variables copy (names/values only; skip huge images)
    vars_out = {}
    raw_vars = project.get('variables')
    if isinstance(raw_vars, dict):
        for scope, bucket in raw_vars.items():
            if not isinstance(bucket, dict):
                continue
            slim = {}
            for k, v in bucket.items():
                if want_vars and k not in want_vars:
                    continue
                if isinstance(v, str) and (v.startswith('data:image/') or len(v) > 4096):
                    continue
                slim[k] = deepcopy(v)
            if slim:
                vars_out[scope] = slim
    entry = {
        'id': uid(),
        'name': name,
        'note': (note or '').strip(),
        'variant': variant,
        'varKeys': sorted(want_vars) if want_vars else [],
        'stepOps': sorted(want_ops) if want_ops else [],
        'updatedAt': _now(),
        'stepCount': len(snap_steps),
        'snapshot': {
            'steps': snap_steps,
            'variables': vars_out,
            'productionRecipe': name,
            'variant': variant,
            'varKeys': sorted(want_vars) if want_vars else [],
            'stepOps': sorted(want_ops) if want_ops else [],
        },
    }
    recipes = ensure_recipes(project)
    recipes.append(entry)
    project['activeRecipeId'] = entry['id']
    _sync_production_recipe_field(project, name)
    return entry


def delete_recipe(project: dict, recipe_id: str) -> bool:
    recipes = ensure_recipes(project)
    before = len(recipes)
    project['recipes'] = [r for r in recipes if not (isinstance(r, dict) and r.get('id') == recipe_id)]
    if project.get('activeRecipeId') == recipe_id:
        project['activeRecipeId'] = ''
    return len(project['recipes']) < before


def _match_step(live_steps: list, snap: dict):
    """Prefer operation+name, then id, then operation alone (first unused)."""
    op = snap.get('operation')
    name = snap.get('name')
    sid = snap.get('id')
    for s in live_steps:
        if s.get('operation') == op and s.get('name') == name:
            return s
    for s in live_steps:
        if sid and s.get('id') == sid:
            return s
    for s in live_steps:
        if s.get('operation') == op:
            return s
    return None


def apply_recipe(project: dict, recipe_id: str, *,
                 var_keys=None, step_ops=None, steps_only: bool = False,
                 vars_only: bool = False) -> dict:
    """Apply recipe snapshot params onto matching live steps. Returns stats.

    Partial apply:
      var_keys  — only merge these variable names (None = all in snapshot)
      step_ops  — only apply steps whose operation is in this set (None = all)
      steps_only / vars_only — skip the other half
    """
    recipes = ensure_recipes(project)
    entry = next((r for r in recipes if isinstance(r, dict) and r.get('id') == recipe_id), None)
    if not entry:
        raise ValueError('配方不存在')
    snap = entry.get('snapshot') or {}
    snap_steps = snap.get('steps') or []
    live = [s for s in (project.get('steps') or []) if isinstance(s, dict)]
    want_ops = {str(x).strip() for x in (step_ops or []) if str(x).strip()} or None
    # fall back to recipe-stored subset if caller did not override
    if want_ops is None and entry.get('stepOps'):
        want_ops = {str(x).strip() for x in entry.get('stepOps') if str(x).strip()} or None
    want_vars = {str(x).strip() for x in (var_keys or []) if str(x).strip()} or None
    if want_vars is None and entry.get('varKeys'):
        want_vars = {str(x).strip() for x in entry.get('varKeys') if str(x).strip()} or None

    applied = 0
    skipped = 0
    if not vars_only:
        for row in snap_steps:
            if not isinstance(row, dict):
                continue
            if want_ops and (row.get('operation') or '') not in want_ops:
                skipped += 1
                continue
            target = _match_step(live, row)
            if target is None:
                skipped += 1
                continue
            params = row.get('params')
            if isinstance(params, dict):
                target['params'] = deepcopy(params)
                applied += 1
            if row.get('imageFrom') is not None:
                target['imageFrom'] = row.get('imageFrom')
    vars_applied = 0
    if not steps_only:
        vars_in = snap.get('variables')
        if isinstance(vars_in, dict):
            dest = project.setdefault('variables', {})
            if not isinstance(dest, dict):
                project['variables'] = {}
                dest = project['variables']
            for scope, bucket in vars_in.items():
                if not isinstance(bucket, dict):
                    continue
                slot = dest.setdefault(scope, {})
                if not isinstance(slot, dict):
                    continue
                for k, v in bucket.items():
                    if want_vars and k not in want_vars:
                        continue
                    slot[k] = deepcopy(v)
                    vars_applied += 1
    name = str(entry.get('name') or '')
    project['activeRecipeId'] = entry['id']
    if entry.get('variant'):
        project['activeRecipeVariant'] = entry.get('variant')
    _sync_production_recipe_field(project, name)
    entry['updatedAt'] = entry.get('updatedAt') or _now()
    return {
        'applied': applied, 'skipped': skipped, 'varsApplied': vars_applied,
        'name': name, 'id': entry['id'],
        'variant': entry.get('variant') or '',
        'partial': bool(want_ops or want_vars or steps_only or vars_only),
    }


def list_variants(project: dict) -> list:
    """Unique product variant labels present on recipes (stable order)."""
    seen = []
    for r in ensure_recipes(project):
        if not isinstance(r, dict):
            continue
        v = str(r.get('variant') or '').strip()
        if v and v not in seen:
            seen.append(v)
    return seen


def recipes_for_variant(project: dict, variant: str) -> list:
    variant = (variant or '').strip()
    out = []
    for r in ensure_recipes(project):
        if not isinstance(r, dict):
            continue
        if not variant or str(r.get('variant') or '').strip() == variant:
            out.append(r)
    return out


def _sync_production_recipe_field(project: dict, name: str):
    for s in project.get('steps') or []:
        if isinstance(s, dict) and s.get('operation') == 'production_task':
            params = s.setdefault('params', {})
            if isinstance(params, dict):
                params['recipe'] = name


def discover_library_sources(root: Path) -> list:
    """List .sieans from projects/ + templates + data native-desktop projects as 换型源."""
    root = Path(root)
    out = []
    seen = set()

    def add(path: Path, kind: str):
        try:
            rp = str(path.resolve())
        except Exception:
            rp = str(path)
        if rp in seen or not path.is_file():
            return
        seen.add(rp)
        out.append({
            'path': rp,
            'name': path.stem,
            'kind': kind,
            'rel': str(path.relative_to(root)) if str(path).startswith(str(root)) else path.name,
        })

    for p in sorted((root / 'projects').glob('*.sieans')):
        add(p, '打开即跑' if p.name.startswith('open-and-run') else '工程')
    for p in sorted((root / 'projects' / 'templates').glob('*.sieans')):
        add(p, '模板')
    data_proj = root / 'data' / 'native-desktop' / 'projects'
    if data_proj.is_dir():
        for p in sorted(data_proj.rglob('*.sieans'))[:40]:
            add(p, '本机库')
    return out


def load_sieans(path) -> dict:
    import json
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('无效方案文件')
    return data
