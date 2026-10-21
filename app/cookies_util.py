"""Tolerant parsing of cookiesYT.json and conversion to useful formats."""
from __future__ import annotations
import json
import os
import re


def _repair_json_text(text: str) -> str:
    """Repairs the typical exported JSON with missing commas after "path": "/"."""
    # 1) Inserts the missing comma between string/number/true/false and the next "key":
    #    Matches: "...."  \n  "xxx"  without a comma before -> inserts comma.
    #    Only when the comma is missing (comma negative lookbehind).
    text = re.sub(r'("[^"]*"|\d+|true|false|null)\s*\n(\s*")', r'\1,\n\2', text)
    # 2) Repairs unquoted values like: "value": CIYD  -> "value": "CIYD"
    def _quote_bare(m):
        prefix, val = m.group(1), m.group(2).strip()
        if val.startswith('"'):
            return m.group(0)
        val = val.rstrip(",")
        had_comma = m.group(0).rstrip().endswith(",")
        return f'{prefix}"{val}"' + ("," if had_comma and not m.group(0).rstrip().endswith('",') else "")
    text = re.sub(r'("value"\s*:\s*)([^",\n\}\]]+)(\s*,?)', _quote_bare, text)
    return text


def read_cookies_json_tolerant(path: str) -> list[dict]:
    """Reads cookiesYT.json even when malformed (missing commas)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read().strip()
    if not raw:
        return []
    # Direct attempt
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except Exception:
        pass
    # Repaired attempt
    try:
        fixed = _repair_json_text(raw)
        data = json.loads(fixed)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except Exception as e:
        raise ValueError(f"Could not parse {path}: {e}")
    return []


def cookies_to_dict(cookies: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in cookies:
        try:
            name = str(c.get("name", "")).strip()
            val = str(c.get("value", ""))
            if name:
                out[name] = val
        except Exception:
            continue
    return out


def cookies_to_header_value(cookies: list[dict]) -> str:
    d = cookies_to_dict(cookies)
    return "; ".join(f"{k}={v}" for k, v in d.items() if k)


def cookies_to_netscape_file(cookies: list[dict], out_path: str) -> str:
    """Converts to Netscape format (cookies.txt) for yt-dlp --cookies."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            try:
                domain = str(c.get("domain", ".youtube.com"))
                # TRUE flag if the domain starts with a dot
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = str(c.get("path", "/"))
                secure = "TRUE" if str(c.get("secure", "false")).lower() == "true" else "FALSE"
                exp = c.get("expirationDate", "")
                try:
                    exp_int = int(float(str(exp)))
                except Exception:
                    exp_int = 0
                name = str(c.get("name", ""))
                value = str(c.get("value", ""))
                if not name:
                    continue
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{exp_int}\t{name}\t{value}\n")
            except Exception:
                continue
    return out_path


def build_ytmusicapi_auth_file(cookies: list[dict], out_path: str) -> str:
    """Generates a browser.json file valid for ytmusicapi.YTMusic(auth=...).

    Includes `authorization: SAPISIDHASH ...` so ytmusicapi detects
    AuthType.BROWSER and can use the library (playlists/liked). The value
    is only recalculated on each request; a valid initial one is enough here.
    """
    from ytmusicapi.auth.browser import initialize_headers
    from ytmusicapi.helpers import get_authorization
    from ytmusicapi.constants import YTM_DOMAIN
    cookie_header = cookies_to_header_value(cookies)
    headers = dict(initialize_headers())
    # ytmusicapi expects lowercase keys (setup_browser stores them that way)
    base = {k.lower(): v for k, v in headers.items()}
    base["cookie"] = cookie_header
    base["x-goog-authuser"] = "0"
    base["origin"] = YTM_DOMAIN
    base["user-agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    d = cookies_to_dict(cookies)
    sapisid = d.get("__Secure-3PAPISID") or d.get("SAPISID") or d.get("__Secure-1PAPISID") or ""
    if sapisid:
        try:
            base["authorization"] = get_authorization(f"{sapisid} {YTM_DOMAIN}")
        except Exception:
            pass
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=True, indent=4, sort_keys=True)
    return out_path
