# AI_Setter
 Ever feel like your favorite climbing board app (eg. Kilter Board App) just doesn't have the right climbs for YOU? Tired of spending HOURS setting climbs only to find that they are total CHOSS? Try using the AI Setter to set climbs according to YOUR preferences and grade -- with a simple touch! Created by Dan Fu -- message me for questions/to contribute.

## What is currently implemented

- A local web app in `webapp/` for browsing the screenshots in `kilter_climbs_data/app_screenshots_dataset/`.
- Browser-side and backend extraction of Kilter hold coordinates from screenshot pixels using the existing color convention: cyan/teal for any hands, green for starts, orange for feet, and purple/magenta for finishes.
- Coordinate-backed climb rendering in 2D and a camera-projected 3D wall view.
- A `Set a Climb` editor that stores new climbs as JSON coordinates in `webapp/data/saved_climbs.json`.
- Generate Climb controls for random, sequential, graph, and neural-network setters.
- A `Generate beta` button that overlays the looping climber animation on demand instead of auto-starting it.
- A Beta Buddy upload path for screenshot-to-beta extraction in the web app.
- Separate pages for finding climbs, setting climbs, and adjusting/generated beta animation.
- Climb lookup sorting by name, grade, and whether the climb was set by a user.
- On-demand `outputs/` artifacts including generated climb samples, summary metrics, heatmaps, and a PyTorch checkpoint.
- A Kilter SQLite DB extraction pipeline for `kilter_climbs_data/oct2025-app-climbs.db`, configured by `ai_setter_config.json`.
- Backend validation that climbs have at most two start holds, at most two finish holds, and valid board coordinates.
- A first-pass looping canvas animation of a physics-constrained monkey stick figure climbing the estimated hand sequence in both 2D and 3D views.

The OCR metadata is cached in `webapp/data/source_climbs_metadata.json`; missing grades remain `Unknown`.

The beta climber uses a derived scale fallback: public Kilter Board listings describe the Original 12x12 board as 12 feet wide by 12 feet tall, but I did not find an official published bolt-grid spacing. The app derives approximate coordinate spacing from the 12 foot board size and the 35 by 39 coordinate bounds used by the screenshot parser.

## Run the web app locally

Use the project conda env:

```bash
conda activate ai_setter
python -m pip install -r requirements.txt
python webapp/server.py --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Deploy with Streamlit from GitHub

This repo includes a Streamlit entrypoint for Streamlit Community Cloud:

```text
streamlit_app.py
```

To deploy:

1. Push this repository to GitHub.
2. Open Streamlit Community Cloud and create a new app from the GitHub repo.
3. Set the main file path to `streamlit_app.py`.
4. Deploy.

Streamlit installs dependencies from `requirements.txt` and uses `runtime.txt` for the Python version. The app reuses the existing AI Setter sequence, rendering, and generator modules, but it loads climb search data from `webapp/data/streamlit_climbs.json` instead of the full Kilter DB. That compact artifact contains the 10 most ascended climbs for each grade at every angle, plus the 1,000 most ascended climbs at every angle. If that artifact is not available, the Streamlit app falls back to `webapp/data/climbs_dataset.json`.

Rebuild the compact artifact from a local full CSV with:

```bash
python scripts/build_streamlit_dataset.py
```

Note: GitHub rejects normal Git blobs over 100 MB. Keep large DB/model/output artifacts out of the deployment branch or store them with Git LFS/external storage; the Streamlit app can run from the bundled compact dataset.

For a local Streamlit smoke test:

```bash
conda activate ai_setter
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

You can also run without activating the shell:

```bash
conda run -n ai_setter python webapp/server.py --port 8000
```

Refresh screenshot names from OCR metadata with:

```bash
conda run -n ai_setter python webapp/server.py --refresh-metadata
```

Rebuild the coordinate dataset and generate legacy output artifacts with:

```bash
conda run -n ai_setter python webapp/server.py --refresh-metadata
conda run -n ai_setter python -m ai_setters.generate_outputs --count 32
```

For the full DB-backed preprocessing and PNG artifact pipeline, use:

```bash
MPLCONFIGDIR=/tmp conda run -n ai_setter python -m ai_setters.preprocess_and_train
```

For the full neural training cycle on the configured DB data source, use:

```bash
MPLCONFIGDIR=/tmp conda run -n ai_setter python -m ai_setters.preprocess_and_train --train-neural --epochs 35 --batch-size 512
```

This pipeline writes PNG figures and metric tables, DB CSV exports, generated climb PNGs for every V0-V14 grade under each setter in `outputs/generated_climbs/`, sequence review images in `outputs/sequence_review/heuristic_100/`, and final model artifacts in `outputs/models/`.

To open the manual sequence relabeling tool for the 100 selected climbs:

```bash
MPLCONFIGDIR=/tmp conda run -n ai_setter python -m ai_setters.label_sequences
```

## Kilter DB preprocessing

The default data source is the October 2025 Kilter DB in `ai_setter_config.json`. The full DB export and report are generated with:

```bash
MPLCONFIGDIR=/tmp conda run -n ai_setter python -m ai_setters.kilter_db
```

This writes:

- `outputs/data/all_kilter_climbs.csv`
- `outputs/data/ascended_kilter_climbs.csv`
- `outputs/metrics/kilter_db_field_report.json`
- `outputs/metrics/kilter_db_field_report.md`
- `outputs/figures/kilter_grade_by_angle_violin.png`
- `outputs/figures/db_sample_climbs_4up.png`
- `kilter_climbs_output/output_template_labeled_grid.png`

For a fast smoke test:

```bash
MPLCONFIGDIR=/tmp conda run -n ai_setter python -m ai_setters.kilter_db --limit 500
```

To use the old screenshot dataset path instead of the DB-backed dataset:

```bash
AI_SETTER_DATA_SOURCE=screenshots conda run -n ai_setter python -m ai_setters.generate_outputs --count 32
```

## Tests

```bash
conda run -n ai_setter python -m unittest discover -s tests
```
## Scripts

For a full pipeline with neural training and all outputs, use:
scripts/train_setters --epochs 35 --batch-size 512
scripts/generate_sequences --setter-limit 0
scripts/generate_climbs --count 100 --setter-limit 0

scripts/preprocess_data --limit 5000
scripts/generate_sequences --setter-limit 10000
scripts/train_setters --epochs 35 --batch-size 512
scripts/show_beta --name "Tap Tap Tap" --angle 40
scripts/show_beta --grade V5 --angle 40
scripts/generate_figures --limit 5000
scripts/generate_climbs --count 100
scripts/generate_climbs --per-grade 3 --min-grade 3 --max-grade 8 --setter graph
