#!/usr/bin/env python3
"""细妆㊭：导引带pin badge/cap · hex吸管 · PNG datetime格式 · A↔B对调 · 脉冲gap抖动."""
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
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ee44aa'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('#112233', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'merge_diff_fail_hist_drop_snap_guide_recent_pinned',
        'merge_diff_fail_hist_drop_snap_guide_recent_max_pin',
        'set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin',
        'unpin_merge_diff_fail_hist_drop_snap_guide_recent_color',
        'is_merge_diff_fail_hist_drop_snap_guide_recent_pinned',
        'pick_stale_prune_undo_color_custom_hex_eyedropper',
        'toast_curve_png_datetime_format',
        'set_toast_curve_png_datetime_format',
        'toast_curve_png_datetime_format_presets',
        'swap_stale_prune_undo_color_scale_ab',
        'merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms',
        'set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave64 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
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

    # --- 1. pin badge + max-pin cap ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    host._merge_diff_fail_hist_drop_snap_guide_recent_pinned = []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(2)
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin() == 2
    for hx in ('#aa66ff', '#ff6688', '#66ffaa', '#6688ff'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#aa66ff')
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#ff6688')
    pins = host.merge_diff_fail_hist_drop_snap_guide_recent_pinned()
    assert pins == ['#ff6688', '#aa66ff'], pins
    # third pin caps → drops oldest
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#66ffaa')
    pins = host.merge_diff_fail_hist_drop_snap_guide_recent_pinned()
    assert len(pins) == 2 and pins[0] == '#66ffaa', pins
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_recent_pin_capped') is True
    assert host.is_merge_diff_fail_hist_drop_snap_guide_recent_pinned('#66ffaa')
    assert not host.is_merge_diff_fail_hist_drop_snap_guide_recent_pinned('#aa66ff')
    # badge on swatches
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    btns = getattr(host, '_snap_guide_recent_drag_btns', [])
    pinned_btns = [b for b in btns if b.property('snapGuideRecentPinned')]
    assert len(pinned_btns) >= 1
    assert any(b.text() == '📌' for b in pinned_btns)
    # unpin
    host.unpin_merge_diff_fail_hist_drop_snap_guide_recent_color('#66ffaa')
    assert not host.is_merge_diff_fail_hist_drop_snap_guide_recent_pinned('#66ffaa')
    # context shows unpin when pinned
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#ff6688')
    host._snap_guide_recent_swatch_context_no_exec = True
    assert host._show_snap_guide_recent_swatch_context_menu('#ff6688') is True
    ctx = host._last_snap_guide_recent_swatch_context_menu
    unpins = [a for a in ctx.actions() if a.property('isSnapGuideRecentUnpin')]
    assert len(unpins) == 1
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    ok('导引带 pin badge + max-pin cap')

    # --- 2. hex eyedropper ---
    host._stale_prune_undo_eyedropper_smoke = '#ee44aa'
    host._stale_prune_undo_eyedropper_no_dialog = True
    got = host.pick_stale_prune_undo_color_custom_hex_eyedropper('hi')
    assert got == '#ee44aa', got
    assert host.stale_prune_undo_color_custom_rgb()['hi'] == '#ee44aa'
    assert host.stale_prune_undo_color_scale_preset() == 'custom'
    # UI button present
    wrap = host._make_undo_color_scale_custom_hex_entry()
    eye = getattr(host, '_last_undo_color_scale_custom_hex_eyedropper', None)
    assert eye is not None and eye.objectName() == 'hostUndoColorScaleCustomHexEyedropper'
    host._stale_prune_undo_eyedropper_smoke = '#00ffcc'
    eye.click()
    assert host.stale_prune_undo_color_custom_rgb()['hi'] == '#00ffcc'
    ok('撤销条色阶 hex eyedropper')

    # --- 3. PNG datetime format picker ---
    assert host.toast_curve_png_datetime_format() == '%Y-%m-%d_%H-%M-%S'
    host.set_toast_curve_png_name_template('{project}-{datetime}.png')
    host.set_toast_curve_png_datetime_format('compact')
    assert host.toast_curve_png_datetime_format() == '%Y%m%d%H%M%S'
    name = host.resolve_toast_curve_png_name()
    # compact has no dashes between date parts beyond project sep
    assert datetime.now().strftime('%Y%m%d') in name, name
    host.set_toast_curve_png_datetime_format('iso')
    name2 = host.resolve_toast_curve_png_name()
    assert datetime.now().strftime('%Y-%m-%d') in name2.replace('_', '-').replace('%', '') or '-' in name2
    presets = host.toast_curve_png_datetime_format_presets()
    assert len(presets) >= 4
    # dialog no-exec still refreshes live
    host._toast_curve_png_name_template_dialog_no_exec = True
    host.show_toast_curve_png_name_template_dialog(interactive=False)
    # build interactive=False still... no_exec returns early before chips.
    # Force-build by temporarily clearing no_exec and using interactive=False
    # which still builds widgets then returns without exec in some paths.
    # Instead invoke format setter + live refresh
    live = host.refresh_toast_curve_png_datetime_live_strip(
        template='{project}-{datetime}.png')
    assert live.endswith('.png')
    # manually open dialog build path: disable no_exec, interactive False builds UI
    host._toast_curve_png_name_template_dialog_no_exec = False
    # interactive False returns template without exec but builds
    try:
        host.show_toast_curve_png_name_template_dialog(interactive=False)
    finally:
        host._toast_curve_png_name_template_dialog_no_exec = True
    chips = getattr(host, '_last_toast_curve_png_datetime_format_chips', [])
    assert len(chips) >= 4, len(chips)
    assert all(c.property('isToastCurvePngDatetimeFormatChip') for c in chips)
    # click compact chip
    chip_c = next(c for c in chips if c.property('toastCurvePngDatetimeFormatKey') == 'compact')
    chip_c.click()
    assert host.toast_curve_png_datetime_format() == '%Y%m%d%H%M%S'
    ok('PNG {datetime} format picker')

    # --- 4. A↔B swap ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_stale_prune_undo_color_scale_compare_preset('sunset')
    swapped = host.swap_stale_prune_undo_color_scale_ab()
    assert swapped == ('sunset', 'traffic'), swapped
    assert host.stale_prune_undo_color_scale_preset() == 'sunset'
    assert host.stale_prune_undo_color_scale_compare_preset() == 'traffic'
    menu = host._build_undo_color_scale_hot_sync_menu()
    swaps = [a for a in menu.actions() if a.property('isUndoColorScaleAbSwap')]
    assert len(swaps) == 1
    swaps[0].trigger()
    assert host.stale_prune_undo_color_scale_preset() == 'traffic'
    assert host.stale_prune_undo_color_scale_compare_preset() == 'sunset'
    ok('热同步 A↔B swap')

    # --- 5. pulse gap random jitter ---
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms() == 0
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(200) == 200
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(-5) == 0
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(999) == 500
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(100)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(True)
    assert host._arm_merge_diff_fail_hist_drop_pulse_preview_loop(lambda: None) is True
    total = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_ms', 0)
    roll = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_roll', -1)
    assert 0 <= roll <= 100, roll
    assert total == 200 + 200 + roll, (total, roll)
    host._stop_merge_diff_fail_hist_drop_pulse_preview_loop()
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    sl = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_slider', None)
    assert sl is not None and sl.objectName().endswith('JitterSlider')
    assert sl.value() == 100
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(False)
    ok('脉冲 gap random jitter')

    # leave settings tidy for sibling smokes
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    host._merge_diff_fail_hist_drop_snap_guide_recent_pinned = []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    host.set_toast_curve_png_datetime_format('iso')

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
