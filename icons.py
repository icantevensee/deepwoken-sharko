import math
import time
import threading
import pythoncom
from win32com.shell import shellcon
import win32gui
import win32api
from constants import SharkoConstants
from shortcut_utils import DesktopUtils


throw_lock = threading.Lock()


class IconManager:
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

