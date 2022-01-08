from mcdreforged.api.command import Literal, Text
from mcdreforged.api.types import PluginServerInterface

from .MountManager import MountManager
from .constants import COMMAND_PREFIX
from .utils import rtr

"""
!!mount
        <slot_id> --restore
                  --confirm
        --restore
        --confirm
        --abort
        --list <index>
        --config
"""


def register_commands(server: PluginServerInterface, manager: MountManager):
    # TODO
    slot_node = Text("slot_name")
    config_node = Literal("--config").then(
        Text("config_key").requires(lambda src, ctx: ctx["config_key"] in manager.configurable_things).runs(
            lambda src, ctx: manager.get_config(src, ctx["config_key"])
        ).then(
            Literal("set").then(
                Text("value").runs(lambda src, ctx: manager.set_config(src, ctx["config_key"], ctx["value"]))
            )
        )
    )
    main_node = Literal(COMMAND_PREFIX).runs(
        lambda src: src.reply(rtr("info.help_msg"))
    ).then(
        Literal('--restore').runs(lambda src: src.reply(rtr("info.wip")))
    ).then(
        Literal('--confirm').runs(lambda src, ctx: manager.confirm_mount(src))
    ).then(
        Literal('--list').runs(lambda src, ctx: manager.list_servers(src))
    ).then(
        config_node
    ).then(
        slot_node.requires(lambda src, ctx: ctx["slot_name"] in manager.servers_as_list).runs(
            lambda src, ctx: manager.request_mount(src, ctx['slot_name'], with_confirm=False)
        ).then(
            Literal("--confirm").runs(lambda src, ctx: manager.request_mount(src, ctx['slot_name'], with_confirm=True))
        )
    )

    server.register_command(main_node)
    server.register_help_message(COMMAND_PREFIX, rtr("info.help_msg_brief"))
