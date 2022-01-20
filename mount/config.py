from typing import List

from mcdreforged.api.utils import Serializable
from .utils import psi
from .constants import CONFIG_NAME


class MountConfig(Serializable):
    welcome_player: bool = True
    short_prefix = True  # let !!m to be a short command
    servers_path: str = "../servers"
    overwrite_path: str = "../servers/server.properties.overwrite"

    # available mc servers for this MCDR instance, should be same with the dirname of that server
    available_servers: List[str] = ["servers/Parkour", "servers/PVP", "servers/Bingo"]

    current_server: str = "servers/Parkour"
    mount_name: str = "MountDemo"

    def save(self):
        psi.save_config_simple(config=self, file_name=CONFIG_NAME, in_data_folder=False)


class MountableMCServerConfig(Serializable):
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
