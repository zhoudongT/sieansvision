#!/usr/bin/env python3
"""细妆104：set/toggle dual_origin echo · action checked_preset · truncate from_get prefer."""
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
        assert "set_out['dual_origin_echo']" in hsm_src
        assert "out['dual_origin_echo'] = bool(out['from_set_strategy'] or out['from_toggle'])" in hsm_src
        assert "act_st['checked_preset']" in hsm_src
        assert "'from_get_prefer': bool(from_get_prefer)" in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave136 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave136 APIs: {e}')
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

    # --- 1 set out dual_origin echo ---
    try:
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        assert s == 'overwrite'
        set_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_set', {})
        assert set_st.get('from_set_strategy') is True, set_st
        assert set_st.get('dual_origin_echo') is True, set_st
        assert set_st.get('ensure_strategy') == 'overwrite', set_st
        ok(f'1 set dual_origin echo from_toggle={set_st.get("from_toggle")}')
    except Exception as e:
        bad(f'1 set echo: {e}')

    # --- 2 toggle out dual_origin echo ---
    try:
        tog = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert tog.get('ok') is True and tog.get('to') == 'merge', tog
        assert tog.get('from_toggle') is True, tog
        assert tog.get('from_set_strategy') is True, tog
        assert tog.get('dual_origin_echo') is True, tog
        assert tog.get('ensure_strategy') == 'merge', tog
        tog_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_toggle', {})
        assert tog_st.get('dual_origin_echo') is True and tog_st.get('from_toggle') is True, tog_st
        ok('2 toggle dual_origin echo')
    except Exception as e:
        bad(f'2 toggle echo: {e}')

    # --- 3 set after toggle keeps from_toggle in set out ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        set_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_set', {})
        assert set_st.get('from_set_strategy') is True, set_st
        assert set_st.get('from_toggle') is True, set_st
        assert set_st.get('dual_origin_echo') is True, set_st
        ok('3 set keeps from_toggle in echo')
    except Exception as e:
        bad(f'3 set keep: {e}')

    # --- 4 action checked_preset mirrored into action stash ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act160 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160)
        act160.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert act_st.get('max_len') == 160, act_st
        assert act_st.get('checked_preset') == 160, act_st
        assert act_st.get('checked_preset_ok') is True, act_st
        assert act_st.get('qaction_count') == 4, act_st
        assert act_st.get('checked_synced') is True, act_st
        assert act_st.get('submenu_restamped') is True, act_st
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_action_checked_preset') == 160, menu_st
        assert menu_st.get('tip_max_len_action_checked_preset_ok') is True, menu_st
        ok('4 action checked_preset=160')
    except Exception as e:
        bad(f'4 action checked: {e}')

    # --- 5 fire 48 into action stash ---
    try:
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act48 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48)
        act48.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert act_st.get('checked_preset') == 48 and act_st.get('checked_preset_ok') is True, act_st
        assert act_st.get('max_len') == 48, act_st
        ok('5 action checked_preset=48')
    except Exception as e:
        bad(f'5 action 48: {e}')

    # --- 6 truncate success: from_get_prefer False ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.strategy_badge_hover_tip_max_len()  # seed get stash
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('ok', max_len=96)
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('truncate_ok') is True and last.get('status_prop_ok') is True, last
        assert last.get('from_get_prefer') is False, last
        ok('6 truncate success no prefer')
    except Exception as e:
        bad(f'6 truncate ok: {e}')

    # --- 7 truncate fail → from_get prefer ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.strategy_badge_hover_tip_max_len()  # seed get stash with 策略·覆盖
        get_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get', {})
        assert get_st.get('status') == '策略·覆盖', get_st
        badge = host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge
        orig_sp = badge.setProperty

        def boom(name, val, _orig=orig_sp):
            if name == 'dstImportStrategyBadgeStatus':
                raise RuntimeError('truncate_status_boom')
            return _orig(name, val)

        badge.setProperty = boom
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('short', max_len=96)
        badge.setProperty = orig_sp
        assert isinstance(tr, tuple) and tr[1] is False
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('truncate_ok') is False, last
        assert 'truncate_status_boom' in str(last.get('fail_reason') or ''), last
        assert last.get('from_get_prefer') is True, last
        assert last.get('status_prop_ok') is True, last
        assert last.get('status') == '策略·覆盖', last
        ok(f'7 truncate fail from_get prefer status={last.get("status")}')
    except Exception as e:
        try:
            host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge.setProperty = orig_sp
        except Exception:
            pass
        bad(f'7 truncate prefer: {e}')

    # --- 8 restore ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('ok', max_len=96)
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('truncate_ok') is True and last.get('from_get_prefer') is False, last
        ok('8 restore defaults')
    except Exception as e:
        bad(f'8 restore: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
