"""Shared annotate / ROI draw density — polish pens, crosshair, tolerance chips.

Used across SimpleRoiEditor, CaliperRoiEditor, image_view overlays, and panel
soft demos. Soft OpenCV/Qt path only. No Comm/HMI cobind; no spark micro-props.
"""
from __future__ import annotations

from typing import Any


# Industrial palette (Qt / canvas hex)
PALETTE = {
    'ok': '#00d250',
    'ng': '#ff5252',
    'warn': '#ffb400',
    'info': '#42a5f5',
    'axis_x': '#00d250',
    'axis_y': '#00bcd4',
    'roi': '#e8a838',
    'roi_fill': '#e8a83833',
    'caliper': '#c48a2a',
    'caliper_tip': '#e8a838',
    'label': '#9ad',
    'crosshair': '#66cfff',
    'tolerance_ok': '#00d250',
    'tolerance_ng': '#ff5252',
    'grid': '#3a4250',
}


def pen_style(kind: str = 'roi', *, width: float | None = None,
              judge_ok=None) -> dict:
    """Return a draw-pen descriptor {color, width, style} for shared editors."""
    kind = str(kind or 'roi').lower()
    if judge_ok is True:
        color = PALETTE['ok']
    elif judge_ok is False:
        color = PALETTE['ng']
    else:
        color = PALETTE.get(kind, PALETTE['roi'])
    defaults = {
        'roi': 2.0,
        'caliper': 1.2,
        'caliper_tip': 1.4,
        'measure': 2.0,
        'label': 1.0,
        'crosshair': 1.0,
        'tolerance': 1.2,
        'grid': 1.0,
        'ok': 2.0,
        'ng': 2.0,
        'warn': 1.6,
        'info': 1.4,
    }
    w = float(width) if width is not None else float(defaults.get(kind, 1.5))
    style = 'dash' if kind in ('crosshair', 'tolerance', 'grid') else 'solid'
    return {'color': color, 'width': w, 'style': style, 'kind': kind}


def crosshair_specs(cx, cy, *, size: float = 24, color: str | None = None,
                    span: float | None = None) -> list:
    """Full or local crosshair overlay specs for annotate density."""
    try:
        cx = float(cx); cy = float(cy)
    except (TypeError, ValueError):
        return []
    col = color or PALETTE['crosshair']
    specs = []
    if span and float(span) > 0:
        s = float(span)
        specs.append(dict(type='line', x1=cx - s, y1=cy, x2=cx + s, y2=cy,
                          color=col, width=1.0))
        specs.append(dict(type='line', x1=cx, y1=cy - s, x2=cx, y2=cy + s,
                          color=col, width=1.0))
    else:
        specs.append(dict(type='cross', x=cx, y=cy, size=float(size),
                          color=col, width=1.0))
    specs.append(dict(type='point', x=cx, y=cy, r=2.5, color=col))
    return specs


def roi_rect_specs(roi, *, color: str | None = None, label: str = 'ROI',
                   show_label: bool = True, show_crosshair: bool = True,
                   show_handles: bool = False) -> list:
    """Shared ROI rectangle (+ optional center crosshair / corner ticks)."""
    if not isinstance(roi, (list, tuple)) or len(roi) < 4:
        if isinstance(roi, dict):
            try:
                roi = [roi['x'], roi['y'], roi.get('w') or roi.get('width'),
                       roi.get('h') or roi.get('height')]
            except Exception:
                return []
        else:
            return []
    try:
        x, y, w, h = float(roi[0]), float(roi[1]), float(roi[2]), float(roi[3])
    except (TypeError, ValueError):
        return []
    col = color or PALETTE['roi']
    specs = [dict(type='rect', x=x, y=y, w=w, h=h, color=col, width=2.0)]
    if show_crosshair and w > 0 and h > 0:
        specs.extend(crosshair_specs(x + w / 2, y + h / 2, size=min(16, w, h) / 2,
                                     color=PALETTE['crosshair']))
    if show_label:
        specs.append(dict(type='label', x=x + 4, y=max(0, y - 14),
                          text=f'{label} [{int(x)},{int(y)},{int(w)},{int(h)}]',
                          color=col))
    if show_handles:
        hs = 5.0
        for hx, hy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
            specs.append(dict(type='rect', x=hx - hs / 2, y=hy - hs / 2,
                              w=hs, h=hs, color=col, width=1.2))
    return specs


def tolerance_chip_specs(x, y, jmin, jmax, value=None, *, in_band=None) -> list:
    """Small tolerance-band chip near a metric label."""
    try:
        x = float(x); y = float(y)
    except (TypeError, ValueError):
        return []
    if in_band is True:
        col = PALETTE['tolerance_ok']
    elif in_band is False:
        col = PALETTE['tolerance_ng']
    else:
        col = PALETTE['warn']
    txt = f'T[{jmin},{jmax}]'
    if value is not None:
        try:
            txt += f' v={float(value):.3g}'
        except (TypeError, ValueError):
            pass
    return [dict(type='label', x=x, y=y, text=txt, color=col)]


def measure_segment_specs(x1, y1, x2, y2, *, judge_ok=None, label: str = '',
                          show_ends: bool = True) -> list:
    pen = pen_style('measure', judge_ok=judge_ok)
    specs = [dict(type='line', x1=x1, y1=y1, x2=x2, y2=y2,
                  color=pen['color'], width=pen['width'])]
    if show_ends:
        specs.append(dict(type='point', x=x1, y=y1, color=pen['color']))
        specs.append(dict(type='point', x=x2, y=y2, color=pen['color']))
    if label:
        mx = (float(x1) + float(x2)) / 2
        my = (float(y1) + float(y2)) / 2
        specs.append(dict(type='label', x=mx, y=my, text=label, color=pen['color']))
    return specs


def caliper_probe_specs(cx, cy, half_w, half_l, angle_deg: float = 0.0,
                        *, search_dir: str = 'both') -> list:
    """Oriented caliper box + tip line (shared with CaliperRoiEditor preview)."""
    import math
    try:
        cx, cy = float(cx), float(cy)
        hw, hl = float(half_w), float(half_l)
    except (TypeError, ValueError):
        return []
    rad = math.radians(float(angle_deg) or 0.0)
    c, s = math.cos(rad), math.sin(rad)
    # local corners of oriented rect: ±hl along proj, ±hw along search
    corners = []
    for sx, sy in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)):
        px = cx + sx * c - sy * s
        py = cy + sx * s + sy * c
        corners.append([px, py])
    specs = [dict(type='polygon', points=corners, color=PALETTE['caliper'], width=1.2)]
    # tip / search axis
    tip_len = hw if search_dir in ('both', 'pos', 'neg', '') else hw
    ax = -s * tip_len
    ay = c * tip_len
    specs.append(dict(
        type='line', x1=cx - ax, y1=cy - ay, x2=cx + ax, y2=cy + ay,
        color=PALETTE['caliper_tip'], width=1.4,
    ))
    specs.append(dict(type='point', x=cx, y=cy, r=2, color=PALETTE['caliper_tip']))
    return specs


def densify_overlay_list(specs=None, *, max_specs: int = 240,
                         prefer_types: tuple | None = None) -> list:
    """Cap + stable order for shared annotate density merges."""
    specs = [s for s in (specs or []) if isinstance(s, dict)]
    if prefer_types:
        rank = {t: i for i, t in enumerate(prefer_types)}
        specs = sorted(specs, key=lambda s: rank.get(str(s.get('type')), 99))
    return specs[: max(1, int(max_specs))]


def annotate_density_summary(specs=None) -> dict:
    specs = [s for s in (specs or []) if isinstance(s, dict)]
    counts: dict[str, int] = {}
    for s in specs:
        t = str(s.get('type') or '?')
        counts[t] = counts.get(t, 0) + 1
    return {
        'total': len(specs),
        'byType': counts,
        'summary': '标注·' + ('+'.join(f'{k}{v}' for k, v in counts.items()) or '空'),
        'palette': dict(PALETTE),
    }


def shared_editor_defaults() -> dict:
    """Defaults shared by SimpleRoiEditor / CaliperRoiEditor polish."""
    return {
        'showCrosshair': True,
        'showRoiLabel': True,
        'showHandles': True,
        'nudgeStep': 1,
        'aspectLock': False,
        'pen': pen_style('roi'),
        'crosshairPen': pen_style('crosshair'),
        'caliperPen': pen_style('caliper'),
    }
