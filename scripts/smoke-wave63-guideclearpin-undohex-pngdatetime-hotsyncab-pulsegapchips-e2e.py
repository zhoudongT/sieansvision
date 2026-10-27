#!/usr/bin/env python3
"""细妆㊬：导引带色板右键clear/pin · 撤销条色阶hex · PNG{datetime}live · 热同步A/B · 脉冲gap芯片."""
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
    from PySide6.QtCore import QSettings, QPoint
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor())
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('#112233', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'pin_merge_diff_fail_hist_drop_snap_guide_recent_color',
        'remove_merge_diff_fail_hist_drop_snap_guide_recent_color',
        '_show_snap_guide_recent_swatch_context_menu',
        'set_stale_prune_undo_color_custom_hex',
        'prompt_stale_prune_undo_color_custom_hex',
        '_make_undo_color_scale_custom_hex_entry',
        'refresh_toast_curve_png_datetime_live_strip',
        'stale_prune_undo_color_scale_compare_preset',
        'set_stale_prune_undo_color_scale_compare_preset',
        '_paint_undo_color_scale_compare_bars',
        'apply_merge_diff_fail_hist_drop_pulse_preview_loop_gap_preset',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave63 APIs present')

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
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapMs', 120)
    s.setValue('host/toastCurvePngExportDir', '')
    s.setValue('host/toastCurvePngRecentExports', [])
    s.setValue('host/toastCurvePngNameTemplate', 'tip-anim-{easing}-{ts}.png')
    s.setValue('host/toastCurvePngProjectName', 'default')
    s.setValue('host/toastCurvePngStationName', 'station1')
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
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._path_copy_badge_fail_hist_undo_bar_menu_no_exec = True
    host._merge_diff_fail_hist_no_exec = True
    host._stale_prune_undo_step_menu_no_exec = True
    host._snap_guide_custom_color_no_dialog = True
    host._snap_guide_recent_swatch_context_no_exec = True
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True

    # --- 1. guide recent right-click clear/pin ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    for hx in ('#aa66ff', '#ff6688', '#66ffaa'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    # last remembered first
    cur = host.merge_diff_fail_hist_drop_snap_guide_recent_colors()
    assert cur[0] == '#66ffaa', cur
    # pin #aa66ff to front
    pinned = host.pin_merge_diff_fail_hist_drop_snap_guide_recent_color('#aa66ff')
    assert pinned[0] == '#aa66ff', pinned
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_recent_pinned') == '#aa66ff'
    # remove middle
    rem = host.remove_merge_diff_fail_hist_drop_snap_guide_recent_color('#ff6688')
    assert '#ff6688' not in rem, rem
    assert len(rem) == 2, rem
    # context menu
    assert host._show_snap_guide_recent_swatch_context_menu('#aa66ff') is True
    menu_ctx = host._last_snap_guide_recent_swatch_context_menu
    assert menu_ctx is not None
    pins = [a for a in menu_ctx.actions() if a.property('isSnapGuideRecentPin')]
    rms = [a for a in menu_ctx.actions() if a.property('isSnapGuideRecentRemove')]
    assert len(pins) == 1 and len(rms) == 1
    # rebuild palette has context wiring
    host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color('#112233')
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    pals = [a for a in menu_g.actions() if a.property('isSnapGuideRecentPalette')]
    assert len(pals) == 1
    btns = getattr(host, '_snap_guide_recent_drag_btns', [])
    assert len(btns) >= 1
    ok('导引带最近色板右键 clear/pin')

    # --- 2. undo color-scale custom hex entry ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    got = host.set_stale_prune_undo_color_custom_hex('#ff00aa', which='hi')
    assert got['hi'] == '#ff00aa', got
    assert host.stale_prune_undo_color_scale_preset() == 'custom'
    got2 = host.set_stale_prune_undo_color_custom_hex(
        '#111111,#222222,#333333', which='all')
    assert got2['hi'] == '#111111' and got2['mid'] == '#222222' and got2['lo'] == '#333333', got2
    host._stale_prune_undo_custom_hex_smoke = '#abcdef'
    prompted = host.prompt_stale_prune_undo_color_custom_hex('hi')
    assert prompted == '#abcdef', prompted
    # solo menu embeds hex entry
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    assert host._show_sev_pin_solo_delete_undo_ms_menu() is True
    menu_ms = host._last_sev_pin_solo_delete_undo_ms_menu
    hexs = [a for a in menu_ms.actions() if a.property('isSoloDeleteUndoColorScaleHex')]
    assert len(hexs) == 1, len(hexs)
    entry = getattr(host, '_last_undo_color_scale_custom_hex_entry', None)
    assert entry is not None and entry.objectName() == 'hostUndoColorScaleCustomHexEntry'
    # hot-sync also
    menu_hs = host._build_undo_color_scale_hot_sync_menu()
    hexs2 = [a for a in menu_hs.actions() if a.property('isUndoColorScaleCustomHexEntry')]
    assert len(hexs2) >= 1
    ok('撤销条色阶自定义 hex 入口')

    # --- 3. PNG {datetime} live preview strip ---
    host.set_toast_curve_png_name_template('{project}-{datetime}.png')
    name = host.resolve_toast_curve_png_name()
    assert datetime.now().strftime('%Y-%m-%d') in name or '_' in name, name
    assert getattr(host, '_last_toast_curve_png_resolved_datetime', ''), name
    assert '{datetime}' not in name
    live_name = host.refresh_toast_curve_png_datetime_live_strip(
        template='{project}-{datetime}.png')
    assert live_name.endswith('.png')
    assert getattr(host, '_last_toast_curve_png_datetime_live', '')
    host._toast_curve_png_name_template_smoke = '{project}-{datetime}.png'
    host._toast_curve_png_name_template_dialog_no_exec = True
    host.show_toast_curve_png_name_template_dialog(interactive=False)
    assert '{datetime}' in host.toast_curve_png_name_template() or 'datetime' in host.toast_curve_png_name_template()
    # also expand in resolve with live stamp
    assert getattr(host, '_last_toast_curve_png_datetime_live_name', '').endswith('.png')
    ok('PNG {datetime} live preview strip')

    # --- 4. hot-sync dual A/B compare ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_stale_prune_undo_color_scale_compare_preset('sunset')
    assert host.stale_prune_undo_color_scale_compare_preset() == 'sunset'
    menu = host._build_undo_color_scale_hot_sync_menu()
    abs_ = [a for a in menu.actions() if a.property('isUndoColorScaleCompareBars')]
    assert len(abs_) == 1, len(abs_)
    bar_a = getattr(host, '_last_undo_color_scale_compare_bar_a', None)
    bar_b = getattr(host, '_last_undo_color_scale_compare_bar_b', None)
    assert bar_a is not None and bar_b is not None
    assert bar_a.objectName() == 'hostUndoColorScaleCompareBarA'
    assert bar_b.objectName() == 'hostUndoColorScaleCompareBarB'
    presets = getattr(host, '_last_undo_color_scale_compare_presets', ())
    assert presets[0] == 'traffic' and presets[1] == 'sunset', presets
    # switch B via menu
    bacts = [a for a in menu.actions() if a.property('isUndoColorScaleComparePreset')]
    next(a for a in bacts if a.data() == 'mono').trigger()
    assert host.stale_prune_undo_color_scale_compare_preset() == 'mono'
    assert getattr(host, '_last_undo_color_scale_compare_presets')[1] == 'mono'
    ok('热同步双条 A/B 对比')

    # --- 5. pulse gap persist + preset chips ---
    assert host.apply_merge_diff_fail_hist_drop_pulse_preview_loop_gap_preset(500) == 500
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms() == 500
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_persisted', False) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_chip') == 500
    # snap nearest
    assert host.apply_merge_diff_fail_hist_drop_pulse_preview_loop_gap_preset(280) == 300
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(120)
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    chips = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_chips', [])
    assert len(chips) == 5, len(chips)
    assert all(c.property('isPulseLoopGapChip') for c in chips)
    # click chip 1000
    chip1000 = next(c for c in chips if int(c.property('pulseLoopGapMs')) == 1000)
    chip1000.click()
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms() == 1000
    sl = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_slider', None)
    assert sl is not None and sl.value() == 1000
    ok('脉冲 gap persist + preset chips')

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
