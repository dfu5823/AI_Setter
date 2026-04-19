"""CLI for regenerating generated climb PNGs without the full training pipeline."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

from .dataset import ROOT
from .generators import EmpiricalSequentialSetter, GraphSetter, NeuralSetter, RandomSetter
from .preprocess_and_train import GRADES
from .refresh_sequence_artifacts import DEFAULT_CSV, load_records_from_csv
from .rendering import render_climb_png


SETTER_CLASSES = {
    "random": RandomSetter,
    "sequential": EmpiricalSequentialSetter,
    "graph": GraphSetter,
    "neural": NeuralSetter,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate coordinate-backed climb PNGs.")
    parser.add_argument("--count", type=int, default=100, help="Total climbs to generate when --per-grade is not set.")
    parser.add_argument("--per-grade", type=int, default=None, help="Generate this many climbs for each grade and setter.")
    parser.add_argument("--min-grade", type=int, default=0)
    parser.add_argument("--max-grade", type=int, default=14)
    parser.add_argument("--angle", default="40")
    parser.add_argument("--setter", choices=[*SETTER_CLASSES.keys(), "all"], default="all")
    parser.add_argument("--hand-count", type=int, default=8)
    parser.add_argument("--foot-count", type=int, default=6)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--setter-limit", type=int, default=50000)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "generated_climbs" / "custom")
    args = parser.parse_args()

    records = load_records_from_csv(args.csv, limit=args.setter_limit) if args.csv.exists() else []
    setters = list(SETTER_CLASSES) if args.setter == "all" else [args.setter]
    grades = [f"V{i}" for i in range(args.min_grade, args.max_grade + 1)]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    models: dict[str, Any] = {}
    models_dir = ROOT / "outputs" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for setter in setters:
        model = SETTER_CLASSES[setter](records, models_dir / "neural_setter.pt") if setter == "neural" else SETTER_CLASSES[setter](records)
        models[setter] = model
        if setter != "neural":
            with (models_dir / f"{setter}_setter.pkl").open("wb") as file:
                pickle.dump(model, file)

    generated = []
    if args.per_grade is not None:
        plan = [(setter, grade, copy_index) for setter in setters for grade in grades for copy_index in range(args.per_grade)]
    else:
        base = [(setter, grade, 0) for setter in setters for grade in grades]
        plan = [base[index % len(base)] for index in range(args.count)]

    for index, (setter, grade, copy_index) in enumerate(plan, start=1):
        climb = models[setter].create(
            grade=grade,
            angle=str(args.angle),
            seed=args.seed + index + copy_index * 10000,
            options={"hand_count": args.hand_count, "foot_count": args.foot_count},
        )
        climb["setter"] = setter
        generated.append({"index": index, "setter": setter, "grade": grade, "name": climb.get("name")})
        setter_dir = args.output_dir / setter
        setter_dir.mkdir(parents=True, exist_ok=True)
        render_climb_png(climb, setter_dir / f"{index:03d}_{setter}_{grade}.png", title=f"{setter} {grade} {args.angle} deg")

    (args.output_dir / "manifest.json").write_text(json.dumps(generated, indent=2), encoding="utf-8")
    print(f"Generated {len(generated)} climb PNGs in {args.output_dir}")


if __name__ == "__main__":
    main()
