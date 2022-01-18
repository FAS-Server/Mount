from typing import List, Dict

from mcdreforged.api.utils import Serializable
from .utils import psi
from .constants import CONFIG_NAME


class MountConfig(Serializable):
    servers_path: str = "../MountableServers"

    # whether to overwrite the mc server properties
    overwrite_enable: bool = True
    overwrite_path: str = "../MountableSlots/server.properties.overwrite"

    # available mc servers for this MCDR instance, should be same with the dirname of that server
    available_servers: List[str] = ["Parkour", "PVP", "Bingo"]

    current_server: str = "Parkour"
    mount_name: str = "MountDemo"
    command_permission: Dict[str, int] = {
        "mount_server": 2
    }
    DEBUG: bool = False

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
    reset_path: str = "reset_path"
    reset_type: str = "full"  # TODO: full|region

    # mcdr plugin path for specific plugin, empty for disable, should be relative to mc server path
    spec_plugin_dir: str = "mcdr_plg"

# TODO: 两种重置方法：全重置和地图重置
# TODO: 游戏内配置界面
