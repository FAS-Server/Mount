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
        self._config: Config = psi.load_config_simple(
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
        try:
            with open(os.path.join(self.server_path, 'server.properties'), 'rb') as f:
                self.properties.load(f, 'utf-8')
        except FileNotFoundError:
            psi.logger.error(f'No properties file in {self.server_path}!')

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
                                                                                           COMMAND_PREFIX + " -reset")
            if self.server_path == current_mount and mount_name == self.occupied_by:
                if self.reset_path in ["", None]:
                    reset_button.set_color(RColor.gray).h(rtr("list.reset_btn.unusable"))
                else:
                    reset_button.set_color(RColor.green).h(rtr("list.reset_btn.reset"))
                return reset_button
            elif not self._config.checked:
                return mount_button.set_color(RColor.gray).h(rtr('list.mount_btn.uncheck'))
            elif self.occupied_by in [None, ""]:
                return mount_button.h(rtr("list.mount_btn.normal", server_name=self.server_path)) \
                    .set_color(RColor.green).c(RAction.suggest_command, COMMAND_PREFIX + " " + self.server_path)
            elif self.occupied_by != mount_name and self.server_path != current_mount:
                return mount_button.set_color(RColor.gray).h(
                    rtr("list.mount_btn.occupied", occupied_by=self._config.occupied_by))
            else:
                return error_button

        def get_path():
            path_text = RText(self.name).h(rtr("list.hover_on_name"))\
                .c(RAction.suggest_command, f"{COMMAND_PREFIX} -config {self.server_path}")
            if not self._config.checked:
                path_text.set_color(RColor.gray).set_styles(RStyle.strikethrough)
            elif self.server_path == current_mount and mount_name == self.occupied_by:
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

    def show_config(self):
        conf_list = self._config.get_annotations_fields()

        def get_config_text(config_key: str):
            config_value = self._config.__getattribute__(config_key)
            suggested_value = config_value
            if config_value in ['', None]:
                config_value = rtr('config.empty')
            elif isinstance(config_value, bool):
                suggested_value = not config_value
                config_value = rtr(f'config.bool.{config_value}')
            return RText(f'{rtr(f"config.slot.{config_key}")}: {config_value}\n')\
                .h(rtr(f'config.hover', key=config_key))\
                .c(RAction.suggest_command,
                   f'{COMMAND_PREFIX} -config {self.server_path} set {config_key} {suggested_value}')

        payload = RTextList()
        for key in conf_list:
            payload.append(get_config_text(key))
        return payload

    def edit_config(self, key: str, value: str):
        if isinstance(self._config.__getattribute__(key), bool):
            value = value.lower()
            if value in ['true', 'ok', 't', 'o', 'yes', 'y']:
                value = True
            elif value in ['false', 'no', 'f', 'n']:
                value = False
            else:
                return rtr('config.invalid_bool', value=value)
        self._config.__setattr__(key, value)
        self.save_config()
        return rtr('config.set_value', key=rtr(f'config.slot.{key}'), value=self._config.__getattribute__(key))
