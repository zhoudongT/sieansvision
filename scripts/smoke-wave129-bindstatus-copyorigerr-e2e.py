#!/usr/bin/env python3
"""细妆97：bind_click/menu_bind 顶层 status · copy_orig_len 失败路径 status · FlashMs 仍缓."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

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
        assert '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click' in hsm_src
        assert '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_bind' in hsm_src
        # bind success surfaces status_prop_ok
        assert hsm_src.count("out['status_prop_ok'] = bool(getattr(self, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok'") >= 4
        # copy_orig_len error paths carry status
        assert hsm_src.count("'ok': False, 'reason': str(e),\n                'status': status") >= 1 or \
               ("'ok': False, 'reason': str(e)," in hsm_src and "hover_copy_orig_len" in hsm_src)
        # no FlashMs
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave129 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave129 APIs: {e}')
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

    # --- 1 bind_click (first or already) status surface ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        # clear bound flag to force fresh bind path if possible
        badge = getattr(host, '_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', None)
        if badge is not None and getattr(badge, '_dst_import_strategy_badge_click_bound', False):
            # already path
            out = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
            assert out.get('ok') and out.get('already') is True, out
        else:
            out = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
            assert out.get('ok') and out.get('bound') is True, out
        assert out.get('status_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert out.get('strategy_prop_ok') is True, out
        assert out.get('status') == '策略·合并', out
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click', {})
        assert stash.get('status_prop_ok') is True, stash
        ok(f'1 bind_click status={out.get("status")} already={out.get("already")}')
    except Exception as e:
        bad(f'1 bind_click: {e}')

    # --- 2 bind_click already path explicit ---
    try:
        out = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
        assert out.get('already') is True, out
        assert out.get('status_prop_ok') is True, out
        assert str(out.get('status', '')).startswith('策略·'), out
        ok(f'2 bind_click already status={out.get("status")}')
    except Exception as e:
        bad(f'2 bind_click already: {e}')

    # --- 3 bind_ctx menu status surface ---
    try:
        out = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert out.get('ok') is True, out
        assert out.get('status_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert out.get('strategy_prop_ok') is True, out
        assert str(out.get('status', '')).startswith('策略·'), out
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_menu_bind', {})
        assert stash.get('status_prop_ok') is True, stash
        ok(f'3 bind_ctx status={out.get("status")} already={out.get("already")}')
    except Exception as e:
        bad(f'3 bind_ctx: {e}')

    # --- 4 show context-menu top-level status (regress + confirm) ---
    try:
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('status_prop_ok') is True, menu
        assert menu.get('tip_prop_ok') is True, menu
        assert menu.get('strategy_prop_ok') is True, menu
        assert str(menu.get('status', '')).startswith('策略·'), menu
        ok(f'4 show menu status={menu.get("status")}')
    except Exception as e:
        bad(f'4 show menu: {e}')

    # --- 5 copy_orig_len error-path status (clipboard boom) ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)

        class BoomCB:
            def setText(self, *a, **k):
                raise RuntimeError('clip_boom')

        with patch.object(QApplication, 'clipboard', return_value=BoomCB()):
            out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert out.get('ok') is False, out
        assert 'clip_boom' in str(out.get('reason', '')), out
        assert out.get('status_prop_ok') is True, out
        assert out.get('status') == '策略·覆盖', out
        assert out.get('tip_prop_ok') is True, out
        assert 'orig_len' in out and 'text' in out, out
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_copy_orig_len', {})
        assert stash.get('status_prop_ok') is True and stash.get('ok') is False, stash
        ok(f'5 copy_orig_len err status={out.get("status")} reason={out.get("reason")}')
    except Exception as e:
        bad(f'5 copy_orig err: {e}')

    # --- 6 copy_orig_len success regress ---
    try:
        out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert out.get('ok') and out.get('status_prop_ok') is True, out
        ok('6 copy_orig_len success regress')
    except Exception as e:
        bad(f'6 copy_orig success: {e}')

    # --- 7 toggle surface regress ---
    try:
        t = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert t.get('status_prop_ok') is True, t
        ok(f'7 toggle regress to={t.get("to")}')
    except Exception as e:
        bad(f'7 toggle: {e}')

    # --- 8 restore merge + set str ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        ok('8 set strategy str regress')
    except Exception as e:
        bad(f'8 set: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
