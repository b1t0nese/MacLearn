import sys
import os



def get_app_version() -> str:
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    try:
        with open(os.path.join(base_path, "version.txt"), "r", encoding="utf-8") as version_file:
            version = version_file.read().strip()
    except OSError:
        return "dev"
    return version or "dev"
