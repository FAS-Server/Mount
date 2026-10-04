# Verification evidence / 验证证据

Local environment: Windows, CPython 3.11.16. Automated tests use actual MCDR
serialization, command nodes and RText, with the plugin/server-interface boundary
replaced by a deterministic test server. All filesystem changes use disposable
test directories. No production world was read or changed.

## Current evidence record / 当前证据记录

As of 2026-10-04, the deployed MCDR version is confirmed as **2.14.0**.
At `7d8d83b2b6009b235aa7670aff5562d89f9111d2`, engineering ran the original
66 tests on MCDR 2.7.0, 2.14.0 and 2.16.0: each passed with exit code 0.
The QA-owned additional 11 assertions also passed on 2.14.0 with exit code 0.
The project manager independently reran the 2.14 original 66 plus QA 11 tests,
with test and outer-process exit codes 0; for 2.7/2.16 the manager reviewed the
engineering logs without independently rerunning them. Complete commands,
separate stdout/stderr, environments and exit codes are attached to 401U-8.

Before that test-helper correction, `f981c3fe712d16fd387633ae34ac1b196439b5f4`
failed on 2.14 because the helper imported a 2.16-only callback module:
the original suite was 62 passed / 4 failed; the manager's suite including
QA's 11 additional assertions was 71 passed / 6 failed. This did not establish
a product-command failure. The helper now exercises 2.14's synchronous real
`_entry_execute` callbacks and retains 2.7's `execute` and 2.16's real invoker;
no parser mock, weakened assertions or conditional skips were introduced.

QA's isolated real Java / MCDR 2.14 report contains evidence for 19 passing
assertions at the older `f981c3f` SHA. Product files are identical at `7d8d83b`,
so that evidence is reused, not described as a new-SHA Java rerun. This report
does not establish authenticated player/client, Paper or production-configuration
acceptance. Subsequent documentation-only revisions do not change that test SHA.
These evidence layers describe what was exercised, not release or deployment approval.

中文：2026-10-04，部署版本确认为 MCDR 2.14.0。`7d8d83b` 工程回归三版本原66项各通过，
2.14 原QA11项也通过；经理独立复跑2.14原66＋QA11项，两层退出码0。
2.7/2.16经理仅核对工程日志。真实Java19项来自旧`f981c3f`且产品文件未变，复用该证据，
本轮未重跑Java。认证玩家/客户端、Paper及生产配置仍未验证；历史异常退出原因未定位，
CI artifact v3及凭据workflow权限风险保留。详细记录在401U-8/401U-9任务附件中。

## Historical initial implementation / 初次实现历史记录

At `13c36adcd18ea15e531e61d65914bae7bda946aa` (2026-10-03 UTC), initial local results were
**43 passed on MCDR 2.7.0; 43 passed on MCDR 2.16.0**.
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

- The initial implementation had no real Java evidence or confirmed deployment
  version. The later isolated Java/MCDR 2.14 evidence is scoped above; authenticated
  player/client, Paper and production configuration remain unverified.
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

中文：初次实现的自动测试与真实 MCDR 进程的可控服务端模拟通过，不等于真实 Java 游戏服务
验收。后续2.14隔离Java证据见上文；Bukkit/本地化输出、客户端与生产配置仍须独立验证。
未执行合并、正式发布或生产存档操作。
## Historical acceptance revision / 独立验收修订历史记录

固定旧 SHA `13c36adcd18ea15e531e61d65914bae7bda946aa` 运行独立补验得到 8 passed / 4 failed；保留原脚本全部 12 项功能断言，未删减要求。修复广播/状态重置范围、创建投票门槛和列表展示。新增 11 项语义测试覆盖非法页码及两端导航、四种不可用原因、重名精确目标与路径隐藏、活跃度整体降级、中英文 full/region 文本在 Yes 前展示。

2026-10-03 UTC 修订至`f981c3fe712d16fd387633ae34ac1b196439b5f4`，Windows / Python 3.11，MCDR 2.7.0 和 2.16.0 各 66 passed（原 43 + 独立 12 + 新增 11）。2.7 有两项依赖弃用警告。复现：

```text
uv run --python 3.11 --with-requirements requirements-test-2.7.txt python -m pytest -q tests
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.16.0 python -m pytest -q tests
uv run --python 3.11 --with-requirements requirements-test-2.7.txt python tests/isolated_mcdr.py en_us
uv run --python 3.11 --with-requirements requirements-test-2.7.txt python tests/isolated_mcdr.py zh_cn
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.16.0 python tests/isolated_mcdr.py en_us
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.16.0 python tests/isolated_mcdr.py zh_cn
```

四个隔离进程流程均有成功通过记录，覆盖真实 MCDR 插件加载、列表/边界按钮、玩家快照、切换比例、含空格路径切服、其他选民的重置 scope/status、取消、备份、full/region 重置、执行中 reload 和退出。最终批次中 2.7 中文流程一次完成动作并输出 bye 后非零退出，随后两次复跑均成功；该退出偶发尚未定位，不宣称进程稳定性已证明。服务端仍为 Python vanilla 输出模拟，不是 Java。中文测试环境显式配置 UTF-8 编解码，避免 Windows 默认 GBK 与模拟进程 UTF-8 不匹配；真实部署编码未验证。`rendered-en_us.txt` / `rendered-zh_cn.txt` 是实际 tellraw JSON 平展后的纯文本证据（换行显示为 ` | `），不代表客户端截图。单测另读取实际语言 YAML 并检查 RText 内容与按钮先后。

在该次修订运行时，真实 Java 服务端、认证客户端、EULA 设置及实际部署 MCDR 版本尚未提供；这描述当时的证据边界，后续2.14隔离Java记录见上文。原跨实例 TOCTOU、重置部分失败须人工恢复及 CI artifact v3/workflow 权限限制保留。该次工程运行未发布、合并、接受 EULA 或操作生产世界。

历史2.7中文流程的bye后非零退出仍未定位：原失败样本的完整stdout/stderr、外层及MCDR退出码、精确时序和现场SHA没有找回。残留日志与后续成功重跑不证明该失败已修复。原隔离脚本会覆盖同名日志，复现时应另外保存每次运行的stdout、stderr及外层/MCDR退出码；后续测试捕获器的改进不能补回历史证据。
