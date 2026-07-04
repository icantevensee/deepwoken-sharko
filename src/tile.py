"""
Tile class for visual effects and particles
"""

import random

class Tile:
    """Represents a tile/particle for visual effects"""

    def __init__(self, img, x, y, fade_step=1):
        """
        Initialize a tile sprite.
        """
        self.img       = img
        self.x         = x
        self.y         = y + 600
        self.vx        = random.uniform(-0.2, 0.2)
        self.vy        = random.uniform(-2, -0.4)
        self.alpha     = 255
        self.angle     = 0
        self.angvel    = random.uniform(-8, 8)
        self.fade_step = fade_step

    def update(self):
        """Update tile position and appearance"""
        self.x += self.vx
        self.y += self.vy
        self.angle = (self.angle + self.angvel) % 360
        self.alpha = max(0, int(self.alpha) - self.fade_step)

    def is_alive(self):
        """Check if tile is still visible"""
        return self.alpha > 0
