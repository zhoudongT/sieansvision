#!/usr/bin/env python3
"""细妆㊵：多档JSON合并导入 · 共享进度弧 · Alt+H长按H保持 · 徽章再点开目录 · 失效清理预览确认."""
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
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget, _SevChipPinProgressArc
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'merge_alarm_film_csv_dirs', 'merge_import_alarm_film_csv_dirs_json',
        'import_alarm_film_csv_dirs_json', 'preview_stale_alarm_film_csv_dirs',
        'prune_stale_alarm_film_csv_dirs', 'set_toast_hist_cap_keep_open',
        'begin_toast_hist_cap_hold', 'end_toast_hist_cap_hold',
        '_on_path_copy_badge_clicked', 'flash_path_copy_badge',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostSevPinArc' in src
    assert 'isDirsMergeImport' in src
    assert src.count('_SevChipPinProgressArc(self)') == 1
    ok('wave40 APIs / 共享弧单例源码')

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

    tmp = Path('/tmp/sieans-w40s'); tmp.mkdir(exist_ok=True)
    d0, d1, d2 = tmp / 'a0', tmp / 'a1', tmp / 'a2'
    for d in (d0, d1, d2):
        d.mkdir(exist_ok=True)
    stale = tmp / 'gone-w40'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. merge import (union, not overwrite) ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(d1))
    assert str(d0) in host.alarm_film_csv_dirs() and str(d1) in host.alarm_film_csv_dirs()
    payload = json.dumps({'version': 1, 'max': 5, 'dirs': [str(d2), str(d1)]})
    merged = host.merge_import_alarm_film_csv_dirs_json(payload)
    assert str(d2) in merged, merged
    assert str(d1) in merged and str(d0) in merged, merged
    # d2 should be near front (imported first)
    assert merged.index(str(d2)) < merged.index(str(d0)), merged
    assert getattr(host, '_last_alarm_film_csv_dirs_import_mode', '') == 'merge'
    # overwrite still works
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    replaced = host.import_alarm_film_csv_dirs_json(
        json.dumps({'max': 5, 'dirs': [str(d2)]}), merge=False)
    assert replaced == [str(d2)] or (str(d2) in replaced and str(d0) not in replaced), replaced
    assert getattr(host, '_last_alarm_film_csv_dirs_import_mode', '') == 'replace'
    # menu merge action
    host._alarm_ctx_menu_no_exec = True
    menu = host._build_alarm_list_context_menu()
    found_merge = False
    for a in menu.actions():
        m = a.menu()
        if m is None or '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            if x.property('isDirsMergeImport'):
                found_merge = True
                assert '合并' in (x.text() or '')
    assert found_merge
    ok('多档 JSON 合并导入（去重并集）')

    # --- 2. shared pin arc singleton ---
    arc = host._sev_pin_arc
    assert isinstance(arc, _SevChipPinProgressArc)
    assert arc is host._sev_chip_pin_arc
    assert arc is host._sev_bubble_pin_arc
    assert arc.objectName() == 'hostSevPinArc'
    host.set_sev_chip_pin_arc_color('#3ecf8e')
    assert arc.color().lower() == '#3ecf8e'
    host.set_sev_chip_pin_ms(300)
    host.pin_alarm_severity_filter(False)
    host._on_sev_chip_press(None, 'error')
    assert host._sev_chip_pin_tick.isActive()
    host._on_sev_chip_pin_tick()
    assert getattr(host, '_sev_pin_arc_owner', '') == 'chip'
    host._sev_chip_pin_tick.stop()
    host._hide_sev_chip_pin_arc()
    host._on_sev_bubble_press(None, 'warning')
    assert host._sev_bubble_pin_tick.isActive()
    host._on_sev_bubble_pin_tick()
    assert getattr(host, '_sev_pin_arc_owner', '') == 'bubble'
    assert host._sev_bubble_pin_arc is host._sev_chip_pin_arc
    host._sev_bubble_pin_tick.stop()
    host._hide_sev_bubble_pin_arc()
    host.set_sev_chip_pin_ms(550)
    host.set_sev_chip_pin_arc_color('#f0c040')
    ok('气泡/芯片共享 overlay 单例')

    # --- 3. Alt+H hold H keep menu open ---
    host.set_liaison_toast_history_max(5, persist=False)
    host._toast_hist_cap_menu_no_exec = True
    host._toast_hist_cap_keep_open = False
    menu = host._on_toast_hist_cap_hotkey()
    host._last_toast_hist_cap_menu = menu
    # without hold → digit closes
    host._last_toast_hist_cap_closed_by = ''
    r = host.toast_hist_cap_menu_key(Qt.Key.Key_3, menu)
    assert r == ('digit', 8), r
    assert host._last_toast_hist_cap_closed_by == 'digit'
    # with keep_open → digit applies but does not close
    menu2 = host._on_toast_hist_cap_hotkey()
    host._last_toast_hist_cap_menu = menu2
    host.set_toast_hist_cap_keep_open(True)
    host._last_toast_hist_cap_closed_by = ''
    r2 = host.toast_hist_cap_menu_key(Qt.Key.Key_1, menu2)
    assert r2 == ('digit-hold', 3), r2
    assert host._liaison_toast_history_max == 3
    assert host._last_toast_hist_cap_closed_by == 'digit-hold'
    assert host._toast_hist_cap_keep_open is True
    # hold fire path
    host.begin_toast_hist_cap_hold()
    assert host._toast_hist_cap_h_down
    host._on_toast_hist_cap_hold_fire()
    assert host._toast_hist_cap_keep_open is True
    assert getattr(host, '_last_toast_hist_cap_hold', False)
    # Esc clears keep
    host.toast_hist_cap_menu_key(Qt.Key.Key_Escape, menu2)
    assert host._toast_hist_cap_keep_open is False
    host.set_liaison_toast_history_max(5, persist=True)
    ok('Alt+H 长按 H 保持菜单不关')

    # --- 4. copy badge click → open dir ---
    host._hide_path_copy_badge()
    assert host.flash_path_copy_badge(str(tmp))
    badge = host._path_copy_badge
    assert badge is not None
    txt = badge.text() or getattr(host, '_last_path_copy_badge_text', '') or ''
    assert '再点打开' in txt
    assert getattr(host, '_path_copy_badge_path', '') == str(tmp)
    # open_host_toast_path may soft-fail on openUrl; stub to True via attribute path
    opened = {'n': 0}
    real_open = host.open_host_toast_path
    def _fake_open():
        opened['n'] += 1
        return True
    host.open_host_toast_path = _fake_open
    host._on_path_copy_badge_clicked()
    assert opened['n'] == 1
    host.open_host_toast_path = real_open
    ok('复制徽章再点打开目录')

    # --- 5. prune preview confirm ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.remember_alarm_film_csv_dir(str(d1))
    prev = host.preview_stale_alarm_film_csv_dirs()
    assert str(stale) in prev
    # cancel path
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel)
    before = list(host.alarm_film_csv_dirs())
    kept_cancel = host.prune_stale_alarm_film_csv_dirs(confirm=True)
    assert kept_cancel == before
    assert getattr(host, '_last_stale_prune_confirmed', True) is False
    assert str(stale) in kept_cancel
    # confirm Ok
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    kept = host.prune_stale_alarm_film_csv_dirs(confirm=True)
    assert str(stale) not in kept
    assert str(d0) in kept and str(d1) in kept
    assert getattr(host, '_last_stale_prune_confirmed', False) is True
    # no_confirm / confirm=False for smoke
    host.remember_alarm_film_csv_dir(str(stale))
    kept2 = host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert str(stale) not in kept2
    # menu tip
    menu = host._build_alarm_list_context_menu()
    found_prune = False
    for a in menu.actions():
        m = a.menu()
        if m is None or '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            if x.property('isPruneStale'):
                found_prune = True
                assert '…' in (x.text() or '') or '预览' in (x.toolTip() or '')
    assert found_prune
    ok('失效清理预览清单确认')

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
