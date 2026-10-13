#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "============================================"
echo "Prepare environment for build..."

rm -rf build
python3 -m venv build_env

echo
echo "Installing requirements..."

build_env/bin/python -m pip install --upgrade pip
build_env/bin/python -m pip install nuitka
build_env/bin/python -m pip install -r src/requirements.txt

echo
echo "============================================"
echo "Nuitka compilation..."

JOBS="$(sysctl -n hw.logicalcpu)"
build_env/bin/python -m nuitka \
    --jobs="$JOBS" \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-mode=gui \
    --enable-plugin=pyside6 \
    --include-data-dir=src/interface_module/uis=interface_module/uis \
    --output-dir=build \
    --output-filename=MacLearn \
    src/main.py

echo
echo "============================================"
echo "Done! Build complete."
echo "Application: build/MacLearn.app"
echo
echo "Largest build files:"
find build/MacLearn.app -type f -print0 | xargs -0 stat -f '%z %N' | sort -nr | head -20
