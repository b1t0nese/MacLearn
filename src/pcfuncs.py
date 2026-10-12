import os
import shutil
import signal
import subprocess
import sys
from platform import system as platf_system

_SYSTEM_NAMES = {"windows": "windows", "darwin": "macos", "linux": "linux"}
SYSTEM = _SYSTEM_NAMES.get(platf_system().lower(), "unknown")
IS_WINDOWS = SYSTEM == "windows"
IS_MACOS = SYSTEM == "macos"
IS_LINUX = SYSTEM == "linux"
EXECUTABLE_SUFFIX = ".exe" if IS_WINDOWS else ""



def get_executable_name(name: str) -> str:
    if not EXECUTABLE_SUFFIX or name.lower().endswith(EXECUTABLE_SUFFIX):
        return name
    return name + EXECUTABLE_SUFFIX


def make_executable(path: str) -> bool:
    if IS_WINDOWS or not os.path.isfile(path):
        return False
    try:
        os.chmod(path, os.stat(path).st_mode | 0o111)
        return True
    except OSError:
        return False


def is_executable_available(*names: str) -> bool:
    return any(shutil.which(name) for name in names)


def sign_macos_binary(path: str) -> bool:
    if not IS_MACOS or not os.path.isfile(path):
        return False
    try:
        subprocess.run(["/usr/bin/xattr", "-c", path], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)
        result = subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=120)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def prepare_executable(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    make_executable(path)
    if IS_MACOS:
        return sign_macos_binary(path)
    return True


def kill_processes_by_marker(marker: str, exclude_pid: int = None) -> int:
    if not marker:
        return 0
    exclude_pid = exclude_pid or os.getpid()
    if IS_WINDOWS:
        script = ("$m = '%s'; Get-CimInstance Win32_Process | "
                  "Where-Object { $_.CommandLine -like ('*' + $m + '*') } | "
                  "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Output $_.ProcessId }"
                  % marker)
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                    capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return 0
        return len([line for line in result.stdout.split() if line.isdigit()])
    try:
        result = subprocess.run(["ps", "-eo", "pid=,command="],
                                capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return 0
    killed = 0
    for line in result.stdout.splitlines():
        pid_text, _, command = line.strip().partition(" ")
        if marker not in command or not pid_text.isdigit():
            continue
        pid = int(pid_text)
        if pid == exclude_pid:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            killed += 1
        except OSError:
            continue
    return killed


def _notify_via_osascript(message: str, title: str) -> bool:
    script = 'display notification "%s" with title "%s"' % (
        message.replace("\\", "\\\\").replace('"', '\\"'),
        title.replace("\\", "\\\\").replace('"', '\\"'))
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", script],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _log_notify_error(error: Exception):
    try:
        from logger import get_logger
        get_logger("pcfuncs").warning("⚠ Desktop notifications are not available: %s", error)
    except Exception:
        pass


def notify(message: str, title: str = "MacLearn", app_name: str = "MacLearn") -> bool:
    if IS_MACOS and _notify_via_osascript(message, title):
        return True
    try:
        from plyer import notification as plyer_notification
        plyer_notification.notify(message=message, title=title, app_name=app_name)
        return True
    except Exception as error:
        _log_notify_error(error)
    return False



def get_appdata_root(local: bool = False) -> str:
    if IS_WINDOWS:
        path = os.environ.get("LOCALAPPDATA" if local else "APPDATA")
        if path and os.path.isdir(path):
            return path
        fallback = os.path.join(
            os.path.expanduser("~"), "AppData", "Local" if local else "Roaming")
    elif IS_MACOS:
        fallback = os.path.join(os.path.expanduser("~"), "Library",
                                "Caches" if local else "Application Support")
    else:
        path = os.environ.get("XDG_CACHE_HOME" if local else "XDG_CONFIG_HOME")
        if path and os.path.isdir(path):
            return path
        fallback = os.path.join(os.path.expanduser("~"), ".cache" if local else ".config")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def get_appdata_dir(*subdirs: str, local: bool = False, create: bool = True) -> str:
    path = os.path.join(get_appdata_root(local), "maclearn", *subdirs)
    if create:
        os.makedirs(path, exist_ok=True)
    return path



def launch_new_instance():
    if getattr(sys, 'frozen', False):
        executable, args = sys.argv[0], sys.argv[1:]
    else:
        executable, args = sys.executable, sys.argv
    popen_args = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                  "stderr": subprocess.DEVNULL, "close_fds": True}
    if IS_WINDOWS:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        popen_args["startupinfo"] = startupinfo
        popen_args["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        popen_args["start_new_session"] = True
    subprocess.Popen([executable] + args, **popen_args)

class BaseWindowManager:
    name = "base"
    available = False


    def find(self, process_name: str = None, pid: int = None):
        return None


    def windows_by_pid(self, pid: int) -> list:
        return []


    def restore(self, window) -> bool:
        return False


    def link(self, window, parent) -> bool:
        return False


    def set_borderless(self, window) -> bool:
        return False


    def move(self, window, x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> bool:
        return False


    def show(self, window) -> bool:
        return False



class WindowsWindowManager(BaseWindowManager):
    name = "windows"

    def __init__(self):
        try:
            import win32con
            import win32gui
            import win32process
            import psutil
            self._win32con, self._win32gui = win32con, win32gui
            self._win32process, self._psutil = win32process, psutil
            self.available = True
            self.error = ""
        except ImportError as e:
            self._win32gui = None
            self.available = False
            self.error = f"Для управления окнами установите pywin32: {e}"


    def windows_by_pid(self, pid: int) -> list:
        windows = []
        def enum_windows(window, _):
            if self._win32gui.IsWindowVisible(window):
                _, window_pid = self._win32process.GetWindowThreadProcessId(window)
                if window_pid == pid:
                    windows.append(window)
            return True
        self._win32gui.EnumWindows(enum_windows, None)
        return windows


    def windows_by_process_name(self, process_name: str) -> list:
        windows = []
        def enum_windows(window, results):
            if self._win32gui.IsWindowVisible(window):
                _, pid = self._win32process.GetWindowThreadProcessId(window)
                try:
                    if self._psutil.Process(pid).name().lower() == process_name:
                        results.append(window)
                except Exception:
                    if "Chrome_WidgetWin" in self._win32gui.GetClassName(window):
                        results.append(window)
            return True
        self._win32gui.EnumWindows(enum_windows, windows)
        return windows


    def find(self, process_name: str = None, pid: int = None):
        if pid:
            windows = self.windows_by_pid(pid)
        else:
            windows = self.windows_by_process_name((process_name or "").lower())
        if not windows:
            return None
        for window in windows:
            if self._win32gui.GetWindowText(window):
                return window
        return windows[-1]


    def restore(self, window) -> bool:
        show_command = self._win32gui.GetWindowPlacement(window)[1]
        if show_command in (self._win32con.SW_SHOWMAXIMIZED, self._win32con.SW_SHOWMINIMIZED):
            self._win32gui.ShowWindow(window, self._win32con.SW_RESTORE)
            return True
        return False


    def link(self, window, parent) -> bool:
        self.restore(window)
        self.set_borderless(window)
        self._win32gui.SetParent(window, int(parent))
        return True


    def set_borderless(self, window) -> bool:
        style = self._win32gui.GetWindowLong(window, self._win32con.GWL_STYLE)
        style &= ~(self._win32con.WS_CAPTION | self._win32con.WS_THICKFRAME |
                   self._win32con.WS_MINIMIZEBOX | self._win32con.WS_MAXIMIZEBOX |
                   self._win32con.WS_SYSMENU | self._win32con.WS_BORDER |
                   self._win32con.WS_DLGFRAME)
        self._win32gui.SetWindowLong(window, self._win32con.GWL_STYLE, style)
        return True


    def move(self, window, x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> bool:
        self.restore(window)
        self._win32gui.MoveWindow(window, x, y, width, height, True)
        return True


    def show(self, window) -> bool:
        self._win32gui.ShowWindow(window, self._win32con.SW_SHOW)
        self._win32gui.UpdateWindow(window)
        return True



class LinuxWindowManager(BaseWindowManager):
    name = "linux"

    def __init__(self):
        self.available = is_executable_available("xdotool") and bool(os.environ.get("DISPLAY"))
        self.error = "" if self.available else "Установите xdotool (X11) для управления окнами"


    def restore(self, window) -> bool:
        result = subprocess.run(["xdotool", "windowstate", "--remove", "MAXIMIZED_VERT",
                                 "--remove", "MAXIMIZED_HORZ", str(window)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0


    def find(self, process_name: str = None, pid: int = None):
        cmd = ["xdotool", "search", "--onlyvisible"]
        if pid:
            cmd += ["--pid", str(pid)]
        elif process_name:
            cmd += ["--name", process_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        windows = [int(window) for window in result.stdout.split()]
        return windows[-1] if windows else None


    def link(self, window, parent) -> bool:
        result = subprocess.run(["xdotool", "windowreparent", str(window), str(int(parent))],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0


    def move(self, window, x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> bool:
        subprocess.run(["xdotool", "windowmove", "--sync", str(window), str(x), str(y)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["xdotool", "windowsize", "--sync", str(window), str(width), str(height)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0


    def show(self, window) -> bool:
        result = subprocess.run(["xdotool", "windowmap", str(window)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0



class NullWindowManager(BaseWindowManager):
    name = "none"

    def __init__(self, reason: str = None):
        self.error = reason or f"Встраивание окон не поддерживается на {SYSTEM}"



WINDOW_BACKENDS = {"windows": WindowsWindowManager, "linux": LinuxWindowManager}

WINDOW_MANAGER = WINDOW_BACKENDS.get(SYSTEM, NullWindowManager)()
CAN_EMBED_PROGRAMS = WINDOW_MANAGER.available