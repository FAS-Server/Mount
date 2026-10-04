import json
from pathlib import Path

import pytest

from command_api import CommandUser, command_root


def test_old_commands_request_confirm_cancel(environment, monkeypatch):
    import mount.MountManager as mm
    m, server, Source = environment
    root = command_root(m)
    src = CommandUser()
    target = m.servers_as_list[1]
    root.execute(src, '!!mount '+target)
    assert mm.current_op is mm.Operation.REQUEST_MOUNT
    assert m.next_slot.path == target and server.stops == 0
    actions = []
    monkeypatch.setattr(m, '_do_mount', lambda source, slot: actions.append(('switch', slot.path)))
    root.execute(src, '!!mount --confirm')
    assert actions == [('switch', target)]
    root.execute(src, '!!m --abort')
    assert mm.current_op is mm.Operation.IDLE and m.next_slot is None
    root.execute(src, '!!mount --reset')
    assert mm.current_op is mm.Operation.REQUEST_RESET
    monkeypatch.setattr(m, '_do_reset', lambda source, slot: actions.append(('reset', slot.path)))
    root.execute(src, '!!mount --confirm')
    assert actions[-1] == ('reset', m.current_slot.path)
    root.execute(src, '!!mount --abort')
    assert mm.current_op is mm.Operation.IDLE


def test_tokens_names_and_spaces(environment):
    import mount.MountManager as mm
    from mount.constants import MOUNTABLE_CONFIG
    m, server, _ = environment
    first = Path(m.servers_as_list[1])
    second = first.parent/'other'/first.name
    second.mkdir(parents=True)
    (second/MOUNTABLE_CONFIG).write_bytes((first/MOUNTABLE_CONFIG).read_bytes())
    m._config.available_servers.append(str(second))
    src = CommandUser()
    m.list_servers(src)
    rendered = json.dumps([x.to_json_object() if hasattr(x, 'to_json_object') else str(x) for x in src.replies])
    assert str(first.parent) not in rendered and '#1' in rendered and '#2' in rendered
    root = command_root(m)
    for path in (str(first), str(second)):
        root.execute(src, '!!mount '+m.target_token(path))
        assert m.next_slot.path == path
        root.execute(src, '!!mount --abort')
    root.execute(src, '!!mount slot:'+'0'*64)
    assert m.next_slot is None and mm.current_op is mm.Operation.IDLE


@pytest.mark.parametrize('language', ['en_us', 'zh_cn'])
def test_real_list_text_and_buttons(environment, monkeypatch, language):
    from ruamel.yaml import YAML
    import mount.MountManager as mm
    m, _, _ = environment
    translations = YAML().load((Path(__file__).resolve().parents[1]/'lang'/(language+'.yml')).read_text(encoding='utf-8'))['mount']
    def translate(key, **kwargs):
        section, field = key.split('.')
        return translations[section][field].format(**kwargs)
    monkeypatch.setattr(mm, 'rtr', translate)
    m._config.pinned_servers = [m.current_slot.path]
    src = CommandUser()
    m.list_servers(src)
    rendered = '\n'.join(map(str, src.replies))
    assert translations['flow']['pinned'] in rendered
    assert translations['flow']['current'] in rendered
    assert translations['flow']['available'] in rendered
    assert m.current_slot.path not in rendered
    command = src.replies[2].to_json_object()
    assert m.target_token(m.servers_as_list[1]) in str(command)
    assert 'run_command' in str(command) and 'switch ' not in str(command)
    print(language, rendered)


def test_old_config_empty_and_bad_size(environment):
    from mount.config import MountConfig
    m, _, Source = environment
    old = MountConfig.deserialize({'current_server': m.current_slot.path, 'servers_path': '../servers'})
    assert old.pinned_servers == [] and old.list_order == 'configured'
    assert not hasattr(old, 'backup_permission')
    m._config.available_servers = []
    for size in (0, -2, 'bad', True):
        m._config.list_size = size
        src = Source()
        m.list_servers(src, 'bad')
        assert 'clickEvent' not in str(src.replies[-1].to_json_object())


def test_reload_and_unload_stop_statistics(environment, monkeypatch):
    from types import SimpleNamespace
    import mount.entry as entry
    m, server, _ = environment
    monkeypatch.setattr(entry, 'manager', m)
    monkeypatch.setattr(entry, 'register_commands', lambda *args: None)
    monkeypatch.setattr(entry.MountConfig, 'load', lambda: m._config)
    m.current_slot.on_mount()
    entry.on_load(server, SimpleNamespace(manager=m))
    newer = entry.manager
    assert newer is not m
    entry.on_unload(server)
    assert not any(t.name == 'StatsChecker' for t in __import__('threading').enumerate())


@pytest.mark.parametrize('input_kind', ['path', 'token', 'path_alias', 'token_alias'])
def test_confirm_suffix_prefers_exact_configured_target(environment, input_kind):
    from mount.constants import MOUNTABLE_CONFIG
    m, _, _ = environment
    base = Path(m.servers_as_list[1])
    target = Path(str(base)+' --confirm')
    target.mkdir()
    (target/MOUNTABLE_CONFIG).write_bytes((base/MOUNTABLE_CONFIG).read_bytes())
    m._config.available_servers.append(str(target))
    value = m.target_token(str(target)) if input_kind.startswith('token') else str(target)
    if input_kind.endswith('alias'):
        value += ' --confirm'
    src = CommandUser()
    command_root(m).execute(src, '!!mount '+value)
    assert m.next_slot is not None and m.next_slot.path == str(target)
