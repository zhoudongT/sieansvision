"""Demo selection and lossless workspace return, with real-engine smoke coverage."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from desktop.demo_dialog import DemoDialog
from desktop.mainwindow import MainWindow
from desktop.model import Document
from desktop.catalog import CORE

app=QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parent.parent


class FakeBackend(QObject):
    result=Signal(str,object)
    error=Signal(str,str)
    def request(self,method,params):self.method=method;return 'request'


def wait_until(predicate,ms=20000):
    for _ in range(ms//20):
        app.processEvents();QTest.qWait(20)
        if predicate():return
    raise AssertionError('演示请求未在预期时间完成')


class DemoUiTests(unittest.TestCase):
    def test_search_categories_disabled_plugins_and_explicit_load_signal(self):
        backend=FakeBackend();dialog=DemoDialog(backend,ROOT);requests=[]
        dialog.load_requested.connect(lambda key,run:requests.append((key,run)))
        try:
            backend.result.emit('request',{'items':[
                dict(id='locate',category='定位',name='模板定位',description='查找零件',expected='中心位置',image='demo-locate.png'),
                dict(id='cloud-box',category='3D',name='箱体尺寸',description='三维测量',expected='20 mm'),
                dict(id='python-vars',category='流程',name='三级变量',description='可信脚本',expected='count=3',hasScripts=True),
                dict(id='plugin-off',category='检测',name='停用插件',description='检查配置',expected='',available=False,unavailableReason='插件已停用')
            ]})
            self.assertEqual(dialog.table.rowCount(),4)
            dialog.search.setText('20 mm');self.assertEqual(dialog.table.rowCount(),1)
            dialog.load(False);self.assertEqual(requests,[('cloud-box',False)])
            dialog.search.clear();dialog.category.setCurrentIndex(dialog.category.findData('定位'))
            dialog.load(True);self.assertEqual(requests[-1],('locate',True))
            dialog.category.setCurrentIndex(0);dialog.search.setText('停用插件')
            self.assertFalse(dialog.load_button.isEnabled());dialog.load(True);self.assertEqual(len(requests),2)
            dialog.search.setText('三级变量');self.assertIn('脚本',dialog.requirements.text())
            self.assertEqual(dialog.run_button.text(),'载入演示')
            dialog.set_busy(True);self.assertFalse(dialog.run_button.isEnabled())
            dialog.search.setText('不存在的名称');self.assertEqual(dialog.table.rowCount(),0)
        finally:dialog.close()

    def test_demo_return_restores_unsaved_history_clipboard_source_and_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(ROOT,Path(directory),start_engine=False)
            try:
                first=window.document.add(CORE[0]);window.document.saved=deepcopy(window.document.project)
                window.document.add(CORE[1],parent=first);window.document.copy([first]);window.selected=first
                window.filename=Path(directory)/'original.sieans';window.image='data:image/png;base64,'+base64.b64encode((ROOT/'public/vision/samples/parts.png').read_bytes()).decode()
                window.cloud={'points':[[1,2,3]],'unit':'mm'};window.depth={'raw':{'preserve':True}}
                original=window.backup_workspace();draft=Document();draft.add(CORE[1])
                reply=dict(item=dict(id='test',name='测试演示',expected='测量结果'),project=draft.project,image='',cloud=None,depth=None,autoRun=True)
                window.apply_demo(reply,False)
                self.assertTrue(window.return_demo_action.isVisible());self.assertTrue(window.document.modified)
                window.document.add(CORE[0]);window.apply_demo(reply,False)
                self.assertEqual(window.demo_backup['project'],original['project'])
                window.document.saved=deepcopy(window.document.project)
                with patch('desktop.mainwindow.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel) as question:
                    self.assertFalse(window.confirm_discard(include_original=True));question.assert_called_once()
                window.restore_demo()
                for key in ('project','history','index','saved','clipboard'):self.assertEqual(getattr(window.document,key),original[key])
                for key in ('selected','filename','image','cloud','depth'):self.assertEqual(getattr(window,key),original[key])
                self.assertTrue(window.document.modified);self.assertIsNone(window.demo_backup)
                self.assertFalse(window.return_demo_action.isVisible())
            finally:window.document.saved=deepcopy(window.document.project);window.close()

    def test_loading_error_unlocks_without_replacing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(ROOT,Path(directory),start_engine=False)
            try:
                original=deepcopy(window.document.project);window.engine_ready=True
                with patch.object(window,'request',return_value='demo-request'):
                    window.load_demo('missing',True)
                self.assertTrue(window.busy);window.engine_error('demo-request','演示素材不存在')
                self.assertFalse(window.busy);self.assertFalse(window.demo_loading)
                self.assertEqual(window.document.project,original);self.assertIsNone(window.demo_backup)
            finally:window.close()

    def test_real_demo_library_load_run_restore_cloud_and_hmi_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(ROOT,Path(directory));window.show()
            try:
                wait_until(lambda:window.engine_ready and len(window.definitions)>40)
                window.document.add(CORE[0]);original=deepcopy(window.document.project)
                window.open_demo_library();dialog=window.dialogs['demos']
                wait_until(lambda:len(dialog.items)==149)
                dialog.search.setText('模板平移定位');dialog.load(True)
                wait_until(lambda:window.last_result is not None and not window.busy)
                self.assertEqual(window.last_result['state'],'completed')
                self.assertTrue(window.last_result['results'][0]['output']['result']['found'])
                window.load_demo('cloud-box',True)
                wait_until(lambda:window.last_result is not None and not window.busy and window.document.project['name'].endswith('3D 标准件尺寸'))
                self.assertEqual(window.last_result['state'],'completed');self.assertEqual(window.images.currentIndex(),2)
                self.assertIsNotNone(window.cloud)
                window.load_demo('depth-file-top',False);wait_until(lambda:not window.busy)
                self.assertIn('64 × 48',window.depth_caption.text());self.assertEqual(window.images.currentIndex(),3)
                self.assertFalse(window.depth_view.scene().itemsBoundingRect().isEmpty())
                window.run();wait_until(lambda:not window.busy)
                self.assertEqual(window.last_result['state'],'completed')
                window.load_demo('hmi-inspection',False);wait_until(lambda:not window.busy)
                ids={s['id'] for s in window.document.project['steps']}
                components=window.document.project['hmi']['components']
                self.assertTrue(any(c.get('binding',{}).get('nodeId') in ids for c in components))
                window.load_demo('python-vars',True);wait_until(lambda:not window.busy)
                self.assertIsNone(window.last_result);self.assertFalse(window.script_action.isChecked())
                window.restore_demo();self.assertEqual(window.document.project,original)
            finally:
                window.document.saved=deepcopy(window.document.project);window.demo_backup=None
                window.close();wait_until(lambda:window.engine_stopped)


if __name__=='__main__':unittest.main()
