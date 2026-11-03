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
    (QT / "SoftFrame.cpp", ["loadSoftQrSample", "sample-qr.png", "drawFinder", "SIEANS-", "SOFT exp=", "setSoftQrSamplePath", "FastTransformation", "Letterbox", "Guide frame", "SOFT"]),
    (QT / "SieansDocument.cpp", ["seedGentlQrDemo", "format_data", "send_data", "receive_data", "result_gate", "LocalLoop", "passGate", "barcodeCount >= 1", "TcpRealLoopback", "gate1"]),
    (QT / "CommHub.cpp", ["Local Bus", "echo", "lastRx_ = payload", r"{([A-Za-z_]", "mustache", "soft-echo", "tryReconnect", "reconnecting"]),
    (QT / "MainWindow.cpp", ["sourceVar", "named braces", "lastTx()", "format_data", "receive_data"]),
    (QT / "FilmstripBar.cpp", ["KeepAspectRatio", "letterbox", "item:hover", "Key_Left", "selectPrev", "2px solid #e67a2e", "QEvent::Wheel"]),
    (QT / "PropertyFloat.cpp", ["Key_Escape", "Key_Return", "ControlModifier", "baseline_", "acceptedCommit", "propertyFloatHint", "findChild<QLineEdit*>"]),
    (QT / "main.cpp", ["setSoftQrSamplePath", "SIEANS_QT_EXPR_SELFTEST"]),
    (QT / "MainWindow.cpp", ["SIEANS_QT_AUTO_RUN", "SIEANS_QT_FORCE_SEED", "autoStart", "barcodeText=%6", "lastRecv=%8"]),
    (QT / "GenTLWorker.cpp", ["makeSoftFrame(1280, 1024"]),
    (QT / "OperatorLibrary.cpp", ["focusSearch", "Key_F", "def.tip.contains"]),
    (QT / "ExprEval.cpp", ['"needle" in haystack', "in-miss", "startswith", "endswith", "contains-fn", "lower"]),
    (QT / "VarWatchPanel.cpp", ["lastRecv", "theme::OK", "theme::NG"]),
    (QT / "HostStrip.cpp", ["lastRecv", "RX="]),
    (QT / "CommPanel.cpp", ["TX %2", "RX %3"]),
    (QT / "OperatorRail.cpp", ["点击筛选"]),
    (QT / "ImageView.cpp", ["码 %1", "QColor(0, 0, 0, 160)", "#%1 %2: %3"]),
    (QT / "FlowTabBar.cpp", ["stopRequested", "停止运行"]),
    (QT / "FlowTabBar.hpp", ["stopRequested"]),
    (QT / "MainWindow.cpp", ["emptyDefault", "FlowTabBar::stopRequested"]),
    (QT / "PropertyPanel.cpp", ["emptyDefault", "startswith/endswith/contains", "{{name}}"]),
    (QT / "FlowIoDialog.cpp", ["{{name}}"]),
    (QT / "SieansDocument.cpp", ["emptyDefault", "BARCODE empty", "urlOk", "startswith(barcodeText"]),
    (QT / "FlowCanvas.cpp", ["Right-edge run-state", "状态：%2", "theme::WARN", "showState"]),
    (QT / "HostStatePanel.cpp", ["tickPulse", "pulseTimer_", "outline:1px solid"]),
    (QT / "CommHub.cpp", ["reconnectAttempts_", "reconnect #%1", "backoff", "setInterval(ms)"]),
    (QT / "FilmstripBar.cpp", ["InternalMove", "已重排", "拖拽缩略图重排"]),
    (QT / "PropertyFloat.cpp", ["focusNextPrevChild", "Key_Backtab"]),
    (QT / "CommPanel.cpp", ["reconnect", "color:#e0b84a"]),
    (QT / "FlowTabBar.cpp", ["fitRequested", "适应流程画布"]),
    (QT / "MainWindow.cpp", ["FlowTabBar::fitRequested"]),
    (QT / "ImageView.cpp", ["Key_F", "Key_Home", "setFocusPolicy", "F/Home 适应"]),
    (QT / "VarWatchPanel.cpp", ["passGate", "setBold(true)"]),
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


# soft open-and-run functional: GenTL-fallback frame → QR → LocalBus echo
env3 = os.environ.copy()
env3["QT_QPA_PLATFORM"] = "offscreen"
env3["SIEANS_QT_FORCE_SEED"] = "1"
env3["SIEANS_QT_AUTO_SOFT"] = "1"
env3["SIEANS_QT_AUTO_RUN"] = "1"
smoke = ROOT / "artifacts" / "verify-wave4-soft-run.txt"
smoke.parent.mkdir(parents=True, exist_ok=True)
env3["SIEANS_QT_SMOKE_REPORT"] = str(smoke)
env3["SIEANS_QT_SCREENSHOT"] = str(ROOT / "artifacts" / "verify-wave4-soft-run.png")
env3["SIEANS_QT_SCREENSHOT_QUIT"] = "1"
r3 = subprocess.run([str(BIN)], env=env3, capture_output=True, text=True, timeout=40)
body = smoke.read_text(encoding="utf-8", errors="replace") if smoke.exists() else ""
if r3.returncode == 0 and "passGate=1" in body and "codes=" in body and "lastRecv=BARCODE" in body:
    ok(f"soft AUTO_RUN decode+echo: {body.strip()[:160]}")
else:
    bad(f"soft AUTO_RUN rc={r3.returncode} body={body!r} err={r3.stderr[-300:]}")


# TCP listen smoke (server role from seed tcpReal)
env4 = os.environ.copy()
env4["QT_QPA_PLATFORM"] = "offscreen"
env4["SIEANS_QT_FORCE_SEED"] = "1"
env4["SIEANS_QT_AUTO_TCP"] = "1"
env4["SIEANS_QT_AUTO_SOFT"] = "1"
env4["SIEANS_QT_AUTO_RUN"] = "1"
smoke4 = ROOT / "artifacts" / "verify-wave4-tcp-run.txt"
env4["SIEANS_QT_SMOKE_REPORT"] = str(smoke4)
env4["SIEANS_QT_SCREENSHOT"] = str(ROOT / "artifacts" / "verify-wave4-tcp-run.png")
env4["SIEANS_QT_SCREENSHOT_QUIT"] = "1"
r4 = subprocess.run([str(BIN)], env=env4, capture_output=True, text=True, timeout=45)
body4 = smoke4.read_text(encoding="utf-8", errors="replace") if smoke4.exists() else ""
if r4.returncode == 0 and "passGate=1" in body4:
    ok(f"AUTO_TCP+soft run: {body4.strip()[:140]}")
else:
    bad(f"AUTO_TCP rc={r4.returncode} body={body4!r}")



# project-file open-and-run (no FORCE_SEED) — GenTL→QR reliability via .sieans
env5 = os.environ.copy()
env5["QT_QPA_PLATFORM"] = "offscreen"
env5["SIEANS_QT_AUTO_SOFT"] = "1"
env5["SIEANS_QT_AUTO_RUN"] = "1"
# ensure we hit the on-disk project (default load path), not seed
smoke5 = ROOT / "artifacts" / "verify-wave4-project-run.txt"
env5["SIEANS_QT_SMOKE_REPORT"] = str(smoke5)
env5["SIEANS_QT_SCREENSHOT"] = str(ROOT / "artifacts" / "verify-wave4-project-run.png")
env5["SIEANS_QT_SCREENSHOT_QUIT"] = "1"
r5 = subprocess.run([str(BIN)], env=env5, capture_output=True, text=True, timeout=45)
body5 = smoke5.read_text(encoding="utf-8", errors="replace") if smoke5.exists() else ""
proj = ROOT / "projects" / "open-and-run-gentl-qr.sieans"
proj_txt = proj.read_text(encoding="utf-8", errors="replace") if proj.exists() else ""
if "result_gate" not in proj_txt:
    bad("project missing result_gate")
elif r5.returncode == 0 and "passGate=1" in body5 and "lastRecv=BARCODE" in body5:
    ok(f"project AUTO_RUN decode+echo: {body5.strip()[:140]}")
else:
    bad(f"project AUTO_RUN rc={r5.returncode} body={body5!r} err={(r5.stderr or '')[-300:]}")

print("---")
print("FAILS", fail)
sys.exit(1 if fail else 0)
