#!/usr/bin/env python3
"""Headless/offscreen E2E (t191/t192 NEXT):
1) Design↔run mode flip: HMI counters + filmstrip visibility + sourceConfig RT (no float reopen)
2) Group enter gate: ImageData/InputROI bind via ↑ then 进入组合模块 enable/disable
3) OutputImage imageFrom edge densify + incomplete banner ↔ config_status harvest
4) ContinuousRun/run-all: real QTimer.singleShot(_filmstrip_advance_delay_ms) vs paced loop
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
)

PASS, FAIL = [], []


def ok(msg):
    PASS.append(msg)
    print("PASS:", msg)


def bad(msg):
    FAIL.append(msg)
    print("FAIL:", msg)


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


def _sample_images(n=3):
    samples = ROOT / "public" / "vision" / "samples"
    paths = sorted(str(p.resolve()) for p in samples.glob("*.png"))[:n]
    if len(paths) < 2:
        raise FileNotFoundError("need >=2 png under public/vision/samples")
    return paths


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    orig_getitem = QInputDialog.getItem
    # Silence QMessageBox in group gate tests
    orig_warn = QMessageBox.warning
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    try:
        from desktop.operator_hmi import OperatorHmiView
        from desktop.image_source import normalize_source, DEFAULT_SOURCE
        from desktop.mainwindow import MainWindow
        from desktop.widgets.filmstrip import FilmstripBar
        from desktop.model import Document
        from desktop.group_module import GroupParamPanel, group_bindings_ready
        from desktop.wave3_thin_panels import OutputImagePanel
        from desktop.config_status import step_incomplete, node_needs_bang, project_incomplete_summary
        from desktop.property_float import PropertyFloat

        images = _sample_images(3)

        class _Wb:
            def log_param_change(self, *a, **k):
                return "audited"

            def push_log(self, *a, **k):
                pass

            def set_timing(self, *a, **k):
                pass

            def set_config(self, *a, **k):
                pass

        # ========== 1) Design↔run mode flip ==========
        class ModeHost:
            def __init__(self):
                self.document = Document()
                p = deepcopy(self.document.project)
                p["name"] = "mode-flip"
                p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
                p["sourceConfig"].update(
                    mode="local",
                    images=list(images),
                    intervalMs=70,
                    autoSwitch=True,
                    stopAtLast=True,
                    currentIndex=0,
                )
                p["runUi"] = {
                    "split": "1",
                    "placements": [],
                    "fixedBars": {"bottom": True, "gateKey": "passGate", "showCounters": True},
                    "controls": {},
                }
                p["steps"] = []
                p["edges"] = []
                self.document.load(p)
                self.busy = False
                self.app_mode = "design"
                self.root = ROOT
                self.image = ""
                self.last_result = None
                self.property_float = None
                self.filmstrip = FilmstripBar()
                self.filmstrip.show()
                self.wb_status = _Wb()
                self.logs = QPlainTextEdit()
                self.operator_hmi = OperatorHmiView()
                self.operator_hmi.reload_layout(self.document.project)
                # seed filmstrip from sourceConfig
                self.update_source_config(self.document.project["sourceConfig"])
                app.processEvents()

            def guard(self, fn):
                return fn()

            def log(self, msg):
                self.logs.appendPlainText(str(msg))

            def set_busy(self, busy):
                self.busy = busy

            def document_changed(self):
                pass

            def update_source_config(self, config):
                MainWindow.update_source_config(self, config)

            def _sync_filmstrip_visibility(self):
                MainWindow._sync_filmstrip_visibility(self)

            def _sync_filmstrip_interval_hint(self):
                MainWindow._sync_filmstrip_interval_hint(self)

            def set_app_mode(self, mode):
                MainWindow.set_app_mode(self, mode)

            def _filmstrip_advance_delay_ms(self):
                return MainWindow._filmstrip_advance_delay_ms(self)

            def _active_run_interval_ms(self):
                return 120

        mh = ModeHost()
        src0 = deepcopy(mh.document.project["sourceConfig"])
        if not (mh.app_mode == "design" and mh.filmstrip.isVisible() and mh.filmstrip.run_all.isEnabled()):
            bad("design initial filmstrip not visible/enabled")
        else:
            ok("design: filmstrip visible + run-all (local)")

        # Flip to run — filmstrip hides; HMI reloads; sourceConfig unchanged; no float needed
        mh.set_app_mode("run")
        app.processEvents()
        src_run = deepcopy(mh.document.project["sourceConfig"])
        if mh.app_mode != "run":
            bad("set_app_mode run failed")
        elif not mh.filmstrip.isHidden():
            bad("run mode filmstrip should hide")
        elif src_run.get("mode") != "local" or src_run.get("images") != images:
            bad("sourceConfig mutated on run flip: %r" % src_run)
        else:
            ok("run: filmstrip hidden; sourceConfig intact (no float)")

        # Tick HMI counters in run mode
        panels = mh.operator_hmi._stats_panels
        if not panels:
            bad("run HMI missing stats panels")
        else:
            for gate_val in (1, 1, 0):
                mh.operator_hmi.set_runtime(
                    {
                        "state": "completed",
                        "elapsedMs": 8,
                        "variables": {"flow": {"passGate": gate_val}},
                        "results": [],
                    }
                )
            app.processEvents()
            if panels[0]._ok == 2 and panels[0]._ng == 1:
                ok("run HMI counters tick OK=2 NG=1")
            else:
                bad("run counters ok=%s ng=%s" % (panels[0]._ok, panels[0]._ng))
            counter_snapshot = (panels[0]._ok, panels[0]._ng)

        # Flip back to design — filmstrip restores; sourceConfig round-trip; float not reopened
        mh.property_float = None  # ensure no float
        mh.set_app_mode("design")
        app.processEvents()
        src_des = deepcopy(mh.document.project["sourceConfig"])
        if mh.app_mode != "design":
            bad("back to design failed")
        elif mh.filmstrip.isHidden() or not mh.filmstrip.run_all.isEnabled():
            bad("design restore filmstrip wrong")
        elif src_des != src_run:
            bad("sourceConfig RT mismatch design vs run")
        elif mh.property_float is not None:
            bad("float reopened unexpectedly")
        else:
            ok("design↔run: filmstrip restore + sourceConfig RT without float reopen")

        # Mode→camera while design (no float), flip run/design — soft-disable persists correctly
        cfg = normalize_source(mh.document.project["sourceConfig"])
        cfg["mode"] = "camera"
        mh.update_source_config(cfg)
        app.processEvents()
        if not mh.filmstrip.isHidden():
            bad("design camera should hide filmstrip")
        else:
            mh.set_app_mode("run")
            app.processEvents()
            mh.set_app_mode("design")
            app.processEvents()
            still_cam = mh.document.project["sourceConfig"].get("mode") == "camera"
            hidden = mh.filmstrip.isHidden()
            if still_cam and hidden and not mh.filmstrip.run_all.isEnabled():
                ok("camera mode survives design↔run; filmstrip stays soft-disabled")
            else:
                bad("camera survive mode=%s hidden=%s en=%s"
                    % (mh.document.project["sourceConfig"].get("mode"), hidden,
                       mh.filmstrip.run_all.isEnabled()))
            # restore local for later tests
            cfg = normalize_source(mh.document.project["sourceConfig"])
            cfg.update(mode="local", images=list(images), intervalMs=70)
            mh.update_source_config(cfg)
            app.processEvents()

        # ========== 2) Group enter gate ==========
        loc_id = "locAAAA11112222"
        grp_id = "grpBBBB33334444"
        gproj = {
            "version": 2,
            "id": "grp-smoke",
            "name": "grp-smoke",
            "steps": [
                {"id": loc_id, "operation": "locate", "name": "定位", "params": {}, "position": {"x": 0, "y": 0}},
                {
                    "id": grp_id,
                    "operation": "group",
                    "name": "组合",
                    "params": {
                        "imageData": "",
                        "inputRoi": "",
                        "io": {"inputs": [{"name": "ImageData", "type": "IMAGE", "binding": ""},
                                          {"name": "InputROI", "type": "ROI", "binding": ""}],
                               "outputs": [], "display": {}},
                    },
                    "position": {"x": 0, "y": 80},
                },
            ],
            "edges": [],
        }
        last = {"results": [{"id": loc_id, "output": {"result": {"ok": True, "score": 0.9, "x": 1, "y": 2}}}]}

        class GHost(QApplication if False else __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget):
            pass

        from PySide6.QtWidgets import QWidget

        class HostW(QWidget):
            def __init__(self):
                super().__init__()
                self.last_result = last

        hostw = HostW()
        gstep = deepcopy(gproj["steps"][1])
        gp = GroupParamPanel(gstep, gproj, parent=hostw)
        gp.show()
        app.processEvents()
        entered = []
        gp.enterGroup.connect(lambda: entered.append(True))

        if not hasattr(gp, "enter_btn"):
            bad("GroupParamPanel missing enter_btn")
        elif gp.enter_btn.isEnabled():
            bad("enter should be disabled with empty binds")
        else:
            ok("Group enter disabled when ImageData/InputROI empty")

        # Bind ImageData/InputROI via ↑ on inputs table rows (not outputs ↑)
        gp.tabs.setCurrentIndex(0)
        app.processEvents()
        hostw.show()
        app.processEvents()

        def _input_up_buttons(panel):
            tbl = panel._inputs_table
            out = []
            for r in range(tbl.rowCount()):
                cell = tbl.cellWidget(r, 3)
                if not cell:
                    continue
                for b in cell.findChildren(QPushButton):
                    if (b.text() or "") == "↑":
                        out.append(b)
                        break
            return out

        ups = _input_up_buttons(gp)
        if len(ups) < 2:
            bad("Group inputs ↑ buttons missing count=%d" % len(ups))
        else:
            QInputDialog.getItem = staticmethod(_patch_getitem(["1 定位", "ok"]))
            ups[0].click()
            app.processEvents()
            # still disabled — need both
            if gp.enter_btn.isEnabled():
                bad("enter enabled after only ImageData")
            else:
                ok("enter still disabled after ImageData-only bind")

            QInputDialog.getItem = staticmethod(_patch_getitem(["1 定位", "score"]))
            ups[1].click()
            app.processEvents()
            gp._emit()
            app.processEvents()
            if gp.enter_btn.isEnabled() and group_bindings_ready(gp.params):
                ok("enter enabled after ImageData+InputROI ↑ binds")
            else:
                bad("enter en=%s ready=%s img=%r roi=%r params=%r"
                    % (gp.enter_btn.isEnabled(), group_bindings_ready(gp.params),
                       gp.image_data.text(), gp.input_roi.text(),
                       (gp.params.get("imageData"), gp.params.get("inputRoi"))))

            entered.clear()
            gp.enter_btn.click()
            app.processEvents()
            if entered:
                ok("enterGroup emitted when bindings ready")
            else:
                bad("enterGroup not emitted")

            # Clear ROI → disable again
            gp.input_roi.setText("")
            app.processEvents()
            gp._emit()
            if not gp.enter_btn.isEnabled():
                ok("enter disabled again after clearing InputROI")
            else:
                bad("enter still enabled after clear ROI")

        # ========== 3) OutputImage imageFrom + incomplete banner + config_status ==========
        oimg_id = "oimCCCC55556666"
        oproj = {
            "version": 2,
            "id": "oimg-smoke",
            "name": "oimg-smoke",
            "steps": [
                {"id": loc_id, "operation": "locate", "name": "定位", "params": {}, "position": {"x": 0, "y": 0}},
                {
                    "id": oimg_id,
                    "operation": "output_image",
                    "name": "输出图像",
                    "params": {"path": "", "format": "png"},
                    "position": {"x": 0, "y": 80},
                    "imageFrom": None,
                },
            ],
            "edges": [{"from": "source", "to": oimg_id}],
        }
        # incomplete: no imageFrom, no path
        if not step_incomplete(oproj["steps"][1], oproj):
            bad("config_status should bang empty output_image")
        else:
            ok("config_status harvest: empty output_image incomplete")

        op = OutputImagePanel(deepcopy(oproj["steps"][1]), {}, oproj, parent=hostw)
        op.show()
        app.processEvents()
        banner = getattr(op, "_incomplete_banner", None)
        if banner is None or "未配置完整" not in (banner.text() or ""):
            bad("OutputImage incomplete banner missing/text=%r" % (banner.text() if banner else None))
        else:
            ok("OutputImage incomplete banner shown: %s" % banner.text()[:40])

        # Edge densify: source should be in combo
        combo = op._image_from
        src_idx = combo.findData("source")
        loc_idx = combo.findData(loc_id)
        if src_idx < 0:
            bad("imageFrom combo missing edge source")
        else:
            ok("OutputImage imageFrom edge densify lists source")
        if loc_idx < 0:
            bad("imageFrom soft densify missing locate")
        else:
            ok("OutputImage soft densify lists locate（可选）")

        # Select source + set path → banner complete + config_status clear
        combo.setCurrentIndex(src_idx)
        app.processEvents()
        op._path_edit.setText("/tmp/sieans-oimg-out")
        app.processEvents()
        # commit path via editingFinished semantics
        op._set_param("path", "/tmp/sieans-oimg-out")
        app.processEvents()
        bang = step_incomplete(op.step, oproj)
        banner_ok = "配置完成" in (op._incomplete_banner.text() or "")
        if not bang and banner_ok and op.step.get("imageFrom") == "source":
            ok("OutputImage complete: imageFrom=source + path; banner+config_status green")
        else:
            bad("complete check bang=%s banner=%r imageFrom=%r path=%r"
                % (bang, op._incomplete_banner.text(), op.step.get("imageFrom"), op.params.get("path")))

        # Clear path → bang again
        op._path_edit.setText("")
        op._set_param("path", "")
        app.processEvents()
        if step_incomplete(op.step, oproj) and "保存路径" in (op._incomplete_banner.text() or ""):
            ok("OutputImage path clear → banner+config_status bang again")
        else:
            bad("path clear bang failed banner=%r" % op._incomplete_banner.text())

        # project_incomplete_summary harvest includes oimg when incomplete
        oproj2 = deepcopy(oproj)
        oproj2["steps"][1]["imageFrom"] = None
        oproj2["steps"][1]["params"]["path"] = ""
        oproj2["sourceConfig"] = {"mode": "local", "images": images}
        _ok_flag, _msg, bad_ids = project_incomplete_summary(oproj2)
        if oimg_id in bad_ids:
            ok("project_incomplete_summary harvest includes output_image id")
        else:
            bad("summary bad_ids=%r" % bad_ids)

        # ========== 4) Real QTimer.singleShot filmstrip advance path ==========
        class TimerHost:
            """Mirrors MainWindow.finished run_all_filmstrip branch with real QTimer."""

            def __init__(self):
                self.document = Document()
                p = deepcopy(self.document.project)
                p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
                p["sourceConfig"].update(
                    mode="local", images=list(images), intervalMs=60, autoSwitch=True, stopAtLast=True
                )
                self.document.load(p)
                self.busy = False
                self.app_mode = "design"
                self.root = ROOT
                self.continuous = False
                self.run_all_filmstrip = False
                self._run_target = None
                self.filmstrip = FilmstripBar()
                self.filmstrip.set_paths(images, 0, root=ROOT)
                self.filmstrip.set_auto_switch(True)
                self.filmstrip.set_stop_at_last(True)
                self.filmstrip.set_run_all_enabled(True)
                self.wb_status = _Wb()
                self.logs = QPlainTextEdit()
                self.run_stamps = []
                self.done = False

            def guard(self, fn):
                return fn()

            def log(self, msg):
                self.logs.appendPlainText(str(msg))

            def _filmstrip_advance_delay_ms(self):
                return MainWindow._filmstrip_advance_delay_ms(self)

            def _active_run_interval_ms(self):
                return 120

            def run(self, target=None):
                self.run_stamps.append(time.monotonic())
                # Simulate engine completed quickly → finished() run_all branch
                self._simulate_finished_completed()

            def _simulate_finished_completed(self):
                """Exact MainWindow.finished run_all_filmstrip / continuous advance path."""
                state = "completed"
                if self.run_all_filmstrip and state == "completed":
                    if self.filmstrip.advance():
                        QTimer.singleShot(
                            self._filmstrip_advance_delay_ms(),
                            lambda: self.guard(self.run),
                        )
                    else:
                        self.run_all_filmstrip = False
                        self.done = True
                        self.log("运行全部完成")
                    return
                if self.continuous and state == "completed":
                    cfg = normalize_source(self.document.project.get("sourceConfig"))
                    target = self._run_target
                    if cfg.get("mode") == "local" and self.filmstrip.auto_switch.isChecked() and not target:
                        if self.filmstrip.advance():
                            QTimer.singleShot(
                                self._filmstrip_advance_delay_ms(),
                                lambda: self.guard(lambda: self.run(None)),
                            )
                            return
                        if cfg.get("stopAtLast"):
                            self.continuous = False
                            self._run_target = None
                            self.done = True
                            self.log("已到最后一张，连续运行停止")
                            return

            def start_run_all(self):
                self.continuous = False
                self.run_all_filmstrip = True
                self.done = False
                self.run_stamps.clear()
                self.filmstrip.thumbs.setCurrentRow(0)
                self.guard(self.run)

            def start_continuous(self):
                self.continuous = True
                self.run_all_filmstrip = False
                self._run_target = None
                self.done = False
                self.run_stamps.clear()
                self.filmstrip.thumbs.setCurrentRow(0)
                self.guard(self.run)

        th = TimerHost()
        delay = th._filmstrip_advance_delay_ms()
        if delay != 60:
            bad("timer host delay_ms=%s expected 60" % delay)
        else:
            ok("QTimer path delay_ms=60 from sourceConfig.intervalMs")

        th.start_run_all()
        # Pump Qt event loop until done or timeout
        deadline = time.monotonic() + 5.0
        while not th.done and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        if not th.done:
            bad("run_all QTimer path did not finish")
        elif len(th.run_stamps) != len(images):
            bad("run_all stamps=%d expected %d" % (len(th.run_stamps), len(images)))
        else:
            gaps = [th.run_stamps[i + 1] - th.run_stamps[i] for i in range(len(th.run_stamps) - 1)]
            if all(g >= (delay / 1000.0) * 0.65 for g in gaps):
                ok(
                    "real QTimer.singleShot run-all paced gaps≈%s ms (delay=%s)"
                    % ([int(g * 1000) for g in gaps], delay)
                )
            else:
                bad("QTimer gaps too short: %s delay=%s" % ([int(g * 1000) for g in gaps], delay))

        # Continuous + stopAtLast via same real QTimer path
        th2 = TimerHost()
        th2.start_continuous()
        deadline = time.monotonic() + 5.0
        while not th2.done and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        if th2.done and len(th2.run_stamps) == len(images) and not th2.continuous:
            gaps2 = [th2.run_stamps[i + 1] - th2.run_stamps[i] for i in range(len(th2.run_stamps) - 1)]
            ok(
                "real QTimer ContinuousRun stopAtLast stamps=%d gaps≈%s ms"
                % (len(th2.run_stamps), [int(g * 1000) for g in gaps2])
            )
        else:
            bad(
                "continuous QTimer done=%s stamps=%d cont=%s"
                % (th2.done, len(th2.run_stamps), th2.continuous)
            )

    except Exception as exc:
        import traceback

        traceback.print_exc()
        bad("exception: %s: %s" % (type(exc).__name__, exc))
    finally:
        QInputDialog.getItem = orig_getitem
        QMessageBox.warning = orig_warn

    print("---")
    print("%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
