"""Base Widget Components Module

UI components shared across the Sharko application:
- MenuStyle: QProxyStyle that renders menus with QPainter enabling sophisticated customization.
- VolumeSlider: Slider that can be embedded in menus without closing them.
- SharkoLabel: The main image label that forwards mouse events to the core logic."""

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QLabel,
    QProxyStyle,
    QStyle,
    QStyleOptionMenuItem,
    QWidget,
)


class MenuStyle(QProxyStyle):

    def drawPrimitive(self, element, option, painter, widget=None):
        """Primitive painting for menu and frame elements to use a solid black background."""
        if element in (
            QStyle.PrimitiveElement.PE_PanelMenu,
            QStyle.PrimitiveElement.PE_FrameMenu,
            QStyle.PrimitiveElement.PE_Frame,
            QStyle.PrimitiveElement.PE_FrameWindow,
        ):
            painter.save()
            painter.fillRect(option.rect, QColor("#000000"))
            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)

    def drawControl(self, element, option, painter, widget=None):
        """Painted menu items with tinted backgrounds, icons, checkmarks, submenu arrows, and text colors."""
        if element == QStyle.ControlElement.CE_MenuItem:
            if isinstance(option, QStyleOptionMenuItem):
                painter.save()

                rect = option.rect

                is_enabled = option.state & QStyle.StateFlag.State_Enabled

                if not is_enabled:
                    painter.fillRect(rect, QColor("#0a0a15"))
                elif option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(rect, QColor("#0300A4"))
                else:
                    painter.fillRect(rect, QColor("#02002A"))

                # Separator
                if option.menuItemType == QStyleOptionMenuItem.MenuItemType.Separator:
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
                    option.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

                # Checkmark
                if option.checkType != QStyleOptionMenuItem.CheckType.NotCheckable:
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
                if option.menuItemType == QStyleOptionMenuItem.MenuItemType.SubMenu:
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
                    text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), option.text
                )

                painter.restore()
                return

        super().drawControl(element, option, painter, widget)


class VolumeSlider(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, initial_value=50, parent=None):
        """Initialize volume slider widget with state for value, dragging, and track geometry."""
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
        """Update the slider value, repaint, and emit a signal when the value changes."""
        new_value = max(0, min(100, value))
        if self.value != new_value:
            self.value = new_value
            self.update()
            self.valueChanged.emit(self.value)

    def eventFilter(self, obj, event):
        """Intercept mouse events to implement drag-based slider interaction without closing parent menus."""
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseMove,
        ):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.is_dragging = True
                self.setValue(self._value_from_pos(event.x()))
            elif event.type() == QEvent.Type.MouseMove and self.is_dragging:
                self.setValue(self._value_from_pos(event.x()))
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.is_dragging = False
            return True
        return super().eventFilter(obj, event)

    def _value_from_pos(self, pos_x):
        """Convert an X coordinate within the track rect into a 0–100 slider value."""
        track_left = self.track_rect.left()
        track_width = self.track_rect.width()
        if track_width <= 0:
            return 0
        ratio = (pos_x - track_left) / float(track_width)
        return int(max(0.0, min(1.0, ratio)) * 100)

    def paintEvent(self, event):
        """Draw the slider’s background, label, track, filled progress, and handle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor("#02002A"))

        painter.setPen(QColor("#D5FFFF"))
        painter.setFont(QFont("Arial", 9, QFont.Weight.Normal))
        text_rect = QRect(14, 0, 65, self.height())
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), "Volume:")

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

        if event.button() == Qt.MouseButton.MiddleButton:
            self.drag_start_x = int(event.position().x())
            self.drag_start_y = int(event.position().y())
            self.parent_sharko._middle_button_pressed(event)
        elif event.button() == Qt.MouseButton.LeftButton and hasattr(
            self.parent_sharko, "_handle_question_click"
        ):
            self.parent_sharko._handle_question_click(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse button release."""
        if self.parent_sharko is None:
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self.parent_sharko._middle_button_released(event)
        elif event.button() == Qt.MouseButton.RightButton:
            self.parent_sharko.menu.popup(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        """Handle mouse movement while middle button is held."""
        if self.parent_sharko is None:
            return

        if event.buttons() == Qt.MouseButton.MiddleButton:
            self.parent_sharko._middle_button_hold_move(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click."""
        if self.parent_sharko is None:
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self.parent_sharko.menu.popup(event.globalPosition().toPoint())
