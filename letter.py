"""Animated travel letter dialog for Songnyang."""

import glob
import os

from PyQt6.QtCore import QElapsedTimer, Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QDialog, QPushButton


ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
REVEAL_DIR = os.path.join(ASSET_DIR, "frames", "letter_reveal")
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
                frames.append(image)
        cls._cached_frames = frames

    def __init__(self, quote: str, parent=None):
        super().__init__(parent)
        self._quote = quote
        self._envelope = QPixmap(os.path.join(ASSET_DIR, "envelope_icon.png"))
        self._paper = QPixmap(os.path.join(ASSET_DIR, "heart_letter_paper.jpeg"))
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
        if self._frames and not self._frame_clock.isValid():
            self._frame_clock.start()
            self._frame_timer.start(FRAME_TICK_MS)

    def _draw_paper(self, painter: QPainter, rect: QRectF):
        if self._paper.isNull():
            return
        x, y = rect.x(), rect.y()
        sx, sy = rect.width() / 440, rect.height() / 338

        def point(px, py):
            return x + px * sx, y + py * sy

        paper_shape = QPainterPath()
        paper_shape.moveTo(*point(220, 338))
        for controls in (
            (170, 300, 0, 216, 0, 138),
            (0, 60, 38, 0, 105, 0),
            (156, 0, 193, 30, 220, 61),
            (248, 30, 285, 0, 336, 0),
            (402, 0, 440, 60, 440, 138),
            (440, 216, 270, 300, 220, 338),
        ):
            coords = [point(controls[i], controls[i + 1]) for i in (0, 2, 4)]
            paper_shape.cubicTo(*coords[0], *coords[1], *coords[2])
        painter.save()
        painter.setClipPath(paper_shape)
        painter.drawPixmap(rect, self._paper, QRectF(self._paper.rect()))
        painter.restore()

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
                # Enlarge the source animation's open envelope separately so
                # it remains visible below the expanded letter.
                envelope_rect = QRectF(170 - 50 * settle, 330 - 60 * settle,
                                       160 + 100 * settle, 145 + 45 * settle)
                painter.drawPixmap(envelope_rect, self._frames[-1],
                                   QRectF(67, 129, 66, 66))
                paper_rect = QRectF(118 - 58 * settle, 120 - 100 * settle,
                                    259 + 121 * settle, 205 + 89 * settle)
                self._draw_paper(painter, paper_rect)
            else:
                painter.drawPixmap(QRectF(0, 0, 500, 500), final_frame,
                                   QRectF(final_frame.rect()))
        else:
            if not self._envelope.isNull():
                painter.drawPixmap(QRectF(130, 315, 240, 160), self._envelope,
                                   QRectF(self._envelope.rect()))
            self._draw_paper(painter, QRectF(60, 20, 380, 294))

        reveal_ready = not self._frames or settle > 0
        if reveal_ready:
            painter.save()
            painter.setOpacity(settle if self._frames else 1.0)
            painter.setPen(QColor("#68483a"))
            title_font = QFont(LETTER_FONT, 14, QFont.Weight.Bold)
            title_font.setStyle(QFont.Style.StyleNormal)
            painter.setFont(title_font)
            painter.drawText(QRectF(75, 62, 350, 30), Qt.AlignmentFlag.AlignCenter,
                             "松喵喵的旅游来信")
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
