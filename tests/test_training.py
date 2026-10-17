import shutil
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'))
from training import demo, inspect_dataset

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)/'dataset';demo(self.folder,'detect')

    def test_real_images_counts_background_and_fingerprint(self):
        info,_=inspect_dataset(self.folder,'detect',['part'])
        self.assertEqual(info['splits']['train']['images'],12);self.assertEqual(info['splits']['val']['objects'],4)
        label=self.folder/'labels/train/part-0.txt';label.write_text('')
        changed,_=inspect_dataset(self.folder,'detect',['part'])
        self.assertEqual(changed['splits']['train']['positiveImages'],11);self.assertNotEqual(changed['fingerprint'],info['fingerprint'])

    def test_duplicate_content_and_missing_label_are_rejected(self):
        image=self.folder/'images/val/part-0.png';shutil.copyfile(self.folder/'images/train/part-0.png',image)
        with self.assertRaisesRegex(ValueError,'重复'):inspect_dataset(self.folder,'detect',['part'])
        image.unlink();(self.folder/'labels/train/part-0.txt').unlink()
        with self.assertRaisesRegex(ValueError,'缺少标注'):inspect_dataset(self.folder,'detect',['part'])

    def test_invalid_class_coordinates_box_and_nonfinite(self):
        label=self.folder/'labels/train/part-0.txt'
        for text in ['1 .5 .5 .2 .2','0 -.1 .5 .2 .2','0 .99 .5 .2 .2','0 .5 .5 0 .2','0 nan .5 .2 .2','0 .5 .5']:
            with self.subTest(label=text):
                label.write_text(text)
                with self.assertRaises(ValueError):inspect_dataset(self.folder,'detect',['part'])

    def test_segmentation_polygons_and_task_mismatch(self):
        folder=Path(self.temp.name)/'segment';demo(folder,'segment')
        info,_=inspect_dataset(folder,'segment',['part']);self.assertEqual(info['splits']['val']['objects'],4)
        with self.assertRaises(ValueError):inspect_dataset(folder,'detect',['part'])
        label=folder/'labels/train/part-0.txt'
        for text in ['0 .1 .1 .2 .2','0 .1 .1 .2 .2 .3 .3','0 .1 .1 .2 .2 1.2 .3']:
            label.write_text(text)
            with self.assertRaises(ValueError):inspect_dataset(folder,'segment',['part'])

if __name__=='__main__':unittest.main(verbosity=2)
