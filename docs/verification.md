# Verification evidence / 验证证据

Local environment: Windows, CPython 3.11.16. Automated tests use actual MCDR
serialization, command nodes and RText, with the plugin/server-interface boundary
replaced by a deterministic test server. All filesystem changes use disposable
test directories. No production world was read or changed.

Final local results: **43 passed on MCDR 2.7.0; 43 passed on MCDR 2.16.0**.
The isolated real-MCDR subprocess scenario passed on both versions, including
full/region reset and reload during execution. The 2.7 environment emitted its
existing pkg_resources/enum deprecation warnings; 2.16 emitted none in the unit suite.

## Reproduce

Minimum supported version:

```sh
python -m venv .venv-baseline
.venv-baseline/Scripts/python -m pip install -r requirements-test-2.7.txt
.venv-baseline/Scripts/python -m pytest -q
.venv-baseline/Scripts/python tests/isolated_mcdr.py
```

On Linux use `.venv-baseline/bin/python`. Current-version verification uses
`requirements-test.txt` plus `mcdreforged==2.16.0` in a separate environment.
Both versions were verified locally. Existing repository packaging CI is separate
from these results; no workflow was added because the existing OAuth credential
does not have workflow scope. No extra permission was requested.

## Coverage

The test suite covers frozen thresholds/rounding, explicit solo vote, empty roster,
first-vote locking, duplicate/new-arrival rejection and departing players; exact-ID
expiry/cancel; legacy confirmations; concurrent votes; force summary retaining the
old vote, owner checks, exact old-vote binding, changed targets, force cancellation
and independent permissions; direct authorized backup, duplicate-click exclusion,
originally stopped server, stop timeout, startup timeout, reset failure recovery,
unload/reload while copying and fresh load without a previous module.

File tests verify SHA-256 detects equal-size corruption, failed commit removes only
the temporary copy, manifest includes scope/skipped worlds/empty directories,
overlapping paths and real symbolic links are rejected, Windows reparse-point
attributes are rejected, missing reset-template dimensions remain untouched, and
full/region match the advertised player-data scope. Configuration invalid values,
legacy default migration, empty/bad-size pagination, stable pinned/activity order,
foreign occupied targets, failed lock acquisition and release ownership are checked.
Controlled monotonic clocks verify duplicate joins, player time, unload/remount and
absence of duplicate statistics threads. Snapshot tests cover timeout, malformed
counts, untrusted chat, event deltas and old Info.id barriers.

`tests/isolated_mcdr.py` starts a real MCDR subprocess with the packaged plugin and
a disposable Python process producing vanilla Minecraft stdout. It exercises actual
event dispatch, trusted PlayerCommandSource, list restoration, voting, switching to
a full path with spaces, offline verified backup, both reset modes, reload during
execution, normal reload, and orderly shutdown. Its server-process input/output is
controlled; it does not run a Java Minecraft server or listen on a network port.
The foreground harness collects completion and terminates only its own subprocess
tree on failure. `isolated-mcdr.log` is generated locally and intentionally untracked.

## Limits / 待独立验收

- Real Java vanilla/Paper/Bukkit output, live authentication and game-world validity
  have not been verified. The deployed MCDR version is unknown; test it before rollout.
- Bukkit and localized/custom handler snapshot formats need deployment validation;
  unsupported/unknown snapshots refuse voting safely. A `list` response has no nonce;
  queries never overlap within one server session. Expired/unloaded queries must
  drain their old response before a new query starts; a server that never responds
  remains untrusted until a new service session. Info.id filters queued old output.
- Cross-instance occupied_by remains non-atomic file IO (existing TOCTOU limitation).
  No distributed locking guarantee is claimed.
- Reset is not transactional; a partial disk failure can require manual world recovery.
  Backup verification commits the copy independently of server recovery, so a valid
  backup may coexist with failed startup. Historical backups are never auto-pruned.
- Full unload cannot synchronously join the executor from the event thread because
  startup events need that thread. The old executor retains ownership, performs
  recovery/finalization, and a process-wide owner prevents a fresh load starting a
  second manager. In-memory backup-result delivery does not survive process exit.

中文：自动测试与真实 MCDR 进程的可控服务端模拟通过，不等于真实 Java 游戏服务
验收。实际部署版本、Bukkit/本地化输出及真实游戏存档须由阶段 3 独立验证。
未执行合并、正式发布或生产存档操作。
