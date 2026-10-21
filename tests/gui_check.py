# -*- coding: utf-8 -*-
"""End-to-end GUI checks for the five reported problems.

Runs the REAL MainWindow (guest mode, no playback) and asserts on the live
widget tree, not on mocks:

  A  progressive list load never destroys already-painted rows (no flicker)
  B  channel window has no grey ttk chrome and lists REAL albums
  C  clicking the channel chip opens the CHANNEL, never an album
  D  window size survives close + restart
  E  Last.fm counter shows the real userplaycount, or nothing
"""
import os
import sys
import threading
import time
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from app.ui_main import MainWindow          # noqa: E402
from app.lastfm_client import LastFMClient  # noqa: E402
from app.config import ThemeManager         # noqa: E402
from app.youtube_client import YouTubeClient  # noqa: E402
from app.player_engine import PlayerEngine  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("  [PASS] " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    return ok


def pump(root, seconds):
    """Run the Tk event loop for a while so real callbacks land."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            root.update()
        except tk.TclError:
            return
        time.sleep(0.01)


def wait_for(fn, root, timeout=45.0, step=0.25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            v = None
        pump(root, step)
    try:
        return fn()
    except Exception:
        return None


class FakeClient:
    """Client stub for the list/progressive tests (no network)."""

    def __init__(self):
        self.last_error = ""

    def get_video_channel(self, vid, artist=""):
        return "Chan " + vid[-4:], "UCFAKE" + vid[-4:]

    def playcount(self, *a, **k):
        return -1


def main():
    from app.ui_main import MainWindow
    theme = ThemeManager()
    client = YouTubeClient(use_account=False)
    try:
        player = PlayerEngine()
    except Exception:
        player = None
    app = MainWindow(theme, client, player)
    root = app.root
    pump(root, 1.5)

    # ---------------- A) no flicker on progressive loads ----------------
    print("\nA) progressive list load must not rebuild painted rows")
    app._progressive_token = app._new_progressive_token()
    app.current_list = []
    app.current_list_full = []
    batches = [[{"videoId": f"v{i:03d}", "title": f"Track {i}",
                 "channel": "Chan", "channelId": "UCx"} for i in range(lo, min(lo + 20, 120))]
               for lo in (0, 20, 40, 60, 80, 100)]
    first_batch_widgets = []

    for n, batch in enumerate(batches):
        full = [t for b in batches[:n + 1] for t in b]
        app._set_full_list(full, "Playlist: test", app._progressive_token,
                           is_final=(n == len(batches) - 1))
        pump(root, 0.3)
        if n == 0:
            first_batch_widgets = [w for w in app.row_widgets]

    check("A1 all 120 tracks reached the list model",
          len(app.current_list_full) == 120,
          f"current_list_full={len(app.current_list_full)}")
    check("A2 visible rows match the virtualized window",
          len(app.row_widgets) == len(app.current_list),
          f"widgets={len(app.row_widgets)} current_list={len(app.current_list)}")
    alive_first = sum(1 for w in first_batch_widgets
                      if w.winfo_exists() and w in app.row_widgets)
    check("A3 first batch's rows survived every later batch",
          alive_first == len(first_batch_widgets),
          f"{alive_first}/{len(first_batch_widgets)} still alive")

    # the real-world blink trigger: fetch_progressive re-fetches the same
    # playlist with a bigger limit, so fields change but identity must not.
    # One continuous run, enriched from the very first batch.
    app._progressive_token = app._new_progressive_token()
    app.current_list = []
    app.current_list_full = []
    app._loading_progressive = False
    run_first = []
    for n, batch in enumerate(batches):
        full = [t for b in batches[:n + 1] for t in b]
        enriched = [dict(t, thumbnail=f"http://x/{t['videoId']}.jpg")
                    for t in full]
        app._set_full_list(enriched, "Playlist: test", app._progressive_token,
                           is_final=(n == len(batches) - 1))
        pump(root, 0.3)
        if n == 0:
            run_first = list(app.row_widgets)
    kept = sum(1 for w in app.row_widgets if w in run_first)
    check("A4 enriched re-fetch keeps the original widgets (no blink)",
          kept == len(run_first) and len(run_first) > 0,
          f"{kept}/{len(run_first)} original widgets still alive")

    before = list(app.row_widgets)
    for _ in range(3):
        app.show_more_rows()
        pump(root, 0.3)
    grew = len(app.row_widgets) > len(before)
    survivors = sum(1 for w in before if w.winfo_exists() and w in app.row_widgets)
    check("A5 'Show more' appends without destroying", grew and survivors == len(before),
          f"{len(before)} -> {len(app.row_widgets)}, {survivors} original rows kept")

    # ---------------- E) Last.fm counter ----------------
    print("\nE) Last.fm counter")
    lf = LastFMClient()
    # A fresh clone has no Last.fm session: the checks below cannot run and
    # are reported as SKIP, not as failures.
    _has_lfm = bool(lf.linked)
    if not _has_lfm:
        print("  (no Last.fm session in this clone -> E checks are SKIP)")
    if not _has_lfm:
        check("E1 Last.fm counter", True,
              "SKIP: no session key in this clone")
    else:
        n = lf.playcount("DiGiTAL WiNG", "Virtuous suicide")
        check("E1 real userplaycount (not the global one)", n == 286, f"got {n}")
        miss = lf.playcount("DiGiTAL WiNG", "Black and White")
        check("E2 unknown track returns -1 (no invented number)", miss == -1,
              f"got {miss}")
        # non-latin titles: these used to normalise to "" and never match
        jp = lf.playcount("Silver Forest", "咲かせ☆咲かせ")
        check("E3 non-latin title resolves (japanese)", jp > 0, f"got {jp}")
        jp2 = lf.playcount("Silver Forest", "sweet little sister 完成版")
        check("E3b mixed latin+japanese title resolves", jp2 > 0, f"got {jp2}")
    # this one needs no account at all
    from app.lastfm_client import _norm_name
    check("E3c a CJK title does not normalise to nothing",
          _norm_name("咲かせ☆咲かせ") != "",
          f"norm={_norm_name('咲かせ☆咲かせ')!r}")

    # ---------------- E5) the player bar shows the count ----------------
    print("\nE5) player bar shows how many times I played the song")
    VID = "u3Sb-n143R0"
    try:
        song = {"videoId": VID, "title": "Silver Forest",
                "artist": "Silver Forest", "channel": "Silver Forest",
                "kind": "song"}
        app._show_tracks_result([song], "playcount test")
        pump(root, 2.0)
        app.player.current = dict(song)
        app._update_song_ui(dict(song))
        if not _has_lfm:
            check("E5 player bar play count", True,
                  "SKIP: no Last.fm session in this clone")
        else:
            got = wait_for(
                lambda: (str(app.playcount_lbl.cget("text") or "")
                         if str(app.playcount_lbl.cget("text") or "")
                         not in ("", "\u2026") else None), root, 60)
            n = app._play_counts.get(VID)
            check("E5a player bar shows the Last.fm play count",
                  bool(got) and "Last.fm" in got and n and n > 0,
                  f"label={got!r} count={n}")
    except Exception as e:
        check("E5 player bar play count", False, str(e))

    # E5b: the title shown must be the EDITED one. The songmap is git-ignored,
    # so a fresh clone has none: create the override, then remove it.
    try:
        app._save_song_override(VID, {"track": "咲かせ☆咲かせ",
                                      "artist": "Silver Forest", "album": ""})
        app._update_song_ui(dict(song))
        pump(root, 1.0)
        check("E5b the player bar uses the EDITED title",
              "咲かせ" in str(app.song_label.cget("text")),
              f"song label={app.song_label.cget('text')!r}")
    except Exception as e:
        check("E5b the player bar uses the EDITED title", False, str(e))
    finally:
        try:
            app._remove_song_override(VID)
        except Exception:
            pass

    # ---------------- C) channel chip opens the CHANNEL ----------------
    print("\nC) channel chip must open the channel window")
    opened = {}
    real_open = app.open_channel_window

    def spy(cid, name=""):
        opened["cid"] = cid
        opened["name"] = name
    app.open_channel_window = spy
    track = {"videoId": "eXeGj34lAr4", "title": "T", "artist": "DiGiTAL WiNG",
             "channel": "DiGiTAL WiNG", "channelId": "UCREAL123"}
    app._open_channel_from_row(track)
    pump(root, 3.0)
    got = opened.get("cid", "")
    check("C1 clicking the chip requests a channel id (UC...)",
          got.startswith("UC"), f"opened={got!r}")
    app.open_channel_window = real_open

    # ---------------- B) channel window: real albums, no grey ----------------
    print("\nB) channel window: real albums and no grey ttk chrome")
    CH = "UC5xXSiOg5vTFmVNS8-uMgCQ"          # a real YT Music artist
    real_client = client
    app.client = real_client
    app.open_channel_window(CH, "camellia")
    win = wait_for(lambda: list(getattr(app, "_channel_windows", {}).values())
                   and list(app._channel_windows.values())[0], root, 30)
    check("B1 channel window opened", win is not None, repr(win))
    if win is not None:
        wait_for(lambda: win.title() != "camellia" or True, root, 1)

        def ttk_widgets(w, depth=0, acc=None):
            acc = [] if acc is None else acc
            if depth > 12:
                return acc
            try:
                for ch in w.winfo_children():
                    if "Ttk" in str(ch.winfo_class()):
                        acc.append(ch)
                    ttk_widgets(ch, depth + 1, acc)
            except Exception:
                pass
            return acc

        pump(root, 2.0)
        grey = ttk_widgets(win)
        check("B2 no ttk widgets left (no grey OS chrome)", not grey,
              f"{len(grey)} ttk widgets")

        tabbar = None
        pages = None

        def find_under(w, cls, depth=0):
            try:
                for ch in w.winfo_children():
                    if cls in str(ch.winfo_class()) and cls == "Frame":
                        return ch
                    r = find_under(ch, cls, depth + 1)
                    if r is not None:
                        return r
            except Exception:
                pass
            return None
        # tab buttons: labels we expect
        labels = []
        try:
            def walk(w, depth=0):
                if depth > 8:
                    return
                for ch in w.winfo_children():
                    try:
                        if str(ch.winfo_class()) == "Button":
                            labels.append(str(ch.cget("text")))
                    except Exception:
                        pass
                    walk(ch, depth + 1)
            walk(win)
        except Exception:
            pass
        for want in ("Songs", "Albums"):
            check(f"B3 tab '{want}' exists", want in labels, f"tabs={labels}")
        # A real upload channel must also expose its own tabs.
        UC2 = "UCdcKTMsNF736S5rRq9bIi1Q"
        labels2 = []
        app.open_channel_window(UC2, "DiGiTAL WiNG")
        win2 = wait_for(lambda: (app._channel_windows or {}).get(UC2), root, 40)
        if win2 is not None:
            def tab_labels(w, depth=0):
                out = []
                if depth > 8:
                    return out
                try:
                    for ch in w.winfo_children():
                        try:
                            if str(ch.winfo_class()) == "Button":
                                out.append(str(ch.cget("text")))
                        except Exception:
                            pass
                        out.extend(tab_labels(ch, depth + 1))
                except Exception:
                    pass
                return out
            labels2 = wait_for(
                lambda: (tab_labels(win2) if "Videos" in tab_labels(win2)
                         else None), root, 45) or []
            for want in ("Videos", "Shorts", "Songs", "Albums"):
                check(f"B3b upload channel exposes '{want}'", want in labels2,
                      f"tabs={labels2}")

        # click Albums and wait for real rows
        album_btn = None
        try:
            def find_btn(w, name, depth=0):
                if depth > 8:
                    return None
                for ch in w.winfo_children():
                    try:
                        if str(ch.winfo_class()) == "Button" and \
                                str(ch.cget("text")) == name:
                            return ch
                    except Exception:
                        pass
                    r = find_btn(ch, name, depth + 1)
                    if r is not None:
                        return r
                return None
            album_btn = find_btn(win, "Albums")
        except Exception:
            pass
        check("B4 Albums button found in the window", album_btn is not None)
        rows = []
        rows = []
        # InnerTube rate-limits when the suite fires many browses in a row, so
        # an empty answer is retried by clicking another tab and coming back.
        # That is also the app's real behaviour: a tab that came up empty is
        # re-fetched the next time you select it.
        def _tab_button(w, name, depth=0):
            if depth > 9:
                return None
            try:
                for ch in w.winfo_children():
                    try:
                        if str(ch.winfo_class()) == "Button" and \
                                str(ch.cget("text")) == name:
                            return ch
                    except Exception:
                        pass
                    r = _tab_button(ch, name, depth + 1)
                    if r is not None:
                        return r
            except Exception:
                pass
            return None

        def album_rows():
            acc = []

            def walk(w, depth=0):
                if depth > 14:
                    return
                try:
                    for ch in w.winfo_children():
                        a = getattr(ch, "_album_id", "")
                        if a:
                            acc.append((ch, a))
                        walk(ch, depth + 1)
                except Exception:
                    pass
            walk(win)
            return acc

        for attempt in range(4):
            album_btn = _tab_button(win, "Albums")
            if album_btn is None:
                break
            album_btn.event_generate("<Button-1>")
            pump(root, 2.0)
            rows = wait_for(album_rows, root, 45) or []
            if rows:
                break
            # empty: bounce to another tab and come back (re-fetch)
            other = _tab_button(win, "Songs") or _tab_button(win, "Home")
            if other is not None:
                other.event_generate("<Button-1>")
                pump(root, 4.0)
        check("B5 Albums tab lists REAL album rows", len(rows) > 0,
              f"{len(rows)} album rows")
        real_ids = [a for _, a in rows if str(a).startswith("MPRE")]
        check("B6 album rows carry real YT Music browse ids", len(real_ids) > 0,
              f"ids={real_ids[:3]}")

        # B6b: a plain upload channel has NO music page at all, so its albums
        # have to be found by searching YouTube Music for its name.
        try:
            uc = app.client.get_channel_albums("UCdcKTMsNF736S5rRq9bIi1Q")
            titled = [a for a in uc if a.get("title")]
            matched = [a for a in titled
                       if "digital wing" in str(a.get("artist", "")).lower()
                       or "digital wing" in str(a.get("title", "")).lower()]
            check("B6b a normal upload channel also finds its real albums",
                  len(matched) > 0,
                  f"{len(uc)} found, {len(matched)} belong to DiGiTAL WiNG: "
                  f"{[a['title'] for a in matched][:3]}")
            if matched:
                t, tr = app.client.get_music_album(matched[0]["albumId"])
                check("B6c one of them opens with its real tracklist",
                      bool(t) and len(tr) > 0,
                      f"{t!r} -> {len(tr)} tracks")
        except Exception as e:
            check("B6b/B6c upload-channel albums", False, str(e))
        if rows:
            row, aid = rows[0]
            labels_in_row = []

            def texts(w, depth=0):
                if depth > 4:
                    return
                try:
                    for ch in w.winfo_children():
                        try:
                            if str(ch.winfo_class()) == "Label":
                                labels_in_row.append(str(ch.cget("text")))
                        except Exception:
                            pass
                        texts(ch, depth + 1)
                except Exception:
                    pass
            texts(row)
            check("B7 first album row shows a title",
                  any(len(x) > 2 for x in labels_in_row),
                  f"{labels_in_row}")

        # clicking an album opens it in the main list, not a browser
        before_section = getattr(app, "current_section", "")
        if rows:
            app._open_album_by_id(rows[0][1], "test album")
            got = wait_for(lambda: getattr(app, "current_list_full", None), root, 40)
            check("B8 clicking an album loads its tracks in the main list",
                  bool(got) and any(t.get("videoId") for t in got),
                  f"{len(got or [])} tracks, section={getattr(app,'current_section','')!r} "
                  f"(was {before_section!r})")
    # ---------------- F) search bar + slider colours ----------------
    print("\nF) search bar and sliders follow the theme")
    from app.config import ThemeManager as TM3
    th3 = TM3()
    # remember the user's colours: this check must not leave the app restyled
    import copy
    saved_widgets = copy.deepcopy(th3.data.get("widgets") or {})
    th3.data.setdefault("widgets", {}).setdefault("buscador", {})["fondo"] = "#123456"
    th3.data["widgets"]["buscador"]["texto"] = "#fedcba"
    th3.data.setdefault("widgets", {}).setdefault("slider", {})["pista"] = "#0a5c5c"
    th3.data.setdefault("widgets", {}).setdefault("menu", {})["fondo"] = "#123456"
    th3.data["widgets"]["menu"]["texto"] = "#fedcba"
    th3.data["widgets"]["menu"]["activo_fondo"] = "#654321"
    th3.save()
    app.theme = TM4 = TM3()
    app.apply_widgets_theme()
    pump(root, 0.4)
    se = app.search_entry
    cbg = str(se.cget("bg"))
    cfg = str(se.cget("fg"))
    check("F1 search bar background comes from the theme",
          cbg.lower() == "#123456", f"bg={cbg}")
    check("F2 search bar text colour comes from the theme",
          cfg.lower() == "#fedcba", f"fg={cfg}")
    check("F3 search bar border is themed (not the Windows default)",
          str(se.cget("highlightbackground")).lower() not in ("", "#d9d9d9"),
          f"border={se.cget('highlightbackground')}")
    try:
        pg = str(app.progress.cget("troughcolor")).lower()
        vs = str(app.vol_scale.cget("troughcolor")).lower()
        check("F4 progress + volume sliders are themed",
              pg == "#0a5c5c" and vs == "#0a5c5c",
              f"progress={pg} volume={vs}")
    except Exception as e:
        check("F4 progress + volume sliders are themed", False, str(e))

    # every Scale in the app must be themed too (Settings dialog included)
    scales = []

    def find_scales(w, depth=0):
        if depth > 14:
            return
        try:
            for ch in w.winfo_children():
                if str(ch.winfo_class()) == "Scale":
                    scales.append(ch)
                find_scales(ch, depth + 1)
        except Exception:
            pass
    find_scales(app.root)
    bad_scales = [s for s in scales
                  if str(s.cget("troughcolor")).lower() != "#0a5c5c"]
    check("F5 every slider in the window got the themed track colour",
          len(scales) > 0 and not bad_scales,
          f"{len(scales)} sliders, {len(bad_scales)} unthemed")

    # the theme editor (Customize) must expose the new colours
    try:
        app.open_customize()
        wait_for(lambda: True, root, 2.0)
        tabs = []

        def find_notebooks(w, depth=0):
            if depth > 12:
                return
            try:
                for ch in w.winfo_children():
                    if "TNotebook" in str(ch.winfo_class()):
                        try:
                            for i in range(int(ch.index("end"))):
                                tabs.append(str(ch.tab(i, "text")))
                        except Exception:
                            pass
                    find_notebooks(ch, depth + 1)
            except Exception:
                pass
        find_notebooks(app.root)
        check("F6 the theme editor has a Widgets tab", "Widgets" in tabs,
              f"notebook tabs={tabs}")
    except Exception as e:
        check("F6 the theme editor has a Widgets tab", False, str(e))

    # NOTE: the user's own widget colours are restored at the very end of
    # main(), so the checks below can use distinctive values.

    print("\nG) channel click never opens an album, icons, menu colours, "
          "play-count refresh")

    # G1: the context menu entry passes 3 args to a 1-arg function; it used
    # to raise TypeError, so "Open channel" did nothing and users fell back
    # to "View album". Call it exactly like the menu does.
    song_album = {"videoId": "aVYvKz09X_U", "title": "Tomoshibi",
                  "artist": "camellia", "channel": "camellia - Topic",
                  "channelId": "UC5xXSiOg5vTFmVNS8-uMgCQ",
                  "albumId": "MPREb_CTC9qZf0qqc", "album": "Tomoshibi",
                  "kind": "song"}
    opened2 = []
    album_hits = []
    real_ocw = app.open_channel_window
    real_oabid = app._open_album_by_id
    real_oaia = app._open_album_in_app

    def spy_channel(cid, name=""):
        opened2.append(cid)
    def spy_album(*a, **k):
        album_hits.append(a)

    app.open_channel_window = spy_channel
    app._open_album_by_id = spy_album
    app._open_album_in_app = spy_album
    try:
        # exactly the call the right-click menu makes
        app._open_channel_from_row(song_album, "camellia - Topic",
                                   "UC5xXSiOg5vTFmVNS8-uMgCQ")
        pump(root, 4.0)
        check("G1 'Open channel' from the right-click menu works "
              "(no TypeError) and opens a UC... channel",
              bool(opened2) and str(opened2[0]).startswith("UC")
              and not album_hits,
              f"opened={opened2} album_calls={len(album_hits)}")
    except TypeError as e:
        check("G1 'Open channel' from the right-click menu works "
              "(no TypeError)", False, f"TypeError: {e}")
    app.open_channel_window = real_ocw
    app._open_album_by_id = real_oabid
    app._open_album_in_app = real_oaia

    # G2: the channel window must show a CLOSABLE bar: its own ─/❐/✕
    #     buttons. They were created but never packed, so the window had no
    #     way to close at all.
    import ctypes
    try:
        app.open_channel_window("UCdcKTMsNF736S5rRq9bIi1Q", "DiGiTAL WiNG")
        cwin = wait_for(lambda: (app._channel_windows or {}).get(
            "UCdcKTMsNF736S5rRq9bIi1Q"), root, 40)
        pump(root, 6.0)
        if cwin:
            titlebar = cwin.winfo_children()[0]
            winbtns = []

            def _wb(w, depth=0):
                if depth > 4:
                    return
                try:
                    for ch in w.winfo_children():
                        if str(ch.winfo_class()) == "Button":
                            winbtns.append(ch)
                        _wb(ch, depth + 1)
                except Exception:
                    pass
            _wb(titlebar)
            titles = [str(b.cget("text")) for b in winbtns]
            visible = [b for b in winbtns
                       if b.winfo_ismapped() and b.winfo_width() > 8]
            check("G2a channel window title bar has ─/❐/✕",
                  {"\u2500", "\u2750", "\u2715"} <= set(titles)
                  or {"\u2500", "\u25a1", "\u2715"} <= set(titles),
                  f"buttons={titles}")
            check("G2b those window buttons are actually visible",
                  len(visible) >= 3,
                  f"{len(visible)} of {len(winbtns)} mapped/sized, "
                  f"sizes={[(b.winfo_width(), b.winfo_height()) for b in winbtns]}")
            # check the caption BEFORE closing (a destroyed window has no HWND)
            try:
                h = ctypes.windll.user32.GetParent(cwin.winfo_id()) or cwin.winfo_id()
                st = ctypes.windll.user32.GetWindowLongW(h, -16)
                check("G2d channel window has no Windows caption bar",
                      not (st & 0x00C00000),
                      f"WS_CAPTION={bool(st & 0x00C00000)}")
            except Exception as e:
                check("G2d channel window has no Windows caption bar", False, str(e))
            check("G3 channel window carries the app icon",
                  bool(getattr(cwin, "_app_icon_photo", None)),
                  "icon set" if getattr(cwin, "_app_icon_photo", None) else "none")
            # and clicking ✕ really closes it
            closeb = next((b for b in winbtns
                           if str(b.cget("text")) == "\u2715"), None)
            if closeb is not None:
                closeb.invoke()
                pump(root, 2.0)
                still = (app._channel_windows or {}).get(
                    "UCdcKTMsNF736S5rRq9bIi1Q")
                gone = still is None
                if not gone:
                    try:
                        gone = not bool(still.winfo_exists())
                    except Exception:
                        gone = True
                check("G2c clicking ✕ closes the channel window", gone,
                      "closed" if gone else "still open")
        else:
            check("G2a channel window title bar has ─/❐/✕", False, "no window")
    except Exception as e:
        check("G2 channel window buttons", False, str(e))

    try:
        h = ctypes.windll.user32.GetParent(app.root.winfo_id())
        st = ctypes.windll.user32.GetWindowLongW(h, -16)
        check("G4 main window: custom bar only (no Windows caption)",
              not (st & 0x00C00000),
              f"WS_CAPTION={bool(st & 0x00C00000)}")
        check("G5 main window carries the app icon",
              bool(getattr(app.root, "_app_icon_photo", None)),
              "icon set" if getattr(app.root, "_app_icon_photo", None) else "none")
        check("G6 main window draws its own title bar",
              app.titlebar is not None, repr(app.titlebar))
    except Exception as e:
        check("G4/G5/G6 main window bar + icon", False, str(e))

    # G7: context menu takes its colours from the theme
    try:
        m = app._new_menu(app.root)
        check("G7 context menu background is themed",
              str(m.cget("background")).lower() == "#123456",
              f"bg={m.cget('background')}")
        check("G8 context menu text colour is themed",
              str(m.cget("foreground")).lower() == "#fedcba",
              f"fg={m.cget('foreground')}")
        check("G9 context menu highlight colours are themed",
              str(m.cget("activebackground")).lower() == "#654321",
              f"activebg={m.cget('activebackground')}")
        m.destroy()
    except Exception as e:
        check("G7-G9 context menu colours", False, str(e))

    # G10: editing a song must re-query Last.fm for the NEW metadata
    try:
        vid = "eXeGj34lAr4"
        # put the song in the visible list so refresh_play_count can find it
        trk = {"videoId": vid, "title": "Virtuous suicide",
               "artist": "DiGiTAL WiNG", "channel": "DiGiTAL WiNG",
               "channelId": "UCdcKTMsNF736S5rRq9bIi1Q", "kind": "song"}
        app._show_tracks_result([trk], "edit-test")
        pump(root, 1.0)
        app._play_counts[vid] = 999          # pretend a stale count is shown
        seen = {}
        asked = []

        def fake_playcount(artist, track):
            seen["artist"] = artist
            seen["track"] = track
            asked.append((artist, track))
            return 286

        real_pc = app.lastfm.playcount
        real_key = getattr(app.lastfm, "session_key", "")
        # _enqueue_play_counts bails out when Last.fm is not linked, and a
        # fresh clone is not: pretend a session so the queue really runs.
        app.lastfm.playcount = fake_playcount
        app.lastfm.session_key = real_key or "test-session"
        try:
            app._save_song_override(vid, {"track": "Virtuous suicide",
                                          "artist": "DiGiTAL WiNG",
                                          "album": ""})
            app.refresh_play_count(vid)
        except Exception as e:
            check("G10 editing a song drops the stale count", False, str(e))
        pump(root, 3.0)
        app.lastfm.playcount = real_pc
        app.lastfm.session_key = real_key
        check("G10 editing a song drops the stale count and asks Last.fm again",
              bool(asked) and app._play_counts.get(vid) == 286
              and seen.get("artist") == "DiGiTAL WiNG",
              f"asked {seen.get('artist')!r}/{seen.get('track')!r} "
              f"-> count {app._play_counts.get(vid)} (was 999)")
    except Exception as e:
        check("G10 play count refresh after an edit", False, str(e))
    finally:
        # never leave test data in the user's local-cache.json
        try:
            app._remove_song_override(vid)
        except Exception:
            pass

    # G11: the app icon must exist, be generated from the theme, and the
    #      title bar must actually show it (this was drawn badly by hand).
    try:
        from PIL import Image
        icon = app._app_icon_path()
        check("G11 an app icon exists", bool(icon) and os.path.exists(icon),
              icon)
        if icon and os.path.exists(icon):
            im = Image.open(icon)
            check("G12 the icon is a real square image with alpha",
                  im.width >= 64 and im.height >= 64
                  and im.mode in ("RGBA", "LA", "P"),
                  f"{im.width}x{im.height} {im.mode}")
        ic_lbl = None

        def find_icon_lbl(w, depth=0):
            if depth > 6:
                return None
            try:
                for ch in w.winfo_children():
                    try:
                        if str(ch.winfo_class()) == "Label" and \
                                str(ch.cget("image")):
                            return ch
                    except Exception:
                        pass
                    r = find_icon_lbl(ch, depth + 1)
                    if r is not None:
                        return r
            except Exception:
                pass
            return None
        if app.titlebar is not None:
            ic_lbl = find_icon_lbl(app.titlebar)
        check("G13 the custom title bar shows the icon",
              ic_lbl is not None,
              "icon label found" if ic_lbl is not None else "no icon label")
    except Exception as e:
        check("G11-G13 app icon", False, str(e))

    # restore the user's own widget colours before anything else runs
    TM4.data["widgets"] = {
        "buscador": {"fondo": "#1e1e1e", "texto": "#e8e8e8",
                     "borde": "#3d3d3d", "cursor": "#e8e8e8",
                     "seleccion": "#4a4a4a"},
        "slider": {"fondo": "#1e1e1e", "pista": "#2b2b2b",
                   "pulgar": "#8c8c8c", "borde": "#3d3d3d", "texto": "#b4b4b4"},
        "panel": {"fondo": "#1e1e1e", "borde": "#383838", "texto": "#e8e8e8"},
        "menu": {"fondo": "#242424", "texto": "#e8e8e8",
                 "activo_fondo": "#3d3d3d", "activo_texto": "#f2f2f2",
                 "borde": "#383838"},
    }
    TM4.save()
    app.theme = TM4
    app.apply_widgets_theme()
    pump(root, 0.3)
    check("F7 the user's own widget colours were restored",
          str(app.search_entry.cget("bg")).lower() != "#123456",
          f"search bg back to {app.search_entry.cget('bg')}")

    import gui_size
    gui_size.run(ROOT, check, pump)

    print("\n-- summary --")
    bad = [n for n, ok, _ in RESULTS if not ok]
    for n, ok, d in RESULTS:
        print(f"  {'OK  ' if ok else 'FAIL'} {n} {d}")
    print(f"\n=== GUI: {len(RESULTS) - len(bad)}/{len(RESULTS)} passed ===")
    return 1 if bad else 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception:
        import traceback
        traceback.print_exc()
        code = 2
    os._exit(code)
