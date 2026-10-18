# 秀彬 DEMO 素材来源

- 屏幕边缘探头姿势：用户提供的“俏皮小动物 背景更换.png”，保留墙面与角色、去除绿色背景后保存为 `assets/edge_peek/peek.png`；右侧姿势由程序水平镜像生成。原图备份于 `assets/sources/edge_peek/00_original.png`。
- 上下边缘姿势由现有 `assets/edge_peek/peek.png` 在运行时分别旋转 90° 和 270°，并裁去墙带；无需额外素材。
- 当前待机图：用户提供的“崔秀彬玩偶图片.png”，已去除绿幕并保存为 `assets/idle.png`。
- 点击反馈姿势：用户提供的“崔秀彬萌宠.png”，已去除绿幕并保存为 `assets/poses/wave.png`；点击桌宠时短暂显示。
- 旅行出入场动画：用户提供的“崔秀彬 玩偶图片.png”及“崔秀彬玩偶图片 2026年10月10日 (16)–(19)”五帧，依次去除绿幕并共用裁切框，保存至 `assets/frames/travel_walk/000.png`–`004.png`。去程向右播放原帧，返程向左播放镜像帧；旧四帧备份在 `assets/sources/travel_walk_previous/`。新原图备份于 `assets/sources/travel_walk/`。
- 日常散步动画：用户提供的 3 张“崔秀彬玩偶图片 2026年10月10日 (1)–(3)”向右行走帧，按原顺序去除绿幕并共用裁切框保存至 `assets/frames/walk/000.png`–`002.png`；向左散步时由程序水平镜像。原图备份于 `assets/sources/walk/`。
- 睡觉动画：用户提供的“更换图片背景 2026年10月10日 (5)”至“(8)”四张序列帧，按编号顺序去除绿幕、采用共同裁切范围并保存至 `assets/frames/sleep/00.png`–`03.png`；未经处理的原图保存在 `assets/sources/sleep/`。崔勇萌在 23:00 后空闲时循环播放，点击或拖动可叫醒。
- 拖动抱鱼动画：用户提供的“更换图片背景 2026年10月10日 (9)”至“(12)”四张序列帧，按编号去除绿幕并统一到站立图的 1254×1254 画布和可见高度，保存在 `assets/frames/lift/00.png`–`03.png`；未经处理的原图保存在 `assets/sources/lift/`。拖动移动超过阈值后循环播放，松开即恢复待机图，复用相同窗口和绘制区域以保持显示尺寸。
- 喂食动画：用户提供的 5 张“更换图片背景 2026年10月10日”序列帧，保留橙色兜帽角色造型，去除绿幕并以共同裁切框保存至 `assets/frames/feeding_anim/00.png`–`04.png`；原图备份于 `assets/sources/feeding/`。按原图、(1)、(2)、(3)、(4) 的顺序播放。
- 虚弱动画：用户提供的“更换图片背景 2026年10月10日 (13)–(15)”三帧，移除绿幕并保留透明通道，按 `00.png`–`02.png` 顺序保存到 `assets/frames/weak/`，以 700ms/帧循环播放；运行时对三帧使用相同裁剪框去掉透明留白，素材文件本身保持原样。未处理原图备份于 `assets/sources/weak/`。
- Apple Music 玩游戏动画：用户提供的“崔秀彬 毛绒兽.png”及“崔秀彬玩偶图片 2026年10月10日 (13)–(15)”四帧，移除绿幕并保留透明通道，按 `00.png`–`03.png` 顺序保存到 `assets/frames/play_game/`；未处理原图备份于 `assets/sources/play_game/`。点击肚子出现可点击的 Apple Music 气泡（`assets/game_prompt.png`）；点击后打开音乐应用，确认实际播放后以 `00→01→02→03→02→01`、650ms/帧循环播放游戏姿势，暂停或停止后恢复桌宠状态。气泡原图备份于 `assets/sources/play_game/game_prompt_original_green.png`。
- 信封：用户提供的“可爱信封 抠出左下角.png”，已去除绿幕并保存为 `assets/letter/envelope.png`，同时用于桌面来信提示。
- 信纸：用户提供的“抠出左下角信封.png”，已去除绿幕并保存为 `assets/letter/heart_paper.png`。
- 信件飞出动画：用户提供的“Unfolding Surprise Envelope Reveal.mp4”，提取为透明 PNG 序列并保存至 `assets/letter/reveal/`；对话框最后显示用户提供的秀彬语录之一。
- 旅行照片：TOMORROW X TOGETHER 官方 YouTube [《TXT-LOG: SOOBIN IN JAPAN》](https://www.youtube.com/watch?v=eqfYyTEak8w) 视频封面仍保存在 `assets/travel_postcard.jpg`，当前信件界面不展示。
- 信件短句：由用户提供的 10 条核实语录组成；信件界面只显示单条短句。
