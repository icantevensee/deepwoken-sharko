"""Visual Effects Manager Module

Overlay and engine for rendering combat related vfx:
- Maintains a live list of Particle objects and Laser beams.
- updates their physics and lifetimes on a fixed timer, and draws them using additive blending, offset by a ScreenShaker for camera shake effects.
- helper methods for spawning effect types while ensuring that timers and resources are properly cleaned up when deinitialized."""

import math
import os
import random
import sys
from ctypes import c_bool, c_uint32, c_void_p, windll

import win32api
from PyQt5.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
)
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from constants import SharkoConstants


class Laser:
    """Laser beam visual effect with fade in/out animation."""

    def __init__(self, x, y, angle, color=QColor(0, 120, 255), start_offset=50):
        """Initialize a laser effect."""
        self.origin         = QPointF(float(x), float(y))
        self.angle          = angle
        self.color          = color
        self.thickness      = 30
        self.flicker        = 0.0
        self.start_offset   = start_offset
        self.alpha          = 0.0
        self.fade_speed     = 0.1
        self.state          = "fading_in"

    def update_fade(self):
        """Update laser fade animation and return if still visible."""
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
    """Particle sprite with various types and physics simulation."""

    __slots__ = [
        "pos",
        "pixmap",
        "p_type",
        "alpha",
        "elapsed",
        "vel",
        "friction",
        "rotation",
        "rot_speed",
        "scale",
        "size",
        "gravity",
        "hitbox_width",
        "hitbox_height",
        "db",
    ]

    PARTICLE_UPDATE_MAP = {
        "sparkle": lambda self, dt: Particle.update_sparkle(self, dt),
        "ring": lambda self, dt: Particle.update_ring(self, dt),
        "blood": lambda self, dt: Particle.update_blood(self, dt),
        "blood_sharko": lambda self, dt: Particle.update_blood(self, dt),
        "laser_square": lambda self, dt: Particle.update_laser(self, dt),
        "star": lambda self, dt: Particle.update_star(self, dt),
        "unparryable_glyph": lambda self, dt: Particle.update_glyph(self, dt),
        "unblockable_glyph": lambda self, dt: Particle.update_glyph(self, dt),
        "unparryable_outline": lambda self, dt: Particle.update_outline(self, dt),
        "unblockable_outline": lambda self, dt: Particle.update_outline(self, dt),
        "falling_sharko": lambda self, dt: Particle.update_falling_sharko(self, dt),
        "ardour": lambda self, dt: Particle.update_ardour(self, dt),
    }

    def __init__(self, x, y, p_type, pixmap=None):
        """Initialize a particle with type-specific properties and physics."""
        self.pos = QPointF(float(x), float(y))
        self.pixmap = pixmap
        self.p_type = p_type
        self.alpha = 1.0
        self.elapsed = 0.0

        #  Baseline init
        self.vel = QPointF(0.0, 0.0)
        self.gravity = QPointF(0.0, 0.0)
        self.friction = 1.0
        self.rotation = 0.0
        self.rot_speed = 0.0
        self.scale = 1.0
        self.size = 0.0
        self.hitbox_width = 0.0
        self.hitbox_height = 0.0
        self.db = False

        if p_type == "sparkle":
            self.scale      = 0.0
            self.friction   = 1.0
            self.rotation   = random.uniform(0, 360)
        elif p_type == "ring":
            self.alpha = 1.25
            self.scale      = random.uniform(0.12, 0.18)
            self.rot_speed  = random.uniform(8, 15) * random.choice([-1, 1])
            self.friction   = 1.0
            self.rotation   = random.uniform(0, 360)
        elif p_type == "spark":
            angle           = random.uniform(0, 2 * math.pi)
            speed           = random.uniform(4, 10)
            self.vel        = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.scale      = random.uniform(0.015, 0.04)
            self.friction   = 0.82
            self.rotation   = math.degrees(angle) + 90
        elif p_type == "block":
            angle           = random.uniform(0, 2 * math.pi)
            speed           = random.uniform(5, 12)
            self.vel        = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.friction   = 0.84
            self.size       = random.uniform(6, 12)
            self.rotation   = random.uniform(0, 360)
            self.rot_speed  = random.uniform(-15, 15)
        elif p_type in ("blood", "blood_sharko"):
            angle           = random.uniform(0, 2 * math.pi)
            speed           = random.uniform(4, 12)
            self.vel        = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.gravity    = QPointF(0, 0.2)
            self.friction   = 0.94
            self.size       = random.uniform(8, 14)
            self.rotation   = random.uniform(0, 360)
            self.rot_speed  = random.uniform(-15, 15)
        elif p_type == "laser_square":
            angle           = random.uniform(0, 2 * math.pi)
            speed           = random.uniform(2, 8)
            self.vel        = QPointF(math.cos(angle) * speed, math.sin(angle) * speed)
            self.friction   = 0.92
            self.size       = random.uniform(10, 20)
            self.rotation   = random.uniform(0, 360)
            self.rot_speed  = random.uniform(-10, 10)
        elif p_type == "star":
            self.scale      = 0.0
            self.rotation   = random.uniform(0, random.uniform(0, 360))
            self.rot_speed  = random.uniform(-15, 15)
            self.friction   = 0.96
        elif p_type in ("unparryable_glyph", "unblockable_glyph"):
            self.friction   = 0.96
        elif p_type in ("unparryable_outline", "unblockable_outline"):
            self.rotation   = random.uniform(0, 360)
            self.rot_speed  = 5
            self.friction   = 0.96
        elif p_type == "falling_sharko":
            self.db         = False
            self.friction   = 1
        elif p_type == "ardour":
            self.scale      = 0.0
            self.friction   = 1.0

    def update_sparkle(self, dt):
        if self.elapsed < 0.06:
            self.scale += 0.15
        else:
            self.scale -= 0.03
        self.alpha = max(0.0, min(1.0, self.scale * 6.0))

    def update_ring(self, dt):
        self.rotation += self.rot_speed
        self.scale += 0.005
        self.alpha -= 0.08

    def update_ardour(self, dt):
        self.scale += 0.05
        self.alpha -= 0.008

    def update_blood(self, dt):
        self.rotation += self.rot_speed
        self.alpha -= 0.03

    def update_laser(self, dt):
        self.rotation += self.rot_speed
        self.alpha -= 0.04

    def update_star(self, dt):
        self.rotation += self.rot_speed
        if self.elapsed < 0.12:
            self.scale += 0.08
        else:
            self.alpha -= 0.03
            self.scale -= 0.002

    def update_glyph(self, dt):
        self.rotation += self.rot_speed
        if self.elapsed < 0.07:
            self.scale += 0.075
        else:
            self.alpha -= 0.04
            self.scale += 0.002

    def update_outline(self, dt):
        self.rotation += self.rot_speed
        if self.elapsed < 0.07:
            self.scale += 0.075
        elif self.elapsed > 0.4:
            self.scale -= 0.025
        if self.scale <= 0:
            self.alpha = 0.0

    def update_falling_sharko(self, dt):
        if self.elapsed >= 2:
            self.alpha = 0.0

    def update_default(self, dt):
        self.alpha -= 0.05

    def update(self, dt):
        self.elapsed += dt

        self.vel += self.gravity
        self.pos += self.vel
        self.vel *= self.friction

        self.PARTICLE_UPDATE_MAP.get(self.p_type, Particle.update_default)(self, dt)
        return self.alpha > 0


class VFXManager(QWidget):
    PARTICLE_COLOR_MAP = {
        "blood": QColor(150, 0, 0),
        "blood_sharko": QColor(18, 117, 64),
        "laser_square": QColor(0, 180, 255),
        "block": QColor(255, 255, 0)
    }
    RECT_PARTICLE_DRAW_MAP = {
        "blood": lambda self, p, painter: VFXManager.draw_primitive_rect(self, p, painter),
        "blood_sharko": lambda self, p, painter: VFXManager.draw_primitive_rect(self, p, painter),
        "laser_square": lambda self, p, painter: VFXManager.draw_primitive_rect(self, p, painter),
        "block": lambda self, p, painter: VFXManager.draw_primitive_rect(self, p, painter),
    }

    def __init__(self, damage_callback=None, screen_shaker=None):
        """Initialize the vfx manager widget:
        - Window flags.
        - Load assets.
        - Setup periodic update timer."""
        super().__init__()

        self.screen_shaker = screen_shaker

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.particles = []
        self.lasers = {}
        self.textures = {}
        self.damage_callback = damage_callback
        user32 = windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [c_void_p, c_uint32]
        user32.SetWindowDisplayAffinity.restype = c_bool
        user32.SetWindowDisplayAffinity(int(self.winId()), SharkoConstants.WDA_EXCLUDEFROMCAPTURE)
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.join(os.path.dirname(sys.executable), 'src/vfx')
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self._load_assets()
        self.setGeometry(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1) - 1)
        self.show()
        self.raise_()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_vfx)
        self.timer.start(16)

    def _load_assets(self):
        """Load particle texture pixmaps from disk and apply a tint for ring and spark assets."""
        asset_map = {
            "sparkle1": "../../assets/particles/sparkle1.png",
            "sparkle2": "../../assets/particles/sparkle2.png",
            "sparkle3": "../../assets/particles/sparkle3.png",
            "spark": "../../assets/particles/spark.png",
            "ring": "../../assets/particles/ring.png",
            "ringportion": "../../assets/particles/ringportion.png",
            "star1": "../../assets/particles/star1.png",
            "unparryable_glyph": "../../assets/particles/unparryable_glyph.png",
            "unparryable_outline": "../../assets/particles/unparryable_outline.png",
            "unblockable_glyph": "../../assets/particles/unblockable_glyph.png",
            "unblockable_outline": "../../assets/particles/unblockable_outline.png",
            "falling_sharko": "../../assets/sharko/falling.png",
            "ardour": "../../assets/particles/ardour.png"
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
                if key.startswith("ring") or key.startswith("spark"):
                    p.fillRect(tinted.rect(), QColor(255, 220, 0))
                if key.startswith("ardour"):
                    p.fillRect(tinted.rect(), QColor(218, 74, 222))
                p.end()
                self.textures[key] = tinted

    def set_laser(self, laser_id, x, y, angle, color=QColor(0, 150, 255), offset=0):
        """Create or update a laser instance with given origin, angle, color, and offset."""
        if laser_id not in self.lasers:
            self.lasers[laser_id] = Laser(x, y, angle, color, start_offset=offset)
        else:
            lazer = self.lasers[laser_id]
            lazer.origin, lazer.angle, lazer.color, lazer.start_offset = (QPointF(float(x), float(y)), angle, color, offset)
            if lazer.state == "fading_out":
                lazer.state = "fading_in"

    def remove_laser(self, laser_id):
        """Mark a laser to begin fading out instead of being active."""
        if laser_id in self.lasers:
            self.lasers[laser_id].state = "fading_out"

    def play_star_pop(self, x, y, count=1):
        if "star1" in self.textures:
            for _ in range(count):
                self.particles.append(Particle(x, y, "star", self.textures["star1"]))

    def play_unparryable_indicator(self, x, y):
        if "unparryable_outline" in self.textures and "unparryable_glyph" in self.textures:
            self.particles.append(Particle(x, y, "unparryable_outline", self.textures["unparryable_outline"]))
            self.particles.append(Particle(x, y, "unparryable_glyph", self.textures["unparryable_glyph"]))

    def play_unblockable_indicator(self, x, y):
        if "unblockable_outline" in self.textures and "unblockable_glyph" in self.textures:
            self.particles.append(
                Particle(x, y, "unblockable_outline", self.textures["unblockable_outline"]))
            self.particles.append(Particle(x, y, "unblockable_glyph", self.textures["unblockable_glyph"]))

    def play_parry(self, x, y):
        available_sparkles = [k for k in ["sparkle1", "sparkle2", "sparkle3"] if k in self.textures]
        if len(available_sparkles) >= 2:
            for s_key in random.sample(available_sparkles, 2):
                self.particles.append(Particle(x, y, "sparkle", self.textures[s_key]))
        if "ring" in self.textures:
            self.particles.append(Particle(x, y, "ring", self.textures[random.choice(["ring", "ringportion"])]))

    def play_block(self, x, y):
        for _ in range(7):
            self.particles.append(Particle(x, y, "block"))

    def play_blood(self, x, y, amount=7):
        for _ in range(amount):
            self.particles.append(Particle(x, y, "blood"))

    def play_sharko_blood(self, x, y):
        for _ in range(7):
            self.particles.append(Particle(x, y, "blood_sharko"))

    def play_falling_sharko(self, x, y, scale, vel, sharko_width=696, sharko_height=772):
        particle = Particle(x, y, "falling_sharko", self.textures["falling_sharko"])
        particle.scale = scale
        particle.vel = QPointF(0, vel)
        # Store the actual width/height for collision detection
        particle.hitbox_width = sharko_width * scale
        particle.hitbox_height = sharko_height * scale
        self.particles.append(particle)

    def play_ardour(self, x, y):
        self.particles.append(Particle(x, y, "ardour", self.textures["ardour"]))

    def update_vfx(self):
        """One tick for all particles and lasers, perform collision detection for falling Sharko, then call repaint."""
        # Get mouse position for collision detection
        mouse_x, mouse_y = win32api.GetCursorPos()

        # In-place particle filtering to avoid list recreation
        write_idx = 0
        for p in self.particles:
            if p.update(0.016):
                # Check collision for falling_sharko particles
                if p.p_type == "falling_sharko" and not p.db and self.damage_callback:
                    # Get particle bounds (centered at pos)
                    half_width = p.hitbox_width / 2
                    half_height = p.hitbox_height / 2
                    left = p.pos.x() - half_width
                    right = p.pos.x() + half_width
                    top = p.pos.y() - half_height
                    bottom = p.pos.y() + half_height

                    # Check if mouse is within particle bounds
                    if left <= mouse_x <= right and top <= mouse_y <= bottom:
                        p.db = True  # Mark as hit to avoid multiple damage calls
                        self.damage_callback("falling_sharko")

                self.particles[write_idx] = p
                write_idx += 1
        del self.particles[write_idx:]

        to_remove = []
        for lid, l in self.lasers.items():
            if not l.update_fade():
                to_remove.append(lid)
                continue
            l.flicker = random.uniform(-2.5, 2.5)
            if l.alpha > 0.4 and random.random() > 0.5:
                rad = math.radians(l.angle)
                dist = random.uniform(l.start_offset, 2000)
                px, py = l.origin.x() + math.cos(rad) * dist, l.origin.y() + math.sin(rad) * dist
                self.particles.append(Particle(px, py, "laser_square"))
        for lid in to_remove:
            del self.lasers[lid]
        # Maintain z-order on top of Sharko window
        self.raise_()
        self.update()  # call paint event

    def deinitialize(self):
        """Properly clean up all resources before deletion."""
        try:
            self.timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.timer.stop()
        self.timer.deleteLater()
        self.timer = None
        self.hide()
        self.particles.clear()
        self.lasers.clear()
        self.textures.clear()
        self.damage_callback = None
        self.screen_shaker = None
        self.deleteLater()

    def paintEvent(self, event):
        """Render all lasers and particles onto the vfx overlay using additive blending."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Plus)

        for laser in self.lasers.values():
            painter.save()
            painter.setOpacity(laser.alpha)
            rad = math.radians(laser.angle)
            start_p = QPointF(laser.origin.x() + math.cos(rad) * laser.start_offset, laser.origin.y() + math.sin(rad) * laser.start_offset)
            end_p = QPointF(laser.origin.x() + math.cos(rad) * 4000, laser.origin.y() + math.sin(rad) * 4000)

            glow_c = QColor(laser.color)
            glow_c.setAlpha(110)
            painter.setPen(QPen(glow_c, laser.thickness + 15 + laser.flicker, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start_p, end_p)
            painter.setPen(QPen(QColor(0, 210, 255), laser.thickness + laser.flicker, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start_p, end_p)
            painter.setPen(QPen(QColor(240, 250, 255), laser.thickness * 0.3, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start_p, end_p)
            painter.restore()
        offset_x, offset_y = self.screen_shaker.offset_x, self.screen_shaker.offset_y
        for p in self.particles:
            painter.setOpacity(p.alpha)
            painter.save()
            painter.translate(p.pos.x() + offset_x, p.pos.y() + offset_y)
            painter.rotate(p.rotation)

            self.RECT_PARTICLE_DRAW_MAP.get(p.p_type, VFXManager.draw_textured_pixmap)(self, p, painter)
            painter.restore()

    def draw_primitive_rect(self, p, painter):
        color = self.PARTICLE_COLOR_MAP[p.p_type]
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        s = p.size
        half_s = s / 2
        painter.drawRect(QRectF(-half_s, -half_s, s, s))

    def draw_textured_pixmap(self, p, painter):
        w, h = p.pixmap.width() * p.scale, p.pixmap.height() * p.scale
        painter.drawPixmap(QRectF(-w / 2, -h / 2, w, h), p.pixmap, QRectF(p.pixmap.rect()))
