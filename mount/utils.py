from mcdreforged.api.types import PluginServerInterface as PSI

psi = PSI.get_instance().as_plugin_server_interface()
_debug_no_check: bool = False

def setDebugNoCheck(value: bool):
    logger().info(f'Set debug no check to {value}')
    global _debug_no_check
    _debug_no_check = value

def rtr(translate_key, *args, **kwargs):
    return psi.rtr(f'mount.{translate_key}', *args, **kwargs)

def logger():
    return psi.logger

def debug(msg: str):
    psi.logger.debug(msg, no_check=_debug_no_check)