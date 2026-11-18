import json
import os

from pcfuncs import get_appdata_dir



DEFAULT_AUGMENTATION_PRESET = {
    "crop": 0.5,
    "hflip": 0.3,
    "vflip": 0.2,
    "rotate90": 0.3,
    "shift_scale_rotate": 0.4,
    "color": 0.5,
    "noise": 0.3,
    "blur": 0.2,
}

DEFAULT_SETTINGS = {
    "language": "ru",
    "chromedriver_path": "",
    "chrome_version": 0,
    "chrome_no_headless": False,
    "chrome_session": "default",
    "sam3_device": "cpu",
    "sam3_confidence": 0.15,
    "sam3_min_box_area_px": 100,
    "sam3_one_detection_per_class": False,
    "sam3_weights_path": "",
    "augmentation_preset": dict(DEFAULT_AUGMENTATION_PRESET),
}



def get_settings_path() -> str:
    return os.path.join(get_appdata_dir(), "settings.json")



def load_settings() -> dict:
    settings = {key: value for key, value in DEFAULT_SETTINGS.items()}
    settings["augmentation_preset"] = dict(DEFAULT_AUGMENTATION_PRESET)
    try:
        with open(get_settings_path(), "r", encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)
    except (OSError, ValueError):
        return settings
    if not isinstance(loaded, dict):
        return settings
    for key, value in loaded.items():
        if key in settings:
            settings[key] = value
    if isinstance(settings.get("augmentation_preset"), dict):
        preset = dict(DEFAULT_AUGMENTATION_PRESET)
        preset.update({key: value for key, value in settings["augmentation_preset"].items()
                       if key in DEFAULT_AUGMENTATION_PRESET})
        settings["augmentation_preset"] = preset
    else:
        settings["augmentation_preset"] = dict(DEFAULT_AUGMENTATION_PRESET)
    return settings



def save_settings(settings: dict) -> bool:
    try:
        with open(get_settings_path(), "w", encoding="utf-8") as settings_file:
            json.dump(settings, settings_file, ensure_ascii=False, indent=4)
        return True
    except OSError:
        return False