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


def gentl_available() -> bool:
    """True when sieans_native was built with MvCameraControl GenTL."""
    n = load_native()
    if n is None:
        return False
    try:
        return bool(n.gentl_available())
    except Exception:
        return False


def gentl_acquire_preferred() -> bool:
    """Whether live GenTL freerun should use C++ GenTLCapture.

    Honors SIEANS_NATIVE (python → never; force → require; auto → if available).
    Optional override SIEANS_NATIVE_GENTL_ACQUIRE=0|1|auto.
    """
    override = (os.environ.get("SIEANS_NATIVE_GENTL_ACQUIRE") or "").strip().lower()
    if override in ("0", "false", "off", "no", "python", "harvesters"):
        return False
    if override in ("1", "true", "on", "yes", "native", "force", "cpp"):
        if not gentl_available():
            if native_mode() == "force" or override in ("force", "1", "true", "on", "yes", "native", "cpp"):
                raise RuntimeError(
                    "SIEANS_NATIVE_GENTL_ACQUIRE requires sieans_native GenTL "
                    f"(load error: {_NATIVE_ERR})"
                )
            return False
        return True
    mode = native_mode()
    if mode == "python":
        return False
    ok = gentl_available()
    if mode == "force" and not ok:
        raise RuntimeError(
            f"SIEANS_NATIVE=force but sieans_native GenTL unavailable: {_NATIVE_ERR}"
        )
    return ok

