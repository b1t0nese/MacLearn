@echo off

rmdir /s /q build

echo.
echo Downloading UPX v5.1.0 for compress files...

curl -L -o upx.zip "https://github.com/upx/upx/releases/download/v5.1.0/upx-5.1.0-win64.zip"
echo Extracting upx.exe...
tar -xf upx.zip upx-5.1.0-win64/upx.exe
move upx-5.1.0-win64\upx.exe upx.exe
echo Remove unnecessary files...
rmdir /s /q upx-5.1.0-win64
del upx.zip >nul
echo Done! UPX version:
upx --version

echo.
echo Compiling starting...

pip install nuitka
python -m nuitka --standalone --windows-console-mode=attach ^
    --follow-imports --noinclude-custom-mode=MODULE_NAME:error --jobs=10 ^
    --disable-plugin=pyside6 --enable-plugin=pyqt6 --enable-plugin=upx ^
    --upx-binary="upx.exe" --noinclude-numba-mode=allow --remove-output ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --output-dir=build --output-filename=MacLearn.exe src/main.pyw

del upx.exe >nul
echo.
echo Compiling successfuly end!