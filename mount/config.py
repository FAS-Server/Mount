from typing import List

from mcdreforged.api.utils import Serializable


class MountConfig(Serializable):

    servers_path: List[str] = ["../MountableServers"]

    # whether to walk through servers_path when reload, which will edit the available_servers below
    auto_detect: bool = False

    # whether to overwrite the mc server properties
    overwrite_enable: bool = True
    overwrite_path: str = "../MountableSlots/server.properties.overwrite"

    # available mc servers for this MCDR instance, should be same with the dirname of that server
    available_servers: List[str] = ["Parkour", "PVP", "Bingo"]

    current_server: str = "Parkour"
    start_command: str = "./start.cmd"
    mount_name: str = "MountDemo"


class MountableMCServerConfig(Serializable):
    # relative to servers_path
    path: str = "Demo"
    desc: str = "Demo server"

    # where this server is occupied by another mcdr instance
    occupied: str = ""
    # backup path for reset, empty for disable, should be relative to mc server path
    reset_path: str = "reset_slot"

    # mcdr plugin path for specific plugin, empty for disable, should be relative to mc server path
    spec_plugin_dir: str = "mcdr_plg"

