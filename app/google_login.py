"""DIRECT Google login: opens your real Chrome/Edge at youtube.com,
you sign in YOURSELF on Google's real page (the app never touches
your password) and at the end we import just the cookies. No manual JSON."""
from __future__ import annotations
import os
import shutil
import time

LOGIN_URL = "https://www.youtube.com/"
FULL_BROWSER_LIST = ["chrome", "edge", "brave", "firefox", "vivaldi", "opera", "chromium"]
AUTOMATION_PROFILE_ROOT = os.path.join("config", "browser_login")


def log(msg: str) -> None:
    """Persistent diagnostics (cache/glogin.log) for direct login."""
    try:
        import datetime
        os.makedirs("cache", exist_ok=True)
        with open("cache/glogin.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%H:%M:%S} {msg}\n")
    except Exception:
        pass


def brave_binary() -> str | None:
    cands = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware",
                     "Brave-Browser", "Application", "brave.exe"),
        "/usr/bin/brave-browser", "/usr/bin/brave",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for p in cands:
        try:
            if p and os.path.isfile(p):
                return p
        except Exception:
            continue
    try:
        return shutil.which("brave") or shutil.which("brave-browser")
    except Exception:
        return None


def available_browsers() -> list[str]:
    """Chrome/Edge/Brave with a real binary (what selenium can drive)."""
    out = []
    for name, bins in (("chrome", ("chrome", "google-chrome")),
                       ("edge", ("msedge", "microsoft-edge"))):
        try:
            if any(shutil.which(b) for b in bins):
                out.append(name)
        except Exception:
            continue
    try:
        if brave_binary():
            out.append("brave")
    except Exception:
        pass
    return out


def automation_profile_dir(browser: str) -> str:
    """PERSISTENT automation profile (config/browser_login/<browser>).
    Lives apart from your real profile: no lock conflicts, and the session
    lasts months for silent re-reads."""
    p = os.path.abspath(os.path.join(AUTOMATION_PROFILE_ROOT, (browser or "chrome").lower()))
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass
    return p


def start_browser(browser: str = "chrome", visible: bool = True,
                  profile_dir: str | None = None):
    """Launches the real browser with selenium (the driver downloads itself).
    Uses its own persistent profile. Returns the webdriver.
    Raises a clear RuntimeError on failure."""
    try:
        from selenium import webdriver
    except Exception as e:
        raise RuntimeError(f"Missing 'selenium' (pip install selenium): {e}")
    name = (browser or "chrome").strip().lower()
    if name not in ("chrome", "edge", "brave"):
        raise RuntimeError(f"Browser not supported for login: {browser}")
    log(f"start_browser({name})")
    try:
        if name == "edge":
            from selenium.webdriver.edge.options import Options as EdgeOptions
            opts = EdgeOptions()
        else:
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            opts = ChromeOptions()
            if name == "brave":
                bbin = brave_binary()
                if not bbin:
                    raise RuntimeError("Cannot find Brave installed (brave.exe).")
                opts.binary_location = bbin
                log(f"brave binary: {bbin}")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        prof = profile_dir or automation_profile_dir(name)
        opts.add_argument(f"--user-data-dir={prof}")
        if not visible:
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
        log(f"profile: {prof} visible={visible}")
        drv = (webdriver.Edge(options=opts) if name == "edge"
               else webdriver.Chrome(options=opts))
        log("driver OK")
    except Exception as e:
        log(f"driver FAIL: {e}")
        raise RuntimeError(f"Could not open {name}: {str(e)[:250]}. "
                           "Install Chrome, Edge or Brave and try again.")
    try:
        # Hides the automation flag (Google is less suspicious)
        drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"})
    except Exception:
        pass
    try:
        drv.get(LOGIN_URL)
    except Exception as e:
        try:
            drv.quit()
        except Exception:
            pass
        raise RuntimeError(f"No internet or YouTube blocked: {str(e)[:150]}")
    return drv


def read_stored_session(browser: str, timeout: int = 60) -> list[dict]:
    """Silently re-reads (headless) the automation profile session.
    No windows. Returns [] if no session is saved."""
    drv = None
    try:
        drv = start_browser(browser, visible=False)
        drv.set_page_load_timeout(timeout)
        try:
            drv.get("https://www.youtube.com/")
        except Exception:
            pass
        cookies = read_cookies(drv)
        log(f"stored session {browser}: {len(cookies)} cookies, login={login_detected(cookies)}")
        return cookies
    except Exception as e:
        log(f"stored session FAIL: {e}")
        return []
    finally:
        close_browser(drv)


def read_cookies(driver) -> list[dict]:
    """Current browser cookies in our tolerant JSON format."""
    try:
        raw = driver.get_cookies() or []
    except Exception:
        return []
    out: list[dict] = []
    for c in raw:
        try:
            if not isinstance(c, dict) or not c.get("name"):
                continue
            domain = str(c.get("domain", "") or "")
            exp = c.get("expiry", "")
            try:
                exp = str(int(exp)) if exp else ""
            except Exception:
                exp = ""
            out.append({
                "domain": domain,
                "expirationDate": exp,
                "hostOnly": not domain.startswith("."),
                "httpOnly": bool(c.get("httpOnly", False)),
                "name": str(c.get("name", "")),
                "path": str(c.get("path", "/") or "/"),
                "sameSite": str(c.get("sameSite", "lax") or "lax"),
                "secure": str(bool(c.get("secure", False))).lower(),
                "session": str(not bool(exp)).lower(),
                "storeId": "0",
                "value": str(c.get("value", "") or ""),
            })
        except Exception:
            continue
    return out


def login_detected(cookies: list[dict]) -> bool:
    """True if there is a Google/YouTube session (SID + LOGIN_INFO)."""
    names = {c.get("name", "") for c in cookies if isinstance(c, dict)}
    return "SID" in names and "LOGIN_INFO" in names


def read_profile_session(browser: str) -> list[dict]:
    """Reads the REAL browser profile session (1 click, no automation).
    It's the most reliable: no 'unsafe browser' or drivers."""
    from . import browser_cookies
    log(f"reading profile for {browser}")
    cookies, _header = browser_cookies.refresh_from_browser(browser, "cache")
    log(f"{len(cookies)} cookies from profile {browser}")
    if not login_detected(cookies):
        raise RuntimeError(f"Your {browser} has no YouTube session: go to "
                           "youtube.com with your account and retry.")
    return cookies


def wait_for_login(driver, timeout: int = 300, poll: float = 2.0) -> list[dict]:
    """Waits (blocking, call in a thread) until login or timeout. Returns cookies."""
    t0 = time.time()
    last: list[dict] = []
    while time.time() - t0 < timeout:
        try:
            last = read_cookies(driver)
            if login_detected(last):
                return last
        except Exception:
            pass
        time.sleep(poll)
    return last


def close_browser(driver) -> None:
    try:
        driver.quit()
    except Exception:
        pass
