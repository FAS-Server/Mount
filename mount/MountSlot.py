import os
from threading import Lock

from jproperties import Properties

from .config import SlotConfig as Config
from .constants import MOUNTABLE_CONFIG
from .utils import psi, rtr


class MountSlot:
    def __init__(self, path):
        self.path = path
        self.load_config()
        self.properties = Properties()
        self.load_properties()
        self.slot_lock = Lock()

    @property
    def name(self):
        return os.path.basename(os.path.normpath(self.path))

    @property
    def plg_dir(self):
        if self._config.plugin_dir in ['', '.', None]:
            return ''
        else:
            return os.path.join(self.path, self._config.plugin_dir)

    def load_config(self):
        self._config = psi.load_config_simple(
            target_class=Config,
            file_name=os.path.join(self.path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )

    def save_config(self):
        psi.save_config_simple(
            config=self._config,
            file_name=os.path.join(self.path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )

    def get_config(self) -> Config:
        return self._config

    def __getattr__(self, item):
        if hasattr(self._config, item):
            return self._config.__getattribute__(item)
        raise AttributeError

    def load_properties(self):
        try:
            with open(os.path.join(self.path, 'server.properties'), 'rb') as f:
                self.properties.load(f, 'utf-8')
        except FileNotFoundError:
            psi.logger.error(f'No properties file in {self.path}!')

    def save_properties(self):
        with open(os.path.join(self.path, 'server.properties'), 'wb') as f:
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
