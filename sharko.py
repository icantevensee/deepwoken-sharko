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
from        ctypes import windll, wintypes, byref
import      win32gui
import      win32api

import      random
import      math
import      time

import      pygame

import      os
import      sys

from        pynput import keyboard, mouse

from        PIL import Image
from        PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMenu
from        PyQt5.QtGui import QPixmap, QPainter, QImage, QCursor, QColor
from        PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QObject, pyqtSignal

import      threading

from        boss_bar import ScalableHealthBar
from        vfx_manager import VFXManager, MultiWarningOverlay
from        boss_battle import CombatSystem

from        constants import SharkoConstants
from        icons import IconManager
from        shortcut_utils import DesktopUtils
from        tile import Tile

from        widgets import SharkoLabel, MenuStyle
from        img_utils import ImgUtils



import      psutil


throw_lock = threading.Lock()


# Enable high DPI scaling for PyQt5 on Windows
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
try:
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


class InputSignalEmitter(QObject):
    """Thread-safe signal emitter for input events from pynput listeners."""
    f_pressed = pyqtSignal()
    f_released = pyqtSignal()
    action_triggered = pyqtSignal(int, int, object)  # x, y, button
    

class Sharko(SharkoConstants, IconManager):
    """Main functionality with animation, combat, and effects."""

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
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()

        self.app.setStyle(MenuStyle())
        print("Eee")
        self.window = QWidget()
        self.window.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.window.setAttribute(Qt.WA_TranslucentBackground)
        #self.window.setStyleSheet(self.mainstylesheet)

        #SCREEN & DISPLAY CONFIGURATION This won't work if you have multiple monitors with different resolutions.
        #It should be fine for now since the character will just spawn on the primary monitor and not be able to move to the others.
        screen = self.app.primaryScreen()
        self.screen_x = screen.geometry().width()
        self.screen_y = screen.geometry().height()
        
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
        self.window.setGeometry(x, y, 357, 342)
        
        #CHARACTER & STATE
        self.current_facing = "Right"
        self.current_state = 'greeting'
        self.frame = 0
        
        #GAME STATE FLAGS
        self.talking_disabled       = False
        self.cutscene_active        = False
        self.fight_mode_active      = False
        self.movie_mode_active      = False
        self.end                    = False
        self.currently_moving       = False
        self.position_flip_trigger  = False
        
        #AUDIO SYSTEM
        self.sound_enabled = True
        self.sound_file = self.GREETING_SOUND
        self.sound_lock = threading.Lock()  # Thread-safe sound playback
        pygame.init()
        pygame.mixer.init()  # Initialize once at startup
        pygame.mixer.set_num_channels(16)
        self.sound_paths    = {'end': self.END_TALKING_SOUND, 'start': self.START_TALKING_SOUND, 'greeting': self.GREETING_SOUND, 'clash': self.CLASH_SOUND, 'answer': self.ANSWER_SOUND, 'block_attempt': self.BLOCK_ATTEMPT_SOUND, 'parry': self.PARRY_SOUND, 'block': self.BLOCK_SOUND, 'hit': self.HIT_SOUND}
        self.sounds_group   = {name: pygame.mixer.Sound(path) for name, path in self.sound_paths.items()}
        
        #MOVEMENT SYSTEM
        self.walking_enabled = True
        
        #INPUT & INTERACTION
        self.supress_right_clk = False
        self.last_input_time = time.time()
        
        #PARRY AND BLOCK MECHANICS
        self.attack_press_time          = 0
        self.attack_active_until        = 0
        self.last_attack_time           = 0
        self.parry_press_time           = 0
        self.parry_active_until         = 0
        self.last_parry_block_time      = 0
        self.block_active_until         = 0
        self.block_transition_callback  = None
        self.f_key_held                 = False
        self.blocking                   = False
        
        #ASSET LOADING
        self._load_images(image_path, talking_path, greeting_path, removal_path)
        
        #GUI SETUP
        self._create_gui()
        
        #ANIMATION & CALLBACKS
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(self.ANIMATION_DELAY)
        
        self.idle_timer = None
        self.fight_loop_timer = None
        self.lazer_timer = None
        
        #STARTUP SEQUENCE
        self.animate()
        self.sounds(pygame.mixer.Sound(self.sound_file))
        self.add_talking_sentences(self.intro_line.strip(),'greeting',False)
        
        self.window.show()
        
        QTimer.singleShot(self.GREETING_ANIMATION_DELAY, self.idle_state)
        
        #COMBAT SYSTEM
        self.CombatSystem = CombatSystem()
        self.active_bar = None
        
        #SYSTEM MONITORING
        self.process = psutil.Process(os.getpid())
        
        #INPUT SIGNAL EMITTER (for thread-safe communication from pynput listeners)
        self.input_emitter = InputSignalEmitter()
        self.input_emitter.f_pressed.connect(self._on_f_pressed_safe, Qt.QueuedConnection)
        self.input_emitter.f_released.connect(self._on_f_released_safe, Qt.QueuedConnection)
        self.input_emitter.action_triggered.connect(self._on_action_safe, Qt.QueuedConnection)
        
        #INPUT LISTENERS
        def on_f_press(key):
            try:
                if key.char == 'f':
                    self.input_emitter.f_pressed.emit()
            except AttributeError:
                pass
        
        def on_f_release(key):
            try:
                if key.char == 'f':
                    self.input_emitter.f_released.emit()
            except AttributeError:
                pass
        
        def on_mouse_move(x, y):
            # Mouse move events don't trigger actions currently
            pass
        
        def on_mouse_click(x, y, button, pressed):
            self.input_emitter.action_triggered.emit(x, y, button)
        
        keyboard_listener   = keyboard.Listener(on_press=on_f_press, on_release=on_f_release)
        mouse_listener      = mouse.Listener(on_move=on_mouse_move, on_click=on_mouse_click)

        keyboard_listener.start()
        mouse_listener.start()

        sys.exit(self.app.exec_())

    def log_stats(self):
        """Log current memory usage statistics."""
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        print(f"RAM: {mem_mb:.2f} MB")

    def _load_cutscenes(self):
        """Load and initialize cutscene animation presets with frames and timing."""
        self.cutscene_presets = {
            'InactiveCutscene': [
                {"image": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')), "duration": 1000, "sound": "None"},
                {"image": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'sideframe.png')), "duration": 150, "sound": "None"},
                {"image": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'staringframe.png')), "duration": 1000, "sound": "None"},
                {"type": "talk", "image1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking_forward1.png')), "image2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking_forward2.png')), "sound": 'start', "interval": 500, "repeat_count": 11, "text": "hello?"},
                {"type": "talk", "image1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking_forward1.png')), "image2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking_forward2.png')), "sound": 'clash', "interval": 500, "repeat_count": 10, "text": "HELLO!"},
                {"image": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'staringframe.png')), "duration": 1000, "sound": "None"},
                {"image": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'sideframe.png')), "duration": 150, "sound": "None"}
            ],
        }

    def _load_images(self, image_path, talking_path, greeting_path, removal_path):
        """Load all animation images from specified paths into state dictionaries."""
        self.CURRENT_IMAGES_PATH        = image_path
        self.TALKING_SENTENCES_PATH     = talking_path
        self.GREETING_SENTENCES_PATH    = greeting_path
        self.REMOVAL_SENTENCES_PATH     = removal_path
        self._load_cutscenes()

        self.states = {
            'idle': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
                     Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png'))],
            'Limbo': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
                     Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png'))],
            'walking': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'walk1.png')),
                        Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'walk2.png'))],

            'talking': [],

            'fight': [],

            'greeting': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')),
                        Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png'))],

            'MovieG': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'glasses1.png')),
                         Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'glasses2.png'))],
            
            'MovieNG': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
                     Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png'))],

            'cutscene': [],

            'removal': [Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')),
                        Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png'))],
        }

    def _toggle_menu_items(self, whitelist):
        """Toggle enabled/disabled state of menu items."""
        try:
            for action in self.menu.actions():
                if action.text() not in whitelist:
                    action.setEnabled(not action.isEnabled())
        except Exception:
            pass

    def animate(self):
        """Update and render current animation frame based on character state."""
        if self.label.pixmap() is None or self.label.pixmap().isNull():
            return
        if self.position_flip_trigger:
            self.position_flip_trigger = False
            if self.current_facing == "Left":
                self.window.setGeometry(0, self.window.y(), 357, 342)
            else: 
                self.window.setGeometry(self.screen_x - 357, self.window.y(), 357, 342)

        if self.cutscene_active or self.fight_mode_active:
            return
        state_images = self.states.get(self.current_state, [])
        if not state_images:
            state_images = self.states.get('idle', [])
            if not state_images:
                return
            self.current_state = 'idle'

        self.frame = (self.frame + 1) % len(state_images)
        pixmap = ImgUtils._pil_to_qpixmap(state_images[self.frame])
        self.label.setPixmap(pixmap)

    def move_window_x(self, target_x):
        """Animate character window movement to target X position.
        
        Args:
            target_x: Target X coordinate
        """
        original_animation_delay = self.ANIMATION_DELAY
        self.ANIMATION_DELAY = int(self.ANIMATION_DELAY / 2)
        start_x = self.window.x()

        total_dx = target_x - start_x
        duration_ms = int(math.ceil(abs(total_dx) / self.WALKSPEED) * 1000)
        FRAME_DELAY_MS = self.FRAME_DELAY_MS
        num_steps = max(1, duration_ms // FRAME_DELAY_MS)
        step_dx = total_dx / num_steps

        def step_move(current_step, current_x):
            if self.fight_mode_active:
                return

            if self.end or self.currently_moving:
                self.ANIMATION_DELAY = original_animation_delay
                QTimer.singleShot(FRAME_DELAY_MS, self.idle_state)
                return

            if current_step >= num_steps:
                self.ANIMATION_DELAY = original_animation_delay
                self.window.setGeometry(target_x, self.window.y(), 357, 342)
                if self.current_facing == "Right":
                    QTimer.singleShot(FRAME_DELAY_MS, self.rotate_right)
                    QTimer.singleShot(FRAME_DELAY_MS + 1, self.idle_state)
                else:
                    QTimer.singleShot(FRAME_DELAY_MS, self.rotate_left)
                    QTimer.singleShot(FRAME_DELAY_MS + 1, self.idle_state)
                return

            new_x = int(current_x + step_dx)
            self.x = new_x
            self.window.setGeometry(new_x, self.window.y(), 357, 342)
            QTimer.singleShot(FRAME_DELAY_MS, lambda: step_move(current_step + 1, current_x + step_dx))
        
        QTimer.singleShot(FRAME_DELAY_MS, lambda: step_move(0, start_x))

    def _create_gui(self):
        """Create and configure the GUI elements (label, menus, window properties)."""
        layout = QVBoxLayout(self.window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.label = SharkoLabel(self.window)
        self.label.parent_sharko = self
        self.label.setPixmap(ImgUtils._pil_to_qpixmap(self.states['idle'][0]))
        layout.addWidget(self.label)
        
        # Create context menu
        self.menu = QMenu(self.window)
        self.Movie_menu = QMenu("Movie mode", self.window)
        self.Movie_menu.addAction('Off', self.movie_off)
        self.Movie_menu.addAction('On(Glasses)', self.movie_on_g)
        self.Movie_menu.addAction('On(No glasses)', self.movie_on_ng)
        self.menu.addMenu(self.Movie_menu)
        self.menu.addAction('Fight', self.toggle_fight_mode)
        self.menu.addAction('Sounds off', self.sounds_logics).setCheckable(True)
        self.menu.addAction('Walking off', self.toggle_walking).setCheckable(True)
        self.menu.addAction('Flip side', self.flip_side)
        self.menu.addAction('Close', self.close_command)
        
        self.window.setWindowTitle("Sharko")
        self.window.setFixedSize(357, 342)

    def play_cutscene(self, cutscene_preset):
        if self.cutscene_active:
            return
        self.cutscene_active = True
        self.new_state('cutscene')
        cutscene = self.cutscene_presets[cutscene_preset]
        for frame in cutscene:
            if frame.get("type") == "repeat":
                frame["is_first_frame"] = True
            elif frame.get("type") == "talk":
                frame["is_first_frame"] = True
                text_img = ImgUtils._render_text_image(self,frame["text"], (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT))
                frame["image1"] = self.composite_on_base(frame["image1"], text_img, None)
                frame["image2"] = self.composite_on_base(frame["image2"], text_img, None)
        
        self._play_cutscene_frame(cutscene, 0, cutscene_preset)

    def _play_cutscene_frame(self, cutscene, current_frame, cutscene_preset):
        if cutscene_preset == 'InactiveCutscene':
            if time.time() - self.last_input_time < self.INACTIVE_TIME_REQUIREMENT:
                if current_frame < 6:
                    current_frame = 6 
                elif current_frame == len(cutscene):
                    self.cutscene_active = False
                    self.talking_disabled = False
                    self._load_cutscenes()
                    self.idle_state()
                    self.animate()
                    return
            elif current_frame == len(cutscene):
                self.cutscene_active = False
                self.talking_disabled = True
                self._load_cutscenes()
                self.idle_state()
                self.animate()
                return

        if current_frame == len(cutscene):
            self.cutscene_active = False
            self._load_cutscenes()
            self.idle_state()
            self.animate()
            return
        
        current_frame_data = cutscene[current_frame]
        
        # Handle repeating cutscene frames
        Sound_Cleared = False
        if current_frame_data.get("type") == "repeat" or current_frame_data.get("type") == "talk":
            image       = current_frame_data["image1"]
            duration    = current_frame_data["interval"]
            sound       = current_frame_data["sound"]
            
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
            image       = current_frame_data["image"]
            duration    = current_frame_data["duration"]
            sound       = current_frame_data["sound"]
            Sound_Cleared = True
            current_frame += 1
        
        # Play sound if not "None"
        if sound != "None" and Sound_Cleared:
            try:
                sound_file = self.sounds_group[sound]
                self.sounds(sound_file)
            except KeyError:
                pass
        
        pixmap = ImgUtils._pil_to_qpixmap(image)
        self.label.setPixmap(pixmap)
        
        QTimer.singleShot(duration, lambda: self._play_cutscene_frame(cutscene, current_frame, cutscene_preset))

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

    def _middle_button_pressed(self, event):
        if self.fight_mode_active or self.cutscene_active:
            return
        self.y = event.pos().y()
        self.x = event.pos().x()
        self.currently_moving = True

    def _middle_button_released(self, event):
        self.y = event.pos().y()
        self.currently_moving = False

    def _middle_button_hold_move(self, event):
        if self.fight_mode_active or self.cutscene_active:
            return
        cursor_pos = QCursor.pos()
        x = cursor_pos.x() - self.x
        y = cursor_pos.y() - self.y
        self.window.setGeometry(x, y, 357, 342)

    def _handle_question_click(self, event):
        if not getattr(self, 'question_active', False):
            return
        x_off = 97 if self.current_facing == "Left" else 9
        x = event.pos().x()
        y = event.pos().y()
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
        if hasattr(self, 'idle_timer') and self.idle_timer:
            self.idle_timer.stop()
        self.add_talking_sentences(answer_text, 'talking', False)
        self.new_state('talking')
        self.idle_timer = QTimer()
        self.idle_timer.singleShot(self.TALKING_ANIMATION_DELAY, self.idle_state)

    def new_state(self, new_state):
        self.current_state = new_state

    def movie_off(self):
        self.log_stats()
        self.movie_mode_active = False
        self.idle_state()

    def movie_on_g(self):
        self.movie_mode_active = True
        self.new_state('MovieG')
    
    def movie_on_ng(self):
        self.movie_mode_active = True
        self.new_state('MovieNG')

    def toggle_walking(self):
        self.walking_enabled = not self.walking_enabled
        if not self.walking_enabled and self.current_state == 'walking':
            self.currently_moving = True
            QTimer.singleShot(50, self._stop_walk_cleanup)

    def _stop_walk_cleanup(self):
        self.currently_moving = False
        if self.current_state == 'walking':
            self.new_state('idle')

    def flip_side(self):
        try:
            if self.current_facing == 'Right':
                self.rotate_right()
                if self.current_state == 'fight': return
                self.window.setGeometry(0, self.window.y(), 357, 342)
                self.x = 0
            else:
                self.rotate_left()
                if self.current_state == 'fight': return
                right_x = max(0, self.screen_x - 357)
                self.window.setGeometry(right_x, self.window.y(), 357, 342)
                self.x = right_x
            self.window.raise_()
            self.position_flip_trigger = True
        except (AttributeError, RuntimeError):
            pass

    def _on_f_pressed_safe(self):
        self.last_input_time = time.time()
        self.talking_disabled = False
        # Only initialize on first press, not on key repeat
        current_time = time.time()
        if self.parry_press_time == 0 and current_time - self.last_parry_block_time >= self.PARRY_BLOCK_COOLDOWN:
            self.last_parry_block_time = current_time
            # Cancel any pending callback from previous key press
            if self.block_transition_callback:
                try:
                    self.block_transition_callback.stop()
                except (RuntimeError, Exception):
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
            
            self.block_transition_callback = QTimer()
            self.block_transition_callback.setSingleShot(True)
            self.block_transition_callback.timeout.connect(transition_to_block)
            self.block_transition_callback.start(int(self.PARRY_WINDOW * 1000))

    def _on_f_released_safe(self):
        # Handle parry key release (f)
        self.f_key_held = False
        # Cancel pending block transition if released early
        if self.block_transition_callback:
            try:
                self.block_transition_callback.stop()
            except (RuntimeError, Exception):
                pass
            self.block_transition_callback = None
        
        # If we were blocking, stop it on release
        self.blocking = False
        self.parry_press_time = 0

    def _on_action_safe(self, x, y, button):
        if self.fight_mode_active and button == mouse.Button.left:
                current_time = time.time()
                if current_time - self.last_attack_time >= self.ATTACK_COOLDOWN:
                    self.last_attack_time = current_time
                    self.attack_press_time = time.time()
                    self.attack_active_until = self.attack_press_time + self.PARRY_WINDOW
                    CombatSystem.mouse_attack(self,x,y)
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
        if hasattr(self, 'idle_timer') and self.idle_timer:
            self.idle_timer.stop()
        self.idle_timer = QTimer()
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self.idle_state)
        self.idle_timer.start(self.TALKING_ANIMATION_DELAY)
    
    def _should_transition_to_idle(self) -> bool:
        """Check if current state should transition to idle state."""
        is_talking_like = self.current_state in ['talking', 'greeting']
        is_cutscene     = self.current_state == 'cutscene' and not self.cutscene_active
        is_walking      = self.current_state == 'walking'
        is_movie        = (self.current_state == 'MovieG' and not self.movie_mode_active) or \
                          (self.current_state == 'MovieNG' and not self.movie_mode_active)
        is_limbo        = self.current_state == 'Limbo'
        is_fight        = self.current_state == 'fight' and not self.fight_mode_active
        return is_talking_like or is_cutscene or is_walking or is_movie or is_limbo or is_fight
    
    def idle_state(self):
        self.log_stats()
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
                    QTimer.singleShot(self.IDLE_ANIMATION_DELAY, self.talking_state)
                else:
                    if not self.walking_enabled and self.talking_disabled:
                        self.current_state = 'Limbo'
                        QTimer.singleShot(self.IDLE_ANIMATION_DELAY, self.idle_state)
                    else:
                        QTimer.singleShot(self.IDLE_ANIMATION_DELAY, self.walking_state)

    def walking_state(self):
        if self.current_state == 'idle':
            self.new_state('walking')

            state_images = self.states.get(self.current_state, [])
            if not state_images:
                return
            self.frame = (self.frame + 1) % len(state_images)
            pixmap = ImgUtils._pil_to_qpixmap(state_images[self.frame])
            self.label.setPixmap(pixmap)
            if self.current_facing == "Right":
                self.move_window_x(-179)
            else:
                self.move_window_x(self.screen_x - 179)

    def add_new_question(self,Question_Lines):
        self.add_talking_sentences(Question_Lines,'talking',3)

    def add_talking_sentences(self,sentence,state,IsQuestion):
        if not hasattr(self, 'Lines') or not self.Lines:
            return
        box_w, box_h = self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT

        if IsQuestion == 3:
            try:
                question_text   = sentence[0]
                option1_text    = sentence[1]
                option2_text    = sentence[2]
                answer1_text    = sentence[3]
                answer2_text    = sentence[4]
            except Exception:
                return

            q_img       = ImgUtils._render_text_image(self, question_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_TEXT_HEIGHT))
            opt1_img    = ImgUtils._render_text_image(self, option1_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))
            opt2_img    = ImgUtils._render_text_image(self, option2_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))

            try:
                base1_path  = os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')
                base2_path  = os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png')
                base1 = Image.open(base1_path).convert('RGBA')
                base2 = Image.open(base2_path).convert('RGBA')
                if self.current_facing == "Left":
                    base1 = base1.transpose(Image.FLIP_LEFT_RIGHT)
                    base2 = base2.transpose(Image.FLIP_LEFT_RIGHT)

            except Exception:
                try:
                    combined = Image.new('RGBA', (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT), (0, 0, 0, 0))
                    combined.paste(q_img, (0, self.QUESTION_BOX_TOP_Y), q_img)
                    combined.paste(opt1_img, (0, self.QUESTION_BOX_OPTION1_Y), opt1_img)
                    combined.paste(opt2_img, (0, self.QUESTION_BOX_OPTION2_Y), opt2_img)
                    self.states[state] = [combined, combined]
                    self._question_answers = (answer1_text, answer2_text)
                    self.question_active = True
                except Exception:
                    return
                return

            def _composite_three(base_img):
                b = base_img.copy()
                if self.current_facing == "Left":
                    x = 97
                else:
                    x = 9
                b.paste(q_img, (x, self.QUESTION_BOX_TOP_Y), q_img)
                b.paste(opt1_img, (x, self.QUESTION_BOX_OPTION1_Y), opt1_img)
                b.paste(opt2_img, (x, self.QUESTION_BOX_OPTION2_Y), opt2_img)
                return b

            comp1 = _composite_three(base1)
            comp2 = _composite_three(base2)

            self.states[state] = [comp1, comp2]
            self._question_answers = (answer1_text, answer2_text)
            self.question_active = True
            return

        text_img = ImgUtils._render_text_image(self, sentence, (box_w, box_h))
        try:
            base1_path = os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')
            base2_path = os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png')
            base1 = Image.open(base1_path).convert('RGBA')
            base2 = Image.open(base2_path).convert('RGBA')
            if self.current_facing == "Left":
                base1 = base1.transpose(Image.FLIP_LEFT_RIGHT)
                base2 = base2.transpose(Image.FLIP_LEFT_RIGHT)
        except Exception:
            try:
                self.states[state] = [text_img, text_img]
            except Exception:
                return
            return

        comp1 = self.composite_on_base(base1, text_img, IsQuestion)
        comp2 = self.composite_on_base(base2, text_img, IsQuestion)

        self.states[state] = [comp1, comp2]

    def composite_on_base(self,base_img,text_img,IsQuestion):
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
    


    def add_removal_sentences(self):
        self.add_talking_sentences(random.choice(self.removal_lines).strip(),'removal',False)

    def close_command(self):
        self.end = True
        if self.current_state != 'removal' and self.current_state != 'cutscene':
            self.add_removal_sentences()
            self.new_state('removal')
        if not getattr(self, '_death_scheduled', False):
            self._death_scheduled = True
            QTimer.singleShot(self.REMOVAL_ANIMATION_DELAY, self.death_animation)

    def death_animation(self):
        screen_x,screen_y = self.window.x(), self.window.y()
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
                    window.hide()
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
        img_path = state_images[self.frame]
        
        # Convert PIL Image to QImage properly
        img = img_path.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        w, h = img.size
        qimg = QImage(data, w, h, 4*w, QImage.Format_RGBA8888)
        # Keep a reference to prevent garbage collection
        qimg._buf = data
        self.deathwidget = DeathAnimationWidget(qimg)
        
        #sys.exit(self.app.exec_())


    def rotate_right(self):
        for state in self.states.values():
            for key, state_image in enumerate(state):
                state[key] = ImgUtils._flip_photoimage(state_image)

        for preset in self.cutscene_presets.values():
            for frame in preset:
                for frame_image in frame.items():
                    if isinstance(frame_image[1], Image.Image):
                        frame[frame_image[0]] = ImgUtils._flip_photoimage(frame_image[1])

        if self.current_state != "fight":
            self.current_facing = "Left"
            self.x = 0
            self.position_flip_trigger = True
            try:
                self.new_state('Limbo')
            except Exception:
                pass
        

    def rotate_left(self):
        for state in self.states.values():
            for key, state_image in enumerate(state):
                state[key] = ImgUtils._flip_photoimage(state_image)

        for preset in self.cutscene_presets.values():
            for frame in preset:
                for frame_image in frame.items():
                    if isinstance(frame_image[1], Image.Image):
                        frame[frame_image[0]] = ImgUtils._flip_photoimage(frame_image[1])

        if self.current_state != "fight":
            self.current_facing = "Right"
            self.x = self.screen_x-int(self.WINDOW_SIZE.split('x')[0])
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
                self.active_bar = ScalableHealthBar()
                screen_w = windll.user32.GetSystemMetrics(0)
                self.active_bar.resize(screen_w // 2, 200)
                self.active_bar.slide_in()
                print("Boss Bar Created from external file.")
                self.particles_manager = VFXManager()
                self.warning_manager = MultiWarningOverlay()
            self.new_state('fight')
            self.fight_loop()
            self._toggle_menu_items(['Sounds (Off/On)', 'Fight'])
        else:
            self._toggle_menu_items(['Sounds (Off/On)', 'Fight'])
            self.fight_mode_active = False
            self.supress_right_clk = False
            # Stop all active timers
            if hasattr(self, 'fight_loop_timer') and self.fight_loop_timer:
                try:
                    self.fight_loop_timer.stop()
                except RuntimeError:
                    pass
                self.fight_loop_timer = None
            if hasattr(self, 'lazer_timer') and self.lazer_timer:
                try:
                    self.lazer_timer.stop()
                except RuntimeError:
                    pass
                self.lazer_timer = None
            # Clean up VFX managers
            self.particles_manager.deinitialize()
            del self.particles_manager
            self.warning_manager.deinitialize()
            del self.warning_manager
            if self.active_bar:
                self.active_bar.slide_out_to_hide()
                self.active_bar = None
            self.idle_state()
            self.animate()

    def fight_loop(self):
        if self.current_state != 'fight':
            return
        
        folder_view, hwnd_lv = DesktopUtils.get_desktop_interfaces(
            self.CLSID_ShellWindows,
            self.IID_IFolderView,
            self.SWC_DESKTOP,
            self.SWFO_NEEDDISPATCH
        )
        closest, num_icons = self.get_closest_icons(1)
        screen_w = win32api.GetSystemMetrics(0)
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
        old_facing = self.current_facing
        def inter_attack_idle():
            if self.current_facing != old_facing:
                self.flip_side()
            pixmap = ImgUtils._pil_to_qpixmap(self.states['idle'][0])
            self.label.setPixmap(pixmap)
            time = 3000
            num_idle_frames = time // self.ANIMATION_DELAY
            current_idle_frame = 0
            def play_idle_frame(current_idle_frame):
                if current_idle_frame == num_idle_frames:
                    if self.fight_loop_timer:
                        self.fight_loop_timer.stop()
                    self.fight_loop_timer = QTimer()
                    self.fight_loop_timer.setSingleShot(True)
                    self.fight_loop_timer.timeout.connect(self.fight_loop)
                    self.fight_loop_timer.start(self.ANIMATION_DELAY)
                    return
                current_idle_frame = current_idle_frame + 1
                if current_idle_frame % 2 == 0:
                    pixmap = ImgUtils._pil_to_qpixmap(self.states['idle'][0])
                    self.label.setPixmap(pixmap)
                else:
                    pixmap = ImgUtils._pil_to_qpixmap(self.states['idle'][1])
                    self.label.setPixmap(pixmap)

                if self.fight_loop_timer:
                    self.fight_loop_timer.stop()
                self.fight_loop_timer = QTimer()
                self.fight_loop_timer.setSingleShot(True)
                self.fight_loop_timer.timeout.connect(lambda: play_idle_frame(current_idle_frame))
                self.fight_loop_timer.start(self.ANIMATION_DELAY)
            play_idle_frame(current_idle_frame)
        self.log_stats()
        #CombatSystem.jump(self,[random.randint(350, screen_w - 350), work_area_height - 343], 0.4,on_complete=inter_attack_idle)
        #CombatSystem.jump_and_hit(self,item_pos,closest[0],0.4,on_complete=inter_attack_idle)
        CombatSystem.lazer(self,1000,on_complete=inter_attack_idle)
        
    def sounds(self, sound_object):
        if self.sound_enabled:
            with self.sound_lock:
                try:
                    sound_object.play()
                except Exception as e:
                    print(f"Error playing sound: {e}")        

    
    def sounds_logics(self):
        """Toggle sound on/off"""
        self.sound_enabled = not self.sound_enabled


# Initialize and run
if __name__ == "__main__":
    sharko = Sharko("assets/sharko/",
                    "assets/sentences/talking/",
                    "assets/sentences/greeting/",
                    "assets/sentences/removal/")