"""Regex metadata edits (beets-style rewrite rules).

Rule format (same as the user's regex-edits.json)::

    {"search": {"track": null, "artist": null,
                "album": "(.*) - Single", "albumArtist": null},
     "replace": {"track": null, "artist": null,
                 "album": "$1", "albumArtist": null}}

A rule fires when EVERY non-null search field regex-matches (re.search) the
corresponding metadata value. Each non-null replace field then becomes the
new value, with $1..$9 expanded from THAT field's search match groups
($$ = literal $). Null replace = keep the original value.
"""
from __future__ import annotations
import json
import os
import re

FIELDS = ("track", "artist", "album", "albumArtist")

# Hand-written files often use these names; mapped on load instead of
# dropping the rule (a "title" rule silently did nothing before).
FIELD_ALIASES = {"title": "track", "name": "track",
                 "albumartist": "albumArtist", "album_artist": "albumArtist",
                 "album-artist": "albumArtist"}


def _canon_key(key: str) -> str:
    try:
        k = str(key or "").strip()
        if k in FIELDS:
            return k
        return FIELD_ALIASES.get(k.lower(), k)
    except Exception:
        return str(key)


def blank_rule() -> dict:
    return {"search": {f: None for f in FIELDS},
            "replace": {f: None for f in FIELDS}}


def _exact_pattern(value: str) -> str:
    """Exact-match regex for a literal value."""
    try:
        return "^(?:" + re.escape(str(value or "")) + ")$"
    except Exception:
        return "^(?:)$"


def make_song_rule(original: dict, new_values: dict,
                   video_id: str = "") -> dict:
    """Per-song override rule: exact-match the (post-rule) original metadata,
    set only the changed fields. Stored in the SAME json list with a
    song_edit tag + videoId so the app can find/update it later
    (plain beets-style readers ignore the extra keys)."""
    try:
        orig = {f: str((original or {}).get(f, "") or "") for f in FIELDS}
        newv = {f: str((new_values or {}).get(f, "") or "") for f in FIELDS}
    except Exception:
        orig = {f: "" for f in FIELDS}
        newv = {f: "" for f in FIELDS}
    search = {}
    for f in ("track", "artist", "album"):
        search[f] = _exact_pattern(orig[f]) if orig[f] else None
    search["albumArtist"] = None
    replace = {}
    for f in ("track", "artist", "album"):
        replace[f] = (newv[f] if newv[f] != orig[f] else None)
    replace["albumArtist"] = None
    return {"search": search, "replace": replace,
            "song_edit": True, "videoId": str(video_id or "")}


def find_song_rule(rules: list[dict] | None, video_id: str):
    """(index, rule) of the per-song override for video_id, else (None, None)."""
    try:
        for i, r in enumerate(rules or []):
            if (isinstance(r, dict) and r.get("song_edit")
                    and str(r.get("videoId", "") or "") == str(video_id or "")
                    and video_id):
                return i, r
    except Exception:
        pass
    return None, None


def _compile(pattern: str):
    try:
        return re.compile(str(pattern or ""))
    except re.error:
        return None


def _expand_refs(template: str, match: "re.Match") -> str:
    """Expand $1..$9 ($$ escape) from a search match."""
    try:
        tpl = str(template or "")
    except Exception:
        return ""
    out: list[str] = []
    i = 0
    while i < len(tpl):
        ch = tpl[i]
        if ch == "$" and i + 1 < len(tpl):
            nxt = tpl[i + 1]
            if nxt == "$":
                out.append("$")
                i += 2
                continue
            if nxt.isdigit():
                try:
                    out.append(match.group(int(nxt)) or "")
                except Exception:
                    out.append("")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def apply_rules(meta: dict | None, rules: list[dict] | None) -> dict:
    """Return a NEW dict with the rules applied (original untouched)."""
    try:
        cur = {f: str((meta or {}).get(f, "") or "") for f in FIELDS}
    except Exception:
        cur = {f: "" for f in FIELDS}
    for rule in (rules or []):
        try:
            if not isinstance(rule, dict):
                continue
            search = rule.get("search") or {}
            replace = rule.get("replace") or {}
            matches: dict[str, re.Match] = {}
            fired = True
            for f in FIELDS:
                pat = search.get(f)
                if pat is None:
                    continue
                rx = _compile(pat)
                if rx is None:
                    fired = False
                    break
                try:
                    m = rx.search(cur.get(f, ""))
                except Exception:
                    m = None
                if m is None:
                    fired = False
                    break
                matches[f] = m
            if not fired:
                continue
            for f in FIELDS:
                tpl = replace.get(f)
                if tpl is None or f not in matches:
                    continue
                try:
                    cur[f] = _expand_refs(tpl, matches[f])
                except Exception:
                    pass
        except Exception:
            pass
    return cur


def import_local_cache(data: dict | None) -> list[dict]:
    """Convert a LastFMCache local-cache.json ({videoId: {track, artist,
    album, albumArtist}}) into per-song override rules. Values are the
    corrected metadata; matching is by videoId so no text anchors needed."""
    out: list[dict] = []
    try:
        for vid, meta in (data or {}).items():
            try:
                if not vid or not isinstance(meta, dict):
                    continue
                rep = {}
                for f in ("track", "artist", "album", "albumArtist"):
                    try:
                        v = meta.get(f)
                        rep[f] = str(v) if v is not None and str(v) != "" else None
                    except Exception:
                        rep[f] = None
                if all(rep.get(f) is None for f in ("track", "artist", "album")):
                    continue
                out.append({"search": {f: None for f in FIELDS},
                            "replace": rep,
                            "song_edit": True, "videoId": str(vid),
                            "from": "local-cache"})
            except Exception:
                pass
    except Exception:
        pass
    return out


def describe_rule(rule: dict) -> str:
    """One-line human summary for the listbox."""
    try:
        if isinstance(rule, dict) and rule.get("song_edit"):
            rep = (rule.get("replace") or {})
            chg = ", ".join(f for f in ("track", "artist", "album") if rep.get(f) is not None)
            return f"♪ song override ({chg or 'no changes'})"
        parts = []
        search = (rule or {}).get("search") or {}
        replace = (rule or {}).get("replace") or {}
        for f in FIELDS:
            s = search.get(f)
            if s is None:
                continue
            r = replace.get(f)
            parts.append(f"{f}: /{s}/ -> {r if r is not None else '(keep)'}")
        return "; ".join(parts) if parts else "(empty rule)"
    except Exception:
        return "(invalid rule)"


def validate_rule(rule: dict) -> str:
    """'' when ok, else an error message."""
    try:
        if not isinstance(rule, dict):
            return "Rule must be an object."
        for sec in ("search", "replace"):
            sub = rule.get(sec)
            if not isinstance(sub, dict):
                return f"'{sec}' must be an object."
            for f in FIELDS:
                v = sub.get(f)
                if v is None:
                    continue
                if not isinstance(v, str):
                    return f"{sec}.{f} must be a string or null."
                if sec == "search" and _compile(v) is None:
                    return f"Bad regex in search.{f}."
        search = rule.get("search") or {}
        if all(search.get(f) is None for f in FIELDS):
            # App per-song overrides match by videoId, not by text.
            if rule.get("song_edit") and str(rule.get("videoId", "") or ""):
                return ""
            return "Rule matches everything (all search fields null)."
        return ""
    except Exception as e:
        return str(e) or "Invalid rule."


def _canon_section(sub: dict) -> dict:
    """Map alias field names to canonical ones (title->track, ...)."""
    out: dict = {}
    try:
        for k, v in (sub or {}).items():
            out[_canon_key(k)] = v
    except Exception:
        pass
    return out


def load_rules(path: str) -> list[dict]:
    rules, _, _ = load_rules_report(path)
    return rules


def load_rules_report(path: str) -> tuple[list, list, list]:
    """(valid_rules, kept_raw, rejected).

    - valid_rules: normalized, app-managed.
    - kept_raw: entries the app does not understand, preserved VERBATIM on
      save (never dropped: dropping them once destroyed user data).
    - rejected: [(index, reason, snippet)] only for scalars/non-objects or
      unreadable files (structural garbage, never a dict entry).
    """
    out: list[dict] = []
    kept: list[dict] = []
    rejected: list[tuple[int, str, str]] = []
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f) or []
            if isinstance(data, dict):
                data = [data]
            for i, r in enumerate(data or []):
                try:
                    if not isinstance(r, dict):
                        rejected.append((i, "not an object", str(r)[:60]))
                        continue
                    nr = {"search": {f: _canon_section(r.get("search") or {}).get(f)
                                     for f in FIELDS},
                          "replace": {f: _canon_section(r.get("replace") or {}).get(f)
                                      for f in FIELDS}}
                    for k, v in r.items():
                        if k not in ("search", "replace"):
                            nr[k] = v
                    err = validate_rule(nr)
                    if err:
                        # Unknown shape (not search/replace dicts, bad types):
                        # keep verbatim instead of destroying it.
                        try:
                            _s, _r = r.get("search"), r.get("replace")
                        except Exception:
                            _s, _r = None, None
                        if isinstance(_s, dict) and isinstance(_r, dict):
                            kept.append(r)
                        else:
                            rejected.append((i, err, describe_rule(nr)[:80]))
                        continue
                    out.append(nr)
                except Exception as e:
                    rejected.append((i, str(e)[:100], ""))
    except Exception as e:
        rejected.append((-1, f"file error: {e}"[:120], ""))
    return out, kept, rejected


def save_rules(path: str, rules: list[dict], keep: list[dict] | None = None) -> bool:
    """Write valid rules normalized + kept entries VERBATIM.

    `keep` (unknown shapes) is never normalized, reordered or dropped: a
    lossy save once destroyed the user's hand-written rules.
    """
    try:
        clean = []
        for r in (rules or []):
            if isinstance(r, dict) and not validate_rule(r):
                nr = {"search": {f: (r.get("search") or {}).get(f) for f in FIELDS},
                      "replace": {f: (r.get("replace") or {}).get(f) for f in FIELDS}}
                for k, v in r.items():
                    if k not in ("search", "replace"):
                        nr[k] = v
                clean.append(nr)
        for r in (keep or []):
            if isinstance(r, dict):
                clean.append(r)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


DEFAULT_RULES = [
    {"search": {"track": None, "artist": None, "album": "(.*) - Single", "albumArtist": None},
     "replace": {"track": None, "artist": None, "album": "$1", "albumArtist": None}},
    {"search": {"track": None, "artist": None, "album": "(.*) - EP", "albumArtist": None},
     "replace": {"track": None, "artist": None, "album": "$1", "albumArtist": None}},
]
