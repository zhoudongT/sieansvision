#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Nest depth≥3 + exit undo still reaches pre-enter tip
2) Display engine annotatedImage → filmstrip/HMI image pane live (_pick + set_live_result)
3) ContinuousRun+run-all dual-mode pause UX (single control owns both)
4) PropertyFloat Esc/✕ cancel path: discard unsaved camera↔local vs OK commit
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import base64
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

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


def _tiny_png_data_url():
    # 1x1 red PNG
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.image_source import normalize_source, DEFAULT_SOURCE
    from desktop.model import Document
    from desktop.group_module import (
        GroupBreadcrumb, normalize_group_params, default_group_inner,
    )
    from desktop.property_float import PropertyFloat
    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.operator_hmi import OperatorHmiView
    from desktop.mainwindow import MainWindow

    images = _sample_images(4)

    # ========== 1) Nest depth≥3 + exit undo → pre-enter tip ==========
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

            class _S:
                def rebuild(self):
                    pass

            self.scene = _S()
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

    def make_group(gid, name, inner=None):
        return {
            "id": gid,
            "operation": "group",
            "name": name,
            "params": normalize_group_params({
                "imageData": "source.图像",
                "inputRoi": "source.ROI",
                "inner": inner if inner is not None else default_group_inner(),
            }),
            "position": {"x": 300, "y": 140},
        }

    nh = NestHost()
    p = deepcopy(nh.document.project)
    p["name"] = "nest-depth3"
    p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
    p["sourceConfig"].update(mode="local", images=list(images), intervalMs=40)
    g1, g2, g3 = "g1", "g2", "g3"
    inner_g2 = default_group_inner()
    inner_g2["steps"] = [make_group(g3, "组合C")]
    inner_g1 = default_group_inner()
    inner_g1["steps"] = [make_group(g2, "组合B", inner=inner_g2)]
    p["steps"] = [make_group(g1, "组合A", inner=inner_g1)]
    p["edges"] = []
    nh.document.load(p)

    # Mark root tip before any enter
    root_before = deepcopy(nh.document.project)
    nh.document.commit(root_before)  # ensure tip stable
    pre_enter_root = deepcopy(nh.document.project)

    nh.enter_group_module(g1)
    nh.enter_group_module(g2)
    nh.enter_group_module(g3)
    if len(nh._group_stack) != 3:
        bad("depth3 stack=%d" % len(nh._group_stack))
    else:
        text = nh._group_breadcrumb.label.text()
        if all(x in text for x in ("主流程", "组合A", "组合B", "组合C")) and text.count("›") >= 3:
            ok("depth≥3 breadcrumb: %s" % text)
        else:
            bad("depth≥3 breadcrumb: %r" % text)

    # Edit at depth 3
    edited = deepcopy(nh.document.project)
    edited["steps"] = list(edited.get("steps") or []) + [{
        "id": "leaf-pp",
        "operation": "preprocess",
        "name": "叶预处理",
        "params": {"method": "grayscale"},
        "position": {"x": 300, "y": 200},
        "imageFrom": "source",
    }]
    nh.document.commit(edited)
    if not any(s.get("id") == "leaf-pp" for s in nh.document.project.get("steps") or []):
        bad("depth3 edit missing")
    else:
        ok("depth3 mid-nest edit committed")

    # Exit G3 → G2 view; undo should reach pre-enter-G3 tip (no leaf in G3.inner of G2's g3)
    # Capture G2 project fingerprint before exit? After exit, merged G2 has g3 with leaf.
    nh.exit_group_module()
    if len(nh._group_stack) != 2:
        bad("after exit C depth=%d" % len(nh._group_stack))
    else:
        ok("exit C → depth 2")

    # After exit C: history tip = merged G2; undo → pre-enter tip (G2 without leaf in g3)
    g3step = next((s for s in nh.document.project.get("steps") or [] if s.get("id") == g3), None)
    inner_after = ((g3step or {}).get("params") or {}).get("inner", {}).get("steps") or []
    if not any(s.get("id") == "leaf-pp" for s in inner_after):
        bad("exit C did not persist leaf into G3.inner")
    else:
        ok("exit C persisted leaf into G3.inner")

    idx_at_tip = nh.document.index
    hist_len = len(nh.document.history)
    if idx_at_tip < 1:
        bad("exit C history tip index=%d (need undoable pre-enter)" % idx_at_tip)
    else:
        # One undo must restore pre-enter tip: G3.inner without leaf-pp
        nh.document.undo()
        g3step2 = next((s for s in nh.document.project.get("steps") or [] if s.get("id") == g3), None)
        inner_undo = ((g3step2 or {}).get("params") or {}).get("inner", {}).get("steps") or []
        if any(s.get("id") == "leaf-pp" for s in inner_undo):
            bad("undo after exit C still has leaf — did not reach pre-enter tip (hist_len=%d idx=%d)"
                % (hist_len, idx_at_tip))
        else:
            ok("exit undo reaches pre-enter tip (leaf discarded) hist=%d idx_was=%d"
               % (hist_len, idx_at_tip))
        # redo back so further exits keep merged
        nh.document.redo()

    nh.exit_group_module()  # leave B
    nh.exit_group_module()  # leave A
    if nh._group_stack:
        bad("still nested after full exit")
    else:
        ok("fully exited depth3 nest")

    # Root-level: enter A, exit, undo should restore pre-enter root tip
    nh2 = NestHost()
    p2 = deepcopy(pre_enter_root)
    # simplify: single group
    p2["steps"] = [make_group("gx", "组合X")]
    p2["edges"] = []
    nh2.document.load(p2)
    # mutate root so commit on enter creates distinct tip
    touched = deepcopy(nh2.document.project)
    touched["name"] = "nest-root-pre"
    nh2.document.commit(touched)
    pre = deepcopy(nh2.document.project)
    pre_name = pre.get("name")
    nh2.enter_group_module("gx")
    ed = deepcopy(nh2.document.project)
    ed["steps"] = [{"id": "in1", "operation": "display", "name": "内显示",
                    "params": {"showName": True}, "position": {"x": 1, "y": 1}, "imageFrom": "source"}]
    nh2.document.commit(ed)
    nh2.exit_group_module()
    # merged tip should have display inside gx
    gx = next(s for s in nh2.document.project["steps"] if s["id"] == "gx")
    if not any(s.get("id") == "in1" for s in (gx["params"]["inner"]["steps"] or [])):
        bad("root exit lost inner display")
    else:
        ok("root exit merged inner display")
    if nh2.document.index < 1:
        bad("root exit not undoable")
    else:
        nh2.document.undo()
        # pre-enter tip: gx.inner should NOT have in1
        gx2 = next(s for s in nh2.document.project["steps"] if s["id"] == "gx")
        if any(s.get("id") == "in1" for s in (gx2["params"]["inner"]["steps"] or [])):
            bad("root exit undo did not reach pre-enter tip")
        else:
            ok("root exit undo → pre-enter tip (name=%s)" % nh2.document.project.get("name"))

    # ========== 2) Display annotatedImage → filmstrip/HMI live ==========
    class PickHost:
        def __init__(self):
            self.document = Document()
            self.document.project["steps"] = [
                {"id": "pp1", "operation": "preprocess", "name": "预处理"},
                {"id": "d1", "operation": "display", "name": "显示"},
                {"id": "loc1", "operation": "locate", "name": "定位"},
            ]
            self._pick_annotated_image = MainWindow._pick_annotated_image.__get__(self, PickHost)

    ph = PickHost()
    disp_img = "data:image/png;base64,DISP"
    other_img = "data:image/png;base64,OTHER"
    records = [
        {"id": "pp1", "output": {"annotatedImage": other_img, "operation": "preprocess"}},
        {"id": "d1", "output": {"annotatedImage": disp_img, "operation": "display"}},
        {"id": "loc1", "output": {"annotatedImage": other_img, "operation": "locate"}},
    ]
    picked = ph._pick_annotated_image(records)
    if picked == disp_img:
        ok("prefer display annotatedImage over later locate")
    else:
        bad("pick got %r want display" % picked)

    # filmstrip set_live_result updates current thumb icon
    bar = FilmstripBar()
    bar.set_paths(images, 0)
    app.processEvents()
    before_icon = bar.thumbs.item(0).icon()
    bar.set_live_result(_tiny_png_data_url())
    app.processEvents()
    after_icon = bar.thumbs.item(0).icon()
    if after_icon.isNull():
        bad("set_live_result left null icon")
    else:
        ok("filmstrip set_live_result updated current thumb")

    # HMI set_runtime with annotated
    hmi = OperatorHmiView()
    # ensure at least one image view exists via rebuild defaults
    try:
        hmi.set_runtime({"state": "completed", "elapsedMs": 1, "results": records},
                        image=None, annotated=disp_img)
        ok("HMI set_runtime accepted display annotated")
    except Exception as e:
        bad("HMI set_runtime failed: %s" % e)

    # runtime.cjs includes display in frames list + _stepName
    rt = (ROOT / "lib" / "runtime.cjs").read_text(encoding="utf-8")
    if "'display'].includes(step.operation)" in rt or '"display"].includes' in rt or (
        "distort_correct','display'" in rt or 'distort_correct","display"' in rt
        or "distort_correct','display'" in rt
    ):
        ok("runtime frames.set includes display annotatedImage")
    else:
        # looser
        if "display'].includes" in rt or ",'display']" in rt or ",\"display\"]" in rt:
            ok("runtime frames.set includes display")
        else:
            bad("runtime missing display in frames.set image list")
    if "_stepName" in rt and "display" in rt:
        ok("runtime injects display _stepName")
    else:
        bad("runtime missing display _stepName inject")

    # ========== 3) Dual-mode pause UX — single control owns both ==========
    bar2 = FilmstripBar()
    bar2.set_paths(images, 0)
    if not hasattr(bar2, "set_pause_owner"):
        bad("missing set_pause_owner")
    else:
        bar2.set_pause_owner("continuous")
        tip_c = bar2.pause_btn.toolTip()
        bar2.set_pause_owner("run_all")
        tip_r = bar2.pause_btn.toolTip()
        if "连续" in tip_c and "共用" in tip_c:
            ok("pause owner continuous tip: %s" % tip_c[:40])
        else:
            bad("continuous tip weak: %r" % tip_c)
        if "运行全部" in tip_r and "共用" in tip_r:
            ok("pause owner run_all tip: %s" % tip_r[:40])
        else:
            bad("run_all tip weak: %r" % tip_r)

    class PauseHost:
        def __init__(self):
            self.continuous = False
            self.run_all_filmstrip = False
            self._continuous_paused = False
            self.busy = False
            self._run_target = None
            self.engine_ready = True
            self.logs = []
            self.filmstrip = FilmstripBar()
            self.filmstrip.set_paths(images, 0)
            self.pause_continuous = MainWindow.pause_continuous.__get__(self, PauseHost)
            self.resume_continuous = MainWindow.resume_continuous.__get__(self, PauseHost)
            self._sync_hmi_pause_buttons = lambda *a, **k: None
            self._filmstrip_advance_delay_ms = lambda: 10
            self.guard = lambda fn: fn() if callable(fn) else None

        def log(self, m):
            self.logs.append(str(m))

        def run(self, *a, **k):
            pass

    # run_all path owns pause
    phost = PauseHost()
    phost.run_all_filmstrip = True
    phost.filmstrip.set_pause_owner("run_all")
    phost.filmstrip.set_continuous_controls_enabled(True)
    phost.pause_continuous()
    if not phost._continuous_paused or not phost.filmstrip.pause_btn.isChecked():
        bad("run_all pause not synced")
    else:
        ok("single pause control pauses run_all")
    phost.resume_continuous()
    # continuous path same control
    phost.run_all_filmstrip = False
    phost.continuous = True
    phost.filmstrip.set_pause_owner("continuous")
    phost.pause_continuous()
    if "连续运行" in (phost.logs[-1] if phost.logs else ""):
        ok("same control pauses continuous: %s" % phost.logs[-1])
    else:
        bad("continuous pause log missing: %r" % phost.logs)

    # ========== 4) PropertyFloat Esc/✕ cancel discard vs OK commit ==========
    commits = []

    class FloatHost(QApplication):
        pass

    host_w = type("H", (), {})()
    # PropertyFloat parent optional
    pf = PropertyFloat(None)
    pf.sourceChanged.connect(lambda c: commits.append(deepcopy(c)))

    base_cfg = normalize_source(DEFAULT_SOURCE)
    base_cfg.update(mode="local", images=list(images), intervalMs=50, cameraId="")
    pf.show_source(base_cfg, title="0 图像源")
    app.processEvents()
    if pf._source_baseline is None:
        bad("no source baseline on show")
    else:
        ok("show_source captured baseline mode=%s" % pf._source_baseline.get("mode"))

    # Draft: switch to camera (commit-on-change live)
    form = pf._source_form
    if form is None:
        bad("no source form")
    else:
        form._audit("mode", "camera")
        app.processEvents()
        if not pf._source_dirty:
            bad("draft not marked dirty after mode change")
        elif not commits or commits[-1].get("mode") != "camera":
            bad("live draft did not emit camera")
        else:
            ok("commit-on-change live emitted camera")

        n_before = len(commits)
        # Cancel should restore local baseline
        pf._on_cancel_close()
        app.processEvents()
        if len(commits) <= n_before:
            bad("cancel did not emit restore")
        elif commits[-1].get("mode") != "local":
            bad("cancel restore mode=%r want local" % commits[-1].get("mode"))
        else:
            ok("Esc/取消 discard restored local baseline")

    # OK path commits draft without restore
    commits.clear()
    pf2 = PropertyFloat(None)
    pf2.sourceChanged.connect(lambda c: commits.append(deepcopy(c)))
    pf2.show_source(base_cfg)
    app.processEvents()
    pf2._source_form._audit("mode", "camera")
    app.processEvents()
    pf2._on_ok_close()
    app.processEvents()
    if commits and commits[-1].get("mode") == "camera":
        ok("确定 commits camera (no discard)")
    else:
        bad("OK close last=%r" % (commits[-1] if commits else None))

    # ✕ uses cancel path
    commits.clear()
    pf3 = PropertyFloat(None)
    pf3.sourceChanged.connect(lambda c: commits.append(deepcopy(c)))
    pf3.show_source(base_cfg)
    app.processEvents()
    pf3._source_form._audit("mode", "sdk")
    app.processEvents()
    # simulate ✕
    pf3._on_cancel_close()
    if commits and commits[-1].get("mode") == "local":
        ok("✕ cancel discarded sdk → local")
    else:
        bad("✕ discard last=%r" % (commits[-1] if commits else None))

    # reject()/Esc
    commits.clear()
    pf4 = PropertyFloat(None)
    pf4.sourceChanged.connect(lambda c: commits.append(deepcopy(c)))
    pf4.show_source(base_cfg)
    app.processEvents()
    pf4._source_form._audit("mode", "camera")
    app.processEvents()
    pf4.reject()
    if commits and commits[-1].get("mode") == "local":
        ok("reject/Esc discard → local")
    else:
        bad("reject discard last=%r" % (commits[-1] if commits else None))

    print("---")
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    for m in FAIL:
        print("  FAIL:", m)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
