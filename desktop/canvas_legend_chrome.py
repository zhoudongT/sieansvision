"""On-canvas annotate/display legend chrome — VisionMaster-style compact key.

Soft leftover after wave148: density helpers exist (annotate_draw_density /
display_overlay_density) but no dedicated on-canvas legend. This module builds
OK/NG · overlay-kind · ROI cue entries for ImageView chrome.

Industrial-dark swatches only. No Comm/HMI cobind; no spark/blink cascade.
"""
from __future__ import annotations

from typing import Any

# Reuse annotate palette tones (keep import soft for unit/smoke without Qt).
try:
    from desktop.annotate_draw_density import PALETTE as _ANN_PALETTE
except Exception:  # pragma: no cover
    _ANN_PALETTE = {
        'ok': '#00d250',
        'ng': '#ff5252',
        'warn': '#ffb400',
        'info': '#42a5f5',
        'roi': '#e8a838',
        'caliper': '#c48a2a',
        'label': '#9ad',
        'crosshair': '#66cfff',
        'grid': '#3a4250',
    }

PALETTE = dict(_ANN_PALETTE)
PALETTE.setdefault('ok', '#00d250')
PALETTE.setdefault('ng', '#ff5252')
PALETTE.setdefault('roi', '#e8a838')
PALETTE.setdefault('measure', PALETTE.get('ok', '#00d250'))
PALETTE.setdefault('match', '#7c4dff')
PALETTE.setdefault('find', '#00bcd4')
PALETTE.setdefault('contour', '#26a69a')
PALETTE.setdefault('defect', '#ff5252')
PALETTE.setdefault('label', '#9ad')
PALETTE.setdefault('crosshair', '#66cfff')

# Canonical legend rows (key → label + palette key + overlay types that activate).
LEGEND_DEFS: tuple[dict[str, Any], ...] = (
    dict(key='ok', label='OK', color_key='ok', kinds=(), always=False, judge=True),
    dict(key='ng', label='NG', color_key='ng', kinds=(), always=False, judge=False),
    dict(key='roi', label='ROI', color_key='roi',
         kinds=('rect',), cue=True),
    dict(key='measure', label='测量', color_key='ok',
         kinds=('line',), cue=False),
    dict(key='find', label='查找', color_key='find',
         kinds=('circle', 'ellipse'), cue=False),
    dict(key='match', label='匹配', color_key='match',
         kinds=('polygon',), cue=False),
    dict(key='point', label='点/交点', color_key='crosshair',
         kinds=('point', 'cross'), cue=False),
    dict(key='label', label='标注', color_key='label',
         kinds=('label',), cue=False),
    dict(key='caliper', label='卡尺', color_key='caliper',
         kinds=(), cue=True),
)


def _color_for(key: str, color_key: str | None = None) -> str:
    ck = color_key or key
    return str(PALETTE.get(ck) or PALETTE.get(key) or '#9ad')


def default_legend_entries(*, include_judge: bool = True,
                           include_roi: bool = True) -> list[dict]:
    """Full static VisionMaster-style key (compact industrial)."""
    out = []
    for d in LEGEND_DEFS:
        if d.get('judge') is True and not include_judge:
            continue
        if d.get('judge') is False and not include_judge:
            continue
        if d.get('key') == 'roi' and not include_roi:
            continue
        out.append({
            'key': d['key'],
            'label': d['label'],
            'color': _color_for(d['key'], d.get('color_key')),
            'swatch': 'dot' if d['key'] in ('ok', 'ng', 'point') else (
                'dash' if d['key'] == 'roi' else 'line'),
            'active': True,
            'count': 0,
        })
    return out


def entries_from_overlay_specs(specs=None, *, judge_ok=None,
                               show_roi: bool = True,
                               always_judge: bool = True) -> list[dict]:
    """Bind legend rows to present overlay kinds (+ optional OK/NG).

    Empty specs → still show OK/NG (+ ROI cue) so chrome stays readable.
    """
    specs = [s for s in (specs or []) if isinstance(s, dict)]
    type_counts: dict[str, int] = {}
    color_hints: dict[str, str] = {}
    for s in specs:
        t = str(s.get('type') or '?').lower()
        type_counts[t] = type_counts.get(t, 0) + 1
        col = s.get('color')
        if col and t not in color_hints:
            color_hints[t] = str(col)
        # soft judge color → activate OK/NG
        if col and judge_ok is None:
            c = str(col).lower()
            if c in ('#00d250', '#2d9b6c', '#00c853'):
                pass
            elif c in ('#ff5252', '#f44336', '#e53935'):
                pass

    # kind → legend key
    kind_to_key = {}
    for d in LEGEND_DEFS:
        for k in d.get('kinds') or ():
            kind_to_key[k] = d['key']

    active_keys: set[str] = set()
    counts: dict[str, int] = {}
    for t, n in type_counts.items():
        key = kind_to_key.get(t)
        if key:
            active_keys.add(key)
            counts[key] = counts.get(key, 0) + n
        # heuristic: dashed amber rect → ROI even without explicit tag
        if t == 'rect':
            active_keys.add('roi')
            counts['roi'] = counts.get('roi', 0) + n

    if always_judge or judge_ok is not None:
        active_keys.add('ok')
        active_keys.add('ng')
    if show_roi and ('roi' in active_keys or not specs):
        active_keys.add('roi')

    # Prefer showing only active rows when specs present; else defaults.
    if not specs:
        return default_legend_entries(include_judge=True, include_roi=show_roi)

    out = []
    for d in LEGEND_DEFS:
        key = d['key']
        if key not in active_keys:
            continue
        if key == 'roi' and not show_roi:
            continue
        color = _color_for(key, d.get('color_key'))
        # Prefer first overlay color hint for matching kinds
        for t in d.get('kinds') or ():
            if t in color_hints:
                color = color_hints[t]
                break
        swatch = 'dot' if key in ('ok', 'ng', 'point') else (
            'dash' if key == 'roi' else 'line')
        if key == 'find':
            swatch = 'ring'
        elif key == 'match':
            swatch = 'box'
        entry = {
            'key': key,
            'label': d['label'],
            'color': color,
            'swatch': swatch,
            'active': True,
            'count': int(counts.get(key) or 0),
        }
        if key == 'ok' and judge_ok is False:
            entry['active'] = False
        if key == 'ng' and judge_ok is True:
            entry['active'] = False
        if key == 'ok' and judge_ok is True:
            entry['active'] = True
        if key == 'ng' and judge_ok is False:
            entry['active'] = True
        out.append(entry)
    return out


def legend_summary(entries=None) -> dict:
    entries = [e for e in (entries or []) if isinstance(e, dict)]
    keys = [str(e.get('key') or '') for e in entries]
    bits = []
    for e in entries:
        lab = str(e.get('label') or e.get('key') or '')
        n = int(e.get('count') or 0)
        bits.append(f'{lab}{n}' if n else lab)
    return {
        'total': len(entries),
        'keys': keys,
        'summary': '图例·' + ('+'.join(bits) if bits else '空'),
        'palette': {e.get('key'): e.get('color') for e in entries},
    }


def legend_toggle_state(visible: bool) -> dict:
    """Tiny bind helper for smoke / menu one-liner."""
    return {
        'visible': bool(visible),
        'label': '图例·开' if visible else '图例·关',
        'action': 'hide' if visible else 'show',
    }


def html_legend_block(entries=None, *, title: str = '图例') -> str:
    """Compact HTML for QLabel legend chrome (industrial dark)."""
    entries = [e for e in (entries or []) if isinstance(e, dict)]
    rows = []
    for e in entries:
        color = str(e.get('color') or '#9ad')
        label = str(e.get('label') or e.get('key') or '')
        n = int(e.get('count') or 0)
        active = e.get('active', True) is not False
        opacity = '1' if active else '0.35'
        sw = str(e.get('swatch') or 'line')
        if sw == 'dot':
            mark = f'<span style="color:{color};font-size:11px;">●</span>'
        elif sw == 'dash':
            mark = f'<span style="color:{color};font-size:11px;">┄</span>'
        elif sw == 'ring':
            mark = f'<span style="color:{color};font-size:11px;">○</span>'
        elif sw == 'box':
            mark = f'<span style="color:{color};font-size:11px;">□</span>'
        else:
            mark = f'<span style="color:{color};font-size:11px;">─</span>'
        suffix = f'<span style="color:#787878;font-size:10px;"> {n}</span>' if n else ''
        rows.append(
            f'<div style="opacity:{opacity};line-height:1.35;">'
            f'{mark}&nbsp;<span style="color:#e8e8e8;font-size:11px;">{label}</span>'
            f'{suffix}</div>'
        )
    body = ''.join(rows) or '<div style="color:#787878;font-size:11px;">空</div>'
    return (
        f'<div style="font-family:\'Microsoft YaHei\',\'PingFang SC\',sans-serif;">'
        f'<div style="color:#a8a8a8;font-size:10px;letter-spacing:0.6px;'
        f'margin-bottom:2px;">{title}</div>{body}</div>'
    )
