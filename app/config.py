"""Customization (theme) manager for OpenYTPlayer.

Two levels:
- Working copy: ``config/theme.json`` (autosaved on every change, survives
  restarts). This is what the app renders.
- Theme packages: ``themes/<name>/theme.json`` (+ ``assets/``). Named,
  portable snapshots holding ABSOLUTELY ALL graphical settings: colors,
  background image/video, button shapes, icons, fonts, panel/section/menu
  backgrounds, list options, window geometry, volume defaults, video panel
  geometry/position, sticker files + positions + sizes, sidebar order.
  Asset paths inside a package are stored RELATIVE (``assets/xxx.png``) and
  resolved to absolute paths at load time.
"""
from __future__ import annotations
import json
import os
import copy
import shutil

DEFAULT_THEME: dict = {
    "widgets": {
        # Search bar (the plain Windows entry used to stay white/grey).
        "buscador": {
            "fondo": "#1e1e1e",
            "texto": "#e8e8e8",
            "borde": "#3d3d3d",
            "cursor": "#e8e8e8",
            "seleccion": "#4a4a4a",
        },
        # Progress bar, volume and every Settings slider.
        "slider": {
            "fondo": "#1e1e1e",
            "pista": "#2b2b2b",
            "pulgar": "#8c8c8c",
            "borde": "#3d3d3d",
            "texto": "#b4b4b4",
        },
        # Text panels and scrollbars.
        "panel": {
            "fondo": "#1e1e1e",
            "borde": "#383838",
            "texto": "#e8e8e8",
        },
        # Right-click (context) menus.
        "menu": {
            "fondo": "#242424",
            "texto": "#e8e8e8",
            "activo_fondo": "#3d3d3d",
            "activo_texto": "#f2f2f2",
            "borde": "#383838",
        },
    },
    "ventana": {
        "titulo": "OpenYTPlayer",
        "ancho": 1100,
        "alto": 700,
        "transparencia": 1.0,
        "siempre_encima": False,
        "tema_base": "oscuro",
        "barra_personalizada": True,
        "ocultar_consola": True,
    },
    "fondo": {
        "modo": "degradado",  # color | degradado | imagen | video
        "color": "#191919",
        "color2": "#232323",
        "degradado_direccion": "vertical",  # vertical | horizontal
        "imagen_path": "",
        "video_path": "",
        "overlay_opacidad": 0.25,
    },
    "botones": {
        "tamano": 44,
        "forma": "redondo",  # redondo | cuadrado | custom
        "forma_custom_path": "",  # PNG used as button face
        "usar_formas": True,  # False = classic rectangular buttons
        "color_fondo": "#2b2b2b",
        "color_hover": "#3a3a3a",
        "color_texto": "#e0e0e0",
        "borde_ancho": 0,
        "borde_color": "#4a4a4a",
        "esquina_radio": 22,
        "espaciado": 6,
    },
    "iconos": {
        # Each button may be a text glyph or a path to an image. "" = default.
        # The default set is deliberately MONOCHROME (no colour emoji), so the
        # whole interface stays in the same neutral grey.
        # Keys: play, pause, prev, next, shuffle, loop_off, loop_all, loop_one,
        #         fav, fav_on, volume, search, settings, customize, playlist, close
        "play": "▶",
        "pause": "▌▌",
        "prev": "◀◀",
        "next": "▶▶",
        "shuffle": "⇄",
        "shuffle_on": "⇄●",
        "loop_off": "↻○",
        "loop_all": "↻",
        "loop_one": "↻1",
        "fav": "♡",
        "fav_on": "♥",
        "volume": "♪",
        "search": "⌕",
        "settings": "⚙\ufe0e",
        "customize": "◐",
        "playlist": "☰",
        "close": "✕",
        "tamano_fuente_icono": 18,
    },
    "texto": {
        "fuente_familia": "Segoe UI",
        "fuente_custom_path": "",
        "fuente_tam_titulo": 13,
        "fuente_tam_lista": 11,
        "fuente_tam_pequena": 9,
        "color_titulo": "#f0f0f0",
        "color_subtitulo": "#9d9d9d",
        "color_lista": "#cccccc",
        "color_acento": "#b0b0b0",
    },
    "lista": {
        "color_fondo": "#1a1a1a",
        "color_item_hover": "#262626",
        "color_item_activo": "#333333",
        "altura_fila": 56,
        "mostrar_thumbnails": True,
        "tamano_thumbnail": 44,
        "transparencia": 0.0,
        "lote_progresivo": 80,
        "recomendaciones_continuacion": True,   # barra separadora + recomendaciones sin bucle
        "recomendaciones_cantidad": 10,         # cuántas canciones recomendadas mostrar
    },
    "fondos_secciones": {
        "inicio": {"modo": "heredar", "color": "", "color2": "", "imagen_path": "", "video_path": ""},
        "explorar": {"modo": "heredar", "color": "", "color2": "", "imagen_path": "", "video_path": ""},
        "buscar": {"modo": "heredar", "color": "", "color2": "", "imagen_path": "", "video_path": ""},
        "playlists": {"modo": "heredar", "color": "", "color2": "", "imagen_path": "", "video_path": ""},
        "favoritas": {"modo": "heredar", "color": "", "color2": "", "imagen_path": "", "video_path": ""},
        "cola": {"modo": "heredar", "color": "", "color2": "", "imagen_path": "", "video_path": ""},
    },
    "fondos_botones": {
        "buscar": {"modo": "heredar", "color": "", "imagen_path": ""},
        "playlists": {"modo": "heredar", "color": "", "imagen_path": ""},
        "favoritas": {"modo": "heredar", "color": "", "imagen_path": ""},
        "cola": {"modo": "heredar", "color": "", "imagen_path": ""},
    },
    "fondos_paneles": {
        "barra_superior": {"modo": "heredar", "color": "", "imagen_path": ""},
        "lateral": {"modo": "heredar", "color": "", "imagen_path": ""},
        "lateral_playlists": {"modo": "heredar", "color": "", "imagen_path": ""},
        "reproductor": {"modo": "heredar", "color": "", "imagen_path": ""},
        "progreso": {"modo": "heredar", "color": "", "imagen_path": ""},
        "volumen": {"modo": "heredar", "color": "", "imagen_path": ""},
    },
    "video_panel": {
        "visible": True,
        "x": 620,
        "y": 120,
        "dx": 620,
        "dy": 120,
        "w": 320,
        "h": 240,
        "fps": 15,
        "res_w": 640,  # internal video resolution (window size is separate)
        "res_h": 360,
    },
    "sidebar_orden": ["buscar", "playlists", "favoritas", "cola"],
    "stickers": [],
    "reproductor": {
        "volumen_defecto": 70,
        "loop_defecto": "off",
        "shuffle_defecto": False,
        "autoplay": True,
        "calidad_audio": "bestaudio",
        "cache_max_mb": 500,
        "notificaciones": True,
        "guardar_volumen": True,
        "barra_responsive": True,      # si no caben los botones, se acorta la barra de progreso
        "barra_altura_minima": 60,     # altura mínima del reproductor en px
        "botones_primero": True,       # los controles siempre tienen prioridad sobre la barra
    },
    "cuenta": {
        "cookies_json_path": "cookiesYT.json",
        "usar_cookies": True,
        "fuente_sesion": "archivo",  # archivo | navegador
        "navegador": "chrome",
    },
}

THEMES_DIR = "themes"
THEME_FILE = "theme.json"
ASSETS_DIR = "assets"
ACTIVE_THEME_FILE = os.path.join("config", "active_theme.txt")

# NOTE: internal schema keys stay in Spanish on purpose: renaming them would
# silently drop existing users' customization on load. Only user-facing text
# is English. New code must use .get() with defaults (never hard-require keys).


def _default_theme_minimal() -> dict:
    """Minimalist dark theme (DefaultTheme): flat dark colors, light text."""
    d = copy.deepcopy(DEFAULT_THEME)
    try:
        d["ventana"]["titulo"] = "OpenYTPlayer"
        d["ventana"]["ancho"], d["ventana"]["alto"] = 1100, 700
        d["ventana"]["transparencia"] = 1.0
        d["fondo"] = {
            "modo": "color",
            "color": "#1a1a1a",
            "color2": "#232323",
            "degradado_direccion": "vertical",
            "imagen_path": "",
            "video_path": "",
            "overlay_opacidad": 0.25,
        }
        d["botones"].update({
            "tamano": 44, "forma": "redondo", "forma_custom_path": "",
            "usar_formas": True, "color_fondo": "#2b2b2b",
            "color_hover": "#3a3a3a", "color_texto": "#e0e0e0",
            "borde_ancho": 0, "borde_color": "#4a4a4a",
        })
        d["texto"].update({
            "fuente_familia": "Segoe UI", "fuente_custom_path": "",
            "color_titulo": "#f0f0f0", "color_subtitulo": "#9d9d9d",
            "color_lista": "#cccccc", "color_acento": "#b0b0b0",
        })
        d["lista"].update({
            "color_fondo": "#1a1a1a", "color_item_hover": "#262626",
            "color_item_activo": "#333333", "mostrar_thumbnails": True,
            "tamano_thumbnail": 48, "transparencia": 0.0,
            "recomendaciones_continuacion": True,
            "recomendaciones_cantidad": 10,
        })
        d["widgets"].update({
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
        })
        d["video_panel"].update({
            "visible": True, "dx": 620, "dy": 120, "w": 320, "h": 180,
            "fps": 15,
        })
        d["stickers"] = []
        d["reproductor"]["volumen_defecto"] = 70
        d["reproductor"]["barra_responsive"] = True
        d["reproductor"]["barra_altura_minima"] = 60
        d["reproductor"]["botones_primero"] = True
    except Exception:
        pass
    return d


class ThemeManager:
    def __init__(self, path: str = "config/theme.json"):
        self.path = path
        self.data: dict = copy.deepcopy(DEFAULT_THEME)
        self.load()

    def load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.data = self._merge(copy.deepcopy(DEFAULT_THEME), loaded)
            except Exception:
                self.data = copy.deepcopy(DEFAULT_THEME)
        else:
            self.save()
        return self.data

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _merge(base: dict, override: dict) -> dict:
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k] = ThemeManager._merge(base[k], v)
            else:
                base[k] = v
        return base

    def get(self, *keys, default=None):
        cur = self.data
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def set(self, value, *keys) -> None:
        cur = self.data
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = value
        self.save()

    def reset(self) -> None:
        self.data = copy.deepcopy(DEFAULT_THEME)
        self.save()

    # ---------- theme packages (themes/<name>/) ----------
    @staticmethod
    def _theme_dir(name: str) -> str:
        return os.path.join(THEMES_DIR, name)

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Safe folder name (letters, digits, dash, underscore, max 40)."""
        import re
        clean = (name or "").strip().replace(" ", "_")
        clean = re.sub(r"[^A-Za-z0-9_-]", "", clean)[:40]
        return clean

    @classmethod
    def list_themes(cls) -> list[str]:
        """Names having themes/<name>/theme.json (sorted)."""
        try:
            os.makedirs(THEMES_DIR, exist_ok=True)
            out = []
            for entry in os.listdir(THEMES_DIR):
                full = os.path.join(THEMES_DIR, entry)
                if (os.path.isdir(full)
                        and os.path.isfile(os.path.join(full, THEME_FILE))):
                    out.append(entry)
            return sorted(out)
        except Exception:
            return []

    @classmethod
    def theme_exists(cls, name: str) -> bool:
        return bool(name) and os.path.isfile(
            os.path.join(cls._theme_dir(name), THEME_FILE))

    @staticmethod
    def get_active_theme() -> str | None:
        try:
            if os.path.exists(ACTIVE_THEME_FILE):
                with open(ACTIVE_THEME_FILE, "r", encoding="utf-8") as f:
                    name = (f.read() or "").strip()
                return name or None
        except Exception:
            pass
        return None

    @staticmethod
    def set_active_theme(name: str | None) -> None:
        try:
            os.makedirs(os.path.dirname(ACTIVE_THEME_FILE) or ".", exist_ok=True)
            with open(ACTIVE_THEME_FILE, "w", encoding="utf-8") as f:
                f.write((name or "").strip())
        except Exception:
            pass

    @staticmethod
    def _iter_asset_slots(data: dict):
        """Yield (holder_dict, key) for every file-path slot in the schema."""
        try:
            fondo = (data or {}).get("fondo")
            if isinstance(fondo, dict):
                for k in ("imagen_path", "video_path"):
                    if k in fondo:
                        yield fondo, k
            botones = (data or {}).get("botones")
            if isinstance(botones, dict) and "forma_custom_path" in botones:
                yield botones, "forma_custom_path"
            iconos = (data or {}).get("iconos")
            if isinstance(iconos, dict):
                for k in list(iconos.keys()):
                    if k != "tamano_fuente_icono":
                        yield iconos, k
            texto = (data or {}).get("texto")
            if isinstance(texto, dict) and "fuente_custom_path" in texto:
                yield texto, "fuente_custom_path"
            for group, keys in (("fondos_secciones", ("imagen_path", "video_path")),
                                ("fondos_botones", ("imagen_path",)),
                                ("fondos_paneles", ("imagen_path",))):
                grp = (data or {}).get(group)
                if isinstance(grp, dict):
                    for _sec, cfg in grp.items():
                        if isinstance(cfg, dict):
                            for k in keys:
                                if k in cfg:
                                    yield cfg, k
            for st in ((data or {}).get("stickers") or []):
                if isinstance(st, dict) and "path" in st:
                    yield st, "path"
        except Exception:
            return

    _ASSET_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
                   ".mp4", ".avi", ".mov", ".mkv", ".webm", ".ttf", ".otf")

    @staticmethod
    def _is_file_value(value) -> bool:
        """Plausible file path? Excludes emoji/text icon values."""
        if not isinstance(value, str):
            return False
        v = value.strip()
        if not v or v.lower().startswith(("http://", "https://")):
            return False
        if os.path.isabs(v):
            return True
        if "/" in v or "\\" in v:
            return True
        return v.lower().endswith(ThemeManager._ASSET_EXTS)

    @classmethod
    def _resolve_assets(cls, data: dict, base_dir: str) -> dict:
        """Relative asset paths -> absolute (runtime). Absolute kept as-is."""
        for holder, key in cls._iter_asset_slots(data):
            try:
                v = holder.get(key, "")
                if cls._is_file_value(v) and not os.path.isabs(v):
                    holder[key] = os.path.normpath(os.path.join(base_dir, v))
            except Exception:
                pass
        return data

    @classmethod
    def _collect_assets(cls, data: dict, folder: str) -> dict:
        """Copy referenced files into folder/assets/, store relative paths."""
        assets = os.path.join(folder, ASSETS_DIR)
        try:
            os.makedirs(assets, exist_ok=True)
        except Exception:
            pass
        used: set[str] = set()
        for holder, key in cls._iter_asset_slots(data):
            try:
                v = holder.get(key, "")
                if not cls._is_file_value(v):
                    continue
                src = v if os.path.isabs(v) else os.path.normpath(
                    os.path.join(folder, v))
                if not os.path.isfile(src):
                    continue  # missing file: keep reference so it can be fixed
                try:
                    if os.path.commonpath(
                            [os.path.abspath(src),
                             os.path.abspath(folder)]) == os.path.abspath(folder):
                        holder[key] = os.path.relpath(
                            os.path.abspath(src),
                            os.path.abspath(folder)).replace(os.sep, "/")
                        continue
                except Exception:
                    pass
                base = os.path.basename(src) or "asset"
                stem, ext = os.path.splitext(base)
                cand, i = base, 1
                while cand.lower() in used or os.path.exists(
                        os.path.join(assets, cand)):
                    cand = f"{stem}_{i}{ext}"
                    i += 1
                used.add(cand.lower())
                shutil.copy2(src, os.path.join(assets, cand))
                holder[key] = f"{ASSETS_DIR}/{cand}"
            except Exception:
                pass
        return data

    def load_theme(self, name: str) -> bool:
        """Apply themes/<name>/ to the working copy (resolves asset paths)."""
        try:
            folder = self._theme_dir(name)
            fp = os.path.join(folder, THEME_FILE)
            if not os.path.isfile(fp):
                return False
            with open(fp, "r", encoding="utf-8") as f:
                stored = json.load(f)
            data = self._merge(copy.deepcopy(DEFAULT_THEME), stored or {})
            self._resolve_assets(data, os.path.abspath(folder))
            self.data = data
            self.save()
            self.set_active_theme(name)
            return True
        except Exception:
            return False

    def save_theme(self, name: str) -> bool:
        """Snapshot working copy into themes/<name>/ (imports asset files)."""
        try:
            name = self.sanitize_name(name)
            if not name:
                return False
            folder = self._theme_dir(name)
            os.makedirs(os.path.join(folder, ASSETS_DIR), exist_ok=True)
            stored = self._collect_assets(copy.deepcopy(self.data),
                                          os.path.abspath(folder))
            with open(os.path.join(folder, THEME_FILE), "w",
                      encoding="utf-8") as f:
                json.dump(stored, f, ensure_ascii=False, indent=2)
            # Point the working copy at the theme-owned files so it matches
            # the package exactly (not "dirty" right after saving).
            try:
                self.data = self._merge(
                    copy.deepcopy(DEFAULT_THEME),
                    self._resolve_assets(copy.deepcopy(stored),
                                         os.path.abspath(folder)))
                self.save()
            except Exception:
                pass
            return True
        except Exception:
            return False

    @classmethod
    def delete_theme(cls, name: str) -> bool:
        try:
            if not name:
                return False
            shutil.rmtree(cls._theme_dir(name), ignore_errors=False)
            if cls.get_active_theme() == name:
                cls.set_active_theme(None)
            return True
        except Exception:
            return False

    def is_dirty_vs(self, name: str) -> bool:
        """Working copy differs from the stored theme package?"""
        try:
            folder = self._theme_dir(name)
            fp = os.path.join(folder, THEME_FILE)
            if not os.path.isfile(fp):
                return True
            with open(fp, "r", encoding="utf-8") as f:
                stored = json.load(f)
            data = self._merge(copy.deepcopy(DEFAULT_THEME), stored or {})
            self._resolve_assets(data, os.path.abspath(folder))
            return json.dumps(data, sort_keys=True, ensure_ascii=False) != \
                json.dumps(self.data, sort_keys=True, ensure_ascii=False)
        except Exception:
            return True

    @classmethod
    def ensure_builtin_themes(cls) -> str | None:
        """Create DefaultTheme if missing; snapshot working copy as theme1 on
        first run (preserves the user's current look). Returns active name."""
        try:
            os.makedirs(THEMES_DIR, exist_ok=True)
            if not cls.theme_exists("DefaultTheme"):
                folder = cls._theme_dir("DefaultTheme")
                os.makedirs(os.path.join(folder, ASSETS_DIR), exist_ok=True)
                with open(os.path.join(folder, THEME_FILE), "w",
                          encoding="utf-8") as f:
                    json.dump(_default_theme_minimal(), f,
                              ensure_ascii=False, indent=2)
            active = cls.get_active_theme()
            if active and cls.theme_exists(active):
                return active
            # First run: keep the user's current look as theme1.
            if not cls.theme_exists("theme1"):
                try:
                    tmp = cls()
                    if tmp.save_theme("theme1"):
                        return "theme1"
                except Exception:
                    pass
            if cls.theme_exists("theme1"):
                cls.set_active_theme("theme1")
                return "theme1"
            cls.set_active_theme("DefaultTheme")
            return "DefaultTheme"
        except Exception:
            return None
