
def classFactory(iface):
    from .visibility_plugin import VisibilityPlugin
    return VisibilityPlugin(iface)
