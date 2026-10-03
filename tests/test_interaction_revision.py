import json
from pathlib import Path

import pytest


def test_invalid_page_and_navigation(environment):
    m, _, Source = environment
    m._config.list_size = 1
    for page in (0, -1, 99, 'bad'):
        src = Source()
        m.list_servers(src, page)
        assert 'page_corrected' in str(src.replies[0])
        nav = src.replies[-1].to_json_object()
        assert 'list 0' not in str(nav) and 'list 2' in str(nav)
        assert str(nav).count('clickEvent') == 1
    src = Source()
    m.list_servers(src, 2)
    nav = str(src.replies[-1].to_json_object())
    assert nav.count('clickEvent') == 1 and 'list 1' in nav


@pytest.mark.parametrize('reason', ['occupied', 'unchecked', 'missing', 'invalid'])
def test_unavailable_reason_stays_visible(environment, reason):
    m, _, Source = environment
    from mount.constants import MOUNTABLE_CONFIG
    target = Path(m.servers_as_list[1])
    config = target/MOUNTABLE_CONFIG
    if reason == 'missing':
        m._config.available_servers[1] = str(target/'absent')
    elif reason == 'invalid':
        config.write_text('{', encoding='utf-8')
    else:
        data = json.loads(config.read_text())
        data['occupied_by' if reason == 'occupied' else 'checked'] = 'other' if reason == 'occupied' else False
        config.write_text(json.dumps(data))
    src = Source()
    m.list_servers(src)
    visible = '\n'.join(map(str, src.replies))
    assert 'flow.'+reason in visible
    assert 'flow.switch' not in visible


def test_duplicate_names_use_private_exact_tokens(environment):
    m, _, Source = environment
    from test_commands_stats import command_root
    from mount.constants import MOUNTABLE_CONFIG
    first = Path(m.servers_as_list[1])
    second = first.parent/'other'/first.name
    second.mkdir(parents=True)
    (second/MOUNTABLE_CONFIG).write_bytes((first/MOUNTABLE_CONFIG).read_bytes())
    m._config.available_servers.append(str(second))
    src = Source()
    m.list_servers(src)
    serialized = '\n'.join(json.dumps(row.to_json_object()) if hasattr(row, 'to_json_object') else str(row) for row in src.replies)
    assert str(first.parent) not in serialized and '#1' in serialized and '#2' in serialized
    root = command_root(m)
    for path in (str(first), str(second)):
        root.execute(src, '!!mount switch '+m.target_token(path))
        assert m.vote.target == path
        m.cancel(src, m.vote.request_id)
    m.request_mount(src, 'slot:'+'0'*64)
    assert m.vote is None


def test_untrusted_activity_falls_back_to_configured_order(environment):
    m, _, Source = environment
    from mount.constants import MOUNTABLE_CONFIG
    current = Path(m.current_slot.path)/MOUNTABLE_CONFIG
    data = json.loads(current.read_text())
    data['stats']['schema_version'] = 1
    current.write_text(json.dumps(data))
    target = Path(m.servers_as_list[1])/MOUNTABLE_CONFIG
    data = json.loads(target.read_text())
    data['stats']['player_time_ns_v2'] = 999999
    target.write_text(json.dumps(data))
    m._config.list_order = 'activity'
    src = Source()
    m.list_servers(src)
    text = '\n'.join(map(str, src.replies))
    assert 'activity_fallback' in text
    assert text.index('current') < text.index('target with spaces')


@pytest.mark.parametrize('language', ['en_us', 'zh_cn'])
@pytest.mark.parametrize('mode', ['full', 'region'])
def test_rendered_language_scope_rules_before_buttons(environment, monkeypatch, language, mode):
    from ruamel.yaml import YAML
    import mount.MountManager as mm
    from mount.constants import MOUNTABLE_CONFIG
    m, server, Source = environment
    translations = YAML().load((Path(__file__).resolve().parents[1]/'lang'/(language+'.yml')).read_text(encoding='utf-8'))['mount']
    def translate(key, **kwargs):
        section, field = key.split('.')
        return translations[section][field].format(**kwargs)
    monkeypatch.setattr(mm, 'rtr', translate)
    config = Path(m.current_slot.path)/MOUNTABLE_CONFIG
    data = json.loads(config.read_text())
    data['reset_type'] = mode
    config.write_text(json.dumps(data))
    m.request_reset(Source())
    bob = Source('Bob')
    m.show_status(bob, m.vote.request_id)
    yes = translations['flow']['yes']
    for text in (str(server.messages[-1]), str(bob.replies[-1])):
        for word in (mode, 'world', 'template', 'playerdata', 'advancements', 'stats'):
            assert word in text and text.index(word) < text.index(yes)
        assert str(m.current_slot.path) not in text
    broadcast = str(server.messages[-1])
    assert '100.0%' in broadcast and '3/3' in broadcast and '60' in broadcast
    assert ('New arrivals excluded' if language == 'en_us' else '新加入不计入') in broadcast
    assert ('departures do not lower' if language == 'en_us' else '离开不降低') in broadcast
    print(language, mode, broadcast)
