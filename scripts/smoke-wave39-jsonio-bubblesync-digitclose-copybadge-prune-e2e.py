#!/usr/bin/env python3
"""细妆㊴：多档JSON导入导出 · 气泡弧同步 · Alt+H数字关 · 复制确认徽章 · 失效清理."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m, flush=True)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m, flush=True)

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
    from PySide6.QtCore import QSettings, Qt
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget, _SevChipPinProgressArc
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'export_alarm_film_csv_dirs_json', 'import_alarm_film_csv_dirs_json',
        'prune_stale_alarm_film_csv_dirs', 'stale_alarm_film_csv_dirs',
        'alarm_film_csv_dir_exists', 'flash_path_copy_badge',
        'sync_sev_bubble_pin_from_chip', '_show_sev_bubble_pin_arc',
        '_on_sev_bubble_pin_tick',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostSevBubblePinArc' in src and 'hostPathCopyBadge' in src
    assert 'isPruneStale' in src and 'isDirsExport' in src
    ok('wave39 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevChipPinMs', 550)
    s.setValue('host/sevChipPinArcColor', '#f0c040')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    tmp = Path('/tmp/sieans-w39s'); tmp.mkdir(exist_ok=True)
    d0, d1 = tmp / 'ok0', tmp / 'ok1'
    for d in (d0, d1):
        d.mkdir(exist_ok=True)
    stale = tmp / 'gone-dir'
    # ensure stale does NOT exist
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. JSON export/import ---
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(d1))
    host.set_alarm_film_csv_dirs_max(5)
    out_json = tmp / 'dirs.json'
    path = host.export_alarm_film_csv_dirs_json(str(out_json))
    assert path == str(out_json)
    data = json.loads(out_json.read_text(encoding='utf-8'))
    assert data.get('kind') == 'sieans.alarmFilmCsvDirs'
    assert data.get('max') == 5
    assert str(d1) in data.get('dirs', [])
    host.clear_alarm_film_csv_dirs()
    assert host.alarm_film_csv_dirs() == []
    # import from file
    got = host.import_alarm_film_csv_dirs_json(str(out_json))
    assert str(d1) in got and str(d0) in got
    # import from text
    host.clear_alarm_film_csv_dirs()
    text = json.dumps({'version': 1, 'max': 3, 'dirs': [str(d0), '/tmp']})
    got2 = host.import_alarm_film_csv_dirs_json(text)
    assert str(d0) in got2
    assert host.alarm_film_csv_dirs_max() == 3
    host.set_alarm_film_csv_dirs_max(5)
    # menu has export/import
    host._alarm_ctx_menu_no_exec = True
    menu = host._build_alarm_list_context_menu()
    found_ex = found_im = False
    for a in menu.actions():
        m = a.menu()
        if m is None or '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            if x.property('isDirsExport'):
                found_ex = True
            if x.property('isDirsImport'):
                found_im = True
    assert found_ex and found_im
    ok('多档记忆导出/导入 JSON')

    # --- 2. bubble arc sync ---
    host.set_sev_chip_pin_ms(300)
    host.set_sev_chip_pin_arc_color('#3ecf8e')
    assert host._sev_bubble_pin_ms == 300
    barc = host._sev_bubble_pin_arc
    assert isinstance(barc, _SevChipPinProgressArc)
    assert barc.color().lower() == '#3ecf8e'
    assert barc.objectName() == 'hostSevBubblePinArc'
    host.sync_sev_bubble_pin_from_chip()
    assert host._sev_bubble_pin_ms == host.sev_chip_pin_ms()
    host.pin_alarm_severity_filter(False)
    host._on_sev_bubble_press(None, 'warning')
    assert host._sev_bubble_pin_tick.isActive()
    host._on_sev_bubble_pin_tick()
    assert not barc.isHidden()
    assert barc._p > 0
    host._sev_bubble_pin_press_ms = 280
    host._on_sev_bubble_pin_tick()
    assert barc._p >= 0.9
    host._on_sev_bubble_long_press()
    assert host._alarm_sev_pinned_key == 'warning'
    host.set_sev_chip_pin_ms(550)
    host.set_sev_chip_pin_arc_color('#f0c040')
    ok('进度弧气泡同步')

    # --- 3. Alt+H digit auto-close ---
    host.set_liaison_toast_history_max(5, persist=False)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._on_toast_hist_cap_hotkey()
    host._last_toast_hist_cap_menu = menu
    host._last_toast_hist_cap_closed_by = ''
    r = host.toast_hist_cap_menu_key(Qt.Key.Key_3, menu)
    assert r == ('digit', 8), r
    assert host._liaison_toast_history_max == 8
    assert getattr(host, '_last_toast_hist_cap_closed_by', '') == 'digit'
    assert getattr(host, '_last_toast_hist_cap_digit', 0) == 8
    # digit 2 → 5
    host.toast_hist_cap_menu_key(Qt.Key.Key_2, menu)
    assert host._liaison_toast_history_max == 5
    host.set_liaison_toast_history_max(5, persist=True)
    ok('Alt+H 数字键直达后自动关')

    # --- 4. path copy confirm badge ---
    host._flash_open_dir_ok_tip(str(tmp), soft=False)
    host.review_host_toast_path()
    badge = host._path_copy_badge
    assert badge is not None
    assert badge.objectName() == 'hostPathCopyBadge'
    assert not badge.isHidden() or '已复制' in (getattr(host, '_last_path_copy_badge_text', '') or '')
    txt = badge.text() or getattr(host, '_last_path_copy_badge_text', '') or ''
    assert '已复制' in txt or '✓' in txt
    # direct API
    host._hide_path_copy_badge()
    assert host.flash_path_copy_badge(str(tmp))
    assert '已复制' in (host._path_copy_badge.text() or host._last_path_copy_badge_text)
    ok('路径回看 tip 复制确认徽章')

    # --- 5. stale gray + prune ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))  # nonexistent
    host.remember_alarm_film_csv_dir(str(d1))
    assert not host.alarm_film_csv_dir_exists(str(stale))
    st = host.stale_alarm_film_csv_dirs()
    assert str(stale) in st
    menu = host._build_alarm_list_context_menu()
    found_stale_title = found_prune = False
    for a in menu.actions():
        m = a.menu()
        if m is None or '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            if x.property('isPruneStale'):
                found_prune = True
                assert x.isEnabled()
            sm = x.menu()
            if sm is not None and '失效' in (x.text() or ''):
                found_stale_title = True
                # save should be disabled
                for y in sm.actions():
                    if y.property('isRecentSave'):
                        assert not y.isEnabled()
    assert found_stale_title and found_prune
    kept = host.prune_stale_alarm_film_csv_dirs()
    assert str(stale) not in kept
    assert str(d0) in kept and str(d1) in kept
    assert '清理' in (host._liaison_hotkey_toast.text() or '') or '失效' in (host._liaison_hotkey_toast.text() or '')
    ok('最近另存失效目录灰显/一键清理')

    print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad(f'exception: {exc}')
        print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
        raise SystemExit(1)
