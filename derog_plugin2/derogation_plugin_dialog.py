# -*- coding: utf-8 -*-

import os
import math
import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QPushButton, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QGroupBox, QFrame, QWidget, QTabWidget, QSizePolicy
)
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QColor, QFont, QPainter, QPen, QBrush, QIcon

from qgis.core import (
    QgsVectorLayer, QgsGeometry, QgsPointXY, QgsProject, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsRasterLayer, QgsSimpleFillSymbolLayer, QgsFillSymbol,
    QgsSimpleLineSymbolLayer, QgsLineSymbol,
    QgsLayerTreeGroup
)
from qgis.gui import (
    QgsMapCanvas, QgsRubberBand,
    QgsMapToolPan, QgsMapToolZoom
)

from .sentinel2downloader_dialog import ConfirmDownloadDialog

# ============================================================
# CONFIGURATION DES 6 COUCHES TERRAIN
# ============================================================

# Cle : partie du nom de fichier (en minuscules) → (couleur_trait, couleur_remplissage, nom affiche, est_derogation)
COUCHES_TERRAIN = {
    'domiane_prive_etat':  ('#C0392B', '#C0392B40', "Domaine Privé de l'État",    False),
    'domaine_public':      ('#2980B9', '#2980B940', 'Domaine Public',              False),
    'domaine_forestier':   ('#27AE60', '#27AE6040', 'Domaine Forestier',           False),
    'domaine_communal':    ('#E67E22', '#E67E2240', 'Domaine Communal',            False),
    'derogation_central':  ('#F39C12', '#F39C1240', 'Dérogations Existantes',      True),
    'collectif':           ('#8E44AD', '#8E44AD40', 'Domaine Collectif',           False),
}

COULEURS_COUCHES = {k: (v[0], v[1]) for k, v in COUCHES_TERRAIN.items()}
NOM_LISIBLE      = {k: v[2]         for k, v in COUCHES_TERRAIN.items()}

# Zone valide Maroc — EPSG:26191
MAROC_XMIN = 100000
MAROC_XMAX = 900000
MAROC_YMIN = 100000
MAROC_YMAX = 700000

# ============================================================
# STYLES
# ============================================================

STYLE_DIALOG = """
QDialog {
    background-color: #ECECEC;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    color: #1a1a1a;
}
"""
STYLE_CARD = """
QGroupBox {
    background-color: #ECECEC;
    border: 1px solid #C8C8C8;
    border-radius: 6px;
    margin-top: 8px;
    font-size: 12px;
    font-weight: 600;
    color: #1a1a1a;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    background-color: #ECECEC;
}
"""
STYLE_INPUT = """
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #D8D8D8;
    border: 1px solid #C0C0C0;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    color: #1a1a1a;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border-color: #2563EB;
    background-color: #E0E0E0;
}
"""
STYLE_BTN_PRIMARY = """
QPushButton {
    background-color: #D8D8D8;
    color: black;
    border: none;
    border-radius: 4px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover { background-color: #1D4ED8; color: white; }
"""
STYLE_BTN_SECONDARY = """
QPushButton {
    background-color: #D8D8D8;
    color: #1a1a1a;
    border: 1px solid #C0C0C0;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    min-height: 26px;
}
QPushButton:hover { background-color: #CACACA; }
"""
STYLE_BTN_SUCCESS = """
QPushButton {
    background-color: #1D4ED8;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-size: 12px;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover    { background-color: #162D47; }
QPushButton:disabled { background-color: #A0A0A0; color: #E0E0E0; }
"""
STYLE_BTN_RESET = """
QPushButton {
    background-color: #DC2626;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-size: 12px;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover { background-color: #991B1B; }
"""
STYLE_RADIO = """
QRadioButton {
    spacing: 6px;
    color: #1a1a1a;
    font-size: 12px;
    background: transparent;
}
QRadioButton::indicator {
    width: 14px; height: 14px;
    border-radius: 7px;
    border: 2px solid #AAAAAA;
    background: #D8D8D8;
}
QRadioButton::indicator:checked {
    border-color: #2563EB;
    background-color: #2563EB;
}
"""
STYLE_TABLE = """
QTableWidget {
    background-color: #ECECEC;
    border: 1px solid #C8C8C8;
    border-radius: 6px;
    gridline-color: #D0D0D0;
    font-size: 12px;
    color: #1a1a1a;
}
QTableWidget::item { padding: 8px 12px; border-bottom: 1px solid #D0D0D0; }
QHeaderView::section {
    background-color: #D8D8D8;
    color: #444444;
    font-weight: 600;
    font-size: 11px;
    padding: 8px 12px;
}
"""
STYLE_TAB = """
QTabWidget::pane {
    background-color: #ECECEC;
    border: none;
    border-top: 1px solid #C8C8C8;
}
QTabBar::tab {
    background-color: #D8D8D8;
    color: #444444;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:selected { background-color: #2563EB; color: white; }
"""

# ============================================================
# WIDGET LEGENDE — 2 colonnes
# ============================================================

class LegendWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setMinimumHeight(10)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setStyleSheet("background:#F0F0F0; border-radius:3px;")

    def set_items(self, items):
        """items = liste de (couleur_hex, libelle)"""
        self.items = items
        n    = len(items)
        rows = math.ceil(n / 2)
        h    = 10 + rows * 20 + 10
        self.setMinimumHeight(h)
        self.update()

    def paintEvent(self, event):
        if not self.items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont('Segoe UI', 9)
        p.setFont(f)

        col_w  = self.width() // 2
        x0, y0 = 8, 8
        row_h  = 20

        for idx, (couleur, libelle) in enumerate(self.items):
            col = idx % 2
            row = idx // 2
            x   = x0 + col * col_w
            y   = y0 + row * row_h

            p.setBrush(QBrush(QColor(couleur)))
            p.setPen(QPen(QColor('#555'), 0.5))
            p.drawRect(x, y + 1, 13, 13)

            p.setPen(QPen(QColor('#1a1a1a')))
            p.drawText(x + 18, y + 12, libelle)

        p.end()


# ============================================================
# DIALOGUE PRINCIPAL
# ============================================================

class DerogationPluginDialog(QDialog):

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aide à la Décision — Dérogation & Raster Sentinel")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.png')))
        self.iface          = iface
        self.canvas         = iface.mapCanvas()
        self.resultats      = None

        self.rb_projet      = None
        self.rb_buffer      = None
        self.rb_mini_projet = None
        self.rb_mini_buffer = None

        self._osm_layer     = None

        # Outils de navigation
        self._tool_pan_obj      = None
        self._tool_zoom_in_obj  = None
        self._tool_zoom_out_obj = None

        self.setMinimumSize(980, 700)
        self.resize(1080, 780)
        self.setStyleSheet(STYLE_DIALOG)
        self._build_ui()
        self._init_mini_canvas()

    # ──────────────────────────────────────────────────────────
    # HELPERS COUCHES TERRAIN
    # ──────────────────────────────────────────────────────────

    def _cle_couche_terrain(self, layer):
        nom_lower = layer.name().lower().replace(' ', '_').replace('-', '_')
        for cle in COUCHES_TERRAIN:
            if cle in nom_lower:
                return cle
        return None

    def _est_couche_terrain(self, layer):
        return self._cle_couche_terrain(layer) is not None

    def _nom_affiche(self, layer):
        cle = self._cle_couche_terrain(layer)
        return COUCHES_TERRAIN[cle][2] if cle else layer.name()

    def _est_derogation(self, layer):
        cle = self._cle_couche_terrain(layer)
        return COUCHES_TERRAIN[cle][3] if cle else False

    # ──────────────────────────────────────────────────────────
    # CHARGEMENT AUTOMATIQUE DES 6 SHP
    # ──────────────────────────────────────────────────────────

    DOSSIER_SHP = r"C:\Users\hp\Desktop\TP_Plugin\Data_Mini_ProjetDerogation"

    FICHIERS_SHP = [
        "DOMIANE_PRIVE_ETAT",
        "DOMAINE_PUBLIC",
        "DOMAINE_FORESTIER",
        "DOMAINE_COMMUNAL",
        "Derogation_central_13_avril",
        "COLLECTIF",
    ]

    def _charger_couches_terrain(self):
        manquants = []
        for nom in self.FICHIERS_SHP:
            deja_charge = any(
                self._est_couche_terrain(l) and l.name().lower() == nom.lower()
                for l in QgsProject.instance().mapLayers().values()
            )
            if deja_charge:
                continue
            chemin = os.path.join(self.DOSSIER_SHP, nom + ".shp")
            if not os.path.exists(chemin):
                manquants.append(nom + ".shp")
                continue
            layer = QgsVectorLayer(chemin, nom, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
            else:
                manquants.append(nom + ".shp (invalide)")

        if manquants:
            QMessageBox.warning(
                self, "Fichiers introuvables",
                "Les fichiers suivants n'ont pas pu être chargés :\n\n"
                + "\n".join(f"  • {m}" for m in manquants)
                + f"\n\nDossier recherché :\n{self.DOSSIER_SHP}"
            )

    # ──────────────────────────────────────────────────────────
    # INIT MINI CANVAS
    # ──────────────────────────────────────────────────────────

    def _init_mini_canvas(self):
        self._charger_couches_terrain()
        self._charger_osm()
        self._sync_mini_canvas()

        couches_terrain = [
            l for l in QgsProject.instance().mapLayers().values()
            if isinstance(l, QgsVectorLayer) and l.isValid()
            and self._est_couche_terrain(l)
        ]
        if couches_terrain:
            from qgis.core import QgsRectangle
            ext = QgsRectangle()
            for l in couches_terrain:
                ext.combineExtentWith(l.extent())
            if not ext.isEmpty():
                self.mini_canvas.setExtent(ext)
        self.mini_canvas.refresh()

        self._tool_pan_obj = QgsMapToolPan(self.mini_canvas)
        self.mini_canvas.setMapTool(self._tool_pan_obj)

    def _charger_osm(self):
        url = (
            "type=xyz"
            "&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            "&zmax=19&zmin=0"
        )
        osm = QgsRasterLayer(url, "OpenStreetMap", "wms")
        self._osm_layer = osm if osm.isValid() else None

    def _sync_mini_canvas(self, avec_projet=False):
        toutes = list(QgsProject.instance().mapLayers().values())
        couches_terrain = [
            l for l in toutes
            if isinstance(l, QgsVectorLayer) and l.isValid()
            and self._est_couche_terrain(l)
        ]
        for layer in couches_terrain:
            self._appliquer_couleur(layer)

        all_layers = list(couches_terrain)
        if self._osm_layer:
            all_layers.append(self._osm_layer)

        self.mini_canvas.setLayers(all_layers)
        self.mini_canvas.setDestinationCrs(
            self.canvas.mapSettings().destinationCrs()
        )
        self._maj_legende(couches_terrain, avec_projet=avec_projet)

    # ──────────────────────────────────────────────────────────
    # COULEURS
    # ──────────────────────────────────────────────────────────

    def _appliquer_couleur(self, layer):
        nom_lower = layer.name().lower().replace(' ', '_').replace('-', '_')
        cle_trouvee = None
        for cle in COULEURS_COUCHES:
            if cle in nom_lower:
                cle_trouvee = cle
                break
        if cle_trouvee is None:
            return
        stroke_hex, fill_hex = COULEURS_COUCHES[cle_trouvee]
        geom_type = layer.geometryType()
        try:
            if geom_type == 2:
                sym = QgsFillSymbol.createSimple({
                    'color': fill_hex, 'outline_color': stroke_hex, 'outline_width': '0.5',
                })
                layer.renderer().setSymbol(sym)
            elif geom_type == 1:
                sym = QgsLineSymbol.createSimple({'color': stroke_hex, 'width': '0.6'})
                layer.renderer().setSymbol(sym)
            layer.triggerRepaint()
        except Exception:
            pass

    def _couleur_pour_couche(self, layer):
        nom_lower = layer.name().lower().replace(' ', '_').replace('-', '_')
        for cle, (stroke, fill) in COULEURS_COUCHES.items():
            if cle in nom_lower:
                return stroke, NOM_LISIBLE.get(cle, layer.name())
        return '#888888', layer.name()

    def _maj_legende(self, couches_vecto, avec_projet=False):
        items = []
        for layer in couches_vecto:
            couleur, libelle = self._couleur_pour_couche(layer)
            items.append((couleur, libelle))
        if avec_projet:
            items.append(('#2563EB', 'Zone projet'))
            items.append(('#10B981', 'Zone tampon'))
        self.legend_widget.set_items(items)

    # ──────────────────────────────────────────────────────────
    # CONSTRUCTION UI
    # ──────────────────────────────────────────────────────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(STYLE_TAB)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.vecteur_tab = QWidget()
        self._build_vecteur_tab()
        self.tab_widget.addTab(self.vecteur_tab, "Dérogation")

        self.raster_tab = QWidget()
        self._build_raster_tab()
        self.tab_widget.addTab(self.raster_tab, "Raster")

        main.addWidget(self.tab_widget)

        self.resultats_widget = QWidget()
        rl = QVBoxLayout(self.resultats_widget)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self._build_resultats(rl)
        self._build_footer(rl)
        main.addWidget(self.resultats_widget)

    def _on_tab_changed(self, idx):
        if not hasattr(self, 'resultats_widget'):
            return
        self.resultats_widget.setVisible(idx == 0)

    # ══════════════════════════════════════════════════════════
    # ONGLET VECTEUR
    # ══════════════════════════════════════════════════════════

    def _build_vecteur_tab(self):
        layout = QVBoxLayout(self.vecteur_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)

        # ── Formulaire gauche ──────────────────────────────────
        grp_form = QGroupBox("Informations projet")
        grp_form.setStyleSheet(STYLE_CARD)
        fl = QVBoxLayout(grp_form)
        fl.setContentsMargins(10, 14, 10, 8)
        fl.setSpacing(7)

        nr = QHBoxLayout()
        lbl_n = QLabel("Nom projet :")
        lbl_n.setStyleSheet("font-size:11px;color:#333;background:transparent;")
        lbl_n.setFixedWidth(80)
        self.nom_projet = QLineEdit()
        self.nom_projet.setStyleSheet(STYLE_INPUT)
        nr.addWidget(lbl_n)
        nr.addWidget(self.nom_projet)
        fl.addLayout(nr)

        # Type projet (caché, valeur fixe pour le PDF)
        self.type_projet = QComboBox()
        self.type_projet.addItems([
            "Residentiel", "Commercial", "Industriel",
            "Hotelier", "Equipement", "Autre"
        ])
        self.type_projet.hide()

        fl.addWidget(self._sep())

        lbl_src = QLabel("Source de la géométrie")
        lbl_src.setStyleSheet(
            "font-size:11px;font-weight:600;color:#1a1a1a;background:transparent;"
        )
        fl.addWidget(lbl_src)

        rr = QHBoxLayout()
        self.rb_coords  = QRadioButton("Coordonnées")
        self.rb_shp     = QRadioButton("Shapefile")
        self.rb_geojson = QRadioButton("GeoJSON")
        self.rb_coords.setChecked(True)
        for rb in (self.rb_coords, self.rb_shp, self.rb_geojson):
            rb.setStyleSheet(STYLE_RADIO)
            rr.addWidget(rb)
        rr.addStretch()
        fl.addLayout(rr)

        self.rb_coords.toggled.connect(self._toggle_loc)
        self.rb_shp.toggled.connect(self._toggle_loc)
        self.rb_geojson.toggled.connect(self._toggle_loc)

        # Widget coordonnées
        self.coords_widget = QWidget()
        self.coords_widget.setStyleSheet("background:transparent;")
        cw = QGridLayout(self.coords_widget)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(5)
        cw.setColumnStretch(1, 1)
        cw.setColumnStretch(3, 1)

        lbl_x = QLabel("X (Est) :")
        lbl_x.setStyleSheet("font-size:11px;color:#333;background:transparent;")
        self.x_coord = QDoubleSpinBox()
        self.x_coord.setRange(-9999999, 9999999)
        self.x_coord.setDecimals(2)
        self.x_coord.setValue(500000.00)
        self.x_coord.setSingleStep(100)
        self.x_coord.setStyleSheet(STYLE_INPUT)

        lbl_y = QLabel("Y (Nord) :")
        lbl_y.setStyleSheet("font-size:11px;color:#333;background:transparent;")
        self.y_coord = QDoubleSpinBox()
        self.y_coord.setRange(-9999999, 9999999)
        self.y_coord.setDecimals(2)
        self.y_coord.setValue(300000.00)
        self.y_coord.setSingleStep(100)
        self.y_coord.setStyleSheet(STYLE_INPUT)

        cw.addWidget(lbl_x, 0, 0)
        cw.addWidget(self.x_coord, 0, 1)
        cw.addWidget(lbl_y, 0, 2)
        cw.addWidget(self.y_coord, 0, 3)

        lbl_r = QLabel("Rayon (m) :")
        lbl_r.setStyleSheet("font-size:11px;color:#333;background:transparent;")
        self.rayon_projet = QDoubleSpinBox()
        self.rayon_projet.setRange(1, 99999)
        self.rayon_projet.setDecimals(0)
        self.rayon_projet.setValue(60)
        self.rayon_projet.setSingleStep(10)
        self.rayon_projet.setStyleSheet(STYLE_INPUT)
        self.lbl_surf_calc = QLabel("Surface : —")
        self.lbl_surf_calc.setStyleSheet(
            "font-size:10px;color:#2563EB;font-weight:600;background:transparent;"
        )
        self.rayon_projet.valueChanged.connect(self._maj_surf_calc)
        self._maj_surf_calc()

        cw.addWidget(lbl_r, 1, 0)
        cw.addWidget(self.rayon_projet, 1, 1)
        cw.addWidget(self.lbl_surf_calc, 1, 2, 1, 2)

        lbl_hint = QLabel("EPSG:26191 — Lambert Maroc Nord (mètres)")
        lbl_hint.setStyleSheet("font-size:9px;color:#999;background:transparent;")
        cw.addWidget(lbl_hint, 2, 0, 1, 4)

        fl.addWidget(self.coords_widget)

        self.shp_widget = self._make_file_widget(
            "Shapefile (.shp) :", "shp_path",
            "Sélectionnez un fichier .shp...", self._browse_shp
        )
        fl.addWidget(self.shp_widget)

        self.geojson_widget = self._make_file_widget(
            "GeoJSON :", "geojson_path",
            "Sélectionnez un fichier .geojson...", self._browse_geojson
        )
        fl.addWidget(self.geojson_widget)

        self._toggle_loc()

        fl.addWidget(self._sep())

        lbl_buf = QLabel("Buffer et intersection")
        lbl_buf.setStyleSheet(
            "font-size:11px;font-weight:600;color:#1a1a1a;background:transparent;"
        )
        fl.addWidget(lbl_buf)

        br = QHBoxLayout()
        br.setSpacing(4)
        lbl_b = QLabel("Buffer :")
        lbl_b.setStyleSheet("font-size:11px;color:#333;background:transparent;")
        self.buffer_distance = QDoubleSpinBox()
        self.buffer_distance.setRange(1, 50000)
        self.buffer_distance.setValue(1000)
        self.buffer_distance.setDecimals(0)
        self.buffer_distance.setSingleStep(100)
        self.buffer_distance.setStyleSheet(STYLE_INPUT)
        self.buffer_distance.setFixedWidth(90)
        self.buffer_unit = QComboBox()
        self.buffer_unit.addItems(["metres", "km"])
        self.buffer_unit.setStyleSheet(STYLE_INPUT)
        self.buffer_unit.setFixedWidth(72)
        br.addWidget(lbl_b)
        br.addWidget(self.buffer_distance)
        br.addWidget(self.buffer_unit)
        br.addStretch()
        fl.addLayout(br)

        btn_calc = QPushButton("Lancer l'analyse")
        btn_calc.setStyleSheet(STYLE_BTN_PRIMARY)
        btn_calc.setFixedHeight(28)
        btn_calc.setFixedWidth(160)
        btn_calc.clicked.connect(self._afficher_et_calculer)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_calc)
        btn_row.addStretch()
        fl.addLayout(btn_row)
        fl.addStretch()

        row.addWidget(grp_form, 42)

        # ── Colonne droite : mini canvas + légende ─────────────
        grp_map = QGroupBox("Aperçu cartographique")
        grp_map.setStyleSheet(STYLE_CARD)
        ml = QVBoxLayout(grp_map)
        ml.setContentsMargins(5, 12, 5, 5)
        ml.setSpacing(3)

        self.mini_canvas = QgsMapCanvas()
        self.mini_canvas.setMinimumHeight(170)
        self.mini_canvas.enableAntiAliasing(True)
        self.mini_canvas.setCanvasColor(QColor("#B8D4E8"))
        self.mini_canvas.setDestinationCrs(
            self.canvas.mapSettings().destinationCrs()
        )
        ml.addWidget(self.mini_canvas)

        tool_row = QHBoxLayout()
        tool_row.setSpacing(3)
        ICON_BTNS = [
            ("✋",  "Déplacer (Pan)",  self._tool_pan,      28),
            ("🔍+", "Zoom avant",      self._tool_zoom_in,  36),
            ("🔍-", "Zoom arrière",    self._tool_zoom_out, 36),
            ("⛶",  "Étendue totale",  self._zoom_full,     28),
        ]
        for ico, tip, slot, w in ICON_BTNS:
            btn = QPushButton(ico)
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #D8D8D8;
                    border: 1px solid #C0C0C0;
                    border-radius: 3px;
                    font-size: 13px;
                    min-height: 22px;
                }
                QPushButton:hover { background-color: #2563EB; color: white; }
            """)
            btn.setFixedWidth(w)
            btn.setFixedHeight(22)
            btn.clicked.connect(slot)
            tool_row.addWidget(btn)
        tool_row.addStretch()
        ml.addLayout(tool_row)

        lbl_leg = QLabel("Légende :")
        lbl_leg.setStyleSheet(
            "font-size:10px;font-weight:600;color:#333;"
            "background:transparent;margin-top:3px;"
        )
        ml.addWidget(lbl_leg)

        self.legend_widget = LegendWidget()
        self.legend_widget.setStyleSheet(
            "background:#F0F0F0;border-radius:3px;font-size:9px;"
        )
        ml.addWidget(self.legend_widget)

        row.addWidget(grp_map, 58)
        layout.addLayout(row)

    # ── Helper widget fichier ───────────────────────────────────
    def _make_file_widget(self, label, attr, placeholder, slot):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size:12px;color:#333;background:transparent;")
        v.addWidget(lbl)
        h = QHBoxLayout()
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(STYLE_INPUT)
        setattr(self, attr, inp)
        btn = QPushButton("Parcourir...")
        btn.setStyleSheet(STYLE_BTN_SECONDARY)
        btn.setFixedWidth(90)
        btn.clicked.connect(slot)
        h.addWidget(inp)
        h.addWidget(btn)
        v.addLayout(h)
        return w

    def _sep(self):
        s = QFrame()
        s.setFrameShape(QFrame.HLine)
        s.setStyleSheet("background:#C8C8C8;max-height:1px;")
        return s

    # ══════════════════════════════════════════════════════════
    # ONGLET RASTER
    # ══════════════════════════════════════════════════════════

    def _build_raster_tab(self):
        layout = QVBoxLayout(self.raster_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from .sentinel2downloader_dialog import Sentinel2DownloaderDialog

        self._sentinel_widget = Sentinel2DownloaderDialog(self.iface)
        self._sentinel_widget.setWindowFlags(Qt.Widget)
        self._sentinel_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self._sentinel_widget)

    # ══════════════════════════════════════════════════════════
    # RÉSULTATS + FOOTER
    # ══════════════════════════════════════════════════════════

    def _build_resultats(self, parent):
        grp1 = QGroupBox("Résultats d'analyse — Couches terrain")
        grp1.setStyleSheet(STYLE_CARD)
        gl1 = QVBoxLayout(grp1)
        self.table_resultats = QTableWidget(0, 3)
        self.table_resultats.setHorizontalHeaderLabels([
            "Couche terrain",
            "Surface intersection (ha)",
            "Pourcentage (%)",
        ])
        self.table_resultats.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in [(1, 200), (2, 150)]:
            self.table_resultats.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table_resultats.setColumnWidth(col, w)
        self.table_resultats.setStyleSheet(STYLE_TABLE)
        self.table_resultats.setAlternatingRowColors(True)
        self.table_resultats.setMinimumHeight(110)
        gl1.addWidget(self.table_resultats)
        parent.addWidget(grp1)

        grp2 = QGroupBox("Dérogations existantes dans la zone d'étude")
        grp2.setStyleSheet(STYLE_CARD)
        gl2 = QVBoxLayout(grp2)
        self.table_derogation = QTableWidget(1, 3)
        self.table_derogation.setHorizontalHeaderLabels([
            "Projets dérogés dans Khémisset",
            "Nb projets dans zone tampon",
            "Distance du projet le plus proche",
        ])
        self.table_derogation.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in [(1, 200), (2, 260)]:
            self.table_derogation.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table_derogation.setColumnWidth(col, w)
        self.table_derogation.setStyleSheet(STYLE_TABLE)
        self.table_derogation.verticalHeader().setVisible(False)
        self.table_derogation.setFixedHeight(60)
        for col in range(3):
            it = QTableWidgetItem("—")
            it.setTextAlignment(Qt.AlignCenter)
            self.table_derogation.setItem(0, col, it)
        gl2.addWidget(self.table_derogation)
        parent.addWidget(grp2)

    def _build_footer(self, parent):
        fl = QHBoxLayout()
        fl.addStretch()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#555;font-size:12px;background:transparent;")
        fl.addWidget(self.lbl_status)
        fl.addStretch()

        self.btn_export = QPushButton("Exporter résultats (CSV)")
        self.btn_export.setStyleSheet(STYLE_BTN_SUCCESS)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(lambda: self._exporter('csv'))
        fl.addWidget(self.btn_export)

        self.btn_export_pdf = QPushButton("Exporter résultats (PDF)")
        self.btn_export_pdf.setStyleSheet(STYLE_BTN_SUCCESS)
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_pdf.clicked.connect(lambda: self._exporter('pdf'))
        fl.addWidget(self.btn_export_pdf)

        self.btn_reset = QPushButton("Réinitialiser")
        self.btn_reset.setStyleSheet(STYLE_BTN_RESET)
        self.btn_reset.setToolTip(
            "Efface tous les champs, supprime les rubber bands\n"
            "et remet le formulaire à zéro."
        )
        self.btn_reset.clicked.connect(self._reinitialiser)
        fl.addWidget(self.btn_reset)

        parent.addLayout(fl)

    # ══════════════════════════════════════════════════════════
    # OUTILS MINI CANVAS
    # ══════════════════════════════════════════════════════════

    def _tool_pan(self):
        self._tool_pan_obj = QgsMapToolPan(self.mini_canvas)
        self.mini_canvas.setMapTool(self._tool_pan_obj)

    def _tool_zoom_in(self):
        self._tool_zoom_in_obj = QgsMapToolZoom(self.mini_canvas, False)
        self.mini_canvas.setMapTool(self._tool_zoom_in_obj)

    def _tool_zoom_out(self):
        self._tool_zoom_out_obj = QgsMapToolZoom(self.mini_canvas, True)
        self.mini_canvas.setMapTool(self._tool_zoom_out_obj)

    def _zoom_full(self):
        self.mini_canvas.zoomToFullExtent()
        self.mini_canvas.refresh()
        self._tool_pan_obj = QgsMapToolPan(self.mini_canvas)
        self.mini_canvas.setMapTool(self._tool_pan_obj)

    # ══════════════════════════════════════════════════════════
    # CALCUL SURFACE EN TEMPS RÉEL
    # ══════════════════════════════════════════════════════════

    def _maj_surf_calc(self):
        r    = self.rayon_projet.value()
        surf = math.pi * r * r / 10000
        if surf >= 1.0:
            self.lbl_surf_calc.setStyleSheet(
                "font-size:11px;color:#1a1a1a;font-weight:600;background:transparent;"
            )
            self.lbl_surf_calc.setText(f"Surface : {surf:.4f} ha  ✓")
        else:
            self.lbl_surf_calc.setStyleSheet(
                "font-size:11px;color:#EF4444;font-weight:600;background:transparent;"
            )
            self.lbl_surf_calc.setText(f"Surface : {surf:.4f} ha  ✗ < 1 ha")

    # ══════════════════════════════════════════════════════════
    # TOGGLE LOCALISATION
    # ══════════════════════════════════════════════════════════

    def _toggle_loc(self):
        self.coords_widget.setVisible(self.rb_coords.isChecked())
        self.shp_widget.setVisible(self.rb_shp.isChecked())
        self.geojson_widget.setVisible(self.rb_geojson.isChecked())

    # ══════════════════════════════════════════════════════════
    # PARCOURIR FICHIERS
    # ══════════════════════════════════════════════════════════

    def _browse_shp(self):
        f, _ = QFileDialog.getOpenFileName(self, "Sélectionner SHP", "", "Shapefile (*.shp)")
        if f:
            self.shp_path.setText(f)
            layer = QgsVectorLayer(f, os.path.splitext(os.path.basename(f))[0], "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self._sync_mini_canvas()
                ext = layer.extent()
                if ext and not ext.isEmpty():
                    self.mini_canvas.setExtent(ext)
                self.mini_canvas.refresh()

    def _browse_geojson(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner GeoJSON", "", "GeoJSON (*.geojson *.json)"
        )
        if f:
            self.geojson_path.setText(f)
            layer = QgsVectorLayer(f, os.path.splitext(os.path.basename(f))[0], "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self._sync_mini_canvas()
                ext = layer.extent()
                if ext and not ext.isEmpty():
                    self.mini_canvas.setExtent(ext)
                self.mini_canvas.refresh()

    # ══════════════════════════════════════════════════════════
    # VALIDATION GÉOGRAPHIQUE
    # ══════════════════════════════════════════════════════════

    def _valider_point_maroc(self, x, y):
        """Vérifie que les coordonnées sont dans les limites du territoire marocain."""
        return (
            MAROC_XMIN <= x <= MAROC_XMAX and
            MAROC_YMIN <= y <= MAROC_YMAX
        )

    def _valider_zone_khmissat(self, geom_metre):
        """
        Vérifie que la géométrie (en EPSG:26191) intersecte au moins une
        feature des 6 couches terrain de la province de Khémissat.
        Retourne True si la géométrie est dans la zone, False sinon.
        Si aucune couche n'est chargée, retourne True (on ne bloque pas).
        """
        crs_metre = QgsCoordinateReferenceSystem("EPSG:26191")

        couches_terrain = [
            l for l in QgsProject.instance().mapLayers().values()
            if isinstance(l, QgsVectorLayer) and l.isValid()
            and self._est_couche_terrain(l)
        ]

        if not couches_terrain:
            return True  # Impossible de valider sans couches → on laisse passer

        for layer in couches_terrain:
            crs_layer = layer.crs()
            geom_test = QgsGeometry(geom_metre)
            if crs_layer != crs_metre:
                tr = QgsCoordinateTransform(crs_metre, crs_layer, QgsProject.instance())
                geom_test.transform(tr)
            for feat in layer.getFeatures():
                g = feat.geometry()
                if g and g.intersects(geom_test):
                    return True

        return False

    # ══════════════════════════════════════════════════════════
    # OBTENIR GÉOMÉTRIE PROJET
    # ══════════════════════════════════════════════════════════

    def _get_geometrie_projet(self):
        """
        Retourne (geometrie, surface_ha) en EPSG:26191.
        Applique successivement :
          1. Validation territoire marocain
          2. Validation surface >= 1 ha
          3. Validation zone Khémissat  ← NOUVEAU
        """
        crs_metre = QgsCoordinateReferenceSystem("EPSG:26191")

        # ── MODE COORDONNÉES ──────────────────────────────────
        if self.rb_coords.isChecked():
            x = self.x_coord.value()
            y = self.y_coord.value()
            r = self.rayon_projet.value()

            # 1. Validation territoire Maroc
            if not self._valider_point_maroc(x, y):
                QMessageBox.warning(
                    self,
                    "Coordonnées invalides",
                    f"Le point ({x:.0f}, {y:.0f}) ne se trouve pas\n"
                    f"dans le territoire marocain.\n\n"
                    f"Vérifiez vos coordonnées en EPSG:26191\n"
                    f"(Lambert Maroc Nord, unités = mètres).\n\n"
                    f"Plages valides :\n"
                    f"  X (Est)  : {MAROC_XMIN} — {MAROC_XMAX}\n"
                    f"  Y (Nord) : {MAROC_YMIN} — {MAROC_YMAX}"
                )
                return None, None

            # 2. Validation surface >= 1 ha
            surf_ha = math.pi * r * r / 10000
            if surf_ha < 1.0:
                QMessageBox.warning(
                    self,
                    "Surface insuffisante",
                    f"La surface du projet est {surf_ha:.4f} ha.\n\n"
                    f"Le projet doit avoir une surface ≥ 1 ha.\n"
                    f"Augmentez le rayon (actuellement {r:.0f} m).\n\n"
                    f"Rayon minimum pour 1 ha : ~56 m"
                )
                return None, None

            # 3. Validation zone Khémissat
            geom_pt   = QgsGeometry.fromPointXY(QgsPointXY(x, y))
            geom_circ = geom_pt.buffer(r, 64)

            if not self._valider_zone_khmissat(geom_circ):
                QMessageBox.warning(
                    self,
                    "Zone hors Khémissat",
                    f"Le point ({x:.0f}, {y:.0f}) n'appartient pas\n"
                    f"à la province de Khémissat.\n\n"
                    f"Ce plugin est dédié à l'analyse foncière\n"
                    f"de la province de Khémissat uniquement.\n\n"
                    f"Veuillez saisir des coordonnées situées\n"
                    f"dans la zone d'étude et réessayer."
                )
                return None, None

            return geom_pt, surf_ha

        # ── MODE FICHIER (SHP / GeoJSON) ──────────────────────
        for rb, attr in [(self.rb_shp, 'shp_path'), (self.rb_geojson, 'geojson_path')]:
            if rb.isChecked():
                chemin = getattr(self, attr).text().strip()
                if not chemin or not os.path.exists(chemin):
                    QMessageBox.warning(self, "Erreur", "Fichier introuvable.")
                    return None, None

                layer = QgsVectorLayer(chemin, "projet", "ogr")
                if not layer.isValid():
                    QMessageBox.warning(self, "Erreur", "Fichier invalide.")
                    return None, None

                geom      = next(layer.getFeatures()).geometry()
                crs_layer = layer.crs()

                # Reprojeter en EPSG:26191 pour calculs métriques
                geom_metre = QgsGeometry(geom)
                if crs_layer != crs_metre:
                    tr = QgsCoordinateTransform(crs_layer, crs_metre, QgsProject.instance())
                    geom_metre.transform(tr)

                # 1. Validation surface >= 1 ha
                surf_ha = geom_metre.area() / 10000
                if surf_ha < 1.0:
                    QMessageBox.warning(
                        self,
                        "Surface insuffisante",
                        f"La surface du polygone est {surf_ha:.4f} ha.\n\n"
                        f"Le projet doit avoir une surface ≥ 1 ha."
                    )
                    return None, None

                # 2. Validation zone Khémissat
                if not self._valider_zone_khmissat(geom_metre):
                    QMessageBox.warning(
                        self,
                        "Zone hors Khémissat",
                        f"Le fichier importé ne se trouve pas\n"
                        f"dans la province de Khémissat.\n\n"
                        f"Ce plugin est dédié à l'analyse foncière\n"
                        f"de la province de Khémissat uniquement.\n\n"
                        f"Veuillez importer un fichier situé\n"
                        f"dans la zone d'étude et réessayer."
                    )
                    return None, None

                return geom_metre, surf_ha

        return None, None

    # ══════════════════════════════════════════════════════════
    # RUBBER BANDS
    # ══════════════════════════════════════════════════════════

    def _supprimer_rubber_bands(self):
        for attr in ('rb_projet', 'rb_buffer', 'rb_mini_projet', 'rb_mini_buffer'):
            rb = getattr(self, attr, None)
            if rb is not None:
                rb.reset()
                try:
                    rb.hide()
                except Exception:
                    pass
            setattr(self, attr, None)

    # ══════════════════════════════════════════════════════════
    # RÉINITIALISER
    # ══════════════════════════════════════════════════════════

    def _reinitialiser(self):
        rep = QMessageBox.question(
            self,
            "Réinitialiser",
            "Voulez-vous vraiment effacer toutes les données saisies\n"
            "et remettre le formulaire à zéro ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if rep != QMessageBox.Yes:
            return

        self.nom_projet.clear()
        self.type_projet.setCurrentIndex(0)
        self.x_coord.setValue(500000.00)
        self.y_coord.setValue(300000.00)
        self.rayon_projet.setValue(60)
        self.shp_path.setText("")
        self.geojson_path.setText("")
        self.rb_coords.setChecked(True)
        self.buffer_distance.setValue(1000)
        self.buffer_unit.setCurrentIndex(0)

        self._supprimer_rubber_bands()
        self.canvas.refresh()
        self.mini_canvas.refresh()

        self.table_resultats.setRowCount(0)
        for col in range(3):
            it = QTableWidgetItem("—")
            it.setTextAlignment(Qt.AlignCenter)
            self.table_derogation.setItem(0, col, it)
        self.resultats = None

        self.btn_export.setEnabled(False)
        self.btn_export_pdf.setEnabled(False)
        self.lbl_status.setText("")

        self._sync_mini_canvas()

    # ══════════════════════════════════════════════════════════
    # AFFICHER + CALCULER
    # ══════════════════════════════════════════════════════════

    def _afficher_et_calculer(self):
        geom, surf_projet_ha = self._get_geometrie_projet()
        if not geom:
            return

        self._supprimer_rubber_bands()

        crs_dst   = self.canvas.mapSettings().destinationCrs()
        crs_metre = QgsCoordinateReferenceSystem("EPSG:26191")

        buf_m = self.buffer_distance.value()
        if self.buffer_unit.currentText() == "km":
            buf_m *= 1000

        buffer_metre = geom.buffer(buf_m, 64)

        geom_display   = QgsGeometry(geom)
        buffer_display = QgsGeometry(buffer_metre)
        if crs_dst != crs_metre:
            tr = QgsCoordinateTransform(crs_metre, crs_dst, QgsProject.instance())
            geom_display.transform(tr)
            buffer_display.transform(tr)

        self.rb_projet = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rb_projet.setColor(QColor(37, 99, 235, 200))
        self.rb_projet.setFillColor(QColor(37, 99, 235, 60))
        self.rb_projet.setWidth(2)
        self.rb_projet.setToGeometry(geom_display)

        self.rb_buffer = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rb_buffer.setColor(QColor(16, 185, 129, 200))
        self.rb_buffer.setFillColor(QColor(16, 185, 129, 30))
        self.rb_buffer.setWidth(1)
        self.rb_buffer.setToGeometry(buffer_display)

        self.canvas.setExtent(buffer_display.boundingBox())
        self.canvas.refresh()

        self._sync_mini_canvas(avec_projet=True)

        self.rb_mini_projet = QgsRubberBand(self.mini_canvas, QgsWkbTypes.PolygonGeometry)
        self.rb_mini_projet.setColor(QColor(37, 99, 235, 220))
        self.rb_mini_projet.setFillColor(QColor(37, 99, 235, 70))
        self.rb_mini_projet.setWidth(2)
        self.rb_mini_projet.setToGeometry(geom_display)

        self.rb_mini_buffer = QgsRubberBand(self.mini_canvas, QgsWkbTypes.PolygonGeometry)
        self.rb_mini_buffer.setColor(QColor(16, 185, 129, 200))
        self.rb_mini_buffer.setFillColor(QColor(16, 185, 129, 35))
        self.rb_mini_buffer.setWidth(1)
        self.rb_mini_buffer.setToGeometry(buffer_display)

        self.mini_canvas.setExtent(buffer_display.boundingBox())
        self.mini_canvas.refresh()

        couches_terrain = [
            l for l in QgsProject.instance().mapLayers().values()
            if isinstance(l, QgsVectorLayer) and l.isValid()
            and self._est_couche_terrain(l)
        ]

        if not couches_terrain:
            QMessageBox.warning(
                self, "Couches manquantes",
                "Aucune des 6 couches terrain n'est chargée dans QGIS.\n\n"
                "Chargez les fichiers SHP :\n"
                "  DOMIANE_PRIVE_ETAT, DOMAINE_PUBLIC,\n"
                "  DOMAINE_FORESTIER, DOMAINE_COMMUNAL,\n"
                "  Derogation_central_13_avril, COLLECTIF"
            )
            self.lbl_status.setText("Buffer affiché — couches terrain introuvables")
            return

        self.resultats = []
        total_ha = 0.0

        for layer in couches_terrain:
            est_derog   = self._est_derogation(layer)
            nom_affiche = self._nom_affiche(layer)
            crs_layer   = layer.crs()

            if crs_layer != crs_metre:
                tr = QgsCoordinateTransform(crs_metre, crs_layer, QgsProject.instance())
                buf_repr = QgsGeometry(buffer_metre)
                buf_repr.transform(tr)
            else:
                buf_repr = buffer_metre

            if est_derog:
                nb_total   = layer.featureCount()
                nb_projets = 0
                dist_min   = None

                for feat in layer.getFeatures():
                    g = feat.geometry()
                    if not g:
                        continue
                    if g.intersects(buf_repr):
                        nb_projets += 1
                    centroide_proj  = geom.centroid()
                    centroide_derog = g.centroid()
                    if centroide_proj and centroide_derog:
                        c_derog = QgsGeometry(centroide_derog)
                        if crs_layer != crs_metre:
                            tr_d = QgsCoordinateTransform(
                                crs_layer, crs_metre, QgsProject.instance()
                            )
                            c_derog.transform(tr_d)
                        d = centroide_proj.distance(c_derog)
                        if dist_min is None or d < dist_min:
                            dist_min = d

                dist_txt = "Il n'existe pas" if (dist_min is None or nb_projets == 0) else f"{dist_min:.0f} m"

                self.resultats.append({
                    'nom':        nom_affiche,
                    'surface_ha': 0.0,
                    'part':       None,
                    'est_derog':  True,
                    'nb_total':   nb_total,
                    'nb_projets': nb_projets,
                    'dist_txt':   dist_txt,
                })

            else:
                surf_ha = 0.0
                for feat in layer.getFeatures():
                    g = feat.geometry()
                    if g and g.intersects(buf_repr):
                        inter = g.intersection(buf_repr)
                        if inter and not inter.isEmpty():
                            surf_ha += inter.area() / 10000
                total_ha += surf_ha
                self.resultats.append({
                    'nom':        nom_affiche,
                    'surface_ha': surf_ha,
                    'part':       0.0,
                    'est_derog':  False,
                    'nb_projets': None,
                    'dist_txt':   None,
                })

        for r in self.resultats:
            if not r['est_derog']:
                r['part'] = (r['surface_ha'] / total_ha * 100) if total_ha > 0 else 0.0

        self._afficher_resultats_table()
        self.btn_export.setEnabled(True)
        self.btn_export_pdf.setEnabled(True)
        self.lbl_status.setText(
            f"Buffer affiché — {len(self.resultats)} couche(s) analysée(s)"
        )

    # ══════════════════════════════════════════════════════════
    # TABLEAU RÉSULTATS
    # ══════════════════════════════════════════════════════════

    def _afficher_resultats_table(self):
        lignes_terrain = [r for r in self.resultats if not r['est_derog']]
        self.table_resultats.setRowCount(len(lignes_terrain))
        for i, res in enumerate(lignes_terrain):
            it0 = QTableWidgetItem(res['nom'])
            it1 = QTableWidgetItem(f"{res['surface_ha']:.4f} ha")
            it2 = QTableWidgetItem(f"{res['part']:.1f} %")
            it1.setTextAlignment(Qt.AlignCenter)
            it2.setTextAlignment(Qt.AlignCenter)
            if res['part'] > 50:
                it2.setForeground(QColor("#EF4444"))
            elif res['part'] > 20:
                it2.setForeground(QColor("#F59E0B"))
            else:
                it2.setForeground(QColor("#1a1a1a"))
            self.table_resultats.setItem(i, 0, it0)
            self.table_resultats.setItem(i, 1, it1)
            self.table_resultats.setItem(i, 2, it2)
        self.table_resultats.resizeRowsToContents()

        derog = next((r for r in self.resultats if r['est_derog']), None)
        if derog:
            it0 = QTableWidgetItem(str(derog.get('nb_total', '—')))
            it1 = QTableWidgetItem(str(derog['nb_projets']))
            it2 = QTableWidgetItem(derog['dist_txt'])
            for it in (it0, it1, it2):
                it.setTextAlignment(Qt.AlignCenter)
                it.setForeground(QColor("#D97706"))
            self.table_derogation.setItem(0, 0, it0)
            self.table_derogation.setItem(0, 1, it1)
            self.table_derogation.setItem(0, 2, it2)

    # ══════════════════════════════════════════════════════════
    # EXPORT CSV + PDF
    # ══════════════════════════════════════════════════════════

    def _exporter(self, fmt):
        if not self.resultats:
            QMessageBox.warning(self, "Pas de résultats", "Lancez d'abord l'analyse.")
            return
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        if fmt == 'csv':
            chemin, _ = QFileDialog.getSaveFileName(
                self, "Exporter CSV", f"resultats_{ts}.csv", "CSV (*.csv)"
            )
            if not chemin:
                return
            try:
                with open(chemin, 'w', encoding='utf-8-sig') as f:
                    f.write("Couche;Surface_intersection_ha;Pourcentage;Nb_projets_deroges;Distance_plus_proche;Date_export\n")
                    for r in self.resultats:
                        if r['est_derog']:
                            f.write(f"{r['nom']};;;{r['nb_projets']};{r['dist_txt']};{ts}\n")
                        else:
                            f.write(f"{r['nom']};{r['surface_ha']:.4f};{r['part']:.1f};;;{ts}\n")
                QMessageBox.information(self, "Export réussi", f"Fichier CSV :\n{chemin}")
            except Exception as e:
                QMessageBox.critical(self, "Erreur export CSV", str(e))

        elif fmt == 'pdf':
            chemin, _ = QFileDialog.getSaveFileName(
                self, "Exporter PDF", f"rapport_{ts}.pdf", "PDF (*.pdf)"
            )
            if not chemin:
                return
            self._exporter_pdf(chemin)

    def _exporter_pdf(self, chemin):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer,
                Table, TableStyle, HRFlowable, PageBreak, Image
            )
        except ImportError:
            QMessageBox.critical(
                self, "Module manquant",
                "Installez reportlab dans la console Python QGIS :\n\n"
                "import subprocess, sys\n"
                "subprocess.check_call(\n"
                "    [sys.executable, '-m', 'pip', 'install', 'reportlab']\n"
                ")"
            )
            return

        noir       = colors.HexColor('#1a1a1a')
        gris_fonce = colors.HexColor('#444444')
        gris_moyen = colors.HexColor('#888888')
        gris_clair = colors.HexColor('#D0D0D0')
        gris_bg    = colors.HexColor('#F0F0F0')
        blanc      = colors.white

        date = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

        doc = SimpleDocTemplate(
            chemin, pagesize=A4,
            topMargin=1.8*cm, bottomMargin=1.8*cm,
            leftMargin=2.5*cm, rightMargin=2.5*cm
        )

        s_etablissement = ParagraphStyle('etab',
            fontSize=9, textColor=gris_moyen, alignment=1, spaceAfter=1, fontName='Helvetica')
        s_filiere = ParagraphStyle('fil',
            fontSize=10, textColor=gris_fonce, alignment=1, spaceAfter=2, fontName='Helvetica-Bold')
        s_fst = ParagraphStyle('fst',
            fontSize=9, textColor=gris_moyen, alignment=1, spaceAfter=8, fontName='Helvetica')
        s_titre = ParagraphStyle('tit',
            fontSize=15, textColor=noir, spaceAfter=2, alignment=1, fontName='Helvetica-Bold')
        s_h1 = ParagraphStyle('h1',
            fontSize=11, textColor=noir, spaceBefore=12, spaceAfter=5, fontName='Helvetica-Bold')
        s_info = ParagraphStyle('info',
            fontSize=10, textColor=gris_fonce, spaceAfter=3, leftIndent=10, fontName='Helvetica')
        s_realise = ParagraphStyle('real',
            fontSize=9, textColor=gris_fonce, spaceAfter=2, alignment=1, fontName='Helvetica-Oblique')
        s_legende = ParagraphStyle('leg',
            fontSize=8, textColor=gris_fonce, alignment=1, spaceAfter=2, fontName='Helvetica')

        def tbl_terrain():
            return TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0), gris_fonce),
                ('TEXTCOLOR',     (0, 0), (-1, 0), blanc),
                ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0), (-1,-1), 9),
                ('ROWBACKGROUNDS',(0, 1), (-1,-1), [blanc, gris_bg]),
                ('GRID',          (0, 0), (-1,-1), 0.4, gris_clair),
                ('ALIGN',         (1, 0), (-1,-1), 'CENTER'),
                ('LEFTPADDING',   (0, 0), (-1,-1), 7),
                ('RIGHTPADDING',  (0, 0), (-1,-1), 7),
                ('TOPPADDING',    (0, 0), (-1,-1), 4),
                ('BOTTOMPADDING', (0, 0), (-1,-1), 4),
            ])

        def tbl_derog():
            return TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0), colors.HexColor('#888888')),
                ('TEXTCOLOR',     (0, 0), (-1, 0), blanc),
                ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0), (-1,-1), 9),
                ('ROWBACKGROUNDS',(0, 1), (-1,-1), [blanc]),
                ('GRID',          (0, 0), (-1,-1), 0.4, gris_clair),
                ('ALIGN',         (0, 0), (-1,-1), 'CENTER'),
                ('LEFTPADDING',   (0, 0), (-1,-1), 7),
                ('RIGHTPADDING',  (0, 0), (-1,-1), 7),
                ('TOPPADDING',    (0, 0), (-1,-1), 4),
                ('BOTTOMPADDING', (0, 0), (-1,-1), 4),
            ])

        nom            = self.nom_projet.text().strip() or 'Non renseigné'
        lignes_terrain = [r for r in self.resultats if not r['est_derog']]
        derog          = next((r for r in self.resultats if r['est_derog']), None)
        crs_metre      = QgsCoordinateReferenceSystem("EPSG:26191")

        if self.rb_coords.isChecked():
            r_val  = self.rayon_projet.value()
            surf_p = f"{math.pi * r_val * r_val / 10000:.4f} ha"
        else:
            surf_p = f"{lignes_terrain[0]['surface_ha']:.4f} ha" if lignes_terrain else '—'

        # ── Génération carte matplotlib ──────────────────────────
        carte_path = None
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            from matplotlib.patches import Polygon as MplPolygon
            import numpy as np
            import tempfile

            fig, ax = plt.subplots(figsize=(16, 14), dpi=150)
            ax.set_facecolor('#B8D4E8')
            fig.patch.set_facecolor('#FFFFFF')

            COUL_CARTE = {
                'domiane_prive_etat': ('#C0392B', '#C0392B', 0.35),
                'domaine_public':     ('#2980B9', '#2980B9', 0.35),
                'domaine_forestier':  ('#27AE60', '#27AE60', 0.35),
                'domaine_communal':   ('#E67E22', '#E67E22', 0.35),
                'derogation_central': ('#F39C12', '#F39C12', 0.50),
                'collectif':          ('#8E44AD', '#8E44AD', 0.35),
            }

            def _hex_to_rgba(hex_color, alpha=0.35):
                h = hex_color.lstrip('#')
                r, g, b = tuple(int(h[i:i+2], 16)/255 for i in (0, 2, 4))
                return (r, g, b, alpha)

            def _qgs_geom_to_mpl_coords(geom):
                coords_list = []
                wkt = geom.asWkt()
                if not wkt:
                    return coords_list
                import re
                rings = re.findall(r'\(([^()]+)\)', wkt)
                for ring in rings:
                    pts = []
                    for pair in ring.strip().split(','):
                        vals = pair.strip().split()
                        if len(vals) >= 2:
                            try:
                                pts.append((float(vals[0]), float(vals[1])))
                            except ValueError:
                                pass
                    if pts:
                        coords_list.append(np.array(pts))
                return coords_list

            legend_patches = []
            all_x, all_y   = [], []

            couches_terrain = [
                l for l in QgsProject.instance().mapLayers().values()
                if isinstance(l, QgsVectorLayer) and l.isValid()
                and self._est_couche_terrain(l)
            ]

            for layer in couches_terrain:
                nom_lower = layer.name().lower().replace(' ', '_').replace('-', '_')
                cle_trouvee = None
                for cle in COUL_CARTE:
                    if cle in nom_lower:
                        cle_trouvee = cle
                        break
                edge_col, face_col, alpha_val = (
                    COUL_CARTE[cle_trouvee] if cle_trouvee else ('#888888', '#888888', 0.3)
                )
                face_rgba   = _hex_to_rgba(face_col, alpha_val)
                nom_affiche = self._nom_affiche(layer)
                crs_layer   = layer.crs()

                for feat in layer.getFeatures():
                    g = feat.geometry()
                    if not g or g.isEmpty():
                        continue
                    geom_m = QgsGeometry(g)
                    if crs_layer != crs_metre:
                        tr = QgsCoordinateTransform(crs_layer, crs_metre, QgsProject.instance())
                        geom_m.transform(tr)
                    for coords in _qgs_geom_to_mpl_coords(geom_m):
                        if len(coords) < 3:
                            continue
                        ax.add_patch(MplPolygon(coords, closed=True,
                            facecolor=face_rgba, edgecolor=edge_col,
                            linewidth=0.5, zorder=2))
                        all_x.extend(coords[:, 0])
                        all_y.extend(coords[:, 1])

                legend_patches.append(mpatches.Patch(
                    facecolor=_hex_to_rgba(face_col, 0.6),
                    edgecolor=edge_col, linewidth=0.8, label=nom_affiche
                ))

            # Buffer & zone projet
            if self.rb_coords.isChecked():
                x_proj = self.x_coord.value()
                y_proj = self.y_coord.value()
                r_proj = self.rayon_projet.value()
                buf_m  = self.buffer_distance.value()
                if self.buffer_unit.currentText() == "km":
                    buf_m *= 1000
                pt_geom   = QgsGeometry.fromPointXY(QgsPointXY(x_proj, y_proj))
                proj_geom = pt_geom.buffer(r_proj, 64)
                buff_geom = pt_geom.buffer(r_proj + buf_m, 64)
            else:
                geom_base, _ = self._get_geometrie_projet()
                if geom_base:
                    buf_m = self.buffer_distance.value()
                    if self.buffer_unit.currentText() == "km":
                        buf_m *= 1000
                    proj_geom = geom_base
                    buff_geom = geom_base.buffer(buf_m, 64)
                else:
                    proj_geom = buff_geom = None

            if buff_geom:
                for coords in _qgs_geom_to_mpl_coords(buff_geom):
                    if len(coords) < 3:
                        continue
                    ax.add_patch(MplPolygon(coords, closed=True,
                        facecolor=(0.06, 0.73, 0.50, 0.12), edgecolor='#10B981',
                        linewidth=1.8, linestyle='--', zorder=3))
                    all_x.extend(coords[:, 0])
                    all_y.extend(coords[:, 1])
                legend_patches.append(mpatches.Patch(
                    facecolor=(0.06, 0.73, 0.50, 0.25), edgecolor='#10B981',
                    linewidth=1.5, linestyle='--', label='Zone tampon (buffer)'
                ))

            if proj_geom:
                for coords in _qgs_geom_to_mpl_coords(proj_geom):
                    if len(coords) < 3:
                        continue
                    ax.add_patch(MplPolygon(coords, closed=True,
                        facecolor=(0.15, 0.39, 0.92, 0.30), edgecolor='#2563EB',
                        linewidth=2.0, zorder=4))
                legend_patches.append(mpatches.Patch(
                    facecolor=(0.15, 0.39, 0.92, 0.40), edgecolor='#2563EB',
                    linewidth=2.0, label='Zone projet'
                ))

            # Intersections en surbrillance
            for res in lignes_terrain:
                if res['surface_ha'] <= 0:
                    continue
                nom_lower_res = (res['nom'].lower()
                    .replace(' ', '_').replace("'", '_')
                    .replace('é', 'e').replace('ê', 'e'))
                layer_found = None
                for layer in couches_terrain:
                    if (self._nom_affiche(layer).lower()
                            .replace(' ', '_').replace("'", '_')
                            .replace('é', 'e').replace('ê', 'e') == nom_lower_res):
                        layer_found = layer
                        break
                if not layer_found:
                    continue

                crs_layer = layer_found.crs()
                if self.rb_coords.isChecked():
                    bm = self.buffer_distance.value()
                    if self.buffer_unit.currentText() == "km":
                        bm *= 1000
                    xp = self.x_coord.value()
                    yp = self.y_coord.value()
                    rp = self.rayon_projet.value()
                    buf_repr_calc = QgsGeometry.fromPointXY(QgsPointXY(xp, yp)).buffer(rp + bm, 64)
                else:
                    buf_repr_calc = buff_geom if buff_geom else None

                if buf_repr_calc is None:
                    continue

                buf_in_layer = QgsGeometry(buf_repr_calc)
                if crs_layer != crs_metre:
                    tr_back = QgsCoordinateTransform(crs_metre, crs_layer, QgsProject.instance())
                    buf_in_layer.transform(tr_back)

                for feat in layer_found.getFeatures():
                    g = feat.geometry()
                    if not g or not g.intersects(buf_in_layer):
                        continue
                    inter = g.intersection(buf_in_layer)
                    if not inter or inter.isEmpty():
                        continue
                    inter_m = QgsGeometry(inter)
                    if crs_layer != crs_metre:
                        tr2 = QgsCoordinateTransform(crs_layer, crs_metre, QgsProject.instance())
                        inter_m.transform(tr2)
                    for coords in _qgs_geom_to_mpl_coords(inter_m):
                        if len(coords) < 3:
                            continue
                        ax.add_patch(MplPolygon(coords, closed=True,
                            facecolor=(1.0, 0.2, 0.2, 0.55), edgecolor='#CC0000',
                            linewidth=1.0, zorder=5))

            legend_patches.append(mpatches.Patch(
                facecolor=(1.0, 0.2, 0.2, 0.55), edgecolor='#CC0000',
                linewidth=1.0, label="Zone d'intersection"
            ))

            if all_x and all_y:
                mx = (max(all_x) - min(all_x)) * 0.05 or 1000
                my = (max(all_y) - min(all_y)) * 0.05 or 1000
                ax.set_xlim(min(all_x) - mx, max(all_x) + mx)
                ax.set_ylim(min(all_y) - my, max(all_y) + my)

            ax.set_xlabel("X — Lambert Maroc Nord (m)", fontsize=9, color='#444')
            ax.set_ylabel("Y — Lambert Maroc Nord (m)", fontsize=9, color='#444')
            ax.tick_params(labelsize=7, colors='#666')
            ax.grid(True, linestyle='--', linewidth=0.3, color='#AAAAAA', alpha=0.6)
            ax.set_aspect('equal', adjustable='datalim')
            ax.set_title(
                f"Carte des zones d'intersection — Projet : {nom}",
                fontsize=12, fontweight='bold', color='#1a1a1a', pad=10
            )

            leg = ax.legend(handles=legend_patches, loc='lower left', fontsize=7,
                framealpha=0.92, edgecolor='#CCCCCC', fancybox=True,
                title='Légende', title_fontsize=8)
            leg.get_frame().set_linewidth(0.5)

            ax.annotate('N',  xy=(0.97, 0.97), xycoords='axes fraction',
                fontsize=14, fontweight='bold', color='#1a1a1a', ha='center', va='top')
            ax.annotate('↑',  xy=(0.97, 0.94), xycoords='axes fraction',
                fontsize=18, color='#1a1a1a', ha='center', va='top')

            xlim      = ax.get_xlim()
            scale_len = (xlim[1] - xlim[0]) * 0.15
            scale_x0  = xlim[0] + (xlim[1] - xlim[0]) * 0.05
            scale_y   = ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.03
            ax.plot([scale_x0, scale_x0 + scale_len], [scale_y, scale_y], 'k-', linewidth=2)
            ax.plot([scale_x0, scale_x0], [scale_y - 200, scale_y + 200], 'k-', linewidth=1.5)
            ax.plot([scale_x0 + scale_len]*2, [scale_y - 200, scale_y + 200], 'k-', linewidth=1.5)
            ax.text(scale_x0 + scale_len / 2, scale_y + 400,
                f'{scale_len/1000:.1f} km', ha='center', va='bottom', fontsize=7, color='#1a1a1a')

            plt.tight_layout()
            tmp        = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            carte_path = tmp.name
            tmp.close()
            fig.savefig(carte_path, dpi=150, bbox_inches='tight', facecolor='white', format='png')
            plt.close(fig)

        except Exception:
            carte_path = None
            import traceback
            traceback.print_exc()

        # ── Construction document PDF ────────────────────────────
        elems = []

        elems += [
            Paragraph("Royaume du Maroc", s_etablissement),
            Paragraph("Cycle Ingénieur — Géoinformation", s_filiere),
            Paragraph("Faculté des Sciences et Techniques de Tanger", s_fst),
            HRFlowable(width="100%", thickness=0.8, color=gris_clair),
            Spacer(1, 6),
            Paragraph("Rapport d'Analyse — Dérogation Urbanistique", s_titre),
            Spacer(1, 8),
            Paragraph("Informations du projet", s_h1),
            Paragraph(f"&#8226;  Nom du projet : <b>{nom}</b>", s_info),
            Paragraph(f"&#8226;  Surface du projet : <b>{surf_p}</b>", s_info),
            Spacer(1, 10),
        ]

        elems.append(Paragraph("Résultats d'analyse — Couches terrain", s_h1))
        data_t = [['Couche terrain', 'Surface intersection (ha)', 'Pourcentage (%)']]
        for r in lignes_terrain:
            data_t.append([r['nom'], f"{r['surface_ha']:.4f} ha", f"{r['part']:.1f} %"])
        t1 = Table(data_t, colWidths=[8*cm, 5*cm, 3.5*cm])
        t1.setStyle(tbl_terrain())
        elems += [t1, Spacer(1, 12)]

        elems.append(Paragraph("Dérogations existantes dans la zone d'étude", s_h1))
        if derog:
            data_d = [
                ['Projets dérogés à Khémisset', 'Nb projets dans zone tampon',
                 'Distance du projet le plus proche'],
                [str(derog.get('nb_total', '—')), str(derog['nb_projets']), derog['dist_txt']]
            ]
        else:
            data_d = [
                ['Projets dérogés à Khémisset', 'Nb projets dans zone tampon',
                 'Distance du projet le plus proche'],
                ['—', '—', '—']
            ]
        t2 = Table(data_d, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
        t2.setStyle(tbl_derog())
        elems += [t2, Spacer(1, 20)]

        footer_style = ParagraphStyle('ft', fontSize=8, textColor=gris_moyen,
            alignment=1, fontName='Helvetica-Oblique')
        elems += [
            HRFlowable(width="100%", thickness=0.5, color=gris_clair),
            Spacer(1, 8),
            Paragraph("Réalisé par :", s_realise),
            Paragraph(
                "Makhloufi Ouiam &nbsp;&nbsp;|&nbsp;&nbsp; "
                "Boujbel Boutaine &nbsp;&nbsp;|&nbsp;&nbsp; "
                "El Khlifi Oumaima", s_realise
            ),
            Spacer(1, 4),
            Paragraph(f"Plugin de dérogation urbanistique — {date}", footer_style),
            PageBreak(),
        ]

        elems += [
            Paragraph("Royaume du Maroc", s_etablissement),
            Paragraph("Cycle Ingénieur — Géoinformation", s_filiere),
            Paragraph("Faculté des Sciences et Techniques de Tanger", s_fst),
            HRFlowable(width="100%", thickness=0.8, color=gris_clair),
            Spacer(1, 6),
            Paragraph("Carte des Zones d'Intersection — Résultats d'Analyse", s_titre),
            Spacer(1, 10),
        ]

        if carte_path and os.path.exists(carte_path):
            elems.append(Image(carte_path, width=16.2*cm, height=14*cm))
            elems.append(Spacer(1, 6))
            elems.append(Paragraph(
                f"Figure : Carte des zones d'intersection du projet «&nbsp;{nom}&nbsp;» "
                f"— Projection : Lambert Maroc Nord — EPSG:26191.",
                s_legende
            ))
        else:
            elems.append(Paragraph(
                "⚠ La carte n'a pas pu être générée (matplotlib requis).\n"
                "Installez matplotlib : pip install matplotlib",
                ParagraphStyle('warn', fontSize=10,
                    textColor=colors.HexColor('#DC2626'), alignment=1, fontName='Helvetica')
            ))

        footer_style2 = ParagraphStyle('ft2', fontSize=8, textColor=gris_moyen,
            alignment=1, fontName='Helvetica-Oblique')
        elems += [
            HRFlowable(width="100%", thickness=0.5, color=gris_clair),
            Spacer(1, 8),
            Paragraph("Réalisé par :", s_realise),
            Paragraph(
                "Makhloufi Ouiam &nbsp;&nbsp;|&nbsp;&nbsp; "
                "Boujbel Boutaine &nbsp;&nbsp;|&nbsp;&nbsp; "
                "El Khlifi Oumaima", s_realise
            ),
            Spacer(1, 4),
            Paragraph(f"Plugin de dérogation urbanistique — {date}", footer_style2),
        ]

        try:
            doc.build(elems)
            if carte_path and os.path.exists(carte_path):
                try:
                    os.unlink(carte_path)
                except Exception:
                    pass
            QMessageBox.information(self, "Export réussi", f"Rapport PDF (2 pages) :\n{chemin}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur PDF", str(e))