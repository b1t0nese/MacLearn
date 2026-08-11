@echo off
setlocal enabledelayedexpansion

echo ============================================
echo "Prepare environment for build..."

rmdir /s /q build
python -m venv build_env

echo.
echo "Installing requirements..."

call "build_env/Scripts/pip.exe" install -r requirements.txt
if %errorlevel% neq 0 (
    echo "[ERROR] pip install failed!"
    pause
    exit /b %errorlevel%
)

echo.
echo ============================================
echo "Nuitka compilation..."

call "build_env/Scripts/pip.exe" install nuitka
build_env\Scripts\python.exe -m nuitka --standalone --windows-console-mode=attach ^
    --jobs=12 --follow-imports --include-package=onnxruntime --enable-plugin=pyqt6 ^
    --module-parameter=numba-disable-jit=yes --noinclude-numba-mode=nofollow ^
    --noinclude-custom-mode=MODULE_NAME:error ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --output-dir=build --output-filename=MacLearn.exe src/main.pyw
if %errorlevel% neq 0 (
    echo.
    echo "[ERROR] Build failed with code %errorlevel%!"
    pause
    exit /b %errorlevel%
)

echo.
echo ============================================
echo "UPX compression..."

call upx_build_compress.bat

echo.
echo ============================================
echo "Done! Build complete."
pause