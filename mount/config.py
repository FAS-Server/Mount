from typing import List

from mcdreforged.api.rtext import *
from mcdreforged.api.utils import Serializable

from .constants import COMMAND_PREFIX, CONFIG_NAME
from .utils import debug, psi, rtr, setDebugNoCheck


class MountConfig(Serializable):
    welcome_player: bool = True
    short_prefix: bool = True  # let !!m to be a short command
    servers_path: List[str] = [ "../servers" ]
    overwrite_path: str = "../servers/server.properties.overwrite"

    # available mc servers for this MCDR instance, should be same with the dirname of that server
    available_servers: List[str] = [
        "../servers/Parkour", "../servers/PVP", "../servers/Bingo"]

    current_server: str = "../servers/Parkour"
    mount_name: str = "MountDemo"
    list_size: int = 15
    debug: bool = False
    pinned_servers: List[str] = []
    list_order: str = 'configured'

    def save(self):
        debug(f'Saving plugin config...')
        psi.save_config_simple(
            config=self, file_name=CONFIG_NAME, in_data_folder=False)
    
    @staticmethod
    def load() -> 'MountConfig':
        config = psi.load_config_simple(file_name=CONFIG_NAME, target_class=MountConfig, in_data_folder=False)
        setDebugNoCheck(config.debug)
        if not isinstance(config.servers_path, list) or not all(isinstance(path, str) for path in config.servers_path):
            raise ValueError('servers_path must be a list of paths')
        return config


class SlotStats(Serializable):
    schema_version: int = 2
    use_time_ns_v2: int = 0
    player_time_ns_v2: int = 0
    last_mount_ns: int = -1

    def display(self) -> RTextBase:
        # [TODO) display stats to users
        return RText('')

class SlotConfig(Serializable):
    checked: bool = False
    desc: str = "Demo server"
    start_command: str = "./start.sh"
    handler: str = "vanilla_handler"

    # where this server is occupied by another mcdr instance
    occupied_by: str = ""
    # backup path for reset, empty for disable, should be relative to mc server path
    reset_path: str = ""
    reset_type: str = "full"

    # mcdr plugin path for specific plugin, empty for disable, should be relative to mc server path
    plugin_dir: str = ""

    # slot stats, used for rank
    stats: SlotStats = SlotStats()

    def display(self, server_path: str):
        conf_list = self.get_field_annotations()

        def get_config_text(config_key: str):
            config_value = self.__getattribute__(config_key)
            config_value_str = config_value
            suggested_value = config_value
            if config_value in ['', None, '.']:
                config_value_str = rtr('config.empty')
            elif config_key == 'stats':
                return RText('')
            elif isinstance(config_value, bool):
                suggested_value = not config_value
                config_value_str = rtr(f'config.bool.{"positive" if config_value else "negative"}')
            return RText(f'{rtr(f"config.slot.{config_key}")}: {config_value_str}\n') \
                .h(rtr(f'config.hover', key=config_key)) \
                .c(RAction.suggest_command,
                   f'{COMMAND_PREFIX} --config {server_path} set {config_key} {suggested_value}')

        payload = RTextList()
        for key in conf_list:
            payload.append(get_config_text(key))
        return payload
