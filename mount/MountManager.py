import math
import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from threading import RLock, Thread, Timer

from jproperties import Properties
from mcdreforged.api.rtext import RAction, RText, RTextList
from mcdreforged.api.types import Info, PlayerCommandSource

from .backup_helper import preflight, run_backup
from .config import MountConfig
from .constants import COMMAND_PREFIX
from .detect_helper import DetectHelper
from .list_order import order_slots
from .MountSlot import MountSlot
from .players import PlayerRegistry
from .reset_helper import ResetHelper
from .utils import logger, psi, rtr
from .vote import VoteSession


@dataclass
class ForceRequest:
    request_id: str
    kind: str
    target: str
    owner: str
    vote_id: object
    expires: float
    config: dict
    slot_config: dict


class MountManager:
    def __init__(self, config):
        config.validate()
        self._config = config
        self.lock = RLock()
        self.players = PlayerRegistry()
        self.vote = self.force = self.timer = self.force_timer = None
        self.executing = self.worker = None
        self.closed = False
        self.reloading = False
        self.cooldowns = {}
        self.results = {}
        self.current_slot = MountSlot(config.current_server)
        try:
            self.current_slot.lock(config.mount_name)
        except ResourceWarning:
            self.closed = True
            psi.stop_exit()
            raise

    @property
    def servers_as_list(self):
        return self._config.available_servers

    def identity(self, src):
        return src.player if src.is_player else 'console'

    def can_backup(self, src):
        return src.has_permission(self._config.backup_permission)

    def can_force(self, src):
        return (isinstance(src, PlayerCommandSource) and src.player in self._config.force_players if src.is_player
                else src.is_console and self._config.force_console and src.has_permission(4))

    def message(self, src, key, **kwargs):
        src.reply(rtr('flow.' + key, **kwargs))

    def button(self, key, command):
        return RText(rtr('flow.' + key)).c(RAction.run_command, COMMAND_PREFIX + ' ' + command)

    def action_text(self, kind):
        return rtr('flow.action_' + kind)

    def target_token(self, path):
        return 'slot:' + hashlib.sha256(path.encode('utf-8')).hexdigest()

    def resolve_target(self, target):
        if target.startswith('slot:'):
            return next((path for path in self.servers_as_list if self.target_token(path) == target), '')
        return target

    def target_name(self, path):
        name = os.path.basename(os.path.normpath(path))
        matches = [p for p in self.servers_as_list if os.path.basename(os.path.normpath(p)) == name]
        return name + (' #'+str(matches.index(path)+1) if len(matches) > 1 and path in matches else '')

    def reset_scope(self, slot):
        _, template, present = ResetHelper.preflight(slot.path, slot.reset_path, slot.reset_type)
        return rtr('flow.reset_scope', mode=slot.reset_type, worlds=', '.join(present), template=template.name)

    def restore_players(self):
        if self.closed:
            return
        # Info.source documents console as 1 in MCDR 2.7; creating a barrier
        # uses the public monotonic Info.id, discarding already queued output.
        if self.players.begin(Info(1, '').id):
            psi.execute('list')

    def on_start(self):
        if not self.closed:
            self.current_slot.on_mount()
            self.restore_players()

    def on_stop(self):
        self.players.invalidate()
        self.current_slot.on_unmount()

    def on_info(self, info):
        if not self.closed and self.players.accept(info, psi.get_mcdr_config()['handler']):
            self.current_slot.set_players(self.players.snapshot())
        elif not self.closed and self.players.take_retry():
            self.restore_players()

    def player_event(self, player, joined):
        if self.closed:
            return
        self.players.event(player, joined)
        if joined:
            self.current_slot.on_player_join(player)
            with self.lock:
                pending = self.results.pop(player, None)
            if pending is not None:
                psi.tell(player, pending)
        else:
            self.current_slot.on_player_left(player)

    def validate_target(self, kind, target):
        if kind == 'switch':
            if (os.path.realpath(target) == os.path.realpath(self.current_slot.path)
                    or target not in self.servers_as_list or not os.path.isdir(target)):
                raise ValueError('invalid_target')
            slot = MountSlot(target)
            if not slot.checked or slot.occupied_by not in ('', None):
                raise ValueError('invalid_target')
            return slot
        slot = MountSlot(self.current_slot.path)
        if slot.occupied_by != self._config.mount_name or not slot.checked:
            raise ValueError('invalid_target')
        if kind == 'reset':
            ResetHelper.preflight(slot.path, slot.reset_path, slot.reset_type)
        elif kind == 'backup':
            preflight(slot.path, slot.reset_path,
                      self._config.backup_root, self._config.backup_worlds,
                      self.servers_as_list + self._config.servers_path)
        return slot

    def available(self):
        if self.closed or self.executing or self.reloading:
            raise ValueError('busy')

    def request_mount(self, source, path, with_confirm=False):
        self.request_vote(source, 'switch', self.resolve_target(path))

    def request_reset(self, source):
        self.request_vote(source, 'reset', self.current_slot.path)

    def request_vote(self, src, kind, target):
        try:
            target_slot = self.validate_target(kind, target)
            scope = self.reset_scope(target_slot) if kind == 'reset' else None
            with self.lock:
                self.available()
                if self.vote:
                    raise ValueError('busy')
                roster = self.players.snapshot()
                if roster is None:
                    raise ValueError('snapshot_unknown')
                if not roster:
                    raise ValueError('no_players')
                if not isinstance(src, PlayerCommandSource) or not src.is_player or src.player not in roster:
                    raise ValueError('not_in_roster')
                if time.monotonic() - self.cooldowns.get(kind, -float('inf')) < self._config.vote_cooldown:
                    raise ValueError('cooldown')
                self.vote = VoteSession(kind, target, src.player, roster,
                    getattr(self._config, kind + '_ratio'), self._config.vote_timeout)
                vote = self.vote
                vote.reset_scope = scope
                self.timer = Timer(vote.timeout, self.expire_vote, [vote.request_id])
                self.timer.daemon = True
                self.timer.start()
            self.show_status(src, vote.request_id)
            psi.broadcast(RTextList(rtr('flow.vote_started', actor=vote.owner,
                action=self.action_text(kind), target=self.target_name(target), id=vote.request_id,
                ratio=vote.ratio*100, required=vote.threshold, total=len(vote.roster),
                seconds=max(0, math.ceil(vote.created+vote.timeout-time.monotonic()))),
                RTextList('\n', scope) if scope is not None else '', ' ',
                self.button('yes', 'vote '+vote.request_id+' yes'), ' ',
                self.button('no', 'vote '+vote.request_id+' no'), ' ',
                self.button('progress', 'status '+vote.request_id)))
        except (ValueError, ResourceWarning) as exc:
            self.message(src, str(exc) if isinstance(exc, ValueError) else 'invalid_target')

    def end_vote_locked(self):
        if self.vote:
            self.cooldowns[self.vote.kind] = time.monotonic()
            self.vote = None
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def expire_vote(self, request_id):
        with self.lock:
            if not self.vote or self.vote.request_id != request_id:
                return
            self.end_vote_locked()
        psi.broadcast(rtr('flow.expired', id=request_id))

    def show_status(self, src, request_id=None):
        with self.lock:
            vote = self.vote
            if not vote or request_id and vote.request_id != request_id:
                self.message(src, 'stale')
                return
            text = RTextList(rtr('flow.status', id=vote.request_id, action=self.action_text(vote.kind), target=self.target_name(vote.target),
                actor=vote.owner, yes=vote.yes, required=vote.threshold, total=len(vote.roster),
                no=len(vote.votes)-vote.yes, seconds=max(0, math.ceil(vote.created+vote.timeout-time.monotonic()))),
                RTextList('\n', vote.reset_scope) if vote.reset_scope is not None else '',
                ' ', self.button('yes', 'vote ' + vote.request_id + ' yes'),
                ' ', self.button('no', 'vote ' + vote.request_id + ' no'))
            if self.identity(src) == vote.owner or src.has_permission(self._config.cancel_permission):
                text.append(' ', self.button('cancel', 'cancel ' + vote.request_id))
        src.reply(text)

    def cast_vote(self, src, request_id, choice):
        try:
            with self.lock:
                self.available()
                vote = self.vote
                if not vote or vote.request_id != request_id or time.monotonic() >= vote.created+vote.timeout:
                    raise ValueError('stale')
                if not isinstance(src, PlayerCommandSource) or not src.is_player or src.player not in (self.players.snapshot() or ()):
                    raise ValueError('not_in_roster')
                passed = vote.cast(src.player, choice)
                if passed:
                    self.executing = vote.request_id
                    self.end_vote_locked()
            self.message(src, 'recorded')
            if passed:
                self.launch(vote.request_id, vote.kind, vote.target, src)
            else:
                self.show_status(src, request_id)
        except ValueError as exc:
            self.message(src, str(exc))

    def cancel(self, src, request_id=None):
        with self.lock:
            if request_id and self.force and self.force.request_id == request_id:
                if self.identity(src) != self.force.owner and not src.has_permission(self._config.cancel_permission):
                    self.message(src, 'permission')
                    return
                self.force = None
                if self.force_timer:
                    self.force_timer.cancel()
                self.message(src, 'force_cancelled')
                return
            vote = self.vote
            if not vote or request_id and vote.request_id != request_id:
                self.message(src, 'stale')
                return
            if self.identity(src) != vote.owner and not src.has_permission(self._config.cancel_permission):
                self.message(src, 'permission')
                return
            self.end_vote_locked()
        psi.broadcast(rtr('flow.cancelled', id=vote.request_id))

    abort_operation = cancel
    confirm_operation = show_status

    def reset_summary(self, src, slot):
        src.reply(self.reset_scope(slot))

    @staticmethod
    def slot_contract(slot):
        return {key: value for key, value in slot.get_config().serialize().items() if key != 'stats'}

    def request_force(self, src, kind, target=None):
        if not self.can_force(src):
            self.message(src, 'permission')
            return
        target = self.resolve_target(target) if target else self.current_slot.path
        try:
            target_slot = self.validate_target(kind, target)
            with self.lock:
                self.available()
                request_id = uuid.uuid4().hex
                self.force = ForceRequest(request_id, kind, target, self.identity(src),
                    self.vote.request_id if self.vote else None,
                    time.monotonic()+self._config.force_timeout, self._config.serialize(),
                    self.slot_contract(target_slot))
                if self.force_timer:
                    self.force_timer.cancel()
                self.force_timer = Timer(self._config.force_timeout, self.expire_force, [request_id])
                self.force_timer.daemon = True
                self.force_timer.start()
                old = self.force.vote_id or '-'
            src.reply(RTextList(rtr('flow.force_summary', action=self.action_text(kind), target=self.target_name(target), id=request_id, old=old),
                               ' ', self.button('confirm', 'force confirm ' + request_id),
                               ' ', self.button('cancel_force', 'cancel ' + request_id)))
            if kind == 'reset':
                self.reset_summary(src, target_slot)
        except (ValueError, ResourceWarning):
            self.message(src, 'invalid_target')

    def expire_force(self, request_id):
        with self.lock:
            if self.force and self.force.request_id == request_id:
                self.force = None

    def confirm_force(self, src, request_id):
        with self.lock:
            candidate = self.force
        if not candidate or candidate.request_id != request_id or not self.can_force(src):
            self.message(src, 'stale')
            return
        try:
            target_slot = self.validate_target(candidate.kind, candidate.target)
            if self.slot_contract(target_slot) != candidate.slot_config:
                raise ValueError('invalid_target')
        except (ValueError, ResourceWarning):
            self.message(src, 'invalid_target')
            return
        with self.lock:
            force = self.force
            if (self.closed or self.executing or not force or force.request_id != request_id
                or force.owner != self.identity(src) or not self.can_force(src)
                or time.monotonic() >= force.expires or force.config != self._config.serialize()
                or force.vote_id != (self.vote.request_id if self.vote else None)):
                self.message(src, 'stale')
                return
            self.executing = request_id
            self.force = None
            if self.force_timer:
                self.force_timer.cancel()
            old = self.vote.request_id if self.vote else None
            self.end_vote_locked()
        if old:
            psi.broadcast(rtr('flow.cancelled', id=old))
        self.launch(request_id, force.kind, force.target, src)

    def request_backup(self, src):
        if not self.can_backup(src):
            self.message(src, 'permission')
            return
        try:
            self.validate_target('backup', self.current_slot.path)
            with self.lock:
                self.available()
                if self.vote:
                    raise ValueError('busy')
                request_id = uuid.uuid4().hex
                self.executing = request_id
            self.launch(request_id, 'backup', self.current_slot.path, src)
        except (ValueError, ResourceWarning):
            self.message(src, 'backup_preflight')

    def launch(self, request_id, kind, target, src):
        with self.lock:
            # Even an unload between claim and launch needs the finalizer.
            # The worker sees closed before stopping and releases ownership.
            self.worker = Thread(target=self.execute, args=(request_id, kind, target, src), name='mount-executor')
            self.worker.start()

    def wait_state(self, predicate, timeout):
        deadline = time.monotonic()+timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError('server state timeout')
            time.sleep(0.05)

    def execute(self, request_id, kind, target, src):
        slot, acquired, stopped = None, False, False
        was_running, stop_requested = None, False
        result, error, recovery = None, None, 'unchanged'
        try:
            was_running = psi.is_server_running()
            slot = self.validate_target(kind, target)
            if kind == 'switch':
                slot.lock(self._config.mount_name)
                acquired = True
            if self.closed:
                raise RuntimeError('unloading')
            if was_running:
                psi.broadcast(rtr('flow.stopping'))
                stop_requested = True
                psi.stop()
                self.wait_state(lambda: not psi.is_server_running(), self._config.stop_timeout)
                stopped = True
                self.current_slot.on_unmount()
                self.players.invalidate()
            if kind == 'backup':
                slot = self.validate_target(kind, target)
                result = run_backup(slot.path, slot.reset_path, self._config.backup_root,
                                    self._config.backup_worlds, self.servers_as_list+self._config.servers_path)
            elif kind == 'reset':
                slot = self.validate_target(kind, target)
                ResetHelper.reset(slot.path, slot.reset_path, slot.reset_type)
            else:
                slot.load_config()
                if not slot.checked or slot.occupied_by != self._config.mount_name:
                    raise ValueError('invalid_target')
                self.patch_properties(slot)
                old_config, old_path, previous = psi.get_mcdr_config(), self._config.current_server, self.current_slot
                try:
                    self.patch_mcdr_config(slot)
                    self._config.current_server = slot.path
                    self._config.save()
                except Exception:
                    self._config.current_server = old_path
                    psi.modify_mcdr_config(changes={k: old_config[k] for k in (
                        'working_directory', 'start_command', 'handler', 'plugin_directories')})
                    raise
                self.current_slot = slot
                acquired = False
                previous.release(self._config.mount_name)
        except Exception:
            error = uuid.uuid4().hex
            logger().exception('Mount operation %s failed (%s)', request_id, error)
        finally:
            try:
                if was_running and stop_requested and (stopped or not psi.is_server_running()):
                    psi.start()
                    self.wait_state(psi.is_server_startup, self._config.start_timeout)
                    recovery = 'started'
                    if not self.closed:
                        self.current_slot.on_mount()
                        if self.players.snapshot() is None:
                            self.restore_players()
                elif was_running:
                    recovery = 'still_running' if psi.is_server_running() else 'unknown'
                else:
                    recovery = 'stayed_stopped' if was_running is False else 'unknown'
            except Exception:
                recovery = 'startup_failed'
                logger().exception('Mount server recovery failed')
            try:
                if acquired:
                    slot.release(self._config.mount_name)
                if self.closed:
                    self.current_slot.release(self._config.mount_name)
            except Exception:
                error = error or uuid.uuid4().hex
                logger().exception('Mount lock cleanup failed')
            try:
                text = rtr('flow.result' if kind == 'backup' else 'flow.operation_result',
                           action=self.action_text(kind), id=request_id, result=(result[0] if result else '-'),
                           worlds=(', '.join(result[1]) if result else '-'),
                           skipped=(', '.join(result[2]) if result else '-'),
                           outcome=rtr('flow.failed', error=error) if error else rtr('flow.completed'),
                           error=error or '-', recovery=rtr('flow.'+recovery))
                logger().info(str(text))
                if kind == 'backup':
                    if src.is_player:
                        with self.lock:
                            self.results[src.player] = text
                        if src.player in (self.players.snapshot() or ()):
                            with self.lock:
                                pending = self.results.pop(src.player, None)
                            if pending is not None:
                                psi.tell(src.player, pending)
                    else:
                        src.reply(text)
                else:
                    psi.broadcast(text)
            finally:
                with self.lock:
                    if self.executing == request_id:
                        self.executing = None

    def patch_properties(self, slot):
        if self._config.overwrite_path in ('', '.', None):
            return
        slot.load_properties()
        patches = Properties()
        try:
            with open(self._config.overwrite_path, 'rb') as stream:
                patches.load(stream, 'utf-8')
        except FileNotFoundError:
            return
        for key, value in patches.items():
            slot.properties[key] = value
        slot.save_properties()

    def patch_mcdr_config(self, slot):
        directories = list(psi.get_mcdr_config()['plugin_directories'])
        if self.current_slot.plg_dir in directories:
            directories.remove(self.current_slot.plg_dir)
        if slot.plg_dir and slot.plg_dir not in directories:
            directories.append(slot.plg_dir)
        psi.modify_mcdr_config(changes={'working_directory': slot.path, 'start_command': slot.start_command,
            'handler': slot.handler, 'plugin_directories': directories})

    def close(self):
        with self.lock:
            old = self.vote.request_id if self.vote else None
            self.closed = True
            self.end_vote_locked()
            self.force = None
            if self.force_timer:
                self.force_timer.cancel()
        self.current_slot.on_unmount()
        self.players.invalidate(preserve_query=True)
        if not self.executing:
            self.current_slot.release(self._config.mount_name)
        if old:
            psi.broadcast(rtr('flow.cancelled', id=old))

    def list_servers(self, src, page=1):
        views, slots, reasons = [], {}, {}
        degraded = False
        for path in self.servers_as_list:
            try:
                if not os.path.isdir(path):
                    raise ValueError('missing path')
                slot = MountSlot(path)
                score = slot.stats.player_time_ns_v2
                if slot.stats.schema_version != 2 or type(score) not in (int, float) or not math.isfinite(score) or score < 0:
                    score, degraded = 0, True
                views.append((path, max(0, score)))
                slots[path] = slot
            except Exception:
                reasons[path] = 'missing' if not os.path.isdir(path) else 'invalid'
                degraded = True
                views.append((path, 0))
        views = order_slots(views, self._config.pinned_servers,
                            'configured' if degraded else self._config.list_order)
        size = self._config.list_size
        if type(size) is not int or size <= 0:
            size = 15
        pages = max(1, math.ceil(len(views)/size))
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 0
        if not 1 <= page <= pages:
            page = 1
            self.message(src, 'page_corrected')
        src.reply(rtr('list.title'))
        if degraded and self._config.list_order == 'activity':
            self.message(src, 'activity_fallback')
        for path, _ in views[(page-1)*size:page*size]:
            slot, current = slots.get(path), path == self.current_slot.path
            row = RTextList(self.target_name(path), ' ')
            if path in self._config.pinned_servers:
                row.append(rtr('flow.pinned'), ' ')
            if current:
                row.append(rtr('flow.current'), ' ')
            if slot:
                row.append(slot.desc, ' ')
                reason = ('unchecked' if not slot.checked else 'occupied'
                          if slot.occupied_by and (not current or slot.occupied_by != self._config.mount_name)
                          else 'available')
                row.append(rtr('flow.'+reason), ' ')
                if current and slot.reset_path and reason == 'available':
                    row.append(self.button('reset', 'reset'))
                elif not current and reason == 'available':
                    row.append(self.button('switch', 'switch '+self.target_token(path)))
            else:
                row.append(rtr('flow.'+reasons[path]))
            if current and self.can_backup(src):
                row.append(' ', self.button('backup', 'backup'))
            src.reply(row)
        if not views:
            src.reply(rtr('list.empty'))
        src.reply(RTextList(self.button('previous', 'list '+str(page-1)) if page > 1 else rtr('flow.previous'),
            ' {}/{} '.format(page,pages), self.button('next', 'list '+str(page+1)) if page < pages else rtr('flow.next')))
        if self.can_force(src):
            src.reply(RTextList(rtr('flow.management'), ' ', self.button('force_reset', 'force reset')))
            for path, _ in views:
                if path != self.current_slot.path:
                    src.reply(RTextList(self.target_name(path), ' ',
                        self.button('force_switch', 'force switch '+self.target_token(path))))

    def get_config(self, key, src=None):
        value = getattr(self._config, key)
        if src:
            src.reply(str(value))
        return value

    @staticmethod
    def list_path_config(src, path):
        src.reply(MountSlot(path).get_config().display(path))

    def edit_path_config(self, src, path, key, value):
        with self.lock:
            if self.executing or self.closed:
                self.message(src, 'busy')
                return
            self.executing = request_id = uuid.uuid4().hex
        try:
            slot = self.current_slot if path == self.current_slot.path else MountSlot(path)
            src.reply(slot.edit_config(key, value))
        finally:
            with self.lock:
                if self.executing == request_id:
                    self.executing = None

    def reload(self, src):
        with self.lock:
            if self.executing or self.closed or self.reloading:
                self.message(src, 'busy')
                return
            self.reloading = True
        try:
            config = MountConfig.load()
            added, removed = DetectHelper.detect_slots(config.servers_path, config.available_servers)
            config.available_servers.extend(added)
            for path in removed:
                config.available_servers.remove(path)
            for path in added:
                DetectHelper.init_conf(path)
            config.save()
            psi.reload_plugin(psi.get_self_metadata().id)
        finally:
            with self.lock:
                self.reloading = False
