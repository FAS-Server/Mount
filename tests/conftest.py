import logging
import sys
import types
from pathlib import Path

import pytest
from mcdreforged.api.types import PlayerCommandSource

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# PSI acquisition requires a running MCDR plugin context. Only this boundary
# is replaced; command nodes, RText and serialization use actual MCDR APIs.
utils = types.ModuleType('mount.utils')
utils.psi = None
utils.logger = lambda: logging.getLogger('test')
utils.debug = lambda *args: None
utils.setDebugNoCheck = lambda value: None
utils.rtr = lambda translation_key, *args, **kwargs: translation_key + (' ' + str(kwargs) if kwargs else '')
sys.modules['mount.utils'] = utils


class Source(PlayerCommandSource):
    def __init__(self, player='Alice', permission=0):
        self.name = player
        self.permission = permission
        self.replies = []

    @property
    def player(self):
        return self.name

    @property
    def is_player(self):
        return self.name is not None

    def has_permission(self, level):
        return self.permission >= level

    def reply(self, text):
        self.replies.append(text)


class Server:
    def __init__(self):
        self.running = self.started = True
        self.stops = self.starts = 0
        self.messages = []
        self.stop_works = self.start_works = True
        self.config = {'handler': 'vanilla_handler', 'plugin_directories': [],
                       'working_directory': '', 'start_command': ''}

    def load_config_simple(self, target_class, file_name, **kwargs):
        import json
        path = Path(file_name)
        if path.exists():
            return target_class.deserialize(json.loads(path.read_text(encoding='utf-8')))
        return target_class()

    def save_config_simple(self, config, file_name, **kwargs):
        import json
        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config.serialize()), encoding='utf-8')

    def is_server_running(self):
        return self.running

    def is_server_startup(self):
        return self.running and self.started

    def stop(self):
        self.stops += 1
        if self.stop_works:
            self.running = self.started = False

    def start(self):
        self.starts += 1
        self.running = True
        self.started = self.start_works

    def stop_exit(self):
        self.stop()

    def broadcast(self, text):
        self.messages.append(text)

    def tell(self, player, text):
        self.messages.append(text)

    def execute(self, command):
        pass

    def get_mcdr_config(self):
        return self.config.copy()

    def modify_mcdr_config(self, changes):
        self.config.update(changes)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    import mount.MountManager as mm
    import mount.MountSlot as ms
    import mount.config as cfg
    import mount.entry as entry

    from mount.constants import MOUNTABLE_CONFIG
    server = Server()
    monkeypatch.setattr(cfg, 'CONFIG_NAME', str(tmp_path/'instance.json'))
    for module in (mm, ms, cfg):
        monkeypatch.setattr(module, 'psi', server)
    config = cfg.MountConfig()
    config.current_server = str(tmp_path/'current')
    config.available_servers = [config.current_server, str(tmp_path/'target with spaces')]
    config.overwrite_path = ''
    for path in config.available_servers:
        Path(path, 'world').mkdir(parents=True)
        Path(path, 'world', 'level.dat').write_bytes(b'world-data')
        slot = cfg.SlotConfig()
        slot.checked = True
        slot.reset_path = 'template'
        Path(path, 'template', 'world').mkdir(parents=True)
        Path(path, 'template', 'world', 'level.dat').write_bytes(b'template')
        server.save_config_simple(slot, str(Path(path, MOUNTABLE_CONFIG)))
    manager = mm.MountManager(config)
    yield manager, server, Source
    manager.current_slot.on_unmount()
    manager.current_slot.release(manager._config.mount_name)
    mm.current_op = mm.Operation.IDLE
