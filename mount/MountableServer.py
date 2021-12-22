import os
from threading import Lock

from jproperties import Properties
from .config import MountableMCServerConfig as Config
from .constants import MOUNTABLE_CONFIG
from mcdreforged.api.types import PluginServerInterface as PSI


class MountableServer:
    def __init__(self, path):
        self.server_path = path
        self._config = PSI.get_instance().load_config_simple(
            target_class=Config,
            file_name=os.path.join(path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )
        self.properties = Properties()
        self.load_properties()
        self.slot_lock = Lock()

    def load_config(self):
        self._config = PSI.get_instance().load_config_simple(
            target_class=Config,
            file_name=os.path.join(self.server_path, MOUNTABLE_CONFIG),
            in_data_folder=False
        )

    def save_config(self):
        PSI.get_instance().save_config_simple(
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
            if self._config.occupied in ["", None, mount_name]:
                self._config.occupied = mount_name
                self.save_config()
                return
        raise ResourceWarning

    def release(self, mount_name: str):
        self.load_config()
        if self._config.occupied == mount_name:
            self._config.occupied = ""
            self.save_config()
        self.slot_lock.release()
