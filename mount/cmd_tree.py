from mcdreforged.api.command import GreedyText, Literal, Text, Integer
from mcdreforged.api.rtext import RAction, RText, RTextList

from .config import SlotConfig
from .constants import COMMAND_PREFIX
from .utils import rtr


def register_commands(server, manager):
    def help_text(src):
        commands = ['switch <path>', 'reset', 'list [page]', 'vote <id> yes|no',
                    'status [id]', 'cancel <id>']
        if manager.can_backup(src):
            commands.append('backup')
        if manager.can_force(src):
            commands.extend(['force switch <path>', 'force reset', 'force confirm <id>'])
        if src.has_permission(3):
            commands.extend(['--config <path> set <key> <value>', '--reload'])
        src.reply(RTextList(rtr('help_msg.title', version=server.get_self_metadata().version), '\n',
            rtr('flow.help'), '\n', '\n'.join(COMMAND_PREFIX+' '+cmd for cmd in commands)))

    def target(kind, force=False):
        return GreedyText('target').runs(lambda src, ctx:
            manager.request_force(src, kind, ctx['target']) if force else manager.request_mount(src, ctx['target']))

    root = Literal({COMMAND_PREFIX, '!!m'} if manager.get_config('short_prefix') else COMMAND_PREFIX).runs(help_text)
    root.then(Literal('switch').then(target('switch')))
    root.then(Literal('reset').runs(manager.request_reset))
    root.then(Literal({'list', '--list', '-l'}).runs(lambda src: manager.list_servers(src)).then(
        Integer('page').runs(lambda src, ctx: manager.list_servers(src, ctx['page']))))
    root.then(Literal('status').runs(lambda src: manager.show_status(src)).then(
        Text('id').runs(lambda src, ctx: manager.show_status(src, ctx['id']))))
    root.then(Literal('vote').then(Text('id').then(
        Literal('yes').runs(lambda src, ctx: manager.cast_vote(src, ctx['id'], True))).then(
        Literal('no').runs(lambda src, ctx: manager.cast_vote(src, ctx['id'], False)))))
    root.then(Literal('cancel').then(Text('id').runs(lambda src, ctx: manager.cancel(src, ctx['id']))))
    root.then(Literal('backup').requires(manager.can_backup).runs(manager.request_backup))
    force = Literal('force').requires(manager.can_force)
    force.then(Literal('switch').then(target('switch', True)))
    force.then(Literal('reset').runs(lambda src: manager.request_force(src, 'reset')))
    force.then(Literal('confirm').then(Text('id').runs(lambda src, ctx: manager.confirm_force(src, ctx['id']))))
    root.then(force)
    root.then(Literal({'--reload', '-r'}).requires(lambda src: src.has_permission(3)).runs(manager.reload))
    # Greedy config arguments allow spaces in an exact configured path.
    def config_command(src, ctx):
        value = ctx['config']
        if ' set ' not in value:
            if value in manager.servers_as_list:
                manager.list_path_config(src, value)
            return
        path, arguments = value.rsplit(' set ', 1)
        key, separator, val = arguments.partition(' ')
        if path in manager.servers_as_list and separator and key in SlotConfig.get_field_annotations():
            manager.edit_path_config(src, path, key, val)
    root.then(Literal({'--config', '-cfg'}).requires(lambda src: src.has_permission(3)).then(
        GreedyText('config').runs(config_command)))
    server.register_command(root)
    server.register_help_message(COMMAND_PREFIX, rtr('help_msg.brief'))
