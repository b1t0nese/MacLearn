# `autodataset_module` — автоматический сбор и обработка данных

Отвечает за парсинг изображений, автоматическое создание аннотаций и аугментацию.

## 📄 Файлы модуля

| Файл | Назначение |
|------|------------|
| [`autodataset.py`](#autodatasetpy) | `AutoDataset` — QObject-воркер с сигналами |
| [`browser.py`](#browserpy) | `ChromeBrowser` — ленивый запуск Chrome, кэш драйвера и сессий |
| [`sources/`](#sources) | Источники изображений: `base.py` (реестр), `yandex_images.py` (Яндекс.Картинки) |
| [`photoshop.py`](#photoshoppy) | Обработка изображений: OpenCV, rembg, Albumentations |

---

## `autodataset.py`

### Класс `AutoDataset(QObject)`

Главный воркер, работающий в отдельном `QThread`.

#### Сигналы

| Сигнал | Тип | Назначение |
|--------|------|------------|
| `finished` | — | Работа завершена |
| `progress` | `int` | Прогресс |
| `log_field` | `(str, int)` | Лог-сообщение для UI |
| `cur_image_label` | `(str, np.ndarray)` | Текущее изображение для превью |
| `stage_updated` | `(str, tuple)` | Обновление статуса этапа |
| `subclass_updated` | `(str, int, str, int)` | Обновление статуса подкласса |

#### Метод `update_information(message, level, ...)`

**Единая точка** вывода информации:
- `level=0` → `log.info(message)` + UI
- `level=1` → `log.info("✓ ...")` + UI (OK)
- `level=2` → `log.warning(message)` + UI (WARNING)
- `level=3` → `log.info("⏭ ...")` + UI (SKIP)

Пишет одновременно и в логгер (консоль/файл), и в UI (через сигналы).

#### Методы

| Метод | Описание |
|-------|----------|
| `__init__(project_manager, chromedriver_path, chrome_version, chrome_headless, chrome_session)` | Инициализация воркера и `ChromeBrowser` (Chrome при этом не запускается) |
| `start_browser()` | Отложенный запуск Chrome (`self.browser.start()`) |
| `close()` | Закрытие источника и браузера |
| `update_project_data()` | Загрузить конфигурацию проекта |
| `update_all_information(clear)` | Обновить статусы/счётчики для UI |
| `run()` | Главный метод потока (3 фазы) |
| `stop()` | Остановка по запросу пользователя |
| `always_switch_to_main_window()` | Фоновый поток: переключение на главное окно Chrome |
| `download_images(subclass_data, ...)` | Скачивание изображений для подкласса (источник → очередь → downloader) |
| `download_images_data()` | Проход по всем классам и подклассам |
| `create_annotation_data()` | Автоматическое создание аннотаций |
| `create_augmentation_data()` | Генерация аугментаций |

#### Фазы работы `run()`

| Фаза | Метод | Описание |
|------|-------|----------|
| **1/3** | `download_images_data()` | Скачивание через источник изображений (по умолчанию `YandexImagesSource`) |
| **2/3** | `create_annotation_data()` | rembg + OpenCV контуры → bbox |
| **3/3** | `create_augmentation_data()` | Albumentations вариации |

Перед фазой 1/3 воркер вызывает `start_browser()` — Chrome стартует **лениво**, поэтому запуск
приложения не ждёт браузер. Если скачивание отключено или Chrome не запустился, фаза пропускается.

#### Скачивание (`download_images`)

Двухпоточная схема:
- **Collector** — обращается к источнику (`self.source.collect(...)`), который отдаёт найденные URL в `on_url()`
- **Downloader** — берёт URL из очереди, скачивает через `requests`, сохраняет

```
источник (sources) ──► queue ──► downloader ──► project_manager.save_image()
```

Источник создаётся в `download_images_data()` из реестра `AVAILABLE_SOURCES`; имя источника
берётся из `configuration["image_source"]` (по умолчанию `DEFAULT_SOURCE`).
`collector()` обёрнут в `try/finally`, поэтому очередь всегда закрывается (`None`) даже при ошибке сбора.

#### Остановка

`stop()` выставляет `_is_running = False` и флаг-событие сессии (`_stop_event`), а `stop_check()`
возвращает `True`, если событие выставлено **или** воркер уже не запущен. Событие создаётся заново
только при следующем `download_images()`, поэтому «залипший» коллектор (не успевший выйти за
`collector_thread.join(timeout=5)`) завершается сам и не продолжает сбор после остановки.

---

## `browser.py`

### Класс `ChromeBrowser(QObject)`

Жизненный цикл браузера: **Chrome не запускается при инициализации**, а стартует по требованию
(`start()`). Источники изображений работают с ним через `browser.driver`.

#### Сигналы

| Сигнал | Тип | Назначение |
|--------|------|------------|
| `ready` | `int` | Chrome запущен (PID) — UI встраивает окно браузера |
| `failed` | `str` | Ошибка запуска |
| `closed` | — | Chrome закрыт |
| `chrome_widget_lock` | `bool` | Блокировка ресайза встроенного окна на время автоматизации |

#### Методы

| Метод | Описание |
|-------|----------|
| `__init__(chromedriver_path, chrome_version, chrome_headless, session_name)` | Настройки запуска и папка сессии |
| `is_ready()` | Запущен ли браузер |
| `start()` / `stop()` / `restart()` | Ленивый запуск, закрытие (`driver.quit()`), перезапуск |
| `lock(locked)` | Эмит `chrome_widget_lock` |
| `switch_to_main_window()` | Переключение на первую вкладку |
| `clear_driver_cache()` | Удалить кэшированный chromedriver |
| `clear_session_cache()` | Удалить папку сессии браузера |

#### Кэш приложения

| Что | Путь |
|-----|------|
| chromedriver | `%APPDATA%/maclearn/chromedriver.exe` |
| Сессия браузера (профиль, cookies, disk cache) | `%APPDATA%/maclearn/cache/browser_sessions/<session_name>` |
| Кэш `webdriver_manager` | `%APPDATA%/maclearn/cache/webdriver_manager` |

Порядок выбора драйвера в `start()`: путь из аргумента → кэшированный `chromedriver.exe` → скачивание
через `webdriver_manager` (результат копируется в `chromedriver.exe`). Если Chrome не запустился
с кэшированным драйвером (например, драйвер устарел), кэш сбрасывается и выполняется повторная
попытка с новой сессией. Профиль сессии хранится между запусками (`user_data_dir` в `undetected_chromedriver`).

Папка данных определяется `pcfuncs.get_appdata_dir()` (Windows — `%APPDATA%\maclearn`, macOS —
`~/Library/Application Support/maclearn`, Linux — `~/.config/maclearn`). Имя драйвера берётся из
`pcfuncs.get_executable_name("chromedriver")` — в POSIX-системах это `chromedriver` без расширения,
и ему выдаются права на запуск (`pcfuncs.make_executable()`).

---

## `sources`

Пакет источников изображений: новый источник = новый файл + регистрация декоратором.

### `sources/base.py`

| Компонент | Описание |
|-----------|----------|
| `BaseImageSource` | Базовый класс: `__init__(browser, clipboard_manager)`, `collect(...)`, `stop()` |
| `collect(subclass_data, on_url, stop_check, status, example_image_path)` | Собрать ссылки на изображения |
| `AVAILABLE_SOURCES` | Реестр источников (`dict[str, type]`) |
| `DEFAULT_SOURCE` | Источник по умолчанию (`"Yandex"`) |
| `register_source(name)` | Декоратор регистрации класса источника |
| `create_source(name, browser, clipboard_manager)` | Создать источник по имени |

### `sources/yandex_images.py`

`YandexImagesSource` (`@register_source("Yandex")`) — логика и селекторы Яндекс.Картинок в одном месте:

| Метод | Описание |
|-------|----------|
| `collect(...)` | Поиск + прокрутка + сбор URL (блокировка окна на время работы) |
| `_open_search_page(query, example_image_path, stop_check)` | Поиск по фото-примеру (буфер обмена + «Похожие») |
| `_scroll_and_collect(on_url, stop_check)` | Прокрутка страницы и «Показать ещё» |
| `_get_image_url(img_element)` | Открыть изображение и получить `src` |

#### Селекторы и таймауты

Все CSS/XPath-селекторы вынесены в атрибуты класса (`CSS_SEARCH_IMAGE`, `CSS_OPENED_IMAGE`,
`CSS_CLOSE_VIEWER`, `CSS_CBIR_INTENT`, `XPATH_SHOW_MORE`, `XPATH_SIMILAR`) — при изменении вёрстки
Яндекс.Картинок править нужно только их. Таймауты: `ELEMENT_TIMEOUT`, `SCROLL_TIMEOUT`, `SIMILAR_TIMEOUT`.

#### Пример нового источника

```python
@register_source("MySource")
class MySource(BaseImageSource):
    name = "MySource"

    def collect(self, subclass_data, on_url, stop_check, status=None, example_image_path=None):
        self.browser.lock(True)
        try:
            ...
        finally:
            self.browser.lock(False)
```

---

## `photoshop.py`

### Функции

| Функция | Описание |
|---------|----------|
| `open_image(file_path, color)` | Загрузка изображения (поддержка кириллических путей через np.fromfile) |
| `resize_image(img, target_size)` | Ресайз с сохранением пропорций |
| `visualize_bbox(img, bboxes, colors)` | Рисование bounding boxes на изображении |
| `generate_augmentations(image_path, bboxes, category_ids, n)` | Генерация N аугментированных вариаций |

### `generate_augmentations`

Использует **Albumentations** со случайными параметрами:

| Трансформация | Вероятность |
|---------------|-------------|
| `AtLeastOneBBoxRandomCrop` | 0.5 |
| `HorizontalFlip` | 0.3 |
| `VerticalFlip` | 0.2 |
| `RandomRotate90` | 0.3 |
| `ShiftScaleRotate` | 0.4 |
| `OneOf(Brightness/HueSaturation/ColorJitter)` | 0.5 |
| `OneOf(Gauss/ISO/Multiplicative Noise)` | 0.3 |
| `OneOf(Blur/GaussianBlur/MedianBlur)` | 0.2 |

Аннотации автоматически пересчитываются (BboxParams format='coco', min_visibility=0.2).

### Класс `ImageAnnotation`

Работа с отдельным объектом на изображении.

| Метод | Описание |
|-------|----------|
| `formate_bbox(bbox, img_size, new_img_size, ann_type)` (static) | Форматирование bbox в YOLO / COCO / PASCAL_VOC |
| `calculate_rect()` | Аппроксимация контура, convex hull |
| `calc()` | Вычислить bbox, центр, площадь, форматы |
| `get()` | Все данные аннотации одним словарём |
| `put_contour_on_image(image, ...)` | Рисование контура/рамки |

### Класс `ImageAnnotationDetector`

Автоматическое выделение объектов.

| Метод | Описание |
|-------|----------|
| `__init__(image, max_objects, min_object_area)` | Детектор (по умолчанию 1 объект, мин. 5000px) |
| `remove_bg()` | Удаление фона через **rembg** |
| `detect_contours()` | Canny → морфология → поиск контуров |
| `smooth_contours()` | Сглаживание контуров |
| `filter_contours_to_needed()` | Фильтр по площади и количеству |
| `calculate_bboxes_data()` | Список аннотаций всех объектов |
| `put_contours_on_image(...)` | Рисование на изображении |

#### Алгоритм детекции

```
Исходное изображение
  → rembg.remove()         # удаление фона
  → GaussianBlur(11,11)    # сглаживание
  → Canny(20, 80)          # границы
  → morphologyEx(CLOSE)    # закрыть дыры
  → dilate(×3)             # усилить контуры
  → findContours(EXTERNAL) # внешние контуры
  → convexHull             # выпуклая оболочка
  → boundingRect           # bounding box
```

---

## Связи модуля

```
autodataset.py  ──►  project_module.project_manager (Project, SerialDataset)
              ──►  .browser (ChromeBrowser)
              ──►  .sources (AVAILABLE_SOURCES, DEFAULT_SOURCE, create_source)
              ──►  .photoshop (все функции)
              ──►  pcfuncs (ClipboardManager)
              ──►  logger (get_logger, LogContext)
browser.py      ──►  undetected_chromedriver, webdriver_manager
              ──►  pcfuncs (get_appdata_dir), logger
sources/*       ──►  .base (BaseImageSource, register_source)
              ──►  ../browser (ChromeBrowser), selenium, logger
photoshop.py  ──►  cv2, albumentations, rembg, numpy
```