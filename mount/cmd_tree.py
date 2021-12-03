from mcdreforged.api.command import Literal, Text, GreedyText, Integer
from mcdreforged.api.types import PluginServerInterface
"""
!!mount
        <slot_id> --restore
                  --confirm
        --restore
        --confirm
        --menu             quick menu for lazy man
        --list <index>
        --config --server-port
               --rcon-port
               --rcon-passwd
               --rcon-enable
               <slot_id> desc <desc>
                         reset-path <path>
                         plugin-path <path>
                         
!!mnt           quick menu for lazy man
                    
"""


def register_commands(server: PluginServerInterface):
    # TODO
    slot_node = Text("slot")
    menu_node = Literal("--menu")
    config_node = Literal("--config")
    main_node = Literal('!!' + server.get_self_metadata().id).then(
        Literal('--restore')
    ).then(
        Literal('--confirm')
    ).then(
        menu_node
    ).then(
        Literal('--list')
    ).then(
        config_node
    )
    fast_node = Literal("!!mnt").redirects(menu_node)
    server.register_command(main_node)
    server.register_command(fast_node)
