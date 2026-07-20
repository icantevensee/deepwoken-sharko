"""
combat AI for Sharko.

Main fight loop functionality and descision making.
"""

import                                         random

from PyQt5.QtCore                       import QTimer

import                                         win32api
import                                         win32gui

from windows_interactive.windows_utils  import WindowsUtils
from boss_battle                        import CombatSystem


class SharkoCombatAI:

    def __init__(self, sharko):
        """Initialize the combat ai with tiered attack lists."""
        self.sharko = sharko
        self.tier_1_attacks = [self._jump_and_attack]#[self._jump_and_attack, self._do_area_belly_flop]
        self.tier_2_attacks = []#[self._toast_attack, self._do_laser]
        self.tier_3_attacks = []#[self._roar_attack]
        self.all_attacks = (self.tier_1_attacks + self.tier_2_attacks + self.tier_3_attacks)
        self._first_attack_db = False

    def run_fight_loop_tick(self):
        """Executes one iteration of the descision making loop."""

        if not self._first_attack_db:
            random_attack = self._roar_attack
            self._first_attack_db = True
        else:
            random_attack = random.choice(self.all_attacks)
        random_attack()
        self.sharko.log_stats()

    def _inter_attack_idle(self):
        self.sharko.fight_img_cleanup_func = None
        sharko = self.sharko
        num_idle_frames = sharko.INTER_ATTACK_IDLE_TIME // sharko.ANIMATION_DELAY
        current_idle_frame = 0

        def play_idle_frame(current_frame):
            """Plays an animated idle sequence between boss attacks and schedules the next descision making iteration."""
            if current_frame == num_idle_frames:
                # After idle, schedule the next fight_loop on Sharko
                if sharko.fight_loop_timer:
                    sharko.fight_loop_timer.stop()
                    sharko.fight_loop_timer.deleteLater()
                    sharko.fight_loop_timer = None
                sharko.fight_loop_timer = sharko._add_timer(QTimer())
                sharko.fight_loop_timer.setSingleShot(True)
                sharko.fight_loop_timer.timeout.connect(sharko.fight_loop)
                sharko.fight_loop_timer.start(sharko.ANIMATION_DELAY)
                return

            current_frame += 1
            # Alternate idle frames

            if current_frame % 2 == 0:
                pixmap = sharko.states["idle"][0]()
            else:
                pixmap = sharko.states["idle"][1]()

            if sharko.current_facing == "Left":
                pixmap = pixmap.transformed(sharko.horizontal_flip)
            sharko.label.setPixmap(pixmap)

            if sharko.fight_loop_timer:
                sharko.fight_loop_timer.stop()
                sharko.fight_loop_timer.deleteLater()
                sharko.fight_loop_timer = None
            sharko.fight_loop_timer = sharko._add_timer(QTimer())
            sharko.fight_loop_timer.setSingleShot(True)
            sharko.fight_loop_timer.timeout.connect(lambda: play_idle_frame(current_frame))
            sharko.fight_loop_timer.start(sharko.ANIMATION_DELAY)

        play_idle_frame(current_idle_frame)

    def _do_area_belly_flop(self):
        sharko = self.sharko

        num_subdivisions = 6
        num_lethal = 3
        warning_time_ms = 1200

        work_area_height = WindowsUtils.get_work_area_height()

        CombatSystem.area_belly_flop(
            sharko,
            warning_time_ms,
            num_subdivisions,
            num_lethal,
            work_area_height,
            on_complete=self._inter_attack_idle,
        )

    def _do_laser(self):
        CombatSystem.lazer(self.sharko, on_complete=self._inter_attack_idle)

    def _toast_attack(self):
        if WindowsUtils.are_notifications_enabled():
            CombatSystem.toast_attack(self.sharko, on_complete=self._inter_attack_idle)
        else:
            available_attacks = [attack for attack in self.all_attacks if attack != self._toast_attack]
            random_attack = random.choice(available_attacks)
            random_attack()

    def _roar_attack(self):
        CombatSystem.roar_attack(self.sharko, on_complete=self._inter_attack_idle)

    def _do_sword_poke(self):
        CombatSystem.sword_combo(self.sharko, num_attacks=1)

    def _do_sword_combo(self):
        CombatSystem.sword_combo(self.sharko, num_attacks=3)

    def _jump_and_attack(self):
        sharko = self.sharko

        folder_view, hwnd_lv = WindowsUtils.get_desktop_interfaces(
            sharko.CLSID_ShellWindows,
            sharko.IID_IFolderView,
            sharko.SWC_DESKTOP,
            sharko.SWFO_NEEDDISPATCH,
        )
        closest, num_icons = sharko.get_closest_icons(1)
        screen_w = win32api.GetSystemMetrics(0)

        work_area_height = WindowsUtils.get_work_area_height()

        x, y = 0, 0
        if num_icons <= 3:
            replacement_shortcut = WindowsUtils.create_shortcut(hwnd_lv)
            closest = [replacement_shortcut]
            x = random.randint(350, screen_w - 350)
            y = random.randint(350, work_area_height - 350)

            pos = win32api.MAKELONG(x, y)

            win32gui.SendMessage(hwnd_lv, sharko.LVM_SETITEMPOSITION, replacement_shortcut, pos)

        item = folder_view.Item(closest[0])
        item_pos = folder_view.GetItemPosition(item)

        CombatSystem.jump_and_hit(sharko, item_pos, closest[0], 0.4, on_complete=self._inter_attack_idle)
