from PyQt6.QtWidgets import QApplication, QWidget
from typing import Callable
from PyQt6 import uic
import datetime
import sys
import os


if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
uis_path = os.path.join(base_path, "uis")



class LogsUI(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi(os.path.join(uis_path, "logswindow.ui"), self)

    def log(self, text: str, otstup: int=0):
        self.text_logs.append('\n'*otstup+f'[{datetime.now().strftime("%H:%M:%S")}] {text}')
    
    def clear(self):
        self.text_logs.clear()
    
    def set_progress(self, progress: int=0):
        self.progress_bar.setValue(progress)
    
    def set_button(self, text="Закрыть", style="font-size: 14px; font-weight: bold;", what_do: Callable=None):
        self.btn_action.setText(text)
        self.btn_action.setStyle(style)
        self.btn_action.clicked.connect(what_do if what_do is not None else self.deleteLater)