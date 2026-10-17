import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('release',ROOT/'deploy/build_release.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)

class ReleaseTests(unittest.TestCase):
    def test_release_allowlist_integrity_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);first=MODULE.build(ROOT,folder/'one.zip');second=MODULE.build(ROOT,folder/'two.zip')
            self.assertEqual(first['sha256'],second['sha256'])
            with zipfile.ZipFile(first['path']) as archive:
                self.assertIsNone(archive.testzip());prefix='SIEANS-Vision-'+json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']+'/'
                names=archive.namelist();manifest=json.loads(archive.read(prefix+'release-manifest.json'))
                self.assertGreater(len(manifest['files']),100)
                self.assertFalse(any('/node_modules/' in n or '/.venv/' in n or '/artifacts/' in n or '/data/' in n or n.endswith(('.pt','.onnx','.pyc')) for n in names))
                for entry in manifest['files']:
                    data=archive.read(prefix+entry['path']);self.assertEqual(len(data),entry['bytes']);self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'])
                self.assertIn(prefix+'operator-plugins/sieans-cylinder/cylinder.py',names)
                self.assertIn(prefix+'operator-plugins/sieans-circle/circle.py',names)
                self.assertIn(prefix+'public/vision/samples/demos-circle.json',names)
                self.assertIn(prefix+'operator-plugins/sieans-heightfield/heightfield.py',names)
                self.assertIn(prefix+'public/vision/samples/demos-heightfield.json',names)
                self.assertIn(prefix+'public/vision/cloud-viewer.js',names)
                for required in ['operator-plugins/sieans-relations/relations.py',
                                 'operator-plugins/sieans-deviation/deviation.py',
                                 'operator-plugins/sieans-image-quality/quality.py',
                                 'public/vision/samples/demos-relations.json',
                                 'public/vision/samples/demos-deviation.json',
                                 'public/vision/samples/demos-image-quality.json',
                                 'public/vision/samples/demos-inspection-chain.json',
                                 'public/vision/samples/caliper-corner.png',
                                 'public/vision/samples/caliper-corner-dark.png',
                                 'public/vision/samples/caliper-corner-blur.png',
                                 'public/vision/samples/caliper-no-corner.png',
                                 'public/vision/samples/caliper-vertical-only.png',
                                 'public/vision/session-management-ui.js',
                                 'docs/geometry-relations.md','docs/cloud-deviation.md','docs/image-quality.md']:
                    self.assertIn(prefix+required,names)
                for required in ['lib/access-control.cjs','lib/operator-runtime.cjs','lib/operation-history.cjs','lib/user-store.cjs','public/vision/accounts-ui.js','public/vision/operation-history-ui.js','docs/accounts-operations.md','docs/operator-continuous.md','docs/operator-cloud-input.md','public/vision/operator-cloud-input.js','public/vision/operator.html','public/vision/operator-page.js']:
                    self.assertIn(prefix+required,names)
                for required in ['vision/template_matching.py','operator-plugins/sieans-fixture/fixture.py','public/vision/samples/demos-fixture.json']:
                    self.assertIn(prefix+required,names)
                for required in ['deploy/data_backup.py','lib/data-backup.cjs','lib/camera-session.cjs','cameras/session_worker.py','lib/process-supervisor.cjs','public/vision/camera-session-ui.js','operator-plugins/sieans-rigid/rigid.py','operator-plugins/sieans-intrinsics/intrinsics.py','lib/mqtt-trigger.cjs','public/vision/hmi-pages.js']:
                    self.assertIn(prefix+required,names)
                self.assertIn(prefix+'deploy/start.sh',names)
                self.assertEqual((archive.getinfo(prefix+'deploy/start.sh').external_attr>>16)&0o777,0o755)
                self.assertEqual(len(names),len(manifest['files'])+1)
                archive.extractall(folder/'unpacked')
            app=folder/'unpacked'/prefix
            def verify():
                return subprocess.run(['node',str(app/'scripts/platform.cjs'),'verify'],capture_output=True,encoding='utf-8',timeout=30)
            self.assertEqual(verify().returncode,0)
            with (app/'server.cjs').open('a',encoding='utf-8') as changed:changed.write('\n// tampered\n')
            self.assertNotEqual(verify().returncode,0)

    def test_same_release_is_idempotent_but_different_archive_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/'release.zip';first=MODULE.build(ROOT,archive);modified=archive.stat().st_mtime_ns
            second=MODULE.build(ROOT,archive);self.assertEqual(first['sha256'],second['sha256']);self.assertEqual(archive.stat().st_mtime_ns,modified)
            archive.write_bytes(b'previous archive placeholder')
            with self.assertRaises(FileExistsError):MODULE.build(ROOT,archive)
            self.assertEqual(archive.read_bytes(),b'previous archive placeholder')

if __name__=='__main__':unittest.main()
