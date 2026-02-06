from urllib.parse import quote as url_quote
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from undetected_chromedriver import Chrome
from PIL import Image
import subprocess
import threading
import requests
import platform
import time
import os
import io

from .project_manager import Project
from .photoshop import *



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



class AutoDataset(QObject):
    finished = pyqtSignal()
    chrome_widget_lock = pyqtSignal(bool)
    progress = pyqtSignal(int)
    log_field = pyqtSignal(str, int)
    cur_image_label = pyqtSignal(str, np.ndarray)
    stage_updated = pyqtSignal(str, tuple)
    subclass_updated = pyqtSignal(str, int)


    def update_information(self, log_emit: tuple, subclass_updated: tuple=None,
                           stage_updated: tuple=None, cur_image: tuple=None):
        self.log_field.emit(*log_emit)
        if subclass_updated: self.subclass_updated.emit(*subclass_updated)
        if stage_updated: self.stage_updated.emit(*stage_updated)
        if cur_image: self.cur_image_label.emit(*cur_image)


    def __init__(self, project_manager: Project, chrome_version: int=None, headless_chrome: bool=False):
        super().__init__()
        self._is_running = False

        service = Service(ChromeDriverManager().install())
        self.driver = Chrome(service=service, version_main=chrome_version, headless=headless_chrome)
        self.clipboard_manager = ClipboardManager()

        self.project_manager = project_manager
        self.update_project_data()

        self.downloaded_images_count = 0
        self.created_annotations_count = 0


    def close(self):
        self._is_running = False
        self.driver.close()
        # self.driver.quit()
        del self.clipboard_manager
        del self.project_manager


    def always_switch_to_main_window(self):
        while self._is_running:
            # if self.driver.current_window_handle!=self.driver.window_handles[0]:
            self.driver.switch_to.window(self.driver.window_handles[0])


    def download_images(self, subclass_data: dict, class_id: int, num_images: int,
                        validation_data: int=0, downloaded: int=0):
        if validation_data:
            images_count = num_images+validation_data
            self.log_field.emit('INFO: Установка валидационных данных включена.', 0)
        else: images_count = num_images
        example_image = subclass_data["example_image"]

        self.log_field.emit('Поиск изображений...', 0)
        self.driver.get("https://yandex.ru/images")
        self.chrome_widget_lock.emit(True)

        if example_image:
            self.clipboard_manager.copy_image_to_clipboard(self.project_manager.get_full_path(
                "example_images", example_image))

            search_box = self.driver.find_element(By.NAME, "text")
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("v")\
                .key_up(Keys.CONTROL).perform()

            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, ".CbirIntent.cbir-intent.cbir-intent_visible_yes.i-bem.cbir-intent_js_inited.cbir-intent_loaded_yes")))
                search_box = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "textarea")))
                search_box.send_keys(subclass_data["search_query"])
                time.sleep(0.5)
                search_box.send_keys(Keys.ENTER)
                while self._is_running:
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((
                                By.XPATH, "//a[text()='Похожие' and @class='CbirNavigation-TabsItem CbirNavigation-TabsItem_name_similar-page']"))
                        ).click()
                        break
                    except: pass
            except:
                example_image = None

        if not example_image:
            self.driver.get(f"https://yandex.ru/images/search?text={url_quote(subclass_data['search_query'])}")

        self.log_field.emit('Идёт прогрузка изображений...', 0)
        image_elements = []
        new_height = self.driver.execute_script("return document.body.scrollHeight")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while self._is_running:
            scroll_st = time.time()
            while new_height==last_height:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if time.time()-scroll_st>=5:
                    break                
            if time.time()-scroll_st>=5:
                image_elements = self.driver.find_elements(By.CSS_SELECTOR, ".Link.ImagesContentImage-Cover")
                # image_elements = self.driver.find_elements( # или малые изображения (обложки)
                #     By.CSS_SELECTOR, ".ImagesContentImage-Image.ImagesContentImage-Image_clickable")
                if len(image_elements)<images_count:
                    try:
                        self.driver.find_element(By.XPATH, "//button[.//span[text()='Показать ещё']]").click()
                    except: break
                else: break
            last_height = new_height

        self.log_field.emit('Скачивание изображений...', 0)
        downloaded_images_count = downloaded
        for i, img in enumerate(image_elements):
            image_id = None
            try:
                if downloaded_images_count<images_count and self._is_running:
                    self.driver.execute_script("arguments[0].scrollIntoView();", img)
                    self.driver.execute_script("arguments[0].click();", img)
                    img_src = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "MMImage-Origin"))).get_attribute('src')
                    self.driver.find_element(By.CSS_SELECTOR, ".Button.ImagesViewer-Close").click()
                    # img_src = img.get_attribute('src') # или малые изображения (обложки)
                    response = requests.get(img_src)
                    if response.status_code==200:
                        image_id = self.project_manager.save_image(
                            response.content, class_id, "validation" if validation_data and i+1>=num_images else "default")
                        self.downloaded_images_count += 1; downloaded_images_count += 1; self.update_information(
                            (f"Скачан файл {downloaded_images_count}/{images_count}, id: {image_id}", 0),
                            (subclass_data["search_query"], downloaded_images_count),
                            ("Download images", (self.downloaded_images_count, self.all_images_count)),
                            (self.project_manager.get_full_path("images", self.project_manager.get_image(image_id)["filename"]), np.array([])))
                else: break
            except Exception as e:
                self.log_field.emit(f"Ошибка при скачивании файла: {e}. Id: {image_id if image_id else i}", 0)

        self.chrome_widget_lock.emit(False)


    def update_project_data(self):
        self.project_data = {
            "configuration": self.project_manager.get_configutation(),
            "classes": self.project_manager.get_all_classes_conf()
        }


    @pyqtSlot()
    def run(self):
        self._is_running = True
        self.log_field.emit('Начало работы.\n', 0)

        self.always_switch_to_main_window_thread = threading.Thread(
            target=self.always_switch_to_main_window, daemon=True)
        self.always_switch_to_main_window_thread.start()

        self.update_project_data()
        self.downloaded_images_count = 0
        self.created_annotations_count = 0
        self.all_images_count = sum([int(self.project_data["configuration"]["images_per_class"] * 1.2) for _ in self.project_data["classes"]])

        self.stage_updated.emit("Download images", (self.downloaded_images_count, self.all_images_count))
        if self.project_data["configuration"]["annotation"]:
            self.stage_updated.emit("Create annotation", (self.created_annotations_count, self.all_images_count))

        self.log_field.emit('Установка изображений...\n', 1)
        for class_data in self.project_data["classes"]:
            for subclass_data in class_data["subclasses"]:
                if class_data["enabled"] and self._is_running:
                    img_counts = round(self.project_data["configuration"]["images_per_class"]/len(class_data["subclasses"]))
                    val_img_counts = (img_counts // 5) if self.project_data["configuration"]["validation_data"] else 0
                    must_img_counts, must_val_img_counts = img_counts, val_img_counts
                    def_count, def_val_count = [len(self.project_manager.get_images(class_data["id"], dat_type))\
                                                for dat_type in ["default", "validation"]]
                    img_counts -= def_count; val_img_counts -= def_val_count
                    img_counts, val_img_counts = (img_counts if img_counts>0 else 0), (val_img_counts if val_img_counts>0 else 0)
                    all_imgs = def_count+def_val_count; self.downloaded_images_count += all_imgs; self.update_information(
                        (f'INFO: В классе {subclass_data["search_query"]} уже присутствует изображений: {all_imgs}.', 1),
                        (subclass_data["search_query"], all_imgs), ("Download images", (self.downloaded_images_count, self.all_images_count)))
                    if (img_counts or val_img_counts) and (must_img_counts+must_val_img_counts!=all_imgs):
                        self.download_images(subclass_data, class_data["class_id"], must_img_counts, must_val_img_counts, all_imgs)
        self.log_field.emit('Готово! Изображения скачаны.\n', 2)

        if self.project_data["configuration"]["annotation"]:
            self.log_field.emit('Создание аннотаций...\n', 1)
            all_images = self.project_manager.get_images(type="default")+self.project_manager.get_images(type="validation")
            self.all_images_count = len(all_images)
            for i, image_data in enumerate(all_images):
                image_path = self.project_manager.get_full_path("images", image_data["filename"])
                image = open_image(image_path)
                object_detector = ImageAnnotationDetector(image)
                object_detector.remove_bg()
                object_detector.detect_contours()
                object_detector.smooth_contours()
                object_detector.filter_contours_to_needed()
                annotation_data = object_detector.calculate_bboxes_data()
                bbox = list(map(lambda x: [image_data["class_id"]] + list(x["bbox"]), annotation_data))
                image_data = self.project_manager.change_image(image_data["id"], annotation=bbox)
                self.created_annotations_count += 1; self.update_information(
                    (f"Создана аннотация №{i+1}, данные изображения: {image_data}", 0),
                    stage_updated=("Create annotation", (self.created_annotations_count, self.all_images_count)),
                    cur_image=(image_path, cv2.cvtColor(object_detector.put_contours_on_image(image), cv2.COLOR_BGR2RGB)))
                if not self._is_running:
                    break

        if not self._is_running:
            self.log_field.emit('Работа остановлена\n\n\n', 1)
        else:
            self.log_field.emit('Работа окончена, данные готовы.\n\n\n', 1)

        self._is_running = False
        self.always_switch_to_main_window_thread.join()
        self.finished.emit()


    @pyqtSlot()
    def stop(self):
        self._is_running = False
        self.log_field.emit("Работа скоро остановится, пожалуйста не закрывайте это окно.\n", 1)