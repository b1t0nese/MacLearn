#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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
    --jobs="$JOBS" --lto=yes --standalone --remove-output --report=build/compilation_report.xml \
    --nofollow-import-to=torch.distributed,torch.jit,torch.onnx,torch.quantization,torch.ao \
    --nofollow-import-to=torchvision.datasets,torchvision.io,tkinter,unittest,pytest,scipy.optimize \
    --nofollow-import-to=numpy.testing,numpy.f2py,matplotlib.tests,networkx.algorithms.approximation \
    --macos-create-app-bundle --macos-app-mode=gui --macos-app-name=MacLearn \
    --enable-plugin=pyside6 --include-data-dir=src/interface_module/uis=interface_module/uis \
    --include-data-dir=src/interface_module/translations=interface_module/translations \
    --output-dir=build --output-filename=MacLearn src/main.py --assume-yes-for-downloads

APP="build/MacLearn.app"

find "$APP" -type d -name "test" -path "*torch*" -exec rm -rf {} + 2>/dev/null || true
find "$APP" -type d -name "include" -path "*torch*" -exec rm -rf {} + 2>/dev/null || true

echo
echo "============================================"
echo "Done! Build complete."
echo "Application: build/MacLearn.app"