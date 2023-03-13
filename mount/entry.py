from typing import Optional

from mcdreforged.api.types import Info, PluginServerInterface

from .cmd_tree import register_commands
from .config import MountConfig
from .constants import CONFIG_NAME
from .MountManager import MountManager
from .utils import rtr

manager: Optional[MountManager] = None


def on_load(server: PluginServerInterface, prev_module):
    global manager
    config: MountConfig = server.load_config_simple(
        file_name=CONFIG_NAME, in_data_folder=False, target_class=MountConfig)
    manager = MountManager(config=config)
    register_commands(server, manager)

    if manager.current_slot and server.is_server_running():
        manager.current_slot.on_mount()


def on_unload(server: PluginServerInterface):
    if not manager:
        return
    if manager.current_slot and server.is_server_running():
        manager.current_slot.on_unmount()


def on_server_startup(server: PluginServerInterface):
    if not manager:
        return
    if manager.current_slot:
        manager.current_slot.on_mount()


def on_server_stop(server: PluginServerInterface, code: int):
    if not manager:
        return
    if manager.current_slot:
        manager.current_slot.on_unmount()


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    if not manager:
        return
    if manager._config.welcome_player:
        server.tell(player, rtr('help_msg.welcome'))
    if manager.current_slot:
        manager.current_slot.on_player_join(player)


def on_player_left(server: PluginServerInterface, player: str):
    if not manager:
        return
    if manager.current_slot:
        manager.current_slot.on_player_left(player)
