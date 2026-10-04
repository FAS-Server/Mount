import json
from pathlib import Path
import pytest
from ruamel.yaml import YAML
from mcdreforged.api.command import RequirementNotMet
from test_commands_stats import CommandUser, command_root
from test_qa_list import translate_real

@pytest.mark.parametrize('language', ['en_us', 'zh_cn'])
def test_real_language_capabilities_and_direct_backup(environment, monkeypatch, language):
    m, server, _ = environment
    flow = translate_real(monkeypatch, language)
    root = command_root(m)
    for name, level, backup, force in [('Alice',0,False,False),('Bob',3,True,False),('Admin',0,False,True)]:
        src = CommandUser(name,level)
        root.execute(src, '!!mount')
        root.execute(src, '!!mount list')
        visible = '\n'.join(map(str,src.replies))
        assert (flow['backup'] in visible) == backup
        assert (flow['management'] in visible) == force
        assert ('!!mount backup' in visible) == backup
        assert ('force confirm' in visible) == force
        for cmd, allowed in [('backup',backup),('force reset',force)]:
            if not allowed:
                with pytest.raises(RequirementNotMet):
                    root.execute(src,'!!mount '+cmd)
        print('CAPABILITY',language,name,visible)
    assert not Path(m._config.backup_root).exists() and server.stops == 0
    bob = CommandUser('Bob',3)
    m.list_servers(bob)
    actions = []
    def walk(value):
        if isinstance(value,dict):
            if 'clickEvent' in value: actions.append(value['clickEvent'])
            for item in value.values(): walk(item)
        elif isinstance(value,list):
            for item in value: walk(item)
    for row in bob.replies:
        if hasattr(row,'to_json_object'): walk(row.to_json_object())
    backup = [a for a in actions if a['value']=='!!mount backup']
    assert len(backup)==1 and backup[0]['action']=='run_command'
    root.execute(bob,backup[0]['value'])
    m.worker.join(5)
    assert not m.worker.is_alive() and m.vote is None and m.force is None
    assert server.stops == server.starts == 1
    assert len(list(Path(m._config.backup_root).glob('*/manifest.json')))==1
