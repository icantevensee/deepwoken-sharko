"""
Boss attacks + damage functions.

Every attack that can happen in the bossfight is here as a function. The damage mouse and damage Sharko functions are here too.
"""

import      time
import      math
import      numpy as np
import      random
import      os

import      win32api
import      win32gui

from ctypes                             import windll
from PyQt5.QtGui                        import QPixmap, QPainter
from PyQt5.QtCore                       import QTimer, Qt

from math_utils                         import MathUtils
from windows_interactive.windows_utils  import WindowsUtils

from widgets.sword_window               import SwordWindow


class CombatSystem():

    @staticmethod
    def damage(self, attack_type):
        """- Applies damage or posture changes based on current parry/block state and the given attack type.
           - Plays block/parry/hit sounds and spawns block/parry/blood particles as appropriate.
           - @staticmethod is needed because unlike lua, we don't have . to use self, and : to not to use self, python always passes self as the first argument,
           since this is being called from self.damage andd CombatSystem.damage, we need to make it a static method and pass self explicitly."""
        if not hasattr(self, "particles_manager"):
            return
        current_time = time.time()
        mouse_x, mouse_y = win32api.GetCursorPos()

        posture_amount = self.ATTACK_STATS[attack_type]["posture"]
        damage_amount = self.ATTACK_STATS[attack_type]["damage"]

        if current_time < self.parry_block_active_until or self.f_key_held:
            time_held = current_time - self.parry_press_time if self.f_key_held else 0
            if time_held >= self.PARRY_WINDOW:
                self.last_parry_block_time = current_time
                if hasattr(self, "_apply_posture"):
                    self._apply_posture(posture_amount, damage_amount)
                try:
                    self.audio_manager.play("block", volume=self.sound_volume)
                except Exception as e:
                    print(f"Error playing block sound: {e}")
                if self.particles_manager:
                    self.particles_manager.play_block(mouse_x, mouse_y)
            else:
                self.last_parry_block_time = 0
                if hasattr(self, "_apply_posture"):
                    self._apply_posture(-self.POSTURE_PARRY_COST)
                try:
                    self.audio_manager.play("parry", volume=self.sound_volume)
                except Exception as e:
                    print(f"Error playing parry sound: {e}")
                if self.particles_manager:
                    self.particles_manager.play_parry(mouse_x, mouse_y)

            if self.block_transition_callback:
                try:
                    self.block_transition_callback.deleteLater()
                except (RuntimeError, Exception):
                    pass
                self.block_transition_callback = None
            return

        # Clear outdated flags
        if current_time >= self.parry_block_active_until:
            self.parry_block_active_until = 0
            if self.block_transition_callback:
                try:
                    self.block_transition_callback.deleteLater()
                except (RuntimeError, Exception):
                    pass
                self.block_transition_callback = None

        # Play blood effect and hit sound
        if self.particles_manager:
            self.particles_manager.play_blood(mouse_x, mouse_y)
        self.audio_manager.play("hit", volume=self.sound_volume)

    def damage_sharko(self):
        """Reduces the boss’s health and updates the boss bar. Also plays sharko-blood particles and hit sound when the mouse attack hits Sharko."""
        if not hasattr(self, "particles_manager"):
            return
        self.bar_guis.boss_health -= self.M1_DAMAGE
        self.bar_guis.bb_percentage = self.bar_guis.boss_health / self.MAX_BOSS_HEALTH
        mouse_x, mouse_y = win32api.GetCursorPos()
        self.particles_manager.play_sharko_blood(mouse_x, mouse_y)
        self.audio_manager.play("hit", volume=self.sound_volume)

    def mouse_attack(self, x, y):
        """Checks whether a click is within Destroyman III's hitbox which changes based on the way it's facing and, if so, calls damage_sharko."""
        sprite_x, sprite_y = None, None
        current_x, current_y = self.window.geometry().x(), self.window.geometry().y()
        if self.current_facing == "Left":
            sprite_x, sprite_y = current_x, current_y + 178
        else:
            sprite_x, sprite_y = current_x + 190, current_y + 178
        print(x, y, sprite_x, sprite_y)

        if sprite_x <= x <= sprite_x + self.SPRITE_WIDTH and sprite_y <= y <= sprite_y + self.SPRITE_HEIGHT:
            CombatSystem.damage_sharko(self)

    def jump(self, jump_end, speed, on_complete=None):
        """Executes a full jump animation for Sharko, including bezier trajectory, sprite frame selection based on slope, and hit detection against the mouse."""
        if not self.fight_mode_active:
            return
        if hasattr(self, "temp_combat_timer") and self.temp_combat_timer:
            self.temp_combat_timer.stop()
            self.temp_combat_timer.deleteLater()
            self.temp_combat_timer = None
        self.jump_images = {
            "jump1": QPixmap(os.path.join(self.IMAGES_PATH, "jump1.png")),
            "jump2": QPixmap(os.path.join(self.IMAGES_PATH, "jump2.png")),
            "jump3": QPixmap(os.path.join(self.IMAGES_PATH, "jump3.png")),
            "jump4": QPixmap(os.path.join(self.IMAGES_PATH, "jump4.png"))
        }
        self.alt_jump_images = {
            "jump1": QPixmap(os.path.join(self.IMAGES_PATH, "jump1.png")).transformed(self.horizontal_flip),
            "jump2": QPixmap(os.path.join(self.IMAGES_PATH, "jump2.png")).transformed(self.horizontal_flip),
            "jump3": QPixmap(os.path.join(self.IMAGES_PATH, "jump3.png")).transformed(self.horizontal_flip),
            "jump4": QPixmap(os.path.join(self.IMAGES_PATH, "jump4.png")).transformed(self.horizontal_flip)
        }
        end_x, end_y, start_x, start_y = jump_end[0], jump_end[1], self.window.geometry().x(), self.window.geometry().y()
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = self.WINDOW_SIZE_X // 2
            end_x = end_x - offset

        dist                = math.hypot(end_x - start_x, end_y - start_y)
        screen_height       = windll.user32.GetSystemMetrics(1)
        screen_width        = windll.user32.GetSystemMetrics(0)
        screen_diagonal     = math.hypot(screen_width, screen_height)
        peak_x, peak_y      = (start_x + end_x) / 2, (start_y + end_y) / 2 - screen_height * ((dist / screen_diagonal) * 0.7)
        peak_x = peak_x - 84 if end_x - start_x > 0 else peak_x - 266

        points, Steps, dt = MathUtils.calculate_jump_trajectory(start_x, start_y, peak_x, peak_y, end_x, end_y, speed)

        hit_detected    = False
        current_step    = 2
        last_image = None

        def step_move():
            nonlocal last_image, current_step, hit_detected, offset, cached_images
            current_x = math.floor(points[current_step - 1][0])
            current_y = math.floor(points[current_step - 1][1])
            previous_x = 0
            previous_y = 0
            if current_step > 2:
                previous_x = math.floor(points[current_step - 2][0])
                previous_y = math.floor(points[current_step - 2][1])
            slope = 0
            if (current_y - previous_y) != 0 and (current_x - previous_x) != 0:
                slope = (current_y - previous_y) / math.fabs(current_x - previous_x) * -1
            if np.sign(peak_x - start_x) != np.sign(end_x - peak_x):
                if current_x - previous_x - 2 > 0:
                    cached_images = self.alt_jump_images
                    offset = self.WINDOW_SIZE_X // 2
                elif current_x - previous_x + 2 < 0:
                    cached_images = self.jump_images
                    offset = 0

            new_image = None
            if slope > 0.5:
                new_image = cached_images["jump1"]
            elif slope < -4:
                new_image = cached_images["jump4"]
            elif slope < -0.5:
                new_image = cached_images["jump3"]
            else:
                new_image = cached_images["jump2"]

            if new_image != last_image:
                self.label.setPixmap(new_image)
                last_image = new_image

            self.window.move(current_x + offset, current_y)

            if not hit_detected:
                mouse_x, mouse_y = win32api.GetCursorPos()
                sprite_x = current_x + offset
                sprite_y = current_y
                if cached_images == self.alt_jump_images:
                    sprite_x += 0
                    sprite_y += 178
                else:
                    sprite_x += 190
                    sprite_y += 178

                if sprite_x <= mouse_x <= sprite_x + self.SPRITE_WIDTH and sprite_y <= mouse_y <= sprite_y + self.SPRITE_HEIGHT:
                    hit_detected = True
                    CombatSystem.damage(self, "jump")

            current_step += 1
            if current_step < Steps:
                QTimer.singleShot(int(dt * 1000), step_move)
            else:
                self.window.move(int(end_x + offset), int(end_y))
                self.jump_images.clear()
                self.alt_jump_images.clear()
                del self.jump_images
                del self.alt_jump_images
                self.current_facing = "Right" if offset == 0 else "Left"
                if on_complete:
                    on_complete()
        step_move()

    def jump_and_hit(self, jump_peak, shortcut, speed, on_complete=None):
        """Jump animation but coordinated with a desktop shortcut. jumps with the peak of curve at an icon's position and asks icon manager to launch it."""
        self.jump_images = {
            "jump1": QPixmap(os.path.join(self.IMAGES_PATH, "jump1.png")),
            "jump2": QPixmap(os.path.join(self.IMAGES_PATH, "jump2.png")),
            "jump3": QPixmap(os.path.join(self.IMAGES_PATH, "jump3.png")),
            "jump4": QPixmap(os.path.join(self.IMAGES_PATH, "jump4.png"))
        }
        self.alt_jump_images = {
            "jump1": QPixmap(os.path.join(self.IMAGES_PATH, "jump1.png")).transformed(self.horizontal_flip),
            "jump2": QPixmap(os.path.join(self.IMAGES_PATH, "jump2.png")).transformed(self.horizontal_flip),
            "jump3": QPixmap(os.path.join(self.IMAGES_PATH, "jump3.png")).transformed(self.horizontal_flip),
            "jump4": QPixmap(os.path.join(self.IMAGES_PATH, "jump4.png")).transformed(self.horizontal_flip)
        }
        peak_x, peak_y, start_x, start_y = jump_peak[0], jump_peak[1] - 210, self.window.geometry().x(), self.window.geometry().y()
        folder_view, hwnd_lv = WindowsUtils.get_desktop_interfaces(
            self.CLSID_ShellWindows,
            self.IID_IFolderView,
            self.SWC_DESKTOP,
            self.SWFO_NEEDDISPATCH
        )
        item_name = WindowsUtils.get_item_text(hwnd_lv, shortcut)
        screen_height = windll.user32.GetSystemMetrics(1)
        screen_width = windll.user32.GetSystemMetrics(0)
        work_area_height = WindowsUtils.get_work_area_height()
        thickness_vertical = screen_height - work_area_height
        taskbar_thickness = max(0, thickness_vertical)

        end_x, end_y = WindowsUtils.clamp(peak_x + (peak_x - start_x) / 2 + np.sign(peak_x - start_x) * 210, 0, screen_width - self.WINDOW_SIZE_X), self.screen_y - self.WINDOW_SIZE_Y - taskbar_thickness
        peak_x = peak_x - 84 if end_x - start_x > 0 else peak_x - 266

        points, Steps, dt = MathUtils.calculate_jump_trajectory(start_x, start_y, peak_x, peak_y, end_x, end_y, speed)

        original_count = win32gui.SendMessage(hwnd_lv, self.LVM_GETITEMCOUNT, 0, 0)

        hit_db          = False
        hit_detected    = False
        current_step    = 2
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = self.WINDOW_SIZE_X // 2

        item = folder_view.Item(shortcut)
        start_pos = folder_view.GetItemPosition(item)
        pos = win32api.MAKELONG(int(start_pos[0]), int(start_pos[1]))

        last_image = None

        def step_move():
            nonlocal last_image, current_step, hit_db, hit_detected, shortcut, original_count, item_name, offset, cached_images
            current_x = math.floor(points[current_step - 1][0])
            current_y = math.floor(points[current_step - 1][1])
            previous_x = 0
            previous_y = 0
            if current_step > 2:
                previous_x = math.floor(points[current_step - 2][0])
                previous_y = math.floor(points[current_step - 2][1])
            slope = 0
            if (current_y - previous_y) != 0 and (current_x - previous_x) != 0:
                slope = (current_y - previous_y) / math.fabs(current_x - previous_x) * -1
            if np.sign(peak_x - start_x) != np.sign(end_x - peak_x):
                if current_x - previous_x - 2 > 0:
                    cached_images = self.alt_jump_images
                    offset = self.WINDOW_SIZE_X // 2
                elif current_x - previous_x + 2 < 0:
                    cached_images = self.jump_images
                    offset = 0

            new_image = None
            if slope > 0.5:
                new_image = cached_images["jump1"]
            elif slope < -4:
                new_image = cached_images["jump4"]
            elif slope < -0.5:
                new_image = cached_images["jump3"]
            else:
                new_image = cached_images["jump2"]

            if new_image != last_image:
                self.label.setPixmap(new_image)
                last_image = new_image

            self.window.move(current_x + offset, current_y)

            if not hit_detected:
                mouse_x, mouse_y = win32api.GetCursorPos()
                sprite_x = current_x + offset
                sprite_y = current_y

                if cached_images == self.alt_jump_images:
                    sprite_x += 0
                    sprite_y += 178
                else:
                    sprite_x += 190
                    sprite_y += 178

                if sprite_x <= mouse_x <= sprite_x + self.SPRITE_WIDTH and sprite_y <= mouse_y <= sprite_y + self.SPRITE_HEIGHT:
                    hit_detected = True
                    CombatSystem.damage(self, "jump")

            if not hit_db:
                current_count = win32gui.SendMessage(hwnd_lv, self.LVM_GETITEMCOUNT, 0, 0)
                if not WindowsUtils.icon_exists(hwnd_lv, shortcut) or current_count != original_count:
                    original_count = current_count
                    shortcut = WindowsUtils.get_actual_index(hwnd_lv, item_name)
                    print(f"Shortcut was probably deleted and recreated, updating index to {shortcut}", item_name)
                    if shortcut == -1:
                        shortcut = WindowsUtils.create_shortcut(hwnd_lv)
                        item_name = WindowsUtils.get_item_text(hwnd_lv, shortcut)

                win32gui.SendMessage(hwnd_lv, self.LVM_SETITEMPOSITION, shortcut, pos)

            if current_step >= Steps / 2 and not hit_db:
                mouse = win32api.GetCursorPos()
                hit_db = True
                self.throw_shortcut(shortcut, mouse, speed, item_name)

            current_step += 1
            if current_step < Steps:
                QTimer.singleShot(int(dt * 1000), step_move)
            else:
                if hasattr(self, "screen_shaker") and self.screen_shaker:
                    self.screen_shaker.shake(duration_ms=2500, intensity=35)
                self.window.move(int(end_x + offset), int(end_y))
                self.jump_images.clear()
                self.alt_jump_images.clear()
                del self.jump_images
                del self.alt_jump_images
                self.current_facing = "Right" if offset == 0 else "Left"
                if on_complete:
                    on_complete()
        step_move()

    def lazer(self, on_complete=None):
        """Qpainter based rendering lazer attack:
           - Pivots the head of a sprite to always face mouse, also moving body if head range of movement is exceeded.
           - Creates and positions a lazer beam object via vfx manager.
           - Does damage to the player."""
        self._lazer_body = QPixmap(os.path.join(self.IMAGES_PATH, "Pivot_Body.png"))
        self._lazer_face = QPixmap(os.path.join(self.IMAGES_PATH, "Pivot_Face.png"))
        self._lazer_corals = QPixmap(os.path.join(self.IMAGES_PATH, "Pivot_Corals.png"))

        self._lazer_start_time = time.time()
        body_width = self._lazer_body.width()
        body_height = self._lazer_body.height()

        self._lazer_center_x = body_width / 2
        self._lazer_center_y = body_height / 2

        offset_x, offset_y = 0, 0
        current_geom = self.window.geometry()
        current_x, current_y = current_geom.x(), current_geom.y()

        if self.current_facing == "Right":
            offset_x = self.WINDOW_SIZE_X - body_width
            offset_y = self.WINDOW_SIZE_Y - body_height
        else:
            offset_y = self.WINDOW_SIZE_Y - body_height

        self.window.move(current_x + offset_x, current_y + offset_y)

        # Cache coordinates to prevent win32 polling lag
        self._cached_win_x = current_x + offset_x
        self._cached_win_y = current_y + offset_y

        self._lazer_frame1db = False
        self._lazer_lastangle = 0
        self._lazer_damagetimer = 0
        self._lazer_dir = "Right"
        self._lazer_duration = self.audio_manager.get_sound_length("dread_breath")
        self._lazer_on_complete = on_complete
        self._lazer_offset_x = offset_x
        self._lazer_offset_y = offset_y

        def update_lazer():
            elapsed = (time.time() - self._lazer_start_time) * 1000
            if elapsed < self._lazer_duration:
                mouse_x, mouse_y = win32api.GetCursorPos()
                screen_center_x = self._cached_win_x + self._lazer_center_x
                screen_center_y = self._cached_win_y + self._lazer_center_y

                self._lazer_dir = "Right" if mouse_x < screen_center_x else "Left"

                rel_x = mouse_x - screen_center_x
                rel_y = mouse_y - screen_center_y

                dirconst = -1 if self._lazer_dir == "Right" else 1
                angle_rad = math.atan2(rel_y, dirconst * rel_x)
                angle_deg = dirconst * math.degrees(angle_rad)

                norm_angle = ((angle_deg + 180) % 360 - 180) * dirconst
                if elapsed < self.LAZER_WINDUP:
                    norm_angle = self._lazer_lastangle + 0.2 * (norm_angle - self._lazer_lastangle)
                    self._lazer_lastangle = norm_angle

                face_angle = max(min(norm_angle, 16), -60)
                overflow_angle = (face_angle - norm_angle) * dirconst

                rad_val = math.radians(norm_angle * dirconst)
                local_offset_x = 80 * dirconst
                local_offset_y = 15

                rotated_offset_x = local_offset_x * math.cos(rad_val) - local_offset_y * math.sin(rad_val)
                rotated_offset_y = local_offset_x * math.sin(rad_val) + local_offset_y * math.cos(rad_val)

                pivot_x = screen_center_x + rotated_offset_x
                pivot_y = screen_center_y + rotated_offset_y
                angle = math.degrees(math.atan2(mouse_y - pivot_y, mouse_x - pivot_x))

                if not self._lazer_frame1db:
                    self.particles_manager.play_star_pop(pivot_x, pivot_y, count=1)
                    self.particles_manager.play_ardour(pivot_x, pivot_y)
                    self.audio_manager.play("dread_breath", volume=self.sound_volume)
                    self._lazer_frame1db = True

                if elapsed > self.LAZER_WINDUP:
                    self.particles_manager.set_laser("Sharko_Lazer", pivot_x, pivot_y, angle, offset=0)
                    self._lazer_damagetimer += 1
                    if self._lazer_damagetimer >= 3:
                        CombatSystem.damage(self, "single_lazer_hit")
                        self._lazer_damagetimer = 0

                canvas = QPixmap(self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
                canvas.fill(Qt.transparent)

                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)

                flip = self._lazer_dir == "Left"

                if overflow_angle != 0.0:
                    painter.translate(self._lazer_center_x, self._lazer_center_y)
                    painter.rotate(-overflow_angle)
                    painter.translate(-self._lazer_center_x, -self._lazer_center_y)

                painter.save()
                if flip:
                    painter.translate(self._lazer_body.width(), 0)
                    painter.scale(-1, 1)
                painter.drawPixmap(0, 0, self._lazer_body)
                painter.restore()

                painter.save()
                if flip:
                    painter.translate(self._lazer_center_x, self._lazer_center_y)
                    painter.scale(-1, 1)
                    painter.rotate(-face_angle)
                    painter.translate(-self._lazer_center_x, -self._lazer_center_y)
                else:
                    painter.translate(self._lazer_center_x, self._lazer_center_y)
                    painter.rotate(-face_angle)
                    painter.translate(-self._lazer_center_x, -self._lazer_center_y)

                painter.drawPixmap(0, 0, self._lazer_face)
                painter.restore()

                painter.save()
                if flip:
                    painter.translate(self._lazer_corals.width(), 0)
                    painter.scale(-1, 1)
                painter.drawPixmap(0, 0, self._lazer_corals)
                painter.restore()
                painter.end()

                self.label.setPixmap(canvas)
            else:
                cleanup_lazer()

        def cleanup_lazer():
            if hasattr(self, "temp_combat_timer") and self.temp_combat_timer:
                self.temp_combat_timer.stop()
                self.temp_combat_timer.deleteLater()
                self.temp_combat_timer = None

            self.particles_manager.remove_laser("Sharko_Lazer")

            l_r_offset = 0
            if self.current_facing != self._lazer_dir:
                l_r_offset = self.WINDOW_SIZE_X // 2 if self.current_facing == "Right" else -self.WINDOW_SIZE_X // 2

            self.current_facing = self._lazer_dir
            geom = self.window.geometry()
            target_x = geom.x() - self._lazer_offset_x + l_r_offset
            target_y = geom.y() - self._lazer_offset_y

            hwnd = int(self.window.winId())
            windll.user32.SetWindowPos(hwnd, 0, target_x, target_y, 0, 0, 0x0008 | 0x0004 | 0x0001)

            if hasattr(self, "label") and self.label:
                self.label.clear()

            from PyQt5.QtCore import QCoreApplication
            self.window.repaint()
            QCoreApplication.processEvents()

            del self._lazer_body
            del self._lazer_face
            del self._lazer_corals

            if self._lazer_on_complete: 
                self._lazer_on_complete()

        self.temp_combat_timer = QTimer()
        self.temp_combat_timer.timeout.connect(update_lazer)
        self.temp_combat_timer.start(30)

    def area_belly_flop(self, warning_time, num_subdivisions, num_subdivisions_to_attack, work_area_height, on_complete=None):
        """Performs a multi-stage attack using lambdas and callbacks:
           - Jump out, display warning stripes via the multi warning overlay.
           - Spawn falling-sharko particles over lethal subdivisions.
           - Jump back."""
        original_x = self.window.geometry().x()
        jump_end = -400 if original_x < self.screen_x // 2 else self.screen_x + 400
        groups = []
        subdivision_x_length = int(self.screen_x / num_subdivisions)

        def create_warnings(on_complete=None):
            nonlocal groups
            if not self.fight_mode_active:
                return
            subdivision_pool = list(range(1, num_subdivisions + 1))
            lethal_subdivisions = random.sample(subdivision_pool, num_subdivisions_to_attack)

            lethal_subdivisions.sort()    
            if lethal_subdivisions:
                current_group = [lethal_subdivisions[0]]
                for sub in lethal_subdivisions[1:]:
                    if sub == current_group[-1] + 1:
                        current_group.append(sub)
                    else:
                        groups.append(current_group)
                        current_group = [sub]
                groups.append(current_group)

            for i, group in enumerate(groups):
                start_subdivision = group[0]
                group_count = len(group)
                merged_width = group_count * subdivision_x_length
                calculated_x = (start_subdivision - 1) * subdivision_x_length

                is_last = (i == len(groups) - 1)
                callback_to_pass = on_complete if is_last else None
                self.warning_manager.trigger_warning(merged_width, self.screen_y, warning_time, calculated_x, 0, on_complete=callback_to_pass)

        def create_attack(on_complete):
            if not self.fight_mode_active:
                return
            for group in groups:
                start_subdivision = group[0]
                group_count = len(group)
                merged_width = group_count * subdivision_x_length
                calculated_x = (start_subdivision - 1) * subdivision_x_length
                scale = merged_width / self.FALLING_SHARKO_SIZE_X
                vel = self.screen_y / 23

                self.particles_manager.play_falling_sharko(calculated_x + merged_width // 2, -0.5 * self.FALLING_SHARKO_SIZE_Y * scale, scale, vel, self.FALLING_SHARKO_SIZE_X, self.FALLING_SHARKO_SIZE_Y)
            self.temp_combat_timer = QTimer()
            self.temp_combat_timer.setSingleShot(True)
            self.temp_combat_timer.timeout.connect(on_complete)
            self.temp_combat_timer.start(int((16 ** 2) * 1.5))

        CombatSystem.jump(
            self,
            [jump_end, work_area_height - 343],
            0.4,
            on_complete=lambda: create_warnings(
                on_complete=lambda: create_attack(
                    on_complete=lambda: CombatSystem.jump(
                        self,
                        [original_x, work_area_height - 343],
                        0.4,
                        on_complete=on_complete
                    )
                )
            )
        )

    def toast_attack(self, on_complete=None):
        """Triggers a toast-based attack with toast manager."""
        self.toast_manager.trigger_toast_async(random.choice(self.TOAST_TEXT["titles"]), random.choice(self.TOAST_TEXT["descriptions"]))
        if on_complete:
            self._single_shot(2000, on_complete)

    def roar_attack(self, on_complete=None):
        """Plays a roaring animation with screenshake."""
        self._roar1_frame = QPixmap(os.path.join(self.IMAGES_PATH, "roar1.png")) if self.current_facing  == "Right" else QPixmap(os.path.join(self.IMAGES_PATH, "roar1.png")).transformed(self.horizontal_flip)
        self._roar2_frame = QPixmap(os.path.join(self.IMAGES_PATH, "roar2.png")) if self.current_facing  == "Right" else QPixmap(os.path.join(self.IMAGES_PATH, "roar2.png")).transformed(self.horizontal_flip)
        self._roar3_frame = QPixmap(os.path.join(self.IMAGES_PATH, "roar3.png")) if self.current_facing  == "Right" else QPixmap(os.path.join(self.IMAGES_PATH, "roar3.png")).transformed(self.horizontal_flip)
        self._roar4_frame = QPixmap(os.path.join(self.IMAGES_PATH, "roar4.png")) if self.current_facing  == "Right" else QPixmap(os.path.join(self.IMAGES_PATH, "roar4.png")).transformed(self.horizontal_flip)

        roar_duration = self.audio_manager.get_sound_length("long_roar")
        total_frames = roar_duration // (self.ANIMATION_DELAY // 2) + 4
        mouth_offset_x = self.ROAR_MOUTH_OFFSET_X_RIGHT if self.current_facing  == "Right" else self.WINDOW_SIZE_X - self.ROAR_MOUTH_OFFSET_X_RIGHT
        current_frame = 0
        roar_points = [math.floor(total_frames * 0.2), math.floor(total_frames * 0.4), math.floor(total_frames * 0.6), math.floor(total_frames * 0.8)]

        def update_roar():
            nonlocal current_frame
            current_frame += 1

            if current_frame in [1, total_frames - 1]:
                self.label.setPixmap(self._roar1_frame)
            elif current_frame in [2, total_frames - 2]:
                self.label.setPixmap(self._roar2_frame)

                if current_frame == total_frames - 2:
                    if hasattr(self, "temp_combat_timer") and self.temp_combat_timer:
                        self.temp_combat_timer.stop()
                        self.temp_combat_timer.deleteLater()
                        self.temp_combat_timer = None

                    del self._roar1_frame
                    del self._roar2_frame
                    del self._roar3_frame
                    del self._roar4_frame

                    if on_complete:
                        self._single_shot(self.ANIMATION_DELAY // 2, on_complete)
                else:
                    self.audio_manager.play("long_roar", volume=self.sound_volume)
                    self.particles_manager.play_ardour(self.window.geometry().x() + mouth_offset_x, self.window.geometry().y() + self.ROAR_MOUTH_OFFSET_Y)
                    self.screen_shaker.shake(duration_ms=roar_duration + self.ANIMATION_DELAY, intensity=50, sustained=True)
            elif current_frame % 2 == 0:
                self.label.setPixmap(self._roar3_frame)
            else:
                self.label.setPixmap(self._roar4_frame)

            if current_frame - 2 in roar_points:
                self.particles_manager.play_ardour(self.window.geometry().x() + mouth_offset_x, self.window.geometry().y() + self.ROAR_MOUTH_OFFSET_Y)

        self.temp_combat_timer = QTimer()
        self.temp_combat_timer.timeout.connect(update_roar)
        self.temp_combat_timer.start(self.ANIMATION_DELAY // 2)

    def summon_sword(self):
        """Creates a sword window if not already present."""
        if hasattr(self, "sword_window") and self.sword_window:
            return
        self.sword_window = SwordWindow(lambda: self.current_facing, damage_callback=lambda attack_type: CombatSystem.damage(self, attack_type))
        self.sword_window.initialize(self.window)

    def sword_combo(self, num_attacks):
        """Creates a sword combo sequence by scheduling sword attacks at one second intervals and then returning the sword to following the Sharko window."""
        if not hasattr(self, "sword_window") or not self.sword_window:
            return

        self.sword_window.set_follow_mode("mouse")

        for attack in range(num_attacks):
            self.math.single_shot(attack * 1000 + 500, self.sword_window.attack)
        self.math.single_shot(num_attacks * 1000 + 500, lambda: self.sword_window.set_follow_mode("window", self.window))
