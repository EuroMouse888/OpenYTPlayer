"""Last.fm API client (scrobbles + corrections). No new dependencies.

Setup (2 minutes, once): https://www.last.fm/api/account/create creates an
API key + shared secret. Paste them in the app (Settings > Last.fm), press
Connect, allow access in the browser, done. The session key is stored in
config/lastfm.json and never expires until revoked.

Offline behavior: scrobbles are queued in config/lastfm.json (max 200) and
flushed on the next successful call.
"""
from __future__ import annotations
import hashlib
import json
import os
import time

API_ROOT = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth/"


def _norm_name(s: str) -> str:
    """Comparable form of a name: no accents, no punctuation, no extra
    words like "(feat. X)" or "- Remaster".

    IMPORTANT: letters of EVERY script are kept. Stripping to [a-z0-9] made
    japanese/chinese/korean titles normalise to the empty string, so those
    tracks never matched and the counter silently showed nothing.
    """
    import re
    import unicodedata
    # NFKC also folds full-width forms (ＡＢＣ -> ABC, ！ -> !)
    t = unicodedata.normalize("NFKC", str(s or ""))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.lower()
    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", t)
    # keep letters/digits of any script, turn everything else into spaces
    t = "".join(ch if ch.isalnum() else " " for ch in t)
    t = re.sub(r"\b(feat|ft|featuring|with|remaster(ed)?|radio|"
               r"single|album|version|edit|live|mono|stereo|deluxe|"
               r"bonus|explicit)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _same_name(a: str, b: str) -> bool:
    """True when two names are the same track for our purposes.

    Strict on purpose: a loose matcher made the counter show ANOTHER song's
    plays. Everything (brackets, "feat. X", "- Remastered", ...) is already
    stripped by _norm_name, so what is left must really line up.
    """
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    return na == nb


def _as_int(v) -> int:
    """Last.fm sends counts as strings ("286"); be tolerant, never crash."""
    try:
        if isinstance(v, bool):
            return -1
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v or "").strip()
        if not s or s.lower() in ("null", "none", "-1"):
            return -1
        return int(float(s))
    except Exception:
        return -1
STATE_PATH = os.path.join("config", "lastfm.json")


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sign_call(params: dict, secret: str) -> str:
    """Last.fm api_sig: md5 of sorted key+value pairs + secret."""
    try:
        raw = "".join(f"{k}{params[k]}" for k in sorted(params))
        return _md5(raw + (secret or ""))
    except Exception:
        return ""


class LastFMClient:
    def __init__(self, state_path: str = STATE_PATH):
        self.state_path = state_path
        self.api_key = ""
        self.api_secret = ""
        self.session_key = ""
        self.username = ""
        self.scrobble_enabled = True
        self.edits_path = ""
        self.songmap_path = ""
        self.pending: list[dict] = []  # queued scrobbles while offline
        self.last_error = ""
        self.load()

    # ---------- persistence ----------
    def load(self) -> None:
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    d = json.load(f) or {}
                self.api_key = str(d.get("api_key", "") or "")
                self.api_secret = str(d.get("api_secret", "") or "")
                self.session_key = str(d.get("session_key", "") or "")
                self.username = str(d.get("username", "") or "")
                self.scrobble_enabled = bool(d.get("scrobble_enabled", True))
                self.edits_path = str(d.get("edits_path", "") or "")
                self.songmap_path = str(d.get("songmap_path", "") or "")
                pend = d.get("pending") or []
                self.pending = [p for p in pend if isinstance(p, dict)][:200]
        except Exception:
            pass

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.state_path)) or ".",
                        exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump({"api_key": self.api_key, "api_secret": self.api_secret,
                           "session_key": self.session_key, "username": self.username,
                           "scrobble_enabled": self.scrobble_enabled,
                           "edits_path": self.edits_path,
                           "songmap_path": getattr(self, "songmap_path", ""),
                           "pending": list(self.pending or [])[:200]},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @property
    def linked(self) -> bool:
        return bool(self.session_key)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    # ---------- low-level ----------
    def _post(self, params: dict, signed: bool = True) -> dict | None:
        try:
            import requests
        except Exception as e:
            self.last_error = f"requests missing: {e}"
            return None
        try:
            p = dict(params or {})
            p["api_key"] = self.api_key
            if signed:
                p["api_sig"] = sign_call(p, self.api_secret)
            p["format"] = "json"
            r = requests.post(API_ROOT, data=p, timeout=20)
            r.raise_for_status()
            d = r.json() if callable(getattr(r, "json", None)) else json.loads(r.text)
            if isinstance(d, dict) and "error" in d:
                self.last_error = f"Last.fm {d.get('error')}: {d.get('message', '')}"
                return None
            return d if isinstance(d, dict) else {}
        except Exception as e:
            self.last_error = str(e)[:200]
            return None

    def _get(self, params: dict) -> dict | None:
        try:
            import requests
        except Exception as e:
            self.last_error = f"requests missing: {e}"
            return None
        try:
            p = dict(params or {})
            p["api_key"] = self.api_key
            p["format"] = "json"
            r = requests.get(API_ROOT, params=p, timeout=20)
            r.raise_for_status()
            d = r.json() if callable(getattr(r, "json", None)) else json.loads(r.text)
            if isinstance(d, dict) and "error" in d:
                self.last_error = f"Last.fm {d.get('error')}: {d.get('message', '')}"
                return None
            return d if isinstance(d, dict) else {}
        except Exception as e:
            self.last_error = str(e)[:200]
            return None

    # ---------- auth (desktop flow, no password) ----------
    def get_token(self) -> str:
        d = self._get({"method": "auth.getToken"})
        tok = str((d or {}).get("token", "") or "")
        if not tok and not self.last_error:
            self.last_error = "No token returned (check API key)."
        return tok

    def auth_url(self, token: str) -> str:
        return f"{AUTH_URL}?api_key={self.api_key}&token={token}"

    def get_session(self, token: str) -> bool:
        d = self._post({"method": "auth.getSession", "token": token or ""})
        try:
            sess = (d or {}).get("session") or {}
            key = str(sess.get("key", "") or "")
            name = str(sess.get("name", "") or "")
        except Exception:
            key, name = "", ""
        if not key:
            if not self.last_error:
                self.last_error = "Allow access in the browser first, then retry."
            return False
        self.session_key = key
        self.username = name
        self.save()
        return True

    def unlink(self) -> None:
        self.session_key = ""
        self.username = ""
        self.save()

    # ---------- scrobbling ----------
    def update_now_playing(self, artist: str, track: str,
                            album: str = "", duration: str = "") -> bool:
        if not (self.linked and self.scrobble_enabled):
            return False
        if not artist or not track:
            return False
        p = {"method": "track.updateNowPlaying", "sk": self.session_key,
             "artist": artist, "track": track}
        if album:
            p["album"] = album
        if duration:
            p["duration"] = str(duration)
        ok = self._post(p) is not None
        if ok:
            self._flush_pending()
        return ok

    def scrobble(self, artist: str, track: str, timestamp: int,
                 album: str = "") -> bool:
        if not artist or not track:
            return False
        entry = {"artist": artist, "track": track,
                 "timestamp": int(timestamp or time.time())}
        if album:
            entry["album"] = album
        if not (self.linked and self.scrobble_enabled):
            return False
        p = {"method": "track.scrobble", "sk": self.session_key,
             "artist": artist, "track[0]": track,
             "timestamp[0]": str(entry["timestamp"])}
        if album:
            p["album[0]"] = album
        ok = self._post(p) is not None
        if not ok:
            try:
                self.pending.append(entry)
                self.pending = self.pending[-200:]
                self.save()
            except Exception:
                pass
            return False
        self._flush_pending()
        return True

    def _flush_pending(self) -> int:
        """Send queued scrobbles (oldest first). Returns sent count."""
        if not (self.linked and self.pending):
            return 0
        sent = 0
        rest: list[dict] = []
        for e in list(self.pending):
            p = {"method": "track.scrobble", "sk": self.session_key,
                 "artist": e.get("artist", ""), "track[0]": e.get("track", ""),
                 "timestamp[0]": str(e.get("timestamp", int(time.time())))}
            if e.get("album"):
                p["album[0]"] = e["album"]
            if self._post(p) is not None:
                sent += 1
            else:
                rest.append(e)
                break  # still offline: keep order, retry later
        try:
            self.pending = rest[-200:]
            self.save()
        except Exception:
            pass
        return sent

    # ---------- corrections / metadata ----------
    # Version of the playcount cache. v4 adds NFKC + non-latin scripts to the
    # name matcher: v2/v3 stored "-1" for every japanese/chinese title, so
    # those counts have to be asked again.
    _PC_CACHE_VERSION = 4

    def playcount(self, artist: str, track: str) -> int:
        """How many times YOU played this track on Last.fm (-1 = unknown).

        -1 means "Last.fm does not know this track for you": the UI then shows
        nothing instead of inventing a number.

        Cached on disk (cache/lastfm_counts.json) so scrolling a list does
        not hammer the API.
        """
        artist, track = str(artist or "").strip(), str(track or "").strip()
        if not (self.linked and artist and track):
            return -1
        key = f"{artist.lower()}|{track.lower()}"
        try:
            if not hasattr(self, "_pc_cache"):
                self._pc_cache = {}
                self._pc_loaded = False
            if not self._pc_loaded:
                self._pc_loaded = True
                try:
                    import json as _js
                    import os as _os
                    self._pc_path = _os.path.join("cache", "lastfm_counts.json")
                    if _os.path.exists(self._pc_path):
                        with open(self._pc_path, "r", encoding="utf-8") as f:
                            raw = _js.load(f) or {}
                        # Discard cache written by an older version (which may
                        # contain the GLOBAL playcount instead of userplaycount).
                        if raw.get("__version") != self._PC_CACHE_VERSION:
                            self._pc_cache = {}
                        else:
                            self._pc_cache = {
                                k: v for k, v in raw.items()
                                if k != "__version" and isinstance(v, dict)
                            }
                except Exception:
                    self._pc_cache = {}
            hit = self._pc_cache.get(key)
            if isinstance(hit, dict):
                import time as _t
                age = _t.time() - float(hit.get("ts", 0) or 0)
                if age < 86400 * 30:
                    return _as_int(hit.get("n", -1))
        except Exception:
            pass
        n = -1
        # Last.fm ONLY returns `userplaycount` when the request authenticates
        # with the session key. Omitting `sk` is what made every row show 0.
        attempts = [
            (artist, track, "0"),   # exactly what we store (no autocorrect)
            (artist, track, "1"),   # exact + autocorrect
            ("", track, "1"),       # track only + autocorrect
        ]
        for a, t, ac in attempts:
            params = {"method": "track.getInfo", "track": t,
                      "autocorrect": ac, "sk": self.session_key}
            if a:
                params["artist"] = a
            try:
                d = self._get(params)
            except Exception:
                continue
            tr = (d or {}).get("track") or {}
            if not tr:
                continue
            got_a = str((tr.get("artist") or {}).get("name", "") or "")
            got_t = str(tr.get("name", "") or "")
            if not _same_name(got_t, t):
                continue          # Last.fm matched another song: ignore it
            if a and not _same_name(got_a, a):
                continue          # another artist: ignore it
            # userplaycount = times YOU played it. NEVER use `playcount`
            # (that is the GLOBAL number from every Last.fm user).
            n = _as_int(tr.get("userplaycount", -1))
            break
        try:
            import json as _js
            import time as _t
            self._pc_cache[key] = {"n": n, "ts": _t.time()}
            self._pc_cache["__version"] = self._PC_CACHE_VERSION
            import os as _os
            _os.makedirs("cache", exist_ok=True)
            with open(self._pc_path, "w", encoding="utf-8") as f:
                _js.dump(self._pc_cache, f, ensure_ascii=False)
        except Exception:
            pass
        return n

    def track_get_info(self, artist: str, track: str,
                       autocorrect: bool = True) -> dict:
        """Corrected {artist, track, album, image} or {}."""
        if not (self.configured and artist and track):
            return {}
        d = self._get({"method": "track.getInfo", "artist": artist,
                       "track": track,
                       "autocorrect": "1" if autocorrect else "0"})
        try:
            t = (d or {}).get("track") or {}
            out = {"artist": str((t.get("artist") or {}).get("name", "") or artist),
                   "track": str(t.get("name", "") or track),
                   "album": str((t.get("album") or {}).get("title", "") or "")}
            try:
                imgs = t.get("image") or []
                big = [i.get("#text", "") for i in imgs
                       if isinstance(i, dict) and i.get("#text")]
                out["image"] = big[-1] if big else ""
            except Exception:
                out["image"] = ""
            return out
        except Exception:
            return {}
