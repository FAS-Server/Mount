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

    switch_ratio: float = 0.6
    reset_ratio: float = 1.0
    vote_timeout: int = 60
    vote_cooldown: int = 60
    force_timeout: int = 60
    backup_permission: int = 3
    cancel_permission: int = 3
    force_players: List[str] = []
    force_console: bool = False
    backup_root: str = '../mount-backups'
    backup_worlds: List[str] = ['world', 'world_nether', 'world_the_end']
    stop_timeout: int = 60
    start_timeout: int = 120

    def validate(self):
        for key in ('switch_ratio', 'reset_ratio'):
            value = getattr(self, key)
            if isinstance(value, bool) or not 0 < value <= 1:
                raise ValueError(key)
        for key in ('vote_timeout', 'force_timeout', 'stop_timeout', 'start_timeout'):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(key)
        if type(self.vote_cooldown) is not int or self.vote_cooldown < 0 or self.list_order not in ('configured', 'activity'):
            raise ValueError('invalid vote cooldown or list order')
        for key in ('backup_permission', 'cancel_permission'):
            if type(getattr(self, key)) is not int or not 0 <= getattr(self, key) <= 4:
                raise ValueError(key)
        if type(self.list_size) is not int or self.list_size <= 0:
            self.list_size = 15

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
        config.validate()
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
