import sys
import os
import random
import math
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QColor

class Particle:
    def __init__(self, x, y, p_type, pixmap=None):
        self.pos = QPointF(float(x), float(y))
        self.pixmap = pixmap
        self.p_type = p_type 
        self.alpha = 1.0
        self.elapsed = 0.0
        
        if p_type == 'sparkle': 
            self.scale, self.vel, self.friction = 0.0, QPointF(0, 0), 1.0
            self.rotation = random.uniform(0, 360)
        elif p_type == 'ring':
            self.scale = random.uniform(0.12, 0.18) 
            self.rot_speed = random.uniform(8, 15) * random.choice([-1, 1])
            self.vel, self.friction = QPointF(0, 0), 1.0
            self.rotation = random.uniform(0, 360)
        elif p_type == 'spark':
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(4, 10) 
            self.vel = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.scale, self.friction = random.uniform(0.015, 0.04), 0.82 
            self.rotation = math.degrees(angle) + 90
        elif p_type == 'block':
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(5, 12)
            self.vel = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.friction = 0.84
            self.size = random.uniform(6, 12)
            self.rotation = random.uniform(0, 360)
            self.rot_speed = random.uniform(-15, 15)
        elif p_type == 'blood':
            # EVEN SPREAD: Full 360 degrees
            angle = random.uniform(0, 2 * math.pi) 
            speed = random.uniform(4, 12)
            self.vel = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            # LESS FALL: Reduced gravity
            self.gravity = QPointF(0, 0.2) 
            self.friction = 0.94 
            self.size = random.uniform(4, 10)
            self.rotation = random.uniform(0, 360)
            self.rot_speed = random.uniform(-15, 15)

    def update(self, dt):
        self.elapsed += dt
        if hasattr(self, 'gravity'):
            self.vel += self.gravity
        self.pos += self.vel
        self.vel *= (self.friction if hasattr(self, 'friction') else 1.0)
        
        if self.p_type == 'sparkle':
            if self.elapsed < 0.06: self.scale += 0.15
            else: self.scale -= 0.03
            self.alpha = max(0, min(1.0, self.scale * 6.0))
        elif self.p_type == 'ring':
            self.rotation += self.rot_speed
            self.scale += 0.005
            self.alpha -= 0.08
        elif self.p_type == 'blood':
            self.rotation += self.rot_speed
            self.alpha -= 0.03 # Fades slightly faster than before to keep it clean
        else: # spark/block
            self.alpha -= 0.05
            
        return self.alpha > 0

class VFXManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.particles = []
        self.textures = {}
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self._load_assets()
        self.showFullScreen()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_vfx)
        self.timer.start(16)

    def _load_assets(self):
        asset_map = {
            "sparkle1": "assets/particles/sparkle1.png", "sparkle2": "assets/particles/sparkle2.png",
            "sparkle3": "assets/particles/sparkle3.png", "spark": "assets/particles/spark.png",
            "ring": "assets/particles/ring.png", "ringportion": "assets/particles/ringportion.png"
        }
        for key, rel_path in asset_map.items():
            full_path = os.path.join(self.script_dir, rel_path)
            if os.path.exists(full_path):
                img = QPixmap(full_path)
                tinted = QPixmap(img.size()); tinted.fill(Qt.transparent)
                p = QPainter(tinted); p.drawPixmap(0, 0, img)
                p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
                p.fillRect(tinted.rect(), QColor(255, 255, 0)); p.end()
                self.textures[key] = tinted

    def play_parry(self, x, y):
        available_sparkles = [k for k in ["sparkle1", "sparkle2", "sparkle3"] if k in self.textures]
        if len(available_sparkles) >= 2:
            for s_key in random.sample(available_sparkles, 2):
                self.particles.append(Particle(x, y, 'sparkle', self.textures[s_key]))
        if "ring" in self.textures:
            self.particles.append(Particle(x, y, 'ring', self.textures[random.choice(["ring", "ringportion"])]))
        if "spark" in self.textures:
            for _ in range(35): self.particles.append(Particle(x, y, 'spark', self.textures["spark"]))

    def play_block(self, x, y):
        for _ in range(20): self.particles.append(Particle(x, y, 'block'))

    def play_blood(self, x, y):
        for _ in range(40): self.particles.append(Particle(x, y, 'blood'))

    def update_vfx(self):
        self.particles = [p for p in self.particles if p.update(0.016)]
        self.update()

    def deinitialize(self):
        self.timer.stop(); self.hide(); self.particles.clear(); self.deleteLater()

    def paintEvent(self, event):
        if not self.particles: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Plus)

        for p in self.particles:
            painter.setOpacity(p.alpha)
            painter.save()
            painter.translate(p.pos.x(), p.pos.y())
            painter.rotate(p.rotation)

            if p.p_type == 'blood':
                painter.setBrush(QColor(150, 0, 0)); painter.setPen(Qt.NoPen)
                s = p.size
                painter.drawRect(QRectF(-s/2, -s/2, s, s))
            elif p.p_type == 'block':
                painter.setBrush(QColor(255, 255, 0)); painter.setPen(Qt.NoPen)
                s = p.size
                painter.drawRect(QRectF(-s/2, -s/2, s, s))
            else:
                w, h = p.pixmap.width() * p.scale, p.pixmap.height() * p.scale
                painter.drawPixmap(QRectF(-w/2, -h/2, w, h), p.pixmap, QRectF(p.pixmap.rect()))
            painter.restore()