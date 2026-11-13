#!/usr/bin/env bash
# Build the one-folder Talabiya app into build_exe/dist/Talabiya, then the installer.
# Run from the project root:  bash build_exe/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd -W)"
python -m PyInstaller --paths . --windowed --onedir --name Talabiya -y \
    --icon "$ROOT/talabiya/gui/assets/talabiya.ico" \
    --add-data "$ROOT/talabiya/gui/assets;talabiya/gui/assets" \
    --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy \
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets \
    --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtCharts --exclude-module PySide6.QtPdf \
    --distpath build_exe/dist --workpath build_exe/work --specpath build_exe \
    build_exe/gui_entry.py

ISCC="/c/Program Files (x86)/Inno Setup 6/ISCC.exe"
if [ -x "$ISCC" ]; then
    "$ISCC" installer/talabiya.iss
    ls -la installer/Output
else
    echo "Inno Setup not found: only build_exe/dist/Talabiya was built"
fi
