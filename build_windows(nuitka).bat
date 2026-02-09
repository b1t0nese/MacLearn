python -m nuitka --standalone --windows-console-mode=disable ^
    --noinclude-numba-mode=allow --output-dir=build --jobs=10 ^
    --enable-plugin=pyqt6 ^
    --include-data-dir=interface_module/uis=interface_module/uis ^
    --remove-output --output-filename=MacLearn.exe main.pyw