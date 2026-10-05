import json
import threading
from pathlib import Path

import pytest
from command_api import CommandUser, command_root


def test_stats_preserve_fresh_configuration_and_audit(environment, monkeypatch):
    import mount.MountSlot as ms
    from mount.constants import MOUNTABLE_CONFIG
    m, _, _ = environment
    slot = m.current_slot
    now = [100]
    monkeypatch.setattr(ms.time, 'monotonic_ns', lambda: now[0])
    slot.on_mount()
    path = Path(slot.path) / MOUNTABLE_CONFIG
    data = json.loads(path.read_text())
    data['reset_path'] = 'new-template'
    data['desc'] = 'edited-description'
    path.write_text(json.dumps(data))
    now[0] = 200
    slot.update_stats()
    saved = json.loads(path.read_text())
    assert saved['reset_path'] == 'new-template'
    assert saved['desc'] == 'edited-description'
    assert saved['stats']['use_time_ns_v2'] == 100
    slot.on_unmount()


def test_two_player_increment_and_unknown_departure(environment, monkeypatch):
    import mount.MountSlot as ms
    m, _, _ = environment
    s = m.current_slot
    now = [0]
    monkeypatch.setattr(ms.time, 'monotonic_ns', lambda: now[0])
    s.on_mount()
    s.on_player_join('Alice')
    s.on_player_join('Bob')
    now[0] = 10
    s.on_player_left('unknown')
    now[0] = 20
    s.on_player_left('Alice')
    now[0] = 30
    s.on_unmount()
    assert s.stats.player_time_ns_v2 == 50
    assert s.stats.use_time_ns_v2 == 30
    assert not any(t.name == 'StatsChecker' for t in threading.enumerate())


def test_worker_stop_wakes_promptly():
    from mount.MountSlot import StatsChecker
    callbacks = []
    worker = StatsChecker(600, lambda: callbacks.append(1))
    worker.start()
    worker.stop()
    worker.join(1)
    assert not worker.is_alive() and not callbacks


def test_legal_space_path_ending_confirm_is_exact(environment):
    m, _, _ = environment
    from mount.constants import MOUNTABLE_CONFIG
    original = Path(m.servers_as_list[1])
    target = original.parent / 'legal target --confirm'
    target.mkdir()
    (target / MOUNTABLE_CONFIG).write_bytes((original / MOUNTABLE_CONFIG).read_bytes())
    m._config.available_servers.append(str(target))
    source = CommandUser()
    command_root(m).execute(source, '!!mount switch ' + str(target))
    # The operations layer replaces legacy pending mounts with frozen votes.
    # Preserve QA-L01's exact-target assertion at that new public boundary.
    assert m.vote is not None and m.vote.target == str(target), source.replies
