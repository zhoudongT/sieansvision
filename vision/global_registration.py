"""FPFH mutual matches, bounded RANSAC, ICP and explicit geometric acceptance."""
import numpy as np
from scipy.spatial import cKDTree
from cloud_engine import number


def integer(params, key, default, low, high):
    value = number(params, key, default, low, high)
    if not value.is_integer():
        raise ValueError(f'{key} 必须为整数')
    return int(value)


def rigid(value):
    matrix = np.asarray(value, dtype=float)
    return (matrix.shape == (4,4) and np.isfinite(matrix).all()
            and np.allclose(matrix[3], [0,0,0,1])
            and np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),atol=1e-5)
            and np.isclose(np.linalg.det(matrix[:3,:3]),1,atol=1e-5))


def prepare(points, voxel, o3d, label):
    unique = np.unique(points, axis=0)
    if len(unique) < 30:
        raise ValueError(label+'至少需要 30 个独立点')
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(unique))
    down = pc.voxel_down_sample(voxel)
    if not 30 <= len(down.points) <= 20000:
        raise ValueError(label+'体素采样后须为 30–20000 点，请调整体素边长')
    sampled = np.asarray(down.points)
    singular = np.linalg.svd(sampled-sampled.mean(axis=0),compute_uv=False)
    if singular[-1] <= singular[0]*1e-4:
        raise ValueError(label+'近似平面或共线，缺少可靠的三维全局特征')
    # Sparse isolated points have no meaningful surface normal/FPFH descriptor.
    distances,_ = cKDTree(sampled).query(sampled,k=6,distance_upper_bound=voxel*2.5)
    usable = np.flatnonzero(np.isfinite(distances[:,-1]))
    if len(usable) < 30:
        raise ValueError(label+'有效邻域不足，请增加体素边长或提供更密集的表面点云')
    down = down.select_by_index(usable.tolist())
    down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel*2.5,max_nn=30),fast_normal_computation=False)
    normals = np.asarray(down.normals)
    # Radial orientation is rigid-invariant for equally covered surfaces. Partial
    # views can still change it; no claim of a unique or guaranteed global pose.
    outward = np.asarray(down.points)-np.asarray(down.points).mean(axis=0)
    normals[np.einsum('ij,ij->i',normals,outward)<0] *= -1
    down.normals = o3d.utility.Vector3dVector(normals)
    feature = o3d.pipelines.registration.compute_fpfh_feature(down,o3d.geometry.KDTreeSearchParamHybrid(radius=voxel*5,max_nn=100))
    features = np.asarray(feature.data).T.copy()
    if not np.isfinite(features).all():
        raise ValueError(label+'局部特征包含无效数值')
    return pc,down,features


def register(points, target_points, params, o3d):
    voxel = number(params,'voxelSize',1,1e-6,1e6)
    distance = number(params,'maxDistance',5,1e-9,1e6)
    iterations = integer(params,'iterations',50,1,500)
    trials = integer(params,'ransacIterations',25000,100,100000)
    confidence = number(params,'ransacConfidence',.999,.9,.999999)
    minimum = number(params,'minFitness',.7,0,1)
    reverse_minimum = number(params,'minTargetFitness',.3,0,1)
    rms_limit = number(params,'maxRmsError',distance/2,1e-9,1e6)
    source,src,source_features = prepare(points,voxel,o3d,'输入点云')
    target,dst,target_features = prepare(target_points,voxel,o3d,'参考点云')
    nearest_target = cKDTree(target_features).query(source_features)[1]
    nearest_source = cKDTree(source_features).query(target_features)[1]
    indices = np.flatnonzero(nearest_source[nearest_target] == np.arange(len(source_features)))
    pairs = np.column_stack((indices,nearest_target[indices])).astype(np.int32)
    result = dict(method='global',found=False,passed=False,sourceFeaturePoints=len(src.points),targetFeaturePoints=len(dst.points),
                  featureMatches=len(pairs),sourceUniquePoints=len(source.points),targetUniquePoints=len(target.points),
                  minFitness=minimum,minTargetFitness=reverse_minimum,maxRmsError=rms_limit,
                  note='FPFH 双向特征匹配 → RANSAC → 点到点/稳健点到平面 ICP；质量门限不证明姿态唯一，对称件或相似局部结构可能歧义。')
    if len(pairs)<6:
        return {**result,'reason':'双向特征对应不足 6 对，未输出变换'},None
    reg = o3d.pipelines.registration
    o3d.utility.random.seed(42)
    coarse = reg.registration_ransac_based_on_correspondence(src,dst,o3d.utility.Vector2iVector(pairs),voxel*1.5,
        reg.TransformationEstimationPointToPoint(False),4,
        [reg.CorrespondenceCheckerBasedOnEdgeLength(.9),reg.CorrespondenceCheckerBasedOnDistance(voxel*1.5)],
        reg.RANSACConvergenceCriteria(trials,confidence))
    result.update(coarseFitness=coarse.fitness,coarseRmsError=coarse.inlier_rmse if coarse.fitness>0 else None)
    if coarse.fitness<=0 or not rigid(coarse.transformation):
        return {**result,'reason':'未找到有效粗配准，请检查重叠区域、尺度及表面特征'},None
    # Refine first on a broad downsampled neighborhood, then on original unique points.
    seed = reg.registration_icp(src,dst,max(distance,voxel*1.5),coarse.transformation,
        reg.TransformationEstimationPointToPoint(),reg.ICPConvergenceCriteria(max_iteration=iterations))
    fine = reg.registration_icp(source,target,distance,seed.transformation,
        reg.TransformationEstimationPointToPoint(),reg.ICPConvergenceCriteria(max_iteration=iterations))
    # Independent scans need not share point indices. Surface residuals reduce
    # nearest-point sampling bias; Huber limits the influence of partial edges.
    target.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel*2.5,max_nn=30),fast_normal_computation=False)
    fine = reg.registration_icp(source,target,distance,fine.transformation,
        reg.TransformationEstimationPointToPlane(reg.HuberLoss(distance/2)),
        reg.ICPConvergenceCriteria(max_iteration=iterations))
    if not rigid(fine.transformation):
        return {**result,'reason':'精配准未输出有效刚体变换'},None
    reverse = reg.evaluate_registration(target,source,distance,np.linalg.inv(fine.transformation))
    count = len(fine.correspondence_set)
    result.update(fitness=fine.fitness,targetFitness=reverse.fitness,matchedPoints=count,
                  rmsError=fine.inlier_rmse if count else None)
    failures=[]
    if count<30: failures.append('有效几何对应不足 30 点')
    if fine.fitness<minimum: failures.append('输入覆盖比例低于门限')
    if reverse.fitness<reverse_minimum: failures.append('参考覆盖比例低于门限')
    if count and fine.inlier_rmse>rms_limit: failures.append('对应点均方根误差超限')
    if failures:
        return {**result,'reason':'；'.join(failures)+'；保留原点云，未输出变换'},None
    result.update(found=True,passed=True,reason='匹配质量满足所设门限',transformation=fine.transformation.tolist())
    return result,fine.transformation
