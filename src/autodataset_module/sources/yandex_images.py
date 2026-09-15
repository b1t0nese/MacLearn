from urllib.parse import quote as url_quote
from time import sleep, time as ntime

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base import BaseImageSource, register_source
from logger import get_logger
log = get_logger("autodataset")



@register_source("Yandex")
class YandexImagesSource(BaseImageSource):
    name = "Yandex"

    SEARCH_URL = "https://yandex.ru/images"
    TEXT_SEARCH_URL = "https://yandex.ru/images/search?text={query}"

    CSS_SEARCH_IMAGE = ".Link.ImagesContentImage-Cover"
    CSS_OPENED_IMAGE = "MMImage-Origin"
    CSS_CLOSE_VIEWER = ".Button.ImagesViewer-Close"
    CSS_CBIR_INTENT = ".CbirIntent.cbir-intent.cbir-intent_visible_yes.i-bem.cbir-intent_js_inited.cbir-intent_loaded_yes"
    XPATH_SHOW_MORE = "//button[.//span[text()='Показать ещё']]"
    XPATH_SIMILAR = "//a[text()='Похожие' and @class='CbirNavigation-TabsItem CbirNavigation-TabsItem_name_similar-page']"

    ELEMENT_TIMEOUT = 10
    SCROLL_TIMEOUT = 5
    SIMILAR_TIMEOUT = 30


    def collect(self, subclass_data: dict, on_url, stop_check, status=None, example_image_path: str=None):
        search_query = subclass_data["search_query"]
        self.browser.lock(True)
        try:
            status("Searching images...", 0)
            if not self._open_search_page(search_query, example_image_path, stop_check):
                if stop_check():
                    return
                self.driver.get(self.TEXT_SEARCH_URL.format(query=url_quote(search_query)))
            if stop_check():
                return
            status("Loading images...", 0)
            self._scroll_and_collect(on_url, stop_check)
        finally:
            self.browser.lock(False)


    def _open_search_page(self, search_query: str, example_image_path: str, stop_check) -> bool:
        if not (example_image_path and self.clipboard_manager):
            return False
        try:
            self.driver.get(self.SEARCH_URL)
            self.clipboard_manager.copy_image_to_clipboard(example_image_path)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("v")\
                .key_up(Keys.CONTROL).perform()
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.CSS_CBIR_INTENT)))
            search_box = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "textarea")))
            search_box.send_keys(search_query)
            sleep(0.5)
            search_box.send_keys(Keys.ENTER)
            start = ntime()
            while not stop_check():
                try:
                    WebDriverWait(self.driver, self.ELEMENT_TIMEOUT).until(
                        EC.presence_of_element_located((By.XPATH, self.XPATH_SIMILAR))).click()
                    return True
                except:
                    if ntime() - start > self.SIMILAR_TIMEOUT:
                        return False
                    sleep(0.5)
            return False
        except Exception as e:
            log.warning("⚠ Image example search failed: %s", e)
            return False


    def _scroll_and_collect(self, on_url, stop_check):
        seen_urls = set()
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while not stop_check():
            scroll_start = ntime()
            new_height = last_height
            while new_height == last_height and not stop_check():
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(0.5)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if ntime() - scroll_start >= self.SCROLL_TIMEOUT:
                    break
            if ntime() - scroll_start >= self.SCROLL_TIMEOUT or stop_check():
                try:
                    self.driver.find_element(By.XPATH, self.XPATH_SHOW_MORE).click()
                    sleep(1)
                except:
                    pass
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                continue
            last_height = new_height
            for img in self.driver.find_elements(By.CSS_SELECTOR, self.CSS_SEARCH_IMAGE):
                if stop_check():
                    break
                img_src = self._get_image_url(img)
                if img_src and img_src not in seen_urls:
                    seen_urls.add(img_src)
                    on_url(img_src)


    def _get_image_url(self, img_element) -> str:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView();", img_element)
            self.driver.execute_script("arguments[0].click();", img_element)
            img_src = WebDriverWait(self.driver, self.ELEMENT_TIMEOUT).until(
                EC.presence_of_element_located((By.CLASS_NAME, self.CSS_OPENED_IMAGE))).get_attribute('src')
            self.driver.find_element(By.CSS_SELECTOR, self.CSS_CLOSE_VIEWER).click()
            return img_src
        except:
            sleep(0.2)