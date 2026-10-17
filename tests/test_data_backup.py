import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('backup_worker',Path(__file__).resolve().parents[1]/'deploy/data_backup.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sieans-backup-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=self.root/'data';self.data.mkdir();self.zip=self.root/'backup.zip'
        (self.data/'.config.runtime.json').write_text('credential-secret',encoding='utf-8')
        (self.data/'empty').mkdir();(self.data/'models').mkdir();(self.data/'models/part.onnx').write_bytes(b'model-fixture')
        for folder in ['cache','logs']:
            (self.data/folder).mkdir();(self.data/folder/'excluded').write_text('skip')
        (self.data/b.LOCK).write_text('lock')

    def backup(self,models=None):return b.backup(dict(data=str(self.data),output=str(self.zip),programVersion='test',models=str(models or self.data/'models')))

    def target(self):
        target=self.root/'restored';target.mkdir();(target/b.LOCK).write_text('lock');(target/b.MARKER).write_text('marker');return target

    def rewrite(self,mutate):
        with zipfile.ZipFile(self.zip) as archive:contents={i.filename:(i,archive.read(i)) for i in archive.infolist()}
        manifest=json.loads(contents[b.MANIFEST][1]);mutate(manifest,contents)
        contents[b.MANIFEST]=(b.MANIFEST,json.dumps(manifest).encode())
        with zipfile.ZipFile(self.zip,'w') as archive:
            for info,data in contents.values():archive.writestr(info,data)

    def test_roundtrip_hidden_empty_binary_and_exclusions(self):
        result=self.backup();self.assertEqual(result['models'],'internal');self.assertEqual(result['files'],2)
        self.assertEqual(b.inspect(dict(archive=str(self.zip)))['sha256'],result['sha256'])
        target=self.target();restored=b.restore(dict(archive=str(self.zip),target=str(target),expectedSha256=result['sha256']))
        self.assertEqual(restored['modelsPath'],str(target/'models'));self.assertTrue((target/'empty').is_dir())
        self.assertEqual((target/'.config.runtime.json').read_text(),'credential-secret');self.assertFalse((target/'cache').exists())
        self.assertEqual((target/'models/part.onnx').read_bytes(),b'model-fixture')
        if os.name!='nt':self.assertEqual(stat.S_IMODE(self.zip.stat().st_mode),0o600)

    def test_external_models(self):
        models=self.root/'separate';models.mkdir();(models/'model.bin').write_bytes(b'outside')
        result=self.backup(models);target=self.target();out=b.restore(dict(archive=str(self.zip),target=str(target),expectedSha256=result['sha256']))
        self.assertEqual((Path(out['modelsPath'])/'model.bin').read_bytes(),b'outside');self.assertEqual(Path(out['modelsPath']).parent,target)

    def test_refuses_overwrite_and_source_output(self):
        self.backup();original=self.zip.read_bytes()
        with self.assertRaises(FileExistsError):self.backup()
        self.assertEqual(original,self.zip.read_bytes())
        with self.assertRaises(ValueError):b.backup(dict(data=str(self.data),output=str(self.data/'bad.zip'),programVersion='test'))

    def test_tampered_digest_and_unlisted_member(self):
        self.backup();self.rewrite(lambda m,c:m['files'][0].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'摘要'):b.inspect(dict(archive=str(self.zip)))
        with zipfile.ZipFile(self.zip,'a') as archive:archive.writestr('data/extra','unexpected')
        with self.assertRaises(ValueError):b.load_archive(self.zip)

    def test_traversal_case_collisions_and_reserved_paths(self):
        result=self.backup();original=self.zip.read_bytes()
        for name in ['data/../escape','data/C:/escape','data/foo\\escape','data/CON','data/.SIEANS-RUNTIME.LOCK/x','data/a.','/data/a']:
            with self.subTest(name=name):
                self.zip.write_bytes(original);self.rewrite(lambda m,c:m['directories'].append(name))
                with self.assertRaises(ValueError):b.inspect(dict(archive=str(self.zip)))
        self.zip.write_bytes(original);self.rewrite(lambda m,c:m['directories'].append('data/EMPTY'))
        with self.assertRaises(ValueError):b.inspect(dict(archive=str(self.zip)))

    def test_symlink_members_and_bad_compression(self):
        self.backup();original=self.zip.read_bytes()
        def symlink(m,c):
            key=m['files'][0]['path'];info,data=c[key];info.external_attr=(stat.S_IFLNK|0o777)<<16;c[key]=(info,data)
        self.rewrite(symlink)
        with self.assertRaises(ValueError):b.inspect(dict(archive=str(self.zip)))
        self.zip.write_bytes(original)
        def compressed(m,c):
            key=m['files'][0]['path'];info,data=c[key];info.compress_type=zipfile.ZIP_BZIP2;c[key]=(info,data)
        self.rewrite(compressed)
        with self.assertRaises(ValueError):b.inspect(dict(archive=str(self.zip)))

    def test_restore_requires_reservation_and_matching_archive(self):
        result=self.backup();target=self.target()
        with self.assertRaises(ValueError):b.restore(dict(archive=str(self.zip),target=str(target),expectedSha256='0'*64))
        (target/'existing').write_text('retain')
        with self.assertRaises(ValueError):b.restore(dict(archive=str(self.zip),target=str(target),expectedSha256=result['sha256']))
        self.assertEqual((target/'existing').read_text(),'retain')

    def test_file_directory_conflict_and_invalid_model_directory(self):
        self.backup();original=self.zip.read_bytes()
        self.rewrite(lambda m,c:m['directories'].append(m['files'][0]['path']+'/child'))
        with self.assertRaises(ValueError):b.inspect(dict(archive=str(self.zip)))
        self.zip.write_bytes(original);self.rewrite(lambda m,c:m.update(models=dict(kind='internal',relative='missing')))
        with self.assertRaises(ValueError):b.inspect(dict(archive=str(self.zip)))

    def test_source_change_cleans_only_own_output(self):
        original=b.inventory;calls=0
        def changed(root,prefix):
            nonlocal calls
            calls+=1
            if calls==2:(self.data/'new-file').write_text('changed')
            return original(root,prefix)
        b.inventory=changed
        try:
            with self.assertRaisesRegex(ValueError,'变化'):self.backup()
            self.assertFalse(self.zip.exists());self.assertEqual(list(self.root.glob('*.tmp-*')),[])
        finally:b.inventory=original

    def test_implicit_parent_case_conflicts(self):
        with self.assertRaises(ValueError):b.validate_paths([('data/A/file','file'),('data/a/other','file')])
        with self.assertRaises(ValueError):b.validate_paths([('data/name','file'),('data/name/child','file')])
        b.validate_paths([('data/a','directory'),('data/a/file','file'),('data/a/other','file')])


if __name__=='__main__':unittest.main()
