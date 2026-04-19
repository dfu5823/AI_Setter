# AI Setter Scripts

Run these from the repo root with the `ai_setter` conda environment available.
Each script uses `/Users/danfu/miniconda3/envs/ai_setter/bin/python` by default; override with `AI_SETTER_PYTHON=/path/to/python`.

- `scripts/preprocess_data`: export/cache Kilter DB data, generate sequences, figures, generated climbs, and manifests.
- `scripts/generate_sequences`: refresh generated climb PNGs and the 100-climb sequence review set.
- `scripts/train_setters`: run the full preprocess pipeline with neural training enabled.
- `scripts/show_beta`: start or target the web app beta page for a climb name or grade.
- `scripts/generate_figures`: regenerate figure/table artifacts through the preprocess pipeline.
- `scripts/generate_climbs`: generate climb PNGs without rerunning the full pipeline.

Examples:

```bash
scripts/preprocess_data --limit 5000
scripts/generate_sequences --setter-limit 10000
scripts/train_setters --epochs 35 --batch-size 512
scripts/show_beta --name "Tap Tap Tap" --angle 40
scripts/show_beta --grade V5 --angle 40
scripts/generate_climbs --count 100
scripts/generate_climbs --per-grade 3 --min-grade 3 --max-grade 8 --setter graph
```
