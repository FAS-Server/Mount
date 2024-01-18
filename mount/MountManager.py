import functools
import math
import os.path
import time
from enum import Enum
from threading import Lock
from typing import Callable, List, Optional

from jproperties import Properties
from mcdreforged.api.decorator import new_thread
from mcdreforged.api.rtext import *
from mcdreforged.api.types import CommandSource

from .config import MountConfig, SlotConfig
from .constants import *
from .detect_helper import DetectHelper
from .MountSlot import MountSlot
from .reset_helper import ResetHelper
from .utils import logger, psi, rtr, debug


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
                allow = current_op is Operation.IDLE \
                    or (current_op is Operation.REQUEST_RESET and op_type is Operation.RESET) \
                    or (current_op is Operation.REQUEST_MOUNT and op_type is Operation.MOUNT) \
                    or (current_op in [Operation.REQUEST_RESET, Operation.REQUEST_MOUNT] and op_type is Operation.IDLE)
                debug(f"Executing operation {op_type}, current operation {current_op}, allow = {allow}")
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
            debug(f"Need restart: {reason}")
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
        debug("Initializing MountManager...")
        self.configurable_things = None
        self._config = config
        self.current_slot: Optional[MountSlot] = MountSlot(self._config.current_server)
        try:
            self.current_slot.lock(self._config.mount_name)
        except ResourceWarning:
            logger().error("Current server is already mounted, stopping mcdr...")
            psi.set_exit_after_stop_flag()
            psi.stop()
            return
        self.next_slot: Optional[MountSlot] = None


    def reload(self, src: CommandSource):
        debug("received reload request, reloading...")
        self._config = MountConfig.load()
        
        new_slots, removal_slots = DetectHelper.detect_slots(self._config.servers_path, self._config.available_servers)
        
        self._config.available_servers.extend(new_slots)
        for slot in new_slots:
            if not os.path.isfile(os.path.join(slot, MOUNTABLE_CONFIG)):
                DetectHelper.init_conf(slot)
                src.reply(rtr('detect.init_conf', path=slot))

        for slot in removal_slots:
            debug(f"removing {slot} from available servers...")
            self._config.available_servers.remove(slot)

        if len(new_slots) > 0:
            src.reply(rtr('detect.summary', num=len(new_slots)))
        else:
            src.reply(rtr('detect.summary_empty'))
        self._config.save()
        debug("reload path done, try to reload self plugin...")
        psi.reload_plugin(psi.get_self_metadata().id)


    @property
    def servers_as_list(self):
        """
        get the list of available servers
        :return: the list of available servers
        """
        return self._config.available_servers

    @new_thread("mount-patch_properties")
    def patch_properties(self, slot: MountSlot):
        if self._config.overwrite_path in ['', '.', None]:
            return
        logger().info("Patching properties file...")
        slot.load_properties()
        patches = Properties()
        try:
            with open(self._config.overwrite_path, mode="rb") as f:
                patches.load(f, 'utf-8')
        except FileNotFoundError:
            logger().error('File Not Found, ignore overwriting...')
            return
        for k, v in patches.items():
            slot.properties[k] = v
        slot.save_properties()

    @new_thread("mount-patch_mcdr_config")
    def patch_mcdr_config(self, slot: MountSlot):
        # MCDR v2.7 provided api to modify config
        logger().info("Patching mcdr config...")
        current_plg_dirs = psi.get_mcdr_config()['plugin_directories']
        prev_added_plg_dir = self.current_slot.plg_dir
        if prev_added_plg_dir not in ['', None, '.']:
            try:
                current_plg_dirs.remove(prev_added_plg_dir)
            except ValueError:
                pass
        if slot.plg_dir not in ['', None, '.']:
            try:
                current_plg_dirs.append(slot.plg_dir)
            except ValueError:
                pass
        changes = {
            'working_directory': slot.path,
            'start_command': slot._config.start_command,
            'handler': slot._config.handler,
            'plugin_directories': current_plg_dirs
        }
        debug(f"mcdr config changes is: {changes}")
        psi.modify_mcdr_config(changes=changes)

    def request_operation(self, mode: str, source: CommandSource, path: Optional[str] = None, with_confirm=False):
        pass

    @single_op(Operation.REQUEST_MOUNT)
    def request_mount(self, source: CommandSource, path: str, with_confirm: bool = False):
        global current_op
        debug("Received mount request, evaluating...")

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

        debug("Mount request accepted, waiting for confirmation...")
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
        debug("Received reset request, evaluating...")
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
        debug("Reset request accepted, waiting for confirmation...")
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
        debug("Received confirm request, evaluating...")
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
        debug(f"Resetting current slot {slot.path}...")
        global current_op
        current_op = Operation.RESET
        ResetHelper.reset(slot.path, slot._config.reset_path, slot._config.reset_type)

    @new_thread("mount-mounting")
    @single_op(Operation.MOUNT)
    @need_restart(reason=rtr('info.countdown_reason.mount'))
    def _do_mount(self, source: CommandSource, slot: MountSlot):
        debug(f"Mounting slot {slot.path}...")
        global current_op
        # do the mount
        current_op = Operation.MOUNT
        self.patch_properties(slot)
        self.patch_mcdr_config(slot)
        self.current_slot.release(self._config.mount_name)
        self.current_slot, self.next_slot = slot, None
        self._config.current_server = slot.path
        self._config.save()

    @single_op(Operation.IDLE)
    def abort_operation(self, source: CommandSource):
        debug("Received abort request, evaluating...")
        global current_op
        current_op = Operation.IDLE
        if not isinstance(self.next_slot, MountSlot):
            source.reply(rtr("error.nothing_to_abort"))
            return
        if current_op is Operation.REQUEST_MOUNT:
            self.next_slot.release(self._config.mount_name)
        self.next_slot = None

    @new_thread('mount-list')
    def list_servers(self, src: CommandSource, page: int = 1):
        debug(f"Received list request for page {page}")
        list_size = self._config.list_size
        available_servers = self._config.available_servers
        max_page = math.ceil(len(available_servers) / list_size)
        if not 1 <= page <= max_page:
            page = 1
        
        left = (page - 1) * list_size
        right = min(len(available_servers), page * list_size)
        src.reply(RText(rtr('list.title')))
        for server in available_servers[left: right]:
            slot = MountSlot(path=server)
            src.reply(
                slot
                    .get_config()
                    .as_list_entry(slot.name, slot.path,
                        self._config.mount_name, self._config.current_server
                ))
            
        # <<<   curr/total   >>>
        link_color = {
            True: RColor.green,
            False: RColor.gray
        }

        left_link: RText
        if page <= 1:
            left_link = RText('<<<', color=link_color[False]).h(rtr('list.no_more_page'))
        else:
            left_link = RText('<<<', color=link_color[True]).h(rtr('list.prev_page')) \
                .c(RAction.suggest_command, COMMAND_PREFIX + ' --list ' + str(page - 1))

        right_link: RText
        if page >= max_page:
            right_link = RText('>>>', color=link_color[False]).h(rtr('list.no_more_page'))
        else:
            right_link = RText('>>>', color=link_color[True]).h(rtr('list.next_page')) \
                .c(RAction.suggest_command, COMMAND_PREFIX + ' --list ' + str(page + 1))

        footer = RTextList(
            left_link,
            f'   {page} / {max_page}   ',
            right_link
        )
        if left == right:
            src.reply(rtr('list.empty'))
        else:
            src.reply(footer)
        

    def get_config(self, config_key, src: Optional[CommandSource] = None):
        if src is not None:
            src.reply(self._config.__getattribute__(config_key))
        else:
            return self._config.__getattribute__(config_key)

    def set_config(self, src: CommandSource, config_key, config_value):
        debug(f"Setting config [{config_key}] to [{config_value}]")
        assert hasattr(self._config, config_key)
        self._config.__setattr__(name=config_key, value=config_value)
        self._config.save()
        src.reply(rtr("config.set_value", config_key, config_value))

    @staticmethod
    def list_path_config(src: CommandSource, path: str):
        slot_instance = MountSlot(path)
        src.reply(slot_instance.get_config().display(path))
        del slot_instance

    def edit_path_config(self, src, path: CommandSource, key: str, value):
        debug(f"Editing path({path}) config [{key}] to [{value}]")
        slot_instance = MountSlot(path)
        src.reply(slot_instance.edit_config(key, value))
        self.current_slot.load_config()
        del slot_instance
