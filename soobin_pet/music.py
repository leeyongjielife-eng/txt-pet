"""
music.py — Music.app (iTunes) controller via AppleScript
"""
import subprocess

from AppKit import NSRunningApplication


class MusicController:

    def _run(self, script: str) -> str:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True
        )
        return result.stdout.strip()

    def open_music(self):
        subprocess.run(['open', '-a', 'Music'])

    def play(self):
        self._run('tell application "Music" to play')

    def pause(self):
        self._run('tell application "Music" to pause')

    def toggle(self):
        if self.is_playing():
            self.pause()
            return False
        else:
            self.play()
            return True

    def next_track(self):
        self._run('tell application "Music" to next track')

    def prev_track(self):
        self._run('tell application "Music" to previous track')

    def is_playing(self) -> bool:
        running = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
            'com.apple.Music'
        )
        if not running:
            return False
        state = self._run('tell application "Music" to get player state')
        return state == 'playing'

    def current_track(self) -> str:
        try:
            name = self._run(
                'tell application "Music" to get name of current track'
            )
            artist = self._run(
                'tell application "Music" to get artist of current track'
            )
            return f"{name} — {artist}" if artist else name
        except Exception:
            return ""

    def current_artist(self) -> str:
        try:
            return self._run(
                'tell application "Music" to get artist of current track'
            )
        except Exception:
            return ""

    def current_track_name(self) -> str:
        try:
            return self._run(
                'tell application "Music" to get name of current track'
            )
        except Exception:
            return ""
