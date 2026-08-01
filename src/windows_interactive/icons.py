"""
Icon Manager Module

Manages desktop icon manipulation and throwing animations.
Provides functionality to move desktop icons in trajectories
with collision detection and hit registration.
"""

import                                         math
import                                         time

import                                         threading

import                                         pythoncom
import                                         win32api
import                                         win32con
import                                         win32gui
from win32com.shell                     import shellcon  # type: ignore

from boss_battle                        import CombatSystem
from constants                          import SharkoConstants
from windows_interactive.windows_utils  import WindowsUtils

from PyQt5.QtCore import QTimer

throw_lock = threading.Lock()


class IconManager:
    """Manages desktop icon throwing and trajectory animation."""

    def _throw_worker(self, index, target_pos, speed_factor, name):
        """Worker thread for icon-throw trajectory in a background thread, includes:
        - COM initialization.
        - Icon lookup and verification to make sure icon index has not changed since the last animation step.
        - Animation over time split into a arced throw section, and then a bobbing section once the target position has been achieved."""
        pythoncom.CoInitialize()
        with throw_lock:
            if name in self.thrown_icons:
                return
            self.thrown_icons.add(name)
        try:

            folder_view, hwnd_lv = WindowsUtils.get_desktop_interfaces(
                SharkoConstants.CLSID_ShellWindows,
                SharkoConstants.IID_IFolderView,
                SharkoConstants.SWC_DESKTOP,
                SharkoConstants.SWFO_NEEDDISPATCH,
            )
            item = None
            try:
                item = folder_view.Item(index)
            except Exception:
                with throw_lock:
                    self.thrown_icons.discard(name)
                return
            item_name = name
            start_pos = folder_view.GetItemPosition(item)
            original_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)

            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)

            desktop_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            desktop_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

            mousex, mousey = target_pos

            listview__mousex = int(mousex) - desktop_left
            listview__mousey = int(mousey) - desktop_top

            x0, y0 = start_pos

            spacing = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMSPACING, 0, 0)
            cell_h = (spacing >> 16) & 0xFFFF

            end_x = listview__mousex - cell_h**1.2 * 0.10
            end_y = listview__mousey - cell_h**1.2 * 0.10

            dx = end_x - x0
            dy = end_y - y0
            over_x = x0 + dx * (1 + (0.1 / speed_factor))
            over_y = y0 + dy * (1 + (0.1 / speed_factor))

            over_x = WindowsUtils.clamp(over_x, 0, screen_w - desktop_left - cell_h // 2)
            over_y = WindowsUtils.clamp(over_y, 0, screen_h - desktop_top - cell_h)

            target_x = WindowsUtils.clamp(end_x, 0, screen_w - desktop_left - cell_h // 2)
            target_y = WindowsUtils.clamp(end_y, 0, screen_h - desktop_top - cell_h)

            ctrl_x = (x0 + target_x) // 2
            ctrl_y = min(y0, over_y) - 300

            steps = math.floor(250 * speed_factor)
            duration = 2 * speed_factor
            dt = duration / steps
            hit_registered = False

            for i in range(steps + 1):
                current_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
                if not WindowsUtils.icon_exists(hwnd_lv, index) or current_count != original_count:
                    original_count = current_count
                    index = WindowsUtils.get_actual_index(hwnd_lv, item_name)
                    if index == -1:
                        with throw_lock:
                            self.thrown_icons.discard(name)
                        return

                t = i / steps
                omt = 1 - t

                x = (omt**2) * x0 + 2 * omt * t * ctrl_x + (t**2) * target_x
                y = (omt**2) * y0 + 2 * omt * t * ctrl_y + (t**2) * target_y

                mx, my = win32api.GetCursorPos()

                if not hit_registered and math.dist((x + desktop_left + cell_h // 2, y + desktop_top + cell_h // 2), (mx, my)) < cell_h // 2:
                    hit_registered = True
                    self.input_emitter.damage_signal.emit("icon_attack")

                pos = win32api.MAKELONG(int(x), int(y))
                win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, index, pos)
                time.sleep(dt)

            bob_steps = 45

            dist = math.dist((over_x, over_y), (target_x, target_y))
            dip_amount = WindowsUtils.clamp(dist * 0.15, 5, 80)

            for i in range(bob_steps + 1):
                current_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
                if not WindowsUtils.icon_exists(hwnd_lv, index) or current_count != original_count:
                    original_count = current_count
                    index = WindowsUtils.get_actual_index(hwnd_lv, item_name)
                    if index == -1:
                        with throw_lock:
                            self.thrown_icons.discard(name)
                        return

                t = (i / bob_steps) ** 0.8
                fall = (1 - t) ** 2
                base_y = over_y + (target_y - over_y) * fall

                dip = dip_amount * (math.sin(t * math.pi)) ** 2

                y = base_y + dip
                x = target_x + (over_x - target_x) * t

                x = WindowsUtils.clamp(x, 0, screen_w - desktop_left - cell_h // 2)
                y = WindowsUtils.clamp(y, 0, screen_h - desktop_top - cell_h)

                pos = win32api.MAKELONG(int(x), int(y))
                win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_SETITEMPOSITION, index, pos)
                time.sleep(0.01)

        finally:
            with throw_lock:
                self.thrown_icons.discard(name)
            pythoncom.CoUninitialize()

    def throw_shortcut(self, index, target_pos, speed_factor, name):
        """Spawns a daemon thread that runs _throw_worker and forwards parameters."""
        thread = threading.Thread(
            target=self._throw_worker,
            args=(index, target_pos, speed_factor, name),
            daemon=True,
        )
        thread.start()

    @staticmethod
    def get_closest_icons(n):
        """Computes the indices of the desktop icons closest to the current mouse position using COM and list view geometry."""
        pythoncom.CoInitialize()
        try:
            desktop_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            desktop_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

            folder_view, _ = WindowsUtils.get_desktop_interfaces(
                SharkoConstants.CLSID_ShellWindows,
                SharkoConstants.IID_IFolderView,
                SharkoConstants.SWC_DESKTOP,
                SharkoConstants.SWFO_NEEDDISPATCH,
            )
            mouse = win32api.GetCursorPos()
            items_len = folder_view.ItemCount(shellcon.SVGIO_ALLVIEW)
            dists = []

            for i in range(items_len):
                item = folder_view.Item(i)
                pos = folder_view.GetItemPosition(item)
                local_x = pos[0]
                local_y = pos[1]
                main_monitor_x = local_x + desktop_left
                main_monitor_y = local_y + desktop_top

                d = math.dist((main_monitor_x, main_monitor_y), mouse)
                dists.append((d, i))

            dists.sort()
            return [idx for _, idx in dists[:n]], len(dists)

        finally:
            pythoncom.CoUninitialize()
