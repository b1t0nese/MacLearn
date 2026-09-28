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
- [Модули](#модули)
  - [`project_module`](https://github.com/b1t0nese/MacLearn/blob/main/src/project_module/readme.md) — проекты, SQLite, экспорт
  - [`autodataset_module`](https://github.com/b1t0nese/MacLearn/blob/main/src/autodataset_module/readme.md) — сбор данных, аннотации, аугментация
  - [`interface_module`](https://github.com/b1t0nese/MacLearn/blob/main/src/interface_module/readme.md) — PyQt6 интерфейс
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
          │   (PyQt6 UI)   │ │  (сбор/аннотации)  │
          └───────┬────────┘ └──────────┬─────────┘
                  │                     │
          ┌───────▼──────────┐  ┌───────▼───────────┐
          │ project_module   │  │  logger.py        │
          │ (SQLite/проекты) │  │  (логирование)    │
          └──────────────────┘  └───────────────────┘
```

`main.py` — оркестратор: связывает UI, проекта и автодатасет.
`logger.py` — центральная система логирования, используется всеми модулями.
`pcfuncs.py` — низкоуровневые утилиты (буфер обмена, процессы).

---

## Структура проекта

```
maclearn/
├── requirements.txt                    # Зависимости проекта
├── build_windows(nuitka).bat           # Сборка Windows (Nuitka + UPX)
├── upx_build_compress.bat              # UPX-сжатие
└── src/
    ├── main.py                         # Точка входа, класс App
    ├── logger.py                       # Система логирования
    ├── pcfuncs.py                      # Утилиты
    ├── start.bat                       # Быстрый запуск
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
    └── interface_module/
        ├── window.py                   # MainWindowUI, виджеты
        ├── logs_window.py              # Окно логов
        ├── embedded_program_qt.py      # Встраивание Chrome
        ├── __init__.py
        └── uis/                        # Qt Designer .ui
            ├── mainwindow.ui
            ├── logswindow.ui
            ├── statisticswindow.ui
            ├── tabs/
            │   ├── project_tab.ui
            │   ├── dataset_tab.ui
            │   └── autodataset_tab.ui
            └── widgets/
                ├── class_field.ui
                ├── object_card.ui
                ├── overview_class.ui
                └── information.ui
```

---

# Корневые модули

## `src/main.py`

**Роль:** точка входа и главный контроллер приложения.

### Импорты

| Источник | Что берёт |
|----------|-----------|
| `PyQt6.QtWidgets` | QApplication, QFileDialog, QMessageBox |
| `PyQt6.QtGui` | QDesktopServices |
| `PyQt6.QtCore` | QThread, QUrl |
| `qdarkstyle` | Тёмная тема |
| `project_module.project_manager` | `Project`, `get_dataset_statistics` |
| `autodataset_module.autodataset` | `AutoDataset` |
| `project_module.dataset_manager` | `AVAILABLE_FORMATS` |
| `interface_module.window` | `MainWindowUI`, `StatisticsWindow` |
| `interface_module.logs_window` | `LogsUI` |
| `autodataset_module.photoshop` | `visualize_bbox`, `open_image` |
| `pcfuncs` | Утилиты (clipboard, launch_new_instance) |
| `logger` | `get_logger`, `log_call`, `LogContext`, `SessionLogger`, `install_exception_hook` |

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
| `__init__(self, **config)` | Инициализация, старт сессии, открытие проекта |
| `start(app)` | Запуск Qt event loop с тёмной темой |
| `close_application(event, exit_code)` | Корректное закрытие (воркер → окна → user later GUI) |
| `new_window(project_path)` | Создание окна для проекта (3 этапа: Project, AutoDataset, UI) |
| `init_config_window()` | Подключение сигналов UI-элементов |
| `init_project_conf_in_window()` | Загрузка конфигурации проекта в UI |
| `update_dataset_view_in_window()` | Синхронизация UI датасета с БД |
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
| `project_path` | str (опц.) | Путь к проекту |
| `--chrome-version VERSION` | int | Версия Chrome |
| `--chromedriver-path PATH` | str | Путь к chromedriver |
| `-chrome-headless` | flag | Chrome без окна |

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

---

## `src/pcfuncs.py`

**Роль:** низкоуровневые утилиты платформы. Модуль **определяет ОС при импорте** и автоматически
выбирает подходящие реализации функций (буфер обмена, менеджер окон, запуск процессов), поэтому
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
| `pil_image_to_array(image)` | `PIL.Image` → BGR `np.ndarray` |
| `save_temp_image(image)` / `remove_temp_file(path)` | Временный файл изображения (для внешних утилит) |

**Папка данных приложения** (`get_appdata_dir`):

| ОС | Путь |
|----|------|
| Windows | `%APPDATA%\maclearn\...` (`%LOCALAPPDATA%` при `local=True`) |
| macOS | `~/Library/Application Support/maclearn/...` (`~/Library/Caches` при `local=True`) |
| Linux | `$XDG_CONFIG_HOME/maclearn/...` или `~/.config/maclearn/...` (`$XDG_CACHE_HOME` / `~/.cache` при `local=True`) |

### Буфер обмена

Бэкенды выбираются при импорте модуля: `CLIPBOARD_BACKENDS` → `CLIPBOARD_BACKEND`.

| Бэкенд | ОС | Реализация |
|--------|----|------------|
| `WindowsClipboard` | Windows | `win32clipboard` (DIB) + PIL для чтения |
| `MacOSClipboard` | macOS | `osascript`/`pbcopy` + PIL для чтения |
| `LinuxClipboard` | Linux | `wl-copy`/`wl-paste` (Wayland) или `xclip` (X11) |
| `BaseClipboard` | прочие | заглушка (`available = False`) |

### Класс `ClipboardManager`

Фасад над бэкендом: `available`, `copy_image_to_clipboard(image)` (str путь или `np.ndarray`),
`copy_text_to_clipboard(text)`, `get_image_from_clipboard()` (BGR `np.ndarray` или `None`).

### Класс `ClipboardImageWatcher`

Мониторинг буфера обмена на новые изображения (через `ClipboardManager`).

| Метод | Описание |
|-------|----------|
| `__init__(callback, check_interval, clipboard_manager)` | Колбэк при новом изображении |
| `get_image_hash(image)` | MD5 миниатюры для сравнения |
| `check_clipboard()` | Одиночная проверка буфера |
| `start()` | Запуск фонового потока мониторинга |
| `stop()` | Остановка потока |

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
| `photoshop.py` | OpenCV-обработка, rembg, аугментации |

## ▶ [interface_module](https://github.com/b1t0nese/MacLearn/blob/main/src/interface_module/readme.md)

PyQt6 интерфейс: главное окно, виджеты, лог-окно, встраивание Chrome.

| Файл | Назначение |
|------|------------|
| `window.py` | `MainWindowUI`, `StatisticsWindow`, виджеты |
| `logs_window.py` | `LogsUI` + `LogsUIHandler` |
| `embedded_program_qt.py` | `EmbeddedProgramWidget` (Win32 HWND) |

---

## Поток выполнения

### Запуск

```
main()
  └─ argparse (парсинг CLI)
  └─ QApplication
  └─ App(**config)
       ├─ session.start()
       ├─ open_project(path)
       │    └─ Project(path)           # инициализация SQLite
       │    └─ AutoDataset(...)        # ChromeBrowser без запуска Chrome
       │    └─ MainWindowUI.initUI()
       │    └─ init_config_window()    # сигналы UI
       │    └─ init_project_conf_in_window()
       │    └─ update_dataset_view_in_window()
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
       │    └─ download_images(subclass)      # source.collect + downloader (2 потока)
       ├─ Phase 2: create_annotation_data()   # rembg + OpenCV контуры
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
      │  import / handler                          │  import
      ▼                                            ▼
┌─────────────────────┐                ┌──────────────────────┐
│    logger.py        │◄───────────────│      pcfuncs.py      │
│ (общий для всех)    │                │  (буфер/процессы)    │
└─────────────────────┘                └──────────────────────┘
```

- **main.py** — оркестратор, не имеет своей бизнес-логики, только связывает.
- **project_module** — не зависит от UI, чистая работа с данными.
- **autodataset_module** — зависит от project_module (Project) и pcfuncs (clipboard).
- **interface_module** — зависит от logger (handler для окна логов), автодатасета (сигналы).
- **logger.py** — независимый, используется всеми.
- **pcfuncs.py** — независимый, низкоуровневые утилиты.