#!/usr/bin/env python3
"""Decode barcodes via C++ sieans_native (no camera)."""
from __future__ import annotations
import os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / ".pydeps"))
sys.path.insert(0, str(REPO / "native" / "build" / "python"))

import numpy as np
import sieans_native as native

def main():
    print("native", native.version(), "gentl", native.gentl_available())
    img_path = REPO / "artifacts" / "qr-t238-grab0.png"
    if not img_path.is_file():
        # synthesize a blank and expect empty
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        hits = native.decode_barcodes(img, formats="QRCode")
        print("synthetic empty", len(hits))
        return 0
    import cv2
    img = cv2.imread(str(img_path))
    assert img is not None
    t0 = time.perf_counter()
    hits = native.decode_barcodes(img, formats="QRCode", max_codes=16)
    dt = (time.perf_counter() - t0) * 1000
    print(f"decoded {len(hits)} in {dt:.1f} ms from {img_path.name} {img.shape}")
    for h in hits:
        print(" ", h.get("format"), (h.get("text") or "")[:60])
    # compare with python zxingcpp if present
    try:
        import zxingcpp
        t1 = time.perf_counter()
        py = [c for c in zxingcpp.read_barcodes(img) if c.valid]
        dt2 = (time.perf_counter() - t1) * 1000
        print(f"python zxingcpp: {len(py)} in {dt2:.1f} ms")
    except Exception as exc:
        print("python zxingcpp skip:", exc)
    if len(hits) < 1:
        print("FAIL: expected >=1 QR")
        return 1
    print("PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
