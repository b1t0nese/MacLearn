from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer
import win32process
import win32gui
import win32con



class EmbeddedProgramWidget(QWidget):
    def __init__(self, process_name):
        super().__init__()
        self.program_hwnd = None
        self.process_name = process_name
        self.embed_attempted = False
        self.locked_resize = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self.embed_attempted:
            self.embed_program()
            self.embed_attempted = True
            self.start_update()

    def start_update(self):
        if not hasattr(self, 'update_timer'):
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_window)
            self.update_timer.start(100)


    def embed_program(self):
        if self.program_hwnd:
            return

        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    import psutil
                    process = psutil.Process(pid)
                    process_name = process.name().lower()
                    if self.process_name == process_name:
                        results.append(hwnd)
                except:
                    title = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    if 'Chrome_WidgetWin' in class_name:
                        results.append(hwnd)
            return True

        program_windows = []
        win32gui.EnumWindows(enum_callback, program_windows)
        if program_windows:
            self.program_hwnd = program_windows[-1]
            self.set_window_style()
            win32gui.SetParent(self.program_hwnd, int(self.winId()))


    def move_window(self):
        if self.program_hwnd and not self.locked_resize:
            win32gui.MoveWindow(
                self.program_hwnd, 0, 0,
                self.width(), self.height(), True)
    
    def set_lock_resize(self, boolean):
        self.locked_resize = boolean

    def set_window_style(self):
        if self.program_hwnd:
            style = win32gui.GetWindowLong(self.program_hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | 
                       win32con.WS_MINIMIZEBOX | win32con.WS_MAXIMIZEBOX | 
                       win32con.WS_SYSMENU | win32con.WS_BORDER | win32con.WS_DLGFRAME)
            win32gui.SetWindowLong(self.program_hwnd, win32con.GWL_STYLE, style)

    def update_window(self):
        if self.program_hwnd:
            self.set_window_style()
            self.move_window()
            win32gui.ShowWindow(self.program_hwnd, win32con.SW_SHOW)
            win32gui.UpdateWindow(self.program_hwnd)



if __name__=="__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    process_name = input('Введите название процесса приложения (пример "chrome.exe"): ')
    app = QApplication(sys.argv)
    window = EmbeddedProgramWidget(process_name)
    window.show()
    sys.exit(app.exec())