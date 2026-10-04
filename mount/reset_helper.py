import shutil
from pathlib import Path

from .backup_helper import overlaps, reject_links


class ResetHelper:
    worlds = ['world', 'world_nether', 'world_the_end']
    reserved = ['playerdata', 'advancements', 'stats']

    @staticmethod
    def preflight(slot_path, reset_path, reset_type):
        slot = Path(slot_path).resolve()
        if not reset_path or reset_path == '.' or reset_type not in ('full', 'region'):
            raise ValueError('invalid_reset_path')
        template = slot / reset_path
        reject_links(template)
        present = [name for name in ResetHelper.worlds if (template/name).is_dir()]
        if not present:
            raise ValueError('invalid_reset_path')
        for name in ResetHelper.worlds:
            reject_links(slot/name)
            if overlaps(template, slot/name):
                raise ValueError('invalid_reset_path')
        return slot, template, present

    @staticmethod
    def reset(slot_path, reset_path, reset_type):
        slot, template, present = ResetHelper.preflight(slot_path, reset_path, reset_type)
        # Only worlds actually provided by the template are replaced.
        for name in present:
            src, dest = template/name, slot/name
            if name == 'world' and reset_type == 'region':
                dest.mkdir(exist_ok=True)
                for child in dest.iterdir():
                    if child.name not in ResetHelper.reserved:
                        ResetHelper.remove(child)
                for child in src.iterdir():
                    if child.name not in ResetHelper.reserved:
                        ResetHelper.copy(child, dest/child.name)
            else:
                if dest.exists():
                    ResetHelper.remove(dest)
                ResetHelper.copy(src, dest)

    @staticmethod
    def remove(path):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    @staticmethod
    def copy(src, dest):
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
