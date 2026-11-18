# `interface_module` — PySide6 интерфейс

Модуль содержит UI на PySide6. Зависимость устанавливается из `src/requirements.txt`;
встраивание внешних окон доступно только на платформах, где это поддерживает backend проекта.

Отвечает за пользовательский интерфейс: главное окно, виджеты, окно логов, окно настроек,
редактор аннотаций, переводы, горячие клавиши, встраивание Chrome.

## 📄 Файлы модуля

| Файл | Назначение |
|------|------------|
| [`window.py`](#windowpy) | `MainWindowUI`, `StatisticsWindow`, виджеты, drag & drop |
| [`logs_window.py`](#logs_windowpy) | `LogsUI` — окно логов (интеграция с logger) |
| [`settings_window.py`](#settings_windowpy) | `SettingsWindow` — окно настроек по вкладкам |
| [`image_editor.py`](#image_editorpy) | `ImageEditWindow` — ручная правка bounding boxes |
| [`shortcuts.py`](#shortcutspy) | `ShortcutBinder` — горячие клавиши и подсказки |
| [`translations.py`](#translationspy) | Загрузка переводов из `translations/*.json`, `tr()`, `retranslate()` |
| [`embedded_program_qt.py`](#embedded_program_qtpy) | `EmbeddedProgramWidget` — встраивание Chrome (Win32) |
| `uis/` | Qt Designer `.ui`, включая `settingswindow.ui` и `editorwindow.ui` |

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

При создании подключает `ShortcutBinder` (горячие клавиши окна).

### Класс `ObjectCardWidget(QWidget)`

Карточка объекта (изображение + имя + кнопка удаления). Две роли:

- **Подкласс** (вкладка «Проект») — клик по изображению открывает диалог выбора файла-примера; карточка принимает дроп файлов (файл станет примером).
- **Изображение датасета** — карточка создаётся с `movable=False` и `image_id`; клик открывает редактор аннотаций (обработчик передаётся через `click_image`).

| Атрибут/метод | Описание |
|---------------|----------|
| `field` | Ссылка на `ClassFieldWidget`, в котором лежит карточка |
| `movable` | Разрешено ли переносить карточку драгом (`image_id`-карточки переносит `App`) |
| `image_id` | ID записи в БД (для изображений датасета) |
| `drag_instance` (static) | Перетаскиваемая сейчас карточка (маркер для drop-таргетов) |
| `initUI(object_name, object_image, ...)` | Загрузка `object_card.ui` |
| `update_object_image(image)` | Обновить изображение (str путь или np.ndarray) |
| `start_drag()` | `QDrag` с mime `application/x-maclearn-object-card` + URL файла (для передачи между приложениями); пиктограмма — вся карточка, hotspot — точка нажатия |
| `delete_object()` | Удалить себя |

**Обработка мыши.** Нажатие/move/release на изображение перехватываются через
`eventFilter`; клик срабатывает на **отпускании** кнопки, если драг не начался
(порог `QApplication.startDragDistance()`). Карточка принимает дроп URL-файлов:
в «Проекте» это заменяет изображение-пример.

### Класс `ClassFieldWidget(QWidget)`

Поле класса: checkbox, имя, объекты, кнопки. Является drop-таргетом и (в «Проекте») drag-источником.

| Атрибут/метод | Описание |
|---------------|----------|
| `on_object_drop` | Колбэк `(card, field)` — задают карточки датасета (перенос записи в БД через `App`); без колбэка работает встроенный перенос подкласса |
| `on_files_drop` | Колбэк `(paths, field)` — задают поля датасета (импорт файлов); без колбэка создаёт подклассы |
| `reorderable` | `True` для полей «Проекта» — поле можно перетащить на другое поле для смены порядка |
| `drag_instance` (static) | Перетаскиваемое сейчас поле (mime `application/x-maclearn-class-field`) |
| `initUI(class_name, enabled, import_export, name_enabled)` | Загрузка `class_field.ui` |
| `show_class(enabled)` | Показать/скрыть объекты |
| `add_object(name, image, ...)` | Добавить карточку объекта |
| `move_object(card)` | Принять карточку драгом; при совпадении имени с существующей — мердж (дубль удаляется) |
| `delete_object(widget)` | Удалить карточку |
| `get_object(name)` | Найти карточку по имени |
| `update_layout()` | Авторасположение карточек в grid |
| `_accepted_mime(mime)` | Фильтр принимаемых форматов: карточки (чужие), поля (при reorderable), URL-файлы |
| `dropEvent(event)` | Разбор дропа: поле → `reorder_field`, карточка → `on_object_drop`/`move_object`, файлы → `on_files_drop`/создание подклассов |

### Класс `OverviewClassWidget(QWidget)`

Обзор класса: вкладки + поиск + scroll area.

| Метод | Описание |
|-------|----------|
| `initUI(class_name)` | Загрузка `overview_class.ui` |
| `add_field(field_widget, field_name)` | Добавить поле как вкладку |
| `remove_field(field_widget)` | Удалить поле |
| `reorder_field(dragged, target)` | Смена порядка полей (drag&drop): list, layout и таб-бар пересобираются |
| `search_update()` | Фильтрация объектов по поиску |
| `scroll_to_field(index)` | Скролл к выбранной вкладке |
| `update_tab_selection_from_scroll()` | Синхронизация вкладки при скролле |

### Класс `MainWindowUI(QMainWindow)`

Главное окно приложения.

| Метод | Описание |
|-------|----------|
| `initUI()` | Загрузка `mainwindow.ui` + инициализация вкладок |
| `project_initUI()` | Вкладка «Проект» (поля классов создаются с `reorderable=True`) |
| `project_add_class(name, enabled)` | Добавить класс в проект |
| `dataset_initUI()` | Вкладка «Датасет» + приём дропов на `tab_bar` классов |
| `dataset_add_class(name)` | Добавить класс |
| `dataset_add_class_field(class_name, field_name)` | Добавить поле (default/augment/validation) |
| `dataset_delete_class(widget, user_call)` | Удалить класс |
| `dataset_delete_class_field_widget(widget, user_call)` | Удалить поле |
| `dataset_open_class_by_tab_drop(pos)` | Дроп изображения на вкладку класса — открыть её |
| `_activate_hovered_class_tab()` | Активация вкладки после наведения драга (таймер 400 мс) |
| `eventFilter(watched, event)` | DragEnter/DragMove/Drop на `tab_bar` классов датасета |
| `dataset_update_all_class_layouts()` | Пересчитать раскладки |
| `autodataset_initUI()` | Вкладка «Автодатасет» |
| `setup_autodataset()` | Сброс статусов при новом запуске |
| `autodataset_update_statuses()` | Обновить все таблицы статусов |
| `autodataset_log(text, otstup)` | Лог в UI |
| `autodataset_set_image(path, np_image)` | Превью изображения |
| `update_autodataset_main_status(name, progress)` | Обновить статус этапа |
| `autodataset_set_object_status(...)` | Обновить статус подкласса |
| `set_btn_start_autodataset_state(state)` | Кнопка Запуск/Стоп |
| `autodataset_embed_chrome(pid)` | Слот сигнала `ChromeBrowser.ready` — встроить окно Chrome |
| `autodataset_set_chrome_lock(locked)` | Слот сигнала `ChromeBrowser.chrome_widget_lock` |
| `add_another_program_to_autodataset(...)` | Вкладка с встроенным Chrome |

**Структура главного окна:**
```
MainWindowUI
├── tabWidget
│   ├── project_tab        # Вкладка «Проект»
│   │   └── project_overview (OverviewClassWidget)
│   ├── dataset_tab        # Вкладка «Датасет»
│   │   ├── classes_tabs (dict[str, OverviewClassWidget])
│   │   └── tab_bar        # приём дропов изображений
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

При создании подключает `ShortcutBinder` (клавиша окна закрывает его).

---

## `settings_window.py`

### Класс `SettingsWindow(QWidget)`

Окно настроек приложения (см. `src/settings.py`), UI — `uis/settingswindow.ui`, вкладки:
«Интерфейс» (язык), «Chrome» (драйвер, версия, сессия, окно), «Аннотации (SAM3)»
(устройство, confidence, мин. площадь, веса, одно обнаружение), «Аугментация»
(восемь вероятностей пресета Albumentations).

| Метод | Описание |
|-------|----------|
| `__init__(settings, on_save)` | Заполнение полей из словаря настроек; колбэк сохранения |
| `fill(settings)` | Настройки → виджеты |
| `collect()` | Виджеты → словарь настроек (в формате `DEFAULT_SETTINGS`) |
| `browse_chromedriver()` / `browse_sam3_weights()` | Диалоги выбора файлов |

Сохранение: `save_settings()` → `on_save(collect())` (в `App.apply_app_settings`)
→ запись `settings.json` + применение к живому воркеру без перезапуска.

---

## `image_editor.py`

### Класс `ImageEditWindow(QWidget)`

Ручная правка аннотаций, UI — `uis/editorwindow.ui`: `QGraphicsView` с изображением
(вписывается в окно, `fitInView`), таблица аннотаций `class/x/y/w/h`, режимы
«Перемещение» (тянуть рамку) и «Изменение расположения» (нарисовать рамку заново
или добавить новую), список классов, навигация «‹»/«›» по изображениям того же
класса и типа.

| Метод | Описание |
|-------|----------|
| `load_image(image_id, save_current)` | Загрузка изображения и bbox; `save_current=True` автосохраняет предыдущее |
| `navigate(step)` | Предыдущее/следующее изображение класса (с автосохранением) |
| `save_annotation()` | Записать bbox в БД (`change_image`) |
| `select_bbox(index)` / `apply_selection()` | Выделение рамки, синхронизация с таблицей и списком классов |
| `add_bbox_row()` / `remove_selected_bbox()` | Кнопки «+/−» таблицы |
| `table_item_changed(item)` | Правка координат в таблице → рамка на сцене |
| `handle_mouse_press/move/release` | Сцена: перенос рамки (move) или рисование (draw), координаты пересчитываются из сцены в пиксели изображения |
| `to_image_pos(scene_pos)` | Координаты сцены → пиксели изображения (None вне изображения) |

Автосохранение: при `closeEvent` и при смене изображения. `on_save` вызывает
обновление превью датасета в `App`.

---

## `shortcuts.py`

### Класс `ShortcutBinder(QObject)`

Автоматические горячие клавиши окна. Подключается ко всем окнам приложения
(главное, настройки, логи, статистика, редактор).

| Механизм | Описание |
|----------|----------|
| Кнопки | Каждой `QAbstractButton` с текстом назначается «голая» клавиша — первая свободная буква названия (`Запуск` → `[З]`); нажатие вызывает `animateClick()` |
| Меню | Каждому `QAction` назначается `Ctrl+<буква>` |
| Подсказки | К tooltip элемента добавляется `[клавиша]` |
| Фильтр ввода | Клавиши не срабатывают, пока фокус в `QLineEdit`/`QTextEdit`/`QComboBox`/`QSpinBox` |
| Перехват | `eventFilter` ставится на `QApplication`; события обрабатываются, только если событие пришло в окно биндерa |

| Метод | Описание |
|-------|----------|
| `rebuild()` | Собрать свободные клавиши по кнопкам и действиям окна |
| `key_bindings` | Словарь «клавиша → кнопка» |

---

## `translations.py`

Загрузчик переводов. Исходный язык интерфейса — русский; переводы лежат в
`translations/<код>.json` (`{"name": "...", "translations": {"Файл": "File", ...}}`)
и подхватываются автоматически при старте — новый язык = новый JSON-файл без правок кода.

| Компонент | Описание |
|-----------|----------|
| `LANGUAGES` | Реестр языков `{код: название}` (из JSON) |
| `tr(text)` | Перевод строки на текущий язык (для русского — обратный поиск по переводам) |
| `set_language(code)` / `get_language()` | Текущий язык |
| `retranslate(widget)` | Рекурсивный перевод открытого окна: заголовки, tooltip'ы, тексты QLabel/PushButton/CheckBox, QLineEdit placeholder, QGroupBox/QMenu title, вкладки QTabWidget/QTabBar, заголовки колонок QTableWidget, QAction |

Файлы `translations/` включаются в сборки через `--include-data-dir` в скриптах сборки.

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
                      ──►  .translations (tr), .shortcuts (ShortcutBinder)
                      ──►  logger, uis/*.ui (Qt Designer)
logs_window.py        ──►  logger (LogsUIHandler → logging)
                      ──►  .shortcuts (ShortcutBinder), uis/*.ui
settings_window.py    ──►  settings (DEFAULT_SETTINGS), .translations, .shortcuts
                      ──►  uis/settingswindow.ui
image_editor.py       ──►  project_module (Project.change_image), photoshop (open_image)
                      ──►  .translations, .shortcuts, uis/editorwindow.ui
shortcuts.py          ──►  logger
translations.py       ──►  translations/*.json
embedded_program_qt   ──►  win32gui, win32process, win32con, psutil
```