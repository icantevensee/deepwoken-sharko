import time
from ctypes import windll, c_void_p, c_uint32, c_bool

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QRadialGradient, QColor, QPixmap
from PyQt6.QtWidgets import QWidget

from constants import SharkoConstants


class HurtFlash:
    """Tracks an individual hit flash state with explicit slot memory structures"""
    def __init__(self):
        self.start_time = 0.0
        self.duration = 0.0
        self.is_active = False

    def activate(self, duration_ms):
        self.start_time = time.perf_counter()
        self.duration = duration_ms / 1000.0
        self.is_active = True

    def get_intensity(self):
        if not self.is_active:
            return 0.0

        elapsed = time.perf_counter() - self.start_time
        if elapsed >= self.duration or elapsed < 0:
            self.is_active = False
            return 0.0

        progress = elapsed / self.duration

        if progress < 0.2:
            intensity = (progress / 0.2) * 0.8
        else:
            t = (progress - 0.2) / 0.8
            intensity = 0.8 * (1.0 - t * t)

        return max(0.0, min(intensity, 0.8))


class HurtVignetteOverlay(QWidget):
    _flash_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._intensity = 0.0
        self.width = windll.user32.GetSystemMetrics(0)
        self.height = windll.user32.GetSystemMetrics(1)

        self.RES_SCALE = 0.15
        self.buffer_width = int(self.width * self.RES_SCALE)
        self.buffer_height = int((self.height - 1) * self.RES_SCALE)

        self.MAX_CONCURRENT_FLASHES = 4
        self.flash_pool = [HurtFlash() for _ in range(self.MAX_CONCURRENT_FLASHES)]
        self.pool_index = 0

        user32 = windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [c_void_p, c_uint32]
        user32.SetWindowDisplayAffinity.restype = c_bool

        self.width = user32.GetSystemMetrics(0)
        self.height = user32.GetSystemMetrics(1)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(0, 0, self.width, self.height - 1)
        user32.SetWindowDisplayAffinity(int(self.winId()), SharkoConstants.WDA_EXCLUDEFROMCAPTURE)

        self._base_vignette_mask = QPixmap(self.buffer_width, self.buffer_height)
        self._base_vignette_mask.fill(Qt.GlobalColor.transparent)

        mask_painter = QPainter(self._base_vignette_mask)
        mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        center = self._base_vignette_mask.rect().center()
        radius = max(self.buffer_width, self.buffer_height) / 1.2
        gradient = QRadialGradient(float(center.x()), float(center.y()), float(radius))

        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.6, QColor(139, 0, 0, int(255 * 0.3)))
        gradient.setColorAt(1.0, QColor(139, 0, 0, 255))

        mask_painter.fillRect(self._base_vignette_mask.rect(), gradient)
        mask_painter.end()

        self._flash_signal.connect(self._handle_flash_hurt, Qt.ConnectionType.QueuedConnection)

        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.update_intensity_loop)

        self.show()

    def flash_hurt(self, duration=500):
        self._flash_signal.emit(duration)

    def _handle_flash_hurt(self, duration):
        """Handle flash_hurt on the main thread, activating a slot and starting the timer if needed."""
        slot = self.flash_pool[self.pool_index]
        slot.activate(duration)
        self.pool_index = (self.pool_index + 1) % self.MAX_CONCURRENT_FLASHES

        if self.loop_timer and not self.loop_timer.isActive():
            self.loop_timer.start(30)

    def update_intensity_loop(self):
        """Update the current vignette intensity and stop the timer when no flashes are active."""
        max_calculated_intensity = 0.0
        has_active_elements = False

        for flash in self.flash_pool:
            intensity = flash.get_intensity()
            if flash.is_active:
                has_active_elements = True
                if intensity > max_calculated_intensity:
                    max_calculated_intensity = intensity

        if has_active_elements:
            self._intensity = max_calculated_intensity
            self.update()
        else:
            if self._intensity > 0.0:
                self._intensity = 0.0
                self.update()

            if self.loop_timer and self.loop_timer.isActive():
                self.loop_timer.stop()

    def paintEvent(self, event):
        if self._intensity <= 0.0 or self._base_vignette_mask is None:
            return
        widget_painter = QPainter(self)
        widget_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        widget_painter.setOpacity(self._intensity)
        widget_painter.drawPixmap(self.rect(), self._base_vignette_mask)
        widget_painter.end()

    def deinitialize(self):
        if hasattr(self, "loop_timer") and self.loop_timer:
            try:
                self.loop_timer.timeout.disconnect(self.update_intensity_loop)
            except (RuntimeError, TypeError):
                pass
            self.loop_timer.stop()
            self.loop_timer.deleteLater()
            self.loop_timer = None
        self.flash_pool.clear()
        self._base_vignette_mask = None
        self.deleteLater()
