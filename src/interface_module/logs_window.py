from PyQt6.QtWidgets import QApplication, QWidget
from typing import Callable
from PyQt6 import uic
from datetime import datetime
import logging
import sys
import os


if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
uis_path = os.path.join(base_path, "uis")



class LogsUIHandler(logging.Handler):
    def __init__(self, logs_window: "LogsUI", level=logging.NOTSET):
        super().__init__(level)
        self.logs_window = logs_window

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        try:
            self.logs_window.log(msg)
        except Exception:
            self.handleError(record)



class LogsUI(QWidget):
    def __init__(self, logger_name: str = None):
        super().__init__()
        self.opened = True
        self._target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        self._handler = LogsUIHandler(self)
        self._handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        self._target_logger.addHandler(self._handler)

        uic.loadUi(os.path.join(uis_path, "logswindow.ui"), self)
        self.btn_action.clicked.connect(self.closeEvent)

    def closeEvent(self, e=None):
        self.opened = False
        self._target_logger.removeHandler(self._handler)
        self._handler.close()
        self.close()

    def log(self, text: str, otstup: int=0):
        if isinstance(text, str) and not text.startswith("["):
            self.text_logs.append('\n'*otstup+f'[{datetime.now().strftime("%H:%M:%S")}] {text}')
        else:
            self.text_logs.append(text)
        QApplication.processEvents()

    def clear(self):
        self.text_logs.clear()

    def set_progress(self, progress: int=0):
        self.progress_bar.setValue(progress)

    def set_button(self, text="Закрыть", style="font-size: 14px; font-weight: bold;", what_do: Callable=None):
        self.btn_action.setText(text)
        self.btn_action.setStyle(style)
        self.btn_action.clicked.connect(what_do if what_do is not None else self.deleteLater)

    def wait_while_not_exit(self):
        while self.opened:
            QApplication.processEvents()