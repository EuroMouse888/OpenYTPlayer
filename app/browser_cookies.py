"""Session via BROWSER cookies (Chrome/Edge/Firefox...).

Uses your browser's real session (which Google keeps alive for months and
auto-refreshes) instead of an exported JSON that expires in days. No new
dependencies: yt-dlp already knows how to read and decrypt those stores.
"""
from __future__ import annotations
import os
import shutil

BROWSER_CANDIDATES = ["chrome", "edge", "brave", "vivaldi", "opera", "firefox", "chromium"]

_DOMAINS_OK = ("youtube.com", "music.youtube.com", "google.com")


def _cookie_matches_yt(domain: str) -> bool:
    d = (domain or "").lower().lstrip(".")
    return any(d == k or d.endswith("." + k) for k in _DOMAINS_OK)


def detect_browsers() -> list[str]:
    """Browsers that look installed (binary or profile). Best-effort."""
    found: list[str] = []
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    home = os.path.expanduser("~")
    profile_dirs = {
        "chrome": [os.path.join(local, "Google", "Chrome", "User Data")],
        "edge": [os.path.join(local, "Microsoft", "Edge", "User Data")],
        "brave": [os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data")],
        "vivaldi": [os.path.join(local, "Vivaldi", "User Data")],
        "opera": [os.path.join(roaming, "Opera Software", "Opera Stable")],
        "firefox": [os.path.join(roaming, "Mozilla", "Firefox", "Profiles"),
                    os.path.join(home, ".mozilla", "firefox")],
        "chromium": [os.path.join(home, ".config", "chromium")],
    }
    binaries = {"chrome": ["chrome", "google-chrome"],
                "edge": ["msedge", "microsoft-edge"],
                "brave": ["brave", "brave-browser"],
                "vivaldi": ["vivaldi"],
                "opera": ["opera"],
                "firefox": ["firefox"],
                "chromium": ["chromium", "chromium-browser"]}
    for b in BROWSER_CANDIDATES:
        try:
            if any(shutil.which(x) for x in binaries.get(b, [b])):
                found.append(b)
                continue
            for d in profile_dirs.get(b, []):
                if os.path.isdir(d):
                    found.append(b)
                    break
        except Exception:
            continue
    return found


def jar_to_list(jar) -> list[dict]:
    """Converts a CookieJar to the cookiesYT.json list-of-dicts format."""
    out: list[dict] = []
    try:
        cookies = list(jar)
    except Exception:
        return out
    for c in cookies:
        try:
            domain = getattr(c, "domain", "") or ""
            if not _cookie_matches_yt(domain):
                continue
            name = getattr(c, "name", "") or ""
            if not name:
                continue
            expires = getattr(c, "expires", None)
            try:
                exp = str(int(expires)) if expires else ""
            except Exception:
                exp = ""
            secure = bool(getattr(c, "secure", False))
            rest = {}
            try:
                rest = dict(getattr(c, "_rest", {}) or {})
            except Exception:
                pass
            out.append({
                "domain": domain if domain.startswith(".") else domain,
                "expirationDate": exp,
                "hostOnly": not domain.startswith("."),
                "httpOnly": bool(getattr(c, "has_nonstandard_attr", lambda k: False)("httpOnly")),
                "name": name,
                "path": getattr(c, "path", "/") or "/",
                "sameSite": str(rest.get("SameSite", "lax") or "lax"),
                "secure": str(secure).lower(),
                "session": str(not bool(expires)).lower(),
                "storeId": "0",
                "value": getattr(c, "value", "") or "",
            })
        except Exception:
            continue
    return out


def extract_youtube_cookies(browser: str) -> list[dict]:
    """Reads the browser's YouTube cookies. Raises a clear exception on failure."""
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
    except Exception as e:
        raise RuntimeError(f"yt-dlp without browser-cookie support: {e}")
    name = (browser or "").strip().lower()
    if not name:
        raise RuntimeError("Choose a browser (Chrome/Edge/Firefox...)")
    try:
        jar = extract_cookies_from_browser(name)
    except Exception as e:
        raise RuntimeError(f"Could not read '{name}': {str(e)[:200]}. "
                           "Open it, sign in at youtube.com with your account and retry.")
    cookies = jar_to_list(jar)
    if not cookies:
        raise RuntimeError(f"'{name}' has no YouTube session. Go to youtube.com first.")
    return cookies


def refresh_from_browser(browser: str, cache_dir: str = "cache") -> tuple[list[dict], str, str]:
    """Extracts, saves cookies.txt+browser.json and returns (cookies, header)."""
    from . import cookies_util
    cookies = extract_youtube_cookies(browser)
    header = cookies_util.cookies_to_header_value(cookies)
    cookies_util.cookies_to_netscape_file(cookies, os.path.join(cache_dir, "cookies.txt"))
    try:
        cookies_util.build_ytmusicapi_auth_file(cookies, os.path.join(cache_dir, "browser.json"))
    except Exception:
        pass
    return cookies, header
