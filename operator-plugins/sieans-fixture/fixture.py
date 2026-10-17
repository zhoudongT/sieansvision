"""Apply a validated 2D similarity pose to points or an image inspection fixture."""
import base64
import hashlib
import io
import math
import cv2
import numpy as np
from PIL import Image


def number(p,key,low,high,integer=False):
    v=p[key]
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high or integer and int(v)!=v:raise ValueError('定位跟随参数类型或范围无效：'+key)
    return int(v) if integer else float(v)


def read_pose(pose):
    if not isinstance(pose,dict) or pose.get('format')!='sieans-pose2d-v1':raise ValueError('需要模板定位输出的 2D 位姿')
    for key in ['sourceWidth','sourceHeight','templateWidth','templateHeight']:number(pose,key,1,32766,True)
    scale=number(pose,'scale',.1,5);angle=number(pose,'angleDeg',-180,180)
    for key in ['sourcePixelSha256','templatePixelSha256']:
        digest=pose.get(key)
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('2D 位姿缺少图像校验标识')
    matrix=pose.get('matrix');inverse=pose.get('inverse')
    for value in [matrix,inverse]:
        if not isinstance(value,list) or len(value)!=2 or any(not isinstance(row,list) or len(row)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e9 for v in row) for row in value):raise ValueError('2D 位姿变换矩阵无效')
    matrix=np.array(matrix,dtype=float);inverse=np.array(inverse,dtype=float);radians=math.radians(angle);expected=scale*np.array([[math.cos(radians),math.sin(radians)],[-math.sin(radians),math.cos(radians)]])
    if not np.allclose(matrix[:,:2],expected,rtol=1e-7,atol=1e-8):raise ValueError('2D 位姿旋转/比例与矩阵不一致，不支持透视、反射或非均匀缩放')
    full=np.vstack((matrix,[0,0,1]));back=np.vstack((inverse,[0,0,1]))
    if not np.allclose(full@back,np.eye(3),rtol=1e-7,atol=1e-7):raise ValueError('2D 位姿的正反向矩阵不一致')
    return matrix,inverse


def read_image(image_data,pose):
    if not isinstance(image_data,str) or not image_data:raise ValueError('图像校正需要当前原始图像')
    raw=base64.b64decode(image_data.split(',',1)[-1],validate=True)
    if len(raw)>12_000_000:raise ValueError('输入图像超过 12 MB')
    with Image.open(io.BytesIO(raw)) as header:
        if header.size!=(pose['sourceWidth'],pose['sourceHeight']) or header.width*header.height>16_000_000:raise ValueError('定位位姿与输入图像尺寸不一致或图像过大')
    image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[:2]!=(pose['sourceHeight'],pose['sourceWidth']) or hashlib.sha256(image.tobytes()).hexdigest()!=pose['sourcePixelSha256']:raise ValueError('定位位姿与当前图像不一致，请使用同一帧的定位结果')
    return image


def run(ctx):
    p=ctx['params'];pose=p['pose'];matrix,inverse=read_pose(pose)
    if p['task']=='points':
        if ctx.get('image'):read_image(ctx['image'],pose)
        rows=p['points']
        if not isinstance(rows,list) or not 1<=len(rows)<=1000:raise ValueError('跟随点表需要 1–1000 行')
        direction=p['direction']
        if direction not in ('template-to-image','image-to-template'):raise ValueError('坐标转换方向无效')
        transform=matrix if direction=='template-to-image' else inverse;w,h=(pose['sourceWidth'],pose['sourceHeight']) if direction=='template-to-image' else (pose['templateWidth'],pose['templateHeight']);items=[]
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or set(row)!={'x','y'}:raise ValueError('跟随点表只能包含 X、Y 两列')
            xy=np.array([number(row,'x',-1e6,1e6),number(row,'y',-1e6,1e6)])
            target=transform[:,:2]@xy+transform[:,2];inside=bool(0<=target[0]<=w-1 and 0<=target[1]<=h-1)
            items.append(dict(index=index+1,sourceX=float(xy[0]),sourceY=float(xy[1]),targetX=float(target[0]),targetY=float(target[1]),inside=inside))
        invalid=sum(not row['inside'] for row in items)
        return dict(result=dict(passed=invalid==0,direction=direction,count=len(items),outsideCount=invalid,items=items,diagnostic='点位转换完成' if not invalid else '部分转换点超出目标图像范围'))
    if p['task']!='rectify':raise ValueError('未知定位跟随功能')
    image=read_image(ctx.get('image'),pose)
    x=number(p,'cropX',-32766,32766,True);y=number(p,'cropY',-32766,32766,True);w=number(p,'cropWidth',0,2048,True) or pose['templateWidth'];h=number(p,'cropHeight',0,2048,True) or pose['templateHeight']
    if w>2048 or h>2048 or w*h>4_000_000:raise ValueError('校正图像单边不超过 2048 且面积不超过 400 万像素')
    local=matrix.copy();local[:,2]+=matrix[:,:2]@np.array([x,y])
    corners=np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1]],dtype=float);mapped=corners@local[:,:2].T+local[:,2]
    if np.any(mapped< -1e-7) or np.any(mapped[:,0]>image.shape[1]-1+1e-7) or np.any(mapped[:,1]>image.shape[0]-1+1e-7):raise ValueError('跟随检测区域超出原图；拒绝使用边界填充伪造检测像素')
    corrected=cv2.warpAffine(image,local,(w,h),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP)
    encoded=cv2.imencode('.png',corrected)[1]
    if len(encoded)>700000:raise ValueError('校正图像超过输出上限，请缩小检测区域')
    data='data:image/png;base64,'+base64.b64encode(encoded).decode()
    return dict(image=data,annotatedImage=data,result=dict(passed=True,rectified=True,width=w,height=h,templateOriginX=x,templateOriginY=y,sourcePolygon=mapped.tolist(),diagnostic='目标已校正到模板像素坐标；下游坐标原点为本检测区域左上角'))
