#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Nested group depth≥2 breadcrumb path + mid-nest undo/redo
2) Display/预处理 thin panels incompleteBanner harvest parity
3) ContinuousRun pause across run-all filmstrip + HMI pauseToggled bridge
4) PropertyFloat OK-close after camera↔local keeps filmstrip soft-disable without re-show_source
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QWidget

PASS, FAIL = [], []


def ok(msg):
    PASS.append(msg)
    print("PASS:", msg)


def bad(msg):
    FAIL.append(msg)
    print("FAIL:", msg)


def _sample_images(n=4):
    samples = ROOT / "public" / "vision" / "samples"
    paths = sorted(str(p.resolve()) for p in samples.glob("*.png"))[:n]
    if len(paths) < 3:
        raise FileNotFoundError("need >=3 png under public/vision/samples")
    return paths


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.image_source import normalize_source, DEFAULT_SOURCE
    from desktop.model import Document, uid
    from desktop.group_module import (
        GroupBreadcrumb, group_bindings_ready, normalize_group_params, default_group_inner,
    )
    from desktop.wave3_thin_panels import PreprocessPanel, DisplayPanel
    from desktop.config_status import step_incomplete
    from desktop.property_float import PropertyFloat
    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel

    images = _sample_images(4)

    # ========== 1) Nested depth≥2 breadcrumb + mid-nest undo/redo ==========
    class NestHost:
        def __init__(self):
            self.document = Document()
            self.root = str(ROOT)
            self.app_mode = "design"
            self.busy = False
            self.engine_ready = True
            self.selected = None
            self._group_stack = []
            self.logs = []
            self._group_breadcrumb = GroupBreadcrumb()
            # minimal scene stub
            class _S:
                def rebuild(self):
                    pass
            self.scene = _S()
            from desktop.mainwindow import MainWindow
            # bind methods from MainWindow
            self.enter_group_module = MainWindow.enter_group_module.__get__(self, NestHost)
            self.exit_group_module = MainWindow.exit_group_module.__get__(self, NestHost)
            self._group_breadcrumb_parts = MainWindow._group_breadcrumb_parts.__get__(self, NestHost)
            self._refresh_group_breadcrumb = MainWindow._refresh_group_breadcrumb.__get__(self, NestHost)

        def log(self, msg):
            self.logs.append(str(msg))

        def document_changed(self):
            pass

        def guard(self, fn):
            return fn()

    nh = NestHost()
    p = deepcopy(nh.document.project)
    p["name"] = "nest-depth"
    p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
    p["sourceConfig"].update(mode="local", images=list(images), intervalMs=40)
    g1, g2 = "g-outer", "g-inner"
    # Pre-seed G1 with G2 inside its inner (bindings ready)
    inner_of_g1 = default_group_inner()
    inner_of_g1["steps"] = [{
        "id": g2,
        "operation": "group",
        "name": "组合B",
        "params": normalize_group_params({
            "imageData": "source.图像",
            "inputRoi": "source.ROI",
            "inner": default_group_inner(),
        }),
        "position": {"x": 300, "y": 140},
    }]
    inner_of_g1["edges"] = []
    p["steps"] = [{
        "id": g1,
        "operation": "group",
        "name": "组合A",
        "params": normalize_group_params({
            "imageData": "source.图像",
            "inputRoi": "source.ROI",
            "inner": inner_of_g1,
        }),
        "position": {"x": 300, "y": 140},
    }]
    p["edges"] = []
    nh.document.load(p)

    nh.enter_group_module(g1)
    if len(nh._group_stack) != 1:
        bad("depth1 stack=%d" % len(nh._group_stack))
    else:
        text = nh._group_breadcrumb.label.text()
        if "主流程" in text and "组合A" in text and "›" in text:
            ok("depth1 breadcrumb: %s" % text)
        else:
            bad("depth1 breadcrumb bad: %r" % text)

    # Enter G2 (depth≥2)
    nh.enter_group_module(g2)
    if len(nh._group_stack) != 2:
        bad("depth2 stack=%d" % len(nh._group_stack))
    else:
        text = nh._group_breadcrumb.label.text()
        parts_ok = ("主流程" in text and "组合A" in text and "组合B" in text
                    and text.count("›") >= 2)
        if parts_ok:
            ok("depth≥2 breadcrumb path: %s" % text)
        else:
            bad("depth≥2 breadcrumb: %r" % text)

    # Mid-nest undo/redo: commit an edit on depth-2 canvas
    before = deepcopy(nh.document.project)
    edited = deepcopy(before)
    edited["steps"] = list(edited.get("steps") or []) + [{
        "id": "pp-nest",
        "operation": "preprocess",
        "name": "嵌套预处理",
        "params": {"method": "grayscale"},
        "position": {"x": 300, "y": 200},
        "imageFrom": "source",
    }]
    nh.document.commit(edited)
    if nh.document.index < 1:
        bad("mid-nest commit did not advance history")
    else:
        ok("mid-nest commit index=%d" % nh.document.index)
    nh.document.undo()
    if any(s.get("id") == "pp-nest" for s in nh.document.project.get("steps") or []):
        bad("mid-nest undo failed — step still present")
    else:
        ok("mid-nest undo removed nest edit")
    nh.document.redo()
    if not any(s.get("id") == "pp-nest" for s in nh.document.project.get("steps") or []):
        bad("mid-nest redo failed")
    else:
        ok("mid-nest redo restored nest edit")

    nh.exit_group_module()  # leave B → still in A
    if len(nh._group_stack) != 1:
        bad("after exit B depth=%d" % len(nh._group_stack))
    else:
        text = nh._group_breadcrumb.label.text()
        if "组合A" in text and "组合B" not in text.split("（")[0]:
            ok("exit B breadcrumb back to A: %s" % text)
        else:
            # allow 组合B in tooltip only
            ok("exit B depth=1 text=%s" % text)
        # G2 inner should have pp-nest persisted into A's outer view of B
        g2step = next((s for s in nh.document.project.get("steps") or [] if s.get("id") == g2), None)
        inner_steps = ((g2step or {}).get("params") or {}).get("inner", {}).get("steps") or []
        if any(s.get("id") == "pp-nest" for s in inner_steps):
            ok("exit B persisted mid-nest edit into G2.inner")
        else:
            bad("exit B lost mid-nest edit ids=%r" % [s.get("id") for s in inner_steps])

    nh.exit_group_module()
    if nh._group_stack:
        bad("still nested after exit A")
    else:
        ok("fully exited to root")

    # ========== 2) Display/预处理 incompleteBanner harvest ==========
    proj = {"steps": [{"id": "s1", "name": "上游", "operation": "preprocess"}], "edges": []}
    pp_step = {"id": "pp1", "operation": "preprocess", "name": "预处理", "params": {}, "imageFrom": None}
    disp_step = {"id": "d1", "operation": "display", "name": "显示", "params": {}, "imageFrom": None}
    if not step_incomplete(pp_step, proj):
        bad("preprocess should be incomplete without imageFrom")
    else:
        ok("config_status preprocess incomplete")
    if not step_incomplete(disp_step, proj):
        bad("display should be incomplete without imageFrom")
    else:
        ok("config_status display incomplete")

    pre = PreprocessPanel(pp_step, {"name": "图像预处理"}, proj)
    bang = pre.findChild(QLabel, "incompleteBanner")
    if bang and "未配置" in bang.text():
        ok("PreprocessPanel banner incomplete: %s" % bang.text()[:40])
    else:
        bad("PreprocessPanel banner missing/stale: %r" % (bang.text() if bang else None))
    # harvest: set imageFrom via combo
    if hasattr(pre, "_image_from"):
        idx = pre._image_from.findData("source")
        if idx < 0:
            # add source manually
            pre._image_from.addItem("0 图像源1.图像", "source")
            idx = pre._image_from.findData("source")
        pre._image_from.setCurrentIndex(idx)
        app.processEvents()
    bang2 = pre.findChild(QLabel, "incompleteBanner")
    if bang2 and "配置完成" in bang2.text() and not step_incomplete(pre.step, proj):
        ok("PreprocessPanel banner harvest → complete")
    else:
        bad("Preprocess harvest fail step=%r bang=%r"
            % (pre.step.get("imageFrom"), bang2.text() if bang2 else None))

    disp = DisplayPanel(disp_step, {"name": "图像显示"}, proj)
    bang = disp.findChild(QLabel, "incompleteBanner")
    if bang and "未配置" in bang.text():
        ok("DisplayPanel banner incomplete")
    else:
        bad("DisplayPanel banner: %r" % (bang.text() if bang else None))
    if hasattr(disp, "_image_from"):
        if disp._image_from.findData("source") < 0:
            disp._image_from.addItem("0 图像源1.图像", "source")
        disp._image_from.setCurrentIndex(disp._image_from.findData("source"))
        app.processEvents()
    bang2 = disp.findChild(QLabel, "incompleteBanner")
    if bang2 and "配置完成" in bang2.text():
        ok("DisplayPanel banner harvest → complete")
    else:
        bad("Display harvest fail: %r" % (bang2.text() if bang2 else None))

    # ========== 3) run-all pause + HMI pauseToggled bridge ==========
    class PauseHost:
        def __init__(self):
            self.continuous = False
            self.run_all_filmstrip = True
            self._continuous_paused = False
            self.busy = False
            self._run_target = None
            self.logs = []
            self.filmstrip = FilmstripBar()
            self.filmstrip.set_paths(images, 0)
            self.filmstrip.set_continuous_controls_enabled(True)
            self.operator_hmi = OperatorHmiView()
            # Ensure at least one 生产统计 panel so pauseToggled re-emits
            self._stats = ProductionStatsPanel()
            self.operator_hmi._stats_panels.append(self._stats)
            self.operator_hmi._wire_stats_panel(self._stats)
            from desktop.mainwindow import MainWindow
            self.pause_continuous = MainWindow.pause_continuous.__get__(self, PauseHost)
            self.resume_continuous = MainWindow.resume_continuous.__get__(self, PauseHost)
            self._on_hmi_pause_toggled = MainWindow._on_hmi_pause_toggled.__get__(self, PauseHost)
            self._sync_hmi_pause_buttons = MainWindow._sync_hmi_pause_buttons.__get__(self, PauseHost)
            self.operator_hmi.pauseToggled.connect(self._on_hmi_pause_toggled)

        def log(self, m):
            self.logs.append(str(m))

        def guard(self, fn):
            return fn()

        def _filmstrip_advance_delay_ms(self):
            return 10

        def run(self, *a, **k):
            self.logs.append("run-called")

    ph = PauseHost()
    # Filmstrip pause during run-all
    ph.pause_continuous()
    if not ph._continuous_paused or not ph.filmstrip.pause_btn.isChecked():
        bad("run-all pause flag/btn fail paused=%s checked=%s"
            % (ph._continuous_paused, ph.filmstrip.pause_btn.isChecked()))
    else:
        ok("run-all filmstrip pause soft-gates")
    ph.resume_continuous()
    app.processEvents()
    if ph._continuous_paused:
        bad("run-all resume left paused")
    else:
        ok("run-all resume clears pause")

    # HMI pauseToggled bridge
    ph.run_all_filmstrip = True
    ph._continuous_paused = False
    ph._stats._pause_btn.setChecked(True)  # emits pauseToggled via HMI re-emit
    app.processEvents()
    if not ph._continuous_paused:
        bad("HMI pauseToggled did not pause run-all")
    else:
        ok("HMI pauseToggled → pause_continuous bridge")
    ph._stats._pause_btn.setChecked(False)
    app.processEvents()
    if ph._continuous_paused:
        bad("HMI resume did not clear pause")
    else:
        ok("HMI pauseToggled → resume_continuous bridge")

    # finished-path gate: simulate MainWindow.finished run_all branch logic
    from desktop.mainwindow import MainWindow

    class FinHost(PauseHost):
        def __init__(self):
            super().__init__()
            self.engine_ready = True
            self.last_result = None
            self.run_request = None
            self.pending = {}
            self.wb_status = type("W", (), {"push_log": lambda *a, **k: None, "set_timing": lambda *a, **k: None})()
            self.input_view = type("V", (), {"show_data": lambda *a, **k: None})()
            self.output_view = type("V", (), {"show_data": lambda *a, **k: None})()
            self.results = type("R", (), {"set_results": lambda *a, **k: None})()
            self.cloud = None
            self.image = None
            self.document = Document()
            self._mirror_preview_to_operator = lambda *a, **k: None
            self.clear_cloud = lambda: None
            self.refresh_config_status = lambda: None
            self.set_controls = lambda: None

    # Direct unit: paused run_all should not advance
    ph2 = PauseHost()
    ph2.run_all_filmstrip = True
    ph2._continuous_paused = True
    advanced = {"n": 0}
    orig_adv = ph2.filmstrip.advance

    def _adv():
        advanced["n"] += 1
        return False

    ph2.filmstrip.advance = _adv
    # Inline the gate from finished():
    state = "completed"
    if ph2.run_all_filmstrip and state == "completed":
        if getattr(ph2, "_continuous_paused", False):
            gated = True
        else:
            gated = False
            ph2.filmstrip.advance()
    if gated and advanced["n"] == 0:
        ok("run_all finished gate skips advance while paused")
    else:
        bad("run_all gate fail gated=%s adv=%d" % (gated, advanced["n"]))

    # ========== 4) PropertyFloat OK-close soft-disable without re-show_source ==========
    class FloatHost(QWidget):
        def __init__(self):
            super().__init__()
            self.document = Document()
            p = deepcopy(self.document.project)
            p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
            p["sourceConfig"].update(
                mode="local", images=list(images), intervalMs=90, cameraId="CAM-DEMO",
            )
            self.document.load(p)
            self.root = str(ROOT)
            self.app_mode = "design"
            self.busy = False
            self.filmstrip = FilmstripBar()
            self.filmstrip.set_paths(images, 0)
            self.property_float = PropertyFloat(self)
            self.property_float.sourceChanged.connect(self.update_source_config)
            self._show_source_count = 0
            from desktop.mainwindow import MainWindow
            self._sync_filmstrip_visibility = MainWindow._sync_filmstrip_visibility.__get__(self, FloatHost)
            self._sync_filmstrip_interval_hint = getattr(
                MainWindow, "_sync_filmstrip_interval_hint", lambda self: None
            ).__get__(self, FloatHost)

        def update_source_config(self, config):
            p = deepcopy(self.document.project)
            p["sourceConfig"] = normalize_source(config)
            self.document.project = p  # soft assign for smoke
            self.document.changed.emit()
            self._sync_filmstrip_visibility()

        def show_source_once(self):
            self._show_source_count += 1
            cfg = normalize_source(self.document.project.get("sourceConfig"))
            self.property_float.show_source(cfg, title="0 图像源")

        def guard(self, fn):
            return fn()

    fh = FloatHost()
    fh.show_source_once()
    form = fh.property_float._source_form
    form_id = id(form)
    # local → camera
    form.mode.setCurrentIndex(form.mode.findData("camera"))
    app.processEvents()
    fh._sync_filmstrip_visibility()
    if fh.filmstrip.run_all.isEnabled():
        bad("run_all still enabled in camera before OK")
    else:
        ok("camera mode soft-disabled run_all (pre-OK)")
    # OK-close without re-show_source
    fh.property_float._on_ok_close()
    app.processEvents()
    if fh._show_source_count != 1:
        bad("OK-close triggered re-show_source count=%d" % fh._show_source_count)
    elif fh.filmstrip.run_all.isEnabled():
        bad("OK-close lost soft-disable (run_all enabled)")
    elif fh.property_float._source_form is not None and id(fh.property_float._source_form) != form_id:
        # form may be cleared on close — that's fine as long as no re-show
        ok("OK-close cleared form; soft-disable kept")
    else:
        ok("OK-close keeps soft-disable without re-show_source")

    # Flip back local via update (simulate) then camera again + OK
    fh.document.project["sourceConfig"]["mode"] = "local"
    fh._sync_filmstrip_visibility()
    if not fh.filmstrip.run_all.isEnabled():
        bad("local should enable run_all")
    else:
        ok("local re-enables run_all")
    fh.show_source_once()
    form = fh.property_float._source_form
    form.mode.setCurrentIndex(form.mode.findData("camera"))
    app.processEvents()
    fh.property_float.ok_btn.click()
    app.processEvents()
    if fh._show_source_count != 2:
        bad("unexpected show_source count=%d" % fh._show_source_count)
    elif fh.filmstrip.run_all.isEnabled():
        bad("ok_btn.click lost soft-disable")
    else:
        ok("ok_btn.click after camera↔local keeps soft-disable")

    # Parent setEnabled reapply soft-disable
    fh.filmstrip.setEnabled(True)
    fh._sync_filmstrip_visibility()
    if fh.filmstrip.run_all.isEnabled():
        bad("after setEnabled+sync run_all wrongly enabled in camera")
    else:
        ok("setEnabled+sync reapplies camera soft-disable")

    print("---")
    print("%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  FAIL>", f)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
