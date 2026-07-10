"""
Widgets: assortment of large PyQt5 objects that don't fall into any of the other files:
-Menu Menustyle
-Volume slider
-Sharko label(image display of the main sharko window)
-Ascii sword window
-Fake command prompt
-Native windows button object
"""

import math
import os
import sys
import time

import ctypes

from PyQt5.QtCore import QEvent, QFileInfo, QPoint, QRect, Qt, QTimer, pyqtSignal,QSize
from PyQt5.QtGui import QColor, QCursor, QFont, QPainter, QPalette, QPen, QTextCursor
from PyQt5.QtWidgets import (
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProxyStyle,
    QStyle,
    QStyleOptionMenuItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MenuStyle(QProxyStyle):

    # Remove the white border around the menu
    def drawPrimitive(self, element, option, painter, widget=None):
        # Remove ALL menu borders and frames
        if element in (
            QStyle.PE_PanelMenu,
            QStyle.PE_FrameMenu,
            QStyle.PE_Frame,
            QStyle.PE_FrameWindow,
        ):
            painter.save()
            painter.fillRect(option.rect, QColor("#000000"))
            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.CE_MenuItem:
            if isinstance(option, QStyleOptionMenuItem):
                painter.save()

                rect = option.rect

                is_enabled = option.state & QStyle.State_Enabled

                if not is_enabled:
                    painter.fillRect(rect, QColor("#0a0a15"))
                elif option.state & QStyle.State_Selected:
                    painter.fillRect(rect, QColor("#0300A4"))
                else:
                    painter.fillRect(rect, QColor("#02002A"))

                # Separator
                if option.menuItemType == QStyleOptionMenuItem.Separator:
                    painter.fillRect(rect, QColor("#005C75"))
                    painter.restore()
                    return

                # Icon
                icon_size = option.maxIconWidth
                if option.icon and not option.icon.isNull():
                    icon_rect = QRect(
                        rect.left() + 4,
                        rect.top() + (rect.height() - icon_size) // 2,
                        icon_size,
                        icon_size,
                    )
                    option.icon.paint(painter, icon_rect, Qt.AlignCenter)

                # Checkmark
                if option.checkType != QStyleOptionMenuItem.NotCheckable:
                    check_rect = QRect(
                        rect.right() - 20,
                        rect.top() + (rect.height() - 16) // 2,
                        16,
                        16,
                    )
                    check_color = (QColor("#D5FFFF") if is_enabled else QColor("#808080"))
                    if option.checked:
                        # Dim checkmark if disabled
                        painter.fillRect(check_rect, check_color)
                    else:
                        # Dim checkmark outline if disabled
                        painter.setPen(check_color)
                        painter.drawRect(check_rect)

                # Submenu arrow
                if option.menuItemType == QStyleOptionMenuItem.SubMenu:
                    arrow_rect = QRect(
                        rect.right() - 16,
                        rect.top() + (rect.height() - 12) // 2,
                        12,
                        12,
                    )
                    # Dim arrow if disabled
                    arrow_color = (QColor("#D5FFFF") if is_enabled else QColor("#808080"))
                    painter.setPen(arrow_color)
                    painter.drawPolyline(
                        [
                            arrow_rect.topLeft(),
                            arrow_rect.center(),
                            arrow_rect.bottomLeft(),
                        ]
                    )

                # Text
                # Dim text if disabled
                text_color = QColor("#808080") if not is_enabled else QColor("#D5FFFF")
                painter.setPen(text_color)
                text_rect = QRect(rect)
                text_rect.setLeft(rect.left() + option.maxIconWidth + 12)

                painter.drawText(
                    text_rect, int(Qt.AlignVCenter | Qt.AlignLeft), option.text
                )

                painter.restore()
                return

        super().drawControl(element, option, painter, widget)


class VolumeSlider(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, initial_value=50, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self.setMinimumWidth(220)

        self.value = max(0, min(100, initial_value))
        self.is_dragging = False

        self.track_rect = QRect()
        self.handle_center = QPoint()
        self.handle_radius = 6

        self.setMouseTracking(True)

        self.installEventFilter(self)

    def setValue(self, value):
        new_value = max(0, min(100, value))
        if self.value != new_value:
            self.value = new_value
            self.update()
            self.valueChanged.emit(self.value)

    def eventFilter(self, obj, event):
        """Prevents parent QMenu from automatically closing during interactive drag operations."""
        if event.type() in (
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
            QEvent.MouseMove,
        ):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.is_dragging = True
                self.setValue(self._value_from_pos(event.x()))
            elif event.type() == QEvent.MouseMove and self.is_dragging:
                self.setValue(self._value_from_pos(event.x()))
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.is_dragging = False
            return True
        return super().eventFilter(obj, event)

    def _value_from_pos(self, pos_x):
        track_left = self.track_rect.left()
        track_width = self.track_rect.width()
        if track_width <= 0:
            return 0
        ratio = (pos_x - track_left) / float(track_width)
        return int(max(0.0, min(1.0, ratio)) * 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor("#02002A"))

        painter.setPen(QColor("#D5FFFF"))
        painter.setFont(QFont("Arial", 9, QFont.Normal))
        text_rect = QRect(14, 0, 65, self.height())
        painter.drawText(text_rect, int(Qt.AlignVCenter | Qt.AlignLeft), "Volume:")

        track_left = text_rect.right() + 8
        track_right = self.width() - 16
        track_width = max(10, track_right - track_left)
        track_y = self.height() // 2

        self.track_rect = QRect(track_left, track_y - 3, track_width, 6)

        painter.fillRect(self.track_rect, QColor("#000000"))
        painter.setPen(QPen(QColor("#005C75"), 1))
        painter.drawRect(self.track_rect)

        handle_x = int(track_left + (self.value / 100.0) * track_width)
        progress_rect = QRect(track_left, track_y - 3, handle_x - track_left, 6)
        painter.fillRect(progress_rect, QColor("#0300A4"))

        self.handle_center = QPoint(handle_x, track_y)
        painter.setBrush(QColor("#D5FFFF"))
        painter.setPen(QPen(QColor("#0300A4"), 1))
        painter.drawEllipse(self.handle_center, self.handle_radius, self.handle_radius)


class SharkoLabel(QLabel):
    """Custom QLabel for Sharko that handles mouse events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_sharko = None
        self.drag_start_x = 0
        self.drag_start_y = 0

    def mousePressEvent(self, event):
        """Handle mouse button press."""
        if self.parent_sharko is None:
            return

        if event.button() == Qt.MiddleButton:
            self.drag_start_x = event.x()
            self.drag_start_y = event.y()
            self.parent_sharko._middle_button_pressed(event)
        elif event.button() == Qt.LeftButton and hasattr(
            self.parent_sharko, "_handle_question_click"
        ):
            self.parent_sharko._handle_question_click(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse button release."""
        if self.parent_sharko is None:
            return

        if event.button() == Qt.MiddleButton:
            self.parent_sharko._middle_button_released(event)
        elif event.button() == Qt.RightButton:
            self.parent_sharko.menu.popup(event.globalPos())

    def mouseMoveEvent(self, event):
        """Handle mouse movement while middle button is held."""
        if self.parent_sharko is None:
            return

        if event.buttons() == Qt.MiddleButton:
            self.parent_sharko._middle_button_hold_move(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click."""
        if self.parent_sharko is None:
            return

        if event.button() == Qt.MiddleButton:
            self.parent_sharko.menu.popup(event.globalPos())


class SwordWindow(QWidget):
    ANIM_SPEED_MULT = 1.0
    COMBO_TIMEOUT = 1500
    TIP_HIT_RADIUS = 60

    def __init__(self, window_side, damage_callback=None):
        super().__init__()
        self.damage_callback = damage_callback
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

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
        self.setGeometry(0, 0, ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
        self.timer.start(16)

    def set_follow_mode(self, mode="mouse", window=None):
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
        self.timer.stop()
        self.timer.deleteLater()
        self.timer = None
        self.hide()
        self.deleteLater()

    def engine_loop(self):
        if self.is_appearing:
            self.appear_progress += (16 / 1000.0) / self.appear_duration
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
                    print("Damage callback fired!")
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
                self.angle = self.lerp(90, 90, p)
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Consolas", 26, QFont.Bold))

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
        if self.is_attacking == False:
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


class NativeWindowButton(QWidget):
    def __init__(self, button_type, parent=None, scale_factor=1):
        super().__init__(parent)
        self.button_type = button_type
        self.scale_factor = scale_factor
        self.setFixedSize(int(46 * self.scale_factor), int(32 * self.scale_factor))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        pen_width = max(1, int(1 * self.scale_factor))
        pen = QPen(QColor(204, 204, 204), pen_width)
        painter.setPen(pen)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        size = int(10 * self.scale_factor) // 2

        if self.button_type == "min":
            painter.drawLine(cx - size, cy, cx + size, cy)
        elif self.button_type == "max":
            painter.drawRect(cx - size, cy - size, size * 2, size * 2)
        elif self.button_type == "close":
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen_close = QPen(QColor(204, 204, 204), max(1.2, 1.2 * self.scale_factor))
            painter.setPen(pen_close)
            painter.drawLine(cx - size, cy - size, cx + size, cy + size)
            painter.drawLine(cx + size, cy - size, cx - size, cy + size)


class FakeCommandPrompt(QMainWindow):
    def __init__(
        self, sequences, width, height, x, y, scale_factor=1, pause_between_ms=1800
    ):
        super().__init__()
        self.sequences = sequences
        self.scale_factor = scale_factor
        self.win_width = width
        self.win_height = height
        self.win_x = x
        self.win_y = y
        self.pause_between_ms = pause_between_ms

        self.sequence_index = 0
        self.char_index = 0
        self.init_ui()

    def init_ui(self):
        self.resize(self.win_width, self.win_height)

        self.move(self.win_x, self.win_y)

        # Enforce stealth window properties
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowTransparentForInput
            | Qt.WindowStaysOnTopHint
        )

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        window_layout = QVBoxLayout(central_widget)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)

        # Title Bar Construction
        title_bar = QWidget(central_widget)
        title_bar.setFixedHeight(int(32 * self.scale_factor))
        title_bar.setStyleSheet("background-color: #202020; border-top: 1px solid #333333;")

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(int(10 * self.scale_factor), 0, 0, 0)
        title_layout.setSpacing(0)

        # Native Icon Provider Hook
        self.icon_label = QLabel(title_bar)
        icon_size = int(16 * self.scale_factor)
        self.icon_label.setFixedSize(icon_size, icon_size)
        if sys.platform == "win32":
            cmd_path = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cmd.exe")
            if os.path.exists(cmd_path):
                file_info = QFileInfo(cmd_path)
                real_cmd_icon = QFileIconProvider().icon(file_info)
                pixmap = real_cmd_icon.pixmap(QSize(icon_size, icon_size))
                self.icon_label.setPixmap(pixmap)
        title_layout.addWidget(self.icon_label)

        title_label = QLabel("  Command Prompt", title_bar)
        font_size = int(16 * self.scale_factor)
        title_label.setStyleSheet(f"color: #CCCCCC; font-family: 'Segoe UI', Arial; font-size: {font_size}px;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()
        title_layout.addWidget(NativeWindowButton("min", title_bar, self.scale_factor))
        title_layout.addWidget(NativeWindowButton("max", title_bar, self.scale_factor))
        title_layout.addWidget(NativeWindowButton("close", title_bar, self.scale_factor))
        window_layout.addWidget(title_bar)

        self.text_area = QTextEdit(central_widget)
        self.text_area.setStyleSheet("background-color: #000000; border-left: 1px solid #5A5A5A; border-right: 1px solid #5A5A5A; border-bottom: 1px solid #5A5A5A;")
        self.text_area.setTextInteractionFlags(Qt.NoTextInteraction)

        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(0, 0, 0))
        palette.setColor(QPalette.Text, QColor(204, 204, 204))
        self.text_area.setPalette(palette)

        text_font_size = int(12 * self.scale_factor)
        cmd_font = QFont("Consolas", text_font_size)
        self.text_area.setFont(cmd_font)

        window_layout.addWidget(self.text_area)

        startup_text = (
            "Microsoft Windows\n"
            "(c) Microsoft Corporation. All rights reserved.\n\n"
            "C:\\Users\\Admin>"
        )
        self.text_area.setText(startup_text)
        self.text_area.moveCursor(QTextCursor.End)

        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.type_next_character)
        QTimer.singleShot(800, self.start_next_sequence)

    def mousePressEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        event.ignore()

    def keyReleaseEvent(self, event):
        event.ignore()

    def start_next_sequence(self):
        if self.sequence_index < len(self.sequences):
            self.char_index = 0
            self.typing_timer.start(40)
        else:
            QTimer.singleShot(2000, self.close)

    def type_next_character(self):
        current_command, _ = self.sequences[self.sequence_index]
        if self.char_index < len(current_command):
            char = current_command[self.char_index]
            self.text_area.insertPlainText(char)
            self.char_index += 1
        else:
            self.typing_timer.stop()
            if current_command.strip().lower() == "exit":
                QTimer.singleShot(300, self.close)
            else:
                QTimer.singleShot(500, self.display_response)

    def display_response(self):
        _, current_response = self.sequences[self.sequence_index]
        output = f"\n{current_response}\n\nC:\\Users\\Admin>"
        self.text_area.insertPlainText(output)
        self.text_area.moveCursor(QTextCursor.End)
        self.sequence_index += 1
        QTimer.singleShot(self.pause_between_ms, self.start_next_sequence)
