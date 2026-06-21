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
from        ctypes import windll, byref, Structure, c_uint, sizeof, c_void_p

import      random
import      math
import      time
import      numpy as np

import      pygame

import      os
import      sys

import      threading

from pynput             import keyboard, mouse

from PIL                import Image
from PyQt5.QtWidgets    import QApplication, QWidget, QVBoxLayout, QMenu,QWidgetAction
from PyQt5.QtGui        import QPixmap, QPainter, QImage, QCursor
from PyQt5.QtCore       import Qt, QTimer, QObject, pyqtSignal


from bar_guis           import ScalableHealthBar
from vfx_manager        import VFXManager, MultiWarningOverlay, ScreenShaker
from boss_battle        import CombatSystem
from boss_ai            import SharkoCombatAI

from constants          import SharkoConstants
from icons              import IconManager
from windows_utils      import WindowsUtils
from tile               import Tile

from widgets            import SharkoLabel, MenuStyle, VolumeSlider
from img_utils          import ImgUtils

import      psutil


# Enable high DPI scaling for PyQt5 on Windows
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
try:
    windll.user32.SetProcessDpiAwarenessContext(c_void_p(-4))
    print("Modern Per-Monitor V2 Awareness Active.")
except Exception:
    try:
        windll.shcore.SetProcessDpiAwareness(1)
        print("Legacy System DPI Awareness Active.")
    except Exception:
        pass

class LASTINPUTINFO(Structure):
    _fields_ = [
        ('cbSize', c_uint),
        ('dwTime', c_uint),
    ]

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
        self.window = QWidget()
        self.window.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.window.setAttribute(Qt.WA_TranslucentBackground)

        #SCREEN & DISPLAY CONFIGURATION This won't work if you have multiple monitors with different resolutions.
        #It should be fine for now since the character will just spawn on the primary monitor and not be able to move to the others.
        screen = self.app.primaryScreen()
        self.screen_x = screen.geometry().width()
        self.screen_y = screen.geometry().height()
        
        work_area_height = WindowsUtils.get_work_area_height()
        thickness_vertical = self.screen_y - work_area_height  
        if thickness_vertical > 0:
            taskbar_thickness = thickness_vertical
        else:
            taskbar_thickness = 0

        x = self.screen_x - self.WINDOW_SIZE_X
        y = self.screen_y - self.WINDOW_SIZE_Y - taskbar_thickness
        self.x = x
        self.y = y
        self.window.setGeometry(x, y, self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
        
        #CHARACTER & STATE
        self.current_facing = "Right"
        self.current_state = 'greeting'
        self.frame = 0
        
        #GAME STATE FLAGS
        self.talking_disabled       = False
        self.cutscene_active        = False
        self.fight_mode_active      = False
        self.movie_mode_active      = False
        self.currently_moving       = False
        
        #AUDIO SYSTEM
        self.sound_volume = 1
        self.sound_lock = threading.Lock()  # Thread-safe sound playback
        pygame.mixer.init()  # Initialize once at startup
        pygame.mixer.set_num_channels(16)
        self.sound_paths    = {'end': [self.END_TALKING_SOUND,False], 'start': [self.START_TALKING_SOUND,False], 'greeting': [self.GREETING_SOUND,False], 'clash': [self.CLASH_SOUND,False], 'answer': [self.ANSWER_SOUND,False], 'block_attempt': [self.BLOCK_ATTEMPT_SOUND,True], 'parry': [self.PARRY_SOUND,True], 'block': [self.BLOCK_SOUND,True], 'hit': [self.HIT_SOUND,True]}
        self.sounds_group   = {name: [pygame.mixer.Sound(obj[0]),obj[1]] for name, obj in self.sound_paths.items()}
        
        #MOVEMENT SYSTEM
        self.walking_enabled = True
        
        #INPUT & INTERACTION
        self.suppress_right_click = False
        
        #PARRY AND BLOCK MECHANICS
        self.attack_press_time          = 0
        self.attack_active_until        = 0
        self.last_attack_time           = 0
        self.parry_press_time           = 0
        self.parry_active_until         = 0
        self.last_parry_block_time      = 0
        self.block_active_until         = 0
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
        
        #TIMER MANAGEMENT SYSTEM
        self.active_timers = set()  # Track all non-animation timers
        
        self.idle_timer = None
        self.fight_loop_timer = None
        self.temp_combat_timer = None
        self.block_transition_callback = None
        
        #STARTUP SEQUENCE
        self.sounds(self.sounds_group['greeting'])
        self.add_talking_sentences(self.intro_line.strip(),'greeting',False)
        
        self.window.show()
        
        self._single_shot(self.GREETING_ANIMATION_DELAY, lambda: (
            self.idle_state(),
            [img.close() for img in self.states['greeting']], 
            self.states.update({'greeting': []})
        ))        
        #COMBAT SYSTEM
        self.active_bar = None
        self.combat_ai = None
        
        #SYSTEM MONITORING
        self.process = psutil.Process(os.getpid())
        
        #INPUT SIGNAL EMITTER (for thread-safe communication from pynput listeners)
        self.input_emitter = InputSignalEmitter()
        self.input_emitter.f_pressed.connect(self._on_f_pressed_safe, Qt.QueuedConnection)
        self.input_emitter.f_released.connect(self._on_f_released_safe, Qt.QueuedConnection)
        self.input_emitter.action_triggered.connect(self._on_action_safe, Qt.QueuedConnection)
        
        #INPUT LISTENERS
        def on_f_press(key):
            if getattr(key, "char", None) == 'f':
                self.input_emitter.f_pressed.emit()

        def on_f_release(key):
            if getattr(key, "char", None) == 'f':
                self.input_emitter.f_released.emit()

        
        def on_mouse_click(x, y, button, pressed):
            if button == mouse.Button.right and self.suppress_right_click == True:
                mouse.Listener.suppress_event(self)
            if pressed:
                self.input_emitter.action_triggered.emit(x, y, button)
        
        self.keyboard_listener   = keyboard.Listener(on_press=on_f_press, on_release=on_f_release)
        self.mouse_listener      = mouse.Listener(on_click=on_mouse_click)

        self.keyboard_listener.start()
        self.mouse_listener.start()

        sys.exit(self.app.exec_())

    def log_stats(self):
        """Log current memory usage statistics."""
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        print(f"RAM: {mem_mb:.2f} MB")

    @staticmethod
    def get_inactive_length():
        last_input_info = LASTINPUTINFO()
        last_input_info.cbSize = sizeof(last_input_info)
        
        windll.user32.GetLastInputInfo(byref(last_input_info))
        
        millis = windll.kernel32.GetTickCount64()
        
        return millis - last_input_info.dwTime

    def _add_timer(self, timer):
        """Register a timer for centralized tracking and management."""
        self.active_timers.add(timer)
        return timer

    def _single_shot(self, delay_ms, callback):
        """Create a tracked single-shot timer that cleans up automatically."""
        timer = self._add_timer(QTimer())
        timer.setSingleShot(True)
        
        def cleanup():
            try:
                callback()
            finally:
                self.active_timers.discard(timer) 
                timer.deleteLater()

        timer.timeout.connect(cleanup)
        timer.start(delay_ms)
        return timer

    def _stop_all_timers(self):
        """Stop and disconnect all tracked timers."""
        for timer in list(self.active_timers):
            try:
                try:
                    timer.timeout.disconnect()
                except (RuntimeError, TypeError):
                    pass
                timer.stop()
                timer.deleteLater()
            except (RuntimeError, AttributeError):
                pass
        self.active_timers.clear()

    def _load_cutscenes(self):
        """Load and initialize cutscene animation presets with frames and timing."""


        self.cutscene_presets = {
            'InactiveCutscene': [
                {"image": lambda: self.images["idle1"],        "duration": 1000, "sound": "None"},
                {"image": lambda: self.images["sideframe"],    "duration": 150,  "sound": "None"},
                {"image": lambda: self.images["staringframe"], "duration": 1000, "sound": "None"},
                {"type": "talk", "image1": lambda: self.images["talk_fwd_1"], "image2": lambda: self.images["talk_fwd_2"], "sound": 'start', "interval": 500, "repeat_count": 11, "text": "hello?"},
                {"type": "talk", "image1": lambda: self.images["talk_fwd_1"], "image2": lambda: self.images["talk_fwd_2"], "sound": 'clash', "interval": 500, "repeat_count": 10, "text": "HELLO!"},
                {"image": lambda: self.images["staringframe"], "duration": 1000, "sound": "None"},
                {"image": lambda: self.images["sideframe"],    "duration": 150,  "sound": "None"},
            ],
        }

    def _load_images(self, image_path, talking_path, greeting_path, removal_path):
        """Load all animation images from specified paths into state dictionaries."""
        self.CURRENT_IMAGES_PATH        = image_path
        self.TALKING_SENTENCES_PATH     = talking_path
        self.GREETING_SENTENCES_PATH    = greeting_path
        self.REMOVAL_SENTENCES_PATH     = removal_path

        self.images = {
            "idle1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle1.png')),
            "idle2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'idle2.png')),
            "walk1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'walk1.png')),
            "walk2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'walk2.png')),
            "talk1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking1.png')),
            "talk2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking2.png')),
            "glasses1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'glasses1.png')),
            "glasses2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'glasses2.png')),
            "sideframe": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'sideframe.png')),
            "staringframe": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'staringframe.png')),
            "talk_fwd_1": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking_forward1.png')),
            "talk_fwd_2": Image.open(os.path.join(self.CURRENT_IMAGES_PATH, 'talking_forward2.png'))
        }
        self._load_cutscenes()

        self.states = {
            'idle': [lambda: self.images["idle1"],lambda: self.images["idle2"]],
            'Limbo': [lambda: self.images["idle1"],lambda: self.images["idle2"]],
            'walking': [lambda: self.images["walk1"],lambda: self.images["walk2"]],
            'talking': [],
            'fight': [],
            'greeting': [],
            'MovieG': [lambda: self.images["glasses1"],lambda: self.images["glasses2"]],
            'MovieNG': [lambda: self.images["idle1"],lambda: self.images["idle2"]],
            'cutscene': [],
            'removal': [],
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

        if self.cutscene_active or self.fight_mode_active:
            return
        state_images = self.states.get(self.current_state, [])
        if not state_images:
            state_images = self.states.get('idle', [])
            if not state_images:
                return
            self.new_state('idle')
        self.frame = (self.frame + 1) % len(state_images)
        pil_frame_img = state_images[self.frame]
        
        photo_image = pil_frame_img() if callable(pil_frame_img) else pil_frame_img
        if self.current_facing == "Left" and self.current_state != 'talking' and self.current_state != 'removal': 
            photo_image = photo_image.transpose(Image.FLIP_LEFT_RIGHT)
        self.label.setPixmap(ImgUtils._pil_to_qpixmap(photo_image))
        if self.current_facing == "Left" and self.current_state != 'talking' and self.current_state != 'removal':
            photo_image.close()

    def move_window_x(self, target_x):
        """Animate character window movement to target X position.
        
        Args:
            target_x: Target X coordinate
        """
        start_x = self.window.x()

        total_dx = target_x - start_x
        duration_ms = int(math.ceil(abs(total_dx) / self.WALKSPEED) * 1000)
        num_steps = max(1, duration_ms // self.FRAME_DELAY_MS)
        step_dx = total_dx / num_steps

        def step_move(current_step, current_x):
            if self.fight_mode_active:
                return
            if self.currently_moving:
                self._single_shot(self.FRAME_DELAY_MS, self.idle_state)
                return
            if current_step >= num_steps:
                self.window.setGeometry(target_x, self.window.y(), self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
                self.flip_side()
                return

            new_x = int(current_x + step_dx)
            self.x = new_x
            self.window.setGeometry(new_x, self.window.y(), self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
            self._single_shot(self.FRAME_DELAY_MS, lambda: step_move(current_step + 1, current_x + step_dx))
        
        self._single_shot(self.FRAME_DELAY_MS, lambda: step_move(0, start_x))

    def _create_gui(self):
        """Create and configure the GUI elements (label, menus, window properties)."""
        layout = QVBoxLayout(self.window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.label = SharkoLabel(self.window)
        self.label.parent_sharko = self
        self.label.setPixmap(ImgUtils._pil_to_qpixmap(self.states['idle'][0]()))
        layout.addWidget(self.label)
        
        # Create context menu
        self.menu = QMenu(self.window)
        self.Movie_menu = QMenu("Movie mode", self.window)
        self.Movie_menu.addAction('Off', self.movie_off)
        self.Movie_menu.addAction('On(Glasses)', self.movie_on_g)
        self.Movie_menu.addAction('On(No glasses)', self.movie_on_ng)
        self.menu.addMenu(self.Movie_menu)
        self.menu.addAction('Fight', self.toggle_fight_mode)
        volume_widget = VolumeSlider(initial_value=int(self.sound_volume * 100))
        volume_widget.valueChanged.connect(self.sounds_logics)
        slider_action = QWidgetAction(self.menu)
        slider_action.setDefaultWidget(volume_widget)
        self.menu.addAction(slider_action)
        self.menu.addAction('Walking off', self.toggle_walking).setCheckable(True)
        self.menu.addAction('Flip side', self.flip_side)
        self.menu.addAction('Close', self.close_command)
        self.window.setWindowTitle("Sharko")
        self.window.setFixedSize(self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)

    def play_cutscene(self, cutscene_preset):
        if self.cutscene_active:
            return
        self.cutscene_active = True
        self._toggle_menu_items(['Sounds off', 'Close'])
        self.new_state('cutscene')
        cutscene = self.cutscene_presets[cutscene_preset]
        for frame in cutscene:
            frame["is_first_frame"] = True
        self._play_cutscene_frame(cutscene, 0, cutscene_preset, 0)

    def _play_cutscene_frame(self, cutscene, current_frame, cutscene_preset, repeat_count):
        if cutscene_preset == 'InactiveCutscene':
            if self.get_inactive_length() < self.INACTIVE_TIME_REQUIREMENT and current_frame < 6:
                current_frame = 6
            if current_frame == len(cutscene):
                self.cutscene_active = False
                self.talking_disabled = True
                self._toggle_menu_items(['Sounds off', 'Close'])
                self.idle_state()
                return

        if current_frame == len(cutscene):
            self.cutscene_active = False
            self._toggle_menu_items(['Sounds off', 'Close'])
            self.idle_state()
            return
        
        current_frame_data = cutscene[current_frame]
        sound_cleared = False
        if current_frame_data.get("type") in ["repeat", "talk"]:
            if current_frame_data.get("type") == "talk":
                text_img = ImgUtils._render_text_image(self,current_frame_data["text"], (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT))
                bg_img = current_frame_data["image1" if repeat_count % 2 == 0 else "image2"]()
                if self.current_facing == "Left": 
                    bg_img = bg_img.transpose(Image.FLIP_LEFT_RIGHT)
                image = ImgUtils.composite_on_base(self, bg_img, text_img, None)
                if self.current_facing == "Left":
                    bg_img.close()
                text_img.close()
            else:
                image = current_frame_data["image1"]()
                if self.current_facing == "Left": 
                    image = image.transpose(Image.FLIP_LEFT_RIGHT)

            duration    = current_frame_data["interval"]
            sound       = current_frame_data["sound"]
            
            if current_frame_data["is_first_frame"]:
                repeat_count = cutscene[current_frame]["repeat_count"]
                current_frame_data["is_first_frame"] = False
                sound_cleared = True

            repeat_count -= 1
            
            if repeat_count == 0:
                current_frame += 1
        else:
            image       = current_frame_data["image"]()
            duration    = current_frame_data["duration"]
            sound       = current_frame_data["sound"]
            sound_cleared = True
            current_frame += 1
            if self.current_facing == "Left": 
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
    

        if sound != "None" and sound_cleared:
            self.sounds(self.sounds_group[sound])
        self.label.setPixmap(ImgUtils._pil_to_qpixmap(image))
        if current_frame_data.get("type") == "talk" or current_frame_data.get("type") == "repeat" and self.current_facing == "Left":
            image.close()
        self._single_shot(duration, lambda: self._play_cutscene_frame(cutscene, current_frame, cutscene_preset, repeat_count))


    def clear_talking(self):
        if getattr(self, 'question_active', False):
            self.question_active = False
            self._question_answers = None
        for img in self.states['talking']:
            img.close()

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
        self.window.setGeometry(x, y, self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)

    def _handle_question_click(self, event):
        if not getattr(self, 'question_active', False):
            return
        x_off = self.TEXT_OFFSET_LEFT if self.current_facing == "Left" else self.TEXT_OFFSET_RIGHT
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
            self.idle_timer.deleteLater()
            self.idle_timer = None
        self.add_talking_sentences(answer_text, 'talking', False)
        self.new_state('talking')
        self._single_shot(self.TALKING_ANIMATION_DELAY, self.idle_state)

    def new_state(self, new_state):
        self.current_state = new_state

    def movie_off(self):
        self.log_stats()
        if self.movie_mode_active == True:
            self.new_state('Limbo')
            self.idle_state()

    def movie_on_g(self):
        if self.current_state in ['idle', 'talking', 'greeting']:
            self.new_state('MovieG')
    
    def movie_on_ng(self):
        if self.current_state in ['idle', 'talking', 'greeting']:
            self.new_state('MovieNG')

    def toggle_walking(self):
        self.walking_enabled = not self.walking_enabled
        if not self.walking_enabled and self.current_state == 'walking':
            self.currently_moving = True
            self._single_shot(50, self._stop_walk_cleanup)

    def _stop_walk_cleanup(self):
        self.currently_moving = False
        if self.current_state == 'walking':
            self.new_state('idle')

    def flip_side(self):
                    
        self.window.raise_()
        
        if self.current_facing == 'Right':
            self.current_facing = "Left"
            self.x = 0
        else:
            self.current_facing = "Right"
            right_x = max(0, self.screen_x - self.WINDOW_SIZE_X)
            self.x = right_x
        
        self.window.setGeometry(self.x, self.window.y(), self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
        self.animate()
        if self.current_state == 'walking': 
            self.idle_state()
            return 
        self.new_state('Limbo')

    def _on_f_pressed_safe(self):
        self.talking_disabled = False
        # Only initialize on first press, not on key repeat
        current_time = time.time()
        if self.parry_press_time == 0 and current_time - self.last_parry_block_time >= self.PARRY_BLOCK_COOLDOWN:
            self.last_parry_block_time = current_time
            # Cancel any pending callback from previous key press
            if self.block_transition_callback:
                self.block_transition_callback.stop()
                self.block_transition_callback.deleteLater()
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
                    self.sounds(self.sounds_group['block_attempt'])
            
            self.block_transition_callback = self._add_timer(QTimer())
            self.block_transition_callback.setSingleShot(True)
            self.block_transition_callback.timeout.connect(transition_to_block)
            self.block_transition_callback.start(int(self.PARRY_WINDOW * 1000))

    def _on_f_released_safe(self):
        # Handle parry key release (f)
        self.f_key_held = False
        # Cancel pending block transition if released early
        if self.block_transition_callback:
            self.block_transition_callback.stop()
            self.block_transition_callback.deleteLater()
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
        self.talking_disabled = False

    def talking_state(self):
        if self.current_state == 'idle':
            
            Line = random.choice(self.Lines + self.Questions)

            if isinstance(Line, str):
                self.add_talking_sentences(Line.strip(),'talking',False)
            else:
                self.add_new_question(Line)
            self.new_state('talking')

            self.sounds(self.sounds_group['start'])
        if hasattr(self, 'idle_timer') and self.idle_timer:
            self.idle_timer.stop()
            self.idle_timer.deleteLater()
        self.idle_timer = self._add_timer(QTimer())
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self.idle_state)
        self.idle_timer.start(self.TALKING_ANIMATION_DELAY)
    
    def _should_transition_to_idle(self) -> bool:
        """Check if current state should transition to idle state."""
        is_talking_like = self.current_state in ['talking', 'greeting']
        is_cutscene     = self.current_state == 'cutscene' and not self.cutscene_active
        is_walking      = self.current_state == 'walking'
        is_limbo        = self.current_state == 'Limbo'
        is_fight        = self.current_state == 'fight' and not self.fight_mode_active
        return is_talking_like or is_cutscene or is_walking or is_limbo or is_fight
    
    def idle_state(self):
        self.log_stats()
        if not self._should_transition_to_idle():
            return
        if self.current_state not in ['walking', 'cutscene', 'Limbo']:
            self.sounds(self.sounds_group['end'])
        self.new_state('idle')
        self.clear_talking()
        if self.get_inactive_length() > self.INACTIVE_TIME_REQUIREMENT and not self.talking_disabled:
            self.talking_disabled = True
            self._single_shot(2000, lambda: self.play_cutscene('InactiveCutscene'))
        else:
            random_number = random.random()
            if (random_number > 0.2 and not self.talking_disabled) or self.currently_moving or \
            (not self.walking_enabled and not self.talking_disabled):
                self._single_shot(self.IDLE_ANIMATION_DELAY, self.talking_state)
            elif self.walking_enabled:
                self._single_shot(self.IDLE_ANIMATION_DELAY, self.walking_state)
            else:
                self.new_state('Limbo')
                self._single_shot(self.IDLE_ANIMATION_DELAY, self.idle_state)

    def walking_state(self):
        if self.current_state != 'idle':
            return
        self.new_state('walking')

        state_images = self.states.get(self.current_state, [])
        if not state_images:
            return
        self.frame = (self.frame + 1) % len(state_images)
        photo_image = state_images[self.frame]()
        if self.current_facing == "Left": 
            photo_image = photo_image.transpose(Image.FLIP_LEFT_RIGHT)
        self.label.setPixmap(ImgUtils._pil_to_qpixmap(photo_image))
        if self.current_facing == "Left": 
            photo_image.close()

        if self.current_facing == "Right":
            self.move_window_x(-179)
        else:
            self.move_window_x(self.screen_x - 179)

    def add_new_question(self,Question_Lines):
        self.add_talking_sentences(Question_Lines,'talking',True)

    def add_talking_sentences(self,sentence,state,is_question):
        if not hasattr(self, 'Lines') or not self.Lines:
            return
        if is_question == True:
            self._add_question_images(sentence, state)
        else:
            self._add_talking_images(sentence,state)

    def _add_talking_images(self,sentence,state):
        text_img = ImgUtils._render_text_image(self, sentence, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT))
        try:
            base1_photo_image, base2_photo_image = self.images["talk1"], self.images["talk2"]
            base1 = base1_photo_image.convert('RGBA')
            base2 = base2_photo_image.convert('RGBA')
            if self.current_facing == "Left":
                base1 = base1.transpose(Image.FLIP_LEFT_RIGHT)
                base2 = base2.transpose(Image.FLIP_LEFT_RIGHT)
        except Exception:
            try:
                self.states[state] = [text_img, text_img]
            except Exception:
                return
            return

        comp1 = ImgUtils.composite_on_base(self, base1, text_img)
        comp2 = ImgUtils.composite_on_base(self, base2, text_img)
        base1.close()
        base2.close()
        for img in self.states[state]:
            img.close()
        self.states[state] = [comp1, comp2] 
    
    def _add_question_images(self,sentence, state):
        question_text   = sentence[0]
        option1_text    = sentence[1]
        option2_text    = sentence[2]
        answer1_text    = sentence[3]
        answer2_text    = sentence[4]


        q_img       = ImgUtils._render_text_image(self, question_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_TEXT_HEIGHT))
        opt1_img    = ImgUtils._render_text_image(self, option1_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))
        opt2_img    = ImgUtils._render_text_image(self, option2_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))

        try:
            base1_photo_image, base2_photo_image = self.images["talk1"], self.images["talk2"]
            base1 = base1_photo_image.convert('RGBA')
            base2 = base2_photo_image.convert('RGBA')
            if self.current_facing == "Left":
                base1 = base1.transpose(Image.FLIP_LEFT_RIGHT)
                base2 = base2.transpose(Image.FLIP_LEFT_RIGHT)

        except Exception:
            try:
                combined = Image.new('RGBA', (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT), (0, 0, 0, 0))
                combined.paste(q_img, (0, self.QUESTION_BOX_TOP_Y), q_img)
                combined.paste(opt1_img, (0, self.QUESTION_BOX_OPTION1_Y), opt1_img)
                combined.paste(opt2_img, (0, self.QUESTION_BOX_OPTION2_Y), opt2_img)
                for img in self.states[state]:
                    img.close()
                self.states[state] = [combined, combined]
                self._question_answers = (answer1_text, answer2_text)
                self.question_active = True
            except Exception:
                return
            return

        def _composite_three(base_img):
            b = base_img.copy()
            if self.current_facing == "Left":
                x = self.TEXT_OFFSET_LEFT
            else:
                x = self.TEXT_OFFSET_RIGHT
            b.paste(q_img, (x, self.QUESTION_BOX_TOP_Y), q_img)
            b.paste(opt1_img, (x, self.QUESTION_BOX_OPTION1_Y), opt1_img)
            b.paste(opt2_img, (x, self.QUESTION_BOX_OPTION2_Y), opt2_img)
            return b

        comp1 = _composite_three(base1)
        comp2 = _composite_three(base2)
        base1.close()
        base2.close()
        for img in self.states[state]:
            img.close()
        self.states[state] = [comp1, comp2]
        
        self._question_answers = (answer1_text, answer2_text)
        self.question_active = True
        return

    def close_command(self):
        self._stop_all_timers()
        if self.cutscene_active == True:
            self.cutscene_active = False
            self._toggle_menu_items(['Sounds off', 'Close'])
        self._toggle_menu_items([])
        if self.current_state != 'removal':
            self.add_talking_sentences(random.choice(self.removal_lines).strip(),'removal',False)
            self.new_state('removal')
        if not getattr(self, '_death_scheduled', False):
            self._death_scheduled = True
            self._single_shot(self.REMOVAL_ANIMATION_DELAY, self.death_animation)

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
                src_path.size = (SharkoConstants.WINDOW_SIZE_X, SharkoConstants.WINDOW_SIZE_Y)
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
                    QApplication.quit()
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
        self._death_image_buf = data
        self.deathwidget = DeathAnimationWidget(qimg)
        

    def toggle_fight_mode(self):
        if self.current_state != 'fight':
            self.fight_mode_active = True
            self.suppress_right_click = True
            self._stop_all_timers()

            if hasattr(self, 'animation_timer') and self.animation_timer:
                self.animation_timer.stop()
                self.animation_timer.deleteLater()
                self.animation_timer = None
            self.active_bar = ScalableHealthBar()
            screen_w = windll.user32.GetSystemMetrics(0)
            self.active_bar.resize(screen_w // 2, 200)
            self.active_bar.slide_in()
            self.warning_manager = MultiWarningOverlay()
            self.screen_shaker = ScreenShaker()
            self.particles_manager = VFXManager(damage_callback=lambda: CombatSystem.damage(self),shaker = self.screen_shaker)
            self.screen_shaker.particles_manager = self.particles_manager
            self.combat_ai = SharkoCombatAI(self)
            WindowsUtils.disable_desktop_grid_and_autoarrange_universal()

            self.new_state('fight')
            self.fight_loop()
        else:
            self.fight_mode_active = False
            self.suppress_right_click = False
            self.animation_timer = QTimer()
            self.animation_timer.timeout.connect(self.animate)
            self.animation_timer.start(self.ANIMATION_DELAY)
            self._stop_all_timers()

            if hasattr(self, 'pivot_images') and self.pivot_images:
                for img in self.pivot_images.values():
                    img.close() 
                self.pivot_images.clear()
                del self.pivot_images
            if hasattr(self, 'combat_ai') and self.combat_ai:
                del self.combat_ai
                self.combat_ai = None
            if hasattr(self, 'fight_loop_timer') and self.fight_loop_timer:
                self.fight_loop_timer.stop()
                self.fight_loop_timer.deleteLater()
                self.fight_loop_timer = None
            if hasattr(self, 'temp_combat_timer') and self.temp_combat_timer:
                self.temp_combat_timer.stop()
                self.temp_combat_timer.deleteLater()
                self.temp_combat_timer = None
            if hasattr(self, 'screen_shaker') and self.screen_shaker:
                self.screen_shaker.deinitialize()
                self.screen_shaker = None
            if self.active_bar:
                self.active_bar.slide_out_to_hide()
            if hasattr(self, 'particles_manager') and self.particles_manager:
                self.particles_manager.deinitialize()
                self.particles_manager = None
            if hasattr(self, 'sword_window') and self.sword_window:
                self.sword_window.deinitialize()
                self.sword_window = None
            if hasattr(self, 'warning_manager') and self.warning_manager:
                self.warning_manager.deinitialize()
                self.warning_manager = None
            self.idle_state()
        self._toggle_menu_items(['Sounds off', 'Fight'])


    def fight_loop(self):
        """
        Delegate fight loop behavior to SharkoCombatAI.

        All previous fight_loop logic now lives in boss_ai.SharkoCombatAI.run_fight_loop_tick().
        """
        # Stop any existing fight_loop_timer reference for this tick
        if hasattr(self, 'fight_loop_timer') and self.fight_loop_timer:
            self.fight_loop_timer.stop()
            self.fight_loop_timer.deleteLater()
            self.fight_loop_timer = None

        if self.current_state != 'fight' or not self.fight_mode_active:
            return
        if not self.combat_ai:
            return

        # Let AI run one full fight-loop tick (it will reschedule itself)
        self.combat_ai.run_fight_loop_tick()

    def sounds(self, sound_object):
        if self.sound_volume == 0:
            return
        with self.sound_lock:
            if sound_object[1] == True:
                try:
                    self._pitched_from_sound_object(sound_object[0])
                except Exception as e:
                    print(f"Error playing sound: {e}")
            else:
                try:
                    sound_object[0].set_volume(self.sound_volume)
                    sound_object[0].play()
                except Exception as e:
                    print(f"Error playing sound: {e}")
    def _pitched_from_sound_object(self, sound_object):
        pitch_factor = random.uniform(0.97, 1.03)

        snd_array = pygame.sndarray.array(sound_object)
        new_indices = np.arange(0, len(snd_array), pitch_factor).astype(np.int32)
        pitched_array = snd_array[new_indices[new_indices < len(snd_array)]]
        pitched_sound = pygame.sndarray.make_sound(pitched_array)
        pitched_sound.set_volume(self.sound_volume)
        pitched_sound.play()



    
    def sounds_logics(self,volume):
        self.sound_volume = volume/100        


# Initialize and run
if __name__ == "__main__":
    sharko = Sharko("assets/sharko/",
                    "assets/sentences/talking/",
                    "assets/sentences/greeting/",
                    "assets/sentences/removal/")