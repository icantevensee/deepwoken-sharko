"""Warnings Manager Module

Overlay and engine for drawing animated red warning stripes used to telegraph incoming area attacks:
- Each warning region is represented by a WarningInstance that drives a looping opacity animation with a timed fade-out.
- MultiWarningOverlay manages the collection of warning instances."""

import win32api
from PyQt6.QtCore import (
    QEasingCurve,
    QRect,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class WarningInstance:
    """Helper class to create, manage, and clean up warnings."""

    def __init__(self, rect, duration_ms, parent_update_func, shape="rect", on_complete=None):
        """Initialize a single warning region with an opacity animation and exit timer."""
        self.rect = rect
        self.shape = shape
        self.opacity = 0
        self.is_fading_out = False
        self.exit_timer = None  # Store timer reference for cleanup
        self.on_complete = on_complete  # Callback when warning expires
        self.deleted = False

        self.anim = QVariantAnimation()
        self.anim.setDuration(300)
        self.anim.setStartValue(0)
        self.anim.setEndValue(180)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.anim.valueChanged.connect(self.update_val)
        self.update_callback = parent_update_func

        self.anim.finished.connect(self.loop_logic)
        self.anim.start()

        self.exit_timer = QTimer()
        self.exit_timer.setSingleShot(True)
        self.exit_timer.timeout.connect(self.start_exit)
        self.exit_timer.start(duration_ms)

    def update_val(self, val):
        """Update the current opacity value and trigger a repaint of the parent widget."""
        self.opacity = val
        self.update_callback()

    def loop_logic(self):
        """Control the looping behavior of the warning opacity animation and handle fade-out completion."""
        if self.is_fading_out and self.anim.direction() == QVariantAnimation.Direction.Backward:
            self.opacity = -1
            if self.on_complete:
                self.on_complete()
            return

        new_dir = QVariantAnimation.Direction.Backward if self.anim.direction() == QVariantAnimation.Direction.Forward else QVariantAnimation.Direction.Forward
        self.anim.setDirection(new_dir)
        self.anim.start()

    def start_exit(self):
        """Begin the warning exit process by stopping the lifetime timer and scheduling for deletion on next 0 transparency update."""
        self.exit_timer.deleteLater()
        self.is_fading_out = True

    def cleanup(self):
        """Stop and cleanup this warning instance."""
        try:
            if self.exit_timer:
                self.exit_timer.stop()
                try:
                    self.exit_timer.timeout.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self.exit_timer.deleteLater()
                self.exit_timer = None
        except (RuntimeError, AttributeError):
            pass
        try:
            self.anim.stop()
            try:
                self.anim.valueChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            try:
                self.anim.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.anim.deleteLater()
            self.anim = None
        except (RuntimeError, TypeError, AttributeError):
            pass


class MultiWarningOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1) - 1)
        self.show()

        self.active_warnings = []

    def trigger_warning(self, width, height, duration_ms, x, y, shape="rect", on_complete=None):
        """Create a new warning instance covering a given rectangle and add it to the overlay."""
        rect = QRect(x, y, width, height)

        new_warning = WarningInstance(rect, duration_ms, self.update, shape, on_complete)
        self.active_warnings.append(new_warning)

    def trigger_circular_warning(self, center_x, center_y, radius, duration_ms, on_complete=None):
        """Helper to trigger a circular warning using center coordinates and a radius."""
        diameter = radius * 2
        top_left_x = center_x - radius
        top_left_y = center_y - radius
        self.trigger_warning(diameter, diameter, duration_ms, top_left_x, top_left_y, "circle", on_complete)

    def paintEvent(self, event):
        """Draw all active warning stripes and borders onto the overlay."""
        from PyQt6.QtGui import QPainterPath  # Import needed for circular clipping

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)

        for i in range(len(self.active_warnings) - 1, -1, -1):
            w_inst = self.active_warnings[i]

            if w_inst.opacity == -1:
                self.active_warnings.pop(i)
                continue

            color = QColor(255, 0, 0, w_inst.opacity)
            rect = w_inst.rect
            x, y, w, h = rect.getRect()

            painter.save()

            # Apply clipping shape
            if w_inst.shape == "circle":
                clip_path = QPainterPath()
                clip_path.addEllipse(float(x), float(y), float(w), float(h))
                painter.setClipPath(clip_path)
            else:
                painter.setClipRect(rect)

            # Stripes
            painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            for j in range(-h, w + h, 25):
                painter.drawLine(x + j, y, x + j + h, y + h)
            painter.restore()

            # Draw outer border
            painter.setPen(QPen(color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.MiterJoin))
            if w_inst.shape == "circle":
                painter.drawEllipse(rect)
            else:
                painter.drawRect(rect)

    def deinitialize(self):
        """Clean up all warning instances and delete the overlay widget."""
        for w in self.active_warnings:
            w.cleanup()
        self.active_warnings.clear()
        self.deleteLater()
