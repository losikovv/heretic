# HereticBuilder

Minimal local tools for exploring and editing the HereticSheets SQLite snapshot.

The database stays in the parent project at `../data/heretic_db.sqlite`.

## HereticBuilder

```bash
python3 tools/roster_builder.py
```

Open `http://127.0.0.1:4175`.

## Static Build

Build a serverless Codex export for static hosts such as GitHub Pages:

```bash
python3 tools/builder.py build
```

For a GitHub Pages project site, pass the repository path:

```bash
python3 tools/builder.py build --base-path /codex --mount-codex-at-root
```

The generated site is written to `../dist/`.

The CLI reads `../heretic.toml` by default. Named profiles are available for
the current project Pages and organization Pages shapes:

```bash
python3 tools/builder.py build --profile project-pages
python3 tools/builder.py build --profile org-pages
```

## Unit Image Pixelizer

Create low-resolution, limited-palette 90s-style PNGs from the unit image links
stored in `datasheet.bannerImage` and `datasheet.rowImage`:

```bash
python3 tools/unit_image_pixelizer.py --colors 16 --max-side 96 --scale 4
```

Useful discovery modes:

```bash
python3 tools/unit_image_pixelizer.py --print-urls
python3 tools/unit_image_pixelizer.py --dry-run --kind row --limit 10
```

The app serves the checked-in production image pack from
`assets/unit-images/` and `assets/faction-images/`. The pixelizer writes
intermediate generated files under `../generated/unit_images_90s/`; copy the
selected PNGs and `manifest.csv` into `assets/unit-images/` when refreshing the
production pack.
It requires Pillow for image processing:

```bash
python3 -m pip install Pillow
```

On macOS it can also fall back to the built-in `sips` command:

```bash
python3 tools/unit_image_pixelizer.py --engine sips --name Abaddon
```
