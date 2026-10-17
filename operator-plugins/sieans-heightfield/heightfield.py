"""Independent datum plane and bounded visible-surface grid integration (2.5D)."""
import math
import numpy as np


def number(p,key,low,high,integer=False):
    value=p[key]
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high or integer and int(value)!=value:raise ValueError('参数类型或范围无效：'+key)
    return int(value) if integer else float(value)


def vector(value,label):
    if not isinstance(value,list) or len(value)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e9 for v in value):raise ValueError(label+'必须是三个有限数值')
    return np.array(value,dtype=float)


def identity(value):
    if value.get('unit') not in ('mm','m') or not isinstance(value.get('frame'),str) or len(value['frame'])>120:raise ValueError('模型必须声明 mm/m 单位及坐标系名称')


def plane_read(value):
    if not isinstance(value,dict) or value.get('format')!='sieans-plane-grid-v1':raise ValueError('需要高度网格基准标定输出的平面模型')
    identity(value);origin=vector(value.get('origin'),'平面原点');u=vector(value.get('axisU'),'U 轴');v=vector(value.get('axisV'),'V 轴');normal=vector(value.get('normal'),'法向');basis=np.column_stack((u,v,normal))
    if not np.allclose(basis.T@basis,np.eye(3),atol=1e-8,rtol=1e-8) or not np.isclose(np.linalg.det(basis),1,atol=1e-8):raise ValueError('平面坐标轴必须为右手正交单位基')
    return origin,basis


def fit(p):
    identity(p);rows=p['points']
    if not isinstance(rows,list) or not 3<=len(rows)<=1000:raise ValueError('独立基准点表需 3–1000 行')
    points=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'x','y','z'}:raise ValueError('基准点表只能包含 X、Y、Z 三列')
        points.append([number(row,k,-1e9,1e9) for k in ('x','y','z')])
    points=np.array(points);unique=np.unique(points,axis=0)
    if len(unique)<3:raise ValueError('独立基准点不足三个不同坐标')
    maximum_rms=number(p,'maximumRms',1e-12,1e6);maximum_error=number(p,'maximumError',1e-12,1e6)
    if maximum_error<maximum_rms:raise ValueError('最大单点误差门限不能小于 RMS 门限')
    hint=vector(p['normalHint'],'正法向提示');direction=vector(p['axisHint'],'U 轴方向提示')
    if np.linalg.norm(hint)<1e-12 or np.linalg.norm(direction)<1e-12:raise ValueError('法向和 U 轴提示不能为零')
    origin=unique.mean(axis=0);_,singular,axes=np.linalg.svd(unique-origin,full_matrices=False)
    if singular[1]<=max(singular[0]*1e-8,1e-12):raise ValueError('基准点共线、重合或分布退化，不能确定平面')
    normal=axes[-1];cosine=float(normal@hint/np.linalg.norm(hint))
    if abs(cosine)<.05:raise ValueError('正法向提示几乎位于基准面内，无法可靠确定高度正方向')
    if cosine<0:normal=-normal
    u=direction-normal*float(direction@normal)
    if np.linalg.norm(u)<1e-8*np.linalg.norm(direction):raise ValueError('U 轴提示接近平面法向，无法确定网格方向')
    u/=np.linalg.norm(u);v=np.cross(normal,u);distances=(points-origin)@normal;errors=(unique-origin)@normal
    rms=float(np.sqrt(np.mean(errors**2)));maximum=float(np.max(np.abs(errors)));passed=rms<=maximum_rms and maximum<=maximum_error
    items=[dict(index=i+1,x=float(row[0]),y=float(row[1]),z=float(row[2]),distance=float(distance)) for i,(row,distance) in enumerate(zip(points,distances))]
    result=dict(found=passed,passed=passed,pointCount=len(points),uniquePointCount=len(unique),rmsError=rms,maximumError=maximum,unit=p['unit'],items=items,diagnostic='独立基准平面标定通过' if passed else '基准点不满足平面拟合误差门限')
    if passed:result['plane']=dict(format='sieans-plane-grid-v1',unit=p['unit'],frame=p['frame'],origin=origin.tolist(),axisU=u.tolist(),axisV=v.tolist(),normal=normal.tolist())
    return dict(result=result)


def run(ctx):
    p=ctx['params']
    if p['task']=='fit':return fit(p)
    if p['task']!='integrate':raise ValueError('未知高度网格功能')
    model=p['plane'];origin,basis=plane_read(model);cloud=ctx['cloud']
    if not isinstance(cloud,dict) or cloud.get('unit')!=model['unit'] or cloud.get('frame','')!=model['frame']:raise ValueError('测量点云与基准平面的单位或坐标系不一致')
    raw=cloud.get('points')
    if not isinstance(raw,list) or not 1<=len(raw)<=200000:raise ValueError('点云需要 1–200000 点')
    if any(not isinstance(row,list) or len(row)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>1e9 for x in row) for row in raw):raise ValueError('点云坐标必须为有限 N×3 数值')
    points=np.array(raw,dtype=float);unique=np.unique(points,axis=0)
    u0=number(p,'uMinimum',-1e9,1e9);v0=number(p,'vMinimum',-1e9,1e9);cell=number(p,'cellSize',1e-9,1e6);nu=number(p,'cellsU',1,512,True);nv=number(p,'cellsV',1,512,True);total=nu*nv
    if total>65536:raise ValueError('网格总量超过 65536 格')
    minimum_samples=number(p,'minimumSamples',1,10000,True);maximum_spread=number(p,'maximumCellSpread',0,1e9);minimum_coverage=number(p,'minimumCoverage',0,1)
    lower=number(p,'minimumHeight',-1e9,1e9);upper=number(p,'maximumHeight',-1e9,1e9);low_volume=number(p,'minimumPositiveVolume',0,1e30);high_volume=number(p,'maximumPositiveVolume',0,1e30)
    if lower>upper or low_volume>high_volume:raise ValueError('高度或正向体积公差上下限颠倒')
    statistic=p['cellStatistic'];detail=p['detailMode'];limit=number(p,'detailLimit',1,1000,True)
    if statistic not in ('maximum','mean') or detail not in ('all','invalid'):raise ValueError('网格代表值或明细模式无效')
    if not isinstance(p['colorize'],bool):raise ValueError('着色开关类型无效')
    if p['colorize'] and len(points)>10000:raise ValueError('着色输出最多 10000 点，请先下采样或关闭着色')
    coordinate_epsilon=64*np.finfo(float).eps*max(1.,float(np.max(np.abs(points))),float(np.max(np.abs(origin))))
    if cell<coordinate_epsilon*16:raise ValueError('网格边长小于当前坐标的可靠数值精度，请改用局部坐标或增大网格')
    def project(source):
        local=(source-origin)@basis;xy=(local[:,:2]-[u0,v0])/cell
        nearest=np.rint(xy);xy=np.where(np.abs(xy-nearest)<1e-8,nearest,xy)
        inside=(xy[:,0]>=0)&(xy[:,0]<nu)&(xy[:,1]>=0)&(xy[:,1]<nv)
        ids=np.full(len(source),-1,dtype=np.int64);ids[inside]=np.floor(xy[inside,1]).astype(np.int64)*nu+np.floor(xy[inside,0]).astype(np.int64)
        return local,inside,ids
    local,inside,ids=project(unique);selected=ids[inside];height=local[inside,2]
    counts=np.bincount(selected,minlength=total);sums=np.bincount(selected,weights=height,minlength=total);high=np.full(total,-np.inf);low=np.full(total,np.inf)
    np.maximum.at(high,selected,height);np.minimum.at(low,selected,height);occupied=counts>0
    spreads=np.zeros(total);spreads[occupied]=high[occupied]-low[occupied]
    epsilon=coordinate_epsilon
    valid=(counts>=minimum_samples)&(spreads<=maximum_spread+epsilon)
    representative=np.zeros(total);representative[occupied]=high[occupied] if statistic=='maximum' else sums[occupied]/counts[occupied]
    good=valid&(representative>=lower-epsilon)&(representative<=upper+epsilon);invalid=~valid;outside=valid&~good
    valid_count=int(valid.sum());coverage=valid_count/total
    result=dict(found=valid_count>0,passed=False,unit=model['unit'],areaUnit=model['unit']+'²',volumeUnit=model['unit']+'³',pointCount=len(points),uniquePointCount=len(unique),roiPointCount=int(inside.sum()),outsideRoiPointCount=int((~inside).sum()),totalCells=total,occupiedCells=int(occupied.sum()),validCells=valid_count,missingCells=int((~occupied).sum()),insufficientCells=int((occupied&(counts<minimum_samples)).sum()),spreadRejectedCells=int((occupied&(spreads>maximum_spread+epsilon)).sum()),outsideHeightCells=int(outside.sum()),coverage=coverage,roiArea=total*cell**2,observedArea=valid_count*cell**2,cellStatistic=statistic,items=[])
    if valid_count:
        values=representative[valid];positive=float(np.maximum(values,0).sum()*cell**2);negative=float(np.maximum(-values,0).sum()*cell**2)
        result.update(minimumHeight=float(values.min()),maximumHeight=float(values.max()),meanHeight=float(values.mean()),positiveVolume=positive,negativeVolume=negative,netVolume=positive-negative)
        volume_epsilon=epsilon*result['observedArea']
        result['passed']=bool(coverage>=minimum_coverage and not outside.any() and low_volume-volume_epsilon<=positive<=high_volume+volume_epsilon)
    indices=np.arange(total) if detail=='all' else np.flatnonzero(invalid|outside)
    for index in indices[:limit]:
        row=dict(column=int(index%nu),row=int(index//nu),u=float(u0+(index%nu+.5)*cell),v=float(v0+(index//nu+.5)*cell),sampleCount=int(counts[index]),valid=bool(valid[index]),passed=bool(good[index]))
        row['reason']='缺少采样' if not occupied[index] else '独立采样数量不足' if counts[index]<minimum_samples else '同格高度跨度超限' if invalid[index] else '高度超差' if outside[index] else ''
        if occupied[index]:row['heightSpread']=float(spreads[index])
        if valid[index]:row.update(height=float(representative[index]),signedVolume=float(representative[index]*cell**2))
        result['items'].append(row)
    result['detailsTruncated']=len(indices)>limit
    result['diagnostic']='可见高度表面网格测量通过' if result['passed'] else '没有有效网格，不输出高度或体积' if not valid_count else '覆盖率、高度或正向观测体积不满足要求；缺失/无效格未补齐'
    output=dict(result=result)
    if p['colorize']:
        _,mask,point_ids=project(points);colors=np.tile([.5,.5,.5],(len(points),1));selected_ids=point_ids[mask];colors[mask]=np.where(invalid[selected_ids,None],[[1.,.6,.1]],np.where(outside[selected_ids,None],[[1.,.15,.1]],[[.1,.75,.4]]))
        output['cloud']=dict(cloud,colors=colors.tolist())
    return output
