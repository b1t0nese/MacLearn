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
from requests import get as get_request
from threading import Thread
from platform import system as platf_system
from time import sleep, time as ntime
from typing import Callable
import subprocess
import cv2
import os

from .project_manager import Project
from .photoshop import *



class ClipboardManager:
    def __init__(self):
        self.system = platf_system().lower()
        self._win32clipboard, self._tempfile = None, None
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
        import tempfile
        self._tempfile = tempfile

    def _check_command_exists(self, command):
        try:
            subprocess.run([command, "-version"], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL,
                            check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


    def copy_image_to_clipboard(self, image: str | np.ndarray):
        if isinstance(image, str):
            if not os.path.exists(image):
                raise FileNotFoundError(f"File not found: {image}")
            image_array = np.fromfile(image, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_UNCHANGED)
        if image is not None and image.size > 0:
            if self.system == "windows":
                self._copy_windows(image)
            elif self.system == "linux":
                self._copy_linux(image)
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

    def _copy_linux(self, image):
        if not self._check_linux_deps():
            raise RuntimeError("xclip not found. Install with: sudo apt-get install xclip")
        success, png_data = cv2.imencode('.png', image)
        if not success:
            raise RuntimeError("Failed to encode image to PNG")
        with self._tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(png_data.tobytes())
        try:
            result = subprocess.run([
                "xclip", "-selection", "clipboard", 
                "-t", "image/png", 
                "-i", tmp_path
            ], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"xclip error: {result.stderr}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)



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
        try:
            self.log_field.emit(*log_emit)
            if subclass_updated: self.subclass_updated.emit(*subclass_updated)
            if stage_updated: self.stage_updated.emit(*stage_updated)
            if cur_image: self.cur_image_label.emit(*cur_image)
        except:
            print(f"{log_emit[1]*"\n"}{log_emit[0]}")


    def __init__(self, project_manager: Project, chromedriver_path: str=None, chrome_version: int=None):
        super().__init__()
        self._is_running = False
        self._image_downloaded = True

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = Chrome(service=service, driver_executable_path=chromedriver_path, version_main=chrome_version)
            self.clipboard_manager = ClipboardManager()
        except Exception as e:
            self.driver, self.clipboard_manager = None, None
            print(f"ERROR (chrome start): {e}")

        self.project_manager = project_manager
        self.update_project_data()

        self.downloaded_images_count = 0
        self.created_annotations_count = 0

        self.do_download_images = True
        self.do_annotation = True
        self.do_augmentation = True


    def close(self):
        self._is_running = False
        if self.driver:
            self.driver.close()
            # self.driver.quit()
        del self.driver
        del self.clipboard_manager
        del self.project_manager


    def always_switch_to_main_window(self):
        while self._is_running and self.driver:
            # if self.driver.current_window_handle!=self.driver.window_handles[0]:
            self.driver.switch_to.window(self.driver.window_handles[0])


    def download_image(self, img_src: str, class_id: int, image_type: str, do_before_download: Callable=None):
        self._image_downloaded = False
        try:
            response = get_request(img_src)
            if response.status_code==200:
                image_id = self.project_manager.save_image(
                    response.content, class_id, image_type)
                do_before_download(image_id)
        except Exception as e:
            self.update_information((f"Ошибка при скачивании файла: {e}. src: {img_src}", 0))
        self._image_downloaded = True


    def download_images(self, subclass_data: dict, class_id: int, num_images: int,
                        num_val_images: int=0, downloaded: int=0):
        if num_val_images:
            images_count = num_images+num_val_images
            self.update_information(('INFO: Установка валидационных данных включена.', 0))
        else: images_count = num_images
        example_image = subclass_data["example_image"]

        self.update_information(('Поиск изображений...', 0))
        self.driver.get("https://yandex.ru/images")
        try:
            self.chrome_widget_lock.emit(True)
        except: pass

        if example_image:
            self.clipboard_manager.copy_image_to_clipboard(
                self.project_manager.get_full_path("example_images", example_image))
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
                sleep(0.5)
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

        self.update_information(('Идёт прогрузка изображений...', 0))
        image_elements = []
        new_height = self.driver.execute_script("return document.body.scrollHeight")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while self._is_running:
            scroll_st = ntime()
            while new_height==last_height:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if ntime()-scroll_st>=5:
                    break                
            if ntime()-scroll_st>=5:
                image_elements = self.driver.find_elements(By.CSS_SELECTOR, ".Link.ImagesContentImage-Cover")
                # image_elements = self.driver.find_elements( # или малые изображения (обложки)
                #     By.CSS_SELECTOR, ".ImagesContentImage-Image.ImagesContentImage-Image_clickable")
                if len(image_elements)<images_count:
                    try:
                        self.driver.find_element(By.XPATH, "//button[.//span[text()='Показать ещё']]").click()
                    except: break
                else: break
            last_height = new_height

        self.update_information(('Скачивание изображений...', 0))
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
                    def do_before_download(img_id):
                        nonlocal downloaded_images_count, image_id, images_count
                        image_id = img_id
                        self.downloaded_images_count += 1; downloaded_images_count += 1; self.update_information(
                            (f"Скачан файл {downloaded_images_count}/{images_count}, id: {image_id}", 0),
                            (subclass_data["search_query"], downloaded_images_count),
                            ("Download images", (self.downloaded_images_count, self.all_images_count)),
                            (self.project_manager.get_full_path("images", self.project_manager.get_image(image_id)["filename"]), np.array([])))
                    Thread(target=self.download_image, args=(
                        img_src, class_id, "validation" if num_val_images and downloaded_images_count>=num_images\
                            else "default", do_before_download)).start()
                else: break
            except Exception as e:
                self.update_information((f"Ошибка при получении ссылки файла: {e}. Id: {image_id if image_id else i}", 0))

        try:
            self.chrome_widget_lock.emit(False)
        except: pass


    def download_images_data(self):
        self.update_information(('Установка изображений...\n', 1))
        for class_data in self.project_data["classes"]:
            for subclass_data in class_data["subclasses"]:
                if class_data["enabled"] and self._is_running:
                    img_counts = round(self.project_data["configuration"]["images_per_class"]/len(class_data["subclasses"]))
                    val_img_counts = (img_counts // 5) if self.project_data["configuration"]["validation_data"] else 0
                    must_img_counts, must_val_img_counts = img_counts, val_img_counts
                    def_count, def_val_count = [round(len(self.project_manager.get_images(class_data["id"], dat_type))/len(class_data["subclasses"]))\
                                                for dat_type in ["default", "validation"]]
                    img_counts -= def_count; val_img_counts -= def_val_count
                    img_counts, val_img_counts = (img_counts if img_counts>0 else 0), (val_img_counts if val_img_counts>0 else 0)
                    all_imgs = def_count+def_val_count; self.downloaded_images_count += all_imgs; self.update_information(
                        (f'INFO: В классе "{subclass_data["search_query"]}" уже присутствует изображений: {all_imgs}.', 1),
                        (subclass_data["search_query"], all_imgs), ("Download images", (self.downloaded_images_count, self.all_images_count)))
                    if img_counts or val_img_counts:
                        self.download_images(subclass_data, class_data["class_id"], must_img_counts, must_val_img_counts, all_imgs)
        self.update_information(('Готово! Изображения скачаны.\n', 2))


    def create_annotation_data(self):
        self.update_information(('Создание аннотаций...\n', 1))
        all_images = []
        for images_type in ["default", "validation"]:
            all_images += self.project_manager.get_images(images_type=images_type)
        self.all_images_count = len(all_images)
        for i, image_data in enumerate(all_images):
            if not image_data["annotation"] and self._is_running:
                image_path = self.project_manager.get_full_path("images", image_data["filename"])
                image = open_image(image_path)
                if image is not None and image.size > 0:
                    object_detector = ImageAnnotationDetector(image)
                    object_detector.remove_bg()
                    object_detector.detect_contours()
                    object_detector.smooth_contours()
                    object_detector.filter_contours_to_needed()
                    annotation_data = object_detector.calculate_bboxes_data()
                    if annotation_data:
                        bbox = list(map(lambda x: [image_data["class_id"]] + list(x["bbox"]), annotation_data))
                        image_data = self.project_manager.change_image(image_data["id"], annotation=bbox)
                        self.created_annotations_count += 1; self.update_information(
                            (f"Создана аннотация №{i+1}, данные изображения: {image_data}", 0),
                            stage_updated=("Create annotation", (self.created_annotations_count, self.all_images_count)),
                            cur_image=(image_path, cv2.cvtColor(object_detector.put_contours_on_image(image), cv2.COLOR_BGR2RGB)))
        self.update_information(('Готово! Аннотация создана.\n', 2))


    def update_project_data(self):
        self.project_data = {
            "configuration": self.project_manager.get_configutation(),
            "classes": self.project_manager.get_all_classes_conf()
        }


    @pyqtSlot()
    def run(self):
        self._is_running, self._image_downloaded = True, True
        self.update_information(('Начало работы.\n', 0))

        self.always_switch_to_main_window_thread = Thread(
            target=self.always_switch_to_main_window, daemon=True)
        self.always_switch_to_main_window_thread.start()

        self.update_project_data()
        self.downloaded_images_count = 0
        self.created_annotations_count = 0
        self.processed_images_to_augment_count = 0
        self.all_images_count = sum([int(self.project_data["configuration"]["images_per_class"] *
                                         (1.2 if self.project_data["configuration"]["validation_data"] else 1))
                                     for class_data in self.project_data["classes"] if class_data["enabled"]])

        if self.do_download_images and self.driver and self._is_running:
            self.update_information(("Подсчёт работы 1...\n", 1), stage_updated=(
                "Download images", (self.downloaded_images_count, self.all_images_count)))
        if self.project_data["configuration"]["annotation"] and self.do_annotation and self._is_running:
            self.update_information(("Подсчёт работы 2...\n", 0), stage_updated=(
                "Create annotation", (self.created_annotations_count, self.all_images_count)))
        if self.project_data["configuration"]["augmentation"] and self.do_augmentation and self._is_running:
            self.update_information(("Подсчёт работы 3...\n", 0),  stage_updated=(
                "Create augmentation data", (self.processed_images_to_augment_count, self.all_images_count)))

        if self.do_download_images and self.driver:
            self.download_images_data()
        else:
            self.update_information((f'''INFO: Установка изображений выключена{
                ", Chrome не инициализировался" if not self.driver else ""}.\n''', 2))
        if self.project_data["configuration"]["annotation"] and self.do_annotation:
            self.create_annotation_data()
        else:
            self.update_information(('INFO: Создание аннотации выключено.\n', 2))
        if self.project_data["configuration"]["augmentation"] and self.do_augmentation:
            pass #self.create_augmentation_data()
        else:
            self.update_information(('INFO: Создание аугментированных данных выключено.\n', 2))

        if not self._is_running:
            self.update_information(('Работа остановлена\n\n\n', 2))
        else:
            self.update_information(('Работа окончена, данные готовы.\n\n\n', 2))

        self._is_running = False
        self.always_switch_to_main_window_thread.join()
        self.finished.emit()


    @pyqtSlot()
    def stop(self):
        self._is_running = False
        self.update_information(("Работа скоро остановится, пожалуйста не закрывайте это окно.\n", 1))