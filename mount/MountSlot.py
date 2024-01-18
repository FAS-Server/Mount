import os
import time
from asyncio import Event
from threading import Lock, Thread
from typing import Callable

from jproperties import Properties

from .config import SlotConfig as Config
from .constants import MOUNTABLE_CONFIG
from .utils import logger, psi, rtr, debug


class StatsChecker(Thread):
    def __init__(self, interval: int, cb: Callable[[], None]):
        super().__init__()
        self.setDaemon(True)
        self.setName(self.__class__.__name__)
        self._report_time = time.time()
        self.stop_event = Event()
        self.interval = interval
        self._callback = cb

    def run(self):
        while True: # loop until stop
            while True: # # loop for report
                if self.stop_event.wait(1):
                    return
                if time.time() - self._report_time > self.interval:
                    break
            self._report_time = time.time()
            self._callback()

    def stop(self):
        self.stop_event.set()

class MountSlot:
    def __init__(self, path: str):
        self.path = path
        self.load_config()
        self.properties = Properties()
        self.slot_lock = Lock()
        self.__players = []
        self.__players_lock = Lock()
        self.__stats_lock = Lock()
        self.__stats_checker = StatsChecker(60, self.update_stats)

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
            self.load_config()
            if self._config.occupied_by in ["", None, mount_name]:
                self._config.occupied_by = mount_name
                self.save_config()
                return
        raise ResourceWarning

    def release(self, mount_name: str):
        debug(f'Releasing slot {self.path}...')
        self.load_config()
        if self._config.occupied_by == mount_name:
            self._config.occupied_by = ""
            self.save_config()
        self.slot_lock.release()

    def edit_config(self, key: str, value: str):
        debug(f'Editing slot config in {self.path}, [{key}]] set to [{value}]')
        if key in [ 'stats' ]:
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

    def on_mount(self):
        debug(f'slot {self.path} is mounted, saving stats...')
        if not self.__stats_checker.is_alive:
            with self.__stats_lock:
                current = time.time_ns
                self._config.stats.last_mount_ns = current
                self.save_config()
            debug(f'starting stats checker for slot {self.path}...')
            self.__stats_checker.start()

    def on_unmount(self):
        debug(f'slot {self.path} is unmounted, saving stats...')
        if self.__stats_checker.is_alive:
            self.update_stats()
            self.__stats_checker.stop()


    def update_stats(self):
        debug(f'Updating stats in slot {self.path}...')
        if not self.__stats_checker.is_alive:
            return
        with self.__stats_lock:
            current = time.time_ns()
            prev = self._config.stats.last_mount_ns
            p = len(self.__players)
            t = current - prev
            stats = self._config.stats
            stats.last_mount_ns = current
            stats.total_use_time = stats.total_use_time + t
            stats.total_player_time = stats.total_player_time + t * p
            self._config.stats = stats
            debug(f'current stats: {stats}')
            self.save_config()
