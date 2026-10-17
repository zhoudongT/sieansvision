import base64
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'vision'))
from annotation_suggestions import convert,suggest
from annotations import revision
from training import parse_labels


class SuggestionTests(unittest.TestCase):
    def test_detect_clipping_and_invalid_geometry(self):
        result=convert([dict(bbox=[-10,20,50,40],label='part',classId=9,confidence=.8),dict(bbox=[20,20,0,4],label='x',classId=0,confidence=.5)],'detect',100,200)
        self.assertEqual(result['proposals'][0]['box'],[.2,.2,.4,.2]);self.assertEqual(len(result['rejected']),1)
        self.assertNotIn('classId',result['proposals'][0])  # Model class numbers never become dataset classes implicitly.

    def test_holes_disconnected_and_self_intersection_require_manual_work(self):
        outline=dict(points=[[0,0],[90,0],[90,90],[0,90]],isHole=False)
        records=[dict(contours=[outline],label='part',classId=1,confidence=.8),dict(contours=[outline,dict(points=[[5,5],[6,5],[6,6]],isHole=True)],label='hole',classId=1,confidence=.8),dict(contours=[outline,outline],label='islands',classId=1,confidence=.8),dict(contours=[dict(points=[[0,0],[90,90],[0,90],[90,0]],isHole=False)],label='cross',classId=1,confidence=.8)]
        result=convert(records,'segment',100,100);self.assertEqual(len(result['proposals']),1);self.assertEqual(len(result['rejected']),3)

    def test_actual_detect_and_segment_are_read_only_and_revision_guarded(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);(folder/'images/train').mkdir(parents=True);(folder/'labels/train').mkdir(parents=True)
            image=folder/'images/train/bus.jpg';image.write_bytes((ROOT/'public/vision/samples/segmentation-bus.jpg').read_bytes());label=folder/'labels/train/bus.txt'
            before=revision(image,label)
            for task,model in [('detect','yolo11n.pt'),('segment','yolo11n-seg.pt')]:
                request=dict(folder=str(folder),split='train',name=image.name,task=task,names=['bus'],revision=before,modelPath=str(ROOT/'models'/model),device='cpu',confidence=.25)
                response=suggest(request);bus=next(p for p in response['proposals'] if p['label']==('bus' if task=='detect' else 'person'))
                coords=bus.get('box') or [v for p in bus['points'] for v in p]
                parse_labels('0 '+' '.join(map(str,coords)),task,['bus'])
                self.assertEqual(response['device'],'cpu');self.assertEqual(response['revision'],before);self.assertFalse(label.exists());self.assertEqual(revision(image,label),before)
                with self.assertRaisesRegex(ValueError,'不一致'):suggest(dict(request,task='segment' if task=='detect' else 'detect'))
                with self.assertRaisesRegex(ValueError,'其他页面'):suggest(dict(request,revision='stale'))
                for value in [True,0,float('nan'),2]:
                    with self.assertRaises(ValueError):suggest(dict(request,confidence=value))


if __name__=='__main__':unittest.main(verbosity=2)
