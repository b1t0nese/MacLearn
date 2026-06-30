from platform import system as platf_system
from PIL import Image, ImageGrab
from plyer import notification
import numpy as np
import subprocess
import threading
import hashlib
import time
import cv2
import sys
import os



def launch_new_instance():
    if getattr(sys, 'frozen', False):
        executable, args = sys.argv[0], sys.argv[1:]
    else:
        executable, args = sys.executable, sys.argv
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(
        [executable] + args,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        startupinfo=startupinfo, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True)



class ClipboardManager:
    def __init__(self):
        self.system = platf_system().lower()
        self._win32clipboard, self._tempfile = None, None
        self._import_windows_libs()

    def _import_windows_libs(self):
        if self._win32clipboard is None:
            try:
                import win32clipboard
                self._win32clipboard = win32clipboard
            except ImportError:
                raise ImportError("Для работы с буфером обмена в Windows установите pywin32: pip install pywin32")

    def copy_image_to_clipboard(self, image: str | np.ndarray):
        if isinstance(image, str):
            if not os.path.exists(image):
                raise FileNotFoundError(f"File not found: {image}")
            image_array = np.fromfile(image, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_UNCHANGED)
        if image is not None and image.size > 0:
            if self.system == "windows":
                self._copy_windows(image)
            else:
                raise NotImplementedError(f"System {self.system} not supported")

    def _copy_windows(self, image):
        success, bmp_data = cv2.imencode('.bmp', image)
        if not success:
            raise RuntimeError("Failed to encode image to BMP")
        if self._win32clipboard:
            self._win32clipboard.OpenClipboard()
            self._win32clipboard.EmptyClipboard()
            self._win32clipboard.SetClipboardData(self._win32clipboard.CF_DIB, bmp_data.tobytes()[14:])
            self._win32clipboard.CloseClipboard()



class ClipboardImageWatcher:
    def __init__(self, callback, check_interval=0.5):
        self.callback = callback
        self.check_interval = check_interval
        self.running = False
        self.last_hash = None
        self.thread = None

    def get_image_hash(self, image):
        if image is None:
            return None
        img = image.copy()
        img.thumbnail((100, 100))
        return hashlib.md5(img.tobytes()).hexdigest()

    def check_clipboard(self):
        try:
            current_image = ImageGrab.grabclipboard()
            if current_image and isinstance(current_image, Image.Image):
                current_hash = self.get_image_hash(current_image)
                if current_hash != self.last_hash:
                    self.last_hash = current_hash
                    self.callback(current_image)
            elif current_image is None:
                self.last_hash = None
        except Exception as e:
            print(f"Ошибка при чтении буфера: {e}")

    def _run(self):
        while self.running:
            self.check_clipboard()
            time.sleep(self.check_interval)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("Мониторинг остановлен")