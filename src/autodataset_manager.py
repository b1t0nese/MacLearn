# Старая фигня версия автодатасет класса, который я делал под ткинтер
# Будет подвержен сильному рефакторингу



import random
import shutil
import os
import win32clipboard
import io
import time
import requests
import cv2
import numpy as np
from rembg import remove
from PIL import Image
import threading
from undetected_chromedriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains



class ImgDatasetDownloader:
    def __init__(self, window, headless_chrome=False):
        self.driver = Chrome(headless=headless_chrome)

        self.window = window
        self.window.start_command = self.work

        self.progress = 0
        self.work_thr = False
        self.classes = []
        self.imgs_path = ''


    def download_image(self, img_src, output_folder, id, i, num_images):
        response = requests.get(img_src)
        if response.status_code == 200:
            self.imgs_path = os.path.join(output_folder, f"{id}.{i}.jpg")
            with open(self.imgs_path, 'wb') as file:
                file.write(response.content)
            try:
                self.window.print_info(f"Скачан файл {i + 1}/{self.window.cnt_ent.get()}, id: {id}")
                self.window.show_image(cv2.imread(self.imgs_path), self.imgs_path)
            except:
                self.window.print_info(f"Файл повреждён {i + 1}/{self.window.cnt_ent.get()}, id: {id}")
            self.progress += self.calc_percentg()
            self.window.progressbar.configure(value=self.progress)
        else:
            self.window.print_info(f"Файл {i + 1}/{self.window.cnt_ent.get()} не скачан: {response.status_code}. Id: {id}")


    def download_images(self, query, num_images, id, output_folder, exaple_img=None, size=None):
        self.window.print_info('Поиск изображений...', otstup=1)
        self.driver.get("https://yandex.ru/images")

        search_box = self.driver.find_element(By.NAME, "text")

        if exaple_img:
            image = Image.open(exaple_img)
            output = io.BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()

            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("v")\
                .key_up(Keys.CONTROL).perform()
            
            search_box = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "textarea")))

        search_box.send_keys(query)
        time.sleep(0.5)
        search_box.send_keys(Keys.ENTER)

        if exaple_img:
            while True:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//a[text()='Похожие' and @class='CbirNavigation-TabsItem CbirNavigation-TabsItem_name_similar-page']"))
                    ).click()
                    break
                except: pass

        self.window.print_info('Идёт прогрузка изображений...')
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

        image_elements = image_elements[:num_images]

        self.window.print_info('Скачивание изображений...', otstup=1)
        len_img = len([f for f in os.listdir(output_folder) if f.startswith(str(id)) or f.startswith(('false', 'true'))])
        for i, img in enumerate(image_elements):
            i += len_img
            try:
                if size:
                    self.driver.execute_script("arguments[0].scrollIntoView();", img)
                    self.driver.execute_script("arguments[0].click();", img)
                    img_src = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "MMImage-Origin"))).get_attribute('src')
                    self.driver.find_element(By.CSS_SELECTOR, ".Button.ImagesViewer-Close").click()
                else:
                    img_src = img.get_attribute('src')
                threading.Thread(target=self.download_image, args=(img_src, output_folder, id, i, num_images), daemon=True).start()

            except Exception as e:
                self.window.print_info(f"Ошибка при скачивании файла {i + 1}: {e}. Id: {id}")


    def distort_image(self, img, distortion_type=None, fill_color=None):
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


    def resize(self, img, target_size=None, remove_fon=False, fill_color=None):
        if fill_color is None:
            fill_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        if target_size is None:
            target_size = (300, 300)

        if remove_fon=='True':
            img = remove(img)
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


    def work(self, classes, tr_classes, config):
        self.classes = classes
        self.config = config

        value = self.window.cnt_ent.get()
        if not value.isdigit():
            self.window.print_info("Ошибка: Количество изображений на класс должно быть числом.")
            self.window.start_b.configure(text='Начать')
            self.work_thr = False
            return False

        self.window.print_info('Начало работы.\n')

        if self.config['download']=='True':
            if not os.path.exists(self.config['download_folder']):
                os.makedirs(self.config['download_folder'])
            self.window.print_info('Удаление скачанных ранее изображений...')
            for item in os.listdir(self.config['download_folder']):
                item_path = os.path.join(self.config['download_folder'], item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            for i, clas in enumerate(self.classes):
                img_counts = int(self.window.cnt_ent.get())//len(clas)
                if self.config['download_tr']=='True':
                    img_counts += int(self.window.cnt_ent.get())//len(tr_classes[i])*tr_classes[i].count("True")//len(clas)
                size = tuple([int(i) for i in self.config['size'].split("x")]) if self.config['size'] else None
                for j, query in enumerate(clas):
                    example_img = f"{self.config['examples_folder']}/{i}_{j}.jpg"
                    example_img = example_img if os.path.exists(example_img) else None
                    self.download_images(query, img_counts, i, self.config['download_folder'], exaple_img=example_img, size=size)
                self.window.progressbar.configure(value=self.progress)

            self.window.print_info('Готово! Изображения скачаны.\n', otstup=1)
        else:
            self.window.print_info('Скачивание изображений отключено.')

        if self.config['download_tr']=='True':
            self.window.print_info('Удаление ранее скачанных тренировочных изображений...', otstup=1)
            if not os.path.exists(self.config['train_folder']):
                os.makedirs(self.config['train_folder'])
            for item in os.listdir(self.config['train_folder']):
                item_path = os.path.join(self.config['train_folder'], item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            for i, clas in enumerate(tr_classes):
                img_counts = int(self.window.cnt_ent.get())//len(clas)
                for query in clas:
                    if not os.path.exists(f'{self.config['train_folder']}/{i}'):
                        os.makedirs(f'{self.config['train_folder']}/{i}')
                    if query=='True':
                        files = [f for f in os.listdir(self.config['download_folder']) if f.startswith(str(i))]
                        for j in range(img_counts):
                            filename = random.choice(files)
                            files.remove(filename)
                            src_path = os.path.join(self.config['download_folder'], filename)
                            dst_path = os.path.join(f'{self.config['train_folder']}/{i}', f"true_{filename}")
                            shutil.move(src_path, dst_path)
                            self.window.print_info(f"Перемещено: {src_path} -> {dst_path}")
                    else:
                        self.download_images(query, img_counts, 'false', f'{self.config['train_folder']}/{i}')

            self.window.print_info('Готово! Тренировочные изображения созданы.\n', otstup=1)
        else:
            self.window.print_info('Скачивание train отключено.')

        if self.config['create_dataset']=='True':
            if not os.path.exists(self.config['dataset_folder']):
                os.makedirs(self.config['dataset_folder'])
            self.window.print_info('Очищение папки старого датасета...', otstup=1)
            for item in os.listdir(self.config['dataset_folder']):
                item_path = os.path.join(self.config['dataset_folder'], item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            self.window.print_info('Создание датасета...')
            if self.config['augmentation']=='False':
                self.window.print_info('Аугментация отключена.')
            for id in range(len(self.classes)):
                folder_path = f'{self.config['dataset_folder']}/{id}'
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                for i, filename in enumerate(os.listdir(self.config['download_folder'])):
                    clas = int(filename.split('.')[0])
                    if clas==id:
                        self.window.print_info(f'Обработка файла №{i}, id: {id}')
                        fill_color = tuple([int(c) for c in self.config['fon'].split(",")]) if self.config['fon'] else None
                        size = tuple([int(i) for i in self.config['size'].split("x")]) if self.config['size'] else None
                        img = cv2.imread(os.path.join(self.config['download_folder'], filename))
                        img = self.resize(img, target_size=size, remove_fon=self.config['remove_fon'], fill_color=fill_color)
                        self.imgs_path = f'{folder_path}/{i}.{{}}.jpg'
                        cv2.imwrite(f'{folder_path}/{i}.{0}.jpg', img); self.window.show_image(img, f'{folder_path}/{i}.{0}.jpg')
                        if self.config['augmentation']=='True':
                            distort_tips = ["blur", "noise", "rotation", "perspective"]
                            for j, d_tip in enumerate(distort_tips):
                                distort_img = self.distort_image(img, distortion_type=d_tip, fill_color=fill_color)
                                cv2.imwrite(f'{folder_path}/{i}.{j+1}.jpg', distort_img)
                        self.progress += self.calc_percentg()
                        self.window.progressbar.configure(value=self.progress)
                self.window.progressbar.configure(value=self.progress)

            self.window.print_info('Готово! Ваш датасет создан!', otstup=1)
        else:
            self.window.print_info('Создание датасета отключено.')

        self.work_thr = False
        self.window.start_b.configure(text='Начать')
        self.progress = 100
        self.window.progressbar.configure(value=self.progress)


    def start(self):
        if not self.work_thr:
            self.window.start_b.configure(text='Стоп')
            work_thr = threading.Thread(target=self.work, daemon=True)
            work_thr.start()
        else:
            exit()


    def calc_percentg(self):
        divisor = 0
        if self.config['download']=='True':
            divisor += 1
        if self.config['download_tr']=='True':
            divisor += 1
        if self.config['create_dataset']=='True':
            divisor += 1

        if divisor > 0:
            return 100/(len(self.classes)*int(self.window.cnt_ent.get())*divisor)
        else:
            return 0