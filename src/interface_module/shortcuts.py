from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication,
                               QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QWidget)

from logger import get_logger

log = get_logger("interface")



TEXT_INPUTS = (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox)

PLAIN_MODIFIERS = (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier)



class ShortcutBinder(QObject):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self.key_bindings: dict[str, QAbstractButton] = {}
        self._bound_buttons: set[int] = set()
        self._bound_actions: set[int] = set()
        self._taken_keys: set[str] = set()
        self._taken_letters: set[str] = set()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.rebuild()



    def rebuild(self):
        for button in self.window.findChildren(QAbstractButton):
            if id(button) in self._bound_buttons or not button.text():
                continue
            key = self._free_key(button.text(), self._taken_keys)
            if not key:
                continue
            self._taken_keys.add(key)
            self._bound_buttons.add(id(button))
            self.key_bindings[key] = button
            self._append_hint(button, key)
        for action in self.window.findChildren(QAction):
            if id(action) in self._bound_actions or not action.text():
                continue
            letter = self._free_key(action.text(), self._taken_letters)
            if not letter:
                continue
            self._taken_letters.add(letter)
            self._bound_actions.add(id(action))
            shortcut = QKeySequence(f"Ctrl+{letter}")
            action.setShortcut(shortcut)
            self._append_hint(action, shortcut.toString())
        log.debug("ShortcutBinder: %d plain keys, %d menu combos bound to %s",
                  len(self.key_bindings), len(self._bound_actions), self.window.objectName())



    @staticmethod
    def _free_key(text: str, taken: set) -> str:
        for char in text:
            if char.isspace():
                continue
            key = char.upper()
            if key not in taken:
                return key
        return ""



    @staticmethod
    def _append_hint(element, hint: str):
        tooltip = element.toolTip()
        if f"[{hint}]" in tooltip:
            return
        tooltip = f"{tooltip}\n" if tooltip else ""
        element.setToolTip(f"{tooltip}[{hint}]")



    def eventFilter(self, watched, event):
        try:
            return self._handle_event(watched, event)
        except RuntimeError:
            return False



    def _handle_event(self, watched, event):
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        if event.modifiers() not in PLAIN_MODIFIERS or not event.text():
            return super().eventFilter(watched, event)
        if not self.key_bindings or watched.window() is not self.window:
            return super().eventFilter(watched, event)
        focus = self.window.focusWidget()
        if focus is None or isinstance(focus, TEXT_INPUTS):
            return super().eventFilter(watched, event)
        button = self.key_bindings.get(event.text().upper())
        if button is None or not button.isVisible() or not button.isEnabled():
            return super().eventFilter(watched, event)
        button.animateClick()
        return True
