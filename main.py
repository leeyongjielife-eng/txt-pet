#!/usr/bin/env python3
"""
다고냥 (DA-GO-NYANG) Desktop Pet  —  Full Frame Animation
"""
import ctypes, glob, math, os, random, sys, tempfile, time
from datetime import datetime

from PyQt6.QtCore  import Qt, QTimer, QPoint, QRect, QLockFile
from PyQt6.QtGui   import QColor, QCursor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import QApplication, QMenu, QWidget
from AppKit import NSEvent, NSEventMaskKeyDown

from music import MusicController
from memory import MemoryManager
from letter import LetterDialog

_TXT_KEYWORDS = {
    "tomorrow x together", "txt", "투모로우바이투게더",
    "taehyun", "yeonjun", "soobin", "beomgyu", "hueningkai", "huening kai",
}

def _is_txt_content(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _TXT_KEYWORDS)

_MUSIC_STATES = ("music_anim", "music_static")

# 作息系统
_ROUTINE_BLOCKED = frozenset({
    "music_anim", "music_static",
    "eating_anim", "tail_wag", "flower_gift",
})
_ROUTINE_MSG = {
    "morning": "MOA早安喵～",
    "daytime": "今天也在这里喵。",
    "evening": "想活动一下喵。",
    "night":   "有点困喵...",
}

ROOT_DIR   = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR  = os.path.join(ROOT_DIR, "assets")
FRAMES_DIR = os.path.join(ASSET_DIR, "frames")

PET_SIZE     = 133          # 2/3 of 200
WALK_SIZE    = 125          # 步行动作比待机略收，和待机猫身占屏尺寸接近
LIFT_SIZE    = 160          # 拎起姿势按图像内容高度放大，与待机猫身接近
IDLE_POSE_SIZE = (133, 146) # 略高于普通帧，为头顶装饰留空间，猫身保持同一像素高度
MUSIC_ANIM_SIZE = (180, 163) # 放大头部至接近站立猫，并保持音乐帧原始比例
MUSIC_ANIM_CROP = QRect(17, 52, 701, 636) # 三帧共用透明边界，避免逐帧水平跳动
SLEEP_ANIM_SIZE = (180, 180) # 放大睡姿猫头至接近站立猫的实际头部尺寸
BUBBLE_H     = 34
MUSIC_DRAW_Y = BUBBLE_H + 2
MUSIC_WIN_H = MUSIC_DRAW_Y + MUSIC_ANIM_SIZE[1] + 12
SLEEP_WIN_H = BUBBLE_H + SLEEP_ANIM_SIZE[1] + 12
STAMINA_H    = 0
WIN_W        = PET_SIZE + 50
WIN_H        = BUBBLE_H + PET_SIZE + STAMINA_H + 8
BUBBLE_MAX_W = WIN_W - 8    # 滚动气泡最大宽度
EATING_WIN_W = 266          # 以 2:1 横幅完整展示猫和旁边的可颂/榛果
IDLE_POSE_INTERVAL_MS = (45_000, 90_000)
IDLE_POSE_DURATION_MS = {"workout": 5_000}
IDLE_POSE_SPEECH = {"workout": "练完啦！要不要一起运动，喵？"}
FEED_PROMPT_MS = 6_000
MUSIC_PROMPT_MS = 8_000
STAMINA_GAIN = 20
STAMINA_ANIM_MS = 900
STAMINA_HOLD_MS = 2_200
STAMINA_DRAIN_MS = 10 * 60 * 1000
STAMINA_WORKOUT_IDLE_S = 60 * 60
STAMINA_WORKOUT_COST = 2
WEAK_STAMINA_THRESHOLD = 20
EDGE_PEEK_RATIO = 1 / 3
MOOD_INTERVAL_MS = 10 * 60 * 1000
MOOD_DURATION_MS = 30_000
STAMINA_PERCENT_X_OFFSET = -18  # 资源画布含右侧尾巴，头部中心位于窗口中心左侧
STAMINA_PERCENT_Y = 19          # 额头三条纹正上方、猫猫轮廓外的空白位置
LOW_STAMINA_FX_MS = 80

# ms per frame for each animation
FRAME_MS = {
    "idle":          600,
    "blink":         110,
    "tail_wag":      190,
    "yawn":          250,
    "music_anim":    170,
    "music_static":  600,
    "eating_anim":   780,
    "flower_gift":   780,
    "scared_anim":   140,
    "walk":          300,
    "lift":          200,
    "sleep":         700,
    "workout":       250,
    "workout_after": 250,
    "travel":        250,
    "shy":           160,
    "weak":          700,
}

INACTIVITY_MS      = 20 * 60 * 1000     # 20分钟无互动触发打哈欠
HEAD_ZONE_RATIO    = 0.45               # 图片顶部45%视为头部区域
SLEEP_HOUR         = 23                # 按系统时间进入睡眠
WAKE_SLEEP_DELAY_MS = 5 * 60 * 1000    # 醒来后连续待机五分钟再睡
WORK_RESET_S       = 30 * 60           # 空闲30分钟 → 重置工作计时
WORK_TRIGGER_S     = 90 * 60           # 连续使用电脑90分钟后触发旅行
WALK_CHECK_MS  = 5 * 60 * 1000         # 每5分钟检查一次散步
WALK_PROB      = 0.20                  # 20%触发概率
WALK_PX_MIN    = 50                    # 最小移动距离px
WALK_PX_MAX    = 200                   # 最大移动距离px
WALK_STEP_PX   = 2                     # 每步移动像素
WALK_STEP_MS   = 40                    # 步进间隔ms
LIFT_DRAG_THRESHOLD_PX = 18             # 从按下点向上或向下拖动达到此距离触发拎起动画

_WALK_BLOCKED = frozenset({            # 散步阻断集
    "music_anim", "music_static",
    "eating_anim", "scared_anim", "tail_wag", "flower_gift",
})

_WORKOUT_SPEECHES = ("运动一下喵。", "MOA也要一起吗？", "腹肌确认喵。")
_SHY_SPEECHES    = ("被发现了喵...", "没、没什么喵...", "有点不好意思喵...", "MOA在看吗喵...")
SHY_PROB_CLICK   = 0.20    # 点击身体触发概率
SHY_PROB_TXT     = 0.15    # TXT歌曲切换触发概率
SHY_PROB_WORKOUT = 0.20    # 健身结束触发概率
TRAVEL_ANIM_MS = 3_000
TRAVEL_AWAY_MS = 20 * 60 * 1000
TRAVEL_RETURN_LINE_MS = 2_500
LETTER_QUOTES = (
    "小心寒冷，小心路上的冰，小心摔倒。",
    "不要为了快点走而摔倒。",
    "走路时有能扶着就扶着，不仅仅是说路。",
    "有结冰的路就避开。",
    "一步一步踩稳，好好走。",
    "我喜欢用行动来表达。",
    "祈祷别人幸福也是让我幸福的事。",
    "只要练习，没有什么是做不到的。",
    "在低谷时，也在一点点成长。",
    "今天的幸福，也同样珍贵。",
    "我想把心里的温暖都给 MOA。",
    "努力会慢慢变成自己的能力。",
)

ACTION_CFG = {
    "music":   {"anim": "music_anim",   "loop": True,  "speech": "♪ ·•·•·",    "dur": 0},
    "eating":  {"anim": "eating_anim",  "loop": False, "speech": "巧克力可颂★","dur": 6_000},
    "scared":  {"anim": "scared_anim",  "loop": False, "speech": "啊！！💦",   "dur": 4_000},
    "flower_gift": {"anim": "flower_gift", "loop": False, "speech": "这朵花送给你喵🌸", "dur": 3_000},
}


class PetWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.music  = MusicController()
        self.memory = MemoryManager()
        self._drag_pos      = None
        self._drag_origin_global = None
        self._drag_can_trigger_pose = False
        self._lift_active = False
        self._lift_resume_music = False
        self._speech        = ""
        self._track_lbl     = ""
        self._is_txt_song   = False
        self._scroll_offset = 0
        self._routine_state  = ""
        self._sleeping       = False
        self._sleep_after_wake = False
        self._last_activity  = time.time()
        self._last_mouse_pos = None
        self._work_start     = time.time()
        self._work_notified  = False
        self._walking        = False
        self._walk_target_x  = 0
        self._walk_dir       = 0
        self._edge_side      = None
        self._edge_screen    = None
        self._edge_return    = None
        self._shy_speech     = ""
        self._wake_suppressed_night = False
        self._idle_pose = ""
        self._last_idle_pose = ""
        self._idle_pose_pixmaps: dict[str, QPixmap] = {}
        self._workout_pose_px = None
        self._feed_prompt = False
        self._music_prompt = False
        self._music_playing = False
        saved_stamina = self.memory.get("stamina")
        self._stamina = max(0, min(100, 100 if saved_stamina is None else int(saved_stamina)))
        self._stamina_display = float(self._stamina)
        self._stamina_progress = 0.0
        self._stamina_anim_start = float(self._stamina)
        self._stamina_anim_target = float(self._stamina)
        self._stamina_feedback = ""
        self._stamina_workout = False
        self._mood_emoji = ""
        self._travel_state = "idle"
        self._travel_resume_music = False
        self._letter_pending = False
        self._letter_dialog = None
        self._keyboard_monitor = None

        # animation state
        self._seqs:  dict[str, list[QPixmap]] = {}
        self._seq:   list[QPixmap] = []
        self._fidx   = 0
        self._loop   = True
        self._acting = False
        self._cur    = ""
        self._last_interact = 0   # timestamp of last user interaction

        self._setup_window()
        self._setup_timers()
        self._load_frames()
        self._load_letter_assets()
        self._start_keyboard_monitor()

    # ── asset loading ─────────────────────────────────────────────────────────

    def _load_frames(self):
        screen = QApplication.primaryScreen()
        pixel_ratio = screen.devicePixelRatio() if screen else 1.0

        def _px(path, size=(PET_SIZE, PET_SIZE), crop=None):
            source = QPixmap(path)
            if source.isNull():
                return QPixmap()
            img = source.toImage().convertToFormat(
                QImage.Format.Format_ARGB32_Premultiplied
            )
            if crop is not None:
                img = img.copy(crop)
            pixmap = QPixmap.fromImage(img).scaled(
                round(size[0] * pixel_ratio),
                round(size[1] * pixel_ratio),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap.setDevicePixelRatio(pixel_ratio)
            return pixmap

        if os.path.isdir(FRAMES_DIR):
            for name in sorted(os.listdir(FRAMES_DIR)):
                d = os.path.join(FRAMES_DIR, name)
                if not os.path.isdir(d):
                    continue
                # Yawn is composited over the exact standing sprite below so
                # its body, scale, and position stay pixel-aligned with idle.
                if name in ("yawn", "letter_reveal"):
                    continue
                files = sorted(
                    f for f in glob.glob(os.path.join(d, "*.png"))
                    if not os.path.basename(f).startswith(".")
                )
                if files:
                    crop = None
                    if name == "music_anim":
                        size = MUSIC_ANIM_SIZE
                        crop = MUSIC_ANIM_CROP
                    elif name == "sleep":
                        size = SLEEP_ANIM_SIZE
                    elif name == "eating_anim":
                        size = (EATING_WIN_W, PET_SIZE)
                    elif name == "walk":
                        size = (WALK_SIZE, WALK_SIZE)
                    elif name == "lift":
                        size = (LIFT_SIZE, LIFT_SIZE)
                    else:
                        size = (PET_SIZE, PET_SIZE)
                    frames = [_px(f, size, crop) for f in files]
                    self._seqs[name] = [frame for frame in frames if not frame.isNull()]
                    print(f"  {name}: {len(self._seqs[name])} 帧")

        # idle base
        p = os.path.join(ASSET_DIR, "idle.png")
        standing_path = os.path.join(ASSET_DIR, "idle_standing.png")
        if not os.path.exists(standing_path):
            standing_path = p
        idle_px = _px(standing_path, IDLE_POSE_SIZE) if os.path.exists(standing_path) else QPixmap(*IDLE_POSE_SIZE)
        self._seqs["idle"] = [idle_px]
        self._idle_px = idle_px

        # All yawn frames reuse the same standing body. Only the eye angle and
        # mouth opening change, so the cat does not shift during the action.
        def _yawn_frame(openness):
            frame = QPixmap(idle_px)
            painter = QPainter(frame)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(118, 107, 102))
            painter.drawRect(QRect(26, 50, 28, 37))
            painter.drawRect(QRect(59, 50, 27, 37))
            painter.drawEllipse(QRect(51, 64, 16, 12))

            eye_pen = QPen(QColor(10, 9, 9), 3.2)
            eye_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            eye_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(eye_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            eye_angle = 2 + 5 * openness
            left_eye = QPainterPath()
            left_eye.moveTo(30, 64 - eye_angle)
            left_eye.lineTo(46, 64)
            left_eye.lineTo(30, 64 + eye_angle)
            right_eye = QPainterPath()
            right_eye.moveTo(82, 64 - eye_angle)
            right_eye.lineTo(66, 64)
            right_eye.lineTo(82, 64 + eye_angle)
            painter.drawPath(left_eye)
            painter.drawPath(right_eye)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 7, 7))
            painter.drawEllipse(QRect(54, 67, 7, 5))
            mouth_w = round(9 + 9 * openness)
            mouth_h = round(8 + 18 * openness)
            mouth_x = round(58 - mouth_w / 2)
            mouth_y = round(72 + 9 * (1 - openness))
            painter.drawEllipse(QRect(mouth_x, mouth_y, mouth_w, mouth_h))
            inner = QRect(mouth_x + 3, mouth_y + 2, mouth_w - 6, mouth_h - 4)
            mouth = QPainterPath()
            mouth.addEllipse(inner.x(), inner.y(), inner.width(), inner.height())
            painter.fillPath(mouth, QColor(125, 35, 48))
            painter.save()
            painter.setClipPath(mouth)
            painter.setBrush(QColor(255, 135, 112))
            painter.drawEllipse(QRect(
                inner.x(), inner.y() + round(inner.height() * 0.55),
                inner.width(), max(3, round(inner.height() * 0.5)),
            ))
            painter.restore()
            painter.end()
            return frame

        self._seqs["yawn"] = [_yawn_frame(level) for level in (0.35, 0.7, 1.0, 0.45)]

        workout_path = os.path.join(ASSET_DIR, "idle_workout.png")
        if os.path.exists(workout_path):
            self._workout_pose_px = _px(workout_path, IDLE_POSE_SIZE)

        weak_path = os.path.join(ASSET_DIR, "weak_sprite.png")
        if os.path.exists(weak_path):
            sheet = QImage(weak_path).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            cell_w = sheet.width() // 3
            self._seqs["weak"] = [
                QPixmap.fromImage(sheet.copy(i * cell_w, 0, cell_w, sheet.height())).scaled(
                    round(PET_SIZE * pixel_ratio),
                    round(PET_SIZE * pixel_ratio),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                for i in range(3)
            ]
            for px in self._seqs["weak"]:
                px.setDevicePixelRatio(pixel_ratio)
            print("  weak: 3 帧")

        # music static（戴耳机静止，非 TXT 时使用）
        p = os.path.join(ASSET_DIR, "music.png")
        if os.path.exists(p):
            self._seqs["music_static"] = [_px(p)]
            print("  music_static: 1 帧")

        self._edge_peek_pixmaps = {}
        edge_dir = os.path.join(ASSET_DIR, "edge_peek")
        # The source pictures include a painted wall along the screen side.
        # Crop that strip before scaling so the cat itself meets the real edge.
        edge_crops = {
            "left": QRect(74, 0, 636, 960),
            "right": QRect(0, 0, 636, 960),
            "top": QRect(0, 78, 960, 632),
            "bottom": QRect(0, 0, 960, 636),
        }
        for side in ("left", "right", "top", "bottom"):
            path = os.path.join(edge_dir, f"{side}.png")
            if os.path.exists(path):
                self._edge_peek_pixmaps[side] = _px(path, crop=edge_crops[side])
        if self._edge_peek_pixmaps:
            print(f"  edge_peek: {', '.join(self._edge_peek_pixmaps)}")

        self._go_idle()

    @staticmethod
    def _pixmap_logical_size(pixmap):
        ratio = pixmap.devicePixelRatioF() or 1.0
        return round(pixmap.width() / ratio), round(pixmap.height() / ratio)

    def _load_letter_assets(self):
        envelope_path = os.path.join(ASSET_DIR, "envelope_icon.png")
        self._envelope_px = QPixmap(envelope_path)
        if not self._envelope_px.isNull():
            self._envelope_px = self._envelope_px.scaled(
                48,
                30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        LetterDialog.preload_frames()

    def _start_keyboard_monitor(self):
        try:
            accessibility = ctypes.CDLL(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            is_trusted = accessibility.AXIsProcessTrusted
            is_trusted.argtypes = []
            is_trusted.restype = ctypes.c_bool
            keyboard_access = bool(is_trusted())
            self._keyboard_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown,
                lambda _event: self._record_computer_activity(),
            )
            if not keyboard_access or self._keyboard_monitor is None:
                print("[activity] 键盘活动需要为运行桌宠的进程开启 macOS 辅助功能/输入监控权限。")
        except Exception as exc:
            print(f"[activity] 键盘监控不可用：{exc}")

    def _record_computer_activity(self, now=None):
        now = now or time.time()
        if now - self._last_activity >= WORK_RESET_S:
            self._work_start = now
            self._work_notified = False
        self._last_activity = now

    # ── animation control ─────────────────────────────────────────────────────

    def _go_idle(self):
        if self._stamina <= WEAK_STAMINA_THRESHOLD and "weak" in self._seqs:
            self._enter_weak()
            return
        self._hide_feed_prompt()
        self._hide_music_prompt()
        self._stamina_workout = False
        self._idle_pose = ""
        self._idle_pose_timer.stop()
        self._idle_pose_return_timer.stop()
        self._seq           = self._seqs.get("idle", [])
        self._fidx          = 0
        self._loop          = True
        self._acting        = False
        self._cur           = "idle"
        self._speech        = ""
        self._track_lbl     = ""
        self._is_txt_song   = False
        self._scroll_offset = 0
        self._sleeping      = False
        self._walking       = False
        self._walk_step_timer.stop()
        self._frame_timer.setInterval(FRAME_MS["idle"])
        self._resize_for_animation("idle")
        self._restore_edge_after_action()
        self._schedule_idle_pose()
        self._schedule_wake_sleep()

    def _enter_weak(self):
        self._hide_feed_prompt()
        self._hide_music_prompt()
        self._idle_pose_timer.stop()
        self._idle_pose_return_timer.stop()
        self._seq = self._seqs["weak"]
        self._fidx = 0
        self._loop = True
        self._acting = False
        self._cur = "weak"
        self._speech = ""
        self._sleeping = False
        self._walking = False
        self._stamina_workout = False
        self._walk_step_timer.stop()
        self._frame_timer.setInterval(FRAME_MS["weak"])
        self._resize_for_animation("weak")
        self._restore_edge_after_action()
        self.update()

    def _restore_edge_after_action(self):
        anchor = self._edge_return
        if not anchor:
            return
        self._edge_return = None
        side, screen, x, y = anchor
        if screen is None:
            return
        self._edge_side = side
        self._edge_screen = screen
        x, y = self._edge_snap_position(side, x, y, screen)
        self.move(x, y)

    def _leave_edge_for_action(self):
        if not self._edge_side or self._edge_return:
            return
        side, screen = self._edge_side, self._edge_screen
        x, y = self.x(), self.y()
        self._edge_return = (side, screen, x, y)
        self._edge_side = None
        self._edge_screen = None
        inset = max(48, round(PET_SIZE * EDGE_PEEK_RATIO))
        if side == "left":
            x += inset
        elif side == "right":
            x -= inset
        elif side == "top":
            y += inset
        else:
            y -= inset
        self.move(x, y)

    def _schedule_idle_pose(self, delay=None):
        if not getattr(self, "_idle_pose_pixmaps", None):
            return
        self._idle_pose_timer.start(
            delay if delay is not None else random.randint(*IDLE_POSE_INTERVAL_MS)
        )

    def _show_idle_pose(self):
        if (
            self._cur != "idle" or self._acting or self._sleeping or self._walking
            or self._drag_pos or self._speech or self._shy_speech
            or self._stamina <= WEAK_STAMINA_THRESHOLD
        ):
            self._schedule_idle_pose(random.randint(10_000, 20_000))
            return

        available = [pose for pose in self._idle_pose_pixmaps if pose != self._last_idle_pose]
        if not available:
            available = list(self._idle_pose_pixmaps)
        if not available:
            return

        pose = random.choice(available)
        self._last_idle_pose = pose
        self._idle_pose = pose
        self._seq = [self._idle_pose_pixmaps[pose]]
        self._fidx = 0
        self._speech = IDLE_POSE_SPEECH.get(pose, "")
        self._resize_for_animation("idle_pose_workout" if pose == "workout" else "idle")
        self.update()
        self._idle_pose_return_timer.start(IDLE_POSE_DURATION_MS[pose])

    def _check_stamina_workout(self):
        if self._travel_state != "idle":
            return
        now = time.time()
        if self._stamina <= WEAK_STAMINA_THRESHOLD:
            return
        if now - self._last_interact < STAMINA_WORKOUT_IDLE_S:
            return
        if now - self._last_stamina_workout_at < STAMINA_WORKOUT_IDLE_S:
            return
        if self._cur != "idle" or self._acting or self._sleeping or self._walking:
            return
        if self._drag_pos or self._speech or self._shy_speech:
            return
        self._start_stamina_workout(now)

    def _start_stamina_workout(self, now=None):
        workout_frames = self._seqs.get("workout_after")
        if not workout_frames and self._workout_pose_px is None:
            return
        self._last_stamina_workout_at = now or time.time()
        self._idle_pose_timer.stop()
        self._idle_pose_return_timer.stop()
        self._stamina_workout = True
        self._idle_pose = "workout"
        self._seq = workout_frames or [self._workout_pose_px]
        self._fidx = 0
        self._loop = True
        self._acting = True
        self._cur = "stamina_workout"
        self._speech = IDLE_POSE_SPEECH["workout"]
        self._frame_timer.setInterval(FRAME_MS["workout_after"] if workout_frames else FRAME_MS["idle"])
        self._resize_for_animation("idle_pose_workout")
        self.update()
        QTimer.singleShot(IDLE_POSE_DURATION_MS["workout"], self._finish_stamina_workout)

    def _finish_stamina_workout(self):
        if not self._stamina_workout:
            return
        self._stamina_workout = False
        self._change_stamina(-STAMINA_WORKOUT_COST, f"健身 -{STAMINA_WORKOUT_COST}")
        self._go_idle()

    def _resize_for_animation(self, name: str):
        if name == "music_anim":
            height = MUSIC_WIN_H
        elif name == "sleep":
            height = SLEEP_WIN_H
        else:
            height = WIN_H
        if name == "eating_anim":
            width = EATING_WIN_W
        elif name == "letter_offer":
            width = WIN_W + 44
        elif name == "idle_pose_workout":
            font = QFont("Helvetica", 13, QFont.Weight.Bold)
            width = max(WIN_W, QFontMetrics(font).horizontalAdvance(IDLE_POSE_SPEECH["workout"]) + 24)
        else:
            width = WIN_W
        if self.width() == width and self.height() == height:
            return
        center_x = self.x() + self.width() / 2
        bottom_y = self.y() + self.height()
        self.setFixedSize(width, height)
        screen = QApplication.primaryScreen().geometry()
        x = round(center_x - width / 2)
        y = bottom_y - height
        self.move(
            max(screen.left(), min(x, screen.right() - width + 1)),
            y,
        )

    def _play(self, name: str, loop=False, speech="") -> bool:
        if name not in self._seqs:
            name = "idle"
        if name not in ("idle", "weak"):
            self._leave_edge_for_action()
        self._seq    = self._seqs[name]
        self._fidx   = 0
        self._loop   = loop
        self._acting = True
        self._cur    = name
        self._hide_feed_prompt()
        self._hide_music_prompt()
        self._hide_stamina_gain()
        if name not in ("idle", "blink"):
            self._idle_pose = ""
            self._idle_pose_timer.stop()
            self._idle_pose_return_timer.stop()
        self._speech = speech
        self._resize_for_animation(name)
        self._frame_timer.setInterval(FRAME_MS.get(name, 200))
        self.update()
        return True

    def _advance_frame(self):
        if not self._seq:
            return
        self._fidx += 1
        if self._fidx >= len(self._seq):
            if self._loop:
                self._fidx = 0
            else:
                if self._cur == "yawn":
                    self._go_idle()
                    self.update()
                    return
                self._fidx = len(self._seq) - 1
                if self._acting and self._cur not in _MUSIC_STATES and self._cur != "eating_anim":
                    QTimer.singleShot(300, self._go_idle)
        self.update()

    # ── random idle behaviours ────────────────────────────────────────────────

    def _setup_timers(self):
        import time
        self._last_interact = time.time()
        self._last_stamina_workout_at = self._last_interact

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._advance_frame)
        self._frame_timer.start(FRAME_MS["idle"])

        # 保留待机姿势计时器结构；头顶爱心姿势已停用，健身由体力系统单独触发。
        self._idle_pose_timer = QTimer(self)
        self._idle_pose_timer.setSingleShot(True)
        self._idle_pose_timer.timeout.connect(self._show_idle_pose)
        self._idle_pose_return_timer = QTimer(self)
        self._idle_pose_return_timer.setSingleShot(True)
        self._idle_pose_return_timer.timeout.connect(self._go_idle)

        # 点击猫猫后出现的喂食泡泡
        self._feed_prompt_timer = QTimer(self)
        self._feed_prompt_timer.setSingleShot(True)
        self._feed_prompt_timer.timeout.connect(self._hide_feed_prompt)

        # 点击耳朵后出现的 Apple Music 控制气泡
        self._music_prompt_timer = QTimer(self)
        self._music_prompt_timer.setSingleShot(True)
        self._music_prompt_timer.timeout.connect(self._hide_music_prompt)

        # 体力条数值变化动画
        self._stamina_anim_timer = QTimer(self)
        self._stamina_anim_timer.setInterval(40)
        self._stamina_anim_timer.timeout.connect(self._advance_stamina_gain)
        self._stamina_hide_timer = QTimer(self)
        self._stamina_hide_timer.setSingleShot(True)
        self._stamina_hide_timer.timeout.connect(self._hide_stamina_gain)

        # 运行期间每10分钟自然消耗1%；无互动满1小时触发健身并额外消耗2%。
        self._stamina_drain_timer = QTimer(self)
        self._stamina_drain_timer.timeout.connect(self._drain_stamina)
        self._stamina_drain_timer.start(STAMINA_DRAIN_MS)
        self._stamina_workout_timer = QTimer(self)
        self._stamina_workout_timer.timeout.connect(self._check_stamina_workout)
        self._stamina_workout_timer.start(60_000)

        # 每10分钟随机展示一次猫猫心情，停留30秒。
        self._mood_timer = QTimer(self)
        self._mood_timer.timeout.connect(self._show_random_mood)
        self._mood_timer.start(MOOD_INTERVAL_MS)
        self._mood_hide_timer = QTimer(self)
        self._mood_hide_timer.setSingleShot(True)
        self._mood_hide_timer.timeout.connect(self._hide_mood)

        # 低体力时驱动百分比的闪光与放大动画。
        self._low_stamina_fx_timer = QTimer(self)
        self._low_stamina_fx_timer.setInterval(LOW_STAMINA_FX_MS)
        self._low_stamina_fx_timer.timeout.connect(self.update)
        if self._stamina < WEAK_STAMINA_THRESHOLD:
            self._low_stamina_fx_timer.start()

        # 20分钟无互动 → 打哈欠
        self._inact_timer = QTimer(self)
        self._inact_timer.setSingleShot(True)
        self._inact_timer.timeout.connect(self._on_inactivity)
        self._inact_timer.start(INACTIVITY_MS)

        # 每5秒同步 Apple Music 播放状态
        self._bg_music_timer = QTimer(self)
        self._bg_music_timer.timeout.connect(self._sync_music_state)
        self._bg_music_timer.start(5_000)

        # 滚动字幕（50ms / tick）
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._scroll_tick)
        self._scroll_timer.start(50)

        # 作息状态机（5分钟检查一次；启动后 1 秒初始化）
        self._routine_timer = QTimer(self)
        self._routine_timer.timeout.connect(self._check_routine)
        self._routine_timer.start(5 * 60 * 1000)
        QTimer.singleShot(1_000, self._init_routine)

        # 睡觉检查（每60秒检查一次）
        self._sleep_check_timer = QTimer(self)
        self._sleep_check_timer.timeout.connect(self._check_sleep)
        self._sleep_check_timer.start(60_000)

        self._wake_sleep_timer = QTimer(self)
        self._wake_sleep_timer.setSingleShot(True)
        self._wake_sleep_timer.timeout.connect(self._on_wake_sleep_timeout)

        # 鼠标活动轮询（每30秒检测鼠标是否移动）
        self._mouse_poll_timer = QTimer(self)
        self._mouse_poll_timer.timeout.connect(self._poll_mouse_activity)
        self._mouse_poll_timer.start(30_000)

        # 连续电脑使用时长触发旅行（每分钟检查一次）
        self._work_timer = QTimer(self)
        self._work_timer.timeout.connect(self._check_computer_use_travel)
        self._work_timer.start(60_000)

        # 散步（每5分钟随机检查）
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._check_walk)
        self._walk_timer.start(WALK_CHECK_MS)

        # 散步步进（按需启动）
        self._walk_step_timer = QTimer(self)
        self._walk_step_timer.timeout.connect(self._walk_step)


    def _scroll_tick(self):
        if self._cur not in _MUSIC_STATES or self._is_txt_song:
            if self._scroll_offset:
                self._scroll_offset = 0
                self.update()
            return
        text = self._track_lbl or "♪ ·•·•·"
        tw = QFontMetrics(QFont("Helvetica", 13, QFont.Weight.Bold)).horizontalAdvance(text)
        content_w = BUBBLE_MAX_W - 16
        if tw <= content_w:
            if self._scroll_offset:
                self._scroll_offset = 0
                self.update()
            return
        self._scroll_offset += 1
        if self._scroll_offset > tw - content_w + 24:
            self._scroll_offset = 0
        self.update()

    def _show_random_mood(self):
        if self._travel_state != "idle":
            return
        if self._acting or self._walking or self._drag_pos or self._feed_prompt or self._music_prompt:
            return
        if self._speech or self._shy_speech or self._cur in _MUSIC_STATES:
            return
        if self._stamina < WEAK_STAMINA_THRESHOLD:
            return
        if self._stamina <= 50:
            choices = ("😌", "😐", "😪")
        else:
            choices = ("😊", "😎", "😌", "😉", "😈")
        self._mood_emoji = random.choice(choices)
        self._mood_hide_timer.start(MOOD_DURATION_MS)
        self.update()

    def _hide_mood(self):
        if self._mood_emoji:
            self._mood_emoji = ""
            self.update()

    def _sync_music_state(self):
        playing = self.music.is_playing()
        if self._music_playing != playing:
            self._music_playing = playing
            if self._travel_state != "idle":
                self._travel_resume_music = playing
            if self._music_prompt:
                self.update()
        if self._travel_state != "idle":
            return
        if playing and (self._cur == "idle" or self._sleeping):
            if self._sleeping:
                self._wake_up()
            self._play("music_anim", loop=True, speech="")
            self._poll_track()
        elif not playing and self._cur in _MUSIC_STATES:
            self._go_idle()

    def _on_inactivity(self):
        """20分钟无互动 → 打哈欠，然后重新计时"""
        if self._travel_state != "idle":
            self._inact_timer.start(INACTIVITY_MS)
            return
        if (
            self._stamina > WEAK_STAMINA_THRESHOLD
            and not self._acting and not self._sleeping
            and "yawn" in self._seqs
        ):
            self._play("yawn", loop=False, speech="")
        self._inact_timer.start(INACTIVITY_MS)

    def _reset_inactivity(self):
        """任何用户互动都重置20分钟计时"""
        self._last_interact = time.time()
        self._record_computer_activity(self._last_interact)
        self._last_stamina_workout_at = self._last_interact
        self._inact_timer.start(INACTIVITY_MS)
        if self._sleeping:
            self._wake_up()
        elif self._sleep_after_wake:
            self._schedule_wake_sleep()

    # ── routine state machine ─────────────────────────────────────────────────

    def _get_routine(self) -> str:
        h = datetime.now().hour
        if 6  <= h < 10: return "morning"
        if 10 <= h < 18: return "daytime"
        if 18 <= h < 23: return "evening"
        return "night"

    def _init_routine(self):
        self._routine_state = self._get_routine()
        print(f"[routine] 当前时段：{self._routine_state}")
        self._check_sleep()

    def _check_routine(self):
        new = self._get_routine()
        if new == self._routine_state:
            return
        self._routine_state = new
        if new != "night":
            self._wake_suppressed_night = False
        if self._travel_state != "idle":
            return
        if self._sleeping and new != "night":
            self._wake_up()
            return
        if self._cur in _ROUTINE_BLOCKED:
            return
        self._speech = _ROUTINE_MSG[new]
        self.update()
        QTimer.singleShot(4_000, self._clear_routine_msg)

    def _clear_routine_msg(self):
        if self._speech in _ROUTINE_MSG.values():
            self._speech = ""
            self.update()
            self._schedule_wake_sleep()

    # ── sleep system ──────────────────────────────────────────────────────────

    def _check_sleep(self):
        if (self._travel_state != "idle" or self._sleeping or self._routine_state != "night"
                or self._wake_suppressed_night):
            return
        if (self._acting or self._drag_pos or self._edge_side or self._feed_prompt
                or self._music_prompt or self._cur in _MUSIC_STATES
                or self._cur != "idle"):
            return
        if datetime.now().hour >= SLEEP_HOUR:
            self._enter_sleep()

    def _enter_sleep(self):
        self._sleeping = True
        if "sleep" in self._seqs:
            self._play("sleep", loop=True, speech="")
        else:
            speech = "有点困喵..."
            self._speech = speech
            self.update()
        print("[sleep] 松喵喵睡着了...")

    def _wake_up(self):
        if not self._sleeping:
            return
        self._wake_suppressed_night = True
        self._sleep_after_wake = True
        self._go_idle()
        print("[sleep] 松喵喵醒来了...")

    def _schedule_wake_sleep(self):
        if self._sleep_after_wake and hasattr(self, "_wake_sleep_timer"):
            self._wake_sleep_timer.start(WAKE_SLEEP_DELAY_MS)

    def _on_wake_sleep_timeout(self):
        if not self._sleep_after_wake:
            return
        if (
            self._travel_state != "idle" or self._acting or self._drag_pos
            or self._edge_side or self._feed_prompt or self._music_prompt
            or self._cur != "idle" or self._speech or self._shy_speech
        ):
            return
        self._sleep_after_wake = False
        self._wake_suppressed_night = False
        if self._get_routine() == "night":
            self._enter_sleep()

    # ── computer use duration for travel ──────────────────────────────────────

    def _poll_mouse_activity(self):
        pos = QCursor.pos()
        xy  = (pos.x(), pos.y())
        if xy == self._last_mouse_pos:
            return
        self._last_mouse_pos = xy
        self._record_computer_activity()

    def _check_computer_use_travel(self):
        if self._travel_state != "idle":
            return
        now    = time.time()
        idle_s = now - self._last_activity
        # 连续使用电脑90分钟后触发旅行；键盘和鼠标活动共用同一计时。
        busy_animation = self._acting and self._cur not in _MUSIC_STATES
        if not (
            self._sleeping or busy_animation or self._drag_pos or self._speech or self._shy_speech
            or self._cur in ("eating_anim", "tail_wag", "flower_gift")
        ):
            if idle_s < WORK_RESET_S and not self._work_notified:
                if now - self._work_start >= WORK_TRIGGER_S:
                    self._work_notified = True
                    self._work_start    = now
                    self._start_travel_event()

    def _start_travel_event(self):
        if self._travel_state != "idle" or "travel" not in self._seqs:
            return
        self._travel_resume_music = self._music_playing
        self._travel_state = "leaving"
        self._letter_pending = False
        self._hide_feed_prompt()
        self._hide_music_prompt()
        self._play("travel", loop=True, speech="我要去旅行了喵")
        QTimer.singleShot(TRAVEL_ANIM_MS, self._leave_for_travel)
        print("[travel] 松喵喵准备出发")

    def _leave_for_travel(self):
        if self._travel_state != "leaving":
            return
        self._travel_state = "away"
        self._speech = ""
        self.hide()
        QTimer.singleShot(TRAVEL_AWAY_MS, self._return_from_travel)

    def _return_from_travel(self):
        if self._travel_state != "away":
            return
        self._travel_state = "returning"
        self.show()
        self.raise_()
        self._resize_for_animation("travel")
        self._seq = list(reversed(self._seqs.get("travel", [])))
        if not self._seq:
            self._finish_return_animation()
            return
        self._fidx = 0
        self._loop = True
        self._acting = True
        self._cur = "travel_return"
        self._speech = "我回来啦喵"
        self._frame_timer.setInterval(FRAME_MS["travel"])
        self.update()
        QTimer.singleShot(TRAVEL_ANIM_MS, self._finish_return_animation)

    def _finish_return_animation(self):
        if self._travel_state != "returning":
            return
        self._travel_state = "letter_waiting"
        self._set_idle_speech("我回来啦喵")
        QTimer.singleShot(TRAVEL_RETURN_LINE_MS, self._offer_travel_letter)

    def _offer_travel_letter(self):
        if self._travel_state != "letter_waiting":
            return
        # 每次信件送达后，从此刻开始新一轮90分钟电脑使用计时。
        self._work_start = time.time()
        self._work_notified = False
        self._letter_pending = True
        self._resize_for_animation("letter_offer")
        self._speech = "有一封信给你喵"
        self.update()

    def _set_idle_speech(self, speech):
        self._seq = self._seqs.get("idle", [])
        self._fidx = 0
        self._loop = True
        self._acting = False
        self._cur = "letter_offer"
        self._speech = speech
        self._frame_timer.setInterval(FRAME_MS["idle"])
        self._resize_for_animation("letter_offer")
        self.update()

    def _letter_icon_rect(self):
        return QRect(self.width() - 52, BUBBLE_H + 4, 48, 30)

    def _open_travel_letter(self):
        if not self._letter_pending:
            return
        self._letter_pending = False
        self._speech = ""
        self._set_idle_speech("")
        quote = random.choice(LETTER_QUOTES)
        self._letter_dialog = LetterDialog(quote, self)
        screen = QApplication.primaryScreen().availableGeometry()
        x = self.x() + self.width() + 12
        y = self.y() - 80
        x = min(max(screen.left(), x), screen.right() - self._letter_dialog.width() + 1)
        y = min(max(screen.top(), y), screen.bottom() - self._letter_dialog.height() + 1)
        self._letter_dialog.move(x, y)
        self._letter_dialog.finished.connect(self._close_travel_letter)
        self._travel_state = "reading"
        self._letter_dialog.show()

    def _close_travel_letter(self, _result=0):
        self._letter_dialog = None
        self._travel_state = "idle"
        self._letter_pending = False
        self._speech = ""
        if self._music_playing or self._travel_resume_music:
            self._travel_resume_music = False
            self._play("music_anim", loop=True, speech="")
            QTimer.singleShot(600, self._poll_track)
        else:
            self._go_idle()

    def _clear_timed_bubble(self, msg: str):
        if self._speech == msg:
            self._speech = ""
            self.update()
            self._schedule_wake_sleep()

    # ── walk system ───────────────────────────────────────────────────────────

    def _check_walk(self):
        if self._travel_state != "idle":
            return
        if self._stamina <= WEAK_STAMINA_THRESHOLD:
            return
        if self._walking or self._sleeping or self._drag_pos or self._edge_side:
            return
        if self._cur in _WALK_BLOCKED or self._acting:
            return
        if random.random() > WALK_PROB:
            return
        self._start_walk()

    def _start_walk(self):
        scr    = QApplication.primaryScreen().geometry()
        cur_x  = self.x()
        dist   = random.randint(WALK_PX_MIN, WALK_PX_MAX)
        direct = random.choice((-1, 1))
        target = cur_x + direct * dist
        pet_rect = self._current_pet_rect()
        overhang = round(pet_rect.width() * EDGE_PEEK_RATIO)
        left_limit = scr.left() - pet_rect.x() - overhang
        right_limit = scr.right() - pet_rect.x() - pet_rect.width() + 1 + overhang
        target = max(left_limit, min(target, right_limit))
        if target == cur_x:
            return
        self._walk_target_x = target
        self._walk_dir      = 1 if target > cur_x else -1
        self._walking       = True
        self._play("walk", loop=True, speech="")
        if self._walk_dir < 0:
            flip = QTransform().scale(-1, 1)
            self._seq = [frame.transformed(flip) for frame in self._seq]
            self.update()
        self._walk_step_timer.start(WALK_STEP_MS)
        print(f"[walk] 出发 x={cur_x} → {target}（{'+' if self._walk_dir > 0 else ''}{target - cur_x}px）")

    def _walk_step(self):
        if self._drag_pos:
            self._walk_step_timer.stop()
            self._walking = False
            return
        cur_x = self.x()
        if self._walk_dir > 0:
            new_x = min(cur_x + WALK_STEP_PX, self._walk_target_x)
        else:
            new_x = max(cur_x - WALK_STEP_PX, self._walk_target_x)
        self._move_with_edge_detection(new_x, self.y())
        if self._edge_side:
            self._walk_step_timer.stop()
            self._walking = False
            self._go_idle()
            print(f"[walk] 到达屏幕{self._edge_side}缘，切换探边姿态")
            return
        if new_x == self._walk_target_x:
            self._walk_step_timer.stop()
            self._walking = False
            self._go_idle()
            print("[walk] 到达目标，恢复发呆")

    # ── shy system ────────────────────────────────────────────────────────────

    def _trigger_shy(self, animate=True):
        if self._travel_state != "idle" or self._sleeping or self._drag_pos:
            return
        msg = random.choice(_SHY_SPEECHES)
        self._shy_speech = msg
        self.update()
        if animate and not self._acting and "shy" in self._seqs:
            self._play("shy", loop=False, speech="")
        QTimer.singleShot(3_000, lambda: self._clear_shy(msg))
        print(f"[shy] {msg}")

    def _clear_shy(self, msg: str):
        if self._shy_speech == msg:
            self._shy_speech = ""
            self.update()
            self._schedule_wake_sleep()

    # ── window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setFixedSize(WIN_W, WIN_H)

        scr = QApplication.primaryScreen().geometry()
        self.move(scr.width() - WIN_W - 20, scr.height() - WIN_H - 80)

    def _screen_for_position(self, x: int, y: int):
        if self._edge_side and self._edge_screen is not None:
            return self._edge_screen
        center = QPoint(x + self.width() // 2, y + self.height() // 2)
        return QApplication.screenAt(center) or QApplication.primaryScreen()

    def _edge_candidate(self, x: int, y: int, screen):
        if screen is None:
            return None
        scr = screen.geometry()
        pet = self._current_pet_rect()
        if pet.isNull():
            return None
        body = QRect(x + pet.x(), y + pet.y(), pet.width(), pet.height())
        ratios = {
            "left": max(0, scr.left() - body.left()) / max(1, body.width()),
            "right": max(0, body.right() - scr.right()) / max(1, body.width()),
            "top": max(0, scr.top() - body.top()) / max(1, body.height()),
            "bottom": max(0, body.bottom() - scr.bottom()) / max(1, body.height()),
        }
        side, ratio = max(ratios.items(), key=lambda item: item[1])
        return side if ratio >= EDGE_PEEK_RATIO else None

    def _edge_snap_position(self, side: str, x: int, y: int, screen):
        scr = screen.geometry()
        if side == "left":
            x = scr.left()
            y = max(scr.top(), min(y, scr.bottom() - self.height() + 1))
        elif side == "right":
            x = scr.right() - self.width() + 1
            y = max(scr.top(), min(y, scr.bottom() - self.height() + 1))
        elif side == "top":
            x = max(scr.left(), min(x, scr.right() - self.width() + 1))
            # Keep the widget at the physical edge; its picture is cropped to
            # the cat before scaling, so no painted boundary is visible.
            y = scr.top()
        else:
            x = max(scr.left(), min(x, scr.right() - self.width() + 1))
            y = scr.bottom() - self.height() + 1
        return x, y

    def _move_with_edge_detection(self, x: int, y: int):
        screen = self._screen_for_position(x, y)
        scr = screen.geometry() if screen else None
        pet = self._current_pet_rect()
        body = QRect(x + pet.x(), y + pet.y(), pet.width(), pet.height())
        if self._edge_side and screen is self._edge_screen:
            if (scr.contains(body.topLeft()) and scr.contains(body.bottomRight())):
                previous_side = self._edge_side
                self._edge_side = None
                self._edge_screen = None
                self.move(x, y)
                self.update()
                print(f"[edge] 离开屏幕{previous_side}缘，恢复当前动画")
                return

        side = self._edge_candidate(x, y, screen)
        if side:
            if side != self._edge_side:
                print(f"[edge] 猫身越过屏幕{side}缘三分之一，切换贴边姿态")
            self._edge_side = side
            self._edge_screen = screen
            x, y = self._edge_snap_position(side, x, y, screen)
        elif self._edge_side:
            # Keep the edge pose visible while the body still crosses that edge.
            x, y = self._edge_snap_position(self._edge_side, x, y, self._edge_screen)
        self.move(x, y)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._float_on_top()

    def _float_on_top(self):
        try:
            from AppKit import (
                NSApp,
                NSApplicationActivationPolicyAccessory,
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorStationary,
            )
            import objc
            NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            ns_view = objc.objc_object(c_void_p=int(self.winId()))
            ns_win  = ns_view.window()
            if ns_win:
                ns_win.setLevel_(3)                  # NSFloatingWindowLevel
                ns_win.setCollectionBehavior_(
                    NSWindowCollectionBehaviorCanJoinAllSpaces
                    | NSWindowCollectionBehaviorStationary
                )
        except Exception as e:
            print(f"[float] {e}")

    # ── feeding interaction ───────────────────────────────────────────────────

    def _stamina_percent_rect(self) -> QRect:
        width, height = 50, 19
        center_x = self.width() // 2 + STAMINA_PERCENT_X_OFFSET
        return QRect(center_x - width // 2, STAMINA_PERCENT_Y, width, height)

    def _mood_emoji_rect(self) -> QRect:
        percent_rect = self._stamina_percent_rect()
        width, height = 40, 20
        return QRect(percent_rect.center().x() - width // 2, 0, width, height)

    def _feed_prompt_rect(self) -> QRect:
        width, height = 46, 39
        center_x = self.width() // 2 + STAMINA_PERCENT_X_OFFSET
        return QRect(center_x - width // 2, 0, width, height)

    def _music_prompt_rect(self) -> QRect:
        width, height = 120, 40
        center_x = self.width() // 2 + STAMINA_PERCENT_X_OFFSET
        return QRect(center_x - width // 2, 0, width, height)

    def _music_control_rects(self) -> tuple[QRect, QRect, QRect]:
        bubble = self._music_prompt_rect()
        body = QRect(bubble.x(), bubble.y(), bubble.width(), 32)
        part = body.width() // 3
        return (
            QRect(body.x(), body.y(), part, body.height()),
            QRect(body.x() + part, body.y(), part, body.height()),
            QRect(body.x() + part * 2, body.y(), body.width() - part * 2, body.height()),
        )

    def _ear_rects(self) -> tuple[QRect, QRect]:
        pet = self._current_pet_rect()
        if pet.isNull():
            return QRect(), QRect()
        top = pet.y() + round(pet.height() * 0.10)
        height = round(pet.height() * 0.31)
        return (
            QRect(pet.x() + round(pet.width() * 0.04), top, round(pet.width() * 0.30), height),
            QRect(pet.x() + round(pet.width() * 0.47), top, round(pet.width() * 0.30), height),
        )

    def _show_music_prompt(self):
        if (
            self._travel_state != "idle"
            or (self._acting and self._cur not in _MUSIC_STATES)
            or self._sleeping or self._walking or self._edge_side
            or (self._top_text() and self._cur not in _MUSIC_STATES)
        ):
            return
        self._hide_feed_prompt()
        self._music_prompt = True
        self._music_prompt_timer.start(MUSIC_PROMPT_MS)
        self.update()

    def _hide_music_prompt(self):
        if not hasattr(self, "_music_prompt_timer"):
            return
        self._music_prompt_timer.stop()
        if self._music_prompt:
            self._music_prompt = False
            self.update()
            self._schedule_wake_sleep()

    def _show_feed_prompt(self):
        if self._travel_state != "idle" or self._acting or self._sleeping or self._walking or self._edge_side:
            return
        self._hide_music_prompt()
        self._feed_prompt = True
        self._feed_prompt_timer.start(FEED_PROMPT_MS)
        self.update()

    def _hide_feed_prompt(self):
        if not hasattr(self, "_feed_prompt_timer"):
            return
        self._feed_prompt_timer.stop()
        if self._feed_prompt:
            self._feed_prompt = False
            self.update()
            self._schedule_wake_sleep()

    def _show_stamina_gain(self):
        self._change_stamina(STAMINA_GAIN, f"+{STAMINA_GAIN}")
        self._mood_emoji = "😊"
        self._mood_hide_timer.start(MOOD_DURATION_MS)
        self._go_idle()

    def _drain_stamina(self):
        if self._stamina > 0:
            self._change_stamina(-1, "-1")

    def _change_stamina(self, delta: int, feedback: str):
        old = self._stamina
        new = max(0, min(100, old + delta))
        self._stamina = new
        self.memory.set("stamina", new)
        self._stamina_anim_start = self._stamina_display
        self._stamina_anim_target = float(new)
        self._stamina_progress = 0.0
        self._stamina_feedback = "体力已满" if delta > 0 and old == 100 else feedback
        if new < WEAK_STAMINA_THRESHOLD:
            if not self._low_stamina_fx_timer.isActive():
                self._low_stamina_fx_timer.start()
        else:
            self._low_stamina_fx_timer.stop()
        self._stamina_hide_timer.stop()
        if self._stamina_anim_start == self._stamina_anim_target:
            self._stamina_progress = 1.0
            self._stamina_hide_timer.start(STAMINA_HOLD_MS)
        else:
            self._stamina_anim_timer.start()
        if new <= WEAK_STAMINA_THRESHOLD and self._cur != "eating_anim":
            self._enter_weak()
        elif old <= WEAK_STAMINA_THRESHOLD < new:
            self._go_idle()
        self.update()

    def _advance_stamina_gain(self):
        step = self._stamina_anim_timer.interval() / STAMINA_ANIM_MS
        self._stamina_progress = min(1.0, self._stamina_progress + step)
        eased = 1.0 - (1.0 - self._stamina_progress) ** 3
        self._stamina_display = (
            self._stamina_anim_start
            + (self._stamina_anim_target - self._stamina_anim_start) * eased
        )
        self.update()
        if self._stamina_progress >= 1.0:
            self._stamina_display = self._stamina_anim_target
            self._stamina_anim_timer.stop()
            self._stamina_hide_timer.start(STAMINA_HOLD_MS)

    def _hide_stamina_gain(self):
        if not hasattr(self, "_stamina_anim_timer"):
            return
        self._stamina_anim_timer.stop()
        self._stamina_hide_timer.stop()
        if self._stamina_feedback:
            self._stamina_display = self._stamina_anim_target
            self._stamina_feedback = ""
            self.update()

    def _top_text(self) -> str:
        if self._shy_speech:
            return self._shy_speech
        if self._cur in _MUSIC_STATES:
            return "✨ TXT ✨" if self._is_txt_song else (self._track_lbl or "♪ ·•·•·")
        return self._speech

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # At the edge, use the matching peek pose while keeping the ordinary
        # animation state intact underneath it.
        edge_px = self._edge_peek_pixmaps.get(self._edge_side) if self._edge_side else None
        if edge_px is not None:
            px_w, px_h = self._pixmap_logical_size(edge_px)
            if self._edge_side == "left":
                draw_x = 0
                draw_y = BUBBLE_H + (PET_SIZE - px_h) // 2
            elif self._edge_side == "right":
                draw_x = self.width() - px_w
                draw_y = BUBBLE_H + (PET_SIZE - px_h) // 2
            elif self._edge_side == "top":
                draw_x = (self.width() - px_w) // 2
                draw_y = 0
            else:
                draw_x = (self.width() - px_w) // 2
                draw_y = self.height() - px_h
            painter.drawPixmap(draw_x, draw_y, edge_px)
        elif self._seq and self._fidx < len(self._seq):
            px = self._seq[self._fidx]
            px_w, px_h = self._pixmap_logical_size(px)
            if self._cur in ("idle", "stamina_workout", "yawn") and px_h > PET_SIZE:
                draw_y = BUBBLE_H + PET_SIZE - 4 - px_h
            elif self._cur == "music_anim":
                draw_y = MUSIC_DRAW_Y
            elif self._cur == "sleep":
                draw_y = BUBBLE_H + 2
            else:
                draw_y = BUBBLE_H + (PET_SIZE - px_h) // 2
            painter.drawPixmap(
                (self.width() - px_w) // 2,
                draw_y,
                px,
            )

        if self._letter_pending and not self._envelope_px.isNull():
            painter.drawPixmap(self._letter_icon_rect(), self._envelope_px)

        if self._feed_prompt:
            rect = self._feed_prompt_rect()
            bubble = QRect(rect.x() + 3, rect.y(), rect.width() - 6, 30)
            tail_1 = QRect(rect.center().x() - 5, 28, 10, 8)
            tail_2 = QRect(rect.center().x() - 2, 35, 5, 4)
            painter.setPen(QColor(255, 255, 255, 185))
            painter.setBrush(QColor(255, 255, 255, 115))
            painter.drawEllipse(bubble)
            painter.drawEllipse(tail_1)
            painter.drawEllipse(tail_2)
            painter.setPen(QColor(255, 255, 255, 235))
            painter.setFont(QFont("Apple Color Emoji", 18))
            painter.drawText(bubble, Qt.AlignmentFlag.AlignCenter, "🥐")

        if self._music_prompt:
            rect = self._music_prompt_rect()
            body = QRect(rect.x(), rect.y(), rect.width(), 32)
            tail_1 = QRect(rect.center().x() - 5, 30, 10, 7)
            tail_2 = QRect(rect.center().x() - 2, 36, 5, 4)
            painter.setPen(QColor(255, 255, 255, 195))
            painter.setBrush(QColor(255, 255, 255, 130))
            painter.drawRoundedRect(body, 14, 14)
            painter.drawEllipse(tail_1)
            painter.drawEllipse(tail_2)
            previous_rect, toggle_rect, next_rect = self._music_control_rects()
            painter.setPen(QColor(53, 53, 58, 225))
            painter.setFont(QFont("Helvetica", 15, QFont.Weight.Bold))
            painter.drawText(previous_rect, Qt.AlignmentFlag.AlignCenter, "⏮")
            painter.drawText(toggle_rect, Qt.AlignmentFlag.AlignCenter, "⏸" if self._music_playing else "▶")
            painter.drawText(next_rect, Qt.AlignmentFlag.AlignCenter, "⏭")

        text = self._top_text()

        # 头顶仅保留一个可点击的小百分比；气泡或对话显示时暂时隐藏。
        stamina_value = max(0.0, min(100.0, self._stamina_display))
        if not self._sleeping and not self._edge_side and not self._feed_prompt and not self._music_prompt and not text:
            percent_rect = self._stamina_percent_rect()
            low_stamina = stamina_value < WEAK_STAMINA_THRESHOLD
            pulse = 0.0
            if low_stamina:
                pulse = (math.sin(time.monotonic() * math.tau / 1.1) + 1.0) / 2.0
            font_size = 9 + (round(4 * pulse) if low_stamina else 0)
            painter.setFont(QFont("Helvetica", font_size, QFont.Weight.Bold))
            painter.setPen(QColor(120, 120, 120, 150 + round(80 * pulse)))
            painter.drawText(percent_rect.translated(1, 2), Qt.AlignmentFlag.AlignCenter, f"{round(stamina_value)}%")
            painter.setPen(QColor(255, 255, 255, 190 + round(65 * pulse)))
            painter.drawText(percent_rect, Qt.AlignmentFlag.AlignCenter, f"{round(stamina_value)}%")

            mood_emoji = "😩" if low_stamina else self._mood_emoji
            if mood_emoji:
                emoji_rect = self._mood_emoji_rect()
                painter.setFont(QFont("Apple Color Emoji", 17))
                painter.drawText(emoji_rect, Qt.AlignmentFlag.AlignCenter, mood_emoji)

        if self._sleeping:
            rect = self._wake_button_rect()
            # Borderless translucent pill with a soft cool tint and top
            # highlight, keeping the lightweight Apple glass look.
            glass = QLinearGradient(rect.x(), rect.y(), rect.x(), rect.bottom())
            glass.setColorAt(0.0, QColor(255, 255, 255, 156))
            glass.setColorAt(0.48, QColor(249, 251, 255, 122))
            glass.setColorAt(1.0, QColor(239, 244, 252, 112))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glass)
            painter.drawRoundedRect(rect, 15, 15)
            highlight = rect.adjusted(3, 2, -3, -rect.height() // 2)
            painter.setBrush(QColor(255, 255, 255, 68))
            painter.drawRoundedRect(highlight, 12, 12)
            painter.setPen(QColor(69, 72, 80, 238))
            painter.setFont(QFont("Noteworthy", 11, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Wake Up")

        # speech bubble（优先级：害羞 > 音乐 > 普通）
        if text and not self._feed_prompt and not self._music_prompt:
            font = QFont("Helvetica", 13, QFont.Weight.Bold)
            painter.setFont(font)
            fm  = QFontMetrics(font)
            tw  = fm.horizontalAdvance(text)
            th  = fm.height()
            pad = 8
            bubble_max_w = self.width() - 8
            need_scroll = (
                self._cur in _MUSIC_STATES
                and not self._is_txt_song
                and tw > bubble_max_w - pad * 2
            )
            if need_scroll:
                bw = bubble_max_w
                bx = (self.width() - bw) // 2
                bh = th + pad
                painter.setBrush(QColor(20, 20, 20, 185))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bx, 4, bw, bh, 10, 10)
                painter.setClipRect(bx + pad, 2, bw - pad * 2, bh + 4)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(bx + pad - self._scroll_offset, 4 + th, text)
                painter.setClipping(False)
            else:
                bx = (self.width() - tw) // 2 - pad
                bw = tw + pad * 2
                bh = th + pad
                painter.setBrush(QColor(20, 20, 20, 185))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bx, 4, bw, bh, 10, 10)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(bx + pad, 4 + th, text)

        painter.end()

    # ── mouse ─────────────────────────────────────────────────────────────────

    def _current_pet_rect(self) -> QRect:
        px = self._seq[self._fidx] if self._seq else None
        if px is None:
            return QRect()
        pw, ph = self._pixmap_logical_size(px)
        if self._cur in ("idle", "stamina_workout") and ph > PET_SIZE:
            img_y = BUBBLE_H + PET_SIZE - 4 - ph
        elif self._cur == "music_anim":
            img_y = MUSIC_DRAW_Y
        elif self._cur == "sleep":
            img_y = BUBBLE_H + 2
        else:
            img_y = BUBBLE_H + (PET_SIZE - ph) // 2
        return QRect((self.width() - pw) // 2, img_y, pw, ph)

    def _paw_hit_rects(self):
        pet = self._current_pet_rect()
        if pet.isNull():
            return ()
        return (
            QRect(pet.x() + round(pet.width() * 0.14), pet.y() + round(pet.height() * 0.64),
                  round(pet.width() * 0.28), round(pet.height() * 0.21)),
            QRect(pet.x() + round(pet.width() * 0.53), pet.y() + round(pet.height() * 0.64),
                  round(pet.width() * 0.25), round(pet.height() * 0.21)),
        )

    def _can_click_paw(self, point):
        return (
            self._cur == "idle" and not self._idle_pose and not self._edge_side
            and any(rect.contains(point) for rect in self._paw_hit_rects())
        )

    def _wake_button_rect(self):
        width, height = 90, 25
        return QRect((self.width() - width) // 2, 43, width, height)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self._show_exit_menu(e.globalPosition().toPoint())
            e.accept()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            global_pos = e.globalPosition().toPoint()
            self._drag_pos = global_pos - self.frameGeometry().topLeft()
            self._drag_origin_global = global_pos
            self._drag_can_trigger_pose = (
                self._travel_state == "idle"
                and self._current_pet_rect().contains(e.position().toPoint())
            )
            self._lift_active = False
            self._lift_resume_music = self._music_playing and self._cur in _MUSIC_STATES
            self._click_pos = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            global_pos = e.globalPosition().toPoint()
            if self._drag_can_trigger_pose and not self._lift_active:
                vertical_delta = global_pos.y() - self._drag_origin_global.y()
                if vertical_delta <= -LIFT_DRAG_THRESHOLD_PX and "lift" in self._seqs:
                    self._lift_active = True
                    self._play("lift", loop=True, speech="")
                elif vertical_delta >= LIFT_DRAG_THRESHOLD_PX and "lift" in self._seqs:
                    self._lift_active = True
                    self._play("lift", loop=True, speech="")
            target = global_pos - self._drag_pos
            # A deliberate user drag establishes a new location, so an action
            # started during that drag must not snap back to the old edge.
            if target != self.pos():
                self._edge_return = None
            self._move_with_edge_detection(target.x(), target.y())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._drag_pos:
            moved = (
                e.globalPosition().toPoint() - self._drag_origin_global
            ).manhattanLength()
            click_pos = self._click_pos
            sleep_drag = self._sleeping and moved >= 5
            if moved < 5 and self._sleeping:
                if self._wake_button_rect().contains(click_pos):
                    self._wake_up()
            elif sleep_drag:
                # Keep the sleeping state during a drag. Vertical drags may
                # show the lift pose, then sleep resumes on release.
                pass
            elif moved < 5 and self._letter_pending and self._letter_icon_rect().contains(click_pos):
                self._reset_inactivity()
                self._open_travel_letter()
            elif moved < 5 and self._music_prompt:
                previous_rect, toggle_rect, next_rect = self._music_control_rects()
                self._hide_music_prompt()
                self._reset_inactivity()
                if previous_rect.contains(click_pos):
                    self._act_previous()
                elif toggle_rect.contains(click_pos):
                    self._act_music()
                elif next_rect.contains(click_pos):
                    self._act_next()
            elif moved < 5 and self._feed_prompt and self._feed_prompt_rect().contains(click_pos):
                self._hide_feed_prompt()
                self._reset_inactivity()
                self._start_action("eating")
            elif moved < 5 and self._can_click_paw(click_pos):
                self._reset_inactivity()
                self._act_flower_gift()
            elif (
                moved < 5
                and not self._feed_prompt
                and not self._top_text()
                and self._stamina_percent_rect().contains(click_pos)
            ):
                self._reset_inactivity()
                self._show_feed_prompt()
            elif (
                moved < 5
                and not self._feed_prompt
                and (not self._top_text() or self._cur in _MUSIC_STATES)
                and any(rect.contains(click_pos) for rect in self._ear_rects())
            ):
                self._reset_inactivity()
                self._show_music_prompt()
            elif moved < 5 and self._current_pet_rect().contains(click_pos):
                self._reset_inactivity()
            elif moved < 5:
                self._hide_feed_prompt()
                self._hide_music_prompt()
            else:
                self._reset_inactivity()
        self._drag_pos = None
        self._drag_origin_global = None
        self._drag_can_trigger_pose = False
        if self._lift_active:
            self._lift_active = False
            if self._sleeping:
                self._enter_sleep()
            elif self._lift_resume_music and self._music_playing:
                self._play("music_anim", loop=True, speech="")
                QTimer.singleShot(600, self._poll_track)
            else:
                self._go_idle()
        elif sleep_drag and self._sleeping:
            self._enter_sleep()
        self._lift_resume_music = False

    def closeEvent(self, e):
        if self._keyboard_monitor is not None:
            NSEvent.removeMonitor_(self._keyboard_monitor)
            self._keyboard_monitor = None
        e.accept()

    def _show_exit_menu(self, global_pos):
        menu = QMenu(self)
        exit_action = menu.addAction("退出")
        if menu.exec(global_pos) is exit_action:
            self.close()
            QApplication.instance().quit()

    # ── actions ───────────────────────────────────────────────────────────────

    def _start_action(self, key: str):
        self._reset_inactivity()
        if key == "eating":
            self.memory.increment("croissant_count", "interaction_count")
        cfg = ACTION_CFG[key]
        ok  = self._play(cfg["anim"], loop=cfg["loop"], speech=cfg["speech"])
        if ok and cfg["dur"] > 0:
            callback = self._show_stamina_gain if key == "eating" else self._go_idle
            QTimer.singleShot(cfg["dur"], callback)

    def _act_flower_gift(self):
        if (self._travel_state != "idle" or self._sleeping or self._walking
                or self._edge_side or self._acting):
            return
        cfg = ACTION_CFG["flower_gift"]
        if self._play(cfg["anim"], loop=cfg["loop"], speech=cfg["speech"]):
            self._reset_inactivity()
            QTimer.singleShot(cfg["dur"], self._go_idle)

    def _act_workout(self):
        self._reset_inactivity()
        self.memory.increment("interaction_count")
        if "workout" in self._seqs:
            speech = random.choice(_WORKOUT_SPEECHES)
            self._play("workout", loop=True, speech=speech)
            QTimer.singleShot(6_000, self._finish_workout_action)
            if random.random() < SHY_PROB_WORKOUT:
                QTimer.singleShot(8_700, self._trigger_shy)
        else:
            self._speech = "💪"
            self.update()
            QTimer.singleShot(3_000, lambda: self._clear_timed_bubble("💪"))
            if random.random() < SHY_PROB_WORKOUT:
                QTimer.singleShot(3_300, self._trigger_shy)
        print("[workout] 健身开始！")

    def _finish_workout_action(self):
        if self._cur != "workout" or not self._acting:
            return
        if "workout_after" not in self._seqs:
            self._go_idle()
            return
        self._play("workout_after", loop=False, speech="")

    def _act_music(self):
        self.music.open_music()
        self._music_playing = self.music.toggle()
        if self._music_playing:
            self._play("music_anim", loop=True, speech="")
            QTimer.singleShot(600, self._poll_track)
        else:
            self._go_idle()

    def _poll_track(self):
        if self._cur not in _MUSIC_STATES:
            return
        if not self.music.is_playing():
            self._music_playing = False
            self._go_idle()
            return
        artist        = self.music.current_artist()
        title         = self.music.current_track_name()
        prev_is_txt   = self._is_txt_song
        self._is_txt_song = _is_txt_content(artist) or _is_txt_content(title)
        if self._is_txt_song and not prev_is_txt and random.random() < SHY_PROB_TXT:
            self._trigger_shy(animate=False)
        t = self.music.current_track()
        self._track_lbl = f"♪ {t}"
        self.update()
        QTimer.singleShot(8_000, self._poll_track)

    def _act_previous(self):
        self.music.open_music()
        self.music.prev_track()
        if self._cur in _MUSIC_STATES:
            QTimer.singleShot(700, self._poll_track)

    def _act_next(self):
        self.music.open_music()
        self.music.next_track()
        if self._cur in _MUSIC_STATES:
            QTimer.singleShot(700, self._poll_track)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    instance_lock = QLockFile(
        os.path.join(tempfile.gettempdir(), "songnyang-desktop-pet.lock")
    )
    # Keep Qt's stale-lock detection enabled so a crash/forced quit cannot
    # block every future launch of the pet.
    if not instance_lock.tryLock(0):
        print("[instance] 松喵喵已经在运行，忽略重复启动。")
        return

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    pet = PetWidget()
    pet.show()
    exit_code = app.exec()
    instance_lock.unlock()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
