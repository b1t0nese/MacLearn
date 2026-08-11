# `interface_module` — PyQt6 интерфейс

Отвечает за пользовательский интерфейс: главное окно, виджеты, окно логов, встраивание Chrome.

## 📄 Файлы модуля

| Файл | Назначение |
|------|------------|
| [`window.py`](#windowpy) | `MainWindowUI`, `StatisticsWindow` и виджеты |
| [`logs_window.py`](#logs_windowpy) | `LogsUI` — окно логов (интеграция с logger) |
| [`embedded_program_qt.py`](#embedded_program_qtpy) | `EmbeddedProgramWidget` — встраивание Chrome (Win32) |

---

## `window.py`

### Класс `InformationWidget(QWidget)`

Виджет «пара ключ-значение» для статистики.

| Метод | Описание |
|-------|----------|
| `__init__(title)` | Загрузка `information.ui`, настройка таблицы |
| `add_information(data)` | Заполнить таблицу из словаря |
| `clear()` | Очистить таблицу |

### Класс `StatisticsWindow(QWidget)`

Окно со статистикой датасета (несколько `InformationWidget`).

| Метод | Описание |
|-------|----------|
| `add_information(title, info)` | Добавить виджет с данными |
| `add_information_batch(data)` | Добавить много разделов |
| `clear_all()` | Очистить всё |

### Класс `ObjectCardWidget(QWidget)`

Карточка объекта (изображение + имя + кнопка удаления).

| Метод | Описание |
|-------|----------|
| `initUI(object_name, object_image, ...)` | Загрузка `object_card.ui` |
| `update_object_image(image)` | Обновить изображение (str путь или np.ndarray) |
| `delete_object()` | Удалить себя |

**Клик по изображению** — открывает диалог выбора нового файла.

### Класс `ClassFieldWidget(QWidget)`

Поле класса: checkbox, имя, объекты, кнопки.

| Метод | Описание |
|-------|----------|
| `initUI(class_name, enabled, import_export, name_enabled)` | Загрузка `class_field.ui` |
| `show_class(enabled)` | Показать/скрыть объекты |
| `add_object(name, image, ...)` | Добавить карточку объекта |
| `delete_object(widget)` | Удалить карточку |
| `get_object(name)` | Найти карточку по имени |
| `update_layout()` | Авторасположение карточек в grid |

### Класс `OverviewClassWidget(QWidget)`

Обзор класса: вкладки + поиск + scroll area.

| Метод | Описание |
|-------|----------|
| `initUI(class_name)` | Загрузка `overview_class.ui` |
| `add_field(field_widget, field_name)` | Добавить поле как вкладку |
| `remove_field(field_widget)` | Удалить поле |
| `search_update()` | Фильтрация объектов по поиску |
| `scroll_to_field(index)` | Скролл к выбранной вкладке |
| `update_tab_selection_from_scroll()` | Синхронизация вкладки при скролле |

### Класс `MainWindowUI(QMainWindow)`

Главное окно приложения.

| Метод | Описание |
|-------|----------|
| `initUI()` | Загрузка `mainwindow.ui` + инициализация вкладок |
| `project_initUI()` | Вкладка «Проект» |
| `project_add_class(name, enabled)` | Добавить класс в проект |
| `dataset_initUI()` | Вкладка «Датасет» |
| `dataset_add_class(name)` | Добавить класс |
| `dataset_add_class_field(class_name, field_name)` | Добавить поле (default/augment/validation) |
| `dataset_delete_class(widget, user_call)` | Удалить класс |
| `dataset_delete_class_field_widget(widget, user_call)` | Удалить поле |
| `dataset_update_all_class_layouts()` | Пересчитать раскладки |
| `autodataset_initUI()` | Вкладка «Автодатасет» |
| `setup_autodataset()` | Сброс статусов при новом запуске |
| `autodataset_update_statuses()` | Обновить все таблицы статусов |
| `autodataset_log(text, otstup)` | Лог в UI |
| `autodataset_set_image(path, np_image)` | Превью изображения |
| `update_autodataset_main_status(name, progress)` | Обновить статус этапа |
| `autodataset_set_object_status(...)` | Обновить статус подкласса |
| `set_btn_start_autodataset_state(state)` | Кнопка Запуск/Стоп |
| `add_another_program_to_autodataset(...)` | Вкладка с встроенным Chrome |

**Структура главного окна:**
```
MainWindowUI
├── tabWidget
│   ├── project_tab        # Вкладка «Проект»
│   │   └── project_overview (OverviewClassWidget)
│   ├── dataset_tab        # Вкладка «Датасет»
│   │   └── classes_tabs (dict[str, OverviewClassWidget])
│   └── autodataset_tab    # Вкладка «Автодатасет»
│       ├── work_tab       # Работа
│       │   ├── table_classes
│       │   ├── table_stages
│       │   ├── text_logs
│       │   ├── label_image
│       │   └── btn_start
│       └── program_tab    # Встроенный Chrome (опционально)
```

---

## `logs_window.py`

### Класс `LogsUIHandler(logging.Handler)`

Мост между `logging` и Qt-виджетом.

| Метод | Описание |
|-------|----------|
| `__init__(logs_window)` | Привязка к окну |
| `emit(record)` | Отправить запись в `logs_window.log(msg)` |

### Класс `LogsUI(QWidget)`

Окно логов с прогресс-баром.

| Метод | Описание |
|-------|----------|
| `__init__(logger_name)` | Подключение Handler к логгеру (или корневому) |
| `closeEvent(e)` | Отключение Handler при закрытии |
| `log(text, otstup)` | Добавить текст (совместимость со старым API) |
| `clear()` | Очистить |
| `set_progress(progress)` | Обновить прогресс-бар |
| `set_button(text, style, what_do)` | Настроить кнопку |
| `wait_while_not_exit()` | Блокирующий цикл до закрытия |

**Пример использования:**
```python
# Окно автоматически получает все логи логгера "main"
log_window = LogsUI("main")
log_window.show()

# Старый вызов тоже работает
log_window.log("Текст")
```

---

## `embedded_program_qt.py`

### Функция `get_window_hwnd(program_pid)`
Найти HWND окна процесса по PID (через win32gui.EnumWindows).

### Класс `EmbeddedProgramWidget(QWidget)`

Встраивание окна внешней программы (Chrome) в виджет.

| Метод | Описание |
|-------|----------|
| `__init__(process_name, process_pid)` | Поиск окна процесса |
| `showEvent(event)` | При показе — попытка встраивания |
| `embed_program()` | Встроить программу (SetParent) |
| `link_window()` | Связать HWND с виджетом |
| `move_window()` | Переместить окно в размеры виджета |
| `set_lock_resize(boolean)` | Блокировка ресайза |
| `set_window_style()` | Убрать рамки, заголовки, кнопки |
| `update_window()` | Таймер обновления (каждые 100ms) |

#### Логика встраивания

```
win32gui.SetParent(program_hwnd, self.winId())
  → стиль: убрать caption, border, sysmenu
  → MoveWindow(0, 0, width, height)
  → ShowWindow(SW_SHOW)
  → UpdateWindow
```

---

## Связи модуля

```
window.py             ──►  .embedded_program_qt (EmbeddedProgramWidget)
logs_window.py        ──►  logger (LogsUIHandler → logging)
                     ──►  uis/*.ui (Qt Designer)
embedded_program_qt   ──►  win32gui, win32process, win32con, psutil
```
