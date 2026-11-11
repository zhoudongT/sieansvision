#!/usr/bin/env python3
"""Generate a tiny local ONNX stub that proves the Qt YOLO ONNX path.

This is NOT an official YOLO weight and must not be used as industrial detection.
The graph ignores image content and emits a single YOLOv8-style detection
tensor of shape [1, 5, 1] = (cx, cy, w, h, class0-score) in 64x64 input pixels.
Pass --seg for a two-output YOLOv8/11-seg stub (preds + proto mask).
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


def build_seg(path: Path) -> None:
    """Tiny two-output YOLOv8/11-seg stub: [1,6,1] preds + [1,1,16,16] proto."""
    _need_onnx()
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    # [cx, cy, w, h, class0, mask_coeff] in 64x64 letterbox pixels.
    det = np.array([[[32.0], [32.0], [24.0], [24.0], [0.97], [1.0]]], dtype=np.float32)
    proto = np.zeros((1, 1, 16, 16), dtype=np.float32)
    # Box 20–44 maps to proto cells 5–11 at 64/16 = 4 px per cell.
    proto[0, 0, 5:11, 5:11] = 8.0
    zero = np.array(0.0, dtype=np.float32)
    axes = np.array([0, 1, 2, 3], dtype=np.int64)

    images = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 64, 64])
    output0 = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 6, 1])
    output1 = helper.make_tensor_value_info("output1", TensorProto.FLOAT, [1, 1, 16, 16])
    nodes = [
        helper.make_node("Constant", [], ["zero"], value=numpy_helper.from_array(zero, "zero_t")),
        helper.make_node("Mul", ["images", "zero"], ["zeroed"]),
        helper.make_node("Constant", [], ["axes"], value=numpy_helper.from_array(axes, "axes_t")),
        helper.make_node("ReduceSum", ["zeroed", "axes"], ["scalar"], keepdims=0),
        helper.make_node("Constant", [], ["det"], value=numpy_helper.from_array(det, "det_t")),
        helper.make_node("Add", ["det", "scalar"], ["output0"]),
        helper.make_node("Constant", [], ["proto"], value=numpy_helper.from_array(proto, "proto_t")),
        helper.make_node("Add", ["proto", "scalar"], ["output1"]),
    ]
    graph = helper.make_graph(nodes, "sieans_yolo_seg_smoke", [images], [output0, output1])
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 17)],
        ir_version=8,
        producer_name="sieansvision",
        doc_string="Local smoke stub for Qt ONNX YOLO-seg path; not a real segmenter.",
    )
    model.domain = "sieans.smoke"
    onnx.checker.check_model(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(path))
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seg", action="store_true", help="emit the YOLO-seg stub instead of detect")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
    )
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1] / "models"
    if args.output is None:
        args.output = root / ("sieans-yolo-seg-smoke.onnx" if args.seg else "sieans-yolo-smoke.onnx")
    if args.seg:
        build_seg(args.output)
    else:
        build(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
