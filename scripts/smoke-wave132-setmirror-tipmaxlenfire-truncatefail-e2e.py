#!/usr/bin/env python3
"""细妆100：set→ensure/refresh status 镜像 · tip_max_len QAction.triggered · truncate 失败 stash."""
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
        assert "ens['from_set_strategy'] = True" in hsm_src
        assert 'set_status_prop_ok' in hsm_src
        assert 'menu_tip_max_len_qactions' in hsm_src
        assert 'truncate_ok' in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave132 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave132 APIs: {e}')
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

    # --- 1 set-strategy mirrors ensure/refresh stash ---
    try:
        # seed ensure stash
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        assert s == 'overwrite'
        set_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_set', {})
        assert set_st.get('status_prop_ok') is True, set_st
        assert set_st.get('status') == '策略·覆盖', set_st
        assert set_st.get('click_status_prop_ok') is True, set_st
        ref = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', {})
        assert ref.get('set_strategy') == 'overwrite', ref
        assert ref.get('set_status_prop_ok') is True, ref
        assert ref.get('status') == '策略·覆盖', ref
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('from_set_strategy') is True, ens
        assert ens.get('strategy') == 'overwrite', ens
        assert ens.get('status_prop_ok') is True, ens
        assert ens.get('status') == '策略·覆盖', ens
        ok('1 set→ensure/refresh status mirror')
    except Exception as e:
        bad(f'1 set mirror: {e}')

    # --- 2 set merge mirror ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        ens = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_ensure', {})
        assert ens.get('strategy') == 'merge' and ens.get('status') == '策略·合并', ens
        ok('2 set merge mirror')
    except Exception as e:
        bad(f'2 set merge: {e}')

    # --- 3 menu tip_max_len QAction.triggered fire ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('tip_max_len_qaction_count') == 4, menu
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', None)
        assert isinstance(qactions, list) and len(qactions) == 4, qactions
        act160 = None
        for a in qactions:
            if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 160:
                act160 = a
                break
        assert act160 is not None, 'no 160 action'
        # clear prior action stash
        host._last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action = None
        act160.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert isinstance(act_st, dict), act_st
        assert act_st.get('ok') is True, act_st
        assert act_st.get('max_len') == 160, act_st
        assert act_st.get('status_prop_ok') is True, act_st
        assert act_st.get('strategy_prop_ok') is True, act_st
        assert str(act_st.get('status', '')).startswith('策略·'), act_st
        ok(f'3 QAction.triggered max_len=160 status={act_st.get("status")}')
    except Exception as e:
        bad(f'3 QAction fire: {e}')

    # --- 4 fire another preset (48) ---
    try:
        qactions = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_qactions', [])
        act48 = next(a for a in qactions if int(a.property('dstImportStrategyBadgeHoverTipMaxLen') or 0) == 48)
        act48.trigger()
        app.processEvents()
        act_st = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_tip_max_len_action', {})
        assert act_st.get('max_len') == 48 and act_st.get('status_prop_ok') is True, act_st
        ok('4 QAction.triggered max_len=48')
    except Exception as e:
        bad(f'4 QAction 48: {e}')

    # --- 5 truncate success ---
    try:
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('z' * 200, max_len=40)
        assert isinstance(tr, tuple) and tr[1] is True
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('ok') is True and last.get('truncate_ok') is True, last
        assert last.get('status_prop_ok') is True, last
        assert last.get('fail_reason') is None, last
        ok('5 truncate success stash')
    except Exception as e:
        bad(f'5 truncate ok: {e}')

    # --- 6 truncate failure-path stash ---
    try:
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
        assert last.get('ok') is False and last.get('truncate_ok') is False, last
        assert 'truncate_status_boom' in str(last.get('fail_reason') or last.get('reason') or ''), last
        assert last.get('status_prop_ok') is False, last
        assert last.get('status') is None, last
        ok(f'6 truncate fail reason={last.get("fail_reason")}')
    except Exception as e:
        try:
            host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge.setProperty = orig_sp
        except Exception:
            pass
        bad(f'6 truncate fail: {e}')

    # --- 7 truncate restored ---
    try:
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('ok', max_len=96)
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('truncate_ok') is True and last.get('status_prop_ok') is True, last
        ok('7 truncate restored')
    except Exception as e:
        bad(f'7 truncate restore: {e}')

    # --- 8 restore tip_max_len 96 ---
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
