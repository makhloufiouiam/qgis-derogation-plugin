# Plugin QGIS : Aide à la décision pour les dérogations d'urbanisme
# QGIS Plugin: Decision Support for Planning Derogations

![QGIS](https://img.shields.io/badge/QGIS-3.x-green) ![Python](https://img.shields.io/badge/Python-3.x-blue)

## Contexte
Une dérogation (« kharq ») est une autorisation exceptionnelle accordée pour un projet
qui ne respecte pas totalement le plan d'aménagement. Leur multiplication dégrade la
cohérence du plan. Ce plugin aide à décider objectivement de leur acceptation.

*A derogation is an exceptional authorization for a project that does not fully comply with
the zoning plan. This plugin provides an objective, criteria-based decision.*

## Fonctionnalités
**Onglet Dérogation**
- Localisation par coordonnées (EPSG:26191), Shapefile ou GeoJSON
- Zone tampon paramétrable (1 km par défaut)
- Intersection avec les types de foncier, les espaces verts et les dérogations existantes
- Indicateurs : % par type de terrain, nombre de projets voisins, distance au plus proche
- Critères : surface ≥ 1 ha, aucun empiètement sur les espaces verts, distance minimale entre projets
- Export CSV et PDF

**Onglet Raster**
- Sentinel-2 (NDVI, NDWI, NDBI, NDMI) et Sentinel-1 (RVI, VV/VH, NDPI, DPSVI)
- Intervalle de dates, cadre centre + buffer, filtre de nuages

## Installation
1. Télécharger `derog_plugin2.zip` depuis **Releases**
2. QGIS → *Extensions* → *Installer/Gérer les extensions* → *Installer depuis un ZIP*
3. Activer « Dérogation & Raster Sentinel »

## Données requises
Couches foncières (privé, public, forestier, communal, collectif), plan d'aménagement,
dérogations existantes.

## Structure
```
derog_plugin2/
├── __init__.py
├── derogation_plugin.py
├── derogation_plugin_dialog.py
├── sentinel2downloader_dialog.py
├── derogation_plugin_dialog_base.ui
├── metadata.txt
└── icon.png
```



## Auteurs
Makhloufi Ouiam, FST Tanger, Géoinformation, 2025/2026.

