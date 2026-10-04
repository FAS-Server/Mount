import os
import time
from threading import Event, Lock, RLock, Thread, current_thread
from typing import Callable

from jproperties import Properties

from .config import SlotConfig as Config
from .constants import MOUNTABLE_CONFIG
from .utils import logger, psi, rtr, debug


class StatsChecker(Thread):
    def __init__(self, interval: int, cb: Callable[[], None]):
        super().__init__()
        self.daemon = True
        self.name = self.__class__.__name__
        self._report_time = time.time()
        self.stop_event = Event()
        self.interval = interval
        self._callback = cb

    def run(self):
        while not self.stop_event.wait(self.interval):
            self._callback()

    def stop(self):
        self.stop_event.set()

class MountSlot:
    def __init__(self, path: str):
        self.path = path
        self.__stats_lock = RLock()
        self.load_config()
        self.properties = Properties()
        self.slot_lock = Lock()
        self.__players = set()
        self.__players_lock = Lock()
        self.__stats_checker = None
        self.__anchor = None

    @property
    def name(self) -> str:
        return os.path.basename(os.path.normpath(self.path))

    @property
    def plg_dir(self):
        if self._config.plugin_dir in ['', '.', None]:
            return ''
        else:
            return os.path.join(self.path, self._config.plugin_dir)

    def load_config(self):
        debug(f'Loading slot config in {self.path}...')
        with self.__stats_lock:
            self._config = psi.load_config_simple(
                target_class=Config,
                file_name=os.path.join(self.path, MOUNTABLE_CONFIG),
                in_data_folder=False
            )

    def save_config(self):
        debug(f'Saving slot config in {self.path}...')
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
        debug(f'Loading properties for slot {self.path}...')
        try:
            with open(os.path.join(self.path, 'server.properties'), 'rb') as f:
                self.properties.load(f, 'utf-8')
        except FileNotFoundError:
            logger().error(f'No properties file for slot {self.path}!')

    def save_properties(self):
        debug(f'Saving properties for slot {self.path}...')
        with open(os.path.join(self.path, 'server.properties'), 'wb') as f:
            self.properties.store(f, encoding='utf-8')

    def lock(self, mount_name: str):
        debug(f'Locking {self.path}...')
        acquired = self.slot_lock.acquire(blocking=False)
        if acquired:
            try:
                self.load_config()
                if self._config.occupied_by in ["", None, mount_name]:
                    self._config.occupied_by = mount_name
                    self.save_config()
                    return
            except BaseException:
                self.slot_lock.release()
                raise
            self.slot_lock.release()
        raise ResourceWarning

    def release(self, mount_name: str):
        debug(f'Releasing slot {self.path}...')
        if not self.slot_lock.locked():
            return
        try:
            self.load_config()
            if self._config.occupied_by == mount_name:
                self._config.occupied_by = ""
                self.save_config()
        finally:
            self.slot_lock.release()

    def edit_config(self, key: str, value: str):
        debug(f'Editing slot config in {self.path}, [{key}]] set to [{value}]')
        if key in ['stats', 'occupied_by']:
            return rtr('config.cannot_edit', key=rtr(f'config.slot.{key}'))
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

    def on_player_join(self, player: str):
        with self.__stats_lock:
            self.update_stats()
            self.__players.add(player)

    def on_player_left(self, player: str):
        with self.__stats_lock:
            self.update_stats()
            self.__players.discard(player)

    def set_players(self, players):
        with self.__stats_lock:
            self.update_stats()
            self.__players = set(players)

    def on_mount(self):
        with self.__stats_lock:
            if self.__anchor is not None:
                return
            self.__anchor = time.monotonic_ns()
            self._config.stats.last_mount_ns = time.time_ns()
            self.__stats_checker = StatsChecker(60, self.update_stats)
            self.__stats_checker.start()

    def on_unmount(self):
        with self.__stats_lock:
            self.update_stats()
            self.__anchor = None
            self.__players.clear()
            checker = self.__stats_checker
            if checker:
                checker.stop()
        if checker and checker is not current_thread():
            checker.join()


    def update_stats(self):
        with self.__stats_lock:
            if self.__anchor is None:
                return
            current = time.monotonic_ns()
            t = max(0, current - self.__anchor)
            self.__anchor = current
            stats = self._config.stats
            stats.use_time_ns_v2 += t
            stats.player_time_ns_v2 += t * len(self.__players)
            # Statistics must not overwrite a freshly edited reset template,
            # permissions/configuration or another instance's occupation.
            self.load_config()
            self._config.stats = stats
            self.save_config()
