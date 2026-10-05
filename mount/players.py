import re
import time
from threading import RLock


class PlayerRegistry:
    """Only complete server-output snapshots establish trust."""
    def __init__(self):
        self.lock = RLock()
        self.players = set()
        self.trusted = False
        self.query = None
        self.deltas = []
        self.minimum_id = -1
        self.retry = False

    def invalidate(self, preserve_query=False):
        with self.lock:
            self.players.clear()
            self.trusted = False
            if preserve_query and self.query is not None:
                # A list reply carries no nonce. Drain an old pending reply
                # before issuing a new query in the same server session.
                self.query = time.monotonic() - 6
            else:
                self.query = None
            self.deltas.clear()
            self.retry = False

    def begin(self, minimum_id=-1):
        with self.lock:
            if self.query is not None:
                return False
            self.trusted = False
            self.query = time.monotonic()
            self.deltas.clear()
            self.minimum_id = minimum_id
            self.retry = False
            return True

    def event(self, player, joined):
        with self.lock:
            if joined:
                self.players.add(player)
            else:
                self.players.discard(player)
            if self.query is not None:
                self.deltas.append((player, joined))

    def accept(self, info, handler):
        with self.lock:
            if self.query is None:
                return False
            if not info.is_from_server or info.is_player or handler not in ('vanilla_handler', 'bukkit_handler'):
                return False
            if getattr(info, 'id', self.minimum_id+1) <= self.minimum_id:
                return False
            match = re.fullmatch(r'There are (\d+) (?:of a max of|out of maximum|of a maximum of) \d+ players online:\s*(.*)', info.content)
            if not match:
                return False
            if time.monotonic() - self.query > 5:
                self.query = None
                self.retry = True
                return False
            names = [n.strip() for n in match[2].split(',') if n.strip()]
            if len(names) != int(match[1]) or len(set(names)) != len(names) or any(
                    not re.fullmatch(r'[A-Za-z0-9_]{1,16}', n) for n in names):
                self.query = None
                return False
            self.players = set(names)
            for player, joined in self.deltas:
                if joined:
                    self.players.add(player)
                else:
                    self.players.discard(player)
            self.trusted = True
            self.query = None
            self.deltas.clear()
            return True

    def take_retry(self):
        with self.lock:
            value = self.retry
            self.retry = False
            return value

    def snapshot(self):
        with self.lock:
            return frozenset(self.players) if self.trusted else None
