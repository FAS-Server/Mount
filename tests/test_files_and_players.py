import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mount.backup_helper import run_backup, inventory, preflight
from mount.list_order import order_slots
from mount.players import PlayerRegistry
from mount.reset_helper import ResetHelper


def test_snapshot_failure_event_does_not_restore_trust():
    registry = PlayerRegistry()
    registry.begin()
    registry.query -= 10
    info = SimpleNamespace(is_from_server=True,is_player=False,
                           content='There are 1 of a max of 20 players online: Alice')
    assert not registry.accept(info,'vanilla_handler')
    assert registry.take_retry()
    registry.event('Bob',True)
    registry.event('Alice',False)
    assert registry.snapshot() is None
    registry.begin()
    registry.event('Bob',True)
    registry.event('Alice',False)
    assert registry.accept(info,'vanilla_handler')
    assert registry.snapshot() == frozenset({'Bob'})
    registry.invalidate()
    assert not registry.accept(info,'vanilla_handler')


def test_snapshot_count_and_chat_rejected():
    registry = PlayerRegistry()
    registry.begin()
    info = SimpleNamespace(is_from_server=True,is_player=True,
                           content='There are 1 of a max of 20 players online: Alice')
    assert not registry.accept(info,'vanilla_handler')
    info.is_player = False
    info.content = 'There are 2 of a max of 20 players online: Alice'
    assert not registry.accept(info,'vanilla_handler')
    assert registry.snapshot() is None


def test_backup_content_corruption_and_commit_failure(tmp_path, monkeypatch):
    import mount.backup_helper as helper
    source, dest = tmp_path/'server', tmp_path/'backup'
    (source/'world').mkdir(parents=True)
    (source/'world'/'data').write_bytes(b'1234')
    original = helper.shutil.copytree
    def corrupt(src,dst):
        original(src,dst)
        (Path(dst)/'data').write_bytes(b'4321')
    monkeypatch.setattr(helper.shutil,'copytree',corrupt)
    with pytest.raises(ValueError,match='validation_failed'):
        run_backup(source,'',dest,['world'])
    assert list(dest.iterdir()) == [] and (source/'world'/'data').read_bytes() == b'1234'
    monkeypatch.setattr(helper.shutil,'copytree',original)
    def fail(*args):
        raise OSError('commit failure')
    monkeypatch.setattr(Path,'rename',fail)
    with pytest.raises(OSError,match='commit failure'):
        run_backup(source,'',dest,['world'])
    assert list(dest.iterdir()) == []


def test_backup_manifest_skipped_and_path_isolation(tmp_path):
    source, dest = tmp_path/'server', tmp_path/'backup'
    (source/'world'/'empty').mkdir(parents=True)
    (source/'world'/'data').write_bytes(b'abc')
    backup_id, worlds, missing = run_backup(source,'template',dest,['world','world_nether'])
    manifest = json.loads((dest/backup_id/'manifest.json').read_text())
    assert worlds == ['world'] and missing == ['world_nether']
    assert manifest['worlds']['world'] == inventory(source/'world')
    with pytest.raises(ValueError,match='invalid_backup_path'):
        preflight(source,'template',source/'backups',['world'])
    with pytest.raises(ValueError,match='invalid_world_path'):
        preflight(source,'',dest,['../outside'])


@pytest.mark.parametrize('mode',['full','region'])
def test_reset_actual_world_scope_and_reserved_data(tmp_path, mode):
    (tmp_path/'world'/'playerdata').mkdir(parents=True)
    (tmp_path/'world'/'playerdata'/'player').write_text('original')
    (tmp_path/'world'/'region').write_text('old')
    (tmp_path/'template'/'world'/'playerdata').mkdir(parents=True)
    (tmp_path/'template'/'world'/'playerdata'/'player').write_text('template')
    (tmp_path/'template'/'world'/'region').write_text('new')
    (tmp_path/'world_nether').mkdir()
    (tmp_path/'world_nether'/'data').write_text('retain absent template')
    ResetHelper.reset(tmp_path,'template',mode)
    assert (tmp_path/'world'/'region').read_text() == 'new'
    assert (tmp_path/'world'/'playerdata'/'player').read_text() == ('original' if mode == 'region' else 'template')
    assert (tmp_path/'world_nether'/'data').read_text() == 'retain absent template'


def test_stable_sort_pinned_then_activity():
    entries = [('a',10),('b',10),('c',1),('unavailable',0)]
    assert order_slots(entries,['missing','c'],'configured') == [entries[2],entries[0],entries[1],entries[3]]
    assert order_slots(entries,['c'],'activity') == [entries[2],entries[0],entries[1],entries[3]]
