# AI_Setter
 Ever feel like your favorite climbing board app (eg. Kilter Board App) just doesn't have the right climbs for YOU? Tired of spending HOURS setting climbs only to find that they are total CHOSS? Try using the AI Setter to set climbs according to YOUR preferences and grade -- with a simple touch! Created by Dan Fu -- message me for questions/to contribute.

## What is currently implemented

- A local dependency-light web app in `webapp/` for browsing the screenshots in `kilter_climbs_data/`.
- Browser-side extraction of Kilter hold coordinates from screenshot pixels using the existing color convention: cyan/teal for any hands, green for starts, orange for feet, and purple/magenta for finishes.
- Coordinate-backed climb rendering in 2D and an oblique 3D wall view.
- A `Set a Climb` editor that stores new climbs as JSON coordinates in `webapp/data/saved_climbs.json`.
- A `Generate beta` button that overlays the looping climber animation on demand instead of auto-starting it.
- Backend validation that climbs have at most two start holds, at most two finish holds, and valid board coordinates.
- A first-pass looping canvas animation of a physics-constrained monkey stick figure climbing the estimated hand sequence in both 2D and 3D views.

The original parser and setter code is still prototype-level. The web app does not require OCR; names default to the screenshot filename and grades are `Unknown` for imported screenshots until structured metadata is added.

## Run the web app locally

Use the project conda env:

```bash
conda activate ai_setter
python webapp/server.py --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

You can also run without activating the shell:

```bash
conda run -n ai_setter python webapp/server.py --port 8000
```

Refresh screenshot names from OCR metadata with:

```bash
conda run -n ai_setter python webapp/server.py --refresh-metadata
```

## Tests

```bash
conda run -n ai_setter python -m unittest discover -s tests
```
