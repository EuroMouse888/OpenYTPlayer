"""YouTube client: ytmusicapi (authenticated with cookies) + yt-dlp (streams/search)."""
from __future__ import annotations
import os
import time
import json
import threading
from typing import Any

from . import cookies_util

import re


def extract_playlist_id(text: str) -> str:
    m = re.search(r"[?&]list=([A-Za-z0-9_-]+)", text or "")
    if m:
        return m.group(1)
    m = re.fullmatch(r"[A-Za-z0-9_-]{10,}", (text or "").strip())
    return m.group(0) if m else ""


def extract_video_id(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", t)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", t)
    if m:
        return m.group(1)
    m = re.search(r"/shorts/([A-Za-z0-9_-]{6,})", t)
    if m:
        return m.group(1)
    m = re.fullmatch(r"[A-Za-z0-9_-]{11}", t)
    return m.group(0) if m else ""


class _SilentLogger:
    """Avoids yt-dlp ERROR spam on console (internal retries
    with another player_client usually succeed; the real error arrives via exception)."""
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class YouTubeClient:
    # YouTube player clients to try (android avoids the typical
    # "The page needs to be reloaded" of the web client).
    PLAYER_CLIENTS = ["android", "tv_embedded", "web", "tv"]

    def _base_opts(self, **extra) -> dict:
        opts: dict = {"quiet": True, "no_warnings": True,
                      "logger": _SilentLogger(),
                      "socket_timeout": 20, "retries": 1,
                      "extractor_args": {"youtube": {"player_client": list(self.PLAYER_CLIENTS)}}}
        opts.update(extra)
        return opts

    def _with_cookies(self, opts: dict) -> dict:
        if self.use_cookies and os.path.exists(self.netscape_path):
            opts = dict(opts)
            opts["cookiefile"] = self.netscape_path
        return opts

    def _extract_info_fallback(self, url, base_opts: dict, download: bool = False,
                                 cookies_first: bool = False):
        """Tries with and without cookies. For VIDEOS: without cookies first (broken
        /expired cookies break public videos with 'The page needs to be
        reloaded'). For PLAYLISTS: with cookies first (private ones need them)."""
        import yt_dlp
        order = (True, False) if cookies_first else (False, True)
        last_err: Exception | None = None
        for use_ck in order:
            opts = self._with_cookies(base_opts) if use_ck else base_opts
            if use_ck and "cookiefile" not in opts:
                continue  # no cookies to try
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=download)
            except Exception as e:
                last_err = e
                continue
        raise last_err if last_err else RuntimeError("Extraction failed")

    def _download_with_fallback(self, url, base_opts: dict):
        """Downloads trying without cookies first and with cookies after."""
        import yt_dlp
        last_err: Exception | None = None
        for use_ck in (False, True):
            opts = self._with_cookies(base_opts) if use_ck else base_opts
            if use_ck and "cookiefile" not in opts:
                continue
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.extract_info(url, download=True)
                    return
            except Exception as e:
                last_err = e
                continue
        raise last_err if last_err else RuntimeError("Download failed")
    def __init__(self, cookies_json_path: str = "cookiesYT.json",
                 cache_dir: str = "cache", use_cookies: bool = True,
                 session_source: str = "archivo", browser: str = "chrome",
                 use_account: bool = True):
        """use_account=False = pure guest: no cookies, no OAuth, no account.

        Tests/diagnostics MUST use this: an authenticated client writes its
        queries into the real account's YouTube Music history.
        """
        self.cookies_json_path = cookies_json_path
        self.cache_dir = cache_dir
        self.use_cookies = use_cookies and use_account
        self.use_account = use_account
        self.session_source = session_source or "archivo"  # file | browser
        self.browser = (browser or "chrome").lower()
        self.session_source_used = "archivo"
        self._last_heal = 0.0
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs("config", exist_ok=True)
        self.oauth_path = os.path.join("config", "oauth.json")
        self.oauth_creds_path = os.path.join("config", "oauth_client.json")
        self.cookies: list[dict] = []
        self.cookie_header: str = ""
        self.netscape_path = os.path.join(cache_dir, "cookies.txt")
        self.auth_method = "none"  # oauth | cookies | none
        self.auth_path = os.path.join(cache_dir, "browser.json")
        self.ytmusic = None
        self.authenticated = False
        self.account_label = "Guest (no session)"
        self.last_error = ""
        self._stream_cache: dict[str, dict] = {}
        self._video_cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load_cookies()
        self._init_ytmusic()

    # ---------- cookies ----------
    def _read_navegador(self, full: bool = False) -> list[dict]:
        """Reads browser session. Fast: real profile (fails if it is open).
        Full: + silent automation profile (always works)."""
        from . import google_login as _gl
        if full:
            try:
                cookies = _gl.read_stored_session(self.browser)
                if _gl.login_detected(cookies):
                    return cookies
            except Exception:
                pass
        from . import browser_cookies
        cookies = browser_cookies.extract_youtube_cookies(self.browser)
        if not _gl.login_detected(cookies):
            raise RuntimeError(f"Your {self.browser} has no YouTube session.")
        return cookies

    def _apply_navegador_cookies(self, cookies: list[dict]) -> None:
        from . import cookies_util
        self.cookies = cookies
        self.cookie_header = cookies_util.cookies_to_header_value(cookies)
        self.session_source_used = f"navegador:{self.browser}"
        cookies_util.cookies_to_netscape_file(cookies, self.netscape_path)
        try:
            cookies_util.build_ytmusicapi_auth_file(cookies, self.auth_path)
        except Exception:
            pass

    def _load_cookies(self) -> None:
        try:
            if not getattr(self, "use_account", True):
                # Guest mode: do not read any cookie store (browser or file).
                return
            # Preferred source: browser (live session, refreshes itself)
            if self.session_source == "navegador":
                try:
                    self._apply_navegador_cookies(self._read_navegador(full=False))
                    return
                except Exception as e:
                    self.last_error = f"browser: {str(e)[:200]}"
                    # Fall back to cached file (auto-heal fixes it
                    # in the background with the automation profile)
            if self.use_cookies and os.path.exists(self.cookies_json_path):
                self.cookies = cookies_util.read_cookies_json_tolerant(self.cookies_json_path)
                self.cookie_header = cookies_util.cookies_to_header_value(self.cookies)
                self.session_source_used = "archivo"
                if self.cookies:
                    cookies_util.cookies_to_netscape_file(self.cookies, self.netscape_path)
                    try:
                        cookies_util.build_ytmusicapi_auth_file(self.cookies, self.auth_path)
                    except Exception:
                        pass
        except Exception as e:
            self.last_error = f"Cookies: {e}"

    def reload_cookies(self, path: str | None = None) -> bool:
        if path:
            self.cookies_json_path = path
        self.authenticated = False
        self.auth_method = "none"
        self.ytmusic = None
        self._lib_cache = None
        self._load_cookies()
        self._init_ytmusic()
        return self.authenticated

    def import_login_cookies(self, cookies: list[dict]) -> bool:
        """Saves cookies from direct login (with backup) and reloads."""
        import json as _json
        import shutil as _sh
        try:
            if os.path.exists(self.cookies_json_path):
                try:
                    _sh.copy2(self.cookies_json_path, self.cookies_json_path + ".bak")
                except Exception:
                    pass
            with open(self.cookies_json_path, "w", encoding="utf-8") as f:
                _json.dump(cookies, f, ensure_ascii=False, indent=2)
            self._last_heal = 0.0
            return self.reload_cookies()
        except Exception as e:
            self.last_error = f"import: {e}"
            return False

    # ---------- OAuth (permanent session, does not expire) ----------
    def _load_oauth_creds(self):
        """OAuthCredentials from config/oauth_client.json, or None."""
        try:
            from ytmusicapi import OAuthCredentials
            if not os.path.exists(self.oauth_creds_path):
                return None
            with open(self.oauth_creds_path, "r", encoding="utf-8") as f:
                dc = json.load(f)
            cid, sec = (dc.get("client_id", "") or "").strip(), (dc.get("client_secret", "") or "").strip()
            if not cid or not sec:
                return None
            return OAuthCredentials(cid, sec)
        except Exception:
            return None

    def save_oauth_creds(self, client_id: str, client_secret: str) -> None:
        with open(self.oauth_creds_path, "w", encoding="utf-8") as f:
            json.dump({"client_id": client_id.strip(), "client_secret": client_secret.strip()}, f, indent=2)

    def get_oauth_creds_saved(self) -> tuple[str, str]:
        try:
            with open(self.oauth_creds_path, "r", encoding="utf-8") as f:
                dc = json.load(f)
            return dc.get("client_id", ""), dc.get("client_secret", "")
        except Exception:
            return "", ""

    def oauth_linked(self) -> bool:
        return bool(os.path.exists(self.oauth_path) and os.path.getsize(self.oauth_path) > 10)

    def disconnect_oauth(self) -> None:
        try:
            if os.path.exists(self.oauth_path):
                os.remove(self.oauth_path)
        except Exception:
            pass
        self._lib_cache = None
        self.reload_cookies()

    def finish_oauth_device(self, creds, device_code: str):
        """Completes the device flow: exchanges the code for tokens and saves them.
        Returns (token | None, message)."""
        try:
            raw = creds.token_from_code(device_code)
        except Exception as e:
            return None, f"Could not exchange the code: {str(e)[:200]}"
        if not isinstance(raw, dict) or "access_token" not in raw or "refresh_token" not in raw:
            detail = ""
            try:
                detail = str(raw.get("error", "")) or str(raw)[:120]
            except Exception:
                pass
            return None, ("Not yet authorized in the browser (or code expired). "
                          f"Authorize and press again. [{detail}]")
        try:
            from ytmusicapi.auth.oauth.token import RefreshingToken
            from pathlib import Path
            ref = RefreshingToken(
                credentials=creds,
                access_token=raw["access_token"],
                refresh_token=raw["refresh_token"],
                scope=raw.get("scope", ""),
                token_type=raw.get("token_type", "Bearer"),
                expires_in=raw.get("refresh_token_expires_in", raw.get("expires_in", 3600)))
            ref.update(raw)
            ref.local_cache = Path(self.oauth_path)
            try:
                ref.as_auth()
            except Exception:
                pass
            # Force writing the file with the full token
            try:
                with open(self.oauth_path, "w", encoding="utf-8") as f:
                    f.write(ref.as_json())
            except Exception:
                pass
            self._lib_cache = None
            self.reload_cookies()
            if self.authenticated and self.auth_method == "oauth":
                return ref, "Account permanently linked ✔"
            # Token saved (valid for future startups); immediate
            # verification may fail due to network. Still returned.
            return ref, (f"Token saved but unverified: {self.last_error[:150]}. "
                         "Retry 'I already authorized it' or restart the app.")
        except Exception as e:
            return None, f"Error saving token: {str(e)[:200]}"

    # ---------- ytmusicapi ----------
    def _init_ytmusic(self) -> None:
        try:
            from ytmusicapi import YTMusic
            if not getattr(self, "use_account", True):
                # Guest mode: never sign in, never touch the account history.
                self.ytmusic = YTMusic()
                self.authenticated = False
                self.auth_method = "none"
                self.account_label = "Guest (test mode, not signed in)"
                return
            # 0) Permanent OAuth (does not expire, auto-refreshes the access token)
            creds = self._load_oauth_creds()
            if creds is not None and self.oauth_linked():
                try:
                    self.ytmusic = YTMusic(auth=self.oauth_path, oauth_credentials=creds)
                    try:
                        info = self.ytmusic.get_account_info()
                        name = str((info or {}).get("accountName", "")) if isinstance(info, dict) else ""
                        self.authenticated = True
                        self.auth_method = "oauth"
                        self.account_label = f"Permanently connected{f' as {name}' if name else ''} (OAuth)"
                        return
                    except Exception as e:
                        self.last_error = f"oauth: {str(e)[:200]}"
                        # The refresh token may be revoked: fall back to cookies
                except Exception as e:
                    self.last_error = f"oauth init: {str(e)[:200]}"
            # 1) Try with generated browser.json
            if os.path.exists(self.auth_path) and os.path.getsize(self.auth_path) > 10:
                try:
                    self.ytmusic = YTMusic(auth=self.auth_path)
                    # Real verification: get_account_info distinguishes valid session
                    # from expired cookies (expired ones fail here).
                    try:
                        info = self.ytmusic.get_account_info()
                        name = ""
                        try:
                            name = str(info.get("accountName", "")) if isinstance(info, dict) else ""
                        except Exception:
                            pass
                        self.authenticated = True
                        self.auth_method = "cookies"
                        self.account_label = f"Connected{f' as {name}' if name else ''} ({len(self.cookies)} cookies)"
                        self._lib_cache = None
                        return
                    except Exception as e:
                        msg = str(e)[:200]
                        # Header format OK (BROWSER) but session rejected:
                        # expired cookies or no YT Music account.
                        if self.cookie_header:
                            self.authenticated = False
                            self.auth_method = "none"
                            self.account_label = "Session expired (check cookiesYT.json)"
                            self.last_error = f"session: {msg}"
                            return
                except Exception as e:
                    self.last_error = f"ytmusic auth: {e}"
            # 2) No auth
            self.ytmusic = YTMusic()
            self.auth_method = "none"
            if self.cookie_header and not self.authenticated:
                self.account_label = "Session expired (check cookiesYT.json)"
        except Exception as e:
            self.last_error = f"ytmusic init: {e}"
            self.ytmusic = None

    # ---------- library ----------
    def _maybe_heal_session(self) -> bool:
        """If the source is the browser, re-extracts FRESH cookies and rebuilds
        the session (heals expired sessions without any user action)."""
        if getattr(self, "session_source", "archivo") != "navegador":
            return False
        if time.time() - getattr(self, "_last_heal", 0) < 120:
            return self.authenticated
        self._last_heal = time.time()
        try:
            self._apply_navegador_cookies(self._read_navegador(full=True))
            self._lib_cache = None
            self._init_ytmusic()
        except Exception as e:
            self.last_error = f"auto-session: {str(e)[:150]}"
        return self.authenticated

    def _auth_call(self, fn, *args, **kwargs):
        """Calls the authenticated API with smart retry (heals the session
        if the source is the browser; otherwise, a simple retry)."""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            self.last_error = f"api: {str(e)[:200]}"
        if self._maybe_heal_session():
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                self.last_error = f"api: {str(e)[:200]}"
                return None
        try:
            time.sleep(2)
            return fn(*args, **kwargs)
        except Exception as e:
            self.last_error = f"api: {str(e)[:200]}"
            return None

    def get_library_playlists(self, limit: int = 50, _use_cache: bool = True) -> list[dict]:
        """Returns [{'id','title','count','thumbnails'}]."""
        now = time.time()
        cached = getattr(self, "_lib_cache", None)
        if _use_cache and cached and now - cached[0] < 90 and cached[1]:
            return cached[1][:limit]
        if self.ytmusic is not None:
            raw = self._auth_call(self.ytmusic.get_library_playlists, limit=limit) or []
            out = []
            for p in raw:
                if not isinstance(p, dict):
                    continue
                out.append({
                    "id": p.get("playlistId", ""),
                    "title": p.get("title", "Untitled"),
                    "count": p.get("count", ""),
                    "thumbnails": p.get("thumbnails", []),
                    "source": "libreria",
                })
            if out:
                self._lib_cache = (now, out)
                return out
        return []

    def get_liked_songs(self, limit: int = 100) -> list[dict]:
        if self.ytmusic is not None:
            data = self._auth_call(self.ytmusic.get_liked_songs, limit=limit)
            if isinstance(data, dict):
                tracks = data.get("tracks", []) or []
                out = [self._norm_track(t) for t in tracks if isinstance(t, dict)]
                if out:
                    return out
        return []

    # ---------- escritura en playlists ----------
    def add_to_playlist(self, playlist_id: str, video_ids: list[str]) -> bool:
        """Adds songs to a YouTube Music playlist. Requires session."""
        if self.ytmusic is None or not self.authenticated:
            self.last_error = "No session: cannot save to YouTube playlists"
            return False
        vids = [v for v in (video_ids or []) if v]
        if not playlist_id or not vids:
            return False
        try:
            self.ytmusic.add_playlist_items(playlist_id, vids)
            return True
        except Exception as e:
            self.last_error = f"guardar: {e}"
            return False

    def create_playlist(self, title: str, video_ids: list[str] | None = None,
                        description: str = "", private: bool = True) -> str:
        """Creates a playlist on YouTube Music. Returns the ID or ''."""
        if self.ytmusic is None or not self.authenticated:
            self.last_error = "No session: cannot create YouTube playlists"
            return ""
        try:
            pid = self.ytmusic.create_playlist(
                title, description,
                privacy_status="PRIVATE" if private else "PUBLIC",
                video_ids=[v for v in (video_ids or []) if v] or None)
            return str(pid or "")
        except Exception as e:
            self.last_error = f"create playlist: {e}"
            return ""

    def like_song(self, video_id: str, like: bool = True) -> bool:
        """Like / unlike on YouTube Music. Requires session."""
        if self.ytmusic is None or not self.authenticated or not video_id:
            return False
        try:
            from ytmusicapi.models.content.enums import LikeStatus
            self.ytmusic.rate_song(
                video_id, LikeStatus.LIKE if like else LikeStatus.INDIFFERENT)
            return True
        except Exception as e:
            self.last_error = f"like: {e}"
            return False

    def dislike_song(self, video_id: str, dislike: bool = True) -> bool:
        """Dislike on YouTube Music. Requires session."""
        if self.ytmusic is None or not self.authenticated or not video_id:
            self.last_error = "No session"
            return False
        try:
            from ytmusicapi.models.content.enums import LikeStatus
            self.ytmusic.rate_song(
                video_id, LikeStatus.DISLIKE if dislike else LikeStatus.INDIFFERENT)
            return True
        except Exception as e:
            self.last_error = f"dislike: {e}"
            return False

    # ---------- full YT Music options (right-click menu) ----------
    def get_watch_tracks(self, video_id: str, radio: bool = False,
                         limit: int = 25) -> list[dict]:
        """Playback queue / radio from YT Music for a video.

        radio=False -> 'up next' (normal watch playlist).
        radio=True  -> radio (endless mix that changes each time).
        """
        if self.ytmusic is None or not video_id:
            return []
        try:
            data = self._auth_call(
                self.ytmusic.get_watch_playlist, video_id,
                limit=int(limit or 25), radio=bool(radio)) or {}
        except Exception as e:
            self.last_error = f"watch: {e}"
            return []
        tracks = (data or {}).get("tracks", []) or []
        out = [self._norm_track(t) for t in tracks
               if isinstance(t, dict) and t.get("videoId")]
        return [t for t in out if t.get("videoId")]

    def start_radio(self, video_id: str, limit: int = 25) -> list[dict]:
        """YT Music radio from a song (always varies)."""
        return self.get_watch_tracks(video_id, radio=True, limit=limit)

    def get_up_next(self, video_id: str, limit: int = 25) -> list[dict]:
        """YT Music 'Up next' for a video."""
        return self.get_watch_tracks(video_id, radio=False, limit=limit)

    def get_song_related(self, video_id: str, limit: int = 20) -> list[dict]:
        """Songs related to a video."""
        if self.ytmusic is None or not video_id:
            return []
        try:
            data = self._auth_call(self.ytmusic.get_song_related, video_id) or []
            # get_song_related returns a list of dicts with 'contents' per section
            out: list[dict] = []
            for entry in (data if isinstance(data, list) else []):
                if not isinstance(entry, dict):
                    continue
                for c in (entry.get("contents") or []):
                    if isinstance(c, dict) and c.get("videoId"):
                        out.append(self._norm_track(c))
            return [t for t in out if t.get("videoId")][: int(limit or 20)]
        except Exception as e:
            self.last_error = f"related: {e}"
            return []

    def get_album_tracks(self, browse_id: str) -> tuple[str, list[dict]]:
        """(album_title, tracks) from a YT Music album."""
        if self.ytmusic is None or not browse_id:
            return "", []
        try:
            data = self._auth_call(self.ytmusic.get_album, browse_id) or {}
        except Exception as e:
            self.last_error = f"album: {e}"
            return "", []
        if not isinstance(data, dict):
            return "", []
        title = str(data.get("title", "") or "")
        tracks = []
        for t in (data.get("tracks") or []):
            if not isinstance(t, dict) or not t.get("videoId"):
                continue
            nt = self._norm_track(t)
            if not nt.get("thumbnail"):
                try:
                    thumbs = data.get("thumbnails") or []
                    if thumbs:
                        nt["thumbnail"] = (thumbs[-1] or {}).get("url", "")
                except Exception:
                    pass
            tracks.append(nt)
        return title, tracks

    def get_artist_info(self, artist_id: str) -> dict:
        """Info + top songs from a YT Music artist."""
        if self.ytmusic is None or not artist_id:
            return {}
        try:
            data = self._auth_call(self.ytmusic.get_artist, artist_id) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            self.last_error = f"artist: {e}"
            return {}

    def get_artist_top_tracks(self, artist_id: str, limit: int = 20) -> tuple[str, list[dict]]:
        """(artist_name, top_songs) from YT Music."""
        info = self.get_artist_info(artist_id)
        if not info:
            return "", []
        name = str(info.get("name", "") or "")
        out: list[dict] = []
        try:
            songs = ((info.get("songs") or {}).get("results") or [])
            for t in songs:
                if isinstance(t, dict) and t.get("videoId"):
                    out.append(self._norm_track(t))
        except Exception:
            pass
        return name, out[: int(limit or 20)]

    def get_lyrics_text(self, video_id: str) -> tuple[str, str]:
        """(lyrics, source) for a song. '' if no lyrics or no session."""
        if self.ytmusic is None or not video_id:
            return "", ""
        try:
            watch = self._auth_call(
                self.ytmusic.get_watch_playlist, video_id, limit=1) or {}
            browse = ""
            try:
                for t in ((watch or {}).get("tracks") or []):
                    lb = ((t or {}).get("lyrics") or {})
                    if isinstance(lb, dict) and lb.get("browseId"):
                        browse = lb["browseId"]
                        break
                    # Some versions carry it as lyricsBrowseId
                    if isinstance(t, dict) and t.get("lyricsBrowseId"):
                        browse = t["lyricsBrowseId"]
                        break
            except Exception:
                browse = ""
            if not browse:
                return "", ""
            data = self._auth_call(self.ytmusic.get_lyrics, browse) or {}
            if not isinstance(data, dict):
                return "", ""
            lyr = data.get("lyrics", "") or ""
            if isinstance(lyr, list):
                # With timestamps: LyricLine list
                try:
                    lyr = "\n".join(str(getattr(l, "text", l)) for l in lyr)
                except Exception:
                    lyr = "\n".join(str(x) for x in lyr)
            return str(lyr or ""), str(data.get("source", "") or "")
        except Exception as e:
            self.last_error = f"lyrics: {e}"
            return "", ""

    def get_song_details(self, video_id: str) -> dict:
        """Extended metadata for a song (get_song)."""
        if self.ytmusic is None or not video_id:
            return {}
        try:
            data = self._auth_call(self.ytmusic.get_song, video_id) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            self.last_error = f"details: {e}"
            return {}

    def remove_from_playlist(self, playlist_id: str, tracks: list[dict]) -> bool:
        """Removes songs from your own playlist (needs setVideoId)."""
        if self.ytmusic is None or not self.authenticated:
            self.last_error = "No session"
            return False
        vids = [{"videoId": t.get("videoId", ""), "setVideoId": t.get("setVideoId", "")}
                for t in (tracks or []) if t.get("videoId") and t.get("setVideoId")]
        if not playlist_id or not vids:
            self.last_error = ("Cannot remove (only in your own playlists, "
                               "not in Liked or automatic ones)")
            return False
        try:
            self.ytmusic.remove_playlist_items(playlist_id, vids)
            self._lib_cache = None
            return True
        except Exception as e:
            self.last_error = f"remove: {e}"
            return False

    def delete_playlist(self, playlist_id: str) -> bool:
        """Deletes your own YouTube Music playlist."""
        if self.ytmusic is None or not self.authenticated or not playlist_id:
            self.last_error = "No session"
            return False
        try:
            self.ytmusic.delete_playlist(playlist_id)
            self._lib_cache = None
            return True
        except Exception as e:
            self.last_error = f"delete playlist: {e}"
            return False

    def rename_playlist(self, playlist_id: str, title: str) -> bool:
        """Renames your own YouTube Music playlist."""
        if self.ytmusic is None or not self.authenticated or not playlist_id or not title:
            self.last_error = "No session"
            return False
        try:
            self.ytmusic.edit_playlist(playlist_id, title=title)
            self._lib_cache = None
            return True
        except Exception as e:
            self.last_error = f"rename: {e}"
            return False

    def get_playlist_tracks(self, playlist_id: str, limit: int = 200) -> list[dict]:
        if not playlist_id:
            return []
        # 1) ytmusicapi
        if self.ytmusic is not None:
            pl = self._auth_call(self.ytmusic.get_playlist, playlist_id, limit=limit)
            if isinstance(pl, dict):
                tracks = pl.get("tracks", []) or []
                norm = [self._norm_track(t) for t in tracks if isinstance(t, dict)]
                norm = [t for t in norm if t.get("videoId")]
                if norm:
                    return norm
        # 2) flat yt-dlp fallback
        try:
            return self._flat_playlist_via_ytdlp(playlist_id, limit)
        except Exception as e:
            self.last_error = f"playlist fallback: {e}"
            return []

    PROGRESSIVE_LIMITS = (100, 300, 800, 2000, 5000)

    def fetch_progressive(self, kind: str, identifier: str = "",
                          limits: tuple = PROGRESSIVE_LIMITS,
                          on_batch=None, should_stop=None) -> list[dict]:
        """Progressive loading: calls with growing limits and delivers each batch.

        kind: 'liked' | 'playlist' | 'library'.
        on_batch(full_batch_so_far, is_final) is invoked for each step.
        should_stop() -> True cancels (section change).
        Returns the last full batch. Fast at start (100), complete
        at the end (up to 5000) without blocking the UI: the caller runs it in a thread.
        """
        last: list[dict] = []
        prev_n = -1
        for i, lim in enumerate(list(limits or ()) + []):
            try:
                if should_stop and should_stop():
                    break
            except Exception:
                pass
            try:
                if kind == "liked":
                    batch = self.get_liked_songs(limit=int(lim))
                elif kind == "playlist":
                    batch = self.get_playlist_tracks(identifier, limit=int(lim))
                elif kind == "library":
                    batch = self.get_library_playlists(limit=int(lim), _use_cache=False)
                else:
                    batch = []
            except Exception as e:
                self.last_error = f"progressive: {e}"
                batch = []
            if not isinstance(batch, list):
                batch = []
            last = batch
            is_final = (i == len(list(limits or ())) - 1) or (len(batch) == prev_n) or (len(batch) < int(lim))
            try:
                if on_batch is not None:
                    on_batch(list(batch), bool(is_final))
            except Exception:
                pass
            if len(batch) == prev_n:
                break  # no longer grows: all loaded
            prev_n = len(batch)
            if len(batch) < int(lim):
                break  # the API returned less than requested: real end
        try:
            if on_batch is not None and last is not None:
                pass
        except Exception:
            pass
        return last

    @staticmethod
    def _pick_video_url(formats, prefer_height: int = 360) -> tuple[str, int]:
        """Best source for the requested height. Height closeness dominates;
        audio-carrying (progressive) streams pay a big penalty but still win
        when much closer (e.g. progressive 144p beats video-only 1080p for a
        144p request); container only tiebreaks (mp4 first). Returns
        (url, height). Unit-testable, no network."""
        try:
            _ph = max(144, min(2160, int(prefer_height or 360)))
        except Exception:
            _ph = 360
        try:
            rows = [f for f in (formats or [])
                    if isinstance(f, dict) and f.get("vcodec", "none") != "none"
                    and f.get("url")]

            def _score(f):
                try:
                    h = int(f.get("height") or 0)
                except Exception:
                    h = 0
                try:
                    _au = 10000 if (f.get("acodec", "none") not in ("none", None, "")) else 0
                except Exception:
                    _au = 0
                return abs(h - _ph) * 100 + _au + (0 if (f.get("ext") == "mp4") else 1)

            rows.sort(key=_score)
            if rows:
                try:
                    return str(rows[0].get("url") or ""), int(rows[0].get("height") or 0)
                except Exception:
                    pass
        except Exception:
            pass
        return "", 0

    @staticmethod
    def _table_max_h(info) -> int:
        try:
            hs = [int(f.get("height") or 0)
                  for f in ((info or {}).get("formats") or [])
                  if isinstance(f, dict) and f.get("vcodec", "none") != "none"]
            return max(hs) if hs else 0
        except Exception:
            return 0

    def upgrade_video_info(self, video_id: str, prefer_height: int = 1080) -> dict:
        """Fetch a RICHER format table in the background until it covers
        prefer_height (guest clients are bot-capped at 360p and the wall is
        flaky: the same merged-clients request passes or fails per attempt).
        Up to 3 attempts (guest, then logged-in). Returns the new scored info
        or {}. Never raises. Updates the caches so the worker's next refresh
        picks the HD url instantly."""
        try:
            _ph = max(480, min(2160, int(prefer_height or 1080)))
        except Exception:
            _ph = 1080
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            try:
                _fmt_cache = getattr(self, "_video_fmt_cache", None) or {}
            except Exception:
                _fmt_cache = {}
            try:
                _entry = _fmt_cache.get(video_id) or {}
                info = _entry.get("info") if isinstance(_entry.get("info"), dict) else None
            except Exception:
                info = None
            if info is not None and self._table_max_h(info) >= _ph:
                return self.get_video_info(video_id, _ph)
            base = self._base_opts(noplaylist=True, format="best[ext=mp4]/best")
            if info is None:
                try:
                    info = self._extract_info_fallback(url, base, download=False,
                                                       cookies_first=False)
                except Exception:
                    info = None
                if not isinstance(info, dict):
                    try:
                        info = self._extract_info_fallback(url, base, download=False,
                                                           cookies_first=True)
                    except Exception:
                        info = None
                if not isinstance(info, dict):
                    return {}
            for _att in range(3):
                if self._table_max_h(info) >= _ph:
                    break
                try:
                    cand = self._extract_info_fallback(url, base, download=False,
                                                       cookies_first=(_att > 0))
                except Exception:
                    continue
                if not (isinstance(cand, dict) and cand.get("formats")):
                    continue
                if self._table_max_h(cand) > self._table_max_h(info):
                    try:
                        cand = dict(cand)
                        for _k in ("title", "thumbnail", "duration"):
                            try:
                                if not cand.get(_k) and info.get(_k):
                                    cand[_k] = info[_k]
                            except Exception:
                                pass
                        info = cand
                    except Exception:
                        pass
            try:
                import time as _tt
                _fmt_cache[video_id] = {"ts": _tt.time(), "info": info}
                self._video_fmt_cache = _fmt_cache
            except Exception:
                pass
            # Drop stale per-height picks: the new table may serve them better.
            try:
                for _k in [k for k in (getattr(self, "_video_cache", None) or {})
                           if (isinstance(k, tuple) and k and k[0] == video_id)
                           or k == video_id]:
                    try:
                        self._video_cache.pop(_k, None)
                    except Exception:
                        pass
            except Exception:
                pass
            return self.get_video_info(video_id, _ph)
        except Exception:
            return {}

    def get_video_info(self, video_id: str, prefer_height: int = 360) -> dict:
        """MP4 VIDEO URL (for the mini video panel). Fallback to {}.

        prefer_height: pick the source closest to the requested render
        resolution (before it always scored against 360, so "1080p" just
        upscaled a 360p stream and looked identical). Cache is per (id, height).
        """
        try:
            _ph = max(144, min(2160, int(prefer_height or 360)))
        except Exception:
            _ph = 360
        try:
            hit = (self._video_cache or {}).get((video_id, _ph))
            if isinstance(hit, dict) and hit.get("video_url"):
                return hit
        except Exception:
            pass
        try:
            legacy = (self._video_cache or {}).get(video_id)
            if isinstance(legacy, dict) and legacy.get("video_url"):
                return legacy
        except Exception:
            pass
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = self._base_opts(noplaylist=True, format="best[ext=mp4]/best")
        # Format TABLE is cached per video (10 min): resolution switches reuse
        # it instantly instead of paying a full yt-dlp extraction per click.
        try:
            _fmt_cache = getattr(self, "_video_fmt_cache", None)
            if _fmt_cache is None:
                _fmt_cache = {}
                self._video_fmt_cache = _fmt_cache
            _entry = _fmt_cache.get(video_id)
            import time as _tt
            _fresh = (isinstance(_entry, dict)
                      and _tt.time() - float(_entry.get("ts", 0) or 0) < 600
                      and isinstance(_entry.get("info"), dict))
        except Exception:
            _fresh = False
        if _fresh:
            info = _entry["info"]
        else:
            def _max_h(_inf) -> int:
                try:
                    _hs = [int(f.get("height") or 0)
                           for f in ((_inf or {}).get("formats") or [])
                           if isinstance(f, dict) and f.get("vcodec", "none") != "none"]
                    return max(_hs) if _hs else 0
                except Exception:
                    return 0

            def _get_table(_o, _ck):
                try:
                    return self._extract_info_fallback(url, _o, download=False,
                                                       cookies_first=_ck)
                except Exception:
                    return None

            try:
                info = _get_table(opts, False)
            except Exception:
                info = None
            if not isinstance(info, dict) or not info:
                try:
                    info = _get_table(opts, True)
                except Exception:
                    info = None
            if not isinstance(info, dict) or not info:
                return {}
            # UPGRADE the table while it does not cover the request: the
            # default android-first response only carries progressive streams
            # (max 360p), so higher requests silently returned 360p.
            # Done LAZILY in upgrade_video_info (background): startup here
            # stays fast with the reliable table.
            try:
                import time as _tt2
                _fmt_cache[video_id] = {"ts": _tt2.time(), "info": info}
            except Exception:
                pass
        if not info:
            return {}
        vurl, _chosen_h = self._pick_video_url(info.get("formats"), _ph)
        if not vurl:
            vurl = info.get("url", "") if info.get("vcodec", "none") != "none" else ""
            if vurl:
                try:
                    _chosen_h = int(info.get("height") or 0)
                except Exception:
                    _chosen_h = 0
        out = {"video_url": vurl or "",
               "title": info.get("title", video_id),
               "thumbnail": info.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
               "duration_sec": int(info.get("duration") or 0),
               "height": _chosen_h if vurl else 0,
               "asked_height": _ph if vurl else 0}
        try:
            if not hasattr(self, "_video_cache"):
                self._video_cache = {}
            self._video_cache[(video_id, _ph)] = out
        except Exception:
            pass
        return out

    @staticmethod
    def _norm_track(t: dict) -> dict:
        vid = t.get("videoId", "")
        title = t.get("title", "Untitled")
        artists = t.get("artists") or []
        artist = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict)) if artists else t.get("author", "")
        artist_ids = [a.get("id", "") for a in artists if isinstance(a, dict) and a.get("id")] if artists else []
        album_obj = t.get("album")
        album = ""
        album_id = ""
        if isinstance(album_obj, dict):
            album = album_obj.get("name", "") or ""
            album_id = album_obj.get("id", "") or ""
        elif isinstance(album_obj, str):
            album = album_obj
        thumbs = t.get("thumbnails") or t.get("thumbnail") or []
        thumb_url = ""
        try:
            if isinstance(thumbs, list) and thumbs:
                thumb_url = thumbs[-1].get("url", "")
            elif isinstance(thumbs, dict):
                thumb_url = thumbs.get("url", "")
            elif isinstance(thumbs, str):
                thumb_url = thumbs
        except Exception:
            pass
        dur = t.get("duration") or t.get("length") or ""
        dur_sec = t.get("duration_seconds") if t.get("duration_seconds") else _parse_duration(dur)
        return {
            "videoId": vid, "title": title, "artist": artist or "YouTube",
            "artistIds": artist_ids,
            "album": album, "albumId": album_id, "thumbnail": thumb_url, "duration": dur,
            "duration_sec": dur_sec if isinstance(dur_sec, int) else int(dur_sec or 0),
            "setVideoId": t.get("setVideoId", ""),
            "browseId": t.get("browseId", "") or "",
            "likeStatus": t.get("likeStatus", "") or "",
        }

    def _flat_playlist_via_ytdlp(self, playlist_id: str, limit: int) -> list[dict]:
        url = playlist_id if playlist_id.startswith("http") else f"https://www.youtube.com/playlist?list={playlist_id}"
        opts = self._base_opts(extract_flat=True, playlistend=limit)
        info = self._extract_info_fallback(url, opts, download=False, cookies_first=True)
        entries = (info or {}).get("entries", []) or []
        out = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            vid = e.get("id", "")
            if not vid:
                continue
            out.append({
                "videoId": vid, "title": e.get("title", vid),
                "artist": e.get("uploader", "YouTube"), "album": "",
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "duration": "", "duration_sec": int(e.get("duration") or 0),
            })
        return out

    # ---------- search (songs AND videos, mixed) ----------
    # Real YouTube search (InnerTube WEB). yt-dlp's ytsearch is blocked here
    # (it returns 0 entries for every query and every player client) and YT
    # Music only knows its own music catalogue, so a doujin/cover/video that
    # is not indexed there used to be unreachable: searching its exact title
    # showed songs and no video at all.
    # Public YouTube InnerTube search key. Set your own via env var YT_SEARCH_KEY
    # if you want a different quota; the embedded one is the public WEB key.
    _YT_SEARCH_KEY = os.environ.get("YT_SEARCH_KEY", "")
    _YT_WEB_CLIENTS = (("WEB", "2.20240726.00.00"),
                       ("TVHTML5", "7.20240724.13.00"))

    @staticmethod
    def _runs_text(node: Any) -> str:
        """InnerTube text node -> plain text."""
        try:
            if isinstance(node, dict):
                runs = node.get("runs")
                if isinstance(runs, list):
                    return "".join(str(r.get("text", "")) for r in runs
                                   if isinstance(r, dict))
                if node.get("simpleText") is not None:
                    return str(node.get("simpleText") or "")
        except Exception:
            pass
        return ""

    def _search_youtube_web(self, query: str, limit: int = 20) -> list[dict]:
        """Every public YouTube video matching `query` (InnerTube WEB search).

        This is the source that always sees videos outside the music
        catalogue. Never raises: an empty list means "nothing found".
        """
        import urllib.request
        body = {"context": {"client": {"clientName": "WEB",
                                       "clientVersion": "2.20240726.00.00",
                                       "hl": "en", "gl": "US"}},
                "query": query}
        raw = b""
        for name, ver in self._YT_WEB_CLIENTS:
            try:
                body["context"]["client"]["clientName"] = name
                body["context"]["client"]["clientVersion"] = ver
                req = urllib.request.Request(
                    "https://www.youtube.com/youtubei/v1/search?key=" + self._YT_SEARCH_KEY,
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json",
                             "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                            "AppleWebKit/537.36 Chrome/126 Safari/537.36")})
                raw = urllib.request.urlopen(req, timeout=20).read()
                if raw:
                    break
            except Exception:
                raw = b""
        if not raw:
            return []
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return []
        out: list[dict] = []
        try:
            sections = (data.get("contents", {})
                        .get("twoColumnSearchResultsRenderer", {})
                        .get("primaryContents", {})
                        .get("sectionListRenderer", {})
                        .get("contents", []) or [])
        except Exception:
            sections = []
        for sec in sections:
            try:
                items = (sec.get("itemSectionRenderer", {}) or {}).get("contents", []) or []
            except Exception:
                continue
            for item in items:
                v = item.get("videoRenderer") if isinstance(item, dict) else None
                if not isinstance(v, dict):
                    continue
                vid = str(v.get("videoId", "") or "")
                if not vid:
                    continue
                thumb = ""
                try:
                    thumbs = ((v.get("thumbnail", {}) or {}).get("thumbnails", []) or [])
                    if thumbs:
                        thumb = str(thumbs[-1].get("url", "") or "")
                except Exception:
                    thumb = ""
                # "Artist - Topic" is an auto-generated channel; show the
                # artist name instead of the channel label.
                chan_name = self._runs_text(v.get("ownerText", {})) or "YouTube"
                if chan_name.lower().endswith(" - topic"):
                    chan_name = chan_name[:-len(" - topic")].strip()
                # The uploader channel (what the row must show) and its id
                # (so the user can open that channel).
                chan_id = ""
                try:
                    chan_id = str((((v.get("ownerText", {}) or {})
                                    .get("runs") or [{}])[0]
                                   .get("navigationEndpoint") or {})
                                  .get("browseEndpoint", {}).get("browseId", "") or "")
                except Exception:
                    chan_id = ""
                dur = self._runs_text(v.get("lengthText", {}))
                views = 0
                try:
                    vtxt = self._runs_text(v.get("viewCountText", {}))
                    m = re.search(r"([\d.,]+)\s*([KMB])?", vtxt or "", re.I)
                    if m:
                        n = float(m.group(1).replace(",", ""))
                        mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get(
                            (m.group(2) or "").lower(), 1.0)
                        views = int(n * mult)
                except Exception:
                    views = 0
                out.append({
                    "videoId": vid,
                    "title": self._runs_text(v.get("title", {})) or vid,
                    "artist": self._runs_text(v.get("ownerText", {})) or "YouTube",
                    "channel": chan_name,
                    "channelId": chan_id,
                    "artistIds": [],
                    "album": "", "albumId": "",
                    "thumbnail": thumb or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "duration": dur,
                    "duration_sec": _parse_duration(dur) if dur else 0,
                    "views": views,
                    "setVideoId": "", "browseId": "", "likeStatus": "",
                    "kind": "video",
                })
                if len(out) >= limit:
                    return out
        return out

    def search(self, query: str, limit: int = 20,
               on_batch: Any = None,
               include_channels: bool = True) -> list[dict]:
        """Songs, videos, channels and artists together.

        THREE sources in parallel, so a video can never be hidden by a song
        shelf: YT Music songs, YT Music videos and REAL YouTube (InnerTube
        WEB) for whatever the music catalogue does not carry. Channels and
        artists are appended at the end so they never bury playable results.
        Every row is playable (songs/videos) or openable (channels/artists).
        """
        query = (query or "").strip()
        if not query:
            return []
        songs: list[dict] = []
        videos: list[dict] = []
        web: list[dict] = []
        channels: list[dict] = []
        artists: list[dict] = []
        seen: set[str] = set()
        errs: list[str] = []

        def _collect(raw: list[dict], want: str, into: list[dict]) -> None:
            for t in raw or []:
                if not isinstance(t, dict):
                    continue
                norm = self._norm_track(t)
                vid = str(norm.get("videoId", "") or "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                norm["kind"] = want
                into.append(norm)

        def _notify():
            """Paint early: hand over whatever is already in."""
            if on_batch is None:
                return
            try:
                out = (list(songs) + list(videos) + list(web))
                if out:
                    on_batch(self._rank_by_relevance(query, out)[:limit])
            except Exception:
                pass

        def _songs():
            if self.ytmusic is None:
                return
            try:
                raw = self.ytmusic.search(query, filter="songs", limit=limit) or []
                _collect(raw, "song", songs)
            except Exception as e:
                errs.append(str(e))
            _notify()

        def _videos():
            if self.ytmusic is None:
                return
            try:
                raw = self.ytmusic.search(query, filter="videos", limit=limit) or []
                _collect(raw, "video", videos)
            except Exception as e:
                errs.append(str(e))
                try:
                    raw = self.ytmusic.search(query, limit=limit) or []
                    _collect(raw, "video", videos)
                except Exception:
                    pass
            _notify()

        def _web():
            try:
                for t in self._search_youtube_web(query, limit) or []:
                    vid = str(t.get("videoId", "") or "")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    web.append(t)
            except Exception as e:
                errs.append(str(e))
            _notify()

        def _chans_artists():
            """Channels and artists are fetched after playable results so
            they never delay the songs/videos the user typed for."""
            if not include_channels:
                return
            try:
                chans = self.search_channels(query, limit=8) or []
                for c in chans:
                    c["kind"] = "channel"
                    channels.append(c)
            except Exception as e:
                errs.append(str(e))
            try:
                arts = self.search_artists(query, limit=8) or []
                for a in arts:
                    a["kind"] = "artist"
                    artists.append(a)
            except Exception as e:
                errs.append(str(e))

        threads = [threading.Thread(target=f, daemon=True)
                   for f in (_songs, _videos, _web, _chans_artists)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=25)

        # Relevance first: YouTube ranks by popularity and by "similar
        # words", so typing an exact niche title returns junk with almost
        # the same words. Each kind is re-sorted by how well it matches what
        # was actually typed, keeping the source order as tiebreak.
        songs = self._rank_by_relevance(query, songs)
        videos = self._rank_by_relevance(query, videos)
        web = self._rank_by_relevance(query, web)

        # Videos = YT Music's shelf + real YouTube merged into ONE ranked
        # pool, alternating sources so neither can hide the other, then the
        # final list interleaves songs and videos by relevance.
        merged_videos: list[dict] = []
        vi = wi = 0
        while vi < len(videos) or wi < len(web):
            if vi < len(videos):
                merged_videos.append(videos[vi])
                vi += 1
            if wi < len(web):
                merged_videos.append(web[wi])
                wi += 1
            if len(merged_videos) >= limit:
                break
        # The pool is interleaved by source, so rank it once more: the final
        # merge only looks at the head of each list, and a great match sitting
        # behind a weak one would never get its chance.
        merged_videos = self._rank_by_relevance(query, merged_videos)
        if songs or merged_videos:
            out = self._merge_search_kinds(songs, merged_videos, limit, query)
            # Append channels and artists after playable results.
            if include_channels:
                out = list(out) + channels + artists
            if not songs and not merged_videos and errs:
                self.last_error = f"search: {errs[0]}"
            return out[:limit]
        # Last resort: yt-dlp (its own search is blocked here, but a working
        # extract path still beats an empty result).
        try:
            out = self._search_via_ytdlp(query, limit)
            for t in out or []:
                t["kind"] = "video"
            if out:
                if include_channels:
                    out = list(out) + channels + artists
                return out[:limit]
        except Exception as e:
            errs.append(str(e))
        self.last_error = (f"search: {errs[0]}" if errs else "search: no results")
        return []

    @staticmethod
    def _merge_search_kinds(songs: list[dict], videos: list[dict], limit: int,
                            query: str = "") -> list[dict]:
        """Songs and videos interleaved BY RELEVANCE, never by source.

        A small constant bonus for songs (typing a name usually means the
        song) breaks ties, but a much better matching video still goes first:
        typing an exact niche title must not be buried under songs that only
        share a couple of words.
        """
        out: list[dict] = []
        if not videos:
            return list(songs[:limit])
        if not songs:
            return list(videos[:limit])
        ss = [YouTubeClient._relevance(query, s) for s in songs]
        vs = [YouTubeClient._relevance(query, v) for v in videos]
        si = vi = 0
        bonus = 16.0
        run = 0  # consecutive videos, so one shelf cannot flood the list
        while (si < len(songs) or vi < len(videos)) and len(out) < limit:
            a = (ss[si] + bonus) if si < len(songs) else float("-inf")
            b = vs[vi] if vi < len(videos) else float("-inf")
            take_video = b > a
            if take_video and run >= 2 and si < len(songs):
                # Videos stay visible, but never three in a row.
                take_video = False
            if take_video:
                out.append(videos[vi])
                vi += 1
                run += 1
            else:
                out.append(songs[si])
                si += 1
                run = 0
        return out[:limit]

    # ---------- relevance ----------
    @staticmethod
    def _norm_text(s: str, strip_parens: bool = True) -> str:
        """Lowercase, accent-free, punctuation-free, single-spaced."""
        try:
            import unicodedata
            t = unicodedata.normalize("NFKD", str(s or ""))
            t = "".join(ch for ch in t if not unicodedata.combining(ch))
        except Exception:
            t = str(s or "")
        t = t.lower()
        if strip_parens:
            # Parenthetical noise is decoration, not part of the name.
            t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", t)
        t = re.sub(r"[’'`´]", "", t)
        t = re.sub(r"[^0-9a-z]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    # Words that only decorate a title (they carry no identity).
    _JUNK_WORDS = {"lyrics", "lyric", "video", "official", "audio", "full",
                   "album", "hd", "hq", "mv", "m/v", "the", "a", "en",
                   "feat", "featuring", "ft", "with", "and", "del", "vol"}
    # Words that mark a DIFFERENT rendition: they sink the row.
    _VARIANT_WORDS = {"version", "ver", "remix", "instrumental", "cover",
                      "live", "reaction", "loop", "hours", "hour", "mashup",
                      "rehearsal", "sped", "slowed", "reverb", "nightcore",
                      "acapella", "vocal", "demo", "bootleg", "extended",
                      "bass", "spedup", "8d", "night", "edit", "mix",
                      "parody", "tutorial", "lesson", "review", "guitar",
                      "piano", "tabs", "chords", "ringtone"}
    # Words that mean "this is not the song", hard penalty.
    _SPOOF_WORDS = {"parody", "spoof", "mashup", "but", "reaction", "tutorial",
                    "review", "lesson", "interview", "compilation", "memories"}
    # Filler uploads: they are never what the user typed.
    _FILLER_WORDS = {"loop", "hours", "hour", "night", "min", "full", "all"}

    @classmethod
    def _relevance(cls, query: str, t: dict) -> float:
        """How well a row answers what was typed. Higher = better.

        YouTube's own ranking is popularity-first and happily returns rows
        that merely share a couple of words, so the exact/niche case needs
        an explicit text score. Views break the remaining ties: between two
        rows with the same words, the one everybody watches is the one meant.
        """
        q = cls._norm_text(query)
        if not q:
            return 0.0
        title = cls._norm_text(t.get("title", ""))
        artist = cls._norm_text(t.get("artist", "") or "")
        if not title:
            return 0.0
        score = 0.0
        if title == q:
            score += 120
        elif title.startswith(q):
            score += 25
        elif q in title:
            score += 30
        qt = [w for w in q.split() if w]
        tt = [w for w in title.split() if w]
        at = [w for w in artist.split() if w]
        # The UN-stripped title: "Get Lucky (Bass Tutorial)" must not read
        # as an exact match just because we removed the parentheses.
        tf = [w for w in cls._norm_text(t.get("title", ""),
                                        strip_parens=False).split() if w]
        both = tt + at
        if qt:
            # YT Music writes songs as "Title" with the artist in a separate
            # field, so "artist title" is only a full match once BOTH are
            # considered. Scoring on title alone buried every real song.
            hit = sum(1 for w in qt if w in both)
            score += 46.0 * hit / len(qt)
            if all(w in tt for w in qt):
                score += 22
            if hit == len(qt):
                score += 45
            extra = [w for w in tf if w not in qt and w not in cls._JUNK_WORDS]
            score -= min(18.0, 4.5 * len(extra))
            variants = [w for w in tf if w in cls._VARIANT_WORDS]
            score -= 13.0 * len(variants)
            spoof = [w for w in tf if w in cls._SPOOF_WORDS]
            score -= 40.0 * len(spoof)
            filler = [w for w in tf if w in cls._FILLER_WORDS]
            score -= 25.0 * len(filler)
            a_hit = sum(1 for w in qt if w in at)
            if a_hit:
                score += 20.0 * a_hit / len(qt)
        if qt and tt[:len(qt)] == qt:
            score += 10
        try:
            views = int(t.get("views", 0) or 0)
            if views > 0:
                import math
                score += min(25.0, 4.0 * math.log10(views + 1))
        except Exception:
            pass
        score += min(8.0, len(qt) * 2.0)
        return score

    @classmethod
    def _rank_by_relevance(cls, query: str, items: list[dict]) -> list[dict]:
        """Text score first, YouTube's own order as tiebreak.

        The source rank is worth about a point and a half per position: it
        never overrides a clear text mismatch, but it settles the ambiguous
        cases (parody vs original, two versions of the same name).
        """
        if not items:
            return []
        scored = []
        for i, t in enumerate(items):
            rank_bonus = max(0.0, 3.0 - 1.5 * i)
            scored.append((-(cls._relevance(query, t) + rank_bonus), i, t))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [x[2] for x in scored]

    # ---------- channel (who uploaded it, and what they have) ----------
    def _it_post(self, endpoint: str, body: dict) -> dict:
        """POST an InnerTube endpoint with the public WEB client."""
        import urllib.request
        req = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/%s?key=%s"
            % (endpoint, self._YT_SEARCH_KEY),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 Chrome/126 Safari/537.36")})
        return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())

    def _it_context(self) -> dict:
        return {"client": {"clientName": "WEB",
                           "clientVersion": "2.20240726.00.00",
                           "hl": "en", "gl": "US"}}

    # ---------- YouTube Music (WEB_REMIX) ----------
    # Normal YouTube channel pages have NO albums at all; releases live only in
    # the music app, which answers on the WEB_REMIX client. That is why the
    # Albums tab used to come up empty.
    _YT_MUSIC_VERSION = "1.20241010.01.00"

    def _it_music_context(self) -> dict:
        return {"client": {"clientName": "WEB_REMIX",
                           "clientVersion": self._YT_MUSIC_VERSION,
                           "hl": "en", "gl": "US"}}

    def _it_music_post(self, endpoint: str, body: dict) -> dict:
        return self._it_post(endpoint, body)

    @classmethod
    def _music_shelf_title(cls, shelf: dict) -> str:
        """Title of a music shelf. Carousels keep it in their own header."""
        shelf = shelf or {}
        hdr = shelf.get("header") or {}
        for key in ("musicCarouselShelfBasicHeaderRenderer",
                    "musicShelfRenderer"):
            s = cls._runs_text((hdr.get(key) or {}).get("title"))
            if s:
                return s
        return cls._runs_text(shelf.get("title")) or ""

    @classmethod
    def _music_item(cls, item: dict) -> dict:
        """Normalise musicResponsiveListItemRenderer / musicTwoRowItemRenderer.

        Songs carry their title in flexColumns[0] (the new lockup format);
        carousels use the plain "title" node. Read both.
        """
        item = item or {}
        r = (item.get("musicResponsiveListItemRenderer")
             or item.get("musicTwoRowItemRenderer") or {})
        if not r:
            return {}
        title = cls._runs_text(r.get("title"))
        subtitle = ""
        cols = r.get("flexColumns") or []
        if cols:
            if not title:
                try:
                    title = cls._runs_text(
                        cols[0]["musicResponsiveListItemFlexColumnRenderer"]
                        .get("text"))
                except Exception:
                    title = ""
            try:
                subtitle = cls._runs_text(
                    cols[1]["musicResponsiveListItemFlexColumnRenderer"]
                    .get("text"))
            except Exception:
                subtitle = ""
        if not subtitle:
            subtitle = cls._runs_text(r.get("subtitle"))
        bid = ((r.get("navigationEndpoint") or {}).get("browseEndpoint") or {})
        page_type = ""
        try:
            page_type = str(((bid.get("browseEndpointContextSupportedConfigs") or {})
                             .get("browseEndpointContextMusicConfig") or {})
                            .get("pageType", "") or "")
        except Exception:
            page_type = ""
        # A song row carries a watchEndpoint, not a browseEndpoint. Depending on
        # the renderer the videoId sits on the row or on the play-button overlay.
        video_id = str((((r.get("navigationEndpoint") or {}).get("watchEndpoint"))
                        or {}).get("videoId", "") or "")
        if not video_id:
            try:
                video_id = str(
                    ((((r.get("overlay") or {})
                       .get("musicItemThumbnailOverlayRenderer") or {})
                      .get("content") or {})
                     .get("musicPlayButtonRenderer") or {})
                    .get("playNavigationEndpoint", {}).get("watchEndpoint", {})
                    .get("videoId", "") or "")
            except Exception:
                video_id = ""
        thumb = ""
        for key in ("thumbnailRenderer", "thumbnail"):
            try:
                thr = r.get(key) or {}
                srcs = (((thr.get("musicThumbnailRenderer") or {}).get("thumbnail")
                         or {}).get("thumbnails") or [])
                if not srcs:
                    srcs = (thr.get("thumbnails") or [])
                if srcs:
                    thumb = str(srcs[-1].get("url", "") or "")
                    break
            except Exception:
                thumb = ""
        return {"videoId": video_id,
                "albumId": str(bid.get("browseId", "") or ""),
                "title": title,
                "subtitle": subtitle,
                "pageType": page_type,
                "thumbnail": thumb}

    @classmethod
    def _music_shelf_items(cls, shelf: dict) -> list[dict]:
        out: list[dict] = []
        for it in (shelf.get("contents") or []):
            item = cls._music_item(it)
            if item and item.get("title"):
                out.append(item)
        return out

    def get_channel_music_page(self, channel_id: str) -> dict:
        """Raw YT Music page of a channel (releases/shelves). Never raises."""
        cid = str(channel_id or "").strip()
        if not cid:
            return {}
        try:
            data = self._it_music_post("browse", {
                "context": self._it_music_context(), "browseId": cid})
        except Exception as e:
            self.last_error = f"music page: {e}"
            return {}
        if not isinstance(data, dict):
            return {}
        shelves: list[dict] = []
        tabs = ((data.get("contents") or {})
                .get("singleColumnBrowseResultsRenderer") or {}).get("tabs", [])
        for tab in (tabs or []):
            tr = tab.get("tabRenderer") or {}
            contents = ((tr.get("content") or {})
                        .get("sectionListRenderer") or {}).get("contents") or []
            for sec in contents:
                for key in ("musicShelfRenderer", "musicCarouselShelfRenderer",
                            "musicPlaylistShelfRenderer"):
                    shelf = sec.get(key)
                    if isinstance(shelf, dict):
                        items = self._music_shelf_items(shelf)
                        if items:
                            shelves.append({
                                "kind": key,
                                "title": self._music_shelf_title(shelf),
                                "items": items})
        header = data.get("header") or {}
        name = ""
        avatar = ""
        for key in ("musicImmersiveHeaderRenderer",
                    "musicVisualHeaderRenderer",
                    "musicDetailHeaderRenderer"):
            h = header.get(key) or {}
            if not name:
                name = self._runs_text(h.get("title"))
            if not avatar:
                try:
                    srcs = (((h.get("thumbnail") or {}).get("croppedSquareThumbnailRenderer")
                             or {}).get("thumbnail") or {}).get("thumbnails") or []
                    if not srcs:
                        srcs = (h.get("thumbnail") or {}).get("thumbnails") or []
                    if srcs:
                        avatar = str(srcs[-1].get("url", "") or "")
                except Exception:
                    avatar = ""
        return {"channelId": cid, "name": name, "avatar": avatar,
                "shelves": shelves}

    # Shelf headers that are releases (albums, EPs, singles, discography).
    _ALBUM_SHELF_WORDS = ("album", "ep", "single", "discography", "release")
    # ...and the ones that are NOT releases even though they hold items.
    _NOT_ALBUM_SHELF_WORDS = ("video", "live", "playlist", "compilation", "video")

    _RELEASE_TYPES = ("album", "single", "ep", "compilation")

    @classmethod
    def _music_col(cls, r: dict, idx: int) -> str:
        """Text of flexColumns[idx] (0 = title, 1 = type / artist / year)."""
        try:
            return cls._runs_text(
                (r.get("flexColumns") or [])[idx]
                ["musicResponsiveListItemFlexColumnRenderer"].get("text"))
        except Exception:
            return ""

    @staticmethod
    def _norm_artist(s: str) -> str:
        """Comparable artist name (no accents/punctuation, lowercase)."""
        import re
        import unicodedata
        t = unicodedata.normalize("NFKD", str(s or ""))
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        t = re.sub(r"[^0-9a-z]+", " ", t.lower())
        return re.sub(r"\s+", " ", t).strip()

    def _channel_display_name(self, channel_id: str) -> str:
        """Real channel name, for any kind of channel (not only artists)."""
        cid = str(channel_id or "").strip()
        if not cid:
            return ""
        try:
            page = self.get_channel_page(cid)
            if page.get("name"):
                return str(page["name"])
        except Exception:
            pass
        try:
            page = self.get_channel_music_page(cid)
            return str(page.get("name", "") or "")
        except Exception:
            return ""

    @staticmethod
    def _clean_channel_name(name: str) -> str:
        """'xxx / DiGiTAL WiNG' -> 'DiGiTAL WiNG' (the latin half)."""
        s = str(name or "").strip()
        if not s:
            return ""
        if s.lower().endswith(" - topic"):
            s = s[:-8].strip()
        for sep in ("/", "|", "\u30fb", "\u2022"):
            if sep in s:
                bits = [b.strip() for b in s.split(sep) if b.strip()]
                for b in reversed(bits):
                    if any("a" <= ch.lower() <= "z" for ch in b):
                        return b
                if bits:
                    return bits[-1]
        return s

    def _albums_from_search(self, query: str, want_artist: str) -> list[dict]:
        """Real releases found by searching YouTube Music for `query`.

        Most channels have no music page at all, but their artist usually does
        have releases in YouTube Music. Search is the only place that finds
        them, and the results are filtered by artist so we never show
        somebody else's album.
        """
        q = str(query or "").strip()
        if not q:
            return []
        want = self._norm_artist(want_artist or q)
        out: list[dict] = []
        seen: set = set()
        try:
            data = self._it_music_post("search", {
                "context": self._it_music_context(), "query": q})
        except Exception as e:
            self.last_error = f"album search: {e}"
            return []
        items: list = []

        def _walk(n, depth=0):
            if depth > 30:
                return
            if isinstance(n, dict):
                if "musicResponsiveListItemRenderer" in n:
                    items.append(n["musicResponsiveListItemRenderer"])
                for v in n.values():
                    _walk(v, depth + 1)
            elif isinstance(n, list):
                for v in n:
                    _walk(v, depth + 1)

        _walk(data)
        for r in items:
            bid = ((r.get("navigationEndpoint") or {}).get("browseEndpoint") or {})
            b = str(bid.get("browseId", "") or "")
            if not b.startswith("MPRE") or b in seen:
                continue
            sub = self._music_col(r, 1)
            parts = [p.strip() for p in sub.split("\u2022") if p.strip()]
            if not parts or parts[0].lower() not in self._RELEASE_TYPES:
                continue          # not an Album/EP/Single row
            rel_type = parts[0]
            rest = parts[1:]
            year = rest.pop() if rest and rest[-1].isdigit() else ""
            artist = rest[0] if rest else ""
            na = self._norm_artist(artist)
            ok = False
            if na and want:
                ok = (na == want or na in want or want in na)
            if not ok and not na:
                ok = True         # no artist shown: keep it
            if not ok:
                continue
            seen.add(b)
            title = self._music_col(r, 0) or self._runs_text(r.get("title"))
            thumb = ""
            for _key in ("thumbnailRenderer", "thumbnail"):
                try:
                    thr = r.get(_key) or {}
                    srcs = (((thr.get("musicThumbnailRenderer") or {})
                             .get("thumbnail") or {}).get("thumbnails") or [])
                    if not srcs:
                        srcs = thr.get("thumbnails") or []
                    if srcs:
                        thumb = str(srcs[-1].get("url", "") or "")
                        break
                except Exception:
                    thumb = ""
            out.append({"_album_id": b, "albumId": b, "title": title,
                        "artist": artist, "release_type": rel_type,
                        "year": year, "subtitle": sub,
                        "thumbnail": thumb, "kind": "album"})
        return out

    def get_channel_albums(self, channel_id: str,
                           artist_hint: str = "") -> list[dict]:
        """REAL albums/EPs of this channel on YouTube Music.

        Two strategies, in order:
          1. the channel's own music page release shelves (most precise);
          2. if there is no music page (most normal upload channels), search
             YouTube Music for the channel name and keep only the releases
             whose artist actually matches.
        An empty result means no release is published for that artist.
        """
        cid = str(channel_id or "").strip()
        if not cid:
            return []
        page = self.get_channel_music_page(cid)
        out: list = []
        seen: set = set()
        for shelf in page.get("shelves", []) or []:
            title_l = str(shelf.get("title", "") or "").strip().lower()
            if not title_l:
                continue
            if any(w in title_l for w in self._NOT_ALBUM_SHELF_WORDS):
                continue
            if not any(w in title_l for w in self._ALBUM_SHELF_WORDS):
                continue
            for it in shelf.get("items", []) or []:
                aid = str(it.get("albumId", "") or "")
                if not aid or aid in seen:
                    continue
                seen.add(aid)
                parts = [p.strip() for p in
                         str(it.get("subtitle", "") or "").split("\u2022")
                         if p.strip()]
                rel_type = ""
                if parts and parts[0].lower() in self._RELEASE_TYPES:
                    rel_type = parts.pop(0)
                year = ""
                if parts and parts[-1].isdigit():
                    year = parts.pop()
                artist = parts[0] if parts else ""
                out.append({"_album_id": aid,
                            "albumId": aid,
                            "title": it.get("title", ""),
                            "artist": artist,
                            "release_type": rel_type,
                            "year": year,
                            "subtitle": it.get("subtitle", ""),
                            "thumbnail": it.get("thumbnail", ""),
                            "kind": "album"})
        if out:
            return out
        # Fallback: search by the real artist name (some channels show a
        # mangled one, e.g. a japanese + latin mix).
        name = self._clean_channel_name(
            str(artist_hint or "").strip()
            or str(page.get("name", "") or "")
            or self._channel_display_name(cid))
        if not name:
            return []
        return self._albums_from_search(name, name)

    def get_music_album(self, album_id: str) -> tuple[str, list[dict]]:
        """(album_title, tracks) for a MPREb_* YouTube Music album.

        Works as a guest (no account needed), unlike the ytmusicapi path.
        An album page is a twoColumnBrowseResultsRenderer: the header sits in
        tabs[0].tabRenderer.content...musicResponsiveHeaderRenderer and the
        tracklist in secondaryContents.sectionListRenderer.
        """
        aid = str(album_id or "").strip()
        if not aid:
            return "", []
        try:
            data = self._it_music_post("browse", {
                "context": self._it_music_context(), "browseId": aid})
        except Exception as e:
            self.last_error = f"album: {e}"
            return "", []
        if not isinstance(data, dict):
            return "", []

        def _cover_of(node) -> str:
            try:
                thumbs = (((node or {}).get("thumbnail") or {})
                          .get("musicThumbnailRenderer") or {}) or {}
                urls = ((thumbs.get("thumbnail") or {}).get("thumbnails") or [])
                return str(urls[-1].get("url", "") or "") if urls else ""
            except Exception:
                return ""

        contents = data.get("contents") or {}
        roots: list = []
        for key in ("twoColumnBrowseResultsRenderer",
                    "singleColumnBrowseResultsRenderer"):
            rc = contents.get(key)
            if not isinstance(rc, dict):
                continue
            for tab in (rc.get("tabs") or []):
                roots.append((tab.get("tabRenderer") or {}).get("content") or {})
            sec = rc.get("secondaryContents") or {}
            if sec:
                roots.append(sec)
            if not rc.get("tabs"):
                roots.append(rc)

        title = ""
        cover = _cover_of(data.get("background") or {})
        shelves: list = []
        for root in roots:
            for sec in ((root or {}).get("sectionListRenderer") or {}
                        ).get("contents", []) or []:
                hdr = sec.get("musicResponsiveHeaderRenderer")
                if isinstance(hdr, dict) and not title:
                    title = self._runs_text(hdr.get("title"))
                    cover = cover or _cover_of(hdr)
                for key in ("musicShelfRenderer", "musicPlaylistShelfRenderer"):
                    sh = sec.get(key)
                    if isinstance(sh, dict):
                        shelves.append(sh)
        if not title:
            micro = ((data.get("microformat") or {})
                     .get("microformatDataRenderer") or {})
            title = str(micro.get("title", "") or "")

        tracks: list = []
        seen: set = set()
        for sh in shelves:
            for it in (sh.get("contents") or []):
                item = self._music_item(it)
                vid = str(item.get("videoId", "") or "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                dur = ""
                try:
                    r = it["musicResponsiveListItemRenderer"]
                    dur = self._runs_text(
                        r["fixedColumns"][0]
                        ["musicResponsiveListItemFixedColumnRenderer"]
                        .get("text"))
                except Exception:
                    dur = ""
                tracks.append({"videoId": vid,
                               "title": item.get("title", ""),
                               "artist": item.get("subtitle", ""),
                               "album": title,
                               "albumId": aid,
                               "thumbnail": cover,
                               "duration": dur,
                               "duration_sec": _parse_duration(dur) if dur else 0,
                               "channelId": "",
                               "kind": "song"})
        return title, tracks

    def get_channel_top_songs(self, channel_id: str) -> list[dict]:
        """Real 'Top songs' shelf of a YT Music channel (may be empty)."""
        page = self.get_channel_music_page(channel_id)
        out: list[dict] = []
        for shelf in page.get("shelves", []) or []:
            if shelf.get("kind") != "musicShelfRenderer":
                continue
            title_l = str(shelf.get("title", "") or "").strip().lower()
            if "song" not in title_l and "track" not in title_l:
                continue
            for it in shelf.get("items", []) or []:
                vid = it.get("videoId", "")
                if not vid:
                    continue
                out.append({"videoId": vid, "title": it.get("title", ""),
                            "artist": it.get("subtitle", ""),
                            "channelId": str(channel_id or ""),
                            "channel": str(page.get("name", "") or ""),
                            "thumbnail": it.get("thumbnail", ""),
                            "kind": "song"})
        return out

    def get_video_channel(self, video_id: str, artist_name: str = "") -> tuple[str, str]:
        """(channel name, channel id) for a video. Cached, never raises.

        If the video's channel is an auto-generated "- Topic" channel (common
        on YouTube Music) and we know the artist name, we search YouTube for
        the artist's real channel instead of returning the "- Topic" channel.
        """
        vid = str(video_id or "")
        if not vid:
            return "", ""
        with self._lock:
            hit = self._video_cache.get(vid)
        if isinstance(hit, dict) and hit.get("channel"):
            return str(hit.get("channel") or ""), str(hit.get("channelId") or "")
        try:
            data = self._it_post("player", {"context": self._it_context(),
                                            "videoId": vid})
            vd = data.get("videoDetails", {}) or {}
            name = str(vd.get("author", "") or "")
            cid = str(vd.get("channelId", "") or "")
        except Exception:
            name, cid = "", ""

        # If the channel is an auto-generated "- Topic" channel and we know
        # the artist name, search YouTube for the artist's real channel.
        if name.lower().endswith(" - topic") and artist_name:
            try:
                artist_cid = self._search_artist_channel(artist_name)
                if artist_cid:
                    return artist_name, artist_cid
            except Exception:
                pass

        with self._lock:
            self._video_cache[vid] = {"channel": name, "channelId": cid,
                                      "_ts": time.time()}
        return name, cid

    def _search_artist_channel(self, artist_name: str) -> str | None:
        """Search YouTube for an artist's channel by name. Returns channel id
        or None if not found."""
        try:
            data = self._it_post("search", {
                "context": self._it_context(),
                "query": artist_name,
            })
            contents = ((data.get("contents", {})
                         .get("twoColumnSearchResultsRenderer", {}) or {})
                        .get("primaryContents", {}) or {})
            section_list = contents.get("sectionListRenderer", {}) or {}
            for section in section_list.get("contents", []) or []:
                item_section = section.get("itemSectionRenderer", {}) or {}
                for item in item_section.get("contents", []) or []:
                    ch = item.get("channelRenderer") or {}
                    if ch and ch.get("channelId"):
                        title = self._runs_text(ch.get("title", {})) or ""
                        # Only return channels that look like the artist
                        if artist_name.lower() in title.lower() or \
                           title.lower() in artist_name.lower():
                            return str(ch.get("channelId"))
        except Exception:
            pass
        return None

    # ---------- channel / artist search ----------
    def search_channels(self, query: str, limit: int = 10) -> list[dict]:
        """Search YouTube for channels matching `query`.

        Returns [{'channelId','title','thumbnail','subscriber_count','kind':'channel'}].
        Never raises: empty list means nothing found.
        """
        if not query or not query.strip():
            return []
        try:
            data = self._it_post("search", {
                "context": self._it_context(), "query": query.strip()})
        except Exception as e:
            self.last_error = f"channel search: {e}"
            return []
        out: list[dict] = []
        seen: set[str] = set()
        try:
            contents = ((data.get("contents", {})
                         .get("twoColumnSearchResultsRenderer", {}) or {})
                        .get("primaryContents", {}) or {})
            section_list = contents.get("sectionListRenderer", {}) or {}
            for section in section_list.get("contents", []) or []:
                item_section = section.get("itemSectionRenderer", {}) or {}
                for item in item_section.get("contents", []) or []:
                    ch = item.get("channelRenderer") or {}
                    if not ch or not ch.get("channelId"):
                        continue
                    cid = str(ch.get("channelId"))
                    if cid in seen:
                        continue
                    seen.add(cid)
                    title = self._runs_text(ch.get("title", {})) or cid
                    thumb = ""
                    try:
                        thumbs = (((ch.get("thumbnail") or {})
                                   .get("thumbnails") or []))
                        if thumbs:
                            thumb = str(thumbs[-1].get("url", "") or "")
                    except Exception:
                        pass
                    subs = ""
                    try:
                        sub_runs = ((ch.get("subscriberCountText") or {})
                                    .get("runs") or [])
                        if sub_runs:
                            subs = str(sub_runs[0].get("text", "") or "")
                    except Exception:
                        pass
                    out.append({
                        "channelId": cid,
                        "title": title,
                        "thumbnail": thumb or f"https://i.ytimg.com/vi/{cid}/hqdefault.jpg",
                        "subs": subs,
                        "kind": "channel",
                    })
                    if len(out) >= limit:
                        return out
        except Exception:
            pass
        return out

    def search_artists(self, query: str, limit: int = 10) -> list[dict]:
        """Search YouTube Music for artists matching `query`.

        Returns [{'channelId','title','thumbnail','kind':'artist'}].
        Never raises: empty list means nothing found.
        """
        if not query or not query.strip():
            return []
        try:
            data = self._it_music_post("search", {
                "context": self._it_music_context(), "query": query.strip()})
        except Exception as e:
            self.last_error = f"artist search: {e}"
            return []
        out: list[dict] = []
        seen: set[str] = set()
        try:
            contents = ((data.get("contents", {})
                         .get("twoColumnSearchResultsRenderer", {}) or {})
                        .get("primaryContents", {}) or {})
            section_list = contents.get("sectionListRenderer", {}) or {}
            for section in section_list.get("contents", []) or []:
                item_section = section.get("itemSectionRenderer", {}) or {}
                for item in item_section.get("contents", []) or []:
                    # Music artist shelf / twoRow item
                    r = (item.get("musicResponsiveListItemRenderer")
                         or item.get("musicTwoRowItemRenderer") or {})
                    nav = ((r.get("navigationEndpoint") or {})
                           .get("browseEndpoint") or {})
                    cid = str(nav.get("browseId", "") or "")
                    if not cid or not cid.startswith(("UC", "MP")):
                        continue
                    if cid in seen:
                        continue
                    seen.add(cid)
                    title = self._runs_text(r.get("title")) or cid
                    thumb = ""
                    try:
                        thr = r.get("thumbnailRenderer") or r.get("thumbnail") or {}
                        srcs = (((thr.get("musicThumbnailRenderer") or {})
                                 .get("thumbnail") or {}).get("thumbnails") or [])
                        if not srcs:
                            srcs = thr.get("thumbnails") or []
                        if srcs:
                            thumb = str(srcs[-1].get("url", "") or "")
                    except Exception:
                        pass
                    out.append({
                        "channelId": cid,
                        "title": title,
                        "thumbnail": thumb,
                        "kind": "artist",
                    })
                    if len(out) >= limit:
                        return out
        except Exception:
            pass
        return out

    @classmethod
    def _lockup_items(cls, node, out: list[dict], token_box: list[str],
                      depth: int = 0) -> None:
        """Walk an InnerTube tree collecting video/playlist/album items.

        YouTube serves channel tabs as lockupViewModel (the new format) and
        older music responses as videoRenderer/playlistRenderer; both are
        normalised to the same row dicts.
        """
        if depth > 18:
            return
        if isinstance(node, dict):
            lu = node.get("lockupViewModel")
            if isinstance(lu, dict):
                cid = str(lu.get("contentId", "") or "")
                ctype = str(lu.get("contentType", "") or "")
                meta = ((lu.get("metadata") or {}).get("lockupMetadataViewModel")
                        or {})
                tnode = meta.get("title") or {}
                if isinstance(tnode, dict):
                    title = (str(tnode.get("content", "") or "")
                             or cls._runs_text(tnode))
                else:
                    title = str(tnode or "")
                dur = views = ""
                thumb = ""
                try:
                    srcs = (((lu.get("contentImage") or {}).get("thumbnailViewModel")
                             or {}).get("image") or {}).get("sources") or []
                    if srcs:
                        thumb = str(srcs[-1].get("url", "") or "")
                except Exception:
                    thumb = ""
                try:
                    rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel")
                             or {}).get("metadataRows") or [])
                    for r in rows:
                        for p in (r.get("metadataParts") or []):
                            t = str(((p.get("text") or {}).get("content")) or "")
                            if "view" in t.lower():
                                views = t
                            elif ":" in t and t.count(":") in (1, 2) and not dur:
                                dur = t
                except Exception:
                    pass
                if cid and "PLAYLIST" in ctype:
                    out.append({"_playlist_id": cid, "title": title,
                                "artist": views, "album": "", "duration": "",
                                "duration_sec": 0, "thumbnail": thumb,
                                "kind": "playlist"})
                elif cid and "CHANNEL" not in ctype:
                    out.append({"videoId": cid, "title": title, "artist": "",
                                "album": "", "thumbnail": thumb,
                                "duration": dur,
                                "duration_sec": _parse_duration(dur) if dur else 0,
                                "views_text": views, "channelId": "",
                                "kind": "video"})
                return
            for key in ("videoRenderer", "gridVideoRenderer"):
                v = node.get(key)
                if isinstance(v, dict):
                    vid = str(v.get("videoId", "") or "")
                    if vid:
                        dur = cls._runs_text(v.get("lengthText", {}))
                        out.append({
                            "videoId": vid,
                            "title": cls._runs_text(v.get("title", {})) or vid,
                            "artist": cls._runs_text(v.get("ownerText", {})),
                            "album": "", "thumbnail": "",
                            "duration": dur,
                            "duration_sec": _parse_duration(dur) if dur else 0,
                            "channelId": str(v.get("ownerText", {}) and
                                             ((v.get("navigationEndpoint") or {})
                                              .get("browseEndpoint") or {})
                                             .get("browseId", "") or ""),
                            "kind": "video"})
                    return
            for key in ("playlistRenderer", "gridPlaylistRenderer",
                        "musicTwoRowItemRenderer"):
                v = node.get(key)
                if isinstance(v, dict):
                    bid = ((v.get("navigationEndpoint") or {})
                           .get("browseEndpoint") or {}).get("browseId", "")
                    if bid:
                        out.append({"_playlist_id": str(bid).replace("VL", "", 1),
                                    "title": cls._runs_text(v.get("title", {})),
                                    "artist": cls._runs_text(v.get("videoCountText", {})),
                                    "album": "", "thumbnail": "",
                                    "duration": "", "duration_sec": 0,
                                    "kind": "playlist"})
                    return
            cont = node.get("continuationItemRenderer")
            if isinstance(cont, dict):
                tok = ((cont.get("continuationEndpoint") or {})
                       .get("continuationCommand") or {}).get("token", "")
                if tok:
                    token_box.append(str(tok))
                return
            for v in node.values():
                cls._lockup_items(v, out, token_box, depth + 1)
        elif isinstance(node, list):
            for v in node:
                cls._lockup_items(v, out, token_box, depth + 1)

    def get_channel_page(self, channel_id: str) -> dict:
        """Channel header + the tabs it actually offers."""
        cid = str(channel_id or "").strip()
        if not cid:
            return {}
        try:
            data = self._it_post("browse", {"context": self._it_context(),
                                            "browseId": cid})
        except Exception:
            return {}
        meta = ((data.get("metadata") or {}).get("channelMetadataRenderer") or {})
        avatar = ""
        try:
            srcs = ((meta.get("avatar") or {}).get("thumbnails") or [])
            if srcs:
                avatar = str(srcs[-1].get("url", "") or "")
        except Exception:
            avatar = ""
        tabs = []
        for tab in ((data.get("contents", {})
                     .get("twoColumnBrowseResultsRenderer", {}) or {})
                    .get("tabs", []) or []):
            tr = tab.get("tabRenderer") or {}
            ep = (tr.get("endpoint") or {}).get("browseEndpoint") or {}
            title = str(tr.get("title", "") or "")
            if not title:
                continue
            tabs.append({"title": title,
                         "browseId": str(ep.get("browseId", "") or cid),
                         "params": str(ep.get("params", "") or ""),
                         "selected": bool(tr.get("selected"))})
        return {"channelId": cid, "name": str(meta.get("title", "") or ""),
                "avatar": avatar, "description": str(meta.get("description", "") or ""),
                "url": str(meta.get("ownerUrls", [""])[0] if
                           meta.get("ownerUrls") else ""),
                "tabs": tabs, "_data": data}

    def get_channel_tab(self, channel_id: str, tab_title: str = "",
                        continuation: str = "", page: dict | None = None
                        ) -> tuple[list[dict], str]:
        """Items of one channel tab (Videos / Songs / Albums / Playlists).

        Returns (rows, next continuation token). Never raises.

        Tries several tab title matches so channels in other languages
        (e.g. "Listas de reproducción" instead of "Playlists") still work.
        """
        page = page if isinstance(page, dict) else self.get_channel_page(channel_id)
        if not page:
            return [], ""
        tab = None
        wanted = str(tab_title or "").lower()
        # 1) exact match (case-insensitive)
        for t in page.get("tabs", []) or []:
            if str(t.get("title", "")).lower() == wanted:
                tab = t
                break
        # 2) contains match (e.g. "playlists" inside "Listas de reproducción")
        if tab is None and wanted:
            for t in page.get("tabs", []) or []:
                tt = str(t.get("title", "")).lower()
                if wanted in tt or tt in wanted:
                    tab = t
                    break
        # 3) fallback to first tab
        if tab is None and page.get("tabs"):
            tab = page["tabs"][0]
        try:
            if continuation:
                data = self._it_post("browse", {"context": self._it_context(),
                                                "continuation": continuation})
            else:
                data = self._it_post("browse", {
                    "context": self._it_context(),
                    "browseId": tab.get("browseId") or page.get("channelId"),
                    "params": tab.get("params") or ""})
        except Exception:
            return [], ""
        items: list[dict] = []
        tokens: list[str] = []
        # Tab content lives either inline (selected tab) or in the response
        # of the tab browse call; walk both.
        self._lockup_items(data.get("contents", {}), items, tokens)
        if not items:
            for tab_node in ((data.get("contents", {})
                              .get("twoColumnBrowseResultsRenderer", {}) or {})
                             .get("tabs", []) or []):
                tr = tab_node.get("tabRenderer") or {}
                if tr.get("content"):
                    self._lockup_items(tr.get("content"), items, tokens)
        if not items:
            # Continuation replies carry the rows under the action list.
            for act in (data.get("onResponseReceivedActions") or []) + \
                    (data.get("onResponseReceivedEndpoints") or []):
                self._lockup_items((act.get("appendContinuationItemsAction") or {})
                                   .get("continuationItems", []),
                                   items, tokens)
        return items, (tokens[0] if tokens else "")

    def _search_via_ytdlp(self, query: str, limit: int) -> list[dict]:
        opts = self._base_opts(extract_flat=True, default_search="ytsearch")
        info = self._extract_info_fallback(f"ytsearch{limit}:{query}", opts, download=False)
        entries = (info or {}).get("entries", []) or []
        out = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            vid = e.get("id", "")
            if not vid or vid.startswith("playlist"):
                continue
            out.append({
                "videoId": vid, "title": e.get("title", vid),
                "artist": e.get("uploader", "YouTube"), "album": "",
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "duration": "", "duration_sec": int(e.get("duration") or 0),
            })
        return out

    # ---------- stream info / download ----------
    def get_stream_info(self, video_id: str) -> dict:
        """Returns {'audio_url','title','duration_sec','thumbnail','video_id'} (cached).

        Tries MANY extraction paths before giving up so that age-restricted,
        region-blocked, bot-walled or format-starved videos (e.g. "Nico Miseria
        - Juan José ◇") still yield an audio URL when any path works.

        Strategy: for each player client AND each format selector AND each
        cookie mode, try a full yt-dlp extraction. We cycle through clients
        (android, tv_embedded, web, tv) because YouTube serves different
        format tables to different clients - a video that has no audio URL
        on "web" may have one on "tv_embedded".
        Raises RuntimeError only when every path fails.
        """
        with self._lock:
            if video_id in self._stream_cache:
                cached = self._stream_cache[video_id]
                if time.time() - cached.get("_ts", 0) < 3600 * 3:
                    return cached
        url = f"https://www.youtube.com/watch?v={video_id}"

        format_selectors = [
            "bestaudio/best",
            "best[acodec!=none]/best",
            "worst",
            "m4a/bestaudio/best",
            "bestaudio[ext=m4a]/bestaudio/best",
            "bestaudio[ext=webm]/bestaudio/best",
        ]

        last_err = ""
        # Try each player client separately - YouTube serves different
        # format tables to different clients.
        for client in self.PLAYER_CLIENTS:
            for fmt in format_selectors:
                for cookies_first in (False, True):
                    try:
                        opts = self._base_opts(
                            noplaylist=True, format=fmt,
                            extractor_args={
                                "youtube": {"player_client": [client]}
                            },
                        )
                        info = self._extract_info_fallback(
                            url, opts, download=False,
                            cookies_first=cookies_first,
                        )
                        audio_url = self._pick_audio_url(info)
                        if audio_url:
                            result = self._build_stream_result(
                                info, audio_url, video_id)
                            self._cache_stream_result(video_id, result)
                            return result
                    except Exception as e:
                        last_err = str(e)
                        continue

        if last_err:
            raise RuntimeError(f"No audio URL found ({last_err[:120]})")
        raise RuntimeError("No audio URL found")

    def get_stream_info_safe(self, video_id: str) -> tuple[dict, str | None]:
        """Like get_stream_info but returns (info, None) on success or
        ({}, error_message) on failure. Never raises."""
        try:
            info = self.get_stream_info(video_id)
            return info, None
        except Exception as e:
            return {}, str(e)

    @staticmethod
    def _pick_audio_url(info: dict) -> str:
        """Extract the best audio URL from an yt-dlp info dict."""
        if not isinstance(info, dict):
            return ""
        audio_url = info.get("url", "") or ""
        if audio_url and info.get("acodec", "none") not in ("none", None, ""):
            return audio_url
        if info.get("formats"):
            fmts = [f for f in info["formats"]
                    if isinstance(f, dict) and f.get("acodec", "none") not in
                    ("none", None, "") and f.get("url")]
            if fmts:
                fmts.sort(key=lambda f: (f.get("abr") or 0), reverse=True)
                return fmts[0].get("url", "") or ""
        return ""

    @staticmethod
    def _build_stream_result(info: dict, audio_url: str, video_id: str) -> dict:
        return {
            "audio_url": audio_url,
            "title": info.get("title", video_id),
            "duration_sec": int(info.get("duration") or 0),
            "thumbnail": info.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
            "video_id": video_id,
            "uploader": info.get("uploader", "YouTube"),
            "_ts": time.time(),
        }

    def _cache_stream_result(self, video_id: str, result: dict) -> None:
        try:
            with self._lock:
                self._stream_cache[video_id] = result
        except Exception:
            pass

    @staticmethod
    def _ffmpeg_exe() -> str | None:
        try:
            import imageio_ffmpeg
            p = imageio_ffmpeg.get_ffmpeg_exe()
            if p and os.path.exists(p):
                return p
        except Exception:
            pass
        return None

    @staticmethod
    def _convert_to_mp3(src: str, dst: str) -> bool:
        exe = YouTubeClient._ffmpeg_exe()
        if not exe:
            return False
        import subprocess
        try:
            _nowin = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
            subprocess.run([exe, "-y", "-loglevel", "error", "-i", src,
                            "-vn", "-codec:a", "libmp3lame", "-q:a", "4", dst],
                           check=True, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=_nowin)
            return os.path.exists(dst) and os.path.getsize(dst) > 1024
        except Exception:
            return False

    def download_audio(self, video_id: str, progress_hook=None) -> str:
        """Downloads audio to cache/ as MP3 (pygame-compatible) and returns the path.

        Tries MULTIPLE format selectors AND multiple YouTube player clients
        so songs that can't be downloaded with bestaudio/best (e.g. "Nico
        Miseria - Juan José ◇") still yield a file when any format works.
        """
        import yt_dlp
        safe = "".join(c if c.isalnum() else "_" for c in video_id)
        mp3 = os.path.join(self.cache_dir, f"{safe}.mp3")
        # 1) Reuse existing mp3
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
            return mp3
        # 2) If another cached format exists, convert it to mp3
        for ext in ("m4a", "webm", "opus", "ogg", "mp4"):
            p = os.path.join(self.cache_dir, f"{safe}.{ext}")
            if os.path.exists(p) and os.path.getsize(p) > 1024:
                if self._convert_to_mp3(p, mp3):
                    return mp3
                break
        url = f"https://www.youtube.com/watch?v={video_id}"
        tmpl = os.path.join(self.cache_dir, f"{safe}.%(ext)s")
        # NOTE: we don't use yt-dlp postprocessor because it requires ffprobe
        # (imageio-ffmpeg only ships ffmpeg). We download raw and convert
        # ourselves with ffmpeg to mp3 (pygame-compatible).
        format_selectors = [
            "bestaudio/best",
            "best[acodec!=none]/best",
            "worst",
            "m4a/bestaudio/best",
            "bestaudio[ext=m4a]/bestaudio/best",
            "bestaudio[ext=webm]/bestaudio/best",
        ]
        last_err = ""
        # Try each player client separately - YouTube serves different
        # format tables to different clients.
        for client in self.PLAYER_CLIENTS:
            for fmt in format_selectors:
                for cookies_first in (False, True):
                    try:
                        opts = self._base_opts(
                            noplaylist=True, format=fmt,
                            outtmpl=tmpl, no_overwrites=False,
                            extractor_args={
                                "youtube": {"player_client": [client]}
                            },
                        )
                        opts["socket_timeout"] = 30
                        opts["retries"] = 2
                        if progress_hook:
                            opts["progress_hooks"] = [progress_hook]
                        self._download_with_fallback(url, opts)
                        if os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
                            return mp3
                    except Exception as e:
                        last_err = str(e)
                        continue
        # 3) Without ffmpeg: manually convert any downloaded file
        for name in os.listdir(self.cache_dir):
            if name.startswith(safe) and not name.endswith(".mp3"):
                src = os.path.join(self.cache_dir, name)
                if self._convert_to_mp3(src, mp3):
                    return mp3
                # last resort: return the file as-is
                return src
        for name in os.listdir(self.cache_dir):
            if name.startswith(safe):
                return os.path.join(self.cache_dir, name)
        if last_err:
            raise RuntimeError(f"Download failed ({last_err[:120]})")
        raise RuntimeError("Download failed")


def _parse_duration(d) -> int:
    if isinstance(d, (int, float)):
        return int(d)
    if not isinstance(d, str) or not d:
        return 0
    try:
        parts = [int(x) for x in d.strip().split(":")]
        total = 0
        for p in parts:
            total = total * 60 + p
        return total
    except Exception:
        return 0
