import os
from typing import Iterable, List, Tuple

from mcdreforged.api.types import PluginServerInterface

from .config import SlotConfig
from .constants import IGNORE_PATTEN, MOUNTABLE_CONFIG
from .utils import debug, psi

def is_ignored_slot(path: str) -> bool:
    """
    check if the given path should be ignored
    """
    return os.path.isfile(os.path.join(path, IGNORE_PATTEN))

class DetectHelper:
    @staticmethod
    def detect_slots(detect_paths: Iterable[str], prev_slots: Iterable[str]) -> Tuple[List[str], List[str]]:
        debug(f'Detecting slots from {detect_paths}, previous slots: {prev_slots}')
        all_avaiable_paths = []
        for path in detect_paths:
            raw_paths = os.listdir(path)
            real_paths = map(lambda p: os.path.join(path, p), raw_paths)
            valid_paths = filter(lambda p: os.path.isdir(p) and not is_ignored_slot(p), real_paths)
            all_avaiable_paths.extend(valid_paths)
        
        new_slot_paths = filter(lambda p: p not in prev_slots, all_avaiable_paths)
        removal_slot_paths = filter(lambda p: p not in all_avaiable_paths, prev_slots)
        debug(f'New slots: {new_slot_paths}, removal slots: {removal_slot_paths}')
        return (list(set(new_slot_paths)), list(set(removal_slot_paths)))


    @staticmethod
    def init_conf(path: str):
        debug(f'Initializing mountable config for {path}')
        script_map = {
            'posix': './start.sh',
            'nt': 'start.bat'
        }
        default_script = script_map[os.name] if os.name in script_map else './start.sh'
        default_handler = 'vanilla_handler'
        file_list = filter(lambda _: os.path.isfile(os.path.join(path, _)), os.listdir(path))
        conf = SlotConfig(checked=False, start_command=default_script, handler=default_handler)
        for file in file_list:
            if file[:5] == 'paper' and file[-4:] == '.jar':
                conf.handler = 'bukkit_handler'
                break
        debug(f'saving mountable config: {conf}')
        psi.save_config_simple(
            config=conf,
            file_name=os.path.join(path, MOUNTABLE_CONFIG),
            in_data_folder=False)
