## 操作与组合验证 / Operations and combined verification

401U-12以401U-11为base，复用其统计停止接口、RLock配置保护及列表排序；本PR只增加操作权限/按钮、完整玩家快照、投票/强制确认、备份、执行互斥及失败收尾。Combined head includes the list ancestor. The operations diff does not reimplement ranking/statistics.

真实MCDR 2.7/2.14/2.16各77项通过（退出码0），覆盖原工程66项与原QA11项语义；列表专属断言来自祖先，操作断言按代码块迁入。本轮工程复跑不代替QA独立复核。新SHA证据与完整命令/退出码见任务附件。服务边界为fixture，parser、RText、序列化及文件系统为真实API。

```powershell
uv run --python 3.11 --with-requirements requirements-test-2.7.txt python -m pytest -q -s
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.14.0 python -m pytest -q -s
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.16.0 python -m pytest -q -s
```

涵盖冻结分母/取整、单人/无人、首票锁定、加入/离开、冷却、旧入口、权限隐藏/手输、force本人确认与旧vote_id、竞态至多一次、外部占用拒绝、完整快照失败/竞态/旧输出、文件摘要损坏/提交失败/容量/隔离/links、原停机/stop/start超时、reload/unload归属与线程收尾。QA-01/02真实双语范围和门槛广播保留；QA-03随列表祖先保留。

`tests/isolated_mcdr.py` 是真实MCDR进程加Python vanilla输出模拟，不能当Java或认证玩家证据。旧PR13的f981c3f Java19项只作历史；拆分组合必须重新运行并在任务附件绑定当前head，不能把旧结果写为新SHA通过。

Original history: 13c36ad first suite43; f981c3f revision66; old2.14 callback-helper failures; 7d8d83b compatibility fix; 91bd3dc documentation fix. Source snapshots/logs remain on original tasks and the migration archive. No failed assertions were removed to claim a pass.

未验证 / Unverified: 认证玩家、非零list/join-left、客户端双语渲染/点击、实际玩家NBT full/region后果、掉线重连、Paper/Bukkit及生产配置。跨实例occupied_by TOCTOU、非事务重置部分失败、备份容量/结果留存、历史bye后非零退出无完整现场及CI artifact-v3/workflow权限风险保留。成功的新回归不能消除旧失败。

No merge/release/production access. Client work remains with user coordination through Fairy; there is no persistent testing service. The API and Java test layers must be reported separately from independent acceptance.
