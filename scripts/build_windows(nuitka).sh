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

rm -rf build "$VENV_DIR"
"$PYTHON" -m venv "$VENV_DIR"

echo
echo "Installing requirements..."

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install nuitka
"$PYTHON_BIN" -m pip install -r src/requirements.txt

echo
echo "============================================"
echo "Nuitka compilation..."

JOBS="${JOBS:-12}"
"$PYTHON_BIN" -m nuitka \
    --jobs="$JOBS" --lto=yes --standalone --remove-output \
    --report=build/compilation_report.xml \
    --nofollow-import-to=torch.distributed,torch.jit,torch.onnx,torch.quantization,torch.ao \
    --nofollow-import-to=torchvision.datasets,torchvision.io,tkinter,unittest,pytest,scipy.optimize \
    --nofollow-import-to=numpy.testing,numpy.f2py,matplotlib.tests,networkx.algorithms.approximation \
    --windows-console-mode=force \
    --enable-plugin=pyside6 --module-parameter=numba-disable-jit=yes \
    --include-data-dir=src/interface_module/uis=interface_module/uis \
    --include-data-dir=src/interface_module/translations=interface_module/translations \
    --output-dir=build --output-filename=MacLearn.exe src/main.py \
    --assume-yes-for-downloads

APP="build/MacLearn.dist"

find "$APP" -type d -name "test" -path "*torch*" -exec rm -rf {} + 2>/dev/null || true
find "$APP" -type d -name "include" -path "*torch*" -exec rm -rf {} + 2>/dev/null || true

if command -v upx >/dev/null 2>&1; then
    echo
    echo "Compressing executable files with UPX..."
    find "$APP" -type f \( -name "*.exe" -o -name "*.dll" -o -name "*.pyd" \) \
        -exec upx --best --lzma --force {} +
else
    echo
    echo "UPX not found; skipping compression."
fi

echo
echo "Largest build files:"
find "$APP" -type f -print0 | xargs -0 stat -c '%s %n' | sort -nr | head -20

echo
echo "============================================"
echo "Done! Build complete."
echo "Application: $APP/MacLearn.exe"
