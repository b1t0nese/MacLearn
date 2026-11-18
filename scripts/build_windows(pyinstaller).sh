#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python}"
VENV_DIR="build_env"
PYTHON_BIN="$VENV_DIR/Scripts/python.exe"

echo "============================================"
echo "Prepare environment for build..."

rm -rf build dist MacLearn.exe MacLearn.spec "$VENV_DIR"
"$PYTHON" -m venv "$VENV_DIR"

echo
echo "Installing requirements..."

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install pyinstaller
"$PYTHON_BIN" -m pip install -r src/requirements.txt

echo
echo "============================================"
echo "PyInstaller build (same command as CI workflow)..."

# Консоль оставлена как в nuitka-скрипте (логи видны); add-data кладёт uis и
# translations в корень бандла — так их ищет frozen-код (sys._MEIPASS/uis,
# sys._MEIPASS/translations). collect-data нужен qdarkstyle (.qss) и ultralytics
# (cfg .yaml) — их package data PyInstaller по импортам не видит.
"$PYTHON_BIN" -m PyInstaller \
    --noconfirm --clean --onefile --console --name MacLearn \
    --add-data "src/interface_module/uis;uis" \
    --add-data "src/interface_module/translations;translations" \
    --collect-data qdarkstyle \
    --collect-data ultralytics \
    src/main.py

APP="dist/MacLearn.exe"

echo
echo "Largest build files:"
find dist -type f -print0 | xargs -0 stat -c '%s %n' | sort -nr | head -20

echo
echo "============================================"
echo "Done! Build complete."
echo "Application: $APP"
