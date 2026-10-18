#!/bin/bash
# Build both macOS pets, each in its own drag-to-install DMG.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.packaging-venv/bin/python"
# Sign app bundles on the Mac's native filesystem. Building them on an
# external exFAT disk creates AppleDouble files that break codesign.
BUILD_DIR="${HOME}/Library/Caches/TXTDesktopPets/mac-build"
RELEASE_DIR="$ROOT/release"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

if [ "$(uname -s)" != "Darwin" ]; then
    echo "请在 macOS 上构建安装包。" >&2
    exit 1
fi
if [ ! -x "$PYTHON" ] || ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "缺少构建环境：请先创建 .packaging-venv 并安装 requirements.txt 和 pyinstaller。" >&2
    exit 1
fi

mkdir -p "$BUILD_DIR/dist" "$BUILD_DIR/work" "$BUILD_DIR/spec" "$RELEASE_DIR"
mkdir -p "$STAGE/songnyang/assets" "$STAGE/soobin/assets"

# Only include files read by the running pets. Source art, backups, and local
# save files are kept out of the downloaded application.
for file in idle.png idle_standing.png idle_workout.png weak_sprite.png music.png envelope_icon.png heart_letter_paper.jpeg; do
    cp "$ROOT/assets/$file" "$STAGE/songnyang/assets/"
done
rsync -a --exclude='._*' --exclude='.DS_Store' "$ROOT/assets/frames" "$STAGE/songnyang/assets/"
rsync -a --exclude='._*' --exclude='.DS_Store' "$ROOT/assets/edge_peek" "$STAGE/songnyang/assets/"

for file in idle.png game_prompt.png; do
    cp "$ROOT/soobin_pet/assets/$file" "$STAGE/soobin/assets/"
done
for dir in frames edge_peek poses letter; do
    rsync -a --exclude='._*' --exclude='.DS_Store' "$ROOT/soobin_pet/assets/$dir" "$STAGE/soobin/assets/"
done

echo "构建松喵喵.app ..."
(
    cd "$ROOT"
    "$PYTHON" -m PyInstaller --noconfirm --clean --log-level WARN \
        --onedir --windowed --name '松喵喵' \
        --osx-bundle-identifier 'com.txtpet.songnyang' \
        --icon "$ROOT/assets/idle_standing.png" \
        --add-data "$STAGE/songnyang/assets:assets" \
        --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/work/songnyang" \
        --specpath "$BUILD_DIR/spec" main.py
)

echo "构建崔勇萌.app ..."
(
    cd "$ROOT/soobin_pet"
    "$PYTHON" -m PyInstaller --noconfirm --clean --log-level WARN \
        --onedir --windowed --name '崔勇萌' \
        --osx-bundle-identifier 'com.txtpet.soobin' \
        --icon "$ROOT/soobin_pet/assets/idle.png" \
        --add-data "$STAGE/soobin/assets:assets" \
        --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/work/soobin" \
        --specpath "$BUILD_DIR/spec" main.py
)

create_dmg() {
    local app_name="$1"
    local file_name="$2"
    local save_folder="$3"
    local dmg_root="$STAGE/dmg-$save_folder"
    local dmg_path="$RELEASE_DIR/$file_name"

    mkdir -p "$dmg_root"
    ditto "$BUILD_DIR/dist/$app_name.app" "$dmg_root/$app_name.app"
    ln -s /Applications "$dmg_root/应用程序 Applications"
    cat > "$dmg_root/安装说明.txt" <<EOF
${app_name}（Apple 芯片 Mac 版）

将“${app_name}.app”拖入“应用程序 Applications”，再从“应用程序”打开。
在桌宠上点击鼠标右键，选择“退出”。

体力等数据保存在用户目录的
~/Library/Application Support/TXT Desktop Pets/${save_folder}/ 中，更新应用不会覆盖这些数据。

此安装包尚未使用 Apple Developer ID 签名或公证，不适合直接作为公开发布版。
EOF

    hdiutil create -quiet -ov -format UDZO -fs HFS+ \
        -volname "$app_name" -srcfolder "$dmg_root" "$dmg_path"
    echo "完成：$dmg_path"
}

create_dmg '松喵喵' 'Songnyang-macOS-arm64.dmg' 'Songnyang'
create_dmg '崔勇萌' 'SoobinPet-macOS-arm64.dmg' 'Soobin'
