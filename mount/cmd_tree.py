from mcdreforged.api.command import Literal, Text, GreedyText
from mcdreforged.api.types import PluginServerInterface

from .MountManager import MountManager
from .constants import COMMAND_PREFIX
from .utils import rtr
from .config import MountConfig, MountableMCServerConfig

"""
!!mount
        <slot_id> -confirm
        -restore
        -confirm
        -abort
        -list <index>
        -config
"""


def register_commands(server: PluginServerInterface, manager: MountManager):
    # TODO: 精细权限系统
    def get_slot_node():  # to check if is a usable slot
        return Text('slot_path').requires(lambda src, ctx: ctx['slot_path'] in manager.servers_as_list,
                                          lambda src, ctx: rtr('error.invalid_mount_path'))

    config_node = Literal("-config").then(
        # global config blew
        Literal('-global').then(
            Text("config_key").requires(lambda src, ctx: ctx['config_key'] in MountConfig.get_annotations_fields(),
                                        lambda src, ctx: rtr('config.invalid_key', key=ctx['config_key']))
            .runs(
                lambda src, ctx: manager.get_config(src, ctx["config_key"])
            ).then(
                Literal("set").then(
                    GreedyText("value").runs(lambda src, ctx: manager.set_config(src, ctx["config_key"], ctx["value"])))))
    ).then(
        get_slot_node().runs(lambda src, ctx: manager.list_path_config(src, ctx['slot_path']))
        .then(Literal('set').then(Text('key').requires(
            lambda src, ctx: ctx['key'] in MountableMCServerConfig.get_annotations_fields(),
            lambda src, ctx: rtr('config.invalid_key', key=ctx['key']))
            .then(Text('value').runs(
                lambda src, ctx: manager.edit_path_config(src, ctx['slot_path'], ctx['key'], ctx['value'])
            )))))
    main_node = Literal(COMMAND_PREFIX).runs(
        lambda src: src.reply(rtr("help_msg.full", prefix=COMMAND_PREFIX))
    ).then(
        Literal('-restore').runs(lambda src: src.reply(rtr("info.wip")))
    ).then(
        Literal('-confirm').runs(lambda src, ctx: manager.confirm_operation(src))
    ).then(
        Literal('-list').runs(lambda src, ctx: manager.list_servers(src))
    ).then(
        Literal('-abort').runs(lambda src, ctx: manager.abort_mount(src))
    ).then(
        config_node
    ).then(
        Literal('-reload').runs(lambda src, ctx: manager.reload(src))
    ).then(
        get_slot_node().runs(
            lambda src, ctx: manager.request_mount(src, ctx['slot_path'], with_confirm=False)
        ).then(
            Literal("-confirm").runs(lambda src, ctx: manager.request_mount(src, ctx['slot_path'], with_confirm=True))
        )
    )

    server.register_command(main_node)
    server.register_help_message(COMMAND_PREFIX, rtr("help_msg.brief"))
