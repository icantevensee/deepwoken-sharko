import                          math
import                          random
import                          time

import                          threading

import                          ctypes

import                          win32api
import                          win32gui
import                          win32con
import                          win32ui
import                          winsound
from winrt.windows.ui.notifications import ToastNotificationManager

from PyQt5.QtCore       import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtGui        import QImage, QPixmap, QPainter
from PyQt5.QtWidgets    import QLabel

import uiautomation         as auto
from win11toast         import toast

from constants          import SharkoConstants
from img_utils          import ImgUtils


class ToastBridge(QObject):
    toast_captured = pyqtSignal(QImage, int, int, int, int, str)  # rgba_bytes, width, height, x, y, target_aumid


class ToastManager:
    def __init__(self, damage_callback=None):
        toast_bridge = ToastBridge()
        toast_bridge.toast_captured.connect(self.on_toast_data_received)
        self.bridge = toast_bridge
        self.active_toasts = []
        self.damage_callback = damage_callback
        self._is_deinitialized = False

    @staticmethod
    def _capture_window(hwnd, capture_full_window=True):
        rect = win32gui.GetWindowRect(hwnd)
        x1, y1, x2, y2 = rect
        w, h = x2 - x1, y2 - y1

        if capture_full_window:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

            # Extract bits while DCs are active
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            expected_size = bmpinfo['bmWidth'] * bmpinfo['bmHeight'] * 4  # RGBA = 4 bytes per pixel

            # Validate bitmap data completeness
            if bmpstr is None or len(bmpstr) < expected_size:
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)
                raise ValueError(f"Incomplete bitmap capture: got {len(bmpstr) if bmpstr else 0} bytes, expected {expected_size}")

            q_img = QImage(
                bmpstr,
                bmpinfo['bmWidth'],
                bmpinfo['bmHeight'],
                QImage.Format_ARGB32
            ).copy()

            # CLEANUP PATH A: Delete memory DCs first, then release window DC
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
        else:
            h_desktop = win32gui.GetDesktopWindow()
            desktop_dc = win32gui.GetWindowDC(h_desktop)
            mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            save_dc.BitBlt((0, 0), (w, h), mfc_dc, (x1, y1), win32con.SRCCOPY)

            # Extract bits while DCs are active
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            expected_size = bmpinfo['bmWidth'] * bmpinfo['bmHeight'] * 4  # RGBA = 4 bytes per pixel

            # Validate bitmap data completeness
            if bmpstr is None or len(bmpstr) < expected_size:
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(h_desktop, desktop_dc)
                raise ValueError(f"Incomplete bitmap capture: got {len(bmpstr) if bmpstr else 0} bytes, expected {expected_size}")

            q_img = QImage(
                bmpstr,
                bmpinfo['bmWidth'],
                bmpinfo['bmHeight'],
                QImage.Format_ARGB32
            ).copy()

            # CLEANUP PATH B: Delete memory DCs first, then release desktop DC
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(h_desktop, desktop_dc)

        return q_img, x1, y1

    def spawn_and_clone_worker(self, title, body):
        """Runs isolated inside a separate Thread. Initializes STA COM,
        fires windows-toasts, captures it, and passes graphics data via signals.
        """
        ctypes.windll.ole32.CoInitializeEx(None, SharkoConstants.COINIT_APARTMENTTHREADED)

        try:
            TARGET_AUMID = "Destroyman III"
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
                                                audio={'silent': 'true'},
                                                tag=str(int(time.time() * 10))
                                            ), daemon=True)
            toast_thread.start()

            toast_hwnd = None
            target_crop_bounds = None
            screen_w = win32api.GetSystemMetrics(0)
            timeout = 1.5
            start_time = time.time()

            while (time.time() - start_time) < timeout:
                root = auto.GetRootControl()
                for win in root.GetChildren():
                    try:
                        if win.ClassName == 'Windows.UI.Core.CoreWindow':
                            toast_hwnd = win.NativeWindowHandle
                            for el, depth in auto.WalkControl(win, includeTop=False):
                                try:
                                    if title in str(el.Name):
                                        current = el
                                        for _ in range(5):
                                            parent = current.GetParentControl()
                                            if parent:
                                                rect = parent.BoundingRectangle
                                                width = rect.right - rect.left
                                                if width >= 0.1 * screen_w and width <= 0.5 * screen_w:
                                                    target_crop_bounds = rect
                                                    break
                                            current = parent
                                        break
                                except Exception:
                                    pass
                            if target_crop_bounds:
                                break
                    except Exception:
                        pass
                if target_crop_bounds:
                    break
                time.sleep(0.05)
            if not toast_hwnd or not target_crop_bounds:
                history_manager.clear_with_id(TARGET_AUMID)
                return
            time.sleep(0.3)
            full_stack_img, win_x1, win_y1 = self._capture_window(toast_hwnd, False)
            full_stack_img2, win_x1, win_y1 = self._capture_window(toast_hwnd, True)

            local_x1 = max(0, target_crop_bounds.left - win_x1)
            local_y1 = max(0, target_crop_bounds.top - win_y1)
            local_x2 = min(full_stack_img.width(), local_x1 + target_crop_bounds.width())
            local_y2 = min(full_stack_img.height(), local_y1 + target_crop_bounds.height())

            w_final = local_x2 - local_x1
            h_final = local_y2 - local_y1

            cropped_img = full_stack_img.copy(local_x1, local_y1, w_final, h_final)
            cropped_img2 = full_stack_img2.copy(local_x1, local_y1, w_final, h_final)

            transparent_q = ImgUtils._remove_black_background_qimg(cropped_img2)

            final_masked_img = QImage(w_final, h_final, QImage.Format_ARGB32_Premultiplied)
            final_masked_img.fill(Qt.transparent)

            painter = QPainter(final_masked_img)

            painter.drawImage(0, 0, cropped_img)

            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, transparent_q)

            painter.end()

            default_x = target_crop_bounds.left
            default_y = target_crop_bounds.top

            if self.bridge is not None:
                self.bridge.toast_captured.emit(final_masked_img, w_final, h_final, default_x, default_y, TARGET_AUMID)
        finally:
            ctypes.windll.ole32.CoUninitialize()

    def on_toast_data_received(self, q_img, w, h, x, y, target_aumid):
        """Triggered on the main thread when a background worker finishes cloning."""
        pixmap = QPixmap.fromImage(q_img)

        toast_window = QLabel()
        toast_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        toast_window.setAttribute(Qt.WA_TranslucentBackground)
        toast_window.setPixmap(pixmap)
        toast_window.setGeometry(x, y, w, h)
        toast_window.show()

        self.active_toasts.append(toast_window)
        QTimer.singleShot(10, lambda: ToastNotificationManager.history.clear_with_id(target_aumid))  # wait 1 qt refresh frame before clearing the real notification
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

        pixel_speed_per_frame = 32.5
        total_frames = int(base_dist / pixel_speed_per_frame)

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
                    self.damage_callback("toast_attack")

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
        QTimer.singleShot(13, lambda: self.animate_constant_speed_frame(window_handle, toast_states, w, h))

    def cleanup_toast(self, window_handle):
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
