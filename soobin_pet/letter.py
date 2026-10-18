"""Animated envelope and letter dialog for the Soobin-only desktop pet."""

import glob
import os

from PyQt6.QtCore import QElapsedTimer, Qt, QRectF, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPixmap
from PyQt6.QtWidgets import QDialog, QPushButton

from macos_window import show_on_all_spaces


ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LETTER_DIR = os.path.join(ASSET_DIR, "letter")
REVEAL_DIR = os.path.join(LETTER_DIR, "reveal")
REVEAL_DURATION_MS = 1_200
SETTLE_DURATION_MS = 220
FRAME_TICK_MS = 16
LETTER_FONT = "Kaiti SC"


class LetterDialog(QDialog):
    _cached_frames = None

    @classmethod
    def preload_frames(cls):
        if cls._cached_frames is not None:
            return
        paths = sorted(
            path for path in glob.glob(os.path.join(REVEAL_DIR, "*.png"))
            if not os.path.basename(path).startswith(".")
        )
        frames = []
        for path in paths:
            image = QPixmap(path)
            if not image.isNull():
                frames.append(image.scaled(
                    QSize(500, 500),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        cls._cached_frames = frames

    def __init__(self, quote: str, parent=None):
        super().__init__(parent)
        self._quote = quote
        self._envelope = QPixmap(os.path.join(LETTER_DIR, "envelope.png"))
        self._paper = QPixmap(os.path.join(LETTER_DIR, "heart_paper.png"))
        self.preload_frames()
        self._frames = self._cached_frames
        self._frame_index = 0
        self._frame_clock = QElapsedTimer()

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 540)

        self._close_button = QPushButton("收好", self)
        self._close_button.setGeometry(206, 500, 88, 32)
        self._close_button.setStyleSheet(
            "QPushButton { background: #72cfc2; color: #294c49; border: 0; "
            "border-radius: 14px; padding: 4px 12px; font-weight: 600; }"
            "QPushButton:hover { background: #5bb9ad; }"
        )
        self._close_button.clicked.connect(self.accept)
        self._close_button.setVisible(not self._frames)

        self._frame_timer = QTimer(self)
        self._frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._frame_timer.timeout.connect(self._advance_frame)

    def _advance_frame(self):
        elapsed = self._frame_clock.elapsed()
        next_index = min(
            len(self._frames) - 1,
            elapsed * (len(self._frames) - 1) // REVEAL_DURATION_MS,
        )
        if next_index != self._frame_index or elapsed >= REVEAL_DURATION_MS:
            self._frame_index = next_index
            self.update()
        if elapsed >= REVEAL_DURATION_MS + SETTLE_DURATION_MS:
            self._frame_timer.stop()
            self._close_button.show()

    def showEvent(self, event):
        super().showEvent(event)
        show_on_all_spaces(self)
        if self._frames and not self._frame_clock.isValid():
            self._frame_clock.start()
            self._frame_timer.start(FRAME_TICK_MS)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        settle = 0.0
        if self._frames and self._frame_clock.isValid():
            settle = min(1.0, max(0.0,
                (self._frame_clock.elapsed() - REVEAL_DURATION_MS) / SETTLE_DURATION_MS))

        if self._frames:
            final_frame = self._frames[self._frame_index]
            if settle > 0 and not self._paper.isNull():
                # Keep the animation's open envelope, then let the paper become
                # visibly larger than it in the final composition.
                frame_rect = QRectF(20 * settle, 40 * settle,
                                    500 - 40 * settle, 500 - 40 * settle)
                painter.drawPixmap(frame_rect, final_frame, QRectF(final_frame.rect()))
                paper_rect = QRectF(118 - 58 * settle, 73 - 53 * settle,
                                    259 + 121 * settle, 205 + 89 * settle)
                painter.drawPixmap(paper_rect, self._paper, QRectF(self._paper.rect()))
            else:
                painter.drawPixmap(0, 0, final_frame)
        else:
            if not self._envelope.isNull():
                painter.drawPixmap(QRectF(130, 315, 240, 160), self._envelope,
                                   QRectF(self._envelope.rect()))
            if not self._paper.isNull():
                painter.drawPixmap(QRectF(60, 20, 380, 294), self._paper,
                                   QRectF(self._paper.rect()))

        reveal_ready = not self._frames or settle > 0
        if reveal_ready:
            painter.save()
            painter.setOpacity(settle if self._frames else 1.0)
            painter.setPen(QColor("#68483a"))
            title_font = QFont(LETTER_FONT, 14, QFont.Weight.Bold)
            title_font.setStyle(QFont.Style.StyleNormal)
            painter.setFont(title_font)
            painter.drawText(QRectF(75, 62, 350, 30), Qt.AlignmentFlag.AlignCenter,
                             "崔勇萌的旅行来信")
            quote_font = QFont(LETTER_FONT, 16, QFont.Weight.Bold)
            quote_font.setStyle(QFont.Style.StyleNormal)
            painter.setFont(quote_font)
            metrics = QFontMetricsF(quote_font)
            lines = []
            current_line = ""
            for character in self._quote:
                candidate = current_line + character
                if current_line and metrics.horizontalAdvance(candidate) > 320:
                    lines.append(current_line)
                    current_line = character
                else:
                    current_line = candidate
            if current_line:
                lines.append(current_line)
            for index, line in enumerate(lines):
                painter.drawText(QRectF(90, 93 + index * 27, 320, 36),
                                 Qt.AlignmentFlag.AlignCenter, line)
            painter.restore()

        painter.end()
