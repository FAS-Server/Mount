from mcdreforged.api.types import PluginServerInterface as PSI

psi = PSI.get_instance().as_plugin_server_interface()


def rtr(translate_key, *args, **kwargs):
    return psi.rtr(f'mount.{translate_key}', *args, **kwargs)

def logger():
    return psi.logger