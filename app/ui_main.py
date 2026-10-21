"""OpenYTPlayer main window (Tkinter, ultra-customizable)."""
from __future__ import annotations
import os
import json
import queue
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from io import BytesIO

from .config import ThemeManager
from .youtube_client import YouTubeClient
from .player_engine import PlayerEngine
from .lastfm_client import LastFMClient


def _fmt_time(sec) -> str:
    try:
        sec = int(sec or 0)
    except Exception:
        sec = 0
    m, s = divmod(max(0, sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _hex_to_rgb(c: str) -> tuple[int, int, int]:
    try:
        c = c.strip().lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except Exception:
        return (30, 27, 46)


def _rgb_to_hex(rgb: tuple) -> str:
    try:
        return "#{:02x}{:02x}{:02x}".format(
            max(0, min(255, int(rgb[0]))),
            max(0, min(255, int(rgb[1]))),
            max(0, min(255, int(rgb[2]))))
    except Exception:
        return "#1e1e1e"


def _blend(c1: str, c2: str, t: float) -> str:
    """Blend c1->c2. t=0 returns c1, t=1 returns c2."""
    t = max(0.0, min(1.0, float(t)))
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def _avg_color_hex(img, box=None) -> str:
    """Average color of a PIL.Image (or region) as hex."""
    try:
        from PIL import ImageStat
        region = img.crop(box) if box else img
        small = region.resize((32, 32))
        stat = ImageStat.Stat(small.convert("RGB"))
        return _rgb_to_hex(tuple(stat.mean[:3]))
    except Exception:
        return "#1e1e1e"


class _BgListbox(tk.Frame):
    """Plain list with a REAL IMAGE BACKGROUND (native Listbox has none).

    Minimal API matching what the app uses: delete/insert/get/
    curselection/bind('<<ListboxSelect>>')/configure/cget/pack. Text goes
    straight over the canvas (transparent) and selection is highlighted.
    """

    def __init__(self, master, height: int = 8, **kw):
        super().__init__(master, **kw)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._items: list[str] = []
        self._sel: int = -1
        self._top: int = 0
        self._bg = "#1e1e1e"
        self._fg = "#d8d8d8"
        self._selfg = "#3a3a3a"
        self._font = ("Segoe UI", 11)
        self._bg_photo = None
        self._bg_pil = None
        self._handlers: list = []
        try:
            self._row_h = self._measure()
        except Exception:
            self._row_h = 22
        self._canvas.bind("<Configure>", lambda e: self._redraw())
        self._canvas.bind("<Button-1>", self._click)
        try:
            self._canvas.bind("<MouseWheel>", self._wheel)
            self._canvas.bind("<Button-4>", lambda e: self._scroll(-1))
            self._canvas.bind("<Button-5>", lambda e: self._scroll(1))
        except Exception:
            pass

    def _measure(self) -> int:
        try:
            import tkinter.font as _tf
            return int(_tf.Font(font=self._font).metrics("linespace")) + 8
        except Exception:
            return 22

    # ----- datos -----
    def delete(self, a, b=None) -> None:
        try:
            self._items = []
            self._sel = -1
            self._top = 0
            self._redraw()
        except Exception:
            pass

    def insert(self, index, s) -> None:
        try:
            self._items.append(str(s))
            self._redraw()
        except Exception:
            pass

    def get(self, i: int) -> str:
        try:
            return self._items[int(i)]
        except Exception:
            return ""

    def curselection(self):
        try:
            return (int(self._sel),) if 0 <= int(self._sel) < len(self._items) else ()
        except Exception:
            return ()

    def bind(self, sequence=None, func=None, add=None):  # type: ignore[override]
        try:
            if sequence == "<<ListboxSelect>>" and callable(func):
                self._handlers.append(func)
                return None
            return super().bind(sequence, func, add)
        except Exception:
            return None

    def configure(self, **kw):  # type: ignore[override]
        try:
            if "bg" in kw:
                self._bg = str(kw.pop("bg"))
                try:
                    self._canvas.configure(bg=self._bg)
                except Exception:
                    pass
            if "fg" in kw:
                self._fg = str(kw.pop("fg"))
            if "font" in kw:
                self._font = kw.pop("font")
                try:
                    self._row_h = self._measure()
                except Exception:
                    pass
            if "selectbackground" in kw:
                try:
                    self._selfg = str(kw.pop("selectbackground"))
                except Exception:
                    kw.pop("selectbackground", None)
            kw.pop("selectforeground", None)
            kw.pop("highlightthickness", None)
            if kw:
                try:
                    super().configure(**kw)
                except Exception:
                    pass
            self._redraw()
        except Exception:
            pass
    config = configure

    def cget(self, key):  # type: ignore[override]
        try:
            if key == "bg":
                return self._bg
            if key == "fg":
                return self._fg
            if key == "font":
                return self._font
            return super().cget(key)
        except Exception:
            return ""

    # ----- background -----
    def set_background(self, pil_img) -> None:
        """Background PIL.Image (or None). Re-scaled when painting."""
        try:
            self._bg_pil = pil_img
            self._bg_photo = None
            self._redraw()
        except Exception:
            pass

    # ----- dibujo -----
    def _visible_rows(self) -> int:
        try:
            h = int(self._canvas.winfo_height() or 0)
            if h < 10:
                return 8
            return max(1, h // max(8, int(self._row_h)))
        except Exception:
            return 8

    def _redraw(self) -> None:
        try:
            c = self._canvas
            c.delete("all")
            W = max(50, int(c.winfo_width() or 180))
            H = max(30, int(c.winfo_height() or 180))
            # background: real resized image (cached by size)
            try:
                if self._bg_pil is not None:
                    key = (int(W), int(H))
                    if getattr(self, "_bg_key", None) != key:
                        self._bg_photo = None
                        self._bg_key = key
                    if self._bg_photo is None:
                        from PIL import ImageTk
                        self._bg_photo = ImageTk.PhotoImage(
                            self._bg_pil.convert("RGB").resize((W, H)))
                    c.create_image(0, 0, anchor="nw", image=self._bg_photo)
            except Exception:
                pass
            n = self._visible_rows()
            top = max(0, min(int(self._top), max(0, len(self._items) - 1)))
            self._top = top
            for r in range(n):
                i = top + r
                if i >= len(self._items):
                    break
                y = r * int(self._row_h)
                if i == self._sel:
                    try:
                        c.create_rectangle(0, y, W, y + int(self._row_h),
                                           fill=self._selfg, outline="")
                    except Exception:
                        pass
                try:
                    c.create_text(6, y + int(self._row_h) // 2, anchor="w",
                                  text=self._items[i], fill=self._fg, font=self._font)
                except Exception:
                    pass
        except Exception:
            pass

    def _click(self, event=None) -> None:
        try:
            y = int(getattr(event, "y", 0) or 0)
            i = int(self._top) + max(0, y // max(8, int(self._row_h)))
            if 0 <= i < len(self._items):
                self._sel = i
                self._redraw()
                for h in list(self._handlers):
                    try:
                        h(event)
                    except Exception:
                        pass
        except Exception:
            pass

    def _wheel(self, event=None) -> None:
        try:
            d = int(getattr(event, "delta", 0) or 0)
            self._scroll(-1 if d > 0 else 1)
        except Exception:
            pass

    def _scroll(self, d: int) -> None:
        try:
            self._top = max(0, int(self._top) + int(d))
            self._redraw()
        except Exception:
            pass


class MainWindow:
    def __init__(self, theme: ThemeManager, client: YouTubeClient, player: PlayerEngine):
        self.theme = theme
        self.client = client
        self.player = player
        self.root = tk.Tk()
        # Continuation tracks: recommendations to play after the queue ends
        self._continuation_tracks: list[dict] = []
        # Separator row of the continuation (recommendations) section.
        self._cont_separator = None
        # Callback when queue ends: add continuation tracks and keep playing
        self.player.on_queue_end = self._on_queue_end_continuation
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # No local data: liked = YT Music "Liked songs"
        # (liked via API) and playlists = YT Music only. Never reads nor writes
        # config/favoritas.json nor config/playlists.json.
        self.favs_path = "config/favoritas.json"
        self.playlists_path = "config/playlists.json"
        self.favs: list[dict] = []
        self.local_playlists: dict = {}
        # YT Music liked cache to paint ♥/♡ without network calls per row
        self._liked_ids: set[str] = set()
        # Last.fm "played N times" per videoId + the labels to repaint
        self._play_counts: dict[str, int] = {}
        self._play_labels: dict[str, list] = {}
        self._rendered_visible: list = []
        self._rendered_ids: set = set()
        self._rendered_keys: list = []
        self._pc_queue: list = []
        self._pc_busy: bool = False
        self._channel_queue: list = []
        self._channel_busy: bool = False
        self._channel_windows: dict = {}
        # Last.fm scrobbling + per-song data
        self.lastfm = LastFMClient()
        # Per-song data store: local-cache.json {videoId: {...}}.
        # Edited song -> its saved data; anything else -> song default.
        self._songmap: dict | None = None
        self._songmap_raw: dict = {}
        self._songmap_mtime: float = 0.0
        try:
            self._load_songmap()
        except Exception:
            pass
        self._scrobble_key = ""
        self._play_start_ts = 0
        self.current_list: list[dict] = []
        self.current_list_full: list[dict] = []
        self.visible_count: int = int(theme.get("lista", "lote_progresivo", default=80) or 80)
        self._progressive_token: int = 0
        self._loading_progressive: bool = False
        self._rendering_batch: bool = False
        self.current_section = "buscar"
        self.current_playlist_id = ""
        self.pl_kind: str | None = None  # 'yt' | None (no local lists)
        self.pl_id: str = ""
        self.pl_title: str = ""
        self.playlist_grid_view: bool = False  # False=list, True=grid (legacy mirror)
        self.playlist_view_mode: str = str(theme.get("lista", "vista_playlists", default="list") or "list")  # list|grid|custom
        if self.playlist_view_mode not in ("list", "grid", "custom"):
            self.playlist_view_mode = "list"
        self.playlist_grid_view = (self.playlist_view_mode != "list")
        self._grid_bind_ok = False
        self._grid_conf_after = None
        self._open_autoplay: str = ""
        self._pl_covers: dict[str, str] = {}
        try:
            self._pl_covers = self._pl_covers_load()
        except Exception:
            self._pl_covers = {}
        self.thumb_cache: dict[str, object] = {}
        self.bg_video_running = False
        self._seeking = False
        # Visual engine: current background image + bands + button images
        self._bg_pil = None
        self._bg_bands: list[str] = []
        self._btn_images: dict[int, tuple] = {}  # id(btn) -> (normal, hover)
        self._shape_cache: dict[str, object] = {}
        self._icon_cache: dict[str, object] = {}
        self._canvas_bg_id = None
        self._canvas_bg_photo = None
        self._yt_pl_cache: list[dict] = []
        self._ui_queue: queue.Queue = queue.Queue()
        self._closed = False
        # Video panel (draggable/resizable inside the window)
        self._video_panel = None
        self._video_label = None
        self._video_title = None
        self._video_bar = None
        self._video_grip = None
        self._video_pnl = None
        self._video_fullscreen = False
        self._video_prev_geom: str | None = None
        self._video_pw = 320
        self._video_ph = 180
        self._video_resize_timer = None
        self._video_photo = None
        self._video_running = False
        self._video_thread = None
        self._video_video_id = ""
        # Floating stickers (Toplevels that follow the window, may leave it)
        self._stickers: list[dict] = []  # {win, label, cfg, photo}
        # Video/sticker stacking order: only reordered when our
        # app is in the foreground (no blind flickering lifts).
        self._overlay_order_ok = False
        self._vol_save_timer = None
        try:
            self._cookies_mtime: float = os.path.getmtime(client.cookies_json_path)
        except Exception:
            self._cookies_mtime = -1.0
        self._build_ui()
        self._pump_ui()
        self.apply_theme()
        # Restore stickers from the initial theme once at startup.
        try:
            self._restore_stickers()
        except Exception:
            pass
        self.root.after(3000, self._initial_heal)
        self.player.on_track_change = self._on_track_change_ui
        self.player.on_state_change = self._on_state_change_ui
        self._tick()

    # ---------- local persistence ----------
    @staticmethod
    def _load_json(path, default):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _save_json(self, path, data) -> None:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- UI ----------
    def _build_ui(self) -> None:
        t = self.theme.data
        self.root.title(t["ventana"]["titulo"])
        self._want_size = (int(t["ventana"]["ancho"]), int(t["ventana"]["alto"]))
        self.root.geometry(f"{self._want_size[0]}x{self._want_size[1]}")
        # No white line: dark background from the first frame (before the
        # first apply_theme) + no system borders/highlights.
        try:
            _base_bg = str((t.get("lista") or {}).get("color_fondo") or "#1a1a1a")
        except Exception:
            _base_bg = "#1a1a1a"
        try:
            self.root.configure(bg=_base_bg, bd=0, highlightthickness=0)
        except Exception:
            pass

        # Background (canvas/label at the back)
        self.bg_label = tk.Label(self.root, bg=_base_bg, bd=0, highlightthickness=0)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Main container above the background
        self.main = tk.Frame(self.root, bg=_base_bg, bd=0, highlightthickness=0)
        self.main.place(x=0, y=0, relwidth=1, relheight=1)

        # Custom title bar (no default Windows frame)
        self._frameless = "native"
        self._maximized = False
        self._prev_geom: str | None = None
        self._need_override = False
        self.titlebar = None
        if self.theme.get("ventana", "barra_personalizada", default=True):
            self._build_titlebar()

        # Top bar
        self.topbar = tk.Frame(self.main)
        self.topbar.pack(fill="x", padx=10, pady=(10, 4))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.topbar, textvariable=self.search_var, width=40)
        self.search_entry.pack(side="left", padx=(0, 6), ipady=5)
        self.search_entry.bind("<Return>", lambda e: self.do_search())
        self.btn_search = tk.Button(self.topbar, text="⌕", command=self.do_search)
        self.btn_search.pack(side="left", padx=2)
        self.btn_openurl = tk.Button(self.topbar, text="↗ URL", command=self.open_url_dialog)
        self.btn_openurl.pack(side="left", padx=2)
        self.account_label = tk.Label(self.topbar, text="...")
        self.account_label.pack(side="left", padx=12)
        try:
            self.account_label.configure(cursor="hand2")
            self.account_label.bind("<Button-1>", lambda e: self.open_settings())
        except Exception:
            pass
        self.btn_customize = tk.Button(self.topbar, text="◐ Customize", command=self.open_customize)
        self.btn_customize.pack(side="right", padx=4)
        self.btn_settings = tk.Button(self.topbar, text="⚙︎", command=self.open_settings)
        self.btn_settings.pack(side="right", padx=4)
        self.btn_songedit = tk.Button(self.topbar, text="✎", command=self.open_song_edit_dialog)
        self.btn_songedit.pack(side="right", padx=4)
        for _b in (self.btn_search, self.btn_openurl, self.btn_customize, self.btn_settings,
                   self.btn_songedit):
            self._install_hover(_b)

        # Body: sidebar + list
        self.body = tk.Frame(self.main)
        self.body.pack(fill="both", expand=True, padx=10, pady=4)

        self.sidebar = tk.Frame(self.body, width=190)
        self.sidebar.pack(side="left", fill="y", padx=(0, 8))
        self.sidebar.pack_propagate(False)
        self.side_buttons: dict[str, tk.Button] = {}
        # No local data: YT Music sections + play queue only.
        self._side_labels = {"inicio": "⌂ Home", "explorar": "⌕ Explore",
                             "buscar": "⌕ Search", "playlists": "☰ Playlists",
                             "favoritas": "♥ Liked", "cola": "↳ Queue"}
        order = self.theme.get("sidebar_orden", default=None) or ["inicio", "buscar", "playlists", "favoritas", "cola", "explorar"]
        # Sanitize order (old themes may still carry "locales")
        try:
            order = [k for k in list(order or []) if k in self._side_labels]
        except Exception:
            order = ["inicio", "buscar", "playlists", "favoritas", "cola", "explorar"]
        for _k in list(self._side_labels.keys()):
            if _k not in order:
                order.append(_k)
        order = [k for k in order if k in self._side_labels]
        for key in order:
            b = tk.Button(self.sidebar, text=self._side_labels[key], anchor="w",
                          command=lambda k=key: self.show_section(k))
            b.pack(fill="x", pady=2, ipady=6)
            self.side_buttons[key] = b
            self._install_hover(b)
            self._make_sidebar_draggable(b, key)
        tk.Label(self.sidebar, text="").pack(pady=4)
        self.btn_newlist = tk.Button(self.sidebar, text="+ New YT playlist", command=self.create_yt_playlist_ui)
        self.btn_newlist.pack(fill="x", pady=2)
        self._install_hover(self.btn_newlist)
        self.playlist_box = _BgListbox(self.sidebar)
        self.playlist_box.pack(fill="both", expand=True, pady=4)
        self.playlist_box.bind("<<ListboxSelect>>", self._on_library_select)

        # List panel
        self.listpanel = tk.Frame(self.body)
        self.listpanel.pack(side="left", fill="both", expand=True)
        self.list_title = tk.Label(self.listpanel, text="Search songs or open a playlist", anchor="w")
        self.list_title.pack(fill="x", pady=(0, 4))
        # Scrollable (background does not scroll, mouse wheel enabled)
        self.canvas = tk.Canvas(self.listpanel, highlightthickness=0)
        self.scroll = tk.Scrollbar(self.listpanel, orient="vertical", command=self._canvas_yview)
        self.listframe = tk.Frame(self.canvas)
        self.listframe.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._listframe_win = self.canvas.create_window((0, 0), window=self.listframe, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self._bind_wheel(self.canvas)
        self._bind_wheel(self.listframe)
        self.row_widgets: list[tk.Frame] = []
        self._drag_row = None
        self._drag_start_xy = None
        self._drag_moved = False
        # Capturar TODOS los eventos de mouse desde el root para que el
        # arrastrar funcione desde cualquier parte de cualquier fila.
        self.root.bind("<Button-1>", self._root_press, add="+")
        self.root.bind("<B1-Motion>", self._root_motion, add="+")
        self.root.bind("<ButtonRelease-1>", self._root_release, add="+")

        # Player bar
        self.playerbar = tk.Frame(self.main)
        self.playerbar.pack(fill="x", padx=10, pady=(4, 10))
        # --- Controls are packed FIRST (right side) so they are NEVER
        # squeezed out by a narrow window. The middle (progress bar)
        # gets whatever is left and shrinks if needed. ---
        volf = tk.Frame(self.playerbar)
        volf.pack(side="right", padx=(8, 0))
        self.vol_icon = tk.Label(volf, text="♪")
        self.vol_icon.pack(side="left")
        self.volf = volf
        self.btn_vol_down = tk.Button(volf, text="−",
                                      command=lambda: self._vol_step(-0.2))
        self.btn_vol_down.pack(side="left", padx=1)
        self._install_hover(self.btn_vol_down)
        self.vol_var = tk.DoubleVar(
            value=float(self.theme.get("reproductor", "volumen_defecto",
                                       default=70) or 70))
        self.vol_scale = tk.Scale(volf, from_=0, to=100, resolution=0.2,
                                  orient="horizontal", variable=self.vol_var,
                                  showvalue=False, length=100,
                                  command=lambda v: self._on_volume_change(
                                      float(v)))
        self.vol_scale.pack(side="left")
        self.btn_vol_up = tk.Button(volf, text="+",
                                    command=lambda: self._vol_step(0.2))
        self.btn_vol_up.pack(side="left", padx=1)
        self._install_hover(self.btn_vol_up)
        self.vol_value = tk.Label(volf, text="", width=6)
        self.vol_value.pack(side="left")

        ctrl = tk.Frame(self.playerbar)
        ctrl.pack(side="right", padx=(8, 0))
        self._ctrl_frame = ctrl
        self.btn_prev = tk.Button(ctrl, text="◀◀", command=self.player.prev)
        self.btn_play = tk.Button(ctrl, text="▶", command=self.player.toggle)
        self.btn_next = tk.Button(ctrl, text="▶▶", command=self.player.next)
        self.btn_shuffle = tk.Button(ctrl, text="⇄○",
                                     command=self.toggle_shuffle)
        self.btn_loop = tk.Button(ctrl, text="↻○", command=self.cycle_loop)
        self.btn_fav = tk.Button(ctrl, text="♡",
                                 command=self.toggle_fav_current)
        for b in (self.btn_prev, self.btn_play, self.btn_next,
                  self.btn_shuffle, self.btn_loop, self.btn_fav):
            b.pack(side="left", padx=3)

        # Thumbnail on the left.
        self.thumb_label = tk.Label(self.playerbar, text="♪", bd=0,
                                      highlightthickness=0)
        self.thumb_label.pack(side="left", padx=(0, 8))
        # Middle: song info + progress bar. Expands into leftover space.
        mid = tk.Frame(self.playerbar)
        mid.pack(side="left", fill="both", expand=True)
        self.song_label = tk.Label(mid, text="Nothing playing", anchor="w")
        self.song_label.pack(fill="x")
        self.playcount_lbl = tk.Label(mid, text="", anchor="w",
                                      font=("Segoe UI", 9))
        self.playcount_lbl.pack(fill="x")
        prog = tk.Frame(mid)
        prog.pack(fill="x")
        self.time_a = tk.Label(prog, text="0:00", width=7)
        self.time_a.pack(side="left")
        self.progress = tk.Scale(prog, from_=0, to=100, orient="horizontal",
                                 showvalue=False)
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress.bind("<ButtonPress-1>", self._on_progress_press)
        self.progress.bind("<ButtonRelease-1>", self._on_seek_release)
        self.time_b = tk.Label(prog, text="0:00", width=7)
        self.time_b.pack(side="left")

        # Responsive: keep the progress bar from eating the controls on
        # narrow windows. Recompute the usable width on every resize.
        self._player_prog_frame = prog
        self._player_mid_frame = mid
        self._playerbar_resize_job = None
        self.playerbar.bind("<Configure>", self._on_playerbar_resize)
        self._apply_playerbar_responsive()

        # Sync engine with the saved volume at startup
        try:
            self.player.set_volume(float(self.vol_var.get()))
            self._update_vol_label(float(self.vol_var.get()))
        except Exception:
            pass

        self.status = tk.Label(self.main, text="Ready", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 6))
        self._player_mid = [mid, prog, volf, self.vol_icon]
        for b in (self.btn_prev, self.btn_play, self.btn_next,
                  self.btn_shuffle, self.btn_loop, self.btn_fav):
            self._install_hover(b)
        self._apply_frameless()
        # Icon for the taskbar / Alt+Tab (the Windows caption is gone, so the
        # icon has to be set explicitly or the app shows a blank one).
        try:
            self._apply_app_icon(self.root)
        except Exception:
            pass
        # The WM resizes the window when the caption is removed; put the saved
        # size back so restarts land on exactly the same geometry.
        try:
            self.root.after(80, self._restore_size_after_map)
        except Exception:
            pass
        self.account_label.config(text=self.client.account_label)
        self.refresh_library_list()
        # Video/cover panel + stickers + infinite scroll (after base theme)
        self._more_btn_row = None
        # ---- Virtualized list -------------------------------------------
        # A playlist with 5 000 songs must NEVER build 5 000 rows: that
        # froze the UI for seconds and eventually killed the process. Only a
        # window of rows is alive at any time; the rest of the list is data.
        self.MAX_LIVE_ROWS = 200          # hard cap of live row widgets
        self._window_start = 0            # first BASE track painted
        self._base_window = 0             # how many BASE tracks are painted
        self._sep_visual_pos = 0          # visible track rows above the sep.
        self._painted_order: list = []    # painted tracks, in visual order
        self._row_pool: list = []         # spare row frames (re-used)
        try:
            self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        except Exception:
            pass
        # Periodic near-bottom scroll check for infinite loading
        try:
            self.root.after(1500, self._autocheck_more)
        except Exception:
            pass

    # ----- custom title bar -----
    def _build_titlebar(self) -> None:
        try:
            try:
                _tbg = str((self.theme.data.get("lista") or {}).get("color_fondo") or "#1a1a1a")
            except Exception:
                _tbg = "#1a1a1a"
            bar = tk.Frame(self.main, height=34, bg=_tbg, bd=0,
                           highlightthickness=0)
            bar.pack(fill="x", side="top", padx=0, pady=0)
            bar.pack_propagate(False)
            self.titlebar = bar
            # App icon at the left of our own bar (the Windows caption is
            # gone, so without this the window had no icon at all).
            try:
                ipath = self._app_icon_path()
                if ipath:
                    from PIL import Image, ImageTk
                    self._title_icon = ImageTk.PhotoImage(
                        Image.open(ipath).convert("RGBA")
                        .resize((22, 22), Image.LANCZOS))
                    ico = tk.Label(bar, image=self._title_icon, bd=0,
                                   bg=_tbg, highlightthickness=0)
                    ico.pack(side="left", padx=(6, 2), pady=4)
                    ico.bind("<ButtonPress-1>", self._drag_start)
                    ico.bind("<B1-Motion>", self._drag_move)
                    ico.bind("<Double-Button-1>",
                             lambda e: self._toggle_maximize())
            except Exception:
                pass
            self.title_label = tk.Label(bar, text=self.theme.data["ventana"]["titulo"],
                                        anchor="w", font=("Segoe UI", 10, "bold"),
                                        bg=_tbg, bd=0, highlightthickness=0)
            self.title_label.pack(side="left", padx=6, pady=0)
            self.win_close = tk.Button(bar, text="✕", command=self._close_win,
                                       relief="flat", bd=0, highlightthickness=0,
                                       activebackground="#7f3b36")
            self.win_max = tk.Button(bar, text="▢", command=self._toggle_maximize,
                                     relief="flat", bd=0, highlightthickness=0)
            self.win_min = tk.Button(bar, text="─", command=self._minimize_win,
                                     relief="flat", bd=0, highlightthickness=0)
            for b in (self.win_close, self.win_max, self.win_min):
                b.pack(side="right", padx=1, pady=0)
                self._install_hover(b)
            bar.bind("<ButtonPress-1>", self._drag_start)
            bar.bind("<B1-Motion>", self._drag_move)
            self.title_label.bind("<ButtonPress-1>", self._drag_start)
            self.title_label.bind("<B1-Motion>", self._drag_move)
            bar.bind("<Double-Button-1>", lambda e: self._toggle_maximize())
            self.title_label.bind("<Double-Button-1>", lambda e: self._toggle_maximize())
        except Exception:
            self.titlebar = None

    def _apply_dwm_chrome(self) -> None:
        """Tints the native 1px frame with the theme color (Windows 10/11).

        Removing WS_CAPTION leaves the resize border (WS_THICKFRAME) which DWM
        paints WHITE: that is the 'white line' above ─/▢/✕. With
        DWMWA_BORDER_COLOR (34) and DWMWA_CAPTION_COLOR (35) it takes the theme
        color and disappears. Silent on old Windows (errors ignored).
        """
        if os.name != "nt":
            return
        try:
            import ctypes
            try:
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            except Exception:
                return
            if not hwnd:
                return
            try:
                hexcol = str(self.theme.get("lista", "color_fondo",
                                            default="#1a1a1a") or "#1a1a1a")
            except Exception:
                hexcol = "#1a1a1a"
            try:
                r, g, b = _hex_to_rgb(hexcol)
            except Exception:
                r, g, b = (20, 16, 31)
            colorref = (int(b) << 16) | (int(g) << 8) | int(r)
            for _attr in (34, 35):  # BORDER_COLOR, CAPTION_COLOR
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, _attr, ctypes.byref(ctypes.c_uint(colorref)),
                        ctypes.sizeof(ctypes.c_uint))
                except Exception:
                    pass
        except Exception:
            pass

    def _try_borderless_win(self) -> bool:
        """Remove WS_CAPTION keeping taskbar+resize. Verify it worked."""
        if os.name != "nt":
            return False
        try:
            import ctypes
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                return False
            GWL_STYLE = -16
            WS_CAPTION = 0x00C00000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            if not style or not (style & WS_CAPTION):
                return bool(style)  # already captionless = ok
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style & ~WS_CAPTION)
            SWP = 0x0001 | 0x0002 | 0x0004 | 0x0020
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP)
            check = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            _ok = bool(check and not (check & WS_CAPTION))
            if _ok:
                try:
                    self._apply_dwm_chrome()
                except Exception:
                    pass
            return _ok
        except Exception:
            return False

    def _win_border_color(self) -> int:
        """Theme colour for the 1px native frame (DWMWA_BORDER_COLOR)."""
        try:
            hexcol = str(self.theme.get("lista", "color_fondo", default="#1a1a1a")
                         or "#1a1a1a")
            r, g, b = _hex_to_rgb(hexcol)
            return (int(b) << 16) | (int(g) << 8) | int(r)
        except Exception:
            return (31 << 16) | (16 << 8) | 20

    def _app_icon_path(self) -> str:
        """Icon for the window/title bar.

        Prefers the shipped .ico (Windows keeps every resolution inside it)
        and falls back to the PNG. The theme key `ventana.icono` wins when
        it points at a real file, so the user can use their own image.
        """
        try:
            p = str(self.theme.get("ventana", "icono", default="") or "")
            if p and os.path.exists(p):
                return p
        except Exception:
            pass
        for cand in ("assets/icons/app.ico", "assets/icons/app.png",
                     "assets/icons/app_64.png"):
            if os.path.exists(cand):
                return cand
        # nothing yet: draw one that matches the theme
        try:
            from app.appicon import build
            return build().get("ico") or build().get("png") or ""
        except Exception:
            return ""

    def _pick_app_icon(self, swatch=None) -> None:
        """Let the user use their own image as the window icon."""
        from tkinter import filedialog
        p = filedialog.askopenfilename(
            title="App icon for the window",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                       ("All", "*.*")])
        if not p:
            return
        self.theme.set(p, "ventana", "icono")
        try:
            self.theme.save()
        except Exception:
            pass
        self._apply_app_icon(self.root)
        for w in list((getattr(self, "_channel_windows", {}) or {}).values()):
            try:
                self._apply_app_icon(w)
            except Exception:
                pass
        if swatch is not None:
            try:
                swatch.configure(image="", text=" \u2713 ")
            except Exception:
                pass
        try:
            self.status.configure(text="App icon updated.")
        except Exception:
            pass

    def _reset_app_icon(self, swatch=None) -> None:
        """Go back to the theme-coloured generated icon."""
        try:
            self.theme.set("", "ventana", "icono")
            self.theme.save()
        except Exception:
            pass
        # Regenerate the shipped icon instead of deleting it: it is part of
        # the app, not a user file.
        try:
            from app.appicon import build
            build()
        except Exception:
            pass
        self._apply_app_icon(self.root)
        for w in list((getattr(self, "_channel_windows", {}) or {}).values()):
            try:
                self._apply_app_icon(w)
            except Exception:
                pass
        try:
            self.status.configure(text="Default icon rebuilt from the theme.")
        except Exception:
            pass

    def _apply_app_icon(self, win) -> bool:
        """Put the app icon on a window (title bar + Alt+Tab).

        Must run on the main thread: Tk images cannot be built elsewhere.
        """
        path = self._app_icon_path()
        if not path or win is None:
            return False
        try:
            if path.lower().endswith(".ico"):
                # Tk loads a .ico natively and keeps every size in it.
                win.iconbitmap(path)
                win._app_icon_photo = True
            else:
                from PIL import Image, ImageTk
                img = Image.open(path).convert("RGBA").resize(
                    (64, 64), Image.LANCZOS)
                # Keep a reference or Tk garbage-collects the image.
                win._app_icon_photo = ImageTk.PhotoImage(img)
                win.iconbitmap(win._app_icon_photo)
            try:
                win.wm_iconname(str(self.theme.get("ventana", "titulo",
                                                   default="OpenYTPlayer")))
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _frameless_toplevel(self, win, own_bar: bool = False) -> None:
        """App icon on a window; and NO Windows caption when it draws its own.

        own_bar=True is only for windows that paint a custom title bar (the
        channel window): there the Windows caption was showing ON TOP of it,
        so you saw two bars and the Windows one had no icon. Dialogs keep
        their native bar because that is what gives them the close button.
        """
        if win is None:
            return
        try:
            self._apply_app_icon(win)
        except Exception:
            pass
        if not own_bar:
            return
        if os.name != "nt":
            try:
                win.overrideredirect(True)
            except Exception:
                pass
            return
        # A Toplevel's native HWND only exists once it is realised, so the
        # caption has to be removed after the map. Bind ONCE: re-binding from
        # inside the handler loops forever.
        try:
            if not getattr(win, "_caption_binding_done", False):
                win._caption_binding_done = True
                win.bind("<Map>",
                         lambda e, w=win: self._strip_caption(w), add="+")
        except Exception:
            pass
        try:
            win.after_idle(lambda w=win: self._strip_caption(w))
        except Exception:
            pass
        self._strip_caption(win)

    def _strip_caption(self, win) -> bool:
        """Remove WS_CAPTION from a realised window. True when it worked."""
        if os.name != "nt":
            return False
        try:
            import ctypes
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            if not hwnd:
                return False
            GWL_STYLE = -16
            WS_CAPTION = 0x00C00000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            if not style or not (style & WS_CAPTION):
                return bool(style)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE,
                                               style & ~WS_CAPTION)
            SWP = 0x0001 | 0x0002 | 0x0004 | 0x0020
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP)
            try:
                colorref = self._win_border_color()
                for attr in (34, 35):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(ctypes.c_int(colorref)),
                        ctypes.sizeof(ctypes.c_int))
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _apply_frameless(self) -> None:
        """Remove the default frame. On Windows keep taskbar+resize (no caption);
        on other systems use overrideredirect as fallback."""
        if self.titlebar is None:
            self._frameless = "native"
            return
        if os.name == "nt" and self._try_borderless_win():
            self._frameless = "win"
            return
        if os.name == "nt":
            # The real window does not exist yet: retry on map (HWND is final there).
            self._frameless = "pending"
            try:
                self.root.bind("<Map>", self._on_first_map_frameless, add="+")
            except Exception:
                pass
            return
        try:
            self.root.overrideredirect(True)
            self._frameless = "override"
            self.root.bind("<Map>", self._on_map_override)
        except Exception:
            self._frameless = "native"

    def _caption_present_now(self) -> bool | None:
        """Read the REAL window style (None if unavailable)."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                return None
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            if not style:
                return None
            return bool(style & 0x00C00000)
        except Exception:
            return None

    def _on_first_map_frameless(self, event=None) -> None:
        # Do not trust the flag: check the REAL caption (the build HWND
        # may be transient and give false positives).
        try:
            cap = self._caption_present_now() if os.name == "nt" else False
            if cap is False and getattr(self, "_frameless", "") == "win":
                try:
                    self._apply_dwm_chrome()
                except Exception:
                    pass
                return  # verified: no caption
            if os.name == "nt" and self._try_borderless_win():
                self._frameless = "win"
            else:
                try:
                    self.root.overrideredirect(True)
                    self._frameless = "override"
                    self.root.bind("<Map>", self._on_map_override)
                except Exception:
                    self._frameless = "native"
            try:
                self.status.configure(text=f"Window frame: {self._frameless}")
            except Exception:
                pass
        except Exception:
            pass

    def _on_map_override(self, event=None) -> None:
        try:
            if getattr(self, "_need_override", False):
                self._need_override = False
                self.root.overrideredirect(True)
        except Exception:
            pass

    def _drag_start(self, event=None) -> None:
        try:
            if self._maximized:
                self._toggle_maximize()
                return
            if self._frameless == "win" and os.name == "nt":
                # NATIVE Windows dragging: smooth, with Aero Snap and no tearing
                # (moving via manual geometry() is what breaks the image).
                # NOTE: PostMessage (async), NEVER SendMessage: the modal loop
                # reentrant SendMessage breaks the GIL and aborts the process.
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                    ctypes.windll.user32.ReleaseCapture()
                    ctypes.windll.user32.PostMessageW(hwnd, 0x00A1, 0x02, 0)
                    return
                except Exception:
                    pass
            self._dx = event.x_root - self.root.winfo_x()
            self._dy = event.y_root - self.root.winfo_y()
            self._last_move = 0.0
        except Exception:
            pass

    def _drag_move(self, event=None) -> None:
        try:
            if self._frameless == "win":
                return  # native dragging already moves the window
            now = time.time()
            if now - getattr(self, "_last_move", 0.0) < 0.03:
                return  # throttle: max ~33 moves/s
            self._last_move = now
            self.root.geometry(f"+{event.x_root - self._dx}+{event.y_root - self._dy}")
        except Exception:
            pass

    def _toggle_maximize(self) -> None:
        try:
            if not self._maximized:
                try:
                    self._prev_geom = self.root.geometry()
                except Exception:
                    self._prev_geom = None
                if self._frameless == "override":
                    sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                    self.root.geometry(f"{sw}x{sh}+0+0")
                else:
                    self.root.state("zoomed")
                self._maximized = True
            else:
                if self._frameless == "override" and self._prev_geom:
                    self.root.geometry(self._prev_geom)
                else:
                    try:
                        self.root.state("normal")
                    except Exception:
                        pass
                    if self._prev_geom:
                        try:
                            self.root.geometry(self._prev_geom)
                        except Exception:
                            pass
                self._maximized = False
            self._paint_all_buttons()
            # Reposition video panel when maximizing/restoring
            try:
                self._reposition_video()
            except Exception:
                pass
            # Hide stickers when maximized, show when restored
            try:
                if self._maximized:
                    for st in list(getattr(self, "_stickers", []) or []):
                        try:
                            st.get("win").withdraw()
                        except Exception:
                            pass
                else:
                    for st in list(getattr(self, "_stickers", []) or []):
                        try:
                            st.get("win").deiconify()
                        except Exception:
                            pass
            except Exception:
                pass
            # Force video panel to refresh its size when maximizing/restoring
            try:
                self.root.after(100, self._refresh_video_panel)
            except Exception:
                pass
        except Exception:
            pass

    def _reposition_video(self) -> None:
        """Reposition video panel relative to main window, handling maximized state."""
        try:
            if getattr(self, "_video_fullscreen", False):
                return
            win = getattr(self, "_video_panel", None)
            if win is None:
                return
            try:
                win.winfo_exists()
            except Exception:
                return
            try:
                if not bool(self.theme.get("video_panel", "visible", default=True)):
                    return
            except Exception:
                pass
            # Get absolute position
            try:
                rx, ry = self.root.winfo_x(), self.root.winfo_y()
            except Exception:
                rx, ry = 100, 100
            cfg = self.theme.data.get("video_panel", {}) or {}
            try:
                dx = int(cfg.get("dx", cfg.get("x", 620)))
            except Exception:
                dx = 620
            try:
                dy = int(cfg.get("dy", cfg.get("y", 120)))
            except Exception:
                dy = 120
            try:
                w, h = int(cfg.get("w", 320)), int(cfg.get("h", 240))
            except Exception:
                w, h = 320, 240
            # If maximized, position video to cover bottom-right area of screen
            try:
                if self._maximized:
                    sw = self.root.winfo_screenwidth() or 1280
                    sh = self.root.winfo_screenheight() or 720
                    # Place video in bottom-right corner, slightly smaller than screen
                    vw = min(w, sw - 20)
                    vh = min(h, sh - 20)
                    vx = sw - vw - 10
                    vy = sh - vh - 10
                    win.geometry(f"{vw}x{vh}+{vx}+{vy}")
                    return
            except Exception:
                pass
            ax, ay = rx + dx, ry + dy
            win.geometry(f"{w}x{h}+{ax}+{ay}")
        except Exception:
            pass

    def _minimize_win(self) -> None:
        try:
            if self._frameless == "override":
                self._need_override = True
                self.root.overrideredirect(False)
                self.root.iconify()
            else:
                self.root.iconify()
        except Exception:
            pass

    def _close_win(self) -> None:
        self._save_geometry()
        self.on_close()

    def _restore_size_after_map(self, tries: int = 14) -> None:
        """Force the window back to the saved size once it is really mapped.

        Removing WS_CAPTION makes Windows re-add the resize border, and the WM
        then grows the window by 2px on EVERY restart, so the saved size never
        seemed to stick.

        Only the WIDTH delta is fed back: that border is a stable +2, while the
        height is transiently clamped by the WM until the layout settles, and
        correcting that error as well made the window oscillate between two
        sizes (up and down, forever).
        """
        try:
            want = getattr(self, "_want_size", None)
            if not want:
                return
            w, h = int(want[0]), int(want[1])
            cw = self.root.winfo_width()
            ch = self.root.winfo_height()
            if w < 200 or h < 200:
                return
            if (cw, ch) == (w, h):
                self._size_locked = True
                return
            adj_w = max(200, w - (cw - w))
            try:
                self.root.geometry(f"{adj_w}x{h}")
            except Exception:
                return
            if tries > 0:
                try:
                    self.root.after(150, self._restore_size_after_map, tries - 1)
                    return
                except Exception:
                    return
            self._size_locked = True
        except Exception:
            pass
            pass

    def _save_geometry(self) -> None:
        try:
            if self._maximized:
                return
            # winfo_width/height is the CLIENT area, so it round-trips
            # exactly; root.geometry() includes the WM's invisible border
            # (2px per side on Windows) and drifted on every restart.
            try:
                w = int(self.root.winfo_width())
                h = int(self.root.winfo_height())
            except Exception:
                w = h = 0
            if w < 200 or h < 200:
                g = self.root.geometry()  # "WIDTHxHEIGHT+X+Y"
                wh = g.split("+")[0]
                gw, gh = wh.split("x")
                w, h = int(gw), int(gh)
            if w < 200 or h < 200:
                return  # minimized / no real geometry: do not save garbage
            # Save in the working theme (config/theme.json) so it persists
            # across restarts regardless of which theme package is active.
            self.theme.set(w, "ventana", "ancho")
            self.theme.set(h, "ventana", "alto")
            self.theme.save()
            # Also save in the active theme package file for persistence
            active = ThemeManager.get_active_theme() or "theme1"
            theme_file = os.path.join("themes", active, "theme.json")
            if os.path.isfile(theme_file):
                t = ThemeManager(theme_file)
                t.set(w, "ventana", "ancho")
                t.set(h, "ventana", "alto")
                t.save()
        except Exception:
            pass

    # ---------- themes / visual engine ----------
    def apply_theme(self) -> None:
        d = self.theme.data
        v = d["ventana"]
        self.root.title(v["titulo"])
        # Custom font (.ttf/.otf): register it so Tk can see it
        try:
            self._register_custom_font()
        except Exception:
            pass
        try:
            self.root.attributes("-alpha", float(v.get("transparencia", 1.0)))
            self.root.attributes("-topmost", bool(v.get("siempre_encima", False)))
        except Exception:
            pass
        # Clear image caches so buttons/icons/shapes are regenerated with the
        # NEW theme colors (no leftovers from the previous theme).
        try:
            self._btn_images = {}
        except Exception:
            pass
        try:
            self._shape_cache = {}
        except Exception:
            pass
        try:
            self._icon_cache = {}
        except Exception:
            pass
        # Clear section/panel background caches so the NEW theme colors are used.
        try:
            self._sec_src_cache = {}
        except Exception:
            pass
        try:
            self._sec_avg_cache = {}
        except Exception:
            pass
        try:
            self._panel_avg_cache = {}
        except Exception:
            pass
        try:
            self._btn_face_cache = {}
        except Exception:
            pass
        # 1) Render background and apply to the WHOLE UI (this makes change visible).
        # Synchronous on theme switch: the async thread would repaint rows with
        # the OLD bands/tints mixed with the NEW colors (the "inverted" look).
        try:
            self._bg_gen = int(getattr(self, "_bg_gen", 0) or 0) + 1
        except Exception:
            pass
        try:
            self._bg_gif_token = int(getattr(self, "_bg_gif_token", 0) or 0) + 1
        except Exception:
            pass
        try:
            self.bg_video_running = False
            self._bg_pil = None
            self._bg_photo = None
        except Exception:
            pass
        self._draw_background()
        # 2) Fonts and widgets with background tints
        fam = d["texto"]["fuente_familia"]
        tx, li = d["texto"], d["lista"]
        try:
            self.account_label.configure(bg=self._tint_top, fg=tx["color_titulo"],
                                         font=(fam, tx["fuente_tam_lista"]))
            self.list_title.configure(bg=self._tint_mid, fg=tx["color_titulo"],
                                      font=(fam, tx["fuente_tam_titulo"], "bold"))
            self.song_label.configure(bg=self._tint_bottom, fg=tx["color_titulo"],
                                      font=(fam, tx["fuente_tam_titulo"], "bold"))
            try:
                self.playcount_lbl.configure(bg=self._tint_bottom,
                                             fg=tx["color_subtitulo"],
                                             font=(fam, tx["fuente_tam_pequena"]))
            except Exception:
                pass
            for w in (self.time_a, self.time_b):
                w.configure(bg=self._tint_bottom, fg=tx["color_subtitulo"],
                            font=(fam, tx["fuente_tam_pequena"]))
            self.status.configure(bg=self._tint_bottom, fg=tx["color_subtitulo"],
                                  font=(fam, tx["fuente_tam_pequena"]))
        except Exception:
            pass
        try:
            self.search_entry.configure(font=(fam, tx["fuente_tam_lista"]))
            self.playlist_box.configure(bg=self._tint_mid, fg=tx["color_lista"],
                                        font=(fam, tx["fuente_tam_lista"]),
                                        highlightthickness=0)
        except Exception:
            pass
        # Search bar + every slider follow the theme (they used to keep the
        # plain Windows grey look).
        try:
            self.apply_widgets_theme()
        except Exception:
            pass
        try:
            self.vol_value.configure(fg=tx["color_lista"])
        except Exception:
            pass
        # 3) Buttons with real shapes and icons
        self._paint_all_buttons()
        # 4) List (rows tinted with the background)
        try:
            if (getattr(self, "current_section", "") == "playlists"
                    and getattr(self, "playlist_view_mode", "list") != "list"):
                self._render_playlists_current_view()
            else:
                self.render_list()
        except Exception:
            try:
                self.render_list()
            except Exception:
                pass
        # 5) Video/cover panel
        try:
            self._ensure_video_panel()
        except Exception:
            pass
        try:
            self._paint_video_bar()
        except Exception:
            pass
        try:
            self._paint_playlist_toggle()
        except Exception:
            pass
        try:
            self._paint_section_background()
        except Exception:
            pass
        # 6) Custom panels last: their button/container bg wins
        try:
            self._paint_panels_background()
        except Exception:
            pass
        # 7) Native 1px border in theme color (kills the DWM white line)
        try:
            self._apply_dwm_chrome()
        except Exception:
            pass

    # ----- icons -----
    def _resolve_icon(self, val):
        """Return ('image', path) for an existing image file, else ('text', str)."""
        if isinstance(val, str) and val and os.path.isfile(val):
            return ("image", val)
        return ("text", val or "•")

    def _load_icon_image(self, path: str, box: int):
        """Load a PNG/JPG as a square box-px icon (cached)."""
        key = f"{path}|{box}"
        if key in self._icon_cache:
            return self._icon_cache[key]
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).convert("RGBA")
            img.thumbnail((box, box), Image.LANCZOS)
            base = Image.new("RGBA", (box, box), (0, 0, 0, 0))
            base.alpha_composite(img, ((box - img.width) // 2,
                                       (box - img.height) // 2))
            photo = ImageTk.PhotoImage(base)
            self._icon_cache[key] = photo
            return photo
        except Exception:
            return None

    # ----- button shapes -----
    def _shape_images(self, w: int, h: int):
        """Button background by shape (round/square/custom PNG). Return (normal, hover)."""
        b = self.theme.data["botones"]
        key = (f"{b.get('forma')}|{b.get('forma_custom_path')}|{w}|{h}|"
               f"{b.get('color_fondo')}|{b.get('color_hover')}|"
               f"{b.get('borde_ancho')}|{b.get('borde_color')}")
        if key in self._shape_cache:
            return self._shape_cache[key]
        try:
            from PIL import Image, ImageDraw, ImageTk
            custom = b.get("forma_custom_path", "")
            if b.get("forma") == "custom" and custom and os.path.exists(custom):
                base = Image.open(custom).convert("RGBA").resize((w, h), Image.LANCZOS)
                white = Image.new("RGBA", (w, h), (255, 255, 255, 60))
                hov = Image.alpha_composite(base, white)
                out = (ImageTk.PhotoImage(base), ImageTk.PhotoImage(hov))
                self._shape_cache[key] = out
                return out
            radius = min(w, h) // 2 if b.get("forma", "redondo") == "redondo" else 6
            bw = int(b.get("borde_ancho", 0) or 0)

            def _one(fill):
                img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                dr = ImageDraw.Draw(img)
                dr.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill)
                if bw > 0:
                    dr.rounded_rectangle([bw // 2, bw // 2, w - 1 - bw // 2, h - 1 - bw // 2],
                                         radius=max(0, radius - bw // 2),
                                         outline=b.get("borde_color", "#ffffff"), width=bw)
                return img

            a1 = _hex_to_rgb(b.get("color_fondo", "#2d2d3a")) + (255,)
            a2 = _hex_to_rgb(b.get("color_hover", "#3a3a3a")) + (255,)
            out = (ImageTk.PhotoImage(_one(a1)), ImageTk.PhotoImage(_one(a2)))
            self._shape_cache[key] = out
            return out
        except Exception:
            return (None, None)

    def _style_button(self, btn: tk.Button, icon, behind: str,
                      size: int | None = None, wide: bool = False,
                      fontsize: int | None = None) -> None:
        """Apply icon (text or REAL image) + shape over `behind` color."""
        d = self.theme.data
        b, tx = d["botones"], d["texto"]
        fam = tx["fuente_familia"]
        size = int(size or b.get("tamano", 44))
        fs = int(fontsize or d["iconos"].get("tamano_fuente_icono", 18))
        kind, val = self._resolve_icon(icon)
        try:
            if kind == "image" and not wide:
                photo = self._load_icon_image(val, size)
                if photo is not None:
                    btn.configure(image=photo, text="", compound="none",
                                  bg=behind, activebackground=behind,
                                  relief="flat", bd=0, highlightthickness=0,
                                  cursor="hand2")
                    self._btn_images[id(btn)] = (photo, photo)
                    return
            if b.get("usar_formas", True):
                w = 178 if wide else size + 12
                h = 34 if wide else size + 12
                normal, hover = self._shape_images(w, h)
                if normal is not None:
                    btn.configure(image=normal, text="" if (kind == "image") else str(val),
                                  compound="center", font=(fam, fs),
                                  fg=b.get("color_texto", "#ffffff"),
                                  bg=behind, activebackground=behind,
                                  relief="flat", bd=0, highlightthickness=0,
                                  cursor="hand2")
                    self._btn_images[id(btn)] = (normal, hover or normal)
                    return
            # Classic rectangular
            self._btn_images.pop(id(btn), None)
            btn.configure(image="", text=str(val), bg=b.get("color_fondo"),
                          fg=b.get("color_texto"),
                          activebackground=b.get("color_hover"),
                          font=(fam, fs), relief="raised",
                          bd=b.get("borde_ancho", 0),
                          highlightbackground=b.get("borde_color", "#ffffff"),
                          width=(14 if wide else max(2, size // 16)), height=1,
                          cursor="hand2")
        except Exception:
            pass

    def _btn_hover(self, btn: tk.Button, inside: bool) -> None:
        try:
            pair = self._btn_images.get(id(btn))
            if pair:
                btn.configure(image=pair[1] if inside else pair[0])
        except Exception:
            pass

    def _install_hover(self, btn: tk.Button) -> None:
        try:
            btn.bind("<Enter>", lambda e, bb=btn: self._btn_hover(bb, True))
            btn.bind("<Leave>", lambda e, bb=btn: self._btn_hover(bb, False))
        except Exception:
            pass

    # ----- each SIDEBAR button background -----
    def _side_button_cfg(self, key: str) -> dict:
        try:
            cfg = (self.theme.data.get("fondos_botones", {}) or {}).get(key or "", {}) or {}
        except Exception:
            cfg = {}
        return cfg if isinstance(cfg, dict) else {}

    def _side_button_face(self, key: str, w: int, h: int):
        """Own face (normal, hover) for the sidebar button, or (None, None) if it
        inherits the global shape. Cached by key+size."""
        try:
            cfg = self._side_button_cfg(key)
        except Exception:
            return (None, None)
        try:
            mode = str(cfg.get("modo", "heredar"))
            if mode not in ("color", "imagen"):
                return (None, None)
            color = str(cfg.get("color", "") or "")
            path = str(cfg.get("imagen_path", "") or "")
            if mode == "imagen" and (not path or not os.path.exists(path)):
                return (None, None)
            if mode == "color" and not color:
                return (None, None)
        except Exception:
            return (None, None)
        cache = getattr(self, "_btn_face_cache", None)
        if cache is None:
            cache = {}
            self._btn_face_cache = cache
        ck = f"{key}|{mode}|{color}|{path}|{w}|{h}"
        if ck in cache:
            return cache[ck]
        try:
            from PIL import Image, ImageDraw, ImageTk
            if mode == "imagen":
                base = Image.open(path).convert("RGBA").resize((w, h), Image.LANCZOS)
            else:
                b = self.theme.data.get("botones", {})
                r, g, bl = _hex_to_rgb(color)
                base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                dr = ImageDraw.Draw(base)
                radius = (min(w, h) // 2) if str(b.get("forma", "redondo")) == "redondo" else 6
                dr.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=(r, g, bl, 255))
            white = Image.new("RGBA", (w, h), (255, 255, 255, 60))
            hov = Image.alpha_composite(base, white)
            out = (ImageTk.PhotoImage(base), ImageTk.PhotoImage(hov))
            cache[ck] = out
            return out
        except Exception:
            return (None, None)

    def _style_side_button(self, key: str, btn: tk.Button, behind: str) -> None:
        """Paint a sidebar button with its own background if it has one."""
        try:
            face = self._side_button_face(key, 178, 34)
        except Exception:
            face = (None, None)
        if face and face[0] is not None:
            try:
                d = self.theme.data
                b, tx = d["botones"], d["texto"]
                fam = tx["fuente_familia"]
                fs = 11
                normal, hover = face
                btn.configure(image=normal, text=btn.cget("text"),
                              compound="center", font=(fam, fs),
                              fg=b.get("color_texto", "#ffffff"),
                              bg=behind, activebackground=behind,
                              relief="flat", bd=0, highlightthickness=0,
                              cursor="hand2")
                self._btn_images[id(btn)] = (normal, hover or normal)
                return
            except Exception:
                pass
        self._style_button(btn, btn.cget("text"), behind,
                           size=30, wide=True, fontsize=11)

    def _paint_all_buttons(self) -> None:
        d = self.theme.data
        ic = d["iconos"]
        tx = d["texto"]
        fam = tx["fuente_familia"]
        top, bottom = self._tint_top, self._tint_bottom
        self._style_button(self.btn_search, ic.get("search", "⌕"), top)
        self._style_button(self.btn_openurl, "↗ URL", top, fontsize=10)
        self._style_button(self.btn_customize, "◐ Customize", top, fontsize=10)
        self._style_button(self.btn_settings, ic.get("settings", "⚙︎"), top)
        self._style_button(self.btn_songedit, "✎", top)
        for _key, btn in self.side_buttons.items():
            self._style_side_button(_key, btn, self._tint_mid)
        self._style_button(self.btn_newlist, "+ New YT playlist", self._tint_mid,
                           size=30, wide=True, fontsize=11)
        self._style_button(self.btn_vol_down, "−", bottom, size=22, fontsize=12)
        self._style_button(self.btn_vol_up, "+", bottom, size=22, fontsize=12)
        try:
            self._refresh_vol_icon()
            self._update_vol_label(float(self.vol_var.get()))
        except Exception:
            pass
        # No FAB: the video panel is controlled from Customize > Video.
        try:
            _fab = getattr(self, "_video_fab", None)
            if _fab is not None:
                try:
                    _fab.place_forget()
                    _fab.destroy()
                except Exception:
                    pass
                self._video_fab = None
        except Exception:
            pass
        if getattr(self, "titlebar", None) is not None:
            bar = getattr(self, "_bar_bg", top)
            try:
                self.title_label.configure(bg=bar, fg=tx["color_titulo"],
                                           font=(fam, 10, "bold"),
                                           text=self.theme.data["ventana"]["titulo"])
            except Exception:
                pass
            self._style_button(self.win_min, "─", bar, size=20, fontsize=12)
            self._style_button(self.win_max, "❐" if self._maximized else "▢",
                               bar, size=20, fontsize=12)
            self._style_button(self.win_close, "✕", bar, size=20, fontsize=12)
        self._refresh_control_icons()

    def _refresh_control_icons(self) -> None:
        d = self.theme.data
        ic = d["iconos"]
        behind = getattr(self, "_tint_bottom", d["lista"]["color_fondo"])
        mapping = {
            self.btn_play: ic.get("pause", "▌▌") if self.player.state == "playing" else ic.get("play", "▶"),
            self.btn_prev: ic.get("prev", "◀◀"),
            self.btn_next: ic.get("next", "▶▶"),
            self.btn_shuffle: ic.get("shuffle_on", "⇄●") if self.player.shuffle else ic.get("shuffle", "⇄") + "○",
            self.btn_loop: {"off": ic.get("loop_off", "↻○"), "all": ic.get("loop_all", "↻"),
                            "one": ic.get("loop_one", "↻1")}[self.player.loop_mode],
            self.btn_fav: ic.get("fav_on", "♥") if self._is_fav(self.player.current) else ic.get("fav", "♡"),
        }
        for btn, txt in mapping.items():
            self._style_button(btn, txt, behind)

    # ----- background applied to the UI -----
    def _overlay(self) -> float:
        try:
            return max(0.0, min(0.95, float(self.theme.get("fondo", "overlay_opacidad", default=0.55))))
        except Exception:
            return 0.55

    def _compute_bands(self, img) -> None:
        """32 vertical background averages to tint rows/containers."""
        try:
            w, h = img.size
            bands = []
            for i in range(32):
                y0 = int(h * i / 32)
                bands.append(_avg_color_hex(img, (0, y0, w, min(h, y0 + max(1, h // 32)))))
            self._bg_bands = bands
        except Exception:
            self._bg_bands = ["#1e1e1e"] * 32

    def _band(self, t: float) -> str:
        """Background color at relative height t (0=top,1=bottom) blended with list.

        NOTE: list transparency is NOT applied here: it belongs EXCLUSIVELY to
        song rows (via tiles in _apply_row_tile). These tints go to
        containers/bars and must stay solid.
        """
        try:
            bands = self._bg_bands or ["#1e1e1e"] * 32
            sample = bands[max(0, min(31, int(t * 32)))]
            base = _blend(sample, self.theme.data["lista"]["color_fondo"], self._overlay())
            # Custom section background: color or image/video (cached average).
            # Without this, opaque rows covered the custom image and it looked
            # that "did nothing".
            try:
                sec = self._seccion_efectiva()
                eff = self._effective_section_bg(sec)
                emode = str(eff.get("modo", ""))
                if emode == "color" and eff.get("color"):
                    base = _blend(base, str(eff["color"]), 0.55)
                elif emode in ("imagen", "video"):
                    avg = self._section_avg_color(sec)
                    if avg:
                        base = _blend(base, avg, 0.65)
            except Exception:
                pass
            return base
        except Exception:
            try:
                return self.theme.data["lista"]["color_fondo"]
            except Exception:
                return "#1e1e1e"

    def _apply_background(self, img, repaint_buttons: bool = True) -> None:
        """Put the image on bg_label + canvas and tint the WHOLE UI with it."""
        from PIL import ImageTk
        self._bg_pil = img
        self._compute_bands(img)
        try:
            self._bg_photo = ImageTk.PhotoImage(img)
            self.bg_label.configure(image=self._bg_photo)
        except Exception:
            pass
        self._tint_top = self._band(0.04)
        self._tint_mid = self._band(0.5)
        self._tint_bottom = self._band(0.96)
        self._retint_containers()
        self._refresh_canvas_bg()
        # Animated GIF background: start (or keep) the loop at real size
        try:
            f2 = self.theme.data.get("fondo", {})
            if str(f2.get("modo", "")) == "imagen" and self._is_gif(f2.get("imagen_path", "")):
                _p = str(f2.get("imagen_path"))
                try:
                    _sz = (self._bg_pil.size if getattr(self, "_bg_pil", None) is not None else (0, 0))
                except Exception:
                    _sz = (0, 0)
                if _p != str(getattr(self, "_bg_gif_path", "") or "") or _sz != getattr(self, "_bg_gif_size", None):
                    self._start_bg_gif(_p)
            else:
                self._bg_gif_token = int(getattr(self, "_bg_gif_token", 0) or 0) + 1
                self._bg_gif_path = ""
                self._bg_gif_size = None
        except Exception:
            pass
        if repaint_buttons:
            self._paint_all_buttons()

    def _retint_containers(self) -> None:
        """Recolor containers/labels with the tints (cheap, no images)."""
        top, mid, bottom = self._tint_top, self._tint_mid, self._tint_bottom
        self._bar_bg = _blend(top, "#000000", 0.35)
        try:
            self.main.configure(bg=mid)
            self.topbar.configure(bg=top)
            self.body.configure(bg=mid)
            self.sidebar.configure(bg=top)
            self.listpanel.configure(bg=mid)
            self.playerbar.configure(bg=bottom)
            self.thumb_label.configure(bg=bottom)
            if getattr(self, "titlebar", None) is not None:
                self.titlebar.configure(bg=self._bar_bg)
                self.title_label.configure(bg=self._bar_bg)
            for _w in getattr(self, "_player_mid", []):
                try:
                    _w.configure(bg=bottom)
                except Exception:
                    pass
            self.canvas.configure(bg=mid)
            self.listframe.configure(bg=mid)
        except Exception:
            pass
        # Buttons: only the behind color (they keep their images)
        try:
            for btn, col in ((self.btn_search, top), (self.btn_openurl, top),
                             (self.btn_customize, top), (self.btn_settings, top),
                             (self.btn_songedit, top),
                             (self.btn_newlist, mid)):
                btn.configure(bg=col, activebackground=col)
            for btn in self.side_buttons.values():
                btn.configure(bg=mid, activebackground=mid)
            for btn in (self.btn_prev, self.btn_play, self.btn_next,
                        self.btn_shuffle, self.btn_loop, self.btn_fav,
                        self.btn_vol_down, self.btn_vol_up):
                btn.configure(bg=bottom, activebackground=bottom)
            try:
                self.vol_value.configure(bg=bottom)
                self._refresh_vol_icon()
            except Exception:
                pass
            # Custom panel backgrounds (survive re-tints)
            try:
                self._paint_panels_background()
            except Exception:
                pass
        except Exception:
            pass

    # ---------- background ----------
    def _win_size(self) -> tuple[int, int]:
        try:
            w = self.root.winfo_width() or 0
            h = self.root.winfo_height() or 0
        except Exception:
            w, h = 0, 0
        if w < 200:
            w = self.theme.get("ventana", "ancho", default=1100)
        if h < 200:
            h = self.theme.get("ventana", "alto", default=700)
        return max(200, int(w)), max(200, int(h))

    def _render_bg_pil(self, w: int, h: int):
        from PIL import Image
        f = self.theme.data["fondo"]
        mode = f.get("modo", "degradado")
        if mode == "color":
            return Image.new("RGB", (w, h), f.get("color", "#1a1a1a"))
        if mode == "imagen" and f.get("imagen_path") and os.path.exists(f["imagen_path"]):
            try:
                return Image.open(f["imagen_path"]).convert("RGB").resize((w, h))
            except Exception:
                pass
        if mode == "video" and f.get("video_path") and os.path.exists(f["video_path"]):
            return self._video_first_frame(f["video_path"], w, h)
        return self._gradient_image(w, h, f.get("color", "#1a1a1a"),
                                    f.get("color2", "#232323"),
                                    f.get("degradado_direccion", "vertical"))

    def _draw_background(self) -> None:
        f = self.theme.data["fondo"]
        self.bg_video_running = False
        w, h = self._win_size()
        # First time: sync (tints/bands must exist already).
        # Resize redraws: on a background thread to avoid freezing the UI.
        if self._bg_pil is None:
            try:
                img = self._render_bg_pil(w, h)
                self._apply_background(img, repaint_buttons=False)
            except Exception:
                pass
        else:
            gen = int(getattr(self, "_bg_gen", 0) or 0) + 1
            self._bg_gen = gen
            threading.Thread(target=self._render_bg_thread,
                             args=(gen, w, h), daemon=True).start()
        if (f.get("modo") == "video" and f.get("video_path")
                and os.path.exists(f["video_path"])):
            self._start_bg_video(f["video_path"])
        # SINGLE root bind (with add): _draw_background used to stomp it with bind()
        # without add the sticker binding was lost when moving the window.
        try:
            self._ensure_root_configure_bind()
        except Exception:
            pass

    def _ensure_root_configure_bind(self) -> None:
        """A single root <Configure> serving background + stickers."""
        if getattr(self, "_root_bind_ok", False):
            return
        try:
            self.root.bind("<Configure>", self._on_root_configure, add="+")
            # When clicking / refocusing the main window, overlays
            # (video/stickers outside it) could end up below: reorder.
            self.root.bind("<FocusIn>", self._on_root_focus, add="+")
            self._root_bind_ok = True
        except Exception:
            pass

    def _on_root_focus(self, event=None) -> None:
        try:
            self._stack_overlay_order()
        except Exception:
            pass

    def _on_root_configure(self, event=None) -> None:
        try:
            if event is not None and getattr(event, "widget", None) is not self.root:
                return
        except Exception:
            pass
        # 1) background on resize (with internal debounce)
        try:
            self._on_resize_bg(event)
        except Exception:
            pass
        # 2) stickers follow the window (move + resize)
        try:
            self._reposition_stickers()
        except Exception:
            pass
        # 3) the video panel follows too (relative dx/dy, may be outside)
        try:
            self._reposition_video()
        except Exception:
            pass

    def _render_bg_thread(self, gen: int, w: int, h: int) -> None:
        try:
            img = self._render_bg_pil(w, h)
        except Exception:
            return
        self._call_ui(self._finish_bg_render, gen, img)

    def _finish_bg_render(self, gen: int, img) -> None:
        if gen != getattr(self, "_bg_gen", 0):
            return  # stale: another resize arrived later
        try:
            self._apply_background(img, repaint_buttons=False)
            self._retint_rows()
            # The global background just covered the section custom background:
            # always repaint it afterwards.
            try:
                self._paint_section_background()
            except Exception:
                pass
            # Full repaint so no widget keeps the previous theme's colors.
            try:
                self._paint_panels_background()
            except Exception:
                pass
            try:
                self._paint_video_bar()
            except Exception:
                pass
            try:
                self._paint_playlist_toggle()
            except Exception:
                pass
            try:
                self._update_vol_label(float(self.vol_var.get()))
            except Exception:
                pass
        except Exception:
            pass

    def _on_resize_bg(self, event=None) -> None:
        # Only redraw when the WINDOW size changed (child Configure
        # children bubble up to root: ignore them to avoid freezing the UI).
        try:
            if event is not None and getattr(event, "widget", None) is not self.root:
                return
            size = self._win_size()
            if size == getattr(self, "_last_bg_size", None):
                return
            self._last_bg_size = size
        except Exception:
            pass
        if getattr(self, "_bg_timer", None):
            try:
                self.root.after_cancel(self._bg_timer)
            except Exception:
                pass
        try:
            self._bg_timer = self.root.after(600, self._draw_background)
        except Exception:
            pass

    @staticmethod
    def _gradient_image(w, h, c1, c2, direction="vertical"):
        from PIL import Image
        def hx(c):
            c = c.lstrip("#")
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        a, b = hx(c1), hx(c2)
        img = Image.new("RGB", (w, h))
        px = img.load()
        if direction == "horizontal":
            for x in range(w):
                t = x / max(1, w - 1)
                col = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
                for y in range(h):
                    px[x, y] = col
        else:
            for y in range(h):
                t = y / max(1, h - 1)
                col = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
                for x in range(w):
                    px[x, y] = col
        return img

    @staticmethod
    def _video_first_frame(path, w, h):
        from PIL import Image
        try:
            import imageio.v2 as imageio
            reader = imageio.get_reader(path)
            frame = reader.get_data(0)
            reader.close()
            img = Image.fromarray(frame).convert("RGB").resize((w, h))
            return img
        except Exception:
            return Image.new("RGB", (w, h), "#1a1a1a")

    @staticmethod
    def _is_gif(path) -> bool:
        try:
            return str(path or "").lower().endswith(".gif") and os.path.exists(str(path))
        except Exception:
            return False

    @staticmethod
    def _load_gif_frames(path, w, h, max_frames: int = 40):
        """Frames of a GIF as [(resized PIL RGBA, delay_ms)].

        If not a GIF or on failure, []. Max 40 frames, minimum 80 ms per frame
        to spare the CPU."""
        out = []
        try:
            from PIL import Image
            w, h = max(16, int(w)), max(16, int(h))
            im = Image.open(path)
            try:
                if (str(getattr(im, "format", "") or "").upper() != "GIF"
                        and not str(path).lower().endswith(".gif")):
                    try:
                        im.close()
                    except Exception:
                        pass
                    return []
            except Exception:
                pass
            n = int(getattr(im, "n_frames", 1) or 1)
            for i in range(min(n, max(8, int(max_frames)))):
                try:
                    im.seek(i)
                except Exception:
                    break
                try:
                    dur = int(im.info.get("duration", 100) or 100)
                except Exception:
                    dur = 100
                try:
                    fr = im.convert("RGBA").resize((w, h))
                except Exception:
                    continue
                out.append((fr, max(80, min(2000, dur))))
            try:
                im.close()
            except Exception:
                pass
        except Exception:
            pass
        return out

    def _start_bg_gif(self, path: str) -> None:
        """Global background GIF loop. Loads frames on thread, paints on UI."""
        try:
            self._bg_gif_token = int(getattr(self, "_bg_gif_token", 0) or 0) + 1
            tok = self._bg_gif_token
            self._bg_gif_path = str(path)
        except Exception:
            return

        def _load():
            try:
                w, h = self._win_size()
                frames = self._load_gif_frames(path, w, h)
                self._call_ui(self._begin_bg_gif, tok, str(path), frames, (int(w), int(h)))
            except Exception:
                pass
        try:
            threading.Thread(target=_load, daemon=True).start()
        except Exception:
            pass

    def _begin_bg_gif(self, tok: int, path: str, frames, size) -> None:
        try:
            if tok != getattr(self, "_bg_gif_token", 0):
                return
            if str(path) != str(getattr(self, "_bg_gif_path", "")):
                return
            if not frames or len(frames) < 2:
                return
            from PIL import ImageTk
            photos = []
            for fr, dur in frames:
                try:
                    photos.append((ImageTk.PhotoImage(fr.convert("RGB")), int(dur)))
                except Exception:
                    continue
            if len(photos) < 2:
                return
            self._bg_gif_photos = photos
            self._bg_gif_i = 0
            self._bg_gif_size = size
            self._bg_gif_tick(tok)
        except Exception:
            pass

    def _bg_gif_tick(self, tok: int) -> None:
        try:
            if tok != getattr(self, "_bg_gif_token", 0):
                return
            if getattr(self, "_closed", False):
                return
            try:
                f = self.theme.data.get("fondo", {})
                if not (str(f.get("modo", "")) == "imagen"
                        and str(f.get("imagen_path", "")) == str(getattr(self, "_bg_gif_path", ""))):
                    return
            except Exception:
                return
            phs = getattr(self, "_bg_gif_photos", None) or []
            if not phs:
                return
            i = int(getattr(self, "_bg_gif_i", 0) or 0) % len(phs)
            ph, dur = phs[i]
            try:
                self._bg_photo = ph
                self.bg_label.configure(image=ph)
            except Exception:
                return
            self._bg_gif_i = i + 1
            try:
                self.root.after(max(60, int(dur)), lambda: self._bg_gif_tick(tok))
            except Exception:
                pass
        except Exception:
            pass

    def _start_bg_video(self, path) -> None:
        if self.bg_video_running:
            return
        self.bg_video_running = True
        threading.Thread(target=self._bg_video_loop, args=(path,), daemon=True).start()

    def _bg_video_loop(self, path) -> None:
        try:
            import imageio.v2 as imageio
            from PIL import Image
            reader = imageio.get_reader(path)
            try:
                fps = float(reader.get_meta_data().get("fps", 24) or 24)
            except Exception:
                fps = 24
            delay = max(0.08, min(0.15, 1.0 / max(1, fps)))
            n = 0
            while self.bg_video_running:
                try:
                    for frame in reader:
                        if not self.bg_video_running:
                            break
                        try:
                            w, h = self._win_size()
                            img = Image.fromarray(frame).convert("RGB").resize((w, h))
                            n += 1
                            # Roughly every 2 s re-tint the UI with the current frame
                            self._call_ui(self._set_bg_frame, img, n % 16 == 0)
                        except Exception:
                            pass
                        time.sleep(delay)
                except Exception:
                    time.sleep(0.5)
            try:
                reader.close()
            except Exception:
                pass
        except Exception:
            pass

    def _set_bg_frame(self, img, retint: bool = False) -> None:
        """Update label + canvas with a video frame (main thread)."""
        try:
            from PIL import ImageTk
            self._bg_pil = img
            self._bg_photo = ImageTk.PhotoImage(img)
            self.bg_label.configure(image=self._bg_photo)
            self._refresh_canvas_bg(img)
            if retint:
                self._compute_bands(img)
                self._tint_top = self._band(0.04)
                self._tint_mid = self._band(0.5)
                self._tint_bottom = self._band(0.96)
                self._retint_containers()
                self._retint_rows()
            # Do not cover the section custom background with the global video.
            try:
                eff = self._effective_section_bg(getattr(self, "current_section", "buscar"))
                if str(eff.get("modo", "heredar")) != "heredar":
                    self._paint_section_background()
            except Exception:
                pass
        except Exception:
            pass

    def _set_bg_photo(self, photo) -> None:
        try:
            self._bg_photo = photo
            self.bg_label.configure(image=photo)
        except Exception:
            pass

    # ----- list background (canvas, does not scroll) -----
    def _refresh_canvas_bg(self, img=None) -> None:
        try:
            from PIL import ImageTk
            img = img or self._bg_pil
            if img is None:
                return
            cw = max(200, self.canvas.winfo_width() or 0)
            ch = max(200, self.canvas.winfo_height() or 0)
            if cw < 200 or ch < 200:
                return
            crop = img.resize((cw, ch))
            self._canvas_bg_pil = crop
            self._canvas_bg_photo = ImageTk.PhotoImage(crop)
            if self._canvas_bg_id is None:
                self._canvas_bg_id = self.canvas.create_image(
                    0, 0, anchor="nw", image=self._canvas_bg_photo, tags=("bg",))
                try:
                    self.canvas.tag_lower(self._canvas_bg_id)
                except Exception:
                    pass
            else:
                self.canvas.itemconfigure(self._canvas_bg_id,
                                          image=self._canvas_bg_photo)
            self._pin_canvas_bg()
        except Exception:
            pass

    def _pin_canvas_bg(self) -> None:
        """Keep the background image pinned on top while the list scrolls."""
        try:
            if self._canvas_bg_id is not None:
                self.canvas.coords(self._canvas_bg_id, 0, self.canvas.canvasy(0))
        except Exception:
            pass

    def _canvas_yview(self, *args) -> None:
        try:
            self.canvas.yview(*args)
        except Exception:
            pass
        self._pin_canvas_bg()
        self._schedule_retile()

    def _find_canvas_for_widget(self, widget) -> object:
        """Walk up from widget to find a tk.Canvas to scroll."""
        try:
            w = widget
            while w is not None:
                if w.winfo_class() == "Canvas":
                    return w
                w = w.master
        except Exception:
            pass
        return None

    def _on_mousewheel(self, event=None) -> None:
        try:
            delta = 0
            if event is not None:
                delta = int(getattr(event, "delta", 0) / 120) or (-1 if getattr(event, "num", 0) == 5 else 1)
            # Scroll the canvas under the cursor (channel tabs, playlists,
            # main list), not always the main list canvas.
            target = event.widget if event else None
            canvas = self._find_canvas_for_widget(target) if target else None
            if canvas is None:
                canvas = self.canvas
            canvas.yview_scroll(-delta or -1, "units")
        except Exception:
            pass
        self._pin_canvas_bg()
        self._schedule_retile()

    def _wheel_scroll(self, d: int) -> None:
        try:
            self.canvas.yview_scroll(d, "units")
        except Exception:
            pass
        try:
            self._pin_canvas_bg()
        except Exception:
            pass
        self._schedule_retile()

    def _wheel_scroll_canvas(self, canvas, event_or_delta) -> None:
        """Wheel scroll for a specific canvas (channel tabs, not the main list)."""
        try:
            delta = 0
            if hasattr(event_or_delta, "delta"):
                delta = int(getattr(event_or_delta, "delta", 0) / 120)
            elif isinstance(event_or_delta, int):
                delta = event_or_delta
            else:
                delta = -1 if getattr(event_or_delta, "num", 0) == 5 else 1
            canvas.yview_scroll(-delta or -1, "units")
        except Exception:
            pass

    def _bind_wheel(self, widget) -> None:
        try:
            widget.bind("<MouseWheel>", self._on_mousewheel)
            widget.bind("<Button-4>", lambda e: self._wheel_scroll(-1))
            widget.bind("<Button-5>", lambda e: self._wheel_scroll(1))
        except Exception:
            pass

    def _retint_rows(self) -> None:
        """Recolor existing rows with the current bands (live video).

        Rows with an image tile (transparency>0) are skipped: their tone
        already matches their crop and solid repaint would cover them."""
        try:
            n = max(1, len(self.row_widgets))
            for i, row in enumerate(self.row_widgets):
                try:
                    if getattr(row, "_bg_label", None) is not None:
                        continue
                except Exception:
                    pass
                base = self._band(0.15 + 0.7 * (i / n))
                active = getattr(row, "_active_bg", None)
                if active:
                    base = _blend(base, self.theme.data["lista"]["color_item_activo"], 0.65)
                row.configure(bg=base)
                for child in row.winfo_children():
                    try:
                        cls = child.winfo_class()
                        if cls in ("Label",):
                            child.configure(bg=base)
                        elif cls in ("Button",):
                            child.configure(bg=base, activebackground=base)
                    except Exception:
                        pass
        except Exception:
            pass

    def _call_ui(self, fn, *args, **kwargs) -> None:
        """Queue fn for the UI thread. NEVER touch Tk from threads
        (cross-thread root.after loses callbacks / recurses)."""
        try:
            self._ui_queue.put((fn, args, kwargs))
        except Exception:
            pass

    def _pump_ui(self) -> None:
        """Run on the main thread what background threads queued."""
        try:
            for _ in range(60):
                try:
                    fn, args, kwargs = self._ui_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass
        except Exception:
            pass
        if getattr(self, '_closed', False):
            return
        try:
            self.root.after(120, self._pump_ui)
        except Exception:
            pass

    # ---------- precise volume (0.2 steps) ----------
    @staticmethod
    def _snap_vol(v: float) -> float:
        try:
            return round(max(0.0, min(100.0, float(v))) * 5.0) / 5.0
        except Exception:
            return 0.0

    def _update_vol_label(self, v: float) -> None:
        try:
            self.vol_value.configure(text=f"{float(v):.1f}", fg=self.theme.data["texto"]["color_lista"])
        except Exception:
            pass

    def _vol_step(self, delta: float) -> None:
        try:
            self._on_volume_change(self._snap_vol(float(self.vol_var.get()) + float(delta)))
        except Exception:
            pass

    def _on_volume_change(self, v: float) -> None:
        try:
            v = self._snap_vol(v)
            self.player.set_volume(v)
            try:
                self.vol_var.set(v)
            except Exception:
                pass
            self._update_vol_label(v)
        except Exception:
            pass
        if not bool(self.theme.get("reproductor", "guardar_volumen", default=True)):
            return
        # Debounced save (do not write on every slider pixel)
        try:
            if self._vol_save_timer is not None:
                try:
                    self.root.after_cancel(self._vol_save_timer)
                except Exception:
                    pass
            self._vol_save_timer = self.root.after(600, lambda vv=float(v): self.theme.set(vv, "reproductor", "volumen_defecto"))
        except Exception:
            try:
                self.theme.set(float(v), "reproductor", "volumen_defecto")
            except Exception:
                pass

    # ---------- responsive player bar ----------
    def _apply_playerbar_responsive(self) -> None:
        """Size the progress bar so all controls always fit.

        If the window is too narrow, the progress bar length is reduced
        instead of hiding the volume / skip / pause buttons. Called on
        startup and on every playerbar resize (debounced).
        """
        try:
            if not bool(self.theme.get("reproductor", "barra_responsive",
                                       default=True)):
                return
            pb = getattr(self, "_player_prog_frame", None)
            if pb is None:
                return
            # Available width = playerbar width minus fixed parts.
            try:
                bar_w = max(100, int(self.playerbar.winfo_width() or 0))
            except Exception:
                return
            # Thumbnail (~52px + padding), controls (~200px), volume (~150px),
            # time labels (2×7 chars ≈ 60px), paddings.
            fixed = 52 + 200 + 150 + 60 + 120
            prog_w = bar_w - fixed
            min_w = int(self.theme.get("reproductor", "barra_altura_minima",
                                       default=60))  # px hint, used as min bar width
            prog_w = max(min_w, prog_w)
            # tk.Scale length is in pixels (approximate; the actual drawn
            # trough may differ slightly, so we stay conservative).
            try:
                cur = int(self.progress.cget("length"))
            except Exception:
                cur = -1
            if abs(cur - prog_w) > 8:
                self.progress.configure(length=prog_w)
        except Exception:
            pass

    def _on_playerbar_resize(self, event=None) -> None:
        """Debounced handler for playerbar resize."""
        try:
            if self._playerbar_resize_job is not None:
                try:
                    self.root.after_cancel(self._playerbar_resize_job)
                except Exception:
                    pass
            self._playerbar_resize_job = self.root.after(
                60, self._apply_playerbar_responsive)
        except Exception:
            pass

    def _refresh_vol_icon(self) -> None:
        """Volume bar icon: follows theme iconos.volume
        (emoji/letter or OWN image)."""
        try:
            d = self.theme.data
            ic = d.get("iconos", {})
            val = ic.get("volume", "♪")
            kind, p = self._resolve_icon(val)
            behind = getattr(self, "_tint_bottom", "#222222")
            try:
                behind = self.volf.cget("bg")
            except Exception:
                pass
            if kind == "image":
                photo = self._load_icon_image(p, 22)
                if photo is not None:
                    self.vol_icon.configure(image=photo, text="", bg=behind)
                    self._vol_icon_photo = photo
                    return
            self._vol_icon_photo = None
            self.vol_icon.configure(image="", text=str(val),
                                    font=(d["texto"]["fuente_familia"], 13), bg=behind,
                                    fg=d["texto"].get("color_subtitulo", "#9d9d9d"))
        except Exception:
            pass

    # ---------- draggable sidebar order ----------
    def _make_sidebar_draggable(self, btn: tk.Button, key: str) -> None:
        state = {"y0": 0, "dragging": False}
        def _press(e):
            state["y0"] = e.y_root
            state["dragging"] = True
            try:
                btn.configure(relief="sunken")
            except Exception:
                pass
        def _motion(e):
            if not state["dragging"]:
                return
            dy = e.y_root - state["y0"]
            if abs(dy) < 18:
                return
            # Find the neighbor to swap along the direction
            try:
                keys = [k for k in self._side_labels.keys() if k in self.side_buttons]
                # Current visual pack order: use winfo_y
                ordered = sorted(keys, key=lambda k: self.side_buttons[k].winfo_y())
                idx = ordered.index(key)
                other = ordered[idx + 1] if dy > 0 else ordered[idx - 1] if idx > 0 else None
                if other is None:
                    state["y0"] = e.y_root
                    return
                # Swap visual positions by re-packing in the new order
                ordered[idx], ordered[ordered.index(other)] = ordered[ordered.index(other)], ordered[idx]
                for k in ordered:
                    try:
                        self.side_buttons[k].pack_forget()
                    except Exception:
                        pass
                for k in ordered:
                    try:
                        self.side_buttons[k].pack(fill="x", pady=2, ipady=6)
                    except Exception:
                        pass
                # Re-add separator and rest? (btn_newlist and playlist_box are already below;
                # pack_forget+pack of sidebar buttons leaves them on top anyway)
                try:
                    self.btn_newlist.pack_forget()
                    self.btn_newlist.pack(fill="x", pady=2)
                    self.playlist_box.pack_forget()
                    self.playlist_box.pack(fill="both", expand=True, pady=4)
                except Exception:
                    pass
                self.theme.set(list(ordered), "sidebar_orden")
                try:
                    self.status.configure(text=f"Sidebar order: {' → '.join(ordered)}")
                except Exception:
                    pass
                state["y0"] = e.y_root
            except Exception:
                pass
        def _release(e):
            state["dragging"] = False
            try:
                btn.configure(relief="flat")
            except Exception:
                pass
            try:
                self._paint_all_buttons()
            except Exception:
                pass
        try:
            btn.bind("<ButtonPress-1>", _press, add="+")
            btn.bind("<B1-Motion>", _motion, add="+")
            btn.bind("<ButtonRelease-1>", _release, add="+")
        except Exception:
            pass

    # ---------- list transparency ----------
    def _lista_transparencia(self) -> float:
        try:
            return max(0.0, min(0.9, float(self.theme.get("lista", "transparencia", default=0.0) or 0.0)))
        except Exception:
            return 0.0

    def _on_lista_transparencia_change(self, v) -> None:
        """Transparency slider: saves instantly and re-renders with
        debounce (else 80 tiles per slider tick would freeze dragging)."""
        try:
            self.theme.set(float(v), "lista", "transparencia")
        except Exception:
            pass
        try:
            if getattr(self, "_trans_timer", None) is not None:
                try:
                    self.root.after_cancel(self._trans_timer)
                except Exception:
                    pass
            self._trans_timer = self.root.after(200, self._apply_transparency_preview)
        except Exception:
            pass

    def _apply_transparency_preview(self) -> None:
        try:
            self._trans_timer = None
        except Exception:
            pass
        try:
            self._tint_top = self._band(0.04)
            self._tint_mid = self._band(0.5)
            self._tint_bottom = self._band(0.96)
        except Exception:
            pass
        try:
            self._retint_containers()
        except Exception:
            pass
        try:
            self.render_list(keep_scroll=True)
        except Exception:
            pass

    def _get_list_bg_source(self):
        """Background PIL image for ROWS: the section image if any,
        else the current global background. None if no image."""
        try:
            sec = self._seccion_efectiva()
            cfg = self._section_cfg(sec)
            mode = str(cfg.get("modo", "heredar"))
            path = str(cfg.get("imagen_path", "") or cfg.get("video_path", "") or "")
            if mode in ("imagen", "video") and path and os.path.exists(path):
                cache = getattr(self, "_sec_src_cache", None)
                if cache is None:
                    cache = {}
                    self._sec_src_cache = cache
                hit = cache.get(sec)
                if isinstance(hit, dict) and hit.get("path") == path and hit.get("img") is not None:
                    return hit["img"]
                try:
                    from PIL import Image as _I
                    if mode == "video":
                        img = self._video_first_frame(path, 480, 480).copy()
                    else:
                        img = _I.open(path).convert("RGB")
                    cache[sec] = {"path": path, "img": img}
                    return img
                except Exception:
                    pass
            bgp = getattr(self, "_bg_pil", None)
            return bgp
        except Exception:
            return None

    def _row_is_visible(self, row) -> bool:
        """True when the row is inside the visible area of the list.

        Only the rows on screen may keep a background image: a long list
        with one picture per row used to eat hundreds of megabytes."""
        try:
            top, bottom = self.canvas.yview()
            sr = self.canvas.bbox("all") or (0, 0, 0, 0)
            H = max(1, int(sr[3]) - int(sr[1]))
            y0v, y1v = float(top) * H, float(bottom) * H
            win_id = getattr(self, "_listframe_win", None)
            bbox = self.canvas.bbox(win_id) if win_id is not None else None
            if not bbox:
                return False
            ry = float(bbox[1]) + float(row.winfo_y())
            rh = float(row.winfo_height() or 0)
            return not (ry + rh < y0v - rh or ry > y1v + rh)
        except Exception:
            return False

    def _apply_row_tile(self, row, i: int, n: int, solid_bg: str) -> str:
        """REAL row background: the SAME background seen behind (exact
        1:1 sampling of the image the canvas paints), blended with the
        list color per transparency (0=solid, 1=background as-is).

        Return the resulting average color to paint text/buttons over it
        (readable and matching). With no transparency it creates nothing
        (fast). Rows that are NOT on screen get no picture at all (the
        retile paints them when they scroll in): one image per row was
        what made long lists eat the memory and crash the app.
        If geometry does not exist yet, paint an approximate crop and
        leave the row flagged for re-sampling on layout/scroll
        (_retile_visible_rows)."""
        try:
            tr = self._lista_transparencia()
        except Exception:
            tr = 0.0
        if tr <= 0.01:
            return solid_bg
        try:
            row._tile_solid = solid_bg
            row._tile_exact = False
        except Exception:
            pass
        if not self._row_is_visible(row):
            return solid_bg  # out of view: no image (the retile will do it)
        avg = self._paint_row_tile(row, solid_bg, tr)
        return avg or solid_bg

    def _paint_row_tile(self, row, solid_bg: str, tr: float):
        """Re(paint) a row tile with exact sampling of the canvas
        background. Return the average tone or None on failure."""
        try:
            from PIL import Image, ImageTk
            try:
                rw = int(row.winfo_width() or 0)
                rh = int(row.winfo_height() or 0)
            except Exception:
                rw, rh = 0, 0
            disp = getattr(self, "_canvas_bg_pil", None)
            if disp is None or rw < 20 or rh < 10:
                return None
            try:
                win_id = getattr(self, "_listframe_win", None)
                bbox = self.canvas.bbox(win_id) if win_id is not None else None
                top = float(self.canvas.canvasy(0))
            except Exception:
                return None
            if not bbox:
                return None
            try:
                ry = float(bbox[1]) + float(row.winfo_y())
            except Exception:
                return None
            y0 = int(round(ry - top))
            dw, dh = disp.size
            if y0 + rh <= 0 or y0 >= dh:
                return None  # out of view: nothing to show
            w = max(2, min(rw, dw))
            y1, y2 = max(0, y0), min(dh, y0 + rh)
            if y2 - y1 < 2:
                return None
            try:
                tile = disp.crop((0, y1, w, y2))
            except Exception:
                return None
            if tile.size != (rw, rh):
                try:
                    tile = tile.resize((rw, rh))
                except Exception:
                    return solid_bg
            try:
                r, g, b = _hex_to_rgb(solid_bg)
                solid = Image.new("RGB", (rw, rh), (r, g, b))
                tile = Image.blend(solid, tile.convert("RGB"), max(0.0, min(1.0, float(tr))))
            except Exception:
                pass
            avg = _avg_color_hex(tile)
            try:
                old = getattr(row, "_bg_label", None)
                if old is not None:
                    try:
                        old.destroy()
                    except Exception:
                        pass
                    row._bg_label = None
                    row._bg_photo = None
                photo = ImageTk.PhotoImage(tile)
                # tile-tone bg: where the photo does not cover (the row grows
                # when thumbnails arrive) this matching color shows instead of
                # system gray-white (the rows "white frame").
                bg_lbl = tk.Label(row, image=photo, bd=0, highlightthickness=0,
                                  bg=(avg or solid_bg))
                bg_lbl.place(x=0, y=0, relwidth=1, relheight=1)
                try:
                    bg_lbl.lower()
                except Exception:
                    pass
                row._bg_photo = photo
                row._bg_pil = tile
                row._bg_label = bg_lbl
                row._tile_exact = True
                self._bind_wheel(bg_lbl)
            except Exception:
                return None
            return avg or solid_bg
        except Exception:
            return None

    def _schedule_retile(self) -> None:
        """Re-sample visible rows with debounce (scroll/resize)."""
        try:
            if float(self._lista_transparencia() or 0.0) <= 0.01:
                return
        except Exception:
            return
        try:
            t = getattr(self, "_retile_timer", None)
            if t is not None:
                try:
                    self.root.after_cancel(t)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._retile_timer = self.root.after(150, self._retile_visible_rows)
        except Exception:
            pass

    def _retile_visible_rows(self) -> None:
        """Re-sample with the exact region the rows in view."""
        try:
            self._retile_timer = None
        except Exception:
            pass
        try:
            tr = float(self._lista_transparencia() or 0.0)
            if tr <= 0.01:
                return
            top, bottom = self.canvas.yview()
            sr = self.canvas.bbox("all") or (0, 0, 0, 0)
            H = max(1, int(sr[3]) - int(sr[1]))
            y0v, y1v = float(top) * H, float(bottom) * H
            win_id = getattr(self, "_listframe_win", None)
            bbox = self.canvas.bbox(win_id) if win_id is not None else None
            if not bbox:
                return
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            for row in list(getattr(self, "row_widgets", []) or []):
                try:
                    if getattr(row, "_bg_label", None) is None and not getattr(row, "_tile_solid", None):
                        continue
                    ry = float(bbox[1]) + float(row.winfo_y())
                    try:
                        rh = float(row.winfo_height() or 0)
                    except Exception:
                        rh = 0.0
                    if ry + rh < y0v - rh or ry > y1v + rh:
                        # Out of view: FREE its background picture. Keeping
                        # one image per row was what killed the app with a
                        # long list (hundreds of MB of pictures).
                        try:
                            lbl = getattr(row, "_bg_label", None)
                            if lbl is not None:
                                try:
                                    lbl.destroy()
                                except Exception:
                                    pass
                                row._bg_label = None
                                row._bg_photo = None
                                row._bg_pil = None
                                row._tile_exact = False
                        except Exception:
                            pass
                        continue  # out of view: do not spend
                    solid = getattr(row, "_tile_solid", None) or getattr(row, "_base_bg", None) or "#1e1e1e"
                    avg = self._paint_row_tile(row, solid, tr)
                    if avg:
                        try:
                            row._base_bg = avg
                            row._full_bg = avg
                            row.configure(bg=avg)
                            for child in row.winfo_children():
                                try:
                                    if child is getattr(row, "_bg_label", None):
                                        continue
                                    cls = child.winfo_class()
                                    if cls in ("Label",):
                                        child.configure(bg=avg)
                                    elif cls in ("Button",):
                                        child.configure(bg=avg, activebackground=avg)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    # ---------- PANEL backgrounds (all custom like the menu) ----------
    def _panel_cfg(self, key: str) -> dict:
        try:
            cfg = (self.theme.data.get("fondos_paneles", {}) or {}).get(key or "", {}) or {}
        except Exception:
            cfg = {}
        return cfg if isinstance(cfg, dict) else {}

    def _panel_avg(self, key: str) -> str:
        """Average color of the panel image (cached). "" if none."""
        try:
            cfg = self._panel_cfg(key)
            if str(cfg.get("modo", "heredar")) != "imagen":
                return ""
            p = str(cfg.get("imagen_path", "") or "")
            if not p or not os.path.exists(p):
                return ""
            cache = getattr(self, "_panel_avg_cache", None)
            if cache is None:
                cache = {}
                self._panel_avg_cache = cache
            hit = cache.get(key)
            if isinstance(hit, dict) and hit.get("path") == p and hit.get("avg"):
                return str(hit["avg"])
            from PIL import Image as _I
            avg = _avg_color_hex(_I.open(p).convert("RGB").resize((64, 64)))
            cache[key] = {"path": p, "avg": avg}
            return avg or ""
        except Exception:
            return ""

    def _panel_bg_label(self, key: str, frame) -> None:
        """Put the IMAGE as panel background (Label placed behind)."""
        try:
            old = (getattr(self, "_panel_bg_labels", {}) or {}).get(key)
            if old is not None:
                try:
                    old.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            cfg = self._panel_cfg(key)
            p = str(cfg.get("imagen_path", "") or "")
            if not p or not os.path.exists(p):
                return
            from PIL import Image, ImageTk
            try:
                w = max(120, int(frame.winfo_width() or 0))
                h = max(40, int(frame.winfo_height() or 0))
            except Exception:
                w, h = 400, 100
            img = Image.open(p).convert("RGB").resize((w, h))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(frame, image=photo, bd=0, highlightthickness=0)
            lbl.place(x=0, y=0, relwidth=1, relheight=1)
            try:
                lbl.lower()
            except Exception:
                pass
            if getattr(self, "_panel_photos", None) is None:
                self._panel_photos = {}
            if getattr(self, "_panel_bg_labels", None) is None:
                self._panel_bg_labels = {}
            self._panel_photos[key] = photo
            self._panel_bg_labels[key] = lbl
            try:
                self._bind_wheel(lbl)
            except Exception:
                pass
        except Exception:
            pass

    def _maybe_panel_gif(self, key: str, frame) -> None:
        """If the panel has a GIF, animate it; else stop old loops."""
        try:
            toks = getattr(self, "_panel_gif_toks", None)
            if toks is None:
                toks = {}
                self._panel_gif_toks = toks
            try:
                cfg = self._panel_cfg(key)
                p = str(cfg.get("imagen_path", "") or "")
                is_gif = (str(cfg.get("modo", "")) == "imagen" and self._is_gif(p))
            except Exception:
                is_gif, p = False, ""
            try:
                state = getattr(self, "_panel_gif_state", None) or {}
            except Exception:
                state = {}
            try:
                w = max(120, int(frame.winfo_width() or 0))
                h = max(40, int(frame.winfo_height() or 0))
            except Exception:
                w, h = 400, 100
            if not is_gif:
                toks[key] = int(toks.get(key, 0) or 0) + 1
                try:
                    state.pop(key, None)
                    self._panel_gif_state = state
                except Exception:
                    pass
                return
            cur = state.get(key)
            if isinstance(cur, dict) and cur.get("path") == p and cur.get("size") == (w, h):
                return  # already animating this one
            state[key] = {"path": p, "size": (w, h)}
            try:
                self._panel_gif_state = state
            except Exception:
                pass
            self._start_panel_gif(key, frame, p, w, h)
        except Exception:
            pass

    def _start_panel_gif(self, key: str, frame, path: str, w: int, h: int) -> None:
        try:
            toks = getattr(self, "_panel_gif_toks", None)
            if toks is None:
                toks = {}
                self._panel_gif_toks = toks
            toks[key] = int(toks.get(key, 0) or 0) + 1
            tok = toks[key]
        except Exception:
            return

        def _load():
            try:
                frames = self._load_gif_frames(path, w, h, max_frames=30)
                self._call_ui(self._begin_panel_gif, key, tok, str(path), frame, frames)
            except Exception:
                pass
        try:
            threading.Thread(target=_load, daemon=True).start()
        except Exception:
            pass

    def _begin_panel_gif(self, key: str, tok: int, path: str, frame, frames) -> None:
        try:
            toks = getattr(self, "_panel_gif_toks", None) or {}
            if tok != toks.get(key, 0):
                return
            try:
                cfg = self._panel_cfg(key)
                if not (str(cfg.get("modo", "")) == "imagen"
                        and str(cfg.get("imagen_path", "")) == str(path)):
                    return
            except Exception:
                return
            if not frames or len(frames) < 2:
                return
            from PIL import ImageTk
            photos = []
            for fr, dur in frames:
                try:
                    photos.append((ImageTk.PhotoImage(fr.convert("RGB")), int(dur)))
                except Exception:
                    continue
            if len(photos) < 2:
                return
            try:
                d = getattr(self, "_panel_gif_photos", None)
                if d is None:
                    d = {}
                    self._panel_gif_photos = d
                d[key] = {"photos": photos, "i": 0}
            except Exception:
                pass
            self._panel_gif_tick(key, tok)
        except Exception:
            pass

    def _panel_gif_tick(self, key: str, tok: int) -> None:
        try:
            toks = getattr(self, "_panel_gif_toks", None) or {}
            if tok != toks.get(key, 0):
                return
            if getattr(self, "_closed", False):
                return
            try:
                cfg = self._panel_cfg(key)
                if not (str(cfg.get("modo", "")) == "imagen" and self._is_gif(cfg.get("imagen_path", ""))):
                    return
            except Exception:
                return
            try:
                info = (getattr(self, "_panel_gif_photos", None) or {}).get(key) or {}
                phs = info.get("photos") or []
                lbl = (getattr(self, "_panel_bg_labels", None) or {}).get(key)
                if not phs or lbl is None:
                    return
                try:
                    lbl.winfo_exists()
                except Exception:
                    return
            except Exception:
                return
            i = int(info.get("i", 0) or 0) % len(phs)
            ph, dur = phs[i]
            try:
                lbl.configure(image=ph)
                try:
                    self._panel_photos[key] = ph
                except Exception:
                    pass
            except Exception:
                return
            info["i"] = i + 1
            try:
                self.root.after(max(60, int(dur)), lambda: self._panel_gif_tick(key, tok))
            except Exception:
                pass
        except Exception:
            pass

    def _paint_panels_background(self) -> None:
        """Apply each panel custom background (color or image). Called at
        the end of _retint_containers to survive re-tints."""
        try:
            _t = getattr(self, "_tint_top", "#222222")
            _m = getattr(self, "_tint_mid", "#222222")
            _b = getattr(self, "_tint_bottom", "#222222")
            # --- top bar ---
            cfg = self._panel_cfg("barra_superior")
            if str(cfg.get("modo", "heredar")) == "color" and cfg.get("color"):
                c = str(cfg["color"])
                try:
                    self.topbar.configure(bg=c)
                    for _bb in (self.btn_search, self.btn_openurl, self.btn_customize, self.btn_settings,
                                self.btn_songedit):
                        _bb.configure(bg=c, activebackground=c)
                except Exception:
                    pass
            elif str(cfg.get("modo", "heredar")) == "imagen" and str(cfg.get("imagen_path", "")):
                avg = self._panel_avg("barra_superior") or _t
                try:
                    self.topbar.configure(bg=avg)
                    for _bb in (self.btn_search, self.btn_openurl, self.btn_customize, self.btn_settings,
                                self.btn_songedit):
                        _bb.configure(bg=avg, activebackground=avg)
                except Exception:
                    pass
                self._panel_bg_label("barra_superior", self.topbar)
                try:
                    self._maybe_panel_gif("barra_superior", self.topbar)
                except Exception:
                    pass
            # --- full sidebar ---
            cfg = self._panel_cfg("lateral")
            if str(cfg.get("modo", "heredar")) == "color" and cfg.get("color"):
                c = str(cfg["color"])
                try:
                    self.sidebar.configure(bg=c)
                except Exception:
                    pass
            elif str(cfg.get("modo", "heredar")) == "imagen" and str(cfg.get("imagen_path", "")):
                avg = self._panel_avg("lateral") or _t
                try:
                    self.sidebar.configure(bg=avg)
                except Exception:
                    pass
                self._panel_bg_label("lateral", self.sidebar)
                try:
                    self._maybe_panel_gif("lateral", self.sidebar)
                except Exception:
                    pass
            # --- YT playlists list (REAL image background via _BgListbox) ---
            cfg = self._panel_cfg("lateral_playlists")
            if str(cfg.get("modo", "heredar")) == "color" and cfg.get("color"):
                try:
                    self.playlist_box.set_background(None)
                except Exception:
                    pass
                try:
                    self.playlist_box.configure(bg=str(cfg["color"]))
                except Exception:
                    pass
            elif str(cfg.get("modo", "heredar")) == "imagen" and str(cfg.get("imagen_path", "")):
                p = str(cfg.get("imagen_path", ""))
                if p and os.path.exists(p):
                    try:
                        from PIL import Image
                        self.playlist_box.set_background(Image.open(p).convert("RGB"))
                    except Exception:
                        pass
                    try:
                        self.playlist_box.configure(bg=self._panel_avg("lateral_playlists") or _m)
                    except Exception:
                        pass
                else:
                    try:
                        self.playlist_box.set_background(None)
                    except Exception:
                        pass
            else:
                try:
                    self.playlist_box.set_background(None)
                except Exception:
                    pass
            # --- player ---
            cfg = self._panel_cfg("reproductor")
            if str(cfg.get("modo", "heredar")) == "color" and cfg.get("color"):
                c = str(cfg["color"])
                try:
                    for _w in [self.playerbar] + list(getattr(self, "_player_mid", []) or []) + [getattr(self, "_ctrl_frame", None)]:
                        if _w is not None:
                            _w.configure(bg=c)
                    for _bb in (self.btn_prev, self.btn_play, self.btn_next,
                                self.btn_shuffle, self.btn_loop, self.btn_fav,
                                self.btn_vol_down, self.btn_vol_up):
                        _bb.configure(bg=c, activebackground=c)
                    self.vol_value.configure(bg=c)
                    # Song name / times live INSIDE the player bar: keep them
                    # on the same background or they look "inverted".
                    try:
                        self.song_label.configure(bg=c)
                    except Exception:
                        pass
                    try:
                        self.thumb_label.configure(bg=c)
                    except Exception:
                        pass
                    for _w in list(getattr(self, "_player_mid", []) or []):
                        try:
                            for _ch in _w.winfo_children():
                                try:
                                    _ch.configure(bg=c)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    self._refresh_vol_icon()
                except Exception:
                    pass
            elif str(cfg.get("modo", "heredar")) == "imagen" and str(cfg.get("imagen_path", "")):
                avg = self._panel_avg("reproductor") or _b
                try:
                    for _w in [self.playerbar] + list(getattr(self, "_player_mid", []) or []) + [getattr(self, "_ctrl_frame", None)]:
                        if _w is not None:
                            _w.configure(bg=avg)
                    for _bb in (self.btn_prev, self.btn_play, self.btn_next,
                                self.btn_shuffle, self.btn_loop, self.btn_fav,
                                self.btn_vol_down, self.btn_vol_up):
                        _bb.configure(bg=avg, activebackground=avg)
                    self.vol_value.configure(bg=avg)
                    try:
                        self.song_label.configure(bg=avg)
                    except Exception:
                        pass
                    try:
                        self.thumb_label.configure(bg=avg)
                    except Exception:
                        pass
                    for _w in list(getattr(self, "_player_mid", []) or []):
                        try:
                            for _ch in _w.winfo_children():
                                try:
                                    _ch.configure(bg=avg)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    self._refresh_vol_icon()
                except Exception:
                    pass
                self._panel_bg_label("reproductor", self.playerbar)
                try:
                    self._maybe_panel_gif("reproductor", self.playerbar)
                except Exception:
                    pass
            # --- progress (bar trough + times) ---
            cfg = self._panel_cfg("progreso")
            if str(cfg.get("modo", "heredar")) in ("color", "imagen"):
                c = str(cfg.get("color", "") or "") if str(cfg.get("modo")) == "color" else (self._panel_avg("progreso") or _b)
                if c:
                    try:
                        self.progress.configure(background=c)
                        self.time_a.configure(bg=c)
                        self.time_b.configure(bg=c)
                    except Exception:
                        pass
            # --- volume ---
            cfg = self._panel_cfg("volumen")
            if str(cfg.get("modo", "heredar")) in ("color", "imagen"):
                c = str(cfg.get("color", "") or "") if str(cfg.get("modo")) == "color" else (self._panel_avg("volumen") or _b)
                if c:
                    try:
                        self.volf.configure(bg=c)
                        self.vol_value.configure(bg=c)
                        self._refresh_vol_icon()
                    except Exception:
                        pass
            # Slider colours come from widgets.slider, not from the panel
            # background: the two used to fight each other and the slider
            # colours the user picks were always overwritten here.
            try:
                self.apply_widgets_theme()
            except Exception:
                pass
        except Exception:
            pass

    def _pick_panel_color(self, key: str) -> None:
        c = colorchooser.askcolor(title=f"Panel color: {key}")
        if c and c[1]:
            try:
                cfg = dict(self._panel_cfg(key) or {})
                cfg.update({"modo": "color", "color": c[1], "imagen_path": ""})
                self.theme.data.setdefault("fondos_paneles", {})[key] = cfg
                if key == "lateral_playlists":
                    try:
                        self.playlist_box.set_background(None)
                    except Exception:
                        pass
                try:
                    toks = getattr(self, "_panel_gif_toks", None) or {}
                    toks[key] = int(toks.get(key, 0) or 0) + 1
                except Exception:
                    pass
                try:
                    old = (getattr(self, "_panel_bg_labels", {}) or {}).pop(key, None)
                    if old is not None:
                        old.destroy()
                except Exception:
                    pass
                try:
                    getattr(self, "_panel_avg_cache", {}).pop(key, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _pick_panel_image(self, key: str) -> None:
        p = filedialog.askopenfilename(title=f"Panel image: {key}",
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if p:
            try:
                cfg = dict(self._panel_cfg(key) or {})
                cfg.update({"modo": "imagen", "imagen_path": p, "color": ""})
                self.theme.data.setdefault("fondos_paneles", {})[key] = cfg
                try:
                    getattr(self, "_panel_avg_cache", {}).pop(key, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _reset_panel_bg(self, key: str) -> None:
        try:
            self.theme.data.setdefault("fondos_paneles", {})[key] = {
                "modo": "heredar", "color": "", "imagen_path": ""}
            try:
                getattr(self, "_panel_avg_cache", {}).pop(key, None)
            except Exception:
                pass
            try:
                old = (getattr(self, "_panel_bg_labels", {}) or {}).pop(key, None)
                if old is not None:
                    old.destroy()
            except Exception:
                pass
            try:
                toks = getattr(self, "_panel_gif_toks", None) or {}
                toks[key] = int(toks.get(key, 0) or 0) + 1
            except Exception:
                pass
            if key == "lateral_playlists":
                try:
                    self.playlist_box.set_background(None)
                except Exception:
                    pass
            self.theme.save()
            self.apply_theme()
        except Exception:
            pass

    # ---------- section backgrounds ----------
    def _seccion_efectiva(self) -> str:
        """Effective section for backgrounds (no local lists: direct)."""
        try:
            return str(getattr(self, "current_section", "buscar") or "buscar")
        except Exception:
            return "buscar"

    def _section_cfg(self, section: str) -> dict:
        try:
            cfg = (self.theme.data.get("fondos_secciones", {}) or {}).get(section or "", {}) or {}
        except Exception:
            cfg = {}
        return cfg if isinstance(cfg, dict) else {}

    def _section_avg_color(self, section: str) -> str:
        """Average color of the section custom image/video (cached)."""
        try:
            cfg = self._section_cfg(section)
            mode = str(cfg.get("modo", "heredar"))
            path = str(cfg.get("imagen_path", "") or cfg.get("video_path", "") or "")
            if mode not in ("imagen", "video") or not path or not os.path.exists(path):
                return ""
            cache = getattr(self, "_sec_avg_cache", None)
            if cache is None:
                cache = {}
                self._sec_avg_cache = cache
            hit = cache.get(section)
            if isinstance(hit, dict) and hit.get("path") == path and hit.get("avg"):
                return str(hit["avg"])
            avg = ""
            try:
                from PIL import Image as _I
                if mode == "video":
                    img = self._video_first_frame(path, 64, 64)
                else:
                    img = _I.open(path).convert("RGB").resize((64, 64))
                avg = _avg_color_hex(img)
            except Exception:
                avg = ""
            cache[section] = {"path": path, "avg": avg}
            return avg or ""
        except Exception:
            return ""

    def _effective_section_bg(self, section: str) -> dict:
        """Effective background of a section: inherit->global, or custom."""
        cfg = self._section_cfg(section)
        if not cfg or str(cfg.get("modo", "heredar")) == "heredar":
            try:
                return dict(self.theme.data.get("fondo", {}))
            except Exception:
                return {}
        out = dict(self.theme.data.get("fondo", {}))
        for k in ("modo", "color", "color2", "imagen_path", "video_path"):
            if cfg.get(k):
                out[k] = cfg[k]
        return out

    def _paint_section_background(self) -> None:
        """Tint ONLY the list area with the current section own background.

        - color: canvas+listframe in that color (rows already blend in _band).
        - image/video: canvas with the image (or first frame) + listframe with
          its average color + rows re-tinted via _band (else opaque rows
          covered the image and it looked broken).
        - heredar: sync with global tints.
        Re-applied after every global redraw (see _finish_bg_render).
        """
        try:
            sec = self._seccion_efectiva()
            eff = self._effective_section_bg(sec)
            mode = str(eff.get("modo", "heredar"))
            if mode == "color" and eff.get("color"):
                sec_color = str(eff["color"])
                try:
                    self.canvas.configure(bg=sec_color)
                    self.listframe.configure(bg=sec_color)
                except Exception:
                    pass
                try:
                    self._retint_rows()
                except Exception:
                    pass
                return
            if mode in ("imagen", "video"):
                p = str(eff.get("imagen_path", "") or eff.get("video_path", "") or "")
                if p and os.path.exists(p):
                    try:
                        from PIL import Image, ImageTk
                        cw = max(200, self.canvas.winfo_width() or 400)
                        ch = max(200, self.canvas.winfo_height() or 300)
                        if mode == "video":
                            img = self._video_first_frame(p, cw, ch)
                        else:
                            img = Image.open(p).convert("RGB").resize((cw, ch))
                        self._canvas_bg_pil = img
                        self._canvas_bg_photo = ImageTk.PhotoImage(img)
                        if self._canvas_bg_id is None:
                            self._canvas_bg_id = self.canvas.create_image(0, 0, anchor="nw", image=self._canvas_bg_photo, tags=("bg",))
                        else:
                            self.canvas.itemconfigure(self._canvas_bg_id, image=self._canvas_bg_photo)
                        self._pin_canvas_bg()
                        avg = self._section_avg_color(sec) or getattr(self, "_tint_mid", "#222222")
                        try:
                            self.listframe.configure(bg=avg)
                        except Exception:
                            pass
                        try:
                            self._retint_rows()
                        except Exception:
                            pass
                        try:
                            self.status.configure(text=f"Fondo '{sec}': {os.path.basename(p)} ✔")
                        except Exception:
                            pass
                        # Animated GIF on the section canvas (rows
                        # use the first frame via tiles: animating 80 tiles would be
                        # way too costly, the canvas shows through the gaps).
                        try:
                            if mode == "imagen" and self._is_gif(p):
                                self._start_sec_gif(sec, p, int(cw), int(ch))
                            else:
                                self._sec_gif_token = int(getattr(self, "_sec_gif_token", 0) or 0) + 1
                        except Exception:
                            pass
                        return
                    except Exception:
                        pass
                    # If image/video fails: fall back to global (no black left)
            # Inherit / gradient: global background already painted; ensure sync
            try:
                self._sec_gif_token = int(getattr(self, "_sec_gif_token", 0) or 0) + 1
            except Exception:
                pass
            try:
                self.canvas.configure(bg=self._tint_mid)
                self.listframe.configure(bg=self._tint_mid)
            except Exception:
                pass
        except Exception:
            pass

    def _start_sec_gif(self, sec: str, path: str, cw: int, ch: int) -> None:
        """Animate the section canvas with a GIF. Load on thread, paint on UI."""
        try:
            self._sec_gif_token = int(getattr(self, "_sec_gif_token", 0) or 0) + 1
            tok = self._sec_gif_token
            self._sec_gif_sec = str(sec)
            self._sec_gif_path = str(path)
        except Exception:
            return

        def _load():
            try:
                frames = self._load_gif_frames(path, max(200, int(cw)), max(200, int(ch)))
                self._call_ui(self._begin_sec_gif, tok, str(sec), str(path), frames)
            except Exception:
                pass
        try:
            threading.Thread(target=_load, daemon=True).start()
        except Exception:
            pass

    def _begin_sec_gif(self, tok: int, sec: str, path: str, frames) -> None:
        try:
            if tok != getattr(self, "_sec_gif_token", 0):
                return
            if str(sec) != str(getattr(self, "_sec_gif_sec", "")):
                return
            if str(path) != str(getattr(self, "_sec_gif_path", "")):
                return
            if not frames or len(frames) < 2:
                return
            from PIL import ImageTk
            photos = []
            for fr, dur in frames:
                try:
                    photos.append((ImageTk.PhotoImage(fr.convert("RGB")), int(dur)))
                except Exception:
                    continue
            if len(photos) < 2:
                return
            self._sec_gif_photos = photos
            self._sec_gif_i = 0
            self._sec_gif_tick(tok)
        except Exception:
            pass

    def _sec_gif_tick(self, tok: int) -> None:
        try:
            if tok != getattr(self, "_sec_gif_token", 0):
                return
            if getattr(self, "_closed", False):
                return
            try:
                if self._seccion_efectiva() != str(getattr(self, "_sec_gif_sec", "")):
                    return
                cfg = self._section_cfg(str(getattr(self, "_sec_gif_sec", "")))
                if not (str(cfg.get("modo", "")) == "imagen"
                        and str(cfg.get("imagen_path", "")) == str(getattr(self, "_sec_gif_path", ""))):
                    return
            except Exception:
                return
            phs = getattr(self, "_sec_gif_photos", None) or []
            if not phs:
                return
            i = int(getattr(self, "_sec_gif_i", 0) or 0) % len(phs)
            ph, dur = phs[i]
            try:
                self._canvas_bg_photo = ph
                if self._canvas_bg_id is None:
                    self._canvas_bg_id = self.canvas.create_image(
                        0, 0, anchor="nw", image=ph, tags=("bg",))
                    try:
                        self.canvas.tag_lower(self._canvas_bg_id)
                    except Exception:
                        pass
                else:
                    self.canvas.itemconfigure(self._canvas_bg_id, image=ph)
                self._pin_canvas_bg()
            except Exception:
                return
            self._sec_gif_i = i + 1
            try:
                self.root.after(max(60, int(dur)), lambda: self._sec_gif_tick(tok))
            except Exception:
                pass
        except Exception:
            pass

    # ---------- progressive lists (fast, never blow up) ----------
    def _batch_size(self) -> int:
        try:
            return max(20, min(300, int(self.theme.get("lista", "lote_progresivo", default=80) or 80)))
        except Exception:
            return 80

    def _new_progressive_token(self) -> int:
        self._progressive_token = int(getattr(self, "_progressive_token", 0) or 0) + 1
        return self._progressive_token

    def _set_full_list(self, tracks: list[dict], title: str, token: int, is_final: bool) -> None:
        if token != getattr(self, "_progressive_token", 0):
            return  # stale: the user switched section
        self.current_list_full = list(tracks or [])
        # On first batch, reset scroll and visible rows; later, keep scroll
        first = not getattr(self, "_loading_progressive", False) or len(self.current_list) == 0
        if first:
            self.current_list = list(self.current_list_full[:self._batch_size()])
            self.visible_count = len(self.current_list)
        else:
            # Extend visible rows if the user already asked for "show more"
            want = max(self.visible_count, len(self.current_list))
            self.current_list = list(self.current_list_full[:max(want, self._batch_size())])
            self.visible_count = len(self.current_list)
        total = len(self.current_list_full)
        shown = len(self.current_list)
        suffix = "" if is_final else " ↳ loading…"
        try:
            self.list_title.configure(text=f"{title} ({shown}/{total}{suffix})")
        except Exception:
            pass
        try:
            self.status.configure(text="Ready" if is_final else f"Progressive loading… {total} (non-blocking)")
        except Exception:
            pass
        self._loading_progressive = not is_final
        # New list: the virtualized window starts again from the beginning.
        self._window_start = 0
        self._base_window = len(self.current_list)
        self._painted_order = []
        try:
            self._paint_playlist_toggle()
        except Exception:
            pass
        # "Play all" from the playlist menu (progressive path).
        try:
            if (is_final and getattr(self, "_open_autoplay", "")
                    and (self.current_list_full or [])
                    and any(isinstance(t, dict) and t.get("videoId")
                            for t in (self.current_list_full or [])[:5])):
                self._open_autoplay = ""
                first = next((t for t in (self.current_list_full or [])
                              if isinstance(t, dict) and t.get("videoId")), None)
                if first:
                    self.play_track(first)
        except Exception:
            pass
        try:
            if (getattr(self, "current_section", "") == "playlists"
                    and getattr(self, "playlist_view_mode", "list") != "list"
                    and (tracks or self.current_list_full)
                    and any(isinstance(t, dict) and t.get("_playlist_id")
                            for t in (list(tracks or []) + list(self.current_list_full or []))[:5])):
                self._ensure_playlist_toggle()
                self._render_playlists_current_view()
                # Still show continuation for grid/custom view after render
                if is_final and self.player.loop_mode == "off":
                    self._show_playlist_continuation()
                return
        except Exception:
            pass
        # A progressive batch must NEVER rebuild the list. The first batch of a
        # fresh section does a full render; every later batch only appends the
        # rows that are not on screen yet. Rebuilding per batch is exactly
        # what made long playlists flicker and restart every thumbnail.
        if first:
            self.render_list(keep_scroll=False)
        else:
            self._append_only()
            try:
                self._update_more_button()
            except Exception:
                pass
        # Playlist/queue continuation: when loop is OFF in a playlist or the
        # queue, show a separator + recommended songs below that can be
        # played but are NOT added to the playlist/queue. Only after the
        # final batch. Called AFTER render_list so the separator rows are not
        # destroyed. Works regardless of current_section (a playlist opened
        # from search/URL still has section "buscar" but is still a playlist).
        try:
            if is_final and self.player.loop_mode == "off":
                # Only show if we are viewing playlist/album tracks (not search results)
                has_playlist_rows = any(
                    isinstance(t, dict) and t.get("_playlist_id")
                    for t in (self.current_list_full or [])[:5]
                )
                is_queue = getattr(self, "current_section", "") == "cola"
                is_playlist_ctx = bool(getattr(self, "current_playlist_id", ""))
                is_album_ctx = bool(getattr(self, "_album_mode", False))
                if has_playlist_rows or is_queue or is_playlist_ctx or is_album_ctx:
                    self._show_playlist_continuation()
        except Exception:
            pass

    def _on_canvas_configure(self, event=None) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self._pin_canvas_bg()
        self._schedule_retile()

    def _autocheck_more(self) -> None:
        try:
            if not getattr(self, "_closed", False):
                # Only auto-load on real scroll (content taller than the view)
                # and the user is past 85%. If everything fits on screen we do not
                # load alone: the "Show more" button decides.
                try:
                    top, bottom = self.canvas.yview()
                    if bottom >= 0.92 and top > 0.0:
                        self.show_more_rows(silent=True)
                    else:
                        try:
                            bbox = self.canvas.bbox("all")
                            ch = self.canvas.winfo_height() or 0
                            if bbox and ch and (bbox[3] - bbox[1]) > ch * 1.2 and bottom >= 0.92:
                                self.show_more_rows(silent=True)
                        except Exception:
                            pass
                except Exception:
                    pass
                self.root.after(1200, self._autocheck_more)
        except Exception:
            pass

    def show_more_rows(self, silent: bool = False) -> None:
        try:
            # In Playlists grid/custom mode, rebuild tiles (not song rows).
            try:
                if (self._is_playlist_rows()
                        and str(getattr(self, "playlist_view_mode", "list") or "list") != "list"):
                    if len(self.current_list) >= len(self.current_list_full):
                        if not silent:
                            try:
                                self.status.configure(text="Everything loaded ✔")
                            except Exception:
                                pass
                        return
                    add = self._batch_size()
                    nxt = self.current_list_full[len(self.current_list):len(self.current_list) + add]
                    if not nxt:
                        return
                    self.current_list.extend(nxt)
                    self.visible_count = len(self.current_list)
                    self._render_playlists_current_view()
                    try:
                        base = self.list_title.cget("text").split(" (")[0]
                        self.list_title.configure(
                            text=f"{base} ({len(self.current_list)}/{len(self.current_list_full)})")
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            if len(self.current_list) >= len(self.current_list_full):
                if not silent:
                    try:
                        self.status.configure(text="Everything loaded ✔")
                    except Exception:
                        pass
                return
            # Remove the old "show more" button (else new rows would land below it)
            try:
                if getattr(self, "_more_btn_row", None) is not None:
                    try:
                        self._more_btn_row.destroy()
                    except Exception:
                        pass
                    try:
                        self.row_widgets = [w for w in self.row_widgets if w is not self._more_btn_row]
                    except Exception:
                        pass
                    self._more_btn_row = None
            except Exception:
                pass
            add = self._batch_size()
            base = self._base_tracks()
            # The window always moves FORWARD: the songs after the last one
            # that is on screen (never back to the ones already passed).
            painted_base = [t for t in (self.current_list or [])
                            if isinstance(t, dict) and not t.get("_continuation")]
            start = 0
            if painted_base:
                last = painted_base[-1]
                for i in range(len(base) - 1, -1, -1):
                    if base[i] is last:
                        start = i + 1
                        break
            nxt: list[dict] = list(base[start:start + add])
            if not nxt:
                if not silent:
                    try:
                        self.status.configure(text="Everything loaded ✔")
                    except Exception:
                        pass
                return
            # Too many rows alive? Move the window forward instead of
            # painting thousands of widgets (that froze the app).
            live = len([w for w in self.row_widgets
                        if getattr(w, "_is_draggable", False)])
            if live + len(nxt) > int(getattr(self, "MAX_LIVE_ROWS", 200)):
                if silent:
                    # Auto-load while scrolling: do NOT jump the view. The
                    # "Show more" button pages the list when the user asks.
                    return
                # Page forward: the rows already on screen are RE-USED for
                # the next songs, so nothing is destroyed and the interface
                # never freezes (destroying hundreds of rows took 1 s).
                page = base[start:start + max(live, len(nxt))]
                if not page:
                    return
                self._window_start = start
                self._base_window = len(page)
                self._painted_order = []
                self.current_list = list(page) + self._rec_tracks()
                self.visible_count = len(self.current_list)
                self._render_window(self.current_list)
                try:
                    self.canvas.yview_moveto(0)
                except Exception:
                    pass
                return
            base_part = [t for t in (self.current_list or [])
                         if isinstance(t, dict) and not t.get("_continuation")]
            rec_part = [t for t in (self.current_list or [])
                        if isinstance(t, dict) and t.get("_continuation")]
            self._base_window = len(base_part) + len(nxt)
            self.current_list = base_part + nxt + rec_part
            self.visible_count = len(self.current_list)
            # Append-only: already painted rows are never touched.
            self._append_only()
            # Put the button back if items remain
            try:
                total = len(self.current_list_full)
                shown = len(self.current_list)
                if total > shown:
                    more = tk.Frame(self.listframe, bg=getattr(self, "_tint_mid", "#222222"))
                    more.pack(fill="x", padx=4, pady=6)
                    self._more_btn_row = more
                    self.row_widgets.append(more)
                    rest = total - shown
                    b = tk.Button(more, text=f"Show more ({rest} left)",
                                  command=lambda: self.show_more_rows())
                    b.pack(pady=6)
                    try:
                        self._style_button(b, f"Show more ({rest} left)",
                                           getattr(self, "_tint_mid", "#222222"),
                                           size=30, wide=True, fontsize=11)
                    except Exception:
                        pass
                else:
                    self._more_btn_row = None
            except Exception:
                pass
            total = len(self.current_list_full)
            shown = len(self.current_list)
            try:
                base = self.list_title.cget("text").split(" (")[0]
                rest = "" if self._loading_progressive else ""
                self.list_title.configure(text=f"{base} ({shown}/{total}{rest})")
            except Exception:
                pass
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._schedule_retile()
        except Exception:
            pass

    # ---------- video/cover panel (movable + resizable, inside the window) ----------
    def _video_pos_abs(self) -> tuple[int, int, int, int]:
        """ABSOLUTE video panel position = window + relative dx/dy."""
        try:
            cfg = self.theme.data.get("video_panel", {}) or {}
            try:
                dx = int(cfg.get("dx", cfg.get("x", 620)))
            except Exception:
                dx = 620
            try:
                dy = int(cfg.get("dy", cfg.get("y", 120)))
            except Exception:
                dy = 120
            try:
                w, h = int(cfg.get("w", 320)), int(cfg.get("h", 240))
            except Exception:
                w, h = 320, 240
        except Exception:
            dx, dy, w, h = 620, 120, 320, 240
        try:
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
        except Exception:
            rx, ry = 100, 100
        return rx + dx, ry + dy, max(160, w), max(120, h)

    def _video_bar_colors(self) -> tuple[str, str]:
        """Video bar colors ALWAYS from the active theme (never hardcoded)."""
        try:
            b = (self.theme.data.get("botones", {}) or {})
            bg = str(b.get("color_fondo", "") or (self.theme.data.get("lista", {}) or {}).get("color_fondo", "#222222"))
            fg = str(b.get("color_texto", "") or (self.theme.data.get("texto", {}) or {}).get("color_titulo", "#ffffff"))
            return bg or "#222222", fg or "#ffffff"
        except Exception:
            return "#222222", "#ffffff"

    def _paint_video_bar(self) -> None:
        """Repaint video panel chrome with the ACTIVE theme colors."""
        try:
            bg, fg = self._video_bar_colors()
            win = getattr(self, "_video_panel", None)
            if win is not None:
                try:
                    win.configure(bg="#000000")
                except Exception:
                    pass
            pnl = getattr(self, "_video_pnl", None)
            if pnl is not None:
                try:
                    pnl.configure(bg="#000000", highlightbackground=bg)
                except Exception:
                    pass
            bar = getattr(self, "_video_bar", None)
            if bar is not None:
                try:
                    bar.configure(bg=bg)
                except Exception:
                    pass
            ttl = getattr(self, "_video_title", None)
            if ttl is not None:
                try:
                    ttl.configure(bg=bg, fg=fg)
                except Exception:
                    pass
            for _b in list(getattr(self, "_video_bar_btns", []) or []):
                try:
                    _b.configure(bg=bg, fg=fg, activebackground=bg, activeforeground=fg)
                except Exception:
                    pass
            grip = getattr(self, "_video_grip", None)
            if grip is not None:
                try:
                    grip.configure(bg=bg, fg=fg)
                except Exception:
                    pass
            for _g in list(getattr(self, "_video_grips", []) or []):
                try:
                    _w = _g[1] if isinstance(_g, (tuple, list)) else _g
                    _w.configure(bg=bg)
                except Exception:
                    pass
        except Exception:
            pass

    def _ensure_video_panel(self) -> None:
        if getattr(self, "_video_panel", None) is not None:
            try:
                self._video_panel.winfo_exists()
                return
            except Exception:
                self._video_panel = None
        ax, ay, w, h = self._video_pos_abs()
        try:
            # Frameless Toplevel: may leave the window and follows it
            # (like stickers). It is TRANSIENT to the main window and WITH
            # -topmost: stays above the main window so it never ends up
            # hidden behind it.
            win = tk.Toplevel(self.root)
            # Same frameless bar + app icon as the main window
            self._frameless_toplevel(win)
            try:
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                try:
                    win.transient(self.root)
                except Exception:
                    pass
                win.configure(bg="#000000")
                win.geometry(f"{w}x{h}+{ax}+{ay}")
            except Exception:
                pass
            pnl = tk.Frame(win, bg="#000000", highlightthickness=2)
            try:
                _hl0, _ = self._video_bar_colors()
                pnl.configure(highlightbackground=_hl0)
            except Exception:
                pass
            pnl.pack(fill="both", expand=True)
            # Grab bar (themed: never hardcoded purple)
            _vbg, _vfg = self._video_bar_colors()
            bar = tk.Frame(pnl, bg=_vbg, height=26)
            bar.pack(fill="x", side="top")
            bar.pack_propagate(False)
            ttl = tk.Label(bar, text="▶ Video / Cover", bg=_vbg, fg=_vfg, font=("Segoe UI", 9, "bold"), anchor="w")
            ttl.pack(side="left", padx=6, fill="x", expand=True)
            btn_hide = tk.Button(bar, text="–", command=self._toggle_video_panel, font=("Segoe UI", 9, "bold"), bg=_vbg, fg=_vfg, relief="flat", bd=0, width=3)
            btn_hide.pack(side="right")
            btn_show = tk.Button(bar, text="▢", command=self._toggle_video_panel, font=("Segoe UI", 9), bg=_vbg, fg=_vfg, relief="flat", bd=0, width=3)
            btn_show.pack(side="right")
            btn_full = tk.Button(bar, text="▣", command=self._toggle_video_fullscreen, font=("Segoe UI", 9), bg=_vbg, fg=_vfg, relief="flat", bd=0, width=3)
            btn_full.pack(side="right")
            btn_res = tk.Button(bar, text="⚙︎", command=self._open_video_res_menu, font=("Segoe UI", 9), bg=_vbg, fg=_vfg, relief="flat", bd=0, width=3)
            btn_res.pack(side="right")
            lbl = tk.Label(pnl, bg="black", fg="white", text="♪")
            lbl.pack(fill="both", expand=True)
            # Double-click toggles YouTube-like fullscreen; Esc exits it.
            try:
                lbl.bind("<Double-Button-1>", lambda e: self._toggle_video_fullscreen(), add="+")
                pnl.bind("<Double-Button-1>", lambda e: self._toggle_video_fullscreen(), add="+")
                win.bind("<Double-Button-1>", lambda e: self._toggle_video_fullscreen(), add="+")
                bar.bind("<Double-Button-1>", lambda e: self._toggle_video_fullscreen(), add="+")
            except Exception:
                pass
            # NO overlay grip widgets: they sat on top of the bar buttons
            # (NE/NW corners) and swallowed clicks, so ⚙︎/▣ looked "hidden".
            # Resize/drag is decided by click POSITION (border zones), so no
            # widget ever covers the controls.
            self._video_grips = []
            self._video_panel = win
            self._video_bar = bar
            self._video_pnl = pnl
            self._video_grip = None
            self._video_bar_btns = [btn_hide, btn_show, btn_full, btn_res]
            self._video_label = lbl
            self._video_title = ttl
            self._bind_video_zones(win, pnl, bar, ttl, lbl)
            # If the video is clicked and ended up below stickers, reorder
            try:
                win.bind("<FocusIn>", lambda e: self._stack_overlay_order(), add="+")
            except Exception:
                pass
            # No floating "▶ Video" button: shown/hidden from
            # Customize > Video (user request).
            try:
                self._video_fab = None
            except Exception:
                pass
            vis = True
            try:
                vis = bool(self.theme.get("video_panel", "visible", default=True))
            except Exception:
                pass
            if not vis:
                try:
                    win.withdraw()
                except Exception:
                    pass
            # First paint: current cover or placeholder
            try:
                self.root.after(800, self._refresh_video_panel)
            except Exception:
                pass
            try:
                self._stack_overlay_order()
            except Exception:
                pass
        except Exception:
            pass

    def _stack_overlay_order(self) -> None:
        """Stacking order: main < video < stickers (ONLY inside the app).

        Video and stickers are transient to the main window WITHOUT -topmost:
        the window manager keeps them above it without imposing them on other
        programs. Only the relative order is adjusted here (never touching
        topmost: re-asserting it every tick caused flicker over other windows).
        """
        try:
            if getattr(self, "_closed", False):
                return
            # If the main window is minimized, hide overlays (else
            # they float alone on the desktop).
            try:
                if str(self.root.state()) == "iconic":
                    return
            except Exception:
                pass
            vw = getattr(self, "_video_panel", None)
            if vw is not None:
                try:
                    vw.winfo_exists()
                except Exception:
                    vw = None
            if vw is not None:
                try:
                    if bool(self.theme.get("video_panel", "visible", default=True)):
                        try:
                            vw.lift(self.root)
                        except Exception:
                            try:
                                vw.lift()
                            except Exception:
                                pass
                except Exception:
                    pass
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    w = st.get("win")
                    if w is None:
                        continue
                    try:
                        w.winfo_exists()
                    except Exception:
                        continue
                    try:
                        if vw is not None:
                            w.lift(vw)
                        else:
                            w.lift()
                    except Exception:
                        try:
                            w.lift()
                        except Exception:
                            pass
                except Exception:
                    pass
            try:
                self._overlay_order_ok = True
            except Exception:
                pass
        except Exception:
            pass

    def _our_window_is_foreground(self) -> bool:
        """Is our app (main, video, stickers or dialogs) in the foreground?
        Only then does reordering the overlays make sense."""
        try:
            if os.name != "nt":
                try:
                    return self.root.focus_displayof() is not None
                except Exception:
                    return True
            import ctypes
            try:
                fg = ctypes.windll.user32.GetForegroundWindow()
            except Exception:
                return True
            if not fg:
                return False
            try:
                _pid = ctypes.c_ulong(0)
                ctypes.windll.user32.GetWindowThreadProcessId(
                    fg, ctypes.byref(_pid))
                return int(_pid.value) == int(os.getpid())
            except Exception:
                return True
        except Exception:
            return True

    def _ensure_overlay_topmost(self) -> None:
        """Keep video/stickers as an APP layer (not system-wide).

        They are transient windows of the main one WITHOUT -topmost: they stay
        above it but the system covers them with other programs (before, with
        topmost + topmost re-asserted every 500ms, they flickered over foreign
        windows). Reorder only happens when our app is in the foreground and
        the order is marked dirty: no blind lifts.
        """
        try:
            if getattr(self, "_closed", False):
                return
            try:
                _iconic = (str(self.root.state()) == "iconic")
            except Exception:
                _iconic = False
            if _iconic:
                # Minimized: hide overlays so none are orphaned
                try:
                    vw = getattr(self, "_video_panel", None)
                    if vw is not None:
                        vw.withdraw()
                except Exception:
                    pass
                for st in list(getattr(self, "_stickers", []) or []):
                    try:
                        st.get("win").withdraw()
                    except Exception:
                        pass
                try:
                    self._overlay_order_ok = False
                except Exception:
                    pass
                return
            # Restore overlays if the main window is back and they were hidden by
            # minimizing (but the user wants them visible).
            _restored = False
            try:
                vw = getattr(self, "_video_panel", None)
                if vw is not None and bool(self.theme.get("video_panel", "visible", default=True)):
                    try:
                        _st = str(vw.state())
                    except Exception:
                        _st = ""
                    if _st in ("withdrawn", "iconic"):
                        try:
                            vw.deiconify()
                            _restored = True
                        except Exception:
                            pass
                for st in list(getattr(self, "_stickers", []) or []):
                    try:
                        w = st.get("win")
                        if w is not None and str(w.state()) in ("withdrawn", "iconic"):
                            try:
                                w.deiconify()
                                _restored = True
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
            if _restored:
                try:
                    self._overlay_order_ok = False
                except Exception:
                    pass
            # Reorder ONLY if needed and we are the foreground app.
            try:
                if (not getattr(self, "_overlay_order_ok", False)
                        and self._our_window_is_foreground()):
                    self._stack_overlay_order()
            except Exception:
                pass
        except Exception:
            pass

    def _toggle_video_panel(self) -> None:
        try:
            # Never hide the window while fullscreen: exit fullscreen instead.
            if getattr(self, "_video_fullscreen", False):
                self._exit_video_fullscreen()
                return
            self._ensure_video_panel()
            vis = True
            try:
                vis = bool(self.theme.get("video_panel", "visible", default=True))
            except Exception:
                pass
            if vis:
                try:
                    self._video_panel.withdraw()
                except Exception:
                    pass
                self.theme.set(False, "video_panel", "visible")
                try:
                    self.status.configure(text="Video panel hidden (Customize > Video to show it)")
                except Exception:
                    pass
            else:
                try:
                    ax, ay, w, h = self._video_pos_abs()
                    self._video_panel.geometry(f"{w}x{h}+{ax}+{ay}")
                    self._video_panel.deiconify()
                    try:
                        self._video_panel.attributes("-topmost", True)
                        self._video_panel.transient(self.root)
                    except Exception:
                        pass
                except Exception:
                    pass
                self.theme.set(True, "video_panel", "visible")
                try:
                    self._stack_overlay_order()
                except Exception:
                    pass
                self._refresh_video_panel()
        except Exception:
            pass

    def _toggle_video_fullscreen(self) -> None:
        """Toggle video panel fullscreen mode (hide everything else, video fills screen)."""
        try:
            if getattr(self, "_video_fullscreen", False):
                self._exit_video_fullscreen()
            else:
                self._enter_video_fullscreen()
        except Exception:
            pass

    def _enter_video_fullscreen(self) -> None:
        """Enter video fullscreen like YouTube: video fills the whole screen."""
        try:
            if getattr(self, "_video_fullscreen", False):
                return
            self._video_fullscreen = True
            # Hide stickers
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    st.get("win").withdraw()
                except Exception:
                    pass
            # Ensure video panel exists and is visible
            self._ensure_video_panel()
            self.theme.set(True, "video_panel", "visible")
            try:
                self._video_panel.deiconify()
            except Exception:
                pass
            # Save current geometry to restore later
            try:
                self._video_prev_geom = str(self._video_panel.geometry())
            except Exception:
                self._video_prev_geom = None
            # Keep frameless (never toggle overrideredirect: on Windows that
            # recreates the HWND and the panel turns invisible).
            try:
                self._video_panel.overrideredirect(True)
            except Exception:
                pass
            # Hide the bar + resize grips: 100% video like YouTube.
            try:
                self._video_bar.pack_forget()
            except Exception:
                pass
            for _g in list(getattr(self, "_video_grips", []) or []):
                try:
                    (_g[1] if isinstance(_g, (tuple, list)) else _g).place_forget()
                except Exception:
                    pass
            try:
                self._video_panel.attributes("-topmost", True)
            except Exception:
                pass
            # Never use the -fullscreen attribute: it fights the manual
            # geometry on multi-monitor setups (window ends up between two
            # monitors). Frameless + topmost + exact monitor rect IS
            # fullscreen and its placement is deterministic.
            try:
                self._video_panel.attributes("-fullscreen", False)
            except Exception:
                pass
            # Detach from the main window: a transient fullscreen window stays
            # clipped/minimized with its master on Windows.
            try:
                self._video_panel.tk.call("wm", "transient",
                                          str(self._video_panel), "")
            except Exception:
                pass
            # Video fills ITS monitor (never between two monitors).
            _mx, _my, _mw, _mh = self._video_monitor_rect()
            try:
                self._video_panel.geometry(f"{int(_mw)}x{int(_mh)}+{int(_mx)}+{int(_my)}")
            except Exception:
                pass
            # Verify placement: overrideredirect windows sometimes keep the
            # old position on the first request -> re-apply until it sticks.
            try:
                for _ in range(3):
                    try:
                        self._video_panel.update_idletasks()
                        _gx, _gy = int(self._video_panel.winfo_x()), int(self._video_panel.winfo_y())
                    except Exception:
                        break
                    if (_gx, _gy) == (int(_mx), int(_my)):
                        break
                    try:
                        self._video_panel.geometry(f"{int(_mw)}x{int(_mh)}+{int(_mx)}+{int(_my)}")
                    except Exception:
                        break
            except Exception:
                pass
            try:
                self._video_panel.lift()
            except Exception:
                pass
            try:
                self.status.configure(text="Video fullscreen (Esc / double-click to exit, overlay has ⚙︎/▣)")
            except Exception:
                pass
            # Overlay controls (YouTube style): show on motion, auto-hide.
            try:
                self._video_fs_show_controls()
            except Exception:
                pass
            try:
                self._video_panel.bind("<Motion>", lambda e: self._video_fs_show_controls(), add="+")
            except Exception:
                pass
            # Bind Escape + double-click to exit fullscreen (on the window and
            # on the children that usually have the focus).
            try:
                self._video_panel.bind("<Escape>", lambda e: self._exit_video_fullscreen(), add="+")
            except Exception:
                pass
            for _w in (getattr(self, "_video_label", None),
                       getattr(self, "_video_bar", None),
                       getattr(self, "_video_title", None)):
                try:
                    if _w is not None:
                        _w.bind("<Escape>", lambda e: self._exit_video_fullscreen(), add="+")
                except Exception:
                    pass
            try:
                self._video_panel.focus_force()
            except Exception:
                try:
                    self._video_panel.focus_set()
                except Exception:
                    pass
            # Same song keeps playing: just re-stretch the frame once the
            # fullscreen geometry has settled (no re-stream needed).
            try:
                self.root.after(150, self._video_restretch)
            except Exception:
                pass
        except Exception:
            pass

    def _video_fs_show_controls(self) -> None:
        """Floating overlay controls in fullscreen: ALWAYS visible.

        Both modes must have controls, so unlike YouTube this bar never
        auto-hides (the auto-hide is what made fullscreen feel "broken").
        """
        try:
            if not getattr(self, "_video_fullscreen", False):
                return
            win = getattr(self, "_video_panel", None)
            if win is None:
                return
            ctl = getattr(self, "_video_fs_ctl", None)
            try:
                if ctl is not None:
                    ctl.winfo_exists()
                else:
                    ctl = None
            except Exception:
                ctl = None
            if ctl is None:
                try:
                    bg, fg = self._video_bar_colors()
                except Exception:
                    bg, fg = "#222222", "#ffffff"
                ctl = tk.Frame(win, bg=bg)
                try:
                    b_exit = tk.Button(ctl, text="▣ Exit fullscreen", command=self._exit_video_fullscreen,
                                       bg=bg, fg=fg, activebackground=bg, relief="flat", bd=0)
                    b_exit.pack(side="right", padx=4, pady=4)
                    b_res = tk.Button(ctl, text="⚙︎ Resolution", command=self._open_video_res_menu,
                                      bg=bg, fg=fg, activebackground=bg, relief="flat", bd=0)
                    b_res.pack(side="right", padx=4, pady=4)
                    try:
                        _cur = getattr(getattr(self, "player", None), "current", None) or {}
                    except Exception:
                        _cur = {}
                    ttl = str(_cur.get("title", "") or "")[:40]
                    tk.Label(ctl, text=f"▶ {ttl}" if ttl else "▶ Video",
                             bg=bg, fg=fg, font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
                except Exception:
                    pass
                try:
                    ctl.bind("<Double-Button-1>", lambda e: self._exit_video_fullscreen(), add="+")
                except Exception:
                    pass
                self._video_fs_ctl = ctl
            try:
                ctl.place(relx=0.5, rely=1.0, anchor="s", relwidth=1.0)
                ctl.lift()
            except Exception:
                pass
        except Exception:
            pass

    def _video_fs_hide_controls(self) -> None:
        try:
            ctl = getattr(self, "_video_fs_ctl", None)
            if ctl is not None:
                ctl.place_forget()
        except Exception:
            pass
        try:
            self._video_fs_after = None
        except Exception:
            pass

    def _exit_video_fullscreen(self) -> None:
        """Exit video fullscreen: restore video panel position and show stickers."""
        try:
            if not getattr(self, "_video_fullscreen", False):
                return
            self._video_fullscreen = False
            # Leave REAL fullscreen mode first.
            try:
                self._video_panel.attributes("-fullscreen", False)
            except Exception:
                pass
            # Stay frameless on purpose (see _enter_video_fullscreen).
            try:
                self._video_panel.overrideredirect(True)
            except Exception:
                pass
            # Restore video panel to saved position
            try:
                if getattr(self, "_video_prev_geom", None):
                    self._video_panel.geometry(str(self._video_prev_geom))
                else:
                    self._reposition_video()
            except Exception:
                try:
                    self._reposition_video()
                except Exception:
                    pass
            try:
                self._video_panel.attributes("-topmost", False)
                self._video_panel.transient(self.root)
            except Exception:
                pass
            # Hide overlay controls, show the bar + grips again.
            try:
                self._video_fs_hide_controls()
            except Exception:
                pass
            try:
                ctl = getattr(self, "_video_fs_ctl", None)
                if ctl is not None:
                    ctl.destroy()
            except Exception:
                pass
            try:
                self._video_fs_ctl = None
            except Exception:
                pass
            # Restore the bar FIRST in pack order (before the video label):
            # plain pack() appends it after the expanded label and it gets
            # zero space -> "controls disappear after fullscreen".
            try:
                self._video_bar.pack(fill="x", side="top",
                                     before=self._video_label)
            except Exception:
                try:
                    self._video_bar.pack(fill="x", side="top")
                except Exception:
                    pass
            for _g in list(getattr(self, "_video_grips", []) or []):
                try:
                    if isinstance(_g, (tuple, list)) and len(_g) >= 3:
                        _g[1].place(**dict(_g[2]))
                    else:
                        (_g[1] if isinstance(_g, (tuple, list)) else _g).place(
                            relx=1.0, rely=1.0, anchor="se")
                except Exception:
                    pass
            # Show stickers again
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    st.get("win").deiconify()
                except Exception:
                    pass
            try:
                self.status.configure(text="Video fullscreen exited")
            except Exception:
                pass
            try:
                self._video_panel.unbind("<Escape>")
            except Exception:
                pass
            # Same song keeps playing: re-stretch the frame once the windowed
            # geometry is back (no re-stream needed).
            try:
                self.root.after(150, self._video_restretch)
            except Exception:
                pass
            try:
                self._stack_overlay_order()
            except Exception:
                pass
        except Exception:
            pass

    def _bind_video_drag(self, *widgets) -> None:
        # Free dragging across the screen (may leave the window); on release
        # relative dx/dy to the main window are saved.
        st = {"x": 0, "y": 0, "ox": 0, "oy": 0}
        def _press(e):
            try:
                st["x"], st["y"] = e.x_root, e.y_root
                st["ox"] = e.x_root - self._video_panel.winfo_x()
                st["oy"] = e.y_root - self._video_panel.winfo_y()
            except Exception:
                pass
        def _move(e):
            try:
                nx, ny = e.x_root - st["ox"], e.y_root - st["oy"]
                self._video_panel.geometry(f"+{int(nx)}+{int(ny)}")
            except Exception:
                pass
        def _rel(e):
            try:
                rx, ry = self.root.winfo_x(), self.root.winfo_y()
                self.theme.set(int(self._video_panel.winfo_x() - rx), "video_panel", "dx")
                self.theme.set(int(self._video_panel.winfo_y() - ry), "video_panel", "dy")
            except Exception:
                pass
        for w in widgets:
            try:
                w.bind("<ButtonPress-1>", _press)
                w.bind("<B1-Motion>", _move)
                w.bind("<ButtonRelease-1>", _rel)
            except Exception:
                pass

    def _bind_video_zones(self, win, pnl, bar, ttl, lbl) -> None:
        """Drag (bar) + resize (any border zone) without overlay widgets.

        The click POSITION decides: within 8px of a border/corner resizes,
        anywhere else on the bar/title drags the window. Buttons keep their
        own clicks (widget bindings do not fire on Button children), so the
        ⚙︎/▣/– controls are never covered and never hidden.
        """
        st: dict = {"action": "", "mode": "", "x": 0, "y": 0,
                    "gx": 0, "gy": 0, "gw": 0, "gh": 0, "ox": 0, "oy": 0,
                    "hover": ""}
        _M = 8
        _CURSORS = {"nw": "size_nw_se", "se": "size_nw_se",
                    "ne": "size_ne_sw", "sw": "size_ne_sw",
                    "n": "size_ns", "s": "size_ns",
                    "w": "size_we", "e": "size_we", "": ""}

        def _zone(e) -> str:
            try:
                wx, wy = win.winfo_x(), win.winfo_y()
                ww, wh = max(1, win.winfo_width()), max(1, win.winfo_height())
                lx, ly = e.x_root - wx, e.y_root - wy
            except Exception:
                return ""
            v = "n" if ly < _M else ("s" if ly > wh - _M else "")
            h = "w" if lx < _M else ("e" if lx > ww - _M else "")
            return v + h

        def _press(e):
            try:
                if getattr(self, "_video_fullscreen", False):
                    return
                mode = _zone(e)
                if mode:
                    st["action"], st["mode"] = "resize", mode
                    st["x"], st["y"] = e.x_root, e.y_root
                    st["gx"], st["gy"] = win.winfo_x(), win.winfo_y()
                    st["gw"], st["gh"] = win.winfo_width(), win.winfo_height()
                    return
                if getattr(e, "widget", None) in (bar, ttl):
                    st["action"], st["mode"] = "drag", ""
                    st["x"], st["y"] = e.x_root, e.y_root
                    try:
                        st["ox"] = e.x_root - win.winfo_x()
                        st["oy"] = e.y_root - win.winfo_y()
                    except Exception:
                        pass
            except Exception:
                pass

        def _move(e):
            try:
                if getattr(self, "_video_fullscreen", False):
                    return
                if st.get("action") == "drag":
                    win.geometry(f"+{int(e.x_root - st['ox'])}+{int(e.y_root - st['oy'])}")
                    return
                if st.get("action") != "resize":
                    return
                mode = str(st.get("mode", "") or "")
                dx = e.x_root - st["x"]
                dy = e.y_root - st["y"]
                nx, ny, nw, nh = st["gx"], st["gy"], st["gw"], st["gh"]
                if "e" in mode:
                    nw = max(160, st["gw"] + dx)
                if "s" in mode:
                    nh = max(120, st["gh"] + dy)
                if "w" in mode:
                    nw = max(160, st["gw"] - dx)
                    if nw > 160:
                        nx = st["gx"] + dx
                if "n" in mode:
                    nh = max(120, st["gh"] - dy)
                    if nh > 120:
                        ny = st["gy"] + dy
                win.geometry(f"{int(nw)}x{int(nh)}+{int(nx)}+{int(ny)}")
            except Exception:
                pass

        def _rel(e):
            try:
                action = st.get("action", "")
                st["action"], st["mode"] = "", ""
                if getattr(self, "_video_fullscreen", False):
                    return
                if action == "drag":
                    try:
                        rx, ry = self.root.winfo_x(), self.root.winfo_y()
                        self.theme.set(int(win.winfo_x() - rx), "video_panel", "dx")
                        self.theme.set(int(win.winfo_y() - ry), "video_panel", "dy")
                    except Exception:
                        pass
                elif action == "resize":
                    try:
                        self.theme.set(int(win.winfo_width()), "video_panel", "w")
                        self.theme.set(int(win.winfo_height()), "video_panel", "h")
                    except Exception:
                        pass
                    try:
                        rx, ry = self.root.winfo_x(), self.root.winfo_y()
                        self.theme.set(int(win.winfo_x() - rx), "video_panel", "dx")
                        self.theme.set(int(win.winfo_y() - ry), "video_panel", "dy")
                    except Exception:
                        pass
                    # Window size only: re-stretch, stream keeps running.
                    try:
                        self.root.after(80, self._video_restretch)
                    except Exception:
                        pass
            except Exception:
                pass

        def _hover(e):
            try:
                if getattr(self, "_video_fullscreen", False):
                    return
                cur = _CURSORS.get(_zone(e), "")
                if cur != st.get("hover", ""):
                    st["hover"] = cur
                    for _w in (win, pnl, bar, ttl, lbl):
                        try:
                            _w.configure(cursor=cur or "")
                        except Exception:
                            pass
            except Exception:
                pass

        for _w in (win, pnl, bar, ttl, lbl):
            try:
                _w.bind("<ButtonPress-1>", _press, add="+")
                _w.bind("<B1-Motion>", _move, add="+")
                _w.bind("<ButtonRelease-1>", _rel, add="+")
                _w.bind("<Motion>", _hover, add="+")
            except Exception:
                pass

    def _bind_video_resize_full(self, grips) -> None:
        """Resize the frameless video window from any corner or edge."""
        try:
            win = getattr(self, "_video_panel", None)
        except Exception:
            return
        if win is None:
            return
        st = {"mode": "", "x": 0, "y": 0, "gx": 0, "gy": 0, "gw": 0, "gh": 0}

        def _press(mode):
            def _h(e):
                try:
                    if getattr(self, "_video_fullscreen", False):
                        return
                    st["mode"] = str(mode)
                    st["x"], st["y"] = e.x_root, e.y_root
                    st["gx"], st["gy"] = win.winfo_x(), win.winfo_y()
                    st["gw"], st["gh"] = win.winfo_width(), win.winfo_height()
                except Exception:
                    pass
            return _h

        def _move(e):
            try:
                if getattr(self, "_video_fullscreen", False):
                    return
                mode = str(st.get("mode", "") or "")
                if not mode:
                    return
                dx = e.x_root - st["x"]
                dy = e.y_root - st["y"]
                nx, ny, nw, nh = st["gx"], st["gy"], st["gw"], st["gh"]
                if "e" in mode:
                    nw = max(160, st["gw"] + dx)
                if "s" in mode:
                    nh = max(120, st["gh"] + dy)
                if "w" in mode:
                    nw = max(160, st["gw"] - dx)
                    if nw > 160:
                        nx = st["gx"] + dx
                if "n" in mode:
                    nh = max(120, st["gh"] - dy)
                    if nh > 120:
                        ny = st["gy"] + dy
                win.geometry(f"{int(nw)}x{int(nh)}+{int(nx)}+{int(ny)}")
            except Exception:
                pass

        def _rel(e):
            try:
                st["mode"] = ""
                if getattr(self, "_video_fullscreen", False):
                    return
                try:
                    _nw, _nh = int(win.winfo_width()), int(win.winfo_height())
                    self.theme.set(_nw, "video_panel", "w")
                    self.theme.set(_nh, "video_panel", "h")
                except Exception:
                    pass
                try:
                    rx, ry = self.root.winfo_x(), self.root.winfo_y()
                    self.theme.set(int(win.winfo_x() - rx), "video_panel", "dx")
                    self.theme.set(int(win.winfo_y() - ry), "video_panel", "dy")
                except Exception:
                    pass
                # Window size only: the stream keeps running, the frame is
                # re-stretched to the new size (no song change, no reconnect).
                try:
                    self.root.after(80, self._video_restretch)
                except Exception:
                    pass
            except Exception:
                pass

        for _item in list(grips or []):
            try:
                if isinstance(_item, (tuple, list)) and len(_item) >= 3:
                    _mode, _g = _item[0], _item[1]
                else:
                    _mode, _g = _item
                _g.bind("<ButtonPress-1>", _press(_mode))
                _g.bind("<B1-Motion>", _move)
                _g.bind("<ButtonRelease-1>", _rel)
            except Exception:
                pass

    def _bind_video_resize(self, grip) -> None:
        st = {"x": 0, "y": 0, "w": 0, "h": 0}
        def _press(e):
            try:
                st["x"], st["y"] = e.x_root, e.y_root
                st["w"], st["h"] = self._video_panel.winfo_width(), self._video_panel.winfo_height()
            except Exception:
                pass
        def _move(e):
            try:
                nw = max(160, st["w"] + (e.x_root - st["x"]))
                nh = max(120, st["h"] + (e.y_root - st["y"]))
                self._video_panel.geometry(f"{int(nw)}x{int(nh)}")
            except Exception:
                pass
        def _rel(e):
            try:
                self.theme.set(int(self._video_panel.winfo_width()), "video_panel", "w")
                self.theme.set(int(self._video_panel.winfo_height()), "video_panel", "h")
                # Force restart at the NEW size so the video keeps scaling
                # with the window (before it froze at the old size).
                try:
                    self._video_video_id = ""
                except Exception:
                    pass
                self._refresh_video_panel(force=True)
            except Exception:
                pass
        try:
            grip.bind("<ButtonPress-1>", _press)
            grip.bind("<B1-Motion>", _move)
            grip.bind("<ButtonRelease-1>", _rel)
        except Exception:
            pass

    def _video_res(self) -> tuple[int, int]:
        """Video RESOLUTION (internal ffmpeg pixels).

        Independent from the window size: the frame is ALWAYS stretched to
        fill the whole video window at display time. Changing this never
        resizes the window (corners/edges do that).
        """
        try:
            d = self.theme.data.get("video_panel", {}) or {}
            rw = int(d.get("res_w", 0) or 0)
            rh = int(d.get("res_h", 0) or 0)
            if rw >= 160 and rh >= 120:
                return max(160, min(3840, rw)), max(120, min(2160, rh))
        except Exception:
            pass
        try:
            w = int(self.theme.get("video_panel", "w", default=640) or 640)
            h = int(self.theme.get("video_panel", "h", default=360) or 360)
            return max(160, min(3840, w)), max(120, min(2160, h))
        except Exception:
            return 640, 360

    def _video_monitor_rect(self) -> tuple[int, int, int, int]:
        """Monitor holding the video panel: (x, y, w, h).

        winfo_screenwidth spans ALL monitors (virtual desktop): using it
        centers the window between two monitors. The Win32 monitor API pins
        fullscreen to the right screen.
        """
        try:
            win = getattr(self, "_video_panel", None)
            if win is not None:
                cx = int(win.winfo_x() + max(1, win.winfo_width()) // 2)
                cy = int(win.winfo_y() + max(1, win.winfo_height()) // 2)
            else:
                cx = int(self.root.winfo_x() + 100)
                cy = int(self.root.winfo_y() + 100)
        except Exception:
            cx, cy = 100, 100
        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes
                try:
                    hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
                except Exception:
                    hwnd = None
                if hwnd:
                    hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)
                    if hmon:
                        class _MI(ctypes.Structure):
                            _fields_ = [("cbSize", ctypes.c_ulong),
                                        ("rcMonitor", wintypes.RECT),
                                        ("rcWork", wintypes.RECT),
                                        ("dwFlags", ctypes.c_ulong)]
                        mi = _MI()
                        mi.cbSize = ctypes.sizeof(_MI)
                        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                            r = mi.rcMonitor
                            return (int(r.left), int(r.top),
                                    int(r.right - r.left), int(r.bottom - r.top))
            except Exception:
                pass
            # Fallback: monitor containing the point via Tk (single monitor ok).
            try:
                return (0, 0, int(self.root.winfo_screenwidth() or 1920),
                        int(self.root.winfo_screenheight() or 1080))
            except Exception:
                pass
        else:
            try:
                return (0, 0, int(self.root.winfo_screenwidth() or 1920),
                        int(self.root.winfo_screenheight() or 1080))
            except Exception:
                pass
        return (0, 0, 1920, 1080)

    def _video_target_size(self) -> tuple[int, int]:
        """Target video pixels: fullscreen = screen, windowed = label/theme size."""
        try:
            if getattr(self, "_video_fullscreen", False):
                sw = int(self.root.winfo_screenwidth() or 1920)
                sh = int(self.root.winfo_screenheight() or 1080)
                return max(160, min(1920, sw)), max(120, min(1080, sh))
        except Exception:
            pass
        try:
            pw = int(self._video_label.winfo_width() or 0)
            ph = int(self._video_label.winfo_height() or 0)
            if pw >= 160 and ph >= 120:
                return max(160, min(1920, pw)), max(120, min(1080, ph))
        except Exception:
            pass
        try:
            w = int(self.theme.get("video_panel", "w", default=320) or 320)
            h = int(self.theme.get("video_panel", "h", default=180) or 180)
            return max(160, min(1920, w)), max(120, min(1080, h))
        except Exception:
            return 320, 180

    def _refresh_video_panel(self, force: bool = False,
                               pw: int | None = None, ph: int | None = None) -> None:
        """Show playing video or cover. Non-blocking. Same song is kept.

        The worker renders at the video RESOLUTION (explicit pw/ph or the
        theme res_w/res_h): the window size never matters here because every
        frame is stretched to fill the whole window at display time.
        """
        try:
            self._ensure_video_panel()
        except Exception:
            return
        try:
            if not bool(self.theme.get("video_panel", "visible", default=True)):
                return
        except Exception:
            pass
        track = getattr(self.player, "current", None) or {}
        vid = str((track or {}).get("videoId", "") or "")
        if not vid:
            try:
                self._video_label.configure(image="", text="♪ Nothing playing")
            except Exception:
                pass
            return
        # Resolution: explicit when given, else the theme video resolution.
        # (Window size is irrelevant: frames stretch to fill it on display.)
        try:
            if pw is not None and ph is not None:
                _pw, _ph = (max(160, min(3840, int(pw))),
                            max(120, min(2160, int(ph))))
            else:
                _pw, _ph = self._video_res()
        except Exception:
            _pw, _ph = 640, 360
        try:
            _opw = int(getattr(self, "_video_pw", 0) or 0)
            _oph = int(getattr(self, "_video_ph", 0) or 0)
        except Exception:
            _opw, _oph = 0, 0
        _res_changed = (_pw != _opw) or (_ph != _oph)
        if (vid == getattr(self, "_video_video_id", "")
                and getattr(self, "_video_running", False)
                and not force and not _res_changed):
            return  # already playing this video at this resolution
        if _res_changed or force:
            try:
                self._video_video_id = ""
            except Exception:
                pass
        self._video_video_id = vid
        try:
            self._video_pw, self._video_ph = int(_pw), int(_ph)
        except Exception:
            pass
        try:
            _ed0 = self._meta_edited(track)
            ttl = str(_ed0.get("track") or (track or {}).get("title", "") or "")[:40]
            base = f"▶ {ttl}" if ttl else "▶ Video / Cover"
            try:
                _rw0, _rh0 = int(_pw), int(_ph)
                base = f"{base} [{_rw0}x{_rh0}]"
            except Exception:
                pass
            self._video_title.configure(text=base)
        except Exception:
            pass
        # Stop the previous thread and launch a new one (instant cover + video try)
        try:
            self._video_running = False
        except Exception:
            pass
        threading.Thread(target=self._video_worker, args=(vid, dict(track or {}), _pw, _ph), daemon=True).start()
        # HD ramp (YouTube style): playback starts instantly on the fast
        # source; if it is below the request, upgrade the table in the
        # background and hot-switch the stream at the same audio position.
        try:
            if int(_ph) >= 720:
                threading.Thread(target=self._hd_ramp_bg,
                                 args=(vid, int(_pw), int(_ph)),
                                 daemon=True).start()
        except Exception:
            pass
        # Fixed-rate display loop (single instance; self re-armed).
        try:
            if not getattr(self, "_video_tick_on", False):
                self._video_tick_on = True
                self.root.after(50, self._video_display_tick)
        except Exception:
            pass

    def _hd_ramp_bg(self, vid: str, pw: int, ph: int) -> None:
        """Background HD upgrade: if the playing source is below the request,
        fetch the rich table and hot-switch (same song, same audio position).
        Matched by (vid, asked height): a newer resolution click or song
        change makes this ramp stale and it aborts silently."""
        try:
            import time as _t
            src = None
            for _ in range(120):
                try:
                    s = getattr(self, "_video_src", None) or {}
                except Exception:
                    s = {}
                if (s.get("vid") == vid and int(s.get("asked", 0) or 0) == int(ph)):
                    src = s
                    break
                _t.sleep(0.1)
            if not src:
                return
            try:
                src_h = int(src.get("h") or 0)
            except Exception:
                src_h = 0
            if src_h >= int(ph) - 100:
                return  # already at (or above) the request
            try:
                up = self.client.upgrade_video_info(vid, int(ph)) or {}
            except Exception:
                up = {}
            try:
                new_h = int(up.get("height") or 0)
            except Exception:
                new_h = 0
            if new_h <= max(src_h, 0):
                return  # upgrade found nothing better
            # Still the same song asking the same resolution?
            try:
                cur = getattr(getattr(self, "player", None), "current", None) or {}
                if str(cur.get("videoId", "") or "") != str(vid):
                    return
                s2 = getattr(self, "_video_src", None) or {}
                if s2.get("vid") != vid or int(s2.get("asked", 0) or 0) != int(ph):
                    return
                _rw, _rh = self._video_res()
                if int(_rh) != int(ph):
                    return
            except Exception:
                return
            try:
                self._call_ui(self.status.configure,
                              text=f"Video upgraded to {new_h}p ✔")
            except Exception:
                pass
            try:
                self._video_video_id = ""
            except Exception:
                pass
            try:
                self._call_ui(self._refresh_video_panel, True, int(pw), int(ph))
            except Exception:
                pass
        except Exception:
            pass

    def _video_fps(self) -> int:
        """Mini-video FPS, configurable (Customize > Video). 1-60."""
        try:
            return max(1, min(60, int(self.theme.get("video_panel", "fps", default=15) or 15)))
        except Exception:
            return 15

    def _video_worker(self, vid: str, track: dict, pw: int = 320, ph: int = 180) -> None:
        gen = int(getattr(self, "_video_gen", 0) or 0) + 1
        self._video_gen = gen
        self._video_running = True
        try:
            self._video_latest = None
            self._video_shown = None
        except Exception:
            pass
        try:
            import time as _tt
            self._video_last_frame = _tt.time()
        except Exception:
            pass
        # 1) Instant cover (hq) to avoid black
        try:
            thumb = track.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            self._show_video_cover(thumb, pw, ph)
        except Exception:
            pass
        # 2) Real video via direct ffmpeg (imageio.get_reader on googlevideo URLs
        #    stuck at 1 frame: with no reconnect or scaling it lagged
        #    or died silently). Here we pipe 320x180 rawvideo at the configured FPS
        #    (Customize > Video), like streaming audio:
        #    with reconnect and timeout.
        vurl = ""
        try:
            try:
                _want_h = int(OH)
            except Exception:
                _want_h = 360
            info = self.client.get_video_info(vid, prefer_height=_want_h)
            vurl = (info or {}).get("video_url", "")
            try:
                self._video_src = {"gen": gen, "vid": vid,
                                   "h": int((info or {}).get("height") or 0),
                                   "asked": int(_want_h)}
            except Exception:
                pass
        except Exception:
            vurl = ""
        if not vurl:
            return
        # --- shielding: kill old ffmpegs (otherwise blocking reads leave them
        # hanging, processes pile up + the panel freezes) ---
        try:
            self._kill_video_procs(except_gen=gen)
        except Exception:
            pass
        try:
            import subprocess as _sp
            try:
                import imageio_ffmpeg as _iff
                exe = _iff.get_ffmpeg_exe()
            except Exception:
                exe = None
            if not exe:
                return
            from PIL import Image
            import time as _t
            fps = self._video_fps()
            # Scale INSIDE ffmpeg to panel size (even, up to 1080p): no
            # PIL resize per frame in the worker and PhotoImage comes out
            # at final size, so the video keeps scaling with the window.
            try:
                OW = max(160, min(3840, int(pw)))
                OH = max(120, min(2160, int(ph)))
                OW -= OW % 2
                OH -= OH % 2
            except Exception:
                OW, OH = 320, 180
            frame_sz = OW * OH * 3
            _nowin = getattr(_sp, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0

            def _spawn(skip: float = 0.0):
                cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin",
                       "-thread_queue_size", "512"]
                # Reconnect flags are HTTP-demuxer options: for file/pipe
                # inputs ffmpeg aborts with "Option reconnect not found" and
                # the panel goes black/cover-only. Only add them for http(s).
                try:
                    _is_http = str(vurl or "").lower().startswith(("http://", "https://"))
                except Exception:
                    _is_http = False
                if _is_http:
                    cmd += ["-reconnect", "1", "-reconnect_streamed", "1",
                            "-reconnect_delay_max", "5"]
                if skip > 0.5:
                    cmd += ["-ss", f"{skip:.1f}"]
                cmd += ["-i", vurl,
                        "-an", "-vf", f"scale={OW}:{OH}", "-r", str(fps),
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
                try:
                    p = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.DEVNULL,
                                   creationflags=_nowin)
                except Exception:
                    return None
                try:
                    procs = getattr(self, "_video_procs", None)
                    if procs is None:
                        procs = {}
                        self._video_procs = procs
                    procs[gen] = p
                except Exception:
                    pass
                return p

            def _drop(p):
                try:
                    procs = getattr(self, "_video_procs", None) or {}
                    if procs.get(gen) is p:
                        procs.pop(gen, None)
                except Exception:
                    pass
                try:
                    if p is not None:
                        try:
                            p.kill()
                        except Exception:
                            pass
                        try:
                            p.wait(timeout=3)
                        except Exception:
                            pass
                except Exception:
                    pass

            alive = lambda: (self._video_running
                             and self._video_video_id == vid
                             and gen == getattr(self, "_video_gen", 0))
            try:
                if bool(self.theme.get("video_panel", "visible", default=True)) is False:
                    return
            except Exception:
                pass
            # LOOP + SYNC with audio:
            # - Video starts at -ss = audio position (not from 0),
            #   so it is not offset when audio is already seconds in.
            # - If the video ends before audio does (shorter video), it
            #   repeats in LOOP from the audio position (real loop).
            # - Drift correction: the master clock is the AUDIO
            #   (player.get_position()). If video lags >1.5s behind,
            #   frames are skipped; if ahead, it waits.
            # - Seek: if audio jumps (>2.5s), ffmpeg relaunches with -ss.
            try:
                _vdur = 0
                try:
                    _vdur = int((info or {}).get("duration_sec") or 0)
                except Exception:
                    _vdur = 0
            except Exception:
                _vdur = 0
            got_any = False
            attempt = 0
            # Start at the REAL audio position (synchronized from the
            # first frame, not from 0).
            try:
                _init_skip = max(0.0, float(self.player.get_position() or 0.0))
            except Exception:
                _init_skip = 0.0
            # Outer loop: retries + video loop while the song
            # keeps playing (before: 4 tries then frozen on EOF).
            while alive() and attempt < 12:
                try:
                    start_pos = max(0.0, float(self.player.get_position() or 0.0))
                except Exception:
                    start_pos = 0.0
                if attempt == 0 and _init_skip > 0.5:
                    start_pos = _init_skip
                if attempt > 0:
                    try:
                        # Natural loop: resume from audio (modulo when
                        # we know the video length to stay in range).
                        if _vdur > 0 and start_pos >= _vdur:
                            try:
                                start_pos = float(start_pos % max(1, _vdur))
                            except Exception:
                                pass
                        _t.sleep(0.6)
                    except Exception:
                        pass
                    if not alive():
                        break
                    # Fresh URL (googlevideo ones expire) + audio position.
                    # Same render height: do not downgrade the stream mid-song.
                    try:
                        try:
                            _want_h2 = int(OH)
                        except Exception:
                            _want_h2 = 360
                        fresh = self.client.get_video_info(vid, prefer_height=_want_h2) or {}
                        if fresh.get("video_url"):
                            vurl = fresh["video_url"]
                            try:
                                _vdur = int(fresh.get("duration_sec") or _vdur or 0)
                            except Exception:
                                pass
                    except Exception:
                        pass
                # -ss BEFORE -i = fast seek; with stream=True for looping
                proc = _spawn(skip=start_pos)
                if proc is None:
                    attempt += 1
                    continue
                t_end = _t.time() + 10
                got_first = False
                ended_ok = False
                # This segment clock: frames read and base audio position
                try:
                    seg_audio_base = float(start_pos)
                except Exception:
                    seg_audio_base = 0.0
                seg_frames = 0
                last_audio = seg_audio_base
                last_sync_check = _t.time()
                while alive():
                    try:
                        if not bool(self.theme.get("video_panel", "visible", default=True)):
                            break
                    except Exception:
                        pass
                    # Pause with the player: do not consume frames (ffmpeg stalls
                    # only when the pipe fills up) to avoid desync.
                    try:
                        if getattr(getattr(self, "player", None), "state", "") == "paused":
                            _t.sleep(0.2)
                            continue
                    except Exception:
                        pass
                    # SEEK detection roughly every 0.5s: if audio jumped, relaunch
                    try:
                        _now_c = _t.time()
                        if _now_c - last_sync_check > 0.5:
                            last_sync_check = _now_c
                            try:
                                _apos = float(self.player.get_position() or 0.0)
                            except Exception:
                                _apos = last_audio
                            # Expected when all is linear: base + frames/fps
                            try:
                                _expected = seg_audio_base + (seg_frames / max(1, fps))
                            except Exception:
                                _expected = _apos
                            if abs(_apos - _expected) > 2.5:
                                # Manual seek or big jump: exit and relaunch with -ss
                                try:
                                    _init_skip = _apos
                                except Exception:
                                    pass
                                break
                            last_audio = _apos
                    except Exception:
                        pass
                    try:
                        raw = proc.stdout.read(frame_sz) if proc and proc.stdout else b""
                    except Exception:
                        break
                    if not raw or len(raw) < frame_sz:
                        # Fin natural (rc 0) o caida/URL muerta.
                        try:
                            rc = proc.poll()
                        except Exception:
                            rc = -1
                        if rc == 0:
                            ended_ok = True
                            break
                        if not got_first:
                            # Starting up or dead URL: wait until t_end.
                            if (rc is not None and rc != 0) or _t.time() > t_end:
                                break
                            try:
                                _t.sleep(0.05)
                            except Exception:
                                pass
                            continue
                        # Premature EOF with frames already seen -> retry with -ss.
                        break
                    got_first = True
                    got_any = True
                    seg_frames += 1
                    # Drift correction: compare video vs audio.
                    # Video is behind -> skip (do not paint this frame).
                    try:
                        _apos2 = float(self.player.get_position() or 0.0)
                    except Exception:
                        _apos2 = seg_audio_base + seg_frames / max(1, fps)
                    try:
                        _vtime = seg_audio_base + (seg_frames / max(1, fps))
                        _drift = _vtime - _apos2  # >0 video ahead, <0 behind
                        if _drift < -1.5:
                            # Way behind: drop frames to catch up
                            # (skip painting this one and keep reading fast)
                            try:
                                _skip_n = min(30, int(abs(_drift) * fps))
                            except Exception:
                                _skip_n = 0
                            # Consume without painting: already consumed 1, drop more
                            try:
                                for _ in range(max(0, _skip_n - 1)):
                                    try:
                                        _extra = proc.stdout.read(frame_sz) if proc and proc.stdout else b""
                                        if not _extra or len(_extra) < frame_sz:
                                            break
                                        seg_frames += 1
                                    except Exception:
                                        break
                            except Exception:
                                pass
                            continue
                        if _drift > 1.5:
                            # Ahead: wait for audio to catch up
                            try:
                                _t.sleep(min(1.0, _drift / 2.0))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        # Already at panel size from ffmpeg: no resize.
                        # Stored as the LAST frame and painted by the tick at
                        # a fixed rate (so no bursts or lag
                        # buildup: old frames are overwritten, never queued).
                        self._video_latest = (gen, Image.frombytes("RGB", (OW, OH), raw))
                    except Exception:
                        pass
                    # REAL pacing (configurable in Customize > Video): without it
                    # ffmpeg delivers everything at once through the pipe, the UI shows it at
                    # 500fps and the video "ends in seconds" with stuttery lag.
                    # Fixed 1/fps sleep: if the UI is slow the pipe fills and ffmpeg
                    # it stalls on its own (no accumulated debt).
                    try:
                        _t.sleep(1.0 / max(1, fps))
                    except Exception:
                        pass
                _drop(proc)
                proc = None
                if not alive():
                    break
                if not got_first:
                    # Dead URL in this segment.
                    # If there was video before, retry with -ss; if there never
                    # was any, stick with the cover.
                    if got_any:
                        attempt += 1
                        continue
                    break
                if ended_ok:
                    # NATURAL video end -> LOOP while audio continues.
                    try:
                        _ap = float(self.player.get_position() or 0.0)
                        _ad = float(getattr(self.player, "duration_sec", 0) or 0)
                    except Exception:
                        _ap, _ad = 0.0, 0.0
                    # If audio ended (or nearly), do not loop: the song
                    # switches on its own via the player and the worker renews.
                    try:
                        _same_track = (
                            getattr(getattr(self, "player", None), "current", None) or {}).get("videoId", "") == vid
                    except Exception:
                        _same_track = True
                    if _same_track and _ad > 0 and _ap < max(0.0, _ad - 2.0):
                        attempt += 1
                        continue  # loop: relaunch from audio position
                    break
                # Mid-stream drop -> retry with -ss (up to 12 segments)
                attempt += 1
                continue
        except Exception:
            pass
        finally:
            try:
                # With no frames and still on this song: note in the title
                # that the cover is showing (the title rewrites on theme change).
                if not got_any:
                    try:
                        alive_now = (self._video_running
                                     and self._video_video_id == vid
                                     and gen == getattr(self, "_video_gen", 0))
                    except Exception:
                        alive_now = False
                    if alive_now:
                        try:
                            self._call_ui(self._video_note, "portada")
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                self._kill_video_proc(gen)
            except Exception:
                pass

    def _kill_video_proc(self, gen) -> None:
        """Kill ONLY this generation's ffmpeg.

        The old blanket kill in `finally` murdered newer workers spawned by a
        resolution switch (their first proc died -> cover only -> "res no
        cambia"). New workers kill the OLD ones at start; the dying one must
        only bury its own.
        """
        try:
            procs = getattr(self, "_video_procs", None) or {}
            p = procs.pop(gen, None)
        except Exception:
            p = None
        try:
            if p is not None:
                try:
                    p.kill()
                except Exception:
                    pass
                try:
                    p.wait(timeout=3)
                except Exception:
                    pass
        except Exception:
            pass

    def _kill_video_procs(self, except_gen=None) -> None:
        """Kill mini-video ffmpegs (all, or all but one gen)."""
        try:
            procs = getattr(self, "_video_procs", None) or {}
            for g, p in list(procs.items()):
                if except_gen is not None and g == except_gen:
                    continue
                try:
                    procs.pop(g, None)
                except Exception:
                    pass
                try:
                    if p is not None:
                        try:
                            p.kill()
                        except Exception:
                            pass
                        try:
                            p.wait(timeout=3)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def _paint_video_frame(self, photo) -> None:
        try:
            if self._video_label is not None:
                self._video_label.configure(image=photo, text="")
        except Exception:
            pass

    def _video_display_tick(self) -> None:
        """Paint the LAST available frame at a fixed rate (1000/fps).

        Decouple network from screen: even if ffmpeg delivers in bursts, what
        shows advances at a steady rate without judder (in-between frames are
        dropped, never queued)."""
        try:
            if getattr(self, "_closed", False):
                try:
                    self._video_tick_on = False
                except Exception:
                    pass
                return
            try:
                gen = getattr(self, "_video_gen", 0)
                if (gen
                        and getattr(self, "_video_running", False)
                        and getattr(self, "_video_video_id", "")
                        and bool(self.theme.get("video_panel", "visible", default=True))
                        and getattr(getattr(self, "player", None), "state", "") == "playing"):
                    latest = getattr(self, "_video_latest", None)
                    if (latest is not None and latest[0] == gen
                            and latest is not getattr(self, "_video_shown", None)):
                        self._video_shown = latest
                        try:
                            self._paint_video_frame_img(latest[1])
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass
        try:
            fps = self._video_fps()
            self.root.after(max(10, int(1000 / max(1, fps))), self._video_display_tick)
        except Exception:
            try:
                self._video_tick_on = False
            except Exception:
                pass

    def _paint_video_frame_img(self, img) -> None:
        """Paint a frame stretched to fill the WHOLE video window (UI THREAD)."""
        try:
            import time as _t
            try:
                self._video_last_frame = _t.time()
            except Exception:
                pass
            try:
                self._video_last_pil = img
            except Exception:
                pass
            # ALWAYS stretch to the window (resolution and window size are
            # independent: a 240p stream fills a 1080p window and vice versa).
            try:
                lw = int(self._video_label.winfo_width() or 0)
                lh = int(self._video_label.winfo_height() or 0)
                iw, ih = int(img.width), int(img.height)
            except Exception:
                lw, lh, iw, ih = 0, 0, 0, 0
            if (lw >= 160 and lh >= 120 and iw > 0 and ih > 0
                    and (lw != iw or lh != ih)):
                try:
                    from PIL import Image as _I
                    img = img.resize((lw, lh), _I.BILINEAR)
                except Exception:
                    pass
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)
            self._video_photo = photo
            if self._video_label is not None:
                self._video_label.configure(image=photo, text="")
        except Exception:
            pass

    def _video_restretch(self) -> None:
        """Repaint the last frame at the current window size (no re-stream)."""
        try:
            img = getattr(self, "_video_last_pil", None)
            if img is None or getattr(self, "_video_label", None) is None:
                return
            self._paint_video_frame_img(img)
        except Exception:
            pass

    def _video_osd(self, text: str, ms: int = 1200) -> None:
        """Big centered flash over the video (e.g. '720p'): proof the res changed."""
        try:
            pnl = getattr(self, "_video_pnl", None)
            if pnl is None:
                return
            try:
                old = getattr(self, "_video_osd_lbl", None)
                if old is not None:
                    old.destroy()
            except Exception:
                pass
            lbl = tk.Label(pnl, text=str(text or ""), bg="black", fg="white",
                           font=("Segoe UI", 22, "bold"))
            try:
                lbl.place(relx=0.5, rely=0.5, anchor="center")
            except Exception:
                return
            self._video_osd_lbl = lbl
            try:
                pnl.after(max(400, int(ms or 1200)), self._video_osd_clear)
            except Exception:
                pass
        except Exception:
            pass

    def _video_osd_clear(self) -> None:
        try:
            old = getattr(self, "_video_osd_lbl", None)
            if old is not None:
                old.destroy()
        except Exception:
            pass
        try:
            self._video_osd_lbl = None
        except Exception:
            pass

    def _video_note(self, kind: str) -> None:
        """Status suffix in the panel title (cover when there is no video)."""
        try:
            if getattr(self, "_video_title", None) is None:
                return
            cur = str(self._video_title.cget("text") or "")
            base = cur.split(" (cover)")[0]
            if kind == "portada" and "(cover)" not in cur:
                self._video_title.configure(text=(base + " (cover)" if base else "▶ Cover"))
        except Exception:
            pass

    def _show_video_cover(self, url: str, pw: int = 320, ph: int = 180) -> None:
        def _bg():
            try:
                import requests
                from PIL import Image, ImageOps
                from io import BytesIO as _B
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                img = Image.open(_B(r.content)).convert("RGB")
                # pw/ph come from the UI thread (do not touch Tk here).
                # Cover stretched to the video resolution (display stretches
                # it again to the window, like every frame).
                try:
                    tw, th = max(160, int(pw)), max(120, int(ph))
                    img = img.resize((tw, th), Image.BILINEAR)
                except Exception:
                    img = img.resize((max(160, int(pw)), max(120, int(ph))))
                self._call_ui(self._paint_video_frame_img, img)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    # ---------- stickers / floating images ----------
    def _restore_stickers(self) -> None:
        # Destroy stickers from the PREVIOUS theme so none remain when
        # switching themes (stickers belong to the theme, not to the app).
        try:
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    st.get("win").destroy()
                except Exception:
                    pass
        except Exception:
            pass
        self._stickers = []
        try:
            cfgs = self.theme.data.get("stickers", []) or []
        except Exception:
            cfgs = []
        for cfg in list(cfgs):
            try:
                self._create_sticker(dict(cfg), save=False)
            except Exception:
                pass
        # Follow the main window when moved/resized.
        # Use the SINGLE bind (see _ensure_root_configure_bind): do not create another
        # bind here because _draw_background used to stomp it and stickers
        # they stopped following the window.
        try:
            self._ensure_root_configure_bind()
            self._reposition_stickers()
        except Exception:
            pass

    def _on_main_configure_stickers(self, event=None) -> None:
        try:
            if event is not None and getattr(event, "widget", None) is not self.root:
                return
            self._reposition_stickers()
        except Exception:
            pass

    def _reposition_stickers(self) -> None:
        try:
            try:
                if str(self.root.state()) == "iconic":
                    return
            except Exception:
                pass
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
        except Exception:
            return
        for st in list(getattr(self, "_stickers", []) or []):
            try:
                cfg = st.get("cfg", {})
                win = st.get("win")
                if win is None:
                    continue
                win.geometry(f"+{int(rx + int(cfg.get('dx', 0)))}+{int(ry + int(cfg.get('dy', 0)))}")
            except Exception:
                pass

    def _create_sticker(self, cfg: dict, save: bool = True) -> None:
        from PIL import Image, ImageTk
        path = str(cfg.get("path", "") or "")
        if not path or not os.path.exists(path):
            return
        try:
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
        except Exception:
            rx, ry = 100, 100
        dx, dy = int(cfg.get("dx", 100)), int(cfg.get("dy", 100))
        w, h = int(cfg.get("w", 160) or 160), int(cfg.get("h", 160) or 160)
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        try:
            win.overrideredirect(True)
            win.attributes("-topmost", False)
            try:
                win.transient(self.root)
            except Exception:
                pass
            # PNG transparency: background that becomes transparent
            try:
                win.attributes("-transparentcolor", "#010101")
            except Exception:
                pass
            win.geometry(f"{w}x{h}+{rx + dx}+{ry + dy}")
        except Exception:
            pass
        lbl = tk.Label(win, bg="#010101", cursor="fleur")
        lbl.pack(fill="both", expand=True)
        st = {"win": win, "label": lbl, "cfg": cfg, "photo": None}
        try:
            img = Image.open(path).convert("RGBA")
            # #010101 background for the Windows transparency trick
            bg = Image.new("RGBA", (w, h), (1, 1, 1, 255))
            fit = img.copy()
            fit.thumbnail((w, h), Image.LANCZOS)
            bg.alpha_composite(fit, ((w - fit.width) // 2, (h - fit.height) // 2))
            # Fully transparent pixels -> opaque #010101 (invisible via -transparentcolor)
            try:
                import numpy as _np
                arr = _np.array(bg)
                mask = arr[:, :, 3] < 10
                arr[mask] = (1, 1, 1, 255)
                from PIL import Image as _I
                bg = _I.fromarray(arr)
            except Exception:
                pass
            photo = ImageTk.PhotoImage(bg)
            st["photo"] = photo
            lbl.configure(image=photo)
            # If it is a GIF, animate it (frames use the same transparency
            # transparency; on failure the first static frame stays).
            try:
                if self._is_gif(path):
                    self._start_sticker_gif(st, path, w, h)
            except Exception:
                pass
        except Exception:
            try:
                lbl.configure(text="▣")
            except Exception:
                pass
        # Dragging moves the sticker (saves dx/dy relative to the main window)
        drag = {"x": 0, "y": 0, "dx": dx, "dy": dy}
        def _press(e):
            drag["x"], drag["y"] = e.x_root, e.y_root
            try:
                rx0, ry0 = self.root.winfo_x(), self.root.winfo_y()
                drag["dx"] = win.winfo_x() - rx0
                drag["dy"] = win.winfo_y() - ry0
            except Exception:
                pass
        def _move(e):
            try:
                rx0, ry0 = self.root.winfo_x(), self.root.winfo_y()
                ndx = drag["dx"] + (e.x_root - drag["x"])
                ndy = drag["dy"] + (e.y_root - drag["y"])
                cfg["dx"], cfg["dy"] = int(ndx), int(ndy)
                win.geometry(f"+{int(rx0 + ndx)}+{int(ry0 + ndy)}")
            except Exception:
                pass
        def _rel(e):
            if save is not False:
                self._save_stickers()
            else:
                self._save_stickers()
        def _del(e=None):
            try:
                try:
                    _after = st.pop("after", None)
                    if _after is not None:
                        win.after_cancel(_after)
                except Exception:
                    pass
                win.destroy()
            except Exception:
                pass
            try:
                self._stickers = [s for s in self._stickers if s.get("win") is not win]
            except Exception:
                pass
            self._save_stickers()
        try:
            lbl.bind("<ButtonPress-1>", _press)
            lbl.bind("<B1-Motion>", _move)
            lbl.bind("<ButtonRelease-1>", _rel)
            lbl.bind("<Button-3>", _del)
            win.bind("<ButtonPress-1>", _press)
            win.bind("<B1-Motion>", _move)
            try:
                win.bind("<FocusIn>", lambda e: self._stack_overlay_order(), add="+")
            except Exception:
                pass
        except Exception:
            pass
        # Menu: right-click deletes (status notice)
        try:
            self._stickers.append(st)
        except Exception:
            pass
        if save:
            self._save_stickers()
        # Order: stickers always above video
        try:
            self._stack_overlay_order()
        except Exception:
            pass

    def _start_sticker_gif(self, st: dict, path: str, w: int, h: int) -> bool:
        """Animate a GIF sticker. UI thread (after): no threads nor PhotoImage
        outside the mainloop. Return True if started."""
        try:
            from PIL import Image, ImageTk
            win = st.get("win")
            lbl = st.get("label")
            if win is None or lbl is None:
                return False
            frames = self._load_gif_frames(path, w, h)
            if len(frames) < 2:
                return False
            try:
                import numpy as _np
                from PIL import Image as _I
                has_np = True
            except Exception:
                has_np = False
            photos = []
            for fr, dur in frames:
                try:
                    bg = Image.new("RGBA", (w, h), (1, 1, 1, 255))
                    fit = fr.copy()
                    fit.thumbnail((w, h), Image.LANCZOS)
                    bg.alpha_composite(fit, ((w - fit.width) // 2, (h - fit.height) // 2))
                    if has_np:
                        arr = _np.array(bg)
                        mask = arr[:, :, 3] < 10
                        arr[mask] = (1, 1, 1, 255)
                        bg = _I.fromarray(arr)
                    photos.append((ImageTk.PhotoImage(bg), int(dur)))
                except Exception:
                    continue
            if len(photos) < 2:
                return False
            st["photos"] = photos
            st["gi"] = 1
            try:
                st["photo"] = photos[0][0]
                lbl.configure(image=photos[0][0])
            except Exception:
                pass

            def _step():
                try:
                    if st.get("win") is None:
                        return
                    try:
                        win.winfo_exists()
                    except Exception:
                        return
                    phs = st.get("photos") or []
                    if not phs:
                        return
                    i = int(st.get("gi", 0) or 0) % len(phs)
                    ph, dur = phs[i]
                    st["photo"] = ph
                    try:
                        lbl.configure(image=ph)
                    except Exception:
                        return
                    st["gi"] = i + 1
                    try:
                        st["after"] = win.after(max(60, int(dur)), _step)
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                old = st.pop("after", None)
                if old is not None:
                    try:
                        win.after_cancel(old)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                st["after"] = win.after(int(photos[0][1]), _step)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _save_stickers(self) -> None:
        try:
            out = []
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    cfg = dict(st.get("cfg", {}))
                    # Refresh real size
                    try:
                        cfg["w"] = int(st["win"].winfo_width() or cfg.get("w", 160))
                        cfg["h"] = int(st["win"].winfo_height() or cfg.get("h", 160))
                    except Exception:
                        pass
                    if cfg.get("path"):
                        out.append(cfg)
                except Exception:
                    pass
            self.theme.set(out, "stickers")
        except Exception:
            pass

    def _add_sticker_dialog(self) -> None:
        p = filedialog.askopenfilename(title="UI image (PNG/JPG/GIF)",
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not p:
            return
        try:
            from PIL import Image as _I
            im = _I.open(p)
            w, h = im.size
            scale = min(1.0, 220.0 / max(1, max(w, h)))
            w, h = max(40, int(w * scale)), max(40, int(h * scale))
        except Exception:
            w, h = 160, 160
        try:
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
            dx, dy = 120 + len(self._stickers) * 24, 120 + len(self._stickers) * 24
        except Exception:
            dx, dy = 120, 120
        self._create_sticker({"path": p, "dx": dx, "dy": dy, "w": w, "h": h}, save=True)
        try:
            self.status.configure(text="Sticker added (drag it; right-click deletes it) ✔")
        except Exception:
            pass

    # ---------- sections ----------
    def show_section(self, key: str) -> None:
        # Compat: old themes may ask for "locales" (removed)
        if key == "locales":
            key = "playlists"
        # Leaving playlists, queue, or album: remove continuation + reset mode
        if getattr(self, "current_section", "") in ("playlists", "cola", "buscar") \
                and key not in ("playlists", "cola", "buscar"):
            self._clear_playlist_continuation()
            self._album_mode = False
        if key == "buscar" and getattr(self, "_album_mode", False):
            self._album_mode = False
        self.current_section = key
        self._new_progressive_token()
        self.current_list = []
        self.current_list_full = []
        self.visible_count = self._batch_size()
        self._loading_progressive = False
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass
        if key == "buscar":
            self.list_title.configure(text="Search songs above or open a playlist")
            if not self.current_list_full:
                self.render_list()
            else:
                self.render_list()
            self._paint_section_background()
            try:
                self._paint_playlist_toggle()
            except Exception:
                pass
        elif key == "playlists":
            self.list_title.configure(text="Your YouTube playlists")
            self.status.configure(text="Loading playlists (progressive)…")
            try:
                self._ensure_playlist_toggle()
            except Exception:
                pass
            # Set pl_kind so continuation knows we are in a playlist context
            self.pl_kind = "yt"
            self.pl_id = ""
            self.pl_title = "Your playlists"
            threading.Thread(target=self._load_playlists_bg, daemon=True).start()
            # Ensure continuation shows when entering playlists with loop OFF
            try:
                if self.player.loop_mode == "off":
                    self.root.after(100, self._show_playlist_continuation)
            except Exception:
                pass
        elif key == "favoritas":
            self.show_favorites()
        elif key == "cola":
            # The queue is the live list. If it already carries the
            # recommendations (because play_track loaded the whole list),
            # PRESERVE them and the separator position: never append a
            # second copy when navigating to this section.
            full = list(self.player.queue)
            self.current_list_full = full
            has_cont = any(isinstance(t, dict) and t.get("_continuation")
                           for t in full)
            if has_cont:
                if not getattr(self, "_pl_continuation_shown", False):
                    # Restore the separator position: number of leading
                    # non-recommendation tracks.
                    self._pl_continuation_shown = True
                    self._pl_continuation_rendered = True
                    base = 0
                    for t in full:
                        if isinstance(t, dict) and t.get("_continuation"):
                            break
                        base += 1
                    self._playlist_base_count = base
                self._cont_separator = None
                # The queue stays VIRTUALIZED (a 5 000 song queue must not
                # build 5 000 rows). The visible window plus the
                # recommendations are painted; the rest is loaded with
                # "Show more" exactly like any other long list.
                self._window_start = 0
                self._painted_order = []
                self._base_window = min(self._batch_size(),
                                        len(self._base_tracks()))
                self.current_list = self._window_tracks()
            else:
                self._pl_continuation_shown = False
                self._pl_continuation_rendered = False
                self._playlist_base_count = 0
                self._cont_separator = None
                self._window_start = 0
                self._base_window = min(self._batch_size(),
                                        len(self._base_tracks()))
                self.current_list = self._window_tracks()
            self.visible_count = len(self.current_list)
            self.list_title.configure(
                text=f"Current queue ({len(self.current_list)}/{len(full)})")
            self.render_list()
            self._paint_section_background()
            if (not has_cont and self.player.loop_mode == "off"
                    and (getattr(self, "current_playlist_id", "")
                         or getattr(self, "_album_mode", False)
                         or getattr(self, "pl_kind", None) == "yt")):
                self._show_playlist_continuation()
        elif key == "inicio":
            self.list_title.configure(text="Home")
            try:
                self._paint_playlist_toggle()
            except Exception:
                pass
            self._show_home_section()
        elif key == "explorar":
            self.list_title.configure(text="Explore")
            try:
                self._paint_playlist_toggle()
            except Exception:
                pass
            self._show_explore_section()

    def _show_home_section(self) -> None:
        """Home section: recommendations based on YOUR taste (liked songs +
        related tracks), not generic global tops."""
        self.current_section = "inicio"
        self._set_pl_context(None)
        self._new_progressive_token()
        self.current_list = []
        self.current_list_full = []
        self.visible_count = 0
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass
        self.list_title.configure(text="Home — Your Recommendations")
        self.status.configure(text="Loading your recommendations…")
        threading.Thread(target=self._load_home_taste, daemon=True).start()

    def _load_home_taste(self) -> None:
        """Build home recommendations from the user's Liked songs.

        For each liked song, fetch related tracks and mix them in. If the
        user is not signed in or has no liked songs, fall back to a gentle
        popular search (never the cancerous global tops).
        """
        try:
            tracks: list[dict] = []
            seen: set[str] = set()

            if self.client.authenticated:
                liked = self.client.get_liked_songs(limit=15) or []
                for song in liked:
                    vid = str(song.get("videoId", "") or "")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    tracks.append(song)
                    if len(tracks) >= 60:
                        break
                # Related songs for each liked song (the "taste" part).
                for song in liked[:8]:
                    vid = str(song.get("videoId", "") or "")
                    if not vid:
                        continue
                    try:
                        related = self.client.get_song_related(vid, limit=8) or []
                    except Exception:
                        related = []
                    for r in related:
                        rvid = str(r.get("videoId", "") or "")
                        if rvid and rvid not in seen:
                            seen.add(rvid)
                            r["_from"] = "related"
                            tracks.append(r)
                            if len(tracks) >= 60:
                                break
                    if len(tracks) >= 60:
                        break

            if not tracks:
                # Guest / no liked songs: a soft popular seed, not global tops.
                try:
                    res = self.client.search("new music", limit=30) or []
                    tracks = res
                except Exception:
                    tracks = []

            if not tracks:
                self._call_ui(self._show_home_empty)
                return

            self.current_list_full = tracks[:60]
            self.current_list = tracks[:self._batch_size()]
            self.visible_count = len(self.current_list)
            self._call_ui(self._render_home_taste)
        except Exception as e:
            self._call_ui(lambda: self.status.configure(
                text=f"Error loading home: {e}"))

    def _load_home_liked(self) -> None:
        """Kept for compatibility: now delegates to taste-based home."""
        self._load_home_taste()

    def _load_home_popular(self) -> None:
        """Kept for compatibility: now delegates to taste-based home."""
        self._load_home_taste()

    def _show_home_empty(self) -> None:
        if self.current_section != "inicio":
            return
        self.render_list()
        self._paint_section_background()
        try:
            if self.client.authenticated:
                self.status.configure(
                    text="Home - no liked songs yet. Like some on YT Music "
                    "or search for music you enjoy.")
            else:
                self.status.configure(
                    text="Home - sign in to get recommendations from your "
                    "liked songs, or search for music.")
        except Exception:
            pass

    def _render_home_taste(self) -> None:
        self.list_title.configure(
            text=f"Home — Your Recommendations ({len(self.current_list)})")
        self.render_list()
        self._paint_section_background()
        try:
            self.status.configure(
                text=f"Home - {len(self.current_list)} recommendations for you")
        except Exception:
            pass

    def _show_explore_section(self) -> None:
        """Explore section: discover new music based on YOUR taste."""
        self.current_section = "explorar"
        self._set_pl_context(None)
        self._new_progressive_token()
        self.current_list = []
        self.current_list_full = []
        self.visible_count = 0
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass
        self.list_title.configure(text="Explore — For You")
        self._load_explore()

    def _load_explore(self) -> None:
        """Load explore section content (taste-based when signed in)."""
        self.status.configure(text="Loading explore…")
        threading.Thread(target=self._load_explore_bg, daemon=True).start()

    def _load_explore_bg(self) -> None:
        """Load explore section in background.

        Signed in: related songs from liked songs + artist top tracks.
        Guest: a soft discovery search, not global tops.
        """
        try:
            tracks: list[dict] = []
            seen: set[str] = set()

            if self.client.authenticated:
                liked = self.client.get_liked_songs(limit=12) or []
                for song in liked:
                    vid = str(song.get("videoId", "") or "")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    tracks.append(song)
                # Related songs + artist top tracks expand the taste bubble.
                for song in liked[:6]:
                    vid = str(song.get("videoId", "") or "")
                    artist_id = str(song.get("artistIds", [""])[0] if song.get("artistIds") else "")
                    try:
                        related = self.client.get_song_related(vid, limit=6) or []
                    except Exception:
                        related = []
                    for r in related:
                        rvid = str(r.get("videoId", "") or "")
                        if rvid and rvid not in seen:
                            seen.add(rvid)
                            r["_from"] = "related"
                            tracks.append(r)
                    if artist_id:
                        try:
                            _, artist_top = self.client.get_artist_top_tracks(artist_id, limit=6)
                        except Exception:
                            artist_top = []
                        for r in artist_top:
                            rvid = str(r.get("videoId", "") or "")
                            if rvid and rvid not in seen:
                                seen.add(rvid)
                                r["_from"] = "artist"
                                tracks.append(r)
                    if len(tracks) >= 60:
                        break

            if not tracks:
                # Guest / no liked songs: gentle discovery search.
                try:
                    res = self.client.search("discover music", limit=30) or []
                    tracks = res
                except Exception:
                    tracks = []

            if not tracks:
                self._call_ui(self._show_tracks_result, [], "Explore - No results")
                return

            self.current_list_full = tracks[:60]
            self.current_list = tracks[:self._batch_size()]
            self.visible_count = len(self.current_list)
            self._call_ui(self._render_explore)
        except Exception as e:
            self._call_ui(lambda: self.status.configure(text=f"Error loading explore: {e}"))

    def _render_explore(self) -> None:
        self.list_title.configure(
            text=f"Explore — For You ({len(self.current_list)})")
        self.render_list()
        self._paint_section_background()
        try:
            self.status.configure(
                text=f"Explore - {len(self.current_list)} discoveries for you")
        except Exception:
            pass

    def _load_playlists_bg(self) -> None:
        token = getattr(self, "_progressive_token", 0)
        def _batch(batch, is_final):
            if token != getattr(self, "_progressive_token", 0):
                return
            rows = [{"videoId": "", "title": "♪ " + p.get("title", "Untitled"),
                     "artist": str(p.get("count", "")),
                     "_playlist_id": p.get("id", ""),
                     "thumbnail": ((p.get("thumbnails") or [{}])[0].get("url", "")
                                   if p.get("thumbnails") else "")} for p in (batch or []) if isinstance(p, dict)]
            if not rows and is_final and not self.client.authenticated:
                self._call_ui(self._show_playlists_empty)
                return
            if not rows and is_final:
                self._call_ui(self._show_playlists_empty)
                return
            self._call_ui(self._set_full_list, rows, "Your playlists", token, is_final)
            self._call_ui(self._paint_section_background)
        try:
            self.client.fetch_progressive("library", "", on_batch=_batch,
                                          should_stop=lambda: token != getattr(self, "_progressive_token", 0))
        except Exception:
            try:
                pls = self.client.get_library_playlists()
                self._call_ui(self._show_playlists_result, pls)
            except Exception:
                pass

    def _show_playlists_empty(self) -> None:
        if self.current_section != "playlists":
            return
        if not self.client.authenticated:
            self.list_title.configure(text="Not signed in: refresh cookiesYT.json (auto-reloads) or use ↗ URL")
            self.status.configure(text="Expired cookies. Export fresh cookies or use ↗ URL / Search.")
        else:
            self.list_title.configure(text="Your YT Music library is empty: use ↗ URL or Search")
            self.status.configure(text=self.client.last_error or "Empty library")
        self.current_list = []
        self.current_list_full = []
        self._ensure_playlist_toggle()
        self.render_list()

    def _show_playlists_result(self, pls: list[dict]) -> None:
        if self.current_section != "playlists":
            return
        if not pls:
            self._show_playlists_empty()
            return
        rows = [{"videoId": "", "title": "♪ " + p["title"],
                 "artist": str(p.get("count", "")),
                 "_playlist_id": p.get("id", ""),
                 "thumbnail": (p.get("thumbnails") or [{}])[0].get("url", "") if p.get("thumbnails") else ""} for p in pls]
        self.current_list_full = rows
        self.current_list = list(rows[:self._batch_size()])
        self.visible_count = len(self.current_list)
        self._ensure_playlist_toggle()
        self.list_title.configure(text=f"Your playlists ({len(self.current_list)}/{len(rows)})")
        self.status.configure(text="Ready")
        self._render_playlists_current_view()
        self._paint_section_background()

    def _is_playlist_rows(self) -> bool:
        """Are the visible rows playlists (not songs)?"""
        try:
            if getattr(self, "current_section", "") != "playlists":
                return False
            for t in (getattr(self, "current_list", []) or [])[:5]:
                if isinstance(t, dict) and t.get("_playlist_id"):
                    return True
            return False
        except Exception:
            return False

    def _ensure_playlist_toggle(self) -> None:
        """Themed List/Grid/Custom toggle, always visible in Playlists."""
        try:
            btn = getattr(self, "_playlist_view_btn", None)
            if btn is None:
                try:
                    if btn is not None:
                        btn.winfo_exists()
                    else:
                        raise Exception("none")
                except Exception:
                    pass
                btn = tk.Button(self.listpanel, text="",
                                command=self._cycle_playlist_view,
                                font=("Segoe UI", 9), relief="flat", bd=0, padx=6)
                btn.place(relx=1.0, x=-5, y=38, anchor="ne")
                self._playlist_view_btn = btn
            self._paint_playlist_toggle()
        except Exception:
            pass

    def _paint_playlist_toggle(self) -> None:
        """Repaint the playlist view toggle with ACTIVE theme colors + mode."""
        try:
            btn = getattr(self, "_playlist_view_btn", None)
            if btn is None:
                return
            try:
                btn.winfo_exists()
            except Exception:
                self._playlist_view_btn = None
                return
            if getattr(self, "current_section", "") != "playlists":
                try:
                    btn.place_forget()
                except Exception:
                    pass
                return
            try:
                rows = list(getattr(self, "current_list", []) or [])
                if rows and not any(isinstance(t, dict) and t.get("_playlist_id") for t in rows[:5]):
                    try:
                        btn.place_forget()
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            try:
                btn.place(relx=1.0, x=-5, y=38, anchor="ne")
            except Exception:
                pass
            mode = str(getattr(self, "playlist_view_mode", "list") or "list")
            label = {"list": "▤ List", "grid": "▣ Grid", "custom": "◆ Custom"}.get(mode, "▤ List")
            try:
                b = (self.theme.data.get("botones", {}) or {})
                bg = str(b.get("color_fondo", "") or (self.theme.data.get("lista", {}) or {}).get("color_item_hover", "#333333"))
                fg = str(b.get("color_texto", "") or (self.theme.data.get("texto", {}) or {}).get("color_titulo", "#ffffff"))
            except Exception:
                bg, fg = "#333333", "#ffffff"
            try:
                btn.configure(text=label, bg=bg, fg=fg, activebackground=bg, activeforeground=fg)
            except Exception:
                pass
        except Exception:
            pass

    def _cycle_playlist_view(self) -> None:
        """Cycle List -> Square grid -> Custom shape tiles."""
        try:
            order = ["list", "grid", "custom"]
            cur = str(getattr(self, "playlist_view_mode", "list") or "list")
            nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "list"
            self.playlist_view_mode = nxt
            self.playlist_grid_view = (nxt != "list")
            try:
                self.theme.set(nxt, "lista", "vista_playlists")
            except Exception:
                pass
            self._paint_playlist_toggle()
            self._render_playlists_current_view()
            try:
                self.status.configure(text=f"Playlist view: {nxt.capitalize()} (List/Grid/Custom)")
            except Exception:
                pass
        except Exception:
            pass

    def _toggle_playlist_view(self) -> None:
        self._cycle_playlist_view()

    def _render_playlists_current_view(self) -> None:
        mode = str(getattr(self, "playlist_view_mode", "list") or "list")
        if mode in ("grid", "custom"):
            self._render_playlists_grid(custom=(mode == "custom"))
        else:
            self.render_list()

    def _render_playlists_grid(self, custom: bool = False) -> None:
        for w in self.row_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self.row_widgets = []
        try:
            if getattr(self, "_more_btn_row", None) is not None:
                try:
                    self._more_btn_row.destroy()
                except Exception:
                    pass
                self._more_btn_row = None
        except Exception:
            pass

        tile_size = 150
        try:
            avail = int(self.canvas.winfo_width() or self.listpanel.winfo_width() or 500)
        except Exception:
            avail = 500
        avail = max(220, int(avail) - 16)
        cols = max(1, avail // 170)
        cols = min(cols, max(1, len(self.current_list or []) or 1))
        tile_size = max(110, min(260, (avail - 8 * (cols + 1)) // max(1, cols)))
        # Re-layout when the window width changes (debounced).
        try:
            if not getattr(self, "_grid_bind_ok", False):
                self._grid_bind_ok = True

                def _on_grid_conf(e=None):
                    try:
                        if (getattr(self, "current_section", "") != "playlists"
                                or str(getattr(self, "playlist_view_mode", "list") or "list") == "list"
                                or not self._is_playlist_rows()):
                            return
                        try:
                            if getattr(self, "_grid_conf_after", None) is not None:
                                self.root.after_cancel(self._grid_conf_after)
                        except Exception:
                            pass
                        self._grid_conf_after = self.root.after(
                            250, self._render_playlists_current_view)
                    except Exception:
                        pass
                self.listpanel.bind("<Configure>", _on_grid_conf, add="+")
                self.canvas.bind("<Configure>", _on_grid_conf, add="+")
        except Exception:
            pass
        try:
            li = self.theme.data.get("lista", {}) or {}
            tx = self.theme.data.get("texto", {}) or {}
            tile_bg = str(li.get("color_item_hover", "#333333") or "#333333")
            base_bg = str(li.get("color_fondo", "#222222") or "#222222")
            title_fg = str(tx.get("color_titulo", "#ffffff") or "#ffffff")
            sub_fg = str(tx.get("color_subtitulo", "#a0a0a0") or "#a0a0a0")
            fam = str(tx.get("fuente_familia", "Segoe UI") or "Segoe UI")
        except Exception:
            tile_bg, base_bg, title_fg, sub_fg, fam = "#333333", "#222222", "#ffffff", "#a0a0a0", "Segoe UI"
        # Custom tile face: theme button custom PNG when available.
        custom_img = None
        if custom:
            try:
                b = (self.theme.data.get("botones", {}) or {})
                cp = str(b.get("forma_custom_path", "") or "")
                if cp and os.path.exists(cp):
                    from PIL import Image, ImageTk
                    custom_img = ImageTk.PhotoImage(
                        Image.open(cp).convert("RGBA").resize((tile_size, tile_size)))
                    self._pl_custom_img = custom_img
            except Exception:
                custom_img = None
        row_frame = None
        col = 0
        for t in self.current_list:
            if col == 0:
                row_frame = tk.Frame(self.listframe, bg=base_bg)
                row_frame.pack(fill="x", padx=4, pady=4)
                self.row_widgets.append(row_frame)
            tile = tk.Frame(row_frame, bg=tile_bg,
                            width=tile_size, height=tile_size + 34, cursor="hand2")
            tile.pack(side="left", padx=4, pady=4)
            tile.pack_propagate(False)
            tile._playlist_data = t
            if custom_img is not None:
                try:
                    face = tk.Label(tile, image=custom_img, bg=tile_bg, cursor="hand2")
                    face.place(x=0, y=0, relwidth=1, relheight=1)
                    tile._face = face
                except Exception:
                    pass
            thumb_lbl = tk.Label(tile, bg=base_bg)
            thumb_lbl.pack(fill="both", expand=True, padx=4, pady=4)
            try:
                _th = self._playlist_thumb(t)
            except Exception:
                _th = t.get("thumbnail", "")
            if _th:
                self._load_thumb_async(_th, thumb_lbl, tile_size - 8)
            else:
                thumb_lbl.configure(text="♪", fg=sub_fg, font=(fam, 24))
            title_lbl = tk.Label(tile, text=str(t.get("title", "Untitled"))[:20],
                                 bg=base_bg,
                                 fg=title_fg,
                                 font=(fam, 9, "bold"), wraplength=tile_size - 8)
            title_lbl.pack(fill="x", padx=4, pady=2)
            pid = t.get("_playlist_id", "")
            title = t.get("title", "")
            tile.bind("<Button-1>", lambda e, p=pid, ti=title: self.open_playlist(p, ti))
            thumb_lbl.bind("<Button-1>", lambda e, p=pid, ti=title: self.open_playlist(p, ti))
            title_lbl.bind("<Button-1>", lambda e, p=pid, ti=title: self.open_playlist(p, ti))
            tile.bind("<Double-Button-1>", lambda e, p=pid, ti=title: self.open_playlist(p, ti))
            tile.bind("<Button-3>", lambda e, p=pid, ti=title: self._show_playlist_menu(e, p, ti))
            thumb_lbl.bind("<Button-3>", lambda e, p=pid, ti=title: self._show_playlist_menu(e, p, ti))
            title_lbl.bind("<Button-3>", lambda e, p=pid, ti=title: self._show_playlist_menu(e, p, ti))
            try:
                if custom_img is not None and getattr(tile, "_face", None) is not None:
                    tile._face.bind("<Button-1>", lambda e, p=pid, ti=title: self.open_playlist(p, ti))
                    tile._face.bind("<Button-3>", lambda e, p=pid, ti=title: self._show_playlist_menu(e, p, ti))
            except Exception:
                pass
            col += 1
            if col >= cols:
                col = 0

        total = len(self.current_list_full)
        shown = len(self.current_list)
        if total > shown:
            more = tk.Frame(self.listframe, bg=base_bg)
            more.pack(fill="x", padx=4, pady=6)
            self._more_btn_row = more
            self.row_widgets.append(more)
            rest = total - shown
            b = tk.Button(more, text=f"Show more ({rest} left)",
                          command=self.show_more_rows)
            b.pack(pady=6)
            try:
                self._style_button(b, f"Show more ({rest} left)",
                                   base_bg,
                                   size=30, wide=True, fontsize=11)
            except Exception:
                pass

        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self._schedule_retile()


    def _on_library_select(self, event=None) -> None:
        try:
            sel = self.playlist_box.curselection()
            if not sel:
                return
            name = self.playlist_box.get(sel[0])
            pid = getattr(self, "_lib_ids", {}).get(name, "")
            if pid:
                self.open_playlist(pid, name)
        except Exception:
            pass

    def refresh_library_list(self) -> None:
        def _bg():
            pls = self.client.get_library_playlists(limit=50)
            self._call_ui(self._fill_library_box, pls)
        threading.Thread(target=_bg, daemon=True).start()

    def _fill_library_box(self, pls: list[dict]) -> None:
        try:
            self.playlist_box.delete(0, "end")
            self._lib_ids = {}
            for p in pls[:50]:
                self.playlist_box.insert("end", p["title"])
                self._lib_ids[p["title"]] = p["id"]
        except Exception:
            pass

    def _set_pl_context(self, kind, pid: str = "", title: str = "") -> None:
        self.pl_kind = kind
        self.pl_id = pid or ""
        self.pl_title = title or ""
        if kind == "yt":
            self.current_playlist_id = self.pl_id

    def open_playlist(self, pid: str, title: str = "", autoplay: bool = False) -> None:
        # Reset continuation state for the new playlist.
        self._pl_continuation_shown = False
        self._pl_continuation_rendered = False
        self._set_pl_context("yt", pid, title or pid)
        try:
            self._open_autoplay = str(pid) if autoplay else ""
        except Exception:
            pass
        self._new_progressive_token()
        self.current_list = []
        self.current_list_full = []
        self.list_title.configure(text=f"Loading: {title or pid}...")
        self.status.configure(text="Loading playlist (progressive)…")
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass
        threading.Thread(target=self._open_playlist_bg, args=(pid, title), daemon=True).start()

    def _open_playlist_bg(self, pid: str, title: str) -> None:
        token = getattr(self, "_progressive_token", 0)
        base_title = f"Playlist: {title or pid}"
        def _batch(batch, is_final):
            if token != getattr(self, "_progressive_token", 0):
                return
            self._call_ui(self._set_full_list, list(batch or []), base_title, token, is_final)
            self._call_ui(self._paint_section_background)
        try:
            self.client.fetch_progressive("playlist", pid, on_batch=_batch,
                                          should_stop=lambda: token != getattr(self, "_progressive_token", 0))
        except Exception:
            try:
                tracks = self.client.get_playlist_tracks(pid)
                self._call_ui(self._show_tracks_result, tracks, base_title)
            except Exception:
                pass

    def _show_tracks_result(self, tracks: list[dict], title: str) -> None:
        # Single entry (searches, direct URL): also progressive at render
        token = getattr(self, "_progressive_token", 0)
        self.current_list_full = list(tracks or [])
        self.current_list = list(self.current_list_full[:self._batch_size()])
        self.visible_count = len(self.current_list)
        total = len(self.current_list_full)
        shown = len(self.current_list)
        self.list_title.configure(text=f"{title} ({shown}/{total})" if total != shown else f"{title} ({total})")
        self.status.configure(text="Ready" if tracks else (self.client.last_error or "No results"))
        self.render_list()
        self._paint_section_background()
        try:
            self._paint_playlist_toggle()
        except Exception:
            pass
        # Show continuation if loop is OFF and we are viewing a playlist or album
        try:
            if self.player.loop_mode == "off":
                is_playlist_ctx = bool(getattr(self, "current_playlist_id", ""))
                is_album_ctx = bool(getattr(self, "_album_mode", False))
                if is_playlist_ctx or is_album_ctx:
                    self._show_playlist_continuation()
        except Exception:
            pass
        # "Play all" from the playlist menu: start the first song.
        try:
            if getattr(self, "_open_autoplay", "") and (tracks or []):
                self._open_autoplay = ""
                first = next((t for t in (tracks or []) if t.get("videoId")), None)
                if first:
                    self.play_track(first)
        except Exception:
            pass

    def do_search(self) -> None:
        q = self.search_var.get().strip()
        if not q:
            return
        # If a URL was pasted into the search box, open it directly
        from .youtube_client import extract_playlist_id, extract_video_id
        if ("youtube.com" in q or "youtu.be" in q) and (extract_playlist_id(q) or extract_video_id(q)):
            self.open_url_dialog(prefill=q)
            return
        self.current_section = "buscar"
        self._set_pl_context(None)
        self.list_title.configure(text=f"Searching: {q}...")
        self.status.configure(text="Searching...")
        threading.Thread(target=self._search_bg, args=(q,), daemon=True).start()

    def _search_bg(self, q: str) -> None:
        # Songs AND videos from three sources; they are painted as soon as
        # each one answers instead of waiting for the slowest.
        token = self._new_progressive_token()
        # Clear the rendered-id tracker so a new search rebuilds from scratch.
        self._rendered_ids = set()
        acc: list[dict] = []
        lock = threading.Lock()

        def _batch(items: list[dict]) -> None:
            with lock:
                have = {t.get("videoId") or t.get("_playlist_id") for t in acc}
                for t in items or []:
                    k = t.get("videoId") or t.get("_playlist_id")
                    if k and k in have:
                        continue
                    if k:
                        have.add(k)
                    acc.append(t)
                snap = list(acc)
            self._call_ui(self._search_partial, q, snap, token)

        def _run():
            tracks = self.client.search(q, limit=30, on_batch=_batch)
            with lock:
                if not acc:
                    acc.extend(tracks or [])
                snap = list(acc)
            self._call_ui(self._search_partial, q, snap, token, final=True)

        threading.Thread(target=_run, daemon=True).start()

    def _search_partial(self, q: str, tracks: list[dict], token: int,
                        final: bool = False) -> None:
        """Paint whatever has arrived; a newer search cancels this one.

        Replaces the whole list (not append) so search results never pile
        on top of previous search results. Uses incremental rendering: the
        first batch paints all rows, later batches only append rows that
        are not on screen yet — no more destroying and reloading every row
        on every search batch.
        """
        try:
            if token != getattr(self, "_progressive_token", 0):
                return
            if not final and not tracks:
                return
            ns = sum(1 for t in tracks if t.get("kind") == "song")
            nv = sum(1 for t in tracks if t.get("kind") == "video")
            extra = f" • {ns} songs • {nv} videos" if (ns and nv) else ""
            suffix = "" if final else " ↳"
            self.current_list_full = list(tracks)
            self.current_list = list(tracks[:self._batch_size()])
            self.visible_count = len(self.current_list)
            self._loading_progressive = not final
            self.list_title.configure(
                text=f"Results: {q}{suffix} ({len(self.current_list)}){extra}")
            self.status.configure(text="Searching…" if not final
                                  else ("Ready" if tracks
                                        else (self.client.last_error or "No results")))
            # First batch of a new search: full render. Later batches: only
            # append rows that are not already painted (by videoId identity).
            first = len(getattr(self, "_rendered_ids", set()) or set()) == 0
            if first:
                self.render_list(keep_scroll=False)
            else:
                self._append_rows(self.current_list, start_index=0)
                try:
                    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                except Exception:
                    pass
                self._pin_canvas_bg()
                self._schedule_retile()
            try:
                self._update_more_button()
            except Exception:
                pass
        except Exception:
            pass

    def open_url_dialog(self, prefill: str = "") -> None:
        from tkinter import simpledialog
        from .youtube_client import extract_playlist_id, extract_video_id
        url = prefill or simpledialog.askstring(
            "Open URL",
            "Paste a YouTube URL (video, playlist, shorts) or an ID:\n"
            "Works with public playlists, no sign-in needed.")
        if not url:
            return
        url = url.strip()
        pid = extract_playlist_id(url)
        vid = extract_video_id(url)
        if pid:
            self.current_section = "buscar"
            self.open_playlist(pid, pid)
        elif vid:
            try:
                info = {"videoId": vid, "title": vid, "artist": "YouTube",
                        "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                        "duration_sec": 0}
                self.current_section = "buscar"
                self.current_list = [info]
                # Enrich title in background
                threading.Thread(target=self._enrich_single_bg, args=(vid,), daemon=True).start()
                self.play_track(info)
            except Exception as e:
                self.status.configure(text=f"Invalid URL: {e}")
        else:
            # Treat it as a search
            self.search_var.set(url)
            self.do_search()

    def _enrich_single_bg(self, vid: str) -> None:
        try:
            info = self.client.get_stream_info(vid)
            track = {"videoId": vid, "title": info.get("title", vid),
                     "artist": info.get("uploader", "YouTube"),
                     "thumbnail": info.get("thumbnail", ""),
                     "duration_sec": info.get("duration_sec", 0)}
            self._call_ui(self._show_tracks_result, [track], "Video")
            self.root.after(100, lambda: self.play_track(track))
        except Exception:
            pass

    def show_favorites(self) -> None:
        """Liked = YT Music 'Liked songs' (no local data)."""
        self.current_section = "favoritas"
        self._set_pl_context(None)
        self._new_progressive_token()
        self.current_list = []
        self.current_list_full = []
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass
        if not self.client.authenticated:
            self.list_title.configure(text="Liked ♥ (YT Music sign-in needed)")
            self.status.configure(text="Not signed in: link your account to see your YT Music Likes.")
            self.render_list()
            return
        self.list_title.configure(text="Loading YT Music liked songs (progressive)…")
        threading.Thread(target=self._favs_bg, daemon=True).start()

    def _favs_bg(self) -> None:
        token = getattr(self, "_progressive_token", 0)
        def _batch(liked_batch, is_final):
            if token != getattr(self, "_progressive_token", 0):
                return
            liked = [t for t in (liked_batch or [])
                     if isinstance(t, dict) and t.get("videoId")]
            # Liked cache to paint ♥/♡ with no network per row
            try:
                self._liked_ids = {t["videoId"] for t in liked if t.get("videoId")}
            except Exception:
                pass
            self._call_ui(self._set_full_list, list(liked), "Liked ♥ (YT Music)", token, is_final)
            self._call_ui(self._paint_section_background)
            try:
                self._call_ui(self._refresh_control_icons)
            except Exception:
                pass
        try:
            self.client.fetch_progressive("liked", "", on_batch=_batch,
                                          should_stop=lambda: token != getattr(self, "_progressive_token", 0))
        except Exception:
            try:
                liked = self.client.get_liked_songs(limit=100)
                liked = [t for t in (liked or []) if t.get("videoId")]
                try:
                    self._liked_ids = {t["videoId"] for t in liked}
                except Exception:
                    pass
                self._call_ui(self._show_tracks_result, list(liked), "Liked ♥ (YT Music)")
            except Exception:
                pass

    # ---------- list ----------
    def _section_solid_color(self) -> str:
        """Devuelve el color sólido de la sección actual si está en modo color,
        o '' si debe usar el fondo global."""
        try:
            sec = self._seccion_efectiva()
            eff = self._effective_section_bg(sec)
            if str(eff.get("modo", "")) == "color" and eff.get("color"):
                return str(eff["color"])
        except Exception:
            pass
        return ""

    def _row_band_bg(self, i: int, n: int, active: bool = False) -> str:
        sec_color = self._section_solid_color()
        if sec_color:
            base = sec_color
        else:
            base = self._band(0.15 + 0.7 * (i / max(1, n)))
        if active:
            base = _blend(base, self.theme.data["lista"]["color_item_activo"], 0.65)
        return base

    def _row_hover(self, row: tk.Frame, inside: bool) -> None:
        try:
            base = getattr(row, "_base_bg", None) or row.cget("bg")
            active = bool(getattr(row, "_active_bg", False))
            if inside and not active:
                hov = _blend(base, self.theme.data["lista"]["color_item_hover"], 0.6)
            else:
                hov = getattr(row, "_full_bg", base)
            row.configure(bg=hov)
            for child in row.winfo_children():
                try:
                    if child.winfo_class() == "Label":
                        child.configure(bg=hov)
                    elif child.winfo_class() == "Button":
                        child.configure(bg=hov, activebackground=hov)
                except Exception:
                    pass
        except Exception:
            pass

    def _row_button(self, row: tk.Frame, row_bg: str, text: str, cmd, size: int = 26) -> tk.Button:
        b = tk.Button(row, text=text, command=cmd)
        b.pack(side="right", padx=2)
        self._install_hover(b)
        self._style_button(b, text, row_bg, size=size, fontsize=11)
        return b

    # ---------- right-click menu: ALL YT Music options ----------
    def _show_track_menu(self, event, track: dict) -> None:
        """Song context menu (right-click): all of YT Music here."""
        try:
            if not isinstance(track, dict) or not track.get("videoId"):
                return
            tr = dict(track)
            vid = tr.get("videoId", "")
            m = self._new_menu(self.root)
            m.add_command(label=f"▶ Play: {(tr.get('title') or '')[:40]}",
                          command=lambda: self.play_track(tr))
            m.add_command(label="▶▶ Play next",
                          command=lambda: self._menu_play_next(tr))
            m.add_command(label="＋ Add to queue",
                          command=lambda: self.add_to_queue(tr))
            # For continuation tracks: insert at specific position
            if tr.get("_continuation"):
                m.add_command(label="＋ Add after current song",
                              command=lambda: self._add_continuation_after_current(tr))
                m.add_command(label="＋ Add to queue (choose position)",
                              command=lambda: self._add_continuation_at_position(tr))
            m.add_separator()
            m.add_command(label="◉ Start radio",
                          command=lambda: self._menu_start_radio(tr))
            m.add_command(label="↳ Up next (YT Music queue)",
                          command=lambda: self._menu_up_next(tr))
            m.add_command(label="✦ Related songs",
                          command=lambda: self._menu_related(tr))
            m.add_separator()
            _fav_lbl = "♡ Unlike" if self._is_fav(tr) else "♥ Like (to YT Music Liked songs)"
            m.add_command(label=_fav_lbl, command=lambda: self.toggle_fav(tr))
            m.add_command(label="▽ Dislike",
                          command=lambda: self._menu_dislike(tr))
            m.add_command(label="⊞+ Save to YT playlist...",
                          command=lambda: self.save_to_playlist_dialog(tr))
            m.add_command(label="＋ New YT playlist with this song",
                          command=lambda: self._menu_create_playlist_with(tr))
            if self.pl_kind == "yt" and self.pl_id:
                m.add_command(label="✕ Remove from this playlist",
                              command=lambda: self.remove_track_current(tr))
            m.add_separator()
            m.add_command(label="▤ View album",
                          command=lambda: self._menu_view_album(tr))
            m.add_command(label="♫ View artist",
                          command=lambda: self._menu_view_artist(tr))
            _chan_name = str(tr.get("channel") or tr.get("artist") or "")
            m.add_command(
                label=f"▣ Open channel: {_chan_name[:28]}" if _chan_name
                else "▣ Open channel",
                command=lambda: self._open_channel_from_row(
                    tr, _chan_name, str(tr.get("channelId") or "")))
            m.add_command(label="≡ View lyrics",
                          command=lambda: self._menu_lyrics(tr))
            m.add_command(label="✦ Correct from Last.fm",
                          command=lambda: self._menu_lastfm_correct(tr))
            m.add_command(label="ℹ Song details",
                          command=lambda: self._menu_details(tr))
            m.add_separator()
            m.add_command(label="↗ Copy YouTube URL",
                          command=lambda: self._menu_copy_url(tr))
            m.add_command(label="◎ Open in YouTube",
                          command=lambda: self._menu_open_yt(tr))
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    m.grab_release()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            return "break"
        except Exception:
            return None

    # ---------- custom playlist display covers (local override) ----------
    @staticmethod
    def _pl_covers_path() -> str:
        try:
            return os.path.join("config", "playlist_covers.json")
        except Exception:
            return "playlist_covers.json"

    def _pl_covers_load(self) -> dict[str, str]:
        try:
            p = self._pl_covers_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f) or {}
                return {str(k): str(v) for k, v in d.items() if v and os.path.exists(str(v))}
        except Exception:
            pass
        return {}

    def _pl_covers_save(self) -> None:
        try:
            p = self._pl_covers_path()
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(getattr(self, "_pl_covers", {}) or {}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _playlist_thumb(self, t: dict) -> str:
        """Effective playlist cover: custom local file first, then YT thumbnail."""
        try:
            pid = str((t or {}).get("_playlist_id", "") or "")
            if pid and pid in (getattr(self, "_pl_covers", {}) or {}):
                cp = str(self._pl_covers[pid])
                if cp and os.path.exists(cp):
                    return cp
        except Exception:
            pass
        try:
            return str((t or {}).get("thumbnail", "") or "")
        except Exception:
            return ""

    def _set_playlist_cover_dialog(self, pid: str, title: str) -> None:
        p = filedialog.askopenfilename(title=f"Display cover: {title or pid}",
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not p:
            return
        try:
            self._pl_covers[str(pid)] = str(p)
            self._pl_covers_save()
        except Exception:
            pass
        try:
            self._render_playlists_current_view()
        except Exception:
            pass
        try:
            self.status.configure(text="Display cover set (this app only: YT has no cover API) ✔")
        except Exception:
            pass

    def _remove_playlist_cover(self, pid: str) -> None:
        try:
            if str(pid) in (getattr(self, "_pl_covers", {}) or {}):
                self._pl_covers.pop(str(pid), None)
                self._pl_covers_save()
        except Exception:
            pass
        try:
            self._render_playlists_current_view()
        except Exception:
            pass
        try:
            self.status.configure(text="Display cover removed ✔")
        except Exception:
            pass

    def _show_playlist_menu(self, event, pid: str, title: str) -> None:
        try:
            m = self._new_menu(self.root)
            m.add_command(label=f"▤ Open: {(title or pid or '')[:40]}",
                          command=lambda: self.open_playlist(pid, title))
            m.add_command(label="▶ Play all",
                          command=lambda: self.open_playlist(pid, title, autoplay=True))
            m.add_command(label="◉ Playlist radio",
                          command=lambda: self._menu_playlist_radio(pid, title))
            m.add_separator()
            m.add_command(label="✎ Rename playlist",
                          command=lambda: self.rename_yt_playlist(pid, title))
            m.add_command(label="▣ Set display cover (this app)",
                          command=lambda: self._set_playlist_cover_dialog(pid, title))
            try:
                if str(pid) in (getattr(self, "_pl_covers", {}) or {}):
                    m.add_command(label="⌫ Remove display cover",
                                  command=lambda: self._remove_playlist_cover(pid))
            except Exception:
                pass
            m.add_command(label="↗ Copy playlist URL",
                          command=lambda: self._menu_copy_playlist_url(pid))
            m.add_separator()
            m.add_command(label="✕ Delete YouTube playlist",
                          command=lambda: self.delete_yt_playlist(pid, title))
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    m.grab_release()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            return "break"
        except Exception:
            return None

    def _menu_play_next(self, track: dict) -> None:
        """Put the song right after the current one."""
        try:
            if not track.get("videoId"):
                return
            q = list(self.player.queue or [])
            idx = int(getattr(self.player, "index", -1) or -1)
            if idx < 0 or idx >= len(q):
                self.player.queue_add(track)
            else:
                try:
                    self.player.queue.insert(idx + 1, dict(track))
                    self.player._rebuild_shuffle()
                except Exception:
                    self.player.queue_add(track)
            self.status.configure(text=f"Up next: {track.get('title','')}")
        except Exception:
            pass

    def _menu_start_radio(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        self.status.configure(text="Starting YT Music radio...")
        def _bg():
            tracks = self.client.start_radio(vid, limit=25)
            if not tracks:
                self._call_ui(self.status.configure,
                              text=f"No radio: {(self.client.last_error or '')[:120]}")
                return
            # Radio STARTS with the chosen song and keeps mixing
            full = [dict(track)] + [t for t in tracks
                                    if t.get("videoId") != vid]
            self._call_ui(self._show_tracks_result, full,
                          f"◉ Radio: {track.get('title','')[:30]}")
            try:
                self.player.set_queue(full, start=0)
            except Exception:
                pass
            self._call_ui(self.status.configure, text="Radio started ◉")
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_up_next(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        self.status.configure(text="Loading YT Music Up next...")
        def _bg():
            tracks = self.client.get_up_next(vid, limit=25)
            if not tracks:
                self._call_ui(self.status.configure,
                              text=f"No results: {(self.client.last_error or '')[:120]}")
                return
            self._call_ui(self._show_tracks_result, tracks,
                          f"Up next: {track.get('title','')[:30]}")
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_related(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        self.status.configure(text="Finding related songs...")
        def _bg():
            tracks = self.client.get_song_related(vid, limit=20)
            if not tracks:
                self._call_ui(self.status.configure,
                              text=f"No related songs: {(self.client.last_error or '')[:120]}")
                return
            self._call_ui(self._show_tracks_result, tracks,
                          f"Related: {track.get('title','')[:30]}")
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_dislike(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        if not self.client.authenticated:
            self.status.configure(text="Not signed in: link your account to vote on YT Music.")
            return
        self.status.configure(text="Marking Dislike...")
        def _bg():
            ok = self.client.dislike_song(vid, True)
            if ok:
                try:
                    self._liked_ids.discard(vid)
                except Exception:
                    pass
                self._call_ui(self.status.configure, text="Marked Dislike ▽")
            else:
                self._call_ui(self.status.configure,
                              text=f"Failed: {(self.client.last_error or '')[:120]}")
            try:
                self._call_ui(self.render_list, True)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_create_playlist_with(self, track: dict) -> None:
        from tkinter import simpledialog
        if not self.client.authenticated:
            self.status.configure(text="Not signed in: link your account to create playlists.")
            return
        name = simpledialog.askstring("New YouTube playlist",
                                      "Playlist name:")
        if not name or not name.strip():
            return
        vid = track.get("videoId", "")
        self.status.configure(text=f"Creating '{name.strip()}'...")
        def _bg():
            pid = self.client.create_playlist(name.strip(), [vid] if vid else [])
            if pid:
                self._call_ui(self.refresh_library_list)
                self._call_ui(self.status.configure,
                              text=f"Playlist '{name.strip()}' creada ✔")
            else:
                self._call_ui(self.status.configure,
                              text=f"No se creo: {(self.client.last_error or '')[:120]}")
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_view_album(self, track: dict) -> None:
        album_id = str((track or {}).get("albumId", "") or "")
        album_name = str((track or {}).get("album", "") or "")
        if not album_id:
            # Without browseId (flat search): find the album by name
            q = f"{track.get('artist','')} {album_name or track.get('title','')}".strip()
            if not q:
                self.status.configure(text="This song has no album attached.")
                return
            self.status.configure(text=f"Finding album: {album_name or q}...")
            def _bg2():
                res = self.client.search(album_name or q, limit=10)
                self._call_ui(self._show_tracks_result, res, f"Album: {album_name or q}")
            threading.Thread(target=_bg2, daemon=True).start()
            return
        self.status.configure(text="Loading YT Music album...")
        def _bg():
            title, tracks = self.client.get_album_tracks(album_id)
            if not tracks:
                self._call_ui(self.status.configure,
                              text=f"No album: {(self.client.last_error or '')[:120]}")
                return
            self._call_ui(self._show_tracks_result, tracks,
                          f"▤ {title or album_name}")
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_view_artist(self, track: dict) -> None:
        aids = list((track or {}).get("artistIds", []) or [])
        aname = str((track or {}).get("artist", "") or "")
        if not aids:
            if not aname:
                self.status.configure(text="This song has no artist attached.")
                return
            self.status.configure(text=f"Finding artist: {aname}...")
            def _bg2():
                res = self.client.search(aname, limit=10)
                self._call_ui(self._show_tracks_result, res, f"Artist: {aname}")
            threading.Thread(target=_bg2, daemon=True).start()
            return
        aid = aids[0]
        self.status.configure(text="Loading YT Music artist...")
        def _bg():
            name, tracks = self.client.get_artist_top_tracks(aid, limit=20)
            if not tracks:
                self._call_ui(self.status.configure,
                              text=f"No artist: {(self.client.last_error or '')[:120]}")
                return
            self._call_ui(self._show_tracks_result, tracks,
                          f"♫ {name or aname}")
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_lyrics(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        self.status.configure(text="Finding lyrics...")
        def _bg():
            lyr, src = self.client.get_lyrics_text(vid)
            def _ui():
                win = tk.Toplevel(self.root)
                # Same frameless bar + app icon as the main window
                self._frameless_toplevel(win)
                win.title(f"Lyrics: {(track.get('title') or '')[:40]}")
                win.geometry("460x520")
                tk.Label(win, text=f"{track.get('title','')} — {track.get('artist','')}",
                         wraplength=420, font=("Segoe UI", 11, "bold")).pack(pady=8)
                txt = tk.Text(win, wrap="word")
                txt.pack(fill="both", expand=True, padx=10, pady=6)
                txt.insert("1.0", lyr or "No lyrics available for this song.")
                txt.configure(state="disabled")
                if src:
                    tk.Label(win, text=str(src)[:120], fg="gray").pack(pady=4)
            if not lyr:
                self._call_ui(self.status.configure, text="No lyrics available.")
            self._call_ui(_ui)
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_details(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        try:
            _ed = self._meta_edited(track)
        except Exception:
            _ed = {}
        lines = [f"Title: {track.get('title','?')}",
                 f"Artist: {track.get('artist','')}",
                 f"Album: {track.get('album','')}"]
        try:
            _shown = [f"Shown: {_ed.get('track','')}",
                      f"       {_ed.get('artist','')}",
                      f"       {_ed.get('album','')}"]
            if (_ed.get("track") != track.get("title", "")
                    or _ed.get("artist") != track.get("artist", "")
                    or _ed.get("album") != track.get("album", "")):
                lines += _shown + ["(regex edits applied)"]
        except Exception:
            pass
        lines += [f"Length: {track.get('duration') or _fmt_time(track.get('duration_sec'))}",
                  f"videoId: {vid}",
                  f"Liked: {track.get('likeStatus','') or ('yes' if self._is_fav(track) else 'no')}"]
        def _bg():
            info = self.client.get_song_details(vid) if vid else {}
            def _ui():
                extra = ""
                try:
                    if isinstance(info, dict) and info:
                        vd = info.get("videoDetails") or {}
                        extra = (f"\nViews: {vd.get('viewCount','?')}"
                                 f"\nChannel: {vd.get('author','?')}")
                        md = info.get("microformat") or {}
                        try:
                            extra += f"\nPublished: {(md.get('microformatDataRenderer') or {}).get('publishDate','')}"
                        except Exception:
                            pass
                except Exception:
                    extra = ""
                messagebox.showinfo("Details", "\n".join(lines) + extra)
            self._call_ui(_ui)
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_lastfm_correct(self, track: dict) -> None:
        """Fetch Last.fm correction (autocorrect) and apply it to the visible
        copies of this song (list, queue, player bar)."""
        try:
            tr = dict(track or {})
            if not tr.get("videoId"):
                return
            if not self.lastfm.configured:
                self.status.configure(text="Last.fm: set API key first (Settings > Last.fm).")
                return
            self.status.configure(text="Asking Last.fm for the correct tags...")
        except Exception:
            return

        def _bg():
            try:
                ed = self._meta_edited(tr)
                info = self.lastfm.track_get_info(ed.get("artist", "") or tr.get("artist", ""),
                                                  ed.get("track", "") or tr.get("title", ""))
                if not info or (not info.get("track") and not info.get("artist")):
                    self._call_ui(self.status.configure,
                                  text=f"Last.fm: no correction ({self.lastfm.last_error[:80]})")
                    return
                new_title = info.get("track") or tr.get("title", "")
                new_artist = info.get("artist") or tr.get("artist", "")
                new_album = info.get("album") or tr.get("album", "")
                self._call_ui(self._apply_correction_ui, tr.get("videoId", ""),
                              new_title, new_artist, new_album)
            except Exception as e:
                try:
                    self._call_ui(self.status.configure, text=f"Last.fm error: {e}")
                except Exception:
                    pass
        threading.Thread(target=_bg, daemon=True).start()

    def _apply_correction_ui(self, video_id: str, title: str, artist: str, album: str) -> None:
        """Write a Last.fm correction into every visible copy of the song."""
        try:
            if not video_id:
                return
            n = 0
            for bag in (getattr(self, "current_list_full", []) or [],
                        getattr(self, "current_list", []) or [],
                        list(getattr(self.player, "queue", []) or [])):
                for t in bag:
                    try:
                        if isinstance(t, dict) and t.get("videoId") == video_id:
                            if title:
                                t["title"] = title
                            if artist:
                                t["artist"] = artist
                            if album:
                                t["album"] = album
                            n += 1
                    except Exception:
                        pass
            try:
                cur = getattr(self.player, "current", None) or {}
                if cur.get("videoId") == video_id:
                    if title:
                        cur["title"] = title
                    if artist:
                        cur["artist"] = artist
                    if album:
                        cur["album"] = album
                    self._update_song_ui(dict(cur))
            except Exception:
                pass
            try:
                self.render_list(keep_scroll=True)
            except Exception:
                pass
            # New metadata = new Last.fm lookup for this song.
            try:
                self.refresh_play_count(video_id)
            except Exception:
                pass
            self.status.configure(text=f"Corrected from Last.fm ✔ ({n} copies)")
        except Exception:
            pass

    def _menu_copy_url(self, track: dict) -> None:
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        url = f"https://music.youtube.com/watch?v={vid}"
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status.configure(text="URL copied to clipboard ✔")
        except Exception as e:
            self.status.configure(text=f"Could not copy: {e}")

    def _menu_open_yt(self, track: dict) -> None:
        import webbrowser
        vid = (track or {}).get("videoId", "")
        if not vid:
            return
        try:
            webbrowser.open(f"https://music.youtube.com/watch?v={vid}")
        except Exception as e:
            self.status.configure(text=f"Could not open: {e}")

    def _menu_playlist_radio(self, pid: str, title: str) -> None:
        if not pid:
            return
        self.status.configure(text="Starting playlist radio...")
        def _bg():
            tracks = self.client.get_playlist_tracks(pid, limit=50)
            if not tracks:
                self._call_ui(self.status.configure, text="Empty playlist or no access.")
                return
            seed = (tracks[0] or {}).get("videoId", "")
            radio = self.client.start_radio(seed, limit=25) if seed else []
            full = radio or tracks
            self._call_ui(self._show_tracks_result, full, f"◉ Radio: {title}")
            if radio:
                try:
                    self.player.set_queue(full, start=0)
                except Exception:
                    pass
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_copy_playlist_url(self, pid: str) -> None:
        if not pid:
            return
        url = f"https://music.youtube.com/playlist?list={pid}"
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status.configure(text="URL de playlist copiada ✔")
        except Exception as e:
            self.status.configure(text=f"Could not copy: {e}")

    def _row_key(self, t: dict, i: int = 0) -> str:
        """Stable identity of a row, independent of any later enrichment.

        The progressive loader re-fetches the same playlist with a bigger
        limit, so the SAME track comes back with different thumbnail/duration
        fields. Comparing whole dicts made the renderer think nothing matched
        and rebuild the whole list on every batch: that was the blinking.
        """
        if not isinstance(t, dict):
            return f"row-{i}"
        for k in ("videoId", "_album_id", "_playlist_id", "albumId"):
            v = str(t.get(k, "") or "")
            if v:
                return v
        return f"row-{i}"

    def _append_only(self) -> bool:
        """Paint any row of current_list that is not on screen yet.

        Never destroys anything. This is what a progressive batch calls, so
        rows that were already painted stay exactly as they are.
        """
        try:
            painted = set(getattr(self, "_rendered_ids", set()) or set())
            li = self.theme.data["lista"]
            tx = self.theme.data["texto"]
            fam = tx["fuente_familia"]
            total = max(1, len(getattr(self, "current_list_full", []) or
                               self.current_list or [1]))
            added = 0
            for i, t in enumerate(self.current_list or []):
                key = self._row_key(t, i)
                if key in painted:
                    continue
                painted.add(key)
                try:
                    self._build_one_row(i, total, t, li, tx, fam,
                                         before=self._before_widget_for(t))
                    added += 1
                except Exception:
                    pass
            self._rendered_ids = painted
            self._rendered_keys = [self._row_key(t, i)
                                   for i, t in enumerate(self.current_list or [])]
            self._rendered_visible = list(self.current_list)
            try:
                self._enqueue_channel_lookups(self.current_list)
                self._enqueue_play_counts(self.current_list)
            except Exception:
                pass
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
            return added > 0
        except Exception:
            return False

    def _extend_rows(self, new_visible: list[dict]) -> bool:
        """Append the new rows instead of rebuilding the list.

        Progressive loads (long playlists) call this on every batch; a full
        render_list() per batch made loaded rows blink and reload forever.
        """
        try:
            have = len(getattr(self, "_rendered_visible", []) or [])
            if have <= 0:
                return False
            old_keys = [self._row_key(t, i)
                        for i, t in enumerate(self._rendered_visible)]
            new_keys = [self._row_key(t, i)
                        for i, t in enumerate(new_visible or [])]
            # Rows already on screen must be a prefix of the new list,
            # compared by IDENTITY (see _row_key), not by field equality.
            if new_keys[:have] != old_keys[:have]:
                return False
            self._append_only()
            try:
                self._update_more_button()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _update_more_button(self) -> None:
        """Keep the 'Show more' row consistent with what is on screen."""
        try:
            more = getattr(self, "_more_btn_row", None)
            if more is None:
                return
            total = len(getattr(self, "current_list_full", []) or [])
            shown = len(self.current_list)
            for w in more.winfo_children():
                try:
                    rest = total - shown
                    w.configure(text=f"Show more ({rest} left)")
                    self._style_button(w, f"Show more ({rest} left)",
                                       self._tint_mid, size=30, wide=True,
                                       fontsize=11)
                except Exception:
                    pass
        except Exception:
            pass

    # ---------- playlist continuation (loop OFF) ----------
    def _clear_playlist_continuation(self) -> None:
        """Remove the separator, the recommendation rows AND the
        recommendation tracks from the session list/queue. Nothing is ever
        saved to YouTube."""
        try:
            # Invalidate any recommendation request still in flight.
            self._pl_continuation_token = int(
                getattr(self, "_pl_continuation_token", 0) or 0) + 1
            if not getattr(self, "_pl_continuation_shown", False):
                return
            self._pl_continuation_shown = False
            self._pl_continuation_rendered = False
            self._cont_separator = None
            self._playlist_base_count = 0
            self._continuation_tracks = []
            # Remove the recommendation tracks from the session data too.
            cur_vid = str((self.player.current or {}).get("videoId", "") or "")

            def _keep(t) -> bool:
                if not isinstance(t, dict):
                    return False
                if not t.get("_continuation"):
                    return True
                # Keep the song that is playing right now, even if it was
                # originally a recommendation.
                return bool(cur_vid) and str(t.get("videoId", "") or "") == cur_vid

            self.current_list_full = [t for t in (self.current_list_full or [])
                                      if _keep(t)]
            self.current_list = list(
                self.current_list_full[:self._batch_size()])
            self.player.queue = [t for t in (self.player.queue or [])
                                 if _keep(t)]
            if cur_vid:
                for i, t in enumerate(self.player.queue):
                    if str(t.get("videoId", "") or "") == cur_vid:
                        self.player.index = i
                        break
                else:
                    self.player.index = -1
            else:
                self.player.index = 0 if self.player.queue else -1
            for w in list(self.row_widgets):
                try:
                    if getattr(w, "_is_continuation", False):
                        w.destroy()
                        self.row_widgets.remove(w)
                except Exception:
                    pass
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def _show_playlist_continuation(self) -> None:
        """Show a separator bar below the playlist/album songs and,
        underneath, recommended songs. Recommendations are appended to
        current_list_full and player.queue so they play one after another
        when the playlist ends. They are NOT saved to any playlist/album.
        Every row is draggable to any position."""
        try:
            if getattr(self, "_pl_continuation_shown", False):
                return
            is_playlist_ctx = bool(getattr(self, "current_playlist_id", ""))
            is_album_ctx = bool(getattr(self, "_album_mode", False))
            is_queue_ctx = getattr(self, "current_section", "") == "cola"
            if not (is_playlist_ctx or is_album_ctx or is_queue_ctx):
                return
            if self.player.loop_mode != "off":
                return
            if not bool(self.theme.get("lista",
                                       "recomendaciones_continuacion",
                                       default=True)):
                return
            base = [t for t in (self.current_list_full or [])
                    if isinstance(t, dict) and t.get("videoId")]
            if not base:
                return
            # The list stays VIRTUALIZED: a 5 000 song playlist must never
            # build 5 000 rows (it froze the UI and killed the process).
            # The separator is painted after the visible window and the
            # songs that are not on screen yet keep their place in the data,
            # so playback still runs the whole playlist before the
            # recommendations.
            self._pl_continuation_shown = True
            self._playlist_base_count = len(base)
            self._base_window = len(self.current_list or [])
            self._sep_visual_pos = len([w for w in self.row_widgets
                                        if getattr(w, "_is_draggable", False)])
            self._pl_continuation_seed = base[-1]
            # New fetch token: a late reply from a previous playlist/album
            # must NEVER be appended to the list the user is looking at now.
            self._pl_continuation_token = int(
                getattr(self, "_pl_continuation_token", 0) or 0) + 1
            token = self._pl_continuation_token
            # Separator bar (visual only, never part of playback).
            sep = self._make_separator_widget()
            self.row_widgets.append(sep)
            threading.Thread(target=self._load_pl_continuation_bg,
                             args=(base[-1], token), daemon=True).start()
        except Exception:
            pass

    def _load_pl_continuation_bg(self, seed: dict, token: int = None) -> None:
        """Fetch related songs for the playlist continuation."""
        try:
            vid = str(seed.get("videoId", "") or "")
            related: list[dict] = []
            if vid:
                try:
                    related = self.client.get_song_related(
                        vid,
                        limit=int(self.theme.get("lista",
                                                 "recomendaciones_cantidad",
                                                 default=10))) or []
                except Exception:
                    related = []
            if not related:
                artist = str(seed.get("artist", "") or "")
                if artist:
                    try:
                        related = self.client.search(artist, limit=10) or []
                    except Exception:
                        related = []
            self._call_ui(self._render_pl_continuation, related, token)
        except Exception as e:
            self._call_ui(lambda: self.status.configure(
                text=f"Error cargando recomendaciones: {e}"))
            self._call_ui(self._render_pl_continuation, [], token)

    def _render_pl_continuation(self, related: list[dict],
                                token: int = None) -> None:
        """Append recommended continuation songs to current_list_full and
        player.queue so they play after the playlist ends. Paint them below
        the separator. Every row is draggable anywhere."""
        try:
            if token is not None and token != getattr(
                    self, "_pl_continuation_token", -1):
                return  # stale reply from another playlist/album
            if not getattr(self, "_pl_continuation_shown", False):
                return
            if getattr(self, "_pl_continuation_rendered", False):
                return
            self._pl_continuation_rendered = True
            related_list = list(related or [])
            cant = int(self.theme.get("lista",
                                      "recomendaciones_cantidad",
                                      default=10))
            related_list = related_list[:max(1, cant)]
            for t in related_list:
                t["_continuation"] = True
            # Append to session list and player queue (NOT saved anywhere).
            self.current_list_full = list(self.current_list_full or []) + list(related_list)
            # The painted window stays bounded (virtualized): the
            # recommendation rows are painted right after the separator, but
            # the songs that are not on screen yet keep their place in the
            # data, so the whole playlist still plays before them.
            self.current_list = self._window_tracks()
            for t in related_list:
                try:
                    self.player.queue_add(t)
                except Exception:
                    pass
            # Already appended to player.queue above: do NOT add them again
            # when the queue ends (that used to duplicate recommendations).
            self._continuation_tracks = []
            # Paint recommendation rows below the separator.
            li = self.theme.data["lista"]
            tx = self.theme.data["texto"]
            fam = tx["fuente_familia"]
            n = max(1, len(self.current_list_full))
            start_i = self._playlist_base_count
            # _append_rows (and not _build_one_row) so the rows are marked
            # as painted: otherwise the next render painted them AGAIN and
            # every recommendation appeared twice.
            try:
                self._append_rows(list(related_list), start_index=start_i)
            except Exception:
                pass
            try:
                total = len(self.current_list_full)
                shown = len(self.current_list)
                self.list_title.configure(
                    text=f"{self.list_title.cget('text').split(' (')[0]} ({shown}/{total})")
            except Exception:
                pass
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def _sync_list_from_rows(self) -> None:
        """Make current_list_full / player.queue match the visual row order.

        Uses the track object stored on every row (not a videoId lookup), so
        duplicate songs are preserved. The separator splits the visual order
        in two zones: the playlist songs above it and the recommendations
        below it. Songs that are not painted yet (long list, "Show more")
        keep their place: the ones before the visible window stay before it
        and the ones after it stay right after it, still BEFORE the
        recommendations, so the whole playlist plays first.
        """
        try:
            old_full = list(self.current_list_full or [])
            old_ids = [str(t.get("videoId", "") or "")
                       for t in old_full if isinstance(t, dict)]
            q_ids = [str(t.get("videoId", "") or "")
                     for t in (self.player.queue or []) if isinstance(t, dict)]
            sep = getattr(self, "_cont_separator", None)
            has_sep = (getattr(self, "_pl_continuation_shown", False)
                       and sep is not None and sep in self.row_widgets)
            above: list[dict] = []
            below: list[dict] = []
            zone = above
            for w in self.row_widgets:
                if getattr(w, "_is_separator", False):
                    zone = below
                    continue
                dd = getattr(w, "_drag_data", None) or {}
                t = dd.get("track")
                if not isinstance(t, dict):
                    vid = str(dd.get("vid", "") or "")
                    t = next((x for x in old_full
                              if isinstance(x, dict)
                              and str(x.get("videoId", "") or "") == vid), None)
                if isinstance(t, dict) and t.get("videoId"):
                    zone.append(t)
            painted = above + below
            if not painted:
                return
            painted_ids = {id(t) for t in painted}
            # Songs of the playlist that are NOT painted yet: the ones
            # before the visible window keep their place before it, the ones
            # after it keep their place right after it.
            base_old = [t for t in old_full
                        if isinstance(t, dict) and not t.get("_continuation")]
            painted_base = [t for t in painted
                            if isinstance(t, dict) and not t.get("_continuation")]
            first_i = 0
            if painted_base:
                first_i = next((i for i, t in enumerate(base_old)
                                if t is painted_base[0]), 0)
            before = [t for t in base_old[:first_i] if id(t) not in painted_ids]
            after = [t for t in base_old[first_i:] if id(t) not in painted_ids]
            recs = [t for t in self._rec_tracks() if id(t) not in painted_ids]
            new_tracks = before + above + after + below + recs

            if not new_tracks:
                return
            # Separator position: visible rows above it / index in the list.
            if has_sep:
                self._sep_visual_pos = len(above)
                self._playlist_base_count = (len(before) + len(above)
                                             + len(after))
            self.current_list_full = new_tracks
            self._painted_order = list(painted)
            self.current_list = list(painted)
            self._base_window = len(painted_base)
            self._rendered_visible = list(self.current_list)
            # Only overwrite the live queue when the user is in the queue or
            # when the queue is exactly this list. Browsing another list must
            # never destroy the queue that is playing.
            if getattr(self, "current_section", "") == "cola" or q_ids == old_ids:
                self.player.queue = list(new_tracks)
                cur_vid = str((self.player.current or {}).get("videoId", "") or "")
                if cur_vid:
                    for i, t in enumerate(new_tracks):
                        if str(t.get("videoId", "") or "") == cur_vid:
                            self.player.index = i
                            break
                    else:
                        self.player.index = 0
                else:
                    self.player.index = 0 if new_tracks else -1
                try:
                    self.player._rebuild_shuffle()
                except Exception:
                    pass
        except Exception:
            pass

    def _promote_continuation_row(self, track: dict) -> None:
        """When a recommended (continuation) song starts playing, move its
        row ABOVE the separator AND sync current_list_full / player.queue so
        the playback order matches the visual order. Played recommendations
        accumulate above the separator; unplayed ones stay below."""
        try:
            if not getattr(self, "_pl_continuation_shown", False):
                return
            vid = str(track.get("videoId", "") or "")
            if not vid:
                return
            sep = getattr(self, "_cont_separator", None)
            if sep is None or not sep.winfo_exists():
                self._cont_separator = None
                return
            try:
                sep_pos = self.row_widgets.index(sep)
            except (ValueError, AttributeError):
                self._cont_separator = None
                return
            # Find this track's row below the separator.
            target_i = None
            for i in range(sep_pos + 1, len(self.row_widgets)):
                w = self.row_widgets[i]
                if not getattr(w, "_is_continuation", False) or w is sep:
                    continue
                row_vid = str((getattr(w, "_drag_data", None) or {}).get("vid", "") or "")
                if row_vid == vid:
                    target_i = i
                    break
            if target_i is None:
                return
            # Detach and re-insert just before the separator.
            w = self.row_widgets[target_i]
            w.pack_forget()
            self.row_widgets.pop(target_i)
            self.row_widgets.insert(sep_pos, w)
            # Repack the block from the separator onward.
            block = list(self.row_widgets[sep_pos:])
            for b in block:
                try:
                    b.pack_forget()
                except Exception:
                    pass
            for b in block:
                try:
                    if b is sep:
                        b.pack(fill="x", padx=4, pady=(10, 2))
                    else:
                        b.pack(fill="x", padx=4, pady=2)
                except Exception:
                    pass
            # CRITICAL: sync the data model so playback order matches visuals.
            self._sync_list_from_rows()
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def _add_more_button(self) -> None:
        """The 'Show more' button, when the list still has songs."""
        try:
            total = len(getattr(self, "current_list_full", []) or [])
            shown = len(self.current_list)
            if total > shown:
                more = tk.Frame(self.listframe, bg=self._tint_mid)
                more.pack(fill="x", padx=4, pady=6)
                more._is_more = True
                self._more_btn_row = more
                self.row_widgets.append(more)
                rest = total - shown
                b = tk.Button(more, text=f"Show more ({rest} left)",
                              command=lambda: self.show_more_rows())
                b.pack(pady=6)
                try:
                    self._style_button(b, f"Show more ({rest} left)",
                                       self._tint_mid, size=30, wide=True,
                                       fontsize=11)
                except Exception:
                    pass
            else:
                self._more_btn_row = None
        except Exception:
            pass

    def _render_window(self, tracks: list[dict]) -> None:
        """Paint a window of songs RE-USING the row widgets that are
        already on screen.

        Destroying hundreds of Tk rows took a full second and froze the
        interface every time the list paged; the rows are re-used (and the
        spare ones are only hidden, never destroyed) so it stays instant
        and the memory stays flat."""
        try:
            song_rows = [w for w in self.row_widgets
                         if getattr(w, "_is_draggable", False)]
            for w in list(self.row_widgets):
                if w in song_rows:
                    continue
                try:
                    w.destroy()
                except Exception:
                    pass
            self.row_widgets = []
            self._cont_separator = None
            self._rendered_ids = set()
            self._rendered_keys = []
            self._play_labels = {}
            li = self.theme.data["lista"]
            tx = self.theme.data["texto"]
            fam = tx["fuente_familia"]
            n = max(1, len(self.current_list_full or tracks or [1]))
            pool = list(getattr(self, "_row_pool", []) or [])
            for k, t in enumerate(tracks or []):
                reuse = song_rows[k] if k < len(song_rows) else None
                if reuse is None and pool:
                    reuse = pool.pop(0)
                try:
                    self._build_one_row(k, n, t, li, tx, fam, reuse=reuse)
                except Exception:
                    pass
            # The rows we do not need are only hidden: they are the pool
            # for the next page (destroying them is what froze the app).
            spare = song_rows[len(tracks or []):]
            for row in spare:
                try:
                    row.pack_forget()
                except Exception:
                    pass
            pool = spare + pool
            limit = int(getattr(self, "MAX_LIVE_ROWS", 400))
            while len(pool) > limit:
                try:
                    pool.pop(0).destroy()
                except Exception:
                    pool.pop(0)
            self._row_pool = pool
            self._ensure_separator_row()
            self._rendered_visible = list(self.current_list)
            self._add_more_button()
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def render_list(self, keep_scroll: bool = False) -> None:
        ypos = None
        try:
            if keep_scroll:
                ypos = self.canvas.yview()
        except Exception:
            pass
        # A full render destroys every row, so the "already painted" trackers
        # MUST be cleared here too; otherwise _append_rows skips everything and
        # the list comes back empty.
        self._rendered_ids = set()
        self._rendered_keys = []
        # Rows are about to be destroyed: their labels must not be kept.
        self._play_labels = {}
        # The separator frame is destroyed with the rows: forget the stale
        # reference so _ensure_separator_row can create a fresh one.
        self._cont_separator = None
        for w in self.row_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self.row_widgets = []
        try:
            if getattr(self, "_more_btn_row", None) is not None:
                try:
                    self._more_btn_row.destroy()
                except Exception:
                    pass
                self._more_btn_row = None
        except Exception:
            pass
        self._append_rows(list(self.current_list), start_index=0)
        # Paint the recommendations separator at the right place (if this
        # list has continuation enabled). render_list() is called from the
        # queue view too, so the separator survives navigation.
        self._ensure_separator_row()
        self._rendered_visible = list(self.current_list)
        # "Load more" button when full items remain (virtualized progressive)
        self._add_more_button()
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self._pin_canvas_bg()
        if keep_scroll and ypos is not None:
            try:
                self.canvas.yview_moveto(ypos[0])
            except Exception:
                pass
        try:
            self._paint_section_background()
        except Exception:
            pass
        self._schedule_retile()

    def _append_rows(self, tracks: list[dict], start_index: int = 0) -> None:
        """Build rows only for items not already on screen (by videoId).

        Skipping already-rendered rows is what stops the "rows reload / blink
        forever" on long playlists and keeps thumbnails from restarting.
        """
        li = self.theme.data["lista"]
        tx = self.theme.data["texto"]
        fam = tx["fuente_familia"]
        n = max(1, len(getattr(self, "current_list_full", []) or tracks or [1]))
        rendered_ids = set(getattr(self, "_rendered_ids", set()))
        for k, t in enumerate(tracks or []):
            i = start_index + k
            vid = str(t.get("videoId", "") or t.get("_playlist_id", "") or f"row-{i}")
            if vid in rendered_ids:
                continue
            rendered_ids.add(vid)
            try:
                self._build_one_row(i, n, t, li, tx, fam,
                                     before=self._before_widget_for(t))
            except Exception:
                pass
        self._rendered_ids = rendered_ids
        try:
            self._enqueue_channel_lookups(tracks)
        except Exception:
            pass
        try:
            self._enqueue_play_counts(tracks)
        except Exception:
            pass
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self._pin_canvas_bg()

    def _before_widget_for(self, track: dict):
        """New playlist songs are painted BEFORE the recommendations
        separator, so the order on screen is always the playback order."""
        try:
            if isinstance(track, dict) and track.get("_continuation"):
                return None
            sep = getattr(self, "_cont_separator", None)
            if sep is not None and sep.winfo_exists():
                return sep
        except Exception:
            pass
        return None

    def _build_one_row(self, i: int, n: int, t: dict, li: dict, tx: dict,
                       fam: str, before=None, reuse=None) -> None:
            base_bg = self._band(0.15 + 0.7 * (i / max(1, n)))
            if reuse is not None:
                # Re-use an emptied row. Destroying hundreds of Tk rows
                # takes a whole second and froze the interface; re-using
                # them keeps the page instant.
                row = reuse
                for _attr in ("_bg_label", "_bg_photo", "_bg_pil",
                              "_tile_solid", "_drag_data"):
                    try:
                        setattr(row, _attr, None)
                    except Exception:
                        pass
                try:
                    row._tile_exact = False
                    row._is_continuation = False
                    row.configure(bg=base_bg)
                except Exception:
                    pass
            else:
                row = tk.Frame(self.listframe, bg=base_bg)
                try:
                    if before is not None:
                        row.pack(fill="x", padx=4, pady=2, before=before)
                    else:
                        row.pack(fill="x", padx=4, pady=2)
                except Exception:
                    row.pack(fill="x", padx=4, pady=2)
            row._base_bg = base_bg
            row._full_bg = base_bg
            row._active_bg = False
            if before is not None:
                # Painted BEFORE the separator: keep row_widgets in the same
                # order as the screen, otherwise the drag would read a
                # different order than the one the user sees.
                try:
                    self.row_widgets.insert(self.row_widgets.index(before), row)
                except (ValueError, AttributeError):
                    self.row_widgets.append(row)
            else:
                self.row_widgets.append(row)
            self._bind_wheel(row)
            if t.get("_local_name"):
                # Compat: no local lists anymore (this row should never appear)
                cbg = self._apply_row_tile(row, i, n, base_bg)
                lb = tk.Label(row, text=t.get("title") or f"⊞ {t.get('_local_name', '')}", bg=cbg,
                              fg=tx["color_titulo"], font=(fam, tx["fuente_tam_lista"], "bold"),
                              anchor="w")
                lb.pack(side="left", fill="x", expand=True, padx=6, pady=8)
                self._bind_wheel(lb)
                try:
                    row._base_bg = cbg
                    row._full_bg = cbg
                except Exception:
                    pass
                return
            if t.get("_playlist_id"):
                cbg = self._apply_row_tile(row, i, n, base_bg)
                lb = tk.Label(row, text=t.get("title") or "♪ Playlist", bg=cbg,
                              fg=tx["color_titulo"], font=(fam, tx["fuente_tam_lista"], "bold"),
                              anchor="w")
                lb.pack(side="left", fill="x", expand=True, padx=6, pady=8)
                self._bind_wheel(lb)
                tk.Label(row, text=t.get("artist", ""), bg=cbg,
                         fg=tx["color_subtitulo"], font=(fam, tx["fuente_tam_pequena"])).pack(side="left")
                # YT playlists: open with double-click or right-click (menu)
                lb.bind("<Double-Button-1>",
                        lambda e, p=t["_playlist_id"], ti=t["title"]: self.open_playlist(p, ti))
                row.bind("<Double-Button-1>",
                         lambda e, p=t["_playlist_id"], ti=t["title"]: self.open_playlist(p, ti))
                for _w in (row, lb):
                    try:
                        _w.bind("<Button-3>",
                                lambda e, p=t["_playlist_id"], ti=t["title"]: self._show_playlist_menu(e, p, ti))
                    except Exception:
                        pass
                try:
                    row._base_bg = cbg
                    row._full_bg = cbg
                except Exception:
                    pass
                return
            # channel / artist: openable row (not playable).
            if t.get("kind") in ("channel", "artist"):
                cbg = self._apply_row_tile(row, i, n, base_bg)
                kind_label = "◍ Artista" if t.get("kind") == "artist" else "▣ Canal"
                lb = tk.Label(row, text=f"{kind_label}  {t.get('title') or 'Channel'}", bg=cbg,
                              fg=tx["color_titulo"], font=(fam, tx["fuente_tam_lista"], "bold"),
                              anchor="w", cursor="hand2")
                lb.pack(side="left", fill="x", expand=True, padx=6, pady=8)
                self._bind_wheel(lb)
                # Thumbnail / avatar on the left.
                try:
                    _tsize = max(44, int(li.get("tamano_thumbnail", 56) or 56))
                except Exception:
                    _tsize = 56
                if li.get("mostrar_thumbnails", True):
                    th = tk.Label(row, text="▶", bg=cbg, fg="white",
                                  font=(fam, max(12, _tsize // 3)),
                                  cursor="hand2",
                                  bd=0, highlightthickness=0)
                    try:
                        th.configure(compound="center", anchor="center")
                    except Exception:
                        pass
                    th.pack(side="left", padx=4, pady=3)
                    self._bind_wheel(th)
                    self._load_thumb_async(t.get("thumbnail", ""), th, _tsize,
                                           play_overlay=False)
                    th.bind("<Button-1>",
                            lambda e, cid=t.get("channelId", ""),
                                 cname=t.get("title", ""):
                            self.open_channel_window(cid, cname))
                    th.bind("<Button-3>",
                            lambda e, cid=t.get("channelId", ""),
                                 cname=t.get("title", ""):
                            self.open_channel_window(cid, cname))
                # Subtitle: subscriber count for channels.
                subs = str(t.get("subs", "") or "")
                if subs:
                    tk.Label(row, text=subs, bg=cbg,
                             fg=tx["color_subtitulo"],
                             font=(fam, tx["fuente_tam_pequena"])).pack(side="left")
                for _w in (row, lb):
                    try:
                        _w.bind("<Button-1>",
                                lambda e, cid=t.get("channelId", ""),
                                     cname=t.get("title", ""):
                                self.open_channel_window(cid, cname))
                        _w.bind("<Double-Button-1>",
                                lambda e, cid=t.get("channelId", ""),
                                     cname=t.get("title", ""):
                                self.open_channel_window(cid, cname))
                        _w.bind("<Button-3>",
                                lambda e, cid=t.get("channelId", ""),
                                     cname=t.get("title", ""):
                                self.open_channel_window(cid, cname))
                    except Exception:
                        pass
                try:
                    row._base_bg = cbg
                    row._full_bg = cbg
                except Exception:
                    pass
                return
            # song: active color first so the tile matches
            # Set drag data BEFORE any decoration: if a thumbnail/channel
            # lookup fails, the row must still be clickable and draggable.
            row._drag_data = {"x": 0, "y": 0, "vid": t.get("videoId", ""),
                              "index": i, "track": t}
            row._is_draggable = isinstance(t, dict) and bool(t.get("videoId"))
            if isinstance(t, dict) and t.get("_continuation"):
                row._is_continuation = True
            active = self.player.current and self.player.current.get("videoId") == t.get("videoId")
            bg = self._row_band_bg(i, n, active=bool(active))
            try:
                row.configure(bg=bg)
                row._full_bg = bg
                row._base_bg = bg
                row._active_bg = bool(active)
            except Exception:
                pass
            cbg = self._apply_row_tile(row, i, n, bg)
            try:
                row._base_bg = cbg
                row._full_bg = cbg
            except Exception:
                pass
            self._fill_song_row(row, i, n, t, li, tx, fam, cbg)

    def _fill_song_row(self, row, i: int, n: int, t: dict, li: dict,
                       tx: dict, fam: str, cbg: str) -> None:
        """Paint (or RE-PAINT) the content of a song row.

        When the row already has its widgets they are re-used and only
        their text and bindings are updated: that is what lets the list
        page through a huge playlist without destroying (and rebuilding)
        hundreds of Tk widgets, which froze the app for a second."""
        try:
            parts = getattr(row, "_song_parts", None)
            if parts is None:
                # A row coming from another kind of list: clean it first.
                for child in list(row.winfo_children()):
                    try:
                        child.destroy()
                    except Exception:
                        pass
                parts = {"th": None, "txt": None, "chan": [], "dl": None}
                row._song_parts = parts
            try:
                _tsize = max(44, int(li.get("tamano_thumbnail", 56) or 56))
            except Exception:
                _tsize = 56
            # Thumbnail = PLAY BUTTON (clicking the thumbnail plays).
            if li.get("mostrar_thumbnails", True):
                th = parts.get("th")
                if th is None or not th.winfo_exists():
                    th = tk.Label(row, text="\u25b6", bg=cbg, fg="white",
                                  font=(fam, max(12, _tsize // 3)),
                                  cursor="hand2",
                                  bd=0, highlightthickness=0)
                    try:
                        th.configure(compound="center", anchor="center")
                    except Exception:
                        pass
                    th.pack(side="left", padx=4, pady=3)
                    self._bind_wheel(th)
                    parts["th"] = th
                else:
                    try:
                        th.configure(bg=cbg, text="\u25b6")
                        th.pack(side="left", padx=4, pady=3)
                    except Exception:
                        pass
                self._load_thumb_async(t.get("thumbnail", ""), th, _tsize,
                                       play_overlay=True)
                th.bind("<Button-3>",
                        lambda e, tr=t: self._show_track_menu(e, tr))
            try:
                _ed = self._meta_edited(t)
                _tt = _ed.get("track") or t.get('title', '?')
                _ta = _ed.get("artist") or t.get('artist', '')
            except Exception:
                _tt, _ta = t.get('title', '?'), t.get('artist', '')
            # The uploader channel is what the user must always see, even
            # when the song data is edited for Last.fm.
            _chan = str(t.get("channel") or "")
            if not _chan:
                _chan = _ta
            _chan_list = ([c.strip() for c in _chan.split(",") if c.strip()]
                          if _chan else [])
            _chan_id_list = [c.strip() for c in
                              str(t.get("channelId") or "").split(",")
                              if c.strip()]
            if not _chan_list and _ta:
                _chan_list = [_ta]
                _chan_id_list = [str(t.get("channelId") or "") or ""]
            while len(_chan_id_list) < len(_chan_list):
                _chan_id_list.append("")
            # ---- TITLE ----
            txt = parts.get("txt")
            if txt is None or not txt.winfo_exists():
                txt = tk.Label(row, text=str(_tt),
                               bg=cbg, fg=tx["color_lista"],
                               font=(fam, tx["fuente_tam_lista"]), anchor="w")
                txt.pack(side="left", padx=(4, 2), pady=6)
                self._bind_wheel(txt)
                parts["txt"] = txt
            else:
                try:
                    txt.configure(text=str(_tt), bg=cbg,
                                  fg=tx["color_lista"])
                    txt.pack(side="left", padx=(4, 2), pady=6)
                except Exception:
                    pass
            txt.bind("<Button-3>", lambda e, tr=t: self._show_track_menu(e, tr))
            # ---- CHANNELS (one clickable label per artist) ----
            chan_labels = parts.get("chan") or []
            for idx, _cname in enumerate(_chan_list):
                _cid = _chan_id_list[idx] if idx < len(_chan_id_list) else ""
                if idx < len(chan_labels) and chan_labels[idx] is not None \
                        and chan_labels[idx].winfo_exists():
                    chan_lbl = chan_labels[idx]
                    try:
                        chan_lbl.configure(text=f"\u25a3 {_cname}", bg=cbg,
                                            fg=tx["color_titulo"])
                        chan_lbl.pack(side="left", padx=(2, 2), pady=6)
                    except Exception:
                        pass
                else:
                    chan_lbl = tk.Label(row, text=f"\u25a3 {_cname}",
                                        bg=cbg, fg=tx["color_titulo"],
                                        font=(fam, tx["fuente_tam_lista"], "bold"),
                                        anchor="w", cursor="hand2")
                    chan_lbl.pack(side="left", padx=(2, 2), pady=6)
                    self._bind_wheel(chan_lbl)
                    while len(chan_labels) <= idx:
                        chan_labels.append(None)
                    chan_labels[idx] = chan_lbl
                chan_lbl._is_channel = True
                chan_lbl._channel_id = _cid
                chan_lbl._channel_name = _cname
                chan_lbl._channel_track = t
                chan_lbl.bind("<Button-3>",
                              lambda e, tr=t: self._show_track_menu(e, tr))
            for extra in chan_labels[len(_chan_list):]:
                if extra is not None:
                    try:
                        extra.pack_forget()
                    except Exception:
                        pass
            parts["chan"] = chan_labels
            # "How many times I played it" (Last.fm), next to the title.
            try:
                txt._title = str(_tt)
                # The channel is painted as its own clickable label(s) next
                # to the title; don't repeat it inside the title text.
                txt._chan = ""
                txt._has_channel_label = bool(_chan_list)
                txt._vid = str(t.get("videoId", "") or "")
                self._refresh_row_text(txt)
                if txt._vid:
                    self._play_labels.setdefault(txt._vid, []).append(txt)
            except Exception:
                pass
            dur = t.get("duration") or (_fmt_time(t.get("duration_sec"))
                                        if t.get("duration_sec") else "")
            if dur:
                dl = parts.get("dl")
                if dl is None or not dl.winfo_exists():
                    dl = tk.Label(row, text=str(dur), bg=cbg,
                                  fg=tx["color_subtitulo"],
                                  font=(fam, tx["fuente_tam_pquena"]))
                    dl.pack(side="left", padx=4)
                    parts["dl"] = dl
                else:
                    try:
                        dl.configure(text=str(dur), bg=cbg,
                                     fg=tx["color_subtitulo"])
                        dl.pack(side="left", padx=4)
                    except Exception:
                        pass
                try:
                    dl.bind("<Button-3>",
                            lambda e, tr=t: self._show_track_menu(e, tr))
                except Exception:
                    pass
            elif parts.get("dl") is not None:
                try:
                    parts["dl"].pack_forget()
                except Exception:
                    pass
        except Exception:
            pass


    # ---------- visual helpers (drag & drop) ----------
    def _repack_rows(self) -> None:
        """Re-pack every existing row in exactly the order of row_widgets.
        Nothing is destroyed: thumbnails, labels and bindings stay alive."""
        try:
            alive = []
            for w in self.row_widgets:
                try:
                    if w.winfo_exists():
                        alive.append(w)
                except Exception:
                    pass
            self.row_widgets = alive
            for w in self.row_widgets:
                try:
                    w.pack_forget()
                except Exception:
                    pass
            for w in self.row_widgets:
                try:
                    if getattr(w, "_is_separator", False):
                        w.pack(fill="x", padx=4, pady=(10, 2))
                    elif getattr(w, "_is_more", False):
                        w.pack(fill="x", padx=4, pady=6)
                    else:
                        w.pack(fill="x", padx=4, pady=2)
                except Exception:
                    pass
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def _base_tracks(self) -> list:
        """The playlist/album songs of the current list (no recommendations)."""
        return [t for t in (self.current_list_full or [])
                if isinstance(t, dict) and not t.get("_continuation")]

    def _rec_tracks(self) -> list:
        """The recommendation songs of the current list."""
        return [t for t in (self.current_list_full or [])
                if isinstance(t, dict) and t.get("_continuation")]

    def _window_tracks(self) -> list:
        """The tracks that are painted right now: the visible window of the
        playlist plus the recommendations (they are few and always visible).

        The list stays virtualized: a 5 000 song playlist paints ~80 rows,
        never 5 000."""
        painted = getattr(self, "_painted_order", None)
        if painted:
            return list(painted)
        base = self._base_tracks()
        start = max(0, int(getattr(self, "_window_start", 0) or 0))
        size = max(0, int(getattr(self, "_base_window", 0) or 0))
        win = base[start:start + size]
        return win + self._rec_tracks()

    def _ensure_separator_row(self) -> None:
        """Make sure the recommendations separator exists and sits after
        exactly the visible track rows that belong to the playlist.
        Used after render_list()."""
        if not getattr(self, "_pl_continuation_shown", False):
            return
        try:
            rows = [w for w in self.row_widgets
                    if getattr(w, "_is_draggable", False)]
            if not rows:
                return
            base = max(0, int(getattr(self, "_sep_visual_pos", 0) or 0))
            if base <= 0:
                base = max(0, int(getattr(self, "_playlist_base_count", 0) or 0))
            base = min(base, len(rows))
            sep = getattr(self, "_cont_separator", None)
            if sep is not None:
                try:
                    if not sep.winfo_exists():
                        sep = None
                except Exception:
                    sep = None
            if sep is None:
                sep = self._make_separator_widget()
            try:
                self.row_widgets.remove(sep)
            except ValueError:
                pass
            others = list(self.row_widgets)
            count = 0
            insert_at = len(others)
            for i, w in enumerate(others):
                if getattr(w, "_is_draggable", False):
                    if count >= base:
                        insert_at = i
                        break
                    count += 1
            others.insert(insert_at, sep)
            self.row_widgets = others
            # Move ONLY the separator: re-packing every row re-lays the
            # whole list out and that is slow with many rows.
            try:
                sep.pack_forget()
            except Exception:
                pass
            try:
                if insert_at < len(others) - 1 and others[insert_at] is not sep:
                    sep.pack(fill="x", padx=4, pady=(10, 2),
                             before=others[insert_at])
                else:
                    sep.pack(fill="x", padx=4, pady=(10, 2))
            except Exception:
                try:
                    sep.pack(fill="x", padx=4, pady=(10, 2))
                except Exception:
                    pass
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def _move_drag_row_to_pointer(self, x_root: int, y_root: int) -> None:
        """Live drag: move the dragged row to the slot under the pointer.
        Works across the recommendations separator and preserves all rows."""
        row = self._drag_row
        if row is None:
            return
        try:
            if not row.winfo_exists():
                return
        except Exception:
            return
        lf = self.listframe
        try:
            x0 = lf.winfo_rootx()
            x1 = x0 + max(1, lf.winfo_width())
            if x_root < x0 - 30 or x_root > x1 + 30:
                return
            y = y_root - lf.winfo_rooty()
        except Exception:
            return
        rows = [w for w in self.row_widgets if w is not row]
        if not rows:
            return
        pos = len(rows)
        for i, w in enumerate(rows):
            try:
                if not w.winfo_exists():
                    continue
                if y < w.winfo_y() + max(1, w.winfo_height()) / 2.0:
                    pos = i
                    break
            except Exception:
                continue
        if getattr(self, "_drag_target_pos", None) == pos:
            return
        self._drag_target_pos = pos
        new_rows = [w for w in self.row_widgets if w is not row]
        new_rows.insert(max(0, min(pos, len(new_rows))), row)
        self.row_widgets = new_rows
        # Move ONLY the dragged row: re-packing the whole list on every
        # mouse move re-lays it out and that is slow with many rows.
        try:
            row.pack_forget()
        except Exception:
            pass
        try:
            if pos < len(new_rows) - 1 and new_rows[pos] is not row:
                row.pack(fill="x", padx=4, pady=2, before=new_rows[pos])
            else:
                row.pack(fill="x", padx=4, pady=2)
        except Exception:
            try:
                row.pack(fill="x", padx=4, pady=2)
            except Exception:
                pass
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self._pin_canvas_bg()

    # ---------- click & drag (captured from root, works on every child) ----------
    def _root_press(self, event) -> None:
        """Single click + drag anywhere in a row.

        event.widget is the REAL widget under the pointer even when the
        binding lives on the root window, so we walk up its parent chain.
        (window containing was unreliable and returned None on Windows.)
        """
        self._drag_row = None
        self._drag_start_xy = None
        self._drag_moved = False
        self._drag_channel = None
        self._drag_target_pos = None
        try:
            widget = event.widget
            row = None
            while widget is not None and widget is not self.root:
                if row is None and getattr(widget, "_is_draggable", False):
                    row = widget
                if getattr(widget, "_is_channel", False):
                    self._drag_channel = widget
                widget = widget.master
            if row is not None and row in self.row_widgets:
                self._drag_row = row
                self._drag_start_xy = (event.x_root, event.y_root)
                try:
                    row._original_bg = row.cget("bg")
                except Exception:
                    row._original_bg = None
        except Exception:
            pass

    def _root_motion(self, event) -> None:
        """Track the drag and move the row visually under the pointer."""
        try:
            if self._drag_row is None or self._drag_start_xy is None:
                return
            dx = abs(event.x_root - self._drag_start_xy[0])
            dy = abs(event.y_root - self._drag_start_xy[1])
            if not self._drag_moved:
                if dx <= 4 and dy <= 4:
                    return
                self._drag_moved = True
                try:
                    self._drag_row.configure(
                        bg=str(self.theme.get("texto", "color_acento",
                                             default="#4a4a4a")),
                        cursor="fleur")
                except Exception:
                    pass
            self._move_drag_row_to_pointer(event.x_root, event.y_root)
        except Exception:
            pass

    def _root_release(self, event) -> None:
        """Release: a click plays/opens the channel; a drag reorders."""
        start_xy = self._drag_start_xy
        row = self._drag_row
        had_motion = self._drag_moved
        channel = getattr(self, "_drag_channel", None)
        self._drag_start_xy = None
        self._drag_row = None
        self._drag_moved = False
        self._drag_channel = None
        self._drag_target_pos = None
        if start_xy is None or row is None:
            return
        dx = abs(event.x_root - start_xy[0])
        dy = abs(event.y_root - start_xy[1])
        try:
            row.configure(cursor="")
            orig = getattr(row, "_original_bg", None)
            if orig:
                row.configure(bg=orig)
        except Exception:
            pass
        # A drag wins over everything: reorder and do not play/open.
        if had_motion or dx > 4 or dy > 4:
            self._sync_list_from_rows()
            try:
                self.status.configure(
                    text="Orden actualizado (arrastrar y soltar)")
            except Exception:
                pass
            return
        # Simple click on a channel name -> open THAT channel.
        if channel is not None:
            cid = str(getattr(channel, "_channel_id", "") or "")
            cname = str(getattr(channel, "_channel_name", "") or "")
            if cid:
                self.open_channel_window(cid, cname)
            else:
                tr = getattr(channel, "_channel_track", None)
                if isinstance(tr, dict):
                    self._open_channel_from_row(tr)
            return
        # Simple click anywhere else on the row -> play immediately.
        track = (getattr(row, "_drag_data", None) or {}).get("track")
        if isinstance(track, dict) and track.get("videoId"):
            self.play_track(track)

    def _queue_move_up_by_vid(self, vid: str) -> None:
        """Move the track with this videoId up one position in the queue."""
        for i, t in enumerate(self.player.queue):
            if t.get("videoId") == vid:
                if i > 0:
                    self.player.queue_move(i, i - 1)
                    self._rebuild_rows_from_full_list()
                break

    def _queue_move_down_by_vid(self, vid: str) -> None:
        """Move the track with this videoId down one position in the queue."""
        for i, t in enumerate(self.player.queue):
            if t.get("videoId") == vid:
                if i < len(self.player.queue) - 1:
                    self.player.queue_move(i, i + 1)
                    self._rebuild_rows_from_full_list()
                break

    def _queue_move_up(self, pos: int) -> None:
        """Move the track at pos up one position in the queue (legacy)."""
        if pos <= 0:
            return
        self.player.queue_move(pos, pos - 1)
        self._rebuild_rows_from_full_list()

    def _queue_move_down(self, pos: int) -> None:
        """Move the track at pos down one position in the queue (legacy)."""
        if pos >= len(self.player.queue) - 1:
            return
        self.player.queue_move(pos, pos + 1)
        self._rebuild_rows_from_full_list()

    def _make_separator_widget(self):
        """Create the recommendations separator bar (visual only)."""
        sep = tk.Frame(self.listframe, bg=self._tint_mid)
        sep.pack(fill="x", padx=4, pady=(10, 2))
        sep._is_continuation = True
        sep._is_separator = True
        lbl = tk.Label(sep,
                       text="━  Recomendaciones — suenan tras la playlist, no se guardan",
                       bg=self._tint_mid,
                       fg=self.theme.data["texto"]["color_subtitulo"],
                       font=(self._font_family(), 9, "bold"),
                       anchor="w")
        lbl.pack(fill="x", padx=8, pady=4)
        lbl._is_continuation = True
        self._cont_separator = sep
        return sep

    def _rebuild_rows_from_full_list(self) -> None:
        """Repinta las filas visibles desde el orden actual, con el
        separador de recomendaciones en su sitio, para que el orden visual
        coincida exactamente con el orden de reproducción (player.queue).
        The list stays VIRTUALIZED: only the visible window is painted.
        Nothing is saved to any playlist/album."""
        try:
            # Limpiar tracker para que se repintén todas las filas
            self._rendered_ids = set()
            self._rendered_keys = []
            self._play_labels = {}
            # Destruir todas las filas actuales
            for w in list(self.row_widgets):
                try:
                    w.destroy()
                except Exception:
                    pass
            self.row_widgets = []
            self._cont_separator = None
            # Eliminar "Show more" si existe
            try:
                if getattr(self, "_more_btn_row", None) is not None:
                    try:
                        self._more_btn_row.destroy()
                    except Exception:
                        pass
                    self._more_btn_row = None
            except Exception:
                pass

            li = self.theme.data["lista"]
            tx = self.theme.data["texto"]
            fam = tx["fuente_familia"]
            n = max(1, len(self.current_list_full or []))
            show_sep = getattr(self, "_pl_continuation_shown", False)
            # Only the visible window is painted (never the whole list).
            tracks = list(getattr(self, "_painted_order", None) or
                          self.current_list or [])
            sep_added = False
            for k, t in enumerate(tracks):
                # The separator goes right before the first recommendation.
                if (show_sep and not sep_added and isinstance(t, dict)
                        and t.get("_continuation")):
                    self._make_separator_widget()
                    self.row_widgets.append(self._cont_separator)
                    sep_added = True
                try:
                    self._build_one_row(k, n, t, li, tx, fam)
                except Exception:
                    pass
            if show_sep and not sep_added:
                # No recommendation on screen yet: the separator closes the
                # visible block, the recommendations come with them.
                self._make_separator_widget()
                self.row_widgets.append(self._cont_separator)

            # Sincronizar current_list con el batch visible
            self.current_list = list(tracks)
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass
            self._pin_canvas_bg()
            self._schedule_retile()
        except Exception:
            pass

    def _add_continuation_after_current(self, track: dict) -> None:
        """Add a continuation track right after the current playing song."""
        try:
            pos = self.player.index + 1 if self.player.index >= 0 else 0
            self.player.queue_insert(track, pos)
            self._rebuild_rows_from_full_list()
            try:
                self.status.configure(text=f"Added '{track.get('title','')}' after current")
            except Exception:
                pass
        except Exception:
            pass

    def _add_continuation_at_position(self, track: dict) -> None:
        """Ask user for position and insert continuation track there."""
        from tkinter import simpledialog
        try:
            pos_str = simpledialog.askinteger(
                "Add to queue",
                f"Insert position (1-{len(self.player.queue) + 1}):",
                initialvalue=1,
                minvalue=1,
                maxvalue=len(self.player.queue) + 1)
            if pos_str is not None:
                pos = pos_str - 1  # convert to 0-based
                self.player.queue_insert(track, pos)
                self._rebuild_rows_from_full_list()
                try:
                    self.status.configure(
                        text=f"Added '{track.get('title','')}' at position {pos_str}")
                except Exception:
                    pass
        except Exception:
            pass

    def _trim_thumb_cache(self, limit: int = 900) -> None:
        """Keep the thumbnail cache small.

        Scrolling through a very long list would otherwise keep thousands
        of images in memory for ever (the app used to die with a long
        playlist). The image stays alive while its row shows it, so
        dropping the oldest entries is safe."""
        try:
            cache = self.thumb_cache
            if len(cache) <= limit:
                return
            for k in list(cache.keys())[:len(cache) - limit]:
                try:
                    cache.pop(k, None)
                except Exception:
                    pass
        except Exception:
            pass

    def _load_thumb_async(self, url: str, label: tk.Label, size: int,
                            play_overlay: bool = False) -> None:
        """SQUARE thumbnail (undistorted cover) + fixed px size.

        play_overlay=True leaves '▶' centered OVER the image (compound=center)
        to show the thumbnail IS the play button.
        """
        if not url:
            return
        # Local display-cover files (custom playlist covers): load from disk.
        try:
            if isinstance(url, str) and os.path.exists(url):
                try:
                    size = max(16, int(size or 44))
                except Exception:
                    size = 44
                key = f"file:{os.path.abspath(url)}|{size}"
                if key in self.thumb_cache:
                    try:
                        label.configure(image=self.thumb_cache[key], text=_ov_txt,
                                        compound=_ov_comp, width=size, height=size,
                                        anchor="center")
                    except Exception:
                        pass
                    return

                def _bg_local(_p=url, _k=key, _s=size):
                    try:
                        from PIL import Image, ImageOps
                        img = Image.open(_p).convert("RGB")
                        try:
                            img = ImageOps.fit(img, (_s, _s), Image.LANCZOS)
                        except Exception:
                            w, h = img.size
                            side = min(w, h)
                            left, top = (w - side) // 2, (h - side) // 2
                            img = img.crop((left, top, left + side, top + side)).resize(
                                (_s, _s), Image.LANCZOS)
                        # Tk images belong to the main thread (see the note in
                        # the remote branch below).
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        raw = buf.getvalue()
                    except Exception:
                        return

                    def _make():
                        try:
                            from PIL import Image as _I, ImageTk
                            photo = ImageTk.PhotoImage(_I.open(BytesIO(raw)))
                            self.thumb_cache[_k] = photo
                            self._trim_thumb_cache()
                            label.configure(image=photo, text=_ov_txt,
                                            compound=_ov_comp, width=_s, height=_s,
                                            anchor="center")
                        except Exception:
                            pass
                    self._call_ui(_make)
                threading.Thread(target=_bg_local, daemon=True).start()
                return
        except Exception:
            pass
        try:
            size = max(16, int(size or 44))
        except Exception:
            size = 44
        # Cache by URL+SIZE (before it was URL only and mixed 44 with 52).
        key = f"{url}|{size}"
        try:
            _ov_txt = "▶" if play_overlay else ""
            _ov_comp = "center" if play_overlay else "none"
        except Exception:
            _ov_txt, _ov_comp = "", "none"
        if key in self.thumb_cache:
            try:
                # width/height in px (with an image set the unit is pixels):
                # without this the width=3 text strangled the image down to 3px.
                label.configure(image=self.thumb_cache[key], text=_ov_txt,
                                compound=_ov_comp, width=size, height=size,
                                anchor="center")
            except Exception:
                pass
            return
        def _bg():
            try:
                import requests
                from PIL import Image, ImageOps
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                img = Image.open(BytesIO(r.content)).convert("RGB")
                # SQUARE cover WITHOUT distortion (before, resize((s,s)) squeezed
                # 16:9/4:3 covers and they looked "too narrow").
                try:
                    img = ImageOps.fit(img, (size, size), Image.LANCZOS)
                except Exception:
                    # Manual fallback: centered crop to square aspect
                    w, h = img.size
                    side = min(w, h)
                    left, top = (w - side) // 2, (h - side) // 2
                    img = img.crop((left, top, left + side, top + side)).resize(
                        (size, size), Image.LANCZOS)
                # The Tk image MUST be built on the main thread: creating it
                # here raised "main thread is not in main loop" and every
                # thumbnail silently stayed as the placeholder glyph.
                buf = BytesIO()
                img.save(buf, format="PNG")
                raw = buf.getvalue()
            except Exception:
                return

            def _make():
                try:
                    from PIL import Image as _I, ImageTk
                    photo = ImageTk.PhotoImage(_I.open(BytesIO(raw)))
                    self.thumb_cache[key] = photo
                    # Compat: also store by bare URL for old readers
                    try:
                        self.thumb_cache.setdefault(url, photo)
                    except Exception:
                        pass
                    self._trim_thumb_cache()
                    label.configure(image=photo, text=_ov_txt,
                                    compound=_ov_comp, width=size, height=size,
                                    anchor="center")
                except Exception:
                    pass
                # The row grows when the thumbnail arrives and the background
                # tile ends up small (white frame): re-sample with debounce.
                if play_overlay:
                    try:
                        self._schedule_retile()
                    except Exception:
                        pass

            self._call_ui(_make)
        threading.Thread(target=_bg, daemon=True).start()

    # ---------- actions ----------
    def _enter_queue_view(self) -> None:
        """Navigate to the queue WITHOUT destroying the playlist list.

        play_track() has just loaded current_list_full (playlist + its
        recommendations) into player.queue and the rows for that exact list
        are already on screen. Re-rendering here used to reset the
        continuation and append a second copy of the recommendations.
        """
        try:
            self.current_section = "cola"
            full = list(self.player.queue)
            self.current_list_full = full
            # Keep the list virtualized: the visible window + the
            # recommendations are painted, never the whole queue.
            self._base_window = max(1, min(self._base_window or self._batch_size(),
                                           len(self._base_tracks())))
            self.current_list = self._window_tracks()
            self.visible_count = len(self.current_list)
            self.list_title.configure(
                text=f"Current queue ({len(self.current_list)}/{len(full)})")
            # Rows from the list we were just viewing are still valid. Only
            # build them when there is nothing on screen (first navigation).
            if not self.row_widgets:
                self.render_list()
            self._paint_section_background()
        except Exception:
            self.show_section("cola")

    def play_track(self, track: dict) -> None:
        # Channel / artist rows are not playable: open the channel window.
        if t_kind := str(track.get("kind", "") or ""):
            if t_kind in ("channel", "artist") and track.get("channelId"):
                self.open_channel_window(str(track["channelId"]),
                                         str(track.get("title", "") or ""))
                return
        if not track.get("videoId"):
            return
        # CARGAR TODA LA LISTA ACTUAL EN LA COLA empezando desde esta canción,
        # y navegar a la sección cola. Así el usuario puede reordenar arrastrando.
        try:
            source = getattr(self, "current_list_full", None) or self.current_list
            # Solo canciones con videoId
            queue_tracks = [t for t in source if isinstance(t, dict) and t.get("videoId")]
            ids = [t.get("videoId") for t in queue_tracks]
            if track.get("videoId") in ids and queue_tracks:
                # Prefer the exact object clicked (works with duplicate songs);
                # fall back to the first matching videoId.
                try:
                    start_pos = next(i for i, t in enumerate(queue_tracks)
                                     if t is track)
                except StopIteration:
                    start_pos = ids.index(track["videoId"])
                # Preserve the recommendation separator ONLY if it belongs to
                # the list currently painted on screen.
                sep = getattr(self, "_cont_separator", None)
                sep_ok = False
                try:
                    sep_ok = (sep is not None and sep.winfo_exists()
                              and sep in self.row_widgets)
                except Exception:
                    sep_ok = False
                if not sep_ok:
                    if any(isinstance(t, dict) and t.get("_continuation")
                           for t in queue_tracks):
                        # The recommendations are already in the queue; keep
                        # them and restore the separator position.
                        self._pl_continuation_shown = True
                        self._pl_continuation_rendered = True
                        base = int(getattr(self, "_playlist_base_count", 0) or 0)
                        if not (0 <= base < len(queue_tracks)):
                            base = 0
                            for t in queue_tracks:
                                if isinstance(t, dict) and t.get("_continuation"):
                                    break
                                base += 1
                            self._playlist_base_count = base
                    else:
                        self._pl_continuation_shown = False
                        self._pl_continuation_rendered = False
                        self._playlist_base_count = 0
                        self._continuation_tracks = []
                        self._cont_separator = None
                self.player.set_queue(queue_tracks, start=start_pos)
                self.status.configure(text=f"Cola cargada: {len(queue_tracks)} canciones")
                # Navegar a la sección cola para que el usuario pueda reordenar
                self._enter_queue_view()
                return
        except Exception:
            pass
        # Fallback: solo esta canción
        self.player.set_queue([track], start=0)
        self._enter_queue_view()

    def add_to_queue(self, track: dict) -> None:
        if track.get("videoId"):
            self.player.queue_add(track)
            self.status.configure(text=f"Added to the queue: {track.get('title','')}")

    def _is_fav(self, track) -> bool:
        """Is it in YT Music Liked songs? (liked cache, no local data)."""
        try:
            if not isinstance(track, dict) or not track.get("videoId"):
                return False
            if str(track.get("likeStatus", "") or "").upper() == "LIKE":
                return True
            return str(track.get("videoId", "")) in (getattr(self, "_liked_ids", set()) or set())
        except Exception:
            return False

    def toggle_fav(self, track: dict) -> None:
        """♥/♡ = YT MUSIC Like (adds to 'Liked songs')."""
        if not isinstance(track, dict) or not track.get("videoId"):
            return
        if not self.client.authenticated:
            self.status.configure(text="Not signed in: link your account to Like on YT Music.")
            return
        vid = track["videoId"]
        liked = self._is_fav(track)
        self.status.configure(text="Removing Like..." if liked else "Saving Like to YT Music...")
        def _bg():
            ok = self.client.like_song(vid, not liked)
            def _ui():
                if ok:
                    try:
                        if liked:
                            self._liked_ids.discard(vid)
                        else:
                            self._liked_ids.add(vid)
                    except Exception:
                        pass
                    try:
                        track["likeStatus"] = "INDIFFERENT" if liked else "LIKE"
                    except Exception:
                        pass
                    self.status.configure(
                        text="Removed from YT Music Liked songs" if liked
                        else "Added to YT Music Liked songs ♥")
                else:
                    self.status.configure(
                        text=f"Failed: {(self.client.last_error or '')[:120]}")
                try:
                    self._refresh_control_icons()
                except Exception:
                    pass
                if self.current_section == "favoritas":
                    self.show_favorites()
                else:
                    self.render_list(keep_scroll=True)
            try:
                self._call_ui(_ui)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def toggle_fav_current(self) -> None:
        if self.player.current:
            self.toggle_fav(self.player.current)

    def toggle_shuffle(self) -> None:
        self.player.set_shuffle(not self.player.shuffle)
        self._refresh_control_icons()
        self.status.configure(text=f"Shuffle: {'ON' if self.player.shuffle else 'OFF'}")

    def cycle_loop(self) -> None:
        m = self.player.cycle_loop()
        self._refresh_control_icons()
        self.status.configure(text=f"Loop: {m}")
        # When loop is turned OFF in a playlist or the queue, show the
        # continuation. When loop is turned back ON, hide it.
        # Use pl_kind (set by open_playlist) not current_section, because
        # playlists opened from search/URL leave current_section as "buscar".
        try:
            is_playlist_ctx = bool(getattr(self, "current_playlist_id", ""))
            is_queue_ctx = getattr(self, "current_section", "") == "cola"
            if is_playlist_ctx or is_queue_ctx:
                if m == "off":
                    self._show_playlist_continuation()
                else:
                    self._clear_playlist_continuation()
        except Exception:
            pass

    def create_yt_playlist_ui(self) -> None:
        """Sidebar '+ New YT playlist' button (no local lists)."""
        from tkinter import simpledialog
        if not self.client.authenticated:
            self.status.configure(text="Not signed in: link your account to create YT Music playlists.")
            return
        name = simpledialog.askstring("New YouTube playlist", "Name:")
        if not name or not name.strip():
            return
        self.status.configure(text=f"Creating '{name.strip()}'...")
        def _bg():
            pid = self.client.create_playlist(name.strip(), [])
            if pid:
                self._call_ui(self.refresh_library_list)
                self._call_ui(self.status.configure, text=f"Playlist '{name.strip()}' creada ✔")
                self._call_ui(self.show_section, "playlists")
            else:
                self._call_ui(self.status.configure,
                              text=f"No se creo: {(self.client.last_error or '')[:120]}")
        threading.Thread(target=_bg, daemon=True).start()

    def create_local_playlist(self) -> None:
        # Compat: it used to create LOCAL lists (removed). Now it creates YT ones.
        try:
            return self.create_yt_playlist_ui()
        except Exception:
            pass

    def open_local(self, name: str) -> None:
        # Compat: no local lists anymore. Go to YT playlists.
        try:
            self.show_section("playlists")
        except Exception:
            pass

    def _add_track_to_local(self, name: str, track: dict) -> None:
        # Compat: no local lists (does nothing).
        try:
            self.status.configure(text="Local lists were removed: use YT Music playlists.")
        except Exception:
            pass

    # ----- gestion nativa de playlists -----
    def remove_track_current(self, track: dict) -> None:
        """Remove a song from the open YT playlist (own ones only)."""
        if self.pl_kind == "yt" and self.pl_id:
            if not track.get("setVideoId"):
                self.status.configure(text="Only removable from your own playlists")
                return
            self.status.configure(text="Removing song...")
            pid, title = self.pl_id, self.pl_title
            def _bg():
                ok = self.client.remove_from_playlist(pid, [track])
                if ok:
                    self._call_ui(self.open_playlist, pid, title)
                    self._call_ui(self.status.configure, text="Song removed ✔")
                else:
                    self._call_ui(self.status.configure,
                                  text=f"No se pudo quitar: {self.client.last_error[:120]}")
            threading.Thread(target=_bg, daemon=True).start()

    def delete_yt_playlist(self, pid: str, title: str) -> None:
        if not messagebox.askyesno("Delete playlist", f"Delete '{title}' from YouTube?\nThis cannot be undone."):
            return
        self.status.configure(text=f"Borrando '{title}'...")
        def _bg():
            ok = self.client.delete_playlist(pid)
            if ok:
                self._call_ui(self.show_section, "playlists")
                self._call_ui(self.refresh_library_list)
                self._call_ui(self.status.configure, text=f"Playlist borrada ✔")
            else:
                self._call_ui(self.status.configure,
                              text=f"No se pudo borrar: {self.client.last_error[:120]}")
        threading.Thread(target=_bg, daemon=True).start()

    def rename_yt_playlist(self, pid: str, title: str) -> None:
        from tkinter import simpledialog
        clean = title.replace("♪ ", "", 1) if title.startswith("♪ ") else title
        new = simpledialog.askstring("Rename playlist", "New name:", initialvalue=clean)
        if not new or not new.strip():
            return
        self.status.configure(text="Renaming...")
        def _bg():
            ok = self.client.rename_playlist(pid, new.strip())
            if ok:
                self._call_ui(self.show_section, "playlists")
                self._call_ui(self.refresh_library_list)
                self._call_ui(self.status.configure, text="Renamed ✔")
            else:
                self._call_ui(self.status.configure,
                              text=f"No se pudo renombrar: {self.client.last_error[:120]}")
        threading.Thread(target=_bg, daemon=True).start()

    def delete_local_list(self, name: str) -> None:
        # Compat: no local lists.
        try:
            self.status.configure(text="Local lists were removed: use YT Music playlists.")
        except Exception:
            pass

    def rename_local_list(self, name: str) -> None:
        # Compat: no local lists.
        try:
            self.status.configure(text="Local lists were removed: use YT Music playlists.")
        except Exception:
            pass

    def save_to_playlist_dialog(self, track: dict) -> None:
        """Save a song to YOUTUBE playlists + Like (no local data)."""
        if not track.get("videoId"):
            return
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title(f"Save: {(track.get('title') or '')[:40]}")
        win.geometry("440x360")
        tx = self.theme.data["texto"]
        li = self.theme.data["lista"]
        try:
            win.configure(bg=li["color_fondo"])
        except Exception:
            pass
        tk.Label(win, text="♥ YouTube Like",
                 font=(tx["fuente_familia"], 11, "bold")).pack(pady=(8, 2))
        tk.Button(win, text="♥ Like it",
                  command=lambda: self._like_bg(track, win)).pack(pady=2)
        tk.Label(win, text="Your YouTube playlists. Pick one:",
                 font=(tx["fuente_familia"], 11, "bold")).pack(pady=(10, 2))
        self._yt_save_list = tk.Listbox(win, height=7)
        self._yt_save_list.pack(fill="x", padx=10)
        self._yt_save_list.bind("<Double-Button-1>",
                                lambda e: self._save_yt_bg(track, win))
        self._yt_save_ids: list[str] = []
        btnrow = tk.Frame(win)
        btnrow.pack(pady=4)
        tk.Button(btnrow, text="Save there",
                  command=lambda: self._save_yt_bg(track, win)).pack(side="left", padx=4)
        tk.Button(btnrow, text="Reload",
                  command=lambda: self._reload_yt_save_list()).pack(side="left", padx=4)
        tk.Button(btnrow, text="+ New YT playlist",
                  command=lambda: self._create_yt_bg(track, win)).pack(side="left", padx=4)
        self._reload_yt_save_list()

    def _reload_yt_save_list(self) -> None:
        def _bg():
            pls = self.client.get_library_playlists(limit=50)
            self._yt_pl_cache = pls
            rows = []
            for p in pls:
                cnt = p.get("count", "")
                rows.append(f"{p.get('title', '?')} ({cnt})" if cnt != "" else p.get("title", "?"))
            self._call_ui(self._fill_yt_save_list, rows, [p.get("id", "") for p in pls])
        threading.Thread(target=_bg, daemon=True).start()

    def _fill_yt_save_list(self, titles, ids=None) -> None:
        try:
            self._yt_save_list.delete(0, "end")
            self._yt_save_ids = list(ids or [])
            for t in titles:
                self._yt_save_list.insert("end", t)
            if not titles:
                self._yt_save_list.insert("end", "(no access: check your session)")
                self._yt_save_ids = [""]
        except Exception:
            pass

    def _save_yt_bg(self, track, win) -> None:
        try:
            sel = self._yt_save_list.curselection()
            if not sel:
                self.status.configure(text="Pick a playlist from the LIST first (click)")
                return
            idx = sel[0]
            ids = getattr(self, "_yt_save_ids", [])
            pid = ids[idx] if idx < len(ids) else ""
            title = self._yt_save_list.get(idx)
            if not pid:
                self.status.configure(text="Could not identify the playlist")
                return
            self.status.configure(text=f"Saving to '{title}'...")
            def _bg():
                ok = self.client.add_to_playlist(pid, [track["videoId"]])
                msg = f"Saved to '{title}' ✔" if ok else f"Could not save: {self.client.last_error[:100]}"
                try:
                    self._call_ui(lambda: self.status.configure(text=msg))
                    self._call_ui(win.destroy)
                except Exception:
                    pass
            threading.Thread(target=_bg, daemon=True).start()
        except Exception:
            pass

    def _create_yt_bg(self, track, win) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring("New YouTube playlist", "Name:")
        if not name:
            return
        self.status.configure(text=f"Creando '{name}'...")
        def _bg():
            pid = self.client.create_playlist(name, [track["videoId"]])
            msg = f"Playlist '{name}' creada ✔" if pid else f"No se creo: {self.client.last_error[:100]}"
            try:
                self._call_ui(lambda: self.status.configure(text=msg))
                self._call_ui(self._reload_yt_save_list)
                self._call_ui(self.refresh_library_list)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _like_bg(self, track, win) -> None:
        def _bg():
            ok = self.client.like_song(track["videoId"], True)
            msg = "♥ Like saved to YT Music" if ok else f"Failed: {self.client.last_error[:100]}"
            try:
                self._call_ui(lambda: self.status.configure(text=msg))
                if ok:
                    try:
                        self._liked_ids.add(track["videoId"])
                    except Exception:
                        pass
                    self._call_ui(self._refresh_control_icons)
                    self._call_ui(self.render_list, True)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _save_local_from_dialog(self, track, win) -> None:
        # Compat: no local lists.
        try:
            self.status.configure(text="Local lists were removed: use YT Music playlists.")
        except Exception:
            pass

    def _create_local_from_dialog(self, track, win) -> None:
        # Compat: no local lists.
        try:
            self.status.configure(text="Local lists were removed: use YT Music playlists.")
        except Exception:
            pass

    # ---------- player callbacks ----------
    def _on_track_change_ui(self, track) -> None:
        try:
            self._call_ui(self._update_song_ui, dict(track or {}))
            # Loop OFF + playlist/album: when a recommended (continuation)
            # song starts playing, move its row above the separator so played
            # recommendations accumulate above it. Session only, never saved.
            tr = dict(track or {})
            if tr.get("_continuation") and getattr(self, "_pl_continuation_shown", False):
                self._call_ui(self._promote_continuation_row, tr)
        except Exception:
            pass

    # ---------- per-song map (local-cache.json) ----------
    @staticmethod
    def _songmap_default() -> str:
        """Where the per-song data lives (local-cache.json).

        Inside the project so a clone works out of the box; you can point it
        anywhere you like in Settings > Last.fm.
        """
        return os.path.join("config", "local-cache.json")

    def _load_songmap(self) -> bool:
        """Load the per-song map into memory (lossless raw kept for save)."""
        try:
            p = (getattr(self.lastfm, "songmap_path", "") or "").strip()
            if not p:
                try:
                    _dflt = self._songmap_default()
                    if _dflt and os.path.exists(_dflt):
                        p = _dflt
                        self.lastfm.songmap_path = p
                        self.lastfm.save()
                except Exception:
                    pass
            if p and os.path.exists(p):
                with open(p, "r", encoding="utf-8-sig") as f:
                    data = json.load(f) or {}
                if isinstance(data, dict):
                    self._songmap_raw = data
                    self._songmap = {str(k): (v if isinstance(v, dict) else {})
                                     for k, v in data.items()}
                    try:
                        self._songmap_mtime = os.path.getmtime(p)
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        self._songmap = None
        self._songmap_raw = {}
        return False

    def _save_songmap(self) -> bool:
        """Write the map back (other entries + extra keys untouched)."""
        try:
            p = (getattr(self.lastfm, "songmap_path", "") or "").strip()
            if not p:
                return False
            os.makedirs(os.path.dirname(os.path.abspath(p)) or ".", exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._songmap_raw, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _save_song_override(self, vid: str, new_values: dict) -> tuple[bool, str]:
        """Persist per-song data into local-cache.json (THE store).

        Blank values clear that field (falls back to the song default).
        Generates the file if none is loaded. Returns (ok, message)."""
        try:
            if not vid:
                return False, "No song."
            try:
                newv = {f: str((new_values or {}).get(f, "") or "")
                        for f in ("track", "artist", "album")}
            except Exception:
                return False, "Bad values."
            if not isinstance(getattr(self, "_songmap", None), dict):
                self._songmap = {}
                self._songmap_raw = {}
            try:
                _old = (self._songmap or {}).get(str(vid)) or {}
                _old_n = {f: str(_old.get(f, "") or "") for f in ("track", "artist", "album")}
            except Exception:
                _old_n = {"track": "", "artist": "", "album": ""}
            if all(newv.get(f, "") == _old_n.get(f, "") for f in ("track", "artist", "album")):
                return False, "No changes: nothing to save."
            try:
                _entry = dict(self._songmap_raw.get(str(vid))
                              if isinstance(self._songmap_raw.get(str(vid)), dict) else {})
                for f in ("track", "artist", "album"):
                    _entry[f] = newv.get(f, "") or None
                self._songmap_raw[str(vid)] = _entry
                try:
                    self._songmap[str(vid)] = _entry
                except Exception:
                    pass
            except Exception as e:
                return False, f"Entry error: {e}"
            # No file yet? Generate it now.
            try:
                _p = (getattr(self.lastfm, "songmap_path", "") or "").strip()
            except Exception:
                _p = ""
            if not _p:
                try:
                    _p = os.path.join("config", "local-cache.json")
                    self.lastfm.songmap_path = _p
                    self.lastfm.save()
                except Exception:
                    pass
            if self._save_songmap():
                try:
                    self.render_list(keep_scroll=True)
                    self._update_song_ui(dict(getattr(self.player, "current", None) or {}))
                except Exception:
                    pass
                return True, "Song data saved ✔ (local-cache.json)"
            return False, "Could not save local-cache.json."
        except Exception as e:
            return False, f"Save error: {e}"

    def _remove_song_override(self, vid: str, silent: bool = False) -> tuple[bool, str]:
        """Drop a song's entry from local-cache.json (back to default)."""
        try:
            if not vid:
                return False, "No song."
            if not isinstance(getattr(self, "_songmap", None), dict) or str(vid) not in (self._songmap or {}):
                return False, "That song has no saved data."
            try:
                self._songmap.pop(str(vid), None)
                self._songmap_raw.pop(str(vid), None)
            except Exception:
                pass
            if not self._save_songmap():
                return False, "Could not save local-cache.json."
            if not silent:
                try:
                    self.render_list(keep_scroll=True)
                    self._update_song_ui(dict(getattr(self.player, "current", None) or {}))
                except Exception:
                    pass
            return True, "Song data removed ✔ (back to default)"
        except Exception as e:
            return False, f"Remove error: {e}"

    def _songmap_maybe_reload(self) -> bool:
        """Reload local-cache.json if it changed on disk."""
        try:
            p = (getattr(self.lastfm, "songmap_path", "") or "").strip()
            if not p or not os.path.exists(p):
                return False
            try:
                mt = os.path.getmtime(p)
            except Exception:
                return False
            if mt > float(getattr(self, "_songmap_mtime", 0) or 0) + 0.5:
                if self._load_songmap_file_quiet(p):
                    try:
                        self.render_list(keep_scroll=True)
                        self._update_song_ui(dict(getattr(self.player, "current", None) or {}))
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        return False

    def _load_songmap_file_quiet(self, path: str) -> bool:
        try:
            import json as _js
            with open(path, "r", encoding="utf-8-sig") as f:
                data = _js.load(f) or {}
            if not isinstance(data, dict):
                return False
            self._songmap_raw = data
            self._songmap = {str(k): (v if isinstance(v, dict) else {})
                             for k, v in data.items()}
            try:
                self._songmap_mtime = os.path.getmtime(path)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _load_songmap_file(self, path: str) -> bool:
        """Settings loader: this local-cache.json becomes THE per-song store."""
        try:
            if not path or not os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f) or {}
            if not isinstance(data, dict):
                try:
                    self.status.configure(text="That file is not a {videoId: {...}} map.")
                except Exception:
                    pass
                return False
            self._songmap_raw = data
            self._songmap = {str(k): (v if isinstance(v, dict) else {})
                             for k, v in data.items()}
            try:
                self.lastfm.songmap_path = path
                self.lastfm.save()
            except Exception:
                pass
            try:
                self.render_list(keep_scroll=True)
                self._update_song_ui(dict(getattr(self.player, "current", None) or {}))
            except Exception:
                pass
            try:
                n = len(self._songmap or {})
                cur = dict(getattr(self.player, "current", None) or {})
                vid = str(cur.get("videoId", "") or "")
                hit = "current song mapped ✔" if vid and vid in (self._songmap or {}) else "current song not mapped"
                self.status.configure(text=f"Song map loaded ✔ ({n} songs, {os.path.basename(path)}) — {hit}")
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _pick_songmap_file_ui(self) -> None:
        """Settings loader: pick a local-cache.json as THE per-song store."""
        try:
            p = filedialog.askopenfilename(
                title="Load local-cache.json (per-song data)",
                initialdir=os.path.dirname(self._songmap_default()),
                filetypes=[("JSON", "*.json"), ("All", "*.*")])
        except Exception:
            p = ""
        if p:
            self._load_songmap_file(p)

    def _export_songmap_file_ui(self) -> None:
        """Settings exporter: save a copy of the per-song store elsewhere."""
        if not isinstance(getattr(self, "_songmap_raw", None), dict):
            try:
                self.status.configure(text="No song map loaded.")
            except Exception:
                pass
            return
        try:
            p = filedialog.asksaveasfilename(title="Export local-cache.json",
                                             defaultextension=".json",
                                             initialfile="local-cache.json",
                                             filetypes=[("JSON", "*.json")])
        except Exception:
            p = ""
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._songmap_raw, f, ensure_ascii=False, indent=2)
            try:
                self.status.configure(text=f"Song map exported ✔ ({p})")
            except Exception:
                pass
        except Exception as e:
            try:
                self.status.configure(text=f"Export failed: {e}")
            except Exception:
                pass

    def _meta_edited(self, track: dict | None) -> dict:
        """Edited {track, artist, album, albumArtist} for display+scrobble.

        Single store: the per-song map (local-cache.json). Edited song ->
        its mapped values; anything else -> the raw song data (default).
        """
        try:
            t = track or {}
            cur = {"track": str(t.get("title", "") or ""),
                   "artist": str(t.get("artist", "") or ""),
                   "album": str(t.get("album", "") or ""),
                   "albumArtist": str(t.get("albumArtist", "") or "")}
        except Exception:
            cur = {"track": "", "artist": "", "album": "", "albumArtist": ""}
            t = {}
        try:
            vid = str((t or {}).get("videoId", "") or "")
            if vid:
                _sm = getattr(self, "_songmap", None) or {}
                _ent = _sm.get(vid)
                if isinstance(_ent, dict):
                    for f in ("track", "artist", "album", "albumArtist"):
                        try:
                            _v = _ent.get(f)
                            if _v is not None and str(_v) != "":
                                cur[f] = str(_v)
                        except Exception:
                            pass
        except Exception:
            pass
        return cur

    def _lastfm_np_bg(self, track: dict) -> None:
        """Now-playing ping (thread)."""
        try:
            if not (self.lastfm.linked and self.lastfm.scrobble_enabled):
                return
            ed = self._meta_edited(track)
            if not ed.get("artist") or not ed.get("track"):
                return
            try:
                dur = str(int(float((track or {}).get("duration_sec") or 0) or 0) or "")
            except Exception:
                dur = ""
            self.lastfm.update_now_playing(ed["artist"], ed["track"],
                                           album=ed.get("album", ""), duration=dur)
        except Exception:
            pass

    def _lastfm_scrobble_bg(self, track: dict, ts: int) -> None:
        """Scrobble one play (thread)."""
        try:
            if not (self.lastfm.linked and self.lastfm.scrobble_enabled):
                return
            ed = self._meta_edited(track)
            if not ed.get("artist") or not ed.get("track"):
                return
            ok = self.lastfm.scrobble(ed["artist"], ed["track"], int(ts or 0),
                                      album=ed.get("album", ""))
            try:
                self._call_ui(self.status.configure,
                              text=("Scrobbled to Last.fm ✔" if ok
                                    else f"Last.fm queued ({self.lastfm.last_error[:80]})"))
            except Exception:
                pass
        except Exception:
            pass

    def _update_song_ui(self, track: dict) -> None:
        ed = self._meta_edited(track)
        title = ed.get("track") or (track.get("title", "?") if track else "Nothing playing")
        artist = ed.get("artist") or (track.get("artist", "") if track else "")
        self.song_label.configure(text=f"{title} — {artist}" if artist else title)
        # How many times this song was played on Last.fm (edited data), shown
        # in the player bar. It arrives from the network a moment later.
        try:
            self._set_playcount_text("")
            vid = str((track or {}).get("videoId", "") or "")
            if vid:
                self.refresh_play_count(vid)
        except Exception:
            pass
        # Scrobble bookkeeping: new song = new timestamp, not scrobbled yet.
        try:
            import time as _tt
            self._play_start_ts = int(_tt.time())
            self._scrobble_key = ""
        except Exception:
            pass
        try:
            threading.Thread(target=self._lastfm_np_bg, args=(dict(track or {}),),
                             daemon=True).start()
        except Exception:
            pass
        # Window title: show playlist name + position when playing from a playlist.
        try:
            base_title = self.theme.data["ventana"]["titulo"]
            if self.pl_kind == "yt" and self.pl_title:
                idx = self.player.index + 1 if self.player.index >= 0 else 1
                total = len(self.player.queue)
                self.root.title(f"{base_title} — Playlist: {self.pl_title} ({idx}/{total})")
            else:
                self.root.title(base_title)
        except Exception:
            pass
        if track and track.get("thumbnail"):
            self._load_thumb_async(track["thumbnail"], self.thumb_label, 52)
        else:
            try:
                # Back to text mode: width in chars (with an image it was px).
                self.thumb_label.configure(image="", text="♪", compound="none",
                                           width=6, height=0, anchor="center")
            except Exception:
                pass
        self._refresh_control_icons()
        # NOTE: we do NOT call render_list() here. That used to destroy every
        # row on each song change: thumbnails restarted, the whole list
        # blinked, and on long playlists it made rows vanish/reload forever.
        # The active row keeps its color via _build_one_row's active flag.
        try:
            self._refresh_video_panel()
        except Exception:
            pass

    def _on_state_change_ui(self, state, track) -> None:
        try:
            self._call_ui(self._refresh_control_icons)
            online = getattr(self.player, "_active", "stream") == "stream"
            if state == "playing":
                msg = "Playing online" if online else "Playing (downloaded)"
                self._call_ui(lambda m=msg: self.status.configure(text=m))
            elif state == "loading":
                self._call_ui(lambda: self.status.configure(text="Connecting... (online)"))
            elif state == "paused":
                self._call_ui(lambda: self.status.configure(text="Paused"))
            elif state == "stopped":
                # Show error if the track failed to play
                err = getattr(self.player, "last_error", "") or ""
                if err and "stopped" not in err.lower():
                    self._call_ui(lambda e=err: self.status.configure(text=f"Error: {e}[:140]"))
                else:
                    self._call_ui(lambda: self.status.configure(text="Stopped"))
        except Exception:
            pass

    def _on_queue_end_continuation(self) -> bool:
        """Called by PlayerEngine when the queue ends.
        Adds continuation tracks to the queue so playback continues.
        Returns True if more tracks were added."""
        try:
            if self._continuation_tracks:
                # Add continuation tracks AFTER the current playing position
                pos = self.player.index + 1 if self.player.index >= 0 else len(self.player.queue)
                for t in self._continuation_tracks:
                    self.player.queue_insert(t, pos)
                    pos += 1
                self._continuation_tracks = []
                try:
                    self.status.configure(
                        text=f"Continuing with {len(self._continuation_tracks)} recommended tracks")
                except Exception:
                    pass
                return True
        except Exception:
            pass
        return False

    def _on_progress_press(self, event=None) -> None:
        """Clicking the bar = jump to that time (before, only dragging
        the slider worked). Places the value where clicked; the
        real seek happens in _on_seek_release on release."""
        self._seeking = True
        try:
            dur = float(self.player.duration_sec or 0)
            if dur > 0 and event is not None:
                try:
                    w = max(1, int(self.progress.winfo_width() or 1))
                except Exception:
                    w = 1
                try:
                    frac = min(1.0, max(0.0, float(event.x) / float(w)))
                except Exception:
                    return
                try:
                    self.progress.set(frac * 100.0)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_seek_release(self, event=None) -> None:
        try:
            val = float(self.progress.get())
            dur = float(self.player.duration_sec or 0)
            if dur > 0:
                self.player.seek(val / 100.0 * dur)
                # The worker detects the jump on its own (<0.5s) and relaunches with
                # -ss, but forcing restart pins video to audio.
                try:
                    self._video_video_id = ""
                    self._refresh_video_panel()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._seeking = False

    def _initial_heal(self) -> None:
        """At startup: if the source is the browser and there is no session, try
        healing it silently (automation profile)."""
        try:
            if (getattr(self.client, "session_source", "archivo") == "navegador"
                    and not self.client.authenticated):
                threading.Thread(target=self._initial_heal_bg, daemon=True).start()
        except Exception:
            pass

    def _initial_heal_bg(self) -> None:
        try:
            if self.client._maybe_heal_session():
                self._call_ui(self._after_cookies_changed)
        except Exception:
            pass

    def _cookies_mtime_now(self) -> float:
        try:
            return os.path.getmtime(self.client.cookies_json_path)
        except Exception:
            return -1.0

    def _watch_cookies_file(self) -> None:
        """If the cookies JSON changed on disk, reload the session alone."""
        try:
            mt = self._cookies_mtime_now()
            if mt != getattr(self, "_cookies_mtime", mt):
                self._cookies_mtime = mt
                threading.Thread(target=self._auto_reload_cookies, daemon=True).start()
        except Exception:
            pass

    def _auto_reload_cookies(self) -> None:
        try:
            self.client.reload_cookies()
            self.client._lib_cache = None
        except Exception:
            pass
        self._call_ui(self._after_cookies_changed)

    def _after_cookies_changed(self) -> None:
        try:
            self.account_label.configure(text=self.client.account_label)
            self.status.configure(text=f"Session updated: {self.client.account_label}")
            self.refresh_library_list()
        except Exception:
            pass

    def _tick(self) -> None:
        try:
            pos = self.player.get_position()
            dur = float(self.player.duration_sec or 0)
            self.time_a.configure(text=_fmt_time(pos))
            self.time_b.configure(text=_fmt_time(dur))
            if dur > 0 and not self._seeking:
                try:
                    self.progress.configure(to=100)
                    self.progress.set(pos / dur * 100.0)
                except Exception:
                    pass
        except Exception:
            pass
        # Overlays as an app layer: order only when needed and we are
        # foreground (no blind lifts flickering over other programs).
        try:
            self._ensure_overlay_topmost()
        except Exception:
            pass
        # Mini-video watchdog: if visible, playing and frameless for >8 s,
        # the worker died silently -> relaunch (touch nothing else).
        try:
            import time as _t
            _last = float(getattr(self, "_video_last_frame", 0.0) or 0.0)
            if (_last > 0.0
                    and getattr(self, "_video_running", False)
                    and getattr(self.player, "state", "") == "playing"
                    and getattr(self.player, "current", None)
                    and bool(self.theme.get("video_panel", "visible", default=True))
                    and getattr(self, "_video_panel", None) is not None
                    and _t.time() - _last > 8.0):
                try:
                    self._video_video_id = ""
                except Exception:
                    pass
                try:
                    self._refresh_video_panel()
                except Exception:
                    pass
        except Exception:
            pass
        # HD re-ramp: the bot-wall varies over time. While an HD request is
        # served below what was asked, retry the upgrade every 90 s so HD
        # engages on its own the moment YouTube allows it (no user action).
        try:
            import time as _t2
            _cur = getattr(getattr(self, "player", None), "current", None) or {}
            _vid = str(_cur.get("videoId", "") or "")
            _src = getattr(self, "_video_src", None) or {}
            if (_vid and _src.get("vid") == _vid
                    and getattr(self.player, "state", "") == "playing"
                    and getattr(self, "_video_running", False)):
                try:
                    _asked = int(_src.get("asked", 0) or 0)
                    _got = int(_src.get("h", 0) or 0)
                except Exception:
                    _asked, _got = 0, 0
                if _asked >= 720 and _got < _asked - 100:
                    try:
                        _ts = getattr(self, "_hd_try_ts", None) or {}
                    except Exception:
                        _ts = {}
                    try:
                        _last_try = float(_ts.get(_vid, 0) or 0)
                    except Exception:
                        _last_try = 0.0
                    if _t2.time() - _last_try > 90:
                        try:
                            _ts[_vid] = _t2.time()
                            self._hd_try_ts = _ts
                        except Exception:
                            pass
                        try:
                            import threading as _th
                            _th.Thread(target=self._hd_ramp_bg,
                                       args=(_vid, int(getattr(self, "_video_pw", 0) or 640),
                                             int(getattr(self, "_video_ph", 0) or 360)),
                                       daemon=True).start()
                        except Exception:
                            pass
        except Exception:
            pass
        # Last.fm scrobble: standard rule (>30s AND (half the song OR 4 min)).
        try:
            _tr = getattr(getattr(self, "player", None), "current", None) or {}
            _vid = str(_tr.get("videoId", "") or "")
            if (_vid and getattr(self.player, "state", "") == "playing"
                    and self.lastfm.linked and self.lastfm.scrobble_enabled):
                try:
                    _idx = int(getattr(self.player, "index", -1) or -1)
                except Exception:
                    _idx = -1
                _key = f"{_vid}|{_idx}"
                if _key != getattr(self, "_scrobble_key", ""):
                    try:
                        _pos = float(self.player.get_position() or 0)
                        _dur = float(getattr(self.player, "duration_sec", 0) or 0)
                    except Exception:
                        _pos, _dur = 0.0, 0.0
                    if _pos > 30 and (_dur <= 0 or _pos > _dur / 2.0 or _pos > 240):
                        self._scrobble_key = _key
                        try:
                            _ts = int(getattr(self, "_play_start_ts", 0) or 0)
                        except Exception:
                            _ts = 0
                        try:
                            import time as _tt3
                            _ts = _ts or int(_tt3.time())
                        except Exception:
                            pass
                        threading.Thread(target=self._lastfm_scrobble_bg,
                                         args=(dict(_tr), int(_ts)),
                                         daemon=True).start()
        except Exception:
            pass
        self._watch_cookies_file()
        if getattr(self, '_closed', False):
            return
        try:
            self.root.after(500, self._tick)
        except Exception:
            pass

    # ---------- dialogs ----------
    def open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title("Account & settings")
        win.geometry("440x1400")
        # Which copy is actually running? (the user keeps numbered backups, so
        # a stale copy is the classic "my change did nothing" trap).
        try:
            import time as _tt2
            _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _parts = []
            for _f in ("ui_main.py", "youtube_client.py"):
                try:
                    _p = os.path.join(_here, "app", _f)
                    _parts.append(f"{_f} {_tt2.strftime('%Y-%m-%d %H:%M', _tt2.localtime(os.path.getmtime(_p)))}")
                except Exception:
                    pass
            tk.Label(win, text="RUNNING FROM", font=("Segoe UI", 11, "bold")).pack(pady=(8, 2))
            tk.Label(win, text=_here, wraplength=400, fg="#7a7a7a").pack(pady=1)
            tk.Label(win, text=" • ".join(_parts) + "\nSearch shows songs AND videos.",
                     wraplength=400, fg="gray").pack(pady=(1, 4))
        except Exception:
            pass
        # Per-song data (local-cache.json) - ALWAYS visible at top
        tk.Label(win, text="Per-song data (local-cache.json)", font=("Segoe UI", 11, "bold")).pack(pady=(6, 2))
        btn_load = tk.Button(win, text="Load local-cache.json...", font=("Segoe UI", 10, "bold"), width=30)
        btn_load.pack(pady=4)
        btn_load.configure(command=self._pick_songmap_file_ui)
        btn_exp = tk.Button(win, text="Export local-cache.json...", font=("Segoe UI", 10, "bold"), width=30)
        btn_exp.pack(pady=4)
        btn_exp.configure(command=self._export_songmap_file_ui)
        # Google / YouTube account
        tk.Label(win, text="Google / YouTube account", font=("Segoe UI", 12, "bold")).pack(pady=(10, 2))
        tk.Label(win, text=f"Status: {self.client.account_label}", wraplength=400).pack(pady=2)
        tk.Label(win, text=f"Cookies: {self.client.cookies_json_path} ({len(self.client.cookies)} cookies)",
                 wraplength=400).pack(pady=2)
        if self.client.last_error:
            tk.Label(win, text=f"Detail: {self.client.last_error[:220]}",
                     wraplength=400, fg="red").pack(pady=2)
        tk.Button(win, text="Reload cookies", command=self._reload_cookies_ui).pack(pady=2)
        tk.Button(win, text="Choose another cookies JSON...",
                  command=self._pick_cookies_ui).pack(pady=2)
        tk.Label(win, text=("Session source (exported cookies expire in days; "
                            "browser ones last months and self-heal):"),
                 wraplength=400).pack(pady=(6, 2))
        fuente_var = tk.StringVar(value=self.theme.get("cuenta", "fuente_sesion", default="archivo"))
        fr = tk.Frame(win)
        fr.pack()
        tk.Radiobutton(fr, text="JSON file", variable=fuente_var, value="archivo",
                       command=lambda: self._set_fuente_sesion(fuente_var.get())).pack(side="left")
        tk.Radiobutton(fr, text="Navegador", variable=fuente_var, value="navegador",
                       command=lambda: self._set_fuente_sesion(fuente_var.get())).pack(side="left")
        brow_row = tk.Frame(win)
        brow_row.pack(pady=4)
        tk.Label(brow_row, text="Browser:").pack(side="left")
        brow_var = tk.StringVar(value=self.theme.get("cuenta", "navegador", default="chrome"))
        brow_box = ttk.Combobox(brow_row, textvariable=brow_var, width=12, state="readonly",
                                values=["chrome", "edge", "brave", "vivaldi", "opera", "firefox", "chromium"])
        brow_box.pack(side="left", padx=4)
        brow_box.bind("<<ComboboxSelected>>", lambda e: self._set_navegador(brow_var.get()))
        tk.Button(brow_row, text="Link",
                  command=self._link_browser_ui).pack(side="left", padx=4)
        tk.Button(win, text="Read browser session (1 click)",
                  command=lambda: self._import_profile_session_ui(
                      self.theme.get("cuenta", "navegador", default="chrome"))).pack(pady=2)
        tk.Label(win, text=("If you see 'Session expired': Google cookies expire. "
                            "Export fresh youtube.com cookies to cookiesYT.json "
                            "(overwrite the file) and the app reloads the session alone. "
                            "Or link your account via OAuth (never expires)."),
                 wraplength=400).pack(pady=6)
        tk.Label(win, text="Permanent session (OAuth)", font=("Segoe UI", 11, "bold")).pack(pady=(8, 2))
        tk.Button(win, text="Link Google account (permanent)...",
                  command=self.open_oauth_dialog).pack(pady=2)
        tk.Button(win, text="Sign in with Google (direct)...",
                  command=self.open_google_login_dialog).pack(pady=2)
        tk.Button(win, text="Unlink OAuth",
                  command=self._disconnect_oauth_ui).pack(pady=2)
        tk.Label(win, text="Last.fm + metadata", font=("Segoe UI", 11, "bold")).pack(pady=(8, 2))
        tk.Button(win, text="Last.fm scrobbling...",
                  command=self.open_lastfm_dialog).pack(pady=2)
        tk.Label(win, text="Audio cache", font=("Segoe UI", 11, "bold")).pack(pady=(12, 4))
        tk.Button(win, text="Clear cache", command=self._clean_cache_ui).pack(pady=4)
        tk.Label(win, text=f"Window frame: {getattr(self, '_frameless', '?')} "
                           "(win=custom, native=Windows)",
                 wraplength=400).pack(pady=2)
        tk.Button(win, text="Reset theme", command=self._reset_theme_ui).pack(pady=8)

    def _set_fuente_sesion(self, val: str) -> None:
        self.theme.set(val, "cuenta", "fuente_sesion")
        self.client.session_source = val
        self.status.configure(text=f"Session source: {val}. Reloading...")
        threading.Thread(target=self._reload_session_bg, daemon=True).start()

    def _set_navegador(self, val: str) -> None:
        self.theme.set(val, "cuenta", "navegador")
        self.client.browser = (val or "chrome").lower()

    def _link_browser_ui(self) -> None:
        self.status.configure(text="Reading browser session...")
        threading.Thread(target=self._reload_session_bg, daemon=True).start()

    def _reload_session_bg(self) -> None:
        try:
            self.client.reload_cookies()
        except Exception:
            pass
        self._call_ui(self._after_cookies_changed)

    def _reload_cookies_ui(self) -> None:
        ok = self.client.reload_cookies()
        self.account_label.configure(text=self.client.account_label)
        messagebox.showinfo("Account", f"Status: {self.client.account_label}\nAuth: {ok}")
        self.refresh_library_list()

    def _pick_cookies_ui(self) -> None:
        p = filedialog.askopenfilename(title="Choose cookiesYT.json",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if p:
            self.theme.set(p, "cuenta", "cookies_json_path")
            self.client.reload_cookies(p)
            self.account_label.configure(text=self.client.account_label)
            self.refresh_library_list()

    def _disconnect_oauth_ui(self) -> None:
        self.client.disconnect_oauth()
        self.account_label.configure(text=self.client.account_label)
        self.status.configure(text=f"OAuth unlinked. {self.client.account_label}")
        self.refresh_library_list()

    def _disconnect_oauth_ui(self) -> None:
        self.client.disconnect_oauth()
        self.account_label.configure(text=self.client.account_label)
        self.status.configure(text=f"OAuth unlinked. {self.client.account_label}")
        self.refresh_library_list()

    # ---------- Last.fm dialog ----------
    def open_lastfm_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title("Last.fm scrobbling")
        win.geometry("460x560")
        fam = self._font_family() if hasattr(self, "_font_family") else "Segoe UI"
        tk.Label(win, text="Last.fm scrobbling", font=(fam, 12, "bold")).pack(pady=8)
        tk.Label(win, text=("1) Create an API account (once): last.fm/api/account/create\n"
                            "2) Paste the key + secret below, press Connect,\n"
                            "allow access in the browser, press 'I allowed it'."),
                 wraplength=420, justify="left").pack(pady=4)
        frm = tk.Frame(win)
        frm.pack(pady=4)
        tk.Label(frm, text="API key:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        key_var = tk.StringVar(value=self.lastfm.api_key)
        tk.Entry(frm, textvariable=key_var, width=40).grid(row=0, column=1, pady=2)
        tk.Label(frm, text="Secret:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        sec_var = tk.StringVar(value=self.lastfm.api_secret)
        tk.Entry(frm, textvariable=sec_var, width=40, show="•").grid(row=1, column=1, pady=2)
        try:
            _linked = f"Linked as {self.lastfm.username}" if self.lastfm.linked else "Not linked"
            _pend = len(getattr(self.lastfm, "pending", []) or [])
        except Exception:
            _linked, _pend = "Not linked", 0
        status_lbl = tk.Label(win, text=f"{_linked} | queued: {_pend}", wraplength=420)
        status_lbl.pack(pady=4)

        def _refresh_status(extra: str = "") -> None:
            try:
                _l = f"Linked as {self.lastfm.username}" if self.lastfm.linked else "Not linked"
                _p = len(getattr(self.lastfm, "pending", []) or [])
                status_lbl.configure(text=f"{_l} | queued: {_p}" + (f" | {extra}" if extra else ""))
            except Exception:
                pass

        ctx: dict = {"token": ""}

        def _save_keys():
            self.lastfm.api_key = key_var.get().strip()
            self.lastfm.api_secret = sec_var.get().strip()
            self.lastfm.save()

        def _connect():
            _save_keys()
            if not self.lastfm.configured:
                _refresh_status("paste key + secret first")
                return
            status_lbl.configure(text="Asking Last.fm for a token...")
            import webbrowser

            def _bg():
                try:
                    tok = self.lastfm.get_token()
                except Exception:
                    tok = ""
                if not tok:
                    self._call_ui(status_lbl.configure,
                                  text=f"Token failed: {self.lastfm.last_error[:100]}")
                    return
                ctx["token"] = tok
                try:
                    webbrowser.open(self.lastfm.auth_url(tok))
                except Exception:
                    pass
                self._call_ui(status_lbl.configure,
                              text="Browser opened: allow access, then press 'I allowed it'.")
            threading.Thread(target=_bg, daemon=True).start()

        def _finish():
            _save_keys()
            tok = ctx.get("token", "")
            if not tok:
                _refresh_status("press Connect first")
                return
            status_lbl.configure(text="Finishing link...")

            def _bg():
                ok = self.lastfm.get_session(tok)
                self._call_ui(_refresh_status, "linked ✔" if ok else f"failed: {self.lastfm.last_error[:100]}")
                if ok:
                    self._call_ui(self.status.configure, text="Last.fm linked ✔")
            threading.Thread(target=_bg, daemon=True).start()

        def _unlink():
            self.lastfm.unlink()
            ctx["token"] = ""
            _refresh_status("unlinked")

        def _flush():
            def _bg():
                try:
                    n = self.lastfm._flush_pending()
                except Exception:
                    n = 0
                self._call_ui(_refresh_status, f"sent {n} queued ✔")
            threading.Thread(target=_bg, daemon=True).start()

        sc_var = tk.BooleanVar(value=bool(self.lastfm.scrobble_enabled))

        def _sc_toggle():
            self.lastfm.scrobble_enabled = bool(sc_var.get())
            self.lastfm.save()
            self.status.configure(text=f"Last.fm scrobbling {'on' if sc_var.get() else 'off'}")

        brow = tk.Frame(win)
        brow.pack(pady=4)
        tk.Button(brow, text="1) Connect (opens browser)", command=_connect).pack(side="left", padx=4)
        tk.Button(brow, text="2) I allowed it", command=_finish).pack(side="left", padx=4)
        brow2 = tk.Frame(win)
        brow2.pack(pady=4)
        tk.Button(brow2, text="Unlink", command=_unlink).pack(side="left", padx=4)
        tk.Button(brow2, text="Send queued now", command=_flush).pack(side="left", padx=4)
        tk.Checkbutton(win, text="Scrobble plays to Last.fm", variable=sc_var,
                       command=_sc_toggle).pack(pady=4)
        tk.Label(win, text=("Scrobbles use the EDITED title/artist/album (regex edits\n"
                            "applied, e.g. 'X - Single' is scrobbled as 'X')."),
                 wraplength=420, fg="gray").pack(pady=4)

    def open_song_edit_dialog(self) -> None:
        """Edit THIS song's title/artist/album (✎ next to ⚙︎).

        Saved into local-cache.json (generated if none is loaded). Edited
        songs use the saved data; anything else shows the song default."""
        try:
            cur = dict(getattr(self.player, "current", None) or {})
        except Exception:
            cur = {}
        vid = str(cur.get("videoId", "") or "")
        if not vid:
            try:
                self.status.configure(text="Play a song first, then edit its data. ♪")
            except Exception:
                pass
            return
        # Pick up external edits to the json made while the app runs.
        try:
            self._songmap_maybe_reload()
        except Exception:
            pass
        try:
            shown = self._meta_edited(cur)
            _mapped = (isinstance(getattr(self, "_songmap", None), dict)
                       and str(vid) in (self._songmap or {}))
        except Exception:
            shown, _mapped = {}, False
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title("Edit song data")
        win.geometry("480x440")
        try:
            fam = self._font_family()
        except Exception:
            fam = "Segoe UI"
        try:
            tk.Label(win, text=f"Playing: {shown.get('artist','')} — "
                               f"{shown.get('track','')}",
                     font=(fam, 10, "bold"), wraplength=440).pack(pady=(8, 2))
        except Exception:
            pass
        if _mapped:
            try:
                tk.Label(win, text="★ this song has saved data",
                         fg="green").pack(pady=0)
            except Exception:
                pass
        try:
            _sp = (getattr(self.lastfm, "songmap_path", "") or "").strip()
        except Exception:
            _sp = ""
        tk.Label(win, text="New values (blank = back to default). Saved into "
                           + (os.path.basename(_sp) if _sp else "local-cache.json") + ".",
                 wraplength=440, fg="gray").pack(pady=2)
        frm = tk.Frame(win)
        frm.pack(pady=6)
        vars_map: dict[str, tk.StringVar] = {}
        for i, f in enumerate(("track", "artist", "album")):
            tk.Label(frm, text=f"{'Title' if f == 'track' else f.capitalize()}:").grid(
                row=i, column=0, sticky="e", padx=4, pady=3)
            sv = tk.StringVar(value=str(shown.get(f, "") or ""))
            tk.Entry(frm, textvariable=sv, width=44).grid(row=i, column=1, pady=3)
            vars_map[f] = sv
        prev = tk.Label(win, text="", wraplength=440, justify="left", fg="gray")
        prev.pack(fill="x", padx=10, pady=4)

        def _refresh_preview(*_a):
            try:
                _t = vars_map["track"].get() or cur.get("title", "")
                _a2 = vars_map["artist"].get() or cur.get("artist", "")
                _al = vars_map["album"].get() or cur.get("album", "")
                prev.configure(text=f"result: {_a2} — {_t}"
                                    + (f" @@ {_al}" if _al else ""))
            except Exception:
                pass

        for sv in vars_map.values():
            try:
                sv.trace_add("write", _refresh_preview)
            except Exception:
                pass
        _refresh_preview()

        def _save():
            try:
                newv = {f: vars_map[f].get() for f in ("track", "artist", "album")}
                ok, msg = self._save_song_override(vid, newv)
                try:
                    self.status.configure(text=msg)
                except Exception:
                    pass
                if ok:
                    # The edited artist/title is what Last.fm must be asked
                    # about now, so the ⟳N has to be looked up again.
                    try:
                        self.refresh_play_count(vid)
                    except Exception:
                        pass
                    win.destroy()
            except Exception as e:
                try:
                    self.status.configure(text=f"Save error: {e}")
                except Exception:
                    pass

        def _remove():
            try:
                _ok, _msg = self._remove_song_override(vid)
                try:
                    self.status.configure(text=_msg)
                except Exception:
                    pass
                try:
                    self.refresh_play_count(vid)
                except Exception:
                    pass
                win.destroy()
            except Exception:
                pass

        brow = tk.Frame(win)
        brow.pack(pady=8)
        tk.Button(brow, text="Save song data", command=_save).pack(side="left", padx=4)
        tk.Button(brow, text="Remove saved data", command=_remove).pack(side="left", padx=4)
        tk.Button(brow, text="Cancel", command=win.destroy).pack(side="left", padx=4)

    def _import_profile_session_ui(self, browser, win=None, status_widget=None) -> None:
        """1 click: read the real browser profile session and import it."""
        def _set(t):
            try:
                if status_widget is not None:
                    status_widget.configure(text=t)
                self.status.configure(text=t)
            except Exception:
                pass
        _set(f"Reading {browser} session...")
        def _bg():
            try:
                from app import google_login as _gl
                cookies = _gl.read_profile_session(browser)
                ok = self.client.import_login_cookies(cookies)
                self._call_ui(self.account_label.configure, text=self.client.account_label)
                self._call_ui(self.refresh_library_list)
                if ok and self.client.authenticated:
                    self._call_ui(_set, f"Session linked ✔ ({len(cookies)} cookies from {browser})")
                    if win is not None:
                        self._call_ui(win.destroy)
                    self._call_ui(messagebox.showinfo, "Session",
                                  f"Connected with your {browser}. Your playlists are loading.")
                else:
                    self._call_ui(_set, f"Read but unverified: {self.client.last_error[:150]} "
                                        "(see cache/glogin.log)")
            except Exception as e:
                try:
                    from app import google_login as _gl2
                    _gl2.log(f"1-click FAIL: {e}")
                except Exception:
                    pass
                msg = str(e)
                if "Could not copy" in msg or "Permission denied" in msg:
                    msg = (f"Your {browser} is OPEN and locks its cookies. Close it completely "
                           "and press again. Alternative: 'Link / refresh', which does "
                           "not need it closed.")
                else:
                    msg = msg[:220]
                self._call_ui(_set, msg)
        threading.Thread(target=_bg, daemon=True).start()

    def open_google_login_dialog(self) -> None:
        """DIRECT Google login in a real window + automatic import."""
        from app import google_login as _gl
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title("Sign in with Google")
        win.geometry("460x420")
        tk.Label(win, text="Sign in with your Google account",
                 font=("Segoe UI", 12, "bold")).pack(pady=8)
        tk.Label(win, text=("Option A (recommended): open a window, YOU sign in\n"
                            "on the REAL Google page and it imports itself. Works with\n"
                            "your browser open.\n"
                            "Option B (1 click): read your current session. Requires fully closing\n"
                            "your browser first (if open it locks its cookies)."),
                 wraplength=420, justify="left").pack(padx=10, pady=4)
        brow_var = tk.StringVar(value=self.theme.get("cuenta", "navegador", default="chrome"))
        brow_row = tk.Frame(win)
        brow_row.pack(pady=4)
        tk.Label(brow_row, text="Browser:").pack(side="left")
        avail = _gl.available_browsers()
        full = list(dict.fromkeys(avail + _gl.FULL_BROWSER_LIST))
        brow_box = ttk.Combobox(brow_row, textvariable=brow_var, width=10, state="readonly",
                                values=full)
        if brow_var.get() not in full:
            brow_var.set(full[0])
        brow_box.pack(side="left", padx=4)
        tk.Button(win, text="Read current session (1 click, browser closed)",
                  command=lambda: self._import_profile_session_ui(brow_var.get(), win, status_lbl)).pack(pady=4)
        status_lbl = tk.Label(win, text="Not started", fg="gray", wraplength=420)
        status_lbl.pack(pady=6)
        ctx: dict = {"driver": None, "watching": False}
        btnrow = tk.Frame(win)
        btnrow.pack(pady=4)

        def _set_status(t):
            try:
                status_lbl.configure(text=t)
            except Exception:
                pass

        def _open():
            _set_status("Opening browser...")
            def _bg():
                try:
                    drv = _gl.start_browser(brow_var.get())
                    ctx["driver"] = drv
                    self.theme.set(brow_var.get(), "cuenta", "navegador")
                    self.client.browser = brow_var.get().lower()
                    self._call_ui(_set_status, "Browser open: sign in on YouTube...")
                    ctx["watching"] = True
                    threading.Thread(target=_watch, daemon=True).start()
                except Exception as e:
                    self._call_ui(_set_status, f"No se pudo abrir: {str(e)[:200]}")
                    try:
                        from app import google_login as _gl3
                        _gl3.log(f"abrir FAIL: {e}")
                    except Exception:
                        pass
                    self._call_ui(messagebox.showerror, "Google login", str(e)[:400] + "\n(more detail in cache/glogin.log)")
            threading.Thread(target=_bg, daemon=True).start()

        def _watch():
            # Autodetect: when a session appears, notify (without closing anything)
            try:
                import time as _t
                for _ in range(150):  # ~5 min
                    if not ctx.get("watching"):
                        return
                    try:
                        if ctx["driver"] and _gl.login_detected(_gl.read_cookies(ctx["driver"])):
                            self._call_ui(_set_status, "Session detected! Press 'I'm in, link it'.")
                            return
                    except Exception:
                        return
                    _t.sleep(2)
                self._call_ui(_set_status, "Timed out — did you sign in?")
            except Exception:
                pass

        def _finish():
            drv = ctx.get("driver")
            if drv is None:
                messagebox.showwarning("Google login", "Open the browser and sign in first.")
                return
            _set_status("Importing session...")
            def _bg():
                try:
                    cookies = _gl.read_cookies(drv)
                    if not _gl.login_detected(cookies):
                        self._call_ui(_set_status, "Still signed out: sign in on the browser first.")
                        return
                    ok = self.client.import_login_cookies(cookies)
                    try:
                        _gl.close_browser(drv)
                    except Exception:
                        pass
                    ctx["driver"] = None
                    ctx["watching"] = False
                    self._call_ui(self.account_label.configure, text=self.client.account_label)
                    self._call_ui(self.refresh_library_list)
                    if ok and self.client.authenticated:
                        self._call_ui(self.status.configure,
                                      text=f"Signed in with Google ✔ ({len(cookies)} cookies)")
                        self._call_ui(win.destroy)
                        self._call_ui(messagebox.showinfo, "Google login",
                                      "Session linked. Your playlists are loading.")
                    else:
                        self._call_ui(_set_status, f"Imported but unverified: {self.client.last_error[:150]}")
                except Exception as e:
                    self._call_ui(_set_status, f"Error: {str(e)[:200]}")
            threading.Thread(target=_bg, daemon=True).start()

        def _cancel():
            ctx["watching"] = False
            try:
                if ctx.get("driver"):
                    _gl.close_browser(ctx["driver"])
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        tk.Button(btnrow, text="A. Open window & link", command=_open).pack(side="left", padx=4)
        tk.Button(btnrow, text="I'm in, link it", command=_finish).pack(side="left", padx=4)
        tk.Button(btnrow, text="Cancel", command=_cancel).pack(side="left", padx=4)
        win.protocol("WM_DELETE_WINDOW", _cancel)

    def open_oauth_dialog(self) -> None:
        """Google OAuth linking (device flow, never-expiring session)."""
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title("Link Google account (permanent)")
        win.geometry("480x600")
        cid0, sec0 = self.client.get_oauth_creds_saved()
        tk.Label(win, text="1) Create your OAuth client (just once):", font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(win, text=("console.cloud.google.com → new project → enable "
                            "'YouTube Data API v3' → Credentials → Create client ID "
                            "OAuth → 'Desktop app' type. Copy the ID and secret below."),
                 wraplength=440, justify="left").pack(padx=10, pady=2)
        tk.Label(win, text="Client ID:").pack(anchor="w", padx=10)
        cid_var = tk.StringVar(value=cid0)
        tk.Entry(win, textvariable=cid_var, width=60).pack(padx=10)
        tk.Label(win, text="Client secret:").pack(anchor="w", padx=10)
        sec_var = tk.StringVar(value=sec0)
        tk.Entry(win, textvariable=sec_var, width=60, show="•").pack(padx=10)
        tk.Label(win, text="2) Get the code and authorize it in the browser:",
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 0))
        code_lbl = tk.Label(win, text="(press 'Get code')",
                            font=("Segoe UI", 16, "bold"), fg="blue")
        code_lbl.pack(pady=4)
        url_lbl = tk.Label(win, text="", wraplength=440, fg="gray")
        url_lbl.pack(pady=2)
        btnrow = tk.Frame(win)
        btnrow.pack(pady=4)
        ctx: dict = {}

        def _step1():
            cid, sec = cid_var.get().strip(), sec_var.get().strip()
            if not cid or not sec:
                messagebox.showwarning("OAuth", "Paste the Client ID and Client secret first.")
                return
            try:
                self.client.save_oauth_creds(cid, sec)
            except Exception as e:
                messagebox.showerror("OAuth", f"Could not save: {e}")
                return
            code_lbl.configure(text="Requesting code...")
            def _bg():
                try:
                    from ytmusicapi import OAuthCredentials
                    creds = OAuthCredentials(cid, sec)
                    code = creds.get_code()
                    ctx["creds"] = creds
                    ctx["device"] = code.get("device_code", "")
                    uc = code.get("user_code", "")
                    url = f"{code.get('verification_url', '')}?user_code={uc}"
                    ctx["url"] = url
                    self._call_ui(code_lbl.configure, text=uc)
                    self._call_ui(url_lbl.configure, text=url)
                    self._call_ui(lambda: self.status.configure(text="OAuth code ready: authorize it in the browser"))
                except Exception as e:
                    self._call_ui(code_lbl.configure, text="Error")
                    self._call_ui(messagebox.showerror, "OAuth", f"Could not request the code:\n{str(e)[:300]}")
            threading.Thread(target=_bg, daemon=True).start()

        def _open_browser():
            import webbrowser
            if ctx.get("url"):
                webbrowser.open(ctx["url"])
            else:
                messagebox.showinfo("OAuth", "Press 'Get code' first.")

        def _step2():
            if not ctx.get("device") or not ctx.get("creds"):
                messagebox.showwarning("OAuth", "Get the code and authorize it in the browser first.")
                return
            code_lbl.configure(text="Verifying...")
            def _bg():
                tok, msg = self.client.finish_oauth_device(ctx["creds"], ctx["device"])
                self._call_ui(self.account_label.configure, text=self.client.account_label)
                self._call_ui(self.refresh_library_list)
                if tok and self.client.authenticated and self.client.auth_method == "oauth":
                    self._call_ui(self.status.configure, text=msg)
                    self._call_ui(win.destroy)
                    self._call_ui(messagebox.showinfo, "OAuth", msg + "\nYou will no longer depend on cookies.")
                elif tok:
                    self._call_ui(code_lbl.configure, text="(check your network)")
                    self._call_ui(messagebox.showinfo, "OAuth", msg)
                else:
                    self._call_ui(code_lbl.configure, text="(retry)")
                    self._call_ui(messagebox.showwarning, "OAuth", msg)
            threading.Thread(target=_bg, daemon=True).start()

        tk.Button(btnrow, text="Get code", command=_step1).pack(side="left", padx=4)
        tk.Button(btnrow, text="Open browser", command=_open_browser).pack(side="left", padx=4)
        tk.Button(btnrow, text="3. Authorized it", command=_step2).pack(side="left", padx=4)
        tk.Label(win, text=("3) In the browser, accept with your Google account and come back "
                            "to press 'Authorized it'. From then on the session renews "
                            "alone and cookies stop mattering."),
                 wraplength=440, justify="left").pack(padx=10, pady=8)

    def _clean_cache_ui(self) -> None:
        try:
            import shutil
            n = 0
            for name in os.listdir(self.client.cache_dir):
                pp = os.path.join(self.client.cache_dir, name)
                if os.path.isfile(pp) and not name.endswith((".txt", ".json")):
                    try:
                        os.remove(pp)
                        n += 1
                    except Exception:
                        pass
            messagebox.showinfo("Cache", f"Deleted {n} files.")
        except Exception as e:
            messagebox.showerror("Cache", str(e))

    def _reset_theme_ui(self) -> None:
        if messagebox.askyesno("Theme", "Reset all customization?"):
            self.theme.reset()
            self.apply_theme()

    def _theme_ttk(self, master=None) -> None:
        """Make ttk widgets follow the theme instead of the OS grey.

        ttk draws its own chrome and ignored the theme completely, which is
        what left grey tab bars behind. 'clam' is the only ttk theme whose
        colours can be set.
        """
        try:
            style = ttk.Style(master or self.root)
            try:
                style.theme_use("clam")
            except Exception:
                return
            pnl = self._wcol("panel", "fondo")
            txt = self._wcol("panel", "texto")
            bor = self._wcol("panel", "borde")
            sel = self._wcol("buscador", "seleccion")
            for name in ("TNotebook", "Notebook"):
                style.configure(name, background=pnl, bordercolor=bor,
                                lightcolor=bor, darkcolor=pnl,
                                tabcolor=pnl, foreground=txt)
                style.map(name, background=[("selected", sel)],
                          foreground=[("selected", "#ffffff")])
            style.configure("TFrame", background=pnl)
            style.configure("TLabel", background=pnl, foreground=txt)
            style.configure("TCombobox", fieldbackground=pnl, background=pnl,
                            foreground=txt, arrowcolor=txt, bordercolor=bor)
            style.configure("TNotebook.Tab", background=self._tint_mid,
                            foreground=txt)
            style.map("TNotebook.Tab",
                      background=[("selected", sel)],
                      foreground=[("selected", "#ffffff")])
        except Exception:
            pass

    def open_customize(self) -> None:
        win = tk.Toplevel(self.root)
        # Same frameless bar + app icon as the main window
        self._frameless_toplevel(win)
        win.title("TOTAL Customization")
        win.geometry("560x620")
        self._theme_ttk(win)
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Background ---
        f_fondo = ttk.Frame(nb)
        nb.add(f_fondo, text="Background")
        modo_var = tk.StringVar(value=self.theme.get("fondo", "modo", default="degradado"))
        tk.Label(f_fondo, text="Background mode:").pack(anchor="w", padx=8, pady=(8, 0))
        # Display text is English; values stay Spanish (theme schema keys).
        for m, _mlbl in (("color", "Color"), ("degradado", "Gradient"),
                         ("imagen", "Image"), ("video", "Video")):
            tk.Radiobutton(f_fondo, text=_mlbl, variable=modo_var, value=m).pack(anchor="w", padx=16)
        tk.Button(f_fondo, text="Color 1...",
                  command=lambda: self._pick_color("fondo", "color")).pack(pady=4)
        tk.Button(f_fondo, text="Color 2 (gradient)...",
                  command=lambda: self._pick_color("fondo", "color2")).pack(pady=2)
        tk.Button(f_fondo, text="Choose background image...",
                  command=lambda: self._pick_file("fondo", "imagen_path",
                                                  [("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])).pack(pady=4)
        tk.Button(f_fondo, text="Choose background VIDEO...",
                  command=lambda: self._pick_file("fondo", "video_path",
                                                  [("Video", "*.mp4 *.avi *.mov *.mkv *.webm")])).pack(pady=2)
        tk.Label(f_fondo, text="Readability (layer over the background)").pack(pady=(8, 0))
        ov_var = tk.DoubleVar(value=float(self.theme.get("fondo", "overlay_opacidad", default=0.55)))
        tk.Scale(f_fondo, from_=0.0, to=0.9, resolution=0.05, orient="horizontal",
                 variable=ov_var,
                 command=lambda v: (self.theme.set(float(v), "fondo", "overlay_opacidad"),
                                    self.apply_theme())).pack(fill="x", padx=12)
        tk.Button(f_fondo, text="Apply mode",
                  command=lambda: (self.theme.set(modo_var.get(), "fondo", "modo"),
                                   self.apply_theme())).pack(pady=8)

        # --- Buttons ---
        f_bot = ttk.Frame(nb)
        nb.add(f_bot, text="Buttons")
        tk.Label(f_bot, text="Button size").pack(pady=(8, 0))
        tam_var = tk.IntVar(value=int(self.theme.get("botones", "tamano", default=44)))
        tk.Scale(f_bot, from_=24, to=96, orient="horizontal", variable=tam_var,
                 command=lambda v: (self.theme.set(int(float(v)), "botones", "tamano"),
                                    self.apply_theme())).pack(fill="x", padx=12)
        tk.Button(f_bot, text="Background color...",
                  command=lambda: self._pick_color("botones", "color_fondo")).pack(pady=3)
        tk.Button(f_bot, text="Hover color...",
                  command=lambda: self._pick_color("botones", "color_hover")).pack(pady=3)
        tk.Button(f_bot, text="Text/icon color...",
                  command=lambda: self._pick_color("botones", "color_texto")).pack(pady=3)
        tk.Label(f_bot, text="Border & radius").pack(pady=(8, 0))
        borde_var = tk.IntVar(value=int(self.theme.get("botones", "borde_ancho", default=0)))
        tk.Scale(f_bot, from_=0, to=6, orient="horizontal", variable=borde_var,
                 command=lambda v: (self.theme.set(int(float(v)), "botones", "borde_ancho"),
                                    self.apply_theme())).pack(fill="x", padx=12)
        tk.Label(f_bot, text="Button shape:").pack(pady=(8, 0))
        forma_var = tk.StringVar(value=self.theme.get("botones", "forma", default="redondo"))
        for fm, lbl in (("redondo", "Round"), ("cuadrado", "Square"),
                        ("custom", "Custom shape (PNG)")):
            tk.Radiobutton(f_bot, text=lbl, variable=forma_var, value=fm,
                           command=lambda: (self.theme.set(forma_var.get(), "botones", "forma"),
                                            self.apply_theme())).pack(anchor="w", padx=16)
        tk.Button(f_bot, text="Load PNG shape...",
                  command=self._pick_shape_png).pack(pady=4)
        tk.Button(f_bot, text="Remove PNG shape",
                  command=lambda: (self.theme.set("", "botones", "forma_custom_path"),
                                   self.theme.set("redondo", "botones", "forma"),
                                   self.apply_theme())).pack(pady=2)
        self._forma_lbl = tk.Label(f_bot, text="", wraplength=480)
        self._forma_lbl.pack(pady=2)
        self._update_forma_label()
        usar_var = tk.BooleanVar(value=bool(self.theme.get("botones", "usar_formas", default=True)))
        tk.Checkbutton(f_bot, text="Use shapes (otherwise plain rectangles)",
                       variable=usar_var,
                       command=lambda: (self.theme.set(bool(usar_var.get()), "botones", "usar_formas"),
                                        self.apply_theme())).pack(pady=4)

        # --- Widgets (search bar + sliders) ---
        f_wdg = ttk.Frame(nb)
        nb.add(f_wdg, text="Widgets")
        tk.Label(f_wdg, text="Colours of the search bar and of every slider "
                 "(progress, volume and these Customize sliders).",
                 wraplength=480, bg=self._wcol("panel", "fondo"),
                 fg=self._wcol("panel", "texto")).pack(pady=6)

        def _wgroup(title: str, group: str, keys: list[tuple[str, str]]) -> None:
            # tk.LabelFrame paints its own light OS background; theme it.
            pnl, bor = self._wcol("panel", "fondo"), self._wcol("panel", "borde")
            box = tk.LabelFrame(f_wdg, text=title, padx=10, pady=6,
                                bg=pnl, fg=self._wcol("panel", "texto"),
                                highlightbackground=bor, highlightcolor=bor,
                                highlightthickness=1, bd=1, relief="solid")
            box.pack(fill="x", padx=14, pady=6)
            for row, (key, label) in enumerate(keys):
                tk.Label(box, text=f"{label}:", width=18, anchor="w",
                         bg=pnl, fg=self._wcol("panel", "texto")
                         ).grid(row=row, column=0, sticky="w", pady=2)
                sw = tk.Label(box, text=" ", width=4, bd=1, relief="solid",
                              bg=pnl)
                sw.grid(row=row, column=1, padx=4, pady=2)
                try:
                    sw.configure(bg=self._wcol(group, key))
                except Exception:
                    pass
                tk.Button(box, text="Change", width=9,
                          command=lambda g=group, k=key, s=sw:
                          self._pick_widget_color(g, k, s)).grid(row=row, column=2, padx=2)
                tk.Button(box, text="Reset", width=9,
                          command=lambda g=group, k=key, s=sw:
                          self._reset_widget_color(g, k, s)).grid(row=row, column=3, padx=2)

        _wgroup("Search bar", "buscador", [
            ("fondo", "Background"), ("texto", "Text"),
            ("borde", "Border"), ("cursor", "Caret"),
            ("seleccion", "Selection")])
        _wgroup("Sliders", "slider", [
            ("fondo", "Background"), ("pista", "Track"),
            ("pulgar", "Thumb"), ("borde", "Border"),
            ("texto", "Numbers")])
        _wgroup("Panels & scrollbars", "panel", [
            ("fondo", "Background"), ("borde", "Border"),
            ("texto", "Text")])
        _wgroup("Right-click menu", "menu", [
            ("fondo", "Background"), ("texto", "Text"),
            ("activo_fondo", "Highlight bg"), ("activo_texto", "Highlight text"),
            ("borde", "Separators")])

        # --- App icon (title bar + taskbar + Alt+Tab) ---
        box = tk.LabelFrame(f_wdg, text="App icon", padx=10, pady=6,
                            bg=self._wcol("panel", "fondo"),
                            fg=self._wcol("panel", "texto"),
                            highlightbackground=self._wcol("panel", "borde"),
                            highlightcolor=self._wcol("panel", "borde"),
                            highlightthickness=1, bd=1, relief="solid")
        box.pack(fill="x", padx=14, pady=6)
        tk.Label(box, text="Shown on the title bar and the taskbar.",
                 bg=self._wcol("panel", "fondo"),
                 fg=self._wcol("panel", "texto")).grid(row=0, column=0,
                                                        columnspan=4,
                                                        sticky="w", pady=(0, 6))
        prev = tk.Label(box, text=" \u2713 ", width=5, bd=1, relief="solid",
                        bg=self._wcol("panel", "fondo"))
        prev.grid(row=1, column=0, padx=(0, 8), pady=2)
        try:
            from PIL import Image, ImageTk
            _ic = self._app_icon_path()
            if _ic:
                prev.configure(image=ImageTk.PhotoImage(
                    Image.open(_ic).convert("RGBA").resize((28, 28),
                                                          Image.LANCZOS)))
                prev.image = prev.cget("image")
        except Exception:
            pass
        tk.Button(box, text="Use my image...", width=14,
                  command=lambda: self._pick_app_icon(prev)
                  ).grid(row=1, column=1, padx=3)
        tk.Button(box, text="Theme default", width=14,
                  command=lambda: self._reset_app_icon(prev)
                  ).grid(row=1, column=2, padx=3)
        tk.Label(box, text="PNG with transparency looks best.",
                 bg=self._wcol("panel", "fondo"),
                 fg=self._wcol("panel", "borde")).grid(row=1, column=3,
                                                        padx=8)
        def _applied():
            self.apply_widgets_theme()
            try:
                self.status.configure(text="Widget colours applied")
            except Exception:
                pass
        tk.Button(f_wdg, text="Apply now", command=_applied,
                  bg=self._tint_mid, fg=self._ch_fg(),
                  activebackground=self._tint_mid, activeforeground=self._ch_fg(),
                  relief="flat", bd=0).pack(pady=8)

        # --- Icons ---
        f_ico = ttk.Frame(nb)
        nb.add(f_ico, text="Icons")
        tk.Label(f_ico, text="Click a button to change its icon (emoji, letter or image).",
                 wraplength=480).pack(pady=6)
        keys = ["play", "pause", "prev", "next", "shuffle", "loop_all",
                "loop_one", "loop_off", "fav", "fav_on", "search", "settings", "volume"]
        grid = tk.Frame(f_ico)
        grid.pack(padx=8, pady=4)
        for idx, k in enumerate(keys):
            cur = self.theme.get("iconos", k, default="?")
            tk.Label(grid, text=f"{k}:").grid(row=idx, column=0, sticky="w", padx=4, pady=2)
            prev = tk.Label(grid, width=4)
            prev.grid(row=idx, column=1, padx=4, pady=2)
            self._update_icon_preview(k, prev)
            tk.Label(grid, text=str(cur)[:22]).grid(row=idx, column=2, sticky="w", padx=4)
            tk.Button(grid, text="Change",
                      command=lambda kk=k, pp=prev: self._change_icon(kk, pp)).grid(row=idx, column=3, padx=4, pady=2)
            tk.Button(grid, text="Default",
                      command=lambda kk=k, pp=prev: self._reset_icon(kk, pp)).grid(row=idx, column=4, padx=4, pady=2)
        tk.Label(f_ico, text="Icon font size").pack(pady=(8, 0))
        fi_var = tk.IntVar(value=int(self.theme.get("iconos", "tamano_fuente_icono", default=18)))
        tk.Scale(f_ico, from_=10, to=40, orient="horizontal", variable=fi_var,
                 command=lambda v: (self.theme.set(int(float(v)), "iconos", "tamano_fuente_icono"),
                                    self.apply_theme())).pack(fill="x", padx=12)

        # --- Text ---
        f_txt = ttk.Frame(nb)
        nb.add(f_txt, text="Text")
        tk.Button(f_txt, text="Title color...",
                  command=lambda: self._pick_color("texto", "color_titulo")).pack(pady=4)
        tk.Button(f_txt, text="Subtitle color...",
                  command=lambda: self._pick_color("texto", "color_subtitulo")).pack(pady=2)
        tk.Button(f_txt, text="List color...",
                  command=lambda: self._pick_color("texto", "color_lista")).pack(pady=2)
        tk.Button(f_txt, text="Accent color...",
                  command=lambda: self._pick_color("texto", "color_acento")).pack(pady=2)
        tk.Button(f_txt, text="List background...",
                  command=lambda: self._pick_color("lista", "color_fondo")).pack(pady=4)
        tk.Button(f_txt, text="Active item...",
                  command=lambda: self._pick_color("lista", "color_item_activo")).pack(pady=2)
        tk.Label(f_txt, text="Title size").pack(pady=(8, 0))
        st_var = tk.IntVar(value=int(self.theme.get("texto", "fuente_tam_titulo", default=13)))
        tk.Scale(f_txt, from_=8, to=24, orient="horizontal", variable=st_var,
                 command=lambda v: (self.theme.set(int(float(v)), "texto", "fuente_tam_titulo"),
                                    self.apply_theme())).pack(fill="x", padx=12)
        tk.Label(f_txt, text="List size").pack()
        sl_var = tk.IntVar(value=int(self.theme.get("texto", "fuente_tam_lista", default=11)))
        tk.Scale(f_txt, from_=8, to=20, orient="horizontal", variable=sl_var,
                 command=lambda v: (self.theme.set(int(float(v)), "texto", "fuente_tam_lista"),
                                    self.apply_theme())).pack(fill="x", padx=12)
        tk.Label(f_txt, text="CUSTOM font (.ttf/.otf)").pack(pady=(10, 0))
        try:
            tk.Label(f_txt, text="Your icons live in assets/icons/",
                     fg="gray").pack(pady=1)
        except Exception:
            pass
        self._customfont_lbl = tk.Label(f_txt, text="", wraplength=480)
        self._customfont_lbl.pack(pady=2)
        try:
            _cp = str(self.theme.get("texto", "fuente_custom_path", default="") or "")
            self._customfont_lbl.configure(text=f"Archivo: {os.path.basename(_cp)}" if _cp else "(none: uses the family above)")
        except Exception:
            pass
        tk.Label(f_txt, text="Family (e.g. Segoe UI)").pack()
        fam_var = tk.StringVar(value=str(self.theme.get("texto", "fuente_familia", default="Segoe UI")))
        tk.Entry(f_txt, textvariable=fam_var, width=30).pack(pady=2)
        tk.Button(f_txt, text="Apply family",
                  command=lambda: (self.theme.set(fam_var.get().strip() or "Segoe UI", "texto", "fuente_familia"),
                                   self.apply_theme())).pack(pady=2)
        tk.Button(f_txt, text="Load .ttf/.otf...",
                  command=self._pick_custom_font).pack(pady=2)
        tk.Button(f_txt, text="Remove custom font",
                  command=self._clear_custom_font).pack(pady=2)

        # --- Window ---
        f_win = ttk.Frame(nb)
        nb.add(f_win, text="Window")
        tk.Label(f_win, text="Transparency").pack(pady=(8, 0))
        tr_var = tk.DoubleVar(value=float(self.theme.get("ventana", "transparencia", default=1.0)))
        tk.Scale(f_win, from_=0.4, to=1.0, resolution=0.05, orient="horizontal",
                 variable=tr_var,
                 command=lambda v: (self.theme.set(float(v), "ventana", "transparencia"),
                                    self.apply_theme())).pack(fill="x", padx=12)
        top_var = tk.BooleanVar(value=bool(self.theme.get("ventana", "siempre_encima", default=False)))
        tk.Checkbutton(f_win, text="Always on top", variable=top_var,
                       command=lambda: (self.theme.set(bool(top_var.get()), "ventana", "siempre_encima"),
                                        self.apply_theme())).pack(pady=6)
        bar_var = tk.BooleanVar(value=bool(self.theme.get("ventana", "barra_personalizada", default=True)))
        tk.Checkbutton(f_win, text="Custom title bar (restart to apply)", variable=bar_var,
                       command=lambda: (self.theme.set(bool(bar_var.get()), "ventana", "barra_personalizada"),
                                        messagebox.showinfo("Bar", "Restart the app to apply the bar change."))).pack(pady=4)
        thumb_var = tk.BooleanVar(value=bool(self.theme.get("lista", "mostrar_thumbnails", default=True)))
        tk.Checkbutton(f_win, text="Show thumbnails", variable=thumb_var,
                       command=lambda: (self.theme.set(bool(thumb_var.get()), "lista", "mostrar_thumbnails"),
                                        self.apply_theme())).pack(pady=4)
        tk.Label(f_win, text="Default volume (0.2 steps)").pack(pady=(8, 0))
        vd_var = tk.DoubleVar(value=float(self.theme.get("reproductor", "volumen_defecto", default=70) or 70))
        tk.Scale(f_win, from_=0, to=100, resolution=0.2, orient="horizontal", variable=vd_var,
                 command=lambda v: self.theme.set(round(float(v), 1), "reproductor", "volumen_defecto")).pack(fill="x", padx=12)
        gv_var = tk.BooleanVar(value=bool(self.theme.get("reproductor", "guardar_volumen", default=True)))
        tk.Checkbutton(f_win, text="Save volume on exit (remember last)", variable=gv_var,
                       command=lambda: self.theme.set(bool(gv_var.get()), "reproductor", "guardar_volumen")).pack(pady=2)
        hc_var = tk.BooleanVar(value=bool(self.theme.get("ventana", "ocultar_consola", default=True)))
        tk.Checkbutton(f_win, text="Hide console on startup (restart)", variable=hc_var,
                       command=lambda: self.theme.set(bool(hc_var.get()), "ventana", "ocultar_consola")).pack(pady=2)
        tk.Button(f_win, text="Reset EVERYTHING", command=self._reset_theme_ui).pack(pady=12)

        # --- Lists (transparency + section backgrounds + batch) ---
        f_lst = ttk.Frame(nb)
        nb.add(f_lst, text="Lists")
        tk.Label(f_lst, text="BACKGROUND-relative transparency (0=opaque, 0.9=background shows)",
                 wraplength=480).pack(pady=(8, 0))
        lt_var = tk.DoubleVar(value=float(self.theme.get("lista", "transparencia", default=0.0) or 0.0))
        tk.Scale(f_lst, from_=0.0, to=0.9, resolution=0.05, orient="horizontal",
                 variable=lt_var,
                 command=lambda v: self._on_lista_transparencia_change(v)).pack(fill="x", padx=12)
        tk.Label(f_lst, text="Progressive batch (rows per load: 20-300)").pack(pady=(8, 0))
        lote_var = tk.IntVar(value=int(self.theme.get("lista", "lote_progresivo", default=80) or 80))
        tk.Scale(f_lst, from_=20, to=300, orient="horizontal", variable=lote_var,
                 command=lambda v: self.theme.set(int(float(v)), "lista", "lote_progresivo")).pack(fill="x", padx=12)
        tk.Label(f_lst, text="CUSTOM background per section (inherit = global background):",
                 font=("Segoe UI", 10, "bold")).pack(pady=(10, 4))
        for sec, lbl in (("inicio", "Home"), ("explorar", "Explore"),
                         ("buscar", "Search"), ("playlists", "Playlists"),
                         ("favoritas", "Liked"), ("cola", "Queue")):
            row = tk.Frame(f_lst)
            row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, text=f"{lbl}:", width=10, anchor="w").pack(side="left")
            tk.Button(row, text="Color...",
                      command=lambda s=sec: self._pick_section_color(s)).pack(side="left", padx=2)
            tk.Button(row, text="Image...",
                      command=lambda s=sec: self._pick_section_image(s)).pack(side="left", padx=2)
            tk.Button(row, text="Video...",
                      command=lambda s=sec: self._pick_section_video(s)).pack(side="left", padx=2)
            tk.Button(row, text="Inherit",
                      command=lambda s=sec: self._reset_section_bg(s)).pack(side="left", padx=2)
        tk.Button(f_lst, text="Show more (progressive load)",
                  command=lambda: self.show_more_rows()).pack(pady=8)

        # --- Playlist continuation (loop OFF) ---
        tk.Label(f_lst, text="PLAYLIST / QUEUE CONTINUATION (loop OFF):",
                 font=("Segoe UI", 10, "bold")).pack(pady=(10, 4))
        tk.Label(f_lst, text="When a playlist or the queue has NO loop "
                 "(neither list-loop nor single-song-loop), a separator bar "
                 "appears below the songs with recommendations from that "
                 "list. They are playable but are NOT added to the list.",
                 wraplength=480, justify="left").pack(pady=(0, 4))
        cont_var = tk.BooleanVar(value=bool(
            self.theme.get("lista", "recomendaciones_continuacion",
                             default=True) or True))
        tk.Checkbutton(f_lst, text="Show continuation recommendations",
                       variable=cont_var,
                       command=lambda: self.theme.set(
                           bool(cont_var.get()), "lista",
                           "recomendaciones_continuacion")).pack(pady=2)
        cant_var = tk.IntVar(value=int(
            self.theme.get("lista", "recomendaciones_cantidad", default=10)
            or 10))
        tk.Scale(f_lst, from_=3, to=30, orient="horizontal",
                 variable=cant_var,
                 command=lambda v: self.theme.set(int(float(v)), "lista",
                                                  "recomendaciones_cantidad")).pack(fill="x", padx=12)
        tk.Label(f_lst, text="How many recommended songs to show below the "
                 "playlist (3-30).", wraplength=480, justify="left").pack()

        # --- Responsive player bar ---
        tk.Label(f_lst, text="PLAYER BAR (responsive):",
                 font=("Segoe UI", 10, "bold")).pack(pady=(10, 4))
        resp_var = tk.BooleanVar(value=bool(
            self.theme.get("reproductor", "barra_responsive",
                             default=True) or True))
        tk.Checkbutton(f_lst, text="Shrink progress bar so buttons always fit",
                       variable=resp_var,
                       command=lambda: self.theme.set(
                           bool(resp_var.get()), "reproductor",
                           "barra_responsive")).pack(pady=2)
        min_var = tk.IntVar(value=int(
            self.theme.get("reproductor", "barra_altura_minima", default=60)
            or 60))
        tk.Scale(f_lst, from_=30, to=200, orient="horizontal",
                 variable=min_var,
                 command=lambda v: self.theme.set(int(float(v)), "reproductor",
                                                  "barra_altura_minima")).pack(fill="x", padx=12)
        tk.Label(f_lst, text="Minimum progress-bar width (px) when the window "
                 "is narrow. Controls never hide: the bar shortens instead.",
                 wraplength=480, justify="left").pack()

        # --- Sidebar (each BUTTON background) ---
        f_menu = ttk.Frame(nb)
        nb.add(f_menu, text="Menu")
        tk.Label(f_menu, text="Background of each SIDEBAR button\n(inherit = global Buttons style).",
                 wraplength=480, justify="left").pack(pady=(8, 4))
        for key, lbl in (("buscar", "⌕ Search"), ("playlists", "☰ Playlists"),
                         ("favoritas", "♥ Liked"), ("cola", "↳ Queue")):
            row = tk.Frame(f_menu)
            row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, text=f"{lbl}:", width=12, anchor="w").pack(side="left")
            tk.Button(row, text="Color...",
                      command=lambda k=key: self._pick_button_color(k)).pack(side="left", padx=2)
            tk.Button(row, text="Image...",
                      command=lambda k=key: self._pick_button_image(k)).pack(side="left", padx=2)
            tk.Button(row, text="Inherit",
                      command=lambda k=key: self._reset_button_bg(k)).pack(side="left", padx=2)
        tk.Label(f_menu, text="IMAGE is cropped to the button (178x34).\nCOLOR follows the shape (round/square).",
                 wraplength=480).pack(pady=(10, 4))

        # --- Panels (each PANEL background, like the menu) ---
        f_pan = ttk.Frame(nb)
        nb.add(f_pan, text="Panels")
        tk.Label(f_pan, text="Background of each UI PANEL\n(inherit = global background tints).\nIn lists COLOR is solid; IMAGE shows in gaps and tints.",
                 wraplength=480, justify="left").pack(pady=(8, 4))
        for pkey, plbl in (("barra_superior", "Top bar"),
                           ("lateral", "Sidebar"),
                           ("lateral_playlists", "YT playlist list"),
                           ("reproductor", "Player"),
                           ("progreso", "Song progress"),
                           ("volumen", "Volume")):
            row = tk.Frame(f_pan)
            row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, text=f"{plbl}:", width=16, anchor="w").pack(side="left")
            tk.Button(row, text="Color...",
                      command=lambda k=pkey: self._pick_panel_color(k)).pack(side="left", padx=2)
            tk.Button(row, text="Image...",
                      command=lambda k=pkey: self._pick_panel_image(k)).pack(side="left", padx=2)
            tk.Button(row, text="Inherit",
                      command=lambda k=pkey: self._reset_panel_bg(k)).pack(side="left", padx=2)

        # --- Video / Cover ---
        f_vid = ttk.Frame(nb)
        nb.add(f_vid, text="Video")
        tk.Label(f_vid, text="Mini video/cover panel in its own window.",
                 wraplength=480).pack(pady=(8, 4))
        tk.Label(f_vid, text="It can leave the window and follows it.\nDrag its bar to move it, ◢ to\nresize it. Position and size save automatically.",
                 wraplength=480).pack(pady=2)
        tk.Button(f_vid, text="Show / hide video panel",
                  command=self._toggle_video_panel).pack(pady=6)
        tk.Button(f_vid, text="Center video panel",
                  command=self._center_video_panel).pack(pady=2)
        tk.Label(f_vid, text="Video FPS (1-60, higher = smoother and more CPU)").pack(pady=(10, 0))
        fps_var = tk.IntVar(value=int(self.theme.get("video_panel", "fps", default=15) or 15))
        fps_lbl = tk.Label(f_vid, text=f"{fps_var.get()} fps")
        fps_lbl.pack()
        def _fps_chg(v):
            try:
                f = max(1, min(60, int(float(v))))
                self.theme.set(f, "video_panel", "fps")
                fps_lbl.configure(text=f"{f} fps")
            except Exception:
                pass
        tk.Scale(f_vid, from_=1, to=60, orient="horizontal", variable=fps_var,
                 command=_fps_chg).pack(fill="x", padx=12)
        # --- Stickers (floating images) ---

        # --- Stickers (floating images) ---
        f_stk = ttk.Frame(nb)
        nb.add(f_stk, text="Stickers")
        tk.Label(f_stk, text="Images over the UI (saved with position).\nThey can leave the window but follow it.\nDrag to move, right-click to delete.",
                 wraplength=480, justify="left").pack(pady=(8, 4))
        tk.Button(f_stk, text="Add floating image...",
                  command=self._add_sticker_dialog).pack(pady=6)
        tk.Button(f_stk, text="Delete all stickers",
                  command=self._clear_stickers).pack(pady=2)
        tk.Label(f_stk, text="Sidebar order: drag the ⌕/☰/♥/↳ buttons\nin the left bar to reorder (auto-saved).",
                 wraplength=480).pack(pady=(12, 4))

        # --- Themes ---
        f_thm = ttk.Frame(nb)
        nb.add(f_thm, text="Themes")
        self._theme_cur = tk.StringVar(value=self.theme_get_active_name() or "theme1")
        self._theme_names_var = tk.StringVar(value=())
        self._theme_list = tk.Listbox(f_thm, listvariable=self._theme_names_var,
                                      height=6, selectmode="browse")
        self._theme_list.pack(fill="both", expand=True, padx=8, pady=(8, 2))
        self._theme_list.bind("<<ListboxSelect>>", lambda e: self._theme_pick())
        btnr = tk.Frame(f_thm)
        btnr.pack(fill="x", padx=8, pady=4)
        tk.Button(btnr, text="Apply selected theme",
                  command=self._theme_apply_sel).pack(side="left", padx=2)
        tk.Button(btnr, text="Save current as...",
                  command=self._theme_save_as).pack(side="left", padx=2)
        tk.Button(btnr, text="Delete selected theme",
                  command=self._theme_del).pack(side="left", padx=2)
        self._theme_lbl = tk.Label(f_thm, text="", wraplength=460, fg="gray")
        self._theme_lbl.pack(fill="x", padx=8, pady=(0, 6))
        self._theme_refresh()

    # ----- custom font (.ttf/.otf) -----
    def _register_custom_font(self) -> bool:
        """Register the theme .ttf/.otf for the session (Windows: private
        process memory, installs nothing). Return True if OK."""
        try:
            p = str(self.theme.get("texto", "fuente_custom_path", default="") or "")
            if not p or not os.path.exists(p):
                return False
            if os.name == "nt":
                try:
                    import ctypes
                    # 0x10 = FR_PRIVATE (this process only)
                    return bool(ctypes.windll.gdi32.AddFontResourceExW(p, 0x10, 0))
                except Exception:
                    return False
            return True  # Linux/macOS: if installed, Tk will see it
        except Exception:
            return False

    # ---------- theme package helpers ----------
    def theme_get_active_name(self) -> str | None:
        try:
            from app.config import ThemeManager
            return ThemeManager.get_active_theme()
        except Exception:
            return None

    def _theme_refresh(self) -> None:
        try:
            from app.config import ThemeManager
            names = ThemeManager.list_themes()
        except Exception:
            names = []
        self._theme_list.delete(0, "end")
        for nm in names:
            self._theme_list.insert("end", nm)
        active = self.theme_get_active_name() or ""
        try:
            idx = names.index(active) if active in names else 0
        except ValueError:
            idx = 0
        self._theme_list.selection_clear(0, "end")
        if names:
            self._theme_list.selection_set(idx)
            self._theme_list.see(idx)
        self._theme_cur.set(active or (names[0] if names else ""))
        self._theme_lbl.configure(text=self._theme_desc(active))

    def _theme_desc(self, name: str | None) -> str:
        if not name:
            return "No theme active"
        try:
            from app.config import ThemeManager
            td = ThemeManager.theme_exists(name)
            dirty = ThemeManager("config/theme.json").is_dirty_vs(name)
            active = ThemeManager.get_active_theme()
            st = []
            st.append(f"Theme: {name}")
            st.append("active" if active == name else "inactive")
            if dirty:
                st.append("unsaved changes in current look")
            return " • ".join(st)
        except Exception:
            return name

    def _theme_pick(self) -> None:
        sel = self._theme_list.curselection()
        if not sel:
            return
        nm = self._theme_list.get(sel[0])
        self._theme_cur.set(nm)
        self._theme_lbl.configure(text=self._theme_desc(nm))

    def _theme_apply_sel(self) -> None:
        nm = self._theme_cur.get()
        if not ThemeManager.theme_exists(nm):
            self.status.configure(text=f"Theme '{nm}' not found.")
            return
        try:
            self.theme.load_theme(nm)
        except Exception as e:
            self.status.configure(text=f"Failed to apply theme: {e}")
            return
        self.apply_theme()
        # Restore stickers from the newly applied theme.
        try:
            self._restore_stickers()
        except Exception:
            pass
        self.status.configure(text=f"Theme '{nm}' applied ✔")

    def _theme_save_as(self) -> None:
        from tkinter import simpledialog
        nm = simpledialog.askstring("Save theme as", "Theme name (folder name under themes/):",
                                    initialvalue=self._theme_cur.get() or "theme1")
        if not nm:
            return
        try:
            self.theme.save_theme(nm)
        except Exception as e:
            self.status.configure(text=f"Failed to save theme: {e}")
            return
        self.apply_theme()
        self._theme_refresh()
        self.status.configure(text=f"Theme '{nm}' saved ✔")

    def _theme_del(self) -> None:
        nm = self._theme_cur.get()
        if not nm or not ThemeManager.theme_exists(nm):
            self.status.configure(text="Select a theme first.")
            return
        if nm == "DefaultTheme" and not messagebox.askyesno(
                "Delete theme",
                f"Delete the built-in theme '{nm}'? This cannot be undone."):
            return
        try:
            ThemeManager.delete_theme(nm)
        except Exception as e:
            self.status.configure(text=f"Failed to delete theme: {e}")
            return
        self._theme_refresh()
        self.status.configure(text=f"Theme '{nm}' deleted ✔")

    def _font_family(self) -> str:
        """Effective family: custom when a file exists, normal otherwise."""
        try:
            d = self.theme.data.get("texto", {})
            if str(d.get("fuente_custom_path", "") or "") and os.path.exists(str(d["fuente_custom_path"])):
                fam = str(d.get("fuente_familia", "") or "").strip()
                if fam:
                    return fam
            return str(d.get("fuente_familia", "Segoe UI"))
        except Exception:
            return "Segoe UI"

    # ---------- themeable widgets (search bar, sliders, panels) ----------
    # Keys live in the theme under "widgets" and are editable in Settings.
    _WIDGET_DEFAULTS = {
        "buscador": {"fondo": "#1e1e1e", "texto": "#e8e8e8",
                     "borde": "#3d3d3d", "cursor": "#e8e8e8",
                     "seleccion": "#4a4a4a"},
        "slider": {"fondo": "#1e1e1e", "pista": "#2b2b2b",
                   "pulgar": "#8c8c8c", "borde": "#3d3d3d",
                   "texto": "#b4b4b4"},
        "panel": {"fondo": "#1e1e1e", "borde": "#383838",
                  "texto": "#e8e8e8"},
        "menu": {"fondo": "#242424", "texto": "#e8e8e8",
                 "activo_fondo": "#3d3d3d", "activo_texto": "#f2f2f2",
                 "borde": "#383838"},
    }

    def _wcol(self, group: str, key: str, default: str = "") -> str:
        """One widget colour, falling back to a sane default."""
        try:
            v = str(((self.theme.data.get("widgets") or {}).get(group) or {})
                    .get(key, "") or "").strip()
            if v:
                return v
        except Exception:
            pass
        try:
            return str(self._WIDGET_DEFAULTS[group][key])
        except Exception:
            return default

    def _style_entry(self, w) -> None:
        try:
            w.configure(bg=self._wcol("buscador", "fondo"),
                        fg=self._wcol("buscador", "texto"),
                        insertbackground=self._wcol("buscador", "cursor"),
                        selectbackground=self._wcol("buscador", "seleccion"),
                        selectforeground=self._wcol("buscador", "texto"),
                        highlightbackground=self._wcol("buscador", "borde"),
                        highlightcolor=self._wcol("buscador", "borde"),
                        highlightthickness=1,
                        relief="solid", bd=1)
        except Exception:
            pass

    def _style_scale(self, w) -> None:
        """Colour a tk.Scale (progress bar, volume, Settings sliders).

        Options are applied one by one: a single unknown option would make
        Tk reject the WHOLE configure() call and leave the slider grey.
        (troughrelief is ttk-only and used to kill all of them.)
        """
        if w is None:
            return
        opts = {
            "troughcolor": self._wcol("slider", "pista"),
            "background": self._wcol("slider", "fondo"),
            "activebackground": self._wcol("slider", "pulgar"),
            "highlightbackground": self._wcol("slider", "borde"),
            "highlightcolor": self._wcol("slider", "pulgar"),
            "highlightthickness": 1,
            "fg": self._wcol("slider", "texto"),
            "relief": "flat",
            "bd": 1,
        }
        for key, val in opts.items():
            try:
                w.configure(**{key: val})
            except Exception:
                try:
                    w.cget(key)
                except Exception:
                    continue

    def _style_scrolledtext(self, w) -> None:
        try:
            w.configure(bg=self._wcol("panel", "fondo"),
                        fg=self._wcol("panel", "texto"),
                        highlightbackground=self._wcol("panel", "borde"),
                        highlightcolor=self._wcol("buscador", "borde"),
                        highlightthickness=1, insertbackground=self._wcol("buscador", "cursor"),
                        relief="solid", bd=1)
        except Exception:
            pass

    def apply_widgets_theme(self) -> None:
        """Re-colour the search bar and EVERY slider in the app.

        Walks the live widget tree, so sliders created later (Settings
        dialogs) get picked up too as long as apply_widgets_theme runs.
        """
        for w in (getattr(self, "search_entry", None),):
            if w is not None:
                self._style_entry(w)
        done = 0
        try:
            self._style_tree(self.root)
        except Exception:
            pass
        try:
            for win in list(getattr(self, "_channel_windows", {}).values() or []):
                self._style_tree(win)
        except Exception:
            pass
        try:
            self._style_scale(getattr(self, "progress", None))
            self._style_scale(getattr(self, "vol_scale", None))
        except Exception:
            pass
        return done

    def _style_menu(self, m) -> None:
        """Colour a right-click menu from the theme (Windows honours these)."""
        if m is None:
            return
        opts = {
            "background": self._wcol("menu", "fondo"),
            "foreground": self._wcol("menu", "texto"),
            "activebackground": self._wcol("menu", "activo_fondo"),
            "activeforeground": self._wcol("menu", "activo_texto"),
            "disabledforeground": self._wcol("menu", "borde"),
            "bd": 0,
            "relief": "solid",
            "font": (self._font_family(),
                     int(self.theme.get("texto", "fuente_tam_lista", default=11) or 11)),
        }
        for k, v in opts.items():
            try:
                m.configure(**{k: v})
            except Exception:
                pass
        # separators and the border
        try:
            i = m.index("end")
            while i >= 0:
                try:
                    if m.type(i) == "separator":
                        m.entryconfigure(
                            i, background=self._wcol("menu", "borde"))
                except Exception:
                    pass
                i -= 1
        except Exception:
            pass
        return m

    def _new_menu(self, master=None) -> "tk.Menu":
        """A themed context menu (use instead of tk.Menu for popups)."""
        try:
            m = tk.Menu(master or self.root, tearoff=0)
        except Exception:
            return tk.Menu(self.root, tearoff=0)
        return self._style_menu(m)

    def _style_tree(self, w, depth: int = 0) -> int:
        """Apply widget colours recursively. Returns how many were changed."""
        n = 0
        if w is None or depth > 14:
            return 0
        try:
            cn = str(w.winfo_class())
        except Exception:
            return 0
        try:
            if cn in ("Scale",):
                self._style_scale(w); n += 1
            elif cn == "Entry":
                self._style_entry(w); n += 1
            elif cn in ("Text",):
                self._style_scrolledtext(w); n += 1
            elif cn in ("Scrollbar",):
                w.configure(troughcolor=self._wcol("panel", "fondo"),
                            bg=self._wcol("slider", "fondo"),
                            activebackground=self._wcol("slider", "pulgar"),
                            highlightthickness=0, bd=0, relief="flat")
                n += 1
        except Exception:
            pass
        try:
            for ch in w.winfo_children():
                n += self._style_tree(ch, depth + 1)
        except Exception:
            pass
        return n

    def _pick_widget_color(self, group: str, key: str, swatch) -> None:
        from tkinter import colorchooser
        cur = self._wcol(group, key)
        try:
            picked = colorchooser.askcolor(color=cur, parent=self.root)[1]
        except Exception:
            return
        if not picked:
            return
        self._set_widget_color(group, key, picked, swatch)

    def _reset_widget_color(self, group: str, key: str, swatch) -> None:
        try:
            dflt = self._WIDGET_DEFAULTS[group][key]
        except Exception:
            return
        self._set_widget_color(group, key, dflt, swatch)

    def _set_widget_color(self, group: str, key: str, value: str,
                          swatch=None) -> None:
        widgets = self.theme.data.setdefault("widgets", {})
        grp = widgets.setdefault(group, {})
        grp[key] = value
        try:
            self.theme.save()
        except Exception:
            pass
        try:
            if swatch is not None:
                swatch.configure(bg=value)
        except Exception:
            pass
        self.apply_widgets_theme()

    def _pick_custom_font(self) -> None:
        from tkinter import simpledialog
        p = filedialog.askopenfilename(title="Custom font",
                                       filetypes=[("Fonts", "*.ttf *.otf"), ("All", "*.*")])
        if not p:
            return
        fam0 = os.path.splitext(os.path.basename(p))[0]
        fam = simpledialog.askstring("Custom font",
                                     "Font FAMILY name\n(usually the name before the dash,\ne.g. 'MyFont-Bold' → 'MyFont'):",
                                     initialvalue=fam0)
        if fam is None:
            return
        fam = (fam or "").strip() or fam0
        self.theme.set(p, "texto", "fuente_custom_path")
        self.theme.set(fam, "texto", "fuente_familia")
        self._register_custom_font()
        self.apply_theme()

    def _clear_custom_font(self) -> None:
        try:
            self.theme.set("", "texto", "fuente_custom_path")
            self.apply_theme()
        except Exception:
            pass

    def _pick_color(self, section: str, key: str) -> None:
        cur = self.theme.get(section, key, default="#ffffff")
        c = colorchooser.askcolor(color=cur)
        if c and c[1]:
            self.theme.set(c[1], section, key)
            self.apply_theme()

    def _pick_file(self, section: str, key: str, types) -> None:
        p = filedialog.askopenfilename(filetypes=types)
        if p:
            self.theme.set(p, section, key)
            self.apply_theme()

    def _pick_button_color(self, key: str) -> None:
        c = colorchooser.askcolor(title=f"Button color: {key}")
        if c and c[1]:
            try:
                cfg = dict(self._side_button_cfg(key) or {})
                cfg.update({"modo": "color", "color": c[1], "imagen_path": ""})
                self.theme.data.setdefault("fondos_botones", {})[key] = cfg
                try:
                    cache = getattr(self, "_btn_face_cache", None)
                    if isinstance(cache, dict):
                        for ck in [k for k in cache if k.startswith(key + "|")]:
                            cache.pop(ck, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _pick_button_image(self, key: str) -> None:
        p = filedialog.askopenfilename(title=f"Button image: {key}",
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if p:
            try:
                cfg = dict(self._side_button_cfg(key) or {})
                cfg.update({"modo": "imagen", "imagen_path": p, "color": ""})
                self.theme.data.setdefault("fondos_botones", {})[key] = cfg
                try:
                    cache = getattr(self, "_btn_face_cache", None)
                    if isinstance(cache, dict):
                        for ck in [k for k in cache if k.startswith(key + "|")]:
                            cache.pop(ck, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _reset_button_bg(self, key: str) -> None:
        try:
            self.theme.data.setdefault("fondos_botones", {})[key] = {
                "modo": "heredar", "color": "", "imagen_path": ""}
            try:
                cache = getattr(self, "_btn_face_cache", None)
                if isinstance(cache, dict):
                    for ck in [k for k in cache if k.startswith(key + "|")]:
                        cache.pop(ck, None)
            except Exception:
                pass
            self.theme.save()
            self.apply_theme()
        except Exception:
            pass

    def _pick_section_color(self, section: str) -> None:
        c = colorchooser.askcolor(title=f"Background color: {section}")
        if c and c[1]:
            try:
                cfg = dict(self._section_cfg(section) or {})
                cfg.update({"modo": "color", "color": c[1], "imagen_path": "", "video_path": ""})
                self.theme.data.setdefault("fondos_secciones", {})[section] = cfg
                try:
                    getattr(self, "_sec_avg_cache", {}).pop(section, None)
                except Exception:
                    pass
                try:
                    getattr(self, "_sec_src_cache", {}).pop(section, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _pick_section_image(self, section: str) -> None:
        p = filedialog.askopenfilename(title=f"Background image: {section}",
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if p:
            try:
                cfg = dict(self._section_cfg(section) or {})
                cfg.update({"modo": "imagen", "imagen_path": p, "video_path": ""})
                self.theme.data.setdefault("fondos_secciones", {})[section] = cfg
                try:
                    getattr(self, "_sec_avg_cache", {}).pop(section, None)
                except Exception:
                    pass
                try:
                    getattr(self, "_sec_src_cache", {}).pop(section, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _pick_section_video(self, section: str) -> None:
        p = filedialog.askopenfilename(title=f"Background video: {section}",
                                       filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.webm")])
        if p:
            try:
                cfg = dict(self._section_cfg(section) or {})
                cfg.update({"modo": "video", "video_path": p, "imagen_path": ""})
                self.theme.data.setdefault("fondos_secciones", {})[section] = cfg
                try:
                    getattr(self, "_sec_avg_cache", {}).pop(section, None)
                except Exception:
                    pass
                try:
                    getattr(self, "_sec_src_cache", {}).pop(section, None)
                except Exception:
                    pass
                self.theme.save()
                self.apply_theme()
            except Exception:
                pass

    def _reset_section_bg(self, section: str) -> None:
        try:
            self.theme.data.setdefault("fondos_secciones", {})[section] = {
                "modo": "heredar", "color": "", "color2": "",
                "imagen_path": "", "video_path": ""}
            try:
                getattr(self, "_sec_avg_cache", {}).pop(section, None)
            except Exception:
                pass
            try:
                getattr(self, "_sec_src_cache", {}).pop(section, None)
            except Exception:
                pass
            self.theme.save()
            self.apply_theme()
        except Exception:
            pass

    def _center_video_panel(self) -> None:
        try:
            self._ensure_video_panel()
            rw = self.root.winfo_width() or 1100
            rh = self.root.winfo_height() or 700
            cfg = self.theme.data.get("video_panel", {}) or {}
            w, h = int(cfg.get("w", 320)), int(cfg.get("h", 240))
            dx, dy = max(0, (rw - w) // 2), max(0, (rh - h) // 2 - 40)
            self.theme.set(int(dx), "video_panel", "dx")
            self.theme.set(int(dy), "video_panel", "dy")
            self.theme.set(True, "video_panel", "visible")
            try:
                self._video_panel.deiconify()
            except Exception:
                pass
            self._reposition_video()
        except Exception:
            pass

    def _open_video_res_menu(self) -> None:
        """Open resolution menu from the gear icon on the video panel bar."""
        try:
            menu = self._new_menu(self._video_panel)
            resolutions = [
                ("144p (256x144)", 256, 144),
                ("240p (426x240)", 426, 240),
                ("360p (640x360)", 640, 360),
                ("480p (854x480)", 854, 480),
                ("720p (1280x720)", 1280, 720),
                ("1080p (1920x1080)", 1920, 1080),
                ("1440p (2560x1440)", 2560, 1440),
                ("2160p 4K (3840x2160)", 3840, 2160),
            ]
            try:
                _rw, _rh = self._video_res()
            except Exception:
                _rw, _rh = 640, 360
            for label, w, h in resolutions:
                if w == _rw and h == _rh:
                    label = "✓ " + label
                menu.add_command(label=label,
                                 command=lambda w=w, h=h: self._apply_video_res_from_menu(w, h))
            menu.add_separator()
            menu.add_command(label="Custom size...",
                             command=self._open_custom_res_dialog)
            try:
                # At the mouse pointer: in fullscreen the panel corner is (0,0),
                # which would throw the menu to the screen edge.
                try:
                    _px = int(self._video_panel.winfo_pointerx())
                    _py = int(self._video_panel.winfo_pointery())
                except Exception:
                    _px = int(self._video_panel.winfo_rootx())
                    _py = int(self._video_panel.winfo_rooty() + 26)
                menu.tk_popup(_px, _py)
            finally:
                menu.grab_release()
        except Exception as e:
            self.status.configure(text=f"Resolution menu error: {e}")

    def _apply_video_res_from_menu(self, w: int, h: int) -> None:
        """Apply VIDEO resolution (internal pixels). The window is NOT resized:
        window size is changed with the window corners/edges. Same song kept."""
        try:
            w = max(160, min(3840, w))
            h = max(120, min(2160, h))
            self.theme.set(w, "video_panel", "res_w")
            self.theme.set(h, "video_panel", "res_h")
            try:
                self.status.configure(text=f"Switching video to {w}x{h}…")
            except Exception:
                pass
            # Reload the stream at the new resolution on the SAME song
            # (explicit size: the window size is irrelevant here).
            # The last frame stays on screen until the first new frame lands,
            # so the switch looks instant (video URL is cached per song).
            try:
                self._video_video_id = ""
                self._refresh_video_panel(force=True, pw=int(w), ph=int(h))
            except Exception:
                pass
            try:
                self._video_osd(f"{w}x{h}")
            except Exception:
                pass
            self.status.configure(text=f"Video resolution set to {w}x{h} (window unchanged) ✔")
        except Exception as e:
            self.status.configure(text=f"Invalid resolution: {e}")

    def _open_custom_res_dialog(self) -> None:
        """Open dialog to enter custom video resolution (window NOT resized)."""
        import tkinter.simpledialog as sd
        try:
            _rw, _rh = self._video_res()
        except Exception:
            _rw, _rh = 640, 360
        res = sd.askstring("Custom Resolution", "Enter video resolution (WxH, e.g. 640x360):",
                           initialvalue=f"{int(_rw)}x{int(_rh)}")
        if res:
            try:
                parts = str(res).split("x")
                if len(parts) == 2:
                    w = int(parts[0])
                    h = int(parts[1])
                    self._apply_video_res_from_menu(w, h)
                else:
                    self.status.configure(text="Invalid format. Use WxH (e.g. 320x180)")
            except Exception as e:
                self.status.configure(text=f"Invalid resolution: {e}")

    def _clear_stickers(self) -> None:
        try:
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    st.get("win").destroy()
                except Exception:
                    pass
            self._stickers = []
            self._save_stickers()
            self.status.configure(text="Stickers deleted ✔")
        except Exception:
            pass

    def _pick_shape_png(self) -> None:
        p = filedialog.askopenfilename(title="PNG shape for buttons",
                                       initialdir=self._icons_dir(),
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp *.webp")])
        if p:
            self.theme.set(p, "botones", "forma_custom_path")
            self.theme.set("custom", "botones", "forma")
            self._shape_cache.clear()
            self.apply_theme()
            self._update_forma_label()

    def _update_forma_label(self) -> None:
        try:
            p = self.theme.get("botones", "forma_custom_path", default="")
            fm = self.theme.get("botones", "forma", default="redondo")
            self._forma_lbl.configure(text=f"Shape: {fm}" + (f" ({os.path.basename(p)})" if p else ""))
        except Exception:
            pass

    def _change_icon(self, key: str, preview_label=None) -> None:
        from tkinter import simpledialog
        cur = self.theme.get("iconos", key, default="")
        ans = simpledialog.askstring("Icon", f"Icon for '{key}' (emoji/letter):\nCurrent: {cur}\n"
                                              "Leave empty to pick an IMAGE from assets/icons.")
        if ans is None:
            return
        if ans is not None and ans != "":
            self.theme.set(ans[:8], "iconos", key)
            self._icon_cache.clear()
            self.apply_theme()
            if preview_label is not None:
                self._update_icon_preview(key, preview_label)
            return
        if ans is None:
            return
        # pick image: it REALLY loads and applies instantly
        p = filedialog.askopenfilename(title=f"Image for {key}",
                                       initialdir=self._icons_dir(),
                                       filetypes=[("Image", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if p:
            photo = self._load_icon_image(p, 40)
            if photo is None:
                messagebox.showerror("Icon", "Could not load that image.")
                return
            self.theme.set(p, "iconos", key)
            self.apply_theme()
            if preview_label is not None:
                self._update_icon_preview(key, preview_label)

    def _reset_icon(self, key: str, preview_label=None) -> None:
        """Back to the built-in icon (the one the theme shipped with)."""
        try:
            from app.config import DEFAULT_THEME
            dflt = str((DEFAULT_THEME.get("iconos") or {}).get(key, "") or "")
            if not dflt:
                dflt = "?"
            self.theme.set(dflt, "iconos", key)
            try:
                self._icon_cache.clear()
            except Exception:
                pass
            self.apply_theme()
            if preview_label is not None:
                self._update_icon_preview(key, preview_label)
            try:
                self.status.configure(text=f"'{key}' back to default: {dflt}")
            except Exception:
                pass
        except Exception as e:
            try:
                self.status.configure(text=f"Could not reset '{key}': {e}")
            except Exception:
                pass

    @staticmethod
    def _icons_dir() -> str:
        """Shared folder for icon / shape images (created on demand)."""
        d = os.path.join("assets", "icons")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def _update_icon_preview(self, key: str, label: tk.Label) -> None:
        try:
            cur = self.theme.get("iconos", key, default="")
            kind, val = self._resolve_icon(cur)
            if kind == "image":
                photo = self._load_icon_image(val, 32)
                if photo is not None:
                    label.configure(image=photo, text="")
                    label._prev = photo
                    return
            label.configure(image="", text=str(val)[:8])
        except Exception:
            pass

    # ---------- Last.fm play counts ----------
    def _ed_album(self, track: dict) -> str:
        """Album of a row, after the per-song edits (same as the player bar)."""
        try:
            return str(self._meta_edited(track).get("album") or "")
        except Exception:
            return str((track or {}).get("album") or "")
    def _open_album_in_app(self, track: dict) -> None:
        """Click on the album name: open the album inside the app.

        Uses the album id when YT Music gave us one, otherwise searches by
        name and shows the album in the main list (never a web browser).
        """
        try:
            t = dict(track or {})
            aid = str(t.get("albumId") or "")
            name = str(_ed_album(t) or t.get("album") or "")
            if not aid and not name:
                try:
                    self.status.configure(text="This song has no album.")
                except Exception:
                    pass
                return
            if aid:
                try:
                    self.status.configure(text=f"Loading album: {name or aid}...")
                except Exception:
                    pass
                def _bg_album():
                    try:
                        title, tracks = self.client.get_album_tracks(aid)
                    except Exception:
                        title, tracks = "", []
                    self._call_ui(self._show_album_in_app, title or name, tracks)
                threading.Thread(target=_bg_album, daemon=True).start()
                return
            q = f"{t.get('artist', '')} {name}".strip()
            try:
                self.status.configure(text=f"Finding album: {name}...")
            except Exception:
                pass

            def _bg_find():
                try:
                    res = self.client.search(q, limit=12) or []
                except Exception:
                    res = []
                pick = None
                for r in res:
                    if str(r.get("album") or "") == name:
                        pick = r
                        break
                self._call_ui(self._show_album_in_app, name, [], pick)

            threading.Thread(target=_bg_find, daemon=True).start()
        except Exception:
            pass

    def _open_album_by_id(self, album_id: str, album_name: str = "") -> None:
        """Open a YouTube Music album INSIDE the app (never a web browser).

        album_id is the real browse id (MPREb_*) that came from the channel's
        Albums tab, so this always shows the channel's own release.
        """
        aid = str(album_id or "").strip()
        if not aid:
            try:
                self.status.configure(text="That row has no album.")
            except Exception:
                pass
            return
        try:
            self.status.configure(text=f"Loading album: {album_name or aid}...")
        except Exception:
            pass

        def _bg():
            title, tracks = self.client.get_music_album(aid)
            self._call_ui(self._album_loaded, aid, album_name, title, tracks)

        threading.Thread(target=_bg, daemon=True).start()

    def _album_loaded(self, album_id: str, album_name: str, title: str,
                      tracks: list[dict]) -> None:
        try:
            name = title or album_name or "Album"
            if not tracks:
                try:
                    self.status.configure(
                        text=f"No playable tracks on '{name}'.")
                except Exception:
                    pass
                return
            self.current_section = "buscar"
            self._album_mode = True
            # Reset continuation state for the new album.
            self._pl_continuation_shown = False
            self._pl_continuation_rendered = False
            self._show_tracks_result(tracks, f"\U0001f4bd {name}")
            try:
                self.status.configure(
                    text=f"Album: {name} ({len(tracks)} tracks)")
            except Exception:
                pass
        except Exception:
            pass

    def _show_album_in_app(self, title: str, tracks: list[dict],
                           seed: dict | None = None) -> None:
        """Render an album inside the main window (or find it and open it)."""
        try:
            tracks = [t for t in (tracks or []) if isinstance(t, dict)]
            if tracks:
                self.current_section = "buscar"
                self._show_tracks_result(tracks, f"▤ {title}")
                try:
                    self.status.configure(text=f"Album: {title} ({len(tracks)})")
                except Exception:
                    pass
                return
            if seed and seed.get("albumId"):
                try:
                    self._menu_view_album(seed)
                except Exception:
                    pass
                return
            try:
                self.status.configure(
                    text=f"Could not open the album '{title}'.")
            except Exception:
                pass
        except Exception:
            pass
    def _refresh_row_text(self, lbl) -> None:
        """Title + channel + play count, painted in place.

        Background results (channel, play count) call this on the single
        label instead of re-rendering the list: that was the flicker, the
        endless thumbnail restarts and the crashes on long lists.
        """
        try:
            title = str(getattr(lbl, "_title", "") or "")
            chan = ("" if getattr(lbl, "_has_channel_label", False)
                    else str(getattr(lbl, "_chan", "") or ""))
            base = f"{title} — {chan}" if chan else title
            n = self._play_counts.get(str(getattr(lbl, "_vid", "") or ""))
            # Only show the count if we actually know it (n >= 0).
            # -1 = unknown, never played, or not found: show nothing.
            if n is not None and n >= 0:
                lbl.configure(text=f"{base}  ⟳{int(n)}")
            else:
                lbl.configure(text=base)
        except Exception:
            pass
    def refresh_play_count(self, video_id: str) -> None:
        """Re-ask Last.fm for this song with its CURRENT (edited) metadata.

        Editing a song changes the artist/title Last.fm is asked about, but
        the count was cached per videoId, so the row kept showing the number
        of the OLD metadata forever. Here we drop the stale value, forget the
        disk cache for the old artist|track, repaint the row without the
        count and queue a fresh lookup.
        """
        vid = str(video_id or "")
        if not vid:
            return
        try:
            t = None
            for bag in (getattr(self, "current_list_full", []) or [],
                        getattr(self, "current_list", []) or []):
                for x in bag:
                    if isinstance(x, dict) and str(x.get("videoId", "")) == vid:
                        t = x
                        break
                if t is not None:
                    break
            # The song editor works on the PLAYING song, which is often not
            # in the visible list at all; without this fallback the count
            # could never be refreshed for it.
            if t is None:
                cur = getattr(self.player, "current", None) or {}
                if isinstance(cur, dict) and str(cur.get("videoId", "")) == vid:
                    t = cur
            if t is None:
                t = {"videoId": vid}
            ed = self._meta_edited(t)
            old_a = old_t = ""
            try:
                old_a = str(t.get("artist") or "")
                old_t = str(t.get("title") or "")
            except Exception:
                pass
            # forget the on-disk count for the OLD metadata (and the new one,
            # in case the user toggles back and forth)
            try:
                cache = getattr(self.lastfm, "_pc_cache", None)
                if isinstance(cache, dict):
                    stale = [k for k in list(cache.keys())
                             if k == f"{old_a.lower()}|{old_t.lower()}"]
                    new_a = str(ed.get("artist") or old_a or "")
                    new_t = str(ed.get("track") or old_t or "")
                    if new_a and new_t:
                        stale.append(f"{new_a.lower()}|{new_t.lower()}")
                    for k in stale:
                        cache.pop(k, None)
                    try:
                        import json as _js
                        cpath = getattr(self.lastfm, "_pc_path",
                                        os.path.join("cache", "lastfm_counts.json"))
                        with open(cpath, "w", encoding="utf-8") as f:
                            _js.dump(cache, f, ensure_ascii=False)
                    except Exception:
                        pass
            except Exception:
                pass
            self._play_counts.pop(vid, None)
            for lbl in list(self._play_labels.get(vid, [])):
                try:
                    if lbl.winfo_exists():
                        self._refresh_row_text(lbl)
                except Exception:
                    pass
            self._enqueue_play_counts([t])
        except Exception:
            pass

    def _enqueue_play_counts(self, tracks: list[dict]) -> None:
        """Ask Last.fm how many times each visible song was played.

        Only when the account is linked, throttled, cached for a month and
        never blocking the UI.
        """
        try:
            if not getattr(self.lastfm, "linked", False):
                return
            todo = []
            for t in (tracks or [])[:18]:
                if not isinstance(t, dict) or t.get("_playlist_id"):
                    continue
                vid = str(t.get("videoId", "") or "")
                if not vid or vid in self._play_counts:
                    continue
                try:
                    ed = self._meta_edited(t)
                    a = str(ed.get("artist") or t.get("artist") or "")
                    ti = str(ed.get("track") or t.get("title") or "")
                except Exception:
                    a, ti = str(t.get("artist") or ""), str(t.get("title") or "")
                if not a or not ti:
                    continue
                todo.append((vid, a, ti))
            if not todo:
                return
            if getattr(self, "_pc_queue", None) is None:
                self._pc_queue = []
                self._pc_busy = False
            self._pc_queue.extend(todo)
            if self._pc_busy:
                return
            self._pc_busy = True

            def _worker():
                import time as _t
                try:
                    while self._pc_queue:
                        vid, a, ti = self._pc_queue.pop(0)
                        try:
                            n = self.lastfm.playcount(a, ti)
                        except Exception:
                            n = -1
                        # Always report back, including -1: the player bar
                        # needs to know it is "not on Last.fm" and must stop
                        # waiting, instead of staying on "…".
                        self._call_ui(self._apply_play_count, vid,
                                      int(n if n is not None else -1))
                        _t.sleep(0.35)
                finally:
                    self._pc_busy = False

            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def _set_playcount_text(self, text: str) -> None:
        """Player bar play counter ('' hides it)."""
        try:
            lbl = getattr(self, "playcount_lbl", None)
            if lbl is None:
                return
            lbl.configure(text=str(text or ""))
        except Exception:
            pass

    def _refresh_playcount_ui(self, vid: str) -> None:
        """Repaint the player counter when the current song's count arrives."""
        try:
            cur = getattr(self.player, "current", None) or {}
            if str(cur.get("videoId", "") or "") != str(vid or ""):
                return
            n = self._play_counts.get(str(vid))
            if n is None:
                self._set_playcount_text("…")
                return
            n = int(n)
            if n < 0:
                # Last.fm does not know this track: say nothing rather than
                # invent a number.
                self._set_playcount_text("")
                return
            if n == 0:
                # Last.fm knows the track and you never played it.
                self._set_playcount_text("⟳ 0 plays on Last.fm")
            else:
                self._set_playcount_text(
                    f"⟳ {n} play{'s' if n != 1 else ''} on Last.fm")
        except Exception:
            pass

    def _apply_play_count(self, vid: str, n: int) -> None:
        """Store the count and repaint ONLY the rows of that song."""
        try:
            self._play_counts[str(vid)] = int(n)
            # Drop labels of rows that no longer exist: render_list()
            # destroys them and the list would keep growing forever.
            for key, lst in list(self._play_labels.items()):
                alive = []
                for lbl in lst:
                    try:
                        if lbl.winfo_exists():
                            alive.append(lbl)
                            self._refresh_row_text(lbl)
                    except Exception:
                        continue
                if alive:
                    self._play_labels[key] = alive
                else:
                    self._play_labels.pop(key, None)
            self._refresh_playcount_ui(str(vid))
        except Exception:
            pass

# ---------- channel browser ----------
    def _ch_bg(self) -> str:
        """Window background that matches the active theme."""
        try:
            return self._band(0.35)
        except Exception:
            return "#1e1e1e"

    def _ch_fg(self) -> str:
        try:
            return str(self.theme.data["texto"]["color_titulo"])
        except Exception:
            return "#d8d8d8"

    def _enqueue_channel_lookups(self, tracks: list[dict]) -> None:
        """Rows from YT Music do not carry the uploader; fetch it lazily.

        One worker thread, a few videos at a time, and the row is repainted
        only when the answer actually changes something.
        """
        try:
            todo = []
            for t in (tracks or [])[:24]:
                if not isinstance(t, dict):
                    continue
                vid = str(t.get("videoId", "") or "")
                if not vid or t.get("channel") or t.get("_playlist_id"):
                    continue
                todo.append(vid)
            if not todo:
                return
            if getattr(self, "_channel_queue", None) is None:
                self._channel_queue = list()
                self._channel_busy = False
            q = self._channel_queue
            for v in todo:
                if v not in q:
                    q.append(v)
            if self._channel_busy:
                return
            self._channel_busy = True

            def _worker():
                try:
                    while q:
                        vid = q.pop(0)
                        try:
                            name, cid = self.client.get_video_channel(vid)
                        except Exception:
                            continue
                        if not name:
                            continue
                        self._call_ui(self._apply_channel, vid, name, cid)
                finally:
                    self._channel_busy = False

            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def _apply_channel(self, vid: str, name: str, cid: str) -> None:
        """Store the channel on the track and repaint ONLY its rows.

        It used to call render_list(), which rebuilt every row for every
        resolved video: on a long list that is dozens of rebuilds, constant
        flicker and thumbnails that never finished loading.
        """
        try:
            name = str(name or "")
            if name.lower().endswith(" - topic"):
                name = name[: -len(" - topic")].strip()
            for lst in (getattr(self, "current_list_full", None) or [],
                        getattr(self, "current_list", None) or [],
                        getattr(self, "player", None) and self.player.queue or []):
                for t in lst:
                    if isinstance(t, dict) and t.get("videoId") == vid:
                        t["channel"] = name
                        if cid:
                            t["channelId"] = cid
            cur = dict(getattr(self.player, "current", None) or {})
            if cur.get("videoId") == vid:
                cur["channel"] = name
                if cid:
                    cur["channelId"] = cid
                try:
                    self.player.current = cur
                except Exception:
                    pass
                self._update_song_ui(cur)
            for lbl in list(self._play_labels.get(str(vid), [])):
                try:
                    if lbl.winfo_exists():
                        lbl._chan = name
                        self._refresh_row_text(lbl)
                except Exception:
                    continue
        except Exception:
            pass

    def _open_channel_from_row(self, track: dict, *_ignored) -> None:
        """Clicked the uploader name: open THAT channel, never the album.

        *_ignored swallows the two extra arguments the old context-menu entry
        used to pass; it raised a TypeError, so "Open channel" from the
        right-click menu silently did nothing and the user ended up using
        "View album" instead (which is what they reported as "it opens the
        album").
        """
        t = track if isinstance(track, dict) else {}
        vid = str(t.get("videoId", "") or "")
        name = str(t.get("channel") or "") or str(t.get("artist") or "")
        artist = str(t.get("artist") or "") or str(t.get("musicArtist") or "")
        cid = str(t.get("channelId") or "")
        if not vid:
            try:
                self.status.configure(text="That row has no channel.")
            except Exception:
                pass
            return
        try:
            self.status.configure(
                text=f"Opening channel of {name or 'this video'}...")
        except Exception:
            pass

        def _bg():
            # The channel of the UPLOAD. This never looks at albumId on
            # purpose: clicking the uploader must open the uploader.
            n, c = "", ""
            try:
                n, c = self.client.get_video_channel(vid, artist)
            except Exception:
                pass
            if not c and cid:
                c = cid
            if not n and name:
                n = name
            if not c:
                self._call_ui(
                    self.status.configure,
                    text="Could not get the channel of this video.")
                return
            self._call_ui(self.open_channel_window, c, n or "")

        threading.Thread(target=_bg, daemon=True).start()

    def _open_channel_direct(self, channel_id: str, channel_name: str) -> None:
        """Open a channel window by channel ID (direct, no search needed)."""
        try:
            self.status.configure(text=f"Opening channel '{channel_name or channel_id}'...")
        except Exception:
            pass
        self.open_channel_window(channel_id, channel_name or "")

    @staticmethod
    def _first_video_from_page(page: dict) -> str:
        """Scan the channel page data for the first videoId (any tab)."""
        try:
            data = page.get("_data") if isinstance(page, dict) else None
            if not isinstance(data, dict):
                return ""
            found: list[str] = []

            def _walk(node):
                if len(found) > 0:
                    return
                if isinstance(node, dict):
                    vid = node.get("videoId")
                    if isinstance(vid, str) and vid and len(vid) == 11:
                        found.append(vid)
                        return
                    for v in node.values():
                        _walk(v)
                elif isinstance(node, list):
                    for v in node:
                        _walk(v)

            _walk(data)
            return found[0] if found else ""
        except Exception:
            return ""

    def open_channel_window(self, channel_id: str, channel_name: str = "") -> None:
        """Channel window: header + real tabs (Videos, Songs, Albums,
        Playlists). Rows play; playlist rows open that playlist.

        Never raises: a broken channel is reported in the window itself.
        """
        cid = str(channel_id or "").strip()
        if not cid:
            try:
                self.status.configure(
                    text="No channel ID available for this result.")
            except Exception:
                pass
            return
        try:
            self._open_channel_window_impl(cid, channel_name or "")
        except Exception as e:
            # A channel window must never crash the player.
            try:
                self.status.configure(
                    text=f"Channel window error: {str(e)[:140]}")
            except Exception:
                pass

    def _open_channel_window_impl(self, cid: str, channel_name: str) -> None:
        """Actual channel window creation (called with try/except around it)."""
        if getattr(self, "_channel_windows", None) is None:
            self._channel_windows = {}
        existing = self._channel_windows.get(cid)
        if existing is not None:
            try:
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return
            except Exception:
                self._channel_windows.pop(cid, None)

        # True own title bar like the main window: no Windows frame,
        # drag to move, minimise / maximise / close buttons match it.
        win = tk.Toplevel(self.root)
        # This window paints its own title bar right below, so the Windows
        # caption has to go: otherwise both bars showed at once.
        self._frameless_toplevel(win, own_bar=True)
        self._channel_windows[cid] = win
        win.title(channel_name or "Channel")
        win.geometry("900x680")
        win.configure(bg=self._ch_bg())
        try:
            win.transient(self.root)
        except Exception:
            pass
        # NOTE: no -topmost here. It used to steal focus from other apps
        # and made the channel window impossible to interact with.

        fam = self._font_family()
        bg = self._ch_bg()
        fg = self._ch_fg()
        try:
            accent = str(self.theme.data["botones"]["color_fondo"])
        except Exception:
            accent = str(self.theme.get("texto", "color_acento", default="#4a4a4a"))

        # ----- custom title bar (same look as the main window) -----
        titlebar = tk.Frame(win, bg=bg, highlightthickness=0, bd=0)
        titlebar.pack(side="top", fill="x")

        drag: dict = {"x": 0, "y": 0}

        def _on_drag_start(ev):
            try:
                drag["x"] = ev.x_root
                drag["y"] = ev.y_root
            except Exception:
                pass

        def _on_drag_move(ev):
            try:
                dx = ev.x_root - drag["x"]
                dy = ev.y_root - drag["y"]
                if dx or dy:
                    drag["x"] = ev.x_root
                    drag["y"] = ev.y_root
                    x = win.winfo_x() + dx
                    y = win.winfo_y() + dy
                    win.geometry(f"+{x}+{y}")
            except Exception:
                pass

        def _on_drag_release(ev):
            pass

        titlebar.bind("<Button-1>", _on_drag_start)
        titlebar.bind("<B1-Motion>", _on_drag_move)
        titlebar.bind("<ButtonRelease-1>", _on_drag_release)

        av = tk.Label(titlebar, text="▶", bg=bg, fg=fg,
                      font=(fam, 18, "bold"), width=4, height=1, cursor="hand2")
        av.pack(side="left", padx=(10, 6), pady=4)
        title_lbl = tk.Label(titlebar, text=channel_name or "Loading...",
                             bg=bg, fg=fg,
                             font=(fam, 12, "bold"), anchor="w",
                             cursor="hand2")
        title_lbl.pack(side="left", padx=6, pady=4, fill="x", expand=True)

        btnf = tk.Frame(titlebar, bg=bg)
        btnf.pack(side="right", padx=(4, 10), pady=4)

        def _make_win_btn(txt, cmd):
            b = tk.Button(btnf, text=txt, command=cmd, bg=bg, fg=fg,
                          font=(fam, 11, "bold"), width=3, height=1,
                          cursor="hand2", relief="flat", bd=0,
                          activebackground="#7f3b36",
                          activeforeground="#ffffff")
            # NOTE: no pack() here. The three buttons are packed below in the
            # correct order (side="right" puts the first packed one farthest
            # to the right, so we pack close -> max -> min for a left-to-right
            # order of min, max, close).
            b.bind("<Enter>", lambda e: b.configure(bg="#444444"))
            b.bind("<Leave>", lambda e: b.configure(bg=bg))
            return b

        win_min = _make_win_btn("─", lambda: win.iconify())
        win_close = _make_win_btn("✕", lambda: win.destroy())
        # Pack order: side="right" puts first packed farthest right.
        # Pack close first (far right), then min (far left) -> [min] [close]
        win_close.pack(side="right", padx=1, pady=0)
        win_close.bind("<Enter>", lambda e: win_close.configure(bg="#7f3b36"))
        win_close.bind("<Leave>", lambda e: win_close.configure(bg=bg))
        win_min.pack(side="right", padx=1, pady=0)
        win_min.bind("<Enter>", lambda e: win_min.configure(bg="#444444"))
        win_min.bind("<Leave>", lambda e: win_min.configure(bg=bg))

        win.bind("<Configure>", lambda e: None)

        body = tk.Frame(win, bg=bg)
        body.pack(side="top", fill="both", expand=True)
        try:
            av.bind("<Button-1>", lambda e: play_track_av())
        except Exception:
            pass

        def play_track_av():
            """Click the avatar / title = play the channel's first video."""
            try:
                first = (state.get("page") or {}).get("_first_video_id") or ""
            except Exception:
                first = ""
            if not first:
                # No playable video found on this channel yet.
                try:
                    status_lbl.configure(
                        text="No playable videos found on this channel.")
                except Exception:
                    pass
                return
            self._channel_windows[cid] = win
            self.play_track({"videoId": first, "title": channel_name or "Channel",
                             "artist": ""})

        # Content below the title bar: status + tabs.
        status_lbl = tk.Label(body, text="Loading channel...", bg=bg,
                              fg=fg, anchor="w")
        status_lbl.pack(fill="x", padx=12, pady=(4, 0))

        # Themed tab strip built with plain tk widgets. ttk.Notebook paints
        # its own (light grey, OS) chrome, which ignored the theme.
        tabbar = tk.Frame(body, bg=bg)
        tabbar.pack(fill="x", padx=8, pady=(4, 0))
        pages = tk.Frame(body, bg=bg)
        pages.pack(fill="both", expand=True, padx=8, pady=6)

        state: dict = {"page": None, "tab": "Videos", "loaded": set(),
                    "empty": set()}

        def _load_page():
            try:
                page = self.client.get_channel_page(cid)
            except Exception:
                page = {}
            self._call_ui(_page_ready, page)

        def _page_ready(page: dict):
            p = page or {}
            state["page"] = p
            try:
                nm = p.get("name") or channel_name
                title_lbl.configure(text=nm or "Channel")
                win.title(nm or "Channel")
            except Exception:
                pass
            try:
                if p.get("avatar"):
                    self._load_thumb_async(p["avatar"], av, 56)
                else:
                    av.configure(text="\u25b6")
            except Exception:
                pass
            subs = []
            try:
                if p.get("description"):
                    subs.append(str(p["description"]).strip().replace("\n", " ")[:180])
                if p.get("url"):
                    subs.append(str(p["url"]))
            except Exception:
                pass
            try:
                status_lbl.configure(text="  \u2022  ".join(subs) or " ")
            except Exception:
                pass

            # Remember the first playable video on this channel so clicking
            # the avatar/title plays a real song instead of the channel ID.
            try:
                _fvid = self._first_video_from_page(p)
                if _fvid:
                    p["_first_video_id"] = _fvid
            except Exception:
                pass

            have = {str(t_.get("title", "")).lower() for t_ in
                    (p.get("tabs", []) or [])}
            # Tabs are declared by where the data really comes from:
            # plain channel tabs come from the normal browse, songs/albums
            # from YouTube Music (the only place releases exist).
            plan: list = []
            if "home" in have:
                plan.append(("Home", "tab", "Home"))
            if "videos" in have:
                plan.append(("Videos", "tab", "Videos"))
            plan.append(("Songs", "music_songs", ""))
            plan.append(("Albums", "music_albums", ""))
            for key in ("playlists", "releases"):
                if key in have:
                    lbl = "Playlists" if key == "playlists" else "Releases"
                    plan.append((lbl, "tab", "Playlists" if key == "playlists"
                                 else "Albums"))
            if "shorts" in have:
                plan.append(("Shorts", "tab", "Shorts"))
            seen: set = set()
            plan = [t for t in plan if not (t[0] in seen or seen.add(t[0]))]

            buttons: list = []
            bodies: dict = {}
            first_label = plan[0][0] if plan else ""

            def _select(label: str) -> None:
                state["tab"] = label
                for b in buttons:
                    on = (str(b.cget("text")) == label)
                    b.configure(bg=accent if on else self._tint_mid,
                                fg="#ffffff" if on else fg,
                                font=(fam, 10, "bold") if on else (fam, 10),
                                relief="sunken" if on else "flat")
                for lbl, fr in bodies.items():
                    if lbl == label:
                        fr.pack(fill="both", expand=True)
                    else:
                        fr.pack_forget()
                loader = loaders.get(label)
                if not loader:
                    return
                # Always (re)load when the user clicks a tab, unless it is
                # already loading. YouTube sometimes answers empty under load,
                # so a second click is the natural way to ask again.
                loader()

            loaders: dict = {}
            for label, source, tab_title in plan:
                try:
                    b = tk.Button(tabbar, text=label, bg=self._tint_mid, fg=fg,
                                  font=(fam, 10, "bold"), padx=12, pady=5,
                                  relief="flat", bd=0, cursor="hand2",
                                  activebackground=self._tint_mid,
                                  activeforeground=fg)
                    b.pack(side="left", padx=(0, 4))
                    b.bind("<Button-1>", lambda e, l=label: _select(l))
                    buttons.append(b)
                    fr = tk.Frame(pages, bg=bg)
                    bodies[label] = fr
                    loaders[label] = self._make_channel_tab_loader(
                        fr, p, label, source=source, tab_title=tab_title,
                        on_empty=(lambda l=label: state["empty"].add(l)),
                        on_status=(lambda m, l=label: status_lbl.configure(
                            text=f"{l}: {m}"[:140])))
                except Exception as e:
                    # One broken tab must not take the whole window down.
                    try:
                        self.status.configure(
                            text=f"Tab '{label}' unavailable: {e}"[:140])
                    except Exception:
                        pass

            if not plan:
                tk.Label(pages, text="This channel has no public tabs.",
                         bg=bg, fg="gray").pack(pady=20)
                return
            _select(first_label)

        threading.Thread(target=_load_page, daemon=True).start()

    def _make_channel_tab_loader(self, frame, page: dict, label: str,
                                 source: str = "tab", tab_title: str = "",
                                 on_empty=None, on_status=None):
        """One channel tab: a scrollable list plus 'Load more'.

        source:
          "tab"         -> the channel's own browse tab (Videos, Playlists...)
          "music_songs" -> YT Music "Top songs" shelf (real catalogue)
          "music_albums"-> YT Music release shelves (real albums/EPs)

        on_status(msg) -> called with status messages to show in the
        channel window (instead of the main window's status bar).
        Returns a zero-arg loader; each tab keeps its own state, so switching
        tabs never mixes or re-fetches rows.
        """
        fam = self._font_family()
        bg = self._ch_bg()
        fg = self._ch_fg()
        canvas = tk.Canvas(frame, bg=bg, highlightthickness=0)
        sb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview,
                          troughcolor=bg, bg=self._tint_mid,
                          activebackground=self._tint_mid,
                          highlightbackground=self._tint_mid,
                          relief="flat", bd=0, highlightthickness=0)
        inner = tk.Frame(canvas, bg=bg)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        # Wheel scroll for THIS tab's canvas (not the main list canvas).
        canvas.bind("<MouseWheel>",
                    lambda e, c=canvas: self._wheel_scroll_canvas(c, e))
        canvas.bind("<Button-4>",
                    lambda e, c=canvas: self._wheel_scroll_canvas(c, -1))
        canvas.bind("<Button-5>",
                    lambda e, c=canvas: self._wheel_scroll_canvas(c, 1))
        more_btn = tk.Button(frame, text="Load more...", state="disabled",
                             bg=self._tint_mid, fg=fg, activebackground=self._tint_mid,
                             activeforeground=fg, relief="flat", bd=0,
                             highlightthickness=0, cursor="hand2")
        more_btn.pack(fill="x", padx=6, pady=4)
        st: dict = {"token": "", "loading": False, "started": False}
        empty_shown = [False]

        def _say(msg: str) -> None:
            if empty_shown[0]:
                return
            empty_shown[0] = True
            tk.Label(inner, text=msg, bg=bg, fg="gray",
                     font=(fam, 10), justify="center", wraplength=460
                     ).pack(pady=16)

        def _status(msg: str) -> None:
            if on_status:
                try:
                    on_status(msg)
                except Exception:
                    pass

        def _fill(items):
            # Only add rows that aren't already rendered (by id).
            existing_ids = set()
            for w in inner.winfo_children():
                for attr in ("_video_id", "_playlist_id", "_album_id"):
                    v = getattr(w, attr, "")
                    if v:
                        existing_ids.add(v)
            for it in items:
                key = (str(it.get("videoId", "") or "")
                       or str(it.get("_album_id", "") or "")
                       or str(it.get("_playlist_id", "")))
                if not key or key in existing_ids:
                    continue
                existing_ids.add(key)
                try:
                    self._build_channel_row(inner, it, label)
                except Exception:
                    pass

        def _done(rows, tok, first):
            st["token"] = tok or ""
            st["loading"] = False
            if first:
                st["started"] = True
            if not rows and first:
                try:
                    if on_empty is not None:
                        on_empty()
                except Exception:
                    pass
                if source == "music_albums":
                    _say("This channel has no albums on YouTube Music.\n"
                         "(Only artists registered in YouTube Music publish "
                         "releases here.)")
                    _status(f"{label}: no albums on YouTube Music.")
                elif source == "music_songs":
                    _say("No songs in the YouTube Music catalogue for this "
                         "channel.")
                    _status(f"{label}: no songs on YouTube Music.")
                else:
                    _say("Nothing here (or it is private).")
                    _status(f"{label}: nothing here.")
                more_btn.configure(state="disabled", text="")
                return
            _fill(rows)
            more_btn.configure(text="Load more..." if tok else "No more",
                               state="normal" if tok else "disabled")
            _status(f"{label}: {len(rows)} item{'s' if len(rows) != 1 else ''} loaded.")

        def _fetch(continuation: str, first: bool):
            if st["loading"]:
                return
            st["loading"] = True
            more_btn.configure(state="disabled",
                               text="Loading..." if not first else "Load more...")
            _status(f"{label}: loading…")

            def _bg():
                try:
                    if source == "music_albums":
                        rows = self.client.get_channel_albums(
                            page.get("channelId", "")) if first else []
                        tok = ""
                    elif source == "music_songs":
                        rows = self.client.get_channel_top_songs(
                            page.get("channelId", "")) if first else []
                        tok = ""
                    else:
                        rows, tok = self.client.get_channel_tab(
                            page.get("channelId", ""),
                            tab_title or label,
                            continuation=continuation, page=page)
                except Exception:
                    rows, tok = [], ""
                self._call_ui(_done, rows, tok, first)

            threading.Thread(target=_bg, daemon=True).start()

        def _load():
            if st["started"] or st["loading"]:
                return
            _fetch("", True)

        more_btn.configure(command=lambda: _fetch(st.get("token", ""), False))
        return _load

    def _build_channel_row(self, parent, it: dict, tab_label: str) -> None:
        fam = self._font_family()
        bg = self._ch_bg()
        fg = self._ch_fg()
        # --- real album/EP from YouTube Music ---
        aid = str(it.get("_album_id") or it.get("albumId") or "")
        if aid and not it.get("videoId"):
            row = tk.Frame(parent, bg=bg)
            row.pack(fill="x", padx=4, pady=2)
            row._album_id = aid
            cover = tk.Label(row, text="\U0001f4be", bg=bg, fg=fg, font=(fam, 12))
            cover.pack(side="left", padx=4)
            try:
                if it.get("thumbnail"):
                    self._load_thumb_async(it["thumbnail"], cover, 48)
            except Exception:
                pass
            mid = tk.Frame(row, bg=bg)
            mid.pack(side="left", fill="x", expand=True)
            t = tk.Label(mid, text=it.get("title") or "Album", bg=bg, fg=fg,
                         font=(fam, 10, "bold"), anchor="w", cursor="hand2")
            t.pack(fill="x")
            bits = [x for x in (str(it.get("release_type") or ""),
                               str(it.get("year") or ""),
                               str(it.get("artist") or "")) if x]
            if bits:
                tk.Label(mid, text=" • ".join(bits), bg=bg, fg="#909090",
                         font=(fam, 9), anchor="w").pack(fill="x")

            def _open(e=None, a=aid, ti=it.get("title", "")):
                self._open_album_by_id(a, ti)

            for w in (row, cover, t):
                w.bind("<Button-1>", _open)
                w.bind("<Double-Button-1>", _open)
            return
        if it.get("_playlist_id"):
            row = tk.Frame(parent, bg=bg)
            row.pack(fill="x", padx=4, pady=1)
            lab = tk.Label(row, text="☰", bg=bg, fg=fg, font=(fam, 12))
            lab.pack(side="left", padx=4)
            try:
                # Playlist/album cover, not a bare glyph.
                if it.get("thumbnail"):
                    self._load_thumb_async(it["thumbnail"], lab, 44)
            except Exception:
                pass
            t = tk.Label(row, text=it.get("title") or "Playlist", bg=bg, fg=fg,
                         font=(fam, 10), anchor="w", cursor="hand2")
            t.pack(side="left", fill="x", expand=True)
            sub = str(it.get("artist") or "")
            if sub:
                tk.Label(row, text=sub, bg=bg, fg="#999", font=(fam, 9)).pack(side="left")
            for w in (row, lab, t):
                w.bind("<Double-Button-1>",
                       lambda e, p=it.get("_playlist_id"), ti=it.get("title", ""):
                       self.open_playlist(p, ti))
            try:
                t.bind("<Button-1>",
                       lambda e, p=it.get("_playlist_id"), ti=it.get("title", ""):
                       self.open_playlist(p, ti))
            except Exception:
                pass
            return
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=4, pady=1)
        th = tk.Label(row, text="▶", bg=bg, fg=fg, font=(fam, 11), width=4, cursor="hand2")
        th.pack(side="left", padx=2)
        mid = tk.Frame(row, bg=bg)
        mid.pack(side="left", fill="x", expand=True)
        t = tk.Label(mid, text=it.get("title") or "?", bg=bg, fg=fg,
                     font=(fam, 10), anchor="w", cursor="hand2")
        t.pack(fill="x")
        sub_bits = [x for x in (str(it.get("views_text") or ""),
                                str(it.get("duration") or "")) if x]
        if sub_bits:
            tk.Label(mid, text=" • ".join(sub_bits), bg=bg, fg="#999",
                     font=(fam, 9), anchor="w").pack(fill="x")
        row._video_id = str(it.get("videoId", "") or "")
        row._playlist_id = str(it.get("_playlist_id", "") or "")
        for w in (row, th, t):
            w.bind("<Double-Button-1>", lambda e, tr=it: self.play_track(tr))
            w.bind("<Button-3>", lambda e, tr=it: self._show_track_menu(e, tr))
        th.bind("<Button-1>", lambda e, tr=it: self.play_track(tr))
        try:
            if it.get("thumbnail"):
                self._load_thumb_async(it["thumbnail"], th, 44)
        except Exception:
            pass

    # ---------- mainloop ----------
    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self.bg_video_running = False

    def on_close(self) -> None:
        self._closed = True
        self.bg_video_running = False
        # NOTE: the size is read straight from the live window. The startup
        # correction (_restore_size_after_map) must NOT run here: at this
        # point _want_size is still the size from boot, and forcing it back
        # would silently discard the size the user just chose.
        try:
            self._video_running = False
        except Exception:
            pass
        try:
            self._kill_video_procs(except_gen=None)
        except Exception:
            pass
        self._save_geometry()
        # Save current volume for next time
        try:
            if bool(self.theme.get("reproductor", "guardar_volumen", default=True)):
                self.theme.set(round(float(self.vol_var.get()), 1), "reproductor", "volumen_defecto")
        except Exception:
            pass
        # Save video panel geometry (relative dx/dy, may be outside)
        # + stickers
        try:
            if getattr(self, "_video_panel", None) is not None:
                try:
                    rx, ry = self.root.winfo_x(), self.root.winfo_y()
                    self.theme.set(int(self._video_panel.winfo_x() - rx), "video_panel", "dx")
                    self.theme.set(int(self._video_panel.winfo_y() - ry), "video_panel", "dy")
                except Exception:
                    pass
                self.theme.set(int(self._video_panel.winfo_width()), "video_panel", "w")
                self.theme.set(int(self._video_panel.winfo_height()), "video_panel", "h")
                try:
                    self._video_panel.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._save_stickers()
        except Exception:
            pass
        try:
            for st in list(getattr(self, "_stickers", []) or []):
                try:
                    st.get("win").destroy()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
