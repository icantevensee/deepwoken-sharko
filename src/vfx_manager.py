"""
Visual Effects Manager Module

Manages particle systems and visual effects including:
- Laser effects with fade animations
- Particle types (sparkles, rings, blood, etc.)
- Visual effect rendering and updates
- Warning overlays for combat events
"""

import math
import os
import random
import time
import sys
from ctypes import c_bool, c_uint32, c_void_p, windll

import win32api
from PyQt5.QtCore import (
    QEasingCurve,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from constants import SharkoConstants

class Laser:
    """Laser beam visual effect with fade in/out animation."""

    def __init__(self, x, y, angle, color=QColor(0, 120, 255), start_offset=50):
        """Initialize a laser effect.
        """
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

    def __init__(self, x, y, p_type, pixmap=None):
        """Initialize a particle with type-specific properties and physics.
        """
        self.pos = QPointF(float(x), float(y))
        self.pixmap = pixmap
        self.p_type = p_type
        self.alpha = 1.0
        self.elapsed = 0.0

        if p_type == "sparkle":
            self.scale      = 0.0
            self.vel        = QPointF(0, 0)
            self.friction   = 1.0
            self.rotation   = random.uniform(0, 360)
        elif p_type == "ring":
            self.scale      = random.uniform(0.12, 0.18)
            self.rot_speed  = random.uniform(8, 15) * random.choice([-1, 1])
            self.vel        = QPointF(0, 0)
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
            self.vel        = QPointF(0, 0)
            self.friction   = 0.96
        elif p_type in ("unparryable_glyph", "unblockable_glyph"):
            self.scale      = 0.0
            self.rotation   = 0
            self.rot_speed  = 0.0
            self.vel        = QPointF(0, 0)
            self.friction   = 0.96
        elif p_type in ("unparryable_outline", "unblockable_outline"):
            self.scale      = 0.0
            self.rotation   = random.uniform(0, 360)
            self.rot_speed  = 5
            self.vel        = QPointF(0, 0)
            self.friction   = 0.96
        elif p_type == "falling_sharko":
            self.db         = False
            self.rotation   = 0
            self.rot_speed  = 0
            self.friction   = 1
            self.hitbox_width = 0
            self.hitbox_height = 0

    def update(self, dt):
        """Update particle physics, position, and animation properties.
        """
        self.elapsed += dt
        if hasattr(self, "gravity"):
            self.vel += self.gravity
        self.pos += self.vel
        self.vel *= self.friction if hasattr(self, "friction") else 1.0

        if self.p_type == "sparkle":
            if self.elapsed < 0.06:
                self.scale  += 0.15
            else:
                self.scale  -= 0.03
            self.alpha = max(0, min(1.0, self.scale * 6.0))
        elif self.p_type == "ring":
            self.rotation += self.rot_speed
            self.scale      += 0.005
            self.alpha      -= 0.08
        elif self.p_type in ("blood", "blood_sharko"):
            self.rotation += self.rot_speed
            self.alpha      -= 0.03
        elif self.p_type == "laser_square":
            self.rotation   += self.rot_speed
            self.alpha      -= 0.04
        elif self.p_type == "star":
            self.rotation += self.rot_speed
            if self.elapsed < 0.12:
                self.scale  += 0.08
            else:
                self.alpha  -= 0.03
                self.scale  -= 0.002
        elif self.p_type in ("unparryable_glyph", "unblockable_glyph"):
            self.rotation += self.rot_speed
            if self.elapsed < 0.07:
                self.scale  += 0.075
            else:
                self.alpha  -= 0.04
                self.scale  += 0.002
        elif self.p_type in ("unparryable_outline", "unblockable_outline"):
            self.rotation += self.rot_speed
            if self.elapsed < 0.07:
                self.scale  += 0.075
            elif self.elapsed > 0.4:
                self.scale  -= 0.025
            if self.scale <= 0:
                self.alpha  = 0
        elif self.p_type == "falling_sharko":
            if self.elapsed >= 2:
                self.alpha  = 0
        else:
            self.alpha      -= 0.05

        return self.alpha > 0


class VFXManager(QWidget):
    # Cache QColor objects to avoid creating them every frame
    _COLOR_BLOOD = QColor(150, 0, 0)
    _COLOR_BLOOD_SHARKO = QColor(18, 117, 64)
    _COLOR_BLOCK = QColor(255, 255, 0)
    _COLOR_LASER = QColor(0, 180, 255)

    def __init__(self, damage_callback=None, screen_shaker=None):
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
            self.script_dir = os.path.join(os.path.dirname(sys.executable), 'src')
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self._load_assets()
        self.setGeometry(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)-1)
        self.show()
        self.raise_()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_vfx)
        self.timer.start(16)

    def _load_assets(self):
        asset_map = {
            "sparkle1": "../assets/particles/sparkle1.png",
            "sparkle2": "../assets/particles/sparkle2.png",
            "sparkle3": "../assets/particles/sparkle3.png",
            "spark": "../assets/particles/spark.png",
            "ring": "../assets/particles/ring.png",
            "ringportion": "../assets/particles/ringportion.png",
            "star1": "../assets/particles/star1.png",
            "unparryable_glyph": "../assets/particles/unparryable_glyph.png",
            "unparryable_outline": "../assets/particles/unparryable_outline.png",
            "unblockable_glyph": "../assets/particles/unblockable_glyph.png",
            "unblockable_outline": "../assets/particles/unblockable_outline.png",
            "falling_sharko": "../assets/sharko/falling.png",
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
                p.end()
                self.textures[key] = tinted

    def set_laser(self, laser_id, x, y, angle, color=QColor(0, 150, 255), offset=0):
        if laser_id not in self.lasers:
            self.lasers[laser_id] = Laser(x, y, angle, color, start_offset=offset)
        else:
            l = self.lasers[laser_id]
            l.origin, l.angle, l.color, l.start_offset = (QPointF(float(x), float(y)), angle, color, offset)
            if l.state == "fading_out":
                l.state = "fading_in"

    def remove_laser(self, laser_id):
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

    def play_blood(self, x, y):
        for _ in range(7):
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

    def update_vfx(self):
        # Get mouse position for collision detection
        mouse_x, mouse_y = win32api.GetCursorPos()

        # In-place particle filtering to avoid list recreation
        write_idx = 0
        for i, p in enumerate(self.particles):
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
        self.update()

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

            if p.p_type in ("blood", "blood_sharko"):
                color = self._COLOR_BLOOD if p.p_type == "blood" else self._COLOR_BLOOD_SHARKO
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                s = p.size
                half_s = s / 2
                painter.drawRect(QRectF(-half_s, -half_s, s, s))
            elif p.p_type in ("block", "laser_square"):
                color = self._COLOR_LASER if p.p_type == "laser_square" else self._COLOR_BLOCK
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                s = p.size
                half_s = s / 2
                painter.drawRect(QRectF(-half_s, -half_s, s, s))
            else:
                w, h = p.pixmap.width() * p.scale, p.pixmap.height() * p.scale
                half_w, half_h = w / 2, h / 2
                painter.drawPixmap(QRectF(-half_w, -half_h, w, h), p.pixmap, QRectF(p.pixmap.rect()))
            painter.restore()


class WarningInstance:
    """Helper class to track individual warning states."""

    def __init__(self, rect, duration_ms, parent_update_func, on_complete=None):
        self.rect = rect
        self.opacity = 0
        self.is_fading_out = False
        self.exit_timer = None  # Store timer reference for cleanup
        self.on_complete = on_complete  # Callback when warning expires
        self.deleted = False

        self.anim = QVariantAnimation()
        self.anim.setDuration(300)
        self.anim.setStartValue(0)
        self.anim.setEndValue(180)
        self.anim.setEasingCurve(QEasingCurve.InOutSine)

        self.anim.valueChanged.connect(self.update_val)
        self.update_callback = parent_update_func

        self.anim.finished.connect(self.loop_logic)
        self.anim.start()

        self.exit_timer = QTimer()
        self.exit_timer.setSingleShot(True)
        self.exit_timer.timeout.connect(self.start_exit)
        self.exit_timer.start(duration_ms)

    def update_val(self, val):
        self.opacity = val
        self.update_callback()

    def loop_logic(self):
        if self.is_fading_out and self.anim.direction() == QVariantAnimation.Backward:
            self.opacity = -1
            if self.on_complete:
                self.on_complete()
            return

        new_dir = QVariantAnimation.Backward if self.anim.direction() == QVariantAnimation.Forward else QVariantAnimation.Forward
        self.anim.setDirection(new_dir)
        self.anim.start()

    def start_exit(self):
        self.exit_timer.deleteLater()
        self.is_fading_out = True

    def cleanup(self):
        """Clean up timers and animations."""
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
                self.anim.valueChanged.disconnect(self.update_val)
            except (RuntimeError, TypeError):
                pass
            try:
                self.anim.finished.disconnect(self.loop_logic)
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
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)-1)
        self.show()

        self.active_warnings = []

    def trigger_warning(self, width, height, duration_ms, x, y, on_complete=None):
        rect = QRect(x, y, width, height)

        new_warning = WarningInstance(rect, duration_ms, self.update, on_complete)
        self.active_warnings.append(new_warning)

    def paintEvent(self, event):
        # Maintain z-order on top of Sharko window
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Source)

        for i in range(len(self.active_warnings) - 1, -1, -1):
            w_inst = self.active_warnings[i]

            if w_inst.opacity == -1:
                self.active_warnings.pop(i)
                continue

            color = QColor(255, 0, 0, w_inst.opacity)
            rect = w_inst.rect
            x, y, w, h = rect.getRect()

            # Draw Stripes
            painter.save()
            painter.setClipRect(rect)
            painter.setPen(QPen(color, 5, Qt.SolidLine, Qt.FlatCap))
            for j in range(-h, w + h, 25):
                painter.drawLine(x + j, y, x + j + h, y + h)
            painter.restore()

            # Draw Border
            painter.setPen(QPen(color, 4, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
            painter.drawRect(rect)

    def deinitialize(self):
        """Properly clean up all warning animations before deletion."""
        for w in self.active_warnings:
            w.cleanup()
        self.active_warnings.clear()
        self.deleteLater()


class ScreenShaker(QWidget):
    def __init__(self):
        super().__init__()
        import dxcam #uses a LOT of memory, so only import if it's actually ever used. Large ~25 mb decrease in ram if not imported.
    
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
        self.setGeometry(0, 0, self.width, self.height-1)
        user32.SetWindowDisplayAffinity(int(self.winId()), SharkoConstants.WDA_EXCLUDEFROMCAPTURE)
        self.captured_pixmap = None
        self.intensity = 0
        self.start_time = 0
        self.duration = 0

        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.process_shake_step)

        self.offset_x = 0
        self.offset_y = 0

    def shake(self, duration_ms=450, intensity=30):

        self.intensity = intensity
        self.duration = duration_ms / 1000.0

        self.start_time = time.time()
        self.show()

        self.loop_timer.start(30)

    def process_shake_step(self):
        elapsed = time.time() - self.start_time

        if elapsed >= self.duration:
            self.stop_and_reset()
            return

        frame = self.camera.grab_view()
        if frame is not None:
            height, width, channels = frame.shape
            bytes_per_line = channels * width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_ARGB32_Premultiplied)
            self.captured_pixmap = QPixmap.fromImage(q_img)

        progress = elapsed / self.duration

        decay = math.exp(-4.5 * progress)
        current_intensity = self.intensity * decay
        t_ms = elapsed * 1000.0
        frequency_multiplier = 1.0 + (progress * 1.5)

        speed_x = 0.01 * frequency_multiplier
        speed_y = 0.02 * frequency_multiplier
        randomness = 0.35

        sin_wave = math.sin(t_ms * speed_x) * current_intensity
        cos_wave = math.cos(t_ms * speed_y) * current_intensity
        rand_noise_x = random.uniform(-current_intensity, current_intensity) * randomness
        rand_noise_y =  random.uniform(-current_intensity, current_intensity) * randomness

        self.offset_x = int(sin_wave + rand_noise_x)
        self.offset_y = int(cos_wave + rand_noise_y)
        self.raise_()
        self.particles_manager.raise_()
        self.update()

    def stop_and_reset(self):
        self.loop_timer.stop()
        self.captured_pixmap = None
        self.offset_x = 0
        self.offset_y = 0
        self.hide()
    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.captured_pixmap:
            painter.fillRect(0, 0, self.width, self.height, Qt.transparent)
            return
        painter.fillRect(0, 0, self.width, self.height, Qt.black)
        painter.drawPixmap(self.offset_x, self.offset_y, self.captured_pixmap)
        painter.end()

    def deinitialize(self):
        if hasattr(self, "loop_timer") and self.loop_timer:
            self.loop_timer.stop()
            self.loop_timer.deleteLater()
            self.loop_timer = None
        if hasattr(self, "camera") and self.camera:
            self.camera.release()
            self.camera = None
        self.captured_pixmap = None
        if hasattr(self, "particles_manager"):
            self.particles_manager = None
        self.hide()
        self.deleteLater()
