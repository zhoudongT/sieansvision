#!/usr/bin/env python3
"""细妆98：copy tip 失败路径 status · refresh→bind stash 镜像 · tip_max_len strategy 抛光."""
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
        assert "out['click_status_prop_ok']" in hsm_src
        assert "out['menu_bind_status_prop_ok']" in hsm_src
        assert "'strategy_prop_ok': bool(strategy_prop_ok)" in hsm_src
        assert 'import_strategy_badge_flash_ms' not in hsm_src
        ok('wave130 APIs present (FlashMs still deferred)')
    except Exception as e:
        bad(f'wave130 APIs: {e}')
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

    # --- 1 copy tip clipboard error-path status ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)

        class BoomCB:
            def setText(self, *a, **k):
                raise RuntimeError('copy_tip_boom')

        with patch.object(QApplication, 'clipboard', return_value=BoomCB()):
            out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip()
        assert out.get('ok') is False, out
        assert 'copy_tip_boom' in str(out.get('reason', '')), out
        assert out.get('status_prop_ok') is True, out
        assert out.get('status') == '策略·合并', out
        assert out.get('tip_prop_ok') is True, out
        assert out.get('tip'), out
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_copy', {})
        assert stash.get('ok') is False and stash.get('status_prop_ok') is True, stash
        ok(f'1 copy tip err status={out.get("status")}')
    except Exception as e:
        bad(f'1 copy tip err: {e}')

    # --- 2 copy tip success regress ---
    try:
        out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip()
        assert out.get('ok') and out.get('status_prop_ok') is True, out
        ok('2 copy tip success regress')
    except Exception as e:
        bad(f'2 copy tip success: {e}')

    # --- 3 refresh→bind stash status mirror ---
    try:
        out = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert out.get('status_prop_ok') is True, out
        assert out.get('click_status_prop_ok') is True, out
        assert out.get('menu_bind_status_prop_ok') is True, out
        assert out.get('click_tip_prop_ok') is True, out
        assert out.get('menu_bind_tip_prop_ok') is True, out
        assert isinstance(out.get('click_bind'), dict) and out['click_bind'].get('status_prop_ok') is True, out.get('click_bind')
        assert isinstance(out.get('menu_bind'), dict) and out['menu_bind'].get('status_prop_ok') is True, out.get('menu_bind')
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', {})
        assert stash.get('click_status_prop_ok') is True and stash.get('menu_bind_status_prop_ok') is True, stash
        ok(f'3 refresh bind mirror click={out.get("click_status_prop_ok")} menu={out.get("menu_bind_status_prop_ok")}')
    except Exception as e:
        bad(f'3 refresh bind: {e}')

    # --- 4 tip_max_len setter strategy polish ---
    try:
        out = host.set_strategy_badge_hover_tip_max_len(120, persist=True)
        assert out.get('ok') is True, out
        assert out.get('max_len') == 120, out
        assert out.get('status_prop_ok') is True, out
        assert out.get('strategy_prop_ok') is True, out
        assert out.get('tip_max_len_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert str(out.get('status', '')).startswith('策略·'), out
        assert out.get('strategy_prop') in ('merge', 'overwrite'), out
        stash = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len', {})
        assert stash.get('strategy_prop_ok') is True, stash
        ok(f'4 tip_max_len status={out.get("status")} strategy={out.get("strategy_prop")}')
    except Exception as e:
        bad(f'4 tip_max_len: {e}')

    # --- 5 tip_max_len overwrite ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        out = host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        assert out.get('status') == '策略·覆盖', out
        assert out.get('strategy_prop') == 'overwrite', out
        assert out.get('strategy_prop_ok') is True, out
        ok('5 tip_max_len overwrite strategy polish')
    except Exception as e:
        bad(f'5 tip_max_len overwrite: {e}')

    # --- 6 copy_orig_len err regress ---
    try:
        class BoomCB2:
            def setText(self, *a, **k):
                raise RuntimeError('orig_boom')
        with patch.object(QApplication, 'clipboard', return_value=BoomCB2()):
            out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert out.get('ok') is False and out.get('status_prop_ok') is True, out
        ok('6 copy_orig_len err regress')
    except Exception as e:
        bad(f'6 copy_orig err: {e}')

    # --- 7 bind_click status regress ---
    try:
        out = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
        assert out.get('status_prop_ok') is True, out
        ok('7 bind_click regress')
    except Exception as e:
        bad(f'7 bind_click: {e}')

    # --- 8 restore merge ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        ok('8 restore merge')
    except Exception as e:
        bad(f'8 restore: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
