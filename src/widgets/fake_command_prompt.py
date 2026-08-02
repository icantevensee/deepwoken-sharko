"""Fake Command Prompt Widget Module

Non interactive fake command prompt window that plays back predefined command/response sequences:
- Mimics a Windows cmd.exe window using:
  + native-like minimize/maximize/close buttons.
  + read-only text area that types commands one character at a time and prints scripted outputs.
- Displays scripted narrative command text without accepting any user input.
- Closes once all sequences are played or an exit command is reached."""

import os
import sys

from PyQt6.QtCore import QFileInfo, Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QTextCursor
from PyQt6.QtWidgets import (
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class NativeWindowButton(QWidget):
    def __init__(self, button_type, parent=None, scale_factor=1):
        """Initialize native style window button widget."""
        super().__init__(parent)
        self.button_type = button_type
        self.scale_factor = scale_factor
        self.setFixedSize(int(46 * self.scale_factor), int(32 * self.scale_factor))

    def paintEvent(self, event):
        """Draw the minimize, maximize, or close icon."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

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
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen_close = QPen(QColor(204, 204, 204), max(1.2, 1.2 * self.scale_factor))
            painter.setPen(pen_close)
            painter.drawLine(cx - size, cy - size, cx + size, cy + size)
            painter.drawLine(cx + size, cy - size, cx - size, cy + size)


class FakeCommandPrompt(QMainWindow):
    def __init__(self, sequences, width, height, x, y, scale_factor=1, pause_between_ms=1800):
        """Initialize the fake command prompt window's text sequences and layout parameters."""
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
        """Build the faux command prompt UI, including title bar, native buttons, and text area."""
        self.resize(self.win_width, self.win_height)

        self.move(self.win_x, self.win_y)

        # Enforce stealth window properties
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowStaysOnTopHint
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
        self.text_area.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

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
        """Start typing the next command sequence or schedule window closure when sequences are exhausted."""
        if self.sequence_index < len(self.sequences):
            self.char_index = 0
            self.typing_timer.start(40)
        else:
            QTimer.singleShot(2000, self.close)

    def type_next_character(self):
        """Append the next character of the current command to the text area, or move on when finished."""
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
        """Insert the response for a fake command, then move onto the next sequence."""
        _, current_response = self.sequences[self.sequence_index]
        output = f"\n{current_response}\n\nC:\\Users\\Admin>"
        self.text_area.insertPlainText(output)
        self.text_area.moveCursor(QTextCursor.End)
        self.sequence_index += 1
        QTimer.singleShot(self.pause_between_ms, self.start_next_sequence)
