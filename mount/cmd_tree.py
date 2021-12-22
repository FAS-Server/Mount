from mcdreforged.api.command import Literal, Text, GreedyText, Integer
from mcdreforged.api.types import PluginServerInterface

from .MountManager import MountManager

"""
!!mount
        <slot_id> --restore
                  --confirm
        --restore
        --confirm
        --abort
        --menu             quick menu for lazy man
        --list <index>
        --config
        
                         
!!mnt           quick menu for lazy man
                    
"""


def register_commands(server: PluginServerInterface, manager: MountManager):
    # TODO
    slot_node = Text("slot_name")
    menu_node = Literal("--menu")
    config_node = Literal("--config")
    main_node = Literal('!!' + server.get_self_metadata().id).runs(
        lambda src: src.reply(manager.rtr())
    ).then(
        Literal('--restore').runs(lambda src: src.reply(manager.rtr("info.wip")))
    ).then(
        Literal('--confirm')
    ).then(
        menu_node
    ).then(
        Literal('--list')
    ).then(
        config_node
    ).then(
        slot_node.runs(lambda src, ctx: manager.request_mount(src, ctx['slot_name'])).then(
            Literal("--confirm")
        )
    )

    fast_node = Literal("!!mnt").redirects(menu_node)
    server.register_command(main_node)
    server.register_command(fast_node)
    server.register_help_message()
