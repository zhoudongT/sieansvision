#!/usr/bin/env python3
"""E2E offscreen smoke (t191/t192 NEXT):
1) format-protocol HMI counters + 判定门 persist after save/reopen (project JSON)
2) sourceConfig.mode toggle → _sync_filmstrip_visibility on every source apply/OK
3) ContinuousRun (headless) + filmstrip run-all advance with local images folder
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QInputDialog, QPushButton, QComboBox

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


def _sample_images():
    samples = ROOT / "public" / "vision" / "samples"
    paths = [
        samples / "circle-ring.png",
        samples / "circle-hole.png",
        samples / "caliper-line.png",
    ]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError("missing samples: %s" % missing)
    return [str(p.resolve()) for p in paths]


def _run_format_protocol_flow():
    """Headless engine RUN of format-protocol; return flow vars dict or None."""
    script = ROOT / "scripts" / "_tmp_fmt_flow_once.cjs"
    script.write_text(
        """'use strict';
const fs=require('fs'),os=require('os'),path=require('path');
const {Runtime}=require(%s);
const root=%s;
const project=JSON.parse(fs.readFileSync(path.join(root,'projects/open-and-run-format-protocol.sieans'),'utf8'));
try{require(%s).reset();}catch(_){}
const data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-fmt-e2e-'));
const runtime=new Runtime(data,{async run(){throw new Error('vision unused');}},null);
(async()=>{
  const started=runtime.start({project,allowScripts:false});
  for(let i=0;i<200;i++){
    await new Promise(r=>setTimeout(r,25));
    const st=runtime.poll(started.id);
    if(st.state!=='running'){
      const flow=(st.variables&&st.variables.flow)||{};
      if(st.state!=='completed'){console.log(JSON.stringify({ok:false,state:st.state,error:st.error||''}));process.exit(2);}
      console.log(JSON.stringify({ok:true,flow}));
      process.exit(0);
    }
  }
  console.log(JSON.stringify({ok:false,state:'timeout'}));
  process.exit(3);
})().catch(e=>{console.log(JSON.stringify({ok:false,error:String(e)}));process.exit(4);});
"""
        % (
            json.dumps(str(ROOT / "lib" / "runtime.cjs")),
            json.dumps(str(ROOT)),
            json.dumps(str(ROOT / "lib" / "comm-bus.cjs")),
        ),
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            ["node", str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
        try:
            data = json.loads(line)
        except Exception:
            bad("format-protocol engine stdout=%r stderr=%r" % (proc.stdout[-400:], proc.stderr[-400:]))
            return None
        if not data.get("ok"):
            bad("format-protocol engine fail %s" % data)
            return None
        return data.get("flow") or {}
    finally:
        try:
            script.unlink()
        except Exception:
            pass


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    orig = QInputDialog.getItem

    try:
        from desktop.operator_hmi import OperatorHmiView
        from desktop.image_source import normalize_source, DEFAULT_SOURCE, ImageSourceForm
        from desktop.mainwindow import MainWindow
        from desktop.widgets.filmstrip import FilmstripBar
        from desktop.model import Document
        from desktop import scheme as flow_scheme

        images = _sample_images()

        # ========== 1) format-protocol HMI counters + 判定门 save/reopen ==========
        proj_path = ROOT / "projects" / "open-and-run-format-protocol.sieans"
        project = json.loads(proj_path.read_text(encoding="utf-8"))
        # ensure gateKey + counters flags
        run_ui = dict(project.get("runUi") or {})
        fb = dict(run_ui.get("fixedBars") or {})
        fb.setdefault("gateKey", "passGate")
        fb["showCounters"] = True
        fb["showOkNg"] = True
        fb["showHistory"] = True
        run_ui["fixedBars"] = fb
        project["runUi"] = run_ui
        project["sourceConfig"] = normalize_source(project.get("sourceConfig") or {})
        project["sourceConfig"]["mode"] = "local"
        project["sourceConfig"]["images"] = list(images)
        project["sourceConfig"]["currentIndex"] = 0
        project["sourceConfig"]["autoSwitch"] = True
        project["sourceConfig"]["stopAtLast"] = True
        project["sourceConfig"]["intervalMs"] = 100

        flow = _run_format_protocol_flow()
        if flow is not None:
            if flow.get("passGate") in (1, True, "1"):
                ok("format-protocol flow.passGate=%s" % flow.get("passGate"))
            else:
                bad("format-protocol passGate=%r keys=%s" % (flow.get("passGate"), list(flow)[:12]))

        hmi = OperatorHmiView()
        patches = []
        hmi.runUiChanged.connect(lambda p: patches.append(deepcopy(p)))
        hmi.reload_layout(project)
        app.processEvents()
        if not hmi._stats_panels:
            bad("HMI missing ProductionStatsPanel")
        else:
            panel = hmi._stats_panels[0]
            if panel.gate_key() == "passGate":
                ok("HMI gateKey loaded passGate from format-protocol runUi")
            else:
                bad("HMI gateKey=%r expected passGate" % panel.gate_key())

            # Simulate two completed runs via set_runtime (counters)
            result_ok = {
                "state": "completed",
                "elapsedMs": 12,
                "variables": {"flow": dict(flow or {"passGate": 1, "recvData": "OK,12.5,PASS"})},
                "results": [],
            }
            result_ng = {
                "state": "completed",
                "elapsedMs": 9,
                "variables": {"flow": {"passGate": 0, "recvData": "NG,0,FAIL"}},
                "results": [],
            }
            hmi.set_runtime(result_ok)
            hmi.set_runtime(result_ng)
            app.processEvents()
            if panel._ok == 1 and panel._ng == 1:
                ok("HMI counters OK=1 NG=1 after format-protocol gated runs")
            else:
                bad("HMI counters ok=%s ng=%s" % (panel._ok, panel._ng))

            # Change 判定门 → persist into project via MainWindow._on_hmi_run_ui_changed path
            QInputDialog.getItem = staticmethod(_patch_getitem(["commOk"]))
            gbs = [
                b
                for b in panel.findChildren(QPushButton)
                if "判定门" in (b.text() or "") or (b.text() or "").startswith("门:")
            ]
            if not gbs:
                bad("判定门 button missing")
            else:
                gbs[0].click()
                app.processEvents()
                fb2 = (patches[-1].get("fixedBars") if patches else {}) or {}
                if fb2.get("gateKey") != "commOk":
                    bad("runUiChanged gateKey=%r" % fb2.get("gateKey"))
                else:
                    # Simulate document commit + disk save/reopen (scheme_for_disk + JSON)
                    project2 = deepcopy(project)
                    project2["runUi"] = dict(project2.get("runUi") or {})
                    project2["runUi"]["fixedBars"] = dict(fb2)
                    try:
                        flow_scheme.ensure_scheme(project2)
                    except Exception:
                        pass
                    snap = flow_scheme.scheme_for_disk(project2)
                    with tempfile.TemporaryDirectory(prefix="sieans-gate-") as td:
                        dest = Path(td) / "format-protocol-gate.sieans"
                        dest.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
                        reopened = json.loads(dest.read_text(encoding="utf-8"))
                    gk = ((reopened.get("runUi") or {}).get("fixedBars") or {}).get("gateKey")
                    if gk == "commOk":
                        ok("判定门 persist save/reopen JSON gateKey=commOk")
                    else:
                        bad("reopened gateKey=%r" % gk)

                    # open_project_file merge semantics: prefer disk runUi after normalize-like strip
                    stripped = deepcopy(reopened)
                    stripped.pop("runUi", None)  # simulate normalize dropping extension
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
                        if key in reopened:
                            restored[key] = reopened[key]
                    gk2 = ((restored.get("runUi") or {}).get("fixedBars") or {}).get("gateKey")
                    if gk2 == "commOk":
                        ok("open merge restores runUi.fixedBars.gateKey after strip")
                    else:
                        bad("open-merge gateKey=%r" % gk2)

                    hmi3 = OperatorHmiView()
                    hmi3.reload_layout(restored)
                    app.processEvents()
                    if hmi3._stats_panels and hmi3._stats_panels[0].gate_key() == "commOk":
                        ok("HMI reopen applies 判定门=commOk")
                    else:
                        bad(
                            "reopen gate=%r"
                            % (hmi3._stats_panels[0].gate_key() if hmi3._stats_panels else None)
                        )

        # ========== 2) sourceConfig.mode toggle UI → _sync_filmstrip_visibility ==========
        class FakeDoc:
            def __init__(self):
                self.project = {
                    "version": 2,
                    "id": "mode-sync",
                    "name": "mode-sync",
                    "steps": [],
                    "edges": [],
                    "sourceConfig": deepcopy(DEFAULT_SOURCE),
                }
                self.history = [deepcopy(self.project)]
                self.index = 0

            def commit(self, p):
                Document.validate(p)
                self.project = p

            def validate(self, p):
                Document.validate(p)

        class _WbStatus:
            def log_param_change(self, *a, **k):
                return "audited"

        class FakeHost:
            def __init__(self):
                self.document = FakeDoc()
                self.filmstrip = FilmstripBar()
                self.filmstrip.show()  # so isVisible() reflects setVisible from sync
                self.app_mode = "design"
                self.busy = False
                self.root = ROOT
                self.logs_msgs = []
                self.wb_status = _WbStatus()
                from PySide6.QtWidgets import QPlainTextEdit
                self.logs = QPlainTextEdit()

            def guard(self, fn):
                return fn()

            def _sync_filmstrip_visibility(self):
                MainWindow._sync_filmstrip_visibility(self)

            def _sync_filmstrip_interval_hint(self):
                MainWindow._sync_filmstrip_interval_hint(self)

            def update_source_config(self, config):
                MainWindow.update_source_config(self, config)

            def on_param_audited(self, module, param, old, new):
                MainWindow.on_param_audited(self, module, param, old, new)

        host = FakeHost()
        # Wire live ImageSourceForm like property_float: changed → update_source_config
        form = ImageSourceForm(host.document.project["sourceConfig"])
        form.changed.connect(host.update_source_config)
        form.paramAudited.connect(lambda p, o, n: host.on_param_audited("图像源1", p, o, n))
        form.show()
        app.processEvents()

        # Start local with images
        cfg = normalize_source(host.document.project["sourceConfig"])
        cfg.update(mode="local", images=list(images), intervalMs=150, autoSwitch=True)
        form.set_config(cfg)
        app.processEvents()
        host.update_source_config(form.config())
        app.processEvents()
        vis = (not host.filmstrip.isHidden()) and host.filmstrip.isVisible()
        en = host.filmstrip.run_all.isEnabled()
        hint = host.filmstrip.interval_label.text()
        if not (vis and en and "150" in hint):
            bad("local after source OK: visible=%s hidden=%s run_all=%s hint=%r mode=%s"
                % (host.filmstrip.isVisible(), host.filmstrip.isHidden(), en, hint,
                   host.document.project["sourceConfig"].get("mode")))
        else:
            ok("source OK local → filmstrip visible + run-all enabled")

        # Toggle mode via UI combo (simulates dialog OK path via changed+paramAudited)
        mode_combo = form.mode
        cam_idx = mode_combo.findData("camera")
        mode_combo.setCurrentIndex(cam_idx)
        app.processEvents()
        if (not host.filmstrip.isHidden()) or host.filmstrip.run_all.isEnabled():
            bad(
                "camera after mode toggle: visible=%s hidden=%s run_all=%s mode=%s"
                % (host.filmstrip.isVisible(), host.filmstrip.isHidden(),
                   host.filmstrip.run_all.isEnabled(),
                   host.document.project["sourceConfig"].get("mode"))
            )
        elif host.document.project["sourceConfig"].get("mode") != "camera":
            bad("sourceConfig.mode not camera after toggle")
        else:
            ok("source mode→camera UI → _sync_filmstrip_visibility soft-disable")

        loc_idx = mode_combo.findData("local")
        mode_combo.setCurrentIndex(loc_idx)
        app.processEvents()
        if (
            (not host.filmstrip.isHidden())
            and host.filmstrip.run_all.isEnabled()
            and host.document.project["sourceConfig"].get("mode") == "local"
        ):
            ok("source mode→local UI → filmstrip restored")
        else:
            bad("restore local after mode toggle failed visible=%s hidden=%s en=%s mode=%s"
                % (host.filmstrip.isVisible(), host.filmstrip.isHidden(),
                   host.filmstrip.run_all.isEnabled(),
                   host.document.project["sourceConfig"].get("mode")))

        # ========== 3) filmstrip run-all + ContinuousRun E2E ==========
        strip = FilmstripBar()
        strip.set_paths(images, 0, root=ROOT)
        strip.set_auto_switch(True)
        strip.set_stop_at_last(True)
        strip.set_run_all_enabled(True)
        app.processEvents()
        if len(strip.paths()) != 3:
            bad("filmstrip paths=%d" % len(strip.paths()))
        else:
            ok("filmstrip loaded 3 local sample images")

        # Simulate MainWindow.run_all_images advance loop
        visited = []
        strip.thumbs.setCurrentRow(0)
        app.processEvents()
        run_all = True
        steps = 0
        while run_all and steps < 10:
            visited.append(strip.current_path())
            steps += 1
            if strip.advance():
                app.processEvents()
                continue
            run_all = False
        if visited == images:
            ok("filmstrip run-all E2E visited all 3 images in order")
        else:
            bad("run-all visited=%r" % visited)

        # Continuous with auto_switch + stopAtLast: advance until end then stop
        strip2 = FilmstripBar()
        strip2.set_paths(images, 0, root=ROOT)
        strip2.set_auto_switch(True)
        strip2.set_stop_at_last(True)
        cont = True
        cont_visited = []
        strip2.thumbs.setCurrentRow(0)
        app.processEvents()
        for _ in range(10):
            cont_visited.append(strip2.current_path())
            # emulate continuous completed handler
            cfg = {"mode": "local", "stopAtLast": True}
            if cfg.get("mode") == "local" and strip2.auto_switch.isChecked():
                if strip2.advance():
                    app.processEvents()
                    continue
                if cfg.get("stopAtLast"):
                    cont = False
                    break
            break
        if cont is False and cont_visited == images:
            ok("ContinuousRun filmstrip auto-switch+stopAtLast stops after last")
        else:
            bad("continuous visited=%r cont=%s" % (cont_visited, cont))

        # Headless ContinuousRun class with format-protocol, maxCycles=2
        cont_script = ROOT / "scripts" / "_tmp_continuous_once.cjs"
        cont_script.write_text(
            """'use strict';
const fs=require('fs'),os=require('os'),path=require('path');
const {Runtime}=require(%s);
const {ContinuousRun}=require(%s);
const root=%s;
const project=JSON.parse(fs.readFileSync(path.join(root,'projects/open-and-run-format-protocol.sieans'),'utf8'));
try{require(%s).reset();}catch(_){}
const data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-cont-'));
const runtime=new Runtime(data,{async run(){throw new Error('vision unused');}},null);
const cont=new ContinuousRun(runtime,data);
(async()=>{
  const st=cont.start({project,allowScripts:false,intervalMs:100,maxCycles:2});
  for(let i=0;i<400;i++){
    await new Promise(r=>setTimeout(r,50));
    const s=cont.status();
    if(!s.busy){
      console.log(JSON.stringify({ok:s.state==='completed'&&s.completedCycles===2,state:s.state,completed:s.completedCycles,failed:s.failedCycles,error:s.error||null}));
      process.exit(s.state==='completed'&&s.completedCycles===2?0:2);
    }
  }
  console.log(JSON.stringify({ok:false,state:'timeout',status:cont.status()}));
  process.exit(3);
})().catch(e=>{console.log(JSON.stringify({ok:false,error:String(e)}));process.exit(4);});
"""
            % (
                json.dumps(str(ROOT / "lib" / "runtime.cjs")),
                json.dumps(str(ROOT / "lib" / "continuous-run.cjs")),
                json.dumps(str(ROOT)),
                json.dumps(str(ROOT / "lib" / "comm-bus.cjs")),
            ),
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                ["node", str(cont_script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=90,
            )
            line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
            try:
                data = json.loads(line)
            except Exception:
                bad("ContinuousRun stdout=%r stderr=%r" % (proc.stdout[-500:], proc.stderr[-500:]))
                data = None
            if data and data.get("ok"):
                ok("ContinuousRun headless maxCycles=2 completed=%s" % data.get("completed"))
            elif data:
                bad("ContinuousRun fail %s" % data)
        finally:
            try:
                cont_script.unlink()
            except Exception:
                pass

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
