import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop.model import Document
from desktop.catalog import CORE
from desktop.catalog import all_definitions
from desktop.forms import ParameterPanel,ValueEditor
from desktop.mainwindow import MainWindow

app=QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parent.parent


def wait_until(predicate,ms=20000):
    for _ in range(ms//20):
        app.processEvents();QTest.qWait(20)
        if predicate():return
    raise AssertionError('等待原生引擎超时')


class WorkbenchTests(unittest.TestCase):
    def test_complete_builtin_catalog_renders_without_mutating_project_or_exposing_script(self):
        definitions=all_definitions([]);self.assertEqual(len(definitions),37)
        for key,definition in definitions.items():
            with self.subTest(operator=key):
                doc=Document();node=doc.add(definition);before=deepcopy(doc.project)
                panel=ParameterPanel();events=[];panel.changed.connect(events.append)
                panel.set_step(doc.project['steps'][0],definition,doc.project)
                self.assertEqual(events,[]);self.assertEqual(doc.project,before)
                if key=='script':self.assertIsNone(panel.findChild(ValueEditor,'parameter:code'))
                panel.close();panel.deleteLater()

    def test_migrated_panels_open_against_real_engine_and_continuous_survives_hide(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(ROOT,Path(directory));window.show()
            try:
                wait_until(lambda:window.engine_ready and len(window.definitions)>40)
                for key in ['variables','hmi','projects','plugins','history','audit','accounts','training']:
                    window.open_panel(key);app.processEvents()
                    self.assertTrue(window.dialogs[key].isVisible(),key)
                    window.dialogs[key].hide()
                window.open_panel('continuous');dialog=window.dialogs['continuous']
                dialog.close();app.processEvents()
                self.assertIn('continuous',window.dialogs)
                window.set_busy(True);window.open_panel('continuous');app.processEvents()
                self.assertTrue(dialog.isVisible())
                window.set_busy(False)
                window.cloud={'points':[[1,2,3]],'unit':'mm'};window.depth={'test':True}
                window.demo();self.assertIsNone(window.cloud);self.assertIsNone(window.depth)
                dialog.set_input(window.image);dialog.interval.setValue(100);dialog.max_cycles.setValue(2)
                dialog.start_continuous();wait_until(lambda:window.busy)
                dialog.close()
                wait_until(lambda:not window.busy and window.last_result is not None)
                self.assertEqual(dialog.states['continuous']['completedCycles'],2)
                self.assertEqual(window.last_result['state'],'completed')
                self.assertFalse(window.output_view.scene().itemsBoundingRect().isEmpty())
            finally:
                window.document.saved=deepcopy(window.document.project)
                window.close();wait_until(lambda:window.engine_stopped)

    def test_copy_and_history_keep_internal_binding_independent(self):
        doc=Document();a=doc.add(CORE[0]);b=doc.add(CORE[1],parent=a)
        p=deepcopy(doc.project);p['steps'][1]['params']['minArea']={'$ref':'results.'+a+'.count'};doc.commit(p)
        doc.copy([a,b]);ids=doc.paste()
        self.assertEqual(doc.project['steps'][-1]['params']['minArea']['$ref'],'results.'+ids[0]+'.count')
        self.assertEqual(doc.project['steps'][-1]['imageFrom'],ids[0]);doc.undo();self.assertEqual(len(doc.project['steps']),2)
        doc.redo();self.assertEqual(len(doc.project['steps']),4)
        before=deepcopy(doc.project)
        with self.assertRaisesRegex(ValueError,'循环'):doc.connect(b,a)
        self.assertEqual(doc.project,before)

    def test_native_demo_runs_real_engine_and_closes_owned_process(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(ROOT,Path(directory));window.show()
            try:
                wait_until(lambda:window.engine_ready and len(window.definitions)>10)
                window.demo();self.assertEqual(len(window.scene.nodes),3)
                window.run();wait_until(lambda:not window.busy)
                self.assertIn('运行完成',window.logs.toPlainText())
                self.assertEqual(window.images.currentIndex(),1)
                self.assertTrue(any('完成' in item.state for key,item in window.scene.nodes.items() if key!='source'))
                self.assertFalse(window.output_view.scene().itemsBoundingRect().isEmpty())
                self.assertGreater(len(window.definitions),40)
            finally:
                window.document.saved=deepcopy(window.document.project)
                window.close();wait_until(lambda:window.engine_stopped)
                self.assertEqual(window.backend.process.processId(),0)


if __name__=='__main__':unittest.main()
