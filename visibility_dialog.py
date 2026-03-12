from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QProgressBar, QGroupBox,
    QFormLayout, QApplication, QCheckBox, QHBoxLayout
)
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProject, QgsFeature, QgsGeometry, QgsPointXY,
    QgsVectorLayer, QgsRasterLayer, QgsSymbol,
    QgsSingleSymbolRenderer, QgsRasterShader, 
    QgsColorRampShader, QgsSingleBandPseudoColorRenderer,
    QgsCoordinateTransform, QgsField,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling
)
from qgis.PyQt.QtCore import QVariant, Qt

import processing
import random

class VisibilityDock(QDockWidget):

    def __init__(self, iface):
        super().__init__("Viewshed Analyzer")
        self.iface = iface
        self.canvas = iface.mapCanvas()

        container = QWidget()
        layout = QVBoxLayout()
        container.setMinimumWidth(320)

        # Premium UI Styling
        container.setStyleSheet("""
            QWidget { background-color: #f8f9fa; font-family: 'Segoe UI', sans-serif; color: #333; }
            QGroupBox { font-weight: bold; border: 1px solid #dee2e6; border-radius: 8px; margin-top: 15px; padding-top: 15px; background-color: white; color: #212529; }
            QComboBox { background-color: white; border: 1px solid #ced4da; border-radius: 4px; padding: 5px; color: #212529; }
            QComboBox QAbstractItemView { background-color: white; color: #212529; selection-background-color: #007bff; selection-color: white; }
            QPushButton { background-color: #007bff; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #0056b3; }
            QProgressBar { border: 1px solid #dee2e6; border-radius: 5px; text-align: center; background-color: #e9ecef; }
            QProgressBar::chunk { background-color: #28a745; border-radius: 4px; }
        """)

        in_group = QGroupBox("Project Selection")
        in_layout = QVBoxLayout()
        form = QFormLayout()
        
        self.dem = QComboBox()
        self.layer = QComboBox()
        form.addRow("DEM Layer:", self.dem)
        form.addRow("Observer Layer:", self.layer)
        in_layout.addLayout(form)
        
        in_group.setLayout(in_layout)
        layout.addWidget(in_group)

        p_group = QGroupBox("Analysis Settings")
        p_layout = QFormLayout()
        self.height = QDoubleSpinBox()
        self.height.setSuffix(" m"); self.height.setValue(1.7)
        self.radius = QSpinBox()
        self.radius.setSuffix(" m"); self.radius.setMaximum(100000); self.radius.setValue(2000)
        p_layout.addRow("POV Height:", self.height)
        p_layout.addRow("Radius:", self.radius)
        p_group.setLayout(p_layout)
        layout.addWidget(p_group)

        op_group = QGroupBox("Operations")
        op_layout = QVBoxLayout()
        self.run_btn = QPushButton("Run Global Analysis")
        self.run_btn.clicked.connect(self.run_from_layer)
        self.reset_btn = QPushButton("Reset Analysis Results")
        self.reset_btn.setStyleSheet("background-color: #dc3545;")
        self.reset_btn.clicked.connect(self.reset_results)
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m Points")
        
        op_layout.addWidget(self.run_btn)
        op_layout.addWidget(self.reset_btn)
        op_layout.addWidget(self.progress)
        op_group.setLayout(op_layout)
        layout.addWidget(op_group)


        dev_info = QLabel("Developer: Ineffable | ineffable0xd@gmail.com")
        dev_info.setAlignment(Qt.AlignCenter)
        dev_info.setStyleSheet("color: #adb5bd; font-size: 10px; margin-top: 15px;")
        layout.addWidget(dev_info)

        layout.addStretch()
        container.setLayout(layout)
        self.setWidget(container)

        self.populate_layers()
        QgsProject.instance().layersAdded.connect(self.populate_layers)
        QgsProject.instance().layersRemoved.connect(self.populate_layers)

    def showEvent(self, event):
        self.populate_layers()
        super().showEvent(event)

    def populate_layers(self):
        self.dem.clear(); self.layer.clear()
        for l in QgsProject.instance().mapLayers().values():
            self.layer.addItem(l.name(), l)
            if l.type() == 1: self.dem.addItem(l.name(), l)

    def reset_results(self):
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup("Viewsheds")
        if group:
            for child in list(group.children()):
                QgsProject.instance().removeMapLayer(child.layerId())
            root.removeChildNode(group)
        for layer in list(QgsProject.instance().mapLayers().values()):
            if layer.name() == "Hillshade":
                QgsProject.instance().removeMapLayer(layer.id())

    def create_hillshade(self):
        dem = self.dem.currentData()
        if not dem: return
        for l in list(QgsProject.instance().mapLayers().values()):
            if l.name() == "Hillshade": QgsProject.instance().removeMapLayer(l.id())
        
        res = processing.run("gdal:hillshade", {'INPUT': dem, 'Z_FACTOR': 1, 'OUTPUT': 'TEMPORARY_OUTPUT'})
        hs = QgsRasterLayer(res['OUTPUT'], "Hillshade")
        if hs.isValid():
            QgsProject.instance().addMapLayer(hs, False)
            QgsProject.instance().layerTreeRoot().insertLayer(0, hs)

    def run_from_layer(self):
        l = self.layer.currentData()
        if not l: return
        self.create_hillshade()
        
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup("Viewsheds")
        if not group: group = root.insertGroup(0, "Viewsheds")
        else:
            if root.children()[0] != group:
                c = group.clone(); root.insertChildNode(0, c); root.removeChildNode(group); group = c
        group.setExpanded(True)

        v = processing.run("native:extractvertices", {'INPUT': l, 'OUTPUT': 'memory:'})['OUTPUT']
        count = v.featureCount()
        self.progress.setMaximum(count)
        
        for i, f in enumerate(v.getFeatures(), 1):
            self.run_viewshed(f.geometry().asPoint(), i, group)
            self.progress.setValue(i); QApplication.processEvents()

    def run_viewshed(self, point, idx, group):
        dem = self.dem.currentData()
        if not dem: return
        
        color = QColor(random.randint(0,255), random.randint(0,255), random.randint(0,255))
        dem_crs = dem.crs(); canvas_crs = self.canvas.mapSettings().destinationCrs()
        p_analysis = point
        if canvas_crs != dem_crs:
            p_analysis = QgsCoordinateTransform(canvas_crs, dem_crs, QgsProject.instance()).transform(point)

        h = self.height.value()

        val, ok = dem.dataProvider().sample(p_analysis, 1)
        elev = float(round(val, 2)) if ok else 0.0

        obs = QgsVectorLayer(f"Point?crs={canvas_crs.authid()}", f"observer_{idx} (Elev: {elev}m)", "memory")
        pr = obs.dataProvider()
        pr.addAttributes([QgsField("Elevation", QVariant.Double), QgsField("POV_Height", QVariant.Double)])
        obs.updateFields()
        
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(point))
        f.setAttributes([elev, h])
        pr.addFeature(f)

        sym = QgsSymbol.defaultSymbol(obs.geometryType()); sym.setColor(color)
        obs.setRenderer(QgsSingleSymbolRenderer(sym))
        
        ls = QgsPalLayerSettings(); ls.fieldName = "Elevation"; ls.placement = QgsPalLayerSettings.AroundPoint
        tf = QgsTextFormat(); tf.setSize(9); tf.setColor(QColor("black"))
        bs = QgsTextBufferSettings(); bs.setEnabled(True); bs.setSize(1); bs.setColor(QColor("white"))
        tf.setBuffer(bs); ls.setFormat(tf)
        obs.setLabeling(QgsVectorLayerSimpleLabeling(ls)); obs.setLabelsEnabled(True)

        QgsProject.instance().addMapLayer(obs, False); group.insertLayer(0, obs)

        flags = "-c"
        res = processing.run("grass7:r.viewshed", {
            'input': dem, 'coordinates': f"{p_analysis.x()},{p_analysis.y()}",
            'observer_elevation': h, 'max_distance': self.radius.value(),
            'flags': flags, 'output': 'TEMPORARY_OUTPUT'
        })
        
        path = res.get('output') or res.get('output_raster') or res.get('OUTPUT')
        if not path: return
        vs = QgsRasterLayer(path, f"viewshed_{idx}")
        if vs.isValid():
            sh = QgsRasterShader(); cr = QgsColorRampShader(); cr.setColorRampType(QgsColorRampShader.Discrete)
            cr.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(-1, QColor(0,0,0,0), "Invisible"),
                QgsColorRampShader.ColorRampItem(1e9, color, "Visible")
            ])
            sh.setRasterShaderFunction(cr)
            vs.setRenderer(QgsSingleBandPseudoColorRenderer(vs.dataProvider(), 1, sh))
            vs.renderer().setOpacity(1.0)
            QgsProject.instance().addMapLayer(vs, False); group.insertLayer(1, vs); vs.triggerRepaint()