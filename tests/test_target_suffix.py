from pathlib import Path

import pytest

from command_api import CommandUser, command_root


@pytest.mark.parametrize('input_kind', ['path', 'token', 'path_alias', 'token_alias'])
def test_confirm_suffix_prefers_exact_configured_vote_target(environment, input_kind):
    from mount.constants import MOUNTABLE_CONFIG
    m, server, _ = environment
    base = Path(m.servers_as_list[1])
    target = Path(str(base)+' --confirm'+(' --confirm' if input_kind.endswith('alias') else ''))
    target.mkdir()
    (target/MOUNTABLE_CONFIG).write_bytes((base/MOUNTABLE_CONFIG).read_bytes())
    m._config.available_servers.append(str(target))
    value = m.target_token(str(target)) if input_kind.startswith('token') else str(target)
    src = CommandUser()
    command_root(m).execute(src, '!!mount switch '+value)
    assert m.vote is not None and m.vote.target == str(target)
    assert m.vote.yes == 0 and server.stops == 0


def test_legal_space_path_ending_confirm_is_exact(environment):
    from mount.constants import MOUNTABLE_CONFIG
    m, _, _ = environment
    original = Path(m.servers_as_list[1])
    target = original.parent / 'legal target --confirm'
    target.mkdir()
    (target / MOUNTABLE_CONFIG).write_bytes((original / MOUNTABLE_CONFIG).read_bytes())
    m._config.available_servers.append(str(target))
    source = CommandUser()
    command_root(m).execute(source, '!!mount switch ' + str(target))
    assert m.vote is not None and m.vote.target == str(target), source.replies
