# Mount

![MCDReforged](https://img.shields.io/badge/dynamic/json?label=MCDReforged&query=dependencies.mcdreforged&url=https%3A%2F%2Fraw.githubusercontent.com%2FFAS-Server%2FMount%2Fmaster%2Fmcdreforged.plugin.json&style=plastic)
![许可证](https://img.shields.io/github/license/FAS-Server/Mount?style=plastic)
![版本](https://img.shields.io/github/v/release/FAS-Server/Mount?style=plastic)
![总下载](https://img.shields.io/github/downloads/FAS-Server/Mount/total?label=total%20download&style=plastic)

**简体中文** | **[English](README_en.md)**

> 一个可以在单MCDR实例下挂载多个MC服务器的插件

## 使用说明

1. 配置一个MCDR实例(包括MC服务端)并加入此插件, 将其启动

2. 依照 [配置选项](#配置选项) 修改主体插件配置, **特别是自动检测挂载点的配置**, 然后重载此插件(使用指令`!!mount -r`即可，需要 MCDR 3 级权限)

3. 修改在第二步配置的`overwrite_path`所指文件, 建议添加服务器端口和RCON相关配置来获取一致的体验

4. 在第二步配置的自动检测目录中, 放入更多MC服务端实例，重载后输入`!!mount -l`查看。检查各实例的`mountable.json`；游戏内用`!!mount --config <完整路径>`查看或修改配置需要 MCDR 3 级权限。确认配置后将`checked`设置为`true`

5. 重新输入`!!mount -l`查看可用状态；在线玩家可点击投票切换按钮发起投票，再用带会话 ID 的赞成按钮投票。达到门槛后才执行切换

6. 更多指令, 可在游戏内输入`!!mount`获取帮助信息

## 配置选项
1. 主体配置, 储存于配置文件夹下的`mount.json`中, 配置内的文件路径为MCDR实例目录的相对路径
```json5
{
  // 是否在玩家加入时显示一条帮助
  "welcome_player": true,
  // 是否启用 !!m 短指令
  "short_prefix": true,
  // 自动检测挂载点时的目录
  "servers_path": [ "./servers" ],
  // 重写挂载点的server.properties时使用的覆盖配置, 格式同server.properties,只添加需要覆盖的配置行即可
  "overwrite_path": "../servers/server.properties.overwrite",
  // 当前可用的挂载点列表,
  "available_servers": [
    "servers/Parkour",
    "servers/PVP",
    "servers/Bingo"
  ],
  // 当前MCDR实例正在使用的挂载点
  "current_server": "servers/Parkour",
  // 此MCDR实例的挂载标识
  "mount_name": "MountDemo",
  // 分页大小
  "list_size": 15,
  // 调试模式, 开启后会在控制台输出更多信息
  "debug": false
}
```
2. 挂载点配置信息, 储存于挂载点路径下的`mountable.json`中, 配置内的文件路径为MC服务器目录的相对路径
```json5
{
  // 是否通过了人工确认
  "checked": false,
  // 描述信息
  "desc":  "Demo server",
  // 此挂载点启动命令
  "start_command": "./start.sh",
  // 此挂载点使用的MCDR handler
  "handler": "vanilla_handler",
  // 占用此挂载点的MCDR实例的挂载标识, 空代表未挂载
  "occupied_by": "",
  // 此挂载点的重置路径, 空或者.代表无重置路径
  "reset_path": "",
  // 仅替换reset_path模板提供的world/world_nether/world_the_end；缺失的世界不变
  // full替换所选整个世界；region仅保留主世界world内的playerdata/advancements/stats，下界/末地仍整世界替换
  "reset_type": "full",
  // 专为此挂载点的mcdr插件目录, 使得每个挂载点可使用专有的插件, 空或者.代表无
  "plugin_dir": "",
  "stats": {
    // 此挂载点的统计信息, 将自动生成
  }
}
```
## 其他
- 在自动检测目录的子目录下添加名为`.mount-ignore`的文件可以使该子目录免于检测
- 通过手动修改配置文件, 可以添加任意目录的服务器作为挂载点
- 实际配置格式均需要满足json格式，即不得包含上例中以`//`开头的注释

## 投票、备份与排序升级

安装包含这些功能的版本后，普通切换和重置均创建在线玩家投票：默认切换 60%、重置 100%，门槛为 `ceil(N×ratio)`；创建时冻结在线集合，发起者也须显式投票。首票不能更改，后来者不加入、离开不降低门槛；无人在线或快照不可信时拒绝发起。超时及同类投票终结后的冷却默认均为 60 秒，可配置。

备份权限由`backup_permission`控制，默认 MCDR 3 级；授权者点击即执行，无投票或二次确认。运行中的服务器完全停止后，复制配置的世界及其中玩家数据，再尝试启动；原已停机则保持停机。默认备份`world`、`world_nether`、`world_the_end`，可配置相对路径；不备份插件数据，不提供恢复命令或自动清理。副本校验成功与服务器恢复启动成功分别报告。

强制名单`force_players`默认空，控制台强制`force_console`默认关闭；名单不授予备份或管理取消权限。所有`force switch/reset`均须操作者本人在默认 60 秒内执行`force confirm <id>`。确认前原投票继续；目标、配置或原会话变化会使摘要失效，不能抢占执行中的操作。备份和强制入口仅向授权者显示，手动输入也会检查权限。

列表默认配置顺序，置顶优先，可选可信活跃度排序；同分稳定，排序先于分页，不隐藏不可用项，统计不可信时明确降级。旧`<路径>`及`<路径> --confirm`创建切换投票；单独`--confirm`只查进度，`--reset/-rs`仍走重置投票，`!!m`别名可配置。重置失败可能留下部分替换，无自动回滚；跨实例文件占用检查不提供原子锁保证。

配置、命令及迁移细节见 [迁移与命令说明](docs/migration.md)。测试层级、历史失败和未验证范围见 [验证证据](docs/verification.md)，其中测试结果不代表客户端或生产部署验收，也不表示该版本已正式发布。
