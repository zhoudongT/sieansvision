#!/usr/bin/env python3
"""细妆㊮：pin拖序+计数角标 · eyedropper mid/lo · PNG自定义strftime · A/B锁定 · 脉冲jitter分布/种子."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m, flush=True)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m, flush=True)

def main():
    from PySide6.QtWidgets import (
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog,
    )
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#aabbcc'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('%Y%m%d_%H%M', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'reorder_merge_diff_fail_hist_drop_snap_guide_recent_pinned',
        'merge_diff_fail_hist_drop_snap_guide_recent_pin_count',
        'pick_stale_prune_undo_color_custom_hex_eyedropper',
        'prompt_toast_curve_png_datetime_custom_strftime',
        'stale_prune_undo_color_scale_ab_lock',
        'set_stale_prune_undo_color_scale_ab_lock',
        'toggle_stale_prune_undo_color_scale_ab_lock',
        'merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist',
        'set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist',
        'merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed',
        'set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed',
        '_roll_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave65 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
    s.setValue('host/stalePruneUndoColorScaleAbLock', False)
    s.setValue('host/stalePruneUndoColorCustomAlpha', 160)
    s.setValue('host/stalePruneUndoColorCustomAlphaStep', 10)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffFailHistGroupOrder', [])
    s.setValue('host/mergeDiffFailHistCollapsed', [])
    s.setValue('host/mergeDiffFailHistDropSnapThresh', 18)
    s.setValue('host/mergeDiffFailHistDropPulseMs', 280)
    s.setValue('host/mergeDiffFailHistDropPulseEasing', 'OutCubic')
    s.setValue('host/mergeDiffFailHistDropPulseIntensityPct', 100)
    s.setValue('host/mergeDiffFailHistDropSnapGuidePreset', 'green')
    s.setValue('host/mergeDiffFailHistDropSnapGuideAlphaPct', 12)
    s.setValue('host/mergeDiffFailHistDropSnapGuideCustomHex', '#3ecf8e')
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentColors', [])
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentPinned', [])
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPin', 3)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapMs', 120)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterMs', 0)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterDist', 'uniform')
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeed', 0)
    s.setValue('host/toastCurvePngExportDir', '')
    s.setValue('host/toastCurvePngRecentExports', [])
    s.setValue('host/toastCurvePngNameTemplate', 'tip-anim-{easing}-{ts}.png')
    s.setValue('host/toastCurvePngProjectName', 'default')
    s.setValue('host/toastCurvePngStationName', 'station1')
    s.setValue('host/toastCurvePngDatetimeFormat', '%Y-%m-%d_%H-%M-%S')
    s.setValue('host/sevPinSoloDeleteUndoMs', 4000)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
    host._toast_hist_cap_tip_anim_curve_clipboard_toast_quiet = False
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_no_exec = True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_no_dialog = True
    host._toast_curve_png_recent_exports_menu_no_exec = True
    host._toast_curve_png_name_template_dialog_no_exec = True
    host._toast_curve_png_datetime_custom_no_dialog = True
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._stale_prune_undo_custom_hex_no_dialog = True
    host._stale_prune_undo_eyedropper_no_dialog = True
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._path_copy_badge_fail_hist_undo_bar_menu_no_exec = True
    host._merge_diff_fail_hist_no_exec = True
    host._stale_prune_undo_step_menu_no_exec = True
    host._snap_guide_custom_color_no_dialog = True
    host._snap_guide_recent_swatch_context_no_exec = True
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True

    # --- 1. pin list drag reorder + count badge ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    host._merge_diff_fail_hist_drop_snap_guide_recent_pinned = []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    for hx in ('#aa66ff', '#ff6688', '#66ffaa', '#6688ff'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#aa66ff')
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#ff6688')
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#66ffaa')
    pins = host.merge_diff_fail_hist_drop_snap_guide_recent_pinned()
    assert pins == ['#66ffaa', '#ff6688', '#aa66ff'], pins
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_pin_count() == 3
    # reorder pins: move oldest to front
    reo = host.reorder_merge_diff_fail_hist_drop_snap_guide_recent_pinned(
        ['#aa66ff', '#66ffaa', '#ff6688'])
    assert reo == ['#aa66ff', '#66ffaa', '#ff6688'], reo
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_pinned()[0] == '#aa66ff'
    # overall recent keeps pins first
    colors = host.merge_diff_fail_hist_drop_snap_guide_recent_colors()
    assert colors[:3] == ['#aa66ff', '#66ffaa', '#ff6688'], colors
    # badge UI
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    badge = getattr(host, '_last_snap_guide_recent_pin_count_badge', None)
    assert badge is not None
    assert badge.property('snapGuideRecentPinCount') == 3
    assert '📌3/3' in badge.text()
    btns = getattr(host, '_snap_guide_recent_drag_btns', [])
    pinned_btns = [b for b in btns if b.property('snapGuideRecentPinned')]
    assert len(pinned_btns) == 3
    idxs = sorted(b.property('snapGuideRecentPinIndex') for b in pinned_btns)
    assert idxs == [1, 2, 3], idxs
    assert any('📌1' in (b.text() or '') for b in pinned_btns)
    ok('pin 列表内拖序 + 计数角标')

    # --- 2. eyedropper mid/lo ---
    host._stale_prune_undo_eyedropper_no_dialog = True
    host._stale_prune_undo_eyedropper_smoke = '#112233'
    assert host.pick_stale_prune_undo_color_custom_hex_eyedropper('mid') == '#112233'
    assert host.stale_prune_undo_color_custom_rgb()['mid'] == '#112233'
    assert getattr(host, '_last_stale_prune_undo_color_eyedropper_which') == 'mid'
    host._stale_prune_undo_eyedropper_smoke = '#445566'
    assert host.pick_stale_prune_undo_color_custom_hex_eyedropper('lo') == '#445566'
    assert host.stale_prune_undo_color_custom_rgb()['lo'] == '#445566'
    wrap = host._make_undo_color_scale_custom_hex_entry()
    mid_btn = getattr(host, '_last_undo_color_scale_custom_hex_eyedropper_mid', None)
    lo_btn = getattr(host, '_last_undo_color_scale_custom_hex_eyedropper_lo', None)
    assert mid_btn is not None and mid_btn.property('undoColorScaleEyedropperWhich') == 'mid'
    assert lo_btn is not None and lo_btn.property('undoColorScaleEyedropperWhich') == 'lo'
    host._stale_prune_undo_eyedropper_smoke = '#778899'
    mid_btn.click()
    assert host.stale_prune_undo_color_custom_rgb()['mid'] == '#778899'
    host._stale_prune_undo_eyedropper_smoke = '#99aabb'
    lo_btn.click()
    assert host.stale_prune_undo_color_custom_rgb()['lo'] == '#99aabb'
    ok('eyedropper mid/lo')

    # --- 3. PNG custom strftime ---
    host._toast_curve_png_datetime_custom_no_dialog = True
    host._toast_curve_png_datetime_custom_smoke = '%Y%m%d_%H%M'
    got = host.prompt_toast_curve_png_datetime_custom_strftime()
    assert got == '%Y%m%d_%H%M', got
    assert host.toast_curve_png_datetime_format() == '%Y%m%d_%H%M'
    assert getattr(host, '_toast_curve_png_datetime_format_is_custom') is True
    host.set_toast_curve_png_name_template('{project}-{datetime}.png')
    name = host.resolve_toast_curve_png_name()
    assert datetime.now().strftime('%Y%m%d') in name, name
    # dialog chips include custom
    host._toast_curve_png_name_template_dialog_no_exec = False
    try:
        host.show_toast_curve_png_name_template_dialog(interactive=False)
    finally:
        host._toast_curve_png_name_template_dialog_no_exec = True
    chips = getattr(host, '_last_toast_curve_png_datetime_format_chips', [])
    keys = [c.property('toastCurvePngDatetimeFormatKey') for c in chips]
    assert 'custom' in keys, keys
    # click custom chip uses smoke
    host._toast_curve_png_datetime_custom_smoke = '%H-%M-%S'
    chip_c = next(c for c in chips if c.property('toastCurvePngDatetimeFormatKey') == 'custom')
    chip_c.click()
    assert host.toast_curve_png_datetime_format() == '%H-%M-%S'
    # invalid falls back
    host.set_toast_curve_png_datetime_format('%bogus')
    # %bogus may still "work" as literal in strftime... use truly bad
    # empty / no percent -> iso
    assert host.set_toast_curve_png_datetime_format('nopercent') == '%Y-%m-%d_%H-%M-%S'
    ok('PNG 自定义 strftime')

    # --- 4. A/B lock ---
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_stale_prune_undo_color_scale_compare_preset('sunset')
    assert host.set_stale_prune_undo_color_scale_ab_lock(True) is True
    swapped = host.swap_stale_prune_undo_color_scale_ab()
    assert swapped == ('traffic', 'sunset'), swapped  # unchanged
    assert getattr(host, '_last_stale_prune_undo_color_scale_ab_swap_blocked') is True
    assert host.stale_prune_undo_color_scale_preset() == 'traffic'
    assert host.stale_prune_undo_color_scale_compare_preset() == 'sunset'
    menu = host._build_undo_color_scale_hot_sync_menu()
    locks = [a for a in menu.actions() if a.property('isUndoColorScaleAbLock')]
    swaps = [a for a in menu.actions() if a.property('isUndoColorScaleAbSwap')]
    assert len(locks) == 1 and locks[0].isChecked()
    assert len(swaps) == 1 and not swaps[0].isEnabled()
    host.toggle_stale_prune_undo_color_scale_ab_lock()
    assert host.stale_prune_undo_color_scale_ab_lock() is False
    swapped2 = host.swap_stale_prune_undo_color_scale_ab()
    assert swapped2 == ('sunset', 'traffic'), swapped2
    ok('热同步 A/B 锁定')

    # --- 5. pulse jitter dist/seed ---
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist() == 'uniform'
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('gauss') == 'gauss'
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('gaussian') == 'gauss'
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('nope') == 'uniform'
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('triangular')
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42) == 42
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(-1) == 0
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(9999999) == 999999
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(100)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(7)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    r1 = host._roll_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter()
    r2 = host._roll_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter()
    assert r1 == r2  # seeded → reproducible (same Random(7) each call — wait, each call creates new Random(7) so first randint is same)
    assert 0 <= r1 <= 100
    host.set_merge_diff_fail_hist_drop_pulse_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(True)
    assert host._arm_merge_diff_fail_hist_drop_pulse_preview_loop(lambda: None) is True
    total = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_ms', 0)
    roll = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_roll', -1)
    assert total == 200 + 200 + roll
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist_used') == 'uniform'
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_used') == 7
    host._stop_merge_diff_fail_hist_drop_pulse_preview_loop()
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    dist_chips = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist_chips', [])
    assert len(dist_chips) == 3
    seed_sp = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_spin', None)
    assert seed_sp is not None and seed_sp.value() == 7
    # click gauss chip
    gchip = next(c for c in dist_chips if c.property('pulseLoopGapJitterDist') == 'gauss')
    gchip.click()
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist() == 'gauss'
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(False)
    ok('脉冲 jitter 分布/种子')

    # tidy
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(0)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_toast_curve_png_datetime_format('iso')
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    host._merge_diff_fail_hist_drop_snap_guide_recent_pinned = []

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
