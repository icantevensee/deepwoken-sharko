import sys
import math
import random
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPainter, QPixmap, QLinearGradient, QColor, QFont, QFontDatabase, QPainterPath, QPen
from PyQt5.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint
from ctypes import windll
# --- PATHS ---
PARRY_IMAGES = [
    'assets/particlesUI/sparkle2.png', 
    'assets/particlesUI/spark.png',
    'assets/particlesUI/ring.png'
]
# Ensure these files exist in your project folder
BAR_IMG_PATH = "assets/UI/boss_bar_border.png"
MARKER_PATH = "assets/UI/boss_bar_pins.png"
CENTER_ICON_PATH = "assets/UI/boss_bar_skull.png"
FONT_PATH = "assets/fonts/Boss_Font.otf"

class ScalableHealthBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. Window Setup: Transparent, Always on Top, Click-Through
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowTransparentForInput |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Default Size
        self.setMinimumSize(400, 160)
        
        # 2. Load Resources
        self.bar_img = QPixmap(BAR_IMG_PATH)
        self.marker_img = QPixmap(MARKER_PATH)
        self.icon_img = QPixmap(CENTER_ICON_PATH)
        self.original_crop_border = 16 
        self.percentage = 1.0
        self.current_percentage = 1.0

        # 3. Health Animation Timer (The "Sliding" fill effect)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_health_fill)
        self.animation_timer.start(16)

        # 4. Slide Animation Setup (The "In/Out" movement)
        self._pos_animation = QPropertyAnimation(self, b"anim_pos")
        self._pos_animation.setDuration(600)
        self._pos_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 5. Font Setup
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        if font_id != -1:
            family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.custom_font = QFont(family, 22)
        else:
            self.custom_font = QFont("Arial", 22)
        screen_w = windll.user32.GetSystemMetrics(0)
        self.initial_x = (screen_w - self.width()) // 2
        self.move(self.initial_x, -self.height())

    # --- ANIMATION PROPERTY ---
    # We use 'anim_pos' to avoid clashing with the built-in 'pos()' method
    @pyqtProperty(QPoint)
    def anim_pos(self): 
        return self.pos()
    
    @anim_pos.setter
    def anim_pos(self, p): 
        self.move(p)

    def slide_in(self):
        """Slides the bar down. Call this to 'create' it on screen."""
        self._pos_animation.stop() # Stop any current movement
        
        screen_w = windll.user32.GetSystemMetrics(0)
        target_x = (screen_w - self.width()) // 2
        target_y = 10 
        
        # If it was hidden or deleted, we ensure it's visible and positioned correctly
        self.show()
        self.pos
        
        self._pos_animation.setStartValue(self.pos() if self.y() > -self.height() else QPoint(target_x, -self.height()))
        self._pos_animation.setEndValue(QPoint(target_x, target_y))
        self._pos_animation.start()

    def slide_out_to_hide(self):
        """Slides the bar up and hides it. Use this instead of destroy if you want to reuse it."""
        self._pos_animation.stop()
        
        self._pos_animation.setStartValue(self.pos())
        self._pos_animation.setEndValue(QPoint(self.x(), -self.height()))
        
        # Connect to hide() instead of deleteLater()
        try:
            self._pos_animation.finished.disconnect() # Clear old connections
        except:
            pass
            
        self._pos_animation.finished.connect(self.deleteLater)
        self._pos_animation.start()

    def update_health_fill(self):        
        self.update()
        # Smooth interpolation for the health bar fill
        if abs(self.percentage - self.current_percentage) < 0.001:
            self.current_percentage = self.percentage

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), int(self.height()/4)
        y_offset = self.height() // 2

        # --- LAYER: Health Bar Background & Fill ---
        if not self.bar_img.isNull():
            sw, sh = self.bar_img.width(), self.bar_img.height()
            cap_w = int(h*0.75)
            src_b = self.original_crop_border
            
            # Background Rect
            bg_rect = QRect(cap_w//2, math.floor(h*0.25//2) + y_offset, int(w - cap_w), h - math.floor(h*0.25))
            painter.fillRect(bg_rect, QColor(63, 62, 72))

            # Foreground Fill Rect
            self.current_percentage += (self.percentage - self.current_percentage) * 0.05
            fill_w = int((w - cap_w) * self.current_percentage)
            fill_rect = QRect(cap_w//2, math.floor(h*0.25//2) + y_offset, fill_w, h - math.floor(h*0.25))
            painter.fillRect(fill_rect, QColor(118, 139, 153))

            # Draw the 3-slice border image
            painter.drawPixmap(QRect(0, y_offset, cap_w, h), self.bar_img, QRect(0, 0, src_b, sh))
            painter.drawPixmap(QRect(cap_w, y_offset, w - 2*cap_w, h), self.bar_img, QRect(src_b, 0, sw - 2*src_b, sh))
            painter.drawPixmap(QRect(w - cap_w, y_offset, cap_w, h), self.bar_img, QRect(sw - src_b, 0, src_b, sh))

        # --- LAYER: Pins/Markers ---
        if not self.marker_img.isNull():
            mw = int(h * 11/22)
            for p in [0.2, 0.4, 0.6, 0.8]:
                m_x = int(p * w) - mw // 2
                painter.drawPixmap(QRect(m_x, y_offset, mw, h), self.marker_img)

        # --- LAYER: Boss Icon ---
        if not self.icon_img.isNull():
            iw = int(h*2.5)
            painter.drawPixmap(QRect(w//2 - int(iw*21/32)//2, int(self.height()*0.17), int(iw*21/32), iw), self.icon_img)

        # --- LAYER: Text ---
        boss_name = "DESTROYMAN III"
        painter.setFont(self.custom_font)
        metrics = painter.fontMetrics()
        text_width = metrics.boundingRect(boss_name).width()
        text_x = (w - text_width) // 2
        text_y = y_offset + h + metrics.ascent() + 10 

        path = QPainterPath()
        path.addText(text_x, text_y, self.custom_font, boss_name)
        
        # Text Outline
        pen = QPen(QColor(0, 0, 0), 4)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.strokePath(path, pen)
        # Text Fill
        painter.fillPath(path, QColor(255, 255, 255))

    def change_percentage(self):
        """Randomizes health for demo purposes."""
        self.percentage = random.random()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    screen_w = windll.user32.GetSystemMetrics(0)
    
    health_bar = ScalableHealthBar()
    health_bar.resize(screen_w // 2, 200)
    
    health_bar.slide_in()

    logic_timer = QTimer()
    logic_timer.timeout.connect(health_bar.change_percentage)
    logic_timer.start(1500)

    QTimer.singleShot(2000, health_bar.slide_out_to_hide)
    QTimer.singleShot(4000, health_bar.slide_in)
    QTimer.singleShot(6000, health_bar.slide_out_to_hide)
    

    sys.exit(app.exec_())