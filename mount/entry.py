from typing import Optional

from mcdreforged.api.types import PluginServerInterface

from .MountManager import MountManager
from .constants import CONFIG_NAME
from .config import MountConfig

manager: Optional[MountManager] = None


def on_load(server: PluginServerInterface, prev_module):
    global manager
    config = server.load_config_simple(file_name=CONFIG_NAME, in_data_folder=False, target_class=MountConfig)
    manager = MountManager(config=config)


def on_unload(server: PluginServerInterface):
    global manager
    manager.abort_mount(source=server.get_plugin_command_source())
