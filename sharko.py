"""
Sharko - Main Character Module

Core implementation of Sharko, the interactive desktop character with features:
- Idle, walking, and fighting animations
- Boss battle system with health bar
- Parry and block combat mechanics
- Desktop icon manipulation and throwing
- Sound effects and particle effects
- Customizable movie mode and UI states
"""
from ctypes import windll, wintypes, byref
import win32gui
import win32api

import random
import math
import time

import tkinter as tk
from tkinter import TclError
import pygame

import os
import sys

from pynput import keyboard, mouse

from PIL import Image, ImageDraw, ImageFont, ImageTk
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPixmap, QPainter, QImage
from PyQt5.QtCore import Qt, QTimer

import threading

from boss_bar import ScalableHealthBar
from vfx_manager import VFXManager, MultiWarningOverlay
from boss_battle import CombatSystem

from constants import SharkoConstants
from icons import IconManager
from shortcut_utils import DesktopUtils
from tile import Tile

import psutil


throw_lock = threading.Lock()


# Make Tkinter aware of Windows DPI scaling
try:
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class Sharko(SharkoConstants, IconManager):
    """Main interactive desktop character with animation, combat, and effects."""
    thrown_icons = set()

    def __init__(self, image_path, talking_path, greeting_path, removal_path):
        """Initialize Sharko character with paths to animation assets.
        
        Args:
            image_path: Path to idle/walking animation images
            talking_path: Path to talking animation images
            greeting_path: Path to greeting animation images
            removal_path: Path to removal animation images
        """
        #APPLICATION & GUI SETUP
        self.app = QApplication(sys.argv)
        self.window = tk.Tk()
        
        #SCREEN & DISPLAY CONFIGURATION
        self.screen_x = self.window.winfo_screenwidth()
        self.screen_y = self.window.winfo_screenheight()
        
        desktop_working_area = wintypes.RECT()
        windll.user32.SystemParametersInfoW(self.SPI_GETWORKAREA, 0, byref(desktop_working_area), 0)
        work_area_height = desktop_working_area.bottom - desktop_working_area.top
        thickness_vertical = self.screen_y - work_area_height    
        if thickness_vertical > 0:
            taskbar_thickness = thickness_vertical
        else:
            taskbar_thickness = 0

        x = self.screen_x - 357
        y = self.screen_y - 342 - taskbar_thickness
        self.x = x
        self.y = y
        self.window.geometry(f"+{x}+{y}")
        
        #CHARACTER & STATE
        self.current_facing = "Right"
        self.current_state = 'greeting'
        self.frame = 0
        
        #GAME STATE FLAGS
        self.talking_disabled = False
        self.cutscene_active = False
        self.fight_mode_active = False
        self.movie_mode_active = False
        self.end = False
        self.currently_moving = False
        self.position_flip_trigger = False
        
        #AUDIO SYSTEM
        self.sound_enabled = True
        self.sound_file = self.GREETING_SOUND
        pygame.init()
        pygame.mixer.set_num_channels(16)
        self.sound_paths = {'end': self.END_TALKING_SOUND, 'start': self.START_TALKING_SOUND, 'greeting': self.GREETING_SOUND, 'clash': self.CLASH_SOUND, 'answer': self.ANSWER_SOUND, 'block_attempt': self.BLOCK_ATTEMPT_SOUND, 'parry': self.PARRY_SOUND, 'block': self.BLOCK_SOUND, 'hit': self.HIT_SOUND}
        self.sounds_group = {name: pygame.mixer.Sound(path) for name, path in self.sound_paths.items()}
        
        #MOVEMENT SYSTEM
        self.walking_enabled = True
        
        #INPUT & INTERACTION
        self.supress_right_clk = False
        self.last_input_time = time.time()
        
        #PARRY AND BLOCK MECHANICS
        self.parry_press_time = 0
        self.parry_active_until = 0
        self.last_parry_block_time = 0
        self.blocking = False
        self.block_active_until = 0
        self.block_transition_callback = None
        self.f_key_held = False
        
        #ASSET LOADING
        self.load_images(image_path, talking_path, greeting_path, removal_path)
        
        #GUI SETUP
        self.create_gui()
        
        #ANIMATION & CALLBACKS
        self._idle_after_id = None
        self._fight_loop_after_id = None
        
        #STARTUP SEQUENCE
        self.animate()
        self.sounds(pygame.mixer.Sound(self.sound_file))
        self.add_talking_sentences(self.intro_line.strip(),'greeting',False)
        self.window.after(self.GREETING_ANIMATION_DELAY, self.idle_state)
        
        #COMBAT SYSTEM
        self.CombatSystem = CombatSystem()
        self.active_bar = None
        
        #SYSTEM MONITORING
        self.process = psutil.Process(os.getpid())
        
        #INPUT LISTENERS
        keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        mouse_listener = mouse.Listener(on_move=self.on_click,on_click=self.on_click)

        keyboard_listener.start()
        mouse_listener.start()

        self.window.mainloop()

    def log_stats(self):
        """Log current memory usage statistics."""
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        print(f"RAM: {mem_mb:.2f} MB")

    def load_cutscenes(self):
        """Load and initialize cutscene animation presets with frames and timing."""
        self.CutscenePresets = {
            'InactiveCutscene': [
                {"image": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')), "duration": 1000, "sound": "None"},
                {"image": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'sideframe.png')), "duration": 150, "sound": "None"},
                {"image": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'staringframe.png')), "duration": 1000, "sound": "None"},
                {"type": "repeat", "image1": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'HelloSmall1.png')), "image2": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'HelloSmall2.png')), "sound": 'start', "interval": 500, "repeat_count": 10, "is_first_frame": True},
                {"type": "repeat", "image1": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'HelloBig1.png')), "image2": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'HelloBig2.png')), "sound": 'clash', "interval": 500, "repeat_count": 11, "is_first_frame": True},
                {"image": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'staringframe.png')), "duration": 1000, "sound": "None"},
                {"image": tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'sideframe.png')), "duration": 150, "sound": "None"}
            ],
        }

    def load_images(self, image_path, talking_path, greeting_path, removal_path):
        """Load all animation images from specified paths into state dictionaries."""
        self.CURRENT_IMAGES_PATH = image_path
        self.TALKING_SENTENCES_PATH = talking_path
        self.GREETING_SENTENCES_PATH = greeting_path
        self.REMOVAL_SENTENCES_PATH = removal_path
        self.load_cutscenes()

        self.states = {
            'idle': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png'))],
            'Limbo': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png'))],
            'walking': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'walk1.png')),
                        tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'walk2.png'))],

            'talking': [],

            'fight': [],

            'greeting': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')),
                        tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png'))],

            'MovieG': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'glasses1.png')),
                         tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'glasses2.png'))],
            
            'MovieNG': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png'))],

            'cutscene': [],

            'removal': [tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')),
                        tk.PhotoImage(file=os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png'))],
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
            'jump1': tk.PhotoImage(file=os.path.join(self.ALT_IMAGES_PATH, 'jump1.png')),
            'jump2': tk.PhotoImage(file=os.path.join(self.ALT_IMAGES_PATH, 'jump2.png')),
            'jump3': tk.PhotoImage(file=os.path.join(self.ALT_IMAGES_PATH, 'jump3.png')),
            'jump4': tk.PhotoImage(file=os.path.join(self.ALT_IMAGES_PATH, 'jump4.png')),
            'idle1': tk.PhotoImage(file=os.path.join(self.ALT_IMAGES_PATH, 'idle1.png'))
        }
        self.pivot_images = {
            'Pivot_Body': Image.open(os.path.join(self.IMAGES_PATH, 'Pivot_Body.png')).convert("RGBA"),
            'Pivot_Face': Image.open(os.path.join(self.IMAGES_PATH, 'Pivot_Face.png')).convert("RGBA"),
            'Pivot_Corals': Image.open(os.path.join(self.IMAGES_PATH, 'Pivot_Corals.png')).convert("RGBA")
        }

    def move_window_x(self, window, target_x):
        """Animate character window movement to target X position.
        
        Args:
            window: Tkinter window to move
            target_x: Target X coordinate
        """
        ANIMATION_DELAYOrig = self.ANIMATION_DELAY
        self.ANIMATION_DELAY = int(self.ANIMATION_DELAY/2)
        start_x = int(window.geometry().split('+')[-2])

        total_dx = target_x - start_x
        duration_ms = int(math.ceil(abs(total_dx)/self.WALKSPEED)*1000)   
        FRAME_DELAY_MS = self.FRAME_DELAY_MS 
        num_steps = max(1, duration_ms // FRAME_DELAY_MS)
        step_dx = total_dx / num_steps
        def step_move(current_step, current_x):
            if self.fight_mode_active:
                return

            if self.end or self.currently_moving:
                self.ANIMATION_DELAY = ANIMATION_DELAYOrig
                self.window.after(FRAME_DELAY_MS, self.idle_state)
                return

            if current_step >= num_steps:
                self.ANIMATION_DELAY = ANIMATION_DELAYOrig
                window.geometry(f'+{target_x}+{window.geometry().split('+')[-1]}')
                if self.current_facing == "Right" :
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
        
    def create_gui(self):
        """Create and configure the GUI elements (label, menus, window properties)."""
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
        try:
            self.label.bind("<Double-Button-2>", lambda event: self.menu.post(event.x_root, event.y_root))
        except (TclError, AttributeError):
            pass

    def animate(self):
        """Update and render current animation frame based on character state."""
        if self.label.image is None:
            return
        if self.position_flip_trigger:
            self.position_flip_trigger = False
            if self.current_facing == "Left":
                self.window.geometry(f'+{0}+{self.window.geometry().split('+')[-1]}')
            else: 
                self.window.geometry(f'+{self.screen_x-359}+{self.window.geometry().split('+')[-1]}')

        if self.cutscene_active or self.fight_mode_active:
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
        if self.cutscene_active:
            return
        self.cutscene_active = True
        self.new_state('cutscene')
        Cutscene = self.CutscenePresets[cutscenepreset]
        self.PlayCutsceneFrame(Cutscene, 0,cutscenepreset)

    def PlayCutsceneFrame(self, Cutscene, current_frame, cutscenepreset):
        if cutscenepreset == 'InactiveCutscene':
            if time.time() - self.last_input_time < self.INACTIVE_TIME_REQUIREMENT:
                if current_frame < 6:
                    current_frame = 6 
                elif current_frame == len(Cutscene):
                    self.cutscene_active = False
                    self.talking_disabled = False
                    self.load_cutscenes()
                    self.idle_state()
                    self.animate()
                    return
            elif current_frame == len(Cutscene):
                self.cutscene_active = False
                self.talking_disabled = True
                self.load_cutscenes()
                self.idle_state()
                self.animate()
                return

        if current_frame == len(Cutscene):
            self.cutscene_active = False
            self.load_cutscenes()
            self.idle_state()
            self.animate()
            return
        
        current_frame_data = Cutscene[current_frame]
        
        # Handle repeating cutscene frames
        Sound_Cleared = False
        if current_frame_data.get("type") == "repeat":
            image = current_frame_data["image1"]
            duration = current_frame_data["interval"]
            sound = current_frame_data["sound"]
            
            # Decrement repeat count
            current_frame_data["repeat_count"] -= 1
            
            # Swap images for next iteration
            if current_frame_data["is_first_frame"]:
                current_frame_data["is_first_frame"] = False
                Sound_Cleared = True
            else:
                current_frame_data["image1"], current_frame_data["image2"] = current_frame_data["image2"], current_frame_data["image1"]
            
            # Move to next frame if repeat count exhausted
            if current_frame_data["repeat_count"] == 0:
                current_frame += 1
        else:
            # Handle simple frames
            image = current_frame_data["image"]
            duration = current_frame_data["duration"]
            sound = current_frame_data["sound"]
            Sound_Cleared = True
            current_frame += 1
        
        # Play sound if not "None"
        if sound != "None" and Sound_Cleared:
            try:
                sound_file = self.sounds_group[sound]
                self.sounds(sound_file)
            except KeyError:
                pass
        
        self.label.configure(image=image)
        self.label.image = image
        self.window.after(duration, self.PlayCutsceneFrame, Cutscene, current_frame, cutscenepreset)

    def clear_talking(self,state):
        self.states[state] = []
        if hasattr(self, 'talk_overlay') and self.talk_overlay is not None:
            try:
                self.talk_overlay.destroy()
            except (RuntimeError, AttributeError):
                pass
            self.talk_overlay = None
        if getattr(self, 'question_active', False):
            self.question_active = False
            self._question_answers = None
            try:
                self.label.unbind("<Button-1>")
            except (TclError, AttributeError):
                pass

    def move1(self, event):
        if self.fight_mode_active or self.cutscene_active:
            return
        self.y = event.y
        self.x = event.x
        self.currently_moving = True

    def _handle_question_click(self, event):
        if not getattr(self, 'question_active', False):
            return
        x_off = 97 if self.current_facing == "Left" else 9
        x = event.x
        y = event.y
        if x >= x_off and x <= x_off + self.QUESTION_BOX_WIDTH and y >= self.QUESTION_BOX_OPTION1_Y and y <= self.QUESTION_BOX_OPTION1_Y + self.QUESTION_BOX_OPTION_HEIGHT:
            answer_text = self._question_answers[0] if self._question_answers else None
            if answer_text:
                self.sounds(self.sounds_group['answer'])
                self._display_answer(answer_text)
        elif x >= x_off and x <= x_off + self.QUESTION_BOX_WIDTH and y >= self.QUESTION_BOX_OPTION2_Y and y <= self.QUESTION_BOX_OPTION2_Y + self.QUESTION_BOX_OPTION_HEIGHT:
            answer_text = self._question_answers[1] if self._question_answers else None
            if answer_text:
                self.sounds(self.sounds_group['answer'])
                self._display_answer(answer_text)

    def _display_answer(self, answer_text):
        self.question_active = False
        self._question_answers = None
        try:
            self.label.unbind("<Button-1>")
        except (TclError, AttributeError):
            pass
        try:
            if getattr(self, '_idle_after_id', None) is not None:
                self.window.after_cancel(self._idle_after_id)
        except (TclError, ValueError):
            pass
        self.add_talking_sentences(answer_text, 'talking', False)
        self.new_state('talking')
        try:
            self._idle_after_id = self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)
        except (TclError, ValueError):
            self._idle_after_id = None

    def release(self, event):
        self.y = event.y
        self.currently_moving = False

    def move2(self, event):
        if self.fight_mode_active or self.cutscene_active:
            return
        x = self.window.winfo_pointerx() - self.x
        y = self.window.winfo_pointery() - self.y
        self.window.geometry(f"+{x}+{y}")

    def new_state(self, new_state):
        self.current_state = new_state

    def MovieOff(self):
        self.movie_mode_active = False
        self.idle_state()

    def MovieOn(self):
        self.movie_mode_active = True
        self.new_state('MovieG')
    
    def MovieOn1(self):
        self.movie_mode_active = True
        self.new_state('MovieNG')

    def toggle_walking(self):
        self.walking_enabled = not self.walking_enabled
        if not self.walking_enabled and self.current_state == 'walking':
            self.currently_moving = True
            try:
                self.window.after(50, self._stop_walk_cleanup)
            except (TclError, ValueError):
                self._stop_walk_cleanup()

    def _stop_walk_cleanup(self):
        self.currently_moving = False
        if self.current_state == 'walking':
            self.new_state('idle')

    def flip_side(self):
        try:
            if self.current_facing == 'Right':
                self.rotate_right()
                try:
                    y = self.window.geometry().split('+')[-1]
                except (IndexError, ValueError):
                    y = self.window.winfo_y()
                self.window.geometry(f'+{0}+{y}')
                self.x = 0
            else:
                self.rotate_left()
                right_x = max(0, self.screen_x - int(self.WINDOW_SIZE.split('x')[0]))
                try:
                    y = self.window.geometry().split('+')[-1]
                except (IndexError, ValueError):
                    y = self.window.winfo_y()
                self.window.geometry(f'+{right_x}+{y}')
                self.x = right_x
            self.window.lift()
            self.position_flip_trigger = True
        except (AttributeError, RuntimeError):
            pass

    def on_press(self, key):
        self.last_input_time = time.time()
        self.talking_disabled = False
        try:
            if key.char == 'f':
                # Only initialize on first press, not on key repeat
                current_time = time.time()
                if self.parry_press_time == 0 and current_time - self.last_parry_block_time >= self.PARRY_BLOCK_COOLDOWN:
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
                    self.parry_active_until = self.parry_press_time + self.PARRY_WINDOW
                    
                    # Schedule block transition at 0.3s mark
                    def transition_to_block():
                        # Check both that key is held AND that 0.3s has actually passed
                        if self.f_key_held and (time.time() - self.parry_press_time) >= self.PARRY_WINDOW:
                            self.blocking = True
                            self.block_active_until = time.time() + self.PARRY_WINDOW
                            # Extend parry window to include block window
                            self.parry_active_until = self.block_active_until
                            try:
                                self.sounds(self.sounds_group['block_attempt'])
                            except Exception as e:
                                print(f"Error playing block attempt sound: {e}")
                    
                    self.block_transition_callback = self.window.after(
                        int(self.PARRY_WINDOW * 1000), transition_to_block
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
        if button == mouse.Button.right and self.supress_right_clk:
            mouse.Listener.suppress_event(self)
        self.last_input_time = time.time()
        self.talking_disabled = False

    def talking_state(self):
        if self.current_state == 'idle':
            
            Line = random.choice(self.Lines + self.Questions)

            if isinstance(Line, str):
                self.add_talking_sentences(Line.strip(),'talking',False)
                self.new_state('talking')
            else:
                self.add_new_question(Line)
                self.new_state('talking')

            self.sounds(self.sounds_group['start'])
        try:
            if getattr(self, '_idle_after_id', None) is not None:
                self.window.after_cancel(self._idle_after_id)
        except Exception:
            pass
        self._idle_after_id = self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)
    
    def _should_transition_to_idle(self) -> bool:
        """Check if current state should transition to idle state."""
        is_talking_like = self.current_state in ['talking', 'greeting', 'removal']
        is_cutscene = self.current_state == 'cutscene' and not self.cutscene_active
        is_walking = self.current_state == 'walking'
        is_movie = (self.current_state == 'MovieG' and not self.movie_mode_active) or \
                   (self.current_state == 'MovieNG' and not self.movie_mode_active)
        is_limbo = self.current_state == 'Limbo'
        is_fight = self.current_state == 'fight' and not self.fight_mode_active
        return is_talking_like or is_cutscene or is_walking or is_movie or is_limbo or is_fight
    
    def idle_state(self):
        try:
            self._idle_after_id = None
        except (AttributeError, TypeError):
            pass
        
        if self._should_transition_to_idle():
            if self.current_state not in ['walking', 'cutscene', 'Limbo']:
                self.sounds(self.sounds_group['end'])
            self.new_state('idle')
            self.clear_talking('talking')
            if time.time() - self.last_input_time > self.INACTIVE_TIME_REQUIREMENT and not self.talking_disabled:
                self.talking_disabled = True
                self.play_cutscene('InactiveCutscene')
            else:
                random_integer = random.randint(1, 20)
                if (random_integer > 13 and not self.talking_disabled) or self.currently_moving or \
                   (not self.walking_enabled and not self.talking_disabled):
                    self.window.after(self.IDLE_ANIMATION_DELAY, self.talking_state)
                else:
                    if not self.walking_enabled and self.talking_disabled:
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
            if self.current_facing == "Right":
                self.move_window_x(self.window, -179)
            else:
                self.move_window_x(self.window, self.screen_x-179)

    def add_new_question(self,Question_Lines):
        self.add_talking_sentences(Question_Lines,'talking',3)

    def add_talking_sentences(self,sentence,state,IsQuestion):

        if not hasattr(self, 'Lines') or not self.Lines:
            return
        
        box_w, box_h = self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT

        def render_text_image(text, size):
            img = Image.new('RGBA', (size[0], size[1]), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            base_font_path = self.FONT

            padding = self.TEXT_RENDER_PADDING
            line_spacing = self.TEXT_LINE_SPACING

            for font_size in range(self.FONT_SIZE_MAX, self.FONT_SIZE_MIN, -1):
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

            q_img = render_text_image(question_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_TEXT_HEIGHT))
            opt1_img = render_text_image(option1_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))
            opt2_img = render_text_image(option2_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))

            try:
                base1_path = os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')
                base2_path = os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png')
                base1 = Image.open(base1_path).convert('RGBA')
                base2 = Image.open(base2_path).convert('RGBA')
            except Exception:
                try:
                    combined = Image.new('RGBA', (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT), (0, 0, 0, 0))
                    combined.paste(q_img, (0, self.QUESTION_BOX_TOP_Y), q_img)
                    combined.paste(opt1_img, (0, self.QUESTION_BOX_OPTION1_Y), opt1_img)
                    combined.paste(opt2_img, (0, self.QUESTION_BOX_OPTION2_Y), opt2_img)
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
                if self.current_facing == "Left":
                    x = 97
                else:
                    x = 9
                b.paste(q_img, (x, self.QUESTION_BOX_TOP_Y), q_img)
                b.paste(opt1_img, (x, self.QUESTION_BOX_OPTION1_Y), opt1_img)
                b.paste(opt2_img, (x, self.QUESTION_BOX_OPTION2_Y), opt2_img)
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
            base1_path = os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')
            base2_path = os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png')
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
            if self.current_facing == "Left":
                x = 97
            else:
                x = 9
            y = self.QUESTION_BOX_TOP_Y
            if IsQuestion == 1:
                y = self.QUESTION_BOX_OPTION1_Y
            elif IsQuestion == 2:
                y = self.QUESTION_BOX_OPTION2_Y
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
        self.add_talking_sentences(random.choice(self.removal_lines).strip(),'removal',False)

    def close_command(self):
        self.end = True
        if self.current_state != 'removal' and self.current_state != 'cutscene':
            self.add_removal_sentences()
            self.new_state('removal')
        if not getattr(self, '_death_scheduled', False):
            self._death_scheduled = True
            self.window.after(self.REMOVAL_ANIMATION_DELAY, self.death_animation)

    def death_animation(self):
        screen_x,screen_y = self.window.winfo_x(), self.window.winfo_y()
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
                self.particles_manager = []
                self.firstime = True
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.animate)
                self.load_tiles(src_path)
                src_path.size = (357, 342)
                self.resize(self.img_w, self.img_h)
                self.setGeometry(screen_x-50,screen_y-600, self.img_w, self.img_h)
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
                if self.firstime:
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

    def rotate_right(self):
        new_image_path = "assets/mirror_sharko/"
        new_talking_path = "assets/mirror_sentences/talking/"
        new_greeting_path = "assets/mirror_sentences/greeting/"
        new_removal_path = "assets/mirror_sentences/removal/"
        self.load_images(new_image_path,new_talking_path,new_greeting_path,new_removal_path)
        self.current_facing = "Left"
        self.x = 0
        self.position_flip_trigger = True
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
        self.current_facing = "Right"
        self.x = self.screen_x-359
        self.position_flip_trigger = True
        try:
            self.new_state('Limbo')
        except Exception:
            pass


    def toggle_fight_mode(self):
        if self.current_state != 'fight':
            self.fight_mode_active = True
            self.supress_right_clk = True
            if not self.active_bar:
                #self.active_bar = ScalableHealthBar()
                screen_w = windll.user32.GetSystemMetrics(0)
                #self.active_bar.resize(screen_w // 2, 200)
                #self.active_bar.slide_in()
                print("Boss Bar Created from external file.")
                self.particles_manager = VFXManager()
                #self.warning_manager = MultiWarningOverlay()
            self.new_state('fight')
            self.fight_loop()
        else:
            self.fight_mode_active = False
            self.supress_right_clk = False
            self.particles_manager.deinitialize()
            del self.particles_manager
            #self.warning_manager.deinitialize()
            #del self.warning_manager
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
        
        #self.particles_manager.start_spirit_beam("main_beam", 0, 0, 0, 0)

        #mx, my = win32api.GetCursorPos()
        #self.particles_manager.update_spirit_beam("main_beam", mx, my, mx, my)
        
        folder_view, hwnd_lv = DesktopUtils.get_desktop_interfaces(
            self.CLSID_ShellWindows,
            self.IID_IFolderView,
            self.SWC_DESKTOP,
            self.SWFO_NEEDDISPATCH
        )
        closest, num_icons = self.get_closest_icons(1)
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        desktop_working_area = wintypes.RECT()
        windll.user32.SystemParametersInfoW(self.SPI_GETWORKAREA, 0, byref(desktop_working_area), 0)
        work_area_height = desktop_working_area.bottom - desktop_working_area.top
        x,y = 0,0
        if num_icons <= 3:
            replacement_shortcut = DesktopUtils.create_shortcut(hwnd_lv)
            closest = []
            closest.append(replacement_shortcut)
            x = random.randint(350,screen_w-350)
            y = random.randint(350,work_area_height-350)

            pos = win32api.MAKELONG(int(x), int(y))
            win32gui.SendMessage(hwnd_lv, self.LVM_SETITEMPOSITION, replacement_shortcut, pos)
        item = folder_view.Item(closest[0])
        item_pos = folder_view.GetItemPosition(item)
        
        def schedule_next_attack():
            """Schedule the next attack 2 seconds after this one finishes"""
            self._fight_loop_after_id = self.window.after(2000, self.fight_loop)
        self.log_stats()
        #CombatSystem.Jump(self,[random.randint(350, screen_w - 350), work_area_height - 343], 1)
        CombatSystem.JumpAndHit(self,item_pos,closest[0],0.4,on_complete=schedule_next_attack)
        #CombatSystem.Lazer(self,10000,on_complete=schedule_next_attack)
        


    def sounds(self, sound_object):
        pygame.mixer.init()
        if self.sound_enabled:
            sound_object.play()        

    
    def sounds_logics(self):
        """Toggle sound on/off"""
        self.sound_enabled = not self.sound_enabled


# Initialize and run
if __name__ == "__main__":
    sharko = Sharko("assets/sharko/",
                    "assets/sentences/talking/",
                    "assets/sentences/greeting/",
                    "assets/sentences/removal/")