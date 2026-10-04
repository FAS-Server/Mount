"""Independent acceptance probes; two assertions document contract defects."""
import re
import threading
from pathlib import Path

import pytest

from test_commands_stats import CommandUser, command_root


def test_other_reset_voter_receives_scope_before_yes(environment):
    m, server, Source = environment
    m.request_reset(Source('Alice'))
    bob = Source('Bob')
    m.show_status(bob, m.vote.request_id)
    visible = '\n'.join(map(str, server.messages + bob.replies))
    assert 'reset_scope' in visible, visible


def test_creation_broadcast_contains_threshold_and_timeout(environment):
    m, server, Source = environment
    m.request_mount(Source(), m.servers_as_list[1])
    visible = '\n'.join(map(str, server.messages))
    assert 'required' in visible and 'seconds' in visible, visible






def test_three_independent_capabilities_and_default_force_denial(environment):
    m, server, _ = environment
    root = command_root(m)
    for name, permission, backup, force in [('Alice',0,False,False),('Bob',3,True,False),('Admin',0,False,True)]:
        src = CommandUser(name,permission)
        root.execute(src,'!!mount')
        root.execute(src,'!!mount list')
        output = '\n'.join(map(str,src.replies))
        assert ('backup' in output) == backup
        assert ('force ' in output) == force
    m._config.force_players = []
    m.request_force(CommandUser('Admin',3),'reset')
    m.request_force(CommandUser(None,4),'reset')
    assert m.force is None and server.stops == 0


def test_force_permission_revoked_after_summary(environment):
    m, server, Source = environment
    m.request_force(Source('Admin'),'reset')
    request = m.force.request_id
    m._config.force_players = []
    m.confirm_force(Source('Admin'),request)
    assert m.executing is None and server.stops == 0


def test_old_yes_button_cannot_vote_on_new_request(environment):
    m, server, Source = environment
    m.request_mount(Source(),m.servers_as_list[1])
    old = m.vote.request_id
    m.cancel(Source(),old)
    m.request_mount(Source(),m.servers_as_list[1])
    m.cast_vote(Source(),old,True)
    assert m.vote.yes == 0 and server.stops == 0


def test_vote_force_cancel_race_at_most_one_execution(environment):
    m, server, Source = environment
    m.request_mount(Source(),m.servers_as_list[1])
    vote = m.vote.request_id
    m.cast_vote(Source(),vote,True)
    m.request_force(Source('Admin'),'switch',m.servers_as_list[1])
    force = m.force.request_id
    barrier = threading.Barrier(3)
    errors = []
    def run(fn):
        try:
            barrier.wait(5)
            fn()
        except BaseException as exc:
            errors.append(exc)
    threads = [threading.Thread(target=run,args=(fn,)) for fn in (
        lambda:m.cast_vote(Source('Bob'),vote,True),
        lambda:m.confirm_force(Source('Admin'),force),
        lambda:m.cancel(Source(),vote))]
    for thread in threads: thread.start()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    if m.worker: m.worker.join(5)
    assert not errors and server.stops <= 1 and m.executing is None


@pytest.mark.parametrize('n',[1,3,5])
def test_actual_manager_rounding_for_both_actions(environment,n):
    m, server, Source = environment
    m.players.players = {'Alice'} | {'P'+str(i) for i in range(n-1)}
    for kind,expected in [('switch',{1:1,3:2,5:3}[n]),('reset',n)]:
        m.request_vote(Source(),kind,m.servers_as_list[1] if kind=='switch' else m.current_slot.path)
        assert m.vote.threshold == expected and m.vote.yes == 0
        m.cancel(Source(),m.vote.request_id)
