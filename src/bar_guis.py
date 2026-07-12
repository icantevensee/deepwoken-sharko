"""
Boss Health Bar Module

Provides a scalable, animated boss health bar overlay for the Sharko game.
Features include smooth health fill animations, slide-in/out transitions,
and customizable visual elements like markers, icons, and text.
"""

import math
import time
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
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import QWidget

from constants import SharkoConstants
from img_utils import ImgUtils

# Ensure these files exist in your project folder


class ScalableHealthBar(QWidget):
    """Scalable health bar widget for boss battles with animations and effects."""

    def __init__(self, parent=None, bar_height_scale=0.18, target_obj=None):
        """Initialize the health bar with transparent background and animations."""
        super().__init__(parent)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        screen_w = windll.user32.GetSystemMetrics(0)
        screen_h = windll.user32.GetSystemMetrics(1) - 1
        self.setGeometry(0, 0, screen_w, screen_h)

        # Health
        self.boss_health = SharkoConstants.MAX_BOSS_HEALTH
        self.target_obj = target_obj
        self.player_health = SharkoConstants.MAX_PLAYER_HEALTH

        bb_color                        = QColor(230, 191, 124)
        outline_color                   = QColor(183, 197, 211)
        self.bb_img                     = QPixmap(SharkoConstants.BOSS_BAR_IMG_PATH)
        ImgUtils.tint_pixmap(self.bb_img, bb_color)
        self.bb_pin_img                 = QPixmap(SharkoConstants.BOSS_BAR_PINS_PATH)
        ImgUtils.tint_pixmap(self.bb_pin_img, bb_color)
        self.bb_skull_img               = QPixmap(SharkoConstants.BOSS_BAR_SKULL_PATH)
        self.pb_img                     = QPixmap(SharkoConstants.POSTURE_BAR_BORDER_PATH)
        ImgUtils.tint_pixmap(self.pb_img, outline_color)
        self.pb_pin_img                 = QPixmap(SharkoConstants.POSTURE_BAR_PINS_PATH)
        ImgUtils.tint_pixmap(self.pb_pin_img, outline_color)
        self.plrb_img                   = QPixmap(SharkoConstants.PLR_HEALTH_BAR_BORDER_PATH)
        ImgUtils.tint_pixmap(self.plrb_img, outline_color)
        self.plrb_pin_img               = QPixmap(SharkoConstants.PLR_HEALTH_BAR_PINS_PATH)
        ImgUtils.tint_pixmap(self.plrb_pin_img, outline_color)
        self.icon_border_img            = QPixmap(SharkoConstants.ICON_FRAME_PATH)
        self.parry_cooldown_icon_img    = QPixmap(SharkoConstants.PARRY_COOLDOWN_ICON_PATH)
        self.bb_crop_border             = 16
        self.pb_crop_border             = 13
        self.bb_percentage              = 1
        self.current_bb_percentage      = 1
        self.pb_percentage              = 1
        self.current_pb_percentage      = 1
        self.plrb_percentage            = 1
        self.current_plrb_percentage    = 1
        self.bb_x_offset                = 0
        self.bb_y_offset                = 0
        self.bar_height_scale           = bar_height_scale
        self._boss_bar_canvas_offset = QPoint(0, 0)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_health_fill)
        self.animation_timer.start(16)

        self._bb_pos_animation = QPropertyAnimation(self, b"boss_bar_anim_pos")
        self._bb_pos_animation.setDuration(600)
        self._bb_pos_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.custom_font = QFont(target_obj.BOSS_FONT_FAMILY, 22)
        self.show()

    # --- ANIMATION PROPERTY ---
    @pyqtProperty(QPoint)
    def boss_bar_anim_pos(self):
        return self._boss_bar_canvas_offset

    @boss_bar_anim_pos.setter
    def boss_bar_anim_pos(self, p):
        self._boss_bar_canvas_offset = QPoint(p.x(), p.y())
        self.update()

    def slide_in(self):
        self._bb_pos_animation.stop()

        self.show()
        self._bb_pos_animation.setStartValue(QPoint(0, int(-self.height() * self.bar_height_scale * 1.6)))
        self._bb_pos_animation.setEndValue(QPoint(0, max(8, int(self.height() * self.bar_height_scale * 1.6))))
        self._bb_pos_animation.start()

    def slide_out_to_hide(self):
        self._bb_pos_animation.stop()
        self.animation_timer.stop()

        self._bb_pos_animation.setStartValue(self._boss_bar_canvas_offset)
        self._bb_pos_animation.setEndValue(QPoint(0, int(-self.height() * self.bar_height_scale * 1.6)))

        try:
            self._bb_pos_animation.finished.disconnect()
        except Exception:
            pass

        def cleanup_after_slide():
            self.animation_timer.stop()
            try:
                self._bb_pos_animation.finished.disconnect()
            except Exception:
                pass
            self.animation_timer.deleteLater()
            self.animation_timer = None
            self.deleteLater()

        self._bb_pos_animation.finished.connect(cleanup_after_slide)
        self._bb_pos_animation.start()

    def update_health_fill(self):
        """Update the health fill animation frame."""
        self.update()
        current_time = time.time()
        time_held = current_time - self.target_obj.parry_press_time if self.target_obj.f_key_held else 0
        if self.target_obj.posture > 0 and time_held < SharkoConstants.PARRY_WINDOW and current_time > self.target_obj.posture_break_cooldown_until:
            self.target_obj.posture = max(0, self.target_obj.posture - 0.003)
        self.pb_percentage = self.target_obj.posture / self.target_obj.MAX_POSTURE
        if abs(self.bb_percentage - self.current_bb_percentage) < 0.001:
            self.current_bb_percentage = self.bb_percentage
        if abs(self.pb_percentage - self.current_pb_percentage) < 0.001:
            self.current_pb_percentage = self.pb_percentage
        if abs(self.plrb_percentage - self.current_plrb_percentage) < 0.001:
            self.current_plrb_percentage = self.plrb_percentage

    def paintEvent(self, event):
        """Render the health bar with background, fill, markers, icon, and text."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        self._paint_boss_bar(painter)
        self._paint_posture_bar(painter)
        self._paint_player_health_bar(painter)

    def _paint_boss_bar(self, painter):
        # Dimensions
        w = self.width() // 2
        h = max(8, int(self.height() * self.bar_height_scale))
        x_offset = self.width() // 4
        y_offset = self._boss_bar_canvas_offset.y()

        sw, sh = self.bb_img.width(), self.bb_img.height()
        self.scale = h / sh

        src_b = self.bb_crop_border
        cap_w = int(src_b * self.scale)

        # Background rect
        bg_x = cap_w // 2 + x_offset
        bg_y = int(h * 0.125) + y_offset
        bg_w = w - cap_w
        bg_h = int(h * 0.75)

        bg_rect = QRect(bg_x, bg_y, bg_w, bg_h)
        painter.fillRect(bg_rect, QColor(63, 62, 72))

        # Foreground fill
        self.current_bb_percentage += (self.bb_percentage - self.current_bb_percentage) * 0.3
        fill_w = int(bg_w * self.current_bb_percentage)

        fill_rect = QRect(bg_x, bg_y, fill_w, bg_h)
        painter.fillRect(fill_rect, QColor(118, 139, 153))

        # Horizontal border
        painter.drawPixmap(QRect(x_offset, y_offset, cap_w, h), self.bb_img, QRect(0, 0, src_b, sh))
        painter.drawPixmap(QRect(cap_w + x_offset, y_offset, w - 2 * cap_w, h), self.bb_img, QRect(src_b, 0, sw - 2 * src_b, sh))
        painter.drawPixmap(QRect(w - cap_w + x_offset, y_offset, cap_w, h), self.bb_img, QRect(sw - src_b, 0, src_b, sh))

        # Pins
        mw = int(self.bb_pin_img.width() * self.scale)
        for p in [0.2, 0.4, 0.6, 0.8]:
            m_x = bg_x + int(p * bg_w) - (mw // 2)
            painter.drawPixmap(QRect(m_x, y_offset, mw, h), self.bb_pin_img)

        # Skull
        if not self.bb_skull_img.isNull():
            ih = int(self.bb_skull_img.height() * self.scale)
            iw = int(ih * (self.bb_skull_img.width() / self.bb_skull_img.height()))
            painter.drawPixmap(QRect(x_offset + (w - iw) // 2, y_offset - int(ih * (34 / 64)), iw, ih), self.bb_skull_img)

        # Text
        boss_name = "DESTROYMAN III"
        painter.setFont(self.custom_font)

        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(boss_name)
        text_x = x_offset + (w - text_width) // 2
        text_y = y_offset + h + metrics.ascent() + 10

        path = QPainterPath()
        path.addText(text_x, text_y, self.custom_font, boss_name)

        # Text Outline
        pen = QPen(QColor(0, 0, 0), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.strokePath(path, pen)
        painter.fillPath(path, QColor(255, 255, 255))

    def _paint_posture_bar(self, painter):
        h = int(2 * self.height() // (16 / 5))
        y_offset = int(self.height() // (16 / 3))
        x_offset = self._boss_bar_canvas_offset.y()

        sw, sh = self.pb_img.width(), self.pb_img.height()
        w = math.floor(sw * self.scale)
        src_b = self.pb_crop_border
        cap_h = math.floor(src_b * self.scale)
        max_fill_h = h - cap_h

        # Background Rect
        bg_rect = QRect(int(w * 0.125) + x_offset, cap_h // 2 + y_offset, int(w * 0.75), max_fill_h)
        painter.fillRect(bg_rect, QColor(63, 62, 72))

        # Foreground Fill
        self.current_pb_percentage += (self.pb_percentage - self.current_pb_percentage) * 0.3
        fill_h = int(max_fill_h * self.current_pb_percentage)
        
        # Invert the fill starting y to make it fill from bottom to top
        fill_y = cap_h // 2 + y_offset + (max_fill_h - fill_h)
        fill_rect = QRect(int(w * 0.125) + x_offset, fill_y, int(w * 0.75), fill_h)
        painter.fillRect(fill_rect, QColor(218, 183, 75))

        # Border
        mid_slice_y = y_offset + cap_h // 2
        bot_slice_y = mid_slice_y + max_fill_h - cap_h // 2
        painter.drawPixmap(QRect(x_offset, y_offset, w, cap_h), self.pb_img, QRect(0, 0, sw, src_b))
        painter.drawPixmap(QRect(x_offset, mid_slice_y, w, max_fill_h), self.pb_img, QRect(0, src_b, sw, sh - 2 * src_b))
        painter.drawPixmap(QRect(x_offset, bot_slice_y, w, cap_h), self.pb_img, QRect(0, sh - src_b, sw, src_b))
        # Pins
        mh = int(self.pb_pin_img.height() * self.scale)
        mw = int(self.pb_pin_img.width() * self.scale)
        for p in [0.2, 0.4, 0.6, 0.8]:
            # Pins calculated relative to the inner canvas height and inverted to align with a bottom-up scale
            m_y = int(p * max_fill_h) - mh // 2 + cap_h // 2
            painter.drawPixmap(QRect(x_offset, m_y + y_offset, mw, mh), self.pb_pin_img)

    def _paint_player_health_bar(self, painter):
        h = 2 * self.height() // 3
        y_offset = self.height() // 6
        x_offset = self._boss_bar_canvas_offset.y() - int(h * 0.1)

        sw, sh = self.plrb_img.width(), self.plrb_img.height()
        w = math.floor(sw * self.scale)
        src_b = self.bb_crop_border
        cap_h = math.floor(src_b * self.scale)
        max_fill_h = h - cap_h

        # Background Rect
        bg_rect = QRect(int(w * 0.125) + x_offset, cap_h // 2 + y_offset, int(w * 0.75), max_fill_h)
        painter.fillRect(bg_rect, QColor(63, 62, 72))

        # Foreground Fill
        self.current_plrb_percentage += (self.plrb_percentage - self.current_plrb_percentage) * 0.3
        fill_h = int(max_fill_h * self.current_plrb_percentage)
        
        # Invert the fill starting y to make it fill from bottom to top
        fill_y = cap_h // 2 + y_offset + (max_fill_h - fill_h)
        fill_rect = QRect(int(w * 0.125) + x_offset, fill_y, int(w * 0.75), fill_h)
        painter.fillRect(fill_rect, QColor(204, 111, 48))

        # Border
        mid_slice_y = y_offset + cap_h // 2
        bot_slice_y = mid_slice_y + max_fill_h - cap_h // 2
        painter.drawPixmap(QRect(x_offset, y_offset, w, cap_h), self.plrb_img, QRect(0, 0, sw, src_b))
        painter.drawPixmap(QRect(x_offset, mid_slice_y, w, max_fill_h), self.plrb_img, QRect(0, src_b, sw, sh - 2 * src_b))
        painter.drawPixmap(QRect(x_offset, bot_slice_y, w, cap_h), self.plrb_img, QRect(0, sh - src_b, sw, src_b))
        # Pins
        mh = int(self.plrb_pin_img.height() * self.scale)
        mw = int(self.plrb_pin_img.width() * self.scale)
        for p in [0.2, 0.4, 0.6, 0.8]:
            # Pins calculated relative to the inner canvas height and inverted to align with a bottom-up scale
            m_y = int(p * max_fill_h) - mh // 2 + cap_h // 2
            painter.drawPixmap(QRect(x_offset, m_y + y_offset, mw, mh), self.plrb_pin_img)
