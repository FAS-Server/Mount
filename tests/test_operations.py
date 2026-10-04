import threading
from pathlib import Path

from mount.vote import VoteSession


def test_threshold_frozen_and_first_vote():
    vote = VoteSession('switch', 'x', 'Alice', frozenset({'Alice','Bob','Carol'}), .6, 60)
    assert vote.threshold == 2
    assert not vote.cast('Alice', True)
    import pytest
    with pytest.raises(ValueError, match='duplicate_vote'):
        vote.cast('Alice', False)
    with pytest.raises(ValueError, match='not_in_roster'):
        vote.cast('Dave', True)
    assert vote.cast('Bob', True)
    assert VoteSession('reset','x','',frozenset(),1,60).threshold == 0


def test_old_confirm_does_not_execute_and_stale_cancel(environment):
    m, server, Source = environment
    m.request_mount(Source(), m.servers_as_list[1], True)
    first = m.vote.request_id
    m.confirm_operation(Source())
    assert server.stops == 0 and m.vote.yes == 0
    m.cancel(Source(), first)
    m.request_mount(Source(), m.servers_as_list[1])
    second = m.vote.request_id
    m.cancel(Source(), first)
    m.expire_vote(first)
    assert m.vote.request_id == second


def test_concurrent_votes_execute_once(environment):
    m, server, Source = environment
    m.request_mount(Source(), m.servers_as_list[1])
    request_id = m.vote.request_id
    threads = [threading.Thread(target=m.cast_vote, args=(Source(name),request_id,True))
               for name in ['Alice','Bob','Bob','Admin']]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    m.worker.join(5)
    assert server.stops == server.starts == 1
    assert m.executing is None and m.current_slot.path == m.servers_as_list[1]


def test_force_summary_keeps_vote_and_requires_owner(environment, monkeypatch):
    m, server, Source = environment
    m.request_mount(Source(), m.servers_as_list[1])
    vote_id = m.vote.request_id
    m.request_force(Source('Admin'), 'switch', m.servers_as_list[1])
    force_id = m.force.request_id
    assert m.vote.request_id == vote_id
    m.confirm_force(Source('Alice'), force_id)
    assert m.vote.request_id == vote_id and server.stops == 0
    m.expire_force(force_id)
    assert m.vote.request_id == vote_id
    m.request_force(Source('Admin'), 'switch', m.servers_as_list[1])
    force_id = m.force.request_id
    m.confirm_force(Source('Admin'), force_id)
    m.confirm_force(Source('Admin'), force_id)
    m.worker.join(5)
    assert server.stops == 1 and m.vote is None


def test_force_bound_to_exact_old_vote(environment):
    m, server, Source = environment
    m.request_mount(Source(), m.servers_as_list[1])
    m.request_force(Source('Admin'), 'switch', m.servers_as_list[1])
    force_id = m.force.request_id
    m.cancel(Source(), m.vote.request_id)
    m.request_mount(Source(), m.servers_as_list[1])
    new_vote = m.vote.request_id
    m.confirm_force(Source('Admin'), force_id)
    assert server.stops == 0 and m.vote.request_id == new_vote


def test_backup_permission_direct_execution_and_stopped_server(environment):
    m, server, Source = environment
    m.request_backup(Source(permission=0))
    assert not Path(m._config.backup_root).exists() and server.stops == 0
    server.running = server.started = False
    m.request_backup(Source(None,3))
    m.worker.join(5)
    assert len(list(Path(m._config.backup_root).glob('*/manifest.json'))) == 1
    assert server.stops == server.starts == 0 and m.executing is None


def test_stop_timeout_copies_nothing(environment):
    m, server, Source = environment
    server.stop_works = False
    m.request_backup(Source(None,3))
    m.worker.join(5)
    assert not Path(m._config.backup_root).exists()
    assert m.executing is None and server.starts == 0


def test_backup_start_timeout_keeps_verified_copy(environment):
    m, server, Source = environment
    server.start_works = False
    src = Source(None,3)
    m.request_backup(src)
    m.worker.join(5)
    assert len(list(Path(m._config.backup_root).glob('*/manifest.json'))) == 1
    assert m.executing is None and 'startup_failed' in str(src.replies)


def test_target_occupied_after_vote_does_not_stop(environment):
    m, server, Source = environment
    from mount.MountSlot import MountSlot
    m.request_mount(Source(), m.servers_as_list[1])
    request_id = m.vote.request_id
    slot = MountSlot(m.servers_as_list[1])
    slot.lock('external')
    m.cast_vote(Source(),request_id,True)
    m.cast_vote(Source('Bob'),request_id,True)
    m.worker.join(5)
    assert server.stops == 0 and m.executing is None
    assert MountSlot(slot.path).occupied_by == 'external'
    slot.release('external')


def test_reload_reuses_executor_owner(environment, monkeypatch):
    m, server, Source = environment
    from mount import entry
    from types import SimpleNamespace
    m.executing = 'running'
    monkeypatch.setattr(entry,'register_commands',lambda *args: None)
    m.close()
    entry.on_load(server, SimpleNamespace(manager=m))
    assert entry.manager is m and not m.closed
    m.executing = None
