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


def test_actual_mcdr_parser_spaces_and_legacy(environment):
    m, server, _ = environment
    root, src = command_root(m), CommandUser()
    root.execute(src,'!!mount switch '+m.servers_as_list[1])
    request_id = m.vote.request_id
    root.execute(src,'!!mount --confirm')
    assert m.vote.request_id == request_id and m.vote.yes == 0 and server.stops == 0
    root.execute(src,'!!m --abort')
    root.execute(src,'!!mount '+m.servers_as_list[1]+' --confirm')
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


def test_old_config_and_invalid_page_size(environment):
    m, server, Source = environment
    from mount.config import MountConfig
    legacy = MountConfig.deserialize({'current_server':m.current_slot.path,'servers_path':'../servers'})
    assert legacy.force_players == [] and legacy.backup_permission == 3
    assert legacy.switch_ratio == .6 and legacy.reset_ratio == 1
    m._config.available_servers = []
    m._config.list_size = 0
    m.list_servers(Source())
    m._config.list_size = -2
    m.list_servers(Source(),-10)
