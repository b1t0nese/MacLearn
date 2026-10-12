from urllib.parse import quote as url_quote
from time import sleep, time as ntime

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
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
    XPATH_SHOW_MORE = "//button[.//span[text()='Показать ещё']]"

    ELEMENT_TIMEOUT = 10
    SCROLL_TIMEOUT = 5
    SIMILAR_TIMEOUT = 30


    def collect(self, subclass_data: dict, on_url, stop_check, status=None, example_image_path: str=None):
        search_query = subclass_data["search_query"]
        self.browser.lock(True)
        try:
            status("Searching images...", 0)
            if example_image_path:
                if not self._open_search_page(example_image_path, stop_check):
                    log.warning("⚠ Image search failed, text query fallback is disabled")
                    return
            else:
                if stop_check():
                    return
                self.driver.get(self.TEXT_SEARCH_URL.format(query=url_quote(search_query)))
            if stop_check():
                return
            status("Loading images...", 0)
            self._scroll_and_collect(on_url, stop_check)
        finally:
            self.browser.lock(False)


    def _open_search_page(self, example_image_path: str, stop_check) -> bool:
        if not example_image_path:
            return False
        try:
            self.driver.get(self.SEARCH_URL)
            file_input = WebDriverWait(self.driver, self.ELEMENT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".CbirCore-FileInput")))
            file_input.send_keys(example_image_path)
            start = ntime()
            while not stop_check():
                try:
                    WebDriverWait(self.driver, self.ELEMENT_TIMEOUT).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "a.CbirNavigation-TabsItem[data-cbir-page-type='similar']"))).click()
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
            if stop_check():
                break
            page_stopped_growing = ntime() - scroll_start >= self.SCROLL_TIMEOUT
            last_height = new_height
            for img in self.driver.find_elements(By.CSS_SELECTOR, self.CSS_SEARCH_IMAGE):
                if stop_check():
                    break
                image_url = self._get_image_url(img)
                if image_url and image_url not in seen_urls:
                    seen_urls.add(image_url)
                    on_url(image_url)
            if page_stopped_growing and not stop_check():
                try:
                    self.driver.find_element(By.XPATH, self.XPATH_SHOW_MORE).click()
                    sleep(1)
                except Exception as error:
                    log.warning("⚠ Could not load more images: %s", error)


    def _get_image_url(self, img_element) -> str | None:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView();", img_element)
            self.driver.execute_script("arguments[0].click();", img_element)
            image_url = WebDriverWait(self.driver, self.ELEMENT_TIMEOUT).until(
                EC.presence_of_element_located((By.CLASS_NAME, self.CSS_OPENED_IMAGE)))
            image_url = image_url.get_attribute("src")
            self.driver.find_element(By.CSS_SELECTOR, self.CSS_CLOSE_VIEWER).click()
            return image_url
        except WebDriverException as error:
            if "invalid session id" in str(error).lower():
                raise RuntimeError("Browser session was lost while collecting image data") from error
            log.warning("⚠ Could not collect image data: %s", error)
            sleep(0.2)
        except Exception as error:
            log.warning("⚠ Could not collect image data: %s", error)
            sleep(0.2)