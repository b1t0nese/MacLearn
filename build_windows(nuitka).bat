@echo off

echo.
echo Prepare environment for build...

python -m venv build_env
rmdir /s /q build_env/src
robocopy "src" "build_env/src" /E /NFL /NDL /NJH /NJS

echo.
echo Installing requirements...

call "build_env/Scripts/pip.exe" install -r requirements.txt

cd build_env

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

call "Scripts/pip.exe" install nuitka
call "Scripts/python.exe" -m nuitka --standalone --windows-console-mode=attach --jobs=10 ^
    --follow-imports --noinclude-custom-mode=MODULE_NAME:error --enable-plugin=pyqt6 ^
    --module-parameter=numba-disable-jit=yes --noinclude-numba-mode=allow ^
    --enable-plugin=upx --upx-binary="upx.exe" --onefile-no-compression ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --output-dir=build --output-filename=MacLearn.exe src/main.pyw

echo.
echo Compiling successfuly end!