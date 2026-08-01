import time

from PyQt5.QtCore import QObject, QTimer

from windows_interactive.windows_utils import WindowsUtils


class MouseStunManager(QObject):
    """Manages active mouse stun conditions using dedicated single-shot timers."""

    def __init__(self):
        super().__init__()
        self.original_speed = WindowsUtils.get_windows_mouse_speed()
        self.active_stuns = []

    def stun(self, duration_ms, speed):
        """Schedules a new stun"""
        speed = max(1, min(int(speed), 20))
        duration_ms = max(0, float(duration_ms))

        if duration_ms <= 0:
            return

        current_time = time.time()
        duration_seconds = duration_ms / 1000.0
        new_end_time = current_time + duration_seconds

        # Check for overlapping stuns with the same speed that end earlier
        for stun_item in self.active_stuns[:]:
            if stun_item['speed'] == speed and stun_item['end_time'] <= new_end_time:
                print(f"overlap, extending {speed} to {new_end_time}")
                stun_item['timer'].stop()
                stun_item['timer'].deleteLater()
                self.active_stuns.remove(stun_item)

        timer = QTimer(self)
        timer.setSingleShot(True)

        stun_record = {
            'speed': speed,
            'end_time': new_end_time,
            'timer': timer
        }

        timer.timeout.connect(lambda: self._on_stun_timeout(stun_record))
        self.active_stuns.append(stun_record)
        timer.start(int(duration_ms))
        self._apply_highest_priority_stun()

    def _on_stun_timeout(self, stun_record):
        """Triggered when a stun duration expires"""
        if stun_record in self.active_stuns:
            stun_record['timer'].deleteLater()
            self.active_stuns.remove(stun_record)
            # print(f"timeout, the stun with speed {stun_record['speed']} expired")

        self._apply_highest_priority_stun()

    def _apply_highest_priority_stun(self):
        """Looks through active stuns and applies the lowest mouse speed"""
        if len(self.active_stuns) == 0:
            current_speed = WindowsUtils.get_windows_mouse_speed()
            if current_speed != self.original_speed:
                # print(f"restore, all stuns finished, restoring speed to {self.original_speed}")
                WindowsUtils.set_windows_mouse_speed(self.original_speed)
            return

        # Lowest speed is highest priority
        highest_priority_stun = min(self.active_stuns, key=lambda x: x['speed'])
        target_speed = highest_priority_stun['speed']

        current_speed = WindowsUtils.get_windows_mouse_speed()
        if current_speed != target_speed:
            # print(f"apply, setting mouse speed to: {target_speed}")
            WindowsUtils.set_windows_mouse_speed(target_speed)

    def deinitialize(self):
        """Cleans up timers and restores the original mouse speed"""
        for stun_item in self.active_stuns:
            try:
                stun_item['timer'].stop()
                stun_item['timer'].deleteLater()
            except Exception:
                pass
        self.active_stuns.clear()

        current_speed = WindowsUtils.get_windows_mouse_speed()
        if current_speed != self.original_speed:
            # print(f"cleanup, restoring mouse speed to original: {self.original_speed}")
            WindowsUtils.set_windows_mouse_speed(self.original_speed)
        self.deleteLater()
