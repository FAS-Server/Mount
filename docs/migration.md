# Mount voting and backup migration / 投票与备份迁移

## 行为变化

旧配置可继续加载，新增字段采用安全默认值。`!!mount <完整路径>` 和尾随
`--confirm` 均只创建切换投票；`--reset/-rs` 创建重置投票。单独 `--confirm`
只显示投票进度，不投赞成票也不执行操作。`--abort` 仅取消有权取消的当前投票。
新按钮全部绑定完整 UUID，旧会话按钮不会操作新会话。`!!m` 别名按原配置保留。

切换默认 60%、重置默认 100%、60 秒超时。冻结在线分母，门槛向上取整，发起者
必须显式投票，一人一票且不能改票。加入不增员、离开不降低门槛；已经离线的玩家
不能继续投票。普通投票仅受信任玩家命令源可发起，控制台只看进度。
同实例同类投票从上次终结起冷却 60 秒。

运行中加载、重载及切服后查询 `list` 恢复完整在线集合。只支持 vanilla/bukkit
英文在线列表格式；超时、人数不匹配或其他 handler 安全拒绝投票，单次进出事件
不恢复信任。已收到但尚未处理的旧输出通过 MCDR 单调 Info.id 屏障过滤。
查询不重叠，过期/卸载前的查询必须先丢弃旧回复再重查；完全不回复时持续拒绝投票，直到新服务会话。
查询期间的进出事件合并进快照。服务器身份依赖其认证方式，离线模式同名冒用
风险必须由部署者处理；不要将普通聊天字符串作为强制名单身份来源。

## 新增配置

在原 Mount 实例配置文件中设置，重载生效：

| 字段 | 默认值 / 说明 |
|---|---|
| `pinned_servers` | `[]`；完整路径，按置顶名单顺序优先 |
| `list_order` | `configured`；可选 `activity`，只使用新可信累计玩家时长，同分稳定 |
| `switch_ratio`, `reset_ratio` | `0.6`, `1.0`；范围 `(0,1]` |
| `vote_timeout`, `vote_cooldown` | `60`, `60` 秒 |
| `backup_permission`, `cancel_permission` | `3`, `3`；MCDR 0–4 等级 |
| `force_players`, `force_console` | `[]`, `false`；按认证玩家名精确匹配，名单不附带其他权限 |
| `force_timeout` | `60` 秒，所有强制操作本人确认有效期 |
| `backup_root` | `../mount-backups`；须与实例、源世界和重置模板隔离 |
| `backup_worlds` | `world/world_nether/world_the_end`；可配置实例内相对路径 |
| `stop_timeout`, `start_timeout` | `60`, `120` 秒 |

非法分页大小回退 15；非法比例、权限、计时或排序模式拒绝加载，修正配置后重载。
旧 `SlotStats` 字段保留供审计，不参与排名；新 `use_time_ns_v2` 和
`player_time_ns_v2` 从零建立可信基线，单调时钟累计。不持久化玩家姓名名单。

## 操作命令

`!!mount switch <完整路径>` 支持空格。`reset` 发起当前服重置投票；
`vote <id> yes|no` 投票，`status [id]` 查看，`cancel <id>` 由发起者或管理权限取消。
`list [page]` 先排序再分页，不可用目标保留显示。

授权者看到独立 `backup` 按钮，点击直接开始，无确认、无投票、不切换或重置。
服务器原在运行则完全停服后复制并尝试恢复；原已停机则保持停机。
至少一个世界存在才备份，缺失世界列入 manifest。逐文件相对路径、大小、SHA-256
及空目录校验一致后，写 manifest 并在同一文件系统内将临时目录改名提交。
不自动删除历史备份、不提供恢复命令、不备份插件数据；自行安排容量与人工恢复。
符号链接、Windows 重解析点、世界/模板/目的包含关系拒绝。
启动命令发出不等于启动完成，结果分别报告文件操作与真实启动状态。
备份结果仅向发起者及管理日志显示；掉线结果限本次运行期保存并在回服后补发。

`force switch <完整路径>`、`force reset` 仅名单用户可用；均需
`force confirm <id>` 本人确认。确认摘要绑定操作者、完整目标、配置与原投票 ID。
确认前原投票继续；放弃、过期或原投票变化使摘要失效。确认不等待他人同意，
也不能抢占执行中的操作。

重置仅替换模板实际提供的默认三个世界。full 替换整个世界；region 仅保留
主世界的 `playerdata/advancements/stats`，下界与末地整世界替换。重置不是备份，
中途磁盘失败可能留下部分替换的世界，无自动回滚，应使用人工备份恢复。

卸载取消待投票/待确认，执行器协作收尾并恢复本次停下的服务器。
执行中重载复用旧管理器避免双执行器，完成后再次重载才加载新实例配置。
跨实例 `occupied_by` 仍为文件检查与写入，存在既有 TOCTOU 限制，不提供跨实例原子锁保证。

## English

Existing configuration loads with safe defaults. Legacy `<path>` and `<path> --confirm`
start a switch vote; `--reset/-rs` starts a reset vote. Bare `--confirm` only shows
progress. No legacy confirmation bypasses voting. `!!m` remains configurable.

Use `switch <full path>` (spaces supported), `reset`, `vote <id> yes|no`, `status [id]`,
`cancel <id>` and `list [page]`. Switch/reset require 60%/100% of the frozen online
electorate, rounded up; timeout and per-kind cooldown are 60 seconds. The initiator
must vote explicitly. First votes are final; arrivals are excluded, departures
do not lower the threshold, and offline players cannot cast new votes. Console
can inspect votes but cannot initiate or vote.

Load/reload/startup queries `list`. Only supported vanilla/bukkit English output
establishes a complete snapshot. Failure stays untrusted despite subsequent
join/leave events. Already queued old output is filtered by a monotonic Info.id
barrier.
Queries never overlap; expired/unloaded queries drain their old reply before a
new query starts. A server that never responds stays untrusted until a new session.
Authentication remains the Minecraft server's responsibility; offline mode allows
name impersonation. Force names match trusted player command sources.

The configuration table above lists all new fields. `list_order` defaults to
`configured`; `activity` uses only new trusted player-time statistics. Pinned
paths precede stable sorting and pagination. Old statistics stay for audit,
never influence activity ranking, and no permanent player-name history is added.

`backup` is visible only to users meeting `backup_permission` (default 3), and
executes immediately without voting or confirmation. It stops a running server,
copies configured worlds including player data, verifies paths/sizes/SHA-256 and
empty directories, writes a manifest, and atomically renames the temporary copy.
Missing worlds are recorded; all missing is rejected. Originally stopped servers
remain stopped. File results and verified startup results are reported separately.
Backup results are private to the requester/admin log; offline delivery is kept
only in memory. No retention deletion, restore command, plugin-data or cross-instance
backup is supplied. Reject links/reparse points and overlapping source/template/destination.

`force_players` defaults to empty and `force_console` to false. Names do not grant
backup or management-cancel permission. Every `force switch/reset` requires personal
`force confirm <id>` within `force_timeout` (60 seconds). The old vote continues
until confirmation; changing/ending it invalidates the summary. Execution cannot
be preempted. Force confirmation binds owner, target, configuration and exact old vote.

Reset replaces only worlds provided by the template. Full replaces whole worlds;
region preserves playerdata/advancements/stats only in the main world. Nether/End
are replaced entirely. Reset disk failures can leave partially replaced worlds;
there is no automatic rollback. Keep an independent backup for manual recovery.

Unload cancels pending sessions and lets an executor finish recovery. Reload during
execution reuses that executor's manager; reload again after completion to load new
instance configuration. File-based occupied_by retains its pre-existing cross-instance
TOCTOU limitation. Merge, release and production-world operations are outside this change.
## 列表与投票展示补充 / List and vote presentation

列表正文使用服务器目录名；重名以配置顺序编号消歧。按钮使用完整 SHA-256 路径令牌，后台仍精确匹配配置路径，手动输入完整路径继续兼容。令牌目标移除后拒绝执行。正文区分置顶、当前、可用、占用、未检查及目录/配置失效；边界翻页不可点击，无效页码返回第 1 页。任一活跃度不可验证时，整体降级为置顶加配置顺序并说明原因，不隐藏不可用项。

List text uses directory names, with configured-order numbers for duplicates. Buttons use full SHA-256 path tokens resolved to exact configured paths; manual full paths remain supported. Removed token targets are rejected. Rows distinguish pinned/current/available/occupied/unchecked/missing/invalid states. Boundary navigation is inactive; invalid pages return to page 1. Untrusted activity falls back to pinned then configured order with an explicit explanation, preserving unavailable entries.

投票创建广播包含实际比例、赞成门槛、冻结人数、剩余时间及进出规则。重置创建广播与 status 在赞成按钮之前显示本轮预检得到的模式、世界、模板名称和 full/region 玩家数据后果；不增加投票前确认。

Vote creation broadcasts include ratio, threshold, frozen electorate, remaining time and join/leave rules. Reset broadcasts and status show the preflight scope (mode, worlds, template name and full/region player-data consequences) before Yes buttons, without adding confirmation before voting.
