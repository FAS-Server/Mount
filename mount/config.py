import time
from typing import List

from mcdreforged.api.rtext import *
from mcdreforged.api.utils import Serializable

from .constants import COMMAND_PREFIX, CONFIG_NAME
from .utils import psi, rtr


class MountConfig(Serializable):
    welcome_player: bool = True
    short_prefix = True  # let !!m to be a short command
    servers_path: List[str] = [ "../servers" ]
    overwrite_path: str = "../servers/server.properties.overwrite"

    # available mc servers for this MCDR instance, should be same with the dirname of that server
    available_servers: List[str] = [
        "servers/Parkour", "servers/PVP", "servers/Bingo"]

    current_server: str = "servers/Parkour"
    mount_name: str = "MountDemo"
    list_size: int = 15

    def save(self):
        psi.save_config_simple(
            config=self, file_name=CONFIG_NAME, in_data_folder=False)
    
    @staticmethod
    def load() -> 'MountConfig':
        return psi.load_config_simple(file_name=CONFIG_NAME, target_class=MountConfig, in_data_folder=False)


class SlotStats(Serializable):
    last_mount_ns: int = time.time_ns
    total_use_time: int = 0
    total_player_time: int = 0
    total_players: int = 0

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
        conf_list = self.get_annotations_fields()

        def get_config_text(config_key: str):
            config_value = self.__getattribute__(config_key)
            suggested_value = config_value
            if config_value in ['', None, '.']:
                config_value = rtr('config.empty')
            elif isinstance(config_value, bool):
                suggested_value = not config_value
                config_value = rtr(f'config.bool.{config_value}')
            return RText(f'{rtr(f"config.slot.{config_key}")}: {config_value}\n') \
                .h(rtr(f'config.hover', key=config_key)) \
                .c(RAction.suggest_command,
                   f'{COMMAND_PREFIX} -config {server_path} set {config_key} {suggested_value}')

        payload = RTextList()
        for key in conf_list:
            payload.append(get_config_text(key))
        return payload


    def as_list_entry(self, name: str, server_path: str, mount_name: str, current_mount: str):
        """
        - path [↻] <desc_short>
        """

        def get_button() -> RTextBase:
            error_button = RText("[?]", color=RColor.red).h(
                rtr("list.error_btn.hover"))
            mount_button = RText("[▷]")
            reset_button = RText("[↻]", color=RColor.yellow).c(RAction.suggest_command,
                                                               COMMAND_PREFIX + " --reset")
            if server_path == current_mount and mount_name == self.occupied_by:
                if self.reset_path in ["", None, '.']:
                    reset_button.set_color(RColor.gray).h(
                        rtr("list.reset_btn.unusable"))
                else:
                    reset_button.set_color(RColor.green).h(
                        rtr("list.reset_btn.reset"))
                return reset_button
            elif not self.checked:
                return mount_button.set_color(RColor.gray).h(rtr('list.mount_btn.uncheck'))
            elif self.occupied_by in [None, ""]:
                return mount_button.h(rtr("list.mount_btn.normal", server_name=server_path)) \
                    .set_color(RColor.green).c(RAction.suggest_command, COMMAND_PREFIX + " " + server_path)
            elif self.occupied_by != mount_name and server_path != current_mount:
                return mount_button.set_color(RColor.gray).h(
                    rtr("list.mount_btn.occupied", occupied_by=self.occupied_by))
            else:
                return error_button

        def get_path():
            path_text = RText(name).h(rtr("list.hover_on_name")) \
                .c(RAction.suggest_command, f"{COMMAND_PREFIX} --config {server_path}")
            if not self.checked:
                path_text.set_color(RColor.gray).set_styles(
                    RStyle.strikethrough)
            elif server_path == current_mount and mount_name == self.occupied_by:
                path_text.set_color(
                    RColor.light_purple).set_styles(RStyle.bold)
            elif self.occupied_by in ["", None]:
                path_text.set_color(RColor.green)
            else:
                path_text.set_color(RColor.red)
            return path_text

        return RTextList(
            get_button(),
            ' ',
            get_path(),
            ' ',
            RText(self.desc)
        )
