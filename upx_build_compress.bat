@echo off
setlocal enabledelayedexpansion

cd build

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
echo Compress successfuly end!