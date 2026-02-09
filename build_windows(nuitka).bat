python -m nuitka --standalone --windows-console-mode=disable ^
    --noinclude-numba-mode=allow --enable-plugin=pyqt6 --follow-imports ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --jobs=11 --output-dir=build --remove-output ^
    --output-filename=MacLearn.exe src/main.pyw