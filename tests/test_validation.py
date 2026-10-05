import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from mount.backup_helper import preflight, reject_links
from mount.config import MountConfig


@pytest.mark.parametrize('key,value',[
    ('switch_ratio',0),('reset_ratio',1.01),('vote_timeout',0),
    ('backup_permission',5),('cancel_permission',-1),('vote_cooldown',-1)])
def test_invalid_config_rejected(key,value):
    config = MountConfig()
    setattr(config,key,value)
    with pytest.raises(ValueError):
        config.validate()


def test_real_link_path_rejected(tmp_path):
    source, linked = tmp_path/'source', tmp_path/'linked'
    source.mkdir()
    try:
        os.symlink(source,linked,target_is_directory=True)
    except OSError as exc:
        pytest.skip('OS does not permit test symlinks: '+str(exc))
    with pytest.raises(ValueError,match='unsafe_link'):
        reject_links(linked)


def test_reparse_point_rejected(tmp_path,monkeypatch):
    actual = Path.lstat
    def lstat(path):
        st = actual(path)
        if path==tmp_path:
            return SimpleNamespace(st_mode=st.st_mode,st_file_attributes=0x400)
        return st
    monkeypatch.setattr(Path,'lstat',lstat)
    with pytest.raises(ValueError,match='unsafe_link'):
        reject_links(tmp_path)


def test_untrusted_command_identity_rejected(environment):
    m, server, Source = environment
    fake = SimpleNamespace(is_player=True,player='Admin',has_permission=lambda level:True,reply=lambda text:None)
    assert not m.can_force(fake)
    m.request_mount(fake,m.servers_as_list[1])
    assert m.vote is None


def test_departures_do_not_reduce_threshold_and_arrivals_excluded(environment):
    m, server, Source = environment
    m.request_mount(Source(),m.servers_as_list[1])
    vote = m.vote
    m.players.event('Bob',False)
    m.players.event('Dave',True)
    m.cast_vote(Source('Dave'),vote.request_id,True)
    m.cast_vote(Source('Alice'),vote.request_id,True)
    assert vote.threshold==2 and vote.yes==1 and server.stops==0


def test_lock_failed_acquisition_and_foreign_owner_cleanup(environment):
    m, server, Source = environment
    from mount.MountSlot import MountSlot
    a,b = MountSlot(m.servers_as_list[1]),MountSlot(m.servers_as_list[1])
    a.lock('external')
    with pytest.raises(ResourceWarning):
        b.lock('isolated')
    assert not b.slot_lock.locked()
    b.release('isolated')
    assert MountSlot(a.path).occupied_by=='external'
    a.release('external')


def test_vote_cooldown_counts_from_termination(environment):
    m, server, Source = environment
    m._config.vote_cooldown = 60
    m.request_mount(Source(),m.servers_as_list[1])
    m.cancel(Source(),m.vote.request_id)
    m.request_mount(Source(),m.servers_as_list[1])
    assert m.vote is None
