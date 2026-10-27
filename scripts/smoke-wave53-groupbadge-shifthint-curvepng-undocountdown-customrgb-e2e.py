#!/usr/bin/env python3
"""细妆㊢：失败历史组头计数徽章 · Shift连选提示 · 曲线导出PNG · 徽章撤销倒计时 · undo色阶自定义RGB."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m, flush=True)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m, flush=True)

def main():
    from PySide6.QtWidgets import (
        QApplication, QMessageBox, QFileDialog, QColorDialog,
    )
    from PySide6.QtCore import QSettings, Qt, QEvent
    from PySide6.QtGui import QKeyEvent, QColor
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor())

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        '_merge_diff_fail_hist_group_count_badge_icon',
        '_show_sev_pin_arc_seize_recent_shift_hint',
        'export_toast_hist_cap_tip_anim_easing_curve_png',
        'path_copy_badge_fail_history_undo_left_ms',
        '_on_path_copy_badge_fail_history_undo_tick',
        '_expire_path_copy_badge_fail_history_undo',
        'set_stale_prune_undo_color_custom_rgb',
        'stale_prune_undo_color_custom_rgb',
        'prompt_stale_prune_undo_color_custom_rgb',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'Shift连选' in src or 'Shift 连选' in src
    assert 'hostToastTipAnimEasingCurveExportPng' in src
    assert 'isUndoColorScaleCustomRgb' in src
    ok('wave53 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimMs', 320)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoExtendStepMs', 0)
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorCustomHi', '#112233')
    s.setValue('host/stalePruneUndoColorCustomMid', '#445566')
    s.setValue('host/stalePruneUndoColorCustomLo', '#778899')
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffBatchFailLast', [])
    s.setValue('host/mergeDiffBatchFailHistorySort', 'time')
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._merge_diff_fail_hist_no_exec = True

    tmp = Path('/tmp/sieans-w53s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w53'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)
    png_out = tmp / 'curve-w53.png'
    if png_out.exists():
        png_out.unlink()

    # --- 1. group header count badge ---
    now = datetime.now()
    day0 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = now.strftime('%Y-%m-%d %H:%M:%S')
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w53-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w53-d1/b']},
        {'ts': day1, 'paths': ['/tmp/w53-d1/c']},
        {'ts': day1, 'paths': ['/tmp/w53-d1/d']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    assert lst is not None
    hdrs = []
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdrs.append(it)
    assert len(hdrs) >= 2
    # day1 has 3 batches → badge n
    counts = [int(h.data(Qt.ItemDataRole.UserRole + 4) or 0) for h in hdrs]
    assert max(counts) >= 3
    assert any(not h.icon().isNull() for h in hdrs)
    icon = host._merge_diff_fail_hist_group_count_badge_icon(7)
    assert not icon.isNull()
    assert getattr(host, '_last_merge_diff_fail_hist_group_badge_icon_n', 0) == 7
    ok('失败历史 组头计数徽章')

    # --- 2. Shift range-select hint ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ee0001', '#ee0002', '#ee0003'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_hint', False) is True
    tip0 = drag.item(0).toolTip()
    assert 'Shift' in tip0
    msg = host._show_sev_pin_arc_seize_recent_shift_hint(drag, n=2)
    assert 'Shift' in msg and '2' in msg
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_hint_n', 0) == 2
    ev_sh = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Shift,
        Qt.KeyboardModifier.ShiftModifier)
    drag.keyPressEvent(ev_sh)
    assert 'Shift' in (getattr(host, '_last_sev_pin_arc_seize_recent_shift_hint_text', '') or '')
    ok('拖拽 Shift 连选提示')

    # --- 3. curve export PNG ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    btn = getattr(host, '_last_toast_hist_cap_tip_anim_curve_export_btn', None)
    assert btn is not None and btn.objectName() == 'hostToastTipAnimEasingCurveExportPng'
    host._toast_hist_cap_tip_anim_curve_png_path = str(png_out)
    got = host.export_toast_hist_cap_tip_anim_easing_curve_png(str(png_out))
    assert got == str(png_out)
    assert png_out.exists() and png_out.stat().st_size > 100
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_png', '') == str(png_out)
    ok('曲线 导出 PNG')

    # --- 4. badge undo countdown ---
    host._merge_diff_batch_fail_history = [
        {'ts': day1, 'paths': ['/tmp/w53-undo/a']},
        {'ts': day0, 'paths': ['/tmp/w53-undo/b']},
    ]
    host._path_copy_badge_fail_history_can_undo = False
    host._path_copy_badge_fail_history_undo = None
    host._path_copy_badge_fail_history_undo_left_ms = 0
    host._path_copy_badge_fail_history_undo_ms = 2000
    host._last_path_copy_badge_fail_history_undo_expired = False
    snap = host.clear_path_copy_badge_fail_history(confirm=False)
    assert len(snap) == 2
    assert host.can_undo_path_copy_badge_fail_history_clear() is True
    left0 = host.path_copy_badge_fail_history_undo_left_ms()
    assert left0 > 0
    menu = host._build_path_copy_badge_menu()
    undo_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFailHistoryUndo')]
    assert len(undo_acts) == 1 and undo_acts[0].isEnabled()
    assert 's' in undo_acts[0].text()
    # force expire
    host._path_copy_badge_fail_history_undo_left_ms = 250
    host._on_path_copy_badge_fail_history_undo_tick()
    assert host.can_undo_path_copy_badge_fail_history_clear() is False
    assert getattr(host, '_last_path_copy_badge_fail_history_undo_expired', False) is True
    # clear again and undo before expire
    host._merge_diff_batch_fail_history = list(snap)
    host._path_copy_badge_fail_history_undo_ms = 8000
    host.clear_path_copy_badge_fail_history(confirm=False)
    assert host.can_undo_path_copy_badge_fail_history_clear() is True
    restored = host.undo_path_copy_badge_fail_history_clear()
    assert len(restored) == 2
    assert host.path_copy_badge_fail_history_undo_left_ms() == 0
    ok('徽章撤销 倒计时')

    # --- 5. undo custom RGB ---
    # settings were set before construct; re-apply
    got_rgb = host.set_stale_prune_undo_color_custom_rgb(
        '#aa1122', '#bb3344', '#cc5566')
    assert got_rgb['hi'] == '#aa1122'
    assert host.stale_prune_undo_color_scale_preset() == 'custom'
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(8000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    host._stale_prune_can_undo = True
    host._stale_prune_undo_left_ms = 8000
    host._show_stale_prune_undo_bar()
    host._update_stale_prune_undo_bar()
    assert getattr(host, '_last_stale_prune_undo_color_scale_used', '') == 'custom'
    chunk = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert (chunk == '#aa1122' or 'aa1122' in chunk.lower().replace('#','').replace(' ','')
            or '170,17,34' in chunk.replace(' ','') or '170, 17, 34' in chunk)
    host._stale_prune_undo_left_ms = 800
    host._update_stale_prune_undo_bar()
    chunk = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert (chunk == '#cc5566' or 'cc5566' in chunk.lower().replace('#','').replace(' ','')
            or '204,85,102' in chunk.replace(' ','') or '204, 85, 102' in chunk)
    host._stale_prune_undo_custom_rgb_hi = '#010203'
    host._stale_prune_undo_custom_rgb_mid = '#040506'
    host._stale_prune_undo_custom_rgb_lo = '#070809'
    prompted = host.prompt_stale_prune_undo_color_custom_rgb()
    assert prompted['hi'] == '#010203'
    host._stale_prune_undo_step_menu_no_exec = True
    menu = host._build_stale_prune_undo_step_menu()
    cs_acts = [a for a in menu.actions() if a.property('isUndoColorScalePreset')]
    assert len(cs_acts) == 5
    rgb_acts = [a for a in menu.actions() if a.property('isUndoColorScaleCustomRgb')]
    assert len(rgb_acts) == 1
    host.set_stale_prune_undo_color_scale_preset('traffic')
    ok('undo 色阶 自定义 RGB')

    print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad(f'exception: {exc}')
        raise SystemExit(1)
