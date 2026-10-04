import sys
import types

from .cmd_tree import register_commands
from .config import MountConfig
from .MountManager import MountManager
from .utils import rtr

manager = None
# Deliberately outside the reloadable plugin package. A full unload followed
# by a fresh load (prev_module=None) must still find a running old executor.
_lifecycle = sys.modules.setdefault('_mount_operation_lifecycle', types.ModuleType('_mount_operation_lifecycle'))


def on_load(server, prev_module):
    global manager
    previous = getattr(prev_module, 'manager', None) or getattr(_lifecycle, 'owner', None)
    # Keep exactly one executor/owner across reload. Never block the event
    # thread waiting for startup events required by the old executor.
    if previous and previous.executing:
        manager = previous
        manager.closed = False
        _lifecycle.owner = manager
        register_commands(server, manager)
        return
    if previous:
        previous.close()
        previous.current_slot.release(previous._config.mount_name)
    manager = MountManager(MountConfig.load())
    if previous:
        manager.cooldowns = dict(previous.cooldowns)
        manager.results = dict(previous.results)
        manager.players = previous.players
    _lifecycle.owner = manager
    register_commands(server, manager)
    if server.is_server_startup():
        manager.on_start()


def on_unload(server):
    if manager:
        manager.close()


def on_mcdr_stop(server):
    on_unload(server)


def on_server_startup(server):
    if manager:
        manager.on_start()


def on_server_stop(server, code):
    if manager:
        manager.on_stop()


def on_info(server, info):
    if manager:
        manager.on_info(info)


def on_player_joined(server, player, info):
    if manager:
        manager.player_event(player, True)
        if manager._config.welcome_player:
            server.tell(player, rtr('help_msg.welcome'))


def on_player_left(server, player):
    if manager:
        manager.player_event(player, False)
