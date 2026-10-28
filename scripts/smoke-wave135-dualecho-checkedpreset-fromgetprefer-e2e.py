#!/usr/bin/env python3
"""细妆103：refresh dual-origin echo · menu checked preset sync · tip from_get prefer."""
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
        assert 'dual_origin_echo' in hsm_src
        assert 'tip_max_len_checked_preset' in hsm_src
        assert 'hover_status_from_get_prefer' in hsm_src
        assert 'tip_max_len_checked_synced' in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave135 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave135 APIs: {e}')
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

    # --- 1 refresh echoes dual-origin after toggle ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('from_toggle') is True, ref
        assert ref.get('from_set_strategy') is True, ref
        assert ref.get('dual_origin_echo') is True, ref
        assert ref.get('ensure_strategy') == 'overwrite', ref
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', {})
        assert stash.get('dual_origin_echo') is True and stash.get('from_toggle') is True, stash
        ok('1 refresh dual-origin echo')
    except Exception as e:
        bad(f'1 dual echo: {e}')

    # --- 2 set-only still echoes from_set (and kept from_toggle) ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('from_set_strategy') is True, ref
        assert ref.get('from_toggle') is True, ref  # kept
        assert ref.get('dual_origin_echo') is True, ref
        assert ref.get('ensure_strategy') == 'merge', ref
        ok('2 refresh echo after set')
    except Exception as e:
        bad(f'2 echo set: {e}')

    # --- 3 menu restamp syncs qaction_count + checked preset ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act160 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160)
        act160.trigger()
        app.processEvents()
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_submenu_restamped') is True, menu_st
        assert menu_st.get('tip_max_len_qaction_count') == 4, menu_st
        assert menu_st.get('tip_max_len_checked_preset') == 160, menu_st
        assert menu_st.get('tip_max_len_checked_preset_ok') is True, menu_st
        assert menu_st.get('tip_max_len_checked_synced') is True, menu_st
        ok('3 checked preset 160 synced')
    except Exception as e:
        bad(f'3 checked sync: {e}')

    # --- 4 fire 48 checked sync ---
    try:
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act48 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48)
        act48.trigger()
        app.processEvents()
        menu_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu', {})
        assert menu_st.get('tip_max_len_checked_preset') == 48, menu_st
        assert menu_st.get('tip_max_len_checked_preset_ok') is True, menu_st
        assert menu_st.get('tip_max_len_qaction_count') == 4, menu_st
        ok('4 checked preset 48 synced')
    except Exception as e:
        bad(f'4 checked 48: {e}')

    # --- 5 tip normal: from_get prefer False (tip status strong) ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert isinstance(tip, str)
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok', False) is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_from_get_prefer', None) is False
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status', None) == '策略·覆盖'
        ok('5 tip strong → no from_get prefer')
    except Exception as e:
        bad(f'5 tip strong: {e}')

    # --- 6 tip weaker → from_get prefer ---
    try:
        badge = host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge
        orig_sp = badge.setProperty

        def boom(name, val, _orig=orig_sp):
            if name == 'dstImportStrategyBadgeStatus':
                raise RuntimeError('tip_status_boom')
            return _orig(name, val)

        badge.setProperty = boom
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        badge.setProperty = orig_sp
        assert isinstance(tip, str)
        # tip path failed status write → prefer from_get (getter ran before boom)
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_from_get_prefer', False) is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok', False) is True
        st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status', None)
        assert str(st).startswith('策略·'), st
        ok(f'6 tip weaker → from_get prefer status={st}')
    except Exception as e:
        try:
            host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge.setProperty = orig_sp
        except Exception:
            pass
        bad(f'6 from_get prefer: {e}')

    # --- 7 tip restored strong again ---
    try:
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok', False) is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_from_get_prefer', None) is False
        ok('7 tip restored no prefer')
    except Exception as e:
        bad(f'7 tip restore: {e}')

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
