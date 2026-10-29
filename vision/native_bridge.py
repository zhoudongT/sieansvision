"""Prefer C++ sieans_native barcode decode; fall back to Python zxingcpp.

Controlled by env SIEANS_NATIVE:
  auto (default) — try native, else python
  1/on/force     — require native
  0/off/python   — force python zxingcpp
"""
from __future__ import annotations

import os
from typing import Any

_NATIVE = None
_NATIVE_ERR = None


def native_mode() -> str:
    v = (os.environ.get("SIEANS_NATIVE") or "auto").strip().lower()
    if v in ("0", "false", "off", "no", "python"):
        return "python"
    if v in ("1", "true", "on", "yes", "native", "force"):
        return "force"
    return "auto"


def load_native():
    global _NATIVE, _NATIVE_ERR
    if _NATIVE is not None or _NATIVE_ERR is not None:
        return _NATIVE
    try:
        import sieans_native as native  # type: ignore
        _NATIVE = native
        return _NATIVE
    except Exception as exc:  # noqa: BLE001 — soft fallback
        _NATIVE_ERR = exc
        return None


def native_info() -> dict[str, Any]:
    n = load_native()
    if n is None:
        return {"available": False, "error": str(_NATIVE_ERR or "not loaded")}
    try:
        return {
            "available": True,
            "version": n.version(),
            "gentl": bool(n.gentl_available()),
            "mode": native_mode(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}


def decode_barcodes_native(image, *, formats: str = "", max_codes: int = 16):
    """Return list[dict] compatible with engine.barcode items (pre-offset)."""
    native = load_native()
    if native is None:
        raise RuntimeError(f"sieans_native unavailable: {_NATIVE_ERR}")
    return list(
        native.decode_barcodes(
            image,
            formats=formats or "",
            max_codes=int(max_codes),
            try_rotate=True,
            try_downscale=True,
        )
    )
