# -*- coding: utf-8 -*-
"""
derogation_plugin.py
Fichier principal du plugin généré par Plugin Builder.
Gère : initialisation, bouton dans la barre QGIS, menu, ouverture du dialogue.
"""

import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon


class DerogationPlugin:
    """Classe principale du plugin — instanciée par QGIS via classFactory."""

    def __init__(self, iface):
        """
        :param iface: QgisInterface fourni automatiquement par QGIS
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = "Dérogation & Raster Sentinel"
        self.toolbar = self.iface.addToolBar("Dérogation & Raster Sentinel")
        self.toolbar.setObjectName("DerogationUrbanistique")
        self.dialog = None  # sera créé au premier clic

    # ------------------------------------------------------------------
    #  Méthodes obligatoires Plugin Builder
    # ------------------------------------------------------------------

    def initGui(self):
        """
        Appelé par QGIS à l'activation du plugin.
        Crée le bouton dans la barre d'outils et l'entrée dans le menu.
        """
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        action = QAction(
            icon,
            "Dérogation & Raster Sentinel",
            self.iface.mainWindow()
        )
        action.setToolTip(
            "Ouvrir le plugin d'aide à la décision pour les dérogations urbanistiques"
        )
        action.triggered.connect(self.run)

        # Ajouter à la barre d'outils QGIS
        self.toolbar.addAction(action)

        # Ajouter au menu Extensions
        self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

    def unload(self):
        """
        Appelé par QGIS à la désactivation du plugin.
        Supprime le bouton et l'entrée du menu.
        """
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        # Supprimer la barre d'outils
        del self.toolbar

    # ------------------------------------------------------------------
    #  Action principale
    # ------------------------------------------------------------------

    def run(self):
        """
        Appelé quand l'utilisateur clique sur le bouton.
        Ouvre (ou ramène au premier plan) la fenêtre du plugin.
        """
        # Créer le dialogue une seule fois (singleton)
        if self.dialog is None:
            from .derogation_plugin_dialog import DerogationPluginDialog
            self.dialog = DerogationPluginDialog(self.iface)

        # Afficher et mettre au premier plan
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
