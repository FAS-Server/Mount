import threading
from pathlib import Path
from types import SimpleNamespace

from mount import entry


def test_backup_duplicate_click_and_unload_reload_in_copy(environment, monkeypatch):
    m, server, Source = environment
    import mount.MountManager as module
    original = module.run_backup
    entered, finish = threading.Event(), threading.Event()
    def slow(*args):
        entered.set()
        assert finish.wait(5)
        return original(*args)
    monkeypatch.setattr(module,'run_backup',slow)
    m.request_backup(Source(None,3))
    assert entered.wait(5)
    m.request_backup(Source(None,3))
    assert server.stops==1
    m.close()
    monkeypatch.setattr(entry,'register_commands',lambda *a:None)
    entry.on_load(server,SimpleNamespace(manager=m))
    assert entry.manager is m
    finish.set()
    m.worker.join(5)
    assert server.starts==1 and m.executing is None
    assert len(list(Path(m._config.backup_root).glob('*/manifest.json')))==1


def test_fresh_load_finds_unloaded_executor(environment,monkeypatch):
    m, server, Source = environment
    m.executing = 'in-flight'
    entry._lifecycle.owner = m
    m.close()
    monkeypatch.setattr(entry,'register_commands',lambda *a:None)
    entry.on_load(server,None)
    assert entry.manager is m and not m.closed
    m.executing = None


def test_reset_failure_recovers_and_clears_request(environment,monkeypatch):
    m, server, Source = environment
    import mount.MountManager as module
    def fail(*args):
        raise OSError('injected reset failure')
    monkeypatch.setattr(module.ResetHelper,'reset',fail)
    m.request_force(Source('Admin'),'reset')
    m.confirm_force(Source('Admin'),m.force.request_id)
    m.worker.join(5)
    assert m.executing is None and server.stops==server.starts==1


def test_force_target_change_does_not_cancel_original_vote(environment):
    m, server, Source = environment
    from mount.MountSlot import MountSlot
    m.request_mount(Source(),m.servers_as_list[1])
    old = m.vote.request_id
    m.request_force(Source('Admin'),'switch',m.servers_as_list[1])
    force_id = m.force.request_id
    slot = MountSlot(m.servers_as_list[1])
    slot.edit_config('checked','false')
    m.confirm_force(Source('Admin'),force_id)
    assert m.vote.request_id==old and server.stops==0


def test_force_cancel_keeps_vote_and_not_management_permission(environment):
    m, server, Source = environment
    m.request_mount(Source(),m.servers_as_list[1])
    old = m.vote.request_id
    m.request_force(Source('Admin'),'switch',m.servers_as_list[1])
    m.cancel(Source('Admin'),old)
    assert m.vote.request_id==old
    m.cancel(Source('Admin'),m.force.request_id)
    assert m.force is None and m.vote.request_id==old


def test_snapshot_barrier_ignores_old_service_output():
    from mount.players import PlayerRegistry
    p = PlayerRegistry()
    p.begin(100)
    info = SimpleNamespace(id=99,is_player=False,is_from_server=True,
        content='There are 1 of a max of 20 players online: Alice')
    assert not p.accept(info,'vanilla_handler')
    info.id = 101
    assert p.accept(info,'vanilla_handler')


def test_old_query_must_drain_before_new_query_even_after_unload():
    from mount.players import PlayerRegistry
    p = PlayerRegistry()
    assert p.begin(100)
    p.invalidate(preserve_query=True)
    assert not p.begin(200)
    p.event('Bob',True)
    assert p.snapshot() is None
    old = SimpleNamespace(id=101,is_player=False,is_from_server=True,
        content='There are 1 of a max of 20 players online: Alice')
    assert not p.accept(old,'vanilla_handler')
    assert p.take_retry()
    assert p.begin(200)
    assert not p.accept(old,'vanilla_handler')
    fresh = SimpleNamespace(id=201,is_player=False,is_from_server=True,
        content='There are 1 of a max of 20 players online: Bob')
    assert p.accept(fresh,'vanilla_handler') and p.snapshot()==frozenset({'Bob'})


def test_single_player_explicit_vote_and_no_players(environment):
    m, server, Source = environment
    m.players.players = set()
    m.request_mount(Source(),m.servers_as_list[1])
    assert m.vote is None and server.stops==0
    m.players.players = {'Alice'}
    m.request_mount(Source(),m.servers_as_list[1])
    assert m.vote.yes==0 and m.vote.threshold==1
    m.cast_vote(Source(),m.vote.request_id,True)
    m.worker.join(5)
    assert server.stops==1


def test_unload_between_execution_claim_and_launch_cleans_owner(environment,monkeypatch):
    m, server, Source = environment
    launch = m.launch
    def unload_first(*args):
        m.close()
        launch(*args)
    monkeypatch.setattr(m,'launch',unload_first)
    m.players.players = {'Alice'}
    m.request_mount(Source(),m.servers_as_list[1])
    m.cast_vote(Source(),m.vote.request_id,True)
    m.worker.join(5)
    from mount.MountSlot import MountSlot
    assert m.executing is None and server.stops==0
    assert MountSlot(m.current_slot.path).occupied_by==''
    assert MountSlot(m.servers_as_list[1]).occupied_by==''
