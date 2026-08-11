# `autodataset_module` — автоматический сбор и обработка данных

Отвечает за парсинг изображений, автоматическое создание аннотаций и аугментацию.

## 📄 Файлы модуля

| Файл | Назначение |
|------|------------|
| [`autodataset.py`](#autodatasetpy) | `AutoDataset` — QObject-воркер с сигналами |
| [`photoshop.py`](#photoshoppy) | Обработка изображений: OpenCV, rembg, Albumentations |

---

## `autodataset.py`

### Класс `AutoDataset(QObject)`

Главный воркер, работающий в отдельном `QThread`.

#### Сигналы

| Сигнал | Тип | Назначение |
|--------|------|------------|
| `finished` | — | Работа завершена |
| `chrome_widget_lock` | `bool` | Заблокировать/разблокировать встроенное окно Chrome |
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
| `__init__(project_manager, chromedriver_path, chrome_version, chrome_headless)` | Инициализация Chrome driver |
| `close()` | Закрытие воркера |
| `update_project_data()` | Загрузить конфигурацию проекта |
| `update_all_information(clear)` | Обновить статусы/счётчики для UI |
| `run()` | Главный метод потока (3 фазы) |
| `stop()` | Остановка по запросу пользователя |
| `always_switch_to_main_window()` | Фоновый поток: переключение на главное окно Chrome |
| `download_images(subclass_data, ...)` | Скачивание изображений для подкласса |
| `download_images_data()` | Проход по всем классам и подклассам |
| `create_annotation_data()` | Автоматическое создание аннотаций |
| `create_augmentation_data()` | Генерация аугментаций |

#### Фазы работы `run()`

| Фаза | Метод | Описание |
|------|-------|----------|
| **1/3** | `download_images_data()` | Скачивание из Яндекс.Картинок |
| **2/3** | `create_annotation_data()` | rembg + OpenCV контуры → bbox |
| **3/3** | `create_augmentation_data()` | Albumentations вариации |

#### Скачивание (`download_images`)

Двухпоточная схема:
- **Collector** — скроллит Яндекс.Картинки, собирает URL, кладёт в `queue.Queue`
- **Downloader** — берёт URL из очереди, скачивает через `requests`, сохраняет

```
Яндекс.Картинки ──► collector ──► queue ──► downloader ──► project_manager.save_image()
```

Поддержка поиска по фото-примеру: копирование в буфер обмена (ClipboardManager) и вставка в поисковую строку.

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
              ──►  .photoshop (все функции)
              ──►  pcfuncs (ClipboardManager)
              ──►  logger (get_logger, LogContext)
photoshop.py  ──►  cv2, albumentations, rembg, numpy
```
