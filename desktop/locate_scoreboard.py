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
    """Pull match scores from an engine last_result bag (items[].score / bestScore).

    Soft-engine friendly: also reads matches[], templateScores{}, output.score,
    and per-item templateId. No Halcon / real camera required.
    """
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
        data = rec.get('data') or rec.get('result') or rec.get('output') or rec
        if not isinstance(data, dict):
            continue
        # explicit per-template map from soft engine
        tmap = data.get('templateScores') or data.get('scoresById') or data.get('batchScores')
        if isinstance(tmap, dict):
            for tk, tv in tmap.items():
                sc = normalize_score(tv)
                if sc is not None:
                    out[str(tk)] = sc
        items = data.get('items') or data.get('matches') or []
        if not isinstance(items, list):
            items = []
        best = normalize_score(
            data.get('bestScore') or data.get('score') or data.get('matchScore')
            or rec.get('score')
        )
        tpl_id = str(
            (data.get('activeTemplateId') or data.get('templateId')
             or data.get('bestTemplateId')
             or (rec.get('params') or {}).get('activeTemplateId') or '')
        )
        for it in items:
            if not isinstance(it, dict):
                continue
            sc = normalize_score(it.get('score') or it.get('matchScore'))
            tid = str(it.get('templateId') or it.get('id') or it.get('name') or '')
            if sc is not None:
                if tid:
                    prev = out.get(tid)
                    out[tid] = sc if prev is None else max(float(prev), sc)
                best = sc if best is None else max(best, sc)
                if not tpl_id and tid:
                    tpl_id = tid
        if best is not None:
            if tpl_id:
                prev = out.get(tpl_id)
                out[tpl_id] = best if prev is None else max(float(prev), best)
            out['__best__'] = best
            if rid:
                out[f'step:{rid}'] = best
            op = str(rec.get('operation') or data.get('operation') or '')
            if op in ('locate', 'match', 'template_match') or rid:
                out['__step_best__'] = best
                if rid:
                    out[f'__step:{rid}__'] = {'score': best, 'templateId': tpl_id}
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


def scores_for_library(ingest: dict | None, template_library: list | None) -> dict:
    """Map ingest bag onto template ids/names/paths; drop meta keys."""
    ingest = ingest if isinstance(ingest, dict) else {}
    out = {}
    meta = {'__best__', '__step_best__'}
    for k, v in ingest.items():
        if k in meta or str(k).startswith('step:') or str(k).startswith('__step:'):
            continue
        if isinstance(v, dict):
            continue
        sc = normalize_score(v)
        if sc is not None:
            out[str(k)] = sc
    # If only __best__ / step best, stamp onto active / sole template
    best = normalize_score(ingest.get('__best__') or ingest.get('__step_best__'))
    lib = [e for e in (template_library or []) if isinstance(e, dict)]
    if best is not None and lib:
        # prefer already-known tpl id; else fill missing only
        known = any(str(e.get('id') or '') in out for e in lib)
        if not known:
            # stamp best onto first / only so scoreboard is non-empty from live engine
            eid = str(lib[0].get('id') or 't0')
            out.setdefault(eid, best)
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

    def sparkline(self, *, width: int = 16, relative: bool = True) -> str:
        """Industrial block sparkline; relative scales to window min/max."""
        vals = self.values()
        if not vals:
            return ''
        window = vals[-max(4, int(width or 16)):]
        if relative and len(window) >= 2:
            lo, hi = min(window), max(window)
            span = hi - lo
            if span < 1e-9:
                normed = [0.5] * len(window)
            else:
                normed = [(v - lo) / span for v in window]
        else:
            normed = [max(0.0, min(1.0, float(v))) for v in window]
        return ''.join(_spark_char(v) for v in normed)

    def delta(self) -> float | None:
        vals = self.values()
        if len(vals) < 2:
            return None
        return float(vals[-1] - vals[-2])

    def ok_rate(self) -> float | None:
        pts = [p for p in self._points if p.get('ok') is not None]
        if not pts:
            return None
        return sum(1 for p in pts if p.get('ok')) / len(pts)

    def summary(self, *, industrial: bool = True) -> str:
        vals = self.values()
        if not vals:
            return '趋势：暂无分数'
        n = len(vals)
        avg = sum(vals) / n
        lo, hi = min(vals), max(vals)
        last = vals[-1]
        spark = self.sparkline(width=16, relative=True)
        dlt = self.delta()
        if dlt is None:
            arrow = '·'
            dtxt = ''
        elif dlt > 1e-6:
            arrow = '↑'
            dtxt = f' Δ+{dlt:.3f}'
        elif dlt < -1e-6:
            arrow = '↓'
            dtxt = f' Δ{dlt:.3f}'
        else:
            arrow = '→'
            dtxt = ' Δ0'
        ok_r = self.ok_rate()
        ok_txt = f' OK{ok_r*100:.0f}%' if ok_r is not None else ''
        # last point OK glyph
        last_ok = self._points[-1].get('ok') if self._points else None
        mark = ''
        if last_ok is True:
            mark = '✓'
        elif last_ok is False:
            mark = '✗'
        if industrial:
            return (
                f'趋势 n={n} 末={last:.3f}{mark}{dtxt} 均={avg:.3f} '
                f'[{lo:.2f},{hi:.2f}]{ok_txt} {arrow}{spark}'
            )
        return f'趋势 n={n} 末={last:.3f} 均={avg:.3f} [{lo:.2f},{hi:.2f}] {spark}'

    def summary_rich(self) -> str:
        """HTML-ish tip text for industrial tooltip (plain-safe)."""
        base = self.summary(industrial=True)
        pts = self.points()[-8:]
        if not pts:
            return base
        lines = [base, '— 近点 —']
        for p in pts:
            ok = p.get('ok')
            mark = '✓' if ok is True else ('✗' if ok is False else '·')
            lines.append(
                f"{mark} {p.get('label') or '—'}  {float(p['score']):.3f}"
                + (f"  tpl={p.get('templateId')}" if p.get('templateId') else '')
            )
        return '\n'.join(lines)


    def point_at(self, index: int) -> dict:
        """Point by absolute index into the ring buffer (soft)."""
        pts = self._points
        try:
            i = int(index)
        except (TypeError, ValueError):
            return {}
        if i < 0:
            i = len(pts) + i
        if 0 <= i < len(pts):
            return dict(pts[i])
        return {}

    def hover_tip_at(self, index: int) -> str:
        """Industrial hover tip for one spark bar / frame point."""
        pt = self.point_at(index)
        if not pt:
            return ''
        ok = pt.get('ok')
        mark = '✓' if ok is True else ('✗' if ok is False else '·')
        frame = str(pt.get('frame') or '')
        label = str(pt.get('label') or '')
        tpl = str(pt.get('templateId') or '')
        abs_i = index if index >= 0 else len(self._points) + index
        parts = [f'#{abs_i + 1} {mark} {float(pt.get("score") or 0):.3f}']
        if label:
            parts.append(label)
        if frame:
            parts.append(f'frame={frame}')
        if tpl:
            parts.append(f'tpl={tpl}')
        parts.append('点击跳到该帧')
        return ' · '.join(parts)

    def index_at_fraction(self, frac: float, *, bar_count: int | None = None) -> int:
        """Map [0,1] x-fraction across visible spark window → absolute point index."""
        pts = self._points
        if not pts:
            return -1
        n_vis = min(len(pts), max(4, int(bar_count or 16)))
        window_start = len(pts) - n_vis
        f = max(0.0, min(0.999999, float(frac or 0.0)))
        local = int(f * n_vis)
        return window_start + local

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



def seek_filmstrip_from_spark_jump(filmstrip, bag=None, *, flash=True) -> dict:
    """Wire spark click-jump bag → filmstrip seek (+ optional thumb flash). Soft.

    bag keys: frame, label, index. Uses FilmstripBar.seek_frame_token when
    available, else select_path / select_index.
    Returns {ok, index, path, matchedBy, frame, label, sparkIndex, flash?}.
    """
    bag = bag if isinstance(bag, dict) else {}
    frame = str(bag.get('frame') or '')
    label = str(bag.get('label') or '')
    spark_index = bag.get('index')
    out = {
        'ok': False, 'index': -1, 'path': '', 'matchedBy': '',
        'frame': frame, 'label': label, 'sparkIndex': spark_index,
    }
    if filmstrip is None:
        out['reason'] = 'no filmstrip'
        return out

    def _maybe_flash(hit):
        if not flash or not hit.get('ok'):
            return hit
        # seek_frame_token already flashes when flash=True; still fill if missing
        if hit.get('flash'):
            return hit
        if hasattr(filmstrip, 'flash_seek_thumb'):
            try:
                hit['flash'] = filmstrip.flash_seek_thumb(
                    hit.get('index'), path=str(hit.get('path') or ''),
                )
            except Exception as err:
                hit['flash'] = {'ok': False, 'reason': str(err)}
        return hit

    # Prefer dedicated seek_frame_token
    if hasattr(filmstrip, 'seek_frame_token'):
        # try frame token first, then label, then spark index as filmstrip index
        for token, how_pref in ((frame, 'frame'), (label, 'label')):
            if not token:
                continue
            hit = filmstrip.seek_frame_token(token, emit=True, flash=flash)
            if hit.get('ok'):
                out.update(hit)
                out['frame'] = frame
                out['label'] = label
                out['sparkIndex'] = spark_index
                out['matchedBy'] = hit.get('matchedBy') or how_pref
                return _maybe_flash(out)
        if spark_index is not None:
            hit = filmstrip.seek_frame_token('', index=spark_index, emit=True, flash=flash)
            if hit.get('ok'):
                out.update(hit)
                out['frame'] = frame
                out['label'] = label
                out['sparkIndex'] = spark_index
                out['matchedBy'] = hit.get('matchedBy') or 'sparkIndex'
                return _maybe_flash(out)
        out['reason'] = 'not found'
        return out
    # Fallback select_path / select_index
    for token in (frame, label):
        if token and hasattr(filmstrip, 'select_path') and filmstrip.select_path(token, emit=True):
            idx = int(getattr(filmstrip, 'current_index', lambda: -1)())
            paths = list(getattr(filmstrip, 'paths', lambda: [])())
            out.update(ok=True, index=idx, path=(paths[idx] if 0 <= idx < len(paths) else token),
                       matchedBy='path')
            return _maybe_flash(out)
    if spark_index is not None and hasattr(filmstrip, 'select_index'):
        try:
            i = int(spark_index)
        except (TypeError, ValueError):
            i = -1
        if filmstrip.select_index(i, emit=True):
            paths = list(getattr(filmstrip, 'paths', lambda: [])())
            out.update(ok=True, index=i, path=(paths[i] if 0 <= i < len(paths) else ''),
                       matchedBy='sparkIndex')
            return _maybe_flash(out)
    out['reason'] = 'not found'
    return out


def sync_compare_strip_from_spark_jump(compare_strip, bag=None) -> dict:
    """Spark jump → activate matching path on CompareThumbStrip (soft sync).

    Does not add paths; only activates if already on the strip.
    Returns {ok, index, path, matchedBy, frame, label}.
    """
    bag = bag if isinstance(bag, dict) else {}
    frame = str(bag.get('frame') or '')
    label = str(bag.get('label') or '')
    path = str(bag.get('path') or frame or '')
    out = {
        'ok': False, 'index': -1, 'path': '', 'matchedBy': '',
        'frame': frame, 'label': label,
    }
    if compare_strip is None:
        out['reason'] = 'no compare strip'
        return out
    for token in (path, frame, label):
        if not token:
            continue
        if hasattr(compare_strip, 'activate_path'):
            hit = compare_strip.activate_path(token, emit=False)
            if hit.get('ok'):
                out.update(hit)
                out['frame'] = frame
                out['label'] = label
                return out
        # fallback: scan paths()
        try:
            paths = list(compare_strip.paths() if callable(getattr(compare_strip, 'paths', None)) else [])
        except Exception:
            paths = []
        from pathlib import Path as _P
        base = _P(token).name
        for i, pth in enumerate(paths):
            if pth == token or _P(pth).name == base:
                out.update(ok=True, index=i, path=pth, matchedBy='scan')
                try:
                    lst = getattr(compare_strip, '_list', None)
                    if lst is not None:
                        lst.setCurrentRow(i)
                except Exception:
                    pass
                return out
    out['reason'] = 'not on strip'
    return out


def sync_spark_from_compare_path(spark_widget, path='', *, trend=None) -> dict:
    """Compare-strip path → highlight/jump matching spark bar (soft reverse sync).

    Matches by frame path / basename / label. Returns {ok, local, index, frame, label}.
    """
    token = str(path or '').strip()
    out = {'ok': False, 'local': -1, 'index': -1, 'frame': '', 'label': '', 'path': token}
    if not token or spark_widget is None:
        out['reason'] = 'no spark/path'
        return out
    from pathlib import Path as _P
    base = _P(token).name
    stem = _P(token).stem
    pts = []
    try:
        pts = list(getattr(spark_widget, '_points', None) or [])
    except Exception:
        pts = []
    if not pts and trend is not None and hasattr(trend, 'points'):
        try:
            pts = list(trend.points())
        except Exception:
            pts = []
    win_start = int(getattr(spark_widget, '_window_start', 0) or 0)
    hit_local = -1
    hit_pt = None
    for i, pt in enumerate(pts):
        if not isinstance(pt, dict):
            continue
        fr = str(pt.get('frame') or '')
        lab = str(pt.get('label') or '')
        if fr == token or _P(fr).name == base or _P(fr).name == token:
            hit_local, hit_pt = i, pt
            break
        if lab and (lab == token or lab == base or lab == stem or base in lab):
            hit_local, hit_pt = i, pt
            break
    if hit_local < 0:
        out['reason'] = 'no spark point'
        return out
    abs_i = win_start + hit_local
    out.update(
        ok=True, local=hit_local, index=abs_i,
        frame=str((hit_pt or {}).get('frame') or ''),
        label=str((hit_pt or {}).get('label') or ''),
    )
    # visual select: set hover + optional jump without re-emitting seek loop
    try:
        spark_widget._hover_local = hit_local
        spark_widget._sync_select_local = hit_local
        spark_widget._last_jump = {
            'index': abs_i, 'local': hit_local,
            'frame': out['frame'], 'label': out['label'],
            'score': float((hit_pt or {}).get('score') or 0),
            'ok': (hit_pt or {}).get('ok'),
            'templateId': str((hit_pt or {}).get('templateId') or ''),
            'fromCompare': True,
        }
        if hasattr(spark_widget, 'update'):
            spark_widget.update()
    except Exception as err:
        out['paintErr'] = str(err)
    return out


def _spark_char(v: float) -> str:
    # 8-level block sparkline (v expected in [0,1])
    chars = '▁▂▃▄▅▆▇█'
    i = int(max(0.0, min(0.999, float(v))) * len(chars))
    return chars[i]




def spark_bar_heights(values, *, width: int = 16, relative: bool = True) -> list:
    """Normalize scores to [0,1] bar heights (same relative logic as unicode sparkline)."""
    vals = [float(v) for v in (values or []) if v is not None]
    if not vals:
        return []
    window = vals[-max(4, int(width or 16)):]
    if relative and len(window) >= 2:
        lo, hi = min(window), max(window)
        span = hi - lo
        if span < 1e-9:
            return [0.5] * len(window)
        return [(v - lo) / span for v in window]
    return [max(0.0, min(1.0, float(v))) for v in window]


class MatchScoreSparkWidget:
    """Painted mini bar-spark for MatchScoreTrend (vs unicode ▁▂▃ blocks).

    Constructed lazily as a real QWidget when Qt is available; otherwise acts as
    a headless holder exposing set_from_trend / heights for smokes.
    """

    @staticmethod
    def create(parent=None, *, width: int = 120, height: int = 28):
        try:
            from PySide6.QtWidgets import QWidget
            from PySide6.QtGui import QPainter, QColor, QPen, QBrush
            from PySide6.QtCore import Qt, QRect, Signal
        except Exception:
            return _HeadlessSpark(width=width, height=height)

        class _Painted(QWidget):
            frameJumpRequested = Signal(dict)  # {index,frame,label,score,ok,templateId}

            def __init__(self, parent=None):
                super().__init__(parent)
                self.setObjectName('matchScoreSparkWidget')
                self.setFixedHeight(int(height))
                self.setMinimumWidth(int(width))
                self.setToolTip('匹配分趋势 · 悬停看点 · 点击跳帧 · 无硬件')
                self.setMouseTracking(True)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self._heights: list[float] = []
                self._oks: list = []
                self._points: list = []
                self._window_start = 0
                self._bar_count = 16
                self._unicode = ''
                self._summary = ''
                self._hover_local = -1
                self._sync_select_local = -1
                self._last_jump = {}
                self._on_jump = None

            def set_jump_handler(self, fn):
                self._on_jump = fn

            def set_from_trend(self, trend, *, bar_count: int = 16) -> dict:
                vals = []
                oks = []
                pts = []
                self._bar_count = max(4, int(bar_count or 16))
                if trend is not None and hasattr(trend, 'points'):
                    pts = list(trend.points())
                    vals = [p.get('score') for p in pts]
                    oks = [p.get('ok') for p in pts]
                elif trend is not None and hasattr(trend, 'values'):
                    vals = list(trend.values())
                self._heights = spark_bar_heights(vals, width=self._bar_count, relative=True)
                n = len(self._heights)
                self._oks = list(oks[-n:]) if oks else []
                self._points = list(pts[-n:]) if pts else []
                self._window_start = max(0, len(pts) - n) if pts else 0
                try:
                    self._unicode = trend.sparkline(width=self._bar_count, relative=True) if trend else ''
                except Exception:
                    self._unicode = ''
                try:
                    self._summary = trend.summary(industrial=True) if trend else ''
                except Exception:
                    self._summary = ''
                tip = (self._summary or '匹配分趋势') + '\n悬停柱看帧分 · 点击跳到该帧 · unicode=' + (self._unicode or '—')
                self.setToolTip(tip)
                self.update()
                return {
                    'n': len(self._heights),
                    'unicode': self._unicode,
                    'heights': list(self._heights),
                    'painted': True,
                    'windowStart': self._window_start,
                }

            def heights(self) -> list:
                return list(self._heights)

            def unicode_spark(self) -> str:
                return self._unicode

            def last_jump(self) -> dict:
                return dict(self._last_jump or {})

            def hover_index(self) -> int:
                return int(self._hover_local)

            def _local_index_at(self, x: float) -> int:
                hs = self._heights
                if not hs:
                    return -1
                n = len(hs)
                pad = 3
                gap = 1
                avail_w = max(1, self.width() - pad * 2)
                bar_w = max(1, (avail_w - gap * (n - 1)) // n)
                if x < pad:
                    return 0
                rel = x - pad
                stride = bar_w + gap
                i = int(rel // stride) if stride else 0
                return max(0, min(n - 1, i))

            def point_at_local(self, local: int) -> dict:
                if 0 <= local < len(self._points):
                    pt = dict(self._points[local])
                    pt['index'] = self._window_start + local
                    return pt
                if 0 <= local < len(self._heights):
                    return {
                        'score': self._heights[local],
                        'ok': self._oks[local] if local < len(self._oks) else None,
                        'label': f'#{self._window_start + local + 1}',
                        'frame': '',
                        'templateId': '',
                        'index': self._window_start + local,
                    }
                return {}

            def hover_tip_for_local(self, local: int) -> str:
                pt = self.point_at_local(local)
                if not pt:
                    return self._summary or ''
                ok = pt.get('ok')
                mark = '✓' if ok is True else ('✗' if ok is False else '·')
                abs_i = int(pt.get('index') if pt.get('index') is not None else local)
                parts = [f'#{abs_i + 1} {mark} {float(pt.get("score") or 0):.3f}']
                if pt.get('label'):
                    parts.append(str(pt['label']))
                if pt.get('frame'):
                    parts.append(f"frame={pt['frame']}")
                if pt.get('templateId'):
                    parts.append(f"tpl={pt['templateId']}")
                parts.append('点击跳到该帧')
                return ' · '.join(parts)

            def jump_to_local(self, local: int) -> dict:
                pt = self.point_at_local(local)
                if not pt:
                    return {}
                bag = {
                    'index': int(pt.get('index') if pt.get('index') is not None else local),
                    'local': local,
                    'frame': str(pt.get('frame') or ''),
                    'label': str(pt.get('label') or ''),
                    'score': float(pt.get('score') or 0),
                    'ok': pt.get('ok'),
                    'templateId': str(pt.get('templateId') or ''),
                }
                self._last_jump = bag
                try:
                    self.frameJumpRequested.emit(bag)
                except Exception:
                    pass
                if callable(self._on_jump):
                    try:
                        self._on_jump(bag)
                    except Exception:
                        pass
                return bag

            def mouseMoveEvent(self, event):  # noqa: N802
                try:
                    x = float(event.position().x()) if hasattr(event, 'position') else float(event.x())
                except Exception:
                    x = 0.0
                local = self._local_index_at(x)
                self._hover_local = local
                tip = self.hover_tip_for_local(local) if local >= 0 else (self._summary or '')
                if tip:
                    self.setToolTip(tip)
                self.update()
                super().mouseMoveEvent(event)

            def leaveEvent(self, event):  # noqa: N802
                self._hover_local = -1
                tip = self._summary or '匹配分趋势'
                if self._unicode:
                    tip += '\nunicode=' + self._unicode
                self.setToolTip(tip)
                self.update()
                super().leaveEvent(event)

            def mousePressEvent(self, event):  # noqa: N802
                try:
                    if event.button() == Qt.MouseButton.LeftButton:
                        x = float(event.position().x()) if hasattr(event, 'position') else float(event.x())
                        local = self._local_index_at(x)
                        if local >= 0:
                            self.jump_to_local(local)
                except Exception:
                    pass
                super().mousePressEvent(event)

            def paintEvent(self, event):  # noqa: N802
                painter = QPainter(self)
                try:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    painter.fillRect(self.rect(), QColor('#12161c'))
                    painter.setPen(QPen(QColor('#2a3a4a')))
                    painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
                    hs = self._heights
                    if not hs:
                        painter.setPen(QColor('#556'))
                        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '—')
                        return
                    n = len(hs)
                    pad = 3
                    gap = 1
                    avail_w = max(1, self.width() - pad * 2)
                    avail_h = max(1, self.height() - pad * 2)
                    bar_w = max(1, (avail_w - gap * (n - 1)) // n)
                    for i, h in enumerate(hs):
                        bh = max(1, int(round(float(h) * avail_h)))
                        x = pad + i * (bar_w + gap)
                        y = pad + (avail_h - bh)
                        ok = self._oks[i] if i < len(self._oks) else None
                        if ok is True:
                            color = QColor('#3d9a5f')
                        elif ok is False:
                            color = QColor('#b85a4a')
                        else:
                            color = QColor('#4a8ab8')
                        sel = int(getattr(self, '_sync_select_local', -1))
                        if i == self._hover_local or i == sel:
                            color = color.lighter(130)
                            painter.fillRect(QRect(x - 1, pad, bar_w + 2, avail_h), QBrush(QColor('#1a2430')))
                            if i == sel and i != self._hover_local:
                                painter.setPen(QPen(QColor('#ffd24a')))
                                painter.drawRect(x - 1, pad, bar_w + 1, avail_h - 1)
                        painter.fillRect(QRect(x, y, bar_w, bh), QBrush(color))
                finally:
                    painter.end()

        return _Painted(parent)

    # allow MatchScoreSparkWidget() alias → create()
    def __new__(cls, parent=None, *, width: int = 120, height: int = 28):
        return cls.create(parent, width=width, height=height)


class _HeadlessSpark:
    def __init__(self, *, width=120, height=28):
        self._heights = []
        self._unicode = ''
        self._points = []
        self._window_start = 0
        self._last_jump = {}
        self._hover_local = -1
        self._on_jump = None
        self._w = width
        self._h = height

    def set_jump_handler(self, fn):
        self._on_jump = fn

    def set_from_trend(self, trend, *, bar_count: int = 16) -> dict:
        pts = list(trend.points()) if trend is not None and hasattr(trend, 'points') else []
        vals = [p.get('score') for p in pts] if pts else (
            list(trend.values()) if trend is not None and hasattr(trend, 'values') else []
        )
        self._heights = spark_bar_heights(vals, width=bar_count, relative=True)
        n = len(self._heights)
        self._points = list(pts[-n:]) if pts else []
        self._window_start = max(0, len(pts) - n) if pts else 0
        try:
            self._unicode = trend.sparkline(width=bar_count, relative=True) if trend else ''
        except Exception:
            self._unicode = ''
        return {
            'n': len(self._heights), 'unicode': self._unicode,
            'heights': list(self._heights), 'painted': False,
            'windowStart': self._window_start,
        }

    def heights(self):
        return list(self._heights)

    def unicode_spark(self):
        return self._unicode

    def hover_tip_for_local(self, local: int) -> str:
        if 0 <= local < len(self._points):
            pt = self._points[local]
            ok = pt.get('ok')
            mark = '✓' if ok is True else ('✗' if ok is False else '·')
            return f"#{self._window_start + local + 1} {mark} {float(pt.get('score') or 0):.3f} · 点击跳到该帧"
        return ''

    def jump_to_local(self, local: int) -> dict:
        if local < 0 or local >= max(len(self._points), len(self._heights)):
            return {}
        pt = dict(self._points[local]) if local < len(self._points) else {
            'score': self._heights[local] if local < len(self._heights) else 0,
        }
        bag = {
            'index': self._window_start + local,
            'local': local,
            'frame': str(pt.get('frame') or ''),
            'label': str(pt.get('label') or ''),
            'score': float(pt.get('score') or 0),
            'ok': pt.get('ok'),
            'templateId': str(pt.get('templateId') or ''),
        }
        self._last_jump = bag
        if callable(self._on_jump):
            try:
                self._on_jump(bag)
            except Exception:
                pass
        return bag

    def last_jump(self):
        return dict(self._last_jump or {})


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
