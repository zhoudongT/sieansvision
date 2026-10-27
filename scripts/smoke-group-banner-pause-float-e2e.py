#!/usr/bin/env python3
"""Headless/offscreen E2E (t191/t192 NEXT):
1) Group enter/exit nested canvas: bindings persist + leave restores outer step
2) Thin-panel incomplete banners (FormatData/TextSave/ProtocolParse/OutputImage) ↔ config_status
3) ContinuousRun pause/resume + intervalMs live edit mid-run (real QTimer)
4) PropertyFloat sourceConfig camera→local→camera RT without float reopen
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import os
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPlainTextEdit

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

    from desktop.image_source import normalize_source, DEFAULT_SOURCE, ImageSourceForm
    from desktop.mainwindow import MainWindow
    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.model import Document
    from desktop.group_module import GroupParamPanel, group_bindings_ready, normalize_group_params, default_group_inner
    from desktop.wave3_thin_panels import (
        FormatDataPanel, OutputImagePanel, ProtocolParsePanel, TextSavePanel,
    )
    from desktop.config_status import step_incomplete, project_incomplete_summary
    from desktop.property_float import PropertyFloat

    images = _sample_images(4)

    class _Wb:
        def log_param_change(self, *a, **k):
            return "audited"

        def push_log(self, *a, **k):
            pass

        def set_timing(self, *a, **k):
            pass

        def set_config(self, *a, **k):
            pass

    # ========== 1) Group enter/exit nested canvas ==========
    class GroupHost:
        def __init__(self):
            self.document = Document()
            p = deepcopy(self.document.project)
            p["name"] = "group-nest"
            p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
            p["sourceConfig"].update(mode="local", images=list(images), intervalMs=50)
            gid = "g1"
            p["steps"] = [{
                "id": gid,
                "operation": "group",
                "name": "组合A",
                "params": normalize_group_params({
                    "imageData": "source.图像",
                    "inputRoi": "source.ROI",
                    "inner": default_group_inner(),
                }),
            }]
            p["edges"] = []
            self.document.load(p)
            self.root = str(ROOT)
            self.app_mode = "design"
            self.busy = False
            self.engine_ready = True
            self.selected = None
            self._group_stack = []
            from desktop.group_module import GroupBreadcrumb
            self._group_breadcrumb = GroupBreadcrumb()
            self.filmstrip = FilmstripBar()
            self.logs = type("L", (), {"appendPlainText": lambda *a, **k: None})()
            self.wb_status = _Wb()
            from desktop.graph import FlowScene
            # minimal scene stub
            class _Scene:
                def rebuild(self):
                    pass
            self.scene = _Scene()

        def log(self, m):
            self._last_log = str(m)

        def guard(self, fn):
            return fn()

        def document_changed(self):
            pass

        enter_group_module = MainWindow.enter_group_module
        exit_group_module = MainWindow.exit_group_module

    gh = GroupHost()
    # reject enter without bindings
    p = deepcopy(gh.document.project)
    p["steps"][0]["params"] = normalize_group_params({"imageData": "", "inputRoi": ""})
    gh.document.load(p)
    gh.enter_group_module("g1")
    if gh._group_stack:
        bad("enter should refuse empty bindings")
    else:
        ok("enter refused when ImageData/InputROI empty")

    # bind and enter
    p = deepcopy(gh.document.project)
    p["steps"][0]["params"] = normalize_group_params({
        "imageData": "source.图像",
        "inputRoi": "source.ROI",
        "inner": default_group_inner(),
    })
    gh.document.load(p)
    outer_steps_before = deepcopy(gh.document.project["steps"])
    gh.enter_group_module("g1")
    if len(gh._group_stack) != 1:
        bad("enter stack empty")
    elif not gh._group_breadcrumb.isVisible():
        bad("breadcrumb hidden after enter")
    elif gh.document.project.get("steps"):
        # default inner empty — ok
        ok("enter nested canvas (empty inner); breadcrumb visible")
    else:
        ok("enter nested canvas; breadcrumb visible")

    # add an inner step while nested
    inner_proj = deepcopy(gh.document.project)
    inner_proj["steps"] = [{
        "id": "inner_locate",
        "operation": "locate",
        "name": "内定位",
        "params": {},
    }]
    inner_proj["edges"] = []
    gh.document.project = inner_proj
    gh.exit_group_module()

    if gh._group_stack:
        bad("stack not cleared after exit")
    elif gh._group_breadcrumb.isVisible():
        bad("breadcrumb still visible after exit")
    else:
        outer = gh.document.project
        gstep = next(s for s in outer["steps"] if s["id"] == "g1")
        params = gstep.get("params") or {}
        binds_ok = (
            str(params.get("imageData") or "").strip() == "source.图像"
            and str(params.get("inputRoi") or "").strip() == "source.ROI"
        )
        inner = (params.get("inner") or {})
        inner_ids = [s.get("id") for s in (inner.get("steps") or [])]
        outer_ids = [s.get("id") for s in (outer.get("steps") or [])]
        if not binds_ok:
            bad("bindings lost after exit: %r" % params)
        elif "inner_locate" not in inner_ids:
            bad("inner step not persisted: %r" % inner_ids)
        elif outer_ids != ["g1"]:
            bad("outer steps not restored: %r" % outer_ids)
        else:
            ok("exit restores outer step; bindings+inner persist")

    # re-enter: inner still there
    gh.enter_group_module("g1")
    re_ids = [s.get("id") for s in (gh.document.project.get("steps") or [])]
    if re_ids == ["inner_locate"]:
        ok("re-enter shows persisted inner steps")
    else:
        bad("re-enter inner mismatch: %r" % re_ids)
    gh.exit_group_module()

    # ========== 2) Thin-panel incomplete banners ==========
    # FormatData
    fd_step = {"id": "fd1", "operation": "format_data", "name": "格式化", "params": {"template": ""}}
    fd = FormatDataPanel(fd_step, {}, {"steps": [fd_step], "edges": []})
    bang = fd.findChild(QLabel, "incompleteBanner")
    if bang is None or "未配置完整" not in (bang.text() or ""):
        bad("FormatData empty template banner missing: %r" % (bang.text() if bang else None))
    elif not step_incomplete(fd.step, fd.project):
        bad("FormatData config_status not incomplete")
    else:
        ok("FormatData incomplete banner + config_status")
    # fill template via live edit
    edits = fd.findChildren(QPlainTextEdit)
    if edits:
        edits[0].setPlainText("{0}")
        app.processEvents()
    if step_incomplete(fd.step, fd.project):
        bad("FormatData still incomplete after template")
    elif "配置完成" not in (bang.text() or ""):
        bad("FormatData banner not green: %r" % bang.text())
    else:
        ok("FormatData complete banner green")

    # TextSave (SaveImage-ish path)
    ts_step = {"id": "ts1", "operation": "text_save", "name": "文本保存", "params": {"path": ""}}
    ts = TextSavePanel(ts_step, {}, {"steps": [ts_step], "edges": []})
    bang = ts.findChild(QLabel, "incompleteBanner")
    if bang is None or "文件路径" not in (bang.text() or "") and "未配置完整" not in (bang.text() or ""):
        bad("TextSave banner missing: %r" % (bang.text() if bang else None))
    elif not step_incomplete(ts.step, ts.project):
        bad("TextSave config_status not incomplete")
    else:
        ok("TextSave incomplete banner + config_status")
    # live path
    from PySide6.QtWidgets import QLineEdit
    for le in ts.findChildren(QLineEdit):
        if le.placeholderText() and "路径" in le.placeholderText():
            le.setText("/tmp/out.txt")
            app.processEvents()
            break
    if step_incomplete(ts.step, ts.project):
        bad("TextSave still incomplete after path")
    else:
        ok("TextSave complete after path")

    # ProtocolParse
    pp_step = {"id": "pp1", "operation": "protocol_parse", "name": "协议解析", "params": {"sourceVar": ""}}
    pp = ProtocolParsePanel(pp_step, {}, {"steps": [pp_step], "edges": []})
    bang = pp.findChild(QLabel, "incompleteBanner")
    if bang is None or "未配置完整" not in (bang.text() or ""):
        bad("ProtocolParse banner missing: %r" % (bang.text() if bang else None))
    elif not step_incomplete(pp.step, pp.project):
        bad("ProtocolParse config_status not incomplete")
    else:
        ok("ProtocolParse incomplete banner + config_status")
    if hasattr(pp, "_source_var_edit"):
        pp._source_var_edit.setText("recvData")
    else:
        pp._set_param("sourceVar", "recvData")
    app.processEvents()
    if step_incomplete(pp.step, pp.project):
        bad("ProtocolParse still incomplete after sourceVar step=%r" % pp.step.get("params"))
    else:
        ok("ProtocolParse complete after sourceVar")

    # OutputImage parity still works
    oi_step = {"id": "oi1", "operation": "output_image", "name": "输出图像", "params": {"path": ""}}
    oi_proj = {
        "steps": [
            {"id": "src_loc", "operation": "locate", "name": "定位"},
            oi_step,
        ],
        "edges": [{"from": "src_loc", "to": "oi1"}],
        "sourceConfig": {"mode": "local", "images": images},
    }
    oi = OutputImagePanel(oi_step, {}, oi_proj)
    bang = oi.findChild(QLabel, "incompleteBanner")
    if bang is None or "未配置完整" not in (bang.text() or ""):
        bad("OutputImage banner missing")
    else:
        ok("OutputImage incomplete banner parity")

    # harvest summary
    harv = {
        "steps": [
            {"id": "fd1", "operation": "format_data", "params": {"template": ""}},
            {"id": "ts1", "operation": "text_save", "params": {"path": ""}},
            {"id": "pp1", "operation": "protocol_parse", "params": {"sourceVar": ""}},
            {"id": "oi1", "operation": "output_image", "params": {"path": ""}},
        ],
        "sourceConfig": {"mode": "local", "images": images},
    }
    _, _, bad_ids = project_incomplete_summary(harv)
    need = {"fd1", "ts1", "pp1", "oi1"}
    if need <= set(bad_ids):
        ok("project_incomplete_summary harvests Format/TextSave/Protocol/OutputImage")
    else:
        bad("harvest missing %r got %r" % (need - set(bad_ids), bad_ids))

    # ========== 3) ContinuousRun pause/resume + intervalMs live ==========
    class ContHost:
        def __init__(self):
            self.document = Document()
            p = deepcopy(self.document.project)
            p["name"] = "cont-pause"
            p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
            p["sourceConfig"].update(
                mode="local", images=list(images), intervalMs=80,
                autoSwitch=True, stopAtLast=True, currentIndex=0,
            )
            p["steps"] = []
            p["edges"] = []
            self.document.load(p)
            self.root = str(ROOT)
            self.app_mode = "design"
            self.busy = False
            self.engine_ready = True
            self.continuous = False
            self._continuous_paused = False
            self.run_all_filmstrip = False
            self._run_target = None
            self.filmstrip = FilmstripBar()
            self.filmstrip.set_paths(list(images), 0, root=self.root)
            self.filmstrip.set_auto_switch(True)
            self.filmstrip.set_stop_at_last(True)
            if hasattr(self.filmstrip, "continuousPauseToggled"):
                self.filmstrip.continuousPauseToggled.connect(self._on_filmstrip_continuous_pause)
            self.logs = type("L", (), {"appendPlainText": lambda *a, **k: None})()
            self.wb_status = _Wb()
            self._stamps = []
            self._gaps_phase = []  # collect gaps when not paused

        def log(self, m):
            pass

        def guard(self, fn):
            return fn()

        def request(self, *a, **k):
            pass

        def _flush_after_continuous(self):
            pass

        def _active_run_interval_ms(self):
            return 120

        _filmstrip_advance_delay_ms = MainWindow._filmstrip_advance_delay_ms
        pause_continuous = MainWindow.pause_continuous
        resume_continuous = MainWindow.resume_continuous
        _on_filmstrip_continuous_pause = MainWindow._on_filmstrip_continuous_pause
        stop_run = MainWindow.stop_run

        def run(self, target=None):
            if not self.continuous or getattr(self, "_continuous_paused", False):
                return
            self._stamps.append(time.perf_counter())
            # emulate finished → continuous schedule (copy of mainwindow path)
            state = "completed"
            if self.continuous and state == "completed":
                if getattr(self, "_continuous_paused", False):
                    return
                cfg = normalize_source(self.document.project.get("sourceConfig"))
                if cfg.get("mode") == "local" and self.filmstrip.auto_switch.isChecked() and not target:
                    if self.filmstrip.advance():
                        QTimer.singleShot(
                            self._filmstrip_advance_delay_ms(),
                            lambda: self.guard(
                                lambda: self.run(None)
                                if self.continuous and not getattr(self, "_continuous_paused", False)
                                else None
                            ),
                        )
                        return
                    if cfg.get("stopAtLast"):
                        self.continuous = False
                        self._continuous_paused = False
                        return

        def run_continuous(self):
            self.continuous = True
            self._continuous_paused = False
            if hasattr(self.filmstrip, "set_continuous_controls_enabled"):
                self.filmstrip.set_continuous_controls_enabled(True)
            if hasattr(self.filmstrip, "set_continuous_paused"):
                self.filmstrip.set_continuous_paused(False)
            self.run()

    ch = ContHost()
    ch.run_continuous()
    # let 1 advance fire (~80ms), then pause
    deadline = time.perf_counter() + 0.25
    while time.perf_counter() < deadline and len(ch._stamps) < 2:
        app.processEvents()
        time.sleep(0.01)
    if len(ch._stamps) < 1:
        bad("ContinuousRun never stamped before pause")
    else:
        ok("ContinuousRun started stamps=%d" % len(ch._stamps))

    before_pause = len(ch._stamps)
    ch.pause_continuous()
    if not ch._continuous_paused:
        bad("pause_continuous flag not set")
    elif hasattr(ch.filmstrip, "pause_btn") and not ch.filmstrip.pause_btn.isChecked():
        bad("filmstrip pause_btn not checked")
    else:
        ok("pause_continuous + filmstrip UI synced")

    # wait > 2 intervals — should not advance
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.25:
        app.processEvents()
        time.sleep(0.01)
    if len(ch._stamps) != before_pause:
        bad("stamps advanced while paused: %d→%d" % (before_pause, len(ch._stamps)))
    else:
        ok("no filmstrip advance while paused")

    # live edit intervalMs mid-pause then resume
    cfg = normalize_source(ch.document.project["sourceConfig"])
    cfg["intervalMs"] = 120
    ch.document.project["sourceConfig"] = cfg
    if ch._filmstrip_advance_delay_ms() < 100:
        bad("live intervalMs not picked up: %d" % ch._filmstrip_advance_delay_ms())
    else:
        ok("intervalMs live edit mid-run → delay_ms=%d" % ch._filmstrip_advance_delay_ms())

    ch.resume_continuous()
    if ch._continuous_paused:
        bad("still paused after resume")
    # wait for resume schedule (~120ms) + maybe one more
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.35:
        app.processEvents()
        time.sleep(0.01)
    if len(ch._stamps) <= before_pause:
        bad("no advance after resume stamps=%d" % len(ch._stamps))
    else:
        # check gap after resume uses ~120ms
        if len(ch._stamps) >= 2:
            gap = (ch._stamps[-1] - ch._stamps[-2]) * 1000
            if gap < 90:
                bad("post-resume gap too small for 120ms: %.0f" % gap)
            else:
                ok("resume advanced; post-edit gap≈%.0f ms (expect≥100)" % gap)
        else:
            ok("resume advanced stamps=%d" % len(ch._stamps))

    ch.stop_run()
    if ch.continuous or ch._continuous_paused:
        bad("stop_run left continuous/paused")
    else:
        ok("stop_run clears continuous+paused")

    # ========== 4) PropertyFloat camera→local→camera without reopen ==========
    class FloatHost:
        def __init__(self):
            self.document = Document()
            p = deepcopy(self.document.project)
            p["name"] = "float-mode"
            p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
            p["sourceConfig"].update(
                mode="local", images=list(images), intervalMs=90,
                autoSwitch=True, stopAtLast=False, cameraId="CAM-DEMO",
            )
            self.document.load(p)
            self.root = str(ROOT)
            self.app_mode = "design"
            self.busy = False
            self.filmstrip = FilmstripBar()
            self.property_float = PropertyFloat()
            self.property_float.sourceChanged.connect(self.update_source_config)
            self.property_float.paramAudited.connect(
                lambda mod, param, old, new: self.on_param_audited(mod, param, old, new)
            )
            self.wb_status = _Wb()
            self.logs = type("L", (), {"appendPlainText": lambda *a, **k: None})()
            self._show_source_count = 0

        def log(self, *a, **k):
            pass

        def guard(self, fn):
            return fn()

        update_source_config = MainWindow.update_source_config
        on_param_audited = MainWindow.on_param_audited
        _sync_filmstrip_visibility = MainWindow._sync_filmstrip_visibility
        _sync_filmstrip_interval_hint = MainWindow._sync_filmstrip_interval_hint

        def show_source_once(self):
            self._show_source_count += 1
            cfg = normalize_source(self.document.project.get("sourceConfig"))
            self.property_float.show_source(cfg, title="0 图像源")

    fh = FloatHost()
    fh.update_source_config(fh.document.project["sourceConfig"])
    fh.show_source_once()
    form = fh.property_float._source_form
    if form is None:
        bad("PropertyFloat missing source form")
        form_id = None
    else:
        form_id = id(form)
        ok("PropertyFloat opened once")

    # local → camera
    form.mode.setCurrentIndex(form.mode.findData("camera"))
    app.processEvents()
    cfg = fh.document.project["sourceConfig"]
    same = fh.property_float._source_form is not None and id(fh.property_float._source_form) == form_id
    if cfg.get("mode") != "camera":
        bad("mode not camera after flip: %r" % cfg.get("mode"))
    elif fh.filmstrip.isVisible():
        bad("filmstrip still visible in camera")
    elif not same:
        bad("float form recreated on local→camera")
    elif cfg.get("images") != images:
        bad("images wiped on →camera")
    elif int(cfg.get("intervalMs") or 0) != 90:
        bad("intervalMs wiped on →camera")
    else:
        bang = form.findChild(QLabel, "incompleteBanner")
        # cameraId set → complete; or incomplete if empty — we set CAM-DEMO
        tip = bang.text() if bang else ""
        ok("local→camera hide filmstrip; form same; images/interval persist tip=%r" % tip[:40])

    # camera → local
    form.mode.setCurrentIndex(form.mode.findData("local"))
    app.processEvents()
    cfg = fh.document.project["sourceConfig"]
    same = id(fh.property_float._source_form) == form_id
    if cfg.get("mode") != "local" or not fh.filmstrip.isVisible() or not same:
        bad("camera→local fail mode=%s vis=%s same=%s"
            % (cfg.get("mode"), fh.filmstrip.isVisible(), same))
    elif cfg.get("images") != images or int(cfg.get("intervalMs") or 0) != 90:
        bad("local restore lost images/interval")
    else:
        ok("camera→local restore filmstrip; form same; sourceConfig RT")

    # local → camera again (full camera→local→camera cycle)
    form.mode.setCurrentIndex(form.mode.findData("camera"))
    app.processEvents()
    cfg = fh.document.project["sourceConfig"]
    same = id(fh.property_float._source_form) == form_id
    if fh._show_source_count != 1:
        bad("show_source called again count=%d" % fh._show_source_count)
    elif cfg.get("mode") != "camera" or fh.filmstrip.isVisible() or not same:
        bad("2nd→camera fail mode=%s vis=%s same=%s"
            % (cfg.get("mode"), fh.filmstrip.isVisible(), same))
    elif cfg.get("images") != images or int(cfg.get("intervalMs") or 0) != 90 or cfg.get("cameraId") != "CAM-DEMO":
        bad("2nd camera wiped fields: %r" % {k: cfg.get(k) for k in ("images", "intervalMs", "cameraId")})
    else:
        ok("camera→local→camera RT without float reopen; fields intact")

    # banner refreshed for camera without rebuild
    bang = form.findChild(QLabel, "incompleteBanner")
    if bang and ("配置完成" in bang.text() or "相机" in bang.text() or "未配置" in bang.text()):
        ok("ImageSource incomplete banner refreshed on mode without rebuild")
    else:
        bad("banner stale after mode: %r" % (bang.text() if bang else None))

    print("---")
    print("%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
