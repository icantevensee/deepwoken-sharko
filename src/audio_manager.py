"""Audio Management Module

Lazy loading engine for sfx:
- Live list of dynamic PitchedSound instances and active player streams.
- Methods for registering sound configurations while ensuring that file handles and multimedia objects are properly cleaned up when deinitialized.
"""
import                          random
import                          os

from PyQt5.QtMultimedia import  QMediaPlayer, QMediaContent
from PyQt5.QtCore import        QObject, QUrl


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
        self.active_players = set()

        file_size_bytes = os.path.getsize(audio_path)
        self.sound_length = int((file_size_bytes * 8 / 320000) * 1000)

    def play(self, volume=1.0):
        """Plays the sound effect."""
        self.volume = max(0.0, min(1.0, volume))
        if self.volume == 0:
            return

        player = QMediaPlayer(None, QMediaPlayer.LowLatency)

        if self.looped:
            from PyQt5.QtMultimedia import QMediaPlaylist
            playlist = QMediaPlaylist(player)
            playlist.addMedia(QMediaContent(self.media_url))
            playlist.setPlaybackMode(QMediaPlaylist.Loop)
            player.setPlaylist(playlist)
        else:
            player.setMedia(QMediaContent(self.media_url))

        player.setVolume(int(self.volume * 100))

        if self.pitched:
            player.setPlaybackRate(random.uniform(0.95, 1.05))
        else:
            player.setPlaybackRate(1.0)

        player.stateChanged.connect(self._handle_state_change)
        self.active_players.add(player)
        player.play()

    def stop(self):
        """Instantly terminates all overlapping streams and clears RAM."""
        for player in list(self.active_players):
            player.stop()
            player.deleteLater()
        self.active_players.clear()

    def _handle_state_change(self, state):
        """Safe extraction tracking that deletes C++ objects natively."""
        player = self.sender()
        if state == QMediaPlayer.StoppedState and player in self.active_players:
            self.active_players.remove(player)
            player.deleteLater()

    def is_playing(self):
        """True if active players."""
        return len(self.active_players) > 0
