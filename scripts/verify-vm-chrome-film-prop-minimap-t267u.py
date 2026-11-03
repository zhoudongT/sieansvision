#!/usr/bin/env python3
"""Static + binary smoke for VM chrome land: filmstrip thumbs, PropertyFloat editables,
toolbox glyphs, minimap, flow I/O, host HMI. No screenshots."""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / "qtapp" / "src"
BIN = ROOT / "qtapp" / "build" / "sieans_qt"
fail = 0

def ok(msg):
    print(f"PASS  {msg}")

def bad(msg):
    global fail
    fail += 1
    print(f"FAIL  {msg}")

checks = [
    (QT / "FilmstripBar.cpp", ["rebuildThumbs", "QListWidget", "scaled(72, 48", "addPaths", "autoSwitch"]),
    (QT / "PropertyFloat.cpp", ["paramsReverted", "baseline_", "revertAndHide", "propertyFloatOk"]),
    (QT / "PropertyPanel.cpp", ["specsFor", "QDoubleSpinBox", "emitEdit", "QComboBox", "addExprTable"]),
    (QT / "OperatorLibrary.cpp", ["opGlyph", "setIconSize", "glyphKindFor"]),
    (QT / "FlowMinimap.cpp", ["flowMinimap", "centerOn", "itemsBoundingRect"]),
    (QT / "FlowIoDialog.cpp", ["flowIoTable", "resultIo", "输入设置", "输出设置"]),
    (QT / "HostStatePanel.cpp", ["startRequested", "raiseAlarm", "Idle"]),
    (QT / "MainWindow.cpp", ["onOpenFlowIo", "onParamsReverted", "onToggleRunMode", "HostStatePanel"]),
]
for path, needles in checks:
    if not path.exists():
        bad(f"missing {path}")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [n for n in needles if n not in text]
    if missing:
        bad(f"{path.name}: missing {missing}")
    else:
        ok(f"{path.name} markers")

if not BIN.exists():
    bad(f"binary missing: {BIN}")
else:
    ok(f"binary {BIN.stat().st_size} bytes")

# offscreen brief launch — soft backend, quit via env if supported
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"
env["SIEANS_QT_AUTO_SOFT"] = "1"
# main.cpp likely quits on SIEANS_QT_QUIT_MS or similar — check
main = (QT / "main.cpp").read_text(encoding="utf-8", errors="replace")
quit_env = None
for cand in ("SIEANS_QT_AUTO_QUIT_MS", "SIEANS_QT_QUIT_MS", "SIEANS_QT_HEADLESS_MS"):
    if cand in main or cand in (QT / "MainWindow.cpp").read_text(encoding="utf-8", errors="replace"):
        quit_env = cand
        break
# MainWindow uses singleShot quit for AUTO flags — grep
mw = (QT / "MainWindow.cpp").read_text(encoding="utf-8", errors="replace")
import re
m = re.search(r'qgetenv\("SIEANS_QT_[^"]+"\)', mw)
print("info  sample env hooks:", sorted(set(re.findall(r'qgetenv\("([^"]+)"\)', mw)))[:12])

# Brief offscreen run with screenshot-quit path (no user screenshot delivery).
env["SIEANS_QT_SCREENSHOT"] = str(ROOT / "artifacts" / "verify-vm-chrome-t267u.png")
env["SIEANS_QT_SCREENSHOT_QUIT"] = "1"
env["SIEANS_QT_AUTO_SAMPLE"] = "1"
Path(env["SIEANS_QT_SCREENSHOT"]).parent.mkdir(parents=True, exist_ok=True)
proc2 = subprocess.Popen([str(BIN)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    proc2.wait(timeout=12)
except subprocess.TimeoutExpired:
    proc2.kill()
    proc2.wait(timeout=3)
    bad("offscreen screenshot-quit timed out")
else:
    err = (proc2.stderr.read() or b"").decode(errors="replace")
    if proc2.returncode == 0:
        ok(f"offscreen screenshot-quit exit 0")
    else:
        bad(f"offscreen exit {proc2.returncode}: {err[-500:]}")

print("---")
print("FAILS", fail)
sys.exit(1 if fail else 0)
