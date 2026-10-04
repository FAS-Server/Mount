## 列表与统计迁移 / List and statistics migration

`mount.json` 增加 `pinned_servers: []` 与 `list_order: "configured"`。置顶路径按配置顺序优先；`activity` 使用新的可信累计玩家时间，同分保持配置顺序，先排序再分页。不可用服仍显示原因，不提供操作按钮。非法页码回到第一页并提示；非法分页大小使用15。

旧 `mountable.json` 可直接加载。旧 `total_use_time`、`total_player_time`、`total_players` 保留审计，不参与排行。`schema_version: 2`、`use_time_ns_v2`、`player_time_ns_v2` 从新安装后的单调时钟增量累计；运行期去重玩家，不新增永久玩家名单。中途加载只统计此后观察到的可信玩家事件，不能代表完整在线快照，也不追补以前的时间。不可信活跃度降级为置顶后的配置顺序。

列表显示名称和同名编号；完整SHA-256目标token映射配置路径，公开按钮不带绝对路径。`!!mount <完整路径或token>`（可含空格）、尾随 `--confirm`、`--reset`、`--confirm`、`--abort` 保持原请求/确认/取消流程与权限。本版本不包含投票、强制或备份入口。管理员的配置查看仍使用原配置命令。

Add `pinned_servers: []` and `list_order: "configured"` to the instance configuration. Pins follow their configured order. Optional `activity` uses newly accumulated player time; ties are stable and ordering precedes pagination. Unavailable servers remain visible with reasons and no action. Invalid pages return to page 1 with a notice; invalid page sizes use 15.

Existing slot configurations load unchanged. Legacy totals remain for audit and never rank servers. Schema 2 use/player time starts with new monotonic increments. Player deduplication is runtime only. Loading midway counts subsequently observed player events; it does not claim a complete roster or reconstruct past time. Untrusted activity falls back to configured order after pins.

Names and duplicate-name numbers replace paths in public rows. Full SHA-256 target tokens map exactly to configured paths. Existing mount/reset/confirm/abort behavior and permissions remain, including complete paths containing spaces and the trailing `--confirm` alias. There are no vote, force or backup commands in this version.

修改配置前备份配置文件；回退保留旧审计字段。统计值不能当作完整认证玩家历史。Back up configuration before editing; retain legacy audit fields when reverting. Statistics are not a complete authenticated-player history.
