"""
Code for all the attacks sharko can do + damage functions & mouse attack function
"""

import      time
import      math
import      numpy as np
import      random
import      os

import                     win32api
import                     win32gui

from ctypes         import windll, wintypes, byref
from PIL            import Image
from PyQt5.QtGui    import QPixmap, QImage, QCursor
from PyQt5.QtCore   import Qt, QTimer, QPoint

from math_utils     import MathUtils
from img_utils      import ImgUtils
from windows_utils  import WindowsUtils

from widgets        import SwordWindow



class CombatSystem():
    
    @staticmethod
    def damage(self): #@staticmethod is needed because unlike lua, we don't have . to use self, and : to not to use self, python always passes self as the first argument
        if not hasattr(self, "particles_manager"):
            return
        current_time = time.time()
        mouse_x, mouse_y = win32api.GetCursorPos()
        
        # Check if in parry/block window (parry window OR key is still held)
        if current_time < self.parry_active_until or self.f_key_held:
            # Check cooldown
            # Calculate how long the key has been held
            time_held = current_time - self.parry_press_time if self.f_key_held else 0
            # Block if held >= 0.3s, otherwise parry
            if time_held >= self.PARRY_WINDOW:
                self.last_parry_block_time = 0
                try:
                    self.sounds(self.sounds_group["block"])
                except Exception as e:
                    print(f"Error playing block sound: {e}")
                if self.particles_manager:
                    self.particles_manager.play_block(mouse_x, mouse_y)
            else:
                self.last_parry_block_time = 0
                try:
                    self.sounds(self.sounds_group["parry"])
                except Exception as e:
                    print(f"Error playing parry sound: {e}")
                if self.particles_manager:
                    self.particles_manager.play_parry(mouse_x, mouse_y)
            
            # Clear flags after successful block/parry
            self.blocking = False
            self.block_active_until = 0
            if self.block_transition_callback:
                try:
                    self.block_transition_callback.deleteLater()
                except (RuntimeError, Exception):
                    pass
                self.block_transition_callback = None
            return
        
        # Clear outdated flags
        if current_time >= self.parry_active_until:
            self.blocking = False
            self.parry_active_until = 0
            self.block_active_until = 0
            self.f_key_held = False
            if self.block_transition_callback:
                try:
                    self.block_transition_callback.deleteLater()
                except (RuntimeError, Exception):
                    pass
                self.block_transition_callback = None
        
        # Play blood effect and hit sound
        if self.particles_manager:
            self.particles_manager.play_blood(mouse_x, mouse_y)
        try:
            # Try to play a hit/damage sound if it exists
            self.sounds(self.sounds_group["hit"])
        except Exception as e:
            pass

    def damage_sharko(self):
        if not hasattr(self,"particles_manager"):
            return
        self.bar_guis.health -= self.M1_DAMAGE
        self.bar_guis.percentage = self.bar_guis.health/self.MAX_HEALTH
        mouse_x, mouse_y = win32api.GetCursorPos()
        self.particles_manager.play_sharko_blood(mouse_x, mouse_y)
        try:
            # Try to play a hit/damage sound if it exists
            self.sounds(self.sounds_group["hit"])
        except Exception as e:
            pass
            

    def mouse_attack(self,x,y):
        sprite_x, sprite_y = None,None
        current_x, current_y = self.window.geometry().x(), self.window.geometry().y()
        if self.current_facing == "Left":
            sprite_x, sprite_y = current_x , current_y+178
        else:
            sprite_x, sprite_y = current_x + 190, current_y+178
        print(x,y,sprite_x,sprite_y)

        if sprite_x <= x <= sprite_x + self.SPRITE_WIDTH and sprite_y <= y <= sprite_y + self.SPRITE_HEIGHT:
            CombatSystem.damage_sharko(self)


            

    def jump(self,jump_end,speed,on_complete=None):
        if self.fight_mode_active == False:
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
            "jump1": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump1.png"))]][0])),
            "jump2": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump2.png"))]][0])),
            "jump3": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump3.png"))]][0])),
            "jump4": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump4.png"))]][0]))
        }
        end_x, end_y, start_x, start_y = jump_end[0], jump_end[1], self.window.geometry().x(), self.window.geometry().y()
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = self.WINDOW_SIZE_X//2
            end_x = end_x - offset
        
        dist                = math.sqrt((end_x-start_x)**2+(end_y-start_y)**2)
        screen_height       = windll.user32.GetSystemMetrics(1)
        screen_width        = windll.user32.GetSystemMetrics(0)
        screen_diagonal     = math.sqrt(screen_height**2+screen_width**2)
        peak_x, peak_y      = (start_x+end_x)/2, (start_y+end_y)/2-screen_height*((dist/screen_diagonal)*0.7)
        peak_x = peak_x-84 if end_x - start_x > 0 else peak_x-266

        points, Steps, dt = MathUtils.calculate_jump_trajectory(start_x, start_y, peak_x, peak_y, end_x, end_y, speed)

        hit_detected    = False
        current_step    = 2
        last_image = None
        def step_move():
            nonlocal last_image,current_step, hit_detected, offset, cached_images
            current_x = math.floor(points[current_step-1][0])
            current_y = math.floor(points[current_step-1][1])
            previous_x = 0
            previous_y = 0
            if current_step > 2:
                previous_x = math.floor(points[current_step-2][0])
                previous_y = math.floor(points[current_step-2][1])
            slope = 0
            if (current_y-previous_y) != 0 and (current_x-previous_x) != 0:
                slope = (current_y-previous_y)/math.fabs(current_x-previous_x)*-1
            if np.sign(peak_x - start_x) != np.sign(end_x - peak_x):
                if current_x-previous_x-2 > 0:
                    cached_images = self.alt_jump_images
                    offset = self.WINDOW_SIZE_X//2
                elif current_x-previous_x+2 < 0:
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
            
            self.window.move(current_x+offset, current_y)
            
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
                    CombatSystem.damage(self)
            
            current_step += 1
            if current_step < Steps:
                QTimer.singleShot(int(dt*1000),step_move)
            else:
                self.window.move(int(end_x+offset), int(end_y))
                self.jump_images.clear()
                self.alt_jump_images.clear()
                del self.jump_images
                del self.alt_jump_images
                self.current_facing = "Right" if offset == 0 else "Left"
                if on_complete:
                    on_complete()
        step_move()

    def jump_and_hit(self,jump_peak,shortcut,speed,on_complete=None):
        self.jump_images = {
            "jump1": QPixmap(os.path.join(self.IMAGES_PATH, "jump1.png")),
            "jump2": QPixmap(os.path.join(self.IMAGES_PATH, "jump2.png")),
            "jump3": QPixmap(os.path.join(self.IMAGES_PATH, "jump3.png")),
            "jump4": QPixmap(os.path.join(self.IMAGES_PATH, "jump4.png"))
        }
        self.alt_jump_images = {
            "jump1": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump1.png"))]][0])),
            "jump2": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump2.png"))]][0])),
            "jump3": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump3.png"))]][0])),
            "jump4": QPixmap.fromImage(ImgUtils._flip_image([(img.convert("RGBA"), img.close())[0] for img in [Image.open(os.path.join(self.IMAGES_PATH, "jump4.png"))]][0]))
        }
        peak_x, peak_y, start_x, start_y = jump_peak[0], jump_peak[1]-210, self.window.geometry().x(), self.window.geometry().y()
        folder_view,hwnd_lv = WindowsUtils.get_desktop_interfaces(
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

        end_x, end_y = WindowsUtils.clamp(peak_x+(peak_x-start_x)/2+np.sign(peak_x-start_x)*210, 0, screen_width - self.WINDOW_SIZE_X), self.screen_y-self.WINDOW_SIZE_Y-taskbar_thickness
        peak_x = peak_x-84 if end_x - start_x > 0 else peak_x-266

        points, Steps, dt = MathUtils.calculate_jump_trajectory(start_x, start_y, peak_x, peak_y, end_x, end_y, speed)

        original_count = win32gui.SendMessage(hwnd_lv, self.LVM_GETITEMCOUNT, 0, 0)

        hit_db          = False
        hit_detected    = False
        current_step    = 2
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = self.WINDOW_SIZE_X//2

        item = folder_view.Item(shortcut)
        start_pos = folder_view.GetItemPosition(item)
        pos = win32api.MAKELONG(int(start_pos[0]), int(start_pos[1]))
        
        last_image = None
        
        def step_move():
            nonlocal last_image,current_step,hit_db,hit_detected,shortcut,original_count,item_name,offset,cached_images
            current_x = math.floor(points[current_step-1][0])
            current_y = math.floor(points[current_step-1][1])
            previous_x = 0
            previous_y = 0
            if current_step > 2:
                previous_x = math.floor(points[current_step-2][0])
                previous_y = math.floor(points[current_step-2][1])
            slope = 0
            if (current_y-previous_y) != 0 and (current_x-previous_x) != 0:
                slope = (current_y-previous_y)/math.fabs(current_x-previous_x)*-1
            if np.sign(peak_x - start_x) != np.sign(end_x - peak_x):
                if current_x-previous_x-2 > 0:
                    cached_images = self.alt_jump_images
                    offset = self.WINDOW_SIZE_X//2
                elif current_x-previous_x+2 < 0:
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
            
            self.window.move(current_x+offset, current_y)
            
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
                    CombatSystem.damage(self)
            
            if not hit_db:
                current_count = win32gui.SendMessage(hwnd_lv, self.LVM_GETITEMCOUNT, 0, 0)
                if not WindowsUtils.icon_exists(hwnd_lv, shortcut) or current_count != original_count:
                    original_count = current_count
                    shortcut = WindowsUtils.get_actual_index(hwnd_lv, item_name)
                    print(f"Shortcut was probably deleted and recreated, updating index to {shortcut}",item_name)
                    if shortcut == -1: 
                        shortcut = WindowsUtils.create_shortcut(hwnd_lv)
                        item_name = WindowsUtils.get_item_text(hwnd_lv, shortcut)

                win32gui.SendMessage(hwnd_lv, self.LVM_SETITEMPOSITION, shortcut, pos)
            

            if current_step >= Steps/2 and not hit_db:
                mouse = win32api.GetCursorPos()
                hit_db = True
                self.throw_shortcut(shortcut, mouse, speed, item_name)

            current_step += 1
            if current_step < Steps:
                QTimer.singleShot(int(dt*1000),step_move)
            else:
                if hasattr(self,"screen_shaker") and self.screen_shaker:
                    self.screen_shaker.shake(duration_ms=2500, intensity=35)
                self.window.move(int(end_x+offset), int(end_y))
                self.jump_images.clear()
                self.alt_jump_images.clear()
                del self.jump_images
                del self.alt_jump_images
                self.current_facing = "Right" if offset == 0 else "Left"
                if on_complete:
                    on_complete()
        step_move()

    def lazer(self, duration_ms, on_complete=None):
        self.pivot_images = {
            "Pivot_Body": Image.open(os.path.join(self.IMAGES_PATH, "Pivot_Body.png")).convert("RGBA"),
            "Pivot_Face": Image.open(os.path.join(self.IMAGES_PATH, "Pivot_Face.png")).convert("RGBA"),
            "Pivot_Corals": Image.open(os.path.join(self.IMAGES_PATH, "Pivot_Corals.png")).convert("RGBA")
        }

        start_time = time.time()
        body_width = self.pivot_images["Pivot_Body"].width
        body_height = self.pivot_images["Pivot_Body"].height
        center_p = (body_width // 2, body_height // 2)
        offset_x, offset_y = 0,0
        if self.current_facing == "Right":
            offset_x = self.WINDOW_SIZE_X-body_width
            offset_y = self.WINDOW_SIZE_Y-body_height
            current_x, current_y = self.window.geometry().x(), self.window.geometry().y()
            self.window.move(current_x + offset_x, current_y + offset_y)
        else:
            offset_y = self.WINDOW_SIZE_Y-body_height
            current_x, current_y = self.window.geometry().x(), self.window.geometry().y()
            self.window.move(current_x + offset_x, current_y + offset_y)
        frame1db = False
        lastangle = 0
        damagetimer = 0
        Indicator_Length = 0.5*1000
        lazer_dir = None
        def update_lazer():
            nonlocal lazer_dir,frame1db, lastangle, damagetimer
            elapsed = (time.time() - start_time) * 1000
            if elapsed < duration_ms:
                window_x, window_y = self.window.geometry().x(), self.window.geometry().y()
                
                screen_center_x = window_x + center_p[0]
                screen_center_y = window_y + center_p[1]
                

                mouse_x, mouse_y = win32api.GetCursorPos()

                lazer_dir = "Right" if mouse_x < screen_center_x else "Left"

                def get_dir_img(name):
                    img = self.pivot_images[name]
                    return  img.transpose(Image.FLIP_LEFT_RIGHT) if lazer_dir == "Left" else img

                body = get_dir_img("Pivot_Body")
                face = get_dir_img("Pivot_Face")
                corals = get_dir_img("Pivot_Corals")

                rel_x = mouse_x - screen_center_x
                rel_y = mouse_y - screen_center_y
                
                dirconst = -1 if lazer_dir == "Right" else 1
                calc_x = dirconst*rel_x
                angle_rad = math.atan2(rel_y, calc_x)
                angle_deg = math.degrees(angle_rad)
                angle_deg = dirconst*angle_deg

                norm_angle = ((angle_deg + 180) % 360 - 180)*dirconst
                if elapsed < Indicator_Length:
                    norm_angle = lastangle + 0.2 * (norm_angle - lastangle)
                    lastangle = norm_angle
                face_angle = max(min(norm_angle, 16), -60)
                overflow_angle = (norm_angle - face_angle)*dirconst
                face_angle = face_angle*dirconst
                rot_dir = -1 

                rad = math.radians(norm_angle*dirconst)
                local_offset_x = 80 * dirconst
                local_offset_y = 15
                rotated_offset_x = local_offset_x * math.cos(rad) - local_offset_y * math.sin(rad)
                rotated_offset_y = local_offset_x * math.sin(rad) + local_offset_y * math.cos(rad)

                pivot_x = screen_center_x + rotated_offset_x
                pivot_y = screen_center_y + rotated_offset_y
                mouse_x, mouse_y = win32api.GetCursorPos()
                dx, dy = mouse_x - pivot_x, mouse_y - pivot_y
                angle = math.degrees(math.atan2(dy, dx))
                if not frame1db:
                    self.particles_manager.play_star_pop(pivot_x, pivot_y, count=1)
                    frame1db = True
                if elapsed > Indicator_Length:
                    self.particles_manager.set_laser("Sharko_Lazer", pivot_x, pivot_y, angle, offset=0)
                    damagetimer = damagetimer+1
                    if damagetimer >= 3:
                        CombatSystem.damage(self)
                        damagetimer = 0

                rotated_face = face.rotate(
                    rot_dir * face_angle, 
                    center=center_p, 
                    resample=Image.BICUBIC, 
                    fillcolor=(0,0,0,0)
                )
                
                f_alpha = rotated_face.split()[3]
                clean_mask = f_alpha.point(lambda p: 255 if p > 245 else 0)
                rotated_face.putalpha(clean_mask)

                combined = Image.new("RGBA", (self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y), (0, 0, 0, 0))
                combined.paste(body, (0, 0), body)
                combined.paste(rotated_face, (0, 0), rotated_face)
                combined.paste(corals, (0, 0), corals)

                if overflow_angle != 0:
                    combined = combined.rotate(
                        rot_dir * overflow_angle, 
                        center=center_p, 
                        resample=Image.BICUBIC, 
                        fillcolor=(0,0,0,0)
                    )
                
                # Convert PIL image to QPixmap
                final_pixmap = ImgUtils._pil_to_qpixmap(combined)
                self.label.setPixmap(final_pixmap)
                
                # Schedule next update
            else:
                if hasattr(self, "temp_combat_timer") and self.temp_combat_timer:
                    self.temp_combat_timer.stop()
                    self.temp_combat_timer.deleteLater()
                    self.temp_combat_timer = None
                self.particles_manager.remove_laser("Sharko_Lazer")
                l_r_offset = 0
                if self.current_facing != lazer_dir:
                    if self.current_facing == "Right":
                        l_r_offset=self.WINDOW_SIZE_X//2
                    else:
                        l_r_offset=-self.WINDOW_SIZE_X//2
                self.current_facing = lazer_dir
                current_x, current_y = self.window.geometry().x(), self.window.geometry().y()
                self.window.move(current_x - offset_x + l_r_offset, current_y - offset_y)
                if hasattr(self, "pivot_images") and self.pivot_images:
                    for img in self.pivot_images.values():
                        img.close() 
                    self.pivot_images.clear()
                    del self.pivot_images
                if on_complete: on_complete()

        self.temp_combat_timer = QTimer()
        self.temp_combat_timer.timeout.connect(update_lazer)
        self.temp_combat_timer.start(30)


    def area_belly_flop(self, warning_time, num_subdivisions, num_subdivisions_to_attack, work_area_height, on_complete=None):
        original_x = self.window.geometry().x()
        jump_end = -400 if original_x < self.screen_x // 2 else self.screen_x + 400
        groups = []
        subdivision_x_length = int(self.screen_x / num_subdivisions)

        def create_warnings(on_complete=None):
            nonlocal groups
            if self.fight_mode_active == False:
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
            if self.fight_mode_active == False:
                return
            for group in groups:
                start_subdivision = group[0]
                group_count = len(group)
                merged_width = group_count * subdivision_x_length
                calculated_x = (start_subdivision - 1) * subdivision_x_length
                scale = merged_width / self.FALLING_SHARKO_SIZE_X
                vel = self.screen_y / 23

                self.particles_manager.play_falling_sharko(calculated_x+merged_width//2, -0.5*self.FALLING_SHARKO_SIZE_Y*scale, scale, vel, self.FALLING_SHARKO_SIZE_X, self.FALLING_SHARKO_SIZE_Y)
            self.temp_combat_timer = QTimer()
            self.temp_combat_timer.setSingleShot(True)
            self.temp_combat_timer.timeout.connect(on_complete)
            self.temp_combat_timer.start(int((16**2)*1.5))

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

    def summon_sword(self):
        if hasattr(self, "sword_window") and self.sword_window:
            return
        self.sword_window = SwordWindow(lambda: self.current_facing,damage_callback=lambda:CombatSystem.damage(self))
        self.sword_window.initialize(self.window)

    def sword_combo(self, num_attacks):
        if not hasattr(self, "sword_window") or not self.sword_window:
            return
        
        self.sword_window.set_follow_mode("mouse")

        for attack in range(num_attacks):
            self._single_shot(attack*1000+500,self.sword_window.attack)
        self._single_shot(num_attacks*1000+500,lambda: self.sword_window.set_follow_mode("window",self.window))


        