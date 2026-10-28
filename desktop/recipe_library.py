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

# wave22: 换型失败码（MainWindow._report_variant_fail 对齐）
FAIL_CODES = {
    'VARIANT_EMPTY': '变体名为空',
    'VARIANT_NO_RECIPES': '变体下无配方',
    'RECIPE_MISSING': '配方不存在',
    'APPLY_ERROR': '换型套用异常',
    'ENTER_RUN_FAIL': '切运行态失败',
    'TRIAL_FIRE_FAIL': '单次试跑触发失败',
}


def fail_message(code: str, detail: str = '') -> str:
    base = FAIL_CODES.get(str(code or ''), str(code or 'APPLY_ERROR'))
    detail = str(detail or '').strip()
    return f'{base} · {detail}' if detail else base


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



def capture_project_snapshot_for_rollback(project: dict) -> dict:
    """Deep-copy the mutable halves that apply_recipe can touch (for one-click rollback)."""
    if not isinstance(project, dict):
        return {}
    return {
        'steps': deepcopy(project.get('steps') or []),
        'variables': deepcopy(project.get('variables') or {}),
        'activeRecipeId': project.get('activeRecipeId'),
        'activeRecipeVariant': project.get('activeRecipeVariant'),
        'productionRecipe': deepcopy(project.get('productionRecipe'))
            if isinstance(project.get('productionRecipe'), dict)
            else project.get('productionRecipe'),
    }


def restore_project_snapshot(project: dict, snap: dict | None) -> dict:
    """Restore a prior capture_project_snapshot_for_rollback into project. Returns stats."""
    if not isinstance(project, dict) or not isinstance(snap, dict):
        return {'ok': False, 'reason': 'empty'}
    if 'steps' in snap:
        project['steps'] = deepcopy(snap.get('steps') or [])
    if 'variables' in snap:
        project['variables'] = deepcopy(snap.get('variables') or {})
    for k in ('activeRecipeId', 'activeRecipeVariant', 'productionRecipe'):
        if k in snap:
            if snap[k] is None:
                project.pop(k, None)
            else:
                project[k] = deepcopy(snap[k]) if isinstance(snap[k], (dict, list)) else snap[k]
    return {
        'ok': True,
        'steps': len(project.get('steps') or []),
        'restoredKeys': [k for k in ('steps', 'variables', 'activeRecipeId',
                                     'activeRecipeVariant', 'productionRecipe') if k in snap],
    }


def preview_apply_recipe(project: dict, recipe_id: str, *,
                         var_keys=None, step_ops=None,
                         steps_only: bool = False, vars_only: bool = False) -> dict:
    """Dry-run apply on a deep copy — never mutates project. Returns preview bag.

    Bag keys:
      diff          — diff_recipe output
      wouldApply    — apply_recipe stats against a scratch copy
      projected     — scratch project after would-be apply (caller may inspect)
      sideBySide    — format_diff_side_by_side rows
      chip          — format_diff_chip
    """
    live = project if isinstance(project, dict) else {}
    diff = diff_recipe(
        live, recipe_id,
        var_keys=var_keys, step_ops=step_ops,
        steps_only=steps_only, vars_only=vars_only,
    )
    scratch = deepcopy(live)
    stats = apply_recipe(
        scratch, recipe_id,
        var_keys=var_keys, step_ops=step_ops,
        steps_only=steps_only, vars_only=vars_only,
    )
    return {
        'diff': diff,
        'wouldApply': stats,
        'projected': scratch,
        'sideBySide': format_diff_side_by_side(diff),
        'chip': format_diff_chip(diff),
        'name': stats.get('name') or diff.get('name') or '',
        'id': recipe_id,
        'mutatedLive': False,
    }


def apply_recipe_with_rollback(project: dict, recipe_id: str, *,
                               var_keys=None, step_ops=None,
                               steps_only: bool = False, vars_only: bool = False,
                               store_key: str = '_recipeRollbackSnap',
                               stack_key: str = '_recipeRollbackStack',
                               stack_cap: int = 16) -> dict:
    """Apply recipe and push a rollback snapshot onto a multi-step history stack.

    Also mirrors the top entry at project[store_key] for one-shot callers.
    Soft / no hardware. Cap defaults to 16.
    """
    if not isinstance(project, dict):
        raise ValueError('project required')
    snap = capture_project_snapshot_for_rollback(project)
    stats = apply_recipe(
        project, recipe_id,
        var_keys=var_keys, step_ops=step_ops,
        steps_only=steps_only, vars_only=vars_only,
    )
    entry = {
        'snapshot': snap,
        'recipeId': recipe_id,
        'name': stats.get('name') or '',
        'appliedAt': _now(),
        'stats': {
            'applied': stats.get('applied'),
            'skipped': stats.get('skipped'),
            'varsApplied': stats.get('varsApplied'),
        },
    }
    stack = project.get(stack_key)
    if not isinstance(stack, list):
        stack = []
        # migrate legacy one-shot snap into stack if present
        legacy = project.get(store_key)
        if isinstance(legacy, dict) and isinstance(legacy.get('snapshot'), dict):
            stack.append(legacy)
    stack.append(entry)
    cap = max(1, int(stack_cap or 16))
    if len(stack) > cap:
        stack = stack[-cap:]
    project[stack_key] = stack
    project[store_key] = entry  # top mirror for one-shot API
    out = dict(stats)
    out['rollbackReady'] = True
    out['rollbackKey'] = store_key
    out['rollbackStackKey'] = stack_key
    out['rollbackDepth'] = len(stack)
    return out


def rollback_last_recipe_apply(project: dict, *,
                               store_key: str = '_recipeRollbackSnap',
                               stack_key: str = '_recipeRollbackStack') -> dict:
    """Pop one step from the rollback history stack (soft / no hardware).

    Falls back to legacy project[store_key] when the stack is empty.
    """
    if not isinstance(project, dict):
        return {'ok': False, 'reason': 'no project'}
    stack = project.get(stack_key)
    bag = None
    if isinstance(stack, list) and stack:
        bag = stack.pop()
        project[stack_key] = stack
        if stack:
            project[store_key] = stack[-1]
        else:
            project.pop(store_key, None)
    else:
        bag = project.get(store_key)
        project.pop(store_key, None)
        project.pop(stack_key, None)
    if not isinstance(bag, dict) or not isinstance(bag.get('snapshot'), dict):
        return {'ok': False, 'reason': 'no rollback snapshot'}
    stats = restore_project_snapshot(project, bag.get('snapshot'))
    name = bag.get('name') or bag.get('recipeId') or ''
    stats['ok'] = True
    stats['rolledBack'] = name
    stats['recipeId'] = bag.get('recipeId') or ''
    depth = len(project.get(stack_key) or []) if isinstance(project.get(stack_key), list) else 0
    stats['rollbackDepth'] = depth
    stats['remaining'] = depth
    return stats


def has_recipe_rollback(project: dict, *, store_key: str = '_recipeRollbackSnap',
                        stack_key: str = '_recipeRollbackStack') -> bool:
    if not isinstance(project, dict):
        return False
    stack = project.get(stack_key)
    if isinstance(stack, list) and any(
        isinstance(e, dict) and isinstance(e.get('snapshot'), dict) for e in stack
    ):
        return True
    bag = project.get(store_key)
    return isinstance(bag, dict) and isinstance(bag.get('snapshot'), dict)


def recipe_rollback_depth(project: dict, *,
                          store_key: str = '_recipeRollbackSnap',
                          stack_key: str = '_recipeRollbackStack') -> int:
    """How many soft rollback steps are available."""
    if not isinstance(project, dict):
        return 0
    stack = project.get(stack_key)
    if isinstance(stack, list):
        return sum(
            1 for e in stack
            if isinstance(e, dict) and isinstance(e.get('snapshot'), dict)
        )
    bag = project.get(store_key)
    return 1 if isinstance(bag, dict) and isinstance(bag.get('snapshot'), dict) else 0


def list_recipe_rollback_stack(project: dict, *,
                               stack_key: str = '_recipeRollbackStack',
                               store_key: str = '_recipeRollbackSnap') -> list:
    """Newest-last list of {name,recipeId,appliedAt,stats} (no heavy snapshots)."""
    if not isinstance(project, dict):
        return []
    stack = project.get(stack_key)
    rows = []
    if isinstance(stack, list):
        src = stack
    else:
        bag = project.get(store_key)
        src = [bag] if isinstance(bag, dict) else []
    for e in src:
        if not isinstance(e, dict) or not isinstance(e.get('snapshot'), dict):
            continue
        rows.append({
            'name': e.get('name') or '',
            'recipeId': e.get('recipeId') or '',
            'appliedAt': e.get('appliedAt') or '',
            'stats': dict(e.get('stats') or {}),
        })
    return rows


def rollback_recipe_n_steps(project: dict, n: int = 1, *,
                            store_key: str = '_recipeRollbackSnap',
                            stack_key: str = '_recipeRollbackStack') -> dict:
    """Roll back up to n history steps (soft). Returns aggregate stats."""
    if not isinstance(project, dict):
        return {'ok': False, 'reason': 'no project', 'steps': 0}
    want = max(0, int(n or 0))
    if want <= 0:
        return {'ok': False, 'reason': 'n<=0', 'steps': 0}
    rolled = []
    last = None
    for _ in range(want):
        last = rollback_last_recipe_apply(
            project, store_key=store_key, stack_key=stack_key,
        )
        if not last.get('ok'):
            break
        rolled.append(last.get('rolledBack') or last.get('recipeId') or '')
    return {
        'ok': bool(rolled),
        'steps': len(rolled),
        'rolledBack': list(rolled),
        'remaining': recipe_rollback_depth(
            project, store_key=store_key, stack_key=stack_key,
        ),
        'last': last,
        'reason': (None if rolled else (last or {}).get('reason') or 'empty'),
    }


def diff_recipe(project: dict, recipe_id: str, *,
                var_keys=None, step_ops=None, steps_only: bool = False,
                vars_only: bool = False) -> dict:
    """Preview params/vars delta vs live project without mutating.

    Returns {
      stepDeltas:[{id,name,op,changedKeys,from,to,sample}],
      varDeltas:[{scope,key,from,to}],
      summary:{stepsChanged,stepsSame,stepsMissing,varsChanged,chip},
      name, variant, id,
    }
    """
    recipes = ensure_recipes(project)
    entry = next((r for r in recipes if isinstance(r, dict) and r.get('id') == recipe_id), None)
    if not entry:
        raise ValueError('配方不存在')
    snap = entry.get('snapshot') or {}
    snap_steps = snap.get('steps') or []
    live = [s for s in (project.get('steps') or []) if isinstance(s, dict)]
    want_ops = {str(x).strip() for x in (step_ops or []) if str(x).strip()} or None
    if want_ops is None and entry.get('stepOps'):
        want_ops = {str(x).strip() for x in entry.get('stepOps') if str(x).strip()} or None
    want_vars = {str(x).strip() for x in (var_keys or []) if str(x).strip()} or None
    if want_vars is None and entry.get('varKeys'):
        want_vars = {str(x).strip() for x in entry.get('varKeys') if str(x).strip()} or None

    step_deltas = []
    same = 0
    missing = 0
    if not vars_only:
        for row in snap_steps:
            if not isinstance(row, dict):
                continue
            if want_ops and (row.get('operation') or '') not in want_ops:
                continue
            target = _match_step(live, row)
            if target is None:
                missing += 1
                step_deltas.append({
                    'id': row.get('id'), 'name': row.get('name'),
                    'op': row.get('operation'), 'changedKeys': ['(无匹配模块)'],
                    'from': None, 'to': row.get('params'), 'sample': '缺失',
                })
                continue
            live_p = target.get('params') if isinstance(target.get('params'), dict) else {}
            snap_p = row.get('params') if isinstance(row.get('params'), dict) else {}
            changed = []
            samples = []
            keys = sorted(set(live_p) | set(snap_p))
            for k in keys:
                lv, sv = live_p.get(k), snap_p.get(k)
                if lv != sv:
                    changed.append(k)
                    if len(samples) < 3:
                        samples.append(f'{k}:{lv!r}→{sv!r}')
            # also imageFrom
            if row.get('imageFrom') is not None and row.get('imageFrom') != target.get('imageFrom'):
                changed.append('imageFrom')
                samples.append(f"imageFrom:{target.get('imageFrom')!r}→{row.get('imageFrom')!r}")
            if changed:
                step_deltas.append({
                    'id': target.get('id') or row.get('id'),
                    'name': target.get('name') or row.get('name'),
                    'op': target.get('operation') or row.get('operation'),
                    'changedKeys': changed,
                    'from': {k: live_p.get(k) for k in changed if k != 'imageFrom'},
                    'to': {k: snap_p.get(k) for k in changed if k != 'imageFrom'},
                    'sample': '；'.join(samples),
                })
            else:
                same += 1

    var_deltas = []
    if not steps_only:
        vars_in = snap.get('variables')
        live_vars = project.get('variables') if isinstance(project.get('variables'), dict) else {}
        if isinstance(vars_in, dict):
            for scope, bucket in vars_in.items():
                if not isinstance(bucket, dict):
                    continue
                live_bucket = live_vars.get(scope) if isinstance(live_vars.get(scope), dict) else {}
                for k, v in bucket.items():
                    if want_vars and k not in want_vars:
                        continue
                    lv = live_bucket.get(k)
                    if lv != v:
                        var_deltas.append({
                            'scope': scope, 'key': k, 'from': lv, 'to': v,
                        })

    n_step = len([d for d in step_deltas if d.get('sample') != '缺失'])
    n_miss = missing
    n_var = len(var_deltas)
    # params delta chip text
    chip_bits = []
    if n_step:
        chip_bits.append(f'模块Δ{n_step}')
    if n_miss:
        chip_bits.append(f'缺{n_miss}')
    if same:
        chip_bits.append(f'同{same}')
    if n_var:
        chip_bits.append(f'变量Δ{n_var}')
    if not chip_bits:
        chip_bits.append('无变化')
    # sample keys for chip
    key_samples = []
    for d in step_deltas[:4]:
        keys = d.get('changedKeys') or []
        if keys and keys[0] != '(无匹配模块)':
            key_samples.append(f"{d.get('name') or d.get('op')}:{','.join(keys[:2])}")
    for vd in var_deltas[:3]:
        key_samples.append(f"{vd['scope']}.{vd['key']}")
    chip = ' · '.join(chip_bits)
    if key_samples:
        chip += ' · ' + '；'.join(key_samples[:4])
        if (n_step + n_var) > 4:
            chip += '…'

    return {
        'stepDeltas': step_deltas,
        'varDeltas': var_deltas,
        'summary': {
            'stepsChanged': n_step,
            'stepsSame': same,
            'stepsMissing': n_miss,
            'varsChanged': n_var,
            'chip': chip,
        },
        'name': str(entry.get('name') or ''),
        'variant': entry.get('variant') or '',
        'id': entry['id'],
    }


def format_diff_chip(diff: dict | None) -> str:
    """Short Chinese chip for dialogs / tooltips."""
    if not isinstance(diff, dict):
        return '无差分'
    s = (diff.get('summary') or {}).get('chip')
    return s or '无变化'


def format_diff_detail(diff: dict | None, *, max_steps: int = 40, max_vars: int = 30) -> list:
    """行级差分列表，供换型对话框详情区显示。"""
    rows = []
    if not isinstance(diff, dict):
        return [{'kind': 'info', 'text': '无差分'}]
    for d in (diff.get('stepDeltas') or [])[:max_steps]:
        name = d.get('name') or d.get('op') or d.get('id') or '?'
        op = d.get('op') or ''
        sample = d.get('sample') or ','.join(d.get('changedKeys') or [])
        keys = d.get('changedKeys') or []
        kind = 'missing' if sample == '缺失' or (keys and keys[0] == '(无匹配模块)') else 'step'
        rows.append({
            'kind': kind,
            'text': f"[模块] {name} ({op}) · {sample}",
            'id': d.get('id'), 'op': op, 'name': name,
            'changedKeys': keys, 'from': d.get('from'), 'to': d.get('to'),
        })
    for vd in (diff.get('varDeltas') or [])[:max_vars]:
        rows.append({
            'kind': 'var',
            'text': f"[变量] {vd.get('scope')}.{vd.get('key')}: {vd.get('from')!r} → {vd.get('to')!r}",
            'scope': vd.get('scope'), 'key': vd.get('key'),
            'from': vd.get('from'), 'to': vd.get('to'),
        })
    if not rows:
        rows.append({'kind': 'info', 'text': '与当前工程无参数/变量差异'})
    return rows




def format_diff_side_by_side(diff: dict | None, *, max_rows: int = 60) -> list:
    """Side-by-side dry-run rows: current vs recipe (delegates to locate_scoreboard)."""
    try:
        from desktop.locate_scoreboard import format_side_by_side_diff
        return format_side_by_side_diff(diff, max_rows=max_rows)
    except Exception:
        # minimal fallback
        rows = []
        for d in format_diff_detail(diff, max_steps=max_rows, max_vars=max_rows):
            rows.append({
                'kind': d.get('kind') or 'info',
                'key': d.get('key') or d.get('name') or '',
                'current': _short_fallback(d.get('from')),
                'recipe': _short_fallback(d.get('to')),
                'text': d.get('text') or '',
            })
        return rows or [{'kind': 'info', 'key': '', 'current': '', 'recipe': '', 'text': '无差分'}]


def _short_fallback(v) -> str:
    if v is None:
        return '空'
    s = repr(v) if not isinstance(v, str) else v
    return s if len(s) <= 48 else s[:45] + '…'

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
