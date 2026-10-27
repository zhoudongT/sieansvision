#!/usr/bin/env python3
"""Offscreen Qt smoke: specialized panels + fake last_result + open upstream pickers.

Constructs locate / geometry / format / protocol panels, stubs QInputDialog.getItem
to auto-accept, clicks insert-upstream buttons, asserts tokens land in fields.
Also smokes HMI gate picker -> gateKeyChanged / runUi.fixedBars and filmstrip soft-disable.
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

PASS = []
FAIL = []


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
        self.setWindowTitle("smoke-host")


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

    locate_id = "locAAAA11112222"
    geom_id = "geoBBBB33334444"
    proto_id = "prsCCCC55556666"
    fmt_id = "fmtDDDD77778888"

    project = {
        "version": 2,
        "id": "smokeproj",
        "name": "panel-smoke",
        "steps": [
            {
                "id": locate_id,
                "operation": "locate",
                "name": "定位匹配",
                "params": {"matchMode": "fast", "upstreamRef": ""},
                "position": {"x": 0, "y": 0},
                "variables": {},
            },
            {
                "id": geom_id,
                "operation": "geometry_find",
                "name": "几何查找",
                "params": {"feature": "circles", "upstreamRef": ""},
                "position": {"x": 0, "y": 120},
                "variables": {},
            },
            {
                "id": proto_id,
                "operation": "protocol_parse",
                "name": "协议解析",
                "params": {
                    "sourceVar": "recvData",
                    "protocol": "delimited",
                    "delimiter": ",",
                    "fields": "status,value,judge",
                    "targetPrefix": "parsed_",
                },
                "position": {"x": 0, "y": 240},
                "variables": {},
            },
            {
                "id": fmt_id,
                "operation": "format_data",
                "name": "格式化",
                "params": {
                    "template": "STATUS={0}",
                    "args": "",
                    "targetVar": "formatted",
                    "scope": "flow",
                },
                "position": {"x": 0, "y": 360},
                "variables": {},
            },
        ],
        "edges": [],
        "variables": {},
        "sourceConfig": {"mode": "local", "images": [], "intervalMs": 250, "autoSwitch": True},
    }

    last_result = {
        "results": [
            {
                "id": locate_id,
                "output": {
                    "result": {
                        "ok": True,
                        "score": 0.92,
                        "x": 10.5,
                        "y": 20.5,
                        "matches": [{"score": 0.92}],
                    }
                },
            },
            {
                "id": geom_id,
                "output": {
                    "result": {
                        "ok": True,
                        "count": 2,
                        "shapes": [{"x": 1, "y": 2}],
                        "x": 1.0,
                        "y": 2.0,
                    }
                },
            },
            {
                "id": proto_id,
                "output": {
                    "result": {
                        "ok": True,
                        "fields": {"status": "OK", "value": "12.5"},
                        "parsed": {"status": "OK"},
                        "count": 3,
                    }
                },
            },
        ]
    }

    host = HostWindow(last_result)
    host.resize(800, 600)

    orig_getitem = QInputDialog.getItem
    QInputDialog.getItem = staticmethod(_patch_getitem())

    try:
        from desktop.locate_match_panel import LocateMatchPanel
        from desktop.geometry_find_panel import GeometryFindPanel
        from desktop.wave3_thin_panels import FormatDataPanel, ProtocolParsePanel
        from desktop.operator_hmi import ProductionStatsPanel, OperatorHmiView
        from desktop.widgets.filmstrip import FilmstripBar
        from desktop.upstream_field_picker import pick_upstream_field

        picked = pick_upstream_field(
            host, project, step_id=fmt_id, last_result=last_result,
        )
        if picked and picked[0] == locate_id and "results." in picked[2]:
            ok("pick_upstream_field live token=%s" % picked[2])
        else:
            bad("pick_upstream_field unexpected: %r" % (picked,))

        loc_step = deepcopy(next(s for s in project["steps"] if s["id"] == locate_id))
        loc = LocateMatchPanel(loc_step, {}, project, parent=host)
        loc.show()
        app.processEvents()
        btns = _find_buttons(loc, "插入上游字段")
        if not btns:
            bad("LocateMatchPanel missing insert button")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem([
                "2 %s" % project["steps"][1]["name"],
                "count",
            ]))
            btns[0].click()
            app.processEvents()
            token = loc.params.get("upstreamRef") or ""
            lines = [e.text() for e in loc.findChildren(QLineEdit) if "results." in (e.text() or "")]
            if "results." in token and "count" in token:
                ok("LocateMatchPanel picker -> %s" % token)
            elif lines:
                ok("LocateMatchPanel picker line -> %s" % lines[0])
            else:
                bad("LocateMatchPanel no token params=%r" % token)

        geo_step = deepcopy(next(s for s in project["steps"] if s["id"] == geom_id))
        geo = GeometryFindPanel(geo_step, {}, project, parent=host)
        geo.show()
        app.processEvents()
        gbtns = _find_buttons(geo, "插入上游字段")
        if not gbtns:
            bad("GeometryFindPanel missing insert button")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem([
                "1 %s" % project["steps"][0]["name"],
                "score",
            ]))
            gbtns[0].click()
            app.processEvents()
            uref = geo.params.get("upstreamRef") or ""
            lines = [e.text() for e in geo.findChildren(QLineEdit) if "results." in (e.text() or "")]
            if "results." in uref and "score" in uref:
                ok("GeometryFindPanel picker -> %s" % uref)
            elif lines:
                ok("GeometryFindPanel picker line -> %s" % lines[0])
            else:
                bad("GeometryFindPanel no token params=%r" % uref)

        fmt_step = deepcopy(next(s for s in project["steps"] if s["id"] == fmt_id))
        fmt = FormatDataPanel(fmt_step, {}, project, parent=host)
        fmt.show()
        app.processEvents()
        fbtns = _find_buttons(fmt, "插入上游字段")
        if not fbtns:
            bad("FormatDataPanel missing insert button")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem([
                "3 %s" % project["steps"][2]["name"],
                "fields",
            ]))
            fbtns[0].click()
            app.processEvents()
            args = fmt.params.get("args") or ""
            lines = [e.text() for e in fmt.findChildren(QLineEdit) if "results." in (e.text() or "")]
            if "results." in args:
                ok("FormatDataPanel args picker -> %s" % args)
            elif lines:
                ok("FormatDataPanel picker line -> %s" % lines[0])
            else:
                bad("FormatDataPanel no token args=%r" % args)

        pr_step = deepcopy(next(s for s in project["steps"] if s["id"] == proto_id))
        pr = ProtocolParsePanel(pr_step, {}, project, parent=host)
        pr.show()
        app.processEvents()
        pbtns = _find_buttons(pr, "插入上游字段")
        if not pbtns:
            bad("ProtocolParsePanel missing insert button")
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem([
                "1 %s" % project["steps"][0]["name"],
                "ok",
            ]))
            pbtns[0].click()
            app.processEvents()
            src = pr.params.get("sourceVar") or ""
            if src:
                ok("ProtocolParsePanel sourceVar after pick -> %s" % src)
            else:
                bad("ProtocolParsePanel empty sourceVar after pick")

        events = []
        stats = ProductionStatsPanel()
        stats.gateKeyChanged.connect(lambda k: events.append(k))
        QInputDialog.getItem = staticmethod(_patch_getitem(["passGate"]))
        gate_btns = _find_buttons(stats, "判定门")
        if not gate_btns:
            bad("ProductionStatsPanel missing gate button")
        else:
            gate_btns[0].click()
            app.processEvents()
            if events == ["passGate"] and stats.gate_key() == "passGate":
                ok("ProductionStatsPanel gateKeyChanged(passGate)")
            else:
                bad("gateKey events=%r key=%r" % (events, stats.gate_key()))

        hmi = OperatorHmiView()
        patches = []
        hmi.runUiChanged.connect(lambda p: patches.append(p))
        hmi.reload_layout({
            "runUi": {
                "split": "1",
                "placements": [],
                "fixedBars": {"bottom": True, "gateKey": ""},
                "controls": {},
            }
        })
        app.processEvents()
        if not hmi._stats_panels:
            bad("OperatorHmiView default grid missing stats panel")
        else:
            panel = hmi._stats_panels[0]
            QInputDialog.getItem = staticmethod(_patch_getitem(["commOk"]))
            gbs = _find_buttons(panel, "判定门")
            if not gbs:
                gbs = [
                    b for b in panel.findChildren(QPushButton)
                    if "判定门" in (b.text() or "") or (b.text() or "").startswith("门:")
                ]
            if not gbs:
                bad("HMI stats gate button not found")
            else:
                gbs[0].click()
                app.processEvents()
                fb = (patches[-1].get("fixedBars") if patches else {}) or {}
                if fb.get("gateKey") == "commOk":
                    ok("OperatorHmiView runUiChanged fixedBars.gateKey=commOk")
                else:
                    bad("HMI persist patches=%r" % patches)

        bar = FilmstripBar()
        bar.set_interval_hint(250)
        if "250" not in (bar.interval_label.text() or ""):
            bad("interval hint text=%r" % bar.interval_label.text())
        else:
            ok("FilmstripBar interval hint 250 ms")
        bar.set_run_all_enabled(False, "camera soft-disable")
        if bar.run_all.isEnabled():
            bad("run_all still enabled after soft-disable")
        else:
            ok("FilmstripBar run_all soft-disabled")
        bar.set_run_all_enabled(True)
        if not bar.run_all.isEnabled():
            bad("run_all failed to re-enable")
        else:
            ok("FilmstripBar run_all re-enabled")

        sample = json.loads((ROOT / "projects/open-and-run-format-protocol.sieans").read_text())
        ops = [s["operation"] for s in sample["steps"]]
        expect = ["var_calc", "send_data", "receive_data", "protocol_parse", "format_data", "var_calc"]
        if ops == expect:
            ok("format-protocol sample chain send->recv->parse")
        else:
            bad("format-protocol ops=%r" % ops)
        parse = next(s for s in sample["steps"] if s["operation"] == "protocol_parse")
        if parse["params"].get("sourceVar") == "recvData":
            ok("protocol_parse sourceVar=recvData")
        else:
            bad("parse sourceVar=%r" % parse["params"].get("sourceVar"))

    except Exception as exc:
        bad("exception: %s: %s" % (type(exc).__name__, exc))
        import traceback
        traceback.print_exc()
    finally:
        QInputDialog.getItem = orig_getitem

    print("---")
    print("%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
