"""Launch-time self-check for SIEANS Vision desktop (Chinese-friendly messages)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _try_import(name: str):
    try:
        __import__(name)
        return True, ''
    except Exception as exc:  # noqa: BLE001 — report any import failure to user
        return False, f'{type(exc).__name__}: {exc}'


def check_dependencies(root: Path | None = None) -> list[dict]:
    """Return list of {id, ok, title, detail} for required desktop/runtime pieces."""
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    pydeps = root / '.pydeps'
    if pydeps.is_dir() and str(pydeps) not in sys.path:
        sys.path.insert(0, str(pydeps))

    items: list[dict] = []

    def add(item_id: str, ok: bool, title: str, detail: str = ''):
        items.append({'id': item_id, 'ok': bool(ok), 'title': title, 'detail': detail or ''})

    ok, err = _try_import('PySide6')
    add('pyside6', ok, '桌面界面 PySide6', err or '已安装')

    ok, err = _try_import('cv2')
    add('opencv', ok, '图像库 OpenCV', err or '已安装')

    ok, err = _try_import('numpy')
    add('numpy', ok, '数值库 NumPy', err or '已安装')

    ok, err = _try_import('harvesters')
    add('harvesters', ok, '工业相机 GenTL (harvesters)', err or '已安装')

    ok_r, err_r = _try_import('rapidocr_onnxruntime')
    if not ok_r:
        ok_r2, err_r2 = _try_import('rapidocr')
        ok_r, err_r = ok_r2, err_r or err_r2
    add('rapidocr', ok_r, '字符识别 RapidOCR', err_r or '已安装')

    ok, err = _try_import('zxingcpp')
    add('zxingcpp', ok, '条码识别 zxing-cpp', err or '已安装')

    cti_env = os.environ.get('SIEANS_GENTL_CTI', '')
    cti_paths = [p for p in cti_env.split(':') if p.strip()] if cti_env else [
        '/opt/MVS/lib/64/MvProducerU3V.cti',
        '/opt/MVS/lib/64/MvProducerGEV.cti',
    ]
    existing = [p for p in cti_paths if Path(p).is_file()]
    if existing:
        add('cti', True, '海康 GenTL 驱动 (CTI)', '；'.join(existing))
    else:
        add('cti', False, '海康 GenTL 驱动 (CTI)',
            '未找到 MvProducerU3V.cti。请安装 MVS，或设置 SIEANS_GENTL_CTI')

    mvs_lib = Path('/opt/MVS/lib/64')
    add('mvs_lib', mvs_lib.is_dir(), 'MVS 运行库',
        str(mvs_lib) if mvs_lib.is_dir() else '未找到 /opt/MVS/lib/64')

    return items


def enumerate_gentl_devices() -> tuple[list[str], str]:
    """Best-effort GenTL device list. Returns (labels, error_or_empty)."""
    try:
        from harvesters.core import Harvester
    except Exception as exc:  # noqa: BLE001
        return [], f'无法加载 harvesters：{exc}'

    cti_env = os.environ.get('SIEANS_GENTL_CTI', '')
    cti_paths = [p for p in cti_env.split(':') if p.strip()] if cti_env else [
        '/opt/MVS/lib/64/MvProducerU3V.cti',
        '/opt/MVS/lib/64/MvProducerGEV.cti',
    ]
    h = Harvester()
    try:
        loaded = False
        for cti in cti_paths:
            if Path(cti).is_file():
                try:
                    h.add_file(cti)
                    loaded = True
                except Exception:  # noqa: BLE001
                    continue
        if not loaded:
            return [], '没有可用的 CTI 文件'
        h.update()
        labels = []
        for info in h.device_info_list:
            try:
                label = str(info)
            except Exception:  # noqa: BLE001
                label = repr(info)
            labels.append(label)
        return labels, ''
    except Exception as exc:  # noqa: BLE001
        return [], f'{type(exc).__name__}: {exc}'
    finally:
        try:
            h.reset()
        except Exception:  # noqa: BLE001
            pass


def summarize(items: list[dict], devices: list[str], device_error: str = '') -> dict:
    failed = [i for i in items if not i['ok']]
    lines = []
    if not failed:
        lines.append('依赖自检通过')
    else:
        lines.append('部分依赖未就绪：' + '、'.join(i['title'] for i in failed))
        for i in failed:
            if i['detail']:
                lines.append(f"  · {i['title']}：{i['detail']}")
    if devices:
        lines.append(f'已发现 {len(devices)} 台 GenTL 相机')
        for d in devices[:5]:
            lines.append(f'  · {d}')
    else:
        msg = '未检测到 GenTL 工业相机'
        if device_error:
            msg += f'（{device_error}）'
        msg += '。请确认 MV-CB013 USB 已插入，且未在 MVS / 网页端占用。'
        lines.append(msg)
    ready = not failed  # camera optional for App start
    camera_ready = bool(devices)
    return {
        'ok': ready,
        'camera_ready': camera_ready,
        'failed': failed,
        'devices': devices,
        'message': '\n'.join(lines),
        'short': lines[0] + (' · 相机就绪' if camera_ready else ' · 等待相机'),
    }


def run_check(root: Path | None = None) -> dict:
    items = check_dependencies(root)
    devices, err = enumerate_gentl_devices()
    return summarize(items, devices, err)


if __name__ == '__main__':
    report = run_check()
    print(report['message'])
    raise SystemExit(0 if report['ok'] else 1)
