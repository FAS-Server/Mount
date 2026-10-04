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


