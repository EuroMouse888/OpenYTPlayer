#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start.py — OpenYTPlayer entry point.
YouTube player linkable to your Google account (via cookiesYT.json),
ultra-customizable: background (color/gradient/image/VIDEO), button sizes,
customizable icons, fonts, colors, window... EVERYTHING.

Usage:
    python start.py               -> opens the player
    python start.py --selftest    -> automatic tests without opening a window
    python start.py --selftest --offline
                                  -> same tests with NO network calls
    python start.py --reset       -> resets the theme and opens the player

The selftest never signs in (guest client): test queries are not written to
your account's YouTube Music history.
"""
from __future__ import annotations
import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

REQUIRED = ["yt_dlp", "ytmusicapi", "PIL", "pygame", "requests", "imageio",
            "sounddevice", "numpy", "selenium"]


def ensure_dirs() -> None:
    for d in ("config", "cache", "assets"):
        os.makedirs(d, exist_ok=True)


def check_deps() -> list[str]:
    missing = []
    for mod in REQUIRED:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    return missing


class _Skip(Exception):
    """Internal: a selftest step deliberately skipped (offline mode)."""


def run_selftest(online: bool = True) -> int:
    print("=== OpenYTPlayer SELFTEST ===")
    print("     mode: " + ("online (GUEST, not signed in)" if online
                         else "offline (no network calls)"))
    ok = True

    # 1) Dependencies
    missing = check_deps()
    if missing:
        print(f"[FAIL] Missing dependencies: {missing}")
        print("       Install with: pip install -r requirements.txt")
        ok = False
    else:
        print("[OK] Dependencies")

    # 2) Cookies
    try:
        from app import cookies_util
        cookies = cookies_util.read_cookies_json_tolerant("cookiesYT.json")
        print(f"[OK] Parsed cookies: {len(cookies)}")
        if not cookies:
            print("     WARNING: 0 cookies (check cookiesYT.json), continuing as guest.")
        else:
            hdr = cookies_util.cookies_to_header_value(cookies)
            assert len(hdr) > 20, "empty cookie header"
            print(f"[OK] Header cookie ({len(hdr)} chars)")
            p = cookies_util.cookies_to_netscape_file(cookies, "cache/cookies.txt")
            assert os.path.exists(p), "cookies.txt was not generated"
            print(f"[OK] Netscape: {p}")
            try:
                a = cookies_util.build_ytmusicapi_auth_file(cookies, "cache/browser.json")
                assert os.path.exists(a)
                print(f"[OK] browser.json: {a}")
            except Exception as e:
                print(f"[FAIL] browser.json: {e}")
                ok = False
    except Exception as e:
        print(f"[FAIL] Cookies: {e}")
        traceback.print_exc()
        ok = False

    # 3) Theme (use a temp file so the user customization is untouched)
    try:
        import tempfile
        from app.config import ThemeManager
        tmp = os.path.join(tempfile.gettempdir(), "openytplayer_selftest_theme.json")
        try:
            os.remove(tmp)
        except Exception:
            pass
        tm = ThemeManager(tmp)
        assert tm.get("botones", "tamano") is not None
        tm.set(48, "botones", "tamano")
        assert tm.get("botones", "tamano") == 48
        print("[OK] ThemeManager load/set/save")
    except Exception as e:
        print(f"[FAIL] Theme: {e}")
        traceback.print_exc()
        ok = False

    # 4) YouTube client (GUEST: never signs in, so test queries never land
    #    in the real account's YouTube Music history)
    try:
        from app.youtube_client import YouTubeClient
        cl = YouTubeClient("cookiesYT.json", "cache", False, use_account=False)
        print(f"[OK] YouTubeClient init: {cl.account_label} (cookies={len(cl.cookies)})")
        # Quick search (may fail without internet; not fatal)
        try:
            if not online:
                print("[SKIP] Search (offline mode)")
            else:
                res = cl.search("never gonna give you up", limit=3)
                if res:
                    print(f"[OK] Search: {len(res)} results (e.g. {res[0].get('title','')[:50]})")
                else:
                    print(f"[WARN] Empty search: {cl.last_error[:150]}")
        except Exception as e:
            print(f"[WARN] Search (no network?): {str(e)[:150]}")
    except Exception as e:
        print(f"[FAIL] Client: {e}")
        traceback.print_exc()
        ok = False

    # 5) Online stream (direct URL + ffmpeg; the case that used to fail with
    #    "The page needs to be reloaded"). Guest client again.
    try:
        from app.youtube_client import YouTubeClient
        if not online:
            print("[SKIP] Stream + ffmpeg pipe (offline mode)")
            raise _Skip()
        cl = YouTubeClient("cookiesYT.json", "cache", False, use_account=False)
        info = cl.get_stream_info("nj5NftxIZV4")
        assert info.get("audio_url"), "no audio_url"
        print(f"[OK] Stream URL: {(info.get('title','') or '')[:45]} ({info.get('duration_sec')}s)")
        import subprocess
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        proc = subprocess.Popen(
            [exe, "-hide_banner", "-loglevel", "error", "-nostdin",
             "-i", info["audio_url"], "-vn", "-ac", "2", "-ar", "44100",
             "-f", "s16le", "-acodec", "pcm_s16le", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0)
        data = proc.stdout.read(44100 * 2 * 2)  # ~1 s
        proc.kill()
        assert len(data) > 50000, f"weak pipe: {len(data)}"
        print(f"[OK] Online ffmpeg pipe ({len(data)} bytes)")
        try:
            from app.stream_player import available
            print(f"[OK] stream_player available: {available()}")
        except Exception as e:
            print(f"[WARN] stream_player: {str(e)[:120]}")
    except _Skip:
        pass
    except Exception as e:
        print(f"[FAIL] Stream: {str(e)[:200]}")
        traceback.print_exc()
        ok = False

    # 6) Audio engine
    try:
        from app.player_engine import PlayerEngine
        from app.youtube_client import YouTubeClient
        cl = YouTubeClient("cookiesYT.json", "cache", False, use_account=False)
        pe = PlayerEngine(cl, volume=50)
        assert pe.state in ("stopped", "loading", "playing", "paused")
        pe.set_queue([{"videoId": "dQw4w9WgXcQ", "title": "test", "artist": "t",
                       "duration_sec": 10}], autoplay=False)
        assert len(pe.queue) == 1
        pe.set_shuffle(True)
        assert pe.shuffle is True
        assert pe.cycle_loop() in ("off", "all", "one")
        pe.stop()
        print(f"[OK] PlayerEngine (backend={pe._backend}, mixer={pe._mixer_ok}, stream={pe._stream_available()})")
        if not pe._mixer_ok:
            print(f"     WARNING audio: {pe.last_error[:150]}")
    except Exception as e:
        print(f"[FAIL] Player: {e}")
        traceback.print_exc()
        ok = False

    # 7) OAuth (API surface only, no network, no touching the user config)
    try:
        from ytmusicapi import OAuthCredentials  # noqa
        from app.youtube_client import YouTubeClient as _YC
        for _m in ("finish_oauth_device", "disconnect_oauth", "save_oauth_creds",
                   "oauth_linked", "_load_oauth_creds"):
            assert hasattr(_YC, _m), _m
        from app import browser_cookies as _bc
        assert hasattr(_bc, "extract_youtube_cookies") and hasattr(_bc, "detect_browsers")
        from app import google_login as _gl
        assert hasattr(_gl, "start_browser") and hasattr(_gl, "login_detected")
        assert hasattr(_gl, "read_stored_session") and hasattr(_gl, "brave_binary")
        assert hasattr(_YC, "import_login_cookies")
        print("[OK] OAuth + browser session + Google login available")
    except Exception as e:
        print(f"[FAIL] OAuth: {e}")
        traceback.print_exc()
        ok = False

    # 8) UI imports (no window opened if there is no display)
    try:
        import app.ui_main as ui
        assert hasattr(ui, "MainWindow")
        print("[OK] UI imports (MainWindow)")
    except Exception as e:
        print(f"[FAIL] UI: {e}")
        traceback.print_exc()
        ok = False

    # 9) Last.fm + regex metadata edits (offline: engine + signing only)
    try:
        from app import metadata_edits as _me
        from app.lastfm_client import LastFMClient, sign_call
        _rules = [
            {"search": {"track": None, "artist": None,
                        "album": "(.*) - Single", "albumArtist": None},
             "replace": {"track": None, "artist": None,
                         "album": "$1", "albumArtist": None}},
            {"search": {"track": None, "artist": None,
                        "album": "(.*) - EP", "albumArtist": None},
             "replace": {"track": None, "artist": None,
                         "album": "$1", "albumArtist": None}},
        ]
        assert _me.apply_rules(
            {"track": "T", "artist": "A", "album": "Foo - Single",
             "albumArtist": ""}, _rules)["album"] == "Foo"
        assert _me.apply_rules(
            {"track": "T", "artist": "A", "album": "Bar - EP",
             "albumArtist": ""}, _rules)["album"] == "Bar"
        assert _me.apply_rules(
            {"track": "T", "artist": "A", "album": "Baz",
             "albumArtist": ""}, _rules)["album"] == "Baz"
        assert _me.validate_rule(
            {"search": {"album": "("}, "replace": {}}) != ""
        s1 = sign_call({"b": "2", "a": "1"}, "s")
        s2 = sign_call({"a": "1", "b": "2"}, "s")
        assert len(s1) == 32 and s1 == s2
        _lfm = LastFMClient(os.path.join(
            tempfile.gettempdir(), "openytplayer_selftest_lastfm.json"))
        assert _lfm.update_now_playing("A", "T") is False
        assert _lfm.scrobble("A", "T", 123) is False
        print("[OK] Last.fm + metadata engine (offline)")
    except Exception as e:
        print(f"[FAIL] Last.fm/edits: {e}")
        traceback.print_exc()
        ok = False

    print("=== RESULT:", "ALL OK ✔" if ok else "FAILURES ✘", "===")
    return 0 if ok else 1


def _console_hide_wanted() -> bool:
    """Does the theme ask to hide the console? (False with --consola or selftest)."""
    try:
        args = sys.argv[1:]
        if "--consola" in args or "--show-console" in args or "--selftest" in args:
            return False
        import json as _j
        if os.path.exists("config/theme.json"):
            with open("config/theme.json", "r", encoding="utf-8") as _f:
                _d = _j.load(_f)
            return bool(_d.get("ventana", {}).get("ocultar_consola", True))
    except Exception:
        pass
    return True


def _relaunch_with_pythonw_if_wanted() -> bool:
    """Relaunch with pythonw.exe (no console) and return True to exit.

    With python.exe the console is CREATED before it can be hidden: it always
    flashes. Relaunching with pythonw.exe means no black window at any
    moment. Only when the theme asks to hide it (ocultar_consola) and we are
    under python.exe (not pythonw, no --consola, no --selftest).
    """
    if os.name != "nt":
        return False
    try:
        _exe_base = os.path.basename(sys.executable or "").lower()
        if "pythonw" in _exe_base:
            return False  # already console-less
        if not _console_hide_wanted():
            return False
        import subprocess as _sp
        _cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(_cand):
            return False
        _script = os.path.abspath(__file__)
        _args = [a for a in sys.argv[1:]
                 if a not in ("--consola", "--show-console")]
        _sp.Popen([_cand, _script] + _args, cwd=BASE_DIR,
                  creationflags=getattr(_sp, "DETACHED_PROCESS", 0x00000008))
        return True
    except Exception:
        return False


def _hide_console_if_wanted() -> None:
    """Hide the console on Windows (the project must not show a console).

    Plan A (new): relaunch with pythonw (see _relaunch_with_pythonw_if_wanted,
    called at the start of main). This here is plan B in case the relaunch
    did not happen (no pythonw available): ShowWindow(SW_HIDE) + logs to file.
    It also redirects stdout/stderr to a file when there is no console (pythonw
    leaves sys.stdout as None and some prints would fail).
    """
    # No console (pythonw / double-click .pyw): send logs to a file.
    try:
        if sys.stdout is None or sys.stderr is None:
            try:
                _logf = open("cache/stdout.log", "a", encoding="utf-8", buffering=1)
            except Exception:
                _logf = None
            if _logf is not None:
                try:
                    if sys.stdout is None:
                        sys.stdout = _logf
                except Exception:
                    pass
                try:
                    if sys.stderr is None:
                        sys.stderr = _logf
                except Exception:
                    pass
    except Exception:
        pass
    try:
        if not _console_hide_wanted():
            return
        # Redirect stdout to a file so diagnostics are not lost.
        try:
            import io as _io
            try:
                if sys.stdout is not None:
                    sys.stdout = _io.TextIOWrapper(
                        open("cache/stdout.log", "ab", buffering=0),
                        encoding="utf-8", errors="replace", line_buffering=True)
            except Exception:
                pass
        except Exception:
            pass
        if os.name == "nt":
            try:
                import ctypes
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    # 0 = SW_HIDE
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
            except Exception:
                pass
    except Exception:
        pass


def _install_crash_log() -> None:
    """faulthandler + hooks that leave the error in cache/crash.log
    (if the window dies without a message, that file tells why)."""
    try:
        import faulthandler
        try:
            _f = open("cache/crash.log", "w", encoding="utf-8")
            faulthandler.enable(file=_f)
        except Exception:
            pass
    except Exception:
        pass

    def _write_exc(text: str) -> None:
        try:
            with open("cache/crash.log", "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    import traceback as _tb
    import threading as _th

    def _exchook(etype, value, tb):
        try:
            _write_exc("".join(_tb.format_exception(etype, value, tb)))
        except Exception:
            pass
        _tb.print_exception(etype, value, tb)

    def _thexchook(args):
        try:
            _write_exc(f"[thread {args.thread.name}] " + "".join(
                _tb.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
        except Exception:
            pass
        try:
            print(f"[thread {args.thread.name}] {args.exc_value}")
        except Exception:
            pass

    try:
        sys.excepthook = _exchook
    except Exception:
        pass
    try:
        _th.excepthook = _thexchook
    except Exception:
        pass


def main() -> int:
    # No console: if running under python.exe, relaunch with pythonw.exe BEFORE
    # anything else (any heavy import would lengthen the console flash).
    try:
        if _relaunch_with_pythonw_if_wanted():
            return 0
    except Exception:
        pass
    ensure_dirs()
    _install_crash_log()
    _hide_console_if_wanted()
    args = sys.argv[1:]
    if "--selftest" in args:
        return run_selftest(online="--offline" not in args)
    if "--reset" in args:
        try:
            from app.config import ThemeManager
            ThemeManager("config/theme.json").reset()
            print("Theme reset.")
        except Exception as e:
            print(f"Could not reset: {e}")

    missing = check_deps()
    if missing:
        print(f"Missing dependencies: {missing}")
        print("Run: pip install -r requirements.txt")
        # Try to continue anyway if only something optional is missing
        critical = [m for m in missing if m in ("yt_dlp", "PIL")]
        if critical:
            try:
                input("Press Enter to exit...")
            except Exception:
                pass
            return 1

    try:
        from app.config import ThemeManager
        from app.youtube_client import YouTubeClient
        from app.player_engine import PlayerEngine
        from app.ui_main import MainWindow

        # First run: create DefaultTheme + snapshot the current look as theme1.
        try:
            ThemeManager.ensure_builtin_themes()
        except Exception:
            pass
        theme = ThemeManager("config/theme.json")
        client = YouTubeClient(
            theme.get("cuenta", "cookies_json_path", default="cookiesYT.json"),
            "cache",
            bool(theme.get("cuenta", "usar_cookies", default=True)),
            session_source=str(theme.get("cuenta", "fuente_sesion", default="archivo")),
            browser=str(theme.get("cuenta", "navegador", default="chrome")),
        )
        player = PlayerEngine(
            client,
            volume=float(theme.get("reproductor", "volumen_defecto", default=70)),
            loop_mode=str(theme.get("reproductor", "loop_defecto", default="off")),
            shuffle=bool(theme.get("reproductor", "shuffle_defecto", default=False)),
        )
        print(f"Account: {client.account_label}")
        print(f"Audio: backend={player._backend} mixer_ok={player._mixer_ok}")
        app = MainWindow(theme, client, player)
        app.run()
        return 0
    except Exception:
        traceback.print_exc()
        try:
            # No console means no stdin: do not block.
            if sys.stdin is not None and sys.stdin.isatty():
                input("Fatal error. Press Enter to exit...")
            else:
                try:
                    import time as _t
                    _t.sleep(2)
                except Exception:
                    pass
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
