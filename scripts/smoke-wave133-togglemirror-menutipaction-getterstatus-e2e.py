#!/usr/bin/env python3
"""细妆101：toggle→ensure/refresh 镜像 · tip_max_len action→menu out · getter status surface."""
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
        assert "ens['from_toggle'] = True" in hsm_src
        assert 'toggle_status_prop_ok' in hsm_src
        assert 'tip_max_len_action_status' in hsm_src
        assert 'hover_tip_max_len_get' in hsm_src
        assert '_strategy_badge_tip_max_len_getting' in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave133 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave133 APIs: {e}')
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

    # --- 1 toggle merge→overwrite mirrors ensure/refresh ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        tog = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert tog.get('ok') is True and tog.get('to') == 'overwrite', tog
        assert tog.get('status') == '策略·覆盖', tog
        assert tog.get('status_prop_ok') is True, tog
        assert tog.get('click_status_prop_ok') is True, tog
        ref = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', {})
        assert ref.get('toggle_strategy') == 'overwrite', ref
        assert ref.get('toggle_from') == 'merge', ref
        assert ref.get('toggle_status_prop_ok') is True, ref
        assert ref.get('status') == '策略·覆盖', ref
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_toggle') is True, ens
        assert ens.get('strategy') == 'overwrite', ens
        assert ens.get('status_prop_ok') is True, ens
        assert ens.get('status') == '策略·覆盖', ens
        ok('1 toggle→ensure/refresh overwrite mirror')
    except Exception as e:
        bad(f'1 toggle overwrite: {e}')

    # --- 2 toggle back to merge ---
    try:
        tog = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert tog.get('to') == 'merge' and tog.get('status') == '策略·合并', tog
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_toggle') is True and ens.get('strategy') == 'merge', ens
        assert ens.get('status') == '策略·合并', ens
        ref = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', {})
        assert ref.get('toggle_strategy') == 'merge' and ref.get('toggle_status_prop_ok') is True, ref
        ok('2 toggle→merge mirror')
    except Exception as e:
        bad(f'2 toggle merge: {e}')

    # --- 3 tip_max_len QAction → menu out status copy ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('tip_max_len_qaction_count') == 4, menu
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act160 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160)
        host._last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action = None
        # seed menu stash without action fields
        menu_before = dict(getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {}) or {})
        menu_before.pop('tip_max_len_action_status', None)
        menu_before.pop('tip_max_len_action_max_len', None)
        host._last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu = menu_before
        act160.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert act_st.get('max_len') == 160 and act_st.get('status_prop_ok') is True, act_st
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_action_max_len') == 160, menu_st
        assert menu_st.get('tip_max_len_action_status_prop_ok') is True, menu_st
        assert str(menu_st.get('tip_max_len_action_status', '')).startswith('策略·'), menu_st
        assert menu_st.get('tip_max_len') == 160, menu_st
        assert menu_st.get('tip_max_len_status_ok') is True, menu_st
        assert str(menu_st.get('status', '')).startswith('策略·'), menu_st
        ok(f'3 action→menu out status={menu_st.get("tip_max_len_action_status")}')
    except Exception as e:
        bad(f'3 action→menu: {e}')

    # --- 4 fire 48 also updates menu ---
    try:
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act48 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48)
        act48.trigger()
        app.processEvents()
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_action_max_len') == 48, menu_st
        assert menu_st.get('tip_max_len') == 48 and menu_st.get('tip_max_len_action_status_prop_ok') is True, menu_st
        ok('4 action 48→menu out')
    except Exception as e:
        bad(f'4 action 48: {e}')

    # --- 5 getter status surface ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host._last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get = None
        v = host.strategy_badge_hover_tip_max_len()
        assert isinstance(v, int) and v == 96, v
        get_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get', {})
        assert isinstance(get_st, dict), get_st
        assert get_st.get('ok') is True, get_st
        assert get_st.get('max_len') == 96, get_st
        assert get_st.get('status') == '策略·覆盖', get_st
        assert get_st.get('status_prop_ok') is True, get_st
        assert get_st.get('tip_max_len_prop_ok') is True, get_st
        assert get_st.get('strategy') == 'overwrite', get_st
        assert get_st.get('strategy_prop_ok') is True, get_st
        badge = host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge
        assert int(badge.property('dstImportStrategyBadgeHoverTipMaxLen')) == 96
        assert badge.property('dstImportStrategyBadgeStatus') == '策略·覆盖'
        ok(f'5 getter status surface status={get_st.get("status")}')
    except Exception as e:
        bad(f'5 getter: {e}')

    # --- 6 getter after merge ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        v = host.strategy_badge_hover_tip_max_len()
        assert v == 96
        get_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get', {})
        assert get_st.get('status') == '策略·合并' and get_st.get('status_prop_ok') is True, get_st
        assert get_st.get('strategy') == 'merge', get_st
        ok('6 getter merge status')
    except Exception as e:
        bad(f'6 getter merge: {e}')

    # --- 7 getter still int when called from tip (no recurse break) ---
    try:
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert isinstance(tip, str) and 'DST导入策略' in tip
        get_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_get', {})
        assert get_st.get('ok') is True and get_st.get('max_len') == 96, get_st
        ok('7 tip→getter no recurse break')
    except Exception as e:
        bad(f'7 tip→getter: {e}')

    # --- 8 restore defaults ---
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
