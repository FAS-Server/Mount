# Mount

**简体中文** | **[English](README_en.md)**

> 一个可以在单MCDR实例下挂载多个MC服务器的插件

## 使用说明

在游戏内输入`!!mount`即可获取帮助信息

## 配置选项
1. 主体配置, 储存于配置文件夹下的`mount.json`中, 配置内的文件路径为MCDR实例目录的相对路径
```json5
{
  // 是否在玩家加入时显示一条帮助
  welcome_player: true,
  // 是否启用 !!m 短指令
  short_prefix: true,
  // 自动检测挂载点时的目录
  servers_path: "./servers",
  // 重写挂载点的server.properties时使用的覆盖配置
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
  mount_name: "MountDemo"
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
  plugin_dir: ""
}
```
## 其他
- 在自动检测目录的子目录下添加名为`.mount-ignore`的文件可以使该子目录免于检测
- 通过手动修改配置文件, 可以添加任意目录的服务器作为挂载点