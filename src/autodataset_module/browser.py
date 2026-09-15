import shutil
import uuid
import os

from PyQt6.QtCore import QObject, pyqtSignal
from undetected_chromedriver import Chrome, ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager

from pcfuncs import get_appdata_dir
from logger import get_logger
log = get_logger("autodataset")



chromedriver_cache_path = os.path.join(get_appdata_dir(), "chromedriver.exe")

def get_session_dir(session_name: str = "default") -> str:
    return get_appdata_dir("cache", "browser_sessions", session_name)



class ChromeBrowser(QObject):
    ready = pyqtSignal(int)
    failed = pyqtSignal(str)
    closed = pyqtSignal()
    chrome_widget_lock = pyqtSignal(bool)


    def __init__(self, chromedriver_path: str=None, chrome_version: int=None,
                 chrome_headless: bool=False, session_name: str="default", parent=None):
        super().__init__(parent)
        self.chromedriver_path = chromedriver_path
        self.chrome_version = chrome_version
        self.chrome_headless = chrome_headless
        self.session_name = session_name or "default"
        self.session_dir = get_session_dir(self.session_name)
        self.driver = None
        self.chrome_pid = None
        self.locked = False
        self.used_cached_driver = False
        log.info("✓ ChromeBrowser created (headless=%s, version=%s, session=%s)",
                 chrome_headless, chrome_version, self.session_name)


    def is_ready(self) -> bool:
        return self.driver is not None


    def start(self) -> bool:
        if self.is_ready():
            return True
        log.info("▶ Starting Chrome (session dir: %s)", self.session_dir)
        error = self._start_driver(self.session_dir)
        if error and self.used_cached_driver:
            log.warning("⚠ Cached chromedriver failed (%s), refreshing cache and retrying", error)
            self.clear_driver_cache()
            error = self._start_driver(get_session_dir(f"{self.session_name}_{uuid.uuid4().hex[:8]}"))
        if error:
            log.error("✗ Chrome start failed: %s", error)
            self.failed.emit(str(error))
            return False
        log.info("✓ Chrome started (PID=%s)", self.chrome_pid)
        self.ready.emit(self.chrome_pid or 0)
        return True


    def stop(self):
        if not self.is_ready():
            return
        log.info("▶ Closing Chrome (PID=%s)", self.chrome_pid)
        try:
            self.driver.quit()
        except Exception as e:
            log.warning("⚠ Chrome quit error: %s", e)
        self.driver, self.chrome_pid = None, None
        self.closed.emit()
        log.info("✓ Chrome closed")


    def restart(self) -> bool:
        self.stop()
        return self.start()


    def lock(self, locked: bool=True):
        if self.locked == locked:
            return
        self.locked = locked
        try:
            self.chrome_widget_lock.emit(locked)
        except:
            pass


    def switch_to_main_window(self):
        if not self.is_ready():
            return
        try:
            self.driver.switch_to.window(self.driver.window_handles[0])
        except:
            pass


    def clear_driver_cache(self) -> bool:
        try:
            os.remove(chromedriver_cache_path)
            log.info("✓ chromedriver cache cleared")
            return True
        except Exception as e:
            log.warning("⚠ Could not clear chromedriver cache: %s", e)
            return False


    def clear_session_cache(self) -> bool:
        try:
            shutil.rmtree(self.session_dir)
            log.info("✓ Browser session cache cleared: %s", self.session_dir)
            return True
        except Exception as e:
            log.warning("⚠ Could not clear session cache: %s", e)
            return False


    def _start_driver(self, session_dir: str) -> str:
        try:
            os.makedirs(session_dir, exist_ok=True)
            driver_path = self._resolve_driver_path()
            driver_kwargs = {"version_main": self.chrome_version, "user_data_dir": session_dir}
            if driver_path:
                driver_kwargs["driver_executable_path"] = driver_path
            self.driver = Chrome(self._build_options(session_dir), **driver_kwargs)
            self.chrome_pid = self._get_driver_pid()
            return ""
        except Exception as e:
            log.error("✗ Chrome driver error: %s", e, exc_info=True)
            self.driver, self.chrome_pid = None, None
            return str(e)


    def _get_driver_pid(self) -> int | None:
        process = getattr(getattr(self.driver, "service", None), "process", None)
        return process.pid if process else None


    def _build_options(self, session_dir: str) -> ChromeOptions:
        options = ChromeOptions()
        if self.chrome_headless:
            options.add_argument('--headless')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-features=ChromeBrowserCloudManagement')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument(f'--disk-cache-dir={os.path.join(session_dir, "disk_cache")}')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' \
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_argument('--log-level=3')
        return options


    def _resolve_driver_path(self) -> str | None:
        self.used_cached_driver = False
        if self.chromedriver_path:
            log.debug("Using chromedriver from argument: %s", self.chromedriver_path)
            return self.chromedriver_path
        if os.path.isfile(chromedriver_cache_path):
            self.used_cached_driver = True
            log.info("✓ Using cached chromedriver: %s", chromedriver_cache_path)
            return chromedriver_cache_path
        try:
            downloaded_path = self._download_driver()
        except Exception as e:
            log.warning("⚠ Could not download chromedriver, undetected_chromedriver will handle it: %s", e)
            return None
        shutil.copy2(downloaded_path, chromedriver_cache_path)
        self.used_cached_driver = True
        log.info("✓ chromedriver cached: %s", chromedriver_cache_path)
        return chromedriver_cache_path


    def _download_driver(self) -> str:
        cache_dir = get_appdata_dir("cache", "webdriver_manager")
        try:
            return ChromeDriverManager(
                cache_manager=DriverCacheManager(root_dir=cache_dir)).install()
        except TypeError:
            log.debug("webdriver_manager without cache_manager argument, using default cache")
            return ChromeDriverManager().install()