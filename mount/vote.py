"""Frozen electorate. The manager serializes all mutations."""
import math
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class VoteSession:
    kind: str
    target: str
    owner: str
    roster: frozenset
    ratio: float
    timeout: float
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: float = field(default_factory=time.monotonic)
    votes: dict = field(default_factory=dict)
    reset_scope: object = None

    @property
    def threshold(self):
        return math.ceil(len(self.roster) * self.ratio)

    @property
    def yes(self):
        return sum(self.votes.values())

    def cast(self, player, choice):
        if player not in self.roster:
            raise ValueError('not_in_roster')
        if player in self.votes:
            raise ValueError('duplicate_vote')
        self.votes[player] = choice
        return bool(self.roster) and self.yes >= self.threshold
