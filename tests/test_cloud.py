import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vision'))
from engine import run
from cloud_engine import validate


def cloud(points, unit='mm'):
    return {'points': np.asarray(points).tolist(), 'unit': unit, 'frame': 'test'}


def invoke(operation, points, **params):
    return run({'operation': 'cloud_'+operation, 'cloud': cloud(points), 'params': params})


class CloudTests(unittest.TestCase):
    def test_dimensions_are_axis_aligned_and_not_object_volume(self):
        points = [[x,y,z] for x in (0,20) for y in (0,10) for z in (0,5)]
        result = invoke('measure', points)['result']
        self.assertEqual([result[k] for k in ('sizeX','sizeY','sizeZ')], [20,10,5])
        self.assertEqual(result['boundingBoxVolume'],1000)
        self.assertNotIn('volume', result)

    def test_crop_preserves_color_and_does_not_mutate_input(self):
        source = {**cloud([[0,0,0],[1,2,3],[9,9,9]]), 'colors': [[1,0,0],[0,1,0],[0,0,1]]}
        result = run({'operation':'cloud_filter','cloud':source,'params':{'method':'crop','minimum':[.5,1,2],'maximum':[2,3,4]}})
        self.assertEqual(result['cloud']['points'], [[1,2,3]])
        self.assertEqual(result['cloud']['colors'], [[0,1,0]])
        self.assertEqual(len(source['points']),3)

    def test_voxel_centroid(self):
        result = invoke('filter', [[0,0,0],[.1,.1,.1],[10,10,10]], method='voxel',voxelSize=1)
        points = sorted(result['cloud']['points'])
        np.testing.assert_allclose(points, [[.05,.05,.05],[10,10,10]])

    def test_outlier_filters_remove_isolated_point(self):
        points = [[x/10,y/10,0] for x in range(10) for y in range(10)]+[[100,100,100]]
        stat = invoke('filter', points, method='statistical',neighbors=10,stdRatio=2)
        self.assertEqual(stat['result']['pointCount'],100)
        radius = invoke('filter', points, method='radius',minPoints=3,radius=.3)
        self.assertEqual(radius['result']['pointCount'],100)

    def test_plane_model_and_outlier_extraction(self):
        points = [[x,y,2*x+3*y+4] for x in range(10) for y in range(10)]+[[0,0,100]]
        result = invoke('plane', points, distanceThreshold=.001,output='outliers')
        self.assertEqual(result['result']['inlierCount'],100)
        self.assertLess(result['result']['rmsError'],1e-8)
        plane = np.asarray(result['result']['plane'])
        self.assertLess(np.max(np.abs(np.c_[points[:-1],np.ones(100)]@plane)),1e-8)
        self.assertEqual(result['cloud']['points'],[[0,0,100]])

    def test_dbscan_two_clusters_and_noise(self):
        points = [[x/10,y/10,0] for x in range(5) for y in range(5)]
        points += [[10+x/10,y/10,0] for x in range(5) for y in range(5)]+[[100,100,100]]
        result = invoke('cluster', points,eps=.3,minPoints=4)
        self.assertEqual(result['result']['count'],2)
        self.assertEqual(result['result']['noiseCount'],1)
        self.assertEqual([item['pointCount'] for item in result['result']['items']],[25,25])
        self.assertEqual(len(result['cloud']['colors']),51)

    def test_surface_volume_does_not_count_duplicate_points_or_fill_holes(self):
        points = [[x+.5,y+.5,5] for x in range(20) for y in range(10)]
        result = invoke('height', points+points, baselineZ=0,cellSize=1)['result']
        self.assertEqual(result['occupiedCells'],200)
        self.assertEqual(result['estimatedVolume'],1000)
        self.assertEqual(invoke('height',points[:-1],cellSize=1)['result']['estimatedVolume'],995)
        self.assertEqual(invoke('height',points,baselineZ=10,cellSize=1)['result']['estimatedVolume'],0)

    def test_icp_recovers_small_known_rigid_transform(self):
        points = np.random.default_rng(15).uniform(-10,10,(200,3))
        angle = .03
        rotation = np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
        translation = np.array([.12,-.15,.08])
        target = points@rotation.T+translation
        result = invoke('register', points,targetCloud=cloud(target),maxDistance=2,iterations=100)
        transform = np.asarray(result['result']['transformation'])
        np.testing.assert_allclose(transform[:3,:3],rotation,atol=1e-6)
        np.testing.assert_allclose(transform[:3,3],translation,atol=1e-6)
        self.assertLess(result['result']['rmsError'],1e-6)
        self.assertEqual(result['result']['fitness'],1)

    def test_import_ascii_and_binary_ply_pcd(self):
        points = np.array([[0,0,0],[1,2,3],[5,8,13]],float)
        with tempfile.TemporaryDirectory() as directory:
            pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
            pc.normals = o3d.utility.Vector3dVector([[0,0,1]]*3)
            pc.colors = o3d.utility.Vector3dVector([[1,0,0],[0,1,0],[0,0,1]])
            for extension in ('ply','pcd','xyz','xyzn','xyzrgb','pts'):
                for ascii_mode in (True,False):
                    name = 'input.'+extension
                    path = Path(directory)/name
                    o3d.io.write_point_cloud(str(path),pc,write_ascii=ascii_mode,compressed=extension=='pcd' and not ascii_mode)
                    result = run({'operation':'cloud_import','name':name,'content':base64.b64encode(path.read_bytes()).decode(),'unit':'mm'})
                    np.testing.assert_allclose(result['cloud']['points'],points)

    def test_depth_pinhole_projection_and_units(self):
        data = {'depth':[[1000,0],[2000,1000]],'intrinsics':{'fx':2,'fy':2,'cx':0,'cy':0},'depthScale':1000,'unit':'m'}
        result = run({'operation':'cloud_import','name':'depth.json','content':base64.b64encode(json.dumps(data).encode()).decode()})
        np.testing.assert_allclose(result['cloud']['points'],[[0,0,1],[0,1,2],[.5,.5,1]])
        self.assertEqual(result['cloud']['unit'],'m')

    def test_invalid_and_degenerate_data_is_rejected(self):
        for points in ([],[[1,2]],[[True,False,True]],[[1,2,float('nan')]],[[1,2,float('inf')]],[[1,2,'3']]):
            with self.assertRaises(ValueError): validate({'points':points,'unit':'mm'})
        with self.assertRaises(ValueError): invoke('plane',[[0,0,0],[1,1,1],[2,2,2]])
        with self.assertRaises(ValueError): invoke('filter',[[0,0,0]],method='crop',minimum=[1,1,1],maximum=[2,2,2])
        with self.assertRaises(ValueError): invoke('register',[[0,0,0],[1,1,0],[2,0,1]],targetCloud=cloud([[0,0,0]],'m'))
        for name,header in [('oversized.ply',b'ply\nformat binary_little_endian 1.0\nelement vertex 999999999\nend_header\n'),('oversized.pcd',b'POINTS 999999999\nDATA binary_compressed\n')]:
            with self.assertRaisesRegex(ValueError,'20'):
                run({'operation':'cloud_import','name':name,'content':base64.b64encode(header).decode(),'unit':'mm'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
