#!/usr/bin/env python3
"""Wave4: SoftFrame real QR, seed GenTL→QR→TCP, CommHub LocalBus echo, named {var}."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / "qtapp" / "src"
BIN = ROOT / "qtapp" / "build" / "sieans_qt"
fail = 0

def ok(msg): print(f"PASS  {msg}")
def bad(msg):
    global fail
    fail += 1
    print(f"FAIL  {msg}")

checks = [
    (QT / "SoftFrame.cpp", ["loadSoftQrSample", "sample-qr.png", "drawFinder", "SIEANS-", "SOFT exp=", "setSoftQrSamplePath"]),
    (QT / "SieansDocument.cpp", ["seedGentlQrDemo", "format_data", "send_data", "receive_data", "LocalLoop", "passGate", "barcodeCount >= 1", "TcpRealLoopback"]),
    (QT / "CommHub.cpp", ["Local Bus", "echo", "lastRx_ = payload", r"{([A-Za-z_]", "soft-echo"]),
    (QT / "MainWindow.cpp", ["sourceVar", "named braces", "lastTx()", "format_data", "receive_data"]),
    (QT / "FilmstripBar.cpp", ["KeepAspectRatio", "letterbox", "item:hover"]),
    (QT / "PropertyFloat.cpp", ["Key_Escape", "Key_Return", "ControlModifier", "baseline_"]),
    (QT / "main.cpp", ["setSoftQrSamplePath", "SIEANS_QT_EXPR_SELFTEST"]),
]
for path, needles in checks:
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [n for n in needles if n not in text]
    if missing:
        bad(f"{path.name}: missing {missing}")
    else:
        ok(f"{path.name} markers")

# sample qr present
qr = ROOT / "qtapp" / "resources" / "sample-qr.png"
if qr.exists() and qr.stat().st_size > 1000:
    ok(f"sample-qr.png {qr.stat().st_size}")
else:
    bad("sample-qr.png missing/small")

if not BIN.exists():
    bad(f"binary missing {BIN}")
else:
    ok(f"binary {BIN.stat().st_size}")

# expr selftest
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"
env["SIEANS_QT_EXPR_SELFTEST"] = "1"
env["SIEANS_QT_EXPR_SELFTEST_QUIT"] = "1"
r = subprocess.run([str(BIN)], env=env, capture_output=True, text=True, timeout=15)
if r.returncode == 0 and "expr-selftest ok" in (r.stdout or ""):
    ok("expr-selftest")
else:
    bad(f"expr-selftest rc={r.returncode} out={r.stdout[-200:]} err={r.stderr[-300:]}")

# soft open-and-run screenshot-quit with AUTO_SOFT
env2 = os.environ.copy()
env2["QT_QPA_PLATFORM"] = "offscreen"
env2["SIEANS_QT_AUTO_SOFT"] = "1"
env2["SIEANS_QT_AUTO_SAMPLE"] = "1"
shot = ROOT / "artifacts" / "verify-wave4-t268u.png"
shot.parent.mkdir(parents=True, exist_ok=True)
env2["SIEANS_QT_SCREENSHOT"] = str(shot)
env2["SIEANS_QT_SCREENSHOT_QUIT"] = "1"
r2 = subprocess.run([str(BIN)], env=env2, capture_output=True, text=True, timeout=20)
if r2.returncode == 0:
    ok("offscreen soft open-and-run quit 0")
else:
    bad(f"offscreen soft rc={r2.returncode} err={r2.stderr[-400:]}")

print("---")
print("FAILS", fail)
sys.exit(1 if fail else 0)
