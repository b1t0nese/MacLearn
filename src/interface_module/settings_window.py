from PySide6.QtWidgets import QWidget, QFileDialog
from pcfuncs import EXECUTABLE_SUFFIX
from typing import Callable
import sys
import os

from logger import get_logger
from settings import DEFAULT_SETTINGS
from interface_module.translations import LANGUAGES
from interface_module.shortcuts import ShortcutBinder
from interface_module.ui_loader import loadUi



if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
uis_path = os.path.join(base_path, "uis")

log = get_logger("main")



AUGMENTATION_FIELDS = {
    "crop": "dspin_aug_crop",
    "hflip": "dspin_aug_hflip",
    "vflip": "dspin_aug_vflip",
    "rotate90": "dspin_aug_rotate90",
    "shift_scale_rotate": "dspin_aug_shift_scale_rotate",
    "color": "dspin_aug_color",
    "noise": "dspin_aug_noise",
    "blur": "dspin_aug_blur",
}



class SettingsWindow(QWidget):
    def __init__(self, settings: dict, on_save: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self._on_save = on_save
        loadUi(os.path.join(uis_path, "settingswindow.ui"), self)
        self.combo_sam3_device.addItems(["cpu", "cuda", "mps"])
        for language_code, language_name in LANGUAGES.items():
            self.combo_language.addItem(language_name, language_code)
        self.btn_browse_chromedriver.clicked.connect(self.browse_chromedriver)
        self.btn_browse_sam3_weights.clicked.connect(self.browse_sam3_weights)
        self.btn_save_settings.clicked.connect(self.save_settings)
        self.btn_close_settings.clicked.connect(self.close)
        self.fill(settings)
        self.shortcut_binder = ShortcutBinder(self)
        log.debug("Settings window opened")



    def fill(self, settings: dict):
        defaults = DEFAULT_SETTINGS
        language_index = self.combo_language.findData(settings.get("language", defaults["language"]))
        self.combo_language.setCurrentIndex(max(0, language_index))
        self.edit_chromedriver_path.setText(settings.get("chromedriver_path", defaults["chromedriver_path"]) or "")
        self.spin_chrome_version.setValue(int(settings.get("chrome_version", defaults["chrome_version"]) or 0))
        self.edit_chrome_session.setText(settings.get("chrome_session", defaults["chrome_session"]) or "default")
        self.check_chrome_no_headless.setChecked(bool(settings.get("chrome_no_headless", defaults["chrome_no_headless"])))
        device_index = self.combo_sam3_device.findText(str(settings.get("sam3_device", defaults["sam3_device"])))
        self.combo_sam3_device.setCurrentIndex(max(0, device_index))
        self.dspin_sam3_confidence.setValue(float(settings.get("sam3_confidence", defaults["sam3_confidence"])))
        self.spin_sam3_min_area.setValue(int(settings.get("sam3_min_box_area_px", defaults["sam3_min_box_area_px"])))
        self.edit_sam3_weights_path.setText(settings.get("sam3_weights_path", defaults["sam3_weights_path"]) or "")
        self.check_sam3_one_detection.setChecked(bool(settings.get("sam3_one_detection_per_class", defaults["sam3_one_detection_per_class"])))
        preset = settings.get("augmentation_preset", defaults["augmentation_preset"])
        for preset_key, field_name in AUGMENTATION_FIELDS.items():
            getattr(self, field_name).setValue(float(preset.get(preset_key, defaults["augmentation_preset"][preset_key])))



    def collect(self) -> dict:
        settings = {key: value for key, value in DEFAULT_SETTINGS.items()}
        settings["language"] = self.combo_language.currentData() or DEFAULT_SETTINGS["language"]
        settings["chromedriver_path"] = self.edit_chromedriver_path.text().strip()
        settings["chrome_version"] = self.spin_chrome_version.value()
        settings["chrome_session"] = self.edit_chrome_session.text().strip() or "default"
        settings["chrome_no_headless"] = self.check_chrome_no_headless.isChecked()
        settings["sam3_device"] = self.combo_sam3_device.currentText()
        settings["sam3_confidence"] = round(self.dspin_sam3_confidence.value(), 2)
        settings["sam3_min_box_area_px"] = self.spin_sam3_min_area.value()
        settings["sam3_weights_path"] = self.edit_sam3_weights_path.text().strip()
        settings["sam3_one_detection_per_class"] = self.check_sam3_one_detection.isChecked()
        settings["augmentation_preset"] = {
            preset_key: round(getattr(self, field_name).value(), 2)
            for preset_key, field_name in AUGMENTATION_FIELDS.items()
        }
        return settings



    def browse_chromedriver(self):
        chromedriver_path, _ = QFileDialog.getOpenFileName(
            self, "chromedriver", "",
            f"chromedriver*{EXECUTABLE_SUFFIX};;All files (*)")
        if chromedriver_path:
            self.edit_chromedriver_path.setText(chromedriver_path)



    def browse_sam3_weights(self):
        weights_path, _ = QFileDialog.getOpenFileName(
            self, "SAM3", "", "Weights (*.pt *.pth);;All files (*)")
        if weights_path:
            self.edit_sam3_weights_path.setText(weights_path)



    def save_settings(self):
        settings = self.collect()
        log.info("✓ Settings collected from window (language=%s)", settings["language"])
        if self._on_save is not None:
            self._on_save(settings)
        self.close()
