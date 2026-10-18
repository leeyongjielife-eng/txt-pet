# TXT 桌宠

两个独立的 macOS 桌面宠物：松喵喵和崔勇萌。可分别运行，也可同时运行。用鼠标左键互动、拖动位置；在桌宠上点击右键，选择“退出”。

当前发布构建适用于 Apple 芯片 Mac。Windows 版尚未开发。

## 从源码运行

需要 Python 3.14，以及对应目录 `requirements.txt` 中的依赖。项目自带两个启动脚本：

```bash
PET_PYTHON=/path/to/python3 ./run.sh
PET_PYTHON=/path/to/python3 ./soobin_pet/run.sh
```

两个桌宠分别使用项目根目录和 `soobin_pet/` 中的素材。源码运行时，存档写入各自的 `data/` 目录；这些个人数据不会提交到仓库。

## 构建 Mac 安装镜像

在 Apple 芯片 Mac 上准备独立的构建环境：

```bash
python3 -m venv .packaging-venv
.packaging-venv/bin/python -m pip install -r requirements.txt pyinstaller
./packaging/build_mac.sh
```

脚本会在 `release/` 目录生成两个独立 DMG，每个镜像只包含对应桌宠和“应用程序”快捷方式。安装版的存档写入 `~/Library/Application Support/TXT Desktop Pets/`，不会改写应用包。

当前构建未使用 Apple Developer ID 签名或公证。面向其他用户正式发布前，需要完成签名、公证和安装测试。
