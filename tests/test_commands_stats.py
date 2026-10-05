import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcdreforged.api.types import PlayerCommandSource
from mcdreforged.api.command import RequirementNotMet

from mount.cmd_tree import register_commands


class CommandUser(PlayerCommandSource):
    def __init__(self, name='Alice', permission=0):
        self.name, self.permission, self.replies = name, permission, []

    @property
    def player(self):
        return self.name

    @property
    def is_player(self):
        return self.player is not None

    @property
    def is_console(self):
        return not self.is_player

    def get_permission_level(self):
        return self.permission

    def reply(self,text,**kwargs):
        self.replies.append(text)


def command_root(m):
    holder = []
    server = SimpleNamespace(register_command=holder.append, register_help_message=lambda *a:None,
                             get_self_metadata=lambda:SimpleNamespace(version='test'))
    register_commands(server,m)
    node = holder[0]
    if hasattr(node, 'execute'):
        return node
    # MCDR 2.14 invokes callbacks synchronously and returns None. MCDR 2.16
    # returns executions requiring its own invoker. Use the real traversal
    # result instead of treating every version without execute as 2.16.
    class Root:
        def execute(self,source,command):
            executions = node._entry_execute(source,command)
            if executions is None:
                return
            from mcdreforged.command.builder.callback import DirectCallbackInvoker
            for execution in executions:
                execution.scheduled_callback.invoke(DirectCallbackInvoker())
    return Root()


def test_actual_mcdr_parser_spaces_and_explicit_vote(environment):
    m, server, _ = environment
    root, src = command_root(m), CommandUser()
    root.execute(src,'!!mount switch '+m.servers_as_list[1])
    request_id = m.vote.request_id
    root.execute(src,'!!mount status')
    assert m.vote.request_id == request_id and m.vote.yes == 0 and server.stops == 0
    root.execute(src,'!!m cancel '+request_id)
    root.execute(src,'!!mount switch '+m.servers_as_list[1])
    assert m.vote.target == m.servers_as_list[1] and m.vote.yes == 0
    root.execute(src,'!!mount list 0')
    assert src.replies


def test_restricted_help_list_and_manual_command(environment):
    m, server, _ = environment
    root, user, admin = command_root(m), CommandUser(), CommandUser('Admin',3)
    root.execute(user,'!!mount')
    root.execute(user,'!!mount list')
    user_text = '\n'.join(str(text) for text in user.replies)
    assert 'backup' not in user_text and 'force ' not in user_text
    with pytest.raises(RequirementNotMet):
        root.execute(user,'!!mount backup')
    with pytest.raises(RequirementNotMet):
        root.execute(user,'!!mount force reset')
    root.execute(admin,'!!mount')
    root.execute(admin,'!!mount list')
    admin_text = '\n'.join(str(text) for text in admin.replies)
    assert 'backup' in admin_text and 'force ' in admin_text
    assert not Path(m._config.backup_root).exists()




def test_defaults_and_invalid_page_size(environment):
    m, server, Source = environment
    from mount.config import MountConfig
    legacy = MountConfig.deserialize({'current_server':m.current_slot.path,'servers_path':['../servers']})
    assert legacy.force_players == [] and legacy.backup_permission == 3
    assert legacy.switch_ratio == .6 and legacy.reset_ratio == 1
    m._config.available_servers = []
    m._config.list_size = 0
    m.list_servers(Source())
    m._config.list_size = -2
    m.list_servers(Source(),-10)


def test_current_config_rejects_string_path_and_drops_audit_fields(environment, monkeypatch):
    import mount.config as config
    with pytest.raises(TypeError):
        config.MountConfig.deserialize({'servers_path': '../servers'})
    stats = config.SlotStats.deserialize({'total_use_time': 999, 'total_player_time': 999, 'total_players': 999})
    assert not any(key.startswith('total_') for key in stats.serialize())
    assert stats.use_time_ns_v2 == 0 and stats.player_time_ns_v2 == 0
