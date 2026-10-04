## 列表验证 / List verification

使用真实MCDR命令节点、RText及序列化API；仅PSI服务边界为隔离fixture。`tests/test_list.py` 保留原排序/统计/分页及QA-03语义，`tests/test_legacy.py` 增加旧命令请求/确认/取消、空格目标、真实双语文本和重载线程检查。`tests/command_api.py` 依真实2.7/2.14/2.16回调返回值执行，不mock parser。

Run from the repository root:

```powershell
uv run --python 3.11 --with-requirements requirements-test-2.7.txt python -m pytest -q -s
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.14.0 python -m pytest -q -s
uv run --python 3.11 --with-requirements requirements-test.txt --with mcdreforged==2.16.0 python -m pytest -q -s
```

2.7/2.14/2.16各26项通过（退出码0），包括原QA9项列表探针；工程复跑不代替新SHA独立审查。测试覆盖默认配置顺序、手动置顶、活跃度与同分、排序先于分页、异常活跃度降级、全部不可用原因、完整token与隐私、边界按钮、空列表/非法页码/大小、重复加入离开、反复挂载与重载/卸载无统计线程残留。旧操作测试校验原请求状态及确认分派，不宣称执行器或磁盘操作可靠性已由本方向修复。

Tests cover ordering, pagination, status reasons, privacy, exact targets, legacy dispatch and statistics lifecycle. Server/filesystem operation reliability belongs to the operations change. API/fixture passes do not establish client rendering or authenticated-player behavior.

未验证 / Unverified: 客户端中英文渲染/点击、真实认证玩家统计、Paper/Bukkit、生产版本/配置。历史PR13 Java证据只属于原SHA，不作为本列表SHA重跑证据。保留旧操作失败、跨实例占用TOCTOU、非事务重置、历史退出及CI风险；无合并发布授权。
