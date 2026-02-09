python -m nuitka --standalone --windows-console-mode=disable ^
    --noinclude-numba-mode=allow ^
    --output-dir=build ^
    --jobs=11 ^
    --enable-plugin=pyqt6 ^
    --include-data-dir=src/interface_module/uis=interface_module/uis ^
    --remove-output ^
    --output-filename=MacLearn.exe ^

    --follow-imports ^
    --follow-stdlib ^
    --recurse-none ^
    --assume-yes-for-downloads ^
    --user-plugin=remove_unused_imports.py ^

    --lto=yes ^
    --experimental=use_pefile ^
    --experimental=use_pefile_recurse ^

    --python-flag=-O ^
    --python-flag=-B ^

    src/main.pyw