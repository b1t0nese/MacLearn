@echo off
setlocal enabledelayedexpansion

python -m nuitka --standalone --windows-console-mode=disable ^
    --noinclude-numba-mode=allow --enable-plugin=pyqt6 --follow-imports ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --jobs=11 --output-dir=build --remove-output ^
    --output-filename=MacLearn.exe src/main.pyw

cd build/main.dist

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
echo 1. Collecting files...
set "files="
for /f "delims=" %%f in ('dir /s /b *.exe *.dll *.pyd') do (
    set "files=!files! "%%f"")
echo !files!

echo.
echo 2. Compress all files with LZMA...
if defined files (cmd /c upx --best --lzma !files!)

echo.
echo 3. Compress all files with default...
if defined files (cmd /c upx --best !files!)

del upx.exe >nul
echo.
echo Compiling successfuly end!