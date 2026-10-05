"""Offline, verified filesystem snapshots. No server lifecycle operations."""
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path


def reject_links(path):
    path = Path(path).absolute()
    for parent in [path, *path.parents]:
        if parent.exists() and (parent.is_symlink() or
                getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('unsafe_link')
    if path.is_dir():
        for root, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                p = Path(root, name)
                if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise ValueError('unsafe_link')


def overlaps(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    return a == b or a in b.parents or b in a.parents


def preflight(slot_path, reset_path, root, worlds, all_slots=()):
    slot, dest = Path(slot_path).resolve(), Path(root).resolve()
    reject_links(root)
    protected = [slot, *(Path(p).resolve() for p in all_slots)]
    if reset_path:
        protected.append((slot / reset_path).resolve())
    if any(overlaps(dest, p) for p in protected):
        raise ValueError('invalid_backup_path')
    sources, missing = [], []
    for name in worlds:
        p = slot / name
        if not name or Path(name).is_absolute() or '..' in Path(name).parts or p.resolve() == slot:
            raise ValueError('invalid_world_path')
        reject_links(p)
        if p.is_dir():
            sources.append((name, p))
        else:
            missing.append(name)
    if not sources:
        raise ValueError('missing_worlds')
    if any(overlaps(a[1], b[1]) for i, a in enumerate(sources) for b in sources[i+1:]):
        raise ValueError('overlapping_worlds')
    if reset_path and any(overlaps(p, slot / reset_path) for _, p in sources):
        raise ValueError('invalid_reset_path')
    ancestor = dest
    while not ancestor.exists():
        ancestor = ancestor.parent
    required = sum(p.stat().st_size for _, src in sources for p in src.rglob('*') if p.is_file())
    if shutil.disk_usage(ancestor).free < required * 1.1:
        raise ValueError('insufficient_space')
    return dest, sources, missing


def inventory(root):
    reject_links(root)
    result = {}
    for p in sorted(Path(root).rglob('*')):
        relative = p.relative_to(root).as_posix()
        if p.is_dir():
            result[relative + '/'] = None
        elif p.is_file():
            digest = hashlib.sha256()
            with p.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            result[relative] = [p.stat().st_size, digest.hexdigest()]
        else:
            raise ValueError('unsafe_file')
    return result


def run_backup(slot_path, reset_path, root, worlds, all_slots=()):
    dest, sources, missing = preflight(slot_path, reset_path, root, worlds, all_slots)
    dest.mkdir(parents=True, exist_ok=True)
    backup_id = uuid.uuid4().hex
    temporary, final = dest / (backup_id + '.tmp'), dest / backup_id
    temporary.mkdir()
    try:
        manifests = {}
        for name, src in sources:
            before = inventory(src)
            shutil.copytree(src, temporary / name)
            if before != inventory(temporary / name) or before != inventory(src):
                raise ValueError('validation_failed')
            manifests[name] = before
        (temporary / 'manifest.json').write_text(json.dumps({
            'id': backup_id, 'worlds': manifests, 'skipped': missing,
            'algorithm': 'sha256'}, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.rename(final)
        return backup_id, [name for name, _ in sources], missing
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
