from ctypes import windll, wintypes, byref
import ctypes
import tkinter as tk
import random
import os
import pygame
import math
import time
from pynput import keyboard, mouse
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageOps, ImageFilter
import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPixmap, QPainter, QImage
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from vfx_manager import VFXManager
import threading
import pythoncom
from win32com.shell import shell, shellcon
from win32com.client import Dispatch
import win32com.client as wcomcli
import win32gui
import win32api
import numpy as np
from boss_bar import ScalableHealthBar

# Import modularized components
from constants import SharkoConstants
from math_utils import MathUtils
from shortcut_utils import DesktopUtils
from tile import Tile


throw_lock = threading.Lock()




# Make Tkinter aware of Windows DPI scaling
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class Sharko(SharkoConstants):
    """Main Sharko character class"""
    thrown_icons = set()


    def __init__(self, image_path, talking_path, greeting_path, removal_path):
        self.app = QApplication(sys.argv)


        self._idle_after_id = None
        self._fight_loop_after_id = None
        try:
            file = open('Lines.txt', 'r', encoding='utf-8')
            self.Lines = file.readlines()
            clean_lines = [self._decode_escapes(line.strip()) for line in self.Lines]
            self.Lines = clean_lines
        except Exception:
            try:
                file = open('Lines.txt', 'r')
                self.Lines = [line.strip() for line in file.readlines()]
            except Exception:
                self.Lines = []
        finally:
            try:
                file.close()
            except Exception:
                pass
        file = open('RemovalLines+IntroLine.txt', 'r', encoding='utf-8')
        removalandintrolines = file.readlines()
        self.RemovalLines = []

        for index, line in enumerate(removalandintrolines):
            decoded = self._decode_escapes(line.strip())
            if index > 2:
                self.RemovalLines.append(decoded)
            elif index == 1:
                self.IntroLine = decoded
        file.close()

        file = open('Questions.txt', 'r', encoding='utf-8')
        removalandintrolines = file.readlines()
        self.Questions = []
        for index, line in enumerate(removalandintrolines):
            decoded = self._decode_escapes(line.strip())
            Current_Question = math.floor(index/5)
            Current_Line  = index - Current_Question*5
            if Current_Line == 0:
                self.Questions.append([])
            self.Questions[Current_Question].append(decoded)
        file.close()

        self.Quiet = False
        self.CutsceneIsPlaying = False
        self.FightModeIsOn = False
        self.Moviemode = False
        self.end = False
        self.Beingmoved = False
        self.geomreminder = False
        self.window = tk.Tk()
        self.active_bar = None
        
        self.sound_enabled = True
        pygame.init()
        self.Screen_x = self.window.winfo_screenwidth()
        self.Screen_y = self.window.winfo_screenheight()
        self.CurrentDirection = "Right"
        self.current_state = 'greeting'
        self.sound_file = self.GREETING_SOUND
        self.frame = 0
        self.min_volume = 0.1
        self.load_images(image_path, talking_path, greeting_path, removal_path)
        self.create_gui()
        self.animate()
        self.sounds(self.sound_file)
        self.add_talking_sentences(self.IntroLine.strip(),'greeting',False)
        self.window.after(self.GREETING_ANIMATION_DELAY, self.idle_state)
        self.sound_paths = [self.END_TALKING_SOUND, self.START_TALKING_SOUND, self.GREETING_SOUND, self.CLASH_SOUND, self.ANSWER_SOUND, self.BLOCK_ATTEMPT_SOUND, self.PARRY_SOUND, self.BLOCK_SOUND,self.HIT_SOUND]
        self.sounds_group = [pygame.mixer.Sound(path) for path in self.sound_paths]
        self.Walkspeed = 230 #Pixels per second
        self.walking_enabled = True
        self.SupressRightClicks = False
        
        # Parry and block mechanics
        self.parry_press_time = 0  # when 'f' was pressed
        self.parry_active_until = 0  # timestamp when parry window expires
        self.last_parry_block_time = 0
        self.blocking = False
        self.block_active_until = 0  # timestamp when block ends
        self.parry_window = 0.3  # seconds
        self.parry_block_cooldown = 0.75  # seconds
        self.block_transition_callback = None  # scheduled callback to transition to block mode
        self.f_key_held = False  # tracks current f key state

        screen_width = windll.user32.GetSystemMetrics(0)
        screen_height = windll.user32.GetSystemMetrics(1)
        desktop_working_area = wintypes.RECT()
        windll.user32.SystemParametersInfoW(SharkoConstants.SPI_GETWORKAREA, 0, byref(desktop_working_area), 0)
        work_area_height = desktop_working_area.bottom - desktop_working_area.top
        thickness_vertical = screen_height - work_area_height    
        if thickness_vertical > 0:
            TaskbarThick = thickness_vertical
        else:
            TaskbarThick = 0

        x = self.Screen_x-357
        y = self.Screen_y-342-TaskbarThick
        self.x = x
        self.y = y
        self.window.geometry(f"+{x}+{y}")
        self.last_input_time = time.time()


        keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        mouse_listener = mouse.Listener(on_move=self.on_click,on_click=self.on_click)

        keyboard_listener.start()
        mouse_listener.start()

        self.window.mainloop()


    def _decode_escapes(self, s):
        """Decode escape sequences and HTML entities in strings"""
        if not isinstance(s, str):
            return s
        if ('\\u' in s) or ('\\x' in s) or ('\\U' in s) or ('&#' in s) or ('&' in s):
            try:
                decoded = s.encode('utf-8').decode('unicode_escape')
            except Exception:
                decoded = s
            try:
                import html
                decoded = html.unescape(decoded)
            except Exception:
                pass
            return decoded
        return s

    def load_cutscenes(self):
                #Cutscene Format:
                #[image1, howlongtokeepimage1,sound], [image2, howlongtokeepimage2,sound], etc
                #["repeat",firstimage,secondimage, sound, timebetweentransitions, #transitions, Isthisfirstframe(just keep it true)] if you want it to repeat between 2 frames for dialouge
                #howlongtokeep & timebetweentransitions are in miliseconds
                self.CutscenePresets = {
            'InactiveCutscene': [[tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')), 1000, "None"],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'sideframe.png')), 150, "None"],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'staringframe.png')), 1000, "None"],
                     ["repeat",tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloSmall1.png')),tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloSmall2.png')), 1, 500, 10,True],
                     ["repeat",tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloBig1.png')),tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloBig2.png')), 3, 500, 11,True],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'staringframe.png')), 1000, "None"],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'sideframe.png')), 150, "None"]],

        }


    def load_images(self, image_path, talking_path, greeting_path, removal_path):
        self.IMAGES_PATH = image_path
        self.TALKING_SENTENCES_PATH = talking_path
        self.GREETING_SENTENCES_PATH = greeting_path
        self.REMOVAL_SENTENCES_PATH = removal_path
        self.load_cutscenes()

        self.states = {
            'idle': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle2.png'))],
            'Limbo': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle2.png'))],
            'walking': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'walk1.png')),
                        tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'walk2.png'))],

            'talking': [],

            'fight': [],

            'greeting': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking1.png')),
                        tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking2.png'))],

            'MovieG': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'glasses1.png')),
                         tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'glasses2.png'))],
            
            'MovieNG': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle2.png'))],

            'cutscene': [],

            'removal': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking1.png')),
                        tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking2.png'))],
        }
        
        # Pre-load jump images for fighting to avoid loading them in each frame
        self.jump_images = {
            'jump1': tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'jump1.png')),
            'jump2': tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'jump2.png')),
            'jump3': tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'jump3.png')),
            'jump4': tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'jump4.png')),
            'idle1': tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png'))
        }
        self.alt_jump_images = {
            'jump1': tk.PhotoImage(file=os.path.join(self.ALT_1IMAGES_PATH, 'jump1.png')),
            'jump2': tk.PhotoImage(file=os.path.join(self.ALT_1IMAGES_PATH, 'jump2.png')),
            'jump3': tk.PhotoImage(file=os.path.join(self.ALT_1IMAGES_PATH, 'jump3.png')),
            'jump4': tk.PhotoImage(file=os.path.join(self.ALT_1IMAGES_PATH, 'jump4.png')),
            'idle1': tk.PhotoImage(file=os.path.join(self.ALT_1IMAGES_PATH, 'idle1.png'))
        }
        self.pivot_images = {
            'Pivot_Body': Image.open(os.path.join(self.IMAGES_PATH, 'Pivot_Body.png')).convert("RGBA"),
            'Pivot_Face': Image.open(os.path.join(self.IMAGES_PATH, 'Pivot_Face.png')).convert("RGBA"),
            'Pivot_Corals': Image.open(os.path.join(self.IMAGES_PATH, 'Pivot_Corals.png')).convert("RGBA")
        }




    def move_window_x(self,window, target_x):
        ANIMATION_DELAYOrig = self.ANIMATION_DELAY
        self.ANIMATION_DELAY = int(self.ANIMATION_DELAY/2)
        start_x = int(window.geometry().split('+')[-2])

        total_dx = target_x - start_x
        duration_ms = int(math.ceil(abs(total_dx)/self.Walkspeed)*1000)   
        FRAME_DELAY_MS = 16 
        num_steps = max(1, duration_ms // FRAME_DELAY_MS)
        step_dx = total_dx / num_steps
        def step_move(current_step, current_x):
            if self.FightModeIsOn == True:
                return

            if self.end == True or self.Beingmoved == True:
                self.ANIMATION_DELAY = ANIMATION_DELAYOrig
                self.window.after(FRAME_DELAY_MS, self.idle_state)
                return

            if current_step >= num_steps:
                self.ANIMATION_DELAY = ANIMATION_DELAYOrig
                window.geometry(f'+{target_x}+{window.geometry().split('+')[-1]}')
                if self.CurrentDirection == "Right" :
                    self.window.after(FRAME_DELAY_MS, self.rotate_right)
                    self.window.after(FRAME_DELAY_MS+1, self.idle_state)
                else:
                    self.window.after(FRAME_DELAY_MS, self.rotate_left)
                    self.window.after(FRAME_DELAY_MS+1, self.idle_state)
                return

            new_x = int(current_x + step_dx)
            self.x = new_x
            window.geometry(f'+{new_x}+{window.geometry().split('+')[-1]}')
            window.after(FRAME_DELAY_MS, step_move, current_step + 1, current_x + step_dx)
        window.after(FRAME_DELAY_MS, step_move, 0, start_x)



    def Lazer(self, duration_ms, on_complete=None):



        start_time = time.time()
        body_width = self.pivot_images['Pivot_Body'].width
        body_height = self.pivot_images['Pivot_Body'].height
        center_p = (body_width // 2, body_height // 2)
        offset_x, offset_y = 0,0
        if self.CurrentDirection == "Right":
            offset_x = 357-body_width
            offset_y = 342-body_height
            self.window.geometry(f'+{int(self.window.geometry().split('+')[-2])+offset_x}+{int(self.window.geometry().split('+')[-1])+offset_y}')
        else:
            offset_y = 342-body_height
            self.window.geometry(f'+{int(self.window.geometry().split('+')[-2])+offset_x}+{int(self.window.geometry().split('+')[-1])+offset_y}')
        def update_lazer():
            elapsed = (time.time() - start_time) * 1000
            
            if elapsed < duration_ms:
                mouse_x, mouse_y = win32api.GetCursorPos()
                geom_parts = self.window.geometry().split('+')
                window_x, window_y = int(geom_parts[-2]), int(geom_parts[-1])
                
                screen_center_x = window_x + center_p[0]
                screen_center_y = window_y + center_p[1]
                


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
                face_angle = max(min(norm_angle, 16), -60)
                overflow_angle = (norm_angle - face_angle)*dirconst
                face_angle = face_angle*dirconst
                rot_dir = -1 

                rad = math.radians(face_angle)
                local_offset_x = 10 * dirconst
                local_offset_y = 25
                rotated_offset_x = local_offset_x * math.cos(rad) - local_offset_y * math.sin(rad)
                rotated_offset_y = local_offset_x * math.sin(rad) + local_offset_y * math.cos(rad)

                pivot_x = screen_center_x + rotated_offset_x
                pivot_y = screen_center_y + rotated_offset_y
                mouse_x, mouse_y = win32api.GetCursorPos()
                dx, dy = mouse_x - pivot_x, mouse_y - pivot_y
                angle = math.degrees(math.atan2(dy, dx))
                self.vfx.set_laser("Sharko_Lazer", pivot_x, pivot_y, angle, offset=70)

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
                
                self.window.after(16, update_lazer)
            else:
                self.vfx.remove_laser("Sharko_Lazer")
                self.window.geometry(f'+{int(self.window.geometry().split('+')[-2])-offset_x}+{int(self.window.geometry().split('+')[-1])-offset_y}')
                idle_img = self.jump_images['idle1']
                self.label.image = idle_img
                self.label.configure(image=idle_img)
                if on_complete: on_complete()
        update_lazer()
            



    def JumpAndHit(self,jump_peak,shortcut,speed,on_complete=None):
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
            TaskbarThick = thickness_vertical
        else:
            TaskbarThick = 0
        end_x, end_y = DesktopUtils.clamp(peak_x+(peak_x-start_x)/2+np.sign(peak_x-start_x)*210, 0, screen_width - 357), self.Screen_y-342-TaskbarThick
        if end_x - start_x > 0:
            peak_x = peak_x-84
        else:
            peak_x = peak_x-266
        P0 = (start_x, start_y)
        Pmid = (peak_x, peak_y)
        P2 = (end_x, end_y)
        B, P1 = MathUtils.quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5)
        L2 = MathUtils.quadratic_length(P0, P1, P2, n=2000)
        
        T = 1*(L2/(speed*1800))**0.4
        Steps = math.floor(T*60)
        dt = T/Steps
        original_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
        ts = np.linspace(0, 1, Steps)
        points = B(ts)
        hashit = False
        hit_detected = False
        sprite_width = 165
        sprite_height = 165
        current_step = 2
        cached_images = self.jump_images
        offset = 0
        if end_x > start_x:
            cached_images = self.alt_jump_images
            offset = int(359/2)

        item = folder_view.Item(shortcut)
        start_pos = folder_view.GetItemPosition(item)
        pos = win32api.MAKELONG(int(start_pos[0]), int(start_pos[1]))
        
        # Cache image dictionaries for performance
        last_image = None  # Track last displayed image to avoid redundant updates
        
        def Step_move(current_step,hashit,hit_detected,shortcut,original_count,item_name,offset,cached_images):
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

            # Use preloaded image dictionary and only update if image changes
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
            
            # Only check cursor collision every 2 frames to reduce system calls
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
                    self.damage()
            
            if hashit == False:
                current_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
                if not DesktopUtils.icon_exists(hwnd_lv, shortcut) or current_count != original_count:
                    original_count = current_count
                    shortcut = DesktopUtils.get_actual_index(hwnd_lv, item_name)
                    print("Shortcut was probably deleted and recreated, updating index to "+str(shortcut),item_name)
                    if shortcut == -1: 
                        shortcut = DesktopUtils.create_shortcut(hwnd_lv)
                        item_name = DesktopUtils.get_item_text(hwnd_lv, shortcut)

                win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, shortcut, pos)
            

            if current_step >= Steps/2 and hashit == False:
                mouse = win32api.GetCursorPos()
                hashit = True
                self.throw_shortcut(shortcut, mouse, speed, item_name)

            current_step = current_step + 1
            if current_step< Steps:
                self.window.after(math.ceil(dt*1000),Step_move,current_step,hashit,hit_detected,shortcut,original_count,item_name,offset,cached_images)
            else:
                self.window.geometry(f'+{int(end_x+offset)}+{int(end_y)}')
                self.label.image = cached_images['idle1']
                self.label.configure(image=self.label.image)
                if on_complete:
                    on_complete()
        Step_move(current_step,hashit,hit_detected,shortcut,original_count,item_name,offset,cached_images)

    def Jump(self,jump_end,speed,on_complete=None):
        end_x, end_y, start_x, start_y = jump_end[0], jump_end[1], int(self.window.geometry().split('+')[-2]), int(self.window.geometry().split('+')[-1])
        dist = math.sqrt((end_x-start_x)**2+(end_y-start_y)**2)
        screen_height = windll.user32.GetSystemMetrics(1)
        screen_width = windll.user32.GetSystemMetrics(0) 
        screendiagonal = math.sqrt(screen_height**2+screen_width**2)
        peak_x, peak_y = (start_x+end_x)/2, (start_y+end_y)/2-screen_height*((dist/screendiagonal)*0.7)
        if end_x - start_x > 0:
            peak_x = peak_x-84
        else:
            peak_x = peak_x-266

        P0 = (start_x, start_y)
        Pmid = (peak_x, peak_y)
        P2 = (end_x, end_y)
        B, P1 = MathUtils.quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5)
        L2 = MathUtils.quadratic_length(P0, P1, P2, n=2000)
        
        T = 0.75*(L2/(speed*1800))**0.4
        Steps = math.floor(T*60)
        dt = T/Steps
        ts = np.linspace(0, 1, Steps)
        points = B(ts)
        current_step = 2
        img_pth = self.IMAGES_PATH
        offset = 0
        hit_detected = False
        sprite_width = 165
        sprite_height = 165
        if end_x > start_x:
            img_pth = self.ALT_1IMAGES_PATH
            offset = int(359/2)
        
        # Cache image dictionaries for performance
        cached_images = self.alt_jump_images if img_pth == self.ALT_1IMAGES_PATH else self.jump_images
        frame_counter = 0  # Track frames for cursor position sampling
        last_image = None  # Track last displayed image to avoid redundant updates
        
        def Step_move(current_step, hit_detected,img_pth,offset):
            nonlocal frame_counter, last_image
            frame_counter += 1
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
                    img_pth = self.ALT_1IMAGES_PATH
                    offset = int(359/2)
                elif current_x-previous_x+2 < 0:
                    img_pth = self.IMAGES_PATH
                    offset = 0

            # Use preloaded image dictionary and only update if image changes
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
            
            # Only check cursor collision every 2 frames to reduce system calls
            if not hit_detected and frame_counter % 2 == 0:
                mouse_x, mouse_y = win32api.GetCursorPos()
                sprite_x = current_x + offset
                sprite_y = current_y
                if img_pth == self.ALT_1IMAGES_PATH:
                    sprite_x += 192
                    sprite_y += 178
                else:
                    sprite_x += 0
                    sprite_y += 0
                
                if (sprite_x <= mouse_x <= sprite_x + sprite_width and 
                    sprite_y <= mouse_y <= sprite_y + sprite_height):
                    hit_detected = True
                    self.damage()
            
            current_step = current_step + 1
            if current_step < Steps:
                self.window.after(math.ceil(dt*1000),Step_move,current_step,hit_detected,img_pth,offset)
            else:
                self.window.geometry(f'+{int(end_x)}+{int(end_y)}')
                self.label.image = cached_images['idle1']
                self.label.configure(image=self.label.image)
                if on_complete:
                    on_complete()
        Step_move(current_step, hit_detected,img_pth,offset)
        

    def create_gui(self):
        self.label = tk.Label(self.window, bd=0, bg='#2a2d2a')
        self.label.configure(image=self.states['idle'][0])
        self.label.image = self.states['idle'][0]
        self.label.pack()

        self.menu = tk.Menu(self.window, tearoff=0)
        self.Movie_menu = tk.Menu(self.window, tearoff=0)
        self.Movie_menu.add_command(label='Off', command=self.MovieOff)
        self.Movie_menu.add_command(label='On(Glasses)', command=self.MovieOn)
        self.Movie_menu.add_command(label='On(No glasses)', command=self.MovieOn1)
        self.menu.add_cascade(label='Movie mode', menu=self.Movie_menu)
        self.menu.add_command(label='Fight', command=self.toggle_fight_mode)
        self.menu.add_command(label='Sounds (Off/On)', command=self.sounds_logics)
        self.menu.add_command(label='Walking (Off/On)', command=self.toggle_walking)
        self.menu.add_command(label='Flip side', command=self.flip_side)
        self.menu.add_command(label='Close', command=self.close_command)

        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.wm_attributes('-transparentcolor', '#2a2d2a')
        self.window.geometry(self.WINDOW_SIZE)
        


        self.label.bind("<ButtonPress-2>", self.move1)
        self.label.bind("<ButtonRelease-2>", self.release)
        self.label.bind("<B2-Motion>", self.move2)
        self.label.bind("<Double-Button-2>", lambda event: self.menu.post(event.x_root, event.y_root))


    def animate(self):
        if self.label.image == None:
            return
        if self.geomreminder == True:
            self.geomreminder = False
            if self.CurrentDirection == "Left":
                self.window.geometry(f'+{0}+{self.window.geometry().split('+')[-1]}')
            else: 
                self.window.geometry(f'+{self.Screen_x-359}+{self.window.geometry().split('+')[-1]}')

        if self.CutsceneIsPlaying == True or self.FightModeIsOn == True:
            return
        state_images = self.states.get(self.current_state, [])
        if not state_images:
            state_images = self.states.get('idle', [])
            if not state_images:
                self.window.after(self.ANIMATION_DELAY, self.animate)
                return
            self.current_state = 'idle'

        self.frame = (self.frame + 1) % len(state_images)
        self.label.configure(image=state_images[self.frame])
        self.label.image = state_images[self.frame]

        self.window.after(self.ANIMATION_DELAY, self.animate)

    def play_cutscene(self, cutscenepreset):
        if self.CutsceneIsPlaying == True:
            return
        self.CutsceneIsPlaying = True
        self.new_state('cutscene')
        Cutscene = self.CutscenePresets[cutscenepreset]
        self.PlayCutsceneFrame(Cutscene, 0,cutscenepreset)


    def PlayCutsceneFrame(self, Cutscene, Currentframe,cutscenepreset):
        if cutscenepreset== 'InactiveCutscene':
            if time.time()-self.last_input_time < self.INACTIVE_TIME_REQUIREMENT:
                if Currentframe <6:
                    Currentframe = 6 
                elif Currentframe == len(Cutscene):
                    self.CutsceneIsPlaying = False
                    self.Quiet = False
                    self.load_cutscenes()
                    self.idle_state()
                    self.animate()
                    return
            elif Currentframe == len(Cutscene):
                self.CutsceneIsPlaying = False
                self.Quiet = True
                self.load_cutscenes()
                self.idle_state()
                self.animate()
                return


        if Currentframe == len(Cutscene):
            self.CutsceneIsPlaying = False
            self.load_cutscenes()
            self.idle_state()
            self.animate()
            return
            


        
        CurrentFrameInfo = Cutscene[Currentframe]
        if CurrentFrameInfo[0] == "repeat":
            Image = CurrentFrameInfo[1]
            Time = CurrentFrameInfo[4]
            Sound = CurrentFrameInfo[3]
            CurrentFrameInfo[5] = CurrentFrameInfo[5]-1
            FF = CurrentFrameInfo[6]
            CurrentFrameInfo[6] = False
            CurrentFrameInfo[1], CurrentFrameInfo[2] = CurrentFrameInfo[2], CurrentFrameInfo[1]
            if CurrentFrameInfo[5] == 0 :
                Currentframe = Currentframe + 1
        else:
            Image = CurrentFrameInfo[0]
            Time = CurrentFrameInfo[1]
            Sound = CurrentFrameInfo[2]
            Currentframe = Currentframe + 1
            FF = True
        if Sound != "None" and FF == True:
            Soundfile = self.sound_paths[Sound]
            self.sounds(Soundfile)
        self.label.configure(image=Image)
        self.label.image = Image
        self.window.after(Time, self.PlayCutsceneFrame,Cutscene,Currentframe,cutscenepreset)


        



    def clear_talking(self,state):
        self.states[state] = []
        if hasattr(self, 'talk_overlay') and self.talk_overlay is not None:
            try:
                self.talk_overlay.destroy()
            except Exception:
                pass
            self.talk_overlay = None
        if getattr(self, 'question_active', False):
            self.question_active = False
            self._question_answers = None
            try:
                self.label.unbind("<Button-1>")
            except Exception:
                pass


    def move1(self, event):
        if self.FightModeIsOn == True or self.CutsceneIsPlaying == True:
            return
        self.y = event.y
        self.x = event.x
        self.Beingmoved = True

    def _handle_question_click(self, event):
        if not getattr(self, 'question_active', False):
            return
        x_off = 97 if self.CurrentDirection == "Left" else 9
        x = event.x
        y = event.y
        if x >= x_off and x <= x_off + 255 and y >= 96 and y <= 126:
            answer_text = self._question_answers[0] if self._question_answers else None
            if answer_text:
                sound_file = self.ANSWER_SOUND
                self.sounds(sound_file)
                self._display_answer(answer_text)
        elif x >= x_off and x <= x_off + 255 and y >= 126 and y <= 163:
            answer_text = self._question_answers[1] if self._question_answers else None
            if answer_text:
                sound_file = self.ANSWER_SOUND
                self.sounds(sound_file)
                self._display_answer(answer_text)

    def _display_answer(self, answer_text):
        self.question_active = False
        self._question_answers = None
        try:
            self.label.unbind("<Button-1>")
        except Exception:
            pass
        try:
            if getattr(self, '_idle_after_id', None) is not None:
                self.window.after_cancel(self._idle_after_id)
        except Exception:
            pass
        self.add_talking_sentences(answer_text, 'talking', False)
        self.new_state('talking')
        try:
            self._idle_after_id = self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)
        except Exception:
            self._idle_after_id = None


    def release(self, event):
        self.y = event.y
        self.Beingmoved = False


    def move2(self, event):
        if self.FightModeIsOn == True or self.CutsceneIsPlaying == True:
            return
        x = self.window.winfo_pointerx() - self.x
        y = self.window.winfo_pointery() - self.y
        self.window.geometry(f"+{x}+{y}")


    def new_state(self, new_state):
        self.current_state = new_state

    def MovieOff(self):
        self.Moviemode = False
        self.idle_state()

    def MovieOn(self):
        self.Moviemode = True
        self.new_state('MovieG')
    
    def MovieOn1(self):
        self.Moviemode = True
        self.new_state('MovieNG')

    def toggle_walking(self):
        self.walking_enabled = not self.walking_enabled
        if not self.walking_enabled and self.current_state == 'walking':
            self.Beingmoved = True
            try:
                self.window.after(50, self._stop_walk_cleanup)
            except Exception:
                self._stop_walk_cleanup()

    def _stop_walk_cleanup(self):
        self.Beingmoved = False
        if self.current_state == 'walking':
            self.new_state('idle')

    def flip_side(self):
        try:
            if self.CurrentDirection == 'Right':
                self.rotate_right()
                try:
                    y = self.window.geometry().split('+')[-1]
                except Exception:
                    y = self.window.winfo_y()
                self.window.geometry(f'+{0}+{y}')
                self.x = 0
            else:
                self.rotate_left()
                right_x = max(0, self.Screen_x - int(self.WINDOW_SIZE.split('x')[0]))
                try:
                    y = self.window.geometry().split('+')[-1]
                except Exception:
                    y = self.window.winfo_y()
                self.window.geometry(f'+{right_x}+{y}')
                self.x = right_x
            self.window.lift()
            self.geomreminder = True
        except Exception:
            pass



    def on_press(self, key):
        self.last_input_time = time.time()
        self.Quiet = False
        try:
            if key.char == 'f':
                # Only initialize on first press, not on key repeat
                current_time = time.time()
                if self.parry_press_time == 0 and current_time - self.last_parry_block_time >= self.parry_block_cooldown:
                    self.last_parry_block_time = current_time
                    # Cancel any pending callback from previous key press
                    if self.block_transition_callback:
                        try:
                            self.window.after_cancel(self.block_transition_callback)
                        except Exception:
                            pass
                        self.block_transition_callback = None
                    
                    # Start parry window
                    self.f_key_held = True
                    self.parry_press_time = time.time()
                    self.parry_active_until = self.parry_press_time + self.parry_window
                    
                    # Schedule block transition at 0.3s mark
                    def transition_to_block():
                        # Check both that key is held AND that 0.3s has actually passed
                        if self.f_key_held and (time.time() - self.parry_press_time) >= self.parry_window:
                            self.blocking = True
                            self.block_active_until = time.time() + self.parry_window
                            # Extend parry window to include block window
                            self.parry_active_until = self.block_active_until
                            try:
                                self.sounds(self.BLOCK_ATTEMPT_SOUND)
                            except Exception as e:
                                print(f"Error playing block attempt sound: {e}")
                    
                    self.block_transition_callback = self.window.after(
                        int(self.parry_window * 1000), transition_to_block
                    )
        except AttributeError:
            pass

    def on_release(self, key):
        # Handle parry key release (f)
        try:
            if key.char == 'f':
                self.f_key_held = False
                # Cancel pending block transition if released early
                if self.block_transition_callback:
                    try:
                        self.window.after_cancel(self.block_transition_callback)
                    except Exception:
                        pass
                    self.block_transition_callback = None
                
                # If we were blocking, stop it on release
                self.blocking = False
                self.parry_press_time = 0
        except AttributeError:
            pass

    def on_click(self,x, y, button):
        if button == mouse.Button.right and self.SupressRightClicks == True:
            mouse.Listener.suppress_event(self)
        self.last_input_time = time.time()
        self.Quiet = False


    def talking_state(self):
        if self.current_state == 'idle':
            
            Line = random.choice(self.Lines + self.Questions)

            if isinstance(Line, str):
                self.add_talking_sentences(Line.strip(),'talking',False)
                self.new_state('talking')
            else:
                self.add_new_question(Line)
                self.new_state('talking')

            sound_file = self.START_TALKING_SOUND
            self.sounds(sound_file)
        try:
            if getattr(self, '_idle_after_id', None) is not None:
                self.window.after_cancel(self._idle_after_id)
        except Exception:
            pass
        self._idle_after_id = self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)

    
    def idle_state(self):
        try:
            self._idle_after_id = None
        except Exception:
            pass
        if self.current_state == 'talking' or self.current_state == 'cutscene' and self.CutsceneIsPlaying == False or self.current_state == 'greeting'or self.current_state == 'walking' or self.current_state == 'MovieG' and self.Moviemode == False or self.current_state == 'MovieNG' and self.Moviemode == False or self.current_state == 'Limbo' or self.current_state == 'fight' and self.FightModeIsOn == False:
            if not self.current_state == 'walking' and not self.current_state == 'cutscene' and not self.current_state == 'Limbo':
                sound_file = self.END_TALKING_SOUND
                self.sounds(sound_file)
            self.new_state('idle')
            self.clear_talking('talking')
            if time.time()-self.last_input_time > self.INACTIVE_TIME_REQUIREMENT and self.Quiet == False:
                self.Quiet = True
                self.play_cutscene('InactiveCutscene')
            else:
                random_integer = random.randint(1, 20)
                if random_integer > 3 and self.Quiet == False or self.Beingmoved == True or self.walking_enabled == False and self.Quiet == False:
                    self.window.after(self.IDLE_ANIMATION_DELAY, self.talking_state)
                else:
                    if self.walking_enabled == False and self.Quiet == True:
                        self.current_state = 'Limbo'
                        self.window.after(self.IDLE_ANIMATION_DELAY, self.idle_state)
                    else:
                        self.window.after(self.IDLE_ANIMATION_DELAY, self.walking_state)

    def walking_state(self):
        if self.current_state == 'idle':
            self.new_state('walking')

            state_images = self.states.get(self.current_state, [])
            if not state_images:
                return
            self.frame = (self.frame + 1) % len(state_images)
            self.label.configure(image=state_images[self.frame])
            self.label.image = state_images[self.frame]
            if self.CurrentDirection == "Right":
                self.move_window_x(self.window, -179)
            else:
                self.move_window_x(self.window, self.Screen_x-179)

    def add_new_question(self,Question_Lines):
        self.add_talking_sentences(Question_Lines,'talking',3)




    def add_talking_sentences(self,sentence,state,IsQuestion):


        if not hasattr(self, 'Lines') or not self.Lines:
            return


        
        box_w, box_h = 255, 140

        def render_text_image(text, size):
            img = Image.new('RGBA', (size[0], size[1]), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            base_font_path = self.FONT

            padding = 0
            line_spacing = 8 

            for font_size in range(72, 7, -1):
                font = ImageFont.truetype(base_font_path, font_size)

                words = text.split()
                lines = []
                cur = ''
                for w in words:
                    test = (cur + ' ' + w).strip()
                    bbox = draw.multiline_textbbox((0, 0), test, font=font)
                    tw = bbox[2] - bbox[0]
                    if tw <= size[0] - padding * 2:
                        cur = test
                    else:
                        if cur:
                            lines.append(cur)
                        cur = w
                if cur:
                    lines.append(cur)

                allowable_w = size[0] - padding * 2
                too_wide = False
                for l in lines:
                    try:
                        bbox = draw.multiline_textbbox((0, 0), l, font=font)
                        if bbox[2] - bbox[0] > allowable_w:
                            too_wide = True
                            break
                    except Exception:
                        too_wide = True
                        break
                if too_wide:
                    continue

                try:
                    ascent, descent = font.getmetrics()
                    single_line_h = ascent + descent
                except Exception:
                    try:
                        bbox = draw.textbbox((0, 0), 'Mg', font=font)
                        single_line_h = bbox[3] - bbox[1]
                    except Exception:
                        single_line_h = 12
                total_h = single_line_h * len(lines) + (len(lines)-1) * line_spacing
                if total_h <= size[1] - padding * 2:
                    y = 0
                    for i, l in enumerate(lines):
                        bbox = draw.multiline_textbbox((0, 0), l, font=font)
                        tw = bbox[2] - bbox[0]
                        x = 0
                        draw.text((x, y), l, font=font, fill=(0, 0, 0, 255))
                        y += single_line_h + line_spacing
                    return img

            draw.text((0, 0), text, font=ImageFont.load_default(), fill=(0,0,0,255))
            return img

        if IsQuestion == 3:
            try:
                question_text = sentence[0]
                option1_text = sentence[1]
                option2_text = sentence[2]
                answer1_text = sentence[3]
                answer2_text = sentence[4]
            except Exception:
                return

            q_img = render_text_image(question_text, (255, 80))
            opt1_img = render_text_image(option1_text, (255, 30))
            opt2_img = render_text_image(option2_text, (255, 30))

            try:
                base1_path = os.path.join(self.IMAGES_PATH, 'talking1.png')
                base2_path = os.path.join(self.IMAGES_PATH, 'talking2.png')
                base1 = Image.open(base1_path).convert('RGBA')
                base2 = Image.open(base2_path).convert('RGBA')
            except Exception:
                try:
                    combined = Image.new('RGBA', (255, 140), (0, 0, 0, 0))
                    combined.paste(q_img, (0, 9), q_img)
                    combined.paste(opt1_img, (0, 96), opt1_img)
                    combined.paste(opt2_img, (0, 126), opt2_img)
                    tk_img = ImageTk.PhotoImage(combined)
                    self.states[state] = [tk_img, tk_img]
                    self._question_answers = (answer1_text, answer2_text)
                    self.question_active = True
                    try:
                        self.label.bind("<Button-1>", self._handle_question_click)
                    except Exception:
                        pass
                except Exception:
                    return
                return

            def composite_three(base_img):
                b = base_img.copy()
                if self.CurrentDirection == "Left":
                    x = 97
                else:
                    x = 9
                b.paste(q_img, (x, 9), q_img)
                b.paste(opt1_img, (x, 96), opt1_img)
                b.paste(opt2_img, (x, 126), opt2_img)
                return b

            comp1 = composite_three(base1)
            comp2 = composite_three(base2)

            try:
                tk_img1 = ImageTk.PhotoImage(comp1)
                tk_img2 = ImageTk.PhotoImage(comp2)
            except Exception:
                return

            self.states[state] = [tk_img1, tk_img2]
            self._question_answers = (answer1_text, answer2_text)
            self.question_active = True
            try:
                self.label.bind("<Button-1>", self._handle_question_click)
            except Exception:
                pass
            return

        

        text_img = render_text_image(sentence, (box_w, box_h))
        try:
            base1_path = os.path.join(self.IMAGES_PATH, 'talking1.png')
            base2_path = os.path.join(self.IMAGES_PATH, 'talking2.png')
            base1 = Image.open(base1_path).convert('RGBA')
            base2 = Image.open(base2_path).convert('RGBA')
        except Exception:
            try:
                tk_img = ImageTk.PhotoImage(text_img)
            except Exception:
                return
            self.states[state] = [tk_img, tk_img]
            return

        def composite_on_base(base_img):
            b = base_img.copy()
            bw, bh = b.size
            if self.CurrentDirection == "Left":
                x = 97
            else:
                x = 9
            y = 9
            if IsQuestion == 1:
                y = 96
            elif IsQuestion == 2:
                y = 126
            b.paste(text_img, (x, y), text_img)
            return b

        comp1 = composite_on_base(base1)
        comp2 = composite_on_base(base2)

        try:
            tk_img1 = ImageTk.PhotoImage(comp1)
            tk_img2 = ImageTk.PhotoImage(comp2)
        except Exception:
            return

        self.states[state] = [tk_img1, tk_img2]

    
    def add_removal_sentences(self):
        self.add_talking_sentences(random.choice(self.RemovalLines).strip(),'removal',False)


    def close_command(self):
        self.end = True
        if self.current_state != 'removal' and self.current_state != 'cutscene':
            self.add_removal_sentences()
            self.new_state('removal')
        if not getattr(self, '_death_scheduled', False):
            self._death_scheduled = True
            self.window.after(self.REMOVAL_ANIMATION_DELAY, self.death_animation)


    def exit():
        os._exit(0)

    def death_animation(self):
        Screen_x,Screen_y = self.window.winfo_x(), self.window.winfo_y()
        window = self.window
        TILE_SIZE = 15

        class DeathAnimationWidget(QWidget):

            def __init__(self, src_path):
                super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
                self.setAttribute(Qt.WA_TranslucentBackground)
                self.setWindowFlag(Qt.WindowStaysOnTopHint)
                self.setWindowFlag(Qt.Tool)
                self.setWindowFlag(Qt.FramelessWindowHint)
                self.tiles = []
                self.vfx = []
                self.firstime = True
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.animate)
                self.load_tiles(src_path)
                src_path.size = (357, 342)
                self.resize(self.img_w, self.img_h)
                self.setGeometry(Screen_x-50,Screen_y-600, self.img_w, self.img_h)
                self.setFixedSize(600,2000)
                self.show()
                self.timer.start(16)


            def load_tiles(self, src_path):

                src = src_path
                self.img_w = src.width()
                self.img_h = src.height()
                for y in range(0, self.img_h, TILE_SIZE):
                    for x in range(0, self.img_w, TILE_SIZE):
                        tile_img = src.copy(x, y, TILE_SIZE, TILE_SIZE)
                        if tile_img.hasAlphaChannel():
                            self.tiles.append(Tile(QPixmap.fromImage(tile_img), x+50, y))

            def animate(self):
                for tile in self.tiles:
                    tile.update()
                self.tiles = [t for t in self.tiles if t.alpha > 0]
                if not self.tiles:
                    os._exit(0)
                self.update()
                if self.firstime == True:
                    window.withdraw()
                    self.firstime = False

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)
                for tile in self.tiles:
                    painter.save()
                    painter.setOpacity(tile.alpha / 255.0)
                    painter.translate(tile.x + TILE_SIZE // 2, tile.y + TILE_SIZE // 2)
                    painter.rotate(tile.angle)
                    painter.translate(-TILE_SIZE // 2, -TILE_SIZE // 2)
                    painter.drawPixmap(0, 0, tile.img)
                    painter.restore()
        state_images = self.states.get(self.current_state, [])

        if len(sys.argv) > 1:
            img_path = sys.argv[1]
            img_path = state_images[self.frame]
            img_path = ImageTk.getimage(img_path)
        else:
            img_path = state_images[self.frame]
            img_path = ImageTk.getimage(img_path)
            img = img_path.convert("RGBA")
            r, g, b, a = img.split()
            bgra = Image.merge("RGBA", (b, g, r, a))
            buf = bgra.tobytes("raw", "RGBA")
            w,h = img.size
            qimg = QImage(buf, w ,h , 4*w, QImage.Format_ARGB32)
            qimg._buf = buf
        w = DeathAnimationWidget(qimg)
        
        sys.exit(self.app.exec_())

    
    def damage(self):
        current_time = time.time()
        mouse_x, mouse_y = win32api.GetCursorPos()
        
        # Check if in parry/block window (parry window OR key is still held)
        if current_time < self.parry_active_until or self.f_key_held:
            # Check cooldown
            # Calculate how long the key has been held
            time_held = current_time - self.parry_press_time if self.f_key_held else 0
            # Block if held >= 0.3s, otherwise parry
            if time_held >= self.parry_window:
                print("Blocked! Attack negated.")
                self.last_parry_block_time = 0
                try:
                    self.sounds(self.BLOCK_SOUND)
                except Exception as e:
                    print(f"Error playing block sound: {e}")
                if self.vfx:
                    self.vfx.play_block(mouse_x, mouse_y)
            else:
                print("Parried! Attack blocked.")
                self.last_parry_block_time = 0
                try:
                    self.sounds(self.PARRY_SOUND)
                except Exception as e:
                    print(f"Error playing parry sound: {e}")
                if self.vfx:
                    self.vfx.play_parry(mouse_x, mouse_y)
            
            # Clear flags after successful block/parry
            self.blocking = False
            self.parry_active_until = 0
            self.block_active_until = 0
            # Don't clear f_key_held - user is still physically holding the key
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
        
        print("Hit! Damage dealt.")
        # Play blood effect and hit sound
        if self.vfx:
            self.vfx.play_blood(mouse_x, mouse_y)
        try:
            # Try to play a hit/damage sound if it exists
            self.sounds(self.HIT_SOUND)
        except Exception as e:
            pass

    def _throw_worker(self, index, target_pos,speed_factor,name):
        pythoncom.CoInitialize()
        with throw_lock:
            if name in self.thrown_icons:
                pythoncom.CoUninitialize()
                return
            self.thrown_icons.add(name)
        try:

            folder_view, hwnd_lv = DesktopUtils.get_desktop_interfaces(
                SharkoConstants.CLSID_ShellWindows,
                SharkoConstants.IID_IFolderView,
                SharkoConstants.SWC_DESKTOP,
                SharkoConstants.SWFO_NEEDDISPATCH
            )
            item = None
            try:
                item = folder_view.Item(index)
            except Exception:
                with throw_lock:
                    self.thrown_icons.discard(name)

                pythoncom.CoUninitialize()
                return
            item_name = name
            start_pos = folder_view.GetItemPosition(item)
            original_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)

            mousex, mousey = target_pos
            x0, y0 = start_pos

            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)

            spacing = win32gui.SendMessage(hwnd_lv, 0x1033, 0, 0)
            cell_h = (spacing >> 16) & 0xFFFF

            end_x = mousex - cell_h ** 1.2 * 0.10
            end_y = mousey - cell_h ** 1.2 * 0.10

            dx = end_x - x0
            dy = end_y - y0
            over_x = x0 + dx * (1+(0.1/speed_factor))
            over_y = y0 + dy * (1+(0.1/speed_factor))

            over_x = DesktopUtils.clamp(over_x, 0, screen_w - cell_h // 2)
            over_y = DesktopUtils.clamp(over_y, 0, screen_h - cell_h)

            target_x = DesktopUtils.clamp(end_x, 0, screen_w - cell_h // 2)
            target_y = DesktopUtils.clamp(end_y, 0, screen_h - cell_h)

            ctrl_x = (x0 + target_x) // 2
            ctrl_y = min(y0, over_y) - 300

            steps = math.floor(250*speed_factor)
            duration = 2.0*speed_factor
            dt = duration / steps
            hit_registered = False

            for i in range(steps + 1):
                current_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
                if not DesktopUtils.icon_exists(hwnd_lv, index) or current_count != original_count:
                    original_count = current_count
                    index = DesktopUtils.get_actual_index(hwnd_lv, item_name)
                    if index == -1: 
                        with throw_lock:
                            self.thrown_icons.discard(name)

                        pythoncom.CoUninitialize()
                        return

                t = i / steps
                omt = 1 - t

                x = (omt**2) * x0 + 2 * omt * t * ctrl_x + (t**2) * target_x
                y = (omt**2) * y0 + 2 * omt * t * ctrl_y + (t**2) * target_y

                mx, my = win32api.GetCursorPos()

                if not hit_registered and math.dist((x+cell_h//2, y+cell_h//2), (mx, my)) < cell_h//2:
                    hit_registered = True
                    self.damage()

                pos = win32api.MAKELONG(int(x), int(y))
                win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, index, pos)
                time.sleep(dt)

            bob_steps = 45

            dist = math.dist((over_x, over_y), (target_x, target_y))
            dip_amount = DesktopUtils.clamp(dist * 0.15, 5, 80)

            for i in range(bob_steps + 1):
                current_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
                if not DesktopUtils.icon_exists(hwnd_lv, index) or current_count != original_count:
                    original_count = current_count
                    index = DesktopUtils.get_actual_index(hwnd_lv, item_name)
                    if index == -1: 
                        with throw_lock:
                            self.thrown_icons.discard(name)
                        pythoncom.CoUninitialize()
                        return

                t = (i / bob_steps)**0.8
                if not hit_registered and math.dist((x+cell_h//2, y+cell_h//2), (mx, my)) < cell_h//2:
                    hit_registered = True
                    self.damage()
                fall = (1 - t) ** 2
                base_y = over_y + (target_y - over_y) * fall

                dip = dip_amount * (math.sin(t * math.pi)) ** 2

                y = base_y + dip
                x = target_x + (over_x - target_x) * t

                x = DesktopUtils.clamp(x, 0, screen_w - cell_h // 2)
                y = DesktopUtils.clamp(y, 0, screen_h - cell_h)

                pos = win32api.MAKELONG(int(x), int(y))
                win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, index, pos)
                time.sleep(0.01)

        finally:
            with throw_lock:
                self.thrown_icons.discard(name)
            pythoncom.CoUninitialize()

        
    def throw_shortcut(self, index, target_pos,speed_factor,name):
        thread = threading.Thread(
            target=self._throw_worker,
            args=(index, target_pos,speed_factor,name),
            daemon=True,
        )
        thread.start()

        
    def get_closest_icons(self, n):
        pythoncom.CoInitialize()
        try:
            folder_view, _ = DesktopUtils.get_desktop_interfaces(
                SharkoConstants.CLSID_ShellWindows,
                SharkoConstants.IID_IFolderView,
                SharkoConstants.SWC_DESKTOP,
                SharkoConstants.SWFO_NEEDDISPATCH
            )
            mouse = win32api.GetCursorPos()
            items_len = folder_view.ItemCount(shellcon.SVGIO_ALLVIEW)
            dists = []

            for i in range(items_len):
                item = folder_view.Item(i)
                pos = folder_view.GetItemPosition(item)
                d = math.dist(pos, mouse)
                dists.append((d, i))

            dists.sort()
            return [idx for _, idx in dists[:n]],len(dists)

        finally:
            pythoncom.CoUninitialize()


    def restart_application(self, new_image_path, new_talking_path, new_greeting_path, new_removal_path):
        self.window.destroy()
        Sharko(new_image_path, new_talking_path, new_greeting_path, new_removal_path)
    

    def rotate_right(self):

        new_image_path = "assets/mirror_sharko/"
        new_talking_path = "assets/mirror_sentences/talking/"
        new_greeting_path = "assets/mirror_sentences/greeting/"
        new_removal_path = "assets/mirror_sentences/removal/"
        self.load_images(new_image_path,new_talking_path,new_greeting_path,new_removal_path)
        self.CurrentDirection = "Left"
        self.x = 0
        self.geomreminder = True
        try:
            self.new_state('Limbo')
        except Exception:
            pass
        

    def rotate_left(self):
        new_image_path = "assets/sharko/"
        new_talking_path = "assets/sentences/talking/"
        new_greeting_path = "assets/sentences/greeting/"
        new_removal_path = "assets/sentences/removal/"
        self.load_images(new_image_path,new_talking_path,new_greeting_path,new_removal_path)
        self.CurrentDirection = "Right"
        self.x = self.Screen_x-359

        self.geomreminder = True
        try:
            self.new_state('Limbo')
        except Exception:
            pass


    def toggle_fight_mode(self):
        if self.current_state != 'fight':
            self.FightModeIsOn = True
            self.SupressRightClicks = True
            if not self.active_bar:
                self.active_bar = ScalableHealthBar()
                screen_w = ctypes.windll.user32.GetSystemMetrics(0)
                self.active_bar.resize(screen_w // 2, 200)
                self.active_bar.slide_in()
                print("Boss Bar Created from external file.")
                self.vfx = VFXManager()
                self.vfx.play_block(500, 500)
                self.vfx.play_parry(600, 500)
            self.new_state('fight')
            self.fight_loop()
        else:
            self.FightModeIsOn = False
            self.SupressRightClicks = False
            self.vfx.deinitialize()
            del self.vfx
            if getattr(self, '_fight_loop_after_id', None) is not None:
                self.window.after_cancel(self._fight_loop_after_id)
                self._fight_loop_after_id = None
            if self.active_bar:
                self.active_bar.slide_out_to_hide()
                self.active_bar = None
            for aid in self.window.after_info():
                self.window.after_cancel(aid)
            self.idle_state()
            self.animate()

    def fight_loop(self):
        if self.current_state != 'fight':
            return
        print("Fight loop running")
        
        #self.vfx.start_spirit_beam("main_beam", 0, 0, 0, 0)

        #mx, my = win32api.GetCursorPos()
        #self.vfx.update_spirit_beam("main_beam", mx, my, mx, my)
        
        folder_view, hwnd_lv = DesktopUtils.get_desktop_interfaces(
            SharkoConstants.CLSID_ShellWindows,
            SharkoConstants.IID_IFolderView,
            SharkoConstants.SWC_DESKTOP,
            SharkoConstants.SWFO_NEEDDISPATCH
        )
        closest, num_icons = self.get_closest_icons(1)
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        desktop_working_area = wintypes.RECT()
        windll.user32.SystemParametersInfoW(SharkoConstants.SPI_GETWORKAREA, 0, byref(desktop_working_area), 0)
        work_area_height = desktop_working_area.bottom - desktop_working_area.top
        x,y = 0,0
        if num_icons <= 3:
            replacementshortcut = DesktopUtils.create_shortcut(hwnd_lv)
            closest = []
            closest.append(replacementshortcut)
            x = random.randint(350,screen_w-350)
            y = random.randint(350,work_area_height-350)

            pos = win32api.MAKELONG(int(x), int(y))
            win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, replacementshortcut, pos)
        item = folder_view.Item(closest[0])
        item_pos = folder_view.GetItemPosition(item)
        
        def schedule_next_attack():
            """Schedule the next attack 2 seconds after this one finishes"""
            self._fight_loop_after_id = self.window.after(2000, self.fight_loop)
        
        #self.Jump([random.randint(350, screen_w - 350), work_area_height - 343], 1)
        self.JumpAndHit(item_pos,closest[0],0.4,on_complete=schedule_next_attack)
        #self.Lazer(10000,on_complete=schedule_next_attack)


    def sounds(self, sound_file):
        pygame.mixer.init()
        pygame.mixer.music.load(sound_file)
        if self.sound_enabled:
            pygame.mixer.music.set_volume(1.0)
        else:
            pygame.mixer.music.set_volume(0.0)
        pygame.mixer.music.play()

    
    def sounds_logics(self):
        """Toggle sound on/off"""
        self.sound_enabled = not self.sound_enabled
        if not self.sound_enabled:
            for sound in self.sounds_group:
                sound.set_volume(0.0)  
        else:
            for sound in self.sounds_group:
                sound.set_volume(1.0)


# Initialize and run
if __name__ == "__main__":
    sharko = Sharko("assets/sharko/",
                    "assets/sentences/talking/",
                    "assets/sentences/greeting/",
                    "assets/sentences/removal/")