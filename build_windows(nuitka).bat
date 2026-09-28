@echo off
setlocal enabledelayedexpansion

echo ============================================
echo Prepare environment for build...

rmdir /s /q build
python -m venv build_env

echo.
echo Installing requirements...

call "build_env/Scripts/pip.exe" install nuitka
call "build_env/Scripts/pip.exe" install -r requirements.txt
if !errorlevel! neq 0 (
    echo "[ERROR] pip install failed!"
    pause
    exit /b !errorlevel!
)

echo.
echo ============================================
echo Nuitka compilation...

build_env\Scripts\python.exe -m nuitka --jobs=12 --standalone ^
    --windows-console-mode=force --include-package=onnxruntime ^
    --enable-plugin=pyqt6 --module-parameter=numba-disable-jit=yes ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --output-dir=build --output-filename=MacLearn.exe src/main.py
if !errorlevel! neq 0 (
    echo.
    echo "[ERROR] Build failed with code !errorlevel!!"
    pause
    exit /b !errorlevel!
)

echo.
echo ============================================
echo UPX compression...

call upx_build_compress.bat

echo.
echo ============================================
echo Done! Build complete.
pause