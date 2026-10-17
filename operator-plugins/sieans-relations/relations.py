"""Geometric relations in one common coordinate system; no image calibration implied."""
import math


def run(ctx):
    p = ctx['params']
    rows = p['entities']
    if len(rows) != 2:
        raise ValueError('必须输入两组几何要素')
    if any(not math.isfinite(v) for row in rows for v in row.values()):
        raise ValueError('坐标及方程系数必须为有限数')
    tol = p['parallelTolerance']
    lower, upper = p['minimumAngle'], p['maximumAngle']
    if not 0 <= lower <= upper <= 90:
        raise ValueError('夹角上下限必须满足 0 ≤ 下限 ≤ 上限 ≤ 90°')
    if not math.isfinite(tol) or not 0 <= tol <= 1:
        raise ValueError('平行判定阈值必须在 0–1 度内')
    items = []
    def item(name, value, unit):
        if not math.isfinite(value):
            raise ValueError('数值范围过大，无法稳定计算')
        items.append(dict(measurement=name, value=value, unit=unit))
    if p['geometry'] == 'lines-2d':
        directions = []
        for row in rows:
            dx, dy = row['x2']-row['x1'], row['y2']-row['y1']
            length = math.hypot(dx, dy)
            if not math.isfinite(length) or length <= 1e-12:
                raise ValueError('直线端点重合或坐标范围过大')
            directions.append((dx/length, dy/length))
        u, v = directions
        cross = u[0]*v[1]-u[1]*v[0]
        dot = u[0]*v[0]+u[1]*v[1]
        angle = math.degrees(math.atan2(abs(cross), abs(dot)))
        parallel = angle <= tol or abs(cross) <= 1e-14
        dx, dy = rows[1]['x1']-rows[0]['x1'], rows[1]['y1']-rows[0]['y1']
        if parallel:
            item('第二直线起点到第一直线距离', abs(dx*u[1]-dy*u[0]), '输入坐标单位')
        else:
            t = (dx*v[1]-dy*v[0])/cross
            item('交点 X', rows[0]['x1']+t*u[0], '输入坐标单位')
            item('交点 Y', rows[0]['y1']+t*u[1], '输入坐标单位')
    elif p['geometry'] == 'planes-3d':
        planes = []
        for row in rows:
            n = [row[k] for k in ('a', 'b', 'c')]
            length = math.hypot(*n)
            if not math.isfinite(length) or length <= 1e-12:
                raise ValueError('平面法向量为零或数值范围过大')
            planes.append(([v/length for v in n], row['d']/length))
        (u, a), (v, b) = planes
        dot = sum(x*y for x, y in zip(u, v))
        cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        angle = math.degrees(math.atan2(math.hypot(*cross), abs(dot)))
        parallel = angle <= tol or math.hypot(*cross) <= 1e-14
        if parallel:
            # Average distances of each plane's closest-to-origin point to the other.
            item('对称参考间距', (abs(b-a*dot)+abs(a-b*dot))/2, '输入坐标单位')
    else:
        raise ValueError('未知几何关系类型')
    item('无向锐夹角', angle, '°')
    return dict(result=dict(angleDegrees=angle, parallel=parallel, items=items,
                            passed=lower-1e-12 <= angle <= upper+1e-12))
