import      time
import      math
import      numpy as np

import      win32api
import      win32gui
from        ctypes import windll, wintypes, byref
from        PIL import Image, ImageTk

from        icons import IconManager
from        math_utils import MathUtils


from        shortcut_utils import DesktopUtils
from        constants import SharkoConstants


class CombatSystem(IconManager):
    
    @staticmethod
    def damage(self): #@staticmethod is needed because unlike lua, we don't have . to use self, and : to not to use self, python always passes self as the first argument
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
                    self.sounds(self.sounds_group['block'])
                except Exception as e:
                    print(f"Error playing block sound: {e}")
                if self.particles_manager:
                    self.particles_manager.play_block(mouse_x, mouse_y)
            else:
                self.last_parry_block_time = 0
                try:
                    self.sounds(self.sounds_group['parry'])
                except Exception as e:
                    print(f"Error playing parry sound: {e}")
                if self.particles_manager:
                    self.particles_manager.play_parry(mouse_x, mouse_y)
            
            # Clear flags after successful block/parry
            self.blocking = False
            self.block_active_until = 0
            if self.block_transition_callback:
                try:
                    self.window.after_cancel(self.block_transition_callback)
                except Exception:
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
                    self.window.after_cancel(self.block_transition_callback)
                except Exception:
                    pass
                self.block_transition_callback = None
        
        # Play blood effect and hit sound
        if self.particles_manager:
            self.particles_manager.play_blood(mouse_x, mouse_y)
        try:
            # Try to play a hit/damage sound if it exists
            self.sounds(self.sounds_group['hit'])
        except Exception as e:
            pass

    def jump(self,jump_end,speed,on_complete=None):
        end_x, end_y, start_x, start_y = jump_end[0], jump_end[1], int(self.window.geometry().split('+')[-2]), int(self.window.geometry().split('+')[-1])
        dist                = math.sqrt((end_x-start_x)**2+(end_y-start_y)**2)
        screen_height       = windll.user32.GetSystemMetrics(1)
        screen_width        = windll.user32.GetSystemMetrics(0)
        screen_diagonal     = math.sqrt(screen_height**2+screen_width**2)
        peak_x, peak_y      = (start_x+end_x)/2, (start_y+end_y)/2-screen_height*((dist/screen_diagonal)*0.7)
        if end_x - start_x > 0:
            peak_x = peak_x-84
        else:
            peak_x = peak_x-266

        P0      = (start_x, start_y)
        Pmid    = (peak_x, peak_y)
        P2      = (end_x, end_y)
        B, P1   = MathUtils.quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5)
        L2      = MathUtils.quadratic_length(P0, P1, P2, n=2000)
        
        T       = 0.75*(L2/(speed*1800))**0.4
        Steps   = math.floor(T*30)
        dt      = T/Steps
        ts = np.linspace(0, 1, Steps)
        points  = B(ts)
        hit_detected    = False
        sprite_width    = 165
        sprite_height   = 165
        current_step    = 2
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = int(359/2)
        
        last_image = None
        
        def step_move(current_step, hit_detected, offset, cached_images):
            nonlocal last_image
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
                    offset = int(359/2)
                elif current_x-previous_x+2 < 0:
                    cached_images = self.jump_images
                    offset = 0

            new_image = None
            if slope > 0.5:
                new_image = cached_images['jump1']
            elif slope < -4:
                new_image = cached_images['jump4']
            elif slope < -0.5:
                new_image = cached_images['jump3']
            else:
                new_image = cached_images['jump2']
            
            if new_image != last_image:
                self.label.image = new_image
                self.label.configure(image=new_image)
                last_image = new_image
            
            self.window.geometry(f'+{current_x+offset}+{current_y}')
            
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
                
                if (sprite_x <= mouse_x <= sprite_x + sprite_width and 
                    sprite_y <= mouse_y <= sprite_y + sprite_height):
                    hit_detected = True
                    CombatSystem.damage(self)
            
            current_step = current_step + 1
            if current_step < Steps:
                self.window.after(math.ceil(dt*1000),step_move,current_step,hit_detected,offset,cached_images)
            else:
                self.window.geometry(f'+{int(end_x+offset)}+{int(end_y)}')
                self.label.image = cached_images['idle1']
                self.label.configure(image=self.label.image)
                if on_complete:
                    on_complete()
        step_move(current_step, hit_detected, offset, cached_images)

    def jump_and_hit(self,jump_peak,shortcut,speed,on_complete=None):
        peak_x, peak_y, start_x, start_y = jump_peak[0], jump_peak[1]-210, int(self.window.geometry().split('+')[-2]), int(self.window.geometry().split('+')[-1])
        folder_view,hwnd_lv = DesktopUtils.get_desktop_interfaces(
            SharkoConstants.CLSID_ShellWindows,
            SharkoConstants.IID_IFolderView,
            SharkoConstants.SWC_DESKTOP,
            SharkoConstants.SWFO_NEEDDISPATCH
        )
        item_name = DesktopUtils.get_item_text(hwnd_lv, shortcut)
        screen_height = windll.user32.GetSystemMetrics(1)
        screen_width = windll.user32.GetSystemMetrics(0)
        desktop_working_area = wintypes.RECT()
        windll.user32.SystemParametersInfoW(SharkoConstants.SPI_GETWORKAREA, 0, byref(desktop_working_area), 0)
        work_area_height = desktop_working_area.bottom - desktop_working_area.top
        thickness_vertical = screen_height - work_area_height    
        if thickness_vertical > 0:
            taskbar_thickness = thickness_vertical
        else:
            taskbar_thickness = 0
        end_x, end_y = DesktopUtils.clamp(peak_x+(peak_x-start_x)/2+np.sign(peak_x-start_x)*210, 0, screen_width - 357), self.screen_y-342-taskbar_thickness
        if end_x - start_x > 0:
            peak_x = peak_x-84
        else:
            peak_x = peak_x-266
        P0      = (start_x, start_y)
        Pmid    = (peak_x, peak_y)
        P2      = (end_x, end_y)
        B, P1   = MathUtils.quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5)
        L2      = MathUtils.quadratic_length(P0, P1, P2, n=2000)
        
        T       = 1*(L2/(speed*1800))**0.4
        Steps   = math.floor(T*60)
        dt      = T/Steps
        original_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
        ts = np.linspace(0, 1, Steps)
        points  = B(ts)
        hit_db          = False
        hit_detected    = False
        sprite_width    = 165
        sprite_height   = 165
        current_step    = 2
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = int(359/2)

        item = folder_view.Item(shortcut)
        start_pos = folder_view.GetItemPosition(item)
        pos = win32api.MAKELONG(int(start_pos[0]), int(start_pos[1]))
        
        last_image = None
        
        def step_move(current_step,hit_db,hit_detected,shortcut,original_count,item_name,offset,cached_images):
            nonlocal last_image
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
                    offset = int(359/2)
                elif current_x-previous_x+2 < 0:
                    cached_images = self.jump_images
                    offset = 0

            new_image = None
            if slope > 0.5:
                new_image = cached_images['jump1']
            elif slope < -4:
                new_image = cached_images['jump4']
            elif slope < -0.5:
                new_image = cached_images['jump3']
            else:
                new_image = cached_images['jump2']
            
            if new_image != last_image:
                self.label.image = new_image
                self.label.configure(image=new_image)
                last_image = new_image
            
            self.window.geometry(f'+{current_x+offset}+{current_y}')
            
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
                
                if (sprite_x <= mouse_x <= sprite_x + sprite_width and 
                    sprite_y <= mouse_y <= sprite_y + sprite_height):
                    hit_detected = True
                    CombatSystem.damage(self)
            
            if not hit_db:
                current_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
                if not DesktopUtils.icon_exists(hwnd_lv, shortcut) or current_count != original_count:
                    original_count = current_count
                    shortcut = DesktopUtils.get_actual_index(hwnd_lv, item_name)
                    print("Shortcut was probably deleted and recreated, updating index to "+str(shortcut),item_name)
                    if shortcut == -1: 
                        shortcut = DesktopUtils.create_shortcut(hwnd_lv)
                        item_name = DesktopUtils.get_item_text(hwnd_lv, shortcut)

                win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, shortcut, pos)
            

            if current_step >= Steps/2 and not hit_db:
                mouse = win32api.GetCursorPos()
                hit_db = True
                self.throw_shortcut(shortcut, mouse, speed, item_name)

            current_step = current_step + 1
            if current_step< Steps:
                self.window.after(math.ceil(dt*1000),step_move,current_step,hit_db,hit_detected,shortcut,original_count,item_name,offset,cached_images)
            else:
                self.window.geometry(f'+{int(end_x+offset)}+{int(end_y)}')
                self.label.image = cached_images['idle1']
                self.label.configure(image=self.label.image)
                if on_complete:
                    on_complete()
        step_move(current_step,hit_db,hit_detected,shortcut,original_count,item_name,offset,cached_images)

    def lazer(self, duration_ms, on_complete=None):

        start_time = time.time()
        body_width = self.pivot_images['Pivot_Body'].width
        body_height = self.pivot_images['Pivot_Body'].height
        center_p = (body_width // 2, body_height // 2)
        offset_x, offset_y = 0,0
        if self.current_facing == "Right":
            offset_x = 357-body_width
            offset_y = 342-body_height
            self.window.geometry(f'+{int(self.window.geometry().split("+")[-2])+offset_x}+{int(self.window.geometry().split("+")[-1])+offset_y}')
        else:
            offset_y = 342-body_height
            self.window.geometry(f'+{int(self.window.geometry().split("+")[-2])+offset_x}+{int(self.window.geometry().split("+")[-1])+offset_y}')
        frame1db = False
        Indicator_Length = 0.5*1000
        def update_lazer(frame1db,lastangle=0,damagetimer = 0):
            elapsed = (time.time() - start_time) * 1000
            if elapsed < duration_ms:
                geom_parts = self.window.geometry().split('+')
                window_x, window_y = int(geom_parts[-2]), int(geom_parts[-1])
                
                screen_center_x = window_x + center_p[0]
                screen_center_y = window_y + center_p[1]
                

                mouse_x, mouse_y = win32api.GetCursorPos()

                lazer_dir = "Left" if mouse_x < screen_center_x else "Right"


                def get_dir_img(name):
                    img = self.pivot_images[name]
                    return  img.transpose(Image.FLIP_LEFT_RIGHT) if lazer_dir == "Right" else img

                body = get_dir_img('Pivot_Body')
                face = get_dir_img('Pivot_Face')
                corals = get_dir_img('Pivot_Corals')

                rel_x = mouse_x - screen_center_x
                rel_y = mouse_y - screen_center_y
                
                dirconst = -1 if lazer_dir == "Left" else 1
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

                combined = Image.new("RGBA", (357, 342), (0, 0, 0, 0))
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
                
                final_img = ImageTk.PhotoImage(combined)
                self.label.image = final_img
                self.label.configure(image=final_img)
                
                self.window.after(30, lambda: update_lazer(frame1db,lastangle,damagetimer))
            else:
                self.particles_manager.remove_laser("Sharko_Lazer")
                self.window.geometry(f'+{int(self.window.geometry().split("+")[-2])-offset_x}+{int(self.window.geometry().split("+")[-1])-offset_y}')
                idle_img = self.jump_images['idle1']
                self.label.image = idle_img
                self.label.configure(image=idle_img)
                if on_complete: on_complete()
        update_lazer(frame1db)