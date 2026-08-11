# `project_module` — работа с проектами и данными

Отвечает за хранение, управление и экспорт датасетов.

## 📄 Файлы модуля

| Файл | Назначение |
|------|------------|
| [`project_manager.py`](#project_managerpy) | Базовые классы: `Dataset`, `Project`, `SerialDataset`, статистика |
| [`dataset_manager.py`](#dataset_managerpy) | Экспорт датасетов: `BaseDataset`, `YOLOdataset`, `CSVdataset` |

---

## Функции (общие)

### `get_image_type(image_bytes) -> str`
Определяет формат изображения по байтам через `filetype`.

### `to_snake_case(text) -> str`
Транслитерация русского текста в snake_case (для имён файлов).

---

## `project_manager.py`

### Функции

| Функция | Описание |
|---------|----------|
| `get_image_type(image_bytes)` | Определить расширение изображения по байтам |
| `to_snake_case(text)` | Транслитерация в snake_case |
| `get_dataset_statistics(project)` | Полная статистика датасета (словарь) |

### Класс `Dataset`

Работа с SQLite-базой проекта (`project.sqlite`).

#### Таблицы БД

| Таблица | Назначение |
|---------|------------|
| `configuration` | Ключ-значение настроек проекта |
| `classes_conf` | Классы (id, class_name, enabled, subclasses JSON) |
| `dataset` | Изображения (id, filename, class_id, type, annotation, parent_image_id) |

#### Методы

| Метод | Описание |
|-------|----------|
| `get_connection()` | SQLite-подключение (check_same_thread=False) |
| `close_all_connections()` | Закрыть все подключения |
| `initDB()` | Создать таблицы (если нет) |
| `set_configutation(conf_data)` | Сохранить конфигурацию |
| `get_configutation()` | Получить конфигурацию (с типами int/bool) |
| `add_or_upd_class_conf(...)` | Добавить/обновить класс |
| `del_class_conf(class_id, class_name)` | Удалить класс |
| `get_class_conf(...)` | Получить класс |
| `get_all_classes_conf(enabled)` | Все классы (опц. фильтр) |
| `get_classes_ids_numbers(rev)` | Маппинг class_id ↔ индекс |
| `save_image(bytes, class_id, type, annotation, parent)` | Сохранить изображение |
| `change_image(...)` | Изменить запись изображения |
| `del_image(image_id, filename)` | Удалить изображение + файл |
| `get_image(...)` | Получить запись изображения |
| `get_images(**kwargs)` | Получить все изображения по фильтрам |

**Файловая структура проекта:**
```
project/
├── project.sqlite     # БД (SQLite)
├── images/            # Файлы изображений
├── example_images/    # Примеры для поиска
└── dataset/           # Экспортированные датасеты
```

### Класс `Project(Dataset)`

Наследует `Dataset`, добавляет работу с путями и zip-архивами.

| Метод | Описание |
|-------|----------|
| `__init__(path)` | Поддержка `.maclproj` (zip) или папки |
| `save(configuration, classes_conf)` | Сохранить конфигурацию + классы |
| `save_as(to_path)` | Сохранить как zip/папку |
| `path_is_project(path)` | Проверить, является ли путь проектом |
| `get_full_path(*parts)` | Полный путь до элемента структуры |
| `get_project_conf()` | Полная конфигурация проекта |
| `add_subclass_example_image(subclass)` | Скопировать пример в `example_images/` |
| `makedirs_ifnotexc()` | Создать структуру папок |
| `add_skipped_paths()` | Сканировать файловую систему в структуру |

### Класс `SerialDataset(Project)`

Последовательный проект: авто-инкремент позиции при добавлении изображений.

| Метод | Описание |
|-------|----------|
| `set_position(class_id, image_id)` | Установить позицию |
| `next()` | Перейти к следующему изображению/классу |
| `add_image(image_bytes, call_func)` | Добавить изображение + вернуть данные |

---

## `dataset_manager.py`

### Класс `BaseDataset(Project)`

Базовый класс для экспорта датасетов. Регистрируется через `AVAILABLE_FORMATS`.

| Метод | Описание |
|-------|----------|
| `from_project(project)` | Создать экземпляр из существующего проекта |
| `export()` | Экспорт датасета (переопределяется) |
| `put_data(dataset_path)` | Скопировать датасет в целевую папку |
| `get_dataset_path()` | Авто-путь: `<имя_проекта>_dataset` |
| `clear()` | Удалить временную папку `dataset/` |

### Функция `register_formatter(name)`
Декоратор: регистрирует класс в `AVAILABLE_FORMATS`.

### Функция `export_image(...)`
Экспорт изображения с resize в JPG (качество 95).

### `YOLOdataset`

Экспорт в формате **YOLO**:

```
dataset/
├── data.yaml          # конфигурация (nc, names, path)
├── train/
│   ├── 0/             # класс 0
│   │   ├── img.jpg
│   │   └── labels/    # .txt файлы аннотаций
│   └── 1/             # класс 1
└── val/
    └── ...
```

- `create_paths(classes_len, annotation)` — структура папок
- `create_yaml_config(classes_config)` — data.yaml
- `export_data(classes_config, images_size)` — изображения с resize
- `create_annotations()` — YOLO-формат аннотаций (нормализованные)

### `CSVdataset`

Экспорт в формате **CSV**:

```
dataset/
├── train.csv
├── val.csv
└── train/images/
└── val/images/
```

- С аннотациями: `filename, class_id, x_min, y_min, x_max, y_max`
- Без аннотаций: `filename, class_id`

---

## Связи модуля

```
project_manager.py  ──►  autodataset_module.photoshop (open_image)
dataset_manager.py  ──►  project_manager (Project)
                    ──►  autodataset_module.photoshop (export_image)
```
