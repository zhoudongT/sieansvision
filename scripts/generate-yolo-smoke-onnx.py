#!/usr/bin/env python3
"""Generate a tiny local ONNX stub that proves the Qt YOLO ONNX path.

This is NOT an official YOLO weight and must not be used as industrial detection.
The graph ignores image content and emits a single YOLOv8-style detection
tensor of shape [1, 5, 1] = (cx, cy, w, h, class0-score) in 64x64 input pixels.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _need_onnx():
    try:
        import onnx  # noqa: F401
        import numpy  # noqa: F401
        return
    except ImportError:
        pass
    raise SystemExit(
        "need the onnx and numpy packages to generate the stub "
        "(install into a user venv; do not use this script to download YOLO weights)"
    )


def build(path: Path) -> None:
    _need_onnx()
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    # YOLOv8-style output: [1, 4+nc, anchors] with nc=1, anchors=1.
    # Box is centered in the 64x64 letterbox; score 0.97.
    det = np.array([[[32.0], [32.0], [24.0], [24.0], [0.97]]], dtype=np.float32)
    zero = np.array(0.0, dtype=np.float32)

    images = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 64, 64])
    output0 = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 5, 1])

    # Opset 13+ 把 ReduceSum 的 axes 改成输入。用 axes 张量把图像乘 0 再加到常量上，
    # 这样 images 输入被实际使用，输出仍是固定检测框。
    axes = np.array([0, 1, 2, 3], dtype=np.int64)
    nodes = [
        helper.make_node("Constant", [], ["zero"], value=numpy_helper.from_array(zero, "zero_t")),
        helper.make_node("Mul", ["images", "zero"], ["zeroed"]),
        helper.make_node("Constant", [], ["axes"], value=numpy_helper.from_array(axes, "axes_t")),
        helper.make_node("ReduceSum", ["zeroed", "axes"], ["scalar"], keepdims=0),
        helper.make_node("Constant", [], ["det"], value=numpy_helper.from_array(det, "det_t")),
        helper.make_node("Add", ["det", "scalar"], ["output0"]),
    ]
    graph = helper.make_graph(nodes, "sieans_yolo_smoke", [images], [output0])
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 17)],
        ir_version=8,
        producer_name="sieansvision",
        doc_string="Local smoke stub for Qt ONNX YOLO path; not a real detector.",
    )
    model.domain = "sieans.smoke"
    onnx.checker.check_model(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(path))
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "sieans-yolo-smoke.onnx",
    )
    args = ap.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
