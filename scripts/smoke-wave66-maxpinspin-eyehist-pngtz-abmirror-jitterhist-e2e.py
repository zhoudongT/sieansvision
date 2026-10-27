#!/usr/bin/env python3
"""细妆㊯：pin上限旋钮 · 吸管历史 · PNG时区偏移 · A/B锁定镜像 · jitter直方图."""
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog,
    )
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('%Y%m%d', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin',
        'stale_prune_undo_eyedropper_history',
        'remember_stale_prune_undo_eyedropper_history',
        'clear_stale_prune_undo_eyedropper_history',
        'apply_stale_prune_undo_eyedropper_history',
        'toast_curve_png_datetime_tz_offset_hours',
        'set_toast_curve_png_datetime_tz_offset_hours',
        'stale_prune_undo_color_scale_ab_mirror',
        'set_stale_prune_undo_color_scale_ab_mirror',
        'sample_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter',
        'render_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave66 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
    s.setValue('host/stalePruneUndoColorScaleAbLock', False)
    s.setValue('host/stalePruneUndoColorScaleAbMirror', False)
    s.setValue('host/stalePruneUndoEyedropperHistory', [])
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
    s.setValue('host/toastCurvePngNameTemplate', '{project}-{datetime}.png')
    s.setValue('host/toastCurvePngProjectName', 'default')
    s.setValue('host/toastCurvePngStationName', 'station1')
    s.setValue('host/toastCurvePngDatetimeFormat', '%Y-%m-%d_%H-%M-%S')
    s.setValue('host/toastCurvePngDatetimeTzOffsetHours', 0)
    s.setValue('host/sevPinSoloDeleteUndoMs', 4000)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
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

    # --- 1. pin max menu spin ---
    for hx in ('#aa66ff', '#ff6688', '#66ffaa'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#aa66ff')
    host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#ff6688')
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin() == 3
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    sp = getattr(host, '_last_snap_guide_recent_max_pin_spin', None)
    assert sp is not None
    assert sp.objectName() == 'hostSnapGuideRecentMaxPinSpin'
    assert sp.value() == 3
    sp.setValue(2)
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin() == 2
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_pin_count() <= 2
    badge = getattr(host, '_last_snap_guide_recent_pin_count_badge', None)
    assert badge is not None
    assert badge.property('snapGuideRecentMaxPin') == 2
    # actions include spin widgetaction
    spins = [a for a in menu_g.actions() if a.property('isSnapGuideRecentMaxPinSpin')]
    assert len(spins) >= 1
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    ok('pin 上限菜单旋钮')

    # --- 2. eyedropper history ---
    host.clear_stale_prune_undo_eyedropper_history()
    assert host.stale_prune_undo_eyedropper_history() == []
    host._stale_prune_undo_eyedropper_smoke = '#112233'
    host.pick_stale_prune_undo_color_custom_hex_eyedropper('hi')
    host._stale_prune_undo_eyedropper_smoke = '#445566'
    host.pick_stale_prune_undo_color_custom_hex_eyedropper('mid')
    hist = host.stale_prune_undo_eyedropper_history()
    assert hist[0] == '#445566' and '#112233' in hist, hist
    # remember dedupe to front
    host.remember_stale_prune_undo_eyedropper_history('#112233')
    assert host.stale_prune_undo_eyedropper_history()[0] == '#112233'
    got = host.apply_stale_prune_undo_eyedropper_history('#445566', which='lo')
    assert got == '#445566'
    assert host.stale_prune_undo_color_custom_rgb()['lo'] == '#445566'
    wrap = host._make_undo_color_scale_custom_hex_entry()
    row = getattr(host, '_last_undo_color_scale_eyedropper_history_row', None)
    assert row is not None and row.objectName() == 'hostUndoColorScaleEyedropperHistory'
    btns = getattr(host, '_last_undo_color_scale_eyedropper_history_btns', [])
    assert len(btns) >= 1
    host.clear_stale_prune_undo_eyedropper_history()
    assert host.stale_prune_undo_eyedropper_history() == []
    ok('eyedropper 历史色')

    # --- 3. PNG TZ offset ---
    assert host.toast_curve_png_datetime_tz_offset_hours() == 0
    assert host.set_toast_curve_png_datetime_tz_offset_hours(8) == 8
    assert host.set_toast_curve_png_datetime_tz_offset_hours(-20) == -12
    assert host.set_toast_curve_png_datetime_tz_offset_hours(99) == 14
    host.set_toast_curve_png_datetime_tz_offset_hours(3)
    host.set_toast_curve_png_datetime_format('%Y%m%d%H')
    base = datetime(2026, 10, 28, 10, 0, 0)
    # resolve with explicit when — offset applied inside
    name0 = host.resolve_toast_curve_png_name(when=base)
    # with +3h → hour 13
    assert '13' in name0 or datetime.strftime(base + timedelta(hours=3), '%Y%m%d%H') in name0, name0
    expected = (base + timedelta(hours=3)).strftime('%Y%m%d%H')
    assert expected in name0, (name0, expected)
    host.set_toast_curve_png_datetime_tz_offset_hours(0)
    name1 = host.resolve_toast_curve_png_name(when=base)
    assert base.strftime('%Y%m%d%H') in name1
    host._toast_curve_png_name_template_dialog_no_exec = False
    try:
        host.show_toast_curve_png_name_template_dialog(interactive=False)
    finally:
        host._toast_curve_png_name_template_dialog_no_exec = True
    tzsp = getattr(host, '_last_toast_curve_png_datetime_tz_offset_spin', None)
    assert tzsp is not None and tzsp.objectName() == 'hostToastCurvePngDatetimeTzOffsetSpin'
    ok('PNG 时区偏移')

    # --- 4. A/B lock mirror ---
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_stale_prune_undo_color_scale_compare_preset('sunset')
    # mirror alone without lock: no sync
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_preset('cool')
    assert host.stale_prune_undo_color_scale_compare_preset() == 'sunset'  # unchanged
    # lock + mirror: B follows A
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    assert host.stale_prune_undo_color_scale_compare_preset() == 'cool'  # synced on enable
    host.set_stale_prune_undo_color_scale_preset('mono')
    assert host.stale_prune_undo_color_scale_compare_preset() == 'mono'
    assert getattr(host, '_last_stale_prune_undo_color_scale_ab_mirrored') == 'mono'
    # swap still blocked
    swapped = host.swap_stale_prune_undo_color_scale_ab()
    assert swapped == ('mono', 'mono')
    menu = host._build_undo_color_scale_hot_sync_menu()
    mirs = [a for a in menu.actions() if a.property('isUndoColorScaleAbMirror')]
    assert len(mirs) == 1 and mirs[0].isChecked() and mirs[0].isEnabled()
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    ok('A/B 锁定镜像')

    # --- 5. jitter histogram ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(100)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    samples = host.sample_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter(64)
    assert len(samples) == 64
    assert all(0 <= x <= 100 for x in samples)
    # seeded → reproducible
    s2 = host.sample_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter(64)
    assert samples == s2
    txt = host.render_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist(samples)
    assert 'n=64' in txt and 'ms' in txt
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist_bins')
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    assert host.render_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist() == '（无抖动）'
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(80)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('gauss')
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    hl = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist_label', None)
    assert hl is not None and 'n=' in (hl.text() or '')
    btn = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist_refresh', None)
    assert btn is not None
    btn.click()
    assert 'n=' in (hl.text() or '')
    ok('jitter 直方图预览')

    # tidy
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(0)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_toast_curve_png_datetime_tz_offset_hours(0)
    host.set_toast_curve_png_datetime_format('iso')
    host.clear_stale_prune_undo_eyedropper_history()
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    host._merge_diff_fail_hist_drop_snap_guide_recent_pinned = []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)

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
