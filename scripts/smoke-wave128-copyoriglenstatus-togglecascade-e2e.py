#!/usr/bin/env python3
"""细妆96：copy_*_orig_len Status 级联 · toggle 表面 status_prop_ok · FlashMs 暂缓."""
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
        assert 'hover_copy_orig_len' in hsm_src
        assert "status_prop_ok': bool(status_prop_ok)" in hsm_src
        # toggle surfaces status from badge refresh
        assert "'strategy_prop_ok': bool(badge.get('strategy_prop_ok'))" in hsm_src
        # FlashMs deferred — no strategy badge flash_ms getter yet
        assert 'strategy_badge_flash_ms' not in hsm_src or hsm_src.count('def strategy_badge_flash_ms') == 0
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave128 APIs present (FlashMs deferred)')
    except Exception as e:
        bad(f'wave128 APIs present: {e}')
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

    # --- 1 copy_orig_len Status cascade (merge) ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert out.get('ok') and out.get('copied') is True, out
        assert out.get('status_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert out.get('status') == '策略·合并', out
        assert isinstance(out.get('orig_len'), int) and out['orig_len'] > 0, out
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_copy_orig_len', {})
        assert stash.get('status_prop_ok') is True, stash
        ok(f'1 copy_orig_len status={out.get("status")} orig_len={out.get("orig_len")}')
    except Exception as e:
        bad(f'1 copy_orig_len merge: {e}')

    # --- 2 copy_orig_len overwrite ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert out.get('status_prop_ok') is True, out
        assert out.get('status') == '策略·覆盖', out
        ok(f'2 copy_orig_len overwrite status={out.get("status")}')
    except Exception as e:
        bad(f'2 copy_orig_len overwrite: {e}')

    # --- 3 toggle surfaces status ---
    try:
        t = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert t.get('ok') is True, t
        assert t.get('status_prop_ok') is True, t
        assert t.get('strategy_prop_ok') is True, t
        assert t.get('tip_prop_ok') is True, t
        assert str(t.get('status', '')).startswith('策略·'), t
        assert isinstance(t.get('badge'), dict) and t['badge'].get('status_prop_ok') is True, t.get('badge')
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_toggle', {})
        assert stash.get('status_prop_ok') is True, stash
        ok(f'3 toggle surface status={t.get("status")} to={t.get("to")}')
    except Exception as e:
        bad(f'3 toggle: {e}')

    # --- 4 toggle again (round-trip) ---
    try:
        t = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert t.get('status_prop_ok') is True, t
        assert t.get('strategy_prop_ok') is True, t
        ok(f'4 toggle round-trip to={t.get("to")} status={t.get("status")}')
    except Exception as e:
        bad(f'4 toggle round-trip: {e}')

    # --- 5 copy tip Status regress (细妆95) ---
    try:
        host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        c = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip()
        assert c.get('status_prop_ok') is True, c
        ok('5 copy tip status regress')
    except Exception as e:
        bad(f'5 copy tip regress: {e}')

    # --- 6 truncate last status regress ---
    try:
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('y' * 180, max_len=32)
        assert isinstance(tr, tuple) and tr[1] is True
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('status_prop_ok') is True, last
        ok('6 truncate status regress')
    except Exception as e:
        bad(f'6 truncate regress: {e}')

    # --- 7 set strategy still str ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge', s
        ok('7 set strategy str regress')
    except Exception as e:
        bad(f'7 set strategy: {e}')

    # --- 8 refresh status ---
    try:
        r = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert r.get('status_prop_ok') is True, r
        ok('8 refresh status regress')
    except Exception as e:
        bad(f'8 refresh: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
