# `autodataset_module` — автоматический сбор и обработка данных

Отвечает за парсинг изображений, автоматическое создание аннотаций и аугментацию.

## 📄 Файлы модуля

| Файл | Назначение |
|------|------------|
| [`autodataset.py`](#autodatasetpy) | `AutoDataset` — QObject-воркер с сигналами |
| [`browser.py`](#browserpy) | `ChromeBrowser` — ленивый запуск Chrome, кэш драйвера и сессий |
| [`sources/`](#sources) | Источники изображений: `base.py` (реестр), `yandex_images.py` (Яндекс.Картинки) |
| [`photoshop.py`](#photoshoppy) | Обработка изображений: SAM3, OpenCV, Albumentations |

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
| `browser.start()` | Отложенный запуск Chrome перед фазой сбора |
| `close()` | Закрытие источника и браузера |
| `detach_from_thread()` | Возврат воркера в поток приложения (вызывается сигналом `finished` из рабочего потока) |
| `update_project_data()` | Загрузить конфигурацию проекта |
| `update_all_information(clear)` | Обновить статусы/счётчики для UI |
| `run()` | Главный метод потока (3 фазы) |
| `stop()` | Остановка по запросу пользователя |
| `always_switch_to_main_window()` | Фоновый поток: переключение на главное окно Chrome |
| `download_images(subclass_data, ...)` | Последовательный сбор и сохранение изображений для подкласса |
| `download_images_data()` | Проход по всем классам и подклассам |
| `create_annotation_data()` | Автоматическое создание аннотаций |
| `create_augmentation_data()` | Генерация аугментаций |

#### Фазы работы `run()`

| Фаза | Метод | Описание |
|------|-------|----------|
| **1/3** | `download_images_data()` | Скачивание через источник изображений (по умолчанию `YandexImagesSource`) |
| **2/3** | `create_annotation_data()` | SAM3 текстовые промпты → bbox |
| **3/3** | `create_augmentation_data()` | Albumentations вариации |

Перед фазой 1/3 воркер вызывает `browser.start()` — Chrome стартует **лениво**, поэтому запуск
приложения не ждёт браузер. Если скачивание отключено или Chrome не запустился, фаза пропускается.

#### Скачивание (`download_images`)

Однопоточная схема:
- Источник получает содержимое изображения из браузера и передаёт байты callback-функции
- `Project` сразу сохраняет полученные байты без повторного HTTP-запроса

```
источник (sources) ──► image bytes ──► project_manager.save_image()
```

Источник создаётся в `download_images_data()` из реестра `AVAILABLE_SOURCES`; имя источника
берётся из `configuration["image_source"]` (по умолчанию `DEFAULT_SOURCE`).
Источник прекращает сбор через `stop_check()`, когда необходимое количество изображений сохранено.

#### Остановка

`stop()` выставляет `_is_running = False` и флаг-событие сессии (`_stop_event`), а `stop_check()`
возвращает `True`, если событие выставлено **или** воркер уже не запущен. Событие создаётся заново
при следующем `download_images()`, поэтому источник прекращает сбор и не сохраняет новые изображения
после остановки.

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
| `kill_session_processes(session_dir)` | Закрыть процессы браузера, запущенные для папки сессии (окно-сирота после ошибки старта) |

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
и ему выдаются права на запуск и валидная подпись (`pcfuncs.prepare_executable()`).

#### macOS: подпись `chromedriver`

`undetected_chromedriver` перед запуском патчит chromedriver «на месте», из-за чего ломается подпись
кода Google, и macOS убивает драйвер сигналом `SIGKILL` (`Status code was: -9`, в системном логе —
`CODE SIGNING: cs_invalid_page ... sending SIGKILL`). Поэтому драйвер патчится заранее
(`_prepare_driver_for_macos()`), сразу после патча получает ad-hoc подпись (`pcfuncs.sign_macos_binary()`),
а патчер `undetected_chromedriver` при следующем вызове видит свой маркер (`undetected chromedriver`)
и файл больше не меняет.

#### Окно-сирота после ошибки старта

`undetected_chromedriver` запускает Chrome **до** старта chromedriver, поэтому при любой ошибке старта
остаётся окно браузера, хотя UI считает, что Chrome не запущен. Метод `kill_session_processes()`
(через `pcfuncs.kill_processes_by_marker()`) закрывает такие процессы по `--user-data-dir=<папка сессии>`:
он вызывается перед стартом и после неудачной попытки.

---

## `sources`

Пакет источников изображений: новый источник = новый файл + регистрация декоратором.

### `sources/base.py`

| Компонент | Описание |
|-----------|----------|
| `BaseImageSource` | Базовый класс: `__init__(browser)`, `collect(...)`, `stop()` |
| `collect(subclass_data, on_image, stop_check, status, example_image_path)` | Получить и передать байты изображений |
| `AVAILABLE_SOURCES` | Реестр источников (`dict[str, type]`) |
| `DEFAULT_SOURCE` | Источник по умолчанию (`"Yandex"`) |
| `register_source(name)` | Декоратор регистрации класса источника |
| `create_source(name, browser)` | Создать источник по имени |

### `sources/yandex_images.py`

`YandexImagesSource` (`@register_source("Yandex")`) — логика и селекторы Яндекс.Картинок в одном месте:

| Метод | Описание |
|-------|----------|
| `collect(...)` | Поиск + прокрутка + получение байтов (блокировка окна на время работы) |
| `_open_search_page(example_image_path, stop_check)` | Поиск по фото-примеру и переход на «Похожие» |
| `_scroll_and_collect(on_image, stop_check)` | Прокрутка страницы и «Показать ещё» |
| `_get_image_data(img_element)` | Открыть изображение и получить `src` и байты |

#### Селекторы и таймауты

Все CSS/XPath-селекторы вынесены в атрибуты класса (`CSS_SEARCH_IMAGE`, `CSS_OPENED_IMAGE`,
`CSS_CLOSE_VIEWER`, `XPATH_SHOW_MORE`) — при изменении вёрстки
Яндекс.Картинок править нужно только их. Таймауты: `ELEMENT_TIMEOUT`, `SCROLL_TIMEOUT`, `SIMILAR_TIMEOUT`.

#### Пример нового источника

```python
@register_source("MySource")
class MySource(BaseImageSource):
    name = "MySource"

    def collect(self, subclass_data, on_image, stop_check, status=None, example_image_path=None):
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
| `remove_bg()` | Запуск SAM3 по промптам классов |
| `detect_contours()` | Совместимый пустой этап после SAM3 |
| `smooth_contours()` | Совместимый пустой этап после SAM3 |
| `filter_contours_to_needed()` | Совместимый пустой этап после SAM3 |
| `calculate_bboxes_data()` | Преобразование результатов SAM3 в bbox |
| `put_contours_on_image(...)` | Рисование на изображении |

#### Алгоритм детекции

```
Исходное изображение
  → SAM3 текстовые промпты классов
  → NMS и фильтрация площади
  → bounding box
```

---

## Связи модуля

```
autodataset.py  ──►  project_module.project_manager (Project, SerialDataset)
              ──►  .browser (ChromeBrowser)
              ──►  .sources (AVAILABLE_SOURCES, DEFAULT_SOURCE, create_source)
              ──►  .photoshop (все функции)
              ──►  pcfuncs
              ──►  logger (get_logger, LogContext)
browser.py      ──►  undetected_chromedriver, webdriver_manager
              ──►  pcfuncs (get_appdata_dir), logger
sources/*       ──►  .base (BaseImageSource, register_source)
              ──►  ../browser (ChromeBrowser), selenium, logger
photoshop.py  ──► cv2, albumentations, sam3_studio_lib, numpy
```