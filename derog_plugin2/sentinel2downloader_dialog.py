# -*- coding: utf-8 -*-
"""
Sentinel Downloader — via CDSE Sentinel Hub Processing API
- Intervalle de dates + cadre (lat, lon, buffer km)
- Téléchargement direct découpé sur l'AOI (quelques Mo seulement)
- Une couche QGIS par jour trouvé
"""
import io
import os
import glob
import re
import shutil
import struct
import tempfile
import time
import zipfile
import datetime
import numpy as np
from qgis.PyQt.QtCore import QDate, QVariant, QSettings, Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDateEdit,
    QGroupBox,
    QMessageBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QFileDialog,
    QScrollArea,
    QFrame,
)
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsMessageLog,
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsFields,
    QgsSingleSymbolRenderer,
    QgsFillSymbol,
    QgsContrastEnhancement,
    QgsRasterMinMaxOrigin,
    QgsSingleBandGrayRenderer,
)
from osgeo import gdal, osr

CDSE_CATALOGUE_URL = 'https://catalogue.dataspace.copernicus.eu/odata/v1'
CDSE_DOWNLOAD_URL = 'https://download.dataspace.copernicus.eu/odata/v1'
CDSE_TOKEN_URL = (
    'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
)
CDSE_CLIENT_ID = 'cdse-public'

# Sentinel Hub Processing API (CDSE)
SH_TOKEN_URL    = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
SH_PROCESS_URL  = 'https://sh.dataspace.copernicus.eu/api/v1/process'

CADRE_LAYER_NAME = 'Cadre de la zone'
SENTINEL2_BANDS = ('B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B11', 'B12')
REQUEST_TIMEOUT = (30, 120)
DOWNLOAD_TIMEOUT = (30, 1800)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class ConfirmDownloadDialog(QDialog):
    """Popup simple — liste les images trouvées par date avec leurs tuiles."""

    def __init__(self, days_data, product_type, parent=None):
        super().__init__(parent)
        self.days_data = days_data
        self.product_type = product_type
        self.selected_labels = []
        self.date_checkboxes = {}
        is_radar = product_type == 'radar'
        self.setWindowTitle(
            'Images Radar trouvées' if is_radar else 'Images Satellite trouvées'
        )
        self.setMinimumWidth(480)
        self.setMinimumHeight(320)
        self._build_ui()

    def _build_ui(self):
        is_radar = self.product_type == 'radar'
        total_days = len(self.days_data)

        root = QVBoxLayout()
        root.setSpacing(8)
        root.setContentsMargins(16, 16, 16, 16)

        satellite = 'Sentinel-1 (Radar)' if is_radar else 'Sentinel-2 (Optique)'
        title = QLabel(f'<b>{satellite}</b> — {total_days} date(s) trouvée(s)')
        title.setStyleSheet('font-size: 13px; margin-bottom: 4px;')
        root.addWidget(title)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel('Sélection :'))
        select_row.addStretch()
        self.select_all_check = QCheckBox('Sélectionner tout')
        self.select_all_check.setChecked(True)
        self.select_all_check.stateChanged.connect(self._on_select_all_changed)
        select_row.addWidget(self.select_all_check)
        root.addLayout(select_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setSpacing(6)
        cards_layout.setContentsMargins(0, 0, 0, 0)

        for acq_label in sorted(self.days_data.keys()):
            products = self.days_data[acq_label]

            card = QFrame()
            card.setStyleSheet(
                'QFrame { background: #f4f8ff; border: 1px solid #c0d0e8;'
                ' border-radius: 6px; padding: 6px; }'
            )
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(3)
            card_layout.setContentsMargins(8, 6, 8, 6)

            header = QHBoxLayout()
            date_lbl = QLabel(f'<b>{acq_label}</b>')
            date_lbl.setStyleSheet('font-size: 12px; border: none; background: transparent;')
            header.addWidget(date_lbl)
            header.addStretch()
            checkbox = QCheckBox('Sélectionner')
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._on_date_checkbox_toggled)
            header.addWidget(checkbox)
            card_layout.addLayout(header)
            self.date_checkboxes[acq_label] = checkbox

            if is_radar:
                for i, p in enumerate(products, start=1):
                    name = p.get('Name', '?')
                    short = name[:40] + ('…' if len(name) > 40 else '')
                    line = QLabel(f'   Tuile {i} :  {short}')
                    line.setStyleSheet('color: #333; border: none; background: transparent;')
                    card_layout.addWidget(line)
            else:
                for i, p in enumerate(
                    sorted(products, key=lambda x: x.get('cloud_cover', 100)), start=1
                ):
                    name = p.get('Name', '')
                    tile = name.split('_T')[1][:5] if '_T' in name else '?'
                    cloud = p.get('cloud_cover', 100.0)
                    line = QLabel(f'   Tuile {i} :  {tile}  —  Nuages : {cloud:.1f} %')
                    line.setStyleSheet('color: #333; border: none; background: transparent;')
                    card_layout.addWidget(line)

            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton('Annuler')
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton('Télécharger')
        self.ok_btn.setFixedWidth(150)
        self.ok_btn.setDefault(True)
        self.ok_btn.setStyleSheet('background-color: #2a7a2a; color: white; font-weight: bold;')
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.ok_btn)
        root.addLayout(btn_row)

        self._sync_select_all_state()
        self.setLayout(root)

    def _on_select_all_changed(self, state):
        checked = state == Qt.Checked
        for checkbox in self.date_checkboxes.values():
            checkbox.setChecked(checked)

    def _on_date_checkbox_toggled(self):
        self._sync_select_all_state()

    def _sync_select_all_state(self):
        if not self.date_checkboxes:
            self.select_all_check.setChecked(False)
            self.ok_btn.setEnabled(False)
            return

        all_checked = all(cb.isChecked() for cb in self.date_checkboxes.values())
        self.select_all_check.blockSignals(True)
        self.select_all_check.setChecked(all_checked)
        self.select_all_check.blockSignals(False)
        self.ok_btn.setEnabled(True)

    def accept(self):
        self.selected_labels = [
            label for label, checkbox in self.date_checkboxes.items()
            if checkbox.isChecked()
        ]
        if not self.selected_labels:
            QMessageBox.warning(
                self,
                'Sélection',
                'Aucune date sélectionnée. Cochez au moins une date ou activez "Sélectionner tout".'
            )
            return
        super().accept()


class Sentinel2DownloaderDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle('Sentinel Downloader — CDSE / Sentinel Hub')
        self.setMinimumWidth(620)
        self.resize(660, 600)
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout()

        product_group = QGroupBox('Type de produit')
        product_form = QFormLayout()
        self.product_type_combo = QComboBox()
        self.product_type_combo.addItem('Optique (Sentinel-2)', 'optique')
        self.product_type_combo.addItem('Radar (Sentinel-1)', 'radar')
        product_form.addRow('Produit :', self.product_type_combo)
        product_group.setLayout(product_form)
        layout.addWidget(product_group)

        # Authentification lue depuis les variables d'environnement (pas d'UI)
        # Définir SH_CLIENT_ID et SH_CLIENT_SECRET dans l'environnement système.

        period = QGroupBox('Intervalle de dates')
        period_form = QFormLayout()
        self.start_date = QDateEdit(QDate.currentDate().addDays(-7))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        period_form.addRow('Du :', self.start_date)
        period_form.addRow('Au :', self.end_date)
        period.setLayout(period_form)

        zone = QGroupBox('Cadre (centre + taille)')
        zone_form = QFormLayout()
        self.lat_edit = QLineEdit('48.8566')
        self.lon_edit = QLineEdit('2.3522')
        self.buffer_edit = QLineEdit('5')
        self.buffer_edit.setToolTip('Demi-côté du carré en kilomètres')
        zone_form.addRow('Latitude :', self.lat_edit)
        zone_form.addRow('Longitude :', self.lon_edit)
        zone_form.addRow('Buffer (km) :', self.buffer_edit)
        zone.setLayout(zone_form)

        self.cloud_group = QGroupBox('Filtrage des nuages (optionnel)')
        self.cloud_group.setCheckable(True)
        self.cloud_group.setChecked(False)
        cloud_form = QFormLayout()
        self.cloud_threshold = QSpinBox()
        self.cloud_threshold.setRange(0, 100)
        self.cloud_threshold.setValue(50)
        self.cloud_threshold.setSuffix('%')
        self.cloud_threshold.setToolTip('Filtrer les tuiles avec plus de % de nuages')
        cloud_form.addRow('Seuil nuages :', self.cloud_threshold)
        self.cloud_group.setLayout(cloud_form)
        self.cloud_filter_enabled = self.cloud_group

        # --- Indices côte à côte ---
        indices_row = QHBoxLayout()

        # Indices optiques (Sentinel-2)
        self.indices_group = QGroupBox('Indices optiques (Sentinel-2)')
        indices_layout = QVBoxLayout()
        self.ndvi_check = QCheckBox('NDVI — végétation')
        self.ndwi_check = QCheckBox('NDWI — eau')
        self.ndbi_check = QCheckBox('NDBI — bâti / sol nu')
        self.ndmi_check = QCheckBox('NDMI — humidité végétale')
        indices_layout.addWidget(self.ndvi_check)
        indices_layout.addWidget(self.ndwi_check)
        indices_layout.addWidget(self.ndbi_check)
        indices_layout.addWidget(self.ndmi_check)
        indices_layout.addStretch()
        self.indices_group.setLayout(indices_layout)

        # Indices radar (Sentinel-1)
        self.radar_indices_group = QGroupBox('Indices radar (Sentinel-1)')
        radar_indices_layout = QVBoxLayout()
        self.rvi_check   = QCheckBox('RVI  — Radar Vegetation Index')
        self.vvvh_check  = QCheckBox('VV/VH — rapport de polarisation')
        self.ndpi_check  = QCheckBox('NDPI — Normalized Difference Polarization Index')
        self.dpsvi_check = QCheckBox('DPSVI — Dual-Pol SAR Vegetation Index')
        radar_indices_layout.addWidget(self.rvi_check)
        radar_indices_layout.addWidget(self.vvvh_check)
        radar_indices_layout.addWidget(self.ndpi_check)
        radar_indices_layout.addWidget(self.dpsvi_check)
        radar_indices_layout.addStretch()
        self.radar_indices_group.setLayout(radar_indices_layout)

        indices_row.addWidget(self.indices_group)
        indices_row.addWidget(self.radar_indices_group)

        layout.addWidget(period)
        layout.addWidget(zone)
        layout.addWidget(self.cloud_group)
        layout.addLayout(indices_row)

        self.product_type_combo.currentIndexChanged.connect(self.update_product_controls)
        self.cloud_group.toggled.connect(self.update_product_controls)
        self.update_product_controls()

        # --- Dossier de sortie ---
        output_group = QGroupBox('Dossier de sortie')
        output_form = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        default_out = os.path.join(os.path.expanduser('~'), 'Documents', 'Sentinel_Downloads')
        self.output_dir_edit.setText(
            QSettings().value('Sentinel2Downloader/output_dir', default_out)
        )
        browse_btn = QPushButton('Parcourir...')
        browse_btn.clicked.connect(self.browse_output_dir)
        output_form.addWidget(self.output_dir_edit)
        output_form.addWidget(browse_btn)
        output_group.setLayout(output_form)
        layout.addWidget(output_group)

        row = QHBoxLayout()
        self.run_button = QPushButton('Télécharger')
        self.run_button.clicked.connect(self.on_run)
        row.addWidget(self.run_button)
        close_btn = QPushButton('Fermer')
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self.status_label = QLabel('Prêt — renseignez les paramètres puis cliquez sur Télécharger.')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def update_product_controls(self):
        product_type = self.product_type_combo.currentData()
        is_optique = product_type == 'optique'
        is_radar   = product_type == 'radar'

        # Nuages : uniquement optique
        self.cloud_group.setEnabled(is_optique)
        self.cloud_threshold.setEnabled(is_optique and self.cloud_group.isChecked())
        if not is_optique:
            self.cloud_group.setChecked(False)

        # Indices : chaque section activée selon le produit choisi
        self.indices_group.setEnabled(is_optique)
        self.radar_indices_group.setEnabled(is_radar)

        # Décocher les indices du mode inactif pour éviter la confusion
        if not is_optique:
            for cb in (self.ndvi_check, self.ndwi_check, self.ndbi_check, self.ndmi_check):
                cb.setChecked(False)
        if not is_radar:
            for cb in (self.rvi_check, self.vvvh_check, self.ndpi_check, self.dpsvi_check):
                cb.setChecked(False)

    def browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, 'Choisir le dossier de sortie',
            self.output_dir_edit.text()
        )
        if folder:
            self.output_dir_edit.setText(folder)
            QSettings().setValue('Sentinel2Downloader/output_dir', folder)

    def on_run(self):
        try:
            self.run_download()
        except Exception as error:
            self.show_error(str(error))

    def run_download(self):
        self.run_button.setEnabled(False)
        try:
            params = self.validate_inputs()
            try:
                import requests
            except ModuleNotFoundError:
                raise Exception('Installez requests : python -m pip install requests')

            self.set_status('Connexion à Sentinel Hub (CDSE)...')
            QApplication.processEvents()
            sh_session = self.create_sh_session(
                requests, params['sh_client_id'], params['sh_client_secret']
            )

            # Session CDSE classique pour la recherche catalogue (sans user/password requis pour catalogue public)
            catalogue_session = requests.Session()

            aoi_wkt = self.build_odata_aoi(params['lat'], params['lon'], params['buffer_km'])
            bbox    = self.wkt_to_bbox(aoi_wkt)
            self.show_cadre_layer(aoi_wkt)

            self.set_status('Recherche des images sur la période...')
            QApplication.processEvents()
            products = self.search_products(
                catalogue_session,
                aoi_wkt,
                params['start_date'],
                params['end_date'],
                params['product_type'],
            )
            days = self.group_products_by_day(products)
            if not days:
                if params['product_type'] == 'radar':
                    raise Exception('Aucune image radar Sentinel-1 sur cette période et ce cadre.')
                raise Exception('Aucune image Sentinel-2 sur cette période et ce cadre.')

            if params['product_type'] == 'optique' and self.cloud_filter_enabled.isChecked():
                threshold = self.cloud_threshold.value()
                filtered_days = {}
                for acq_label in days.keys():
                    day_products = days[acq_label]
                    if all(p.get('cloud_cover', 100) <= threshold for p in day_products):
                        filtered_days[acq_label] = day_products
                if not filtered_days:
                    raise Exception('Aucune image après filtrage des nuages.')
                days = filtered_days

            confirm = ConfirmDownloadDialog(days, params['product_type'], self)
            if confirm.exec_() != QDialog.Accepted:
                self.set_status('Annulé.')
                return

            selected_days = {label: days[label] for label in confirm.selected_labels}
            if not selected_days:
                self.set_status('Aucune date sélectionnée.')
                return

            days = selected_days
            output_dir = self.output_dir_edit.text().strip()
            if not output_dir:
                output_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'Sentinel_Downloads')
            os.makedirs(output_dir, exist_ok=True)
            QSettings().setValue('Sentinel2Downloader/output_dir', output_dir)
            work_dir = output_dir
            self.set_status(f'Dossier de sortie : {work_dir}')
            if params['product_type'] == 'radar':
                for index, (acq_label, day_products) in enumerate(sorted(days.items()), start=1):
                    self.set_status(
                        f"Jour {index}/{len(days)} — {acq_label} → téléchargement radar via SH..."
                    )
                    QApplication.processEvents()
                    stack_path = self.sh_download_radar(
                        sh_session, day_products, bbox, work_dir, acq_label
                    )
                    # Toujours corriger le géoréférencement (même fichier en cache)
                    self._fix_geotransform(stack_path, bbox)
                    layer = QgsRasterLayer(stack_path, f'Sentinel-1 — {acq_label}')
                    if not layer.isValid():
                        raise Exception(f'Couche invalide pour {acq_label}')
                    self.apply_radar_rendering(layer)
                    QgsProject.instance().addMapLayer(layer)

                    radar_index_paths = self.compute_selected_radar_indices(stack_path, work_dir, acq_label)
                    for index_name, index_path in radar_index_paths.items():
                        index_layer = QgsRasterLayer(index_path, f'Sentinel-1 — {acq_label} — {index_name}')
                        if not index_layer.isValid():
                            raise Exception(f'Couche indice radar invalide pour {acq_label} ({index_name})')
                        self.apply_index_rendering(index_layer, index_path)
                        QgsProject.instance().addMapLayer(index_layer)
            else:
                for index, (acq_label, day_products) in enumerate(sorted(days.items()), start=1):
                    self.set_status(
                        f"Jour {index}/{len(days)} — {acq_label} → téléchargement S2 via SH..."
                    )
                    QApplication.processEvents()
                    display_path, stack_path, band_paths = self.sh_download_s2(
                        sh_session, day_products, bbox, work_dir, acq_label
                    )
                    # Toujours corriger le géoréférencement (même fichier en cache)
                    self._fix_geotransform(stack_path, bbox)
                    # Charger le stack multi-bandes pour permettre le choix manuel des bandes
                    layer = QgsRasterLayer(stack_path, f'Sentinel-2 — {acq_label}')
                    if not layer.isValid():
                        raise Exception(f'Couche multi-bandes invalide pour {acq_label}')
                    QgsProject.instance().addMapLayer(layer)
                    QgsMessageLog.logMessage(
                        f'{acq_label} : couche multi-bandes chargée ({stack_path})',
                        'Sentinel2Downloader', Qgis.Info,
                    )

                    index_paths = self.compute_selected_indices(stack_path, work_dir, acq_label)
                    for index_name, index_path in index_paths.items():
                        index_layer = QgsRasterLayer(index_path, f'Sentinel-2 — {acq_label} — {index_name}')
                        if not index_layer.isValid():
                            raise Exception(f'Couche indice invalide pour {acq_label} ({index_name})')
                        self.apply_index_rendering(index_layer, index_path)
                        QgsProject.instance().addMapLayer(index_layer)

            self.iface.mapCanvas().setExtent(
                QgsProject.instance().mapLayersByName(CADRE_LAYER_NAME)[0].extent()
            )
            self.iface.mapCanvas().refresh()
            if params['product_type'] == 'radar':
                self.set_status(
                    f'Terminé — {len(days)} couche(s) Sentinel-1 ajoutée(s) dans QGIS (VV + VH, sigma0 dB).'
                )
            else:
                self.set_status(
                    f'Terminé — {len(days)} couche(s) Sentinel-2 ajoutée(s) dans QGIS '
                    f'(RGB affichage + 12 bandes B01–B12 pour indices).'
                )
        finally:
            self.run_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Sentinel Hub Processing API — authentification et téléchargement
    # ------------------------------------------------------------------

    def create_sh_session(self, requests, client_id, client_secret):
        """Obtient un token OAuth2 client_credentials pour la SH Processing API."""
        response = requests.post(
            SH_TOKEN_URL,
            data={
                'grant_type':    'client_credentials',
                'client_id':     client_id,
                'client_secret': client_secret,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise Exception(
                f'Connexion Sentinel Hub échouée ({response.status_code}) : {response.text[:200]}'
            )
        token = response.json().get('access_token')
        if not token:
            raise Exception('Token Sentinel Hub absent dans la réponse.')
        session = requests.Session()
        session.headers['Authorization'] = f'Bearer {token}'
        session.headers['Content-Type']  = 'application/json'
        return session

    def compute_image_size(self, bbox, max_pixels=2400):
        """
        Calcule width/height en pixels pour rester sous max_pixels par axe.
        Sentinel Hub accepte width/height directement — plus fiable que resx/resy
        qui peut être rejeté si la combinaison bbox+res dépasse 2500px.
        """
        lon_span = bbox[2] - bbox[0]
        lat_span = bbox[3] - bbox[1]
        if lon_span >= lat_span:
            width  = max_pixels
            height = max(1, int(round(lat_span / lon_span * max_pixels)))
        else:
            height = max_pixels
            width  = max(1, int(round(lon_span / lat_span * max_pixels)))
        return width, height

    def wkt_to_bbox(self, aoi_wkt):
        """Extrait [min_lon, min_lat, max_lon, max_lat] depuis un WKT POLYGON."""
        coords = re.findall(r'([-\d.]+)\s+([-\d.]+)', aoi_wkt)
        lons = [float(c[0]) for c in coords]
        lats = [float(c[1]) for c in coords]
        return [min(lons), min(lats), max(lons), max(lats)]

    def _sh_pick_date(self, day_products):
        """Choisit la date d'acquisition la moins nuageuse pour la requête SH."""
        best = min(day_products, key=lambda p: p.get('cloud_cover', 100))
        label = best['acq_label']  # dd/mm/yyyy
        try:
            d = datetime.datetime.strptime(label, '%d/%m/%Y')
            return d.strftime('%Y-%m-%d')
        except ValueError:
            return datetime.date.today().isoformat()

    def _fix_geotransform(self, tif_path, bbox):
        """
        Force le géoréférencement d'un GeoTIFF pour qu'il couvre exactement la bbox.
        bbox = [min_lon, min_lat, max_lon, max_lat]
        Appelé sur chaque fichier téléchargé ET sur les fichiers en cache,
        pour garantir que toutes les couches sont calées sur le même cadre.
        """
        try:
            min_lon, min_lat, max_lon, max_lat = bbox
            ds = gdal.Open(tif_path, gdal.GA_Update)
            if ds is None:
                return
            w = ds.RasterXSize
            h = ds.RasterYSize
            pixel_w = (max_lon - min_lon) / w
            pixel_h = (max_lat - min_lat) / h
            ds.SetGeoTransform([min_lon, pixel_w, 0.0, max_lat, 0.0, -pixel_h])
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            ds.SetProjection(srs.ExportToWkt())
            ds.FlushCache()
            ds = None
        except Exception as err:
            QgsMessageLog.logMessage(
                f'_fix_geotransform ignoré pour {tif_path} : {err}',
                'Sentinel2Downloader', Qgis.Warning,
            )

    def _sh_request(self, sh_session, payload, out_path, label):
        """Envoie une requête à la SH Processing API, sauvegarde le GeoTIFF
        et corrige le géoréférencement avec la bbox de la requête."""
        import json
        self.set_status(f'{label} — envoi requête Sentinel Hub...')
        QApplication.processEvents()

        response = sh_session.post(
            SH_PROCESS_URL,
            data=json.dumps(payload),
            timeout=DOWNLOAD_TIMEOUT,
        )
        if response.status_code != 200:
            raise Exception(
                f'SH Processing API erreur ({response.status_code}) : {response.text[:300]}'
            )
        with open(out_path, 'wb') as fh:
            fh.write(response.content)
        if not self.is_valid_raster_file(out_path):
            raise Exception(f'Le GeoTIFF reçu de Sentinel Hub est invalide ({out_path}).')

        # ── Correction géoréférencement ──────────────────────────────
        # Sentinel Hub retourne parfois un GeoTIFF sans projection ou avec
        # une geotransform incorrecte → on force la bbox déclarée dans la requête.
        try:
            bbox = payload['input']['bounds']['bbox']  # [min_lon, min_lat, max_lon, max_lat]
            ds = gdal.Open(out_path, gdal.GA_Update)
            if ds is not None:
                w, h = ds.RasterXSize, ds.RasterYSize
                min_lon, min_lat, max_lon, max_lat = bbox
                pixel_w = (max_lon - min_lon) / w
                pixel_h = (max_lat - min_lat) / h
                # GeoTransform : (x_origine, pixel_width, 0, y_origine, 0, -pixel_height)
                ds.SetGeoTransform([min_lon, pixel_w, 0.0, max_lat, 0.0, -pixel_h])
                srs = osr.SpatialReference()
                srs.ImportFromEPSG(4326)
                ds.SetProjection(srs.ExportToWkt())
                ds.FlushCache()
                ds = None
        except Exception as geo_err:
            QgsMessageLog.logMessage(
                f'Correction géoréférencement ignorée ({geo_err})',
                'Sentinel2Downloader', Qgis.Warning,
            )

    def sh_download_s2(self, sh_session, day_products, bbox, work_dir, acq_label):
        """
        Télécharge Sentinel-2 L2A via SH Processing API en deux étapes :
          1. RGB_display.tif  : 4 bandes UINT8 (B04/B03/B02/alpha) avec étirement intégré dans
             l'evalscript → directement affichable dans QGIS sans aucun rendu supplémentaire.
          2. FINAL_12bands.tif : 12 bandes FLOAT32 [0-1] pour le calcul des indices.
        Retourne (display_path, stack_path, band_paths).
        """
        day_key = acq_label.replace('/', '-')
        day_dir = os.path.join(work_dir, day_key)
        os.makedirs(day_dir, exist_ok=True)

        _img_w, _img_h = self.compute_image_size(bbox)
        date_str  = self._sh_pick_date(day_products)
        date_from = f'{date_str}T00:00:00Z'
        date_to   = f'{date_str}T23:59:59Z'

        # ── 1. Image RGB 8-bit pour l'affichage ──────────────────────────────
        display_path = os.path.join(day_dir, 'RGB_display.tif')
        self.set_status(f'{acq_label} — téléchargement RGB (affichage)...')
        QApplication.processEvents()
        payload_rgb = {
                'input': {
                    'bounds': {
                        'bbox': bbox,
                        'properties': {'crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'},
                    },
                    'data': [{
                        'type': 'sentinel-2-l2a',
                        'dataFilter': {
                            'timeRange': {'from': date_from, 'to': date_to},
                            'maxCloudCoverage': 100,
                            'mosaickingOrder': 'leastCC',
                        },
                    }],
                },
                'output': {
                    'width': _img_w,
                    'height': _img_h,
                    'responses': [{'identifier': 'default', 'format': {'type': 'image/tiff'}}],
                },
                'evalscript': (
                    '//VERSION=3\n'
                    'function setup() {\n'
                    '  return {\n'
                    '    input: [{ bands: ["B04","B03","B02","dataMask"] }],\n'
                    '    output: { bands: 4, sampleType: "UINT8" }\n'
                    '  };\n'
                    '}\n'
                    'function evaluatePixel(s) {\n'
                    '  function stretch(v) {\n'
                    '    return Math.min(255, Math.max(0, Math.round(v / 0.3 * 255)));\n'
                    '  }\n'
                    '  return [stretch(s.B04), stretch(s.B03), stretch(s.B02), s.dataMask * 255];\n'
                    '}\n'
                ),
            }
        self._sh_request(sh_session, payload_rgb, display_path, f'{acq_label}/RGB')

        # ── 2. Stack 12 bandes FLOAT32 pour les indices ──────────────────────
        stack_path = os.path.join(day_dir, 'FINAL_12bands.tif')
        band_paths = {}
        if not (os.path.isfile(stack_path) and self.is_valid_raster_file(stack_path)):
            for code in SENTINEL2_BANDS:
                band_path = os.path.join(day_dir, f'{code}.tif')
                if os.path.isfile(band_path) and self.is_valid_raster_file(band_path):
                    band_paths[code] = band_path
                    continue
                self.set_status(f'{acq_label} — bande {code}...')
                QApplication.processEvents()
                payload = {
                    'input': {
                        'bounds': {
                            'bbox': bbox,
                            'properties': {'crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'},
                        },
                        'data': [{
                            'type': 'sentinel-2-l2a',
                            'dataFilter': {
                                'timeRange': {'from': date_from, 'to': date_to},
                                'maxCloudCoverage': 100,
                                'mosaickingOrder': 'leastCC',
                            },
                        }],
                    },
                    'output': {
                        'width': _img_w,
                        'height': _img_h,
                        'responses': [{'identifier': 'default', 'format': {'type': 'image/tiff'}}],
                    },
                    'evalscript': (
                        '//VERSION=3\n'
                        'function setup() {\n'
                        f'  return {{ input: ["{code}"], output: {{ bands: 1, sampleType: "FLOAT32" }} }};\n'
                        '}\n'
                        'function evaluatePixel(sample) {\n'
                        f'  return [sample.{code}];\n'
                        '}\n'
                    ),
                }
                self._sh_request(sh_session, payload, band_path, f'{acq_label}/{code}')
                band_paths[code] = band_path

            self.set_status(f'{acq_label} — empilement des bandes...')
            QApplication.processEvents()
            self.build_multiband_geotiff(band_paths, stack_path)
        else:
            for code in SENTINEL2_BANDS:
                band_path = os.path.join(day_dir, f'{code}.tif')
                if os.path.isfile(band_path) and self.is_valid_raster_file(band_path):
                    band_paths[code] = band_path

        return display_path, stack_path, band_paths

    def sh_download_radar(self, sh_session, day_products, bbox, work_dir, acq_label):
        """
        Télécharge VV + VH Sentinel-1 GRD via SH Processing API, déjà en sigma0 dB.
        """
        day_key = acq_label.replace('/', '-')
        day_dir = os.path.join(work_dir, day_key)
        os.makedirs(day_dir, exist_ok=True)
        stack_path = os.path.join(day_dir, 'FINAL_S1_dB.tif')
        _img_w, _img_h = self.compute_image_size(bbox)
        date_str = self._sh_pick_date(day_products)
        # Fenêtre ±1 jour pour s'assurer de capturer le passage Sentinel-1
        # (les acquisitions radar ont une heure précise qui peut déborder minuit UTC)
        d = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        date_from = (d - datetime.timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
        date_to   = (d + datetime.timedelta(days=1)).strftime('%Y-%m-%dT23:59:59Z')

        payload = {
            'input': {
                'bounds': {
                    'bbox': bbox,
                    'properties': {'crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'},
                },
                'data': [{
                    'type': 'sentinel-1-grd',
                    'dataFilter': {
                        'timeRange': {'from': date_from, 'to': date_to},
                        'acquisitionMode': 'IW',
                        'polarization': 'DV',
                        'mosaickingOrder': 'mostRecent',
                    },
                    'processing': {
                        'backCoeff':       'SIGMA0_ELLIPSOID',
                        'orthorectify':    True,
                        'demInstance':     'COPERNICUS',
                        'speckleFilter':   {'type': 'NONE'},
                        'toDb':            False,
                    },
                }],
            },
            'output': {
                'width': _img_w,
                'height': _img_h,
                'responses': [{'identifier': 'default', 'format': {'type': 'image/tiff'}}],
            },
            'evalscript': (
                '//VERSION=3\n'
                'function setup() {\n'
                '  return {\n'
                '    input: [{ bands: ["VV", "VH"] }],\n'
                '    output: { bands: 2, sampleType: "FLOAT32" }\n'
                '  };\n'
                '}\n'
                'function evaluatePixel(sample) {\n'
                '  var vv = sample.VV > 0 ? 10 * Math.log10(sample.VV) : -30;\n'
                '  var vh = sample.VH > 0 ? 10 * Math.log10(sample.VH) : -30;\n'
                '  return [vv, vh];\n'
                '}\n'
            ),
        }
        self._sh_request(sh_session, payload, stack_path, acq_label)
        return stack_path

    def group_products_by_day(self, products):
        """Regroupe les produits par jour et trie les tuiles pour l’optique par couverture nuageuse."""
        days = {}
        for product in products:
            days.setdefault(product['acq_label'], []).append(product)
        for acq_label in days:
            days[acq_label].sort(key=lambda product: product.get('cloud_cover', 100.0), reverse=True)
        return days

    def build_mosaic_stack_for_day(self, session, day_products, work_dir, aoi_wkt, acq_label):
        day_key = acq_label.replace('/', '-')
        day_dir = os.path.join(work_dir, day_key)
        os.makedirs(day_dir, exist_ok=True)
        clips_per_band = {code: [] for code in SENTINEL2_BANDS}

        for tile_index, product in enumerate(day_products, start=1):
            self.set_status(
                f"{acq_label} — tuile {tile_index}/{len(day_products)} "
                f"({self.tile_from_name(product['Name'])})..."
            )
            QApplication.processEvents()
            band_paths = self.download_product_bands(session, product, day_dir)
            clip_dir = os.path.join(day_dir, f"clip_{product['scene_id']}")
            os.makedirs(clip_dir, exist_ok=True)
            for code, path in band_paths.items():
                clip_path = os.path.join(clip_dir, f'{code}.tif')
                self.clip_raster_to_cadre(path, aoi_wkt, clip_path)
                clips_per_band[code].append(clip_path)

        mosaic_dir = os.path.join(day_dir, 'mosaic')
        os.makedirs(mosaic_dir, exist_ok=True)
        mosaicked_bands = {}
        for code in SENTINEL2_BANDS:
            tile_clips = clips_per_band[code]
            if not tile_clips:
                continue
            mosaic_path = os.path.join(mosaic_dir, f'{code}.tif')
            self.mosaic_rasters(tile_clips, aoi_wkt, mosaic_path)
            mosaicked_bands[code] = mosaic_path

        stack_path = os.path.join(day_dir, 'FINAL_12bands.tif')
        return self.build_multiband_geotiff(mosaicked_bands, stack_path)

    def build_mosaic_stack_for_day_radar(self, session, day_products, work_dir, aoi_wkt, acq_label):
        day_key = acq_label.replace('/', '-')
        day_dir = os.path.join(work_dir, day_key)
        os.makedirs(day_dir, exist_ok=True)
        stack_path = os.path.join(day_dir, 'FINAL_S1_dB.tif')
        if os.path.isfile(stack_path) and self.is_valid_raster_file(stack_path):
            return stack_path

        measurement_paths = []
        for tile_index, product in enumerate(day_products, start=1):
            self.set_status(
                f"{acq_label} — tuile {tile_index}/{len(day_products)} "
                f"({self.tile_from_name(product['Name'])})..."
            )
            QApplication.processEvents()
            measurement_paths.extend(self.download_product_bands_radar(session, product, day_dir))

        if not measurement_paths:
            raise Exception(f'Aucune mesure radar disponible pour {acq_label}')

        self.set_status(f'{acq_label} — fusion et découpage radar ({len(measurement_paths)} fichier(s))...')
        QApplication.processEvents()
        raw_path = os.path.join(day_dir, 'FINAL_S1_raw.tif')
        self.mosaic_rasters_radar(measurement_paths, aoi_wkt, raw_path)

        # Conversion en dB : les DN bruts Sentinel-1 GRD ont une dynamique
        # exponentielle — sans cette étape QGIS affiche une image uniforme (vide).
        self.set_status(f'{acq_label} — conversion amplitude → dB (sigma0)...')
        QApplication.processEvents()
        self.convert_radar_to_db(raw_path, stack_path)
        return stack_path

    def convert_radar_to_db(self, input_path, output_path):
        """Convertit les DN bruts Sentinel-1 GRD en sigma0 dB : 20*log10(DN).
        Les pixels NoData (DN=0) reçoivent la valeur nodata=-9999.
        Cette conversion est indispensable pour que QGIS affiche la couche
        avec un contraste correct (sinon image uniformément vide ou blanche).
        """
        dataset = gdal.Open(input_path, gdal.GA_ReadOnly)
        if dataset is None:
            raise Exception(f'Impossible d\'ouvrir le raster radar : {input_path}')

        driver = gdal.GetDriverByName('GTiff')
        out = driver.Create(
            output_path,
            dataset.RasterXSize,
            dataset.RasterYSize,
            dataset.RasterCount,
            gdal.GDT_Float32,
            ['COMPRESS=LZW', 'TILED=YES'],
        )
        out.SetGeoTransform(dataset.GetGeoTransform())
        out.SetProjection(dataset.GetProjection())

        NODATA_DB = -9999.0
        for i in range(1, dataset.RasterCount + 1):
            src_band = dataset.GetRasterBand(i)
            data = src_band.ReadAsArray().astype(np.float32)
            # sigma0 dB = 20 * log10(DN) ; pixels DN=0 → nodata
            db_data = np.where(data > 0, 20.0 * np.log10(np.maximum(data, 1e-6)), NODATA_DB)
            out_band = out.GetRasterBand(i)
            out_band.SetNoDataValue(NODATA_DB)
            desc = src_band.GetDescription()
            out_band.SetDescription(desc if desc else f'sigma0_dB_band{i}')
            out_band.WriteArray(db_data)
            out_band.FlushCache()

        out.FlushCache()
        out = None
        dataset = None
        QgsMessageLog.logMessage(
            f'Conversion dB terminée : {output_path}',
            'Sentinel2Downloader',
            Qgis.Info,
        )

    # ------------------------------------------------------------------
    # Téléchargement sélectif par HTTP Range (évite de télécharger le ZIP complet)
    # ------------------------------------------------------------------

    def _get_download_url(self, session, product_id):
        """Résout les redirections et renvoie l'URL finale de téléchargement."""
        url = f'{CDSE_DOWNLOAD_URL}/Products({product_id})/$value'
        for _ in range(5):
            response = session.head(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
            if response.status_code in (301, 302, 303, 307, 308):
                url = response.headers.get('Location', url)
            elif response.status_code in (200, 206):
                return url, response.headers
            else:
                # HEAD pas supporté → on tente GET avec Range minuscule
                response = session.get(
                    url, headers={'Range': 'bytes=0-0'},
                    allow_redirects=False, timeout=REQUEST_TIMEOUT
                )
                if response.status_code in (301, 302, 303, 307, 308):
                    url = response.headers.get('Location', url)
                else:
                    return url, response.headers
        return url, {}

    def _fetch_bytes(self, session, url, start, end):
        """Télécharge un intervalle d'octets depuis une URL."""
        headers = {'Range': f'bytes={start}-{end}'}
        response = session.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT)
        if response.status_code not in (200, 206):
            raise Exception(
                f'Range request échoué ({response.status_code}) pour {url} bytes={start}-{end}'
            )
        return response.content

    def _parse_zip_index(self, session, url, total_size):
        """
        Télécharge et analyse l'index central du ZIP (End of Central Directory).
        Renvoie une liste de dicts : {name, compress_type, file_size, header_offset, compress_size}.
        """
        # Lire les 64 Ko finaux pour trouver l'EOCD
        tail_size = min(65536, total_size)
        tail = self._fetch_bytes(session, url, total_size - tail_size, total_size - 1)

        # Signature EOCD = 0x06054b50
        EOCD_SIG = b'PK\x05\x06'
        idx = tail.rfind(EOCD_SIG)
        if idx == -1:
            raise Exception('Signature EOCD introuvable dans le ZIP (index corrompu ou ZIP64).')

        eocd = tail[idx:]
        if len(eocd) < 22:
            raise Exception('EOCD tronqué.')

        cd_size   = struct.unpack_from('<I', eocd, 12)[0]
        cd_offset = struct.unpack_from('<I', eocd, 16)[0]

        # Vérifier ZIP64 (valeurs 0xFFFFFFFF → non supporté ici, fallback)
        if cd_offset == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
            raise Exception('ZIP64 détecté : fallback sur téléchargement complet.')

        # Télécharger le Central Directory
        cd_data = self._fetch_bytes(session, url, cd_offset, cd_offset + cd_size - 1)

        entries = []
        pos = 0
        CD_SIG = b'PK\x01\x02'
        while pos + 46 <= len(cd_data):
            if cd_data[pos:pos+4] != CD_SIG:
                break
            compress_type  = struct.unpack_from('<H', cd_data, pos + 10)[0]
            compress_size  = struct.unpack_from('<I', cd_data, pos + 20)[0]
            file_size      = struct.unpack_from('<I', cd_data, pos + 24)[0]
            fname_len      = struct.unpack_from('<H', cd_data, pos + 28)[0]
            extra_len      = struct.unpack_from('<H', cd_data, pos + 30)[0]
            comment_len    = struct.unpack_from('<H', cd_data, pos + 32)[0]
            header_offset  = struct.unpack_from('<I', cd_data, pos + 42)[0]
            fname          = cd_data[pos+46 : pos+46+fname_len].decode('utf-8', errors='replace')
            entries.append({
                'name':          fname,
                'compress_type': compress_type,
                'compress_size': compress_size,
                'file_size':     file_size,
                'header_offset': header_offset,
            })
            pos += 46 + fname_len + extra_len + comment_len

        return entries

    def _download_entry(self, session, url, entry, output_path):
        """
        Télécharge un fichier individuel dans le ZIP via Range,
        en lisant d'abord le Local File Header pour connaître l'offset exact des données.
        """
        # Lire le Local File Header (30 octets fixes + noms variables)
        lh = self._fetch_bytes(session, url, entry['header_offset'], entry['header_offset'] + 29)
        if lh[:4] != b'PK\x03\x04':
            raise Exception(f"Local File Header invalide pour {entry['name']}")
        fname_len  = struct.unpack_from('<H', lh, 26)[0]
        extra_len  = struct.unpack_from('<H', lh, 28)[0]
        data_start = entry['header_offset'] + 30 + fname_len + extra_len
        data_end   = data_start + entry['compress_size'] - 1

        raw = self._fetch_bytes(session, url, data_start, data_end)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if entry['compress_type'] == 8:   # DEFLATE
            import zlib
            data = zlib.decompress(raw, -15)
        elif entry['compress_type'] == 0: # Stocké
            data = raw
        else:
            raise Exception(
                f"Méthode de compression {entry['compress_type']} non supportée pour {entry['name']}"
            )

        with open(output_path, 'wb') as fh:
            fh.write(data)

    def _selective_download(self, session, product_id, wanted_fn, work_dir, label):
        """
        Télécharge sélectivement les fichiers voulus d'un produit ZIP Copernicus.
        `wanted_fn(entry_name) -> output_path | None`
        Renvoie un dict {entry_name: local_path} des fichiers téléchargés.
        Lève une exception si Range non supporté → l'appelant doit fallback sur zip complet.
        """
        url, head_headers = self._get_download_url(session, product_id)
        content_length = head_headers.get('Content-Length') or head_headers.get('content-length')
        accept_ranges  = (head_headers.get('Accept-Ranges') or head_headers.get('accept-ranges') or '').lower()

        # Vérification du support Range
        if accept_ranges == 'none':
            raise Exception('Range non supporté par le serveur.')
        if not content_length:
            raise Exception('Content-Length absent, impossible de calculer les offsets.')

        total_size = int(content_length)
        self.set_status(f'{label} — lecture de l\'index ZIP ({total_size // 1024 // 1024} Mo total)...')
        QApplication.processEvents()

        entries = self._parse_zip_index(session, url, total_size)

        results = {}
        wanted_entries = []
        for entry in entries:
            out_path = wanted_fn(entry['name'])
            if out_path is not None:
                wanted_entries.append((entry, out_path))

        if not wanted_entries:
            raise Exception('Aucun fichier utile trouvé dans l\'index ZIP.')

        total_wanted = sum(e['file_size'] for e, _ in wanted_entries)
        self.set_status(
            f'{label} — téléchargement sélectif : {len(wanted_entries)} fichier(s), '
            f'~{total_wanted // 1024 // 1024} Mo (sur {total_size // 1024 // 1024} Mo total)'
        )
        QApplication.processEvents()

        for i, (entry, out_path) in enumerate(wanted_entries, 1):
            self.set_status(
                f'{label} — fichier {i}/{len(wanted_entries)} : {os.path.basename(entry["name"])} '
                f'({entry["file_size"] // 1024} Ko)...'
            )
            QApplication.processEvents()
            if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                self._download_entry(session, url, entry, out_path)
            results[entry['name']] = out_path

        return results

    # ------------------------------------------------------------------
    # Téléchargement des bandes (remplace ensure_valid_zip + extract_*)
    # ------------------------------------------------------------------

    def download_product_bands(self, session, product, work_dir):
        """Télécharge uniquement les bandes JP2 Sentinel-2 (téléchargement sélectif par Range)."""
        scene_dir = os.path.join(work_dir, product['scene_id'])
        bands_dir = os.path.join(scene_dir, 'bands_raw')
        os.makedirs(bands_dir, exist_ok=True)
        label = f"{product['acq_label']} ({self.tile_from_name(product['Name'])})"

        # Vérifier si les bandes sont déjà téléchargées
        found_cached = {}
        for code in SENTINEL2_BANDS:
            p = os.path.join(bands_dir, f'{code}.jp2')
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                found_cached[code] = p
        if len(found_cached) == len(SENTINEL2_BANDS):
            return found_cached

        # Tentative de téléchargement sélectif
        try:
            found = dict(found_cached)

            def wanted_fn(entry_name):
                if not entry_name.lower().endswith('.jp2'):
                    return None
                code = self.band_code_from_path(entry_name)
                if code not in SENTINEL2_BANDS or code in found:
                    return None
                return os.path.join(bands_dir, f'{code}.jp2')

            downloaded = self._selective_download(
                session, product['Id'], wanted_fn, bands_dir, label
            )
            for entry_name, out_path in downloaded.items():
                code = self.band_code_from_path(entry_name)
                if code in SENTINEL2_BANDS:
                    found[code] = out_path

            missing = [c for c in SENTINEL2_BANDS if c not in found]
            if missing:
                raise Exception(
                    f'Bandes manquantes après téléchargement sélectif : {", ".join(missing)}'
                )
            return found

        except Exception as selective_err:
            QgsMessageLog.logMessage(
                f'Téléchargement sélectif impossible ({selective_err}), '
                f'fallback sur ZIP complet pour {product["Name"]}.',
                'Sentinel2Downloader', Qgis.Warning,
            )
            self.set_status(f'{label} — fallback ZIP complet...')
            QApplication.processEvents()
            scene_dir2 = os.path.join(work_dir, product['scene_id'])
            os.makedirs(scene_dir2, exist_ok=True)
            zip_path = os.path.join(scene_dir2, f"{product['Name']}.zip")
            if not self.is_valid_zip_file(zip_path):
                self.ensure_valid_zip(session, product['Id'], zip_path)
            return self.extract_sentinel2_bands(scene_dir2, zip_path)

    def download_product_bands_radar(self, session, product, work_dir):
        """Télécharge uniquement les mesures .tif Sentinel-1 (téléchargement sélectif par Range)."""
        scene_dir = os.path.join(work_dir, product['scene_id'])
        meas_dir  = os.path.join(scene_dir, 'measurement')
        os.makedirs(meas_dir, exist_ok=True)
        label = f"{product['acq_label']} ({self.tile_from_name(product['Name'])})"

        # Vérifier si les mesures sont déjà présentes
        cached = [
            os.path.join(meas_dir, f)
            for f in os.listdir(meas_dir)
            if f.lower().endswith(('.tif', '.tiff'))
        ]
        cached_valid = [p for p in cached if self.is_valid_raster_file(p)]
        if cached_valid:
            return cached_valid

        # Tentative de téléchargement sélectif
        try:
            def wanted_fn(entry_name):
                lower = entry_name.lower()
                if not lower.endswith(('.tif', '.tiff')):
                    return None
                # Cibler uniquement le dossier measurement/ du .SAFE
                parts = lower.replace('\\', '/').split('/')
                if 'measurement' not in parts:
                    return None
                base = os.path.basename(entry_name)
                return os.path.join(meas_dir, base)

            downloaded = self._selective_download(
                session, product['Id'], wanted_fn, meas_dir, label
            )
            result = [p for p in downloaded.values() if self.is_valid_raster_file(p)]
            if not result:
                raise Exception('Aucune mesure radar valide téléchargée sélectivement.')
            return result

        except Exception as selective_err:
            QgsMessageLog.logMessage(
                f'Téléchargement sélectif impossible ({selective_err}), '
                f'fallback sur ZIP complet pour {product["Name"]}.',
                'Sentinel2Downloader', Qgis.Warning,
            )
            self.set_status(f'{label} — fallback ZIP complet...')
            QApplication.processEvents()
            scene_dir2 = os.path.join(work_dir, product['scene_id'])
            os.makedirs(scene_dir2, exist_ok=True)
            zip_path = os.path.join(scene_dir2, f"{product['Name']}.zip")
            if not self.is_valid_zip_file(zip_path):
                self.ensure_valid_zip(session, product['Id'], zip_path)
            return self.extract_sentinel1_measurements(scene_dir2, zip_path)

    def clip_raster_to_cadre(self, source_path, aoi_wkt, output_path):
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        gdal.Warp(
            output_path,
            source_path,
            format='GTiff',
            cutlineSRS='EPSG:4326',
            cutlineWKT=aoi_wkt,
            cropToCutline=True,
            xRes=10,
            yRes=10,
            resampleAlg='bilinear',
            dstNodata=0,
            targetAlignedPixels=True,
            multithread=True,
        )
        return output_path

    def mosaic_rasters(self, raster_paths, aoi_wkt, output_path):
        """Fusionne plusieurs tuiles pour couvrir tout le cadre."""
        if len(raster_paths) == 1:
            gdal.Warp(
                output_path,
                raster_paths[0],
                format='GTiff',
                cutlineSRS='EPSG:4326',
                cutlineWKT=aoi_wkt,
                cropToCutline=True,
                xRes=10,
                yRes=10,
                resampleAlg='bilinear',
                dstNodata=0,
                multithread=True,
            )
            return output_path

        gdal.Warp(
            output_path,
            raster_paths,
            format='GTiff',
            cutlineSRS='EPSG:4326',
            cutlineWKT=aoi_wkt,
            cropToCutline=True,
            xRes=10,
            yRes=10,
            resampleAlg='bilinear',
            dstNodata=0,
            multithread=True,
        )
        return output_path

    def mosaic_rasters_radar(self, raster_paths, aoi_wkt, output_path):
        """Fusionne, reprojette en EPSG:4326 et recadre les mesures radar dans l'AOI."""
        invalid_paths = [path for path in raster_paths if not self.is_valid_raster_file(path)]
        if invalid_paths:
            raise Exception(
                'Une ou plusieurs mesures radar sont invalides ou non lisibles : '
                + ', '.join(invalid_paths)
            )

        # IMPORTANT : on force dstSRS='EPSG:4326' pour que le découpage par l'AOI
        # (exprimée en EPSG:4326) soit cohérent avec le CRS de sortie.
        # Sans cela, gdal.Warp garde le CRS source (UTM ou autre) et le cutline
        # en EPSG:4326 ne correspond pas → tout devient NoData → image vide dans QGIS.
        warp_kwargs = dict(
            format='GTiff',
            dstSRS='EPSG:4326',
            cutlineSRS='EPSG:4326',
            cutlineWKT=aoi_wkt,
            cropToCutline=True,
            xRes=0.0001,    # ~10 m en degrés à l'équateur ; adapté pour EPSG:4326
            yRes=0.0001,
            resampleAlg='bilinear',
            dstNodata=0,
            targetAlignedPixels=True,
            multithread=True,
            creationOptions=['COMPRESS=LZW', 'TILED=YES'],
        )

        src = raster_paths[0] if len(raster_paths) == 1 else raster_paths
        result = gdal.Warp(output_path, src, **warp_kwargs)
        result = None  # flush

        if not self.is_valid_raster_file(output_path):
            raise Exception(f'La sortie radar a été générée mais est invalide : {output_path}')
        return output_path

    def extract_sentinel1_measurements(self, scene_dir, zip_path):
        if not os.path.isdir(scene_dir):
            os.makedirs(scene_dir, exist_ok=True)

        already_extracted = any(
            name.endswith('.SAFE') or name.lower().endswith(('.tif', '.tiff'))
            for name in os.listdir(scene_dir)
        )
        if not already_extracted:
            with zipfile.ZipFile(zip_path, 'r') as archive:
                measurement_entries = [
                    entry for entry in archive.namelist()
                    if entry.lower().endswith(('.tif', '.tiff'))
                ]
                if measurement_entries:
                    for entry in measurement_entries:
                        target = os.path.join(scene_dir, entry)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with archive.open(entry) as src, open(target, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                else:
                    archive.extractall(scene_dir)

        measurement_paths = []
        seen = set()
        for root, _, files in os.walk(scene_dir):
            # Filtrer uniquement le dossier 'measurement/' du .SAFE
            # pour éviter les quick-look ou autres .tiff parasites
            in_measurement = os.path.basename(root).lower() == 'measurement' or \
                             'measurement' in root.lower().split(os.sep)
            for file_name in files:
                if not file_name.lower().endswith(('.tif', '.tiff')):
                    continue
                path = os.path.join(root, file_name)
                if path not in seen:
                    seen.add(path)
                    measurement_paths.append(path)

        if not measurement_paths:
            # Fallback : chercher dans tous les sous-dossiers .SAFE
            for root, dirs, files in os.walk(scene_dir):
                for dir_name in dirs:
                    if dir_name.endswith('.SAFE'):
                        safe_path = os.path.join(root, dir_name)
                        meas_path = os.path.join(safe_path, 'measurement')
                        search_root = meas_path if os.path.isdir(meas_path) else safe_path
                        for sr, _, sfiles in os.walk(search_root):
                            for file_name in sfiles:
                                if file_name.lower().endswith(('.tif', '.tiff')):
                                    path = os.path.join(sr, file_name)
                                    if path not in seen:
                                        seen.add(path)
                                        measurement_paths.append(path)

        valid_measurements = [path for path in measurement_paths if self.is_valid_raster_file(path)]
        if not valid_measurements:
            raise Exception(f'Aucune mesure radar valide trouvée dans {zip_path}')

        if len(valid_measurements) != len(measurement_paths):
            raise Exception(f'Quelques mesures radar sont invalides dans {zip_path}')

        return valid_measurements

    def extract_sentinel2_bands(self, scene_dir, zip_path):
        bands_dir = os.path.join(scene_dir, 'bands_raw')
        os.makedirs(bands_dir, exist_ok=True)
        found = {}

        with zipfile.ZipFile(zip_path, 'r') as archive:
            for entry in archive.namelist():
                if not entry.lower().endswith('.jp2'):
                    continue
                code = self.band_code_from_path(entry)
                if code not in SENTINEL2_BANDS:
                    continue
                if code in found:
                    continue
                target = os.path.join(bands_dir, f'{code}.jp2')
                with archive.open(entry) as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                found[code] = target

        missing = [code for code in SENTINEL2_BANDS if code not in found]
        if missing:
            safe_dirs = [
                os.path.join(scene_dir, name)
                for name in os.listdir(scene_dir)
                if name.endswith('.SAFE')
            ]
            if not safe_dirs:
                with zipfile.ZipFile(zip_path, 'r') as archive:
                    archive.extractall(scene_dir)
                safe_dirs = [
                    os.path.join(scene_dir, name)
                    for name in os.listdir(scene_dir)
                    if name.endswith('.SAFE')
                ]
            if not safe_dirs:
                raise Exception('Aucune structure .SAFE trouvée pour extraire les bandes Sentinel-2.')

            for jp2 in glob.glob(os.path.join(safe_dirs[0], '**', '*.jp2'), recursive=True):
                code = self.band_code_from_path(jp2)
                if code in SENTINEL2_BANDS and code not in found:
                    found[code] = jp2

        missing = [code for code in SENTINEL2_BANDS if code not in found]
        if missing:
            raise Exception(
                f'Bandes Sentinel-2 absentes après extraction : {", ".join(missing)}. '
                'Vérifiez le téléchargement ou les noms de fichiers du produit.'
            )

        return found

    def band_code_from_path(self, path):
        filename = os.path.basename(path).upper()
        match = re.search(r'(^|[_-])(B\d{2}|B8A)(?=($|[_-]|\.))', filename)
        return match.group(2) if match else ''

    def build_multiband_geotiff(self, band_paths, output_path):
        ordered_paths = []
        ordered_codes = []
        for code in SENTINEL2_BANDS:
            if code in band_paths:
                ordered_paths.append(band_paths[code])
                ordered_codes.append(code)

        if not ordered_paths:
            raise Exception('Aucune bande Sentinel-2 après fusion.')

        missing = [code for code in SENTINEL2_BANDS if code not in band_paths]
        if missing:
            QgsMessageLog.logMessage(
                f'Bandes absentes : {", ".join(missing)}',
                'Sentinel2Downloader',
                Qgis.Warning,
            )

        vrt_path = output_path + '.vrt'
        vrt = gdal.BuildVRT(vrt_path, ordered_paths, separate=True)
        if vrt is None:
            raise Exception('Impossible d\'empiler les bandes (tailles différentes).')

        translate_options = gdal.TranslateOptions(
            format='GTiff',
            creationOptions=['COMPRESS=LZW', 'TILED=YES'],
        )
        dataset = gdal.Translate(output_path, vrt, options=translate_options)
        vrt = None
        if dataset is None:
            raise Exception('Impossible de créer le fichier multi-bandes.')

        for index, code in enumerate(ordered_codes, start=1):
            dataset.GetRasterBand(index).SetDescription(code)
        band_count = dataset.RasterCount
        dataset = None

        if band_count < len(ordered_codes):
            raise Exception(
                f'Seulement {band_count} bandes empilées sur {len(ordered_codes)} attendues.'
            )
        return output_path


    def compute_selected_indices(self, stack_path, work_dir, acq_label):
        selected = {}
        if self.ndvi_check.isChecked():
            selected['NDVI'] = ('B08', 'B04', lambda nir, red: np.where((nir + red) != 0, (nir - red) / (nir + red), np.nan))
        if self.ndwi_check.isChecked():
            # NDWI = (GREEN - NIR) / (GREEN + NIR) — arr_a=B08=NIR, arr_b=B03=GREEN
            selected['NDWI'] = ('B03', 'B08', lambda green, nir: np.where((green + nir) != 0, (green - nir) / (green + nir), np.nan))
        if self.ndbi_check.isChecked():
            selected['NDBI'] = ('B11', 'B08', lambda swir1, nir: np.where((swir1 + nir) != 0, (swir1 - nir) / (swir1 + nir), np.nan))
        if self.ndmi_check.isChecked():
            selected['NDMI'] = ('B08', 'B11', lambda nir, swir1: np.where((nir + swir1) != 0, (nir - swir1) / (nir + swir1), np.nan))

        if not selected:
            return {}

        dataset = gdal.Open(stack_path)
        if dataset is None:
            raise Exception(f"Impossible d’ouvrir la couche finale pour les indices ({acq_label}).")

        band_positions = {code: index for index, code in enumerate(SENTINEL2_BANDS, start=1)}  # noqa: F841 (unused, kept for reference)
        # Vérifie les bandes présentes dans le fichier
        present_bands = []
        for i in range(1, dataset.RasterCount + 1):
            desc = dataset.GetRasterBand(i).GetDescription()
            if desc:
                present_bands.append(desc)
            else:
                # fallback: suppose l'ordre
                present_bands.append(SENTINEL2_BANDS[i-1])

        needed_bands = set()
        for v in selected.values():
            needed_bands.add(v[0])
            needed_bands.add(v[1])
        missing = [b for b in needed_bands if b not in present_bands]
        if missing:
            QgsMessageLog.logMessage(
                f"Bandes présentes dans le fichier : {', '.join(present_bands)}",
                'Sentinel2Downloader',
                Qgis.Info
            )
            QgsMessageLog.logMessage(
                f"Bandes nécessaires pour les indices : {', '.join(needed_bands)}",
                'Sentinel2Downloader',
                Qgis.Info
            )
            QgsMessageLog.logMessage(f"Bandes manquantes : {', '.join(missing)}", 'Sentinel2Downloader', Qgis.Warning)

        # Associe code -> index pour lecture
        band_index_by_code = {desc: i+1 for i, desc in enumerate(present_bands)}
        source_data = {}
        for code in needed_bands:
            source_data[code] = dataset.GetRasterBand(band_index_by_code[code]).ReadAsArray().astype(np.float32)

        index_paths = {}
        # Horodatage pour éviter conflit si le fichier est déjà ouvert dans QGIS
        ts = datetime.datetime.now().strftime('%H%M%S')
        index_dir = os.path.join(work_dir, f'{acq_label.replace("/", "-")}_indices')
        os.makedirs(index_dir, exist_ok=True)

        for index_name, (band_a_code, band_b_code, calc_fn) in selected.items():
            output_path = os.path.join(index_dir, f'{index_name}_{ts}.tif')
            arr_a = source_data[band_a_code]
            arr_b = source_data[band_b_code]
            result = np.asarray(calc_fn(arr_a, arr_b), dtype=np.float32)
            result = np.where(np.isnan(result), -9999.0, result)

            driver = gdal.GetDriverByName('GTiff')
            out = driver.Create(
                output_path,
                dataset.RasterXSize,
                dataset.RasterYSize,
                1,
                gdal.GDT_Float32,
                options=['COMPRESS=LZW', 'TILED=YES'],
            )
            out.SetGeoTransform(dataset.GetGeoTransform())
            out.SetProjection(dataset.GetProjection())
            band = out.GetRasterBand(1)
            band.SetNoDataValue(-9999.0)
            band.WriteArray(result)
            band.FlushCache()
            out.FlushCache()
            out = None
            index_paths[index_name] = output_path

        dataset = None
        return index_paths

    def compute_selected_radar_indices(self, stack_path, work_dir, acq_label):
        """
        Calcule les indices radar sélectionnés depuis le stack Sentinel-1 (VV bande 1, VH bande 2).
        Les bandes du stack sont en sigma0 dB (sorties de SH Processing API).

        Formules (toutes basées sur VV et VH en linéaire sauf VV/VH) :
          RVI   — Radar Vegetation Index
                  Kim & van Zyl (2009) : (4 * VH_lin) / (VV_lin + VH_lin)
                  Plage [0, 1] — proche de 1 = végétation dense.

          VV/VH — rapport de polarisation (linéaire)
                  VV_lin / VH_lin
                  Valeurs élevées = sol nu / zones urbanisées.
                  Valeurs faibles = végétation / humidité.

          NDPI  — Normalized Difference Polarization Index
                  (VV_lin - VH_lin) / (VV_lin + VH_lin)
                  Analogue au NDVI mais en radar ; plage [-1, 1].
                  Valeurs positives = sol nu/bâti ; négatives = végétation/eau.

          DPSVI — Dual-Pol SAR Vegetation Index
                  Periasamy (2018) : (VV_lin * VH_lin) / VV_lin²  →  VH_lin / VV_lin
                  Sensible à la structure du couvert végétal.
                  Plage [0, ∞[, valeurs élevées = végétation structurée.
        """
        selected = {}
        if self.rvi_check.isChecked():
            selected['RVI']   = True
        if self.vvvh_check.isChecked():
            selected['VVVH']  = True
        if self.ndpi_check.isChecked():
            selected['NDPI']  = True
        if self.dpsvi_check.isChecked():
            selected['DPSVI'] = True

        if not selected:
            return {}

        dataset = gdal.Open(stack_path, gdal.GA_ReadOnly)
        if dataset is None:
            raise Exception(f"Impossible d'ouvrir la couche radar pour les indices ({acq_label}).")

        n_bands = dataset.RasterCount
        if n_bands < 1:
            raise Exception(f'Aucune bande dans le stack radar ({acq_label}).')

        NODATA_DB  = -9999.0  # valeur nodata réelle du GeoTIFF SH
        NODATA_OUT = -9999.0

        # ── Lecture bandes dB ──────────────────────────────────────────
        vv_db = dataset.GetRasterBand(1).ReadAsArray().astype(np.float32)
        has_vh = n_bands >= 2
        if has_vh:
            vh_db = dataset.GetRasterBand(2).ReadAsArray().astype(np.float32)
        else:
            QgsMessageLog.logMessage(
                f'{acq_label} : bande VH absente — indices radar non calculables.',
                'Sentinel2Downloader', Qgis.Warning,
            )
            dataset = None
            return {}

        # ── Masque NoData ──────────────────────────────────────────────
        nodata_mask = (vv_db == NODATA_DB) | (vh_db == NODATA_DB)

        # ── Conversion dB → linéaire (puissance) ──────────────────────
        # sigma0_lin = 10^(dB/10)  (puissance, pas amplitude)
        def db_to_lin(arr):
            return np.where(
                arr == NODATA_DB,
                np.nan,
                10.0 ** (arr / 10.0),
            )

        vv_lin = db_to_lin(vv_db)
        vh_lin = db_to_lin(vh_db)

        # ── Formules ───────────────────────────────────────────────────
        def calc_rvi():
            denom = vv_lin + vh_lin
            return np.where(
                (~nodata_mask) & (denom > 0),
                (4.0 * vh_lin) / denom,
                np.nan,
            )

        def calc_vvvh():
            return np.where(
                (~nodata_mask) & (vh_lin > 0),
                vv_lin / vh_lin,
                np.nan,
            )

        def calc_ndpi():
            denom = vv_lin + vh_lin
            return np.where(
                (~nodata_mask) & (denom > 0),
                (vv_lin - vh_lin) / denom,
                np.nan,
            )

        def calc_dpsvi():
            # DPSVI = VH_lin / VV_lin  (Periasamy 2018, forme simplifiée)
            return np.where(
                (~nodata_mask) & (vv_lin > 0),
                vh_lin / vv_lin,
                np.nan,
            )

        formulas = {
            'RVI':   calc_rvi,
            'VVVH':  calc_vvvh,
            'NDPI':  calc_ndpi,
            'DPSVI': calc_dpsvi,
        }

        ts = datetime.datetime.now().strftime('%H%M%S')
        index_dir = os.path.join(work_dir, f'{acq_label.replace("/", "-")}_radar_indices')
        os.makedirs(index_dir, exist_ok=True)
        index_paths = {}

        for index_name in selected:
            output_path = os.path.join(index_dir, f'{index_name}_{ts}.tif')
            result = formulas[index_name]().astype(np.float32)
            result = np.where(np.isnan(result), NODATA_OUT, result)

            driver = gdal.GetDriverByName('GTiff')
            out = driver.Create(
                output_path,
                dataset.RasterXSize,
                dataset.RasterYSize,
                1,
                gdal.GDT_Float32,
                options=['COMPRESS=LZW', 'TILED=YES'],
            )
            out.SetGeoTransform(dataset.GetGeoTransform())
            out.SetProjection(dataset.GetProjection())
            b = out.GetRasterBand(1)
            b.SetNoDataValue(NODATA_OUT)
            b.SetDescription(index_name)
            b.WriteArray(result)
            b.FlushCache()
            out.FlushCache()
            out = None
            index_paths[index_name] = output_path
            QgsMessageLog.logMessage(
                f'{acq_label} — indice radar {index_name} calculé : {output_path}',
                'Sentinel2Downloader', Qgis.Info,
            )

        dataset = None
        return index_paths

    def apply_radar_rendering(self, layer):
        """Configure le rendu QGIS pour une couche radar dB reçue via SH Processing API."""
        try:
            provider = layer.dataProvider()
            renderer = QgsSingleBandGrayRenderer(provider, 1)

            enhancement = QgsContrastEnhancement(provider.dataType(1))
            enhancement.setContrastEnhancementAlgorithm(
                QgsContrastEnhancement.StretchToMinimumMaximum
            )

            # Calcul des stats réelles sur l'étendue complète (pas d'estimation)
            stats = provider.bandStatistics(1, 0xFF, layer.extent(), 0)
            min_val = stats.minimumValue
            max_val = stats.maximumValue

            # Valeurs sigma0 dB typiques Sentinel-1 : -25 à +5 dB
            # Si les stats semblent aberrantes on force une plage typique
            if max_val > 50 or min_val >= 0 or (max_val - min_val) < 1:
                min_val = -25.0
                max_val = 5.0

            enhancement.setMinimumValue(min_val)
            enhancement.setMaximumValue(max_val)

            origin = QgsRasterMinMaxOrigin()
            origin.setLimits(QgsRasterMinMaxOrigin.MinMax)
            renderer.setMinMaxOrigin(origin)
            renderer.setContrastEnhancement(enhancement)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
        except Exception as err:
            QgsMessageLog.logMessage(
                f'apply_radar_rendering ignoré : {err}',
                'Sentinel2Downloader', Qgis.Warning,
            )

    def _percentile_stretch(self, tif_path, band_index, low_pct=2.0, high_pct=98.0):
        """
        Calcule les percentiles low_pct / high_pct d'une bande GDAL en ignorant
        les pixels NoData (valeur 0 pour S2 L2A SH).
        Retourne (min_val, max_val) pour le ContrastEnhancement.
        """
        ds = gdal.Open(tif_path, gdal.GA_ReadOnly)
        if ds is None:
            return 0, 3000
        band = ds.GetRasterBand(band_index)
        nodata = band.GetNoDataValue()
        data = band.ReadAsArray().astype(np.float32)
        ds = None

        # Masque NoData uniquement — ne pas exclure les valeurs négatives
        # qui sont des valeurs d'indices légitimes (NDVI<0 = eau, NDBI<0 = végétation…)
        mask = np.ones(data.shape, dtype=bool)
        if nodata is not None:
            mask &= data != nodata
        # Exclure seulement les pixels à 0 si nodata n'est pas déclaré (heuristique S2 brut)
        if nodata is None:
            mask &= data != 0
        valid = data[mask]

        if valid.size == 0:
            return 0, 3000

        p_low  = float(np.percentile(valid, low_pct))
        p_high = float(np.percentile(valid, high_pct))
        if p_high <= p_low:
            p_high = p_low + 1
        return p_low, p_high

    def apply_optical_rendering(self, layer, tif_path=None):
        """
        Applique un rendu vraie couleur (B04=R, B03=G, B02=B) avec étirement
        percentile 2%–98% calculé via GDAL sur les pixels valides.
        provider.bandStatistics() est évité car il inclut les NoData et renvoie
        des bornes aberrantes qui donnent une image noire dans QGIS.
        """
        try:
            from qgis.core import (
                QgsMultiBandColorRenderer,
                QgsContrastEnhancement,
                QgsRasterMinMaxOrigin,
            )
            provider = layer.dataProvider()
            n_bands  = layer.bandCount()

            # Ordre du stack : B01=1, B02=2, B03=3, B04=4, …
            red_band   = 4  # B04
            green_band = 3  # B03
            blue_band  = 2  # B02
            if n_bands < 4:
                red_band = green_band = blue_band = 1

            renderer = QgsMultiBandColorRenderer(provider, red_band, green_band, blue_band)

            # Chemin du fichier source pour le calcul percentile GDAL
            src_path = tif_path or layer.source()

            def make_enhancement(band_index):
                enhancement = QgsContrastEnhancement(provider.dataType(band_index))
                enhancement.setContrastEnhancementAlgorithm(
                    QgsContrastEnhancement.StretchToMinimumMaximum
                )
                if src_path:
                    min_val, max_val = self._percentile_stretch(src_path, band_index)
                else:
                    # Fallback : plage typique S2 L2A en zone tempérée
                    min_val, max_val = 0, 3000
                QgsMessageLog.logMessage(
                    f'Band {band_index} stretch : {min_val:.0f} – {max_val:.0f}',
                    'Sentinel2Downloader', Qgis.Info,
                )
                enhancement.setMinimumValue(min_val)
                enhancement.setMaximumValue(max_val)
                return enhancement

            renderer.setRedContrastEnhancement(make_enhancement(red_band))
            renderer.setGreenContrastEnhancement(make_enhancement(green_band))
            renderer.setBlueContrastEnhancement(make_enhancement(blue_band))

            origin = QgsRasterMinMaxOrigin()
            origin.setLimits(QgsRasterMinMaxOrigin.MinMax)
            renderer.setMinMaxOrigin(origin)

            layer.setRenderer(renderer)
            layer.triggerRepaint()
        except Exception as err:
            QgsMessageLog.logMessage(
                f'apply_optical_rendering ignoré : {err}',
                'Sentinel2Downloader', Qgis.Warning,
            )

    def apply_index_rendering(self, layer, index_path):
        """Étirement Min/Max percentile 2-98% pour les couches indices (FLOAT32)."""
        try:
            provider = layer.dataProvider()
            enhancement = QgsContrastEnhancement(provider.dataType(1))
            enhancement.setContrastEnhancementAlgorithm(
                QgsContrastEnhancement.StretchToMinimumMaximum
            )
            min_val, max_val = self._percentile_stretch(index_path, 1, low_pct=2.0, high_pct=98.0)
            enhancement.setMinimumValue(min_val)
            enhancement.setMaximumValue(max_val)

            renderer = QgsSingleBandGrayRenderer(provider, 1)
            origin = QgsRasterMinMaxOrigin()
            origin.setLimits(QgsRasterMinMaxOrigin.MinMax)
            renderer.setMinMaxOrigin(origin)
            renderer.setContrastEnhancement(enhancement)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
        except Exception as err:
            QgsMessageLog.logMessage(
                f'apply_index_rendering ignoré : {err}',
                'Sentinel2Downloader', Qgis.Warning,
            )

    def show_cadre_layer(self, aoi_wkt):
        for layer in QgsProject.instance().mapLayersByName(CADRE_LAYER_NAME):
            QgsProject.instance().removeMapLayer(layer.id())

        geometry = QgsGeometry.fromWkt(aoi_wkt)
        layer = QgsVectorLayer('Polygon?crs=EPSG:4326', CADRE_LAYER_NAME, 'memory')
        provider = layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField('info', QVariant.String))
        provider.addAttributes(fields)
        layer.updateFields()
        feature = QgsFeature(fields)
        feature.setGeometry(geometry)
        feature.setAttributes(['Zone Sentinel-2'])
        provider.addFeatures([feature])
        layer.updateExtents()
        symbol = QgsFillSymbol.createSimple({
            'color': '0,0,255,30',
            'outline_color': '0,0,255,255',
            'outline_width': '1.2',
        })
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        QgsProject.instance().addMapLayer(layer)

    def validate_inputs(self):
        start = datetime.date(
            self.start_date.date().year(),
            self.start_date.date().month(),
            self.start_date.date().day(),
        )
        end = datetime.date(
            self.end_date.date().year(),
            self.end_date.date().month(),
            self.end_date.date().day(),
        )
        if end < start:
            raise Exception('La date « Au » doit être après « Du ».')

        try:
            lat = float(self.lat_edit.text().strip())
            lon = float(self.lon_edit.text().strip())
            buffer_km = float(self.buffer_edit.text().strip())
        except ValueError:
            raise Exception('Latitude, longitude et buffer doivent être des nombres.')

        # Credentials hardcodés — plus besoin de variables d'environnement
        sh_client_id     = 'sh-45d855eb-ab8f-410b-895a-e6035c6b609f'
        sh_client_secret = '9XLZqSjGVZ9nuSnRFqccmwvDd5qdtpHD'
        user             = 'bboutaina506@gmail.com'
        password         = 'axR::7vE5W74HeD'

        return {
            'start_date': start,
            'end_date': end,
            'lat': lat,
            'lon': lon,
            'buffer_km': buffer_km,
            'product_type': self.product_type_combo.currentData(),
            'user': user,
            'password': password,
            'sh_client_id': sh_client_id,
            'sh_client_secret': sh_client_secret,
        }

    def create_cdse_session(self, requests, username, password):
        data = {
            'client_id': CDSE_CLIENT_ID,
            'grant_type': 'password',
            'username': username,
            'password': password,
        }
        totp = ''  # TOTP non utilisé
        if totp:
            data['totp'] = totp
        response = requests.post(CDSE_TOKEN_URL, data=data, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            raise Exception(f'Connexion CDSE échouée ({response.status_code}).')
        token = response.json().get('access_token')
        session = requests.Session()
        session.headers['Authorization'] = f'Bearer {token}'
        return session

    def search_products(self, requests, aoi, start_date, end_date, product_type):
        start_iso = f'{start_date.isoformat()}T00:00:00.000Z'
        end_iso = f'{end_date.isoformat()}T23:59:59.999Z'

        if product_type == 'radar':
            filter_query = (
                f"Collection/Name eq 'SENTINEL-1' and "
                f"Attributes/OData.CSC.StringAttribute/any("
                f"att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'GRD'"
                f") and "
                f"OData.CSC.Intersects(area=geography'SRID=4326;{aoi}') and "
                f'ContentDate/Start gt {start_iso} and ContentDate/Start lt {end_iso}'
            )
        else:
            filter_query = (
                f"Collection/Name eq 'SENTINEL-2' and "
                f"Attributes/OData.CSC.StringAttribute/any("
                f"att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A'"
                f") and "
                f"OData.CSC.Intersects(area=geography'SRID=4326;{aoi}') and "
                f'ContentDate/Start gt {start_iso} and ContentDate/Start lt {end_iso}'
            )

        response = requests.get(
            f'{CDSE_CATALOGUE_URL}/Products',
            params={
                '$filter': filter_query,
                '$expand': 'Attributes',
                '$orderby': 'ContentDate/Start asc',
                '$top': 100,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise Exception(f'Recherche échouée ({response.status_code}).')

        aoi_geom = QgsGeometry.fromWkt(aoi)
        products = []
        for item in response.json().get('value', []):
            if not self.product_intersects_aoi(item, aoi_geom):
                continue
            name = item['Name']
            acq_label = self.format_acq_label(name, item.get('ContentDate'))
            scene_id = (
                f"{acq_label}_{item['Id'][:8]}"
                if product_type == 'radar'
                else f"{acq_label}_{self.tile_from_name(name)}"
            )
            product = {
                'Id': item['Id'],
                'Name': name,
                'acq_label': acq_label,
                'scene_id': scene_id,
            }
            if product_type == 'optique':
                product['cloud_cover'] = self.cloud_cover(item.get('Attributes', []))
            products.append(product)
        return products

    def product_intersects_aoi(self, item, aoi_geom):
        footprint = item.get('GeoFootprint') or item.get('ContentGeometry') or item.get('Footprint')
        if not footprint:
            return True
        if isinstance(footprint, dict):
            return True
        try:
            product_geom = QgsGeometry.fromWkt(footprint)
        except Exception:
            return True
        if not product_geom or not product_geom.isGeosValid():
            return True
        return bool(product_geom.intersects(aoi_geom))

    def format_acq_label(self, name, content_date):
        if content_date and content_date.get('Start'):
            try:
                day = datetime.date.fromisoformat(content_date['Start'][:10])
                return day.strftime('%d/%m/%Y')
            except ValueError:
                pass
        match = re.search(r'_(\d{8})T', name)
        if match:
            raw = match.group(1)
            return f'{raw[6:8]}/{raw[4:6]}/{raw[0:4]}'
        return '?'

    def tile_from_name(self, name):
        match = re.search(r'_T(\d{2}[A-Z]{3})_', name)
        if match:
            return match.group(1)

        match = re.search(r'_(\d{8}T\d{6})', name)
        if match:
            return match.group(1)

        return name[-8:] if len(name) >= 8 else name

    def cloud_cover(self, attributes):
        for attribute in attributes or []:
            if attribute.get('Name') == 'cloudCover':
                return float(attribute.get('Value', 100))
        return 100.0

    def is_valid_zip_file(self, path):
        if not path or not os.path.isfile(path):
            return False
        return zipfile.is_zipfile(path)

    def is_valid_raster_file(self, path):
        if not path or not os.path.isfile(path):
            return False
        if os.path.getsize(path) < 1024:
            return False
        dataset = gdal.Open(path, gdal.GA_ReadOnly)
        if dataset is None:
            return False
        valid = dataset.RasterCount > 0 and dataset.RasterXSize > 0 and dataset.RasterYSize > 0
        dataset = None
        return valid

    def ensure_valid_zip(self, session, product_id, output_path):
        if self.is_valid_zip_file(output_path):
            return
        if os.path.exists(output_path):
            os.remove(output_path)
        self.download_product_zip(session, product_id, output_path)
        if not self.is_valid_zip_file(output_path):
            raise Exception(f'Archive téléchargée invalide pour le produit {product_id}.')

    def download_product_zip(self, session, product_id, output_path):
        url = f'{CDSE_DOWNLOAD_URL}/Products({product_id})/$value'
        last_error = None

        for attempt in range(1, 4):
            temp = output_path + '.part'
            if os.path.exists(temp):
                os.remove(temp)

            try:
                response = session.get(url, stream=True, allow_redirects=False, timeout=DOWNLOAD_TIMEOUT)
                while response.status_code in (301, 302, 303, 307):
                    url = response.headers.get('Location')
                    if not url:
                        raise Exception('Redirection CDSE sans URL de destination.')
                    response = session.get(url, stream=True, allow_redirects=False, timeout=DOWNLOAD_TIMEOUT)

                if response.status_code != 200:
                    raise Exception(f'Téléchargement échoué ({response.status_code}).')

                expected_size = response.headers.get('Content-Length')
                expected_size = int(expected_size) if expected_size and expected_size.isdigit() else None
                written = 0

                with open(temp, 'wb') as handle:
                    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        written += len(chunk)

                if expected_size is not None and written != expected_size:
                    raise Exception(f'Téléchargement incomplet ({written}/{expected_size} octets).')

                os.replace(temp, output_path)
                if not self.is_valid_zip_file(output_path):
                    raise Exception(f'Archive téléchargée invalide ou vide pour le produit {product_id}.')
                return
            except Exception as error:
                if os.path.exists(temp):
                    os.remove(temp)
                last_error = error
                if attempt == 3:
                    break
                self.set_status(
                    f'Erreur téléchargement (tentative {attempt}/3) : {error}. Nouvelle tentative...'
                )
                QApplication.processEvents()
                time.sleep(2 ** (attempt - 1))

        raise Exception(f'Téléchargement échoué après 3 tentatives : {last_error}')

    def build_odata_aoi(self, lat, lon, buffer_km):
        src = QgsCoordinateReferenceSystem('EPSG:4326')
        dst = QgsCoordinateReferenceSystem('EPSG:3857')
        to_m = QgsCoordinateTransform(src, dst, QgsProject.instance())
        to_deg = QgsCoordinateTransform(dst, src, QgsProject.instance())
        center = to_m.transform(QgsPointXY(lon, lat))
        d = buffer_km * 1000.0
        corners = [
            QgsPointXY(center.x() - d, center.y() - d),
            QgsPointXY(center.x() + d, center.y() - d),
            QgsPointXY(center.x() + d, center.y() + d),
            QgsPointXY(center.x() - d, center.y() + d),
        ]
        ring = [to_deg.transform(point) for point in corners]
        ring.append(ring[0])
        coords = ','.join(
            f'{self.fmt_coord(point.x())} {self.fmt_coord(point.y())}' for point in ring
        )
        return f'POLYGON(({coords}))'

    def fmt_coord(self, value):
        return format(float(value), '.8f').rstrip('0').rstrip('.') or '0'

    def set_status(self, message):
        self.status_label.setText(message)
        QgsMessageLog.logMessage(message, 'Sentinel2Downloader', Qgis.Info)

    def show_error(self, message):
        self.set_status('Erreur : ' + message)
        QMessageBox.critical(self, 'Sentinel-2 Downloader', message)
