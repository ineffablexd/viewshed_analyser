from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtCore import Qt
from .visibility_dialog import VisibilityDock

class VisibilityPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None

    def initGui(self):
        self.action = QAction("Viewshed Analyzer", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("Ineffable Tools", self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("Ineffable Tools", self.action)

    def run(self):
        if not self.dock:
            self.dock = VisibilityDock(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()
