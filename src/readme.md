# MacLearn — Документация по коду

Техническая документация по архитектуре, модулям и внутреннему устройству проекта **MacLearn**.

---

## Оглавление

- [Архитектура](#архитектура)
- [Структура проекта](#структура-проекта)
- [Корневые модули](#корневые-модули)
  - [`src/main.py` — точка входа, главный контроллер](#srcmainpy)
  - [`src/logger.py` — система логирования](#srcloggerpy)
  - [`src/pcfuncs.py` — утилиты](#srcpcfuncspy)
  - [`src/settings.py` — настройки приложения](#srcsettingspy)
- [Модули](#модули)
  - [`project_module`](https://github.com/b1t0nese/MacLearn/blob/main/src/project_module/readme.md) — проекты, SQLite, экспорт
  - [`autodataset_module`](https://github.com/b1t0nese/MacLearn/blob/main/src/autodataset_module/readme.md) — сбор данных, аннотации, аугментация
  - [`interface_module`](https://github.com/b1t0nese/MacLearn/blob/main/src/interface_module/readme.md) — PySide6 интерфейс
- [Поток выполнения](#поток-выполнения)
- [Взаимодействие модулей](#взаимодействие-модулей)

---

## Архитектура

```
                ┌─────────────────────────┐
                │      main.py (App)      │
                │   Главный контроллер    │
                └──────┬─────────┬────────┘
                       │         │
          ┌────────────▼───┐ ┌───▼────────────────┐
          │interface_module│ │ autodataset_module │
          │   (PySide6 UI) │ │  (сбор/аннотации)  │
          └───────┬────────┘ └──────────┬─────────┘
                  │                     │
          ┌───────▼──────────┐  ┌───────▼───────────┐
          │ project_module   │  │  logger.py        │
          │ (SQLite/проекты) │  │  (логирование)    │
          └──────────────────┘  └───────────────────┘
```

`main.py` — оркестратор: связывает UI, проекта и автодатасет.
`logger.py` — центральная система логирования, используется всеми модулями.
`pcfuncs.py` — низкоуровневые кроссплатформенные утилиты, работа с процессами и путями приложения.

---

## Структура проекта

```
maclearn/
├── src/requirements.txt                # Зависимости проекта
├── scripts/                            # Скрипты сборки (Nuitka)
└── src/
    ├── main.py                         # Точка входа, класс App
    ├── logger.py                       # Система логирования
    ├── pcfuncs.py                      # Утилиты
    ├── settings.py                     # Настройки приложения (settings.json)
    ├── autodataset_module/
    │   ├── autodataset.py              # AutoDataset (QObject)
    │   ├── browser.py                  # ChromeBrowser — ленивый запуск Chrome, кэш
    │   ├── sources/                    # источники изображений (реестр)
    │   │   ├── base.py                 # BaseImageSource, AVAILABLE_SOURCES
    │   │   └── yandex_images.py        # YandexImagesSource
    │   └── photoshop.py                # Обработка изображений
    ├── project_module/
    │   ├── project_manager.py          # Dataset, Project, статистика
    │   ├── dataset_manager.py          # Экспорт (YOLO, CSV)
    │   └── __init__.py
    ├── interface_module/
        ├── window.py                   # MainWindowUI, виджеты, drag & drop
        ├── logs_window.py              # Окно логов
        ├── settings_window.py          # Окно настроек (вкладки)
        ├── image_editor.py             # Редактор аннотаций (QGraphicsView)
        ├── shortcuts.py                # Горячие клавиши и подсказки
        ├── translations.py             # Загрузчик переводов + retranslate
        ├── translations/               # Файлы переводов (ru.json, en.json, ...)
        ├── embedded_program_qt.py      # Встраивание Chrome
        ├── __init__.py
        └── uis/                        # Qt Designer .ui
            ├── mainwindow.ui
            ├── logswindow.ui
            ├── statisticswindow.ui
            ├── settingswindow.ui
            ├── editorwindow.ui
            ├── tabs/
            │   ├── project_tab.ui
            │   ├── dataset_tab.ui
            │   └── autodataset_tab.ui
            └── widgets/
                ├── class_field.ui
                ├── object_card.ui
                ├── overview_class.ui
                └── information.ui
    └── sam3_studio_lib/                 # SAM3-аннотация и экспорт
```

---

# Корневые модули

## `src/main.py`

**Роль:** точка входа и главный контроллер приложения.

### Импорты

| Источник | Что берёт |
|----------|-----------|
| `PySide6.QtWidgets` | QApplication, QFileDialog, QMessageBox |
| `PySide6.QtGui` | QAction, QActionGroup, QDesktopServices |
| `PySide6.QtCore` | QThread, QUrl |
| `qdarkstyle` | Тёмная тема |
| `project_module.project_manager` | `Project`, `get_dataset_statistics` |
| `autodataset_module.autodataset` | `AutoDataset` |
| `autodataset_module.browser` | `get_session_dir` |
| `project_module.dataset_manager` | `AVAILABLE_FORMATS` |
| `interface_module.window` | `MainWindowUI`, `StatisticsWindow` |
| `interface_module.logs_window` | `LogsUI` |
| `interface_module.settings_window` | `SettingsWindow` |
| `interface_module.image_editor` | `ImageEditWindow` |
| `interface_module.shortcuts` | `ShortcutBinder` |
| `interface_module.translations` | `LANGUAGES`, `get_language`, `set_language`, `retranslate`, `tr` |
| `autodataset_module.photoshop` | `visualize_bbox`, `open_image` |
| `pcfuncs` | Кроссплатформенные утилиты и запуск новых экземпляров |
| `logger` | `get_logger`, `log_call`, `LogContext`, `SessionLogger`, `install_exception_hook`, `set_console_level` |
| `settings` | `load_settings`, `save_settings` |

### Глобальная инициализация

```python
log = get_logger("main")           # Логгер для главного модуля
session = SessionLogger("main")     # Сессия приложения
install_exception_hook(log)         # Глобальный перехват исключений
```

### Класс `App`

Главный класс, связывающий всё приложение.

| Атрибут | Тип | Назначение |
|---------|-----|------------|
| `config` | dict | Конфигурация запуска (аргументы CLI) |
| `autodataset_worker` | `AutoDataset` | Рабочий поток автодатасета |
| `autodataset_thread` | `QThread` | Qt-поток для автодатасета |
| `appApplication` | `QApplication` | Экземпляр Qt |
| `windowUI` | `MainWindowUI` | Главное окно |
| `statistics_window` | `StatisticsWindow` | Окно статистики |

#### Методы

| Метод | Описание |
|-------|----------|
| `__init__(self, **config)` | Загрузка настроек, язык, старт сессии, открытие проекта |
| `start(app)` | Запуск Qt event loop с тёмной темой |
| `close_application(event, exit_code)` | Корректное закрытие (воркер → окна → user later GUI) |
| `new_window(project_path)` | Создание окна для проекта (3 этапа: Project, AutoDataset, UI) |
| `init_config_window()` | Подключение сигналов UI-элементов |
| `init_language_menu()` | Заполнение меню «Язык / Language» (QUiLoader игнорирует подменю из .ui) |
| `change_language(code)` | Смена языка: перевод, сохранение в настройки |
| `open_settings_window()` | Открыть окно настроек |
| `apply_app_settings(settings)` | Сохранить настройки, применить Chrome/сессию к живому воркеру |
| `init_project_conf_in_window()` | Загрузка конфигурации проекта в UI |
| `update_dataset_view_in_window()` | Синхронизация UI датасета с БД |
| `open_image_editor(image_id)` | Открыть редактор аннотаций (окно переиспользуется по image_id) |
| `move_image_to_class(card, class_id, field)` | Drag&drop изображения: перенос записи в БД |
| `drop_images_to_class(paths, class_id, type)` | Drag&drop файлов из проводника: импорт в класс |
| `open_project(project_path)` | Открыть проект |
| `new_project()` | Создать пустой проект `.maclproj` и открыть его |
| `open_project_as_dir()` | Открыть проект как папку (диалог) |
| `save_project()` | Сохранение конфигурации из UI в БД |
| `save_project_as()` | Сохранить как `.maclproj` (zip) |
| `save_project_as_dir()` | Сохранить как папку |
| `export_dataset_data()` | Экспорт датасета по выбранному формату |
| `toggle_autodataset_work()` | Запуск/остановка автодатасета |
| `start_autodataset()` | Запуск воркера в QThread |
| `stop_autodataset()` | Остановка воркера |
| `on_autodataset_finished()` | Колбэк по завершении + уведомление |
| `autodataset_worker_connect_signals()` | Подключение сигналов воркера к UI |
| `autodataset_worker_disconnect_signals()` | Отключение сигналов |

`__init__` загружает `settings.json` (`load_settings()`), применяет язык (`set_language`)
и мержит CLI-аргументы с настройками: параметры Chrome берутся из CLI, если переданы,
иначе из сохранённых настроек (`_apply_chrome_settings`).

#### Поток воркера

`start_autodataset()` создаёт новый `QThread`, переносит в него `autodataset_worker` (`moveToThread`)
и подключает сигналы: `started` → `run()`, `finished` → `thread.quit()` и
`finished` → `worker.detach_from_thread()`. Последняя связка обязательна: Qt разрешает менять поток
объекта только из его собственного потока, поэтому воркер возвращается в поток приложения ещё
**внутри** рабочего потока. Иначе `delete_autodataset_thread()` не сможет его вернуть: в лог
попадёт `QObject::moveToThread: Current thread ... is not the object's thread`, а воркер останется
привязанным к уже завершённому `QThread` и следующий запуск не начнётся.

### Функция `main()`

Разбирает аргументы CLI и запускает приложение:

| Аргумент | Тип | Описание |
|----------|-----|----------|
| `--project-path PATH` | str (опц.) | Путь к существующему проекту; без аргумента запускается создание нового |
| `--chrome-version VERSION` | int | Версия Chrome |
| `--chromedriver-path PATH` | str | Путь к chromedriver |
| `--chrome-no-headless` | flag | Показать окно Chrome; по умолчанию headless |
| `--chrome-session NAME` | str | Имя сессии браузера (отдельный профиль/кэш) |
| `--language ru\|en` | str | Язык интерфейса (переопределяет настройку) |
| `--log-level DEBUG\|INFO\|WARNING\|ERROR` | str | Уровень консольных логов (`set_console_level`) |

---

## `src/logger.py`

**Роль:** профессиональная система логирования, используемая всеми модулями.

### Компоненты

| Компонент | Тип | Описание |
|-----------|-----|----------|
| `ColoredFormatter` | class | Цветной форматтер для консоли с эмодзи |
| `FileFormatter` | class | Компактный форматтер для файла |
| `setup_logger(name, level, log_file, console)` | fn | Настройка логгера (файл + консоль) |
| `get_logger(name)` | fn | Получение/авто-создание логгера |
| `@log_call(logger, level)` | decorator | Трассировка вход/выход функции |
| `@log_timing(logger)` | decorator | Замер времени выполнения |
| `LogContext(name, logger, level)` | class | Контекстный менеджер блока |
| `SessionLogger(name)` | class | Логгер сессии приложения |
| `install_exception_hook(logger)` | fn | Глобальный перехват исключений |

### Цвета и иконки

| Уровень | Цвет | Иконка |
|---------|------|--------|
| DEBUG | Серый | 🔍 |
| INFO | Синий | ℹ️ |
| OK | Зелёный | ✅ |
| WARNING | Оранжевый | ⚠️ |
| ERROR | Красный | ❌ |
| CRITICAL | Ярко-красный | 💥 |

### Формат файлового лога

```
[2025-08-11 13:31:00] [INFO] [main] ▶ Application starting...
[2025-08-11 13:31:01] [INFO] [autodataset] ✓ Chrome driver started (PID=12345)
```

### Ротация файлов

- Максимальный размер: **10 MB**
- Резервных копий: **5**
- Папка: `%APPDATA%/maclearn/logs/` (папка данных приложения в AppData)

### Уровни логирования по умолчанию

| Логгер | Уровень |
|--------|---------|
| `main` | INFO |
| `autodataset` | DEBUG |
| Прочие | DEBUG |

### Консольный уровень

`set_console_level(level)` меняет уровень **консольного** вывода у всех уже созданных
и будущих логгеров (файловые хендлеры всегда пишут всё). Вызывается из `main()`
при передаче `--log-level`.

---

## `src/pcfuncs.py`

**Роль:** низкоуровневые утилиты платформы. Модуль **определяет ОС при импорте** и автоматически
выбирает подходящие реализации функций (менеджер окон и запуск процессов), поэтому
остальной код не содержит проверок платформы.

### Определение ОС (при импорте)

| Переменная | Описание |
|------------|----------|
| `SYSTEM` | `"windows"`, `"macos"` (`darwin`), `"linux"` или `"unknown"` |
| `IS_WINDOWS` / `IS_MACOS` / `IS_LINUX` | Флаги текущей платформы |
| `EXECUTABLE_SUFFIX` | `".exe"` в Windows, `""` в остальных |

### Функции

| Функция | Описание |
|---------|----------|
| `get_executable_name(name)` | `chromedriver` → `chromedriver.exe` (Windows) |
| `make_executable(path)` | `chmod +x` в POSIX, ничего в Windows |
| `prepare_executable(path)` | `make_executable` + валидная ad-hoc подпись в macOS |
| `sign_macos_binary(path)` | `codesign --force --sign -`: без валидной подписи macOS убивает бинарь (`SIGKILL`) |
| `kill_processes_by_marker(marker, exclude_pid)` | Завершить процессы, в командной строке которых есть `marker` |
| `notify(message, title, app_name)` | Системное уведомление: macOS — `osascript`, остальные ОС — `plyer` |
| `is_executable_available(*names)` | Есть ли программа в PATH |
| `get_appdata_root(local)` / `get_appdata_dir(*subdirs, local, create)` | Папка данных приложения |
| `launch_new_instance()` | Запуск нового независимого экземпляра приложения |

**Папка данных приложения** (`get_appdata_dir`):

| ОС | Путь |
|----|------|
| Windows | `%APPDATA%\maclearn\...` (`%LOCALAPPDATA%` при `local=True`) |
| macOS | `~/Library/Application Support/maclearn/...` (`~/Library/Caches` при `local=True`) |
| Linux | `$XDG_CONFIG_HOME/maclearn/...` или `~/.config/maclearn/...` (`$XDG_CACHE_HOME` / `~/.cache` при `local=True`) |

### Менеджер окон (встраивание чужих окон)

Бэкенды выбираются при импорте: `WINDOW_BACKENDS` → `WINDOW_MANAGER`; флаг `CAN_EMBED_PROGRAMS`.

| Бэкенд | ОС | Реализация |
|--------|----|------------|
| `WindowsWindowManager` | Windows | Win32 API (`win32gui`, `win32process`, `win32con`, `psutil`) |
| `LinuxWindowManager` | Linux (X11) | `xdotool` (`search`, `windowreparent`, `windowmove`, `windowsize`, `windowmap`) |
| `NullWindowManager` | macOS и прочие | заглушка, `available = False` |

| Метод | Описание |
|-------|----------|
| `find(process_name, pid)` | Найти окно процесса |
| `windows_by_pid(pid)` | Все видимые окна процесса |
| `restore(window)` | Снять состояние maximized/minimized (иначе `MoveWindow` не действует) |
| `link(window, parent)` | Встроить окно в родительское |
| `set_borderless(window)` | Убрать рамку, заголовок, системные кнопки |
| `move(window, x, y, width, height)` | Переместить и изменить размер |
| `show(window)` | Показать окно |

---

## `src/settings.py`

**Роль:** настройки приложения, общие для всех проектов. Хранятся в `settings.json`
в папке данных приложения.

| Компонент | Описание |
|-----------|----------|
| `DEFAULT_SETTINGS` | Дефолты: язык, Chrome (путь/версия/headless/сессия), SAM3 (device/confidence/мин. площадь/веса/одно обнаружение), `augmentation_preset` |
| `DEFAULT_AUGMENTATION_PRESET` | Вероятности трансформаций Albumentations (crop, hflip, vflip, rotate90, shift_scale_rotate, color, noise, blur) |
| `get_settings_path()` | Путь к `settings.json` |
| `load_settings()` | Загрузка с мержем дефолтов (неизвестные ключи отбрасываются) |
| `save_settings(settings)` | Сохранение в JSON |

Приоритет значений: **CLI-аргумент** → **settings.json** → **дефолт**. Настройки SAM3
и пресет аугментаций подмешиваются в конфигурацию автодатасета, не перезаписывая
настройки проекта (`autodataset.py` мержит `{**load_settings(), **configuration}`).

---

# Модули

## ▶ [project_module](https://github.com/b1t0nese/MacLearn/blob/main/src/project_module/readme.md)

Управление проектами, SQLite-хранилище, экспорт в форматы.

| Файл | Назначение |
|------|------------|
| `project_manager.py` | `Dataset`, `Project`, `SerialDataset`, `get_dataset_statistics` |
| `dataset_manager.py` | `BaseDataset`, `YOLOdataset`, `CSVdataset`, `AVAILABLE_FORMATS` |

## ▶ [autodataset_module](https://github.com/b1t0nese/MacLearn/blob/main/src/autodataset_module/readme.md)

Автоматический сбор данных: парсинг, скачивание, аннотации, аугментация.

| Файл | Назначение |
|------|------------|
| `autodataset.py` | `AutoDataset` — QObject-воркер с сигналами |
| `browser.py` | `ChromeBrowser` — ленивый запуск Chrome, кэш драйвера и сессий |
| `sources/` | `BaseImageSource` + `AVAILABLE_SOURCES` (реестр), `YandexImagesSource` |
| `photoshop.py` | SAM3-аннотация, OpenCV-обработка, аугментации |

## ▶ [interface_module](https://github.com/b1t0nese/MacLearn/blob/main/src/interface_module/readme.md)

PySide6 интерфейс: главное окно, виджеты, лог-окно, настройки, редактор аннотаций, переводы, горячие клавиши, встраивание Chrome.

| Файл | Назначение |
|------|------------|
| `window.py` | `MainWindowUI`, `StatisticsWindow`, виджеты, drag & drop |
| `logs_window.py` | `LogsUI` + `LogsUIHandler` |
| `settings_window.py` | `SettingsWindow` — окно настроек по вкладкам |
| `image_editor.py` | `ImageEditWindow` — ручная правка bounding boxes |
| `shortcuts.py` | `ShortcutBinder` — горячие клавиши окон и меню |
| `translations.py` | Загрузка `translations/*.json`, `tr()`, `retranslate()` |
| `embedded_program_qt.py` | `EmbeddedProgramWidget` (Win32 HWND) |

---

## Поток выполнения

### Запуск

```
main()
  └─ argparse (парсинг CLI)
  └─ set_console_level(--log-level)
  └─ QApplication
  └─ App(**config)
       ├─ load_settings() + set_language() + _apply_chrome_settings()
       ├─ session.start()
       ├─ open_project(path)
       │    └─ Project(path)           # инициализация SQLite
       │    └─ AutoDataset(...)        # ChromeBrowser без запуска Chrome
       │    └─ MainWindowUI.initUI()
       │    └─ init_config_window()    # сигналы UI, меню языка
       │    └─ init_project_conf_in_window()
       │    └─ update_dataset_view_in_window()
       │    └─ retranslate() + ShortcutBinder()
       │    └─ windowUI.show()
  └─ app.start(application)
       ├─ qdarkstyle
       └─ app.exec()                   # Qt event loop
```

### Автодатасет

```
start_autodataset()
  └─ QThread
  └─ AutoDataset.run()
       ├─ ChromeBrowser.start()               # отложенный запуск + кэш chromedriver
       │    └─ ready(pid) → UI встраивает окно браузера
       ├─ Phase 1: download_images_data()     # источник изображений (sources)
       │    └─ download_images(subclass)      # source.collect + save_image (1 поток)
       ├─ Phase 2: create_annotation_data()   # SAM3 bounding boxes
       ├─ Phase 3: create_augmentation_data() # Albumentations
  └─ finished → on_autodataset_finished()
```

---

## Взаимодействие модулей

```
┌────────────┐  Project/AutoDataset (import)  ┌───────────────────┐
│  main.py   │ ──────────────────────────────►│ project_module    │
│   (App)    │                                │ (Project, export) │
└────────────┘                                └───────────────────┘
      │  import                                     ▲
      ▼                                             │
┌────────────┐  signals→slots                 ┌─────┴───────────┐
│  interface │◄──────────────────────────────►│  autodataset    │
│  _module   │  log_field/cur_image/...       │  _module        │
└────────────┘                                └─────────────────┘
      │  import / handler                          │  settings
      ▼                                            ▼
┌─────────────────────┐                ┌──────────────────────┐
│    logger.py        │◄───────────────│  pcfuncs.py /        │
│ (общий для всех)    │                │  settings.py         │
└─────────────────────┘                └──────────────────────┘
```

- **main.py** — оркестратор, не имеет своей бизнес-логики, только связывает.
- **project_module** — не зависит от UI, чистая работа с данными.
- **autodataset_module** — зависит от project_module (Project), settings, pcfuncs и Selenium.
- **interface_module** — зависит от logger (handler для окна логов), translations, shortcuts, автодатасета (сигналы).
- **settings.py** — независимый (только pcfuncs), общие настройки приложения.
- **logger.py** — независимый, используется всеми.
- **pcfuncs.py** — независимый, низкоуровневые утилиты.