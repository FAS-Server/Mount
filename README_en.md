# Mount

![MCDReforged](https://img.shields.io/badge/dynamic/json?label=MCDReforged&query=dependencies.mcdreforged&url=https%3A%2F%2Fraw.githubusercontent.com%2FFAS-Server%2FMount%2Fmaster%2Fmcdreforged.plugin.json&style=plastic)
![license](https://img.shields.io/github/license/FAS-Server/Mount?style=plastic)
![Release](https://img.shields.io/github/v/release/FAS-Server/Mount?style=plastic)
![total download](https://img.shields.io/github/downloads/FAS-Server/Mount/total?label=total%20download&style=plastic)

**[简体中文](README.md)** | **English**

> A plugin that make it possible to mount multi minecraft server in one mcdr instance

## Usage

1. Deploy a MCDR instance(with MC server), and start it with this plugin

2. Edit the main config according to [Config](#config), then reload this plugin(by command `!!mount -r` or other command provided by MCDR)

3. Edit the file of `overwrite_path` which is configed at setp 2, Recommand to set up server port and rcon to get a consistent experience

4. Add more MC server into the `servers_path` at step 2, then you can use `!!mount -l` to see them and edit their config according to [Config](#config), finally make sure set `checked` to true

5. Type `!!mount -l` now, you can see available servers now, and then mount it

6. For more command, type `!!mount` in game to get help

## Config
1. Main config, stored in config folder with name `mount.json`, and path in the config value should be relative to mcdr instance folder
```json5
{
  // show a help message when player join server
  "welcome_player": true,
  // enable short command !!m
  "short_prefix": true,
  // path used for auto-detect
  "servers_path": [ "./servers" ],
  // file used to overwrite server.properties, same format with server.properties but add necessary configs only
  "overwrite_path": "../servers/server.properties.overwrite",
  // available mount servers
  "available_servers": [
    "servers/Parkour",
    "servers/PVP",
    "servers/Bingo"
  ],
  // current mount server
  "current_server": "servers/Parkour",
  // Mount-label used to identity this MCDR instance
  "mount_name": "MountDemo",
  // page size of pagination
  "list_size": 15,
  "pinned_servers": [],
  "list_order": "configured",
  // debug mode, will print more info
  "debug": false
}
```
2. Config for mountable server, stored under mc server with name`mountable.json`, and path in config should relative to mc server folder
```json5
{
  // manually checked
  "checked": false,
  // description
  "desc":  "Demo server",
  // start command
  "start_command": "./start.sh",
  // MCDR handler
  "handler": "vanilla_handler",
  // Mount-label to show which MCDR instance occupied this server
  "occupied_by": "",
  // reset path for this server, '' and '.' means empty
  "reset_path": "",
  // reset method, full for reset all, region for keep up player data(e.g. Parkour record)
  "reset_type": "full",
  // mcdr plugin dir for this server, '' and '.' means empty
  "plugin_dir": "",
  "stats": {
    // Stats for this server, will generate automaticaly
  }
}
```
## Other
- add file with name `.mount-ignore` under folder in auto-detect folder to not detect that folder
- by editing config file, you can add any server in any folder as mountable server
- the actual config file must be json format, so remove the comments starting with `//` from above config sample
## Lists and statistics

`pinned_servers` takes precedence. `list_order` defaults to `configured`; optional `activity` ranks newly accumulated trusted player time. Ties are stable and ordering precedes pagination. Unavailable servers show reasons. Legacy suspect totals stay for audit only. Runtime player deduplication does not claim a complete roster when loaded midway. Public actions use private tokens, duplicate names use numbers, and complete paths may contain spaces. Existing switch/reset requests, confirmation and cancellation keep their behavior.

See [migration](docs/migration.md) and [verification boundaries](docs/verification.md). Client rendering/clicking, authenticated players and production remain unverified.
## List and statistics

`pinned_servers` takes priority. `list_order` accepts `configured` or `activity`; trusted player time determines activity order, ties stay stable and sorting precedes pagination. Unavailable targets show their status and reason. Monotonic counters accumulate observed events; player deduplication lasts only for the running session.

Use `!!mount --list [page]`, `!!mount <full path or token>`, `!!mount --reset`, `!!mount --confirm` and `!!mount --abort`. Exact configured targets take precedence over the trailing ` --confirm` parameter. Public buttons use tokens and duplicate names use numbered labels without exposing absolute paths.

For version1.0.0 create configuration in the format above. `servers_path` must be an array of strings. Generated statistics use `schema_version: 2`, nanosecond `use_time_ns_v2`/`player_time_ns_v2` counters and the `last_mount_ns` anchor; no permanent player list is stored.
