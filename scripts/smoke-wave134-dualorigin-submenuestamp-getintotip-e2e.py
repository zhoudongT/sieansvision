#!/usr/bin/env python3
"""细妆102：ensure dual-origin flags · tip_max_len submenu restamp · getter→tip/refresh."""
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

def main() -> int:
    hsm_src = (ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')
    try:
        assert 'tip_max_len_submenu_restamped' in hsm_src
        assert 'tip_max_len_get_into_refresh' in hsm_src
        assert 'hover_tip_max_len_get_into_tip' in hsm_src
        assert "ens['from_toggle'] = bool(ens.get('from_toggle'))" in hsm_src
        assert "ens['from_set_strategy'] = True" in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave134 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave134 APIs: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.host_state_machine import HostStateMachineWidget
    host = HostStateMachineWidget(compact=True)
    host.show()
    app.processEvents()
    host._dst_reorder_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_history_menu_no_exec = True

    # --- 1 toggle leaves dual-origin on ensure ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_toggle') is True, ens
        assert ens.get('from_set_strategy') is True, ens
        assert ens.get('strategy') == 'overwrite', ens
        ok('1 toggle dual-origin from_toggle+from_set_strategy')
    except Exception as e:
        bad(f'1 dual toggle: {e}')

    # --- 2 ensure() keeps dual-origin after refresh ---
    try:
        host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_toggle') is True, ens
        assert ens.get('from_set_strategy') is True, ens
        ok('2 ensure keeps dual-origin after refresh')
    except Exception as e:
        bad(f'2 ensure keep: {e}')

    # --- 3 set alone keeps from_toggle if prior ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_set_strategy') is True, ens
        assert ens.get('from_toggle') is True, ens  # kept from prior toggle
        assert ens.get('strategy') == 'merge', ens
        ok('3 set keeps from_toggle')
    except Exception as e:
        bad(f'3 set keep toggle: {e}')

    # --- 4 tip_max_len action re-stamps submenu ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        sub = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_submenu', None)
        assert sub is not None and len(qactions) == 4
        act160 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160)
        act160.trigger()
        app.processEvents()
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_submenu_restamped') is True, menu_st
        assert menu_st.get('tip_max_len_action_max_len') == 160, menu_st
        assert menu_st.get('tip_max_len_submenu_status_prop_ok') is True, menu_st
        assert str(sub.property('dstImportStrategyBadgeMenuTipMaxLenStatus') or '').startswith('策略·'), sub.property('dstImportStrategyBadgeMenuTipMaxLenStatus')
        assert int(sub.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160
        # checked mark on 160
        assert act160.isChecked() is True
        act96 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 96)
        assert act96.isChecked() is False
        assert str(act160.property('dstImportStrategyBadgeMenuTipMaxLenActionStatus') or '').startswith('策略·')
        ok(f'4 submenu restamp status={menu_st.get("tip_max_len_action_submenu_status")}')
    except Exception as e:
        bad(f'4 submenu restamp: {e}')

    # --- 5 fire 48 restamp ---
    try:
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act48 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48)
        act48.trigger()
        app.processEvents()
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        sub = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_submenu', None)
        assert menu_st.get('tip_max_len_submenu_restamped') is True
        assert menu_st.get('tip_max_len_action_max_len') == 48
        assert int(sub.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48
        assert act48.isChecked() is True
        ok('5 submenu restamp 48')
    except Exception as e:
        bad(f'5 restamp 48: {e}')

    # --- 6 tip folds get-stash ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert isinstance(tip, str) and 'DST导入策略' in tip
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get_into_tip', False) is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get_status_prop_ok', False) is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get_status', None) == '策略·覆盖'
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get_max_len', None) == 96
        fr = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_from_get', {})
        assert isinstance(fr, dict) and fr.get('ok') is True and fr.get('status') == '策略·覆盖', fr
        ok('6 tip←get-stash')
    except Exception as e:
        bad(f'6 tip get: {e}')

    # --- 7 refresh folds get-stash ---
    try:
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('tip_max_len_get_into_refresh') is True, ref
        assert ref.get('tip_max_len_get_status_prop_ok') is True, ref
        assert str(ref.get('tip_max_len_get_status', '')).startswith('策略·'), ref
        assert ref.get('tip_max_len_get_max_len') == 96, ref
        assert isinstance(ref.get('tip_max_len_from_get'), dict) and ref['tip_max_len_from_get'].get('ok') is True
        # dual-origin still after refresh
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_set_strategy') is True, ens
        ok(f'7 refresh←get-stash status={ref.get("tip_max_len_get_status")}')
    except Exception as e:
        bad(f'7 refresh get: {e}')

    # --- 8 restore ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        ok('8 restore defaults')
    except Exception as e:
        bad(f'8 restore: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
