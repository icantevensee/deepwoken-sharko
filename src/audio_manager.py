"""Audio Management Module

Lazy loading engine for sfx:
- Live list of dynamic PitchedSound instances and active player streams.
- Methods for registering sound configurations while ensuring that file handles and multimedia objects are properly cleaned up when deinitialized.
"""
import                          random
import                          os

from PyQt6.QtMultimedia import  QAudioOutput, QMediaPlayer
from PyQt6.QtCore import        QObject, QUrl


class AudioManager:
    def __init__(self):
        self._sound_configs = {}
        self._loaded_sounds = {}

    def register_sound(self, name, audio_path, pitched=False, looped=False, volume=1.0):
        """Registers the configuration of a sound without loading it into ram."""
        self._sound_configs[name] = {
            "path": audio_path,
            "pitched": pitched,
            "looped": looped,
            "volume": volume
        }

    def load_sound(self, name) -> "PitchedSound":
        """Retrieves the sound instance, creating it only if it doesn't exist yet."""
        if name not in self._loaded_sounds:
            if name not in self._sound_configs:
                raise ValueError(f"Sound '{name}' has not been registered.")

            config = self._sound_configs[name]
            self._loaded_sounds[name] = PitchedSound(
                audio_path=config["path"],
                pitched=config["pitched"],
                looped=config["looped"],
                volume=config["volume"]
            )
        return self._loaded_sounds[name]

    def set_sound_volume(self, name, volume):
        """Sets the volume of a specific sound."""
        if name not in self._loaded_sounds:
            return
        sound = self._loaded_sounds[name]
        sound.set_volume(volume)

    def is_track_playing(self, name):
        """Check if a track has playing instances."""
        sound = self._loaded_sounds.get(name)
        if sound is None:
            return False
        return sound.is_playing()

    def get_sound_length(self, name):
        """Returns the duration of a registered sound in milliseconds from its instance."""
        return self.load_sound(name).sound_length

    def play(self, name, volume=1.0):
        """Helper to instantly fetch and play a sound."""
        self.load_sound(name).play(volume)

    def unload_sound(self, name):
        """Manually drops a sound from RAM if it's no longer needed."""
        if name in self._loaded_sounds:
            self._loaded_sounds[name].stop()
            del self._loaded_sounds[name]


class PitchedSound(QObject):
    def __init__(self, audio_path, pitched=False, looped=False, volume=1.0):
        super().__init__()
        self.pitched = pitched
        self.looped = looped
        self.volume = max(0.0, min(1.0, volume))
        self.media_url = QUrl.fromLocalFile(audio_path)
        self.active_players = []

        file_size_bytes = os.path.getsize(audio_path)
        self.sound_length = int((file_size_bytes * 8 / 320000) * 1000)

    def play(self, volume=1.0):
        """Plays the sound effect."""
        self.volume = max(0.0, min(1.0, volume))
        if self.volume == 0:
            return

        # QMediaPlayer in PyQt6 uses a separate QAudioOutput for volume control.
        player = QMediaPlayer(None)
        audio_output = QAudioOutput()
        audio_output.setVolume(self.volume)
        player.setAudioOutput(audio_output)

        player.setSource(self.media_url)
        if self.looped:
            player.setLoops(QMediaPlayer.Loops.Infinite)

        if self.pitched:
            player.setPlaybackRate(random.uniform(0.95, 1.05))
        else:
            player.setPlaybackRate(1.0)

        player.playbackStateChanged.connect(self._handle_state_change)
        self.active_players.append((player, audio_output))
        player.play()

    def set_volume(self, volume):
        """Sets the volume of all of that sound."""
        self.volume = max(0.0, min(1.0, volume))
        qt_volume = self.volume
        for player, audio_output in self.active_players:
            if audio_output is not None:
                audio_output.setVolume(qt_volume)

    def stop(self):
        """Instantly terminates all overlapping streams and clears RAM."""
        for player, audio_output in list(self.active_players):
            player.stop()
            player.deleteLater()
            if audio_output is not None:
                audio_output.deleteLater()
        self.active_players.clear()

    def _handle_state_change(self, state):
        """Safe extraction tracking that deletes C++ objects natively."""
        player = self.sender()
        if state == QMediaPlayer.PlaybackState.StoppedState:
            for pair in list(self.active_players):
                if pair[0] is player:
                    self.active_players.remove(pair)
                    player.deleteLater()
                    if pair[1] is not None:
                        pair[1].deleteLater()
                    break

    def is_playing(self):
        """True if active players."""
        return len(self.active_players) > 0
