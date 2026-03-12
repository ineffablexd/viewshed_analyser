from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox
)

from qgis.PyQt.QtGui import QColor

from qgis.gui import QgsMapToolEmitPoint

from qgis.core import (
    QgsProject, QgsFeature, QgsGeometry, QgsPointXY,
    QgsVectorLayer, QgsRasterLayer,
    QgsSymbol, QgsSingleSymbolRenderer
)

import processing
import random


class ClickTool(QgsMapToolEmitPoint):

    def __init__(self, canvas, plugin):
        super().__init__(canvas)
        self.plugin = plugin

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.plugin.run_viewshed(point)


class VisibilityDock(QDockWidget):

    def __init__(self, iface):

        super().__init__("Visibility Analyzer")

        self.iface = iface
        self.canvas = iface.mapCanvas()

        container = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("DEM Layer"))
        self.dem = QComboBox()
        layout.addWidget(self.dem)

        layout.addWidget(QLabel("Input Layer (towers or line)"))
        self.layer = QComboBox()
        layout.addWidget(self.layer)

        layout.addWidget(QLabel("POV Height (m)"))
        self.height = QDoubleSpinBox()
        self.height.setValue(1.7)
        layout.addWidget(self.height)

        layout.addWidget(QLabel("Radius (m)"))
        self.radius = QSpinBox()
        self.radius.setMaximum(100000)
        self.radius.setValue(2000)
        layout.addWidget(self.radius)

        self.run_layer_btn = QPushButton("Run From Layer Vertices")
        self.run_layer_btn.clicked.connect(self.run_from_layer)
        layout.addWidget(self.run_layer_btn)

        self.click_btn = QPushButton("Click On Map Mode")
        self.click_btn.clicked.connect(self.activate_click)
        layout.addWidget(self.click_btn)

        container.setLayout(layout)
        self.setWidget(container)

        self.populate_layers()

    # ------------------------------------------------

    def populate_layers(self):

        self.dem.clear()
        self.layer.clear()

        for l in QgsProject.instance().mapLayers().values():

            self.layer.addItem(l.name(), l)

            if l.type() == 1:  # raster
                self.dem.addItem(l.name(), l)

    # ------------------------------------------------

    def activate_click(self):

        tool = ClickTool(self.canvas, self)
        self.canvas.setMapTool(tool)

    # ------------------------------------------------

    def create_hillshade(self):

        dem = self.dem.currentData()

        if not dem:
            return

        # check if hillshade already exists
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Hillshade":
                return

        result = processing.run(
            "gdal:hillshade",
            {
                'INPUT': dem.source(),
                'AZIMUTH': 315,
                'ALTITUDE': 45,
                'Z_FACTOR': 1,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
        )

        path = result['OUTPUT']

        hillshade = QgsRasterLayer(path, "Hillshade")

        if hillshade.isValid():
            QgsProject.instance().addMapLayer(hillshade)

    # ------------------------------------------------

    def run_from_layer(self):

        layer = self.layer.currentData()

        if not layer:
            return

        self.create_hillshade()

        vertices = processing.run(
            "native:extractvertices",
            {
                'INPUT': layer,
                'OUTPUT': 'memory:'
            }
        )['OUTPUT']

        i = 1

        for f in vertices.getFeatures():

            p = f.geometry().asPoint()

            self.run_viewshed(p, i)

            i += 1

    # ------------------------------------------------

    def run_viewshed(self, point, index=1):

        dem = self.dem.currentData()

        if not dem:
            return

        root = QgsProject.instance().layerTreeRoot()

        group = root.findGroup("Viewsheds")

        if not group:
            group = root.addGroup("Viewsheds")

        # ------------------------------------
        # observer point
        # ------------------------------------

        observer = QgsVectorLayer(
            "Point?crs=" + dem.crs().authid(),
            f"observer_{index}",
            "memory"
        )

        pr = observer.dataProvider()

        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point)))

        pr.addFeature(feat)

        observer.updateExtents()

        symbol = QgsSymbol.defaultSymbol(observer.geometryType())

        color = QColor(
            random.randint(0,255),
            random.randint(0,255),
            random.randint(0,255)
        )

        symbol.setColor(color)

        observer.setRenderer(QgsSingleSymbolRenderer(symbol))

        QgsProject.instance().addMapLayer(observer, False)

        group.addLayer(observer)

        # ------------------------------------
        # viewshed
        # ------------------------------------

        result = processing.run(
            "grass7:r.viewshed",
            {
                'input': dem.source(),
                'coordinates': f"{point.x()},{point.y()}",
                'observer_elevation': self.height.value(),
                'max_distance': self.radius.value(),
                'output': 'TEMPORARY_OUTPUT'
            }
        )

        path = result['output']

        viewshed = QgsRasterLayer(path, f"viewshed_{index}")

        if viewshed.isValid():

            QgsProject.instance().addMapLayer(viewshed, False)

            group.addLayer(viewshed)

            viewshed.renderer().setOpacity(0.6)