#!/bin/bash
# 다고냥 Desktop Pet — 一键启动
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
PYTHON="${PET_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"

if [ ! -x "$PYTHON" ]; then
    echo "找不到桌宠使用的 Python：$PYTHON" >&2
    exit 1
fi

# 检查并安装运行依赖
if ! "$PYTHON" -c "import PyQt6.QtWidgets, PIL, AppKit" 2>/dev/null; then
    echo "正在安装桌宠运行依赖..."
    "$PYTHON" -m pip install -r requirements.txt
fi

echo "启动 다고냥..."
exec "$PYTHON" main.py "$@"
