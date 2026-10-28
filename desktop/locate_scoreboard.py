# -*- coding: utf-8 -*-
"""Locate multi-template batch scoreboard + match-score trend (no Halcon / no robot).

Industrial UX: score every template in the library against a score map (or soft
heuristic), threshold OK/NG, select best. Trend strip keeps recent run scores.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable


def normalize_score(v) -> float | None:
    try:
        if v is None or v == '':
            return None
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


def build_batch_scoreboard(
    template_library: list | None,
    scores_by_id: dict | None = None,
    *,
    threshold: float = 0.85,
    active_id: str = '',
) -> dict:
    """Build industrial multi-template scoreboard rows.

    Returns {
      rows:[{id,name,path,score,ok,rank,active,note}],
      bestId, bestScore, passCount, failCount, threshold, summary,
    }
    """
    lib = [e for e in (template_library or []) if isinstance(e, dict)]
    scores = scores_by_id if isinstance(scores_by_id, dict) else {}
    thr = float(threshold if threshold is not None else 0.85)
    thr = max(0.0, min(1.0, thr))
    rows = []
    for i, entry in enumerate(lib):
        eid = str(entry.get('id') or f't{i}')
        name = str(entry.get('name') or eid)
        path = str(entry.get('path') or '')
        # accept id / name / path keys
        raw = scores.get(eid)
        if raw is None:
            raw = scores.get(name)
        if raw is None and path:
            raw = scores.get(path)
        score = normalize_score(raw)
        ok = bool(score is not None and score >= thr)
        rows.append({
            'id': eid,
            'name': name,
            'path': path,
            'score': score,
            'ok': ok if score is not None else False,
            'pending': score is None,
            'rank': 0,
            'active': bool(active_id) and eid == str(active_id),
            'note': str(entry.get('note') or ''),
        })
    # rank by score desc (pending last)
    ranked = sorted(
        rows,
        key=lambda r: (
            0 if r['score'] is None else 1,
            r['score'] if r['score'] is not None else -1.0,
        ),
        reverse=True,
    )
    for i, r in enumerate(ranked):
        r['rank'] = i + 1 if r['score'] is not None else 0
    # restore library order in rows but keep ranks
    rank_map = {r['id']: r['rank'] for r in ranked}
    for r in rows:
        r['rank'] = rank_map.get(r['id'], 0)
    best = next((r for r in ranked if r['score'] is not None), None)
    pass_n = sum(1 for r in rows if r['ok'])
    fail_n = sum(1 for r in rows if r['score'] is not None and not r['ok'])
    pend_n = sum(1 for r in rows if r['pending'])
    bits = [f'{len(rows)}模板', f'阈值{thr:.2f}', f'OK{pass_n}', f'NG{fail_n}']
    if pend_n:
        bits.append(f'待评{pend_n}')
    if best:
        bits.append(f'最优「{best["name"]}」={best["score"]:.3f}')
    else:
        bits.append('无有效分')
    return {
        'rows': rows,
        'ranked': ranked,
        'bestId': best['id'] if best else '',
        'bestScore': best['score'] if best else None,
        'bestName': best['name'] if best else '',
        'passCount': pass_n,
        'failCount': fail_n,
        'pendingCount': pend_n,
        'threshold': thr,
        'summary': ' · '.join(bits),
    }


def select_best_template(board: dict | None) -> dict | None:
    """Return best scoring row dict, or None."""
    if not isinstance(board, dict):
        return None
    ranked = board.get('ranked') or board.get('rows') or []
    for r in ranked:
        if isinstance(r, dict) and r.get('score') is not None:
            return r
    return None


def soft_estimate_scores(template_library: list | None, seed: str = '') -> dict:
    """Deterministic soft scores for UI/smoke when no image match is available.

    Not a real matcher — open-and-use placeholder so the scoreboard fills.
    Prefer ingesting real engine scores via ingest_engine_scores().
    """
    import hashlib
    out = {}
    seed_b = (seed or 'sieans').encode('utf-8', errors='ignore')
    for i, entry in enumerate(template_library or []):
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get('id') or f't{i}')
        path = str(entry.get('path') or '')
        h = hashlib.sha1(seed_b + eid.encode() + path.encode()).hexdigest()
        # map to 0.55–0.98 band so threshold demos look industrial
        n = int(h[:4], 16) / 65535.0
        out[eid] = round(0.55 + 0.43 * n, 4)
    return out


def ingest_engine_scores(last_result=None, step_id: str = '') -> dict:
    """Pull match scores from an engine last_result bag (items[].score / bestScore)."""
    out = {}
    if not isinstance(last_result, dict):
        return out
    records = last_result.get('results') or last_result.get('modules') or []
    if isinstance(records, dict):
        records = list(records.values())
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        rid = str(rec.get('id') or '')
        if step_id and rid and rid != step_id:
            continue
        data = rec.get('data') or rec.get('result') or rec
        if not isinstance(data, dict):
            continue
        items = data.get('items') or []
        best = normalize_score(data.get('bestScore') or data.get('score'))
        tpl_id = str(
            (data.get('activeTemplateId') or data.get('templateId')
             or (rec.get('params') or {}).get('activeTemplateId') or '')
        )
        if items and isinstance(items[0], dict):
            sc = normalize_score(items[0].get('score'))
            if sc is not None:
                best = sc if best is None else max(best, sc)
        if best is not None:
            if tpl_id:
                out[tpl_id] = best
            out['__best__'] = best
            # also stash under step
            if rid:
                out[f'step:{rid}'] = best
    # flow vars
    vars_bag = (last_result.get('variables') or {})
    flow = vars_bag.get('flow') if isinstance(vars_bag, dict) else {}
    if isinstance(flow, dict):
        for k, v in flow.items():
            kl = str(k).lower()
            if 'score' in kl or kl.endswith('_score'):
                sc = normalize_score(v)
                if sc is not None:
                    out[str(k)] = sc
    return out


class MatchScoreTrend:
    """Ring buffer of recent match scores (runs/frames) — no hardware."""

    def __init__(self, capacity: int = 32):
        self.capacity = max(4, int(capacity or 32))
        self._points: list[dict] = []

    def clear(self):
        self._points.clear()

    def push(self, score, *, label: str = '', ok: bool | None = None,
             template_id: str = '', frame: str = '') -> dict:
        sc = normalize_score(score)
        if sc is None:
            return {}
        pt = {
            'score': sc,
            'label': str(label or f'#{len(self._points)+1}'),
            'ok': bool(ok) if ok is not None else None,
            'templateId': str(template_id or ''),
            'frame': str(frame or ''),
        }
        self._points.append(pt)
        if len(self._points) > self.capacity:
            self._points = self._points[-self.capacity:]
        return pt

    def points(self) -> list:
        return list(self._points)

    def values(self) -> list:
        return [p['score'] for p in self._points]

    def summary(self) -> str:
        vals = self.values()
        if not vals:
            return '趋势：暂无分数'
        n = len(vals)
        avg = sum(vals) / n
        lo, hi = min(vals), max(vals)
        last = vals[-1]
        spark = ''.join(_spark_char(v) for v in vals[-16:])
        return f'趋势 n={n} 末={last:.3f} 均={avg:.3f} [{lo:.2f},{hi:.2f}] {spark}'

    def to_dict(self) -> dict:
        return {'capacity': self.capacity, 'points': deepcopy(self._points)}

    def load_dict(self, data: dict | None):
        self._points = []
        if not isinstance(data, dict):
            return
        for p in (data.get('points') or [])[-self.capacity:]:
            if isinstance(p, dict) and p.get('score') is not None:
                self._points.append({
                    'score': float(p['score']),
                    'label': str(p.get('label') or ''),
                    'ok': p.get('ok'),
                    'templateId': str(p.get('templateId') or ''),
                    'frame': str(p.get('frame') or ''),
                })


def _spark_char(v: float) -> str:
    # 8-level block sparkline
    chars = '▁▂▃▄▅▆▇█'
    i = int(max(0.0, min(0.999, float(v))) * len(chars))
    return chars[i]


def format_side_by_side_diff(diff: dict | None, *, max_rows: int = 60) -> list:
    """Flatten recipe diff into side-by-side rows: {kind,key,current,recipe,text}."""
    rows = []
    if not isinstance(diff, dict):
        return [{'kind': 'info', 'key': '', 'current': '', 'recipe': '', 'text': '无差分'}]
    for d in (diff.get('stepDeltas') or []):
        name = d.get('name') or d.get('op') or d.get('id') or '?'
        op = d.get('op') or ''
        frm = d.get('from') if isinstance(d.get('from'), dict) else {}
        to = d.get('to') if isinstance(d.get('to'), dict) else {}
        keys = d.get('changedKeys') or []
        if keys and keys[0] == '(无匹配模块)':
            rows.append({
                'kind': 'missing',
                'key': f'{name}/{op}',
                'current': '（无匹配模块）',
                'recipe': str(d.get('sample') or '缺失'),
                'text': f'[缺] {name} ({op})',
            })
            continue
        for k in keys:
            if k == 'imageFrom':
                rows.append({
                    'kind': 'step',
                    'key': f'{name}.imageFrom',
                    'current': '…',
                    'recipe': '…',
                    'text': f'[模块] {name}.imageFrom',
                })
                continue
            cv = frm.get(k)
            rv = to.get(k)
            rows.append({
                'kind': 'step',
                'key': f'{name}.{k}',
                'current': _short(cv),
                'recipe': _short(rv),
                'text': f'[模块] {name}.{k}: {_short(cv)} → {_short(rv)}',
            })
            if len(rows) >= max_rows:
                return rows
    for vd in (diff.get('varDeltas') or []):
        rows.append({
            'kind': 'var',
            'key': f"{vd.get('scope')}.{vd.get('key')}",
            'current': _short(vd.get('from')),
            'recipe': _short(vd.get('to')),
            'text': (
                f"[变量] {vd.get('scope')}.{vd.get('key')}: "
                f"{_short(vd.get('from'))} → {_short(vd.get('to'))}"
            ),
        })
        if len(rows) >= max_rows:
            break
    if not rows:
        rows.append({
            'kind': 'info', 'key': '', 'current': '—', 'recipe': '—',
            'text': '与当前工程无参数/变量差异',
        })
    return rows


def _short(v) -> str:
    if v is None:
        return '空'
    s = repr(v) if not isinstance(v, str) else v
    return s if len(s) <= 48 else s[:45] + '…'
