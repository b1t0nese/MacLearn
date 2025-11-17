import io
import random
import time
import subprocess
import threading
import platform
import os
from urllib.parse import quote as url_quote
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from undetected_chromedriver import Chrome
import requests
import cv2
import numpy as np
from PIL import Image
from rembg import remove as removefon

from project_manager import Project



class ClipboardManager:
    def __init__(self):
        self.system = platform.system().lower()
        self._win32clipboard = None
        if self.system=="windows":
            self._import_windows_libs()
        elif self.system=="linux":
            self._check_linux_deps()

    def _import_windows_libs(self):
        if self._win32clipboard is None:
            try:
                import win32clipboard
                self._win32clipboard = win32clipboard
            except ImportError:
                raise ImportError("Для работы с буфером обмена в Windows установите pywin32: pip install pywin32")

    def _check_linux_deps(self):
        if not self._check_command_exists("xclip"):
            raise RuntimeError("Установите xclip для работы с буфером обмена.")

    def _check_command_exists(self, command):
        try:
            subprocess.run([command, "-version"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


    def copy_image_to_clipboard(self, image_path):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File not found: {image_path}")
        image = Image.open(image_path)
        if self.system=="windows":
            self._copy_windows(image)
        elif self.system=="linux":
            self._copy_linux(image)
        elif self.system=="darwin":
            self._copy_macos(image)
        else:
            raise NotImplementedError(f"System {self.system} not supported")

    def _copy_windows(self, image):
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        if self._win32clipboard:
            self._win32clipboard.OpenClipboard()
            self._win32clipboard.EmptyClipboard()
            self._win32clipboard.SetClipboardData(self._win32clipboard.CF_DIB, data)
            self._win32clipboard.CloseClipboard()

    def _copy_linux(self, image):
        if self._check_linux_deps():
            temp_path = "/tmp/clipboard_image.png"
            try:
                image.save(temp_path, "PNG")
                subprocess.run([
                    "xclip", "-selection", "clipboard", 
                    "-t", "image/png", 
                    "-i", temp_path
                ], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Ошибка xclip: {e.stderr}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    def _copy_macos(self, image):
        temp_path = "/tmp/clipboard_image.png"
        try:
            image.save(temp_path, "PNG")
            subprocess.run([
                "osascript", "-e", 
                f'set the clipboard to (read (POSIX file "{temp_path}") as PNG picture)'
            ], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Ошибка AppleScript: {e.stderr}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)



def distort_image(img, distortion_type=None, fill_color=None):
    if distortion_type is None:
        distortion_type = random.choice(["blur", "noise", "rotation", "perspective"])
    if fill_color is None:
        fill_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

    if distortion_type == "blur":
        blur_amount = random.randint(3, 15)
        if blur_amount % 2 == 0:
            blur_amount += 1
        distorted_img = cv2.GaussianBlur(img, (blur_amount, blur_amount), 0)
    elif distortion_type == "noise":
        row, col, ch = img.shape
        noise_level = random.randint(0, 10)
        gauss = np.random.normal(0, noise_level, (row, col, ch)).astype('uint8')
        distorted_img = cv2.add(img, gauss)
    elif distortion_type == "rotation":
        angle = random.randint(-30, 30)
        height, width = img.shape[:2]
        center = (width // 2, height // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        distorted_img = cv2.warpAffine(img, rotation_matrix, (width, height), borderValue=fill_color)
    elif distortion_type == "perspective":
        height, width = img.shape[:2]
        max_offset = min(width, height) // 4
        pts1 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
        offset1 = (random.randint(0, max_offset), random.randint(0, max_offset))
        offset2 = (width - random.randint(0, max_offset), random.randint(0, max_offset))
        offset3 = (random.randint(0, max_offset), height - random.randint(0, max_offset))
        offset4 = (width - random.randint(0, max_offset), height - random.randint(0, max_offset))
        pts2 = np.float32([offset1, offset2, offset3, offset4])
        matrix = cv2.getPerspectiveTransform(pts1, pts2)
        distorted_img = cv2.warpPerspective(img, matrix, (width, height), borderMode=cv2.BORDER_CONSTANT, borderValue=fill_color)
    else:
        distorted_img = None

    return distorted_img


def resize(img, target_size=None, remove_fon=False, fill_color=None):
    if fill_color is None:
        fill_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    if target_size is None:
        target_size = (300, 300)

    if remove_fon=='True':
        img = removefon(img)
        img = img.copy()

        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        img[:, :, 3] = mask
        coords = cv2.findNonZero(mask)
        x, y, w, h = cv2.boundingRect(coords)

        for c in range(3):
            img[:, :, c] = np.where(mask == 0, fill_color[c], img[:, :, c])
        img = img[y:y+h, x:x+w]

    height, width = img.shape[:2]
    target_width, target_height = target_size

    scale = min(target_width / width, target_height / height)
    new_width = int(width * scale)
    new_height = int(height * scale)

    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    if resized_img.shape[2] == 4:
        background = np.full((new_height, new_width, 3), fill_color, dtype=np.uint8)
        alpha = resized_img[:, :, 3] / 255.0
        alpha = np.repeat(alpha[:, :, np.newaxis], 3, axis=2)
        resized_img = (resized_img[:, :, :3] * alpha + background * (1 - alpha)).astype(np.uint8)
    
    return resized_img



class AutoDataset(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    log_field = pyqtSignal(str, int)
    cur_image_label = pyqtSignal(str)
    stage_updated = pyqtSignal(str, str)
    subclass_updated = pyqtSignal(str, int)

    def __init__(self, project_manager: Project, headless_chrome=False):
        super().__init__()
        self._is_running = False
        self.driver = Chrome(headless=headless_chrome)
        self.clipboard_manager = ClipboardManager()
        self.project_manager = project_manager
        self.current_status_data = None

    def always_switch_to_main_window(self):
        while self._is_running:
            # if self.driver.current_window_handle!=self.driver.window_handles[0]:
            self.driver.switch_to.window(self.driver.window_handles[0])


    def download_images(self, subclass_data: dict, num_images: int,
                        class_id: int, size: tuple=(320, 240)):
        self.log_field.emit('Поиск изображений...', 0)
        self.driver.get("https://yandex.ru/images")

        if subclass_data["example_image"]:
            self.clipboard_manager.copy_image_to_clipboard(self.project_manager.get_full_path(
                "example_images", subclass_data["example_image"]))

            search_box = self.driver.find_element(By.NAME, "text")
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("v")\
                .key_up(Keys.CONTROL).perform()
            time.sleep(0.5)
            search_box.send_keys(Keys.ENTER)

            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, ".CbirIntent.cbir-intent.cbir-intent_visible_yes.i-bem.cbir-intent_js_inited.cbir-intent_loaded_yes")))
            search_box = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "textarea")))
            search_box.send_keys(subclass_data["search_query"])
            time.sleep(0.5)
            search_box.send_keys(Keys.ENTER)

            while True:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((
                            By.XPATH, "//a[text()='Похожие' and @class='CbirNavigation-TabsItem CbirNavigation-TabsItem_name_similar-page']"))
                    ).click()
                    break
                except: pass

        else:
            self.driver.get(f"https://yandex.ru/images/search?text={url_quote(subclass_data['search_query'])}")

        self.log_field.emit('Идёт прогрузка изображений...', 0)
        new_height = self.driver.execute_script("return document.body.scrollHeight")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            scroll_st = time.time()
            while new_height==last_height:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if time.time()-scroll_st>=5:
                    break                
            if time.time()-scroll_st>=5:
                if size:
                    image_elements = self.driver.find_elements(By.CSS_SELECTOR, ".Link.ImagesContentImage-Cover")
                else:
                    image_elements = self.driver.find_elements(By.CSS_SELECTOR, ".ImagesContentImage-Image.ImagesContentImage-Image_clickable")
                if len(image_elements)>num_images:
                    break
                else:
                    try:
                        self.driver.find_element(By.XPATH, "//button[.//span[text()='Показать ещё']]").click()
                    except: break
            last_height = new_height

        self.log_field.emit('Скачивание изображений...', 1)
        downloaded_images_count = 0
        for id, img in enumerate(image_elements):
            try:
                if size:
                    self.driver.execute_script("arguments[0].scrollIntoView();", img)
                    self.driver.execute_script("arguments[0].click();", img)
                    img_src = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "MMImage-Origin"))).get_attribute('src')
                    self.driver.find_element(By.CSS_SELECTOR, ".Button.ImagesViewer-Close").click()
                else:
                    img_src = img.get_attribute('src')
                response = requests.get(img_src)
                if response.status_code==200:
                    image_id = self.project_manager.save_image(response.content, class_id)
                    downloaded_images_count += 1
                    self.subclass_updated.emit(subclass_data["search_query"], downloaded_images_count)
                    self.log_field.emit(f"Скачан файл {downloaded_images_count}/{num_images}, id: {id}", 0)
                    self.cur_image_label.emit(self.project_manager.get_full_path(
                        "images", self.project_manager.get_image(image_id)["filename"]))
                if downloaded_images_count>=num_images:
                    break
            except Exception as e:
                self.log_field.emit(f"Ошибка при скачивании файла: {e}. Id: {id}", 0)


    @pyqtSlot()
    def run(self):
        self._is_running = True
        self.log_field.emit('Начало работы.\n', 0)

        self.always_switch_to_main_window_thread = threading.Thread(
            target=self.always_switch_to_main_window, daemon=True)
        self.always_switch_to_main_window_thread.start()

        self.project_data = {
            "configuration": self.project_manager.get_configutation(),
            "classes": self.project_manager.get_all_classes_conf()
        }

        self.log_field.emit('Установка изображений...\n', 1)
        for class_data in self.project_data["classes"]:
            size = tuple(map(int, self.project_data["configuration"]["images_size"].split("x")))
            for subclass_data in class_data["subclasses"]:
                if class_data["enabled"] and self._is_running:
                    img_counts = self.project_data["configuration"]["images_per_class"]//len(class_data["subclasses"])
                    self.download_images(subclass_data, img_counts, class_data["class_id"], size=size)
        self.log_field.emit('Готово! Изображения скачаны.\n', 1)

        if not self._is_running:
            self.log_field.emit('Работа остановлена\n', 1)
        else:
            self.log_field.emit('Работа окончена, данные готовы.\n', 1)

        self._is_running = False
        self.always_switch_to_main_window_thread.join()
        self.finished.emit()


    @pyqtSlot()
    def stop(self):
        self._is_running = False
        self.log_field.emit("Работа скоро остановится, пожалуйста не закрывайте это окно.\n", 1)