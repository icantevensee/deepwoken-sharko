"""Clipper that isolates a frameless widget window to the main monitor using non-blocking updates."""
from PyQt5.QtCore import QObject, QEvent, QRect, QPoint
from PyQt5.QtGui import QRegion
from PyQt5.QtWidgets import QApplication


class MainMonitorClipper(QObject):

    def __init__(self, target_widget):
        super().__init__(target_widget)
        self.target = target_widget
        self._is_updating = False

        desktop = QApplication.desktop()
        self.primary_geo = desktop.screenGeometry(0)

        self._last_processed_pos = QPoint(-99999, -99999)

        self.target.installEventFilter(self)
        self.update_mask()

    def destroy_clipper(self):
        """Cleanly drops layout tracking filters and clears active masks."""
        if self.target:
            self.target.removeEventFilter(self)
            self.target.setMask(QRegion())
            self.target = None
        self.deleteLater()

    def eventFilter(self, obj, event):
        if not self._is_updating and obj == self.target and event.type() in (QEvent.Move, QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
            self.update_mask()
        return super().eventFilter(obj, event)

    def update_mask(self):
        if not self.target or not self.target.isVisible():
            return

        current_pos = self.target.pos()
        if current_pos == self._last_processed_pos:
            return

        self._is_updating = True
        try:
            widget_geo = self.target.geometry()
            intersecting_rect = widget_geo.intersected(self.primary_geo)

            if intersecting_rect.isEmpty() or intersecting_rect.width() <= 0 or intersecting_rect.height() <= 0:
                hidden_region = QRegion(-1, -1, 1, 1)
                self.target.setMask(hidden_region)
            else:
                local_top_left = self.target.mapFromGlobal(intersecting_rect.topLeft())
                local_rect = QRect(
                    local_top_left.x(),
                    local_top_left.y(),
                    intersecting_rect.width(),
                    intersecting_rect.height()
                )

                self.target.setMask(QRegion(local_rect))
                self.target.update()

            self._last_processed_pos = current_pos
        finally:
            self._is_updating = False
