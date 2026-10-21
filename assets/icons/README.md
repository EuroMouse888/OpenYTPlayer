# assets/icons

The application icon lives here and **is part of the repo**, so a fresh clone
always has one.

| File | Use |
|------|-----|
| `app.ico` | Windows title bar / taskbar / Alt+Tab (all sizes inside) |
| `app.png` | 256 px, used by the in-app title bar and the README |
| `app_64.png` | 64 px fallback |

## Regenerating it

```powershell
py -m app.appicon
```

Draws it in the app's own brand colours, independently of your theme, so it
looks the same for everyone. To match a specific theme instead:

```powershell
py -m app.appicon --theme themes\DefaultTheme\theme.json
```

## Using your own image

🎨 Customize → **Window** → *App icon…* → pick any `.png` / `.jpg` / `.gif` /
`.webp` / `.ico`. The path is stored in `config/theme.json`
(`ventana.icono`) and takes priority over the shipped icon. *Reset* goes back
to the default.

## Notes

- Square images, 256×256 or more, scale best.
- Transparent PNG looks best.
- This folder is yours to edit: drop your own artwork here and it will never
  be overwritten.