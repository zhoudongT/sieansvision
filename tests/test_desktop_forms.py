"""Offscreen interactions for the native schema editors (no engine required)."""
import os
from copy import deepcopy
from pathlib import Path
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton
from desktop.forms import OutputBindings, ParameterPanel, ResultPanel, StructureEditor, ValueEditor


class NativeFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.step = dict(id='inspect', name='检测', operation='plugin', imageFrom='source',
                         params=dict(pluginId='typed', pluginVersion='1.0.0', operatorId='inspect',
                                     arguments={'gain': 2, 'futureField': {'keep': True}},
                                     inputs={'origin': {'x': 10, 'y': 5}},
                                     outputBindings=[]), futureStepField={'keep': [1, 2]})
        self.project = dict(steps=[dict(id='earlier', name='上游'), self.step,
                                  dict(id='later', name='下游')],
                            edges=[{'from': 'source', 'to': 'earlier'},
                                   {'from': 'source', 'to': 'inspect'},
                                   {'from': 'earlier', 'to': 'inspect'},
                                   {'from': 'inspect', 'to': 'later'}])
        self.definition = dict(name='点偏移', description='表单测试',
                               parameters=[dict(key='gain', label='倍率', type='number', default=1,
                                                minimum=0, maximum=20)],
                               inputs=[dict(key='origin', label='基准点', type='object', properties=[
                                   dict(key='x', label='X', type='number', required=True),
                                   dict(key='y', label='Y', type='number', default=0)])],
                               outputs=[dict(key='point', label='结果点', type='object', properties=[
                                   dict(key='x', label='X', type='number')])])
        self.panel = ParameterPanel()
        self.events = []
        self.panel.changed.connect(self.events.append)
        self.panel.set_step(self.step, self.definition, self.project)

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_loading_is_read_only_and_edit_emits_independent_complete_steps(self):
        before = deepcopy(self.step)
        self.assertEqual(self.events, [])
        editor = self.panel.findChild(ValueEditor, 'parameter:gain')
        editor.literal.setValue(3.25)
        changed = self.events[-1]
        self.assertEqual(changed['params']['arguments']['gain'], 3.25)
        self.assertEqual(changed['params']['arguments']['futureField'], {'keep': True})
        self.assertEqual(changed['futureStepField'], {'keep': [1, 2]})
        self.assertEqual(self.step, before)
        changed['futureStepField']['keep'].append(3)
        editor.literal.setValue(4)
        self.assertEqual(self.events[-1]['futureStepField'], {'keep': [1, 2]})

    def test_identical_state_does_not_rebuild_or_lose_focus_controls(self):
        editor = self.panel.findChild(ValueEditor, 'parameter:gain')
        editor.literal.setValue(4)
        project = deepcopy(self.project)
        project['steps'][1] = deepcopy(self.events[-1])
        self.panel.set_step(self.events[-1], self.definition, project)
        self.assertIs(self.panel.findChild(ValueEditor, 'parameter:gain'), editor)

    def test_nested_input_edits_and_reference_scope_node_path(self):
        editor = self.panel.findChild(ValueEditor, 'input:origin')
        x = editor.literal.findChild(ValueEditor, 'entry:x')
        x.mode.setCurrentIndex(1)
        ref = x.reference
        ref.scope.setCurrentIndex(ref.scope.findData('results'))
        self.assertEqual([ref.node.itemData(i) for i in range(ref.node.count())], ['earlier'])
        ref.path.setText('point.x')
        ref.path.editingFinished.emit()
        self.assertEqual(self.events[-1]['params']['inputs']['origin'],
                         {'x': {'$ref': 'results.earlier.point.x'}, 'y': 5})
        x.mode.setCurrentIndex(0)
        self.assertEqual(self.events[-1]['params']['inputs']['origin']['x'], 10)

    def test_reference_invalid_path_does_not_corrupt_saved_value(self):
        editor = self.panel.findChild(ValueEditor, 'parameter:gain')
        editor.mode.setCurrentIndex(1)
        editor.reference.path.setText('__proto__.value')
        editor.reference.path.editingFinished.emit()
        self.assertEqual(self.events, [])
        editor.reference.path.setText('threshold.value')
        editor.reference.path.editingFinished.emit()
        self.assertEqual(self.events[-1]['params']['arguments']['gain'], {'$ref': 'flow.threshold.value'})

    def test_array_structured_add_edit_remove_honors_bounds(self):
        array = StructureEditor(dict(type='array', minimumRows=1, maximumRows=2,
                                     columns=[dict(key='value', label='值', type='number', default=2)]),
                                [{'value': 1}])
        changes = []
        array.changed.connect(changes.append)
        array.add_button.click()
        self.assertEqual(changes[-1], [{'value': 1}, {'value': 2}])
        self.assertFalse(array.add_button.isEnabled())
        row = array.findChild(ValueEditor, 'entry:1')
        row.literal.findChild(ValueEditor, 'entry:value').literal.setValue(7)
        self.assertEqual(changes[-1], [{'value': 1}, {'value': 7}])
        array._remove(1)
        self.assertEqual(changes[-1], [{'value': 1}])
        count = len(changes)
        array._remove(0)
        self.assertEqual(len(changes), count)
        array.deleteLater()

    def test_free_structure_fields_have_native_type_controls(self):
        record = StructureEditor({'type': 'object'}, {})
        changes = []
        record.changed.connect(changes.append)
        record.new_key.setText('accepted')
        record.new_type.setCurrentIndex(record.new_type.findData('boolean'))
        record.add_button.click()
        self.assertEqual(changes[-1], {'accepted': False})
        record.findChild(ValueEditor, 'entry:accepted').literal.setChecked(True)
        self.assertEqual(changes[-1], {'accepted': True})
        record.deleteLater()

    def test_output_bindings_require_complete_unique_targets(self):
        bindings = self.panel.findChild(OutputBindings)
        bindings.findChild(QPushButton, 'addOutputBinding').click()
        self.assertEqual(self.events, [])
        table = bindings.table
        table.cellWidget(0, 0).setCurrentIndex(table.cellWidget(0, 0).findData('point.x'))
        table.cellWidget(0, 2).setText('answer')
        table.cellWidget(0, 2).editingFinished.emit()
        self.assertEqual(self.events[-1]['params']['outputBindings'],
                         [{'field': 'point.x', 'scope': 'flow', 'name': 'answer'}])
        bindings.findChild(QPushButton, 'addOutputBinding').click()
        table.cellWidget(1, 2).setText('answer')
        count = len(self.events)
        table.cellWidget(1, 2).editingFinished.emit()
        self.assertEqual(len(self.events), count)
        self.assertTrue(bindings.error.text())
        table.cellWidget(1, 3).click()
        self.assertEqual(len(self.events[-1]['params']['outputBindings']), 1)

    def test_core_parameters_and_script_preservation(self):
        core = dict(id='inspect', name='等待', operation='delay', params={'milliseconds': 100, 'hidden': True})
        definition = dict(name='等待', parameters=[dict(key='milliseconds', label='等待时间', type='integer', default=100)])
        self.panel.set_step(core, definition, self.project)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.panel.findChild(ValueEditor, 'parameter:milliseconds').literal.setValue(250)
        self.assertEqual(self.events[-1]['params'], {'milliseconds': 250, 'hidden': True})
        script = dict(id='inspect', operation='script', name='脚本', params={'code': 'return 1', 'arguments': {'x': 2}})
        self.panel.set_step(script, dict(name='脚本', parameters=[dict(key='code', type='string')]), self.project)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertIsNone(self.panel.findChild(ValueEditor, 'parameter:code'))
        self.panel.name_edit.setText('改名')
        self.panel.name_edit.editingFinished.emit()
        self.assertEqual(self.events[-1]['params'], script['params'])

    def test_image_source_selection_emits_actual_connected_id(self):
        choices = self.panel.image_from
        self.assertEqual({choices.itemData(i) for i in range(choices.count())}, {None, 'source', 'earlier'})
        choices.setCurrentIndex(choices.findData('earlier'))
        self.assertEqual(self.events[-1]['imageFrom'], 'earlier')

    def test_core_named_input_uses_direct_parameter_storage(self):
        step = dict(id='inspect', operation='condition', params={'left': 2})
        self.panel.set_step(step, dict(name='判断', inputs=[dict(key='left', type='number')]), self.project)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.panel.findChild(ValueEditor, 'input:left').literal.setValue(4)
        self.assertEqual(self.events[-1]['params'], {'left': 4.0})

    def test_result_tree_is_recursive_lazy_and_hides_image_payload(self):
        panel = ResultPanel()
        images = []
        panel.image_requested.connect(images.append)
        image = 'data:image/png;base64,' + 'A' * 600
        panel.set_results([dict(id='inspect', output=dict(elapsedMs=4, result={'rows': [{'value': 7}], 'ok': True}, annotatedImage=image))])
        root = panel.tree.topLevelItem(0)
        output = next(root.child(i) for i in range(root.childCount()) if root.child(i).text(0) == 'output')
        self.assertEqual(output.child(0).text(0), '展开查看')
        output.setExpanded(True)
        result = next(output.child(i) for i in range(output.childCount()) if output.child(i).text(0) == 'result')
        result.setExpanded(True)
        rows = next(result.child(i) for i in range(result.childCount()) if result.child(i).text(0) == 'rows')
        rows.setExpanded(True)
        rows.child(0).setExpanded(True)
        self.assertEqual(rows.child(0).child(0).text(1), '7')
        img = next(output.child(i) for i in range(output.childCount()) if output.child(i).text(0) == 'annotatedImage')
        self.assertEqual(img.text(1), '双击查看图像')
        panel.tree.itemActivated.emit(img, 1)
        self.assertEqual(images, [image])
        panel.deleteLater()


if __name__ == '__main__':
    unittest.main(verbosity=2)
