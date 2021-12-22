from typing import List, Dict

from mcdreforged.api.utils import Serializable


class MountConfig(Serializable):
    servers_path: str = "../MountableServers"

    # whether to walk through servers_path when reloaded, which will edit the available_servers below
    auto_detect: bool = False

    # whether to overwrite the mc server properties
    overwrite_enable: bool = True
    overwrite_path: str = "../MountableSlots/server.properties.overwrite"

    # available mc servers for this MCDR instance, should be same with the dirname of that server
    available_servers: List[str] = ["Parkour", "PVP", "Bingo"]

    current_server: str = "Parkour"
    mount_name: str = "MountDemo"
    command_permission: Dict[str, int] = {
        "mount_server"
    }
    DEBUG = False


class MountableMCServerConfig(Serializable):
    # relative to servers_path
    desc: str = "Demo server"
    start_command: str = "./start.sh"
    handler = "vanilla_handler"

    # where this server is occupied by another mcdr instance
    occupied: str = ""
    # backup path for reset, empty for disable, should be relative to mc server path
    reset_path: str = "reset_path"

    # mcdr plugin path for specific plugin, empty for disable, should be relative to mc server path
    spec_plugin_dir: str = "mcdr_plg"
