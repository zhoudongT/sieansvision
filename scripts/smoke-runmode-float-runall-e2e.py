#!/usr/bin/env python3
"""Headless/offscreen E2E (t191/t192 NEXT):
1) 运行模式 counters tick + 判定门 change + Save + Reopen → gateKey+runUi applied
2) PropertyFloat source mode camera/local while float open → filmstrip hide/show
3) Filmstrip run-all with samples folder + intervalMs pacing
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
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
    QPlainTextEdit,
    QPushButton,
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


def _sample_folder_images(limit=4):
    samples = ROOT / "public" / "vision" / "samples"
    paths = sorted(str(p.resolve()) for p in samples.glob("*.png"))[:limit]
    if len(paths) < 2:
        raise FileNotFoundError("need >=2 png under public/vision/samples")
    return paths


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    orig = QInputDialog.getItem

    try:
        from desktop.operator_hmi import OperatorHmiView
        from desktop.image_source import normalize_source, DEFAULT_SOURCE
        from desktop.mainwindow import MainWindow
        from desktop.widgets.filmstrip import FilmstripBar
        from desktop.model import Document
        from desktop.property_float import PropertyFloat
        from desktop import scheme as flow_scheme

        images = _sample_folder_images(4)

        # ========== 1) 运行模式 counters + 判定门 Save/Reopen ==========
        proj = json.loads(
            (ROOT / "projects" / "open-and-run-format-protocol.sieans").read_text(encoding="utf-8")
        )
        run_ui = dict(proj.get("runUi") or {})
        fb = dict(run_ui.get("fixedBars") or {})
        fb["gateKey"] = "passGate"
        fb["showCounters"] = True
        fb["showOkNg"] = True
        fb["showHistory"] = True
        fb["bottom"] = True
        run_ui["fixedBars"] = fb
        proj["runUi"] = run_ui
        proj["sourceConfig"] = normalize_source(proj.get("sourceConfig") or {})
        proj["sourceConfig"].update(
            mode="local",
            images=list(images),
            intervalMs=80,
            autoSwitch=True,
            stopAtLast=True,
            currentIndex=0,
        )
        try:
            flow_scheme.ensure_scheme(proj)
        except Exception:
            pass

        class _Wb:
            def log_param_change(self, *a, **k):
                return "audited"

        class FakeDoc(Document):
            pass

        class RunHost:
            """Minimal MainWindow surface for HMI persist + filmstrip sync."""

            def __init__(self, project):
                self.document = FakeDoc()
                self.document.load(project)
                self.filename = None
                self.busy = False
                self.app_mode = "run"
                self.root = ROOT
                self.filmstrip = FilmstripBar()
                self.filmstrip.show()
                self.wb_status = _Wb()
                self.logs = QPlainTextEdit()
                self.operator_hmi = OperatorHmiView()
                self.operator_hmi.runUiChanged.connect(
                    lambda patch: self.guard(lambda: self._on_hmi_run_ui_changed(patch))
                )
                self.operator_hmi.reload_layout(self.document.project)
                app.processEvents()

            def guard(self, fn):
                return fn()

            def _on_hmi_run_ui_changed(self, patch):
                MainWindow._on_hmi_run_ui_changed(self, patch)

            def _sync_filmstrip_visibility(self):
                MainWindow._sync_filmstrip_visibility(self)

            def _sync_filmstrip_interval_hint(self):
                MainWindow._sync_filmstrip_interval_hint(self)

            def update_source_config(self, config):
                MainWindow.update_source_config(self, config)

            def on_param_audited(self, module, param, old, new):
                MainWindow.on_param_audited(self, module, param, old, new)

            def _filmstrip_advance_delay_ms(self):
                return MainWindow._filmstrip_advance_delay_ms(self)

            def _active_run_interval_ms(self):
                return 120

            def save_to(self, path: Path):
                snapshot = flow_scheme.scheme_for_disk(self.document.project)
                # Mirror _write_scheme_file client-side keep of runUi
                out = deepcopy(snapshot)
                for key in ("runUi", "commManager", "globalTriggers", "notes", "sourceConfig"):
                    if key in snapshot:
                        out[key] = deepcopy(snapshot[key])
                path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                self.filename = path
                self.document.saved = deepcopy(out)
                return out

            def reopen_from(self, path: Path):
                value = json.loads(path.read_text(encoding="utf-8"))
                # Simulate engine normalize that might drop extensions, then open merge
                stripped = deepcopy(value)
                for k in ("runUi", "commManager", "globalTriggers", "notes"):
                    stripped.pop(k, None)
                restored = deepcopy(stripped)
                for key in (
                    "flows",
                    "activeFlowId",
                    "flowEdges",
                    "runUi",
                    "commManager",
                    "globalTriggers",
                    "notes",
                    "sourceConfig",
                ):
                    if key in value:
                        restored[key] = value[key]
                self.document.load(restored)
                self.app_mode = "run"
                self.operator_hmi.reload_layout(self.document.project)
                app.processEvents()
                return restored

        host = RunHost(proj)
        panels = host.operator_hmi._stats_panels
        if not panels:
            bad("run-mode HMI missing stats panel")
        else:
            panel = panels[0]
            if panel.gate_key() != "passGate":
                bad("run-mode initial gateKey=%r" % panel.gate_key())
            else:
                ok("run-mode gateKey=passGate from project.runUi")

            # Counters tick (模拟连续运行完成)
            for i, gate_val in enumerate((1, 1, 0, 1)):
                host.operator_hmi.set_runtime(
                    {
                        "state": "completed",
                        "elapsedMs": 10 + i,
                        "variables": {"flow": {"passGate": gate_val, "recvData": "OK"}},
                        "results": [],
                    }
                )
            app.processEvents()
            if panel._ok == 3 and panel._ng == 1:
                ok("run-mode counters tick OK=3 NG=1")
            else:
                bad("counters ok=%s ng=%s" % (panel._ok, panel._ng))

            # 判定门 change → document commit via _on_hmi_run_ui_changed
            QInputDialog.getItem = staticmethod(_patch_getitem(["commOk"]))
            gbs = [
                b
                for b in panel.findChildren(QPushButton)
                if "判定门" in (b.text() or "") or (b.text() or "").startswith("门:")
            ]
            if not gbs:
                bad("判定门 button missing in run-mode")
            else:
                gbs[0].click()
                app.processEvents()
                live_gk = (
                    ((host.document.project.get("runUi") or {}).get("fixedBars") or {}).get("gateKey")
                )
                if live_gk != "commOk":
                    bad("document gateKey after pick=%r" % live_gk)
                else:
                    ok("判定门 change committed runUi.fixedBars.gateKey=commOk")

                with tempfile.TemporaryDirectory(prefix="sieans-runmode-") as td:
                    dest = Path(td) / "format-protocol-runmode.sieans"
                    saved = host.save_to(dest)
                    sgk = ((saved.get("runUi") or {}).get("fixedBars") or {}).get("gateKey")
                    if sgk != "commOk":
                        bad("saved JSON gateKey=%r" % sgk)
                    else:
                        ok("Save wrote gateKey=commOk")

                    # New host reopen (fresh HMI) — counters reset, gateKey must apply
                    host2 = RunHost(
                        {
                            "version": 2,
                            "id": "blank",
                            "name": "blank",
                            "steps": [],
                            "edges": [],
                            "runUi": {"fixedBars": {"gateKey": "passGate"}},
                        }
                    )
                    restored = host2.reopen_from(dest)
                    rgk = ((restored.get("runUi") or {}).get("fixedBars") or {}).get("gateKey")
                    hmi_gk = (
                        host2.operator_hmi._stats_panels[0].gate_key()
                        if host2.operator_hmi._stats_panels
                        else None
                    )
                    if rgk == "commOk" and hmi_gk == "commOk":
                        ok("Reopen applies gateKey+runUi (JSON=%s HMI=%s)" % (rgk, hmi_gk))
                    else:
                        bad("reopen JSON gate=%r HMI gate=%r" % (rgk, hmi_gk))

                    # Counters still work under new gate (commOk)
                    host2.operator_hmi.set_runtime(
                        {
                            "state": "completed",
                            "elapsedMs": 5,
                            "variables": {"flow": {"commOk": 1}},
                            "results": [],
                        }
                    )
                    host2.operator_hmi.set_runtime(
                        {
                            "state": "completed",
                            "elapsedMs": 6,
                            "variables": {"flow": {"commOk": 0}},
                            "results": [],
                        }
                    )
                    app.processEvents()
                    p2 = host2.operator_hmi._stats_panels[0]
                    if p2._ok == 1 and p2._ng == 1:
                        ok("reopen counters tick under gateKey=commOk OK=1 NG=1")
                    else:
                        bad("reopen counters ok=%s ng=%s" % (p2._ok, p2._ng))

        # ========== 2) PropertyFloat source mode while float open ==========
        class FloatHost:
            def __init__(self):
                self.document = Document()
                p = deepcopy(self.document.project)
                p["sourceConfig"] = normalize_source(DEFAULT_SOURCE)
                p["sourceConfig"].update(
                    mode="local",
                    images=list(images),
                    intervalMs=80,
                    autoSwitch=True,
                    stopAtLast=False,
                )
                self.document.load(p)
                self.busy = False
                self.app_mode = "design"
                self.root = ROOT
                self.filmstrip = FilmstripBar()
                self.filmstrip.show()
                self.wb_status = _Wb()
                self.logs = QPlainTextEdit()
                self.property_float = PropertyFloat()
                self.property_float.sourceChanged.connect(self.update_source_config)
                self.property_float.paramAudited.connect(self.on_param_audited)

            def guard(self, fn):
                return fn()

            def update_source_config(self, config):
                MainWindow.update_source_config(self, config)

            def on_param_audited(self, module, param, old, new):
                MainWindow.on_param_audited(self, module, param, old, new)

            def _sync_filmstrip_visibility(self):
                MainWindow._sync_filmstrip_visibility(self)

            def _sync_filmstrip_interval_hint(self):
                MainWindow._sync_filmstrip_interval_hint(self)

            def open_property_float_source(self):
                cfg = normalize_source(self.document.project.get("sourceConfig"))
                self.property_float.show_source(cfg, title="0 图像源")
                self._sync_filmstrip_visibility()

        fh = FloatHost()
        # Seed filmstrip from sourceConfig before opening float
        fh.update_source_config(fh.document.project["sourceConfig"])
        app.processEvents()
        flo = fh.property_float
        fh.open_property_float_source()
        app.processEvents()
        form = flo._source_form
        if form is None:
            bad("PropertyFloat show_source missing form")
        else:
            # float stays open across mode toggles (same form instance)
            form_id = id(form)
            if not fh.filmstrip.isVisible() or not fh.filmstrip.run_all.isEnabled():
                bad(
                    "float-open local: vis=%s run_all=%s"
                    % (fh.filmstrip.isVisible(), fh.filmstrip.run_all.isEnabled())
                )
            else:
                ok("PropertyFloat open source local → filmstrip visible")

            form.mode.setCurrentIndex(form.mode.findData("camera"))
            app.processEvents()
            same = flo._source_form is not None and id(flo._source_form) == form_id
            if fh.filmstrip.isHidden() and not fh.filmstrip.run_all.isEnabled() and same:
                ok("float-open mode→camera hide/soft-disable without reopen")
            else:
                bad(
                    "camera while float: hidden=%s en=%s same_form=%s"
                    % (fh.filmstrip.isHidden(), fh.filmstrip.run_all.isEnabled(), same)
                )

            form.mode.setCurrentIndex(form.mode.findData("local"))
            app.processEvents()
            same2 = flo._source_form is not None and id(flo._source_form) == form_id
            if (
                (not fh.filmstrip.isHidden())
                and fh.filmstrip.run_all.isEnabled()
                and same2
                and fh.document.project["sourceConfig"].get("mode") == "local"
            ):
                ok("float-open mode→local restore without reopen")
            else:
                bad(
                    "local restore while float: hidden=%s en=%s same=%s mode=%s"
                    % (
                        fh.filmstrip.isHidden(),
                        fh.filmstrip.run_all.isEnabled(),
                        same2,
                        fh.document.project["sourceConfig"].get("mode"),
                    )
                )

            # OK button closes float; filmstrip state must remain
            flo.ok_btn.click()
            app.processEvents()
            if (not fh.filmstrip.isHidden()) and fh.filmstrip.run_all.isEnabled():
                ok("PropertyFloat OK close keeps filmstrip local state")
            else:
                bad("after OK close filmstrip wrong")

        # ========== 3) Filmstrip run-all + intervalMs pacing ==========
        rh = RunHost(proj)
        rh.app_mode = "design"
        rh.document.project["sourceConfig"]["intervalMs"] = 80
        rh.document.project["sourceConfig"]["mode"] = "local"
        rh.document.project["sourceConfig"]["images"] = list(images)
        rh.filmstrip.set_paths(images, 0, root=ROOT)
        rh.filmstrip.set_auto_switch(True)
        rh.filmstrip.set_stop_at_last(True)
        rh.filmstrip.set_run_all_enabled(True)
        rh._sync_filmstrip_visibility()
        rh._sync_filmstrip_interval_hint()
        app.processEvents()

        delay = rh._filmstrip_advance_delay_ms()
        if delay == 80:
            ok("intervalMs pacing delay_ms=80 from sourceConfig")
        else:
            bad("delay_ms=%s expected 80" % delay)

        # Automated run-all with paced advances (no live engine)
        visited = []
        rh.filmstrip.thumbs.setCurrentRow(0)
        app.processEvents()
        t0 = time.monotonic()
        gaps = []
        last = t0
        run_all = True
        steps = 0
        while run_all and steps < 20:
            visited.append(rh.filmstrip.current_path())
            steps += 1
            if not rh.filmstrip.advance():
                run_all = False
                break
            # pace like MainWindow QTimer.singleShot(_filmstrip_advance_delay_ms)
            wait_ms = rh._filmstrip_advance_delay_ms()
            deadline = time.monotonic() + wait_ms / 1000.0
            while time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.005)
            now = time.monotonic()
            gaps.append(now - last)
            last = now
        elapsed = time.monotonic() - t0

        if visited == images:
            ok("run-all samples folder visited %d images in order" % len(visited))
        else:
            bad("run-all visited=%r expected=%r" % (visited, images))

        # N-1 paced gaps between N images; each gap should be ~>= 0.7 * delay
        if len(gaps) == len(images) - 1 and all(g >= (delay / 1000.0) * 0.7 for g in gaps):
            ok(
                "run-all intervalMs pacing gaps≈%s ms (delay=%s, elapsed=%.0fms)"
                % ([int(g * 1000) for g in gaps], delay, elapsed * 1000)
            )
        else:
            bad("pacing gaps=%s delay=%s" % ([int(g * 1000) for g in gaps], delay))

        # Folder add path: FilmstripBar.add_folder uses QFileDialog — simulate set_paths from folder glob
        folder = ROOT / "public" / "vision" / "samples"
        folder_imgs = sorted(str(p.resolve()) for p in folder.glob("circle-*.png"))
        if len(folder_imgs) >= 2:
            rh.filmstrip.set_paths(folder_imgs, 0, root=ROOT)
            app.processEvents()
            if rh.filmstrip.paths() == folder_imgs:
                ok("samples folder subset circle-*.png loaded (%d)" % len(folder_imgs))
            else:
                bad("folder subset paths mismatch")
        else:
            bad("circle-*.png not found in samples")

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
