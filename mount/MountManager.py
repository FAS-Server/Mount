import json
import os.path
from typing import Optional, Dict, Any

from .MountableServer import MountableServer
from .config import MountConfig, MountableMCServerConfig
from mcdreforged.api.types import PluginServerInterface, CommandSource
from mcdreforged.api.decorator import new_thread
from .constants import MOUNTABLE_CONFIG
import yaml
import functools


class MountManager:
    def __init__(self, config: MountConfig):
        self.__abort_mount = None
        self._config = config
        self._psi = PluginServerInterface.get_instance()
        self.debug_logger = functools.partial(self._psi.logger.debug, no_check=self._config.DEBUG)
        self.current_slot: Optional[MountableServer] = MountableServer(self._config.current_server)
        try:
            self.current_slot.lock(self._config.mount_name)
        except ResourceWarning:
            self._psi.logger.error("Cannot mount current server, stopping...")
            self._psi.stop_exit()
        self.future_slot: Optional[MountableServer] = None

    def rtr(self, translate_key, *args, **kwargs):
        self.debug_logger(f'Translating key {translate_key} with args {args} and kwargs{kwargs}')
        return self._psi.rtr(f'mount.{translate_key}', *args, **kwargs)

    def detect_servers(self):
        def is_valid_server(path: str):
            return os.path.isdir(path) and os.path.isfile(os.path.join(path, MOUNTABLE_CONFIG))

        dirs = filter(is_valid_server, os.listdir(self._config.servers_path))
        for server_dir in dirs:
            if server_dir not in self._config.available_servers:
                self._config.available_servers.append(server_dir)

    @new_thread(thread_name="mount-patch_properties")
    def patch_properties(self, slot: MountableServer):
        self._psi.logger.info("Patching properties file...")
        slot.load_properties()
        with open(self._config.overwrite_path, mode="r", encoding="utf8") as f:
            overwrite: Dict[str, Any] = json.load(f)

        for k, v in overwrite:
            slot.properties[k] = v

        slot.save_properties()

    @new_thread(thread_name="mount-patch_mcdr_config")
    def patch_mcdr_config(self, slot: MountableServer):
        with open("config.yml", "r", encoding="utf-8") as f:
            mcdr_config = yaml.safe_load(f)

        mcdr_config['working_directory'] = slot.server_path
        mcdr_config['start_command'] = slot.start_command
        mcdr_config['handler'] = slot.handler
        if self.current_slot.spec_plugin_dir not in ['', None]:
            try:
                mcdr_config['plugin_directories'].remove(self.current_slot.spec_plugin_dir)
            except ValueError:
                pass
        if slot.spec_plugin_dir not in ['', None]:
            mcdr_config['plugin_directories'].append(slot.spec_plugin_dir)

        with open('config.yml', 'w', encoding='utf-8') as f:
            yaml.dump(mcdr_config, f, default_flow_style=False)

    def request_mount(self, source: CommandSource, slot_name: str, with_confirm: bool = False):
        self._psi.logger.debug("Received mount request, evaluating...")
        mount_path = os.path.join(self._config.servers_path, slot_name)

        if mount_path == self.current_slot.server_path:
            source.reply(self.rtr('error.is_current_mount'))
            return

        if isinstance(self.future_slot, MountableServer):  # check if there is a previous mount request
            source.reply(self.rtr('error.mount_spam'))
            return

        if not self._config.auto_detect and slot_name not in self._config.available_servers:
            source.reply(self.rtr('error.unknown_mount_path'))
            return

        if not os.path.isdir(mount_path):
            source.reply(self.rtr('error.invalid_mount_path'))
            return

        mountable_conf_path = os.path.join(mount_path, MOUNTABLE_CONFIG)
        if not os.path.isfile(mountable_conf_path):
            self._psi.save_config_simple(config=MountableMCServerConfig(),
                                         file_name=mountable_conf_path, in_data_folder=False)
            source.reply(self.rtr('error.init_mountable_config'))
            return

        future_slot = MountableServer(mount_path)
        try:
            future_slot.lock(self._config.mount_name)
            self.future_slot = future_slot
        except ResourceWarning:
            source.reply(self.rtr("error.occupied"))
            self.future_slot.release(self._config.mount_name)
            self.future_slot = None
            return

        if with_confirm:
            self._do_mount(self.future_slot)
        else:
            source.reply(self.rtr("info.mount_confirm"))
            # TODO: countdown for timeout (optional)

        return

    def confirm_mount(self, source: CommandSource):
        if not isinstance(self.future_slot, MountableServer):
            source.reply(self.rtr('error.nothing_to_confirm'))
            return

        self._do_mount(self.future_slot)

    @new_thread(thread_name="mount-mounting")
    def _do_mount(self, slot: MountableServer):
        # Stop the server for mount
        for t in range(10):
            self._psi.broadcast(self.rtr('info.countdown'))
        self._psi.stop()
        self._psi.wait_for_start()

        # do the mount
        self.patch_properties(slot)
        self.patch_mcdr_config(slot)
        self.current_slot.release(self._config.mount_name)
        self.current_slot, self.future_slot = slot, None
        self._psi.execute_command("!!MCDR reload config")
        self._psi.execute_command("!!MCDR reload all")
        self._psi.start()

    def abort_mount(self, source: CommandSource):
        if not isinstance(self.future_slot, MountableServer):
            source.reply(self.rtr("error.nothing_to_abort"))
            return

        self.future_slot = None
        self._psi.broadcast(self.rtr("info.mount_abort"))
