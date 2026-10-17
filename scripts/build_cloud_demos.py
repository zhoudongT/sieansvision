"""Deterministic geometry fixtures; no hardware samples or customer data."""
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/vision/samples'


def box(x0,y0,z0,w,d,h):
    return sorted(set((x0+x,y0+y,z0+z) for x in range(w+1) for y in range(d+1) for z in range(h+1)
                      if x in (0,w) or y in (0,d) or z in (0,h)))


def save(name,points):
    cloud = {'unit':'mm','frame':'fixture','points':np.asarray(points).tolist()}
    (OUT/(name+'.json')).write_text(json.dumps(cloud),encoding='utf-8')
    # Native vector projection used solely as a gallery thumbnail.
    p=np.asarray(points,float); p-=p.mean(axis=0)
    q=np.column_stack((p[:,0]*.85-p[:,1]*.5, -p[:,2]-.3*p[:,1]-.2*p[:,0]))
    span=max(np.ptp(q[:,0]),np.ptp(q[:,1])*1.7,1); q=q/span*280+[160,95]
    dots=''.join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.1" fill="hsl({202-140*(z-p[:,2].min())/(np.ptp(p[:,2]) or 1):.1f},70%,42%)"/>' for (x,y),z in zip(q,p[:,2]))
    (OUT/(name+'.svg')).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 190"><rect width="320" height="190" fill="#edf4f9"/>{dots}<text x="12" y="20" fill="#547189" font-family="sans-serif" font-size="11">3D / mm</text></svg>',encoding='utf-8')
    return cloud


box_cloud=save('cloud-box',box(0,0,0,20,10,5))
scene=[[x,y,0] for x in range(-30,31) for y in range(-20,21)]
scene+=box(-23,-8,0,12,10,8)+box(8,-3,0,16,12,14)
save('cloud-scene',scene)
save('cloud-height',[[x+.5,y+.5,5] for x in range(20) for y in range(10)])
points=np.random.default_rng(15).uniform(-10,10,(200,3))
save('cloud-registration',points)
angle=.03; rotation=np.array([[math.cos(angle),-math.sin(angle),0],[math.sin(angle),math.cos(angle),0],[0,0,1]])
target={'points':(points@rotation.T+[.12,-.15,.08]).tolist(),'unit':'mm','frame':'reference'}
depth={'depth':[[1000]*20 for _ in range(10)],'unit':'mm','frame':'depth-camera','depthScale':1,'intrinsics':{'fx':100,'fy':100,'cx':9.5,'cy':4.5}}
(OUT/'cloud-depth.json').write_text(json.dumps(depth),encoding='utf-8')

def step(operation,**params):return {'operation':operation,'params':params}
def demo(id,name,source,steps,description,expected,preview=None):
    return {'id':id,'name':name,'category':'3D','cloud':source+'.json','image':(preview or source)+'.svg','steps':steps,'description':description,'expected':expected}
demos=[
 demo('cloud-box','3D 标准件尺寸','cloud-box',[step('cloud_measure')],'测量合成箱体的三轴包围盒尺寸。','X=20、Y=10、Z=5 mm；包围盒体积 1000 mm³。'),
 demo('cloud-clusters','去除平面 → 3D 目标聚类','cloud-scene',[step('cloud_plane',distanceThreshold=.02,iterations=500,output='outliers'),step('cloud_cluster',eps=1.8,minPoints=5)],'分离背景平面，再用空间密度将两个箱体分组。','聚类数量 2，两个目标着不同颜色。'),
 demo('cloud-volume','高度表面与网格体积','cloud-height',[step('cloud_height',baselineZ=0,cellSize=1)],'每个 1 mm 网格一个表面样点，验证相对基准高度及网格积分。','高度 5 mm；200 个单元，估计体积 1000 mm³。'),
 demo('cloud-icp','点云局部配准 ICP','cloud-registration',[step('cloud_register',targetCloud=target,maxDistance=2,iterations=100)],'恢复已知小角度旋转及平移。测试点云不代表实际工件。','fitness=1；平移 (0.12, -0.15, 0.08) mm，残差接近 0。'),
 demo('cloud-depth','深度图 → 点云测量','cloud-depth',[step('cloud_measure')],'使用针孔内参将原始深度数组投影成 3D 坐标。','200 点，Z=1000 mm，X 尺寸 190 mm、Y 尺寸 90 mm。','cloud-height'),
]
(OUT/'demos-3d.json').write_text(json.dumps(demos,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Generated {len(demos)} 3D demos')
