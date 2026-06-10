from        PyQt5.QtWidgets import QLabel, QStyleOptionMenuItem, QProxyStyle, QStyle
from        PyQt5.QtGui import QColor
from        PyQt5.QtCore import Qt, QRect


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

                # Background
                if option.state & QStyle.State_Selected:
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
                    icon_rect = QRect(rect.left() + 4, rect.top() + (rect.height() - icon_size) // 2,
                                      icon_size, icon_size)
                    option.icon.paint(painter, icon_rect, Qt.AlignCenter)

                # Checkmark
                if option.checkType != QStyleOptionMenuItem.NotCheckable:
                    check_rect = QRect(rect.right() - 20, rect.top() + (rect.height() - 16) // 2, 16, 16)
                    if option.checked:
                        painter.fillRect(check_rect, QColor("#D5FFFF"))
                    else:
                        painter.setPen(QColor("#D5FFFF"))
                        painter.drawRect(check_rect)

                # Submenu arrow
                if option.menuItemType == QStyleOptionMenuItem.SubMenu:
                    arrow_rect = QRect(rect.right() - 16, rect.top() + (rect.height() - 12) // 2, 12, 12)
                    painter.setPen(QColor("#D5FFFF"))
                    painter.drawPolyline([
                        arrow_rect.topLeft(),
                        arrow_rect.center(),
                        arrow_rect.bottomLeft()
                    ])

                # Text
                painter.setPen(QColor("#D5FFFF"))
                text_rect = QRect(rect)
                text_rect.setLeft(rect.left() + option.maxIconWidth + 12)

                painter.drawText(
                    text_rect,
                    int(Qt.AlignVCenter | Qt.AlignLeft),
                    option.text
                )

                painter.restore()
                return

        super().drawControl(element, option, painter, widget)


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
        elif event.button() == Qt.LeftButton and hasattr(self.parent_sharko, '_handle_question_click'):
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