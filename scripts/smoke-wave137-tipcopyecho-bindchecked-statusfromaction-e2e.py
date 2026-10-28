#!/usr/bin/env python3
"""细妆105：tip/copy dual_origin · truncate from_get_fold · bind/refresh checked_preset · status_from_action."""
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
        assert 'hover_dual_origin_echo' in hsm_src
        assert "out['dual_origin_echo'] = bool(out['from_set_strategy'] or out['from_toggle'])" in hsm_src
        assert "'from_get_fold': bool(from_get_fold)" in hsm_src
        assert "out['tip_max_len_action_checked_preset']" in hsm_src
        assert "act_st['status_from_action']" in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave137 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave137 APIs: {e}')
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

    # seed dual-origin via set+toggle
    try:
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        # now merge, dual origin on ensure
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_set_strategy') and ens.get('from_toggle'), ens
        ok('0 seed dual-origin ensure')
    except Exception as e:
        bad(f'0 seed: {e}')

    # --- 1 tip dual_origin echo ---
    try:
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert isinstance(tip, str) and tip
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_from_set_strategy') is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_from_toggle') is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_dual_origin_echo') is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_ensure_strategy') == 'merge'
        ok('1 tip dual_origin echo')
    except Exception as e:
        bad(f'1 tip echo: {e}')

    # --- 2 copy dual_origin echo ---
    try:
        cp = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip()
        assert cp.get('ok') is True, cp
        assert cp.get('from_set_strategy') is True, cp
        assert cp.get('from_toggle') is True, cp
        assert cp.get('dual_origin_echo') is True, cp
        assert cp.get('ensure_strategy') == 'merge', cp
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_copy', {})
        assert stash.get('dual_origin_echo') is True, stash
        ok('2 copy dual_origin echo')
    except Exception as e:
        bad(f'2 copy echo: {e}')

    # --- 3 truncate success from_get_fold ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.strategy_badge_hover_tip_max_len()  # seed get
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('ok', max_len=96)
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('truncate_ok') is True and last.get('status_prop_ok') is True, last
        assert last.get('from_get_prefer') is False, last
        assert last.get('from_get_fold') is True, last
        assert last.get('status') == '策略·覆盖', last
        ok('3 truncate success from_get_fold')
    except Exception as e:
        bad(f'3 truncate fold: {e}')

    # --- 4 action status_from_action ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act160 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160)
        act160.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert act_st.get('checked_preset') == 160, act_st
        assert act_st.get('status_from_action') and str(act_st['status_from_action']).startswith('策略·'), act_st
        assert act_st.get('status_from_action_ok') is True, act_st
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_action_status_from_action') == act_st.get('status_from_action'), menu_st
        assert menu_st.get('tip_max_len_action_status_from_action_ok') is True, menu_st
        ok(f'4 status_from_action={act_st.get("status_from_action")}')
    except Exception as e:
        bad(f'4 status_from_action: {e}')

    # --- 5 refresh folds checked_preset ---
    try:
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('tip_max_len_action_checked_preset') == 160, ref
        assert ref.get('tip_max_len_action_checked_preset_ok') is True, ref
        assert ref.get('tip_max_len_action_from_action') is True, ref
        assert ref.get('tip_max_len_action_status_from_action') and str(ref['tip_max_len_action_status_from_action']).startswith('策略·'), ref
        ok('5 refresh fold checked_preset=160')
    except Exception as e:
        bad(f'5 refresh fold: {e}')

    # --- 6 click/menu bind fold (already path) ---
    try:
        click = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
        assert click.get('already') is True or click.get('bound') is True, click
        assert click.get('tip_max_len_action_checked_preset') == 160, click
        assert click.get('tip_max_len_action_from_action') is True, click
        menu_b = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu_b.get('tip_max_len_action_checked_preset') == 160, menu_b
        assert menu_b.get('tip_max_len_action_checked_preset_ok') is True, menu_b
        assert menu_b.get('tip_max_len_action_status_from_action'), menu_b
        ok('6 click+menu bind fold checked_preset')
    except Exception as e:
        bad(f'6 bind fold: {e}')

    # --- 7 fire 48 then refresh/bind update ---
    try:
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act48 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48)
        act48.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert act_st.get('checked_preset') == 48 and act_st.get('status_from_action_ok') is True, act_st
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('tip_max_len_action_checked_preset') == 48, ref
        click = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
        assert click.get('tip_max_len_action_checked_preset') == 48, click
        ok('7 fire 48 → refresh/bind fold')
    except Exception as e:
        bad(f'7 fire 48: {e}')

    # --- 8 restore ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_dual_origin_echo') is True
        ok('8 restore defaults')
    except Exception as e:
        bad(f'8 restore: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
