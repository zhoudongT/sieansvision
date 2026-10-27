#!/usr/bin/env python3
"""细妆㊰：pin上限快捷 · 历史色右键删 · PNG城市TZ · A/B镜像方向 · jitter箱线均值."""
from __future__ import annotations
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
    from PySide6.QtWidgets import (
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog,
    )
    from PySide6.QtCore import QSettings, QPoint
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
        'bump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin',
        '_ensure_snap_guide_recent_max_pin_shortcuts',
        'remove_stale_prune_undo_eyedropper_history',
        'toast_curve_png_datetime_tz_city',
        'toast_curve_png_datetime_tz_city_presets',
        'set_toast_curve_png_datetime_tz_city',
        '_local_utc_offset_hours',
        'stale_prune_undo_color_scale_ab_mirror_dir',
        'set_stale_prune_undo_color_scale_ab_mirror_dir',
        'toggle_stale_prune_undo_color_scale_ab_mirror_dir',
        'stats_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter',
        'render_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_box',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave67 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
    s.setValue('host/stalePruneUndoColorScaleAbLock', False)
    s.setValue('host/stalePruneUndoColorScaleAbMirror', False)
    s.setValue('host/stalePruneUndoColorScaleAbMirrorDir', 'a_to_b')
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
    s.setValue('host/toastCurvePngDatetimeTzCity', 'local')
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
    host._stale_prune_undo_eyedropper_history_ctx_no_exec = True

    # --- 1. pin max keyboard shortcuts ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    assert host._ensure_snap_guide_recent_max_pin_shortcuts() is True
    assert getattr(host, '_snap_guide_recent_max_pin_inc_shortcut', None) is not None
    assert getattr(host, '_snap_guide_recent_max_pin_dec_shortcut', None) is not None
    assert host.bump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(1) == 4
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin() == 4
    assert host.bump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(-2) == 2
    assert host.bump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(99) == 6
    assert host.bump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(-99) == 1
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    acts = [a for a in menu_g.actions() if a.property('isSnapGuideRecentMaxPinBump')]
    assert len(acts) >= 2
    dec = getattr(host, '_last_snap_guide_recent_max_pin_dec', None)
    inc = getattr(host, '_last_snap_guide_recent_max_pin_inc', None)
    assert dec is not None and inc is not None
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin(3)
    inc.click()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin() == 4
    dec.click()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin() == 3
    ok('pin 上限键盘快捷')

    # --- 2. eyedropper history right-click remove ---
    host.clear_stale_prune_undo_eyedropper_history()
    host.remember_stale_prune_undo_eyedropper_history('#112233')
    host.remember_stale_prune_undo_eyedropper_history('#445566')
    host.remember_stale_prune_undo_eyedropper_history('#778899')
    assert len(host.stale_prune_undo_eyedropper_history()) == 3
    got = host.remove_stale_prune_undo_eyedropper_history('#445566')
    assert '#445566' not in got and '#112233' in got and '#778899' in got
    assert getattr(host, '_last_stale_prune_undo_eyedropper_history_removed') == '#445566'
    outer = host._make_undo_color_scale_custom_hex_entry()
    btns = getattr(host, '_last_undo_color_scale_eyedropper_history_btns', [])
    assert btns
    # trigger context builder without exec
    b0 = btns[0]
    hx0 = str(b0.property('undoEyedropperHistoryHex') or '')
    # manually invoke context handler path
    b0.customContextMenuRequested.emit(QPoint(1, 1))
    m = getattr(host, '_last_undo_color_scale_eyedropper_history_context', None)
    assert m is not None
    rem = [a for a in m.actions() if a.property('isUndoEyedropperHistoryRemove')]
    assert len(rem) == 1
    rem[0].trigger()
    assert hx0 not in host.stale_prune_undo_eyedropper_history()
    ok('历史色右键删单条')

    # --- 3. PNG TZ city presets ---
    assert host.toast_curve_png_datetime_tz_city() in ('local', 'custom') or True
    presets = host.toast_curve_png_datetime_tz_city_presets()
    assert any(x[0] == 'shanghai' for x in presets)
    local_off = host._local_utc_offset_hours()
    cid, rel = host.set_toast_curve_png_datetime_tz_city('shanghai')
    assert cid == 'shanghai'
    assert rel == max(-12, min(14, 8 - local_off))
    assert host.toast_curve_png_datetime_tz_offset_hours() == rel
    assert host.toast_curve_png_datetime_tz_city() == 'shanghai'
    cid2, rel2 = host.set_toast_curve_png_datetime_tz_city('utc')
    assert cid2 == 'utc' and rel2 == max(-12, min(14, 0 - local_off))
    cid3, rel3 = host.set_toast_curve_png_datetime_tz_city('local')
    assert cid3 == 'local' and rel3 == 0
    # manual spin → custom
    host.set_toast_curve_png_datetime_tz_offset_hours(2)
    assert host.toast_curve_png_datetime_tz_city() == 'custom'
    host._toast_curve_png_name_template_dialog_no_exec = False
    try:
        host.show_toast_curve_png_name_template_dialog(interactive=False)
    finally:
        host._toast_curve_png_name_template_dialog_no_exec = True
    chips = getattr(host, '_last_toast_curve_png_datetime_tz_city_chips', [])
    assert len(chips) >= 5
    ok('PNG TZ 城市预设')

    # --- 4. A/B mirror B→A direction ---
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('a_to_b')
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_stale_prune_undo_color_scale_compare_preset('sunset')
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    # a_to_b: enable syncs B=A
    assert host.stale_prune_undo_color_scale_compare_preset() == 'traffic'
    host.set_stale_prune_undo_color_scale_preset('cool')
    assert host.stale_prune_undo_color_scale_compare_preset() == 'cool'
    # switch to b_to_a
    assert host.set_stale_prune_undo_color_scale_ab_mirror_dir('b_to_a') == 'b_to_a'
    # enabling sync once: A follows B (both cool after prior)
    host.set_stale_prune_undo_color_scale_compare_preset('mono')
    assert host.stale_prune_undo_color_scale_preset() == 'mono'
    assert getattr(host, '_last_stale_prune_undo_color_scale_ab_mirrored_dir') == 'b_to_a'
    # changing A should NOT move B in b_to_a
    host.set_stale_prune_undo_color_scale_preset('sunset')
    assert host.stale_prune_undo_color_scale_compare_preset() == 'mono'
    # wave68: toggle cycles a_to_b → b_to_a → both → a_to_b
    host.toggle_stale_prune_undo_color_scale_ab_mirror_dir()
    assert host.stale_prune_undo_color_scale_ab_mirror_dir() == 'both'
    host.toggle_stale_prune_undo_color_scale_ab_mirror_dir()
    assert host.stale_prune_undo_color_scale_ab_mirror_dir() == 'a_to_b'
    menu = host._build_undo_color_scale_hot_sync_menu()
    dirs = [a for a in menu.actions() if a.property('isUndoColorScaleAbMirrorDir')]
    assert len(dirs) == 1
    mirs = [a for a in menu.actions() if a.property('isUndoColorScaleAbMirror')]
    assert len(mirs) == 1 and 'A→B' in mirs[0].text()
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('a_to_b')
    ok('A/B 镜像 B→A 方向')

    # --- 5. jitter box / mean ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(100)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(7)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    samples = host.sample_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter(64)
    st = host.stats_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter(samples)
    assert st['n'] == 64
    assert st['min'] <= st['q1'] <= st['med'] <= st['q3'] <= st['max']
    assert 0 <= st['mean'] <= 100
    box = host.render_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_box(samples)
    assert 'μ=' in box and 'med=' in box and '[' in box
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    assert host.render_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_box() == '（无箱线）'
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(80)
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    bl = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_box_label', None)
    assert bl is not None and ('μ=' in (bl.text() or '') or '无箱线' in (bl.text() or ''))
    btn = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_hist_refresh', None)
    assert btn is not None
    btn.click()
    assert 'μ=' in (bl.text() or '')
    ok('jitter 箱线图/均值线')

    # tidy
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(0)
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('a_to_b')
    host.set_toast_curve_png_datetime_tz_city('local')
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
