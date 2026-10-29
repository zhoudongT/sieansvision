"""Open-and-run sample catalog — single source for 从模板新建 / 打开示例 / docs.

wave148/wave150: keep App menus and docs in parity with projects/*.sieans soft samples
(wave150 adds soft simulator camera open-and-run).
wave157: GenTL→QR LocalBus barcode send + session persist/reconnect UX.
wave155: TCP loopback (tcp-sim + CommManager real TCP) is productized; still no Halcon/robot/cloud claims. Soft open-and-run remains default.
"""
from __future__ import annotations

from typing import Iterable

# (label, relative_path)
# Order = menu order. Keep denser-chrome samples near their capability cluster.
OPEN_AND_RUN_ENTRIES: list[tuple[str, str]] = [
    ('默认产线 · 上位机运行壳', 'projects/default-platform.sieans'),
    ('打开即跑 · 演示链', 'projects/open-and-run-demo.sieans'),
    ('打开即跑 · 模板匹配', 'projects/open-and-run-locate.sieans'),
    ('打开即跑 · 匹配定位候选铬', 'projects/open-and-run-match-locate-chrome.sieans'),
    ('打开即跑 · 卡尺直线', 'projects/open-and-run-caliper.sieans'),
    ('打开即跑 · 卡尺→几何测量', 'projects/open-and-run-caliper-measure.sieans'),
    ('打开即跑 · 测量卡尺铬→OCR缺陷表', 'projects/open-and-run-measure-caliper-chrome.sieans'),
    ('打开即跑 · 几何测量', 'projects/open-and-run-measure.sieans'),
    ('打开即跑 · 几何查找→多匹配', 'projects/open-and-run-geom-find-match.sieans'),
    ('打开即跑 · 几何夹角圆距+脚本', 'projects/open-and-run-geom-script.sieans'),
    ('打开即跑 · 轮廓→色彩区域', 'projects/open-and-run-contour-color.sieans'),
    ('打开即跑 · 夹具位姿→预处理链', 'projects/open-and-run-fixture-pose-chain.sieans'),
    ('打开即跑 · 定位→夹具→预处理', 'projects/open-and-run-fixture-preprocess.sieans'),
    ('打开即跑 · 九点/门限密度铬', 'projects/open-and-run-ninepoint.sieans'),
    ('打开即跑 · 条码/ID密度铬', 'projects/open-and-run-barcode.sieans'),
    ('打开即跑 · OCR/缺陷密度铬', 'projects/open-and-run-ocr-defect-chrome.sieans'),
    ('打开即跑 · OCR→门限→Comm', 'projects/open-and-run-ocr-gate-comm.sieans'),
    ('打开即跑 · 定位→测量→缺陷', 'projects/open-and-run-locate-measure-defect.sieans'),
    ('打开即跑 · 参考图缺陷', 'projects/open-and-run-defects.sieans'),
    ('打开即跑 · Python脚本', 'projects/open-and-run-script.sieans'),
    ('打开即跑 · Format↔Protocol', 'projects/open-and-run-format-protocol.sieans'),
    ('打开即跑 · Format↔Protocol演示', 'projects/open-and-run-format-protocol-demo.sieans'),
    ('打开即跑 · 组合+通信', 'projects/open-and-run-group-comm.sieans'),
    ('打开即跑 · 多协议通信', 'projects/open-and-run-comm-multiproto.sieans'),
    ('打开即跑 · TCP环回（sim+真套接字）', 'projects/open-and-run-tcp-sim.sieans'),
    ('打开即跑 · 软模拟采集', 'projects/open-and-run-soft-camera.sieans'),
    ('打开即跑 · GenTL相机→二维码', 'projects/open-and-run-gentl-qr.sieans'),
]

# New-from-template extras (non open-and-run shells / camera-oriented).
TEMPLATE_EXTRAS: list[tuple[str, str]] = [
    ('空白检测工程', 'projects/templates/blank-inspection.sieans'),
    ('采集 → 几何 → 尺寸', 'projects/templates/measure-chain.sieans'),
    ('参考图缺陷检测', 'projects/templates/defect-inspection.sieans'),
    ('MV GenTL → OCR（真实相机）', 'projects/templates/mv-gentl-ocr.sieans'),
]

# Open-example only extras (kept out of 从模板新建 to avoid claiming live camera).
EXAMPLE_EXTRAS: list[tuple[str, str]] = [
    ('相机/OCR（需 GenTL 或离线帧）', 'projects/mv-camera-ocr.sieans'),
]


def new_from_template_entries() -> list[tuple[str, str]]:
    """文件→从模板新建检测工程."""
    return list(OPEN_AND_RUN_ENTRIES) + list(TEMPLATE_EXTRAS)


def open_example_rels() -> list[str]:
    """文件→打开示例 relative paths (existence filtered by caller)."""
    rels = [rel for _, rel in OPEN_AND_RUN_ENTRIES]
    rels += [rel for _, rel in TEMPLATE_EXTRAS]
    rels += [rel for _, rel in EXAMPLE_EXTRAS]
    return rels


def expected_sample_files() -> list[str]:
    """All soft open-and-run .sieans that menus/docs should cover."""
    return [rel for _, rel in OPEN_AND_RUN_ENTRIES]


def iter_labels_and_rels(entries: Iterable[tuple[str, str]]):
    for label, rel in entries:
        yield label, rel
