#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "============================================"
echo "Prepare environment for build..."

rm -rf build dist MacLearn.dmg MacLearn.spec
python3 -m venv build_env

echo
echo "Installing requirements..."

build_env/bin/python -m pip install --upgrade pip
build_env/bin/python -m pip install pyinstaller
build_env/bin/python -m pip install -r src/requirements.txt

echo
echo "============================================"
echo "PyInstaller build (same command as CI workflow)..."

# onedir (не onefile): torch на импорте поднимает multiprocessing-детей, и в macOS
# onefile они падают на dlopen Qt-фреймворков; add-data кладёт uis и translations
# в корень бандла — так их ищет frozen-код (sys._MEIPASS/uis, sys._MEIPASS/translations).
build_env/bin/python -m PyInstaller \
    --noconfirm --clean --onedir --windowed --name MacLearn \
    --add-data "src/interface_module/uis:uis" \
    --add-data "src/interface_module/translations:translations" \
    --collect-data qdarkstyle \
    --collect-data ultralytics \
    src/main.py

APP="dist/MacLearn.app"

echo
echo "Packing dmg..."
hdiutil create -volname "MacLearn" -srcfolder "$APP" -ov -format UDZO MacLearn.dmg

echo
echo "============================================"
echo "Done! Build complete."
echo "Application: $APP"
echo "Image: MacLearn.dmg"
