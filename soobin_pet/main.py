#!/usr/bin/env python3
"""Standalone CHOI YONG MEONG desktop pet with feeding and travel-letter actions."""

import argparse
import glob
import json
import math
import os
import random
import sys
import tempfile
import time
from datetime import date, datetime, timedelta

from AppKit import NSEvent, NSEventMaskKeyDown
from PyQt6.QtCore import QPoint, Qt, QTimer, QRect, QLockFile
from PyQt6.QtGui import QColor, QCursor, QFont, QFontMetrics, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from letter import LetterDialog
from macos_window import show_on_all_spaces
from music import MusicController
from quotes import random_letter_quote


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(ROOT_DIR, "assets")
FRAMES_DIR = os.path.join(ASSET_DIR, "frames")
STATE_PATH = os.path.join(ROOT_DIR, "data", "pet_state.json")
if getattr(sys, "frozen", False):
    STATE_PATH = os.path.join(
        os.path.expanduser("~"), "Library", "Application Support",
        "TXT Desktop Pets", "Soobin", "pet_state.json",
    )
TRAVEL_SECONDS = 3_000
TRAVEL_FRAME_INTERVAL_MS = 250
FEED_FRAME_INTERVAL_MS = 780
FEED_DURATION_MS = 6_000
FEED_PROMPT_MS = 6_000
GAME_PROMPT_MS = 8_000
MUSIC_POLL_MS = 5_000
PLAY_GAME_FRAME_INTERVAL_MS = 650
PLAY_GAME_SEQUENCE = (0, 1, 2, 3, 2, 1)
CLICK_FEEDBACK_MS = 900
STAMINA_INTERVAL_MS = 10 * 60 * 1_000
MOOD_INTERVAL_MS = 10 * 60 * 1_000
MOOD_DURATION_MS = 30 * 1_000
IDLE_RESET_SECONDS = 30 * 60
WALK_CHECK_MS = 5 * 60 * 1_000
WALK_PROBABILITY = 0.20
WALK_DISTANCE_MIN = 50
WALK_DISTANCE_MAX = 200
WALK_STEP_PX = 2
WALK_STEP_MS = 40
WALK_FRAME_INTERVAL_MS = 300
LIFT_FRAME_INTERVAL_MS = 160
ICON_RECT = QRect(94, 126, 38, 26)
BASE_WINDOW_SIZE = (146, 166)
IDLE_DRAW_SIZE = 132
IDLE_DRAW_Y = 34
IDLE_VISIBLE_BASELINE_Y = 163
WAVE_DRAW_HEIGHT = 154
WAVE_VISIBLE_BOTTOM_RATIO = 1529 / 1672
WEAK_SOURCE_RECT = QRect(78, 439, 1099, 530)
WEAK_DRAW_WIDTH = 129
WEAK_VISIBLE_BASELINE_Y = 151
WALK_DRAW_HEIGHT = 130
TRAVEL_DRAW_HEIGHT = 129
FEED_WINDOW_SIZE = (184, BASE_WINDOW_SIZE[1])
STAMINA_RECT = QRect(48, 19, 50, 19)
MOOD_RECT = QRect(53, 0, 40, 20)
LOW_STAMINA_FX_MS = 80
FEED_PROMPT_RECT = QRect(53, 0, 40, 34)
GAME_PROMPT_RECT = QRect(48, 0, 48, 40)
GAME_PROMPT_DRAW_RECT = QRect(32, -18, 80, 80)
GAME_BELLY_RECT = QRect(40, 114, 70, 31)
MOODS = ("😊", "😎", "😌", "😉", "😈", "😐", "😪")
DRAG_THRESHOLD_PX = 5
SLEEP_HOUR = 23
SLEEP_FRAME_INTERVAL_MS = 700
WEAK_FRAME_INTERVAL_MS = 700
EDGE_PEEK_TRIGGER_PX = 24
EDGE_PEEK_DIVIDER_RATIO = 380 / 1254
EDGE_PEEK_DRAW_RECT = QRect(8, 23, 152, 152)
EDGE_PEEK_WINDOW_SIZE = (168, 166)


class SoobinPet(QWidget):
    def __init__(self, args):
        super().__init__()
        self._trigger_seconds = args.trigger_minutes * 60
        self._away_seconds = args.away_seconds
        self._last_activity = time.time()
        self._work_start = self._last_activity
        self._travel_state = "idle"
        self._letter_pending = False
        self._letter_dialog = None
        self._stamina, self._saved_position = self._load_state()
        self._user_position = self._saved_position is not None
        self._drag_offset = None
        self._drag_origin = None
        self._press_pos = QPoint()
        self._dragged = False
        self._feed_prompt = False
        self._game_prompt = False
        self._game_prompt_image = QPixmap()
        self._game_frame_index = 0
        self._game_frames = []
        self._game_active = False
        self._music_playing = False
        self.music = MusicController()
        self._stamina_feedback = ""
        self._mood = ""
        self._sleeping = False
        self._sleep_suppressed_until = None
        self._click_pose_active = False
        self._weak = QPixmap()
        self._wave = QPixmap()
        self._edge_peek = QPixmap()
        self._edge_peek_right = QPixmap()
        self._edge_peek_top = QPixmap()
        self._edge_peek_bottom = QPixmap()
        self._edge_side = None
        self._frame_index = 0
        self._weak_frames = []
        self._weak_frame_index = 0
        self._travel_frames = []
        self._travel_frames_left = []
        self._walk_frames = []
        self._walk_frames_left = []
        self._walk_active_frames = []
        self._walking = False
        self._lift_frames = []
        self._lift_animation_active = False
        self._walk_target_x = None
        self._walk_direction = 1
        self._walk_frame_index = 0
        self._feeding_frames = []
        self._sleep_frames = []
        self._feeding_active = False
        self._feeding_index = 0
        self._animation_frames = []
        self._active_screen = None
        self._travel_return_pos = None
        self._travel_return_screen = None
        self._current_image = QPixmap()
        self._speech = ""
        self._key_monitor = None
        self._envelope_icon = QPixmap()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setFixedSize(*BASE_WINDOW_SIZE)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._load_assets()
        LetterDialog.preload_frames()
        screen = self._screen_under_cursor()
        self._active_screen = screen
        if screen:
            saved = self._saved_position
            saved_screen = (QApplication.screenAt(QPoint(saved[0] + self.width() // 2,
                                                         saved[1] + self.height() // 2))
                            if saved else None)
            if saved and saved_screen:
                restored_pos = self._clamp_to_screen(QPoint(*saved), saved_screen, physical=True)
                self.move(restored_pos)
                if (restored_pos.x(), restored_pos.y()) != saved:
                    self._save_state()
            else:
                self.move(self._anchor_on_screen(screen))
            if saved and not saved_screen:
                self._user_position = False
        QTimer.singleShot(0, self._settle_edge_peek)

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._next_frame)
        self._game_frame_timer = QTimer(self)
        self._game_frame_timer.timeout.connect(self._advance_game_frame)
        self._game_frame_timer.start(PLAY_GAME_FRAME_INTERVAL_MS)
        self._music_timer = QTimer(self)
        self._music_timer.timeout.connect(self._sync_music_state)
        self._music_timer.start(MUSIC_POLL_MS)
        self._weak_frame_timer = QTimer(self)
        self._weak_frame_timer.timeout.connect(self._advance_weak_frame)
        self._weak_frame_timer.start(WEAK_FRAME_INTERVAL_MS)
        self._low_stamina_fx_timer = QTimer(self)
        self._low_stamina_fx_timer.setInterval(LOW_STAMINA_FX_MS)
        self._low_stamina_fx_timer.timeout.connect(self.update)
        if self._stamina <= 20:
            self._low_stamina_fx_timer.start()
        self._feeding_timer = QTimer(self)
        self._feeding_timer.setSingleShot(True)
        self._feeding_timer.timeout.connect(self._advance_feeding)
        self._feed_prompt_timer = QTimer(self)
        self._feed_prompt_timer.setSingleShot(True)
        self._feed_prompt_timer.timeout.connect(self._hide_feed_prompt)
        self._game_prompt_timer = QTimer(self)
        self._game_prompt_timer.setSingleShot(True)
        self._game_prompt_timer.timeout.connect(self._hide_game_prompt)
        self._click_feedback_timer = QTimer(self)
        self._click_feedback_timer.setSingleShot(True)
        self._click_feedback_timer.timeout.connect(self._end_click_feedback)
        self._stamina_timer = QTimer(self)
        self._stamina_timer.timeout.connect(self._drain_stamina)
        self._stamina_timer.start(STAMINA_INTERVAL_MS)
        self._mood_timer = QTimer(self)
        self._mood_timer.timeout.connect(self._show_random_mood)
        self._mood_timer.start(MOOD_INTERVAL_MS)
        self._mood_hide_timer = QTimer(self)
        self._mood_hide_timer.setSingleShot(True)
        self._mood_hide_timer.timeout.connect(self._hide_mood)
        self._stamina_feedback_timer = QTimer(self)
        self._stamina_feedback_timer.setSingleShot(True)
        self._stamina_feedback_timer.timeout.connect(self._hide_stamina_feedback)
        self._activity_timer = QTimer(self)
        self._activity_timer.timeout.connect(self._check_activity)
        self._activity_timer.start(1000)
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._check_random_walk)
        self._walk_timer.start(WALK_CHECK_MS)
        self._walk_step_timer = QTimer(self)
        self._walk_step_timer.timeout.connect(self._walk_step)
        self._walk_frame_timer = QTimer(self)
        self._walk_frame_timer.timeout.connect(self._advance_walk_frame)
        self._screen_timer = QTimer(self)
        self._screen_timer.timeout.connect(self._sync_screen)
        self._screen_timer.start(350)
        self._sleep_check_timer = QTimer(self)
        self._sleep_check_timer.timeout.connect(self._check_sleep)
        self._sleep_check_timer.start(60_000)
        self._start_keyboard_monitor()
        self._check_sleep()
        QTimer.singleShot(0, self._sync_music_state)

        if args.demo_now:
            QTimer.singleShot(900, self._start_trip)

    def _load_assets(self):
        idle_path = os.path.join(ASSET_DIR, "idle.png")
        if os.path.isfile(idle_path):
            self._idle = QPixmap(idle_path)
        else:
            self._idle = QPixmap()
        self._wave = QPixmap(os.path.join(ASSET_DIR, "poses", "wave.png"))
        self._edge_peek = QPixmap(os.path.join(ASSET_DIR, "edge_peek", "peek.png"))
        self._weak = QPixmap(os.path.join(ASSET_DIR, "weak.png"))
        self._game_prompt_image = QPixmap(os.path.join(ASSET_DIR, "game_prompt.png"))
        game_folder = os.path.join(FRAMES_DIR, "play_game")
        game_paths = sorted(
            path for path in glob.glob(os.path.join(game_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._game_frames = [QPixmap(path) for path in game_paths]
        self._game_frames = [frame for frame in self._game_frames if not frame.isNull()]
        weak_folder = os.path.join(FRAMES_DIR, "weak")
        weak_paths = sorted(
            path for path in glob.glob(os.path.join(weak_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._weak_frames = [QPixmap(path) for path in weak_paths]
        self._weak_frames = [
            frame.copy(WEAK_SOURCE_RECT)
            if frame.rect().contains(WEAK_SOURCE_RECT) else frame
            for frame in self._weak_frames
            if not frame.isNull()
        ]
        envelope_path = os.path.join(ASSET_DIR, "letter", "envelope.png")
        if os.path.isfile(envelope_path):
            self._envelope_icon = QPixmap(envelope_path)
        travel_folder = os.path.join(FRAMES_DIR, "travel_walk")
        travel_paths = sorted(
            path for path in glob.glob(os.path.join(travel_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._travel_frames = [QPixmap(path) for path in travel_paths]
        self._travel_frames = [frame for frame in self._travel_frames if not frame.isNull()]
        walk_folder = os.path.join(FRAMES_DIR, "walk")
        walk_paths = sorted(
            path for path in glob.glob(os.path.join(walk_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._walk_frames = [QPixmap(path) for path in walk_paths]
        self._walk_frames = [frame for frame in self._walk_frames if not frame.isNull()]
        lift_folder = os.path.join(FRAMES_DIR, "lift")
        lift_paths = sorted(
            path for path in glob.glob(os.path.join(lift_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._lift_frames = [QPixmap(path) for path in lift_paths]
        self._lift_frames = [frame for frame in self._lift_frames if not frame.isNull()]
        feeding_folder = os.path.join(FRAMES_DIR, "feeding_anim")
        feeding_paths = sorted(
            path for path in glob.glob(os.path.join(feeding_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._feeding_frames = [QPixmap(path) for path in feeding_paths]
        self._feeding_frames = [frame for frame in self._feeding_frames if not frame.isNull()]
        sleep_folder = os.path.join(FRAMES_DIR, "sleep")
        sleep_paths = sorted(
            path for path in glob.glob(os.path.join(sleep_folder, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        self._sleep_frames = [QPixmap(path) for path in sleep_paths]
        self._sleep_frames = [frame for frame in self._sleep_frames if not frame.isNull()]
        mirror = QTransform().scale(-1, 1)
        if not self._edge_peek.isNull():
            self._edge_peek_right = self._edge_peek.transformed(mirror)
            # 松喵喵的上、下贴边图分别是左贴边图旋转 90°、270°。
            top = self._edge_peek.transformed(QTransform().rotate(90))
            bottom = self._edge_peek.transformed(QTransform().rotate(270))
            # 跨过原图墙带末端的 2 像素黑色分界线。
            wall_height = round(top.height() * EDGE_PEEK_DIVIDER_RATIO) + 2
            # 像松喵喵一样裁掉墙带，只让猫身贴齐真实屏幕边缘。
            self._edge_peek_top = top.copy(
                0, wall_height, top.width(), top.height() - wall_height
            )
            self._edge_peek_bottom = bottom.copy(
                0, 0, bottom.width(), bottom.height() - wall_height
            )
        self._travel_frames_left = [frame.transformed(mirror) for frame in self._travel_frames]
        self._walk_frames_left = [frame.transformed(mirror) for frame in self._walk_frames]
        self._weak_image_keys = {frame.cacheKey() for frame in self._weak_frames}
        if not self._weak.isNull():
            self._weak_image_keys.add(self._weak.cacheKey())
        self._standing_canvas_keys = {
            frame.cacheKey()
            for frame in [self._idle, *self._lift_frames, *self._game_frames]
            if not frame.isNull()
        }
        self._current_image = self._resting_image()

    @staticmethod
    def _load_state():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as state_file:
                state = json.load(state_file)
            stamina = max(0, min(100, int(state.get("stamina", 100))))
            position = state.get("position")
            if (isinstance(position, list) and len(position) == 2
                    and all(isinstance(value, int) for value in position)):
                return stamina, (position[0], position[1])
            return stamina, None
        except (OSError, ValueError, TypeError):
            return 100, None

    def _save_state(self):
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        state = {
            "stamina": self._stamina,
            "position": [self.x(), self.y()],
        }
        temporary_path = STATE_PATH + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as state_file:
            json.dump(state, state_file, ensure_ascii=False, indent=2)
        os.replace(temporary_path, STATE_PATH)

    def _resting_image(self):
        if self._edge_side == "left" and not self._edge_peek.isNull():
            return self._edge_peek
        if self._edge_side == "right" and not self._edge_peek_right.isNull():
            return self._edge_peek_right
        if self._edge_side == "top" and not self._edge_peek_top.isNull():
            return self._edge_peek_top
        if self._edge_side == "bottom" and not self._edge_peek_bottom.isNull():
            return self._edge_peek_bottom
        if self._game_active and self._game_frames:
            frame_index = PLAY_GAME_SEQUENCE[
                self._game_frame_index % len(PLAY_GAME_SEQUENCE)
            ]
            return self._game_frames[frame_index]
        if self._stamina <= 20:
            if self._weak_frames:
                return self._weak_frames[self._weak_frame_index % len(self._weak_frames)]
            if not self._weak.isNull():
                return self._weak
        return self._idle

    def _advance_weak_frame(self):
        if (self._stamina > 20 or not self._weak_frames
                or self._current_image.cacheKey() not in {frame.cacheKey() for frame in self._weak_frames}):
            return
        self._weak_frame_index = (self._weak_frame_index + 1) % len(self._weak_frames)
        self._current_image = self._weak_frames[self._weak_frame_index]
        self.update()

    def _advance_game_frame(self):
        if (not self._game_active or not self._music_playing or not self._game_frames
                or self._current_image.cacheKey() not in {frame.cacheKey() for frame in self._game_frames}):
            return
        self._game_frame_index = (
            self._game_frame_index + 1
        ) % len(PLAY_GAME_SEQUENCE)
        frame_index = PLAY_GAME_SEQUENCE[self._game_frame_index]
        self._current_image = self._game_frames[frame_index]
        self.update()

    def _sync_music_state(self):
        playing = self.music.is_playing()
        if playing == self._music_playing:
            return
        self._music_playing = playing
        self._game_active = playing and bool(self._game_frames)
        if playing:
            self._hide_game_prompt()
            self._hide_feed_prompt()
            self._hide_mood()
            if self._sleeping:
                self._wake_from_sleep()
            if self._walking:
                self._stop_random_walk()
            self._game_frame_index = 0
            if not self._feeding_active and self._travel_state == "idle":
                self._current_image = self._resting_image()
        elif any(self._current_image.cacheKey() == frame.cacheKey()
                 for frame in self._game_frames):
            self._current_image = self._resting_image()
        self.update()

    def _show_game_prompt(self):
        if (self._travel_state != "idle" or self._music_playing or self._game_prompt
                or self._sleeping or self._walking or self._feeding_active
                or self._feed_prompt or self._drag_offset is not None
                or self._stamina <= 20 or self._edge_side is not None):
            return
        self._hide_mood()
        self._game_prompt = True
        self._game_prompt_timer.start(GAME_PROMPT_MS)
        self.update()

    def _hide_game_prompt(self):
        if not hasattr(self, "_game_prompt_timer"):
            return
        self._game_prompt_timer.stop()
        if self._game_prompt:
            self._game_prompt = False
            self.update()

    def _open_music_from_game_prompt(self):
        self._hide_game_prompt()
        self.music.open_music()
        self._record_activity()
        self._sync_music_state()

    @staticmethod
    def _screen_under_cursor():
        return QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()

    def _anchor_on_screen(self, screen):
        bounds = screen.availableGeometry()
        return QPoint(bounds.right() - self.width() - 36,
                      bounds.bottom() - self.height() - 42)

    def _clamp_to_screen(self, position, screen, physical=False):
        bounds = screen.geometry() if physical else screen.availableGeometry()
        max_x = max(bounds.left(), bounds.right() - self.width() + 1)
        max_y = max(bounds.top(), bounds.bottom() - self.height() + 1)
        return QPoint(min(max(position.x(), bounds.left()), max_x),
                      min(max(position.y(), bounds.top()), max_y))

    def _position_on_screen(self, previous_screen, target_screen):
        if not self._user_position or previous_screen is None:
            return self._anchor_on_screen(target_screen)
        previous = previous_screen.availableGeometry()
        target = target_screen.availableGeometry()
        previous_x_range = max(1, previous.width() - self.width())
        previous_y_range = max(1, previous.height() - self.height())
        target_x_range = max(0, target.width() - self.width())
        target_y_range = max(0, target.height() - self.height())
        x_ratio = min(1.0, max(0.0, (self.x() - previous.left()) / previous_x_range))
        y_ratio = min(1.0, max(0.0, (self.y() - previous.top()) / previous_y_range))
        target_position = QPoint(
            target.left() + round(x_ratio * target_x_range),
            target.top() + round(y_ratio * target_y_range),
        )
        return self._clamp_to_screen(target_position, target_screen)

    def _screen_for_pet(self):
        return (QApplication.screenAt(self.geometry().center())
                or self._active_screen or self._screen_under_cursor())

    def _clear_edge_peek(self):
        was_edge_peeking = self._edge_side is not None
        self._edge_side = None
        if self.size().width() != BASE_WINDOW_SIZE[0] or self.size().height() != BASE_WINDOW_SIZE[1]:
            self.setFixedSize(*BASE_WINDOW_SIZE)
        if (was_edge_peeking and self._travel_state in ("idle", "letter_waiting")
                and not self._walking and not self._feeding_active and not self._click_pose_active):
            self._current_image = self._resting_image()
            self.update()

    def _bring_edge_pet_onscreen(self, extra_width=0):
        if self._edge_side is None:
            return
        screen = self._screen_for_pet()
        if screen is None:
            return
        bounds = screen.geometry()
        x, y = self.x(), self.y()
        if self._edge_side == "left":
            x = bounds.left() + extra_width
        elif self._edge_side == "right":
            x = bounds.right() - self.width() + 1
        elif self._edge_side == "top":
            y = bounds.top()
        else:
            y = bounds.bottom() - self.height() + 1
        self.move(x, y)
        self._clear_edge_peek()

    def _settle_edge_peek(self):
        if (self._edge_peek.isNull() or self._travel_state not in ("idle", "letter_waiting")
                or self._drag_offset is not None or self._feeding_active
                or self._sleeping or self._walking or self._click_pose_active):
            return
        screen = self._screen_for_pet()
        if screen is None:
            return
        bounds = screen.geometry()
        distances = {
            "left": self.x() - bounds.left(),
            "right": bounds.right() + 1 - (self.x() + self.width()),
            "top": self.y() - bounds.top(),
            "bottom": bounds.bottom() + 1 - (self.y() + self.height()),
        }
        side = min(distances, key=distances.get)
        if distances[side] > EDGE_PEEK_TRIGGER_PX:
            side = None

        if side is None:
            self._clear_edge_peek()
            return

        divider = round(EDGE_PEEK_DRAW_RECT.width() * EDGE_PEEK_DIVIDER_RATIO)
        if side == "right":
            divider_x = (EDGE_PEEK_DRAW_RECT.x() + EDGE_PEEK_DRAW_RECT.width()
                         - divider)
            target_x = bounds.right() + 1 - divider_x
            image = self._edge_peek_right
            target_y = self.y()
        elif side == "left":
            target_x = bounds.left() - EDGE_PEEK_DRAW_RECT.x() - divider
            target_y = self.y()
            image = self._edge_peek
        elif side == "top":
            target_x = max(bounds.left(), min(
                self.x(), bounds.right() - EDGE_PEEK_WINDOW_SIZE[0] + 1
            ))
            target_y = bounds.top()
            image = self._edge_peek_top
        else:
            target_x = max(bounds.left(), min(
                self.x(), bounds.right() - EDGE_PEEK_WINDOW_SIZE[0] + 1
            ))
            target_y = bounds.bottom() - EDGE_PEEK_WINDOW_SIZE[1] + 1
            image = self._edge_peek_bottom
        self._edge_side = side
        self._current_image = image
        self._active_screen = screen
        self.setFixedSize(*EDGE_PEEK_WINDOW_SIZE)
        self.move(target_x, target_y)
        self.update()

    def _sync_screen(self):
        screen = self._screen_under_cursor()
        pet_screen = QApplication.screenAt(self.geometry().center())
        screens = QApplication.screens()
        if (self._user_position and self._travel_return_screen in screens
                and self._travel_state in ("leaving", "away", "returning")):
            self._active_screen = self._travel_return_screen
            return
        if self._drag_offset is not None:
            self._active_screen = pet_screen or screen or self._active_screen
            return
        if screen is None:
            return
        if pet_screen is screen:
            self._active_screen = screen
            return
        if self._walking:
            self._stop_random_walk()
        previous_screen = pet_screen or self._active_screen
        self._active_screen = screen
        self._clear_edge_peek()
        self.move(self._position_on_screen(previous_screen, screen))
        if self._user_position:
            self._save_state()
        if self._letter_dialog and self._letter_dialog.isVisible():
            self._position_letter_dialog(self._letter_dialog, screen)

    def showEvent(self, event):
        super().showEvent(event)
        show_on_all_spaces(self)

    def _start_keyboard_monitor(self):
        try:
            self._key_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, lambda _event: self._record_activity()
            )
        except Exception as exc:
            print(f"[soobin] 全局键盘活动监听不可用：{exc}")

    def _record_activity(self):
        now = time.time()
        if now - self._last_activity >= IDLE_RESET_SECONDS:
            self._work_start = now
        self._last_activity = now

    def _drain_stamina(self):
        if self._stamina > 0:
            self._change_stamina(-1)

    def _change_stamina(self, delta):
        old_stamina = self._stamina
        self._stamina = max(0, min(100, self._stamina + delta))
        if old_stamina > 20 >= self._stamina:
            self._weak_frame_index = 0
        if delta > 0:
            self._stamina_feedback = ("体力已满" if old_stamina == 100
                                      else f"+{self._stamina - old_stamina}")
            self._stamina_feedback_timer.start(1_300)
        if self._stamina <= 20:
            self._hide_mood()
            if self._walking:
                self._stop_random_walk()
            if not self._low_stamina_fx_timer.isActive():
                self._low_stamina_fx_timer.start()
        else:
            self._low_stamina_fx_timer.stop()
        self._save_state()
        if (self._travel_state == "idle" and not self._walking
                and not self._feeding_active and not self._click_pose_active):
            self._current_image = self._resting_image()
        self.update()

    def _hide_stamina_feedback(self):
        if self._stamina_feedback:
            self._stamina_feedback = ""
            self.update()

    def _show_random_mood(self):
        if (self._travel_state == "idle" and not self._walking and self._stamina > 20
                and not self._feeding_active and not self._feed_prompt
                and not self._music_playing):
            self._mood = random.choice(MOODS)
            self._mood_hide_timer.start(MOOD_DURATION_MS)
            self.update()

    def _hide_mood(self):
        if self._mood:
            self._mood = ""
            self.update()

    def _show_feed_prompt(self):
        if (self._travel_state != "idle" or self._feeding_active
                or self._drag_offset is not None or self._edge_side is not None):
            return
        self._hide_mood()
        self._feed_prompt = True
        self._feed_prompt_timer.start(FEED_PROMPT_MS)
        self.update()

    def _hide_feed_prompt(self):
        self._feed_prompt_timer.stop()
        if self._feed_prompt:
            self._feed_prompt = False
            self.update()

    def _show_click_feedback(self):
        if (self._sleeping or self._travel_state != "idle" or self._feeding_active or self._feed_prompt
                or self._drag_offset is not None or self._click_pose_active or self._music_playing):
            return
        self._hide_feed_prompt()
        self._hide_mood()
        if not self._wave.isNull():
            self._current_image = self._wave
            self._click_pose_active = True
            self._click_feedback_timer.start(CLICK_FEEDBACK_MS)
        self._record_activity()
        self.update()

    def _end_click_feedback(self):
        self._click_pose_active = False
        if self._travel_state == "idle" and not self._feeding_active:
            self._current_image = self._resting_image()
        self.update()

    def _check_activity(self):
        pos = (QCursor.pos().x(), QCursor.pos().y())
        if getattr(self, "_last_mouse_pos", None) != pos:
            self._last_mouse_pos = pos
            self._record_activity()
        if (self._sleeping or self._walking or self._travel_state != "idle" or self._feeding_active or self._feed_prompt
                or self._drag_offset is not None):
            return
        if time.time() - self._work_start >= self._trigger_seconds:
            self._start_trip()

    def _start_trip(self):
        if (self._sleeping or self._walking or self._travel_state != "idle" or self._feeding_active or self._feed_prompt
                or self._drag_offset is not None or self._click_pose_active):
            return
        self._hide_game_prompt()
        if self._user_position:
            self._travel_return_pos = QPoint(self.pos())
            self._travel_return_screen = self._screen_for_pet()
        self._clear_edge_peek()
        self._travel_state = "leaving"
        self._letter_pending = False
        self._speech = "我去旅行啦"
        self._start_walk_animation("right")
        QTimer.singleShot(TRAVEL_SECONDS, self._leave)
        print("[soobin] 旅行开始")

    def _leave(self):
        if self._travel_state != "leaving":
            return
        self._stop_frame_animation()
        self._travel_state = "away"
        self._speech = ""
        self.hide()
        QTimer.singleShot(round(self._away_seconds * 1000), self._return)

    def _return(self):
        if self._travel_state != "away":
            return
        self._travel_state = "returning"
        screen_obj = (self._travel_return_screen
                      if self._user_position and self._travel_return_screen in QApplication.screens()
                      else self._screen_under_cursor())
        if screen_obj is None:
            return
        self._active_screen = screen_obj
        return_pos = (QPoint(self._travel_return_pos)
                      if self._user_position and self._travel_return_pos is not None
                      else self._anchor_on_screen(screen_obj))
        self.move(return_pos)
        self.show()
        self.raise_()
        self._speech = "我回来啦"
        self._start_walk_animation("left")
        QTimer.singleShot(TRAVEL_SECONDS, self._offer_letter)

    def _offer_letter(self):
        if self._travel_state != "returning":
            return
        self._stop_frame_animation()
        self._current_image = self._resting_image()
        self._travel_state = "letter_waiting"
        self._letter_pending = True
        self._work_start = time.time()
        self._speech = "有一封信给你"
        self.update()
        self._settle_edge_peek()

    def _next_frame(self):
        if not self._animation_frames:
            self._frame_timer.stop()
            return
        self._frame_index = (self._frame_index + 1) % len(self._animation_frames)
        self._current_image = self._animation_frames[self._frame_index]
        self.update()

    def _check_sleep(self):
        today = date.today()
        if self._sleep_suppressed_until and today >= self._sleep_suppressed_until:
            self._sleep_suppressed_until = None
        if (self._sleeping or not self._sleep_frames or datetime.now().hour < SLEEP_HOUR
                or (self._sleep_suppressed_until and today < self._sleep_suppressed_until)
                or self._travel_state != "idle" or self._feeding_active or self._walking
                or self._feed_prompt or self._drag_offset is not None or self._click_pose_active
                or self._music_playing or self._edge_side is not None):
            return
        self._start_sleep()

    def _start_sleep(self):
        if not self._sleep_frames:
            return
        self._stop_random_walk()
        self._hide_game_prompt()
        self._sleeping = True
        self._hide_feed_prompt()
        self._hide_mood()
        self._click_pose_active = False
        self._click_feedback_timer.stop()
        self._speech = ""
        self._animation_frames = self._sleep_frames
        self._frame_index = 0
        self._current_image = self._animation_frames[0]
        self._frame_timer.start(SLEEP_FRAME_INTERVAL_MS)
        self.update()

    def _wake_from_sleep(self):
        if not self._sleeping:
            return
        self._sleeping = False
        self._sleep_suppressed_until = date.today() + timedelta(days=1)
        self._stop_frame_animation()
        self._current_image = self._resting_image()
        self.update()

    def _start_lift_animation(self):
        if (not self._lift_frames or self._lift_animation_active
                or self._travel_state != "idle" or self._feeding_active):
            return
        if self._sleeping:
            self._wake_from_sleep()
        self._hide_feed_prompt()
        self._hide_mood()
        self._click_pose_active = False
        self._click_feedback_timer.stop()
        self._lift_animation_active = True
        self._animation_frames = self._lift_frames
        self._frame_index = 0
        self._current_image = self._animation_frames[0]
        self._frame_timer.start(LIFT_FRAME_INTERVAL_MS)
        self.update()

    def _stop_lift_animation(self):
        if not self._lift_animation_active:
            return
        self._lift_animation_active = False
        self._stop_frame_animation()
        self._current_image = self._resting_image()
        self.update()

    def _advance_feeding(self):
        if not self._feeding_active:
            return
        self._feeding_index += 1
        if self._feeding_index >= len(self._feeding_frames):
            self._finish_feeding()
            return
        self._current_image = self._feeding_frames[self._feeding_index]
        self.update()
        if self._feeding_index == len(self._feeding_frames) - 1:
            # 松喵喵会让最后一帧停留到整段喂食动作结束。
            remaining = FEED_DURATION_MS - self._feeding_index * FEED_FRAME_INTERVAL_MS
            self._feeding_timer.start(max(FEED_FRAME_INTERVAL_MS, remaining))
        else:
            self._feeding_timer.start(FEED_FRAME_INTERVAL_MS)

    def _resize_preserving_center_bottom(self, size):
        width, height = size
        old_geometry = self.geometry()
        screen = self._screen_for_pet()
        new_x = round(old_geometry.x() + (old_geometry.width() - width) / 2)
        new_y = old_geometry.y() + old_geometry.height() - height
        self.setFixedSize(width, height)
        if screen is not None:
            bounds = screen.geometry()
            new_x = max(bounds.left(), min(new_x, bounds.right() - width + 1))
        self.move(new_x, new_y)

    def _start_feeding(self):
        if self._sleeping or self._travel_state != "idle" or self._feeding_active or not self._feeding_frames:
            return
        self._hide_game_prompt()
        self._bring_edge_pet_onscreen(FEED_WINDOW_SIZE[0] - self.width())
        self._feeding_active = True
        self._click_pose_active = False
        self._click_feedback_timer.stop()
        self._feeding_index = 0
        self._speech = ""
        self._hide_feed_prompt()
        self._hide_mood()
        self._last_activity = time.time()
        self._work_start = self._last_activity
        self._resize_preserving_center_bottom(FEED_WINDOW_SIZE)
        self._current_image = self._feeding_frames[0]
        self.update()
        self._feeding_timer.start(
            FEED_FRAME_INTERVAL_MS if len(self._feeding_frames) > 1 else FEED_DURATION_MS
        )

    def _finish_feeding(self):
        self._feeding_timer.stop()
        self._feeding_active = False
        self._current_image = self._resting_image()
        self._resize_preserving_center_bottom(BASE_WINDOW_SIZE)
        self._change_stamina(20)
        if self._stamina > 20:
            self._mood = "😊"
            self._mood_hide_timer.start(MOOD_DURATION_MS)
        self.update()
        self._settle_edge_peek()

    def _start_walk_animation(self, direction="right"):
        if not self._travel_frames:
            self._current_image = self._resting_image()
            return
        self._animation_frames = (self._travel_frames_left if direction == "left"
                                  else self._travel_frames)
        self._frame_index = 0
        self._current_image = self._animation_frames[0]
        self._frame_timer.start(TRAVEL_FRAME_INTERVAL_MS)
        self.update()

    def _stop_frame_animation(self):
        self._frame_timer.stop()
        self._animation_frames = []
        self.update()

    def _check_random_walk(self):
        if (not self._walk_frames or self._sleeping or self._travel_state != "idle"
                or self._walking or self._stamina <= 20 or self._feeding_active or self._music_playing
                or self._feed_prompt or self._game_prompt or self._drag_offset is not None
                or self._click_pose_active or self._letter_pending):
            return
        if random.random() >= WALK_PROBABILITY:
            return

        screen = self._screen_for_pet()
        if screen is None:
            return
        self._bring_edge_pet_onscreen()
        bounds = screen.availableGeometry()
        current_x = self.x()
        direction = random.choice((-1, 1))
        distance = random.randint(WALK_DISTANCE_MIN, WALK_DISTANCE_MAX)
        left_limit = bounds.left()
        right_limit = bounds.right() - self.width() + 1
        target_x = max(left_limit, min(current_x + direction * distance, right_limit))
        if target_x == current_x:
            return

        self._active_screen = screen
        self._walk_target_x = target_x
        self._walk_direction = 1 if target_x > current_x else -1
        self._walk_frame_index = 0
        self._walk_active_frames = (self._walk_frames if self._walk_direction > 0
                                    else self._walk_frames_left)
        self._walking = True
        self._hide_mood()
        self._current_image = self._walk_active_frames[0]
        self._walk_frame_timer.start(WALK_FRAME_INTERVAL_MS)
        self._walk_step_timer.start(WALK_STEP_MS)
        self.update()

    def _advance_walk_frame(self):
        if not self._walking or not self._walk_active_frames:
            self._walk_frame_timer.stop()
            return
        self._walk_frame_index = (self._walk_frame_index + 1) % len(self._walk_active_frames)
        self._current_image = self._walk_active_frames[self._walk_frame_index]
        self.update()

    def _walk_step(self):
        if not self._walking or self._drag_offset is not None:
            self._stop_random_walk()
            return
        current_x = self.x()
        if self._walk_direction > 0:
            next_x = min(current_x + WALK_STEP_PX, self._walk_target_x)
        else:
            next_x = max(current_x - WALK_STEP_PX, self._walk_target_x)
        self.move(next_x, self.y())
        if next_x == self._walk_target_x:
            self._stop_random_walk()
            self._settle_edge_peek()

    def _stop_random_walk(self):
        self._walk_step_timer.stop()
        self._walk_frame_timer.stop()
        was_walking = self._walking
        self._walking = False
        self._walk_active_frames = []
        self._walk_target_x = None
        if was_walking and self._travel_state == "idle" and not self._feeding_active:
            self._current_image = self._resting_image()
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image_rect = QRect(8, 32, 128, 128)
        if not self._current_image.isNull():
            if self._feeding_active:
                # Expand only the window width for the oranges and book. Keep
                # the sprite at idle height and on the same visual baseline.
                scaled = self._current_image.scaledToHeight(
                    IDLE_DRAW_SIZE,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = IDLE_DRAW_Y
            elif (self._edge_side is not None
                    and self._current_image.cacheKey() in {
                        self._edge_peek.cacheKey(), self._edge_peek_right.cacheKey(),
                        self._edge_peek_top.cacheKey(), self._edge_peek_bottom.cacheKey(),
                    }):
                # Match the standing sprite's ~125 px visible height while
                # keeping the wall divider at the physical screen edge.
                scaled = self._current_image.scaled(
                    EDGE_PEEK_DRAW_RECT.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = EDGE_PEEK_DRAW_RECT.x() + (EDGE_PEEK_DRAW_RECT.width() - scaled.width()) // 2
                if self._edge_side == "top":
                    y = 0
                elif self._edge_side == "bottom":
                    y = self.height() - scaled.height()
                else:
                    y = EDGE_PEEK_DRAW_RECT.y() + (EDGE_PEEK_DRAW_RECT.height() - scaled.height()) // 2
            elif self._current_image.cacheKey() in self._weak_image_keys:
                # Remove the large transparent margins from all three weak
                # frames, then match 松喵喵's visible lying-pose width.
                scaled = self._current_image.scaledToWidth(
                    WEAK_DRAW_WIDTH,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = WEAK_VISIBLE_BASELINE_Y - scaled.height()
            elif self._current_image.cacheKey() in self._standing_canvas_keys:
                # The idle, lift and game frames share the same source canvas.
                # Preserve 崔勇萌's original proportions instead of stretching
                # the square source canvas to match another character's width.
                scaled = self._current_image.scaledToHeight(
                    IDLE_DRAW_SIZE,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = IDLE_DRAW_Y
            elif (not self._wave.isNull()
                  and self._current_image.cacheKey() == self._wave.cacheKey()):
                # Keep the greeting pose's visible height and foot baseline
                # aligned with the standing sprite without stretching it.
                scaled = self._current_image.scaledToHeight(
                    WAVE_DRAW_HEIGHT,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = IDLE_VISIBLE_BASELINE_Y - round(
                    WAVE_VISIBLE_BOTTOM_RATIO * scaled.height()
                )
            elif self._travel_state in ("leaving", "returning"):
                scaled = self._current_image.scaledToHeight(
                    TRAVEL_DRAW_HEIGHT,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = IDLE_DRAW_Y
            elif self._walking:
                scaled = self._current_image.scaledToHeight(
                    WALK_DRAW_HEIGHT,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (self.width() - scaled.width()) // 2
                y = IDLE_DRAW_Y
            else:
                scaled = self._current_image.scaled(
                    image_rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = image_rect.x() + (image_rect.width() - scaled.width()) // 2
                y = image_rect.y() + (image_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QColor("#e7b74f"))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "请放入崔勇萌\n官方透明图")
        if self._speech:
            font = QFont("Helvetica", 13, QFont.Weight.Bold)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            padding = 8
            bubble_width = metrics.horizontalAdvance(self._speech) + padding * 2
            bubble_height = metrics.height() + padding
            bubble_x = (self.width() - bubble_width) // 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 20, 20, 185))
            painter.drawRoundedRect(bubble_x, 4, bubble_width, bubble_height, 10, 10)
            painter.setPen(QColor("white"))
            painter.drawText(bubble_x + padding, 4 + metrics.height(), self._speech)
        elif (self._travel_state == "idle" and not self._feeding_active
              and self._edge_side is None):
            if self._game_prompt and not self._game_prompt_image.isNull():
                painter.drawPixmap(GAME_PROMPT_DRAW_RECT, self._game_prompt_image)
            elif self._feed_prompt:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 225))
                painter.drawRoundedRect(FEED_PROMPT_RECT, 13, 13)
                painter.setPen(QColor("#444444"))
                painter.setFont(QFont("Apple Color Emoji", 15))
                painter.drawText(FEED_PROMPT_RECT, Qt.AlignmentFlag.AlignCenter, "🍊")
            else:
                low_stamina = self._stamina <= 20
                pulse = ((math.sin(time.monotonic() * math.tau / 1.1) + 1.0) / 2.0
                         if low_stamina else 0.0)
                stamina_text = self._stamina_feedback or f"{self._stamina}%"
                font_size = 9 + (round(4 * pulse) if low_stamina else 0)
                painter.setFont(QFont("Helvetica", font_size, QFont.Weight.Bold))
                painter.setPen(QColor(120, 120, 120, 150 + round(80 * pulse)))
                painter.drawText(STAMINA_RECT.translated(1, 2), Qt.AlignmentFlag.AlignCenter,
                                 stamina_text)
                painter.setPen(QColor(255, 255, 255, 190 + round(65 * pulse)))
                painter.drawText(STAMINA_RECT, Qt.AlignmentFlag.AlignCenter, stamina_text)
                mood_emoji = "😩" if low_stamina else self._mood
                if mood_emoji:
                    painter.setFont(QFont("Apple Color Emoji", 17))
                    painter.drawText(MOOD_RECT, Qt.AlignmentFlag.AlignCenter, mood_emoji)
        if self._letter_pending:
            if not self._envelope_icon.isNull():
                painter.drawPixmap(ICON_RECT, self._envelope_icon)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#fff8ef"))
                painter.drawRoundedRect(ICON_RECT, 5, 5)
                painter.setPen(QColor("#b86566"))
                painter.drawLine(ICON_RECT.left() + 2, ICON_RECT.top() + 4,
                                 ICON_RECT.center().x(), ICON_RECT.center().y() + 1)
                painter.drawLine(ICON_RECT.right() - 2, ICON_RECT.top() + 4,
                                 ICON_RECT.center().x(), ICON_RECT.center().y() + 1)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._show_exit_menu(event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._stop_random_walk()
        global_pos = event.globalPosition().toPoint()
        self._drag_offset = global_pos - self.frameGeometry().topLeft()
        self._drag_origin = global_pos
        self._press_pos = event.position().toPoint()
        self._dragged = False
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_offset is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        global_pos = event.globalPosition().toPoint()
        if (global_pos - self._drag_origin).manhattanLength() >= DRAG_THRESHOLD_PX:
            self._dragged = True
            self._clear_edge_peek()
            self._start_lift_animation()
            self._hide_feed_prompt()
            self._hide_game_prompt()
            self._hide_mood()
            screen = (QApplication.screenAt(global_pos)
                      or QApplication.screenAt(self.geometry().center())
                      or self._active_screen or QApplication.primaryScreen())
            self.move(self._clamp_to_screen(global_pos - self._drag_offset, screen, physical=True))
            self._active_screen = screen

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._drag_offset is None:
            return
        moved = (event.globalPosition().toPoint() - self._drag_origin).manhattanLength()
        click_pos = self._press_pos
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if moved >= DRAG_THRESHOLD_PX or self._dragged:
            self._stop_lift_animation()
            self._wake_from_sleep()
            self._user_position = True
            self._settle_edge_peek()
            self._record_activity()
            self._save_state()
            self._drag_origin = None
            self._dragged = False
            return
        self._drag_origin = None
        self._dragged = False
        self._record_activity()
        if self._sleeping:
            self._wake_from_sleep()
            return
        if self._letter_pending and ICON_RECT.contains(click_pos):
            self._open_letter()
        elif self._game_prompt:
            if GAME_PROMPT_RECT.contains(click_pos):
                self._open_music_from_game_prompt()
            else:
                self._hide_game_prompt()
        elif (self._edge_side is None and self._feed_prompt
              and FEED_PROMPT_RECT.contains(click_pos)):
            self._start_feeding()
        elif self._edge_side is None and STAMINA_RECT.contains(click_pos):
            self._show_feed_prompt()
        elif GAME_BELLY_RECT.contains(click_pos):
            self._show_game_prompt()
        elif QRect(8, 32, 128, 128).contains(click_pos):
            self._show_click_feedback()
        else:
            self._hide_feed_prompt()

    def _show_exit_menu(self, global_pos):
        menu = QMenu(self)
        exit_action = menu.addAction("退出")
        if menu.exec(global_pos) is exit_action:
            self.close()
            QApplication.instance().quit()

    def _open_letter(self):
        if not self._letter_pending:
            return
        self._letter_pending = False
        self._travel_state = "reading"
        self._speech = ""
        self._current_image = self._resting_image()
        self.update()
        dialog = LetterDialog(random_letter_quote(), self)
        screen_obj = self._screen_for_pet()
        self._position_letter_dialog(dialog, screen_obj)
        dialog.finished.connect(self._close_letter)
        self._letter_dialog = dialog
        self._travel_state = "reading"
        dialog.show()

    def _position_letter_dialog(self, dialog, screen_obj):
        screen = screen_obj.availableGeometry()
        x = min(max(screen.left(), self.x() + self.width() + 12), screen.right() - dialog.width() + 1)
        y = min(max(screen.top(), self.y() - 80), screen.bottom() - dialog.height() + 1)
        dialog.move(x, y)

    def _close_letter(self, _result=0):
        self._stop_frame_animation()
        self._letter_dialog = None
        self._travel_state = "idle"
        self._speech = ""
        self._work_start = time.time()
        self._last_activity = self._work_start
        self._current_image = self._resting_image()
        self.update()


def main():
    parser = argparse.ArgumentParser(description="崔秀彬 / CHOI YONG MEONG 旅行来信桌宠 DEMO")
    parser.add_argument("--demo-now", action="store_true", help="启动后立即出发")
    parser.add_argument("--trigger-minutes", type=float, default=90, help="连续活动触发分钟数")
    parser.add_argument("--away-seconds", type=float, default=20 * 60, help="旅行离开时间")
    args = parser.parse_args()

    instance_lock = QLockFile(
        os.path.join(tempfile.gettempdir(), "choi-yong-meong-desktop-pet.lock")
    )
    if not instance_lock.tryLock(0):
        print("[instance] 崔勇萌已经在运行，忽略重复启动。")
        return 0

    try:
        app = QApplication(sys.argv[:1])
        app.setQuitOnLastWindowClosed(True)
        pet = SoobinPet(args)
        pet.show()
        return app.exec()
    finally:
        instance_lock.unlock()


if __name__ == "__main__":
    sys.exit(main())
