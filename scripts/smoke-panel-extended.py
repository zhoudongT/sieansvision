#!/usr/bin/env python3
"""Extended offscreen smoke: measure/nine/condition/data_io pickers + harvest;
camera↔local filmstrip soft-disable; HMI gateKey project JSON round-trip.
Exit 0 on PASS. No robot SDK.
"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QPushButton, QWidget

PASS, FAIL = [], []


def ok(msg):
    PASS.append(msg)
    print("PASS:", msg)


def bad(msg):
    FAIL.append(msg)
    print("FAIL:", msg)


class HostWindow(QWidget):
    def __init__(self, last_result):
        super().__init__()
        self.last_result = last_result


def _patch_getitem(choices_queue=None):
    queue = list(choices_queue or [])

    def _fake(parent, title, label, items, current=0, editable=False, *a, **kw):
        items = list(items or [])
        if not items:
            return "", False
        if queue:
            pick = queue.pop(0)
            if isinstance(pick, int):
                choice = items[pick] if 0 <= pick < len(items) else items[0]
            else:
                choice = pick if pick in items else items[0]
        else:
            choice = items[current] if 0 <= current < len(items) else items[0]
        return choice, True

    return _fake


def _find_buttons(root, text):
    return [b for b in root.findChildren(QPushButton) if text in (b.text() or "")]


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    loc_id = "locAAAA11112222"
    meas_id = "meaBBBB33334444"
    nine_id = "ninCCCC55556666"
    cond_id = "cndDDDD77778888"
    recv_id = "rcvEEEE99990000"
    send_id = "sndFFFF11112222"

    project = {
        "version": 2,
        "id": "ext-smoke",
        "name": "ext-smoke",
        "steps": [
            {"id": loc_id, "operation": "locate", "name": "定位", "params": {}, "position": {"x": 0, "y": 0}, "variables": {}},
            {"id": meas_id, "operation": "point_distance", "name": "点距", "params": {}, "position": {"x": 0, "y": 80}, "variables": {}},
            {"id": nine_id, "operation": "nine_point", "name": "九点", "params": {}, "position": {"x": 0, "y": 160}, "variables": {}},
            {"id": cond_id, "operation": "condition", "name": "条件", "params": {"rules": [{"enabled": True, "left": "", "comparison": "eq", "right": ""}]}, "position": {"x": 0, "y": 240}, "variables": {}},
            {"id": recv_id, "operation": "receive_data", "name": "接收", "params": {"device": "LocalLoop", "targetVar": "recvData"}, "position": {"x": 0, "y": 320}, "variables": {}},
            {"id": send_id, "operation": "send_data", "name": "发送", "params": {"device": "LocalLoop", "sourceMode": "variable", "sourceVar": ""}, "position": {"x": 0, "y": 400}, "variables": {}},
        ],
        "edges": [],
        "variables": {},
        "commManager": {"devices": [{"name": "LocalLoop", "protocol": "Local Bus", "enabled": True}]},
        "sourceConfig": {"mode": "local", "images": [], "intervalMs": 200, "autoSwitch": True, "stopAtLast": False},
    }

    last_result = {
        "results": [
            {"id": loc_id, "output": {"result": {"ok": True, "score": 0.88, "x": 1, "y": 2}}},
            {"id": meas_id, "output": {"result": {"ok": True, "value": 12.3, "distance": 12.3}}},
            {"id": nine_id, "output": {"result": {"ok": True, "matrix": [1, 0, 0, 1], "rms": 0.01}}},
            {"id": recv_id, "output": {"result": {"ok": True, "payload": "OK,1,PASS", "bytes": 10}}},
        ]
    }

    host = HostWindow(last_result)
    orig = QInputDialog.getItem
    QInputDialog.getItem = staticmethod(_patch_getitem())

    try:
        from desktop.measure_geom_panel import MeasureGeomPanel
        from desktop.nine_point_panel import NinePointPanel
        from desktop.condition_branch_panel import ConditionBranchPanel
        from desktop.data_io_panel import DataIoPanel
        from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
        from desktop.widgets.filmstrip import FilmstripBar
        from desktop.image_source import normalize_source, DEFAULT_SOURCE
        from desktop.mainwindow import MainWindow

        # --- measure ---
        mstep = deepcopy(next(s for s in project["steps"] if s["id"] == meas_id))
        mp = MeasureGeomPanel(mstep, {}, project, parent=host)
        mp.show(); app.processEvents()
        mbtns = _find_buttons(mp, "插入上游字段")
        if not mbtns:
            bad("MeasureGeomPanel missing insert")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem([
                "1 定位", "score",
            ]))
            mbtns[0].click(); app.processEvents()
            lines = [e.text() for e in mp.findChildren(QLineEdit) if "results." in (e.text() or "")]
            toks = [v for v in (mp.params or {}).values() if isinstance(v, str) and "results." in v]
            if lines or toks:
                ok("MeasureGeomPanel picker -> %s" % ((lines or toks)[0],))
            else:
                bad("MeasureGeomPanel no token after pick")

        # --- nine ---
        nstep = deepcopy(next(s for s in project["steps"] if s["id"] == nine_id))
        npanel = NinePointPanel(nstep, {}, project, parent=host)
        npanel.show(); app.processEvents()
        nbtns = _find_buttons(npanel, "插入上游字段")
        if not nbtns:
            bad("NinePointPanel missing insert")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem(["1 定位", "x"]))
            nbtns[0].click(); app.processEvents()
            uref = (npanel.params.get("upstreamRef") or "")
            lines = [e.text() for e in npanel.findChildren(QLineEdit) if "results." in (e.text() or "")]
            if "results." in uref or lines:
                ok("NinePointPanel picker -> %s" % (uref or lines[0],))
            else:
                bad("NinePointPanel no token")

        # --- condition harvest through wrap ---
        cstep = deepcopy(next(s for s in project["steps"] if s["id"] == cond_id))
        cp = ConditionBranchPanel(cstep, {}, project, parent=host)
        cp.show(); app.processEvents()
        # click ↑ on left wrap
        up_btns = [b for b in cp.findChildren(QPushButton) if (b.text() or "") == "↑"]
        if len(up_btns) < 1:
            bad("ConditionBranchPanel missing ↑ pickers")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem(["1 定位", "score"]))
            up_btns[0].click(); app.processEvents()
            rules = cp.params.get("rules") or []
            left = (rules[0].get("left") if rules else "") or ""
            if isinstance(left, str) and "results." in left and "score" in left:
                ok("Condition harvest through wrap left=%s" % left)
            else:
                bad("Condition harvest left=%r rules=%r" % (left, rules))

        # --- data_io receive + send ---
        rstep = deepcopy(next(s for s in project["steps"] if s["id"] == recv_id))
        rp = DataIoPanel(rstep, {}, project, parent=host)
        rp.show(); app.processEvents()
        rbtns = _find_buttons(rp, "插入上游字段")
        if not rbtns:
            bad("DataIoPanel(receive) missing insert")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem(["1 定位", "ok"]))
            rbtns[0].click(); app.processEvents()
            tv = rp.params.get("targetVar") or ""
            lines = [e.text() for e in rp.findChildren(QLineEdit) if "results." in (e.text() or "")]
            if "results." in tv or lines:
                ok("DataIoPanel(receive) picker -> %s" % (tv if "results." in tv else lines[0],))
            else:
                bad("DataIoPanel(receive) no token tv=%r" % tv)

        sstep = deepcopy(next(s for s in project["steps"] if s["id"] == send_id))
        sp = DataIoPanel(sstep, {}, project, parent=host)
        sp.show(); app.processEvents()
        sbtns = _find_buttons(sp, "插入上游字段")
        if not sbtns:
            bad("DataIoPanel(send) missing insert")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem(["4 接收", "payload"]))
            sbtns[0].click(); app.processEvents()
            sv = sp.params.get("sourceVar") or ""
            lines = [e.text() for e in sp.findChildren(QLineEdit) if "results." in (e.text() or "")]
            if "results." in sv or lines:
                ok("DataIoPanel(send) picker -> %s" % (sv if "results." in sv else lines[0],))
            else:
                bad("DataIoPanel(send) no token sv=%r" % sv)

        # --- camera ↔ local filmstrip ---
        class FakeDoc:
            def __init__(self):
                self.project = {"sourceConfig": deepcopy(DEFAULT_SOURCE)}

            def commit(self, p):
                self.project = p

        class Fake:
            def __init__(self):
                self.document = FakeDoc()
                self.filmstrip = FilmstripBar()
                self.app_mode = "design"
                self.busy = False

            def _sync_filmstrip_visibility(self):
                MainWindow._sync_filmstrip_visibility(self)

        fake = Fake()
        cfg = normalize_source(fake.document.project["sourceConfig"])
        cfg.update(mode="local", intervalMs=333, autoSwitch=True, stopAtLast=False)
        fake.document.project["sourceConfig"] = cfg
        fake._sync_filmstrip_visibility()
        if not (fake.filmstrip.isVisible() and fake.filmstrip.run_all.isEnabled() and "333" in fake.filmstrip.interval_label.text()):
            bad("local filmstrip state wrong")
        else:
            ok("camera-ux local interval+run-all")

        cfg = normalize_source(fake.document.project["sourceConfig"])
        cfg.update(mode="camera", intervalMs=500, autoSwitch=False)
        fake.document.project["sourceConfig"] = cfg
        fake._sync_filmstrip_visibility()
        if fake.filmstrip.isVisible() or fake.filmstrip.run_all.isEnabled():
            bad("camera should hide + soft-disable run-all")
        elif "500" not in fake.filmstrip.interval_label.text():
            bad("camera interval not synced while hidden")
        elif fake.filmstrip.auto_switch.isChecked():
            bad("camera autoSwitch not restored to False")
        else:
            ok("camera-ux soft-disable + interval/auto-switch synced")

        cfg = normalize_source(fake.document.project["sourceConfig"])
        cfg.update(mode="local", intervalMs=100, autoSwitch=True)
        fake.document.project["sourceConfig"] = cfg
        fake._sync_filmstrip_visibility()
        if fake.filmstrip.isVisible() and fake.filmstrip.run_all.isEnabled() and "100" in fake.filmstrip.interval_label.text() and fake.filmstrip.auto_switch.isChecked():
            ok("camera-ux restore local")
        else:
            bad("restore local failed")

        # --- gateKey persist round-trip into project JSON ---
        proj = {
            "version": 2,
            "id": "gate-rt",
            "name": "gate-rt",
            "steps": [],
            "edges": [],
            "runUi": {
                "split": "1",
                "placements": [],
                "fixedBars": {"bottom": True, "gateKey": "passGate"},
                "controls": {},
            },
        }
        hmi = OperatorHmiView()
        patches = []
        hmi.runUiChanged.connect(lambda p: patches.append(p))
        hmi.reload_layout(proj)
        app.processEvents()
        # initial apply should set panel gate without notify loop
        if hmi._stats_panels and hmi._stats_panels[0].gate_key() == "passGate":
            ok("gateKey applied from runUi.fixedBars")
        else:
            bad("gateKey not applied from fixedBars")

        panel = hmi._stats_panels[0]
        QInputDialog.getItem = staticmethod(_patch_getitem(["commOk"]))
        gbs = [b for b in panel.findChildren(QPushButton)
               if "判定门" in (b.text() or "") or (b.text() or "").startswith("门:")]
        if not gbs:
            bad("gate button missing on HMI stats")
        else:
            gbs[0].click(); app.processEvents()
            fb = (patches[-1].get("fixedBars") if patches else {}) or {}
            if fb.get("gateKey") != "commOk":
                bad("runUiChanged gateKey=%r" % fb.get("gateKey"))
            else:
                # simulate MainWindow commit into project JSON
                proj2 = deepcopy(proj)
                proj2["runUi"]["fixedBars"] = dict(fb)
                raw = json.dumps(proj2, ensure_ascii=False)
                roundtrip = json.loads(raw)
                gk = ((roundtrip.get("runUi") or {}).get("fixedBars") or {}).get("gateKey")
                if gk == "commOk":
                    ok("gateKey persist round-trip JSON gateKey=commOk")
                else:
                    bad("JSON round-trip gateKey=%r" % gk)
                # reload fresh HMI from persisted project
                hmi2 = OperatorHmiView()
                hmi2.reload_layout(roundtrip)
                app.processEvents()
                if hmi2._stats_panels and hmi2._stats_panels[0].gate_key() == "commOk":
                    ok("gateKey reload from persisted project")
                else:
                    bad("reload gate=%r" % (hmi2._stats_panels[0].gate_key() if hmi2._stats_panels else None))

    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad("exception: %s: %s" % (type(exc).__name__, exc))
    finally:
        QInputDialog.getItem = orig

    print("---")
    print("%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
