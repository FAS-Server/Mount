import re
import json
import threading
from pathlib import Path

import pytest

from mount.list_order import order_slots
from command_api import command_root, CommandUser
def test_monotonic_statistics_duplicates_unmount_remount(environment, monkeypatch):
    m, server, _ = environment
    import mount.MountSlot as module
    now = [100]
    monkeypatch.setattr(module.time,'monotonic_ns',lambda:now[0])
    slot = m.current_slot
    slot.on_mount()
    now[0] = 110
    slot.on_player_join('Alice')
    now[0] = 120
    slot.on_player_join('Alice')
    now[0] = 130
    slot.on_player_left('Alice')
    now[0] = 140
    slot.on_unmount()
    assert slot.stats.use_time_ns_v2 == 40 and slot.stats.player_time_ns_v2 == 20
    now[0] = 1000
    slot.on_mount()
    slot.on_mount()
    now[0] = 1010
    slot.on_unmount()
    assert slot.stats.use_time_ns_v2 == 50
    assert not any(t.name=='StatsChecker' for t in threading.enumerate())

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

def test_list_marks_pinned_current_and_disables_border_actions(environment):
    m, server, Source = environment
    m._config.pinned_servers = [m.current_slot.path]
    src = Source()
    m.list_servers(src,1)
    visible = '\n'.join(map(str,src.replies))
    assert 'pinned' in visible.lower() and 'current' in visible.lower() and 'flow.unavailable' not in visible, visible
    navigation = src.replies[-1].to_json_object()
    assert 'clickEvent' not in str(navigation), navigation

def test_list_border_buttons_have_no_click_action(environment):
    m, server, Source = environment
    src = Source()
    m.list_servers(src,1)
    navigation = src.replies[-1].to_json_object()
    assert 'clickEvent' not in str(navigation), navigation

def test_language_fields_match_and_utf8_is_valid():
    from ruamel.yaml import YAML
    root = Path(__file__).resolve().parents[1]
    data = [YAML().load((root/'lang'/name).read_text(encoding='utf-8'))['mount']['flow'] for name in ['en_us.yml','zh_cn.yml']]
    assert data[0].keys() == data[1].keys()
    for key in data[0]:
        assert set(re.findall(r'{(\w+)}',data[0][key])) == set(re.findall(r'{(\w+)}',data[1][key]))
        assert '\ufffd' not in data[1][key]

def test_stable_sort_pinned_then_activity():
    entries = [('a',10),('b',10),('c',1),('unavailable',0)]
    assert order_slots(entries,['missing','c'],'configured') == [entries[2],entries[0],entries[1],entries[3]]
    assert order_slots(entries,['c'],'activity') == [entries[2],entries[0],entries[1],entries[3]]
