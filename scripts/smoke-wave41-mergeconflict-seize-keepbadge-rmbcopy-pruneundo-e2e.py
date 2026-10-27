#!/usr/bin/env python3
"""细妆㊶：合并冲突计数tip · 共享弧抢占可视化 · 容量保持徽标 · 徽章右键再复制 · 失效清理undo."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m, flush=True)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m, flush=True)

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
    from PySide6.QtCore import QSettings, Qt
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget, _SevChipPinProgressArc
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'merge_alarm_film_csv_dirs', 'merge_import_alarm_film_csv_dirs_json',
        'claim_sev_pin_arc', '_flash_sev_pin_arc_seize',
        '_ensure_toast_hist_cap_keep_badge', 'set_toast_hist_cap_keep_open',
        'copy_path_copy_badge_path', 'undo_prune_stale_alarm_film_csv_dirs',
        'can_undo_prune_stale_alarm_film_csv_dirs',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isKeepBadge' in src and 'isPruneUndo' in src
    assert 'hostToastHistCapKeepBadge' in src
    ok('wave41 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevChipPinMs', 550)
    s.setValue('host/sevChipPinArcColor', '#f0c040')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    tmp = Path('/tmp/sieans-w41s'); tmp.mkdir(exist_ok=True)
    dirs = [tmp / f'd{i}' for i in range(6)]
    for d in dirs:
        d.mkdir(exist_ok=True)
    stale = tmp / 'gone-w41'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. merge conflict count tip ---
    host.clear_alarm_film_csv_dirs()
    host.set_alarm_film_csv_dirs_max(5)
    host.remember_alarm_film_csv_dir(str(dirs[0]))
    host.remember_alarm_film_csv_dir(str(dirs[1]))
    # import overlaps d0 + adds d2,d3 + will not trim yet
    payload = json.dumps({
        'max': 5,
        'dirs': [str(dirs[2]), str(dirs[0]), str(dirs[3])],
    })
    out = host.merge_import_alarm_film_csv_dirs_json(payload)
    stats = getattr(host, '_last_merge_stats', {})
    assert stats.get('conflict') == 1, stats  # dirs[0]
    assert stats.get('new') == 2, stats  # d2,d3
    tip = getattr(host, '_last_merge_import_tip', '') or ''
    assert '冲突' in tip and '新增' in tip, tip
    # force trim: max=3, existing 4+, incoming more
    host.set_alarm_film_csv_dirs_max(3)
    host.clear_alarm_film_csv_dirs()
    for d in dirs[:3]:
        host.remember_alarm_film_csv_dir(str(d))
    # incoming 3 new unique that push past max when unioned with existing
    payload2 = json.dumps({
        'max': 3,
        'dirs': [str(dirs[3]), str(dirs[4]), str(dirs[5])],
    })
    out2 = host.merge_import_alarm_film_csv_dirs_json(payload2)
    stats2 = getattr(host, '_last_merge_stats', {})
    assert stats2.get('new') == 3, stats2
    assert stats2.get('trimmed') >= 1, stats2
    tip2 = getattr(host, '_last_merge_import_tip', '') or ''
    assert '裁剪' in tip2, tip2
    assert len(out2) == 3
    ok('合并导入冲突计数 tip')

    # --- 2. arc owner seize visualization ---
    host.set_sev_chip_pin_ms(400)
    host.pin_alarm_severity_filter(False)
    # start chip press → owner chip
    host._on_sev_chip_press(None, 'error')
    host._on_sev_chip_pin_tick()
    assert host._sev_pin_arc_owner == 'chip'
    assert host._sev_chip_pin_tick.isActive()
    # bubble seizes
    host._last_sev_pin_arc_seize = {}
    host._on_sev_bubble_press(None, 'warning')
    host._on_sev_bubble_pin_tick()
    assert host._sev_pin_arc_owner == 'bubble'
    seize = getattr(host, '_last_sev_pin_arc_seize', {})
    assert seize.get('from') == 'chip' and seize.get('to') == 'bubble', seize
    tip_s = getattr(host, '_last_sev_pin_arc_seize_tip', '') or ''
    assert '抢占' in tip_s, tip_s
    # chip tick should have been stopped by claim
    assert not host._sev_chip_pin_tick.isActive()
    host._sev_bubble_pin_tick.stop()
    host._hide_sev_bubble_pin_arc()
    # explicit claim API
    host._sev_pin_arc_owner = 'bubble'
    prev = host.claim_sev_pin_arc('chip', flash=True)
    assert prev == 'bubble'
    assert host._sev_pin_arc_owner == 'chip'
    ok('共享弧 owner 互斥抢占可视化')

    # --- 3. keep badge on capacity menu ---
    host.set_liaison_toast_history_max(5, persist=False)
    host._toast_hist_cap_menu_no_exec = True
    host.set_toast_hist_cap_keep_open(True)
    menu = host._build_liaison_toast_capacity_menu()
    found = False
    for a in menu.actions():
        if a.property('isKeepBadge'):
            found = True
            assert '保持' in (a.text() or '')
            assert not a.isEnabled()
            assert a.objectName() == 'hostToastHistCapKeepBadge'
    assert found
    assert getattr(host, '_last_toast_hist_cap_keep_badge', False)
    # inject into live menu
    host.set_toast_hist_cap_keep_open(False)
    menu2 = host._on_toast_hist_cap_hotkey()
    host._last_toast_hist_cap_menu = menu2
    host.set_toast_hist_cap_keep_open(True)
    assert host._ensure_toast_hist_cap_keep_badge()
    found2 = any(a.property('isKeepBadge') for a in menu2.actions())
    assert found2
    host.set_toast_hist_cap_keep_open(False)
    host.set_liaison_toast_history_max(5, persist=True)
    ok('容量菜单「保持」徽标')

    # --- 4. badge RMB copy path ---
    host.flash_path_copy_badge(str(tmp))
    assert getattr(host, '_path_copy_badge_path', '') == str(tmp)
    # simulate right click via API
    assert host.copy_path_copy_badge_path()
    assert getattr(host, '_last_path_copy_badge_recopied', False)
    clip = QApplication.clipboard().text()
    assert clip == str(tmp), clip
    # mouse handler path
    class _E:
        def button(self):
            return Qt.MouseButton.RightButton
    host._last_path_copy_badge_recopied = False
    host._on_path_copy_badge_clicked(_E())
    assert host._last_path_copy_badge_recopied
    ok('徽章右键再复制路径')

    # --- 5. prune undo ---
    host.clear_alarm_film_csv_dirs()
    host.set_alarm_film_csv_dirs_max(5)
    host.remember_alarm_film_csv_dir(str(dirs[0]))
    host.remember_alarm_film_csv_dir(str(stale))
    host.remember_alarm_film_csv_dir(str(dirs[1]))
    before = list(host.alarm_film_csv_dirs())
    assert str(stale) in before
    kept = host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert str(stale) not in kept
    assert host.can_undo_prune_stale_alarm_film_csv_dirs()
    assert getattr(host, '_host_toast_click_action', '') == 'undo_prune'
    # menu has undo enabled
    host._alarm_ctx_menu_no_exec = True
    menu = host._build_alarm_list_context_menu()
    found_undo = False
    for a in menu.actions():
        m = a.menu()
        if m is None or '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            if x.property('isPruneUndo'):
                found_undo = True
                assert x.isEnabled()
    assert found_undo
    restored = host.undo_prune_stale_alarm_film_csv_dirs()
    assert str(stale) in restored
    assert str(dirs[0]) in restored and str(dirs[1]) in restored
    assert not host.can_undo_prune_stale_alarm_film_csv_dirs()
    assert getattr(host, '_last_stale_prune_undone', False)
    # toast click action path
    host.remember_alarm_film_csv_dir(str(stale))
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert host._host_toast_click_action == 'undo_prune'
    host._on_host_toast_clicked()
    assert str(stale) in host.alarm_film_csv_dirs()
    ok('失效清理 undo')

    print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad(f'exception: {exc}')
        print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
        raise SystemExit(1)
