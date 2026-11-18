import json
import os
import sys

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QGroupBox, QLabel, QLineEdit, QMenu,
                               QPushButton, QRadioButton, QTabBar, QTabWidget,
                               QTableWidget, QWidget)



SOURCE_LANGUAGE = "ru"

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
translations_path = os.path.join(base_path, "translations")

LANGUAGES = {}
_TRANSLATIONS = {}
_REVERSE_TRANSLATIONS = []
_current_language = SOURCE_LANGUAGE



def _load_translations():
    if not os.path.isdir(translations_path):
        return
    for filename in sorted(os.listdir(translations_path)):
        language_code, extension = os.path.splitext(filename)
        if extension != ".json":
            continue
        try:
            with open(os.path.join(translations_path, filename), "r", encoding="utf-8") as translations_file:
                translation_data = json.load(translations_file)
        except (OSError, ValueError):
            continue
        if not isinstance(translation_data, dict):
            continue
        strings = translation_data.get("translations", {})
        if not isinstance(strings, dict):
            continue
        LANGUAGES[language_code] = translation_data.get("name") or language_code
        _TRANSLATIONS[language_code] = {key: value for key, value in strings.items()
                                        if isinstance(key, str) and isinstance(value, str)}
        _REVERSE_TRANSLATIONS.append({value: key for key, value in _TRANSLATIONS[language_code].items()})



_load_translations()
LANGUAGES.setdefault(SOURCE_LANGUAGE, "Русский")
_TRANSLATIONS.setdefault(SOURCE_LANGUAGE, {})



def get_language() -> str:
    return _current_language



def set_language(language_code: str):
    global _current_language
    if language_code not in LANGUAGES:
        return
    _current_language = language_code



def tr(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    source_text = text
    for reverse_strings in _REVERSE_TRANSLATIONS:
        if text in reverse_strings:
            source_text = reverse_strings[text]
            break
    if _current_language == SOURCE_LANGUAGE:
        return source_text
    return _TRANSLATIONS.get(_current_language, {}).get(source_text, source_text)



def retranslate(widget: QWidget):
    widgets = [widget, *widget.findChildren(QWidget)]
    for target in widgets:
        target.setWindowTitle(tr(target.windowTitle()))
        target.setToolTip(tr(target.toolTip()))
        if isinstance(target, (QLabel, QPushButton, QCheckBox, QRadioButton)):
            target.setText(tr(target.text()))
        elif isinstance(target, QLineEdit):
            target.setPlaceholderText(tr(target.placeholderText()))
        elif isinstance(target, (QGroupBox, QMenu)):
            target.setTitle(tr(target.title()))
        elif isinstance(target, QTabWidget):
            for index in range(target.count()):
                target.setTabText(index, tr(target.tabText(index)))
        elif isinstance(target, QTabBar):
            for index in range(target.count()):
                target.setTabText(index, tr(target.tabText(index)))
        elif isinstance(target, QTableWidget):
            for column in range(target.columnCount()):
                header_item = target.horizontalHeaderItem(column)
                if header_item is not None:
                    header_item.setText(tr(header_item.text()))
    for action in widget.findChildren(QAction):
        action.setText(tr(action.text()))
