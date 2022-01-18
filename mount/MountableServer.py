import os
from threading import Lock

from jproperties import Properties
from .config import MountableMCServerConfig as Config
from .constants import MOUNTABLE_CONFIG, COMMAND_PREFIX
from mcdreforged.api.rtext import RTextList, RAction, RText, RColor, RTextBase, RStyle

from .utils import rtr, psi


class MountableServer:
    def __init__(self, path):
        self.server_path = path
        self._config = psi.load_config_simple(
            target_class=Config,
            file_name=os.path.join(path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )
        self.properties = Properties()
        self.load_properties()
        self.slot_lock = Lock()

    @property
    def name(self):
        return os.path.basename(os.path.normpath(self.server_path))

    def load_config(self):
        self._config = psi.load_config_simple(
            target_class=Config,
            file_name=os.path.join(self.server_path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )

    def save_config(self):
        psi.save_config_simple(
            config=self._config,
            file_name=os.path.join(self.server_path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )

    def __getattr__(self, item):
        if hasattr(self._config, item):
            return self._config.__getattribute__(item)
        raise AttributeError

    def load_properties(self):
        with open(os.path.join(self.server_path, 'server.properties'), 'rb') as f:
            self.properties.load(f, 'utf-8')

    def save_properties(self):
        with open(os.path.join(self.server_path, 'server.properties'), 'wb') as f:
            self.properties.store(f, encoding='utf-8')

    def lock(self, mount_name: str):
        acquired = self.slot_lock.acquire(blocking=False)
        if acquired:
            self.load_config()
            if self._config.occupied_by in ["", None, mount_name]:
                self._config.occupied_by = mount_name
                self.save_config()
                return
        raise ResourceWarning

    def release(self, mount_name: str):
        self.load_config()
        if self._config.occupied_by == mount_name:
            self._config.occupied_by = ""
            self.save_config()
        self.slot_lock.release()

    def as_list_entry(self, mount_name: str, current_mount: str):
        """
        - path [⇄] <desc_short>
        """

        def get_button() -> RTextBase:
            error_button = RText("[?]", color=RColor.red).h(rtr("button.error.hover"))
            mount_button = RText("[▷]")
            reset_button = RText("[⇄]", color=RColor.green).h(rtr("button.reset.hover")).c(RAction.suggest_command,
                                                                                           COMMAND_PREFIX + " --reset")
            if self.server_path == current_mount and mount_name == self.occupied_by:
                if self.reset_path in ["", None]:
                    reset_button.set_color(RColor.gray).h(rtr("list.reset_btn.unusable"))
                else:
                    reset_button.set_color(RColor.green).h()
                return reset_button
            elif self.occupied_by in [None, ""]:
                return mount_button.h(rtr("list.mount_btn.normal", server_name=self.server_path))\
                    .set_color(RColor.green).c(RAction.suggest_command, COMMAND_PREFIX + " " + self.server_path)
            elif self.occupied != mount_name and self.server_path != current_mount:
                return mount_button.set_color(RColor.gray).h(
                    rtr("list.mount_btn.occupied", occupied_by=self._config.occupied_by))
            else:
                return error_button

        def get_path():
            path_text = RText(self.name).h(rtr("list.hover_on_name")).c(RAction.suggest_command, "")  # TODO:显示详情信息
            if self.server_path == current_mount and mount_name == self.occupied_by:
                path_text.set_color(RColor.light_purple).set_styles(RStyle.bold)
            elif self.occupied_by in ["", None]:
                path_text.set_color(RColor.gray)
            else:
                path_text.set_color(RColor.red)
            return path_text

        return RTextList(
            get_path(),
            ' ',
            get_button(),
            ' ',
            RText(self.desc)
        )
