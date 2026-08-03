import time

import threading

from PyQt6.QtCore import QObject, QTimer

from windows_interactive.windows_utils import WindowsUtils


class MouseSpeedWorker(threading.Thread):
    """A single, reusable background thread that uses events"""
    def __init__(self, original_speed):
        super().__init__(daemon=True)
        self.target_speed = None
        self.original_speed = original_speed
        self._event = threading.Event()
        self._running = True

    def change_speed(self, speed):
        """Updates the target speed and wakes up the thread immediately."""
        self.target_speed = speed
        self._event.set()

    def run(self):
        while self._running:
            self._event.wait()
            self._event.clear()

            if not self._running:
                break

            speed_to_apply = self.target_speed

            if speed_to_apply is not None:
                WindowsUtils.set_windows_mouse_speed(speed_to_apply)

        WindowsUtils.set_windows_mouse_speed(self.original_speed)

    def stop(self):
        self._running = False
        self._event.set()


class MouseStunManager(QObject):
    """Manages active mouse stun conditions without queues or heavy thread allocation."""

    def __init__(self):
        super().__init__()
        self.original_speed = WindowsUtils.get_windows_mouse_speed()
        self.current_applied_speed = self.original_speed
        self.active_stuns = []

        self.worker = MouseSpeedWorker(self.original_speed)
        self.worker.start()

    def stun(self, duration_ms, speed):
        """Schedules a new stun."""
        speed = max(1, min(int(speed), 20))
        duration_ms = max(0, float(duration_ms))

        if duration_ms <= 0:
            return

        current_time = time.time()
        new_end_time = current_time + (duration_ms / 1000.0)

        # Filter out overlapping stuns
        surviving_stuns = []
        for stun_item in self.active_stuns:
            if stun_item['speed'] == speed and stun_item['end_time'] <= new_end_time:
                stun_item['timer'].stop()
                stun_item['timer'].deleteLater()
            else:
                surviving_stuns.append(stun_item)
        self.active_stuns = surviving_stuns

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
        """Triggered when a stun duration expires."""
        if stun_record in self.active_stuns:
            stun_record['timer'].deleteLater()
            self.active_stuns.remove(stun_record)

        self._apply_highest_priority_stun()

    def _apply_highest_priority_stun(self):
        """Evaluates active stuns and passes targets to the worker event loop"""
        if not self.active_stuns:
            if self.current_applied_speed != self.original_speed:
                self.current_applied_speed = self.original_speed
                self.worker.change_speed(self.original_speed)
            return

        highest_priority_stun = min(self.active_stuns, key=lambda x: x['speed'])
        target_speed = highest_priority_stun['speed']

        if self.current_applied_speed != target_speed:
            self.current_applied_speed = target_speed
            self.worker.change_speed(target_speed)

    def deinitialize(self):
        """Cleans up active timers and guarantees mouse speed restoration"""
        for stun_item in self.active_stuns:
            try:
                stun_item['timer'].stop()
            except Exception:
                pass
            stun_item['timer'].deleteLater()
        self.active_stuns.clear()

        # Restore original system speed
        self.worker.stop()
        self.deleteLater()
