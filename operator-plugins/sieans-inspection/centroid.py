"""Centroid of observed points, not the centre of mass of a closed solid."""
import math


def run(ctx):
    cloud = ctx['cloud']
    points = cloud['points']
    if not points:
        raise ValueError('点云为空')
    centroid = [math.fsum(p[axis] for p in points) / len(points) for axis in range(3)]
    target = [ctx['params'][key] for key in ('targetX', 'targetY', 'targetZ')]
    distance = math.dist(centroid, target)
    return dict(result=dict(centroid=centroid, distanceToTarget=distance, pointCount=len(points),
                            unit=cloud['unit'], passed=distance <= ctx['params']['tolerance']))
