
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtCore import Qt
from .visibility_dialog import VisibilityDock

class VisibilityPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.dock = None

    def initGui(self):
        self.action = QAction("Visibility Analyzer", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&Visibility Analyzer", self.action)

    def unload(self):
        self.iface.removePluginMenu("&Visibility Analyzer", self.action)

    def run(self):
        if not self.dock:
            self.dock = VisibilityDock(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()
