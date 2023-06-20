# Mount

![MCDReforged](https://img.shields.io/badge/dynamic/json?label=MCDReforged&query=dependencies.mcdreforged&url=https%3A%2F%2Fraw.githubusercontent.com%2FFAS-Server%2FMount%2Fmaster%2Fmcdreforged.plugin.json&style=plastic)
![许可证](https://img.shields.io/github/license/FAS-Server/Mount?style=plastic)
![版本](https://img.shields.io/github/v/release/FAS-Server/Mount?style=plastic)
![总下载](https://img.shields.io/github/downloads/FAS-Server/Mount/total?label=total%20download&style=plastic)

**简体中文** | **[English](README_en.md)**

> 一个可以在单MCDR实例下挂载多个MC服务器的插件

## 使用说明

1. 配置一个MCDR实例(包括MC服务端)并加入此插件, 将其启动

2. 依照 (配置选项)[## 配置选项] 修改主体插件配置, **特别是自动检测挂载点的配置**, 然后重载此插件(使用指令`!!mount -r`即可)

3. 修改在第二步配置的`overwrite_name`文件, 建议添加服务器端口和RCON相关配置来获取一致的体验

4. 在第二步配置的自动检测目录中, 放入更多MC服务端实例, 然后可以游戏内输入`!!mount -l`查看并修改相关配置选项, 在修改完毕之后将`人工检查`项设置为`True`

5. 此时重新输入`!!mount -l` 即可看到人工检查通过的服务端处于可用状态, 挂载即可

6. 更多指令, 可在游戏内输入`!!mount`获取帮助信息

## 配置选项
1. 主体配置, 储存于配置文件夹下的`mount.json`中, 配置内的文件路径为MCDR实例目录的相对路径
```json5
{
  // 是否在玩家加入时显示一条帮助
  welcome_player: true,
  // 是否启用 !!m 短指令
  short_prefix: true,
  // 自动检测挂载点时的目录
  servers_path: [ "./servers" ],
  // 重写挂载点的server.properties时使用的覆盖配置, 格式同server.properties,只添加需要覆盖的配置行即可
  overwrite_name: "../servers/server.properties.overwrite",
  // 当前可用的挂载点列表,
  available_servers: [
    "servers/Parkour",
    "servers/PVP",
    "servers/Bingo"
  ],
  // 当前MCDR实例正在使用的挂载点
  current_server: "servers/Parkour",
  // 此MCDR实例的挂载标识
  mount_name: "MountDemo",
  // 分页大小
  list_size: 15
}
```
2. 挂载点配置信息, 储存于挂载点路径下的`mountable.json`中, 配置内的文件路径为MC服务器目录的相对路径
```json5
{
  // 是否通过了人工确认
  checked: false,
  // 描述信息
  desc:  "Demo server",
  // 此挂载点启动命令
  start_command: "./start.sh",
  // 此挂载点使用的MCDR handler
  handler: "vanilla_handler",
  // 占用此挂载点的MCDR实例的挂载标识, 空代表未挂载
  occupied_by: "",
  // 此挂载点的重置路径, 空或者.代表无重置路径
  reset_path: "",
  // 此挂载点的重置方法, full代表全部重置, region代表保留玩家信息(如跑酷记录)
  reset_type: "full",
  // 专为此挂载点的mcdr插件目录, 使得每个挂载点可使用专有的插件, 空或者.代表无
  plugin_dir: "",
  stats: {
    // 此挂载点的统计信息, 将自动生成
  }
}
```
## 其他
- 在自动检测目录的子目录下添加名为`.mount-ignore`的文件可以使该子目录免于检测
- 通过手动修改配置文件, 可以添加任意目录的服务器作为挂载点