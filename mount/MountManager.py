import functools
import os.path
import shutil
import time
from enum import Enum
from threading import Lock
from typing import Callable, Optional

import yaml
from jproperties import Properties
from mcdreforged.api.decorator import new_thread
from mcdreforged.api.rtext import *
from mcdreforged.api.types import CommandSource

from .config import MountConfig, SlotConfig
from .constants import *
from .MountSlot import MountSlot
from .utils import psi, rtr


class Operation(Enum):
    REQUEST_RESET = 'request reset'
    REQUEST_MOUNT = 'request mount'
    RESET = 'reset'
    MOUNT = 'mount'
    IDLE = 'idle'


_operation_lock = Lock()
current_op = Operation.IDLE


def single_op(op_type: Operation):
    """
    Used to avoid operation conflict
    """
    def wrapper(func: Callable):
        @functools.wraps(func)
        def wrap(manager, src: CommandSource, *args, **kwargs):
            # allowed operation flow:
            # IDLE -> REQUEST_RESET -> RESET / IDLE
            # IDLE -> REQUEST_MOUNT -> MOUNT / IDLE
            with _operation_lock:
                global current_op
                allow = False
                if current_op is Operation.IDLE:
                    allow = True
                elif current_op is Operation.REQUEST_RESET and op_type is Operation.RESET:
                    allow = True
                elif current_op is Operation.REQUEST_MOUNT and op_type is Operation.MOUNT:
                    allow = True
                elif current_op in [Operation.REQUEST_RESET, Operation.REQUEST_MOUNT] and op_type is Operation.IDLE:
                    allow = True
                psi.logger.debug(f"Executing operation {op_type}, current operation {current_op}, allow = {allow}")
                if allow:
                    func(manager, src, *args, **kwargs)
                else:
                    src.reply(rtr('error.operation_conflict', curr=current_op.value))

        return wrap

    return wrapper


def need_restart(reason: RTextBase):
    """
    Stop server, execute the function, and then restart server and reload plugin
    """
    def wrapper(func: Callable):
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            global current_op
            for t in range(10):
                psi.broadcast(rtr('info.countdown', sec=10 - t, reason=reason))
                time.sleep(1)
            psi.stop()
            psi.wait_for_start()
            func(*args, **kwargs)
            psi.start()
            current_op = Operation.IDLE
            psi.refresh_changed_plugins()
        return wrap

    return wrapper


class MountManager:
    def __init__(self, config: MountConfig):
        """
        constructor
        :param config: the MountConfig for current mcdr server
        """
        self.configurable_things = None
        self.__abort_mount = None
        self._config = config
        self.current_slot: Optional[MountSlot] = MountSlot(self._config.current_server)
        try:
            self.current_slot.lock(self._config.mount_name)
        except ResourceWarning:
            psi.logger.error("Current server is already mounted, stopping mcdr...")
            psi.set_exit_after_stop_flag()
            psi.stop()
            return
        self.next_slot: Optional[MountSlot] = None

    def reload(self, src: CommandSource):
        self.detect_servers(src)
        psi.reload_plugin(psi.get_self_metadata().id)

    @property
    def servers_as_list(self):
        """
        get the list of available servers
        :return: the list of available servers
        """
        return self._config.available_servers

    def detect_servers(self, src: CommandSource):
        """
        auto-detect servers in target folder
        you can add a file named '.mount-ignore' to ignore that folder
        """
        def is_ignored(path: str) -> bool:
            """
            check if the given path should be ignored
            """
            return os.path.isfile(os.path.join(path, IGNORE_PATTEN))

        self._config = psi.load_config_simple(
            file_name=CONFIG_NAME, target_class=MountConfig, in_data_folder=False)
        script_map = {
            'posix': './start.sh',
            'nt': 'start.bat'
        }

        default_script = script_map[os.name] if os.name in script_map else './start.sh'
        default_handler = 'vanilla_handler'
        dirs = []
        for detect_path in self._config.servers_path:
            raw_paths = os.listdir(detect_path)
            real_paths = map(lambda p: os.path.join(detect_path, p), raw_paths)
            valid_paths = filter(lambda p: os.path.isdir(p), real_paths)
            dirs.extend(valid_paths)
        index = 0
        while index < len(self._config.available_servers):
            server_path = self._config.available_servers[index]
            if is_ignored(server_path):
                self._config.available_servers.pop(index)
            else:
                index += 1

        def is_valid_folder(path: str):
            return not os.path.isfile(os.path.join(path, IGNORE_PATTEN)) \
                   and path not in self._config.available_servers

        def init_conf(path: str):
            file_list = filter(lambda _: os.path.isfile(os.path.join(path, _)), os.listdir(path))
            conf = SlotConfig(checked=False, start_command=default_script, handler=default_handler)
            for file in file_list:
                if file[:5] == 'paper' and file[-4:] == '.jar':
                    conf.handler = 'bukkit_handler'
                    break
            psi.save_config_simple(
                config=conf,
                file_name=os.path.join(path, MOUNTABLE_CONFIG),
                in_data_folder=False)
            src.reply(rtr('detect.init_conf', path=path))

        dirs = list(filter(is_valid_folder, dirs))
        for server_dir in dirs:
            self._config.available_servers.append(server_dir)
            src.reply(rtr('detect.detected', path=server_dir))
            if not os.path.isfile(os.path.join(server_dir, MOUNTABLE_CONFIG)):
                init_conf(server_dir)
        if len(dirs) > 0:
            src.reply(rtr('detect.summary', num=len(dirs)))
        else:
            src.reply(rtr('detect.summary_empty'))
        self._config.save()

    @new_thread("mount-patch_properties")
    def patch_properties(self, slot: MountSlot):
        if self._config.overwrite_path in ['', '.', None]:
            return
        psi.logger.info("Patching properties file...")
        slot.load_properties()
        patches = Properties()
        try:
            with open(self._config.overwrite_path, mode="rb") as f:
                patches.load(f, 'utf-8')
        except FileNotFoundError:
            psi.logger.error('File Not Found, ignore overwriting...')
            return
        for k, v in patches.items():
            slot.properties[k] = v
        slot.save_properties()

    @new_thread("mount-patch_mcdr_config")
    def patch_mcdr_config(self, slot: MountSlot):
        with open("config.yml", "r", encoding="utf-8") as f:
            mcdr_config = yaml.safe_load(f)

        mcdr_config['working_directory'] = slot.path
        mcdr_config['start_command'] = slot.start_command
        mcdr_config['handler'] = slot.handler
        if self.current_slot.plg_dir not in ['', None, '.']:
            try:
                mcdr_config['plugin_directories'].remove(self.current_slot.plg_dir)
            except ValueError:
                pass
        if slot.plg_dir not in ['', None, '.']:
            mcdr_config['plugin_directories'].append(slot.plg_dir)

        with open('config.yml', 'w', encoding='utf-8') as f:
            yaml.dump(mcdr_config, f, default_flow_style=False)

    def request_operation(self, mode: str, source: CommandSource, path: Optional[str] = None, with_confirm=False):
        pass

    @single_op(Operation.REQUEST_MOUNT)
    def request_mount(self, source: CommandSource, path: str, with_confirm: bool = False):
        global current_op
        psi.logger.debug("Received mount request, evaluating...")

        if path == self.current_slot.path:
            source.reply(rtr('error.is_current_mount'))
            return

        if path not in self._config.available_servers:
            source.reply(rtr('error.unknown_mount_path'))
            return

        if not os.path.isdir(path):
            source.reply(rtr('error.invalid_mount_path'))
            return

        mountable_conf_path = os.path.join(path, MOUNTABLE_CONFIG)
        if not os.path.isfile(mountable_conf_path):
            psi.save_config_simple(config=SlotConfig(),
                                   file_name=mountable_conf_path,
                                   in_data_folder=False)
            source.reply(rtr('error.init_mountable_config'))
            return

        next_slot = MountSlot(path)
        if not next_slot.checked:
            source.reply(rtr('error.unchecked_path'))
            return

        try:
            next_slot.lock(self._config.mount_name)
            self.next_slot = next_slot
        except ResourceWarning:
            source.reply(rtr("error.occupied"))
            self.next_slot.release(self._config.mount_name)
            self.next_slot = None
            return

        current_op = Operation.REQUEST_MOUNT
        text = RTextList(
            RText(rtr("info.mount_request", server_path=self.next_slot.path), color=RColor.yellow),
            RText(rtr('info.confirm'), color=RColor.green)
                .c(RAction.suggest_command, f'{COMMAND_PREFIX} --confirm'),
            ' ',
            RText(rtr('info.abort'), color=RColor.red).c(RAction.suggest_command, f'{COMMAND_PREFIX} --abort')
        )
        source.reply(text)

    @single_op(Operation.REQUEST_RESET)
    def request_reset(self, source: CommandSource):
        global current_op
        # check for operation here
        if self.current_slot.reset_path in ['', None, '.'] \
                or not os.path.isdir(
                os.path.join(self.current_slot.path, self.current_slot.reset_path)):
            source.reply(rtr('error.reset.invalid_path'))
            return
        if self.current_slot.reset_type not in ['full', 'region']:
            source.reply(rtr('error.reset.invalid_type'))
            return
        current_op = Operation.REQUEST_RESET
        text = RTextList(
            RText(rtr("info.reset_request", reset_path=self.current_slot.reset_path), color=RColor.yellow),
            RText(rtr('info.confirm'), color=RColor.green)
                .c(RAction.suggest_command, f'{COMMAND_PREFIX} --confirm'),
            ' ',
            RText(rtr('info.abort'), color=RColor.red).c(RAction.suggest_command, f'{COMMAND_PREFIX} --abort')
        )
        source.reply(text)

    def confirm_operation(self, source: CommandSource):
        if current_op is Operation.REQUEST_RESET:
            self._do_reset(source, self.current_slot)
        elif current_op is Operation.REQUEST_MOUNT:
            if not isinstance(self.next_slot, MountSlot):
                source.reply(rtr('error.nothing_to_confirm'))
            else:
                self._do_mount(source, self.next_slot)

    @new_thread('mount-resetting')
    @single_op(Operation.RESET)
    @need_restart(reason=rtr('info.countdown_reason.reset'))
    def _do_reset(self, source: CommandSource, slot: MountSlot):
        global current_op
        current_op = Operation.RESET
        reserve_dirs = ['playerdata', 'advancements', 'stats']
        worlds = ['world', 'world_nether', 'world_the_end']
        reset_worlds = filter(lambda x: os.path.isdir(x),
                              map(lambda x: os.path.join(slot.path, slot.reset_path, x), worlds))
        curr_worlds = filter(lambda x: os.path.isdir(x),
                             map(lambda x: os.path.join(slot.path, x), worlds))

        # reset main world (maybe the only world)
        curr_main_world = os.path.join(slot.path, 'world')
        reset_main_world = os.path.join(slot.path, slot.reset_path, 'world')
        if curr_main_world not in curr_worlds:
            pass
        elif slot.reset_type == 'region':
            dirs = os.listdir(curr_main_world)
            for i in map(lambda x: os.path.join(curr_main_world, x),
                         filter(lambda x: x not in reserve_dirs, dirs)):
                psi.logger.info(f'Deleting world/{os.path.basename(i)}...')
                if os.path.isdir(i):
                    shutil.rmtree(i)
                else:
                    os.remove(i)
        elif slot.reset_type == 'full':
            psi.logger.info('Deleting the whole world/')
            shutil.rmtree(curr_main_world)

        if reset_main_world not in reset_worlds:
            psi.logger.info('No need to reset world/')
        elif slot.reset_type == 'region':
            dirs = os.listdir(reset_main_world)
            for i in map(lambda x: os.path.join(reset_main_world, x),
                         filter(lambda x: x not in reserve_dirs, dirs)):
                psi.logger.info(f'Resetting world/{os.path.basename(i)}')
                if os.path.isdir(i):
                    shutil.copytree(i, os.path.join(curr_main_world, os.path.basename(i)))
                else:
                    shutil.copy(i, os.path.join(curr_main_world, os.path.basename(i)))
        elif slot.reset_type == 'full':
            psi.logger.info('Resetting the whole world/')
            shutil.copytree(reset_main_world, curr_main_world)

        for i in worlds[1:]:
            dir1 = os.path.join(slot.path, i)
            dir2 = os.path.join(slot.path, slot.reset_path, i)
            if dir1 in curr_worlds:
                psi.logger.info(f'Deleting {i}')
                shutil.rmtree(dir1)
            if dir2 in reset_worlds:
                psi.logger.info(f'Resetting {i}')
                shutil.copytree(dir2, dir1)

    @new_thread("mount-mounting")
    @single_op(Operation.MOUNT)
    @need_restart(reason=rtr('info.countdown_reason.mount'))
    def _do_mount(self, source: CommandSource, slot: MountSlot):
        global current_op
        # do the mount
        current_op = Operation.MOUNT
        self.patch_properties(slot)
        self.patch_mcdr_config(slot)
        self.current_slot.release(self._config.mount_name)
        self.current_slot, self.next_slot = slot, None
        self._config.current_server = slot.path
        self._config.save()
        psi.execute_command("!!MCDR reload config")

    @single_op(Operation.IDLE)
    def abort_operation(self, source: CommandSource):
        global current_op
        current_op = Operation.IDLE
        if not isinstance(self.next_slot, MountSlot):
            source.reply(rtr("error.nothing_to_abort"))
            return
        if current_op is Operation.REQUEST_MOUNT:
            self.next_slot.release(self._config.mount_name)
        self.next_slot = None

    @new_thread('mount-list')
    def list_servers(self, src: CommandSource):
        src.reply(RText(rtr('list.title')))
        for server in self._config.available_servers:
            slot = MountSlot(path=server)
            src.reply(
                slot
                    .get_config()
                    .as_list_entry(slot.name, slot.path,
                        self._config.mount_name, self._config.current_server
                ))

    def get_config(self, config_key, src: Optional[CommandSource] = None):
        if src is not None:
            src.reply(self._config.__getattribute__(config_key))
        else:
            return self._config.__getattribute__(config_key)

    def set_config(self, src: CommandSource, config_key, config_value):
        assert hasattr(self._config, config_key)
        self._config.__setattr__(name=config_key, value=config_value)
        self._config.save()
        src.reply(rtr("info.setup_config", config_key, config_value))

    @staticmethod
    def list_path_config(src: CommandSource, path: str):
        slot_instance = MountSlot(path)
        src.reply(slot_instance.get_config().display(path))
        del slot_instance

    def edit_path_config(self, src, path: CommandSource, key: str, value):
        slot_instance = MountSlot(path)
        src.reply(slot_instance.edit_config(key, value))
        self.current_slot.load_config()
        del slot_instance
