#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
PYTHON="${PET_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"

if [ ! -x "$PYTHON" ]; then
    echo "找不到桌宠使用的 Python：$PYTHON" >&2
    exit 1
fi
if ! "$PYTHON" -c "import PyQt6.QtWidgets, AppKit" 2>/dev/null; then
    "$PYTHON" -m pip install -r requirements.txt
fi
exec "$PYTHON" main.py "$@"
