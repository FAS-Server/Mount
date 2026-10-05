import json
import threading
from pathlib import Path


def test_main_statistics_schema_and_operation_restart_cleanup(environment):
    from mount.config import SlotStats
    m, _, _ = environment
    assert set(SlotStats().serialize()) == {
        'last_mount_ns', 'total_use_time', 'total_player_time', 'total_players'}
    for _ in range(3):
        m.current_slot.on_mount()
        m.current_slot.set_players({'Alice', 'Bob'})
        m.current_slot.on_unmount()
        m.current_slot.on_unmount()
    assert not any(t.name == 'StatsChecker' for t in threading.enumerate())


def test_operation_lifecycle_preserves_reset_config(environment, monkeypatch):
    import mount.MountSlot as ms
    from mount.constants import MOUNTABLE_CONFIG
    m, _, _ = environment
    now = [100]
    monkeypatch.setattr(ms.time, 'time_ns', lambda: now[0])
    slot = m.current_slot
    slot.on_mount()
    slot.set_players({'Alice', 'Bob'})
    path = Path(slot.path)/MOUNTABLE_CONFIG
    data = json.loads(path.read_text())
    data['reset_path'] = 'fresh-template'
    data['desc'] = 'fresh-description'
    path.write_text(json.dumps(data))
    now[0] = 110
    slot.update_stats()
    saved = json.loads(path.read_text())
    assert saved['reset_path'] == 'fresh-template'
    assert saved['desc'] == 'fresh-description'
    assert saved['stats']['total_use_time'] == 10
    assert saved['stats']['total_player_time'] == 20
    slot.on_unmount()


def test_operation_rows_keep_main_configured_order(environment):
    m, _, Source = environment
    m._config.available_servers.reverse()
    src = Source()
    m.list_servers(src)
    rows = list(map(str, src.replies))
    assert 'target with spaces' in rows[1] and 'current' in rows[2]
    assert not hasattr(m._config, 'pinned_servers')
    assert not hasattr(m._config, 'list_order')


def test_real_config_command_api_across_mcdr_versions(environment):
    from test_commands_stats import CommandUser, command_root
    m, _, _ = environment
    src = CommandUser('Admin', 3)
    root = command_root(m)
    path = m.current_slot.path
    root.execute(src, '!!mount --config '+path)
    root.execute(src, '!!mount --config '+path+' set desc Updated')
    assert m.current_slot.desc == 'Updated'


def test_worker_stop_wakes_promptly():
    from mount.MountSlot import StatsChecker
    callbacks = []
    worker = StatsChecker(600, lambda: callbacks.append(1))
    worker.start()
    worker.stop()
    worker.join(1)
    assert not worker.is_alive() and not callbacks
