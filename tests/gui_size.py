# -*- coding: utf-8 -*-
"""Window-size persistence checks (run against a live MainWindow)."""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = '''import os, sys, time
sys.path.insert(0, r"{root}"); os.chdir(r"{root}")
from app.ui_main import MainWindow
from app.config import ThemeManager
from app.youtube_client import YouTubeClient
try:
    from app.player_engine import PlayerEngine
    p = PlayerEngine()
except Exception:
    p = None
t = ThemeManager(); c = YouTubeClient(use_account=False)
a = MainWindow(t, c, p)
for _ in range(160):
    try:
        a.root.update()
    except Exception:
        break
    time.sleep(0.05)
print("SIZE", a.root.winfo_width(), a.root.winfo_height())
os._exit(0)
'''


def run(root, check, pump):
    print("\nD) window size survives close + restart")
    theme_file = os.path.join(root, "config", "theme.json")

    def stored():
        with open(theme_file, encoding="utf-8") as f:
            d = json.load(f)
        return (int(d["ventana"]["ancho"]), int(d["ventana"]["alto"]))

    from app.ui_main import MainWindow
    from app.config import ThemeManager
    from app.youtube_client import YouTubeClient
    try:
        from app.player_engine import PlayerEngine
        pl = PlayerEngine()
    except Exception:
        pl = None

    # 1) the user drags the window to a new size, then closes the app
    app = MainWindow(ThemeManager(), YouTubeClient(use_account=False), pl)
    pump(app.root, 3.0)
    app.root.geometry("1280x800+40+30")
    pump(app.root, 2.0)
    live = (app.root.winfo_width(), app.root.winfo_height())
    app.on_close()
    on_disk = stored()
    check("D1 the size you close with is written to config/theme.json",
          on_disk == live, f"on_screen={live} stored={on_disk}")

    # 2) restart in the same process: same size, and saving again must not
    #    move it (that is the 'it never sticks' bug)
    app2 = MainWindow(ThemeManager(), YouTubeClient(use_account=False), pl)
    pump(app2.root, 7.0)
    live2 = (app2.root.winfo_width(), app2.root.winfo_height())
    check("D2 after restart the window is the saved size", live2 == on_disk,
          f"restarted at {live2}, stored {on_disk}")
    app2._save_geometry()
    check("D3 no drift: saving again keeps the same size", stored() == on_disk,
          f"{stored()} vs {on_disk}")
    app2.root.destroy()

    # 3) and once more in a genuinely separate process
    helper = os.path.join(root, "_t_size_probe.py")
    with open(helper, "w", encoding="utf-8") as f:
        f.write(PROBE.replace("{root}", root))
    out = subprocess.run([sys.executable, "-u", helper], cwd=root,
                         capture_output=True, text=True, timeout=400).stdout
    m = [x for x in out.splitlines() if x.startswith("SIZE")]
    got = tuple(int(x) for x in m[0].split()[1:3]) if m else None
    check("D4 a separate process opens at the stored size", got == on_disk,
          f"restarted at {got}, stored {on_disk}")