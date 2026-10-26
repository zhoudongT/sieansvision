"""Native HMI/variable contracts: real schema, draft safety, scoped RPC and Qt UI."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PySide6.QtCore import QObject, Signal, QPointF, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QComboBox
from PySide6.QtTest import QTest

from desktop.model import Document
from desktop.catalog import CORE
from desktop.backend import Backend
from desktop.variables_dialog import (DataTree, MISSING, TypedValueDialog, VariablesDialog,
    type_matches, validate_values)
from desktop.hmi_editor import (COL_WIDTH, ComponentItem, HmiDialog, new_component,
    RecordTable, empty_page, pages, read_binding, validate_layout)

app = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parent.parent


class FakeBackend(QObject):
    result = Signal(str, object)
    error = Signal(str, str)

    def __init__(self): super().__init__(); self.requests = []; self.serial = 0

    def request(self, method, params=None):
        self.serial += 1; request_id = str(self.serial)
        self.requests.append((request_id, method, deepcopy(params or {})))
        return request_id

    def reply(self, value):
        request_id = self.requests[-1][0]; self.result.emit(request_id, deepcopy(value))


def project_document():
    document = Document(); node_id = document.add(CORE[0])
    project = deepcopy(document.project)
    project['variables'] = {'count': 0, 'rows': [1, 2], 'flag': False}
    project['variableTypes'] = {'count': 'integer', 'rows': 'integer[]', 'flag': 'boolean'}
    project['vendorExtension'] = {'token': ['preserve', 1]}
    project['steps'][0]['variables'] = {'done': False}; project['steps'][0]['variableTypes'] = {'done': 'boolean'}
    project['steps'][0]['vendorExtension'] = {'hidden': 42}
    document.load(project)
    return document, node_id


def snapshot(document):
    return {'revision': 7, 'global': {'line': 'A'}, 'globalTypes': {'line': 'string'},
        'flow': deepcopy(document.project['variables']), 'modules': {s['id']: deepcopy(s.get('variables', {})) for s in document.project['steps']}}


class VariableTests(unittest.TestCase):
    def setUp(self): self.dialogs = []
    def tearDown(self):
        for dialog in self.dialogs: dialog.reject()
        app.processEvents()

    def dialog(self):
        document, node = project_document(); backend = FakeBackend(); dialog = VariablesDialog(document, backend)
        self.dialogs.append(dialog); app.processEvents(); backend.reply(snapshot(document))
        return document, node, backend, dialog

    def test_initial_contracts_and_unknown_fields_are_preserved(self):
        document, node, backend, dialog = self.dialog(); original = deepcopy(document.project)
        dialog.mode.setCurrentIndex(dialog.mode.findData('initial'))
        dialog.initial['flow']['count'] = 5; dialog.initial['module:' + node]['points'] = [1.5, 2.5]
        dialog.types['module:' + node]['points'] = 'number[]'; dialog.apply()
        self.assertEqual(document.project['variables']['count'], 5)
        self.assertEqual(document.project['steps'][0]['variableTypes']['points'], 'number[]')
        self.assertEqual(document.project['vendorExtension'], original['vendorExtension'])
        self.assertEqual(document.project['steps'][0]['vendorExtension'], original['steps'][0]['vendorExtension'])
        self.assertEqual(dialog.snapshot['flow']['count'], 0)
        self.assertEqual([r[1] for r in backend.requests], ['variables/get'])
        document.undo(); self.assertTrue(dialog.stale)

    def test_runtime_revision_owned_requests_and_busy_lock(self):
        document, node, backend, dialog = self.dialog()
        backend.result.emit('someone-else', {'revision': 999})
        backend.error.emit('someone-else', 'unrelated')
        self.assertEqual(dialog.snapshot['revision'], 7)
        self.assertNotEqual(dialog.message.text(), 'unrelated')
        dialog.mode.setCurrentIndex(dialog.mode.findData('current'))
        dialog.runtime_draft['global']['line'] = 'B'; dialog.apply()
        request_id, method, params = backend.requests[-1]
        self.assertEqual(method, 'variables/set'); self.assertEqual(params['revision'], 7)
        self.assertEqual(params['state']['globalTypes'], {'line': 'string'})
        backend.error.emit(request_id, '变量已被其他操作更新，请重新读取')
        self.assertIn('重新读取', dialog.message.text()); self.assertEqual(dialog.runtime_draft['global']['line'], 'B')
        count = len(backend.requests); dialog.set_busy(True); dialog.apply()
        self.assertEqual(len(backend.requests), count); self.assertFalse(dialog.apply_button.isEnabled())

    def test_invalid_types_do_not_commit_and_external_edits_are_not_overwritten(self):
        document, node, backend, dialog = self.dialog(); original = deepcopy(document.project)
        dialog.mode.setCurrentIndex(dialog.mode.findData('initial')); dialog.initial['flow']['count'] = '5'; dialog.apply()
        self.assertEqual(document.project, original); self.assertIn('不匹配', dialog.message.text())
        candidate = deepcopy(document.project); candidate['variables']['count'] = 20; document.commit(candidate)
        dialog.initial['flow']['count'] = 30; dialog.apply()
        self.assertEqual(document.project['variables']['count'], 20)

    def test_nested_editor_round_trips_null_boolean_and_safe_integer(self):
        value = {'rows': [{'id': 9007199254740991, 'ok': False, 'detail': None}], 'count': 0}
        editor = TypedValueDialog(value); self.dialogs.append(editor); editor.accept()
        self.assertEqual(editor.result(), QDialog.DialogCode.Accepted); self.assertEqual(editor.value, value)
        self.assertFalse(type_matches(True, 'integer')); self.assertFalse(type_matches(9007199254740992, 'integer'))
        self.assertTrue(type_matches([], 'boolean[]')); self.assertFalse(type_matches([1, False], 'integer[]'))
        with self.assertRaises(ValueError): validate_values({'v': [1, '2']}, {'v': 'integer[]'})
        tree = DataTree({'zero': 0, 'false': False, 'null': None})
        self.assertEqual([tree.topLevelItem(i).text(1) for i in range(3)], ['0', '否', '空值'])


class HmiTests(unittest.TestCase):
    def setUp(self): self.dialogs = []
    def tearDown(self):
        for dialog in self.dialogs: dialog.reject()
        app.processEvents()

    def dialog(self, types=('value', 'input', 'button', 'lamp', 'table', 'alarm', 'trend', 'cloud')):
        document, node = project_document(); p = deepcopy(document.project); layout = empty_page()
        for i, kind in enumerate(types):
            c = new_component(kind, p); c['y'] = min(i, layout['rows'] - c['h']); layout['components'].append(c)
        layout['vendorLayout'] = {'keep': 1}; layout['components'][0]['vendorStyle'] = {'keep': False}
        p['hmi'] = layout; document.load(p); backend = FakeBackend(); dialog = HmiDialog(document, backend)
        self.dialogs.append(dialog); app.processEvents()
        if backend.requests: backend.reply({'variables': snapshot(document), 'status': {'state': 'idle'}, 'results': []})
        return document, node, backend, dialog

    def test_layout_round_trip_and_drag_clamp_preserve_extensions(self):
        document, node, backend, dialog = self.dialog(('value',)); original = deepcopy(document.project)
        item = next(i for i in dialog.scene.items() if isinstance(i, ComponentItem))
        item.setPos(QPointF(9999, -100))
        self.assertEqual(item.pos(), QPointF((12 - item.component['w']) * COL_WIDTH, 0))
        item.component['x'] = round(item.pos().x() / COL_WIDTH)
        dialog.apply_layout()
        self.assertEqual(document.project['hmi']['version'], 1)
        self.assertEqual(document.project['hmi']['vendorLayout'], {'keep': 1})
        self.assertEqual(document.project['hmi']['components'][0]['vendorStyle'], {'keep': False})
        self.assertEqual(document.project['vendorExtension'], original['vendorExtension'])
        self.assertEqual(document.project['steps'], original['steps'])

    def test_mouse_drag_updates_grid_model_and_table_columns_show_records(self):
        document, node, backend, dialog = self.dialog(('value',)); dialog.show(); app.processEvents()
        item = next(i for i in dialog.scene.items() if isinstance(i, ComponentItem))
        origin = dialog.view.mapFromScene(item.pos() + QPointF(25, 15))
        target = dialog.view.mapFromScene(item.pos() + QPointF(25 + 2 * COL_WIDTH, 15 + 2 * dialog.current_page()['rowHeight']))
        QTest.mousePress(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=origin)
        QTest.mouseMove(dialog.view.viewport(), target, 30)
        QTest.mouseRelease(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=target)
        self.assertEqual((item.component['x'], item.component['y']), (2, 2))
        table = RecordTable(); table.set_value([{'count': 0, 'passed': False}, {'count': 2, 'passed': True}])
        self.assertEqual(table.table.columnCount(), 2); self.assertEqual(table.table.rowCount(), 2)
        self.assertEqual(table.table.item(0, 0).text(), '0'); self.assertEqual(table.table.item(0, 1).text(), '否')

    def test_all_components_are_valid_in_existing_javascript_schema(self):
        document, node, backend, dialog = self.dialog(tuple(['text', 'value', 'lamp', 'image', 'cloud', 'table', 'button', 'input', 'alarm', 'trend']))
        validate_layout(dialog.draft)
        process = subprocess.run(['node', '-e', "const fs=require('fs'),h=require('./public/vision/hmi-layout.js');h.normalize(JSON.parse(fs.readFileSync(0,'utf8')));"], input=json.dumps(dialog.draft), text=True, cwd=ROOT, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        dialog.preview.setCurrentIndex(1); app.processEvents()
        self.assertEqual(len(dialog.cards), 10)
        self.assertEqual({c.c['type'] for c in dialog.cards}, set(['text', 'value', 'lamp', 'image', 'cloud', 'table', 'button', 'input', 'alarm', 'trend']))

    def test_binding_false_zero_null_missing_and_failed_results(self):
        state = {'variables': {'flow': {'zero': 0, 'false': False, 'null': None, 'rows': [{'x': 2}]}, 'modules': {'n': {'v': 3}}}, 'results': [{'id': 'a', 'error': 'bad', 'output': {'result': {'value': 5}}}, {'id': 'b', 'output': {'result': {'value': 0}}}], 'status': {'elapsedMs': 12}}
        self.assertIs(read_binding({'source': 'flow', 'path': 'false'}, state), False)
        self.assertIsNone(read_binding({'source': 'flow', 'path': 'null'}, state))
        self.assertEqual(read_binding({'source': 'flow', 'path': 'rows.0.x'}, state), 2)
        self.assertEqual(read_binding({'source': 'module', 'nodeId': 'n', 'path': 'v'}, state), 3)
        self.assertIs(read_binding({'source': 'result', 'nodeId': 'a', 'path': 'value'}, state), MISSING)
        self.assertEqual(read_binding({'source': 'result', 'nodeId': 'b', 'path': 'value'}, state), 0)
        self.assertIs(read_binding({'source': 'flow', 'path': '__proto__'}, state), MISSING)

    def test_pending_input_survives_refresh_write_uses_revision_and_busy_locks(self):
        document, node, backend, dialog = self.dialog(('input', 'button'))
        dialog.draft['components'][0]['binding']['path'] = 'count'; dialog.preview.setCurrentIndex(1)
        card = dialog.cards[0]; card.field.setText('4'); card.mark_pending()
        state = {'variables': snapshot(document), 'status': {'state': 'idle'}, 'results': []}
        state['variables']['flow']['count'] = 8; dialog.set_runtime(state)
        self.assertEqual(card.field.text(), '4')
        dialog.preview.setCurrentIndex(0); self.assertEqual(dialog.preview.currentIndex(), 1)
        dialog.write_input(card)
        request_id, method, params = backend.requests[-1]
        self.assertEqual(method, 'variables/set'); self.assertEqual(params['state']['flow']['count'], 4)
        self.assertEqual(params['revision'], 7); self.assertTrue(card.saving)
        saved = deepcopy(params['state']); saved['revision'] = 8; backend.result.emit(request_id, saved)
        self.assertFalse(card.pending); self.assertFalse(card.saving)
        dialog.set_busy(True); self.assertFalse(card.write_button.isEnabled()); self.assertFalse(dialog.apply_button.isEnabled())
        count = len(backend.requests); dialog.write_input(card); self.assertEqual(len(backend.requests), count)
        self.assertEqual(dialog.state['results'], [])

    def test_multi_page_copy_navigation_and_delete_references(self):
        document, node, backend, dialog = self.dialog(('button',))
        dialog.add_page(); other = dialog.active_page; self.assertEqual(dialog.draft['version'], 2)
        main = dialog.draft['pages'][0]; main['components'][0].update(action='navigate', targetPageId=other)
        with self.assertRaisesRegex(ValueError, '引用'): dialog.remove_page()
        dialog.copy_page(); copied = dialog.active_page; self.assertNotEqual(copied, other)
        dialog.set_default(); self.assertEqual(dialog.draft['defaultPageId'], copied)
        dialog.active_page = 'main'; dialog.render(); dialog.preview.setCurrentIndex(1)
        dialog.component_action(main['components'][0]); self.assertEqual(dialog.active_page, other)
        validate_layout(dialog.draft)

    def test_monitor_uses_runtime_samples_and_acknowledges_only_own_request(self):
        document, node, backend, dialog = self.dialog(('alarm', 'trend'))
        monitor = {'widgets': {}, 'events': []}
        for c in dialog.draft['components']:
            signature = json.dumps({k: v for k, v in c.items() if k not in ('x', 'y', 'w', 'h', 'fontSize', 'color')})
            monitor['widgets'][c['id']] = {'signature': signature, 'quality': 'good', 'active': True, 'samples': [{'time': 1000, 'quality': 'good', 'value': 1}, {'time': 2000, 'quality': 'invalid', 'reason': 'failed'}, {'time': 3000, 'quality': 'good', 'value': 3}]}
        alarm = dialog.draft['components'][0]
        monitor['events'] = [{'id': 'event1', 'componentId': alarm['id'], 'label': alarm['label'], 'value': 12, 'startedAt': 1000, 'severity': 'warning'}]
        dialog.set_runtime({'status': {'state': 'completed'}, 'variables': snapshot(document), 'results': [], 'monitor': monitor})
        dialog.preview.setCurrentIndex(1); dialog.show(); app.processEvents()
        self.assertEqual(dialog.cards[0].content.rowCount(), 1)
        self.assertEqual(len(dialog.cards[1].chart.samples), 3)
        dialog.acknowledge(monitor['events'][0], 'checked')
        request_id, method, params = backend.requests[-1]; self.assertEqual(method, 'monitor/ack'); self.assertEqual(params['comment'], 'checked')
        backend.result.emit('unrelated', {}); self.assertEqual(len(dialog.state['monitor']['events']), 1)
        monitor['events'][0]['acknowledgedAt'] = 4000; backend.result.emit(request_id, monitor)
        self.assertFalse(dialog.cards[0].content.cellWidget(0, 6).isEnabled())

    def test_late_runtime_view_cannot_restore_previous_results_after_start(self):
        document, node, backend, dialog = self.dialog(('value',))
        dialog.refresh(); request_id = backend.requests[-1][0]; dialog.set_busy(True)
        backend.result.emit(request_id, {'variables': snapshot(document), 'status': {'state': 'completed'}, 'results': [{'id': node, 'output': {'result': {'count': 99}}}]})
        self.assertEqual(dialog.state['results'], []); self.assertEqual(dialog.state['status']['state'], 'running')


class NativeHmiIntegrationTests(unittest.TestCase):
    def test_real_stdio_run_hmi_variable_write_alarm_ack_and_trend(self):
        def wait_for(predicate, milliseconds=12000):
            for _ in range(milliseconds // 20):
                app.processEvents(); QTest.qWait(20)
                if predicate(): return
            self.fail('原生引擎等待超时：' + str(errors[-3:]))

        with tempfile.TemporaryDirectory() as directory:
            backend = Backend(); errors = []; replies = {}
            backend.error.connect(lambda request_id, message: errors.append((request_id, message)))
            backend.result.connect(lambda request_id, value: replies.update({request_id: value}))
            backend.start(ROOT, Path(directory)); wait_for(lambda: backend.is_ready)
            document = Document(); project = deepcopy(document.project)
            project.update(variables={'count': 0}, variableTypes={'count': 'integer'})
            project['steps'] = [{'id': 'set', 'name': '计数', 'operation': 'variables', 'params': {'scope': 'flow', 'name': 'count', 'value': 3}, 'position': {'x': 100, 'y': 100}, 'imageFrom': 'source', 'variables': {}}]
            project['edges'] = [{'id': 'e', 'from': 'source', 'to': 'set', 'fromPort': 'bottom', 'toPort': 'top'}]
            layout = empty_page()
            for kind in ['button', 'value', 'input', 'alarm', 'trend']:
                c = new_component(kind, project)
                if 'binding' in c: c['binding'] = {'source': 'flow', 'path': 'count'}
                if kind == 'alarm': c['threshold'] = 1
                layout['components'].append(c)
            project['hmi'] = layout; document.load(project)
            dialog = HmiDialog(document, backend); dialog.show()
            try:
                wait_for(lambda: 'revision' in dialog.state['variables'])
                dialog.preview.setCurrentIndex(1)
                run_ids = []
                def run():
                    dialog.set_busy(True)
                    run_ids.append(backend.request('run', {'project': deepcopy(document.project), 'allowScripts': False}))
                dialog.run_requested.connect(run)
                dialog.component_action(layout['components'][0]); wait_for(lambda: run_ids and run_ids[-1] in replies)
                result = replies[run_ids[-1]]; self.assertEqual(result['state'], 'completed', result.get('error'))
                dialog.set_busy(False); dialog.set_runtime(result); dialog.refresh()
                wait_for(lambda: dialog.state['variables']['flow']['count'] == 3 and dialog.state.get('monitor', {}).get('events'))
                value_card = next(c for c in dialog.cards if c.c['type'] == 'value')
                self.assertIn('3.00', value_card.scalar.text())
                input_card = next(c for c in dialog.cards if c.c['type'] == 'input')
                input_card.field.setText('4'); input_card.mark_pending(); dialog.write_input(input_card)
                wait_for(lambda: not input_card.saving)
                self.assertEqual(dialog.state['variables']['flow']['count'], 4)
                event = dialog.state['monitor']['events'][0]; dialog.acknowledge(event, '本机闭环验证')
                wait_for(lambda: dialog.state['monitor']['events'][0].get('acknowledgedAt'))
                trend = next(c for c in dialog.cards if c.c['type'] == 'trend')
                self.assertGreaterEqual(len(trend.chart.samples), 1)
                self.assertFalse(errors, errors)
            finally:
                dialog.reject(); backend.shutdown(); wait_for(lambda: backend.process.processId() == 0)


if __name__ == '__main__': unittest.main()
