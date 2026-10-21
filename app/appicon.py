"""Application icon.

`assets/icons/app.ico` and `assets/icons/app.png` are the SHIPPED icon and
are committed to the repo, so a fresh clone always has one. They are drawn in
the app's own brand colours (not your theme's), which keeps the icon stable
for everyone.

Run this module to regenerate them after changing the branding:

    py -m app.appicon

It can also follow a theme: pass a theme.json and the plate/accents are taken
from it (`py -m app.appicon --theme themes/DefaultTheme/theme.json`).
"""
from __future__ import annotations
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- brand identity (theme-independent on purpose) -----------------------
BRAND_BASE = (36, 26, 63)      # deep violet plate
BRAND_TOP = (74, 53, 128)      # gradient top
BRAND_ACCENT = (255, 17, 207)  # magenta play mark / rim

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _mix(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


def _hex_to_rgb(h):
    h = str(h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        return None


def _palette(theme_path: str | None = None):
    """Brand colours, optionally derived from a theme file."""
    if theme_path and os.path.exists(theme_path):
        try:
            from app.config import ThemeManager
            d = ThemeManager(theme_path).data
            base = _hex_to_rgb((d.get("lista") or {}).get("color_fondo"))
            top = _hex_to_rgb((d.get("fondo") or {}).get("color2"))
            acc = _hex_to_rgb((d.get("botones") or {}).get("color_fondo"))
            if base and acc and sum(acc) >= 40:
                return base, (top or base), acc
        except Exception:
            pass
    return BRAND_BASE, BRAND_TOP, BRAND_ACCENT


def draw(size: int = 256, theme_path: str | None = None):
    """The icon at `size`x`size` (supersampled 4x, then downsampled)."""
    from PIL import Image, ImageDraw
    base, top, accent = _palette(theme_path)
    S, SS = 256, 1024
    k = SS / S

    img = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    box = [6 * k, 6 * k, (S - 6) * k, (S - 6) * k]
    radius = 54 * k

    mask = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)

    plate = Image.new("RGBA", (SS, SS), base + (255,))
    grad = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(SS):
        t = y / max(1, SS - 1)
        gd.line([(0, y), (SS, y)], fill=_mix(top, base, t) + (255,))
    plate.paste(grad, (0, 0), mask)
    img.alpha_composite(plate)

    dr = ImageDraw.Draw(img)
    # thin accent rim so the icon reads on light AND dark backgrounds
    dr.rounded_rectangle(box, radius=radius, outline=accent + (215,),
                         width=int(5 * k))

    # play triangle, optically centred (a geometric centre looks off-centre)
    cx, cy = S * 0.53, S * 0.52
    w, h = S * 0.30, S * 0.36
    dr.polygon([(cx - w * 0.52) * k, (cy - h * 0.5) * k,
                (cx - w * 0.52) * k, (cy + h * 0.5) * k,
                (cx + w * 0.60) * k, cy * k],
               fill=(255, 255, 255, 242))

    out = img.resize((size, size), Image.LANCZOS)
    return out


def build(out_dir: str | None = None, theme_path: str | None = None) -> dict:
    """Write app.png (+ _64.png) and the multi-size app.ico."""
    from PIL import Image
    out_dir = out_dir or os.path.join(_ROOT, "assets", "icons")
    os.makedirs(out_dir, exist_ok=True)
    big = draw(256, theme_path)
    png = os.path.join(out_dir, "app.png")
    big.save(png)
    big.resize((64, 64), Image.LANCZOS).save(
        os.path.join(out_dir, "app_64.png"))
    ico = os.path.join(out_dir, "app.ico")
    big.save(ico, format="ICO",
             sizes=[(s, s) for s in ICO_SIZES if s <= 256])
    return {"png": png, "ico": ico}


if __name__ == "__main__":
    theme = None
    if "--theme" in sys.argv:
        i = sys.argv.index("--theme")
        theme = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    paths = build(theme_path=theme)
    for k, v in paths.items():
        print(f"{k}: {v} ({os.path.getsize(v)} bytes)")