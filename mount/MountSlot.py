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
        self.__players = []
        self.__players_lock = self.__stats_lock
        self.__stats_checker = None

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
        with self.__stats_lock:
            debug(f'Loading slot config in {self.path}...')
            self._config = psi.load_config_simple(
                target_class=Config,
                file_name=os.path.join(self.path, MOUNTABLE_CONFIG),
                in_data_folder=False
            )


    def save_config(self):
        with self.__stats_lock:
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
        with self.__stats_lock:
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
        with self.__stats_lock:
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
        with self.__stats_lock:
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
        debug(f'Player {player} joined slot {self.path}, saving stats...')
        with self.__players_lock:
            self.update_stats()
            self._config.stats.total_players = self._config.stats.total_players + 1
            self.__players.append(player)
            self.update_stats()

    def on_player_left(self, player: str):
        debug(f'Player {player} left slot {self.path}, saving stats...')
        try:
            with self.__players_lock:
                self.update_stats()
                self.__players.remove(player)
        except ValueError:
            pass

    def set_players(self, players):
        with self.__players_lock:
            self.update_stats()
            self.__players = list(players)

    def on_mount(self):
        with self.__stats_lock:
            if self.__stats_checker and self.__stats_checker.is_alive():
                return
            self._config.stats.last_mount_ns = time.time_ns()
            self.save_config()
            self.__stats_checker = StatsChecker(60, self.update_stats)
            self.__stats_checker.start()

    def on_unmount(self):
        with self.__stats_lock:
            checker = self.__stats_checker
            if checker:
                self.update_stats()
                checker.stop()
        if checker and checker is not current_thread():
            checker.join()
        with self.__stats_lock:
            if self.__stats_checker is checker:
                self.__stats_checker = None
                self.__players.clear()

    def update_stats(self):
        with self.__stats_lock:
            if not self.__stats_checker or not self.__stats_checker.is_alive():
                return
            current = time.time_ns()
            stats = self._config.stats
            t = current - stats.last_mount_ns
            stats.last_mount_ns = current
            stats.total_use_time += t
            stats.total_player_time += t * len(self.__players)
            # Preserve fresh reset/config/occupation fields during operation IO.
            self.load_config()
            self._config.stats = stats
            self.save_config()
