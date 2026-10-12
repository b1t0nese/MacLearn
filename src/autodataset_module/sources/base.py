from typing import Callable

from ..browser import ChromeBrowser



class BaseImageSource:
    name = "base"

    def __init__(self, browser: ChromeBrowser):
        self.browser = browser

    @property
    def driver(self):
        return self.browser.driver

    def collect(self, subclass_data: dict, on_image: Callable[[bytes], None],
                stop_check: Callable[[], bool], status: Callable[..., None]=None,
                example_image_path: str=None):
        raise NotImplementedError

    def stop(self):
        pass



AVAILABLE_SOURCES: dict[str, type[BaseImageSource]] = {}
DEFAULT_SOURCE = "Yandex"


def register_source(name: str=None):
    def decorator(cls):
        AVAILABLE_SOURCES[name or cls.name] = cls
        return cls
    return decorator


def get_source(name: str) -> type[BaseImageSource] | None:
    return AVAILABLE_SOURCES.get(name)


def create_source(name: str, browser: ChromeBrowser) -> BaseImageSource | None:
    source_class = get_source(name)
    if not source_class:
        return None
    return source_class(browser)