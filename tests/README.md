# Verification (tests)

Real interface testing, not simulations: it starts the real `MainWindow` and
inspects the live widget tree.

```powershell
py tests\gui_check.py
```

Output: `=== GUI: N/N passed ===` and exit code 0.

## What it covers

| Group | What it checks |
|-------|----------------|
| A | A progressive list load **never destroys** the rows already painted (no flicker), neither when the same tracks arrive again with richer fields, nor when "Show more" is pressed |
| B | The channel window: no `ttk` (no system grey), real tabs, **real albums** from YouTube Music with their `browseId` and covers, and clicking an album opens it inside the app |
| C | Clicking the channel chip always asks for a real `channelId` `UC...` (never an album, never the browser) |
| D | The window size survives closing and reopening, **without drift** between restarts (including in a separate process) |
| E | The Last.fm counter is the real `userplaycount` (286 for *Virtuous suicide*), **Japanese/Chinese titles too** (261 for *咲かせ☆咲かせ*), returns `-1` — not an invented number — when it does not exist, and the **player** shows `⟳ N plays on Last.fm` with the song's edited data |
| F | The search box and the sliders take the theme colours, and the theme editor has the **Widgets** tab |
| G | Clicking the channel **never** opens an album (including from the context menu), the windows show no Windows caption and carry the icon, the right-click menu takes its colours from the theme, and editing a song asks Last.fm again |

## Notes

- It uses **guest mode** (`use_account=False`): it never touches your
  YouTube Music session.
- Group F saves and restores the colours of `config/theme.json`; they are left
  exactly as they were.
- It needs a connection (InnerTube + Last.fm). There is no offline mode.
- `tests/gui_size.py` is a small helper that prints the real geometry of the
  window and its list panel, useful when a theme breaks the layout.
