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

import      os
import      sys

from pynput                             import keyboard, mouse
import keyboard as                             blocker_keyboard

from PyQt5.QtWidgets                    import QApplication, QWidget, QVBoxLayout, QMenu, QWidgetAction
from PyQt5.QtGui                        import QPixmap, QPainter, QTransform, QFontDatabase
from PyQt5.QtCore                       import Qt, QTimer, QObject, pyqtSignal

from widgets.bar_guis                   import ScalableCombatBars
from vfx.vfx_manager                    import VFXManager
from vfx.warnings_manager               import MultiWarningOverlay
from vfx.hurt_vignette                  import HurtVignetteOverlay
from vfx.screen_shaker                  import ScreenShaker
from vfx.tile                           import Tile

from boss_battle                        import CombatSystem
from boss_ai                            import SharkoCombatAI

from constants                          import SharkoConstants
from windows_interactive.icons          import IconManager
from windows_interactive.toasts         import ToastManager
from windows_interactive.windows_utils  import WindowsUtils
from windows_interactive.stun_manager   import MouseStunManager

from widgets.main_monitor_clipper       import MainMonitorClipper

from audio_manager                      import AudioManager

from widgets.base_components            import SharkoLabel, MenuStyle, VolumeSlider

from img_utils                          import ImgUtils

import                                          psutil


# Enable dpi scaling
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
        ("cbSize", c_uint),
        ("dwTime", c_uint),
    ]


class InputSignalEmitter(QObject):
    """Thread-safe signal emitter for input events from pynput listeners."""
    f_pressed = pyqtSignal()
    f_released = pyqtSignal()
    action_triggered = pyqtSignal(int, int, object)
    damage_signal = pyqtSignal(str)


class Sharko(SharkoConstants, IconManager):
    """Main functionality with animation, combat, and effects."""
    thrown_icons = set()

    def __init__(self):
        """Initialize Sharko character with paths to animation assets."""
        # APPLICATION & GUI SETUP
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

        # FONT CONFIGURATIONS
        SPEECH_FONT_ID          = QFontDatabase.addApplicationFont(self.SPEECH_FONT)
        BOSS_FONT_ID            = QFontDatabase.addApplicationFont(self.BOSS_FONT)
        if SPEECH_FONT_ID != -1:
            self.SPEECH_FONT_FAMILY  = QFontDatabase.applicationFontFamilies(SPEECH_FONT_ID)[0]
        else:
            self.SPEECH_FONT_FAMILY  = "Arial"

        if BOSS_FONT_ID != -1:
            self.BOSS_FONT_FAMILY    = QFontDatabase.applicationFontFamilies(BOSS_FONT_ID)[0]
        else:
            self.BOSS_FONT_FAMILY    = "Arial"

        #  SCREEN & DISPLAY CONFIGURATION
        screen = self.app.primaryScreen()
        self.screen_x = screen.geometry().width()
        self.screen_y = screen.geometry().height()

        work_area_height = WindowsUtils.get_work_area_height()
        thickness_vertical = self.screen_y - work_area_height
        taskbar_thickness = max(0, thickness_vertical)

        x = self.screen_x - self.WINDOW_SIZE_X
        y = self.screen_y - self.WINDOW_SIZE_Y - taskbar_thickness
        self.x = x
        self.y = y
        self.window.setGeometry(x, y, self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)

        # CHARACTER & STATE
        self.current_facing = "Right"
        self.current_state = "greeting"
        self.frame = 0
        WindowsUtils.toggle_taskbar_visibility(True)

        # GAME STATE FLAGS
        self.talking_disabled       = False
        self.cutscene_active        = False
        self.fight_mode_active      = False
        self.currently_moving       = False

        # AUDIO SYSTEM
        self.audio_manager = AudioManager()
        self.sound_volume = 1
        self.default_sound_paths = {
            "end": [self.END_TALKING_SOUND, False, False],
            "start": [self.START_TALKING_SOUND, False, False],
            "greeting": [self.GREETING_SOUND, False, False],
            "clash_royale": [self.CLASH_SOUND, False, False],
            "answer": [self.ANSWER_SOUND, False, False],
        }

        self.fight_sound_paths = {
            "block_attempt": [self.BLOCK_ATTEMPT_SOUND, True, False],
            "parry": [self.PARRY_SOUND, True, False],
            "block": [self.BLOCK_SOUND, True, False],
            "hit": [self.HIT_SOUND, True, False],
            "posture_break": [self.POSTURE_BREAK_SOUND, True, False],
            "long_roar": [self.LONG_ROAR_SOUND, False, False],
            "dread_breath": [self.DREAD_BREATH_SOUND, False, False],
            "roar_1": [self.ROAR_SOUND_1, False, False],
            "roar_2": [self.ROAR_SOUND_2, False, False],
            "theme_vamp": [self.THEME_VAMP, False, False],
            "theme_loop": [self.THEME_LOOP, False, True],
        }

        for name, obj in self.fight_sound_paths.items():
            self.audio_manager.register_sound(name, obj[0], pitched=obj[1], looped=obj[2])

        for name, obj in self.default_sound_paths.items():
            self.audio_manager.register_sound(name, obj[0], pitched=obj[1], looped=obj[2])
            self.audio_manager.load_sound(name)

        # MOVEMENT SYSTEM
        self.walking_enabled = True

        # INPUT & INTERACTION
        self.suppress_right_click = False
        self.question_active = False
        self._question_answers = None
        self.screen_shaker = None
        self.particles_manager = None
        self.sword_window = None
        self.warning_manager = None
        self.hurt_vignette = None

        # PARRY AND BLOCK MECHANICS
        self.attack_press_time          = 0
        self.attack_active_until        = 0
        self.last_attack_time           = 0
        self.parry_press_time           = 0
        self.parry_block_active_until   = 0
        self.last_parry_block_time      = 0
        self.f_key_held                 = False
        self.posture                    = 0
        self.posture_break_cooldown_until = 0
        # ASSET LOADING
        self._load_images()

        # GUI SETUP
        self._create_gui()

        # ANIMATION & CALLBACKS
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(self.ANIMATION_DELAY)

        # TIMER MANAGEMENT SYSTEM
        self.active_timers = set()  # Track all non-animation timers

        self.idle_timer = None
        self.fight_loop_timer = None
        self.temp_combat_timer = None
        self.block_transition_callback = None

        # STARTUP SEQUENCE
        self.audio_manager.play("greeting", volume=self.sound_volume)
        self.add_talking_sentences(self.intro_line.strip(), "greeting", False)

        self.window.show()

        self._single_shot(self.GREETING_ANIMATION_DELAY, lambda: (
            self.idle_state(),
            self.states.update({"greeting": []})
        ))
        # COMBAT SYSTEM
        self.bar_guis = None
        self.combat_ai = None

        # FLIP OBJECT
        self.horizontal_flip = QTransform()
        self.horizontal_flip.scale(-1, 1)

        # SYSTEM MONITORING
        self.process = psutil.Process(os.getpid())

        # INPUT SIGNAL EMITTER (for thread-safe communication from pynput listeners)
        self.input_emitter = InputSignalEmitter()
        self.input_emitter.f_pressed.connect(self._on_f_pressed_safe, Qt.QueuedConnection)
        self.input_emitter.f_released.connect(self._on_f_released_safe, Qt.QueuedConnection)
        self.input_emitter.action_triggered.connect(self._on_action_safe, Qt.QueuedConnection)
        self.input_emitter.damage_signal.connect(lambda attack_type: CombatSystem.damage(self, attack_type), Qt.QueuedConnection)

        self.keyboard_listener = None
        self.mouse_listener = None
        sys.exit(self.app.exec_())

    def log_stats(self):
        """Log current memory usage statistics."""
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        print(f"RAM: {mem_mb:.2f} MB")

    @staticmethod
    def get_inactive_length():
        """Returns user inactivity duration since the last input in ms."""
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
            except (RuntimeError, TypeError):
                pass
        self.active_timers.clear()

    def _cancel_block_transition(self):
        """Cancels any pending block transitions and resets parry/block flags."""
        if self.block_transition_callback:
            self.block_transition_callback.stop()
            self.block_transition_callback.deleteLater()
            self.block_transition_callback = None
        self.parry_press_time = 0
        self.f_key_held = False

    @staticmethod
    def _calculate_new_posture(current_posture, posture_amount, max_posture):
        """Calculates the new posture value from the current posture and the modification amount.
        Also contains logic to determine if a posture overflow occurred."""
        if max_posture <= 0:
            return 0, False

        new_posture = max(0, min(max_posture, current_posture + posture_amount))
        overflow = new_posture >= max_posture and posture_amount > 0
        return new_posture, overflow

    def _apply_posture(self, posture_amount):
        """Adjust posture and trigger the posture-broken state if it fills up."""
        current_posture = self.posture
        new_posture, overflow = self._calculate_new_posture(current_posture, posture_amount, self.MAX_POSTURE)

        if overflow and current_posture < self.MAX_POSTURE:
            self.posture = 0
            QTimer.singleShot(200, lambda: (setattr(self.bar_guis, 'pb_percentage', 0), setattr(self, 'posture', 0)))
            self._cancel_block_transition()
            self.posture_break_cooldown_until = time.time() + self.POSTURE_BREAK_COOLDOWN
        self.posture = new_posture
        return overflow

    def _create_gui(self):
        """Create and configure the gui elements (label, menus, window properties)."""
        layout = QVBoxLayout(self.window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.label = SharkoLabel(self.window)
        self.label.parent_sharko = self
        self.label.setPixmap(self.states["idle"][0]())
        layout.addWidget(self.label)

        # Create context menu
        self.menu = QMenu(self.window)
        self.Movie_menu = QMenu("Do not disturb", self.window)  # internally known as movie mode
        self.Movie_menu.addAction("Off", self.movie_off)
        self.Movie_menu.addAction("On(Movie glasses)", self.movie_on_g)
        self.Movie_menu.addAction("On(No glasses)", self.movie_on_ng)
        self.menu.addMenu(self.Movie_menu)
        self.menu.addAction("Fight", self.toggle_fight_mode)
        volume_widget = VolumeSlider(initial_value=int(self.sound_volume * 100))
        volume_widget.valueChanged.connect(self.sounds_logics)
        slider_action = QWidgetAction(self.menu)
        slider_action.setDefaultWidget(volume_widget)
        self.menu.addAction(slider_action)
        self.menu.addAction("Walking off", self.toggle_walking).setCheckable(True)
        self.menu.addAction("Flip side", lambda: self.flip_side(True))
        self.menu.addAction("Close", self.close_command)
        self.window.setWindowTitle("Sharko")
        self.window.setFixedSize(self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)

    def _load_cutscenes(self):
        """Load and initialize cutscene animation presets with frames and timing."""

        self.cutscene_presets = {
            "InactiveCutscene": [
                {"image": lambda: self.qpixmaps["idle1"], "duration": 1000, "sound": "None"},
                {"image": lambda: self.qpixmaps["sideframe"], "duration": 150, "sound": "None"},
                {"image": lambda: self.qpixmaps["staringframe"], "duration": 1000, "sound": "None"},
                {"type": "talk", "image1": lambda: self.qpixmaps["talk_fwd_1"], "image2": lambda: self.qpixmaps["talk_fwd_2"], "sound": "start", "interval": 500, "repeat_count": 11, "text": "hello?"},
                {"type": "talk", "image1": lambda: self.qpixmaps["talk_fwd_1"], "image2": lambda: self.qpixmaps["talk_fwd_2"], "sound": "clash_royale", "interval": 500, "repeat_count": 10, "text": "HELLO!"},
                {"image": lambda: self.qpixmaps["staringframe"], "duration": 1000, "sound": "None"},
                {"image": lambda: self.qpixmaps["sideframe"], "duration": 150, "sound": "None", "on_complete": "None"},
            ],
            "BeginFightCutscene": [
                {"image": lambda: self.qpixmaps["idle1"], "duration": 1000, "sound": "theme_vamp"},
                {"image": lambda: self.qpixmaps["staringframe"], "duration": 1000, "sound": "None"},
                {"type": "talk", "image1": lambda: self.qpixmaps["talk_fwd_1"], "image2": lambda: self.qpixmaps["talk_fwd_2"], "sound": "None", "interval": 500, "repeat_count": 20, "text": "Fight cutscene test text 1"},
                {"type": "talk", "image1": lambda: self.qpixmaps["talk_fwd_1"], "image2": lambda: self.qpixmaps["talk_fwd_2"], "sound": "None", "interval": 500, "repeat_count": 15, "text": "Fight cutscene test text 2"},
                {"image": lambda: self.qpixmaps["staringframe"], "duration": 1000, "sound": "None"},
                {"image": lambda: self.qpixmaps["sideframe"], "duration": 150, "sound": "None", "on_complete": "None"},
            ],
        }

    def _load_images(self):
        """Load all animation images from specified paths into state dictionaries."""

        self.qpixmaps = {
            "idle1": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "idle1.png")),
            "idle2": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "idle2.png")),
            "walk1": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "walk1.png")),
            "walk2": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "walk2.png")),
            "glasses1": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "glasses1.png")),
            "glasses2": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "glasses2.png")),
            "sideframe": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "sideframe.png")),
            "staringframe": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "staringframe.png")),
            "talk1": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "talking1.png")),
            "talk2": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "talking2.png")),
            "talk_fwd_1": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "talking_forward1.png")),
            "talk_fwd_2": QPixmap(os.path.join(self.CURRENT_IMAGES_PATH, "talking_forward2.png")),
        }
        self._load_cutscenes()

        self.states = {
            "idle": [lambda: self.qpixmaps["idle1"], lambda: self.qpixmaps["idle2"]],
            "Limbo": [lambda: self.qpixmaps["idle1"], lambda: self.qpixmaps["idle2"]],
            "walking": [lambda: self.qpixmaps["walk1"], lambda: self.qpixmaps["walk2"]],
            "talking": [],
            "fight": [],
            "greeting": [],
            "MovieG": [lambda: self.qpixmaps["glasses1"], lambda: self.qpixmaps["glasses2"]],
            "MovieNG": [lambda: self.qpixmaps["idle1"], lambda: self.qpixmaps["idle2"]],
            "cutscene": [],
            "removal": [],
        }

    def _toggle_menu_items(self, whitelist, enable):
        """Toggle enabled/disabled state of menu items."""
        for action in self.menu.actions():
            if action.text() not in whitelist:
                action.setEnabled(enable)
            else:
                action.setEnabled(True)

    def animate(self):
        """Update and render current animation frame based on character state."""
        if self.label.pixmap() is None or self.label.pixmap().isNull() or self.cutscene_active:
            return

        state_images = self.states.get(self.current_state, [])
        if not state_images:
            state_images = self.states.get("idle", [])
            if not state_images:
                return
            self.new_state("idle")
        self.frame = (self.frame + 1) % len(state_images)
        qpixmap_frame_pointer = state_images[self.frame]

        qpixmap = qpixmap_frame_pointer() if callable(qpixmap_frame_pointer) else qpixmap_frame_pointer
        if self.current_facing == "Left" and self.current_state not in ("talking", "removal"):
            qpixmap = qpixmap.transformed(self.horizontal_flip)
        self.label.setPixmap(qpixmap)

    def move_window_x(self, target_x):
        """Animate character window movement to target X position."""
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
                self.flip_side(False)
                return

            new_x = int(current_x + step_dx)
            self.x = new_x
            self.window.setGeometry(new_x, self.window.y(), self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
            self._single_shot(self.FRAME_DELAY_MS, lambda: step_move(current_step + 1, current_x + step_dx))

        self._single_shot(self.FRAME_DELAY_MS, lambda: step_move(0, start_x))

    def play_cutscene(self, cutscene_preset):
        """Initializes playing a cutscene preset if no other cutscene is active."""
        if self.cutscene_active:
            return
        self.cutscene_active = True
        self._toggle_menu_items(["Close"], False)
        self.new_state("cutscene")
        cutscene = self.cutscene_presets[cutscene_preset]
        for frame in cutscene:
            frame["is_first_frame"] = True
        if hasattr(self, "skip_cutscene_action") and self.skip_cutscene_action:
            self.menu.removeAction(self.skip_cutscene_action)
        self.cutscene_skipped = False
        self.skip_cutscene_action = self.menu.addAction("Skip cutscene", lambda: setattr(self, "cutscene_skipped", True))
        self._play_cutscene_frame(cutscene, 0, cutscene_preset, 0)

    def _play_cutscene_frame(self, cutscene, current_frame, cutscene_preset, repeat_count):
        """Renders a single cutscene frame, handling repeat/talk segments, and then schedules the next frame."""
        if cutscene_preset == "InactiveCutscene" and self.get_inactive_length() < self.INACTIVE_TIME_REQUIREMENT and current_frame < 6 or self.cutscene_skipped:
            current_frame = 6
            self.talking_disabled = True
        if current_frame == len(cutscene):
            if hasattr(self, "skip_cutscene_action") and self.skip_cutscene_action:
                self.menu.removeAction(self.skip_cutscene_action)
            self.cutscene_active = False
            self._toggle_menu_items(["Close"], True)
            if cutscene[current_frame - 1]["on_complete"] == "None":
                self.idle_state()
            else:
                cutscene[current_frame - 1]["on_complete"]()
            return

        current_frame_data = cutscene[current_frame]
        frame_type = current_frame_data.get("type")
        sound_cleared = False
        if frame_type in ("repeat", "talk"):
            if frame_type == "talk":
                text_img = ImgUtils._render_text_image(self, current_frame_data["text"], (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT))
                bg_pixmap = current_frame_data["image1" if repeat_count % 2 == 0 else "image2"]()
                if self.current_facing == "Left":
                    bg_pixmap = bg_pixmap.transformed(self.horizontal_flip)
                image = ImgUtils.composite_on_base(self, bg_pixmap, text_img)
            else:
                image = current_frame_data["image1"]()
                if self.current_facing == "Left":
                    image = image.transformed(self.horizontal_flip)

            duration = current_frame_data["interval"]
            sound = current_frame_data["sound"]

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
                image = image.transformed(self.horizontal_flip)

        if sound != "None" and sound_cleared:
            self.audio_manager.play(sound, volume=self.sound_volume)
        self.label.setPixmap(image)
        self._single_shot(duration, lambda: self._play_cutscene_frame(cutscene, current_frame, cutscene_preset, repeat_count))

    def clear_talking(self):
        """Clears any active talking state images and resets flags."""
        if getattr(self, "question_active", False):
            self.question_active = False
            self._question_answers = None
        self.states["talking"] = []

    def _middle_button_pressed(self, event):
        """Starts a drag operation when the middle mouse button is pressed."""
        if self.fight_mode_active or self.cutscene_active:
            return
        self.y = event.pos().y()
        self.x = event.pos().x()
        self.currently_moving = True

    def _middle_button_released(self, event):
        """Ends the drag operation when the middle mouse button is released."""
        self.y = event.pos().y()
        self.currently_moving = False

    def _middle_button_hold_move(self, event):
        """Moves the main character window while the middle mouse button is held down and moved."""
        if self.fight_mode_active or self.cutscene_active:
            return
        cursor_pos = event.globalPos()
        x = cursor_pos.x() - self.x
        y = cursor_pos.y() - self.y
        self.window.setGeometry(x, y, self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)

    def _handle_question_click(self, event):
        """Processes clicks on question options when a question dialogue is active."""
        if not getattr(self, "question_active", False):
            return
        x_off = self.TEXT_OFFSET_LEFT if self.current_facing == "Left" else self.TEXT_OFFSET_RIGHT
        x = event.pos().x()
        y = event.pos().y()
        answer_text = None
        if x_off <= x <= x_off + self.QUESTION_BOX_WIDTH and self.QUESTION_BOX_OPTION1_Y <= y <= self.QUESTION_BOX_OPTION1_Y + self.QUESTION_BOX_OPTION_HEIGHT:
            answer_text = self._question_answers[0] if self._question_answers else None
        elif x_off <= x <= x_off + self.QUESTION_BOX_WIDTH and self.QUESTION_BOX_OPTION2_Y <= y <= self.QUESTION_BOX_OPTION2_Y + self.QUESTION_BOX_OPTION_HEIGHT:
            answer_text = self._question_answers[1] if self._question_answers else None

        if answer_text:
            self.audio_manager.play("answer", volume=self.sound_volume)
            self._display_answer(answer_text)

    def _display_answer(self, answer_text):
        """Creates a speaking animation with a response when the user answers a question."""
        self.question_active = False
        self._question_answers = None
        if hasattr(self, "idle_timer") and self.idle_timer:
            self.idle_timer.stop()
            self.idle_timer.deleteLater()
            self.idle_timer = None
        self.add_talking_sentences(answer_text, "talking", False)
        self.new_state("talking")
        self._single_shot(self.TALKING_ANIMATION_DELAY, self.idle_state)

    def new_state(self, new_state):
        """Sets the current state of the sharko."""
        self.current_state = new_state

    def movie_off(self):
        """Turns off movie mode and returns to idle."""
        self.log_stats()
        if self.current_state in ("MovieG", "MovieNG"):
            self.new_state("Limbo")
            self.idle_state()

    def movie_on_g(self):
        """Activates movie/ do not disturb mode with movie glasses."""
        if self.current_state in ("idle", "talking", "greeting"):
            self.new_state("MovieG")

    def movie_on_ng(self):
        """Activates movie/ do not disturb mode without movie glasses."""
        if self.current_state in ("idle", "talking", "greeting"):
            self.new_state("MovieNG")

    def toggle_walking(self):
        """Toggles whether Destroyman III can walk around the screen."""
        self.walking_enabled = not self.walking_enabled
        if not self.walking_enabled and self.current_state == "walking":
            self.currently_moving = True
            self._single_shot(50, self._stop_walk_cleanup)

    def _stop_walk_cleanup(self):
        """Finishes walking animation and returns to idle."""
        self.currently_moving = False
        if self.current_state == "walking":
            self.new_state("idle")

    def flip_side(self, manual_activation=False):
        """Flips Destroyman III's facing direction between left and right and repositions the window accordingly."""
        if manual_activation and self.current_state == "walking":
            return
        self.window.raise_()

        if self.current_facing == "Right":
            self.current_facing = "Left"
            self.x = 0
        else:
            self.current_facing = "Right"
            right_x = max(0, self.screen_x - self.WINDOW_SIZE_X)
            self.x = right_x

        self.window.setGeometry(self.x, self.window.y(), self.WINDOW_SIZE_X, self.WINDOW_SIZE_Y)
        self.animate()
        if self.current_state == "walking":
            self.idle_state()
            return
        self.new_state("Limbo")

    def _on_f_pressed_safe(self):
        """Handles an f key press in a safe, main thread friendly way."""
        current_time = time.time()
        if current_time < self.posture_break_cooldown_until:
            return
        if self.parry_press_time == 0 and current_time - self.last_parry_block_time >= self.PARRY_BLOCK_COOLDOWN:
            self._cancel_block_transition()

            self.f_key_held = True
            self.last_parry_block_time = current_time
            self.parry_press_time = current_time
            self.parry_block_active_until = self.parry_press_time + self.PARRY_WINDOW

            def transition_to_block():
                if self.f_key_held and (time.time() - self.parry_press_time) >= self.PARRY_WINDOW:
                    self.parry_block_active_until = time.time() + self.PARRY_WINDOW
                    self.audio_manager.play("block_attempt", volume=self.sound_volume)

            self.block_transition_callback = self._add_timer(QTimer())
            self.block_transition_callback.setSingleShot(True)
            self.block_transition_callback.timeout.connect(transition_to_block)
            self.block_transition_callback.start(int(self.PARRY_WINDOW * 1000))

    def _on_f_released_safe(self):
        """Handles parry key release (f) in a safe, main thread friendly way."""
        self.f_key_held = False
        self._cancel_block_transition()

    def _on_action_safe(self, x, y, button):
        if self.fight_mode_active and button == mouse.Button.left:
            current_time = time.time()
            if current_time - self.last_attack_time >= self.ATTACK_COOLDOWN:
                self.last_attack_time = current_time
                self.attack_press_time = time.time()
                self.attack_active_until = self.attack_press_time + self.PARRY_WINDOW
                CombatSystem.mouse_attack(self, x, y)

    def _on_f_press(self, key):
        """Keyboard listener callback for f key presses that will later trigger the safe f key functions."""
        if getattr(key, "char", None) == "f" and self.fight_mode_active:
            self.input_emitter.f_pressed.emit()

    def _on_f_release(self, key):
        """Keyboard listener callback for f key releases that will later trigger the safe f key functions."""
        if getattr(key, "char", None) == "f" and self.fight_mode_active:
            self.input_emitter.f_released.emit()

    def _on_mouse_click(self, x, y, button, pressed):
        """Mouse listener callback for button clicks.
            - Can later trigger the safe action function.
            - Can also supress clicks during fight mode to stop the user from changing the desktop icon settings and ruin attacks."""
        if button == mouse.Button.right and self.suppress_right_click and WindowsUtils.should_supress_click():
            mouse.Listener.suppress_event(self)
        if pressed:
            self.input_emitter.action_triggered.emit(x, y, button)

    def _start_input_listeners(self):
        """Starts the keyboard and mouse listeners for fight mode."""
        if self.keyboard_listener is None:
            self.keyboard_listener = keyboard.Listener(on_press=self._on_f_press, on_release=self._on_f_release)
        if self.mouse_listener is None:
            self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)

        self.keyboard_listener.start()
        self.mouse_listener.start()

    def _stop_input_listeners(self):
        """Stops the keyboard and mouse listeners once fight mode ends."""
        for listener in (self.keyboard_listener, self.mouse_listener):
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
        self.keyboard_listener = None
        self.mouse_listener = None

    def talking_state(self):
        """Starts a talking animation and state, can either be a normal dialouge or a question."""
        if self.current_state == "idle":
            line_text = random.choice(self.Lines + self.Questions)

            if isinstance(line_text, str):
                self.add_talking_sentences(line_text, "talking", False)
            else:
                self.add_talking_sentences(line_text, "talking", True)
            self.new_state("talking")

            self.audio_manager.play("start", volume=self.sound_volume)
        if hasattr(self, "idle_timer") and self.idle_timer:
            self.idle_timer.stop()
            self.idle_timer.deleteLater()
        self.idle_timer = self._add_timer(QTimer())
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self.idle_state)
        self.idle_timer.start(self.TALKING_ANIMATION_DELAY)

    def _should_transition_to_idle(self) -> bool:
        """Check if current state should transition to idle state."""
        is_talking_like = self.current_state in ("talking", "greeting")
        is_cutscene     = self.current_state == "cutscene" and not self.cutscene_active
        is_walking      = self.current_state == "walking"
        is_limbo        = self.current_state == "Limbo"
        is_fight        = self.current_state == "fight" and not self.fight_mode_active
        return is_talking_like or is_cutscene or is_walking or is_limbo or is_fight

    def idle_state(self):
        """Idle state initialization, and descision making on what to do next."""
        self.log_stats()
        if not self._should_transition_to_idle():
            return
        if self.current_state not in ("walking", "cutscene", "Limbo"):
            self.audio_manager.play("end", volume=self.sound_volume)
        self.new_state("idle")
        self.clear_talking()
        inactive_length = self.get_inactive_length()
        if inactive_length > self.INACTIVE_TIME_REQUIREMENT and not self.talking_disabled:
            self.talking_disabled = True
            self._single_shot(2000, lambda: self.play_cutscene("InactiveCutscene"))
        else:
            if inactive_length < self.INACTIVE_TIME_REQUIREMENT:
                self.talking_disabled = False
            random_number = random.random()
            if (random_number > 0.2 and not self.talking_disabled) or self.currently_moving or not self.walking_enabled and not self.talking_disabled:
                self._single_shot(self.IDLE_ANIMATION_DELAY, self.talking_state)
            elif self.walking_enabled:
                self._single_shot(self.IDLE_ANIMATION_DELAY, self.walking_state)
            else:
                self.new_state("Limbo")
                self._single_shot(self.IDLE_ANIMATION_DELAY, self.idle_state)

    def walking_state(self):
        """triggers the walking animation and state from idle."""
        if self.current_state != "idle":
            return
        self.new_state("walking")

        state_images = self.states.get(self.current_state, [])
        if not state_images:
            return
        self.frame = (self.frame + 1) % len(state_images)
        qpixmap = state_images[self.frame]()
        if self.current_facing == "Left":
            qpixmap = qpixmap.transformed(self.horizontal_flip)
        self.label.setPixmap(qpixmap)

        if self.current_facing == "Right":
            self.move_window_x(-179)
        else:
            self.move_window_x(self.screen_x - 179)        

    def add_talking_sentences(self, sentence, state, is_question):
        """Simply adds talking or question images for a given sentence for a named state."""
        if not self.Lines:
            return
        if is_question:
            self._add_question_images(sentence, state)
        else:
            self._add_talking_images(sentence, state)

    def _add_talking_images(self, sentence, state):
        """Builds talking frames for a sentence using the talking base images."""
        text_img = ImgUtils._render_text_image(self, sentence, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_HEIGHT))

        base1 = self.qpixmaps["talk1"]
        base2 = self.qpixmaps["talk2"]

        if self.current_facing == "Left":
            base1 = base1.transformed(self.horizontal_flip)
            base2 = base2.transformed(self.horizontal_flip)

        comp1_pixmap = ImgUtils.composite_on_base(self, base1, text_img)
        comp2_pixmap = ImgUtils.composite_on_base(self, base2, text_img)

        self.states[state] = [comp1_pixmap, comp2_pixmap]

    def _add_question_images(self, sentence, state):
        """Builds question frames for a sentence using the talking base images."""
        question_text, option1_text, option2_text, answer1_text, answer2_text = sentence

        q_img    = ImgUtils._render_text_image(self, question_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_TEXT_HEIGHT))
        opt1_img = ImgUtils._render_text_image(self, option1_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))
        opt2_img = ImgUtils._render_text_image(self, option2_text, (self.QUESTION_BOX_WIDTH, self.QUESTION_BOX_OPTION_HEIGHT))

        base1 = self.qpixmaps["talk1"]
        base2 = self.qpixmaps["talk2"]
        if self.current_facing == "Left":
            base1 = base1.transformed(self.horizontal_flip)
            base2 = base2.transformed(self.horizontal_flip)

        comp1_pixmap = ImgUtils.composite_three(self, base1, q_img, opt1_img, opt2_img)
        comp2_pixmap = ImgUtils.composite_three(self, base2, q_img, opt1_img, opt2_img)

        self.states[state] = [comp1_pixmap, comp2_pixmap]
        self._question_answers = (answer1_text, answer2_text)
        self.question_active = True

    def close_command(self):
        """Initiates removal sequence and schedules the death animation."""
        self._stop_all_timers()
        if self.cutscene_active:
            self.cutscene_active = False
        self._toggle_menu_items([], False)
        if self.current_state != "removal":
            self.add_talking_sentences(random.choice(self.removal_lines).strip(), "removal", False)
            self.new_state("removal")
        if not getattr(self, "_death_scheduled", False):
            self._death_scheduled = True
            self._single_shot(self.REMOVAL_ANIMATION_DELAY, self.death_animation)

    def death_animation(self):
        """The tile based death animation that quits the program once it finishes."""
        screen_x, screen_y = self.window.x(), self.window.y()
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
                self.setGeometry(screen_x - 50, screen_y - 600, self.img_w, self.img_h)
                self.setFixedSize(600, 2000)
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
                            self.tiles.append(Tile(QPixmap.fromImage(tile_img), x + 50, y, SharkoConstants.FADE_STEP))

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
                    painter.setOpacity(tile.alpha / 255)
                    painter.translate(tile.x + TILE_SIZE // 2, tile.y + TILE_SIZE // 2)
                    painter.rotate(tile.angle)
                    painter.translate(-TILE_SIZE // 2, -TILE_SIZE // 2)
                    painter.drawPixmap(0, 0, tile.img)
                    painter.restore()
        state_images = self.states.get(self.current_state, [])
        qpixmap = state_images[self.frame]
        qimg = qpixmap.toImage()
        self.deathwidget = DeathAnimationWidget(qimg)

    def toggle_fight_mode(self):
        """Toggles fight mode on or off, and instantiates or deinitializes down combat related systems."""
        if self.current_state != "fight":
            def _start_fight_mode():
                for name in self.fight_sound_paths:
                    self.audio_manager.load_sound(name)

                self.fight_mode_active = True
                WindowsUtils.cache_desktop_handles()
                blocker_keyboard.add_hotkey('shift+f10', lambda: None, suppress=True)  # desktop context menu open shortcut
                self.suppress_right_click = True
                self._stop_all_timers()
                if not self.audio_manager.is_track_playing("theme_loop"):
                    self.audio_manager.play("theme_loop", volume=self.sound_volume)
                self.audio_manager.unload_sound("theme_vamp")

                if self.animation_timer:
                    self.animation_timer.stop()
                    self.animation_timer.deleteLater()
                    self.animation_timer = None

                self.bar_guis = ScalableCombatBars(bar_height_scale=0.05, target_obj=self)
                self.posture = 0
                self.posture_break_cooldown_until = 0
                self.bar_guis.slide_in()
                self.warning_manager = MultiWarningOverlay()
                self.hurt_vignette = HurtVignetteOverlay()
                self.screen_shaker = ScreenShaker()
                self.toast_manager = ToastManager(damage_callback=lambda attack_type: CombatSystem.damage(self, attack_type))
                self.particles_manager = VFXManager(damage_callback=lambda attack_type: CombatSystem.damage(self, attack_type), screen_shaker=self.screen_shaker)
                self.screen_shaker.particles_manager, self.screen_shaker.hurt_vignette = self.particles_manager, self.hurt_vignette
                self.combat_ai = SharkoCombatAI(self)
                self.main_monitor_clipper = MainMonitorClipper(self.window)
                self.stun_manager = MouseStunManager()

                WindowsUtils.disable_desktop_grid_and_autoarrange_universal()
                self._start_input_listeners()

                self.new_state("fight")
                self.fight_loop()
                self._toggle_menu_items(["Fight"], False)
            self.cutscene_presets["BeginFightCutscene"][-1]["on_complete"] = _start_fight_mode
            self._single_shot(self.audio_manager.get_sound_length("theme_vamp") - 100, lambda: self.audio_manager.play("theme_loop", volume=self.sound_volume))
            self.play_cutscene("BeginFightCutscene")
        else:
            self.fight_mode_active = False
            self.suppress_right_click = False
            blocker_keyboard.remove_hotkey('shift+f10')
            self._stop_input_listeners()
            self.animation_timer = QTimer()
            self.animation_timer.timeout.connect(self.animate)
            self.animation_timer.start(self.ANIMATION_DELAY)
            self._stop_all_timers()
            if hasattr(self, "main_monitor_clipper") and self.main_monitor_clipper:
                self.main_monitor_clipper.destroy_clipper()
                self.main_monitor_clipper = None
            for name in self.fight_sound_paths:
                self.audio_manager.unload_sound(name)
            if hasattr(self, "fight_img_cleanup_func") and self.fight_img_cleanup_func:
                self.fight_img_cleanup_func()
                self.fight_img_cleanup_func = None
            if hasattr(self, "combat_ai") and self.combat_ai:
                del self.combat_ai
                self.combat_ai = None
            if hasattr(self, "fight_loop_timer") and self.fight_loop_timer:
                self.fight_loop_timer.stop()
                self.fight_loop_timer.deleteLater()
                self.fight_loop_timer = None
            if hasattr(self, "temp_combat_timer") and self.temp_combat_timer:
                self.temp_combat_timer.stop()
                self.temp_combat_timer.deleteLater()
                self.temp_combat_timer = None
            if hasattr(self, "screen_shaker") and self.screen_shaker:
                self.screen_shaker.deinitialize()
                self.screen_shaker = None
            if hasattr(self, "toast_manager") and self.toast_manager:
                self.toast_manager.deinitialize()
                self.toast_manager = None
            if self.bar_guis:
                self.bar_guis.slide_out_to_hide()
                self.bar_guis = None
            if hasattr(self, "particles_manager") and self.particles_manager:
                self.particles_manager.deinitialize()
                self.particles_manager = None
            if hasattr(self, "sword_window") and self.sword_window:
                self.sword_window.deinitialize()
                self.sword_window = None
            if hasattr(self, "warning_manager") and self.warning_manager:
                self.warning_manager.deinitialize()
                self.warning_manager = None
            if hasattr(self, "hurt_vignette") and self.hurt_vignette:
                self.hurt_vignette.deinitialize()
                self.hurt_vignette = None
            if hasattr(self, "stun_manager") and self.stun_manager:
                self.stun_manager.deinitialize()
                self.stun_manager = None
            self.idle_state()
            self._toggle_menu_items(["Fight"], True)

    def fight_loop(self):
        """Executes one iteration of the fight loop, hands over the actual work to the combat AI."""
        if self.fight_loop_timer:
            self.fight_loop_timer.stop()
            self.fight_loop_timer.deleteLater()
            self.fight_loop_timer = None

        if self.current_state != "fight" or not self.fight_mode_active or not self.combat_ai:
            return

        self.combat_ai.run_fight_loop_tick()

    def sounds_logics(self, volume):
        """Updates volume based on the slider value."""
        self.sound_volume = volume / 100
        self.audio_manager.set_sound_volume("theme_loop", self.sound_volume)
        self.audio_manager.set_sound_volume("theme_vamp", self.sound_volume)


# Initialize and run
if __name__ == "__main__":
    sharko = Sharko()
