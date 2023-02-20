from typing import Optional

from mcdreforged.api.types import Info, PluginServerInterface

from .cmd_tree import register_commands
from .config import MountConfig
from .constants import CONFIG_NAME
from .MountManager import MountManager
from .utils import rtr

manager: Optional[MountManager] = None


def welcome(server: PluginServerInterface, player: str, info: Info):
    server.tell(player, rtr('help_msg.welcome'))


def on_load(server: PluginServerInterface, prev_module):
    global manager
    config: MountConfig = server.load_config_simple(
        file_name=CONFIG_NAME, in_data_folder=False, target_class=MountConfig)
    manager = MountManager(config=config)
    register_commands(server, manager)
    if config.welcome_player:
        server.register_event_listener(
            event='mcdr.player_joined', callback=welcome)
