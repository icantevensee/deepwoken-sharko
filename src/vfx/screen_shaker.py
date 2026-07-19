"""Screen Shaker Module

- Provides a full-screen, translucent overlay that captures the desktop and applies time-varying offsets to create a camera shake effect synchronized with combat events.
- Uses dxcam to grab BGRA frames, wraps them in QImage for zero-copy rendering, and animates positional noise with exponential decay to simulate impact and settling.
- This module is only imported and activated when screen shake is actually needed, to avoid memory overhead of dxcam when unused."""

import math
import random
import time
from ctypes import c_bool, c_uint32, c_void_p, windll

from PyQt5.QtCore import (
    Qt,
    QTimer,
)
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QWidget

from constants import SharkoConstants


class ScreenShaker(QWidget):
    def __init__(self):
        """Initialize the screen shake widget and dxcam capture resources.
        dxcam takes up a lot of memory so it's only imported if it's actually ever used. Large ~25 mb decrease in ram if not imported."""
        super().__init__()
        import dxcam

        user32 = windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [c_void_p, c_uint32]
        user32.SetWindowDisplayAffinity.restype = c_bool
        self.camera = dxcam.create(max_buffer_len=1, output_color="BGRA")

        self.width = user32.GetSystemMetrics(0)
        self.height = user32.GetSystemMetrics(1)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowTransparentForInput
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, self.width, self.height - 1)
        user32.SetWindowDisplayAffinity(int(self.winId()), SharkoConstants.WDA_EXCLUDEFROMCAPTURE)
        self.captured_image = None
        self.current_frame = None
        self.intensity = 0
        self.start_time = 0
        self.duration = 0
        self.sustained = False

        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.process_shake_step)

        self.offset_x = 0
        self.offset_y = 0

    def shake(self, duration_ms=450, intensity=30, sustained=False):
        """Start a shake effect with a given duration and intensity."""
        self.intensity = intensity
        self.sustained = sustained
        self.duration = duration_ms / 1000.0

        self.start_time = time.time()
        self.show()

        self.loop_timer.start(30)

    def process_shake_step(self):
        """Capture the current screen frame, compute shake offsets, and update the overlay position."""
        elapsed = time.time() - self.start_time

        if elapsed >= self.duration:
            self.stop_and_reset()
            return

        frame = self.camera.grab_view()
        if frame is not None:
            # Keep a strong reference to the frame array so its memory address stays valid
            self.current_frame = frame

            height, width, channels = frame.shape
            bytes_per_line = channels * width

            # Build the zero-copy QImage wrapper. Use Format_ARGB32 to match raw DXcam BGRA.
            self.captured_image = QImage(
                self.current_frame.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_ARGB32
            )

        progress = elapsed / self.duration
        if self.sustained:
            if progress < 0.8:
                decay = 1.0
            else:
                tail = (progress - 0.8) / 0.2
                decay = math.exp(-4.5 * tail)
            current_intensity = self.intensity * decay
            frequency_multiplier = 1.0
        else:
            decay = math.exp(-4.5 * progress)
            current_intensity = self.intensity * decay
            frequency_multiplier = 1.0 + (progress * 1.5)

        t_ms = elapsed * 1000.0

        speed_x = 0.01 * frequency_multiplier
        speed_y = 0.02 * frequency_multiplier
        randomness = 0.35

        sin_wave = math.sin(t_ms * speed_x) * current_intensity
        cos_wave = math.cos(t_ms * speed_y) * current_intensity
        rand_noise_x = random.uniform(-current_intensity, current_intensity) * randomness
        rand_noise_y = random.uniform(-current_intensity, current_intensity) * randomness

        self.offset_x = int(sin_wave + rand_noise_x)
        self.offset_y = int(cos_wave + rand_noise_y)
        self.raise_()
        self.particles_manager.raise_()
        self.update()

    def stop_and_reset(self):
        """Stop the shake loop, free captured image from memory, and restore offsets to their default state."""
        self.loop_timer.stop()
        self.captured_image = None
        self.current_frame = None
        self.offset_x = 0
        self.offset_y = 0
        self.update()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.captured_image:
            painter.fillRect(0, 0, self.width, self.height, Qt.transparent)
            return

        painter.fillRect(0, 0, self.width, self.height, Qt.black)
        painter.drawImage(self.offset_x, self.offset_y, self.captured_image)

    def deinitialize(self):
        """Release some dxcam resources and cleanup the shaker."""
        if hasattr(self, "loop_timer") and self.loop_timer:
            self.loop_timer.stop()
            self.loop_timer.deleteLater()
            self.loop_timer = None
        if hasattr(self, "camera") and self.camera:
            self.camera.release()
            self.camera = None
        self.particles_manager = None
        self.captured_image = None
        self.current_frame = None
        self.hide()
        self.deleteLater()
