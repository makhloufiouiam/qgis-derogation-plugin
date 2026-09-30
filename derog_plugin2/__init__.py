# -*- coding: utf-8 -*-
"""
Plugin Builder __init__.py
Ce fichier est le point d'entrée obligatoire pour QGIS.
Ne pas modifier la fonction classFactory.
"""

def classFactory(iface):
    """
    Appelé automatiquement par QGIS au chargement du plugin.
    :param iface: QgisInterface — interface QGIS injectée automatiquement
    """
    from .derogation_plugin import DerogationPlugin
    return DerogationPlugin(iface)
