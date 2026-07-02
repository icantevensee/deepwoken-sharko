import                          math
import                          random
import                          time

import                          sys
import                          platform
import                          threading

import                          ctypes

import                          win32api
import                          win32gui
import                          win32ui
import                          winsound
from winrt.windows.ui.notifications import ToastNotificationManager

from PIL                import Image
from PyQt5.QtCore       import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtGui        import QImage, QPixmap
from PyQt5.QtWidgets    import QLabel
sys.coinit_flags = 2 #Get the COM threading right for pywinauto so it doesn't clash with PyQt5
from pywinauto          import Application
from win11toast         import toast

from constants          import SharkoConstants
from img_utils          import ImgUtils

try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass


class ToastBridge(QObject):
    toast_captured = pyqtSignal(bytes, int, int, int, int)


class ToastManager:
    def __init__(self, damage_callback=None):
        toast_bridge = ToastBridge()
        toast_bridge.toast_captured.connect(self.on_toast_data_received)
        self.bridge = toast_bridge
        self.active_toasts = []
        self.damage_callback = damage_callback
        self._is_deinitialized = False

    @staticmethod
    def _capture_window(hwnd):
        rect = win32gui.GetWindowRect(hwnd)
        x1, y1, x2, y2 = rect
        w, h = x2 - x1, y2 - y1

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)

        ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        return img, x1, y1

    def spawn_and_clone_worker(self, title, body):
        """Runs isolated inside a separate Thread. Initializes STA COM,
        fires windows-toasts, captures it, and passes graphics data via signals.
        """
        ctypes.windll.ole32.CoInitializeEx(None, SharkoConstants.COINIT_APARTMENTTHREADED)

        try:
            if platform.release() == "11":
                TARGET_AUMID = "Microsoft.Windows.Accessibility.Utilities"
            else:
                TARGET_AUMID = "Windows.SystemToast.Background"
            history_manager = ToastNotificationManager.history
            history_manager.clear_with_id(TARGET_AUMID)

            winsound.PlaySound("Notification.Default", winsound.SND_ALIAS | winsound.SND_ASYNC)
            toast_thread = threading.Thread(target=lambda:
                toast(
                title, 
                body,
                app_id=TARGET_AUMID,
                scenario='incomingCall',
                duration='short',
                audio={'silent': 'true'}
            ), daemon=True)
            toast_thread.start()


            time.sleep(0.3)

            toast_hwnd = None
            target_crop_bounds = None

            app = Application(backend="uia").connect(path="ShellExperienceHost.exe")
            for window in app.windows():
                if window.is_visible() and window.element_info.class_name == "Windows.UI.Core.CoreWindow":
                    toast_hwnd = window.handle
                    all_descendants = window.descendants()
                    for el in all_descendants:
                        try:
                            if title in str(el.window_text()):
                                current = el
                                for _ in range(5):
                                    parent = current.parent()
                                    if parent and (300 < parent.rectangle().width() < 500):
                                        target_crop_bounds = parent.rectangle()
                                        break
                                    current = parent
                                break
                        except Exception:
                            print("ggg")
                            pass
                    if target_crop_bounds:
                        break

            if not toast_hwnd or not target_crop_bounds:
                print("ggg")
                history_manager.clear_with_id(TARGET_AUMID)
                return

            full_stack_img, win_x1, win_y1 = self._capture_window(toast_hwnd)

            local_x1 = max(0, target_crop_bounds.left - win_x1)
            local_y1 = max(0, target_crop_bounds.top - win_y1)
            local_x2 = min(full_stack_img.width, local_x1 + target_crop_bounds.width())
            local_y2 = min(full_stack_img.height, local_y1 + target_crop_bounds.height())

            cropped_img = full_stack_img.crop((local_x1, local_y1, local_x2, local_y2))
            w_final, h_final = cropped_img.size

            transparent_img = ImgUtils._remove_black_background(cropped_img)
            rgba_bytes = transparent_img.tobytes("raw", "RGBA")

            default_x = target_crop_bounds.left
            default_y = target_crop_bounds.top

            history_manager.clear_with_id(TARGET_AUMID)

            if self.bridge is not None:
                self.bridge.toast_captured.emit(rgba_bytes, w_final, h_final, default_x, default_y)
        finally:
            ctypes.windll.ole32.CoUninitialize()

    def on_toast_data_received(self, rgba_bytes, w, h, x, y):
        """Triggered on the main thread when a background worker finishes cloning."""
        q_img = QImage(rgba_bytes, w, h, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(q_img)

        toast_window = QLabel()
        toast_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        toast_window.setAttribute(Qt.WA_TranslucentBackground)
        toast_window.setPixmap(pixmap)
        toast_window.setGeometry(x, y, w, h)
        toast_window.show()

        self.active_toasts.append(toast_window)

        self.start_constant_speed_trajectory(toast_window, x, y, w, h)

    def start_constant_speed_trajectory(self, window_handle, start_x, start_y, w, h):
        """Initializes a trajectory with true constant pixel speed and drift correction."""
        mouse_x, mouse_y = win32api.GetCursorPos()
        target_x = mouse_x - (w / 2)
        target_y = mouse_y - (h / 2)

        base_dx = target_x - start_x
        base_dy = target_y - start_y
        base_dist = math.hypot(base_dx, base_dy)
        if base_dist == 0:
            base_dist = 1.0

        perpx = -base_dy / base_dist
        perpy = base_dx / base_dist

        pixel_speed_per_frame = 25.0
        total_frames = max(5, int(base_dist / pixel_speed_per_frame))

        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        screen_diag = math.hypot(screen_w, screen_h)
        distance_ratio = min(base_dist / screen_diag, 1.0)

        curve_amp = screen_diag * (distance_ratio**2.25 * 2.25)
        curve_amp = min(curve_amp * random.uniform(0.95, 1.05), screen_diag * 0.45)

        toast_states = {
            "start_x": float(start_x),
            "start_y": float(start_y),
            "base_dx": base_dx,
            "base_dy": base_dy,
            "perpx": perpx,
            "perpy": perpy,
            "curve_dir": random.choice([-1.0, 1.0]),
            "curve_amp": curve_amp,
            "current_frame": 0,
            "total_frames": total_frames,
            "pixel_speed": pixel_speed_per_frame,
            "has_hit_mouse": False,
            "exit_vx": 0.0,
            "exit_vy": 0.0,
            "drift_x": 0.0,
            "drift_y": 0.0,
        }

        self.animate_constant_speed_frame(window_handle, toast_states, w, h)

    def animate_constant_speed_frame(self, window_handle, toast_states, w, h):
        """Calculates a clean sine arc that shifts coordinates fluidly to match live cursor movement."""
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)

        if not toast_states["has_hit_mouse"]:
            toast_states["current_frame"] += 1
            t = toast_states["current_frame"] / toast_states["total_frames"]

            if t >= 1.0:
                t = 1.0
                toast_states["has_hit_mouse"] = True
                if self.damage_callback is not None:
                    self.damage_callback()

            base_x = toast_states["start_x"] + toast_states["base_dx"] * t
            base_y = toast_states["start_y"] + toast_states["base_dy"] * t

            curve_progress = t * t
            arc_offset = math.sin(t * math.pi) * toast_states["curve_amp"] * toast_states["curve_dir"] * curve_progress
            curved_base_x = base_x + toast_states["perpx"] * arc_offset
            curved_base_y = base_y + toast_states["perpy"] * arc_offset

            mouse_x, mouse_y = win32api.GetCursorPos()
            live_target_x = mouse_x - (w / 2)
            live_target_y = mouse_y - (h / 2)

            orig_target_x = toast_states["start_x"] + toast_states["base_dx"]
            orig_target_y = toast_states["start_y"] + toast_states["base_dy"]

            total_drift_x = live_target_x - orig_target_x
            total_drift_y = live_target_y - orig_target_y

            current_drift_x = total_drift_x * t
            current_drift_y = total_drift_y * t

            next_x = curved_base_x + current_drift_x
            next_y = curved_base_y + current_drift_y

            if toast_states["current_frame"] > 1:
                toast_states["exit_vx"] = next_x - window_handle.x()
                toast_states["exit_vy"] = next_y - window_handle.y()
            else:
                toast_states["exit_vx"] = toast_states["base_dx"] / toast_states["total_frames"]
                toast_states["exit_vy"] = toast_states["base_dy"] / toast_states["total_frames"]

        else:
            current_speed = math.hypot(toast_states["exit_vx"], toast_states["exit_vy"])
            if current_speed > 0:
                ux = toast_states["exit_vx"] / current_speed
                uy = toast_states["exit_vy"] / current_speed
            else:
                ux, uy = 1.0, 0.0

            next_x = window_handle.x() + (ux * toast_states["pixel_speed"])
            next_y = window_handle.y() + (uy * toast_states["pixel_speed"])

        is_offscreen = ((next_x + w) < 0 or next_x > screen_w or (next_y + h) < 0 or next_y > screen_h)

        if is_offscreen and toast_states["has_hit_mouse"]:
            self.cleanup_toast(window_handle)
            return

        window_handle.move(int(next_x), int(next_y))
        QTimer.singleShot(10, lambda: self.animate_constant_speed_frame(window_handle, toast_states, w, h))

    def cleanup_toast(self, window_handle):
        print("gg")
        """Safely removes the window from UI memory to allow garbage collection."""
        if window_handle in self.active_toasts:
            self.active_toasts.remove(window_handle)
        window_handle.close()
        window_handle.deleteLater()

    def deinitialize(self):
        """Stops toast manager state and removes any active toast windows."""
        if self._is_deinitialized:
            return

        self._is_deinitialized = True

        self.bridge.toast_captured.disconnect(self.on_toast_data_received)
        self.bridge.deleteLater()
        self.bridge = None

        for toast_window in list(self.active_toasts):
            try:
                self.cleanup_toast(toast_window)
            except Exception:
                pass

        self.active_toasts.clear()
        self.damage_callback = None

    def trigger_toast_async(self, title, body):
        """Spawns an isolated background thread to pipeline windows_toasts securely."""
        t = threading.Thread(target=self.spawn_and_clone_worker, args=(title, body), daemon=True)
        t.start()
        