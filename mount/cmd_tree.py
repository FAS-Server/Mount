from mcdreforged.api.command import Literal, Text, GreedyText
from mcdreforged.api.types import PluginServerInterface, CommandSource
from mcdreforged.api.rtext import RTextList, RText, RAction, RColor

from .MountManager import MountManager
from .constants import COMMAND_PREFIX
from .utils import rtr
from .config import MountableMCServerConfig


def get_clickable(cmd: str):
    cmd = f'{COMMAND_PREFIX} {cmd}'
    return RText(cmd, color=RColor.yellow).h(rtr('help_msg.click_to_fill', cmd=cmd)).c(RAction.suggest_command, cmd)


def get_help(src: CommandSource):
    sub_command = ['reset', 'list', 'reload', 'config']
    payload = RTextList(RText(rtr('help_msg.title', version=src.get_server().as_plugin_server_interface()
                                  .get_self_metadata().version)), '\n')
    payload.append(
        get_clickable('<server_name>'),
        ' ',
        rtr('help_msg.command.mount'),
        '\n'
    )
    for i in sub_command:
        payload.append(
            get_clickable('--' + i),
            ' ',
            rtr(f'help_msg.command.{i}'),
            '\n'
        )
    src.reply(payload)


def get_config_help(src: CommandSource):
    payload = RTextList(
        get_clickable(" -config <server_name>"),
        ' ',
        RText(rtr('help_msg.config.all')),
        '\n',
        get_clickable(" --config <server_name> set <key> <value>"),
        ' ',
        RText(rtr('help_msg.config.edit'))
    )
    src.reply(payload)


def register_commands(server: PluginServerInterface, manager: MountManager):
    root_prefix = {COMMAND_PREFIX, "!!m"} if manager.get_config(
        'short_prefix') else COMMAND_PREFIX

    def get_slot_node():  # to check if is a usable slot
        return Text('slot_path').requires(lambda src, ctx: ctx['slot_path'] in manager.servers_as_list,
                                          lambda src, ctx: rtr('error.invalid_mount_path'))

    config_node = Literal({"--config", "-cfg"}).runs(lambda src: get_config_help(src))\
        .requires(lambda src: src.has_permission(3), lambda src: src.reply(rtr('error.perm_deny'))).then(
        get_slot_node().runs(
            lambda src, ctx: manager.list_path_config(src, ctx['slot_path']))
        .then(Literal('set').then(Text('key').requires(
            lambda src, ctx: ctx['key'] in MountableMCServerConfig.get_annotations_fields(
            ),
            lambda src, ctx: rtr('config.invalid_key', key=ctx['key']))
            .then(GreedyText('value').runs(
                lambda src, ctx: manager.edit_path_config(
                    src, ctx['slot_path'], ctx['key'], ctx['value'])
            )))))
    main_node = Literal(root_prefix).runs(
        lambda src: get_help(src)
    ).then(
        Literal({'--reset', '-rs'}).runs(lambda src: manager.request_reset(src))
    ).then(
        Literal('--confirm').runs(lambda src,
                                  ctx: manager.confirm_operation(src))
    ).then(
        Literal({'--list', '-l'}).runs(lambda src,
                                       ctx: manager.list_servers(src))
    ).then(
        Literal('--abort').runs(lambda src, ctx: manager.abort_operation(src))
    ).then(
        config_node
    ).then(
        Literal({'--reload', '-r'}).runs(lambda src, ctx: manager.reload(src))
    ).then(
        get_slot_node().runs(
            lambda src, ctx: manager.request_mount(
                src, ctx['slot_path'], with_confirm=False)
        ).then(
            Literal("--confirm")
            .runs(lambda src, ctx: manager.request_mount(src, ctx['slot_path'], with_confirm=True))
        )
    )
    server.register_command(main_node)
    server.register_help_message(COMMAND_PREFIX, rtr("help_msg.brief"))
