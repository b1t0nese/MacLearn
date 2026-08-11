import logging
import logging.handlers
import functools
import inspect
import traceback
import time
import sys
import os


LOG_DIR = None


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[38;5;245m",
        "INFO": "\033[38;5;39m",
        "OK": "\033[38;5;42m",
        "WARNING": "\033[38;5;214m",
        "ERROR": "\033[38;5;196m",
        "CRITICAL": "\033[38;5;196;1m",
    }
    ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "OK": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "💥",
    }
    RESET = "\033[0m"
    CONSOLE_FMT = "{icon} \033[1m{level:<8}\033[0m | {color}{message}{reset}"

    def format(self, record):
        level_name = record.levelname
        if level_name == "INFO" and record.msg.startswith("✓"):
            level_name = "OK"
        elif level_name == "INFO" and record.msg.startswith("✗"):
            level_name = "ERROR"

        icon = self.ICONS.get(level_name, "")
        color = self.COLORS.get(level_name, self.RESET)

        formatted = self.CONSOLE_FMT.format(
            icon=icon, level=level_name, color=color,
            message=super().format(record), reset=self.RESET)

        if record.exc_info and record.exc_info[0]:
            tb = "".join(traceback.format_exception(*record.exc_info))
            formatted += f"\n{color}{tb}{self.RESET}"

        return formatted


class FileFormatter(logging.Formatter):
    FILE_FMT = "[{asctime}] [{levelname}] [{name}] {message}"
    DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(self.FILE_FMT, datefmt=self.DATE_FMT, style="{")


def _get_log_dir() -> str:
    if LOG_DIR:
        return LOG_DIR
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logger(name: str = None, level: int = logging.DEBUG,
                 log_file: str = None, console: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    log_dir = _get_log_dir()
    if not log_file:
        log_file = f"{name.replace('.', '_') if name else 'app'}.log"
    file_path = os.path.join(log_dir, log_file)

    file_handler = logging.handlers.RotatingFileHandler(
        file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FileFormatter())
    logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredFormatter())
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    if name and ("main" in name.lower() or "__main__" in name):
        level = logging.INFO
    elif name and ("autodataset" in name.lower()):
        level = logging.DEBUG
    else:
        level = logging.DEBUG
    return setup_logger(name, level=level)


def log_call(logger: logging.Logger = None, level: int = logging.DEBUG):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            func_name = func.__qualname__

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            args_repr = []
            for param_name, param_value in bound.arguments.items():
                if param_name == "self":
                    continue
                if isinstance(param_value, str) and len(param_value) > 80:
                    args_repr.append(f"{param_name}={param_value[:77]}...")
                elif isinstance(param_value, (bytes, bytearray)):
                    args_repr.append(f"{param_name}=<{len(param_value)} bytes>")
                else:
                    args_repr.append(f"{param_name}={param_value!r}")

            logger.log(level, "▸ %s(%s)", func_name, ", ".join(args_repr))

            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                if elapsed >= 1.0:
                    logger.log(level, "◂ %s = %s [%.3fs]", func_name, result is not None, elapsed)
                else:
                    logger.log(level, "◂ %s = %s [%.0fms]", func_name, result is not None, elapsed * 1000)
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error("✗ %s raised %s [%.3fs]", func_name, e, elapsed, exc_info=True)
                raise

        return wrapper
    return decorator


def log_timing(logger: logging.Logger = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                if elapsed >= 1.0:
                    logger.info("⏱ %s took %.3fs", func.__qualname__, elapsed)
                else:
                    logger.debug("⏱ %s took %.0fms", func.__qualname__, elapsed * 1000)
        return wrapper
    return decorator


class LogContext:
    def __init__(self, name: str, logger: logging.Logger = None, level: int = logging.INFO):
        self.name = name
        self.logger = logger
        self.level = level
        self.start = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        if self.logger:
            self.logger.log(self.level, "▶ %s", self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start
        if self.logger:
            if exc_type:
                self.logger.error(
                    "✗ %s failed after %.3fs: %s", self.name, elapsed,
                    exc_val, exc_info=(exc_type, exc_val, exc_tb))
            else:
                if elapsed >= 1.0:
                    self.logger.log(self.level, "◀ %s completed in %.3fs", self.name, elapsed)
                else:
                    self.logger.log(self.level, "◀ %s completed in %.0fms", self.name, elapsed * 1000)
        return False


class SessionLogger:
    def __init__(self, name: str = "session"):
        self.name = name
        self.start_time = 0.0
        self.logger = get_logger(name)
        self.events: list[dict] = []

    def start(self, extra: dict = None):
        self.start_time = time.perf_counter()
        args = sys.argv if hasattr(sys, "argv") else []
        info = {
            "event": "session_start",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "python": sys.version,
            "args": args,
            "platform": sys.platform,
            **(extra or {}),
        }
        self.events.append(info)
        self.logger.info("=" * 60)
        self.logger.info(
            "🚀 SESSION START | Python %s | %s | args: %s",
            sys.version.split()[0], sys.platform, args)
        if extra:
            for k, v in extra.items():
                self.logger.info("   %s: %s", k, v)
        self.logger.info("=" * 60)

    def end(self, exit_code: int = 0):
        elapsed = time.perf_counter() - self.start_time
        self.logger.info("=" * 60)
        self.logger.info(
            "🏁 SESSION END | code=%d | duration=%.2fs", exit_code, elapsed)
        self.logger.info("=" * 60)
        self.events.append({
            "event": "session_end",
            "exit_code": exit_code,
            "duration_s": round(elapsed, 2),
        })

    def event(self, event_type: str, **data):
        record = {"event": event_type, **data}
        self.events.append(record)
        self.logger.info("📌 %s: %s", event_type, data)

    def error(self, message: str, **extra):
        self.logger.error("💥 %s", message, extra=extra)
        self.events.append({"event": "error", "message": message, **extra})

    def get_summary(self) -> str:
        return "\n".join([
            f"Session: {self.name}",
            f"Total events: {len(self.events)}",
            f"Errors: {len([e for e in self.events if e.get("event") == "error"])}",
        ])


def install_exception_hook(logger: logging.Logger = None):
    if logger is None:
        logger = get_logger("crash")

    def exception_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "💀 UNHANDLED EXCEPTION: %s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = exception_hook
    logger.info("🔌 Global exception hook installed")