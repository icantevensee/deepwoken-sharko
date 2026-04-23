import sys
import os
import random
import math
from PyQt5.QtWidgets import QApplication,QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QColor, QPen

class Laser:
    def __init__(self, x, y, angle, color=QColor(0, 120, 255), start_offset=50):
        self.origin = QPointF(float(x), float(y))
        self.angle = angle
        self.color = color
        self.thickness = 30
        self.flicker = 0.0
        self.start_offset = start_offset
        self.alpha = 0.0  
        self.state = "fading_in" 
        self.fade_speed = 0.1    

    def update_fade(self):
        if self.state == "fading_in":
            self.alpha += self.fade_speed
            if self.alpha >= 1.0:
                self.alpha = 1.0
                self.state = "active"
        elif self.state == "fading_out":
            self.alpha -= self.fade_speed
            return self.alpha > 0
        return True

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
            angle = random.uniform(0, 2 * math.pi) 
            speed = random.uniform(4, 12)
            self.vel = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.gravity = QPointF(0, 0.2) 
            self.friction = 0.94 
            self.size = random.uniform(4, 10)
            self.rotation = random.uniform(0, 360)
            self.rot_speed = random.uniform(-15, 15)
        elif p_type == 'laser_square':
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 8)
            self.vel = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.friction = 0.92
            self.size = random.uniform(10, 20)
            self.rotation = random.uniform(0, 360)
            self.rot_speed = random.uniform(-10, 10)
        elif p_type == 'star':
            self.scale = 0.0  # Start invisible for the "pop"
            self.rotation = random.uniform(0, random.uniform(0, 360))
            self.rot_speed = random.uniform(-15, 15)
            # Give it a tiny bit of drift
            self.vel = QPointF(0,0)
            self.friction = 0.96

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
            self.alpha -= 0.03 
        elif self.p_type == 'laser_square':
            self.rotation += self.rot_speed
            self.alpha -= 0.04
        elif self.p_type == 'star':
            self.rotation += self.rot_speed
            if self.elapsed < 0.12:
                self.scale += 0.08
            else:
                self.alpha -= 0.03
                self.scale -= 0.002
        else: # spark/block
            self.alpha -= 0.05
            
        return self.alpha > 0

class VFXManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.particles = []
        self.lasers = {} 
        self.textures = {}
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self._load_assets()
        self.showFullScreen()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_vfx)
        self.timer.start(16)

    def _load_assets(self):
        asset_map = {
            "sparkle1": "assets/particles/sparkle1.png", 
            "sparkle2": "assets/particles/sparkle2.png",
            "sparkle3": "assets/particles/sparkle3.png", 
            "spark": "assets/particles/spark.png",
            "ring": "assets/particles/ring.png", 
            "ringportion": "assets/particles/ringportion.png",
            "star1": "assets/particles/star1.png"
        }
        for key, rel_path in asset_map.items():
            full_path = os.path.join(self.script_dir, rel_path)
            if os.path.exists(full_path):
                img = QPixmap(full_path)
                tinted = QPixmap(img.size())
                tinted.fill(Qt.transparent)
                p = QPainter(tinted)
                p.drawPixmap(0, 0, img)
                p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
                if not key.startswith("star1"):
                    p.fillRect(tinted.rect(), QColor(255, 220, 0)) 
                p.end()
                self.textures[key] = tinted

    def set_laser(self, laser_id, x, y, angle, color=QColor(0, 150, 255), offset=0):
        if laser_id not in self.lasers:
            self.lasers[laser_id] = Laser(x, y, angle, color, start_offset=offset)
        else:
            l = self.lasers[laser_id]
            l.origin, l.angle, l.color, l.start_offset = QPointF(float(x), float(y)), angle, color, offset
            if l.state == "fading_out": l.state = "fading_in"

    def remove_laser(self, laser_id):
        if laser_id in self.lasers: self.lasers[laser_id].state = "fading_out"

    def play_star_pop(self, x, y, count=1):
        if "star1" in self.textures:
            for _ in range(count):
                self.particles.append(Particle(x, y, 'star', self.textures["star1"]))

    def play_parry(self, x, y):
        available_sparkles = [k for k in ["sparkle1", "sparkle2", "sparkle3"] if k in self.textures]
        if len(available_sparkles) >= 2:
            for s_key in random.sample(available_sparkles, 2):
                self.particles.append(Particle(x, y, 'sparkle', self.textures[s_key]))
        if "ring" in self.textures:
            self.particles.append(Particle(x, y, 'ring', self.textures[random.choice(["ring", "ringportion"])]))

    def play_block(self, x, y):
        for _ in range(7): self.particles.append(Particle(x, y, 'block'))

    def play_blood(self, x, y):
        for _ in range(7): self.particles.append(Particle(x, y, 'blood'))

    def update_vfx(self):
        self.particles = [p for p in self.particles if p.update(0.016)]
        to_remove = []
        for lid, l in self.lasers.items():
            if not l.update_fade(): 
                to_remove.append(lid)
                continue
            l.flicker = random.uniform(-2.5, 2.5)
            # Only spawn trailing squares if laser is visible enough
            if l.alpha > 0.4 and random.random() > 0.15:
                rad = math.radians(l.angle)
                dist = random.uniform(l.start_offset, 2000)
                px, py = l.origin.x() + math.cos(rad) * dist, l.origin.y() + math.sin(rad) * dist
                self.particles.append(Particle(px, py, 'laser_square'))
        for lid in to_remove: del self.lasers[lid]
        self.update()

    def deinitialize(self):
        self.timer.stop(); self.hide(); self.particles.clear(); self.lasers.clear(); self.deleteLater()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Plus)

        # 1. DRAW LASERS
        for laser in self.lasers.values():
            painter.save()
            painter.setOpacity(laser.alpha)
            rad = math.radians(laser.angle)
            start_p = QPointF(laser.origin.x() + math.cos(rad) * laser.start_offset, 
                             laser.origin.y() + math.sin(rad) * laser.start_offset)
            end_p = QPointF(laser.origin.x() + math.cos(rad) * 4000, 
                           laser.origin.y() + math.sin(rad) * 4000)
            
            glow_c = QColor(laser.color); glow_c.setAlpha(110)
            painter.setPen(QPen(glow_c, laser.thickness + 15 + laser.flicker, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start_p, end_p)
            painter.setPen(QPen(QColor(0, 210, 255), laser.thickness + laser.flicker, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start_p, end_p)
            painter.setPen(QPen(QColor(240, 250, 255), laser.thickness * 0.3, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start_p, end_p)
            painter.restore()

        # 2. DRAW ALL PARTICLES
        for p in self.particles:
            painter.setOpacity(p.alpha)
            painter.save()
            painter.translate(p.pos.x(), p.pos.y())
            painter.rotate(p.rotation)

            if p.p_type == 'blood':
                painter.setBrush(QColor(150, 0, 0)); painter.setPen(Qt.NoPen)
                s = p.size; painter.drawRect(QRectF(-s/2, -s/2, s, s))
            elif p.p_type == 'block' or p.p_type == 'laser_square':
                color = QColor(0, 180, 255) if p.p_type == 'laser_square' else QColor(255, 255, 0)
                painter.setBrush(color); painter.setPen(Qt.NoPen)
                s = p.size; painter.drawRect(QRectF(-s/2, -s/2, s, s))
            else:
                w, h = p.pixmap.width() * p.scale, p.pixmap.height() * p.scale
                painter.drawPixmap(QRectF(-w/2, -h/2, w, h), p.pixmap, QRectF(p.pixmap.rect()))
            painter.restore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    vfx_manager = VFXManager()
    
    pivot_x, pivot_y = 600, 400
    is_on = True
    def toggle_laser():
        global is_on
        if is_on:
            vfx_manager.remove_laser("test_beam")
            print("Turning off...")
        else:
            print("Turning on...")
        is_on = not is_on
    from PyQt5.QtGui import QCursor
    mouse = QCursor.pos()
    vfx_manager.play_star_pop(mouse.x(), mouse.y(), count=1)
    # Timer to move the laser
    test_timer = QTimer()
    def update_test():
        if is_on:

            dx, dy = mouse.x() - pivot_x, mouse.y() - pivot_y
            angle = math.degrees(math.atan2(dy, dx))
            vfx_manager.set_laser("test_beam", pivot_x, pivot_y, angle, offset=0)
        
    test_timer.timeout.connect(update_test)
    test_timer.start(16)

    # Timer to toggle on/off every 3 seconds to test fades
    toggle_timer = QTimer()
    toggle_timer.timeout.connect(toggle_laser)
    toggle_timer.start(3000)

    sys.exit(app.exec_())