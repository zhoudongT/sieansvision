"""Native pointer gestures must create edges rather than move graph nodes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import unittest
from PySide6.QtCore import Qt,QPoint,QPointF,QMimeData,QCoreApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDragEnterEvent,QDropEvent
from PySide6.QtTest import QTest
from desktop.model import Document
from desktop.catalog import CORE
from desktop.graph import FlowScene,FlowView

app=QApplication.instance() or QApplication([])


class NativeGraphGestures(unittest.TestCase):
    def setUp(self):
        self.doc=Document();project=deepcopy(self.doc.project);project['sourcePosition']={'x':80,'y':20};self.doc.commit(project)
        self.a=self.doc.add(CORE[0],{'x':80,'y':160});self.b=self.doc.add(CORE[1],{'x':80,'y':360})
        self.scene=FlowScene(self.doc);self.view=FlowView(self.scene);self.view.resize(800,650);self.view.show();self.view.fit();app.processEvents()
        self.notices=[];self.scene.notice.connect(self.notices.append)

    def tearDown(self):self.view.close();self.scene.deleteLater();app.processEvents()

    def port(self,node,side):return self.view.mapFromScene(self.scene.nodes[node].ports[side].scenePos())

    def drag(self,origin,target):
        QTest.mousePress(self.view.viewport(),Qt.MouseButton.LeftButton,pos=origin)
        for i in range(1,7):QTest.mouseMove(self.view.viewport(),origin+(target-origin)*i/6,10)
        QTest.mouseRelease(self.view.viewport(),Qt.MouseButton.LeftButton,pos=target);app.processEvents()

    def test_bottom_to_top_drag_connects_without_moving_nodes_and_undo_works(self):
        positions=[deepcopy(s['position']) for s in self.doc.project['steps']]
        self.drag(self.port(self.a,'bottom'),self.port(self.b,'top'))
        self.assertEqual(len(self.doc.project['edges']),1)
        edge=self.doc.project['edges'][0];self.assertEqual((edge['from'],edge['to'],edge['fromPort'],edge['toPort']),(self.a,self.b,'bottom','top'))
        self.assertEqual([s['position'] for s in self.doc.project['steps']],positions)
        self.assertEqual(self.doc.project['steps'][1]['imageFrom'],self.a)
        self.doc.undo();self.assertEqual(self.doc.project['edges'],[])
        self.doc.redo();self.assertEqual(len(self.doc.project['edges']),1)

    def test_input_to_output_drag_and_left_right_ports(self):
        self.drag(self.port(self.b,'top'),self.port(self.a,'bottom'))
        self.assertEqual(len(self.doc.project['edges']),1)
        self.doc.undo();self.drag(self.port(self.a,'right'),self.port(self.b,'left'))
        edge=self.doc.project['edges'][0];self.assertEqual((edge['fromPort'],edge['toPort']),('right','left'))

    def test_source_can_branch_to_multiple_inputs_and_rebuild_cancels_preview(self):
        self.drag(self.port('source','bottom'),self.port(self.a,'top'))
        self.drag(self.port('source','right'),self.port(self.b,'left'))
        self.assertEqual(len(self.doc.project['edges']),2)
        self.assertTrue(all(e['from']=='source' for e in self.doc.project['edges']))
        QTest.mouseClick(self.view.viewport(),Qt.MouseButton.LeftButton,pos=self.port(self.a,'bottom'))
        self.assertIsNotNone(self.scene.link_preview)
        self.doc.undo();self.assertIsNone(self.scene.link);self.assertIsNone(self.scene.link_preview)

    def test_click_connection_preview_escape_and_empty_drop(self):
        QTest.mouseClick(self.view.viewport(),Qt.MouseButton.LeftButton,pos=self.port(self.a,'bottom'))
        QTest.mouseMove(self.view.viewport(),self.port(self.b,'top'),10)
        self.assertIsNotNone(self.scene.link_preview)
        QTest.mouseClick(self.view.viewport(),Qt.MouseButton.LeftButton,pos=self.port(self.b,'top'));app.processEvents()
        self.assertEqual(len(self.doc.project['edges']),1);self.assertIsNone(self.scene.link_preview)
        self.doc.undo();origin=self.port(self.a,'bottom')
        QTest.mouseClick(self.view.viewport(),Qt.MouseButton.LeftButton,pos=origin)
        QTest.keyClick(self.view,Qt.Key.Key_Escape);self.assertIsNone(self.scene.link);self.assertIsNone(self.scene.link_preview)
        self.drag(origin,QPoint(700,550));self.assertEqual(self.doc.project['edges'],[]);self.assertIsNone(self.scene.link_preview)

    def test_duplicates_cycles_and_same_kind_ports_are_rejected_atomically(self):
        self.drag(self.port(self.a,'bottom'),self.port(self.b,'top'));before=deepcopy(self.doc.project)
        self.drag(self.port(self.a,'right'),self.port(self.b,'left'));self.assertEqual(self.doc.project,before)
        self.drag(self.port(self.b,'bottom'),self.port(self.a,'top'));self.assertEqual(self.doc.project,before)
        self.assertTrue(any(('循环' in message or '订阅线序' in message) for message in self.notices))
        self.drag(self.port(self.a,'bottom'),self.port(self.b,'bottom'));self.assertEqual(self.doc.project,before)

    def test_ports_remain_easy_to_hit_when_zoomed_out_and_nodes_still_move(self):
        self.view.resetTransform();self.view.scale(.55,.55);self.view.centerOn(200,250)
        self.drag(self.port(self.a,'bottom')+QPoint(6,0),self.port(self.b,'top')+QPoint(6,0))
        self.assertEqual(len(self.doc.project['edges']),1)
        origin=self.view.mapFromScene(self.scene.nodes[self.a].scenePos()+QPointF(70,24))
        self.drag(origin,origin+QPoint(55,0));app.processEvents()
        self.assertGreater(self.doc.project['steps'][0]['position']['x'],80)

    def test_dragging_one_node_does_not_teleport_sibling(self):
        """Two operators: move A; B scene+viewport stay put (no sceneRect jump)."""
        # Place B away from A; record both scene and viewport positions.
        self.scene.nodes[self.b].setPos(280, 360)
        self.scene.save_positions(); app.processEvents()
        nb = self.scene.nodes[self.b]
        b_scene = QPointF(nb.pos())
        b_vp = self.view.mapFromScene(nb.scenePos())
        na = self.scene.nodes[self.a]
        # Drag A toward the canvas top (the path that used to grow sceneRect).
        origin = self.view.mapFromScene(na.scenePos() + QPointF(70, 14))
        self.drag(origin, origin + QPoint(40, -180)); app.processEvents()
        nb = self.scene.nodes[self.b]
        self.assertEqual(nb.pos(), b_scene)
        self.assertEqual(self.view.mapFromScene(nb.scenePos()), b_vp)
        # Dragged node itself still moved, and may sit above y=0 (4f55066).
        self.assertNotEqual(self.scene.nodes[self.a].pos(), QPointF(80, 160))
        self.assertLessEqual(self.scene.nodes[self.a].y(), 160)

    def test_toolbox_mime_drop_creates_operator_node(self):
        """算子库 MIME drop on FlowView must emit key+position for add_node."""
        got=[]
        self.view.dropped.connect(lambda key,pos: got.append((key,dict(pos))))
        mime=QMimeData();mime.setData('application/x-sieans-operator',b'preprocess')
        pos=self.view.viewport().rect().center()
        enter=QDragEnterEvent(pos,Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.assertTrue(QCoreApplication.sendEvent(self.view.viewport(),enter));self.assertTrue(enter.isAccepted())
        drop=QDropEvent(pos,Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.assertTrue(QCoreApplication.sendEvent(self.view.viewport(),drop));self.assertTrue(drop.isAccepted())
        self.assertEqual(len(got),1);self.assertEqual(got[0][0],'preprocess')
        self.assertIn('x',got[0][1]);self.assertIn('y',got[0][1])


if __name__=='__main__':unittest.main()
