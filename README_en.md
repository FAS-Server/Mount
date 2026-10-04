# Mount

![MCDReforged](https://img.shields.io/badge/dynamic/json?label=MCDReforged&query=dependencies.mcdreforged&url=https%3A%2F%2Fraw.githubusercontent.com%2FFAS-Server%2FMount%2Fmaster%2Fmcdreforged.plugin.json&style=plastic)
![license](https://img.shields.io/github/license/FAS-Server/Mount?style=plastic)
![Release](https://img.shields.io/github/v/release/FAS-Server/Mount?style=plastic)
![total download](https://img.shields.io/github/downloads/FAS-Server/Mount/total?label=total%20download&style=plastic)

**[简体中文](README.md)** | **English**

> A plugin that make it possible to mount multi minecraft server in one mcdr instance

## Usage

1. Deploy a MCDR instance(with MC server), and start it with this plugin

2. Edit the main config according to [Config](#config), then reload this plugin (`!!mount -r` requires MCDR permission level 3)

3. Edit the file specified by `overwrite_path` in step 2. Setting server port and RCON options can provide a consistent experience

4. Add more MC servers under `servers_path`, reload, and use `!!mount -l` to list them. Check each instance's `mountable.json`; viewing or editing configuration with `!!mount --config <full path>` requires MCDR permission level 3. Set `checked` to `true` after checking the configuration

5. Type `!!mount -l` to check availability. An online player can click the vote-switch button to start a vote, then explicitly vote with its session-ID Yes button. Switching runs only after the threshold is reached

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
  // Only replace world/world_nether/world_the_end provided by reset_path; missing worlds stay unchanged
  // full replaces entire selected worlds; region preserves only main-world playerdata/advancements/stats; selected Nether/End worlds are replaced entirely
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

## Voting, backup and ordering upgrade

After installing a version containing these features, ordinary switch/reset commands create online-player votes: defaults are 60%/100%, with a threshold of `ceil(N×ratio)` and the online electorate frozen at creation. The initiator must vote explicitly. First votes cannot change; arrivals are excluded and departures do not lower the threshold. Empty or untrusted player snapshots refuse initiation. Timeout and cooldown after each vote of the same kind ends both default to 60 seconds and are configurable.

`backup_permission` defaults to MCDR level 3. Authorized backup clicks execute immediately without voting or confirmation. A running server is fully stopped before copying configured worlds and their player data, then startup is attempted; an originally stopped server stays stopped. Defaults are `world`, `world_nether`, `world_the_end`, with configurable relative paths. Plugin data, restore commands and automatic retention cleanup are excluded. Verified-copy success and server-startup success are reported separately.

`force_players` defaults to empty and `force_console` to false. Force names grant neither backup nor management-cancel permission. Every `force switch/reset` requires the operator's own `force confirm <id>` within 60 seconds by default. The old vote continues before confirmation; target, configuration or old-session changes invalidate the summary. Running operations cannot be preempted. Backup/force entries are visible only to authorized users, and manually typed commands also check authorization.

Lists default to configured order, with pins first and optional trusted activity sorting. Ties are stable, sorting precedes pagination, unavailable entries remain visible, and untrusted statistics trigger an explicit fallback. Legacy `<path>` and `<path> --confirm` create switch votes; bare `--confirm` only shows progress, `--reset/-rs` creates reset votes, and `!!m` is configurable. Failed resets may leave partial replacements with no automatic rollback; file-based cross-instance occupancy does not provide atomic locking.

See [migration and commands](docs/migration.md) for configuration and migration details, and [verification evidence](docs/verification.md) for test layers, historical failures and unverified areas. Tests do not establish client or production acceptance or imply a formal release.


## Lists and statistics

`pinned_servers` takes precedence. `list_order` defaults to `configured`; optional `activity` ranks newly accumulated trusted player time. Ties are stable and ordering precedes pagination. Unavailable servers show reasons. Legacy suspect totals stay for audit only. Runtime player deduplication does not claim a complete roster when loaded midway. Public actions use private tokens, duplicate names use numbers, and complete paths may contain spaces. Existing switch/reset requests, confirmation and cancellation keep their behavior.

See [migration](docs/migration.md) and [verification boundaries](docs/verification.md). Client rendering/clicking, authenticated players and production remain unverified.
