# EasyQuant brand assets

| File | Description |
|------|-------------|
| `logo.svg` | Horizontal logo: icon + wordmark (vector) |
| `logo-icon.svg` | Square mark only (64×64 viewBox), for favicons / app icons |
| `logo-mono.svg` | Single-color variant (print, dark toolbar) |
| `logo.png` / `logo@2x.png` | Raster wordmark, 640px / 1280px wide |
| `logo-icon.png` | Raster mark, 512×512 (same file copied to `eqlib/static/` for matplotlib) |
| `logo-mono.png` | Raster monochrome, 640px wide |

Regenerate PNGs (matplotlib, no Cairo):

```bash
python tools/generate_logo_png.py
```

Design notes: dark squircle, single equity stroke (slate to white gradient in SVG), and a dot at the series end. Minimal, print-safe SVG (ASCII-only comments if any).
