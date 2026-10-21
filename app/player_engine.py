"""Playback engine: ONLINE streaming (ffmpeg+sounddevice) with
fallback to download+pygame. Queue + loop/shuffle."""
from __future__ import annotations
import os
import time
import random
import threading
from typing import Callable


class PlayerEngine:
    LOOP_OFF, LOOP_ALL, LOOP_ONE = "off", "all", "one"

    def __init__(self, youtube_client=None, volume: float = 70,
                 loop_mode: str = "off", shuffle: bool = False,
                 on_track_change: Callable | None = None,
                 on_state_change: Callable | None = None):
        self.client = youtube_client
        self.queue: list[dict] = []
        self.index: int = -1
        self.loop_mode = loop_mode if loop_mode in ("off", "all", "one") else "off"
        self.shuffle = bool(shuffle)
        self._shuffle_order: list[int] = []
        self.volume = max(0.0, min(100.0, float(volume)))
        self.state = "stopped"  # stopped|loading|playing|paused
        self.current: dict | None = None
        self.duration_sec: int = 0
        self._paused_pos: float = 0.0
        self._play_start: float = 0.0
        self._backend = "stream"
        self._active = "stream"  # stream | file (backend in use now)
        self._mixer_ok = False
        self._stream_ok: bool | None = None
        self._streamer = None
        self.prefer_stream = True  # False = forzar descarga (fallback manual)
        self._load_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._play_lock = threading.Lock()  # Serializa play_at para evitar
                                            # doble stream / velocidad x2
        self._play_gen = 0  # only the latest requested track may start audio
        self.on_track_change = on_track_change
        self.on_state_change = on_state_change
        self.on_queue_end = None  # Callback when queue ends, for continuation
        self.last_error = ""
        self._init_backend()

    # ---------- backend ----------
    def _init_backend(self) -> None:
        try:
            import vlc  # noqa
            try:
                inst = vlc.Instance()
                if inst is not None:
                    self._vlc_available = True
                else:
                    self._vlc_available = False
            except Exception:
                self._vlc_available = False
        except Exception:
            self._vlc_available = False
        try:
            import pygame
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(self.volume / 100.0)
            self._mixer_ok = True
            self._backend = "pygame"
        except Exception as e:
            self.last_error = f"Audio: {e}"
            self._mixer_ok = False

    def _stream_available(self) -> bool:
        if self._stream_ok is None:
            try:
                from .stream_player import available
                self._stream_ok = bool(available())
            except Exception:
                self._stream_ok = False
        return bool(self._stream_ok)

    def _get_streamer(self):
        if self._streamer is None:
            from .stream_player import StreamPlayer
            self._streamer = StreamPlayer()
        return self._streamer

    def _emit_state(self) -> None:
        try:
            if self.on_state_change:
                self.on_state_change(self.state, self.current)
        except Exception:
            pass

    def _emit_track(self) -> None:
        try:
            if self.on_track_change:
                self.on_track_change(self.current)
        except Exception:
            pass

    def _set_state(self, s: str) -> None:
        self.state = s
        self._emit_state()

    # ---------- queue ----------
    def set_queue(self, tracks: list[dict], start: int = 0, autoplay: bool = True) -> None:
        self.stop()
        self.queue = list(tracks or [])
        self.index = -1
        self._rebuild_shuffle()
        if self.queue:
            pos = max(0, min(start, len(self.queue) - 1))
            if autoplay:
                self.play_at(pos)
            else:
                self.index = pos
                self.current = self.queue[pos]
                self._emit_track()

    def _rebuild_shuffle(self) -> None:
        self._shuffle_order = list(range(len(self.queue)))
        if self.shuffle:
            random.shuffle(self._shuffle_order)

    def set_shuffle(self, on: bool) -> None:
        self.shuffle = bool(on)
        self._rebuild_shuffle()

    def cycle_loop(self) -> str:
        order = ["off", "all", "one"]
        self.loop_mode = order[(order.index(self.loop_mode) + 1) % 3]
        return self.loop_mode

    def queue_add(self, track: dict) -> None:
        """Add a track to the end of the queue WITHOUT rebuilding shuffle."""
        self.queue.append(track)

    def queue_insert(self, track: dict, pos: int) -> None:
        """Insert a track at a specific position in the queue."""
        pos = max(0, min(pos, len(self.queue)))
        self.queue.insert(pos, track)
        # If inserted before current track, shift current index forward
        if pos <= self.index:
            self.index += 1

    def queue_remove(self, pos: int) -> None:
        if 0 <= pos < len(self.queue):
            del self.queue[pos]
            if pos < self.index:
                self.index -= 1
            elif pos == self.index:
                self.stop()

    def queue_move(self, from_pos: int, to_pos: int) -> None:
        """Move a track from from_pos to to_pos in the queue."""
        if not (0 <= from_pos < len(self.queue) and 0 <= to_pos < len(self.queue)):
            return
        track = self.queue.pop(from_pos)
        self.queue.insert(to_pos, track)
        # Adjust current index based on movement
        if self.index == from_pos:
            self.index = to_pos
        elif from_pos < self.index <= to_pos:
            self.index -= 1
        elif to_pos <= self.index < from_pos:
            self.index += 1

    def queue_reorder(self, new_order: list) -> None:
        """Reorder the entire queue by a list of new positions.
        
        new_order[i] = old position that should go to position i.
        """
        if len(new_order) != len(self.queue):
            return
        old_queue = list(self.queue)
        self.queue = [old_queue[old_pos] for old_pos in new_order]
        # Recalculate current index based on the current track's videoId
        if self.current and self.current.get("videoId"):
            vid = self.current["videoId"]
            for i, t in enumerate(self.queue):
                if t.get("videoId") == vid:
                    self.index = i
                    break

    def queue_clear(self) -> None:
        self.stop()
        self.queue = []
        self.index = -1

    # ---------- playback ----------
    def play_at(self, pos: int) -> None:
        if not self.queue or not (0 <= pos < len(self.queue)):
            return
        # Serializa para evitar que dos streams suenen a la vez (x2 velocidad)
        # al hacer skip rápido. Si ya hay un play_at en curso, este espera.
        with self._play_lock:
            if not self.queue or not (0 <= pos < len(self.queue)):
                return
            self.stop()
            # Never block the UI thread waiting for a previous load. The new
            # load thread waits for the old one before opening audio, and a
            # generation number guarantees that only the LAST click can play.
            self._play_gen = int(getattr(self, "_play_gen", 0) or 0) + 1
            gen = self._play_gen
            old_thread = self._load_thread
            self.index = pos
            track = self.queue[pos]
            self.current = dict(track)
            self.duration_sec = int(track.get("duration_sec") or 0)
            self._emit_track()
            self._set_state("loading")
            self._stop_event.clear()
            self._load_thread = threading.Thread(
                target=self._load_and_play,
                args=(dict(track), gen, old_thread), daemon=True)
            self._load_thread.start()

    def _load_and_play(self, track: dict, gen: int = None,
                       previous: threading.Thread = None) -> None:
        vid = track.get("videoId", "")
        try:
            def _current() -> bool:
                return ((gen is None or gen == self._play_gen)
                        and not self._stop_event.is_set())

            def _wait_previous() -> bool:
                # Wait for the older loader to finish BEFORE opening audio.
                # This is done in this background thread (never in the UI),
                # so fast skips cannot overlap two streams (x2 speed).
                try:
                    if (previous is not None and previous.is_alive()
                            and previous is not threading.current_thread()):
                        previous.join(timeout=20.0)
                except Exception:
                    pass
                return _current()

            if not _current():
                return
            if self.client is None:
                raise RuntimeError("No YouTube client")
            # 1) Get stream info (audio URL + duration).
            info: dict = {}
            info_err = ""
            try:
                info = self.client.get_stream_info(vid)
                self.duration_sec = int(info.get("duration_sec") or self.duration_sec or 0)
                if self.current is not None:
                    self.current["duration_sec"] = self.duration_sec
                    if not self.current.get("thumbnail"):
                        self.current["thumbnail"] = info.get("thumbnail", "")
            except Exception as e:
                info_err = str(e)[:200]
                self.last_error = f"info: {info_err}"
                info = {}
            if not _current():
                return
            audio_url = (info or {}).get("audio_url", "")
            # 2) ONLINE streaming (without downloading) - only if we got a URL
            if audio_url and self.prefer_stream and self._stream_available():
                try:
                    if not _wait_previous():
                        return
                    st = self._get_streamer()
                    st.play(audio_url, start=0.0, volume=self.volume,
                            duration=float(self.duration_sec or 0))
                    if not _current():
                        st.stop()
                        return
                    self._active = "stream"
                    self._backend = "stream"
                    self._paused_pos = 0.0
                    self._set_state("playing")
                    self._start_monitor()
                    return
                except Exception as e:
                    self.last_error = f"stream: {str(e)[:150]}"
                    if not _current():
                        return
                    # Fall through to download fallback
            # 3) Fallback: download to cache + pygame.
            local = None
            for attempt in range(5):
                if not _current():
                    return
                try:
                    self.last_error = f"Descargando intento {attempt + 1}/5..."
                    local = self.client.download_audio(vid)
                    if local and os.path.exists(local) and os.path.getsize(local) > 1024:
                        break
                except Exception as e:
                    self.last_error = f"Intento {attempt + 1}/5 falló: {str(e)[:100]}"
                    local = None
                    time.sleep(2.0)
            if local and _current():
                if not _wait_previous():
                    return
                self._play_file(local)
                if not _current():
                    self.stop()
                return
            # If we get here, every download attempt failed.
            self.last_error = f"download: all 5 attempts failed. Last error: {self.last_error}"
            if self.current is not None:
                self.current = dict(self.current)
                self.current["error"] = self.last_error
            if not _current():
                return
            # Auto-skip to the next track only after ALL attempts exhausted.
            try:
                nxt = self._next_index()
            except Exception:
                nxt = None
            if nxt is not None and nxt != self.index:
                failed = self.index
                self._set_state("stopped")
                time.sleep(0.5)
                if _current() and self.index == failed:
                    self.play_at(nxt)
                    return
            self._set_state("stopped")
        except Exception as e:
            self.last_error = str(e)[:300]
            if self.current is not None:
                self.current = dict(self.current)
                self.current["error"] = self.last_error
            if not _current():
                return
            # Last resort auto-skip
            try:
                nxt = self._next_index()
            except Exception:
                nxt = None
            if nxt is not None and nxt != self.index:
                failed = self.index
                self._set_state("stopped")
                time.sleep(0.5)
                if _current() and self.index == failed:
                    self.play_at(nxt)
                    return
            self._set_state("stopped")

    def _play_file(self, local: str) -> None:
        if not self._mixer_ok:
            self._init_backend()
        import pygame
        pygame.mixer.music.load(local)
        pygame.mixer.music.set_volume(self.volume / 100.0)
        pygame.mixer.music.play()
        self._active = "file"
        self._backend = "pygame"
        self._play_start = time.time()
        self._paused_pos = 0.0
        self._set_state("playing")
        self._start_monitor()

    def _start_monitor(self) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while True:
            time.sleep(0.5)
            if self.state in ("stopped",):
                return
            if self.state != "playing":
                continue
            ended = False
            try:
                if self._active == "stream" and self._streamer is not None:
                    ended = bool(getattr(self._streamer, "finished", False))
                else:
                    import pygame
                    ended = not pygame.mixer.music.get_busy()
            except Exception:
                return
            if ended and self.state == "playing" and not self._stop_event.is_set():
                # Track ended
                self._on_track_end()
                return

    def _on_track_end(self) -> None:
        if self.loop_mode == "one" and self.index >= 0:
            self.play_at(self.index)
            return
        nxt = self._next_index()
        if nxt is None:
            # Queue ended: try callback for continuation (e.g. recommendations)
            if self.on_queue_end:
                try:
                    if self.on_queue_end():
                        # Callback added tracks to the queue. Find the first
                        # new track that wasn't in the queue before.
                        # The first new track should be right after the old
                        # queue length. Since queue_add just appends, the new
                        # tracks start at len(self.queue) - len(added).
                        # But we don't know how many were added. Let's find
                        # the first track that is different from what was
                        # playing. We'll play at index + 1 since that's where
                        # the first new track should be after the last one.
                        self.play_at(self.index + 1)
                        return
                except Exception:
                    pass
            self._set_state("stopped")
            return
        self.play_at(nxt)

    def _next_index(self) -> int | None:
        if not self.queue:
            return None
        if self.shuffle and self._shuffle_order:
            try:
                i = self._shuffle_order.index(self.index)
                if i + 1 < len(self._shuffle_order):
                    return self._shuffle_order[i + 1]
                return self._shuffle_order[0] if self.loop_mode == "all" else None
            except ValueError:
                return self._shuffle_order[0] if self._shuffle_order else None
        else:
            if self.index + 1 < len(self.queue):
                return self.index + 1
            return 0 if self.loop_mode == "all" else None

    def _prev_index(self) -> int | None:
        if not self.queue:
            return None
        # If it has been playing for >3s, restart the current track
        if self.get_position() > 3:
            return self.index
        if self.shuffle and self._shuffle_order:
            try:
                i = self._shuffle_order.index(self.index)
                if i - 1 >= 0:
                    return self._shuffle_order[i - 1]
                return self._shuffle_order[-1] if self.loop_mode == "all" else self.index
            except ValueError:
                return self.index
        else:
            if self.index - 1 >= 0:
                return self.index - 1
            return 0 if self.loop_mode == "all" else self.index

    def next(self) -> None:
        nxt = self._next_index()
        if nxt is None:
            self.stop()
            return
        # If it is the same and there is no loop, restart
        if nxt == self.index and self.loop_mode == "off" and self.get_position() <= 3:
            return
        self.play_at(nxt)

    def prev(self) -> None:
        prv = self._prev_index()
        if prv is None:
            return
        self.play_at(prv)

    def toggle(self) -> None:
        if self.state == "playing":
            self.pause()
        elif self.state == "paused":
            self.resume()
        elif self.current is not None and self.index >= 0:
            self.play_at(self.index)
        elif self.queue:
            self.play_at(0)

    def pause(self) -> None:
        try:
            if self.state != "playing":
                return
            if self._active == "stream" and self._streamer is not None:
                self._paused_pos = float(self._streamer.pause())
            else:
                import pygame
                self._paused_pos = self.get_position()
                pygame.mixer.music.pause()
            self._set_state("paused")
        except Exception:
            pass

    def resume(self) -> None:
        try:
            if self.state != "paused":
                return
            if self._active == "stream" and self._streamer is not None:
                self._streamer.resume()
            else:
                import pygame
                pygame.mixer.music.unpause()
                self._play_start = time.time() - self._paused_pos
            self._set_state("playing")
            self._start_monitor()
        except Exception:
            pass

    def stop(self, load_only: bool = False) -> None:
        try:
            self._stop_event.set()
            try:
                if self._streamer is not None:
                    self._streamer.stop()
            except Exception:
                pass
            import pygame
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        except Exception:
            pass
        if not load_only:
            self._set_state("stopped")

    def set_volume(self, v: float) -> None:
        self.volume = round(max(0.0, min(100.0, float(v))), 1)
        try:
            if self._streamer is not None:
                self._streamer.set_volume(self.volume)
        except Exception:
            pass
        try:
            import pygame
            pygame.mixer.music.set_volume(self.volume / 100.0)
        except Exception:
            pass

    def get_position(self) -> float:
        if self.state == "paused":
            return float(self._paused_pos)
        if self.state != "playing":
            return 0.0
        if self._active == "stream" and self._streamer is not None:
            try:
                return max(0.0, float(self._streamer.get_pos()))
            except Exception:
                pass
        try:
            import pygame
            ms = pygame.mixer.music.get_pos()
            if ms is not None and ms >= 0:
                return ms / 1000.0
        except Exception:
            pass
        return max(0.0, time.time() - self._play_start)

    def seek(self, seconds: float) -> bool:
        """Real seek in streaming; best-effort for files."""
        if self.current is None or self.index < 0:
            return False
        seconds = max(0.0, min(float(seconds), float(self.duration_sec or 0)))
        if self._active == "stream" and self._streamer is not None:
            try:
                self._streamer.seek(seconds)
                self._paused_pos = seconds
                self._set_state("playing" if self.state != "paused" else "paused")
                self._start_monitor()
                return True
            except Exception:
                return False
        try:
            import pygame
            try:
                pygame.mixer.music.play(start=seconds)
            except Exception:
                try:
                    pygame.mixer.music.play()
                    pygame.mixer.music.set_pos(seconds)
                except Exception:
                    return False
            self._play_start = time.time() - seconds
            self._paused_pos = seconds
            if self.state == "paused":
                pygame.mixer.music.pause()
            else:
                self._set_state("playing")
                self._start_monitor()
            return True
        except Exception:
            return False

    def cleanup_cache(self, max_mb: int = 500) -> None:
        try:
            if self.client is None:
                return
            d = getattr(self.client, "cache_dir", "cache")
            if not os.path.isdir(d):
                return
            files = []
            for n in os.listdir(d):
                p = os.path.join(d, n)
                if os.path.isfile(p) and not n.endswith((".txt", ".json")):
                    try:
                        files.append((os.path.getmtime(p), os.path.getsize(p), p))
                    except Exception:
                        pass
            files.sort()
            total = sum(s for _, s, _ in files)
            limit = max_mb * 1024 * 1024
            for _, s, p in files:
                if total <= limit:
                    break
                try:
                    os.remove(p)
                    total -= s
                except Exception:
                    pass
        except Exception:
            pass
