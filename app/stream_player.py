"""ONLINE playback: ffmpeg decodes the HTTP stream to PCM and
sounddevice sends it to the speakers. No downloads or waiting."""
from __future__ import annotations
import os
import subprocess
import threading
import time

SR = 44100
CH = 2
SAMPW = 2  # int16
BPS = SR * CH * SAMPW  # bytes per second
BUF_MAX = BPS * 30  # ~30 s buffer


def ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p
    except Exception:
        pass
    return None


def available() -> bool:
    if not ffmpeg_exe():
        return False
    try:
        import sounddevice  # noqa
        return True
    except Exception:
        return False


class StreamPlayer:
    """Online player with seek/pause/volume. Fully non-blocking."""

    def __init__(self):
        self.url = ""
        self.volume = 0.7
        self.playing = False
        self.finished = False
        self.failed = False
        self.failed_msg = ""
        self.duration = 0.0
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._eof = False
        self._running = False
        self._fed_total = 0
        self._pos_base = 0.0
        self._t0 = 0.0
        self._proc: subprocess.Popen | None = None
        self._stream = None
        self._feeder: threading.Thread | None = None

    # ---------- control ----------
    def play(self, url: str, start: float = 0.0, volume: float = 70,
             duration: float = 0.0) -> None:
        self.stop()
        exe = ffmpeg_exe()
        if not exe:
            raise RuntimeError("No ffmpeg")
        import sounddevice as sd
        self.url = url
        self.volume = max(0, min(100, float(volume))) / 100.0
        self.duration = float(duration or 0)
        self.finished = False
        self.failed = False
        self.failed_msg = ""
        self._eof = False
        self._fed_total = 0
        with self._lock:
            self._buf.clear()
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin",
               "-reconnect", "1", "-reconnect_streamed", "1",
               "-reconnect_delay_max", "5"]
        if start > 0.5:
            cmd += ["-ss", f"{start:.1f}"]
        cmd += ["-i", url, "-vn", "-ac", str(CH), "-ar", str(SR),
                "-f", "s16le", "-acodec", "pcm_s16le", "-"]
        try:
            # CREATE_NO_WINDOW so streaming audio neither opens nor
            # flashes consoles on Windows.
            _nowin = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL,
                                          creationflags=_nowin)
        except Exception as e:
            raise RuntimeError(f"Could not launch ffmpeg: {e}")
        self._running = True
        self._feeder = threading.Thread(target=self._feed_loop, daemon=True)
        self._feeder.start()
        # Wait briefly for data to arrive (fails fast if the URL is bad)
        t_end = time.time() + 12
        while time.time() < t_end:
            with self._lock:
                n = len(self._buf)
            if n > BPS // 4:  # >0.25 s
                break
            if self._eof and n == 0:
                break
            time.sleep(0.05)
        with self._lock:
            n = len(self._buf)
        if n == 0:
            err = "no stream data"
            try:
                if self._proc and self._proc.poll() not in (None, 0):
                    err = f"ffmpeg exited with code {self._proc.poll()}"
            except Exception:
                pass
            self.stop()
            self.failed = True
            self.failed_msg = err
            raise RuntimeError(f"Stream with no data ({err})")
        try:
            self._stream = sd.OutputStream(samplerate=SR, channels=CH,
                                           dtype="int16", blocksize=4096,
                                           callback=self._callback)
            self._stream.start()
        except Exception as e:
            self.stop()
            self.failed = True
            self.failed_msg = str(e)[:150]
            raise RuntimeError(f"No audio device: {e}")
        self._pos_base = float(start)
        self._t0 = time.monotonic()
        self.playing = True

    def _feed_loop(self) -> None:
        try:
            while self._running and self._proc and self._proc.stdout:
                with self._lock:
                    buffered = len(self._buf)
                if buffered >= BUF_MAX:
                    time.sleep(0.1)
                    continue
                try:
                    chunk = self._proc.stdout.read(32768)
                except Exception:
                    break
                if not chunk:
                    break
                with self._lock:
                    self._buf += chunk
                    self._fed_total += len(chunk)
        finally:
            with self._lock:
                self._eof = True

    def _callback(self, outdata, frames, time_info, status) -> None:
        import sounddevice as sd
        need = frames * CH * SAMPW
        with self._lock:
            chunk = bytes(self._buf[:need])
            del self._buf[:need]
            eof = self._eof
            empty = len(self._buf) == 0
        if len(chunk) < need:
            chunk = chunk + b"\x00" * (need - len(chunk))
            if eof and empty:
                # Real end of track
                try:
                    outdata[:] = b"\x00" * need
                except Exception:
                    pass
                self.finished = True
                self.playing = False
                raise sd.CallbackStop()
        try:
            import numpy as np
            arr = np.frombuffer(bytearray(chunk), dtype=np.int16).astype(np.float32)
            arr *= self.volume
            outdata[:] = arr.astype(np.int16).reshape(-1, CH)
        except Exception:
            # Without numpy: fixed volume, copy directly
            try:
                outdata[:] = chunk
            except Exception:
                pass

    def pause(self) -> float:
        pos = self.get_pos()
        self._shutdown_audio(keep_pos=pos)
        self.playing = False
        self._paused_at = pos
        return pos

    def resume(self) -> None:
        start = getattr(self, "_paused_at", 0.0)
        url, vol, dur = self.url, self.volume, self.duration
        self.play(url, start=start, volume=vol * 100, duration=dur)

    def seek(self, seconds: float) -> None:
        seconds = max(0.0, min(float(seconds), self.duration or float("inf")))
        was_playing = self.playing
        url, vol, dur = self.url, self.volume, self.duration
        self._shutdown_audio(keep_pos=seconds)
        self.play(url, start=seconds, volume=vol * 100, duration=dur)
        if not was_playing:
            self.pause()

    def stop(self) -> None:
        self._shutdown_audio(keep_pos=0.0)
        self.playing = False
        self.finished = False

    def _shutdown_audio(self, keep_pos: float = 0.0) -> None:
        self._running = False
        try:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
        finally:
            self._stream = None
        try:
            if self._proc is not None:
                try:
                    self._proc.kill()
                except Exception:
                    pass
                try:
                    self._proc.wait(timeout=3)
                except Exception:
                    pass
        finally:
            self._proc = None
        with self._lock:
            self._buf.clear()
            self._eof = False
        self._paused_at = float(keep_pos)

    def set_volume(self, v: float) -> None:
        self.volume = max(0, min(100, float(v))) / 100.0

    def get_pos(self) -> float:
        if self.playing:
            return max(0.0, self._pos_base + (time.monotonic() - self._t0))
        return float(getattr(self, "_paused_at", 0.0))
