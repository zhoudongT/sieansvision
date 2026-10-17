import base64
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'vision'))
from training import demo,inspect_dataset,parse_labels
from annotations import handle,image_path

class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)/'data';demo(self.folder,'detect')
        self.base=dict(folder=str(self.folder),task='detect',names=['part'],split='train',name='part-0.png')

    def invoke(self,action,**values):return handle(dict(self.base,**values,action='annotation_'+action))

    def test_saved_box_roundtrip_conflict_and_backup(self):
        original=self.invoke('load');self.assertEqual(original['width'],128);self.assertTrue(original['image'].startswith('data:image/png;base64,'))
        records=[dict(classId=0,box=[.5,.5,.25,.375])]
        saved=self.invoke('save',records=records,revision=original['revision'])
        loaded=self.invoke('load');self.assertEqual(loaded['records'],records);self.assertEqual(loaded['revision'],saved['revision'])
        self.assertEqual(len(list((self.folder/'annotation-history/train/part-0').glob('*.txt'))),1)
        with self.assertRaisesRegex(ValueError,'其他页面'):self.invoke('save',records=[],revision=original['revision'])
        self.assertEqual(self.invoke('load')['records'],records)

    def test_invalid_box_and_class_do_not_replace_saved_label(self):
        original=self.invoke('load');before=(self.folder/'labels/train/part-0.txt').read_bytes()
        for record in [dict(classId=0,box=[.99,.5,.5,.2]),dict(classId=9,box=[.5,.5,.2,.2]),dict(classId=True,box=[.5,.5,.2,.2]),dict(classId=0,box=[.5,.5,float('nan'),.2])]:
            with self.subTest(record=record),self.assertRaises(ValueError):self.invoke('save',records=[record],revision=original['revision'])
        self.assertEqual((self.folder/'labels/train/part-0.txt').read_bytes(),before)

    def test_import_leaves_unlabelled_until_explicit_background_and_rejects_duplicates(self):
        content=(ROOT/'public/vision/samples/parts.png').read_bytes();encoded=base64.b64encode(content).decode()
        self.invoke('upload',name='uploaded.png',image=encoded)
        loaded=self.invoke('load',name='uploaded.png');self.assertFalse(loaded['hasLabel']);self.assertEqual(loaded['records'],[])
        with self.assertRaisesRegex(ValueError,'缺少标注'):inspect_dataset(self.folder,'detect',['part'])
        with self.assertRaisesRegex(ValueError,'重复'):self.invoke('upload',name='other.png',split='val',image=encoded)
        self.invoke('save',name='uploaded.png',records=[],revision=loaded['revision'])
        self.assertTrue(self.invoke('load',name='uploaded.png')['hasLabel']);info,_=inspect_dataset(self.folder,'detect',['part']);self.assertEqual(info['splits']['train']['images'],13);self.assertEqual(info['splits']['train']['positiveImages'],12)

    def test_polygon_roundtrip_and_self_intersection(self):
        folder=Path(self.temp.name)/'segment';demo(folder,'segment');self.base.update(folder=str(folder),task='segment')
        old=self.invoke('load');points=[[.1,.1],[.9,.15],[.8,.85],[.2,.8]]
        self.invoke('save',records=[dict(classId=0,points=points)],revision=old['revision'])
        loaded=self.invoke('load');self.assertEqual(loaded['records'][0]['points'],points)
        for points in [[[.1,.1],[.9,.8],[.1,.8],[.9,.1],[.5,.95]],[[.1,.1],[.2,.2],[.3,.3]],[[.1,.1],[.9,.1],[.9,.1],[.5,.8]]]:
            with self.subTest(points=points),self.assertRaises(ValueError):self.invoke('save',records=[dict(classId=0,points=points)],revision=loaded['revision'])

    def test_history_is_read_only_and_explicit_restore_preserves_replaced_version(self):
        original=self.invoke('load')
        self.assertEqual(self.invoke('history',revision=original['revision'])['entries'],[])
        self.invoke('save',revision=original['revision'],records=[])
        current=self.invoke('load');history=self.invoke('history',revision=current['revision'])
        self.assertEqual(len(history['entries']),1);entry=history['entries'][0]
        restored=self.invoke('history_load',revision=current['revision'],historyId=entry['id'])
        self.assertEqual(restored['records'],original['records']);self.assertEqual(self.invoke('load')['records'],[])
        self.invoke('save',revision=current['revision'],records=restored['records'])
        loaded=self.invoke('load');self.assertEqual(loaded['records'],original['records'])
        entries=self.invoke('history',revision=loaded['revision'])['entries'];self.assertEqual(len(entries),2)
        self.assertTrue(any(e['objects']==0 for e in entries))
        with self.assertRaisesRegex(ValueError,'其他页面'):self.invoke('history_load',revision=current['revision'],historyId=entry['id'])

    def test_history_rejects_traversal_invalid_geometry_and_truncates_listing(self):
        current=self.invoke('load');folder=self.folder/'annotation-history/train/part-0';folder.mkdir(parents=True)
        for i in range(202):(folder/(format(i,'032x')+'.txt')).write_text('0 .5 .5 .2 .2',encoding='utf-8')
        bad=folder/('f'*32+'.txt');bad.write_text('0 .5 .5 -1 0',encoding='utf-8')
        listed=self.invoke('history',revision=current['revision']);self.assertTrue(listed['limitReached']);self.assertEqual(len(listed['entries']),200);self.assertTrue(any(not e['valid'] for e in listed['entries']))
        for identifier in ['../escape','x','a'*32+'/x']:
            with self.assertRaisesRegex(ValueError,'编号无效'):self.invoke('history_load',revision=current['revision'],historyId=identifier)
        with self.assertRaises(ValueError):self.invoke('history_load',revision=current['revision'],historyId='f'*32)

    def test_path_traversal_reserved_names_and_fake_images(self):
        for split,name in [('test','part.png'),('train','../part.png'),('train','folder\\part.png'),('train','CON.png'),('train','x.svg')]:
            with self.subTest(name=name),self.assertRaises(ValueError):image_path(self.folder,split,name)
        with self.assertRaises(ValueError):self.invoke('upload',name='fake.png',image=base64.b64encode(b'<script>bad</script>').decode())
        self.assertFalse((self.folder/'images/train/fake.png').exists())

    def test_image_changes_invalidate_revision_and_split_lists_are_distinct(self):
        original=self.invoke('load');path=self.folder/'images/train/part-0.png';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'其他页面'):self.invoke('save',revision=original['revision'],records=[])
        rows=self.invoke('list')['items'];self.assertEqual(sum(r['split']=='train' for r in rows),12);self.assertEqual(sum(r['split']=='val' for r in rows),4)

if __name__=='__main__':unittest.main(verbosity=2)
