"""Sword Window Widget Module

Widget that renders an ascii sword used for animated melee attacks:
- The sword can follow either the mouse cursor or a target window.
- Has a combo system that goes through multiple different strikes(overhead, diagonal, cross, thrust, and spin).
- Each uses easing functions and dynamic transformations for angle, scale, and twist."""

import math
import time

import ctypes

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter
from PyQt6.QtWidgets import QWidget


class SwordWindow(QWidget):
    ANIM_SPEED_MULT = 1.0
    COMBO_TIMEOUT = 1500
    TIP_HIT_RADIUS = 60

    def __init__(self, window_side, damage_callback=None):
        """Initialize ascii sword window with combat, animation, and follow-mode state."""
        super().__init__()
        self.damage_callback = damage_callback
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.sword = [
            '   .',
            '  / \\',
            '  | |',
            '  | |',
            '  | |',
            '  |.|',
            '  |:| ',
            '  |:| ',
            '"-<v>-"',
            '   |',
            '   O',
        ]
        self.sword_height = len(self.sword) * 34

        # Physical Properties
        self.angle = 0
        self.z_scale = 1
        self.y_twist = 1
        self.x, self.y = 0, 0
        self.offset_x = 0
        self.offset_y = 0

        # Combo Logic
        self.combo_step = 0
        self.last_attack_time = 0
        self.is_attacking = False
        self.anim_p = 0

        # Appearing Animation
        self.is_appearing = False
        self.appear_progress = 0
        self.appear_duration = 1.5
        self.appear_start_x = 0
        self.appear_start_y = 0

        # Follow Mode
        self.follow_mode = "mouse"  # "mouse" or "window"
        self.follow_window = None  # Reference to window to follow (e.g., Sharko)

        self.side = "Right"
        self.follow_window_side = window_side

        self.timer = QTimer()
        self.timer.timeout.connect(self.engine_loop)

    def initialize(self, sharko_window=None):
        """Position and start the sword appearance animation relative to a window or the mouse."""
        if sharko_window:
            self.follow_window = sharko_window
            self.follow_mode = "window"
            window_pos = sharko_window.geometry()
            self.appear_start_x = float(window_pos.x() + window_pos.width() // 2)
            self.appear_start_y = float(window_pos.y() + window_pos.height() // 2)
        else:
            self.follow_mode = "mouse"
            cursor_pos = QCursor.pos()
            self.appear_start_x = float(cursor_pos.x())
            self.appear_start_y = float(cursor_pos.y())

        self.x = self.appear_start_x
        self.y = self.appear_start_y
        self.is_appearing = True
        self.appear_progress = 0.0
        self.setGeometry(0, 0, ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1) - 1)
        self.timer.start(30)

    def set_follow_mode(self, mode="mouse", window=None):
        """Change the follow mode between tracking a window or the mouse."""
        if mode == "window" and window:
            self.follow_window = window
            self.follow_mode = "window"
        elif mode == "mouse":
            self.follow_mode = "mouse"
            self.follow_window = None

    def attack(self):
        """Triggers the strike event directly on command."""
        if self.is_attacking or self.is_appearing:
            return

        now = time.time() * 1000
        if now - self.last_attack_time > SwordWindow.COMBO_TIMEOUT:
            self.combo_step = 0

        self.is_attacking = True
        self.anim_p = 0.0
        self.combo_step = (self.combo_step % 5) + 1
        self.last_attack_time = now
        self._damage_fired = False

    def deinitialize(self):
        """Stop the sword animation and cleanup the widget."""
        self.timer.stop()
        self.timer.deleteLater()
        self.timer = None
        self.hide()
        self.deleteLater()

    def engine_loop(self):
        """Main update loop that handles states: following behavior, attack animations, and idle bobbing."""
        if self.is_appearing:
            self.appear_progress += (30 / 1000.0) / self.appear_duration
            if self.appear_progress >= 1.0:
                self.appear_progress = 1.0
                self.is_appearing = False

            self.x = self.appear_start_x
            self.y = self.appear_start_y
            self.angle = 0
            self.z_scale = 1.0
            self.y_twist = 1.0
            self.offset_x = 0
            self.offset_y = 0
        else:
            if self.follow_mode == "window" and self.follow_window:
                # Follow the window
                window_pos = self.follow_window.geometry()
                target_x = float(window_pos.x() + window_pos.width() // 2)
                target_y = float(window_pos.y() + window_pos.height() // 2)
                self.side = "Right" if target_x > (self.width() // 2) else "Left"
                num = 320 // 2 if self.side == self.follow_window_side() else 320
                tx = target_x + (-1 * num - self.offset_x if self.side == "Right" else num + self.offset_x)
                ty = target_y + 120 + self.offset_y
            else:
                # Follow the mouse (default)
                local_pos = self.mapFromGlobal(QCursor.pos())
                mx, my = local_pos.x(), local_pos.y()
                self.side = ("Right" if QCursor.pos().x() > (self.width() // 2) else "Left")
                tx = mx + (-320 - self.offset_x if self.side == "Right" else 320 + self.offset_x)
                ty = my + 120 + self.offset_y

            self.x += (tx - self.x) * 0.15
            self.y += (ty - self.y) * 0.15

        if self.is_attacking and not self.is_appearing:
            self.anim_p += 0.08 * SwordWindow.ANIM_SPEED_MULT
            if self.anim_p >= 1.0:
                self.is_attacking = False
                self.anim_p = 1.0

            p = self.anim_p

            if self.damage_callback is None:
                self._damage_fired = False
            elif not hasattr(self, "_damage_fired") or not self._damage_fired:
                if p >= 0.5:
                    self.damage_callback("sword_slash")
                    self._damage_fired = True

            if self.combo_step == 1:  # OVERHEAD SLAM
                self.offset_x = 0
                self.offset_y = 0
                self.angle = self.lerp(0, 170, self.ease_out_back(p))
                self.z_scale = 1.0 + math.sin(p * math.pi) * 0.5
                self.y_twist = 1.0

            elif self.combo_step == 2:  # DIAGONAL UP-RIP
                self.angle = self.lerp(170, -45, self.ease_in_out(p))
                self.z_scale = 1.5 - (p * 0.5)
                self.y_twist = math.cos(p * math.pi)

            elif self.combo_step == 3:  # CROSS CUT (Horizontal 3D)
                self.angle = self.lerp(-45, 90, self.ease_out_expo(p))
                self.z_scale = 1.0 + math.sin(p * math.pi) * 0.3
                self.y_twist = 1.0 - math.sin(p * math.pi) * 1.8

            elif self.combo_step == 4:  # POMMEL THRUST
                self.angle = self.lerp(190, -40, p)
                self.z_scale = 0.7 + p * 0.8
                self.y_twist = 0.9
                self.offset_x = self.lerp(0, 70, p)

            elif self.combo_step == 5:  # HELIX SPIN

                self.offset_x = self.lerp(700, -200, p)
                self.offset_y = -200
                self.angle = 90
                self.z_scale = self.lerp(1, 1.5, p)

                self.y_twist = 0.5

        else:
            idle_bob = math.sin(time.time() * 3) * 5
            self.angle += (idle_bob - self.angle) * 0.1
            self.z_scale += (1.0 - self.z_scale) * 0.1
            self.y_twist += (1.0 - self.y_twist) * 0.1

        self.update()

    def lerp(self, start, end, t):
        return start + (end - start) * t

    def ease_in_out(self, t):
        return t * t * (3 - 2 * t)

    def ease_out_back(self, t):
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * math.pow(t - 1, 3) + c1 * math.pow(t - 1, 2)

    def ease_out_expo(self, t):
        return 1 if t == 1 else 1 - math.pow(2, -10 * t)

    def paintEvent(self, event):
        """Draw the sword based on states."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Consolas", 26, QFont.Weight.Bold))

        painter.save()
        painter.translate(self.x, self.y)

        if self.side == "Left":
            painter.scale(-1, 1)

        painter.scale(self.z_scale, self.z_scale)
        painter.rotate(self.angle)

        painter.scale(abs(self.y_twist), 1.0)

        total_chars = sum(len(line) for line in self.sword)
        visible_chars = int(total_chars * self.appear_progress + 0.5) if self.is_appearing else total_chars

        char_count = 0
        painter.setPen(QColor(0, 0, 0, 100))

        for i, line in enumerate(self.sword):
            line_start_char = char_count
            line_end_char = char_count + len(line)

            if line_start_char < visible_chars:
                chars_to_show = min(visible_chars - line_start_char, len(line))
                visible_line = line[:chars_to_show]
                painter.drawText(2, int(-self.sword_height + i * 34) + 2, visible_line)

            char_count = line_end_char

        char_count = 0
        if not self.is_attacking:
            painter.setPen(QColor(255, 255, 255))
        else:
            painter.setPen(QColor(255, 130, 130, 100))
        for i, line in enumerate(self.sword):
            line_start_char = char_count
            line_end_char = char_count + len(line)

            if line_start_char < visible_chars:
                chars_to_show = min(visible_chars - line_start_char, len(line))
                visible_line = line[:chars_to_show]
                painter.drawText(0, int(-self.sword_height + i * 34), visible_line)

            char_count = line_end_char

        painter.restore()
