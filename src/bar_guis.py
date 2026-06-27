"""
Boss Health Bar Module

Provides a scalable, animated boss health bar overlay for the Sharko game.
Features include smooth health fill animations, slide-in/out transitions,
and customizable visual elements like markers, icons, and text.
"""

import math
import random
from ctypes import windll

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import QWidget

from constants import SharkoConstants

# --- PATHS ---
PARRY_IMAGES = [
    "assets/particlesUI/sparkle2.png",
    "assets/particlesUI/spark.png",
    "assets/particlesUI/ring.png",
]
# Ensure these files exist in your project folder
BAR_IMG_PATH = "assets/UI/boss_bar_border.png"
MARKER_PATH = "assets/UI/boss_bar_pins.png"
CENTER_ICON_PATH = "assets/UI/boss_bar_skull.png"
FONT_PATH = "assets/fonts/Boss_Font.otf"


class ScalableHealthBar(QWidget):
    """Scalable health bar widget for boss battles with animations and effects."""

    def __init__(self, parent=None):
        """Initialize the health bar with transparent background and animations."""
        super().__init__(parent)

        # 1. Window Setup: Transparent, Always on Top, Click-Through
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Health
        self.health = SharkoConstants.MAX_HEALTH

        # Default Size
        self.setMinimumSize(400, 160)

        # 2. Load Resources
        def tint_pixmap(pixmap, color):
            painter = QPainter(pixmap)
            original = QPixmap(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            painter.fillRect(pixmap.rect(), color)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.drawPixmap(0, 0, original)
            painter.end()

        barcolor = QColor(230, 191, 124)
        self.bar_img = QPixmap(BAR_IMG_PATH)
        tint_pixmap(self.bar_img, barcolor)
        self.marker_img = QPixmap(MARKER_PATH)
        tint_pixmap(self.marker_img, barcolor)
        self.icon_img = QPixmap(CENTER_ICON_PATH)
        self.original_crop_border = 16
        self.percentage = 1.0
        self.current_percentage = 1.0

        # 3. Health Animation Timer (The "Sliding" fill effect)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_health_fill)
        self.animation_timer.start(16)

        # 4. Slide Animation Setup (The "In/Out" movement)
        self._pos_animation = QPropertyAnimation(self, b"anim_pos")
        self._pos_animation.setDuration(600)
        self._pos_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 5. Font Setup
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        if font_id != -1:
            family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.custom_font = QFont(family, 22)
        else:
            self.custom_font = QFont("Arial", 22)
        screen_w = windll.user32.GetSystemMetrics(0)
        self.initial_x = (screen_w - self.width()) // 2
        self.move(self.initial_x, -self.height())

    # --- ANIMATION PROPERTY ---
    @pyqtProperty(QPoint)
    def anim_pos(self):
        return self.pos()

    @anim_pos.setter
    def anim_pos(self, p):
        self.move(p)

    def slide_in(self):
        """Slides the health bar down into view using animation. Call to display the bar."""
        self._pos_animation.stop()  # Stop any current movement

        screen_w = windll.user32.GetSystemMetrics(0)
        target_x = (screen_w - self.width()) // 2
        target_y = 10

        # If it was hidden or deleted, we ensure it's visible and positioned correctly
        self.show()
        self.pos

        self._pos_animation.setStartValue(self.pos() if self.y() > -self.height() else QPoint(target_x, -self.height()))
        self._pos_animation.setEndValue(QPoint(target_x, target_y))
        self._pos_animation.start()

    def slide_out_to_hide(self):
        """Slides the health bar up and hides it. Use instead of delete to reuse the bar."""
        self._pos_animation.stop()
        self.animation_timer.stop()  # Stop health animation timer

        self._pos_animation.setStartValue(self.pos())
        self._pos_animation.setEndValue(QPoint(self.x(), -self.height()))

        # Connect to hide() instead of deleteLater()
        try:
            self._pos_animation.finished.disconnect()  # Clear old connections
        except:
            pass

        def cleanup_after_slide():
            self.animation_timer.stop()
            try:
                self._pos_animation.finished.disconnect()
            except:
                pass
            self.animation_timer.deleteLater()
            self.animation_timer = None
            self.deleteLater()

        self._pos_animation.finished.connect(cleanup_after_slide)
        self._pos_animation.start()

    def update_health_fill(self):
        """Update the health fill animation frame."""
        self.update()
        # Smooth interpolation for the health bar fill
        if abs(self.percentage - self.current_percentage) < 0.001:
            self.current_percentage = self.percentage

    def paintEvent(self, event):
        """Render the health bar with background, fill, markers, icon, and text."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), int(self.height() / 4)
        y_offset = self.height() // 2

        # --- LAYER: Health Bar Background & Fill ---
        if not self.bar_img.isNull():
            sw, sh = self.bar_img.width(), self.bar_img.height()
            cap_w = int(h * 0.75)
            src_b = self.original_crop_border

            # Background Rect
            bg_rect = QRect(cap_w // 2, math.floor(h * 0.25 // 2) + y_offset, int(w - cap_w), h - math.floor(h * 0.25))
            painter.fillRect(bg_rect, QColor(63, 62, 72))

            # Foreground Fill Rect
            self.current_percentage += (self.percentage - self.current_percentage) * 0.3
            fill_w = int((w - cap_w) * self.current_percentage)
            fill_rect = QRect(cap_w // 2, math.floor(h * 0.25 // 2) + y_offset, fill_w, h - math.floor(h * 0.25))
            painter.fillRect(fill_rect, QColor(118, 139, 153))

            # Draw the 3-slice border image
            painter.drawPixmap(QRect(0, y_offset, cap_w, h), self.bar_img, QRect(0, 0, src_b, sh))
            painter.drawPixmap(QRect(cap_w, y_offset, w - 2 * cap_w, h), self.bar_img, QRect(src_b, 0, sw - 2 * src_b, sh))
            painter.drawPixmap(QRect(w - cap_w, y_offset, cap_w, h), self.bar_img, QRect(sw - src_b, 0, src_b, sh))

        # --- LAYER: Pins/Markers ---
        if not self.marker_img.isNull():
            mw = int(h * 11 / 22)
            for p in [0.2, 0.4, 0.6, 0.8]:
                m_x = int(p * w) - mw // 2
                painter.drawPixmap(QRect(m_x, y_offset, mw, h), self.marker_img)

        # --- LAYER: Boss Icon ---
        if not self.icon_img.isNull():
            iw = int(h * 2.5)
            painter.drawPixmap(QRect(w // 2 - int(iw * 21 / 32) // 2, int(self.height() * 0.17), int(iw * 21 / 32), iw), self.icon_img)

        # --- LAYER: Text ---
        boss_name = "DESTROYMAN III"
        painter.setFont(self.custom_font)
        metrics = painter.fontMetrics()
        text_width = metrics.boundingRect(boss_name).width()
        text_x = (w - text_width) // 2
        text_y = y_offset + h + metrics.ascent() + 10

        path = QPainterPath()
        path.addText(text_x, text_y, self.custom_font, boss_name)

        # Text Outline
        pen = QPen(QColor(0, 0, 0), 4)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.strokePath(path, pen)
        # Text Fill
        painter.fillPath(path, QColor(255, 255, 255))

    def change_percentage(self):
        """Update health percentage (used for demo/testing purposes)."""
        self.percentage = random.random()
